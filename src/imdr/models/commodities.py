"""Commodities domain ORM models mapping to [commodities] schema tables."""
from __future__ import annotations

from datetime import date

from sqlalchemy import Date, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from imdr.models.base import Base


class CmdtyCommodity(Base):
    """Shared commodity dimension — links spot and implied vol products."""

    __tablename__ = "dim_commodity"
    __table_args__ = (
        UniqueConstraint("symbol", name="uq_cmdty_dim_commodity"),
        {"schema": "commodities"},
    )

    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    display_name: Mapped[str] = mapped_column(String(60), nullable=False)
    commodity_class: Mapped[str] = mapped_column(String(20), nullable=False)
    spot_tag: Mapped[str | None] = mapped_column(String(60), nullable=True)

    spot_observations: Mapped[list[CmdtyFactSpot]] = relationship(
        back_populates="commodity"
    )
    vol_observations: Mapped[list[CmdtyFactImpliedVol]] = relationship(
        back_populates="commodity"
    )

    def __repr__(self) -> str:
        return f"<CmdtyCommodity {self.symbol} ({self.commodity_class})>"


class CmdtyFactSpot(Base):
    """Daily commodity spot prices."""

    __tablename__ = "fact_spot"
    __table_args__ = (
        UniqueConstraint("commodity_id", "obs_date", name="uq_cmdty_fact_spot"),
        {"schema": "commodities"},
    )

    commodity_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("commodities.dim_commodity.id"), nullable=False
    )
    obs_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    price: Mapped[float] = mapped_column(Float, nullable=False)

    commodity: Mapped[CmdtyCommodity] = relationship(
        back_populates="spot_observations"
    )

    def __repr__(self) -> str:
        return f"<CmdtyFactSpot {self.obs_date} commodity_id={self.commodity_id} price={self.price}>"


class CmdtyDimEIASeries(Base):
    """EIA petroleum status report series x region dimension."""

    __tablename__ = "dim_eia_series"
    __table_args__ = (
        UniqueConstraint("series_name", "region", name="uq_cmdty_dim_eia_series"),
        {"schema": "commodities"},
    )

    series_name: Mapped[str] = mapped_column(String(30), nullable=False)
    region: Mapped[str] = mapped_column(String(20), nullable=False)
    series_units: Mapped[str] = mapped_column(String(40), nullable=False, default="")

    eia_observations: Mapped[list[CmdtyFactEIA]] = relationship(
        back_populates="eia_series"
    )

    def __repr__(self) -> str:
        return f"<CmdtyDimEIASeries {self.series_name}.{self.region}>"


class CmdtyFactEIA(Base):
    """Weekly EIA petroleum status observations."""

    __tablename__ = "fact_eia"
    __table_args__ = (
        UniqueConstraint("eia_series_id", "obs_date", name="uq_cmdty_fact_eia"),
        {"schema": "commodities"},
    )

    eia_series_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("commodities.dim_eia_series.id"), nullable=False
    )
    obs_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    stat_value: Mapped[float] = mapped_column(Float, nullable=False)

    eia_series: Mapped[CmdtyDimEIASeries] = relationship(
        back_populates="eia_observations"
    )

    def __repr__(self) -> str:
        return f"<CmdtyFactEIA {self.obs_date} series_id={self.eia_series_id} stat_value={self.stat_value}>"


class CmdtyFactImpliedVol(Base):
    """Daily commodity option implied vol surfaces."""

    __tablename__ = "fact_implied_vol"
    __table_args__ = (
        UniqueConstraint(
            "commodity_id", "obs_date", "strike", "tenor",
            name="uq_cmdty_fact_implied_vol",
        ),
        {"schema": "commodities"},
    )

    commodity_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("commodities.dim_commodity.id"), nullable=False
    )
    obs_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    strike: Mapped[str] = mapped_column(String(15), nullable=False)
    tenor: Mapped[str] = mapped_column(String(15), nullable=False)
    vol: Mapped[float] = mapped_column(Float, nullable=False)

    commodity: Mapped[CmdtyCommodity] = relationship(
        back_populates="vol_observations"
    )

    def __repr__(self) -> str:
        return (
            f"<CmdtyFactImpliedVol commodity_id={self.commodity_id} "
            f"{self.obs_date} {self.strike} {self.tenor}={self.vol}>"
        )
