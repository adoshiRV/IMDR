"""Tests for RunReport."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from imdr.reporting.run_report import EventLevel, RunReport


def test_report_info():
    r = RunReport(pipeline_name="test")
    r.info("extract", "Got 100 rows")
    assert len(r.events) == 1
    assert r.events[0].level == EventLevel.INFO
    assert r.events[0].category == "extract"


def test_report_warning():
    r = RunReport()
    r.warning("validation", "Missing 5 symbols", details={"missing": ["CNY"]})
    assert r.has_warnings
    assert not r.has_errors


def test_report_error():
    r = RunReport()
    r.error("load", "DB write failed")
    assert r.has_errors


def test_events_by_level():
    r = RunReport()
    r.info("a", "info1")
    r.warning("b", "warn1")
    r.info("c", "info2")
    r.error("d", "err1")

    infos = r.events_by_level(EventLevel.INFO)
    assert len(infos) == 2
    warnings = r.events_by_level(EventLevel.WARNING)
    assert len(warnings) == 1


def test_events_by_category():
    r = RunReport()
    r.info("extract", "msg1")
    r.info("load", "msg2")
    r.info("extract", "msg3")

    extract_events = r.events_by_category("extract")
    assert len(extract_events) == 2


def test_finish():
    r = RunReport()
    assert r.finished_at is None
    r.finish()
    assert r.finished_at is not None


def test_to_dict():
    r = RunReport(pipeline_name="test.pipeline")
    r.info("extract", "ok")
    r.warning("validate", "issue")
    r.finish()

    d = r.to_dict()
    assert d["pipeline_name"] == "test.pipeline"
    assert d["event_count"] == 2
    assert d["warnings"] == 1
    assert d["errors"] == 0


def test_flush_jsonl():
    r = RunReport(pipeline_name="test")
    r.info("extract", "row1")
    r.warning("validate", "row2")
    r.finish()

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "logs" / "test.jsonl"
        r.flush_jsonl(path)

        assert path.exists()
        lines = path.read_text().strip().splitlines()
        assert len(lines) == 3  # 1 header + 2 events

        header = json.loads(lines[0])
        assert header["type"] == "run_header"
        assert header["pipeline_name"] == "test"
