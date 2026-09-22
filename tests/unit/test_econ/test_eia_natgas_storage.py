"""Tests for scripts/econ/us/eia/eia_natgas_storage.py.

No real network calls — EiaClient is monkeypatched at the fetcher's import site.

Covered:
- All eight storage series are requested in ONE fetch_series call, as a list
  facet, at weekly frequency.
- A mixed-series response is split into the right per-series observations.
- Indicator metadata is correct: unit 'bcf' (migration 131), WEEKLY, energy, US.
- `until` clips the window; `since` is passed through as start_period.
- A PARTIAL response (1-7 series missing) raises — EIA renamed or retired a
  series id, and letting the survivors through would leave the rest silently
  stale behind a rc=0.
- An ENTIRELY empty response does not raise here; run_main fails it on zero
  observations instead.
- Sentinel and non-numeric values become NULL rather than aborting the run.
- Malformed periods are skipped.

Every test supplies rows for all eight series (see `_baseline`) unless it is
specifically exercising the partial/empty guard.
"""

from __future__ import annotations

import datetime
from unittest.mock import MagicMock, patch

import pytest

from scripts.econ.us.eia import eia_natgas_storage as mod


L48 = "NW2_EPG0_SWO_R48_BCF"
EAST = "NW2_EPG0_SWO_R31_BCF"
SALT = "NW2_EPG0_SSO_R33_BCF"

BASE_PERIOD = "2020-01-03"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _row(series: str, period: str, value) -> dict:
    return {"period": period, "series": series, "value": value, "units": "BCF"}


def _baseline(exclude: tuple[str, ...] = ()) -> list[dict]:
    """One row per storage series, so the partial-response guard stays quiet.

    Pass `exclude` to leave a series out of the baseline when the test wants to
    supply that series' rows itself.
    """
    return [
        _row(sid, BASE_PERIOD, 100)
        for sid in mod._SERIES
        if sid not in exclude
    ]


def _patch_client(rows: list[dict]) -> tuple[MagicMock, object]:
    """Patch EiaClient so `with EiaClient() as c: c.fetch_series(...)` yields `rows`.

    Returns the inner client mock (to assert on the call) and the patcher.
    """
    client = MagicMock()
    client.fetch_series.return_value = rows
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=client)
    ctx.__exit__ = MagicMock(return_value=False)
    return client, patch.object(mod, "EiaClient", return_value=ctx)


def _by_code(observations) -> dict[str, list]:
    out: dict[str, list] = {}
    for o in observations:
        out.setdefault(o.imdr_code, []).append(o)
    return out


# ---------------------------------------------------------------------------
# Request shape
# ---------------------------------------------------------------------------

class TestRequestShape:
    def test_single_call_with_all_eight_series_as_list_facet(self) -> None:
        client, p = _patch_client(_baseline())
        with p:
            mod.run_fetch(since=None, until=None)

        assert client.fetch_series.call_count == 1
        args, kwargs = client.fetch_series.call_args
        assert args[0] == "natural-gas/stor/wkly"
        assert kwargs["frequency"] == "weekly"
        series = kwargs["facets"]["series"]
        assert isinstance(series, list)
        assert len(series) == 8
        assert set(series) == set(mod._SERIES)

    def test_since_is_passed_as_start_period(self) -> None:
        client, p = _patch_client(_baseline())
        with p:
            mod.run_fetch(since="2019-01-01", until=None)
        assert client.fetch_series.call_args.kwargs["start_period"] == "2019-01-01"

    def test_default_start_used_when_since_is_none(self) -> None:
        client, p = _patch_client(_baseline())
        with p:
            mod.run_fetch(since=None, until=None)
        assert client.fetch_series.call_args.kwargs["start_period"] == mod._DEFAULT_START


# ---------------------------------------------------------------------------
# Series splitting + metadata
# ---------------------------------------------------------------------------

class TestSeriesSplitting:
    def test_mixed_response_splits_by_series(self) -> None:
        rows = _baseline() + [
            _row(L48, "2026-09-04", 3254),
            _row(EAST, "2026-09-04", 773),
            _row(L48, "2026-09-11", 3298),
            _row(EAST, "2026-09-11", 795),
            _row(SALT, "2026-09-11", 222),
        ]
        _, p = _patch_client(rows)
        with p:
            indicators, observations = mod.run_fetch(since=None, until=None)

        assert len(indicators) == 8
        by_code = _by_code(observations)
        # 1 baseline row each, plus the extras above.
        assert len(by_code["EIA.NATGAS.STORAGE_L48.US"]) == 3
        assert len(by_code["EIA.NATGAS.STORAGE_EAST.US"]) == 3
        assert len(by_code["EIA.NATGAS.STORAGE_SOUTH_CENTRAL_SALT.US"]) == 2
        assert len(by_code["EIA.NATGAS.STORAGE_PACIFIC.US"]) == 1

        latest = [
            o for o in by_code["EIA.NATGAS.STORAGE_L48.US"]
            if o.obs_date == datetime.date(2026, 9, 11)
        ][0]
        assert latest.value == 3298.0
        assert latest.vintage == 0

    def test_indicator_metadata(self) -> None:
        _, p = _patch_client(_baseline())
        with p:
            indicators, _ = mod.run_fetch(since=None, until=None)

        ind = [i for i in indicators if i.source_code == L48][0]
        assert ind.imdr_code == "EIA.NATGAS.STORAGE_L48.US"
        assert ind.vendor_name == "EIA"
        # 'bcf' must exist in dbo.dim_unit (migration 131) or the loader
        # aborts the whole parquet pair with rc=2 -- nothing loads at all.
        assert ind.unit == "bcf"
        assert ind.frequency == "WEEKLY"
        assert ind.country_iso == "US"
        assert ind.category == "energy"
        assert ind.is_seasonally_adjusted is False

    def test_every_mapped_series_has_a_distinct_code(self) -> None:
        codes = [code for code, _ in mod._SERIES.values()]
        assert len(codes) == len(set(codes)) == 8

    def test_unknown_series_id_is_ignored(self) -> None:
        rows = _baseline() + [_row("NOT_A_SERIES", BASE_PERIOD, 1)]
        _, p = _patch_client(rows)
        with p:
            indicators, observations = mod.run_fetch(since=None, until=None)

        assert len(indicators) == 8
        assert len(observations) == 8


# ---------------------------------------------------------------------------
# Partial / empty response guard
# ---------------------------------------------------------------------------

class TestPartialResponseGuard:
    def test_one_missing_series_raises(self) -> None:
        """EAST vanishes — a renamed/retired id, not a quiet week."""
        _, p = _patch_client(_baseline(exclude=(EAST,)))
        with p:
            with pytest.raises(RuntimeError, match=r"1/8 storage series"):
                mod.run_fetch(since=None, until=None)

    def test_error_names_the_missing_series(self) -> None:
        _, p = _patch_client(_baseline(exclude=(EAST, SALT)))
        with p:
            with pytest.raises(RuntimeError) as exc:
                mod.run_fetch(since=None, until=None)
        msg = str(exc.value)
        assert EAST in msg and SALT in msg
        assert "2/8" in msg

    def test_only_l48_surviving_raises(self) -> None:
        """The exact silent-staleness case: run_main's emptiness gate would pass."""
        _, p = _patch_client([_row(L48, BASE_PERIOD, 3000)])
        with p:
            with pytest.raises(RuntimeError, match=r"7/8 storage series"):
                mod.run_fetch(since=None, until=None)

    def test_entirely_empty_response_does_not_raise(self) -> None:
        """All eight empty (e.g. a future --since) — run_main fails it on zero obs."""
        _, p = _patch_client([])
        with p:
            indicators, observations = mod.run_fetch(since=None, until=None)
        assert indicators == []
        assert observations == []

    def test_until_emptying_every_series_does_not_raise(self) -> None:
        _, p = _patch_client(_baseline())
        with p:
            indicators, observations = mod.run_fetch(since=None, until="2010-01-01")
        assert indicators == []
        assert observations == []

    def test_until_emptying_only_some_series_raises(self) -> None:
        """Clipping is applied BEFORE the guard, so a lopsided window is caught."""
        rows = _baseline(exclude=(EAST,)) + [_row(EAST, "2026-09-11", 795)]
        _, p = _patch_client(rows)
        with p:
            with pytest.raises(RuntimeError, match=r"1/8 storage series"):
                mod.run_fetch(since=None, until=BASE_PERIOD)


# ---------------------------------------------------------------------------
# Window + value handling
# ---------------------------------------------------------------------------

class TestWindowAndValues:
    def test_until_clips_the_window(self) -> None:
        rows = _baseline() + [
            _row(L48, "2026-09-04", 3254),
            _row(L48, "2026-09-11", 3298),
        ]
        _, p = _patch_client(rows)
        with p:
            _, observations = mod.run_fetch(since=None, until="2026-09-04")

        l48 = _by_code(observations)["EIA.NATGAS.STORAGE_L48.US"]
        assert {o.obs_date for o in l48} == {
            datetime.date(2020, 1, 3), datetime.date(2026, 9, 4),
        }

    def test_sentinel_and_non_numeric_values_become_none(self) -> None:
        rows = _baseline(exclude=(L48,)) + [
            _row(L48, "2026-08-28", None),
            _row(L48, "2026-09-04", "--"),
            _row(L48, "2026-09-11", "not-a-number"),
        ]
        _, p = _patch_client(rows)
        with p:
            _, observations = mod.run_fetch(since=None, until=None)

        l48 = _by_code(observations)["EIA.NATGAS.STORAGE_L48.US"]
        assert len(l48) == 3
        assert all(o.value is None for o in l48)

    def test_string_numeric_values_are_parsed(self) -> None:
        rows = _baseline(exclude=(L48,)) + [_row(L48, "2026-09-11", "3298")]
        _, p = _patch_client(rows)
        with p:
            _, observations = mod.run_fetch(since=None, until=None)
        assert _by_code(observations)["EIA.NATGAS.STORAGE_L48.US"][0].value == 3298.0

    def test_malformed_periods_are_skipped(self) -> None:
        rows = _baseline(exclude=(L48,)) + [
            _row(L48, "2026-09", 3200),        # wrong length
            _row(L48, "", 3200),               # empty
            _row(L48, "2026-13-45", 3200),     # right length, impossible date
            _row(L48, "2026-09-11", 3298),     # good
        ]
        _, p = _patch_client(rows)
        with p:
            _, observations = mod.run_fetch(since=None, until=None)

        l48 = _by_code(observations)["EIA.NATGAS.STORAGE_L48.US"]
        assert len(l48) == 1
        assert l48[0].obs_date == datetime.date(2026, 9, 11)


# ---------------------------------------------------------------------------
# Wiring
# ---------------------------------------------------------------------------

class TestMain:
    def test_main_delegates_to_run_main_with_us_anchor(self) -> None:
        with patch.object(mod, "run_main", return_value=0) as rm:
            assert mod.main() == 0
        kwargs = rm.call_args.kwargs
        assert kwargs["country_code"] == "US"
        assert kwargs["vendor"] == "eia"
        assert kwargs["topic"] == "natgas_storage"
        assert kwargs["fetch_fn"] is mod.run_fetch
