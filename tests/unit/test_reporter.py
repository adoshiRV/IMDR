"""Tests for the post-append reporter."""

from __future__ import annotations

from datetime import date, datetime, timezone
from unittest.mock import MagicMock

from imdr.reporting.reporter import AppendVerification, PipelineReporter, SuccessReport
from imdr.healthchecks.base import HealthReport
from imdr.models.audit import RunStatus


class FakeModel:
    id = "id"
    rate_date = "rate_date"
    created_at = "created_at"


class TestPipelineReporter:
    def test_verify_append_all_rows_present(self) -> None:
        session = MagicMock()
        session.query.return_value.filter.return_value.scalar.return_value = 50
        now = datetime.now(timezone.utc)
        session.query.return_value.filter.return_value.one.return_value = (now, now)

        reporter = PipelineReporter(session, FakeModel, "rate_date")
        result = reporter.verify_append(date(2025, 1, 1), expected_count=50)

        assert result.rows_verified == 50
        assert result.missing == 0
        assert result.timestamp_range is not None

    def test_verify_append_missing_rows(self) -> None:
        session = MagicMock()
        session.query.return_value.filter.return_value.scalar.return_value = 40
        now = datetime.now(timezone.utc)
        session.query.return_value.filter.return_value.one.return_value = (now, now)

        reporter = PipelineReporter(session, FakeModel, "rate_date")
        result = reporter.verify_append(date(2025, 1, 1), expected_count=50)

        assert result.rows_verified == 40
        assert result.missing == 10

    def test_verify_append_no_data(self) -> None:
        session = MagicMock()
        session.query.return_value.filter.return_value.scalar.return_value = 0
        session.query.return_value.filter.return_value.one.return_value = (None, None)

        reporter = PipelineReporter(session, FakeModel, "rate_date")
        result = reporter.verify_append(date(2025, 1, 1), expected_count=50)

        assert result.rows_verified == 0
        assert result.missing == 50
        assert result.timestamp_range is None


class TestSuccessReport:
    def test_to_dict(self) -> None:
        now = datetime.now(timezone.utc)
        report = SuccessReport(
            pipeline_name="fx.spot_rates",
            domain="fx",
            run_date=date(2025, 1, 1),
            started_at=now,
            finished_at=now,
            rows_extracted=100,
            rows_loaded=95,
            rows_verified_in_db=95,
            missing_records=5,
            timestamp_range=(now, now),
            health_report=HealthReport(passed=True, results=[]),
            status=RunStatus.SUCCESS,
        )
        d = report.to_dict()
        assert d["status"] == "success"
        assert d["rows_loaded"] == 95
        assert d["health_report"]["passed"] is True
