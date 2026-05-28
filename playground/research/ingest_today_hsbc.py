"""Discover and ingest today's HSBC Global Investment Research reports.

Walks the HSBC Reach All Reports listing
(``/ibcom/in/reach/servlet/Reach``), parses the server-rendered HTML
table, dedupes by ``shortId``, filters by publish_date, and ingests
each PDF end-to-end. Per the discovery notes in
``docs/admin/research/scrapers/hsbc.md``, the listing href IS the PDF
URL — no detail page, no viewer.

Defaults
--------
* Date window: ``today and yesterday`` (UTC).
* Embed: OFF (set ``IMDR_RESEARCH_EMBED=true`` to enable).
* Concurrency: 1 (Chrome locks the persistent profile dir).

Usage
-----
    C:/Users/adoshi/.conda/envs/imdr/python.exe playground/research/ingest_today_hsbc.py

Optional env
------------
    IMDR_RESEARCH_EMBED=true              # enable embedding
    IMDR_RESEARCH_EMBED_MODEL=gemini-embedding-2
    IMDR_RESEARCH_SINCE=2026-05-05
    IMDR_RESEARCH_UNTIL=2026-05-08
    IMDR_RESEARCH_LIMIT=5                 # cap on reports
    IMDR_RESEARCH_PARALLEL=1              # leave at 1
"""
from __future__ import annotations

import asyncio
import os
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from ingest._console import force_utf8_stdout  # noqa: E402

# Force stdout/stderr to UTF-8 before any print() so a non-cp1252 char in
# a report title can't crash the run when output is piped to Tee-Object.
force_utf8_stdout()

from ingest.crawler_hsbc import ReportRef, discover_reports  # noqa: E402
from ingest.models import ReportMeta  # noqa: E402
from ingest.paths import build_sharepoint_path  # noqa: E402
from ingest.pipeline import IngestResult, ingest_one  # noqa: E402
from ingest.qdrant_writer import QdrantWriter  # noqa: E402

VENDOR_CODE = "hsbc"
PROFILE_DIR = HERE / "profiles" / VENDOR_CODE


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
    return create_engine(
        url,
        pool_size=4,
        max_overflow=4,
        pool_pre_ping=True,
        pool_timeout=60,
        echo=False,
        fast_executemany=True,
        connect_args={"timeout": 60},
    )


def _read_date_env(name: str) -> date | None:
    raw = os.environ.get(name)
    if not raw:
        return None
    return date.fromisoformat(raw.strip())


def _read_int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw.strip())


def _bool_env(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


@dataclass
class Outcome:
    ref: ReportRef
    result: IngestResult | None = None
    error: BaseException | None = None


async def _ingest_one_ref(
    ref: ReportRef,
    *,
    sem: asyncio.Semaphore,
    api_keys: dict[str, str],
    engine,
    do_embed: bool,
    embed_model: str,
    qdrant_writer: QdrantWriter | None,
) -> Outcome:
    async with sem:
        meta = ReportMeta(
            vendor_code=VENDOR_CODE,
            vendor_id=0,
            title=ref.title or f"{VENDOR_CODE}/{ref.uuid}",
            publish_date=ref.publish_date,
            pdf_url=ref.pdf_url,
            sharepoint_path=None,
            asset_class=ref.publication_type or "",
            region="",
        )
        sharepoint_relative = build_sharepoint_path(
            vendor_code=VENDOR_CODE,
            publish_date=ref.publish_date,
            uuid=ref.uuid,
            title=ref.title,
        )
        try:
            result = await ingest_one(
                url=ref.pdf_url,
                meta=meta,
                sharepoint_relative_path=sharepoint_relative,
                profile_dir=PROFILE_DIR,
                api_keys=api_keys,
                engine=engine,
                embed=do_embed,
                embedding_model_name=embed_model,
                qdrant_writer=qdrant_writer,
                store_pdf_text=False,
            )
            return Outcome(ref=ref, result=result)
        except BaseException as exc:  # noqa: BLE001
            return Outcome(ref=ref, error=exc)


async def _amain() -> None:
    from imdr.config.settings import get_settings  # noqa: PLC0415

    settings = get_settings()
    api_keys = {
        "voyage": settings.voyage_key,
        "google": settings.gemini_key,
    }

    # SGT-anchored: vendor pubDate is NY/UTC; UTC "today" lags SGT for ops.
    today = datetime.now(timezone(timedelta(hours=8))).date()
    since = _read_date_env("IMDR_RESEARCH_SINCE") or (today - timedelta(days=3))
    until = _read_date_env("IMDR_RESEARCH_UNTIL") or today
    limit = _read_int_env("IMDR_RESEARCH_LIMIT", 0)
    parallel = max(1, _read_int_env("IMDR_RESEARCH_PARALLEL", 1))
    do_embed = _bool_env("IMDR_RESEARCH_EMBED", False)
    from ingest import embed as _embed_mod  # noqa: PLC0415
    embed_model = os.environ.get(
        "IMDR_RESEARCH_EMBED_MODEL", _embed_mod.DEFAULT_MODEL_NAME
    ).strip()

    print("=" * 60)
    print(f"  vendor       : {VENDOR_CODE}")
    print(f"  date window  : {since} .. {until}")
    print(f"  parallel     : {parallel}")
    print(f"  limit        : {limit if limit else 'no cap'}")
    print(f"  embed        : {'ON' if do_embed else 'OFF'}")
    if do_embed:
        print(f"  embed model  : {embed_model}")
    print(f"  profile      : {PROFILE_DIR}")
    print("=" * 60)
    print()

    if not PROFILE_DIR.exists():
        raise SystemExit(
            f"Profile not found: {PROFILE_DIR}\nRun explore_hsbc.py first."
        )

    refs = await discover_reports(
        PROFILE_DIR, since=since, until=until,
    )
    if settings.research_drop_single_name_equity:
        from ingest.relevance import apply_relevance_filter  # noqa: PLC0415
        refs, _ = apply_relevance_filter(
            vendor_code=VENDOR_CODE, refs=refs, verbose=True,
        )
    if limit:
        refs = refs[:limit]

    if not refs:
        print("\nno reports to ingest in this window.")
        return

    print()
    print(f"  ingesting {len(refs)} report(s)...")
    for r in refs:
        title = r.title[:55] if r.title else "(no title)"
        ptype = f"[{r.publication_type[:18]}]" if r.publication_type else ""
        print(f"    {r.publish_date}  {r.uuid[:10]}  {ptype:<22}  {title}")
    print()

    engine = _research_engine(settings)
    sem = asyncio.Semaphore(parallel)
    qdrant_writer = QdrantWriter.from_env() if do_embed else None
    if qdrant_writer:
        print(f"  qdrant       : {qdrant_writer.mode}")
        print()

    try:
        outcomes = await asyncio.gather(
            *(
                _ingest_one_ref(
                    r,
                    sem=sem,
                    api_keys=api_keys,
                    engine=engine,
                    do_embed=do_embed,
                    embed_model=embed_model,
                    qdrant_writer=qdrant_writer,
                )
                for r in refs
            )
        )
    finally:
        if qdrant_writer is not None:
            qdrant_writer.close()

    print()
    print("=" * 60)
    print("  results")
    print("-" * 60)
    inserted = 0
    skipped = 0
    failed = 0
    for o in outcomes:
        if o.error is not None:
            failed += 1
            print(
                f"  [FAIL]   {o.ref.uuid[:10]}  {o.ref.title[:40]:<40}  "
                f"{type(o.error).__name__}: {o.error}"
            )
            continue
        r = o.result
        if r.was_inserted:
            inserted += 1
            print(
                f"  [INS]    id={r.report_id:<5} {o.ref.uuid[:10]}  "
                f"chunks={r.n_chunks:>3} embeds={r.n_embeddings:>3}  "
                f"total={r.timings_s.get('total', 0):.1f}s  "
                f"{o.ref.title[:40]}"
            )
        else:
            skipped += 1
            print(
                f"  [DUP]    id={r.report_id:<5} {o.ref.uuid[:10]}  "
                f"already in DB  {o.ref.title[:40]}"
            )
    print("-" * 60)
    print(f"  inserted: {inserted}   duplicate: {skipped}   failed: {failed}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(_amain())
