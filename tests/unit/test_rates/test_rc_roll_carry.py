"""Roll-carry: one request family, three storage quotes.

Regression cover for the defect found 2026-10-14 — `rc` was classed as a
single-tenor quote, so build_tags emitted `{prefix}.ROLL_CARRY.{tenor}` while
the real tag is `{prefix}.ROLL_CARRY.{HORIZON}.{FWD_START}.{TENOR}.{MEASURE}`.
The emitted tag could never resolve, and `rc` produced ZERO rows across all
59 curves from inception despite sitting in pipelines.yml default_quotes.

These tests pin the shape, the 1x quota cost, and the fan-out on parse.
"""
from __future__ import annotations

import pytest

from imdr.domains.rates.schema import (
    MULTI_TENOR_LEGS,
    QUOTE_TO_CITI,
    RC_MEASURE_TO_QUOTE,
    RC_QUOTES,
    SINGLE_TENOR_QUOTES,
    quote_to_citi,
    validate_quote,
)
from imdr.domains.rates.translate import citi_tag_to_internal
from imdr.universe.rates import get_rates_universe


@pytest.fixture(scope="module")
def universe():
    return get_rates_universe()


class TestTagShape:
    def test_rc_is_not_single_tenor(self) -> None:
        """The original defect: 'rc' sat in SINGLE_TENOR_QUOTES, which is what
        made build_tags emit an unresolvable 2-segment tail."""
        assert "rc" not in SINGLE_TENOR_QUOTES
        assert MULTI_TENOR_LEGS["rc"] == 3

    def test_built_tags_carry_four_trailing_segments(self, universe) -> None:
        tags = universe.build_tags("IDR", "JIBOR", "ROLL_CARRY")
        assert tags
        for t in tags:
            tail = t.split(".")[4:]  # after RATES.SWAP_LIBOR.IDR.ROLL_CARRY
            assert len(tail) == 4, t
            assert tail[-1] in RC_MEASURE_TO_QUOTE, t

    def test_every_combo_emits_all_three_measures(self, universe) -> None:
        """One 'rc' request must return all three measures, so the tag-quota
        cost stays 1x. Requesting per-measure would pay three times over."""
        tags = universe.build_tags("IDR", "JIBOR", "ROLL_CARRY")
        legs = {".".join(t.split(".")[4:7]) for t in tags}
        assert len(tags) == len(legs) * 3

    def test_spot_start_is_preserved_not_parsed_as_a_tenor(self, universe) -> None:
        """FWD_START legitimately takes the literal 'SPOT'; a tenor regex
        would silently drop every spot-starting combo."""
        tags = universe.build_tags("IDR", "JIBOR", "ROLL_CARRY")
        assert any(".SPOT." in t for t in tags)


class TestParseFanOut:
    def test_measure_selects_the_storage_quote(self, universe) -> None:
        base = "RATES.SWAP_LIBOR.IDR.ROLL_CARRY.3M.SPOT.10Y"
        for measure, quote in RC_MEASURE_TO_QUOTE.items():
            parsed = citi_tag_to_internal(f"{base}.{measure}", universe)
            assert parsed is not None, measure
            assert parsed["quote"] == quote
            # The measure moves into the quote; the tenor keeps only the legs.
            assert parsed["tenor"] == "3M.SPOT.10Y"
            assert parsed["ccy"] == "IDR"

    def test_unknown_measure_is_rejected(self, universe) -> None:
        assert citi_tag_to_internal(
            "RATES.SWAP_LIBOR.IDR.ROLL_CARRY.3M.SPOT.10Y.NONSENSE", universe
        ) is None

    def test_wrong_segment_count_is_rejected(self, universe) -> None:
        """The pre-fix tag shape must not parse as something plausible."""
        assert citi_tag_to_internal(
            "RATES.SWAP_LIBOR.IDR.ROLL_CARRY.10Y", universe
        ) is None

    def test_round_trip_every_built_tag(self, universe) -> None:
        tags = universe.build_tags("IDR", "JIBOR", "ROLL_CARRY")
        by_quote: dict[str, int] = {}
        for t in tags:
            parsed = citi_tag_to_internal(t, universe)
            assert parsed is not None, t
            by_quote[parsed["quote"]] = by_quote.get(parsed["quote"], 0) + 1
        assert set(by_quote) == set(RC_QUOTES)
        assert len(set(by_quote.values())) == 1  # evenly split across measures

    def test_storage_tenor_fits_the_column(self, universe) -> None:
        """rates.fact_observation.tenor is VARCHAR(30), quote is VARCHAR(10)."""
        for t in universe.build_tags("IDR", "JIBOR", "ROLL_CARRY"):
            parsed = citi_tag_to_internal(t, universe)
            assert len(parsed["tenor"]) <= 30
            assert len(parsed["quote"]) <= 10


class TestQuoteCodes:
    def test_storage_codes_validate(self) -> None:
        for q in RC_QUOTES:
            assert validate_quote(q) == q

    def test_storage_codes_are_not_requestable(self) -> None:
        """All three come back from ONE 'rc' request, so asking for a tag by
        storage code is a bug rather than something to map onto ROLL_CARRY."""
        for q in RC_QUOTES:
            with pytest.raises(ValueError, match="storage-only"):
                quote_to_citi(q)

    def test_rc_family_still_requestable(self) -> None:
        assert quote_to_citi("rc") == "ROLL_CARRY"
        assert QUOTE_TO_CITI["rc"] == "ROLL_CARRY"


class TestOtherFamiliesUnaffected:
    """The fix touches shared translate/build code used by all 59 curves."""

    @pytest.mark.parametrize(
        "citi_qt,expected_legs",
        [("FWD", 2), ("CURVES", 2), ("BFLY", 3)],
    )
    def test_multi_tenor_families_keep_their_shape(
        self, universe, citi_qt: str, expected_legs: int
    ) -> None:
        tags = universe.build_tags("IDR", "JIBOR", citi_qt)
        assert tags
        for t in tags:
            assert len(t.split(".")[4:]) == expected_legs, t

    def test_par_and_bfly_still_parse(self, universe) -> None:
        assert citi_tag_to_internal("RATES.OIS.USD_SOFR.PAR.10Y", universe) == {
            "ccy": "USD", "curve": "SOFR", "quote": "par", "tenor": "10Y",
        }
        assert citi_tag_to_internal(
            "RATES.SWAP_LIBOR.IDR.BFLY.2Y.5Y.10Y", universe
        ) == {
            "ccy": "IDR", "curve": "JIBOR", "quote": "bfly", "tenor": "2Y.5Y.10Y",
        }
