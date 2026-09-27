"""Tests for scripts/econ/in/imd/imd_rainfall.py.

Network-free. httpx.get is patched on the module.

Regression-pins the 2026-08-20 incident: the fetcher omitted the `msg`
query param, IMD served its DEFAULT Daily window, and the daily rain sum
was stored under a "cumulative monsoon-to-date" label (~68x level error,
+-50% day-to-day swings, three unusable digest editions).

Exercises:
  - URL carries msg=C
  - served-mode guard raises when IMD serves D (or anything != C)
  - stale-date district rows are excluded from the sums
  - actual/normal are summed over the SAME district set
  - district floor raises rather than publishing a partial aggregate
  - off-season returns empty (clean skip, not an error)
  - broken page structure raises instead of returning empty
  - pinned aggregate math + imdr_codes + units
"""
from __future__ import annotations

import datetime
import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Load the module via importlib (avoids `in` keyword in dotted import path)
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[3]
_MOD_PATH = _REPO_ROOT / "scripts" / "econ" / "in" / "imd" / "imd_rainfall.py"

_spec = importlib.util.spec_from_file_location("imd_rainfall", _MOD_PATH)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["imd_rainfall"] = _mod
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]

run_fetch = _mod.run_fetch
_parse_districts = _mod._parse_districts
_aggregate_obs_date = _mod._aggregate_obs_date
_assert_served_mode = _mod._assert_served_mode


# ---------------------------------------------------------------------------
# Page fixtures
# ---------------------------------------------------------------------------

def _district(title: str, did: str, date: str, actual: float, normal: float) -> str:
    """One amCharts areas[] entry, shaped like the live page."""
    balloon = (
        f"<h6>{title}<\\/h6> <p><em>Date : {date}<\\/br>"
        f"Departure : -12%<\\/br>Actual : {actual} mm<\\/br>"
        f"Normal : {normal} mm<\\/em><\\/p>"
    )
    return (
        f'{{ "title": "{title}", "id": "{did}", "color": "#00ff00", '
        f'"info": "x", "balloonText": "{balloon}" }}'
    )


def _page(districts: list[str], *, mode: str = "C",
          season: str = "01-06-2026", as_of: str = "19-08-2026") -> str:
    return f"""
    <html><body>
      <label for="rb5">Daily ({as_of})</label>
      <label for="rb7">Monthly (,,From 01-08-2026 To {as_of},,)</label>
      <label for="rb8">Cumulative (From {season})</label>
      <script>
        var check="{mode}";
        var map = {{ "dataProvider": {{ "areas": [ {",".join(districts)} ] }} }};
      </script>
    </body></html>
    """


def _n_districts(n: int, *, date: str = "2026-08-19",
                 actual: float = 500.0, normal: float = 600.0) -> list[str]:
    return [_district(f"D{i}", f"ID{i}", date, actual, normal) for i in range(n)]


def _patch_get(html: str) -> MagicMock:
    resp = MagicMock()
    resp.text = html
    resp.raise_for_status = MagicMock()
    return resp


# ---------------------------------------------------------------------------
# The incident: window mode
# ---------------------------------------------------------------------------

def test_url_requests_cumulative_window():
    """Omitting msg gets IMD's DEFAULT Daily view -- the 2026-08-20 bug."""
    assert _mod._MODE == "C"
    assert _mod._URL.endswith("?msg=C")


@pytest.mark.parametrize("served", ["D", "W", "M"])
def test_served_mode_guard_raises_on_wrong_window(served):
    """A daily sum is ~68x smaller than the cumulative and otherwise
    identical in shape -- refuse to publish it under a cumulative label."""
    with pytest.raises(RuntimeError, match=r"served window mode"):
        _assert_served_mode(_page(_n_districts(700), mode=served))


def test_served_mode_guard_raises_when_marker_absent():
    with pytest.raises(RuntimeError, match=r"served window mode"):
        _assert_served_mode("<html>no marker</html>")


def test_served_mode_guard_passes_on_cumulative():
    _assert_served_mode(_page(_n_districts(700), mode="C"))  # no raise


# ---------------------------------------------------------------------------
# Stale-row exclusion
# ---------------------------------------------------------------------------

def test_stale_date_rows_excluded_from_sums():
    """On 19 Aug 2026 the live page carried 34 rows stuck on foreign dates
    (26 @ 2023-07-03, 6 @ 2024-05-24, ...). The old code summed them all."""
    districts = (
        _n_districts(700, date="2026-08-19", actual=500.0, normal=600.0)
        + [_district("STALE", "S1", "2023-07-03", 9999.0, 9999.0)]
        + [_district("STALE2", "S2", "2024-05-24", 8888.0, 8888.0)]
    )
    with patch.object(_mod.httpx, "get", return_value=_patch_get(_page(districts))):
        inds, obs = run_fetch(None, None)

    by_code = {o.imdr_code: o.value for o in obs}
    # 700 x 500 = 350_000 exactly -- the 9999/8888 rows must not appear
    assert by_code["IMD.RAINFALL.AI.CUM.ACTUAL_MM"] == pytest.approx(350_000.0)
    assert by_code["IMD.RAINFALL.AI.CUM.NORMAL_MM"] == pytest.approx(420_000.0)
    assert all(o.obs_date == datetime.date(2026, 8, 19) for o in obs)


def test_actual_and_normal_summed_over_same_district_set():
    """A district missing one leg must drop out of BOTH sums, else the
    ratio is computed across mismatched denominators."""
    districts = _n_districts(700, actual=500.0, normal=600.0)
    # a district with a normal but no parseable actual
    districts.append(
        '{ "title": "HALF", "id": "H1", "color": "#fff", "info": "x", '
        '"balloonText": "<h6>HALF<\\/h6> <p><em>Date : 2026-08-19<\\/br>'
        'Normal : 700 mm<\\/em><\\/p>" }'
    )
    with patch.object(_mod.httpx, "get", return_value=_patch_get(_page(districts))):
        _, obs = run_fetch(None, None)

    by_code = {o.imdr_code: o.value for o in obs}
    assert by_code["IMD.RAINFALL.AI.CUM.ACTUAL_MM"] == pytest.approx(350_000.0)
    # 700 must NOT be in the normal sum
    assert by_code["IMD.RAINFALL.AI.CUM.NORMAL_MM"] == pytest.approx(420_000.0)


# ---------------------------------------------------------------------------
# Guards
# ---------------------------------------------------------------------------

def test_district_floor_raises_on_partial_page():
    with patch.object(_mod.httpx, "get",
                      return_value=_patch_get(_page(_n_districts(120)))):
        with pytest.raises(RuntimeError, match=r"districts usable"):
            run_fetch(None, None)


def test_broken_layout_raises_rather_than_returning_empty():
    """Silent [] would look like an off-season skip and hide a dead regex."""
    with patch.object(_mod.httpx, "get",
                      return_value=_patch_get("<html>redesigned</html>")):
        with pytest.raises(RuntimeError, match=r"served window mode"):
            run_fetch(None, None)


def test_zero_districts_raises_when_mode_ok():
    with patch.object(_mod.httpx, "get",
                      return_value=_patch_get(_page([]))):
        with pytest.raises(RuntimeError, match=r"parsed 0 districts"):
            run_fetch(None, None)


def test_off_season_returns_empty_not_error():
    """Past the withdrawal tail the page repeats a closed season's final
    total; republishing it daily is noise. Clean skip, not a failure."""
    districts = _n_districts(700, date="2026-12-01")
    html = _page(districts, season="01-06-2026", as_of="01-12-2026")
    with patch.object(_mod.httpx, "get", return_value=_patch_get(html)):
        inds, obs = run_fetch(None, None)
    assert (inds, obs) == ([], [])


def test_in_season_publishes():
    districts = _n_districts(700, date="2026-06-15")
    html = _page(districts, season="01-06-2026", as_of="15-06-2026")
    with patch.object(_mod.httpx, "get", return_value=_patch_get(html)):
        _, obs = run_fetch(None, None)
    assert len(obs) == 3


# ---------------------------------------------------------------------------
# Contract: codes, units, math
# ---------------------------------------------------------------------------

def test_departure_math_and_codes_pinned():
    # 700 districts, actual 450 vs normal 600 -> -25.00% exactly
    districts = _n_districts(700, actual=450.0, normal=600.0)
    with patch.object(_mod.httpx, "get", return_value=_patch_get(_page(districts))):
        inds, obs = run_fetch(None, None)

    by_code = {o.imdr_code: o.value for o in obs}
    assert by_code["IMD.RAINFALL.AI.CUM.DEPARTURE_PCT"] == pytest.approx(-25.0)

    assert {i.imdr_code for i in inds} == {
        "IMD.RAINFALL.AI.CUM.ACTUAL_MM",
        "IMD.RAINFALL.AI.CUM.NORMAL_MM",
        "IMD.RAINFALL.AI.CUM.DEPARTURE_PCT",
    }


def test_mm_series_declared_as_mm_not_ratio():
    """Migration 123 seeds dim_unit 'mm'. The old code declared these two
    as 'ratio' (dimensionless)."""
    districts = _n_districts(700)
    with patch.object(_mod.httpx, "get", return_value=_patch_get(_page(districts))):
        inds, _ = run_fetch(None, None)

    units = {i.imdr_code: i.unit for i in inds}
    assert units["IMD.RAINFALL.AI.CUM.ACTUAL_MM"] == "mm"
    assert units["IMD.RAINFALL.AI.CUM.NORMAL_MM"] == "mm"
    assert units["IMD.RAINFALL.AI.CUM.DEPARTURE_PCT"] == "pct"


def test_indicator_metadata_contract():
    districts = _n_districts(700)
    with patch.object(_mod.httpx, "get", return_value=_patch_get(_page(districts))):
        inds, _ = run_fetch(None, None)
    for i in inds:
        assert i.vendor_name == "IMD"
        assert i.frequency == "DAILY"
        assert i.country_iso == "IN"
        assert i.is_seasonally_adjusted is False
        assert "cumulative" in i.display_name.lower()


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

def test_aggregate_obs_date_picks_modal_over_stale():
    rows = _parse_districts(_page(
        _n_districts(50, date="2026-08-19")
        + [_district("S", "S", "2023-07-03", 1.0, 1.0)] * 3
    ))
    assert _aggregate_obs_date(rows) == datetime.date(2026, 8, 19)


def test_aggregate_obs_date_ignores_zero_sentinel():
    rows = _parse_districts(_page(
        [_district("Z", f"Z{i}", "0000-00-00", 1.0, 1.0) for i in range(9)]
        + _n_districts(4, date="2026-08-19")
    ))
    assert _aggregate_obs_date(rows) == datetime.date(2026, 8, 19)


def test_parse_districts_reads_balloon_fields():
    rows = _parse_districts(_page([_district("NICOBAR", "N1", "2026-08-19", 0.5, 7.4)]))
    assert len(rows) == 1
    assert rows[0]["title"] == "NICOBAR"
    assert rows[0]["obs_date"] == "2026-08-19"
    assert rows[0]["actual_mm"] == pytest.approx(0.5)
    assert rows[0]["normal_mm"] == pytest.approx(7.4)
