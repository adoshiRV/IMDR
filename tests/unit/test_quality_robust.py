"""Tests for RobustStatisticalOutlierCheck and DistributionCheck.

Covers the 2026-07-17 prod incident fix — see
docs/admin/development/prod_long_running_quality_query.md. The windowed
``PERCENTILE_CONT(...) OVER (PARTITION BY...)`` antipattern caused a
62-minute suspended query on prod (no grouped-aggregate percentile exists
in T-SQL). Both checks now do only cheap indexed range-scan SELECTs;
median/MAD/percentile math is computed in pandas.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd
import pytest

from imdr.healthchecks.base import CheckStatus
from imdr.healthchecks.quality import DistributionCheck, RobustStatisticalOutlierCheck

_MAD_SCALE = 1.4826


@pytest.fixture()
def reader() -> MagicMock:
    return MagicMock()


def _max_ts_df(ts) -> pd.DataFrame:
    return pd.DataFrame({"mt": [pd.Timestamp(ts)]})


# ---------------------------------------------------------------------------
# RobustStatisticalOutlierCheck
# ---------------------------------------------------------------------------

class TestRobustStatisticalOutlierCheckNoData:
    def test_empty_max_ts_returns_passed_and_short_circuits(self, reader: MagicMock) -> None:
        reader.read_sql.return_value = pd.DataFrame()

        check = RobustStatisticalOutlierCheck(value_column="close_px", trailing_months=12)
        result = check.run(reader, "[fx].[fact_ohlc]")

        assert result.status == CheckStatus.PASSED
        assert result.check_name == "robust_outliers"
        assert "No outliers" in result.message
        # No baseline pull attempted once the anchor query comes back empty.
        assert reader.read_sql.call_count == 1

    def test_empty_baseline_returns_passed(self, reader: MagicMock) -> None:
        reader.read_sql.side_effect = [_max_ts_df("2025-06-01"), pd.DataFrame()]

        check = RobustStatisticalOutlierCheck(value_column="close_px")
        result = check.run(reader, "[fx].[fact_ohlc]")

        assert result.status == CheckStatus.PASSED
        assert reader.read_sql.call_count == 2


class TestRobustStatisticalOutlierCheckSQLShape:
    def test_no_percentile_cont_distinct_or_windowed_over(self, reader: MagicMock) -> None:
        ts_values = pd.date_range("2025-01-01", periods=6, freq="D")
        baseline_df = pd.DataFrame({
            "symbol": ["USDKRW"] * 6,
            "series": ["SPOT"] * 6,
            "ts": ts_values,
            "close_px": [1330, 1335, 1340, 1345, 1350, 1390],
        })
        where = "AND [ts] >= '2025-01-06' AND [ts] <= '2025-01-06'"
        reader.read_sql.side_effect = [
            _max_ts_df(ts_values[-1]),
            baseline_df,
            baseline_df.tail(1),
        ]

        check = RobustStatisticalOutlierCheck(value_column="close_px", min_obs=3)
        check.run(reader, "[fx].[fact_ohlc]", where=where)

        assert reader.read_sql.call_count == 3
        for call in reader.read_sql.call_args_list:
            sql = call.args[0]
            assert "PERCENTILE_CONT" not in sql
            assert "OVER (" not in sql
            assert "OVER(" not in sql
            assert "SELECT DISTINCT" not in sql
            assert ", max_ts" not in sql  # no implicit cross join with a max_ts CTE

    def test_baseline_filter_scopes_anchor_query(self, reader: MagicMock) -> None:
        reader.read_sql.return_value = pd.DataFrame()

        check = RobustStatisticalOutlierCheck(
            value_column="mid_rate",
            baseline_filter="AND [frequency_id] = 5",
        )
        check.run(reader, "[fx].[fact_fx_rate]")

        max_ts_sql = reader.read_sql.call_args_list[0].args[0]
        assert "AND [frequency_id] = 5" in max_ts_sql

    def test_baseline_filter_scopes_baseline_pull(self, reader: MagicMock) -> None:
        reader.read_sql.side_effect = [_max_ts_df("2025-06-01"), pd.DataFrame()]

        check = RobustStatisticalOutlierCheck(
            value_column="mid_rate",
            baseline_filter="AND [frequency_id] = 5",
        )
        check.run(reader, "[fx].[fact_fx_rate]")

        baseline_sql = reader.read_sql.call_args_list[1].args[0]
        assert "AND [frequency_id] = 5" in baseline_sql


class TestRobustStatisticalOutlierCheckTrailingWindow:
    """Regression test for finding 2 — the run-window `where` must not shrink the baseline."""

    def test_run_window_where_does_not_narrow_baseline_pull(self, reader: MagicMock) -> None:
        reader.read_sql.side_effect = [_max_ts_df("2025-06-01"), pd.DataFrame()]

        where = "AND [obs_date] >= '2025-06-01' AND [obs_date] <= '2025-06-01'"
        check = RobustStatisticalOutlierCheck(value_column="mid_rate", trailing_months=6)
        check.run(reader, "[fx].[fact_fx_rate]", where=where)

        max_ts_sql, baseline_sql = (c.args[0] for c in reader.read_sql.call_args_list)
        assert where in max_ts_sql
        assert where not in baseline_sql
        assert ":baseline_start" in baseline_sql
        assert ":max_ts" in baseline_sql


class TestRobustStatisticalOutlierCheckCorrectness:
    def test_median_mad_robust_z_with_planted_outlier(self, reader: MagicMock) -> None:
        ts_values = pd.date_range("2025-01-01", periods=6, freq="D")
        baseline_df = pd.DataFrame({
            "symbol": ["USDKRW"] * 6,
            "ts": ts_values,
            "close_px": [1330, 1335, 1340, 1345, 1350, 1390],
        })
        reader.read_sql.side_effect = [_max_ts_df(ts_values[-1]), baseline_df]

        check = RobustStatisticalOutlierCheck(
            value_column="close_px",
            group_columns=["symbol"],
            n_mad=4.0,
            min_obs=3,
        )
        result = check.run(reader, "[fx].[fact_ohlc]")

        # sorted [1330,1335,1340,1345,1350,1390] -> median=(1340+1345)/2=1342.5
        # abs dev sorted [2.5,2.5,7.5,7.5,12.5,47.5] -> mad=(7.5+7.5)/2=7.5
        assert result.status == CheckStatus.WARNING
        assert len(result.flagged) == 1
        row = result.flagged.iloc[0]
        assert row["close_px"] == 1390
        assert row["median_val"] == pytest.approx(1342.5)
        assert row["mad_val"] == pytest.approx(7.5)
        assert row["robust_z"] == pytest.approx(47.5 / (7.5 * _MAD_SCALE))
        assert result.meta["outlier_count"] == 1

    def test_min_obs_drops_thin_groups(self, reader: MagicMock) -> None:
        ts_values = pd.date_range("2025-01-01", periods=3, freq="D")
        baseline_df = pd.DataFrame({
            "symbol": ["EURUSD"] * 3,
            "ts": ts_values,
            "close_px": [1.10, 1.10, 5.0],
        })
        reader.read_sql.side_effect = [_max_ts_df(ts_values[-1]), baseline_df]

        check = RobustStatisticalOutlierCheck(
            value_column="close_px",
            group_columns=["symbol"],
            n_mad=1.0,
            min_obs=100,
        )
        result = check.run(reader, "[fx].[fact_ohlc]")

        assert result.status == CheckStatus.PASSED


class TestRobustStatisticalOutlierCheckDefaults:
    def test_default_group_columns(self) -> None:
        check = RobustStatisticalOutlierCheck(value_column="close_px")
        assert check._group_cols == ["symbol", "series"]

    def test_custom_group_columns(self) -> None:
        check = RobustStatisticalOutlierCheck(
            value_column="close_px",
            group_columns=["symbol"],
        )
        assert check._group_cols == ["symbol"]

    def test_meta_includes_all_params(self, reader: MagicMock) -> None:
        ts_values = pd.date_range("2025-01-01", periods=4, freq="D")
        baseline_df = pd.DataFrame({
            "symbol": ["EURUSD"] * 4,
            "ts": ts_values,
            "close_px": [1.10, 1.10, 1.11, 99.0],
        })
        reader.read_sql.side_effect = [_max_ts_df(ts_values[-1]), baseline_df]

        check = RobustStatisticalOutlierCheck(
            value_column="close_px",
            group_columns=["symbol"],
            n_mad=1.0,
            trailing_months=24,
            min_obs=3,
        )
        result = check.run(reader, "[fx].[fact_ohlc]")

        assert result.meta["n_mad"] == 1.0
        assert result.meta["trailing_months"] == 24
        assert result.meta["outlier_count"] == 1


# ---------------------------------------------------------------------------
# DistributionCheck
# ---------------------------------------------------------------------------

class TestDistributionCheckSQLShape:
    def test_no_percentile_cont_or_windowed_over(self, reader: MagicMock) -> None:
        stats_df = pd.DataFrame({
            "strike": ["ATM"], "n": [5], "mean_px": [1.03], "std_px": [0.11],
            "min_px": [0.9], "max_px": [1.2],
        })
        ts_values = pd.date_range("2025-01-01", periods=5, freq="D")
        pull_df = pd.DataFrame({
            "strike": ["ATM"] * 5,
            "value": [1.0, 1.1, 0.9, 1.2, 0.95],
        })
        reader.read_sql.side_effect = [stats_df, _max_ts_df(ts_values[-1]), pull_df]

        check = DistributionCheck(value_column="value", group_column="strike", ts_column="ts")
        result = check.run(reader, "[fx].[fact_vol]")

        assert reader.read_sql.call_count == 3
        for call in reader.read_sql.call_args_list:
            sql = call.args[0]
            assert "PERCENTILE_CONT" not in sql
            assert "OVER (" not in sql
            assert "SELECT DISTINCT" not in sql
        assert "p01" in result.summary.columns
        assert "p99" in result.summary.columns

    def test_percentile_pull_is_bounded_even_with_no_where(self, reader: MagicMock) -> None:
        stats_df = pd.DataFrame({
            "strike": ["ATM"], "n": [5], "mean_px": [1.03], "std_px": [0.11],
            "min_px": [0.9], "max_px": [1.2],
        })
        ts_values = pd.date_range("2025-01-01", periods=5, freq="D")
        pull_df = pd.DataFrame({
            "strike": ["ATM"] * 5,
            "value": [1.0, 1.1, 0.9, 1.2, 0.95],
        })
        reader.read_sql.side_effect = [stats_df, _max_ts_df(ts_values[-1]), pull_df]

        check = DistributionCheck(
            value_column="value", group_column="strike", ts_column="ts", trailing_months=12,
        )
        check.run(reader, "[fx].[fact_vol]")  # no `where` at all — must not full-table-scan

        pull_sql = reader.read_sql.call_args_list[2].args[0]
        assert ":baseline_start" in pull_sql
        assert ":max_ts" in pull_sql

    def test_empty_table_returns_passed_without_percentiles(self, reader: MagicMock) -> None:
        stats_df = pd.DataFrame({
            "strike": pd.array([], dtype="object"),
            "n": [], "mean_px": [], "std_px": [], "min_px": [], "max_px": [],
        })
        reader.read_sql.side_effect = [stats_df, pd.DataFrame()]

        check = DistributionCheck(value_column="value", group_column="strike", ts_column="ts")
        result = check.run(reader, "[fx].[fact_vol]")

        assert result.status == CheckStatus.PASSED
        assert reader.read_sql.call_count == 2
