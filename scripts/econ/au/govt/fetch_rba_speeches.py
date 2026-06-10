"""RBA — Speeches discovery (filtered).

Source: `https://www.rba.gov.au/speeches/{YYYY}/`

The RBA publishes ~80-120 speeches per year across Governor, Deputy
Governor, Assistant Governors, and Monetary Policy Board members. Most
are noise for a rates desk — interviews, fireside chats, public-good
talks. The few that matter are dense forward-guidance signals.

URL pattern (probed 2026-06-10):
    /speeches/{YYYY}/sp-{role}-{YYYY-MM-DD}[-{suffix}].html

Role codes embedded in the URL:
    gov  = Governor                 (Michele Bullock — highest signal)
    dg   = Deputy Governor          (Andrew Hauser — high signal)
    ag   = Assistant Governor       (mid signal; filter by title)
    mpb  = Monetary Policy Board    (mid signal; filter by title)

Filter strategy (default ON, set ``include_all=True`` to disable):
    - Keep every gov / dg speech (scarce, always high-signal).
    - Keep ag / mpb speeches only when the title carries macro keywords
      (monetary policy, inflation, cash rate, economic conditions,
      outlook, financial stability, labour, household, etc.).
    - Drop Q&A transcripts (URL suffix `-q-and-a-transcript.html`) —
      they're audio-paired with the parent speech, no additional content.

Akamai-gated, same as the rest of `rba.gov.au`. Uses the shared
`_playwright.py` helper.
"""
from __future__ import annotations

import re
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _models import FetchResult, FilingItem  # noqa: E402
from _playwright import fetch_rba_html  # noqa: E402

HERE = Path(__file__).resolve().parent
PROFILE = HERE / "profile_rba_speeches"

RBA_BASE = "https://www.rba.gov.au"
RBA_SPEECHES_URL = "https://www.rba.gov.au/speeches/{year}/"
_ANCHOR_SELECTOR = "a[href*='/speeches/']"

# Per-speech URL: /speeches/2026/sp-gov-2026-06-04.html  (sometimes -2 or
# -q-and-a-transcript suffix).
_SPEECH_HREF_RE = re.compile(
    r"/speeches/(\d{4})/sp-(gov|dg|ag|mpb)-(\d{4}-\d{2}-\d{2})(?:-[\w\-]+)?\.html",
    re.IGNORECASE,
)

# Roles always kept (scarce, high-signal).
_KEEP_ALL_ROLES = {"gov", "dg"}

# Macro-relevant keywords; speeches by ag/mpb need at least one of these
# in their title to clear the filter. `credit` tightened to specific
# macro contexts (avoids keeping speeches about credit-card surcharging).
_TITLE_KEEP_RE = re.compile(
    r"\b(monetary policy|inflation|cash rate|economic (conditions|outlook)|"
    r"outlook|financial (stability|conditions|system)|labour market|"
    r"household|wages?|credit (conditions|growth|cycle|spreads?)|housing|"
    r"interest rates?|yield curve|reserve bank|policy framework|"
    r"policy reaction|productivity)\b",
    re.IGNORECASE,
)

# Role → display label for the doc title.
_ROLE_LABEL = {
    "gov": "Governor",
    "dg":  "Deputy Governor",
    "ag":  "Assistant Governor",
    "mpb": "Monetary Policy Board",
}


_DROP_SUFFIX_PATTERNS = ("q-and-a-transcript", "-discussion", "-transcript")


def _is_qanda(href: str) -> bool:
    low = href.lower()
    return any(p in low for p in _DROP_SUFFIX_PATTERNS)


def _keep(role: str, title: str) -> bool:
    if role in _KEEP_ALL_ROLES:
        return True
    return bool(_TITLE_KEEP_RE.search(title or ""))


def _parse_listing_html(html: str, year: int, *, include_all: bool) -> list[FilingItem]:
    from bs4 import BeautifulSoup  # type: ignore

    soup = BeautifulSoup(html, "html.parser")
    items: list[FilingItem] = []
    seen_urls: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        m = _SPEECH_HREF_RE.search(href)
        if not m:
            continue
        if _is_qanda(href):
            continue

        url = href if href.startswith("http") else RBA_BASE + href
        if url in seen_urls:
            continue
        seen_urls.add(url)

        role = m.group(2).lower()
        try:
            publish_date = date.fromisoformat(m.group(3))
        except ValueError:
            continue

        title = re.sub(r"\s+", " ", a.get_text(" ")).strip()
        if not title:
            # Fall back to enclosing <h3> / <article> heading.
            article = a.find_parent("article")
            if article is not None:
                heading = article.find(["h3", "h2"])
                if heading is not None:
                    title = re.sub(r"\s+", " ", heading.get_text(" ")).strip()
        if not title:
            continue

        if not include_all and not _keep(role, title):
            continue

        items.append(FilingItem(
            vendor_code="rba",
            title=f"{title} — {_ROLE_LABEL.get(role, role.upper())}",
            publish_date=publish_date,
            source_url=url,
            pdf_url=None,
            doc_type="speech",
            stream="rba_speeches",
            extras={"year": year, "role": role},
        ))
    return items


def discover(*, years: list[int] | None = None, include_all: bool = False) -> FetchResult:
    """Discover RBA speeches for the requested years (default: current year).

    Filter (default ON):
      - keep all `gov` / `dg`
      - keep `ag` / `mpb` only when title matches macro keywords
      - always drop `q-and-a-transcript` / `-discussion` / `-transcript` URLs

    Pass ``include_all=True`` to disable the filter. **For historical
    backfill you almost always want `include_all=True`** — title-only
    filtering will silently drop ag/mpb speeches whose macro content
    lives in the body (e.g. "Opening Remarks at the X Conference").
    The default ON setting is calibrated for daily-delta runs where
    drops cost less than a flooded daily snapshot.
    """
    if years is None:
        years = [datetime.now().year]

    items: list[FilingItem] = []
    notes: list[str] = []
    for year in years:
        try:
            html = fetch_rba_html(
                RBA_SPEECHES_URL.format(year=year),
                PROFILE,
                anchor_selector=_ANCHOR_SELECTOR,
            )
        except Exception as exc:  # noqa: BLE001
            return FetchResult(
                vendor_code="rba",
                ok=False,
                error=f"playwright fetch {year}: {type(exc).__name__}: {exc}",
            )
        year_items = _parse_listing_html(html, year, include_all=include_all)
        items.extend(year_items)
        notes.append(f"{year}: {len(year_items)}")
    return FetchResult(
        vendor_code="rba",
        ok=True,
        items=items,
        note=("filter=ON " if not include_all else "filter=OFF ") + "years " + ", ".join(notes),
    )


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--all", action="store_true", help="disable role/title filter")
    args = p.parse_args()
    res = discover(include_all=args.all)
    print(f"rba_speeches ok={res.ok} items={len(res.items)} err={res.error}")
    for it in res.items[:30]:
        role = it.extras.get("role", "?")
        print(f"  {it.publish_date}  [{role:3}] {it.title[:100]}")
