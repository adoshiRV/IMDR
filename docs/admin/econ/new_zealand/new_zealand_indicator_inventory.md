# New Zealand (NZ) — Econ Indicator Inventory

Last updated: 2026-06-19

Tracker forked from [`../country_econ_blueprint.md`](../country_econ_blueprint.md) §1-4 per the [onboarding playbook](../onboarding_new_country.md#step-1--fork-the-blueprint-into-a-country-tracker).

**Status (2026-06-19): Track A PROD-LIVE.** Promoted to `scripts/econ/nz/statsnz/` (13 fetchers) + `scripts/econ/nz/nz_monthly.py`; libraries at `src/imdr/domains/econ/statsnz_{common,infoshare}.py`. **Loaded: 1,063 indicators × 154,777 obs in `econ.fact_indicator`** (vendor_id=25, 1914→2026; zero migrations needed). Scheduler wiring (`scripts/imdr_monthly.py`) NOT yet done — gated. A 14th fetcher `statsnz_cpi_core.py` (42 CPI core series via Infoshare, cell 2.4) exists at `scripts/econ/nz/statsnz/` but is NOT yet added to `nz_monthly.py` — gated (see [`new_zealand_prod_pipeline.md`](new_zealand_prod_pipeline.md)). The playground fetchers below remain the dev surface (note: prod OTI captures 87 indicators vs the 2 in the pre-`ncols`-fix playground smoke).

Original playground fetchers under `playground/econ/statsnz/`:

| Fetcher | Indicators | Obs | History | Cells |
|---|---|---|---|---|
| `fetch_cpi.py` | 17 | 2,710 | 1914→2026-Q1 | 2.4 |
| `statsnz_cpi_core.py` *(Infoshare)* | 42 | — | 1988-Q4→ | 2.4 |
| `fetch_gdp.py` | 14 | 2,174 | 1987→2025-Q4 | 1.4 |
| `fetch_hlfs.py` | 4 | 36 | ⚠ 2024→2026 only (shallow XLSX) | 1.4 |
| `fetch_bop.py` | 32 | 5,317 | CA 1971→, IIP 2000→ | 3.2 + 3.3 |
| `fetch_ppi.py` *(Infoshare)* | 41 | 7,954 | 1977-Q4→ | 2.2 |
| `fetch_cgpi.py` *(Infoshare)* | 7 | 1,022 | 1989→ | 2.2 |
| `fetch_oti.py` *(Infoshare)* | 2 | 614 | 1949→ | 3.1 |
| `fetch_hlpi.py` *(Infoshare)* | 182 | 13,104 | 2008→ | 2.4 |
| `fetch_lci.py` *(Infoshare)* | 1 | 134 | headline only (industry tbls slow) | 2.3 |
| `fetch_qes.py` *(Infoshare)* | 312 | 46,488 | 1989→ | 1.4 + 2.3 |
| `fetch_ect.py` *(Infoshare)* | 39 | 12,363 | monthly | 1.1 |
| `fetch_omt.py` *(Infoshare)* | 7 | 3,892 | monthly | 1.3 |
| `fetch_rts.py` *(Infoshare)* | 318 | 31,932 | quarterly | 1.1 |
| `fetch_hlf.py` *(Infoshare)* | 6 | 966 | 1986→ (full HLFS history) | 1.4 |
| `fetch_bld.py` *(Infoshare)* | — | — | ⚠ deferred (tables time out) | 1.1 |

**Total: ~1,000 indicators across 13 fetchers** spanning cells 1.1, 1.3, 1.4, 2.2, 2.3, 2.4, 3.1, 3.2, 3.3 (9 of 16). All smoke-verified (`--no-parquet`); **0 loaded to DB** (gated). Remaining frontier: RBNZ (rates/FX/credit — Akamai/Playwright), NZDMO + Treasury (fiscal), BIS NZ slices.

**Key build finding (2026-06-16):** only **CPI / GDP / BoP-IIP** publish a long-format release-page **CSV** (`Series_reference/Period/Data_value`) servable over plain `httpx` — that is the entire clean-CSV lane. **The release-CSV CPI carries only the standard class hierarchy + tradables/non-tradables — it has NO core / analytical measures (exclusion-based or statistical trimmed means).** Those live exclusively behind Infoshare; see `statsnz_cpi_core.py` (added 2026-06-19). BoP-IIP CSV carries only `Series_title_1` = Actual/SA/Trend, so series labels were decoded from the companion XLSX (Tables 1/2/4/18); both accounting identities verified exact (CA = goods+services+primary+secondary; Net IIP = assets−liabilities incl. reserve assets P5). Wiring map currently lists 0 ✅ / 4 ⚠ (all via FRED OECD mirror) / 12 ❌.

**Release-CSV lane is exhausted (verified 2026-06-16).** Everything else — **Overseas merchandise trade (1.3), Retail trade (1.1), Business Price Indexes / PPI+CGPI+FEPI (2.2/2.1), ECT + Building consents (1.1), Overseas Trade Indexes / ToT (3.1), LCI (2.3), QES (1.4)**, plus **full HLFS history (1.4)** — has **no release-page CSV** (probed bare `.csv` + `-infoshare-data.csv` + `-data.csv` + `-seasonally-adjusted.csv` + `-visualisation.csv` suffixes; all 404). The release XLSX for these are multi-table *presentation* workbooks with **no `Series ref` row at all** (OMT/PPI confirmed) — formatted for humans, no stable series codes, shallow history. **The only path to these is Infoshare** (`infoshare.stats.govt.nz`), which exports the clean long format *with* a `Description` column (`Series_Reference, Period, Data_Value, Status Code, Type, Group, Description` — see `discovery/samples/cpi_mar2026_infoshare.csv`). **Infoshare CRACKED 2026-06-16 (no `.sch` needed).** DevTools capture revealed the real mechanism: it's ASP.NET WebForms, not the Export Direct `.sch` path. Driver at `playground/econ/statsnz/_infoshare.py` (`InfoshareClient`) — Playwright navigates the browse tree (pxID is session-regenerated, never stable; bare GET bounces to `session_expired`), selects all options in each `*_lbVariableOptions` listbox, sets `dlOutputOptions=csv`, clicks `btnGo`, captures the **wide-pivot** CSV download (rows=periods `1977Q4`/`2026M04`, cols=categories, `..`=NA). No login/MFA. Full recipe + quirks in [[reference-statsnz-infoshare-recipe]]. **PPI live to parquet (1977→).**

**Infoshare dataset expansion plan** (tree paths mapped 2026-06-16; each = ~1 recon + 1 fetcher on the proven driver):

| Dataset | Cell | Tree location | Status |
|---|---|---|---|
| CPI core (exclusion + statistical) | 2.4 | Economic indicators › Consumers Price Index - CPI | ✅ live (42; `statsnz_cpi_core.py`, 2026-06-19; **NOT in `nz_monthly.py` — gated**) |
| PPI Outputs+Inputs | 2.2 | Economic indicators › Producers Price Index - PPI | ✅ live (10) |
| CGPI | 2.2 | Economic indicators › Capital Goods Price Index - CEP | ✅ live (7) |
| HLPI (living-costs) | 2.4 | Economic indicators › Household living-costs price Indexes - HPI | ✅ live (182) |
| OTI / Terms of Trade | 3.1 | Imports and exports › Overseas Trade Indexes - Prices - OTP | ✅ live (2; analytical totals 1949→. Commodity/partner breakdown tables available to add) |
| LCI (labour cost) | 2.3 | Work income and spending › Labour Cost Index - LCI | ⚠ headline live (1); industry/occupation cross-tab tables time out server-side (deferred) |
| QES (employment) | 1.4 / 2.3 | Work income and spending › Quarterly Employment Survey - QEM | ✅ live (312) |
| ECT (cards) | 1.1 | Economic indicators › Electronic Card Transactions - ECT | ✅ live (39; monthly) |
| OMT (merch trade) | 1.3 | Imports and exports › Overseas Trade Statistics - OTT | ✅ live (7; SA totals + balance, monthly — country×commodity detail intentionally skipped) |
| RTS (retail) | 1.1 | Industry sectors › Retail Trade (ANZSIC06) - RTT | ✅ live (318; quarterly) |
| HLFS full history | 1.4 | Work income and spending › Household Labour Force Survey - HLF | ✅ live (6; SA+trend employed 1986→, replaces shallow release XLSX) |
| Building consents | 1.1 | Industry sectors › Building Consents - BLD | ⚠ deferred — all monthly BLD tables time out generating server-side (cell 1.1 already covered by ECT+RTS) |

**Infoshare parser handles 2-dimensional tables** (two-row header → composite category, constant levels dropped) — validated on HLPI Groups (household×expenditure → 168 series) and QES (industry×sex×ord/ot → 153 series). Some large LCI cross-tab tables time out generating server-side (not a parser issue — same-size QES tables work); deferred.

## Status markers

| Marker | Meaning |
|---|---|
| ✅ | At least one indicator on disk + production fetcher registered |
| ⚠ | Partial — headline present, sub-bullets missing |
| ❓ | Unknown source — needs catalogue browse |
| ❌ | Not available (vendor-gated, expected gap) |

## 4×4 Tracker

All sources resolved via Step-2 vendor cascade — see §Vendor cascade below. No code written; status reflects **discovery state**, not load state. Every cell would flip to ⚠ on first headline fetch, then ✅ once sub-bullets are present.

| Cell | Status | Headline indicator (Tier-1 vendor) | Sub-bullets covered | Notes |
|---|:---:|---|:---:|---|
| 1.1 Private Demand    | ❓ | Stats NZ ECT (electronic-card txns M, 2002→) + RTS (retail trade Q, 1995→) + BLD (building consents M, 1965→) | 0/8  | Tier-1 = Stats NZ Infoshare via Playwright Export Direct. RBNZ C12 (credit card spending) + RBNZ H2 (housing) supplement. |
| 1.2 Fiscal Demand     | ❓ | NZDMO (nominal bonds + T-bills + IIB tender history) + NZ Treasury (Fiscal Time Series XLSX 1972→, FSGNZ monthly, BEFU/HYEFU XLSX) | 0/6  | Two-vendor split: NZDMO = debt-stock side (AOFM analogue), Treasury = revenue/expenditure side. |
| 1.3 External Demand   | ❓ | Stats NZ IIE/OEA (overseas merchandise trade, M, 1960→) + ITS (services Q, 2000→) | 0/10 | Goods is monthly (high-vol); services is quarterly. Customs basis = OEA; BoP basis = BOP. |
| 1.4 Macro Core        | ⚠ | Stats NZ SNE/SNC (GDP P+E+I, Q from 1987-Q2) + HLF (HLFS labour Q, 1986-Q1→) + QES (employment Q, 1989→) + M3 RBNZ (population) | 1/15 partial via FRED ⚠ | FRED `NAEXKP01NZQ189S` + `LRUNTTTTNZQ156N` already give ⚠ partial coverage. Stats NZ replaces with full history + sub-decomp. |
| 2.1 Input Costs       | ❓ | Stats NZ FEPI (farm expenses Q, 1993→) | 0/5 | Niche, unlikely in ADE first wave — Infoshare-only. Supplement: BIS commodity benchmarks if needed. |
| 2.2 Producer Prices   | ❓ | Stats NZ PPI input + output (Q, 1977-Q4→) + CGPI (capital-goods Q, 1989→) | 0/7 | Quarterly Business Price Indexes release bundles PPI + CGPI + FEPI. |
| 2.3 Domestic Costs    | ❓ | Stats NZ LCI (labour cost index Q, 1992→) + QES wages | 0/10 | LCI is fixed-quality wage inflation; QES is hours+earnings. |
| 2.4 CPI Pressure      | ⚠ | Stats NZ CPIQ (quarterly 1949→) + CPIM (monthly from 2027) + SPI (M food/petrol/rent 1980s→) + HLPI (Q 2008→) + **CPI core (42 series via Infoshare — `statsnz_cpi_core.py`)** | 1/13 partial via FRED ⚠ | Existing `playground/econ/statsnz/fetch.py` covers **latest quarter only**. Infoshare Export Direct needed for full history. **Release-CSV lane has NO core series** — the exclusion-based and statistical-trimmed-mean analytical series are Infoshare-only; `statsnz_cpi_core.py` (2026-06-19) covers 27 exclusion cores (index 1988-Q4→) + 15 statistical-trimmed-mean/weighted-percentile cores (QoQ %, quarterly). RBNZ M4 (Survey of Expectations Q) + RBNZ H1 (household inflation expectations Q) supplement. |
| 3.1 Terms of Trade    | ❓ | Stats NZ OTI (Q, 1957-Q2→ Fisher index) | 0/4 | RBNZ B10 (TWI weights + trade volumes annual) supplements. |
| 3.2 Current Account   | ❓ | Stats NZ BOPQ (Q, 1971-Q2→) | 0/10 | Goods + services + primary + secondary income. |
| 3.3 Capital Account   | ❓ | Stats NZ IIPQ (IIP stock Q, 1989-Q4→) + Stats NZ BOPQ FA + **RBNZ D30** (non-resident NZGB holdings M) + RBNZ D31 (Kauri bond holdings M) | 0/16 | NZDMO does NOT publish foreign holdings (unlike AOFM) — RBNZ owns it. |
| 3.4 FX / REER         | ❓ | RBNZ B1 (NZD/USD + NZD/AUD + TWI daily + monthly) + RBNZ E1 (FX reserves M) + RBNZ B26 (FX turnover M) + BIS WS_EER (NEER + REER M from 1994) | 0/9 | RBNZ B13 (historical TWI weights annual) + RBNZ S50 (SDDS reserves M) supplement. |
| 4.1 Demand Trans      | ❓ | RBNZ C5/C41 (sector lending M) + RBNZ B3/B21 (retail rates M) + RBNZ B20/B25/B6/B7 (mortgage rates M) + RBNZ C22/C30/C31/C32/C33/C35/C40 (mortgage lending breakdowns by LVR/borrower/payment/DTI M) + RBNZ C60 (Credit Conditions Survey Q) | 0/12 | Akamai-gated XLSX. C60 is the NZ SLOOS-equivalent (quarterly). |
| 4.2 Balance Sheets    | ❓ | RBNZ C13 (key household financials Q) + RBNZ C21 (household balance sheet Q) + RBNZ S10/S20/S21/S30-37/S40/S41 (banks balance sheet + NPLs M/Q) + BIS WS_DSR (Q.NZ.P + Q.NZ.H + Q.NZ.N) + BIS WS_CREDIT_GAP + BIS WS_TC | 0/15 | RBNZ T-series (non-bank/finance-co) supplements. |
| 4.3 Fin Conditions    | ❓ | RBNZ B2 (wholesale rates daily-close — OCR / 90-day / swaps / govt bonds 1-10Y) + RBNZ B4 (extended wholesale rates M) + RBNZ D35 (govt bond turnover M) + NZDMO tender yields | 0/15 | **No NZ zero-coupon term-premium series exists** (unlike AOFM). Use B2 + swap spreads as proxy. |
| 4.4 Policy Reaction   | ⚠ | RBNZ OCR event log + RBNZ C50 (M1/M3 monetary aggregates M) + RBNZ D3 (settlement cash daily) + RBNZ D9 (standing facilities daily) + RBNZ D10 (OMOs daily) + BIS WS_CBPOL `D.NZ` (1999→) | 1/16 partial via FRED ⚠ | RBNZ macroprudential tools (LVR, DTI) live in narrative form — event log under `frequency_id=EVENT`. |

**Score (discovery):** **0 ✅ / 4 ⚠ / 12 ❓ / 0 ❌.** Every cell has a resolved Tier-1 source — no genuine gaps. Expected end-state after Phase 2 (headline-first) + Phase 3 (sub-bullet completion) + Phase 4 (DMO + Treasury fiscal): **16/16 ✅**, comparable to AU. No cell is structurally vendor-gated; the only "❌" categories from the playbook (PMI, REER, lending-stance survey, corporate IG/HY spreads) are all served by NZ — PMI replaceable by BNZ-BusinessNZ PMI (paid; defer), REER via BIS WS_EER, lending stance via RBNZ C60, corporate spreads via S&P or skip.

## Vendor cascade

Six vendors total; 4 primary + 2 supplementary. Matches the AU vendor count (ABS + RBA + AOFM + Cotality + FRED-mirror) closely.

| Vendor | Role | Auth | Access pattern | Cells owned |
|---|---|---|---|---|
| **Stats NZ** | Statistical office (ABS analogue) | ADE API needs `Ocp-Apim-Subscription-Key`; Infoshare + release pages no-auth | **ADE SDMX-JSON** at `api.data.stats.govt.nz/rest/...` (Tier-1 where dataflow migrated) → **Infoshare Export Direct via Playwright** (deep history) → **release-page bulk CSV via Playwright** (latest snapshot fallback). All `www.stats.govt.nz` is JS-rendered — networkidle + 2s settle required. | 1.1, 1.3, 1.4 (real-econ + labour), 2.1-2.4, 3.1, 3.2, 3.3 (flow side) |
| **RBNZ** | Central bank (RBA analogue) | No key; Akamai/Cloudflare JS challenge on all `rbnz.govt.nz/-/media/...` paths | Playwright persistent context (same pattern as RBA F1+F2). Canonical XLSX URL: `https://www.rbnz.govt.nz/-/media/project/sites/rbnz/files/statistics/series/{letter}/{code}/h{code}-{cadence}.xlsx`. Rate limit: **7,000 requests/day**, 291/hour. Entry point: **data-file-index-page** (one-page listing of every current XLSX). Discontinued tables under `/statistics/discontinued-statistics/` — exclude. | 3.3 (foreign holdings), 3.4 (FX + TWI + reserves), 4.1-4.4 (all monetary/financial). M-series (M1/M9/M12/M14/M15) overlaps Stats NZ — defer to Stats NZ as Tier-1. |
| **NZDMO** | Sovereign debt manager (AOFM analogue) | No key; data hub at `debtmanagement.treasury.govt.nz/investor-resources/data` | Direct XLSX downloads (tender results history, issuance history, IIB factors, repurchase/buyback events). Cadence varies — per-tender (weekly-ish) to monthly. | 1.2 (debt-stock side). NOT 3.3 — NZDMO does not publish foreign holdings (RBNZ D30 does). NOT 4.3 turnover — RBNZ D35 owns. |
| **NZ Treasury** | Fiscal ministry | No key | Direct XLSX/PDF — Fiscal Time Series XLSX (1972→) + monthly FSGNZ (PDF tables) + BEFU + HYEFU semi-annual XLSX + Budget Data Library annual XLSX | 1.2 (revenue/expenditure/balance side), 1.4 (forecasts via BEFU/HYEFU) |
| **BIS** | Multilateral mirror | No key | SDMX-JSON at `stats.bis.org/api/v2/data/dataflow/BIS/{flow}/{ver}/{key}`. Reuses Indonesia helper `_bis_sdmx.py` — only ref-area swap to `NZ`. | 3.4 supplement (WS_EER), 4.2 supplement (WS_DSR + WS_CREDIT_GAP + WS_TC), 4.4 supplement (WS_CBPOL) |
| **FRED-mirror** | OECD/BIS via FRED | API key (existing) | Already wired; ~14 NZ-tagged series candidates | All cells (Tier-2 fallback). Existing ⚠ in cells 1.4, 2.4, 4.4. |

### Tier-2 fallback per cell

| Cell | Tier-1 | Tier-2 |
|---|---|---|
| 1.1 Private Demand    | Stats NZ ECT/RTS/BLD | RBNZ C12 (credit card) |
| 1.2 Fiscal Demand     | NZDMO + Treasury | RBNZ D30 (debt stock) |
| 1.3 External Demand   | Stats NZ IIE/OEA/ITS | RBNZ M14 (overseas trade mirror) |
| 1.4 Macro Core        | Stats NZ SNE/HLF/QES | FRED `NAEXKP01NZQ189S` + `LRUNTTTTNZQ156N` |
| 2.1 Input Costs       | Stats NZ FEPI | Stats NZ Business Price Indexes bundle |
| 2.2 Producer Prices   | Stats NZ PPI + CGPI | — |
| 2.3 Domestic Costs    | Stats NZ LCI + QES | RBNZ M15 (labour market mirror) |
| 2.4 CPI Pressure      | Stats NZ CPIQ + CPIM + SPI + HLPI | FRED `NZLCPIALLAINMEI`; RBNZ H1/M4 inflation expectations |
| 3.1 Terms of Trade    | Stats NZ OTI | — |
| 3.2 Current Account   | Stats NZ BOPQ | RBNZ M12 mirror |
| 3.3 Capital Account   | Stats NZ IIPQ + BOPQ FA + RBNZ D30 + RBNZ D31 | — |
| 3.4 FX / REER         | RBNZ B1 + E1 + B26 | BIS `WS_EER M.R.B.NZ` + FRED `CCRETT01NZM661N` |
| 4.1 Demand Trans      | RBNZ C-series + B-series + C60 SLOOS | — |
| 4.2 Balance Sheets    | RBNZ C13 + C21 + S-series + BIS WS_DSR + WS_TC + WS_CREDIT_GAP | FRED BIS-credit mirror |
| 4.3 Fin Conditions    | RBNZ B2 + B4 + D35 + NZDMO tenders | FRED `IRLTLT01NZM156N` + `IR3TBB01NZM156N` |
| 4.4 Policy Reaction   | RBNZ OCR event + C50 + D3 + D9 + D10 + BIS WS_CBPOL | FRED OECD mirror |

## Quirks to plan around (load-bearing)

1. **RBNZ Akamai gate** — every `rbnz.govt.nz/-/media/...` URL returns 403 to plain `httpx`. Need Playwright persistent context warm-up. Stay under 291 req/hour, 7,000 req/day. Per [[feedback-js-rendered-dont-bail]] + [[feedback-no-anti-detection-research]]: headed Playwright with `networkidle` settle, no stealth plugins.
2. **Stats NZ ADE subscription key** — keys are in `.env` as `IMDR_ECON_STATSNZ_PRIMARY_KEY` + `IMDR_ECON_STATSNZ_SECONDARY_KEY`. **ADE migration scope confirmed 2026-06-11 via `probe_ade.py`: 911 dataflows total but ZERO macro headlines** (CPI / GDP / HLFS / BOP / IIP / PPI / retail trade / building consents are all absent). What's there: 705 census flows (CEN13/CEN18/CEN23), 59 LEED labour earnings, 33 population estimates, 24 Iwi-affiliation census, 16 income microdata (INC_INC_*), 14 business demography (BDS_*), 10 corrections/justice, 7 household economic survey, 3 agriculture/forestry, 3 production (PRD), 21 population estimates. Discovery snapshot at `playground/econ/statsnz/discovery/ade/2026-06-11/`. **Implication**: Stats NZ Tier-1 for the macro pair is **NOT ADE**; it's release-page CSV (latest snapshot, `fetch.py` shape) → Infoshare Export Direct via Playwright (history). ADE will be re-probed periodically as Stats NZ migrates more flows.
3. **Stats NZ Infoshare is stateful ASP.NET** — no GET-URL shortcut for direct CSV. Two modes: (a) **Export Direct** uploads a `.sch` file (plain-text series ID list, max 100 per file) → returns CSV download; (b) per-table browse → multi-select → Export CSV. Both need Playwright.
4. **Stats NZ release-page CSV is latest-period only** — current `playground/econ/statsnz/fetch.py` covers only the latest quarter. Backfill needs Infoshare Export Direct, not the release-page path.
5. **CPIM (monthly CPI) starts 2027** — quarterly is the headline for the foreseeable future. Don't scaffold the monthly-CPI loader yet.
6. **No NZ zero-coupon term-premium series** — unlike AOFM. Cell 4.3 term premium = RBNZ B2 govt bonds + swap rates as proxy, or skip the AOFM-style FY/TP/RNY decomposition.
7. **NZDMO ≠ AOFM** for cell 3.3 — NZDMO does not publish a foreign-holdings table; RBNZ D30 (non-resident NZGB holdings monthly) is the analogue. RBNZ D31 (Kauri bonds) is the secondary slice.
8. **NZ tenor-by-investor cross-cut probably not public** — analogous to Indonesia DJPPR situation per [[reference-id-tenor-by-investor-search]]. D30 + D31 give resident vs non-resident; cross with tenor likely requires NZClear / Computershare microdata which isn't open. Don't sink time here.
9. **MPS XLSX projection data** is published with each quarterly MPS, but filename pattern (`mps-data-{mmm}{yyyy}.xlsx` candidate) needs Playwright on the issue page to confirm — folder slug has issue-specific date suffix (e.g. `feb-180226`).
10. **RBNZ M-series mirrors Stats NZ** for CPI / GDP / Trade / Labour (M1, M9, M14, M15). Always prefer Stats NZ as Tier-1 — RBNZ M-series is convenience only.

## Identity checks (Step 4)

To run when adjacent cells land. NZ-specific reconciliations:

| Identity | Cells | Check |
|---|---|---|
| `CA = goods + services + primary + secondary` | 3.2 internal | Stats NZ BOPQ sub-items sum to total |
| `Net IIP = FA − FL` | 3.3 internal | Stats NZ IIPQ identity |
| `Real GDP YoY ≈ Σ expenditure contributions` | 1.4 | Stats NZ SNE expenditure decomp |
| `Active + Inactive = Population 15+` | 1.4 | Stats NZ HLF labour identity |
| `Employed + Unemployed = Active` | 1.4 | Stats NZ HLF |
| `M1 ⊂ M3` | 4.4 | RBNZ C50 monetary aggregates |
| `Goods exports − Goods imports = Goods balance` (BoP basis) | 1.3 / 3.2 | Stats NZ OEA vs BOPQ goods reconciles |
| `OTI export ÷ OTI import × 100 ≈ Terms of trade` | 3.1 | Stats NZ OTI internal |
| `RBNZ M-series CPI ≈ Stats NZ CPIQ` | 2.4 cross-vendor | Sanity check on RBNZ mirror lag |
| `BIS WS_CBPOL M.NZ ≈ RBNZ OCR event log` | 4.4 cross-vendor | BIS mirror accuracy |

## Phase plan (proposed)

Aligned with [onboarding playbook §Step 3](../onboarding_new_country.md#step-3--headline-first-in-this-build-order). Discovery + cascade is now complete → ready for Phase 2 build, gated on user sign-off.

| Phase | Scope | Expected delta | Gated? |
|---|---|---|---|
| **Phase 2 — Headline pair** | Stats NZ CPIQ history (Infoshare Export Direct) + Stats NZ SNE GDP + RBNZ B2 (OCR + wholesale rates) | 3 fetchers, ~50 indicators, cells 2.4 / 1.4 / 4.4 flip to ⚠/✅ | ✅ user OK to start |
| **Phase 3 — BoP / IIP / Labour / Trade** | Stats NZ BOPQ + IIPQ + HLF + QES + IIE/OEA + RBNZ B1 (FX/TWI) | 6 fetchers, ~80 indicators, cells 3.2 / 3.3 / 3.4 / 1.3 flip | gated |
| **Phase 4 — RBNZ credit + balance sheets** | RBNZ C5/C41/C13/C21/C60 + B3/B20-25/B6/B7 mortgage rates + S-series banks + D-series settlement | 8 fetchers, ~120 indicators, cells 4.1 / 4.2 flip | gated |
| **Phase 5 — Fiscal + DMO** | Treasury Fiscal Time Series + FSGNZ + BEFU/HYEFU + NZDMO tender history | 4 fetchers, ~40 indicators, cell 1.2 flips | gated |
| **Phase 6 — Inflation expectations + supplements** | RBNZ M4 + H1 + Stats NZ PPI/CGPI/FEPI/LCI + BIS NZ slices | 5 fetchers, ~60 indicators, cells 2.1-2.3 + 2.4 sub-bullets fill | gated |
| **Phase 7 — Macroprudential event log + Survey of Expectations** | RBNZ LVR/DTI announcements + C40 DTI microdata + M5 Business Expectations | 2 fetchers + event-log scaffold, cell 4.4 sub-bullets fill | gated |
| **Phase 8 — Identity checks + cleanup + migration apply** | Run §Identity checks above; apply `dim_vendor` migrations for RBNZ/STATSNZ/NZDMO/TREASURY; load to DB | DB-LIVE | gated, user-supervised |
| **Phase 9 — Prod promotion** | Per [`../econ_to_prod.md`](../econ_to_prod.md) Phase G — promote helpers to `src/imdr/domains/econ/`, country orchestrators at `scripts/econ/nz/nz_{daily,monthly,quarterly}.py`, register in `imdr_{daily,monthly,quarterly}.py:PIPELINES` | Daily ingest live | gated, user OK each scheduler entry |

**Phase 2 — Track B (govt/CB document pipeline)** runs in parallel after Phase 2 lands, per the playbook's two-track model — RBNZ MPS PDF + speeches + media releases via Playwright into the research-doc pipeline. Out of scope until Track A is at least at Phase 4.

## Related

- [`index.md`](index.md) — NZ landing page (access paths + policy doc sources)
- [`_playground/rbnz.md`](_playground/rbnz.md) — RBNZ playground notes
- [`_playground/statsnz.md`](_playground/statsnz.md) — Stats NZ playground notes
- [`../macro_economy_wiring_map.md#78-new-zealand-nz`](../macro_economy_wiring_map.md) — wiring-map row (will flip cells as phases land)
- [`../onboarding_new_country.md`](../onboarding_new_country.md) — playbook
- [`../australia/australia_indicator_inventory.md`](../australia/australia_indicator_inventory.md) — closest comparable (16/16 ✅ template)
- [`../indonesia/indonesia_indicator_inventory.md`](../indonesia/indonesia_indicator_inventory.md) — sibling comparable (13/16 ✅)
