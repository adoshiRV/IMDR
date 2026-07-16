"""Unit tests for the shared RBA statistical-table parse layer
(imdr.domains.econ.rba_tables).

No network / no sample-file dependency: parse_rba_csv is driven off a tmp CSV
mimicking the RBA multi-row-header layout. Replaces the retired playground
test_rba_fetch.py (playground.econ.rba.fetch was promoted+split into per-topic
scripts/econ/au/rba/rba_*.py, all driven by this shared module).
"""

from __future__ import annotations

import datetime

import pytest

from imdr.domains.econ.rba_tables import (
    RBASeries,
    _parse_date,
    build_observations,
    parse_rba_csv,
)
from imdr.domains.econ.schema import VALID_CATEGORIES, VALID_FREQUENCIES


def _spec(**over) -> RBASeries:
    base = dict(
        table="f1",
        series_id="FIRMMCRTD",
        imdr_code="RBA.RATES.CASH_RATE_TARGET.AU",
        display_name="RBA Cash Rate Target",
        unit="pct",
        frequency="DAILY",
        category="rates",
    )
    base.update(over)
    return RBASeries(**base)


# RBA-style CSV: title row, some header rows, the 'Series ID' row, a blank row,
# then DD-MMM-YYYY data rows.
_RBA_CSV = """F1 INTEREST RATES AND YIELDS
Title,Cash Rate Target,BBSW 1m
Description,Cash rate,Bank bill
Frequency,Daily,Daily
Series ID,FIRMMCRTD,FIRMMBAB30D
,,
15-Mar-2024,4.35,4.40
16-Mar-2024,4.35,
17-Mar-2024,"1,234.50",4.41
not-a-date,9.99,9.99
"""


class TestSourceCodeAndPath:
    def test_source_code(self) -> None:
        assert _spec().source_code == "RBA.F1.FIRMMCRTD"

    def test_csv_path_name(self) -> None:
        assert _spec().csv_path.name == "f1-data.csv"


class TestParseDate:
    @pytest.mark.parametrize("s,expected", [
        ("15-Mar-2024", datetime.date(2024, 3, 15)),
        ("15 Mar 2024", datetime.date(2024, 3, 15)),
        ("2024-03-15", datetime.date(2024, 3, 15)),
        ("15/03/2024", datetime.date(2024, 3, 15)),
    ])
    def test_supported_formats(self, s: str, expected: datetime.date) -> None:
        assert _parse_date(s) == expected

    @pytest.mark.parametrize("s", ["", "   ", "not-a-date", "2024"])
    def test_bad_values_return_none(self, s: str) -> None:
        assert _parse_date(s) is None


class TestParseRbaCsv:
    def _write(self, tmp_path, text: str):
        p = tmp_path / "f1-data.csv"
        p.write_text(text, encoding="utf-8")
        return p

    def test_title_and_series_parsed(self, tmp_path) -> None:
        title, data = parse_rba_csv(self._write(tmp_path, _RBA_CSV))
        assert title == "F1 INTEREST RATES AND YIELDS"
        assert set(data) == {"FIRMMCRTD", "FIRMMBAB30D"}

    def test_values_and_dates(self, tmp_path) -> None:
        _, data = parse_rba_csv(self._write(tmp_path, _RBA_CSV))
        cash = dict(data["FIRMMCRTD"])
        assert cash[datetime.date(2024, 3, 15)] == 4.35
        # comma thousands stripped
        assert cash[datetime.date(2024, 3, 17)] == 1234.50
        # bad-date row is skipped entirely
        assert datetime.date(9999, 1, 1) not in cash

    def test_empty_cell_becomes_none(self, tmp_path) -> None:
        _, data = parse_rba_csv(self._write(tmp_path, _RBA_CSV))
        bbsw = dict(data["FIRMMBAB30D"])
        assert bbsw[datetime.date(2024, 3, 16)] is None

    def test_bad_date_row_not_included(self, tmp_path) -> None:
        _, data = parse_rba_csv(self._write(tmp_path, _RBA_CSV))
        # 3 valid data rows -> 3 points per series (the not-a-date row dropped)
        assert len(data["FIRMMCRTD"]) == 3

    def test_missing_series_id_header_raises(self, tmp_path) -> None:
        bad = "F1 TITLE\nTitle,x\n15-Mar-2024,1.0\n"
        with pytest.raises(ValueError, match="no 'Series ID' header"):
            parse_rba_csv(self._write(tmp_path, bad))

    def test_empty_file_raises(self, tmp_path) -> None:
        with pytest.raises(ValueError, match="empty file"):
            parse_rba_csv(self._write(tmp_path, ""))


class TestBuildObservations:
    _DATA = {
        "FIRMMCRTD": [
            (datetime.date(2024, 1, 15), 4.35),
            (datetime.date(2024, 2, 15), 4.35),
            (datetime.date(2024, 3, 15), None),
        ]
    }

    def test_indicator_fields(self) -> None:
        ind, _ = build_observations(self._DATA, _spec(), since=None, until=None)
        assert ind.vendor_name == "RBA"
        assert ind.country_iso == "AU"
        assert ind.source_code == "RBA.F1.FIRMMCRTD"

    def test_none_value_passthrough(self) -> None:
        _, obs = build_observations(self._DATA, _spec(), since=None, until=None)
        assert obs[-1].value is None

    def test_since_filter(self) -> None:
        _, obs = build_observations(
            self._DATA, _spec(), since=datetime.date(2024, 2, 1), until=None
        )
        assert {o.obs_date for o in obs} == {
            datetime.date(2024, 2, 15), datetime.date(2024, 3, 15)
        }

    def test_until_filter(self) -> None:
        _, obs = build_observations(
            self._DATA, _spec(), since=None, until=datetime.date(2024, 2, 1)
        )
        assert {o.obs_date for o in obs} == {datetime.date(2024, 1, 15)}

    def test_missing_series_id_yields_no_obs(self) -> None:
        _, obs = build_observations(self._DATA, _spec(series_id="NOPE"), since=None, until=None)
        assert obs == []


class TestSpecConfigs:
    """Validate a representative fetcher's spec list (rba_rates._SERIES)."""

    def test_rba_rates_specs_are_valid(self) -> None:
        from scripts.econ.au.rba import rba_rates

        specs = rba_rates._SERIES
        assert specs, "rba_rates._SERIES is empty"
        codes = [s.imdr_code for s in specs]
        assert len(codes) == len(set(codes)), "duplicate imdr_codes"
        for s in specs:
            assert s.category in VALID_CATEGORIES, f"{s.imdr_code}: bad category {s.category}"
            assert s.frequency in VALID_FREQUENCIES, f"{s.imdr_code}: bad frequency {s.frequency}"
            assert s.imdr_code.endswith(".AU")
            assert s.source_code.startswith("RBA.")
