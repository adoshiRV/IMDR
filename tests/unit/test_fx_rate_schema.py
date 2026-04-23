"""Tests for schemas/fx_rate.py Pydantic validation."""

from datetime import date
from decimal import Decimal

import pytest

from imdr.schemas.fx_rate import FXRateCreate


class TestFXRateCreate:
    def _base_kwargs(self) -> dict:
        return {
            "pair_id": 1,
            "vendor_id": 1,
            "frequency_id": 5,  # DAILY
            "obs_date": date(2026, 4, 21),
            "tenor": "1M",
            "mid_rate": Decimal("1.17887"),
            "fwd_points": Decimal("0.001666"),
        }

    def test_valid_forward(self) -> None:
        m = FXRateCreate(**self._base_kwargs())
        assert m.tenor == "1M"
        assert m.mid_rate == Decimal("1.17887")

    def test_valid_spot(self) -> None:
        kwargs = self._base_kwargs()
        kwargs.update(tenor="SPOT", fwd_points=None)
        m = FXRateCreate(**kwargs)
        assert m.tenor == "SPOT"
        assert m.fwd_points is None

    def test_spot_with_fwd_points_rejected(self) -> None:
        kwargs = self._base_kwargs()
        kwargs["tenor"] = "SPOT"
        with pytest.raises(ValueError, match="fwd_points must be NULL for SPOT"):
            FXRateCreate(**kwargs)

    def test_invalid_tenor_rejected(self) -> None:
        kwargs = self._base_kwargs()
        kwargs["tenor"] = "15M"  # not in curated Phase 1 grid
        with pytest.raises(ValueError, match="tenor must be one of"):
            FXRateCreate(**kwargs)

    def test_zero_mid_rate_rejected(self) -> None:
        kwargs = self._base_kwargs()
        kwargs["mid_rate"] = Decimal("0")
        with pytest.raises(ValueError):
            FXRateCreate(**kwargs)

    def test_negative_mid_rate_rejected(self) -> None:
        kwargs = self._base_kwargs()
        kwargs["mid_rate"] = Decimal("-1.5")
        with pytest.raises(ValueError):
            FXRateCreate(**kwargs)

    def test_tenor_case_normalized(self) -> None:
        kwargs = self._base_kwargs()
        kwargs["tenor"] = "1m"
        m = FXRateCreate(**kwargs)
        assert m.tenor == "1M"

    def test_all_tenors_accepted(self) -> None:
        for t in ["SPOT", "ON", "1W", "1M", "3M", "6M", "9M", "1Y", "2Y", "5Y", "10Y"]:
            kwargs = self._base_kwargs()
            kwargs["tenor"] = t
            if t == "SPOT":
                kwargs["fwd_points"] = None
            m = FXRateCreate(**kwargs)
            assert m.tenor == t

    def test_ids_must_be_positive(self) -> None:
        for field in ("pair_id", "vendor_id", "frequency_id"):
            kwargs = self._base_kwargs()
            kwargs[field] = 0
            with pytest.raises(ValueError):
                FXRateCreate(**kwargs)
