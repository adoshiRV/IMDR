"""UPAg — All-India APY (Area / Production / Yield) by crop × season.

Source: `dash.upag.gov.in/_dash-update-component` — Plotly Dash callback
endpoint serving the AIAPY report at `upag.gov.in/dash-reports/allindiaapy`.

Component-prefix `aiapy` (NOT `aiapy-…-yw`, which is the year-wise
sub-view). Data callback's output includes ``aiapy-idstore.data``; the
fetcher reads the live signature from `_dash-dependencies` for
resilience.

History: 1966-67 → 2025-26 (60 FYs) × 37 crops × {Kharif, Rabi, Summer,
Total} × {Area Lakh-Ha, Production Lakh-Tonnes, Yield Kg/Ha}. The
'Final Estimate' cycle is canonical (14,736 rows); 'Third Advance
Estimates' covers the latest 1-2 years before Final lands.

Cell mapping (see docs/admin/econ/india/in_coverage_plan.md):
  Cluster 4 (agriculture) — A26 area + production + yield by major
  crop is THE annual macro indicator for India's farm sector.
"""
from __future__ import annotations

import datetime
import re

import httpx

from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from imdr.domains.econ.upag import fetch_signature, post_callback, slug
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc

# UPAg returns 3 UOMs in one response (Area Lakh-Ha, Production
# Lakh-Tonnes, Yield Kg/Ha). None map cleanly to existing dim_unit
# rows; using "ratio" as a placeholder so the loader doesn't reject
# the row. Deferred — adding lakh_ha/lakh_t/kg_ha to dim_unit is
# tracked in docs/admin/econ/india/in_coverage_plan.md.
_UOM_MAP: dict[str, str] = {
    "Lakh Ha":      "ratio",
    "Lakh Tonnes":  "ratio",
    "Kg/Ha":        "ratio",
}
_UOM_SUFFIX: dict[str, str] = {
    "Lakh Ha":     "Lakh Ha",
    "Lakh Tonnes": "Lakh Tonnes",
    "Kg/Ha":       "Kg/Ha",
}

_CYCLE_RANK = {
    "Final Estimate": 0,
    "Fourth Advance Estimates": 1,
    "Third Advance Estimates": 2,
    "Second Advance Estimates": 3,
    "First Advance Estimates": 4,
}


def _crop_year_to_fy_date(cy: str) -> datetime.date | None:
    m = re.match(r"^(\d{4})-\d{2}$", cy.strip())
    if not m:
        return None
    return datetime.date(int(m.group(1)), 4, 1)


def run_fetch(
    since: str | None,
    until: str | None,
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    since_dt = datetime.date.fromisoformat(since) if since else None
    until_dt = datetime.date.fromisoformat(until) if until else None
    now = datetime.datetime.now(UTC)

    print("  fetching AIAPY (Area + Production + Yield, all crops + seasons)")
    with httpx.Client(timeout=60, follow_redirects=True) as c:
        sig = fetch_signature(c,
                              output_contains="aiapy-idstore.data",
                              exclude_contains="aiapy-idstore-yw")
        resp = post_callback(
            c, sig,
            inputs=[{"id": "aiapy-filters-store", "property": "data",
                      "value": {"metric": ["Area", "Production", "Yield"],
                                "uom": "Lakh"}}],
            state=[{"id": "url", "property": "search",
                    "value": "?rtab=All%20India%20APY&rtype=dashboard"}],
        )
    rows = (resp.get("aiapy-idstore", {}).get("data") or [])
    print(f"  {len(rows)} raw rows returned")

    # Dedup by (crop, year, season, metric): prefer Final Estimate; fall
    # back to Third Advance for current/recent year where Final isn't out.
    by_key: dict[tuple, dict] = {}
    for r in rows:
        crop = (r.get("Crop") or "").strip()
        year = (r.get("Crop Year") or "").strip()
        season = (r.get("Season") or "").strip()
        metric = (r.get("Metric") or "").strip()
        cycle = (r.get("Estimation Cycle") or "").strip()
        if not (crop and year and season and metric):
            continue
        key = (crop, year, season, metric)
        rank = _CYCLE_RANK.get(cycle, 9)
        cur = by_key.get(key)
        if cur is None or rank < _CYCLE_RANK.get(cur.get("Estimation Cycle"), 9):
            by_key[key] = r
    print(f"  {len(by_key)} unique (crop, year, season, metric) tuples after cycle dedup")

    indicators: dict[str, IndicatorRow] = {}
    observations: list[ObservationRow] = []
    seen_obs: set[tuple[str, datetime.date]] = set()
    skipped_units: set[str] = set()

    for r in by_key.values():
        crop = r.get("Crop").strip()
        year = r.get("Crop Year").strip()
        season = r.get("Season").strip()
        metric = r.get("Metric").strip()
        cat = (r.get("Crop Category") or "").strip()
        value = r.get("Value")
        uom = (r.get("Unit Of Measure") or "").strip()
        if not isinstance(value, (int, float)):
            continue
        obs_date = _crop_year_to_fy_date(year)
        if obs_date is None:
            continue
        if since_dt and obs_date < since_dt:
            continue
        if until_dt and obs_date > until_dt:
            continue
        if uom not in _UOM_MAP:
            skipped_units.add(uom)
            continue

        crop_slug = slug(crop)
        season_slug = slug(season)
        metric_slug = slug(metric)
        imdr_code = f"INDIA.APY.{crop_slug}.{season_slug}.{metric_slug}.IN"
        if imdr_code not in indicators:
            indicators[imdr_code] = IndicatorRow(
                imdr_code=imdr_code, vendor_name="UPAg",
                source_code=f"UPAg/AIAPY/{crop_slug}/{season_slug}/{metric_slug}",
                display_name=(
                    f"India APY — {crop} {season} {metric} ({cat}, {_UOM_SUFFIX[uom]})"
                )[:255],
                unit=_UOM_MAP[uom], frequency="ANNUAL",
                country_iso="IN", category="other",
                is_seasonally_adjusted=False, bbg_ticker=None,
            )
        key = (imdr_code, obs_date)
        if key in seen_obs:
            continue
        seen_obs.add(key)
        observations.append(ObservationRow(
            imdr_code=imdr_code, obs_date=obs_date, vintage=0,
            release_date=now, value=float(value), ingested_at=now,
        ))

    if skipped_units:
        print(f"  skipped rows with unknown UOMs: {sorted(skipped_units)}")
    return list(indicators.values()), observations


def main() -> int:
    return run_main(vendor="upag", topic="aiapy",
                    fetch_fn=run_fetch,
                    description=__doc__.splitlines()[0] if __doc__ else "",
                    country_code="IN")


if __name__ == "__main__":
    import sys
    sys.exit(main())
