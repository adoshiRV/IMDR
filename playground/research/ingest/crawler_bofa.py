"""Discover BofA Securities Mercury research via per-hub HTML scraping.

Pattern: **HSBC-style HTML scrape** (Liferay portal), with lazy URL
resolution via a Liferay portlet resource endpoint (per-tile POST to
get the signed ``rsch.baml.com/r?q=...`` URL).

Architecture
------------
1. Programmatic login via :mod:`login_bofa` (PingFederate stack, same as
   Barclays). Each crawl run re-authenticates (~15s) because BofA's
   Premia session tokens are session-scoped and don't survive
   ``context.close()``.

2. Per-hub walk over 22 production hubs (Equity Regional, Economics
   Overview/Country, Credit High Grade/High Yield/Securitized/EM
   FI/EM Corporate/Municipal/Strategy Americas, Rates Regional/
   Inflation, FX G10/Global, Commodities, Futures, Technical
   Analysis, Investment Themes, etc.). Each hub renders the latest
   ~25 reports per "series" in HTML.

3. Per-tile parse via regex on ``<table id="Table_report
   <SERIES>_<TITLE>" summary="Table of report <SERIES> <TITLE>">``.
   The SERIES slot is double-duty — flagship series names AND
   single-name subjects (Kosmos Energy Ltd, AA2000, etc.); this is
   the discriminator for the series-regex single-name drop.

4. 3-stage drop:
   - **Hub blanket**: drop everything in EQUITY hubs unless series
     is on a strategy keep-allowlist.
   - **Series single-name regex**: drop tiles whose SERIES looks
     like a corporate name (ends in Ltd/Inc/Corp/SA/PJSC/Holdings,
     or matches a 4-digit Japanese ticker pattern, or is on a
     known single-name DROP list).
   - **MBS data-table**: in ``credit_securitized`` hub, drop pool
     data tables (Fannie/Freddie/Ginnie Mae * Servicer/Vintage/...)
     which are machine-generated data, not prose research.

5. URL resolution: for each kept tile, POST to the per-portlet
   ``htmlResourceUrl`` template with ``pidvalue`` substituted →
   response body is the signed ``rsch.baml.com/r?q=...`` URL. We
   append ``&cmd=PDF`` for the pdf_url. Actual PDF fetching needs
   Playwright ``page.goto()`` (SAML autopost handshake) — see
   :mod:`fetch_bofa`.

Pagination not yet wired — one pass through 22 hubs gives ~250
unique tiles (latest 5-15 per series per hub). If we need a deeper
historical window we'd add the Liferay "more" portlet action URL
walk per series.

See ``docs/admin/research/scrapers/bofa.md`` for the full spec.
"""
from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Iterable
from urllib.parse import unquote_plus

from .filters import bofa as _bofa_filter

# ---------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------

# 22 production hubs (Advanced Search + Structured Products excluded —
# both returned 0 tiles in the Phase 2 probe).
HUB_URLS: tuple[tuple[str, str], ...] = (
    # MACRO / ECONOMICS
    ("economics_overview",          "https://markets.ml.com/economics-overview"),
    ("economics_country",           "https://markets.ml.com/economics-country"),
    ("investment_themes",           "https://markets.ml.com/researchlibrary/investment-themes"),
    # RATES
    ("rates_regional",              "https://markets.ml.com/global-overview"),
    ("rates_inflation",             "https://markets.ml.com/inflation"),
    # FX
    ("fx_g10",                      "https://markets.ml.com/researchlibrary/global-fx-strategy"),
    ("fx_global",                   "https://markets.ml.com/foreign-exchange"),
    # COMMODITIES
    ("commodities",                 "https://markets.ml.com/researchlibrary/commodities"),
    ("futures",                     "https://markets.ml.com/futures/overview"),
    # CREDIT
    ("credit_global",               "https://markets.ml.com/researchlibrary/global"),
    ("credit_strategy_americas",    "https://markets.ml.com/credit-strategy-americas"),
    ("credit_high_grade",           "https://markets.ml.com/high-grade"),
    ("credit_high_yield",           "https://markets.ml.com/high-yield-distressed"),
    ("credit_securitized",          "https://markets.ml.com/mbs"),
    ("credit_em_fi",                "https://markets.ml.com/emerging-markets-global"),
    ("credit_em_corporate",         "https://markets.ml.com/em-corporate-credit"),
    ("credit_municipal",            "https://markets.ml.com/municipal"),
    # EQUITY (mostly drop — single-name heavy)
    ("equity_regional",             "https://markets.ml.com/researchlibrary/global1"),
    ("equity_etf",                  "https://markets.ml.com/researchlibrary/exchange-traded-funds"),
    ("equity_em_equity",            "https://markets.ml.com/gem-equity-strategy-and-equity-fundamental"),
    # TECHNICAL
    ("technical_analysis",          "https://markets.ml.com/researchlibrary/technical-analysis"),
)

# Equity hubs: blanket-drop except for series matching the keep-allowlist.
_EQUITY_HUBS: frozenset[str] = frozenset({
    "equity_regional", "equity_em_equity", "equity_etf",
})

# Strategy-style equity series we KEEP (aggregate not single-name).
_EQUITY_KEEP_SERIES: frozenset[str] = frozenset({
    "LatAm Trading Catalysts", "APAC Signal-to-Noise", "Latam Equity Quant",
    "The ETF Angle", "Exchange Traded Funds", "The LatAm Feedbeker",
    "LatAm Earnings Tracker", "LatAm Fund Manager Survey",
    "European Call Overwriting Wizard", "EEMEA Equity Strategy Watch",
    "Transportation - Trucking",
    "LatAm Transportation & Capital Goods", "Greater China Industrials",
    "Sportswear - China", "Biotechnology",
})

# Series that are pure admin / invitations / reminders — drop unconditionally.
_ADMIN_DROP_SERIES: frozenset[str] = frozenset({
    "Conference Call Invitation",
})


# Pre-known single-name corporate / equity issuers from Phase 2 probe.
_KNOWN_SINGLE_NAME_SERIES: frozenset[str] = frozenset({
    "Kosmos Energy Ltd",
    "CD&R Smokey Buyer, Inc. (subsidiary issuer)",
    "AA2000",
    "Telefonica Moviles Chile SA",
    "Codelco",
    "Osaka Soda (4046)",
    "Intertek Group",
    "TFI International",
    "UP Fintech Holding",
    "Dasa",
    "WT Microelectronics",
    "Daily Boarding",
})

# Corporate-name suffix pattern (catches Ltd / Inc / Corp / SA / PJSC /
# Holding(s) / Group / Plc — common single-name terminators).
_CORPORATE_SUFFIX_RE = re.compile(
    r"\b(?:Ltd\.?|Inc\.?|Corp\.?|S\.?A\.?(?:\.E\.?)?|PJSC|Plc|"
    r"Holding(?:s)?|Group|Industries|GmbH|N\.?V\.?|AG|Co\.?,?\s*Ltd\.?)"
    r"(?:\s*\(.+?\))?$",
    re.IGNORECASE,
)

# Japanese ticker pattern: "Osaka Soda (4046)" → matches.
_JP_TICKER_RE = re.compile(r"\(\d{4}\)\s*$")

# MBS data-table series pattern. Tiles in `credit_securitized` matching
# this regex are machine-generated pool reports, not prose research.
_MBS_DATATABLE_RE = re.compile(
    r"\b(Fannie|Freddie|Ginnie)\s+Mae\b.*\b"
    r"(Servicer|Vintage|Coupon|Pool|S-curve|by State|by Coupon|by Issuer)\b",
    re.IGNORECASE,
)

# Tile / structure regexes ---------------------------------------------

# <table id="Table_report SERIES_TITLE" summary="...">...</table>
_TILE_BLOCK_RE = re.compile(
    r'<table[^>]+?id="Table_report\s+([^"_]+?)_([^"]+?)"[^>]*?'
    r'summary="([^"]+?)"[^>]*>(.*?)</table>',
    re.IGNORECASE | re.DOTALL,
)

# Anchor inside a tile: id="_<NAMESPACE>_<REPORT_ID>" onclick=...checkAnalystHover OR htmlIconClickOnCachedPortlet
_TILE_ANCHOR_RE = re.compile(
    r'<a id="_multiDataReports_WAR_researchlibrary_portlet_INSTANCE_'
    r'([A-Za-z0-9]+)_(\d{6,10})"',
    re.IGNORECASE,
)

# Per-hub pdfResourceUrl template — one per portlet INSTANCE.
# Symmetric to htmlResourceUrl but resolves to a direct-PDF endpoint
# on research1.ml.com/C?q=... (returns application/pdf bytes directly,
# no SAML handshake needed). See docs/admin/research/scrapers/bofa.md.
_PDF_RESOURCE_URL_RE = re.compile(
    r'<input[^>]*id="_multiDataReports_WAR_researchlibrary_portlet_INSTANCE_'
    r'([A-Za-z0-9]+)_pdfResourceUrl"[^>]*value="([^"]+)"',
    re.IGNORECASE,
)

# Primary author span inside a tile: <a onclick="navigateToResearchSearchProxy('First+Last')">...</a>
_PRIMARY_AUTHOR_RE = re.compile(
    r"navigateToResearchSearchProxy\('([^']+)'\)",
)

# Date string in tile: "29-May-2026 03:27:58" or "29-May-2026 06:00:24 AM"
_DATE_RE = re.compile(
    r"(\d{1,2}-(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)-\d{4}"
    r"\s+\d{1,2}:\d{2}:\d{2}(?:\s*[AP]M)?)",
)

_MONTH_TO_NUM = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}

# ---------------------------------------------------------------------
# ReportRef dataclass
# ---------------------------------------------------------------------

@dataclass(slots=True, frozen=True)
class ReportRef:
    """One BofA report tile discovered during the hub walk.

    ``pdf_url`` is the signed ``rsch.baml.com/r?q=...&cmd=PDF`` URL
    resolved via the portlet htmlResourceUrl POST. PDF fetching must
    use Playwright ``page.goto()`` to handle the SAML autopost — see
    :mod:`fetch_bofa`.
    """
    url: str
    pdf_url: str
    uuid: str               # numeric BofA report_id, e.g. "12978792"
    title: str
    publish_date: date

    series: str = ""        # Flagship series name OR single-name subject
    subject: str = ""       # Currently a copy of `series`; left distinct for future
    hub: str = ""           # which hub URL surfaced this tile
    portlet_instance: str = ""  # Liferay portlet INSTANCE id (for URL resolution)
    analyst_primary: str = ""
    analysts: tuple[str, ...] = ()
    abstract: str = ""
    summary: str = ""       # raw `summary` attribute on the table

    # Asset-class hint derived from the hub (consumed by classifier as
    # a Tier-1 fallback when no per-tile structured signal is available).
    asset_class_hint: str = ""

    # Diagnostic — drop reason if this tile would be dropped. The
    # discover_reports() loop calls _drop_reason() and only returns
    # ReportRefs that survived. This field is left empty on returned
    # refs (it's only used in the loop locally).
    drop_reason: str = ""


# ---------------------------------------------------------------------
# Hub → asset-class hint (for the classifier; not a drop signal)
# ---------------------------------------------------------------------

_HUB_ASSET_CLASS: dict[str, str] = {
    "economics_overview": "MACRO",
    "economics_country": "MACRO",
    "investment_themes": "STRATEGY",
    "rates_regional": "RATES",
    "rates_inflation": "RATES",
    "fx_g10": "FX",
    "fx_global": "FX",
    "commodities": "COMMODITIES",
    "futures": "COMMODITIES",
    "credit_global": "CREDIT",
    "credit_strategy_americas": "CREDIT",
    "credit_high_grade": "CREDIT",
    "credit_high_yield": "CREDIT",
    "credit_securitized": "CREDIT",
    "credit_em_fi": "CREDIT",
    "credit_em_corporate": "CREDIT",
    "credit_municipal": "CREDIT",
    "equity_regional": "EQUITY",
    "equity_etf": "STRATEGY",
    "equity_em_equity": "EQUITY",
    "technical_analysis": "STRATEGY",
}


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def _decode_entities(s: str) -> str:
    return (
        s.replace("&amp;", "&")
        .replace("&nbsp;", " ")
        .replace("&#039;", "'")
        .replace("&quot;", '"')
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&hellip;", "…")
    )


def _parse_bofa_date(text: str) -> date | None:
    """Locale-safe parse of "29-May-2026 03:27:58 PM" → date."""
    if not text:
        return None
    m = _DATE_RE.search(text)
    if not m:
        return None
    s = m.group(1).strip()
    parts = s.split("-", 2)
    if len(parts) != 3:
        return None
    try:
        day = int(parts[0])
    except ValueError:
        return None
    month = _MONTH_TO_NUM.get(parts[1][:3].title())
    if not month:
        return None
    year_part = parts[2].split()[0]
    try:
        year = int(year_part)
    except ValueError:
        return None
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _extract_templates(html: str) -> dict[str, str]:
    """Build {portlet_instance: pdfResourceUrl_template} map from hub HTML.

    The PDF resource URL resolves (via POST with ``pidvalue → report_id``
    substituted) to a direct-PDF endpoint on
    ``research1.ml.com/C?q=...&e=...&h=...`` returning
    ``application/pdf`` bytes. No SAML handshake required.
    """
    out: dict[str, str] = {}
    for m in _PDF_RESOURCE_URL_RE.finditer(html):
        out[m.group(1)] = _decode_entities(m.group(2))
    return out


def _is_corporate_name(series: str) -> bool:
    """Return True if SERIES looks like a single-name corporate / equity issuer."""
    if not series:
        return False
    if series in _KNOWN_SINGLE_NAME_SERIES:
        return True
    if _JP_TICKER_RE.search(series):
        return True
    if _CORPORATE_SUFFIX_RE.search(series):
        return True
    return False


def _is_mbs_datatable(series: str) -> bool:
    return bool(_MBS_DATATABLE_RE.search(series or ""))


def _drop_reason(*, hub: str, series: str, title: str = "") -> str | None:
    """3-stage drop check. Returns a short reason string, or None to keep."""
    # 0. Admin-series unconditional drop (Conference Call Invitation etc.)
    if series in _ADMIN_DROP_SERIES:
        return f"admin-series:{series}"
    # 0a. Title-prefix admin drop ("Reminder: " for upcoming-call pings).
    if title and title.strip().lower().startswith("reminder:"):
        return "title-prefix:reminder"
    # 1. Hub-level blanket: equity hubs default-drop unless series is on
    # the keep-allowlist.
    if hub in _EQUITY_HUBS and series not in _EQUITY_KEEP_SERIES:
        # Even within equity hubs, allow series that look like aggregate
        # strategy (don't match corporate-name heuristics) — they're
        # rare but worth not dropping by default.
        # Actually safer: be strict on equity hubs since the user posture
        # is "no single-name equity". Drop unless explicit keep.
        return f"equity-hub-blanket:{hub}"
    # 2. Series single-name regex.
    if _is_corporate_name(series):
        return f"single-name-corporate:{series[:40]}"
    # 3. MBS data-table.
    if hub == "credit_securitized" and _is_mbs_datatable(series):
        return f"mbs-datatable:{series[:40]}"
    return None


# ---------------------------------------------------------------------
# Tile extraction
# ---------------------------------------------------------------------

def _parse_tiles(html: str) -> list[dict]:
    tiles: list[dict] = []
    for m in _TILE_BLOCK_RE.finditer(html):
        series = _decode_entities(m.group(1).strip())
        title = _decode_entities(m.group(2).strip())
        summary = _decode_entities(m.group(3).strip())
        body = m.group(4)

        anchor = _TILE_ANCHOR_RE.search(body)
        if not anchor:
            # No clickable anchor → no report_id → can't resolve URL.
            # Skip rather than emit a half-broken ref.
            continue
        portlet_instance = anchor.group(1)
        report_id = anchor.group(2)

        # Primary author (first navigateToResearchSearchProxy call inside the tile).
        # Values are URL-encoded ("David+Hauner%2C+CFA" → "David Hauner, CFA").
        analyst_primary = ""
        analysts: list[str] = []
        for am in _PRIMARY_AUTHOR_RE.finditer(body):
            name = unquote_plus(am.group(1)).strip()
            if name and name not in analysts:
                analysts.append(name)
        if analysts:
            analyst_primary = analysts[0]

        pdate = _parse_bofa_date(body)

        tiles.append({
            "series": series,
            "title": title,
            "summary": summary,
            "portlet_instance": portlet_instance,
            "report_id": report_id,
            "analyst_primary": analyst_primary,
            "analysts": tuple(analysts),
            "publish_date": pdate,
        })
    return tiles


# ---------------------------------------------------------------------
# URL resolver (portlet htmlResourceUrl POST → signed rsch.baml.com URL)
# ---------------------------------------------------------------------

async def _resolve_pdf_url(
    ctx, *, template: str, report_id: str,
) -> str | None:
    """POST to the per-portlet ``pdfResourceUrl`` with ``pidvalue``
    substituted. Response body is the direct PDF URL on
    ``research1.ml.com/C?q=...&e=...&h=...``.

    Returns the URL or None on failure. ``ctx.request.get(url)`` then
    returns ``%PDF-...`` bytes directly — no SAML autopost needed.
    """
    url = template.replace("pidvalue", report_id)
    try:
        resp = await ctx.request.post(
            url,
            headers={"x-requested-with": "XMLHttpRequest"},
        )
    except Exception:  # noqa: BLE001
        return None
    if resp.status != 200:
        return None
    try:
        body = (await resp.text()).strip()
    except Exception:  # noqa: BLE001
        return None
    # research1.ml.com/C?... is the direct-PDF host; rsch.baml.com is
    # the HTML viewer host (used as a fallback if BofA ever changes
    # the resource id).
    m = re.search(r"https://(?:research1\.ml\.com|rsch\.baml\.com)/[^\s\"'<]+", body)
    if not m:
        return None
    return m.group(0)


# ---------------------------------------------------------------------
# Hub walker
# ---------------------------------------------------------------------

async def _walk_hub(
    ctx, hub_name: str, hub_url: str, *,
    since: date | None, until: date | None,
    resolve_urls: bool,
) -> tuple[list[ReportRef], dict]:
    """Fetch one hub HTML, parse tiles, apply drops, optionally resolve
    signed URLs. Returns (kept_refs, diag) where diag has the raw
    counts (parsed / dropped / kept / no_url) for logging."""
    page = await ctx.new_page()
    try:
        await page.goto(hub_url, wait_until="domcontentloaded", timeout=45000)
        try:
            await page.wait_for_load_state("networkidle", timeout=20000)
        except Exception:  # noqa: BLE001
            pass
        await page.wait_for_timeout(2000)
        html = await page.content()
    except Exception as exc:  # noqa: BLE001
        print(f"    [{hub_name}] goto failed: {exc!s:.150}")
        try:
            await page.close()
        except Exception:  # noqa: BLE001
            pass
        return [], {"parsed": 0, "dropped": 0, "kept": 0, "no_url": 0,
                    "n_templates": 0}
    finally:
        try:
            await page.close()
        except Exception:  # noqa: BLE001
            pass

    templates = _extract_templates(html)
    tiles = _parse_tiles(html)
    asset_class_hint = _HUB_ASSET_CLASS.get(hub_name, "")

    kept_refs: list[ReportRef] = []
    n_dropped = 0
    n_no_url = 0
    drop_reasons_local: dict[str, int] = {}

    for tile in tiles:
        series = tile["series"]
        report_id = tile["report_id"]
        title = tile["title"]
        pdate = tile["publish_date"]

        reason = _drop_reason(hub=hub_name, series=series, title=title)
        if reason is not None:
            n_dropped += 1
            drop_reasons_local[reason.split(":", 1)[0]] = \
                drop_reasons_local.get(reason.split(":", 1)[0], 0) + 1
            continue

        # Credit-hub allowlist gate — default-drop unless series/title
        # matches macro/sovereign/strategy KEEP signals. Mirrors the
        # equity-hub blanket-drop for credit hubs.
        credit_reason = _bofa_filter.credit_hub_drop_reason(
            hub=hub_name, series=series, title=title,
        )
        if credit_reason is not None:
            n_dropped += 1
            drop_reasons_local[credit_reason.split(":", 1)[0]] = \
                drop_reasons_local.get(credit_reason.split(":", 1)[0], 0) + 1
            continue

        # Title-level filter — noise families + BofA-specific thin-title
        # patterns. This is the filter that was previously dead code because
        # the crawler never called it.
        skip_reason = _bofa_filter.should_exclude(title=title)
        if skip_reason is not None:
            n_dropped += 1
            drop_reasons_local[skip_reason.split(":", 1)[0]] = \
                drop_reasons_local.get(skip_reason.split(":", 1)[0], 0) + 1
            continue

        # Date filter — belt-and-braces; the hub HTML only renders the
        # latest ~25, but explicit since/until lets callers do narrower
        # backfills.
        if pdate is None:
            # Missing date → keep, with no date filter applied. The
            # classifier downstream will need to handle no-date case.
            pass
        else:
            if since is not None and pdate < since:
                n_dropped += 1
                drop_reasons_local["before-since"] = \
                    drop_reasons_local.get("before-since", 0) + 1
                continue
            if until is not None and pdate > until:
                n_dropped += 1
                drop_reasons_local["after-until"] = \
                    drop_reasons_local.get("after-until", 0) + 1
                continue

        # Resolve PDF URL if requested.
        pdf_url = ""
        if resolve_urls:
            tmpl = templates.get(tile["portlet_instance"])
            if tmpl:
                pdf_url = await _resolve_pdf_url(
                    ctx, template=tmpl, report_id=report_id,
                ) or ""
            if not pdf_url:
                n_no_url += 1
                # Skip URL-less rows — the writer would have no way to
                # fetch the PDF. Surfaces transient resolver failures.
                continue

        ref = ReportRef(
            url=pdf_url or f"bofa://{report_id}",
            pdf_url=pdf_url or "",
            uuid=report_id,
            title=title or f"bofa/{report_id}",
            publish_date=pdate or date.today(),
            series=series,
            subject=series,
            hub=hub_name,
            portlet_instance=tile["portlet_instance"],
            analyst_primary=tile["analyst_primary"],
            analysts=tile["analysts"],
            summary=tile["summary"],
            asset_class_hint=asset_class_hint,
        )
        kept_refs.append(ref)

    diag = {
        "parsed": len(tiles),
        "dropped": n_dropped,
        "kept": len(kept_refs),
        "no_url": n_no_url,
        "n_templates": len(templates),
        "drop_reasons": drop_reasons_local,
    }
    return kept_refs, diag


# ---------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------

async def discover_reports(
    profile_dir: Path,
    *,
    hub_urls: Iterable[tuple[str, str]] | None = None,
    since: date | None = None,
    until: date | None = None,
    resolve_urls: bool = True,
) -> list[ReportRef]:
    """Walk BofA Mercury hubs, parse tiles, apply drops, optionally
    resolve signed URLs.

    Parameters
    ----------
    profile_dir
        Path to the persistent Playwright profile (cookies / preferences
        are restored from here even though the Premia session itself
        is re-established via programmatic login on every run).
    hub_urls
        Override the default 22-hub list — useful for smoke tests
        (e.g. just one or two hubs).
    since, until
        Inclusive date bounds. Defaults to no bound on either side.
    resolve_urls
        When True, POST to the per-tile htmlResourceUrl resolver to
        get the signed rsch.baml.com URL. Set False for a pure
        discovery probe (no resource POSTs at all).
    """
    import os  # noqa: PLC0415
    from playwright.async_api import async_playwright  # noqa: PLC0415

    hubs = list(hub_urls) if hub_urls is not None else list(HUB_URLS)

    # Read credentials from .env via os.environ (caller is expected to
    # have already populated them; ingest_today.py does this for us).
    user = os.environ.get("IMDR_RESEARCH_BOFA_USERNAME", "")
    pwd = os.environ.get("IMDR_RESEARCH_BOFA_PASSWORD", "")
    if not (user and pwd):
        raise RuntimeError(
            "IMDR_RESEARCH_BOFA_USERNAME / _PASSWORD missing from env. "
            "Populate .env or settings before invoking discover_reports."
        )

    print(
        f"  bofa per-hub crawl ({len(hubs)} hubs, "
        f"since={since}, until={until}, resolve_urls={resolve_urls})"
    )

    all_refs: list[ReportRef] = []
    by_id: set[str] = set()
    total_diag = {
        "parsed": 0, "dropped": 0, "kept": 0, "no_url": 0,
        "drop_reasons": {},
    }

    async with async_playwright() as pw:
        # MUST match the explorer's launch mode (headless=False matches
        # the UA that BofA Premia issued the session for). Per
        # project_bofa_onboarding.md, headless launches get redirected
        # to the login page when re-using a persistent-profile session.
        ctx = await pw.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            channel="chrome",
            headless=False,
            accept_downloads=True,
        )
        try:
            from .login_bofa import login as bofa_login  # noqa: PLC0415
            print(f"  Logging in as {user}...")
            await bofa_login(ctx, username=user, password=pwd)
            print("  ...login OK.")

            for hub_name, hub_url in hubs:
                print(f"  [{hub_name}]  GET {hub_url}")
                refs, diag = await _walk_hub(
                    ctx, hub_name, hub_url,
                    since=since, until=until,
                    resolve_urls=resolve_urls,
                )
                for r in refs:
                    if r.uuid in by_id:
                        continue
                    by_id.add(r.uuid)
                    all_refs.append(r)
                print(
                    f"    parsed={diag['parsed']:>4}  dropped={diag['dropped']:>4}  "
                    f"kept={diag['kept']:>3}  no_url={diag['no_url']}  "
                    f"templates={diag['n_templates']}"
                )
                # Roll-up diag
                for k in ("parsed", "dropped", "kept", "no_url"):
                    total_diag[k] += diag.get(k, 0)
                for r_reason, n in (diag.get("drop_reasons") or {}).items():
                    total_diag["drop_reasons"][r_reason] = \
                        total_diag["drop_reasons"].get(r_reason, 0) + n
        finally:
            await ctx.close()

    # Sort newest-first for caller convenience.
    all_refs.sort(key=lambda r: (r.publish_date, r.uuid), reverse=True)

    print()
    print(
        f"  TOTAL parsed={total_diag['parsed']}  dropped={total_diag['dropped']}  "
        f"kept={len(all_refs)} (unique)  no_url={total_diag['no_url']}"
    )
    if total_diag["drop_reasons"]:
        print(f"  drop reasons: {total_diag['drop_reasons']}")
    return all_refs
