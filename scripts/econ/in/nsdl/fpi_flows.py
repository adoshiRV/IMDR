"""NSDL FPI daily flows (debt + equity) — India external-sector Stage 2.

Source: NSDL's "Export to Excel" download from the **Current Month**
report, https://www.fpi.nsdl.co.in/web/Reports/Monthly.aspx (Home » FPI
Investments » Current Month). The exported file is HTML saved with a
``.xls`` extension and covers the WHOLE CURRENT MONTH (~10-14 trading
days per run) — see the module docstring in
``src/imdr/domains/econ/nsdl_fpi.py`` for the exact table shape, the
grand-Total-row quirk, and why this replaced an earlier DOM-scrape
approach against ``Latest.aspx`` (pandas auto-expands the vendor's HTML
rowspans on export-parse, which eliminated a whole class of mapping bugs
the DOM-scrape path had to handle manually).

ACCESS CONSTRAINT — CDP-attach to the user's Chrome is REQUIRED
================================================================
NSDL is blocked from the RV corp network for direct httpx/Playwright-
launched fetches (``RemoteProtocolError``). It only loads inside the
user's own authenticated, normal-network Chrome session — same family
of block as AOFM (see ``playground/econ/aofm/connect_aofm.py`` +
[[feedback-aofm-use-msedge-not-chrome]]). This fetcher does NOT launch a
fresh browser profile; it attaches to an already-running Chrome via the
Chrome DevTools Protocol (CDP), and drives the download via CDP's own
``Page.setDownloadBehavior`` (Playwright's ``expect_download`` does not
fire over ``connect_over_cdp`` -- the file still downloads fine, but
through Chrome's own download manager, not Playwright's event handler;
confirmed live 2026-07-15).

**User-side setup, once per run session (repeat these steps if the
debug-port Chrome gets closed):**

  1. Launch a SECOND Chrome window on a dedicated profile + debug port
     (port 9333, distinct from AOFM's 9222 so both can run side by
     side):

         "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" ^
             --remote-debugging-port=9333 ^
             --user-data-dir="C:\\Users\\adoshi\\AppData\\Local\\Google\\Chrome\\User Data NSDL" ^
             --profile-directory="Default" ^
             https://www.fpi.nsdl.co.in/web/Reports/Monthly.aspx

  2. Verify that window renders the "Current Month (Trends in FPI/FII
     Investments)" table.

  3. Then run this fetcher (conda ``imdr`` env):

         python -m scripts.econ.in.nsdl.fpi_flows

     It connects to ``http://localhost:9333``, finds (or opens) the
     Monthly.aspx tab, clicks "Export to Excel", waits for the download
     to land in ``data/econ/in/nsdl/_downloads/``, parses it, and never
     closes or navigates the user's Chrome away from NSDL on exit.

If CDP attach fails (debug-port Chrome not running), or the download
never lands, or the export's table shape is unrecognisable, ``run_fetch``
raises ``RuntimeError`` with diagnostics rather than silently producing
zero rows.

NO GENUINE EMPTY-DAY STATE: the Current Month export always contains at
least the days published so far this month, so ``run_fetch`` treats
"no tables found", "0 rows resolved", and "0 observations built" as hard
failures (``RuntimeError``, non-zero exit), never a silent empty return.
``allow_empty`` is deliberately left at its default (``False``).

Indicators (33 total — 4 measures x 8 asset classes + 1 conversion rate):
  INDIA.NSDL.FPI.{EQUITY|DEBT_GENERAL|DEBT_VRR|DEBT_FAR|HYBRID|MUTUAL_FUNDS|AIF|TOTAL}.NET.INR_CR.IN
  INDIA.NSDL.FPI.{...}.NET.USD_MN.IN
  INDIA.NSDL.FPI.{...}.GROSS_PURCHASE.INR_CR.IN
  INDIA.NSDL.FPI.{...}.GROSS_SALE.INR_CR.IN
  INDIA.NSDL.FPI.USDINR_CONVERSION.IN                      (unit=ratio, category=fx)

Deliberately NOT parsed: the export's second table, "Daily Trends in
FPI Derivative Trades" (Index/Stock/IRF/Currency/Commodity F&O — buy/
sell contracts + open interest, also multi-day). Optional/nice-to-have
per the coverage-plan discussion; skipped for this Stage 2 build to
keep scope to the cash-flow BoP/capital-account signal.

Cell mapping (see docs/admin/econ/india/in_coverage_plan.md, item A16):
  3.3 Capital + Financial Account — FPI portfolio flows (debt + equity)

HISTORY / BACKFILL
================================================================
The Current Month export already gives ~10-14 days per run (the whole
month to date), so daily runs naturally self-heal any single missed day
within the current month via the loader's idempotent MERGE. For
BACKFILL of history predating this fetcher's first run, per
docs/admin/econ/india/nsdl_fpi_sources.md (portal menu map) the NSDL
FPI portal has an **Archive** report
(``https://www.fpi.nsdl.co.in/web/Reports/Archive.aspx``, confirmed URL
2026-07-15) that appears to expose a date/period selector for past
months' daily-trends reports, and calendar/financial-year aggregate
views (``Yearwise.aspx?RptType=5|6``) for coarser long-history. NOT YET
built — recommend probing the Archive report's export shape (same
CDP-attach + ``pd.read_html`` pattern as this fetcher should apply) as
a follow-on once this Stage 2 daily fetcher is confirmed stable.

Candidate follow-on streams (explicitly out of scope for this build):
AUC (holdings/stock), Debt Utilisation Status (General/VRR/FAR
headroom), ODI/P-Note outstanding value — see the coverage-plan doc's
"candidate" rows.
"""
from __future__ import annotations

import datetime as _dt
import sys

from imdr.domains.econ.nsdl_fpi import (
    DEFAULT_CDP_URL,
    build_indicator_rows,
    fetch_export_xls,
    load_export_tables,
    parse_cash_table,
)
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main


def run_fetch(
    since: str | None,
    until: str | None,
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    xls_path = fetch_export_xls(cdp_url=DEFAULT_CDP_URL)
    cash_df, _derivatives_df = load_export_tables(xls_path)

    rows = parse_cash_table(cash_df)
    if not rows:
        raise RuntimeError(
            f"NSDL export at {xls_path} was read but 0 rows resolved "
            "against ASSET_CLASS_MAP/ROUTE_MAP. This means every row's "
            "asset-class/route label failed to match -- most likely "
            "NSDL relabelled the table (see the WARN lines just above "
            "listing the raw (asset, route) pairs that didn't resolve), "
            "or the export's shape changed. Not a genuine empty period."
        )

    if since:
        since_d = _dt.date.fromisoformat(since)
        rows = [r for r in rows if r.reporting_date >= since_d]
    if until:
        until_d = _dt.date.fromisoformat(until)
        rows = [r for r in rows if r.reporting_date <= until_d]
    if (since or until) and not rows:
        raise RuntimeError(
            f"--since/--until filter left 0 rows (since={since!r}, "
            f"until={until!r}) -- the Current Month export only ever "
            "covers the current month, so a filter window outside that "
            "will always empty out; not a genuine empty period."
        )

    days = sorted({r.reporting_date for r in rows})
    print(f"  parsed {len(rows)} rows across {len(days)} day(s) "
          f"({days[0] if days else '?'} .. {days[-1] if days else '?'}), "
          f"file={xls_path.name}")

    indicators, observations = build_indicator_rows(rows)
    if not observations:
        raise RuntimeError(
            "NSDL rows parsed but no Sub-total/Total rows resolved -- "
            "check ROUTE_MAP against the raw route labels above."
        )
    return indicators, observations


def main() -> int:
    return run_main(
        vendor="nsdl", topic="fpi_flows",
        fetch_fn=run_fetch,
        description=__doc__.splitlines()[0] if __doc__ else "",
        country_code="IN",
        # allow_empty left at its default (False) -- see the module
        # docstring's "NO GENUINE EMPTY-DAY STATE" note.
    )


if __name__ == "__main__":
    sys.exit(main())
