# Macro Economy Wiring Map

**Generic clusters. Choose indicators by country and regime — the wiring stays broadly stable.**

> Read the map as clusters, not a checklist in isolation: identify the active loop first, then pick the country-specific data that best represents it. The four main loops are **Growth → Inflation → External/FX → Policy Transmission**. Each loop feeds the next; feedback runs in both directions.

This file is the **coverage target** for `econ.dim_indicator`. Every cluster below should resolve to at least one indicator per country we care about. The per-country tracker in §6 is updated as fetchers + sign-offs land.

- **Onboarding playbook**: [onboarding_new_country.md](onboarding_new_country.md) — 5-step workflow with vendor cascade, build order, identity checks, quality bar, ❌→⚠→✅ promotion rules.
- **Indicator catalogue**: [country_econ_blueprint.md](country_econ_blueprint.md) — country-agnostic master list of series per cluster.
- **Schema + build log**: [economics_data_ingest.md](economics_data_ingest.md) — pipeline + per-vendor build state.
- **Date**: 2026-06-22 (§7.12 IN Cluster 4: OGD Agmarknet mandi-price pre-prod note added; prior 2026-06-19 IN Track A Phase G)

---

## 1. Growth Engine

> Demand components feed GDP, income and slack.

### 1.1 Private Demand
- Consumption, capex and housing
- Household income, wages, confidence
- Household credit and wealth effects

### 1.2 Fiscal Demand
- Government spending
- Taxes, transfers and subsidies
- Fiscal impulse and deficits

### 1.3 External Demand
- Exports and imports
- Net exports and global demand
- Inventories / stock cycle

### 1.4 Macro Core
- GDP, income and productivity
- Output gap / slack
- Employment and PMI nowcast

**Internal wiring**: 1.1 + 1.2 + 1.3 → demand components feed 1.4 (Macro Core).

---

## 2. Inflation Engine

> Cost pressures and domestic slack feed CPI.

### 2.1 Input Costs
- Commodities, food and energy
- Supply shocks and bottlenecks
- FX pass-through starts here

### 2.2 Producer Prices
- Import prices and PPI
- Margins and inventories
- Pipeline pressure into CPI

### 2.3 Domestic Costs
- Wages, rents and services
- Capacity utilisation
- Inflation expectations

### 2.4 CPI Pressure
- Core and headline CPI
- Breadth and persistence
- Real income squeeze

**Internal wiring**: 2.1 → 2.2 → 2.4; 2.3 → 2.4 directly (slack → prices). Macro slack from §1.4 also feeds 2.4.

---

## 3. External & FX

> Balance of payments and competitiveness loop.

### 3.1 Terms of Trade
- Export prices vs import prices
- Commodity exposure
- National income shock

### 3.2 Current Account
- Trade balance
- Services, income balance, remittances
- External saving / funding need

### 3.3 Capital Account
- FDI, portfolio and bank flows
- Reserves and errors & omissions
- Funding quality / reversibility

### 3.4 FX / REER
- Spot FX, NEER and REER
- Competitiveness and pass-through
- Reserve pressure / intervention

**Internal wiring**: 3.4 (FX) feeds back into 2.1 (Input Costs via FX pass-through). 3.1 + 3.2 + 3.3 drive 3.4 over the medium term.

---

## 4. Policy Transmission

> Reaction function works through financial conditions.

### 4.1 Demand Transmission
- Loan growth and lending standards
- Housing / wealth channel
- Consumption and capex response

### 4.2 Balance Sheets
- Households, corporates, banks, sovereign
- Debt service, NPLs, refinancing wall
- Financial stability constraint

### 4.3 Financial Conditions
- Real rates, curve and credit spreads
- Loan rates and liquidity
- Equities / credit / market pricing

### 4.4 Policy Reaction
- Policy rate and liquidity
- Fiscal stance and macroprudential tools
- Reaction to CPI, growth and FX

**Internal wiring**: 4.4 → 4.3 → 4.1 → §1 (Growth Engine, feedback to demand). 4.2 is the constraint that gates transmission.

---

## 5. Reading the map

The map is regime-agnostic. Different countries lean on different bullets in the same cluster (e.g. **2.3 Domestic Costs**: US watches ECI + JOLTS quits, India watches WPI services component, Korea watches MOTIE wage tracker). The cell wiring stays stable; only the chosen indicator changes.

For how to *use* this map (workflow, promotion rules, identity checks), see [onboarding_new_country.md](onboarding_new_country.md).

---

## 6. Per-country coverage tracker

Status per (country, cluster). Legend:
- ✅ at least one indicator on disk + registered in `dim_indicator`
- ⚠️ partial (some bullets covered, gaps remain)
- ❌ no coverage yet
- — not applicable for this country

Countries in scope (Phase 1–3): G10 + key APAC. Edit this table as fetchers land + indicators are seeded.

### 6.1 Growth Engine

| Country | 1.1 Private Demand | 1.2 Fiscal Demand | 1.3 External Demand | 1.4 Macro Core |
|---|:---:|:---:|:---:|:---:|
| US | ❌ | ❌ | ❌ | ⚠️ (FRED GDP + payrolls) |
| EU | ❌ | ❌ | ❌ | ❌ |
| UK | ❌ | ❌ | ❌ | ❌ |
| JP | ❌ | ❌ | ❌ | ❌ |
| CA | ❌ | ❌ | ❌ | ❌ |
| AU | ✅ (ABS Retail Trade 10 + ABS Lending 11 + Cotality Daily HVI 6 + ABS RPPI 17) | ✅ (AOFM portfolio agg 16 + issuance/buybacks 10) | ✅ (ABS BOP 14 + BOP_GOODS 7 + ITPI 24 + ANA_EXP 10) | ✅ (ABS ANA_AGG GDP 7 + LF 6 + LF_UNDER 3 + ANA_EXP 10 + JV 3 + CAPEX 4) |
| NZ | ❌ | ❌ | ❌ | ❌ |
| CN | ❌ | ❌ | ❌ | ❌ |
| HK | ❌ | ❌ | ❌ | ❌ |
| SG | ❌ | ❌ | ❌ | ❌ |
| IN | ⚠️ (MOSPI NAS PFCE Q + UPAg AIAPY) | ⚠️ (CGA 30 fiscal line items; MOSPI NAS GFCE Q) | ✅ (DGCIS 198 × HS-2 + Bulletin T32 Foreign Trade) | ✅ (MOSPI IIP + DPIIT 8-Core + MOSPI NAS GDP + Bulletin T23 + FRED) |
| KR | ✅ (KOSTAT Retail + BOK CCI + Consumer Tendency Survey) | ✅ (BOK 200Y154 Public Sector Revenue/Expenditure/Net Lending) | ✅ (BOK Trade Value+Volume indices + BoP goods X/M) | ✅ (KOSIS GDP-Q + KOSTAT EAPS labour + KOSTAT IIP + BSI Mfg) |
| TW | ❌ | ❌ | ❌ | ❌ |
| PH | ❌ | ❌ | ❌ | ❌ |
| TH | ❌ | ❌ | ❌ | ❌ |
| ID | ❌ | ❌ | ❌ | ❌ |

### 6.2 Inflation Engine

| Country | 2.1 Input Costs | 2.2 Producer Prices | 2.3 Domestic Costs | 2.4 CPI Pressure |
|---|:---:|:---:|:---:|:---:|
| US | ⚠️ (FRED oil/gas) | ❌ | ❌ | ⚠️ (FRED CPI) |
| EU | ❌ | ❌ | ❌ | ❌ |
| UK | ❌ | ❌ | ❌ | ❌ |
| JP | ❌ | ❌ | ❌ | ❌ |
| CA | ❌ | ❌ | ❌ | ❌ |
| AU | ✅ (ABS ITPI SITC 1-digit 18 + RBA ICP 21 sub-indices × A$/SDR/US$) | ✅ (ABS PPI_FD 3 — TSEST=TOTXE) | ✅ (ABS WPI 6 — OHRPEB total, NSA-only) | ✅ (ABS CPI 16 — headline Q + Trimmed Mean M + Weighted Median M + subcategories) |
| NZ | ❌ | ❌ | ❌ | ⚠️ (Stats NZ CPI release) |
| CN | ❌ | ❌ | ❌ | ❌ |
| HK | ❌ | ❌ | ❌ | ❌ |
| SG | ❌ | ❌ | ❌ | ❌ |
| IN | ⚠️ (DPIIT 8-Core fuel/energy + UPAg MSP + UPAg IMC mandi) | ✅ (DPIIT WPI 8 series + Bulletin T22 WPI 48 sub-aggregates) | ❌ (wages — Labour Bureau corp-firewall blocked) | ✅ (MOSPI CPI 78 + Bulletin T19C 28 + FRED OECD MEI + FAO FPI) |
| KR | ✅ (BOK Import/Export prices × Won/USD; CPI Fresh-food) | ✅ (KOSIS BOK PPI Total + 5 sectors) | ✅ (KOSTAT Wages annual + Mfg Capacity Util + BOK Expected Inflation) | ✅ (KOSTAT CPI Headline + Living + Core × MoM/YoY/YTD) |
| TW | ❌ | ❌ | ❌ | ❌ |
| PH | ❌ | ❌ | ❌ | ❌ |
| TH | ❌ | ❌ | ❌ | ❌ |
| ID | ❌ | ❌ | ❌ | ❌ |

### 6.3 External & FX

| Country | 3.1 Terms of Trade | 3.2 Current Account | 3.3 Capital Account | 3.4 FX / REER |
|---|:---:|:---:|:---:|:---:|
| US | ❌ | ❌ | ❌ | ⚠️ (FRED DXY) |
| EU | ❌ | ❌ | ❌ | ❌ |
| UK | ❌ | ❌ | ❌ | ❌ |
| JP | ❌ | ❌ | ❌ | ❌ |
| CA | ❌ | ❌ | ❌ | ❌ |
| AU | ❌ (derivable from ITPI_EXP/ITPI_IMP ratio, analytics-only) | ✅ (ABS BOP CA + primary + secondary + capital + financial 14) | ✅ (ABS BOP FA 13 + AOFM foreign holdings 34 + ABS IIP 33) | ✅ (RBA F11.1 AUD/USD + TWI + 17 crosses 19 + RBA F15 REER 3) |
| NZ | ❌ | ❌ | ❌ | ❌ |
| CN | ❌ | ❌ | ❌ | ❌ |
| HK | ❌ | ❌ | ❌ | ❌ |
| SG | ❌ | ❌ | ❌ | ❌ |
| IN | ⚠️ (derivable from DGCIS + Bulletin T32) | ✅ (Bulletin T40 BoP — Current Acc / Merchandise / Invisibles / Services × Credit+Debit+Net) | ✅ (RBI DBIE FX reserves weekly + Bulletin T33 + T34 NRI Deposits) | ✅ (BIS NEER+REER 1994→ + Bulletin T37 + FRED DEXINUS) |
| KR | ✅ (KOSIS BOK Net Barter + Income ToT) | ✅ (KOSIS BoP CA + Goods/Services/Primary/Secondary 1980→) | ✅ (KOSIS BoP FA + DI/PI/Deriv/OI/Reserves + E&O 1980→) | ❌ (KOSIS-absent — FX rates + reserves need Citi spot / BOK direct) |
| TW | ❌ | ❌ | ❌ | ❌ |
| PH | ❌ | ❌ | ❌ | ❌ |
| TH | ❌ | ❌ | ❌ | ❌ |
| ID | ❌ | ❌ | ❌ | ❌ |

### 6.4 Policy Transmission

| Country | 4.1 Demand Transmission | 4.2 Balance Sheets | 4.3 Financial Conditions | 4.4 Policy Reaction |
|---|:---:|:---:|:---:|:---:|
| US | ❌ | ❌ | ⚠️ (FRED UST + spreads) | ⚠️ (FRED Fed Funds + IOER) |
| EU | ❌ | ❌ | ❌ | ❌ |
| UK | ❌ | ❌ | ❌ | ❌ |
| JP | ❌ | ❌ | ❌ | ❌ |
| CA | ❌ | ❌ | ❌ | ❌ |
| AU | ✅ (RBA D2 14 credit aggregates × NSA+SA + ABS Lending 11 new commitments) | ✅ (RBA E1+E2 16 household + business balance sheets + 8 gearing ratios) | ✅ (RBA F1+F2 12 cash/BBSW/OIS/AGB/TIB + AOFM term premium 30 + turnover 67 + F17 zero-coupon curve 16) | ✅ (RBA D3 14 monetary aggregates NSA+SA + RBA A2 4 cash-rate event log) |
| NZ | ❌ | ❌ | ❌ | ❌ |
| CN | ❌ | ❌ | ❌ | ❌ |
| HK | ❌ | ❌ | ❌ | ⚠️ (HKMA aggregate balance + EFBN) |
| SG | ❌ | ❌ | ❌ | ❌ |
| IN | ❌ (needs DBIE Sectoral Deployment) | ⚠️ (BIS DSR + Credit-to-GDP + Bulletin T2 RBI BS; A7 BSR + NBFC pending) | ⚠️ (RBI DBIE WACR daily + Bulletin T27 Call Money + FRED OECD Call Money) | ✅ (RBI DBIE Repo/SDF/Reverse Repo/CRR/SLR + BIS CBPOL + Bulletin T6 Money Stock + T11 Reserve Money) |
| KR | ✅ (BOK Lending Attitude Survey + Household Loans monthly + REB housing) | ✅ (BOK HH Credit + Corp financial ratios × 13 + FSS NPL legacy) | ⚠️ (KOSIS bank deposit + CD 91d + Repo rates — deposit-side only; KOSIS confirmed not to carry BOK Base Rate; Base Rate is in cell 4.4 via BIS CBPOL) | ✅ (BIS CBPOL BOK Base Rate daily 1999→ **[primary]** + FRED Call / 3M Interbank / 10Y Govt + BOK M2/Lf monetary aggregates. FRED Discount Rate deactivated 2026-06-16 — was discount rate not Base Rate.) |
| TW | ❌ | ❌ | ❌ | ❌ |
| PH | ❌ | ❌ | ❌ | ❌ |
| TH | ❌ | ❌ | ❌ | ❌ |
| ID | ❌ | ❌ | ❌ | ❌ |

---

## 7. Per-country wiring view (image-as-checklist)

One 4×4 grid per country — same layout as the wiring map image. Status of each cluster at a glance; named indicators in parentheses.

Columns left-to-right are the 4 clusters of each engine. Rows top-to-bottom are the 4 engines (Growth / Inflation / External / Policy).

Legend: ✅ at-least-one indicator on disk + registered • ⚠️ partial (named) • ❌ no coverage yet • — N/A.

### 7.1 United States (US)

Updated 2026-06-03 after FRED load v2 (162 indicators total, 133 US-specific).

| Engine | A | B | C | D |
|---|:---:|:---:|:---:|:---:|
| **Growth** | ⚠️ Private *(retail sales, cap-goods orders, real DPI)* | ⚠️ Fiscal *(FGEXPND/FGRECPT/FYFSGDA188S + debt + monthly MTS)* | ⚠️ External *(EXPGS, IMPGS, NETEXP)* | ✅ Macro Core *(GDP, GDPNow, INDPRO, payrolls, CFNAI)* |
| **Inflation** | ⚠️ Input Costs *(WTI, Brent, HH gas, gold)* | ⚠️ Producer *(PPIACO, PPIFIS, IR import price)* | ⚠️ Domestic *(AHE, ECI wages, MICH 1Y exp)* | ✅ CPI *(CPI + Core + PCE + 6 more)* |
| **External** | ❌ Terms of Trade | ⚠️ Current Acc *(IEABC current account quarterly + BOPGSTB monthly trade balance)* | ❌ Capital Acc | ⚠️ FX/REER *(DTWEXBGS, AFE, EME)* |
| **Policy** | ⚠️ Demand Trans *(SLOOS, mortgage rates, BUSLOANS)* | ⚠️ Balance Sheets *(TDSP, FODSP, CMDEBT, HH mortgage debt)* | ✅ Fin Conditions *(UST curve + IG/HY/BAA OAS + NFCI + VIX)* | ✅ Policy *(Fed funds, EFFR, SOFR, IORB, Fed BS, RRP)* |

US score: **4 ✅ / 11 ⚠️ / 1 ❌** (was 4/8/4 before v2 expansion). Only Terms-of-Trade and Capital-Account remain ❌.

> **Tier-1 source-agency discovery COMPLETE + DATA LOADED 2026-06-22 (playground-resident, NOT promoted/orchestrated — §7.1 markers NOT flipped yet, as ✅ requires a *registered prod* fetcher).** Migration 105 registered vendors bls/bea/census/treasury_us; **82 indicators / 30,563 obs loaded** into `econ.fact_indicator` (BEA 36 back to 1947, BLS 29, EIA 3, Treasury 4, Census 10) via the user-supervised one-shot loader. FRED is a mirror; the source agencies now have working playground fetchers, all producing loader-valid parquet. Built: **BLS** (CPI · PPI · Employment Situation · ECI/JOLTS/productivity · import/export prices → cells 1.4·2.1·2.2·2.3·2.4·**3.1**), **BEA** (GDP/NIPA · Personal Income/PCE · ITA current+financial account · IIP → 1.1·1.3·1.4·2.4·**3.2**·**3.3**), **Census** (MARTS retail · FT-900 trade · New Residential Construction → 1.1·1.3), **Treasury** (MTS fiscal · Debt-to-Penny → 1.2·4.2), **EIA** (WTI/Brent/Henry Hub spot → 2.1). Identity checks pass: BoP CA decomposition diff=0, export/import ToT=1.12, fiscal receipts−outlays=deficit diff=0. The two ❌ (3.1 Terms-of-Trade, 3.3 Capital Account) are now covered in discovery (BLS import/export ratio; BEA ITA financial account + IIP). Cells flip to ✅ on prod promotion per [econ_to_prod.md](econ_to_prod.md). Plan: [united_states/us_coverage_plan.md](united_states/us_coverage_plan.md). Track B (FOMC docs) discovery also complete — [united_states/us_govt_doc_sources.md](united_states/us_govt_doc_sources.md).

### 7.2 Eurozone (EU)

| Engine | A | B | C | D |
|---|:---:|:---:|:---:|:---:|
| **Growth** | ❌ | ❌ | ❌ | ⚠️ Macro Core *(FRED Real GDP + Harmonised Unemployment + IIP)* |
| **Inflation** | ❌ | ❌ | ❌ | ⚠️ CPI *(FRED HICP + OECD CPI YoY)* |
| **External** | ❌ | ❌ | ❌ | ❌ |
| **Policy** | ❌ | ❌ | ❌ | ⚠️ Policy *(FRED ECB total assets — partial)* |

### 7.3 United Kingdom (UK)

| Engine | A | B | C | D |
|---|:---:|:---:|:---:|:---:|
| **Growth** | ❌ | ❌ | ❌ | ⚠️ Macro Core *(FRED Real GDP + OECD Unemployment + IIP)* |
| **Inflation** | ❌ | ❌ | ❌ | ⚠️ CPI *(FRED CPI YoY)* |
| **External** | ❌ | ❌ | ❌ | ❌ |
| **Policy** | ❌ | ❌ | ❌ | ⚠️ Policy *(FRED gilt yields 2 series — partial)* |

### 7.4 Japan (JP)

| Engine | A | B | C | D |
|---|:---:|:---:|:---:|:---:|
| **Growth** | ❌ | ❌ | ❌ | ⚠️ Macro Core *(FRED Real GDP + OECD Unemployment + IIP)* |
| **Inflation** | ❌ | ❌ | ❌ | ⚠️ CPI *(FRED CPI YoY)* |
| **External** | ❌ | ❌ | ❌ | ❌ |
| **Policy** | ❌ | ❌ | ❌ | ⚠️ Policy *(FRED JGB yield — partial)* |

### 7.5 Canada (CA)

| Engine | A | B | C | D |
|---|:---:|:---:|:---:|:---:|
| **Growth** | ❌ | ❌ | ❌ | ⚠️ Macro Core *(FRED Real GDP + OECD Unemployment + IIP)* |
| **Inflation** | ❌ | ❌ | ❌ | ⚠️ CPI *(FRED CPI YoY)* |
| **External** | ❌ | ❌ | ❌ | ❌ |
| **Policy** | ❌ | ❌ | ❌ | ❌ |

### 7.6 Switzerland (CH)

| Engine | A | B | C | D |
|---|:---:|:---:|:---:|:---:|
| **Growth** | ❌ | ❌ | ❌ | ⚠️ Macro Core *(FRED IIP only — GDP + Unemployment codes failed validation, see §8.1)* |
| **Inflation** | ❌ | ❌ | ❌ | ⚠️ CPI *(FRED CPI YoY)* |
| **External** | ❌ | ❌ | ❌ | ❌ |
| **Policy** | ❌ | ❌ | ❌ | ❌ |

### 7.7 Australia (AU)

Updated 2026-07-14: **758 indicators / 523,708 obs DB-LIVE** (DB-verified 2026-07-14, up from 463 / 397,053 on 2026-06-10). **16 of 16 cells ✅**. ABS 20 fetchers / 22 dataflows (324 indicators, incl. new age/state labour breakdowns) + RBA 9 fetchers via CSV snapshot (119 indicators incl. TIB + I2 ICP + F15 REER + F17 zero-coupon curve) + AOFM 5 fetchers (157 indicators) + Cotality (16 indicators — 6 daily + 10 monthly HVI) + SQM Research (33, rents+vacancy, new vendor) + APRA MADIS (8, by-bank housing loans) + SEEK (90, job-ad+salary indices, new vendor) + ANZ-Indeed (3, job ads) + FRED-mirror (3). Phase G blocker lifted. Second-most-populated country after Indonesia. **2026-07-14 housing + labour tracking buildout**: 5 new sources wired into `au_daily`/`au_monthly` (not yet into top-level `imdr_*` schedulers — separate sign-off gate); migrations 109 (SQM/SEEK vendor seed) + 110 (`aud_pw` unit seed) applied. See [`australia/australia_indicator_inventory.md`](australia/australia_indicator_inventory.md).

| Engine | A | B | C | D |
|---|:---:|:---:|:---:|:---:|
| **Growth** | ✅ Private Demand *(ABS Retail Trade 10 series + **Cotality monthly HVI 10 + SQM weekly asking rents 24, NEW 2026-07-14**)* | ✅ Fiscal Demand *(AOFM portfolio aggregate 16 series — TB+TIB+TN outstanding monthly since 2003; AOFM issuance/buybacks 10 series — monthly gross issuance + buyback flows)* | ✅ External Demand *(ABS BOP 14 + BOP_GOODS 7 + ITPI 6 + ANA_EXP 10)* | ✅ Macro Core *(ABS ANA_AGG GDP chain-vol SA + LF/LF_UNDER unemployment/participation/employed incl. **age+state breakdowns, 84 series (was 9), NEW 2026-07-14** + ANA_EXP expenditure decomp + Job Vacancies 3 + **SEEK Job-Ad/Salary indices 90 + ANZ-Indeed Job Ads 3, both NEW 2026-07-14**)* |
| **Inflation** | ✅ Input Costs *(ABS ITPI import-side SITC 1-digit — 18 indicators: food/beverages-tobacco/crude materials/energy/fats-oils/chemicals/mfg-by-material/machinery-transport/misc-manufactures × Index+YoY. Import crude materials YoY Q1-2026: +4.5%; energy: +0.7%)* | ✅ Producer Prices *(ABS PPI_FD 3 — final demand, TSEST=TOTXE)* | ✅ Domestic Costs *(ABS WPI 6 — OHRPEB, TOT level, NSA-only — SA not published)* | ✅ CPI Pressure *(ABS CPI — headline Q NSA + Trimmed Mean M + Weighted Median M + subcategories + CPI_Q SA quarterly analytical; DB shows 86 series for this group as of 2026-07-14, up from the 16-22 range documented 2026-06-19 — a COICOP group/sub-group breakdown found during this refresh's DB verification, ingested 2026-06-22/25, not part of any AU buildout session and not yet narrated in `_playground/abs.md`)* |
| **External** | ❌ | ❌ 3.1 ToT *(derivable from ITPI export/import ratio — analytics-only, no fetcher)* | ✅ Current Account *(ABS BOP 14 — CA + primary + secondary + capital + financial account sub-items)* + ✅ Capital Account *(AOFM foreign holdings 34 series — non-resident AGS holdings by investor category, quarterly since 2003; Mar-2026: AUD 469bn = 50.9% of AUD 922bn outstanding)* + ✅ **IIP stocks** *(ABS IIP 33 series — Net IIP / FA / FL / Direct Inv / Portfolio Inv / Other Inv / Derivatives / Reserve Asset sub-decomp, quarterly since 1988-Q3; Mar-2026: Net IIP +AUD 707bn net liability, Total FL AUD 5.27tn, Gross External Debt AUD 2.76tn)* | ✅ FX / REER *(RBA F11.1 — AUD/USD + TWI + 17 AUD crosses, 19 series; daily via CSV snapshot)* |
| **Policy** | ✅ Demand Trans *(RBA D2 — 14 credit aggregates: owner-occupier housing / investor housing / business / personal / total credit / narrow credit × NSA+SA; monthly. Owner-occ credit Apr-2026: AUD 1,747bn; investor housing: AUD 863bn. + **APRA MADIS by-bank (CBA/WBC/NAB/ANZ) owner-occ + investor housing loan books, 8 series monthly since 2019-03, NEW 2026-07-14** — loan books not rates, no system-total published)* | ✅ Balance Sheets *(RBA E1+E2 — 16 series: household total assets/liabilities/net worth + business loans/liabilities + 8 gearing ratios. Household net worth Q4-2025: AUD 17,783bn; debt-to-income: 177.0%; housing-DTI: 133.7%. + **Cotality daily HVI 6 + monthly HVI 10 (NEW 2026-07-14, 5-8 capitals + aggregate) + SQM vacancy rates 9 (NEW 2026-07-14, 8 capitals + national)**)* | ✅ Fin Conditions *(RBA F1+F2 — cash rate, BBSW 1m/3m/6m, OIS 1m/3m/6m, govt bonds 2y/3y/5y/10y; 11 series; daily via CSV snapshot)* + *(AOFM term premium 30 series — FY/TP/RNY × 1Y..10Y daily since 1992; 10Y Mar-2026: 95bp)* + *(AOFM turnover 67 series — TB+TIB secondary by region/tenor/category)* | ✅ Policy Reaction *(RBA D3 — M1/M3/Broad money/Money base NSA+SA, 14 series; monthly via CSV snapshot)* + *(RBA A2 — Cash Rate Target + administered rates event log, 4 series. Cash Rate Target May-2026: 4.35%)* |

### 7.8 New Zealand (NZ)

| Engine | A | B | C | D |
|---|:---:|:---:|:---:|:---:|
| **Growth** | ❌ | ❌ | ❌ | ⚠️ Macro Core *(FRED NZ Unemployment + IIP + Stats NZ CPI)* |
| **Inflation** | ❌ | ❌ | ❌ | ⚠️ CPI *(FRED OECD CPI + Stats NZ release scraper)* |
| **External** | ❌ | ❌ | ❌ | ❌ |
| **Policy** | ❌ | ❌ | ❌ | ⚠️ Policy *(FRED NZ govt yield + OCR — partial)* |

### 7.8a Germany (DE)

| Engine | A | B | C | D |
|---|:---:|:---:|:---:|:---:|
| **Growth** | ❌ | ❌ | ❌ | ⚠️ Macro Core *(FRED Real GDP + OECD Unemployment + IIP)* |
| **Inflation** | ❌ | ❌ | ❌ | ⚠️ CPI *(FRED CPI YoY)* |
| **External** | ❌ | ❌ | ❌ | ❌ |
| **Policy** | ❌ | ❌ | ❌ | ⚠️ Policy *(FRED Bund yield — partial)* |

### 7.9 China (CN)

| Engine | A | B | C | D |
|---|:---:|:---:|:---:|:---:|
| **Growth** | ❌ | ❌ | ❌ | ❌ |
| **Inflation** | ❌ | ❌ | ❌ | ❌ |
| **External** | ❌ | ❌ | ❌ | ❌ |
| **Policy** | ❌ | ❌ | ❌ | ❌ |

### 7.10 Hong Kong (HK)

Updated 2026-06-03 after HKMA v2 load (29 indicators, 192k obs; FX history back to 1981, HIBOR to 1996).

| Engine | A | B | C | D |
|---|:---:|:---:|:---:|:---:|
| **Growth** | ❌ | ❌ | ❌ | ❌ *needs C&SD: GDP, unemployment* |
| **Inflation** | ❌ | ❌ | ❌ | ❌ *needs C&SD: CCPI* |
| **External** | ❌ | ❌ | ⚠️ Capital Acc *(HKMA FX Reserves Total)* | ⚠️ FX/REER *(HKD vs USD/EUR/GBP/JPY/CNY/SGD + NEERI 2020 ×3 weights)* |
| **Policy** | ⚠️ Demand Trans *(HKMA Total Loans for use in HK)* | ⚠️ Balance Sheets *(NPL ratio, classified loans, overdue+rescheduled)* | ⚠️ Fin Conditions *(HIBOR ON/1W/1M/3M/6M/12M + Composite IR)* | ⚠️ Policy *(agg bal, EFBN, CI, M1/M2/M3, currency circ — LERS means 4.4 is monetised via reserves)* |

HK score: **0 ✅ / 7 ⚠️ / 9 ❌** (was 0/1/15 before v2). All right-side clusters (External, Policy) now have at least one indicator; left-side (Growth, Inflation) blocked on Census & Statistics Department which is a separate vendor scope.

### 7.11 Singapore (SG)

| Engine | A | B | C | D |
|---|:---:|:---:|:---:|:---:|
| **Growth** | ❌ | ❌ | ❌ | ❌ |
| **Inflation** | ❌ | ❌ | ❌ | ❌ |
| **External** | ❌ | ❌ | ❌ | ❌ |
| **Policy** | ❌ | ❌ | ❌ | ❌ |

### 7.12 India (IN)

Scoping plan landed 2026-06-10: [`india/in_coverage_plan.md`](india/in_coverage_plan.md) — dual-track DBIE + CIMS plus MOSPI / DGCIS / MoF / DPIIT / CCIL / NSDL / BIS / UPAg / RBI Bulletin cascade.

**Prod-live 2026-06-19 (Track A Phase G complete):** 15 prod fetchers at `scripts/econ/in/{vendor}/` — IMD · BIS · FAO · RBI FX Reserves · RBI Key Rates · MOSPI CPI/IIP · DPIIT WPI/8-Core · CGA · DGCIS · UPAg IMC/MSP/AIAPY · MOSPI NAS GDP · **RBI Bulletin (23 tables incl. T34 NRI Deposits, T40 BoP)**. Two cadence-split orchestrators: `scripts/econ/in/in_daily.py` (frequency_scope=["DAILY"]) + `scripts/econ/in/in_monthly.py` (frequency_scope=["MONTHLY","WEEKLY","DAILY","QUARTERLY","ANNUAL"]). Quarterly/annual fetchers (`mospi_nas_gdp`, `upag_msp`, `upag_aiapy`) folded into monthly 2026-06-19; `in_quarterly.py` deleted; `scripts/imdr_quarterly.py` has no India entry. Wired into `scripts/imdr_daily.py:PIPELINES` + `scripts/imdr_monthly.py:PIPELINES` 2026-06-19. Ops runbook: [`india/india_prod_pipeline.md`](india/india_prod_pipeline.md).

**rbi_bulletin.py requires headed Chrome** (TSPD anti-bot) — monthly orchestrator must run on a display-capable host.

| Engine | A | B | C | D |
|---|:---:|:---:|:---:|:---:|
| **Growth** | ⚠️ Private Demand *(MOSPI NAS PFCE Q + AIAPY consumption-side proxies)* | ⚠️ Fiscal Demand *(CGA 30 line items; MOSPI NAS GFCE Q)* | ✅ External Demand *(DGCIS multi-month: 198 × 30.9k obs HS-2 Apr 2013→Mar 2026 + Bulletin T32 Foreign Trade)* | ✅ Macro Core *(MOSPI IIP + DPIIT 8-Core + MOSPI NAS GDP + Bulletin IIP T23 + FRED)* |
| **Inflation** | ⚠️ Input Costs *(DPIIT 8-Core fuel/energy + UPAg MSP + UPAg IMC mandi prices)* | ✅ Producer Prices *(DPIIT WPI 8 × 169mo + Bulletin WPI T22 48 sub-aggregates)* | ❌ Domestic Costs *(wages — Labour Bureau corp-firewall blocked)* | ✅ CPI Pressure *(MOSPI CPI 78 + Bulletin T19C 28 + FRED OECD MEI + FAO FPI)* |
| **External** | ⚠️ Terms of Trade *(derivable from DGCIS + Bulletin T32)* | ✅ Current Acc *(Bulletin T40 BoP: Merchandise / Invisibles / Services / Software-Services / etc. — Credit+Debit+Net × 2 quarters)* | ✅ Capital Acc *(RBI DBIE FX reserves weekly 2015→ + Bulletin T33 dual-unit)* | ✅ FX/REER *(BIS NEER+REER 1994→ + Bulletin T37 + FRED DEXINUS)* |
| **Policy** | ❌ Demand Trans *(needs A7 DBIE Sectoral Deployment)* | ⚠️ Balance Sheets *(BIS DSR + Credit-to-GDP Q 1951→ + Bulletin T2 RBI BS; A7 BSR + NBFC pending)* | ⚠️ Fin Conditions *(RBI DBIE WACR daily + Bulletin T27 Call Money daily + FRED OECD Call Money 1990→)* | ✅ Policy Reaction *(RBI DBIE Repo + SDF + Reverse Repo + CRR + SLR + BIS CBPOL + Bulletin T6 Money Stock + T11 Reserve Money)* |

**Cluster 4 (agriculture)** — full coverage via **UPAg**: A26 ✅ AIAPY (324 × 15,030 obs, **1966-67 → 2025-26 = 60 FYs**); A31 ✅ MSP (28 × 353); A33 ✅ IMC mandi prices (16 × 128, Agmarknet wholesale). Closes Cluster 4 input-price + output-volume + market-price axes that were previously corp-firewall blocked at agricoop.gov.in / cacp.dacnet.nic.in / agmarknet.gov.in. **Plus (PRE-PROD, 2026-06-22)**: comprehensive daily per-mandi price source via data.gov.in OGD Agmarknet REST API (~22k records/day; dedicated `econ.fact_india_mandi` star schema; migration 104 drafted, NOT applied; `playground/econ/in/ogd/ogd_mandi.py` not yet wired) — see [`india/india_mandi_prices.md`](india/india_mandi_prices.md).

IN cell coverage (prod-live 2026-06-19): **8 ✅ + 6 ⚠ + 2 ❌** (was 1 ✅ / 4 ⚠ / 11 ❌ pre-session). **The BoP T40 path via RBI Bulletin eliminates the A5-A7 SAP-BO iframe requirement for the BoP cell**. Remaining ❌ cells: 2.3 Domestic Costs (wages — Labour Bureau corp-firewall blocked) · 4.1 Demand Transmission (needs A7 DBIE Sectoral Deployment, or alt path TBD).

### 7.13 South Korea (KR)

KOSIS OpenAPI went live 2026-06-03 PM (TLS 1.2 pinned, 40k-cell cap). Expanded 2026-06-05 across 4 rounds to **164 indicators / 47,748 obs end-to-end** across 20 KOSIS fetchers + 4 FRED Korea rate series + 4 REB-direct housing. KOSIS mirrors BOK ECOS 1:1 with `tblId = DT_{STAT_CODE}`, so most Korea series are reachable without the still-blocked ECOS direct API.

**Production status (2026-06-05):** All KOSIS + REB cells below are auto-loaded via the prod orchestrators — no manual load step. Weekly housing cells load via `scripts/imdr_weekly.py` → `kr_weekly`; all other cells load via `scripts/imdr_monthly.py` → `kr_monthly`. Ops runbook: [korea/korea_prod_pipeline.md](korea/korea_prod_pipeline.md).

| Engine | A | B | C | D |
|---|:---:|:---:|:---:|:---:|
| **Growth** | ✅ Private Demand *(KOSTAT Retail Sales × 7 types × Value+SA, monthly 2000→)* | ✅ Fiscal Demand *(BOK 200Y154 Public Sector — Revenue / Expenditure / Net Lending / Saving + Direct/Indirect Taxes, annual 2007→)* | ✅ External Demand *(BOK Trade Value+Volume indices monthly 1988→; BOK BoP goods X/M monthly 1980→; GDP exports/imports QoQ+YoY quarterly 1961→)* | ✅ Macro Core *(BOK GDP-Q × 12 components 1961→; KOSTAT EAPS labour 8 series 1999-06→)* |
| **Inflation** | ✅ Input Costs *(BOK Import Price All-items × Won+USD basis, monthly 1980→; CPI Fresh-food + BOK PPI Mining/Utilities sub-cuts)* | ✅ Producer Prices *(BOK PPI Total + 5 sectors, monthly 1990→)* | ✅ Domestic Costs *(KOSTAT Wages — national avg level + YoY growth, annual 2011→)* | ✅ CPI Pressure *(KOSTAT CPI Headline + Living + Fresh-food + 2 core × MoM/YoY/YTD, monthly 2000→)* |
| **External** | ✅ Terms of Trade *(BOK Net Barter + Income ToT, monthly 1988→)* | ✅ Current Acc *(BOK BoP CA + Goods/Services/Primary/Secondary income balances + sub-cuts, monthly 1980→)* | ✅ Capital Acc *(BOK BoP FA + DI/PI/Deriv/OI/Reserves × net/assets/liab + E&O, monthly 1980→)* | parked *(3.4 FX/REER — user-deferred this session; route via Citi spot + FRED BIS REER/NEER)* |
| **Policy** | ✅ Demand Trans *(BOK Lending Attitude Survey × Bank Overall/LargeCorp/SME/HH/Housing, quarterly 2003→; BOK Household Loans by purpose monthly 2003→; REB housing)* | ✅ Balance Sheets *(BOK Household Credit total + Loans quarterly 2002→; FSS Bank Total Loans + NPL Level + NPL Ratio quarterly — FSS data stale to 2016)* | ⚠️ Fin Conditions *(BOK bank deposit + CD 91d + Repo + FinDebent + FinDebent rates monthly 1996→; BOK Base Rate confirmed NOT on KOSIS — KOSIS 금리 branch has only deposit/loan rates; Base Rate is in ECOS only, not mirrored to KOSIS OpenAPI; covered in cell 4.4 via BIS CBPOL)* | ✅ Policy Reaction *(BIS CBPOL `BIS.POLICY_RATE.KR` daily 1999-05-06→ **[BOK Base Rate — primary]**; FRED Call Money 1991→; 3M Interbank 1991→; 10Y Govt 2000→. FRED Discount Rate deactivated 2026-06-16 — it was the BOK discount rate, not the Base Rate. Wired into `imdr_daily.py` + `kr_monthly.py` 2026-06-16, migration 102.)* |

KR went from **1 ✅ / 6 ⚠️ / 9 ❌** to **15 ✅ / 1 ⚠️ / 1 parked** in one day across 21 fetchers + 172 KR-specific indicators, plus the BIS CBPOL Base Rate fetcher added 2026-06-16. The remaining ⚠️ is 4.3 Financial Conditions (KOSIS bank rates are deposit-side only; the BOK Base Rate proper is now correctly on BIS CBPOL in cell 4.4, not FRED). The parked cell is 3.4 FX/REER (user-deferred; route via Citi spot + FRED BIS REER when needed). **All other 15 cells ✅ in `econ.dim_indicator`.** Cell 4.4 now carries the real BOK Base Rate (BIS.POLICY_RATE.KR, id 1435).

The 2026-06-05 gap-closure round added 5 more fetchers (M-aggregates, IIP+Capacity Util, Consumer Survey, BSI Realised+Outlook, Corporate Financial Ratios) — see §7.13 grid entries for `[CCI, IIP, BSI Mfg, Mfg Capacity Util, Corp ratios, M2/Lf]`. The 2026-06-16 round added the BIS CBPOL policy-rate fetcher and deactivated the incorrectly-labelled FRED Discount Rate.

### 7.14 Taiwan (TW)

| Engine | A | B | C | D |
|---|:---:|:---:|:---:|:---:|
| **Growth** | ❌ | ❌ | ❌ | ❌ |
| **Inflation** | ❌ | ❌ | ❌ | ❌ |
| **External** | ❌ | ❌ | ❌ | ❌ |
| **Policy** | ❌ | ❌ | ❌ | ❌ |

### 7.15 Philippines (PH)

Source-catalogue scoped 2026-06-05: BSP (monetary/banking/FX) + PSA (CPI/national accounts/labour) + DBM/BTr (fiscal). No formal data API — BSP runs on SharePoint listing pages; PSA is XLSX/PDF. See [philippines/index.md](../econ/philippines/index.md).

| Engine | A | B | C | D |
|---|:---:|:---:|:---:|:---:|
| **Growth** | ❌ | ❌ | ❌ | ❌ |
| **Inflation** | ❌ | ❌ | ❌ | ❌ |
| **External** | ❌ | ❌ | ❌ | ❌ |
| **Policy** | ❌ | ❌ | ❌ | ❌ |

### 7.16 Thailand (TH)

Source-catalogue scoped 2026-06-05: BoT REST JSON API (free key, rates/FX/monetary/BoP/banking) + NSO Thailand XLSX (CPI/labour/national accounts). BoT is cleanest API in ASEAN after Singapore + Malaysia. See [thailand/index.md](../econ/thailand/index.md).

| Engine | A | B | C | D |
|---|:---:|:---:|:---:|:---:|
| **Growth** | ❌ | ❌ | ❌ | ❌ |
| **Inflation** | ❌ | ❌ | ❌ | ❌ |
| **External** | ❌ | ❌ | ❌ | ❌ |
| **Policy** | ❌ | ❌ | ❌ | ❌ |

### 7.17 Indonesia (ID)

**Prod-promoted 2026-06-09 via `scripts/econ/id/id_monthly.py`; wired into `scripts/imdr_monthly.py:PIPELINES` 2026-06-09. `scripts.econ.id.bis.bis_indonesia` and `scripts.econ.id.bi.bi_srbi` registered in `scripts/imdr_daily.py:PIPELINES` for same-day capture of event-driven series (BI policy rate + SRBI auction yields).**
Source-catalogue scoped 2026-06-05; Phases A+B+C+C2+D+D2+D3+D4+D5+D6+F+G+H+I complete 2026-06-10 — **308 indicators × 114,106 observations live in `econ.fact_indicator`** (BPS 82 + BI 184 + BIS 6 + DJPPR 36). 28 prod fetchers: 10 BPS + 16 BI (9 SEKI + 3 Survey publications + SKDU macro + bank rates + SRBI auction + SBN position by holder) + 1 BIS SDMX + 1 DJPPR. Phase I (2026-06-10): BI SEKI IV.4 SBN position by holder — 19 indicators × 3,630 obs; 4 headline totals (SUN/ON/SPN/SBSN) + 8 ON bank-type holder decomp + 7 SPN holder decomp; monthly 2008-12→2026-05; reuses `bi_seki.py` (no new library). See [indonesia/index.md](../econ/indonesia/index.md), [prod-pipeline](../econ/indonesia/indonesia_prod_pipeline.md), [indicator-inventory](../econ/indonesia/indonesia_indicator_inventory.md), [coverage-plan](../econ/indonesia/id_coverage_plan.md), [bps_api_reference](../econ/indonesia/bps_api_reference.md), [_playground/bps.md](../econ/indonesia/_playground/bps.md), [_playground/bi.md](../econ/indonesia/_playground/bi.md), [_playground/bis.md](../econ/indonesia/_playground/bis.md).

`*` denotes partial coverage at the cell. **All 16 cells covered; 13 of 16 are full ✅.** Three cells still ⚠ partial:
- 2.1 Input Costs — BPS import prices only (2/7 sub-bullets)
- 3.1 Terms of Trade — NBToT + Income ToT derivable in analytics (2/5 in DB)
- 3.4 FX/REER — NEER+REER+reserves; intervention proxy + composition derivable (8/11)

| Engine | A | B | C | D |
|---|:---:|:---:|:---:|:---:|
| **Growth** (1.1 Private / 1.2 Fiscal / 1.3 External / 1.4 Macro) | ✅ | ✅ | ✅ | ✅ |
| **Inflation** (2.1 Input / 2.2 Producer / 2.3 Domestic / 2.4 CPI) | ⚠* | ✅ | ✅ | ✅ |
| **External** (3.1 ToT / 3.2 CA / 3.3 FA / 3.4 FX) | ⚠* | ✅ | ✅ | ⚠* |
| **Policy** (4.1 Demand / 4.2 BS / 4.3 FinCond / 4.4 PolReaction) | ✅ | ✅ *(added: BI SEKI IV.4 SBN position by holder 2026-06-10 — 19 indicators; bank-type decomp for ON bonds + SPN T-bills)* | ✅ *(added: BI SRBI 6M/9M/12M auction yields 2026-06-10)* | ✅ |

---

## 8. Notes on regime-dependence

Same cluster, different country choices:

- **2.4 CPI Pressure**:
  - US → headline CPI (CPIAUCSL) + core CPI (CPILFESL) + sticky/flexible split (Atlanta Fed)
  - EU → HICP + HICP ex-energy-food + core
  - IN → CPI Combined (RBI Bulletin T19C) — rural + urban dual split
  - JP → headline CPI + core CPI + core-core CPI
  - KR → CPI from MODS (Statistics Korea)

- **4.4 Policy Reaction**:
  - US → Fed funds target + IOER + reverse repo rate
  - EU → ECB deposit rate + MRO + 2-week MRO + lending facility
  - JP → BoJ policy rate + JGB YCC band (when active)
  - HK → no policy rate (LERS) → HKMA aggregate balance is the regime variable
  - CN → 7-day reverse repo rate + MLF rate + LPR-1Y + LPR-5Y
  - IN → RBI repo rate + SDF + MSF

- **3.4 FX / REER**:
  - G10 → spot + DXY + BIS NEER + BIS REER
  - APAC EM → spot + NDF curve (KRW, INR, TWD, PHP, IDR) + central-bank intervention indicator
  - CN → onshore CNY + CNH + PBOC fixing midpoint

The wiring map abstracts these so the schema stays uniform — country-specific picks live in `dim_indicator.imdr_code` + `country_id`.

---

## 8.1 Known FRED-code gaps to revisit

Five candidate IDs failed FRED `/series` validation during the v2+IIP load. They name a real concept but the exact ID is wrong; finding the right code is a follow-up.

| Concept | Bad ID we tried | Status | Next step |
|---|---|---|---|
| AU CPI YoY (OECD-mirror) | `CPALTT01AUM659N` | Dropped | Search `australia cpi` on FRED — likely a `CPALCY01AUM659N` or `CPALTT01AUQ659N` (AU CPI is quarterly) |
| EZ CPI YoY (OECD-mirror) | `CPALTT01EZM659N` | Dropped | Use `CP0000EZ19M086NEST` (Eurostat HICP, already in seed) or find correct OECD code |
| CH Unemployment | `LRHUTTTTCHM156S` | Dropped | CH is not in OECD harmonised series; pivot to Swiss SECO source |
| CH Real GDP | `NGDPRSAXDCCHQ` | Dropped | Use BIS or SECO source; defer |
| NZ Real GDP | `NZLGDPRQDSMEI` | Dropped | NZ Real GDP on FRED via `NAEXKP01NZQ189S` (CVM) or use `NZGDP` codes |

Plus one transient `NFCIRISK` 500 (Chicago Fed NFCI sub-index; intermittent FRED outage, retry).

**~~Fetcher-stuck dim rows~~** — RESOLVED 2026-06-04. All 3 were officially discontinued by FRED (real cause; not a fetch bug). Substitutions:

| imdr_code | Old (discontinued) | New | Status |
|---|---|---|---|
| `FRED.BOP.CURRENT_ACCT.US` | `BOPBCA` (discontinued 2014) | `IEABC` (Balance on current account, quarterly) | ✅ 24 obs (2020-2025) |
| `FRED.BALANCE_SHEET.FED_MBS_HOLD.US` | `MBST` (discontinued 2018) | `WSHOMCB` (SOMA MBS holdings, weekly H.4.1) | ✅ 335 obs (2020-2026) |
| `FRED.SENTIMENT.CFSI.US` | `CFSI` (discontinued 2016) | dropped — covered by KCFSI + STLFSI4 + ANFCI | n/a |

**FRED ops note**: today's session hit `HTTP 429 Too Many Requests` after consecutive validate + fetch runs. Fixed by wiring the connector for **dual-key rotation** (`IMDR_ECON_FRED_KEY` + `IMDR_ECON_FRED_KEY2`, round-robin per request) + bumping the throttle from 0.6s → 0.5s (60 req/min/key vs FRED's 120/min/key cap). Post-fix run was clean — 0 429s.

---

For maintenance rules (when to flip ❌ → ⚠️ → ✅, when to add a new country vs reshape the map), see [onboarding_new_country.md §5](onboarding_new_country.md#step-5--reconcile-against-the-wiring-map).
