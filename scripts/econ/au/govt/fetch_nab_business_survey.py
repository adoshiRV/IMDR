"""NAB Monthly Business Survey — filing discovery.

Source: `https://business.nab.com.au/tag/economic-commentary`

NAB publishes the Monthly Business Survey (BSI) — the flagship AU
business-conditions / confidence indicator — as monthly articles on
business.nab.com.au. URL pattern (probed 2026-06-10):
    /tag/economic-commentary/nab-monthly-business-survey---{month}-{year}

The economic-commentary tag listing also hosts the Quarterly SME
Business Survey, Consumer Sentiment Survey, Monthly Data Insights,
Forward View, Housing Market Update, and Monetary Policy Update —
left for later passes; this fetcher focuses on the flagship monthly
BSI to keep daily-snapshot noise low.

Reachability (probed 2026-06-10): 200 OK over plain httpx. No gating.

Manifest-only — the actual numeric BSI values live inside the article
body (text + embedded charts). Extraction deferred to research-doc
pipeline.
"""
from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _http import make_session, patient_get  # noqa: E402
from _models import FetchResult, FilingItem  # noqa: E402


NAB_BASE = "https://business.nab.com.au"
NAB_TAG_URL = "https://business.nab.com.au/tag/economic-commentary"

# Slug pattern: /tag/economic-commentary/nab-monthly-business-survey---november-2025
_SLUG_RE = re.compile(
    r"/tag/economic-commentary/nab-monthly-business-survey-+([a-z]+)-+(\d{4})",
    re.IGNORECASE,
)

_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}


def _parse_tag_html(html: str) -> list[FilingItem]:
    items: list[FilingItem] = []
    seen_urls: set[str] = set()
    for m in _SLUG_RE.finditer(html):
        month_name = m.group(1).lower()
        year = int(m.group(2))
        mon = _MONTHS.get(month_name)
        if mon is None:
            continue
        # publish_date is the *reference* month, not exact release date.
        # The NAB monthly is typically released around the 2nd week of the
        # *following* month; we approximate to the first of the reference
        # month and rely on the source_url for disambiguation.
        publish_date = date(year, mon, 1)
        slug = m.group(0)
        url = NAB_BASE + slug
        if url in seen_urls:
            continue
        seen_urls.add(url)

        items.append(FilingItem(
            vendor_code="nab",
            title=f"NAB Monthly Business Survey — {month_name.capitalize()} {year}",
            publish_date=publish_date,
            source_url=url,
            pdf_url=None,
            doc_type="release",
            stream="nab_monthly_business_survey",
            extras={"reference_month": f"{year}-{mon:02d}", "month_name": month_name},
        ))
    return items


def discover() -> FetchResult:
    with make_session() as sess:
        try:
            r = patient_get(sess, NAB_TAG_URL)
        except RuntimeError as exc:
            return FetchResult(vendor_code="nab", ok=False, error=str(exc))
    items = _parse_tag_html(r.text)
    items.sort(key=lambda it: it.publish_date, reverse=True)
    return FetchResult(
        vendor_code="nab",
        ok=True,
        items=items,
        note=f"{len(items)} monthly BSI releases parsed",
    )


if __name__ == "__main__":
    res = discover()
    print(f"nab_business_survey ok={res.ok} items={len(res.items)} err={res.error}")
    for it in res.items[:12]:
        print(f"  {it.publish_date}  [{it.doc_type:8}] {it.title[:80]}")
        print(f"    {it.source_url}")
