"""Tests for AnalyticalReader — the ORM-bypassing read helper."""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from imdr.connectors.reader import AnalyticalReader


def _make_reader() -> tuple[AnalyticalReader, MagicMock]:
    """Build an AnalyticalReader whose engine is a fully-mocked connection."""
    connector = MagicMock()
    # _engine.connect() is used as a context manager
    conn_ctx = MagicMock()
    connector.read_engine.connect.return_value.__enter__ = MagicMock(return_value=conn_ctx)
    connector.read_engine.connect.return_value.__exit__ = MagicMock(return_value=False)
    return AnalyticalReader(connector), conn_ctx


class TestReadSql:
    @patch("imdr.connectors.reader.pd.read_sql")
    def test_returns_dataframe(self, mock_read_sql: MagicMock) -> None:
        mock_read_sql.return_value = pd.DataFrame({"a": [1, 2]})
        reader, _ = _make_reader()

        df = reader.read_sql("SELECT 1 AS a")
        assert list(df["a"]) == [1, 2]
        assert mock_read_sql.call_count == 1

    @patch("imdr.connectors.reader.pd.read_sql")
    def test_passes_params_through(self, mock_read_sql: MagicMock) -> None:
        mock_read_sql.return_value = pd.DataFrame()
        reader, _ = _make_reader()

        reader.read_sql("SELECT * FROM t WHERE id = :id", params={"id": 5})
        kwargs = mock_read_sql.call_args.kwargs
        assert kwargs["params"] == {"id": 5}


class TestDateRangeScan:
    def test_invalid_table_raises(self) -> None:
        reader, _ = _make_reader()
        with pytest.raises(ValueError, match="Invalid table"):
            reader.date_range_scan(
                "fact_ohlc",  # missing brackets
                "ts",
                start=date(2026, 1, 1),
                end=date(2026, 1, 31),
            )

    def test_invalid_date_column_raises(self) -> None:
        reader, _ = _make_reader()
        with pytest.raises(ValueError, match="Invalid date_column"):
            reader.date_range_scan(
                "[fx].[fact_ohlc]",
                "bad-col",  # hyphen not allowed
                start=date(2026, 1, 1),
                end=date(2026, 1, 31),
            )

    @patch("imdr.connectors.reader.pd.read_sql")
    def test_column_subset_narrows_select(self, mock_read_sql: MagicMock) -> None:
        mock_read_sql.return_value = pd.DataFrame()
        reader, _ = _make_reader()

        reader.date_range_scan(
            "[fx].[fact_ohlc]",
            "ts",
            start=date(2026, 1, 1),
            end=date(2026, 1, 31),
            columns=["ts", "close_px"],
        )
        # First positional arg is the SQLAlchemy text() construct
        sql_text = str(mock_read_sql.call_args.args[0])
        assert "SELECT [ts], [close_px]" in sql_text
        assert "FROM [fx].[fact_ohlc]" in sql_text

    def test_invalid_column_in_subset_raises(self) -> None:
        reader, _ = _make_reader()
        with pytest.raises(ValueError, match="Invalid column"):
            reader.date_range_scan(
                "[fx].[fact_ohlc]",
                "ts",
                start=date(2026, 1, 1),
                end=date(2026, 1, 31),
                columns=["ts", "bad-col"],
            )


class TestReadView:
    def test_invalid_view_raises(self) -> None:
        reader, _ = _make_reader()
        with pytest.raises(ValueError, match="Invalid view_name"):
            reader.read_view("no_brackets")

    @patch("imdr.connectors.reader.pd.read_sql")
    def test_filters_become_parameterised_where(self, mock_read_sql: MagicMock) -> None:
        mock_read_sql.return_value = pd.DataFrame()
        reader, _ = _make_reader()

        reader.read_view("[fx].[v_test]", filters={"pair_id": 42, "obs_date": "2026-01-01"})
        sql_text = str(mock_read_sql.call_args.args[0])
        params = mock_read_sql.call_args.kwargs["params"]
        # Each filter becomes a [col] = :p_col clause
        assert "[pair_id] = :p_pair_id" in sql_text
        assert "[obs_date] = :p_obs_date" in sql_text
        assert params == {"p_pair_id": 42, "p_obs_date": "2026-01-01"}

    def test_invalid_limit_raises(self) -> None:
        reader, _ = _make_reader()
        with pytest.raises(ValueError, match="Invalid limit"):
            reader.read_view("[fx].[v_test]", limit=0)

    def test_invalid_order_by_raises(self) -> None:
        reader, _ = _make_reader()
        with pytest.raises(ValueError, match="Invalid order_by"):
            reader.read_view("[fx].[v_test]", order_by="bad-col")

    @patch("imdr.connectors.reader.pd.read_sql")
    def test_limit_emits_top(self, mock_read_sql: MagicMock) -> None:
        mock_read_sql.return_value = pd.DataFrame()
        reader, _ = _make_reader()

        reader.read_view("[fx].[v_test]", limit=10)
        sql_text = str(mock_read_sql.call_args.args[0])
        assert "TOP(10)" in sql_text

    def test_invalid_filter_column_raises(self) -> None:
        reader, _ = _make_reader()
        with pytest.raises(ValueError, match="Invalid filter column"):
            reader.read_view("[fx].[v_test]", filters={"bad-col": 1})
