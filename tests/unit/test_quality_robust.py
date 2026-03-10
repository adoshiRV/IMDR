"""Tests for RobustStatisticalOutlierCheck."""

from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd
import pytest

from imdr.healthchecks.base import CheckStatus
from imdr.healthchecks.quality import RobustStatisticalOutlierCheck


@pytest.fixture()
def reader() -> MagicMock:
    return MagicMock()


class TestRobustStatisticalOutlierCheck:
    def test_no_outliers_returns_passed(self, reader: MagicMock) -> None:
        reader.read_sql.return_value = pd.DataFrame()

        check = RobustStatisticalOutlierCheck(
            value_column="close_px",
            group_columns=["symbol", "series"],
            n_mad=4.0,
            trailing_months=12,
        )
        result = check.run(reader, "[fx].[fact_ohlc]")

        assert result.status == CheckStatus.PASSED
        assert result.check_name == "robust_outliers"
        assert "No outliers" in result.message

    def test_outlier_detected_returns_warning(self, reader: MagicMock) -> None:
        flagged = pd.DataFrame({
            "ts": ["2025-09-14 22:00:00"],
            "symbol": ["USDKRW"],
            "series": ["SPOT"],
            "close_px": [8845.45],
            "median_val": [1340.0],
            "mad_val": [50.0],
            "robust_z": [101.2],
        })
        reader.read_sql.return_value = flagged

        check = RobustStatisticalOutlierCheck(
            value_column="close_px",
            n_mad=4.0,
        )
        result = check.run(reader, "[fx].[fact_ohlc]")

        assert result.status == CheckStatus.WARNING
        assert result.check_name == "robust_outliers"
        assert "1 outliers" in result.message
        assert result.flagged is not None
        assert len(result.flagged) == 1
        assert result.meta["n_mad"] == 4.0
        assert result.meta["trailing_months"] == 12

    def test_default_group_columns(self) -> None:
        check = RobustStatisticalOutlierCheck(value_column="close_px")
        assert check._group_cols == ["symbol", "series"]

    def test_custom_group_columns(self) -> None:
        check = RobustStatisticalOutlierCheck(
            value_column="close_px",
            group_columns=["symbol"],
        )
        assert check._group_cols == ["symbol"]

    def test_sql_contains_trailing_window(self, reader: MagicMock) -> None:
        reader.read_sql.return_value = pd.DataFrame()

        check = RobustStatisticalOutlierCheck(
            value_column="close_px",
            trailing_months=6,
        )
        check.run(reader, "[fx].[fact_ohlc]")

        sql = reader.read_sql.call_args[0][0]
        assert "DATEADD(MONTH, -6," in sql

    def test_sql_partitions_by_group_columns(self, reader: MagicMock) -> None:
        reader.read_sql.return_value = pd.DataFrame()

        check = RobustStatisticalOutlierCheck(
            value_column="close_px",
            group_columns=["symbol", "series"],
        )
        check.run(reader, "[fx].[fact_ohlc]")

        sql = reader.read_sql.call_args[0][0]
        assert "PARTITION BY [symbol], [series]" in sql

    def test_min_obs_in_sql(self, reader: MagicMock) -> None:
        reader.read_sql.return_value = pd.DataFrame()

        check = RobustStatisticalOutlierCheck(
            value_column="close_px",
            min_obs=200,
        )
        check.run(reader, "[fx].[fact_ohlc]")

        sql = reader.read_sql.call_args[0][0]
        assert "HAVING COUNT(*) >= 200" in sql

    def test_meta_includes_all_params(self, reader: MagicMock) -> None:
        flagged = pd.DataFrame({
            "ts": ["2025-01-01"],
            "symbol": ["EURUSD"],
            "series": ["SPOT"],
            "close_px": [99.0],
            "median_val": [1.1],
            "mad_val": [0.01],
            "robust_z": [50.0],
        })
        reader.read_sql.return_value = flagged

        check = RobustStatisticalOutlierCheck(
            value_column="close_px",
            n_mad=5.0,
            trailing_months=24,
        )
        result = check.run(reader, "[fx].[fact_ohlc]")

        assert result.meta["n_mad"] == 5.0
        assert result.meta["trailing_months"] == 24
        assert result.meta["outlier_count"] == 1
