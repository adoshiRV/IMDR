"""Per-stream resolvers for Australia govt-filings ingest.

Each resolver takes a discovered FilingItem and returns
``("pdf", pdf_bytes)``. **Body-text only is NOT a valid return for AU**
— every AU stream must land in SharePoint (Phase J contract, decided
2026-06-11). HTML-only sources are rendered to PDF via Playwright
`page.pdf()` so the end-state matches publisher-PDF streams.

Three transport patterns:
  - `_render_to_pdf_akamai`  — Playwright fresh-profile + page.pdf() for
    RBA HTML-only pages (Governor's Statement / Board Minutes / Speeches)
  - `_fetch_publisher_pdf`   — Playwright nav (warmed Akamai cookie) +
    ctx.request.get on the publisher PDF URL (RBA SMP / FSR)
  - `_render_to_pdf_plain`   — Playwright headless + page.pdf() for
    non-gated HTML sources (Treasury / APRA / ABS / NAB)
  - `_fetch_pdf_direct`      — plain httpx GET (Westpac CCI library URL)

Smokes proven 2026-06-11 — see playground/econ/au/govt/_e2e_ingest_pdf.py
and _e2e_render_pdf.py for the reference recipes used here.
"""
from __future__ import annotations

import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Literal

import httpx
from bs4 import BeautifulSoup  # type: ignore

sys.path.insert(0, str(Path(__file__).parent))
from _models import FilingItem  # noqa: E402

ResolvedKind = Literal["pdf"]
ResolveResult = tuple[ResolvedKind, bytes]

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/127.0 Safari/537.36"
)
_GOTO_TIMEOUT_MS = 60_000
_SELECTOR_TIMEOUT_MS = 15_000


# ---------------------------------------------------------------------
# Playwright-based transports
# ---------------------------------------------------------------------

def _fresh_profile() -> Path:
    """Per-call ephemeral Chrome profile dir. Caller must rmtree() after use."""
    return Path(tempfile.mkdtemp(prefix="au_govt_resolver_"))


def _render_to_pdf_akamai(url: str, *, anchor_selector: str = "h1") -> bytes:
    """Render an Akamai-gated RBA HTML page to PDF.

    Uses the fresh-profile headed-Chrome bypass pattern proven by
    `playground/econ/rba/fetch_d2_e_tables.py`. Returns the rendered
    PDF bytes (Playwright `page.pdf()` after `emulate_media('print')`).
    """
    from playwright.sync_api import sync_playwright

    profile = _fresh_profile()
    try:
        with sync_playwright() as pw:
            ctx = pw.chromium.launch_persistent_context(
                user_data_dir=str(profile),
                channel="chrome",
                headless=False,
                ignore_https_errors=True,
                viewport={"width": 1400, "height": 900},
                locale="en-AU",
            )
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=_GOTO_TIMEOUT_MS)
            page.wait_for_selector(anchor_selector, timeout=_SELECTOR_TIMEOUT_MS)
            page.wait_for_timeout(1_500)
            page.emulate_media(media="print")
            pdf = page.pdf(
                format="A4",
                print_background=True,
                margin={"top": "12mm", "right": "12mm", "bottom": "12mm", "left": "12mm"},
            )
            ctx.close()
        return pdf
    finally:
        shutil.rmtree(profile, ignore_errors=True)


def _fetch_publisher_pdf(landing_url: str, *, pdf_path_pattern: re.Pattern[str]) -> bytes:
    """RBA SMP / FSR path: navigate to landing, find the publisher PDF URL,
    download via the same Playwright session (warmed Akamai cookie)."""
    from playwright.sync_api import sync_playwright

    profile = _fresh_profile()
    try:
        with sync_playwright() as pw:
            ctx = pw.chromium.launch_persistent_context(
                user_data_dir=str(profile),
                channel="chrome",
                headless=False,
                ignore_https_errors=True,
                viewport={"width": 1400, "height": 900},
                locale="en-AU",
            )
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.goto(landing_url, wait_until="domcontentloaded", timeout=_GOTO_TIMEOUT_MS)
            page.wait_for_selector("h1", timeout=_SELECTOR_TIMEOUT_MS)
            html = page.content()
            m = pdf_path_pattern.search(html)
            if not m:
                ctx.close()
                raise RuntimeError(
                    f"publisher PDF link not found at {landing_url} (pattern {pdf_path_pattern.pattern})"
                )
            pdf_path = m.group(0)
            pdf_url = pdf_path if pdf_path.startswith("http") else "https://www.rba.gov.au" + pdf_path
            r = ctx.request.get(pdf_url, timeout=_GOTO_TIMEOUT_MS)
            # Read body BEFORE closing the context (Playwright APIResponse
            # body is invalid once the context is disposed).
            if not r.ok:
                ctx.close()
                raise RuntimeError(f"publisher PDF download status={r.status} url={pdf_url}")
            body = r.body()
            ctx.close()
            return body
    finally:
        shutil.rmtree(profile, ignore_errors=True)


def _render_to_pdf_plain(url: str, *, anchor_selector: str = "h1") -> bytes:
    """Render a non-gated HTML page to PDF via headless Chrome."""
    from playwright.sync_api import sync_playwright

    profile = _fresh_profile()
    try:
        with sync_playwright() as pw:
            ctx = pw.chromium.launch_persistent_context(
                user_data_dir=str(profile),
                channel="chrome",
                headless=True,
                ignore_https_errors=True,
                viewport={"width": 1400, "height": 900},
                locale="en-AU",
            )
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=_GOTO_TIMEOUT_MS)
            page.wait_for_selector(anchor_selector, timeout=_SELECTOR_TIMEOUT_MS)
            page.wait_for_timeout(1_500)
            page.emulate_media(media="print")
            pdf = page.pdf(
                format="A4",
                print_background=True,
                margin={"top": "12mm", "right": "12mm", "bottom": "12mm", "left": "12mm"},
            )
            ctx.close()
        return pdf
    finally:
        shutil.rmtree(profile, ignore_errors=True)


def _fetch_pdf_direct(url: str) -> bytes:
    """Plain-httpx GET for sources where the PDF URL is direct + public
    (Westpac IQ library.westpaciq.com.au, etc.)."""
    with httpx.Client(follow_redirects=True, timeout=60, headers={"User-Agent": _UA}) as c:
        r = c.get(url)
    if not r.is_success:
        raise RuntimeError(f"direct PDF fetch status={r.status_code} url={url}")
    if not r.content.startswith(b"%PDF"):
        raise RuntimeError(f"direct PDF fetch returned non-PDF magic={r.content[:8]!r} url={url}")
    return r.content


# ---------------------------------------------------------------------
# Publisher-PDF patterns
# ---------------------------------------------------------------------

_RBA_SMP_PDF_RE = re.compile(
    r"/publications/smp/\d{4}/[a-z]+/pdf/statement-on-monetary-policy-\d{4}-\d{2}\.pdf",
    re.IGNORECASE,
)
_RBA_FSR_PDF_RE = re.compile(
    r"/publications/fsr/\d{4}/[a-z]+/pdf/financial-stability-review-\d{4}-\d{2}\.pdf",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------
# Per-stream resolvers
# ---------------------------------------------------------------------

def resolve_rba_governors_statement(item: FilingItem) -> ResolveResult:
    return ("pdf", _render_to_pdf_akamai(item.source_url))


def resolve_rba_board_minutes(item: FilingItem) -> ResolveResult:
    return ("pdf", _render_to_pdf_akamai(item.source_url))


def resolve_rba_speeches(item: FilingItem) -> ResolveResult:
    return ("pdf", _render_to_pdf_akamai(item.source_url))


def resolve_rba_smp(item: FilingItem) -> ResolveResult:
    return ("pdf", _fetch_publisher_pdf(item.source_url, pdf_path_pattern=_RBA_SMP_PDF_RE))


def resolve_rba_fsr(item: FilingItem) -> ResolveResult:
    return ("pdf", _fetch_publisher_pdf(item.source_url, pdf_path_pattern=_RBA_FSR_PDF_RE))


def resolve_treasury(item: FilingItem) -> ResolveResult:
    return ("pdf", _render_to_pdf_plain(item.source_url))


def resolve_apra(item: FilingItem) -> ResolveResult:
    # Renders the page narrative; the XLSX URL is preserved in
    # FilingItem.extras['xlsx_url'] for downstream analytics consumers.
    return ("pdf", _render_to_pdf_plain(item.source_url))


def resolve_abs(item: FilingItem) -> ResolveResult:
    return ("pdf", _render_to_pdf_plain(item.source_url))


def resolve_westpac_cci(item: FilingItem) -> ResolveResult:
    # source_url is the library.westpaciq.com.au PDF URL — direct fetch.
    return ("pdf", _fetch_pdf_direct(item.source_url))


def resolve_nab(item: FilingItem) -> ResolveResult:
    return ("pdf", _render_to_pdf_plain(item.source_url))


# ---------------------------------------------------------------------
# Dispatch — by `stream` so the 5 RBA streams pick the right transport
# ---------------------------------------------------------------------

_RESOLVERS = {
    # RBA — 5 streams
    "rba_governors_statement":      resolve_rba_governors_statement,
    "rba_board_minutes":            resolve_rba_board_minutes,
    "rba_smp":                      resolve_rba_smp,
    "rba_fsr":                      resolve_rba_fsr,
    "rba_speeches":                 resolve_rba_speeches,
    # Other agencies (one stream each)
    "treasury_publications":        resolve_treasury,
    "apra_adi_performance":         resolve_apra,
    "apra_gi_performance":          resolve_apra,
    "abs_cpi_release":              resolve_abs,
    "abs_labour_force_release":     resolve_abs,
    "abs_national_accounts_release": resolve_abs,
    "westpac_mi_consumer_sentiment": resolve_westpac_cci,
    "nab_monthly_business_survey":  resolve_nab,
}


def resolve(item: FilingItem) -> ResolveResult:
    fn = _RESOLVERS.get(item.stream)
    if fn is None:
        raise ValueError(
            f"no resolver for stream={item.stream!r} (vendor_code={item.vendor_code!r})"
        )
    return fn(item)


if __name__ == "__main__":
    # Smoke: pick the latest item per stream from the last snapshot and
    # resolve it. Prints transport flavour + bytes per stream.
    import io as _io
    import json as _json
    sys.stdout = _io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    from _models import DATA_DIR as _DATA_DIR, vendor_snapshots_dir  # noqa: PLC0415

    if not _DATA_DIR.exists():
        print(f"no snapshot — run ingest_filings.py first ({_DATA_DIR})")
        sys.exit(1)

    streams_done = set()
    for sub in sorted(_DATA_DIR.iterdir()):
        if not sub.is_dir():
            continue
        snaps = sorted(vendor_snapshots_dir(sub.name).glob("*.json"))
        if not snaps:
            continue
        payload = _json.loads(snaps[-1].read_text(encoding="utf-8"))
        for it_json in payload.get("items", []):
            item = FilingItem.from_json(it_json)
            if item.stream in streams_done:
                continue
            streams_done.add(item.stream)
            try:
                kind, body = resolve(item)
                magic = body[:8].hex() if isinstance(body, bytes) else "(non-bytes)"
                print(f"  {item.stream:<35s}  kind={kind}  bytes={len(body):>8,}  magic={magic}")
            except Exception as exc:  # noqa: BLE001
                print(f"  {item.stream:<35s}  ERR  {type(exc).__name__}: {str(exc)[:140]}")
