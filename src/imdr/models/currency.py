"""Shared currency dimension ORM model mapping to [dbo].[dim_currency]."""
from __future__ import annotations

from sqlalchemy import Boolean, String, UniqueConstraint
from sqlalchemy.dialects.mssql import TINYINT
from sqlalchemy.orm import Mapped, mapped_column

from imdr.models.base import Base


class DimCurrency(Base):
    """Currency dimension — one row per ISO 4217 code (USD, EUR, ...)."""

    __tablename__ = "dim_currency"
    __table_args__ = (
        UniqueConstraint("code", name="uq_dbo_dim_currency_code"),
        {"schema": "dbo"},
    )

    # Override Base.id: currency space is <200 codes, so the table uses TINYINT.
    id: Mapped[int] = mapped_column(TINYINT, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(3), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:
        return f"<DimCurrency {self.code}>"
