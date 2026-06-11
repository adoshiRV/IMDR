"""Tests for safe_write_pdf — atomic + collision-safe local PDF write.

See docs/admin/development/parallel_vendor_ingest.md Phase 2.

Covers:
* Bytes-match idempotent replay -> no error, no rewrite.
* Bytes-mismatch -> existing is archived to a dated sibling, new bytes
  written in place.
* PermissionError on os.replace (OneDrive holds the file) -> retries
  succeed within budget; exceed budget -> UploadError, tmp cleaned up.
* Concurrent same-bytes writers (threaded) -> both succeed.
* Concurrent diff-bytes writers -> last writer wins after archival.
"""
from __future__ import annotations

import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from unittest.mock import patch

import pytest

_RESEARCH_ROOT = Path(__file__).resolve().parents[3] / "playground" / "research"
if str(_RESEARCH_ROOT) not in sys.path:
    sys.path.insert(0, str(_RESEARCH_ROOT))

from ingest.upload import (  # noqa: E402
    PdfPathCollisionError,
    UploadError,
    safe_write_pdf,
)


def test_writes_payload_when_target_missing(tmp_path):
    target = tmp_path / "report.pdf"
    safe_write_pdf(target, b"hello")
    assert target.read_bytes() == b"hello"


def test_idempotent_replay_on_matching_bytes(tmp_path):
    target = tmp_path / "report.pdf"
    target.write_bytes(b"hello")
    # Should NOT raise, NOT rewrite.
    mtime_before = target.stat().st_mtime_ns
    safe_write_pdf(target, b"hello")
    mtime_after = target.stat().st_mtime_ns
    assert mtime_before == mtime_after, "idempotent replay must not touch file"


def test_archives_existing_on_mismatched_bytes(tmp_path):
    """Vendor re-issue: existing is renamed to a dated sibling, new bytes
    are written to the original path."""
    target = tmp_path / "report.pdf"
    target.write_bytes(b"original content")
    safe_write_pdf(target, b"DIFFERENT content")
    # Target now holds the new bytes.
    assert target.read_bytes() == b"DIFFERENT content"
    # An archive sibling exists with the original bytes.
    archives = [
        p for p in tmp_path.glob("report.*.pdf") if p != target
    ]
    assert len(archives) == 1, f"expected one archive, got {archives}"
    assert archives[0].read_bytes() == b"original content"


def test_archive_collision_appends_hash_disambiguator(tmp_path):
    """Two re-issues in the same second produce two distinct archives."""
    target = tmp_path / "report.pdf"
    target.write_bytes(b"v1")
    # First re-issue archives v1 under mtime stem.
    safe_write_pdf(target, b"v2")
    # Force the second archive name to collide by pre-creating one at the
    # mtime-stem path. We don't know the exact mtime stem, but we know the
    # pattern: report.YYYYMMDD_HHMMSS.pdf — match any.
    archives_after_first = sorted(tmp_path.glob("report.*.pdf"))
    assert len(archives_after_first) == 1
    first_archive = archives_after_first[0]
    # Second re-issue: target holds v2, force-collide its archive by
    # touching the mtime of target back to first_archive's mtime so the
    # archive name regenerates identically.
    import os as _os
    mt = first_archive.stat().st_mtime
    _os.utime(target, (mt, mt))
    safe_write_pdf(target, b"v3")
    archives_after_second = sorted(
        p for p in tmp_path.glob("report.*.pdf") if p != target
    )
    assert len(archives_after_second) == 2, (
        f"expected two archives after second re-issue, got "
        f"{archives_after_second}"
    )
    assert target.read_bytes() == b"v3"


def test_zero_byte_existing_target_treated_as_missing(tmp_path):
    """A 0-byte file from a prior aborted write is overwritten cleanly."""
    target = tmp_path / "report.pdf"
    target.write_bytes(b"")
    safe_write_pdf(target, b"new payload")
    assert target.read_bytes() == b"new payload"


def test_no_tmp_leftover_on_success(tmp_path):
    target = tmp_path / "report.pdf"
    safe_write_pdf(target, b"payload")
    leftover = list(tmp_path.glob("report.pdf.*.tmp"))
    assert leftover == [], f"tmp sibling must be replaced into target, got {leftover}"


def test_permission_error_retried_then_succeeds(tmp_path):
    """OneDrive holds file briefly -> first replace fails, second succeeds."""
    target = tmp_path / "report.pdf"
    call_count = {"n": 0}

    import os as _os
    original_replace = _os.replace

    def flaky_replace(src, dst):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise PermissionError("simulated OneDrive lock")
        return original_replace(src, dst)

    with patch("ingest.upload.os.replace", side_effect=flaky_replace):
        # Also patch the sleep so the test doesn't actually wait 1-2s.
        with patch("ingest.upload.time.sleep"):
            safe_write_pdf(target, b"payload")

    assert call_count["n"] == 2, "expected exactly one retry"
    assert target.read_bytes() == b"payload"


def test_permission_error_exhausts_budget_raises_and_cleans_tmp(tmp_path):
    """Persistent PermissionError exceeds retry budget -> UploadError."""
    target = tmp_path / "report.pdf"

    with patch("ingest.upload.os.replace",
               side_effect=PermissionError("still locked")):
        with patch("ingest.upload.time.sleep"):
            with pytest.raises(UploadError) as exc_info:
                safe_write_pdf(target, b"payload")

    assert "os.replace failed" in str(exc_info.value)
    leftover = list(tmp_path.glob("report.pdf.*.tmp"))
    assert leftover == [], f"tmp must be cleaned up on terminal failure, got {leftover}"


def test_concurrent_same_bytes_both_succeed(tmp_path):
    """Two threads writing identical bytes to the same target both succeed."""
    target = tmp_path / "report.pdf"
    payload = b"x" * 1024
    errors: list[BaseException] = []
    barrier = threading.Barrier(2)

    def _worker():
        try:
            barrier.wait()
            safe_write_pdf(target, payload)
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(_worker) for _ in range(2)]
        for f in as_completed(futures):
            f.result()

    assert errors == [], f"unexpected errors: {errors}"
    assert target.read_bytes() == payload


def test_concurrent_different_bytes_last_writer_wins(tmp_path):
    """Two threads writing different bytes: target holds one payload, the
    other is archived (or, in a tight race, silently replaced).

    With archive-on-collision, the first writer creates the file, the
    second writer detects the mismatch and archives the first writer's
    bytes before writing its own. Both calls return without raising.
    """
    target = tmp_path / "report.pdf"
    payload_a = b"AAA" * 100
    payload_b = b"BBB" * 100
    results: list[tuple[str, BaseException | None]] = []
    barrier = threading.Barrier(2)

    def _worker(label, payload):
        try:
            barrier.wait()
            safe_write_pdf(target, payload)
            results.append((label, None))
        except BaseException as exc:  # noqa: BLE001
            results.append((label, exc))

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(_worker, "A", payload_a),
            pool.submit(_worker, "B", payload_b),
        ]
        for f in as_completed(futures):
            f.result()

    # Final target has one of the two payloads.
    final = target.read_bytes()
    assert final in (payload_a, payload_b)

    collisions = [
        exc for _, exc in results if isinstance(exc, PdfPathCollisionError)
    ]
    # PdfPathCollisionError is now only raised on archive-rename failure
    # (a permission error during os.replace target->archive), which the
    # threaded race shouldn't hit. Any other Exception is a regression.
    assert collisions == [], (
        f"PdfPathCollisionError is reserved for archive failures only, "
        f"got: {collisions}"
    )
    other = [exc for _, exc in results if exc is not None]
    assert other == [], f"unexpected errors: {other}"
