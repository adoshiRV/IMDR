# FX Data — Consumer Reference

Last updated: 2026-05-14

## What's in this domain

The FX domain holds three distinct datasets. **Spot and forward rates** (`fx.fact_fx_rate`) cover 19–26 currency pairs across up to 22 tenors from SPOT through 10Y, sourced from Citi Velocity's Historical API and updated daily (EOD) plus hourly intraday. Historical depth reaches back to 2007-01-01 for the core pairs. **Implied and realized vol surfaces** (`fx.fact_vol`) cover 18 pairs with 11 strikes (ATM plus risk reversals, strangles, and delta calls/puts) across 14 tenors from ON through 10Y, sourced from Citi Velocity daily; history begins 2016-01-04. **Intraday OHLC bars** (`fx.fact_ohlc`) hold hourly bars from BidFX — spot mid + bid/ask OHLC, 17 pairs, built from tick data; available from 2021-01-03 to 2026-04-28 (BidFX feed retired in favour of Citi for new data).

A key structural point: FX rates and FX vol live in separate fact tables with different natural keys. The rate table (`fact_fx_rate`) is keyed on `(pair_id, frequency_id, obs_ts, tenor)`; the vol table (`fact_vol`) is keyed on `(pair_id, obs_date, strike, tenor, vol_type)`. An LLM or analyst must join to `fx.dim_currency_pair` in both cases but the filtering columns differ. OHLC lives entirely in `fx.fact_ohlc` and uses a string `symbol` column rather than a foreign key — it predates the dimension tables.

## Coverage

### fx.fact_fx_rate

Universe defined in [`src/imdr/universe/fx.yml`](../../src/imdr/universe/fx.yml) under `fx_rate.pairs`.

**Active Phase 1 pairs (19 — the core daily ingestion set):**

| Class | Pairs |
|---|---|
| G10 | EUR/USD, GBP/USD, AUD/USD, NZD/USD, USD/JPY, USD/CHF, USD/CAD, USD/NOK, USD/SEK, USD/CNH |
| EM deliverable | USD/HKD, USD/SGD |
| EM NDF | USD/KRW, USD/TWD, USD/THB, USD/IDR, USD/PHP, USD/INR, USD/MYR |

Additional pairs present in `dim_currency_pair` (26 rows total) include USD/MXN, USD/PLN, USD/ILS, and CNH/CNY offshore variants — these have data in the table from BBG historical backfill but may not be updated daily.

**Tenors in DB (22 values):** SPOT, ON, TN, SN, 1W, 2W, 3W, 1M, 2M, 3M, 4M, 5M, 6M, 7M, 8M, 9M, 10M, 11M, 1Y, 2Y, 5Y, 10Y

- Date range: 2007-01-01 to 2026-05-13 (~2.9M rows)
- Update cadence: DAILY (Citi EOD), HOURLY (intraday — 18 hour buckets/day), SNAPSHOT (BBG intraday — legacy backfill)
- Vendor: Citi Velocity (daily/hourly); Bloomberg (historical SNAPSHOT backfill)

### fx.fact_vol

**Pairs (18 — Citi Velocity vol universe):**

EUR/USD, GBP/USD, USD/JPY, AUD/USD, NZD/USD, USD/CAD, USD/CHF, USD/NOK, USD/SEK, USD/CNH, USD/INR, USD/KRW, USD/TWD, USD/THB, USD/IDR, USD/PHP, USD/SGD, USD/HKD

**Strikes (11):** ATM, 25RR, 10RR, 25STR, 10STR, STRIKE_C25, STRIKE_P25, STRIKE_C10, STRIKE_P10, STRIKE_C35, STRIKE_P35

- ATM strike has three `vol_type` values: IMPLIED, REALISED, SPREAD. All other strikes have only IMPLIED.

**Tenors (14):** ON, 1W, 2W, 1M, 2M, 3M, 6M, 9M, 1Y, 2Y, 3Y, 5Y, 7Y, 10Y

- Date range: 2016-01-04 to 2026-05-12 (~8.5M rows)
- Update cadence: DAILY (Citi EOD)
- Vendor: Citi Velocity

### fx.fact_ohlc

**Pairs (17 symbols — BidFX legacy feed):** EURUSD, GBPUSD, AUDUSD, NZDUSD, USDJPY, USDCHF, USDCAD, USDNOK, USDSEK, USDCNH, USDHKD, USDSGD, USDINR, USDKRW, USDTWD, USDTHB, USDIDР

**Series:** SPOT and FORWARD_1M / NDF_1M (34 bars per hour total)

- Date range: 2021-01-03 to 2026-04-28 (~1.1M rows)
- Update cadence: HOURLY (BidFX live feed — retired 2026-04-28)
- Vendor: BidFX

---

## Schema — full dump

### `fx.dim_currency_pair`

One row per tracked currency pair. Shared foreign key dimension for `fact_fx_rate` and `fact_vol`.

| Column | Type | Nullable | FK | Description |
|---|---|---|---|---|
| `id` | INT IDENTITY | NO | — | Surrogate PK |
| `base_ccy` | VARCHAR(3) | NO | — | Base currency ISO code (e.g. EUR) |
| `quote_ccy` | VARCHAR(3) | NO | — | Quote currency ISO code (e.g. USD) |
| `ccy_class` | VARCHAR(20) | NO | — | `g10`, `em_ndf`, or `em_deliverable` |
| `base_currency_id` | TINYINT | YES | `dbo.dim_currency(id)` | FK to currency dimension (modern, post-migration 043) |
| `quote_currency_id` | TINYINT | YES | `dbo.dim_currency(id)` | FK to currency dimension |
| `created_at` | DATETIMEOFFSET | NO | — | Row insertion time |
| `updated_at` | DATETIMEOFFSET | NO | — | Last update time |

**Unique constraint:** `uq_fx_dim_currency_pair` on `(base_ccy, quote_ccy)`

**Note:** 26 rows currently. The string columns `base_ccy` / `quote_ccy` are the practical query keys. `base_currency_id` / `quote_currency_id` are the forward-compatible path added in migration 043.

---

### `fx.fact_fx_rate`

One row per (pair, vendor, frequency, observation timestamp, tenor). Holds spot mid and forward outright mid, plus forward points for non-SPOT tenors.

| Column | Type | Nullable | FK | Description |
|---|---|---|---|---|
| `id` | INT IDENTITY | NO | — | Surrogate PK (NONCLUSTERED) |
| `pair_id` | INT | NO | `fx.dim_currency_pair(id)` | Which pair |
| `vendor_id` | INT | NO | `dbo.dim_vendor(id)` | Source vendor — see enum below |
| `frequency_id` | TINYINT | NO | `dbo.dim_frequency(id)` | DAILY, HOURLY, or SNAPSHOT |
| `obs_ts` | DATETIMEOFFSET(7) | NO | — | UTC observation timestamp. DAILY rows: midnight UTC of obs_date. HOURLY rows: actual hour bucket from Citi. SNAPSHOT rows: Bloomberg intraday snapshot. |
| `obs_date` | DATE | NO | — | UTC date component of `obs_ts`. Retained for backward-compat range scans on the clustered index. |
| `tenor` | VARCHAR(5) | NO | — | One of the 22 tenor values listed in Coverage above |
| `mid_rate` | DECIMAL(18,8) | NO | — | Spot mid (tenor=SPOT) or forward outright mid; always > 0 |
| `fwd_points` | DECIMAL(18,10) | YES | — | Forward points; NULL for SPOT rows, non-null for all other tenors |
| `created_at` | DATETIMEOFFSET | NO | — | Row insertion time |
| `updated_at` | DATETIMEOFFSET | NO | — | Last update time |

**Primary key:** `pk_fx_fact_fx_rate` on `id` (NONCLUSTERED)

**Unique constraint:** `uq_fx_fact_fx_rate` on `(pair_id, vendor_id, frequency_id, obs_ts, tenor)`

**Check constraints:**
- `mid_rate > 0`
- `tenor <> 'SPOT' OR fwd_points IS NULL`

**Indexes:**

| Index | Columns | Purpose |
|---|---|---|
| Clustered | `(obs_date, pair_id, tenor)` | Primary time-series range scan |
| `ix_fx_fact_fx_rate_obs_ts` | `(obs_ts)` | Hour-level range scans |
| `ix_fx_fact_fx_rate_pair` | `(pair_id)` | FK support |
| `ix_fx_fact_fx_rate_vendor` | `(vendor_id)` | FK support |
| `ix_fx_fact_fx_rate_frequency` | `(frequency_id)` | FK support |

---

### `fx.fact_vol`

One row per (pair, obs_date, strike, tenor, vol_type). Daily implied and realized vol surfaces from Citi Velocity.

| Column | Type | Nullable | FK | Description |
|---|---|---|---|---|
| `id` | INT IDENTITY | NO | — | Surrogate PK |
| `pair_id` | INT | NO | `fx.dim_currency_pair(id)` | Which pair |
| `obs_date` | DATE | NO | — | Observation date |
| `strike` | VARCHAR(15) | NO | — | Strike type: ATM, 25RR, 10RR, 25STR, 10STR, STRIKE_C10, STRIKE_C25, STRIKE_C35, STRIKE_P10, STRIKE_P25, STRIKE_P35 |
| `tenor` | VARCHAR(5) | NO | — | Tenor: ON, 1W, 2W, 1M, 2M, 3M, 6M, 9M, 1Y, 2Y, 3Y, 5Y, 7Y, 10Y |
| `vol_type` | VARCHAR(10) | NO | — | `IMPLIED`, `REALISED`, or `SPREAD`. Only ATM has all three; others are IMPLIED only. |
| `value` | FLOAT | NO | — | Vol level in % (e.g. 8.5 = 8.5% annualized vol) |
| `created_at` | DATETIMEOFFSET | NO | — | Row insertion time |
| `updated_at` | DATETIMEOFFSET | NO | — | Last update time |

**Unique constraint:** `uq_fx_fact_vol` on `(pair_id, obs_date, strike, tenor, vol_type)`

**Indexes:** `ix_fx_fact_vol_obs_date` on `(obs_date)`, `ix_fx_fact_vol_pair_date` on `(pair_id, obs_date)`

---

### `fx.fact_ohlc`

One row per (timestamp, symbol, series). Hourly OHLC bars from BidFX (legacy — no new data after 2026-04-28).

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | INT IDENTITY | NO | Surrogate PK |
| `ts` | DATETIMEOFFSET | NO | Start of the hour window (UTC) |
| `symbol` | VARCHAR(10) | NO | Compact pair code, e.g. EURUSD, USDJPY |
| `series` | VARCHAR(30) | NO | `SPOT`, `FORWARD_1M`, or `NDF_1M` |
| `tenor` | VARCHAR(10) | NO | `SPOT` or `1M` |
| `deal_type` | VARCHAR(20) | NO | `SPOT`, `FORWARD`, or `NDF` |
| `pair_used` | VARCHAR(20) | NO | Actual pair sent to BidFX API (may differ if flipped) |
| `open_px` | NUMERIC(18,8) | NO | First mid price in the hour |
| `high_px` | NUMERIC(18,8) | NO | Highest mid price in the hour |
| `low_px` | NUMERIC(18,8) | NO | Lowest mid price in the hour |
| `close_px` | NUMERIC(18,8) | NO | Last mid price in the hour |
| `mid_px` | NUMERIC(18,8) | NO | Quote mid (= close_px) |
| `mid_mean_px` | NUMERIC(18,8) | NO | Arithmetic mean of all mid prices in the hour |
| `mid_median_px` | NUMERIC(18,8) | NO | Median of all mid prices in the hour |
| `bid` | NUMERIC(18,8) | NO | Last bid price in the hour |
| `ask` | NUMERIC(18,8) | NO | Last ask price in the hour |
| `n_ticks` | INT | NO | Tick count used to build the bar |
| `created_at` | DATETIMEOFFSET | NO | Row insertion time |

**Unique constraint:** `uq_fx_fact_ohlc` on `(ts, symbol, series, tenor)`

**Indexes:** rowstore on `ts`, rowstore on `symbol`

---

### `dbo.dim_vendor` (shared across all domains)

| id | vendor_code | display_name |
|---|---|---|
| 1 | citi_velocity | Citi Velocity |
| 2 | barclays | Barclays |
| 3 | bidfx | BidFX |
| 4 | bloomberg | Bloomberg |
| 5 | BBG | Bloomberg |

---

### `dbo.dim_frequency` (shared across all domains)

| id | frequency_code | display_name | typical_seconds |
|---|---|---|---|
| 1 | TICK | Tick-level | 0 |
| 2 | SNAPSHOT | Intraday snapshot (ad-hoc cadence) | NULL |
| 3 | MINUTE | Minute bar | 60 |
| 4 | HOURLY | Hourly bar | 3600 |
| 5 | DAILY | Daily EOD | 86400 |
| 6 | WEEKLY | Weekly | 604800 |
| 7 | MONTHLY | Monthly | 2592000 |
| 8 | QUARTERLY | Quarterly | 7776000 |
| 9 | ANNUAL | Annual | 31536000 |
| 10 | EVENT | Event-driven | NULL |

---

## How to query — examples

**1. Latest SPOT mid rate for all G10 pairs**

```sql
SELECT
    p.base_ccy,
    p.quote_ccy,
    f.mid_rate,
    f.obs_ts
FROM [FX].[fact_fx_rate] f
JOIN [FX].[dim_currency_pair] p ON p.id = f.pair_id
JOIN [dbo].[dim_frequency]   df ON df.id = f.frequency_id
WHERE f.tenor = 'SPOT'
  AND df.frequency_code = 'DAILY'
  AND f.obs_date = (
      SELECT MAX(obs_date)
      FROM [FX].[fact_fx_rate]
      WHERE tenor = 'SPOT'
  )
ORDER BY p.base_ccy, p.quote_ccy;
```

Note: filter on `frequency_code = 'DAILY'` to avoid picking up HOURLY or SNAPSHOT rows for the same obs_date.

---

**2. EUR/USD forward curve as of the most recent daily observation**

```sql
SELECT
    f.tenor,
    f.mid_rate,
    f.fwd_points
FROM [FX].[fact_fx_rate] f
JOIN [FX].[dim_currency_pair] p ON p.id = f.pair_id
JOIN [dbo].[dim_frequency]   df ON df.id = f.frequency_id
WHERE p.base_ccy = 'EUR' AND p.quote_ccy = 'USD'
  AND df.frequency_code = 'DAILY'
  AND f.obs_date = (
      SELECT MAX(obs_date)
      FROM [FX].[fact_fx_rate] f2
      JOIN [FX].[dim_currency_pair] p2 ON p2.id = f2.pair_id
      WHERE p2.base_ccy = 'EUR' AND p2.quote_ccy = 'USD'
  )
ORDER BY
  CASE f.tenor
    WHEN 'SPOT' THEN 0  WHEN 'ON' THEN 1  WHEN 'TN' THEN 2
    WHEN 'SN'   THEN 3  WHEN '1W' THEN 4  WHEN '2W' THEN 5
    WHEN '3W'   THEN 6  WHEN '1M' THEN 7  WHEN '2M' THEN 8
    WHEN '3M'   THEN 9  WHEN '6M' THEN 10 WHEN '9M' THEN 11
    WHEN '1Y'   THEN 12 WHEN '2Y' THEN 13 WHEN '5Y' THEN 14
    WHEN '10Y'  THEN 15 ELSE 99
  END;
```

---

**3. EUR/USD 1M implied vol time series — last 90 days**

```sql
SELECT
    v.obs_date,
    v.value   AS implied_vol_pct
FROM [FX].[fact_vol] v
JOIN [FX].[dim_currency_pair] p ON p.id = v.pair_id
WHERE p.base_ccy = 'EUR' AND p.quote_ccy = 'USD'
  AND v.strike   = 'ATM'
  AND v.tenor    = '1M'
  AND v.vol_type = 'IMPLIED'
  AND v.obs_date >= DATEADD(day, -90, CAST(GETDATE() AS date))
ORDER BY v.obs_date;
```

---

**4. Vol smile for USD/JPY 3M on the latest date (all strikes, implied only)**

```sql
SELECT
    v.strike,
    v.value AS implied_vol_pct
FROM [FX].[fact_vol] v
JOIN [FX].[dim_currency_pair] p ON p.id = v.pair_id
WHERE p.base_ccy = 'USD' AND p.quote_ccy = 'JPY'
  AND v.tenor    = '3M'
  AND v.vol_type = 'IMPLIED'
  AND v.obs_date = (
      SELECT MAX(obs_date)
      FROM [FX].[fact_vol] v2
      JOIN [FX].[dim_currency_pair] p2 ON p2.id = v2.pair_id
      WHERE p2.base_ccy = 'USD' AND p2.quote_ccy = 'JPY'
  )
ORDER BY v.strike;
```

---

**5. Hourly EUR/USD SPOT mid on a specific trading day (intraday bar-by-bar)**

```sql
SELECT
    f.obs_ts,
    f.mid_rate
FROM [FX].[fact_fx_rate] f
JOIN [FX].[dim_currency_pair] p ON p.id = f.pair_id
JOIN [dbo].[dim_frequency]   df ON df.id = f.frequency_id
WHERE p.base_ccy = 'EUR' AND p.quote_ccy = 'USD'
  AND f.tenor    = 'SPOT'
  AND df.frequency_code = 'HOURLY'
  AND f.obs_date = '2026-05-13'
ORDER BY f.obs_ts;
```

---

**6. EURUSD realized vs implied ATM vol 1Y — spread over time**

```sql
SELECT
    obs_date,
    MAX(CASE WHEN vol_type = 'IMPLIED'  THEN value END) AS implied,
    MAX(CASE WHEN vol_type = 'REALISED' THEN value END) AS realised,
    MAX(CASE WHEN vol_type = 'SPREAD'   THEN value END) AS spread
FROM [FX].[fact_vol] v
JOIN [FX].[dim_currency_pair] p ON p.id = v.pair_id
WHERE p.base_ccy = 'EUR' AND p.quote_ccy = 'USD'
  AND v.strike = 'ATM' AND v.tenor = '1Y'
  AND v.obs_date >= '2025-01-01'
GROUP BY v.obs_date
ORDER BY v.obs_date;
```

Note: `REALISED` and `SPREAD` only exist for ATM; querying them on other strikes returns no rows.

---

## Connection details

- **Server:** read from `IMDR_MSSQL_SERVER` environment variable
- **Database:** `IMDR` (never connect to any other database)
- **Auth:** Windows Authentication (`Trusted_Connection=yes`)
- **Driver:** `SQL Server` (legacy ODBC driver; set via `IMDR_MSSQL_DRIVER=SQL+Server`)
- **Access level:** analysts have read-only SELECT on `fx`, `dbo`, `audit` schemas

Python connection example using the project reader:

```python
import pandas as pd
import sqlalchemy as sa
from imdr.connectors.mssql import MSSQLConnector
from imdr.config.settings import get_settings

conn = MSSQLConnector(get_settings())
with conn.engine.connect() as c:
    df = pd.read_sql(
        sa.text("""
            SELECT p.base_ccy, p.quote_ccy, f.tenor, f.mid_rate, f.obs_date
            FROM [FX].[fact_fx_rate] f
            JOIN [FX].[dim_currency_pair] p ON p.id = f.pair_id
            WHERE f.tenor = 'SPOT' AND f.obs_date = :d
        """),
        c, params={"d": "2026-05-13"}
    )
```

---

## Vendor notes

**Citi Velocity** is the primary live data source for both `fact_fx_rate` and `fact_vol`. The Historical API returns time series for named tags in the format `FX.SPOT.{C1}.{C2}.CITI` or `FX.FORWARD.FWD_OUTRIGHT.{C1}.{C2}.{TENOR}.CITI`. NDF currencies (KRW, IDR, PHP, TWD) use the `USD.{NDF}` direction, not the reverse — `USD.KRW` works, `KRW.USD` does not return data. Citi's DAILY runs are triggered at approximately 18:00 SGT (London close), so the "latest daily" observation for APAC pairs may reflect the prior NY close. Vol tag format is `FX.VOL.{C1}.{C2}.{STRIKE}.{TENOR}.{VOL_TYPE}.CITI`; the full cache is at `data/cache/fx/fx_vol_tree.json`.

**BidFX** sourced `fact_ohlc` until 2026-04-28. The feed is retired; no new OHLC data is being written. Historical bars remain queryable but note the `symbol` column uses compact notation (EURUSD, USDJPY) rather than the `base_ccy`/`quote_ccy` split used by the newer tables.

**Bloomberg** contributed historical backfill to `fact_fx_rate` (the SNAPSHOT-frequency rows covering 2007–2019 for the core 19 pairs). BBG data is read-only via the Z:\BBG_mirror\ file share; the R pipeline owns those files.

---

## Where ops detail lives

- Rate pipeline architecture: [fx_rate_pipeline.md](../admin/fx/fx_rate_pipeline.md)
- Rate runbook (backfill, add pair): [fx_rate_operations.md](../admin/fx/fx_rate_operations.md)
- Vol pipeline operations: [fx_vol_operations.md](../admin/fx/fx_vol_operations.md)
- OHLC schema detail: [fx_ohlc_schema.md](../admin/fx/fx_ohlc_schema.md)
- BBG historical integration: [fx_rate_bbg.md](../admin/fx/fx_rate_bbg.md)
- Calendar integration (which dates to skip): [calendar_integration.md](../admin/fx/calendar_integration.md)

---

## Last verified

2026-05-14. Row counts, date ranges, and column lists confirmed against live IMDR DB.
