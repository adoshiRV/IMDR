# Macro Economy Wiring Map

**Generic clusters. Choose indicators by country and regime — the wiring stays broadly stable.**

> Read the map as clusters, not a checklist in isolation: identify the active loop first, then pick the country-specific data that best represents it. The four main loops are **Growth → Inflation → External/FX → Policy Transmission**. Each loop feeds the next; feedback runs in both directions.

This file is the **coverage target** for `econ.dim_indicator`. Every cluster below should resolve to at least one indicator per country we care about. The per-country tracker in §6 is updated as fetchers + sign-offs land.

- **Onboarding playbook**: [onboarding_new_country.md](onboarding_new_country.md) — 5-step workflow with vendor cascade, build order, identity checks, quality bar, ❌→⚠→✅ promotion rules.
- **Indicator catalogue**: [country_econ_blueprint.md](country_econ_blueprint.md) — country-agnostic master list of series per cluster.
- **Schema + build log**: [economics_data_ingest.md](economics_data_ingest.md) — pipeline + per-vendor build state.
- **Date**: 2026-06-10 (ID SRBI added: **292 indicators / 110,961 obs** for ID alone — 289 econ indicators + 3 SRBI rates; **AU 447 indicators / 359,245 obs — 15 of 16 cells ✅** (+11 this pass: Cotality 6 daily HVI + ABS BA value 2 + RBA F15 REER 3); total across all countries updated)

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
| AU | ❌ | ❌ | ❌ | ❌ |
| NZ | ❌ | ❌ | ❌ | ❌ |
| CN | ❌ | ❌ | ❌ | ❌ |
| HK | ❌ | ❌ | ❌ | ❌ |
| SG | ❌ | ❌ | ❌ | ❌ |
| IN | ❌ | ❌ | ❌ | ❌ |
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
| AU | ❌ | ❌ | ❌ | ❌ |
| NZ | ❌ | ❌ | ❌ | ⚠️ (Stats NZ CPI release) |
| CN | ❌ | ❌ | ❌ | ❌ |
| HK | ❌ | ❌ | ❌ | ❌ |
| SG | ❌ | ❌ | ❌ | ❌ |
| IN | ❌ | ❌ | ❌ | ⚠️ (RBI Bulletin T19C) |
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
| AU | ❌ | ❌ | ❌ | ❌ |
| NZ | ❌ | ❌ | ❌ | ❌ |
| CN | ❌ | ❌ | ❌ | ❌ |
| HK | ❌ | ❌ | ❌ | ❌ |
| SG | ❌ | ❌ | ❌ | ❌ |
| IN | ❌ | ❌ | ⚠️ (RBI FX reserves) | ❌ |
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
| AU | ❌ | ❌ | ❌ | ❌ |
| NZ | ❌ | ❌ | ❌ | ❌ |
| CN | ❌ | ❌ | ❌ | ❌ |
| HK | ❌ | ❌ | ❌ | ⚠️ (HKMA aggregate balance + EFBN) |
| SG | ❌ | ❌ | ❌ | ❌ |
| IN | ❌ | ❌ | ⚠️ (RBI call money) | ❌ |
| KR | ✅ (BOK Lending Attitude Survey + Household Loans monthly + REB housing) | ✅ (BOK HH Credit + Corp financial ratios × 13 + FSS NPL legacy) | ⚠️ (KOSIS bank deposit + CD 91d + Repo rates — Base Rate via FRED proxies cell 4.4 instead) | ✅ (FRED KR Discount Rate / Call / 3M Interbank / 10Y Govt + BOK M2/Lf monetary aggregates) |
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

Updated 2026-06-10: **447 indicators / 359,245 obs DB-LIVE** (manual load). **15 of 16 cells ✅**. ABS 17 fetchers / 20 dataflows (178 indicators incl. IIP + BA value+count) + RBA 8 fetchers via CSV snapshot (103 indicators incl. TIB + I2 ICP + F15 REER) + AOFM 5 fetchers (157 indicators) + Cotality (new vendor, 6 daily HVI) + FRED-mirror (3). Phase G blocker lifted. Second-most-populated country after Indonesia.

| Engine | A | B | C | D |
|---|:---:|:---:|:---:|:---:|
| **Growth** | ✅ Private Demand *(ABS Retail Trade 10 series)* | ✅ Fiscal Demand *(AOFM portfolio aggregate 16 series — TB+TIB+TN outstanding monthly since 2003; AOFM issuance/buybacks 10 series — monthly gross issuance + buyback flows)* | ✅ External Demand *(ABS BOP 14 + BOP_GOODS 7 + ITPI 6 + ANA_EXP 10)* | ✅ Macro Core *(ABS ANA_AGG GDP chain-vol SA + LF unemployment/participation/employed + ANA_EXP expenditure decomp + Job Vacancies 3)* |
| **Inflation** | ✅ Input Costs *(ABS ITPI import-side SITC 1-digit — 18 indicators: food/beverages-tobacco/crude materials/energy/fats-oils/chemicals/mfg-by-material/machinery-transport/misc-manufactures × Index+YoY. Import crude materials YoY Q1-2026: +4.5%; energy: +0.7%)* | ✅ Producer Prices *(ABS PPI_FD 3 — final demand, TSEST=TOTXE)* | ✅ Domestic Costs *(ABS WPI 6 — OHRPEB, TOT level, NSA-only — SA not published)* | ✅ CPI Pressure *(ABS CPI 16 — headline Q NSA + Trimmed Mean M + Weighted Median M + subcategories)* |
| **External** | ❌ | ❌ 3.1 ToT *(derivable from ITPI export/import ratio — analytics-only, no fetcher)* | ✅ Current Account *(ABS BOP 14 — CA + primary + secondary + capital + financial account sub-items)* + ✅ Capital Account *(AOFM foreign holdings 34 series — non-resident AGS holdings by investor category, quarterly since 2003; Mar-2026: AUD 469bn = 50.9% of AUD 922bn outstanding)* + ✅ **IIP stocks** *(ABS IIP 33 series — Net IIP / FA / FL / Direct Inv / Portfolio Inv / Other Inv / Derivatives / Reserve Asset sub-decomp, quarterly since 1988-Q3; Mar-2026: Net IIP +AUD 707bn net liability, Total FL AUD 5.27tn, Gross External Debt AUD 2.76tn)* | ✅ FX / REER *(RBA F11.1 — AUD/USD + TWI + 17 AUD crosses, 19 series; daily via CSV snapshot)* |
| **Policy** | ✅ Demand Trans *(RBA D2 — 14 credit aggregates: owner-occupier housing / investor housing / business / personal / total credit / narrow credit × NSA+SA; monthly. Owner-occ credit Apr-2026: AUD 1,747bn; investor housing: AUD 863bn)* | ✅ Balance Sheets *(RBA E1+E2 — 16 series: household total assets/liabilities/net worth + business loans/liabilities + 8 gearing ratios. Household net worth Q4-2025: AUD 17,783bn; debt-to-income: 177.0%; housing-DTI: 133.7%)* | ✅ Fin Conditions *(RBA F1+F2 — cash rate, BBSW 1m/3m/6m, OIS 1m/3m/6m, govt bonds 2y/3y/5y/10y; 11 series; daily via CSV snapshot)* + *(AOFM term premium 30 series — FY/TP/RNY × 1Y..10Y daily since 1992; 10Y Mar-2026: 95bp)* + *(AOFM turnover 67 series — TB+TIB secondary by region/tenor/category)* | ✅ Policy Reaction *(RBA D3 — M1/M3/Broad money/Money base NSA+SA, 14 series; monthly via CSV snapshot)* + *(RBA A2 — Cash Rate Target + administered rates event log, 4 series. Cash Rate Target May-2026: 4.35%)* |

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

Scoping plan landed 2026-06-10: [`india/in_coverage_plan.md`](india/in_coverage_plan.md) — dual-track DBIE + CIMS (per user direction) plus MOSPI / DGCIS / MoF / DPIIT / CCIL / NSDL / BIS cascade.

**Live 2026-06-10:** BIS + FRED + RBI DBIE India packages shipped — **26 indicators × 39,569 obs** in `econ.fact_indicator`. BIS: NEER/REER broad, Private-NFS DSR, Credit-to-GDP ratio + gap, RBI repo daily (1946→). FRED: CPI YoY + level (1990→), IIP (1994→2023), Real GDP annual (PWT 1990→), Call money rate (1990→), INR/USD daily + monthly (1990→). RBI DBIE: FX reserves total + FCA + Gold + SDR + IMF position (weekly, 2015→) plus 8-row Key Rates snapshot (Repo / SDF / Reverse Repo / CRR / SLR + CPI/WPI YoY latest + WACR). First IN data live in DB; DBIE bootstrap-auth client at [`src/imdr/domains/econ/rbi_dbie.py`](../../src/imdr/domains/econ/rbi_dbie.py).

| Engine | A | B | C | D |
|---|:---:|:---:|:---:|:---:|
| **Growth** | ❌ | ❌ | ❌ | ⚠️ Macro Core *(FRED IIP 1994→2023 + Real GDP PWT annual 1990→2023)* |
| **Inflation** | ❌ | ❌ | ❌ | ⚠️ CPI *(FRED OECD MEI YoY + level 1990→ + RBI DBIE WPI/CPI latest snapshot + RBI Bulletin T19C)* |
| **External** | ❌ | ❌ | ✅ Capital Acc *(RBI DBIE FX reserves — TR + FCA + Gold + SDR + IMF, weekly 2015→)* | ⚠️ FX/REER *(BIS NEER + REER broad M, 1994→ + FRED DEXINUS daily 1990→)* |
| **Policy** | ❌ | ⚠️ Balance Sheets *(BIS Private-NFS DSR + Credit-to-GDP ratio + gap, Q, 1951→)* | ⚠️ Fin Conditions *(RBI DBIE WACR daily + FRED OECD Call Money 1990→ + RBI Bulletin T27)* | ✅ Policy Reaction *(RBI DBIE Repo + SDF + Reverse Repo + CRR + SLR event-stamped + BIS CBPOL daily 1946→)* |

### 7.13 South Korea (KR)

KOSIS OpenAPI went live 2026-06-03 PM (TLS 1.2 pinned, 40k-cell cap). Expanded 2026-06-05 across 4 rounds to **164 indicators / 47,748 obs end-to-end** across 20 KOSIS fetchers + 4 FRED Korea rate series + 4 REB-direct housing. KOSIS mirrors BOK ECOS 1:1 with `tblId = DT_{STAT_CODE}`, so most Korea series are reachable without the still-blocked ECOS direct API.

**Production status (2026-06-05):** All KOSIS + REB cells below are auto-loaded via the prod orchestrators — no manual load step. Weekly housing cells load via `scripts/imdr_weekly.py` → `kr_weekly`; all other cells load via `scripts/imdr_monthly.py` → `kr_monthly`. Ops runbook: [korea/korea_prod_pipeline.md](korea/korea_prod_pipeline.md).

| Engine | A | B | C | D |
|---|:---:|:---:|:---:|:---:|
| **Growth** | ✅ Private Demand *(KOSTAT Retail Sales × 7 types × Value+SA, monthly 2000→)* | ✅ Fiscal Demand *(BOK 200Y154 Public Sector — Revenue / Expenditure / Net Lending / Saving + Direct/Indirect Taxes, annual 2007→)* | ✅ External Demand *(BOK Trade Value+Volume indices monthly 1988→; BOK BoP goods X/M monthly 1980→; GDP exports/imports QoQ+YoY quarterly 1961→)* | ✅ Macro Core *(BOK GDP-Q × 12 components 1961→; KOSTAT EAPS labour 8 series 1999-06→)* |
| **Inflation** | ✅ Input Costs *(BOK Import Price All-items × Won+USD basis, monthly 1980→; CPI Fresh-food + BOK PPI Mining/Utilities sub-cuts)* | ✅ Producer Prices *(BOK PPI Total + 5 sectors, monthly 1990→)* | ✅ Domestic Costs *(KOSTAT Wages — national avg level + YoY growth, annual 2011→)* | ✅ CPI Pressure *(KOSTAT CPI Headline + Living + Fresh-food + 2 core × MoM/YoY/YTD, monthly 2000→)* |
| **External** | ✅ Terms of Trade *(BOK Net Barter + Income ToT, monthly 1988→)* | ✅ Current Acc *(BOK BoP CA + Goods/Services/Primary/Secondary income balances + sub-cuts, monthly 1980→)* | ✅ Capital Acc *(BOK BoP FA + DI/PI/Deriv/OI/Reserves × net/assets/liab + E&O, monthly 1980→)* | parked *(3.4 FX/REER — user-deferred this session; route via Citi spot + FRED BIS REER/NEER)* |
| **Policy** | ✅ Demand Trans *(BOK Lending Attitude Survey × Bank Overall/LargeCorp/SME/HH/Housing, quarterly 2003→; BOK Household Loans by purpose monthly 2003→; REB housing)* | ✅ Balance Sheets *(BOK Household Credit total + Loans quarterly 2002→; FSS Bank Total Loans + NPL Level + NPL Ratio quarterly — FSS data stale to 2016)* | ⚠️ Fin Conditions *(BOK bank deposit + CD 91d + Repo + FinDebent + FinDebent rates monthly 1996→; BOK Base Rate ❌ on KOSIS — see 4.4 fallback)* | ✅ Policy Reaction *(FRED Korea Discount Rate 1990→; Call Money 1991→; 3M Interbank 1991→; 10Y Govt 2000→ — covers cell 4.4 via OECD-mirror feeds. Citi BENCH_RATES catalogue has no KR — only 10 entries ECB/FED/JPY/UK/US — gap documented for future Citi-side addition)* |

KR went from **1 ✅ / 6 ⚠️ / 9 ❌** to **15 ✅ / 1 ⚠️ / 1 parked** in one day across 21 fetchers + 172 KR-specific indicators. The remaining ⚠️ is 4.3 Financial Conditions (KOSIS bank rates are deposit-side only; the BOK Base Rate proper is on FRED via cell 4.4). The parked cell is 3.4 FX/REER (user-deferred; route via Citi spot + FRED BIS REER when needed). **All other 15 cells now ✅ in `econ.dim_indicator`.**

The 2026-06-05 gap-closure round added 5 more fetchers (M-aggregates, IIP+Capacity Util, Consumer Survey, BSI Realised+Outlook, Corporate Financial Ratios) — see §7.13 grid entries for `[CCI, IIP, BSI Mfg, Mfg Capacity Util, Corp ratios, M2/Lf]`.

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

**Prod-promoted 2026-06-09 via `scripts/econ/id/id_monthly.py`; wired into `scripts/imdr_monthly.py:PIPELINES` 2026-06-09. `scripts.econ.bis.bis_indonesia` and `scripts.econ.bi.bi_srbi` registered in `scripts/imdr_daily.py:PIPELINES` for same-day capture of event-driven series (BI policy rate + SRBI auction yields).**
Source-catalogue scoped 2026-06-05; Phases A+B+C+C2+D+D2+D3+D4+D5+D6+F+G+H complete 2026-06-10 — **289 indicators × 110,476 observations live in `econ.fact_indicator`** (BPS 82 + BI 165 + BIS 6 + DJPPR 36). 27 prod fetchers: 10 BPS + 15 BI (9 SEKI + 3 Survey publications + SKDU macro + bank rates + SRBI auction) + 1 BIS SDMX + 1 DJPPR. See [indonesia/index.md](../econ/indonesia/index.md), [prod-pipeline](../econ/indonesia/indonesia_prod_pipeline.md), [indicator-inventory](../econ/indonesia/indonesia_indicator_inventory.md), [coverage-plan](../econ/indonesia/id_coverage_plan.md), [bps_api_reference](../econ/indonesia/bps_api_reference.md), [_playground/bps.md](../econ/indonesia/_playground/bps.md), [_playground/bi.md](../econ/indonesia/_playground/bi.md), [_playground/bis.md](../econ/indonesia/_playground/bis.md).

`*` denotes partial coverage at the cell. **All 16 cells covered; 13 of 16 are full ✅.** Three cells still ⚠ partial:
- 2.1 Input Costs — BPS import prices only (2/7 sub-bullets)
- 3.1 Terms of Trade — NBToT + Income ToT derivable in analytics (2/5 in DB)
- 3.4 FX/REER — NEER+REER+reserves; intervention proxy + composition derivable (8/11)

| Engine | A | B | C | D |
|---|:---:|:---:|:---:|:---:|
| **Growth** (1.1 Private / 1.2 Fiscal / 1.3 External / 1.4 Macro) | ✅ | ✅ | ✅ | ✅ |
| **Inflation** (2.1 Input / 2.2 Producer / 2.3 Domestic / 2.4 CPI) | ⚠* | ✅ | ✅ | ✅ |
| **External** (3.1 ToT / 3.2 CA / 3.3 FA / 3.4 FX) | ⚠* | ✅ | ✅ | ⚠* |
| **Policy** (4.1 Demand / 4.2 BS / 4.3 FinCond / 4.4 PolReaction) | ✅ | ✅ | ✅ *(added: BI SRBI 6M/9M/12M auction yields 2026-06-10)* | ✅ |

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
