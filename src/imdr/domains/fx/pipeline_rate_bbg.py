"""Bloomberg FX rate snapshot pipeline.

Reads BBG-pipeline CSVs from the shared Z: drive (acquired by
``LocalFilesystemAcquirer``), extracts via ``BloombergCSVFXRateExtractor``
(which applies the inverse FxSwap→FxFwd conversion), and upserts into
``fx.fact_fx_rate`` with ``vendor_id=bloomberg`` + ``frequency_id=SNAPSHOT``.

Each invocation captures whatever the BBG CSV currently holds and stamps
``obs_ts`` = file mtime (UTC). Run 6× daily after each BBG batch refresh
to capture all 6 intraday snapshots (see plan + docs).

Idempotent on the (pair, vendor, freq, obs_ts, tenor) unique key — re-runs
within the same BBG batch window are no-ops.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import pandas as pd
import structlog
from sqlalchemy import select

from imdr.config.pipeline_config import get_pipeline_config
from imdr.config.settings import Settings
from imdr.connectors.bulk import chunked_bulk_merge
from imdr.connectors.mssql import MSSQLConnector
from imdr.domains.fx.extractors_rate_bbg import (
    BBGFXSourceFile,
    BloombergCSVFXRateExtractor,
    resolve_pair_orientation,
)
from imdr.domains.fx.repository_rate import FXRateRepository, FX_RATE_SPEC
from imdr.domains.fx.repository_vol import FXCurrencyPairRepository
from imdr.models.frequency import DimFrequency
from imdr.models.vendor import DimVendor
from imdr.pipelines.base import BasePipeline
from imdr.schemas.fx_rate import FXRateCreate
from imdr.universe.fx import FXUniverse

_log = structlog.get_logger("BloombergFXRatePipeline")

VENDOR_CODE = "BBG"

# Default mapping from IMDR pair → BBG ccy folder.
# BBG names files by the non-USD leg, e.g. ``FX_EUR.csv`` for EUR/USD,
# ``FX_JPY.csv`` for USD/JPY. We resolve this at extract time via the
# extractor's ``resolve_pair_orientation`` helper, but the universe drives
# WHICH ccys to look for.
_DEFAULT_BBG_FX_ROOT = Path(r"Z:\Business\Research\Dashboard\DataSources\BBG_mirror\FX")


def _ccys_from_universe(universe: FXUniverse) -> list[str]:
    """Pick the non-USD leg of each pair as the BBG ccy folder name."""
    out: list[str] = []
    seen: set[str] = set()
    for base, quote in universe.fx_rate_pairs():
        ccy = quote if base == "USD" else base
        if ccy not in seen:
            seen.add(ccy)
            out.append(ccy)
    return out


class BloombergFXRatePipeline(BasePipeline[pd.DataFrame, list[FXRateCreate], int]):
    """ETL pipeline: BBG CSVs → fx.fact_fx_rate (SNAPSHOT cadence)."""

    pipeline_name = "fx.bloomberg_snapshot"
    domain = "fx"

    # Frequency stamp for this pipeline's rows. Overridden by
    # ``BloombergFXRateDailyPipeline`` (DAILY). Read inside ``transform``
    # so subclasses get the right value without monkey-patching the module.
    FREQUENCY_CODE: str = "SNAPSHOT"

    def __init__(
        self,
        files: list[Path],
        connector: MSSQLConnector,
        settings: Settings,
        universe: FXUniverse | None = None,
        bbg_fx_root: Path | None = None,
        chunk_size: int | None = None,
    ) -> None:
        super().__init__(connector)
        self._settings = settings
        self._universe = universe
        self._files = files
        self._bbg_fx_root = bbg_fx_root or _DEFAULT_BBG_FX_ROOT
        self._chunk_size = chunk_size
        # Use Citi rate config for thresholds — it shares the target table
        self._config = get_pipeline_config("fx.citi_rate")
        self._raw_df: pd.DataFrame | None = None
        self._extraction_errors: list[dict] = []

    def extract(self) -> pd.DataFrame:
        """Parse acquired BBG CSVs into the IMDR wide DataFrame format.

        ``self._files`` comes from ``LocalFilesystemAcquirer.fetch()`` —
        we discover orientation + obs_ts (file mtime) here, then extract.
        """
        # Alias the extractor's errors list before any stat()/extract() call
        # so a path.stat() failure (file deleted between acquisition and
        # here — R pipeline overwrites in place) and an extractor failure
        # both flow into the same diagnostic stream.
        extractor = BloombergCSVFXRateExtractor()
        self._extraction_errors = extractor.errors

        # Reconstruct BBGFXSourceFile from the acquired Path list. We trust
        # the layout: <root>/<CCY>/FX_<CCY>.csv (parent.name is the ccy code).
        srcs: list[BBGFXSourceFile] = []
        for path in self._files:
            ccy = path.parent.name
            try:
                base, quote = resolve_pair_orientation(ccy)
                mtime = datetime.fromtimestamp(
                    path.stat().st_mtime, tz=timezone.utc,
                )
            except (FileNotFoundError, OSError) as exc:
                self._extraction_errors.append({
                    "file": str(path),
                    "ccy": ccy,
                    "error": f"{type(exc).__name__}: {exc}",
                })
                _log.warning("bbg_source_file_missing", path=str(path), ccy=ccy)
                continue
            srcs.append(
                BBGFXSourceFile(
                    path=path, ccy=ccy, base_ccy=base,
                    quote_ccy=quote, obs_ts=mtime,
                )
            )

        df = extractor.extract(srcs)

        # SNAPSHOT semantics: each ingest captures one batch moment per pair.
        # The live BBG CSV holds the full historical tail, but only the top
        # row reflects "this batch" — older rows belong to prior days and
        # were captured by the Phase A backfill at frequency_id=DAILY. Keep
        # only the latest obs_date per pair so MERGE's unique key
        # (pair, vendor, freq, obs_ts, tenor) doesn't collide on rows that
        # all share the same file-mtime obs_ts.
        if not df.empty:
            latest_per_pair = df.groupby(["base_ccy", "quote_ccy"])["obs_date"].transform("max")
            df = df[df["obs_date"] == latest_per_pair].reset_index(drop=True)

        self._raw_df = df
        _log.info(
            "extract_complete",
            files=len(srcs),
            rows=len(df),
            extraction_errors=len(self._extraction_errors),
        )
        return df

    def transform(self, raw: pd.DataFrame) -> list[FXRateCreate]:
        """Resolve FKs, validate via Pydantic. Mirrors the Citi pipeline."""
        # No new BBG snapshot files this fire (R pipeline batch hasn't rolled
        # over yet, or every file disappeared at acquisition time). Skip the
        # session — nothing to seed or upsert.
        if raw.empty:
            return []
        # 1. Auto-seed dim_currency_pair (idempotent)
        if self._universe is None:
            from imdr.universe.fx import get_fx_universe
            self._universe = get_fx_universe()
        pairs_to_seed = self._universe.fx_rate_pair_create_entries()
        with self._connector.session() as session:
            pair_repo = FXCurrencyPairRepository(session)
            inserted = pair_repo.bulk_seed_from_universe(pairs_to_seed)
            if inserted:
                _log.info("dim_currency_pair_seeded", new_pairs=inserted)

            # 2. pair_id cache
            pair_id_cache: dict[tuple[str, str], int] = {}
            for pair in pair_repo.all():
                pair_id_cache[(pair.base_ccy, pair.quote_ccy)] = pair.id

            # 3. Resolve vendor_id + frequency_id (fail loudly if missing)
            vendor = session.execute(
                select(DimVendor).where(DimVendor.vendor_code == VENDOR_CODE)
            ).scalar_one_or_none()
            if vendor is None:
                raise RuntimeError(
                    f"Vendor '{VENDOR_CODE}' missing from dbo.dim_vendor — "
                    "check migration 018"
                )
            frequency = session.execute(
                select(DimFrequency).where(DimFrequency.frequency_code == self.FREQUENCY_CODE)
            ).scalar_one_or_none()
            if frequency is None:
                raise RuntimeError(
                    f"Frequency '{self.FREQUENCY_CODE}' missing from dbo.dim_frequency — "
                    "run migration 023_create_dim_frequency.sql"
                )
            vendor_id = vendor.id
            frequency_id = frequency.id

        # 4. Resolve pair_ids, validate via Pydantic.
        # `to_dict("records")` iteration is 10-50× faster than `iterrows()`
        # for the historical-backfill case (years of daily data → hundreds
        # of thousands of rows). Same shape as `FXRatePipeline.transform`.
        observations: list[FXRateCreate] = []
        skipped_unmapped = 0
        skipped_nan_mid = 0
        skipped_invalid = 0
        for row in raw.to_dict("records"):
            key = (row["base_ccy"], row["quote_ccy"])
            pair_id = pair_id_cache.get(key)
            if pair_id is None:
                skipped_unmapped += 1
                continue

            mid_rate_raw = row["mid_rate"]
            if pd.isna(mid_rate_raw):
                skipped_nan_mid += 1
                continue

            try:
                # Controlled-precision Decimal conversion (avoids FP noise tails
                # overflowing DECIMAL(18,8) / DECIMAL(18,10) on the schema).
                mid_rate = Decimal(f"{float(mid_rate_raw):.8f}")
                fwd_points_raw = row["fwd_points"]
                fwd_points = (
                    None if pd.isna(fwd_points_raw)
                    else Decimal(f"{float(fwd_points_raw):.6f}")
                )
                observations.append(
                    FXRateCreate(
                        pair_id=pair_id,
                        vendor_id=vendor_id,
                        frequency_id=frequency_id,
                        obs_ts=row["obs_ts"],
                        obs_date=row["obs_date"],
                        tenor=row["tenor"],
                        mid_rate=mid_rate,
                        fwd_points=fwd_points,
                    )
                )
            except Exception as exc:
                # Skip rows that fail Pydantic validation (e.g. negative
                # mid_rate from a BBG data glitch). Log first few for ops.
                skipped_invalid += 1
                if skipped_invalid <= 5:
                    _log.warning(
                        "transform_skipped_invalid_row",
                        pair=f"{row['base_ccy']}/{row['quote_ccy']}",
                        obs_date=str(row["obs_date"]),
                        tenor=row["tenor"],
                        mid_rate=str(mid_rate_raw),
                        error=str(exc),
                    )

        if skipped_unmapped:
            _log.warning("transform_skipped_unmapped_pairs", count=skipped_unmapped)
        if skipped_nan_mid:
            _log.warning("transform_skipped_nan_mid_rate", count=skipped_nan_mid)
        if skipped_invalid:
            _log.warning("transform_skipped_invalid_rows", count=skipped_invalid)
        _log.info("transform_complete", observations=len(observations))
        return observations

    def load(self, data: list[FXRateCreate]) -> int:
        """Bulk upsert via temp-table MERGE (same path as Citi pipeline)."""
        if not data:
            return 0
        if self._chunk_size:
            count = chunked_bulk_merge(
                self._connector, FX_RATE_SPEC, data, self._chunk_size,
            )
        else:
            with self._connector.session() as session:
                repo = FXRateRepository(session)
                count = repo.bulk_upsert(data)
        _log.info("load_complete", rows_loaded=count)
        return count

    def get_run_context(self) -> dict[str, Any]:
        # The most recent file mtime is the "as-of" date of this snapshot batch
        if self._raw_df is not None and not self._raw_df.empty:
            latest = self._raw_df["obs_date"].max()
            return {"run_date": latest}
        return {}
