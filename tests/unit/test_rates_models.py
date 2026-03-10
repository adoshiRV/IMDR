"""Tests for models/rates.py and schemas/rates.py."""

import pytest
from pydantic import ValidationError

from imdr.models.rates import RatesCurve, RatesObservation
from imdr.schemas.rates import (
    ALLOWED_QUOTES,
    RatesCurveCreate,
    RatesObservationCreate,
)


class TestORMModels:
    def test_rates_curve_tablename(self):
        assert RatesCurve.__tablename__ == "dim_curve"

    def test_rates_curve_schema(self):
        assert RatesCurve.__table_args__[-1]["schema"] == "rates"

    def test_rates_observation_tablename(self):
        assert RatesObservation.__tablename__ == "fact_observation"

    def test_rates_observation_schema(self):
        assert RatesObservation.__table_args__[-1]["schema"] == "rates"

    def test_rates_curve_repr(self):
        c = RatesCurve(ccy="USD", curve="SOFR", curve_type="rfr")
        assert "USD" in repr(c)
        assert "SOFR" in repr(c)


class TestRatesCurveCreate:
    def test_valid(self):
        c = RatesCurveCreate(
            ccy="usd",
            curve="SOFR",
            curve_type="rfr",
            curve_status="active",
            instrument="ois",
            citi_prefix="RATES.OIS.USD_SOFR",
        )
        assert c.ccy == "USD"  # uppercase validator
        assert c.curve_type == "rfr"

    def test_invalid_curve_type(self):
        with pytest.raises(ValidationError):
            RatesCurveCreate(
                ccy="USD",
                curve="SOFR",
                curve_type="invalid",
                curve_status="active",
                instrument="ois",
                citi_prefix="RATES.OIS.USD_SOFR",
            )

    def test_invalid_curve_status(self):
        with pytest.raises(ValidationError):
            RatesCurveCreate(
                ccy="USD",
                curve="SOFR",
                curve_type="rfr",
                curve_status="invalid",
                instrument="ois",
                citi_prefix="RATES.OIS.USD_SOFR",
            )


class TestRatesObservationCreate:
    def test_valid(self):
        o = RatesObservationCreate(
            curve_id=1,
            ts="2024-01-15T00:00:00Z",
            quote="par",
            tenor="5Y",
            value=3.85,
        )
        assert o.quote == "par"
        assert o.value == 3.85

    def test_invalid_quote(self):
        with pytest.raises(ValidationError):
            RatesObservationCreate(
                curve_id=1,
                ts="2024-01-15T00:00:00Z",
                quote="invalid",
                tenor="5Y",
                value=3.85,
            )

    def test_all_allowed_quotes(self):
        for q in ALLOWED_QUOTES:
            o = RatesObservationCreate(
                curve_id=1,
                ts="2024-01-15T00:00:00Z",
                quote=q,
                tenor="5Y",
                value=1.0,
            )
            assert o.quote == q

    def test_quote_normalized_to_lowercase(self):
        o = RatesObservationCreate(
            curve_id=1,
            ts="2024-01-15T00:00:00Z",
            quote="PAR",
            tenor="5Y",
            value=3.85,
        )
        assert o.quote == "par"
