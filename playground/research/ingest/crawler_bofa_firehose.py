"""BofA Securities Advanced Search firehose discovery path.

Parallel to :mod:`crawler_bofa` (which scrapes per-hub HTML tiles). This
module queries the Advanced Search page with a per-discipline filter and a
date window, then paginates through all results. Coverage is ~1,227
reports/week total vs ~240 tiles from the hub crawler.

Only macro-relevant disciplines are queried — single-name equity bulk
(Equity-Fundamental, Equity-Small Cap, etc.) is intentionally excluded.
Each discipline is mapped to a synthetic hub key that the existing
:mod:`classifiers.bofa` and :mod:`filters.bofa` recognise unchanged.

Public entry point
------------------
``discover_reports(profile_dir, *, disciplines=None, since=None, until=None,
                   resolve_urls=True) -> list[ReportRef]``

Reuses from :mod:`crawler_bofa`:
- ``ReportRef`` dataclass
- ``_parse_bofa_date``
- ``_resolve_pdf_url``
- ``_drop_reason``
- ``_HUB_ASSET_CLASS``

Also applies the same drop stack from :mod:`filters.bofa`:
``credit_hub_drop_reason`` + ``should_exclude``.
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from pathlib import Path
from typing import Sequence
from urllib.parse import unquote_plus

from .crawler_bofa import _decode_entities, _MONTH_TO_NUM  # noqa: PLC0415
from .filters import bofa as _bofa_filter

# ── Discipline → synthetic hub key ────────────────────────────────────────────
# Only macro-relevant disciplines; single-name equity bulk excluded.
# The hub key must be present in classifiers/bofa.py::_HUB_TO_ASSET_CLASS.

_DISCIPLINE_TO_HUB: dict[str, str] = {
    "Economics":                          "economics_overview",
    "Emerging Markets Economics":         "economics_country",
    "Country Investment Strategy":        "economics_overview",
    "Currency Strategy":                  "fx_global",
    "Rates Strategy":                     "rates_regional",
    "Fixed Income Strategy":              "rates_regional",
    "Fixed Income Technical Analysis":    "technical_analysis",
    "Technical Analysis":                 "technical_analysis",
    "Quantitative Strategy":              "technical_analysis",
    "Commodities":                        "commodities",
    "Multi-Asset Strategy":               "investment_themes",
    "Investment Strategy":                "investment_themes",
    "Credit Strategy":                    "credit_global",
    "High Yield Strategy":                "credit_high_yield",
    "Emerging Markets Debt Strategy":     "credit_em_fi",
    "Emerging Markets Credit":            "credit_em_corporate",
}

# Pagination cap — BofA renders at most 250 results per query.
_PAGE_CAP = 250

# Advanced search URL
_ADVSEARCH_URL = "https://markets.ml.com/researchlibrary/advancedsearch"

# Regex to locate the SearchCriteriaPortlet INSTANCE id at runtime.
# Matches: _SearchCriteriaPortlet_WAR_rlalerts_portlet_INSTANCE_<ID>_disciplineDropDown
_PFX_RE = re.compile(
    r"_SearchCriteriaPortlet_WAR_rlalerts_portlet_INSTANCE_([A-Za-z0-9]+)_disciplineDropDown"
)

# Regex to extract the SearchSummaryPortlet INSTANCE id (used in row anchors +
# pdfResourceUrl).
_SUMMARY_INST_RE = re.compile(
    r"_SearchSummaryPortlet_WAR_rlapp_portlet_INSTANCE_([A-Za-z0-9]+)_pdfResourceUrl"
)

# Count text: "1-25 of 1,227" or "1-25 of 48"
_COUNT_RE = re.compile(r"1-\d+\s+of\s+([\d,]+)")

# Each result row anchor:
#   <a id="_SearchSummaryPortlet_WAR_rlapp_portlet_INSTANCE_{INST}_{report_id}"
#      onclick="javascript:htmlIconClickOnCachedPortlet('{report_id}',...)">
_ROW_ANCHOR_RE = re.compile(
    r'<a\s[^>]*?id="_SearchSummaryPortlet_WAR_rlapp_portlet_INSTANCE_'
    r"([A-Za-z0-9]+)_(\d{6,12})"
    r'"[^>]*?onclick="javascript:htmlIconClickOnCachedPortlet\(\'[^\']*\'',
    re.IGNORECASE,
)

# Series: first <span aria-hidden="true"> inside the anchor row
_SERIES_IN_ROW_RE = re.compile(
    r'<span\s+aria-hidden="true">([^<]+?)</span>',
    re.IGNORECASE,
)

# Subtitle / title: <span class="white-text" aria-hidden="true">TITLE</span>
_SUBTITLE_RE = re.compile(
    r'<span\s+class="white-text"\s+aria-hidden="true">([^<]+?)</span>',
    re.IGNORECASE,
)

# Date: "14-Jun-2026 05:04:52 PM" anywhere in span.dark-grey-text after the row
_DATE_SPAN_RE = re.compile(
    r'<span\s+class="dark-grey-text"[^>]*>.*?'
    r"(\d{1,2}-(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)-\d{4}"
    r"\s+\d{1,2}:\d{2}:\d{2}(?:\s*[AP]M)?)",
    re.IGNORECASE | re.DOTALL,
)

# Author via navigateToResearchSearchProxy
_AUTHOR_RE = re.compile(r"navigateToResearchSearchProxy\('([^']+)'\)")

# pdfResourceUrl template:
#   <input type="hidden" id="_SearchSummaryPortlet_WAR_rlapp_portlet_INSTANCE_{INST}_pdfResourceUrl"
#          value="...pidvalue...">
_PDF_TEMPLATE_RE = re.compile(
    r'<input[^>]*?id="_SearchSummaryPortlet_WAR_rlapp_portlet_INSTANCE_'
    r"([A-Za-z0-9]+)_pdfResourceUrl\"[^>]*?value=\"([^\"]+)\"",
    re.IGNORECASE,
)

# Next-page control: <a ...><img alt="go to next page results">
_NEXT_PAGE_RE = re.compile(
    r'<img\s[^>]*?alt="go to next page results"',
    re.IGNORECASE,
)

# Separator between result rows — the thick grey divider that marks each new row
_ROW_SEP_RE = re.compile(
    r'<tr><td colspan="3"[^>]*class="graybackground_all_border"',
    re.IGNORECASE,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_bofa_date_str(text: str) -> date | None:
    """Parse 'D-Mon-YYYY HH:MM:SS AM' → date."""
    if not text:
        return None
    m = re.search(
        r"(\d{1,2})-(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)-(\d{4})",
        text,
        re.IGNORECASE,
    )
    if not m:
        return None
    day = int(m.group(1))
    month = _MONTH_TO_NUM.get(m.group(2)[:3].title())
    if not month:
        return None
    try:
        return date(int(m.group(3)), month, day)
    except ValueError:
        return None


def _extract_pdf_template(html: str) -> tuple[str, str] | None:
    """Return (summary_instance, pdf_template_url) from the page, or None."""
    m = _PDF_TEMPLATE_RE.search(html)
    if not m:
        return None
    return m.group(1), _decode_entities(m.group(2))


def _parse_total_count(html: str) -> int | None:
    """Return the total result count from '1-25 of 1,227' text, or None."""
    m = _COUNT_RE.search(html)
    if not m:
        return None
    try:
        return int(m.group(1).replace(",", ""))
    except ValueError:
        return None


def _has_next_page(html: str) -> bool:
    return bool(_NEXT_PAGE_RE.search(html))


def _parse_result_rows(html: str) -> list[dict]:
    """Parse all result rows from a single results page.

    Each row is delimited by the grey divider (<tr><td ...graybackground_all_border>).
    Within each row segment we extract: report_id, summary_instance, series,
    title, publish_date, analysts.
    """
    rows: list[dict] = []

    # Split on dividers so each chunk is a single-report block.
    # The first chunk is the header / portlet framing (before the first divider).
    segments = _ROW_SEP_RE.split(html)

    for seg in segments[1:]:  # skip the pre-divider header chunk
        # Extract report anchor
        anchor_m = _ROW_ANCHOR_RE.search(seg)
        if not anchor_m:
            continue
        summary_inst = anchor_m.group(1)
        report_id = anchor_m.group(2)

        # Series: first aria-hidden span in the segment (the one inside the anchor)
        series_m = _SERIES_IN_ROW_RE.search(seg)
        series = _decode_entities(series_m.group(1).strip()) if series_m else ""

        # Title: white-text span
        title_m = _SUBTITLE_RE.search(seg)
        title = _decode_entities(title_m.group(1).strip()) if title_m else ""

        # Date
        date_m = _DATE_SPAN_RE.search(seg)
        publish_date = _parse_bofa_date_str(date_m.group(1)) if date_m else None

        # Authors
        analysts: list[str] = []
        for am in _AUTHOR_RE.finditer(seg):
            name = unquote_plus(am.group(1)).strip()
            if name and name not in analysts:
                analysts.append(name)

        rows.append({
            "report_id": report_id,
            "summary_instance": summary_inst,
            "series": series,
            "title": title,
            "publish_date": publish_date,
            "analyst_primary": analysts[0] if analysts else "",
            "analysts": tuple(analysts),
        })

    return rows


# ── Per-discipline paginator ───────────────────────────────────────────────────

async def _query_discipline(
    ctx,
    *,
    discipline: str,
    hub: str,
    date_label: str,
    from_date: str,
    to_date: str,
    since: date | None,
    until: date | None,
    resolve_urls: bool,
    seen_ids: set[str],
) -> tuple[list, dict]:
    """Run one discipline query (including pagination) on the Advanced Search
    page. Returns (kept_refs, diag).

    ``date_label`` is the dropdown label, e.g. ``'Last 1 Week'``.
    ``from_date`` / ``to_date`` are filled only for ``'Custom Range'``
    (empty string otherwise).
    """
    from .crawler_bofa import (  # noqa: PLC0415
        ReportRef, _drop_reason, _HUB_ASSET_CLASS, _resolve_pdf_url,
    )

    asset_class_hint = _HUB_ASSET_CLASS.get(hub, "")
    kept_refs: list[ReportRef] = []
    n_parsed = 0
    n_dropped = 0
    n_no_url = 0
    drop_reasons: dict[str, int] = {}
    total_count: int | None = None
    pdf_template: str | None = None
    summary_inst: str | None = None
    page_count = 0

    page = await ctx.new_page()
    try:
        # ── Step 1: load the Advanced Search page ────────────────────────────
        await page.goto(_ADVSEARCH_URL, wait_until="domcontentloaded", timeout=45000)
        try:
            await page.wait_for_load_state("networkidle", timeout=20000)
        except Exception:  # noqa: BLE001
            pass
        await page.wait_for_timeout(2500)

        html = await page.content()

        # Derive the portlet INSTANCE prefix at runtime (may change between sessions)
        pfx_m = _PFX_RE.search(html)
        if not pfx_m:
            print(f"    [{discipline}] WARNING: could not find SearchCriteriaPortlet INSTANCE id - skipping")
            return [], {"parsed": 0, "dropped": 0, "kept": 0, "no_url": 0}
        pfx = pfx_m.group(1)
        # Liferay portlet element id format:
        #   _SearchCriteriaPortlet_WAR_rlalerts_portlet_INSTANCE_{pfx}_{fieldname}
        _CP = f"_SearchCriteriaPortlet_WAR_rlalerts_portlet_INSTANCE_{pfx}"
        discipline_dd_id = f"{_CP}_disciplineDropDown"
        date_dd_id = f"{_CP}_dateRangeDropDown"
        from_date_id = f"{_CP}_fromDate"
        to_date_id = f"{_CP}_toDate"

        # ── Step 2: select discipline ─────────────────────────────────────────
        try:
            await page.select_option(f"#{discipline_dd_id}", label=discipline)
        except Exception as exc:  # noqa: BLE001
            print(f"    [{discipline}] select_option(discipline) failed: {exc!s:.120}")
            return [], {"parsed": 0, "dropped": 0, "kept": 0, "no_url": 0}

        # CRITICAL: discipline selection triggers an async re-render; wait for it.
        try:
            await page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:  # noqa: BLE001
            pass
        await page.wait_for_timeout(1500)

        # ── Step 3: select date range ─────────────────────────────────────────
        try:
            await page.select_option(f"#{date_dd_id}", label=date_label)
        except Exception as exc:  # noqa: BLE001
            print(f"    [{discipline}] select_option(date) failed: {exc!s:.120}")
            return [], {"parsed": 0, "dropped": 0, "kept": 0, "no_url": 0}
        await page.wait_for_timeout(800)

        if date_label == "Custom Range":
            if from_date:
                await page.fill(f"#{from_date_id}", from_date)
            if to_date:
                await page.fill(f"#{to_date_id}", to_date)
            await page.wait_for_timeout(400)

        # ── Step 4: click Search ──────────────────────────────────────────────
        try:
            await page.click('input[value="Search"]', timeout=8000)
        except Exception:  # noqa: BLE001
            try:
                await page.click('button:has-text("Search")', timeout=8000)
            except Exception as exc2:  # noqa: BLE001
                print(f"    [{discipline}] Search click failed: {exc2!s:.120}")
                return [], {"parsed": 0, "dropped": 0, "kept": 0, "no_url": 0}

        # ── Step 5: wait for results (with retry on NavigationError) ──────────
        for _attempt in range(5):
            try:
                await page.wait_for_timeout(4500)
                await page.wait_for_load_state("networkidle", timeout=15000)
                break
            except Exception:  # noqa: BLE001
                await page.wait_for_timeout(1500)

        # ── Pagination loop ───────────────────────────────────────────────────
        while True:
            # Retry page.content() — Playwright raises when page is still navigating.
            html = None
            for _ci in range(6):
                try:
                    html = await page.content()
                    break
                except Exception:  # noqa: BLE001
                    await page.wait_for_timeout(1500)
            if html is None:
                print(f"    [{discipline}] page.content() failed after retries - stopping")
                break

            page_count += 1

            # Extract template once (same for all pages of this discipline)
            if pdf_template is None:
                tmpl_pair = _extract_pdf_template(html)
                if tmpl_pair:
                    summary_inst, pdf_template = tmpl_pair

            # Parse count from first page
            if total_count is None:
                total_count = _parse_total_count(html)
                if total_count is not None and total_count > _PAGE_CAP:
                    print(
                        f"    [{discipline}] WARNING: total={total_count} > {_PAGE_CAP} cap "
                        f"(date_label={date_label!r}, from={from_date}, to={to_date}). "
                        f"Consider sub-partitioning by day via Custom Range."
                    )

            rows = _parse_result_rows(html)
            n_parsed += len(rows)

            for row in rows:
                report_id = row["report_id"]
                series = row["series"]
                title = row["title"]
                pdate = row["publish_date"]

                # Date filter
                if pdate is not None:
                    if since is not None and pdate < since:
                        n_dropped += 1
                        drop_reasons["before-since"] = drop_reasons.get("before-since", 0) + 1
                        continue
                    if until is not None and pdate > until:
                        n_dropped += 1
                        drop_reasons["after-until"] = drop_reasons.get("after-until", 0) + 1
                        continue

                # Dedup across disciplines
                if report_id in seen_ids:
                    continue

                # Drop stack (same as hub crawler)
                reason = _drop_reason(hub=hub, series=series, title=title)
                if reason is not None:
                    n_dropped += 1
                    drop_reasons[reason.split(":", 1)[0]] = \
                        drop_reasons.get(reason.split(":", 1)[0], 0) + 1
                    continue

                credit_reason = _bofa_filter.credit_hub_drop_reason(
                    hub=hub, series=series, title=title,
                )
                if credit_reason is not None:
                    n_dropped += 1
                    drop_reasons[credit_reason.split(":", 1)[0]] = \
                        drop_reasons.get(credit_reason.split(":", 1)[0], 0) + 1
                    continue

                skip_reason = _bofa_filter.should_exclude(title=title)
                if skip_reason is not None:
                    n_dropped += 1
                    drop_reasons[skip_reason.split(":", 1)[0]] = \
                        drop_reasons.get(skip_reason.split(":", 1)[0], 0) + 1
                    continue

                # PDF URL resolution
                pdf_url = ""
                if resolve_urls and pdf_template:
                    pdf_url = await _resolve_pdf_url(
                        ctx, template=pdf_template, report_id=report_id,
                    ) or ""
                if resolve_urls and not pdf_url:
                    n_no_url += 1
                    continue

                seen_ids.add(report_id)

                ref = ReportRef(
                    url=pdf_url or f"bofa://{report_id}",
                    pdf_url=pdf_url or "",
                    uuid=report_id,
                    title=title or f"bofa/{report_id}",
                    publish_date=pdate or date.today(),
                    series=series,
                    subject=series,
                    hub=hub,
                    portlet_instance=row.get("summary_instance", ""),
                    analyst_primary=row["analyst_primary"],
                    analysts=row["analysts"],
                    asset_class_hint=asset_class_hint,
                )
                kept_refs.append(ref)

            # Next page?
            if not _has_next_page(html):
                break
            if page_count >= 10:
                # BofA caps at 250 results / 10 pages; stop here.
                break

            # Click the next-page control
            try:
                next_img = page.locator('img[alt="go to next page results"]').first
                parent_link = next_img.locator("xpath=..")
                await parent_link.click(timeout=8000)
            except Exception as exc:  # noqa: BLE001
                print(f"    [{discipline}] next-page click failed: {exc!s:.80}")
                break

            await page.wait_for_timeout(3500)
            try:
                await page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:  # noqa: BLE001
                pass

    finally:
        try:
            await page.close()
        except Exception:  # noqa: BLE001
            pass

    diag = {
        "parsed": n_parsed,
        "dropped": n_dropped,
        "kept": len(kept_refs),
        "no_url": n_no_url,
        "total_count": total_count,
        "pages": page_count,
        "drop_reasons": drop_reasons,
    }
    return kept_refs, diag


# ── Sub-partitioner (day-by-day for disciplines over the 250 cap) ─────────────

async def _query_discipline_sub_partitioned(
    ctx,
    *,
    discipline: str,
    hub: str,
    since: date,
    until: date,
    resolve_urls: bool,
    seen_ids: set[str],
) -> tuple[list, dict]:
    """Re-run a discipline day by day when the weekly total exceeds 250."""
    all_refs: list = []
    agg_diag: dict = {
        "parsed": 0, "dropped": 0, "kept": 0, "no_url": 0,
        "total_count": None, "pages": 0, "drop_reasons": {},
    }
    cur = since
    while cur <= until:
        date_str = cur.strftime("%m/%d/%Y")
        refs, diag = await _query_discipline(
            ctx,
            discipline=discipline,
            hub=hub,
            date_label="Custom Range",
            from_date=date_str,
            to_date=date_str,
            since=since,
            until=until,
            resolve_urls=resolve_urls,
            seen_ids=seen_ids,
        )
        all_refs.extend(refs)
        for k in ("parsed", "dropped", "kept", "no_url", "pages"):
            agg_diag[k] += diag.get(k, 0)
        for r, n in (diag.get("drop_reasons") or {}).items():
            agg_diag["drop_reasons"][r] = agg_diag["drop_reasons"].get(r, 0) + n
        cur += timedelta(days=1)
    return all_refs, agg_diag


# ── Public entry point ────────────────────────────────────────────────────────

async def discover_reports(
    profile_dir: Path,
    *,
    disciplines: Sequence[str] | None = None,
    since: date | None = None,
    until: date | None = None,
    resolve_urls: bool = True,
) -> list:
    """Run Advanced Search for each macro discipline and collect results.

    Parameters
    ----------
    profile_dir
        Path to the persistent Playwright Chrome profile (cookies/prefs).
        Programmatic login is performed on each run — same pattern as the
        hub crawler.
    disciplines
        Subset of ``_DISCIPLINE_TO_HUB`` keys to query. Defaults to all keys.
    since, until
        Inclusive date bounds. When both are provided and a discipline exceeds
        the 250-result cap, it is automatically sub-partitioned by day.
    resolve_urls
        When True, POST to the portlet PDF resource URL resolver for each
        kept report. Set False for a pure discovery probe.

    Returns
    -------
    list[ReportRef]
        Kept reports, deduplicated across disciplines, sorted newest-first.
    """
    import os  # noqa: PLC0415
    from playwright.async_api import async_playwright  # noqa: PLC0415

    disc_list: list[str] = (
        list(disciplines) if disciplines is not None else list(_DISCIPLINE_TO_HUB)
    )

    user = os.environ.get("IMDR_RESEARCH_BOFA_USERNAME", "")
    pwd = os.environ.get("IMDR_RESEARCH_BOFA_PASSWORD", "")
    if not (user and pwd):
        raise RuntimeError(
            "IMDR_RESEARCH_BOFA_USERNAME / _PASSWORD missing from env."
        )

    # Determine the date window label for the dropdown.
    # When since/until are provided, use 'Custom Range' day-by-day; otherwise
    # default to 'Last 1 Week' which matches the validated smoke window.
    use_custom = since is not None or until is not None
    date_label = "Custom Range" if use_custom else "Last 1 Week"

    print(
        f"  bofa firehose ({len(disc_list)} disciplines, "
        f"since={since}, until={until}, resolve_urls={resolve_urls})"
    )

    all_refs: list = []
    seen_ids: set[str] = set()
    total_diag: dict = {
        "parsed": 0, "dropped": 0, "kept": 0, "no_url": 0,
        "drop_reasons": {},
    }

    async with async_playwright() as pw:
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

            for discipline in disc_list:
                hub = _DISCIPLINE_TO_HUB[discipline]
                print(f"  [{discipline}] hub={hub}")

                if use_custom and since is not None and until is not None:
                    # Probe first with the full window; sub-partition if over cap.
                    from_str = since.strftime("%m/%d/%Y")
                    to_str = until.strftime("%m/%d/%Y")

                    # Use a throwaway set so probe_ids don't pollute seen_ids before
                    # the sub-partition pass runs (otherwise those IDs would be
                    # skipped by the day-by-day queries and silently dropped).
                    probe_seen: set[str] = set(seen_ids)
                    probe_refs, probe_diag = await _query_discipline(
                        ctx,
                        discipline=discipline,
                        hub=hub,
                        date_label="Custom Range",
                        from_date=from_str,
                        to_date=to_str,
                        since=since,
                        until=until,
                        resolve_urls=resolve_urls,
                        seen_ids=probe_seen,
                    )
                    total_count = probe_diag.get("total_count")

                    if total_count is not None and total_count > _PAGE_CAP:
                        print(
                            f"    [{discipline}] count={total_count} > {_PAGE_CAP}; "
                            f"sub-partitioning day-by-day..."
                        )
                        # Sub-partition day-by-day. The probe window may have
                        # fetched up to _PAGE_CAP reports; we add their ids to
                        # seen_ids first so the day-by-day pass skips them, then
                        # merge probe_refs into the final result so nothing is lost.
                        for r in probe_refs:
                            seen_ids.add(r.uuid)
                        sub_refs, sub_diag = await _query_discipline_sub_partitioned(
                            ctx,
                            discipline=discipline,
                            hub=hub,
                            since=since,
                            until=until,
                            resolve_urls=resolve_urls,
                            seen_ids=seen_ids,
                        )
                        # Union: probe covers the first cap window; sub covers the rest.
                        combined_refs = probe_refs + sub_refs
                        combined_diag = dict(sub_diag)
                        combined_diag["kept"] = len(combined_refs)
                        combined_diag["parsed"] = (
                            probe_diag.get("parsed", 0) + sub_diag.get("parsed", 0)
                        )
                        combined_diag["dropped"] = (
                            probe_diag.get("dropped", 0) + sub_diag.get("dropped", 0)
                        )
                        combined_diag["no_url"] = (
                            probe_diag.get("no_url", 0) + sub_diag.get("no_url", 0)
                        )
                        combined_diag["total_count"] = total_count
                        refs, diag = combined_refs, combined_diag
                    else:
                        # Under-cap: commit probe_ids into shared seen_ids.
                        seen_ids.update(probe_seen)
                        refs, diag = probe_refs, probe_diag

                else:
                    refs, diag = await _query_discipline(
                        ctx,
                        discipline=discipline,
                        hub=hub,
                        date_label=date_label,
                        from_date="",
                        to_date="",
                        since=since,
                        until=until,
                        resolve_urls=resolve_urls,
                        seen_ids=seen_ids,
                    )

                all_refs.extend(refs)
                print(
                    f"    parsed={diag['parsed']:>4}  dropped={diag['dropped']:>4}  "
                    f"kept={diag['kept']:>3}  no_url={diag.get('no_url', 0)}  "
                    f"total={diag.get('total_count', '?')}"
                )

                for k in ("parsed", "dropped", "kept", "no_url"):
                    total_diag[k] += diag.get(k, 0)
                for r, n in (diag.get("drop_reasons") or {}).items():
                    total_diag["drop_reasons"][r] = \
                        total_diag["drop_reasons"].get(r, 0) + n

        finally:
            await ctx.close()

    all_refs.sort(
        key=lambda r: (r.publish_date, r.uuid), reverse=True
    )

    print()
    print(
        f"  FIREHOSE TOTAL  parsed={total_diag['parsed']}  "
        f"dropped={total_diag['dropped']}  kept={len(all_refs)} (unique)  "
        f"no_url={total_diag['no_url']}"
    )
    if total_diag["drop_reasons"]:
        print(f"  drop reasons: {total_diag['drop_reasons']}")

    return all_refs
