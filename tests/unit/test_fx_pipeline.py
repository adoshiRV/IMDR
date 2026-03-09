from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd

from imdr.domains.fx.pipeline import FXSpotRatePipeline


class TestFXSpotRatePipeline:
    def test_transform_validates_records(self) -> None:
        connector = MagicMock()
        pipeline = FXSpotRatePipeline(connector, Path("dummy.csv"))
        df = pd.DataFrame([
            {
                "base_currency": "USD",
                "quote_currency": "EUR",
                "rate_date": date(2025, 1, 1),
                "mid": Decimal("1.085"),
                "source": "Test",
            },
        ])
        result = pipeline.transform(df)
        assert len(result) == 1
        assert result[0].base_currency == "USD"

    def test_transform_skips_invalid_rows(self) -> None:
        connector = MagicMock()
        pipeline = FXSpotRatePipeline(connector, Path("dummy.csv"))
        df = pd.DataFrame([
            {
                "base_currency": "USD",
                "quote_currency": "EUR",
                "rate_date": date(2025, 1, 1),
                "mid": Decimal("1.085"),
                "source": "Test",
            },
            {
                "base_currency": "X",
                "quote_currency": "EUR",
                "rate_date": date(2025, 1, 1),
                "mid": Decimal("1.085"),
                "source": "Test",
            },
        ])
        result = pipeline.transform(df)
        assert len(result) == 1

    def test_transform_empty_dataframe(self) -> None:
        connector = MagicMock()
        pipeline = FXSpotRatePipeline(connector, Path("dummy.csv"))
        df = pd.DataFrame(columns=["base_currency", "quote_currency", "rate_date", "mid", "source"])
        result = pipeline.transform(df)
        assert len(result) == 0
