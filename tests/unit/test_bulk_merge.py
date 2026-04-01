"""Tests for bulk merge utilities (chunked_bulk_merge, MergeSpec)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, call, patch

import pytest
from pydantic import BaseModel

from imdr.connectors.bulk import MergeSpec, bulk_merge, chunked_bulk_merge


# ── Helpers ──────────────────────────────────────────────────────────────────


class _FakeItem(BaseModel):
    pair_id: int
    obs_date: date
    value: float


class _FakeDecimalItem(BaseModel):
    pair_id: int
    obs_date: date
    value: Decimal


def _make_items(n: int) -> list[_FakeItem]:
    return [_FakeItem(pair_id=1, obs_date=date(2026, 1, 1), value=float(i)) for i in range(n)]


_SIMPLE_SPEC = MergeSpec(
    target_table="[fx].[fact_vol]",
    staging_name="#test_staging",
    columns={"pair_id": "INT", "obs_date": "DATE", "value": "FLOAT"},
    natural_key=["pair_id", "obs_date"],
    value_columns=["value"],
)


# ── chunked_bulk_merge tests ────────────────────────────────────────────────


class TestChunkedBulkMerge:
    def test_empty_returns_zero(self) -> None:
        connector = MagicMock()
        result = chunked_bulk_merge(connector, _SIMPLE_SPEC, [], chunk_size=100)
        assert result == 0
        connector.session.assert_not_called()

    @patch("imdr.connectors.bulk.bulk_merge")
    def test_single_chunk(self, mock_bulk_merge: MagicMock) -> None:
        mock_bulk_merge.return_value = 3
        connector = MagicMock()
        mock_session = MagicMock()
        connector.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        connector.session.return_value.__exit__ = MagicMock(return_value=False)

        items = _make_items(3)
        result = chunked_bulk_merge(connector, _SIMPLE_SPEC, items, chunk_size=100)

        assert result == 3
        mock_bulk_merge.assert_called_once()
        assert len(mock_bulk_merge.call_args[0][2]) == 3  # all items in one chunk

    @patch("imdr.connectors.bulk.bulk_merge")
    def test_multiple_chunks(self, mock_bulk_merge: MagicMock) -> None:
        mock_bulk_merge.return_value = 0  # return value not used for count
        connector = MagicMock()
        mock_session = MagicMock()
        connector.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        connector.session.return_value.__exit__ = MagicMock(return_value=False)

        items = _make_items(7)
        result = chunked_bulk_merge(connector, _SIMPLE_SPEC, items, chunk_size=3)

        assert result == 7
        assert mock_bulk_merge.call_count == 3  # 3 + 3 + 1

    @patch("imdr.connectors.bulk.bulk_merge")
    def test_exact_boundary(self, mock_bulk_merge: MagicMock) -> None:
        mock_bulk_merge.return_value = 0
        connector = MagicMock()
        mock_session = MagicMock()
        connector.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        connector.session.return_value.__exit__ = MagicMock(return_value=False)

        items = _make_items(6)
        result = chunked_bulk_merge(connector, _SIMPLE_SPEC, items, chunk_size=3)

        assert result == 6
        assert mock_bulk_merge.call_count == 2  # 3 + 3


# ── MergeSpec tests ─────────────────────────────────────────────────────────


class TestMergeSpec:
    def test_default_audit_columns(self) -> None:
        spec = MergeSpec(
            target_table="[fx].[fact_vol]",
            staging_name="#test",
            columns={"pair_id": "INT", "value": "FLOAT"},
            natural_key=["pair_id"],
            value_columns=["value"],
        )
        sql = spec._merge_sql()
        assert "tgt.updated_at = SYSDATETIMEOFFSET()" in sql
        assert "created_at" in sql
        assert "updated_at" in sql

    def test_custom_audit_columns_no_updated_at(self) -> None:
        spec = MergeSpec(
            target_table="[fx].[fact_ohlc]",
            staging_name="#test",
            columns={"pair_id": "INT", "value": "FLOAT"},
            natural_key=["pair_id"],
            value_columns=["value"],
            audit_columns={"created_at": "SYSDATETIMEOFFSET()"},
        )
        sql = spec._merge_sql()
        assert "created_at" in sql
        assert "updated_at" not in sql

    def test_empty_audit_columns(self) -> None:
        spec = MergeSpec(
            target_table="[fx].[fact_vol]",
            staging_name="#test",
            columns={"pair_id": "INT", "value": "FLOAT"},
            natural_key=["pair_id"],
            value_columns=["value"],
            audit_columns={},
        )
        sql = spec._merge_sql()
        assert "created_at" not in sql
        assert "updated_at" not in sql

    def test_serialize_row_date_to_string(self) -> None:
        item = _FakeItem(pair_id=1, obs_date=date(2026, 3, 25), value=1.5)
        row = _SIMPLE_SPEC.serialize_row(item)
        assert row["obs_date"] == "2026-03-25"
        assert isinstance(row["obs_date"], str)

    def test_serialize_row_decimal_to_float(self) -> None:
        spec = MergeSpec(
            target_table="[fx].[fact_vol]",
            staging_name="#test",
            columns={"pair_id": "INT", "obs_date": "DATE", "value": "FLOAT"},
            natural_key=["pair_id", "obs_date"],
            value_columns=["value"],
        )
        item = _FakeDecimalItem(pair_id=1, obs_date=date(2026, 3, 25), value=Decimal("1.23456"))
        row = spec.serialize_row(item)
        assert isinstance(row["value"], float)
        assert row["value"] == pytest.approx(1.23456)

    def test_staging_sql_creates_table(self) -> None:
        sql = _SIMPLE_SPEC._create_staging_sql()
        assert "CREATE TABLE #test_staging" in sql
        assert "pair_id" in sql
        assert "value" in sql

    def test_insert_sql_has_params(self) -> None:
        sql = _SIMPLE_SPEC._insert_sql()
        assert ":pair_id" in sql
        assert ":obs_date" in sql
        assert ":value" in sql

    def test_merge_sql_on_clause(self) -> None:
        sql = _SIMPLE_SPEC._merge_sql()
        assert "tgt.pair_id = src.pair_id" in sql
        assert "tgt.obs_date = src.obs_date" in sql

    def test_invalid_target_table_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid target_table"):
            MergeSpec(
                target_table="bad_table",
                staging_name="#test",
                columns={"id": "INT"},
                natural_key=["id"],
                value_columns=[],
            )

    def test_natural_key_not_in_columns_raises(self) -> None:
        with pytest.raises(ValueError, match="natural_key columns not in columns"):
            MergeSpec(
                target_table="[fx].[t]",
                staging_name="#test",
                columns={"id": "INT"},
                natural_key=["id", "missing"],
                value_columns=[],
            )
