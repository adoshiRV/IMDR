"""Backfill Qdrant points for reports that were ingested without ``--embed``.

When a report goes through ``ingest_one()`` with ``embed=False``,
chunks are written to ``research.fact_chunk`` but no embeddings are
generated and no Qdrant points are written. The corpus is retrievable
via SQL but invisible to vector search.

This script reconciles that drift WITHOUT re-fetching / re-parsing the
PDFs. For every report whose chunks are present in DB but absent from
Qdrant, it:

  1. Pulls the persisted ``chunk_text`` rows (the canonical text).
  2. Re-runs ``embed_chunks()`` against the configured model.
  3. Builds ``ChunkPoint`` payloads with vendor_code + publish_date +
     title + page bounds from DB.
  4. Calls ``qdrant_writer.upsert_chunks()`` so ``point.id ==
     fact_chunk.id`` (the same FK link the live pipeline uses).

No DB rows are written; ``fact_chunk_embedding`` is deprecated (see
``ingest/db.py::_bulk_insert_embeddings``) so we don't touch it.

Run with ``--dry-run`` (default) to see the report list, then
``--commit`` to actually embed + upsert.

Usage::

    python playground/research/backfill_qdrant.py                  # dry-run, all vendors
    python playground/research/backfill_qdrant.py --vendor anz     # one vendor
    python playground/research/backfill_qdrant.py --commit         # destructive (writes to Qdrant)
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import time
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from ingest._console import force_utf8_stdout  # noqa: E402

# Force stdout/stderr to UTF-8 before any print() so a non-cp1252 char in
# a report title can't crash the run when output is piped to Tee-Object.
force_utf8_stdout()

from ingest import embed as embed_mod  # noqa: E402
from ingest.models import Chunk  # noqa: E402
from ingest.qdrant_writer import ChunkPoint, QdrantWriter  # noqa: E402

QDRANT_COLLECTION = "research_gemini_embedding_2_3072d"
ALL_VENDORS = (
    "anz", "barclays", "bnp", "db", "goldman", "hsbc", "jpm", "ms",
    "nomura", "westpac",
)
PREVIEW_CHARS = 240


# ---------------------------------------------------------------------
# Find reports needing backfill
# ---------------------------------------------------------------------

def _qdrant_ids_for_vendor(vendor_code: str, url: str) -> set[int]:
    from qdrant_client import QdrantClient  # noqa: PLC0415
    from qdrant_client.http import models as qm  # noqa: PLC0415

    client = QdrantClient(url=url, timeout=60)
    try:
        existing = {c.name for c in client.get_collections().collections}
        if QDRANT_COLLECTION not in existing:
            return set()
        ids: set[int] = set()
        flt = qm.Filter(must=[qm.FieldCondition(
            key="vendor_code", match=qm.MatchValue(value=vendor_code),
        )])
        next_offset = None
        while True:
            points, next_offset = client.scroll(
                collection_name=QDRANT_COLLECTION,
                scroll_filter=flt, limit=1000,
                with_payload=False, with_vectors=False,
                offset=next_offset,
            )
            ids.update(int(p.id) for p in points)
            if next_offset is None:
                break
        return ids
    finally:
        client.close()


def _db_chunks_by_report(engine, vendor_code: str) -> dict[int, list[int]]:
    """report_id -> [chunk_id, ...]"""
    from sqlalchemy import text  # noqa: PLC0415

    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT c.report_id, c.id
            FROM research.fact_chunk c
            JOIN research.dim_report r ON r.id = c.report_id
            JOIN dbo.dim_vendor v ON v.id = r.vendor_id
            WHERE v.vendor_code = :v
        """), {"v": vendor_code}).all()
    out: dict[int, list[int]] = defaultdict(list)
    for report_id, chunk_id in rows:
        out[report_id].append(int(chunk_id))
    return dict(out)


def _fully_missing_reports(engine, vendor_code: str, qdrant_url: str) -> list[int]:
    db = _db_chunks_by_report(engine, vendor_code)
    if not db:
        return []
    qd = _qdrant_ids_for_vendor(vendor_code, qdrant_url)
    return sorted(
        report_id for report_id, chunk_ids in db.items()
        if not any(cid in qd for cid in chunk_ids)
    )


# ---------------------------------------------------------------------
# Per-report backfill
# ---------------------------------------------------------------------

def _load_report_for_backfill(engine, report_id: int):
    """Return (vendor_code, publish_date, title, [chunk_rows])."""
    from sqlalchemy import text  # noqa: PLC0415

    with engine.connect() as conn:
        meta = conn.execute(text("""
            SELECT v.vendor_code, r.publish_date, r.title
            FROM research.dim_report r
            JOIN dbo.dim_vendor v ON v.id = r.vendor_id
            WHERE r.id = :i
        """), {"i": report_id}).first()
        if meta is None:
            return None
        rows = conn.execute(text("""
            SELECT id, chunk_index, page_start, page_end, section_title,
                   chunk_text, chunk_text_hash, token_count, chunker_version
            FROM research.fact_chunk
            WHERE report_id = :i
            ORDER BY chunk_index
        """), {"i": report_id}).all()
    return meta, rows


async def _backfill_report(
    engine, report_id: int, *,
    api_keys: dict[str, str],
    model_name: str,
    qdrant_writer: QdrantWriter,
) -> tuple[int, int]:
    """Embed + upsert one report. Returns (chunks_processed, points_upserted)."""
    loaded = _load_report_for_backfill(engine, report_id)
    if loaded is None:
        print(f"  [WARN] report id={report_id} not found")
        return 0, 0
    meta, rows = loaded
    vendor_code, publish_date, title = meta
    if not rows:
        print(f"  [WARN] report id={report_id} has no chunks")
        return 0, 0

    # Rebuild Chunk dataclasses for embed_chunks(). chunk_index is
    # what binds the result back to chunk_id below.
    chunk_id_by_index: dict[int, int] = {}
    chunks: list[Chunk] = []
    chunk_payload_extras: dict[int, dict] = {}
    for r in rows:
        cid, idx, p_start, p_end, sec, ctext, ctext_hash, tcount, cv = r
        chunk_id_by_index[int(idx)] = int(cid)
        chunks.append(Chunk(
            chunk_index=int(idx),
            text=ctext or "",
            text_hash=bytes(ctext_hash) if ctext_hash is not None else b"",
            token_count=int(tcount or 0),
            page_start=int(p_start) if p_start is not None else None,
            page_end=int(p_end) if p_end is not None else None,
            section_title=sec,
            chunker_version=cv or "",
        ))
        chunk_payload_extras[int(idx)] = {
            "page_start": int(p_start) if p_start is not None else None,
            "page_end": int(p_end) if p_end is not None else None,
            "text": ctext or "",
        }

    embeddings = await embed_mod.embed_chunks(
        chunks, model_name=model_name, api_keys=api_keys,
    )

    spec = embed_mod.get_spec(model_name)
    import struct  # noqa: PLC0415
    # model_id for the payload is a stable integer per (provider, model, dims).
    # We don't need to look it up in dim_embedding_model (it would re-insert
    # if absent, but the field is purely audit and the live pipeline derives
    # it the same way). Default to 0 if unknown — Qdrant just stores it as int.
    model_id = _resolve_model_id(engine, spec.provider, spec.model_name, spec.dimensions)

    points: list[ChunkPoint] = []
    for emb in embeddings:
        cid = chunk_id_by_index.get(emb.chunk_index)
        extras = chunk_payload_extras.get(emb.chunk_index)
        if cid is None or extras is None:
            continue
        vec = list(struct.unpack(f"<{spec.dimensions}f", emb.vector))
        points.append(ChunkPoint(
            chunk_id=cid,
            vector=vec,
            report_id=report_id,
            vendor_code=vendor_code,
            publish_date=publish_date,
            page_start=extras["page_start"],
            page_end=extras["page_end"],
            title=title or "",
            text_preview=(extras["text"] or "")[:PREVIEW_CHARS],
            model_id=model_id,
        ))

    if not points:
        return len(chunks), 0
    qdrant_writer.upsert_chunks(
        model_name=spec.model_name,
        dimensions=spec.dimensions,
        points=points,
    )
    return len(chunks), len(points)


def _resolve_model_id(engine, provider: str, model_name: str, dimensions: int) -> int:
    """Read-only lookup against research.dim_embedding_model.

    Returns 0 if the model isn't in the registry yet. The audit
    payload tolerates a sentinel; the live pipeline seeds the row on
    first use via ``ingest/db.py::_ensure_model_id``, so as soon as a
    real ingest runs after this backfill, the value will exist.
    """
    from sqlalchemy import text  # noqa: PLC0415
    with engine.connect() as conn:
        row = conn.execute(text("""
            SELECT id FROM research.dim_embedding_model
            WHERE provider = :p AND model_name = :m AND dimensions = :d
        """), {"p": provider, "m": model_name, "d": dimensions}).first()
    return int(row[0]) if row else 0


# ---------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------

async def _amain(args: argparse.Namespace) -> int:
    from sqlalchemy import create_engine  # noqa: PLC0415
    from imdr.config.settings import get_settings  # noqa: PLC0415

    s = get_settings()
    api_keys = {"voyage": s.voyage_key, "google": s.gemini_key}
    qdrant_url = (s.qdrant_url or "").strip()
    if not qdrant_url:
        print("  [ERR] settings.qdrant_url unset; set IMDR_QDRANT_URL in .env")
        return 2

    engine = create_engine(
        f"mssql+pyodbc://@{s.mssql_host}:{s.mssql_port}/{s.mssql_database}"
        f"?driver=ODBC+Driver+18+for+SQL+Server"
        f"&Trusted_Connection=yes&Encrypt=yes&TrustServerCertificate=yes",
        pool_pre_ping=True,
    )

    vendors = ALL_VENDORS if args.vendor == "all" else (args.vendor,)

    print("=" * 100)
    print("  backfill_qdrant")
    print(f"  mode    : {'COMMIT' if args.commit else 'DRY-RUN'}")
    print(f"  vendors : {', '.join(vendors)}")
    print(f"  model   : {args.model}")
    print(f"  qdrant  : {qdrant_url}")
    print("=" * 100)

    targets: dict[str, list[int]] = {}
    for v in vendors:
        ids = _fully_missing_reports(engine, v, qdrant_url)
        targets[v] = ids
        print(f"  {v:10s}  {len(ids)} report(s) missing from Qdrant")

    total = sum(len(ids) for ids in targets.values())
    if total == 0:
        print("\n  no reports need backfill — Qdrant is in sync.")
        return 0

    print(f"\n  TOTAL: {total} report(s) to backfill.")

    if not args.commit:
        print("\n  DRY-RUN — re-run with --commit to embed + upsert.")
        return 0

    qdrant_writer = QdrantWriter.from_env()
    total_chunks = total_points = 0
    overall_start = time.perf_counter()
    try:
        for vendor_code, report_ids in targets.items():
            if not report_ids:
                continue
            print()
            print(f"  vendor: {vendor_code}  ({len(report_ids)} report(s))")
            print("  " + "-" * 90)
            for i, rid in enumerate(report_ids, 1):
                t0 = time.perf_counter()
                try:
                    n_chunks, n_points = await _backfill_report(
                        engine, rid,
                        api_keys=api_keys, model_name=args.model,
                        qdrant_writer=qdrant_writer,
                    )
                except Exception as exc:  # noqa: BLE001
                    print(f"    [{i:>3}/{len(report_ids)}] id={rid:<5}  [FAIL] "
                          f"{type(exc).__name__}: {exc!s:.140}")
                    continue
                elapsed = time.perf_counter() - t0
                print(f"    [{i:>3}/{len(report_ids)}] id={rid:<5}  "
                      f"chunks={n_chunks:>3}  points={n_points:>3}  "
                      f"elapsed={elapsed:>5.1f}s")
                total_chunks += n_chunks
                total_points += n_points
    finally:
        qdrant_writer.close()

    print()
    print("=" * 100)
    print(f"  done: {total_points} qdrant point(s) upserted across "
          f"{total_chunks} chunk(s) in {time.perf_counter() - overall_start:.0f}s")
    print("=" * 100)
    return 0


def main() -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--vendor", default="all",
                   help=f"one of {ALL_VENDORS} or 'all' (default)")
    p.add_argument("--model", default=embed_mod.DEFAULT_MODEL_NAME,
                   help=f"embedding model (default {embed_mod.DEFAULT_MODEL_NAME})")
    p.add_argument("--commit", action="store_true",
                   help="actually embed + upsert (default is dry-run)")
    args = p.parse_args()
    if args.vendor != "all" and args.vendor not in ALL_VENDORS:
        print(f"unknown vendor {args.vendor!r}; known: {', '.join(ALL_VENDORS)}")
        return 2
    return asyncio.run(_amain(args))


if __name__ == "__main__":
    sys.exit(main())
