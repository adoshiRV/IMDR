"""NSDL FPI daily flows — "Export to Excel" parser + CDP-attach download.

**Pivoted 2026-07-15 away from DOM-table scraping** (the previous
`Latest.aspx` rowspan-scrape approach — see git history / prior review
rounds for that dead end) **to NSDL's own "Export to Excel" download**,
confirmed simpler and MORE robust:

  - The exported file (from the "Current Month" report,
    ``https://www.fpi.nsdl.co.in/web/Reports/Monthly.aspx``) is **HTML
    saved with a ``.xls`` extension** — ``pandas.read_html(path)``
    parses it directly, no browser/DOM needed once downloaded.
  - It covers the **WHOLE CURRENT MONTH** (confirmed 2026-07-14/15: ~10
    trading days, ~25 rows/day), not just the latest single day — so
    every fetcher run naturally backfills the month-to-date, not just
    appends one row.
  - **pandas auto-expands the vendor's HTML rowspans** when parsing the
    table — the Reporting Date and Asset Class columns come back
    pre-filled on every row. This eliminates entirely the rowspan/
    grid-expansion machinery an earlier version of this module had to
    build for the DOM-scrape path (and the subtle mapping bug that
    approach produced — see below).
  - Earlier "Export to Excel breaks the page" finding was a false
    alarm from probing ``Latest.aspx``'s export specifically; the
    **Monthly.aspx** "Current Month" report's Export to Excel works
    cleanly (confirmed live 2026-07-15 via CDP-attach, see
    ``playground/econ/in/nsdl/dump_monthly_export.py``).

Table shape (table 0 of 2 returned by ``pd.read_html``; columns are
UNSTABLE by name — pandas embeds the page's "on <date>" title and a
disclaimer sentence into the MultiIndex column labels, which change
daily — so this module reads columns POSITIONALLY, never by name):

    [0] Reporting Date | [1] Asset Class (Equity / Debt-General Limit /
    Debt-VRR / Debt-FAR / Hybrid / Mutual Funds / AIFs) | [2] Investment
    Route (Stock Exchange / Primary market & others / Sub-total, or for
    Mutual Funds: Equity/Debt/Hybrid/Solution-oriented/Other schemes) |
    [3] Gross Purchases (Rs Crore) | [4] Gross Sales (Rs Crore) |
    [5] Net Investment (Rs Crore) | [6] Net Investment US$ million |
    [7] Conversion (1 USD to INR, e.g. "Rs.95.8336") | [8] (trailing
    empty column, always NaN — ignored).

GRAND-TOTAL ROW QUIRK (confirmed live via the real export, both
2026-07-14 and 2026-07-15 files): each day's grand total is a row with
**Investment Route == "Total"** (not "Sub-total") — but its Asset Class
column shows whichever asset class happens to be LAST that day (AIFs on
both observed files), because pandas forward-fills the vendor's
rowspan from the AIFs group onto this row too. Example (14-Jul-2026):
``AIFs | Total | 12384.55 | 15357.27 | (2972.72) | (310.20)``. The FIX:
**``route == "Total"`` is the authoritative signal** for the grand-total
row — the Asset Class column is IGNORED for that row and the row is
mapped to its own ``TOTAL`` asset class regardless of what it shows.
(An earlier DOM-scrape version of this module discovered this same
quirk the hard way, at the HTML-rowspan level with a ``<tr
class="total">`` CSS marker; the export path hits the identical
vendor-side rowspan quirk but pandas' auto-expansion makes fixing it
much simpler — one ``route``-text check, no DOM/grid code at all.)

Negative net flows are shown in parentheses, e.g. ``(263.07)`` for an
outflow of US$263.07mn — ``coerce_float`` parses ``(x)`` as ``-x``. The
Conversion column carries a ``"Rs."`` prefix, e.g. ``"Rs.95.8336"`` —
``coerce_conversion`` strips it before parsing.

There is a SECOND table in the export (index 1), "Daily Trends in FPI
Derivative Trades" (Index/Stock/Interest-Rate/Currency/Commodity F&O —
Buy/Sell contracts + amount, and end-of-day Open Interest, also
multi-day). NOT parsed by this module — deliberately out of scope for
the Stage 2 cash-flows build (nice-to-have per the coverage-plan
follow-on list, not the headline BoP/capital-account signal); a future
module can add a parser for it without touching this one.

NETWORK CONSTRAINT: NSDL is blocked from the RV corp network for direct
httpx/Playwright-launched fetches (``RemoteProtocolError``). It only
loads inside the user's own authenticated Chrome. See
``scripts/econ/in/nsdl/fpi_flows.py`` module docstring for the exact
CDP-attach setup the user must do before running the prod fetcher.

See docs/admin/econ/india/nsdl_fpi_sources.md for the full portal menu
map (Archive/backfill candidates, AUC holdings, debt-utilisation
headroom, ODI/P-Note — all out of scope for this Stage 2 build).
"""
from __future__ import annotations

import datetime
import re
import time
from dataclasses import dataclass
from pathlib import Path

from imdr.domains.econ.schema import IndicatorRow, ObservationRow

UTC = datetime.timezone.utc

MONTHLY_URL = "https://www.fpi.nsdl.co.in/web/Reports/Monthly.aspx"
DEFAULT_CDP_URL = "http://localhost:9333"

_REPO_ROOT = Path(__file__).resolve().parents[4]
DOWNLOAD_DIR = _REPO_ROOT / "data" / "econ" / "in" / "nsdl" / "_downloads"

# Positional column indices into the export's table 0 (see module
# docstring for why positional, not name-based).
_COL_DATE = 0
_COL_ASSET = 1
_COL_ROUTE = 2
_COL_GROSS_PURCHASE = 3
_COL_GROSS_SALE = 4
_COL_NET_INR = 5
_COL_NET_USD = 6
_COL_CONVERSION = 7
_N_COLS = 8

# Deliberately NO bare "debt" -> DEBT_GENERAL entry: no confirmed bare
# "Debt" row has been observed, and a real Debt-aggregate row (summing
# General/VRR/FAR) would silently fold into DEBT_GENERAL and corrupt it
# if this alias existed. An unmapped bare-"Debt" label surfaces via the
# unmapped-label WARN in ``parse_cash_table`` instead of being guessed at.
ASSET_CLASS_MAP: dict[str, str] = {
    "equity": "EQUITY",
    "debt-general limit": "DEBT_GENERAL",
    "debt general limit": "DEBT_GENERAL",
    "debt-vrr": "DEBT_VRR",
    "debt vrr": "DEBT_VRR",
    "debt-far": "DEBT_FAR",
    "debt far": "DEBT_FAR",
    "hybrid": "HYBRID",
    "mutual funds": "MUTUAL_FUNDS",
    "mutual fund": "MUTUAL_FUNDS",
    "aifs": "AIF",
    "aif": "AIF",
    # Defensive only -- the grand-total row is actually identified by
    # route == "Total" (see parse_cash_table), not this key. Kept in case
    # some future export variant literally labels the asset-class column
    # "Total" on a row that ISN'T the vendor's rowspan-inherited quirk.
    "total": "TOTAL",
    "grand total": "TOTAL",
}

# Deliberately NO "total"/"grand total" -> SUBTOTAL entries: the grand
# Total row is identified by its OWN route text ("Total", distinct from
# "Sub-total") in parse_cash_table, not via this map. See module docstring
# for the confirmed live quirk this guards against (Asset Class column
# showing the wrong -- rowspan-inherited -- asset class on that row).
ROUTE_MAP: dict[str, str] = {
    "stock exchange": "STOCK_EXCHANGE",
    "primary market & others": "PRIMARY_OTHER",
    "primary market and others": "PRIMARY_OTHER",
    "primary market": "PRIMARY_OTHER",
    "sub total": "SUBTOTAL",
    "sub-total": "SUBTOTAL",
    "subtotal": "SUBTOTAL",
}

_DATE_FORMATS = ("%d-%b-%Y", "%d-%B-%Y", "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d")


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip().lower()


def coerce_float(raw: str | None) -> float | None:
    """Parse an NSDL table cell into a float. ``None`` for blank/non-numeric.

    Handles thousands-separator commas and parenthesised negatives, e.g.
    ``(263.07)`` -> ``-263.07`` — confirmed 2026-07-14/15 as the vendor's
    negative-flow convention (see module docstring).
    """
    if raw is None:
        return None
    s = raw.strip().replace(",", "")
    if not s or s in {"-", "--", "NA", "N/A"}:
        return None
    neg = s.startswith("(") and s.endswith(")")
    if neg:
        s = s[1:-1]
    try:
        v = float(s)
    except ValueError:
        return None
    return -v if neg else v


def coerce_conversion(raw: str | None) -> float | None:
    """Parse the "Conversion" cell, e.g. ``"Rs.95.8336"`` -> ``95.8336``."""
    if raw is None:
        return None
    s = raw.strip()
    s = re.sub(r"(?i)^rs\.?\s*", "", s)
    s = re.sub(r"^₹\s*", "", s)
    return coerce_float(s)


def coerce_date(raw: str | None) -> datetime.date | None:
    """Parse an NSDL "Reporting Date" cell, e.g. ``14-Jul-2026``."""
    if raw is None:
        return None
    s = raw.strip()
    if not s:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


@dataclass
class FPIFlowRow:
    reporting_date: datetime.date
    asset_class: str  # ASSET_CLASS_MAP suffix, e.g. "EQUITY", or "TOTAL"
    route: str  # ROUTE_MAP suffix, e.g. "SUBTOTAL"
    gross_purchase_inr_cr: float | None
    gross_sale_inr_cr: float | None
    net_inr_cr: float | None
    net_usd_mn: float | None
    usd_inr_conversion: float | None


def _cell_str(value) -> str:
    """Stringify one pandas cell, treating NaN/None as ``""``."""
    import pandas as pd

    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def parse_cash_table(df) -> list[FPIFlowRow]:
    """Parse table 0 of the NSDL export (a ``pandas.DataFrame``) into
    ``FPIFlowRow`` objects, covering every reporting day present in the
    export (the "Current Month" export carries ~10-14 days per run).

    Reads columns POSITIONALLY (0-7) -- the DataFrame's own column labels
    embed page-specific text (title + disclaimer sentence) that changes
    daily and cannot be relied on as a stable key.

    Rows whose Reporting Date doesn't parse (the trailing blank spacer
    row, the "Note" disclaimer row) or whose Asset Class/Investment Route
    text doesn't resolve to a known label are skipped -- logged via a
    WARN summary so a future NSDL relabel is visible in the run output,
    not silently dropped.

    The grand Total row for each day is identified by
    ``route == "Total"`` (see module docstring for the confirmed
    rowspan-inheritance quirk this guards against) and mapped to its own
    ``TOTAL`` asset class regardless of what its Asset Class column shows.
    """
    out: list[FPIFlowRow] = []
    malformed: list[list[str]] = []
    unmapped: list[tuple[str, str]] = []

    n_rows = len(df)
    for idx in range(n_rows):
        raw_row = df.iloc[idx]
        cells = [_cell_str(raw_row.iloc[i]) for i in range(_N_COLS)]
        if not any(cells):
            continue

        date_s, asset_s, route_s, gp_s, gs_s, net_inr_s, net_usd_s, conv_s = cells
        reporting_date = coerce_date(date_s)
        if reporting_date is None:
            malformed.append(cells)
            continue

        route_norm = _norm(route_s)
        if route_norm == "total":
            # Grand-total row: the Asset Class column is unreliable here
            # (vendor rowspan-inherits the LAST asset class of the day,
            # e.g. "AIFs" -- see module docstring). route == "Total" is
            # the authoritative signal, not the asset_class text.
            asset_class = "TOTAL"
            route = "SUBTOTAL"
        else:
            asset_class = ASSET_CLASS_MAP.get(_norm(asset_s))
            route = ROUTE_MAP.get(route_norm)

        if asset_class is None or route is None:
            unmapped.append((asset_s, route_s))
            continue

        out.append(FPIFlowRow(
            reporting_date=reporting_date,
            asset_class=asset_class,
            route=route,
            gross_purchase_inr_cr=coerce_float(gp_s),
            gross_sale_inr_cr=coerce_float(gs_s),
            net_inr_cr=coerce_float(net_inr_s),
            net_usd_mn=coerce_float(net_usd_s),
            usd_inr_conversion=coerce_conversion(conv_s),
        ))

    if malformed:
        preview = malformed[:3]
        print(f"  WARN: {len(malformed)} row(s) skipped (unparsable reporting "
              f"date) -- first {len(preview)}: {preview!r}")
    if unmapped:
        preview = unmapped[:8]
        print(f"  WARN: {len(unmapped)} row(s) skipped (asset-class/route "
              f"label did not resolve) -- (asset, route) pairs: {preview!r}"
              + (" ..." if len(unmapped) > len(preview) else ""))
    return out


def subtotal_rows(rows: list[FPIFlowRow]) -> list[FPIFlowRow]:
    """Only the Sub-total (or Total) row per asset class per day — the
    headline flow number."""
    return [r for r in rows if r.route == "SUBTOTAL"]


_MEASURES: list[tuple[str, str, str]] = [
    # (imdr_suffix, unit, attr_name)
    ("NET.INR_CR", "inr_cr", "net_inr_cr"),
    ("NET.USD_MN", "usd_mn", "net_usd_mn"),
    ("GROSS_PURCHASE.INR_CR", "inr_cr", "gross_purchase_inr_cr"),
    ("GROSS_SALE.INR_CR", "inr_cr", "gross_sale_inr_cr"),
]

_ASSET_CLASS_DISPLAY: dict[str, str] = {
    "EQUITY": "Equity",
    "DEBT_GENERAL": "Debt (General Limit)",
    "DEBT_VRR": "Debt-VRR",
    "DEBT_FAR": "Debt-FAR",
    "HYBRID": "Hybrid",
    "MUTUAL_FUNDS": "Mutual Funds",
    "AIF": "AIFs",
    "TOTAL": "Total (all asset classes)",
}


def build_indicator_rows(
    rows: list[FPIFlowRow],
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    """Sub-total rows -> (IndicatorRow, ObservationRow) pairs, across every
    reporting day present in ``rows``.

    Emits, per asset class per day: NET (INR crore + USD mn) and
    GROSS_PURCHASE / GROSS_SALE (INR crore only -- USD-mn gross legs
    aren't published). Plus one USD/INR conversion-rate observation PER
    DISTINCT reporting date (each day has its own FX rate; the export
    covers multiple days per run, so a single conversion value can't be
    reused across all of them).
    """
    st_rows = subtotal_rows(rows)
    now = datetime.datetime.now(UTC)

    indicators: dict[str, IndicatorRow] = {}
    observations: list[ObservationRow] = []

    for row in st_rows:
        for suffix, unit, attr in _MEASURES:
            value = getattr(row, attr)
            imdr_code = f"INDIA.NSDL.FPI.{row.asset_class}.{suffix}.IN"
            if imdr_code not in indicators:
                indicators[imdr_code] = IndicatorRow(
                    imdr_code=imdr_code,
                    vendor_name="NSDL",
                    source_code=f"NSDL.Monthly.{row.asset_class}.SubTotal.{suffix}",
                    display_name=(
                        f"NSDL FPI {_ASSET_CLASS_DISPLAY.get(row.asset_class, row.asset_class)} "
                        f"— {suffix.replace('.', ' ').replace('_', ' ').title()} "
                        f"(daily, {unit})"
                    ),
                    unit=unit,
                    frequency="DAILY",
                    country_iso="IN",
                    category="bop",
                )
            observations.append(ObservationRow(
                imdr_code=imdr_code,
                obs_date=row.reporting_date,
                vintage=0,
                release_date=now,
                value=value,
                ingested_at=now,
            ))

    conversion_by_date: dict[datetime.date, float] = {}
    for r in rows:
        if r.usd_inr_conversion is not None and r.reporting_date not in conversion_by_date:
            conversion_by_date[r.reporting_date] = r.usd_inr_conversion
    if conversion_by_date:
        imdr_code = "INDIA.NSDL.FPI.USDINR_CONVERSION.IN"
        indicators[imdr_code] = IndicatorRow(
            imdr_code=imdr_code,
            vendor_name="NSDL",
            source_code="NSDL.Monthly.Conversion",
            display_name="NSDL FPI report USD/INR conversion rate (daily)",
            unit="ratio",
            frequency="DAILY",
            country_iso="IN",
            category="fx",
        )
        for d, v in sorted(conversion_by_date.items()):
            observations.append(ObservationRow(
                imdr_code=imdr_code,
                obs_date=d,
                vintage=0,
                release_date=now,
                value=v,
                ingested_at=now,
            ))

    return list(indicators.values()), observations


# ---------------------------------------------------------------------------
# Export download (CDP-attach) + table loading -- see
# scripts/econ/in/nsdl/fpi_flows.py for the full user-side setup instructions.
# ---------------------------------------------------------------------------

def load_export_tables(path: Path):
    """Read the NSDL export (.xls, actually HTML) at ``path`` and return
    ``(cash_df, derivatives_df)`` -- the 2 tables ``pandas.read_html``
    finds. Raises ``RuntimeError`` if fewer than 2 tables are found (the
    export's shape has changed -- fail loud, don't guess).
    """
    import pandas as pd

    tables = pd.read_html(path)
    if len(tables) < 2:
        raise RuntimeError(
            f"Expected 2 tables (cash + derivatives) in {path}, got "
            f"{len(tables)}. NSDL export shape may have changed."
        )
    return tables[0], tables[1]


def fetch_export_xls(
    cdp_url: str = DEFAULT_CDP_URL,
    download_dir: Path = DOWNLOAD_DIR,
    timeout_ms: int = 60_000,
) -> Path:
    """Attach to the user's already-running Chrome via CDP, navigate to the
    "Current Month" report, click "Export to Excel", and return the Path
    to the newly-downloaded ``.xls`` file.

    Uses CDP's own ``Page.setDownloadBehavior`` (not Playwright's
    ``expect_download``) -- over ``connect_over_cdp`` the download is
    handled by Chrome's own download manager, not Playwright's event
    handler, so ``expect_download`` never fires even though the file
    downloads successfully. Confirmed live 2026-07-15, see
    ``playground/econ/in/nsdl/dump_monthly_export.py``.

    Never closes or navigates the user's Chrome away from NSDL except to
    open Monthly.aspx if no matching tab is already there. Raises
    ``RuntimeError`` with setup instructions if the CDP attach itself
    fails (i.e. the user hasn't started the debug-port Chrome yet), or if
    no new file appears within ``timeout_ms`` of clicking Export.
    """
    from playwright.sync_api import sync_playwright

    download_dir.mkdir(parents=True, exist_ok=True)
    before = {p.name for p in download_dir.glob("*.xls")}

    with sync_playwright() as pw:
        try:
            browser = pw.chromium.connect_over_cdp(cdp_url)
        except Exception as exc:
            raise RuntimeError(
                f"Could not attach to Chrome via CDP at {cdp_url}. Start a "
                "debug-port Chrome pointed at NSDL first — see "
                "scripts/econ/in/nsdl/fpi_flows.py module docstring — then "
                "retry."
            ) from exc

        ctx = browser.contexts[0] if browser.contexts else browser.new_context()
        page = None
        for p in ctx.pages:
            if "fpi.nsdl.co.in" in (p.url or ""):
                page = p
                break
        if page is None:
            page = ctx.new_page()

        cdp = ctx.new_cdp_session(page)
        cdp.send("Page.setDownloadBehavior", {
            "behavior": "allow",
            "downloadPath": str(download_dir),
        })

        if "Monthly.aspx" not in (page.url or ""):
            page.goto(MONTHLY_URL, wait_until="domcontentloaded", timeout=timeout_ms)

        try:
            page.bring_to_front()
        except Exception:
            pass

        # Wait for text specific to the results table, not just any
        # <table> -- a session-expired / error page can render its own
        # (unrelated) tables and would otherwise satisfy a bare "table"
        # selector while carrying zero usable rows.
        page.wait_for_selector("text=Gross Purchases", timeout=timeout_ms)

        link = page.get_by_text("Export to Excel", exact=False).first
        link.click(timeout=15_000)

        deadline = time.time() + (timeout_ms / 1000)
        new_file: Path | None = None
        while time.time() < deadline:
            after = {p.name for p in download_dir.glob("*.xls")}
            new_names = after - before
            if new_names:
                candidates = [download_dir / name for name in new_names]
                new_file = max(candidates, key=lambda p: p.stat().st_mtime)
                break
            time.sleep(1.0)

        if new_file is None:
            raise RuntimeError(
                "Export to Excel did not produce a new .xls file in "
                f"{download_dir} within {timeout_ms}ms. Check that the "
                "click landed on the button and that Chrome's download "
                "settings allow silent downloads to that path."
            )
        return new_file
