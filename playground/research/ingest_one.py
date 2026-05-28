"""Spine runner — ingest ONE Goldman Sachs PDF end-to-end.

Hardcodes the test target so we can iterate the spine quickly. Once the
flow works we generalise (pull list of (url, meta) from a listing crawler).

Prerequisites:
    1. Migrations 032 + 033 applied (research.dim_report has content_hash,
       research.fact_chunk + fact_chunk_embedding exist, voyage-3-large
       seeded into dim_embedding_model).
    2. dbo.dim_vendor has a row with vendor_code='goldman'.
    3. The persistent profile playground/research/profiles/goldman/ has
       been logged into Marquee at least once (run explore_goldman.py).
    4. .env contains IMDR_VOYAGE_KEY.

Usage:
    C:/Users/adoshi/.conda/envs/imdr/python.exe playground/research/ingest_one.py
"""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import date
from pathlib import Path

# Allow `from ingest import ...` when run as a script.
HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from ingest._console import force_utf8_stdout  # noqa: E402

# Force stdout/stderr to UTF-8 before any print() so a non-cp1252 char in
# a report title can't crash the run when output is piped to Tee-Object.
force_utf8_stdout()

from ingest.models import ReportMeta  # noqa: E402
from ingest.paths import build_sharepoint_path  # noqa: E402
from ingest.pipeline import ingest_one  # noqa: E402

# ── Test target — Goldman "Global Markets Daily" 2026-05-06 ───────────
TARGET_UUID = "721599cb-abbc-498a-b841-33bb3f653801"
TARGET_URL = (
    f"https://marquee.gs.com/content/research/en/reports/"
    f"2026/05/06/{TARGET_UUID}.pdf"
)
TARGET_META = ReportMeta(
    vendor_code="goldman",
    vendor_id=0,                               # resolved at write time
    title="Global Markets Daily: Taking Stock and Optimising",
    publish_date=date(2026, 5, 6),
    pdf_url=TARGET_URL,
    sharepoint_path=None,                      # populated by pipeline post-upload
    asset_class="macro",
    region="global",
)
# Path under IMDR/ on TradeKnowledgeCore/ResearchData1 — date-first layout
TARGET_SHAREPOINT_RELATIVE = build_sharepoint_path(
    vendor_code=TARGET_META.vendor_code,
    publish_date=TARGET_META.publish_date,
    uuid=TARGET_UUID,
    title=TARGET_META.title,
)
PROFILE_DIR = HERE / "profiles" / "goldman"
LOCAL_PDF_DIR = HERE / "pdfs"


def _research_engine(settings):
    """Build a research-only SQLAlchemy engine using ODBC Driver 18.

    The project default is the legacy "SQL Server" driver (per .env), chosen
    for DATETIMEOFFSET handling in other pipelines. That driver chokes on
    NVARCHAR(MAX) and BINARY parameter binding above ~8 KB — fatal for
    pdf_text and vector. Driver 18 handles both natively. We isolate the
    upgrade to this single research pipeline so other pipelines are
    untouched.
    """
    from sqlalchemy import create_engine  # noqa: PLC0415

    url = (
        f"mssql+pyodbc://@{settings.mssql_host}:{settings.mssql_port}"
        f"/{settings.mssql_database}"
        f"?driver=ODBC+Driver+18+for+SQL+Server"
        f"&Trusted_Connection=yes"
        f"&Encrypt=yes"
        f"&TrustServerCertificate=yes"
        # Driver 18's TLS handshake to AWS RDS occasionally exceeds the
        # default 15s login timeout — give it ~60s of headroom.
        f"&LoginTimeout=60"
    )
    return create_engine(
        url,
        pool_size=2,
        max_overflow=2,
        pool_pre_ping=True,
        pool_timeout=60,
        echo=False,
        fast_executemany=True,
        connect_args={"timeout": 60},
    )


async def _amain() -> None:
    from imdr.config.settings import get_settings  # noqa: PLC0415

    settings = get_settings()
    api_keys = {
        "voyage": settings.voyage_key,
        "google": settings.gemini_key,
    }

    engine = _research_engine(settings)

    if not PROFILE_DIR.exists():
        raise SystemExit(
            f"Profile not found: {PROFILE_DIR}\n"
            "Run explore_goldman.py first and complete the interactive login."
        )

    LOCAL_PDF_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Target:    {TARGET_URL}")
    print(f"Profile:   {PROFILE_DIR}")
    print(f"DB:        {settings.mssql_database}@{settings.mssql_host} (ODBC Driver 18)")
    print(f"SharePoint: IMDR/{TARGET_SHAREPOINT_RELATIVE}")
    print()

    # IMDR_RESEARCH_EMBED       false (default) | true
    # IMDR_RESEARCH_EMBED_MODEL voyage-3-large (default) | voyage-finance-2 |
    #                            gemini-embedding-001
    embed_flag = os.environ.get("IMDR_RESEARCH_EMBED", "false").strip().lower()
    do_embed = embed_flag in ("1", "true", "yes", "on")
    from ingest import embed as _embed_mod  # noqa: PLC0415
    embed_model = os.environ.get(
        "IMDR_RESEARCH_EMBED_MODEL", _embed_mod.DEFAULT_MODEL_NAME
    ).strip()
    print(f"Embed:     {'ON' if do_embed else 'OFF (set IMDR_RESEARCH_EMBED=true to enable)'}")
    if do_embed:
        print(f"Model:     {embed_model}")
    print()

    result = await ingest_one(
        url=TARGET_URL,
        meta=TARGET_META,
        sharepoint_relative_path=TARGET_SHAREPOINT_RELATIVE,
        profile_dir=PROFILE_DIR,
        api_keys=api_keys,
        engine=engine,
        embed=do_embed,
        embedding_model_name=embed_model,
    )

    print("-" * 50)
    print(f"  report_id      : {result.report_id}")
    print(f"  was_inserted   : {result.was_inserted}")
    print(f"  pages          : {result.page_count}")
    print(f"  chunks         : {result.n_chunks}")
    print(f"  embeddings     : {result.n_embeddings}")
    print(f"  sharepoint     : {result.sharepoint_path}")
    print()
    print("  Phase timings (s):")
    for phase, sec in result.timings_s.items():
        print(f"    {phase:<28} {sec:7.3f}")
    print("-" * 50)


if __name__ == "__main__":
    asyncio.run(_amain())
