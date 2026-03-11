"""Rates observation data cleaning rules.

Detects and corrects data quality issues in [rates].[fact_observation]:
  - Hard-bound violations → NULL value
  - Robust outliers       → NULL value
  - Percentage change     → NULL value

Each rule is idempotent — safe to re-run.  Dry-run mode (default)
shows what would change without writing.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from imdr.connectors.reader import AnalyticalReader
from imdr.healthchecks.cleaning import CleaningAction, CleaningRule

TABLE = "[rates].[fact_observation]"


# ---------------------------------------------------------------------------
# Rule implementations
# ---------------------------------------------------------------------------

class HardBoundViolationRule(CleaningRule):
    """NULL out rows where value falls outside per-quote-type hard bounds."""

    def __init__(
        self,
        ranges: dict[str, tuple[float, float]],
    ) -> None:
        self._ranges = ranges

    @property
    def name(self) -> str:
        return "hard_bound"

    @property
    def action_label(self) -> str:
        return "null_value"

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
        for quote, (lo, hi) in self._ranges.items():
            when_clauses.append(
                f"([quote] = '{quote}' AND ([value] < {lo} OR [value] > {hi}))"
            )
        filter_expr = " OR ".join(when_clauses)

        sql = f"""
            SELECT [id], [ts], [curve_id], [quote], [tenor], [value]
            FROM {table}
            WHERE ({filter_expr}) {where}
        """
        return reader.read_sql(sql, params)

    def build_update_sql(self, ids: list[int]) -> str:
        id_list = ", ".join(str(i) for i in ids)
        return f"UPDATE {TABLE} SET [value] = NULL WHERE [id] IN ({id_list})"

    def build_action(self, row: pd.Series) -> CleaningAction:
        return CleaningAction(
            rule_name=self.name,
            row_id=int(row["id"]),
            ts=row["ts"],
            action=self.action_label,
            detail=self.describe(row),
            context={
                "curve_id": int(row["curve_id"]),
                "quote": row["quote"],
                "tenor": row["tenor"],
            },
        )

    def describe(self, row: pd.Series) -> str:
        lo, hi = self._ranges.get(row["quote"], (None, None))
        return (
            f"hard bound: curve_id={row['curve_id']} {row['quote']} {row['tenor']} "
            f"value={row['value']} outside [{lo}, {hi}] @ {row['ts']}"
        )


class RobustOutlierRule(CleaningRule):
    """NULL out rows that are outliers by median + MAD (trailing window)."""

    _MAD_SCALE = 1.4826

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
        return "null_value"

    def detect(
        self,
        reader: AnalyticalReader,
        table: str = TABLE,
        where: str = "",
        params: dict[str, Any] | None = None,
    ) -> pd.DataFrame:
        sql = f"""
            SELECT [id], [ts], [curve_id], [quote], [tenor], [value]
            FROM {table}
            WHERE 1=1
              {where}
            ORDER BY [curve_id], [quote], [tenor], [ts]
        """
        df = reader.read_sql(sql, params)
        if df.empty:
            return df

        df["ts"] = pd.to_datetime(df["ts"], utc=True)
        group_cols = ["curve_id", "quote", "tenor"]
        df = df.sort_values(group_cols + ["ts"])

        window = f"{self._trailing_months * 30}D"
        flagged: list[pd.DataFrame] = []

        for _key, grp in df.groupby(group_cols):
            grp = grp.set_index("ts").sort_index()
            vals = grp["value"].astype(float)

            if len(vals) < self._min_obs:
                continue

            # Interpolate NaN for stable stats (NULL'd rows don't shift distribution)
            vals_for_stats = vals.interpolate(method="time")

            roll_median = vals_for_stats.rolling(window, min_periods=self._min_obs).median()
            abs_dev = (vals_for_stats - roll_median).abs()
            roll_mad = abs_dev.rolling(window, min_periods=self._min_obs).median()
            robust_sigma = roll_mad * self._MAD_SCALE

            # Flag using ORIGINAL values (not interpolated)
            robust_z = (vals - roll_median).abs() / robust_sigma.replace(0, float("nan"))
            mask = (robust_z > self._n_mad) & vals.notna()

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
        return f"UPDATE {TABLE} SET [value] = NULL WHERE [id] IN ({id_list})"

    def build_action(self, row: pd.Series) -> CleaningAction:
        return CleaningAction(
            rule_name=self.name,
            row_id=int(row["id"]),
            ts=row["ts"],
            action=self.action_label,
            detail=self.describe(row),
            context={
                "curve_id": int(row["curve_id"]),
                "quote": row["quote"],
                "tenor": row["tenor"],
            },
        )

    def describe(self, row: pd.Series) -> str:
        return (
            f"robust outlier: curve_id={row['curve_id']} {row['quote']} {row['tenor']} "
            f"value={row.get('value', '?')} z={row.get('robust_z', '?'):.1f} "
            f"@ {row['ts']}"
        )


class PercentageChangeRule(CleaningRule):
    """NULL out rows where value changed by more than threshold from previous observation."""

    def __init__(self, threshold_pct: float = 30.0) -> None:
        self._threshold = threshold_pct

    @property
    def name(self) -> str:
        return "pct_change"

    @property
    def action_label(self) -> str:
        return "null_value"

    def detect(
        self,
        reader: AnalyticalReader,
        table: str = TABLE,
        where: str = "",
        params: dict[str, Any] | None = None,
    ) -> pd.DataFrame:
        sql = f"""
            WITH with_prev AS (
                SELECT [id], [ts], [curve_id], [quote], [tenor], [value],
                       LAG([value]) OVER (
                           PARTITION BY [curve_id], [quote], [tenor]
                           ORDER BY [ts]
                       ) AS prev_val
                FROM {table}
                WHERE 1=1
                  {where}
            )
            SELECT [id], [ts], [curve_id], [quote], [tenor],
                   [value], prev_val,
                   ([value] - prev_val)
                       / ABS(NULLIF(prev_val, 0)) * 100.0 AS pct_change
            FROM with_prev
            WHERE [value] IS NOT NULL
              AND prev_val IS NOT NULL
              AND prev_val != 0
              AND ABS(([value] - prev_val)
                      / ABS(prev_val) * 100.0) > {self._threshold}
        """
        return reader.read_sql(sql, params)

    def build_update_sql(self, ids: list[int]) -> str:
        id_list = ", ".join(str(i) for i in ids)
        return f"UPDATE {TABLE} SET [value] = NULL WHERE [id] IN ({id_list})"

    def build_action(self, row: pd.Series) -> CleaningAction:
        return CleaningAction(
            rule_name=self.name,
            row_id=int(row["id"]),
            ts=row["ts"],
            action=self.action_label,
            detail=self.describe(row),
            context={
                "curve_id": int(row["curve_id"]),
                "quote": row["quote"],
                "tenor": row["tenor"],
            },
        )

    def describe(self, row: pd.Series) -> str:
        pct = row.get("pct_change")
        pct_str = f" ({pct:+.1f}%)" if pd.notna(pct) else ""
        return (
            f"pct_change: curve_id={row['curve_id']} {row['quote']} {row['tenor']}"
            f" value={row['value']}{pct_str} from prev={row.get('prev_val', '?')}"
            f" @ {row['ts']}"
        )
