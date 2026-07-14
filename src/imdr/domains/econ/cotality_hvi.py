"""Cotality (formerly CoreLogic) Home Value Index fetchers.

Source: https://www.cotality.com/au/our-data/indices
The page exposes HTML tables that are server-rendered AS chrome but
*populated* by client-side JS — plain httpx returns the table header with
empty ``<tbody>``. We use a Playwright headless render + BeautifulSoup parse.

Investigated 2026-07-14 (see playground/econ/au/cotality/probe_indices_page.py
+ the two Cotality methodology PDFs it downloaded) for rent/yield coverage and
broader regional/national series. Findings, confirmed against Cotality's own
"Home Value Hedonic Indices FAQs" (Oct 2023) §5.1/§5.3:
  - Rent value index, gross rental yield, and total-return indices ARE part
    of Cotality's methodology (Table 1 of the index-series whitepaper lists
    "Hedonic Index (rents)" and "Rental Yield") but are SUBSCRIBER-ONLY
    ("CoreLogic Indices - Research Pack"), not exposed on this public page.
    No rent/yield table exists anywhere in the rendered DOM (2 tabs checked
    beyond Daily/Monthly: "Daily back series" is a chart+lead-gated Excel
    download only; "Land value index" is a single-suburb Infogram embed).
  - National / Combined Rest of State / Capital+Rest-of-state aggregates are
    likewise subscriber-only (§5.3 "Full Research Indices suite"). Not
    obtainable by scraping this page.
  - The public page DOES have a second, previously-unscraped tab — "Monthly
    values" — covering 3 MORE capital-city regions (Darwin, Canberra,
    Hobart) plus a second Brisbane metro definition (ABS GCCSA boundary,
    excluding Gold Coast) alongside the "Brisbane (inc Gold Coast)" cut
    already captured by the daily table. That is the only additional,
    freely-scrapable coverage available — see cotality_hvi_monthly.py.

Series (6, daily, All Dwellings):
  COTALITY.HVI.SYDNEY.AU
  COTALITY.HVI.MELBOURNE.AU
  COTALITY.HVI.BRISBANE.AU
  COTALITY.HVI.ADELAIDE.AU
  COTALITY.HVI.PERTH.AU
  COTALITY.HVI.FIVE_CAPITAL_AGG.AU
"""
from __future__ import annotations

import re
import shutil
from datetime import date, datetime
from pathlib import Path

from imdr.domains.econ.schema import IndicatorRow, ObservationRow

_REPO_ROOT = Path(__file__).resolve().parents[4]
_PROFILE = _REPO_ROOT / "data" / "econ" / "au" / "cotality" / "profile"

COTALITY_URL = "https://www.cotality.com/au/our-data/indices"

CITY_MAP: dict[str, tuple[str, str]] = {
    "sydney":                       ("SYDNEY",                "Sydney"),
    "melbourne":                    ("MELBOURNE",             "Melbourne"),
    "brisbane":                     ("BRISBANE",              "Brisbane"),
    "adelaide":                     ("ADELAIDE",              "Adelaide"),
    "perth":                        ("PERTH",                 "Perth"),
    "5 capital city aggregate":     ("FIVE_CAPITAL_AGG",      "5-capital-city aggregate"),
}

# Monthly Values tab — superset of CITY_MAP plus Darwin/Canberra/Hobart and
# the second Brisbane metro definition (see module docstring). Keys are the
# *literal* city labels used in that table (post _normalise_city), which
# differ slightly from CITY_MAP's daily-table labels (e.g. the daily table's
# Brisbane row carries a "*incl Gold Coast" footnote instead of the inline
# "(inc Gold Coast)" qualifier used here).
MONTHLY_REGION_MAP: dict[str, tuple[str, str]] = {
    "sydney":                        ("SYDNEY",           "Sydney"),
    "melbourne":                     ("MELBOURNE",        "Melbourne"),
    "brisbane (inc gold coast)":     ("BRISBANE",         "Brisbane (incl. Gold Coast)"),
    "brisbane":                      ("BRISBANE_GCCSA",   "Brisbane (ABS GCCSA boundary, excl. Gold Coast)"),
    "adelaide":                      ("ADELAIDE",         "Adelaide"),
    "perth":                         ("PERTH",            "Perth"),
    "5 capital city aggregate":      ("FIVE_CAPITAL_AGG", "5-capital-city aggregate"),
    "darwin":                        ("DARWIN",           "Darwin"),
    "canberra":                      ("CANBERRA",         "Canberra"),
    "hobart":                        ("HOBART",           "Hobart"),
}


def _normalise_city(label: str) -> str:
    return re.sub(r"[\s\*]+$", "", label).strip().lower()


def _fetch_html() -> str:
    from playwright.sync_api import sync_playwright

    if _PROFILE.exists():
        shutil.rmtree(_PROFILE, ignore_errors=True)
    _PROFILE.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as pw:
        # Headless verified 2026-06-11: page JS still populates the tbody
        # under headless and the 6 series extract cleanly.
        ctx = pw.chromium.launch_persistent_context(
            user_data_dir=str(_PROFILE),
            channel="chrome",
            headless=True,
            ignore_https_errors=True,
            viewport={"width": 1400, "height": 900},
            locale="en-AU",
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        try:
            page.goto(COTALITY_URL, wait_until="domcontentloaded", timeout=60_000)
            page.wait_for_selector("table tbody tr td", timeout=20_000)
            # Monthly Values tab is a separate tbody populated by its own JS
            # pass (selector taken straight from the page's own script, see
            # module docstring) -- wait for it too so a single render serves
            # both the daily and monthly parsers. state="attached" because
            # the Monthly Values tab pane is CSS-hidden (display:none) while
            # the Daily tab is active, so it never becomes "visible".
            page.wait_for_selector("#monthlyIndices .graph-api-data tr",
                                    state="attached", timeout=20_000)
            page.wait_for_timeout(2_000)
            html = page.content()
        finally:
            ctx.close()
    return html


def _parse_daily_table(html: str) -> dict[str, float]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table")
    if not tables:
        return {}
    daily = tables[0]
    values: dict[str, float] = {}
    for tr in daily.find_all("tr"):
        cells = [re.sub(r"\s+", " ", td.get_text(" ")).strip()
                 for td in tr.find_all(["th", "td"])]
        if len(cells) < 4:
            continue
        city = _normalise_city(cells[0])
        if city not in CITY_MAP:
            continue
        today_value: float | None = None
        for cell in cells[1:]:
            try:
                v = float(cell)
            except ValueError:
                continue
            if 50.0 <= v <= 500.0:
                today_value = v
                break
        if today_value is not None:
            values[city] = today_value
    return values


def fetch_today_values() -> dict[str, float]:
    """Render the indices page in Playwright; return {city_norm: today's value}."""
    html = _fetch_html()
    return _parse_daily_table(html)


def build_rows() -> tuple[list[IndicatorRow], list[ObservationRow]]:
    """One run = one daily snapshot (today's value per series)."""
    values = fetch_today_values()
    if not values:
        raise RuntimeError("No rows extracted from Cotality daily HVI table")

    today = date.today()
    now = datetime.now()
    indicators: list[IndicatorRow] = []
    observations: list[ObservationRow] = []
    for city_norm, (suffix, label) in CITY_MAP.items():
        v = values.get(city_norm)
        if v is None:
            print(f"  WARN  {suffix}: not found in rendered table")
            continue
        imdr_code = f"COTALITY.HVI.{suffix}.AU"
        indicators.append(IndicatorRow(
            imdr_code=imdr_code,
            vendor_name="Cotality",
            source_code=f"COTALITY.HVI.{suffix}",
            display_name=f"Cotality Daily Home Value Index — {label} (All dwellings, index)",
            unit="index",
            frequency="DAILY",
            country_iso="AU",
            category="housing",
            is_seasonally_adjusted=False,
        ))
        observations.append(ObservationRow(
            imdr_code=imdr_code,
            obs_date=today,
            vintage=0,
            release_date=now.replace(tzinfo=None),
            value=v,
            ingested_at=now,
        ))
        print(f"  {imdr_code:<48s} today={today} value={v}")
    return indicators, observations


def _parse_month_end_date(html: str) -> date | None:
    """Parse the "30 June 2026" caption above the Monthly Values table."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    tag = soup.find("div", class_="graph-date-month")
    if not tag:
        return None
    text = re.sub(r"\s+", " ", tag.get_text(" ")).strip()
    try:
        return datetime.strptime(text, "%d %B %Y").date()
    except ValueError:
        return None


def _parse_monthly_table(html: str) -> dict[str, float]:
    """Extract the All Dwellings index value per region from the Monthly
    Values tab. Column layout (verified 2026-07-14): cells[0]=city,
    cells[1]=All Dwellings index value, cells[2:]=YoY%/MoM%/icons for All
    Dwellings then Houses then Units -- we only take the All Dwellings index
    value, matching the daily scraper's all-dwellings-only convention.
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    monthly_table = None
    for table in soup.find_all("table"):
        heading = table.find_previous(["h1", "h2", "h3", "h4"])
        if heading and "Monthly Values" in heading.get_text(" "):
            monthly_table = table
            break
    if monthly_table is None:
        return {}

    values: dict[str, float] = {}
    for tr in monthly_table.find_all("tr"):
        cells = [re.sub(r"\s+", " ", td.get_text(" ")).strip()
                 for td in tr.find_all(["th", "td"])]
        if len(cells) < 2:
            continue
        region = _normalise_city(cells[0])
        if region not in MONTHLY_REGION_MAP:
            continue
        try:
            values[region] = float(cells[1])
        except ValueError:
            continue
    return values


def fetch_monthly_values() -> tuple[dict[str, float], date | None]:
    """Render the indices page; return ({region_norm: index value}, month_end_date)."""
    html = _fetch_html()
    return _parse_monthly_table(html), _parse_month_end_date(html)


def build_monthly_rows() -> tuple[list[IndicatorRow], list[ObservationRow]]:
    """One run = one monthly snapshot (latest published month-end value per region).

    Rent/yield and national/combined-regional aggregates are NOT included --
    confirmed subscriber-only, not present anywhere in the public page's DOM
    (see module docstring).
    """
    values, month_end = fetch_monthly_values()
    if not values:
        raise RuntimeError("No rows extracted from Cotality Monthly Values table")
    if month_end is None:
        raise RuntimeError("Could not parse month-end date from Monthly Values tab")

    now = datetime.now()
    indicators: list[IndicatorRow] = []
    observations: list[ObservationRow] = []
    for region_norm, (suffix, label) in MONTHLY_REGION_MAP.items():
        v = values.get(region_norm)
        if v is None:
            print(f"  WARN  {suffix}: not found in rendered monthly table")
            continue
        imdr_code = f"COTALITY.HVI_MONTHLY.{suffix}.AU"
        indicators.append(IndicatorRow(
            imdr_code=imdr_code,
            vendor_name="Cotality",
            source_code=f"COTALITY.HVI_MONTHLY.{suffix}",
            display_name=f"Cotality Home Value Index — {label} (All dwellings, index, monthly)",
            unit="index",
            frequency="MONTHLY",
            country_iso="AU",
            category="housing",
            is_seasonally_adjusted=False,
        ))
        observations.append(ObservationRow(
            imdr_code=imdr_code,
            obs_date=month_end,
            vintage=0,
            release_date=now.replace(tzinfo=None),
            value=v,
            ingested_at=now,
        ))
        print(f"  {imdr_code:<48s} month_end={month_end} value={v}")
    return indicators, observations
