"""One-off: backfill BoK / FSC / FSS / MOTIR historical filings.

The daily orchestrator (``ingest_filings.py``) pulls a small page count
per agency (e.g. pages=2 for BoK = 20 items). Sufficient for steady
state, but it means each agency only has 2-4 months of history in
``research.dim_report``. This script does a one-off deep-history pull
per vendor:

  * call the same per-agency ``discover(pages=N)`` the daily uses but
    with a large N, so we walk back to the API cap;
  * dedupe against the same per-vendor ``seen.json`` the daily
    maintains -- so items already ingested are skipped, and successful
    new items are written into ``seen.json`` and won't be re-tried
    tomorrow;
  * push each new item through ``imdr.research.filings.ingest_filing``
    -- same code path the daily uses, so a backfilled filing is
    indistinguishable from a daily-ingested one.

Probed depth (2026-06-11, playground/econ/kr_govt_docs/probe_backfill_depth.py):

    vendor  pages-needed  items-reachable  earliest      already-in-db
    motir   pages=20      ~200             2025-12-11    8
    fss     pages=25      ~250             2024-04-29    20
    fsc     pages=50      ~500             2022-06-17    20
    bok     pages=500     ~5000            2011-09-08    19 (+ menuNo bug fixed in 9c9d1ae)

Usage:
    # Dry-run discovery (no DB writes) -- print counts per vendor
    python -m scripts.econ.kr.govt.backfill_kr_govt --vendor bok --pages 20 --dry-run

    # Smoke a few real items (DB + Qdrant + SharePoint)
    python -m scripts.econ.kr.govt.backfill_kr_govt --vendor motir --pages 20 --limit 5

    # Skip embeddings (DB rows + SharePoint only, no Qdrant) for cheap iteration
    python -m scripts.econ.kr.govt.backfill_kr_govt --vendor fss --pages 25 --no-embed

    # Full backfill -- one vendor at a time
    python -m scripts.econ.kr.govt.backfill_kr_govt --vendor motir --pages 20
    python -m scripts.econ.kr.govt.backfill_kr_govt --vendor fss   --pages 25
    python -m scripts.econ.kr.govt.backfill_kr_govt --vendor fsc   --pages 50
    python -m scripts.econ.kr.govt.backfill_kr_govt --vendor bok   --pages 500

This is a one-off; safe to delete once all four vendors are backfilled.
"""
from __future__ import annotations

import argparse
import asyncio
import io
import sys
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent))
from _models import (  # noqa: E402
    FilingItem,
    dedup_key,
    load_seen,
    save_seen,
)

# Per-vendor discover() entry. Each accepts pages=N.
import fetch_bok       # noqa: E402
import fetch_fsc       # noqa: E402
import fetch_fss       # noqa: E402
import fetch_motir     # noqa: E402

import resolvers as _r  # noqa: E402

_DISCOVER = {
    "bok":   fetch_bok.discover,
    "fsc":   fetch_fsc.discover,
    "fss":   fetch_fss.discover,
    "motir": fetch_motir.discover,
}

_VENDOR_DISPLAY = {
    "bok":   "Bank of Korea",
    "fsc":   "Financial Services Commission (Korea)",
    "fss":   "Financial Supervisory Service (Korea)",
    "motir": "Ministry of Trade, Industry and Resources (Korea)",
}


def _discover(vendor: str, pages: int) -> list[FilingItem]:
    t0 = time.monotonic()
    res = _DISCOVER[vendor](pages=pages)
    elapsed = time.monotonic() - t0
    if not res.ok:
        print(f"  ERR discover: {res.error}")
        return []
    print(
        f"  discover ok: fetched={len(res.items)} items in {elapsed:.1f}s"
        f"  note={res.note or '-'}"
    )
    return res.items


def _filter_new(vendor: str, items: list[FilingItem]) -> list[FilingItem]:
    """Drop items whose dedup_key is already in any vendor's seen.json.

    seen.json is loaded *aggregated across vendors* by load_seen() —
    same as the daily uses — so a vendor X item already known to
    vendor Y won't re-ingest. (Unlikely but defensive.)
    """
    seen = load_seen()
    new = [it for it in items if dedup_key(it) not in seen]
    print(f"  seen.json has {len(seen)} known keys; new this run: {len(new)}")
    return new


async def _ingest_loop(
    vendor: str,
    new_items: list[FilingItem],
    *,
    embed: bool,
    limit: int | None,
) -> dict:
    """Mirrors ingest_filings._ingest_new_items but for a single vendor +
    no orchestrator context. Returns counters."""
    # Lazy imports — heavy modules
    from sqlalchemy import create_engine  # noqa: PLC0415
    _playground = Path(__file__).resolve().parents[4] / "playground"
    if str(_playground) not in sys.path:
        sys.path.insert(0, str(_playground))
    from imdr.config.settings import get_settings  # noqa: PLC0415
    from imdr.research.filings import FilingInput, ingest_filing  # noqa: PLC0415
    from research.ingest.qdrant_writer import QdrantWriter  # noqa: PLC0415

    s = get_settings()
    url = (
        f"mssql+pyodbc://@{s.mssql_host}:{s.mssql_port}/{s.mssql_database}"
        "?driver=ODBC+Driver+18+for+SQL+Server"
        "&Trusted_Connection=yes&Encrypt=yes&TrustServerCertificate=yes"
        "&LoginTimeout=60"
    )
    engine = create_engine(
        url, pool_size=2, max_overflow=2, pool_pre_ping=True,
        echo=False, fast_executemany=True,
    )
    qw = QdrantWriter.from_env() if embed else None
    api_keys = {"voyage": s.voyage_key, "google": s.gemini_key}

    counters = {"ingested": 0, "dedup": 0, "resolve_fail": 0, "ingest_fail": 0}
    success: list[FilingItem] = []

    capped = new_items if limit is None else new_items[:limit]
    print(f"  ingesting {len(capped)} item(s)  (embed={'yes' if embed else 'no'})")

    for i, item in enumerate(capped, start=1):
        try:
            kind, body = _r.resolve(item)
        except Exception as exc:  # noqa: BLE001
            counters["resolve_fail"] += 1
            print(f"    [{i:4}/{len(capped)}] resolve-fail  {item.publish_date}  {item.title[:60]!r}  {type(exc).__name__}: {str(exc)[:80]}")
            continue
        filing = FilingInput(
            vendor_code=item.vendor_code,
            title=item.title,
            publish_date=item.publish_date,
            source_url=item.source_url,
            pdf_bytes=body if kind == "pdf" else None,
            body_text=body if kind == "body" else None,
            doc_type=item.doc_type,
            stream=item.stream,
            asset_class="macro",
            region="ASIA-EM",
            country_code="KR",
            authors=_VENDOR_DISPLAY[vendor],
            language="en",
            tags=tuple(item.extras.get("tags", ())) if item.extras else (),
        )
        try:
            res = await ingest_filing(
                filing, engine=engine, api_keys=api_keys,
                qdrant_writer=qw, embed=embed,
            )
        except Exception as exc:  # noqa: BLE001
            counters["ingest_fail"] += 1
            print(f"    [{i:4}/{len(capped)}] ingest-fail   {item.publish_date}  {item.title[:60]!r}  {type(exc).__name__}: {str(exc)[:120]}")
            continue
        if res.already_existed:
            counters["dedup"] += 1
            print(f"    [{i:4}/{len(capped)}] dedup         {item.publish_date}  report_id={res.report_id}  {item.title[:55]!r}")
        else:
            counters["ingested"] += 1
            print(f"    [{i:4}/{len(capped)}] ingested      {item.publish_date}  report_id={res.report_id}  chunks={res.chunk_count}  {item.title[:50]!r}")
        success.append(item)

    engine.dispose()

    # Persist seen.json — only successfully ingested + dedup items get
    # added (resolve/ingest failures stay "new" for next run).
    if success:
        seen = load_seen()
        seen.update({dedup_key(it) for it in success})
        save_seen(seen)
        print(f"  seen.json updated: +{len(success)} keys (total {len(seen)})")

    return counters


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--vendor", required=True, choices=sorted(_DISCOVER.keys()),
                    help="which agency to backfill")
    ap.add_argument("--pages", type=int, required=True,
                    help="page-count to walk (10 items/page; see probe results in docstring)")
    ap.add_argument("--dry-run", action="store_true",
                    help="discover + filter only; no DB / SharePoint / Qdrant writes")
    ap.add_argument("--no-embed", action="store_true",
                    help="skip Qdrant embeddings (DB rows + SharePoint still happen)")
    ap.add_argument("--limit", type=int, default=None,
                    help="cap ingest at N new items (smoke / staged backfill)")
    args = ap.parse_args(argv)

    print(f"=== backfill {args.vendor} (pages={args.pages}) ===")
    items = _discover(args.vendor, args.pages)
    if not items:
        print("Nothing discovered; bailing.")
        return 1

    new_items = _filter_new(args.vendor, items)
    if not new_items:
        print("All items already in seen.json; nothing to ingest.")
        return 0

    if new_items:
        dates = sorted({it.publish_date for it in new_items})
        print(f"  date span (new):  {dates[0]} -> {dates[-1]}  ({len(dates)} unique days)")
        # Sample
        print("  sample (newest 3 + oldest 3):")
        for it in (new_items[:3] + new_items[-3:]):
            print(f"    {it.publish_date}  [{it.doc_type:8}]  {it.title[:80]}")

    if args.dry_run:
        print("\nDRY RUN — no DB / SharePoint / Qdrant writes.")
        return 0

    counters = asyncio.run(_ingest_loop(
        args.vendor, new_items,
        embed=not args.no_embed,
        limit=args.limit,
    ))
    print(f"\n=== {args.vendor} done ===")
    print(f"  ingested     : {counters['ingested']}")
    print(f"  dedup        : {counters['dedup']}")
    print(f"  resolve_fail : {counters['resolve_fail']}")
    print(f"  ingest_fail  : {counters['ingest_fail']}")
    return 0 if (counters["resolve_fail"] + counters["ingest_fail"]) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
