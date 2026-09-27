"""Shared crawler for every Bank Indonesia `.aspx` document listing.

BI runs one SharePoint page template across all its publication streams, so
a single parser covers news releases, Governor speeches, and the whole
`publikasi/laporan` report family. That is why the `fetch_bi_*.py` modules
are thin wrappers over this one rather than three separate crawlers.

Probed 2026-09-21. Two row variants exist in the same
`div.media.media--pers` container:

  Variant A -- news releases / speeches
      <div class="media media--pers">
        <a href="{detail}" class="... media__title ...">{title}</a>
        <div class="media__subtitle">{d Month YYYY}&nbsp;<span>Hits N</span></div>
        <p class="ellipsis--three-line">{abstract}</p>

  Variant B -- reports (`publikasi/laporan`)
      <div class="media media--pers">
        <a href="{detail}" class="box-list__hyperlink"></a>    <- empty anchor
        <p class="... media__title ...">{title}</p>
        <div class="media__subtitle">{d Month YYYY}</div>
        <div class="media__subtitle">{report family}</div>     <- stream classifier

Variant B's SECOND subtitle is the report-family name ("Laporan Kebijakan
Moneter", "Kajian Stabilitas Keuangan", ...). Note `Default.aspx?id=<slug>`
does NOT filter -- that param is ignored and the listing comes back
combined. The parameter that DOES filter, server-side, is `?Kategori=`
(see the pagination note below for how it was found). The family subtitle
is still carried on every row as `extras["family"]`, which is what lets a
caller confirm a category-scoped fetch actually came back scoped.

Pagination -- UNRESOLVED, and deliberately not attempted. The listings use
an ASP.NET `DataPager` inside an UpdatePanel. Probed 2026-09-21, every route
fails from plain httpx:

  - Query params are ignored: `?page=2`, `?Page=2`, `?Halaman=2`,
    `?PageIndex=2`, `?start=10`, `?Index=2` all return page 1 unchanged.
  - `__doPostBack` to any pager target, with the page's full hidden-input
    set echoed back, returns page 1 again -- for all 5-7 targets, both with
    and without `X-MicrosoftAjax: Delta=true`.
  - On the reports listing the delta postback instead answers with a
    `pageRedirect` that DROPS the category filter and lands on unfiltered
    page 1.

So every fetcher here is page-1-only. That is sufficient for a daily pull
(page 1 always holds everything published since yesterday) and, because
`?Kategori=` narrows the reports listing to one publication family, page 1
of each category is 10 rows of a monthly-or-slower series -- i.e. 1-3 years
of history per stream without paging at all. Backfilling deeper would need
Playwright driving the pager clicks; filed as an open item rather than
half-built here.

The one genuine win from that probe: the `pageRedirect` payload leaked BI's
own filter URL, which is how we learned the reports listing supports
server-side `?Kategori=` and `?Periode=` scoping, and it enumerated all 21
categories. See `BI_REPORT_CATEGORIES` below.

Language mirrors: `/id/` runs AHEAD of `/en/`. On 2026-09-21 the Indonesian
news-release listing was at 17 Sep while the English mirror was still at
10 Sep. Fetch `/id/` when recency matters, `/en/` when English text does.
"""
from __future__ import annotations

import datetime as dt
import html as _html
import re
import sys
import urllib.parse
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent))
from _http import patient_get
from _models import FilingItem

BI_ROOT = "https://www.bi.go.id"

# Indonesian + English month names -> month number. BI mixes them: the /en/
# mirror sometimes serves an Indonesian month name in the subtitle.
_MONTHS = {
    "januari": 1, "februari": 2, "maret": 3, "april": 4, "mei": 5, "juni": 6,
    "juli": 7, "agustus": 8, "september": 9, "oktober": 10, "november": 11,
    "desember": 12,
    "january": 1, "february": 2, "march": 3, "may": 5, "june": 6, "july": 7,
    "august": 8, "october": 10, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "agt": 8,
    "ags": 8, "aug": 8, "sep": 9, "sept": 9, "okt": 10, "oct": 10, "nov": 11,
    "des": 12, "dec": 12,
}

_ROW_SPLIT = re.compile(r'<div class="media media--pers">')
_TITLE_ANCHOR = re.compile(
    r'<a\s+href="([^"]+)"[^>]*class="[^"]*media__title[^"]*"[^>]*>(.*?)</a>',
    re.S,
)
_BOX_ANCHOR = re.compile(
    r'<a\s+href="([^"]+)"[^>]*class="[^"]*box-list__hyperlink[^"]*"'
)
_TITLE_P = re.compile(
    r'<p[^>]*class="[^"]*media__title[^"]*"[^>]*>(.*?)</p>', re.S
)
_SUBTITLE = re.compile(r'<div class="media__subtitle">(.*?)</div>', re.S)
_ABSTRACT = re.compile(r'<p class="ellipsis--three-line">(.*?)</p>', re.S)
_DATE = re.compile(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})")


def _text(raw: str) -> str:
    """Strip tags / entities / nbsp from a markup fragment."""
    s = re.sub(r"<[^>]+>", " ", raw)
    s = _html.unescape(s).replace("\xa0", " ")
    return re.sub(r"\s+", " ", s).strip()


def parse_date(raw: str) -> dt.date | None:
    """``"10 September 2026 Hits 2094"`` -> ``date(2026, 9, 10)``."""
    m = _DATE.search(_text(raw))
    if not m:
        return None
    month = _MONTHS.get(m.group(2).lower())
    if not month:
        return None
    try:
        return dt.date(int(m.group(3)), month, int(m.group(1)))
    except ValueError:
        return None


def parse_rows(html: str) -> list[dict]:
    """Extract every `media--pers` row, whichever variant it is.

    Returns dicts with: url, title, publish_date, abstract, family.
    `family` is populated for variant-B (report) rows only.
    """
    rows: list[dict] = []
    for blk in _ROW_SPLIT.split(html)[1:]:
        subtitles = [_text(s) for s in _SUBTITLE.findall(blk)]
        m = _TITLE_ANCHOR.search(blk)
        if m:  # variant A
            url, title = m.group(1), _text(m.group(2))
        else:  # variant B
            a, p = _BOX_ANCHOR.search(blk), _TITLE_P.search(blk)
            if not (a and p):
                continue
            url, title = a.group(1), _text(p.group(1))
        pub = parse_date(subtitles[0]) if subtitles else None
        if not (title and pub):
            # A row with no parseable date is template furniture, not a
            # filing. Dropping it is correct; counting it would inflate the
            # daily total.
            continue
        ab = _ABSTRACT.search(blk)
        rows.append(
            {
                "url": url if url.startswith("http") else BI_ROOT + url,
                "title": title,
                "publish_date": pub,
                "abstract": _text(ab.group(1)) if ab else "",
                "family": subtitles[1] if len(subtitles) > 1 else "",
            }
        )
    return rows


BI_REPORT_BASE = "https://www.bi.go.id/id/publikasi/laporan/default.aspx"

# The 21 publication families the reports listing can be filtered to, exactly
# as BI spells them in its own `?Kategori=` URL (lower-case, spaces intact).
# Harvested from the `pageRedirect` delta payload described in the module
# docstring -- this list is BI's, not ours, so it is the authoritative set.
BI_REPORT_CATEGORIES = (
    "laporan perekonomian",
    "laporan tahunan bank indonesia",
    "laporan ekonomi dan keuangan syariah",
    "kajian stabilitas keuangan",
    "laporan pelaksanaan tugas dan wewenang bank indonesia",
    "laporan kebijakan moneter",
    "laporan nusantara",
    "perkembangan ekonomi keuangan dan kerja sama internasional",
    "perkembangan uang beredar",
    "neraca pembayaran dan posisi investasi internasional indonesia",
    "survei konsumen",
    "survei kegiatan dunia usaha",
    "survei perbankan",
    "survei harga properti residensial di pasar primer",
    "survei penjualan eceran",
    "survei proyeksi indikator makro ekonomi",
    "perkembangan properti komersial",
    "prompt manufacturing index",
    "analisis inflasi",
    "buku dedikasi untuk negeri",
    "laporan lainnya",
)

# `?Periode=` accepts these, comma-separable. Not needed once Kategori is
# set, but recorded so the next person does not have to re-probe.
BI_REPORT_PERIODS = ("bulanan", "triwulan", "semesteran", "tahunan")


def category_url(kategori: str) -> str:
    """Listing URL scoped to one publication family."""
    return f"{BI_REPORT_BASE}?Kategori={urllib.parse.quote(kategori)}"


def crawl(
    client: httpx.Client,
    listing_url: str,
    *,
    vendor_code: str,
    doc_type: str,
    stream: str,
    title_filter: re.Pattern | None = None,
) -> list[FilingItem]:
    """Crawl one BI listing page into FilingItem rows.

    Single GET -- see the pagination note in the module docstring.

    `title_filter` splits streams that share a `?Kategori=` bucket. The
    clearest case: "laporan kebijakan moneter" holds BOTH the monthly
    Tinjauan Kebijakan Moneter (policy review) and the quarterly Laporan
    Kebijakan Moneter (policy report), separable only by title prefix.
    """
    html = patient_get(client, listing_url).text
    items: list[FilingItem] = []
    for row in parse_rows(html):
        if title_filter and not title_filter.search(row["title"]):
            continue
        items.append(
            FilingItem(
                vendor_code=vendor_code,
                title=row["title"],
                publish_date=row["publish_date"],
                source_url=row["url"],
                doc_type=doc_type,
                stream=stream,
                extras={
                    k: v
                    for k, v in (
                        ("abstract", row["abstract"]),
                        ("family", row["family"]),
                    )
                    if v
                },
            )
        )
    return items
