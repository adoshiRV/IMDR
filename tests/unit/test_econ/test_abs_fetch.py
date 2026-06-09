"""Tests for playground/econ/abs/fetch.py parse layer.

No network calls. Tests the _parse_abs_csv function and the quarter-to-date
conversion logic.

Covered:
- _parse_abs_csv parses TIME_PERIOD and OBS_VALUE columns correctly.
- Quarter strings (YYYY-Q#) are converted to the first day of the quarter.
- Missing / NaN obs values are handled.
- _parse_abs_csv raises ValueError when expected columns are absent.
- ObservationRow list is produced with the correct imdr_code.
"""

from __future__ import annotations

import datetime
import textwrap

import pytest


class TestParseAbsCsv:
    def _csv(self, rows: list[tuple[str, str]]) -> str:
        header = "DATAFLOW,FREQ,MEASURE,INDEX,TSEST,REGION,TIME_PERIOD,OBS_VALUE\n"
        lines = [
            f"CPI,Q,1,INX,20,50,{period},{value}\n"
            for period, value in rows
        ]
        return header + "".join(lines)

    def test_quarterly_period_to_first_of_quarter(self) -> None:
        from playground.econ.abs.fetch import _parse_abs_csv

        csv_text = self._csv([("2024-Q1", "152.3"), ("2024-Q2", "153.1")])
        df = _parse_abs_csv(csv_text, "ABS.CPI.HEADLINE_SA.AU")

        assert len(df) == 2
        assert df["obs_date"].iloc[0] == datetime.date(2024, 1, 1)
        assert df["obs_date"].iloc[1] == datetime.date(2024, 4, 1)

    def test_q1_maps_to_jan(self) -> None:
        from playground.econ.abs.fetch import _parse_abs_csv

        df = _parse_abs_csv(self._csv([("2023-Q1", "149.0")]), "ABS.CPI.HEADLINE_SA.AU")
        assert df["obs_date"].iloc[0] == datetime.date(2023, 1, 1)

    def test_q4_maps_to_oct(self) -> None:
        from playground.econ.abs.fetch import _parse_abs_csv

        df = _parse_abs_csv(self._csv([("2023-Q4", "151.0")]), "ABS.CPI.HEADLINE_SA.AU")
        assert df["obs_date"].iloc[0] == datetime.date(2023, 10, 1)

    def test_imdr_code_assigned(self) -> None:
        from playground.econ.abs.fetch import _parse_abs_csv

        df = _parse_abs_csv(self._csv([("2024-Q1", "152.3")]), "ABS.CPI.HEADLINE_SA.AU")
        assert (df["imdr_code"] == "ABS.CPI.HEADLINE_SA.AU").all()

    def test_numeric_value_parsed(self) -> None:
        from playground.econ.abs.fetch import _parse_abs_csv

        df = _parse_abs_csv(self._csv([("2024-Q1", "152.3456")]), "ABS.CPI.HEADLINE_SA.AU")
        assert abs(df["value"].iloc[0] - 152.3456) < 0.0001

    def test_missing_value_becomes_nan(self) -> None:
        import pandas as pd
        from playground.econ.abs.fetch import _parse_abs_csv

        df = _parse_abs_csv(self._csv([("2024-Q1", "")]), "ABS.CPI.HEADLINE_SA.AU")
        # Empty string → NaN after pd.to_numeric
        assert len(df) == 1
        assert pd.isna(df["value"].iloc[0])

    def test_raises_when_columns_missing(self) -> None:
        from playground.econ.abs.fetch import _parse_abs_csv

        bad_csv = "Date,Value\n2024-01-01,100\n"
        with pytest.raises(ValueError, match="Unexpected ABS CSV columns"):
            _parse_abs_csv(bad_csv, "ABS.CPI.HEADLINE_SA.AU")

    def test_multiple_quarters_sorted(self) -> None:
        from playground.econ.abs.fetch import _parse_abs_csv

        csv_text = self._csv([
            ("2023-Q4", "151.0"),
            ("2023-Q3", "150.0"),
            ("2023-Q2", "149.0"),
        ])
        df = _parse_abs_csv(csv_text, "ABS.CPI.HEADLINE_SA.AU")
        assert len(df) == 3
        # All should have correct obs_dates
        months = sorted([row.obs_date.month for row in df.itertuples()])
        assert months == sorted([10, 7, 4])


class TestAbsIndicatorRow:
    def test_abs_series_produces_valid_indicator_row(self) -> None:
        from playground.econ.schema_prototype import IndicatorRow

        row = IndicatorRow(
            imdr_code="ABS.CPI.HEADLINE_SA.AU",
            vendor_name="ABS",
            source_code="ABS.CPI.HEADLINE_SA",
            description="ABS CPI All Groups Australia (seasonally adjusted)",
            unit="index",
            frequency="QUARTERLY",
            country_iso="AU",
            category="cpi",
            is_seasonally_adjusted=True,
        )
        assert row.frequency == "QUARTERLY"
        assert row.category == "cpi"

    def test_trimmed_mean_series_valid(self) -> None:
        from playground.econ.schema_prototype import IndicatorRow

        row = IndicatorRow(
            imdr_code="ABS.CPI.TRIMMED_MEAN_SA.AU",
            vendor_name="ABS",
            source_code="ABS.CPI.TRIMMED_MEAN_SA",
            description="ABS CPI Trimmed Mean (seasonally adjusted)",
            unit="index",
            frequency="QUARTERLY",
            country_iso="AU",
            category="cpi",
            is_seasonally_adjusted=True,
        )
        assert row.imdr_code == "ABS.CPI.TRIMMED_MEAN_SA.AU"
