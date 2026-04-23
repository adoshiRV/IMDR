# FX Rate Pipeline Architecture

End-to-end architecture of the `fx.citi_rate` pipeline (Citi Velocity → [fx.fact_fx_rate](fx_rate_schema.md)). Operational runbook: [fx_rate_operations.md](fx_rate_operations.md).

---

## Data flow

```
           ┌─────────────────────────┐
           │   CitiVelocityClient    │   OAuth2, batching, rate-limit headers
           └────────────┬────────────┘
                        │ fetch_and_parse_batched()
                        ▼
           ┌─────────────────────────┐
           │ CitiVelocityFXRate-     │   per-pair:
           │ Extractor.extract()     │     1 SPOT tag  + 10 FWD_OUTRIGHT + 10 FWD_POINT
           └────────────┬────────────┘
                        │ long-form DataFrame (ts, base, quote, tenor, quote_kind, numeric)
                        ▼
           ┌─────────────────────────┐
           │ pivot_long_to_wide()    │
           │ (rate_translate.py)     │
           └────────────┬────────────┘
                        │ wide DataFrame (ts, base, quote, tenor, mid_rate, fwd_points)
                        ▼
           ┌─────────────────────────┐
           │ FXRatePipeline.transform│   seed dim_currency_pair, resolve
           │   resolve pair_id +     │   vendor_id + frequency_id,
           │   vendor_id + freq_id + │   validate with FXRateCreate
           │   Pydantic validate     │
           └────────────┬────────────┘
                        │ list[FXRateCreate]
                        ▼
           ┌─────────────────────────┐
           │ bulk_merge(_FX_RATE_SPEC│   temp-table MERGE on
           │   chunked_bulk_merge()  │   (pair_id, vendor_id, frequency_id, obs_date, tenor)
           └────────────┬────────────┘
                        │
                        ▼
           ┌─────────────────────────┐
           │    fx.fact_fx_rate      │  (PAGE-compressed, clustered on obs_date,pair_id,tenor)
           └────────────┬────────────┘
                        │ post_load()
                        ▼
           ┌───────────────────────────────────┐
           │  parquet_write() + quality checks │
           │  data/parquet/fx/fact_fx_rate/    │
           │  {BASE}_{QUOTE}/{YYYY-MM}.parquet │
           └───────────────────────────────────┘
```

---

## Module map

| File | Role |
|---|---|
| [rate_translate.py](../../src/imdr/domains/fx/rate_translate.py) | `citi_fx_rate_tag_to_internal()` parses 3 tag families; `pivot_long_to_wide()` collapses to one row per (pair, date, tenor) with `mid_rate` + `fwd_points` columns |
| [extractors_rate.py](../../src/imdr/domains/fx/extractors_rate.py) | `CitiVelocityFXRateExtractor` — pre-flight quota check, per-pair tag batch, `TagQuotaExceeded` re-raise, non-quota errors accumulated in `_errors` |
| [pipeline_rate.py](../../src/imdr/domains/fx/pipeline_rate.py) | `FXRatePipeline(BasePipeline)` — extract→transform→load→post_load; auto-seeds dim_currency_pair, resolves vendor_id + frequency_id |
| [repository_rate.py](../../src/imdr/domains/fx/repository_rate.py) | `_FX_RATE_SPEC` MergeSpec; `FXRateRepository.bulk_upsert()` delegates to `bulk_merge()` |
| [store_rate.py](../../src/imdr/domains/fx/store_rate.py) | Hive-partitioned parquet archive keyed by (base, quote, YYYY-MM) with atomic writes |
| [coverage.py](../../src/imdr/domains/fx/coverage.py) | `get_fx_rate_coverage()` — per-pair date + tenor + row-count panels for the dashboard |
| [clean_fx_fact_fx_rate.py](../../src/imdr/domains/fx/clean_fx_fact_fx_rate.py) | `HardBoundViolationRule` (deletes), `RobustOutlierRule` (flags), `PercentageChangeRule` (flags) |

---

## Tag patterns (per pair)

| Pattern | Qty | Example |
|---|---|---|
| `FX.SPOT.{C1}.{C2}.CITI` | 1 | `FX.SPOT.EUR.USD.CITI` |
| `FX.FORWARD.FWD_OUTRIGHT.{C1}.{C2}.{TENOR}.CITI` | 10 | `FX.FORWARD.FWD_OUTRIGHT.USD.HKD.1M.CITI` |
| `FX.FORWARD.FWD_POINT.{C1}.{C2}.{TENOR}.CITI` | 10 | `FX.FORWARD.FWD_POINT.EUR.USD.1Y.CITI` |

**Total: 21 tags/pair × 19 pairs = 399/day** (all Phase 1 pairs have Citi forwards).

---

## FK resolution (transform step)

Every row needs three FKs resolved before insert:

| FK | How resolved | Failure mode |
|---|---|---|
| `pair_id` | `FXCurrencyPairRepository.all()` → `{(base,quote): id}` cache | Skip row + log `transform_skipped_unmapped_pairs` |
| `vendor_id` | `select DimVendor.vendor_code='citi_velocity'` | Pipeline raises `RuntimeError` — fix seed |
| `frequency_id` | `select DimFrequency.frequency_code='DAILY'` | Pipeline raises `RuntimeError` — apply migration 023 |

Same session is used for dim-seed + FK-cache build to avoid stale reads.

---

## `fwd_points` semantics

- `tenor='SPOT'` → always NULL (enforced by CHECK + Pydantic + model_validator)
- Non-SPOT tenors: expected NON-NULL but tolerant of NULL. Citi occasionally returns `FWD_POINT = ERROR` even when `FWD_OUTRIGHT` succeeds for thin EM tenors.
- Consumers should treat `fwd_points IS NULL` as "missing" rather than "zero".

---

## Quality checks (post-load, flag-don't-block)

Run by `FXRatePipeline._run_quality_checks()` and surfaced in the email report:

| Check | What it flags |
|---|---|
| `PositiveValueCheck(columns=['mid_rate'])` | Non-positive rates (shouldn't happen — CHECK constraint would fail insert, but defensive) |
| `PercentageChangeCheck(group=[pair_id, tenor], threshold=10%)` | Day-over-day jumps > 10% |
| `RobustStatisticalOutlierCheck(group=[pair_id, tenor], n_mad=5.0, trailing_months=6)` | MAD-based outliers on rolling 6-month window |

Per-pair hard-bound violations are handled by the `clean_fx_fact_fx_rate` CLI, not live (different action: DELETE row vs flag).

---

## Idempotency

Re-running the same date is safe:
- MERGE upserts on `(pair_id, vendor_id, frequency_id, obs_date, tenor)` — second run updates `mid_rate` / `fwd_points` in place and resets `updated_at`.
- Parquet dedup: `.drop_duplicates(subset=['obs_date','tenor'], keep='last')` before write.
- `FXCurrencyPairRepository.bulk_seed_from_universe()` checks existence before insert.

---

## Extending

- **Add a pair**: edit `fx.yml` → `fx_rate.pairs` and `fx_rate.expected_ranges` + confirm ccy is in `classifications`. Next run auto-seeds `dim_currency_pair`.
- **Add a tenor**: edit `fx.yml` → `fx_rate.tenors` and [schemas/fx_rate.py](../../src/imdr/schemas/fx_rate.py) `ALLOWED_TENORS`.
- **Add a vendor**: INSERT into `dbo.dim_vendor` + modify the pipeline to resolve by a CLI flag. Schema already supports multi-vendor coexistence via natural key.
- **Switch frequency** (e.g. add intraday snapshots): add rows to `dbo.dim_frequency` (already has `SNAPSHOT`, `MINUTE`, `HOURLY` seeded) and wire a second pipeline or CLI flag.
