# Macro Economy Wiring Map

**Generic clusters. Choose indicators by country and regime — the wiring stays broadly stable.**

> Read the map as clusters, not a checklist in isolation: identify the active loop first, then pick the country-specific data that best represents it. The four main loops are **Growth → Inflation → External/FX → Policy Transmission**. Each loop feeds the next; feedback runs in both directions.

This file is the **coverage target** for `econ.dim_indicator`. Every cluster below should resolve to at least one indicator per country we care about. The per-country tracker in §6 is updated as fetchers + sign-offs land.

- **Companion**: [economics_data_ingest.md](economics_data_ingest.md) — the schema, sources, and pipeline plan.
- **Date**: 2026-06-03 (updated after FRED v2+IIP + HKMA v2 — 199 indicators / 272,893 obs across 9 countries + HK; KOSIS OpenAPI live for KR)

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

## 5. How to use this map

1. **Identify the active loop.** Which engine is driving the trade thesis — growth slowdown, sticky inflation, BoP stress, policy pivot?
2. **Pick the cluster.** Within the active engine, which cell is most informative *for this country at this point in the cycle*? (E.g. for the US in 2026 you care about 1.4 + 2.4; for India you care about 3.4 + 4.4.)
3. **Choose indicators.** From the cluster's bullets, pick the country-specific series that most cleanly proxies the concept.
4. **Verify coverage.** §6 below tracks whether `econ.dim_indicator` has at least one indicator per (country, cluster).

The map is regime-agnostic — different countries lean on different bullets in the same cluster (e.g. **2.3 Domestic Costs**: US watches ECI + JOLTS quits, India watches WPI services component, Korea watches MOTIE wage tracker). The cell wiring stays stable; only the chosen indicator changes.

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
| KR | ❌ | ❌ | ❌ | ❌ |
| TW | ❌ | ❌ | ❌ | ❌ |

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
| KR | ❌ | ❌ | ❌ | ⚠️ (MODS press release PDFs — unparsed) |
| TW | ❌ | ❌ | ❌ | ❌ |

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
| KR | ❌ | ❌ | ❌ | ❌ |
| TW | ❌ | ❌ | ❌ | ❌ |

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
| KR | ❌ | ❌ | ❌ | ❌ |
| TW | ❌ | ❌ | ❌ | ❌ |

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
| **External** | ❌ Terms of Trade | ⚠️ Current Acc *(BOPBCA, BOPGSTB)* | ❌ Capital Acc | ⚠️ FX/REER *(DTWEXBGS, AFE, EME)* |
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

| Engine | A | B | C | D |
|---|:---:|:---:|:---:|:---:|
| **Growth** | ❌ | ❌ | ❌ | ⚠️ Macro Core *(FRED Real GDP + OECD Unemployment + IIP)* |
| **Inflation** | ❌ | ❌ | ❌ | ❌ AU CPI YoY code dropped by FRED validator — refetch with different ID |
| **External** | ❌ | ❌ | ❌ | ❌ |
| **Policy** | ❌ | ❌ | ❌ | ❌ |

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

| Engine | A | B | C | D |
|---|:---:|:---:|:---:|:---:|
| **Growth** | ❌ | ❌ | ❌ | ❌ |
| **Inflation** | ❌ | ❌ | ❌ | ⚠️ CPI *(RBI Bulletin T19C — combined rural+urban)* |
| **External** | ❌ | ❌ | ⚠️ Capital Acc *(RBI DBIE FX reserves, 5 components)* | ❌ |
| **Policy** | ❌ | ❌ | ⚠️ Fin Conditions *(RBI Bulletin T27 call money)* | ❌ |

### 7.13 South Korea (KR)

KOSIS OpenAPI went live 2026-06-03 PM (TLS 1.2 pinned, 40k-row cap). First fetcher `playground/econ/kosis/fetch_bop.py` covers BoP via `orgId=301`. KOSIS mirrors BOK ECOS 1:1 with `tblId = DT_{STAT_CODE}`, so most Korea series are reachable without the still-blocked ECOS direct API.

| Engine | A | B | C | D |
|---|:---:|:---:|:---:|:---:|
| **Growth** | ❌ *(KOSIS available — pending fetcher)* | ❌ *(KOSIS available)* | ❌ *(KOSIS available)* | ❌ *(KOSIS available for GDP / unemployment / IIP)* |
| **Inflation** | ❌ *(KOSIS available)* | ❌ *(KOSIS available)* | ❌ *(KOSIS available)* | ⚠️ CPI *(MODS press-release PDFs — raw on OneDrive, unparsed; + KOSIS available)* |
| **External** | ❌ *(KOSIS available)* | ⚠️ Current Acc *(KOSIS fetch_bop.py — BoP `orgId=301`)* | ⚠️ Capital Acc *(KOSIS fetch_bop.py — Financial Account `BOPF…` codes)* | ❌ *(KOSIS available for FX)* |
| **Policy** | ❌ | ❌ | ❌ *(KOSIS available for KORIBOR / policy rate)* | ❌ *(KOSIS available)* |

KR went from **0 ⚠️ / 16 ❌** to **2 ⚠️ / 14 ❌** with KOSIS BoP. Remaining ❌s are now "we have the API key + reference doc; just need to add more `tblId`s to a KOSIS fetcher" rather than infrastructure-blocked.

### 7.14 Taiwan (TW)

| Engine | A | B | C | D |
|---|:---:|:---:|:---:|:---:|
| **Growth** | ❌ | ❌ | ❌ | ❌ |
| **Inflation** | ❌ | ❌ | ❌ | ❌ |
| **External** | ❌ | ❌ | ❌ | ❌ |
| **Policy** | ❌ | ❌ | ❌ | ❌ |

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

## 9. Maintenance

- When a new indicator lands in `econ.dim_indicator`, update the relevant cell from ❌ → ⚠️ → ✅.
- ✅ = at least one indicator per bullet in that cluster, with vintage-0 sample on disk + the production fetcher registered.
- ⚠️ = partial; cell text in parentheses names the indicator(s) present.
- Add new countries by appending rows to §6.x tables — keep the cluster columns identical.
- New clusters / sub-bullets shouldn't be added casually; they're meant to be a stable taxonomy. If a country needs something genuinely off-map (e.g. China RRR ratios, India SLR), record it in §7 (regime-dependence) rather than reshaping the map.
