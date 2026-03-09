"""Tests for health check framework."""

from __future__ import annotations

from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from imdr.healthchecks.base import CheckStatus, HealthCheckRunner
from imdr.healthchecks.checks import (
    DuplicateCheck,
    FreshnessCheck,
    NullCheck,
    RowCountCheck,
    ValueRangeCheck,
)


class FakeModel:
    """Fake ORM model for testing checks.

    Uses MagicMock for columns so SQLAlchemy-style method calls
    (e.g. col.is_(None)) work in unit tests.
    """

    id = MagicMock()
    rate_date = MagicMock()
    mid = MagicMock()
    base_currency = MagicMock()
    quote_currency = MagicMock()
    created_at = MagicMock()


class TestRowCountCheck:
    def test_passes_when_enough_rows(self) -> None:
        session = MagicMock()
        session.query.return_value.filter.return_value.scalar.return_value = 10
        check = RowCountCheck(FakeModel, "rate_date", expected_min=5)
        result = check.run(session, run_date=date(2025, 1, 1))
        assert result.status == CheckStatus.PASSED
        assert result.details["actual"] == 10

    def test_fails_when_too_few_rows(self) -> None:
        session = MagicMock()
        session.query.return_value.filter.return_value.scalar.return_value = 2
        check = RowCountCheck(FakeModel, "rate_date", expected_min=5)
        result = check.run(session, run_date=date(2025, 1, 1))
        assert result.status == CheckStatus.FAILED

    def test_fails_when_zero_rows(self) -> None:
        session = MagicMock()
        session.query.return_value.filter.return_value.scalar.return_value = 0
        check = RowCountCheck(FakeModel, "rate_date", expected_min=1)
        result = check.run(session, run_date=date(2025, 1, 1))
        assert result.status == CheckStatus.FAILED


class TestNullCheck:
    def test_passes_when_no_nulls(self) -> None:
        session = MagicMock()
        # Single query returns tuple of null counts (all zero)
        session.query.return_value.filter.return_value.one.return_value = (0, 0)
        check = NullCheck(FakeModel, ["mid", "base_currency"], "rate_date")
        result = check.run(session, run_date=date(2025, 1, 1))
        assert result.status == CheckStatus.PASSED

    def test_fails_when_nulls_found(self) -> None:
        session = MagicMock()
        # Single query returns tuple: mid has 3 nulls, base_currency has 0
        session.query.return_value.filter.return_value.one.return_value = (3, 0)
        check = NullCheck(FakeModel, ["mid", "base_currency"], "rate_date")
        result = check.run(session, run_date=date(2025, 1, 1))
        assert result.status == CheckStatus.FAILED
        assert "mid" in result.details["null_counts"]


class TestDuplicateCheck:
    def test_passes_when_no_duplicates(self) -> None:
        session = MagicMock()
        session.query.return_value.filter.return_value.group_by.return_value.having.return_value.all.return_value = []
        check = DuplicateCheck(FakeModel, ["base_currency", "quote_currency", "rate_date"], "rate_date")
        result = check.run(session, run_date=date(2025, 1, 1))
        assert result.status == CheckStatus.PASSED

    def test_fails_when_duplicates_found(self) -> None:
        session = MagicMock()
        session.query.return_value.filter.return_value.group_by.return_value.having.return_value.all.return_value = [
            ("USD", "EUR", date(2025, 1, 1), 2),
        ]
        check = DuplicateCheck(FakeModel, ["base_currency", "quote_currency", "rate_date"], "rate_date")
        result = check.run(session, run_date=date(2025, 1, 1))
        assert result.status == CheckStatus.FAILED


class TestFreshnessCheck:
    def test_passes_when_fresh(self) -> None:
        session = MagicMock()
        session.query.return_value.scalar.return_value = datetime.now(timezone.utc)
        check = FreshnessCheck(FakeModel, "created_at", max_staleness_hours=24)
        result = check.run(session)
        assert result.status == CheckStatus.PASSED

    def test_warns_when_stale(self) -> None:
        session = MagicMock()
        # 48 hours ago
        from datetime import timedelta
        stale_time = datetime.now(timezone.utc) - timedelta(hours=48)
        session.query.return_value.scalar.return_value = stale_time
        check = FreshnessCheck(FakeModel, "created_at", max_staleness_hours=24)
        result = check.run(session)
        assert result.status == CheckStatus.WARNING

    def test_fails_when_no_records(self) -> None:
        session = MagicMock()
        session.query.return_value.scalar.return_value = None
        check = FreshnessCheck(FakeModel, "created_at", max_staleness_hours=24)
        result = check.run(session)
        assert result.status == CheckStatus.FAILED


class TestValueRangeCheck:
    def test_passes_when_in_range(self) -> None:
        session = MagicMock()
        session.query.return_value.filter.return_value.one.return_value = (0.5, 5.0)
        check = ValueRangeCheck(FakeModel, "mid", 0.0001, 10000.0, "rate_date")
        result = check.run(session, run_date=date(2025, 1, 1))
        assert result.status == CheckStatus.PASSED

    def test_fails_when_out_of_range(self) -> None:
        session = MagicMock()
        session.query.return_value.filter.return_value.one.return_value = (-1.0, 5.0)
        check = ValueRangeCheck(FakeModel, "mid", 0.0001, 10000.0, "rate_date")
        result = check.run(session, run_date=date(2025, 1, 1))
        assert result.status == CheckStatus.FAILED

    def test_warns_when_no_values(self) -> None:
        session = MagicMock()
        session.query.return_value.filter.return_value.one.return_value = (None, None)
        check = ValueRangeCheck(FakeModel, "mid", 0.0001, 10000.0, "rate_date")
        result = check.run(session, run_date=date(2025, 1, 1))
        assert result.status == CheckStatus.WARNING


class TestHealthCheckRunner:
    def test_all_pass(self) -> None:
        session = MagicMock()
        session.query.return_value.filter.return_value.scalar.return_value = 10
        checks = [RowCountCheck(FakeModel, "rate_date", expected_min=1)]
        runner = HealthCheckRunner(checks)
        report = runner.run_all(session, run_date=date(2025, 1, 1))
        assert report.passed is True
        assert len(report.results) == 1

    def test_report_to_dict(self) -> None:
        session = MagicMock()
        session.query.return_value.filter.return_value.scalar.return_value = 10
        checks = [RowCountCheck(FakeModel, "rate_date", expected_min=1)]
        runner = HealthCheckRunner(checks)
        report = runner.run_all(session, run_date=date(2025, 1, 1))
        d = report.to_dict()
        assert d["passed"] is True
        assert len(d["checks"]) == 1
        assert d["checks"][0]["name"] == "row_count"
