"""Shared country dimension ORM model mapping to [dbo].[dim_country].

Country is the cross-domain anchor: currencies, calendars, and (eventually)
fact tables FK to dim_country.id. Created by migration 037 (with remediation
38 — see plan), folds calendar.dim_market into dbo namespace with explicit
country semantics and ISO-3 interop. See
C:\\Users\\adoshi\\.claude\\plans\\okay-lets-do-that-validated-puzzle.md
for the full design.
"""
from __future__ import annotations

from sqlalchemy import Boolean, CheckConstraint, String, UniqueConstraint
from sqlalchemy.dialects.mssql import TINYINT
from sqlalchemy.orm import Mapped, mapped_column

from imdr.models.base import Base


class DimCountry(Base):
    """Country dimension — the anchor table for currencies and calendars.

    52 rows: 50 real markets (preserved surrogate ids from calendar.dim_market),
    plus 3 pseudo-countries (EU, WW, XX). Pseudo rows have iso_alpha3=NULL and
    NULL operational columns; a CHECK constraint enforces the pseudo invariant.

    Operational columns (timezone, weekend_days, trading hours) hold LOCAL clock
    times in the country's IANA timezone. Convert to UTC at query time via
    `AT TIME ZONE`. DST-correct for real countries.
    """

    __tablename__ = "dim_country"
    __table_args__ = (
        UniqueConstraint("country_code", name="uq_dbo_dim_country_code"),
        # iso_alpha3 uniqueness is enforced via a filtered unique INDEX
        # (see migration 038) — NULLs allowed for pseudo countries.
        CheckConstraint(
            "(is_pseudo=0 AND iso_alpha3 IS NOT NULL) OR "
            "(is_pseudo=1 AND iso_alpha3 IS NULL)",
            name="chk_dbo_dim_country_pseudo",
        ),
        {"schema": "dbo"},
    )

    # TINYINT IDENTITY PK — country space well under 255 entries.
    id: Mapped[int] = mapped_column(TINYINT, primary_key=True, autoincrement=True)
    country_code: Mapped[str] = mapped_column(String(3), nullable=False)
    iso_alpha3: Mapped[str | None] = mapped_column(String(3), nullable=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_pseudo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Operational hours — NULL for pseudo countries (EU/WW/XX).
    timezone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    weekend_days: Mapped[str | None] = mapped_column(String(10), nullable=True)
    trading_open: Mapped[str | None] = mapped_column(String(5), nullable=True)
    trading_close: Mapped[str | None] = mapped_column(String(5), nullable=True)
    lunch_start: Mapped[str | None] = mapped_column(String(5), nullable=True)
    lunch_end: Mapped[str | None] = mapped_column(String(5), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:
        return f"<DimCountry {self.country_code}>"
