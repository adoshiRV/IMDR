"""Unit tests for the shared ABS SDMX parse layer (imdr.domains.econ.abs_sdmx).

No network: the ABS CSV rows are supplied directly / via a fake client.
Replaces the retired playground test_abs_fetch.py (playground.econ.abs.fetch
was promoted+split into per-topic scripts/econ/au/abs/abs_*.py, all driven by
this shared module).
"""

from __future__ import annotations

import datetime

import pytest

from imdr.domains.econ.abs_sdmx import (
    SDMXSeries,
    csv_rows_to_observations,
    fetch_series,
    parse_sdmx_period,
)
from imdr.domains.econ.schema import VALID_CATEGORIES, VALID_FREQUENCIES


def _spec(**over) -> SDMXSeries:
    base = dict(
        dataflow="CPI",
        key="1.10001.10.50.Q",
        imdr_code="ABS.CPI.HEADLINE_NSA.AU",
        display_name="ABS CPI All Groups Australia (NSA, index)",
        unit="index",
        frequency="QUARTERLY",
        category="cpi",
    )
    base.update(over)
    return SDMXSeries(**base)


class TestSourceCode:
    def test_no_suffix(self) -> None:
        assert _spec().source_code == "ABS.CPI.1.10001.10.50.Q"

    def test_with_suffix(self) -> None:
        assert _spec(source_code_suffix="M").source_code == "ABS.CPI.1.10001.10.50.Q.M"


class TestParseSdmxPeriod:
    @pytest.mark.parametrize("period,expected", [
        ("2024-Q1", datetime.date(2024, 1, 1)),
        ("2024-Q4", datetime.date(2024, 10, 1)),
        ("2024-03", datetime.date(2024, 3, 1)),
        ("2024-03-15", datetime.date(2024, 3, 15)),
        ("2024", datetime.date(2024, 1, 1)),
    ])
    def test_valid_periods(self, period: str, expected: datetime.date) -> None:
        assert parse_sdmx_period(period) == expected

    @pytest.mark.parametrize("period", ["", "2024-Q5", "2024-Q0", "garbage", "abcd"])
    def test_bad_periods_return_none(self, period: str) -> None:
        assert parse_sdmx_period(period) is None


class TestCsvRowsToObservations:
    _HEADER = ["DATAFLOW", "TIME_PERIOD", "OBS_VALUE", "UNIT_MEASURE"]

    def test_valid_rows_parsed(self) -> None:
        rows = [
            self._HEADER,
            ["CPI", "2024-Q1", "137.4", "index"],
            ["CPI", "2024-Q2", "138.8", "index"],
        ]
        obs = csv_rows_to_observations(rows, "ABS.CPI.HEADLINE_NSA.AU")
        assert [o.obs_date for o in obs] == [datetime.date(2024, 1, 1), datetime.date(2024, 4, 1)]
        assert [o.value for o in obs] == [137.4, 138.8]
        assert all(o.imdr_code == "ABS.CPI.HEADLINE_NSA.AU" for o in obs)

    def test_empty_value_becomes_none(self) -> None:
        rows = [self._HEADER, ["CPI", "2024-Q1", "", "index"]]
        obs = csv_rows_to_observations(rows, "X")
        assert obs[0].value is None

    def test_non_numeric_value_becomes_none(self) -> None:
        rows = [self._HEADER, ["CPI", "2024-Q1", "n/a", "index"]]
        assert csv_rows_to_observations(rows, "X")[0].value is None

    def test_bad_period_row_skipped(self) -> None:
        rows = [
            self._HEADER,
            ["CPI", "not-a-period", "1.0", "index"],
            ["CPI", "2024-Q1", "2.0", "index"],
        ]
        obs = csv_rows_to_observations(rows, "X")
        assert len(obs) == 1
        assert obs[0].value == 2.0

    def test_header_only_returns_empty(self) -> None:
        assert csv_rows_to_observations([self._HEADER], "X") == []

    def test_missing_obs_value_column_raises(self) -> None:
        rows = [["DATAFLOW", "TIME_PERIOD"], ["CPI", "2024-Q1"]]
        with pytest.raises(ValueError, match="TIME_PERIOD or OBS_VALUE"):
            csv_rows_to_observations(rows, "X")


class TestFetchSeries:
    class _FakeClient:
        def __init__(self, rows: list[list[str]]) -> None:
            self._rows = rows
            self.calls: list[tuple] = []

        def fetch_series_csv(self, dataflow, key, since=None, until=None):
            self.calls.append((dataflow, key, since, until))
            return self._rows

    def test_builds_indicator_and_observations(self) -> None:
        rows = [
            ["DATAFLOW", "TIME_PERIOD", "OBS_VALUE"],
            ["CPI", "2024-Q1", "137.4"],
            ["CPI", "2024-Q2", "138.8"],
        ]
        client = self._FakeClient(rows)
        spec = _spec()
        ind, obs = fetch_series(client, spec, since="2024-01-01", until=None)

        assert ind.imdr_code == "ABS.CPI.HEADLINE_NSA.AU"
        assert ind.vendor_name == "ABS"
        assert ind.country_iso == "AU"
        assert ind.source_code == "ABS.CPI.1.10001.10.50.Q"
        assert len(obs) == 2
        # spec fields threaded through to the client call
        assert client.calls == [("CPI", "1.10001.10.50.Q", "2024-01-01", None)]


class TestBuildSeriesConfigs:
    """The per-topic fetchers are pure config over this module; validate a
    representative one (abs_cpi) produces well-formed, schema-valid specs."""

    def test_abs_cpi_specs_are_valid(self) -> None:
        from scripts.econ.au.abs import abs_cpi

        specs = abs_cpi._build_series()
        assert specs, "abs_cpi._build_series() returned no specs"
        codes = [s.imdr_code for s in specs]
        assert len(codes) == len(set(codes)), "duplicate imdr_codes"
        for s in specs:
            assert s.category in VALID_CATEGORIES, f"{s.imdr_code}: bad category {s.category}"
            assert s.frequency in VALID_FREQUENCIES, f"{s.imdr_code}: bad frequency {s.frequency}"
            assert s.imdr_code.endswith(".AU")
            assert s.source_code.startswith("ABS.")
