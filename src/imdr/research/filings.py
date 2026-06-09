"""Govt-filings ingest helper — reuses the research corpus stack.

A *filing* is a dated text document published by an official source (central
bank, ministry, regulator, statistical agency, official think-tank). Examples:

  - Bank of Korea MPC Minutes
  - MOEF Treasury Issuance Plan
  - FSS Press Release on capital ratios
  - KCS 10-day trade quick estimate
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
know the agency-specific URL recipes and call :func:`ingest_filing` once
per document discovered.

The classifier path is bypassed by design — for an official source the
classification *is* the source. Tags are passed in by the caller (`doc_type`,
`stream`, `asset_class` etc.) rather than inferred from text.

This module is a SKELETON. It declares the public contract and lays out
the call sequence. Internal helpers delegate to existing primitives in
``playground/research/ingest/`` so we don't duplicate parsing/chunking/
embedding/upload logic.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Literal, Protocol


# Re-export the vendor-category enum so per-country callers don't import
# it from the migration. Matches CHECK constraint in migration 086.
VendorCategory = Literal[
    "official_cb",
    "official_ministry",
    "official_regulator",
    "official_thinktank",
    "official_statistics",
    "official_market_infra",
]

# Canonical doc-type taxonomy for filings. Stored as a tag with
# category='doc_type' on ``research.map_report_tag``. Keep narrow —
# Mycroft/Lois rely on this vocabulary for filtering.
DocType = Literal[
    "decision",   # CB policy decision text / opening remarks
    "minutes",    # MPC minutes / board minutes
    "outlook",    # Economic outlook / forecast publication
    "report",     # Periodic report (MPR, FSR, Annual, Issue Note, …)
    "speech",     # Governor / minister / official speech transcript
    "release",    # Press release, statistical release, announcement
    "review",     # Stability review, sectoral review
]


@dataclass(slots=True, frozen=True)
class FilingInput:
    """One filing as known to the caller, before this module touches it.

    Constructed by the per-country prod fetcher and passed to
    :func:`ingest_filing`. Required fields cover what the SharePoint mirror,
    dim_report row, and Qdrant payload need; everything else has a sensible
    default.

    Either ``pdf_bytes`` OR ``pdf_url`` must be provided. If only ``pdf_url``
    is given, the helper fetches the PDF via the patient TLS-1.2 session
    (same shape as ``playground/econ/kr_govt_docs/_kr_http.py``). If both
    are given, ``pdf_bytes`` wins and ``pdf_url`` is stored only as the
    canonical source URL on the dim_report row.

    For HTML-only sources (e.g. MOEF detail pages without an attached PDF),
    pass ``body_text`` instead of ``pdf_bytes`` — the helper synthesizes a
    single-page Document from the text and skips PDF parsing.
    """

    # Identity
    vendor_code: str                  # e.g. "bok", "moef_kr", "fss_kr"
    title: str
    publish_date: date
    source_url: str                   # canonical URL (RSS link, detail page, …)

    # Body — exactly one of these must be non-empty
    pdf_bytes: bytes | None = None
    pdf_url: str | None = None        # used if pdf_bytes is None
    body_text: str | None = None      # used if neither pdf is available

    # Classification (set by the caller from the source itself —
    # NO classifier runs on filings).
    doc_type: DocType | None = None
    stream: str = ""                  # e.g. "mpc_minutes", "treasury_debt_rss"
    asset_class: str = "macro"
    region: str = ""                  # ISO region or country group
    country_code: str | None = None   # 2-char ISO; resolved to dim_country.id
    authors: str = ""                 # agency name or named individual
    language: str = "en"

    # Free-form tags emitted by the caller for downstream filtering. Each
    # entry becomes a row in research.map_report_tag via the existing
    # resolve_tag_ids() race-safe upsert. Suggested categories:
    #   ('doc_type', '...'), ('stream', '...'), ('topic', '...'),
    #   ('agency_unit', '...'), ('language', '...').
    tags: tuple[tuple[str, str], ...] = field(default=())


@dataclass(slots=True, frozen=True)
class FilingResult:
    """What :func:`ingest_filing` returns. Idempotent shape — re-running
    on the same content_hash returns the existing report_id and sets
    ``already_existed=True`` so the caller can short-circuit log/notify."""

    report_id: int
    content_hash: bytes
    sharepoint_path: str | None       # None when body_text path is used (no PDF)
    chunk_count: int
    embedding_count: int              # 0 if embed=False or embedding skipped
    already_existed: bool


# ---------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------

def ingest_filing(
    filing: FilingInput,
    *,
    embed: bool = True,
    store_pdf_text: bool = False,
) -> FilingResult:
    """Ingest one filing end-to-end. Idempotent on ``content_hash``.

    Sequence:
      1. Resolve PDF/text bytes (fetch if needed, hash, dedupe).
      2. If ``content_hash`` already present in ``research.dim_report`` →
         return existing report_id with ``already_existed=True``.
      3. Parse PDF (PyMuPDF) OR synthesize a Document from ``body_text``.
      4. Upload PDF to SharePoint (skipped for text-only filings).
      5. Chunk + embed (embed step skipped when ``embed=False``).
      6. Write metadata row, chunks, and Qdrant points in one transaction
         (Qdrant write is a separate non-transactional step — see notes).
      7. Tag the report with ``doc_type``, ``stream``, plus caller-supplied
         tags. ``vendor_category`` flows from ``dbo.dim_vendor`` lookup
         and is added to the Qdrant payload (NOT stored on dim_report —
         it's denormalized from the vendor row).

    Args:
        filing: caller-supplied metadata + body.
        embed: when False, write the chunks but skip embedding/Qdrant.
            Useful for backfill paths that re-embed later.
        store_pdf_text: forwarded to db.insert_report. When False
            (default), the full PDF text is NOT written to dim_report —
            canonical text lives only in fact_chunk.chunk_text.

    Raises:
        ValueError: vendor_code not in dim_vendor, or vendor exists but
            vendor_category is not one of the official_* values.
        ValueError: filing has neither pdf_bytes nor pdf_url nor body_text.
        RuntimeError: PDF parse / chunk / embed failures (propagated).
    """
    raise NotImplementedError("skeleton — see module docstring for contract")


# ---------------------------------------------------------------------
# Internals — declared as Protocols so the skeleton compiles and the
# real wiring can be filled in later. Each delegates to existing helpers
# in playground/research/ingest/ rather than duplicating logic.
# ---------------------------------------------------------------------

class _PdfFetcher(Protocol):
    """Patient TLS-1.2 fetcher for govt-source URLs. Implementation
    reuses the helper proven in playground/econ/kr_govt_docs/_kr_http.py
    (10-attempt retry, 2.5s base backoff). Promoted to src/imdr/connectors/
    when this module ships."""

    def fetch_pdf(self, url: str) -> bytes: ...


def _resolve_vendor(vendor_code: str) -> tuple[int, VendorCategory]:
    """Look up vendor_id + vendor_category in one round-trip.

    Validates that vendor_category is one of the ``official_*`` values —
    a filing ingest path is not the right call site for a sell_side
    vendor (use the existing crawler scaffold instead).

    Raises ValueError if vendor_code is unknown or has the wrong
    category.
    """
    raise NotImplementedError


def _short_circuit_if_exists(content_hash: bytes) -> int | None:
    """Existing-row check, identical shape to
    ``playground/research/ingest/db._get_existing_report_id``."""
    raise NotImplementedError


def _parse_or_synthesize(filing: FilingInput, pdf_bytes: bytes | None) -> "Document":  # type: ignore[name-defined]
    """Build a ``Document`` from EITHER pdf bytes (parse with PyMuPDF via
    ``playground/research/ingest/parse.parse_pdf``) OR body_text (synthesize
    a single-page Document for HTML-only sources). Returns the same dataclass
    shape that the existing ingest pipeline emits, so chunk/embed/write paths
    don't need to fork."""
    raise NotImplementedError


def _build_report_meta(
    filing: FilingInput, vendor_id: int, sharepoint_path: str | None
) -> "ReportMeta":  # type: ignore[name-defined]
    """Construct ReportMeta directly from the FilingInput — no classifier
    enrichment. The ``context`` field is left empty; downstream summary
    generation can run on chunks later if desired."""
    raise NotImplementedError


def _qdrant_payload_extra(vendor_category: VendorCategory, filing: FilingInput) -> dict:
    """Extra payload fields written alongside the default (vendor_code,
    publish_date, …) Qdrant payload. Critical: ``vendor_category`` and
    ``country_code`` go here so Mycroft/Lois can pre-filter at search
    time without an SQL round-trip.

    Returned dict is merged into ChunkPoint.extra_payload at upsert time.
    Requires a corresponding payload-index addition in
    ``src/imdr/connectors/qdrant_schema.CollectionSpec.payload_indexes``
    (vendor_category as KEYWORD, country_code as KEYWORD) — out of scope
    for this skeleton but flagged here so the wiring step doesn't miss it.
    """
    return {
        "vendor_category": vendor_category,
        "country_code": (filing.country_code or "").upper() or None,
        "doc_type": filing.doc_type,
        "stream": filing.stream or None,
        "language": filing.language,
    }


# ---------------------------------------------------------------------
# Caller pattern (illustrative — for kr_monthly.py and siblings)
# ---------------------------------------------------------------------
#
# from imdr.research.filings import FilingInput, ingest_filing
# from imdr.research.fetchers.kr_bok import discover_bok_listcont  # to be built
#
# for item in discover_bok_listcont(menu_no="400007", page_unit=10):
#     ingest_filing(FilingInput(
#         vendor_code="bok",
#         title=item.title,
#         publish_date=item.publish_date,
#         source_url=item.detail_url,
#         pdf_url=item.pdf_url,
#         doc_type="release" if "Notice" in item.title else "report",
#         stream="bok_news_publications",
#         asset_class="rates",
#         region="ASIA-EM",
#         country_code="KR",
#         authors="Bank of Korea",
#         tags=(("doc_type", "release"), ("stream", "bok_news_publications")),
#     ))
#
# The fetcher module (kr_bok / kr_moef_rss / kr_fss / kr_fsc / kr_kcs /
# kr_motir / kr_kdi) is responsible for the URL recipes confirmed in
# docs/admin/econ/korea/govt_doc_sources.md. Each fetcher emits an
# iterable of "item" dataclasses; this module turns each item into a
# dim_report row + Qdrant points.
