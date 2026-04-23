"""Data access layer for rates swaption skew domain tables.

Session is injected — the repository does NOT own its lifecycle.
"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from imdr.connectors.bulk import MergeSpec, bulk_merge
from imdr.models.currency import DimCurrency
from imdr.models.rates_skew import RatesFactSwaptionSkew, RatesSkewSurface
from imdr.schemas.rates_skew import RatesSkewSurfaceCreate, RatesSwaptionSkewCreate

_SWAPTION_SKEW_SPEC = MergeSpec(
    target_table="[rates].[fact_swaption_skew]",
    staging_name="#rates_swaption_skew_staging",
    columns={
        "surface_id": "INT",
        "vendor_id": "INT",
        "obs_date": "DATE",
        "swap_tenor": "VARCHAR(4)",
        "strike_offset": "INT",
        "vol": "FLOAT",
    },
    natural_key=["surface_id", "obs_date", "swap_tenor", "strike_offset"],
    value_columns=["vol"],
)


class RatesSkewSurfaceRepository:
    """Data access layer for [rates].[dim_skew_surface]."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_key(
        self, ccy: str, option_expiry: str,
    ) -> RatesSkewSurface | None:
        return self._session.execute(
            select(RatesSkewSurface).where(
                RatesSkewSurface.ccy == ccy.upper(),
                RatesSkewSurface.option_expiry == option_expiry.upper(),
            )
        ).scalar_one_or_none()

    def all(self) -> Sequence[RatesSkewSurface]:
        return self._session.scalars(select(RatesSkewSurface)).all()

    def bulk_seed_from_universe(self, entries: list[RatesSkewSurfaceCreate]) -> int:
        """Seed dimension table from parsed data. Skips existing rows.

        Resolves ccy → dbo.dim_currency.id for the FK; caches lookups per call.
        """
        count = 0
        currency_cache: dict[str, int] = {}
        for data in entries:
            existing = self.get_by_key(data.ccy, data.option_expiry)
            if existing:
                continue
            ccy = data.ccy.upper()
            currency_id = currency_cache.get(ccy)
            if currency_id is None:
                currency_id = self._session.execute(
                    select(DimCurrency.id).where(DimCurrency.code == ccy)
                ).scalar_one_or_none()
                if currency_id is None:
                    raise ValueError(
                        f"Currency '{ccy}' not found in dbo.dim_currency — "
                        "add it via a seed migration before loading this surface."
                    )
                currency_cache[ccy] = currency_id
            self._session.add(RatesSkewSurface(
                ccy=ccy,
                option_expiry=data.option_expiry,
                currency_id=currency_id,
            ))
            count += 1
        self._session.flush()
        return count


class RatesSwaptionSkewRepository:
    """Data access layer for [rates].[fact_swaption_skew]."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def bulk_upsert(self, items: list[RatesSwaptionSkewCreate]) -> int:
        """Upsert skew observations via shared temp->MERGE utility."""
        return bulk_merge(self._session, _SWAPTION_SKEW_SPEC, items)

    def count_by_date(self, obs_date: date) -> int:
        """Count observations for a given date."""
        result = self._session.execute(
            select(func.count(RatesFactSwaptionSkew.id)).where(
                RatesFactSwaptionSkew.obs_date == obs_date
            )
        ).scalar_one()
        return result or 0
