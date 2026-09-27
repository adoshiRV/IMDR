"""RBI DBIE reportId 698 — Daily Forward Premia (Inter-Bank), USD/INR.

Access path: DBIE Home -> search "Forward Premia" -> click the
"Daily Forward Premia (Inter-Bank)" leaf result (breadcrumb: Publication >
Time-Series Publications > External Sector > Daily) -> new SAP-BO tab opens
with the report iframe. Shared scraping scaffolding (persistent Chrome
profile, search->click->new-tab->poll-iframe flow, retry loop, login-wall
detection) lives in `imdr.domains.econ.rbi_dbie_sapbo` -- shared with
rbi_dbie_nri_deposits.py. See that module's docstring for the
sequential-run constraint (one shared Chrome profile dir).

The SAP-BO iframe is NOT accessible headless; Playwright must run with
headless=False. This fetcher REQUIRES A HOST WITH A DISPLAY.

Discovery (2026-07-14): DBIE search for "Forward Premia" surfaces THREE
distinct reports:
  - "Daily Forward Premia (Inter-Bank)"                  reportId 698 (THIS)
  - "Forward Premia (Inter-Bank) (Monthly Average)"       reportId 558
  - "Daily Forward Premia (USD vis-a-vis INR) (in Paise)" (different unit, not used)

reportId 698 carries only 3 tenors -- 1-month / 3-month / 6-month annualised
% p.a. -- there is NO 12-month column in either the daily or monthly report.
Column layout (0-indexed): col0=date, col1=1-month, col2=3-month, col3=6-month.

The live default view renders a rolling ~100-row window (observed
2026-01-27 -> 2026-06-30 on the 2026-07-14 scrape), the same "default
window, not full history" behaviour seen on reportId 417 (NRI Deposits).
A leading FY-label row (e.g. "2026-27") and an ordinal-numbering row
(e.g. "1","2","3","4") precede the actual data rows; both are skipped
generically because neither parses as a date.

Indicator codes:
  INDIA.DBIE.FORWARD_PREMIA.{1M|3M|6M}.IN

Observed values (2026-06-30 scrape): 1M=3.17%, 3M=3.04%, 6M=2.90% p.a.

Run (prod, loads to DB):
    python -m scripts.econ.in.rbi.rbi_dbie_forward_premia

Run (smoke, no DB write):
    python -m scripts.econ.in.rbi.rbi_dbie_forward_premia --no-load
"""
from __future__ import annotations

import datetime
import sys

from imdr.domains.econ.rbi_dbie_sapbo import launch_dbie_context, search_click_scrape
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc

REPORT_ID = "698"
LEAF_TEXT = "Daily Forward Premia (Inter-Bank)"
MAX_ATTEMPTS = 3

# Column (1-indexed; col-0 = date) -> tenor slug. Calibrated from live
# scrape 2026-07-14.
_COL_MAP: dict[int, str] = {
    1: "1M",
    2: "3M",
    3: "6M",
}

_DATE_FORMATS = ("%d-%b-%y", "%d-%b-%Y")


def _parse_date(cell: str) -> datetime.date | None:
    cell = (cell or "").strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.datetime.strptime(cell, fmt).date()
        except ValueError:
            continue
    return None


def _leaf_matcher(page):
    return page.locator(f"a:has-text('{LEAF_TEXT}')")


def _parse_forward_premia(
    table_rows: list[list[str]],
    now: datetime.datetime,
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    """Parse the Daily Forward Premia SAP-BO table.

    Row 0 (header):      ['Date', '1-month', '3-month', '6-month']
    Row 1 (ordinal):      ['1', '2', '3', '4']
    FY-label rows:        ['2026-27', '', '', '']  -> skip (not a date)
    Data rows:            ['30-Jun-26', '3.17', '3.04', '2.90']

    Any row whose col0 does not parse as a %d-%b-%y date is skipped -- this
    generically drops the header, the ordinal row, and the FY-label rows
    without needing separate special-cases for each.
    """
    if not table_rows:
        return [], []

    PREFIX = "INDIA.DBIE.FORWARD_PREMIA"
    indicators: dict[str, IndicatorRow] = {}
    observations: list[ObservationRow] = []
    seen_obs: set[tuple[str, datetime.date]] = set()

    for row in table_rows:
        if not row:
            continue
        d = _parse_date(row[0])
        if d is None:
            continue

        for ci, tenor_slug in _COL_MAP.items():
            if ci >= len(row):
                continue
            cell = (row[ci] or "").replace(",", "").strip()
            if cell in ("", "-", "..", "NA", "*", "N.A.", "N.A"):
                continue
            try:
                value = float(cell)
            except ValueError:
                continue

            imdr_code = f"{PREFIX}.{tenor_slug}.IN"
            if imdr_code not in indicators:
                indicators[imdr_code] = IndicatorRow(
                    imdr_code=imdr_code,
                    vendor_name="RBI",
                    source_code=f"dbie/{REPORT_ID}/{tenor_slug.lower()}",
                    display_name=(
                        f"RBI DBIE Daily Forward Premia (Inter-Bank) — "
                        f"{tenor_slug} (% p.a.)"
                    )[:255],
                    unit="pct",
                    frequency="DAILY",
                    country_iso="IN",
                    category="fx",
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

    since_dt = datetime.date.fromisoformat(since) if since else None
    until_dt = datetime.date.fromisoformat(until) if until else None
    now = datetime.datetime.now(UTC)

    with sync_playwright() as pw:
        ctx = launch_dbie_context(pw)
        try:
            table_rows = search_click_scrape(
                ctx, "Forward Premia", _leaf_matcher, max_attempts=MAX_ATTEMPTS,
            )
        finally:
            ctx.close()

    if not table_rows:
        return [], []

    inds, obs = _parse_forward_premia(table_rows, now)
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
        topic="dbie_forward_premia",
        fetch_fn=run_fetch,
        description="RBI DBIE reportId 698 — Daily Forward Premia (Inter-Bank), USD/INR",
        country_code="IN",
    )


if __name__ == "__main__":
    sys.exit(main())
