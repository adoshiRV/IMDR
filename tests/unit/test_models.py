from __future__ import annotations

from imdr.models.base import Base, TimestampMixin


class TestBaseModel:
    def test_base_is_abstract(self) -> None:
        assert Base.__abstract__ is True

    def test_timestamp_mixin_has_columns(self) -> None:
        assert hasattr(TimestampMixin, "created_at")
        assert hasattr(TimestampMixin, "updated_at")
