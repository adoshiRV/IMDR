"""Cotality (formerly CoreLogic) Daily Home Value Index fetcher.

Source: https://www.cotality.com/au/our-data/indices
The page exposes two HTML tables that are server-rendered AS chrome but
*populated* by client-side JS — plain httpx returns the table header with
empty ``<tbody>``. We use a Playwright headed render + BeautifulSoup parse.

Each run = one observation per series for today's date. Idempotent MERGE
means re-running on the same day is harmless; running daily builds up
a real daily time series over time. ABS RPPI is quarterly, so this fills
the high-frequency housing gap that RBA cites in every FSR.

Series (6):
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


def _normalise_city(label: str) -> str:
    return re.sub(r"[\s\*]+$", "", label).strip().lower()


def _fetch_html() -> str:
    from playwright.sync_api import sync_playwright

    if _PROFILE.exists():
        shutil.rmtree(_PROFILE, ignore_errors=True)
    _PROFILE.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            user_data_dir=str(_PROFILE),
            channel="chrome",
            headless=False,
            ignore_https_errors=True,
            viewport={"width": 1400, "height": 900},
            locale="en-AU",
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        try:
            page.goto(COTALITY_URL, wait_until="domcontentloaded", timeout=60_000)
            page.wait_for_selector("table tbody tr td", timeout=20_000)
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
