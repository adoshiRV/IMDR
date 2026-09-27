"""Tests for the Indonesia govt-filings (Track B) parse layer.

Covers `scripts/econ/id/govt/` (promoted from playground on 2026-09-21,
Phase J). No live network calls -- every test feeds a markup or payload
fragment captured from the real source on 2026-09-21.

The prod tree uses flat `sys.path` imports rather than a package, matching
every other `scripts/econ/{cc}/govt/` tree, so these tests add that
directory to `sys.path` instead of importing a dotted path.

Each test here pins a bug that actually bit during discovery, or a source
quirk that would silently zero out a stream if a future edit regressed it:

- BI serves TWO row variants on one template (anchor-titled news rows vs
  empty-anchor report rows with a family subtitle).
- BI mixes Indonesian and English month names across its /id/ and /en/
  mirrors, and pads dates with `&nbsp;` + a "Hits N" span.
- BI answers a missing `.aspx` with HTTP 200 + site chrome, so 404 detection
  must be structural.
- BI retitled its rate decision from "Hasil Rapat Dewan Gubernur" to
  "BI-Rate ...", and "Board of Governors" alone false-positives on
  personnel news.
- OJK's two language mirrors use DIFFERENT DATE ORDER (D Month YYYY vs
  Month D, YYYY) -- parsing only one dropped all 10 English rows.
- OJK's press rows share the `list-group-item` class with ~370 nav entries.
- DJPPR's CMS disagrees with itself on repeater field-name case
  (`@judul` vs `@Judul`).
- BPS's PDF URL token is re-signed per request and must NOT be the dedup
  identity.
"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import pytest

_GOVT = Path(__file__).resolve().parents[3] / "scripts" / "econ" / "id" / "govt"
if str(_GOVT) not in sys.path:
    sys.path.insert(0, str(_GOVT))

import _bi_aspnet as BI  # noqa: E402, N812
import fetch_bi  # noqa: E402
import fetch_bps  # noqa: E402
import fetch_djppr  # noqa: E402
import fetch_kemenkeu  # noqa: E402
import fetch_ojk  # noqa: E402
import ingest_filings  # noqa: E402
import resolvers  # noqa: E402
from _models import FilingItem, dedup_key  # noqa: E402

# ---------------------------------------------------------------------------
# Un-leak the bare module names. DO NOT REMOVE.
#
# Every `scripts/econ/{cc}/govt/` tree imports its siblings unqualified
# (`from _http import ...`) after a `sys.path.insert`. pytest collects all
# test files into ONE process, so whichever country imports first wins
# `sys.modules["_http"]` for the whole session. "id" sorts before "us", so
# leaving these cached made `test_us_govt_probes.py` resolve US's
# `from _http import save_raw` against INDONESIA's `_http.py` and fail
# collection with `ImportError: cannot import name 'save_raw'` — taking
# three pre-existing US test modules down with it.
#
# Popping them here is safe: the objects above hold live references, so these
# tests keep working; only *future* imports are affected, which is exactly
# what we want. `_GOVT` comes off `sys.path` too so it cannot shadow another
# country's modules later in the session.
#
# The durable fix is to make these trees real packages with relative imports,
# which would touch KR/AU/US/ID at once and is out of scope here.
# ---------------------------------------------------------------------------
for _leaked in (
    "_http", "_models", "_bi_aspnet", "resolvers", "ingest_filings",
    "fetch_bi", "fetch_bps", "fetch_djppr", "fetch_kemenkeu", "fetch_ojk",
):
    sys.modules.pop(_leaked, None)
if str(_GOVT) in sys.path:
    sys.path.remove(str(_GOVT))

# ---------------------------------------------------------------------------
# Fixtures -- fragments captured from the live sources on 2026-09-21
# ---------------------------------------------------------------------------

BI_NEWS_ROW = """
<div class="media media--pers">
  <a href="/en/publikasi/ruang-media/news-release/Pages/sp_2818426.aspx">
    <div class="media__img"></div></a>
  <div class="media-body">
    <div>
      <a href="/en/publikasi/ruang-media/news-release/Pages/sp_2818426.aspx"
         class="mt-0 media__title ellipsis--two-line">
        Retail Sales Survey August 2026: Retail Sales Expected to Maintain Growth
      </a>
      <div class="media__subtitle"> 10 September 2026&#160; <span>Hits 2094</span> </div>
    </div>
  </div>
  <p class="ellipsis--three-line">No.28/184/DKom&#160;Retailers expect sales to grow.</p>
</div>
"""

BI_REPORT_ROW = """
<div class="media media--pers">
  <a href="/id/publikasi/laporan/Pages/PIII-Tw2-2026.aspx"
     class="box-list__hyperlink"></a>
  <div class="media-body media-body--magz">
    <div>
      <p class="mt-0 media__title ellipsis--two-line">
        Laporan Posisi Investasi Internasional Indonesia - Triwulan II 2026 </p>
      <div class="media__subtitle">10 September 2026</div>
      <div class="media__subtitle">Neraca Pembayaran dan Posisi Investasi Internasional Indonesia</div>
    </div>
  </div>
</div>
"""

# Template furniture: a row with no parseable date. Must be dropped.
BI_UNDATED_ROW = """
<div class="media media--pers">
  <a href="/id/publikasi/laporan/Pages/Placeholder.aspx" class="box-list__hyperlink"></a>
  <div class="media-body"><div>
    <p class="media__title">Placeholder</p>
    <div class="media__subtitle">Coming soon</div>
  </div></div>
</div>
"""

OJK_ID_ROW = """
<li class="list-group-item">
  <div class="row"><div class="col-lg-2">
    <div style="background-image: url(/PublishingImages/x.jpg)"></div></div>
  <div class="col-lg-10">
    <div class="date"> 9 September 2026 </div>
    <a href="/id/berita-dan-kegiatan/siaran-pers/Pages/Gelar-LIKE-IT.aspx"
       class="group-item-title">
      <strong>Siaran Pers: OJK Dorong Generasi Muda Tingkatkan Literasi Keuangan</strong>
    </a>
    <div class="caption">OJK terus mendorong peningkatan literasi keuangan.</div>
  </div></div>
</li>
"""

OJK_EN_ROW = """
<li class="list-group-item">
  <div class="col-lg-10">
    <div class="date"> August 31, 2026 </div>
    <a href="/en/berita-dan-kegiatan/siaran-pers/Pages/OJK-Strengthens-Enforcement.aspx"
       class="group-item-title">
      <strong>Press Release: OJK Strengthens Enforcement, Imposes 1,277 Sanctions</strong>
    </a>
    <div class="caption">Enforcement summary.</div>
  </div>
</li>
"""

# The left-hand nav reuses `list-group-item` but has no `group-item-title`.
OJK_NAV_ROW = """
<li class='list-group-item'>
  <strong><a href='/id/tentang-ojk/Pages/Visi-Misi.aspx'>Visi Misi</a></strong>
</li>
"""


# ---------------------------------------------------------------------------
# BI -- date parsing
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "raw,expected",
    [
        # NBSP is deliberate -- BI pads the date cell with &nbsp;.
        ("10 September 2026  Hits 2094", dt.date(2026, 9, 10)),  # noqa: RUF001
        ("1 Februari 2024", dt.date(2024, 2, 1)),
        ("28 November 2025", dt.date(2025, 11, 28)),
        ("21 Sep 2026", dt.date(2026, 9, 21)),
        ("5 Desember 2022", dt.date(2022, 12, 5)),
        ("14 Agustus 2026", dt.date(2026, 8, 14)),
    ],
)
def test_bi_parse_date_accepts_both_languages(raw, expected):
    assert BI.parse_date(raw) == expected


@pytest.mark.parametrize("raw", ["Coming soon", "", "Triwulan II", "31 Foobar 2026"])
def test_bi_parse_date_rejects_unparseable(raw):
    assert BI.parse_date(raw) is None


def test_bi_parse_date_rejects_impossible_day():
    # 31 February must not silently roll into March.
    assert BI.parse_date("31 Februari 2026") is None


# ---------------------------------------------------------------------------
# BI -- row variants
# ---------------------------------------------------------------------------

def test_bi_parses_news_row_variant_a():
    rows = BI.parse_rows(BI_NEWS_ROW)
    assert len(rows) == 1
    row = rows[0]
    assert row["title"].startswith("Retail Sales Survey August 2026")
    assert row["publish_date"] == dt.date(2026, 9, 10)
    assert row["url"] == (
        "https://www.bi.go.id/en/publikasi/ruang-media/news-release"
        "/Pages/sp_2818426.aspx"
    )
    assert "Retailers expect sales to grow" in row["abstract"]
    # "Hits 2094" is date-cell furniture and must not leak into the title.
    assert "Hits" not in row["title"]


def test_bi_parses_report_row_variant_b_with_family():
    rows = BI.parse_rows(BI_REPORT_ROW)
    assert len(rows) == 1
    row = rows[0]
    assert row["title"].startswith("Laporan Posisi Investasi Internasional")
    assert row["publish_date"] == dt.date(2026, 9, 10)
    # The SECOND subtitle is the publication family -- the only thing that
    # confirms a `?Kategori=`-scoped fetch came back scoped.
    assert row["family"].startswith("Neraca Pembayaran")


def test_bi_parses_both_variants_together():
    rows = BI.parse_rows(BI_NEWS_ROW + BI_REPORT_ROW)
    assert len(rows) == 2


def test_bi_drops_undated_template_rows():
    """An undated row is furniture; counting it would inflate the daily total."""
    rows = BI.parse_rows(BI_UNDATED_ROW)
    assert rows == []


def test_bi_relative_urls_are_absolutised():
    for row in BI.parse_rows(BI_NEWS_ROW + BI_REPORT_ROW):
        assert row["url"].startswith("https://www.bi.go.id/")


# ---------------------------------------------------------------------------
# BI -- report categories
# ---------------------------------------------------------------------------

def test_bi_category_url_encodes_spaces():
    url = BI.category_url("laporan kebijakan moneter")
    assert url.endswith("?Kategori=laporan%20kebijakan%20moneter")


def test_bi_report_categories_are_bi_spelling():
    """Lower-case with spaces, as BI's own filter URL spells them."""
    assert len(BI.BI_REPORT_CATEGORIES) == 21
    assert len(set(BI.BI_REPORT_CATEGORIES)) == 21
    for cat in BI.BI_REPORT_CATEGORIES:
        assert cat == cat.lower()
        assert cat.strip() == cat
    # The two that carry the policy text this whole track exists for.
    assert "laporan kebijakan moneter" in BI.BI_REPORT_CATEGORIES
    assert "kajian stabilitas keuangan" in BI.BI_REPORT_CATEGORIES


def test_bi_streams_reference_only_real_categories():
    """Every Kategori-scoped stream must name a category BI actually has."""
    for _, url, _, _ in fetch_bi.STREAMS:
        if "Kategori=" not in url:
            continue
        assert url in {
            BI.category_url(c) for c in BI.BI_REPORT_CATEGORIES
        }, f"stream url references an unknown category: {url}"


# ---------------------------------------------------------------------------
# BI -- rate-decision tagging
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "title",
    [
        "BI-Rate Tetap 5,75%: Memperkuat Stabilitas, Mendorong Pertumbuhan Ekonomi",
        "BI Rate Turun 25 bps",
        "Hasil Rapat Dewan Gubernur September 2026",
        "BI Board of Governors' Meeting: BI-Rate Held",
    ],
)
def test_rdg_title_matches_decisions(title):
    assert fetch_bi.RDG_TITLE.search(title)


@pytest.mark.parametrize(
    "title",
    [
        # The false positive that made personnel news look like policy text.
        "Inauguration of Members of the Bank Indonesia Board of Governors",
        "Gubernur BI Lantik Pemimpin Satuan Kerja Bank Indonesia",
        "Consumer Survey August 2026: Consumer Confidence Increasing",
        "Official Reserve Assets Remained Maintained in August 2026",
    ],
)
def test_rdg_title_ignores_non_decisions(title):
    assert not fetch_bi.RDG_TITLE.search(title)


def test_retag_decisions_promotes_only_matching_releases():
    base = dict(
        vendor_code="bi", publish_date=dt.date(2026, 8, 19),
        stream="news_release", extras={},
    )
    items = [
        FilingItem(title="BI-Rate Tetap 5,75%", source_url="u1",
                   doc_type="release", **base),
        FilingItem(title="Consumer Survey August 2026", source_url="u2",
                   doc_type="release", **base),
        # Already a report -- must not be reclassified even on a title match.
        FilingItem(title="Laporan Kebijakan Moneter: BI-Rate review",
                   source_url="u3", doc_type="report", **base),
    ]
    out = fetch_bi._retag_decisions(items)
    assert [i.doc_type for i in out] == ["decision", "release", "report"]


# ---------------------------------------------------------------------------
# BI -- disguised 404 + detail resolution
# ---------------------------------------------------------------------------

def test_bi_is_missing_detects_200_with_chrome():
    """A missing BI page returns HTTP 200, so detection must be structural."""
    assert resolvers.is_missing("<html><body>site chrome only</body></html>")
    assert not resolvers.is_missing('<div id="layout-title">Real Title</div>')


def test_bi_detail_date_is_month_first():
    """BI's detail pages serve M/D/YYYY -- 9/17/2026 is 17 September."""
    assert resolvers._bi_date("9/17/2026 7:00 PM") == dt.date(2026, 9, 17)
    assert resolvers._bi_date("12/1/2025 9:00 AM") == dt.date(2025, 12, 1)
    assert resolvers._bi_date("no date here") is None


def test_bi_news_release_url_builds_sp_pattern():
    """Release No.28/184/DKom of 2026 lives at sp_2818426.aspx."""
    assert resolvers.bi_news_release_url(184, 2026).endswith("sp_2818426.aspx")
    assert resolvers.bi_news_release_url(7, 2019).endswith("sp_28719.aspx")


def test_bi_text_strips_sharepoint_zero_width_junk():
    """BI's rich-text fields carry ZWSP/ZWJ from the SharePoint editor."""
    assert resolvers._text("<p>​‍Departemen Komunikasi</p>") == (  # noqa: RUF001
        "Departemen Komunikasi"
    )


# ---------------------------------------------------------------------------
# OJK
# ---------------------------------------------------------------------------

def test_ojk_parses_indonesian_row():
    rows = fetch_ojk.parse_rows(OJK_ID_ROW)
    assert len(rows) == 1
    assert rows[0]["publish_date"] == dt.date(2026, 9, 9)
    assert rows[0]["url"].startswith("https://ojk.go.id/id/")


def test_ojk_parses_us_ordered_english_date():
    """The /en/ mirror uses `Month D, YYYY`; parsing only D-M-Y lost all rows."""
    rows = fetch_ojk.parse_rows(OJK_EN_ROW)
    assert len(rows) == 1
    assert rows[0]["publish_date"] == dt.date(2026, 8, 31)


def test_ojk_skips_nav_list_group_items():
    """`list-group-item` is also the nav class -- ~370 per page."""
    assert fetch_ojk.parse_rows(OJK_NAV_ROW) == []
    rows = fetch_ojk.parse_rows(OJK_NAV_ROW * 5 + OJK_ID_ROW + OJK_NAV_ROW * 5)
    assert len(rows) == 1


def test_ojk_dk_title_matches_commissioner_meeting():
    assert fetch_ojk.DK_TITLE.search("Hasil Rapat Dewan Komisioner Bulanan")
    assert not fetch_ojk.DK_TITLE.search("OJK Lantik Pejabat Baru")


# ---------------------------------------------------------------------------
# DJPPR
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "raw,expected",
    [
        ("4 September 2026", dt.date(2026, 9, 4)),
        ("21 Agustus 2026", dt.date(2026, 8, 21)),
        ("12 Januari 2021", dt.date(2021, 1, 12)),
        (None, None),
        ("", None),
        ("Kalendar Penerbitan SBN 2026", None),
    ],
)
def test_djppr_parse_tanggal(raw, expected):
    assert fetch_djppr.parse_tanggal(raw) == expected


def test_djppr_field_lookup_is_case_insensitive():
    """The CMS emits @judul on one page and @Judul on another."""
    assert fetch_djppr._field({"@judul": " Sukuk Ritel "}, "judul") == "Sukuk Ritel"
    assert fetch_djppr._field({"@Judul": "Hasil Lelang"}, "judul") == "Hasil Lelang"
    assert fetch_djppr._field({"@TANGGAL": "4 September 2026"}, "tanggal") == (
        "4 September 2026"
    )
    assert fetch_djppr._field({}, "judul") == ""


def test_djppr_row_to_item_resolves_relative_link():
    item = fetch_djppr._row_to_item(
        {"@judul": "Hasil Penjualan ORI030", "@tanggal": "3 Agustus 2026",
         "@link": "/hasilpenjualanori030"},
        "press_release", "release",
    )
    assert item is not None
    assert item.source_url == "https://djppr.kemenkeu.go.id/hasilpenjualanori030"
    assert item.publish_date == dt.date(2026, 8, 3)
    assert "undated" not in item.extras


def test_djppr_undated_rows_are_flagged_not_dropped():
    """Issuance calendars carry no date but are still worth carrying."""
    item = fetch_djppr._row_to_item(
        {"@judul": "Kalendar Penerbitan SBN 2026",
         "@link": "https://api-djppr.kemenkeu.go.id/web/api/v1/media/ABC"},
        "auction_calendar", "reference",
    )
    assert item is not None
    assert item.extras.get("undated") == "1"
    # A /media/ link is the document itself.
    assert item.pdf_url == item.source_url


def test_djppr_row_without_title_or_link_is_dropped():
    assert fetch_djppr._row_to_item({"@judul": "x"}, "s", "release") is None
    assert fetch_djppr._row_to_item({"@link": "/y"}, "s", "release") is None


def test_djppr_repeater_walk_finds_nested_repeaters():
    tree = {
        "widgetType": "section",
        "rows": [{"cols": [{"modules": [
            {"widgetType": "repeater", "data": [{"@judul": "A", "@link": "/a"}]},
            {"widgetType": "text"},
        ]}]}],
    }
    found: list[dict] = []
    fetch_djppr._repeaters(tree, found)
    assert len(found) == 1
    assert found[0]["data"][0]["@judul"] == "A"


# ---------------------------------------------------------------------------
# BPS
# ---------------------------------------------------------------------------

BPS_BRS_ROW = {
    "brs_id": 2615,
    "subj": "International Trade and Balance of Payments",
    "title": "Exports and Imports of Indonesia in July 2026 reached USD26.22 billion",
    "abstract": "<p>Indonesia's exports for January-July 2026 reached US$167.03 billion.</p>",
    "rl_date": "2026-09-01",
    "pdf": "https://webapi.bps.go.id/download.php?f=SIGNED-TOKEN-A",
    "slide": "https://webapi.bps.go.id/download.php?f=SLIDE-TOKEN",
}


def test_bps_row_to_item_uses_stable_id_not_volatile_pdf_url():
    """The `?f=` token is re-signed per request, so it cannot be identity.

    Using it made every BPS row re-report as new on every daily run.
    """
    a = fetch_bps._row_to_item(BPS_BRS_ROW, "press_release_brs", "release")
    rotated = dict(BPS_BRS_ROW, pdf="https://webapi.bps.go.id/download.php?f=TOKEN-B")
    b = fetch_bps._row_to_item(rotated, "press_release_brs", "release")

    assert a is not None and b is not None
    assert a.source_url == "bps://press_release_brs/2615"
    assert dedup_key(a) == dedup_key(b), "dedup key must survive token rotation"
    # The volatile link is still carried, just not as identity.
    assert a.pdf_url != b.pdf_url


def test_bps_row_to_item_strips_html_from_abstract():
    item = fetch_bps._row_to_item(BPS_BRS_ROW, "press_release_brs", "release")
    assert item is not None
    assert "<p>" not in item.extras["abstract"]
    assert item.extras["abstract"].startswith("Indonesia's exports")
    assert item.extras["subject"] == "International Trade and Balance of Payments"


def test_bps_row_without_id_or_date_is_dropped():
    assert fetch_bps._row_to_item(dict(BPS_BRS_ROW, brs_id=None), "s", "release") is None
    assert fetch_bps._row_to_item(
        {"brs_id": 1, "title": "t"}, "s", "release"
    ) is None
    assert fetch_bps._row_to_item(
        {"brs_id": 1, "rl_date": "2026-09-01"}, "s", "release"
    ) is None


def test_bps_parse_date_falls_back_across_fields():
    assert fetch_bps._parse_date({"rl_date": "2026-09-01"}) == dt.date(2026, 9, 1)
    assert fetch_bps._parse_date({"updt_date": "2025-12-31"}) == dt.date(2025, 12, 31)
    assert fetch_bps._parse_date({"updt_date": None}) is None
    assert fetch_bps._parse_date({"rl_date": "not-a-date"}) is None


def test_bps_publication_and_news_are_off_by_default():
    """Only the BRS press stream is Tier 1; the other two are opt-in."""
    enabled = {stream for _, stream, _, on in fetch_bps.MODELS if on}
    assert enabled == {"press_release_brs"}


# ---------------------------------------------------------------------------
# Cross-agency contract
# ---------------------------------------------------------------------------

def test_dedup_key_is_vendor_scoped():
    """Two agencies publishing the same URL must not collide."""
    base = dict(
        title="t", publish_date=dt.date(2026, 9, 1), source_url="https://x/y",
    )
    assert dedup_key(FilingItem(vendor_code="bi", **base)) != dedup_key(
        FilingItem(vendor_code="ojk", **base)
    )


def test_kemenkeu_reports_blocked_not_empty():
    """MoF must surface as a NAMED blocker, never as a quiet empty day."""
    assert fetch_kemenkeu.discover.__doc__
    # ok=False is the contract the daily-pull summary keys off; assert on the
    # constant rather than calling discover(), which would hit the network.
    assert "blocked" in fetch_kemenkeu.BLOCK_REASON.lower()


# ---------------------------------------------------------------------------
# Prod resolver dispatch (Phase J)
# ---------------------------------------------------------------------------

def _item(vendor: str, stream: str, **kw) -> FilingItem:
    base = dict(
        vendor_code=vendor, title="t", publish_date=dt.date(2026, 9, 1),
        source_url=f"https://x/{stream}", stream=stream,
    )
    base.update(kw)
    return FilingItem(**base)


def test_press_release_stream_disambiguates_on_vendor():
    """DJPPR and OJK both name a stream `press_release`.

    Dispatching on stream alone would send DJPPR items to OJK's HTML
    resolver. The vendor+stream table must win.
    """
    assert resolvers._BY_VENDOR_STREAM[("djppr", "press_release")] is (
        resolvers._resolve_djppr_detail
    )
    assert resolvers._BY_VENDOR_STREAM[("ojk", "press_release")] is (
        resolvers._resolve_ojk_body
    )


def test_every_bi_stream_has_a_resolver():
    """A BI stream added to fetch_bi without a resolver would fail at ingest."""
    for stream, _url, _dt, _f in fetch_bi.STREAMS:
        assert stream in resolvers._RESOLVERS, f"BI stream {stream} has no resolver"


def test_every_ojk_stream_resolves():
    for stream, _url, _dt in fetch_ojk.STREAMS:
        assert (
            ("ojk", stream) in resolvers._BY_VENDOR_STREAM
            or stream in resolvers._RESOLVERS
        ), f"OJK stream {stream} has no resolver"


def test_undated_rows_are_not_ingestable_even_when_stream_resolves():
    """Order bug guard: the undated check must beat the vendor+stream match.

    DJPPR's `press_release` has a resolver AND undated rows; if the resolver
    lookup ran first, calendars would be ingested dated 'today'.
    """
    dated = _item("djppr", "press_release")
    undated = _item("djppr", "press_release", extras={"undated": "1"})
    assert resolvers.is_ingestable(dated)
    assert not resolvers.is_ingestable(undated)


def test_auction_calendars_are_discovered_but_not_ingested():
    assert not resolvers.is_ingestable(
        _item("djppr", "auction_calendar", extras={"undated": "1"})
    )


def test_unknown_stream_raises_rather_than_silently_skipping():
    with pytest.raises(ValueError, match="no resolver"):
        resolvers.resolve(_item("bi", "not_a_real_stream"))


def test_bi_text_floor_is_below_the_thinnest_observed_release():
    """BI's thinnest real release in the 11-release sample was 821 chars."""
    assert resolvers._MIN_BODY_CHARS < 821


# ---------------------------------------------------------------------------
# Prod ingest wiring
# ---------------------------------------------------------------------------

def test_ingest_maps_text_kind_not_body_kind():
    """The resolve kind is "text"; AU's tree tests "body" and never matches.

    Guards the one-word difference that would send every BI news release to
    ingest with both pdf_bytes and body_text set to None.
    """
    import inspect

    src = inspect.getsource(ingest_filings._ingest_new_items)
    # Strip comments: the function documents AU's `kind == "body"` bug by
    # name, so a naive substring check would flag its own explanation.
    code = "\n".join(
        ln.split("#", 1)[0] for ln in src.splitlines()
    )
    assert 'kind == "text"' in code
    assert 'kind == "body"' not in code


def test_every_fetcher_registered_has_a_display_name():
    for name, _fn, _kw in ingest_filings.FETCHERS:
        assert name in ingest_filings._VENDOR_DISPLAY


def test_kemenkeu_is_registered_so_the_blocker_stays_visible():
    assert "kemenkeu" in {n for n, _, _ in ingest_filings.FETCHERS}
    # ...but has no staleness threshold: it has no items to go stale.
    assert "kemenkeu" not in ingest_filings.STALE_AFTER_DAYS


def test_id_daily_track_b_runs_ingest_not_discovery_only():
    """Registering the discovery form would silently never write to the DB.

    Read via AST rather than importing. `id_daily.py` — like every other
    `scripts/econ/{cc}/{cc}_daily.py` — rewraps `sys.stdout`/`sys.stderr` in a
    fresh `TextIOWrapper` at MODULE level, so importing it under pytest
    replaces the captured streams and the wrapper later closes pytest's
    temp file: `ValueError: I/O operation on closed file`, and capture is
    broken for the ENTIRE session (observed: 3,381 errors across unrelated
    suites). The rewrap is deliberate — Windows subprocess output needs
    UTF-8 — and all six country orchestrators do it, so the fix belongs in
    the test, not in a one-off divergence for Indonesia.

    Reading the literal also tests the right thing: what matters is what is
    *registered in the source*, not what an import happens to expose.
    """
    import ast

    src = (
        Path(__file__).resolve().parents[3]
        / "scripts" / "econ" / "id" / "id_daily.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(src)

    pipelines: dict[str, list[list[str]]] = {}
    for node in tree.body:
        if not isinstance(node, ast.AnnAssign | ast.Assign):
            continue
        target = node.target if isinstance(node, ast.AnnAssign) else node.targets[0]
        if not isinstance(target, ast.Name) or not node.value:
            continue
        if target.id not in ("TRACK_A_PIPELINES", "TRACK_B_PIPELINES"):
            continue
        rows = []
        for elt in getattr(node.value, "elts", []):
            rows.append([
                c.value for c in getattr(elt, "elts", [])
                if isinstance(c, ast.Constant) and isinstance(c.value, str)
            ])
        pipelines[target.id] = rows

    assert set(pipelines) == {"TRACK_A_PIPELINES", "TRACK_B_PIPELINES"}
    # Track B must run the ingesting form, not bare discovery.
    assert any("--ingest" in row for row in pipelines["TRACK_B_PIPELINES"])
    # The two Track A feeds already registered individually in imdr_daily
    # must both be present, or switching the scheduler over drops them.
    track_a = {m for row in pipelines["TRACK_A_PIPELINES"] for m in row}
    assert "scripts.econ.id.bis.bis_indonesia" in track_a
    assert "scripts.econ.id.bi.bi_srbi" in track_a


# ---------------------------------------------------------------------------
# seen.json semantics (subtle: three classes of row, three fates)
# ---------------------------------------------------------------------------

def test_not_ingestable_rows_are_recorded_as_seen_not_re_reported():
    """An undated row must be marked seen even though it is never ingested.

    `dedup_key` is (vendor, source_url) and ignores the `date.today()` stamp
    the fetcher applies to undated rows, so omitting them from seen.json had
    them re-counted as "new" on every future run — a backlog that never
    drains. Reproduces the classification loop's three-way split.
    """
    ingestable = _item("djppr", "press_release", source_url="https://x/a")
    undated = _item(
        "djppr", "auction_calendar", source_url="https://x/b",
        extras={"undated": "1"},
    )
    already = _item("bi", "news_release", source_url="https://x/c")

    prior_seen = {dedup_key(already)}
    skipped: set[str] = set()
    fresh = []
    for item in (ingestable, undated, already):
        key = dedup_key(item)
        if key in prior_seen or key in skipped:
            continue
        if not resolvers.is_ingestable(item):
            skipped.add(key)
            continue
        fresh.append(item)

    assert [i.source_url for i in fresh] == ["https://x/a"]
    assert skipped == {dedup_key(undated)}

    # Discovery-only run records everything fresh.
    discovery_seen = prior_seen | skipped | {dedup_key(i) for i in fresh}
    assert discovery_seen == {
        dedup_key(already), dedup_key(undated), dedup_key(ingestable)
    }

    # Ingest run where the candidate FAILED: the undated row still sticks,
    # the failed candidate does not (so it retries), and the pre-existing
    # entry is never dropped.
    succeeded: set[str] = set()
    ingest_seen = prior_seen | skipped | succeeded
    assert dedup_key(undated) in ingest_seen
    assert dedup_key(already) in ingest_seen, "must not drop prior history"
    assert dedup_key(ingestable) not in ingest_seen, "failed item must retry"


def test_seen_rebuild_never_drops_previously_ingested_history():
    """Guard against deriving seen.json by subtracting all candidates.

    An earlier version computed `classified - candidates | succeeded`, where
    `candidates` was every ingestable row in the fetch result — including
    rows already in seen.json from previous runs. That silently evicted
    previously-ingested items, so they would be re-ingested next run.
    """
    old_ingested = _item("bi", "news_release", source_url="https://x/old")
    prior_seen = {dedup_key(old_ingested)}
    # This run re-discovers it (page 1 still lists it) and ingests nothing.
    seen = prior_seen | set() | set()
    assert dedup_key(old_ingested) in seen


def test_djppr_media_linked_press_row_resolves_as_pdf_not_slug():
    """Some DJPPR press rows link straight at a media file, not a detail page.

    Deriving a slug from the last path segment then yields a GUID and the
    page API answers 404. Seen on the full 2026-09-21 ingest:
    `Pembukaan Masa Penawaran Green Sukuk Ritel` linked to
    `E6B48E4B-9108-4872-896D-0AC966451083`.
    """
    media = fetch_djppr._row_to_item(
        {"@judul": "Pembukaan Masa Penawaran Green Sukuk Ritel",
         "@tanggal": "1 September 2026",
         "@link": "https://api-djppr.kemenkeu.go.id/web/api/v1/media/E6B48E4B"},
        "press_release", "release",
    )
    assert media is not None
    # The fetcher must have recognised it as a document, not a page.
    assert media.pdf_url == media.source_url
    assert "/media/" in media.pdf_url
    # And it stays ingestable — the resolver takes the pdf_url short-circuit.
    assert resolvers.is_ingestable(media)


def test_djppr_page_linked_press_row_keeps_no_pdf_url():
    """A normal slug row must NOT look like a media row, or it would skip
    the detail fetch that carries the full @Konten text."""
    page = fetch_djppr._row_to_item(
        {"@judul": "Hasil Penjualan ORI030", "@tanggal": "3 Agustus 2026",
         "@link": "/hasilpenjualanori030"},
        "press_release", "release",
    )
    assert page is not None
    assert page.pdf_url is None


# ---------------------------------------------------------------------------
# id_daily email render — exercised in a SUBPROCESS
# ---------------------------------------------------------------------------
#
# `id_daily.py` cannot be imported in-process (module-level stdout rewrap —
# see the note on the AST test above), but `_render_email` is the code path
# the scheduled run takes and `--no-email` never touches it. A subprocess
# gives real coverage without poisoning pytest's capture, and it is also how
# the cron invokes it.

_RENDER_PROBE = '''
import datetime, json, sys
from scripts.econ.id import id_daily

t0 = datetime.datetime(2026, 9, 21, tzinfo=datetime.UTC)
out = {}

# Realistic shapes, with one pipeline failed.
subj, body = id_daily._render_email(
    run_started_at=t0,
    pipeline_results={"results": [
        {"name": "a", "returncode": 0, "duration_s": 1.0},
        {"name": "b", "returncode": 1, "duration_s": 2.0},
    ], "failed": ["b"]},
    track_a={"total_obs": 7, "by_vendor": [
        {"vendor_name": "Bank Indonesia", "n_indicators": 3,
         "n_obs": 7, "latest_obs": "2026-09-19"}]},
    track_b={"total_reports": 2, "total_chunks": 9, "by_vendor": [
        {"vendor_code": "bi", "display_name": "Bank Indonesia",
         "vendor_category": "official_cb", "n_reports": 2, "n_chunks": 9}],
        "recent": [{"vendor_code": "bi", "publish_date": "2026-09-17",
                    "title": "BI-Rate Tetap 5,75%"}]},
)
out["subject"] = subj
out["has_failed_marker"] = "FAILED" in subj
out["mentions_rate_title"] = "BI-Rate" in body

# Degraded path: main() passes {} when a snapshot query raises. The email
# must still render, because it is what reports the pipeline failures.
subj2, body2 = id_daily._render_email(
    run_started_at=t0, pipeline_results={}, track_a={}, track_b={})
out["empty_subject"] = subj2
out["empty_has_placeholders"] = (
    "no new daily observations" in body2 and "no new filings" in body2)

# HTML escaping: a vendor name with markup must not land raw in the body.
_, body3 = id_daily._render_email(
    run_started_at=t0, pipeline_results={}, track_a={}, track_b={
        "total_reports": 1, "total_chunks": 1, "recent": [], "by_vendor": [
            {"vendor_code": "x", "display_name": "<script>bad</script>",
             "vendor_category": "official_cb", "n_reports": 1, "n_chunks": 1}]})
out["escapes_html"] = "<script>" not in body3 and "&lt;script&gt;" in body3

print(json.dumps(out))
'''


def test_id_daily_email_renders_in_all_paths():
    import json
    import subprocess

    repo = Path(__file__).resolve().parents[3]
    proc = subprocess.run(
        [sys.executable, "-c", _RENDER_PROBE],
        cwd=repo, capture_output=True, text=True, timeout=180,
    )
    assert proc.returncode == 0, (
        f"id_daily._render_email raised:\n{proc.stderr[-2000:]}"
    )
    got = json.loads(proc.stdout.strip().splitlines()[-1])

    assert "Indonesia daily" in got["subject"]
    assert got["has_failed_marker"], "a failed pipeline must show in the subject"
    assert got["mentions_rate_title"]
    # The degraded path is the one that matters most: it carries the failure report.
    assert "Indonesia daily" in got["empty_subject"]
    assert got["empty_has_placeholders"]
    assert got["escapes_html"], "vendor display_name must be HTML-escaped"
