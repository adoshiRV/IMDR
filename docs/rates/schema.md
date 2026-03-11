# Rates Domain - Database Schema Reference

**Database:** `IMDR`
**Schema:** `[rates]`
**Engine:** Microsoft SQL Server (Windows Authentication)

---

## Tables

### `[rates].[dim_curve]` - Curve Dimension

Stores the 39 rate curves tracked by IMDR. One row per (ccy, curve) combination. Seeded from `universe/rates.yml` via `scripts/migrations/seed_rates_dim_curve.py`.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | `INT IDENTITY` | NO | Auto-increment primary key |
| `ccy` | `VARCHAR(10)` | NO | ISO currency code, e.g. `USD`, `EUR`, `JPY` |
| `curve` | `VARCHAR(30)` | NO | Curve name, e.g. `SOFR`, `SONIA`, `EURIBOR`, `LIBOR` |
| `curve_type` | `VARCHAR(10)` | NO | `rfr` (risk-free rate / OIS) or `ibor` (interbank offered rate) |
| `curve_status` | `VARCHAR(10)` | NO | `active`, `ceased`, or `reformed` |
| `instrument` | `VARCHAR(20)` | NO | Citi instrument type: `ois` or `swap_libor` |
| `citi_prefix` | `VARCHAR(60)` | NO | Citi Velocity tag prefix, e.g. `RATES.OIS.USD_SOFR` |
| `cessation_date` | `DATE` | YES | Date the rate ceased publication (null if active) |
| `primary_from` | `DATE` | YES | Date this became the primary benchmark for the currency |
| `supersedes` | `VARCHAR(30)` | YES | Which curve this replaced (e.g. SOFR supersedes LIBOR) |
| `superseded_by` | `VARCHAR(30)` | YES | Which curve replaced this one |
| `notes` | `VARCHAR(500)` | YES | Free text context |
| `created_at` | `DATETIMEOFFSET` | NO | Row insertion timestamp |
| `updated_at` | `DATETIMEOFFSET` | NO | Last update timestamp |

**Constraints:**
- `PK` on `id`
- `UNIQUE (ccy, curve)` as `uq_rates_dim_curve`

---

### `[rates].[fact_observation]` - Rate Observations

The primary fact table. Stores rate observations (par rates, spreads, forwards, butterflies, swap spreads, roll & carry) for all curves and tenors.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | `INT IDENTITY` | NO | Auto-increment primary key |
| `curve_id` | `INT` | NO | FK to `[rates].[dim_curve](id)` |
| `ts` | `DATETIMEOFFSET` | NO | Observation timestamp (UTC) |
| `quote` | `VARCHAR(10)` | NO | Quote type: `par`, `spread`, `fwd`, `bfly`, `ssw`, `rc` |
| `tenor` | `VARCHAR(30)` | NO | Tenor encoding (see below) |
| `value` | `FLOAT` | NO | Rate value (percentage points, e.g. 3.85 = 3.85%) |
| `created_at` | `DATETIMEOFFSET` | NO | Row insertion timestamp |
| `updated_at` | `DATETIMEOFFSET` | NO | Last update timestamp |

**Constraints:**
- `PK` on `id`
- `UNIQUE (curve_id, ts, quote, tenor)` as `uq_rates_fact_obs`
- `FK curve_id → [rates].[dim_curve](id)`
- `CHECK quote IN ('par','spread','fwd','bfly','ssw','rc')` as `ck_rates_quote`

**Indexes:**
- `ix_rates_obs_ts` on `(ts DESC)`
- `ix_rates_obs_quote_tenor` on `(quote, tenor, ts) INCLUDE (curve_id, value)`

---

## Internal Schema

All rates data flows through a 6-column model:

| Column | Type | Example | Description |
|---|---|---|---|
| `ts` | datetime (UTC) | `2024-01-15T00:00:00Z` | Observation timestamp |
| `ccy` | string | `USD` | ISO currency code |
| `curve` | string | `SOFR` | Curve name |
| `quote` | string | `par` | Quote type (internal code) |
| `tenor` | string | `5Y` or `2ys10ys` | Encoded tenor |
| `value` | float | `3.85` | Rate in percentage points |

---

## Quote Types

| Internal Code | Citi Code | Meaning | Tenor Shape |
|---|---|---|---|
| `par` | `PAR` | Par swap rate | Single: `5Y`, `10Y` |
| `ssw` | `SWAP_SPREAD` | Swap spread vs govies | Single: `5Y`, `10Y` |
| `rc` | `ROLL_CARRY` | Roll & carry | Single: `5Y`, `10Y` |
| `spread` | `CURVES` | Curve spread (e.g. 2s10s) | 2-tenor: `2ys10ys` |
| `fwd` | `FWD` | Forward starting swap | 2-tenor: `5ys5ys` |
| `bfly` | `BFLY` | Butterfly | 3-tenor: `2ys5ys10ys` |

---

## Tenor Encoding

| Quote | Storage Format | Display Format | Example |
|---|---|---|---|
| par / ssw / rc | Uppercase passthrough | Same | `5Y`, `10Y`, `18M` |
| spread | Lowercase + `s` separator | Numeric + `s` | `2ys10ys` → `2s10s` |
| fwd | Lowercase + `s` separator | Concatenated | `5ys5ys` → `5y5y` |
| bfly | Lowercase + `s` separator | Numeric + `s` | `2ys5ys10ys` → `2s5s10s` |

---

## Universe Coverage

**39 curves** across **22 currencies**, split by type:

### RFR (OIS) — 16 curves

| Currency | Curve | Status | Primary From | Supersedes |
|---|---|---|---|---|
| USD | SOFR | active | 2023-07-01 | LIBOR |
| USD | FEDFUND | active | — | — |
| EUR | EUROSTR | active | 2022-01-03 | EONIA |
| EUR | EONIA | ceased | — | — |
| GBP | SONIA | active | 2022-01-01 | GBP_LIBOR |
| JPY | TONAR | active | 2022-01-01 | JPY_LIBOR |
| JPY | TONAR_JSCC | active | — | — |
| JPY | TONAR_LCH | active | — | — |
| CHF | SARON | active | 2022-01-01 | CHF_LIBOR |
| AUD | AONIA | active | — | — |
| NZD | NZIONA | active | — | — |
| CAD | CORRA | active | 2024-06-28 | CDOR |
| NOK | NOWA | active | — | — |
| SEK | STINA | active | — | — |
| SGD | SORA | active | 2023-07-01 | SOR |
| THB | THOR | active | 2023-07-01 | THBFIX |

### IBOR (SWAP_LIBOR) — 23 curves

| Currency | Curve | Status | Cessation | Notes |
|---|---|---|---|---|
| USD | LIBOR | ceased | 2023-06-30 | Historical only |
| EUR | EURIBOR | reformed | — | Hybrid methodology since 2019 |
| GBP | GBP_LIBOR | ceased | 2024-03-28 | Synthetic ceased Mar 2024 |
| JPY | JPY_LIBOR | ceased | 2021-12-31 | — |
| CHF | CHF_LIBOR | ceased | 2021-12-31 | — |
| AUD | BBSW | active | — | Dual-rate market |
| NZD | BKBM | active | — | — |
| CAD | CDOR | ceased | 2024-06-28 | — |
| NOK | NIBOR | active | — | — |
| SEK | STIBOR | active | — | — |
| SGD | SOR | ceased | 2023-06-30 | — |
| THB | THBFIX | ceased | 2023-06-30 | — |
| CNH | CNH_HIBOR | active | — | — |
| CNY | SHIBOR | active | — | — |
| CNY | NDIRS | active | — | — |
| HKD | HIBOR | active | — | — |
| IDR | JIBOR | active | — | — |
| INR | MIFOR | reformed | — | References SOFR since 2023 |
| KRW | CD | active | — | — |
| MYR | KLIBOR | active | — | — |
| PHP | PHIREF | active | — | — |
| TWD | TAIBOR | active | — | — |
| VND | VND_REF | active | — | — |

---

## Maturities

- **OIS**: 44 tenors — 1D, 1W, 2W, 3W, 1M–11M, 1Y, 15M, 18M, 21M, 2Y–20Y, 25Y, 30Y, 35Y, 40Y, 45Y, 50Y
- **SWAP_LIBOR**: 36 tenors — 1W, 1M–11M, 1Y–20Y, 25Y, 30Y, 40Y, 50Y

---

## Common Queries

```sql
-- Latest par rate for USD SOFR 5Y
SELECT TOP 1 o.ts, o.value
FROM [rates].[fact_observation] o
JOIN [rates].[dim_curve] c ON o.curve_id = c.id
WHERE c.ccy = 'USD' AND c.curve = 'SOFR'
  AND o.quote = 'par' AND o.tenor = '5Y'
ORDER BY o.ts DESC;

-- Full par curve for USD SOFR on a specific date
SELECT o.tenor, o.value
FROM [rates].[fact_observation] o
JOIN [rates].[dim_curve] c ON o.curve_id = c.id
WHERE c.ccy = 'USD' AND c.curve = 'SOFR'
  AND o.quote = 'par'
  AND CAST(o.ts AS DATE) = '2024-01-15'
ORDER BY o.tenor;

-- Cross-curve comparison: SOFR vs LIBOR par 5Y
SELECT o.ts, c.curve, o.value
FROM [rates].[fact_observation] o
JOIN [rates].[dim_curve] c ON o.curve_id = c.id
WHERE c.ccy = 'USD' AND c.curve IN ('SOFR', 'LIBOR')
  AND o.quote = 'par' AND o.tenor = '5Y'
ORDER BY o.ts, c.curve;

-- Observation count per curve
SELECT c.ccy, c.curve, COUNT(*) AS obs_count
FROM [rates].[fact_observation] o
JOIN [rates].[dim_curve] c ON o.curve_id = c.id
GROUP BY c.ccy, c.curve
ORDER BY c.ccy, c.curve;

-- Gap detection: dates with fewer observations than expected
SELECT CAST(o.ts AS DATE) AS obs_date, COUNT(*) AS row_count
FROM [rates].[fact_observation] o
WHERE o.quote = 'par'
GROUP BY CAST(o.ts AS DATE)
HAVING COUNT(*) < 100
ORDER BY obs_date DESC;
```

---

## Expected Value Ranges

Each quote type has configured bounds for quality check validation. Values outside these ranges are flagged (but not rejected) during pipeline runs. Configured in `src/imdr/universe/rates.yml`:

| Quote | Min | Max | Notes |
|---|---|---|---|
| `par` | -3.0 | 20.0 | Par swap rates (percentage points) |
| `spread` | -500.0 | 500.0 | Curve spreads (basis points) |
| `fwd` | -5.0 | 25.0 | Forward rates (percentage points) |
| `bfly` | -100.0 | 100.0 | Butterfly spreads (basis points) |
| `ssw` | -500.0 | 500.0 | Swap spreads (basis points) |
| `rc` | -200.0 | 200.0 | Roll & carry (basis points) |

These use the shared `ExpectedRange` model (`src/imdr/universe/base.py`), matching the FX domain's per-symbol range pattern.

---

## Cache Files

| File | Purpose |
|---|---|
| `data/cache/rates/empty_combos.json` | Tracks `(ccy, curve, quote)` combos known to return 0 rows from the API. Used to skip wasted API calls. Auto-retries after 30 days. |
| `data/cache/rates/rates_tags.json` | Tag discovery cache (Citi tag listing). Used by `RatesTagDiscovery`. |

---

## Audit

Pipeline runs are tracked in `[audit].[pipeline_runs]` with `pipeline_name = 'rates.historical'` and `domain = 'rates'`. See `docs/fx/schema.md` for the full audit table schema.
