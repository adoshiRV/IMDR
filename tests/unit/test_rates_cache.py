"""Tests for the CurveQuoteCache — status-aware empty combo caching."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from imdr.domains.rates.cache import (
    CurveQuoteCache,
    _ACTIVE_STALE_DAYS,
    _CEASED_STALE_DAYS,
    _PROTECTED_QUOTES,
)


@pytest.fixture
def cache(tmp_path: Path) -> CurveQuoteCache:
    """Fresh cache pointing at a temp directory."""
    c = CurveQuoteCache(tmp_path)
    return c


class TestProtectedQuotes:
    """par and ssw must never be cached for active/reformed curves."""

    def test_par_not_cached_for_active(self, cache: CurveQuoteCache) -> None:
        cache.mark_empty("USD", "SOFR", "par", curve_status="active")
        assert not cache.should_skip("USD", "SOFR", "par", curve_status="active")

    def test_ssw_not_cached_for_active(self, cache: CurveQuoteCache) -> None:
        cache.mark_empty("EUR", "EUROSTR", "ssw", curve_status="active")
        assert not cache.should_skip("EUR", "EUROSTR", "ssw", curve_status="active")

    def test_par_not_cached_for_reformed(self, cache: CurveQuoteCache) -> None:
        cache.mark_empty("INR", "MIFOR", "par", curve_status="reformed")
        assert not cache.should_skip("INR", "MIFOR", "par", curve_status="reformed")

    def test_par_cached_for_ceased(self, cache: CurveQuoteCache) -> None:
        cache.mark_empty("USD", "LIBOR", "par", curve_status="ceased")
        assert cache.should_skip("USD", "LIBOR", "par", curve_status="ceased")

    def test_ssw_cached_for_ceased(self, cache: CurveQuoteCache) -> None:
        cache.mark_empty("GBP", "GBP_LIBOR", "ssw", curve_status="ceased")
        assert cache.should_skip("GBP", "GBP_LIBOR", "ssw", curve_status="ceased")

    def test_bfly_cached_for_active(self, cache: CurveQuoteCache) -> None:
        """Non-protected quotes (bfly, fwd, etc.) can be cached for any status."""
        cache.mark_empty("USD", "SOFR", "bfly", curve_status="active")
        assert cache.should_skip("USD", "SOFR", "bfly", curve_status="active")

    def test_protected_quotes_constant(self) -> None:
        assert "par" in _PROTECTED_QUOTES
        assert "ssw" in _PROTECTED_QUOTES


class TestStaleDays:
    """Active curves: 2-day window. Ceased curves: 30-day window."""

    def test_active_stale_days_constant(self) -> None:
        assert _ACTIVE_STALE_DAYS == 2

    def test_ceased_stale_days_constant(self) -> None:
        assert _CEASED_STALE_DAYS == 30

    def test_active_entry_expires_after_2_days(self, cache: CurveQuoteCache) -> None:
        two_days_ago = (date.today() - timedelta(days=2)).isoformat()
        cache._cache["USD|SOFR|bfly"] = two_days_ago
        assert not cache.should_skip("USD", "SOFR", "bfly", curve_status="active")

    def test_active_entry_fresh_within_2_days(self, cache: CurveQuoteCache) -> None:
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        cache._cache["USD|SOFR|bfly"] = yesterday
        assert cache.should_skip("USD", "SOFR", "bfly", curve_status="active")

    def test_ceased_entry_fresh_within_30_days(self, cache: CurveQuoteCache) -> None:
        fifteen_days_ago = (date.today() - timedelta(days=15)).isoformat()
        cache._cache["USD|LIBOR|par"] = fifteen_days_ago
        assert cache.should_skip("USD", "LIBOR", "par", curve_status="ceased")

    def test_ceased_entry_expires_after_30_days(self, cache: CurveQuoteCache) -> None:
        thirty_one_days_ago = (date.today() - timedelta(days=31)).isoformat()
        cache._cache["USD|LIBOR|par"] = thirty_one_days_ago
        assert not cache.should_skip("USD", "LIBOR", "par", curve_status="ceased")

    def test_override_stale_days(self, tmp_path: Path) -> None:
        """Legacy callers can override stale_days for backwards compat."""
        cache = CurveQuoteCache(tmp_path, stale_days=5)
        cache.mark_empty("USD", "SOFR", "bfly", curve_status="active")
        # With override=5, entry from today should be skipped
        assert cache.should_skip("USD", "SOFR", "bfly", curve_status="active")
        # But expired after 5 days
        five_days_ago = (date.today() - timedelta(days=5)).isoformat()
        cache._cache["USD|SOFR|bfly"] = five_days_ago
        assert not cache.should_skip("USD", "SOFR", "bfly", curve_status="active")


class TestMarkActive:
    def test_removes_entry(self, cache: CurveQuoteCache) -> None:
        cache._cache["USD|SOFR|bfly"] = date.today().isoformat()
        cache.mark_active("USD", "SOFR", "bfly")
        assert "USD|SOFR|bfly" not in cache._cache

    def test_noop_if_not_cached(self, cache: CurveQuoteCache) -> None:
        cache.mark_active("USD", "SOFR", "par")
        assert not cache._dirty


class TestClearCurve:
    def test_removes_all_quotes(self, cache: CurveQuoteCache) -> None:
        cache._cache["USD|SOFR|par"] = "2026-04-01"
        cache._cache["USD|SOFR|bfly"] = "2026-04-01"
        cache._cache["USD|SOFR|fwd"] = "2026-04-01"
        cache._cache["EUR|EUROSTR|par"] = "2026-04-01"
        removed = cache.clear_curve("USD", "SOFR")
        assert removed == 3
        assert "EUR|EUROSTR|par" in cache._cache

    def test_returns_zero_if_not_found(self, cache: CurveQuoteCache) -> None:
        assert cache.clear_curve("ZZZ", "FAKE") == 0


class TestClearAll:
    def test_empties_cache(self, cache: CurveQuoteCache) -> None:
        cache._cache["A|B|C"] = "2026-01-01"
        cache._cache["D|E|F"] = "2026-01-01"
        removed = cache.clear_all()
        assert removed == 2
        assert len(cache._cache) == 0

    def test_returns_zero_if_empty(self, cache: CurveQuoteCache) -> None:
        assert cache.clear_all() == 0


class TestPersistence:
    def test_save_and_load(self, tmp_path: Path) -> None:
        c1 = CurveQuoteCache(tmp_path)
        c1.mark_empty("USD", "LIBOR", "par", curve_status="ceased")
        c1.save()

        c2 = CurveQuoteCache(tmp_path)
        c2.load()
        assert c2.should_skip("USD", "LIBOR", "par", curve_status="ceased")

    def test_no_save_when_clean(self, tmp_path: Path) -> None:
        c = CurveQuoteCache(tmp_path)
        c.save()
        cache_path = tmp_path / "rates" / "empty_combos.json"
        assert not cache_path.exists()

    def test_creates_directory(self, tmp_path: Path) -> None:
        c = CurveQuoteCache(tmp_path / "nested" / "deep")
        c.mark_empty("X", "Y", "bfly", curve_status="active")
        c.save()
        assert (tmp_path / "nested" / "deep" / "rates" / "empty_combos.json").exists()


class TestDefaultStatus:
    """When no curve_status is passed, default to 'active' (safe default)."""

    def test_should_skip_defaults_active(self, cache: CurveQuoteCache) -> None:
        cache._cache["USD|SOFR|bfly"] = date.today().isoformat()
        # No curve_status → defaults to "active" → 2-day window
        assert cache.should_skip("USD", "SOFR", "bfly")

    def test_mark_empty_defaults_active(self, cache: CurveQuoteCache) -> None:
        # par + default active → should NOT be cached
        cache.mark_empty("USD", "SOFR", "par")
        assert "USD|SOFR|par" not in cache._cache
