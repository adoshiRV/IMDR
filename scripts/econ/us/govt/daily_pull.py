"""United States govt filings — daily discovery orchestrator.

Mirror of `playground/econ/au/govt/daily_pull.py`. Runs every Tier-1
Federal Reserve probe under `playground/econ/us/govt/` in sequence,
dedups against the rolling `data/seen.json`, writes a MANIFEST-ONLY
per-day snapshot of NEW items, and prints a summary table.

⚠ MANIFEST-ONLY — NO DB writes. The snapshot carries title / url / date /
doc_type only; NO document bodies are fetched into any store. This is
Phase-H discovery (see docs/admin/econ/onboarding_new_country.md §H).
When the research-doc pipeline absorbs filings (research.dim_report /
research.fact_chunk / Qdrant), add an `--ingest` flag to pipe new items
through `ingest_filing()` — that is gated Phase-J work, NOT done here.

Usage:
    python -m playground.econ.us.govt.daily_pull            # discover + snapshot + summary
    python -m playground.econ.us.govt.daily_pull --dry-run  # no seen.json / snapshot write
    python -m playground.econ.us.govt.daily_pull --reset    # wipe seen.json (treat everything as new)

Daily output:
    data/snapshots/{YYYY-MM-DD}.json   — new items discovered today (manifest-only)
    data/seen.json                     — rolling source_url set (dedup)
    data/_last_run.log                 — most recent run output, for review
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import time
from datetime import date, datetime
from pathlib import Path

# Force UTF-8 on stdout — print() carries arrows.
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent))
from _models import (  # noqa: E402
    SEEN_FILE,
    FetchResult,
    FilingItem,
    dedup_key,
    load_seen,
    save_seen,
)

import probe_fed_speeches      # noqa: E402
import probe_fomc_minutes      # noqa: E402
import probe_fomc_sep          # noqa: E402
import probe_fomc_statements   # noqa: E402
# High-value streams added 2026-06-22 (macro-PM signal set).
import probe_fomc_presconf       # noqa: E402
import probe_mpr                 # noqa: E402
import probe_beige_book          # noqa: E402
import probe_financial_stability # noqa: E402
import probe_sloos               # noqa: E402
import probe_treasury_refunding  # noqa: E402
import probe_nyfed_surveys       # noqa: E402

DATA_DIR = Path(__file__).parent / "data"
SNAPSHOTS_DIR = DATA_DIR / "snapshots"
LAST_RUN_LOG = DATA_DIR / "_last_run.log"

# One entry per Tier-1 Federal Reserve stream. The three FOMC probes each
# GET the same calendar hub independently (cheap, ~160 KB) — kept separate
# so each stream has its own owner + doc_type. Speeches uses the JSON feed.
# Label is the stream id (snapshot key); the probes themselves all return
# vendor_code="fed".
FETCHERS = [
    ("fomc_statements",           probe_fomc_statements.discover,   {}),
    ("fomc_minutes",              probe_fomc_minutes.discover,      {}),
    ("fomc_sep",                  probe_fomc_sep.discover,          {}),
    ("fed_speeches",              probe_fed_speeches.discover,      {"limit": 40}),
    # High-value macro-PM streams (added 2026-06-22).
    ("fomc_presconf",             probe_fomc_presconf.discover,     {}),
    ("monetary_policy_report",    probe_mpr.discover,               {}),
    ("beige_book",                probe_beige_book.discover,        {"limit": 16}),
    ("financial_stability_report", probe_financial_stability.discover, {}),
    ("sloos",                     probe_sloos.discover,             {"limit": 16}),
    ("treasury_refunding",        probe_treasury_refunding.discover, {"quarters": 8}),
    ("nyfed_dealer_survey",       probe_nyfed_surveys.discover,     {"meetings": 8}),
]


def _print_and_log(msg: str, log_lines: list[str]) -> None:
    print(msg)
    log_lines.append(msg)


def _summarise_new_items(items: list[FilingItem]) -> str:
    if not items:
        return ""
    titles = [it.title[:60] for it in items[:2]]
    extra = f" +{len(items) - 2} more" if len(items) > 2 else ""
    return ", ".join(titles) + extra


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="don't write seen.json or daily snapshot")
    parser.add_argument("--reset", action="store_true",
                        help="wipe seen.json before run (treat everything as new)")
    args = parser.parse_args(argv)

    run_id = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log: list[str] = []
    _print_and_log(f"=== United States govt filings daily pull — {run_id} ===", log)
    _print_and_log("  (manifest-only — no DB writes, no document bodies fetched)", log)

    if args.reset and SEEN_FILE.exists() and not args.dry_run:
        SEEN_FILE.unlink()
        _print_and_log("  [reset] seen.json wiped", log)
    seen = load_seen()
    _print_and_log(f"  seen.json: {len(seen)} known items pre-run", log)

    results: list[FetchResult] = []
    # Keyed by STREAM label (not vendor_code — all four are "fed").
    new_items_by_stream: dict[str, list[FilingItem]] = {}

    for stream, discover_fn, kwargs in FETCHERS:
        t0 = time.monotonic()
        try:
            res = discover_fn(**kwargs)
        except Exception as exc:  # noqa: BLE001
            res = FetchResult(vendor_code="fed", ok=False, error=f"{type(exc).__name__}: {exc}")
        elapsed = time.monotonic() - t0
        new = [it for it in res.items if dedup_key(it) not in seen]
        new_items_by_stream[stream] = new
        results.append(res)
        status = "ok " if res.ok else "ERR"
        line = (
            f"  {stream:18}  {status}  fetched={len(res.items):3}  new={len(new):3}  "
            f"({elapsed:.1f}s)  {res.note or ''}"
        )
        if not res.ok:
            line += f"   error={res.error[:120] if res.error else '?'}"
        _print_and_log(line, log)
        if new:
            _print_and_log(f"            -> {_summarise_new_items(new)}", log)

    total_new = sum(len(v) for v in new_items_by_stream.values())
    _print_and_log(f"\n  TOTAL new: {total_new}", log)

    if not args.dry_run and total_new > 0:
        SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        snapshot_path = SNAPSHOTS_DIR / f"{date.today().isoformat()}.json"
        payload = {
            "run_at": datetime.now().isoformat(timespec="seconds"),
            "manifest_only": True,
            "streams": {
                s: [it.to_json() for it in new_items_by_stream[s]]
                for s in new_items_by_stream
                if new_items_by_stream[s]
            },
        }
        # Merge if the same date file exists (multiple runs same day).
        if snapshot_path.exists():
            existing = json.loads(snapshot_path.read_text(encoding="utf-8"))
            existing_keys = {
                f"{stream}|{i['source_url']}"
                for stream, items in existing.get("streams", {}).items()
                for i in items
            }
            for stream, items in payload["streams"].items():
                merged = existing.get("streams", {}).get(stream, [])
                for it in items:
                    if f"{stream}|{it['source_url']}" not in existing_keys:
                        merged.append(it)
                existing.setdefault("streams", {})[stream] = merged
            existing["run_at"] = payload["run_at"]
            payload = existing
        snapshot_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        _print_and_log(f"  snapshot: {snapshot_path}", log)

        for items in new_items_by_stream.values():
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
