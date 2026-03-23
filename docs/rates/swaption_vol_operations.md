# Rates Swaption Vol — Operations Guide

User-facing guide for running, monitoring, and maintaining the rates swaption vol pipeline.

For schema details, see `docs/rates/swaption_vol_schema.md`.

---

## Pipeline Overview

The rates swaption vol pipeline ingests daily ATM swaption vol surfaces from Citi Velocity for 11 currencies across 6 data types (~38,000 rows/day).

**Table:** `[rates].[fact_swaption_vol]`
**Dimension:** `[rates].[dim_vol_surface]`
**Date column:** `obs_date`
**Value column:** `value`

---

## Scripts

### Daily EOD — `scripts/rates/citi/rates_vol_citi_live.py`

```bash
python -m scripts.rates.citi.rates_vol_citi_live
python -m scripts.rates.citi.rates_vol_citi_live --date 2026-03-10
python -m scripts.rates.citi.rates_vol_citi_live --currencies USD,EUR,JPY
```

- Runs as part of `scripts/imdr_daily.py` orchestrator
- Determines last business day automatically
- Skips weekends
- Logs per-currency breakdown

### Historical Backfill — `scripts/rates/citi/rates_vol_citi_historical.py`

Edit the `CONFIGURE HERE` section and run:

```bash
python -m scripts.rates.citi.rates_vol_citi_historical
```

**Modes:**
- `range`: Backfill from START to END date (processes day by day)
- `catchup`: Last N calendar days
- `gaps`: Read dates from a text file

**Config variables:**
- `MODE`: "range" | "catchup" | "gaps"
- `START`, `END`: Date range (YYYY-MM-DD)
- `LOOKBACK_DAYS`: For catchup mode
- `GAPS_FILE`: Path to gaps file (one date per line)
- `CURRENCIES`: Optional list to limit currencies (None = all 11)

### Generic Runner — `scripts/run_pipeline.py`

```bash
python -m scripts.run_pipeline rates.vol --start 2026-03-10 --end 2026-03-10
python -m scripts.run_pipeline rates.vol --start 2024-01-01 --end 2024-12-31 --currencies USD,EUR
```

---

## Monitoring

### Expected Row Counts

| Scope | Expected Rows/Day |
|-------|-------------------|
| All 11 currencies | ~38,000 |
| Single G10 ccy (no RFR) | ~2,560 |
| Single G10 ccy (with RFR) | ~4,450 |

### Health Checks

Run automatically via `pipeline.run()`:
- **RowCountCheck**: min 50 rows per run
- **NullCheck**: no nulls in required columns
- **DuplicateCheck**: no duplicate natural keys
- **FreshnessCheck**: data not older than 48 hours

### Quality Checks (post-load, flag only)

- **CompositeRangeCheck**: Values within configured bounds per (data_type, quote_type)
- **PercentageChangeCheck**: Day-over-day moves >50% flagged
- **RobustStatisticalOutlierCheck**: MAD-based outlier detection (n_mad=4.0)

---

## Troubleshooting

### No data returned for a currency

1. Check if it's a holiday: `holiday_hits_for_timestamp([ccy], target_date)`
2. Verify API connectivity: run with `--currencies {ccy}` for isolation
3. Check Citi Velocity API status (token expiry, rate limits)

### Duplicate key errors

The pipeline uses MERGE (upsert) — duplicates are handled by updating the existing row. If you see constraint violations, check that `dim_vol_surface` was properly seeded.

### Missing dimension rows

The pipeline auto-seeds `dim_vol_surface` during `transform()`. If surfaces are missing, verify `universe/rates.yml` vol section is up to date and re-run.

### Backfill taking too long

At ~6.5 minutes per day (381 API batches), a full year backfill = ~27 hours. Consider:
- Limiting to specific currencies: `CURRENCIES = ["USD", "EUR"]`
- Running overnight with `nohup`

---

## File Locations

| Component | Path |
|-----------|------|
| Pipeline | `src/imdr/domains/rates/pipeline_vol.py` |
| Extractor | `src/imdr/domains/rates/extractors_vol.py` |
| Tag parser | `src/imdr/domains/rates/vol_translate.py` |
| Repository | `src/imdr/domains/rates/repository_vol.py` |
| ORM models | `src/imdr/models/rates_vol.py` |
| Pydantic schemas | `src/imdr/schemas/rates_vol.py` |
| Parquet store | `src/imdr/domains/rates/store_vol.py` |
| Universe config | `src/imdr/universe/rates.yml` (vol section) |
| Pipeline config | `src/imdr/config/pipelines.yml` (rates.vol section) |
| Migration | `migrations/007_create_rates_swaption_vol.sql` |
| Live script | `scripts/rates/citi/rates_vol_citi_live.py` |
| Historical script | `scripts/rates/citi/rates_vol_citi_historical.py` |
| Parquet archive | `data/parquet/rates/swaption_vol/{ccy}/{YYYY-MM}.parquet` |
