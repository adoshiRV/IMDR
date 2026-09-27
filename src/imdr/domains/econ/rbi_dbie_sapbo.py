"""Shared Playwright/SAP-BO scraping scaffolding for RBI DBIE report fetchers.

Both `scripts/econ/in/rbi/rbi_dbie_nri_deposits.py` (reportId 417) and
`scripts/econ/in/rbi/rbi_dbie_forward_premia.py` (reportId 698) drive the
same DBIE Home -> search -> click leaf -> new SAP-BO tab -> poll iframe
flow. This module owns the ~70% that is byte-for-byte identical between
them; each fetcher keeps its own `_COL_MAP` and parser (report-specific).

The SAP-BO iframe is NOT accessible headless; Playwright must run with
headless=False. Both fetchers REQUIRE A HOST WITH A DISPLAY.

Both fetchers share ONE persistent Chrome profile directory
(`data/econ/in/rbi/_profile_dbie`). `launch_persistent_context` takes an
exclusive lock on that directory, so any fetcher using `profile_dir()`
MUST run sequentially, never concurrently with another DBIE fetcher, or
the profile lock will corrupt/deadlock the session. This is safe today
because `scripts/econ/_country_runner.py` runs each fetcher as its own
sequential subprocess (`in_monthly.py`'s `PIPELINES` list) -- a future
change to run fetchers concurrently would break this invariant.

Session flakiness: the click-flow occasionally lands on the SAP-BO
"Logon to Open Document" page (`UI5logon.jsp`) instead of the
authenticated report -- a race in the SPA's click-flow token hand-off,
not a real login wall (no credentials are available/expected).
`search_click_scrape` retries the whole search -> click -> new-tab flow
up to `max_attempts` times before giving up.
"""
from __future__ import annotations

from pathlib import Path

# parents[0]=econ, [1]=domains, [2]=imdr, [3]=src, [4]=repo root
_REPO_ROOT = Path(__file__).resolve().parents[4]
_PROFILE = _REPO_ROOT / "data" / "econ" / "in" / "rbi" / "_profile_dbie"

DBIE_HOME_URL = "https://data.rbi.org.in/DBIE/#/dbie/home"


def profile_dir() -> Path:
    """The one persistent Chrome profile dir shared by every DBIE fetcher."""
    _PROFILE.mkdir(parents=True, exist_ok=True)
    return _PROFILE


def is_login_wall(url: str) -> bool:
    """True if `url` is the SAP-BO 'Logon to Open Document' page.

    This is a token-handoff race in the SPA's click-flow, not a real
    login wall -- no credentials are available/expected. Isolated here
    (rather than an inline substring check) so the magic string is
    unit-tested.
    """
    return "UI5logon.jsp" in (url or "")


def dismiss_modal(page) -> bool:
    """Close a DBIE `<app-modal>` if one is open. True if one was closed.

    A persistent profile carries a DBIE session across runs, and a stale
    one greets the next run with a session-timeout / logout popup. Its
    backdrop swallows every click, so the search box never receives the
    term and Playwright retries the click until it times out -- three
    full attempts, several minutes, and an empty result that looks like
    a scraping failure rather than a dialog. Observed 2026-09-15; wiping
    the profile dir also fixes it, but dismissing the dialog keeps the
    session cache that makes the flow fast.
    """
    try:
        modal = page.locator("app-modal").first
        if modal.count() == 0 or not modal.is_visible():
            return False
    except Exception:
        return False

    for sel in ("app-modal button.close", "app-modal .modal-header button",
                "app-modal button"):
        try:
            btn = page.locator(sel).first
            if btn.count():
                btn.click(timeout=3000)
                page.wait_for_timeout(1000)
                print("  dismissed a stale-session modal")
                return True
        except Exception:
            continue
    # No usable close control -- get out of its way rather than let the
    # backdrop eat the rest of the run.
    try:
        page.keyboard.press("Escape")
        page.wait_for_timeout(500)
    except Exception:
        pass
    return False


def scrape_iframe_table(page) -> list[list[str]]:
    """Extract the largest leaf table from the SAP-BO openDocChildFrame."""
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


def launch_dbie_context(pw):
    """Launch the shared persistent-profile Chrome context for DBIE scraping."""
    return pw.chromium.launch_persistent_context(
        user_data_dir=str(profile_dir()),
        channel="chrome",
        headless=False,
        accept_downloads=True,
        viewport={"width": 1400, "height": 900},
    )


def search_click_scrape(
    ctx,
    search_term: str,
    leaf_matcher,
    *,
    max_attempts: int = 3,
) -> list[list[str]]:
    """DBIE Home -> search -> click leaf -> new SAP-BO tab -> poll iframe.

    `leaf_matcher(page) -> Locator` returns the (unfiltered) locator for
    the leaf search result to click; `.first` is applied here. Retries
    the whole flow up to `max_attempts` times, treating an `is_login_wall`
    landing the same as any other transient failure (empty result, retry).

    Returns the scraped table rows, or `[]` if every attempt failed.
    """
    table_rows: list[list[str]] = []

    for attempt in range(1, max_attempts + 1):
        print(f"\n--- attempt {attempt}/{max_attempts} ---")
        page = ctx.new_page()
        try:
            print("Loading DBIE home...")
            page.goto(DBIE_HOME_URL, timeout=60000, wait_until="domcontentloaded")
            try:
                page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            page.wait_for_timeout(3000)

            dismiss_modal(page)

            print(f"Searching for '{search_term}'...")
            search_input = page.locator("input[placeholder=Search]").first
            search_input.click(timeout=8000)
            search_input.fill("")
            search_input.fill(search_term)
            page.keyboard.press("Enter")
            page.wait_for_timeout(3000)

            pages_before = len(ctx.pages)
            leaf = leaf_matcher(page)
            try:
                n = leaf.count()
            except Exception:
                n = 0
            if n == 0:
                print("  No leaf candidates found")
                try:
                    all_links = page.evaluate("""() => {
                        return Array.from(document.querySelectorAll('a'))
                            .map(el => (el.textContent||'').replace(/\\s+/g,' ').trim())
                            .filter(Boolean);
                    }""")
                    print(f"  All links on page: {all_links[:40]}")
                except Exception:
                    pass
                table_rows = []
            else:
                try:
                    leaf.first.click(timeout=10000)
                except Exception as e:
                    print(f"  Leaf click failed: {e}")
                    table_rows = []
                else:
                    table_rows = _wait_and_scrape(ctx, page, pages_before)
        finally:
            if page in ctx.pages:
                page.close()

        if table_rows:
            break

    return table_rows


def _wait_and_scrape(ctx, page, pages_before: int) -> list[list[str]]:
    deadline = 30
    while len(ctx.pages) == pages_before and deadline > 0:
        page.wait_for_timeout(1000)
        deadline -= 1
    if len(ctx.pages) == pages_before:
        print("  No new SAP-BO tab opened")
        return []

    sap_page = ctx.pages[-1]
    print(f"  SAP-BO tab: {sap_page.url[:120]}")

    rows: list[list[str]] = []
    for poll_attempt in range(10):
        sap_page.wait_for_timeout(5000)
        if is_login_wall(sap_page.url):
            print("  Landed on login wall (SPA token race) -- aborting attempt")
            rows = []
            break
        rows = scrape_iframe_table(sap_page)
        if rows and len(rows) > 3:
            print(f"  iframe ready after {(poll_attempt+1)*5}s: {len(rows)} rows")
            break
        print(f"  iframe attempt {poll_attempt+1}: {len(rows)} rows")
    else:
        print(f"  iframe timeout ({len(rows)} rows)")

    sap_page.close()
    return rows
