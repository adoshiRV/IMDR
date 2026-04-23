"""Tests for the cross-domain staleness monitor and alert formatter."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from imdr.healthchecks.staleness import (
    DEFAULT_SPECS,
    DomainSummary,
    StaleKey,
    StalenessMonitor,
    StalenessReport,
    StalenessSpec,
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


# ── DomainSummary tests ─────────────────────────────────────────────


class TestDomainSummary:
    def test_is_stale_when_keys_stale(self) -> None:
        s = DomainSummary("D", "d.p", 10, 3, 7, date(2026, 4, 10))
        assert s.is_stale is True

    def test_not_stale_when_zero(self) -> None:
        s = DomainSummary("D", "d.p", 10, 0, 10, date(2026, 4, 13))
        assert s.is_stale is False


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


# ── StalenessAlertFormatter tests ───────────────────────────────────


class TestStalenessAlertFormatter:
    def _make_report(self, has_stale: bool = True) -> StalenessReport:
        now = datetime.now(timezone.utc)
        ref = date(2026, 4, 13)
        if has_stale:
            sk = StaleKey("Rates Curves", "rates.historical", 1, "USD / SOFR", date(2026, 3, 31), 13, 3)
            stale = DomainSummary("Rates Curves", "rates.historical", 39, 1, 38, date(2026, 4, 13), [sk])
            fresh = DomainSummary("FX Vol", "fx.vol", 17, 0, 17, date(2026, 4, 13))
            return StalenessReport(now, ref, [stale, fresh])
        else:
            f1 = DomainSummary("Rates Curves", "rates.historical", 39, 0, 39, date(2026, 4, 13))
            f2 = DomainSummary("FX Vol", "fx.vol", 17, 0, 17, date(2026, 4, 13))
            return StalenessReport(now, ref, [f1, f2])

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

    def test_body_renders_html(self) -> None:
        formatter = StalenessAlertFormatter()
        report = self._make_report(has_stale=True)
        body = formatter.format_body(report=report)
        assert "<!DOCTYPE html>" in body
        assert "IMDR" in body
        assert "USD / SOFR" in body
        assert "STALE DOMAINS" in body
        assert "HEALTHY DOMAINS" in body

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
