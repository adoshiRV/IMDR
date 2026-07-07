"""End-to-end orchestrator for one PDF.

Phases (each timed):

    fetch → parse → [idempotency] → chunk → upload → embed → MSSQL write → Qdrant write

Upload runs **before** embed deliberately:
  * Don't pay Voyage cost on a doomed run (auth/network failures fail cheaply).
  * If embed/DB blow up later, the PDF still exists on SharePoint —
    a human can inspect or a retry can pick up.
  * dim_report.pdf_path only ever points at a file that actually exists.

Idempotency runs *before* upload+embed so re-runs on a known PDF skip
both expensive remote calls.

When a :class:`QdrantWriter` is passed in, vectors are also pushed to a
per-model Qdrant collection. ``point.id == fact_chunk.id`` so the two
stores stay FK-aligned. ``research.fact_chunk_embedding`` rows are
still written for the audit trail; the ``vector`` column will be
dropped in a follow-up migration once Qdrant is the production source.
"""
from __future__ import annotations

import asyncio
import random
import struct
import time
from dataclasses import dataclass, replace
from pathlib import Path

from sqlalchemy.engine import Engine

from . import embed as embed_mod
from .chunk import chunk_doc
from .fetch import fetch_html_as_pdf, fetch_pdf
from .fetch_bofa import fetch_pdf as fetch_bofa_pdf
from .models import ReportMeta
from .parse import parse_pdf
from .qdrant_writer import ChunkPoint, QdrantWriter
from .upload import upload_pdf


def _is_bofa_url(url: str) -> bool:
    """True for BofA PDF URLs produced by the firehose crawler.

    research1.ml.com/C?... — HMAC self-auth direct PDF (most reports).
    rsch.baml.com/r?...    — forwarded links that redirect through the
                             Liferay viewer; handled by fetch_bofa_pdf.
    """
    return "research1.ml.com" in url or "rsch.baml.com" in url


@dataclass(slots=True)
class IngestResult:
    report_id: int
    was_inserted: bool
    n_chunks: int
    n_embeddings: int
    n_qdrant_points: int
    page_count: int
    sharepoint_path: str | None
    qdrant_collection: str | None
    timings_s: dict[str, float]


async def ingest_one(
    *,
    url: str,
    meta: ReportMeta,
    sharepoint_relative_path: str,
    profile_dir: Path,
    api_keys: dict[str, str],
    engine: Engine,
    embedding_model_name: str = embed_mod.DEFAULT_MODEL_NAME,
    embed: bool = True,
    qdrant_writer: QdrantWriter | None = None,
    store_pdf_text: bool = False,
    pdf_bytes: bytes | None = None,
    source: str = "portal",
    source_type: str = "research",
) -> IngestResult:
    """Fetch → parse → idempotency-check → chunk → upload → embed → DB write.

    Dedup is keyed on ``(vendor_id, pdf_path)`` — a path derived from the
    vendor's own stable document UUID plus date and title slug.  This check
    fires **before** the expensive fetch/parse/embed so a re-run of the same
    logical report costs nothing.

    The content-hash check that follows parse is a second-layer fallback for
    cases where the same PDF bytes land under a different path (rare).  It
    cannot be the primary gate because many vendors (DB, Goldman, STANC …)
    embed per-download watermarks that make the hash differ between downloads
    of the same report.

    ``sharepoint_relative_path`` is the path under the IMDR root of the
    TradeKnowledgeCore/ResearchData1 SharePoint library — e.g.
    ``"goldman/2026/05/721599cb-...pdf"``.

    When ``embed=False`` the embedding step is skipped — chunks are still
    inserted but no rows go into ``research.fact_chunk_embedding``.
    Useful for fast iteration while building the crawler / acquirer;
    production ingest should always run with ``embed=True``.

    ``source`` / ``source_type`` are passed straight through to
    :func:`write_report` (defaults ``portal`` / ``research``). The
    manual-ingest runner sets ``source='manual'`` for locally-supplied
    PDFs that never came from a vendor portal or the email channel.
    """
    from sqlalchemy import text as _sql_text

    from .db import ensure_model_id, resolve_tag_ids, write_report  # noqa: PLC0415

    timings: dict[str, float] = {}

    # Short id for log lines — distinguishes which report is currently
    # in flight when multiple are processed sequentially. Falls back to
    # the URL tail if the meta has no vendor_code/title yet.
    _ref_tag = f"{meta.vendor_code}/{(meta.title or url or '')[:24].rstrip()!r}"

    def _phase_start(name: str, detail: str = "") -> float:
        suffix = f" ({detail})" if detail else ""
        print(f"      [.] {_ref_tag} {name}{suffix} ...", flush=True)
        return time.perf_counter()

    def _phase_end(name: str, t0: float) -> None:
        print(
            f"      [+] {_ref_tag} {name} done in "
            f"{time.perf_counter() - t0:.1f}s",
            flush=True,
        )

    # Pre-fetch dedup: (vendor_id, pdf_path) is stable across runs because
    # the path is derived from the vendor's own document UUID + date + title
    # slug (see ingest/paths.py).  This fires before any network call so
    # repeated daily runs cost nothing for already-ingested reports.
    #
    # content_hash alone cannot be the gate: DB, Goldman, STANC and others
    # embed per-download watermarks that make the hash differ even when the
    # underlying report content is identical — every re-download would slip
    # through and create a duplicate row.
    with engine.connect() as _pre_conn:
        _path_row = _pre_conn.execute(
            _sql_text(
                "SELECT r.id, r.pdf_path "
                "FROM research.dim_report r "
                "JOIN dbo.dim_vendor v ON v.id = r.vendor_id "
                "WHERE v.vendor_code = :vc "
                "  AND r.pdf_path = :path"
            ),
            {"vc": meta.vendor_code, "path": sharepoint_relative_path},
        ).first()
    if _path_row is not None:
        for k in ("pace", "fetch", "parse", "chunk", "embed", "upload", "db", "qdrant"):
            timings[k] = 0.0
        timings["total"] = 0.0
        return IngestResult(
            report_id=_path_row[0],
            was_inserted=False,
            n_chunks=0,
            n_embeddings=0,
            n_qdrant_points=0,
            page_count=0,
            sharepoint_path=_path_row[1] or None,
            qdrant_collection=None,
            timings_s=timings,
        )

    # Inter-report pacing — random sleep before any vendor-side work so
    # the cadence of successive PDF downloads from the same Playwright
    # session looks more like a human reader than an automated firehose.
    # Settings.research_pacing_seconds_{min,max}; max=0 disables.
    try:
        from imdr.config.settings import get_settings  # noqa: PLC0415
        _s = get_settings()
        _pace_max = float(_s.research_pacing_seconds_max)
        _pace_min = float(_s.research_pacing_seconds_min)
    except Exception:  # noqa: BLE001
        _pace_min, _pace_max = 0.0, 0.0
    if _pace_max > 0:
        delay = random.uniform(min(_pace_min, _pace_max), _pace_max)
        timings["pace"] = delay
        await asyncio.sleep(delay)
    else:
        timings["pace"] = 0.0

    t = time.perf_counter()
    if pdf_bytes is None:
        # Dispatch on render_mode first, then URL host.
        # "html" — Goldman markets/blogs content rendered via page.pdf().
        # BofA URLs — research1.ml.com (HMAC self-auth) and rsch.baml.com
        #   (viewer redirect) routed through fetch_bofa_pdf which handles
        #   direct-PDF / expired-interstitial / viewer-remint paths.
        # Default — direct-GET fetch for all other vendors.
        if getattr(meta, "render_mode", "pdf") == "html":
            pdf_bytes = await fetch_html_as_pdf(url, profile_dir)
        elif _is_bofa_url(url):
            pdf_bytes = await fetch_bofa_pdf(url, profile_dir)
        else:
            pdf_bytes = await fetch_pdf(url, profile_dir)
    # else: caller pre-fetched (e.g. Barclays does this during discovery
    # because its session can't survive a separate Chrome launch).
    timings["fetch"] = time.perf_counter() - t

    t = time.perf_counter()
    doc = parse_pdf(pdf_bytes)
    timings["parse"] = time.perf_counter() - t

    # Second-layer dedup: content_hash catches the rare case where the same
    # PDF bytes arrived under a different path (e.g. a vendor reissues with a
    # corrected UUID).  For watermarked vendors the hash will always differ
    # between downloads, so this fallback is a safety net, not the primary gate.
    with engine.connect() as conn:
        existing = conn.execute(
            _sql_text(
                "SELECT id, pdf_path FROM research.dim_report "
                "WHERE content_hash = :h"
            ),
            {"h": doc.content_hash},
        ).first()
    if existing is not None:
        for k in ("chunk", "embed", "upload", "db", "qdrant"):
            timings[k] = 0.0
        timings["total"] = sum(timings.values())
        return IngestResult(
            report_id=existing[0],
            was_inserted=False,
            n_chunks=0,
            n_embeddings=0,
            n_qdrant_points=0,
            page_count=doc.page_count,
            sharepoint_path=existing[1] or None,
            qdrant_collection=None,
            timings_s=timings,
        )

    t = time.perf_counter()
    chunks = chunk_doc(doc)
    timings["chunk"] = time.perf_counter() - t

    _t = _phase_start("upload_pdf", f"{len(doc.pdf_bytes)//1024}KB")
    sharepoint_full_path = await upload_pdf(
        pdf_bytes=doc.pdf_bytes,
        relative_path=sharepoint_relative_path,
    )
    timings["upload"] = time.perf_counter() - _t
    _phase_end("upload_pdf", _t)

    if embed:
        _t = _phase_start("embed_chunks", f"{len(chunks)} chunks")
        embeddings = await embed_mod.embed_chunks(
            chunks,
            model_name=embedding_model_name,
            api_keys=api_keys,
        )
        timings["embed"] = time.perf_counter() - _t
        _phase_end("embed_chunks", _t)
    else:
        embeddings = []
        timings["embed"] = 0.0

    # Now meta knows where the PDF lives.
    meta_with_path = replace(meta, sharepoint_path=sharepoint_full_path)

    spec = embed_mod.get_spec(embedding_model_name)
    # Pre-resolve dim_tag + dim_embedding_model ids in their own
    # autocommit txns BEFORE opening the report transaction. Under
    # parallel vendors, two workers can race on the same canonical tag
    # (every classifier emits MACRO/RATES); doing it here means the
    # IntegrityError catch happens in resolve_tag_ids, not inside the
    # report's engine.begin() where it would roll back the report.
    tag_ids = resolve_tag_ids(engine, meta_with_path.tags)
    model_id_pre: int | None = None
    if embeddings:
        model_id_pre = ensure_model_id(
            engine,
            provider=spec.provider,
            model_name=spec.model_name,
            dimensions=spec.dimensions,
        )
    _t = _phase_start(
        "db_write",
        f"{len(chunks)} chunks, {len(embeddings)} embeds",
    )
    with engine.begin() as conn:
        report_id, was_inserted, chunk_id_by_index, model_id = write_report(
            conn=conn,
            meta=meta_with_path,
            doc=doc,
            chunks=chunks,
            embeddings=embeddings,
            tag_ids=tag_ids,
            model_id=model_id_pre,
            store_pdf_text=store_pdf_text,
            source=source,
            source_type=source_type,
        )
    timings["db"] = time.perf_counter() - _t
    _phase_end("db_write", _t)

    # Push vectors to Qdrant. Point.id = MSSQL fact_chunk.id (FK link).
    n_qdrant_points = 0
    qdrant_collection: str | None = None
    if (
        qdrant_writer is not None
        and was_inserted
        and embeddings
        and model_id is not None
    ):
        _t = time.perf_counter()
        # Build chunk lookup by index for O(1) payload assembly.
        chunks_by_index = {c.chunk_index: c for c in chunks}
        points: list[ChunkPoint] = []
        for emb in embeddings:
            chunk = chunks_by_index.get(emb.chunk_index)
            chunk_id = chunk_id_by_index.get(emb.chunk_index)
            if chunk is None or chunk_id is None:
                continue
            # Deserialise the float32-LE-packed vector back to a list[float].
            vec_floats = list(
                struct.unpack(f"<{spec.dimensions}f", emb.vector)
            )
            points.append(ChunkPoint(
                chunk_id=chunk_id,
                vector=vec_floats,
                report_id=report_id,
                vendor_code=meta_with_path.vendor_code,
                publish_date=meta_with_path.publish_date,
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                title=meta_with_path.title,
                text_preview=chunk.text,
                model_id=model_id,
            ))
        if points:
            _t = _phase_start("qdrant_upsert", f"{len(points)} points")
            qdrant_collection = qdrant_writer.upsert_chunks(
                model_name=spec.model_name,
                dimensions=spec.dimensions,
                points=points,
            )
            n_qdrant_points = len(points)
            _phase_end("qdrant_upsert", _t)
        timings["qdrant"] = time.perf_counter() - _t
    else:
        timings["qdrant"] = 0.0

    timings["total"] = sum(timings.values())

    return IngestResult(
        report_id=report_id,
        was_inserted=was_inserted,
        n_chunks=len(chunks),
        n_embeddings=len(embeddings),
        n_qdrant_points=n_qdrant_points,
        page_count=doc.page_count,
        sharepoint_path=sharepoint_full_path,
        qdrant_collection=qdrant_collection,
        timings_s=timings,
    )
