"""Bloomberg rates snapshot pipeline (IRS + OIS PAR curves).

Reads BBG R-pipeline PAR CSVs from Z:\\ via ``LocalFilesystemAcquirer``,
extracts via ``BloombergCSVRatesExtractor``, and upserts into
``rates.fact_observation`` with ``vendor_id=bloomberg`` +
``frequency_id=SNAPSHOT``.

Each invocation captures whatever the BBG CSVs currently hold and stamps
``ts`` = file mtime (UTC). Runs alongside ``bbg_fx_snapshot`` in the
half-hourly orchestrator (``scripts/imdr_snapshots_bbg.py``).

Idempotent on the (curve, vendor, ts, quote, tenor, frequency) unique
key — re-runs within the same BBG batch window are no-ops.

**HARD RULE — Z:\\BBG\\ is read-only.** No file moves, renames, deletes,
or writes. Only ``glob``, ``stat``, ``read_csv``. Enforced by the
``archive_after_load=False`` setting on ``bbg_rates_snapshot`` and by
``tests/unit/test_vendors/test_bbg_rates_snapshot_no_move.py``.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import structlog
from sqlalchemy import select

from imdr.config.pipeline_config import get_pipeline_config
from imdr.config.settings import Settings
from imdr.connectors.bulk import chunked_bulk_merge
from imdr.connectors.mssql import MSSQLConnector
from imdr.domains.rates.extractors_bbg import (
    BBGRatesSourceFile,
    BloombergCSVRatesExtractor,
    parse_bbg_rates_folder,
)
from imdr.domains.rates.repository import (
    RatesCurveRepository,
    RatesObservationRepository,
    _RATES_OBS_SPEC,
)
from imdr.models.frequency import DimFrequency
from imdr.models.vendor import DimVendor
# Side-effect: load all ORM models so SQLAlchemy can resolve cross-schema FKs
# (rates.dim_curve.country_id → dbo.dim_country.id, etc.)
import imdr.models.country   # noqa: F401
import imdr.models.calendar  # noqa: F401
import imdr.models.fx_vol    # noqa: F401
import imdr.models.fx_rate   # noqa: F401
import imdr.models.fx_ohlc   # noqa: F401
import imdr.models.rates     # noqa: F401
from imdr.pipelines.base import BasePipeline
from imdr.schemas.rates import RatesCurveCreate, RatesObservationCreate

_log = structlog.get_logger("BloombergRatesPipeline")

VENDOR_CODE = "BBG"

# Default root for BBG IRS/OIS trees on Z:\
_DEFAULT_BBG_ROOT = Path(r"Z:\Business\Research\Dashboard\DataSources\BBG_mirror")


# curve_type → dim_curve.instrument mapping (single source of truth).
# Keep aligned with rates.yml `instruments:` keys.
_INSTRUMENT_BY_CURVE_TYPE: dict[str, str] = {
    "rfr":   "ois",          # OIS overnight indices (SOFR, ESTR, ...)
    "ibor":  "swap_libor",   # legacy IBOR fixings (BBSW, EURIBOR, ...)
    "basis": "basis_swap",   # cross-currency basis swaps (BBG BASIS/)
    "ccs":   "xccy_swap",    # cross-currency fixed-vs-float swaps (BBG CCS/)
}


def _build_curve_create(src: BBGRatesSourceFile) -> RatesCurveCreate:
    """Construct a RatesCurveCreate from a BBG source file's metadata.

    BBG curves are seeded with ``citi_prefix='BBG:{folder}'`` to mark them
    as BBG-sourced (not on Citi) while satisfying the schema's NOT NULL.
    """
    instrument = _INSTRUMENT_BY_CURVE_TYPE.get(src.curve_type)
    if instrument is None:
        raise ValueError(
            f"Unknown curve_type {src.curve_type!r} for BBG curve {src.folder!r}; "
            f"valid: {sorted(_INSTRUMENT_BY_CURVE_TYPE)}"
        )
    return RatesCurveCreate(
        ccy=src.ccy,
        curve=src.curve,
        curve_type=src.curve_type,
        curve_status="active",
        instrument=instrument,
        citi_prefix=f"BBG:{src.folder}",
    )


class BloombergRatesPipeline(BasePipeline[pd.DataFrame, list[RatesObservationCreate], int]):
    """ETL pipeline: BBG IRS+OIS PAR CSVs → rates.fact_observation."""

    pipeline_name = "rates.bloomberg_snapshot"
    domain = "rates"

    # Frequency stamp for this pipeline's rows. Overridden by
    # ``BloombergRatesDailyPipeline`` (DAILY). Read inside ``transform`` so
    # subclasses get the right value without monkey-patching the module.
    FREQUENCY_CODE: str = "SNAPSHOT"

    def __init__(
        self,
        files: list[Path],
        connector: MSSQLConnector,
        settings: Settings,
        bbg_root: Path | None = None,
        chunk_size: int | None = None,
    ) -> None:
        super().__init__(connector)
        self._settings = settings
        self._files = files
        self._bbg_root = bbg_root or _DEFAULT_BBG_ROOT
        self._chunk_size = chunk_size
        # Reuse the Citi rate config — same target table, same thresholds
        try:
            self._config = get_pipeline_config("rates.historical")
        except Exception:
            self._config = None
        self._raw_df: pd.DataFrame | None = None
        self._sources: list[BBGRatesSourceFile] = []
        self._extraction_errors: list[dict] = []

    # ── Pipeline phases ─────────────────────────────────────────────

    def _build_sources_from_paths(self) -> list[BBGRatesSourceFile]:
        """Reconstruct ``BBGRatesSourceFile``s from the acquired Paths.

        Layout assumed: ``<bbg_root>/{KIND}/{folder}/PAR/{KIND}_PAR_*.csv``
        where KIND ∈ {IRS, OIS, BASIS, CCS}. Shared by snapshot and daily
        pipelines so neither has to reimplement the path → metadata walk.
        """
        from datetime import datetime, timezone

        srcs: list[BBGRatesSourceFile] = []
        for path in self._files:
            try:
                # path = .../BBG_mirror/{KIND}/{folder}/PAR/{KIND}_PAR_{folder}.csv
                folder = path.parent.parent.name
                kind = path.parent.parent.parent.name
                if kind not in ("IRS", "OIS", "BASIS", "CCS"):
                    _log.warning("bbg_rates_unexpected_path", path=str(path))
                    continue
                ccy, curve, curve_type = parse_bbg_rates_folder(kind, folder)
                mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
                srcs.append(BBGRatesSourceFile(
                    path=path, folder=folder, kind=kind,
                    ccy=ccy, curve=curve, curve_type=curve_type,
                    obs_ts=mtime,
                ))
            except Exception as e:
                _log.warning("bbg_rates_path_parse_failed",
                             path=str(path), error=str(e))
        return srcs

    def _extractor(self) -> BloombergCSVRatesExtractor:
        """Build the CSV extractor. Daily subclass overrides to pick mode."""
        return BloombergCSVRatesExtractor()

    def extract(self) -> pd.DataFrame:
        """Walk Paths → sources, run the extractor, stash debug state."""
        srcs = self._build_sources_from_paths()
        self._sources = srcs

        extractor = self._extractor()
        df = extractor.extract(srcs)
        self._extraction_errors = extractor.errors
        self._raw_df = df

        _log.info(
            "extract_complete",
            files=len(srcs),
            rows=len(df),
            extraction_errors=len(self._extraction_errors),
        )
        return df

    def transform(self, raw: pd.DataFrame) -> list[RatesObservationCreate]:
        """Auto-seed dim_curve, resolve FKs, validate via Pydantic."""
        if not self._sources:
            return []

        # 1. Auto-seed dim_curve from discovered BBG curves (idempotent).
        #    Each BBG curve becomes a (ccy, curve) row with citi_prefix='BBG:{folder}'.
        curves_to_seed = [_build_curve_create(src) for src in self._sources]
        # Dedupe by (ccy, curve) — multiple files could resolve to the same curve
        seen: set[tuple[str, str]] = set()
        unique_curves: list[RatesCurveCreate] = []
        for c in curves_to_seed:
            key = (c.ccy, c.curve)
            if key not in seen:
                seen.add(key)
                unique_curves.append(c)

        with self._connector.session() as session:
            curve_repo = RatesCurveRepository(session)
            inserted = curve_repo.bulk_seed_from_universe(unique_curves)
            if inserted:
                _log.info("dim_curve_seeded_bbg", new_curves=inserted,
                          total=len(unique_curves))

            # 2. Build curve_id cache (sees freshly seeded rows)
            curve_id_cache: dict[tuple[str, str], int] = {}
            for entry in curve_repo.all():
                curve_id_cache[(entry.ccy, entry.curve)] = entry.id

            # 3. Resolve vendor_id + frequency_id (fail loudly)
            vendor = session.execute(
                select(DimVendor).where(DimVendor.vendor_code == VENDOR_CODE)
            ).scalar_one_or_none()
            if vendor is None:
                raise RuntimeError(
                    f"Vendor '{VENDOR_CODE}' missing from dbo.dim_vendor"
                )
            frequency = session.execute(
                select(DimFrequency).where(DimFrequency.frequency_code == self.FREQUENCY_CODE)
            ).scalar_one_or_none()
            if frequency is None:
                raise RuntimeError(
                    f"Frequency '{self.FREQUENCY_CODE}' missing — run migration 023"
                )
            vendor_id = vendor.id
            frequency_id = frequency.id

        if raw.empty:
            return []

        # 4. Resolve curve_ids, validate via Pydantic
        observations: list[RatesObservationCreate] = []
        skipped_unmapped = 0
        skipped_invalid = 0
        for _, row in raw.iterrows():
            key = (row["ccy"], row["curve"])
            curve_id = curve_id_cache.get(key)
            if curve_id is None:
                skipped_unmapped += 1
                continue

            try:
                observations.append(RatesObservationCreate(
                    curve_id=curve_id,
                    vendor_id=vendor_id,
                    ts=row["ts"],
                    quote=row["quote"],
                    tenor=row["tenor"],
                    value=float(row["value"]),
                    frequency_id=frequency_id,
                ))
            except Exception as exc:
                skipped_invalid += 1
                if skipped_invalid <= 5:
                    _log.warning(
                        "transform_skipped_invalid_row",
                        ccy=row.get("ccy"), curve=row.get("curve"),
                        tenor=row.get("tenor"), value=row.get("value"),
                        error=str(exc),
                    )

        if skipped_unmapped:
            _log.warning("transform_skipped_unmapped_curves", count=skipped_unmapped)
        if skipped_invalid:
            _log.warning("transform_skipped_invalid_rows", count=skipped_invalid)
        _log.info("transform_complete", observations=len(observations))
        return observations

    def load(self, data: list[RatesObservationCreate]) -> int:
        """Bulk upsert via temp-table MERGE (same path as Citi pipeline)."""
        if not data:
            return 0
        if self._chunk_size:
            count = chunked_bulk_merge(
                self._connector, _RATES_OBS_SPEC, data, self._chunk_size,
            )
        else:
            with self._connector.session() as session:
                repo = RatesObservationRepository(session)
                count = repo.bulk_upsert(data)
        _log.info("load_complete", rows_loaded=count)
        return count

    def get_run_context(self) -> dict[str, Any]:
        """Latest source mtime is the as-of moment of this snapshot."""
        if self._sources:
            latest = max((s.obs_ts for s in self._sources), default=None)
            if latest is not None:
                return {"run_date": latest.date()}
        return {}
