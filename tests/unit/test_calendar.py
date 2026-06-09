"""Tests for the global trading calendar module."""

from __future__ import annotations

from datetime import date, datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from imdr.market_calendar.calendar import (
    is_holiday,
    is_market_open,
    is_trading_day,
    is_weekend,
    last_business_day,
    last_trading_day,
    next_trading_day,
    trading_days_between,
)
from imdr.market_calendar.holidays import is_settlement_holiday, isda_holidays
from imdr.market_calendar.imm import (
    imm_date,
    imm_dates_monthly,
    imm_dates_quarterly,
    is_imm_date,
    is_quarterly_imm_date,
    next_imm_date,
)

# Phase D Step 11: tests use the modern (country_code, calendar_code, …) API
# exclusively. The IL placeholder below survives because the one IL test that
# uses it (``test_israel_friday_not_trading``) hits the weekend short-circuit
# before the holiday lookup — so the unknown calendar_code never reaches the
# DB query. If a future test needs to assert IL behaviour on a non-weekend
# date it must first seed an IL calendar in ``calendar.dim_calendar``;
# otherwise the call raises ``CalendarDBError``.
_IL_PLACEHOLDER_CALENDAR = "IL"   # no row in calendar.dim_calendar


# ── Weekend tests (no calendar arg needed) ─────────────────────────

class TestIsWeekend:
    def test_us_saturday(self):
        assert is_weekend("US", date(2026, 3, 21)) is True

    def test_us_sunday(self):
        assert is_weekend("US", date(2026, 3, 22)) is True

    def test_us_monday(self):
        assert is_weekend("US", date(2026, 3, 23)) is False

    def test_israel_friday(self):
        """Israel has Fri/Sat weekend."""
        assert is_weekend("IL", date(2026, 3, 20)) is True  # Friday

    def test_israel_saturday(self):
        assert is_weekend("IL", date(2026, 3, 21)) is True

    def test_israel_sunday(self):
        """Sunday is a working day in Israel."""
        assert is_weekend("IL", date(2026, 3, 22)) is False

    def test_saudi_friday(self):
        """Saudi Arabia has Fri/Sat weekend."""
        assert is_weekend("SA", date(2026, 3, 20)) is True

    def test_egypt_friday(self):
        """Egypt has Fri/Sat weekend."""
        assert is_weekend("EG", date(2026, 3, 20)) is True

    def test_bangladesh_friday(self):
        """Bangladesh has Fri/Sat weekend."""
        assert is_weekend("BD", date(2026, 3, 20)) is True


# ── Holiday tests ──────────────────────────────────────────────────

class TestIsHoliday:
    def test_us_new_years(self):
        assert is_holiday("US", "GT", date(2026, 1, 1)) is True

    def test_us_regular_day(self):
        assert is_holiday("US", "GT", date(2026, 3, 23)) is False

    def test_eu_target2_new_years(self):
        assert is_holiday("EU", "TE", date(2026, 1, 1)) is True

    def test_eu_target2_christmas(self):
        assert is_holiday("EU", "TE", date(2026, 12, 25)) is True

    def test_jp_holiday(self):
        # Jan 1 is a public holiday in Japan
        assert is_holiday("JP", "JN", date(2026, 1, 1)) is True


# ── Trading day tests ──────────────────────────────────────────────

class TestIsTradingDay:
    def test_regular_monday(self):
        assert is_trading_day("US", "GT", date(2026, 3, 23)) is True

    def test_saturday(self):
        assert is_trading_day("US", "GT", date(2026, 3, 21)) is False

    def test_us_holiday(self):
        assert is_trading_day("US", "GT", date(2026, 1, 1)) is False

    def test_israel_friday_not_trading(self):
        """Friday is not a trading day in Israel.

        Weekend check short-circuits before the holiday lookup, so we get
        the right answer even though IL has no calendar in the DB. The
        complementary "Sunday is a trading day" assertion was removed in
        Phase D Step 10 — it would have to hit the holiday lookup, which
        now raises ``CalendarDBError`` for unknown calendars. Sunday
        weekend semantics are still tested in
        ``TestIsWeekend::test_israel_sunday``.
        """
        assert is_trading_day("IL", _IL_PLACEHOLDER_CALENDAR, date(2026, 3, 20)) is False


# ── Market open tests ─────────────────────────────────────────────

class TestIsMarketOpen:
    def test_us_during_trading_hours(self):
        # 14:00 UTC = 10:00 ET (within 09:30-16:00)
        dt = datetime(2026, 3, 23, 14, 0, tzinfo=ZoneInfo("UTC"))
        assert is_market_open("US", "GT", dt) is True

    def test_us_after_close(self):
        # 22:00 UTC = 18:00 ET (after 16:00 close)
        dt = datetime(2026, 3, 23, 22, 0, tzinfo=ZoneInfo("UTC"))
        assert is_market_open("US", "GT", dt) is False

    def test_us_before_open(self):
        # 12:00 UTC = 08:00 ET (before 09:30 open)
        dt = datetime(2026, 3, 23, 12, 0, tzinfo=ZoneInfo("UTC"))
        assert is_market_open("US", "GT", dt) is False

    def test_jp_during_lunch_break(self):
        # 03:00 UTC = 12:00 JST (within 11:30-12:30 lunch)
        dt = datetime(2026, 3, 23, 3, 0, tzinfo=ZoneInfo("UTC"))
        assert is_market_open("JP", "JN", dt) is False

    def test_jp_during_morning_session(self):
        # 01:00 UTC = 10:00 JST (within 09:00-11:30)
        dt = datetime(2026, 3, 23, 1, 0, tzinfo=ZoneInfo("UTC"))
        assert is_market_open("JP", "JN", dt) is True

    def test_jp_during_afternoon_session(self):
        # 04:00 UTC = 13:00 JST (within 12:30-15:30)
        dt = datetime(2026, 3, 23, 4, 0, tzinfo=ZoneInfo("UTC"))
        assert is_market_open("JP", "JN", dt) is True

    def test_weekend_not_open(self):
        # Saturday
        dt = datetime(2026, 3, 21, 14, 0, tzinfo=ZoneInfo("UTC"))
        assert is_market_open("US", "GT", dt) is False

    def test_holiday_not_open(self):
        # Jan 1 US holiday
        dt = datetime(2026, 1, 1, 14, 0, tzinfo=ZoneInfo("UTC"))
        assert is_market_open("US", "GT", dt) is False


# ── Last/next trading day tests ───────────────────────────────────

class TestLastTradingDay:
    def test_skips_weekend(self):
        # Monday -> previous Friday
        result = last_trading_day("US", "GT", before=date(2026, 3, 23))
        assert result == date(2026, 3, 20)  # Friday

    def test_skips_holiday(self):
        # Day after New Year's
        result = last_trading_day("US", "GT", before=date(2026, 1, 2))
        assert result == date(2025, 12, 31)

    def test_skips_weekend_and_holiday(self):
        # After a holiday weekend
        result = last_trading_day("US", "GT", before=date(2026, 7, 6))
        # Jul 3 is observed Independence Day (Friday), Jul 4/5 weekend
        assert result == date(2026, 7, 2)


class TestNextTradingDay:
    def test_skips_weekend(self):
        # Friday -> Monday
        result = next_trading_day("US", "GT", after=date(2026, 3, 20))
        assert result == date(2026, 3, 23)

    def test_skips_holiday(self):
        # Dec 31 -> Jan 2 (Jan 1 is holiday)
        result = next_trading_day("US", "GT", after=date(2025, 12, 31))
        assert result == date(2026, 1, 2)


class TestTradingDaysBetween:
    def test_full_week(self):
        # Mon-Fri = 5 trading days
        days = trading_days_between("US", "GT", date(2026, 3, 16), date(2026, 3, 20))
        assert len(days) == 5

    def test_includes_boundaries(self):
        days = trading_days_between("US", "GT", date(2026, 3, 23), date(2026, 3, 23))
        assert len(days) == 1
        assert days[0] == date(2026, 3, 23)

    def test_weekend_excluded(self):
        # Sat-Sun
        days = trading_days_between("US", "GT", date(2026, 3, 21), date(2026, 3, 22))
        assert len(days) == 0


class TestLastBusinessDay:
    def test_returns_datetime(self):
        result = last_business_day("US", "GT")
        assert isinstance(result, datetime)
        assert result.tzinfo is not None

    def test_not_weekend(self):
        result = last_business_day("US", "GT")
        assert result.weekday() < 5

    def test_returns_today_when_market_closed(self):
        """After US market close, last_business_day should return today."""
        # Tuesday 2026-03-31 at 8pm ET (after 4pm close)
        fake_now = datetime(2026, 3, 31, 20, 0, tzinfo=ZoneInfo("America/New_York"))
        with patch("imdr.market_calendar.calendar.datetime") as mock_dt:
            mock_dt.now.return_value = fake_now
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            result = last_business_day("US", "GT")
        assert result.date() == date(2026, 3, 31)

    def test_returns_previous_day_before_market_close(self):
        """Before US market close, last_business_day should return previous trading day."""
        # Tuesday 2026-03-31 at 2pm ET (before 4pm close)
        fake_now = datetime(2026, 3, 31, 14, 0, tzinfo=ZoneInfo("America/New_York"))
        with patch("imdr.market_calendar.calendar.datetime") as mock_dt:
            mock_dt.now.return_value = fake_now
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            result = last_business_day("US", "GT")
        assert result.date() == date(2026, 3, 30)

    def test_returns_friday_on_weekend(self):
        """On a Saturday, last_business_day should return Friday."""
        fake_now = datetime(2026, 3, 28, 10, 0, tzinfo=ZoneInfo("America/New_York"))
        with patch("imdr.market_calendar.calendar.datetime") as mock_dt:
            mock_dt.now.return_value = fake_now
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            result = last_business_day("US", "GT")
        assert result.date() == date(2026, 3, 27)  # Friday


# ── IMM date tests ────────────────────────────────────────────────

class TestIMMDates:
    def test_imm_date_is_wednesday(self):
        d = imm_date(2026, 3)
        assert d.weekday() == 2  # Wednesday

    def test_imm_date_is_third_week(self):
        d = imm_date(2026, 3)
        assert 15 <= d.day <= 21

    def test_imm_date_march_2026(self):
        assert imm_date(2026, 3) == date(2026, 3, 18)

    def test_imm_dates_monthly_count(self):
        assert len(imm_dates_monthly(2026)) == 12

    def test_imm_dates_quarterly_count(self):
        assert len(imm_dates_quarterly(2026)) == 4

    def test_imm_dates_quarterly_months(self):
        dates = imm_dates_quarterly(2026)
        assert [d.month for d in dates] == [3, 6, 9, 12]

    def test_all_monthly_are_wednesdays(self):
        for d in imm_dates_monthly(2026):
            assert d.weekday() == 2

    def test_is_imm_date_true(self):
        assert is_imm_date(date(2026, 3, 18)) is True

    def test_is_imm_date_false(self):
        assert is_imm_date(date(2026, 3, 19)) is False

    def test_is_quarterly_imm_date_true(self):
        assert is_quarterly_imm_date(date(2026, 3, 18)) is True

    def test_is_quarterly_imm_date_false_monthly(self):
        # January IMM is monthly, not quarterly
        assert is_quarterly_imm_date(date(2026, 1, 21)) is False

    def test_next_imm_date(self):
        result = next_imm_date(after=date(2026, 3, 18))
        assert result == date(2026, 4, 15)

    def test_next_quarterly_imm_date(self):
        result = next_imm_date(after=date(2026, 3, 18), quarterly_only=True)
        assert result == date(2026, 6, 17)

    def test_next_imm_same_month(self):
        # Before the IMM date in the same month
        result = next_imm_date(after=date(2026, 3, 1))
        assert result == date(2026, 3, 18)


# ── ISDA tests ────────────────────────────────────────────────────

class TestISDA:
    def test_nyse_holidays_not_empty(self):
        hols = isda_holidays("NYSE", 2026)
        assert len(hols) > 0

    def test_ecb_holidays_not_empty(self):
        hols = isda_holidays("ECB", 2026)
        assert len(hols) > 0

    def test_unsupported_center_returns_empty(self):
        hols = isda_holidays("FAKE_CENTER", 2026)
        assert len(hols) == 0

    def test_us_settlement_holiday(self):
        # Independence Day observed (Jul 3, 2026 is Friday)
        assert is_settlement_holiday("US", date(2026, 7, 3)) is True

    def test_us_settlement_regular_day(self):
        assert is_settlement_holiday("US", date(2026, 3, 23)) is False

    def test_india_settlement_holiday(self):
        # Republic Day (Jan 26)
        assert is_settlement_holiday("IN", date(2026, 1, 26)) is True

    def test_market_without_isda_centers(self):
        # JP has no ISDA centers configured
        assert is_settlement_holiday("JP", date(2026, 1, 1)) is False


# ── Health check integration test ─────────────────────────────────

class TestShouldRelaxChecks:
    def test_relax_on_weekend(self):
        from imdr.healthchecks.quality import should_relax_checks
        assert should_relax_checks(date(2026, 3, 21), "US") is True  # Saturday

    def test_no_relax_on_trading_day(self):
        from imdr.healthchecks.quality import should_relax_checks
        assert should_relax_checks(date(2026, 3, 23), "US") is False  # Monday

    def test_relax_on_holiday(self):
        from imdr.healthchecks.quality import should_relax_checks
        assert should_relax_checks(date(2026, 1, 1), "US") is True  # New Year's
