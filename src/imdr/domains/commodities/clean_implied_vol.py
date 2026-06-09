"""Commodity implied vol data cleaning rules.

Detects and corrects data quality issues in [commodities].[fact_implied_vol]:
  - Hard-bound violations → NULL vol
  - Robust outliers       → NULL vol
  - Percentage change     → NULL vol

Each rule is idempotent — safe to re-run.  Dry-run mode (default)
shows what would change without writing.
"""
from __future__ import annotations

import re
from typing import Any

import pandas as pd

from imdr.connectors.reader import AnalyticalReader
from imdr.healthchecks.cleaning import CleaningAction, CleaningRule

TABLE = "[commodities].[fact_implied_vol]"

_SAFE_IDENT_RE = re.compile(r"^[A-Za-z0-9_./-]+$")


def _assert_safe(value: str, label: str) -> None:
    if not isinstance(value, str) or not _SAFE_IDENT_RE.match(value):
        raise ValueError(f"Unsafe {label}: {value!r}")


def _product_label(row: pd.Series) -> str:
    s = row.get("symbol")
    if s:
        return str(s)
    return f"commodity_id={row['commodity_id']}"


# ---------------------------------------------------------------------------
# Rule implementations
# ---------------------------------------------------------------------------


class HardBoundViolationRule(CleaningRule):
    """NULL out rows where vol falls outside per-strike hard bounds."""

    def __init__(self, ranges: dict[str, tuple[float, float]]) -> None:
        for strike in ranges:
            _assert_safe(strike, "strike")
        self._ranges = ranges

    @property
    def name(self) -> str:
        return "hard_bound"

    @property
    def action_label(self) -> str:
        return "null_vol"

    def detect(
        self,
        reader: AnalyticalReader,
        table: str = TABLE,
        where: str = "",
        params: dict[str, Any] | None = None,
    ) -> pd.DataFrame:
        if not self._ranges:
            return pd.DataFrame()

        merged_params: dict[str, Any] = dict(params or {})
        when_clauses = []
        for i, (strike, (lo, hi)) in enumerate(self._ranges.items()):
            ks, klo, khi = f"hb_strike_{i}", f"hb_lo_{i}", f"hb_hi_{i}"
            when_clauses.append(
                f"(v.[strike] = :{ks} AND (v.[vol] < :{klo} OR v.[vol] > :{khi}))"
            )
            merged_params[ks] = strike
            merged_params[klo] = lo
            merged_params[khi] = hi
        filter_expr = " OR ".join(when_clauses)

        sql = f"""
            SELECT v.[id], v.[obs_date], v.[commodity_id], c.[symbol],
                   v.[strike], v.[tenor], v.[vol]
            FROM {table} v
            JOIN [commodities].[dim_commodity] c ON c.id = v.commodity_id
            WHERE ({filter_expr}) {where}
        """
        return reader.read_sql(sql, merged_params)

    def build_update_sql(self, ids: list[int]) -> str:
        id_list = ", ".join(str(int(i)) for i in ids)
        return (
            f"UPDATE {TABLE} SET [vol] = NULL, "
            f"[updated_at] = SYSDATETIMEOFFSET() "
            f"WHERE [id] IN ({id_list})"
        )

    def build_action(self, row: pd.Series) -> CleaningAction:
        return CleaningAction(
            rule_name=self.name,
            row_id=int(row["id"]),
            ts=row["obs_date"],
            action=self.action_label,
            detail=f"vol={row['vol']} outside [{self._ranges.get(row['strike'], ('?','?'))}] for strike={row['strike']}",
            context={"commodity_id": int(row["commodity_id"]), "strike": row["strike"], "tenor": row["tenor"]},
        )


class RobustOutlierRule(CleaningRule):
    """NULL out rows that are statistical outliers (MAD-based)."""

    def __init__(
        self,
        n_mad: float = 4.0,
        trailing_months: int = 12,
        min_obs: int = 30,
    ) -> None:
        self._n_mad = n_mad
        self._trailing_months = trailing_months
        self._min_obs = min_obs

    @property
    def name(self) -> str:
        return "robust_outlier"

    @property
    def action_label(self) -> str:
        return "null_vol"

    def detect(
        self,
        reader: AnalyticalReader,
        table: str = TABLE,
        where: str = "",
        params: dict[str, Any] | None = None,
    ) -> pd.DataFrame:
        sql = f"""
        WITH stats AS (
            SELECT [commodity_id], [strike], [tenor],
                   PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY [vol])
                       OVER (PARTITION BY [commodity_id], [strike], [tenor]) AS med,
                   COUNT(*) OVER (PARTITION BY [commodity_id], [strike], [tenor]) AS n
            FROM {table}
            WHERE [vol] IS NOT NULL
                  AND [obs_date] >= DATEADD(MONTH, -{self._trailing_months}, GETDATE())
                  {where}
        )
        SELECT v.[id], v.[obs_date], v.[commodity_id], c.[symbol],
               v.[strike], v.[tenor], v.[vol]
        FROM {table} v
        JOIN [commodities].[dim_commodity] c ON c.id = v.commodity_id
        JOIN (
            SELECT DISTINCT [commodity_id], [strike], [tenor], med, n
            FROM stats
            WHERE n >= {self._min_obs}
        ) s ON s.[commodity_id] = v.[commodity_id]
           AND s.[strike] = v.[strike] AND s.[tenor] = v.[tenor]
        WHERE ABS(v.[vol] - s.med) > {self._n_mad} * (
            SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY ABS(v2.[vol] - s.med))
            FROM {table} v2
            WHERE v2.[commodity_id] = v.[commodity_id]
              AND v2.[strike] = v.[strike] AND v2.[tenor] = v.[tenor]
              AND v2.[vol] IS NOT NULL
              AND v2.[obs_date] >= DATEADD(MONTH, -{self._trailing_months}, GETDATE())
        )
        {where}
        """
        return reader.read_sql(sql, params)

    def build_update_sql(self, ids: list[int]) -> str:
        id_list = ", ".join(str(int(i)) for i in ids)
        return (
            f"UPDATE {TABLE} SET [vol] = NULL, "
            f"[updated_at] = SYSDATETIMEOFFSET() "
            f"WHERE [id] IN ({id_list})"
        )

    def build_action(self, row: pd.Series) -> CleaningAction:
        return CleaningAction(
            rule_name=self.name,
            row_id=int(row["id"]),
            ts=row["obs_date"],
            action=self.action_label,
            detail=f"vol={row['vol']} is MAD outlier for {_product_label(row)} {row['strike']}/{row['tenor']}",
            context={"commodity_id": int(row["commodity_id"]), "strike": row["strike"], "tenor": row["tenor"]},
        )


class PercentageChangeRule(CleaningRule):
    """NULL out rows with extreme day-over-day vol changes."""

    def __init__(self, threshold_pct: float = 40.0, min_abs_value: float = 0.5) -> None:
        self._threshold_pct = threshold_pct
        self._min_abs_value = min_abs_value

    @property
    def name(self) -> str:
        return "pct_change"

    @property
    def action_label(self) -> str:
        return "null_vol"

    def detect(
        self,
        reader: AnalyticalReader,
        table: str = TABLE,
        where: str = "",
        params: dict[str, Any] | None = None,
    ) -> pd.DataFrame:
        sql = f"""
        WITH lagged AS (
            SELECT [id], [obs_date], [commodity_id], [strike], [tenor], [vol],
                   LAG([vol]) OVER (
                       PARTITION BY [commodity_id], [strike], [tenor]
                       ORDER BY [obs_date]
                   ) AS prev_vol
            FROM {table}
            WHERE [vol] IS NOT NULL {where}
        )
        SELECT l.[id], l.[obs_date], l.[commodity_id], c.[symbol],
               l.[strike], l.[tenor], l.[vol], l.prev_vol
        FROM lagged l
        JOIN [commodities].[dim_commodity] c ON c.id = l.commodity_id
        WHERE l.prev_vol IS NOT NULL
          AND ABS(l.prev_vol) >= {self._min_abs_value}
          AND ABS((l.[vol] - l.prev_vol) / l.prev_vol * 100.0) > {self._threshold_pct}
        """
        return reader.read_sql(sql, params)

    def build_update_sql(self, ids: list[int]) -> str:
        id_list = ", ".join(str(int(i)) for i in ids)
        return (
            f"UPDATE {TABLE} SET [vol] = NULL, "
            f"[updated_at] = SYSDATETIMEOFFSET() "
            f"WHERE [id] IN ({id_list})"
        )

    def build_action(self, row: pd.Series) -> CleaningAction:
        pct = abs((row["vol"] - row["prev_vol"]) / row["prev_vol"] * 100.0) if row["prev_vol"] else 0
        return CleaningAction(
            rule_name=self.name,
            row_id=int(row["id"]),
            ts=row["obs_date"],
            action=self.action_label,
            detail=f"vol={row['vol']} prev={row['prev_vol']} pct={pct:.1f}%",
            context={"commodity_id": int(row["commodity_id"]), "strike": row["strike"], "tenor": row["tenor"]},
        )
