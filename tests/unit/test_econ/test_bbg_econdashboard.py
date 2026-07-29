"""No-network tests for the BBG EconDashboards econ ingest library.

Covers the pure resolvers (unit / frequency / concept) and the imdr_code
assignment logic -- in particular that a collision-disambiguation suffix, once
persisted, is reused via ``existing_codes`` and never migrates to a different
ticker when the upstream catalogue grows (the stability contract).
"""

from __future__ import annotations

import sqlite3

import pytest

from imdr.domains.econ.bbg_econdashboard import (
    _concept,
    _resolve_frequency,
    _resolve_unit,
    fetch_econdashboard,
)


class TestResolveUnit:
    @pytest.mark.parametrize(
        "cat,ccy,quote,expected",
        [
            # trade: local currency at native scale
            ("exports", "AUD", "Million", "aud_mn"),
            ("imports", "IDR", "Billion", "idr_bn"),
            ("exports", "INR", "Crores", "inr_cr"),
            ("imports", "TWD", "Billion", "twd_bn"),
            ("exports", "MYR", "Million", "myr_mn"),
            # US trade contribution: no currency, quoted as %
            ("exports", None, "%", "pct"),
            ("imports", None, "Percent", "pct"),
            # fixed-unit categories ignore ccy/quote
            ("pmi", None, None, "index"),
            ("big_mac", "USD", None, "usd"),
            ("neer", None, None, "index_2020_100"),
            ("current_account", "AUD", "% RATIO", "pct_of_gdp"),
            ("cpi_yoy", None, "% CHANGE", "pct_yoy"),
        ],
    )
    def test_units(self, cat, ccy, quote, expected) -> None:
        assert _resolve_unit(cat, ccy, quote) == expected

    @pytest.mark.parametrize(
        "quote,expected",
        [
            ("% CHANGE", "pct_yoy"),
            ("%", "pct_yoy"),
            (None, "pct_yoy"),
            ("2010=100", "index"),   # base-year tag
            ("Index", "index"),      # literal word (the hardening fix)
        ],
    )
    def test_core_cpi_index_vs_yoy(self, quote, expected) -> None:
        assert _resolve_unit("core_cpi_yoy", None, quote) == expected


class TestResolveFrequency:
    @pytest.mark.parametrize(
        "native,cat,expected",
        [
            ("Monthly", "cpi_yoy", "MONTHLY"),
            ("Quarterly", "gdp_yoy", "QUARTERLY"),
            ("Yearly", "big_mac", "ANNUAL"),
            ("Intraday", "surprise", "SNAPSHOT"),
            (None, "surprise", "DAILY"),        # category default
            (None, "gdp_yoy", "QUARTERLY"),     # GDP must not fall back to MONTHLY
            (None, "cpi_yoy", "MONTHLY"),       # generic fallback
        ],
    )
    def test_frequency(self, native, cat, expected) -> None:
        assert _resolve_frequency(native, cat) == expected


class TestConcept:
    def test_us_trade_contribution_override(self) -> None:
        assert _concept("exports", "US") == "TRADE.EXPORTS_CONTRIB"
        assert _concept("imports", "US") == "TRADE.IMPORTS_CONTRIB"

    def test_non_us_trade_is_generic(self) -> None:
        assert _concept("exports", "AU") == "TRADE.EXPORTS"
        assert _concept("cpi_yoy", "KR") == "CPI.YOY"


# --------------------------------------------------------------------------
# Code assignment / collision stability (driven through a temp SQLite)
# --------------------------------------------------------------------------

_SERIES_COLS = (
    "ticker, country_code, country_name, category, category_label, "
    "native_frequency, seasonality_transform, currency, quote_units"
)


def _make_db(tmp_path, series_rows, obs_rows):
    path = tmp_path / "econ_dashboard.sqlite3"
    con = sqlite3.connect(str(path))
    con.execute(
        "CREATE TABLE series (ticker TEXT, country_code TEXT, country_name TEXT, "
        "category TEXT, category_label TEXT, native_frequency TEXT, "
        "seasonality_transform TEXT, currency TEXT, quote_units TEXT)"
    )
    con.execute(
        "CREATE TABLE observations (ticker TEXT, observation_date TEXT, value REAL, "
        "source_updated_at TEXT)"
    )
    con.executemany(f"INSERT INTO series ({_SERIES_COLS}) VALUES (?,?,?,?,?,?,?,?,?)", series_rows)
    con.executemany("INSERT INTO observations VALUES (?,?,?,?)", obs_rows)
    con.commit()
    con.close()
    return path


def _codes(indicators):
    return {i.source_code: i.imdr_code for i in indicators}


def test_excluded_categories_are_skipped(tmp_path) -> None:
    series = [
        ("AUCPIYOY Index", "AU", "Australia", "cpi_yoy", "CPI YoY", "Monthly", None, None, "% CHANGE"),
        ("ADSWAP5 Curncy", "AU", "Australia", "swap_5y", "5Y swap", "Daily", None, "AUD", "%"),
        ("RBATCTR Index", "AU", "Australia", "policy_rate", "Cash rate", "Daily", None, "AUD", "%"),
        ("CO1 Comdty", "AU", "Australia", "oil_price", "Brent", None, None, "USD", "USD/bbl."),
    ]
    obs = [(s[0], "2026-07-29", 1.0, None) for s in series]
    inds, _ = fetch_econdashboard("AU", sqlite_path=_make_db(tmp_path, series, obs))
    codes = _codes(inds)
    assert codes == {"AUCPIYOY Index": "BBG.CPI.YOY.AU"}  # only the econ category survives


def test_collision_gets_suffix(tmp_path) -> None:
    # AU carries two core-CPI tickers -> one bare, one .2 (deterministic by ticker order)
    series = [
        ("ACPMXVLY Index", "AU", "Australia", "core_cpi_yoy", "Core CPI m", "Monthly", None, None, "% CHANGE"),
        ("AUUIR Index", "AU", "Australia", "core_cpi_yoy", "Core CPI q", "Quarterly", None, None, "%"),
    ]
    obs = [(s[0], "2026-07-29", 3.0, None) for s in series]
    inds, _ = fetch_econdashboard("AU", sqlite_path=_make_db(tmp_path, series, obs))
    codes = _codes(inds)
    assert set(codes.values()) == {"BBG.CPI.CORE.YOY.AU", "BBG.CPI.CORE.YOY.AU.2"}


def test_existing_codes_are_stable_when_catalogue_grows(tmp_path) -> None:
    """A newly-added ticker that sorts alphabetically FIRST must not steal the
    bare imdr_code already persisted to another ticker."""
    persisted = {
        "ACPMXVLY Index": "BBG.CPI.CORE.YOY.AU",
        "AUUIR Index": "BBG.CPI.CORE.YOY.AU.2",
    }
    series = [
        # 'AACORE' sorts before both existing tickers -> would grab the bare code
        # under naive per-batch assignment.
        ("AACORE Index", "AU", "Australia", "core_cpi_yoy", "Core CPI new", "Monthly", None, None, "%"),
        ("ACPMXVLY Index", "AU", "Australia", "core_cpi_yoy", "Core CPI m", "Monthly", None, None, "% CHANGE"),
        ("AUUIR Index", "AU", "Australia", "core_cpi_yoy", "Core CPI q", "Quarterly", None, None, "%"),
    ]
    obs = [(s[0], "2026-07-29", 3.0, None) for s in series]
    inds, _ = fetch_econdashboard(
        "AU", sqlite_path=_make_db(tmp_path, series, obs), existing_codes=persisted
    )
    codes = _codes(inds)
    # persisted codes unchanged; the new ticker takes the next free suffix
    assert codes["ACPMXVLY Index"] == "BBG.CPI.CORE.YOY.AU"
    assert codes["AUUIR Index"] == "BBG.CPI.CORE.YOY.AU.2"
    assert codes["AACORE Index"] == "BBG.CPI.CORE.YOY.AU.3"


def test_since_until_bound_observations(tmp_path) -> None:
    series = [
        ("AUCPIYOY Index", "AU", "Australia", "cpi_yoy", "CPI YoY", "Monthly", None, None, "% CHANGE"),
    ]
    obs = [
        ("AUCPIYOY Index", "2021-01-31", 1.0, None),
        ("AUCPIYOY Index", "2024-06-30", 3.0, None),
        ("AUCPIYOY Index", "2026-07-29", 3.2, None),
    ]
    _, observations = fetch_econdashboard(
        "AU", since="2024-01-01", until="2026-01-01", sqlite_path=_make_db(tmp_path, series, obs)
    )
    dates = sorted(str(o.obs_date) for o in observations)
    assert dates == ["2024-06-30"]
