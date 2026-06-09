# Australia (AU) — Econ Indicator Inventory

Last updated: 2026-06-10

Tracker forked from [`../country_econ_blueprint.md`](../country_econ_blueprint.md) §1-4 per the [onboarding playbook](../onboarding_new_country.md#step-1--fork-the-blueprint-into-a-country-tracker).

**Status (2026-06-10):** DB-LIVE — **379 indicators / 339,631 obs** (verified against `econ.fact_indicator`). ABS **15 fetchers across 18 dataflows (141 indicators)** + RBA 5 fetchers via CSV snapshot (78 indicators) + AOFM 5 fetchers (157 indicators) + FRED-mirror (3 indicators). 14 of 16 wiring-map cells ✅. Second-most-populated country after Indonesia. Phase G blocker lifted (AOFM in DB). Production promotion can proceed with user sign-off.

## Status markers

| Marker | Meaning |
|---|---|
| ✅ | At least one indicator on disk + production fetcher registered |
| ⚠ | Partial — headline present, sub-bullets missing |
| ❓ | Unknown source — needs catalogue browse |
| ❌ | Not available (vendor-gated, expected gap) |

## 4×4 Tracker

| Cell | Status | Headline indicator (vendor) | Sub-bullets covered | Notes |
|---|:---:|---|:---:|---|
| 1.1 Private Demand    | ✅ | ABS Retail Trade — monthly retail sales                  | 10/8  | 10 indicators loaded via `fetch_retail.py`. |
| 1.2 Fiscal Demand     | ✅ | AOFM issuance/buybacks + portfolio aggregate             | 26/6  | 16 portfolio aggregate (TB+TIB+TN outstanding monthly) + 10 issuance/buyback flow. |
| 1.3 External Demand   | ✅ | ABS BOP 14 + BOP_GOODS 7 + ITPI 6 + ANA_EXP 10          | 37/10 | Full goods/services trade + expenditure decomp loaded. |
| 1.4 Macro Core        | ✅ | ABS ANA_AGG (GDP chain-vol SA) + LF + ANA_EXP + Job Vacancies | 26/15 | GDP 7 + Labour 6 + Expenditure 10 + Job Vacancies 3. |
| 2.1 Input Costs       | ✅ | ABS ITPI import-side SITC 1-digit (18 indicators — food / beverages-tobacco / crude materials / energy / fats-oils / chemicals / mfg-by-material / machinery-transport / misc-manufactures × Index + YoY) | 18/5 | Extended `fetch_trade_prices.py`; INDEX codes 6013001–6013009 from ITPI_IMP. Import crude materials YoY Q1-2026: +4.5%; energy YoY: +0.7%. |
| 2.2 Producer Prices   | ✅ | ABS PPI_FD — final demand (TSEST=TOTXE, not TOTIE)       | 3/7   | 3 indicators loaded. PPI by industry (PPI_IND) deferred. |
| 2.3 Domestic Costs    | ✅ | ABS WPI — OHRPEB/TOT (NSA only; SA not published)        | 6/10  | 6 indicators. SA unavailable from ABS. |
| 2.4 CPI Pressure      | ✅ | ABS CPI — headline (INDEX=10001, Q NSA) + Trimmed Mean + Weighted Median M | 16/13 | 16 indicators including subcategory breakdown. |
| 3.1 Terms of Trade    | ❌ | AU.TOT.NET_BARTER (ABS ANA derived)                      | 0/4   | Derivable from ITPI export/import price ratio; not yet computed. |
| 3.2 Current Account   | ✅ | ABS BOP — CA + primary income + secondary income + capital | 14/10 | Full BOP flow loaded via `fetch_bop.py`. |
| 3.3 Capital Account   | ✅ | ABS BOP financial account + AOFM non-resident AGS holdings | 47/16 | BOP financial account 13 series + ITPI 6 + AOFM foreign holdings 34 series (quarterly since 2003; Mar-2026: AUD 469bn = 50.9% of outstanding). IIP (`BOP_FACTOR`) deferred. |
| 3.4 FX / REER         | ✅ | RBA F11.1 — AUD/USD + TWI + 17 AUD crosses               | 19/9  | 19 indicators. REER (BIS WS_EER) deferred. |
| 4.1 Demand Trans      | ✅ | RBA D2 — 14 credit aggregates (owner-occupier housing / investor housing / business / personal / total credit / narrow credit × NSA + SA) | 14/12 | Owner-occupier housing credit Apr-2026: AUD 1,747bn; investor housing credit Apr-2026: AUD 863bn. No RBA SLOOS-equivalent; D2 loan-growth as proxy. |
| 4.2 Balance Sheets    | ✅ | RBA E1+E2 — 16 series (household total assets/liabilities/net worth + business loans/total liabilities + 8 E2 ratios) | 16/15 | Household net worth Q4-2025: AUD 17,783bn; dwellings Q4-2025: AUD 11,821bn; debt-to-income 177.0%; housing-debt-to-income 133.7%; owner-occupier housing DTI 99.6%. |
| 4.3 Fin Conditions    | ✅ | RBA F1+F2 rates + AOFM term premium + AOFM turnover      | 108/15 | 11 RBA rates + 30 AOFM term premium (FY/TP/RNY × 1Y..10Y, daily since 1992; 10Y Mar-2026: 95bp) + 67 AOFM turnover by region/tenor. |
| 4.4 Policy Reaction   | ✅ | RBA D3 — M1/M3/Broad money/Money base NSA+SA + RBA A2 — cash-rate event log (4 series) | 18/16 | D3: 14 indicators. A2: Cash Rate Target + administered rates event log, 4 series. Cash Rate Target May-2026: 4.35%. |

**Score (2026-06-10):** **14 of 16 cells ✅, 1 ❌ Input-Costs-by-product-detail nuance (2.1 SITC 1-digit loaded, blueprint sub-bullets exceeded), 1 ❌-carried (3.1 ToT — derivable from ITPI export/import ratio, analytics-only, no fetcher needed).** 379 indicators / 339,631 obs in DB. AOFM fills 1.2 (Fiscal Demand), 3.3 (Capital Account — bond-holders-by-investor), and supplements 4.3 (term premium + turnover). RBA D2+E1+E2+A2 close 4.1, 4.2, and supplements 4.4.

## Playground fetcher inventory

All 25 playground fetchers as of 2026-06-10. All loaded into DB.

| Fetcher | Vendor | Dataflow / Table | Cell | Indicators |
|---|---|---|:---:|:---:|
| `fetch_cpi.py` | ABS | `CPI` | 2.4 | 16 |
| `fetch_gdp.py` | ABS | `ANA_AGG` | 1.4 | 7 |
| `fetch_labour.py` | ABS | `LF` | 1.4 | 6 |
| `fetch_lf_under.py` | ABS | `LF_UNDER` (M21/M23/M24 — underutilisation) | 1.4 | 3 |
| `fetch_wpi.py` | ABS | `WPI` | 2.3 | 6 |
| `fetch_ppi_fd.py` | ABS | `PPI_FD` | 2.2 | 3 |
| `fetch_retail.py` | ABS | `RT` (Retail Trade) | 1.1 | 10 |
| `fetch_capex.py` | ABS | `CAPEX` (private new capital expenditure) | 1.4 | 4 |
| `fetch_lending.py` | ABS | `LEND_HOUSING` + `LEND_BUSINESS` + `LEND_PERSONAL` | 4.1 | 11 |
| `fetch_rppi.py` | ABS | `RPPI` (residential property price index, national + 8 cities) | 4.2 / 1.1 | 17 |
| `fetch_bop.py` | ABS | `BOP` | 3.2 | 14 |
| `fetch_bop_goods.py` | ABS | `BOP_GOODS` | 3.3 | 7 |
| `fetch_trade_prices.py` | ABS | `ITPI_IMP` + `ITPI_EXP` (export 3 + import headline 3 + 18 SITC 1-digit) | 2.1 / 3.3 | 24 |
| `fetch_gdp_expenditure.py` | ABS | `ANA_EXP` | 1.3 / 1.4 | 10 |
| `fetch_job_vacancies.py` | ABS | `JV` | 1.4 | 3 |
| `fetch_rates.py` | RBA | F1 + F2 | 4.3 | 11 |
| `fetch_fx.py` | RBA | F11.1 | 3.4 | 19 |
| `fetch_monetary.py` | RBA | D3 | 4.4 | 14 |
| `fetch_d2_e_tables.py` | RBA | D2 + E1 + E2 + A2 (Playwright, CSV snapshots) | 4.1 / 4.2 / 4.4 | — (discovery; `fetch_credit_balsheet.py` loads) |
| `fetch_credit_balsheet.py` | RBA | D2 (14 credit aggregates) + E1+E2 (16 balance-sheet/ratio series) + A2 (4 cash-rate event-log series) | 4.1 / 4.2 / 4.4 | 34 |
| `fetch_foreign_holdings.py` | AOFM | Foreign holdings XLSX | 3.3 | 34 |
| `fetch_portfolio_aggregate.py` | AOFM | Portfolio aggregate XLSX | 1.2 | 16 |
| `fetch_term_premium.py` | AOFM | Term premium XLSX | 4.3 | 30 |
| `fetch_turnover.py` | AOFM | Turnover XLSX | 4.3 | 67 |
| `fetch_issuance_buybacks.py` | AOFM | Issuance/buybacks XLSX | 1.2 | 10 |

**Total: 379 indicators (ABS 141 + RBA 78 + AOFM 157 + FRED-mirror 3) / 339,631 obs.** ABS sub-totals reconcile: CPI 16 + GDP 7 + Labour 6 + LF_UNDER 3 + WPI 6 + PPI_FD 3 + Retail 10 + CAPEX 4 + Lending 11 + RPPI 17 + BOP 14 + BOP_GOODS 7 + Trade Prices 24 + GDP_EXP 10 + JV 3 = 141.

## Phase G — BLOCKER LIFTED

AOFM data is in DB (157 indicators / 268,195 obs). The Phase G condition ("do not promote AU to
prod until AOFM resolved") is satisfied. Production promotion can proceed with explicit user sign-off.

Manual monthly refresh via Edge is the stable path (see [`_playground/aofm.md`](_playground/aofm.md)).
Playwright/Chrome automation of AOFM remains blocked by corp TLS-inspection; Chrome uses BoringSSL
which is reset by the corp firewall on `*.gov.au/sites/default/files/*.xlsx`. Edge (Schannel) works.

## Next moves (in priority order)

1. **[READY]** Sign off on production promotion — register AU into `scripts/imdr_{daily,monthly}.py:PIPELINES` (explicit user OK required per `feedback_no_prod_wiring_without_permission.md`). AOFM will be a manual monthly step (Edge download + re-run fetchers) until automation is possible.
2. Stabilise RBA live-refresh via Playwright (current load is CSV snapshot for all 5 RBA fetchers; see [`_playground/rba.md`](_playground/rba.md)).
3. Load proper `IIP` dataflow — probed 2026-06-10 via `playground/econ/abs/discovery/probe_iip.py`. Confirmed 8 dimensions (`MEASURE.DATA_ITEM.SECTOR.MATURITY.INDUSTRY.CURRENCY.TSEST.FREQ`), 129 DATA_ITEM codes, 22 sectors, live data through Q1-2026. Next step: pick headline keys (Net IIP / Foreign Assets / Foreign Liabilities by sector, MEASURE=6 end-of-period stock) + write `fetch_iip.py`. Fills cell 3.3 stock-side.
4. Derive ToT (3.1) from ITPI export/import price ratio (analytics-side, no new fetcher).

## Build order (historical reference)

Completed in this order:
1. CPI (2.4) — ABS CPI. [✓ loaded]
2. GDP (1.4) — ABS ANA_AGG. [✓ loaded]
3. Labour (1.4) — ABS LF. [✓ loaded]
4. WPI (2.3) — ABS WPI. [✓ loaded]
5. PPI_FD (2.2) — ABS PPI_FD. [✓ loaded]
6. Retail Trade (1.1) — ABS. [✓ loaded]
7. BOP (3.2) — ABS BOP. [✓ loaded]
8. BOP_GOODS (3.3) — ABS BOP_GOODS. [✓ loaded]
9. Trade prices (3.3) — ABS ITPI. [✓ loaded]
10. GDP expenditure (1.3/1.4) — ABS ANA_EXP. [✓ loaded]
11. Job Vacancies (1.4) — ABS. [✓ loaded]
12. Rates F1+F2 (4.3) — RBA CSV snapshot. [✓ loaded]
13. FX F11.1 (3.4) — RBA CSV snapshot. [✓ loaded]
14. Monetary D3 (4.4) — RBA CSV snapshot. [✓ loaded]
15. AOFM foreign holdings (3.3) — manual Edge download. [✓ loaded]
16. AOFM portfolio aggregate (1.2) — manual Edge download. [✓ loaded]
17. AOFM term premium (4.3) — manual Edge download. [✓ loaded]
18. AOFM turnover (4.3) — manual Edge download. [✓ loaded]
19. AOFM issuance/buybacks (1.2) — manual Edge download. [✓ loaded]
20. Trade prices extended (2.1) — ABS ITPI import-side SITC 1-digit, 18 indicators added to `fetch_trade_prices.py`. [✓ loaded]
21. RBA D2 credit aggregates (4.1) — `fetch_credit_balsheet.py`, 14 indicators. [✓ loaded]
22. RBA E1+E2 balance-sheet ratios (4.2) + A2 cash-rate event log (4.4) — `fetch_credit_balsheet.py`, 16 + 4 indicators. [✓ loaded]

## Expected ❌ cells

| Cell | Common gap | Workaround |
|---|---|---|
| 3.1 ToT | Derivable from ITPI export/import price ratio; no standalone fetcher needed | Analytics-side derivation; no new fetcher required |
| 1.1 Private Demand — sentiment | ABS does not publish CCI/BSI | Westpac-MI CCI + NAB BSI (paid) or skip |
| 4.2 Balance Sheets — corporate ratios | RBA E-tables cover households; corporates sparse | BIS credit-to-GDP gap as cross-country fallback |

## Vendor / dataflow inventory (ABS SDMX)

All 18 dataflows verified and loaded as of 2026-06-10 (CPI, ANA_AGG, ANA_EXP, BOP, BOP_GOODS, CAPEX, ITPI_IMP, ITPI_EXP, JV, LEND_BUSINESS, LEND_HOUSING, LEND_PERSONAL, LF, LF_UNDER, PPI_FD, RPPI, RT, WPI). Full enumeration of all 1,223 ABS dataflows in `playground/econ/abs/discovery/dataflows_full.json`. IIP probed (`probe_iip.py`); load pending.

| Dataflow | Topic | National headline key | Loaded |
|---|---|---|:---:|
| `CPI` | Consumer Price Index | `1.10001.10.50.Q` (Q NSA national) | ✅ |
| `ANA_AGG` | National Accounts Key Aggregates | `M1.GPM.20.AUS.Q` (chain-vol GDP SA) | ✅ |
| `LF` | Labour Force | `M13.3.1599.20.AUS.M` (unemployment rate, SA) | ✅ |
| `WPI` | Wage Price Index | `1.OHRPEB.7.TOT.10.AUS.Q` (NSA; SA not published) | ✅ |
| `PPI_FD` | Producer Prices Final Demand | TSEST=TOTXE (not TOTIE) | ✅ |
| Retail Trade | Monthly retail sales | national monthly | ✅ |
| `BOP` | Balance of Payments | current + primary + secondary + capital + financial | ✅ |
| `BOP_GOODS` | BoP Goods | chain-volume TSEST=10 | ✅ |
| `ITPI` | International Trade Price Indexes | Import IDX=6011001 / Export IDX=8093697 | ✅ |
| `ANA_EXP` | GDP Expenditure Decomposition | expenditure components | ✅ |
| Job Vacancies | Job Vacancies survey | quarterly national | ✅ |
| `BOP_FACTOR` | BoP + IIP combined SA | (net international position) | ❌ deferred |

## Vendor / table inventory (RBA stats tables)

See [`_playground/rba.md`](_playground/rba.md) + `playground/econ/rba/discovery/webfetch_inventory.md`.

| Table | Topic | Cadence | Loaded |
|---|---|:---:|:---:|
| **F1 + F2** | Cash rate, BBSW, OIS, govt bond yields | Daily | ✅ 11 indicators (CSV snapshot) |
| **F11.1** | Exchange rates incl. AUD/USD + TWI + 17 crosses | Daily | ✅ 19 indicators (CSV snapshot) |
| **D3** | Monetary aggregates M1/M3/Broad/Base NSA+SA | Monthly | ✅ 14 indicators (CSV snapshot) |
| **F15** | Real exchange rate measures | Monthly | ❌ deferred |
| **F17** | Zero-coupon analytical series | Daily | ❌ deferred |
| **D2** | Bank credit aggregates (owner-occupier / investor housing / business / personal / total / narrow × NSA+SA) | Monthly | ✅ 14 indicators (`fetch_credit_balsheet.py`) |
| **E1 + E2** | Household balance sheet (total assets/liabilities/net worth + business) + gearing ratios (debt-to-income, housing-DTI, etc.) | Quarterly | ✅ 16 indicators (`fetch_credit_balsheet.py`) |
| **G1**/G4 | CPI — RBA reformats ABS | Q/M | ❌ redundant (ABS direct loaded) |
| **H1**/H3/H5 | GDP / activity / labour — RBA reformats ABS | Q/M | ❌ redundant (ABS direct loaded) |
| **A2** | Monetary policy + administered rate changes (Cash Rate Target + bank rates event log) | Event | ✅ 4 indicators (`fetch_credit_balsheet.py`). Cash Rate Target May-2026: 4.35%. |

## Cross-cell identity checks

To run once headline + components land:

| Identity | Notes |
|---|---|
| `CA ≈ FA − E&O` | ABS publishes both in BOP; cross-cell consistency check |
| `Employed + Unemployed = Labour Force` | ABS LF: M3 + M6 = M9 |
| `Goods exports − Goods imports = Goods balance` | ABS BOP_GOODS |
| `Nominal GDP = Real GDP × Deflator / 100` | ABS ANA_AGG MEASURE=M1 vs M5 (price deflator) |
| `Real GDP YoY ≈ weighted sum of expenditure contributions` | ANA_EXP demand-side decomposition |

## Quality bar

| Bar | Threshold |
|---|---|
| **History depth** | ABS CPI from 1948 Q3 (77+ yrs); ABS LF from 1978; RBA F2 from 1969 — all comfortably ≥ 10 yrs. |
| **Update lag** | ABS CPI Q: ~30 days post quarter-end; M: ~25 days. ABS LF: ~15 days. RBA F-tables: T+1 daily. |
| **Cadence** | Q for headline CPI; M for LF + sub-CPI; D for RBA F1/F2/F11.1. |
| **Identity-check pass** | Pending first parquet sample. |
| **Vendor stability** | ABS SDMX v2.1 (NSI Web Service v8.19.9.0). RBA Akamai-fronted, profile-gated. |

## Remaining gaps / pending items

- **3.1 ToT**: derivable from ITPI export/import price ratio — not yet computed as a standalone indicator. Analytics-only; no new fetcher needed.
- **3.3 IIP**: `BOP_FACTOR` (net international position) deferred.
- **RBA live-refresh**: all 5 loaded RBA fetchers use static CSV snapshots from `discovery/samples/`; see [`_playground/rba.md`](_playground/rba.md) for the Playwright path.
- **Broken legacy file**: `playground/econ/rba/fetch.py` — assumes bogus HTTPClient fetch path; flag for deletion.

## Cross-refs

- [`index.md`](index.md) — country landing
- [`_playground/abs.md`](_playground/abs.md) — ABS playground notes
- [`_playground/rba.md`](_playground/rba.md) — RBA playground notes
- [`../country_econ_blueprint.md`](../country_econ_blueprint.md) — indicator catalogue
- [`../macro_economy_wiring_map.md#77-australia-au`](../macro_economy_wiring_map.md#77-australia-au) — wiring map §7.7
