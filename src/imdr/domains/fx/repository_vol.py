"""Data access layer for FX vol domain tables.

Session is injected — the repository does NOT own its lifecycle.
"""
from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from imdr.connectors.bulk import MergeSpec, bulk_merge
from imdr.models.fx_vol import FXCurrencyPair
from imdr.schemas.fx_vol import FXCurrencyPairCreate, FXVolCreate

FX_VOL_SPEC = MergeSpec(
    target_table="[fx].[fact_vol]",
    staging_name="#fx_vol_staging",
    columns={
        "pair_id": "INT",
        "obs_date": "DATE",
        "strike": "VARCHAR(15)",
        "tenor": "VARCHAR(5)",
        "vol_type": "VARCHAR(10)",
        "value": "FLOAT",
    },
    natural_key=["pair_id", "obs_date", "strike", "tenor", "vol_type"],
    value_columns=["value"],
)


class FXCurrencyPairRepository:
    """Data access layer for [fx].[dim_currency_pair]."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_key(self, base_ccy: str, quote_ccy: str) -> FXCurrencyPair | None:
        return self._session.execute(
            select(FXCurrencyPair).where(
                FXCurrencyPair.base_ccy == base_ccy.upper(),
                FXCurrencyPair.quote_ccy == quote_ccy.upper(),
            )
        ).scalar_one_or_none()

    def all(self) -> Sequence[FXCurrencyPair]:
        return self._session.scalars(select(FXCurrencyPair)).all()

    def bulk_seed_from_universe(self, pairs: list[FXCurrencyPairCreate]) -> int:
        """Seed dimension table from universe config. Skips existing rows."""
        count = 0
        for data in pairs:
            existing = self.get_by_key(data.base_ccy, data.quote_ccy)
            if not existing:
                self._session.add(FXCurrencyPair(**data.model_dump()))
                count += 1
        self._session.flush()
        return count


class FXVolRepository:
    """Data access layer for [fx].[fact_vol]."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def bulk_upsert(self, items: list[FXVolCreate]) -> int:
        """Upsert vol observations via shared temp→MERGE utility."""
        return bulk_merge(self._session, FX_VOL_SPEC, items)
