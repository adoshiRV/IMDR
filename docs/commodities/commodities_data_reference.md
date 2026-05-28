# Commodities Data — Consumer Reference

Last updated: 2026-05-14

## What's in this domain

The commodities domain holds three datasets. **Spot prices** (`commodities.fact_spot`) cover Gold (XAU), Silver (XAG), and WTI Crude (CR_NYM_CL) in daily close prices from Citi Velocity; data begins 2026-01-01 (283 rows — live feed, no multi-year backfill). **Implied volatility surfaces** (`commodities.fact_implied_vol`) cover Gold, Silver, Platinum, WTI, and Brent across strikes and tenors, sourced from Citi Velocity daily; history begins 2026-01-02 (~68K rows). **EIA weekly petroleum statistics** (`commodities.fact_eia`) cover 16 series × PADD regions from Citi Velocity's EIA feed; history begins 2026-01-02 (~1.2K rows, weekly cadence).

All three tables use a dimension table (`dim_commodity` or `dim_eia_series`) as the primary join key. The commodities domain is live but has a shallow history — data loads started in January 2026 and no historical backfill has been run. The precious metals vol surface (Gold, Silver, Platinum) and crude oil NEARBY contract vol are modelled differently: precious metals have a full strike grid (ATM + risk reversals + strangles + exotic strikes) with fixed tenors, while crude oil uses rolling nearby-month contract notation (NEARBY01_M through NEARBY12_M) with ATM vol only.

## Coverage

Universe defined in [`src/imdr/universe/commodities.yml`](../../src/imdr/universe/commodities.yml).

### commodities.fact_spot

| Symbol | Display name | Class | Citi tag |
|---|---|---|---|
| XAU | Gold | precious_metal | COMMODITIES.SPOT.SPOT_GOLD |
| XAG | Silver | precious_metal | COMMODITIES.SPOT.SPOT_SILVER |
| CR_NYM_CL | WTI Crude | energy | COMMODITIES.SPOT.OIL_PRICE_NYMEX |

Note: Platinum (XPT) and ICE Brent (CR_IPE_BRENT) are in dim_commodity but have no Citi SPOT tag and therefore have no rows in fact_spot.

- Date range: 2026-01-01 to 2026-05-12
- Update cadence: DAILY
- Vendor: Citi Velocity

### commodities.fact_implied_vol

**5 commodities in dim_commodity** (3 precious metals + 2 energy):

| Symbol | Display name | Vol model |
|---|---|---|
| XAU | Gold | Full strike grid + 14 fixed tenors |
| XAG | Silver | Full strike grid + 14 fixed tenors |
| XPT | Platinum | Full strike grid + extended tenors (including exotic) |
| CR_NYM_CL | WTI Crude | ATM only, 12 nearby-month contracts |
| CR_IPE_BRENT | ICE Brent | ATM only, 12 nearby-month contracts |

**Strikes in DB (19):** ATM, ATMF, 10RR, 25RR, 35RR, 10STR, 25STR, 35STR, C10, C25, C35, P10, P25, P35, BID, ASK, SVVSTAR, SVXI, XI

- ATM, RR, STR, and delta strikes apply to XAU, XAG, XPT
- BID/ASK and ATMF apply to XPT only
- SVVSTAR, SVXI, XI are exotic vol metrics for precious metals
- Oil (CR_NYM_CL, CR_IPE_BRENT) has only ATM with NEARBY01_M through NEARBY12_M tenors

**Tenors in DB (27 distinct values):** Fixed tenors (ON, 1W, 2W, 1M, 2M, 3M, 6M, 9M, 18M, 1Y, 2Y, 3Y, 4Y, 5Y, 6Y, 7Y, 8Y, 9Y, 10Y, 15Y) for precious metals; nearby-month notation (NEARBY01_M, NEARBY02_M, ..., NEARBY06_M) for crude oil

- Date range: 2026-01-02 to 2026-05-12
- Update cadence: DAILY
- Vendor: Citi Velocity

### commodities.fact_eia

**16 EIA petroleum series** × PADD regions (67 series-region combinations in dim_eia_series):

| Series name | Regions | Units |
|---|---|---|
| CRUDE_STOCKS | TOTAL_US, PADD_I–V, CUSHING_OK | thousands_barrels |
| CRUDE_IMPORTS | TOTAL_US, PADD_I, PADD_III, PADD_V | thousands_barrels_day |
| CRUDE_EXPORTS | TOTAL_US | thousands_barrels_day |
| CRUDE_RUNS | TOTAL_US, PADD_I–V | thousands_barrels_day |
| DISTILLATE_STOCKS | TOTAL_US, PADD_I–V | thousands_barrels |
| DISTILLATE_IMPORTS | TOTAL_US, PADD_I, PADD_III | thousands_barrels_day |
| DISTILLATE_PRODUCTION | TOTAL_US, PADD_I–V | thousands_barrels_day |
| DISTILLATES_EXPORT | TOTAL_US | thousands_barrels_day |
| GASOLINE_STOCKS | TOTAL_US, PADD_I–V | thousands_barrels |
| GASOLINE_IMPORTS | TOTAL_US, PADD_I, PADD_III | thousands_barrels_day |
| GASOLINE_PRODUCTION | TOTAL_US, PADD_I–V | thousands_barrels_day |
| GASOLINE_EXPORT | TOTAL_US | thousands_barrels_day |
| JET_STOCKS | TOTAL_US, PADD_I–V | thousands_barrels |
| JET_PRODUCTION | TOTAL_US, PADD_I–V | thousands_barrels_day |
| HEATING_OIL_STOCKS | TOTAL_US, PADD_I | thousands_barrels |
| ULSD_STOCKS | TOTAL_US, PADD_I, PADD_II | thousands_barrels |

PADD regions: PADD_I = East Coast, PADD_II = Midwest, PADD_III = Gulf Coast, PADD_IV = Rocky Mountain, PADD_V = West Coast. Cushing (CUSHING_OK) is the WTI delivery point, tracked separately for CRUDE_STOCKS.

- Date range: 2026-01-02 to 2026-05-01 (weekly — typically released Wednesdays, lags actual EIA publication by ~1 day)
- Update cadence: WEEKLY (Citi re-publishes EIA data daily but values only change on release days)
- Vendor: Citi Velocity (which re-distributes EIA data)

---

## Schema — full dump

### `commodities.dim_commodity`

One row per tracked commodity. Shared dimension for `fact_spot` and `fact_implied_vol`.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | INT IDENTITY | NO | Surrogate PK |
| `symbol` | VARCHAR(20) | NO | Commodity symbol (e.g. XAU, CR_NYM_CL) |
| `display_name` | VARCHAR(100) | NO | Human-readable name |
| `commodity_class` | VARCHAR(30) | NO | `precious_metal` or `energy` |
| `spot_tag` | VARCHAR(100) | YES | Citi Velocity spot tag (NULL if no spot data) |
| `created_at` | DATETIMEOFFSET | NO | Row insertion time |
| `updated_at` | DATETIMEOFFSET | NO | Last update time |

5 rows. XPT and CR_IPE_BRENT have `spot_tag = NULL`.

---

### `commodities.fact_spot`

One row per (commodity, date). Daily spot price.

| Column | Type | Nullable | FK | Description |
|---|---|---|---|---|
| `id` | INT IDENTITY | NO | — | Surrogate PK |
| `commodity_id` | INT | NO | `commodities.dim_commodity(id)` | Which commodity |
| `obs_date` | DATE | NO | — | Observation date |
| `price` | FLOAT | NO | — | Spot price in USD (XAU: USD/troy oz, XAG: USD/troy oz, WTI: USD/barrel) |
| `created_at` | DATETIMEOFFSET | NO | — | Row insertion time |
| `updated_at` | DATETIMEOFFSET | NO | — | Last update time |

**Unique constraint:** implied by `(commodity_id, obs_date)` — pipeline performs MERGE on this key.

---

### `commodities.fact_implied_vol`

One row per (commodity, obs_date, strike, tenor). Daily implied vol observation.

| Column | Type | Nullable | FK | Description |
|---|---|---|---|---|
| `id` | INT IDENTITY | NO | — | Surrogate PK |
| `commodity_id` | INT | NO | `commodities.dim_commodity(id)` | Which commodity |
| `obs_date` | DATE | NO | — | Observation date |
| `strike` | VARCHAR(10) | NO | — | Strike type — see coverage section for valid values per commodity |
| `tenor` | VARCHAR(15) | NO | — | Tenor string — fixed (1M, 3M…) for precious metals; NEARBY01_M–NEARBY12_M for crude |
| `vol` | FLOAT | NO | — | Implied vol value (% annualized for standard strikes; varies for exotic strikes) |
| `created_at` | DATETIMEOFFSET | NO | — | Row insertion time |
| `updated_at` | DATETIMEOFFSET | NO | — | Last update time |

**Unique constraint:** implied by `(commodity_id, obs_date, strike, tenor)`.

Note: the column is `vol`, not `value`.

---

### `commodities.dim_eia_series`

One row per tracked EIA series + region combination.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | INT IDENTITY | NO | Surrogate PK |
| `series_name` | VARCHAR(50) | NO | Series identifier (e.g. CRUDE_STOCKS, GASOLINE_PRODUCTION) |
| `region` | VARCHAR(20) | NO | Region identifier (e.g. TOTAL_US, PADD_I, CUSHING_OK) |
| `series_units` | VARCHAR(30) | NO | Units string: `thousands_barrels` or `thousands_barrels_day` |
| `created_at` | DATETIMEOFFSET | NO | Row insertion time |
| `updated_at` | DATETIMEOFFSET | NO | Last update time |

67 rows. No separate PK/UK constraint documented — pipeline uses `(series_name, region)` as the natural key.

---

### `commodities.fact_eia`

One row per (eia_series, date). Weekly EIA petroleum statistic.

| Column | Type | Nullable | FK | Description |
|---|---|---|---|---|
| `id` | INT IDENTITY | NO | — | Surrogate PK |
| `eia_series_id` | INT | NO | `commodities.dim_eia_series(id)` | Which series + region |
| `obs_date` | DATE | NO | — | Observation date (weekly, typically Friday) |
| `stat_value` | FLOAT | NO | — | Value in the series_units of the referenced dim row |
| `created_at` | DATETIMEOFFSET | NO | — | Row insertion time |
| `updated_at` | DATETIMEOFFSET | NO | — | Last update time |

**Unique constraint:** implied by `(eia_series_id, obs_date)`.

---

## How to query — examples

**1. Gold spot price — last 30 days**

```sql
SELECT
    fs.obs_date,
    fs.price  AS xau_usd_per_oz
FROM [commodities].[fact_spot] fs
JOIN [commodities].[dim_commodity] dc ON dc.id = fs.commodity_id
WHERE dc.symbol  = 'XAU'
  AND fs.obs_date >= DATEADD(day, -30, CAST(GETDATE() AS date))
ORDER BY fs.obs_date;
```

---

**2. Gold ATM implied vol — 1Y tenor — time series**

```sql
SELECT
    fv.obs_date,
    fv.vol  AS atm_implied_vol_pct
FROM [commodities].[fact_implied_vol] fv
JOIN [commodities].[dim_commodity]   dc ON dc.id = fv.commodity_id
WHERE dc.symbol  = 'XAU'
  AND fv.strike  = 'ATM'
  AND fv.tenor   = '1Y'
ORDER BY fv.obs_date;
```

---

**3. Gold vol smile — latest date, 3M tenor (all strikes)**

```sql
SELECT
    fv.strike,
    fv.vol
FROM [commodities].[fact_implied_vol] fv
JOIN [commodities].[dim_commodity]   dc ON dc.id = fv.commodity_id
WHERE dc.symbol  = 'XAU'
  AND fv.tenor   = '3M'
  AND fv.obs_date = (
      SELECT MAX(obs_date) FROM [commodities].[fact_implied_vol] fv2
      JOIN [commodities].[dim_commodity] dc2 ON dc2.id=fv2.commodity_id
      WHERE dc2.symbol='XAU'
  )
ORDER BY fv.strike;
```

---

**4. Brent implied vol — nearby-month term structure (ATM) — latest date**

```sql
SELECT
    fv.tenor,
    fv.vol  AS atm_vol_pct
FROM [commodities].[fact_implied_vol] fv
JOIN [commodities].[dim_commodity]   dc ON dc.id = fv.commodity_id
WHERE dc.symbol  = 'CR_IPE_BRENT'
  AND fv.strike  = 'ATM'
  AND fv.obs_date = (
      SELECT MAX(obs_date) FROM [commodities].[fact_implied_vol] fv2
      JOIN [commodities].[dim_commodity] dc2 ON dc2.id=fv2.commodity_id
      WHERE dc2.symbol='CR_IPE_BRENT'
  )
ORDER BY fv.tenor;
-- Tenors are NEARBY01_M (front month) through NEARBY12_M (12th contract)
```

---

**5. EIA US crude inventory — last 12 weekly observations**

```sql
SELECT
    fe.obs_date,
    fe.stat_value  AS thousands_barrels
FROM [commodities].[fact_eia] fe
JOIN [commodities].[dim_eia_series] des ON des.id = fe.eia_series_id
WHERE des.series_name = 'CRUDE_STOCKS'
  AND des.region      = 'TOTAL_US'
ORDER BY fe.obs_date DESC
OFFSET 0 ROWS FETCH NEXT 12 ROWS ONLY;
```

---

**6. All EIA series for a specific reference date**

```sql
SELECT
    des.series_name,
    des.region,
    des.series_units,
    fe.stat_value,
    fe.obs_date
FROM [commodities].[fact_eia] fe
JOIN [commodities].[dim_eia_series] des ON des.id = fe.eia_series_id
WHERE fe.obs_date = (SELECT MAX(obs_date) FROM [commodities].[fact_eia])
ORDER BY des.series_name, des.region;
```

---

## Connection details

- **Server:** read from `IMDR_MSSQL_SERVER` environment variable
- **Database:** `IMDR` (never connect to any other database)
- **Auth:** Windows Authentication (`Trusted_Connection=yes`)
- **Driver:** `SQL Server` (legacy ODBC driver; set via `IMDR_MSSQL_DRIVER=SQL+Server`)
- **Access level:** analysts have read-only SELECT on `commodities`, `dbo`, `audit` schemas

---

## Vendor notes

**Citi Velocity** is the sole source for all three commodities tables. Spot tag format: `COMMODITIES.SPOT.{TAG_NAME}` (e.g. `COMMODITIES.SPOT.SPOT_GOLD`). Precious-metals vol tag format: `COMMODITIES.IMPLIED_VOL.{PRODUCT}.USD.{STRIKE}.{TENOR}` (e.g. `COMMODITIES.IMPLIED_VOL.XAU.USD.ATM.1Y`). Crude oil vol format uses nearby-month notation: `COMMODITIES.IMPLIED_VOL.{PRODUCT}.ATM.NEARBY{NN}_M` where NN is zero-padded 01–12. EIA format: `COMMODITIES.EIA.EIA_{SERIES}.EIA_{REGION}`. The Citi API initially returned 0 rows for commodities due to a dict-vs-list parsing difference; this was fixed and confirmed working — all four data categories return data.

Note on units: precious metals `vol` values are annualized implied volatility in percent (e.g. 15.0 = 15% vol). Crude oil NEARBY values are also in percent. Exotic strikes (SVVSTAR, SVXI, XI) have different semantics — see the quality ranges in `commodities.yml` for expected bounds.

---

## Where ops detail lives

- Citi commodities catalog exploration: [`docs/admin/vendors/citi/exploration/commodities.md`](../admin/vendors/citi/exploration/commodities.md)
- Universe YAML: [`src/imdr/universe/commodities.yml`](../../src/imdr/universe/commodities.yml)

---

## Last verified

2026-05-14. Row counts, date ranges, and column lists confirmed against live IMDR DB. History limited to 2026-01 onward — no historical backfill loaded.
