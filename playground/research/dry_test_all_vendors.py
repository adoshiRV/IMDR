"""Dry test — per-vendor pipeline check, no downloads.

For each of the 6 live vendors, runs the same discovery the daily
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

Usage:
    C:/Users/adoshi/.conda/envs/imdr/python.exe playground/research/dry_test_all_vendors.py
"""
from __future__ import annotations

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

PROFILES_ROOT = HERE / "profiles"
_VENDORS: tuple[str, ...] = (
    "anz", "barclays", "bnp", "goldman", "hsbc", "ms", "nomura",
)


def _import_discover(vendor: str):
    if vendor == "anz":
        from ingest.crawler_anz import discover_reports
    elif vendor == "barclays":
        from ingest.crawler_barclays import discover_reports
    elif vendor == "bnp":
        from ingest.crawler_bnp import discover_reports
    elif vendor == "goldman":
        from ingest.crawler_goldman import discover_reports
    elif vendor == "hsbc":
        from ingest.crawler_hsbc import discover_reports
    elif vendor == "ms":
        from ingest.crawler_ms import discover_reports
    elif vendor == "nomura":
        from ingest.crawler_nomura import discover_reports
    else:
        raise KeyError(vendor)
    return discover_reports


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


async def _amain() -> None:
    stats_list: list[dict] = []
    for vendor in _VENDORS:
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


if __name__ == "__main__":
    asyncio.run(_amain())
