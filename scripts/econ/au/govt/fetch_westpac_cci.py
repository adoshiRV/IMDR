"""Westpac–Melbourne Institute Consumer Sentiment (CCI) — filing discovery.

Source: `https://www.westpaciq.com.au/topic.consumersentiment`

Westpac IQ hosts the monthly Westpac-MI Consumer Sentiment report. Each
month publishes:
  - an article landing page at `www.westpaciq.com.au/{YYYY}/{MM}/consumer-sentiment-{month}-{YYYY}`
  - a PDF report at the AEM library host:
    `library.westpaciq.com.au/content/dam/public/westpaciq/secure/economics/documents/aus/{YYYY}/{MM}/er{YYYYMMDD}BullConsumerSentiment.pdf`

The topic page renders the full archive (going back years) inside an
HTML blob with relative `/content/dam/...` paths that we prefix with
the library host. PDFs are publicly accessible (no auth) despite the
"secure" path segment.

URL pattern corrected 2026-06-11 — earlier version assumed
`www.westpaciq.com.au/{YYYY}/{MM}/er...pdf` (returned 500). Sell-side
research crawler (`playground/research/ingest/crawler_westpac.py`) was
the reference for the actual library.westpaciq host.

Reachability (probed 2026-06-11): 200 OK direct over plain httpx.

This fetcher emits ONE FilingItem per monthly release with the PDF as
the canonical source_url + pdf_url. The actual numeric CCI value lives
in the PDF — parsing is by the research-doc pipeline when it ingests.
"""
from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _http import make_session, patient_get  # noqa: E402
from _models import FetchResult, FilingItem  # noqa: E402


WESTPAC_LIBRARY_BASE = "https://library.westpaciq.com.au"
WESTPAC_CCI_TOPIC_URL = "https://www.westpaciq.com.au/topic.consumersentiment"

# /content/dam/public/westpaciq/secure/economics/documents/aus/2026/06/er20260609BullConsumerSentiment.pdf
# The embedded URLs in the topic page are escaped (e.g. ' quote markers);
# the regex matches the body of the path regardless of surrounding escape chars.
_PDF_PATH_RE = re.compile(
    r"(/content/dam/public/westpaciq/[^\"'\\]*?economics/documents/aus/(\d{4})/(\d{2})/er(\d{8})BullConsumerSentiment\.pdf)",
    re.IGNORECASE,
)


def _parse_topic_html(html: str) -> list[FilingItem]:
    items: list[FilingItem] = []
    seen_urls: set[str] = set()
    for m in _PDF_PATH_RE.finditer(html):
        path = m.group(1)
        year_dir = m.group(2)
        month_dir = m.group(3)
        ymd = m.group(4)
        try:
            publish_date = date(int(ymd[0:4]), int(ymd[4:6]), int(ymd[6:8]))
        except ValueError:
            continue

        pdf_url = WESTPAC_LIBRARY_BASE + path
        if pdf_url in seen_urls:
            continue
        seen_urls.add(pdf_url)

        items.append(FilingItem(
            vendor_code="westpac",
            title=f"Westpac–MI Consumer Sentiment — {publish_date.strftime('%B %Y')}",
            publish_date=publish_date,
            source_url=pdf_url,
            pdf_url=pdf_url,
            doc_type="release",
            stream="westpac_mi_consumer_sentiment",
            extras={"release_date_ymd": ymd, "year_dir": year_dir, "month_dir": month_dir},
        ))
    return items


def discover() -> FetchResult:
    with make_session() as sess:
        try:
            r = patient_get(sess, WESTPAC_CCI_TOPIC_URL)
        except RuntimeError as exc:
            return FetchResult(vendor_code="westpac", ok=False, error=str(exc))
    items = _parse_topic_html(r.text)
    items.sort(key=lambda it: it.publish_date, reverse=True)
    return FetchResult(
        vendor_code="westpac",
        ok=True,
        items=items,
        note=f"{len(items)} monthly CCI releases parsed",
    )


if __name__ == "__main__":
    res = discover()
    print(f"westpac_cci ok={res.ok} items={len(res.items)} err={res.error}")
    for it in res.items[:12]:
        print(f"  {it.publish_date}  [{it.doc_type:8}] {it.title[:80]}")
        print(f"    {it.pdf_url}")
