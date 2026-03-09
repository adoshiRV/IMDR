"""Tests for FX Universe."""

from __future__ import annotations

from datetime import datetime, timezone

from imdr.universe.fx import get_fx_universe


def test_universe_loads():
    """Universe loads from YAML without errors."""
    u = get_fx_universe()
    assert len(u.g10) == 11
    assert "USD" in u.g10
    assert "EUR" in u.g10


def test_all_currencies():
    u = get_fx_universe()
    all_ccy = u.all_currencies
    assert "USD" in all_ccy
    assert "CNH" in all_ccy  # G10 (offshore yuan)
    assert "SGD" in all_ccy  # EM deliverable


def test_active_currencies_excludes_usd():
    u = get_fx_universe()
    active = u.active_currencies
    assert "USD" not in active
    assert "EUR" in active


def test_instruments_dotted():
    u = get_fx_universe()
    instruments = u.instruments()
    assert len(instruments) > 0
    assert all("." in p for p in instruments)
    assert "EUR.USD" in instruments


def test_api_symbols_compact():
    u = get_fx_universe()
    symbols = u.api_symbols()
    assert "EURUSD" in symbols
    assert all("." not in s for s in symbols)


def test_compact_dotted_roundtrip():
    u = get_fx_universe()
    assert u.compact_symbol("EUR.USD") == "EURUSD"
    assert u.dotted_symbol("EURUSD") == "EUR.USD"


def test_candidates_for():
    u = get_fx_universe()
    cands = u.candidates_for("EUR.USD")
    assert cands == ["EURUSD", "USDEUR"]


def test_classification_for():
    u = get_fx_universe()
    assert u.classification_for("USD") == "g10"
    assert u.classification_for("CNH") == "g10"
    assert u.classification_for("SGD") == "em_deliverable"


def test_provider_series_bidfx():
    u = get_fx_universe()
    series = u.provider_series("bidfx", "EUR")
    assert "SPOT" in series
    assert "FORWARD_1M" in series


def test_provider_series_em_ndf():
    u = get_fx_universe()
    series = u.provider_series("bidfx", "INR")
    assert "SPOT" in series
    assert "NDF_1M" in series


def test_is_fx_open_weekday():
    """Tuesday midday UTC should be open."""
    u = get_fx_universe()
    # 2026-03-10 is a Tuesday
    dt = datetime(2026, 3, 10, 12, 0, tzinfo=timezone.utc)
    assert u.is_fx_open(dt) is True


def test_is_fx_closed_saturday():
    """Saturday should be closed."""
    u = get_fx_universe()
    # 2026-03-14 is a Saturday
    dt = datetime(2026, 3, 14, 12, 0, tzinfo=timezone.utc)
    assert u.is_fx_open(dt) is False


def test_series_config():
    u = get_fx_universe()
    cfg = u.series_config("SPOT")
    assert cfg.tenor == "SPOT"
    assert cfg.deal_type == "SPOT"

    cfg = u.series_config("FORWARD_1M")
    assert cfg.tenor == "1M"
    assert cfg.deal_type == "FORWARD"
