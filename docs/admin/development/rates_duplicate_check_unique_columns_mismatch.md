# Tech Debt — `rates.historical` DuplicateCheck uses stale uniqueness definition

- **Date filed**: 2026-05-18
- **Status**: open
- **Triggered by**: KRW.CD hourly backfill (2026-05-06 → 2026-05-15). Every per-day run of the backfill emitted `health_checks_failed` with `Found 851 duplicate group(s)` — same count across all 8 days, suggesting a pre-existing table state, not a backfill bug.
- **Owner**: rates ingest
- **Severity**: 🟡 false-positive failed health check on every `rates.historical` run; **no data correctness impact** (table-level uniqueness is enforced correctly at the DB layer)

## TL;DR

The DB's physical unique constraint on `rates.fact_observation` is:

```
uq_rates_fact_obs: (curve_id, vendor_id, ts, quote, tenor, frequency_id)
```

But the DuplicateCheck wired in [`scripts/rates/citi`](../../../src/imdr/domains/rates/pipeline.py) reads `unique_columns` from [`src/imdr/config/pipelines.yml:160-164`](../../../src/imdr/config/pipelines.yml#L160-L164):

```yaml
unique_columns:
  - curve_id
  - ts
  - quote
  - tenor
```

**Missing `vendor_id` and `frequency_id`.** The check flags any pair of legitimate co-sourced rows (same fact, different vendor, OR same fact, different cadence) as a duplicate. The result is a permanent failed-health-check footer on every `rates.historical` run, even when the data is correctly upserted.

## Evidence

DB query against today's table:

```sql
SELECT vendor_id, COUNT(*) FROM rates.fact_observation GROUP BY vendor_id;
-- 1 (citi_velocity): 19,356,750
-- 4 (bloomberg):        524,050
```

Drilling into a sample duplicate group:

```sql
SELECT id, vendor_id, value, created_at
FROM rates.fact_observation
WHERE curve_id = 1 AND ts = '2023-11-15 00:00:00 +00:00'
  AND quote = 'par' AND tenor = '5Y';
-- 1069644 | vendor_id=1 (Citi) | value=4.23945 | 2026-03-23
-- 6319272 | vendor_id=4 (BBG)  | value=4.235   | 2026-04-29
```

Two rows, same `(curve_id, ts, quote, tenor)`, **different vendor**. Both legitimate; the small value gap (~5 bp) is the expected mid-market mismatch between two pricing sources. The DB allows it under `uq_rates_fact_obs` because that constraint includes `vendor_id`. The health check is unaware of `vendor_id` so it groups them and reports a duplicate.

## Why the count is constant (851)

The 851 figure is a static count of rows in the table where two vendors have written the same `(curve_id, ts, quote, tenor)` natural key. Today that's:

- ~524K Bloomberg rows (vendor_id=4), the smaller set, defines the upper bound on potential overlaps.
- Of those, ~851 collide with a Citi row on the same key — roughly the BBG-mirror IRS feed's overlap with Citi `RATES.SWAP_LIBOR.*` curves for shared dates/tenors.

Every BD of the KRW backfill reported the same 851 because the backfill itself didn't add any cross-vendor overlap rows — KRW.CD `vendor_id` is set to Citi (1) for both the daily and hourly fires, and the BBG KRW IRS feed lands on a **different curve_id** (48: `BBG:KRW-91D_CD-3M`) rather than on curve_id 35. So the backfill grew vendor_id=1 rows on curve_id=35 with no new cross-vendor collisions.

The number will move as: (a) new Bloomberg-sourced curves are introduced that share a key shape with an existing Citi curve, or (b) the BBG-mirror coverage extends back into dates also covered by Citi.

## Other false-positive sources

The same stale `unique_columns` also misses **frequency overlap**. At 09:00 KST the daily fire writes one row at `frequency_id=DAILY` (5) and the hourly fire writes one row at `frequency_id=HOURLY` (4), same `(curve_id, ts, quote, tenor)`. Both are correct; `uq_rates_fact_obs` permits them via `frequency_id`. The DuplicateCheck flags them.

The combined effect is that every `rates.historical` run with any intraday cohort, against a table that has even a single Bloomberg co-sourced fact, will fail the health check. That's the current steady state.

## The fix

One-line change in [`src/imdr/config/pipelines.yml`](../../../src/imdr/config/pipelines.yml):

```yaml
rates.historical:
  ...
  unique_columns:
    - curve_id
    - vendor_id      # add
    - ts
    - quote
    - tenor
    - frequency_id   # add
```

This brings the check's grouping in line with `uq_rates_fact_obs`. Any real duplicate (a violation of the DB's actual constraint) would still surface; the false positives go away.

### Cost / risk of the fix

- **Cost**: yaml edit, no code change, no migration. Health check re-runs on the next ingest will pass cleanly (or surface real duplicates, which would be a separate finding).
- **Risk**: low. The check becomes strictly more conservative than the DB constraint allows — it cannot produce false negatives by accident, because if a row violates `(curve_id, vendor_id, ts, quote, tenor, frequency_id)` uniqueness it would already have been rejected by the MERGE.
- **Side effect**: the health check's query becomes a wider GROUP BY (6 columns instead of 4) but the volume is comparable.

### Should we also verify the table state?

Once the check is fixed, it should pass. If it doesn't, that means there's a **genuine** duplicate slipping past `uq_rates_fact_obs` (which shouldn't be possible) and warrants its own investigation. A pre-fix sanity check is reasonable:

```sql
SELECT curve_id, vendor_id, ts, quote, tenor, frequency_id, COUNT(*)
FROM rates.fact_observation
GROUP BY curve_id, vendor_id, ts, quote, tenor, frequency_id
HAVING COUNT(*) > 1;
-- expected: 0 rows
```

If that returns rows, the index isn't being honored (extremely unlikely given the constraint is enforced) and the fix needs to be paired with a data cleanup. If it returns 0 rows as expected, the fix is purely cosmetic-correctness on the health check.

## Why this matters

The failed health check is currently visible only in run logs and the warning-level structlog line. It does **not** appear in ingest email summaries today — the rates ingest formatter focuses on `extraction_errors`, `tag_errors`, and `coverage_gap`, not on the post-load health check. So this finding has been silently degrading every `rates.historical` JSONL log for months without anyone noticing. Two consequences:

1. **Signal-to-noise**: future operators reading the run logs will see `health_checks_failed` and have to decide whether to investigate. The right reaction (today) is "ignore, known false positive" — but that's institutional knowledge, not encoded.
2. **Alarm fatigue**: if a real duplicate condition ever did arise, it would be lost in the noise.

The fix is small enough that it should be addressed in the same pass as a related rates health-check edit, rather than waiting.

## Related

- `docs/admin/development/rates_hourly_cohort_drift.md` — adjacent finding from the same KRW.CD investigation. Same script, different concern.
- `migrations/` — search for the `uq_rates_fact_obs` migration to confirm the canonical constraint definition lives in version control.
