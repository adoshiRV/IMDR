"""Ingest a LOCAL PDF into the research corpus with ``source='manual'``.

For documents that never came from a vendor portal or the email channel —
e.g. an internally-compiled synthesis, a PDF shared over Teams/Outlook, or
a one-off hand-collected report. Everything downstream of acquisition is
identical to the normal pipeline: parse -> chunk -> upload to the IMDR
SharePoint subtree -> embed -> MSSQL write -> Qdrant upsert.

The vendor's stable document UUID (which the portal crawlers use to make
``pdf_path`` collision-free + idempotent) doesn't exist for a manual drop,
so we derive a deterministic id from the SHA-256 of the PDF bytes. Re-running
on the same file therefore hits the ``(vendor_id, pdf_path)`` dedup gate and
is a no-op — safe to retry.

Usage
-----
    C:/Users/adoshi/.conda/envs/imdr/python.exe playground/research/ingest_manual.py \
        --pdf "C:/Users/adoshi/Downloads/HSBC_Asia_Rates_Flows_x_Swaps_May-Jul2026.pdf" \
        --vendor hsbc \
        --title "Asia Rates: Weekly Flow Colour x Swap Moves" \
        --date 2026-07-05 \
        --asset-class rates --region asia \
        --authors "M. Stokie (HSBC sales & trading)" \
        --source-type desk_commentary

Embedding (+ Qdrant upsert) is ON by default here — a manual doc is only
worth ingesting if it becomes searchable. Pass ``--no-embed`` to skip.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from ingest._console import force_utf8_stdout  # noqa: E402

force_utf8_stdout()

from ingest import embed as _embed_mod  # noqa: E402
from ingest.engine import research_engine  # noqa: E402
from ingest.models import ReportMeta  # noqa: E402
from ingest.paths import build_sharepoint_path  # noqa: E402
from ingest.pipeline import ingest_one  # noqa: E402
from ingest.qdrant_writer import QdrantWriter  # noqa: E402


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Ingest a local PDF with source='manual'.")
    p.add_argument("--pdf", required=True, help="Absolute path to the local PDF.")
    p.add_argument("--vendor", required=True, help="dim_vendor.vendor_code (e.g. hsbc).")
    p.add_argument("--title", required=True, help="Report title (dim_report.title).")
    p.add_argument("--date", required=True, help="Publish date YYYY-MM-DD.")
    p.add_argument("--asset-class", default="", help="Canonical asset class (e.g. rates).")
    p.add_argument("--region", default="", help="Canonical region (e.g. asia).")
    p.add_argument("--authors", default="", help="Comma-joined author display names.")
    p.add_argument("--source", default="manual", help="dim_report.source. Default 'manual'.")
    p.add_argument(
        "--source-type", default="research",
        help="dim_report.source_type (research | desk_commentary). Default 'research'.",
    )
    p.add_argument(
        "--pdf-url", default="",
        help="Provenance URL for the log / ReportMeta.pdf_url. Optional.",
    )
    p.add_argument(
        "--no-embed", action="store_true",
        help="Skip embedding + Qdrant upsert (default: embed ON).",
    )
    p.add_argument(
        "--embed-model", default=_embed_mod.DEFAULT_MODEL_NAME,
        help=f"Embedding model. Default {_embed_mod.DEFAULT_MODEL_NAME}.",
    )
    return p.parse_args()


async def _amain(args: argparse.Namespace) -> int:
    from imdr.config.settings import get_settings  # noqa: PLC0415

    pdf_path = Path(args.pdf)
    if not pdf_path.is_file():
        raise SystemExit(f"PDF not found: {pdf_path}")
    pdf_bytes = pdf_path.read_bytes()

    # Deterministic pseudo-UUID from the bytes → stable pdf_path slug so a
    # re-run dedups on (vendor_id, pdf_path) instead of duplicating.
    synthetic_uuid = hashlib.sha256(pdf_bytes).hexdigest()

    publish_date = date.fromisoformat(args.date)
    do_embed = not args.no_embed

    settings = get_settings()
    api_keys = {"voyage": settings.voyage_key, "google": settings.gemini_key}
    engine = research_engine(settings)
    qdrant_writer = QdrantWriter.from_env() if do_embed else None

    sharepoint_relative = build_sharepoint_path(
        vendor_code=args.vendor,
        publish_date=publish_date,
        uuid=synthetic_uuid,
        title=args.title,
    )
    meta = ReportMeta(
        vendor_code=args.vendor,
        vendor_id=0,                       # resolved at write time
        title=args.title,
        publish_date=publish_date,
        pdf_url=args.pdf_url or f"manual://{pdf_path.name}",
        sharepoint_path=None,              # populated by pipeline post-upload
        asset_class=args.asset_class,
        region=args.region,
        authors=args.authors,
    )

    print(f"PDF        : {pdf_path} ({len(pdf_bytes)//1024} KB)")
    print(f"Vendor     : {args.vendor}")
    print(f"Title      : {args.title}")
    print(f"Date       : {publish_date}")
    print(f"Source     : {args.source} / {args.source_type}")
    print(f"SharePoint : IMDR/{sharepoint_relative}")
    print(f"Embed      : {'ON (' + args.embed_model + ')' if do_embed else 'OFF'}")
    if qdrant_writer is not None:
        print(f"Qdrant     : {qdrant_writer.mode}")
    print()

    try:
        result = await ingest_one(
            url=meta.pdf_url,
            meta=meta,
            sharepoint_relative_path=sharepoint_relative,
            profile_dir=HERE / "profiles" / args.vendor,   # unused (bytes supplied)
            api_keys=api_keys,
            engine=engine,
            embed=do_embed,
            embedding_model_name=args.embed_model,
            qdrant_writer=qdrant_writer,
            store_pdf_text=False,
            pdf_bytes=pdf_bytes,
            source=args.source,
            source_type=args.source_type,
        )
    finally:
        if qdrant_writer is not None:
            qdrant_writer.close()

    print("-" * 50)
    print(f"  report_id      : {result.report_id}")
    print(f"  was_inserted   : {result.was_inserted}")
    print(f"  pages          : {result.page_count}")
    print(f"  chunks         : {result.n_chunks}")
    print(f"  embeddings     : {result.n_embeddings}")
    print(f"  qdrant_points  : {result.n_qdrant_points}")
    print(f"  qdrant_coll    : {result.qdrant_collection}")
    print(f"  sharepoint     : {result.sharepoint_path}")
    print("-" * 50)
    if not result.was_inserted:
        print("  NOTE: dedup hit — this PDF was already in the corpus.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_amain(_parse_args())))
