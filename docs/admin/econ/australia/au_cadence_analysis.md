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

## Resolved caveats (checked 2026-06-11)

### Item 1 — RBA CSV snapshot refresh — RESOLVED, build added to Phase G

**Verified state:** RBA CSVs in `playground/econ/rba/discovery/samples/` are stale:

| File | Last mtime | Cadence | Days stale today (2026-06-11) |
|---|---|---|---|
| f1-data.csv (cash/BBSW/OIS) | Jun 2 | daily business-day | **9 days** ⚠ |
| f2-data.csv (AGB yields + TIB) | Jun 2 | daily business-day | **9 days** ⚠ |
| f11.1-data.csv (AUD FX + TWI) | Jun 2 | daily business-day | **9 days** ⚠ |
| d3-data.csv (monetary aggregates) | Jun 2 | monthly | 9 days (OK — monthly) |
| g1-data.csv | Jun 2 | quarterly | 9 days (OK — quarterly) |
| d2 / e1 / e2 / a2 / i1 / i2 / f15 / f16 / f17-* | Jun 10 | monthly/quarterly | 1 day |

`fetch_d2_e_tables.py` currently grabs 11 tables but **f1, f2, f11.1, d3, g1 are NOT in its TABLES list** — they were originally captured by an earlier ad-hoc one-off Playwright run that never got formalised.

**Resolution — Phase G additions:**

1. Extend `fetch_d2_e_tables.py` TABLES to include f1, f2, f11.1, d3, g1 (5 more entries — Playwright re-runs ~30 sec extra)
2. Promote to `scripts/econ/au/rba/rba_snapshot_refresh.py` during Phase G
3. Wire as FIRST PIPELINES entry in `au_daily.py` BEFORE the rate/FX/curve loaders:

   ```python
   PIPELINES = [
       # Refresh RBA daily-cadence CSVs first; loaders are downstream consumers
       [sys.executable, "-m", "scripts.econ.au.rba.rba_snapshot_refresh", "--daily-only"],
       # Then daily Track A loaders consume the fresh CSVs
       [sys.executable, "-m", "scripts.econ.au.rba.rba_rates"],
       [sys.executable, "-m", "scripts.econ.au.rba.rba_fx"],
       [sys.executable, "-m", "scripts.econ.au.rba.rba_zerocoupon"],
       [sys.executable, "-m", "scripts.econ.au.cotality.cotality_hvi"],
       # Filings ingest can run anytime
       [sys.executable, "-m", "scripts.econ.au.govt.ingest_filings", "--ingest"],
   ]
   ```

4. `au_monthly.py` calls `rba_snapshot_refresh` with `--monthly-only` (or no flag) to grab the slower tables.

This avoids re-architecting fetchers to live-HTTP — the CSV-snapshot pattern is reused as-is, just on a fresh snapshot each run.

### Item 2 — AOFM staleness — RESOLVED (user handles manual Edge refresh; orchestrator emails warning)

User confirmed they'll handle the manual Edge download themselves. Orchestrator surfaces staleness in the daily email.

**Verified state today:** AOFM XLSXs at `playground/econ/aofm/discovery/xlsx/` all have mtime 2026-06-10 (1 day stale — fine for monthly cadence).

**Implementation** in `au_monthly.py` `_render_email()`:

```python
def _aofm_staleness(threshold_days: int = 35) -> dict:
    xlsx_dir = _REPO_ROOT / "data" / "econ" / "au" / "aofm" / "xlsx"  # post Phase G
    newest_mtime = max(
        (p.stat().st_mtime for p in xlsx_dir.glob("*.xlsx")),
        default=0,
    )
    age_days = (time.time() - newest_mtime) / 86400 if newest_mtime else None
    stale = age_days is not None and age_days > threshold_days
    return {"age_days": age_days, "stale": stale, "threshold_days": threshold_days}
```

If `stale=True`, the email subject prefix gets `[AOFM STALE]` and a banner section reminds the user to refresh XLSXs via Edge. If `age_days is None` (no XLSXs found at all), surface as error.

### Item 3 — Cotality cron-reliability — RESOLVED, daily email surfacing required

**Verified state:** Only 6 obs in DB total (one per series, one date 2026-06-10). Already missing today's data.

```sql
SELECT i.imdr_code, COUNT(*), MIN(obs_date), MAX(obs_date)
FROM econ.fact_indicator f JOIN econ.dim_indicator i ON i.id=f.indicator_id
WHERE i.imdr_code LIKE 'COTALITY.HVI.%' GROUP BY i.imdr_code;
-- 6 rows, all n=1, all 2026-06-10
```

**Why this matters:** the Cotality `/au/our-data/indices` page only exposes TODAY's value — there is no published history at the free tier. Missed cron runs = permanent gaps in the time series.

**Resolution** — surface daily Cotality activity in the `au_daily.py` email:

```python
def _cotality_today_check(today: date) -> dict:
    """Sanity: did Cotality HVI get fresh obs for today?"""
    eng = _engine()
    with eng.connect() as conn:
        row = conn.execute(text(
            "SELECT COUNT(*) AS n FROM econ.fact_indicator f "
            "JOIN econ.dim_indicator i ON i.id = f.indicator_id "
            "WHERE i.imdr_code LIKE 'COTALITY.HVI.%' AND f.obs_date = :d"
        ), {"d": today}).first()
    eng.dispose()
    n_series = int(row.n) if row else 0
    return {"date": today.isoformat(), "n_series_with_today": n_series, "expected": 6}
```

If `n_series_with_today < 6`, the email banner reads `[Cotality gap]` and the run is flagged. User can re-run `au_daily.py` to catch up (since the page still shows today's value, idempotent MERGE recovers).

If the gap is yesterday (2026-06-11 run noticed 2026-06-10 had only 6 obs but no 2026-06-11 obs), Cotality cron skipped a day — alert.

## Concrete Phase G build items (added by this cadence analysis)

1. **`scripts/econ/au/rba/rba_snapshot_refresh.py`** — promotes `fetch_d2_e_tables.py` + adds f1/f2/f11.1/d3/g1 to TABLES. Accepts `--daily-only` (f1/f2/f11.1) and full-run modes.
2. **`au_monthly.py:_aofm_staleness_check()`** — surfaces XLSX age in monthly email; banner `[AOFM STALE]` when age > 35 days.
3. **`au_daily.py:_cotality_today_check()`** — surfaces today's obs count in daily email; banner `[Cotality gap]` when fewer than 6 series have today's date.

## Related

- [`australia_govt_prod_pipeline.md`](australia_govt_prod_pipeline.md) — Phase J prod doc (filings side, already built)
- [`../econ_to_prod.md`](../econ_to_prod.md) §G.3 — "one orchestrator, many cadences" rule
- [`../korea/korea_prod_pipeline.md`](../korea/korea_prod_pipeline.md) — Korea reference (has kr_daily + kr_weekly + kr_monthly)
- [`../../development/au_prod_ready_todo.md`](../../development/au_prod_ready_todo.md) — Phase G build list
