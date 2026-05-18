"""Tests for ``BloombergFXRateDailyPipeline``.

Covers the daily class's only novel behavior: rewriting ``obs_ts`` to
midnight UTC of ``obs_date`` so MERGE keys at DAILY frequency don't
collide with the SNAPSHOT rows that share the same source file.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from imdr.domains.fx.pipeline_rate_bbg_daily import BloombergFXRateDailyPipeline


@pytest.fixture
def jpy_csv(tmp_path: Path) -> Path:
    folder = tmp_path / "JPY"
    folder.mkdir()
    f = folder / "FX_JPY.csv"
    f.write_text(
        "Ticker,JPY curncy,JPY1M curncy\n"
        "Tenor,FX_JPY_SPOT,FX_JPY_1M\n"
        "Maturity,0,0.083333333\n"
        "23/04/2026,159.55,159.1444\n"
    )
    return f


class TestDailyExtractMidnightUTC:
    def test_obs_ts_is_midnight_utc_of_obs_date(self, jpy_csv: Path) -> None:
        """Daily pipeline must override mtime-based obs_ts with midnight UTC."""
        pipeline = BloombergFXRateDailyPipeline(
            files=[jpy_csv],
            connector=MagicMock(),
            settings=MagicMock(),
        )
        df = pipeline.extract()

        assert not df.empty
        for ts in df["obs_ts"]:
            assert ts.hour == 0
            assert ts.minute == 0
            assert ts.second == 0
            assert ts.tzinfo is not None
            # Matches the obs_date business day
        assert df["obs_ts"].iloc[0] == datetime(2026, 4, 23, tzinfo=timezone.utc)

    def test_ts_alias_present(self, jpy_csv: Path) -> None:
        """`ts` alias is kept for downstream consumers expecting it."""
        pipeline = BloombergFXRateDailyPipeline(
            files=[jpy_csv],
            connector=MagicMock(),
            settings=MagicMock(),
        )
        df = pipeline.extract()
        assert "ts" in df.columns
        assert (df["ts"] == df["obs_ts"]).all()

    def test_empty_extract_returns_empty(self) -> None:
        pipeline = BloombergFXRateDailyPipeline(
            files=[],
            connector=MagicMock(),
            settings=MagicMock(),
        )
        df = pipeline.extract()
        assert df.empty


class TestDailyClassWiring:
    def test_pipeline_name(self) -> None:
        assert BloombergFXRateDailyPipeline.pipeline_name == "fx.bloomberg_daily"

    def test_frequency_code_overrides_parent_snapshot(self) -> None:
        """Subclass must stamp DAILY, not SNAPSHOT (parent default)."""
        assert BloombergFXRateDailyPipeline.FREQUENCY_CODE == "DAILY"
