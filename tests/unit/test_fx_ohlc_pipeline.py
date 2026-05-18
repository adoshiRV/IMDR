"""Tests for `pipeline_ohlc.py` — the FX OHLC orchestrator + helpers.

Covers:
- `HourResult` dataclass defaults
- `_build_quality_checks` threshold wiring from CleaningConfig
- `_anomaly_prescreen` batched-repo contract + empty-bars short-circuit
- `_write_parquet` success / failure paths (returns None vs diagnostic dict)
- `process_hour` full orchestrator: empty bars, happy path, validation failure,
  anomaly detection, parquet failure surfaced in `result.diagnostics`,
  thresholds plumbed from `get_pipeline_config("fx.ohlc").cleaning`
- `FXOHLCPipeline.get_run_context` shape

Mocks `BidFXExtractor`, `FXOHLCRepository`, `get_pipeline_config`, and the
session context manager at the module boundary.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from imdr.config.pipeline_config import CleaningConfig
from imdr.domains.fx.pipeline_ohlc import (
    FXOHLCPipeline,
    HourResult,
    _anomaly_prescreen,
    _build_quality_checks,
    _write_parquet,
    process_hour,
)
from imdr.utils.time_windows import HourWindow

UTC = timezone.utc
HOUR_TS = datetime(2026, 5, 1, 13, 0, tzinfo=UTC)


def _make_window() -> HourWindow:
    return HourWindow(start=HOUR_TS, end=datetime(2026, 5, 1, 14, 0, tzinfo=UTC))


def _make_bar(symbol: str = "EURUSD", series: str = "SPOT", close: float = 1.085) -> dict:
    """A minimal extractor-output bar that passes FXFactOHLCCreate validation."""
    return {
        "ts": HOUR_TS,
        "symbol": symbol,
        "series": series,
        "tenor": "SPOT",
        "deal_type": "SPOT",
        "pair_used": symbol,
        "open_px": close - 0.001,
        "high_px": close + 0.001,
        "low_px": close - 0.002,
        "close_px": close,
        "mid_px": close,
        "mid_mean_px": close,
        "mid_median_px": close,
        "bid": close - 0.0005,
        "ask": close + 0.0005,
        "n_ticks": 10,
    }


def _make_universe(active_currencies: list[str] | None = None) -> MagicMock:
    universe = MagicMock(name="FXUniverse")
    universe.api_symbols.return_value = ["EURUSD", "USDJPY"]
    universe.currency_from_symbol.side_effect = lambda s: s.replace("USD", "")
    universe.expected_ranges = {}
    universe.expected_range_for.return_value = None
    universe.active_currencies = active_currencies or ["EUR", "JPY"]
    return universe


def _make_settings() -> MagicMock:
    settings = MagicMock(name="Settings")
    settings.anomaly_pct_threshold = 5.0
    settings.parquet_batch_dir = None
    settings.bidfx_max_workers = 4
    return settings


def _make_report() -> MagicMock:
    return MagicMock(name="RunReport")


def _patch_extractor(bars: list[dict], diagnostics: list | None = None):
    """Return a context manager patching BidFXExtractor to yield the given bars."""
    mock_extractor_instance = MagicMock(name="BidFXExtractor_instance")
    mock_extractor_instance.extract.return_value = bars
    mock_extractor_instance.diagnostics = diagnostics or []
    mock_extractor_class = MagicMock(return_value=mock_extractor_instance)
    return patch(
        "imdr.domains.fx.pipeline_ohlc.BidFXExtractor",
        mock_extractor_class,
    )


def _patch_get_pipeline_config(cleaning: CleaningConfig | None = None):
    """Patch get_pipeline_config to return a config with the given cleaning section."""
    cfg = MagicMock(name="PipelineConfig")
    cfg.cleaning = cleaning or CleaningConfig()
    return patch(
        "imdr.domains.fx.pipeline_ohlc.get_pipeline_config",
        return_value=cfg,
    )


def _patch_session_repo(repo: MagicMock):
    """Build a mock connector where `with connector.session() as s:` yields a session,
    and patch FXOHLCRepository to return the given repo mock.
    """
    connector = MagicMock(name="MSSQLConnector")
    session_cm = MagicMock(name="session_cm")
    session_cm.__enter__ = MagicMock(return_value=MagicMock(name="session"))
    session_cm.__exit__ = MagicMock(return_value=None)
    connector.session.return_value = session_cm
    return connector, patch(
        "imdr.domains.fx.pipeline_ohlc.FXOHLCRepository",
        return_value=repo,
    )


# ---------------------------------------------------------------------------
# HourResult
# ---------------------------------------------------------------------------


class TestHourResult:
    def test_defaults_initialize_empty_lists(self) -> None:
        result = HourResult(window=_make_window())
        assert result.bars_produced == 0
        assert result.bars_approved == 0
        assert result.bars_dropped == 0
        assert result.bars == []
        assert result.diagnostics == []
        assert result.missing_ccy == []
        assert result.anomalies == []
        assert result.quality_flags == []


# ---------------------------------------------------------------------------
# _build_quality_checks — config threshold wiring
# ---------------------------------------------------------------------------


class TestBuildQualityChecks:
    def test_returns_five_checks(self) -> None:
        cleaning = CleaningConfig(n_mad=6.0, trailing_months=3, pct_threshold=7.0, min_obs=100)
        checks = _build_quality_checks(_make_universe(), cleaning)
        assert len(checks) == 5

    def test_threshold_pct_from_config(self) -> None:
        """pct_threshold should flow from config to PercentageChangeCheck."""
        cleaning = CleaningConfig(pct_threshold=7.5)
        checks = _build_quality_checks(_make_universe(), cleaning)
        # PercentageChangeCheck is index 2 in the returned list; stored on
        # the private `_threshold` attribute per healthchecks.quality.
        pct_check = checks[2]
        assert pct_check._threshold == 7.5

    def test_pct_threshold_falls_back_to_default(self) -> None:
        """When pct_threshold is None in config, fallback to 5.0 (preserves
        the previous hardcoded behavior)."""
        cleaning = CleaningConfig(pct_threshold=None)
        checks = _build_quality_checks(_make_universe(), cleaning)
        pct_check = checks[2]
        assert pct_check._threshold == 5.0

    def test_robust_outlier_n_mad_and_trailing_from_config(self) -> None:
        cleaning = CleaningConfig(n_mad=6.0, trailing_months=3)
        checks = _build_quality_checks(_make_universe(), cleaning)
        # RobustStatisticalOutlierCheck is the last entry.
        outlier_check = checks[-1]
        assert outlier_check._n_mad == 6.0
        assert outlier_check._trailing_months == 3


# ---------------------------------------------------------------------------
# _anomaly_prescreen — batched repo contract
# ---------------------------------------------------------------------------


class TestAnomalyPrescreen:
    def test_empty_bars_returns_empty_list_no_repo_call(self) -> None:
        """Short-circuit: zero bars in → zero anomalies, no session opened."""
        connector = MagicMock(name="MSSQLConnector")
        result = _anomaly_prescreen([], connector, threshold_pct=5.0)
        assert result == []
        connector.session.assert_not_called()

    def test_uses_batched_repo_call_not_n_plus_one(self) -> None:
        """The prescreen must call `get_last_closes_batch` exactly once,
        not loop `get_last_close` per bar (the N+1 we just fixed)."""
        from imdr.schemas.fx_ohlc import FXFactOHLCCreate
        bars = [
            FXFactOHLCCreate.model_validate(_make_bar("EURUSD", "SPOT", 1.085)),
            FXFactOHLCCreate.model_validate(_make_bar("USDJPY", "SPOT", 150.0)),
            FXFactOHLCCreate.model_validate(_make_bar("GBPUSD", "SPOT", 1.265)),
        ]
        repo = MagicMock(name="FXOHLCRepository")
        # No previous closes → no anomalies, but the batch method must be called.
        repo.get_last_closes_batch.return_value = {}

        connector, repo_patcher = _patch_session_repo(repo)
        with repo_patcher:
            _anomaly_prescreen(bars, connector, threshold_pct=5.0)

        # Exactly one batched call — not three per-bar calls.
        assert repo.get_last_closes_batch.call_count == 1
        # Verify the batched call received the right keys.
        called_keys, called_ts = repo.get_last_closes_batch.call_args.args
        assert set(called_keys) == {("EURUSD", "SPOT"), ("USDJPY", "SPOT"), ("GBPUSD", "SPOT")}
        assert called_ts == HOUR_TS

    def test_no_get_last_close_method_remains(self) -> None:
        """Source-code regression guard: the single-row ``get_last_close``
        was removed when the batched version replaced it. A reintroduction
        is a strong signal the N+1 is creeping back in."""
        import inspect

        from imdr.domains.fx.repository_ohlc import FXOHLCRepository

        src = inspect.getsource(FXOHLCRepository)
        assert "def get_last_close(" not in src, (
            "FXOHLCRepository.get_last_close was removed in favor of "
            "get_last_closes_batch (one query for many keys). Don't "
            "reintroduce it — it leads to N+1 access patterns."
        )

    def test_anomaly_flagged_when_pct_change_exceeds_threshold(self) -> None:
        from imdr.schemas.fx_ohlc import FXFactOHLCCreate
        bars = [FXFactOHLCCreate.model_validate(_make_bar("EURUSD", "SPOT", 1.20))]
        # Previous close is 1.00 → +20% jump, far exceeds 5% threshold.
        prev = MagicMock(close_px=1.00)
        repo = MagicMock(name="FXOHLCRepository")
        repo.get_last_closes_batch.return_value = {("EURUSD", "SPOT"): prev}

        connector, repo_patcher = _patch_session_repo(repo)
        with repo_patcher:
            anomalies = _anomaly_prescreen(bars, connector, threshold_pct=5.0)

        assert len(anomalies) == 1
        assert anomalies[0]["symbol"] == "EURUSD"
        assert anomalies[0]["series"] == "SPOT"
        assert anomalies[0]["previous"] == 1.00
        assert anomalies[0]["current"] == 1.20
        assert anomalies[0]["pct_change"] == pytest.approx(20.0)

    def test_no_anomaly_when_previous_close_is_zero(self) -> None:
        """Zero previous-close guard — division-by-zero protection."""
        from imdr.schemas.fx_ohlc import FXFactOHLCCreate
        bars = [FXFactOHLCCreate.model_validate(_make_bar("EURUSD", "SPOT", 1.20))]
        prev = MagicMock(close_px=0.0)
        repo = MagicMock(name="FXOHLCRepository")
        repo.get_last_closes_batch.return_value = {("EURUSD", "SPOT"): prev}

        connector, repo_patcher = _patch_session_repo(repo)
        with repo_patcher:
            anomalies = _anomaly_prescreen(bars, connector, threshold_pct=5.0)

        assert anomalies == []


# ---------------------------------------------------------------------------
# _write_parquet
# ---------------------------------------------------------------------------


class TestWriteParquet:
    def test_success_returns_none_and_writes_file(self, tmp_path: Path) -> None:
        from imdr.schemas.fx_ohlc import FXFactOHLCCreate
        bars = [FXFactOHLCCreate.model_validate(_make_bar())]
        result = _write_parquet(bars, _make_window(), str(tmp_path))

        assert result is None
        expected = tmp_path / "fx" / "fact_ohlc" / "2026" / "05" / "01" / "fx_ohlc_20260501_1300.parquet"
        assert expected.exists()
        # Round-trip verification
        df = pd.read_parquet(expected)
        assert len(df) == 1
        assert df.iloc[0]["symbol"] == "EURUSD"

    def test_failure_returns_diagnostic_dict_not_silent(self, tmp_path: Path) -> None:
        """Previous behavior was silent (log only); now the failure is
        captured in a structured dict so the orchestrator can append it
        to `result.diagnostics`."""
        from imdr.schemas.fx_ohlc import FXFactOHLCCreate
        bars = [FXFactOHLCCreate.model_validate(_make_bar())]

        # Force failure at the to_parquet step. mkdir() succeeds against
        # tmp_path; the patched to_parquet raises and exercises the new
        # diagnostic-return branch.
        with patch("pandas.DataFrame.to_parquet", side_effect=OSError("disk full")):
            result = _write_parquet(bars, _make_window(), str(tmp_path))

        assert result is not None
        assert result["step"] == "parquet"
        assert "disk full" in result["error"]
        assert result["batch_dir"] == str(tmp_path)
        assert "2026-05-01" in result["window"]


# ---------------------------------------------------------------------------
# process_hour — orchestrator
# ---------------------------------------------------------------------------


class TestProcessHourEmpty:
    def test_no_bars_returns_early_with_warning(self) -> None:
        """When the extractor yields zero bars, process_hour should warn
        and return immediately without touching the DB or running quality."""
        universe = _make_universe()
        settings = _make_settings()
        report = _make_report()
        connector = MagicMock(name="MSSQLConnector")

        with _patch_extractor(bars=[]), _patch_get_pipeline_config():
            result = process_hour(_make_window(), universe, settings, connector, report)

        assert result.bars_produced == 0
        assert result.bars_approved == 0
        assert result.bars == []
        # Warning was emitted for empty extraction.
        warning_categories = [c.args[0] for c in report.warning.call_args_list]
        assert "extract" in warning_categories
        # No DB session opened.
        connector.session.assert_not_called()


class TestProcessHourHappyPath:
    def test_writes_to_db_and_returns_counts(self) -> None:
        bars = [_make_bar("EURUSD"), _make_bar("USDJPY", close=150.0)]
        universe = _make_universe()
        settings = _make_settings()
        report = _make_report()
        repo = MagicMock(name="FXOHLCRepository")
        repo.get_last_closes_batch.return_value = {}  # no previous closes → no anomalies

        connector, repo_patcher = _patch_session_repo(repo)
        with _patch_extractor(bars=bars), _patch_get_pipeline_config(), repo_patcher:
            with patch("imdr.domains.fx.pipeline_ohlc._post_ingest_quality", return_value=[]):
                result = process_hour(_make_window(), universe, settings, connector, report)

        assert result.bars_produced == 2
        assert result.bars_approved == 2
        assert result.bars_dropped == 0
        # bulk_upsert was called with the two validated bars.
        repo.bulk_upsert.assert_called_once()
        approved_bars = repo.bulk_upsert.call_args.args[0]
        assert len(approved_bars) == 2


class TestProcessHourCurrenciesFilter:
    def test_currencies_filter_restricts_expected_symbols(self) -> None:
        """When `currencies={'EUR'}` is passed, expected_symbols only includes
        symbols whose currency matches — drives the missing_ccy computation."""
        bars = [_make_bar("EURUSD")]
        universe = _make_universe()
        # Make currency_from_symbol return EUR for EURUSD, JPY for USDJPY.
        universe.currency_from_symbol.side_effect = (
            lambda s: "EUR" if s == "EURUSD" else "JPY"
        )
        settings = _make_settings()
        report = _make_report()
        repo = MagicMock(name="FXOHLCRepository")
        repo.get_last_closes_batch.return_value = {}

        connector, repo_patcher = _patch_session_repo(repo)
        with _patch_extractor(bars=bars), _patch_get_pipeline_config(), repo_patcher:
            with patch("imdr.domains.fx.pipeline_ohlc._post_ingest_quality", return_value=[]):
                result = process_hour(
                    _make_window(), universe, settings, connector, report,
                    currencies={"EUR"},
                )

        # Only EURUSD expected (USDJPY excluded by currency filter); produced
        # set matches → missing_ccy empty.
        assert result.missing_ccy == []


class TestProcessHourParquetFailureCaptured:
    def test_parquet_failure_appended_to_diagnostics(self) -> None:
        """A parquet write failure was previously silent; now it lands in
        `result.diagnostics` with step='parquet'."""
        bars = [_make_bar("EURUSD")]
        universe = _make_universe()
        settings = _make_settings()
        settings.parquet_batch_dir = "/no/such/dir"
        report = _make_report()
        repo = MagicMock(name="FXOHLCRepository")
        repo.get_last_closes_batch.return_value = {}

        connector, repo_patcher = _patch_session_repo(repo)
        with _patch_extractor(bars=bars), _patch_get_pipeline_config(), repo_patcher:
            with patch("imdr.domains.fx.pipeline_ohlc._post_ingest_quality", return_value=[]):
                with patch(
                    "imdr.domains.fx.pipeline_ohlc._write_parquet",
                    return_value={
                        "step": "parquet",
                        "error": "OSError: disk full",
                        "batch_dir": "/no/such/dir",
                        "window": "2026-05-01 13:00 UTC",
                    },
                ):
                    result = process_hour(
                        _make_window(), universe, settings, connector, report,
                    )

        parquet_diags = [d for d in result.diagnostics if d.get("step") == "parquet"]
        assert len(parquet_diags) == 1
        assert "disk full" in parquet_diags[0]["error"]
        # The orchestrator also routed it through report.warning.
        warning_categories = [c.args[0] for c in report.warning.call_args_list]
        assert "parquet" in warning_categories


class TestProcessHourConfigPlumbing:
    def test_quality_thresholds_pulled_from_pipeline_config(self) -> None:
        """`process_hour` must call `get_pipeline_config('fx.ohlc')` and pass
        its `.cleaning` section into `_post_ingest_quality`. Pin the wiring
        so a future refactor can't silently re-hardcode the thresholds."""
        bars = [_make_bar("EURUSD")]
        universe = _make_universe()
        settings = _make_settings()
        report = _make_report()
        repo = MagicMock(name="FXOHLCRepository")
        repo.get_last_closes_batch.return_value = {}

        custom_cleaning = CleaningConfig(n_mad=6.0, trailing_months=3, pct_threshold=7.5)

        connector, repo_patcher = _patch_session_repo(repo)
        with _patch_extractor(bars=bars), _patch_get_pipeline_config(custom_cleaning) as mock_get_cfg, repo_patcher:
            with patch(
                "imdr.domains.fx.pipeline_ohlc._post_ingest_quality",
                return_value=[],
            ) as mock_quality:
                process_hour(_make_window(), universe, settings, connector, report)

        mock_get_cfg.assert_called_once_with("fx.ohlc")
        # The cleaning section is the 4th positional arg of _post_ingest_quality.
        passed_cleaning = mock_quality.call_args.args[3]
        assert passed_cleaning.n_mad == 6.0
        assert passed_cleaning.trailing_months == 3
        assert passed_cleaning.pct_threshold == 7.5


# ---------------------------------------------------------------------------
# FXOHLCPipeline
# ---------------------------------------------------------------------------


class TestFXOHLCPipeline:
    def test_get_run_context_includes_window_and_date(self) -> None:
        connector = MagicMock(name="MSSQLConnector")
        pipeline = FXOHLCPipeline(
            connector=connector,
            settings=_make_settings(),
            universe=_make_universe(),
            window=_make_window(),
        )
        ctx = pipeline.get_run_context()
        assert ctx["run_date"] == HOUR_TS.date()
        assert "2026-05-01" in ctx["window"]

    def test_extract_and_transform_are_noops(self) -> None:
        """Until the BasePipeline ABC abuse is addressed (see deferral doc),
        FXOHLCPipeline.extract and .transform both return None. Pin the
        current shape so the deferred refactor is visible later."""
        pipeline = FXOHLCPipeline(
            connector=MagicMock(name="MSSQLConnector"),
            settings=_make_settings(),
            universe=_make_universe(),
            window=_make_window(),
        )
        assert pipeline.extract() is None
        assert pipeline.transform(None) is None
