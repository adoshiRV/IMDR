"""Tests for ``imdr.notifications.formatters.holiday_calendar_ingest``.

Validates the OK/PARTIAL/FAIL status logic and that subject + body include
the load summary fields the weekly canonical-holiday-calendar importer
passes in.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from imdr.notifications.formatters.holiday_calendar_ingest import (
    HolidayCalendarIngestFormatter,
)


@pytest.fixture
def fmt() -> HolidayCalendarIngestFormatter:
    return HolidayCalendarIngestFormatter()


class TestSubjectStatus:
    def test_ok_when_no_missing_no_error(self, fmt):
        subj = fmt.format_subject(
            snapshot_date="20260605", inserted=42, calendars=27,
            missing=[], error="",
        )
        assert "Holiday Calendar Weekly Load OK" in subj
        assert "42 new" in subj
        assert "27 calendars" in subj
        assert "20260605" in subj

    def test_partial_when_missing_codes_present(self, fmt):
        subj = fmt.format_subject(
            snapshot_date="20260605", inserted=10, calendars=28,
            missing=["ZZ"], error="",
        )
        assert "PARTIAL" in subj

    def test_fail_when_error_set(self, fmt):
        subj = fmt.format_subject(
            snapshot_date="20260605", inserted=0, calendars=0,
            missing=[], error="snapshot root missing",
        )
        assert "FAIL" in subj

    def test_fail_takes_priority_over_partial(self, fmt):
        # Error AND missing — error wins. Otherwise an outage with stale
        # missing-code state would mask itself as PARTIAL.
        subj = fmt.format_subject(
            snapshot_date="20260605", inserted=0, calendars=0,
            missing=["ZZ"], error="connect failed",
        )
        assert "FAIL" in subj


class TestBodyRendering:
    def test_body_includes_summary_fields(self, fmt):
        body = fmt.format_body(
            snapshot_path=r"Z:\foo\calendar_20260605.xlsx",
            snapshot_date="20260605",
            run_time_utc=datetime(2026, 6, 5, 12, 0, 0, tzinfo=timezone.utc),
            duration_s=3.14,
            calendars=27,
            total_parsed=9000,
            inserted=42,
            skipped=8958,
            load_batch="bbg_weekly_20260605",
            rows=[{"code": "GT", "in_file": 100, "inserted": 5, "skipped": 95}],
            missing=[],
            error="",
        )
        # Header
        assert "Holiday Calendar Weekly Load OK" in body
        # Summary row values
        assert "calendar_20260605.xlsx" in body
        assert "20260605" in body
        assert "27" in body
        assert "9000" in body
        assert "42" in body
        assert "bbg_weekly_20260605" in body
        # Per-calendar row rendered
        assert "GT" in body

    def test_body_renders_missing_calendars_block(self, fmt):
        body = fmt.format_body(
            snapshot_date="20260605", inserted=0, calendars=1,
            missing=["ZZ", "QQ"], error="",
        )
        assert "PARTIAL" in body
        assert "not in dim_calendar" in body
        assert "ZZ" in body
        assert "QQ" in body

    def test_body_renders_error_block_with_traceback(self, fmt):
        body = fmt.format_body(
            snapshot_date="20260605", inserted=0, calendars=0,
            error="OperationalError: SQL Server does not exist",
        )
        assert "FAIL" in body
        assert "OperationalError" in body

    def test_body_no_perc_block_when_rows_empty(self, fmt):
        body = fmt.format_body(
            snapshot_date="20260605", inserted=0, calendars=0,
            rows=[], missing=[], error="",
        )
        # Per-calendar detail header is omitted when there's nothing to show.
        assert "Per-calendar load detail" not in body
