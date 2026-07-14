# Australia (AU) — Econ Indicator Inventory

Last updated: 2026-07-14

Tracker forked from [`../country_econ_blueprint.md`](../country_econ_blueprint.md) §1-4 per the [onboarding playbook](../onboarding_new_country.md#step-1--fork-the-blueprint-into-a-country-tracker).

**Status (2026-07-14):** DB-LIVE — **758 indicators / 523,708 obs** (DB-verified against `econ.fact_indicator`, 2026-07-14; up from 469 / 397,118 on 2026-06-19). **16 of 16 wiring-map cells ✅**, and the housing (4.2/1.1) + credit (4.1) + labour (1.4) cells are now considerably deeper than a single headline series.

**By vendor** (DB-verified 2026-07-14):

| Vendor | Indicators | Obs |
|---|---:|---:|
| ABS (Australian Bureau of Statistics) | 324 | 89,099 |
| AOFM (Australian Office of Financial Management) | 157 | 268,195 |
| RBA (Reserve Bank of Australia) | 119 | 127,276 |
| SEEK | 90 | 14,526 |
| SQM Research | 33 | 21,729 |
| Cotality (formerly CoreLogic) | 16 | 208 |
| APRA (Australian Prudential Regulation Authority) | 8 | 696 |
| ASX (Australian Securities Exchange) | 5 | 19 |
| ANZ Research | 3 | 1,854 |
| FRED (St. Louis Fed, OECD mirror) | 3 | 106 |
| **Total** | **758** | **523,708** |

**Housing + labour tracking buildout (2026-07-14):** 5 new sources loaded and wired into the AU orchestrators —

- **Cotality monthly HVI** (10 new indicators) — extends the existing daily-HVI fetcher with the page's "Monthly Values" tab: 8 capitals + Brisbane GCCSA cut + 5-capital aggregate (`COTALITY.HVI_MONTHLY.{SYDNEY,MELBOURNE,BRISBANE,BRISBANE_GCCSA,ADELAIDE,PERTH,FIVE_CAPITAL_AGG,DARWIN,CANBERRA,HOBART}.AU`). Rents / gross rental yield / national / rest-of-state confirmed **subscriber-only** (Cotality's own "Home Value Hedonic Indices FAQs" §5.1/§5.3) — not scrapable from the public page. Each run captures only the latest published month-end value (no backfill); history accumulates forward from 2026-06-30.
- **SQM Research** (33 new indicators) — weekly asking rents (`SQM.RENT.{8 caps}[_HOUSE|_UNIT].AU`, 8 cities × combined/houses/units = 24 series, 2009-08→) + monthly vacancy rates (`SQM.VACANCY.{8 caps+NATIONAL}.AU`, 9 series, 2005-01→). New vendor `sqm research` (sell_side) via migration 109; new unit `aud_pw` via migration 110. Data embedded server-side in an inline `<script>` JSON literal — plain `httpx`, no Playwright, no paywall on the underlying series.
- **APRA MADIS by-bank housing loans** (8 new indicators) — `APRA.ADI.{CBA,WBC,NAB,ANZ}.HOUSING_{OWNER_OCC,INVESTOR}.AU`, monthly since 2019-03 from APRA's free MADIS back-series XLSX (Table 1, long format). Gives loan **books**, not rates; no system-total row published (would require summing ~195 ADIs — out of scope).
- **SEEK** (90 new indicators) — Advertised Job Index (`SEEK.JOBADS.INDEX{,_TREND}.{NATIONAL+8 states}.AU`, 2001-07→) + Advertised Salary Index (`SEEK.SALARY.INDEX{,_TREND}.{NATIONAL+8 states+27 industries}.AU`, 2015-11→). (National+8 states)×2 variants = 18 job-ad series; (National+8 states+27 industries)×2 variants = 72 salary series; 90 total. Source: `au.seek.com/about/news/article/seek-employment-data` free XLSX (note: `www.seek.com.au` edge-403s the same request).
- **ANZ-Indeed Australian Job Ads** (3 new indicators) — `ANZ.JOBADS.INDEX{,_ORIG,_TREND}.NATIONAL.AU`, monthly since 1975-01 (619 obs) from the ANZ newsroom release-dates archive XLSX. National only — no state or industry/occupation breakdown published. Reuses the existing `anz` vendor row.
- **ABS labour by age + state** (+75 indicators in the LF/LF_UNDER group vs the 2026-06-19 baseline of 9) — extended `abs_labour.py` (age via sibling dataflow `LF_AGES`, state via `LF`'s own REGION dimension) and `abs_lf_under.py` (native AGE+REGION on `LF_UNDER`). New codes `ABS.LF{,_UNDER}.{MEASURE}_{AGE_x|STATE_x}_{SA|ORIG}.AU`. **DB-verified: LF group = 51 + LF_UNDER group = 33 = 84 total** (age/state breakdowns limited to the 3 desk-screen LF measures + 2 LF_UNDER rate measures; SA vs ORIG per-band/per-state availability varies — see `_playground/abs.md`). ABS does **not** publish age × state jointly (one breakdown dimension at a time; joint keys 404).

All five are wired into `au_daily` (SQM) or `au_monthly` (Cotality monthly, SEEK, ANZ-Indeed, APRA); ABS labour/LF_UNDER were already in `au_monthly`. Not wired into top-level `imdr_*` schedulers — that gate is unchanged and still pending explicit user sign-off.

**Known gaps not pursued this pass** (documented as gaps, not open TODOs): Cotality rents/yield/national (subscriber-only); Domain.com.au (entire origin Akamai-403s from this network); CBA Household Spending Insights (institutional login wall); AFR headlines (crawler-blocked); retail mortgage *rates* by bank (APRA MADIS gives loan books only — RBA F6 is a possible future source).

**Verification note (found during this refresh, not part of the housing/labour buildout):** the ABS `CPI` dataflow group grew from 22 to **86** indicators between 2026-06-22 and 2026-06-25 (COICOP group/sub-group breakdowns — `ABS.CPI.{AGG,GRP,SUB}_*`), and a new `ASX` vendor (5 indicators, `ASX.CASHRATE.*` / `ASX.RATETRACKER.*`, first ingested 2026-06-15) appeared in the DB — neither is narrated anywhere in this doc or in `_playground/abs.md`. Flagging for the record; not re-documented in full here as it's outside this session's scope.

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
| 1.1 Private Demand    | ✅ | ABS Retail Trade — monthly retail sales + **Cotality monthly HVI (10) + SQM weekly asking rents (24)** | 10/8  | 10 ABS retail indicators via `fetch_retail.py`; housing-as-demand proxy now covered daily/monthly/weekly by Cotality + SQM (see 4.2). |
| 1.2 Fiscal Demand     | ✅ | AOFM issuance/buybacks + portfolio aggregate             | 26/6  | 16 portfolio aggregate (TB+TIB+TN outstanding monthly) + 10 issuance/buyback flow. |
| 1.3 External Demand   | ✅ | ABS BOP 14 + BOP_GOODS 7 + ITPI 6 + ANA_EXP 10          | 37/10 | Full goods/services trade + expenditure decomp loaded. |
| 1.4 Macro Core        | ✅ | ABS ANA_AGG (GDP chain-vol SA) + LF/LF_UNDER (incl. age+state) + ANA_EXP + Job Vacancies + **SEEK (90) + ANZ-Indeed (3)** | 100/15 | GDP 7 + Labour+underutilisation **84** (was 9; +age/state breakdowns 2026-07-14) + Expenditure 10 + Job Vacancies 3 + SEEK Job-Ad/Salary indices 90 + ANZ-Indeed Job Ads 3. Labour-market cell now has 2 independent non-official leading indicators (SEEK ad volumes/salaries, ANZ-Indeed ad volumes) alongside the official LF release. |
| 2.1 Input Costs       | ✅ | ABS ITPI import-side SITC 1-digit (18 indicators — food / beverages-tobacco / crude materials / energy / fats-oils / chemicals / mfg-by-material / machinery-transport / misc-manufactures × Index + YoY) | 18/5 | Extended `fetch_trade_prices.py`; INDEX codes 6013001–6013009 from ITPI_IMP. Import crude materials YoY Q1-2026: +4.5%; energy YoY: +0.7%. |
| 2.2 Producer Prices   | ✅ | ABS PPI_FD — final demand (TSEST=TOTXE, not TOTIE)       | 3/7   | 3 indicators loaded. PPI by industry (PPI_IND) deferred. |
| 2.3 Domestic Costs    | ✅ | ABS WPI — OHRPEB/TOT (NSA only; SA not published)        | 6/10  | 6 indicators. SA unavailable from ABS. |
| 2.4 CPI Pressure      | ✅ | ABS CPI — headline (INDEX=10001, Q NSA) + Trimmed Mean + Weighted Median M + **6 SA quarterly analytical series via `CPI_Q` dataflow** | 22/13 | 22 indicators. `CPI_Q` adds Q SA trimmed mean + weighted median × index/QoQ/YoY (6 series, history 2000-Q1→, loaded 2026-06-19). Legacy `CPI` dataflow carries NSA quarterly only (TSEST=10) — the SA quarterly analytical series are absent there. |
| 3.1 Terms of Trade    | ✅ | ABS.TOT.NET_BARTER.AU (derived from ITPI export/import ratio × 100) | 1/4 | 65 quarterly obs back to 2010-Q1, latest Q1-2026 = 117.05. Loaded 2026-06-11 via `fetch_tot.py` derived from `ABS.ITPI.EXPORT_HEADLINE_INDEX.AU` / `ABS.ITPI.IMPORT_HEADLINE_INDEX.AU × 100`. |
| 3.2 Current Account   | ✅ | ABS BOP — CA + primary income + secondary income + capital | 14/10 | Full BOP flow loaded via `fetch_bop.py`. |
| 3.3 Capital Account   | ✅ | ABS BOP financial account + AOFM non-resident AGS holdings + **ABS IIP stocks** | 80/16 | BOP financial account 13 series + ITPI 6 + AOFM foreign holdings 34 series (quarterly since 2003; Mar-2026: non-resident AGS holdings AUD 469bn = 50.9% of outstanding) + **ABS IIP 33 series** (Q stock 1988-Q3 → 2026-Q1; Net IIP Mar-2026 = AUD +707bn net liability, Total FL = AUD 5.27tn, Gross External Debt = AUD 2.76tn). |
| 3.4 FX / REER         | ✅ | RBA F11.1 — AUD/USD + TWI + 17 AUD crosses               | 19/9  | 19 indicators. REER (BIS WS_EER) deferred. |
| 4.1 Demand Trans      | ✅ | RBA D2 — 14 credit aggregates (owner-occupier housing / investor housing / business / personal / total credit / narrow credit × NSA + SA) + **APRA MADIS by-bank housing loan books (8)** | 22/12 | Owner-occupier housing credit Apr-2026: AUD 1,747bn; investor housing credit Apr-2026: AUD 863bn. No RBA SLOOS-equivalent; D2 loan-growth as proxy. APRA MADIS (2026-07-14) adds the by-bank split for CBA/WBC/NAB/ANZ owner-occ + investor housing books monthly since 2019-03 — loan **books**, not rates; no system-total row published. |
| 4.2 Balance Sheets    | ✅ | RBA E1+E2 — 16 series (household total assets/liabilities/net worth + business loans/total liabilities + 8 E2 ratios) + **Cotality daily (6) + monthly (10) HVI + SQM vacancy rates (9)** | 41/15 | Household net worth Q4-2025: AUD 17,783bn; dwellings Q4-2025: AUD 11,821bn; debt-to-income 177.0%; housing-debt-to-income 133.7%; owner-occupier housing DTI 99.6%. Cotality monthly (2026-07-14) adds Darwin/Canberra/Hobart + the ABS-GCCSA Brisbane cut alongside the pre-existing 5-capital daily series; SQM vacancy rates add the demand-side counterpart to housing-wealth tracking. |
| 4.3 Fin Conditions    | ✅ | RBA F1+F2 rates + AOFM term premium + AOFM turnover      | 108/15 | 11 RBA rates + 30 AOFM term premium (FY/TP/RNY × 1Y..10Y, daily since 1992; 10Y Mar-2026: 95bp) + 67 AOFM turnover by region/tenor. |
| 4.4 Policy Reaction   | ✅ | RBA D3 — M1/M3/Broad money/Money base NSA+SA + RBA A2 — cash-rate event log (4 series) | 18/16 | D3: 14 indicators. A2: Cash Rate Target + administered rates event log, 4 series. Cash Rate Target May-2026: 4.35%. |

**Score (2026-07-14):** **16 of 16 cells ✅.** **758 indicators / 523,708 obs** in DB (DB-verified 2026-07-14; was 469 / 397,118+ on 2026-06-19). This session's housing + labour tracking buildout adds Cotality monthly HVI (+10), SQM Research rents+vacancy (+33, new vendor), APRA MADIS by-bank housing loans (+8, new vendor), SEEK Job-Ad/Salary indices (+90, new vendor), ANZ-Indeed Job Ads (+3), and ABS labour age/state breakdowns (+75 in the LF/LF_UNDER group). Cell 3.1 ToT closed via derived `ABS.TOT.NET_BARTER.AU` (ITPI export/import ratio × 100, quarterly back to 2010). ABS IIP (33 series) closes cell 3.3 stock-side. AOFM fills 1.2 (Fiscal Demand), 3.3 (Capital Account — bond-holders-by-investor), and supplements 4.3 (term premium + turnover). RBA D2+E1+E2+A2 close 4.1, 4.2, and supplements 4.4. **Identity checks 4 of 5 pass exact**: ToT derivation, Net IIP = FA+FL, 10Y breakeven (2.36% plausible), Household NW = TA-TL; BoP CA decomposition reconciles after manual goods+services balance derivation (Q1-2026: −25,743 = −26,693 primary + −1,696 secondary + 2,646 implied goods+services).

## Playground fetcher inventory

Originally 31 playground fetchers as of 2026-06-10; +5 sources / +1 vendor-set as of the 2026-07-14 housing+labour buildout (`scripts/econ/au/{cotality,sqm,apra,seek,anz}/`). All loaded into DB. **ABS CPI count below (22) reflects the 2026-06-19 doc baseline — DB now shows 86 for this dataflow group; see the verification note above (out-of-session drift, not re-documented in full here).**

| Fetcher | Vendor | Dataflow / Table | Cell | Indicators |
|---|---|---|:---:|:---:|
| `fetch_cpi.py` → `abs_cpi.py` | ABS | `CPI` (NSA quarterly + monthly headline + SA monthly analytical) + **`CPI_Q`** (SA quarterly analytical — trimmed mean + weighted median × index/QoQ/YoY, 6 series) | 2.4 | 22 (doc baseline; DB=86, see note) |
| `fetch_gdp.py` | ABS | `ANA_AGG` | 1.4 | 7 |
| `abs_labour.py` (was `fetch_labour.py`) | ABS | `LF` (headline 6) + `LF_AGES` sibling (age breakdown, 21) + `LF` REGION dim (state breakdown, 24) | 1.4 | **51** (was 6; +45 age/state 2026-07-14) |
| `abs_lf_under.py` (was `fetch_lf_under.py`) | ABS | `LF_UNDER` (M18/M21/M23/M24 — underemployment/underutilisation, native AGE+REGION dims) | 1.4 | **33** (was 3; +30 age/state 2026-07-14) |
| `cotality_hvi_monthly.py` | Cotality | Monthly Values tab, `cotality.com/au/our-data/indices` — 8 capitals + Brisbane GCCSA cut + 5-capital agg | 4.2 / 1.1 | 10 (NEW 2026-07-14) |
| `sqm_research.py` | SQM Research | Weekly asking rents (8 caps × combined/houses/units) + monthly vacancy (8 caps + National) | 4.2 / 1.1 | 33 (NEW 2026-07-14, new vendor) |
| `apra_madis.py` | APRA | MADIS back-series XLSX — big-4 owner-occ + investor housing loan books | 4.1 | 8 (NEW 2026-07-14) |
| `seek_jobads.py` | SEEK | Advertised Job Index (National+8 states × SA/Trend) + Advertised Salary Index (National+8 states+27 industries × SA/Trend) | 1.4 | 90 (NEW 2026-07-14, new vendor) |
| `anz_indeed_jobads.py` | ANZ | ANZ-Indeed Australian Job Ads — newsroom release-dates XLSX, National only, Original/SA/Trend | 1.4 | 3 (NEW 2026-07-14) |
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
| `fetch_iip.py` | ABS | `IIP` (International Investment Position — stocks, 33 series) | 3.3 | 33 |
| `fetch_building_approvals.py` | ABS | `BA_GCCSA` — national NSA dwellings count (Total Res + Houses) + value of jobs (Total Res + Commercial) | 1.1 / 4.2 | 4 |
| `fetch_reer.py` | RBA | F15 — Real Exchange Rate Measures (TWI + import-weighted + export-weighted) | 3.4 | 3 |
| `fetch_hvi.py` (cotality/) | Cotality | Daily Home Value Index for 5 capitals + 5-capital aggregate (Playwright render) | 4.2 / 1.1 | 6 |
| `fetch_zerocoupon.py` | RBA | F17 — Zero-coupon AGB curve: yields + forward rates @ 8 tenors (0.25Y / 0.5Y / 1Y / 2Y / 3Y / 5Y / 7Y / 10Y) | 4.3 | 16 |
| `fetch_rates.py` | RBA | F1 + F2 (cash rate, BBSW, OIS, AGB 2/3/5/10Y, **TIB 10Y real yield**) | 4.3 / 2.4 | 12 |
| `fetch_icp.py` | RBA | I2 — Index of Commodity Prices (7 sub-indices × A$/SDR/US$) | 3.1 / 3.4 commodity driver | 21 |
| `fetch_fx.py` | RBA | F11.1 | 3.4 | 19 |
| `fetch_monetary.py` | RBA | D3 | 4.4 | 14 |
| `fetch_d2_e_tables.py` | RBA | D2 + E1 + E2 + A2 (Playwright, CSV snapshots) | 4.1 / 4.2 / 4.4 | — (discovery; `fetch_credit_balsheet.py` loads) |
| `fetch_credit_balsheet.py` | RBA | D2 (14 credit aggregates) + E1+E2 (16 balance-sheet/ratio series) + A2 (4 cash-rate event-log series) | 4.1 / 4.2 / 4.4 | 34 |
| `fetch_foreign_holdings.py` | AOFM | Foreign holdings XLSX | 3.3 | 34 |
| `fetch_portfolio_aggregate.py` | AOFM | Portfolio aggregate XLSX | 1.2 | 16 |
| `fetch_term_premium.py` | AOFM | Term premium XLSX | 4.3 | 30 |
| `fetch_turnover.py` | AOFM | Turnover XLSX | 4.3 | 67 |
| `fetch_issuance_buybacks.py` | AOFM | Issuance/buybacks XLSX | 1.2 | 10 |

**Total (2026-06-19 doc baseline): 469 indicators (ABS 184 + RBA 119 + AOFM 157 + Cotality 6 + FRED-mirror 3) / 397,053 obs.** ABS sub-totals reconcile: CPI 22 (16 legacy `CPI` + 6 `CPI_Q` SA quarterly analytical added 2026-06-19) + GDP 7 + Labour 6 + LF_UNDER 3 + WPI 6 + PPI_FD 3 + Retail 10 + CAPEX 4 + Lending 11 + RPPI 17 + BOP 14 + BOP_GOODS 7 + Trade Prices 24 + GDP_EXP 10 + JV 3 + IIP 33 + BA 4 = 184. RBA: F1+F2 12 + F11.1 19 + D3 14 + D2+E1+E2+A2 34 + I2 ICP 21 + F15 REER 3 + F17 ZCY 16 = 119.

**Total (DB-verified 2026-07-14): 758 indicators / 523,708 obs.** Reconciliation vs the 2026-06-19 baseline (469, of which ABS's true total was 185 — the old formula's 184 omits the 1 `ABS.TOT.NET_BARTER.AU` ToT indicator from its itemised sum, a pre-existing doc bug, not a data issue):

- ABS: 185 → 324 (+139) = +75 LF/LF_UNDER age/state breakdown (this session: 6+3=9 → 51+33=84) + 64 CPI COICOP group/sub-group breakdown (found out-of-session, ingested 2026-06-22/25, not part of this buildout — see verification note above).
- RBA 119, AOFM 157, FRED-mirror 3 — unchanged.
- Cotality: 6 → 16 (+10 monthly HVI, this session).
- 3 new vendors this session: SQM Research 33, APRA 8, SEEK 90.
- ANZ Research: +3 (this session — ANZ-Indeed Job Ads; vendor row pre-existed for other AU econ use).
- ASX: 5 (found out-of-session, first ingested 2026-06-15, unrelated to this session — no doc previously described this vendor's econ-schema indicators).

185+139=324 (ABS) + 119 + 157 + 3 + 16 + 33 + 8 + 90 + 3 + 5 = **758**. ✓

## Phase G — BLOCKER LIFTED

AOFM data is in DB (157 indicators / 268,195 obs). The Phase G condition ("do not promote AU to
prod until AOFM resolved") is satisfied. Production promotion can proceed with explicit user sign-off.

Manual monthly refresh via Edge is the stable path (see [`_playground/aofm.md`](_playground/aofm.md)).
Playwright/Chrome automation of AOFM remains blocked by corp TLS-inspection; Chrome uses BoringSSL
which is reset by the corp firewall on `*.gov.au/sites/default/files/*.xlsx`. Edge (Schannel) works.

## Next moves (in priority order)

1. **[READY]** Sign off on production promotion — register AU into `scripts/imdr_{daily,monthly}.py:PIPELINES` (explicit user OK required per `feedback_no_prod_wiring_without_permission.md`). AOFM + IIP are quarterly/manual-monthly cadence; ABS daily fetchers + RBA monthly refresh need scheduling.
2. Stabilise RBA live-refresh via Playwright (current load is CSV snapshot for all 5 RBA fetchers; see [`_playground/rba.md`](_playground/rba.md)).
3. Derive ToT (3.1) from ITPI export/import price ratio (analytics-side, no new fetcher).

## Macro-signal backlog (what a real desk would still ask for)

Honest gap analysis from a rates / macro desk perspective. Current 412
indicators cover the official-publisher core (ABS / RBA / AOFM) but
miss several high-signal **non-official** surveys and a few derived
official series. Prioritised by signal-per-effort:

| # | Source | Why | Cadence | Transport | Status |
|---|---|---|---|---|---|
| 1 | **AiG Performance Indexes** (PMI / PSI / PCI → consolidated as "Australian Industry Index") | Australia's PMIs. Free, traded-on, classical leading indicator. | Monthly | plain httpx | 🔴 **Blocked 2026-06-10** — AiG consolidated PMI/PSI/PCI into a single "Australian Industry Index" rendered via Flourish iframes (72 embeds on the page). No inline data, no PDF, no CSV. Direct Flourish API/data endpoints 403. FRED-mirror search attempted but FRED API connection-failed from RV's network today (separate transient). Options: (a) reverse-engineer Flourish API per visualisation_id (brittle), (b) Playwright + DOM scraping of rendered embeds (heavy), (c) retry FRED mirror search when reachability returns. |
| 2 | **NAB Business Survey** (BSI) | The flagship AU business conditions / confidence indicator. | Monthly | plain httpx | 🟡 **Filing discovery LIVE 2026-06-10** — `playground/econ/au/govt/fetch_nab_business_survey.py` (manifest-only, lives in govt-filings playground). Slug pattern `/tag/economic-commentary/nab-monthly-business-survey---{month}-{year}` on `business.nab.com.au` (tag listing surfaces the latest only — daily-pull catches each new release). Numeric BSI value still inside the article body — extraction deferred to research-doc pipeline. |
| 3 | **Westpac–Melbourne Institute Consumer Sentiment** (CCI) | The flagship AU consumer-side confidence indicator. | Monthly | plain httpx | 🟡 **Filing discovery LIVE 2026-06-10** — `playground/econ/au/govt/fetch_westpac_cci.py` (lives in govt-filings playground; manifest-only). 13 monthly releases parsed from `westpaciq.com.au/topic.consumersentiment` with PDF URL pattern `er{YYYYMMDD}BullConsumerSentiment.pdf`. Actual numeric CCI value lives in the PDF — extraction deferred to research-doc pipeline. |
| 4 | **TIBs breakeven-inflation curve** | We have AGB nominal yields (RBA F2). Need indexed yields to compute breakeven. | Daily | RBA CSV snapshot | ✅ **LIVE 2026-06-10** — F2 already publishes 10Y indexed-bond yield (series `FCMYGBAGID`); added as `RBA.RATES.GOVTBOND_INDEXED_10Y.AU`. 2,884 obs back to 2014-11-20. Latest real 10Y = 2.501%, breakeven 10Y inflation = 4.863% − 2.501% = **2.36%** (derived analytics-side). |
| 5 | **RBA Index of Commodity Prices** (ICP, I2 stat table) | AU is the textbook commodity FX; ToT is the dominant AUD driver. | Monthly | RBA CSV snapshot | ✅ **LIVE 2026-06-10** — `fetch_icp.py` loads all 21 series (7 sub-indices × A$/SDR/US$): Total, Rural, Non-rural, Base metals, Bulk commodities export-price + spot-price. Monthly since 1982. 9,159 obs. |
| 6 | **CoreLogic (now Cotality) Daily Home Value Index** | ABS RPPI is quarterly. Cotality is daily, RBA cites it every FSR. | Daily | Playwright (JS-rendered table) | ✅ **LIVE 2026-06-10** — `playground/econ/cotality/fetch_hvi.py`. New vendor row in `dim_vendor` (migration 090). Each run captures 6 daily-HVI series (Sydney/Melbourne/Brisbane/Adelaide/Perth + 5-capital aggregate). Domain rebranded `corelogic.com.au` → `cotality.com`. |
| 7 | **ABS Building Approvals** + Motor Vehicle Sales | Building Approvals = classical leading construction indicator. Motor Vehicle Sales likely XLSX-only. | Monthly | ABS SDMX | ✅ **Building Approvals fully LIVE 2026-06-10** — `fetch_building_approvals.py`, 4 NSA national series (2 dwelling-count: Total Residential + Houses; 2 value-of-jobs: Total Residential + Commercial, AUD thousands after `aud_th` unit seeded via migration 091). SA series 404 at building-type level (only NSA published). Motor Vehicle Sales not in SDMX (XLSX-only) — separate XLSX-parser build required. |
| 8 | **State govt bonds** (TCV / NSWTC / QTC / WATC / SAFA — semis curve) | Semis trade as their own curve vs Commonwealth. | Daily | Per-state probe; fragmented | 🟡 **Probed 2026-06-10, deferred** — 3 of 5 state treasury sites (TCV /investors, NSW TCorp, SAFA) return 403 (Akamai/CDN gated, would need Playwright); QTC + WATC reachable. Each treasury has a different URL pattern + table shape → ~half-day per source. Substituted in this pass by RBA F16 awareness (per-bond AGB ISINs available but deferred to future `dim_bond_instrument` schema). |
| 9 | **China macro panel** (CPI / credit impulse / PMI / iron ore) | China is AU's #1 trade partner. | Various | Separate country buildout | Major (separate scope). |

**Latest build pass (2026-06-10):** items 4 + 5 (TIBs verification + RBA ICP) ✅; item 7 ABS Building Approvals — count series shipped, then value series shipped after `aud_th` unit seed ✅; item 3 Westpac CCI filing-discovery shipped (govt-filings, not time-series); item 6 Cotality Daily HVI ✅ (new vendor); bonus: RBA F15 REER ✅. Item 1 (AiG) blocked behind Flourish-only viz — FRED mirror retried, FRED API connection-failed from this network. Item 2 (NAB) parked. Item 8 (state semis) probed and deferred (3 of 5 sites Akamai-gated, half-day each).

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
23. ABS IIP International Investment Position (3.3 stock-side) — `fetch_iip.py`, 33 indicators, category `instr_outstand`, quarterly 1988-Q3 → 2026-Q1. [✓ loaded 2026-06-10]
24. RBA F2 indexed-bond yield (TIB, breakeven-inflation enabler) — added 1 series (`RBA.RATES.GOVTBOND_INDEXED_10Y.AU`) to `fetch_rates.py`. 2,884 obs daily 2014-11-20 → 2026-05-27. [✓ loaded 2026-06-10]
25. RBA I2 Index of Commodity Prices (commodity-FX / ToT driver) — `fetch_icp.py`, 21 series across 7 sub-indices × 3 currencies (A$ / SDR / US$). Monthly since 1982. [✓ loaded 2026-06-10]
26. ABS Building Approvals (BA_GCCSA dataflow, cell 1.1 leading indicator) — `fetch_building_approvals.py`, 4 NSA national-headline series: 2 count (Total Residential + Houses dwellings, monthly since 1983/1986) + 2 value-of-jobs (Total Residential + Commercial, monthly since 1973/2000, unit `aud_th` after migration 091). [✓ loaded 2026-06-10]
27. Cotality (formerly CoreLogic) Daily HVI — new vendor (migration 090, `dim_vendor.cotality` id=69). `playground/econ/cotality/fetch_hvi.py` Playwright-renders the JS-only indices page and emits 6 daily-frequency series (5 capitals + 5-capital aggregate). Each run captures today's snapshot; daily reruns accumulate the time-series. [✓ loaded 2026-06-10]
28. RBA F15 REER — `fetch_reer.py`, 3 quarterly series (Real TWI + Real import-weighted + Real export-weighted), since 1970. Closes cell 3.4 REER sub-bullet previously addressable only via BIS WS_EER. [✓ loaded 2026-06-10]
29. RBA F17 Zero-coupon AGB curve — `fetch_zerocoupon.py`, 16 daily series (8 desk-relevant tenors × yields + forward rates: 0.25Y / 0.5Y / 1Y / 2Y / 3Y / 5Y / 7Y / 10Y). Daily since 2017-01-03. Cleaner analytical curve than F2 interpolated bonds; useful for any rates relative-value or forwards trade. Discount factors NOT loaded (computable from yields). [✓ loaded 2026-06-10]
30. ABS CPI_Q — quarterly SA analytical series (`abs_cpi.py` extended). 6 new series added: `ABS.CPI.TRIMMED_MEAN_Q_{INDEX,QOQ,YOY}.AU` + `ABS.CPI.WEIGHTED_MEDIAN_Q_{INDEX,QOQ,YOY}.AU`. All SA (TSEST=20), national (REGION=50), history 2000-Q1→. Key shape `CPI_Q/{MEASURE}.{999902|999903}.20.50.Q`. Finding: the legacy `CPI` dataflow only carries TSEST=10 (NSA) at quarterly cadence — the SA quarterly analytical series were absent there. Trimmed Mean Q YoY (Q1-26: 3.5%) = RBA's canonical underlying-inflation gauge. [✓ loaded 2026-06-19]

**Housing + labour tracking buildout — 2026-07-14:**

31. ABS labour age/state breakdown (1.4) — `abs_labour.py` extended with `LF_AGES` sibling dataflow (7 age bands) + `LF`'s own REGION dimension (8 states/territories), for the 3 desk-screen measures (unemployment rate, participation rate, employed persons); `abs_lf_under.py` extended with `LF_UNDER`'s native AGE+REGION dims for the 2 headline rate measures (underemployment, underutilisation). +75 indicators (LF 6→51, LF_UNDER 3→33). SA vs Original picked per band/state per its own published availability (verified live against the codelists). [✓ loaded 2026-07-14]
32. Cotality Monthly Values (4.2/1.1) — `cotality_hvi_monthly.py` extends the existing daily-HVI fetcher to the same page's "Monthly Values" tab: 8 capitals + a second Brisbane cut (ABS GCCSA boundary, excl. Gold Coast) + 5-capital aggregate, 10 series. Rents/yield/national/rest-of-state confirmed subscriber-only via Cotality's own methodology FAQ — not pursued further. [✓ loaded 2026-07-14]
33. SQM Research weekly rents + monthly vacancy (4.2/1.1) — new vendor `sqm research` (migration 109). `sqm_research.py` scrapes an inline `<script>` JSON literal (no API, no paywall on the underlying series) for 8-capital weekly asking rents (combined/houses/units, 2009-08→) + 8-capital + national monthly vacancy rates (2005-01→). 33 indicators. New unit `aud_pw` (migration 110). [✓ loaded 2026-07-14]
34. APRA MADIS by-bank housing loans (4.1) — `apra_madis.py` parses APRA's free MADIS back-series XLSX (long-format Table 1) for CBA/WBC/NAB/ANZ owner-occupier + investor housing loan books, monthly since 2019-03. 8 indicators. Loan books, not rates; no system-total row published. [✓ loaded 2026-07-14]
35. SEEK Job-Ad + Salary indices (1.4) — new vendor `seek` (migration 109). `seek_jobads.py` scrapes two XLSX downloads off `au.seek.com/about/news/article/seek-employment-data`: Advertised Job Index (National+8 states × SA/Trend, 2001-07→) + Advertised Salary Index (National+8 states+27 industries × SA/Trend, 2015-11→). 90 indicators (18 job-ad + 72 salary). [✓ loaded 2026-07-14]
36. ANZ-Indeed Australian Job Ads (1.4) — `anz_indeed_jobads.py` scrapes the ANZ newsroom release-dates archive for the branded monthly job-ads series (Original/SA/Trend), National only, 1975-01→ (619 obs). Reuses the existing `anz` vendor row. 3 indicators. [✓ loaded 2026-07-14]

## Expected ❌ cells

| Cell | Common gap | Workaround |
|---|---|---|
| 3.1 ToT | Derivable from ITPI export/import price ratio; no standalone fetcher needed | Analytics-side derivation; no new fetcher required |
| 1.1 Private Demand — sentiment | ABS does not publish CCI/BSI | Westpac-MI CCI + NAB BSI (paid) or skip |
| 4.2 Balance Sheets — corporate ratios | RBA E-tables cover households; corporates sparse | BIS credit-to-GDP gap as cross-country fallback |

## Vendor / dataflow inventory (ABS SDMX)

20 dataflows loaded as of 2026-06-19 (CPI, **CPI_Q**, ANA_AGG, ANA_EXP, BOP, BOP_GOODS, CAPEX, **IIP**, ITPI_IMP, ITPI_EXP, JV, LEND_BUSINESS, LEND_HOUSING, LEND_PERSONAL, LF, LF_UNDER, PPI_FD, RPPI, RT, WPI). `CPI_Q` added 2026-06-19 — carries the SA quarterly analytical series absent from the legacy `CPI` flow. Full enumeration of all 1,223 ABS dataflows in `playground/econ/abs/discovery/dataflows_full.json`.

| Dataflow | Topic | National headline key | Loaded |
|---|---|---|:---:|
| `CPI` | Consumer Price Index | `1.10001.10.50.Q` (Q NSA national); also M headline + SA M analytical. **NSA-only at quarterly cadence** — the SA quarterly analytical series (trimmed mean / weighted median) are absent. | ✅ |
| `CPI_Q` | CPI Quarterly Analytical (SA) | `{1,2,3}.{999902,999903}.20.50.Q` — MEASURE 1=index, 2=QoQ%, 3=YoY%; INDEX 999902=Trimmed Mean, 999903=Weighted Median; TSEST=20 (SA); REGION=50 (national); FREQ=Q. 6 series, history 2000-Q1→. Trimmed Mean Q YoY (`ABS.CPI.TRIMMED_MEAN_Q_YOY.AU`) is RBA's canonical underlying-inflation gauge; latest Q1-26 YoY 3.5%. **Not present in legacy `CPI` dataflow.** | ✅ (added 2026-06-19) |
| `ANA_AGG` | National Accounts Key Aggregates | `M1.GPM.20.AUS.Q` (chain-vol GDP SA) | ✅ |
| `LF` (+ `LF_AGES` sibling) | Labour Force | `M13.3.1599.20.AUS.M` (unemployment rate, SA, national). Age breakdown lives in the sibling `LF_AGES` dataflow (LF 404s on non-headline AGE codes); state breakdown lives in `LF`'s own REGION dimension crossed with AGE=1599 only — age × state is not jointly published. 51 indicators total (6 headline + 21 age + 24 state, added 2026-07-14). | ✅ |
| `LF_UNDER` | Underemployment / underutilisation | Native AGE + REGION dims (no sibling dataflow needed). 33 indicators (4 headline + 14 age + 16 state — HOURS_WORKED_TOTAL headline 404s, silently skipped by the fetcher). | ✅ |
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
| **F15** | Real exchange rate measures | Monthly | ✅ 3 indicators (`fetch_reer.py`, corrected 2026-07-14 — was mis-marked ❌ deferred in this table despite being loaded since 2026-06-10) |
| **F17** | Zero-coupon analytical series | Daily | ✅ 16 indicators (`fetch_zerocoupon.py`, corrected 2026-07-14 — same mis-marking) |
| **D2** | Bank credit aggregates (owner-occupier / investor housing / business / personal / total / narrow × NSA+SA) | Monthly | ✅ 14 indicators (`fetch_credit_balsheet.py`) |
| **E1 + E2** | Household balance sheet (total assets/liabilities/net worth + business) + gearing ratios (debt-to-income, housing-DTI, etc.) | Quarterly | ✅ 16 indicators (`fetch_credit_balsheet.py`) |
| **G1**/G4 | CPI — RBA reformats ABS | Q/M | ❌ redundant (ABS direct loaded) |
| **H1**/H3/H5 | GDP / activity / labour — RBA reformats ABS | Q/M | ❌ redundant (ABS direct loaded) |
| **A2** | Monetary policy + administered rate changes (Cash Rate Target + bank rates event log) | Event | ✅ 4 indicators (`fetch_credit_balsheet.py`). Cash Rate Target May-2026: 4.35%. |

## Vendor / source inventory — non-official housing & labour (NEW 2026-07-14)

Four sources outside ABS/RBA/AOFM, all free/public, no login required. See per-vendor playground docs for transport details.

| Source | Series | Cadence | History | Loaded | Doc |
|---|---|:---:|---|:---:|---|
| **Cotality** (Monthly Values tab) | 8 capitals + Brisbane GCCSA cut + 5-capital agg, All Dwellings index | Monthly | Latest month-end only (no backfill; accumulates forward from 2026-06-30) | ✅ 10 | [`_playground/cotality.md`](_playground/cotality.md) |
| **SQM Research** | Weekly asking rents (8 caps × combined/houses/units) + monthly vacancy rates (8 caps + National) | Weekly + Monthly | 2009-08→ (rents), 2005-01→ (vacancy) | ✅ 33 | [`_playground/sqm.md`](_playground/sqm.md) |
| **APRA MADIS** | By-bank (CBA/WBC/NAB/ANZ) owner-occ + investor housing loan books | Monthly | 2019-03→ | ✅ 8 | [`_playground/apra.md`](_playground/apra.md) |
| **SEEK** | Advertised Job Index (National+8 states × SA/Trend) + Advertised Salary Index (National+8 states+27 industries × SA/Trend) | Monthly | 2001-07→ (jobs), 2015-11→ (salary) | ✅ 90 | [`_playground/seek.md`](_playground/seek.md) |
| **ANZ-Indeed** | Australian Job Ads, National, Original/SA/Trend | Monthly | 1975-01→ | ✅ 3 | [`_playground/anz.md`](_playground/anz.md) |

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
- **Cotality rents / gross rental yield / national / rest-of-state**: confirmed subscriber-only (2026-07-14 probe against Cotality's own methodology FAQ) — not pursued further, documented as a known gap rather than an open TODO.
- **Retail mortgage rates by bank**: APRA MADIS gives loan books, not rates; RBA F6 lending rates is a possible future source if a by-bank rate cut is wanted.
- **Domain.com.au, CBA Household Spending Insights, AFR headlines**: probed 2026-07-14 and parked — Akamai-403 (Domain), institutional login wall (CBA HSI), crawler-blocked (AFR).
- **CPI COICOP breakdown (86 indicators) + ASX vendor (5 indicators)**: found in the DB during this refresh's verification pass but not narrated in any AU doc — neither is part of this session's buildout. Flagged as a question for the operator rather than back-filled here.

## Cross-refs

- [`index.md`](index.md) — country landing
- [`_playground/abs.md`](_playground/abs.md) — ABS playground notes
- [`_playground/rba.md`](_playground/rba.md) — RBA playground notes
- [`_playground/cotality.md`](_playground/cotality.md) — Cotality daily + monthly HVI
- [`_playground/sqm.md`](_playground/sqm.md) — SQM Research rents + vacancy (NEW 2026-07-14)
- [`_playground/apra.md`](_playground/apra.md) — APRA MADIS by-bank housing loans (NEW 2026-07-14)
- [`_playground/seek.md`](_playground/seek.md) — SEEK Job-Ad + Salary indices (NEW 2026-07-14)
- [`_playground/anz.md`](_playground/anz.md) — ANZ-Indeed Job Ads (NEW 2026-07-14)
- [`../country_econ_blueprint.md`](../country_econ_blueprint.md) — indicator catalogue
- [`../macro_economy_wiring_map.md#77-australia-au`](../macro_economy_wiring_map.md#77-australia-au) — wiring map §7.7
