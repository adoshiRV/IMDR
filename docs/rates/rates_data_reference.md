# Rates Data — Consumer Reference

Last updated: 2026-06-03

## What's in this domain

The rates domain holds four separate datasets. **Swap curves and spreads** (`rates.fact_observation`) cover 65 curves across 26+ currencies — OIS (RFR), IBOR/SWAP_LIBOR, Citi tenor basis (3s6s), and BBG cross-currency basis instruments — with par rates, forwards, spreads, butterflies, roll-carry, swap spreads, and basis spreads; sourced from Citi Velocity daily, with history from 2009-08-10 (~20M+ rows). **Swaption ATM vol surfaces** (`rates.fact_swaption_vol`) cover 11 currencies in a 17-expiry × 15-swap-tenor grid across multiple vol metrics (BLACK, NORMAL, FWDPREMIUM, realized, vol-ratio); sourced from Citi Velocity daily from 2005-01-03 (~6.7M rows). **Swaption skew** (`rates.fact_swaption_skew`) covers USD and JPY at 12 strike offsets from ATM for a 3M/6M/9M/1Y expiry × 1Y/2Y/5Y/10Y swap tenor grid; sourced from Barclays and updated by automated email-download; history from 2004-11-30 (~1.4M rows). **Central bank policy rates** (`rates.fact_bench_rates`) hold 8 CB rate series from Citi Velocity from 2000-01-03 (~52K rows).

All four datasets use daily granularity and obs_date-keyed schemas. Each has its own dimension table (dim_curve, dim_vol_surface, dim_skew_surface, dim_central_bank) that you must join to resolve human-readable labels — the fact tables carry integer FKs only. Swaption skew is Barclays-sourced and updates on a different schedule from the Citi feeds; it may lag by days if the email download fails.

## Coverage

### rates.fact_observation

Universe defined in [`src/imdr/universe/rates.yml`](../../src/imdr/universe/rates.yml).

**65 curves in dim_curve** (26 currencies), split by instrument type:

| curve_type | instrument | Example curves | Status |
|---|---|---|---|
| rfr | ois | SOFR, SONIA, EUROSTR, EONIA, TONAR, SARON, AONIA, NZIONA, CORRA, NOWA, STINA, SORA, THOR, MIBOR, SHIR, FEDFUND/FEDFUNDS | Active (EONIA ceased) |
| ibor | swap_libor | LIBOR, EURIBOR, GBP_LIBOR, JPY_LIBOR, CHF_LIBOR, BBSW, BKBM, CDOR, NIBOR, STIBOR, SOR, THBFIX, CNH_HIBOR, SHIBOR, NDIRS, HIBOR, JIBOR, MIFOR, CD, KLIBOR, PHIREF, TAIBOR, VND_REF | Mixed — some ceased |
| ccs | xccy_swap | CCS_VS_SOFR (CNH) | Active |
| basis | basis_swap | BASIS_SHIR_VS_SOFR (ILS), BASIS_SOR_VS_SOFR (SGD) | BBG cross-currency basis |
| basis | basis_swaps | EUR/AUD `3S6S_BASIS` (tenor basis); USD `SOFR_FEDFUND_BASIS`, EUR `EUROSTR_EURIBOR_BASIS`, AUD `3S_OIS_BASIS` (funding stress) | Citi BASIS_SWAPS family, 5 curves × 20-tenor standard grid. Historical USD/GBP `3S6S_BASIS` and the 2015–2025-02 series remain in `fact_observation` from the prior universe |

**Quote types:**

| DB code | Meaning | Tenor shape | Example |
|---|---|---|---|
| `par` | Par swap rate (%) | Single: `5Y` | 4.75 |
| `ssw` | Swap spread vs govies (bp) | Single: `5Y` | 32.0 |
| `rc` | Roll & carry (bp) | Single: `5Y` | 12.0 |
| `spread` | Curve spread (bp) | Two-leg: `2ys10ys` | -35.0 |
| `fwd` | Forward starting rate (%) | Two-leg: `5ys5ys` | 4.20 |
| `bfly` | Butterfly (bp) | Three-leg: `2ys5ys10ys` | -5.0 |
| `basis` | Cross-currency basis OR tenor basis (bp) | Single (`5Y`) or two-leg | -25.0 |

**Maturities:** OIS curves have up to 44 tenors (1D through 50Y); IBOR curves have up to 36 tenors (1W through 50Y); BASIS_SWAPS curves have 20 tenors (3M through 30Y; AUD missing 3M).

- Date range: 2009-08-10 to 2026-05-13
- Update cadence: DAILY (Citi EOD), HOURLY (a separate hourly runner samples ~16 curves during market hours)
- Vendor: Citi Velocity

### rates.fact_swaption_vol

243 surfaces in `dim_vol_surface` (11 currencies: AUD, CHF, DKK, EUR, GBP, JPY, KRW, NOK, NZD, SEK, USD).

**Data types per currency:**

| data_type | quote_type / vol_window | Description |
|---|---|---|
| ATM | BLACK, NORMAL, FWDPREMIUM, PREMIUM | ATM swaption vol in various quoting conventions |
| ATM_RFR | same | ATM vol vs RFR-based swap |
| REALIZED | vol_window: 1M, 3M, 6M, 1Y; freq: ANNUAL, DAILY | Realized vol |
| REALIZED_RFR | same | Realized vol vs RFR |
| VOL_RATIO | same windows | Implied/realized ratio |
| VOL_RATIO_RFR | same | Ratio vs RFR |

**Grid:** 17 option expiries (1M, 2M, 3M, 6M, 9M, 1Y, 18M, 2Y, 3Y, 4Y, 5Y, 7Y, 10Y, 12Y, 15Y, 20Y, 30Y) × 15 swap tenors (1M, 3M, 6M, 9M, 1Y, 2Y, 3Y, 4Y, 5Y, 7Y, 10Y, 12Y, 15Y, 20Y, 30Y)

- Date range: 2005-01-03 to 2026-05-12
- Update cadence: DAILY
- Vendor: Citi Velocity

### rates.fact_swaption_skew

12 surfaces in `dim_skew_surface` (2 currencies: USD and JPY).

**USD skew grid:** option_expiry ∈ {3M, 6M, 9M, 1Y, 2Y, 5Y, 10Y} × swap_tenor ∈ {1Y, 2Y, 5Y, 10Y} × strike_offset ∈ {-200, -150, -100, -75, -50, -25, +25, +50, +75, +100, +150, +200} bp

**JPY skew grid:** option_expiry ∈ {3M, 6M, 9M, 1Y, 2Y} × swap_tenor ∈ {1Y, 2Y, 5Y, 10Y} × same strikes

- Date range: 2004-11-30 to 2026-05-06
- Update cadence: updated when Barclays sends the weekly email (~daily on trading days, may lag)
- Vendor: Barclays (via automated email-linked download)

### rates.fact_bench_rates

8 CB series in `dim_central_bank`:

| cb_code | display_name | currency |
|---|---|---|
| ECB | ECB Deposit Facility | EUR |
| FED_FUNDS | Fed Effective Rate | USD |
| UK_BASE | BoE Bank Rate | GBP |
| US_FED_CP_1M | Fed Commercial Paper 1M | USD |
| US_FED_CP_2M | Fed Commercial Paper 2M | USD |
| US_FED_CP_3M | Fed Commercial Paper 3M | USD |
| US_FED_FUNDS_TARGET | Fed Target Rate | USD |
| US_FED_PRIME | US Prime Rate | USD |

- Date range: 2000-01-03 to 2026-05-12
- Update cadence: DAILY
- Vendor: Citi Velocity

---

## Schema — full dump

### `rates.dim_curve`

One row per (ccy, curve) combination — the primary dimension for `fact_observation`.

| Column | Type | Nullable | FK | Description |
|---|---|---|---|---|
| `id` | INT IDENTITY | NO | — | Surrogate PK |
| `ccy` | VARCHAR(10) | NO | — | ISO currency code (e.g. USD, EUR) |
| `curve` | VARCHAR(30) | NO | — | Curve name (e.g. SOFR, EURIBOR) |
| `curve_type` | VARCHAR(10) | NO | — | `rfr`, `ibor`, `ccs`, or `basis` |
| `curve_status` | VARCHAR(10) | NO | — | `active`, `ceased`, or `reformed` |
| `instrument` | VARCHAR(20) | NO | — | `ois`, `swap_libor`, `xccy_swap`, or `basis_swap` |
| `citi_prefix` | VARCHAR(60) | NO | — | Citi Velocity tag prefix, e.g. `RATES.OIS.USD_SOFR` |
| `country_id` | TINYINT | NO | `dbo.dim_country(id)` | Country anchor (replaces legacy market_code) |
| `cessation_date` | DATE | YES | — | Date ceased publication; NULL if active |
| `primary_from` | DATE | YES | — | When this became primary benchmark |
| `supersedes` | VARCHAR(30) | YES | — | Which curve this replaced |
| `superseded_by` | VARCHAR(30) | YES | — | Which curve replaced this |
| `notes` | VARCHAR(500) | YES | — | Free text context |
| `created_at` | DATETIMEOFFSET | NO | — | Row insertion time |
| `updated_at` | DATETIMEOFFSET | NO | — | Last update time |

**Unique constraint:** `uq_rates_dim_curve` on `(ccy, curve)`

---

### `rates.fact_observation`

One row per (curve, timestamp, quote, tenor). Primary rates fact table.

| Column | Type | Nullable | FK | Description |
|---|---|---|---|---|
| `id` | INT IDENTITY | NO | — | Surrogate PK |
| `curve_id` | INT | NO | `rates.dim_curve(id)` | Which curve |
| `ts` | DATETIMEOFFSET | NO | — | UTC observation timestamp |
| `quote` | VARCHAR(10) | NO | — | `par`, `spread`, `fwd`, `bfly`, `ssw`, `rc`, `basis` |
| `tenor` | VARCHAR(30) | NO | — | Tenor string — see encoding note below |
| `value` | FLOAT | NO | — | Rate value in percentage points (par, fwd) or basis points (spread, bfly, ssw, rc, basis) |
| `created_at` | DATETIMEOFFSET | NO | — | Row insertion time |
| `updated_at` | DATETIMEOFFSET | NO | — | Last update time |

**Unique constraint:** `uq_rates_fact_obs` on `(curve_id, ts, quote, tenor)`

**Check constraint:** `ck_rates_quote`: `quote IN ('par','spread','fwd','bfly','ssw','rc','basis')`

**Indexes:** `ix_rates_obs_ts` on `(ts DESC)`, `ix_rates_obs_quote_tenor` on `(quote, tenor, ts) INCLUDE (curve_id, value)`

**Tenor encoding:** Multi-leg quotes use a lowercase-with-`s` format: spread `2ys10ys` = 2s10s, forward `5ys5ys` = 5y5y, butterfly `2ys5ys10ys`. Single-leg quotes (`par`, `ssw`, `rc`) use uppercase passthrough: `5Y`, `10Y`, `18M`.

**Value units:** `par` and `fwd` values are percentage points (4.75 = 4.75%). `spread`, `bfly`, `ssw`, `rc`, `basis` are basis points (32.0 = 32 bp).

---

### `rates.dim_vol_surface`

One row per unique swaption vol surface. Auto-seeded by pipeline.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | INT IDENTITY | NO | Surrogate PK |
| `ccy` | VARCHAR(3) | NO | ISO currency code |
| `data_type` | VARCHAR(15) | NO | `ATM`, `ATM_RFR`, `REALIZED`, `REALIZED_RFR`, `VOL_RATIO`, `VOL_RATIO_RFR` |
| `quote_type` | VARCHAR(12) | NO | `BLACK`, `NORMAL`, `FWDPREMIUM`, `PREMIUM` for ATM types; `''` otherwise |
| `vol_window` | VARCHAR(3) | NO | `1M`, `3M`, `6M`, `1Y` for REALIZED/VOL_RATIO; `''` otherwise |
| `freq` | VARCHAR(6) | NO | `ANNUAL`, `DAILY` for REALIZED; `''` otherwise |
| `is_rfr` | BIT | NO | 1 for RFR variants |
| `created_at` | DATETIMEOFFSET | NO | Row insertion time |
| `updated_at` | DATETIMEOFFSET | NO | Last update time |

**Unique constraint:** `uq_rates_dim_vol_surface` on `(ccy, data_type, quote_type, vol_window, freq)`

243 rows across 11 currencies.

---

### `rates.fact_swaption_vol`

One row per (surface, obs_date, option_expiry, swap_tenor). Daily swaption vol observations.

| Column | Type | Nullable | FK | Description |
|---|---|---|---|---|
| `id` | INT IDENTITY | NO | — | Surrogate PK |
| `surface_id` | INT | NO | `rates.dim_vol_surface(id)` | Which surface |
| `obs_date` | DATE | NO | — | Observation date |
| `option_expiry` | VARCHAR(4) | NO | — | Option expiry tenor (e.g. 1M, 6M, 1Y, 10Y) |
| `swap_tenor` | VARCHAR(4) | NO | — | Underlying swap tenor (e.g. 1Y, 5Y, 10Y) |
| `value` | FLOAT | NO | — | Vol value — units depend on data_type/quote_type |
| `created_at` | DATETIMEOFFSET | NO | — | Row insertion time |
| `updated_at` | DATETIMEOFFSET | NO | — | Last update time |

**Unique constraint:** `uq_rates_fact_swaption_vol` on `(surface_id, obs_date, option_expiry, swap_tenor)`

**Indexes:** `ix_rates_fact_swaption_vol_date` on `(obs_date)`, `ix_rates_fact_swaption_vol_surface_date` on `(surface_id, obs_date)`

---

### `rates.dim_skew_surface`

One row per (ccy, option_expiry) for the Barclays skew universe.

| Column | Type | Nullable | FK | Description |
|---|---|---|---|---|
| `id` | INT IDENTITY | NO | — | Surrogate PK |
| `ccy` | VARCHAR(3) | NO | — | Currency code (USD or JPY) |
| `currency_id` | TINYINT | YES | `dbo.dim_currency(id)` | FK to currency dim |
| `option_expiry` | VARCHAR(4) | NO | — | Option expiry tenor |
| `country_id` | TINYINT | NO | `dbo.dim_country(id)` | Country anchor |

**Unique constraint:** `(ccy, option_expiry)` — 12 rows (USD: 7 expiries, JPY: 5 expiries)

---

### `rates.fact_swaption_skew`

One row per (surface, vendor, obs_date, swap_tenor, strike_offset). Absolute normalised bp vol at each strike.

| Column | Type | Nullable | FK | Description |
|---|---|---|---|---|
| `id` | INT IDENTITY | NO | — | Surrogate PK |
| `surface_id` | INT | NO | `rates.dim_skew_surface(id)` | Which surface |
| `vendor_id` | INT | NO | `dbo.dim_vendor(id)` | barclays (id=2) |
| `obs_date` | DATE | NO | — | Observation date |
| `swap_tenor` | VARCHAR(4) | NO | — | Swap tenor: 1Y, 2Y, 5Y, 10Y |
| `strike_offset` | INT | NO | — | Basis points from ATM: -200, -150, -100, -75, -50, -25, +25, +50, +75, +100, +150, +200 |
| `vol` | FLOAT | NO | — | Absolute normalised bp vol (not a spread from ATM) |

**Unique constraint:** `(surface_id, obs_date, swap_tenor, strike_offset)`

Note: the column is `vol`, not `value` — different from `fact_swaption_vol` which uses `value`.

---

### `rates.dim_central_bank`

One row per CB rate series.

| Column | Type | Nullable | FK | Description |
|---|---|---|---|---|
| `id` | INT IDENTITY | NO | — | Surrogate PK |
| `cb_code` | VARCHAR(30) | NO | — | Unique code (e.g. ECB, FED_FUNDS) |
| `display_name` | VARCHAR(60) | NO | — | Human-readable name |
| `currency` | VARCHAR(3) | NO | — | ISO currency |
| `country_id` | TINYINT | NO | `dbo.dim_country(id)` | Country anchor |
| `citi_tag` | VARCHAR(60) | NO | — | Citi Velocity tag |
| `created_at` | DATETIMEOFFSET | NO | — | Row insertion time |
| `updated_at` | DATETIMEOFFSET | NO | — | Last update time |

**Unique constraint:** `uq_rates_dim_central_bank` on `(cb_code)`

---

### `rates.fact_bench_rates`

One row per (cb, vendor, obs_date). Daily CB policy rate observations.

| Column | Type | Nullable | FK | Description |
|---|---|---|---|---|
| `id` | INT IDENTITY | NO | — | Surrogate PK |
| `cb_id` | INT | NO | `rates.dim_central_bank(id)` | Which CB series |
| `vendor_id` | INT | NO | `dbo.dim_vendor(id)` | citi_velocity (id=1) |
| `obs_date` | DATE | NO | — | Observation date |
| `rate` | FLOAT | NO | — | Policy rate value (validated range: -2.0 to 20.0 %) |
| `created_at` | DATETIMEOFFSET | NO | — | Row insertion time |
| `updated_at` | DATETIMEOFFSET | NO | — | Last update time |

**Unique constraint:** `uq_rates_fact_bench_rates` on `(cb_id, obs_date)`

**Index:** `ix_rates_fact_bench_rates_obs_date` on `(obs_date)`

---

## How to query — examples

**1. USD SOFR par curve as of today**

```sql
SELECT
    o.tenor,
    o.value  AS par_rate_pct,
    CAST(o.ts AS date) AS obs_date
FROM [rates].[fact_observation] o
JOIN [rates].[dim_curve] c ON c.id = o.curve_id
WHERE c.ccy   = 'USD'
  AND c.curve = 'SOFR'
  AND o.quote = 'par'
  AND CAST(o.ts AS date) = (
      SELECT MAX(CAST(ts AS date))
      FROM [rates].[fact_observation] o2
      JOIN [rates].[dim_curve] c2 ON c2.id = o2.curve_id
      WHERE c2.ccy='USD' AND c2.curve='SOFR' AND o2.quote='par'
  )
ORDER BY LEN(o.tenor), o.tenor;
```

Note: `value` is in percentage points for `par` (e.g. 4.75 = 4.75%).

---

**2. EUR 5Y5Y forward rate — last 12 months**

```sql
SELECT
    CAST(o.ts AS date) AS obs_date,
    o.value            AS fwd_rate_pct
FROM [rates].[fact_observation] o
JOIN [rates].[dim_curve] c ON c.id = o.curve_id
WHERE c.ccy   = 'EUR'
  AND c.curve = 'EUROSTR'
  AND o.quote = 'fwd'
  AND o.tenor = '5ys5ys'
  AND o.ts >= DATEADD(year, -1, GETDATE())
ORDER BY o.ts;
```

Tenor encoding for forwards: `5ys5ys` = 5Y into 5Y, `1ys9ys` = 1Y into 9Y. Check `dim_curve.citi_prefix` to confirm the exact curve driving EUR fwds.

---

**3. G10 2s10s spread today — all active OIS curves**

```sql
SELECT
    c.ccy,
    c.curve,
    o.value AS spread_bp
FROM [rates].[fact_observation] o
JOIN [rates].[dim_curve] c ON c.id = o.curve_id
WHERE c.curve_type   = 'rfr'
  AND c.curve_status = 'active'
  AND o.quote = 'spread'
  AND o.tenor = '2ys10ys'
  AND CAST(o.ts AS date) = (
      SELECT MAX(CAST(ts AS date)) FROM [rates].[fact_observation]
      WHERE quote='spread' AND tenor='2ys10ys'
  )
ORDER BY c.ccy;
```

---

**4. USD ATM NORMAL swaption vol — 5Y expiry, all swap tenors, latest date**

```sql
SELECT
    sv.option_expiry,
    sv.swap_tenor,
    sv.value  AS vol_bpvol
FROM [rates].[fact_swaption_vol] sv
JOIN [rates].[dim_vol_surface]  ds ON ds.id = sv.surface_id
WHERE ds.ccy        = 'USD'
  AND ds.data_type  = 'ATM'
  AND ds.quote_type = 'NORMAL'
  AND sv.option_expiry = '5Y'
  AND sv.obs_date = (
      SELECT MAX(obs_date) FROM [rates].[fact_swaption_vol] sv2
      JOIN [rates].[dim_vol_surface] ds2 ON ds2.id=sv2.surface_id
      WHERE ds2.ccy='USD' AND ds2.data_type='ATM'
  )
ORDER BY sv.swap_tenor;
```

Units for NORMAL vol: basis points per annum (bp vol). BLACK vol: dimensionless (percentage). Check `data_type` + `quote_type` on `dim_vol_surface` before interpreting values.

---

**5. USD swaption skew — 5Y expiry, 10Y swap tenor, time series at -100bp strike**

```sql
SELECT
    sk.obs_date,
    sk.vol  AS normalised_bpvol
FROM [rates].[fact_swaption_skew] sk
JOIN [rates].[dim_skew_surface]   ss ON ss.id = sk.surface_id
WHERE ss.ccy           = 'USD'
  AND ss.option_expiry = '5Y'
  AND sk.swap_tenor    = '10Y'
  AND sk.strike_offset = -100
  AND sk.obs_date >= '2025-01-01'
ORDER BY sk.obs_date;
```

Note: the `vol` column here contains absolute normalised bp vol, not a spread from ATM. Compute the skew spread at query time: `skew_spread = vol - atm_vol` by joining back to `fact_swaption_vol`.

---

**6. Central bank policy rates — Fed Funds, ECB, BoE — last 6 months**

```sql
SELECT
    cb.display_name,
    br.obs_date,
    br.rate
FROM [rates].[fact_bench_rates] br
JOIN [rates].[dim_central_bank] cb ON cb.id = br.cb_id
WHERE cb.cb_code IN ('FED_FUNDS', 'ECB', 'UK_BASE')
  AND br.obs_date >= DATEADD(month, -6, CAST(GETDATE() AS date))
ORDER BY br.obs_date, cb.cb_code;
```

---

## Connection details

- **Server:** read from `IMDR_MSSQL_SERVER` environment variable
- **Database:** `IMDR` (never connect to any other database)
- **Auth:** Windows Authentication (`Trusted_Connection=yes`)
- **Driver:** `SQL Server` (legacy ODBC driver; set via `IMDR_MSSQL_DRIVER=SQL+Server`)
- **Access level:** analysts have read-only SELECT on `rates`, `dbo`, `audit` schemas

---

## Vendor notes

**Citi Velocity** sources `fact_observation`, `fact_swaption_vol`, and `fact_bench_rates`. Tags follow the `RATES.OIS.{CCY}_{CURVE}.{QUOTE_TYPE}.{TENORS}` format for OIS, and `RATES.SWAP_LIBOR.{CCY}_{CURVE}.*` for IBOR. The Citi API uses a "empty combo" cache to skip known-zero combos (stored in `rates.cache_empty_combo`); this cache retries after 30 days, so a curve that returns no data today may start returning data in a future run. Full tag catalog is at [`docs/admin/vendors/citi/tag_catalog.md`](../admin/vendors/citi/tag_catalog.md).

**Barclays** sources `fact_swaption_skew` via an automated email download that triggers when Barclays sends a new Excel file. The pipeline is registered as the `barclays_skew` vendor feed in `imdr_daily.py`. On failure the staleness monitor flags the table; the most recent data may be several days old if the email flow breaks. Column header format in the Excel source: `USDSW{EXPIRY}{TENOR}F Normalised vol ATM {STRIKE} bp` — see [swaption_skew_schema.md](../admin/rates/swaption_skew_schema.md) for the full parser spec.

---

## Where ops detail lives

- Curve pipeline runbook: [rates_operations.md](../admin/rates/rates_operations.md)
- Rates schema reference (maintainer-level): [rates_schema.md](../admin/rates/rates_schema.md)
- Swaption vol runbook: [swaption_vol_operations.md](../admin/rates/swaption_vol_operations.md)
- Swaption skew schema + ops: [swaption_skew_schema.md](../admin/rates/swaption_skew_schema.md)
- Hourly pipeline design: [rates_hourly_pipeline.md](../admin/rates/rates_hourly_pipeline.md)
- Calendar integration (holiday skip logic): [calendar_integration.md](../admin/rates/calendar_integration.md)
- Full curve catalog: [curve_catalog.md](../admin/rates/curve_catalog.md)

---

## Last verified

2026-05-14. Row counts, date ranges, curve list, and column lists confirmed against live IMDR DB.
