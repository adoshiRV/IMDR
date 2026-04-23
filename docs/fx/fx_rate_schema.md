# FX Rate Schema — `fx.fact_fx_rate`

Daily EOD spot + forward outright + forward points for FX pairs, sourced from Citi Velocity. Created 2026-04-22 via migration [024_create_fx_fact_fx_rate.sql](../../migrations/024_create_fx_fact_fx_rate.sql).

Full column-level semantics, FK relationships, and index design.

---

## Columns

| Column | Type | Null | Description |
|---|---|---|---|
| `id` | INT IDENTITY | NO | PK (NONCLUSTERED) |
| `pair_id` | INT | NO | FK → [fx.dim_currency_pair(id)](../../migrations/004_create_fx_dim_currency_pair.sql) |
| `vendor_id` | INT | NO | FK → [dbo.dim_vendor(id)](../../migrations/018_create_dim_vendor.sql) — typically `citi_velocity` |
| `frequency_id` | TINYINT | NO | FK → [dbo.dim_frequency(id)](../../migrations/023_create_dim_frequency.sql) — `DAILY` for Citi EOD |
| `obs_date` | DATE | NO | Observation date (UTC day) |
| `tenor` | VARCHAR(5) | NO | One of `SPOT, ON, 1W, 1M, 3M, 6M, 9M, 1Y, 2Y, 5Y, 10Y` |
| `mid_rate` | DECIMAL(18, 8) | NO | Spot mid (tenor=SPOT) or forward outright mid; CHECK `> 0` |
| `fwd_points` | DECIMAL(18, 10) | YES | Forward points for non-SPOT tenors; NULL for `SPOT` rows |
| `created_at` | DATETIMEOFFSET | NO | DEFAULT `SYSDATETIMEOFFSET()` |
| `updated_at` | DATETIMEOFFSET | NO | DEFAULT `SYSDATETIMEOFFSET()` |

---

## Constraints

- **Primary key**: `pk_fx_fact_fx_rate` on `id` — NONCLUSTERED per [schema_conventions.md §5.1](../admin/schema_conventions.md) (clustered index is on the natural time-series access path, not the surrogate).
- **Unique / natural key**: `uq_fx_fact_fx_rate` on `(pair_id, vendor_id, frequency_id, obs_date, tenor)`. Allows coexistence of DAILY + future HOURLY rows per pair.
- **Foreign keys**:
  - `FK_fx_fact_fx_rate_pair` → `fx.dim_currency_pair(id)`
  - `FK_fx_fact_fx_rate_vendor` → `dbo.dim_vendor(id)`
  - `FK_fx_fact_fx_rate_frequency` → `dbo.dim_frequency(id)`
- **CHECK constraints**:
  - `ck_fx_fact_fx_rate_mid_rate_positive`: `mid_rate > 0` — domain invariant (FX rates are always positive).
  - `ck_fx_fact_fx_rate_spot_points_null`: `tenor <> 'SPOT' OR fwd_points IS NULL` — spot has no forward points by construction.

---

## Indexes

| Index | Columns | Purpose |
|---|---|---|
| `ix_fx_fact_fx_rate_cluster` (clustered) | `(obs_date, pair_id, tenor)` | Time-series range scan is the dominant access pattern |
| `ix_fx_fact_fx_rate_pair` | `(pair_id)` | FK index (§5.4) |
| `ix_fx_fact_fx_rate_vendor` | `(vendor_id)` | FK index |
| `ix_fx_fact_fx_rate_frequency` | `(frequency_id)` | FK index |

All PAGE-compressed per [schema_conventions.md §5.2](../admin/schema_conventions.md).

---

## Relationship Diagram

```
                                 ┌──────────────────────────┐
                                 │    dbo.dim_currency      │   (ISO ccy codes)
                                 └────────┬─────────────────┘
                                          │
                    ┌─────────────────────┴─────────────────────┐
                    │                                           │
         ┌──────────▼──────────────┐              ┌─────────────▼─────────┐
         │  fx.dim_currency_pair   │              │   dbo.dim_vendor      │
         │  id, base_ccy, quote_   │              │   id, vendor_code     │
         │  ccy, ccy_class         │              │   = 'citi_velocity'   │
         └────────┬────────────────┘              └─────────────┬─────────┘
                  │                                             │
                  │                           ┌─────────────────┘
                  │                           │
                  ▼                           ▼
         ┌────────────────────────────────────────────────────┐
         │               fx.fact_fx_rate                      │
         │  (pair_id, vendor_id, frequency_id, obs_date, tenor│
         │   mid_rate, fwd_points)                            │
         └────────────────────────▲───────────────────────────┘
                                  │
                 ┌────────────────┴───────────────────┐
                 │          dbo.dim_frequency         │
                 │  id, frequency_code = 'DAILY'      │
                 └────────────────────────────────────┘
```

---

## Tenor Enum (curated Phase 1 grid)

Citi offers 29 tenors on `FX.FORWARD.FWD_OUTRIGHT` (see [citi_velocity_fx.md](citi_velocity_fx.md)). Phase 1 uses a curated subset:

| Tenor | Description |
|---|---|
| `SPOT` | Spot mid (fwd_points NULL) |
| `ON`   | Overnight forward |
| `1W`   | One week |
| `1M`   | One month |
| `3M`   | Three months |
| `6M`   | Six months |
| `9M`   | Nine months |
| `1Y`   | One year |
| `2Y`   | Two years |
| `5Y`   | Five years |
| `10Y`  | Ten years |

Adding tenors: extend [src/imdr/universe/fx.yml](../../src/imdr/universe/fx.yml) `fx_rate.tenors`, and update [src/imdr/schemas/fx_rate.py](../../src/imdr/schemas/fx_rate.py) `ALLOWED_TENORS`.

---

## Pair Universe (19)

Tracked in [fx.yml fx_rate.pairs](../../src/imdr/universe/fx.yml). Citi ordering is used verbatim (EUR, GBP, AUD, NZD as non-USD base; rest USD-base).

- **G10 (10)**: EUR/USD, GBP/USD, AUD/USD, NZD/USD, USD/JPY, USD/CHF, USD/CAD, USD/NOK, USD/SEK, USD/CNH
- **EM deliverable (2)**: USD/HKD, USD/SGD
- **EM NDF (7)**: USD/KRW, USD/TWD, USD/THB, USD/IDR, USD/PHP, USD/INR, USD/MYR

Phase 2 candidates (explicitly deferred): LatAm (MXN, BRL, CLP, COP, ARS), EMEA (ZAR, TRY), CEE (PLN, HUF, CZK), MEA (ILS), VND (spot-only on Citi).

---

## Daily Tag Volume

- 19 spot tags + 19 × 10 outright + 19 × 10 points = **399 Citi tags/day**
- Well under the 100K/24h cumulative quota. Full detail in [citi_api_limits.md](../admin/citi_api_limits.md).

---

## Sources

| Module | Purpose |
|---|---|
| [src/imdr/models/fx_rate.py](../../src/imdr/models/fx_rate.py) | SQLAlchemy ORM |
| [src/imdr/schemas/fx_rate.py](../../src/imdr/schemas/fx_rate.py) | Pydantic Create/Response |
| [src/imdr/domains/fx/pipeline_rate.py](../../src/imdr/domains/fx/pipeline_rate.py) | ETL orchestrator |
| [src/imdr/domains/fx/extractors_rate.py](../../src/imdr/domains/fx/extractors_rate.py) | Citi Velocity extractor |
| [src/imdr/domains/fx/rate_translate.py](../../src/imdr/domains/fx/rate_translate.py) | Tag parser + pivot |
| [src/imdr/domains/fx/repository_rate.py](../../src/imdr/domains/fx/repository_rate.py) | Bulk merge repository |
| [src/imdr/domains/fx/store_rate.py](../../src/imdr/domains/fx/store_rate.py) | Parquet archive |

See [fx_rate_operations.md](fx_rate_operations.md) for runbook and [fx_rate_pipeline.md](fx_rate_pipeline.md) for architectural details.
