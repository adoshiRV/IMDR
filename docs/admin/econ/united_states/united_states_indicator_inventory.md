# United States (US) — indicator inventory

Last updated: 2026-06-23 (completeness build-out: 193 active / ~199k obs; 3.4 ✅; real PCE added; FRED-US scheduled)

Canonical "what we have" tracker for US, forked from
[country_econ_blueprint.md §1-4](../country_econ_blueprint.md) and reconciled against
[macro_economy_wiring_map.md §7.1](../macro_economy_wiring_map.md#71-united-states-us).

**Status (2026-06-23): Track A PROD-LIVE + completeness build-out complete.** 18 prod fetchers at `scripts/econ/us/` (original 15 + FRED-US daily + FRED-US monthly + BIS), 2 orchestrators wired into `imdr_monthly.py:PIPELINES` + `imdr_daily.py:PIPELINES` 2026-06-23. **193 active indicators / ~198,775 obs** (FRED-US 106+ · BEA 36 · BLS 29 · Census 10 · EIA 3 · Treasury 4 · BIS 2 + Philly+Dallas adds). Score: **15 ✅ / 1 ⚠ / 0 ❌** (3.4 FX/REER closed; 4.1 Demand Trans is cosmetic ⚠). See [`united_states_prod_pipeline.md`](united_states_prod_pipeline.md) §"Scheduler wiring" for the registered PIPELINES entries.

Markers: ✅ on disk + prod fetcher registered in scheduler · ⚠ partial (headline only) · ❓ source
unknown · ❌ not available (gated gap). Cell markers below: cells backed by a registered
prod fetcher now qualify as ✅ — the scheduler wiring gate (the last remaining condition)
was lifted on 2026-06-23.

## 4×4 coverage tracker

| Cell | Status | Headline indicator (vendor) | Notes |
|---|:---:|---|---|
| 1.1 Private Demand   | ✅ | Census MARTS retail · BEA Personal Income/PCE price · **real PCE quantity DPCERX chained 2017 $mn (added 2026-06-23)** | consumption quantity leg now closed |
| 1.2 Fiscal Demand    | ✅ | Treasury MTS receipts/outlays/deficit · Debt-to-Penny daily | |
| 1.3 External Demand  | ✅ | Census FT-900 goods+services · BEA ITA net exports | |
| 1.4 Macro Core       | ✅ | BEA NIPA GDP adv/2nd/3rd · BLS payrolls/unemp/LFPR · FRED GDPNow/INDPRO/CFNAI | PMI (ISM) paid — stays a gap |
| 2.1 Input Costs      | ✅ | BLS import/export price indexes · EIA WTI/Brent/Henry Hub daily | |
| 2.2 Producer Prices  | ✅ | BLS PPI final demand + stage-of-processing | |
| 2.3 Domestic Costs   | ✅ | BLS ECI total comp · JOLTS quits/openings · productivity · AHE | |
| 2.4 CPI Pressure     | ✅ | BLS CPI-U headline+core+components · BEA PCE price | |
| 3.1 Terms of Trade   | ✅ | BLS export/import price ratio (closes former ❌) | |
| 3.2 Current Account  | ✅ | BEA ITA BalCurrAcct + Gds/Serv/PrimInc/SecInc (quarterly) | |
| 3.3 Capital Account  | ✅ | BEA ITA financial account DI/PI/Other/Reserves · BEA IIP net stock | TIC stock = deferred scrape |
| 3.4 FX / REER        | ✅ | FRED DTWEXBGS/AFE/EME · **BIS NEER+REER broad via `scripts/econ/us/bis/bis_us.py` (added 2026-06-23)** | latest REER 107.26 / NEER 101.69 |
| 4.1 Demand Trans     | ⚠ | FRED SLOOS · mortgage rates · BUSLOANS | FRED is source-clean; no upstream upgrade exists — cosmetic ⚠ |
| 4.2 Balance Sheets   | ✅ | FRED Z.1 TDSP/CMDEBT · Treasury Debt-to-Penny daily | |
| 4.3 Fin Conditions   | ✅ | UST curve + IG/HY/BAA OAS + NFCI + VIX (FRED) | |
| 4.4 Policy Reaction  | ✅ | Fed funds, EFFR, SOFR, IORB, Fed BS, RRP (FRED) · SEP dot-plot via Track B | |

Wiring-map score: **15 ✅ / 1 ⚠ / 0 ❌** (completeness build-out 2026-06-23). Remaining ⚠: 4.1 Demand Trans (FRED is source-clean; cosmetic).

## Current FRED coverage by category (DB-verified 2026-06-22)

| Category | n_ind | Category | n_ind |
|---|---:|---|---:|
| rates | 25 | balance_sheet | 11 |
| sentiment | 16 | housing | 5 |
| cpi | 15 | cb_balance_sheet | 4 |
| credit | 15 | energy | 4 |
| labour | 14 | fx | 3 |
| gdp | 13 | cb_facility | 3 |
| | | bop | 2 |
| | | liquidity | 2 |

Total: **132 US-specific** FRED indicators (vendor `fred`, country US). FRED also
mirrors 41 indicators for EU/UK/JP/DE/CA/CH/NZ/KR/IN/AU (cross-country comparison).

## Playground fetcher inventory

| Fetcher | Vendor | Cells | Status |
|---|---|---|---|
| `playground/econ/fred/{fetch,connector,seed.yml}` | FRED | all baseline | LIVE (playground), loader-ready, **unpromoted** |
| `playground/econ/us/_validate_keys.py` | — | — | key-probe (BLS/BEA/Census/Treasury/EIA all PASS 2026-06-22) |
| `bls/{connector,fetch_cpi,fetch_ppi,fetch_employment_situation,fetch_eci_jolts,fetch_import_export_prices}.py` | BLS | 1.4 · 2.1 · 2.2 · 2.3 · 2.4 · 3.1 | ✅ built (playground), dry-run clean |
| `bea/{connector,fetch_gdp,fetch_personal_income,fetch_ita,fetch_iip}.py` | BEA | 1.1 · 1.3 · 1.4 · 2.4 · 3.2 · 3.3 | ✅ built, dry-run clean, BoP identity=0 |
| `census/{connector,fetch_retail,fetch_trade,fetch_housing}.py` | Census | 1.1 · 1.3 | ✅ built, dry-run clean |
| `treasury/{connector,fetch_mts,fetch_debt}.py` | Treasury | 1.2 · 4.2 | ✅ built, fiscal identity=0; TIC deferred |
| `eia/{connector,fetch_energy}.py` | EIA | 2.1 | ✅ built; `eia` already in dim_vendor (loads clean) |
| `govt/{probe_fomc_statements,probe_fomc_minutes,probe_fomc_sep,probe_fed_speeches,daily_pull}.py` | Fed (Track B) | — | ✅ built; manifest-only snapshots; FOMC + speeches |

**Load status (2026-06-22): LOADED into `econ.fact_indicator`.** Migration 105
registered vendors `bls`/`bea`/`census`/`treasury_us` (`fred`+`eia` pre-existed); all
Track A parquet then loaded via `load_econ_indicator_from_playground`. New
source-agency total: **82 indicators / 30,563 obs** —

| Vendor | Indicators | Obs | History |
|---|---:|---:|---|
| BEA | 36 | 11,979 | 1947→ |
| EIA | 3 | 8,673 | 2015→ |
| BLS | 29 | 5,256 | 2010→ |
| Treasury (`treasury_us`) | 4 | 3,288 | 2015→ |
| Census | 10 | 1,367 | 2015→ |

Combined with the FRED baseline, **US = 214 indicators loaded**. After the
2026-06-23 source reconciliation (migration 106), 188 are active — 26 exact-dup
FRED mirrors deactivated (`is_active=0`, reversible) in favour of the authoritative
source agency, per the [source-of-truth policy](us_coverage_plan.md#source-of-truth-policy-fred-vs-source-agencies).
BLS price indices (PPI + import/export) recategorised `other → cpi`.
**After completeness build-out (2026-06-23): 193 active indicators / ~198,775 obs**
(FRED-US 106+ · BEA 36 · BLS 29 · Census 10 · EIA 3 · Treasury 4 · BIS 2 + Philly/Dallas adds).
**Promoted to `scripts/econ/us/` 2026-06-23 and wired into both orchestrators** —
scheduled refresh active; initial data was loaded via the user-supervised one-shot
loader path; ongoing refresh is now automated. FRED-US series now also on a
scheduled refresh (previously loaded once from playground; `seed_us.yml` is
is_active-safe — excludes the 26 deactivated source-dup series).

## Production fetchers (promoted 2026-06-23; completeness additions 2026-06-23)

18 fetchers at `scripts/econ/us/`, grouped by vendor. 2 orchestrators.
Wired into `imdr_monthly.py:PIPELINES` + `imdr_daily.py:PIPELINES` 2026-06-23 (PROD-LIVE).

### Orchestrators

| Module | Cadence | Fetchers included | Scheduler |
|---|---|---|---|
| `scripts.econ.us.us_monthly` | Monthly / Quarterly / Annual | BLS ×5 + BEA ×4 + Census ×3 + Treasury MTS + BIS ×1 + FRED-US monthly ×1 | **WIRED 2026-06-23** — in `imdr_monthly.py:PIPELINES` |
| `scripts.econ.us.us_daily` | Daily | EIA energy + Treasury Debt + FRED-US daily + Track B filings | **WIRED 2026-06-23** — in `imdr_daily.py:PIPELINES` |

### BLS (5 fetchers)

| Module | Topic | Cells |
|---|---|---|
| `scripts.econ.us.bls.bls_cpi` | CPI-U headline + core + components | 2.4 |
| `scripts.econ.us.bls.bls_ppi` | PPI final demand + stage-of-processing | 2.2 |
| `scripts.econ.us.bls.bls_employment_situation` | Payrolls, unemployment, LFPR, AHE | 1.4 · 2.3 |
| `scripts.econ.us.bls.bls_eci_jolts` | ECI total comp + JOLTS quits + job openings + productivity | 2.3 |
| `scripts.econ.us.bls.bls_import_export_prices` | Import + export price indexes | 2.1 · 3.1 |

### BEA (4 fetchers)

| Module | Topic | Cells |
|---|---|---|
| `scripts.econ.us.bea.bea_gdp` | Real GDP %chg + levels (adv/2nd/3rd vintages) | 1.4 |
| `scripts.econ.us.bea.bea_personal_income` | Personal income + PCE price (T20600/T20804) + **real PCE quantity T20806/DPCERX (added 2026-06-23)** | 1.1 · 2.4 |
| `scripts.econ.us.bea.bea_ita` | ITA current + financial account decomposition | 3.2 · 3.3 |
| `scripts.econ.us.bea.bea_iip` | Net IIP stock | 3.3 |

### Census (3 fetchers)

| Module | Topic | Cells |
|---|---|---|
| `scripts.econ.us.census.census_retail` | MARTS retail + food services | 1.1 |
| `scripts.econ.us.census.census_trade` | FT-900 goods + services trade balance | 1.3 |
| `scripts.econ.us.census.census_housing` | New Residential Construction — starts + permits | 1.1 |

### Treasury (2 fetchers)

| Module | Topic | Cells | Orchestrator |
|---|---|---|---|
| `scripts.econ.us.treasury.treasury_mts` | Monthly Treasury Statement — receipts/outlays/deficit | 1.2 | `us_monthly` |
| `scripts.econ.us.treasury.treasury_debt` | Debt to the Penny (daily) | 4.2 | `us_daily` |

### EIA (1 fetcher)

| Module | Topic | Cells | Orchestrator |
|---|---|---|---|
| `scripts.econ.us.eia.eia_energy` | WTI + Brent + Henry Hub spot (daily) | 2.1 | `us_daily` |

### BIS (1 fetcher) — added 2026-06-23

| Module | Topic | Cells | Orchestrator |
|---|---|---|---|
| `scripts.econ.us.bis.bis_us` | US NEER + REER broad (BIS WS_EER `M.N.B.US` + `M.R.B.US`) | 3.4 | `us_monthly` |

Closes cell 3.4 FX/REER — flips ⚠️ → ✅. No key required (public BIS SDMX-JSON API).

### FRED-US (2 fetchers) — added 2026-06-23

| Module | Topic | Series | Cadence | Orchestrator |
|---|---|---|---|---|
| `scripts.econ.us.fred.fred_us_daily` | DAILY + WEEKLY US FRED series | 56 | Daily / Weekly | `us_daily` |
| `scripts.econ.us.fred.fred_us_monthly` | MONTHLY + QUARTERLY + ANNUAL US FRED series | 52 | Monthly / Quarterly / Annual | `us_monthly` |

`seed_us.yml` generated from DB active-set — excludes 26 migration-106-deactivated source-dup series
(verified still inactive post-reload; `is_active`-safe). Adds Philly Fed + Dallas Fed.
Library: `src/imdr/domains/econ/fred_http.py` (`FredClient`). Unit test: `tests/unit/test_econ/test_fred_http.py`.

### Library connectors (6 modules)

| Module | Vendor |
|---|---|
| `src/imdr/domains/econ/bls_http.py` | BLS |
| `src/imdr/domains/econ/bea_http.py` | BEA |
| `src/imdr/domains/econ/census_http.py` | Census |
| `src/imdr/domains/econ/treasury_fiscaldata.py` | Treasury Fiscal Data |
| `src/imdr/domains/econ/eia_http.py` | EIA |
| `src/imdr/domains/econ/fred_http.py` | FRED (`FredClient`; key via `get_settings().econ_fred_key` + numbered-sibling rotation) — added 2026-06-23 |

For full invocation, failure modes, and archive layout, see
[`united_states_prod_pipeline.md`](united_states_prod_pipeline.md).

---

## §8 — Known gaps & quality notes

- **ISM PMI** (Mfg + Services) — subscription only; 1.4 PMI-leg stays a gap. Michigan
  (UMCSENT, free) is the sentiment proxy already in seed.
- **Conference Board CCI** — paid; use Michigan.
- **Treasury TIC** foreign holdings — CSV/XML scrape (not fiscaldata API); 3.3
  flow is covered by BEA ITA, TIC stock deferred.
- **FRED revisions are silent** — vintage support exists in `FredClient` but the
  current loader uses vintage-0; BEA/BLS first-vs-revised prints should use
  explicit vintages where the release publishes them (GDP adv/2nd/3rd).
- **BIS REER** — ~~pending~~ **added 2026-06-23** via `bis_us.py`; cell 3.4 closed.
- **Real PCE** — ~~deferred~~ **added 2026-06-23** (T20806/DPCERX in `bea_personal_income`); cell 1.1 consumption-quantity leg closed.
- **Regional Fed further surveys** — Philly Fed + Dallas Fed added in `seed_us.yml` 2026-06-23; Richmond/Kansas City/Chicago are optional further adds.

## Related

- [united_states_prod_pipeline.md](united_states_prod_pipeline.md) — Track A ops reference (architecture, CLI, failure modes, scheduler wiring live 2026-06-23)
- [us_coverage_plan.md](us_coverage_plan.md) — cell → exact source-ID mapping + build order + migrations
- [index.md](index.md) — landing page + Track B (FOMC) document sources
- [macro_economy_wiring_map.md §7.1](../macro_economy_wiring_map.md#71-united-states-us)
