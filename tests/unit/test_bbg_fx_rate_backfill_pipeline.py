"""Tests for ``BloombergFXRateBackfillPipeline``.

Covers the two things the backfill class adds over the DAILY pipeline:
keeping the CSV's full historical tail, and narrowing it to an obs_date
window.

Context: ``BBG_mirror\\FX`` was provisioned with 22 currency folders and none
of CNY/CNO/MYO/IDO, so USD/CNY, USD/IDO and USD/MYO stopped at 2026-04-24 --
the day the FX feed cut over to the mirror. The legacy ``BBG\\FX`` tree kept
carrying them, so ~98 business days were recoverable from a file already on
disk. Keeping the tail is only safe because the DAILY parent re-stamps
``obs_ts`` to midnight UTC per obs_date; the SNAPSHOT path stamps every row
with the file mtime, which would collide on the unique key.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from imdr.domains.fx.pipeline_rate_bbg import BloombergFXRatePipeline
from imdr.domains.fx.pipeline_rate_bbg_backfill import (
    BloombergFXRateBackfillPipeline,
)
from imdr.domains.fx.pipeline_rate_bbg_daily import BloombergFXRateDailyPipeline

# Four business days of a two-tenor pair, newest last.
_ROWS = (
    "24/04/2026,159.20,159.0100\n"
    "27/04/2026,159.30,159.1100\n"
    "28/04/2026,159.40,159.2100\n"
    "29/04/2026,159.55,159.4400\n"
)


@pytest.fixture
def jpy_csv(tmp_path: Path) -> Path:
    folder = tmp_path / "JPY"
    folder.mkdir()
    f = folder / "FX_JPY.csv"
    f.write_text(
        "Ticker,JPY curncy,JPY1M curncy\n"
        "Tenor,FX_JPY_SPOT,FX_JPY_1M\n"
        "Maturity,0,0.083333333\n" + _ROWS
    )
    return f


def _pipeline(files, **kw):
    return BloombergFXRateBackfillPipeline(
        files=files, connector=MagicMock(), settings=MagicMock(), **kw
    )


# ---------------------------------------------------------------------------
# Cadence flags
# ---------------------------------------------------------------------------

def test_live_pipelines_keep_only_the_newest_row():
    """Guards the flag that makes the live path safe.

    Every row a live fire reads shares the file's mtime as obs_ts, so keeping
    the tail would collide on (pair, vendor, freq, obs_ts, tenor).
    """
    assert BloombergFXRatePipeline.KEEP_ONLY_LATEST is True
    assert BloombergFXRateDailyPipeline.KEEP_ONLY_LATEST is True


def test_backfill_keeps_the_tail_and_stays_daily():
    assert BloombergFXRateBackfillPipeline.KEEP_ONLY_LATEST is False
    assert BloombergFXRateBackfillPipeline.FREQUENCY_CODE == "DAILY"
    assert BloombergFXRateBackfillPipeline.pipeline_name == "fx.bloomberg_backfill"


# ---------------------------------------------------------------------------
# Extract
# ---------------------------------------------------------------------------

def test_daily_pipeline_still_collapses_to_one_date(jpy_csv: Path):
    """The regression guard: the live cadence must NOT gain the tail."""
    df = BloombergFXRateDailyPipeline(
        files=[jpy_csv], connector=MagicMock(), settings=MagicMock(),
    ).extract()
    assert set(df["obs_date"].astype(str)) == {"2026-04-29"}


def test_backfill_keeps_every_obs_date(jpy_csv: Path):
    df = _pipeline([jpy_csv]).extract()
    assert sorted(set(df["obs_date"].astype(str))) == [
        "2026-04-24", "2026-04-27", "2026-04-28", "2026-04-29",
    ]


def test_obs_ts_is_midnight_utc_per_obs_date(jpy_csv: Path):
    """This is what makes the tail loadable — one key per business day."""
    df = _pipeline([jpy_csv]).extract()
    assert df["obs_ts"].nunique() == 4
    for ts, obs in zip(df["obs_ts"], df["obs_date"]):
        assert (ts.hour, ts.minute, ts.second) == (0, 0, 0)
        assert ts.tzinfo is not None
        assert ts.date() == obs
    assert df["obs_ts"].min() == datetime(2026, 4, 24, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Window
# ---------------------------------------------------------------------------

def test_since_excludes_earlier_dates(jpy_csv: Path):
    """The real repair: skip 04-24, which was already in the table."""
    df = _pipeline([jpy_csv], since=date(2026, 4, 25)).extract()
    assert sorted(set(df["obs_date"].astype(str))) == [
        "2026-04-27", "2026-04-28", "2026-04-29",
    ]


def test_until_excludes_later_dates(jpy_csv: Path):
    df = _pipeline([jpy_csv], until=date(2026, 4, 27)).extract()
    assert sorted(set(df["obs_date"].astype(str))) == [
        "2026-04-24", "2026-04-27",
    ]


def test_window_is_inclusive_on_both_ends(jpy_csv: Path):
    df = _pipeline([jpy_csv], since=date(2026, 4, 27),
                   until=date(2026, 4, 28)).extract()
    assert sorted(set(df["obs_date"].astype(str))) == [
        "2026-04-27", "2026-04-28",
    ]


def test_window_matching_nothing_yields_empty_not_error(jpy_csv: Path):
    df = _pipeline([jpy_csv], since=date(2027, 1, 1)).extract()
    assert df.empty


def test_no_window_keeps_everything(jpy_csv: Path):
    assert _pipeline([jpy_csv]).extract()["obs_date"].nunique() == 4


def test_raw_df_reflects_the_window(jpy_csv: Path):
    """post_load/reporting read _raw_df; it must not hold the pre-filter set."""
    p = _pipeline([jpy_csv], since=date(2026, 4, 28))
    df = p.extract()
    assert p._raw_df is not None
    assert len(p._raw_df) == len(df)
    assert p._raw_df["obs_date"].nunique() == 2
