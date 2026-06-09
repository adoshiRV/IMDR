"""Bloomberg rates DAILY pipeline (close-of-day cadence + historical backfill).

Reads the same BBG_mirror PAR CSVs as ``BloombergRatesPipeline``
(snapshot pipeline) but stamps each captured row with:

  - ``frequency_id = DAILY``
  - ``ts = midnight UTC of obs_date``

Two run modes (one class, two callers):
  * **Daily live** (``historical=False``, default) — reads the LATEST
    row per curve. Used by the ``bbg_rates_daily`` vendor feed which
    fires once/day at ~22:00 SGT via ``imdr_daily.py``.
  * **Historical backfill** (``historical=True``) — reads ALL rows from
    each CSV. Used by the one-shot
    ``scripts/migrations/load_bbg_rates_historical.py``.

Both modes share auto-seeding of ``rates.dim_curve``, the same MERGE
upsert path, and the same ts-at-midnight + DAILY-frequency stamping —
only the row scope + volume differ.

Idempotent on ``(curve_id, vendor_id, ts, quote, tenor, frequency_id)``
— re-runs of either mode are no-ops once data is in.

**HARD RULE — Z:\\BBG_mirror\\ is read-only.** No file moves/renames/
deletes/writes. Same lock-in test contract as the snapshot pipeline.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import structlog

from imdr.config.settings import Settings
from imdr.connectors.mssql import MSSQLConnector
from imdr.domains.rates.extractors_bbg import BloombergCSVRatesExtractor
from imdr.domains.rates.pipeline_bbg import BloombergRatesPipeline

_log = structlog.get_logger("BloombergRatesDailyPipeline")


class BloombergRatesDailyPipeline(BloombergRatesPipeline):
    """ETL pipeline: BBG rates CSVs → rates.fact_observation (DAILY cadence).

    Subclass of ``BloombergRatesPipeline``. Reuses transform/load
    unchanged; overrides only:
      * ``FREQUENCY_CODE`` → DAILY (parent's transform reads this)
      * ``_extractor`` → switches the extractor's mode flag
      * ``extract`` → after the parent walk, rewrite ``ts`` to midnight
        UTC of ``obs_date`` (live mode only; historical mode is already
        stamped at midnight by the extractor).
    """

    pipeline_name = "rates.bloomberg_daily"
    FREQUENCY_CODE = "DAILY"

    def __init__(
        self,
        files: list[Path],
        connector: MSSQLConnector,
        settings: Settings,
        bbg_root: Path | None = None,
        chunk_size: int | None = None,
        historical: bool = False,
    ) -> None:
        super().__init__(
            files=files,
            connector=connector,
            settings=settings,
            bbg_root=bbg_root,
            chunk_size=chunk_size,
        )
        self._historical = historical

    def _extractor(self) -> BloombergCSVRatesExtractor:
        mode = "historical" if self._historical else "live"
        return BloombergCSVRatesExtractor(mode=mode)

    def extract(self) -> pd.DataFrame:
        df = super().extract()
        if df.empty or self._historical:
            # Historical mode: extractor already set ts = midnight UTC of obs_date.
            return df

        # Live mode: extractor stamped ts = file mtime UTC. Rewrite to
        # midnight UTC of obs_date so MERGE keys at DAILY frequency don't
        # collide with intraday SNAPSHOT rows.
        obs_date = df["ts"].dt.tz_convert("UTC").dt.date
        df = df.assign(ts=pd.to_datetime(obs_date).dt.tz_localize("UTC"))
        self._raw_df = df
        return df
