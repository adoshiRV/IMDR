# Australia — Cadence Analysis for Prod Orchestrators

Last updated: 2026-06-11

Per `econ_to_prod.md` §G.3 ("One orchestrator, many cadences"), AU needs orchestrators bucketed by cadence: `au_daily.py` / `au_weekly.py` / `au_monthly.py`. Quarterly fetchers fold into monthly (the playbook explicitly says so). This doc maps every AU fetcher — Track A (data series) AND Track B (filings) — to its proper cadence so the right orchestrator runs at the right time.

## TL;DR

| Orchestrator | Status | What goes in | Why |
|---|---|---|---|
| `au_daily.py` | **PROD-BUILT 2026-06-11** (filings only — needs expansion) | Phase J filings ingest + 5 daily Track A fetchers | Live-rate / live-FX / live-curve + daily housing + daily govt filings |
| `au_weekly.py` | **NOT REQUIRED** | — | Zero genuinely-weekly AU series. Korea has it only because REB R-ONE is weekly. AU doesn't have a weekly cadence anywhere. |
| `au_monthly.py` | **NOT YET BUILT** | 25 fetchers: 6 ABS monthly + 12 ABS quarterly + 2 RBA monthly + 3 RBA quarterly + 1 RBA event + 5 AOFM monthly (manual-refresh) | Real-economy series + balance sheet quarterlies fold here per playbook G.3 |
| `au_full.py` | **NEW — proposed** | calls daily + monthly back-to-back | One-shot full refresh — backfill, catch-up after downtime, manual debug, ad-hoc full reload. NOT scheduler-wired; manual invocation only. |

## Full fetcher inventory mapped to cadence

### Track A — Data series (32 fetchers)

#### Daily (5 fetchers)

| Fetcher | Vendor | Series count | Cadence-source | Notes |
|---|---|---|---|---|
| `fetch_rates.py` | RBA | 12 (F1+F2 cash/BBSW/OIS/AGB/TIB) | Daily business-day | Live rates curve |
| `fetch_fx.py` | RBA | 19 (F11.1 AUD crosses + TWI) | Daily business-day | Live FX |
| `fetch_zerocoupon.py` | RBA | 16 (F17 yields + forwards × 8 tenors) | Daily business-day | Analytical curve |
| `fetch_hvi.py` (cotality) | Cotality | 6 (HVI 5 capitals + aggregate) | Daily | Each run captures today's snapshot; accumulates over time |
| **Filings ingest** | (Phase J) | — | Daily | All Phase J fetchers — already wired in `au_daily.py` |

#### Monthly (8 fetchers — including AOFM)

| Fetcher | Vendor | Series count | Notes |
|---|---|---|---|
| `fetch_cpi.py` | ABS | 16 | Monthly headline + Trimmed Mean / Weighted Median (M); also has Q sub-series |
| `fetch_labour.py` | ABS | 6 | Unemployment + Participation + Employment (M) |
| `fetch_lf_under.py` | ABS | 3 | Underutilisation (M) |
| `fetch_retail.py` | ABS | 10 | Retail Trade (M) |
| `fetch_lending.py` | ABS | 11 | New lending commitments — LEND_HOUSING/BUSINESS/PERSONAL (M) |
| `fetch_building_approvals.py` | ABS | 4 | Dwelling count + value-of-jobs (M) |
| `fetch_monetary.py` | RBA | 14 | D3 monetary aggregates (M) |
| `fetch_icp.py` | RBA | 21 | I2 Commodity Prices (M) |

#### Quarterly (folds into monthly per playbook G.3) (10 fetchers)

| Fetcher | Vendor | Series count | Notes |
|---|---|---|---|
| `fetch_gdp.py` | ABS | 7 | ANA_AGG chain-volume GDP |
| `fetch_gdp_expenditure.py` | ABS | 10 | ANA_EXP demand-side decomp |
| `fetch_wpi.py` | ABS | 6 | Wage Price Index |
| `fetch_ppi_fd.py` | ABS | 3 | Producer Prices Final Demand |
| `fetch_capex.py` | ABS | 4 | Private new capital expenditure |
| `fetch_rppi.py` | ABS | 17 | Residential property price index |
| `fetch_bop.py` | ABS | 14 | Balance of Payments — current + financial accounts |
| `fetch_bop_goods.py` | ABS | 7 | BOP goods chain-volume |
| `fetch_trade_prices.py` | ABS | 24 | ITPI imports/exports (incl. SITC 1-digit) |
| `fetch_job_vacancies.py` | ABS | 3 | Job Vacancies survey |
| `fetch_iip.py` | ABS | 33 | International Investment Position stocks |
| `fetch_tot.py` | ABS | 1 | Derived Terms of Trade (= ITPI_EXP/ITPI_IMP × 100) |
| `fetch_reer.py` | RBA | 3 | F15 Real Exchange Rate Measures |

#### Mixed-cadence fetcher (runs at highest cadence — monthly) (1 fetcher)

| Fetcher | Vendor | Series count | Mix |
|---|---|---|---|
| `fetch_credit_balsheet.py` | RBA | 34 | D2 credit aggregates (M) + E1+E2 household balsheets (Q) + A2 cash-rate event log |

#### AOFM (manual-Edge XLSX refresh, monthly cadence) (5 fetchers)

| Fetcher | Series count | Notes |
|---|---|---|
| `fetch_foreign_holdings.py` | 34 | Quarterly underlying but monthly XLSX refresh |
| `fetch_portfolio_aggregate.py` | 16 | Monthly outstanding by instrument |
| `fetch_term_premium.py` | 30 | Daily underlying, monthly XLSX publish |
| `fetch_turnover.py` | 67 | Monthly turnover by region/tenor |
| `fetch_issuance_buybacks.py` | 10 | Monthly gross issuance + buyback flows |

**AOFM caveat**: corp-firewall blocks Chrome/Playwright from `aofm.gov.au/sites/default/files/*`. The orchestrator can only run these fetchers AFTER a human has manually downloaded the latest XLSXs via Edge into `data/econ/au/aofm/discovery/xlsx/`. So the prod path is: **monthly Edge manual download → `au_monthly.py` ingests**. See `_playground/aofm.md`.

#### FRED OECD mirror (3 indicators)

Already loaded once-off; FRED is a US-domain vendor with its own loader path. Not in AU country orchestrators.

### Track B — Filings (8 fetchers)

All 8 go in `au_daily.py` via `scripts.econ.au.govt.ingest_filings`. Already wired and proven 2026-06-11. Sub-cadences within the 8 (Governor's Statement T+0, Board Minutes T+14, SMP quarterly, FSR semi-annual, Speeches ad-hoc, Treasury various, APRA quarterly, ABS monthly/quarterly) all collapse into "run discovery daily, skip if seen.json deduplicates".

## Proposed orchestrator structure

### `au_daily.py` (EXTEND from current Phase J-only version)

```python
PIPELINES: list[list[str]] = [
    # Filings ingest (Phase J — LIVE)
    [sys.executable, "-m", "scripts.econ.au.govt.ingest_filings", "--ingest"],

    # Daily Track A (after Phase G promotion)
    [sys.executable, "-m", "scripts.econ.au.cotality.cotality_hvi"],
    [sys.executable, "-m", "scripts.econ.au.rba.rba_rates"],
    [sys.executable, "-m", "scripts.econ.au.rba.rba_fx"],
    [sys.executable, "-m", "scripts.econ.au.rba.rba_zerocoupon"],
]
```

Daily Track A fetchers stay GATED until Phase G promotion lands. The filings entry is the only line live today.

### `au_weekly.py` (NOT REQUIRED)

No genuinely-weekly AU series exist. Skip this orchestrator entirely. If a weekly cadence emerges later (e.g. an RBA H-table that updates weekly), add the file then. Korea has `kr_weekly.py` only because REB R-ONE weekly rent indices are genuinely weekly.

### `au_monthly.py` (NEW — to be built in Phase G)

Per playbook G.3 quarterly fetchers fold here. ~25 fetchers total.

```python
PIPELINES: list[list[str]] = [
    # ABS monthly (after Phase G promotion)
    [sys.executable, "-m", "scripts.econ.au.abs.abs_cpi"],
    [sys.executable, "-m", "scripts.econ.au.abs.abs_labour"],
    [sys.executable, "-m", "scripts.econ.au.abs.abs_lf_under"],
    [sys.executable, "-m", "scripts.econ.au.abs.abs_retail"],
    [sys.executable, "-m", "scripts.econ.au.abs.abs_lending"],
    [sys.executable, "-m", "scripts.econ.au.abs.abs_building_approvals"],

    # ABS quarterly (folded into monthly per G.3)
    [sys.executable, "-m", "scripts.econ.au.abs.abs_gdp"],
    [sys.executable, "-m", "scripts.econ.au.abs.abs_gdp_expenditure"],
    [sys.executable, "-m", "scripts.econ.au.abs.abs_wpi"],
    [sys.executable, "-m", "scripts.econ.au.abs.abs_ppi_fd"],
    [sys.executable, "-m", "scripts.econ.au.abs.abs_capex"],
    [sys.executable, "-m", "scripts.econ.au.abs.abs_rppi"],
    [sys.executable, "-m", "scripts.econ.au.abs.abs_bop"],
    [sys.executable, "-m", "scripts.econ.au.abs.abs_bop_goods"],
    [sys.executable, "-m", "scripts.econ.au.abs.abs_trade_prices"],
    [sys.executable, "-m", "scripts.econ.au.abs.abs_job_vacancies"],
    [sys.executable, "-m", "scripts.econ.au.abs.abs_iip"],
    [sys.executable, "-m", "scripts.econ.au.abs.abs_tot"],

    # RBA monthly + quarterly + mixed
    [sys.executable, "-m", "scripts.econ.au.rba.rba_monetary"],          # D3
    [sys.executable, "-m", "scripts.econ.au.rba.rba_icp"],                # I2
    [sys.executable, "-m", "scripts.econ.au.rba.rba_credit_balsheet"],    # D2+E1+E2+A2
    [sys.executable, "-m", "scripts.econ.au.rba.rba_reer"],               # F15

    # AOFM monthly (manual Edge refresh required upstream)
    [sys.executable, "-m", "scripts.econ.au.aofm.aofm_foreign_holdings"],
    [sys.executable, "-m", "scripts.econ.au.aofm.aofm_portfolio_aggregate"],
    [sys.executable, "-m", "scripts.econ.au.aofm.aofm_term_premium"],
    [sys.executable, "-m", "scripts.econ.au.aofm.aofm_turnover"],
    [sys.executable, "-m", "scripts.econ.au.aofm.aofm_issuance_buybacks"],
]
```

### `au_full.py` (NEW — proposed manual-run orchestrator)

A single-command "run everything for AU" entry point. NOT scheduler-wired. Useful for:
- First-time setup after a fresh deploy / new machine
- Catch-up after cron downtime
- Manual ad-hoc full refresh ("rerun all AU right now")
- Debug + smoke verification

```python
"""Australia econ — FULL runner. Manual invocation only.

Runs every AU orchestrator back-to-back: daily, then monthly. Skips
weekly (no AU weekly fetchers). Use for backfills, post-downtime
catch-up, or ad-hoc full refresh. NOT registered in any cron.

Usage:
    python -m scripts.econ.au.au_full
    python -m scripts.econ.au.au_full --no-email
"""
PIPELINES: list[list[str]] = [
    [sys.executable, "-m", "scripts.econ.au.au_daily"],
    [sys.executable, "-m", "scripts.econ.au.au_monthly"],
]
```

It just subprocesses `au_daily.py` + `au_monthly.py` in sequence. Each child orchestrator runs its own pipelines, writes its own email summary. `au_full` itself sends one consolidated "AU full refresh done" email at the end (or `--no-email` skips both children + the consolidated).

## Scheduler implications

| Cron entry | What runs |
|---|---|
| `scripts/imdr_daily.py:PIPELINES` | `scripts.econ.au.au_daily` (filings + 4 daily Track A) |
| `scripts/imdr_weekly.py:PIPELINES` | nothing AU |
| `scripts/imdr_monthly.py:PIPELINES` | `scripts.econ.au.au_monthly` (~25 fetchers) |
| `scripts/imdr_quarterly.py:PIPELINES` | nothing AU (quarterly folds into monthly) |
| **Manual only** | `scripts.econ.au.au_full` (one-shot full refresh) |

## Implications for the "what's left" tracker

Update [`au_prod_ready_todo.md`](../../development/au_prod_ready_todo.md):

- ✅ `au_daily.py` BUILT (filings-only) — needs **extension** to add the 4 daily Track A fetchers after Phase G promotion lands them under `scripts/econ/au/{cotality,rba}/`
- ❌ `au_monthly.py` NOT BUILT — to be created in Phase G
- ❌ `au_weekly.py` NOT NEEDED — explicitly omit, document the reasoning
- ❌ `au_full.py` NOT BUILT — manual-run aggregator over daily + monthly. Build alongside `au_monthly.py` since it depends on the monthly orchestrator existing.

## Caveats / open questions

1. **RBA CSV snapshots are NOT automatic** — `fetch_rates.py` / `fetch_fx.py` / etc. consume CSVs in `playground/econ/rba/discovery/samples/` that were manually downloaded via `fetch_d2_e_tables.py` (Playwright). For daily prod cadence, the snapshot-refresh job needs to run first. Two options:
   - **(a)** Wire the Playwright snapshot-refresh into the same `au_daily.py` pipeline step (before the loader fetchers fire)
   - **(b)** Live HTTP-pull from rba.gov.au using the per-fetcher Akamai bypass (rebuild the fetchers to do HTTP not CSV-read)
   - Decision deferred; current `au_daily.py` only has filings, so this isn't blocking today

2. **AOFM monthly manual-Edge dependency** — the 5 AOFM fetchers will fail unless someone has refreshed the XLSXs first. Need a monthly checklist / runbook reminder. Maybe the orchestrator should `--check-xlsx-fresh` and email "AOFM XLSX > 35 days old" rather than silently load stale data.

3. **Cotality daily snapshot accumulates** — `fetch_hvi.py` captures today's value each run; missing a day = missing data point. Cron reliability matters here more than for the discovery-based fetchers.

## Related

- [`australia_govt_prod_pipeline.md`](australia_govt_prod_pipeline.md) — Phase J prod doc (filings side, already built)
- [`../econ_to_prod.md`](../econ_to_prod.md) §G.3 — "one orchestrator, many cadences" rule
- [`../korea/korea_prod_pipeline.md`](../korea/korea_prod_pipeline.md) — Korea reference (has kr_daily + kr_weekly + kr_monthly)
- [`../../development/au_prod_ready_todo.md`](../../development/au_prod_ready_todo.md) — Phase G build list
