# Rates Domain - Database Schema Reference

**Database:** `IMDR`
**Schema:** `[rates]`
**Engine:** Microsoft SQL Server (Windows Authentication)

---

## Tables

### `[rates].[dim_curve]` - Curve Dimension

Stores the 65 rate curves tracked by IMDR (43 from `universe/rates.yml` — 16 OIS, 23 SWAP_LIBOR, 4 BASIS_SWAPS — plus BBG cross-currency basis + xccy curves seeded by separate vendor scripts). One row per (ccy, curve) combination.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | `INT IDENTITY` | NO | Auto-increment primary key |
| `ccy` | `VARCHAR(10)` | NO | ISO currency code, e.g. `USD`, `EUR`, `JPY` |
| `curve` | `VARCHAR(30)` | NO | Curve name, e.g. `SOFR`, `SONIA`, `EURIBOR`, `LIBOR` |
| `curve_type` | `VARCHAR(10)` | NO | `rfr` (OIS), `ibor` (IBOR swap), `basis` (tenor or cross-currency basis), `ccs` (cross-currency swap) |
| `curve_status` | `VARCHAR(10)` | NO | `active`, `ceased`, or `reformed` |
| `instrument` | `VARCHAR(20)` | NO | `ois` (Citi OIS), `swap_libor` (Citi IBOR swap), `basis_swaps` (Citi tenor basis), `basis_swap` (BBG x-ccy basis), `xccy_swap` (BBG cross-currency swap) |
| `citi_prefix` | `VARCHAR(60)` | NO | Citi Velocity tag prefix, e.g. `RATES.OIS.USD_SOFR` |
| `country_id` | `TINYINT` | NO | FK to `[dbo].[dim_country](id)` |
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
- `FK country_id → [dbo].[dim_country](id)` as `fk_rates_dim_curve_country`

> Migration 044 (2026-05) removed legacy `market_code` + `market_id` columns and replaced with `country_id`. See [country_anchor_design.md](../admin/calendar/country_anchor_design.md).

---

### `[rates].[fact_observation]` - Rate Observations

The primary fact table. Stores rate observations (par rates, spreads, forwards, butterflies, swap spreads, roll & carry) for all curves and tenors.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | `INT IDENTITY` | NO | Auto-increment primary key |
| `curve_id` | `INT` | NO | FK to `[rates].[dim_curve](id)` |
| `ts` | `DATETIMEOFFSET` | NO | Observation timestamp (UTC) |
| `quote` | `VARCHAR(10)` | NO | Quote type: `par`, `spread`, `fwd`, `bfly`, `ssw`, `rc`, `basis` |
| `tenor` | `VARCHAR(30)` | NO | Tenor encoding (see below) |
| `value` | `FLOAT` | NO | Rate value (percentage points, e.g. 3.85 = 3.85%) |
| `created_at` | `DATETIMEOFFSET` | NO | Row insertion timestamp |
| `updated_at` | `DATETIMEOFFSET` | NO | Last update timestamp |

**Constraints:**
- `PK` on `id`
- `UNIQUE (curve_id, ts, quote, tenor)` as `uq_rates_fact_obs`
- `FK curve_id → [rates].[dim_curve](id)`
- `CHECK quote IN ('par','spread','fwd','bfly','ssw','rc','basis')` as `ck_rates_quote`

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

### Multi-Tenor Tag Construction

Multi-tenor quotes (fwd, spread, bfly) use pre-defined combos from `multi_tenor_combos` in `rates.yml` rather than single maturities. The Citi API tag format appends all legs:

| Quote | Citi Tag Example | DB Tenor |
|---|---|---|
| fwd | `RATES.OIS.USD_SOFR.FWD.5Y.5Y` | `5ys5ys` |
| spread | `RATES.OIS.USD_SOFR.CURVES.2Y.10Y` | `2ys10ys` |
| bfly | `RATES.OIS.USD_SOFR.BFLY.2Y.5Y.10Y` | `2ys5ys10ys` |

Standard combos: 17 FWD (1Y1Y through 10Y20Y), 7 CURVES (2s5s through 10s30s), 3 BFLY (2-5-10, 2-10-30, 5-10-30).

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

## Swaption Vol Tables

### `[rates].[dim_vol_surface]` - Vol Surface Dimension

One row per unique vol surface: (ccy, data_type, qualifier). Auto-seeded from `universe/rates.yml` vol section during pipeline runs.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | `INT IDENTITY` | NO | Auto-increment primary key |
| `ccy` | `VARCHAR(3)` | NO | ISO currency code |
| `data_type` | `VARCHAR(15)` | NO | `ATM`, `ATM_RFR`, `REALIZED`, `REALIZED_RFR`, `VOL_RATIO`, `VOL_RATIO_RFR` |
| `quote_type` | `VARCHAR(12)` | NO | `BLACK`, `NORMAL`, `FWDPREMIUM`, `PREMIUM` for ATM/ATM_RFR; `''` otherwise |
| `vol_window` | `VARCHAR(3)` | NO | `1M`, `3M`, `6M`, `1Y` for REALIZED/VOL_RATIO; `''` otherwise |
| `freq` | `VARCHAR(6)` | NO | `ANNUAL`, `DAILY` for REALIZED; `''` otherwise |
| `is_rfr` | `BIT` | NO | 1 if RFR variant, 0 otherwise |
| `created_at` | `DATETIMEOFFSET` | NO | Row insertion timestamp |
| `updated_at` | `DATETIMEOFFSET` | NO | Last update timestamp |

**Constraints:**
- `PK` on `id`
- `UNIQUE (ccy, data_type, quote_type, vol_window, freq)` as `uq_rates_dim_vol_surface`

**Estimated rows**: ~190

---

### `[rates].[fact_swaption_vol]` - Swaption Vol Observations

Daily swaption vol surface observations on the option_expiry x swap_tenor grid. ~38,000 rows/day (all 11 currencies).

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | `INT IDENTITY` | NO | Auto-increment primary key |
| `surface_id` | `INT` | NO | FK to `[rates].[dim_vol_surface](id)` |
| `obs_date` | `DATE` | NO | Observation date |
| `option_expiry` | `VARCHAR(4)` | NO | Option expiry tenor: `1M`, `3M`, ..., `30Y` |
| `swap_tenor` | `VARCHAR(4)` | NO | Underlying swap tenor: `3M`, `1Y`, ..., `30Y` |
| `value` | `FLOAT` | NO | Vol value (units depend on data_type/quote_type) |
| `created_at` | `DATETIMEOFFSET` | NO | Row insertion timestamp |
| `updated_at` | `DATETIMEOFFSET` | NO | Last update timestamp |

**Constraints:**
- `PK` on `id`
- `UNIQUE (surface_id, obs_date, option_expiry, swap_tenor)` as `uq_rates_fact_swaption_vol`
- `FK surface_id -> [rates].[dim_vol_surface](id)`

**Indexes:**
- `ix_rates_fact_swaption_vol_date` on `(obs_date)`
- `ix_rates_fact_swaption_vol_surface_date` on `(surface_id, obs_date)`

---

### `[rates].[dim_central_bank]` - Central Bank Dimension

Stores the central bank entries tracked by IMDR for policy rate ingestion. One row per central bank/rate series. Auto-seeded from `universe/rates.yml` (`bench_rates` section) by the pipeline on first run.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | `INT IDENTITY` | NO | Auto-increment primary key |
| `cb_code` | `VARCHAR(30)` | NO | Unique code, e.g. `ECB`, `FED_FUNDS`, `UK_BASE` |
| `display_name` | `VARCHAR(60)` | NO | Human-readable name, e.g. `ECB Deposit Facility` |
| `currency` | `VARCHAR(3)` | NO | ISO currency code, e.g. `EUR`, `USD`, `GBP` |
| `country_id` | `TINYINT` | NO | FK → `dbo.dim_country(id)` (migration 047, replaces legacy `market_code`) |
| `citi_tag` | `VARCHAR(60)` | NO | Citi Velocity tag, e.g. `RATES.BENCH_RATES.ECB` |
| `created_at` | `DATETIMEOFFSET` | NO | Row insertion timestamp |
| `updated_at` | `DATETIMEOFFSET` | NO | Last update timestamp |

**Constraints:**
- `PK` on `id`
- `UNIQUE (cb_code)` as `uq_rates_dim_central_bank`
- `FK country_id → [dbo].[dim_country](id)` as `fk_rates_dim_central_bank_country` (migration 047)

> Migration 047 (2026-05) removed legacy `market_code` + `market_id` columns and replaced with `country_id TINYINT FK → dbo.dim_country(id)`. See [country_anchor_design.md](../admin/calendar/country_anchor_design.md).

---

### `[rates].[fact_bench_rates]` - Central Bank Policy Rate Observations

Daily central bank policy rate observations from Citi Velocity `RATES.BENCH_RATES.*` tags. ~8 rows/day (10 tags configured, 2 JPY tags return no data).

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | `INT IDENTITY` | NO | Auto-increment primary key |
| `cb_id` | `INT` | NO | FK to `[rates].[dim_central_bank](id)` |
| `vendor_id` | `INT` | NO | FK to `[dbo].[dim_vendor](id)` |
| `obs_date` | `DATE` | NO | Observation date |
| `rate` | `FLOAT` | NO | Policy rate value (validated: finite, range [-2.0, 20.0]) |
| `created_at` | `DATETIMEOFFSET` | NO | Row insertion timestamp |
| `updated_at` | `DATETIMEOFFSET` | NO | Last update timestamp |

**Constraints:**
- `PK` on `id`
- `UNIQUE (cb_id, obs_date)` as `uq_rates_fact_bench_rates`
- `FK cb_id -> [rates].[dim_central_bank](id)`
- `FK vendor_id -> [dbo].[dim_vendor](id)`

**Indexes:**
- `ix_rates_fact_bench_rates_obs_date` on `(obs_date)`

**Migration:** `migrations/020_create_rates_bench_rates.sql`

---

## Cache Files

| File | Purpose |
|---|---|
| `data/cache/rates/empty_combos.json` | Tracks `(ccy, curve, quote)` combos known to return 0 rows from the API. Used to skip wasted API calls. Auto-retries after 30 days. |
| `data/cache/rates/rates_tags.json` | Tag discovery cache (Citi tag listing). Used by `RatesTagDiscovery`. |

---

## Audit

Pipeline runs are tracked in `[audit].[pipeline_runs]` with `pipeline_name = 'rates.historical'` and `domain = 'rates'`. See [`docs/admin/fx/fx_ohlc_schema.md`](../fx/fx_ohlc_schema.md) for the full audit table schema.
