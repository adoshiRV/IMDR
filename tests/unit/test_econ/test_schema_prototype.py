"""Tests for playground/econ/schema_prototype.py.

Covered:
- IndicatorRow validates category against CHECK constraint values.
- IndicatorRow validates frequency against dim_frequency enum.
- IndicatorRow raises ValueError with the exact message text on bad input.
- ObservationRow raises ValueError on negative vintage.
- ObservationRow defaults ingested_at to now (timezone-aware).
- indicators_to_records returns the expected column set.
- observations_to_records returns the expected column set.
- Round-trip: dataclass → dict → DataFrame preserves types.
"""

from __future__ import annotations

import datetime

import pytest

from playground.econ.schema_prototype import (
    IndicatorRow,
    ObservationRow,
    VALID_CATEGORIES,
    VALID_FREQUENCIES,
    indicators_to_records,
    observations_to_records,
)

UTC = datetime.timezone.utc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _valid_indicator(**overrides) -> IndicatorRow:
    defaults = dict(
        imdr_code="FRED.CPI.HEADLINE_SA.US",
        vendor_name="FRED",
        source_code="CPIAUCSL",
        description="CPI All Urban Consumers",
        unit="index",
        frequency="MONTHLY",
        country_iso="US",
        category="cpi",
        is_seasonally_adjusted=True,
    )
    defaults.update(overrides)
    return IndicatorRow(**defaults)


def _valid_obs(**overrides) -> ObservationRow:
    defaults = dict(
        imdr_code="FRED.CPI.HEADLINE_SA.US",
        obs_date=datetime.date(2024, 1, 1),
        vintage=0,
        release_date=datetime.datetime(2024, 1, 15, tzinfo=UTC),
        value=310.326,
    )
    defaults.update(overrides)
    return ObservationRow(**defaults)


# ---------------------------------------------------------------------------
# IndicatorRow validation
# ---------------------------------------------------------------------------

class TestIndicatorRowValidation:
    def test_valid_indicator_constructs_without_error(self) -> None:
        row = _valid_indicator()
        assert row.imdr_code == "FRED.CPI.HEADLINE_SA.US"
        assert row.category == "cpi"

    def test_invalid_category_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="IndicatorRow.category must be one of"):
            _valid_indicator(category="nonsense")

    def test_invalid_frequency_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="IndicatorRow.frequency must be one of"):
            _valid_indicator(frequency="FORTNIGHTLY")

    def test_empty_imdr_code_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="IndicatorRow.imdr_code must not be empty"):
            _valid_indicator(imdr_code="")

    def test_empty_source_code_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="IndicatorRow.source_code must not be empty"):
            _valid_indicator(source_code="")

    def test_all_valid_categories_accepted(self) -> None:
        for cat in VALID_CATEGORIES:
            row = _valid_indicator(category=cat)
            assert row.category == cat

    def test_all_valid_frequencies_accepted(self) -> None:
        for freq in VALID_FREQUENCIES:
            row = _valid_indicator(frequency=freq)
            assert row.frequency == freq

    def test_optional_fields_default_to_none(self) -> None:
        row = _valid_indicator()
        assert row.bbg_ticker is None
        assert row.country_iso == "US"

    def test_is_active_defaults_true(self) -> None:
        row = _valid_indicator()
        assert row.is_active is True


# ---------------------------------------------------------------------------
# ObservationRow validation
# ---------------------------------------------------------------------------

class TestObservationRowValidation:
    def test_valid_obs_constructs(self) -> None:
        row = _valid_obs()
        assert row.vintage == 0
        assert row.value == pytest.approx(310.326)

    def test_negative_vintage_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="ObservationRow.vintage must be >= 0"):
            _valid_obs(vintage=-1)

    def test_zero_vintage_accepted(self) -> None:
        row = _valid_obs(vintage=0)
        assert row.vintage == 0

    def test_positive_vintage_accepted(self) -> None:
        row = _valid_obs(vintage=5)
        assert row.vintage == 5

    def test_none_value_allowed(self) -> None:
        row = _valid_obs(value=None)
        assert row.value is None

    def test_empty_imdr_code_raises(self) -> None:
        with pytest.raises(ValueError, match="ObservationRow.imdr_code must not be empty"):
            _valid_obs(imdr_code="")

    def test_ingested_at_defaults_to_utc_now(self) -> None:
        before = datetime.datetime.now(UTC)
        row = _valid_obs()
        after = datetime.datetime.now(UTC)
        assert row.ingested_at.tzinfo is not None
        assert before <= row.ingested_at <= after


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------

class TestIndicatorsToRecords:
    def test_returns_list_of_dicts(self) -> None:
        rows = [_valid_indicator()]
        records = indicators_to_records(rows)
        assert isinstance(records, list)
        assert len(records) == 1
        assert isinstance(records[0], dict)

    def test_expected_keys_present(self) -> None:
        expected = {
            "imdr_code", "vendor_name", "source_code", "description",
            "unit", "frequency", "country_iso", "category",
            "is_seasonally_adjusted", "is_active", "bbg_ticker",
        }
        records = indicators_to_records([_valid_indicator()])
        assert set(records[0].keys()) == expected

    def test_values_preserved(self) -> None:
        row = _valid_indicator(bbg_ticker="CPI INDX Index")
        rec = indicators_to_records([row])[0]
        assert rec["imdr_code"] == "FRED.CPI.HEADLINE_SA.US"
        assert rec["vendor_name"] == "FRED"
        assert rec["bbg_ticker"] == "CPI INDX Index"
        assert rec["is_seasonally_adjusted"] is True

    def test_empty_list_returns_empty_list(self) -> None:
        assert indicators_to_records([]) == []

    def test_multiple_rows(self) -> None:
        rows = [
            _valid_indicator(imdr_code="FRED.CPI.HEADLINE_SA.US", source_code="CPIAUCSL"),
            _valid_indicator(imdr_code="FRED.GDP.REAL_SA.US", source_code="GDPC1", category="gdp"),
        ]
        records = indicators_to_records(rows)
        assert len(records) == 2
        assert records[1]["category"] == "gdp"


class TestObservationsToRecords:
    def test_returns_list_of_dicts(self) -> None:
        records = observations_to_records([_valid_obs()])
        assert isinstance(records, list)
        assert len(records) == 1

    def test_expected_keys_present(self) -> None:
        expected = {
            "imdr_code", "obs_date", "vintage", "release_date",
            "value", "is_preliminary", "ingested_at",
        }
        records = observations_to_records([_valid_obs()])
        assert set(records[0].keys()) == expected

    def test_vintage_preserved(self) -> None:
        rec = observations_to_records([_valid_obs(vintage=3)])[0]
        assert rec["vintage"] == 3

    def test_none_value_preserved(self) -> None:
        rec = observations_to_records([_valid_obs(value=None)])[0]
        assert rec["value"] is None

    def test_empty_list_returns_empty_list(self) -> None:
        assert observations_to_records([]) == []


# ---------------------------------------------------------------------------
# Round-trip: dataclass → dict → pandas DataFrame
# ---------------------------------------------------------------------------

class TestRoundTrip:
    def test_indicator_dataframe_has_correct_dtypes(self) -> None:
        import pandas as pd

        rows = [_valid_indicator(bbg_ticker=None), _valid_indicator(imdr_code="FRED.GDP.REAL_SA.US", source_code="GDPC1", category="gdp")]
        df = pd.DataFrame(indicators_to_records(rows))
        assert "imdr_code" in df.columns
        assert df.dtypes["is_seasonally_adjusted"] == bool or df.dtypes["is_seasonally_adjusted"] == object
        assert len(df) == 2

    def test_observation_dataframe_obs_date_is_date_type(self) -> None:
        import pandas as pd

        rows = [_valid_obs(obs_date=datetime.date(2024, 3, 1))]
        df = pd.DataFrame(observations_to_records(rows))
        assert df["obs_date"].iloc[0] == datetime.date(2024, 3, 1)
