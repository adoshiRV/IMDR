"""Tests for `CitiVelocityFXVolExtractor`.

Mirror of test_fx_rate_extractor.py — same Citi-extractor orchestration
shape, different domain. Tests mock `fetch_and_parse_batched` at the
module boundary so the per-pair loop semantics can be exercised without
an HTTP layer.

Covered:
- `__init__` defaults — `errors` and `tag_errors` start empty.
- Empty fetch → `pd.DataFrame(columns=COLUMNS)`.
- `TagQuotaExceeded` is re-raised; remaining pairs are not attempted.
- Generic per-pair exception is captured in `errors`; loop continues.
- `tag_errors` is passed through to `fetch_and_parse_batched` (this is
  the parity fix with the rate extractor — was a silent diagnostic gap
  before).
- Default pair list comes from `universe.vol_pairs()`.
- Pre-flight budget sums tag counts across pairs and uses the exact
  `fx_vol.citi_live` pipeline name.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from imdr.connectors.citi_helpers import TagQuotaExceeded
from imdr.domains.fx.extractors_vol import CitiVelocityFXVolExtractor
from imdr.domains.fx.vol_translate import COLUMNS

UTC = timezone.utc
START = datetime(2026, 5, 1, tzinfo=UTC)
END = datetime(2026, 5, 2, tzinfo=UTC)


def _make_universe(
    pairs: list[tuple[str, str]],
    tags_per_pair: int = 90,
) -> MagicMock:
    """Build a MagicMock FXUniverse exposing only the methods the extractor uses."""
    universe = MagicMock(name="FXUniverse")
    universe.vol_pairs.return_value = pairs
    # Deterministic per-pair tag list of the requested size.
    universe.build_vol_tags.side_effect = lambda c1, c2: [
        f"FX.VOL.{c1}.{c2}.ATM.1M.IMPLIED.CITI" for _ in range(tags_per_pair)
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
) -> CitiVelocityFXVolExtractor:
    return CitiVelocityFXVolExtractor(
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
    def test_empty_fetch_returns_empty_df_with_columns_contract(self) -> None:
        universe = _make_universe([("EUR", "USD")])
        extractor = _make_extractor(universe)

        with patch(
            "imdr.domains.fx.extractors_vol.fetch_and_parse_batched",
            return_value=pd.DataFrame(),
        ) as mock_fetch:
            result = extractor.extract(START, END)

        assert list(result.columns) == COLUMNS
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
            "imdr.domains.fx.extractors_vol.fetch_and_parse_batched",
            side_effect=TagQuotaExceeded("over budget"),
        ) as mock_fetch:
            with pytest.raises(TagQuotaExceeded, match="over budget"):
                extractor.extract(START, END)

        # Only the first pair was attempted before the re-raise.
        assert mock_fetch.call_count == 1
        # Quota-exceeded errors are NOT swallowed into `errors`.
        assert extractor.errors == []

    def test_generic_pair_exception_captured_in_errors_loop_continues(self) -> None:
        universe = _make_universe([("EUR", "USD"), ("GBP", "USD")])
        extractor = _make_extractor(universe)

        call_outcomes = [RuntimeError("citi 500"), pd.DataFrame()]

        def _side_effect(*args, **kwargs):
            outcome = call_outcomes.pop(0)
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

        with patch(
            "imdr.domains.fx.extractors_vol.fetch_and_parse_batched",
            side_effect=_side_effect,
        ) as mock_fetch:
            result = extractor.extract(START, END)

        assert mock_fetch.call_count == 2  # loop continued
        assert extractor.errors == [{"pair": "EUR/USD", "error": "citi 500"}]
        assert list(result.columns) == COLUMNS
        assert result.empty


# ---------------------------------------------------------------------------
# extract — tag_errors plumbing (parity with rate extractor)
# ---------------------------------------------------------------------------


class TestTagErrorsPassthrough:
    def test_tag_errors_list_is_passed_to_fetch_helper(self) -> None:
        """The extractor's `tag_errors` list must be passed by reference into
        `fetch_and_parse_batched` so the helper can populate per-tag ERROR /
        EMPTY entries in-place. Without this, the rate extractor's
        diagnostic surface was missing on vol (a silent diagnostic gap).
        """
        universe = _make_universe([("EUR", "USD")])
        extractor = _make_extractor(universe)

        with patch(
            "imdr.domains.fx.extractors_vol.fetch_and_parse_batched",
            return_value=pd.DataFrame(),
        ) as mock_fetch:
            extractor.extract(START, END)

        # The kwarg must be present and point at the extractor's own list.
        assert mock_fetch.call_args.kwargs["tag_errors"] is extractor.tag_errors

    def test_tag_errors_populated_in_place_by_helper(self) -> None:
        """Verify the in-place population pattern: when the helper writes into
        the passed-in list, the extractor's attribute reflects it without a
        separate copy step."""
        universe = _make_universe([("EUR", "USD")])
        extractor = _make_extractor(universe)

        def _side_effect(*args, **kwargs):
            kwargs["tag_errors"].append({"tag": "FX.VOL.X", "error": "QUOTA"})
            return pd.DataFrame()

        with patch(
            "imdr.domains.fx.extractors_vol.fetch_and_parse_batched",
            side_effect=_side_effect,
        ):
            extractor.extract(START, END)

        assert extractor.tag_errors == [{"tag": "FX.VOL.X", "error": "QUOTA"}]


# ---------------------------------------------------------------------------
# extract — pair list + tag composition
# ---------------------------------------------------------------------------


class TestExtractPairList:
    def test_default_pair_list_comes_from_universe(self) -> None:
        universe = _make_universe([("EUR", "USD"), ("USD", "JPY")])
        extractor = _make_extractor(universe)

        with patch(
            "imdr.domains.fx.extractors_vol.fetch_and_parse_batched",
            return_value=pd.DataFrame(),
        ) as mock_fetch:
            extractor.extract(START, END)

        assert mock_fetch.call_count == 2
        universe.vol_pairs.assert_called_once()

    def test_explicit_pairs_override_default(self) -> None:
        universe = _make_universe([("EUR", "USD")])
        extractor = _make_extractor(universe)

        with patch(
            "imdr.domains.fx.extractors_vol.fetch_and_parse_batched",
            return_value=pd.DataFrame(),
        ) as mock_fetch:
            extractor.extract(START, END, pairs=[("USD", "JPY")])

        # Universe pair-list never queried when caller supplies pairs.
        universe.vol_pairs.assert_not_called()
        assert mock_fetch.call_count == 1
        called_tags = mock_fetch.call_args.args[1]
        assert all("USD.JPY" in t for t in called_tags)


# ---------------------------------------------------------------------------
# extract — pre-flight quota budget
# ---------------------------------------------------------------------------


class TestPreFlightBudget:
    def test_budget_is_sum_of_per_pair_tag_counts(self) -> None:
        # 3 pairs × 90 tags each = 270.
        universe = _make_universe(
            [("EUR", "USD"), ("GBP", "USD"), ("USD", "JPY")],
            tags_per_pair=90,
        )
        tracker = MagicMock(name="TagQuotaTracker")
        extractor = _make_extractor(universe, quota_tracker=tracker)

        with patch(
            "imdr.domains.fx.extractors_vol.fetch_and_parse_batched",
            return_value=pd.DataFrame(),
        ):
            extractor.extract(START, END)

        tracker.check_budget.assert_called_once_with(270, "fx_vol.citi_live")

    def test_no_budget_check_when_tracker_is_none(self) -> None:
        universe = _make_universe([("EUR", "USD")])
        extractor = _make_extractor(universe, quota_tracker=None)

        with patch(
            "imdr.domains.fx.extractors_vol.fetch_and_parse_batched",
            return_value=pd.DataFrame(),
        ):
            # Should not raise; budget check is skipped entirely.
            extractor.extract(START, END)


# ---------------------------------------------------------------------------
# extract — frame concatenation on populated results
# ---------------------------------------------------------------------------


class TestExtractConcatenation:
    def test_multiple_pair_frames_are_concatenated(self) -> None:
        universe = _make_universe([("EUR", "USD"), ("GBP", "USD")])
        extractor = _make_extractor(universe)

        per_pair_df = pd.DataFrame({
            "ts": [START], "base_ccy": ["EUR"], "quote_ccy": ["USD"],
            "strike": ["ATM"], "tenor": ["1M"], "vol_type": ["IMPLIED"],
            "value": [0.085],
        })

        with patch(
            "imdr.domains.fx.extractors_vol.fetch_and_parse_batched",
            return_value=per_pair_df,
        ):
            result = extractor.extract(START, END)

        # Both pair fetches returned 1 row each → 2 rows total in the concat.
        assert len(result) == 2
        assert list(result.columns) == COLUMNS
