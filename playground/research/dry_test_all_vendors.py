"""Dry test — per-vendor pipeline check, no downloads.

For each of the 15 live vendors, runs the same discovery the daily
ingest uses (today-1 .. today), then for each surviving ref:

  1. discovery filter (filters/{vendor}.py)  — drops invites/webcasts
  2. relevance filter (ingest/relevance.py)  — drops single-name equity
  3. classifier (classifiers/{vendor}.py)    — produces ClassifyResult

Prints the post-filter survivor count + how many were dropped by each
stage, plus a one-ref worked example so you can eyeball the classify
output.

Touches nothing: no PDF fetch, no parse, no chunk, no upload, no
embed, no MSSQL write, no Qdrant write. Pure auth + listing API +
filter + classifier round-trip.

Why: validates that
  (a) each vendor's Playwright profile is still authenticated,
  (b) discovery returns plausible results,
  (c) per-vendor filters drop the right tiles,
  (d) the relevance filter drops single-name equity research, and
  (e) classifiers produce sensible asset_class / country / region /
      tags / context strings on a real listing-API record.

If a vendor's session has expired the script prints the failure and
continues to the next one. Goldman/Barclays/HSBC etc. can each fail
independently.

Vendors run strictly one at a time: each spins up a headed Playwright
Chrome, and the box cannot host two concurrently.

Usage:
    # full roster
    C:/Users/adoshi/.conda/envs/imdr/python.exe playground/research/dry_test_all_vendors.py

    # narrow to a few
    ... dry_test_all_vendors.py --vendors goldman,citi,ubs
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from ingest._console import force_utf8_stdout  # noqa: E402

# Force stdout/stderr to UTF-8 before any print() so a non-cp1252 char in
# a report title can't crash the run when output is piped to Tee-Object.
force_utf8_stdout()

from imdr.config.settings import get_settings  # noqa: E402

# Same local-disk profile root the daily ingest uses (default
# C:\IMDR_LOCAL\research_profiles) — the old SMB playground/research/profiles
# copies are stale since the 2026-07-22 C-drive unification.
PROFILES_ROOT = get_settings().research_profile_root
# Full live roster — mirrors _load_vendor_registry() in ingest_today.py.
# Kept as a literal (rather than importing that registry) because the
# registry imports all 15 crawlers eagerly: one broken crawler module
# would take down the whole health check instead of failing its own row.
# _check_roster_drift() below flags divergence at the end of a run.
_VENDORS: tuple[str, ...] = (
    "anz", "barclays", "bnp", "bofa", "citi", "db", "goldman", "hsbc",
    "jpm", "ms", "nomura", "socgen", "stanc", "ubs", "westpac",
)

# vendor -> ingest.crawler_* module suffix, where it isn't just the code.
_CRAWLER_MODULE_OVERRIDES: dict[str, str] = {
    # BofA is firehose-only per the 2026-07-17 decision.
    "bofa": "bofa_firehose",
}


def _import_discover(vendor: str):
    """Lazily import one vendor's discover_reports.

    Per-vendor import (not a shared registry import) so a crawler that
    fails to import is reported as that vendor's failure and the run
    continues.
    """
    from importlib import import_module  # noqa: PLC0415

    suffix = _CRAWLER_MODULE_OVERRIDES.get(vendor, vendor)
    return import_module(f"ingest.crawler_{suffix}").discover_reports


def _check_roster_drift() -> None:
    """Best-effort: warn if _VENDORS has drifted from the prod registry."""
    try:
        from ingest_today import _load_vendor_registry  # noqa: PLC0415

        prod = set(_load_vendor_registry())
    except Exception as exc:  # noqa: BLE001 — informational only
        print(f"  (roster drift check skipped: {type(exc).__name__}: {exc})")
        return
    here = set(_VENDORS)
    if missing := sorted(prod - here):
        print(f"  ! in ingest_today registry but NOT health-checked: {missing}")
    if extra := sorted(here - prod):
        print(f"  ! health-checked but NOT in ingest_today registry: {extra}")
    if not (prod - here) and not (here - prod):
        print(f"  roster matches ingest_today registry ({len(prod)} vendors)")


def _format_ref_line(vendor: str, ref) -> str:
    pubtype = getattr(ref, "publication_type", "") or ""
    title = (ref.title or "")[:60]
    return (
        f"{ref.publish_date}  {ref.uuid[:8]}  "
        f"[{pubtype[:22]:<22}]  {title}"
    )


def _print_classify_result(result, indent: str = "    ") -> None:
    asset = result.asset_class or "—"
    country = result.country_code or "—"
    tag_strs = [f"{t.category}:{t.value}" for t in result.tags]
    print(f"{indent}asset_class: {asset}")
    print(f"{indent}country    : {country}")
    print(f"{indent}tags       : {tag_strs if tag_strs else '—'}")
    print(f"{indent}context    :")
    for line in (result.context or "").splitlines():
        print(f"{indent}  {line}")


async def _test_one_vendor(vendor: str) -> dict:
    """Run discovery + relevance filter + classifier for one vendor.

    Returns a dict with the per-vendor stats so the summary at the
    bottom can compare counts side-by-side.
    """
    from ingest.classifiers import get_classifier, has_classifier  # noqa: PLC0415
    from ingest.relevance import apply_relevance_filter  # noqa: PLC0415

    profile_dir = PROFILES_ROOT / vendor
    today = datetime.now(timezone.utc).date()
    since = today - timedelta(days=1)
    until = today

    stats: dict = {
        "vendor": vendor,
        "status": "ok",
        "post_filter": 0,
        "post_relevance": 0,
        "dropped_single_name": 0,
    }

    print()
    print("=" * 72)
    print(f" {vendor.upper()}  ({since} .. {until})")
    print("=" * 72)

    if not profile_dir.exists():
        print(f"  ! profile not found: {profile_dir}")
        stats["status"] = "failed"
        return stats

    try:
        discover = _import_discover(vendor)
        refs = await discover(profile_dir, since=since, until=until)
    except Exception:  # noqa: BLE001
        print("  ! discover_reports raised:")
        traceback.print_exc()
        stats["status"] = "failed"
        return stats

    stats["post_filter"] = len(refs)
    print(f"  discovered (post-filter): {len(refs)}")
    if not refs:
        print("  no reports in window — nothing to classify.")
        stats["status"] = "no-survivors"
        return stats

    # Relevance filter — drops single-name equity. Prints [DROP] lines.
    print("  applying relevance filter (drop single-name equity)...")
    kept, dropped = apply_relevance_filter(
        vendor_code=vendor, refs=refs, verbose=True,
    )
    stats["dropped_single_name"] = len(dropped)
    stats["post_relevance"] = len(kept)
    print(
        f"  after relevance filter: {len(kept)} kept, "
        f"{len(dropped)} dropped"
    )
    if not kept:
        print("  nothing left to classify after relevance filter.")
        stats["status"] = "no-survivors-post-relevance"
        return stats

    ref = kept[0]
    print(f"  picked: {_format_ref_line(vendor, ref)}")

    if not has_classifier(vendor):
        print(f"  ! no classifier registered for vendor={vendor!r}")
        stats["status"] = "no-classifier"
        return stats

    try:
        classify = get_classifier(vendor)
        result = classify(ref)
    except Exception:  # noqa: BLE001
        print("  ! classify(ref) raised:")
        traceback.print_exc()
        stats["status"] = "failed"
        return stats

    print("  classify result:")
    _print_classify_result(result)
    return stats


def _resolve_vendors(arg: str) -> tuple[str, ...]:
    if not arg:
        return _VENDORS
    picked = tuple(v.strip().lower() for v in arg.split(",") if v.strip())
    if unknown := [v for v in picked if v not in _VENDORS]:
        raise SystemExit(
            f"unknown vendor(s): {unknown}; known: {list(_VENDORS)}"
        )
    return picked


async def _amain(vendors: tuple[str, ...]) -> None:
    stats_list: list[dict] = []
    for vendor in vendors:
        try:
            stats = await _test_one_vendor(vendor)
        except Exception:  # noqa: BLE001 — last-resort guard
            print(f"  ! unhandled error in {vendor}:")
            traceback.print_exc()
            stats = {
                "vendor": vendor, "status": "failed",
                "post_filter": 0, "dropped_single_name": 0, "post_relevance": 0,
            }
        stats_list.append(stats)

    print()
    print("=" * 72)
    print(" SUMMARY")
    print("=" * 72)
    print(f"  {'vendor':<10}  {'discovered':>10}  {'dropped':>8}  {'kept':>6}  status")
    for s in stats_list:
        marker = "ok " if s["status"] == "ok" else "!! "
        print(
            f"  {marker}{s['vendor']:<7}  {s['post_filter']:>10}  "
            f"{s['dropped_single_name']:>8}  {s['post_relevance']:>6}  {s['status']}"
        )
    ok = sum(1 for s in stats_list if s["status"] == "ok")
    failed = [s["vendor"] for s in stats_list if s["status"] == "failed"]
    print()
    print(f"  {ok}/{len(stats_list)} vendors classified a live ref")
    if failed:
        print(f"  FAILED: {', '.join(failed)}")
    _check_roster_drift()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--vendors", default="",
        help="comma-separated subset; default = full roster",
    )
    args = ap.parse_args()
    asyncio.run(_amain(_resolve_vendors(args.vendors)))
