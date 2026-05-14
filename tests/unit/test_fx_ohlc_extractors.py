"""Tests for FX OHLC pure helpers, bar builder, and PairCache.

Covers the no-I/O surface of `imdr.domains.fx.extractors_ohlc`:

- `_num` (private numeric coercion — tested via the public helpers that use it)
- `spot_bid_ask`, `spot_mid`, `fwd_points_bid_ask`
- `outright_bid_ask_from_points`, `outright_mid_from_outright_bid_ask`
- `build_bar_from_ticks` — happy path + every failure branch with exact
  `BarDiagnostic.reason` string assertions
- `PairCache` — round-trip save/load, expiry semantics, malformed file handling

The networked `BidFXExtractor` itself is not tested here; that requires an
HTTP mocking harness and belongs in an integration suite.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from imdr.domains.fx.extractors_ohlc import (
    BarDiagnostic,
    PairCache,
    build_bar_from_ticks,
    fwd_points_bid_ask,
    outright_bid_ask_from_points,
    outright_mid_from_outright_bid_ask,
    spot_bid_ask,
    spot_mid,
)

UTC = timezone.utc
TS = datetime(2026, 3, 9, 13, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# spot_bid_ask
# ---------------------------------------------------------------------------


class TestSpotBidAsk:
    def test_prefers_spot_specific_fields(self) -> None:
        tick = {"bid_spot": 1.085, "ask_spot": 1.086, "bid": 9.0, "ask": 9.1}
        assert spot_bid_ask(tick) == (1.085, 1.086)

    def test_falls_back_to_plain_bid_ask(self) -> None:
        tick = {"bid": 1.085, "ask": 1.086}
        assert spot_bid_ask(tick) == (1.085, 1.086)

    def test_missing_returns_none_pair(self) -> None:
        assert spot_bid_ask({}) == (None, None)

    def test_non_numeric_values_become_none(self) -> None:
        tick = {"bid_spot": "n/a", "ask_spot": "n/a"}
        assert spot_bid_ask(tick) == (None, None)

    def test_string_numerics_are_coerced(self) -> None:
        # _num accepts anything float() understands.
        tick = {"bid_spot": "1.085", "ask_spot": "1.086"}
        assert spot_bid_ask(tick) == (1.085, 1.086)


# ---------------------------------------------------------------------------
# spot_mid
# ---------------------------------------------------------------------------


class TestSpotMid:
    def test_average_of_bid_ask(self) -> None:
        assert spot_mid({"bid_spot": 1.0, "ask_spot": 1.2}) == 1.1

    def test_falls_back_to_mid_spot(self) -> None:
        # Only ask present → bid is None → average path skipped → mid_spot path used.
        assert spot_mid({"ask_spot": 1.2, "mid_spot": 1.15}) == 1.15

    def test_falls_back_to_plain_mid(self) -> None:
        assert spot_mid({"mid": 1.099}) == 1.099

    def test_all_missing_returns_none(self) -> None:
        assert spot_mid({}) is None


# ---------------------------------------------------------------------------
# fwd_points_bid_ask + outright math
# ---------------------------------------------------------------------------


class TestForwardPoints:
    def test_extracts_bid_ask(self) -> None:
        tick = {"bid_forward_points": 12.5, "ask_forward_points": 13.0}
        assert fwd_points_bid_ask(tick) == (12.5, 13.0)

    def test_missing_returns_none_pair(self) -> None:
        assert fwd_points_bid_ask({}) == (None, None)


class TestOutrightMath:
    def test_outright_from_points_is_simple_addition(self) -> None:
        # 1.0850 / 1.0860 + 12 / 13 fwd points → 1.0862 / 1.0873.
        assert outright_bid_ask_from_points(1.0850, 1.0860, 0.0012, 0.0013) == (
            pytest.approx(1.0862),
            pytest.approx(1.0873),
        )

    def test_outright_mid_is_average(self) -> None:
        assert outright_mid_from_outright_bid_ask(1.0862, 1.0873) == pytest.approx(
            1.08675,
        )


# ---------------------------------------------------------------------------
# build_bar_from_ticks
# ---------------------------------------------------------------------------


def _spot_tick(bid: float, ask: float) -> dict:
    return {"bid_spot": bid, "ask_spot": ask}


def _fwd_tick(spot_bid: float, spot_ask: float, fwd_bid: float, fwd_ask: float) -> dict:
    return {
        "bid_spot": spot_bid,
        "ask_spot": spot_ask,
        "bid_forward_points": fwd_bid,
        "ask_forward_points": fwd_ask,
    }


class TestBuildBarFromTicksSpot:
    def test_happy_path_builds_full_bar(self) -> None:
        ticks = [_spot_tick(1.080, 1.081), _spot_tick(1.085, 1.086), _spot_tick(1.083, 1.084)]
        bar, diag = build_bar_from_ticks(
            ticks=ticks,
            symbol_compact="EURUSD",
            series="SPOT",
            tenor="SPOT",
            deal_type="SPOT",
            pair_used="EURUSD",
            ts=TS,
        )

        assert diag.success is True
        assert diag.reason == ""
        assert bar is not None
        assert bar["ts"] == TS
        assert bar["symbol"] == "EURUSD"
        assert bar["series"] == "SPOT"
        # mids are (bid+ask)/2 = 1.0805, 1.0855, 1.0835
        assert bar["open_px"] == pytest.approx(1.0805)
        assert bar["close_px"] == pytest.approx(1.0835)
        assert bar["high_px"] == pytest.approx(1.0855)
        assert bar["low_px"] == pytest.approx(1.0805)
        assert bar["mid_px"] == bar["close_px"]  # quote mid = last mid
        assert bar["bid"] == 1.083  # last tick bid
        assert bar["ask"] == 1.084  # last tick ask
        assert bar["n_ticks"] == 3

    def test_no_mids_failure_reason_format(self) -> None:
        # Tick with all numeric fields stripped → mid + bid_ask both None.
        bar, diag = build_bar_from_ticks(
            ticks=[{}],
            symbol_compact="EURUSD",
            series="SPOT",
            tenor="SPOT",
            deal_type="SPOT",
            pair_used="EURUSD",
            ts=TS,
            min_ticks=1,
        )
        assert bar is None
        assert diag.success is False
        assert diag.reason == "no_mids (got 0, need 1)"

    def test_min_ticks_threshold_in_reason_message(self) -> None:
        # Two valid ticks but min_ticks=5 → reason quotes both numbers.
        ticks = [_spot_tick(1.0, 1.1), _spot_tick(1.05, 1.15)]
        bar, diag = build_bar_from_ticks(
            ticks=ticks,
            symbol_compact="EURUSD",
            series="SPOT",
            tenor="SPOT",
            deal_type="SPOT",
            pair_used="EURUSD",
            ts=TS,
            min_ticks=5,
        )
        assert bar is None
        assert diag.success is False
        assert diag.reason == "no_mids (got 2, need 5)"

    def test_incomplete_exec_quote_when_only_mid_present(self) -> None:
        # A tick that yields a mid (via plain `mid`) but no bid/ask pair —
        # mids list fills, but bids/asks stay empty → "incomplete_exec_quote".
        bar, diag = build_bar_from_ticks(
            ticks=[{"mid": 1.085}],
            symbol_compact="EURUSD",
            series="SPOT",
            tenor="SPOT",
            deal_type="SPOT",
            pair_used="EURUSD",
            ts=TS,
            min_ticks=1,
        )
        assert bar is None
        assert diag.success is False
        assert diag.reason == "incomplete_exec_quote (no bid/ask)"


class TestBuildBarFromTicksForward:
    def test_happy_path_combines_spot_and_fwd_points(self) -> None:
        ticks = [
            _fwd_tick(1.0850, 1.0860, 0.0012, 0.0013),
            _fwd_tick(1.0852, 1.0862, 0.0014, 0.0015),
        ]
        bar, diag = build_bar_from_ticks(
            ticks=ticks,
            symbol_compact="USDKRW",
            series="NDF_1M",
            tenor="1M",
            deal_type="NDF",
            pair_used="USDKRW",
            ts=TS,
        )

        assert diag.success is True
        assert bar is not None
        # First outright mid: (1.0862 + 1.0873) / 2 = 1.08675
        assert bar["open_px"] == pytest.approx(1.08675)
        assert bar["n_ticks"] == 2

    def test_drops_tick_when_spot_or_fwd_incomplete(self) -> None:
        # First tick valid; second missing fwd points → second is silently skipped.
        ticks = [
            _fwd_tick(1.0850, 1.0860, 0.0012, 0.0013),
            {"bid_spot": 1.0852, "ask_spot": 1.0862},  # no fwd points
        ]
        bar, diag = build_bar_from_ticks(
            ticks=ticks,
            symbol_compact="USDKRW",
            series="NDF_1M",
            tenor="1M",
            deal_type="NDF",
            pair_used="USDKRW",
            ts=TS,
        )

        assert diag.success is True
        assert bar is not None
        assert bar["n_ticks"] == 1  # second tick dropped


# ---------------------------------------------------------------------------
# PairCache
# ---------------------------------------------------------------------------


class TestPairCache:
    def test_unavailable_before_expiry(self) -> None:
        cache = PairCache()
        expiry = TS + timedelta(days=1)
        cache.mark_unavailable("EUR.USD:SPOT", expiry)

        assert cache.is_unavailable("EUR.USD:SPOT", TS) is True
        # After expiry → no longer unavailable, and the entry is purged.
        assert cache.is_unavailable("EUR.USD:SPOT", expiry + timedelta(seconds=1)) is False
        assert "EUR.USD:SPOT" not in cache.unavailable

    def test_unknown_pair_is_available(self) -> None:
        assert PairCache().is_unavailable("EUR.USD:SPOT", TS) is False

    def test_save_and_load_round_trip(self, tmp_path) -> None:
        path = tmp_path / "pair_cache.json"
        cache = PairCache(_path=path)
        cache.mark_unavailable("USD.KRW:NDF_1M", TS + timedelta(days=7))
        cache.save()

        loaded = PairCache.load(path)
        assert loaded.unavailable == {
            "USD.KRW:NDF_1M": (TS + timedelta(days=7)).isoformat(),
        }

    def test_save_creates_parent_directory(self, tmp_path) -> None:
        path = tmp_path / "deep" / "nested" / "pair_cache.json"
        cache = PairCache(_path=path)
        cache.mark_unavailable("X.Y:SPOT", TS + timedelta(days=1))
        cache.save()
        assert path.exists()

    def test_save_is_noop_when_path_is_none(self) -> None:
        # Should not raise. No file is created (we have nothing to assert on
        # the filesystem side — just confirm the call is safe).
        PairCache().save()

    def test_load_missing_file_returns_empty_cache(self, tmp_path) -> None:
        cache = PairCache.load(tmp_path / "does_not_exist.json")
        assert cache.unavailable == {}

    def test_load_malformed_file_returns_empty_cache(self, tmp_path) -> None:
        path = tmp_path / "broken.json"
        path.write_text("{not valid json", encoding="utf-8")
        # Malformed file → load logs warning + returns empty (does not raise).
        cache = PairCache.load(path)
        assert cache.unavailable == {}


# ---------------------------------------------------------------------------
# BarDiagnostic — defaults pin the success-by-default contract
# ---------------------------------------------------------------------------


class TestBarDiagnosticDefaults:
    def test_success_defaults_true_reason_blank(self) -> None:
        diag = BarDiagnostic(symbol="EURUSD", series="SPOT")
        assert diag.success is True
        assert diag.reason == ""
