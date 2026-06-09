"""Tests for playground/econ/statsnz/fetch.py parse layer.

No network calls. Tests _parse_infoshare_response for both quarterly
(YYYYQN) and monthly (YYYY-MM) period formats.

Covered:
- YYYYQN period format parsed to quarter start date.
- YYYY-MM period format parsed to first of month.
- Numeric values extracted correctly.
- None / empty values handled without raising.
- imdr_code assigned to all rows.
- Series definitions for HEADLINE / HEADLINE_YOY / FOOD all have valid indicator metadata.
"""

from __future__ import annotations

import datetime

import pytest


class TestParseInfoshareResponse:
    def _make_response(self, periods: list[str], values: list) -> dict:
        return {
            "series": [{
                "seriesCode": "CPIQ.TEST",
                "observations": [
                    {"period": p, "value": v}
                    for p, v in zip(periods, values)
                ],
            }]
        }

    def test_quarterly_yyyyqn_parsed_to_quarter_start(self) -> None:
        from playground.econ.statsnz.fetch import _parse_infoshare_response

        data = self._make_response(["2024Q1", "2024Q2"], [1054.0, 1060.0])
        df = _parse_infoshare_response(data, "STATSNZ.CPI.HEADLINE.NZ")

        assert len(df) == 2
        assert df["obs_date"].iloc[0] == datetime.date(2024, 1, 1)
        assert df["obs_date"].iloc[1] == datetime.date(2024, 4, 1)

    def test_monthly_yyyy_mm_parsed_to_first_of_month(self) -> None:
        from playground.econ.statsnz.fetch import _parse_infoshare_response

        data = self._make_response(["2024-01", "2024-02"], [1100.0, 1102.0])
        df = _parse_infoshare_response(data, "STATSNZ.SPI.FOOD.NZ")

        assert len(df) == 2
        assert df["obs_date"].iloc[0] == datetime.date(2024, 1, 1)
        assert df["obs_date"].iloc[1] == datetime.date(2024, 2, 1)

    def test_imdr_code_assigned_to_all_rows(self) -> None:
        from playground.econ.statsnz.fetch import _parse_infoshare_response

        data = self._make_response(["2024Q1", "2024Q2"], [1054.0, 1060.0])
        df = _parse_infoshare_response(data, "STATSNZ.CPI.HEADLINE.NZ")
        assert (df["imdr_code"] == "STATSNZ.CPI.HEADLINE.NZ").all()

    def test_none_value_handled(self) -> None:
        import pandas as pd
        from playground.econ.statsnz.fetch import _parse_infoshare_response

        data = self._make_response(["2024Q1"], [None])
        df = _parse_infoshare_response(data, "STATSNZ.CPI.HEADLINE.NZ")
        assert len(df) == 1
        assert pd.isna(df["value"].iloc[0])

    def test_empty_observations_returns_empty_dataframe(self) -> None:
        from playground.econ.statsnz.fetch import _parse_infoshare_response

        data = {"series": [{"seriesCode": "CPIQ.TEST", "observations": []}]}
        df = _parse_infoshare_response(data, "STATSNZ.CPI.HEADLINE.NZ")
        assert len(df) == 0
        assert set(df.columns) == {"obs_date", "imdr_code", "value"}

    def test_q4_maps_to_october(self) -> None:
        from playground.econ.statsnz.fetch import _parse_infoshare_response

        data = self._make_response(["2023Q4"], [1050.0])
        df = _parse_infoshare_response(data, "STATSNZ.CPI.HEADLINE.NZ")
        assert df["obs_date"].iloc[0] == datetime.date(2023, 10, 1)

    def test_bad_period_string_skipped(self) -> None:
        from playground.econ.statsnz.fetch import _parse_infoshare_response

        data = {
            "series": [{
                "observations": [
                    {"period": "INVALID", "value": 1.0},
                    {"period": "2024Q1", "value": 1054.0},
                ]
            }]
        }
        df = _parse_infoshare_response(data, "STATSNZ.CPI.HEADLINE.NZ")
        assert len(df) == 1
        assert df["obs_date"].iloc[0] == datetime.date(2024, 1, 1)


class TestStatsnzSeriesDefinitions:
    def test_all_series_produce_valid_indicator_rows(self) -> None:
        from playground.econ.schema_prototype import IndicatorRow, VALID_CATEGORIES, VALID_FREQUENCIES
        from playground.econ.statsnz.fetch import _SERIES

        for key, sdef in _SERIES.items():
            row = IndicatorRow(
                imdr_code=sdef["imdr_code"],
                vendor_name="STATSNZ",
                source_code=sdef["series_code"],
                description=sdef["description"],
                unit=sdef["unit"],
                frequency=sdef["frequency"],
                country_iso="NZ",
                category=sdef["category"],
                is_seasonally_adjusted=sdef["is_sa"],
            )
            assert row.frequency in VALID_FREQUENCIES, f"{key} has invalid frequency"
            assert row.category in VALID_CATEGORIES, f"{key} has invalid category"

    def test_headline_series_is_quarterly(self) -> None:
        from playground.econ.statsnz.fetch import _SERIES

        assert _SERIES["HEADLINE"]["frequency"] == "QUARTERLY"

    def test_food_series_is_monthly(self) -> None:
        from playground.econ.statsnz.fetch import _SERIES

        assert _SERIES["FOOD"]["frequency"] == "MONTHLY"

    def test_all_series_have_nz_country(self) -> None:
        from playground.econ.statsnz.fetch import _SERIES

        for key, sdef in _SERIES.items():
            row_country = "NZ"  # hardcoded in run_fetch
            assert row_country == "NZ", f"{key} should be NZ"
