"""ABS — release commentary pages (CPI / Labour Force / National Accounts).

Sources (each `latest-release` URL redirects to the current period's page):
  - CPI:           https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/consumer-price-index-australia/latest-release
  - Labour Force:  https://www.abs.gov.au/statistics/labour/employment-and-unemployment/labour-force-australia/latest-release
  - National Accounts (GDP):
                   https://www.abs.gov.au/statistics/economy/national-accounts/australian-national-accounts-national-income-expenditure-and-product/latest-release

ABS publishes the *data* via SDMX (covered by the `playground/econ/abs/`
fetchers — already loaded into `econ.fact_indicator`). These release
pages add ABS's *narrative commentary* around each print — useful when
the research-doc pipeline absorbs filings, less useful as raw numbers.

Each release page carries an `<h1>`, a "Reference period" string (the
data period), and a `<time datetime="...">` with the release date.

Reachability (probed 2026-06-10): 200 OK over plain HTTPS. No gating.
"""
from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _http import make_session, patient_get  # noqa: E402
from _models import FetchResult, FilingItem  # noqa: E402


ABS_BASE = "https://www.abs.gov.au"

_STREAMS = [
    {
        "stream": "abs_cpi_release",
        "url": "https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/consumer-price-index-australia/latest-release",
        "label": "Consumer Price Index, Australia",
    },
    {
        "stream": "abs_labour_force_release",
        "url": "https://www.abs.gov.au/statistics/labour/employment-and-unemployment/labour-force-australia/latest-release",
        "label": "Labour Force, Australia",
    },
    {
        "stream": "abs_national_accounts_release",
        "url": "https://www.abs.gov.au/statistics/economy/national-accounts/australian-national-accounts-national-income-expenditure-and-product/latest-release",
        "label": "Australian National Accounts: National Income, Expenditure and Product",
    },
]


def _parse_page(html: str) -> tuple[date | None, str | None]:
    """Return (release date, reference period text).

    Picks the released-date `<time>` defensively: prefer one whose parent
    text mentions "Released"; otherwise fall back to the first non-future
    `<time>` with a parseable datetime. This guards against the ABS
    template adding a "Next release" `<time>` element ahead of the
    released-date one.
    """
    from bs4 import BeautifulSoup  # type: ignore

    soup = BeautifulSoup(html, "html.parser")
    today = date.today()

    candidates: list[tuple[date, bool]] = []  # (parsed date, near_released_text)
    for t in soup.find_all("time"):
        iso = t.get("datetime") or ""
        m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", iso)
        if not m:
            continue
        try:
            d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            continue
        if d > today:
            # "Next release" entries — always skip; release date is past-or-today.
            continue
        parent_text = ""
        p = t.find_parent()
        if p is not None:
            parent_text = p.get_text(" ", strip=True).lower()
        near_released = "released" in parent_text or "release date" in parent_text
        candidates.append((d, near_released))

    release_date: date | None = None
    # Prefer a candidate whose context mentions "released"; otherwise newest non-future.
    near = [c for c in candidates if c[1]]
    if near:
        release_date = max(c[0] for c in near)
    elif candidates:
        release_date = max(c[0] for c in candidates)

    ref_period: str | None = None
    rp_el = soup.find(class_=re.compile(r"reference|release-period|period", re.I))
    if rp_el is not None:
        text = re.sub(r"\s+", " ", rp_el.get_text(" ")).strip()
        ref_period = re.sub(r"^Reference period\s*", "", text).strip() or text

    return release_date, ref_period


def discover() -> FetchResult:
    items: list[FilingItem] = []
    notes: list[str] = []
    errors: list[str] = []
    with make_session() as sess:
        for s in _STREAMS:
            try:
                r = patient_get(sess, s["url"])
            except RuntimeError as exc:
                errors.append(f"{s['stream']}: {exc}")
                continue
            release_date, ref_period = _parse_page(r.text)
            if release_date is None:
                errors.append(f"{s['stream']}: no <time> release date on page")
                continue

            ref_suffix = f" — {ref_period}" if ref_period else ""
            items.append(FilingItem(
                vendor_code="abs",
                title=f"{s['label']}{ref_suffix} (released {release_date.isoformat()})",
                publish_date=release_date,
                source_url=s["url"],
                pdf_url=None,
                doc_type="release",
                stream=s["stream"],
                extras={
                    "reference_period": ref_period,
                    "release_date": release_date.isoformat(),
                },
            ))
            notes.append(f"{s['stream']}: {release_date}")

    if errors:
        # Any per-stream failure surfaces as ok=False so the orchestrator's
        # status column flags it. Items still flow through so a partial run
        # doesn't lose the streams that did work.
        return FetchResult(
            vendor_code="abs",
            ok=False,
            items=items,
            error="; ".join(errors),
            note=", ".join(notes),
        )
    return FetchResult(
        vendor_code="abs",
        ok=True,
        items=items,
        note=", ".join(notes),
    )


if __name__ == "__main__":
    res = discover()
    print(f"abs_commentary ok={res.ok} items={len(res.items)} err={res.error}")
    for it in res.items:
        print(f"  {it.publish_date}  [{it.doc_type:8}] {it.title[:100]}")
        print(f"    ref period: {it.extras.get('reference_period')}")
