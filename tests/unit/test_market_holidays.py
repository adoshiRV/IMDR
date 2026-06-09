"""Tests for the country-anchored calendar API.

These tests stub the DB-side caches in :mod:`imdr.market_calendar.holidays_db`
so they run without a live IMDR connection. Real DB integration is verified
manually via the migration's embedded checks and the steps in the rehaul plan.

Phase D Step 11 (2026-05-13): the legacy ``(market_code, d, segment=…)`` API,
the ``dim_market_calendar`` bridge cache, and the Python ``holidays`` library
fallback are all deleted. This file only covers the modern API.
"""

from __future__ import annotations

from datetime import date, datetime

import pytest

from imdr.market_calendar import calendar as cal_mod
from imdr.market_calendar import holidays_db


@pytest.fixture
def stub_db(monkeypatch):
    """Populate the holidays_db caches in-memory and prevent any real DB hits."""

    holidays = {
        # SIFMA US Govt Bond — Veterans Day closed
        ("GT", "BBG"): frozenset({
            date(2026, 1, 1),
            date(2026, 11, 11),
            date(2026, 12, 25),
        }),
        # NYSE — Veterans Day OPEN, but Christmas closed
        ("YO", "BBG"): frozenset({
            date(2026, 1, 1),
            date(2026, 12, 25),
        }),
        # Fed CB calendar
        ("FD", "BBG"): frozenset({
            date(2026, 1, 1),
            date(2026, 11, 11),
            date(2026, 12, 25),
        }),
        # TARGET2 — Labour Day, Christmas, Boxing Day
        ("TE", "BBG"): frozenset({
            date(2026, 1, 1),
            date(2026, 5, 1),
            date(2026, 12, 25),
            date(2026, 12, 26),
        }),
        # Disagreement fixture: BBG vs EXCHANGE_CALENDARS for the same calendar
        ("YO", "EXCHANGE_CALENDARS"): frozenset({
            date(2026, 1, 1),
            date(2026, 12, 25),
            date(2026, 7, 3),  # half-day; EC says yes, BBG says no
        }),
    }

    vendors_by_cal: dict[str, frozenset[str]] = {}
    for cal, vendor in holidays:
        vendors_by_cal.setdefault(cal, set()).add(vendor)
    vendors_by_cal = {k: frozenset(v) for k, v in vendors_by_cal.items()}

    monkeypatch.setattr(holidays_db, "_HOLIDAYS", holidays)
    monkeypatch.setattr(holidays_db, "_VENDORS_BY_CAL", vendors_by_cal)
    return holidays


# ── Vendor-priority resolution ───────────────────────────────────────

class TestResolveHolidaySet:
    def test_trusted_vendor_used_when_present(self, stub_db):
        hols = holidays_db.resolve_holiday_set("YO", trusted_vendor="BBG")
        assert date(2026, 12, 25) in hols
        assert date(2026, 7, 3) not in hols  # only EC has July 3

    def test_returns_none_when_trusted_vendor_has_no_rows(self, stub_db):
        # XE has no rows for any vendor → resolve returns None.
        assert holidays_db.resolve_holiday_set("XE", trusted_vendor="EXCHANGE_CALENDARS") is None

    def test_uses_priority_when_no_trusted(self, stub_db):
        hols = holidays_db.resolve_holiday_set("YO", trusted_vendor=None)
        # MANUAL not present, BBG is next in priority order — pick BBG's set.
        assert hols == stub_db[("YO", "BBG")]

    def test_unknown_calendar_returns_none(self, stub_db):
        assert holidays_db.resolve_holiday_set("ZZ", trusted_vendor="BBG") is None


# ── is_holiday_db ────────────────────────────────────────────────────

class TestIsHolidayDb:
    def test_holiday_hit(self, stub_db):
        assert holidays_db.is_holiday_db("GT", date(2026, 11, 11), trusted_vendor="BBG") is True

    def test_holiday_miss(self, stub_db):
        assert holidays_db.is_holiday_db("YO", date(2026, 11, 11), trusted_vendor="BBG") is False

    def test_no_coverage_returns_none(self, stub_db):
        # XE has no rows for any vendor → caller must raise CalendarDBError.
        assert holidays_db.is_holiday_db("XE", date(2026, 12, 25)) is None


# ── Reconciliation helper ────────────────────────────────────────────

class TestVendorDisagreements:
    def test_finds_july3_divergence(self, stub_db):
        rows = holidays_db.vendor_disagreements(
            "YO", date(2026, 1, 1), date(2026, 12, 31),
        )
        july3 = [r for r in rows if r.holiday_date == date(2026, 7, 3)]
        assert len(july3) == 1
        d = july3[0]
        assert "EXCHANGE_CALENDARS" in d.vendors_say_holiday
        assert "BBG" in d.vendors_say_trading

    def test_silent_agreement_not_returned(self, stub_db):
        # 2026-12-25 — both vendors agree it's a holiday → no disagreement.
        rows = holidays_db.vendor_disagreements(
            "YO", date(2026, 12, 24), date(2026, 12, 26),
        )
        assert all(r.holiday_date != date(2026, 12, 25) for r in rows)

    def test_single_vendor_returns_empty(self, stub_db):
        # GT has only BBG rows in the fixture — needs ≥2 vendors to disagree.
        assert holidays_db.vendor_disagreements(
            "GT", date(2026, 1, 1), date(2026, 12, 31),
        ) == []


# ── Weekend days (DB-backed, Phase D Step 1) ──────────────────────────


@pytest.fixture
def stub_weekend_cache(monkeypatch):
    """Pre-populate _WEEKEND_DAYS_BY_COUNTRY so tests don't hit the DB.

    Mirrors the dim_country.weekend_days values verified in the live DB
    (4 ME countries on [4,5]; standard Sat/Sun on [5,6]; pseudo-countries
    absent from the cache so they hit the default fallback).
    """
    cache = {
        "US": frozenset({5, 6}),
        "UK": frozenset({5, 6}),
        "JP": frozenset({5, 6}),
        "SA": frozenset({4, 5}),
        "IL": frozenset({4, 5}),
        "EG": frozenset({4, 5}),
        "BD": frozenset({4, 5}),
        # EU, WW, XX, RU intentionally absent — they fall back to _DEFAULT_WEEKEND.
    }
    monkeypatch.setattr(holidays_db, "_WEEKEND_DAYS_BY_COUNTRY", cache)
    monkeypatch.setattr(holidays_db, "_WEEKEND_FALLBACK_WARNED", set())
    return cache


class TestGetWeekendDays:
    def test_standard_country_sat_sun(self, stub_weekend_cache):
        assert holidays_db.get_weekend_days("US") == frozenset({5, 6})

    def test_middle_east_fri_sat(self, stub_weekend_cache):
        assert holidays_db.get_weekend_days("SA") == frozenset({4, 5})
        assert holidays_db.get_weekend_days("IL") == frozenset({4, 5})
        assert holidays_db.get_weekend_days("EG") == frozenset({4, 5})
        assert holidays_db.get_weekend_days("BD") == frozenset({4, 5})

    def test_pseudo_country_falls_back_to_default(self, stub_weekend_cache):
        """EU/WW/XX have NULL weekend_days and aren't seeded → default Sat/Sun."""
        assert holidays_db.get_weekend_days("EU") == holidays_db._DEFAULT_WEEKEND
        assert holidays_db.get_weekend_days("WW") == holidays_db._DEFAULT_WEEKEND
        assert holidays_db.get_weekend_days("XX") == holidays_db._DEFAULT_WEEKEND

    def test_unknown_country_falls_back_to_default(self, stub_weekend_cache):
        """A typo or unsupported code returns the default and warns once."""
        result = holidays_db.get_weekend_days("ZZZ")
        assert result == holidays_db._DEFAULT_WEEKEND

    def test_unknown_country_warns_once_per_code(self, stub_weekend_cache):
        """Repeated calls with the same unknown code don't spam logs."""
        holidays_db.get_weekend_days("ZZZ")
        holidays_db.get_weekend_days("ZZZ")
        holidays_db.get_weekend_days("ZZZ")
        assert "ZZZ" in holidays_db._WEEKEND_FALLBACK_WARNED
        # The dedupe set should only carry one entry per unique unknown code.
        assert sum(1 for c in holidays_db._WEEKEND_FALLBACK_WARNED if c == "ZZZ") == 1


class TestWeekendCacheRefresh:
    def test_refresh_clears_weekend_cache_and_dedupe_set(self, monkeypatch):
        """refresh() drops both the data cache and the warning dedupe set."""
        monkeypatch.setattr(
            holidays_db, "_WEEKEND_DAYS_BY_COUNTRY",
            {"US": frozenset({5, 6})},
        )
        monkeypatch.setattr(holidays_db, "_WEEKEND_FALLBACK_WARNED", {"FAKE"})
        # Also stub the other caches so refresh's full body doesn't trip the
        # downstream reload path.
        monkeypatch.setattr(holidays_db, "_HOLIDAYS", {})
        monkeypatch.setattr(holidays_db, "_VENDORS_BY_CAL", {})

        holidays_db.refresh()

        assert holidays_db._WEEKEND_DAYS_BY_COUNTRY is None
        assert holidays_db._WEEKEND_FALLBACK_WARNED == set()


class TestIsWeekendThroughDbCache:
    """End-to-end: cal_mod.is_weekend now reads from the DB-backed cache."""

    def test_us_saturday_via_cache(self, stub_weekend_cache):
        assert cal_mod.is_weekend("US", date(2026, 3, 21)) is True

    def test_israel_friday_via_cache(self, stub_weekend_cache):
        assert cal_mod.is_weekend("IL", date(2026, 3, 20)) is True

    def test_israel_sunday_via_cache(self, stub_weekend_cache):
        assert cal_mod.is_weekend("IL", date(2026, 3, 22)) is False

    def test_pseudo_eu_saturday_via_default(self, stub_weekend_cache):
        # EU not in cache → default {5,6} → Saturday is True.
        assert cal_mod.is_weekend("EU", date(2026, 3, 21)) is True


# ── Modern public API ────────────────────────────────────────────────


class TestIsHoliday:
    """``is_holiday(country_code, calendar_code, d)`` — explicit calendar."""

    def test_sifma_veterans_day_closed(self, stub_db, stub_weekend_cache):
        # GT is the SIFMA US Govt Bond calendar — closed Veterans Day.
        assert cal_mod.is_holiday("US", "GT", date(2026, 11, 11)) is True

    def test_nyse_veterans_day_open(self, stub_db, stub_weekend_cache):
        # YO is NYSE — open Veterans Day.
        assert cal_mod.is_holiday("US", "YO", date(2026, 11, 11)) is False

    def test_target2_labour_day_closed(self, stub_db, stub_weekend_cache):
        # TE is TARGET2 — closed Labour Day.
        assert cal_mod.is_holiday("EU", "TE", date(2026, 5, 1)) is True

    def test_unknown_calendar_raises_calendar_db_error(
        self, stub_db, stub_weekend_cache,
    ):
        """Hard gate: unknown calendar_code raises CalendarDBError (no fallback)."""
        with pytest.raises(cal_mod.CalendarDBError, match="ZZZ"):
            cal_mod.is_holiday("US", "ZZZ", date(2026, 7, 4))


class TestIsTradingDay:
    def test_rates_calendar_veterans_day(self, stub_db, stub_weekend_cache):
        assert cal_mod.is_trading_day("US", "GT", date(2026, 11, 11)) is False

    def test_nyse_veterans_day_open(self, stub_db, stub_weekend_cache):
        assert cal_mod.is_trading_day("US", "YO", date(2026, 11, 11)) is True

    def test_weekend_overrides_calendar(self, stub_db, stub_weekend_cache):
        # Saturday — false regardless of which calendar; weekend check
        # short-circuits before hitting the holiday lookup.
        sat = date(2026, 3, 21)
        assert cal_mod.is_trading_day("US", "GT", sat) is False
        assert cal_mod.is_trading_day("US", "YO", sat) is False


class TestLastTradingDay:
    def test_walks_back_over_weekend(self, stub_db, stub_weekend_cache):
        # Monday 2026-03-23. Last trading day = Friday 2026-03-20.
        result = cal_mod.last_trading_day("US", "YO", before=date(2026, 3, 23))
        assert result == date(2026, 3, 20)

    def test_walks_back_over_holiday(self, stub_db, stub_weekend_cache):
        # 2026-12-26 is Saturday; GT is closed 2026-12-25; 12-24 is Thursday.
        result = cal_mod.last_trading_day("US", "GT", before=date(2026, 12, 28))
        # Monday 12-28 → walk back: Sun (weekend), Sat (weekend), Fri 12-25 (holiday),
        # Thu 12-24 (trading day).
        assert result == date(2026, 12, 24)


class TestNextTradingDay:
    def test_walks_forward_over_weekend(self, stub_db, stub_weekend_cache):
        # Friday 2026-03-20. Next trading day = Monday 2026-03-23.
        result = cal_mod.next_trading_day("US", "YO", after=date(2026, 3, 20))
        assert result == date(2026, 3, 23)


class TestTradingDaysBetween:
    def test_inclusive_range_excludes_weekend(self, stub_db, stub_weekend_cache):
        # Mon-Fri = 5 trading days.
        days = cal_mod.trading_days_between(
            "US", "YO", date(2026, 3, 16), date(2026, 3, 20),
        )
        assert len(days) == 5
        assert days[0] == date(2026, 3, 16)
        assert days[-1] == date(2026, 3, 20)


class TestLastBusinessDay:
    def test_returns_datetime(self, stub_db, stub_weekend_cache):
        result = cal_mod.last_business_day("US", "YO")
        assert isinstance(result, datetime)
        assert result.tzinfo is not None
