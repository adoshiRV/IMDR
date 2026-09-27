"""Unit tests for the Citi Velocity FX proprietary-index library (pure logic)."""

from __future__ import annotations

import datetime

import pytest

from imdr.domains.fx import citi_fx_indices as cfi
from scripts.fx.citi.fx_indices import _parse_obs_date


# ---------------------------------------------------------------------------
# parse_tag — per-product decomposition
# ---------------------------------------------------------------------------

def test_surprise_index_esi_with_sector():
    r = cfi.parse_tag("FX.SURPRISE_INDEX.ESI.CESI.DM.SI_USD.TOTAL")
    assert (r.product_code, r.series_family, r.index_type, r.series_group) == \
        ("SURPRISE_INDEX", "ESI", "CESI", "DM")
    assert r.region_code == "SI_USD" and r.sector_code == "TOTAL"
    assert r.region_currency_code == "USD" and r.component is None


def test_surprise_index_isi_no_sector():
    r = cfi.parse_tag("FX.SURPRISE_INDEX.ISI.SI_CISI.DM.SI_JPY")
    assert r.series_family == "ISI" and r.sector_code is None
    assert r.region_currency_code == "JPY"


def test_neer_basket_and_currency():
    r = cfi.parse_tag("FX.NEER_IDX.BROAD.AUD")
    assert r.product_code == "NEER_IDX"
    assert r.index_type == "BROAD"          # basket -> index_type
    assert r.region_code == "AUD" and r.region_currency_code == "AUD"
    assert r.series_family is None and r.sector_code is None


def test_reer_usd_basket():
    r = cfi.parse_tag("FX.REER_IDX.NBI_ASIA.USD")
    assert r.product_code == "REER_IDX" and r.index_type == "NBI_ASIA"
    assert r.region_currency_code == "USD"


def test_ctot_strips_prefix_for_currency():
    r = cfi.parse_tag("FX.CTOT.DM.CTOT_AUD")
    assert r.series_group == "DM"
    assert r.region_code == "CTOT_AUD"       # prefix retained in region_code
    assert r.region_currency_code == "AUD"   # ...but currency FK resolves cleanly


def test_mriciti_family_component_no_currency():
    r = cfi.parse_tag("FX.MRICITI.MRI_EMMRI.MRI_FXVOL")
    assert r.index_type == "MRI_EMMRI" and r.component == "MRI_FXVOL"
    assert r.region_code is None and r.region_currency_code is None


def test_citipain_bare_currency():
    r = cfi.parse_tag("FX.CITIPAIN.AUD")
    assert r.region_code == "AUD" and r.region_currency_code == "AUD"
    assert r.index_type is None


def test_crfi_type_only():
    r = cfi.parse_tag("FX.CRFI.G10_VALUE")
    assert r.index_type == "G10_VALUE"
    assert r.region_code is None and r.region_currency_code is None


def test_liquidity_pair_with_quote_leg():
    r = cfi.parse_tag("FX.LIQUIDITY_IDX.EUR.CHF.DENSITY.CITI")
    assert r.index_type == "DENSITY"
    assert r.region_code == "EUR" and r.component == "CHF"
    assert r.region_currency_code == "EUR"


def test_liquidity_block_region_no_currency():
    r = cfi.parse_tag("FX.LIQUIDITY_IDX.EM.DENSITY.CITI")
    assert r.region_code == "EM" and r.component is None
    assert r.region_currency_code is None    # EM is a block, not a currency


def test_parse_rejects_non_fx_and_deferred():
    with pytest.raises(ValueError):
        cfi.parse_tag("RATES.OIS.USD_SOFR.PAR.5Y")
    with pytest.raises(ValueError, match="Unsupported"):
        cfi.parse_tag("FX.SC_SCORECARD.FLOWPCT.BUDGET")   # Phase 2, not supported


def test_display_name_shapes():
    assert "[CESI]" in cfi.parse_tag("FX.SURPRISE_INDEX.ESI.CESI.DM.SI_USD.TOTAL").display_name
    neer = cfi.parse_tag("FX.NEER_IDX.BROAD.AUD").display_name
    assert "NEER" in neer and "[BROAD]" in neer and "AUD" in neer


# ---------------------------------------------------------------------------
# build_series — currency FK resolution against dim_currency
# ---------------------------------------------------------------------------

def test_build_series_resolves_only_known_currencies():
    tags = [
        "FX.NEER_IDX.BROAD.USD",         # USD tracked
        "FX.CTOT.EM.CTOT_UAH",           # UAH not tracked -> None
        "FX.SURPRISE_INDEX.ESI.CESI.DM.G10_HARD.TOTAL",  # aggregate block
        "FX.MRICITI.MRI_LTMRI.MRI_TL",   # no currency axis
    ]
    series = cfi.build_series(tags, currency_codes={"USD", "EUR"})
    by = {s.citi_tag: s for s in series}
    assert by[tags[0]].region_currency_code == "USD"
    assert by[tags[1]].region_currency_code is None
    assert by[tags[2]].region_currency_code is None
    assert by[tags[3]].region_currency_code is None


# ---------------------------------------------------------------------------
# classify_fact_action — vintage predicate (shared util)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("exists,incoming,current,expected", [
    (False, 1.0, None, "new"),
    (True, None, 5.0, "skip"),
    (True, 6.0, 5.0, "revision"),
    (True, 5.0, None, "revision"),
    (True, 5.0, 5.0, "skip"),
])
def test_classify_fact_action(exists, incoming, current, expected):
    assert cfi.classify_fact_action(exists, incoming, current) == expected


# ---------------------------------------------------------------------------
# _parse_obs_date
# ---------------------------------------------------------------------------

def test_parse_obs_date_daily():
    assert _parse_obs_date(20260729) == datetime.date(2026, 7, 29)
    assert _parse_obs_date("20050103") == datetime.date(2005, 1, 3)


@pytest.mark.parametrize("bad", [202607, 2026072900, "notadate", 20261332])
def test_parse_obs_date_rejects_bad(bad):
    assert _parse_obs_date(bad) is None
