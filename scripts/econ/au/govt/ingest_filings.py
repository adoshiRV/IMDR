"""Australia government policy filings — daily ingest orchestrator.

Mirror of `scripts/econ/kr/govt/ingest_filings.py`. Runs every per-agency
fetcher in `scripts/econ/au/govt/` in sequence, dedups against the
rolling per-vendor `data/econ/au/govt/{vendor}/seen.json`, writes a
per-day snapshot of NEW items per vendor, and (when ``--ingest`` is
passed) pushes each new filing through
``imdr.research.filings.ingest_filing`` to land in
``research.dim_report`` + ``research.fact_chunk`` + Qdrant + SharePoint.

Wired into ``scripts/econ/au/au_daily.py`` (the per-country daily
orchestrator). Scheduler registration in ``scripts/imdr_daily.py``
is a separate gate.

Direct usage:
    python -m scripts.econ.au.govt.ingest_filings              # discover + snapshot
    python -m scripts.econ.au.govt.ingest_filings --dry-run    # no seen.json / snapshot write
    python -m scripts.econ.au.govt.ingest_filings --reset      # wipe seen.json (re-discover)
    python -m scripts.econ.au.govt.ingest_filings --ingest     # discover + resolve + ingest_filing
    python -m scripts.econ.au.govt.ingest_filings --ingest --no-embed
    python -m scripts.econ.au.govt.ingest_filings --ingest --limit 3
                                                               # smoke: cap at N items

Runtime state (per-machine, gitignored):
    data/econ/au/govt/_last_run.log            — orchestrator stdout
    data/econ/au/govt/{vendor}/seen.json       — per-agency rolling dedup
    data/econ/au/govt/{vendor}/snapshots/
        {YYYY-MM-DD}.json                       — per-agency daily manifest

State is partitioned per vendor_code (rba, treasury_au, apra, abs,
westpac, nab) — same shape as the per-vendor SharePoint mirror and
the broader `data/econ/{cc}/{vendor}/` convention. ``seen.json`` is
updated only for items that successfully resolved + ingested, so
transient failures are retryable on the next run.
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import time
from datetime import date, datetime
from pathlib import Path

# Force UTF-8 stdout — em-dashes and Western titles come through subprocess output.
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent))
from _models import (  # noqa: E402
    DATA_DIR,
    FetchResult,
    FilingItem,
    dedup_key,
    load_seen,
    save_seen,
    vendor_snapshots_dir,
)

import fetch_abs_commentary           # noqa: E402
import fetch_apra_quarterly           # noqa: E402
import fetch_nab_business_survey      # noqa: E402
import fetch_rba_board_minutes        # noqa: E402
import fetch_rba_fsr                  # noqa: E402
import fetch_rba_governors_statement  # noqa: E402
import fetch_rba_smp                  # noqa: E402
import fetch_rba_speeches             # noqa: E402
import fetch_treasury                 # noqa: E402
import fetch_westpac_cci              # noqa: E402

LAST_RUN_LOG = DATA_DIR / "_last_run.log"

# Fetcher order: cheap plain-httpx first, Playwright RBA last so a slow
# Playwright run doesn't delay the lightweight scrapes. Vendor codes
# match dbo.dim_vendor.vendor_code (rba, treasury_au, apra, abs, westpac, nab).
# Multiple fetchers may share a vendor_code — all RBA fetchers emit
# vendor_code='rba' with distinct `stream` values that resolvers.py
# dispatches on.
FETCHERS = [
    ("treasury",                fetch_treasury.discover,                {}),
    ("apra_quarterly",          fetch_apra_quarterly.discover,          {}),
    ("abs_commentary",          fetch_abs_commentary.discover,          {}),
    ("rba_governors_statement", fetch_rba_governors_statement.discover, {}),
    ("rba_board_minutes",       fetch_rba_board_minutes.discover,       {}),
    ("rba_smp",                 fetch_rba_smp.discover,                 {"since_year": datetime.now().year - 1}),
    ("rba_fsr",                 fetch_rba_fsr.discover,                 {"since_year": datetime.now().year - 2}),
    ("rba_speeches",            fetch_rba_speeches.discover,            {}),
]

# Excluded from the AU filings orchestrator (sell_side vendor_category;
# imdr.research.filings.ingest_filing accepts only official_* sources):
#   - fetch_westpac_cci  — Westpac-MI Consumer Sentiment lives in the
#     sell-side research ingest pipeline (playground/research/ingest/
#     crawler_westpac.py crawls /economics + /markets hubs).
#   - fetch_nab_business_survey — NAB has no sell-side fetcher today;
#     to ingest, either add a sell-side NAB crawler OR re-categorise
#     `nab` away from `sell_side`. Keep playground discovery as the
#     reference until that decision lands.
# Discovery-only manifests for these two still live under
# playground/econ/au/govt/ (Westpac CCI tested 2026-06-11; NAB BSI
# tested 2026-06-11 — both prove the URL pattern works).

# Per-vendor display names for the FilingInput.authors field. Vendor_code
# is what dbo.dim_vendor cares about; authors is human-readable metadata
# that appears on the SharePoint mirror + Mycroft/Lois output.
_VENDOR_DISPLAY = {
    "rba":         "Reserve Bank of Australia",
    "treasury_au": "Department of the Treasury (Australia)",
    "apra":        "Australian Prudential Regulation Authority",
    "abs":         "Australian Bureau of Statistics",
    "westpac":     "Westpac IQ",
    "nab":         "National Australia Bank",
}


def _vendor_display_name(vendor_code: str) -> str:
    return _VENDOR_DISPLAY.get(vendor_code, vendor_code)


def _print_and_log(msg: str, log_lines: list[str]) -> None:
    print(msg)
    log_lines.append(msg)


def _summarise_new_items(items: list[FilingItem]) -> str:
    if not items:
        return ""
    titles = [it.title[:60] for it in items[:2]]
    extra = f" +{len(items) - 2} more" if len(items) > 2 else ""
    return ", ".join(titles) + extra


def _ingest_new_items(
    new_items_by_fetcher: dict[str, list[FilingItem]],
    *,
    embed: bool,
    limit: int | None,
    log: list[str],
) -> dict[str, int]:
    """Resolve + ingest each new item via filings.ingest_filing.

    Items that fail resolve or ingest are NOT added to seen.json — caller
    retries them next run.
    """
    import asyncio  # noqa: PLC0415
    from sqlalchemy import create_engine  # noqa: PLC0415
    _playground = Path(__file__).resolve().parents[4] / "playground"
    if str(_playground) not in sys.path:
        sys.path.insert(0, str(_playground))
    from imdr.config.settings import get_settings  # noqa: PLC0415
    from imdr.research.filings import FilingInput, ingest_filing  # noqa: PLC0415
    from research.ingest.qdrant_writer import QdrantWriter  # noqa: PLC0415
    from scripts.econ.au.govt import resolvers as _r  # noqa: PLC0415

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
    api_keys = {"voyage": _s.voyage_key, "google": _s.gemini_key}

    success: dict[str, list[FilingItem]] = {v: [] for v in new_items_by_fetcher}
    n_ingested = 0
    n_failed = 0

    async def _one(fetcher: str, item: FilingItem) -> bool:
        nonlocal n_ingested, n_failed
        try:
            # Resolvers use Playwright sync API for the Akamai-bypass /
            # HTML-render-to-PDF path. Sync-Playwright can't run inside an
            # asyncio event loop, so we offload to a worker thread.
            kind, body = await asyncio.to_thread(_r.resolve, item)
        except Exception as exc:  # noqa: BLE001
            log.append(
                f"  [resolve-fail] {fetcher:30s} {item.title[:55]!r}: "
                f"{type(exc).__name__}: {str(exc)[:100]}"
            )
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
            region="ASIA-DM",
            country_code="AU",
            authors=_vendor_display_name(item.vendor_code),
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
            log.append(
                f"  [ingest-fail]  {fetcher:30s} {item.title[:55]!r}: "
                f"{type(exc).__name__}: {str(exc)[:140]}"
            )
            n_failed += 1
            return False
        if result.already_existed:
            log.append(
                f"  [dedup]        {fetcher:30s} report_id={result.report_id} "
                f"{item.title[:55]!r}"
            )
        else:
            n_ingested += 1
            log.append(
                f"  [ingested]     {fetcher:30s} report_id={result.report_id} "
                f"chunks={result.chunk_count} embed={result.embedding_count} "
                f"sp={'yes' if result.sharepoint_path else 'no'} "
                f"{item.title[:50]!r}"
            )
        return True

    async def _run_all() -> None:
        # Round-robin across fetchers so a low --limit covers as many
        # streams as possible (smoke test wants 1-of-each, not 10 RBAs).
        n_done = 0
        cursors: dict[str, int] = {v: 0 for v in new_items_by_fetcher}
        while True:
            progressed = False
            for fetcher in list(new_items_by_fetcher.keys()):
                if limit is not None and n_done >= limit:
                    return
                idx = cursors[fetcher]
                items = new_items_by_fetcher[fetcher]
                if idx >= len(items):
                    continue
                item = items[idx]
                cursors[fetcher] = idx + 1
                progressed = True
                ok = await _one(fetcher, item)
                if ok:
                    success[fetcher].append(item)
                n_done += 1
            if not progressed:
                return

    try:
        asyncio.run(_run_all())
    finally:
        engine.dispose()

    counts = {v: len(s) for v, s in success.items()}
    _print_and_log(f"\n  INGEST: {n_ingested} new, {n_failed} failed (limit={limit})", log)
    new_items_by_fetcher.clear()
    new_items_by_fetcher.update(success)
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="don't write seen.json or daily snapshot")
    parser.add_argument("--reset", action="store_true",
                        help="wipe per-vendor seen.json before run (treat everything as new)")
    parser.add_argument("--ingest", action="store_true",
                        help="resolve + ingest new items via filings.py")
    parser.add_argument("--no-embed", action="store_true",
                        help="when --ingest, write chunks without embeddings (no Qdrant)")
    parser.add_argument("--limit", type=int, default=None,
                        help="when --ingest, cap at N new items (smoke)")
    args = parser.parse_args(argv)

    run_id = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log: list[str] = []
    _print_and_log(f"=== Australia govt filings daily pull — {run_id} ===", log)

    if args.reset and not args.dry_run:
        n_wiped = 0
        if DATA_DIR.exists():
            for sub in DATA_DIR.iterdir():
                f = sub / "seen.json" if sub.is_dir() else None
                if f and f.exists():
                    f.unlink()
                    n_wiped += 1
        _print_and_log(f"  [reset] wiped {n_wiped} per-vendor seen.json file(s)", log)
    seen = load_seen()
    _print_and_log(f"  seen.json: {len(seen)} known items pre-run (aggregated across vendors)", log)

    results: list[FetchResult] = []
    new_items_by_fetcher: dict[str, list[FilingItem]] = {}

    for fetcher, discover_fn, kwargs in FETCHERS:
        t0 = time.monotonic()
        try:
            res = discover_fn(**kwargs)
        except Exception as exc:  # noqa: BLE001
            res = FetchResult(
                vendor_code=fetcher, ok=False, error=f"{type(exc).__name__}: {exc}"
            )
        elapsed = time.monotonic() - t0
        new = [it for it in res.items if dedup_key(it) not in seen]
        new_items_by_fetcher[fetcher] = new
        results.append(res)
        status = "ok " if res.ok else "ERR"
        line = (
            f"  {fetcher:30s}  {status}  fetched={len(res.items):3}  new={len(new):3}  "
            f"({elapsed:.1f}s)  {res.note or ''}"
        )
        if not res.ok:
            line += f"   error={res.error[:120] if res.error else '?'}"
        _print_and_log(line, log)
        if new:
            _print_and_log(f"            → {_summarise_new_items(new)}", log)

    total_new = sum(len(v) for v in new_items_by_fetcher.values())
    _print_and_log(f"\n  TOTAL new: {total_new}", log)

    if args.ingest and total_new > 0:
        _print_and_log(
            f"  ingesting (embed={'no' if args.no_embed else 'yes'}, limit={args.limit}) ...", log
        )
        _ingest_new_items(
            new_items_by_fetcher,
            embed=not args.no_embed,
            limit=args.limit,
            log=log,
        )
        total_new = sum(len(v) for v in new_items_by_fetcher.values())

    # Snapshots — partition by vendor_code (rba's 5 fetchers → one rba/ dir).
    if not args.dry_run and total_new > 0:
        run_at = datetime.now().isoformat(timespec="seconds")
        today_iso = date.today().isoformat()
        # Aggregate items across fetchers by vendor_code for snapshot writing
        items_by_vendor: dict[str, list[FilingItem]] = {}
        for items in new_items_by_fetcher.values():
            for it in items:
                items_by_vendor.setdefault(it.vendor_code, []).append(it)
        snapshot_paths: list[str] = []
        for vendor, items in items_by_vendor.items():
            if not items:
                continue
            v_snap_dir = vendor_snapshots_dir(vendor)
            v_snap_dir.mkdir(parents=True, exist_ok=True)
            snapshot_path = v_snap_dir / f"{today_iso}.json"
            payload = {
                "vendor": vendor,
                "run_at": run_at,
                "items": [it.to_json() for it in items],
            }
            if snapshot_path.exists():
                existing = json.loads(snapshot_path.read_text(encoding="utf-8"))
                existing_urls = {i["source_url"] for i in existing.get("items", [])}
                merged = list(existing.get("items", []))
                for it in payload["items"]:
                    if it["source_url"] not in existing_urls:
                        merged.append(it)
                existing["items"] = merged
                existing["run_at"] = run_at
                payload = existing
            snapshot_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            snapshot_paths.append(str(snapshot_path))
        if snapshot_paths:
            _print_and_log(
                f"  wrote {len(snapshot_paths)} per-vendor snapshot(s) "
                f"under data/econ/au/govt/{{vendor}}/snapshots/",
                log,
            )

        for items in new_items_by_fetcher.values():
            for it in items:
                seen.add(dedup_key(it))
        save_seen(seen)
        _print_and_log(f"  seen.json: {len(seen)} known items post-run", log)
    elif args.dry_run:
        _print_and_log("  [dry-run] no snapshot or seen.json updates written", log)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LAST_RUN_LOG.write_text("\n".join(log) + "\n", encoding="utf-8")

    if all(not r.ok for r in results):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
