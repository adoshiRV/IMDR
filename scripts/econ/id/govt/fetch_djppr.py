"""DJPPR -- the debt-management office (SBN issuance, auctions, press).

DJPPR is the publisher behind Indonesia's govt-bond supply, so its press
stream is the Tier-1 read for IndoGB: retail-sukuk offer windows, coupon
resets, issuance-calendar changes.

Transport: `djppr.kemenkeu.go.id` serves only a 5 KB SPA shell, but the CMS
behind it has a clean JSON endpoint --
`api-djppr.kemenkeu.go.id/web/api/v1/page?url={slug}`. Track A already
depends on this endpoint (`imdr.domains.econ.djppr_kepemilikan`), so the
page-content shape is a known quantity and reused here rather than
re-derived: `Data.PageContentLive` is a *stringified* JSON widget tree, and
the listings live in the nodes with `widgetType == "repeater"`.

Two host gotchas, both cost time if unknown:

  - Use the APEX host. `www.djppr.kemenkeu.go.id` fails TLS hostname
    verification (`CERTIFICATE_VERIFY_FAILED`); `djppr.kemenkeu.go.id`
    is fine.
  - A missing slug answers **HTTP 200** with `Data.Title == "404"` and a
    2,305-char `PageContentLive`. Check the title, never the status code.

Slug discovery is by probe -- the nav is JS-assembled and carries no hrefs
in the API payload, so there is no machine-readable route list. Confirmed
live slugs are in `STREAMS`; `siaranpers` returns the entire 434-item press
archive in ONE response, so DJPPR needs no pagination at all.

KNOWN GAP -- **per-auction results are not reachable here.** The SBSN
results page (`hasillelangsuratberhargasyariahnegara`) does resolve, but it
is a dead template: one row, last updated 12 January 2021, and that row
carries no link field at all. Its SUN (conventional govt bond) sibling could
not be found -- ~25 slug spellings all returned the 404 shape, and the nav is
JS-assembled so there is no route list to read. Both are recorded as open
items in `id_govt_doc_sources.md`.

This is colour, not a blocker: Track A already carries SBN ownership
(`djppr_sbn_ownership`, 36 indicators) and BI SRBI auction yields as
series, and DJPPR announces every auction *outcome* that matters through
`siaranpers`, which is included here in full.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent))
from _http import make_session, patient_get, throttle
from _models import FetchResult, FilingItem

VENDOR_CODE = "djppr"
API = "https://api-djppr.kemenkeu.go.id/web/api/v1/page?url="
PORTAL = "https://djppr.kemenkeu.go.id"

# (slug, stream, doc_type)
STREAMS: tuple[tuple[str, str, str], ...] = (
    ("siaranpers", "press_release", "release"),
    ("jadwallelang", "auction_calendar", "reference"),
    ("sbnritel", "retail_sbn", "reference"),
)

_MONTHS = {
    "januari": 1, "februari": 2, "maret": 3, "april": 4, "mei": 5, "juni": 6,
    "juli": 7, "agustus": 8, "september": 9, "oktober": 10, "november": 11,
    "desember": 12,
}
_DATE = re.compile(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})")


def parse_tanggal(raw: str | None) -> dt.date | None:
    """`"4 September 2026"` -> `date(2026, 9, 4)`."""
    if not raw:
        return None
    m = _DATE.search(str(raw))
    if not m:
        return None
    month = _MONTHS.get(m.group(2).lower())
    if not month:
        return None
    try:
        return dt.date(int(m.group(3)), month, int(m.group(1)))
    except ValueError:
        return None


def _repeaters(node, out: list[dict]) -> None:
    if isinstance(node, dict):
        if node.get("widgetType") == "repeater":
            out.append(node)
        for v in node.values():
            _repeaters(v, out)
    elif isinstance(node, list):
        for v in node:
            _repeaters(v, out)


def fetch_slug(client: httpx.Client, slug: str) -> tuple[str, list[dict]]:
    """Return `(page_title, repeater_rows)` for one DJPPR slug.

    Raises RuntimeError on the 200-with-"404"-title shape so the caller can
    record it as a stream failure rather than an empty day.
    """
    payload = patient_get(client, API + slug).json()
    data = payload.get("Data") or {}
    title = data.get("Title")
    if title == "404" or not data.get("PageContentLive"):
        raise RuntimeError(f"slug {slug!r} does not exist (200 with Title=404)")
    content = json.loads(data["PageContentLive"])
    reps: list[dict] = []
    _repeaters(content, reps)
    rows: list[dict] = []
    for rep in reps:
        rows.extend(rep.get("data") or [])
    return title, rows


def _field(row: dict, name: str) -> str:
    """Read an '@'-prefixed repeater field, case-insensitively.

    The CMS prefixes repeater field names with '@' and does NOT agree with
    itself on case: `siaranpers` emits `@judul`/`@tanggal`/`@link` while
    `hasillelangsuratberhargasyariahnegara` emits `@Judul`/`@Tanggal`.
    Matching exact-case silently yields zero rows on half the pages.
    """
    target = ("@" + name).lower()
    for k, v in row.items():
        if k.lower() == target:
            return (str(v) if v is not None else "").strip()
    return ""


def _row_to_item(row: dict, stream: str, doc_type: str) -> FilingItem | None:
    # A row without a title or link is a layout placeholder.
    title = _field(row, "judul")
    link = _field(row, "link")
    if not (title and link):
        return None
    url = link if link.startswith("http") else PORTAL + link
    pub = parse_tanggal(_field(row, "tanggal"))
    # Undated rows are reference artefacts (issuance calendars, retail-SBN
    # term sheets) rather than dated filings. They are still worth carrying,
    # so they are stamped with today and flagged, not dropped -- an ingest
    # step can decide what to do with `undated=1`.
    extras = {}
    if pub is None:
        extras["undated"] = "1"
        pub = dt.date.today()
    pdf = url if url.lower().endswith(".pdf") or "/media/" in url else None
    return FilingItem(
        vendor_code=VENDOR_CODE,
        title=title,
        publish_date=pub,
        source_url=url,
        pdf_url=pdf,
        doc_type=doc_type,
        stream=stream,
        extras=extras,
    )


def discover(throttle_s: float = 1.0) -> FetchResult:
    items: list[FilingItem] = []
    failed: list[str] = []
    seen: set[str] = set()

    with make_session() as client:
        for slug, stream, doc_type in STREAMS:
            try:
                _, rows = fetch_slug(client, slug)
            # Broad by intent: per-slug isolation.
            except Exception as exc:
                failed.append(f"{slug}: {type(exc).__name__}")
                continue
            for row in rows:
                item = _row_to_item(row, stream, doc_type)
                if item and item.source_url not in seen:
                    seen.add(item.source_url)
                    items.append(item)
            throttle(throttle_s)

    note = f"{len(STREAMS) - len(failed)}/{len(STREAMS)} slugs"
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
    print(f"djppr ok={res.ok} items={len(res.items)} :: {res.note}")
    by: dict[str, int] = {}
    for it in res.items:
        by[it.stream] = by.get(it.stream, 0) + 1
    for s, n in sorted(by.items(), key=lambda kv: -kv[1]):
        print(f"  {n:4d}  {s}")
    dated = [i for i in res.items if "undated" not in i.extras]
    print(f"\n  dated {len(dated)} / undated {len(res.items) - len(dated)}")
    for it in sorted(dated, key=lambda i: i.publish_date, reverse=True)[:10]:
        print(f"   {it.publish_date}  [{it.stream:19s}] {it.title[:66]}")
