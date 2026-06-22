"""Tests for scripts/econ/in/ogd/ogd_food_nowcast.py.

Network-free and DB-free. All OGD fetches are mocked.

`scripts.econ.in` cannot be imported with dotted syntax because `in` is a
Python keyword. The module is loaded via importlib.util instead.

Exercises:
  - focus filtering (non-focus commodity dropped; alias resolves to canonical)
  - hygiene band (modal < 100, > 200000, None are dropped)
  - coverage floor (< 5 distinct markets not emitted)
  - ISO-week grouping + Monday obs_date
  - median correctness (odd count, even count)
  - imdr_code + subgroup slug construction (veg / fruit / spice)
  - erroring day in window does not abort; empty day is skipped gracefully
  - dedup: identical (market, date, variety) rows do not double-count median
  - cross-day weighting: pooled (market, day, variety) produces pinned median
  - empty observations: main()/run_main(allow_empty=True) returns rc=0
"""
from __future__ import annotations

import datetime
import importlib.util
import sys
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Load the module via importlib (avoids `in` keyword in dotted import path)
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[3]
_MOD_PATH = _REPO_ROOT / "scripts" / "econ" / "in" / "ogd" / "ogd_food_nowcast.py"

_spec = importlib.util.spec_from_file_location("ogd_food_nowcast", _MOD_PATH)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["ogd_food_nowcast"] = _mod
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]

run_fetch = _mod.run_fetch
_MIN_MARKETS = _mod._MIN_MARKETS
_PRICE_MIN = _mod._PRICE_MIN
_PRICE_MAX = _mod._PRICE_MAX
_week_monday = _mod._week_monday

# slug is now sourced from upag — import directly for unit tests.
from imdr.domains.econ.upag import slug as _slug

# Patch target prefix for the loaded module.
_PATCH_PREFIX = "ogd_food_nowcast"

UTC = datetime.timezone.utc

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _row(
    date: datetime.date,
    commodity: str,
    market: str,
    modal: Decimal | None,
    state: str = "MH",
    district: str = "PUNE",
    variety: str = "",
) -> dict:
    """Build a normalised ogd_mandi row dict."""
    return {
        "arrival_date": date,
        "state": state,
        "district": district,
        "market": market,
        "commodity": commodity,
        "commodity_code": "TEST",
        "variety": variety,
        "grade": "",
        "min_price": modal,
        "max_price": modal,
        "modal_price": modal,
    }


def _make_session_mock():
    return MagicMock()


# ---------------------------------------------------------------------------
# _week_monday
# ---------------------------------------------------------------------------

class TestWeekMonday:
    def test_week_1_2026(self) -> None:
        # ISO week 1 of 2026: Monday is 2025-12-29
        assert _week_monday(2026, 1) == datetime.date(2025, 12, 29)

    def test_week_24_2026(self) -> None:
        # ISO week 24 of 2026: 2026-06-08 (Monday)
        assert _week_monday(2026, 24) == datetime.date(2026, 6, 8)

    def test_monday_is_day_1(self) -> None:
        result = _week_monday(2026, 25)
        assert result.weekday() == 0  # Monday = 0


# ---------------------------------------------------------------------------
# slug (upag.slug — shared with nowcast)
# ---------------------------------------------------------------------------

class TestSlugify:
    def test_simple(self) -> None:
        assert _slug("Tomato") == "TOMATO"

    def test_parens_and_slash(self) -> None:
        assert _slug("Bhindi(Ladies Finger)") == "BHINDI_LADIES_FINGER"

    def test_special_chars(self) -> None:
        assert _slug("Mango(Raw-Ripe)") == "MANGO_RAW_RIPE"

    def test_uppercase(self) -> None:
        assert _slug("green chilli") == "GREEN_CHILLI"


# ---------------------------------------------------------------------------
# imdr_code construction — pin exact strings for veg / fruit / spice
# ---------------------------------------------------------------------------

class TestImdrCodeConstruction:
    """Verify exact imdr_code strings for one commodity from each sub-group."""

    def _fetch_one_commodity(self, commodity: str, modal: Decimal, n_markets: int):
        """Run run_fetch for a single date with `n_markets` rows for `commodity`."""
        date = datetime.date(2026, 6, 16)  # ISO week 25, 2026

        rows = [
            _row(date, commodity, f"Market{i}", modal)
            for i in range(n_markets)
        ]

        with (
            patch(f"{_PATCH_PREFIX}.load_key", return_value="FAKEKEY"),
            patch(f"{_PATCH_PREFIX}.make_session", return_value=_make_session_mock()),
            patch(f"{_PATCH_PREFIX}.fetch_date", return_value=(rows, 1)),
        ):
            indicators, observations = run_fetch("2026-06-16", "2026-06-16")
        return indicators, observations

    def test_vegetable_imdr_code(self) -> None:
        inds, obs = self._fetch_one_commodity("Tomato", Decimal("1500"), _MIN_MARKETS)
        assert len(inds) == 1
        assert inds[0].imdr_code == "INDIA.FOODNOWCAST.VEG.TOMATO.MEDIAN_WK.NATL.IN"

    def test_fruit_imdr_code(self) -> None:
        inds, obs = self._fetch_one_commodity("Banana", Decimal("2500"), _MIN_MARKETS)
        assert len(inds) == 1
        assert inds[0].imdr_code == "INDIA.FOODNOWCAST.FRUIT.BANANA.MEDIAN_WK.NATL.IN"

    def test_spice_imdr_code(self) -> None:
        inds, obs = self._fetch_one_commodity("Garlic", Decimal("8000"), _MIN_MARKETS)
        assert len(inds) == 1
        assert inds[0].imdr_code == "INDIA.FOODNOWCAST.SPICE.GARLIC.MEDIAN_WK.NATL.IN"

    def test_complex_slug_vegetable(self) -> None:
        inds, obs = self._fetch_one_commodity("Bhindi(Ladies Finger)", Decimal("2000"), _MIN_MARKETS)
        assert len(inds) == 1
        assert inds[0].imdr_code == "INDIA.FOODNOWCAST.VEG.BHINDI_LADIES_FINGER.MEDIAN_WK.NATL.IN"


# ---------------------------------------------------------------------------
# Focus filtering
# ---------------------------------------------------------------------------

class TestFocusFiltering:
    def _fetch(self, rows: list[dict]):
        with (
            patch(f"{_PATCH_PREFIX}.load_key", return_value="FAKEKEY"),
            patch(f"{_PATCH_PREFIX}.make_session", return_value=_make_session_mock()),
            patch(f"{_PATCH_PREFIX}.fetch_date", return_value=(rows, 1)),
        ):
            return run_fetch("2026-06-16", "2026-06-16")

    def test_non_focus_commodity_dropped(self) -> None:
        date = datetime.date(2026, 6, 16)
        rows = [_row(date, "Wood", f"M{i}", Decimal("500")) for i in range(10)]
        inds, obs = self._fetch(rows)
        assert len(inds) == 0
        assert len(obs) == 0

    def test_excluded_commodity_dropped(self) -> None:
        # Wheat is in EXCLUDE (grain), not FOCUS
        date = datetime.date(2026, 6, 16)
        rows = [_row(date, "Wheat", f"M{i}", Decimal("2000")) for i in range(10)]
        inds, obs = self._fetch(rows)
        assert len(inds) == 0

    def test_alias_resolves_and_kept(self) -> None:
        # "Ladies Finger" is an alias for "Bhindi(Ladies Finger)"
        date = datetime.date(2026, 6, 16)
        rows = [_row(date, "Ladies Finger", f"M{i}", Decimal("2000")) for i in range(_MIN_MARKETS)]
        inds, obs = self._fetch(rows)
        assert len(inds) == 1
        assert "BHINDI_LADIES_FINGER" in inds[0].imdr_code

    def test_focus_canonical_kept(self) -> None:
        date = datetime.date(2026, 6, 16)
        rows = [_row(date, "Onion", f"M{i}", Decimal("1500")) for i in range(_MIN_MARKETS)]
        inds, obs = self._fetch(rows)
        assert len(inds) == 1
        assert "ONION" in inds[0].imdr_code


# ---------------------------------------------------------------------------
# Hygiene band
# ---------------------------------------------------------------------------

class TestHygieneBand:
    def _fetch_rows(self, rows: list[dict]):
        with (
            patch(f"{_PATCH_PREFIX}.load_key", return_value="FAKEKEY"),
            patch(f"{_PATCH_PREFIX}.make_session", return_value=_make_session_mock()),
            patch(f"{_PATCH_PREFIX}.fetch_date", return_value=(rows, 1)),
        ):
            return run_fetch("2026-06-16", "2026-06-16")

    def test_modal_none_dropped(self) -> None:
        date = datetime.date(2026, 6, 16)
        rows = [_row(date, "Tomato", f"M{i}", None) for i in range(_MIN_MARKETS + 2)]
        inds, obs = self._fetch_rows(rows)
        assert len(obs) == 0

    def test_modal_below_100_dropped(self) -> None:
        date = datetime.date(2026, 6, 16)
        rows = [_row(date, "Tomato", f"M{i}", Decimal("0.66")) for i in range(_MIN_MARKETS + 2)]
        inds, obs = self._fetch_rows(rows)
        assert len(obs) == 0

    def test_modal_exactly_100_kept(self) -> None:
        # Spec: "drop where modal_price < 100" — 100 itself passes.
        date = datetime.date(2026, 6, 16)
        rows = [_row(date, "Tomato", f"M{i}", Decimal("100")) for i in range(_MIN_MARKETS)]
        inds, obs = self._fetch_rows(rows)
        assert len(obs) == 1

    def test_modal_99_dropped(self) -> None:
        date = datetime.date(2026, 6, 16)
        rows = [_row(date, "Tomato", f"M{i}", Decimal("99")) for i in range(_MIN_MARKETS + 2)]
        inds, obs = self._fetch_rows(rows)
        assert len(obs) == 0

    def test_modal_above_200000_dropped(self) -> None:
        date = datetime.date(2026, 6, 16)
        rows = [_row(date, "Tomato", f"M{i}", Decimal("200001")) for i in range(_MIN_MARKETS + 2)]
        inds, obs = self._fetch_rows(rows)
        assert len(obs) == 0

    def test_modal_exactly_200000_kept(self) -> None:
        date = datetime.date(2026, 6, 16)
        rows = [_row(date, "Tomato", f"M{i}", Decimal("200000")) for i in range(_MIN_MARKETS)]
        inds, obs = self._fetch_rows(rows)
        assert len(obs) == 1

    def test_valid_modal_kept(self) -> None:
        date = datetime.date(2026, 6, 16)
        rows = [_row(date, "Tomato", f"M{i}", Decimal("1500")) for i in range(_MIN_MARKETS)]
        inds, obs = self._fetch_rows(rows)
        assert len(obs) == 1


# ---------------------------------------------------------------------------
# Coverage floor
# ---------------------------------------------------------------------------

class TestCoverageFloor:
    def _fetch_rows(self, rows: list[dict]):
        with (
            patch(f"{_PATCH_PREFIX}.load_key", return_value="FAKEKEY"),
            patch(f"{_PATCH_PREFIX}.make_session", return_value=_make_session_mock()),
            patch(f"{_PATCH_PREFIX}.fetch_date", return_value=(rows, 1)),
        ):
            return run_fetch("2026-06-16", "2026-06-16")

    def test_below_floor_not_emitted(self) -> None:
        date = datetime.date(2026, 6, 16)
        # 4 distinct markets — below _MIN_MARKETS = 5
        rows = [_row(date, "Tomato", f"M{i}", Decimal("1500")) for i in range(_MIN_MARKETS - 1)]
        inds, obs = self._fetch_rows(rows)
        assert len(obs) == 0

    def test_exactly_at_floor_emitted(self) -> None:
        date = datetime.date(2026, 6, 16)
        rows = [_row(date, "Tomato", f"M{i}", Decimal("1500")) for i in range(_MIN_MARKETS)]
        inds, obs = self._fetch_rows(rows)
        assert len(obs) == 1

    def test_duplicate_market_counted_once(self) -> None:
        # Same market name repeated — should count as 1 distinct market.
        date = datetime.date(2026, 6, 16)
        rows = [_row(date, "Tomato", "SAME_MARKET", Decimal("1500")) for _ in range(10)]
        inds, obs = self._fetch_rows(rows)
        assert len(obs) == 0  # only 1 distinct market < 5


# ---------------------------------------------------------------------------
# ISO-week grouping + Monday obs_date
# ---------------------------------------------------------------------------

class TestIsoWeekGrouping:
    def test_obs_date_is_monday(self) -> None:
        # All rows across Mon-Sun of week 24 should collapse to one obs_date = Mon
        rows = []
        for d_offset in range(7):  # 2026-06-08 (Mon) to 2026-06-14 (Sun)
            date = datetime.date(2026, 6, 8) + datetime.timedelta(days=d_offset)
            for i in range(_MIN_MARKETS):
                rows.append(_row(date, "Tomato", f"M{i}_{d_offset}", Decimal("1500")))

        def mock_fetch(session, key, date, **kw):
            day_rows = [r for r in rows if r["arrival_date"] == date]
            return (day_rows, 1)

        with (
            patch(f"{_PATCH_PREFIX}.load_key", return_value="FAKEKEY"),
            patch(f"{_PATCH_PREFIX}.make_session", return_value=_make_session_mock()),
            patch(f"{_PATCH_PREFIX}.fetch_date", side_effect=mock_fetch),
        ):
            inds, obs = run_fetch("2026-06-08", "2026-06-14")

        assert len(obs) == 1
        assert obs[0].obs_date.weekday() == 0  # Monday

    def test_two_weeks_produce_two_obs(self) -> None:
        # Week 24 (2026-06-10) and week 25 (2026-06-17)
        rows_w24 = [
            _row(datetime.date(2026, 6, 10), "Tomato", f"M{i}", Decimal("1500"))
            for i in range(_MIN_MARKETS)
        ]
        rows_w25 = [
            _row(datetime.date(2026, 6, 17), "Tomato", f"M{i}", Decimal("1600"))
            for i in range(_MIN_MARKETS)
        ]

        all_rows_by_date = {
            datetime.date(2026, 6, 10): rows_w24,
            datetime.date(2026, 6, 17): rows_w25,
        }

        def mock_fetch(session, key, date, **kw):
            return (all_rows_by_date.get(date, []), 1)

        with (
            patch(f"{_PATCH_PREFIX}.load_key", return_value="FAKEKEY"),
            patch(f"{_PATCH_PREFIX}.make_session", return_value=_make_session_mock()),
            patch(f"{_PATCH_PREFIX}.fetch_date", side_effect=mock_fetch),
        ):
            inds, obs = run_fetch("2026-06-10", "2026-06-17")

        tomato_obs = [o for o in obs if "TOMATO" in o.imdr_code]
        assert len(tomato_obs) == 2
        dates = sorted(o.obs_date for o in tomato_obs)
        assert dates[0].weekday() == 0  # both Mondays
        assert dates[1].weekday() == 0


# ---------------------------------------------------------------------------
# Median correctness
# ---------------------------------------------------------------------------

class TestMedianCorrectness:
    def _fetch_with_prices(self, prices: list[int]) -> list:
        date = datetime.date(2026, 6, 16)
        rows = [
            _row(date, "Tomato", f"M{i}", Decimal(str(p)))
            for i, p in enumerate(prices)
        ]
        with (
            patch(f"{_PATCH_PREFIX}.load_key", return_value="FAKEKEY"),
            patch(f"{_PATCH_PREFIX}.make_session", return_value=_make_session_mock()),
            patch(f"{_PATCH_PREFIX}.fetch_date", return_value=(rows, 1)),
        ):
            _, obs = run_fetch("2026-06-16", "2026-06-16")
        return obs

    def test_odd_count_median(self) -> None:
        # 5 values: median is middle value
        prices = [1000, 1200, 1500, 1800, 2000]  # median = 1500
        obs = self._fetch_with_prices(prices)
        assert len(obs) == 1
        assert obs[0].value == pytest.approx(1500.0)

    def test_even_count_median(self) -> None:
        # 6 values: median is average of two middle values
        prices = [1000, 1200, 1500, 1600, 1800, 2000]  # median = (1500+1600)/2 = 1550
        obs = self._fetch_with_prices(prices)
        assert len(obs) == 1
        assert obs[0].value == pytest.approx(1550.0)

    def test_median_robust_to_high_outlier_within_band(self) -> None:
        # One high value within band; median (1200) is not pulled toward it.
        prices = [1000, 1100, 1200, 1300, 150000]  # median = 1200
        obs = self._fetch_with_prices(prices)
        assert len(obs) == 1
        assert obs[0].value == pytest.approx(1200.0)


# ---------------------------------------------------------------------------
# Error / empty day in window does not abort
# ---------------------------------------------------------------------------

class TestWindowResilience:
    def test_error_day_skipped(self) -> None:
        # Day 1: raises, Day 2: returns valid rows.
        date1 = datetime.date(2026, 6, 15)
        date2 = datetime.date(2026, 6, 16)

        rows_d2 = [_row(date2, "Tomato", f"M{i}", Decimal("1500")) for i in range(_MIN_MARKETS)]

        def mock_fetch(session, key, date, **kw):
            if date == date1:
                raise RuntimeError("OGD API connection failed")
            return (rows_d2, 1)

        with (
            patch(f"{_PATCH_PREFIX}.load_key", return_value="FAKEKEY"),
            patch(f"{_PATCH_PREFIX}.make_session", return_value=_make_session_mock()),
            patch(f"{_PATCH_PREFIX}.fetch_date", side_effect=mock_fetch),
        ):
            inds, obs = run_fetch("2026-06-15", "2026-06-16")

        # Second day's data should still land.
        assert len(obs) == 1
        assert obs[0].obs_date.weekday() == 0  # Monday

    def test_empty_day_skipped(self) -> None:
        date1 = datetime.date(2026, 6, 15)
        date2 = datetime.date(2026, 6, 16)

        rows_d2 = [_row(date2, "Tomato", f"M{i}", Decimal("1500")) for i in range(_MIN_MARKETS)]

        def mock_fetch(session, key, date, **kw):
            if date == date1:
                return ([], 1)  # empty — data lag
            return (rows_d2, 1)

        with (
            patch(f"{_PATCH_PREFIX}.load_key", return_value="FAKEKEY"),
            patch(f"{_PATCH_PREFIX}.make_session", return_value=_make_session_mock()),
            patch(f"{_PATCH_PREFIX}.fetch_date", side_effect=mock_fetch),
        ):
            inds, obs = run_fetch("2026-06-15", "2026-06-16")

        assert len(obs) == 1

    def test_all_days_empty_returns_no_obs(self) -> None:
        with (
            patch(f"{_PATCH_PREFIX}.load_key", return_value="FAKEKEY"),
            patch(f"{_PATCH_PREFIX}.make_session", return_value=_make_session_mock()),
            patch(f"{_PATCH_PREFIX}.fetch_date", return_value=([], 1)),
        ):
            inds, obs = run_fetch("2026-06-14", "2026-06-16")

        assert len(obs) == 0
        assert len(inds) == 0


# ---------------------------------------------------------------------------
# T1. Errored day after a prior good day: error contributes 0 obs; good data intact
# ---------------------------------------------------------------------------

class TestWindowResilienceWithError:
    """T1: a day whose fetch raises AFTER a prior good day — no partial bias."""

    def test_errored_day_contributes_zero_obs_good_day_intact(self) -> None:
        date_good = datetime.date(2026, 6, 16)  # week 25
        date_bad = datetime.date(2026, 6, 17)   # same week — raises

        rows_good = [
            _row(date_good, "Tomato", f"M{i}", Decimal("1500"))
            for i in range(_MIN_MARKETS)
        ]

        def mock_fetch(session, key, date, **kw):
            if date == date_bad:
                raise RuntimeError("OGD API connection failed after 4 attempts")
            if date == date_good:
                return (rows_good, 1)
            return ([], 1)

        with (
            patch(f"{_PATCH_PREFIX}.load_key", return_value="FAKEKEY"),
            patch(f"{_PATCH_PREFIX}.make_session", return_value=_make_session_mock()),
            patch(f"{_PATCH_PREFIX}.fetch_date", side_effect=mock_fetch),
        ):
            inds, obs = run_fetch("2026-06-16", "2026-06-17")

        # Good day's data must survive; errored day contributes nothing.
        assert len(obs) == 1
        assert obs[0].obs_date.weekday() == 0  # Monday
        # Median should reflect only the good day's uniform price (1500).
        assert obs[0].value == pytest.approx(1500.0)


# ---------------------------------------------------------------------------
# T2. Duplicate identical source rows do not skew the median
# ---------------------------------------------------------------------------

class TestDedupBeforeMedian:
    """T2: (market, date, variety) dedup — identical rows must not double-count."""

    def test_duplicate_rows_do_not_shift_median(self) -> None:
        # Without dedup: [1000, 1000, 1000, 1000, 1000, 9000] → median = 1000
        # With dedup on (M0, date, ""):   bucket = [1000, 9000] → median = 5000
        # We want dedup: the M0 duplicate rows collapse to one price point (1000).
        date = datetime.date(2026, 6, 16)
        rows = (
            # M0 repeated 5 times with price 1000 → should dedup to one 1000 entry
            [_row(date, "Tomato", "M0", Decimal("1000")) for _ in range(5)]
            # M1..M4 each once with prices that would shift median if M0 counted 5x
            + [_row(date, "Tomato", "M1", Decimal("1100"))]
            + [_row(date, "Tomato", "M2", Decimal("1200"))]
            + [_row(date, "Tomato", "M3", Decimal("1300"))]
            + [_row(date, "Tomato", "M4", Decimal("1400"))]
        )
        # After dedup: prices = [1000, 1100, 1200, 1300, 1400] → median = 1200
        # Without dedup: prices = [1000,1000,1000,1000,1000, 1100,1200,1300,1400] → median = 1100
        # If we see 1200, dedup is working; if we see 1100, it's not.

        with (
            patch(f"{_PATCH_PREFIX}.load_key", return_value="FAKEKEY"),
            patch(f"{_PATCH_PREFIX}.make_session", return_value=_make_session_mock()),
            patch(f"{_PATCH_PREFIX}.fetch_date", return_value=(rows, 1)),
        ):
            _, obs = run_fetch("2026-06-16", "2026-06-16")

        assert len(obs) == 1
        assert obs[0].value == pytest.approx(1200.0), (
            f"Expected 1200.0 (deduped), got {obs[0].value} (likely 1100.0 = no dedup)"
        )

    def test_distinct_varieties_same_market_are_separate_price_points(self) -> None:
        # Two varieties at the same market/day are legitimate distinct signals.
        date = datetime.date(2026, 6, 16)
        # 5 distinct markets; M0 has variety A (1000) and variety B (2000) — both kept.
        rows = (
            [_row(date, "Tomato", "M0", Decimal("1000"), variety="A")]
            + [_row(date, "Tomato", "M0", Decimal("2000"), variety="B")]
            + [_row(date, "Tomato", "M1", Decimal("1500"))]
            + [_row(date, "Tomato", "M2", Decimal("1500"))]
            + [_row(date, "Tomato", "M3", Decimal("1500"))]
            + [_row(date, "Tomato", "M4", Decimal("1500"))]
        )
        # prices = [1000, 2000, 1500, 1500, 1500, 1500] → sorted [1000,1500,1500,1500,1500,2000]
        # median = (1500+1500)/2 = 1500
        with (
            patch(f"{_PATCH_PREFIX}.load_key", return_value="FAKEKEY"),
            patch(f"{_PATCH_PREFIX}.make_session", return_value=_make_session_mock()),
            patch(f"{_PATCH_PREFIX}.fetch_date", return_value=(rows, 1)),
        ):
            _, obs = run_fetch("2026-06-16", "2026-06-16")

        assert len(obs) == 1
        assert obs[0].value == pytest.approx(1500.0)


# ---------------------------------------------------------------------------
# T3. Cross-day weighting: pinned median for known multi-day input
# ---------------------------------------------------------------------------

class TestCrossDayMedian:
    """T3: pooled (market, day, variety) behavior — exact median value pinned."""

    def test_multi_day_pooled_median(self) -> None:
        # Day 1 (Mon): 5 markets, prices [1000, 1100, 1200, 1300, 1400]
        # Day 2 (Tue): 5 new markets, prices [2000, 2100, 2200, 2300, 2400]
        # Pooled sorted: [1000,1100,1200,1300,1400,2000,2100,2200,2300,2400]
        # median of 10 values = (1400+2000)/2 = 1700.0
        date1 = datetime.date(2026, 6, 15)  # week 25
        date2 = datetime.date(2026, 6, 16)  # same week

        rows_d1 = [
            _row(date1, "Tomato", f"D1M{i}", Decimal(str(1000 + i * 100)))
            for i in range(5)
        ]
        rows_d2 = [
            _row(date2, "Tomato", f"D2M{i}", Decimal(str(2000 + i * 100)))
            for i in range(5)
        ]

        all_rows = {date1: rows_d1, date2: rows_d2}

        def mock_fetch(session, key, date, **kw):
            return (all_rows.get(date, []), 1)

        with (
            patch(f"{_PATCH_PREFIX}.load_key", return_value="FAKEKEY"),
            patch(f"{_PATCH_PREFIX}.make_session", return_value=_make_session_mock()),
            patch(f"{_PATCH_PREFIX}.fetch_date", side_effect=mock_fetch),
        ):
            _, obs = run_fetch("2026-06-15", "2026-06-16")

        tomato_obs = [o for o in obs if "TOMATO" in o.imdr_code]
        assert len(tomato_obs) == 1
        assert tomato_obs[0].value == pytest.approx(1700.0)


# ---------------------------------------------------------------------------
# T4. Empty observations → allow_empty=True returns rc=0
# ---------------------------------------------------------------------------

class TestAllowEmpty:
    """T4: run_main with allow_empty=True must return 0 on empty observations."""

    def test_empty_obs_allow_empty_true_returns_zero(self, monkeypatch, tmp_path) -> None:
        from scripts.econ._runner import run_main

        def fetch_empty(since, until):
            return [], []

        # Patch sys.argv so argparse doesn't pick up pytest args.
        monkeypatch.setattr("sys.argv", ["runner", "--no-parquet"])

        rc = run_main(
            vendor="ogd",
            topic="food_nowcast",
            fetch_fn=fetch_empty,
            country_code="IN",
            allow_empty=True,
        )
        assert rc == 0, f"Expected rc=0 with allow_empty=True, got rc={rc}"

    def test_empty_obs_allow_empty_false_returns_one(self, monkeypatch, tmp_path) -> None:
        from scripts.econ._runner import run_main

        def fetch_empty(since, until):
            return [], []

        monkeypatch.setattr("sys.argv", ["runner", "--no-parquet"])

        rc = run_main(
            vendor="ogd",
            topic="food_nowcast",
            fetch_fn=fetch_empty,
            country_code="IN",
            allow_empty=False,
        )
        assert rc == 1, f"Expected rc=1 with allow_empty=False, got rc={rc}"
