"""Tests for `CitiVelocityFXRateExtractor`.

The extractor is networked through Citi; tests mock `fetch_and_parse_batched`
at the module boundary so the orchestration logic can be exercised without an
HTTP layer.

Covered:
- `__init__` defaults — `_errors` and `_tag_errors` start empty.
- Empty fetch → `pd.DataFrame(columns=WIDE_COLUMNS)`.
- `TagQuotaExceeded` is re-raised; remaining pairs are not attempted.
- Generic per-pair exception is captured in `_errors`; loop continues.
- Default pair list excludes `fx_rate_bbg_only_pairs`.
- Spot-only pair emits only the spot tag (no outright/point tags).
- Pre-flight budget formula: `1 + 2 * len(forward_tenors)` per non-spot-only
  pair; `1` per spot-only pair; called with `pipeline_name="fx.citi_rate"`.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from imdr.connectors.citi_helpers import TagQuotaExceeded
from imdr.domains.fx.extractors_rate import CitiVelocityFXRateExtractor
from imdr.domains.fx.rate_translate import WIDE_COLUMNS

UTC = timezone.utc
START = datetime(2026, 5, 1, tzinfo=UTC)
END = datetime(2026, 5, 2, tzinfo=UTC)


def _make_universe(
    pairs: list[tuple[str, str]],
    spot_only: set[tuple[str, str]] | None = None,
    bbg_only: set[tuple[str, str]] | None = None,
    forward_tenors: list[str] | None = None,
) -> MagicMock:
    """Build a MagicMock FXUniverse exposing only the methods the extractor uses."""
    universe = MagicMock(name="FXUniverse")
    universe.fx_rate_pairs.return_value = pairs
    universe.fx_rate_spot_only_pairs.return_value = spot_only or set()
    universe.fx_rate_bbg_only_pairs.return_value = bbg_only or set()
    universe.fx_rate_forward_tenors.return_value = forward_tenors or ["1M", "3M"]
    universe.build_fx_rate_spot_tag.side_effect = lambda c1, c2: f"FX.SPOT.{c1}.{c2}.CITI"
    universe.build_fx_rate_outright_tags.side_effect = lambda c1, c2: [
        f"FX.FORWARD.FWD_OUTRIGHT.{c1}.{c2}.{t}.CITI"
        for t in universe.fx_rate_forward_tenors.return_value
    ]
    universe.build_fx_rate_point_tags.side_effect = lambda c1, c2: [
        f"FX.FORWARD.FWD_POINT.{c1}.{c2}.{t}.CITI"
        for t in universe.fx_rate_forward_tenors.return_value
    ]
    return universe


def _make_settings() -> MagicMock:
    settings = MagicMock(name="Settings")
    settings.citi_batch_size = 50
    settings.citi_rate_limit_sec = 0.0
    return settings


def _make_extractor(
    universe: MagicMock,
    quota_tracker: MagicMock | None = None,
) -> CitiVelocityFXRateExtractor:
    return CitiVelocityFXRateExtractor(
        client=MagicMock(name="CitiVelocityClient"),
        settings=_make_settings(),
        universe=universe,
        quota_tracker=quota_tracker,
    )


# ---------------------------------------------------------------------------
# __init__ defaults
# ---------------------------------------------------------------------------


class TestInit:
    def test_error_lists_start_empty(self) -> None:
        extractor = _make_extractor(_make_universe([("EUR", "USD")]))
        assert extractor.errors == []
        assert extractor.tag_errors == []


# ---------------------------------------------------------------------------
# extract — happy / empty paths
# ---------------------------------------------------------------------------


class TestExtractEmptyResult:
    def test_empty_fetch_returns_empty_wide_df(self) -> None:
        # fetch_and_parse_batched returns an empty DF for every pair → no long_frames.
        universe = _make_universe([("EUR", "USD")])
        extractor = _make_extractor(universe)

        with patch(
            "imdr.domains.fx.extractors_rate.fetch_and_parse_batched",
            return_value=pd.DataFrame(),
        ) as mock_fetch:
            result = extractor.extract(START, END)

        assert list(result.columns) == WIDE_COLUMNS
        assert result.empty
        mock_fetch.assert_called_once()


# ---------------------------------------------------------------------------
# extract — error semantics
# ---------------------------------------------------------------------------


class TestExtractErrors:
    def test_tag_quota_exceeded_re_raises_and_stops_loop(self) -> None:
        universe = _make_universe([("EUR", "USD"), ("GBP", "USD")])
        extractor = _make_extractor(universe)

        with patch(
            "imdr.domains.fx.extractors_rate.fetch_and_parse_batched",
            side_effect=TagQuotaExceeded("over budget"),
        ) as mock_fetch:
            with pytest.raises(TagQuotaExceeded, match="over budget"):
                extractor.extract(START, END)

        # Only the first pair was attempted before the re-raise.
        assert mock_fetch.call_count == 1
        # Quota-exceeded errors are NOT swallowed into _errors.
        assert extractor.errors == []

    def test_generic_pair_exception_captured_in_errors_loop_continues(self) -> None:
        universe = _make_universe([("EUR", "USD"), ("GBP", "USD")])
        extractor = _make_extractor(universe)

        # First call raises, second returns empty (no rows but no error).
        call_outcomes = [RuntimeError("citi 500"), pd.DataFrame()]

        def _side_effect(*args, **kwargs):
            outcome = call_outcomes.pop(0)
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

        with patch(
            "imdr.domains.fx.extractors_rate.fetch_and_parse_batched",
            side_effect=_side_effect,
        ) as mock_fetch:
            result = extractor.extract(START, END)

        assert mock_fetch.call_count == 2  # loop continued after pair 1 failed
        assert extractor.errors == [{"pair": "EUR/USD", "error": "citi 500"}]
        assert list(result.columns) == WIDE_COLUMNS
        assert result.empty


# ---------------------------------------------------------------------------
# extract — pair filtering + tag composition
# ---------------------------------------------------------------------------


class TestExtractPairFiltering:
    def test_default_pair_list_excludes_bbg_only(self) -> None:
        universe = _make_universe(
            pairs=[("EUR", "USD"), ("USD", "ABC")],
            bbg_only={("USD", "ABC")},
        )
        extractor = _make_extractor(universe)

        with patch(
            "imdr.domains.fx.extractors_rate.fetch_and_parse_batched",
            return_value=pd.DataFrame(),
        ) as mock_fetch:
            extractor.extract(START, END)

        # Only EUR/USD reaches the batched fetcher; ABC pair is filtered.
        assert mock_fetch.call_count == 1
        called_tags = mock_fetch.call_args.args[1]
        assert "FX.SPOT.EUR.USD.CITI" in called_tags
        assert not any("USD.ABC" in t for t in called_tags)

    def test_explicit_pairs_override_default_filter(self) -> None:
        # If `pairs=` is passed, the bbg_only filter is bypassed (caller's choice).
        universe = _make_universe(
            pairs=[("EUR", "USD")],
            bbg_only={("USD", "ABC")},
        )
        extractor = _make_extractor(universe)

        with patch(
            "imdr.domains.fx.extractors_rate.fetch_and_parse_batched",
            return_value=pd.DataFrame(),
        ) as mock_fetch:
            extractor.extract(START, END, pairs=[("USD", "ABC")])

        assert mock_fetch.call_count == 1
        called_tags = mock_fetch.call_args.args[1]
        assert "FX.SPOT.USD.ABC.CITI" in called_tags

    def test_spot_only_pair_emits_only_spot_tag(self) -> None:
        universe = _make_universe(
            pairs=[("USD", "VND")],
            spot_only={("USD", "VND")},
            forward_tenors=["1M", "3M", "6M"],
        )
        extractor = _make_extractor(universe)

        with patch(
            "imdr.domains.fx.extractors_rate.fetch_and_parse_batched",
            return_value=pd.DataFrame(),
        ) as mock_fetch:
            extractor.extract(START, END)

        called_tags = mock_fetch.call_args.args[1]
        assert called_tags == ["FX.SPOT.USD.VND.CITI"]
        # Confirm the outright/point builders were not invoked for this pair.
        universe.build_fx_rate_outright_tags.assert_not_called()
        universe.build_fx_rate_point_tags.assert_not_called()

    def test_non_spot_only_pair_emits_spot_plus_outright_plus_points(self) -> None:
        universe = _make_universe(
            pairs=[("EUR", "USD")],
            forward_tenors=["1M", "3M", "6M"],
        )
        extractor = _make_extractor(universe)

        with patch(
            "imdr.domains.fx.extractors_rate.fetch_and_parse_batched",
            return_value=pd.DataFrame(),
        ) as mock_fetch:
            extractor.extract(START, END)

        called_tags = mock_fetch.call_args.args[1]
        # 1 spot + 3 outright + 3 points = 7 tags
        assert len(called_tags) == 7
        assert called_tags[0] == "FX.SPOT.EUR.USD.CITI"
        assert sum(1 for t in called_tags if "FWD_OUTRIGHT" in t) == 3
        assert sum(1 for t in called_tags if "FWD_POINT" in t) == 3


# ---------------------------------------------------------------------------
# extract — pre-flight quota budget
# ---------------------------------------------------------------------------


class TestPreFlightBudget:
    def test_budget_math_for_mixed_spot_only_and_full(self) -> None:
        # 2 full pairs * (1 spot + 2 * 3 tenors) = 2 * 7 = 14
        # 1 spot-only pair * 1 spot                            = 1
        # Total                                                = 15
        universe = _make_universe(
            pairs=[("EUR", "USD"), ("GBP", "USD"), ("USD", "VND")],
            spot_only={("USD", "VND")},
            forward_tenors=["1M", "3M", "6M"],
        )
        tracker = MagicMock(name="TagQuotaTracker")
        extractor = _make_extractor(universe, quota_tracker=tracker)

        with patch(
            "imdr.domains.fx.extractors_rate.fetch_and_parse_batched",
            return_value=pd.DataFrame(),
        ):
            extractor.extract(START, END)

        tracker.check_budget.assert_called_once_with(15, "fx.citi_rate")

    def test_no_budget_check_when_tracker_is_none(self) -> None:
        universe = _make_universe([("EUR", "USD")])
        extractor = _make_extractor(universe, quota_tracker=None)

        with patch(
            "imdr.domains.fx.extractors_rate.fetch_and_parse_batched",
            return_value=pd.DataFrame(),
        ):
            # Should not raise; budget check is skipped entirely.
            extractor.extract(START, END)


# ---------------------------------------------------------------------------
# extract — pivot integration on populated long frames
# ---------------------------------------------------------------------------


class TestExtractPivot:
    def test_long_frames_concatenated_and_pivoted_to_wide(self) -> None:
        universe = _make_universe([("EUR", "USD")])
        extractor = _make_extractor(universe)

        long_df = pd.DataFrame({
            "ts": [START, START],
            "base_ccy": ["EUR", "EUR"],
            "quote_ccy": ["USD", "USD"],
            "tenor": ["SPOT", "1M"],
            "quote_kind": ["mid_rate", "mid_rate"],
            "numeric": [1.0850, 1.0855],
        })

        with patch(
            "imdr.domains.fx.extractors_rate.fetch_and_parse_batched",
            return_value=long_df,
        ):
            result = extractor.extract(START, END)

        assert list(result.columns) == WIDE_COLUMNS
        assert len(result) == 2  # one row per (pair, tenor)
        assert set(result["tenor"]) == {"SPOT", "1M"}
