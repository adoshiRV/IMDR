"""FX Vol data cleaning rules.

Detects and corrects data quality issues in [fx].[fact_vol]:
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

TABLE = "[fx].[fact_vol]"


def _pair_label(row: pd.Series) -> str:
    """Format pair as 'EURUSD' from base_ccy/quote_ccy columns, fallback to pair_id."""
    b, q = row.get("base_ccy"), row.get("quote_ccy")
    if b and q:
        return f"{b}{q}"
    return f"pair_id={row['pair_id']}"


# ---------------------------------------------------------------------------
# Rule implementations
# ---------------------------------------------------------------------------

class HardBoundViolationRule(CleaningRule):
    """NULL out rows where value falls outside per-(strike, vol_type) hard bounds."""

    def __init__(
        self,
        ranges: dict[tuple[str, str], tuple[float, float]],
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
        for (strike, vol_type), (lo, hi) in self._ranges.items():
            when_clauses.append(
                f"(v.[strike] = '{strike}' AND v.[vol_type] = '{vol_type}' "
                f"AND (v.[value] < {lo} OR v.[value] > {hi}))"
            )
        filter_expr = " OR ".join(when_clauses)

        sql = f"""
            SELECT v.[id], v.[obs_date], v.[pair_id], p.[base_ccy], p.[quote_ccy],
                   v.[strike], v.[tenor], v.[vol_type], v.[value]
            FROM {table} v
            JOIN [fx].[dim_currency_pair] p ON p.id = v.pair_id
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
            ts=row["obs_date"],
            action=self.action_label,
            detail=self.describe(row),
            context={
                "pair_id": int(row["pair_id"]),
                "strike": row["strike"],
                "tenor": row["tenor"],
            },
        )

    def describe(self, row: pd.Series) -> str:
        key = (row["strike"], row["vol_type"])
        lo, hi = self._ranges.get(key, (None, None))
        return (
            f"hard bound: {_pair_label(row)} {row['strike']} {row['tenor']} "
            f"{row['vol_type']} value={row['value']} outside [{lo}, {hi}] "
            f"@ {row['obs_date']}"
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
            SELECT v.[id], v.[obs_date], v.[pair_id], p.[base_ccy], p.[quote_ccy],
                   v.[strike], v.[tenor], v.[vol_type], v.[value]
            FROM {table} v
            JOIN [fx].[dim_currency_pair] p ON p.id = v.pair_id
            WHERE 1=1
              {where}
            ORDER BY v.[pair_id], v.[strike], v.[tenor], v.[obs_date]
        """
        df = reader.read_sql(sql, params)
        if df.empty:
            return df

        df["obs_date"] = pd.to_datetime(df["obs_date"])
        group_cols = ["pair_id", "strike", "tenor", "vol_type"]
        df = df.sort_values(group_cols + ["obs_date"])

        window = f"{self._trailing_months * 30}D"
        flagged: list[pd.DataFrame] = []

        for _key, grp in df.groupby(group_cols):
            grp = grp.set_index("obs_date").sort_index()
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
            ts=row["obs_date"],
            action=self.action_label,
            detail=self.describe(row),
            context={
                "pair_id": int(row["pair_id"]),
                "strike": row["strike"],
                "tenor": row["tenor"],
            },
        )

    def describe(self, row: pd.Series) -> str:
        return (
            f"robust outlier: {_pair_label(row)} {row['strike']} {row['tenor']} "
            f"{row.get('vol_type', '')} value={row.get('value', '?')} "
            f"z={row.get('robust_z', '?'):.1f} @ {row['obs_date']}"
        )


class PercentageChangeRule(CleaningRule):
    """NULL out rows where value changed by more than threshold from previous day.

    Three-tier filtering logic:

    1. **Absolute-change strikes** (RR, STR): percentage change is meaningless
       for signed/near-zero values.  Uses absolute vol-point thresholds.
    2. **Class×tenor pct thresholds**: different ccy_class + tenor combos have
       different vol-of-vol.  Short EM tenors get wider thresholds than
       long-dated G10.  Requires JOIN to ``dim_currency_pair``.
    3. **Fallback pct threshold**: ``pipelines.yml`` scalar for unmapped combos.

    Args:
        threshold_pct: Fallback percentage threshold (from pipelines.yml).
        abs_change_strikes: Strike → absolute vol-point threshold.
        pct_thresholds: ccy_class → tenor → pct threshold (from fx.yml).
        min_abs_prev: Minimum ``ABS(prev_val)`` for pct-change paths.
    """

    def __init__(
        self,
        threshold_pct: float = 30.0,
        abs_change_strikes: dict[str, float] | None = None,
        abs_change_vol_types: dict[str, float] | None = None,
        pct_thresholds: dict[str, dict[str, float]] | None = None,
        min_abs_prev: float = 0.5,
    ) -> None:
        self._threshold = threshold_pct
        self._abs_strikes = abs_change_strikes or {}
        self._abs_vol_types = abs_change_vol_types or {}
        self._pct_thresholds = pct_thresholds or {}
        self._min_abs_prev = min_abs_prev

    @property
    def name(self) -> str:
        return "pct_change"

    @property
    def action_label(self) -> str:
        return "null_value"

    def _build_pct_expr(self) -> str:
        return "ABS(([value] - prev_val) / ABS(prev_val) * 100.0)"

    def detect(
        self,
        reader: AnalyticalReader,
        table: str = TABLE,
        where: str = "",
        params: dict[str, Any] | None = None,
    ) -> pd.DataFrame:
        pct_expr = self._build_pct_expr()
        min_prev = f"AND ABS(prev_val) >= {self._min_abs_prev} " if self._min_abs_prev > 0 else ""
        abs_strike_list = ", ".join(f"'{s}'" for s in self._abs_strikes)
        abs_vol_type_list = ", ".join(f"'{vt}'" for vt in self._abs_vol_types)
        not_abs_strike = f"[strike] NOT IN ({abs_strike_list})" if abs_strike_list else "1=1"
        not_abs_vol_type = f"[vol_type] NOT IN ({abs_vol_type_list})" if abs_vol_type_list else "1=1"
        not_abs = f"{not_abs_strike} AND {not_abs_vol_type}"

        # --- Tier 0: absolute-change vol_types (SPREAD, REALISED) ---
        abs_vol_clauses = [
            f"([vol_type] = '{vt}' AND ABS([value] - prev_val) > {thresh})"
            for vt, thresh in self._abs_vol_types.items()
        ]

        # --- Tier 1: absolute-change strikes (exclude vol_types handled by Tier 0) ---
        abs_clauses = [
            f"({not_abs_vol_type} AND [strike] = '{strike}' AND ABS([value] - prev_val) > {thresh})"
            for strike, thresh in self._abs_strikes.items()
        ]

        # --- Tier 2: class×tenor pct thresholds ---
        ct_clauses = []
        mapped_combos: list[str] = []
        for ccy_class, tenor_map in self._pct_thresholds.items():
            for tenor, thresh in tenor_map.items():
                ct_clauses.append(
                    f"({not_abs} AND [ccy_class] = '{ccy_class}' AND [tenor] = '{tenor}' "
                    f"AND prev_val != 0 {min_prev}"
                    f"AND {pct_expr} > {thresh})"
                )
                mapped_combos.append(
                    f"([ccy_class] = '{ccy_class}' AND [tenor] = '{tenor}')"
                )

        # --- Tier 3: fallback for unmapped combos ---
        not_mapped = (
            f"AND NOT ({' OR '.join(mapped_combos)})" if mapped_combos else ""
        )
        fallback_clause = (
            f"({not_abs} {not_mapped} "
            f"AND prev_val != 0 {min_prev}"
            f"AND {pct_expr} > {self._threshold})"
        )

        all_conditions = abs_vol_clauses + abs_clauses + ct_clauses + [fallback_clause]
        filter_expr = " OR ".join(all_conditions)

        # JOIN dim_currency_pair to get ccy_class for tier-2 filtering
        sql = f"""
            WITH with_prev AS (
                SELECT v.[id], v.[obs_date], v.[pair_id], p.[base_ccy], p.[quote_ccy],
                       v.[strike], v.[tenor], v.[vol_type], v.[value], p.[ccy_class],
                       LAG(v.[value]) OVER (
                           PARTITION BY v.[pair_id], v.[strike], v.[tenor], v.[vol_type]
                           ORDER BY v.[obs_date]
                       ) AS prev_val
                FROM {table} v
                JOIN [fx].[dim_currency_pair] p ON p.id = v.pair_id
                WHERE 1=1
                  {where}
            )
            SELECT [id], [obs_date], [pair_id], [base_ccy], [quote_ccy],
                   [strike], [tenor], [vol_type], [ccy_class], [value], prev_val,
                   CASE WHEN ABS(prev_val) > 0
                        THEN ([value] - prev_val)
                             / ABS(prev_val) * 100.0
                        ELSE NULL
                   END AS pct_change
            FROM with_prev
            WHERE [value] IS NOT NULL
              AND prev_val IS NOT NULL
              AND ({filter_expr})
        """
        return reader.read_sql(sql, params)

    def build_update_sql(self, ids: list[int]) -> str:
        id_list = ", ".join(str(i) for i in ids)
        return f"UPDATE {TABLE} SET [value] = NULL WHERE [id] IN ({id_list})"

    def build_action(self, row: pd.Series) -> CleaningAction:
        return CleaningAction(
            rule_name=self.name,
            row_id=int(row["id"]),
            ts=row["obs_date"],
            action=self.action_label,
            detail=self.describe(row),
            context={
                "pair_id": int(row["pair_id"]),
                "strike": row["strike"],
                "tenor": row["tenor"],
            },
        )

    def describe(self, row: pd.Series) -> str:
        pct = row.get("pct_change")
        pct_str = f" ({pct:+.1f}%)" if pd.notna(pct) else ""
        return (
            f"pct_change: {_pair_label(row)} {row['strike']} {row['tenor']}"
            f" {row.get('vol_type', '')}"
            f" value={row['value']}{pct_str} from prev={row.get('prev_val', '?')}"
            f" @ {row['obs_date']}"
        )
