"""Domain-agnostic data quality checks for analytical diagnostics.

Each check uses AnalyticalReader (raw SQL) for efficiency on large datasets.
Checks are configured at construction and work on any table with the right columns.

Usage:
    checks = [
        PositiveValueCheck(columns=["close_px", "bid", "ask"]),
        ColumnOrderCheck(rules=[("bid", "<=", "ask")]),
        SymbolRangeCheck(ranges={"EURUSD": (0.3, 3.0)}, value_column="close_px"),
    ]
    for check in checks:
        result = check.run(reader, "[fx].[fact_ohlc]", where="AND YEAR(ts) = 2024")
        print(result.message)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Callable

import pandas as pd
import structlog

from imdr.connectors.reader import AnalyticalReader
from imdr.healthchecks.base import CheckResult, CheckStatus

log = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Calendar-aware helpers
# ---------------------------------------------------------------------------

def should_relax_checks(run_date: date, market_code: str = "US") -> bool:
    """Return True if health checks should use relaxed thresholds.

    On non-trading days (weekends, holidays), row-count and freshness checks
    should expect no new data rather than flagging missing data as failures.
    Uses each country's project-wide default calendar (see
    ``imdr.market_calendar.countries.DEFAULT_CALENDAR_BY_COUNTRY``).
    """
    from imdr.market_calendar.calendar import is_trading_day
    from imdr.market_calendar.countries import default_calendar

    return not is_trading_day(market_code, default_calendar(market_code), run_date)


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------

@dataclass
class QualityResult:
    """Result from a quality check — richer than CheckResult with DataFrames."""

    check_name: str
    status: CheckStatus
    category: str  # invariant, range, statistical, coverage, basis
    message: str
    summary: pd.DataFrame | None = None
    flagged: pd.DataFrame | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def to_check_result(self) -> CheckResult:
        """Convert to CheckResult for compatibility with HealthCheckRunner."""
        return CheckResult(
            check_name=self.check_name,
            status=self.status,
            message=self.message,
            details=self.meta or None,
        )


# ---------------------------------------------------------------------------
# ABC
# ---------------------------------------------------------------------------

class QualityCheck(ABC):
    """Base class for analytical quality checks.

    Subclass this for both generic checks (in this module) and
    domain-specific checks (in domain modules).
    """

    @abstractmethod
    def run(
        self,
        reader: AnalyticalReader,
        table: str,
        where: str = "",
        params: dict[str, Any] | None = None,
    ) -> QualityResult:
        """Execute the check and return a QualityResult.

        Args:
            reader: AnalyticalReader for SQL execution.
            table: Fully qualified table name, e.g. "[fx].[fact_ohlc]".
            where: Additional WHERE clause fragment, e.g. "AND YEAR(ts) = 2024".
            params: Named bind parameters for the WHERE clause.
        """
        ...


# ---------------------------------------------------------------------------
# Generic checks
# ---------------------------------------------------------------------------

class PositiveValueCheck(QualityCheck):
    """Flag rows where any specified column has a non-positive value."""

    def __init__(self, columns: list[str], symbol_column: str = "symbol") -> None:
        self._columns = columns
        self._symbol_col = symbol_column

    def run(self, reader: AnalyticalReader, table: str,
            where: str = "", params: dict[str, Any] | None = None) -> QualityResult:
        cases = ", ".join(
            f"SUM(CASE WHEN [{c}] <= 0 THEN 1 ELSE 0 END) AS [{c}]"
            for c in self._columns
        )
        sql = f"""
            SELECT [{self._symbol_col}], {cases}, COUNT(*) AS total_rows
            FROM {table}
            WHERE 1=1 {where}
            GROUP BY [{self._symbol_col}]
        """
        df = reader.read_sql(sql, params)

        # Find symbols with violations
        violation_cols = [c for c in self._columns if df[c].sum() > 0]
        total_violations = sum(int(df[c].sum()) for c in violation_cols)

        if total_violations == 0:
            return QualityResult(
                check_name="positive_values",
                status=CheckStatus.PASSED,
                category="invariant",
                message=f"All {len(self._columns)} columns positive across all symbols",
                summary=None,
            )

        # Filter to only symbols with violations
        mask = df[violation_cols].sum(axis=1) > 0
        summary = df[mask][[self._symbol_col] + violation_cols + ["total_rows"]]

        return QualityResult(
            check_name="positive_values",
            status=CheckStatus.WARNING,
            category="invariant",
            message=f"{total_violations} non-positive values in columns: {', '.join(violation_cols)}",
            summary=summary,
            meta={"violation_columns": violation_cols, "total_violations": total_violations},
        )


class ColumnOrderCheck(QualityCheck):
    """Flag rows where column relationships are violated.

    Rules are tuples like ("bid", "<=", "ask") meaning bid should be <= ask.
    """

    def __init__(self, rules: list[tuple[str, str, str]],
                 symbol_column: str = "symbol") -> None:
        self._rules = rules
        self._symbol_col = symbol_column

    def run(self, reader: AnalyticalReader, table: str,
            where: str = "", params: dict[str, Any] | None = None) -> QualityResult:
        cases = []
        labels = []
        for left, op, right in self._rules:
            label = f"{left}_{op}_{right}".replace(" ", "")
            # Invert the operator to find violations
            inv = {"<=": ">", ">=": "<", "<": ">=", ">": "<="}[op]
            cases.append(
                f"SUM(CASE WHEN [{left}] {inv} [{right}] THEN 1 ELSE 0 END) AS [{label}]"
            )
            labels.append(label)

        cases_sql = ", ".join(cases)
        sql = f"""
            SELECT [{self._symbol_col}], {cases_sql}, COUNT(*) AS total_rows
            FROM {table}
            WHERE 1=1 {where}
            GROUP BY [{self._symbol_col}]
        """
        df = reader.read_sql(sql, params)

        violation_labels = [lb for lb in labels if df[lb].sum() > 0]
        total = sum(int(df[lb].sum()) for lb in violation_labels)

        if total == 0:
            rules_desc = ", ".join(f"{l} {o} {r}" for l, o, r in self._rules)
            return QualityResult(
                check_name="column_order",
                status=CheckStatus.PASSED,
                category="invariant",
                message=f"All column relationships hold: {rules_desc}",
            )

        mask = df[violation_labels].sum(axis=1) > 0
        summary = df[mask][[self._symbol_col] + violation_labels + ["total_rows"]]
        violated_rules = [
            f"{l} {o} {r}" for (l, o, r), lb in zip(self._rules, labels) if lb in violation_labels
        ]

        return QualityResult(
            check_name="column_order",
            status=CheckStatus.WARNING,
            category="invariant",
            message=f"{total} violations in: {', '.join(violated_rules)}",
            summary=summary,
            meta={"violated_rules": violated_rules, "total_violations": total},
        )


class SymbolRangeCheck(QualityCheck):
    """Flag rows outside per-symbol hard bounds.

    Args:
        ranges: Dict mapping symbol to (min, max) tuples.
        value_column: Column to check.
        symbol_column: Column containing the symbol identifier.
    """

    def __init__(self, ranges: dict[str, tuple[float, float]],
                 value_column: str, symbol_column: str = "symbol") -> None:
        self._ranges = ranges
        self._value_col = value_column
        self._symbol_col = symbol_column

    def run(self, reader: AnalyticalReader, table: str,
            where: str = "", params: dict[str, Any] | None = None) -> QualityResult:
        if not self._ranges:
            return QualityResult(
                check_name="symbol_range",
                status=CheckStatus.PASSED,
                category="range",
                message="No expected ranges configured — skipped",
            )

        # Build dynamic CASE expression from config
        when_clauses = []
        for sym, (lo, hi) in self._ranges.items():
            when_clauses.append(
                f"WHEN [{self._symbol_col}] = '{sym}' "
                f"AND ([{self._value_col}] < {lo} OR [{self._value_col}] > {hi}) THEN 1"
            )
        case_expr = "CASE " + " ".join(when_clauses) + " ELSE 0 END"

        sql = f"""
            SELECT [{self._symbol_col}],
                   SUM({case_expr}) AS range_violations,
                   MIN([{self._value_col}]) AS min_val,
                   MAX([{self._value_col}]) AS max_val,
                   COUNT(*) AS total_rows
            FROM {table}
            WHERE 1=1 {where}
            GROUP BY [{self._symbol_col}]
            HAVING SUM({case_expr}) > 0
        """
        df = reader.read_sql(sql, params)

        if df.empty:
            return QualityResult(
                check_name="symbol_range",
                status=CheckStatus.PASSED,
                category="range",
                message=f"All {len(self._ranges)} symbols within expected ranges for {self._value_col}",
            )

        total = int(df["range_violations"].sum())

        # Fetch detail rows for violating symbols
        flagged = None
        violating_syms = df[self._symbol_col].tolist()
        if violating_syms:
            sym_list = ", ".join(f"'{s}'" for s in violating_syms[:5])
            detail_whens = []
            for sym, (lo, hi) in self._ranges.items():
                if sym in violating_syms:
                    detail_whens.append(
                        f"([{self._symbol_col}] = '{sym}' "
                        f"AND ([{self._value_col}] < {lo} OR [{self._value_col}] > {hi}))"
                    )
            if detail_whens:
                detail_filter = " OR ".join(detail_whens)
                detail_sql = f"""
                    SELECT TOP 20 ts, [{self._symbol_col}], [{self._value_col}]
                    FROM {table}
                    WHERE ({detail_filter}) {where}
                    ORDER BY ts
                """
                flagged = reader.read_sql(detail_sql, params)

        return QualityResult(
            check_name="symbol_range",
            status=CheckStatus.WARNING,
            category="range",
            message=f"{total} rows outside expected ranges across {len(df)} symbols",
            summary=df,
            flagged=flagged,
            meta={"total_violations": total, "violating_symbols": violating_syms},
        )


class CompositeRangeCheck(QualityCheck):
    """Flag rows outside hard bounds defined by a composite key.

    Generic check for tables where the valid range depends on multiple columns.
    Example: FX vol where (strike=ATM, vol_type=IMPLIED) → (0.5, 80.0)
             but (strike=25RR, vol_type=IMPLIED) → (-20.0, 20.0)

    Args:
        range_map: Dict mapping composite key tuples to (min, max).
        key_columns: Columns forming the composite key (e.g. ["strike", "vol_type"]).
        value_column: Column to check (e.g. "value").
    """

    def __init__(
        self,
        range_map: dict[tuple[str, ...], tuple[float, float]],
        key_columns: list[str],
        value_column: str,
    ) -> None:
        self._range_map = range_map
        self._key_cols = key_columns
        self._value_col = value_column

    def run(
        self,
        reader: AnalyticalReader,
        table: str,
        where: str = "",
        params: dict[str, Any] | None = None,
    ) -> QualityResult:
        if not self._range_map:
            return QualityResult(
                check_name="composite_range",
                status=CheckStatus.PASSED,
                category="range",
                message="No composite ranges configured — skipped",
            )

        # Build dynamic CASE expression from composite keys
        when_clauses = []
        for keys, (lo, hi) in self._range_map.items():
            conditions = " AND ".join(
                f"[{col}] = '{val}'" for col, val in zip(self._key_cols, keys)
            )
            when_clauses.append(
                f"WHEN {conditions} "
                f"AND ([{self._value_col}] < {lo} OR [{self._value_col}] > {hi}) THEN 1"
            )
        case_expr = "CASE " + " ".join(when_clauses) + " ELSE 0 END"
        group_cols = ", ".join(f"[{c}]" for c in self._key_cols)

        sql = f"""
            SELECT {group_cols},
                   SUM({case_expr}) AS range_violations,
                   MIN([{self._value_col}]) AS min_val,
                   MAX([{self._value_col}]) AS max_val,
                   COUNT(*) AS total_rows
            FROM {table}
            WHERE 1=1 {where}
            GROUP BY {group_cols}
            HAVING SUM({case_expr}) > 0
        """
        df = reader.read_sql(sql, params)

        if df.empty:
            return QualityResult(
                check_name="composite_range",
                status=CheckStatus.PASSED,
                category="range",
                message=(
                    f"All {len(self._range_map)} composite keys within expected "
                    f"ranges for {self._value_col}"
                ),
            )

        total = int(df["range_violations"].sum())

        # Fetch detail rows for violating groups
        flagged = None
        detail_whens = []
        for keys, (lo, hi) in self._range_map.items():
            conditions = " AND ".join(
                f"[{col}] = '{val}'" for col, val in zip(self._key_cols, keys)
            )
            # Check if this key combo has violations in summary
            match_mask = True
            for col, val in zip(self._key_cols, keys):
                match_mask = match_mask & (df[col] == val)
            if df[match_mask].any(axis=None):
                detail_whens.append(
                    f"({conditions} "
                    f"AND ([{self._value_col}] < {lo} OR [{self._value_col}] > {hi}))"
                )

        if detail_whens:
            detail_filter = " OR ".join(detail_whens[:10])  # limit to 10 combos
            detail_cols = ", ".join(f"[{c}]" for c in self._key_cols)
            detail_sql = f"""
                SELECT TOP 20 {detail_cols}, [{self._value_col}]
                FROM {table}
                WHERE ({detail_filter}) {where}
            """
            flagged = reader.read_sql(detail_sql, params)

        violating_keys = [
            tuple(row[c] for c in self._key_cols) for _, row in df.iterrows()
        ]
        return QualityResult(
            check_name="composite_range",
            status=CheckStatus.WARNING,
            category="range",
            message=(
                f"{total} rows outside expected ranges across "
                f"{len(df)} composite key groups"
            ),
            summary=df,
            flagged=flagged,
            meta={"total_violations": total, "violating_keys": violating_keys},
        )


class DistributionCheck(QualityCheck):
    """Compute per-group distribution stats: mean, std, min, max, percentiles.

    Returns INFO status — this is informational, not pass/fail.
    """

    def __init__(self, value_column: str, group_column: str,
                 percentiles: list[float] | None = None,
                 series_filter: str | None = None) -> None:
        self._value_col = value_column
        self._group_col = group_column
        self._percentiles = percentiles or [0.01, 0.99]
        self._series_filter = series_filter

    def run(self, reader: AnalyticalReader, table: str,
            where: str = "", params: dict[str, Any] | None = None) -> QualityResult:
        series_clause = ""
        if self._series_filter:
            series_clause = f"AND [series] = '{self._series_filter}'"

        # Stats query
        stats_sql = f"""
            SELECT [{self._group_col}],
                   COUNT(*) AS n,
                   AVG(CAST([{self._value_col}] AS FLOAT)) AS mean_px,
                   STDEV(CAST([{self._value_col}] AS FLOAT)) AS std_px,
                   MIN([{self._value_col}]) AS min_px,
                   MAX([{self._value_col}]) AS max_px
            FROM {table}
            WHERE 1=1 {where} {series_clause}
            GROUP BY [{self._group_col}]
            ORDER BY [{self._group_col}]
        """
        df_stats = reader.read_sql(stats_sql, params)

        # Percentiles query (MSSQL window function syntax)
        pctls = []
        pctl_labels = []
        for p in self._percentiles:
            label = f"p{int(p * 100):02d}"
            pctls.append(
                f"PERCENTILE_CONT({p}) WITHIN GROUP (ORDER BY [{self._value_col}]) "
                f"OVER (PARTITION BY [{self._group_col}]) AS [{label}]"
            )
            pctl_labels.append(label)

        pctl_sql = f"""
            SELECT DISTINCT [{self._group_col}], {', '.join(pctls)}
            FROM {table}
            WHERE 1=1 {where} {series_clause}
        """
        df_pctl = reader.read_sql(pctl_sql, params)

        # Merge
        summary = df_stats.merge(df_pctl, on=self._group_col, how="left")

        series_note = f" ({self._series_filter})" if self._series_filter else ""
        return QualityResult(
            check_name="distribution",
            status=CheckStatus.PASSED,
            category="statistical",
            message=f"Distribution summary for {self._value_col}{series_note} across {len(summary)} groups",
            summary=summary,
        )


class ReturnDistributionCheck(QualityCheck):
    """Compute per-group hourly return distribution using LAG()."""

    def __init__(self, value_column: str, group_column: str,
                 ts_column: str = "ts",
                 series_filter: str | None = None) -> None:
        self._value_col = value_column
        self._group_col = group_column
        self._ts_col = ts_column
        self._series_filter = series_filter

    def run(self, reader: AnalyticalReader, table: str,
            where: str = "", params: dict[str, Any] | None = None) -> QualityResult:
        series_clause = ""
        if self._series_filter:
            series_clause = f"AND [series] = '{self._series_filter}'"

        sql = f"""
            WITH returns AS (
                SELECT [{self._group_col}],
                    (CAST([{self._value_col}] AS FLOAT)
                     - CAST(LAG([{self._value_col}]) OVER (
                           PARTITION BY [{self._group_col}] ORDER BY [{self._ts_col}]) AS FLOAT))
                    / NULLIF(CAST(LAG([{self._value_col}]) OVER (
                           PARTITION BY [{self._group_col}] ORDER BY [{self._ts_col}]) AS FLOAT), 0)
                    * 100 AS pct_return
                FROM {table}
                WHERE 1=1 {where} {series_clause}
            )
            SELECT [{self._group_col}],
                   COUNT(pct_return) AS n_returns,
                   AVG(pct_return) AS mean_ret_pct,
                   STDEV(pct_return) AS std_ret_pct,
                   MIN(pct_return) AS min_ret_pct,
                   MAX(pct_return) AS max_ret_pct
            FROM returns
            WHERE pct_return IS NOT NULL
            GROUP BY [{self._group_col}]
            ORDER BY [{self._group_col}]
        """
        summary = reader.read_sql(sql, params)

        series_note = f" ({self._series_filter})" if self._series_filter else ""
        return QualityResult(
            check_name="return_distribution",
            status=CheckStatus.PASSED,
            category="statistical",
            message=f"Hourly return distribution for {self._value_col}{series_note} across {len(summary)} groups",
            summary=summary,
        )


class StatisticalOutlierCheck(QualityCheck):
    """Flag values beyond mean +/- N sigma per group."""

    def __init__(self, value_column: str, group_column: str,
                 n_sigma: float = 4.0,
                 series_filter: str | None = None,
                 max_rows: int = 50) -> None:
        self._value_col = value_column
        self._group_col = group_column
        self._n_sigma = n_sigma
        self._series_filter = series_filter
        self._max_rows = max_rows

    def run(self, reader: AnalyticalReader, table: str,
            where: str = "", params: dict[str, Any] | None = None) -> QualityResult:
        series_clause = ""
        if self._series_filter:
            series_clause = f"AND [series] = '{self._series_filter}'"

        params = dict(params) if params else {}
        params["n_sigma"] = self._n_sigma

        sql = f"""
            WITH stats AS (
                SELECT [{self._group_col}],
                       AVG(CAST([{self._value_col}] AS FLOAT)) AS mu,
                       STDEV(CAST([{self._value_col}] AS FLOAT)) AS sigma
                FROM {table}
                WHERE 1=1 {where} {series_clause}
                GROUP BY [{self._group_col}]
            )
            SELECT TOP {self._max_rows}
                   f.[ts], f.[{self._group_col}], f.[series],
                   f.[{self._value_col}],
                   s.mu, s.sigma,
                   ABS(CAST(f.[{self._value_col}] AS FLOAT) - s.mu)
                       / NULLIF(s.sigma, 0) AS z_score
            FROM {table} f
            JOIN stats s ON f.[{self._group_col}] = s.[{self._group_col}]
            WHERE 1=1 {where} {series_clause}
              AND s.sigma > 0
              AND ABS(CAST(f.[{self._value_col}] AS FLOAT) - s.mu) / s.sigma > :n_sigma
            ORDER BY z_score DESC
        """
        flagged = reader.read_sql(sql, params)

        if flagged.empty:
            return QualityResult(
                check_name="statistical_outliers",
                status=CheckStatus.PASSED,
                category="statistical",
                message=f"No outliers beyond {self._n_sigma}σ for {self._value_col}",
            )

        return QualityResult(
            check_name="statistical_outliers",
            status=CheckStatus.WARNING,
            category="statistical",
            message=f"{len(flagged)} outliers beyond {self._n_sigma}σ for {self._value_col}",
            flagged=flagged,
            meta={"n_sigma": self._n_sigma, "outlier_count": len(flagged)},
        )


class RobustStatisticalOutlierCheck(QualityCheck):
    """Flag values beyond median +/- N * MAD per group using robust statistics.

    Uses median and MAD (median absolute deviation) instead of mean/std,
    making it resistant to outlier contamination.  Stats are computed over
    a trailing window but applied to the full dataset.

    Args:
        value_column: Column to check (e.g. "close_px").
        group_columns: Columns to partition by (default: symbol + series).
        n_mad: Number of scaled-MAD units for the threshold (default 4.0).
        trailing_months: Trailing window in months for computing stats.
        ts_column: Timestamp column name.
        min_obs: Minimum observations per group to compute stats.
        max_rows: Maximum flagged rows to return.
    """

    _MAD_SCALE = 1.4826  # scale factor: MAD * 1.4826 ≈ σ for normal data

    def __init__(
        self,
        value_column: str,
        group_columns: list[str] | None = None,
        n_mad: float = 4.0,
        trailing_months: int = 12,
        ts_column: str = "ts",
        min_obs: int = 100,
        max_rows: int = 50,
    ) -> None:
        self._value_col = value_column
        self._group_cols = group_columns or ["symbol", "series"]
        self._n_mad = n_mad
        self._trailing_months = trailing_months
        self._ts_col = ts_column
        self._min_obs = min_obs
        self._max_rows = max_rows

    def run(
        self,
        reader: AnalyticalReader,
        table: str,
        where: str = "",
        params: dict[str, Any] | None = None,
    ) -> QualityResult:
        params = dict(params) if params else {}

        group_list = ", ".join(f"[{c}]" for c in self._group_cols)
        partition = f"PARTITION BY {group_list}"

        sql = f"""
            WITH max_ts AS (
                SELECT MAX([{self._ts_col}]) AS mt FROM {table} WHERE 1=1 {where}
            ),
            trailing AS (
                SELECT {group_list}, [{self._value_col}]
                FROM {table}, max_ts
                WHERE [{self._ts_col}] >= DATEADD(MONTH, -{self._trailing_months}, max_ts.mt)
                  AND [{self._value_col}] IS NOT NULL
                  {where}
            ),
            grp_counts AS (
                SELECT {group_list}, COUNT(*) AS n
                FROM trailing
                GROUP BY {group_list}
                HAVING COUNT(*) >= {self._min_obs}
            ),
            medians AS (
                SELECT DISTINCT {group_list},
                       PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY [{self._value_col}])
                           OVER ({partition}) AS median_val
                FROM trailing
            ),
            abs_devs AS (
                SELECT t.{group_list.replace(', ', ', t.')},
                       ABS(CAST(t.[{self._value_col}] AS FLOAT) - m.median_val) AS abs_dev
                FROM trailing t
                JOIN medians m ON {' AND '.join(
                    f't.[{c}] = m.[{c}]' for c in self._group_cols
                )}
            ),
            mad_stats AS (
                SELECT DISTINCT {group_list},
                       PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY abs_dev)
                           OVER ({partition}) AS mad_val
                FROM abs_devs
            ),
            robust AS (
                SELECT m.{group_list.replace(', ', ', m.')},
                       m.median_val,
                       d.mad_val,
                       d.mad_val * {self._MAD_SCALE} AS robust_sigma
                FROM medians m
                JOIN mad_stats d ON {' AND '.join(
                    f'm.[{c}] = d.[{c}]' for c in self._group_cols
                )}
                JOIN grp_counts g ON {' AND '.join(
                    f'm.[{c}] = g.[{c}]' for c in self._group_cols
                )}
            )
            SELECT TOP {self._max_rows}
                   f.[{self._ts_col}],
                   {', '.join(f'f.[{c}]' for c in self._group_cols)},
                   f.[{self._value_col}],
                   r.median_val,
                   r.mad_val,
                   ABS(CAST(f.[{self._value_col}] AS FLOAT) - r.median_val)
                       / NULLIF(r.robust_sigma, 0) AS robust_z
            FROM {table} f
            JOIN robust r ON {' AND '.join(
                f'f.[{c}] = r.[{c}]' for c in self._group_cols
            )}
            WHERE f.[{self._value_col}] IS NOT NULL
              {where}
              AND r.robust_sigma > 0
              AND ABS(CAST(f.[{self._value_col}] AS FLOAT) - r.median_val)
                  / r.robust_sigma > {self._n_mad}
            ORDER BY robust_z DESC
        """
        flagged = reader.read_sql(sql, params)

        if flagged.empty:
            return QualityResult(
                check_name="robust_outliers",
                status=CheckStatus.PASSED,
                category="statistical",
                message=(
                    f"No outliers beyond {self._n_mad} MAD "
                    f"({self._trailing_months}mo window) for {self._value_col}"
                ),
            )

        return QualityResult(
            check_name="robust_outliers",
            status=CheckStatus.WARNING,
            category="statistical",
            message=(
                f"{len(flagged)} outliers beyond {self._n_mad} MAD "
                f"({self._trailing_months}mo window) for {self._value_col}"
            ),
            flagged=flagged,
            meta={
                "n_mad": self._n_mad,
                "trailing_months": self._trailing_months,
                "outlier_count": len(flagged),
            },
        )


class PercentageChangeCheck(QualityCheck):
    """Flag rows where the value changed by more than threshold_pct from the previous bar.

    Uses LAG() partitioned by group columns ordered by timestamp.
    Default partition: (symbol, series). Override with group_columns for
    domains that partition differently (e.g. vol: pair_id, strike, tenor).

    Args:
        min_abs_value: Minimum ``ABS(prev_val)`` to apply percentage check.
            Rows where the previous value is smaller than this are skipped,
            avoiding misleading percentages on near-zero denominators
            (e.g. risk reversals that cross zero).  Default 0.0 (no filter).
    """

    def __init__(
        self,
        value_column: str = "close_px",
        symbol_column: str = "symbol",
        series_column: str = "series",
        ts_column: str = "ts",
        threshold_pct: float = 5.0,
        max_rows: int = 50,
        group_columns: list[str] | None = None,
        min_abs_value: float = 0.0,
    ) -> None:
        self._value_col = value_column
        self._symbol_col = symbol_column
        self._series_col = series_column
        self._ts_col = ts_column
        self._threshold = threshold_pct
        self._max_rows = max_rows
        self._group_cols = group_columns or [symbol_column, series_column]
        self._min_abs_value = min_abs_value

    def run(self, reader: AnalyticalReader, table: str,
            where: str = "", params: dict[str, Any] | None = None) -> QualityResult:
        partition = ", ".join(f"[{c}]" for c in self._group_cols)
        select_cols = ", ".join(f"[{c}]" for c in self._group_cols)
        min_abs_filter = (
            f"AND ABS(prev_val) >= {self._min_abs_value}"
            if self._min_abs_value > 0 else ""
        )
        sql = f"""
            WITH with_prev AS (
                SELECT [{self._ts_col}], {select_cols},
                       [{self._value_col}],
                       LAG([{self._value_col}]) OVER (
                           PARTITION BY {partition}
                           ORDER BY [{self._ts_col}]
                       ) AS prev_val
                FROM {table}
                WHERE [{self._value_col}] IS NOT NULL
                  {where}
            )
            SELECT TOP {self._max_rows}
                   [{self._ts_col}], {select_cols},
                   [{self._value_col}], prev_val,
                   ([{self._value_col}] - prev_val) / ABS(NULLIF(prev_val, 0)) * 100.0
                       AS pct_change
            FROM with_prev
            WHERE prev_val IS NOT NULL
              AND prev_val != 0
              {min_abs_filter}
              AND ABS(([{self._value_col}] - prev_val) / ABS(prev_val) * 100.0)
                  > {self._threshold}
            ORDER BY ABS(([{self._value_col}] - prev_val) / ABS(prev_val) * 100.0) DESC
        """
        flagged = reader.read_sql(sql, params)

        if flagged.empty:
            return QualityResult(
                check_name="pct_change",
                status=CheckStatus.PASSED,
                category="statistical",
                message=f"No bars with >{self._threshold}% change from previous bar",
            )

        return QualityResult(
            check_name="pct_change",
            status=CheckStatus.WARNING,
            category="statistical",
            message=f"{len(flagged)} bars with >{self._threshold}% change from previous bar",
            flagged=flagged,
            meta={"threshold_pct": self._threshold, "flagged_count": len(flagged)},
        )


class SeriesBasisCheck(QualityCheck):
    """Compare a base series against comparison series for the same symbol/timestamp.

    Flags rows where the basis (percentage deviation) exceeds a threshold.
    """

    def __init__(
        self,
        base_series: str,
        compare_series: list[str],
        value_column: str,
        symbol_column: str = "symbol",
        series_column: str = "series",
        ts_column: str = "ts",
        threshold_pct: float = 5.0,
        max_rows: int = 50,
    ) -> None:
        self._base = base_series
        self._compare = compare_series
        self._value_col = value_column
        self._symbol_col = symbol_column
        self._series_col = series_column
        self._ts_col = ts_column
        self._threshold = threshold_pct
        self._max_rows = max_rows

    def run(self, reader: AnalyticalReader, table: str,
            where: str = "", params: dict[str, Any] | None = None) -> QualityResult:
        compare_list = ", ".join(f"'{s}'" for s in self._compare)

        params = dict(params) if params else {}
        params["basis_threshold"] = self._threshold

        sql = f"""
            WITH spot AS (
                SELECT [{self._ts_col}], [{self._symbol_col}],
                       [{self._value_col}] AS base_px
                FROM {table}
                WHERE [{self._series_col}] = '{self._base}' {where}
            ),
            fwd AS (
                SELECT [{self._ts_col}], [{self._symbol_col}],
                       [{self._series_col}] AS fwd_series,
                       [{self._value_col}] AS fwd_px
                FROM {table}
                WHERE [{self._series_col}] IN ({compare_list}) {where}
            )
            SELECT TOP {self._max_rows}
                   f.[{self._ts_col}], f.[{self._symbol_col}], f.fwd_series,
                   s.base_px, f.fwd_px,
                   (CAST(f.fwd_px AS FLOAT) - CAST(s.base_px AS FLOAT))
                       / NULLIF(CAST(s.base_px AS FLOAT), 0) * 100 AS basis_pct
            FROM fwd f
            JOIN spot s ON f.[{self._ts_col}] = s.[{self._ts_col}]
                       AND f.[{self._symbol_col}] = s.[{self._symbol_col}]
            WHERE ABS(
                (CAST(f.fwd_px AS FLOAT) - CAST(s.base_px AS FLOAT))
                / NULLIF(CAST(s.base_px AS FLOAT), 0) * 100
            ) > :basis_threshold
            ORDER BY ABS(
                (CAST(f.fwd_px AS FLOAT) - CAST(s.base_px AS FLOAT))
                / NULLIF(CAST(s.base_px AS FLOAT), 0) * 100
            ) DESC
        """
        flagged = reader.read_sql(sql, params)

        compare_desc = ", ".join(self._compare)
        if flagged.empty:
            return QualityResult(
                check_name="series_basis",
                status=CheckStatus.PASSED,
                category="basis",
                message=f"All {compare_desc} within {self._threshold}% of {self._base}",
            )

        return QualityResult(
            check_name="series_basis",
            status=CheckStatus.WARNING,
            category="basis",
            message=f"{len(flagged)} rows where {compare_desc} deviates >{self._threshold}% from {self._base}",
            flagged=flagged,
            meta={"threshold_pct": self._threshold, "outlier_count": len(flagged)},
        )


# ---------------------------------------------------------------------------
# Coverage analyzer
# ---------------------------------------------------------------------------

class CoverageAnalyzer:
    """Market-hours-aware coverage analysis.

    Generic — works with any table that has a timestamp and symbol column,
    plus a callable that determines whether the market is open.
    """

    def __init__(
        self,
        ts_column: str,
        symbol_column: str,
        is_market_open: Callable[[datetime], bool],
    ) -> None:
        self._ts_col = ts_column
        self._symbol_col = symbol_column
        self._is_open = is_market_open

    def _count_market_hours(self, start: datetime, end: datetime) -> int:
        """Count market-open hours between start and end (inclusive)."""
        count = 0
        current = start.replace(minute=0, second=0, microsecond=0)
        end_hour = end.replace(minute=0, second=0, microsecond=0)
        while current <= end_hour:
            if self._is_open(current):
                count += 1
            current += timedelta(hours=1)
        return count

    def coverage(
        self,
        reader: AnalyticalReader,
        table: str,
        where: str = "",
        params: dict[str, Any] | None = None,
    ) -> pd.DataFrame:
        """Per-symbol coverage: actual hours vs expected market hours."""
        sql = f"""
            SELECT [{self._symbol_col}],
                   MIN([{self._ts_col}]) AS first_ts,
                   MAX([{self._ts_col}]) AS last_ts,
                   COUNT(DISTINCT [{self._ts_col}]) AS actual_hours
            FROM {table}
            WHERE 1=1 {where}
            GROUP BY [{self._symbol_col}]
            ORDER BY [{self._symbol_col}]
        """
        df = reader.read_sql(sql, params)
        if df.empty:
            return df

        expected_list = []
        for _, row in df.iterrows():
            first = pd.Timestamp(row["first_ts"]).to_pydatetime()
            last = pd.Timestamp(row["last_ts"]).to_pydatetime()
            # Strip timezone for is_market_open (expects naive UTC)
            if first.tzinfo is not None:
                first = first.replace(tzinfo=None)
            if last.tzinfo is not None:
                last = last.replace(tzinfo=None)
            expected_list.append(self._count_market_hours(first, last))

        df["expected_hours"] = expected_list
        df["missing_hours"] = df["expected_hours"] - df["actual_hours"]
        df["coverage_pct"] = (
            df["actual_hours"] / df["expected_hours"].replace(0, 1) * 100
        ).round(2)

        return df.sort_values("coverage_pct")

    def gaps(
        self,
        reader: AnalyticalReader,
        table: str,
        where: str = "",
        params: dict[str, Any] | None = None,
        min_market_gap: int = 2,
        top_n: int = 20,
    ) -> pd.DataFrame:
        """Find largest gaps in market hours (excluding weekends)."""
        sql = f"""
            WITH ts_with_next AS (
                SELECT [{self._symbol_col}], [series], [{self._ts_col}],
                       LEAD([{self._ts_col}]) OVER (
                           PARTITION BY [{self._symbol_col}], [series]
                           ORDER BY [{self._ts_col}]) AS next_ts
                FROM (
                    SELECT DISTINCT [{self._symbol_col}], [series], [{self._ts_col}]
                    FROM {table}
                    WHERE 1=1 {where}
                ) d
            )
            SELECT TOP 200
                   [{self._symbol_col}], [series],
                   [{self._ts_col}] AS gap_start,
                   next_ts AS gap_end,
                   DATEDIFF(HOUR, [{self._ts_col}], next_ts) AS calendar_gap_hours
            FROM ts_with_next
            WHERE next_ts IS NOT NULL
              AND DATEDIFF(HOUR, [{self._ts_col}], next_ts) > 1
            ORDER BY DATEDIFF(HOUR, [{self._ts_col}], next_ts) DESC
        """
        df = reader.read_sql(sql, params)
        if df.empty:
            return df

        # Compute market-hours gap for each row
        market_gaps = []
        for _, row in df.iterrows():
            start = pd.Timestamp(row["gap_start"]).to_pydatetime()
            end = pd.Timestamp(row["gap_end"]).to_pydatetime()
            if start.tzinfo is not None:
                start = start.replace(tzinfo=None)
            if end.tzinfo is not None:
                end = end.replace(tzinfo=None)
            # Count market hours in the gap (exclusive of start, inclusive of end - 1h)
            # The gap_start has data; first missing hour is gap_start + 1h
            gap_start = start + timedelta(hours=1)
            gap_end = end - timedelta(hours=1)
            if gap_start > gap_end:
                market_gaps.append(0)
            else:
                market_gaps.append(self._count_market_hours(gap_start, gap_end))

        df["market_gap_hours"] = market_gaps

        # Filter out pure weekend gaps and sort by market hours
        df = df[df["market_gap_hours"] >= min_market_gap]
        df = df.sort_values("market_gap_hours", ascending=False).head(top_n)

        return df.reset_index(drop=True)
