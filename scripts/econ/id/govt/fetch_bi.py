"""Bank Indonesia -- all Tier-1 document streams.

BI is Indonesia's highest-signal official source: the BI-Rate decision, the
monthly policy review, the quarterly policy report, the semi-annual
financial-stability review and the Governor's speeches all live here, and
every one of them sits on the same `.aspx` listing template. So this is one
fetcher with a stream table rather than six near-identical modules.

Streams (probed 2026-09-21, item counts are page-1 depth):

  | stream                | route                              | cadence     |
  |-----------------------|------------------------------------|-------------|
  | news_release          | ruang-media/news-release (/id/)    | ~2-3 / week |
  | news_release_en       | ruang-media/news-release (/en/)    | ~2-3 / week |
  | policy_review_tkm     | Kategori=laporan kebijakan moneter | monthly     |
  | policy_report_lkm     | Kategori=laporan kebijakan moneter | quarterly   |
  | financial_stability   | Kategori=kajian stabilitas keuangan| semi-annual |
  | inflation_analysis    | Kategori=analisis inflasi          | monthly     |
  | money_supply_report   | Kategori=perkembangan uang beredar | monthly     |
  | bop_report            | Kategori=neraca pembayaran ...     | quarterly   |
  | annual_economic_report| Kategori=laporan perekonomian      | annual      |
  | governor_speeches     | ruang-media/pidato-dewan-gubernur  | ~annual     |

Two things worth knowing before changing this file:

1. **The RDG / BI-Rate decision is not its own stream.** It arrives as a
   news release titled "Hasil Rapat Dewan Gubernur ..." (ID) or "BI Board of
   Governors ..." / "BI-Rate ..." (EN). `RDG_TITLE` tags those rows with
   `doc_type="decision"` so the downstream corpus can separate the canonical
   policy text from routine press. Do not try to fetch it from a dedicated
   URL -- there isn't one.

2. **TKM and LKM share one `?Kategori=` bucket.** "laporan kebijakan
   moneter" returns both the monthly Tinjauan Kebijakan Moneter (policy
   review) and the quarterly Laporan Kebijakan Moneter (policy report).
   They are separated by title prefix, which is why those two rows carry a
   `title_filter`.

Page-1-only by design -- see `_bi_aspnet` for the pagination probe record.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import _bi_aspnet as bi_aspnet
from _http import make_session, throttle
from _models import FetchResult, FilingItem

VENDOR_CODE = "bi"

# A news release whose title matches this is the Board of Governors rate
# decision -- the canonical policy text, not routine press.
#
# BI has changed this headline convention: the decision used to be published
# as "Hasil Rapat Dewan Gubernur <Month> <Year>" and is now led by the rate
# itself -- e.g. "BI-Rate Tetap 5,75%: Memperkuat Stabilitas, Mendorong
# Pertumbuhan Ekonomi" (19 Aug 2026, seq 162, a 14.4k-char statement). Both
# spellings are matched so the archive and the current era both resolve.
#
# Do NOT loosen this to a bare "board of governors": that phrase also
# appears on personnel announcements ("Inauguration of Members of the Bank
# Indonesia Board of Governors", 2 Sep 2026), which are not policy text and
# were mis-tagged as decisions before this was tightened.
RDG_TITLE = re.compile(
    r"bi[-\s]?rate"
    r"|hasil\s+rapat\s+dewan\s+gubernur"
    r"|\bhasil\s+RDG\b"
    r"|bi\s+board\s+of\s+governors'?\s+meeting",
    re.I,
)

_TKM = re.compile(r"tinjauan\s+kebijakan\s+moneter", re.I)
_LKM = re.compile(r"laporan\s+kebijakan\s+moneter", re.I)

# (stream, listing_url, doc_type, title_filter)
STREAMS: tuple[tuple[str, str, str, re.Pattern | None], ...] = (
    (
        "news_release",
        "https://www.bi.go.id/id/publikasi/ruang-media/news-release/default.aspx",
        "release",
        None,
    ),
    (
        "news_release_en",
        "https://www.bi.go.id/en/publikasi/ruang-media/news-release/default.aspx",
        "release",
        None,
    ),
    ("policy_review_tkm", bi_aspnet.category_url("laporan kebijakan moneter"), "review", _TKM),
    ("policy_report_lkm", bi_aspnet.category_url("laporan kebijakan moneter"), "report", _LKM),
    (
        "financial_stability",
        bi_aspnet.category_url("kajian stabilitas keuangan"),
        "review",
        None,
    ),
    ("inflation_analysis", bi_aspnet.category_url("analisis inflasi"), "report", None),
    (
        "money_supply_report",
        bi_aspnet.category_url("perkembangan uang beredar"),
        "report",
        None,
    ),
    (
        "bop_report",
        bi_aspnet.category_url(
            "neraca pembayaran dan posisi investasi internasional indonesia"
        ),
        "report",
        None,
    ),
    (
        "annual_economic_report",
        bi_aspnet.category_url("laporan perekonomian"),
        "report",
        None,
    ),
    (
        "governor_speeches",
        "https://www.bi.go.id/id/publikasi/ruang-media/pidato-dewan-gubernur/default.aspx",
        "speech",
        None,
    ),
)


def _retag_decisions(items: list[FilingItem]) -> list[FilingItem]:
    """Promote rate-decision news releases to `doc_type="decision"`."""
    out = []
    for it in items:
        if it.doc_type == "release" and RDG_TITLE.search(it.title):
            it = FilingItem(
                vendor_code=it.vendor_code,
                title=it.title,
                publish_date=it.publish_date,
                source_url=it.source_url,
                pdf_url=it.pdf_url,
                doc_type="decision",
                stream=it.stream,
                extras=it.extras,
            )
        out.append(it)
    return out


def discover(throttle_s: float = 1.0) -> FetchResult:
    """Crawl every BI stream. One bad stream must not sink the rest."""
    items: list[FilingItem] = []
    failed: list[str] = []
    seen_urls: set[str] = set()

    with make_session() as client:
        for stream, url, doc_type, title_filter in STREAMS:
            try:
                got = bi_aspnet.crawl(
                    client,
                    url,
                    vendor_code=VENDOR_CODE,
                    doc_type=doc_type,
                    stream=stream,
                    title_filter=title_filter,
                )
            # Broad by intent: one dead stream must not sink the other nine.
            except Exception as exc:
                failed.append(f"{stream}: {type(exc).__name__}")
                continue
            for it in got:
                # TKM and LKM read the same URL, so the same row can surface
                # twice if a title ever satisfies both filters. Keep the
                # first classification and move on.
                key = f"{it.stream}|{it.source_url}"
                if key in seen_urls:
                    continue
                seen_urls.add(key)
                items.append(it)
            throttle(throttle_s)

    items = _retag_decisions(items)
    decisions = sum(1 for i in items if i.doc_type == "decision")
    note = f"{len(STREAMS) - len(failed)}/{len(STREAMS)} streams, {decisions} RDG"
    if failed:
        note += f"; failed: {', '.join(failed)}"
    return FetchResult(
        vendor_code=VENDOR_CODE,
        ok=len(failed) < len(STREAMS),
        items=items,
        error="; ".join(failed) or None,
        note=note,
    )


if __name__ == "__main__":
    res = discover()
    print(f"bi ok={res.ok} items={len(res.items)} :: {res.note}")
    by_stream: dict[str, int] = {}
    for it in res.items:
        by_stream[it.stream] = by_stream.get(it.stream, 0) + 1
    for s, n in sorted(by_stream.items(), key=lambda kv: -kv[1]):
        print(f"  {n:3d}  {s}")
    print("\n  newest 12:")
    for it in sorted(res.items, key=lambda i: i.publish_date, reverse=True)[:12]:
        print(f"   {it.publish_date}  [{it.doc_type:8s}] {it.title[:78]}")
