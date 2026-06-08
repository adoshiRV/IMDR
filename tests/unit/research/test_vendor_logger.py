"""Tests for VendorLogger — per-vendor stdout prefix + log file.

See docs/admin/development/parallel_vendor_ingest.md Phase 3.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest

_RESEARCH_ROOT = Path(__file__).resolve().parents[3] / "playground" / "research"
if str(_RESEARCH_ROOT) not in sys.path:
    sys.path.insert(0, str(_RESEARCH_ROOT))

from ingest import _vendor_log  # noqa: E402


@pytest.fixture
def isolated_logs_root(tmp_path, monkeypatch):
    """Redirect VendorLogger's logs root to tmp_path so tests don't write to
    the real playground/research/logs/ directory."""
    monkeypatch.setattr(_vendor_log, "_LOGS_ROOT", tmp_path)
    return tmp_path


def test_emits_prefixed_line_to_stdout(isolated_logs_root, capsys):
    log = _vendor_log.VendorLogger("goldman", run_date=date(2026, 6, 9))
    log.line("discovered 12 reports")
    log.close()
    out = capsys.readouterr().out
    assert "[goldman] discovered 12 reports" in out


def test_writes_to_per_vendor_log_file(isolated_logs_root):
    log = _vendor_log.VendorLogger("nomura", run_date=date(2026, 6, 9))
    log.line("hello world")
    log.close()

    expected_path = isolated_logs_root / "20260609" / "nomura.log"
    assert expected_path.exists()
    content = expected_path.read_text(encoding="utf-8")
    assert "hello world" in content
    # File entries are timestamped (UTC ISO-8601), stdout lines are not.
    assert "Z  hello world" in content


def test_two_vendors_get_separate_log_files(isolated_logs_root):
    log_g = _vendor_log.VendorLogger("goldman", run_date=date(2026, 6, 9))
    log_n = _vendor_log.VendorLogger("nomura", run_date=date(2026, 6, 9))
    log_g.line("goldman line")
    log_n.line("nomura line")
    log_g.close()
    log_n.close()

    g_path = isolated_logs_root / "20260609" / "goldman.log"
    n_path = isolated_logs_root / "20260609" / "nomura.log"
    assert "goldman line" in g_path.read_text(encoding="utf-8")
    assert "nomura line" in n_path.read_text(encoding="utf-8")
    # Cross-contamination check.
    assert "goldman line" not in n_path.read_text(encoding="utf-8")
    assert "nomura line" not in g_path.read_text(encoding="utf-8")


def test_append_mode_preserves_earlier_run(isolated_logs_root):
    """Same vendor, same day, second logger appends — doesn't truncate."""
    log1 = _vendor_log.VendorLogger("bnp", run_date=date(2026, 6, 9))
    log1.line("first run")
    log1.close()

    log2 = _vendor_log.VendorLogger("bnp", run_date=date(2026, 6, 9))
    log2.line("second run")
    log2.close()

    path = isolated_logs_root / "20260609" / "bnp.log"
    content = path.read_text(encoding="utf-8")
    assert "first run" in content
    assert "second run" in content


def test_section_emits_three_lines(isolated_logs_root, capsys):
    log = _vendor_log.VendorLogger("hsbc", run_date=date(2026, 6, 9))
    log.section("vendor: hsbc")
    log.close()
    out = capsys.readouterr().out
    assert out.count("[hsbc]") == 3
    assert "vendor: hsbc" in out
    assert "===" in out


def test_context_manager_closes_file(isolated_logs_root):
    with _vendor_log.VendorLogger("ms", run_date=date(2026, 6, 9)) as log:
        log.line("inside")
        path = log.path
    assert path.exists()
    # The file should be closed after the with-block exits.
    assert log._file.closed  # noqa: SLF001
