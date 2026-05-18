"""Tests for ``FXVolPipeline`` transform + iteration form.

Missing-test fix surfaced during the FX domain walk (file 15). Per the
project's testing rule (memory: ``feedback_always_write_tests``) — every
``src/`` module needs tests; pin exact assertion strings; missing tests
is a finding to fix now.
"""
from __future__ import annotations

from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from imdr.domains.fx.pipeline_vol import FXVolPipeline


def _vol_row(
    base_ccy: str = "EUR",
    quote_ccy: str = "USD",
    strike: str = "ATM",
    tenor: str = "1M",
    vol_type: str = "IMPLIED",
    value: float = 7.5,
    ts: datetime | None = None,
) -> dict:
    return {
        "base_ccy": base_ccy,
        "quote_ccy": quote_ccy,
        "strike": strike,
        "tenor": tenor,
        "vol_type": vol_type,
        "value": value,
        "ts": ts or datetime(2026, 3, 10),
    }


class TestIterationForm:
    """Pin the fast iteration form so future refactors can't silently
    reintroduce ``iterrows()`` (10-50× slower on backfill).

    Mirrors the regression guard in ``test_fx_rate_pipeline.py`` /
    ``test_bbg_fx_rate_pipeline.py``.
    """

    def test_transform_uses_to_dict_records_not_iterrows(self) -> None:
        import inspect

        from imdr.domains.fx import pipeline_vol

        src = inspect.getsource(pipeline_vol.FXVolPipeline.transform)
        assert ".iterrows(" not in src, (
            "transform() must not use DataFrame.iterrows — use "
            "to_dict('records') instead (10-50× faster on backfill)."
        )
        assert '.to_dict("records")' in src or ".to_dict('records')" in src


class TestTransform:
    """Cover the FK-resolution + validation path."""

    @patch("imdr.domains.fx.pipeline_vol.FXCurrencyPairRepository")
    def test_transform_resolves_pair_ids(self, mock_repo_cls) -> None:
        pair_obj = MagicMock(base_ccy="EUR", quote_ccy="USD", id=99)
        mock_repo = MagicMock()
        mock_repo.bulk_seed_from_universe.return_value = 0
        mock_repo.all.return_value = [pair_obj]
        mock_repo_cls.return_value = mock_repo

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_connector = MagicMock()
        mock_connector.session.return_value = mock_session

        universe = MagicMock()
        universe.vol_pair_create_entries.return_value = []

        pipeline = FXVolPipeline(
            connector=mock_connector,
            settings=MagicMock(),
            universe=universe,
            start=datetime(2026, 3, 10),
            end=datetime(2026, 3, 10),
        )
        raw = pd.DataFrame([_vol_row(), _vol_row(strike="25RR")])

        observations = pipeline.transform(raw)
        assert len(observations) == 2
        for obs in observations:
            assert obs.pair_id == 99
            assert obs.obs_date == date(2026, 3, 10)
            assert obs.value == 7.5

    @patch("imdr.domains.fx.pipeline_vol.FXCurrencyPairRepository")
    def test_transform_skips_unmapped_pairs(self, mock_repo_cls) -> None:
        mock_repo = MagicMock()
        mock_repo.bulk_seed_from_universe.return_value = 0
        mock_repo.all.return_value = []  # no pairs in cache
        mock_repo_cls.return_value = mock_repo

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_connector = MagicMock()
        mock_connector.session.return_value = mock_session

        universe = MagicMock()
        universe.vol_pair_create_entries.return_value = []

        pipeline = FXVolPipeline(
            connector=mock_connector,
            settings=MagicMock(),
            universe=universe,
            start=datetime(2026, 3, 10),
            end=datetime(2026, 3, 10),
        )
        raw = pd.DataFrame([_vol_row(), _vol_row(base_ccy="GBP")])

        assert pipeline.transform(raw) == []

    @patch("imdr.domains.fx.pipeline_vol.FXCurrencyPairRepository")
    def test_transform_empty_raw_returns_empty(self, mock_repo_cls) -> None:
        mock_repo = MagicMock()
        mock_repo.bulk_seed_from_universe.return_value = 0
        mock_repo.all.return_value = []
        mock_repo_cls.return_value = mock_repo

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_connector = MagicMock()
        mock_connector.session.return_value = mock_session

        universe = MagicMock()
        universe.vol_pair_create_entries.return_value = []

        pipeline = FXVolPipeline(
            connector=mock_connector,
            settings=MagicMock(),
            universe=universe,
            start=datetime(2026, 3, 10),
            end=datetime(2026, 3, 10),
        )
        assert pipeline.transform(pd.DataFrame(columns=["base_ccy", "quote_ccy"])) == []

    @patch("imdr.domains.fx.pipeline_vol.FXCurrencyPairRepository")
    def test_transform_handles_date_or_datetime_ts(self, mock_repo_cls) -> None:
        """Some upstream sources pass ``ts`` as ``date``, others as ``datetime``."""
        pair_obj = MagicMock(base_ccy="EUR", quote_ccy="USD", id=99)
        mock_repo = MagicMock()
        mock_repo.bulk_seed_from_universe.return_value = 0
        mock_repo.all.return_value = [pair_obj]
        mock_repo_cls.return_value = mock_repo

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_connector = MagicMock()
        mock_connector.session.return_value = mock_session

        universe = MagicMock()
        universe.vol_pair_create_entries.return_value = []

        pipeline = FXVolPipeline(
            connector=mock_connector,
            settings=MagicMock(),
            universe=universe,
            start=datetime(2026, 3, 10),
            end=datetime(2026, 3, 10),
        )
        raw = pd.DataFrame([
            _vol_row(ts=datetime(2026, 3, 10, 17, 0)),
            _vol_row(ts=date(2026, 3, 11)),
        ])

        observations = pipeline.transform(raw)
        assert observations[0].obs_date == date(2026, 3, 10)
        assert observations[1].obs_date == date(2026, 3, 11)


class TestLoad:
    def test_load_empty_returns_zero(self) -> None:
        pipeline = FXVolPipeline(
            connector=MagicMock(),
            settings=MagicMock(),
            universe=MagicMock(),
            start=datetime(2026, 3, 10),
            end=datetime(2026, 3, 10),
        )
        assert pipeline.load([]) == 0

    @patch("imdr.domains.fx.pipeline_vol.FXVolRepository")
    def test_load_non_chunked_uses_bulk_upsert(self, mock_repo_cls) -> None:
        mock_repo = MagicMock()
        mock_repo.bulk_upsert.return_value = 42
        mock_repo_cls.return_value = mock_repo

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_connector = MagicMock()
        mock_connector.session.return_value = mock_session

        pipeline = FXVolPipeline(
            connector=mock_connector,
            settings=MagicMock(),
            universe=MagicMock(),
            start=datetime(2026, 3, 10),
            end=datetime(2026, 3, 10),
        )
        result = pipeline.load([MagicMock()])
        assert result == 42

    @patch("imdr.domains.fx.pipeline_vol.chunked_bulk_merge", return_value=99)
    def test_load_chunked_uses_chunked_bulk_merge(self, mock_chunk) -> None:
        pipeline = FXVolPipeline(
            connector=MagicMock(),
            settings=MagicMock(),
            universe=MagicMock(),
            start=datetime(2026, 3, 10),
            end=datetime(2026, 3, 10),
            chunk_size=1000,
        )
        result = pipeline.load([MagicMock()])
        assert result == 99
        assert mock_chunk.called


class TestRunContext:
    def test_run_context_returns_start_date(self) -> None:
        pipeline = FXVolPipeline(
            connector=MagicMock(),
            settings=MagicMock(),
            universe=MagicMock(),
            start=datetime(2026, 3, 10, 17, 0),
            end=datetime(2026, 3, 10, 23, 59),
        )
        assert pipeline.get_run_context() == {"run_date": date(2026, 3, 10)}
