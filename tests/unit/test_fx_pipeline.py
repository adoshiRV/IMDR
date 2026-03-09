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
        pipeline = FXSpotRatePipeline(connector, source_path=Path("dummy.csv"))
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
        pipeline = FXSpotRatePipeline(connector, source_path=Path("dummy.csv"))
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
        pipeline = FXSpotRatePipeline(connector, source_path=Path("dummy.csv"))
        df = pd.DataFrame(columns=["base_currency", "quote_currency", "rate_date", "mid", "source"])
        result = pipeline.transform(df)
        assert len(result) == 0

    def test_pipeline_has_name_and_domain(self) -> None:
        connector = MagicMock()
        pipeline = FXSpotRatePipeline(connector, source_path=Path("dummy.csv"))
        assert pipeline.pipeline_name == "fx.spot_rates"
        assert pipeline.domain == "fx"

    def test_get_health_checks_returns_checks(self) -> None:
        connector = MagicMock()
        pipeline = FXSpotRatePipeline(connector, source_path=Path("dummy.csv"))
        checks = pipeline.get_health_checks()
        assert len(checks) > 0
        check_names = [type(c).__name__ for c in checks]
        assert "RowCountCheck" in check_names
        assert "NullCheck" in check_names
        assert "DuplicateCheck" in check_names

    def test_extract_raises_without_source(self) -> None:
        connector = MagicMock()
        pipeline = FXSpotRatePipeline(connector)
        import pytest
        with pytest.raises(ValueError, match="Either extractor or source_path"):
            pipeline.extract()
