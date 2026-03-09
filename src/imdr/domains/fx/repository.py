from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from imdr.models.fx import FXSpotRate
from imdr.schemas.fx import FXSpotRateCreate


class FXRepository:
    """Data access layer for FX spot rates.

    The session is injected — the repository does NOT own its lifecycle.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, rate_id: int) -> FXSpotRate | None:
        return self._session.get(FXSpotRate, rate_id)

    def get_rates(
        self,
        base_currency: str | None = None,
        quote_currency: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> Sequence[FXSpotRate]:
        stmt = select(FXSpotRate)
        conditions = []
        if base_currency:
            conditions.append(FXSpotRate.base_currency == base_currency.upper())
        if quote_currency:
            conditions.append(FXSpotRate.quote_currency == quote_currency.upper())
        if start_date:
            conditions.append(FXSpotRate.rate_date >= start_date)
        if end_date:
            conditions.append(FXSpotRate.rate_date <= end_date)
        if conditions:
            stmt = stmt.where(and_(*conditions))
        stmt = stmt.order_by(FXSpotRate.rate_date.desc())
        return self._session.scalars(stmt).all()

    def create(self, data: FXSpotRateCreate) -> FXSpotRate:
        rate = FXSpotRate(**data.model_dump())
        self._session.add(rate)
        self._session.flush()
        return rate

    def bulk_create(self, items: list[FXSpotRateCreate]) -> list[FXSpotRate]:
        rates = [FXSpotRate(**d.model_dump()) for d in items]
        self._session.add_all(rates)
        self._session.flush()
        return rates

    def upsert(self, data: FXSpotRateCreate) -> None:
        """Insert or update based on the unique constraint (MSSQL-safe)."""
        existing = self._session.execute(
            select(FXSpotRate).where(
                FXSpotRate.base_currency == data.base_currency,
                FXSpotRate.quote_currency == data.quote_currency,
                FXSpotRate.rate_date == data.rate_date,
            )
        ).scalar_one_or_none()

        if existing:
            for key, value in data.model_dump(exclude_unset=True).items():
                setattr(existing, key, value)
        else:
            self._session.add(FXSpotRate(**data.model_dump()))
        self._session.flush()

    def delete(self, rate_id: int) -> bool:
        rate = self.get_by_id(rate_id)
        if rate is None:
            return False
        self._session.delete(rate)
        self._session.flush()
        return True
