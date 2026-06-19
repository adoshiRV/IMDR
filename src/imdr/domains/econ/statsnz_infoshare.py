"""Stats NZ Infoshare — Playwright driver + wide-CSV parser (prod library).

Promoted from `playground/econ/statsnz/_infoshare.py` (2026-06-17). Infoshare
(`infoshare.stats.govt.nz`) is the only path to the Stats NZ datasets with NO
release-page CSV (PPI, CGPI, OTI/ToT, HLPI, LCI, QES, ECT, OMT, RTS, HLFS
history). Stateful ASP.NET WebForms with these load-bearing quirks
(reverse-engineered 2026-06-16 from a DevTools capture):

  1. **pxID is NOT stable** — each table's `SelectVariables.aspx?pxID={guid}`
     guid is regenerated per session; never hardcode. Navigate the browse tree.
  2. **Session is created by the tree postback, not a GET** — a bare GET of
     `SelectVariables.aspx?pxID=...` bounces to `default.aspx?RedirectReason=
     session_expired`. So `httpx` cannot do this alone; Playwright drives it.
  3. **Browse TreeView** uses `__doPostBack('ctl00$MainContent$tvBrowseNodes',
     's{NodePath}')` (backslash-separated). Click anchors by visible text.
  4. **TreeView remembers expand state across page loads** — clicking an
     already-expanded node collapses it; expand only when the child isn't
     already visible (`_ensure_expanded`).
  5. **Select-all** = select every `<option>` in each `*_lbVariableOptions`
     multi-select; the listbox `onchange` auto-updates the hidden count fields.
  6. **Output** = set `*_dlOutputOptions` to `csv`, click `*_btnGo` → CSV
     download. The CSV is a **wide pivot**: row 0 = title, 1-or-2 header rows
     (2 for two-dimension tables), then period in col 0 (`1977Q4`/`2026M04`) +
     one value per category col (`..` = suppressed/NA).

Per [[feedback-no-anti-detection-research]]: headless Playwright, plain Chrome
UA, no stealth plugins, polite single-session navigation. The persistent
browser profile lives under `data/econ/nz/statsnz/` (country-first; gitignored
via the top-level `data/*` rule).

This module owns the driver + parser + `fetch_table_rows`; each
`scripts/econ/nz/statsnz/statsnz_{topic}.py` owns its tree path + table config.
"""

from __future__ import annotations

import csv
import datetime
import hashlib
import io
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

from imdr.domains.econ.schema import IndicatorRow, ObservationRow

# src/imdr/domains/econ/statsnz_infoshare.py -> parents[4] = repo root.
_REPO_ROOT = Path(__file__).resolve().parents[4]
_PROFILE = _REPO_ROOT / "data" / "econ" / "nz" / "statsnz" / "_pw_profile"
_BASE = "https://infoshare.stats.govt.nz"
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
_TREE_SEL = "a[href*='tvBrowseNodes']"


@dataclass(frozen=True)
class WidePoint:
    period: str          # raw Infoshare period, e.g. '2026Q1' or '2026M04'
    category: str        # column header label, e.g. 'Manufacturing'
    value: float | None


class InfoshareClient:
    """Playwright-backed Infoshare browser session.

    Usage:
        with InfoshareClient() as c:
            text = c.download_csv(["Economic indicators",
                                   "Producers Price Index - PPI",
                                   "Outputs (ANZSIC06) - NZSIOC level 1, Base"])
    """

    def __init__(self, *, headless: bool = True, settle_ms: int = 700) -> None:
        self._headless = headless
        self._settle = settle_ms
        self._pw = None
        self._ctx = None

    def __enter__(self) -> "InfoshareClient":
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        _PROFILE.mkdir(parents=True, exist_ok=True)
        self._ctx = self._pw.chromium.launch_persistent_context(
            user_data_dir=str(_PROFILE),
            headless=self._headless,
            accept_downloads=True,
            viewport={"width": 1400, "height": 1000},
            user_agent=_UA,
        )
        return self

    def __exit__(self, *exc) -> None:
        try:
            if self._ctx is not None:
                self._ctx.close()
        finally:
            if self._pw is not None:
                self._pw.stop()

    # -- internals -----------------------------------------------------------

    def _match_node(self, page, text: str, *, exact: bool):
        """Return the first tree-anchor Locator whose label matches, else None."""
        loc = page.locator(_TREE_SEL, has_text=text)
        for i in range(loc.count()):
            t = (loc.nth(i).text_content() or "").strip()
            if (t == text) if exact else (text in t):
                return loc.nth(i)
        return None

    def _click_node(self, page, text: str, *, exact: bool) -> bool:
        node = self._match_node(page, text, exact=exact)
        if node is None:
            return False
        node.click()
        try:
            page.wait_for_load_state("networkidle", timeout=20000)
        except Exception:
            pass
        page.wait_for_timeout(self._settle)
        return True

    def _ensure_expanded(self, page, frag: str, child_frag: str) -> None:
        """Expand `frag` only if `child_frag` isn't already visible.

        The ASP.NET TreeView toggles on click and remembers expand state across
        page loads (session), so blindly clicking an already-expanded node
        collapses it. Guard on child visibility instead.
        """
        child = self._match_node(page, child_frag, exact=False)
        if child is not None and child.is_visible():
            return  # parent already expanded
        if not self._click_node(page, frag, exact=True):
            raise RuntimeError(f"Infoshare tree node not found: {frag!r}")
        # Deep groups re-render slowly after the expand postback; wait for the
        # child to actually appear before the caller tries to click it.
        for _ in range(6):
            c = self._match_node(page, child_frag, exact=False)
            if c is not None and c.is_visible():
                return
            page.wait_for_timeout(1500)

    # -- public --------------------------------------------------------------

    def download_csv(self, tree_path: list[str]) -> str:
        """Navigate the browse tree to a leaf table and return its wide CSV.

        `tree_path` is a list of node-label fragments, outermost first. All but
        the last are matched exactly (categories/groups); the last is matched by
        substring (leaf table names are long and version-suffixed).
        """
        page = self._ctx.new_page()
        try:
            page.goto(f"{_BASE}/default.aspx", wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(self._settle)
            # Intermediate nodes are expand steps (idempotent); the leaf is a
            # navigate click that lands on SelectVariables.
            for i in range(len(tree_path) - 1):
                self._ensure_expanded(page, tree_path[i], tree_path[i + 1])
            leaf = tree_path[-1]
            # Deep groups re-render slowly after the expand postback; poll for
            # the leaf before giving up.
            clicked = False
            for _ in range(5):
                if self._click_node(page, leaf, exact=False):
                    clicked = True
                    break
                page.wait_for_timeout(1500)
            if not clicked:
                raise RuntimeError(f"Infoshare leaf table not found: {leaf!r}")
            if "SelectVariables.aspx" not in page.url:
                raise RuntimeError(
                    f"did not reach SelectVariables (url={page.url!r}); leaf node may not be a table"
                )

            sels = page.locator("select[id*='lbVariableOptions']")
            if sels.count() == 0:
                raise RuntimeError("no variable list-boxes on SelectVariables page")
            for i in range(sels.count()):
                s = sels.nth(i)
                vals = s.locator("option").evaluate_all("els=>els.map(o=>o.value)")
                if vals:
                    s.select_option(vals)
                    page.wait_for_timeout(150)

            page.locator("select[id*='dlOutputOptions']").select_option("csv")
            # Large tables can be slow to generate; retry the Go-click once.
            dl = None
            last_err: Exception | None = None
            for _attempt in range(2):
                try:
                    with page.expect_download(timeout=120000) as di:
                        page.locator("input[id*='btnGo']").click()
                    dl = di.value
                    break
                except Exception as e:  # noqa: BLE001 — Playwright TimeoutError
                    last_err = e
                    page.wait_for_timeout(1500)
            if dl is None:
                raise RuntimeError(
                    f"Infoshare download never fired for {tree_path[-1]!r}: {last_err!r}"
                )
            fd, tmp_name = tempfile.mkstemp(prefix="infoshare_", suffix=".csv")
            os.close(fd)
            tmp = Path(tmp_name)
            dl.save_as(str(tmp))
            text = tmp.read_text(encoding="utf-8", errors="replace")
            try:
                tmp.unlink()
            except OSError:
                pass
            return text
        finally:
            page.close()


def _parse_value(raw: str) -> float | None:
    s = (raw or "").strip().strip('"')
    if not s or s in ("..", "...", "-", "NA", "N/A", "C", "S"):
        return None
    try:
        return float(s.replace(",", ""))
    except ValueError:
        return None


def _is_period(cell: str) -> bool:
    s = (cell or "").strip()
    return len(s) >= 4 and s[:4].isdigit()


def _build_categories(header_rows: list[list[str]], ncols: int) -> list[str]:
    """Combine 1-or-more header rows into one category label per column.

    Each header row is forward-filled (ASP.NET leaves only the first cell of a
    merged block populated). A header *level* that is constant across every
    data column is dropped (e.g. an inner dim that is always 'All groups'), so
    codes stay clean. Multi-level labels are joined with ' - '.
    """
    levels: list[list[str]] = []
    for hr in header_rows:
        filled: list[str] = []
        last = ""
        for c in range(ncols):
            v = (hr[c].strip() if c < len(hr) and hr[c] else "")
            if v:
                last = v
            filled.append(last)
        levels.append(filled)
    varying = [lv for lv in levels if len({lv[c] for c in range(1, ncols) if lv[c]}) > 1]
    if not varying:
        varying = levels[-1:]  # all levels constant — keep the innermost
    cats: list[str] = []
    for c in range(ncols):
        parts = [lv[c] for lv in varying if lv[c]]
        cats.append(" - ".join(dict.fromkeys(parts)))
    return cats


def parse_wide_csv(text: str) -> tuple[str, list[WidePoint]]:
    """Parse an Infoshare wide-pivot CSV into (table_title, [WidePoint]).

    Layout: row 0 = title, then 1 OR 2 header rows (2 for tables with two
    category dimensions — the outer dim's labels are sparse/merged), then data
    rows: period in col 0 + one value per category col. Header rows = the
    leading rows whose col 0 is NOT a period.
    """
    rows = list(csv.reader(io.StringIO(text)))
    if len(rows) < 3:
        raise ValueError(f"Infoshare CSV too short: {len(rows)} rows")
    title = (rows[0][0] if rows[0] else "").strip()

    h = 1
    while h < len(rows) and not _is_period(rows[h][0] if rows[h] else ""):
        h += 1
    header_rows = rows[1:h]
    if not header_rows:
        raise ValueError("Infoshare CSV: no header rows found")
    # True width = widest row anywhere (a sampled data row can be short when the
    # CSV writer suppresses trailing NAs), else late columns get truncated.
    ncols = max((len(r) for r in rows[1:]), default=0)
    categories = _build_categories(header_rows, ncols)

    out: list[WidePoint] = []
    for r in rows[h:]:
        if not r or not _is_period(r[0]):
            continue
        period = r[0].strip()
        for col in range(1, min(len(r), ncols)):
            if not categories[col]:
                continue
            out.append(WidePoint(period=period, category=categories[col], value=_parse_value(r[col])))
    return title, out


def period_to_obs_date(period: str) -> datetime.date | None:
    """Infoshare period → month-end date. Handles YYYYQn, YYYYMmm, YYYY."""
    p = period.strip()
    try:
        if "Q" in p:
            y, q = p.split("Q")
            month = int(q) * 3
        elif "M" in p:
            y, m = p.split("M")
            month = int(m)
        else:
            y, month = p, 12
        y = int(y)
        if not (1 <= month <= 12):
            return None
        nxt = datetime.date(y + 1, 1, 1) if month == 12 else datetime.date(y, month + 1, 1)
        return nxt - datetime.timedelta(days=1)
    except (ValueError, TypeError):
        return None


def slugify(label: str) -> str:
    """Category label -> IMDR-code suffix (UPPER_SNAKE, alnum only)."""
    s = re.sub(r"[^0-9a-zA-Z]+", "_", label.strip().upper()).strip("_")
    return s or "UNKNOWN"


# econ.dim_indicator.imdr_code and .source_code are varchar(128). Deep 2-/3-dim
# composite categories (e.g. RTS industry x sales-type x price-basis x SA,
# QES industry x sex x ordinary/overtime) can exceed this. Cap the suffix so
# `{prefix}.{suffix}.NZ` fits, appending a short deterministic hash to keep
# truncated codes unique. The full label is preserved in display_name.
_CODE_LIMIT = 128


def _fit_suffix(prefix: str, suffix: str) -> str:
    budget = _CODE_LIMIT - len(prefix) - len(".") - len(".NZ")
    if len(suffix) <= budget:
        return suffix
    h = hashlib.sha1(suffix.encode("utf-8")).hexdigest()[:6]
    keep = budget - 7  # "_" + 6 hex
    return suffix[:keep].rstrip("_") + "_" + h


def fetch_table_rows(
    client: "InfoshareClient",
    tree_path: list[str],
    *,
    code_prefix: str,
    unit: str,
    frequency: str,
    category: str,
    is_sa: bool = False,
    drop_categories: set[str] | None = None,
    display_prefix: str = "",
    vendor_name: str = "statsnz",
    country_iso: str = "NZ",
):
    """Download one Infoshare table and emit (IndicatorRow[], ObservationRow[]).

    Keeps ALL category columns (the "firehose"), minus `drop_categories`.
    IMDR code = ``{code_prefix}.{slug(category)}.NZ``. The relevance call
    (which tables, which drops) lives in each fetcher's config.
    """
    drop = drop_categories or set()
    now = datetime.datetime.now(datetime.timezone.utc)
    text = client.download_csv(tree_path)
    title, points = parse_wide_csv(text)

    indicators: dict[str, IndicatorRow] = {}
    observations: list[ObservationRow] = []
    for pt in points:
        if pt.category in drop or not pt.category:
            continue
        obs_date = period_to_obs_date(pt.period)
        if obs_date is None:
            continue
        suffix = _fit_suffix(code_prefix, slugify(pt.category))
        code = f"{code_prefix}.{suffix}.NZ"
        if code not in indicators:
            indicators[code] = IndicatorRow(
                imdr_code=code,
                vendor_name=vendor_name,
                source_code=f"{code_prefix}.{suffix}",
                display_name=f"{display_prefix}{pt.category}"[:500],
                unit=unit,
                frequency=frequency,
                country_iso=country_iso,
                category=category,
                is_seasonally_adjusted=is_sa,
            )
        observations.append(ObservationRow(
            imdr_code=code,
            obs_date=obs_date,
            vintage=0,
            release_date=now,
            value=pt.value,
            ingested_at=now,
        ))
    print(f"  -> {title[:48]!r}: {len(indicators)} indicators, {len(observations)} obs")
    return list(indicators.values()), observations


__all__ = [
    "InfoshareClient", "WidePoint", "parse_wide_csv", "period_to_obs_date",
    "slugify", "fetch_table_rows",
]
