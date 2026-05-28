# Intra-day research ingest with pre-fetch dedup

- **Filed**: 2026-05-22
- **Status**: deferred (production optimization — wait for promotion out of `playground/`)
- **Triggered by**: 5-vendor backfill discussion 2026-05-22 — the realisation that publishing happens through the day & night, and we'd want to capture it without doing one big batch every 24h

## Problem

The current daily ingest pattern is **one full-window pull, once a day**:

```
ingest_today_{vendor}.py    today-1 .. today    full discovery + fetch
```

This has two suboptimal properties for a production setup:

1. **Latency.** A report published at 09:00 sits unindexed until the daily run at, say, 23:00. Up to a 14h gap.
2. **Vendor pattern.** All ~340 PDF downloads happen in one ~2h window. With our 3-10s pacing it still looks human-ish, but it's a bursty pattern. A trickle of 10-30 PDFs every 4 hours would look more like a human reader checking research throughout the day.

What we want instead: **run every 2-6 hours, fetch only what's actually new since the last run**.

## What's already in place

The pipeline already has the natural fast/slow split:

- **Phase A — metadata** (cheap, ~30s–2min/vendor): listing-API + discovery filter + classifier + relevance filter.
- **Phase B — fetch + ingest** (expensive, ~24s/PDF): paced PDF download + parse + chunk + embed + MSSQL + Qdrant.

The relevance filter (drops single-name equity) lives in Phase A and is fast. The 3-10s `research_pacing_seconds_{min,max}` jitter lives in Phase B (`ingest_one()` in `pipeline.py`).

**Idempotency exists** but in the wrong place — it's inside `ingest_one()` *after* `parse()`. So a previously-ingested report still pays the fetch cost before being short-circuited. Today's ANZ run had 2 `[DUP]` rows that wasted ~48s of PDF downloads.

## Missing piece: pre-fetch dedup

A short-uuid lookup against `research.dim_report.pdf_path` would let us skip dups *before* Phase B even runs. The pattern already exists inline in
[`playground/research/test_qdrant_e2e.py:92-110`](../../../playground/research/test_qdrant_e2e.py#L92-L110):

```python
existing = conn.execute(text("""
    SELECT r.pdf_path FROM research.dim_report r
    JOIN dbo.dim_vendor v ON v.id = r.vendor_id
    WHERE v.vendor_code = :c AND r.pdf_path IS NOT NULL
"""), {"c": vendor_code}).all()
existing_shorts = {Path(p).stem.rsplit("_", 1)[-1] for (p,) in existing}
fresh = [r for r in refs if _short(r.uuid) not in existing_shorts]
```

One bulk SELECT per vendor per run, constant time, then `O(N)` set lookup.

Trade-off the heuristic accepts: it trusts vendor uuids to be stable across listings. They are for all 6 current vendors today. The `content_hash`-based check inside `ingest_one` remains the final safety net for edge cases (vendor re-issues a report under a new uuid → content_hash catches it after fetch).

## Implementation plan (for when this gets picked up)

1. **Extract the dedup heuristic** from `test_qdrant_e2e.py:92-110` into a shared helper, e.g.
   `playground/research/ingest/dedup.py: skip_known_uuids(engine, vendor_code, refs) -> tuple[list[ref], list[ref]]`.
2. **Wire it into all 6 daily ingest scripts** between the relevance filter and the limit cap:
   ```python
   refs = await discover_reports(...)
   if settings.research_drop_single_name_equity:
       refs, _ = apply_relevance_filter(...)
   refs, skipped = skip_known_uuids(engine, VENDOR_CODE, refs)
   if skipped:
       print(f"  pre-fetch dedup: skipped {len(skipped)} known refs, {len(refs)} new")
   if limit:
       refs = refs[:limit]
   ```
3. **Schedule** via Windows Task Scheduler (single trigger, repeats every 4-6 hours, runs
   `playground/research/backfill_all_vendors.ps1` — already supports `-Vendors` for selective re-runs).
4. **Optional Step**: per-vendor schedules. Some vendors publish more in Asia hours
   (ANZ, Nomura) vs US hours (Goldman, MS, Barclays). Could stagger schedules per vendor to
   match publication patterns — but probably YAGNI until we measure it.

## Why deferred

* The research module is still under `playground/` per the
  [playground-only rule](../../../CLAUDE.md). Wiring a scheduled
  production task to playground code crosses a line that should wait
  until research is promoted to `src/imdr/research/`.
* The current 24h pull works fine for validating retrieval quality.
* Scheduling adds operational complexity (failure handling, alerting,
  Task Scheduler state) that's only worth it once the corpus is being
  consumed in anger.

## Out of scope

- Detecting **vendor re-issues** of a report under a new uuid. The
  content_hash check inside `ingest_one` is the right place — it
  already does this; the new pre-fetch dedup just avoids paying the
  fetch cost on the cheap-detection cases.
- A pull-API for "what's been published since timestamp X". Some
  vendors expose this (Nomura's ES query supports `range.gte`); using
  it would be even faster than full discovery + dedup. Worth
  investigating per-vendor when this task is picked up.

## Estimated outcome

With dedup + 4× daily schedule:

| Run | Avg refs discovered | Already in DB | New | Phase B time |
|---|---:|---:|---:|---:|
| 08:00 | ~80 (overnight backlog) | 0 | 80 | ~35 min |
| 12:00 | ~85 | ~80 | 5 | ~3 min |
| 16:00 | ~90 | ~85 | 5 | ~3 min |
| 20:00 | ~95 | ~90 | 5 | ~3 min |

vs current pattern: one ~2h burst at 23:00. Total daily fetch time is roughly the
same, just spread across the day and bounded per-run.
