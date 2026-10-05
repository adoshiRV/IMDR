# HKMA — `playground/econ/hkma/`

**Status:** DATA STALE since 29 May 2026 — **the lane was never scheduled**. 29 indicators ×
192,083 obs in `econ.fact_indicator`, last obs 29 May (HIBOR, FX) / 3 Jun (Aggregate Balance,
monetary base). See [Operational status](#operational-status-2026-10-05) below.

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

## Operational status (2026-10-05)

**The HK lane has no automation.** `scripts/econ/hk/` does not exist (country dirs are
`au bbg id in kr nz us`), and `hkma` appears **0 times** across all seven orchestrators
(`imdr_{daily,hourly,weekly,monthly,quarterly,retry,evening}.py`). Every load to date has been a
hand-run of `fetch.py` piped through the canonical loader; the last one was ~29 May 2026. The
data did not go stale because a task broke — **there is no task**. This is a promotion gap, not a
staleness gap: `fetch.py` lives in gitignored `playground/`, so nothing about it is version
controlled.

**Promotion to `scripts/econ/hk/hkma/` plus a scheduler entry is the actual fix and is NOT done.**
Scheduler registration requires explicit sign-off.

### HKMA API failure modes

| Symptom | Meaning | Handling |
|---|---|---|
| `405 Not Allowed` on **every** endpoint at **every** offset, including offset 0 | Burst throttle. Triggered by walking full history (6.3–7.4k records × 9 endpoints = 60+ requests). Not 429 — do not look for one | Retried with backoff; avoided outright by incremental pagination (below) |
| `502 Bad Gateway` on `api.hkma.gov.hk` while `www.hkma.gov.hk` and `apidocs.hkma.gov.hk` both return 200 | **HKMA-side gateway outage, not an IP block.** Check the other two hosts before assuming you are blocked | Wait it out; retry list covers 502 |

`data.gov.hk` is **not** a fallback: dataset `hk-hkma-dms-daily-figures-interbank-liquidity` only
proxies the same `api.hkma.gov.hk` URL, and the historical-archive API holds no snapshots of it
(it archives file resources, not API endpoints).

**HIBOR fallback that does work:** [HKAB](https://www.hkab.org.hk/en/rates/hibor) publishes the
official fixing (O/N, 1W, 2W, 1M, 2M, 3M, 6M, 12M) at 11:15 HKT daily. Primary source, same
numbers, different host. **The Aggregate Balance has no equivalent free mirror** — if the HKMA API
is down, AB is unobtainable.

### Fetcher hardening (2026-10-05)

Three defects fixed in `fetch.py`, each pinned by tests in
`tests/unit/test_econ/test_hkma_fetch.py`:

1. **Incremental pagination.** Records come newest-first and there is no server-side date filter,
   so `_iter_pages()` now stops once a page runs past `--since`. An incremental run costs **1
   request per endpoint instead of 8**. This is what keeps the run under the throttle.
2. **Backoff instead of abort.** `_get_page()` retries 405/408/429/5xx at 5/15/45/90s then raises
   with the retry count. Previously `raise_for_status()` aborted the whole run **before
   `write_parquet()`**, so a mid-run throttle wrote nothing at all — the run looked like it had
   simply produced no data.
3. **Per-endpoint isolation.** `er_eeri_daily` failing used to take Aggregate Balance, HIBOR and
   the other seven endpoints down with it. Failures are now collected, reported at the end, and
   the remaining endpoints complete.

## Gaps

- **No scheduler entry and no `scripts/econ/hk/`** — see [Operational status](#operational-status-2026-10-05). The single largest gap in this lane.
- `fetch.py` is gitignored (`.gitignore:43 playground/*`), so the hardening above is not in version control; only its tests are.
- C&SD (Census & Statistics Dept) is **not** HKMA. Real-economy series (CPI, GDP, unemployment, trade) are not in this folder — would need a new `playground/econ/cnstat/` for the left half of the HK wiring map.
