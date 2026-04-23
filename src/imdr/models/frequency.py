"""Shared frequency dimension ORM model mapping to [dbo].[dim_frequency].

Cross-domain enum of ingest cadences (TICK, SNAPSHOT, MINUTE, HOURLY, DAILY,
WEEKLY, MONTHLY, QUARTERLY, ANNUAL, EVENT). Fact tables FK to this via
frequency_id to document what cadence each row was produced at.
"""
from __future__ import annotations

from sqlalchemy import Integer, SmallInteger, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from imdr.models.base import Base


class DimFrequency(Base):
    """Frequency dimension — ingest cadence for fact observations."""

    __tablename__ = "dim_frequency"
    __table_args__ = (
        UniqueConstraint("frequency_code", name="uq_dbo_dim_frequency_code"),
        {"schema": "dbo"},
    )

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=True)
    frequency_code: Mapped[str] = mapped_column(String(10), nullable=False)
    display_name: Mapped[str] = mapped_column(String(40), nullable=False)
    typical_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    def __repr__(self) -> str:
        return f"<DimFrequency {self.frequency_code}>"
