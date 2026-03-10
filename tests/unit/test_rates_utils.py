"""Tests for domains/rates/utils.py — x-axis parsing, date formatters."""

from datetime import datetime, timezone

import pytest

from imdr.domains.rates.utils import hhmm, parse_iso_utc, parse_x_to_ts_utc, yyyymmdd


class TestParseXToTsUtc:
    def test_daily_8_digits(self):
        ts = parse_x_to_ts_utc(20170108)
        assert ts.strftime("%Y-%m-%d") == "2017-01-08"
        assert ts.tzinfo is not None

    def test_hourly_10_digits(self):
        ts = parse_x_to_ts_utc(2017010812)
        assert ts.strftime("%Y-%m-%d %H") == "2017-01-08 12"

    def test_minutely_12_digits(self):
        ts = parse_x_to_ts_utc(201701081230)
        assert ts.strftime("%H:%M") == "12:30"

    def test_monthly_6_digits(self):
        ts = parse_x_to_ts_utc(202401)
        assert ts.month == 1
        assert ts.year == 2024
        assert ts.day == 1

    def test_ten_minutely_11_digits(self):
        ts = parse_x_to_ts_utc(20240115143)
        assert ts.minute == 30
        assert ts.hour == 14

    def test_ten_minutely_zero(self):
        ts = parse_x_to_ts_utc(20240115140)
        assert ts.minute == 0
        assert ts.hour == 14

    def test_all_have_utc(self):
        for x in [202401, 20240115, 2024011514, 20240115143, 202401151430]:
            ts = parse_x_to_ts_utc(x)
            assert ts.tzinfo is not None

    def test_invalid_length_raises(self):
        with pytest.raises(ValueError, match="Unrecognized"):
            parse_x_to_ts_utc(12345)

    def test_invalid_length_too_long_raises(self):
        with pytest.raises(ValueError, match="Unrecognized"):
            parse_x_to_ts_utc(1234567890123)


class TestDateFormatters:
    def test_yyyymmdd(self):
        dt = datetime(2024, 3, 15, 10, 30, tzinfo=timezone.utc)
        assert yyyymmdd(dt) == 20240315

    def test_hhmm(self):
        dt = datetime(2024, 3, 15, 10, 30, tzinfo=timezone.utc)
        assert hhmm(dt) == 1030

    def test_hhmm_midnight(self):
        dt = datetime(2024, 3, 15, 0, 0, tzinfo=timezone.utc)
        assert hhmm(dt) == 0


class TestParseIsoUtc:
    def test_z_suffix(self):
        ts = parse_iso_utc("2024-01-15T12:00:00Z")
        assert ts.year == 2024
        assert ts.hour == 12
        assert ts.tzinfo is not None

    def test_offset(self):
        ts = parse_iso_utc("2024-01-15T12:00:00+00:00")
        assert ts.hour == 12

    def test_no_tz_assumes_utc(self):
        ts = parse_iso_utc("2024-01-15T12:00:00")
        assert ts.tzinfo is not None

    def test_space_separator(self):
        ts = parse_iso_utc("2024-01-15 12:00:00Z")
        assert ts.hour == 12
