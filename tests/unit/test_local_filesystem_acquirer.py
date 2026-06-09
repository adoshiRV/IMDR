"""Tests for LocalFilesystemAcquirer."""
from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

import pytest

from imdr.vendors.acquirers.filesystem import (
    LocalFilesystemAcquirer,
    LocalFilesystemSpec,
)
from imdr.vendors.exceptions import ListingNotFound


def _spec(root: Path, **overrides) -> LocalFilesystemSpec:
    defaults = dict(
        name="test_feed",
        vendor_code="bloomberg",
        root=root,
        patterns=["*.csv"],
        min_mtime_age=None,
        min_matches=1,
    )
    defaults.update(overrides)
    return LocalFilesystemSpec(**defaults)


class TestLocalFilesystemAcquirer:
    def test_glob_matches_files(self, tmp_path: Path) -> None:
        (tmp_path / "a.csv").write_text("x")
        (tmp_path / "b.csv").write_text("y")
        (tmp_path / "ignored.txt").write_text("z")

        acquirer = LocalFilesystemAcquirer(_spec(tmp_path))
        result = acquirer.fetch()

        assert len(result.saved_files) == 2
        assert {p.name for p in result.saved_files} == {"a.csv", "b.csv"}
        assert result.bytes_downloaded == 2  # "x" + "y"
        assert result.vendor == "bloomberg"
        assert result.feed == "test_feed"

    def test_results_are_sorted(self, tmp_path: Path) -> None:
        for n in ["c.csv", "a.csv", "b.csv"]:
            (tmp_path / n).write_text("")

        acquirer = LocalFilesystemAcquirer(_spec(tmp_path))
        result = acquirer.fetch()

        names = [p.name for p in result.saved_files]
        assert names == sorted(names)

    def test_nested_glob_pattern(self, tmp_path: Path) -> None:
        # Mirror the real BBG layout: root/{CCY}/FX_{CCY}.csv
        for ccy in ("AUD", "EUR"):
            (tmp_path / ccy).mkdir()
            (tmp_path / ccy / f"FX_{ccy}.csv").write_text("data")

        spec = _spec(tmp_path, patterns=["*/FX_*.csv"])
        acquirer = LocalFilesystemAcquirer(spec)
        result = acquirer.fetch()

        assert len(result.saved_files) == 2

    def test_multiple_patterns_dedup(self, tmp_path: Path) -> None:
        (tmp_path / "x.csv").write_text("data")

        # Two patterns that both match the same file
        spec = _spec(tmp_path, patterns=["*.csv", "x.*"])
        acquirer = LocalFilesystemAcquirer(spec)
        result = acquirer.fetch()

        assert len(result.saved_files) == 1

    def test_missing_root_raises(self, tmp_path: Path) -> None:
        acquirer = LocalFilesystemAcquirer(_spec(tmp_path / "nonexistent"))
        with pytest.raises(ListingNotFound, match="root path does not exist"):
            acquirer.fetch()

    def test_zero_matches_raises(self, tmp_path: Path) -> None:
        # Empty dir
        acquirer = LocalFilesystemAcquirer(_spec(tmp_path))
        with pytest.raises(ListingNotFound, match="matched 0 files"):
            acquirer.fetch()

    def test_min_matches_threshold(self, tmp_path: Path) -> None:
        (tmp_path / "only_one.csv").write_text("data")

        spec = _spec(tmp_path, min_matches=2)
        acquirer = LocalFilesystemAcquirer(spec)
        with pytest.raises(ListingNotFound, match="matched 1 files, need >= 2"):
            acquirer.fetch()

    def test_stale_file_filtered(self, tmp_path: Path) -> None:
        fresh = tmp_path / "fresh.csv"
        stale = tmp_path / "stale.csv"
        fresh.write_text("new")
        stale.write_text("old")
        # Make stale file 7 days old
        old_ts = (fresh.stat().st_mtime - 7 * 86400)
        os.utime(stale, (old_ts, old_ts))

        spec = _spec(tmp_path, min_mtime_age=timedelta(hours=24))
        acquirer = LocalFilesystemAcquirer(spec)
        result = acquirer.fetch()

        assert len(result.saved_files) == 1
        assert result.saved_files[0].name == "fresh.csv"
        assert any("stale file" in w for w in result.warnings)

    def test_all_files_stale_raises(self, tmp_path: Path) -> None:
        f = tmp_path / "old.csv"
        f.write_text("old")
        old_ts = f.stat().st_mtime - 7 * 86400
        os.utime(f, (old_ts, old_ts))

        spec = _spec(tmp_path, min_mtime_age=timedelta(hours=24))
        acquirer = LocalFilesystemAcquirer(spec)
        with pytest.raises(ListingNotFound):
            acquirer.fetch()

    def test_directories_excluded(self, tmp_path: Path) -> None:
        (tmp_path / "a.csv").write_text("data")
        (tmp_path / "subdir").mkdir()  # would match *.* if not filtered

        spec = _spec(tmp_path, patterns=["*"])
        acquirer = LocalFilesystemAcquirer(spec)
        result = acquirer.fetch()

        assert len(result.saved_files) == 1
        assert result.saved_files[0].name == "a.csv"

    def test_fetch_result_timing(self, tmp_path: Path) -> None:
        (tmp_path / "a.csv").write_text("x")
        acquirer = LocalFilesystemAcquirer(_spec(tmp_path))
        result = acquirer.fetch()

        assert result.elapsed_s >= 0
        assert result.finished_at >= result.started_at
        assert result.ok
