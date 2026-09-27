"""IMD All-India cumulative monsoon rainfall — daily snapshot.

Source: mausam.imd.gov.in/responsive/rainfallinformation.php?msg=C — embedded
amCharts `dataProvider.areas` array with one row per IMD district. Each row
carries obs_date / departure_pct / actual_mm / normal_mm inside a
`balloonText` blob.

WINDOW MODE IS LOAD-BEARING
---------------------------
The page serves four *different* windows, selected by the ``msg`` query
param, and **defaults to Daily when ``msg`` is omitted**:

    msg=D   Daily            (0830 hrs D-1 -> 0830 hrs D)
    msg=W   Weekly           -- BROKEN UPSTREAM, see below
    msg=M   Month-to-date    (from 01-{MM}-YYYY)
    msg=C   Cumulative       (from monsoon onset, 01-06-YYYY)  <-- what we want

Until 2026-08-20 this fetcher omitted ``msg`` and therefore stored a
SINGLE-DAY rain sum under a "cumulative monsoon-to-date" label. Measured at
the same instant on 19 Aug 2026 the two windows differ by ~68x:

    D:  actual   6,206.9 mm   departure  -3.74%
    C:  actual 424,111.7 mm   departure -14.46%

A season cumulative moves fractions of a point per day; a daily figure
swings +-50%. The stored series therefore read -50.8 -> -25.9 -> -34.2 ->
-15.0 -> +27.5 -> -3.7 and was excluded as unusable by the daily digest for
three consecutive editions. `_assert_served_mode` now fails loudly if IMD
stops honouring the param, rather than silently reverting to the daily view.

Do NOT switch to ``msg=W``: that view returns ~9 mm/district, a daily
magnitude, i.e. it is broken on IMD's side.

Emits 3 daily indicators (all cumulative from 1 June):

  IMD.RAINFALL.AI.CUM.ACTUAL_MM       district-unweighted sum of actual mm
  IMD.RAINFALL.AI.CUM.NORMAL_MM       district-unweighted sum of normal mm
  IMD.RAINFALL.AI.CUM.DEPARTURE_PCT   implied = (actual / normal - 1) * 100

These codes carry an explicit ``CUM`` segment so the window can never again
be ambiguous. The pre-2026-08-20 codes (`IMD.RAINFALL.AI.{ACTUAL_MM,
NORMAL_MM,DEPARTURE_PCT}`) hold daily-window values under a cumulative
label and are retired by migration 124.

CAVEAT — this is NOT IMD's headline number. IMD's official all-India
departure is area-weighted by sub-division; a district-unweighted sum-ratio
is a proxy. On 19 Aug 2026 the unweighted sum-ratio gave -14.46% and the
mean of per-district departures -12.84%. Present it as an IMDR-computed
proxy, never as "IMD reports".

Per-district series (~700 x 3 = ~2,100 codes) are deferred — they'd
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

_BASE_URL = "https://mausam.imd.gov.in/responsive/rainfallinformation.php"
# 'C' = Cumulative from monsoon onset (1 June). Omitting msg yields Daily.
_MODE = "C"
_URL = f"{_BASE_URL}?msg={_MODE}"
_UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
    "Referer": "https://mausam.imd.gov.in/",
}

# Publish floor. The district set is stable at ~730 reporting districts; a
# drop below this is structural (page/regex change), not transient jitter.
_MIN_DISTRICTS = 600

# Days after monsoon onset for which a cumulative print is still meaningful.
# 1 Jun + 152d ~= 31 Oct: covers the SW monsoon (Jun-Sep) plus a withdrawal
# tail. Beyond it the page repeats the closed season's final total.
_SEASON_LEN_DAYS = 152

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

# Server-rendered echo of the window actually served -- the mode guard.
_SERVED_MODE_RE = re.compile(r'var\s+check\s*=\s*"([A-Z])"')
# Radio labels: "Cumulative (From 01-06-2026)" / "Daily (19-08-2026)".
_SEASON_START_RE = re.compile(r"Cumulative\s*\(From\s*(\d{2}-\d{2}-\d{4})\)")
_PAGE_AS_OF_RE = re.compile(r"Daily\s*\((\d{2}-\d{2}-\d{4})\)")


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
    """Pick the modal obs_date across districts.

    The page carries a tail of stale rows -- districts whose last reported
    day never rolled forward (on 19 Aug 2026: 26 rows at 2023-07-03, 6 at
    2024-05-24, 1 at 2025-10-08, 1 at 2026-06-01). The modal date is the
    real as-of day; `run_fetch` filters the aggregate to it so those rows
    cannot leak into the sums.
    """
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


def _assert_served_mode(html: str) -> None:
    """Fail loudly unless IMD served the window we asked for.

    This is the guard for the 2026-08-20 incident: with no `msg` the page
    silently serves Daily, which is indistinguishable from Cumulative in
    shape and differs only in magnitude.
    """
    m = _SERVED_MODE_RE.search(html)
    served = m.group(1) if m else None
    if served != _MODE:
        raise RuntimeError(
            f"IMD served window mode {served!r}, expected {_MODE!r} "
            f"(Cumulative from 1 June). The page defaults to 'D' (Daily) when "
            f"the msg param is not honoured, and a daily sum is ~68x smaller "
            f"than the cumulative -- refusing to publish it under a "
            f"cumulative label. Check {_URL}"
        )


def _page_date(pattern: re.Pattern[str], html: str) -> datetime.date | None:
    """Parse a DD-MM-YYYY date out of one of the radio labels."""
    m = pattern.search(html)
    if not m:
        return None
    try:
        return datetime.datetime.strptime(m.group(1), "%d-%m-%Y").date()
    except ValueError:
        return None


_INDICATORS = [
    ("IMD.RAINFALL.AI.CUM.ACTUAL_MM",
     "IMD/RAINFALL/AI/CUM/ACTUAL_MM",
     "India All-India cumulative monsoon rainfall — actual "
     "(mm, from 1 Jun; district-unweighted sum)",
     "mm"),
    ("IMD.RAINFALL.AI.CUM.NORMAL_MM",
     "IMD/RAINFALL/AI/CUM/NORMAL_MM",
     "India All-India cumulative monsoon rainfall — normal "
     "(mm, from 1 Jun; district-unweighted sum)",
     "mm"),
    ("IMD.RAINFALL.AI.CUM.DEPARTURE_PCT",
     "IMD/RAINFALL/AI/CUM/DEPARTURE_PCT",
     "India All-India cumulative monsoon rainfall — departure from normal "
     "(%, from 1 Jun; district-unweighted, not IMD's area-weighted headline)",
     "pct"),
]


def run_fetch(
    since: str | None,
    until: str | None,
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    # IMD page is a daily snapshot — since/until have no effect; we can
    # only observe today. The cumulative window is self-healing on gaps
    # (each day's total contains every prior day), so a missed run costs
    # a datapoint but never corrupts the level.
    _ = since, until
    now = datetime.datetime.now(UTC)

    print(f"  fetching {_URL}")
    r = httpx.get(_URL, timeout=30, follow_redirects=True, headers=_UA)
    r.raise_for_status()
    print(f"  {len(r.text)} bytes received")

    _assert_served_mode(r.text)
    print(f"  served window mode={_MODE} (Cumulative from 1 June) — confirmed")

    rows = _parse_districts(r.text)
    print(f"  {len(rows)} districts parsed")
    if not rows:
        raise RuntimeError(
            f"parsed 0 districts from {_URL} — the amCharts dataProvider "
            f"layout has changed; _DISTRICT_RE needs updating"
        )

    obs_date = _aggregate_obs_date(rows)
    if obs_date is None:
        raise RuntimeError(
            f"no parseable obs_date across {len(rows)} districts from {_URL} "
            f"— balloonText date format has changed"
        )

    # Season window. Outside it the page repeats a closed season's final
    # total, which would re-publish the same level every day as noise.
    season_start = _page_date(_SEASON_START_RE, r.text)
    if season_start is None:
        print("  WARNING: could not parse the 'Cumulative (From ...)' label; "
              "skipping the season-window check")
    else:
        season_end = season_start + datetime.timedelta(days=_SEASON_LEN_DAYS)
        if not (season_start <= obs_date <= season_end):
            print(f"  off-season: obs_date={obs_date} outside "
                  f"{season_start}..{season_end} (monsoon onset "
                  f"{season_start}); nothing to publish")
            return [], []

    # Cross-check the page's own as-of label against the district modal date.
    page_as_of = _page_date(_PAGE_AS_OF_RE, r.text)
    if page_as_of and page_as_of != obs_date:
        print(f"  WARNING: page as-of label {page_as_of} != district modal "
              f"date {obs_date}; using the district modal date")

    # Aggregate ONLY over districts reporting on the modal date and carrying
    # both legs. Summing actual and normal over different district subsets
    # would bias the ratio; summing stale rows imports foreign seasons.
    usable = [
        x for x in rows
        if x["obs_date"] == obs_date.isoformat()
        and x["actual_mm"] is not None
        and x["normal_mm"] is not None
    ]
    excluded = len(rows) - len(usable)
    if len(usable) < _MIN_DISTRICTS:
        raise RuntimeError(
            f"only {len(usable)} districts usable on {obs_date} "
            f"(floor {_MIN_DISTRICTS}, {len(rows)} rows parsed, "
            f"{excluded} excluded) — refusing to publish a partial "
            f"all-India aggregate"
        )

    sum_actual = sum(x["actual_mm"] for x in usable)
    sum_normal = sum(x["normal_mm"] for x in usable)
    if sum_normal == 0:
        raise RuntimeError(
            f"sum of normal_mm is 0 across {len(usable)} districts on "
            f"{obs_date} — cannot compute a departure"
        )

    departure_pct = (sum_actual / sum_normal - 1.0) * 100.0
    print(f"  obs_date={obs_date} districts={len(usable)} "
          f"(excluded {excluded}) actual={sum_actual:.1f} "
          f"normal={sum_normal:.1f} departure={departure_pct:+.2f}%")

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
        "IMD.RAINFALL.AI.CUM.ACTUAL_MM": sum_actual,
        "IMD.RAINFALL.AI.CUM.NORMAL_MM": sum_normal,
        "IMD.RAINFALL.AI.CUM.DEPARTURE_PCT": departure_pct,
    }
    for imdr_code, v in values.items():
        observations.append(ObservationRow(
            imdr_code=imdr_code, obs_date=obs_date, vintage=0,
            release_date=now, value=v, ingested_at=now,
        ))
    return indicators, observations


def main() -> int:
    # allow_empty: an off-season run publishes nothing and that is success,
    # not a failed pipeline. Genuine breakage raises instead of returning [].
    return run_main(vendor="imd", topic="rainfall",
                    fetch_fn=run_fetch,
                    description=__doc__.splitlines()[0] if __doc__ else "",
                    country_code="IN",
                    allow_empty=True)


if __name__ == "__main__":
    import sys
    sys.exit(main())
