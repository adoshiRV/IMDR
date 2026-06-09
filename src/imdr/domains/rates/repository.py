"""Data access layer for rates domain tables.

Session is injected — the repository does NOT own its lifecycle.
"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from imdr.connectors.bulk import MergeSpec, bulk_merge
# Importing DimCountry + DimCurrency registers them with SQLAlchemy so the
# rates.dim_curve.country_id FK can be resolved at flush time (post-migration
# 044). Without this import, seeding new curves fails with NoReferencedTable.
from imdr.models.country import DimCountry  # noqa: F401
from imdr.models.currency import DimCurrency
from imdr.models.rates import RatesCurve, RatesObservation
from imdr.schemas.rates import RatesCurveCreate, RatesObservationCreate

_RATES_OBS_SPEC = MergeSpec(
    target_table="[rates].[fact_observation]",
    staging_name="#rates_staging",
    columns={
        "curve_id": "INT",
        "vendor_id": "INT",
        "ts": "DATETIMEOFFSET",
        "quote": "VARCHAR(10)",
        "tenor": "VARCHAR(30)",
        "value": "FLOAT",
        "frequency_id": "TINYINT",
    },
    natural_key=["curve_id", "vendor_id", "ts", "quote", "tenor", "frequency_id"],
    value_columns=["value"],
)


class RatesCurveRepository:
    """Data access layer for [rates].[dim_curve]."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, curve_id: int) -> RatesCurve | None:
        return self._session.get(RatesCurve, curve_id)

    def get_by_key(self, ccy: str, curve: str) -> RatesCurve | None:
        return self._session.execute(
            select(RatesCurve).where(
                RatesCurve.ccy == ccy.upper(),
                RatesCurve.curve == curve.upper(),
            )
        ).scalar_one_or_none()

    def get_or_create(self, data: RatesCurveCreate) -> RatesCurve:
        """Get existing curve or create new one."""
        existing = self.get_by_key(data.ccy, data.curve)
        if existing:
            return existing
        row = RatesCurve(**data.model_dump())
        self._session.add(row)
        self._session.flush()
        return row

    def all(self) -> Sequence[RatesCurve]:
        return self._session.scalars(select(RatesCurve)).all()

    def bulk_seed_from_universe(self, curves: list[RatesCurveCreate]) -> int:
        """Seed dimension table from universe config. Skips existing rows.

        Resolves ``country_id`` (NOT NULL FK added in migration 044) from
        ``ccy`` via ``dbo.dim_currency.country_id`` so new YAML entries can
        be auto-seeded without a per-curve migration.
        """
        # Build ccy -> country_id lookup once per call.
        country_id_by_ccy = {
            c.code: c.country_id
            for c in self._session.scalars(select(DimCurrency)).all()
        }
        count = 0
        unresolved: list[str] = []
        for data in curves:
            existing = self.get_by_key(data.ccy, data.curve)
            if existing:
                continue
            country_id = country_id_by_ccy.get(data.ccy)
            if country_id is None:
                unresolved.append(data.ccy)
                continue
            payload = data.model_dump()
            payload["country_id"] = country_id
            self._session.add(RatesCurve(**payload))
            count += 1
        self._session.flush()
        if unresolved:
            raise RuntimeError(
                "Cannot seed rates.dim_curve — no dbo.dim_currency row for: "
                f"{sorted(set(unresolved))}. Add the ccy to dim_currency first."
            )
        return count


class RatesObservationRepository:
    """Data access layer for [rates].[fact_observation]."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert(self, data: RatesObservationCreate) -> None:
        """Insert or update based on (curve_id, vendor_id, ts, quote, tenor, frequency_id)."""
        existing = self._session.execute(
            select(RatesObservation).where(
                RatesObservation.curve_id == data.curve_id,
                RatesObservation.vendor_id == data.vendor_id,
                RatesObservation.ts == data.ts,
                RatesObservation.quote == data.quote,
                RatesObservation.tenor == data.tenor,
                RatesObservation.frequency_id == data.frequency_id,
            )
        ).scalar_one_or_none()

        if existing:
            existing.value = data.value
        else:
            self._session.add(RatesObservation(**data.model_dump()))
        self._session.flush()

    def bulk_upsert(self, items: list[RatesObservationCreate]) -> int:
        """Upsert observations via shared temp→MERGE utility."""
        return bulk_merge(self._session, _RATES_OBS_SPEC, items)

    def count_by_date(self, ts: datetime) -> int:
        """Count observations for a given timestamp."""
        result = self._session.execute(
            select(func.count(RatesObservation.id)).where(
                RatesObservation.ts == ts
            )
        ).scalar_one()
        return result or 0

    def count_by_curve(self, curve_id: int) -> int:
        result = self._session.execute(
            select(func.count(RatesObservation.id)).where(
                RatesObservation.curve_id == curve_id
            )
        ).scalar_one()
        return result or 0
