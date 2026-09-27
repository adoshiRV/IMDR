"""Bloomberg FX rate BACKFILL pipeline (historical tail, DAILY cadence).

Reads the same BBG CSVs as the live pipelines but keeps the file's **full
historical tail** instead of collapsing to the newest row, so a gap of past
business days can be repaired from a single current file.

Why this exists: ``BBG_mirror\\FX`` was provisioned with 22 currency folders
and none of CNY/CNO/MYO/IDO, so the onshore EM forward curves went dark the
day the FX feed cut over to the mirror — last obs 2026-04-24 against a mirror
created 2026-04-28. The legacy ``BBG\\FX`` tree kept carrying them and is
still refreshed by the R pipeline, so ~98 business days of onshore forwards
were recoverable from files that had been sitting there the whole time.

Everything about the row shape is inherited from
``BloombergFXRateDailyPipeline``: ``frequency_id = DAILY`` and
``obs_ts = midnight UTC of obs_date``. That is what makes the historical tail
loadable at all — the live SNAPSHOT path stamps every row with the file's
mtime, so a tail would collide on the
``(pair_id, vendor_id, frequency_id, obs_ts, tenor)`` unique key. Re-stamped
per obs_date, each business day gets its own key and the load is idempotent:
re-running is a MERGE no-op.

**HARD RULE — the BBG tree is read-only.** No moves/renames/deletes/writes to
source, exactly as for the mirror.
"""
from __future__ import annotations

import datetime as dt

import pandas as pd
import structlog

from imdr.domains.fx.pipeline_rate_bbg_daily import BloombergFXRateDailyPipeline

_log = structlog.get_logger("BloombergFXRateBackfillPipeline")


class BloombergFXRateBackfillPipeline(BloombergFXRateDailyPipeline):
    """ETL pipeline: BBG CSV historical tail → fx.fact_fx_rate (DAILY).

    Differs from its parent in exactly two ways:
      1. ``KEEP_ONLY_LATEST = False`` — keep every obs_date in the file.
      2. an optional ``[since, until]`` obs_date window, so a repair can be
         confined to the known gap instead of rewriting years of settled rows.
    """

    pipeline_name = "fx.bloomberg_backfill"
    KEEP_ONLY_LATEST = False

    def __init__(self, *args, since: dt.date | None = None,
                 until: dt.date | None = None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._since = since
        self._until = until

    def extract(self) -> pd.DataFrame:
        """Full-tail extract, narrowed to the requested obs_date window."""
        df = super().extract()
        if df.empty:
            return df

        obs = pd.to_datetime(df["obs_date"]).dt.date
        mask = pd.Series(True, index=df.index)
        if self._since is not None:
            mask &= obs >= self._since
        if self._until is not None:
            mask &= obs <= self._until
        df = df[mask].reset_index(drop=True)

        self._raw_df = df
        _log.info(
            "extract_complete_backfill",
            rows=len(df),
            since=str(self._since) if self._since else None,
            until=str(self._until) if self._until else None,
            obs_date_range=(
                (str(df["obs_date"].min()), str(df["obs_date"].max()))
                if not df.empty else None
            ),
        )
        return df
