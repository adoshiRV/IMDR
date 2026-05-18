"""Tests for BloombergFXRatePipeline transform path."""
from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from imdr.domains.fx.pipeline_rate_bbg import (
    BloombergFXRatePipeline,
    _ccys_from_universe,
)


@pytest.fixture
def jpy_csv(tmp_path: Path) -> Path:
    """Mirror the real BBG layout: <root>/<CCY>/FX_<CCY>.csv"""
    folder = tmp_path / "JPY"
    folder.mkdir()
    f = folder / "FX_JPY.csv"
    f.write_text(
        "Ticker,JPY curncy,JPY1M curncy\n"
        "Tenor,FX_JPY_SPOT,FX_JPY_1M\n"
        "Maturity,0,0.083333333\n"
        "23/04/2026,159.55,159.1444\n"
    )
    return f


class TestCcysFromUniverse:
    def test_picks_non_usd_leg(self) -> None:
        universe = MagicMock()
        universe.fx_rate_pairs.return_value = [
            ("EUR", "USD"), ("GBP", "USD"), ("USD", "JPY"), ("USD", "HKD"),
        ]
        ccys = _ccys_from_universe(universe)
        assert ccys == ["EUR", "GBP", "JPY", "HKD"]

    def test_dedupes(self) -> None:
        universe = MagicMock()
        universe.fx_rate_pairs.return_value = [
            ("EUR", "USD"), ("EUR", "USD"), ("USD", "JPY"),
        ]
        ccys = _ccys_from_universe(universe)
        assert ccys == ["EUR", "JPY"]


class TestExtract:
    def test_extract_resolves_orientation_and_mtime(self, jpy_csv: Path) -> None:
        pipeline = BloombergFXRatePipeline(
            files=[jpy_csv],
            connector=MagicMock(),
            settings=MagicMock(),
        )
        df = pipeline.extract()

        assert not df.empty
        # USD/JPY orientation
        assert (df["base_ccy"] == "USD").all()
        assert (df["quote_ccy"] == "JPY").all()
        # obs_ts equals the file's mtime (UTC)
        expected_mtime = datetime.fromtimestamp(
            jpy_csv.stat().st_mtime, tz=timezone.utc
        )
        assert (df["obs_ts"] == expected_mtime).all()

    def test_extract_inverse_conversion_applied(self, jpy_csv: Path) -> None:
        """Verifies the BBG-specific math runs inside the pipeline."""
        pipeline = BloombergFXRatePipeline(
            files=[jpy_csv],
            connector=MagicMock(),
            settings=MagicMock(),
        )
        df = pipeline.extract()
        m1 = df[df["tenor"] == "1M"]
        # JPY divisor=100; (159.1444 - 159.55) * 100 ≈ -40.56
        assert float(m1["fwd_points"].iloc[0]) == pytest.approx(-40.56, abs=0.01)


class TestTransform:
    @patch("imdr.domains.fx.pipeline_rate_bbg.FXCurrencyPairRepository")
    def test_transform_resolves_fks_and_validates(
        self, mock_repo_cls, jpy_csv: Path
    ) -> None:
        # Mock pair repo to return USD/JPY pair_id=42
        pair_obj = MagicMock(base_ccy="USD", quote_ccy="JPY", id=42)
        mock_repo = MagicMock()
        mock_repo.bulk_seed_from_universe.return_value = 0
        mock_repo.all.return_value = [pair_obj]
        mock_repo_cls.return_value = mock_repo

        # Mock connector + session
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_connector = MagicMock()
        mock_connector.session.return_value = mock_session

        # Mock vendor + frequency lookups
        vendor_obj = MagicMock(id=4)
        freq_obj = MagicMock(id=2)
        execute_results = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=vendor_obj)),
            MagicMock(scalar_one_or_none=MagicMock(return_value=freq_obj)),
        ]
        mock_session.execute.side_effect = execute_results

        # Mock universe
        universe = MagicMock()
        universe.fx_rate_pair_create_entries.return_value = []

        pipeline = BloombergFXRatePipeline(
            files=[jpy_csv],
            connector=mock_connector,
            settings=MagicMock(),
            universe=universe,
        )
        raw_df = pipeline.extract()
        observations = pipeline.transform(raw_df)

        # Expect SPOT + 1M = 2 rows for one date
        assert len(observations) == 2
        for obs in observations:
            assert obs.pair_id == 42
            assert obs.vendor_id == 4   # bloomberg
            assert obs.frequency_id == 2  # SNAPSHOT
            assert obs.obs_date == date(2026, 4, 23)
            assert obs.obs_ts.tzinfo is not None  # tz-aware

    @patch("imdr.domains.fx.pipeline_rate_bbg.FXCurrencyPairRepository")
    def test_transform_skips_unmapped_pairs(
        self, mock_repo_cls, jpy_csv: Path
    ) -> None:
        # No pairs in cache → JPY rows skipped silently
        mock_repo = MagicMock()
        mock_repo.bulk_seed_from_universe.return_value = 0
        mock_repo.all.return_value = []  # nothing
        mock_repo_cls.return_value = mock_repo

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_connector = MagicMock()
        mock_connector.session.return_value = mock_session

        execute_results = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=MagicMock(id=4))),
            MagicMock(scalar_one_or_none=MagicMock(return_value=MagicMock(id=2))),
        ]
        mock_session.execute.side_effect = execute_results

        universe = MagicMock()
        universe.fx_rate_pair_create_entries.return_value = []

        pipeline = BloombergFXRatePipeline(
            files=[jpy_csv],
            connector=mock_connector,
            settings=MagicMock(),
            universe=universe,
        )
        raw_df = pipeline.extract()
        observations = pipeline.transform(raw_df)

        # All rows skipped because no pair_id resolved
        assert observations == []

    @patch("imdr.domains.fx.pipeline_rate_bbg.FXCurrencyPairRepository")
    def test_transform_raises_if_vendor_missing(
        self, mock_repo_cls, jpy_csv: Path
    ) -> None:
        mock_repo = MagicMock()
        mock_repo.bulk_seed_from_universe.return_value = 0
        mock_repo.all.return_value = []
        mock_repo_cls.return_value = mock_repo

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_connector = MagicMock()
        mock_connector.session.return_value = mock_session

        # Vendor lookup returns None
        execute_results = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=None)),
        ]
        mock_session.execute.side_effect = execute_results

        universe = MagicMock()
        universe.fx_rate_pair_create_entries.return_value = []

        pipeline = BloombergFXRatePipeline(
            files=[jpy_csv],
            connector=mock_connector,
            settings=MagicMock(),
            universe=universe,
        )
        raw_df = pipeline.extract()
        with pytest.raises(RuntimeError, match="bloomberg.*missing"):
            pipeline.transform(raw_df)


class TestEmptyInput:
    def test_extract_no_files_returns_empty_df(self) -> None:
        pipeline = BloombergFXRatePipeline(
            files=[],
            connector=MagicMock(),
            settings=MagicMock(),
        )
        df = pipeline.extract()
        assert df.empty

    def test_load_empty_returns_zero(self) -> None:
        pipeline = BloombergFXRatePipeline(
            files=[],
            connector=MagicMock(),
            settings=MagicMock(),
        )
        assert pipeline.load([]) == 0


class TestTransformRowIteration:
    """Pin the fast iteration form so future refactors can't silently
    reintroduce `iterrows()` (10-50× slower on backfill-sized inputs).

    Mirrors the regression guard in test_fx_rate_pipeline.py for the
    Citi version (commit 2f42fe5).
    """

    def test_transform_uses_to_dict_records_not_iterrows(self) -> None:
        import inspect

        from imdr.domains.fx import pipeline_rate_bbg

        src = inspect.getsource(pipeline_rate_bbg.BloombergFXRatePipeline.transform)
        assert ".iterrows(" not in src, (
            "transform() must not use DataFrame.iterrows — use "
            "to_dict('records') instead (10-50× faster on backfill)."
        )
        assert '.to_dict("records")' in src or ".to_dict('records')" in src

    @patch("imdr.domains.fx.pipeline_rate_bbg.FXCurrencyPairRepository")
    def test_transform_skips_nan_mid_rate(
        self, mock_repo_cls, jpy_csv: Path
    ) -> None:
        """A row with NaN mid_rate must be silently dropped (schema requires NOT NULL)."""
        pair_obj = MagicMock(base_ccy="USD", quote_ccy="JPY", id=42)
        mock_repo = MagicMock()
        mock_repo.bulk_seed_from_universe.return_value = 0
        mock_repo.all.return_value = [pair_obj]
        mock_repo_cls.return_value = mock_repo

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_connector = MagicMock()
        mock_connector.session.return_value = mock_session
        mock_session.execute.side_effect = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=MagicMock(id=4))),
            MagicMock(scalar_one_or_none=MagicMock(return_value=MagicMock(id=2))),
        ]

        universe = MagicMock()
        universe.fx_rate_pair_create_entries.return_value = []

        pipeline = BloombergFXRatePipeline(
            files=[jpy_csv],
            connector=mock_connector,
            settings=MagicMock(),
            universe=universe,
        )
        raw = pipeline.extract().copy()
        # Force NaN mid_rate on every row
        raw["mid_rate"] = float("nan")

        observations = pipeline.transform(raw)
        assert observations == []

    @patch("imdr.domains.fx.pipeline_rate_bbg.FXCurrencyPairRepository")
    def test_transform_raises_if_frequency_missing(
        self, mock_repo_cls, jpy_csv: Path
    ) -> None:
        """Missing dim_frequency must surface the migration-023 hint."""
        mock_repo = MagicMock()
        mock_repo.bulk_seed_from_universe.return_value = 0
        mock_repo.all.return_value = []
        mock_repo_cls.return_value = mock_repo

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_connector = MagicMock()
        mock_connector.session.return_value = mock_session

        # Vendor resolves; frequency returns None
        mock_session.execute.side_effect = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=MagicMock(id=4))),
            MagicMock(scalar_one_or_none=MagicMock(return_value=None)),
        ]

        universe = MagicMock()
        universe.fx_rate_pair_create_entries.return_value = []

        pipeline = BloombergFXRatePipeline(
            files=[jpy_csv],
            connector=mock_connector,
            settings=MagicMock(),
            universe=universe,
        )
        raw_df = pipeline.extract()
        with pytest.raises(
            RuntimeError, match="SNAPSHOT.*dim_frequency.*023_create_dim_frequency"
        ):
            pipeline.transform(raw_df)

    @patch("imdr.domains.fx.pipeline_rate_bbg.FXCurrencyPairRepository")
    def test_transform_skips_invalid_pydantic_row(
        self, mock_repo_cls, jpy_csv: Path
    ) -> None:
        """Negative mid_rate (Pydantic >0 constraint) is dropped, not raised."""
        pair_obj = MagicMock(base_ccy="USD", quote_ccy="JPY", id=42)
        mock_repo = MagicMock()
        mock_repo.bulk_seed_from_universe.return_value = 0
        mock_repo.all.return_value = [pair_obj]
        mock_repo_cls.return_value = mock_repo

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_connector = MagicMock()
        mock_connector.session.return_value = mock_session
        mock_session.execute.side_effect = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=MagicMock(id=4))),
            MagicMock(scalar_one_or_none=MagicMock(return_value=MagicMock(id=2))),
        ]

        universe = MagicMock()
        universe.fx_rate_pair_create_entries.return_value = []

        pipeline = BloombergFXRatePipeline(
            files=[jpy_csv],
            connector=mock_connector,
            settings=MagicMock(),
            universe=universe,
        )
        raw = pipeline.extract().copy()
        raw["mid_rate"] = -1.0  # FXRateCreate enforces mid_rate > 0

        observations = pipeline.transform(raw)
        assert observations == []


class TestGetRunContext:
    def test_returns_latest_obs_date(self, jpy_csv: Path) -> None:
        pipeline = BloombergFXRatePipeline(
            files=[jpy_csv],
            connector=MagicMock(),
            settings=MagicMock(),
        )
        pipeline.extract()
        ctx = pipeline.get_run_context()
        assert "run_date" in ctx
        assert ctx["run_date"] == date(2026, 4, 23)

    def test_returns_empty_when_no_data(self) -> None:
        pipeline = BloombergFXRatePipeline(
            files=[],
            connector=MagicMock(),
            settings=MagicMock(),
        )
        pipeline.extract()
        assert pipeline.get_run_context() == {}
