"""Lock-in test: every BBG feed must NEVER move source files.

Parametrized over all 4 BBG vendor feeds:
  - bbg_fx_snapshot   (half-hourly)   reads Z:\\BBG_mirror\\FX\\
  - bbg_fx_daily      (close-of-day)  reads Z:\\BBG_mirror\\FX\\
  - bbg_rates_snapshot (half-hourly)  reads Z:\\BBG_mirror\\{IRS,OIS,BASIS,CCS}\\
  - bbg_rates_daily   (close-of-day)  reads Z:\\BBG_mirror\\{IRS,OIS,BASIS,CCS}\\

The R pipeline owns those trees and overwrites in place. If IMDR
archives, deletes, or rewrites those CSVs the next fire has nothing to
read. Tests fail if either:
  - someone flips ``archive_after_load`` to True on any feed,
  - someone changes the runner so archive runs regardless of the flag, or
  - someone introduces ``os.rename`` / ``Path.replace`` / ``.unlink`` /
    ``open(..., 'w')`` etc. into any BBG source file.
"""
from __future__ import annotations

import importlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from unittest.mock import MagicMock, patch

import pytest

from imdr.vendors.base import FetchResult, VendorFeed
from imdr.vendors.registry import VENDOR_FEEDS, register_feed


# ── Sample-file layout factories ──────────────────────────────────────


def _fx_layout(root: Path) -> list[Path]:
    """Mirror the BBG FX layout: ``{ccy}/FX_{ccy}.csv`` per pair."""
    files = []
    for ccy in ("EUR", "JPY"):
        d = root / ccy
        d.mkdir(parents=True, exist_ok=True)
        f = d / f"FX_{ccy}.csv"
        f.write_text("Ticker,...\n")
        files.append(f)
    return files


def _rates_layout(root: Path) -> list[Path]:
    """Mirror the BBG rates layout: ``{kind}/{folder}/PAR/{kind}_PAR_{folder}.csv``."""
    files = []
    for kind, folder in (("OIS", "USD-SOFR-ON"), ("IRS", "AUD-BBSW-3M")):
        d = root / kind / folder / "PAR"
        d.mkdir(parents=True, exist_ok=True)
        f = d / f"{kind}_PAR_{folder}.csv"
        f.write_text("Ticker,...\n")
        files.append(f)
    return files


# ── Feed config table ─────────────────────────────────────────────────


@dataclass(frozen=True)
class _FeedCfg:
    name: str
    spec_module: str
    staleness_pipeline_name: str
    src_files_relative: tuple[str, ...]
    layout: Callable[[Path], list[Path]]
    rows_loaded: int = 100
    extra_pattern_prefixes: tuple[str, ...] = field(default_factory=tuple)


_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent


_FEEDS: list[_FeedCfg] = [
    _FeedCfg(
        name="bbg_fx_snapshot",
        spec_module="imdr.vendors.specs.bbg_fx_snapshot",
        staleness_pipeline_name="fx.bloomberg_snapshot",
        src_files_relative=(
            "src/imdr/domains/fx/extractors_rate_bbg.py",
            "src/imdr/domains/fx/pipeline_rate_bbg.py",
            "src/imdr/vendors/specs/bbg_fx_snapshot.py",
        ),
        layout=_fx_layout,
        rows_loaded=209,
    ),
    _FeedCfg(
        name="bbg_fx_daily",
        spec_module="imdr.vendors.specs.bbg_fx_daily",
        staleness_pipeline_name="fx.bloomberg_daily",
        src_files_relative=(
            "src/imdr/domains/fx/pipeline_rate_bbg_daily.py",
            "src/imdr/vendors/specs/bbg_fx_daily.py",
        ),
        layout=_fx_layout,
        rows_loaded=175,
    ),
    _FeedCfg(
        name="bbg_rates_snapshot",
        spec_module="imdr.vendors.specs.bbg_rates_snapshot",
        staleness_pipeline_name="rates.bloomberg_snapshot",
        src_files_relative=(
            "src/imdr/domains/rates/extractors_bbg.py",
            "src/imdr/domains/rates/pipeline_bbg.py",
            "src/imdr/vendors/specs/bbg_rates_snapshot.py",
        ),
        layout=_rates_layout,
        rows_loaded=600,
        extra_pattern_prefixes=("IRS/", "OIS/", "BASIS/", "CCS/"),
    ),
    _FeedCfg(
        name="bbg_rates_daily",
        spec_module="imdr.vendors.specs.bbg_rates_daily",
        staleness_pipeline_name="rates.bloomberg_daily",
        src_files_relative=(
            "src/imdr/domains/rates/pipeline_bbg_daily.py",
            "src/imdr/vendors/specs/bbg_rates_daily.py",
        ),
        layout=_rates_layout,
        rows_loaded=600,
        extra_pattern_prefixes=("IRS/", "OIS/", "BASIS/", "CCS/"),
    ),
]

_FEED_IDS = [c.name for c in _FEEDS]


@pytest.fixture(params=_FEEDS, ids=_FEED_IDS)
def cfg(request: pytest.FixtureRequest) -> _FeedCfg:
    return request.param


def _fetch_result(feed_name: str, files: list[Path]) -> FetchResult:
    now = datetime(2026, 4, 29, 14, 0, tzinfo=timezone.utc)
    return FetchResult(
        vendor="bloomberg", feed=feed_name,
        saved_files=files, bytes_downloaded=len(files) * 10,
        started_at=now, finished_at=now,
    )


# ── Static contract checks ────────────────────────────────────────────


class TestBBGFeedConfig:
    def test_archive_after_load_is_false(self, cfg: _FeedCfg) -> None:
        mod = importlib.import_module(cfg.spec_module)
        assert mod.FEED.archive_after_load is False, (
            f"{cfg.name}: archive_after_load must be False — "
            "Z:\\BBG_mirror\\ is read-only (R pipeline overwrites in place)."
        )

    def test_email_on_zero_rows_is_false(self, cfg: _FeedCfg) -> None:
        mod = importlib.import_module(cfg.spec_module)
        assert mod.FEED.email_on_zero_rows is False

    def test_vendor_code_is_bbg(self, cfg: _FeedCfg) -> None:
        mod = importlib.import_module(cfg.spec_module)
        assert mod.FEED.vendor_code == "BBG"

    def test_root_under_bbg_tree(self, cfg: _FeedCfg) -> None:
        mod = importlib.import_module(cfg.spec_module)
        assert "BBG" in str(mod.SPEC.root)

    def test_staleness_pipeline_name(self, cfg: _FeedCfg) -> None:
        mod = importlib.import_module(cfg.spec_module)
        assert mod.FEED.staleness_pipeline_name == cfg.staleness_pipeline_name

    def test_patterns_under_root(self, cfg: _FeedCfg) -> None:
        if not cfg.extra_pattern_prefixes:
            pytest.skip(f"{cfg.name}: no per-pattern prefix contract")
        mod = importlib.import_module(cfg.spec_module)
        for p in mod.SPEC.patterns:
            assert p.startswith(cfg.extra_pattern_prefixes), (
                f"{cfg.name}: pattern {p!r} doesn't start with one of "
                f"{cfg.extra_pattern_prefixes} — could leak access outside the rates trees."
            )


def test_all_staleness_pipeline_names_distinct() -> None:
    """No two BBG feeds may share a staleness_pipeline_name — audit logs
    + run history must not collide between snapshot and daily fires."""
    names = []
    for feed_cfg in _FEEDS:
        mod = importlib.import_module(feed_cfg.spec_module)
        names.append(mod.FEED.staleness_pipeline_name)
    assert len(set(names)) == len(names), f"Duplicate staleness names: {names}"


# ── Source-tree static check (forbid write-side ops) ──────────────────


class TestSourceCodeNoWrites:
    """Static grep over each feed's source files for forbidden write ops."""

    def _src_files(self, cfg: _FeedCfg) -> list[Path]:
        return [_REPO_ROOT / rel for rel in cfg.src_files_relative]

    def test_no_path_replace(self, cfg: _FeedCfg) -> None:
        for f in self._src_files(cfg):
            text = f.read_text(encoding="utf-8")
            # Strip str.replace(...) calls so we only catch Path.replace
            stripped = re.sub(r"\.replace\(['\"]", "", text)
            assert ".replace(" not in stripped, (
                f"{f.name}: uses Path.replace — forbidden on Z:\\BBG_mirror\\"
            )

    def test_no_os_rename(self, cfg: _FeedCfg) -> None:
        for f in self._src_files(cfg):
            assert "os.rename" not in f.read_text(encoding="utf-8"), (
                f"{f.name}: uses os.rename — forbidden on Z:\\BBG_mirror\\"
            )

    def test_no_shutil_move(self, cfg: _FeedCfg) -> None:
        for f in self._src_files(cfg):
            assert "shutil.move" not in f.read_text(encoding="utf-8"), (
                f"{f.name}: uses shutil.move — forbidden on Z:\\BBG_mirror\\"
            )

    def test_no_path_unlink(self, cfg: _FeedCfg) -> None:
        for f in self._src_files(cfg):
            assert ".unlink(" not in f.read_text(encoding="utf-8"), (
                f"{f.name}: uses Path.unlink — forbidden on Z:\\BBG_mirror\\"
            )

    def test_no_open_for_write(self, cfg: _FeedCfg) -> None:
        for f in self._src_files(cfg):
            text = f.read_text(encoding="utf-8")
            for match in re.finditer(r'open\([^)]*?["\']([rwax+]+)["\']', text):
                mode = match.group(1)
                assert "w" not in mode and "a" not in mode and "x" not in mode, (
                    f"{f.name}: open(..., {mode!r}) — write mode forbidden"
                )


# ── End-to-end runner check ───────────────────────────────────────────


@pytest.fixture
def _mock_feed(cfg: _FeedCfg) -> Any:
    """Register a stand-in feed with archive_after_load=False to exercise
    the runner path without needing the real pipeline + DB."""
    test_name = f"{cfg.name}_test"
    acquirer = MagicMock()
    acquirer.name = test_name

    pipeline = MagicMock()
    pipeline.run.return_value = cfg.rows_loaded
    pipeline._raw_df = None

    formatter = MagicMock()
    formatter.format_subject.return_value = "ok"
    formatter.format_body.return_value = "<html/>"

    feed = VendorFeed(
        name=test_name,
        vendor_code="bloomberg",
        acquirer=acquirer,
        pipeline_builder=lambda files, conn, st: pipeline,
        success_formatter=formatter,
        staleness_pipeline_name=cfg.staleness_pipeline_name,
        archive_after_load=False,
        email_on_zero_rows=False,
    )
    register_feed(feed)
    try:
        yield {"feed": feed, "acquirer": acquirer, "pipeline": pipeline,
               "name": test_name}
    finally:
        VENDOR_FEEDS.pop(test_name, None)


@pytest.fixture
def _patched_deps() -> Any:
    settings = MagicMock()
    settings.email_enabled = True
    settings.email_to = "ops@example.com"
    settings.run_log_dir = ""
    with (
        patch("imdr.vendors.runner.get_settings", return_value=settings),
        patch("imdr.vendors.runner.configure_logging"),
        patch("imdr.vendors.runner.MSSQLConnector") as mock_conn_cls,
        patch("imdr.vendors.runner.send_outlook_email") as mock_send,
    ):
        mock_conn_cls.return_value = MagicMock()
        yield {"send": mock_send}


class TestRunnerHonorsNoMove:
    def test_files_remain_in_place_after_run(
        self, tmp_path: Path, cfg: _FeedCfg, _mock_feed: Any, _patched_deps: Any
    ) -> None:
        from imdr.vendors.runner import run_vendor_feed_daily

        files = cfg.layout(tmp_path)
        _mock_feed["acquirer"].fetch.return_value = _fetch_result(
            _mock_feed["name"], files
        )

        rc = run_vendor_feed_daily(_mock_feed["name"], headless=True)
        assert rc == 0

        for f in files:
            assert f.exists(), f"{f.name} was moved — archive ran"
            assert not (f.parent / "old").exists()
        assert not (tmp_path / "old").exists()

    def test_zero_rows_suppresses_email(
        self, tmp_path: Path, cfg: _FeedCfg, _mock_feed: Any, _patched_deps: Any
    ) -> None:
        from imdr.vendors.runner import run_vendor_feed_daily

        files = cfg.layout(tmp_path)
        _mock_feed["pipeline"].run.return_value = 0
        _mock_feed["acquirer"].fetch.return_value = _fetch_result(
            _mock_feed["name"], files
        )

        rc = run_vendor_feed_daily(_mock_feed["name"], headless=True)
        assert rc == 0
        assert not _patched_deps["send"].called, "0-row fire should not email"
        for f in files:
            assert f.exists()

    def test_nonzero_rows_still_emails(
        self, tmp_path: Path, cfg: _FeedCfg, _mock_feed: Any, _patched_deps: Any
    ) -> None:
        from imdr.vendors.runner import run_vendor_feed_daily

        files = cfg.layout(tmp_path)
        _mock_feed["pipeline"].run.return_value = cfg.rows_loaded
        _mock_feed["acquirer"].fetch.return_value = _fetch_result(
            _mock_feed["name"], files
        )

        rc = run_vendor_feed_daily(_mock_feed["name"], headless=True)
        assert rc == 0
        assert _patched_deps["send"].called
        for f in files:
            assert f.exists()
