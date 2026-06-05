"""Tests for src/imdr/domains/econ/schema.py (prod IndicatorRow / ObservationRow).

This is the prod twin of the playground schema_prototype dataclasses; the
playground copy has its own test file. Both must stay in lockstep on
field names + validation rules, since the same parquet shape feeds the
canonical loader.

Covered:
- IndicatorRow accepts every member of VALID_CATEGORIES and VALID_FREQUENCIES.
- IndicatorRow raises ValueError with the EXACT message string on bad input
  (per project rule -- assert on the message, not just the exception type).
- IndicatorRow optional fields (bbg_ticker / is_active) have correct defaults.
- ObservationRow rejects negative vintage with the EXACT message string.
- ObservationRow ingested_at default is timezone-aware UTC.
- indicators_to_records emits the exact column set expected by
  scripts.migrations.load_econ_indicator_from_playground.
- observations_to_records emits the exact column set expected by
  scripts.migrations.load_econ_indicator_from_playground.
- Round-trip dataclass -> records -> pandas DataFrame preserves shape.
"""

from __future__ import annotations

import datetime

import pytest

from imdr.domains.econ.schema import (
    IndicatorRow,
    ObservationRow,
    VALID_CATEGORIES,
    VALID_FREQUENCIES,
    indicators_to_records,
    observations_to_records,
)

UTC = datetime.timezone.utc


def _valid_indicator(**overrides) -> IndicatorRow:
    defaults = dict(
        imdr_code="KOSTAT.CPI.HEADLINE.YOY.KR",
        vendor_name="KOSIS",
        source_code="101/DT_1J22042/C1=0/ITM_ID=T03",
        display_name="Korea Headline CPI, YoY % (KOSTAT)",
        unit="pct",
        frequency="MONTHLY",
        country_iso="KR",
        category="cpi",
        is_seasonally_adjusted=False,
    )
    defaults.update(overrides)
    return IndicatorRow(**defaults)


def _valid_obs(**overrides) -> ObservationRow:
    defaults = dict(
        imdr_code="KOSTAT.CPI.HEADLINE.YOY.KR",
        obs_date=datetime.date(2026, 1, 1),
        vintage=0,
        release_date=datetime.datetime(2026, 2, 1, tzinfo=UTC),
        value=2.1,
    )
    defaults.update(overrides)
    return ObservationRow(**defaults)


class TestIndicatorRowValidation:
    def test_valid_indicator_constructs(self) -> None:
        row = _valid_indicator()
        assert row.imdr_code == "KOSTAT.CPI.HEADLINE.YOY.KR"
        assert row.category == "cpi"

    def test_invalid_category_raises_with_exact_message(self) -> None:
        with pytest.raises(ValueError) as excinfo:
            _valid_indicator(category="nonsense")
        msg = str(excinfo.value)
        assert msg.startswith("IndicatorRow.category must be one of ")
        assert "got 'nonsense'" in msg

    def test_invalid_frequency_raises_with_exact_message(self) -> None:
        with pytest.raises(ValueError) as excinfo:
            _valid_indicator(frequency="FORTNIGHTLY")
        msg = str(excinfo.value)
        assert msg.startswith("IndicatorRow.frequency must be one of ")
        assert "got 'FORTNIGHTLY'" in msg

    def test_empty_imdr_code_raises_with_exact_message(self) -> None:
        with pytest.raises(ValueError) as excinfo:
            _valid_indicator(imdr_code="")
        assert str(excinfo.value) == "IndicatorRow.imdr_code must not be empty"

    def test_empty_source_code_raises_with_exact_message(self) -> None:
        with pytest.raises(ValueError) as excinfo:
            _valid_indicator(source_code="")
        assert str(excinfo.value) == "IndicatorRow.source_code must not be empty"

    @pytest.mark.parametrize("cat", sorted(VALID_CATEGORIES))
    def test_every_valid_category_accepted(self, cat: str) -> None:
        row = _valid_indicator(category=cat)
        assert row.category == cat

    @pytest.mark.parametrize("freq", sorted(VALID_FREQUENCIES))
    def test_every_valid_frequency_accepted(self, freq: str) -> None:
        row = _valid_indicator(frequency=freq)
        assert row.frequency == freq

    def test_bbg_ticker_defaults_none(self) -> None:
        assert _valid_indicator().bbg_ticker is None

    def test_is_active_defaults_true(self) -> None:
        assert _valid_indicator().is_active is True

    def test_country_iso_optional(self) -> None:
        row = _valid_indicator(country_iso=None)
        assert row.country_iso is None


class TestObservationRowValidation:
    def test_valid_obs_constructs(self) -> None:
        row = _valid_obs()
        assert row.vintage == 0
        assert row.value == pytest.approx(2.1)

    def test_negative_vintage_raises_with_exact_message(self) -> None:
        with pytest.raises(ValueError) as excinfo:
            _valid_obs(vintage=-1)
        assert str(excinfo.value) == "ObservationRow.vintage must be >= 0, got -1"

    def test_empty_imdr_code_raises_with_exact_message(self) -> None:
        with pytest.raises(ValueError) as excinfo:
            _valid_obs(imdr_code="")
        assert str(excinfo.value) == "ObservationRow.imdr_code must not be empty"

    def test_none_value_allowed(self) -> None:
        assert _valid_obs(value=None).value is None

    def test_ingested_at_defaults_to_utc_aware_now(self) -> None:
        before = datetime.datetime.now(UTC)
        row = _valid_obs()
        after = datetime.datetime.now(UTC)
        assert row.ingested_at.tzinfo is not None
        assert before <= row.ingested_at <= after


class TestIndicatorsToRecords:
    def test_returns_list_of_dicts(self) -> None:
        records = indicators_to_records([_valid_indicator()])
        assert isinstance(records, list)
        assert isinstance(records[0], dict)

    def test_emits_expected_loader_column_set(self) -> None:
        # The loader (scripts.migrations.load_econ_indicator_from_playground)
        # reads these exact columns out of the parquet. Any drift here breaks
        # the canonical load step -- pin the column set.
        expected = {
            "imdr_code", "vendor_name", "source_code", "display_name",
            "unit", "frequency", "country_iso", "category",
            "is_seasonally_adjusted", "is_active", "bbg_ticker",
        }
        assert set(indicators_to_records([_valid_indicator()])[0]) == expected

    def test_values_preserved(self) -> None:
        rec = indicators_to_records([_valid_indicator(bbg_ticker="KOCPI INDX Index")])[0]
        assert rec["bbg_ticker"] == "KOCPI INDX Index"
        assert rec["vendor_name"] == "KOSIS"
        assert rec["country_iso"] == "KR"

    def test_empty_input_returns_empty_list(self) -> None:
        assert indicators_to_records([]) == []


class TestObservationsToRecords:
    def test_emits_expected_loader_column_set(self) -> None:
        expected = {
            "imdr_code", "obs_date", "vintage", "release_date",
            "value", "is_preliminary", "ingested_at",
        }
        assert set(observations_to_records([_valid_obs()])[0]) == expected

    def test_vintage_preserved(self) -> None:
        assert observations_to_records([_valid_obs(vintage=3)])[0]["vintage"] == 3

    def test_none_value_preserved(self) -> None:
        assert observations_to_records([_valid_obs(value=None)])[0]["value"] is None

    def test_empty_input_returns_empty_list(self) -> None:
        assert observations_to_records([]) == []


class TestRoundTripDataFrame:
    def test_indicator_round_trip_preserves_rows(self) -> None:
        import pandas as pd

        rows = [
            _valid_indicator(),
            _valid_indicator(imdr_code="BOK.GDP.TOTAL.QOQ_SA.KR",
                             source_code="301/DT_200Y102/10111",
                             category="gdp", frequency="QUARTERLY"),
        ]
        df = pd.DataFrame(indicators_to_records(rows))
        assert len(df) == 2
        assert set(df["category"]) == {"cpi", "gdp"}

    def test_observation_round_trip_preserves_obs_date_type(self) -> None:
        import pandas as pd

        df = pd.DataFrame(observations_to_records([
            _valid_obs(obs_date=datetime.date(2026, 3, 1))
        ]))
        assert df["obs_date"].iloc[0] == datetime.date(2026, 3, 1)
