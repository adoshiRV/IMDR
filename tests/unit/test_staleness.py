"""Tests for the cross-domain staleness monitor and alert formatter."""

from __future__ import annotations

from datetime import date, datetime, timezone
from unittest.mock import MagicMock

import pandas as pd
import pytest

from imdr.healthchecks.staleness import (
    BreakdownRollup,
    DEFAULT_SPECS,
    DomainSummary,
    FREQUENCY_BREAKDOWN,
    StaleKey,
    StalenessMonitor,
    StalenessReport,
    StalenessSpec,
    VENDOR_BREAKDOWN,
    _build_query,
    _days_behind,
)
from imdr.notifications.formatters.staleness_alert import StalenessAlertFormatter


# ── Fixtures ────────────────────────────────────────────────────────


def _make_spec(**overrides) -> StalenessSpec:
    """Build a StalenessSpec with sensible defaults, overridden by kwargs."""
    defaults = dict(
        domain="Test Domain",
        pipeline_name="test.pipeline",
        table="[test].[fact_data]",
        date_column="obs_date",
        key_column="key_id",
        dim_table="[test].[dim_key]",
        dim_join_col="id",
        dim_label_cols=("name",),
        max_stale_days=3,
    )
    defaults.update(overrides)
    return StalenessSpec(**defaults)


def _make_reader_df(
    keys: list[tuple], latest_dates: list[date]
) -> pd.DataFrame:
    """Build a DataFrame mimicking the SQL query result."""
    rows = []
    for key, dt in zip(keys, latest_dates):
        if isinstance(key, tuple):
            label = " / ".join(str(k) for k in key)
        else:
            label = str(key)
        rows.append({"key_id": key[0] if isinstance(key, tuple) else key, "label": label, "latest_date": dt})
    return pd.DataFrame(rows)


def _make_breakdown_df(rows: list[dict]) -> pd.DataFrame:
    """Mimic a SQL result with breakdown columns.

    Each row dict supplies key_id, label, latest_date, and any
    breakdown alias columns (e.g. vendor_code, vendor_name,
    frequency_code, frequency_name).
    """
    return pd.DataFrame(rows)


# ── StalenessSpec tests ─────────────────────────────────────────────


class TestStalenessSpec:
    def test_frozen(self) -> None:
        spec = _make_spec()
        with pytest.raises(AttributeError):
            spec.domain = "changed"  # type: ignore[misc]

    def test_defaults(self) -> None:
        spec = StalenessSpec(
            domain="X",
            pipeline_name="x.y",
            table="[x].[y]",
            date_column="dt",
            key_column="kid",
        )
        assert spec.max_stale_days == 3
        assert spec.dim_table is None
        assert spec.dim_label_cols == ()
        assert spec.breakdowns == ()
        assert spec.has_breakdowns is False
        assert spec.has_dim is False

    def test_has_breakdowns(self) -> None:
        spec = _make_spec(breakdowns=(VENDOR_BREAKDOWN,))
        assert spec.has_breakdowns is True


# ── DomainSummary tests ─────────────────────────────────────────────


class TestDomainSummary:
    def test_is_stale_when_keys_stale(self) -> None:
        s = DomainSummary("D", "d.p", 10, 3, 7, date(2026, 4, 10))
        assert s.is_stale is True

    def test_not_stale_when_zero(self) -> None:
        s = DomainSummary("D", "d.p", 10, 0, 10, date(2026, 4, 13))
        assert s.is_stale is False

    def test_rollup_returns_empty_for_unknown_dim(self) -> None:
        s = DomainSummary("D", "d.p", 10, 0, 10, date(2026, 4, 13))
        assert s.rollup("vendor") == []
        assert s.has_breakdowns is False


# ── StalenessReport tests ───────────────────────────────────────────


class TestStalenessReport:
    def test_has_stale(self) -> None:
        stale = DomainSummary("A", "a.a", 5, 2, 3, date(2026, 4, 10))
        fresh = DomainSummary("B", "b.b", 5, 0, 5, date(2026, 4, 13))
        report = StalenessReport(
            checked_at=datetime.now(timezone.utc),
            reference_date=date(2026, 4, 13),
            summaries=[stale, fresh],
        )
        assert report.has_stale is True
        assert report.total_stale_keys == 2
        assert len(report.stale_domains) == 1
        assert len(report.healthy_domains) == 1

    def test_all_fresh(self) -> None:
        fresh1 = DomainSummary("A", "a.a", 5, 0, 5, date(2026, 4, 13))
        fresh2 = DomainSummary("B", "b.b", 3, 0, 3, date(2026, 4, 13))
        report = StalenessReport(
            checked_at=datetime.now(timezone.utc),
            reference_date=date(2026, 4, 13),
            summaries=[fresh1, fresh2],
        )
        assert report.has_stale is False
        assert report.total_stale_keys == 0

    def test_all_stale_keys_sorted(self) -> None:
        sk1 = StaleKey("A", "a.a", 1, "USD SOFR", date(2026, 3, 31), 13, 3)
        sk2 = StaleKey("A", "a.a", 2, "CAD CORRA", date(2026, 3, 31), 13, 3)
        sk3 = StaleKey("B", "b.b", 3, "EURUSD", date(2026, 4, 10), 3, 3)
        s1 = DomainSummary("A", "a.a", 10, 2, 8, date(2026, 4, 13), [sk1, sk2])
        s2 = DomainSummary("B", "b.b", 5, 1, 4, date(2026, 4, 13), [sk3])
        report = StalenessReport(
            checked_at=datetime.now(timezone.utc),
            reference_date=date(2026, 4, 13),
            summaries=[s1, s2],
        )
        all_keys = report.all_stale_keys()
        assert len(all_keys) == 3
        assert all_keys[0].days_behind >= all_keys[-1].days_behind

    def test_breakdown_totals_aggregates_across_domains(self) -> None:
        r1 = BreakdownRollup("vendor", "bloomberg", "Bloomberg", 5, 3, 2, date(2026, 4, 1))
        r2 = BreakdownRollup("vendor", "citi_velocity", "Citi", 5, 0, 5, date(2026, 4, 13))
        r3 = BreakdownRollup("vendor", "bloomberg", "Bloomberg", 4, 2, 2, date(2026, 4, 1))
        s1 = DomainSummary("A", "a.a", 10, 3, 7, date(2026, 4, 13), by_breakdown={"vendor": [r1, r2]})
        s2 = DomainSummary("B", "b.b", 4, 2, 2, date(2026, 4, 13), by_breakdown={"vendor": [r3]})
        report = StalenessReport(
            checked_at=datetime.now(timezone.utc),
            reference_date=date(2026, 4, 13),
            summaries=[s1, s2],
        )
        totals = report.breakdown_totals("vendor")
        assert totals == {"bloomberg": 5}

    def test_breakdown_totals_empty_for_unknown_dim(self) -> None:
        r1 = BreakdownRollup("vendor", "bloomberg", "Bloomberg", 5, 3, 2, date(2026, 4, 1))
        s1 = DomainSummary("A", "a.a", 5, 3, 2, date(2026, 4, 13), by_breakdown={"vendor": [r1]})
        report = StalenessReport(datetime.now(timezone.utc), date(2026, 4, 13), [s1])
        assert report.breakdown_totals("frequency") == {}


# ── _build_query tests ──────────────────────────────────────────────


class TestBuildQuery:
    def test_no_dim_no_breakdowns(self) -> None:
        spec = _make_spec(dim_table=None, dim_label_cols=())
        sql = _build_query(spec)
        assert "JOIN" not in sql
        assert "GROUP BY f.[key_id]" in sql

    def test_with_dim(self) -> None:
        spec = _make_spec()
        sql = _build_query(spec)
        assert "JOIN [test].[dim_key] d" in sql
        assert "d.[name]" in sql
        assert "GROUP BY f.[key_id], d.[name]" in sql

    def test_with_dim_filter(self) -> None:
        spec = _make_spec(dim_filter="status <> 'ceased'")
        sql = _build_query(spec)
        assert "WHERE d.status <> 'ceased'" in sql

    def test_with_vendor_breakdown(self) -> None:
        spec = _make_spec(breakdowns=(VENDOR_BREAKDOWN,))
        sql = _build_query(spec)
        assert "JOIN [dbo].[dim_vendor] b0" in sql
        assert "b0.[vendor_code] AS vendor_code" in sql
        assert "b0.[display_name] AS vendor_name" in sql
        # Vendor cols should be in GROUP BY
        assert "b0.[vendor_code]" in sql.split("GROUP BY")[1]

    def test_with_two_breakdowns(self) -> None:
        spec = _make_spec(breakdowns=(VENDOR_BREAKDOWN, FREQUENCY_BREAKDOWN))
        sql = _build_query(spec)
        assert "JOIN [dbo].[dim_vendor] b0" in sql
        assert "JOIN [dbo].[dim_frequency] b1" in sql
        assert "b0.[vendor_code] AS vendor_code" in sql
        assert "b1.[frequency_code] AS frequency_code" in sql


# ── StalenessMonitor tests ──────────────────────────────────────────


class TestStalenessMonitor:
    def test_all_fresh(self) -> None:
        """When all keys are within threshold, no staleness is flagged."""
        reader = MagicMock()
        today = date(2026, 4, 13)
        df = _make_reader_df(
            keys=[(1,), (2,), (3,)],
            latest_dates=[date(2026, 4, 13), date(2026, 4, 12), date(2026, 4, 11)],
        )
        reader.read_sql.return_value = df

        spec = _make_spec(max_stale_days=3)
        monitor = StalenessMonitor(reader, specs=[spec], reference_date=today)
        report = monitor.run()

        assert report.has_stale is False
        assert report.summaries[0].stale_keys == 0
        assert report.summaries[0].fresh_keys == 3

    def test_some_stale(self) -> None:
        """Keys older than threshold are flagged."""
        reader = MagicMock()
        today = date(2026, 4, 13)
        df = _make_reader_df(
            keys=[(1,), (2,), (3,)],
            latest_dates=[date(2026, 4, 13), date(2026, 3, 31), date(2026, 4, 2)],
        )
        reader.read_sql.return_value = df

        spec = _make_spec(max_stale_days=3)
        monitor = StalenessMonitor(reader, specs=[spec], reference_date=today)
        report = monitor.run()

        assert report.has_stale is True
        summary = report.summaries[0]
        assert summary.stale_keys == 2
        assert summary.fresh_keys == 1
        # Worst stale key should be key 2 (Mar 31 = 13 days behind)
        assert summary.stale_items[0].days_behind == 13

    def test_all_stale(self) -> None:
        reader = MagicMock()
        today = date(2026, 4, 13)
        df = _make_reader_df(
            keys=[(1,), (2,)],
            latest_dates=[date(2026, 3, 1), date(2026, 3, 15)],
        )
        reader.read_sql.return_value = df

        spec = _make_spec(max_stale_days=3)
        monitor = StalenessMonitor(reader, specs=[spec], reference_date=today)
        report = monitor.run()

        assert report.has_stale is True
        assert report.summaries[0].stale_keys == 2
        assert report.summaries[0].fresh_keys == 0

    def test_empty_table(self) -> None:
        """Empty fact table returns zero keys, no crash."""
        reader = MagicMock()
        reader.read_sql.return_value = pd.DataFrame()

        spec = _make_spec()
        monitor = StalenessMonitor(reader, specs=[spec], reference_date=date(2026, 4, 13))
        report = monitor.run()

        summary = report.summaries[0]
        assert summary.total_keys == 0
        assert summary.stale_keys == 0
        assert summary.latest_date is None
        assert report.has_stale is False

    def test_no_dim_table(self) -> None:
        """Spec with no dim_table uses key_column as label."""
        reader = MagicMock()
        df = pd.DataFrame({
            "key_id": ["VIX", "VIX3M"],
            "label": ["VIX", "VIX3M"],
            "latest_date": [date(2026, 4, 13), date(2026, 4, 13)],
        })
        reader.read_sql.return_value = df

        spec = _make_spec(dim_table=None, dim_label_cols=())
        monitor = StalenessMonitor(reader, specs=[spec], reference_date=date(2026, 4, 13))
        report = monitor.run()

        assert report.has_stale is False
        assert report.summaries[0].total_keys == 2

    def test_multiple_specs(self) -> None:
        """Multiple specs are checked independently."""
        reader = MagicMock()

        fresh_df = _make_reader_df([(1,)], [date(2026, 4, 13)])
        stale_df = _make_reader_df([(1,)], [date(2026, 3, 1)])
        reader.read_sql.side_effect = [fresh_df, stale_df]

        spec_fresh = _make_spec(domain="Fresh Domain", pipeline_name="fresh.p")
        spec_stale = _make_spec(domain="Stale Domain", pipeline_name="stale.p")
        monitor = StalenessMonitor(reader, specs=[spec_fresh, spec_stale], reference_date=date(2026, 4, 13))
        report = monitor.run()

        assert report.has_stale is True
        assert len(report.stale_domains) == 1
        assert report.stale_domains[0].domain == "Stale Domain"
        assert len(report.healthy_domains) == 1
        assert report.healthy_domains[0].domain == "Fresh Domain"

    def test_query_failure_handled_gracefully(self) -> None:
        """DB error for one spec doesn't crash the monitor."""
        reader = MagicMock()
        reader.read_sql.side_effect = Exception("connection refused")

        spec = _make_spec()
        monitor = StalenessMonitor(reader, specs=[spec], reference_date=date(2026, 4, 13))
        report = monitor.run()

        assert len(report.summaries) == 1
        assert report.summaries[0].total_keys == 0
        assert report.has_stale is False

    def test_stale_key_label_from_dim(self) -> None:
        """Labels come from the dim table join."""
        reader = MagicMock()
        df = pd.DataFrame({
            "key_id": [1, 2],
            "label": ["USD / SOFR", "CAD / CORRA"],
            "ccy": ["USD", "CAD"],
            "curve": ["SOFR", "CORRA"],
            "latest_date": [date(2026, 3, 31), date(2026, 3, 31)],
        })
        reader.read_sql.return_value = df

        spec = _make_spec(max_stale_days=3)
        monitor = StalenessMonitor(reader, specs=[spec], reference_date=date(2026, 4, 13))
        report = monitor.run()

        items = report.summaries[0].stale_items
        assert len(items) == 2
        assert items[0].label == "USD / SOFR"
        assert items[1].label == "CAD / CORRA"

    def test_boundary_exactly_at_threshold(self) -> None:
        """Key exactly at threshold boundary is NOT stale."""
        reader = MagicMock()
        today = date(2026, 4, 13)
        # 3 days behind with max_stale_days=3 -> cutoff = Apr 10
        # latest_date = Apr 10 -> NOT stale (>= cutoff)
        df = _make_reader_df([(1,)], [date(2026, 4, 10)])
        reader.read_sql.return_value = df

        spec = _make_spec(max_stale_days=3)
        monitor = StalenessMonitor(reader, specs=[spec], reference_date=today)
        report = monitor.run()

        assert report.has_stale is False

    def test_boundary_one_day_past_threshold(self) -> None:
        """Key one day past threshold IS stale."""
        reader = MagicMock()
        today = date(2026, 4, 13)
        # cutoff = Apr 10, latest = Apr 9 -> stale
        df = _make_reader_df([(1,)], [date(2026, 4, 9)])
        reader.read_sql.return_value = df

        spec = _make_spec(max_stale_days=3)
        monitor = StalenessMonitor(reader, specs=[spec], reference_date=today)
        report = monitor.run()

        assert report.has_stale is True
        assert report.summaries[0].stale_items[0].days_behind == 4


# ── Business-day age tests ──────────────────────────────────────────


class TestDaysBehind:
    def test_calendar_mode_is_plain_subtraction(self) -> None:
        # 2026-04-13 is a Monday, 2026-04-10 a Friday.
        assert _days_behind(date(2026, 4, 10), date(2026, 4, 13)) == 3

    def test_same_day_is_zero(self) -> None:
        assert _days_behind(date(2026, 4, 13), date(2026, 4, 13)) == 0

    def test_future_latest_is_zero(self) -> None:
        assert _days_behind(date(2026, 4, 14), date(2026, 4, 13)) == 0

    def test_business_mode_ignores_weekend(self) -> None:
        # Friday obs checked Monday = 1 business day behind, not 3.
        assert _days_behind(date(2026, 4, 10), date(2026, 4, 13), business_days=True) == 1

    def test_business_mode_thursday_to_monday(self) -> None:
        # Thu -> Mon: Fri + Mon = 2 business days.
        assert _days_behind(date(2026, 4, 9), date(2026, 4, 13), business_days=True) == 2

    def test_business_mode_midweek(self) -> None:
        # Wed -> Fri (same week): Thu + Fri = 2 business days.
        assert _days_behind(date(2026, 4, 8), date(2026, 4, 10), business_days=True) == 2


class TestBusinessDayStaleness:
    def test_friday_obs_on_monday_not_stale(self) -> None:
        """A weekday-only feed read on Monday must not flag Friday data."""
        reader = MagicMock()
        monday = date(2026, 4, 13)
        df = _make_reader_df([(1,)], [date(2026, 4, 10)])  # Friday
        reader.read_sql.return_value = df

        spec = _make_spec(max_stale_days=2, business_days=True)
        monitor = StalenessMonitor(reader, specs=[spec], reference_date=monday)
        report = monitor.run()

        assert report.has_stale is False

    def test_genuine_stall_flags_in_business_mode(self) -> None:
        """Three business days behind clears a 2-business-day threshold."""
        reader = MagicMock()
        monday = date(2026, 4, 13)
        df = _make_reader_df([(1,)], [date(2026, 4, 8)])  # prior Wednesday
        reader.read_sql.return_value = df

        spec = _make_spec(max_stale_days=2, business_days=True)
        monitor = StalenessMonitor(reader, specs=[spec], reference_date=monday)
        report = monitor.run()

        assert report.has_stale is True
        # Wed -> Mon = Thu, Fri, Mon = 3 business days.
        assert report.summaries[0].stale_items[0].days_behind == 3


# ── Breakdown-aware tests ───────────────────────────────────────────


class TestBreakdownAggregation:
    def test_vendor_breakdown_splits_stale_per_vendor(self) -> None:
        """Same key can be fresh from one vendor and stale from another."""
        reader = MagicMock()
        today = date(2026, 4, 13)
        # Curve 1: Citi fresh, BBG stale.  Curve 2: both fresh.
        df = _make_breakdown_df([
            {"key_id": 1, "label": "USD / SOFR", "vendor_code": "citi_velocity",
             "vendor_name": "Citi", "latest_date": date(2026, 4, 13)},
            {"key_id": 1, "label": "USD / SOFR", "vendor_code": "bloomberg",
             "vendor_name": "Bloomberg", "latest_date": date(2026, 3, 31)},
            {"key_id": 2, "label": "EUR / ESTR", "vendor_code": "citi_velocity",
             "vendor_name": "Citi", "latest_date": date(2026, 4, 13)},
            {"key_id": 2, "label": "EUR / ESTR", "vendor_code": "bloomberg",
             "vendor_name": "Bloomberg", "latest_date": date(2026, 4, 12)},
        ])
        reader.read_sql.return_value = df

        spec = _make_spec(breakdowns=(VENDOR_BREAKDOWN,))
        monitor = StalenessMonitor(reader, specs=[spec], reference_date=today)
        report = monitor.run()

        summary = report.summaries[0]
        assert summary.total_keys == 4  # one row per (key, vendor)
        assert summary.stale_keys == 1  # only USD/SOFR-bbg

        rollups = summary.rollup("vendor")
        assert len(rollups) == 2
        by_code = {r.code: r for r in rollups}
        assert by_code["bloomberg"].stale_keys == 1
        assert by_code["bloomberg"].fresh_keys == 1
        assert by_code["citi_velocity"].stale_keys == 0
        assert by_code["citi_velocity"].fresh_keys == 2

        # Stale item carries vendor info
        sk = summary.stale_items[0]
        assert sk.breakdown_code("vendor") == "bloomberg"
        assert sk.breakdown_name("vendor") == "Bloomberg"

    def test_two_breakdowns_independent_rollups(self) -> None:
        """Vendor and frequency rollups are computed from the same rows."""
        reader = MagicMock()
        today = date(2026, 4, 13)
        # Two curves, two vendors, two frequencies -> 8 rows.
        # Make HOURLY-bbg the only stale combo.
        rows = []
        for kid in (1, 2):
            for vendor in ("citi_velocity", "bloomberg"):
                for freq in ("DAILY", "HOURLY"):
                    is_stale = (vendor == "bloomberg" and freq == "HOURLY")
                    rows.append({
                        "key_id": kid,
                        "label": f"key{kid}",
                        "vendor_code": vendor,
                        "vendor_name": vendor.title(),
                        "frequency_code": freq,
                        "frequency_name": freq.title(),
                        "latest_date": date(2026, 3, 1) if is_stale else date(2026, 4, 13),
                    })
        reader.read_sql.return_value = pd.DataFrame(rows)

        spec = _make_spec(breakdowns=(VENDOR_BREAKDOWN, FREQUENCY_BREAKDOWN))
        monitor = StalenessMonitor(reader, specs=[spec], reference_date=today)
        report = monitor.run()

        summary = report.summaries[0]
        assert summary.total_keys == 8
        assert summary.stale_keys == 2  # bbg+HOURLY for both keys

        vendor_rollup = {r.code: r for r in summary.rollup("vendor")}
        assert vendor_rollup["bloomberg"].stale_keys == 2
        assert vendor_rollup["citi_velocity"].stale_keys == 0

        freq_rollup = {r.code: r for r in summary.rollup("frequency")}
        assert freq_rollup["HOURLY"].stale_keys == 2
        assert freq_rollup["DAILY"].stale_keys == 0

    def test_no_breakdowns_means_no_rollups(self) -> None:
        reader = MagicMock()
        df = _make_reader_df([(1,)], [date(2026, 4, 13)])
        reader.read_sql.return_value = df

        spec = _make_spec()
        monitor = StalenessMonitor(reader, specs=[spec], reference_date=date(2026, 4, 13))
        report = monitor.run()

        assert report.summaries[0].by_breakdown == {}


# ── StalenessMonitor.from_config tests ──────────────────────────────


class TestStalenessMonitorFactory:
    def test_from_config_uses_default_specs(self) -> None:
        connector = MagicMock()
        connector.read_engine = MagicMock()
        monitor = StalenessMonitor.from_config(connector)
        assert len(monitor._specs) == len(DEFAULT_SPECS)

    def test_from_config_custom_specs(self) -> None:
        connector = MagicMock()
        connector.read_engine = MagicMock()
        custom = [_make_spec(domain="Custom")]
        monitor = StalenessMonitor.from_config(connector, specs=custom)
        assert len(monitor._specs) == 1
        assert monitor._specs[0].domain == "Custom"


# ── DEFAULT_SPECS validation ────────────────────────────────────────


class TestDefaultSpecs:
    def test_all_specs_have_required_fields(self) -> None:
        for spec in DEFAULT_SPECS:
            assert spec.domain, f"Missing domain in spec for {spec.pipeline_name}"
            assert spec.pipeline_name
            assert spec.table.startswith("[")
            assert spec.date_column
            assert spec.key_column
            assert spec.max_stale_days > 0

    def test_expected_domains_covered(self) -> None:
        domains = {s.pipeline_name for s in DEFAULT_SPECS}
        expected = {
            "rates.historical",
            "rates.vol",
            "rates.skew_barclays_daily",
            "rates.bench_rates",
            "fx.citi_rate",
            "fx.vol",
            "commodities.spot",
            "commodities.vol",
            "commodities.eia",
            "equity.index",
            "equity.vix",
        }
        assert expected == domains

    def test_eia_has_longer_threshold(self) -> None:
        eia = [s for s in DEFAULT_SPECS if s.pipeline_name == "commodities.eia"][0]
        assert eia.max_stale_days == 10

    def test_weekday_market_feeds_business_day_mode(self) -> None:
        """Daily weekday-only market feeds use business-day age, 2-day floor."""
        for pipeline in ("rates.historical", "equity.index", "equity.vix"):
            spec = next(s for s in DEFAULT_SPECS if s.pipeline_name == pipeline)
            assert spec.business_days is True, f"{pipeline} should be business-day"
            assert spec.max_stale_days == 2, f"{pipeline} threshold should be 2"

    def test_calendar_specs_stay_calendar(self) -> None:
        """Calendar-cadence feeds must not silently switch to business days."""
        for pipeline in ("commodities.eia", "commodities.spot"):
            spec = next(s for s in DEFAULT_SPECS if s.pipeline_name == pipeline)
            assert spec.business_days is False

    def test_dual_vendor_specs_have_vendor_breakdown(self) -> None:
        """rates.historical and fx.citi_rate ingest from multiple vendors."""
        for pipeline in ("rates.historical", "fx.citi_rate"):
            spec = next(s for s in DEFAULT_SPECS if s.pipeline_name == pipeline)
            assert VENDOR_BREAKDOWN in spec.breakdowns, (
                f"{pipeline} should have vendor breakdown"
            )

    def test_hourly_capable_specs_have_frequency_breakdown(self) -> None:
        """rates.historical and fx.citi_rate carry frequency_id."""
        for pipeline in ("rates.historical", "fx.citi_rate"):
            spec = next(s for s in DEFAULT_SPECS if s.pipeline_name == pipeline)
            assert FREQUENCY_BREAKDOWN in spec.breakdowns, (
                f"{pipeline} should have frequency breakdown"
            )


# ── StalenessAlertFormatter tests ───────────────────────────────────


class TestStalenessAlertFormatter:
    def _make_report(self, has_stale: bool = True) -> StalenessReport:
        now = datetime.now(timezone.utc)
        ref = date(2026, 4, 13)
        if has_stale:
            sk = StaleKey("Rates Curves", "rates.historical", 1, "USD / SOFR",
                          date(2026, 3, 31), 13, 3)
            stale = DomainSummary("Rates Curves", "rates.historical", 39, 1, 38,
                                  date(2026, 4, 13), [sk])
            fresh = DomainSummary("FX Vol", "fx.vol", 17, 0, 17, date(2026, 4, 13))
            return StalenessReport(now, ref, [stale, fresh])
        else:
            f1 = DomainSummary("Rates Curves", "rates.historical", 39, 0, 39, date(2026, 4, 13))
            f2 = DomainSummary("FX Vol", "fx.vol", 17, 0, 17, date(2026, 4, 13))
            return StalenessReport(now, ref, [f1, f2])

    def _make_breakdown_report(self) -> StalenessReport:
        """Report with vendor + frequency breakdowns."""
        now = datetime.now(timezone.utc)
        ref = date(2026, 4, 13)
        sk = StaleKey(
            "Rates Curves", "rates.historical", 1, "USD / SOFR",
            date(2026, 3, 31), 13, 3,
            breakdowns={
                "vendor": ("bloomberg", "Bloomberg"),
                "frequency": ("HOURLY", "Hourly"),
            },
        )
        v_rollups = [
            BreakdownRollup("vendor", "bloomberg", "Bloomberg", 4, 1, 3, date(2026, 4, 13)),
            BreakdownRollup("vendor", "citi_velocity", "Citi", 4, 0, 4, date(2026, 4, 13)),
        ]
        f_rollups = [
            BreakdownRollup("frequency", "DAILY", "Daily", 4, 0, 4, date(2026, 4, 13)),
            BreakdownRollup("frequency", "HOURLY", "Hourly", 4, 1, 3, date(2026, 4, 13)),
        ]
        s = DomainSummary(
            "Rates Curves", "rates.historical", 8, 1, 7, date(2026, 4, 13),
            stale_items=[sk],
            by_breakdown={"vendor": v_rollups, "frequency": f_rollups},
        )
        return StalenessReport(now, ref, [s])

    def test_subject_when_stale(self) -> None:
        formatter = StalenessAlertFormatter()
        report = self._make_report(has_stale=True)
        subject = formatter.format_subject(report=report)
        assert "[IMDR] STALENESS ALERT" in subject
        assert "1 stale key(s)" in subject
        assert "1 domain(s)" in subject

    def test_subject_when_fresh(self) -> None:
        formatter = StalenessAlertFormatter()
        report = self._make_report(has_stale=False)
        subject = formatter.format_subject(report=report)
        assert "OK" in subject
        assert "All domains fresh" in subject

    def test_subject_includes_breakdown_totals(self) -> None:
        formatter = StalenessAlertFormatter()
        report = self._make_breakdown_report()
        subject = formatter.format_subject(report=report)
        assert "vendor: bloomberg=1" in subject
        assert "frequency: HOURLY=1" in subject

    def test_body_renders_html(self) -> None:
        formatter = StalenessAlertFormatter()
        report = self._make_report(has_stale=True)
        body = formatter.format_body(report=report)
        assert "<!DOCTYPE html>" in body
        assert "IMDR" in body
        assert "USD / SOFR" in body
        assert "STALE DOMAINS" in body
        assert "HEALTHY DOMAINS" in body

    def test_body_renders_breakdown_section(self) -> None:
        formatter = StalenessAlertFormatter()
        report = self._make_breakdown_report()
        body = formatter.format_body(report=report)
        assert "By Vendor" in body
        assert "By Frequency" in body
        assert "bloomberg" in body
        assert "HOURLY" in body
        # Stale-by-breakdown row in summary
        assert "Stale by Vendor" in body
        assert "Stale by Frequency" in body

    def test_body_per_key_table_includes_breakdown_columns(self) -> None:
        formatter = StalenessAlertFormatter()
        report = self._make_breakdown_report()
        body = formatter.format_body(report=report)
        # Per-key detail table should show the codes
        assert ">bloomberg<" in body or ">bloomberg " in body
        assert ">HOURLY<" in body or ">HOURLY " in body

    def test_body_all_fresh(self) -> None:
        formatter = StalenessAlertFormatter()
        report = self._make_report(has_stale=False)
        body = formatter.format_body(report=report)
        assert "ALL FRESH" in body
        assert "STALE DOMAINS" not in body

    def test_body_none_report(self) -> None:
        formatter = StalenessAlertFormatter()
        body = formatter.format_body(report=None)
        assert "No staleness report" in body

    def test_body_days_behind_color_coding(self) -> None:
        """Keys > 7 days behind should get red styling."""
        sk = StaleKey("D", "d.p", 1, "KEY1", date(2026, 3, 31), 13, 3)
        stale = DomainSummary("D", "d.p", 1, 1, 0, date(2026, 3, 31), [sk])
        report = StalenessReport(
            datetime.now(timezone.utc),
            date(2026, 4, 13),
            [stale],
        )
        formatter = StalenessAlertFormatter()
        body = formatter.format_body(report=report)
        assert "color:#c0392b" in body  # Red for >7 days

    def test_multiple_stale_domains(self) -> None:
        sk1 = StaleKey("A", "a.p", 1, "KEY1", date(2026, 3, 31), 13, 3)
        sk2 = StaleKey("B", "b.p", 2, "KEY2", date(2026, 4, 5), 8, 3)
        s1 = DomainSummary("A", "a.p", 5, 1, 4, date(2026, 4, 13), [sk1])
        s2 = DomainSummary("B", "b.p", 3, 1, 2, date(2026, 4, 13), [sk2])
        report = StalenessReport(datetime.now(timezone.utc), date(2026, 4, 13), [s1, s2])

        formatter = StalenessAlertFormatter()
        subject = formatter.format_subject(report=report)
        assert "2 stale key(s)" in subject
        assert "2 domain(s)" in subject

        body = formatter.format_body(report=report)
        assert "KEY1" in body
        assert "KEY2" in body
