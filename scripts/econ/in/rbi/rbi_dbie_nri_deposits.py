"""RBI DBIE reportId 417 — NRI Deposits (Monthly, ~Apr-2018 → present).

Access path: DBIE Home → search "NRI Deposits" → click monthly leaf
(breadcrumb: Publication > Time-Series Publications > External Sector > Monthly)
→ new SAP-BO tab opens with the report iframe.

The SAP-BO iframe is NOT accessible headless; Playwright must run with
headless=False. This fetcher REQUIRES A HOST WITH A DISPLAY (same constraint
as rbi_bulletin.py which uses TSPD-protected XLSX downloads). On a display-less
server, run under a virtual framebuffer (Xvfb).

reportId 417 has 8 series: 4 schemes × 2 measures:
  schemes : NRI_TOTAL  | FCNRB  | NRERA  | NRO
  measures: OUTSTANDING (stock, USD mn) | FLOW (net inflows, USD mn)

Indicator codes (parallel to T34, NOT overwriting):
  INDIA.DBIE.NRI_DEPOSITS.{SCHEME}.{MEASURE}.IN
  where SCHEME ∈ {NRI_TOTAL, FCNRB, NRERA, NRO}
        MEASURE ∈ {OUTSTANDING, FLOW}

FY date parsing: FY year rows provide context; month abbreviations are
resolved against the current FY. Apr-Dec → FY start year; Jan-Mar → start year+1.
E.g. "2025-26" + "Mar." → 2026-03-01.

Run (prod, loads to DB):
    python -m scripts.econ.in.rbi.rbi_dbie_nri_deposits

Run (smoke, no DB write):
    python -m scripts.econ.in.rbi.rbi_dbie_nri_deposits --no-load
"""
from __future__ import annotations

import datetime
import re
import sys
from pathlib import Path

from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc

# Profile dir under the repo data tree (country-first), consistent with rbi_bulletin.py.
# parents[0]=rbi, [1]=in, [2]=econ, [3]=scripts, [4]=repo root
_REPO_ROOT = Path(__file__).resolve().parents[4]
PROFILE = _REPO_ROOT / "data" / "econ" / "in" / "rbi" / "_profile_dbie"

REPORT_ID = "417"

# Exact column → (scheme_slug, measure_slug) mapping, calibrated from
# live scrape 2026-06-23. Columns are 1-indexed (col-0 = date).
_COL_MAP: dict[int, tuple[str, str]] = {
    1: ("NRI_TOTAL", "OUTSTANDING"),
    2: ("FCNRB",     "OUTSTANDING"),
    3: ("NRERA",     "OUTSTANDING"),
    4: ("NRO",       "OUTSTANDING"),
    5: ("NRI_TOTAL", "FLOW"),
    6: ("FCNRB",     "FLOW"),
    7: ("NRERA",     "FLOW"),
    8: ("NRO",       "FLOW"),
}

# Month abbreviation → (month_int, fy_offset)
# fy_offset: 0 = current FY start year, 1 = FY start year + 1
# Indian FY: Apr(1)…Mar(12). "2025-26" → start_year=2025.
_MONTH_MAP: dict[str, tuple[int, int]] = {
    "apr": (4, 0), "may": (5, 0), "jun": (6, 0),
    "jul": (7, 0), "aug": (8, 0), "sep": (9, 0),
    "oct": (10, 0), "nov": (11, 0), "dec": (12, 0),
    "jan": (1, 1), "feb": (2, 1), "mar": (3, 1),
}


def _scrape_iframe_table(page) -> list[list[str]]:
    """Extract the largest leaf table from the openDocChildFrame."""
    target = None
    for f in page.frames:
        if "openDocChildFrame" in (f.name or "") or "WebiView" in (f.url or ""):
            target = f
            break
    if target is None:
        return []
    return target.evaluate("""() => {
        const leafTables = Array.from(document.querySelectorAll('table'))
            .filter(t => t.querySelectorAll('table').length === 0);
        if (leafTables.length === 0) return [];
        let best = leafTables[0];
        let bestRows = best.querySelectorAll('tr').length;
        for (const t of leafTables) {
            const n = t.querySelectorAll('tr').length;
            if (n > bestRows) { best = t; bestRows = n; }
        }
        const out = [];
        for (const tr of best.querySelectorAll('tr')) {
            const cells = Array.from(tr.querySelectorAll('td, th'))
                .map(c => (c.textContent || '').trim());
            if (cells.some(c => c.length > 0)) out.push(cells);
        }
        return out;
    }""")


def _parse_nri_deposits(
    table_rows: list[list[str]],
    now: datetime.datetime,
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    """Parse the NRI Deposits SAP-BO table.

    Row 0 (super-header): ['Month', '', 'Outstanding', '', 'Inflows (+)/...']
    Row 1 (sub-header):   ['1 NRI Deposits', '1.1 FCNR(B)', '1.2 NR(E)RA', '1.3 NRO',
                           '1 NRI Deposits', '1.4 FCNR(B)', '1.5 NR(E)RA', '1.6 NRO']
    FY year rows:         ['2026-27', '', '', ...]  → skip
    Data rows:            ['Apr.', value, value, ...]
    """
    if not table_rows:
        return [], []

    PREFIX = "INDIA.DBIE.NRI_DEPOSITS"
    indicators: dict[str, IndicatorRow] = {}
    observations: list[ObservationRow] = []
    seen_obs: set[tuple[str, datetime.date]] = set()

    current_fy_start: int | None = None

    for row in table_rows[2:]:
        if not row:
            continue
        col0 = (row[0] or "").strip()

        fy_match = re.match(r"^(\d{4})-(\d{2,4})$", col0)
        if fy_match:
            current_fy_start = int(fy_match.group(1))
            continue

        month_key = col0.rstrip(".").lower()[:3]
        mo = _MONTH_MAP.get(month_key)
        if mo is None or current_fy_start is None:
            continue

        month_int, fy_offset = mo
        year = current_fy_start + fy_offset
        try:
            d = datetime.date(year, month_int, 1)
        except ValueError:
            continue

        for ci, (scheme_slug, measure_slug) in _COL_MAP.items():
            if ci >= len(row):
                continue
            cell = (row[ci] or "").replace(",", "").strip()
            if cell in ("", "-", "..", "NA", "*", "N.A.", "N.A"):
                continue
            try:
                value = float(cell)
            except ValueError:
                continue

            imdr_code = f"{PREFIX}.{scheme_slug}.{measure_slug}.IN"
            if imdr_code not in indicators:
                indicators[imdr_code] = IndicatorRow(
                    imdr_code=imdr_code,
                    vendor_name="RBI",
                    source_code=f"dbie/{REPORT_ID}/{scheme_slug.lower()}_{measure_slug.lower()}",
                    display_name=(
                        f"RBI DBIE NRI Deposits — "
                        f"{scheme_slug.replace('_', ' ')} "
                        f"{measure_slug.title()} (USD mn)"
                    )[:255],
                    unit="usd_mn",
                    frequency="MONTHLY",
                    country_iso="IN",
                    category="bop",
                    is_seasonally_adjusted=False,
                    bbg_ticker=None,
                )
            key = (imdr_code, d)
            if key in seen_obs:
                continue
            seen_obs.add(key)
            observations.append(ObservationRow(
                imdr_code=imdr_code,
                obs_date=d,
                vintage=0,
                release_date=now,
                value=value,
                ingested_at=now,
            ))

    return list(indicators.values()), observations


def run_fetch(
    since: str | None,
    until: str | None,
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    from playwright.sync_api import sync_playwright

    PROFILE.mkdir(parents=True, exist_ok=True)

    since_dt = datetime.date.fromisoformat(since) if since else None
    until_dt = datetime.date.fromisoformat(until) if until else None
    now = datetime.datetime.now(UTC)

    table_rows: list[list[str]] = []

    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE),
            channel="chrome",
            headless=False,
            accept_downloads=True,
            viewport={"width": 1400, "height": 900},
        )
        page = ctx.new_page()
        try:
            print("Loading DBIE home...")
            page.goto(
                "https://data.rbi.org.in/DBIE/#/dbie/home",
                timeout=60000, wait_until="domcontentloaded"
            )
            try:
                page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            page.wait_for_timeout(3000)

            print("Searching for 'NRI Deposits'...")
            search_input = page.locator("input[placeholder=Search]").first
            search_input.click(timeout=8000)
            search_input.fill("NRI Deposits")
            page.keyboard.press("Enter")
            page.wait_for_timeout(3000)

            pages_before = len(ctx.pages)
            try:
                leaf = (
                    page.locator("a:has-text('NRI Deposits')")
                    .filter(has_not_text="Outstanding")
                    .filter(has_not_text="Inflows")
                    .filter(has_not_text="Rupees")
                    .filter(has_not_text="US Dollars")
                )
                n = leaf.count()
                print(f"  NRI Deposits leaf candidates: {n}")
                if n == 0:
                    all_nri = page.evaluate("""() => {
                        return Array.from(document.querySelectorAll('a'))
                            .map(el => (el.textContent||'').replace(/\\s+/g,' ').trim())
                            .filter(t => t.includes('NRI'));
                    }""")
                    print(f"  All NRI links: {all_nri}")
                    ctx.close()
                    return [], []
                leaf.first.click(timeout=10000)
            except Exception as e:
                print(f"  Leaf click failed: {e}")
                ctx.close()
                return [], []

            deadline = 30
            while len(ctx.pages) == pages_before and deadline > 0:
                page.wait_for_timeout(1000)
                deadline -= 1
            if len(ctx.pages) == pages_before:
                print("  No new SAP-BO tab opened")
                ctx.close()
                return [], []

            sap_page = ctx.pages[-1]
            print(f"  SAP-BO tab: {sap_page.url[:120]}")

            rows: list[list[str]] = []
            for attempt in range(10):
                sap_page.wait_for_timeout(5000)
                rows = _scrape_iframe_table(sap_page)
                if rows and len(rows) > 3:
                    print(f"  iframe ready after {(attempt+1)*5}s: {len(rows)} rows")
                    break
                print(f"  iframe attempt {attempt+1}: {len(rows)} rows")
            else:
                print(f"  iframe timeout ({len(rows)} rows)")

            table_rows = list(rows)
            sap_page.close()

        finally:
            if page in ctx.pages:
                page.close()
        ctx.close()

    if not table_rows:
        return [], []

    inds, obs = _parse_nri_deposits(table_rows, now)
    print(f"  parsed: {len(inds)} indicators / {len(obs)} raw obs")

    if since_dt or until_dt:
        obs = [
            o for o in obs
            if (since_dt is None or o.obs_date >= since_dt)
            and (until_dt is None or o.obs_date <= until_dt)
        ]
        print(f"  after date filter: {len(obs)} obs")

    return inds, obs


def main() -> int:
    return run_main(
        vendor="rbi",
        topic="dbie_nri_deposits",
        fetch_fn=run_fetch,
        description="RBI DBIE reportId 417 — NRI Deposits (Monthly, ~2018 → present)",
        country_code="IN",
    )


if __name__ == "__main__":
    sys.exit(main())
