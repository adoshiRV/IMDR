"""Data access layer for commodities domain tables.

Session is injected — the repository does NOT own its lifecycle.
"""
from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from imdr.connectors.bulk import MergeSpec, bulk_merge
from imdr.models.commodities import (
    CmdtyCommodity,
    CmdtyDimEIASeries,
    CmdtyFactEIA,
    CmdtyFactImpliedVol,
    CmdtyFactSpot,
)
from imdr.schemas.commodities import (
    CommodityCreate,
    EIACreate,
    EIASeriesCreate,
    ImpliedVolCreate,
    SpotCreate,
)

# ── MergeSpec definitions ────────────────────────────────────────────

_SPOT_SPEC = MergeSpec(
    target_table="[commodities].[fact_spot]",
    staging_name="#cmdty_spot_staging",
    columns={
        "commodity_id": "INT",
        "obs_date": "DATE",
        "price": "FLOAT",
    },
    natural_key=["commodity_id", "obs_date"],
    value_columns=["price"],
)

_EIA_SPEC = MergeSpec(
    target_table="[commodities].[fact_eia]",
    staging_name="#cmdty_eia_staging",
    columns={
        "eia_series_id": "INT",
        "obs_date": "DATE",
        "stat_value": "FLOAT",
    },
    natural_key=["eia_series_id", "obs_date"],
    value_columns=["stat_value"],
)

_VOL_SPEC = MergeSpec(
    target_table="[commodities].[fact_implied_vol]",
    staging_name="#cmdty_implied_vol_staging",
    columns={
        "commodity_id": "INT",
        "obs_date": "DATE",
        "strike": "VARCHAR(15)",
        "tenor": "VARCHAR(15)",
        "vol": "FLOAT",
    },
    natural_key=["commodity_id", "obs_date", "strike", "tenor"],
    value_columns=["vol"],
)


# ── Dimension repositories ───────────────────────────────────────────


class CmdtyCommodityRepository:
    """Data access layer for [commodities].[dim_commodity]."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_key(self, symbol: str) -> CmdtyCommodity | None:
        return self._session.execute(
            select(CmdtyCommodity).where(CmdtyCommodity.symbol == symbol.upper())
        ).scalar_one_or_none()

    def get_or_create(self, data: CommodityCreate) -> CmdtyCommodity:
        existing = self.get_by_key(data.symbol)
        if existing:
            return existing
        row = CmdtyCommodity(**data.model_dump())
        self._session.add(row)
        self._session.flush()
        return row

    def all(self) -> Sequence[CmdtyCommodity]:
        return self._session.scalars(select(CmdtyCommodity)).all()

    def bulk_seed_from_universe(self, entries: list[CommodityCreate]) -> int:
        """Seed dimension table from universe config. Skips existing rows."""
        count = 0
        for data in entries:
            if not self.get_by_key(data.symbol):
                self._session.add(CmdtyCommodity(**data.model_dump()))
                count += 1
        self._session.flush()
        return count


class CmdtyEIASeriesRepository:
    """Data access layer for [commodities].[dim_eia_series]."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_key(self, series_name: str, region: str) -> CmdtyDimEIASeries | None:
        return self._session.execute(
            select(CmdtyDimEIASeries).where(
                CmdtyDimEIASeries.series_name == series_name.upper(),
                CmdtyDimEIASeries.region == region.upper(),
            )
        ).scalar_one_or_none()

    def get_or_create(self, data: EIASeriesCreate) -> CmdtyDimEIASeries:
        existing = self.get_by_key(data.series_name, data.region)
        if existing:
            return existing
        row = CmdtyDimEIASeries(**data.model_dump())
        self._session.add(row)
        self._session.flush()
        return row

    def all(self) -> Sequence[CmdtyDimEIASeries]:
        return self._session.scalars(select(CmdtyDimEIASeries)).all()

    def bulk_seed_from_universe(self, entries: list[EIASeriesCreate]) -> int:
        """Seed dimension table from universe config. Skips existing rows."""
        count = 0
        for data in entries:
            if not self.get_by_key(data.series_name, data.region):
                self._session.add(CmdtyDimEIASeries(**data.model_dump()))
                count += 1
        self._session.flush()
        return count


# ── Fact repositories ────────────────────────────────────────────────


class CmdtySpotRepository:
    """Data access layer for [commodities].[fact_spot]."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def bulk_upsert(self, items: list[SpotCreate]) -> int:
        return bulk_merge(self._session, _SPOT_SPEC, items)


class CmdtyEIARepository:
    """Data access layer for [commodities].[fact_eia]."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def bulk_upsert(self, items: list[EIACreate]) -> int:
        return bulk_merge(self._session, _EIA_SPEC, items)


class CmdtyImpliedVolRepository:
    """Data access layer for [commodities].[fact_implied_vol]."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def bulk_upsert(self, items: list[ImpliedVolCreate]) -> int:
        return bulk_merge(self._session, _VOL_SPEC, items)
