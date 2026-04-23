"""Data access layer for equity domain tables.

Session is injected — the repository does NOT own its lifecycle.
"""
from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from imdr.connectors.bulk import MergeSpec, bulk_merge
from imdr.models.equity import EquityDimIndex, EquityFactIndexLevel, EquityFactVix
from imdr.schemas.equity import IndexCreate, IndexLevelCreate, VixCreate

# ── MergeSpec definitions ────────────────────────────────────────────

_INDEX_LEVEL_SPEC = MergeSpec(
    target_table="[equities].[fact_index_level]",
    staging_name="#equity_index_level_staging",
    columns={
        "index_id": "INT",
        "obs_date": "DATE",
        "close_level": "FLOAT",
    },
    natural_key=["index_id", "obs_date"],
    value_columns=["close_level"],
)

_VIX_SPEC = MergeSpec(
    target_table="[equities].[fact_vix]",
    staging_name="#equity_vix_staging",
    columns={
        "ticker": "VARCHAR(10)",
        "obs_date": "DATE",
        "close_level": "FLOAT",
    },
    natural_key=["ticker", "obs_date"],
    value_columns=["close_level"],
)


# ── Dimension repository ─────────────────────────────────────────────


class EquityIndexRepository:
    """Data access layer for [equities].[dim_index]."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_key(self, ticker: str) -> EquityDimIndex | None:
        return self._session.execute(
            select(EquityDimIndex).where(EquityDimIndex.ticker == ticker.upper())
        ).scalar_one_or_none()

    def get_or_create(self, data: IndexCreate) -> EquityDimIndex:
        existing = self.get_by_key(data.ticker)
        if existing:
            return existing
        row = EquityDimIndex(**data.model_dump())
        self._session.add(row)
        self._session.flush()
        return row

    def all(self) -> Sequence[EquityDimIndex]:
        return self._session.scalars(select(EquityDimIndex)).all()

    def bulk_seed_from_universe(self, entries: list[IndexCreate]) -> int:
        """Seed dimension table from universe config. Skips existing rows."""
        count = 0
        for data in entries:
            if not self.get_by_key(data.ticker):
                self._session.add(EquityDimIndex(**data.model_dump()))
                count += 1
        self._session.flush()
        return count


# ── Fact repositories ────────────────────────────────────────────────


class EquityIndexLevelRepository:
    """Data access layer for [equities].[fact_index_level]."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def bulk_upsert(self, items: list[IndexLevelCreate]) -> int:
        return bulk_merge(self._session, _INDEX_LEVEL_SPEC, items)


class EquityVixRepository:
    """Data access layer for [equities].[fact_vix]."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def bulk_upsert(self, items: list[VixCreate]) -> int:
        return bulk_merge(self._session, _VIX_SPEC, items)
