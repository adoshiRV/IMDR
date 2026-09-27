"""Indonesia govt-filings ingest — discovery + resolve + ingest.

Mirror of `scripts/econ/au/govt/ingest_filings.py`. Runs every per-agency
fetcher, dedupes against per-vendor `seen.json` under
`data/econ/id/govt/{vendor}/`, and (with `--ingest`) resolves each new item
and hands it to `imdr.research.filings.ingest_filing` to land in
`research.dim_report` + Qdrant + the SharePoint mirror.

    python -m scripts.econ.id.govt.ingest_filings              # discover + snapshot
    python -m scripts.econ.id.govt.ingest_filings --dry-run    # no seen/snapshot write
    python -m scripts.econ.id.govt.ingest_filings --reset      # wipe seen.json
    python -m scripts.econ.id.govt.ingest_filings --ingest     # + resolve + ingest
    python -m scripts.econ.id.govt.ingest_filings --ingest --no-embed
    python -m scripts.econ.id.govt.ingest_filings --ingest --limit 3
    python -m scripts.econ.id.govt.ingest_filings --only bi,ojk

`seen.json` is updated only for items that successfully resolved AND
ingested, so a transient failure is retried on the next run rather than
silently swallowed.

## Two Indonesia-specific notes

**Mixed resolve contract.** Unlike Australia (PDF-only), ID resolvers may
return `("text", str)` as well as `("pdf", bytes)` — BI's news releases and
speeches are HTML-first and their body text IS the document. See
`resolvers.py` for why that differs from the AU decision.

**Kemenkeu is a deliberate non-fetcher.** It is registered so the daily
report names MoF as a known blocker every run instead of the gap being
invisible. It always returns `ok=False` with zero items; that must not fail
the run.
"""
from __future__ import annotations

import argparse
import io
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
# Repo root, so `scripts.econ.id.govt...` and `imdr...` resolve when this
# module is executed directly rather than via `-m`.
_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import fetch_bi  # noqa: E402
import fetch_bps  # noqa: E402
import fetch_djppr  # noqa: E402
import fetch_kemenkeu  # noqa: E402
import fetch_ojk  # noqa: E402
from _models import (  # noqa: E402
    DATA_DIR,
    FetchResult,
    FilingItem,
    dedup_key,
    load_seen,
    save_seen,
    vendor_snapshots_dir,
)

LAST_RUN_LOG = DATA_DIR / "_last_run.log"

# Fetcher order: cheapest first. All five are plain httpx (no Playwright
# anywhere in the ID tree), so ordering is about failure visibility rather
# than runtime — kemenkeu last because it only ever reports a blocker.
#
# Vendor codes match dbo.dim_vendor.vendor_code. `bi`, `bps` and `djppr`
# already exist from Track A; `ojk` is seeded by migration 129.
FETCHERS = [
    ("bi", fetch_bi.discover, {}),
    ("bps", fetch_bps.discover, {}),
    ("djppr", fetch_djppr.discover, {}),
    ("ojk", fetch_ojk.discover, {}),
    ("kemenkeu", fetch_kemenkeu.discover, {}),
]

# How stale an agency's newest item may get before the report flags it.
# Set from the slowest Tier-1 stream each agency carries, with headroom.
STALE_AFTER_DAYS = {"bi": 14, "bps": 45, "djppr": 60, "ojk": 21}

_VENDOR_DISPLAY = {
    "bi": "Bank Indonesia",
    "bps": "Badan Pusat Statistik (Statistics Indonesia)",
    "djppr": "DJPPR Indonesia (Kemenkeu debt-mgmt directorate)",
    "ojk": "Otoritas Jasa Keuangan (Indonesia FSA)",
    "kemenkeu": "Ministry of Finance (Indonesia)",
}


def _vendor_display_name(vendor_code: str) -> str:
    return _VENDOR_DISPLAY.get(vendor_code, vendor_code)


def _print_and_log(msg: str, log_lines: list[str]) -> None:
    print(msg)
    log_lines.append(msg)


def run_fetchers(only: set[str] | None = None) -> dict[str, FetchResult]:
    results: dict[str, FetchResult] = {}
    for name, fn, kwargs in FETCHERS:
        if only and name not in only:
            continue
        try:
            results[name] = fn(**kwargs)
        except Exception as exc:  # Broad by intent: one agency must not
            # sink a scheduled run.
            results[name] = FetchResult(
                vendor_code=name, ok=False,
                error=f"{type(exc).__name__}: {exc}", note="fetcher raised",
            )
    return results


def _ingest_new_items(
    new_items_by_fetcher: dict[str, list[FilingItem]],
    *,
    embed: bool,
    limit: int | None,
    log: list[str],
) -> dict[str, int]:
    """Resolve + ingest each new item via `filings.ingest_filing`.

    Items that fail resolve or ingest are NOT returned as successes, so the
    caller leaves them out of `seen.json` and retries next run.
    """
    import asyncio

    from sqlalchemy import create_engine

    _playground = _REPO_ROOT / "playground"
    if str(_playground) not in sys.path:
        sys.path.insert(0, str(_playground))
    from research.ingest.qdrant_writer import QdrantWriter

    from imdr.config.settings import get_settings
    from imdr.research.filings import FilingInput, ingest_filing
    from scripts.econ.id.govt import resolvers as _r

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
            # Resolvers are blocking httpx (and fetch multi-MB PDFs), so
            # offload rather than stalling the event loop.
            kind, body = await asyncio.to_thread(_r.resolve, item)
        except Exception as exc:
            log.append(
                f"  [resolve-fail] {fetcher:10s} {item.title[:55]!r}: "
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
            # The kind is "text", not "body" -- see resolvers.py for why ID's
            # resolve contract differs from AU's PDF-only one.
            body_text=body if kind == "text" else None,
            doc_type=item.doc_type,
            stream=item.stream,
            asset_class="macro",
            region="ASIA-EM",
            country_code="ID",
            authors=_vendor_display_name(item.vendor_code),
            # BI/DJPPR/OJK publish primarily in Indonesian; the /en/ mirrors
            # are tagged per-stream so the corpus can filter on language.
            language="en" if item.stream.endswith("_en") else "id",
            tags=tuple(item.extras.get("tags", ())) if item.extras else (),
        )
        try:
            result = await ingest_filing(
                filing, engine=engine, api_keys=api_keys,
                qdrant_writer=qdrant_writer, embed=embed,
            )
        except Exception as exc:
            log.append(
                f"  [ingest-fail]  {fetcher:10s} {item.title[:55]!r}: "
                f"{type(exc).__name__}: {str(exc)[:140]}"
            )
            n_failed += 1
            return False

        if result.already_existed:
            log.append(
                f"  [dedup]        {fetcher:10s} report_id={result.report_id} "
                f"{item.title[:55]!r}"
            )
        else:
            n_ingested += 1
            log.append(
                f"  [ingested]     {fetcher:10s} report_id={result.report_id} "
                f"chunks={result.chunk_count} embed={result.embedding_count} "
                f"sp={'yes' if result.sharepoint_path else 'no'} "
                f"{item.title[:50]!r}"
            )
        return True

    async def _run_all() -> None:
        # Round-robin across agencies so a low --limit covers as many as
        # possible (a smoke wants 1-of-each, not 3 BI releases).
        n_done = 0
        cursors = {v: 0 for v in new_items_by_fetcher}
        while True:
            progressed = False
            for fetcher in list(new_items_by_fetcher.keys()):
                if limit is not None and n_done >= limit:
                    return
                idx = cursors[fetcher]
                items = new_items_by_fetcher[fetcher]
                if idx >= len(items):
                    continue
                cursors[fetcher] = idx + 1
                progressed = True
                if await _one(fetcher, items[idx]):
                    success[fetcher].append(items[idx])
                n_done += 1
            if not progressed:
                return

    try:
        asyncio.run(_run_all())
    finally:
        engine.dispose()

    counts = {v: len(s) for v, s in success.items()}
    _print_and_log(
        f"\n  INGEST: {n_ingested} new, {n_failed} failed (limit={limit})", log
    )
    new_items_by_fetcher.clear()
    new_items_by_fetcher.update(success)
    return counts


def write_snapshots(run_date: date, new_by_vendor: dict[str, list[FilingItem]]) -> None:
    """One manifest per vendor per day, under that vendor's subtree."""
    for vendor, items in new_by_vendor.items():
        if not items:
            continue
        d = vendor_snapshots_dir(vendor)
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{run_date.isoformat()}.json").write_text(
            json.dumps(
                {
                    "run_date": run_date.isoformat(),
                    "country_code": "ID",
                    "vendor_code": vendor,
                    "new_items": [i.to_json() for i in items],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )


def _summarise(
    run_date: date,
    results: dict[str, FetchResult],
    new_counts: dict[str, int],
    ingested: dict[str, int] | None,
    log: list[str],
) -> None:
    _print_and_log(f"\nIndonesia govt filings — {run_date.isoformat()}", log)
    head = f"  {'agency':<10} {'ok':<4} {'fetched':>8} {'new':>5}"
    if ingested is not None:
        head += f" {'ingested':>9}"
    head += f"  {'newest':<12} note"
    _print_and_log(head, log)
    for name, r in results.items():
        newest = max((i.publish_date for i in r.items), default=None)
        age = (run_date - newest).days if newest else None
        limit = STALE_AFTER_DAYS.get(name)
        flag = f"  STALE >{limit}d" if (age is not None and limit and age > limit) else ""
        row = (
            f"  {name:<10} {'yes' if r.ok else 'NO':<4} {len(r.items):>8} "
            f"{new_counts.get(name, 0):>5}"
        )
        if ingested is not None:
            row += f" {ingested.get(name, 0):>9}"
        row += f"  {newest.isoformat() if newest else '-':<12} {r.note[:42]}{flag}"
        _print_and_log(row, log)
    failed = [n for n, r in results.items() if not r.ok]
    if failed:
        _print_and_log(f"  NOT OK: {', '.join(failed)}", log)


def main(argv: list[str] | None = None) -> int:
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace"
    )
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="do not write seen.json or snapshots")
    parser.add_argument("--reset", action="store_true",
                        help="ignore existing seen.json (re-discover everything)")
    parser.add_argument("--ingest", action="store_true",
                        help="resolve + ingest new items via filings.py")
    parser.add_argument("--no-embed", action="store_true",
                        help="skip embedding (still writes dim_report + SharePoint)")
    parser.add_argument("--limit", type=int, default=None,
                        help="cap the number of items ingested this run")
    parser.add_argument("--only", default="",
                        help="comma-separated agency subset, e.g. bi,ojk")
    args = parser.parse_args(argv)

    only = {s.strip() for s in args.only.split(",") if s.strip()} or None
    if only:
        unknown = only - {n for n, _, _ in FETCHERS}
        if unknown:
            parser.error(f"unknown agency: {', '.join(sorted(unknown))}")

    log: list[str] = []
    run_date = date.today()
    results = run_fetchers(only)

    prior_seen = set() if args.reset else load_seen()
    new_by_vendor: dict[str, list[FilingItem]] = {}
    # Fresh rows we will never ingest (DJPPR's undated issuance calendars and
    # retail-SBN term sheets). They still belong in seen.json: `dedup_key` is
    # (vendor, source_url) and does NOT depend on the stamped `date.today()`,
    # so leaving them out would have them rediscovered and re-counted as
    # "new" on every future run — permanent daily-report noise that looks
    # like a backlog but never drains.
    skipped_keys: set[str] = set()

    from scripts.econ.id.govt import resolvers as _r

    for name, r in results.items():
        fresh: list[FilingItem] = []
        for item in r.items:
            key = dedup_key(item)
            if key in prior_seen or key in skipped_keys:
                continue
            if not _r.is_ingestable(item):
                skipped_keys.add(key)
                continue
            fresh.append(item)
        new_by_vendor[name] = fresh

    new_counts = {k: len(v) for k, v in new_by_vendor.items()}
    skipped_not_ingestable = len(skipped_keys)
    ingested: dict[str, int] | None = None

    if args.ingest:
        ingested = _ingest_new_items(
            new_by_vendor, embed=not args.no_embed, limit=args.limit, log=log
        )
        # `_ingest_new_items` rewrites new_by_vendor in place to hold only the
        # items that actually landed, so only those earn a place in seen.json
        # — a resolve/ingest failure must be retried next run, not swallowed.
        succeeded = {
            dedup_key(i) for items in new_by_vendor.values() for i in items
        }
        seen = prior_seen | skipped_keys | succeeded
    else:
        # Discovery-only: every fresh row is recorded, ingestable or not.
        seen = prior_seen | skipped_keys | {
            dedup_key(i) for items in new_by_vendor.values() for i in items
        }

    _summarise(run_date, results, new_counts, ingested, log)
    if skipped_not_ingestable:
        _print_and_log(
            f"  ({skipped_not_ingestable} discovered rows skipped as "
            f"not-ingestable: undated reference artefacts)", log
        )

    if args.dry_run:
        _print_and_log("\n  --dry-run: nothing written", log)
    else:
        write_snapshots(run_date, new_by_vendor)
        save_seen(seen)
        LAST_RUN_LOG.parent.mkdir(parents=True, exist_ok=True)
        LAST_RUN_LOG.write_text("\n".join(log), encoding="utf-8")
        _print_and_log(f"\n  state -> {DATA_DIR}", log)

    # Non-zero only when EVERY agency failed. Kemenkeu is expected to be
    # ok=False on every run, so `any(ok)` is the right condition.
    return 0 if any(r.ok for r in results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
