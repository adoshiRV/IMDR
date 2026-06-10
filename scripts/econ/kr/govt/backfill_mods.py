"""One-off: re-ingest the 10 orphan MoDS (KOSTAT) PDFs through filings.py.

Background: the existing ``playground/econ/mods/fetch.py`` downloaded 10
press-release PDFs to SharePoint under the date-first canonical path
(``{YYYY}/{MM}/{DD}/econ/kr/mods/...``) but never wrote them to
``research.dim_report`` — they're orphans on the file mirror, invisible
to Mycroft/Lois.

This script walks the existing files, derives metadata, deletes each PDF
in place, then re-ingests via ``filings.ingest_filing()`` which:
  * re-uploads to the canonical path (same path, same content_hash);
  * writes ``research.dim_report`` + ``research.fact_chunk`` rows;
  * pushes chunks to Qdrant with ``vendor_category='official_statistics'``;
  * applies the same tag taxonomy as the live govt-filings stream.

Title derivation: filenames look like
``mods_{list_no}_{slug-of-title}.pdf``. The slug is hyphen-separated
title text. We reverse the slug to title-case (preserving small words
lowercase) for `dim_report.title` — close to the original release name.
The manifest parquet files under ``playground/econ/mods/manifests/``
have mostly-broken titles (parser bug at ingest time) so they're not
the source.

Idempotent: subsequent runs detect that the SP file is gone + the
content_hash is already in dim_report → short-circuit dedup.

Usage:
    python -m scripts.econ.kr.govt.backfill_mods             # full run
    python -m scripts.econ.kr.govt.backfill_mods --dry-run   # plan only
    python -m scripts.econ.kr.govt.backfill_mods --no-embed  # skip Qdrant
"""
from __future__ import annotations

import argparse
import asyncio
import io
import re
import sys
from datetime import date
from pathlib import Path
from typing import Iterator

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from sqlalchemy import create_engine  # noqa: E402

_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / "src"))
sys.path.insert(0, str(_REPO / "playground"))

from imdr.config.settings import get_settings  # noqa: E402
from imdr.research.filings import FilingInput, ingest_filing  # noqa: E402
from research.ingest.qdrant_writer import QdrantWriter  # noqa: E402


LOCAL_ROOT = Path(
    r"C:\Users\adoshi\OneDrive - RV Capital Management Private Ltd"
    r"\Trade Knowledge Core - IMDR"
)

# Filename pattern from the legacy mods/fetch.py:
#     mods_{list_no}_{slug-of-title}.pdf
_FILENAME_RE = re.compile(r"^mods_(\d+)_(.+)\.pdf$")

# Small-words list — kept lower-case during slug → title-case conversion.
_SMALL_WORDS = {
    "a", "an", "and", "as", "at", "by", "for", "from", "in", "of", "on",
    "or", "the", "to", "with",
}


def _slug_to_title(slug: str) -> str:
    """Reverse a hyphen-separated lowercase slug to title-case.

    `consumer-price-index-in-may-2026` → `Consumer Price Index in May 2026`
    """
    parts = [p for p in slug.split("-") if p]
    out: list[str] = []
    for i, w in enumerate(parts):
        if i > 0 and w in _SMALL_WORDS:
            out.append(w)
        else:
            out.append(w.capitalize() if not w.isdigit() else w)
    return " ".join(out)


def iter_orphan_pdfs() -> Iterator[tuple[Path, str, str, date]]:
    """Yield (file_path, list_no, title, publish_date) for each orphan mods PDF."""
    for pdf in LOCAL_ROOT.rglob("econ/kr/mods/*.pdf"):
        m = _FILENAME_RE.match(pdf.name)
        if not m:
            print(f"  SKIP filename {pdf.name!r} doesn't match mods_{{list_no}}_{{slug}}.pdf")
            continue
        list_no, slug = m.group(1), m.group(2)
        # publish_date from path: .../{YYYY}/{MM}/{DD}/econ/kr/mods/...
        try:
            yyyy = pdf.parents[5].name  # mods/ → kr/ → econ/ → {DD}/ → {MM}/ → {YYYY}/
            mm = pdf.parents[4].name
            dd = pdf.parents[3].name
            pdate = date(int(yyyy), int(mm), int(dd))
        except (ValueError, IndexError) as exc:
            print(f"  SKIP {pdf.name}: can't derive date — {exc}")
            continue
        title = _slug_to_title(slug)
        yield pdf, list_no, title, pdate


async def _ingest_one(
    pdf_path: Path,
    list_no: str,
    title: str,
    publish_date: date,
    *,
    engine,
    qdrant_writer: QdrantWriter | None,
    api_keys: dict[str, str],
    embed: bool,
    dry_run: bool,
) -> tuple[bool, str]:
    """Read PDF bytes, delete source file, call ingest_filing → re-create + ingest."""
    pdf_bytes = pdf_path.read_bytes()
    src = pdf_path.relative_to(LOCAL_ROOT).as_posix()
    if dry_run:
        return True, f"would ingest list_no={list_no} title={title!r} from {src}"
    # Delete the source file BEFORE ingest_filing.upload_pdf re-writes the
    # canonical path. Avoids PdfPathCollisionError if the new slug happens
    # to match the old one (unlikely with hash8 suffix but defensive).
    pdf_path.unlink()
    filing = FilingInput(
        vendor_code="mods",
        title=title,
        publish_date=publish_date,
        # MoDS doesn't expose a clean detail URL per release; use the
        # list_no as a stable identifier embedded in a synthetic URL.
        source_url=f"https://mods.go.kr/boardView.es?list_no={list_no}",
        pdf_bytes=pdf_bytes,
        doc_type="release",
        stream="mods_prices",
        asset_class="macro",
        region="ASIA-EM",
        country_code="KR",
        authors="Korea Ministry of Data & Statistics (KOSTAT)",
        language="en",
        tags=(("list_no", list_no),),
    )
    res = await ingest_filing(
        filing,
        engine=engine,
        api_keys=api_keys,
        qdrant_writer=qdrant_writer,
        embed=embed,
    )
    if res.already_existed:
        return True, f"DEDUP existing report_id={res.report_id}"
    return True, (
        f"OK report_id={res.report_id} chunks={res.chunk_count} "
        f"embed={res.embedding_count} sp={res.sharepoint_path!r}"
    )


def _build_engine():
    s = get_settings()
    url = (
        f"mssql+pyodbc://@{s.mssql_host}:{s.mssql_port}/{s.mssql_database}"
        "?driver=ODBC+Driver+18+for+SQL+Server"
        "&Trusted_Connection=yes&Encrypt=yes&TrustServerCertificate=yes"
        "&LoginTimeout=60"
    )
    return create_engine(url, pool_pre_ping=True, fast_executemany=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="show plan, no writes")
    ap.add_argument("--no-embed", action="store_true", help="skip embeddings + Qdrant")
    args = ap.parse_args(argv)

    plan = list(iter_orphan_pdfs())
    print(f"Found {len(plan)} orphan mods PDFs to backfill\n")
    for pdf, list_no, title, pdate in plan:
        print(f"  list_no={list_no}  date={pdate}  title={title}")
    print()
    if args.dry_run:
        print("DRY RUN — no DB writes, no file deletes")
        return 0
    if not plan:
        print("Nothing to do.")
        return 0

    engine = _build_engine()
    qw = QdrantWriter.from_env() if not args.no_embed else None
    s = get_settings()
    api_keys = {"voyage": s.voyage_key, "google": s.gemini_key}

    async def _run_all():
        n_ok = n_fail = 0
        for pdf, list_no, title, pdate in plan:
            try:
                ok, msg = await _ingest_one(
                    pdf, list_no, title, pdate,
                    engine=engine, qdrant_writer=qw,
                    api_keys=api_keys, embed=not args.no_embed,
                    dry_run=False,
                )
                print(f"  [{list_no}] {msg}")
                n_ok += 1 if ok else 0
                n_fail += 0 if ok else 1
            except Exception as exc:  # noqa: BLE001
                print(f"  [{list_no}] ERROR {type(exc).__name__}: {str(exc)[:160]}")
                n_fail += 1
        return n_ok, n_fail

    n_ok, n_fail = asyncio.run(_run_all())
    print(f"\nDONE — {n_ok} ok, {n_fail} failed")
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
