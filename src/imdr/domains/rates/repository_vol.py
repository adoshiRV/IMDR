"""Data access layer for rates swaption vol domain tables.

Session is injected — the repository does NOT own its lifecycle.
"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from imdr.connectors.bulk import MergeSpec, bulk_merge
from imdr.models.rates_vol import RatesFactSwaptionVol, RatesVolSurface
from imdr.schemas.rates_vol import RatesSwaptionVolCreate, RatesVolSurfaceCreate

_SWAPTION_VOL_SPEC = MergeSpec(
    target_table="[rates].[fact_swaption_vol]",
    staging_name="#rates_swaption_vol_staging",
    columns={
        "surface_id": "INT",
        "obs_date": "DATE",
        "option_expiry": "VARCHAR(4)",
        "swap_tenor": "VARCHAR(4)",
        "value": "FLOAT",
    },
    natural_key=["surface_id", "obs_date", "option_expiry", "swap_tenor"],
    value_columns=["value"],
)


class RatesVolSurfaceRepository:
    """Data access layer for [rates].[dim_vol_surface]."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_key(
        self, ccy: str, data_type: str, quote_type: str = "",
        vol_window: str = "", freq: str = "",
    ) -> RatesVolSurface | None:
        return self._session.execute(
            select(RatesVolSurface).where(
                RatesVolSurface.ccy == ccy.upper(),
                RatesVolSurface.data_type == data_type.upper(),
                RatesVolSurface.quote_type == quote_type,
                RatesVolSurface.vol_window == vol_window,
                RatesVolSurface.freq == freq,
            )
        ).scalar_one_or_none()

    def all(self) -> Sequence[RatesVolSurface]:
        return self._session.scalars(select(RatesVolSurface)).all()

    def bulk_seed_from_universe(self, entries: list[RatesVolSurfaceCreate]) -> int:
        """Seed dimension table from universe config. Skips existing rows."""
        count = 0
        for data in entries:
            existing = self.get_by_key(
                data.ccy, data.data_type, data.quote_type, data.vol_window, data.freq
            )
            if not existing:
                self._session.add(RatesVolSurface(**data.model_dump()))
                count += 1
        self._session.flush()
        return count


class RatesSwaptionVolRepository:
    """Data access layer for [rates].[fact_swaption_vol]."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def bulk_upsert(self, items: list[RatesSwaptionVolCreate]) -> int:
        """Upsert vol observations via shared temp->MERGE utility."""
        return bulk_merge(self._session, _SWAPTION_VOL_SPEC, items)

    def count_by_date(self, obs_date: date) -> int:
        """Count observations for a given date."""
        result = self._session.execute(
            select(func.count(RatesFactSwaptionVol.id)).where(
                RatesFactSwaptionVol.obs_date == obs_date
            )
        ).scalar_one()
        return result or 0
