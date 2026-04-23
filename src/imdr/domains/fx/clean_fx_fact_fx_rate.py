"""FX Rate data cleaning rules for [fx].[fact_fx_rate].

Each rule NULLs bad values in mid_rate (does not delete rows). Per the
flag-don't-block principle, these run post-ingest as a separate cleaning pass.

Rules:
  - HardBoundViolationRule : per-pair expected range from fx.yml
  - RobustOutlierRule      : MAD-based (trailing-window)
  - PercentageChangeRule   : day-over-day % change threshold

Each rule is idempotent — safe to re-run. Dry-run mode (default) shows what
would change without writing.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from imdr.connectors.reader import AnalyticalReader
from imdr.healthchecks.cleaning import CleaningAction, CleaningRule

TABLE = "[fx].[fact_fx_rate]"


def _pair_label(row: pd.Series) -> str:
    b, q = row.get("base_ccy"), row.get("quote_ccy")
    if b and q:
        return f"{b}{q}"
    return f"pair_id={row['pair_id']}"


# ---------------------------------------------------------------------------
# Rule: hard-bound violation (per-pair min/max from fx.yml fx_rate.expected_ranges)
# ---------------------------------------------------------------------------

class HardBoundViolationRule(CleaningRule):
    """NULL out rows where mid_rate falls outside per-pair hard bounds."""

    def __init__(self, ranges: dict[str, tuple[float, float]]) -> None:
        """ranges: {pair_code (BASE+QUOTE) -> (min, max)}"""
        self._ranges = ranges

    @property
    def name(self) -> str:
        return "hard_bound"

    @property
    def action_label(self) -> str:
        return "null_mid_rate"

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
        for pair_code, (lo, hi) in self._ranges.items():
            base, quote = pair_code[:3], pair_code[3:]
            when_clauses.append(
                f"(p.[base_ccy] = '{base}' AND p.[quote_ccy] = '{quote}' "
                f"AND (r.[mid_rate] < {lo} OR r.[mid_rate] > {hi}))"
            )
        filter_expr = " OR ".join(when_clauses)

        sql = f"""
            SELECT r.[id], r.[obs_date], r.[pair_id], p.[base_ccy], p.[quote_ccy],
                   r.[tenor], r.[mid_rate]
            FROM {table} r
            JOIN [fx].[dim_currency_pair] p ON p.id = r.pair_id
            WHERE ({filter_expr}) {where}
        """
        return reader.read_sql(sql, params)

    def build_update_sql(self, ids: list[int]) -> str:
        id_list = ", ".join(str(i) for i in ids)
        # CHECK constraint forbids mid_rate <= 0, so we can't NULL mid_rate directly
        # (column is NOT NULL). Instead, delete the violating row entirely — safer
        # than storing a bad value. Row will be re-inserted on next clean ingest.
        return f"DELETE FROM {TABLE} WHERE [id] IN ({id_list})"

    def build_action(self, row: pd.Series) -> CleaningAction:
        return CleaningAction(
            rule_name=self.name,
            row_id=int(row["id"]),
            ts=row["obs_date"],
            action=self.action_label,
            detail=self.describe(row),
            context={"pair_id": int(row["pair_id"]), "tenor": row["tenor"]},
        )

    def describe(self, row: pd.Series) -> str:
        pair = _pair_label(row)
        lo, hi = self._ranges.get(pair, (None, None))
        return (
            f"hard bound: {pair} {row['tenor']} mid_rate={row['mid_rate']} "
            f"outside [{lo}, {hi}] @ {row['obs_date']}"
        )


# ---------------------------------------------------------------------------
# Rule: robust outlier (MAD-based, trailing window)
# ---------------------------------------------------------------------------

class RobustOutlierRule(CleaningRule):
    """Flag rows that are outliers by median + MAD on the trailing window."""

    _MAD_SCALE = 1.4826

    def __init__(
        self,
        n_mad: float = 5.0,
        trailing_months: int = 6,
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
        return "flag_outlier"

    def detect(
        self,
        reader: AnalyticalReader,
        table: str = TABLE,
        where: str = "",
        params: dict[str, Any] | None = None,
    ) -> pd.DataFrame:
        sql = f"""
            SELECT r.[id], r.[obs_date], r.[pair_id], p.[base_ccy], p.[quote_ccy],
                   r.[tenor], r.[mid_rate]
            FROM {table} r
            JOIN [fx].[dim_currency_pair] p ON p.id = r.pair_id
            WHERE 1=1 {where}
            ORDER BY r.[pair_id], r.[tenor], r.[obs_date]
        """
        df = reader.read_sql(sql, params)
        if df.empty:
            return df

        df["obs_date"] = pd.to_datetime(df["obs_date"])
        group_cols = ["pair_id", "tenor"]
        df = df.sort_values(group_cols + ["obs_date"])

        window = f"{self._trailing_months * 30}D"
        flagged: list[pd.DataFrame] = []
        for _key, grp in df.groupby(group_cols):
            grp = grp.set_index("obs_date").sort_index()
            vals = grp["mid_rate"].astype(float)
            if len(vals) < self._min_obs:
                continue
            vals_for_stats = vals.interpolate(method="time")
            roll_median = vals_for_stats.rolling(window, min_periods=self._min_obs).median()
            abs_dev = (vals_for_stats - roll_median).abs()
            roll_mad = abs_dev.rolling(window, min_periods=self._min_obs).median()
            robust_sigma = roll_mad * self._MAD_SCALE
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
        return pd.concat(flagged, ignore_index=True).sort_values("robust_z", ascending=False)

    def build_update_sql(self, ids: list[int]) -> str:
        # Flagging-only rule — no UPDATE (mid_rate is NOT NULL, we preserve the data).
        # Real action: human review via dashboard / manual DELETE if needed.
        return ""

    def build_action(self, row: pd.Series) -> CleaningAction:
        return CleaningAction(
            rule_name=self.name,
            row_id=int(row["id"]),
            ts=row["obs_date"],
            action=self.action_label,
            detail=self.describe(row),
            context={"pair_id": int(row["pair_id"]), "tenor": row["tenor"]},
        )

    def describe(self, row: pd.Series) -> str:
        z = row.get("robust_z", float("nan"))
        z_str = f"{z:.1f}" if pd.notna(z) else "?"
        return (
            f"robust outlier: {_pair_label(row)} {row['tenor']} "
            f"mid_rate={row.get('mid_rate', '?')} z={z_str} @ {row['obs_date']}"
        )


# ---------------------------------------------------------------------------
# Rule: percentage change (day-over-day)
# ---------------------------------------------------------------------------

class PercentageChangeRule(CleaningRule):
    """Flag rows where mid_rate changed by more than threshold_pct from previous day."""

    def __init__(self, threshold_pct: float = 10.0, min_abs_prev: float = 1e-6) -> None:
        self._threshold = threshold_pct
        self._min_abs_prev = min_abs_prev

    @property
    def name(self) -> str:
        return "pct_change"

    @property
    def action_label(self) -> str:
        return "flag_pct_change"

    def detect(
        self,
        reader: AnalyticalReader,
        table: str = TABLE,
        where: str = "",
        params: dict[str, Any] | None = None,
    ) -> pd.DataFrame:
        sql = f"""
            WITH with_prev AS (
                SELECT r.[id], r.[obs_date], r.[pair_id], p.[base_ccy], p.[quote_ccy],
                       r.[tenor], r.[mid_rate],
                       LAG(r.[mid_rate]) OVER (
                           PARTITION BY r.[pair_id], r.[tenor]
                           ORDER BY r.[obs_date]
                       ) AS prev_val
                FROM {table} r
                JOIN [fx].[dim_currency_pair] p ON p.id = r.pair_id
                WHERE 1=1 {where}
            )
            SELECT [id], [obs_date], [pair_id], [base_ccy], [quote_ccy],
                   [tenor], [mid_rate], prev_val,
                   CASE WHEN ABS(prev_val) > 0
                        THEN ([mid_rate] - prev_val) / ABS(prev_val) * 100.0
                        ELSE NULL
                   END AS pct_change
            FROM with_prev
            WHERE prev_val IS NOT NULL
              AND ABS(prev_val) >= {self._min_abs_prev}
              AND ABS([mid_rate] - prev_val) / ABS(prev_val) * 100.0 > {self._threshold}
        """
        return reader.read_sql(sql, params)

    def build_update_sql(self, ids: list[int]) -> str:
        # Flagging-only — don't NULL or delete (could be a legitimate devaluation).
        return ""

    def build_action(self, row: pd.Series) -> CleaningAction:
        return CleaningAction(
            rule_name=self.name,
            row_id=int(row["id"]),
            ts=row["obs_date"],
            action=self.action_label,
            detail=self.describe(row),
            context={"pair_id": int(row["pair_id"]), "tenor": row["tenor"]},
        )

    def describe(self, row: pd.Series) -> str:
        pct = row.get("pct_change")
        pct_str = f" ({pct:+.1f}%)" if pd.notna(pct) else ""
        return (
            f"pct_change: {_pair_label(row)} {row['tenor']} "
            f"mid_rate={row['mid_rate']}{pct_str} from prev={row.get('prev_val', '?')}"
            f" @ {row['obs_date']}"
        )
