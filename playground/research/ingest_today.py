"""Single orchestrator: discover + ingest today's research from every vendor.

Replaces the six ``ingest_today_{vendor}.py`` scripts with one entry point.
For each vendor in the run set:

    discover(profile_dir, since, until)  ->  list[ReportRef]
        |
        v
    ingest_one(...)  ->  (fetch | use cached bytes) -> parse -> idempotency
                        -> chunk -> upload to OneDrive/SharePoint
                        -> embed -> MSSQL write -> Qdrant upsert

Files land under the OneDrive sync of the IMDR SharePoint subtree:

    {LOCAL_IMDR_ROOT}/{YYYY}/{MM}/{DD}/{vendor}/{slug}_{uuid8}.pdf

(see ``ingest/paths.py`` and ``ingest/upload.py``).

Defaults
--------
* Date window: ``today and yesterday`` (UTC). The 2-day window catches
  early-morning APAC and late EU output without much noise.
* Vendors:     all eleven (anz, barclays, bnp, db, goldman, hsbc, jpm, ms, nomura, socgen, westpac).
* Embed:       OFF — set ``--embed`` to enable Voyage/Gemini calls.
* Concurrency: 1 PDF at a time *per vendor*. Vendors run sequentially
  by default — each spins up its own Playwright Chrome against the
  vendor's persistent profile, and Chrome locks the profile dir to a
  single process. Different profiles can run in parallel; same profile
  cannot.

Usage
-----
    # all vendors, today + yesterday, no embeds
    python playground/research/ingest_today.py

    # one vendor, smoke test
    python playground/research/ingest_today.py --vendors goldman --limit 1

    # specific date window with embeds
    python playground/research/ingest_today.py --since 2026-05-10 --until 2026-05-14 --embed

    # comma-separated vendor list
    python playground/research/ingest_today.py --vendors goldman,nomura --limit 1
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Awaitable, Callable, Protocol

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from ingest._console import force_utf8_stdout  # noqa: E402

# Force stdout/stderr to UTF-8 before any print() so a non-cp1252 char in
# a report title or exception message (e.g. "→" U+2192) can't kill the
# asyncio loop mid-vendor when output is piped to Tee-Object on Windows.
force_utf8_stdout()

from ingest import embed as _embed_mod  # noqa: E402
from ingest._vendor_log import VendorLogger  # noqa: E402
from ingest.classifiers import get_classifier, has_classifier  # noqa: E402
from ingest.models import ReportMeta  # noqa: E402
from ingest.paths import build_sharepoint_path  # noqa: E402
from ingest.pipeline import IngestResult, ingest_one  # noqa: E402
from ingest.qdrant_writer import QdrantWriter  # noqa: E402
from ingest.relevance import apply_relevance_filter  # noqa: E402


# ---------------------------------------------------------------------
# Vendor registry
# ---------------------------------------------------------------------

class _DiscoverFn(Protocol):
    async def __call__(self, profile_dir: Path, *, since: date, until: date, **kw): ...


@dataclass(slots=True, frozen=True)
class VendorSpec:
    code: str
    discover: _DiscoverFn
    # Some crawlers expose a publication_type (e.g. "Malaysia Insight",
    # "FICC Research"); use it as a coarse asset_class hint.
    use_pubtype_as_asset_class: bool = False
    # Identifier for the auth/SSO realm a vendor's login federates to.
    # Vendors that share a realm (e.g. Barclays + BofA both go via RV
    # PingFederate) MUST not re-login concurrently — too many bursts
    # from one source IP look like a credential-stuffing attempt to the
    # IdP. The orchestrator gates by-realm in Phase 6 (currently no-op
    # at N=1). `None` = independent vendor IdP, no gating needed.
    # See docs/admin/development/parallel_vendor_ingest.md Phase 5.
    auth_realm: str | None = None


def _load_vendor_registry() -> dict[str, VendorSpec]:
    """Late-import each crawler so a broken vendor doesn't break the others.

    We import inside the function so ``--vendors goldman`` keeps working
    even if (say) the HSBC crawler module fails to import for any reason.
    """
    from ingest.crawler_anz import discover_reports as anz_discover  # noqa: PLC0415
    from ingest.crawler_barclays import discover_reports as barclays_discover  # noqa: PLC0415
    from ingest.crawler_bnp import discover_reports as bnp_discover  # noqa: PLC0415
    from ingest.crawler_citi import discover_reports as citi_discover  # noqa: PLC0415
    # BofA is held out of the orchestrator pending Phase 8 audit
    # (2026-06-04 user decision — see docs/admin/research/scrapers/bofa.md
    # "PROD-HOLD"). Crawler / fetcher / classifier all built and tested
    # standalone; re-enable here + re-add the VendorSpec below + re-add
    # the pipeline.py URL-host dispatch when promoting.
    # from ingest.crawler_bofa import discover_reports as bofa_discover  # noqa: PLC0415
    from ingest.crawler_db import discover_reports as db_discover  # noqa: PLC0415
    from ingest.crawler_goldman import discover_reports as goldman_discover  # noqa: PLC0415
    from ingest.crawler_hsbc import discover_reports as hsbc_discover  # noqa: PLC0415
    from ingest.crawler_jpm import discover_reports as jpm_discover  # noqa: PLC0415
    from ingest.crawler_ms import discover_reports as ms_discover  # noqa: PLC0415
    from ingest.crawler_nomura import discover_reports as nomura_discover  # noqa: PLC0415
    from ingest.crawler_socgen import discover_reports as socgen_discover  # noqa: PLC0415
    from ingest.crawler_stanc import discover_reports as stanc_discover  # noqa: PLC0415
    from ingest.crawler_ubs import discover_reports as ubs_discover  # noqa: PLC0415
    from ingest.crawler_westpac import discover_reports as westpac_discover  # noqa: PLC0415

    return {
        "anz": VendorSpec(
            code="anz", discover=anz_discover,
            use_pubtype_as_asset_class=True,
        ),
        "barclays": VendorSpec(
            code="barclays", discover=barclays_discover,
            use_pubtype_as_asset_class=True,
            # Barclays login goes via PingFederate federating through
            # RV's IdP. BofA (when un-held from PROD-HOLD) is the same
            # realm. Phase 6 will refuse concurrent logins within a
            # realm to avoid IdP anomaly flags.
            auth_realm="rv-pingfed",
        ),
        # BNP has a classifier, so use_pubtype_as_asset_class is moot —
        # the classifier path populates asset_class/tags/context.
        "bnp": VendorSpec(code="bnp", discover=bnp_discover),
        # Citi Velocity Research has a classifier (classifiers/citi.py) —
        # Tier-0 productFocus + subjects[] maps to canonical asset_class.
        # The orchestrator's classifier path populates asset_class/tags/
        # context; use_pubtype_as_asset_class is moot here.
        "citi": VendorSpec(code="citi", discover=citi_discover),
        # BofA Securities Mercury — HELD OUT of orchestrator pending
        # Phase 8 audit (2026-06-04). Crawler / fetcher / classifier
        # all built and tested standalone (2 reports already in DB
        # from a manual smoke run). Re-enable by uncommenting:
        #   * the `from ingest.crawler_bofa import …` line above
        #   * the line below (`"bofa": VendorSpec(...)`)
        #   * pipeline._fetch_pdf_dispatch (currently restored to the
        #     plain fetch.fetch_pdf)
        #   * classifiers/__init__._VENDOR_CODES + dispatcher branch
        # See docs/admin/research/scrapers/bofa.md "PROD-HOLD" section.
        # "bofa": VendorSpec(code="bofa", discover=bofa_discover),
        # DB has a classifier (classifiers/db.py) — topics[].template
        # gives a clean asset-class mapping; use_pubtype_as_asset_class
        # is moot (the classifier path populates asset_class/tags/context).
        "db": VendorSpec(code="db", discover=db_discover),
        "goldman": VendorSpec(code="goldman", discover=goldman_discover),
        "hsbc": VendorSpec(
            code="hsbc", discover=hsbc_discover,
            use_pubtype_as_asset_class=True,
        ),
        # JPM has a classifier (classifiers/jpm.py) — the orchestrator's
        # classifier path populates asset_class/tags/context, so
        # use_pubtype_as_asset_class is moot. ReportRef has no
        # publication_type field anyway.
        "jpm": VendorSpec(code="jpm", discover=jpm_discover),
        "ms": VendorSpec(
            code="ms", discover=ms_discover,
            use_pubtype_as_asset_class=True,
        ),
        "nomura": VendorSpec(
            code="nomura", discover=nomura_discover,
            use_pubtype_as_asset_class=True,
        ),
        # SG has a classifier (classifiers/socgen.py) — Tier-0
        # category_group maps to canonical asset_class, with Tier-1
        # product-name fallback. use_pubtype_as_asset_class is moot.
        "socgen": VendorSpec(code="socgen", discover=socgen_discover),
        # STANC has a classifier (classifiers/stanc.py) — Tier-0
        # assetClassCodes[0] maps to canonical asset_class, with rich
        # country/region resolution + author/theme tags from payload.
        # use_pubtype_as_asset_class is moot. ReportRef has no
        # publication_type field; classifier uses publication_type_code
        # / publication_type_name as vendor_pubtype tag only.
        "stanc": VendorSpec(code="stanc", discover=stanc_discover),
        # UBS Neo has a classifier (classifiers/ubs.py) — Tier-0
        # businessAreaCode maps to canonical asset_class. The
        # orchestrator's classifier path populates asset_class/tags/
        # context; use_pubtype_as_asset_class is moot here. Wired in
        # 2026-06-06 post-Phase-3 7-day smoke (~25/day kept after
        # relevance filter; see docs/admin/research/scrapers/ubs.md).
        "ubs": VendorSpec(code="ubs", discover=ubs_discover),
        # Westpac has a classifier (classifiers/westpac.py), so the
        # orchestrator's classifier path populates asset_class/tags/
        # context — use_pubtype_as_asset_class is moot here.
        "westpac": VendorSpec(code="westpac", discover=westpac_discover),
    }


# ---------------------------------------------------------------------
# DB engine
# ---------------------------------------------------------------------

def _research_engine(settings):
    from sqlalchemy import create_engine  # noqa: PLC0415

    url = (
        f"mssql+pyodbc://@{settings.mssql_host}:{settings.mssql_port}"
        f"/{settings.mssql_database}"
        f"?driver=ODBC+Driver+18+for+SQL+Server"
        f"&Trusted_Connection=yes"
        f"&Encrypt=yes"
        f"&TrustServerCertificate=yes"
        f"&LoginTimeout=60"
    )
    # Pool pre-sized for the Phase 6 parallel-vendor wiring (default N=1
    # today; flag flips to N=3 max). See
    # docs/admin/development/parallel_vendor_ingest.md.
    #   Per ingest_one a single connection is in use at a time — the
    #   idempotency-check, the autocommit dim_tag / dim_model upserts,
    #   and the report engine.begin() each acquire-then-release before
    #   the next phase. Concurrency is across vendors x parallel PDFs.
    #   At N=3 vendors x parallel=2 = 6 in-flight; pool_size=12 +
    #   overflow=12 = 24 cap. Headroom covers retry storms.
    return create_engine(
        url, pool_size=12, max_overflow=12, pool_pre_ping=True,
        pool_timeout=60, echo=False, fast_executemany=True,
        connect_args={"timeout": 60},
    )


# ---------------------------------------------------------------------
# Per-report ingest
# ---------------------------------------------------------------------

# Attribute names we look at when extracting a name from an Analyst-like
# object (JPM uses ``display_name``, DB uses ``name``; future crawlers
# might use ``authorName``/``full_name`` per the dim_report.authors mirror
# contract). First non-empty wins.
_AUTHOR_NAME_ATTRS: tuple[str, ...] = (
    "display_name", "name", "authorName", "full_name",
)


def _normalize_authors(raw) -> str:
    """Flatten whatever the crawler emits into a comma-joined string.

    Handles the three observed shapes:

    * ``str`` (most crawlers) — returned as-is (stripped).
    * ``tuple/list[str]`` (Goldman) — comma-joined.
    * ``tuple/list[<Analyst dataclass>]`` (JPM, DB) — extract one of
      ``display_name`` / ``name`` / ``authorName`` / ``full_name``
      per element, drop empties, comma-join.

    Anything else (None, unrecognised object) collapses to ``""``.
    The classifiers already emit ``Tag('author', name)`` per analyst,
    so an empty scalar is recoverable from tags; this function only
    feeds the cheap WHERE/LIKE mirror on ``dim_report.authors``.
    """
    if raw is None:
        return ""
    if isinstance(raw, str):
        return raw.strip()
    if isinstance(raw, (list, tuple)):
        names: list[str] = []
        for item in raw:
            if isinstance(item, str):
                s = item.strip()
                if s:
                    names.append(s)
                continue
            for attr in _AUTHOR_NAME_ATTRS:
                v = getattr(item, attr, None)
                if isinstance(v, str) and v.strip():
                    names.append(v.strip())
                    break
        return ", ".join(names)
    return ""


@dataclass(slots=True)
class Outcome:
    vendor: str
    ref: object  # ReportRef-like (duck-typed across crawlers)
    result: IngestResult | None = None
    error: BaseException | None = None


async def _ingest_one_ref(
    *,
    vendor: VendorSpec,
    ref,
    pdf_bytes: bytes | None,
    sem: asyncio.Semaphore,
    api_keys: dict[str, str],
    engine,
    profile_dir: Path,
    do_embed: bool,
    embed_model: str,
    qdrant_writer: QdrantWriter | None,
    log: VendorLogger | None = None,
) -> Outcome:
    async with sem:
        # Per-report heartbeat — prints immediately after the semaphore
        # is acquired so the operator sees which report is in flight
        # when a downstream phase hangs. Routed through the vendor
        # logger (when supplied) so the per-vendor log file captures
        # the start time — crucial forensics under Phase 6 concurrency
        # where a stall in upload/db/qdrant otherwise leaves no entry
        # in {vendor}.log at all. Falls back to bare print() for
        # callers that don't have a logger (older test harnesses).
        _uid = (getattr(ref, "uuid", "") or "")[:10]
        _title = (getattr(ref, "title", "") or "")[:60]
        _heartbeat = f"    [start] {_uid}  {_title}"
        if log is not None:
            log.line(_heartbeat)
        else:
            print(f"    [start] {vendor.code}/{_uid}  {_title}", flush=True)

        # Per-vendor classifier produces:
        #   - asset_class (controlled vocab, single primary domain)
        #   - country_code (2-char dim_country.country_code, resolved at write)
        #   - tags (list[Tag] for map_report_tag / dim_tag)
        #   - context (LLM-grade rendered text — dim_report.context)
        # Fallback for any vendor without a classifier yet: empty result
        # + use publication_type as a raw asset_class hint (legacy path).
        if has_classifier(vendor.code):
            result_clf = get_classifier(vendor.code)(ref)
            asset_class = result_clf.asset_class
            country_code = result_clf.country_code
            tags = tuple((t.category, t.value) for t in result_clf.tags)
            context = result_clf.context
        else:
            asset_class = (
                (getattr(ref, "publication_type", "") or "")
                if vendor.use_pubtype_as_asset_class else ""
            )
            country_code = None
            tags = ()
            context = ""

        # Pull the analyst-list string from whichever attribute the
        # vendor's ReportRef exposes. Crawlers ship three shapes:
        #   * ``str``                           — ANZ, MS, BNP, Nomura, HSBC,
        #                                          Barclays, Westpac
        #   * ``tuple[str, ...]``               — Goldman
        #   * ``tuple[<Analyst dataclass>, ...]`` — JPM (display_name),
        #                                          DB (name)
        # Normalise to a comma-joined string before binding into the
        # DB INSERT — without this, ``str(tuple)`` lands a Python repr
        # like ``"(JPMAnalyst(...), ...)"`` in dim_report.authors. The
        # classifiers already emit Tag('author', name) per analyst, so
        # an empty scalar is recoverable from tags; a corrupted scalar
        # silently rots downstream LIKE/WHERE queries.
        authors = _normalize_authors(
            getattr(ref, "analysts", None)
            if getattr(ref, "analysts", None) is not None
            else getattr(ref, "authors", None)
        )

        meta = ReportMeta(
            vendor_code=vendor.code,
            vendor_id=0,
            title=ref.title or f"{vendor.code}/{ref.uuid}",
            publish_date=ref.publish_date,
            pdf_url=ref.pdf_url,
            sharepoint_path=None,
            asset_class=asset_class,
            region="",
            country_code=country_code,
            authors=authors,
            context=context,
            tags=tags,
        )
        sharepoint_relative = build_sharepoint_path(
            vendor_code=vendor.code,
            publish_date=ref.publish_date,
            uuid=ref.uuid,
            title=ref.title,
        )
        try:
            result = await ingest_one(
                url=ref.pdf_url,
                meta=meta,
                sharepoint_relative_path=sharepoint_relative,
                profile_dir=profile_dir,
                api_keys=api_keys,
                engine=engine,
                embed=do_embed,
                embedding_model_name=embed_model,
                qdrant_writer=qdrant_writer,
                store_pdf_text=False,
                pdf_bytes=pdf_bytes,
            )
            return Outcome(vendor=vendor.code, ref=ref, result=result)
        except BaseException as exc:  # noqa: BLE001
            return Outcome(vendor=vendor.code, ref=ref, error=exc)


# ---------------------------------------------------------------------
# Per-vendor run
# ---------------------------------------------------------------------

@dataclass(slots=True)
class VendorRunSummary:
    vendor: str
    discovered: int
    inserted: int
    duplicate: int
    failed: int
    elapsed_s: float
    error: str | None = None


def _print_section_header(text: str) -> None:
    print()
    print("=" * 72)
    print(f"  {text}")
    print("=" * 72)


_VENDOR_PARALLEL_HARD_CAP = 3


def _print_run_header(
    *, vendors, since, until, parallel, vendor_parallel,
    limit, do_embed, embed_model,
):
    _print_section_header("research ingest_today — all vendors")
    print(f"  vendors      : {', '.join(v.code for v in vendors)}")
    print(f"  date window  : {since} .. {until}")
    print(
        f"  parallel     : {parallel} PDFs per vendor, "
        f"{vendor_parallel} vendor(s) concurrently"
    )
    # Show realm groupings if any vendor has one — operator can see
    # which vendors will be serialised within their realm even at N>=2.
    realms = sorted({v.auth_realm for v in vendors if v.auth_realm})
    if realms:
        for realm in realms:
            members = sorted(v.code for v in vendors if v.auth_realm == realm)
            print(f"    realm {realm!r}: {', '.join(members)} (serialised)")
    print(f"  limit        : {limit if limit else 'no cap'} per vendor")
    print(f"  embed        : {'ON' if do_embed else 'OFF'}")
    if do_embed:
        print(f"  embed model  : {embed_model}")
    print()


async def _run_vendor(
    vendor: VendorSpec,
    *,
    since: date,
    until: date,
    limit: int,
    parallel: int,
    api_keys: dict[str, str],
    engine,
    do_embed: bool,
    embed_model: str,
    qdrant_writer: QdrantWriter | None,
    drop_single_name_equity: bool,
) -> VendorRunSummary:
    started = time.perf_counter()
    profile_dir = HERE / "profiles" / vendor.code
    log = VendorLogger(vendor.code)
    log.section(f"vendor: {vendor.code}")
    log.line(f"  log file     : {log.path}")
    log.line(f"  profile      : {profile_dir}")
    profile_dir.mkdir(parents=True, exist_ok=True)

    try:
        refs = await vendor.discover(
            profile_dir, since=since, until=until,
        )
    except BaseException as exc:  # noqa: BLE001
        elapsed = time.perf_counter() - started
        log.line(
            f"  [ERR] _run_vendor: DISCOVER_THREW; "
            f"{type(exc).__name__}: {exc!s:.200}"
        )
        log.close()
        return VendorRunSummary(
            vendor=vendor.code, discovered=0, inserted=0,
            duplicate=0, failed=0, elapsed_s=elapsed,
            error=f"DISCOVER_THREW: {type(exc).__name__}: {exc}",
        )

    n_discovered = len(refs)

    # Gate single-name equity at the same point as the per-vendor scripts
    # (see ingest_today_barclays.py:180-184). Settings.research_drop_single_name_equity
    # is True by default — flip it via IMDR_RESEARCH_DROP_SINGLE_NAME_EQUITY=false
    # for one-off backfills that legitimately want single-name coverage.
    n_filter_dropped = 0
    if drop_single_name_equity and refs:
        refs, dropped = apply_relevance_filter(
            vendor_code=vendor.code, refs=refs, verbose=True,
        )
        n_filter_dropped = len(dropped)
        if dropped:
            log.line(f"  relevance filter: removed {n_filter_dropped} single-name equity ref(s)")

    n_after_filter = len(refs)
    if limit and refs:
        refs = refs[:limit]
    n_after_limit = len(refs)

    # Per-stage funnel — one line that answers "where did the refs go?"
    # without making the operator scan a hundred [DROP]/[SKIP] lines.
    log.line(
        f"  funnel: discovered={n_discovered}  "
        f"after_relevance_filter={n_after_filter}  "
        f"after_limit={n_after_limit}  "
        f"(filter_removed={n_filter_dropped}, limit_cap={limit or 'none'})"
    )

    if not refs:
        elapsed = time.perf_counter() - started
        # NEVER silent — name which step zeroed the list so the operator
        # can tell discover-failure from filter-wipeout from genuinely-empty.
        if n_discovered == 0:
            log.line(
                f"  [WARN] _run_vendor: DISCOVER_ZERO; "
                f"discover() returned 0 refs in window {since}..{until}. "
                f"Either no reports published OR auth/SPA state failed — "
                f"check the crawler's [ERR] line above (if none, run "
                f"playground/research/probe_{vendor.code}_status.py)."
            )
            error_msg = "DISCOVER_ZERO"
        elif n_filter_dropped == n_discovered:
            log.line(
                f"  [OK]   _run_vendor: FILTER_DROPPED_ALL; "
                f"all {n_discovered} discovered ref(s) classified as "
                f"single-name equity. Nothing to ingest — this is expected."
            )
            error_msg = None  # not an error
        else:
            log.line(
                f"  [WARN] _run_vendor: LIMIT_ZERO; "
                f"refs list emptied at limit step (discovered={n_discovered}, "
                f"after_filter={n_after_filter}, after_limit={n_after_limit})."
            )
            error_msg = "LIMIT_ZERO"
        log.close()
        return VendorRunSummary(
            vendor=vendor.code, discovered=n_discovered, inserted=0,
            duplicate=0, failed=0, elapsed_s=elapsed,
            error=error_msg,
        )

    log.line(f"  discovered   : {len(refs)} report(s)")
    for r in refs:
        title = (r.title or "(no title)")[:55]
        ptype = getattr(r, "publication_type", "") or ""
        ptag = f"[{ptype[:18]}]" if ptype else ""
        uid = (r.uuid or "")[:10]
        log.line(f"    {r.publish_date}  {uid:<10}  {ptag:<22}  {title}")
    log.line("")

    sem = asyncio.Semaphore(max(1, parallel))

    # Some vendors need an authenticated SPA session to fetch PDFs; the
    # pipeline's standard fetch_pdf (via a fresh ctx per fetch) won't
    # work because their auth cookies are session-scoped. Those vendors
    # fetch bytes in-session after the filter and hand them to
    # ingest_one. All other vendors use the URL-only path.
    #
    # Barclays: programmatic login + per-PDF SPA fetch.
    # SG (socgen): doc.sgmarkets.com OIDC handshake cookies don't
    #   survive ctx.close(), so the handshake must happen in the same
    #   ctx as the PDF fetches.
    if vendor.code == "barclays":
        from ingest.crawler_barclays import fetch_pdfs as _barclays_fetch_pdfs  # noqa: PLC0415
        outcomes: list[Outcome] = []
        async for ref, pdf_bytes in _barclays_fetch_pdfs(profile_dir, refs):
            if pdf_bytes is None:
                outcomes.append(Outcome(
                    vendor=vendor.code, ref=ref,
                    error=RuntimeError("PDF fetch returned no bytes"),
                ))
                continue
            outcomes.append(await _ingest_one_ref(
                vendor=vendor, ref=ref, pdf_bytes=pdf_bytes,
                sem=sem, api_keys=api_keys, engine=engine,
                profile_dir=profile_dir, do_embed=do_embed,
                embed_model=embed_model, qdrant_writer=qdrant_writer,
                log=log,
            ))
    elif vendor.code == "socgen":
        from ingest.crawler_socgen import fetch_pdfs as _socgen_fetch_pdfs  # noqa: PLC0415
        outcomes: list[Outcome] = []
        async for ref, pdf_bytes in _socgen_fetch_pdfs(profile_dir, refs):
            if pdf_bytes is None:
                outcomes.append(Outcome(
                    vendor=vendor.code, ref=ref,
                    error=RuntimeError("PDF fetch returned no bytes"),
                ))
                continue
            outcomes.append(await _ingest_one_ref(
                vendor=vendor, ref=ref, pdf_bytes=pdf_bytes,
                sem=sem, api_keys=api_keys, engine=engine,
                profile_dir=profile_dir, do_embed=do_embed,
                embed_model=embed_model, qdrant_writer=qdrant_writer,
                log=log,
            ))
    else:
        outcomes = await asyncio.gather(*(
            _ingest_one_ref(
                vendor=vendor,
                ref=r,
                pdf_bytes=None,
                sem=sem,
                api_keys=api_keys,
                engine=engine,
                profile_dir=profile_dir,
                do_embed=do_embed,
                embed_model=embed_model,
                qdrant_writer=qdrant_writer,
                log=log,
            )
            for r in refs
        ))

    log.line("  results")
    log.line("  " + "-" * 68)
    inserted = duplicate = failed = 0
    for o in outcomes:
        ref = o.ref
        uid = (ref.uuid or "")[:10]
        title = (ref.title or "")[:40]
        if o.error is not None:
            failed += 1
            log.line(f"    [FAIL]   {uid}  {title:<40}  "
                     f"{type(o.error).__name__}: {o.error}")
            continue
        r = o.result
        if r.was_inserted:
            inserted += 1
            log.line(f"    [INS]    id={r.report_id:<5} {uid}  "
                     f"chunks={r.n_chunks:>3} embeds={r.n_embeddings:>3}  "
                     f"total={r.timings_s.get('total', 0):.1f}s  {title}")
        else:
            duplicate += 1
            log.line(f"    [DUP]    id={r.report_id:<5} {uid}  "
                     f"already in DB  {title}")
    log.line("  " + "-" * 68)
    elapsed = time.perf_counter() - started
    log.line(f"  inserted: {inserted}   duplicate: {duplicate}   "
             f"failed: {failed}   elapsed: {elapsed:.1f}s")
    log.close()

    return VendorRunSummary(
        vendor=vendor.code, discovered=len(refs),
        inserted=inserted, duplicate=duplicate, failed=failed,
        elapsed_s=elapsed,
    )


# ---------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Discover + ingest today's research from every vendor.",
    )
    p.add_argument(
        "--vendors", default="",
        help=("Comma-separated vendor codes (anz,barclays,bnp,db,goldman,"
              "hsbc,jpm,ms,nomura,socgen,westpac). Default: all eleven."),
    )
    p.add_argument(
        "--since", default=os.environ.get("IMDR_RESEARCH_SINCE", ""),
        help="Earliest publish date (YYYY-MM-DD). Default: yesterday (UTC).",
    )
    p.add_argument(
        "--until", default=os.environ.get("IMDR_RESEARCH_UNTIL", ""),
        help="Latest publish date (YYYY-MM-DD). Default: today (UTC).",
    )
    p.add_argument(
        "--limit", type=int,
        default=int(os.environ.get("IMDR_RESEARCH_LIMIT", "0") or 0),
        help="Cap reports per vendor (0 = no cap). Default 0.",
    )
    p.add_argument(
        "--parallel", type=int,
        default=int(os.environ.get("IMDR_RESEARCH_PARALLEL", "1") or 1),
        help="Concurrent PDFs *per vendor* (Chrome profile locks force 1).",
    )
    p.add_argument(
        "--vendor-parallel", type=int,
        default=int(os.environ.get("IMDR_RESEARCH_VENDOR_PARALLEL", "1") or 1),
        help=(
            "Concurrent vendors. Hard-cap 3 (RAM budget: headed-Chrome "
            "vendors ~1.5 GB each). Vendors sharing an auth_realm "
            "(rv-pingfed) are serialised within the realm regardless. "
            "Default 1 (serial, today's behaviour)."
        ),
    )
    p.add_argument(
        "--embed", action="store_true",
        default=os.environ.get("IMDR_RESEARCH_EMBED", "").strip().lower()
        in ("1", "true", "yes", "on"),
        help="Run Voyage/Gemini embedding + Qdrant upsert. Default OFF.",
    )
    p.add_argument(
        "--embed-model",
        default=os.environ.get("IMDR_RESEARCH_EMBED_MODEL",
                               _embed_mod.DEFAULT_MODEL_NAME).strip(),
        help=f"Embedding model. Default {_embed_mod.DEFAULT_MODEL_NAME}.",
    )
    return p.parse_args()


def _resolve_vendors(arg: str, registry: dict[str, VendorSpec]) -> list[VendorSpec]:
    if not arg.strip():
        return list(registry.values())
    selected: list[VendorSpec] = []
    seen: set[str] = set()
    for raw in arg.split(","):
        code = raw.strip().lower()
        if not code or code in seen:
            continue
        if code not in registry:
            raise SystemExit(
                f"unknown vendor: {code!r}. "
                f"Known: {', '.join(sorted(registry))}"
            )
        seen.add(code)
        selected.append(registry[code])
    if not selected:
        raise SystemExit("--vendors resolved to empty list")
    return selected


def _resolve_window(since_arg: str, until_arg: str) -> tuple[date, date]:
    # SGT-anchored: vendor pubDate is NY/UTC; UTC "today" lags SGT for ops.
    today = datetime.now(timezone(timedelta(hours=8))).date()
    since = date.fromisoformat(since_arg.strip()) if since_arg.strip() \
        else (today - timedelta(days=3))
    until = date.fromisoformat(until_arg.strip()) if until_arg.strip() \
        else today
    if since > until:
        raise SystemExit(f"--since ({since}) is after --until ({until})")
    return since, until


async def _amain(args: argparse.Namespace) -> int:
    from imdr.config.settings import get_settings  # noqa: PLC0415

    settings = get_settings()
    api_keys = {"voyage": settings.voyage_key, "google": settings.gemini_key}

    registry = _load_vendor_registry()
    vendors = _resolve_vendors(args.vendors, registry)
    since, until = _resolve_window(args.since, args.until)

    vendor_parallel = max(1, min(args.vendor_parallel, _VENDOR_PARALLEL_HARD_CAP))
    if args.vendor_parallel > _VENDOR_PARALLEL_HARD_CAP:
        print(
            f"[WARN] --vendor-parallel={args.vendor_parallel} exceeds hard "
            f"cap {_VENDOR_PARALLEL_HARD_CAP}; clamping. See "
            f"docs/admin/development/parallel_vendor_ingest.md for the RAM "
            f"budget that drives the cap."
        )

    _print_run_header(
        vendors=vendors, since=since, until=until,
        parallel=args.parallel, vendor_parallel=vendor_parallel,
        limit=args.limit, do_embed=args.embed,
        embed_model=args.embed_model,
    )

    engine = _research_engine(settings)
    qdrant_writer = QdrantWriter.from_env() if args.embed else None
    if qdrant_writer is not None:
        print(f"  qdrant       : {qdrant_writer.mode}")

    # Eagerly initialise the cross-vendor embed semaphore in THIS task's
    # context before gather spawns per-vendor tasks. Without this, each
    # child task creates its own semaphore on first call (because gather
    # gives each task a copy of the parent context, and ContextVar.set
    # in a child is task-local). See embed.prime_embed_semaphore.
    if args.embed:
        _embed_mod.prime_embed_semaphore()

    overall_started = time.perf_counter()
    summaries: list[VendorRunSummary] = []

    # Concurrency model:
    #   * `host_sem` caps total in-flight vendors at vendor_parallel.
    #   * `realm_sems[realm]` caps vendors-per-realm at 1 — sharing
    #     `auth_realm` means sharing an IdP/credential surface (e.g.
    #     Barclays + BofA both federate through RV PingFed); concurrent
    #     re-logins look like credential stuffing.
    host_sem = asyncio.Semaphore(vendor_parallel)
    realms: dict[str, asyncio.Semaphore] = {}
    for v in vendors:
        if v.auth_realm and v.auth_realm not in realms:
            realms[v.auth_realm] = asyncio.Semaphore(1)

    async def _run_one(vendor: VendorSpec) -> VendorRunSummary:
        # Acquire host slot FIRST, then realm gate. Holding the realm
        # while waiting for a host slot would unnecessarily serialise
        # other same-realm vendors during the wait — the IdP collision
        # risk is at LOGIN time (inside _run_vendor), not at slot-wait.
        realm_sem = realms.get(vendor.auth_realm) if vendor.auth_realm else None
        try:
            if realm_sem is not None:
                async with host_sem, realm_sem:
                    return await _run_vendor(
                        vendor,
                        since=since, until=until,
                        limit=args.limit, parallel=args.parallel,
                        api_keys=api_keys, engine=engine,
                        do_embed=args.embed,
                        embed_model=args.embed_model,
                        qdrant_writer=qdrant_writer,
                        drop_single_name_equity=settings.research_drop_single_name_equity,
                    )
            async with host_sem:
                return await _run_vendor(
                    vendor,
                    since=since, until=until,
                    limit=args.limit, parallel=args.parallel,
                    api_keys=api_keys, engine=engine,
                    do_embed=args.embed,
                    embed_model=args.embed_model,
                    qdrant_writer=qdrant_writer,
                    drop_single_name_equity=settings.research_drop_single_name_equity,
                )
        except (KeyboardInterrupt, asyncio.CancelledError):
            # Bubble up so main() prints the abort line and gather
            # can propagate cancellation to siblings. NEVER absorb a
            # cancel into a synthetic VendorRunSummary — that would
            # mask shutdown from the orchestrator.
            raise
        except BaseException as exc:  # noqa: BLE001
            # Defensive net for anything _run_vendor missed. Bare
            # stdout because the vendor's logger may be in a broken
            # state if it crashed mid-init.
            print(
                f"[{vendor.code}] [ERR] uncaught in _run_vendor: "
                f"{type(exc).__name__}: {exc!s:.200}",
                flush=True,
            )
            return VendorRunSummary(
                vendor=vendor.code, discovered=0, inserted=0,
                duplicate=0, failed=0, elapsed_s=0.0,
                error=f"UNCAUGHT: {type(exc).__name__}: {exc}",
            )

    try:
        # `return_exceptions=True` collapsed into per-vendor try/except
        # inside `_run_one`; we always get a VendorRunSummary out of
        # gather, never an exception (except KeyboardInterrupt which
        # propagates).
        gathered = await asyncio.gather(
            *(_run_one(v) for v in vendors),
            return_exceptions=False,
        )
        summaries.extend(gathered)
    finally:
        if qdrant_writer is not None:
            qdrant_writer.close()

    overall_elapsed = time.perf_counter() - overall_started

    _print_section_header("aggregate summary")
    print(f"  {'vendor':<10} {'disc':>5} {'ins':>5} {'dup':>5} "
          f"{'fail':>5} {'elapsed':>9}  status")
    print("  " + "-" * 68)
    total_disc = total_ins = total_dup = total_fail = 0
    any_failed_vendor = False
    for s in summaries:
        total_disc += s.discovered
        total_ins += s.inserted
        total_dup += s.duplicate
        total_fail += s.failed
        status = "ok" if s.error is None else f"DISCOVER FAILED: {s.error}"
        if s.error is not None:
            any_failed_vendor = True
        print(f"  {s.vendor:<10} {s.discovered:>5} {s.inserted:>5} "
              f"{s.duplicate:>5} {s.failed:>5} {s.elapsed_s:>8.1f}s  {status}")
    print("  " + "-" * 68)
    print(f"  {'TOTAL':<10} {total_disc:>5} {total_ins:>5} "
          f"{total_dup:>5} {total_fail:>5} {overall_elapsed:>8.1f}s")
    print()

    # Exit non-zero if any vendor's discovery blew up entirely, or if any
    # per-PDF ingest failed. Duplicates are not failures.
    if any_failed_vendor or total_fail > 0:
        return 1
    return 0


_ORCHESTRATOR_LOCK_PATH = HERE / ".ingest_today.lock"


def _acquire_orchestrator_lock():
    """Fail fast if another ingest_today run is in progress on this host.

    Two concurrent orchestrators would share the same Chrome profile
    dirs (one per vendor under ``playground/research/profiles/``);
    Chrome's profile lock is unreliable on Windows + SMB, which can
    silently corrupt the LevelDB inside the profile and bork the next
    re-login. Better to crash loudly here.

    Returns the held :class:`filelock.FileLock`. Caller must keep it
    in scope for the lifetime of the run.
    """
    from filelock import FileLock, Timeout  # noqa: PLC0415

    lock = FileLock(str(_ORCHESTRATOR_LOCK_PATH), timeout=0)
    try:
        lock.acquire()
    except Timeout:
        # filelock uses msvcrt.locking on Windows / fcntl on POSIX —
        # both release the OS-level lock on process death, so a crashed
        # prior run does NOT keep us out (the .lock file may still be
        # on disk but is no longer held; the next acquire succeeds).
        # If this error fires, it means a live process owns the lock.
        raise SystemExit(
            f"another ingest_today run is already in progress on this "
            f"host (lock held: {_ORCHESTRATOR_LOCK_PATH}). Wait for it "
            f"to finish. If you are certain no orchestrator is running, "
            f"check for a stuck Python process before removing the lock."
        )
    return lock


def main() -> None:
    args = _parse_args()
    lock = _acquire_orchestrator_lock()
    rc = 1
    try:
        rc = asyncio.run(_amain(args))
    except KeyboardInterrupt:
        # User Ctrl+C — print a clear abort line so the operator knows
        # the run was interrupted (not a crash). Each crawler's own
        # `async with launch_persistent_context(...)` cleanup runs
        # during the asyncio cancel propagation, so Chrome profile
        # SingletonLock files get cleared normally.
        print("\n[ABORT] KeyboardInterrupt — orchestrator stopped by user", flush=True)
        rc = 130  # 128 + SIGINT (POSIX convention)
    finally:
        lock.release()
    sys.exit(rc)


if __name__ == "__main__":
    main()
