"""Korea government policy filings — daily ingest orchestrator.

Runs every fetcher under ``scripts/econ/kr/govt/`` in sequence, dedups
against the rolling ``data/seen.json``, writes a per-day snapshot of
NEW items, prints a summary table, and (when ``--ingest`` is passed)
pushes each new filing through ``imdr.research.filings.ingest_filing``
to land in ``research.dim_report`` + ``research.fact_chunk`` + Qdrant +
SharePoint.

Wired into ``scripts/econ/kr/kr_daily.py`` (the per-country daily
orchestrator), which is itself registered in
``scripts/imdr_daily.py:PIPELINES``.

Direct usage:
    python -m scripts.econ.kr.govt.ingest_filings              # discover + snapshot + summary
    python -m scripts.econ.kr.govt.ingest_filings --dry-run    # no seen.json / snapshot write
    python -m scripts.econ.kr.govt.ingest_filings --reset      # wipe seen.json (re-discover everything)
    python -m scripts.econ.kr.govt.ingest_filings --ingest     # discover + resolve + ingest_filing
    python -m scripts.econ.kr.govt.ingest_filings --ingest --no-embed
                                                               # skip embeddings (cheap iteration)
    python -m scripts.econ.kr.govt.ingest_filings --ingest --limit 3
                                                               # ingest at most N new items (smoke)

Runtime state (per-machine, NOT committed):
    data/snapshots/{YYYY-MM-DD}.json   — new items discovered that day
    data/seen.json                     — rolling source_url set (dedup)
    data/_last_run.log                 — most recent run output

The seen.json is only updated for items that successfully resolved +
ingested, so transient failures are retryable on the next run.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _models import (  # noqa: E402
    SEEN_FILE,
    FetchResult,
    FilingItem,
    dedup_key,
    load_seen,
    save_seen,
)

import fetch_bok       # noqa: E402
import fetch_fsc       # noqa: E402
import fetch_fss       # noqa: E402
import fetch_kcs       # noqa: E402
import fetch_kdi       # noqa: E402
import fetch_moef      # noqa: E402
import fetch_motir     # noqa: E402

DATA_DIR = Path(__file__).parent / "data"
SNAPSHOTS_DIR = DATA_DIR / "snapshots"
LAST_RUN_LOG = DATA_DIR / "_last_run.log"

# Fetcher order: lowest-complexity first (RSS) so a failed BoK/FSC doesn't
# delay the cheap fetches. Within each tier, alphabetic.
FETCHERS = [
    ("moef",  fetch_moef.discover,  {}),
    ("fss",   fetch_fss.discover,   {"pages": 2}),
    ("kcs",   fetch_kcs.discover,   {}),
    ("kdi",   fetch_kdi.discover,   {}),
    ("fsc",   fetch_fsc.discover,   {"pages": 1}),
    ("motir", fetch_motir.discover, {"pages": 1}),
    ("bok",   fetch_bok.discover,   {"pages": 2}),
]


def _print_and_log(msg: str, log_lines: list[str]) -> None:
    print(msg)
    log_lines.append(msg)


def _summarise_new_items(items: list[FilingItem]) -> str:
    """One-line description of up to 2 items for the daily summary."""
    if not items:
        return ""
    titles = [it.title[:60] for it in items[:2]]
    extra = f" +{len(items) - 2} more" if len(items) > 2 else ""
    return ", ".join(titles) + extra


def _ingest_new_items(
    new_items_by_vendor: dict[str, list[FilingItem]],
    *,
    embed: bool,
    limit: int | None,
    log: list[str],
) -> dict[str, int]:
    """Resolve + ingest each new item via filings.ingest_filing.

    Returns ``{vendor_code: success_count}``. Items that fail resolve
    or ingest are NOT added to seen.json (caller retries next run).
    """
    # Lazy imports so a discovery-only run doesn't load the heavy
    # SQLAlchemy + Qdrant + Voyage/Gemini stack. ``imdr.*`` resolves
    # via the installed package. ``research.ingest.*`` lives at
    # ``playground/research/ingest/`` — explicitly insert the
    # playground root here so we don't depend on the import-order
    # side-effect from ``imdr.research.filings`` (which also inserts
    # it but is fragile to refactor).
    import asyncio  # noqa: PLC0415
    from sqlalchemy import create_engine  # noqa: PLC0415
    _playground = Path(__file__).resolve().parents[4] / "playground"
    if str(_playground) not in sys.path:
        sys.path.insert(0, str(_playground))
    from imdr.config.settings import get_settings  # noqa: PLC0415
    from imdr.research.filings import FilingInput, ingest_filing  # noqa: PLC0415
    from research.ingest.qdrant_writer import QdrantWriter  # noqa: PLC0415
    from scripts.econ.kr.govt import resolvers as _r  # noqa: PLC0415

    # Engine — mirrors the research-ingest convention (ODBC Driver 18,
    # fast_executemany, pool_pre_ping). The legacy "SQL Server" driver
    # from .env can't bind BINARY / NVARCHAR(MAX) for fact_chunk writes.
    _s = get_settings()
    _url = (
        f"mssql+pyodbc://@{_s.mssql_host}:{_s.mssql_port}/{_s.mssql_database}"
        "?driver=ODBC+Driver+18+for+SQL+Server"
        "&Trusted_Connection=yes&Encrypt=yes&TrustServerCertificate=yes"
        "&LoginTimeout=60"
    )
    engine = create_engine(
        _url, pool_size=2, max_overflow=2, pool_pre_ping=True,
        echo=False, fast_executemany=True,
    )
    qdrant_writer = QdrantWriter.from_env()
    # Match ingest_today.py: read from pydantic Settings (which load .env).
    api_keys = {"voyage": _s.voyage_key, "google": _s.gemini_key}

    success: dict[str, list[FilingItem]] = {v: [] for v in new_items_by_vendor}
    n_ingested = 0
    n_failed = 0

    async def _one(vendor: str, item: FilingItem) -> bool:
        nonlocal n_ingested, n_failed
        try:
            kind, body = _r.resolve(item)
        except Exception as exc:  # noqa: BLE001
            log.append(f"  [resolve-fail] {vendor:6} {item.title[:60]!r}: {type(exc).__name__}: {str(exc)[:100]}")
            n_failed += 1
            return False
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
            authors=_vendor_display_name(vendor),
            language="en",
            tags=tuple(item.extras.get("tags", ())) if item.extras else (),
        )
        try:
            result = await ingest_filing(
                filing,
                engine=engine,
                api_keys=api_keys,
                qdrant_writer=qdrant_writer,
                embed=embed,
            )
        except Exception as exc:  # noqa: BLE001
            log.append(f"  [ingest-fail] {vendor:6} {item.title[:60]!r}: {type(exc).__name__}: {str(exc)[:140]}")
            n_failed += 1
            return False
        if result.already_existed:
            log.append(f"  [dedup]       {vendor:6} report_id={result.report_id} {item.title[:60]!r}")
        else:
            n_ingested += 1
            log.append(
                f"  [ingested]    {vendor:6} report_id={result.report_id} "
                f"chunks={result.chunk_count} embed={result.embedding_count} "
                f"sp={'yes' if result.sharepoint_path else 'no'} "
                f"qdrant={'yes' if result.qdrant_collection else 'no'} "
                f"{item.title[:55]!r}"
            )
        return True

    async def _run_all() -> None:
        # Round-robin across vendors so a low --limit covers as many
        # agencies as possible (smoke test wants 1-of-each, not 10 MOEFs).
        n_done = 0
        cursors: dict[str, int] = {v: 0 for v in new_items_by_vendor}
        while True:
            progressed = False
            for vendor in list(new_items_by_vendor.keys()):
                if limit is not None and n_done >= limit:
                    return
                idx = cursors[vendor]
                items = new_items_by_vendor[vendor]
                if idx >= len(items):
                    continue
                item = items[idx]
                cursors[vendor] = idx + 1
                progressed = True
                ok = await _one(vendor, item)
                if ok:
                    success[vendor].append(item)
                n_done += 1
            if not progressed:
                return

    try:
        asyncio.run(_run_all())
    finally:
        # Release the pool — this function may be re-entered on a same-day
        # retry, and the orchestrator subprocess may run other pipelines
        # after us. Defensive cleanup matches the project's _engine() +
        # dispose() convention.
        engine.dispose()

    counts = {v: len(s) for v, s in success.items()}
    _print_and_log(f"\n  INGEST: {n_ingested} new, {n_failed} failed (limit={limit})", log)
    # Pass back the items that successfully resolved+ingested so caller
    # updates seen.json only for those.
    new_items_by_vendor.clear()
    new_items_by_vendor.update(success)
    return counts


_VENDOR_DISPLAY = {
    "bok": "Bank of Korea",
    "moef": "Ministry of Economy & Finance (Korea)",
    "motir": "Ministry of Trade, Industry and Resources (Korea)",
    "fsc": "Financial Services Commission (Korea)",
    "fss": "Financial Supervisory Service (Korea)",
    "kcs": "Korea Customs Service",
    "kdi": "Korea Development Institute",
}


def _vendor_display_name(vendor: str) -> str:
    return _VENDOR_DISPLAY.get(vendor, vendor)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="don't write seen.json or daily snapshot")
    parser.add_argument("--reset", action="store_true",
                        help="wipe seen.json before run (treat everything as new)")
    parser.add_argument("--ingest", action="store_true",
                        help="resolve + ingest new items via filings.py")
    parser.add_argument("--no-embed", action="store_true",
                        help="when --ingest, write chunks without embeddings (no Qdrant)")
    parser.add_argument("--limit", type=int, default=None,
                        help="when --ingest, cap at N new items (smoke-test)")
    args = parser.parse_args(argv)

    run_id = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log: list[str] = []
    _print_and_log(f"=== Korea govt filings daily pull — {run_id} ===", log)

    if args.reset and SEEN_FILE.exists() and not args.dry_run:
        SEEN_FILE.unlink()
        _print_and_log("  [reset] seen.json wiped", log)
    seen = load_seen()
    _print_and_log(f"  seen.json: {len(seen)} known items pre-run", log)

    results: list[FetchResult] = []
    new_items_by_vendor: dict[str, list[FilingItem]] = {}

    for vendor, discover_fn, kwargs in FETCHERS:
        t0 = time.monotonic()
        try:
            res = discover_fn(**kwargs)
        except Exception as exc:  # noqa: BLE001
            res = FetchResult(vendor_code=vendor, ok=False, error=f"{type(exc).__name__}: {exc}")
        elapsed = time.monotonic() - t0
        new = [it for it in res.items if dedup_key(it) not in seen]
        new_items_by_vendor[vendor] = new
        results.append(res)
        status = "ok " if res.ok else "ERR"
        line = (
            f"  {vendor:6}  {status}  fetched={len(res.items):3}  new={len(new):3}  "
            f"({elapsed:.1f}s)  {res.note or ''}"
        )
        if not res.ok:
            line += f"   error={res.error[:120] if res.error else '?'}"
        _print_and_log(line, log)
        if new:
            _print_and_log(f"            → {_summarise_new_items(new)}", log)

    total_new = sum(len(v) for v in new_items_by_vendor.values())
    _print_and_log(f"\n  TOTAL new: {total_new}", log)

    # Ingest phase — resolve + ingest each new item via filings.py.
    # Only successfully-ingested items get added to seen.json; failures
    # remain "new" for the next run so we don't lose them.
    if args.ingest and total_new > 0:
        _print_and_log(f"  ingesting (embed={'no' if args.no_embed else 'yes'}, limit={args.limit}) ...", log)
        _ingest_new_items(
            new_items_by_vendor,
            embed=not args.no_embed,
            limit=args.limit,
            log=log,
        )
        total_new = sum(len(v) for v in new_items_by_vendor.values())

    # Persist
    if not args.dry_run and total_new > 0:
        SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        snapshot_path = SNAPSHOTS_DIR / f"{date.today().isoformat()}.json"
        payload = {
            "run_at": datetime.now().isoformat(timespec="seconds"),
            "vendors": {
                v: [it.to_json() for it in new_items_by_vendor[v]]
                for v in new_items_by_vendor
                if new_items_by_vendor[v]
            },
        }
        # If the same date file exists (multiple runs same day), merge by dedup key
        if snapshot_path.exists():
            existing = json.loads(snapshot_path.read_text(encoding="utf-8"))
            existing_keys = {
                f"{vendor}|{i['source_url']}"
                for vendor, items in existing.get("vendors", {}).items()
                for i in items
            }
            for vendor, items in payload["vendors"].items():
                merged = existing.get("vendors", {}).get(vendor, [])
                for it in items:
                    if f"{vendor}|{it['source_url']}" not in existing_keys:
                        merged.append(it)
                existing.setdefault("vendors", {})[vendor] = merged
            existing["run_at"] = payload["run_at"]
            payload = existing
        snapshot_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        _print_and_log(f"  snapshot: {snapshot_path}", log)

        # Update rolling seen.json
        for items in new_items_by_vendor.values():
            for it in items:
                seen.add(dedup_key(it))
        save_seen(seen)
        _print_and_log(f"  seen.json: {len(seen)} known items post-run", log)
    elif args.dry_run:
        _print_and_log("  [dry-run] no snapshot or seen.json updates written", log)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LAST_RUN_LOG.write_text("\n".join(log) + "\n", encoding="utf-8")

    # Exit non-zero if every fetcher failed
    if all(not r.ok for r in results):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
