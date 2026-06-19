"""Smoke test for the BofA Advanced Search firehose discovery path.

Run:
    C:/Users/adoshi/.conda/envs/imdr/python.exe playground/research/_smoke_bofa_firehose.py

Calls discover_reports() for all macro disciplines over the week
2026-06-08 to 2026-06-15, classifies each kept ref, and prints:
  - per-discipline: raw count from Advanced Search + kept after drops
  - total kept vs old hub-crawler baseline (~42/week)
  - asset_class composition of kept refs

This is a headed-Chrome run (~15s login + ~10s per discipline).
BofA stays PROD-HELD - no DB writes.
"""
from __future__ import annotations

import asyncio
import sys
from collections import Counter
from datetime import date
from pathlib import Path

# Allow running from repo root or from playground/research/
_REPO_ROOT = Path(__file__).resolve().parents[2]
_RESEARCH_ROOT = _REPO_ROOT / "playground" / "research"
for p in (_REPO_ROOT, _RESEARCH_ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

# Load .env into env vars
from src.imdr.config.settings import Settings  # noqa: E402

_settings = Settings()  # type: ignore[call-arg]

# Profile dir (same as used by hub crawler and existing smoke scripts)
_PROFILE_DIR = Path("C:/Users/adoshi/AppData/Local/ms-playwright/bofa-profile")

_SINCE = date(2026, 6, 8)
_UNTIL = date(2026, 6, 15)


async def main() -> None:
    from ingest.crawler_bofa_firehose import (
        _DISCIPLINE_TO_HUB,
        discover_reports,
    )
    from ingest.classifiers.bofa import classify

    print(f"BofA Firehose Smoke  since={_SINCE}  until={_UNTIL}")
    print(f"Disciplines: {len(_DISCIPLINE_TO_HUB)}")
    print()

    refs = await discover_reports(
        _PROFILE_DIR,
        since=_SINCE,
        until=_UNTIL,
        resolve_urls=True,
    )

    if not refs:
        print("No refs returned - check login / date window / discipline list.")
        return

    # Classify each kept ref
    asset_class_counter: Counter[str] = Counter()
    disc_kept: dict[str, int] = {}

    for ref in refs:
        result = classify(ref)
        ac = result.asset_class or "UNKNOWN"
        asset_class_counter[ac] += 1

    # Count per discipline (hub to discipline reverse map)
    from ingest.crawler_bofa_firehose import _DISCIPLINE_TO_HUB  # noqa: F811
    hub_to_discs: dict[str, list[str]] = {}
    for disc, hub in _DISCIPLINE_TO_HUB.items():
        hub_to_discs.setdefault(hub, []).append(disc)

    disc_counts: Counter[str] = Counter()
    for ref in refs:
        disc_counts[ref.hub] += 1

    print()
    print("=== Per-hub kept counts ===")
    for hub, cnt in sorted(disc_counts.items(), key=lambda x: -x[1]):
        discs = ", ".join(hub_to_discs.get(hub, [hub]))
        print(f"  {hub:35s}  kept={cnt:>4}   ({discs})")

    print()
    print("=== Asset-class composition ===")
    total = sum(asset_class_counter.values())
    for ac, cnt in asset_class_counter.most_common():
        pct = 100 * cnt / total if total else 0
        print(f"  {ac:15s}  {cnt:>4}  ({pct:.0f}%)")

    print()
    print(f"TOTAL kept:  {len(refs)}")
    print(f"Old baseline (hub crawler):  ~42/week")
    print(f"Increase:  {len(refs) / 42:.1f}x" if len(refs) > 0 else "")


if __name__ == "__main__":
    asyncio.run(main())
