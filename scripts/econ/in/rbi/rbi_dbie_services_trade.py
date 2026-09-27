"""RBI DBIE — India's International Trade in Services (ITS), Monthly.

Access path: DBIE Home -> search "International Trade in Services" -> click
the "India's International Trade in Services" leaf result (breadcrumb:
Publication > Time-Series Publications > PART II : QUARTERLY/ MONTHLY
SERIES > EXTERNAL SECTOR > Monthly) -> new SAP-BO tab opens with the report
iframe. Shared scraping scaffolding (persistent Chrome profile,
search->click->new-tab->poll-iframe flow, retry loop, login-wall detection)
lives in `imdr.domains.econ.rbi_dbie_sapbo` -- shared with
rbi_dbie_forward_premia.py / rbi_dbie_nri_deposits.py. See that module's
docstring for the sequential-run constraint (one shared Chrome profile dir).

The SAP-BO iframe is NOT accessible headless; Playwright must run with
headless=False. This fetcher REQUIRES A HOST WITH A DISPLAY.

Discovery (2026-07-14): this is the ONLY DBIE report matching "International
Trade in Services" (a single leaf result, no siblings to disambiguate). It
carries just 3 columns -- headline services Receipts (Exports) / Payments
(Imports) / Net -- no category breakdown (Software/Travel/Transportation/
etc.) is available at monthly frequency; that granular category split
already exists QUARTERLY under `INDIA.RBI_BULLETIN.BOP.{SOFTWARE_SERVICES,
TRAVEL,TRANSPORTATION,INSURANCE,BUSINESS_SERVICES,FINANCIAL_SERVICES,
COMMUNICATION_SERVICES,G_N_I_E,MISCELLANEOUS}.{CREDIT|DEBIT|NET}.IN` (T40
parser `parse_bop` in rbi_bulletin.py). This fetcher's value-add is
FREQUENCY (monthly vs quarterly), not new categories.

Report Duration shown on the search-result card: 30-APR-2018 -> 30-JUN-2025
(matches the scraped row range exactly).

Column layout (0-indexed): col0=month ("Mon-YYYY"), col1=Receipts (Exports),
col2=Payments (Imports), col3=Net. Data rows run newest-first (Jun-2025 down
to Apr-2018).

Known duplicate-row quirk (2026-07-14 scrape): "Mar-2020" appears TWICE with
different values (a revision artifact in the underlying SAP-BO table, same
pattern RBI shows elsewhere for FY-boundary rows, e.g. T34's Mar(P)). The
parser keeps the FIRST occurrence encountered (i.e., the one appearing
higher in the newest-first table) and silently drops later duplicates for
the same (imdr_code, obs_date) key.

Also checked (2026-07-14): searching "Balance of Payments" surfaces the
"Standard Presentation ... BPM6" and "Key Components of India's Balance of
Payments" report families -- both ANNUAL, both re-aggregations of lines
already covered (more granularly) by quarterly T40 `parse_bop`. Not built
here to avoid duplicating T40 under a different code namespace.

Indicator codes:
  INDIA.DBIE.SERVICES_TRADE.{EXPORTS|IMPORTS|NET}.IN

Observed values (2026-06-30 scrape, Jun-2025): Exports=32,108 / Imports=15,900
/ Net=16,208 (USD mn) -- in line with the ~$30-40bn/month sanity band.

Run (prod, loads to DB):
    python -m scripts.econ.in.rbi.rbi_dbie_services_trade

Run (smoke, no DB write):
    python -m scripts.econ.in.rbi.rbi_dbie_services_trade --no-load
"""
from __future__ import annotations

import datetime
import re
import sys

from imdr.domains.econ.rbi_dbie_sapbo import launch_dbie_context, search_click_scrape
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc

SEARCH_TERM = "International Trade in Services"
MAX_ATTEMPTS = 3

# Column (1-indexed; col-0 = month) -> measure slug. Calibrated from live
# scrape 2026-07-14.
_COL_MAP: dict[int, str] = {
    1: "EXPORTS",
    2: "IMPORTS",
    3: "NET",
}

_MONTH_RE = re.compile(r"^([A-Za-z]{3})-(\d{4})$")


def _parse_month(cell: str) -> datetime.date | None:
    cell = (cell or "").strip()
    m = _MONTH_RE.match(cell)
    if not m:
        return None
    try:
        return datetime.datetime.strptime(f"{m.group(1)} {m.group(2)}", "%b %Y").date()
    except ValueError:
        return None


def _leaf_matcher(page):
    return page.locator(f"a:has-text('{SEARCH_TERM}')")


def _parse_services_trade(
    table_rows: list[list[str]],
    now: datetime.datetime,
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    """Parse the ITS SAP-BO table.

    Row 0 (header):   ['Month', 'Receipts (Exports)', 'Payments (Imports)', 'Net']
    Row 1 (ordinal):  ['1', '2', '3', '4']
    Data rows:        ['Jun-2025', '32,108', '15,900', '16,208']

    Any row whose col0 does not parse as a "Mon-YYYY" month is skipped --
    this generically drops the header and ordinal rows.
    """
    if not table_rows:
        return [], []

    PREFIX = "INDIA.DBIE.SERVICES_TRADE"
    indicators: dict[str, IndicatorRow] = {}
    observations: list[ObservationRow] = []
    seen_obs: set[tuple[str, datetime.date]] = set()

    for row in table_rows:
        if not row:
            continue
        d = _parse_month(row[0])
        if d is None:
            continue

        for ci, measure_slug in _COL_MAP.items():
            if ci >= len(row):
                continue
            cell = (row[ci] or "").replace(",", "").strip()
            if cell in ("", "-", "..", "NA", "*", "N.A.", "N.A"):
                continue
            try:
                value = float(cell)
            except ValueError:
                continue

            imdr_code = f"{PREFIX}.{measure_slug}.IN"
            if imdr_code not in indicators:
                indicators[imdr_code] = IndicatorRow(
                    imdr_code=imdr_code,
                    vendor_name="RBI",
                    source_code=f"dbie/its/{measure_slug.lower()}",
                    display_name=(
                        f"RBI DBIE India's International Trade in Services — "
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

    since_dt = datetime.date.fromisoformat(since) if since else None
    until_dt = datetime.date.fromisoformat(until) if until else None
    now = datetime.datetime.now(UTC)

    with sync_playwright() as pw:
        ctx = launch_dbie_context(pw)
        try:
            table_rows = search_click_scrape(
                ctx, SEARCH_TERM, _leaf_matcher, max_attempts=MAX_ATTEMPTS,
            )
        finally:
            ctx.close()

    if not table_rows:
        return [], []

    inds, obs = _parse_services_trade(table_rows, now)
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
        topic="dbie_services_trade",
        fetch_fn=run_fetch,
        description="RBI DBIE — India's International Trade in Services (ITS), Monthly",
        country_code="IN",
    )


if __name__ == "__main__":
    sys.exit(main())
