"""Bloomberg FX rate DAILY pipeline (close-of-day cadence).

Reads the same BBG_mirror live CSVs as ``BloombergFXRatePipeline``
(snapshot pipeline) but stamps each captured row with:

  - ``frequency_id = DAILY``
  - ``obs_ts = midnight UTC of obs_date``

Per user-confirmed semantics: "the last snapshot is the close for the
day in our case" — both pipelines read the LATEST row from each CSV.
The two paths are siloed by how they STAMP the row, not by what they
READ. Same files, different metadata.

Cadence: fired once per day from ``imdr_daily.py`` after the BBG 19:00
SGT batch settles + mirror sync (~22:00 SGT recommended).

Idempotent on the (pair_id, vendor_id, frequency_id, obs_ts, tenor)
unique key — re-runs on the same business day are MERGE no-ops because
the obs_ts is fixed at midnight UTC.

**HARD RULE — Z:\\BBG_mirror\\ is read-only.** No moves/renames/deletes/
writes to source. Same contract as the snapshot pipeline; enforced by
``archive_after_load=False`` on the ``bbg_fx_daily`` feed and a lock-in
test at ``tests/unit/test_vendors/test_bbg_fx_daily_no_move.py``.
"""
from __future__ import annotations

import pandas as pd
import structlog

from imdr.domains.fx.pipeline_rate_bbg import BloombergFXRatePipeline

_log = structlog.get_logger("BloombergFXRateDailyPipeline")


class BloombergFXRateDailyPipeline(BloombergFXRatePipeline):
    """ETL pipeline: BBG live CSVs → fx.fact_fx_rate (DAILY cadence).

    Subclasses the snapshot pipeline — same extract path (latest row
    per pair) and same transform/load. Three overrides:
      1. ``pipeline_name`` → distinguishes audit logs from snapshot
      2. ``FREQUENCY_CODE`` → DAILY, so the parent's transform stamps
         the right ``frequency_id`` without any module mutation
      3. ``extract`` post-processing → rewrite ``obs_ts`` to midnight
         UTC of ``obs_date`` so MERGE keys at DAILY frequency don't
         collide with intraday SNAPSHOT rows.
    """

    pipeline_name = "fx.bloomberg_daily"
    FREQUENCY_CODE = "DAILY"

    def extract(self) -> pd.DataFrame:
        """Run the snapshot extractor, then rewrite obs_ts to midnight UTC.

        The parent class already filters to the LATEST obs_date per pair
        (SNAPSHOT semantics — see ``BloombergFXRatePipeline.extract``).
        For DAILY we keep the same row set but override the timestamp
        so it represents the business date, not the wall-clock.
        """
        df = super().extract()
        if df.empty:
            return df

        # Override obs_ts: midnight UTC of obs_date (close-of-day stamp)
        df["obs_ts"] = pd.to_datetime(df["obs_date"]).dt.tz_localize("UTC")
        df["ts"] = df["obs_ts"]  # alias kept for any downstream expecting `ts`

        self._raw_df = df
        _log.info(
            "extract_complete_daily",
            rows=len(df),
            obs_date_range=(str(df["obs_date"].min()), str(df["obs_date"].max())),
        )
        return df

