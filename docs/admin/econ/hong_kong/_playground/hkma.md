# HKMA — `playground/econ/hkma/`

**Status:** LIVE. 29 indicators × 192,083 obs in `econ.fact_indicator`.

HKMA public API. No auth required. The reference vendor for the **config-driven multi-endpoint pattern** ([[feedback-econ-vendor-config-driven]]): one `_ENDPOINTS` dict, one generic loop, adding an endpoint is a 1-dict-entry change.

## Contents

| File | Purpose |
|---|---|
| `fetch.py` | Pulls all 10 endpoints in one run via `_ENDPOINTS` dict + generic loop. Writes parquet pairs to `sample_output/`. |
| `sample_output/` | Date-tree parquet output for the canonical loader. |

No `seed.yml` — configuration is embedded in `fetch.py` via `_ENDPOINTS` and `_SERIES_META`.

## `_ENDPOINTS` dict (10 endpoints, 19 series)

| Key | Cadence | What |
|---|---|---|
| `agg_bal` | Daily | Aggregate Balance (closing) — interbank liquidity proxy |
| `mon_base` | Daily | Monetary Base, Certificates of Indebtedness, EFB+EFN outstanding |
| `hibor_daily` | Daily | HIBOR fixings: O/N, 1W, 1M, 3M, 6M, 12M |
| `er_eeri_daily` | Daily | HKD spot rates (USD/EUR/GBP/JPY/CNY/SGD) + NEERI trade/import/export weighted indices |
| `composite_ir` | Monthly | Composite interest rate |
| `fx_reserves` | Monthly | Foreign currency reserves total |
| `money_supply` | Monthly | M1/M2/M3 + currency in circulation |
| `asset_quality` | Monthly | Retail bank NPL ratio, classified loans, loans overdue/restructured |
| `loans_sector` | Monthly | Total loans in HK by sector |
| (10th) | Monthly | (see fetch.py) |

## Pattern: config-driven multi-endpoint fetchers

This is the reference shape for any future vendor with N similar endpoints:

```python
_ENDPOINTS = {
    "endpoint_key": {
        "url": "...",
        "cadence": "DAILY",
        "series": [...],     # which fields to extract
        "metadata": {...},   # name, units, country, category
    },
    # ...
}

def fetch_all():
    for key, cfg in _ENDPOINTS.items():
        rows = _fetch_endpoint(cfg)
        _write_parquet(key, rows)
```

Adding a new HKMA endpoint = 1 dict entry. Adopted as the canonical shape after the 2026-06-03 refactor (see [[feedback-econ-vendor-config-driven]]).

## Canonical loader

```bash
python -m scripts.migrations.load_econ_indicator_from_playground --vendor hkma
```

## Gaps

- C&SD (Census & Statistics Dept) is **not** HKMA. Real-economy series (CPI, GDP, unemployment, trade) are not in this folder — would need a new `playground/econ/cnstat/` for the left half of the HK wiring map.
