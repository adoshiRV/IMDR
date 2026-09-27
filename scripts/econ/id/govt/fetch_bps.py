"""BPS -- Berita Resmi Statistik (press releases) + publications.

BPS is Track B's easiest win and its most important lesson.

**The portal is unusable; the API is not.** `www.bps.go.id` sits behind a
Cloudflare interactive challenge -- every plain GET returns HTTP 403 with
`cf-mitigated: challenge` and a "Just a moment..." body, including
`/en/pressrelease` and `/en/release-calendar`. Scraping it would need
Playwright plus challenge-solving. None of that is necessary: the BPS
WebAPI at `webapi.bps.go.id` is NOT challenged, uses the same free
`IMDR_BPS_API_KEY` that Track A already depends on, and serves the press
releases with body text and a PDF link in the listing row itself.

So this fetcher makes no HTML request at all. If a future maintainer is
tempted to scrape the portal for the release calendar, read
`id_govt_doc_sources.md` first -- the calendar gap and why it is a gap is
recorded there.

Models used (probed 2026-09-21, `lang=eng`, `domain=0000`):

  | model        | total  | what it is                                    |
  |--------------|--------|-----------------------------------------------|
  | pressrelease | 1,904  | BRS -- the narrative behind CPI/GDP/trade      |
  | publication  | 5,898  | statistical yearbooks, methodology, reports    |
  | news         |   823  | BPS activity news + joint statements           |

`pressrelease` is the Tier-1 stream: it is the commentary that accompanies
every headline print Track A already ingests as numbers. `publication` is
Tier 2 (bulky, mostly reference) and `news` Tier 3, so only `pressrelease`
is on by default.

Encoding gotcha: the API sends UTF-8 but does not always say so, and httpx
then falls back to a Latin-1-ish guess that turns apostrophes into U+FFFD
("Indonesia?s exports"). `r.encoding = "utf-8"` before reading `.text` is
required, not cosmetic.
"""
from __future__ import annotations

import datetime as dt
import html as _html
import json
import os
import re
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent))
from _http import make_session, throttle
from _models import FetchResult, FilingItem

VENDOR_CODE = "bps"
API_ROOT = "https://webapi.bps.go.id/v1/api/list"

# model -> (stream, doc_type, enabled-by-default)
MODELS: tuple[tuple[str, str, str, bool], ...] = (
    ("pressrelease", "press_release_brs", "release", True),
    ("publication", "publication", "report", False),
    ("news", "news", "release", False),
)


class MissingKeyError(RuntimeError):
    pass


def _api_key() -> str:
    key = os.environ.get("IMDR_BPS_API_KEY", "").strip()
    if not key:
        raise MissingKeyError("IMDR_BPS_API_KEY is not set")
    return key


def _get_json(client: httpx.Client, url: str) -> dict:
    r = client.get(url)
    r.raise_for_status()
    r.encoding = "utf-8"  # see the encoding gotcha in the module docstring
    return json.loads(r.text)


def _clean(raw: str | None) -> str:
    if not raw:
        return ""
    s = re.sub(r"<[^>]+>", " ", raw)
    return re.sub(r"\s+", " ", _html.unescape(s)).strip()


def _parse_date(row: dict) -> dt.date | None:
    for field in ("rl_date", "updt_date", "pub_date", "news_date"):
        raw = row.get(field)
        if not raw:
            continue
        m = re.match(r"(\d{4})-(\d{2})-(\d{2})", str(raw))
        if m:
            try:
                return dt.date(*(int(g) for g in m.groups()))
            except ValueError:
                continue
    return None


def _row_to_item(row: dict, stream: str, doc_type: str) -> FilingItem | None:
    pub = _parse_date(row)
    title = _clean(row.get("title"))
    if not (pub and title):
        return None
    # BPS has no per-item permalink in the API payload, and the PDF URL is
    # NOT usable as identity: its `?f=` token is re-signed on every request,
    # so the same document comes back under a different URL each run. Using
    # it made the daily pull report all 10 rows as new on every run.
    # `brs_id` / `pub_id` / `news_id` are stable, so identity is a synthetic
    # `bps://{stream}/{id}` URI and the volatile PDF link rides along in
    # `pdf_url`, where it is resolved fresh at ingest time anyway.
    pdf = row.get("pdf") or row.get("excel") or None
    ident = row.get("brs_id") or row.get("pub_id") or row.get("news_id")
    if ident is None:
        return None
    return FilingItem(
        vendor_code=VENDOR_CODE,
        title=title,
        publish_date=pub,
        source_url=f"bps://{stream}/{ident}",
        pdf_url=pdf,
        doc_type=doc_type,
        stream=stream,
        extras={
            k: v
            for k, v in (
                ("abstract", _clean(row.get("abstract"))),
                ("subject", _clean(row.get("subj"))),
                ("bps_id", str(ident) if ident else ""),
                ("slide_url", row.get("slide") or ""),
            )
            if v
        },
    )


def fetch_model(
    client: httpx.Client,
    model: str,
    stream: str,
    doc_type: str,
    *,
    key: str,
    lang: str = "eng",
    max_pages: int = 1,
    throttle_s: float = 1.0,
) -> list[FilingItem]:
    """Page through one API model.

    Unlike BI, BPS paginates properly -- `data[0]` carries
    `{page, pages, per_page, count, total}` and `/page/{n}/` works -- so
    backfill here is only a matter of raising `max_pages`.
    """
    items: list[FilingItem] = []
    page = 1
    while page <= max_pages:
        url = (
            f"{API_ROOT}/model/{model}/lang/{lang}/domain/0000"
            f"/page/{page}/key/{key}"
        )
        payload = _get_json(client, url)
        if payload.get("status") != "OK":
            break
        data = payload.get("data")
        if not (isinstance(data, list) and len(data) > 1):
            break
        meta, rows = data[0], data[1]
        for row in rows:
            item = _row_to_item(row, stream, doc_type)
            if item:
                items.append(item)
        if page >= int(meta.get("pages", 1)):
            break
        page += 1
        throttle(throttle_s)
    return items


def discover(
    *, include_optional: bool = False, max_pages: int = 1, throttle_s: float = 1.0
) -> FetchResult:
    """Fetch the enabled BPS models."""
    try:
        key = _api_key()
    except MissingKeyError as exc:
        return FetchResult(
            vendor_code=VENDOR_CODE, ok=False, error=str(exc),
            note="set IMDR_BPS_API_KEY in .env (same key Track A uses)",
        )

    items: list[FilingItem] = []
    failed: list[str] = []
    wanted = [m for m in MODELS if m[3] or include_optional]

    with make_session() as client:
        for model, stream, doc_type, _ in wanted:
            try:
                items += fetch_model(
                    client, model, stream, doc_type,
                    key=key, max_pages=max_pages, throttle_s=throttle_s,
                )
            # Broad by intent: per-model isolation.
            except Exception as exc:
                failed.append(f"{model}: {type(exc).__name__}")
            throttle(throttle_s)

    note = f"{len(wanted) - len(failed)}/{len(wanted)} models (API, portal is CF-gated)"
    if failed:
        note += f"; failed: {', '.join(failed)}"
    return FetchResult(
        vendor_code=VENDOR_CODE,
        ok=len(failed) < len(wanted),
        items=items,
        error="; ".join(failed) or None,
        note=note,
    )


if __name__ == "__main__":
    res = discover(include_optional=True)
    print(f"bps ok={res.ok} items={len(res.items)} :: {res.note}")
    by: dict[str, int] = {}
    for it in res.items:
        by[it.stream] = by.get(it.stream, 0) + 1
    for s, n in sorted(by.items(), key=lambda kv: -kv[1]):
        print(f"  {n:3d}  {s}")
    print("\n  newest 10:")
    for it in sorted(res.items, key=lambda i: i.publish_date, reverse=True)[:10]:
        print(f"   {it.publish_date}  [{it.stream:17s}] {it.title[:70]}")
