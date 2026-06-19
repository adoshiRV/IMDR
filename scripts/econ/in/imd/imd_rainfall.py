"""IMD All-India cumulative rainfall — daily snapshot.

Source: mausam.imd.gov.in/responsive/rainfallinformation.php — embedded
amCharts `dataProvider.areas` array with one row per IMD district. Each
row carries obs_date / actual_mm / normal_mm / departure_pct (cumulative
since SW monsoon onset 1 June).

This fetcher derives the All-India aggregate as sum(actual_mm) /
sum(normal_mm) across the ~700 districts on the page and emits 3 daily
indicators:

  IMD.RAINFALL.AI.ACTUAL_MM       sum-of-district actual mm
  IMD.RAINFALL.AI.NORMAL_MM       sum-of-district normal mm
  IMD.RAINFALL.AI.DEPARTURE_PCT   implied = (actual / normal - 1) * 100

Per-district series (~700 × 3 = ~2,100 codes) are deferred — they'd
quintuple dim_indicator headcount for a single-country dataset. Add as
a separate fetcher if district granularity is needed downstream.

Cell mapping (see docs/admin/econ/india/in_coverage_plan.md):
  Cluster 8 — agri & weather (rainfall feeds CPI food cluster)
"""
from __future__ import annotations

import datetime
import re

import httpx

from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc

_URL = "https://mausam.imd.gov.in/responsive/rainfallinformation.php"
_UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
    "Referer": "https://mausam.imd.gov.in/",
}

_DISTRICT_RE = re.compile(
    r'\{\s*"title"\s*:\s*"([^"]*)"\s*,\s*'
    r'"id"\s*:\s*"([^"]*)"\s*,\s*'
    r'"color"\s*:\s*"[^"]*"\s*,\s*'
    r'"info"\s*:\s*"([^"]*)"\s*,\s*'
    r'"balloonText"\s*:\s*"([^"]*(?:\\.[^"\\]*)*)"',
    re.DOTALL,
)
_BALLOON_DATE_RE = re.compile(r"Date\s*:\s*([\d\-]+)")
_BALLOON_ACTUAL_RE = re.compile(r"Actual\s*:\s*(-?[\d.]+)\s*mm")
_BALLOON_NORMAL_RE = re.compile(r"Normal\s*:\s*(-?[\d.]+)\s*mm")


def _parse_districts(html: str) -> list[dict]:
    rows: list[dict] = []
    for m in _DISTRICT_RE.finditer(html):
        title, did, _info, balloon = m.groups()
        d = _BALLOON_DATE_RE.search(balloon)
        a = _BALLOON_ACTUAL_RE.search(balloon)
        n = _BALLOON_NORMAL_RE.search(balloon)
        rows.append({
            "title": title,
            "id": did,
            "obs_date": d.group(1) if d else None,
            "actual_mm": float(a.group(1)) if a else None,
            "normal_mm": float(n.group(1)) if n else None,
        })
    return rows


def _aggregate_obs_date(rows: list[dict]) -> datetime.date | None:
    """Pick the modal obs_date across districts. All-India aggregate is
    only meaningful when all districts report for the same day; in
    practice the page is refreshed atomically so >95% share one date."""
    dates: dict[str, int] = {}
    for r in rows:
        d = r.get("obs_date")
        if d and d != "0000-00-00":
            dates[d] = dates.get(d, 0) + 1
    if not dates:
        return None
    modal = max(dates.items(), key=lambda kv: kv[1])[0]
    try:
        return datetime.date.fromisoformat(modal)
    except ValueError:
        return None


_INDICATORS = [
    ("IMD.RAINFALL.AI.ACTUAL_MM",
     "IMD/RAINFALL/AI/ACTUAL_MM",
     "India All-India cumulative rainfall — actual (mm, monsoon-to-date)",
     "ratio"),
    ("IMD.RAINFALL.AI.NORMAL_MM",
     "IMD/RAINFALL/AI/NORMAL_MM",
     "India All-India cumulative rainfall — normal (mm, monsoon-to-date)",
     "ratio"),
    ("IMD.RAINFALL.AI.DEPARTURE_PCT",
     "IMD/RAINFALL/AI/DEPARTURE_PCT",
     "India All-India cumulative rainfall — % departure from normal (monsoon-to-date)",
     "pct"),
]


def run_fetch(
    since: str | None,
    until: str | None,
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    # IMD page is a daily snapshot — since/until have no effect; we can
    # only observe today.
    _ = since, until
    now = datetime.datetime.now(UTC)

    print(f"  fetching {_URL}")
    r = httpx.get(_URL, timeout=30, follow_redirects=True, headers=_UA)
    r.raise_for_status()
    print(f"  {len(r.text)} bytes received")

    rows = _parse_districts(r.text)
    print(f"  {len(rows)} districts parsed")
    if not rows:
        return [], []

    obs_date = _aggregate_obs_date(rows)
    if obs_date is None:
        print("  no usable obs_date across districts; skipping")
        return [], []

    actuals = [r["actual_mm"] for r in rows if r["actual_mm"] is not None]
    normals = [r["normal_mm"] for r in rows if r["normal_mm"] is not None]
    if not actuals or not normals or sum(normals) == 0:
        print("  insufficient actual/normal coverage; skipping")
        return [], []

    sum_actual = sum(actuals)
    sum_normal = sum(normals)
    departure_pct = (sum_actual / sum_normal - 1.0) * 100.0
    print(f"  modal obs_date={obs_date} actual={sum_actual:.1f} normal={sum_normal:.1f} "
          f"departure={departure_pct:+.2f}%")

    indicators: list[IndicatorRow] = []
    observations: list[ObservationRow] = []
    for imdr_code, src, display, unit in _INDICATORS:
        indicators.append(IndicatorRow(
            imdr_code=imdr_code, vendor_name="IMD",
            source_code=src, display_name=display,
            unit=unit, frequency="DAILY",
            country_iso="IN", category="other",
            is_seasonally_adjusted=False, bbg_ticker=None,
        ))

    values = {
        "IMD.RAINFALL.AI.ACTUAL_MM": sum_actual,
        "IMD.RAINFALL.AI.NORMAL_MM": sum_normal,
        "IMD.RAINFALL.AI.DEPARTURE_PCT": departure_pct,
    }
    for imdr_code, v in values.items():
        observations.append(ObservationRow(
            imdr_code=imdr_code, obs_date=obs_date, vintage=0,
            release_date=now, value=v, ingested_at=now,
        ))
    return indicators, observations


def main() -> int:
    return run_main(vendor="imd", topic="rainfall",
                    fetch_fn=run_fetch,
                    description=__doc__.splitlines()[0] if __doc__ else "",
                    country_code="IN")


if __name__ == "__main__":
    import sys
    sys.exit(main())
