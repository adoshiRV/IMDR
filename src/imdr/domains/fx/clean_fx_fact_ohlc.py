"""FX OHLC data cleaning module.

Detects and corrects data quality issues in [fx].[fact_ohlc]:
  - Non-positive prices  → NULL all price columns
  - Hard-bound violations → NULL all price columns
  - Robust outliers       → NULL all price columns
  - Bid > Ask inversions  → Swap bid and ask

Each rule is idempotent — safe to re-run.  Dry-run mode (default)
shows what would change without writing.

Usage:
    runner = CleaningRunner(connector, reader, rules, dry_run=True)
    results = runner.run()
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pandas as pd
import structlog
from sqlalchemy import text

from imdr.connectors.mssql import MSSQLConnector
from imdr.connectors.reader import AnalyticalReader

log = structlog.get_logger(__name__)

TABLE = "[fx].[fact_ohlc]"

PRICE_COLUMNS = [
    "open_px",
    "high_px",
    "low_px",
    "close_px",
    "mid_px",
    "mid_mean_px",
    "mid_median_px",
    "bid",
    "ask",
]


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class CleaningAction:
    """One correction applied (or proposed in dry-run) to a single row."""

    rule_name: str
    row_id: int
    ts: datetime
    symbol: str
    series: str
    action: str  # "null_prices" | "swap_bid_ask"
    detail: str  # human-readable


@dataclass
class CleaningResult:
    """Aggregate result for one rule across all detected rows."""

    rule_name: str
    actions: list[CleaningAction] = field(default_factory=list)
    dry_run: bool = True

    @property
    def count(self) -> int:
        return len(self.actions)


# ---------------------------------------------------------------------------
# ABC
# ---------------------------------------------------------------------------

class CleaningRule(ABC):
    """Base class for cleaning rules.

    Each rule knows how to *detect* bad rows and how to *fix* them.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Short identifier for this rule (e.g. 'non_positive')."""
        ...

    @property
    @abstractmethod
    def action_label(self) -> str:
        """What this rule does (e.g. 'null_prices')."""
        ...

    @abstractmethod
    def detect(
        self,
        reader: AnalyticalReader,
        table: str = TABLE,
        where: str = "",
        params: dict[str, Any] | None = None,
    ) -> pd.DataFrame:
        """Return DataFrame of rows needing correction.  MUST include 'id'."""
        ...

    @abstractmethod
    def build_update_sql(self, ids: list[int]) -> str:
        """Return UPDATE statement for a batch of row IDs."""
        ...

    def describe(self, row: pd.Series) -> str:
        """Human-readable description of the correction for one row."""
        return f"{self.name}: {self.action_label} for {row.get('symbol', '?')} @ {row.get('ts', '?')}"


# ---------------------------------------------------------------------------
# Rule implementations
# ---------------------------------------------------------------------------

_NULL_SET = ", ".join(f"[{c}] = NULL" for c in PRICE_COLUMNS)


class NonPositivePriceRule(CleaningRule):
    """NULL out rows where any price column is non-positive."""

    def __init__(self, columns: list[str] | None = None) -> None:
        self._columns = columns or PRICE_COLUMNS

    @property
    def name(self) -> str:
        return "non_positive"

    @property
    def action_label(self) -> str:
        return "null_prices"

    def detect(
        self,
        reader: AnalyticalReader,
        table: str = TABLE,
        where: str = "",
        params: dict[str, Any] | None = None,
    ) -> pd.DataFrame:
        or_clauses = " OR ".join(f"[{c}] <= 0" for c in self._columns)
        sql = f"""
            SELECT [id], [ts], [symbol], [series],
                   {', '.join(f'[{c}]' for c in self._columns)}
            FROM {table}
            WHERE ({or_clauses}) {where}
        """
        return reader.read_sql(sql, params)

    def build_update_sql(self, ids: list[int]) -> str:
        id_list = ", ".join(str(i) for i in ids)
        return f"UPDATE {TABLE} SET {_NULL_SET} WHERE [id] IN ({id_list})"

    def describe(self, row: pd.Series) -> str:
        bad = [c for c in self._columns if pd.notna(row.get(c)) and float(row[c]) <= 0]
        return f"non-positive in {', '.join(bad)}: {row['symbol']} {row['series']} @ {row['ts']}"


class HardBoundViolationRule(CleaningRule):
    """NULL out rows where close_px falls outside per-symbol hard bounds."""

    def __init__(
        self,
        ranges: dict[str, tuple[float, float]],
        value_column: str = "close_px",
    ) -> None:
        self._ranges = ranges
        self._value_col = value_column

    @property
    def name(self) -> str:
        return "hard_bound"

    @property
    def action_label(self) -> str:
        return "null_prices"

    def detect(
        self,
        reader: AnalyticalReader,
        table: str = TABLE,
        where: str = "",
        params: dict[str, Any] | None = None,
    ) -> pd.DataFrame:
        if not self._ranges:
            return pd.DataFrame()

        when_clauses = []
        for sym, (lo, hi) in self._ranges.items():
            when_clauses.append(
                f"([symbol] = '{sym}' AND ([{self._value_col}] < {lo} OR [{self._value_col}] > {hi}))"
            )
        filter_expr = " OR ".join(when_clauses)

        sql = f"""
            WITH flagged AS (
                SELECT [id], [ts], [symbol], [series], [{self._value_col}],
                       LAG([{self._value_col}]) OVER (
                           PARTITION BY [symbol], [series]
                           ORDER BY [ts]
                       ) AS prev_val
                FROM {table}
                WHERE [{self._value_col}] IS NOT NULL
                  {where}
            )
            SELECT [id], [ts], [symbol], [series], [{self._value_col}],
                   prev_val,
                   CASE WHEN prev_val IS NOT NULL AND prev_val != 0
                        THEN ([{self._value_col}] - prev_val) / ABS(prev_val) * 100.0
                   END AS pct_change
            FROM flagged
            WHERE ({filter_expr})
        """
        return reader.read_sql(sql, params)

    def build_update_sql(self, ids: list[int]) -> str:
        id_list = ", ".join(str(i) for i in ids)
        return f"UPDATE {TABLE} SET {_NULL_SET} WHERE [id] IN ({id_list})"

    def describe(self, row: pd.Series) -> str:
        sym = row["symbol"]
        lo, hi = self._ranges.get(sym, (None, None))
        pct = row.get("pct_change")
        pct_str = f" ({pct:+.1f}%)" if pd.notna(pct) else ""
        return (
            f"hard bound: {sym} {self._value_col}={row[self._value_col]}{pct_str} "
            f"outside [{lo}, {hi}] @ {row['ts']}"
        )


class RobustOutlierRule(CleaningRule):
    """NULL out rows that are outliers by median + MAD (trailing window)."""

    _MAD_SCALE = 1.4826

    def __init__(
        self,
        value_column: str = "close_px",
        group_columns: list[str] | None = None,
        n_mad: float = 4.0,
        trailing_months: int = 1,
        ts_column: str = "ts",
        min_obs: int = 100,
    ) -> None:
        self._value_col = value_column
        self._group_cols = group_columns or ["symbol", "series"]
        self._n_mad = n_mad
        self._trailing_months = trailing_months
        self._ts_col = ts_column
        self._min_obs = min_obs

    @property
    def name(self) -> str:
        return "robust_outlier"

    @property
    def action_label(self) -> str:
        return "null_prices"

    def detect(
        self,
        reader: AnalyticalReader,
        table: str = TABLE,
        where: str = "",
        params: dict[str, Any] | None = None,
    ) -> pd.DataFrame:
        group_list = ", ".join(f"[{c}]" for c in self._group_cols)

        sql = f"""
            SELECT [id], [{self._ts_col}] AS ts,
                   {', '.join(f'[{c}]' for c in self._group_cols)},
                   [{self._value_col}]
            FROM {table}
            WHERE [{self._value_col}] IS NOT NULL
              {where}
            ORDER BY {group_list}, [{self._ts_col}]
        """
        df = reader.read_sql(sql, params)
        if df.empty:
            return df

        df["ts"] = pd.to_datetime(df["ts"], utc=True)
        df = df.sort_values(self._group_cols + ["ts"])

        window = f"{self._trailing_months * 30}D"
        flagged: list[pd.DataFrame] = []

        for _key, grp in df.groupby(self._group_cols):
            grp = grp.set_index("ts").sort_index()
            vals = grp[self._value_col].astype(float)

            if len(vals) < self._min_obs:
                continue

            roll_median = vals.rolling(
                window, min_periods=self._min_obs,
            ).median()
            abs_dev = (vals - roll_median).abs()
            roll_mad = abs_dev.rolling(
                window, min_periods=self._min_obs,
            ).median()
            robust_sigma = roll_mad * self._MAD_SCALE

            robust_z = (vals - roll_median).abs() / robust_sigma.replace(0, float("nan"))
            mask = robust_z > self._n_mad

            if not mask.any():
                continue

            out = grp.loc[mask].copy()
            out["median_val"] = roll_median[mask]
            out["mad_val"] = roll_mad[mask]
            out["robust_z"] = robust_z[mask]
            flagged.append(out.reset_index())

        if not flagged:
            return pd.DataFrame()

        result = pd.concat(flagged, ignore_index=True)
        return result.sort_values("robust_z", ascending=False)

    def build_update_sql(self, ids: list[int]) -> str:
        id_list = ", ".join(str(i) for i in ids)
        return f"UPDATE {TABLE} SET {_NULL_SET} WHERE [id] IN ({id_list})"

    def describe(self, row: pd.Series) -> str:
        return (
            f"robust outlier: {row['symbol']} {row.get('series', '')} "
            f"{self._value_col}={row.get(self._value_col, '?')} "
            f"z={row.get('robust_z', '?'):.1f} @ {row['ts']}"
        )


class PercentageChangeRule(CleaningRule):
    """NULL out rows where close_px changed by more than threshold from previous bar."""

    def __init__(
        self,
        value_column: str = "close_px",
        threshold_pct: float = 5.0,
    ) -> None:
        self._value_col = value_column
        self._threshold = threshold_pct

    @property
    def name(self) -> str:
        return "pct_change"

    @property
    def action_label(self) -> str:
        return "null_prices"

    def detect(
        self,
        reader: AnalyticalReader,
        table: str = TABLE,
        where: str = "",
        params: dict[str, Any] | None = None,
    ) -> pd.DataFrame:
        sql = f"""
            WITH with_prev AS (
                SELECT [id], [ts], [symbol], [series], [{self._value_col}],
                       LAG([{self._value_col}]) OVER (
                           PARTITION BY [symbol], [series]
                           ORDER BY [ts]
                       ) AS prev_val
                FROM {table}
                WHERE [{self._value_col}] IS NOT NULL
                  {where}
            )
            SELECT [id], [ts], [symbol], [series],
                   [{self._value_col}], prev_val,
                   ([{self._value_col}] - prev_val)
                       / ABS(NULLIF(prev_val, 0)) * 100.0 AS pct_change
            FROM with_prev
            WHERE prev_val IS NOT NULL
              AND prev_val != 0
              AND ABS(([{self._value_col}] - prev_val)
                      / ABS(prev_val) * 100.0) > {self._threshold}
        """
        return reader.read_sql(sql, params)

    def build_update_sql(self, ids: list[int]) -> str:
        id_list = ", ".join(str(i) for i in ids)
        return f"UPDATE {TABLE} SET {_NULL_SET} WHERE [id] IN ({id_list})"

    def describe(self, row: pd.Series) -> str:
        pct = row.get("pct_change")
        pct_str = f" ({pct:+.1f}%)" if pd.notna(pct) else ""
        return (
            f"pct_change: {row['symbol']} {row['series']} "
            f"{self._value_col}={row[self._value_col]}{pct_str} "
            f"from prev={row.get('prev_val', '?')} @ {row['ts']}"
        )


class BidAskInversionRule(CleaningRule):
    """Swap bid and ask when bid > ask."""

    @property
    def name(self) -> str:
        return "bid_ask"

    @property
    def action_label(self) -> str:
        return "swap_bid_ask"

    def detect(
        self,
        reader: AnalyticalReader,
        table: str = TABLE,
        where: str = "",
        params: dict[str, Any] | None = None,
    ) -> pd.DataFrame:
        sql = f"""
            SELECT [id], [ts], [symbol], [series], [bid], [ask]
            FROM {table}
            WHERE [bid] > [ask]
              AND [bid] IS NOT NULL
              AND [ask] IS NOT NULL
              {where}
        """
        return reader.read_sql(sql, params)

    def build_update_sql(self, ids: list[int]) -> str:
        id_list = ", ".join(str(i) for i in ids)
        # MSSQL evaluates RHS before assignment, so this swap is correct.
        return (
            f"UPDATE t SET t.[bid] = t.[ask], t.[ask] = t.[bid] "
            f"FROM {TABLE} t WHERE t.[id] IN ({id_list})"
        )

    def describe(self, row: pd.Series) -> str:
        return (
            f"bid/ask inversion: {row['symbol']} bid={row['bid']} > ask={row['ask']} "
            f"@ {row['ts']}"
        )


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

class CleaningRunner:
    """Orchestrates cleaning rules with dry-run support."""

    def __init__(
        self,
        connector: MSSQLConnector,
        reader: AnalyticalReader,
        rules: list[CleaningRule],
        table: str = TABLE,
        dry_run: bool = True,
        batch_size: int = 500,
    ) -> None:
        self._connector = connector
        self._reader = reader
        self._rules = rules
        self._table = table
        self._dry_run = dry_run
        self._batch_size = batch_size

    def run(
        self,
        where: str = "",
        params: dict[str, Any] | None = None,
    ) -> list[CleaningResult]:
        results: list[CleaningResult] = []

        for rule in self._rules:
            log.info("cleaning_detect", rule=rule.name, dry_run=self._dry_run)
            detected = rule.detect(self._reader, self._table, where, params)

            result = CleaningResult(rule_name=rule.name, dry_run=self._dry_run)

            if detected.empty:
                log.info("cleaning_none", rule=rule.name)
                results.append(result)
                continue

            # Build actions
            for _, row in detected.iterrows():
                action = CleaningAction(
                    rule_name=rule.name,
                    row_id=int(row["id"]),
                    ts=row["ts"],
                    symbol=row["symbol"],
                    series=row["series"],
                    action=rule.action_label,
                    detail=rule.describe(row),
                )
                result.actions.append(action)

            log.info("cleaning_detected", rule=rule.name, rows=result.count)

            # Apply if not dry-run
            if not self._dry_run:
                all_ids = [a.row_id for a in result.actions]
                self._execute_batches(rule, all_ids)
                log.info("cleaning_applied", rule=rule.name, rows=result.count)

            results.append(result)

        return results

    def _execute_batches(self, rule: CleaningRule, ids: list[int]) -> None:
        """Execute UPDATE in batches within a single session."""
        with self._connector.session() as session:
            for i in range(0, len(ids), self._batch_size):
                batch = ids[i : i + self._batch_size]
                sql = rule.build_update_sql(batch)
                session.execute(text(sql))
