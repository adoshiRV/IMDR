# Rates Swaption Skew

## Overview

Swaption skew data captures the **normalised implied volatility** at various strike offsets from ATM (at-the-money) across the option expiry x swap tenor grid. This data is essential for pricing, hedging, and risk management of interest rate swaptions.

Values represent **absolute normalised basis point volatility** at each strike — not the spread from ATM. The spread can be computed at query time by subtracting the ATM vol from the corresponding `fact_swaption_vol` table.

## Data Source

**Vendor**: Barclays Trading / S&P Global Market Intelligence
**Delivery**: Excel files (`.xlsx`), manually downloaded
**Format**: Wide time-series with columns per tenor/strike combination

### Column Header Format

```
USDSW{EXPIRY}{TENOR}F Normalised vol ATM {STRIKE} bp
```

Example: `USDSW9M1YF Normalised vol ATM -200 bp`
- Currency: USD
- Option expiry: 9M
- Swap tenor: 1Y
- Strike offset: -200 bps from ATM

### Grid Dimensions

| Dimension | Values |
|-----------|--------|
| **Currency** | USD (initially; expandable) |
| **Option expiry** | 3M, 6M, 9M |
| **Swap tenor** | 1Y, 2Y, 5Y, 10Y |
| **Strike offset** | -200, -150, -100, -75, -50, -25, +25, +50, +75, +100, +150, +200 bps |
| **Data points/day** | 3 x 4 x 12 = **144** |

### Historical Depth

- Start: 2016-04-15
- End: present (updated periodically)
- ~2,608 trading days in initial load

## Database Schema

### Dimension: `rates.dim_skew_surface`

One row per (currency, option expiry) combination.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INT (PK) | Auto-increment |
| `ccy` | VARCHAR(3) | Currency code (e.g. USD) |
| `option_expiry` | VARCHAR(4) | Option expiry tenor (e.g. 3M, 6M, 9M) |
| `market_code` | VARCHAR(5) | Nullable FK for calendar integration |

**Unique constraint**: `(ccy, option_expiry)`

### Fact: `rates.fact_swaption_skew`

Daily observations on the swap_tenor x strike_offset grid.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INT (PK) | Auto-increment |
| `surface_id` | INT (FK) | References `dim_skew_surface.id` |
| `vendor_id` | INT (FK) | References `dbo.dim_vendor.id` |
| `obs_date` | DATE | Observation date |
| `swap_tenor` | VARCHAR(4) | Swap tenor (1Y, 2Y, 5Y, 10Y) |
| `strike_offset` | INT | Basis points from ATM (-200 to +200) |
| `vol` | FLOAT | Absolute normalised bp vol |

**Unique constraint**: `(surface_id, obs_date, swap_tenor, strike_offset)`

## Operations

### Daily automation

Registered as feed `barclays_skew` in `src/imdr/vendors/specs/barclays_skew.py` and scheduled by `scripts/imdr_daily.py` at 08:00 SGT. The runner fetches the newest SKEW BARCLAYS email, downloads the 7 linked Excel files to `data/skew/`, runs `RatesSkewPipeline`, archives to `data/skew/old/`, and sends a success or failure email.

End-to-end run:

```bash
python -m scripts.run_vendor_feed barclays_skew
```

SSO bootstrap (first run or after cookie expiry):

```bash
python -m scripts.run_vendor_feed barclays_skew --headed
```

See [docs/admin/vendors/feeds/barclays_skew.md](../admin/vendors/feeds/barclays_skew.md) for full operational notes, the failure playbook, and [docs/admin/vendors/index.md](../admin/vendors/index.md) for the framework overview.

### Initial Historical Load

1. Place Excel files in `data/skew/`
2. Run the loader:

```bash
python -m scripts.rates.barclays.rates_skew_load
```

The script auto-discovers all `.xlsx` files in the drop folder and auto-detects the option expiry from column headers (not filenames).

### Incremental Load

For date-filtered updates:

```bash
python -m scripts.rates.barclays.rates_skew_load --start 2026-04-01 --end 2026-04-14
```

### Explicit File Paths

```bash
python -m scripts.rates.barclays.rates_skew_load --files path/to/file1.xlsx path/to/file2.xlsx
```

### Via Generic Runner

```bash
python -m scripts.run_pipeline rates.skew --start 2024-01-01 --end 2024-12-31
```

### CLI Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--dir` | `data/skew` | Directory to scan for .xlsx files |
| `--files` | (none) | Explicit file paths (overrides --dir) |
| `--start` | all | Start date filter (YYYY-MM-DD) |
| `--end` | all | End date filter (YYYY-MM-DD) |
| `--chunk-size` | 5000 | Chunk size for bulk merge |

## Common Queries

### Latest skew surface for USD 9M expiry

```sql
SELECT s.option_expiry, f.obs_date, f.swap_tenor, f.strike_offset, f.value
FROM rates.fact_swaption_skew f
JOIN rates.dim_skew_surface s ON f.surface_id = s.id
WHERE s.ccy = 'USD' AND s.option_expiry = '9M'
  AND f.obs_date = (SELECT MAX(obs_date) FROM rates.fact_swaption_skew)
ORDER BY f.swap_tenor, f.strike_offset;
```

### Skew smile for a specific date and tenor

```sql
SELECT f.strike_offset, f.value
FROM rates.fact_swaption_skew f
JOIN rates.dim_skew_surface s ON f.surface_id = s.id
WHERE s.ccy = 'USD' AND s.option_expiry = '6M'
  AND f.obs_date = '2026-04-14'
  AND f.swap_tenor = '10Y'
ORDER BY f.strike_offset;
```

### Skew time series at -100bp strike

```sql
SELECT f.obs_date, s.option_expiry, f.swap_tenor, f.value
FROM rates.fact_swaption_skew f
JOIN rates.dim_skew_surface s ON f.surface_id = s.id
WHERE s.ccy = 'USD' AND f.strike_offset = -100
  AND f.obs_date >= '2025-01-01'
ORDER BY f.obs_date, s.option_expiry, f.swap_tenor;
```

## Pipeline Architecture

```
data/skew/*.xlsx
    → skew_translate.read_skew_files()     [Excel parse + wide-to-long]
    → RatesSkewPipeline.transform()        [seed dim, resolve FKs, Pydantic validate]
    → RatesSkewPipeline.load()             [chunked_bulk_merge → SQL Server]
    → RatesSkewPipeline.post_load()        [parquet archive + health checks]
```

### Key Files

| File | Purpose |
|------|---------|
| `migrations/017_create_rates_swaption_skew.sql` | DDL for dim + fact tables |
| `migrations/018_create_dim_vendor.sql` | Shared vendor dimension |
| `src/imdr/models/rates_skew.py` | ORM models |
| `src/imdr/schemas/rates_skew.py` | Pydantic validation schemas |
| `src/imdr/domains/rates/skew_translate.py` | Excel column parser + file reader |
| `src/imdr/domains/rates/repository_skew.py` | Data access layer (MergeSpec) |
| `src/imdr/domains/rates/store_skew.py` | Parquet archive store |
| `src/imdr/domains/rates/pipeline_skew.py` | ETL pipeline |
| `scripts/rates/barclays/rates_skew_load.py` | CLI load script |

### Parquet Archive

Layout: `data/parquet/rates/swaption_skew/{ccy}/{YYYY-MM}.parquet`

Partitioned by currency and month. Each file contains deduplicated observations with columns: `obs_date`, `option_expiry`, `swap_tenor`, `strike_offset`, `vol`.
