"""US govt filings ingest — Fed / Treasury / NY Fed.

Discovers documents via the 11 stream probes under
``scripts/econ/us/govt/`` and calls
:func:`imdr.research.filings.ingest_filing_sync` for each.

Each document lands in:
  - ``research.dim_report``  (metadata, deduped on content_hash)
  - SharePoint mirror        (``IMDR/research/{vendor_code}/...``)
  - ``research.fact_chunk``  (text chunks)
  - Qdrant collection        (vectors w/ vendor_category in payload)

DIFFERENCE FROM INDIA: India walks pre-downloaded PDFs from disk
(``data/econ/in/govt/{folder}/``). US probes are MANIFEST-ONLY — they
return ``FilingItem`` objects with metadata + URLs, no local bytes.
This module resolves the document bytes at ingest time:

  * ``item.pdf_url`` set → ``httpx GET pdf_url`` → ``pdf_bytes=<bytes>``
  * ``item.pdf_url`` is None (HTML-only, e.g. fed_speeches) →
    ``httpx GET item.source_url`` → BeautifulSoup body-text extraction
    → ``body_text=<text>``  (``filings.ingest_filing`` synthesises a
    Document from plain text via ``synthesize_document_from_text``).

doc_type mapping (probe → FilingInput.doc_type = DocType literal):
  - "decision"   → "decision"   (FOMC statements)
  - "minutes"    → "minutes"    (FOMC minutes)
  - "projection" → "report"     (SEP / dot-plot; not in DocType)
  - "transcript" → "report"     (press-conf Q&A; not in DocType)
  - "speech"     → "speech"     (Fed speeches)
  - "testimony"  → "speech"     (testimony is a speech form; not in DocType)
  - "survey"     → "report"     (SLOOS, NY Fed SME; not in DocType)
  - "refunding"  → "report"     (Treasury QRA; not in DocType)
  - "report"     → "report"     (MPR, Beige Book, FSR)

CLI:
    python -m scripts.econ.us.govt.ingest_filings --dry-run --recent-years 2
    python -m scripts.econ.us.govt.ingest_filings --vendor fomc_statements
    python -m scripts.econ.us.govt.ingest_filings --limit 3 --no-qdrant
    python -m scripts.econ.us.govt.ingest_filings --recent-years 5 --no-embed
    python -m scripts.econ.us.govt.ingest_filings  # all streams, last 2 years

Wired into ``scripts/econ/us/us_daily.py`` (the per-country daily
orchestrator) via dual-track wiring — that step is separately gated.
"""

from __future__ import annotations

import argparse
import datetime
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from imdr.config.settings import get_settings

# Heavy ingest deps (imdr.research.filings + the playground QdrantWriter,
# which pulls tiktoken/embed stack) are lazy-imported inside main() so the
# module imports cheaply and --dry-run stays free of them.
# QdrantWriter lives in playground (per project-research-mcp-owner-only) —
# same sanctioned sys.path idiom as scripts/econ/kr/govt/ingest_filings.py.
_REPO_ROOT = Path(__file__).resolve().parents[4]   # scripts/econ/us/govt/<file>

# In-folder imports — the promoted probes use sys.path.insert(__file__.parent)
# to find _http/_models; we replicate that so importing probes as modules works.
_GOVT_DIR = Path(__file__).resolve().parent
if str(_GOVT_DIR) not in sys.path:
    sys.path.insert(0, str(_GOVT_DIR))


# DocType literal (from src/imdr/research/filings.py):
#   "decision","minutes","outlook","report","speech","release","review"
# Probe doc_types that are NOT in DocType are remapped here:
_DOCTYPE_MAP: dict[str, str] = {
    "decision":   "decision",    # FOMC statements
    "minutes":    "minutes",     # FOMC minutes
    "projection": "report",      # SEP — not in DocType
    "transcript": "report",      # press-conf — not in DocType
    "speech":     "speech",      # fed speeches
    "testimony":  "speech",      # testimony is a speech form — not in DocType
    "report":     "report",      # MPR / Beige Book / FSR
    "survey":     "report",      # SLOOS / NY Fed SME — not in DocType
    "refunding":  "report",      # Treasury QRA — not in DocType
    "release":    "release",     # passthrough
    "outlook":    "outlook",     # passthrough
    "review":     "review",      # passthrough
}


# Stream → discover() function + kwargs for daily_pull.
# The label here is the stream_id used in FilingItem.stream + dry-run output.
# Import probes here (cheap — no network calls at import time).
import probe_fomc_statements      # noqa: E402
import probe_fomc_minutes         # noqa: E402
import probe_fomc_sep             # noqa: E402
import probe_fed_speeches         # noqa: E402
import probe_fomc_presconf        # noqa: E402
import probe_mpr                  # noqa: E402
import probe_beige_book           # noqa: E402
import probe_financial_stability  # noqa: E402
import probe_sloos                # noqa: E402
import probe_treasury_refunding   # noqa: E402
import probe_nyfed_surveys        # noqa: E402

# (stream_id, discover_fn, discover_kwargs, vendor_code_override_or_None)
# vendor_code comes from FilingItem.vendor_code; the override column is
# listed for documentation only (all probes set vendor_code internally).
_STREAMS: list[tuple[str, Callable, dict, str]] = [
    ("fomc_statements",            probe_fomc_statements.discover,    {},              "fed"),
    ("fomc_minutes",               probe_fomc_minutes.discover,       {},              "fed"),
    ("fomc_sep",                   probe_fomc_sep.discover,            {},              "fed"),
    ("fed_speeches",               probe_fed_speeches.discover,        {"limit": 40},   "fed"),
    ("fomc_presconf",              probe_fomc_presconf.discover,       {},              "fed"),
    ("monetary_policy_report",     probe_mpr.discover,                 {},              "fed"),
    ("beige_book",                 probe_beige_book.discover,          {"limit": 16},   "fed"),
    ("financial_stability_report", probe_financial_stability.discover, {},              "fed"),
    ("sloos",                      probe_sloos.discover,               {"limit": 16},   "fed"),
    ("treasury_refunding",         probe_treasury_refunding.discover,  {"quarters": 8}, "treasury_us"),
    ("nyfed_dealer_survey",        probe_nyfed_surveys.discover,       {"meetings": 8}, "nyfed"),
]


@dataclass(slots=True)
class IngestStats:
    stream: str
    vendor_code: str
    doc_type: str
    n_items: int = 0
    ingested: int = 0
    already_existed: int = 0
    failed: int = 0
    chunks_total: int = 0
    embeddings_total: int = 0


def _cutoff_date(recent_years: int) -> datetime.date:
    today = datetime.date.today()
    return today.replace(year=today.year - recent_years)


def _compute_rc(
    total_ok: int, total_skip: int, total_fail: int, n_discover_failures: int
) -> int:
    """Exit code for the ingest run.

    rc=1 in two cases: (a) any stream failed DISCOVERY outright — a probe
    break / site redesign is a real outage the unattended scheduler must see,
    even if a surviving stream had an already-ingested item; or (b) an
    item-level true outage — failures occurred with zero progress. A run that
    made progress (ingested) or found everything already ingested (all-skips)
    stays rc=0 even if a known-discontinued PDF 404s (those retry next run)."""
    item_outage = total_ok == 0 and total_skip == 0 and total_fail > 0
    return 1 if (n_discover_failures > 0 or item_outage) else 0


def _api_keys_from_settings() -> dict[str, str]:
    s = get_settings()
    return {
        "voyage": s.voyage_key or "",
        "google": s.gemini_key or "",
    }


def _strip_html_body(html: str) -> str:
    """Extract main body text from an HTML page (strips nav/script/style)."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        # Fallback: strip all tags with a simple regex.
        import re
        text = re.sub(r"<[^>]+>", " ", html)
        return " ".join(text.split())

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
        tag.decompose()
    main = soup.find("main") or soup.find("article") or soup.find("div", class_="content")
    target = main or soup.body or soup
    return " ".join(target.get_text(separator=" ").split())


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--vendor", nargs="*",
        help="Stream IDs to ingest (e.g. fomc_statements fomc_minutes). "
             "Default: all streams.",
    )
    p.add_argument(
        "--recent-years", type=int, default=2,
        help="Only ingest documents published within the last N years (default 2). "
             "Use a large number (e.g. 20) for a full backfill.",
    )
    p.add_argument(
        "--since-days", type=int, default=None,
        help="Daily fast-path: only ingest documents published within the last N "
             "days. Overrides --recent-years when set — the daily orchestrator uses "
             "this so it doesn't re-fetch the whole multi-year corpus each run "
             "(content-hash dedup makes any overlap a cheap skip).",
    )
    p.add_argument(
        "--limit", type=int, default=None,
        help="Max items per stream (for smoke tests).",
    )
    p.add_argument(
        "--dry-run", action="store_true",
        help="Plan only — list what would be ingested (no network, no DB, no Qdrant).",
    )
    p.add_argument(
        "--no-qdrant", action="store_true",
        help="Skip Qdrant upsert (DB + SharePoint only).",
    )
    p.add_argument(
        "--no-embed", action="store_true",
        help="Skip embedding (chunks land in DB without vectors).",
    )
    args = p.parse_args()

    # Stream filter.
    stream_ids = {s[0] for s in _STREAMS}
    if args.vendor:
        unknown = set(args.vendor) - stream_ids
        if unknown:
            print(f"Unknown stream IDs: {unknown}. Available: {sorted(stream_ids)}")
            return 1
        selected = [s for s in _STREAMS if s[0] in args.vendor]
    else:
        selected = list(_STREAMS)

    if args.since_days is not None:
        cutoff = datetime.date.today() - datetime.timedelta(days=args.since_days)
        window_desc = f"last {args.since_days} days (cutoff {cutoff})"
    else:
        cutoff = _cutoff_date(args.recent_years)
        window_desc = f"last {args.recent_years} years (cutoff {cutoff})"

    print("US govt filings ingest")
    print(f"  streams:      {', '.join(s[0] for s in selected)}")
    print(f"  window:       {window_desc}")
    print(f"  limit:        {args.limit if args.limit is not None else 'inf'}")
    print(f"  dry-run:      {args.dry_run}   embed: {not args.no_embed}   "
          f"qdrant: {not args.no_qdrant}")
    print()

    if args.dry_run:
        print("Discovering items for each stream (no bytes fetched)…")
        for stream_id, discover_fn, discover_kwargs, vendor_hint in selected:
            try:
                res = discover_fn(**discover_kwargs, save_raw_html=False)
            except TypeError:
                # Some probes don't accept save_raw_html; retry without.
                res = discover_fn(**discover_kwargs)
            except Exception as exc:
                print(f"  {stream_id:30s}  DISCOVER ERROR: {exc}")
                continue
            items_in_window = [
                it for it in res.items
                if it.publish_date >= cutoff
            ]
            if args.limit is not None:
                items_in_window = items_in_window[:args.limit]
            # Representative doc_type from first item; map to DocType.
            raw_dt = items_in_window[0].doc_type if items_in_window else (
                res.items[0].doc_type if res.items else "?"
            )
            mapped_dt = _DOCTYPE_MAP.get(raw_dt, "report")
            vc = items_in_window[0].vendor_code if items_in_window else vendor_hint
            print(
                f"  {stream_id:30s}  vendor={vc:12s}  doc_type={mapped_dt:8s}  "
                f"items_in_window={len(items_in_window):>3}  "
                f"(total_fetched={len(res.items)})"
            )
        return 0

    # Real ingest — lazy-import the heavy embed/Qdrant stack here (not at
    # module top) so importing this module + running --dry-run stays cheap.
    # QdrantWriter lives in playground (per project-research-mcp-owner-only) —
    # same sanctioned sys.path idiom as scripts/econ/in/govt/ingest_filings.py.
    from imdr.research.filings import FilingInput, ingest_filing_sync  # noqa: PLC0415
    if str(_REPO_ROOT / "playground") not in sys.path:
        sys.path.insert(0, str(_REPO_ROOT / "playground"))
    from research.ingest.qdrant_writer import QdrantWriter  # noqa: E402,PLC0415

    # Modern ODBC driver required for NVARCHAR(MAX) NULL params in
    # research.dim_report.pdf_text / context (same rationale as India).
    settings = get_settings()
    from sqlalchemy import create_engine as _ce  # noqa: PLC0415
    modern_url = (
        f"mssql+pyodbc://@{settings.mssql_host},{settings.mssql_port}"
        f"/{settings.mssql_database}"
        f"?driver=ODBC+Driver+18+for+SQL+Server"
        f"&Trusted_Connection=yes"
        f"&TrustServerCertificate=yes"
    )
    engine = _ce(modern_url, pool_pre_ping=True, echo=False)
    api_keys = _api_keys_from_settings()
    qwriter = None if args.no_qdrant else QdrantWriter.from_env()

    if not args.no_embed and not any(api_keys.values()):
        print("  WARNING: --no-embed not set, but no voyage/google keys "
              "available in settings — embeddings will fail per-call.")

    # HTTP session for document resolution (reuse the same _http session type).
    from _http import make_session, patient_get  # noqa: PLC0415
    http_sess = make_session()

    all_stats: list[IngestStats] = []
    discover_failures: list[str] = []  # streams whose probe never returned items

    for stream_id, discover_fn, discover_kwargs, vendor_hint in selected:
        print(f"\n=== {stream_id} ===")
        try:
            res = discover_fn(**discover_kwargs)
        except Exception as exc:
            print(f"  DISCOVER FAILED: {exc}")
            discover_failures.append(stream_id)
            continue
        if not res.ok:
            print(f"  DISCOVER ERROR: {res.error}")
            discover_failures.append(stream_id)
            continue

        items_in_window = [
            it for it in res.items
            if it.publish_date >= cutoff
        ]
        if args.limit is not None:
            items_in_window = items_in_window[:args.limit]

        raw_dt_example = items_in_window[0].doc_type if items_in_window else "report"
        mapped_dt_example = _DOCTYPE_MAP.get(raw_dt_example, "report")
        vc_example = items_in_window[0].vendor_code if items_in_window else vendor_hint
        stats = IngestStats(
            stream=stream_id,
            vendor_code=vc_example,
            doc_type=mapped_dt_example,
            n_items=len(items_in_window),
        )
        print(f"  {len(items_in_window)} items in window "
              f"(of {len(res.items)} total fetched), vendor={vc_example}, "
              f"doc_type={mapped_dt_example}")

        for i, item in enumerate(items_in_window, 1):
            mapped_doc_type = _DOCTYPE_MAP.get(item.doc_type, "report")

            # Resolve bytes: PDF preferred; fall back to HTML body-text.
            pdf_bytes: bytes | None = None
            body_text: str | None = None
            if item.pdf_url:
                try:
                    r = patient_get(http_sess, item.pdf_url, min_bytes=500)
                    pdf_bytes = r.content
                except Exception as exc:
                    print(f"  [{i:>3}/{len(items_in_window)}] FAIL fetch pdf "
                          f"{item.pdf_url[:80]}: {exc}")
                    stats.failed += 1
                    continue
            else:
                try:
                    r = patient_get(http_sess, item.source_url, min_bytes=200)
                    body_text = _strip_html_body(r.text)
                    if not body_text.strip():
                        print(f"  [{i:>3}/{len(items_in_window)}] FAIL empty body "
                              f"{item.source_url[:80]}")
                        stats.failed += 1
                        continue
                except Exception as exc:
                    print(f"  [{i:>3}/{len(items_in_window)}] FAIL fetch html "
                          f"{item.source_url[:80]}: {exc}")
                    stats.failed += 1
                    continue

            filing = FilingInput(
                vendor_code=item.vendor_code,
                title=item.title[:200],
                publish_date=item.publish_date,
                source_url=item.source_url,
                pdf_bytes=pdf_bytes,
                body_text=body_text,
                doc_type=mapped_doc_type,
                stream=item.stream,
                asset_class="macro",
                country_code="US",
                language="en",
                tags=(("source", "us_fed_corpus_2026_06"),),
            )
            try:
                t0 = time.time()
                result = ingest_filing_sync(
                    filing,
                    engine=engine,
                    api_keys=api_keys,
                    qdrant_writer=qwriter,
                    embed=not args.no_embed,
                )
                dt_s = time.time() - t0
                if result.already_existed:
                    stats.already_existed += 1
                    print(f"  [{i:>3}/{len(items_in_window)}] SKIP (existed)  "
                          f"report_id={result.report_id}  {item.title[:60]}")
                else:
                    stats.ingested += 1
                    stats.chunks_total += result.chunk_count
                    stats.embeddings_total += result.embedding_count
                    print(f"  [{i:>3}/{len(items_in_window)}] OK  "
                          f"report_id={result.report_id}  "
                          f"chunks={result.chunk_count:>3}  "
                          f"emb={result.embedding_count:>3}  "
                          f"{dt_s:>5.1f}s  {item.title[:50]}")
            except Exception as exc:
                stats.failed += 1
                print(f"  [{i:>3}/{len(items_in_window)}] FAIL  "
                      f"{type(exc).__name__}: {str(exc)[:120]}")
        all_stats.append(stats)

    http_sess.close()
    engine.dispose()

    # Summary
    print(f"\n\n=== Summary ===")
    total_in = sum(s.n_items for s in all_stats)
    total_ok = sum(s.ingested for s in all_stats)
    total_skip = sum(s.already_existed for s in all_stats)
    total_fail = sum(s.failed for s in all_stats)
    total_chunks = sum(s.chunks_total for s in all_stats)
    total_emb = sum(s.embeddings_total for s in all_stats)
    print(f"  {total_ok} ingested, {total_skip} skipped (already in DB), "
          f"{total_fail} failed (of {total_in} total)")
    print(f"  {total_chunks:,} chunks  /  {total_emb:,} embeddings")
    if discover_failures:
        print(f"  !! {len(discover_failures)} of {len(selected)} stream(s) "
              f"FAILED DISCOVERY (no items): {', '.join(discover_failures)}")
    print(f"\n  per-stream:")
    for s in all_stats:
        print(f"    {s.stream:30s}  {s.ingested:>3d} ingested, "
              f"{s.already_existed:>3d} skip, {s.failed:>3d} fail   "
              f"chunks={s.chunks_total:>4d} emb={s.embeddings_total:>4d}")
    for sid in discover_failures:
        print(f"    {sid:30s}  DISCOVERY FAILED")

    return _compute_rc(total_ok, total_skip, total_fail, len(discover_failures))


if __name__ == "__main__":
    sys.exit(main())
