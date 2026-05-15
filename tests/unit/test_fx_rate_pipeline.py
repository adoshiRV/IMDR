"""Tests for `FXRatePipeline.transform()` — the Citi-rate transform path.

Covers the validation + FK resolution + per-row skip semantics:
- vendor / frequency lookup failures raise `RuntimeError` with exact messages
- skipped_unmapped: pair not in `dim_currency_pair` cache → silently dropped
- skipped_nan_mid: `mid_rate` is NaN → skipped (NOT NULL schema constraint)
- skipped_nonpositive: `mid_rate <= 0` → skipped (placeholder sentinels)
- happy path: valid rows produce `FXRateCreate` objects with correct FKs
- `to_dict("records")` iteration is used (not `iterrows`) — regression guard

`extract()` and `load()` are not directly exercised here — they wrap the
Citi client + the bulk-merge plumbing respectively and are integration-
level. `get_health_checks()` and `get_run_context()` are pinned.
"""

from __future__ import annotations

import inspect
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from imdr.domains.fx import pipeline_rate as pipeline_rate_module
from imdr.domains.fx.pipeline_rate import VENDOR_CODE, FXRatePipeline

UTC = timezone.utc
START = datetime(2026, 5, 1, tzinfo=UTC)
END = datetime(2026, 5, 2, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_raw_df(rows: list[dict]) -> pd.DataFrame:
    """Build the wide-shape raw frame that extract() produces."""
    return pd.DataFrame(rows, columns=[
        "ts", "base_ccy", "quote_ccy", "tenor", "mid_rate", "fwd_points",
    ])


def _row(
    base: str = "EUR",
    quote: str = "USD",
    tenor: str = "SPOT",
    mid: float | None = 1.085,
    fwd: float | None = None,
    ts: datetime | None = None,
) -> dict:
    return {
        "ts": ts or START,
        "base_ccy": base,
        "quote_ccy": quote,
        "tenor": tenor,
        "mid_rate": mid,
        "fwd_points": fwd,
    }


def _make_pipeline(connector=None, universe=None) -> FXRatePipeline:
    return FXRatePipeline(
        connector=connector or MagicMock(name="MSSQLConnector"),
        settings=MagicMock(name="Settings"),
        universe=universe or MagicMock(name="FXUniverse"),
        start=START,
        end=END,
    )


def _patch_transform_dependencies(
    pair_id_map: dict[tuple[str, str], int] | None = None,
    vendor_id: int | None = 4,
    frequency_id: int | None = 2,
) -> tuple[MagicMock, MagicMock, list[MagicMock]]:
    """Wire up the session + repos + dim_vendor + dim_frequency mocks.

    Returns (connector, FXCurrencyPairRepository mock class, execute side_effect list).
    Caller patches `imdr.domains.fx.pipeline_rate.FXCurrencyPairRepository` to the
    returned class mock.
    """
    pair_id_map = pair_id_map or {("EUR", "USD"): 42}

    # Pair repo: bulk_seed_from_universe + .all() returns the pair objects.
    pair_objs = [
        MagicMock(base_ccy=b, quote_ccy=q, id=i) for (b, q), i in pair_id_map.items()
    ]
    pair_repo = MagicMock(name="FXCurrencyPairRepository_instance")
    pair_repo.bulk_seed_from_universe.return_value = 0
    pair_repo.all.return_value = pair_objs
    pair_repo_cls = MagicMock(return_value=pair_repo)

    # Session context manager.
    session = MagicMock(name="session")
    session_cm = MagicMock()
    session_cm.__enter__ = MagicMock(return_value=session)
    session_cm.__exit__ = MagicMock(return_value=None)
    connector = MagicMock(name="MSSQLConnector")
    connector.session.return_value = session_cm

    # vendor + frequency .execute() calls return scalar_one_or_none() == obj or None.
    vendor_obj = MagicMock(id=vendor_id) if vendor_id is not None else None
    freq_obj = MagicMock(id=frequency_id) if frequency_id is not None else None
    session.execute.side_effect = [
        MagicMock(scalar_one_or_none=MagicMock(return_value=vendor_obj)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=freq_obj)),
    ]

    return connector, pair_repo_cls, session.execute.side_effect


# ---------------------------------------------------------------------------
# transform — happy path
# ---------------------------------------------------------------------------


class TestTransformHappyPath:
    def test_valid_row_produces_fxrate_create_with_correct_fks(self) -> None:
        connector, pair_repo_cls, _ = _patch_transform_dependencies()
        universe = MagicMock(name="FXUniverse")
        universe.fx_rate_pair_create_entries.return_value = []

        pipeline = _make_pipeline(connector=connector, universe=universe)
        raw = _make_raw_df([_row(mid=1.085, fwd=None)])

        with patch.object(pipeline_rate_module, "FXCurrencyPairRepository", pair_repo_cls):
            observations = pipeline.transform(raw)

        assert len(observations) == 1
        obs = observations[0]
        assert obs.pair_id == 42
        assert obs.vendor_id == 4
        assert obs.frequency_id == 2
        assert obs.tenor == "SPOT"
        assert obs.mid_rate == Decimal("1.085")
        assert obs.fwd_points is None
        assert obs.obs_date == date(2026, 5, 1)

    def test_forward_row_carries_fwd_points(self) -> None:
        connector, pair_repo_cls, _ = _patch_transform_dependencies()
        universe = MagicMock(name="FXUniverse")
        universe.fx_rate_pair_create_entries.return_value = []

        pipeline = _make_pipeline(connector=connector, universe=universe)
        raw = _make_raw_df([_row(tenor="1M", mid=1.0855, fwd=0.0005)])

        with patch.object(pipeline_rate_module, "FXCurrencyPairRepository", pair_repo_cls):
            observations = pipeline.transform(raw)

        assert len(observations) == 1
        assert observations[0].tenor == "1M"
        assert observations[0].fwd_points == Decimal("0.0005")

    def test_empty_raw_short_circuits_after_fk_resolution(self) -> None:
        """Empty raw frame → returns [] without iterating, but vendor/frequency
        lookups still run (they're cheap and surface mis-config early)."""
        connector, pair_repo_cls, _ = _patch_transform_dependencies()
        universe = MagicMock(name="FXUniverse")
        universe.fx_rate_pair_create_entries.return_value = []

        pipeline = _make_pipeline(connector=connector, universe=universe)
        raw = _make_raw_df([])

        with patch.object(pipeline_rate_module, "FXCurrencyPairRepository", pair_repo_cls):
            observations = pipeline.transform(raw)

        assert observations == []


# ---------------------------------------------------------------------------
# transform — skip semantics
# ---------------------------------------------------------------------------


class TestTransformSkipPaths:
    def test_unmapped_pair_silently_skipped(self) -> None:
        """A row whose (base, quote) is not in dim_currency_pair → dropped
        rather than raising (the universe seeds dim_currency_pair, so this
        only happens for pairs Citi returns unexpectedly)."""
        connector, pair_repo_cls, _ = _patch_transform_dependencies(
            pair_id_map={("EUR", "USD"): 42},  # GBP/USD not in cache
        )
        universe = MagicMock(name="FXUniverse")
        universe.fx_rate_pair_create_entries.return_value = []

        pipeline = _make_pipeline(connector=connector, universe=universe)
        raw = _make_raw_df([
            _row(base="EUR", mid=1.085),    # mapped → kept
            _row(base="GBP", mid=1.265),    # unmapped → dropped
        ])

        with patch.object(pipeline_rate_module, "FXCurrencyPairRepository", pair_repo_cls):
            observations = pipeline.transform(raw)

        assert len(observations) == 1
        assert observations[0].pair_id == 42

    def test_nan_mid_rate_dropped(self) -> None:
        """fwd_points-only rows can have NaN mid_rate when the outright tag
        didn't return data — schema is NOT NULL on mid_rate so drop the row."""
        connector, pair_repo_cls, _ = _patch_transform_dependencies()
        universe = MagicMock(name="FXUniverse")
        universe.fx_rate_pair_create_entries.return_value = []

        pipeline = _make_pipeline(connector=connector, universe=universe)
        raw = _make_raw_df([
            _row(mid=None, fwd=0.0005),   # NaN mid → dropped
            _row(mid=1.085, fwd=None),    # valid → kept
        ])

        with patch.object(pipeline_rate_module, "FXCurrencyPairRepository", pair_repo_cls):
            observations = pipeline.transform(raw)

        assert len(observations) == 1
        assert observations[0].mid_rate == Decimal("1.085")

    def test_nonpositive_mid_rate_dropped(self) -> None:
        """Citi occasionally returns 0 or negative for thin tenors as a
        placeholder/error sentinel. FX outrights must be > 0, so drop."""
        connector, pair_repo_cls, _ = _patch_transform_dependencies()
        universe = MagicMock(name="FXUniverse")
        universe.fx_rate_pair_create_entries.return_value = []

        pipeline = _make_pipeline(connector=connector, universe=universe)
        raw = _make_raw_df([
            _row(mid=0.0),    # zero → dropped
            _row(mid=-1.0),   # negative → dropped
            _row(mid=1.085),  # valid → kept
        ])

        with patch.object(pipeline_rate_module, "FXCurrencyPairRepository", pair_repo_cls):
            observations = pipeline.transform(raw)

        assert len(observations) == 1
        assert observations[0].mid_rate == Decimal("1.085")


# ---------------------------------------------------------------------------
# transform — vendor / frequency dim lookup failures
# ---------------------------------------------------------------------------


class TestTransformDimLookupFailures:
    def test_missing_vendor_raises_with_exact_message(self) -> None:
        connector, pair_repo_cls, _ = _patch_transform_dependencies(vendor_id=None)
        universe = MagicMock(name="FXUniverse")
        universe.fx_rate_pair_create_entries.return_value = []

        pipeline = _make_pipeline(connector=connector, universe=universe)
        raw = _make_raw_df([_row()])

        with patch.object(pipeline_rate_module, "FXCurrencyPairRepository", pair_repo_cls):
            with pytest.raises(
                RuntimeError,
                match=f"Vendor '{VENDOR_CODE}' missing from dbo.dim_vendor",
            ):
                pipeline.transform(raw)

    def test_missing_frequency_raises_with_migration_hint(self) -> None:
        connector, pair_repo_cls, _ = _patch_transform_dependencies(frequency_id=None)
        universe = MagicMock(name="FXUniverse")
        universe.fx_rate_pair_create_entries.return_value = []

        pipeline = _make_pipeline(connector=connector, universe=universe)
        raw = _make_raw_df([_row()])

        with patch.object(pipeline_rate_module, "FXCurrencyPairRepository", pair_repo_cls):
            with pytest.raises(
                RuntimeError,
                match=r"Frequency 'DAILY' missing.*023_create_dim_frequency\.sql",
            ):
                pipeline.transform(raw)


# ---------------------------------------------------------------------------
# transform — regression: iterrows must NOT come back
# ---------------------------------------------------------------------------


class TestNoIterrowsRegression:
    def test_transform_source_uses_to_dict_records_not_iterrows(self) -> None:
        """Pin the perf rewrite — the historical-backfill case ran 10-50×
        slower with iterrows. If a future refactor reintroduces the call,
        this test catches it.

        Note: matches the call form `.iterrows(` so that mentions of the
        method name in a comment (explaining *why* we don't use it) don't
        trigger a false positive.
        """
        source = inspect.getsource(FXRatePipeline.transform)
        assert ".iterrows(" not in source, (
            "FXRatePipeline.transform must use to_dict('records') instead of "
            "iterrows() — see fx_walk_optimization_log.md file 12."
        )
        assert 'to_dict("records")' in source or "to_dict('records')" in source


# ---------------------------------------------------------------------------
# load — empty short-circuit
# ---------------------------------------------------------------------------


class TestLoad:
    def test_empty_data_returns_zero_no_db_call(self) -> None:
        connector = MagicMock(name="MSSQLConnector")
        pipeline = _make_pipeline(connector=connector)

        rows_loaded = pipeline.load([])

        assert rows_loaded == 0
        connector.session.assert_not_called()


# ---------------------------------------------------------------------------
# get_run_context + get_health_checks shape
# ---------------------------------------------------------------------------


class TestRunContext:
    def test_run_context_returns_start_date(self) -> None:
        pipeline = _make_pipeline()
        ctx = pipeline.get_run_context()
        assert ctx == {"run_date": START.date()}


class TestHealthChecks:
    def test_get_health_checks_returns_four_base_plus_value_ranges(self) -> None:
        """Base checks: RowCount, Null, Duplicate, Freshness. Plus one
        ValueRangeCheck per entry in config.health_checks.value_ranges."""
        pipeline = _make_pipeline()
        checks = pipeline.get_health_checks()

        # Names: RowCountCheck, NullCheck, DuplicateCheck, FreshnessCheck,
        # then ValueRangeChecks (count depends on pipelines.yml).
        check_types = [type(c).__name__ for c in checks]
        assert check_types[:4] == [
            "RowCountCheck",
            "NullCheck",
            "DuplicateCheck",
            "FreshnessCheck",
        ]
        # Remaining are ValueRangeCheck instances.
        assert all(t == "ValueRangeCheck" for t in check_types[4:])
