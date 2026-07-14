"""SQM Research (sqmresearch.com.au) — weekly asking rents + vacancy rates.

Free public pages, no login required. Investigated 2026-07-14 (see
playground/econ/au/sqm/probe_sqm_pages.py): every city page server-renders
its full historical series as a JSON literal embedded directly in an inline
``<script>`` tag (``var data = [...]``) that feeds a Highcharts chart --
there is no separate ajax/JSON endpoint to find, and no login/paywall gate
on the underlying series data itself (the only gated element is a "Buy the
data behind this chart" HubSpot lead-gen button, which is decorative and
does not block the inline data already present in the page HTML).

Weekly Asking Rents (``/property/weekly-rents?region={region}&type=c``):
  Full history 2009-08-01 -> present. Nominally weekly (~87% of gaps are
  exactly 7 days; the remainder are 8-10 day gaps clustered around month
  boundaries -- an SQM cadence quirk in the source, not a scraping
  artefact). Fields per point: ``houses_all``, ``houses_3`` (3-bed
  houses), ``units_all``, ``units_2`` (2-bed units), ``combined``. We take
  ``houses_all`` / ``units_all`` / ``combined`` only, matching the
  ``{CITY}[_{HOUSE|UNIT}]`` naming convention asked for -- the bed-cut
  series are present in the same payload if ever wanted. 8 capitals; no
  national aggregate is published for rents.

Residential Vacancy Rates (``/property/vacancy-rates?region={region}&type=c``
  or ``?national=1`` for the national aggregate):
  MONTHLY (confirmed from the embedded data -- one point per
  ``{year, month}``, not weekly despite the page living under the same
  "property" section as the weekly rent pages). Full history 2005-01 ->
  present. Fields: ``properties`` (rental stock), ``listings`` (vacant
  listings), ``vr`` (vacancy rate as a fraction, e.g. 0.0160 == 1.60%). We
  store ``vr * 100`` as a percent, matching the "pct" unit convention used
  elsewhere (see asx_rate_tracker.py). 8 capitals + National.

Not built (out of scope for this fetcher):
  - Asking Property Prices (``/property/asking-property-prices?...``) --
    a distinct page from rents/vacancy (not "the same page"), though same
    free/public shape and trivial to add later if wanted.
  - Postcode-level vacancy rates -- a separate per-postcode page; city
    (and national) level only here.
  - 3-bed-house / 2-bed-unit rent cuts -- present in the same rent payload
    as houses_all/units_all but not part of the naming convention asked for.
"""
from __future__ import annotations

import datetime
import json
import re
import time

import httpx

from imdr.domains.econ.schema import IndicatorRow, ObservationRow

UTC = datetime.timezone.utc
BASE_URL = "https://sqmresearch.com.au"
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"

VENDOR_NAME = "SQM Research"

# CITY suffix -> SQM's `region` query-param value (state prefix + city name),
# verified 2026-07-14 against the site's own /sitemap page. Used for both
# the weekly-rents and vacancy-rates endpoints.
CITY_REGION: dict[str, str] = {
    "SYDNEY": "nsw-Sydney",
    "MELBOURNE": "vic-Melbourne",
    "BRISBANE": "qld-Brisbane",
    "ADELAIDE": "sa-Adelaide",
    "PERTH": "wa-Perth",
    "HOBART": "tas-Hobart",
    "DARWIN": "nt-Darwin",
    "CANBERRA": "act-Canberra",
}

# (imdr_code suffix, source field, display label) for the 3 rent series we
# extract per city, in the order asked for: combined, houses, units.
RENT_SERIES: list[tuple[str, str, str]] = [
    ("", "combined", "Combined (houses + units)"),
    ("_HOUSE", "houses_all", "All Houses"),
    ("_UNIT", "units_all", "All Units"),
]

_DATA_ARRAY_RE = re.compile(r"var data\s*=\s*(\[.*?\]);", re.DOTALL)


def _extract_data_array(html: str) -> list[dict]:
    """Pull the embedded `var data = [...]` JSON literal out of an SQM page.

    Returns [] if the page doesn't contain the expected script (e.g. a
    changed page layout or an unrecognised region param).
    """
    m = _DATA_ARRAY_RE.search(html)
    if not m:
        return []
    return json.loads(m.group(1))


def _make_client() -> httpx.Client:
    return httpx.Client(
        base_url=BASE_URL,
        timeout=30.0,
        follow_redirects=True,
        headers={"User-Agent": _UA},
    )


def _parse_date_bound(s: str | None) -> datetime.date | None:
    if not s:
        return None
    return datetime.date.fromisoformat(s)


def fetch_rent_points(client: httpx.Client, city: str) -> list[dict]:
    region = CITY_REGION[city]
    r = client.get("/property/weekly-rents", params={"region": region, "type": "c"})
    r.raise_for_status()
    return _extract_data_array(r.text)


def fetch_vacancy_points(client: httpx.Client, city: str | None) -> list[dict]:
    params = {"national": "1"} if city is None else {"region": CITY_REGION[city], "type": "c"}
    r = client.get("/property/vacancy-rates", params=params)
    r.raise_for_status()
    return _extract_data_array(r.text)


def rent_points_to_rows(
    city: str,
    points: list[dict],
    *,
    since: datetime.date | None = None,
    until: datetime.date | None = None,
    now: datetime.datetime | None = None,
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    """Pure transform: SQM rent JSON points -> (indicators, observations) for one city."""
    now = now or datetime.datetime.now(UTC)
    indicators: list[IndicatorRow] = []
    observations: list[ObservationRow] = []
    for suffix, field, label in RENT_SERIES:
        imdr_code = f"SQM.RENT.{city}{suffix}.AU"
        indicators.append(IndicatorRow(
            imdr_code=imdr_code,
            vendor_name=VENDOR_NAME,
            source_code=f"SQM.RENT.{city}{suffix}",
            display_name=(
                f"SQM Research Weekly Asking Rent — {city.title()} "
                f"({label}, AUD/week)"
            ),
            unit="aud_pw",
            frequency="WEEKLY",
            country_iso="AU",
            category="housing",
        ))
        for point in points:
            d = datetime.date.fromisoformat(point["date"])
            if since and d < since:
                continue
            if until and d > until:
                continue
            v = point.get(field)
            if v is None:
                continue
            observations.append(ObservationRow(
                imdr_code=imdr_code, obs_date=d, vintage=0,
                release_date=now, value=float(v), ingested_at=now,
            ))
    return indicators, observations


def vacancy_points_to_rows(
    code: str,
    city: str | None,
    points: list[dict],
    *,
    since: datetime.date | None = None,
    until: datetime.date | None = None,
    now: datetime.datetime | None = None,
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    """Pure transform: SQM vacancy JSON points -> (indicators, observations) for one city/National."""
    now = now or datetime.datetime.now(UTC)
    label = "National" if city is None else code.title()
    imdr_code = f"SQM.VACANCY.{code}.AU"
    indicators = [IndicatorRow(
        imdr_code=imdr_code,
        vendor_name=VENDOR_NAME,
        source_code=f"SQM.VACANCY.{code}",
        display_name=f"SQM Research Residential Vacancy Rate — {label} (%)",
        unit="pct",
        frequency="MONTHLY",
        country_iso="AU",
        category="housing",
    )]
    observations: list[ObservationRow] = []
    for point in points:
        d = datetime.date(int(point["year"]), int(point["month"]), 1)
        if since and d < since:
            continue
        if until and d > until:
            continue
        vr = point.get("vr")
        if vr is None:
            continue
        observations.append(ObservationRow(
            imdr_code=imdr_code, obs_date=d, vintage=0,
            release_date=now, value=float(vr) * 100.0, ingested_at=now,
        ))
    return indicators, observations


def build_rent_rows(
    since: str | None = None,
    until: str | None = None,
    *,
    delay: float = 1.0,
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    lo, hi = _parse_date_bound(since), _parse_date_bound(until)
    indicators: list[IndicatorRow] = []
    observations: list[ObservationRow] = []
    with _make_client() as client:
        for i, city in enumerate(CITY_REGION):
            if i:
                time.sleep(delay)
            points = fetch_rent_points(client, city)
            if not points:
                print(f"  WARN  RENT {city}: no data extracted")
                continue
            ind, obs = rent_points_to_rows(city, points, since=lo, until=hi)
            indicators.extend(ind)
            observations.extend(obs)
            print(f"  RENT  {city:<10s} n_points={len(points)} n_obs_kept={len(obs)}")
    return indicators, observations


def build_vacancy_rows(
    since: str | None = None,
    until: str | None = None,
    *,
    delay: float = 1.0,
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    lo, hi = _parse_date_bound(since), _parse_date_bound(until)
    targets: list[tuple[str, str | None]] = [(city, city) for city in CITY_REGION] + [("NATIONAL", None)]
    indicators: list[IndicatorRow] = []
    observations: list[ObservationRow] = []
    with _make_client() as client:
        for i, (code, city) in enumerate(targets):
            if i:
                time.sleep(delay)
            points = fetch_vacancy_points(client, city)
            if not points:
                print(f"  WARN  VACANCY {code}: no data extracted")
                continue
            ind, obs = vacancy_points_to_rows(code, city, points, since=lo, until=hi)
            indicators.extend(ind)
            observations.extend(obs)
            print(f"  VACANCY {code:<10s} n_points={len(points)} n_obs_kept={len(obs)}")
    return indicators, observations
