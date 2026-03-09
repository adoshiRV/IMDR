# FX Domain - Database Schema Reference

**Database:** `IMDR`
**Schema:** `[fx]`
**Engine:** Microsoft SQL Server (Windows Authentication)

---

## Tables

### `[fx].[fact_ohlc]` - Hourly OHLC Bars

The primary fact table for FX data. Stores hourly OHLC (Open/High/Low/Close) bars built from tick data sourced from BidFX and CitiVelocity. Each row represents one hour of price action for a single currency pair + series combination.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | `INT IDENTITY` | NO | Auto-increment primary key |
| `ts` | `DATETIMEOFFSET` | NO | Hour timestamp (UTC). The start of the hour window, e.g. `2026-03-09T08:00:00+00:00` means the 08:00-09:00 bar |
| `symbol` | `VARCHAR(10)` | NO | Compact currency pair, e.g. `EURUSD`, `USDCNH`, `USDJPY` |
| `series` | `VARCHAR(30)` | NO | Price series: `SPOT`, `FORWARD_1M`, or `NDF_1M` |
| `tenor` | `VARCHAR(10)` | NO | Instrument tenor: `SPOT` or `1M` |
| `deal_type` | `VARCHAR(20)` | NO | BidFX deal type used for the fetch: `SPOT`, `FORWARD`, or `NDF` |
| `pair_used` | `VARCHAR(20)` | NO | Actual pair sent to the API (may differ from symbol if flipped) |
| `open_px` | `NUMERIC(18,8)` | NO | First mid price in the hour |
| `high_px` | `NUMERIC(18,8)` | NO | Highest mid price in the hour |
| `low_px` | `NUMERIC(18,8)` | NO | Lowest mid price in the hour |
| `close_px` | `NUMERIC(18,8)` | NO | Last mid price in the hour |
| `mid_px` | `NUMERIC(18,8)` | NO | Quote mid (same as close_px - last mid of the window) |
| `mid_mean_px` | `NUMERIC(18,8)` | NO | Arithmetic mean of all mid prices in the hour |
| `mid_median_px` | `NUMERIC(18,8)` | NO | Median of all mid prices in the hour |
| `bid` | `NUMERIC(18,8)` | NO | Last bid price in the hour |
| `ask` | `NUMERIC(18,8)` | NO | Last ask price in the hour |
| `n_ticks` | `INT` | NO | Number of ticks used to build this bar |
| `created_at` | `DATETIMEOFFSET` | NO | Row insertion timestamp (server default) |

**Constraints:**
- `PK` on `id`
- `UNIQUE (ts, symbol, series, tenor)` as `uq_fx_fact_ohlc` - prevents duplicate bars

**Indexes:**
- Rowstore index on `ts`
- Rowstore index on `symbol`
- `ncci_fact_ohlc` - Nonclustered columnstore index on all analytical columns (10-100x faster for scans, aggregations, cross-symbol comparisons)

**Note:** This table does NOT have an `updated_at` column. Bars are insert-or-replace (upsert on the unique constraint), not updated in place.

---

## Views

### `[fx].[vw_ohlc_daily]` - Daily OHLC Rollup

Aggregates hourly bars into daily OHLC bars. Groups by `(symbol, series, tenor, deal_type, pair_used, trade_date)`.

| Column | Description |
|---|---|
| `symbol` | Currency pair |
| `series` | Price series |
| `tenor` | Instrument tenor |
| `deal_type` | Deal type |
| `pair_used` | API pair used |
| `trade_date` | Calendar date (from `CAST(ts AS DATE)`) |
| `open_px` | `MIN(open_px)` across hours |
| `high_px` | `MAX(high_px)` across hours |
| `low_px` | `MIN(low_px)` across hours |
| `close_px` | `MAX(close_px)` across hours |
| `avg_mid_px` | `AVG(mid_px)` across hours |
| `avg_mid_mean_px` | `AVG(mid_mean_px)` across hours |
| `avg_mid_median_px` | `AVG(mid_median_px)` across hours |
| `min_bid` | `MIN(bid)` across hours |
| `max_ask` | `MAX(ask)` across hours |
| `total_ticks` | `SUM(n_ticks)` across hours |
| `row_count` | Number of hourly bars in the day |

---

### `[fx].[vw_daily_change]` - Day-over-Day % Change

Computes day-over-day percentage change on `close_px` using `LAG()`, partitioned by `(symbol, series)`.

| Column | Description |
|---|---|
| `symbol` | Currency pair |
| `series` | Price series |
| `trade_date` | Calendar date |
| `close_px` | Daily close |
| `mid_px` | Daily mid |
| `prev_close_px` | Previous day's close (via `LAG`) |
| `pct_change_close` | `(close - prev_close) / prev_close * 100` |

---

### `[fx].[vw_ohlc_moving_avg]` - Moving Averages + Z-Score

Daily close with 5/20/50-day moving averages and a 20-day rolling z-score, partitioned by `(symbol, series)`.

| Column | Description |
|---|---|
| `symbol` | Currency pair |
| `series` | Price series |
| `trade_date` | Calendar date |
| `close_px` | Daily close |
| `ma_5d` | 5-day moving average |
| `ma_20d` | 20-day moving average |
| `ma_50d` | 50-day moving average |
| `z_score_20d` | 20-day rolling z-score: `(close - ma_20d) / stdev_20d` |

---

### `[fx].[vw_ohlc_summary]` - Data Inventory (Indexed View)

Materialized summary of what data exists per symbol/series. This is an **indexed view** (with `SCHEMABINDING`) for instant lookups.

| Column | Description |
|---|---|
| `symbol` | Currency pair |
| `series` | Price series |
| `total_rows` | Number of hourly bars |
| `total_ticks` | Sum of all ticks across bars |
| `first_ts` | Earliest bar timestamp |
| `last_ts` | Latest bar timestamp |

**Index:** Unique clustered index on `(symbol, series)` as `uci_vw_ohlc_summary`

---

## Universe Coverage

The FX domain tracks **17 currencies** against USD:

| Classification | Currencies | Series Fetched | Deal Type |
|---|---|---|---|
| **G10** | USD, EUR, GBP, JPY, CHF, AUD, NZD, CAD, NOK, SEK, CNH | SPOT + FORWARD_1M | SPOT, FORWARD |
| **EM NDF** | INR, KRW, TWD, THB, IDR, PHP | SPOT + NDF_1M | NDF (single fetch derives both bars) |
| **EM Deliverable** | SGD | SPOT + FORWARD_1M | SPOT, FORWARD |

This produces **34 bars per hour** (17 currencies x 2 series each).

**Pair conventions:** Pairs follow market convention priority (EUR > GBP > AUD > NZD > USD > CAD > CHF > NOK > SEK > JPY). For example: `EURUSD` (not USDEUR), but `USDJPY` (not JPYUSD).

---

## Price Calculation Logic

### SPOT bars
- **mid** = `(bid_spot + ask_spot) / 2` (fallback: `mid_spot` or `mid` field)
- **bid/ask** = `bid_spot` / `ask_spot` from tick

### FORWARD_1M bars
- **outright_bid** = `bid_spot + bid_forward_points`
- **outright_ask** = `ask_spot + ask_forward_points`
- **mid** = `(outright_bid + outright_ask) / 2`
- Forward points are raw decimal values from BidFX (no pip divisor needed)

### NDF_1M bars (EM NDF currencies)
- Same calculation as FORWARD_1M (outright from spot + forward points)
- A single NDF API fetch produces **both** the NDF_1M bar (outright prices) and the SPOT bar (spot fields from the same tick stream)

### OHLC from ticks
- **open** = first mid in the hour
- **high** = max mid in the hour
- **low** = min mid in the hour
- **close** = last mid in the hour
- **mid_mean** = arithmetic mean of all mids
- **mid_median** = median of all mids
- **bid/ask** = last bid/ask in the hour
- **n_ticks** = count of valid ticks used

---

## Audit Table

Pipeline runs are tracked in `[audit].[pipeline_runs]` (separate schema, shared across all domains).

| Column | Type | Description |
|---|---|---|
| `id` | `INT IDENTITY` | Auto-increment PK |
| `pipeline_name` | `VARCHAR(100)` | e.g. `fx_bidfx_live`, `fx_bidfx_historical` |
| `domain` | `VARCHAR(50)` | `fx` |
| `run_status` | `VARCHAR(20)` | `running`, `success`, `failed`, `partial` |
| `started_at` | `DATETIMEOFFSET` | Pipeline start time |
| `finished_at` | `DATETIMEOFFSET` | Pipeline end time (null while running) |
| `rows_extracted` | `INT` | Bars extracted from API |
| `rows_loaded` | `INT` | Bars written to DB |
| `error_message` | `VARCHAR(2000)` | Error details if failed |
| `health_check_passed` | `BIT` | Post-load health check result |
| `health_check_details` | `NVARCHAR(MAX)` | JSON blob with check details |
| `created_at` | `DATETIMEOFFSET` | Row creation time |
| `updated_at` | `DATETIMEOFFSET` | Last update time |

---

## Partitioning (Future)

Monthly partitioning on `ts` is documented in `migrations/005_partitioning_strategy.sql` but **not yet applied**. Should be considered when `fact_ohlc` exceeds ~50M rows. The template covers partition function creation, scheme setup, clustered index rebuild, and maintenance for adding new monthly boundaries.

---

## Migration Files

| Migration | Description | Status |
|---|---|---|
| `001_create_pipeline_runs.sql` | Creates `[audit].[pipeline_runs]` table | Applied |
| `003_columnstore_fx_fact_ohlc.sql` | Adds NCCI on `[fx].[fact_ohlc]` for analytical queries | Applied |
| `004_views_fx_analytics.sql` | Creates 4 analytical views (daily, change, moving avg, summary) | Applied |
| `005_partitioning_strategy.sql` | Monthly partitioning template (commented out) | Not applied |
