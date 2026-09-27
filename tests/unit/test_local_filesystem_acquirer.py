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

class TestExtraSources:
    """Per-root pattern sources — added to restore the onshore BBG FX pairs.

    ``BBG_mirror\\FX`` was provisioned without CNY/CNO/MYO/IDO folders, so
    those pairs went dark at the 2026-04-24 cutover while the legacy
    ``BBG\\FX`` tree kept carrying them. ``extra_sources`` lets one feed read
    the 22 mirror ccys plus the 3 onshore ccys from the legacy tree.
    """

    def test_defaults_to_empty(self, tmp_path: Path) -> None:
        assert _spec(tmp_path).extra_sources == ()

    def test_globs_the_extra_root(self, tmp_path: Path) -> None:
        primary = tmp_path / "mirror"
        legacy = tmp_path / "legacy"
        (primary / "CNH").mkdir(parents=True)
        (primary / "CNH" / "FX_CNH.csv").write_text("x")
        (legacy / "CNY").mkdir(parents=True)
        (legacy / "CNY" / "FX_CNY.csv").write_text("y")

        spec = _spec(primary, patterns=["CNH/FX_CNH.csv"],
                     extra_sources=((legacy, ("CNY/FX_CNY.csv",)),))
        result = LocalFilesystemAcquirer(spec).fetch()

        assert {p.parent.name for p in result.saved_files} == {"CNH", "CNY"}

    def test_extra_patterns_are_per_root_not_shared(self, tmp_path: Path) -> None:
        """The extra root must NOT be globbed with the primary patterns.

        The legacy BBG tree holds CNO/FX_CNO.csv (tenor labels unparseable)
        and KRO (untracked) beside the files we want. Sharing the pattern list
        across roots would acquire them.
        """
        primary = tmp_path / "mirror"
        legacy = tmp_path / "legacy"
        (primary / "CNH").mkdir(parents=True)
        (primary / "CNH" / "FX_CNH.csv").write_text("x")
        for junk in ("CNO", "KRO"):
            (legacy / junk).mkdir(parents=True)
            (legacy / junk / f"FX_{junk}.csv").write_text("junk")
        (legacy / "CNY").mkdir(parents=True)
        (legacy / "CNY" / "FX_CNY.csv").write_text("y")

        spec = _spec(primary, patterns=["*/FX_*.csv"],
                     extra_sources=((legacy, ("CNY/FX_CNY.csv",)),))
        result = LocalFilesystemAcquirer(spec).fetch()

        got = {p.parent.name for p in result.saved_files}
        assert got == {"CNH", "CNY"}
        assert "CNO" not in got and "KRO" not in got

    def test_missing_extra_root_warns_and_does_not_fail(self, tmp_path: Path) -> None:
        """A secondary tree may be retired without taking the feed down."""
        primary = tmp_path / "mirror"
        primary.mkdir()
        (primary / "a.csv").write_text("x")
        gone = tmp_path / "does_not_exist"

        spec = _spec(primary, extra_sources=((gone, ("*.csv",)),))
        result = LocalFilesystemAcquirer(spec).fetch()

        assert len(result.saved_files) == 1
        assert any("extra root does not exist" in w for w in result.warnings)

    def test_missing_primary_root_still_raises(self, tmp_path: Path) -> None:
        """Only the EXTRA roots are forgiving; the primary is still fatal."""
        legacy = tmp_path / "legacy"
        legacy.mkdir()
        (legacy / "a.csv").write_text("x")

        spec = _spec(tmp_path / "nope",
                     extra_sources=((legacy, ("*.csv",)),))
        with pytest.raises(ListingNotFound, match="root path does not exist"):
            LocalFilesystemAcquirer(spec).fetch()

    def test_extra_files_count_toward_min_matches(self, tmp_path: Path) -> None:
        primary = tmp_path / "mirror"
        legacy = tmp_path / "legacy"
        primary.mkdir()
        legacy.mkdir()
        (primary / "a.csv").write_text("x")
        (legacy / "b.csv").write_text("y")

        spec = _spec(primary, min_matches=2,
                     extra_sources=((legacy, ("*.csv",)),))
        assert len(LocalFilesystemAcquirer(spec).fetch().saved_files) == 2

    def test_freshness_filter_applies_to_extra_files(self, tmp_path: Path) -> None:
        """An extra root gets no exemption from the staleness cutoff."""
        primary = tmp_path / "mirror"
        legacy = tmp_path / "legacy"
        primary.mkdir()
        legacy.mkdir()
        (primary / "fresh.csv").write_text("x")
        stale = legacy / "stale.csv"
        stale.write_text("y")
        old = stale.stat().st_mtime - 60 * 60 * 24 * 30
        os.utime(stale, (old, old))

        spec = _spec(primary, min_mtime_age=timedelta(hours=72),
                     extra_sources=((legacy, ("*.csv",)),))
        result = LocalFilesystemAcquirer(spec).fetch()

        assert {p.name for p in result.saved_files} == {"fresh.csv"}
        assert any("stale file" in w for w in result.warnings)
