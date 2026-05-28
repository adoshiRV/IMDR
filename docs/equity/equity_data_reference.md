# Equity Data — Consumer Reference

Last updated: 2026-05-14

## What's in this domain

The equity domain holds daily close levels for two categories of instruments. **Global equity index levels** (`equities.fact_index_level`) cover 23 indices across the US, Europe, and Asia-Pacific, sourced from Citi Velocity via the `EQUITY.EQUITY_INDEX..{TICKER}.LEVEL.REUTERS` tag namespace; data starts 2026-04-01 (live feed, no backfill loaded yet). **CBOE volatility indices** (`equities.fact_vix`) cover 5 tickers — VIX, VIX3M, VIX9D, VVIX, and VXN — also sourced from Citi Velocity daily with the same history start of 2026-04-01.

Both tables are simple: one row per (index/ticker, date) with a single `close_level` column. The equity domain is live but relatively young — the fact tables hold only data from 2026-04-01 onward as the pipeline was launched in early April 2026. No historical backfill has been loaded. An LLM querying this domain should be aware that multi-year time-series queries will return limited data until a backfill is run.

## Coverage

Universe defined in [`src/imdr/universe/equity.yml`](../../src/imdr/universe/equity.yml).

### equities.fact_index_level — 23 indices

**US (5 indices in fact_index_level; VIX is in fact_vix):**

| Ticker | Index | Currency |
|---|---|---|
| SPX | S&P 500 | USD |
| NDX | Nasdaq 100 | USD |
| RUT | Russell 2000 | USD |
| MID | S&P MidCap 400 | USD |
| OEX | S&P 100 | USD |

**Europe (6 indices):**

| Ticker | Index | Currency |
|---|---|---|
| STOXX50E | Euro Stoxx 50 | EUR |
| SX7E | Euro Stoxx Banks | EUR |
| FTSE | FTSE 100 | GBP |
| FCHI | CAC 40 | EUR |
| OMXS30 | OMX Stockholm 30 | SEK |
| WIG20 | Warsaw WIG 20 | PLN |

**Asia-Pacific (12 indices):**

| Ticker | Index | Currency |
|---|---|---|
| N225 | Nikkei 225 | JPY |
| TOPX | TOPIX | JPY |
| HSI | Hang Seng | HKD |
| HSCE | Hang Seng China Enterprises | HKD |
| HSTECH | Hang Seng Tech | HKD |
| TWII | Taiwan Weighted | TWD |
| TAMSCI | MSCI Taiwan | TWD |
| AXJO | ASX 200 | AUD |
| KS200 | KOSPI 200 | KRW |
| NSEI | Nifty 50 | INR |
| SIMSCI | MSCI Singapore | SGD |
| SET | SET Index | THB |

Note: dim_index has 23 rows (VIX is included there as a lookup entry) but `fact_index_level` stores only the 23 non-VIX-family indices; the VIX family (5 tickers) is stored exclusively in `fact_vix`.

- Date range: 2026-04-01 to 2026-05-12 (~603 rows)
- Update cadence: DAILY (Citi EOD)
- Vendor: Citi Velocity

### equities.fact_vix — 5 volatility tickers

| Ticker | Description |
|---|---|
| VIX | CBOE S&P 500 30-day implied vol index |
| VIX3M | CBOE S&P 500 3-month implied vol index |
| VIX9D | CBOE S&P 500 9-day implied vol index |
| VVIX | CBOE Vol-of-VIX |
| VXN | CBOE Nasdaq 100 volatility index |

Unavailable on Citi: V2X/VSTOXX (Euro vol), VDAX, VIX1D, SKEW, MOVE (ICE/BofA proprietary). VIX is stored in `fact_vix`, not in `fact_index_level`.

- Date range: 2026-04-01 to 2026-05-12 (~136 rows)
- Update cadence: DAILY
- Vendor: Citi Velocity

---

## Schema — full dump

### `equities.dim_index`

One row per tracked index or volatility ticker. Serves as dimension for `fact_index_level`.

| Column | Type | Nullable | FK | Description |
|---|---|---|---|---|
| `id` | INT IDENTITY | NO | — | Surrogate PK |
| `ticker` | VARCHAR(20) | NO | — | Citi ticker (e.g. SPX, N225, STOXX50E) |
| `display_name` | VARCHAR(100) | NO | — | Human-readable name |
| `currency` | VARCHAR(3) | NO | — | Reporting currency ISO code |
| `region` | VARCHAR(30) | NO | — | `us`, `europe`, or `asia_pacific` |
| `citi_tag` | VARCHAR(100) | YES | — | Full Citi Velocity tag (e.g. `EQUITY.EQUITY_INDEX..SPX.LEVEL.REUTERS`) |
| `country_id` | TINYINT | NO | `dbo.dim_country(id)` | Country anchor |
| `created_at` | DATETIMEOFFSET | NO | — | Row insertion time |
| `updated_at` | DATETIMEOFFSET | NO | — | Last update time |

23 rows (5 US, 6 Europe, 12 Asia-Pacific). VIX is included here as a lookup entry even though its data lives in `fact_vix`.

---

### `equities.fact_index_level`

One row per (index, date). Daily close level.

| Column | Type | Nullable | FK | Description |
|---|---|---|---|---|
| `id` | INT IDENTITY | NO | — | Surrogate PK |
| `index_id` | INT | NO | `equities.dim_index(id)` | Which index |
| `obs_date` | DATE | NO | — | Observation date |
| `close_level` | FLOAT | NO | — | Daily close level (e.g. 5500.0 for SPX) |
| `created_at` | DATETIMEOFFSET | NO | — | Row insertion time |
| `updated_at` | DATETIMEOFFSET | NO | — | Last update time |

**Unique constraint:** implied by `(index_id, obs_date)` — pipeline performs MERGE on this natural key.

Quality ranges: close_level validated 1.0–100,000.0 during ingestion.

---

### `equities.fact_vix`

One row per (ticker, date). Stored separately from index levels because VIX family uses a different tag resolution path in the pipeline.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | INT IDENTITY | NO | Surrogate PK |
| `ticker` | VARCHAR(20) | NO | VIX-family ticker: VIX, VIX3M, VIX9D, VVIX, VXN |
| `obs_date` | DATE | NO | Observation date |
| `close_level` | FLOAT | NO | Daily close level (e.g. 16.5 for VIX) |
| `created_at` | DATETIMEOFFSET | NO | Row insertion time |
| `updated_at` | DATETIMEOFFSET | NO | Last update time |

**Unique constraint:** implied by `(ticker, obs_date)`.

Quality ranges: close_level validated 1.0–150.0.

Note: `fact_vix` does not use a foreign key to `dim_index`; it stores the ticker string directly. To join VIX metadata (display name, citi_tag), join `dim_index` on `dim_index.ticker = fact_vix.ticker`.

---

## How to query — examples

**1. SPX daily close — last 30 days**

```sql
SELECT
    il.obs_date,
    il.close_level
FROM [equities].[fact_index_level] il
JOIN [equities].[dim_index] di ON di.id = il.index_id
WHERE di.ticker = 'SPX'
  AND il.obs_date >= DATEADD(day, -30, CAST(GETDATE() AS date))
ORDER BY il.obs_date;
```

---

**2. All index closes on the latest available date**

```sql
SELECT
    di.ticker,
    di.display_name,
    di.currency,
    di.region,
    il.close_level,
    il.obs_date
FROM [equities].[fact_index_level] il
JOIN [equities].[dim_index] di ON di.id = il.index_id
WHERE il.obs_date = (
    SELECT MAX(obs_date) FROM [equities].[fact_index_level]
)
ORDER BY di.region, di.ticker;
```

---

**3. VIX term structure today (VIX vs VIX3M vs VIX9D)**

```sql
SELECT
    ticker,
    close_level,
    obs_date
FROM [equities].[fact_vix]
WHERE ticker   IN ('VIX', 'VIX3M', 'VIX9D')
  AND obs_date = (SELECT MAX(obs_date) FROM [equities].[fact_vix])
ORDER BY ticker;
```

---

**4. VIX vs SPX — daily closes on the same timeline**

```sql
SELECT
    v.obs_date,
    v.close_level  AS vix_level,
    il.close_level AS spx_level
FROM [equities].[fact_vix] v
JOIN [equities].[fact_index_level] il
  ON il.obs_date = v.obs_date
JOIN [equities].[dim_index] di ON di.id = il.index_id
WHERE v.ticker  = 'VIX'
  AND di.ticker = 'SPX'
ORDER BY v.obs_date;
```

---

**5. Asia-Pacific indices — all closes in the last 5 days**

```sql
SELECT
    di.ticker,
    di.display_name,
    di.currency,
    il.obs_date,
    il.close_level
FROM [equities].[fact_index_level] il
JOIN [equities].[dim_index] di ON di.id = il.index_id
WHERE di.region  = 'asia_pacific'
  AND il.obs_date >= DATEADD(day, -5, CAST(GETDATE() AS date))
ORDER BY il.obs_date DESC, di.ticker;
```

---

## Connection details

- **Server:** read from `IMDR_MSSQL_SERVER` environment variable
- **Database:** `IMDR` (never connect to any other database)
- **Auth:** Windows Authentication (`Trusted_Connection=yes`)
- **Driver:** `SQL Server` (legacy ODBC driver; set via `IMDR_MSSQL_DRIVER=SQL+Server`)
- **Access level:** analysts have read-only SELECT on `equities`, `dbo`, `audit` schemas

---

## Vendor notes

**Citi Velocity** is the sole source for both equity tables. The tag namespace for index levels is `EQUITY.EQUITY_INDEX..{TICKER}.LEVEL.REUTERS` — note the double dot (intentional empty issuer segment) and `REUTERS` suffix. Only the `LEVEL` qualifier is available; no OHLCV, no bid/ask. Tags cannot be browsed via the Citi tagbrowsing API but can be fetched directly once the ticker is known. The VIX family uses the same namespace. No ETF tickers are available via this namespace — SPY, QQQ, etc. return no data. Probes confirmed on 2026-03-26 that tickers not listed above (including DAX, SX5E, SXXP, SHCOMP, CSI300, STI, JCI) return no data from Citi.

Citi also offers broader equity data (VARSWAP, EQIVOL, VOLSWAP for 197 single-stocks and indices, 9,779 tags total) that is catalogued but not yet ingested into IMDR. See [`docs/admin/vendors/citi/exploration/equity.md`](../admin/vendors/citi/exploration/equity.md) for the full catalog.

---

## Where ops detail lives

- Citi equity catalog exploration: [`docs/admin/vendors/citi/exploration/equity.md`](../admin/vendors/citi/exploration/equity.md)
- Universe YAML: [`src/imdr/universe/equity.yml`](../../src/imdr/universe/equity.yml)

---

## Last verified

2026-05-14. Row counts, date ranges, and column lists confirmed against live IMDR DB. History limited to 2026-04-01 onward — no backfill loaded yet.
