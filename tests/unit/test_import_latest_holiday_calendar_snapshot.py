"""Tests for ``scripts.calendar.import_latest_holiday_calendar_snapshot``.

Covers the snapshot-discovery logic that picks the most recent
``calendar_YYYYMMDD.xlsx`` from the IMDR_MANUAL_UPLOADS\\Calendar tree
(the canonical holiday-calendar source).
"""

from __future__ import annotations

import pytest

from scripts.calendar.import_latest_holiday_calendar_snapshot import (
    find_latest_snapshot,
)


class TestFindLatestSnapshot:
    def test_returns_file_with_greatest_date(self, tmp_path):
        # Spread snapshots across two months — the loader must pick by the
        # YYYYMMDD in the filename, NOT by mtime or alphabetical folder order.
        (tmp_path / "2026" / "05").mkdir(parents=True)
        (tmp_path / "2026" / "06").mkdir(parents=True)
        (tmp_path / "2026" / "05" / "calendar_20260530.xlsx").write_bytes(b"")
        latest = tmp_path / "2026" / "06" / "calendar_20260605.xlsx"
        latest.write_bytes(b"")
        (tmp_path / "2026" / "06" / "calendar_20260604.xlsx").write_bytes(b"")

        path, date_str = find_latest_snapshot(tmp_path)
        assert path == latest
        assert date_str == "20260605"

    def test_ignores_non_matching_filenames(self, tmp_path):
        (tmp_path / "2026" / "06").mkdir(parents=True)
        (tmp_path / "2026" / "06" / "calendar.xlsx").write_bytes(b"")          # no date
        (tmp_path / "2026" / "06" / "refresh_calendar.log").write_bytes(b"")   # not xlsx
        (tmp_path / "2026" / "06" / "calendar_2026060.xlsx").write_bytes(b"")  # 7-digit
        expected = tmp_path / "2026" / "06" / "calendar_20260604.xlsx"
        expected.write_bytes(b"")

        path, date_str = find_latest_snapshot(tmp_path)
        assert path == expected
        assert date_str == "20260604"

    def test_filename_is_case_insensitive(self, tmp_path):
        (tmp_path / "2026" / "06").mkdir(parents=True)
        expected = tmp_path / "2026" / "06" / "Calendar_20260604.XLSX"
        expected.write_bytes(b"")
        path, date_str = find_latest_snapshot(tmp_path)
        assert path == expected
        assert date_str == "20260604"

    def test_raises_when_no_snapshot_present(self, tmp_path):
        # Root exists but no matching file anywhere in YYYY/MM/.
        (tmp_path / "2026" / "06").mkdir(parents=True)
        with pytest.raises(FileNotFoundError, match="no calendar_YYYYMMDD.xlsx found"):
            find_latest_snapshot(tmp_path)

    def test_raises_when_root_empty(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="no calendar_YYYYMMDD.xlsx found"):
            find_latest_snapshot(tmp_path)

    def test_only_searches_two_levels_deep(self, tmp_path):
        # File at root or one-level-deep must NOT be picked up; the snapshot
        # producer always writes under YYYY/MM/.
        (tmp_path / "calendar_20260605.xlsx").write_bytes(b"")          # depth 0
        (tmp_path / "2026").mkdir()
        (tmp_path / "2026" / "calendar_20260605.xlsx").write_bytes(b"")  # depth 1
        (tmp_path / "2026" / "06").mkdir()
        expected = tmp_path / "2026" / "06" / "calendar_20260604.xlsx"
        expected.write_bytes(b"")                                        # depth 2

        path, date_str = find_latest_snapshot(tmp_path)
        assert path == expected
        assert date_str == "20260604"
