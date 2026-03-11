"""Tests for FX OHLC cleaning module."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, call, patch

import pandas as pd
import pytest

from imdr.domains.fx.clean_fx_fact_ohlc import (
    BidAskInversionRule,
    HardBoundViolationRule,
    NonPositivePriceRule,
    RobustOutlierRule,
)
from imdr.healthchecks.cleaning import CleaningRunner


@pytest.fixture()
def reader() -> MagicMock:
    return MagicMock()


@pytest.fixture()
def connector() -> MagicMock:
    mock = MagicMock()
    # session() is a context manager
    mock.session.return_value.__enter__ = MagicMock()
    mock.session.return_value.__exit__ = MagicMock(return_value=False)
    return mock


# ---------------------------------------------------------------------------
# NonPositivePriceRule
# ---------------------------------------------------------------------------

class TestNonPositivePriceRule:
    def test_detect_empty(self, reader: MagicMock) -> None:
        reader.read_sql.return_value = pd.DataFrame()
        rule = NonPositivePriceRule()
        df = rule.detect(reader, "[fx].[fact_ohlc]")
        assert df.empty

    def test_detect_returns_rows(self, reader: MagicMock) -> None:
        reader.read_sql.return_value = pd.DataFrame({
            "id": [1, 2],
            "ts": [datetime(2021, 2, 25), datetime(2021, 2, 26)],
            "symbol": ["USDTWD", "USDTWD"],
            "series": ["NDF_1M", "NDF_1M"],
            "close_px": [-43.15, -10.0],
        })
        rule = NonPositivePriceRule()
        df = rule.detect(reader, "[fx].[fact_ohlc]")
        assert len(df) == 2
        assert "id" in df.columns

    def test_sql_checks_all_price_columns(self, reader: MagicMock) -> None:
        reader.read_sql.return_value = pd.DataFrame()
        rule = NonPositivePriceRule()
        rule.detect(reader, "[fx].[fact_ohlc]")
        sql = reader.read_sql.call_args[0][0]
        assert "[open_px] <= 0" in sql
        assert "[ask] <= 0" in sql

    def test_build_update_nulls_all_prices(self) -> None:
        rule = NonPositivePriceRule()
        sql = rule.build_update_sql([1, 2, 3])
        assert "SET" in sql
        assert "[open_px] = NULL" in sql
        assert "[ask] = NULL" in sql
        assert "IN (1, 2, 3)" in sql

    def test_name_and_action(self) -> None:
        rule = NonPositivePriceRule()
        assert rule.name == "non_positive"
        assert rule.action_label == "null_prices"


# ---------------------------------------------------------------------------
# HardBoundViolationRule
# ---------------------------------------------------------------------------

class TestHardBoundViolationRule:
    def test_detect_empty_ranges(self, reader: MagicMock) -> None:
        rule = HardBoundViolationRule(ranges={})
        df = rule.detect(reader, "[fx].[fact_ohlc]")
        assert df.empty

    def test_detect_builds_per_symbol_filter(self, reader: MagicMock) -> None:
        reader.read_sql.return_value = pd.DataFrame()
        ranges = {"EURUSD": (0.3, 3.0), "USDJPY": (60.0, 200.0)}
        rule = HardBoundViolationRule(ranges=ranges)
        rule.detect(reader, "[fx].[fact_ohlc]")
        sql = reader.read_sql.call_args[0][0]
        assert "'EURUSD'" in sql
        assert "'USDJPY'" in sql
        assert "< 0.3 OR" in sql
        assert "> 200.0" in sql

    def test_describe_includes_bounds(self) -> None:
        ranges = {"USDKRW": (800.0, 1600.0)}
        rule = HardBoundViolationRule(ranges=ranges)
        row = pd.Series({"symbol": "USDKRW", "ts": "2025-01-01", "close_px": 8845.0})
        desc = rule.describe(row)
        assert "800.0" in desc
        assert "1600.0" in desc


# ---------------------------------------------------------------------------
# RobustOutlierRule
# ---------------------------------------------------------------------------

class TestRobustOutlierRule:
    def test_name_and_action(self) -> None:
        rule = RobustOutlierRule()
        assert rule.name == "robust_outlier"
        assert rule.action_label == "null_prices"

    def test_detect_empty_input(self, reader: MagicMock) -> None:
        reader.read_sql.return_value = pd.DataFrame()
        rule = RobustOutlierRule()
        df = rule.detect(reader, "[fx].[fact_ohlc]")
        assert df.empty

    def test_detect_skips_small_groups(self, reader: MagicMock) -> None:
        """Groups with fewer than min_obs rows should be skipped entirely."""
        reader.read_sql.return_value = pd.DataFrame({
            "id": range(10),
            "ts": pd.date_range("2024-01-01", periods=10, freq="h", tz="UTC"),
            "symbol": ["EURUSD"] * 10,
            "series": ["SPOT"] * 10,
            "close_px": [1.10] * 9 + [999.0],  # spike, but only 10 rows
        })
        rule = RobustOutlierRule(min_obs=100)
        df = rule.detect(reader, "[fx].[fact_ohlc]")
        assert df.empty

    def test_detect_flags_spike_in_stable_series(self, reader: MagicMock) -> None:
        """An extreme spike in an otherwise stable series should be flagged."""
        n = 200
        ts = pd.date_range("2024-01-01", periods=n, freq="h", tz="UTC")
        # Small normal variation with a huge spike at end
        prices = [1.10 + 0.001 * (i % 5) for i in range(n - 1)] + [99.0]
        reader.read_sql.return_value = pd.DataFrame({
            "id": range(n),
            "ts": ts,
            "symbol": ["EURUSD"] * n,
            "series": ["SPOT"] * n,
            "close_px": prices,
        })
        rule = RobustOutlierRule(min_obs=100, n_mad=4.0)
        df = rule.detect(reader, "[fx].[fact_ohlc]")
        assert len(df) >= 1
        assert "id" in df.columns
        assert "robust_z" in df.columns
        assert df.iloc[0]["id"] == n - 1

    def test_detect_does_not_flag_normal_drift(self, reader: MagicMock) -> None:
        """Gradual price drift should NOT be flagged as outliers."""
        n = 400
        ts = pd.date_range("2023-01-01", periods=n, freq="h", tz="UTC")
        # Slow linear drift from 1.10 to 1.30
        prices = [1.10 + 0.20 * i / (n - 1) for i in range(n)]
        reader.read_sql.return_value = pd.DataFrame({
            "id": range(n),
            "ts": ts,
            "symbol": ["EURUSD"] * n,
            "series": ["SPOT"] * n,
            "close_px": prices,
        })
        rule = RobustOutlierRule(min_obs=100, n_mad=4.0)
        df = rule.detect(reader, "[fx].[fact_ohlc]")
        assert df.empty


# ---------------------------------------------------------------------------
# BidAskInversionRule
# ---------------------------------------------------------------------------

class TestBidAskInversionRule:
    def test_name_and_action(self) -> None:
        rule = BidAskInversionRule()
        assert rule.name == "bid_ask"
        assert rule.action_label == "swap_bid_ask"

    def test_detect_where_clause(self, reader: MagicMock) -> None:
        reader.read_sql.return_value = pd.DataFrame()
        rule = BidAskInversionRule()
        rule.detect(reader, "[fx].[fact_ohlc]")
        sql = reader.read_sql.call_args[0][0]
        assert "[bid] > [ask]" in sql
        assert "[bid] IS NOT NULL" in sql

    def test_build_update_swaps_bid_ask(self) -> None:
        rule = BidAskInversionRule()
        sql = rule.build_update_sql([10, 20])
        assert "t.[bid] = t.[ask]" in sql
        assert "t.[ask] = t.[bid]" in sql
        assert "IN (10, 20)" in sql

    def test_describe_shows_values(self) -> None:
        rule = BidAskInversionRule()
        row = pd.Series({
            "symbol": "EURUSD",
            "ts": "2024-01-01",
            "series": "SPOT",
            "bid": 1.11,
            "ask": 1.10,
        })
        desc = rule.describe(row)
        assert "inversion" in desc
        assert "1.11" in desc


# ---------------------------------------------------------------------------
# CleaningRunner
# ---------------------------------------------------------------------------

class TestCleaningRunner:
    def test_dry_run_does_not_execute(
        self, connector: MagicMock, reader: MagicMock
    ) -> None:
        reader.read_sql.return_value = pd.DataFrame({
            "id": [1],
            "ts": [datetime(2021, 1, 1)],
            "symbol": ["USDTWD"],
            "series": ["NDF_1M"],
            "close_px": [-43.0],
            "bid": [-43.0],
            "ask": [-43.0],
        })

        rule = NonPositivePriceRule(columns=["close_px"])
        runner = CleaningRunner(
            connector=connector,
            reader=reader,
            rules=[rule],
            table="[fx].[fact_ohlc]",
            dry_run=True,
        )
        results = runner.run()

        assert len(results) == 1
        assert results[0].count == 1
        assert results[0].dry_run is True
        # Session should NOT have been opened
        connector.session.assert_not_called()

    def test_execute_mode_runs_updates(
        self, connector: MagicMock, reader: MagicMock
    ) -> None:
        reader.read_sql.return_value = pd.DataFrame({
            "id": [1, 2],
            "ts": [datetime(2021, 1, 1), datetime(2021, 1, 2)],
            "symbol": ["USDTWD", "USDTWD"],
            "series": ["NDF_1M", "NDF_1M"],
            "close_px": [-43.0, -10.0],
            "bid": [-43.0, -10.0],
            "ask": [-43.0, -10.0],
        })

        rule = NonPositivePriceRule(columns=["close_px"])
        runner = CleaningRunner(
            connector=connector,
            reader=reader,
            rules=[rule],
            table="[fx].[fact_ohlc]",
            dry_run=False,
        )
        results = runner.run()

        assert results[0].count == 2
        assert results[0].dry_run is False
        # Session should have been opened
        connector.session.assert_called()

    def test_empty_detection_skips_execution(
        self, connector: MagicMock, reader: MagicMock
    ) -> None:
        reader.read_sql.return_value = pd.DataFrame()

        rule = NonPositivePriceRule()
        runner = CleaningRunner(
            connector=connector,
            reader=reader,
            rules=[rule],
            table="[fx].[fact_ohlc]",
            dry_run=False,
        )
        results = runner.run()

        assert results[0].count == 0
        connector.session.assert_not_called()

    def test_multiple_rules_run_in_order(
        self, connector: MagicMock, reader: MagicMock
    ) -> None:
        reader.read_sql.return_value = pd.DataFrame()

        rules = [
            NonPositivePriceRule(),
            BidAskInversionRule(),
        ]
        runner = CleaningRunner(
            connector=connector,
            reader=reader,
            rules=rules,
            table="[fx].[fact_ohlc]",
            dry_run=True,
        )
        results = runner.run()

        assert len(results) == 2
        assert results[0].rule_name == "non_positive"
        assert results[1].rule_name == "bid_ask"

    def test_where_clause_passed_to_rules(
        self, connector: MagicMock, reader: MagicMock
    ) -> None:
        reader.read_sql.return_value = pd.DataFrame()

        rule = NonPositivePriceRule()
        runner = CleaningRunner(
            connector=connector,
            reader=reader,
            rules=[rule],
            table="[fx].[fact_ohlc]",
            dry_run=True,
        )
        runner.run(where="AND YEAR([ts]) = 2024")

        sql = reader.read_sql.call_args[0][0]
        assert "AND YEAR([ts]) = 2024" in sql
