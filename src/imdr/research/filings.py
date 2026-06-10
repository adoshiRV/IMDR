"""Govt-filings ingest helper — reuses the research corpus stack.

A *filing* is a dated text document published by an official source (central
bank, ministry, regulator, statistical agency, official think-tank). Examples:

  - Bank of Korea MPC Minutes
  - MOEF Treasury Issuance Plan
  - FSS Press Release on capital ratios
  - KDI Monthly Economic Trends

Filings land in the same downstream stack as sell-side research:

  * Metadata  -> ``research.dim_report`` (vendor_id = the agency)
  * PDF       -> SharePoint mirror (``IMDR/research/{vendor_code}/...``)
  * Chunks    -> ``research.fact_chunk``
  * Vectors   -> Qdrant collection (payload includes ``vendor_category``)

…but they DO NOT touch the sell-side scraper scaffold
(``playground/research/ingest_today.py``, the per-vendor crawlers, the
classifiers, the relevance filter). Filings are called from the per-country
prod scripts (``scripts/econ/kr/...``, ``scripts/econ/id/...`` etc.) which
know the agency-specific URL recipes, do their own discovery, and call
:func:`ingest_filing` once per document.

The classifier path is bypassed by design — for an official source the
classification *is* the source. Tags are passed in by the caller (`doc_type`,
`stream`, `asset_class` etc.) rather than inferred from text.
"""
from __future__ import annotations

import asyncio
import hashlib
import re
import struct
from dataclasses import dataclass, field, replace as _replace
from datetime import date
from typing import Literal

from sqlalchemy import text as _sql_text
from sqlalchemy.engine import Engine

# Reach into playground for the proven primitives — these will move to
# src/imdr/research/ingest/ in a later promotion pass. Importing direct
# avoids duplicating ~600 LoC of parse/chunk/embed/upload/write code.
import sys as _sys
from pathlib import Path as _Path
_PLAYGROUND_ROOT = _Path(__file__).resolve().parents[3] / "playground"
if str(_PLAYGROUND_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_PLAYGROUND_ROOT))

from research.ingest import embed as embed_mod  # noqa: E402
from research.ingest.chunk import chunk_doc  # noqa: E402
from research.ingest.db import ensure_model_id, resolve_tag_ids, write_report  # noqa: E402
from research.ingest.models import Chunk, Document, Embedding, ReportMeta  # noqa: E402
from research.ingest.parse import parse_pdf  # noqa: E402
from research.ingest.qdrant_writer import ChunkPoint, QdrantWriter  # noqa: E402
from research.ingest.upload import upload_pdf  # noqa: E402


# Vendor-category enum — mirrors CHECK constraint in migration 086.
VendorCategory = Literal[
    "official_cb",
    "official_ministry",
    "official_regulator",
    "official_thinktank",
    "official_statistics",
    "official_market_infra",
    "official_supranational",
]
_ALLOWED_OFFICIAL = set(VendorCategory.__args__)  # type: ignore[attr-defined]


# Canonical doc-type taxonomy for filings.
DocType = Literal[
    "decision", "minutes", "outlook", "report", "speech", "release", "review",
]


@dataclass(slots=True, frozen=True)
class FilingInput:
    """One filing as known to the caller, before this module touches it."""

    vendor_code: str
    title: str
    publish_date: date
    source_url: str

    # Body — exactly one of these must be non-empty
    pdf_bytes: bytes | None = None
    pdf_url: str | None = None
    body_text: str | None = None

    # Classification (set by the caller from the source itself —
    # NO classifier runs on filings).
    doc_type: str | None = None
    stream: str = ""
    asset_class: str = "macro"
    region: str = ""
    country_code: str | None = None
    authors: str = ""
    language: str = "en"

    # Free-form tags emitted by the caller for downstream filtering.
    tags: tuple[tuple[str, str], ...] = field(default=())


@dataclass(slots=True, frozen=True)
class FilingResult:
    report_id: int
    content_hash: bytes
    sharepoint_path: str | None
    chunk_count: int
    embedding_count: int
    already_existed: bool
    qdrant_collection: str | None


# ---------------------------------------------------------------------
# Document synthesis for body-text-only sources (MOEF, MOTIR, FSC body)
# ---------------------------------------------------------------------

_SYNTH_PARSER_VERSION = "html-body-synth-v1"


def synthesize_document_from_text(
    title: str,
    body_text: str,
    *,
    vendor_code: str = "",
    source_url: str = "",
) -> Document:
    """Build a :class:`Document` from raw body text (HTML-stripped).

    Used when an agency publishes releases as HTML body only (no PDF).
    The synthetic Document goes through the same chunk/embed/write path
    as a real PDF; the only difference is ``parser_version`` and a
    single 'page' equal to the full body.

    ``vendor_code`` + ``source_url`` are prepended to the hash input as
    a namespace prefix so two filings from different vendors that
    happen to share an identical title + body don't collide on
    ``content_hash`` (defensive — DB review 2026-06-10). The prefix
    does NOT appear in ``full_text`` so chunking/embedding sees only
    the source content.

    ``title`` is prepended to the body in ``full_text`` so the first
    chunk's text_preview surfaces the filing title at search time.
    """
    full = f"{title}\n\n{body_text}".strip()
    namespace = f"{vendor_code}::{source_url}\n\n"
    hash_input = (namespace + full).encode("utf-8")
    return Document(
        pdf_bytes=full.encode("utf-8"),  # synthetic placeholder — never uploaded
        content_hash=hashlib.sha256(hash_input).digest(),
        full_text=full,
        page_count=1,
        parser_version=_SYNTH_PARSER_VERSION,
        pages_text=(full,),
    )


# ---------------------------------------------------------------------
# Vendor resolution
# ---------------------------------------------------------------------

def _resolve_vendor(engine: Engine, vendor_code: str) -> tuple[int, str]:
    """Return (vendor_id, vendor_category). Caller validates the category."""
    with engine.connect() as conn:
        row = conn.execute(
            _sql_text("SELECT id, vendor_category FROM dbo.dim_vendor WHERE vendor_code = :c"),
            {"c": vendor_code},
        ).first()
    if row is None:
        raise ValueError(
            f"vendor_code={vendor_code!r} not in dbo.dim_vendor — seed first via a migration"
        )
    vendor_id, vendor_category = int(row[0]), str(row[1])
    if vendor_category not in _ALLOWED_OFFICIAL:
        raise ValueError(
            f"vendor_code={vendor_code!r} has vendor_category={vendor_category!r}; "
            f"filings ingest accepts only official_* categories (got non-official)"
        )
    return vendor_id, vendor_category


def _existing_report_id(engine: Engine, content_hash: bytes) -> tuple[int, str | None] | None:
    """Idempotency check — returns (report_id, sharepoint_path) if present."""
    with engine.connect() as conn:
        row = conn.execute(
            _sql_text("SELECT id, pdf_path FROM research.dim_report WHERE content_hash = :h"),
            {"h": content_hash},
        ).first()
    if row is None:
        return None
    return int(row[0]), (row[1] or None)


# ---------------------------------------------------------------------
# SharePoint path
# ---------------------------------------------------------------------

_VENDOR_CODE_RE = re.compile(r"^[a-z0-9][a-z0-9_]{0,28}[a-z0-9]$|^[a-z0-9]$")
_COUNTRY_CODE_RE = re.compile(r"^[a-z]{2,4}$")


def _build_sharepoint_path(filing: FilingInput, content_hash: bytes) -> str:
    """SharePoint path for govt filings — fits inside the existing
    date-first ``{YYYY}/{MM}/{DD}/`` hierarchy used by sell-side research
    (see ``playground/research/ingest/paths.py``).

    Layout: ``{YYYY}/{MM}/{DD}/econ/{country}/{vendor}/{slug}_{hash8}.pdf``

    Sell-side path is ``{YYYY}/{MM}/{DD}/{vendor}/...``. Govt filings
    insert ``econ/{country}/`` between the date and vendor so a single
    day folder shows both sell-side vendors (top-level) and govt
    filings (under ``econ/``) grouped by country. Country defaults to
    ``unknown`` if filing has no country_code — should never happen
    for KR per-country prod runs.

    Vendor + country are validated against narrow alnum regexes so a
    badly-formed `FilingInput` fails fast here, not deep inside
    `upload_pdf::_safe_relative_path` (defense in depth — security
    review 2026-06-10).
    """
    country = (filing.country_code or "unknown").lower()
    if not _COUNTRY_CODE_RE.match(country):
        raise ValueError(
            f"country_code must be 2–4 lower-case ASCII letters, got {country!r}"
        )
    if not _VENDOR_CODE_RE.match(filing.vendor_code):
        raise ValueError(
            f"vendor_code must match [a-z0-9_] (≤30 chars), got {filing.vendor_code!r}"
        )
    hash_short = content_hash.hex()[:8]
    yyyy = f"{filing.publish_date.year:04d}"
    mm = f"{filing.publish_date.month:02d}"
    dd = f"{filing.publish_date.day:02d}"
    slug = "".join(c if c.isalnum() else "-" for c in filing.title.lower())
    slug = "-".join(p for p in slug.split("-") if p)[:80]
    return f"{yyyy}/{mm}/{dd}/econ/{country}/{filing.vendor_code}/{slug}_{hash_short}.pdf"


# ---------------------------------------------------------------------
# ReportMeta construction (no classifier — direct from FilingInput)
# ---------------------------------------------------------------------

def _build_meta(filing: FilingInput, vendor_id: int) -> ReportMeta:
    """Construct ReportMeta directly. No classifier enrichment.

    Tags emitted: ('doc_type', X), ('stream', X), ('language', X), plus
    everything in filing.tags.
    """
    base_tags: list[tuple[str, str]] = []
    if filing.doc_type:
        base_tags.append(("doc_type", filing.doc_type))
    if filing.stream:
        base_tags.append(("stream", filing.stream))
    if filing.language:
        base_tags.append(("language", filing.language))
    base_tags.extend(filing.tags)

    return ReportMeta(
        vendor_code=filing.vendor_code,
        vendor_id=vendor_id,
        title=filing.title,
        publish_date=filing.publish_date,
        pdf_url=filing.source_url,
        sharepoint_path=None,    # filled in post-upload
        asset_class=filing.asset_class,
        region=filing.region,
        country_code=filing.country_code,
        authors=filing.authors,
        context="",              # no classifier output for filings
        tags=tuple(base_tags),
    )


# ---------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------

async def ingest_filing(
    filing: FilingInput,
    *,
    engine: Engine,
    api_keys: dict[str, str],
    qdrant_writer: QdrantWriter | None = None,
    embed: bool = True,
    store_pdf_text: bool = False,
    embedding_model_name: str = embed_mod.DEFAULT_MODEL_NAME,
) -> FilingResult:
    """Ingest one filing end-to-end. Idempotent on ``content_hash``.

    Sequence:
      1. Resolve vendor_id + vendor_category from dbo.dim_vendor.
      2. Resolve body: PDF bytes (preferred) OR synthesized Document
         from body_text. Caller supplies one of pdf_bytes, body_text.
         (pdf_url support TBD — currently the per-agency resolvers
         download bytes upstream.)
      3. Hash → idempotency-check; short-circuit if already present.
      4. Chunk via tiktoken (cl100k, 800/100).
      5. Upload PDF to SharePoint (skipped for body_text-only filings).
      6. Embed (skipped when embed=False).
      7. Write to research.dim_report + fact_chunk in one transaction.
      8. Upsert chunks to Qdrant with vendor_category in payload.

    Raises:
      ValueError: vendor_code unknown OR not in official_* category.
      ValueError: filing has neither pdf_bytes nor body_text.
    """
    # 1. Vendor
    vendor_id, vendor_category = _resolve_vendor(engine, filing.vendor_code)

    # 2. Document — either parse PDF or synthesize from body_text
    has_pdf = filing.pdf_bytes is not None
    if has_pdf:
        doc = parse_pdf(filing.pdf_bytes or b"")
    elif filing.body_text:
        doc = synthesize_document_from_text(
            filing.title,
            filing.body_text,
            vendor_code=filing.vendor_code,
            source_url=filing.source_url,
        )
    else:
        raise ValueError(
            f"FilingInput for vendor={filing.vendor_code} title={filing.title[:60]!r} "
            "has neither pdf_bytes nor body_text — caller must provide one."
        )

    # 3. Idempotency
    existing = _existing_report_id(engine, doc.content_hash)
    if existing is not None:
        report_id, sp_path = existing
        return FilingResult(
            report_id=report_id,
            content_hash=doc.content_hash,
            sharepoint_path=sp_path,
            chunk_count=0,
            embedding_count=0,
            already_existed=True,
            qdrant_collection=None,
        )

    # 4. Chunk
    chunks: list[Chunk] = chunk_doc(doc)

    # 5. SharePoint upload — only when we have real PDF bytes
    sharepoint_path: str | None = None
    if has_pdf:
        sp_rel = _build_sharepoint_path(filing, doc.content_hash)
        sharepoint_path = await upload_pdf(
            pdf_bytes=filing.pdf_bytes or b"",
            relative_path=sp_rel,
        )

    # 6. Embed
    embeddings: list[Embedding] = []
    if embed and chunks:
        embeddings = await embed_mod.embed_chunks(
            chunks,
            model_name=embedding_model_name,
            api_keys=api_keys,
        )

    spec = embed_mod.get_spec(embedding_model_name)
    model_id: int | None = None
    if embeddings:
        model_id = ensure_model_id(
            engine,
            provider=spec.provider,
            model_name=spec.model_name,
            dimensions=spec.dimensions,
        )

    # Build meta now that sharepoint_path is known.
    meta = _build_meta(filing, vendor_id)
    meta_with_path = _replace(meta, sharepoint_path=sharepoint_path or "")

    # Resolve dim_tag ids in autocommit before opening report txn (race-safe).
    tag_ids = resolve_tag_ids(engine, meta_with_path.tags)

    # 7. DB write
    with engine.begin() as conn:
        report_id, was_inserted, chunk_id_by_index, model_id_returned = write_report(
            conn=conn,
            meta=meta_with_path,
            doc=doc,
            chunks=chunks,
            embeddings=embeddings,
            tag_ids=tag_ids,
            model_id=model_id,
            store_pdf_text=store_pdf_text,
        )

    # 8. Qdrant
    qdrant_collection: str | None = None
    if qdrant_writer is not None and was_inserted and embeddings and model_id_returned is not None:
        chunks_by_index = {c.chunk_index: c for c in chunks}
        extra = _qdrant_payload_extra(filing, vendor_category)
        points: list[ChunkPoint] = []
        for emb in embeddings:
            ch = chunks_by_index.get(emb.chunk_index)
            ch_id = chunk_id_by_index.get(emb.chunk_index)
            if ch is None or ch_id is None:
                continue
            vec_floats = list(struct.unpack(f"<{spec.dimensions}f", emb.vector))
            points.append(ChunkPoint(
                chunk_id=ch_id,
                vector=vec_floats,
                report_id=report_id,
                vendor_code=filing.vendor_code,
                publish_date=filing.publish_date,
                page_start=ch.page_start,
                page_end=ch.page_end,
                title=filing.title,
                text_preview=ch.text,
                model_id=model_id_returned,
                extra_payload=extra,
            ))
        if points:
            qdrant_collection = qdrant_writer.upsert_chunks(
                model_name=spec.model_name,
                dimensions=spec.dimensions,
                points=points,
            )

    return FilingResult(
        report_id=report_id,
        content_hash=doc.content_hash,
        sharepoint_path=sharepoint_path,
        chunk_count=len(chunks),
        embedding_count=len(embeddings),
        already_existed=False,
        qdrant_collection=qdrant_collection,
    )


def _qdrant_payload_extra(filing: FilingInput, vendor_category: str) -> dict:
    """Extra payload fields written alongside the default Qdrant payload.

    The four added-2026-06-10 KEYWORD indexes (vendor_category,
    country_code, doc_type, stream) are populated here. Sell-side points
    leave these unset; Mycroft/Lois pre-filter on vendor_category to
    isolate or blend corpora.
    """
    return {
        "vendor_category": vendor_category,
        "country_code": (filing.country_code or "").upper() or None,
        "doc_type": filing.doc_type,
        "stream": filing.stream or None,
        "language": filing.language,
    }


# ---------------------------------------------------------------------
# Sync wrapper for non-async callers (per-country prod scripts)
# ---------------------------------------------------------------------

def ingest_filing_sync(filing: FilingInput, **kwargs) -> FilingResult:
    """Sync convenience wrapper — wraps the async core in asyncio.run.

    Use from per-country prod scripts (scripts/econ/kr/kr_govt_daily.py)
    that don't have an existing event loop. If the caller already has a
    loop, call :func:`ingest_filing` directly.
    """
    return asyncio.run(ingest_filing(filing, **kwargs))
