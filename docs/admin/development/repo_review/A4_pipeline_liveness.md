# A4 — `pipelines.yml` Liveness Map

- **Filed**: 2026-05-14
- **Pipeline keys**: 13

## Method

For each key, `rg` the literal string under `src/` and `scripts/`. Then check
whether any caller is a scheduler (`scripts/imdr_*.py`) or the generic runner
(`run_pipeline.py`).

- **live**   — referenced from a scheduler / `run_pipeline.py`
- **partial** — referenced from src/ or scripts/ but not a scheduler (likely tests or old code)
- **dead**    — no caller found anywhere

## Verdict table

| Key | Verdict | Scheduler hits | Other src callers | Other script callers |
|---|---|---|---|---|
| `fx.spot_rates` | **partial** | — | 1 | 1 |
| `fx.ohlc` | **partial** | — | 1 | 3 |
| `fx.citi_rate` | **partial** | — | 4 | 3 |
| `fx.vol` | **partial** | — | 3 | 3 |
| `rates.vol` | **partial** | — | 2 | 1 |
| `rates.skew` | **partial** | — | 1 | 1 |
| `rates.historical` | **partial** | — | 3 | 5 |
| `rates.bench_rates` | **partial** | — | 2 | 1 |
| `commodities.spot` | **partial** | — | 3 | 1 |
| `commodities.eia` | **partial** | — | 3 | 1 |
| `commodities.vol` | **partial** | — | 3 | 3 |
| `equity.index` | **partial** | — | 3 | 2 |
| `equity.vix` | **partial** | — | 3 | 1 |

## Per-key detail

### `fx.spot_rates` — **partial**

- **Scheduler hits**: —
- **src callers**: src/imdr/domains/fx/pipeline.py
- **script callers**: scripts/run_pipeline.py

### `fx.ohlc` — **partial**

- **Scheduler hits**: —
- **src callers**: src/imdr/domains/fx/pipeline_ohlc.py
- **script callers**: scripts/imdr_health_dashboard.py, scripts/run_pipeline.py, scripts/fx/clean/clean_fx_fact_ohlc.py

### `fx.citi_rate` — **partial**

- **Scheduler hits**: —
- **src callers**: src/imdr/domains/fx/extractors_rate.py, src/imdr/domains/fx/pipeline_rate.py, src/imdr/domains/fx/pipeline_rate_bbg.py, src/imdr/healthchecks/staleness.py
- **script callers**: scripts/imdr_health_dashboard.py, scripts/run_pipeline.py, scripts/fx/clean/clean_fx_fact_fx_rate.py

### `fx.vol` — **partial**

- **Scheduler hits**: —
- **src callers**: src/imdr/domains/fx/pipeline_vol.py, src/imdr/healthchecks/reporter.py, src/imdr/healthchecks/staleness.py
- **script callers**: scripts/imdr_health_dashboard.py, scripts/run_pipeline.py, scripts/fx/clean/clean_fx_fact_vol.py

### `rates.vol` — **partial**

- **Scheduler hits**: —
- **src callers**: src/imdr/domains/rates/pipeline_vol.py, src/imdr/healthchecks/staleness.py
- **script callers**: scripts/run_pipeline.py

### `rates.skew` — **partial**

- **Scheduler hits**: —
- **src callers**: src/imdr/domains/rates/pipeline_skew.py
- **script callers**: scripts/run_pipeline.py

### `rates.historical` — **partial**

- **Scheduler hits**: —
- **src callers**: src/imdr/domains/rates/pipeline.py, src/imdr/domains/rates/pipeline_bbg.py, src/imdr/healthchecks/staleness.py
- **script callers**: scripts/imdr_health_dashboard.py, scripts/run_pipeline.py, scripts/rates/citi/rates_citi_historical.py, scripts/rates/citi/rates_citi_live.py, scripts/rates/clean/clean_rates_fact_observation.py

### `rates.bench_rates` — **partial**

- **Scheduler hits**: —
- **src callers**: src/imdr/domains/rates/pipeline_bench.py, src/imdr/healthchecks/staleness.py
- **script callers**: scripts/run_pipeline.py

### `commodities.spot` — **partial**

- **Scheduler hits**: —
- **src callers**: src/imdr/domains/commodities/extractors.py, src/imdr/domains/commodities/pipeline_spot.py, src/imdr/healthchecks/staleness.py
- **script callers**: scripts/run_pipeline.py

### `commodities.eia` — **partial**

- **Scheduler hits**: —
- **src callers**: src/imdr/domains/commodities/extractors.py, src/imdr/domains/commodities/pipeline_eia.py, src/imdr/healthchecks/staleness.py
- **script callers**: scripts/run_pipeline.py

### `commodities.vol` — **partial**

- **Scheduler hits**: —
- **src callers**: src/imdr/domains/commodities/extractors.py, src/imdr/domains/commodities/pipeline_vol.py, src/imdr/healthchecks/staleness.py
- **script callers**: scripts/imdr_health_dashboard.py, scripts/run_pipeline.py, scripts/commodities/clean/clean_cmdty_fact_implied_vol.py

### `equity.index` — **partial**

- **Scheduler hits**: —
- **src callers**: src/imdr/domains/equity/extractors.py, src/imdr/domains/equity/pipeline_index.py, src/imdr/healthchecks/staleness.py
- **script callers**: scripts/run_pipeline.py, scripts/equity/clean/clean_equity_fact_index_level.py

### `equity.vix` — **partial**

- **Scheduler hits**: —
- **src callers**: src/imdr/domains/equity/extractors.py, src/imdr/domains/equity/pipeline_vix.py, src/imdr/healthchecks/staleness.py
- **script callers**: scripts/run_pipeline.py
