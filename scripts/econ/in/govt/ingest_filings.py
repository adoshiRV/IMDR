"""India official filings ingest — RBI / MOSPI / PPAC / Budget / Economic Survey.

Walks `data/econ/in/govt/{folder}/.../*.pdf` (populated by
`scripts/econ/in/govt/daily_pull.py`) and calls
:func:`imdr.research.filings.ingest_filing_sync` for each.

Each PDF lands in:
  - `research.dim_report`  (metadata, deduped on content_hash)
  - SharePoint mirror      (`IMDR/research/{vendor_code}/...`)
  - `research.fact_chunk`  (text chunks)
  - Qdrant collection      (vectors w/ vendor_category in payload)

Folder → (vendor_code, doc_type, country_code) mapping is the only
India-specific knowledge encoded here. Everything else flows through
the shared filings ingest stack.

By default only date-folders within the last ``--since-days`` days (default 2)
are walked. This avoids re-scanning the full multi-year corpus on every daily
run. Pass ``--all`` to restore the full rglob (for manual backfills).

Run:
    python -m scripts.econ.in.govt.ingest_filings                       # all folders, last 2 days
    python -m scripts.econ.in.govt.ingest_filings --since-days 7        # last week
    python -m scripts.econ.in.govt.ingest_filings --all                 # full corpus (backfill)
    python -m scripts.econ.in.govt.ingest_filings --vendor rbi_press    # one folder
    python -m scripts.econ.in.govt.ingest_filings --limit 5             # smoke test
    python -m scripts.econ.in.govt.ingest_filings --dry-run             # plan only
    python -m scripts.econ.in.govt.ingest_filings --no-qdrant           # DB + SP only
    python -m scripts.econ.in.govt.ingest_filings --no-embed            # no vectors

Wired into ``scripts/econ/in/in_daily.py`` (the per-country daily
orchestrator), which is itself registered in
``scripts/imdr_daily.py:PIPELINES``.
"""

from __future__ import annotations

import argparse
import datetime
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from imdr.config.settings import get_settings

# Heavy ingest deps (imdr.research.filings + the playground QdrantWriter, which
# pulls the tiktoken/embed stack) are lazy-imported inside main() so the module
# imports cheaply and --dry-run doesn't need them. Mirrors the deferred-import
# idiom in scripts/econ/kr/govt/ingest_filings.py.
_REPO_ROOT = Path(__file__).resolve().parents[4]   # scripts/econ/in/govt/<file>
DATA_ROOT = _REPO_ROOT / "data" / "econ" / "in" / "govt"


# Folder → (vendor_code, doc_type, country_code, stream)
# doc_type ∈ {"decision","minutes","outlook","report","speech","release","review"}
# per the DocType literal in src/imdr/research/filings.py
_FOLDER_MAP: dict[str, tuple[str, str, str, str]] = {
    "rbi_press":       ("rbi",    "release",  "IN", "monetary_policy"),
    "rbi_mpc_minutes": ("rbi",    "minutes",  "IN", "monetary_policy"),
    "rbi_mpr":         ("rbi",    "report",   "IN", "monetary_policy"),
    "rbi_fsr":         ("rbi",    "report",   "IN", "financial_stability"),
    "rbi_annual":      ("rbi",    "report",   "IN", "annual_report"),
    "rbi_bulletin":    ("rbi",    "report",   "IN", "bulletin"),
    "rbi_notifs":      ("rbi",    "release",  "IN", "regulatory"),
    "rbi_speeches":    ("rbi",    "speech",   "IN", "speech"),
    "mospi_cpi":       ("mospi",  "release",  "IN", "cpi"),
    "mospi_iip":       ("mospi",  "release",  "IN", "iip"),
    "mospi_nas_gdp":   ("mospi",  "release",  "IN", "gdp"),
    "mospi_plfs":      ("mospi",  "release",  "IN", "plfs"),
    "ppac":            ("ppac",   "report",   "IN", "petroleum"),
    "budget":          ("mof_in", "report",   "IN", "fiscal"),
    "econ_survey":     ("dea_in", "report",   "IN", "economic_survey"),
    # cga skipped — no PDFs harvested (XLSM is the data source)
}


@dataclass(slots=True)
class IngestStats:
    folder: str
    vendor_code: str
    n_pdfs: int = 0
    ingested: int = 0
    already_existed: int = 0
    failed: int = 0
    chunks_total: int = 0
    embeddings_total: int = 0


def _recent_date_folders(vendor_dir: Path, since: datetime.date) -> list[Path]:
    """Return leaf date-folders under vendor_dir whose date >= since.

    Layout: {vendor_dir}/{YYYY}/{MM}/{DD}/
    Only yields folders that exist. Returns empty list when vendor_dir
    doesn't exist or has no matching date-subfolders.
    """
    folders: list[Path] = []
    if not vendor_dir.exists():
        return folders
    for year_dir in vendor_dir.iterdir():
        if not year_dir.is_dir() or not year_dir.name.isdigit():
            continue
        for month_dir in year_dir.iterdir():
            if not month_dir.is_dir() or not month_dir.name.isdigit():
                continue
            for day_dir in month_dir.iterdir():
                if not day_dir.is_dir() or not day_dir.name.isdigit():
                    continue
                try:
                    folder_date = datetime.date(
                        int(year_dir.name),
                        int(month_dir.name),
                        int(day_dir.name),
                    )
                except ValueError:
                    continue
                if folder_date >= since:
                    folders.append(day_dir)
    return folders


def _iter_pdfs(
    folder: str,
    limit: int | None = None,
    *,
    since_days: int | None = 2,
    all_corpus: bool = False,
) -> Iterable[Path]:
    """Yield PDFs for a given folder name.

    When ``all_corpus=True`` (backfill mode), walks the full tree.
    Otherwise restricts to date-folders within the last ``since_days`` days.
    """
    base = DATA_ROOT / folder
    if not base.exists():
        return

    if all_corpus or since_days is None:
        pdfs = sorted(base.rglob("*.[pP][dD][fF]"))
    else:
        cutoff = datetime.date.today() - datetime.timedelta(days=since_days)
        recent = _recent_date_folders(base, cutoff)
        pdfs = []
        for day_dir in recent:
            pdfs.extend(day_dir.glob("*.[pP][dD][fF]"))
        pdfs = sorted(pdfs)

    if limit is not None:
        pdfs = pdfs[:limit]
    yield from pdfs


def _title_from_filename(path: Path) -> str:
    """Build a human-readable title from the saved filename.

    Underscores → spaces; trailing `_{8-char hash}` from the corpus
    saver is stripped so duplicate downloads of the same doc fold
    together at SharePoint path level too.
    """
    stem = path.stem
    # strip our content_hash suffix if present: foo_bar_a1b2c3d4 -> foo_bar
    stem = re.sub(r"_[0-9a-f]{8}$", "", stem, flags=re.I)
    return stem.replace("_", " ").strip() or path.name


def _publish_date_from_path(path: Path) -> datetime.date:
    """Folder layout is data/econ/in/govt/{vendor}/{YYYY}/{MM}/{DD}/file.pdf.
    Treat that as the publish date (fetch-date proxy). Caller's manifests
    have the true publish date; downstream filtering can override later
    via direct DB update if needed.
    """
    parts = path.parts
    # find the 3 numeric components in path
    for i, p in enumerate(parts):
        if (p.isdigit() and len(p) == 4
                and i + 2 < len(parts)
                and parts[i + 1].isdigit() and parts[i + 2].isdigit()):
            try:
                return datetime.date(int(p), int(parts[i + 1]), int(parts[i + 2]))
            except ValueError:
                continue
    return datetime.date.today()


def _api_keys_from_settings() -> dict[str, str]:
    s = get_settings()
    return {
        "voyage": s.voyage_key or "",
        "google": s.gemini_key or "",
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--vendor", nargs="*",
                   help="Folder names to ingest (e.g. rbi_press mospi_cpi). "
                        "Default: all folders with a known mapping.")
    p.add_argument("--limit", type=int, default=None,
                   help="Max PDFs per folder (for smoke tests)")
    p.add_argument("--since-days", type=int, default=2,
                   help="Only walk date-folders within the last N days (default 2). "
                        "Ignored when --all is set.")
    p.add_argument("--all", dest="all_corpus", action="store_true",
                   help="Walk the full corpus regardless of date (manual backfill).")
    p.add_argument("--dry-run", action="store_true",
                   help="Plan only — list what would be ingested")
    p.add_argument("--no-qdrant", action="store_true",
                   help="Skip Qdrant upsert (DB + SharePoint only)")
    p.add_argument("--no-embed", action="store_true",
                   help="Skip embedding (chunks land in DB without vectors)")
    args = p.parse_args()

    folders = args.vendor or list(_FOLDER_MAP.keys())
    folders = [f for f in folders if f in _FOLDER_MAP]
    if not folders:
        print(f"No matching folders. Available: {list(_FOLDER_MAP.keys())}")
        return 1

    scope_desc = "full corpus" if args.all_corpus else f"last {args.since_days} days"
    print(f"India govt filings ingest")
    print(f"  folders: {', '.join(folders)}")
    print(f"  scope:   {scope_desc}")
    print(f"  limit:   {args.limit if args.limit is not None else 'inf'}")
    print(f"  dry-run: {args.dry_run}   embed: {not args.no_embed}   "
          f"qdrant: {not args.no_qdrant}")
    print(f"  data root: {DATA_ROOT}\n")

    if args.dry_run:
        for folder in folders:
            vendor, doc_type, cc, stream = _FOLDER_MAP[folder]
            pdfs = list(_iter_pdfs(
                folder, args.limit,
                since_days=args.since_days,
                all_corpus=args.all_corpus,
            ))
            print(f"  {folder:20s}  vendor={vendor:8s} doc_type={doc_type:8s}  "
                  f"stream={stream:20s}  pdfs={len(pdfs)}")
        return 0

    # Real ingest — lazy-import the heavy embed/Qdrant stack here (not at
    # module top) so importing this module + running --dry-run stays cheap.
    # QdrantWriter lives in playground (per project-research-mcp-owner-only) —
    # same sanctioned sys.path idiom as scripts/econ/kr/govt/ingest_filings.py.
    from imdr.research.filings import FilingInput, ingest_filing_sync  # noqa: PLC0415
    if str(_REPO_ROOT / "playground") not in sys.path:
        sys.path.insert(0, str(_REPO_ROOT / "playground"))
    from research.ingest.qdrant_writer import QdrantWriter  # noqa: E402,PLC0415

    # Real ingest — set up engine + qdrant.
    # NB: the global default `SQL Server` ODBC driver returns HYC00
    # "Optional feature not implemented (SQLBindParameter)" when binding
    # NVARCHAR(MAX) NULL parameters to research.dim_report.pdf_text /
    # context. Switch to "ODBC Driver 18 for SQL Server" (modern) for
    # this ingest path. Other domains (econ.fact_indicator etc.) keep
    # the legacy driver because they don't hit MAX columns.
    settings = get_settings()
    from sqlalchemy import create_engine as _ce
    modern_url = (
        f"mssql+pyodbc://@{settings.mssql_host},{settings.mssql_port}"
        f"/{settings.mssql_database}"
        f"?driver=ODBC+Driver+18+for+SQL+Server"
        f"&Trusted_Connection=yes"
        f"&TrustServerCertificate=yes"
    )
    engine = _ce(
        modern_url,
        pool_pre_ping=True,
        echo=False,
    )
    api_keys = _api_keys_from_settings()
    qwriter = None if args.no_qdrant else QdrantWriter.from_env()

    if not args.no_embed and not any(api_keys.values()):
        print("  WARNING: --no-embed not set, but no voyage/google keys "
              "available in settings — embeddings will fail per-call.")

    all_stats: list[IngestStats] = []
    for folder in folders:
        vendor, doc_type, cc, stream = _FOLDER_MAP[folder]
        stats = IngestStats(folder=folder, vendor_code=vendor)
        pdfs = list(_iter_pdfs(
            folder, args.limit,
            since_days=args.since_days,
            all_corpus=args.all_corpus,
        ))
        stats.n_pdfs = len(pdfs)
        print(f"\n=== {folder} → vendor={vendor} doc_type={doc_type} ({len(pdfs)} PDFs) ===")
        for i, path in enumerate(pdfs, 1):
            title = _title_from_filename(path)
            publish_date = _publish_date_from_path(path)
            try:
                pdf_bytes = path.read_bytes()
            except Exception as e:
                print(f"  [{i:>3}/{len(pdfs)}] FAIL read: {e}")
                stats.failed += 1
                continue

            filing = FilingInput(
                vendor_code=vendor,
                title=title[:200],
                publish_date=publish_date,
                source_url=f"file://{path.as_posix()}",
                pdf_bytes=pdf_bytes,
                doc_type=doc_type,
                stream=stream,
                asset_class="macro",
                country_code=cc,
                language="en",
                tags=(("source", "india_corpus_2026_06_10"),),
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
                    print(f"  [{i:>3}/{len(pdfs)}] SKIP (existed)  "
                          f"report_id={result.report_id}  {title[:60]}")
                else:
                    stats.ingested += 1
                    stats.chunks_total += result.chunk_count
                    stats.embeddings_total += result.embedding_count
                    print(f"  [{i:>3}/{len(pdfs)}] OK  "
                          f"report_id={result.report_id}  "
                          f"chunks={result.chunk_count:>3}  "
                          f"emb={result.embedding_count:>3}  "
                          f"{dt_s:>5.1f}s  {title[:50]}")
            except Exception as e:
                stats.failed += 1
                print(f"  [{i:>3}/{len(pdfs)}] FAIL  {type(e).__name__}: {str(e)[:120]}")
        all_stats.append(stats)

    # Summary
    print(f"\n\n=== Summary ===")
    total_in = sum(s.n_pdfs for s in all_stats)
    total_ok = sum(s.ingested for s in all_stats)
    total_skip = sum(s.already_existed for s in all_stats)
    total_fail = sum(s.failed for s in all_stats)
    total_chunks = sum(s.chunks_total for s in all_stats)
    total_emb = sum(s.embeddings_total for s in all_stats)
    print(f"  {total_ok} ingested, {total_skip} skipped (already in DB), "
          f"{total_fail} failed (of {total_in} total)")
    print(f"  {total_chunks:,} chunks  /  {total_emb:,} embeddings")
    print(f"\n  per-folder:")
    for s in all_stats:
        print(f"    {s.folder:18s}  {s.ingested:>3d} ingested, "
              f"{s.already_existed:>3d} skip, {s.failed:>3d} fail   "
              f"chunks={s.chunks_total:>4d} emb={s.embeddings_total:>4d}")

    return 0 if total_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
