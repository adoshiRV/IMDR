from __future__ import annotations

from imdr.models.base import Base, TimestampMixin
from imdr.models.fx import FXSpotRate


class TestBaseModel:
    def test_base_is_abstract(self) -> None:
        assert Base.__abstract__ is True

    def test_timestamp_mixin_has_columns(self) -> None:
        assert hasattr(TimestampMixin, "created_at")
        assert hasattr(TimestampMixin, "updated_at")


class TestFXSpotRate:
    def test_tablename(self) -> None:
        assert FXSpotRate.__tablename__ == "fx_spot_rates"

    def test_schema(self) -> None:
        assert FXSpotRate.__table__.schema == "fx"

    def test_has_required_columns(self) -> None:
        columns = {c.name for c in FXSpotRate.__table__.columns}
        expected = {"id", "base_currency", "quote_currency", "rate_date", "mid", "source", "created_at", "updated_at"}
        assert expected.issubset(columns)

    def test_has_unique_constraint(self) -> None:
        constraint_names = [c.name for c in FXSpotRate.__table__.constraints if c.name]
        assert "uq_fx_spot_rate" in constraint_names
