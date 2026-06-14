"""Smoke: verify the live region_from_tags() pipeline helper — NO DB writes.

Two checks, both read-only:

1. Doctests on ingest.classifiers.canonical.region_from_tags (the exact
   function ingest_today.py now calls to populate dim_report.region).

2. Reconciliation: for every report that carries region tags, recompute the
   region the *pipeline* would now assign and compare it to the value
   currently in the column. A clean run proves new ingests will land the
   same region the backfill produced — so the fix is durable and consistent.

    python playground/research/smoke_region_from_tags.py
"""
from __future__ import annotations

import doctest
from collections import Counter, defaultdict

from sqlalchemy import text

from ingest.classifiers import canonical
from ingest.classifiers.canonical import region_from_tags
from backfill_region_country import _research_engine


def main() -> None:
    # ── 1. doctests on the live helper ────────────────────────────────────
    failures, ran = doctest.testmod(canonical, verbose=False)
    print(f"doctests : {ran - failures}/{ran} passed"
          + ("" if not failures else f"  [FAIL] {failures} FAILED"))

    # ── 2. reconcile pipeline output vs the populated column ──────────────
    from imdr.config.settings import get_settings  # noqa: PLC0415

    engine = _research_engine(get_settings())
    with engine.connect() as conn:
        rows = conn.execute(text(
            """
            SELECT r.id, r.region, t.tag
            FROM research.dim_report r
            JOIN research.map_report_tag m ON m.report_id = r.id
            JOIN research.dim_tag t ON t.id = m.tag_id AND t.tag_category = 'region'
            """
        )).fetchall()

    col_by_id: dict[int, str] = {}
    tags_by_id: dict[int, list[tuple[str, str]]] = defaultdict(list)
    for rid, region_col, tag in rows:
        col_by_id[rid] = region_col
        tags_by_id[rid].append(("region", tag))

    match = mismatch = 0
    dist: Counter[str] = Counter()
    examples: list[str] = []
    for rid, tags in tags_by_id.items():
        computed = region_from_tags(tags)
        dist[computed] += 1
        if computed == col_by_id[rid]:
            match += 1
        else:
            mismatch += 1
            if len(examples) < 15:
                examples.append(
                    f"  id={rid}: pipeline={computed!r} column={col_by_id[rid]!r} "
                    f"tags={[t for _, t in tags]}"
                )

    total = match + mismatch
    print(f"\nreconcile: {total} reports with region tags")
    print(f"  match    : {match}")
    print(f"  mismatch : {mismatch}")
    print("  pipeline would assign:")
    for val, n in dist.most_common():
        print(f"     {val or '(blank)':<10} {n}")
    if examples:
        print("\n  mismatches (first 15):")
        print("\n".join(examples))

    print("\nNO writes performed (read-only smoke).")
    if mismatch == 0 and failures == 0:
        print("[OK] pipeline helper reproduces the column exactly.")
    else:
        print("[WARN] review mismatches above before relying on the live path.")


if __name__ == "__main__":
    main()
