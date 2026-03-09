from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from imdr.schemas.fx import FXSpotRateCreate


class TestFXSpotRateCreate:
    def test_valid_rate(self) -> None:
        rate = FXSpotRateCreate(
            base_currency="usd",
            quote_currency="eur",
            rate_date=date(2025, 1, 15),
            mid=Decimal("1.08500000"),
            source="Bloomberg",
        )
        assert rate.base_currency == "USD"
        assert rate.quote_currency == "EUR"

    def test_invalid_currency_too_short(self) -> None:
        with pytest.raises(ValidationError):
            FXSpotRateCreate(
                base_currency="US",
                quote_currency="EUR",
                rate_date=date(2025, 1, 15),
                mid=Decimal("1.085"),
                source="Bloomberg",
            )

    def test_invalid_currency_too_long(self) -> None:
        with pytest.raises(ValidationError):
            FXSpotRateCreate(
                base_currency="USDD",
                quote_currency="EUR",
                rate_date=date(2025, 1, 15),
                mid=Decimal("1.085"),
                source="Bloomberg",
            )

    def test_ask_less_than_bid_rejected(self) -> None:
        with pytest.raises(ValidationError, match="ask must be >= bid"):
            FXSpotRateCreate(
                base_currency="USD",
                quote_currency="EUR",
                rate_date=date(2025, 1, 15),
                mid=Decimal("1.085"),
                bid=Decimal("1.086"),
                ask=Decimal("1.084"),
                source="Bloomberg",
            )

    def test_ask_equal_to_bid_accepted(self) -> None:
        rate = FXSpotRateCreate(
            base_currency="USD",
            quote_currency="EUR",
            rate_date=date(2025, 1, 15),
            mid=Decimal("1.085"),
            bid=Decimal("1.085"),
            ask=Decimal("1.085"),
            source="Bloomberg",
        )
        assert rate.ask == rate.bid

    def test_mid_must_be_positive(self) -> None:
        with pytest.raises(ValidationError):
            FXSpotRateCreate(
                base_currency="USD",
                quote_currency="EUR",
                rate_date=date(2025, 1, 15),
                mid=Decimal("0"),
                source="Bloomberg",
            )
