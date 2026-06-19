"""Phase-8 1-week full smoke: discover + classify ALL BofA reports from
the last 7 days across all production hubs. NO PDF downloads (the fetch
path is already proven); this audits VOLUME + COMPOSITION + the drop
funnel before we go down the prod order.

Outputs:
  * per-hub discovery funnel (parsed / dropped / kept) — from the crawler
  * kept-report composition by asset_class / hub / series / date
  * a manifest CSV (id, date, hub, series, title, asset_class, country,
    tags, pdf_url) at bofa_explore/smoke_1week_manifest.csv

Usage:
    C:/Users/adoshi/.conda/envs/imdr/python.exe \
        playground/research/_smoke_bofa_1week.py [SINCE_YYYY-MM-DD]
"""
from __future__ import annotations

import asyncio
import csv
import os
import sys
from collections import Counter
from datetime import date, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROFILE = HERE / "profiles" / "bofa"
OUT = HERE / "bofa_explore"

if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from ingest._console import force_utf8_stdout  # noqa: E402
force_utf8_stdout()

_ENV = HERE.parent.parent / ".env"
if _ENV.exists():
    for _l in _ENV.read_text(encoding="utf-8").splitlines():
        _l = _l.strip()
        if _l and not _l.startswith("#") and "=" in _l:
            k, _, v = _l.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

from ingest.crawler_bofa import discover_reports  # noqa: E402
from ingest.classifiers.bofa import classify as classify  # noqa: E402

# Last 1 week. Today is the run date; default since = today - 7.
if len(sys.argv) > 1:
    SINCE = datetime.strptime(sys.argv[1], "%Y-%m-%d").date()
else:
    # 2026-06-15 run → 2026-06-08
    SINCE = date(2026, 6, 8)
UNTIL = date(2026, 6, 15)


async def main() -> None:
    OUT.mkdir(exist_ok=True)
    print("=" * 78)
    print(f"  BofA 1-WEEK FULL SMOKE — all hubs, {SINCE} → {UNTIL} (no PDF dl)")
    print("=" * 78)
    refs = await discover_reports(
        profile_dir=PROFILE, since=SINCE, until=UNTIL, resolve_urls=True,
    )

    # Classify every kept report.
    rows = []
    for r in refs:
        res = classify(r)
        rows.append({
            "uuid": r.uuid, "date": r.publish_date.isoformat(),
            "hub": r.hub, "series": r.series, "title": r.title,
            "asset_class": res.asset_class, "country": res.country_code or "",
            "analyst": r.analyst_primary,
            "tags": "; ".join(f"{t.category}={t.value}" for t in res.tags),
            "pdf_url": r.pdf_url,
        })

    print()
    print("=" * 78)
    print(f"  KEPT: {len(rows)} reports in the {SINCE}→{UNTIL} window")
    print("=" * 78)
    print("  --- by asset_class (classifier) ---")
    for ac, n in Counter(x["asset_class"] for x in rows).most_common():
        print(f"    {ac:>12}  {n:>4}")
    print("  --- by hub ---")
    for hub, n in Counter(x["hub"] for x in rows).most_common():
        print(f"    {hub:>28}  {n:>4}")
    print("  --- by date ---")
    for d, n in sorted(Counter(x["date"] for x in rows).items()):
        print(f"    {d}  {n:>4}")
    print("  --- by country (top 12) ---")
    for c, n in Counter(x["country"] for x in rows if x["country"]).most_common(12):
        print(f"    {c:>6}  {n:>4}")
    print("  --- top series (top 20) ---")
    for s, n in Counter(x["series"] for x in rows).most_common(20):
        print(f"    {n:>3}  {s[:50]}")

    # Manifest CSV
    man = OUT / "smoke_1week_manifest.csv"
    with man.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else
                           ["uuid", "date", "hub", "series", "title",
                            "asset_class", "country", "analyst", "tags", "pdf_url"])
        w.writeheader()
        w.writerows(rows)
    print(f"\n  manifest -> {man}")

    # Full title list so we can eyeball "what it is".
    print("\n  --- ALL kept titles (newest first) ---")
    for x in sorted(rows, key=lambda r: r["date"], reverse=True):
        print(f"    [{x['date']}] [{x['asset_class']:>10}] "
              f"[{x['country'] or '--':>4}] {x['title'][:66]}")


if __name__ == "__main__":
    asyncio.run(main())
