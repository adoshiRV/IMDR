"""Shared currency dimension ORM model mapping to [dbo].[dim_currency]."""
from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.mssql import TINYINT
from sqlalchemy.orm import Mapped, mapped_column

from imdr.models.base import Base


class DimCurrency(Base):
    """Currency dimension — one row per code (ISO 4217 + vendor variants).

    Migration 039 added `country_id` (FK -> dim_country) and `variant`:
    - `country_id`: anchors every currency to a country in dbo.dim_country.
      EUR -> EU pseudo, RUB -> RU, metals -> XX pseudo.
    - `variant`: NULL for canonical ISO codes (USD, GBP, CNY, MYR, IDR).
      Set to 'offshore' / 'onshore' / 'bbg_onshore' for variants like CNH,
      CNO, IDO, MYO. Query `variant IS NULL` to get the canonical currency
      for a country.
    """

    __tablename__ = "dim_currency"
    __table_args__ = (
        UniqueConstraint("code", name="uq_dbo_dim_currency_code"),
        {"schema": "dbo"},
    )

    # Override Base.id: currency space is <200 codes, so the table uses TINYINT.
    id: Mapped[int] = mapped_column(TINYINT, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(3), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    country_id: Mapped[int] = mapped_column(
        TINYINT, ForeignKey("dbo.dim_country.id"), nullable=False, index=True,
    )
    variant: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:
        return f"<DimCurrency {self.code}>"
