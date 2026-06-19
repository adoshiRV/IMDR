"""UPAg — Commodity-wise Minimum Support Price (MSP) by crop × season.

Source: `dash.upag.gov.in/_dash-update-component` — Plotly Dash callback
endpoint serving the MSP report at `upag.gov.in/dash-reports/mipmspstatement`.

Component-prefix `mip-msp-data2`. Data callback inputs the filters-store
value and outputs the unrendered record list at ``mip-msp-data2-store2.data``.

History reachable: 2013-14 → 2026-27 (14 FYs). 28 crops × ~3 metrics
(MSP level + Δ + Δ%). Only the MSP level metric is loaded — the others
are downstream transforms.

Cell mapping (see docs/admin/econ/india/in_coverage_plan.md):
  Cluster 4 (agriculture) — MSP feeds food-CPI thesis + Kharif/Rabi cycle.

Run:
    python -m scripts.econ.in.upag.upag_msp --no-load
"""
from __future__ import annotations

import datetime
import re

import httpx

from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from imdr.domains.econ.upag import fetch_signature, post_callback, slug
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc


def _fy_start(fy: str) -> datetime.date | None:
    """Indian FY '2014-15' → 2014-04-01 (FY start)."""
    m = re.match(r"^(\d{4})-\d{2}$", fy.strip())
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

    print("  fetching MSP rows 2000-01 → 2030-31 (server caps at its data window)")
    with httpx.Client(timeout=60, follow_redirects=True) as c:
        sig = fetch_signature(c, output_contains="mip-msp-data2-store2.data")
        resp = post_callback(
            c, sig,
            inputs=[{"id": "mip-msp-data2-filters-store", "property": "data",
                      "value": {"from_year": "2000-01", "to_year": "2030-31"}}],
            state=[{"id": "url", "property": "search",
                    "value": "?rtab=Commodity-wise%20MSP&rtype=dashboard"}],
        )
    rows = (resp.get("mip-msp-data2-store2", {}).get("data") or [])
    print(f"  {len(rows)} rows returned")

    # MSP-level rows only — Δ and Δ% are downstream transforms.
    rows = [r for r in rows if r.get("Metric") == "MSP"]
    print(f"  {len(rows)} MSP-level rows (Δ + Δ% dropped)")

    indicators: dict[str, IndicatorRow] = {}
    observations: list[ObservationRow] = []
    seen_obs: set[tuple[str, datetime.date]] = set()
    skipped_units: set[str] = set()

    for r in rows:
        crop = (r.get("Crop") or "").strip()
        season = (r.get("Season") or "").strip()
        year_s = (r.get("Year") or "").strip()
        value = r.get("Value")
        uom = (r.get("UOM") or "").strip()
        category = (r.get("Crop Category") or "").strip()
        if not (crop and year_s and isinstance(value, (int, float))):
            continue
        obs_date = _fy_start(year_s)
        if obs_date is None:
            continue
        if since_dt and obs_date < since_dt:
            continue
        if until_dt and obs_date > until_dt:
            continue
        if uom not in ("Rs/Qtl", "Rs/Quintal"):
            skipped_units.add(uom)
            continue

        crop_slug = slug(crop)
        season_slug = slug(season) if season else "ANN"
        imdr_code = f"INDIA.MSP.{crop_slug}.{season_slug}.INR_QTL.IN"
        if imdr_code not in indicators:
            indicators[imdr_code] = IndicatorRow(
                imdr_code=imdr_code, vendor_name="UPAg",
                source_code=f"UPAg/MIP_MSP/{crop_slug}/{season_slug}",
                display_name=(
                    f"India MSP — {crop} ({season}, {category}) — INR/Qtl"
                )[:255],
                unit="inr", frequency="ANNUAL", country_iso="IN",
                category="other",
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
        print(f"  skipped rows with unknown units: {sorted(skipped_units)}")
    return list(indicators.values()), observations


def main() -> int:
    return run_main(vendor="upag", topic="msp",
                    fetch_fn=run_fetch,
                    description=__doc__.splitlines()[0] if __doc__ else "",
                    country_code="IN")


if __name__ == "__main__":
    import sys
    sys.exit(main())
