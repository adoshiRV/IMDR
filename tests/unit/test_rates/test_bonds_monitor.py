"""Track C: econ-monitor BBG store -> rates.fact_bond_yield.

Covers the transform contract in scripts/rates/bonds_monitor.extract, which is the part
that can silently corrupt the panel: weekday filtering, vintage selection, and ticker
resolution through dim_bond_source. Builds a throwaway SQLite with the monitor's shape --
no network, no IMDR, no live file.
"""
from __future__ import annotations

import sqlite3
from datetime import date

import pytest

from scripts.rates.bonds_monitor import extract

BBG_VENDOR_ID = 4
DAILY_FREQUENCY_ID = 5

_AXES = {
    "tenor_code": "10Y", "tenor_days": 3650, "quote_type": "YIELD",
    "spread_anchor": "NONE", "fwd_start": "SPOT", "horizon": "NONE", "units": "PCT",
}


@pytest.fixture()
def sources() -> dict[str, dict]:
    return {
        "GUKG10 INDEX": {"bond_curve_id": 11, **_AXES},
        "USGGBE10 INDEX": {"bond_curve_id": 9, **_AXES, "quote_type": "BREAKEVEN"},
    }


def _db(rows: list[tuple], legs: list[tuple] | None = None) -> sqlite3.Connection:
    """(series_id, obs_date, close, vintage) rows on the monitor's schema."""
    cn = sqlite3.connect(":memory:")
    cn.execute("CREATE TABLE dim_rate_instrument (series_id TEXT PRIMARY KEY, bbg_ticker TEXT, kind TEXT)")
    cn.execute("CREATE TABLE fact_market_daily (series_id TEXT, obs_date TEXT, close REAL, "
               "vintage INTEGER, PRIMARY KEY (series_id, obs_date, vintage))")
    cn.executemany("INSERT INTO dim_rate_instrument VALUES (?,?,'INDEX')",
                   legs or [("BBG.RATES.GOVT_10Y.GB", "GUKG10 Index")])
    cn.executemany("INSERT INTO fact_market_daily VALUES (?,?,?,?)", rows)
    return cn


def test_weekend_rows_are_dropped():
    # 2026-08-28 Fri, 29 Sat, 30 Sun, 31 Mon -- the ALL_CALENDAR_DAYS padding.
    cn = _db([("BBG.RATES.GOVT_10Y.GB", d, 4.0, 0)
              for d in ("2026-08-28", "2026-08-29", "2026-08-30", "2026-08-31")])
    rows, stats = extract(cn, {"GUKG10 INDEX": {"bond_curve_id": 11, **_AXES}}, None)
    assert [r.obs_date for r in rows] == [date(2026, 8, 28), date(2026, 8, 31)]
    assert stats["weekend_dropped"] == 2


def test_only_highest_vintage_per_date_is_read():
    cn = _db([
        ("BBG.RATES.GOVT_10Y.GB", "2026-08-31", 4.10, 0),
        ("BBG.RATES.GOVT_10Y.GB", "2026-08-31", 4.25, 1),   # the revision
    ])
    rows, _ = extract(cn, {"GUKG10 INDEX": {"bond_curve_id": 11, **_AXES}}, None)
    assert [r.value for r in rows] == [4.25]


def test_null_close_is_skipped_not_zeroed():
    cn = _db([
        ("BBG.RATES.GOVT_10Y.GB", "2026-08-28", None, 0),
        ("BBG.RATES.GOVT_10Y.GB", "2026-08-31", 4.0, 0),
    ])
    rows, _ = extract(cn, {"GUKG10 INDEX": {"bond_curve_id": 11, **_AXES}}, None)
    assert [(r.obs_date, r.value) for r in rows] == [(date(2026, 8, 31), 4.0)]


def test_unmapped_ticker_is_reported_not_loaded(sources):
    """KRFRINDX (KOFR index) is a rate, not a bond -- absent from migration 126 by design."""
    cn = _db(
        [("BBG.RATES.bbg-manual-kofr-index", "2026-08-31", 2.5, 0)],
        legs=[("BBG.RATES.bbg-manual-kofr-index", "KRFRINDX Index")],
    )
    rows, stats = extract(cn, sources, None)
    assert rows == []
    assert stats["unmapped"] == [("BBG.RATES.bbg-manual-kofr-index", "KRFRINDX Index")]
    assert stats["legs_loaded"] == 0


def test_axes_come_from_dim_bond_source_not_the_monitor(sources):
    """quote_type/curve are the SOURCE MAP's business -- a breakeven must not land as YIELD."""
    cn = _db(
        [("BBG.RATES.BEI_10Y.US", "2026-08-31", 2.3, 0)],
        legs=[("BBG.RATES.BEI_10Y.US", "USGGBE10 Index")],
    )
    rows, _ = extract(cn, sources, None)
    assert len(rows) == 1
    assert (rows[0].quote_type, rows[0].bond_curve_id) == ("BREAKEVEN", 9)
    assert (rows[0].vendor_id, rows[0].frequency_id) == (BBG_VENDOR_ID, DAILY_FREQUENCY_ID)


def test_ticker_resolution_is_case_insensitive_but_stores_byte_exact(sources):
    """dim_bond_source holds byte-exact vendor strings with inconsistent case."""
    cn = _db([("BBG.RATES.GOVT_10Y.GB", "2026-08-31", 4.0, 0)])
    rows, _ = extract(cn, sources, None)
    assert rows[0].source_ticker == "GUKG10 Index"   # preserved, not upper-cased


def test_tickers_filter_restricts_the_pull(sources):
    cn = _db(
        [("BBG.RATES.GOVT_10Y.GB", "2026-08-31", 4.0, 0),
         ("BBG.RATES.BEI_10Y.US", "2026-08-31", 2.3, 0)],
        legs=[("BBG.RATES.GOVT_10Y.GB", "GUKG10 Index"),
              ("BBG.RATES.BEI_10Y.US", "USGGBE10 Index")],
    )
    rows, stats = extract(cn, sources, ["USGGBE10 Index"])
    assert [r.source_ticker for r in rows] == ["USGGBE10 Index"]
    assert stats["legs_loaded"] == 1
