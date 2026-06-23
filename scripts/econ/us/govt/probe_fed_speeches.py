"""Federal Reserve Board SPEECHES & TESTIMONY — discovery probe.

Listing page: federalreserve.gov/newsevents/speeches-testimony.htm

The HTML listing page is **JS-rendered** — a plain GET returns the page
chrome but NO speech rows (the table is hydrated client-side). Rather than
reach for Playwright, the page is backed by a public JSON firehose that a
plain GET resolves cleanly:

    /json/ne-speeches.json   ← full speeches archive (~1,300 items)

Each item:
    {"d": "6/6/2026 12:00:00 PM",          # publish datetime (US M/D/Y)
     "t": "Deregulating in a Financial Boom: ...",   # title
     "s": "Governor Michael S. Barr",                # speaker
     "lo": "At American University, Washington, D.C.",  # location
     "l": "/newsevents/speech/barr20260606a.htm"}    # detail-page link

A parallel RSS feed exists at /feeds/speeches.xml (last ~10 only) — the
JSON feed is preferred for both recall and structured fields.

Crawler shape: **Shape A-equivalent — single JSON feed** (one GET, parse
JSON array, normalise). Lowest complexity. (The HTML page itself would be
Shape "JS-rendered / Playwright" — avoided via the JSON backing feed.)

Reachability (probed 2026-06-22): JSON feed 200 OK / ~436 KB / 1,320
items over plain HTTPS. plain httpx, no Playwright.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _http import make_session, patient_get, save_raw  # noqa: E402
from _models import FetchResult, FilingItem  # noqa: E402

FED_BASE = "https://www.federalreserve.gov"
SPEECHES_JSON_URL = f"{FED_BASE}/json/ne-speeches.json"
SPEECHES_HTML_URL = f"{FED_BASE}/newsevents/speeches-testimony.htm"  # JS-rendered; not crawled


def _parse_date(raw: str) -> date | None:
    raw = (raw or "").strip()
    # Feed format: "6/6/2026 12:00:00 PM"
    for fmt in ("%m/%d/%Y %I:%M:%S %p", "%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def _doc_type(link: str) -> str:
    return "testimony" if "/testimony/" in link.lower() else "speech"


def _parse_feed(payload: str, *, limit: int) -> list[FilingItem]:
    # The Fed JSON occasionally carries a UTF-8 BOM.
    arr = json.loads(payload.lstrip("﻿"))
    items: list[FilingItem] = []
    seen: set[str] = set()
    for rec in arr:
        link = (rec.get("l") or "").strip()
        title = re.sub(r"\s+", " ", (rec.get("t") or "")).strip()
        d = _parse_date(rec.get("d", ""))
        if not link or not title or d is None:
            continue
        url = FED_BASE + link if link.startswith("/") else link
        if url in seen:
            continue
        seen.add(url)
        items.append(FilingItem(
            vendor_code="fed",
            title=title,
            publish_date=d,
            source_url=url,
            pdf_url=None,                       # speeches are HTML; no canonical PDF
            doc_type=_doc_type(link),
            stream="fed_speeches",
            extras={
                "speaker": (rec.get("s") or "").strip(),
                "location": (rec.get("lo") or "").strip(),
            },
        ))
    items.sort(key=lambda it: it.publish_date, reverse=True)
    return items[:limit]


def discover(*, limit: int = 40, save_raw_json: bool = True) -> FetchResult:
    """Pull the most-recent ``limit`` speeches/testimony from the JSON feed.

    Default 40 ≈ 2-3 months of activity (Fed publishes ~15-20/month). The
    orchestrator dedups against rolling seen.json so re-runs are idempotent.
    """
    with make_session() as sess:
        try:
            r = patient_get(sess, SPEECHES_JSON_URL, min_bytes=500)
        except RuntimeError as exc:
            return FetchResult(vendor_code="fed", ok=False, error=str(exc))
    if save_raw_json:
        save_raw("fed_speeches", "ne-speeches.json", r.text)
    items = _parse_feed(r.text, limit=limit)
    return FetchResult(
        vendor_code="fed",
        ok=True,
        items=items,
        note=f"top {len(items)} of full JSON firehose (HTML listing is JS-rendered; used /json/ne-speeches.json instead)",
    )


def _print_summary(res: FetchResult) -> None:
    print(f"fed_speeches  ok={res.ok}  items={len(res.items)}  err={res.error}")
    print(f"  note: {res.note}")
    for it in res.items[:10]:
        spk = it.extras.get("speaker", "")
        print(f"  {it.publish_date}  [{it.doc_type:9}] {it.title[:70]}")
        print(f"             {spk}  |  {it.source_url}")


if __name__ == "__main__":
    _print_summary(discover())
