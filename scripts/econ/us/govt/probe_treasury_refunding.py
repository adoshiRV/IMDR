"""U.S. Treasury Quarterly Refunding — discovery probe.

Source: home.treasury.gov/policy-issues/financing-the-government/quarterly-refunding

The Quarterly Refunding is the single highest-signal bond-SUPPLY event for
rates desks: it sets coupon-issuance sizing for the next quarter. Each
quarter Treasury publishes (1) the **Quarterly Refunding Statement** (the
press release announcing issuance plans), (2) the **TBAC report** (Treasury
Borrowing Advisory Committee report/recommendation to the Secretary), and
(3) the **marketable-borrowing / financing estimates** press release.

Listing transport
------------------
treasury.gov is on a Drupal stack (``home.treasury.gov``). It is **plain-GET
friendly** for the refunding archive pages (probed 2026-06-22: HTTP 200, no
Akamai gate, no TLS reset from RV's network — same transport class as
federalreserve.gov; ``_http.py:make_session()`` is reused verbatim, no
Playwright, no anti-detection flags).

The refunding documents are NOT on a single calendar hub like the Fed.
Treasury keeps a set of **archive category pages**, each an HTML *table* of
year x quarter cells linking the per-quarter press release for that document
kind:

    .../quarterly-refunding-archives/official-remarks-on-quarterly-refunding-by-calendar-year   ← the STATEMENT
    .../quarterly-refunding-archives/treasury-borrowing-advisory-committee-report-to-the-secretary-by-calendar-year  ← TBAC report
    .../quarterly-refunding-archives/quarterly-refunding-financing-estimates-by-calendar-year    ← borrowing estimates

Each table cell is::

    <a href="/news/press-releases/{slug}" aria-label="{YYYY} {N}{st|nd|rd|th} Quarter">{N}th Quarter</a>

The press-release slug (e.g. ``jy2697``, ``sb0489``) is opaque — it carries
no date — so the (year, quarter) come from the table cell, and the **exact
announcement date** is read from the detail page's
``field--name-field-news-publication-date`` ``<time datetime>`` (the page's
generic ``<title>``/header ``<time>`` is a shared template timestamp and is
NOT reliable; confirmed 2026-06-22 — all detail pages report the same
2026-02-13 header time).

Crawler shape: **Shape D — paginated/category HTML listing on a govt portal**
(here: 3 single-GET category tables, regex over cells; then one detail GET
per kept quarter to resolve the real publish date). No pagination walk — each
category page is one GET carrying every year.

Reachability (probed 2026-06-22): archive pages 200 OK / ~144 KB; detail
press-release pages 200 OK / ~140 KB over plain HTTPS.
"""
from __future__ import annotations

import re
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _http import make_session, patient_get, save_raw  # noqa: E402
from _models import FetchResult, FilingItem  # noqa: E402

TREASURY_BASE = "https://home.treasury.gov"
_ARCH = (
    "/policy-issues/financing-the-government/quarterly-refunding"
    "/quarterly-refunding-archives"
)

# The three refunding document kinds, each its own year x quarter category
# table. doc_type stays "refunding" per the task; the kind is recorded in
# extras so a later ingest can distinguish statement / TBAC / estimate.
_CATEGORY_PAGES: dict[str, str] = {
    "statement": f"{_ARCH}/official-remarks-on-quarterly-refunding-by-calendar-year",
    "tbac_report": (
        f"{_ARCH}/treasury-borrowing-advisory-committee-report-to-the-secretary"
        "-by-calendar-year"
    ),
    "financing_estimate": (
        f"{_ARCH}/quarterly-refunding-financing-estimates-by-calendar-year"
    ),
}

# <a href="/news/press-releases/jy2697" aria-label="2024 4th Quarter">…
_CELL_RE = re.compile(
    r'href="(/news/press-releases/[^"]+)"\s+aria-label="(\d{4})\s+(\d)(?:st|nd|rd|th)\s+Quarter"',
    re.I,
)
# Detail-page real publish date.
_PUBDATE_RE = re.compile(
    r'field--name-field-news-publication-date.*?datetime="([^"]+)"', re.S
)
# Refunding PDFs surfaced on a detail page live under /system/files/.
# The statement page carries the tentative auction/buyback schedule under
# /221/; the financing-estimate page carries the Sources-and-Uses table
# under /136/. The site-wide boilerplate Fact-Sheet is filtered out in
# discover(). NOTE: the TBAC presentation/charge charts are NOT on the
# press-release detail page — they live on the "most-recent documents" hub
# under /system/files/221/TreasuryPresentationToTBAC*.pdf (captured there if
# a later build crawls that hub); the TBAC item's source_url is the report
# press release.
_REFUNDING_PDF_RE = re.compile(r'href="(/system/files/\d+/[^"]+\.(?:pdf|xls|xlsx))"', re.I)

_KIND_LABEL = {
    "statement": "Quarterly Refunding Statement",
    "tbac_report": "TBAC Report to the Secretary",
    "financing_estimate": "Marketable Borrowing Estimates",
}


def _parse_category(html: str, kind: str) -> list[dict]:
    """Return [{slug_url, year, quarter}] for one category archive table."""
    out: list[dict] = []
    seen: set[str] = set()
    for m in _CELL_RE.finditer(html):
        url = TREASURY_BASE + m.group(1)
        year, quarter = int(m.group(2)), int(m.group(3))
        key = f"{year}Q{quarter}"
        if key in seen:
            continue
        seen.add(key)
        out.append({"source_url": url, "year": year, "quarter": quarter})
    return out


def _publish_date(detail_html: str, year: int, quarter: int) -> date:
    """Real announcement date from the detail page; fall back to quarter mid
    if the field is missing (announcements land ~start of Feb/May/Aug/Nov)."""
    m = _PUBDATE_RE.search(detail_html)
    if m:
        try:
            return datetime.fromisoformat(m.group(1).replace("Z", "+00:00")).date()
        except ValueError:
            pass
    # Fallback: refunding for Qn is announced in the first month of that quarter
    # window (Feb/May/Aug/Nov). Use a conservative placeholder day-1.
    month = {1: 2, 2: 5, 3: 8, 4: 11}[quarter]
    return date(year, month, 1)


def discover(*, quarters: int = 8, save_raw_html: bool = True) -> FetchResult:
    """Discover the last ``quarters`` Quarterly Refunding events.

    Emits one FilingItem per (quarter, document-kind) that exists in the
    archive tables. For the STATEMENT item the detail page is also scanned
    for the canonical TBAC/refunding PDFs (``/system/files/221/...``) and the
    first is attached as ``pdf_url``; the rest are listed in ``extras``.
    """
    items: list[FilingItem] = []
    with make_session() as sess:
        # 1) Pull the three category tables.
        per_kind: dict[str, list[dict]] = {}
        for kind, path in _CATEGORY_PAGES.items():
            try:
                r = patient_get(sess, TREASURY_BASE + path)
            except RuntimeError as exc:
                return FetchResult(
                    vendor_code="treasury_us", ok=False,
                    error=f"{kind} archive fetch failed: {exc}",
                )
            if save_raw_html:
                save_raw("treasury_refunding", f"{kind}_archive.html", r.text)
            per_kind[kind] = _parse_category(r.text, kind)

        # The statement table is the spine: take its most-recent N quarters.
        spine = sorted(
            per_kind["statement"],
            key=lambda c: (c["year"], c["quarter"]),
            reverse=True,
        )[:quarters]
        keep_quarters = {(c["year"], c["quarter"]) for c in spine}

        # 2) Resolve each kept quarter across all three kinds.
        for kind, cells in per_kind.items():
            for c in cells:
                yq = (c["year"], c["quarter"])
                if yq not in keep_quarters:
                    continue
                try:
                    dr = patient_get(sess, c["source_url"])
                except RuntimeError:
                    continue
                pub = _publish_date(dr.text, c["year"], c["quarter"])
                pdfs = [TREASURY_BASE + p for p in _REFUNDING_PDF_RE.findall(dr.text)]
                # Drop the boilerplate fact-sheet that appears site-wide.
                pdfs = [p for p in pdfs if "Fact-Sheet" not in p]
                items.append(FilingItem(
                    vendor_code="treasury_us",
                    title=(
                        f"{_KIND_LABEL[kind]} - {c['year']} Q{c['quarter']}"
                    ),
                    publish_date=pub,
                    source_url=c["source_url"],
                    pdf_url=pdfs[0] if pdfs else None,
                    doc_type="refunding",
                    stream="treasury_refunding",
                    extras={
                        "kind": kind,
                        "year": c["year"],
                        "quarter": c["quarter"],
                        "all_pdfs": pdfs,
                    },
                ))

    items.sort(key=lambda it: (it.publish_date, it.extras.get("kind", "")), reverse=True)
    return FetchResult(
        vendor_code="treasury_us",
        ok=True,
        items=items,
        note=(
            f"{len(items)} refunding items across "
            f"{len(keep_quarters)} quarters (statement/TBAC/estimate)"
        ),
    )


def _print_summary(res: FetchResult) -> None:
    print(f"treasury_refunding  ok={res.ok}  items={len(res.items)}  err={res.error}")
    print(f"  note: {res.note}")
    for it in res.items[:12]:
        print(f"  {it.publish_date}  [{it.extras.get('kind',''):18}] {it.title}")
        print(f"             page: {it.source_url}")
        print(f"             pdf : {it.pdf_url}")


if __name__ == "__main__":
    _print_summary(discover())
