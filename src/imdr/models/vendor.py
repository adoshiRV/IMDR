"""Shared vendor dimension ORM model mapping to [dbo].[dim_vendor]."""
from __future__ import annotations

from sqlalchemy import Boolean, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from imdr.models.base import Base


class DimVendor(Base):
    """Vendor dimension — one row per data source (Citi, Barclays, etc.)."""

    __tablename__ = "dim_vendor"
    __table_args__ = (
        UniqueConstraint("vendor_code", name="uq_dbo_dim_vendor_code"),
        {"schema": "dbo"},
    )

    vendor_code: Mapped[str] = mapped_column(String(30), nullable=False)
    display_name: Mapped[str] = mapped_column(String(50), nullable=False)
    vendor_type: Mapped[str] = mapped_column(String(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:
        return f"<DimVendor {self.vendor_code} ({self.vendor_type})>"
