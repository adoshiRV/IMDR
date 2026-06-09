"""Central bank policy rates pipeline — RATES.BENCH_RATES.* → SQL + parquet.

10 flat tags, ~8 rows/day. Single consolidated module: tag parser, repository,
parquet store, and pipeline class.
"""
from __future__ import annotations

import json
import os
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from imdr.config.pipeline_config import get_pipeline_config
from imdr.config.settings import Settings
from imdr.connectors.bulk import MergeSpec, bulk_merge
from imdr.connectors.citi_helpers import (
    TagQuotaExceeded,
    citi_response_to_rows,
    fetch_and_parse_batched,
    parse_x_to_ts_utc,
)
from imdr.connectors.citi_quota import TagQuotaTracker
from imdr.connectors.citi_velocity import CitiVelocityClient
from imdr.connectors.mssql import MSSQLConnector
from imdr.healthchecks.base import HealthCheck
from imdr.healthchecks.checks import (
    DuplicateCheck,
    FreshnessCheck,
    NullCheck,
    RowCountCheck,
    ValueRangeCheck,
)
from imdr.models.country import DimCountry
from imdr.models.rates_bench import RatesDimCentralBank, RatesFactBenchRates
from imdr.models.vendor import DimVendor
from imdr.pipelines.base import BasePipeline
from imdr.schemas.rates_bench import BenchRateCreate, CentralBankCreate
from imdr.universe.rates import RatesUniverse, get_rates_universe

_log = structlog.get_logger("BenchRatesPipeline")

COLUMNS = ["ts", "cb_code", "value"]

PARQUET_ROOT = Path("data/parquet/rates/bench_rates")
PARQUET_NATURAL_KEY = ["cb_code", "obs_date"]


# ── Tag Parser ───────────────────────────────────────────────────


def citi_bench_tag_to_internal(tag: str) -> dict[str, str] | None:
    """Parse RATES.BENCH_RATES.ECB → {"cb_code": "ECB"}."""
    parts = tag.split(".")
    if len(parts) != 3 or parts[0] != "RATES" or parts[1] != "BENCH_RATES":
        return None
    cb_code = parts[2]
    if not cb_code:
        return None
    return {"cb_code": cb_code}


def citi_bench_response_to_df(resp: dict) -> pd.DataFrame:
    """Convert Citi Historical response → DataFrame with [ts, cb_code, value]."""
    rows = citi_response_to_rows(
        resp,
        tag_parser=citi_bench_tag_to_internal,
        parse_x=parse_x_to_ts_utc,
    )
    return pd.DataFrame(rows, columns=COLUMNS) if rows else pd.DataFrame(columns=COLUMNS)


# ── Repository ───────────────────────────────────────────────────

_BENCH_RATES_SPEC = MergeSpec(
    target_table="[rates].[fact_bench_rates]",
    staging_name="#rates_bench_rates_staging",
    columns={
        "cb_id": "INT",
        "vendor_id": "INT",
        "obs_date": "DATE",
        "rate": "FLOAT",
    },
    natural_key=["cb_id", "obs_date"],
    value_columns=["rate", "vendor_id"],
)


class CentralBankRepository:
    """Data access for [rates].[dim_central_bank]."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_code(self, cb_code: str) -> RatesDimCentralBank | None:
        return self._session.execute(
            select(RatesDimCentralBank).where(
                RatesDimCentralBank.cb_code == cb_code.upper()
            )
        ).scalar_one_or_none()

    def all(self) -> Sequence[RatesDimCentralBank]:
        return self._session.scalars(select(RatesDimCentralBank)).all()

    def bulk_seed_from_universe(self, entries: list[CentralBankCreate]) -> int:
        """Seed dimension table from universe config. Skips existing rows."""
        country_id_by_code = {
            c.country_code: c.id
            for c in self._session.scalars(select(DimCountry)).all()
        }
        count = 0
        for data in entries:
            if not self.get_by_code(data.cb_code):
                payload = data.model_dump()
                payload["country_id"] = country_id_by_code[payload.pop("country_code")]
                self._session.add(RatesDimCentralBank(**payload))
                count += 1
        self._session.flush()
        return count


class BenchRatesRepository:
    """Data access for [rates].[fact_bench_rates]."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def bulk_upsert(self, items: list[BenchRateCreate]) -> int:
        return bulk_merge(self._session, _BENCH_RATES_SPEC, items)


# ── Parquet Store ────────────────────────────────────────────────


def parquet_write(
    df: pd.DataFrame,
    data_root: Path | None = None,
    manifest: dict[str, Any] | None = None,
) -> list[Path]:
    """Write bench rates DataFrame to month-partitioned parquet."""
    root = data_root or PARQUET_ROOT
    if df.empty:
        return []

    written: list[Path] = []
    df = df.copy()
    df["obs_date"] = pd.to_datetime(df["ts"]).dt.date
    df["_month"] = pd.to_datetime(df["ts"]).dt.strftime("%Y-%m")

    for month, group in df.groupby("_month"):
        root.mkdir(parents=True, exist_ok=True)
        target = root / f"{month}.parquet"
        tmp = root / f"{month}.tmp.parquet"

        write_df = group[["obs_date", "cb_code", "value"]].copy()

        if target.exists():
            existing = pd.read_parquet(target)
            _log.info("parquet_merge_existing", path=str(target), existing_rows=len(existing))
            write_df = pd.concat([existing, write_df], ignore_index=True)

        before_dedup = len(write_df)
        write_df = (
            write_df.sort_values(PARQUET_NATURAL_KEY)
            .drop_duplicates(subset=PARQUET_NATURAL_KEY, keep="last")
            .reset_index(drop=True)
        )
        if before_dedup != len(write_df):
            _log.info("parquet_dedup", before=before_dedup, after=len(write_df))

        try:
            write_df.to_parquet(tmp, index=False, engine="pyarrow")
            os.replace(str(tmp), str(target))
        except Exception:
            if tmp.exists():
                tmp.unlink()
            raise
        written.append(target)
        _log.info("parquet_written", path=str(target), rows=len(write_df))

    if manifest:
        for month, _ in df.groupby("_month"):
            try:
                manifest_path = root / f"{month}_manifest.json"
                manifest_data = {
                    **manifest,
                    "month": month,
                    "write_ts": datetime.now(timezone.utc).isoformat(),
                }
                with open(manifest_path, "w", encoding="utf-8") as f:
                    json.dump(manifest_data, f, indent=2, default=str)
            except Exception:
                _log.warning("manifest_write_failed", month=month, exc_info=True)

    return written


# ── Pipeline ─────────────────────────────────────────────────────


class BenchRatesPipeline(BasePipeline[pd.DataFrame, list[BenchRateCreate], int]):
    """ETL pipeline: Citi Velocity BENCH_RATES → SQL Server + parquet."""

    pipeline_name = "rates.bench_rates"
    domain = "rates"

    def __init__(
        self,
        connector: MSSQLConnector,
        settings: Settings,
        universe: RatesUniverse | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> None:
        super().__init__(connector)
        self._settings = settings
        self._universe = universe or get_rates_universe()
        self._config = get_pipeline_config(self.pipeline_name)
        self._start = start or datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        self._end = end or self._start.replace(hour=23, minute=59)
        self._raw_df: pd.DataFrame | None = None
        self._extraction_errors: list[dict] = []
        self._quota_usage: int | None = None

    def extract(self) -> pd.DataFrame:
        tags = self._universe.bench_rates_tags()
        _log.info("extract_start", n_tags=len(tags))

        tracker = TagQuotaTracker(
            quota_limit=self._settings.citi_tag_quota_limit,
            tracker_path=self._settings.citi_tag_quota_file or None,
        )
        tracker.check_budget(len(tags), "rates.bench_rates")

        with CitiVelocityClient(self._settings) as client:
            try:
                df = fetch_and_parse_batched(
                    client,
                    tags,
                    self._start,
                    self._end,
                    "DAILY",
                    self._settings.citi_batch_size,
                    self._settings.citi_rate_limit_sec,
                    response_parser=citi_bench_response_to_df,
                    quota_tracker=tracker,
                    pipeline_name="rates.bench_rates",
                )
            except TagQuotaExceeded:
                raise
            except Exception as e:
                self._extraction_errors.append({"product": "BENCH_RATES", "error": str(e)})
                _log.exception("bench_rates_fetch_failed")
                df = pd.DataFrame(columns=COLUMNS)

        self._quota_usage = tracker.current_usage()
        self._raw_df = df
        _log.info("extract_complete", rows=len(df))
        return df

    def transform(self, raw: pd.DataFrame) -> list[BenchRateCreate]:
        if raw.empty:
            return []

        with self._connector.session() as session:
            # 1. Auto-seed dim_central_bank
            cb_repo = CentralBankRepository(session)
            entries = [
                CentralBankCreate(
                    cb_code=e.cb_code,
                    display_name=e.display_name,
                    currency=e.currency,
                    country_code=e.country_code,
                    citi_tag=e.citi_tag,
                )
                for e in self._universe.bench_rates_entries()
            ]
            inserted = cb_repo.bulk_seed_from_universe(entries)
            if inserted:
                _log.info("dim_central_bank_seeded", new_rows=inserted)

            # 2. Build cb_code → cb_id cache
            cb_id_cache: dict[str, int] = {
                cb.cb_code: cb.id for cb in cb_repo.all()
            }

            # 3. Resolve vendor_id for Citi Velocity
            vendor = session.execute(
                select(DimVendor).where(DimVendor.vendor_code == "citi_velocity")
            ).scalar_one_or_none()
            if vendor is None:
                raise RuntimeError(
                    "Vendor 'citi_velocity' not found in dbo.dim_vendor. "
                    "Run migrations/018_create_dim_vendor.sql to seed vendor table."
                )
            vendor_id = vendor.id

        # 4. Build BenchRateCreate list
        observations: list[BenchRateCreate] = []
        skipped = 0
        for _, row in raw.iterrows():
            cb_code = row["cb_code"]
            cb_id = cb_id_cache.get(cb_code)
            if cb_id is None:
                skipped += 1
                continue
            observations.append(
                BenchRateCreate(
                    cb_id=cb_id,
                    vendor_id=vendor_id,
                    obs_date=row["ts"].date() if hasattr(row["ts"], "date") else row["ts"],
                    rate=row["value"],
                )
            )

        if skipped:
            _log.warning("transform_skipped_unknown_cb", count=skipped)

        _log.info("transform_complete", observations=len(observations))
        return observations

    def load(self, data: list[BenchRateCreate]) -> int:
        if not data:
            return 0
        with self._connector.session() as session:
            repo = BenchRatesRepository(session)
            count = repo.bulk_upsert(data)
        _log.info("load_complete", rows_loaded=count)
        return count

    def post_load(self, result: int, data: list[BenchRateCreate]) -> None:
        if self._raw_df is None or self._raw_df.empty:
            return
        manifest = {
            "source": "citi_velocity_historical",
            "range": [str(self._start.date()), str(self._end.date())],
            "rows_loaded": result,
        }
        written = parquet_write(self._raw_df, manifest=manifest)
        _log.info("parquet_archive_complete", files_written=len(written))

    def get_health_checks(self) -> list[HealthCheck]:
        cfg = self._config.health_checks
        checks: list[HealthCheck] = [
            RowCountCheck(RatesFactBenchRates, self._config.date_column, cfg.row_count_min),
            NullCheck(RatesFactBenchRates, self._config.required_columns, self._config.date_column),
            DuplicateCheck(RatesFactBenchRates, self._config.unique_columns, self._config.date_column),
            FreshnessCheck(RatesFactBenchRates, "created_at", cfg.max_staleness_hours),
        ]
        for col_name, vr in cfg.value_ranges.items():
            checks.append(
                ValueRangeCheck(
                    RatesFactBenchRates, col_name, vr.min, vr.max, self._config.date_column
                )
            )
        return checks

    def get_run_context(self) -> dict[str, Any]:
        return {"run_date": self._start.date()}
