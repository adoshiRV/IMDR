# India (IN) — coverage plan (RBI DBIE / RBI CIMS / MOSPI / DGCIS / MoF / BIS)

Last updated: 2026-06-09

Maps every India (IN) cell of the
[macro_economy_wiring_map.md §7.12](../macro_economy_wiring_map.md#712-india-in)
to specific vendor identifiers per source agency.

This is the **scoping plan** for filling `econ.dim_indicator` India rows — as of
2026-06-09 there are **0 indicators × 0 observations** loaded in
`econ.fact_indicator` for IN. 36 series are discovered-but-unloaded in
`playground/econ/rbi/sample_output/2026/` (FX 5 + Bulletin 31).

**Scope (per user 2026-06-09):**
- **RBI** — both DBIE (legacy SPA, partial discovery complete) AND CIMS (10
  successor portals, unprobed). Dual-ingest as insurance against DBIE
  deprecation.
- **MOSPI** — CPI / IIP / NAS / GDP / ASI / PLFS. No public API; XLSX + PDF
  release scraping.
- **DGCIS** — Foreign-trade statistics at HS-chapter and partner-country
  granularity. No public API; XLSX scraping.
- **MoF / Budget Division / CGA / BTr-equivalent** — central-govt fiscal
  realisations.
- **BIS + FRED OECD mirror** — fallback for REER / NEER / credit-to-GDP and
  headline series.

**Critical gotcha — read before adding new RBI fetchers**: the DBIE `authorization`
header value captured 2026-06-03 (`gjl6p01780417269959196`) ends in an
epoch-microseconds timestamp. It worked in fresh httpx calls shortly after
capture but may rotate per-session or per-day. If auth fails, replay the
`security_generateSessionToken` + `login_getSapToken` bootstrap flow seen in
[`playground/econ/rbi/discovery/dbie_payloads.json`](../../../playground/econ/rbi/discovery/dbie_payloads.json).
All DBIE endpoints respond **POST only**, with a `{"body": {...}}` envelope, and
return **HTML-escaped JSON** — must call `html.unescape(text)` before parsing.

**DBIE → CIMS migration**: DBIE is being phased out across 10 CIMS portals
(BoP, FLAIR, SMS, FED, CISBI, FIRMS + 4 more). No firm deprecation date.
Dual-track plan: ship DBIE-based fetchers first (faster), probe + port each
endpoint to CIMS in parallel, switch the read side over per-portal as CIMS
stabilises. See [_playground/rbi.md](_playground/rbi.md) for current state.

## Status legend

| Marker | Meaning |
|---|---|
| ✅ **confirmed** | Smoke-tested — endpoint returned rows for the candidate identifier |
| ⚠ **candidate** | Documented in vendor portal; not yet probed against API |
| ❓ **unknown** | Wiring-map concept exists in IN statistics, but the right dataset hasn't been identified — needs catalogue browse |
| ❌ **vendor-absent** | Confirmed absent (e.g. no published series); fallback path required |

## Vendor cascade for IN

Per the [onboarding playbook](../onboarding_new_country.md#step-2--resolve-each--via-the-vendor-cascade) Tier table. India has the weakest API landscape in our Asia coverage — only RBI offers structured access, and even that is SPA-mediated.

| Tier | Source | Transport | Coverage |
|---|---|---|---|
| **T1** | **RBI DBIE** — `data.rbi.org.in/DBIE/` | SPA + `CIMS_Gateway_DBIE` REST (POST, static auth headers) | FX reserves, Exchange Rate, Key Rates, Money Market, G-Sec, Reserve Money, RBI Balance Sheet, Bulletin tables, Weekly Statistical Supplement, Handbook of Statistics, BoP, External Debt |
| **T1 (succ.)** | **RBI CIMS** — 10 portals (BoP / FLAIR / SMS / FED / CISBI / FIRMS / +4) | unprobed — presumed similar JSON gateway | Successor to DBIE; migration in progress |
| **T2** | **MOSPI** — `mospi.gov.in`, `mospi.nic.in` | XLSX + PDF release downloads (no API) | CPI (Rural/Urban/Combined), WPI (DPIIT site), IIP, NSO National Accounts (GDP/GVA), ASI (Annual Survey of Industries), PLFS (Periodic Labour Force Survey) |
| **T2** | **DGCIS** — `dgciskol.gov.in` / `tradestat.commerce.gov.in` | XLSX downloads (no API; HTML query forms) | Foreign-trade statistics by HS chapter + partner country; principal commodities monthly summary |
| **T2** | **DPIIT** — `dpiit.gov.in` (Office of Economic Adviser) | XLSX + PDF | WPI primary publication + WPI sub-indices; FDI inflows |
| **T2** | **MoF / Budget Division** — `indiabudget.gov.in` + `cga.nic.in` | XLSX + PDF | Union Budget; monthly receipts/expenditure via CGA Monthly Accounts |
| **T3** | **CCIL** — `ccilindia.com` | XLSX + login-gated CSV | G-Sec yields, INR OIS, FBIL benchmarks (MIBOR, FBIL-USD/INR), repo turnover |
| **T3** | **NSE / BSE** — `nseindia.com`, `bseindia.com` | JSON-ish but bot-hostile | Equity indices (NIFTY, SENSEX), bond indices, currency derivatives (USDINR futures + options) |
| **T3** | **NSDL / CDSL** — `nsdl.co.in/publications/fpi.php` | XLSX + HTML | FPI monthly flows (debt + equity), DII flows |
| **T4** | **BIS** — `stats.bis.org/api/v2/data/dataflow/BIS/...` | SDMX-JSON REST (free, no auth) | REER / NEER broad + narrow, credit-to-GDP gap, DSR private NFS, CBPOL policy rate, total credit |
| **T4** | **FRED** — OECD India mirror | REST (paid key in `IMDR_ECON_FRED_KEY`) | Headline subset — CPI YoY, IP, OECD India unemployment, 10Y G-Sec yield, OECD India IR |
| **T6** | **CMIE / CEIC / Macrobond** | paid API | Last resort if a series is on no free source |

When a series is published by both RBI Bulletin AND its primary issuer (e.g. CPI
in RBI Bulletin T19C reproduces MOSPI's release), prefer the **primary issuer**
(MOSPI). RBI Bulletin tables are convenient but lag the original by 1-2 days
and occasionally trim sub-components.

---

## 1. Growth Engine

### 1.1 Private Demand (consumption, retail, household credit)

| Concept | Vendor | Dataset / table | Cadence | Status |
|---|:---:|---|:---:|:---:|
| Private Final Consumption Expenditure (PFCE) | MOSPI | NSO National Accounts — expenditure side | Q | ⚠ MOSPI XLSX scrape |
| Auto sales (passenger vehicles + 2-wheelers) | SIAM | siam.in monthly press release | M | ❓ industry assoc, paid behind login |
| Retail sales — not formally tracked | — | (no national retail trade index in IN) | — | ❌ vendor-absent |
| Consumer Confidence Index (CCI) | RBI | DBIE — Consumer Confidence Survey (Urban + Rural) | BiM | ⚠ DBIE Unit Level Data section |
| Inflation Expectations Survey | RBI | DBIE — IESH | BiM | ⚠ DBIE Unit Level Data section |
| Household credit aggregate (personal loans) | RBI | DBIE — Statistics → Financial Sector → Banking → Sectoral Deployment of Bank Credit | M | ⚠ DBIE |
| Housing loans (HFC + bank) | RBI | DBIE — Sectoral Deployment | M | ⚠ DBIE |
| Credit card outstanding | RBI | DBIE — Payment System Indicators | M | ⚠ DBIE |

### 1.2 Fiscal Demand (govt spending, taxes, deficit)

| Concept | Vendor | Dataset / table | Cadence | Status |
|---|:---:|---|:---:|:---:|
| Central govt receipts (tax + non-tax) | CGA / MoF | Monthly Accounts of GoI | M | ⚠ CGA XLSX |
| Central govt expenditure (revenue + capital) | CGA / MoF | Monthly Accounts | M | ⚠ CGA XLSX |
| Central govt fiscal deficit (cumulative) | CGA / MoF | Monthly Accounts | M | ⚠ CGA XLSX |
| Direct tax collections (income + corporate) | CBDT | press release | M | ⚠ press release scrape |
| Indirect tax — GST collections | GSTN | gstn.gov.in monthly bulletin | M | ⚠ HTML/PDF scrape |
| Govt final consumption (GFCE, NAS basis) | MOSPI | NSO National Accounts — expenditure | Q | ⚠ MOSPI |
| Govt investment / GFCF | MOSPI | NSO National Accounts | Q | ⚠ MOSPI |
| Central govt market borrowings (gross + net) | RBI | DBIE Indicators → Financial Sector → Central Govt Market Borrowings | W | ⚠ DBIE |
| State govt market borrowings (SDL) | RBI | DBIE — State Government Securities Auctions | W | ⚠ DBIE |
| Govt debt outstanding (% of GDP) | MoF / RBI | DBIE Statistics → Public Finance | Q | ⚠ DBIE |
| State govt finances (combined) | RBI | DBIE Statistics → Public Finance → State Govt | A | ⚠ DBIE |

### 1.3 External Demand (trade)

| Concept | Vendor | Dataset / table | Cadence | Status |
|---|:---:|---|:---:|:---:|
| Merchandise exports (USD) | DGCIS / MoCommerce | tradestat.commerce.gov.in monthly summary | M | ⚠ XLSX scrape |
| Merchandise imports (USD) | DGCIS | tradestat | M | ⚠ |
| Merchandise trade balance | DGCIS | tradestat | M | ⚠ |
| Services exports (Receipts) | RBI | DBIE Statistics → External Sector → International Trade in Services | M | ⚠ DBIE |
| Services imports (Payments) | RBI | DBIE Statistics → External Sector → ITS | M | ⚠ DBIE |
| Services balance | RBI | DBIE — ITS | M | ⚠ DBIE |
| Petroleum vs Non-petroleum exports | DGCIS | tradestat split | M | ⚠ XLSX |
| Petroleum vs Non-petroleum imports | DGCIS | tradestat split | M | ⚠ XLSX |
| Gold imports (USD + tonnes) | DGCIS / RBI Bulletin | DGCIS commodity-level; RBI summary | M | ⚠ |
| Exports by partner country | DGCIS | tradestat country-wise | M | ⚠ XLSX (large, ~30MB/release) |
| Imports by partner country | DGCIS | tradestat country-wise | M | ⚠ |
| Exports by HS chapter (98 chapters) | DGCIS | tradestat commodity-wise | M | ⚠ |
| Imports by HS chapter | DGCIS | tradestat commodity-wise | M | ⚠ |
| Net exports (NAS basis) | MOSPI | NSO National Accounts — expenditure | Q | ⚠ MOSPI |

### 1.4 Macro Core (GDP, IIP, labour, sentiment)

| Concept | Vendor | Dataset / table | Cadence | Status |
|---|:---:|---|:---:|:---:|
| Real GDP YoY | MOSPI | NSO NAS — GDP at constant 2011-12 prices | Q | ⚠ MOSPI XLSX |
| Real GDP level (chain-linked) | MOSPI | NSO NAS | Q | ⚠ |
| Nominal GDP level | MOSPI | NSO NAS | Q | ⚠ |
| Real GVA YoY (basic prices) | MOSPI | NSO NAS — GVA decomp | Q | ⚠ |
| Real GVA by sector (Ag / Mining / Mfg / Construction / Services 5-way) | MOSPI | NSO NAS sectoral | Q | ⚠ |
| GDP deflator YoY | MOSPI | NSO NAS derived | Q | ⚠ |
| GDP YoY (RBI Bulletin reissue) | RBI | DBIE Indicators → Real Sector → GDP | Q | ⚠ DBIE |
| Index of Industrial Production (IIP, total) | MOSPI | IIP monthly release (general / mfg / mining / electricity) | M | ⚠ MOSPI |
| IIP — Use-based (Cap goods, Cons durables, etc.) | MOSPI | IIP use-based | M | ⚠ MOSPI |
| IIP (RBI Bulletin reissue) | RBI | DBIE Indicators → Real Sector → IIP-Monthly | M | ⚠ DBIE |
| 8-Core Industries Index | DPIIT (OEA) | dpiit.gov.in monthly | M | ⚠ XLSX scrape |
| Manufacturing PMI | S&P Global | paid | M | ❌ paid |
| Services PMI | S&P Global | paid | M | ❌ paid |
| Unemployment rate | MOSPI | PLFS Annual + Quarterly Urban | A + Q | ⚠ PLFS XLSX |
| Labour force participation rate | MOSPI | PLFS | A + Q | ⚠ |
| Employment growth (formal) | EPFO | epfindia.gov.in payroll release | M | ⚠ |
| CMIE unemployment (high-frequency) | CMIE | unemploymentinindia.cmie.com | W + M | ❌ paid |
| Business Sentiment (RBI IOS — Industrial Outlook Survey) | RBI | DBIE — Surveys | Q | ⚠ DBIE |
| Order Books, Inventories & Capacity Utilisation (OBICUS) | RBI | DBIE — Surveys | Q | ⚠ DBIE |

---

## 2. Inflation Engine

### 2.1 Input Costs

| Concept | Vendor | Dataset / table | Cadence | Status |
|---|:---:|---|:---:|:---:|
| Crude oil import basket (USD/bbl) | PPAC | ppac.gov.in monthly | D + M | ⚠ XLSX |
| Domestic petrol / diesel prices | PPAC | ppac.gov.in city-wise | D | ⚠ |
| LPG / kerosene prices | PPAC | ppac.gov.in | M | ⚠ |
| Coal stock + prices | CIL / CEA | press release | M | ⚠ |
| Food article wholesale prices | DPIIT | WPI Food Articles sub-index | M | ⚠ |
| Fuel & Power WPI sub-index | DPIIT | WPI Fuel | M | ⚠ |
| Commodity import volumes (gold, oil, edible oil) | DGCIS | tradestat commodity | M | ⚠ |
| Supply-chain pressure (global) | FRED | `NYFEDGSCPI` | M | ❓ cross-country |
| FX pass-through gauge | derived | INR depreciation × import-price differential | M | ❓ analytics-side |

### 2.2 Producer Prices (WPI is India's PPI)

| Concept | Vendor | Dataset / table | Cadence | Status |
|---|:---:|---|:---:|:---:|
| WPI All Commodities (2011-12=100) | DPIIT (OEA) | dpiit.gov.in monthly | M | ⚠ XLSX scrape |
| WPI Primary Articles | DPIIT | sub-index | M | ⚠ |
| WPI Fuel & Power | DPIIT | sub-index | M | ⚠ |
| WPI Manufactured Products | DPIIT | sub-index | M | ⚠ |
| WPI Food Index (cross-Primary + Mfg food) | DPIIT | derived published index | M | ⚠ |
| Producer Price Index (proper PPI — pilot) | MOSPI | NSO PPI pilot (April 2024+ experimental) | Q | ❓ pilot only |
| Export Unit Value Index | DGCIS | trade indices | M | ⚠ |
| Import Unit Value Index | DGCIS | trade indices | M | ⚠ |

### 2.3 Domestic Costs (wages, rents, expectations)

| Concept | Vendor | Dataset / table | Cadence | Status |
|---|:---:|---|:---:|:---:|
| Rural wages (Labour Bureau) | Labour Bureau | labourbureaunew.gov.in monthly | M | ⚠ XLSX |
| Wage Rate Index (WRI) | Labour Bureau | WRI publication | M | ⚠ |
| PLFS earnings (urban + rural by activity) | MOSPI | PLFS Annual | A | ⚠ |
| Mfg capacity utilisation (OBICUS) | RBI | DBIE — Surveys | Q | ⚠ DBIE |
| Inflation Expectations Survey of Households | RBI | DBIE — Surveys (IESH 3M + 1Y) | BiM | ⚠ DBIE |
| Survey of Professional Forecasters (CPI median forecast) | RBI | DBIE — Surveys | Q | ⚠ DBIE |
| Housing rents (CPI sub-index) | MOSPI | CPI Housing sub-group | M | ⚠ |

### 2.4 CPI Pressure

| Concept | Vendor | Dataset / table | Cadence | Status |
|---|:---:|---|:---:|:---:|
| Headline CPI Combined (Rural + Urban) YoY | MOSPI | NSO CPI release | M | ⚠ MOSPI XLSX |
| Headline CPI Combined level (2012=100) | MOSPI | NSO CPI | M | ⚠ |
| CPI Rural YoY + level | MOSPI | NSO CPI | M | ⚠ |
| CPI Urban YoY + level | MOSPI | NSO CPI | M | ⚠ |
| Core CPI (CPI ex Food & Fuel) | MOSPI / derived | NSO sub-indices | M | ⚠ |
| CPI Food & Beverages | MOSPI | sub-index | M | ⚠ |
| Consumer Food Price Index (CFPI) | MOSPI | sub-index | M | ⚠ |
| CPI Fuel & Light | MOSPI | sub-index | M | ⚠ |
| CPI Housing (urban only) | MOSPI | sub-index | M | ⚠ |
| CPI sub-group (6 major + Misc 5-way) | MOSPI | NSO CPI | M | ⚠ |
| CPI (RBI Bulletin T19C reissue) | RBI | DBIE Indicators → Real Sector → CPI | M | ⚠ DBIE (partial discovery — see Phase A captured XLSX) |
| CPI for Agricultural Labourers (CPI-AL) | Labour Bureau | press release | M | ⚠ |
| CPI for Industrial Workers (CPI-IW) | Labour Bureau | press release | M | ⚠ |

---

## 3. External & FX

### 3.1 Terms of Trade

| Concept | Vendor | Dataset / table | Cadence | Status |
|---|:---:|---|:---:|:---:|
| Net Barter ToT | DGCIS / derived | from Export UVI / Import UVI | M | ⚠ derive in analytics |
| Income ToT | DGCIS / derived | NBToT × volume ratio | M | ⚠ derive |
| Export Unit Value Index | DGCIS | trade indices | M | ⚠ |
| Import Unit Value Index | DGCIS | trade indices | M | ⚠ |
| Export Quantum Index | DGCIS | trade indices | M | ⚠ |
| Import Quantum Index | DGCIS | trade indices | M | ⚠ |

### 3.2 Current Account

| Concept | Vendor | Dataset / table | Cadence | Status |
|---|:---:|---|:---:|:---:|
| Current Account Balance (USD bn) | RBI | DBIE Statistics → External Sector → BoP | Q | ⚠ DBIE |
| Current Account % of GDP | RBI | DBIE BoP summary | Q | ⚠ |
| Goods balance (BoP basis) | RBI | DBIE BoP | Q | ⚠ |
| Services balance (Net Invisibles — Travel, Transportation, Software, GNIE, Misc) | RBI | DBIE BoP | Q | ⚠ |
| Primary income balance (Investment income) | RBI | DBIE BoP | Q | ⚠ |
| Secondary income (Private Transfers / Remittances) | RBI | DBIE BoP | Q | ⚠ |
| Software services exports | RBI | DBIE — separately published, also via BoP | Q | ⚠ |
| Remittances inflow (Private Transfers) | RBI | DBIE BoP + RBI Bulletin Remittances Survey | Q + A | ⚠ |

### 3.3 Capital + Financial Account

| Concept | Vendor | Dataset / table | Cadence | Status |
|---|:---:|---|:---:|:---:|
| Capital Account total | RBI | DBIE BoP | Q | ⚠ |
| Foreign Direct Investment (FDI inflows / outflows / net) | RBI / DPIIT | DBIE BoP + DPIIT quarterly | Q + M | ⚠ |
| Foreign Portfolio Investment (FPI) — Equity | NSDL | nsdl.co.in/publications/fpi.php monthly | M + D | ⚠ NSDL XLSX |
| Foreign Portfolio Investment — Debt | NSDL | NSDL FPI | M + D | ⚠ |
| External Commercial Borrowings (ECB) | RBI | DBIE — ECB / Trade Credit / Loans | M | ⚠ DBIE |
| NRI Deposits flows (BoP basis) | RBI | DBIE BoP | Q | ⚠ |
| **FCNR(B) outstanding stock** | RBI | DBIE — Liabilities to Others / NRI Deposits | M | ⚠ DBIE — drives FX-swap hedging volume; key for forward-premia transmission |
| **NRE rupee account outstanding stock** | RBI | DBIE — NRI Deposits | M | ⚠ DBIE |
| **NRO rupee account outstanding stock** | RBI | DBIE — NRI Deposits | M | ⚠ DBIE |
| Other Investment (Banking capital + Loans + Misc) | RBI | DBIE BoP | Q | ⚠ |
| Reserve Assets, transactional change | RBI | DBIE BoP | Q | ⚠ |
| Errors and Omissions | RBI | DBIE BoP | Q | ⚠ |
| Net IIP (International Investment Position) | RBI | DBIE — IIP quarterly | Q | ⚠ |
| External Debt (total + components) | RBI / MoF | DBIE External Debt | Q | ⚠ |
| FX Reserves Total (USD) | RBI | DBIE `dbie_foreignExchangeReserves` `reserveCode=TR` | W | ✅ `scripts.econ.rbi.rbi_fx_reserves` (603 obs, 2015→) |
| FX Reserves — Foreign Currency Assets | RBI | DBIE `reserveCode=FCA` | W | ✅ `scripts.econ.rbi.rbi_fx_reserves` (603 obs, 2015→) |
| FX Reserves — Gold | RBI | DBIE `reserveCode=GOLD` | W | ✅ `scripts.econ.rbi.rbi_fx_reserves` (603 obs, 2015→) |
| FX Reserves — SDR | RBI | DBIE `reserveCode=SDR` | W | ✅ `scripts.econ.rbi.rbi_fx_reserves` (603 obs, 2015→) |
| FX Reserves — Reserve position in IMF | RBI | DBIE `reserveCode=IMF` | W | ✅ `scripts.econ.rbi.rbi_fx_reserves` (603 obs, 2015→) |

### 3.4 FX / REER

| Concept | Vendor | Dataset / table | Cadence | Status |
|---|:---:|---|:---:|:---:|
| Spot INR vs USD | (FX domain — Citi `FX.SPOT.USD.INR.CITI`) | — | D | ✅ via market data |
| Spot INR vs EUR / JPY / GBP / CNY | (FX domain — Citi crosses) | — | D | ✅ via market data |
| NDF curve INR (offshore — restricted currency) | (FX domain) | — | D | ✅ via market data |
| Onshore USD/INR forward points | (FX domain — Citi) | — | D | ✅ |
| FX implied vol (INR) | (FX domain — Citi) | — | D | ✅ |
| RBI Reference Rate INR/USD | RBI | DBIE Indicators → External Sector → Exchange Rate | D | ⚠ DBIE |
| INR vs USD / EUR / JPY / GBP (RBI ref) | RBI | DBIE Exchange Rate | D | ⚠ |
| NEER 6-currency + 40-currency (trade-weighted) | RBI | DBIE — NEER + REER Bulletin tables | M | ⚠ DBIE — XLSX captured in `discovery/samples/neer_reer.xlsx` |
| REER 6-currency + 40-currency | RBI | DBIE — same publication | M | ⚠ DBIE — XLSX captured |
| BIS NEER broad | BIS | `WS_EER` key=M.N.B.IN | M | ✅ `scripts.econ.bis.bis_india` (388 obs, 1994→) |
| BIS REER broad | BIS | `WS_EER` key=M.R.B.IN | M | ✅ `scripts.econ.bis.bis_india` (388 obs, 1994→) |
| CB FX intervention (spot + forward book) | RBI | DBIE — Sale/Purchase of US Dollar (RBI net interv.) | M | ⚠ DBIE |
| Forward book outstanding (RBI net long/short USD fwd) | RBI | DBIE — RBI's outstanding forward sales/purchases | M | ⚠ |
| **FBIL onshore USD/INR forward premia** 1M / 3M / 6M / 1Y | FBIL via CCIL | fbil.org.in daily reference fixings (annualised %) | D | ⚠ CCIL — desk-reference fwd premia, distinct from Citi market-data fwd points |

---

## 4. Policy Transmission

### 4.1 Demand Transmission (lending standards, credit channel)

| Concept | Vendor | Dataset / table | Cadence | Status |
|---|:---:|---|:---:|:---:|
| Bank Credit (Non-food, total) | RBI | DBIE — Business of Scheduled Banks | F (fortnightly) | ⚠ DBIE |
| Sectoral Deployment of Bank Credit (Agri/Industry/Services/Personal) | RBI | DBIE Statistics → Banking → Sectoral Deployment | M | ⚠ DBIE |
| Sub-sector credit (e.g. industry by size, services by sub-sector) | RBI | DBIE Sectoral Deployment | M | ⚠ DBIE |
| Bank Deposits (Aggregate) | RBI | DBIE — Business of Scheduled Banks | F | ⚠ DBIE |
| Credit-Deposit ratio | RBI / derived | DBIE | F | ⚠ |
| Mortgage rates (new origination, WALR) | RBI | DBIE — Bank lending rates | M | ⚠ DBIE |
| WALR / WAFR / WATDR (lending + funding rates) | RBI | DBIE — Interest Rate Statistics | M | ⚠ DBIE |
| MCLR (Marginal Cost of Funds based Lending Rate) | RBI | DBIE Key Rates | M | ⚠ DBIE |
| External Benchmark Lending Rate (EBLR) | RBI | DBIE Key Rates | M | ⚠ DBIE |
| BIS credit-to-GDP gap | BIS | `WS_CREDIT_GAP` key=Q.IN.P.A.C | Q | ✅ `scripts.econ.bis.bis_india` (258 obs, 1961→) |
| MFI / NBFC credit | RBI | DBIE — NBFC statistics | Q | ⚠ |

### 4.2 Balance Sheets (sectoral leverage, NPL)

| Concept | Vendor | Dataset / table | Cadence | Status |
|---|:---:|---|:---:|:---:|
| Household debt to GDP | BIS | `WS_CREDIT` key=Q.IN.H.A.M.770.A | Q | ⚠ BIS |
| Household DSR | BIS | `WS_DSR` key=Q.IN.H | Q | ❌ confirmed absent — BIS returns HTTP 404 (EM coverage gap); use private NFS |
| NFC (non-financial corp) DSR | BIS | `WS_DSR` key=Q.IN.N | Q | ❌ confirmed absent — BIS returns HTTP 404 for IN; use private NFS |
| Private NFS DSR | BIS | `WS_DSR` key=Q.IN.P | Q | ✅ `scripts.econ.bis.bis_india` (107 obs, 1999→) |
| Credit-to-GDP ratio | BIS | `WS_CREDIT_GAP` key=Q.IN.P.A.A | Q | ✅ `scripts.econ.bis.bis_india` (298 obs, 1951→) |
| Corporate sector financials (Listed Non-Govt Non-Financial Companies) | RBI | DBIE Statistics → Corporate Sector | A + Q | ⚠ DBIE — 5 sub-categories |
| Bank Asset Quality (GNPA + NNPA ratio) | RBI | DBIE Statistics → Banking → Performance | H | ⚠ DBIE |
| Bank CRAR / Tier-1 / CET1 | RBI | DBIE — Capital Adequacy | H | ⚠ DBIE |
| Bank Sector Aggregates (Stat. Tables Relating to Banks) | RBI | DBIE — STRBI annual publication | A | ⚠ DBIE |
| BSR-1 / BSR-2 (Basic Statistical Returns) | RBI | DBIE Publications | A + Q | ⚠ DBIE |
| Central Govt Debt / GDP | MoF / RBI | DBIE Public Finance | Q | ⚠ |
| Combined Centre+State Debt / GDP | RBI | DBIE Statistics → Public Finance → Central+State Combined | A | ⚠ DBIE |
| NBFC sector balance sheet | RBI | DBIE — NBFC statistics | Q | ⚠ DBIE |
| Financial Stability composite | RBI | Financial Stability Report (semi-annual) | H | ⚠ PDF parse |

### 4.3 Financial Conditions (rates, curve, spreads)

| Concept | Vendor | Dataset / table | Cadence | Status |
|---|:---:|---|:---:|:---:|
| Repo rate | RBI | DBIE Indicators → Financial Sector → Key Rates | EVENT | ⚠ DBIE |
| Standing Deposit Facility (SDF) rate | RBI | DBIE Key Rates | EVENT | ⚠ |
| Marginal Standing Facility (MSF) rate | RBI | DBIE Key Rates | EVENT | ⚠ |
| Bank Rate | RBI | DBIE Key Rates | EVENT | ⚠ |
| CRR / SLR | RBI | DBIE Key Rates | EVENT | ⚠ |
| Reverse Repo rate (historical, pre-SDF) | RBI | DBIE Key Rates | EVENT | ⚠ |
| Call Money rate (WACR) | RBI | DBIE Indicators → Money Market | D | ⚠ DBIE — XLSX captured in `discovery/samples/call_money_rates.xlsx` |
| TREPS rate | RBI | DBIE Money Market | D | ⚠ DBIE |
| Market Repo rate | RBI | DBIE Money Market | D | ⚠ |
| MIBOR (overnight + 14D + 1M + 3M term) | FBIL via CCIL | fbil.org.in / ccilindia.com daily fixings | D | ⚠ CCIL |
| **MIFOR / MMIFOR fixings** 1M / 3M / 6M / 1Y (SOFR-linked post-LIBOR cessation) | FBIL via CCIL | fbil.org.in daily | D | ⚠ CCIL — FX-fwd-premium + SOFR composite; key fixing for INR IRS/OIS arbitrage |
| **MIOIS (Modified MIBOR-OIS) fixings** | FBIL via CCIL | fbil.org.in daily | D | ⚠ CCIL |
| 91-day T-bill rate | RBI | DBIE Money Market | D | ⚠ DBIE |
| 182-day T-bill rate | RBI | DBIE Money Market | D | ⚠ |
| 364-day T-bill rate | RBI | DBIE Money Market | D | ⚠ |
| CD (Certificate of Deposit) issuance + rate | RBI | DBIE Money Market | F | ⚠ |
| CP (Commercial Paper) issuance + rate | RBI | DBIE Money Market | F | ⚠ |
| 1Y / 5Y / 10Y G-Sec yield | CCIL / RBI | DBIE G-Sec Market + CCIL terminal | D | ⚠ |
| G-Sec Turnover (NDS-OM) | RBI | DBIE Indicators → G-Sec → G-Sec Turnover | D | ⚠ DBIE |
| Term spread (10Y – 2Y G-Sec) | derived | from G-Sec curve | D | ⚠ |
| Sovereign CDS 5Y (USD) | (rates domain — market data) | — | D | ✅ via market data |
| INR OIS curve (1Y / 5Y) | CCIL / Citi | CCIL terminal; market data | D | ⚠ + ✅ |
| Corporate bond yields (AAA / AA / A — 5Y / 10Y) | CCIL / SEBI | CCIL daily yields | D | ⚠ CCIL |
| NIFTY 50 level | (equity domain — Citi `EQUITY.EQUITY_INDEX.NIFTY.LEVEL.REUTERS`) | — | D | ✅ via market data |
| SENSEX level | (equity domain) | — | D | ✅ via market data |
| Daily LAF (Liquidity Adjustment Facility) net operation | RBI | DBIE Indicators → Financial Sector → Daily LAF Operation | D | ⚠ DBIE |

### 4.4 Policy Reaction (rate + liquidity + macroprudential)

| Concept | Vendor | Dataset / table | Cadence | Status |
|---|:---:|---|:---:|:---:|
| Repo rate level + changes | RBI | DBIE Key Rates + MPC resolution | EVENT | ⚠ DBIE |
| MPC voting record + statements | RBI | press release scrape (`BS_PressReleaseDisplay.aspx`) | per meeting | ⚠ scrape |
| MPC minutes | RBI | rbi.org.in/Scripts/PublicationReport.aspx?ID=911 | per meeting | ⚠ HTML scrape |
| Monetary Policy Report (forecasts) | RBI | semi-annual MPR PDF | H | ⚠ PDF parse |
| Reserve Money (M0) | RBI | DBIE Indicators → Financial Sector → Reserve Money | W | ⚠ DBIE — XLSX captured |
| M1 (narrow money) | RBI | DBIE — Monetary Statistics | F | ⚠ DBIE — XLSX captured |
| M3 (broad money) | RBI | DBIE — Monetary Statistics | F | ⚠ DBIE — XLSX captured |
| Currency in circulation | RBI | DBIE — Reserve Money | W | ⚠ DBIE |
| RBI Balance Sheet (assets + liabilities) | RBI | DBIE Indicators → Financial Sector → RBI Balance Sheet | W | ⚠ DBIE |
| Policy rate (BIS cross-check) | BIS | `WS_CBPOL` key=D.IN | D / EVENT | ✅ `scripts.econ.bis.bis_india` (23,518 obs, 1946→ — daily RBI repo rate) |
| Net OMO (outright open market operations) | RBI | DBIE — OMO publications | EVENT | ⚠ |
| **VRR (Variable Rate Repo) auction history** — durable liquidity infusion | RBI | DBIE — Auctions / RBI press release | EVENT | ⚠ DBIE + press release scrape |
| **VRRR (Variable Rate Reverse Repo) auction history** — durable absorption (sterilisation post-FCNR-type inflows) | RBI | DBIE — Auctions / RBI press release | EVENT | ⚠ DBIE + press release scrape |
| **Centre's cash balance with RBI** + Ways & Means Advances | RBI | DBIE — Reserve Money + Public Finance | W | ⚠ DBIE — orthogonal liquidity drain to FCNR-style inflow |
| **Bank NDTL (Net Demand & Time Liabilities)** — CRR sizing base | RBI | DBIE — Business of Scheduled Banks | F | ⚠ DBIE — explicit row (was implicit in BSB) |
| FX intervention spot + forward (cross-ref 3.4) | RBI | DBIE — Sale/Purchase USD | M | ⚠ DBIE |
| LCR / NSFR (bank liquidity rules) | RBI | DBIE — Liquidity Coverage Ratio | Q | ⚠ DBIE |
| Macroprudential — Countercyclical Capital Buffer (CCyB) | RBI | press release | EVENT | ⚠ |
| Macroprudential — LTV / Risk weights | RBI | press release | EVENT | ⚠ |

---

## 5. Events, Press Releases & Document Sources

Data series alone don't answer questions like "will FCNR flows lower MIBOR
fixings" — the regulatory window, the MPC reaction function, and qualitative
RBI communication are essential context. These ingest as **document corpus +
event-stamped records**, not as time series in `econ.fact_indicator`.

Storage convention (per Picasso / Lois corpus pattern):
- Documents → `data/research/in/{vendor}/{YYYY}/{MM}/{DD}/{filename}.pdf` +
  `.md` extract.
- Event stamps → `econ.fact_event` (new table TBD) with
  `(country_id, vendor_id, event_type, event_ts, document_url, summary_text)`.
- Vectorise extracts into Qdrant `imdr-research` collection for retrieval by
  Mycroft + Lois.

### 5.1 RBI events

| Event class | Source URL pattern | Cadence | What to extract |
|---|---|:---:|---|
| **MPC resolution** (rate decision + Governor statement) | `rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=...` | 6 / yr | Date · repo / SDF / MSF / CRR / SLR changes · stance (accommodative / neutral / hawkish) · vote count |
| **MPC minutes** | `rbi.org.in/Scripts/PublicationReport.aspx?ID=911` | 6 / yr (14d after meeting) | Per-member rationale + vote |
| **Monetary Policy Report (MPR)** | `rbi.org.in/Scripts/Publications.aspx?head=Monetary%20Policy%20Report` | semi-annual | Inflation + GDP forecast bands · risk balance |
| **Financial Stability Report (FSR)** | `rbi.org.in/Scripts/PublicationReportDetails.aspx?ID=...` | semi-annual | Systemic-risk dashboard · stress-test results · macro-prudential calls |
| **RBI Bulletin — State of the Economy** chapter | `rbi.org.in/Scripts/BS_ViewBulletin.aspx` | M | Staff macro view |
| **RBI Annual Report** | `rbi.org.in/Scripts/AnnualReportPublications.aspx` | A | RBI balance sheet + monetary operations narrative |
| **Notifications — FCNR / NRI / FPI / ECB regulatory windows** | `rbi.org.in/Scripts/NotificationUser.aspx` | EVENT | Rate caps · withholding tax · CRR waivers · forex regulatory changes |
| **Notifications — Liquidity ops (VRR / VRRR / OMO calendars)** | `rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx` | weekly + EVENT | Auction size · cut-off rate · maturity |
| **G-Sec auction calendar + results** | `rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx` (auction tags) | weekly | Issuance size · cut-off yield · bid-cover |
| **Governor + Deputy Governor speeches** | `rbi.org.in/scripts/BS_speechesview.aspx` | irregular | Forward guidance signals |
| **Sectoral Deployment / Credit aggregates press notes** | `rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx` | M | Sectoral credit growth narrative (companion to DBIE Sectoral Deployment) |

### 5.2 MoF / Fiscal events

| Event class | Source URL pattern | Cadence | What to extract |
|---|---|:---:|---|
| **Union Budget** (Budget Speech + Receipts + Expenditure books) | `indiabudget.gov.in` | A (Feb) | Fiscal deficit target · borrowing programme size · revenue assumptions |
| **Interim Budget** (election year) | `indiabudget.gov.in` | A (Feb in poll yr) | Vote-on-account |
| **Economic Survey** | `indiabudget.gov.in/economicsurvey/` | A (day before Budget) | Govt's macro view + sectoral analysis |
| **Mid-Year Economic Analysis** | `dea.gov.in` | A (Dec) | Mid-year fiscal review |
| **CGA Monthly Accounts** press release | `cga.nic.in/MonthlyReport.aspx` | M | Tax/non-tax receipts + expenditure split + fiscal deficit% |
| **Borrowing calendar (H1 + H2 issuance plan)** | RBI press release | semi-annual | G-Sec + T-bill + SDL size by tenor |
| **GST monthly collections** | `gstn.gov.in` press release | M | GST collections + IGST split |
| **Fortnightly tax receipts** (CBDT / CBIC) | press release | F | Direct + indirect tax momentum |

### 5.3 MOSPI / Statistical-system events

| Event class | Source URL pattern | Cadence | What to extract |
|---|---|:---:|---|
| **CPI press release** | `mospi.gov.in/cpi-press-release` | M | Headline / rural / urban / sub-group + base-revision notes |
| **IIP press release** | `mospi.gov.in/iip` | M | Total + use-based + sectoral + revision flags |
| **NAS Quarterly GDP press release** | `mospi.gov.in/QuarterlyEstimatesGDP` | Q | Real GDP / GVA + sectoral + revision history |
| **NAS Provisional + Revised Annual GDP** | `mospi.gov.in` | A (May + Jan) | Annual baseline + base-year rebase notifications |
| **PLFS Annual + Quarterly Urban** | `mospi.gov.in/plfs` | A + Q | Unemployment / LFPR / earnings |
| **ASI** | `mospi.gov.in/asi-press-release` | A (lag 2y) | Manufacturing structural data |

### 5.4 Sector / other regulator events

| Event class | Source URL pattern | Cadence | Why |
|---|---|:---:|---|
| **SEBI board meeting outcomes** | `sebi.gov.in` press release | M | Bond market structure (FPI debt limits · T+1 settlement · derivative norms) |
| **IRDAI board outcomes** | `irdai.gov.in` | M | Insurance-sector G-Sec demand shifts |
| **DPIIT FDI policy notifications** | `dpiit.gov.in` | EVENT | Capital-account FDI rules |
| **NSE / BSE — F&O turnover + open interest** | NSE EOD reports | D | Derivative-market positioning |
| **EPFO payroll release** | `epfindia.gov.in` | M | Formal-sector employment proxy |

### 5.5 Storage + retrieval pattern

- All documents archived under `data/research/in/{rbi|mof|mospi|sebi|...}/...`
- Markdown extracts of PDFs via `pymupdf` text extraction (per the Picasso / Mycroft PDF embed pattern).
- Vectorise via existing `imdr-research` Qdrant pipeline (see [[project-research-mcp-owner-only]]).
- Event-stamped records (rate decisions, intervention disclosures, FCNR notification dates) flow into a new `econ.fact_event` table for time-series joins.

---

## Discovery → Production phase plan

Plan follows the [onboarding playbook](../onboarding_new_country.md). Phases are
deliberately small because of the dual DBIE/CIMS track and the heavy MOSPI
XLSX scraping work.

| Phase | Scope | Outputs |
|---|---|---|
| **A0 — DBIE auth durability check** | Verify the captured `authorization` header still works 1d / 7d / 30d after capture. If it rotates, build the bootstrap-replay flow first. | `playground/econ/rbi/probe_auth_durability.py` + finding note |
| **A — DBIE FX reserves load** | Already-decoded endpoint. 5 reserve codes × Weekly. | First IN rows in `econ.fact_indicator` (5 indicators); load via `scripts.migrations.load_econ_indicator_from_playground --vendor rbi` |
| **B — DBIE Indicators-tree payload capture** | Click-through Playwright + network interception for each leaf in the Indicators menu (Exchange Rate, Key Rates, Money Market, G-Sec Turnover, Reserve Money, RBI Balance Sheet, Payment System, Central Govt Market Borrowings, Business of Scheduled Banks, IIP, CPI, GDP, Daily LAF, Sectoral Deployment). | `discovery/payloads_indicators.json` with one POST body per leaf; coverage of wiring cells 1.4/2.4/3.3/3.4/4.1/4.3/4.4 partial |
| **C — Generic `dbie_getPublicationDataImpala` wrapper** | Likely many Statistics + Bulletin tables route through the Impala endpoint with `{publication_id, table_id, ...}`. Decode body shape from 2-3 menus and ship a generic fetcher. | `playground/econ/rbi/fetch_publication.py` |
| **D — RBI Bulletin tables** | T19C (CPI), T27 (call money), Remittances Survey, Inflation Expectations, Consumer Confidence — already in metadata, get them loading via the wrapper from Phase C. | 31 Bulletin indicators loaded |
| **E — CIMS portal probe** | Open each of the 10 CIMS sub-portals (`BoP`, `FLAIR`, `SMS`, `FED`, `CISBI`, `FIRMS` + 4) in headed Playwright; capture endpoint inventories. | `discovery/cims_endpoints.json` + per-portal payload samples |
| **F — DBIE↔CIMS endpoint mapping** | For each DBIE endpoint in production by end of Phase D, find the CIMS equivalent and record both. Build the read layer behind a `vendor_route` flag so we can flip per-endpoint. | `playground/econ/rbi/route_map.md` |
| **G — MOSPI CPI release scrape** | MOSPI publishes monthly CPI on `mospi.gov.in/cpi-press-release`. PDF + XLSX. Parse the press release table for Headline / Rural / Urban / CFPI / sub-groups. Promotes 2.4 from ⚠ → ✅. | `playground/econ/mospi/fetch_cpi.py` |
| **H — MOSPI IIP release scrape** | IIP monthly release on `mospi.gov.in/iip`. XLSX + PDF. Promotes 1.4 IIP. | `playground/econ/mospi/fetch_iip.py` |
| **I — MOSPI NAS quarterly GDP** | Quarterly press release with detailed sectoral + expenditure tables (XLSX). Promotes 1.4 GDP + 1.1 PFCE + 1.3 NetExp + 1.2 GFCE. | `playground/econ/mospi/fetch_nas.py` |
| **J — DGCIS trade scrape** | `tradestat.commerce.gov.in` monthly XLSX (totals + petroleum split + partner country + HS chapter). Promotes 1.3 External Demand + 3.1 ToT. | `playground/econ/dgcis/fetch_trade.py` |
| **K — DPIIT WPI scrape** | Monthly WPI release XLSX. Promotes 2.2. | `playground/econ/dpiit/fetch_wpi.py` |
| **L — MoF / CGA fiscal scrape** | Monthly Accounts of GoI XLSX from `cga.nic.in`. Promotes 1.2. | `playground/econ/mof/fetch_monthly_accounts.py` |
| **M — BIS IN package** ✅ | `scripts/econ/bis/bis_india.py` shipped 2026-06-10. 6 of 8 candidate indicators live (DSR.HOUSEHOLDS + DSR.NFC return HTTP 404 — confirmed BIS gap for IN). **24,957 obs loaded** to `econ.fact_indicator` covering NEER/REER 1994→, Private-NFS DSR 1999→, Credit-to-GDP ratio 1951→, Credit-to-GDP gap 1961→, RBI repo rate daily 1946→. | `scripts.econ.bis.bis_india` |
| **N — Audit + promotion** | Run the load-from-playground command per vendor; verify Phase G coverage map; update wiring map §7.12 and §6 tables; commit. | `econ.fact_indicator` IN rows live; coverage table flipped |
| **O — Prod wiring** | Build `scripts/econ/in/in_monthly.py` (BBG-style orchestrator); user-OK before registering in `scripts/imdr_monthly.py:PIPELINES`. | Orchestrator script committed but **not auto-wired** until user signs off (per [[feedback-no-prod-wiring-without-permission]]) |

Phase A is the unblocker — until DBIE auth proves stable (or we have the replay
flow), nothing downstream is reliable.

Estimate: **6-10 working days end-to-end** for everything except CIMS Phase E/F
(which is parallel and best-effort). The MOSPI / DGCIS scrapes are the biggest
single time sink (Phases G-K), each is ~½-1 day per release format.

## Open questions for the next pass

1. **Auth-header rotation** — does `gjl6p01780417269959196` survive a fresh
   day? If not, what does `security_generateSessionToken` actually return and
   how do we plumb it through `httpx`?
2. **`dbie_getPublicationDataImpala` body shape** — is it `{publication_id,
   table_id}` or is the publication-key hidden inside a deeper structure?
3. **CIMS reachability** — are the 10 CIMS portals on `*.rbi.org.in` and does
   our network pass them through?
4. **MOSPI release format stability** — does MOSPI keep the same XLSX schema
   month-to-month, or do they rebase / restructure mid-year? (We hit this on
   BPS Indonesia.)
5. **DGCIS query-form vs export endpoint** — can we hit the XLSX download URL
   directly with `httpx`, or does the site require a session cookie / token
   from the query form?
6. **CCIL access** — desk has a CCIL terminal login; do we have machine-readable
   credentials we can use for G-Sec yields + MIBOR + corporate bond curve, or
   do we treat CCIL as out-of-scope and live with RBI Bulletin lag?

---

## Appendix A — Worked desk question: "Will increased onshore liquidity translate to lower MIBOR/MIFOR fixings post FCNR flows?"

This is the litmus test for whether the India build can answer real desk
questions. The transmission chain and the corresponding shopping list:

```
FCNR(B) inflow (USD into Indian bank deposit)
  → bank sells USD spot, buys INR              [3.4 spot FX]
  → onshore INR liquidity ↑                    [4.3 LAF / 4.4 Reserve Money]
  → bank hedges FX: USD/INR sell-buy swap      [3.4 RBI fwd book + fwd premia]
  → forward premia compress                    [3.4 FBIL fwd fixings]
  → MIFOR ≈ SOFR + fwd premium → MIFOR ↓       [4.3 MIFOR + 4.3 MIBOR]
  → INR OIS reprices via arbitrage             [4.3 OIS curve]
  → RBI sterilises via VRRR / fwd-buy          [4.4 VRRR + 3.4 RBI fwd book]
  → net effect on MIBOR depends on sterilisation intensity
```

| Step | Series | Cell | Status |
|---|---|---|:---:|
| 1. FCNR stock + flow | FCNR(B) outstanding · NRE · NRO outstanding · NRI Deposits BoP flow | 3.3 | ⚠ DBIE |
| 2. Spot FX absorbed | USD/INR spot · RBI Reference Rate | 3.4 | ✅ + ⚠ |
| 3. Onshore liquidity print | LAF Daily net · Reserve Money M0 · Bankers' Deposits w/ RBI | 4.3 + 4.4 | ⚠ DBIE |
| 4. Bank hedging activity | RBI outstanding forward book · USD intervention spot/fwd | 3.4 | ⚠ DBIE |
| 5. Forward premia signal | FBIL onshore fwd premia 1M/3M/6M/1Y · Citi NDF curve | 3.4 | ⚠ CCIL + ✅ |
| 6. MIFOR transmission | MIFOR/MMIFOR fixings 1M/3M/6M/1Y | 4.3 | ⚠ CCIL — newly added row |
| 7. MIBOR transmission | MIBOR ON/14D/1M/3M | 4.3 | ⚠ CCIL |
| 8. Term-rate arbitrage | INR OIS curve 1M-5Y | 4.3 | ⚠ + ✅ |
| 9. RBI sterilisation | VRRR auction history · Net OMO · Govt cash balance | 4.4 | ⚠ DBIE — newly added rows |
| 10. Regulatory event context | FCNR notification (rate cap / CRR waiver) · MPC stance | §5.1 | ⚠ press-release scrape — needs FCNR-keyword filter |
| 11. Policy reaction function | MPC minutes (forward-guidance language) | §5.1 | ⚠ HTML scrape |

The answer cannot come from data series alone — step 10's regulatory window
(was FCNR(B) rate cap waived? was the special swap window opened?) gates the
size of step 1, and step 11's MPC language gates step 9's sterilisation
intensity. The document corpus in §5 is therefore **load-bearing**, not
optional.

Other desk-question archetypes the build needs to support:

1. **"Where is INR going next month?"** — needs BoP flows · FPI flows (NSDL) · RBI intervention · fwd premia · DXY context · seasonality of remittances.
2. **"How dovish was the latest MPC?"** — needs MPC minutes (votes) + Governor speech + MPR forecast revision history.
3. **"Is the fiscal slippage risk priced in?"** — needs CGA monthly accounts · GST collections · borrowing calendar · 10Y G-Sec yield · term spread · Budget Estimates.
4. **"Are food prices going to push CPI through 6% again?"** — needs CPI sub-groups · CFPI · monsoon data (IMD) · MSP announcements · global commodity proxies.

---

## Final India Checklist

Master punch-list to take India from **0 indicators / 0 events** today to a
production state where the desk-question patterns above are answerable.
Group A = data series, Group B = events/documents, Group C = infra, Group D = sign-off.

Mark items in PRs that close them.

### A. Data series (target: ~150 indicators across 16 cells)

- [x] **A0** DBIE auth durability — captured header confirmed dead 2026-06-10 (returns errorCode 4302). Bootstrap flow live: POST `security_generateSessionToken` w/o auth header → new token in **HTTP response header** `authorization`. Client at `src/imdr/domains/econ/rbi_dbie.py` re-bootstraps on token-expiry mid-call.
- [x] **A1** DBIE FX reserves (TR + FCA + GOLD + SDR + IMF) — `scripts.econ.rbi.rbi_fx_reserves` shipped 2026-06-10; **3,015 obs × 5 indicators** loaded covering 2015→2026, weekly. Latest TR = $682.32 bn (2026-05-28).
- [x] **A5 (partial) — Key Rates dashboard snapshot** — `scripts.econ.rbi.rbi_key_rates` shipped 2026-06-10. The Impala endpoint (`dbie_getPublicationDataImpala`) is wedded to one dashboard regardless of `reportId`, returning 9 rows: Repo / SDF / Reverse Repo / CRR / SLR (event-stamped step functions) + CPI YoY / WPI YoY (monthly latest) + WACR (daily) + Exchange Rate (ambiguous, deferred). 8 indicators emitted; obs_date = last-change / last-release date so MERGE skips on re-run unless a value moved. Discovered also: `dbie_getAllDBIEReports` returns the full 1,225-report catalogue ([discovery/all_reports.json](../../../playground/econ/rbi/discovery/all_reports.json)) — but the time-series-per-report endpoint is still unknown (candidates: `dbie_getElementsDataQuery`, `dbie_getEntityDataQuery`, `dbie_getImpalaDQAction`, `dbie_firstEBRBaseReport`).
- [ ] **A2** DBIE Indicators-tree payload capture — Playwright + network interception for all leaves; produces `discovery/payloads_indicators.json`
- [ ] **A3** Generic `dbie_getPublicationDataImpala` wrapper — decode body shape; ship `playground/econ/rbi/fetch_publication.py`
- [ ] **A4** RBI Bulletin tables (T19C CPI, T27 call money, IESH, Consumer Confidence, etc.) — 31 indicators
- [ ] **A5** RBI DBIE — Exchange Rate · Key Rates · Money Market · G-Sec Turnover · Reserve Money · RBI Balance Sheet · Payment System · Central Govt Market Borrowings · Business of Scheduled Banks · Daily LAF · Sectoral Deployment · Surveys (IESH / OBICUS / SPF / Consumer Confidence)
- [ ] **A6** RBI DBIE — BoP · ITS Services trade · External Debt · NIIP · NRI Deposits (incl. **FCNR(B) / NRE / NRO** stocks) · ECB · FDI · RBI sale/purchase USD · forward book outstanding
- [ ] **A7** RBI DBIE — Corporate sector (5 sub-categories) · Banking Performance (GNPA/NNPA/CRAR) · BSR-1/BSR-2 · NBFC statistics
- [x] **A8 (playground)** MOSPI CPI release scrape — Combined/Rural/Urban + 13 divisions × Index + YoY → **78 indicators × 4 months (Jan-Apr 2026) decoded** in playground 2026-06-10. Listing API `POST /api/latest-release/get-web-latest-release-list` with `search_term="CPI for"` paginates the press-release archive; XLSX path lives at `/uploads/PressRelease/`. Annexure-I parser works for the post-Jan-2026 "2024-base" format; older "2012-base" releases (Annex-I, 7 sheets) still need a second parser. RBI Bulletin T19C carries headline rural+urban back to 2014 as a fallback for the deep-history gap. See [`playground/econ/mospi/discovery/findings.md`](../../../playground/econ/mospi/discovery/findings.md). **Prod-promotion gated on**: (a) `mospi` vendor migration, (b) legacy-format parser, (c) CFPI + Core extraction, (d) user sign-off.
- [x] **A9 (playground)** MOSPI IIP release scrape — total + sectoral (Mining/Mfg/Electricity) + 6 UBC. **20 indicators × 168 months = 3,350 obs decoded** in playground 2026-06-10 via same listing API as A8 (`search_term="Quick Estimates of IIP"`). One XLSX = full history back to Apr 2012; re-runs are MERGE-skip until a new release lands. See [`playground/econ/mospi/discovery/findings.md`](../../../playground/econ/mospi/discovery/findings.md) §"A9 IIP". **Prod-promotion gated on**: shared `mospi` vendor migration + user sign-off (same gates as A8).
- [x] **A10 (playground)** MOSPI NAS quarterly + annual GDP — **35 indicators × 336 obs** decoded 2026-06-10 via same listing API as A8/A9 (`search_term="Provisional Estimates of Annual GDP"`). 12 annual headlines × real + nominal × 4 FYs ≈ 96 obs annual; 11 quarterly headlines × 16 Q ≈ 176 obs quarterly. Date window 2022-04-01 → 2026-01-01. **Critical**: new 2022-23 base year (rolled out Feb 2026) — only 4 FYs/16 Q of back-history in current release; pre-rebase 2011-12-base series live in older releases (deep history backfill deferred). See [`playground/econ/mospi/discovery/findings.md`](../../../playground/econ/mospi/discovery/findings.md) §"A10 NAS GDP". **Prod-promotion gated on**: shared `mospi` vendor + extend to Statement 6/7/8 (nominal + growth rates) + 2011-12-base backfill + user sign-off.
- [~] **A11 (PDF-only — deferred)** MOSPI PLFS — listing API confirms releases live (Annual Report + Quarterly Bulletin + Monthly Bulletin since 2025-08), but **`file_two=null` on every PLFS release** — they ship PDF-only press notes. Headline LFPR / unemployment / worker-population-ratio numbers are embedded in the PDF text. Defer to a PDF-parsing-equipped session.
- [x] **A12 (playground)** DPIIT WPI release scrape — **8 indicators × 1,352 obs** decoded 2026-06-10. One XLS at `eaindustry.nic.in/indx_download_1112/monthly_index_{YYYYMM}.xls` carries the full WPI back to April 2012 (Base 2011-12=100). 870 rows × 169 monthly cols. Headlines emitted: HEADLINE + PRIMARY + FOOD_ART + NONFOOD_ART + MINERALS + CRUDE_NG + FUEL_POWER + MFG (April 2026 headline = 167.0). Auto-discovery via `download_data_1112.asp` link page. See [`playground/econ/dpiit/discovery/findings.md`](../../../playground/econ/dpiit/discovery/findings.md). Bonus discovery: same site has 8-Core Industries XLSX (relates to A26 cluster 1.4). **Prod-promotion gated on**: `dpiit` vendor migration, mfg sub-group extension (14 more series for core-WPI decomp), user sign-off.
- [x] **A13 (playground)** DGCIS MEIDB monthly trade — POST flow + table parser **proven 2026-06-10**. Single-shot POST to `/meidb/commoditywise_{export,import}` with Laravel CSRF + 7-field form (`_token`, `ddMonth`, `ddYear`, `comlev="all"`, `ddCommodityLevel`, `ddReportVal`, `ddReportYear`) returns a 108KB HTML page with **99-row HS-2-digit table** including current month, prior-year same month, YoY %, and FY-YTD comparisons (Mar 2025 smoke test verified: HS 01 Live Animals through HS 10 Cereals all parse cleanly). Multi-month iteration (~144 months × 2 directions = ~288 POSTs for deep history) is the next step but deferred. See [`playground/econ/dgcis/discovery/findings.md`](../../../playground/econ/dgcis/discovery/findings.md).
- [x] **A14 (playground)** MoF / CGA Monthly Accounts scrape — **30 line items × 143 months = 4,182 obs** decoded in playground 2026-06-10. Single `.xlsm` (~520KB) at `cga.nic.in/writereaddata/MonthAccount/MonthAccountDashboard/DAMA dashboard {Month YYYY} Data file{...}.xlsm` carries the full series back to FY 2014-15. Covers: direct taxes (Corp/Inc/STT) · indirect taxes (CGST/IGST/UTGST/CompCess/Customs/Excise/Service Tax legacy) · non-tax receipts (Interest/Dividends/Other) · capital receipts (Loan Recovery/Disinvestment) · expenditure decomp (Revenue/Capital/Interest Pmts/Defence/Pensions/Subsidies/Grants) · 4 deficits (Revenue/Effective Revenue/Fiscal/Primary). Values in INR crore, **cumulative-since-April** (Indian FY convention). See [`playground/econ/cga/discovery/findings.md`](../../../playground/econ/cga/discovery/findings.md). **Prod-promotion gated on**: `cga` vendor migration, BERE + GDP sheet parsers for Budget vs Actual variance, user sign-off.
- [~] **A15 (Next.js SPA — deferred)** DPIIT FDI quarterly — page is a Next.js SSR/SSG SPA at `dpiit.gov.in/publications/fdi-statistics`. The `_next/data/{build}/publications/fdi-statistics.json` endpoint returns HTML not JSON; 0 XHRs captured on plain Playwright load (page might need extra interaction to fetch data). Defer to a session with deeper Playwright work (likely needs `wait_for_selector` or click-through to data tabs).
- [⊘] **A16 (network-blocked)** NSDL FPI — `www.fpi.nsdl.co.in` and `nsdl.co.in` both return `RemoteProtocolError` from our network (HTTP/2 protocol issues, same family as the AOFM blocker per [[project-aofm-blocked]]). Needs the user's daily Chrome via CDP attach (see AOFM workflow) OR an alternate route (Citi vendor feed).
- [ ] **A17** CCIL feed — MIBOR + **MIFOR/MMIFOR** + **FBIL onshore fwd premia** + G-Sec yields 1Y/5Y/10Y + corp bond curve + OIS curve (credentials check needed)
- [⊘] **A18 (network-blocked)** Labour Bureau — `labourbureau.gov.in` / `labourbureaunew.gov.in` / `labourbureau.nic.in` all return `ConnectError` from our network. Needs CDP-attach or alternate route (RBI Bulletin carries CPI-IW too).
- [~] **A19 (PDF-only — deferred)** PPAC — `ppac.gov.in` reachable, but Indian Crude Basket (ICB) + ICR + monthly Flash Reports are all PDF-only at `ppac.gov.in/download.php?file=menu/{timestamp}_{name}.pdf`. No inline data tables, no XLSX. Defer to PDF-parsing session — page lists ~17 monthly PDFs on `prices/internationalprices`.
- [ ] **A20** EPFO monthly payroll release
- [x] **A21** BIS package for IN — `scripts.econ.bis.bis_india` shipped 2026-06-10; 6/8 indicators × 24,957 obs live (NEER/REER broad · DSR PNFS · credit-to-GDP ratio · credit-to-GDP gap · RBI repo rate daily 1946→). DSR.HOUSEHOLDS + DSR.NFC return 404 — confirmed BIS gap for IN.
- [x] **A22** FRED OECD India mirror — 7/16 candidates validated 2026-06-10; **11,589 obs loaded**. Live: CPI YoY (1990→) · CPI level (1990→2024) · IIP (1994→2023) · Real GDP annual (PWT, 1990→2023) · Call money rate (1990→) · INR/USD daily (1990→) + monthly (1990→). Confirmed FRED-absent for IN: OECD harmonised unemployment (`LRHUTTTT*IN*` 400) · OECD 10Y govt yield (`IRLTLT01INM156N` 400) · OECD 3M interbank (`IR3TIB01INM156N` 400) · IMF IFS quarterly GDP (`NGDPRSAXDCINQ` 400). Discount Rate `INTDSRINM193N` validates but is stale (last 2022-07) — use `BIS.POLICY_RATE.IN` instead.
  - **Reproducibility caveat (carried over from FRED architecture):** FRED India entries live in `playground/econ/fred/seed.yml` (gitignored). Same as every other FRED country today. Tracked via Linear `IMD-FRED-PROMOTE` (TBD): move `seed.yml` + `connector.py` to `src/imdr/domains/econ/fred*` so the seed becomes reproducible. Until then, anyone re-running `python -m playground.econ.fred.fetch` must hand-add the India rows from the locally-loaded DB state.
- [~] **A23 (deprioritised 2026-06-10)** GSTN monthly GST collections — investigation found no clean public source. GST Council archive stops at Sept 2023; PIB press releases obfuscate titles inside client-decoded encrypted HTML blobs; gst.gov.in / gstn.org.in are empty shells. **Likely already covered by A14** — CGA Monthly Accounts XLSM carries CGST + IGST + UTGST + GST Compensation Cess as separate line items (sum = total GST collection). PIB monthly press releases are the in-month flash but CGA is the finalised version (~1 month lag). Recommend: treat A14 as authoritative for the *data series*; keep B14 (PIB monthly GST collections release) only as a *document corpus* item. See [`playground/econ/gstn/discovery/findings.md`](../../../playground/econ/gstn/discovery/findings.md).

### B. Events + documents

- [ ] **B1** RBI MPC resolutions — `BS_PressReleaseDisplay.aspx` scraper + per-meeting structured extract (date, repo/SDF/MSF/CRR/SLR, stance, vote)
- [ ] **B2** RBI MPC minutes — `PublicationReport.aspx?ID=911` scraper + per-member vote + rationale extraction
- [ ] **B3** RBI Monetary Policy Report (MPR) PDF — semi-annual; forecast band extraction
- [ ] **B4** RBI Financial Stability Report (FSR) PDF — semi-annual; systemic-risk dashboard + stress-test results
- [ ] **B5** RBI Bulletin "State of the Economy" chapter — monthly PDF extract
- [ ] **B6** RBI Annual Report PDF — annual
- [ ] **B7** RBI Notifications — full archive scrape from `NotificationUser.aspx`; classifier tags (FCNR · NRI · FPI · ECB · CRR · SLR · LRS · macro-prudential · liquidity-ops · G-Sec auction)
- [ ] **B8** RBI Governor + Deputy Governor speeches archive — `BS_speechesview.aspx`
- [ ] **B9** Union Budget speech + Receipts/Expenditure books (annual) — `indiabudget.gov.in`
- [ ] **B10** Economic Survey (annual) — `indiabudget.gov.in/economicsurvey/`
- [ ] **B11** Mid-Year Economic Analysis (annual Dec) — `dea.gov.in`
- [ ] **B12** CGA Monthly Accounts press release — companion to the data scrape in A14
- [ ] **B13** Borrowing calendar (H1 + H2) — RBI press release
- [ ] **B14** GST monthly collections press release — companion to A23
- [ ] **B15** SEBI board outcomes — bond-market structure (FPI debt limits, T+1, derivative norms)
- [ ] **B16** IRDAI board outcomes — insurance G-Sec demand context
- [ ] **B17** DPIIT FDI policy notifications

### C. Infrastructure

- [ ] **C1** `econ.fact_event` table — new migration; columns `(country_id, vendor_id, event_type, event_ts, document_url, summary_text)`
- [ ] **C2** Document storage convention — `data/research/in/{vendor}/{YYYY}/{MM}/{DD}/...` archived; markdown extracts via `pymupdf`
- [ ] **C3** Qdrant `imdr-research` IN-namespace — ingest extracts so Mycroft / Lois can retrieve
- [ ] **C4** **CIMS portal probe** — open all 10 CIMS sub-portals; capture endpoint inventories; produces `discovery/cims_endpoints.json`
- [ ] **C5** **DBIE↔CIMS endpoint mapping** — per-endpoint route-flag in the read layer; produces `playground/econ/rbi/route_map.md`
- [ ] **C6** CCIL terminal credentials — desk has login; confirm machine-readable access for A17
- [ ] **C7** PDF extractor cleanups — base-year change detector for MOSPI CPI / WPI; revision-flag handling
- [ ] **C8** Identity reconciliation — DBIE FX reserves vs FRED OECD mirror · WPI vs DPIIT site · RBI ref rate vs Citi spot
- [ ] **C9** `dim_indicator` IN rows — ~150 codes registered with imdr_code + frequency_id + currency_id

### D. Promotion + sign-off

- [ ] **D1** Wiring-map §7.12 flip — ❌→⚠→✅ per cell, update with each phase
- [ ] **D2** Coverage rollup in `india/index.md` — "X indicators / Y observations / Z events live in IN"
- [ ] **D3** Build `scripts/econ/in/in_monthly.py` orchestrator (BBG-style)
- [ ] **D4** Build `scripts/econ/in/in_daily.py` orchestrator (FX reserves W, FBIL/MIBOR/MIFOR D, LAF D, FPI D)
- [ ] **D5** Build `scripts/econ/in/in_weekly.py` (Reserve Money W, OMO/VRR/VRRR auction results)
- [ ] **D6** Build `scripts/econ/in/in_quarterly.py` (BoP, IIP-Q-rev, NAS GDP, BSR, IIP, Sectoral Deployment publication)
- [ ] **D7** User-OK before registering any of the above in `scripts/imdr_{daily,weekly,monthly,quarterly}.py:PIPELINES` (per [[feedback-no-prod-wiring-without-permission]])
- [ ] **D8** Linear epic created — `IMD-INDIA-ECON` parent + per-phase sub-issues mapped to this checklist
- [ ] **D9** Smoke test on the FCNR-MIFOR worked example end-to-end before declaring "production"

### A. Data series — India Cluster Map additions (2026-06-10)

New rows added after cross-checking the 12-cluster India Macro Read map (see [Appendix B](#appendix-b--india-cluster-map-cross-check) for the full mapping). These live alongside the wiring-cell rows in Groups A–D above; numbering picks up at A24.

- [x] **A24 (playground)** **IMD district-wise cumulative rainfall** — 761 districts × (actual_mm, normal_mm, departure_pct) parsed cleanly from inline JS in `https://mausam.imd.gov.in/responsive/rainfallinformation.php` 2026-06-10. No API call needed — single static GET returns ~250KB HTML w/ amcharts `dataProvider.areas` array. To build a time series: scrape daily, stamp fetch-date as obs_date. Smoke test: 723 districts with valid data, mean departure -35% (early June 9 monsoon, expected). See [`playground/econ/imd/discovery/findings.md`](../../../playground/econ/imd/discovery/findings.md). **Prod-promotion gated on**: (a) `imd` vendor migration, (b) sub-divisional aggregate (36 met regions) — `subDivisionWiseWarningGIS.php` needs probing, (c) `imdr_daily.py` registration, (d) user sign-off.
- [ ] **A25** **CWC reservoir levels** — weekly, 4 zones (N/S/E/W). `cwc.gov.in/reservoir-storage`. Predicts hydropower output + Rabi sowing conditions + drinking-water stress.
- [ ] **A26** **DAC crop sowing area** — weekly during sowing season (Kharif Jun-Sep, Rabi Oct-Mar). `agricoop.gov.in`. Per crop + total acreage YoY.
- [ ] **A27** **POSOCO national power demand** — daily peak load + energy met. `posoco.in/reports/daily-reports`. High-frequency activity proxy (alternative to monthly IIP).
- [ ] **A28** **NHB Residex / RBI HPI** — quarterly housing price indices, 50+ cities. NHB `nhb.org.in/residex/` + RBI quarterly HPI publication.
- [ ] **A29** **MGNREGA spend + person-days** — weekly. MoRD `nrega.nic.in`. Rural distress proxy (counter-cyclical to farm income).
- [ ] **A30** **PM-KISAN disbursement** — installment events. MoA press release.
- [ ] **A31** **MSP minimum support price levels** — annual + event when announced. MoA press release per crop.
- [ ] **A32** **FCI food stocks** — monthly. FCI `fci.gov.in/stocks.php`. Rice + wheat buffer vs norm.
- [ ] **A33** **Agmarknet mandi prices** — daily, ~3,000 mandis × ~300 commodities. `agmarknet.gov.in`. Food-CPI leading indicator at granularity.
- [ ] **A34** **DPIIT PLI scheme commitments** — quarterly (scheme-wise applications + sanctioned investment + actual deployment). `dpiit.gov.in` + scheme-specific dashboards.
- [ ] **A35** **DIPAM disinvestment proceeds** — event-driven. `dipam.gov.in`.
- [ ] **A36** **Ministry of Tourism FTA (Foreign Tourist Arrivals)** — monthly. `tourism.gov.in/Statistics`.
- [ ] **A37** **NBFC sector aggregates** — quarterly. RBI NBFC publication / Financial Stability Report annex.
- [ ] **A38** **IBBI quarterly newsletter — insolvency cases** — quarterly. `ibbi.gov.in`. Corporate stress / refinancing wall proxy.
- [ ] **A39** **NSDL FPI — index-inclusion slice** — daily. Slice the existing NSDL FPI debt flow (A16) into JPM GBI-EM-eligible vs ineligible bonds, and Bloomberg EM-eligible slice. Tracks index-inclusion flow specifically.
- [ ] **A40** **DoF / FAI fertilizer prices** — monthly. `faidelhi.org` + Dept of Fertilizers subsidy dashboard.
- [ ] **A41** **FAO Food Price Index** — monthly (cross-country benchmark). `fao.org/worldfoodsituation/foodpricesindex`. Imported-food inflation reference.
- [ ] **A42** **Baltic Dry Index** — daily (commercial proxy via FRED `BDIY` or paid). Shipping-cost proxy.
- [ ] **A43** **SIAM auto sales** — monthly. `siam.in` press release. PVs + 2-wheelers + tractors (TAMA via separate channel for tractors — rural demand proxy).
- [ ] **A44** **GST e-Way Bill volumes** — monthly + daily. `ewaybillgst.gov.in`. Real-time trade activity proxy.

### B. Events + documents — India Cluster Map additions

- [ ] **B18** **Election Commission of India (ECI) dates** — General + State elections + by-poll dates. `eci.gov.in`. Drives federal-politics + policy-continuity risk.
- [ ] **B19** **GST Council meeting outcomes** — per-meeting notification. `gstcouncil.gov.in`. Tax-reform event corpus.
- [ ] **B20** **MoCI / DPIIT PLI scheme launches + reviews** — event press releases.
- [ ] **B21** **MoA MSP announcements** — Kharif (May/Jun) + Rabi (Oct) annual cycles.
- [ ] **B22** **IMD seasonal forecasts** — Long-Range Forecast Apr + update Jun for SW monsoon; NE-monsoon forecast Oct. Document corpus.
- [ ] **B23** **Customs notifications (CBIC)** — BCD changes, tariff revisions. `cbic.gov.in`. Trade-policy event corpus.
- [ ] **B24** **DEA Mid-Year Economic Analysis** (already in B11) — confirmed within cluster-11 coverage.

### A45 — 8-Core Industries (added 2026-06-10; previously mis-numbered A26)

- [x] **A45 (playground)** 8-Core Industries Index — same `eaindustry.nic.in` vendor as A12 WPI. One XLSX (`/eight_core_infra/Core_Industries_2011_12_{YYYYMMDD}.xlsx`) carries full history Apr 2011 → Apr 2026 (180 months). 9 sectors (Overall + Coal/Crude/NG/Petroleum/Fertilizers/Steel/Cement/Electricity) × LEVEL + YOY = **18 indicators × 3,150 obs** in playground 2026-06-10. ICI leads the IIP by ~10 days each month — important high-frequency activity indicator. Shares `dpiit` vendor migration with A12. (Numbered A45 to avoid collision with original A26 = DAC crop sowing.)

### Reachability findings (2026-06-10) for vendors NOT yet decoded

| Vendor | URL | Status | Disposition |
|---|---|---|---|
| NSDL FPI | `fpi.nsdl.co.in`, `nsdl.co.in` | `RemoteProtocolError` from our network | Needs CDP-attach or Citi feed |
| Labour Bureau | `labourbureau.gov.in/.nic.in` (all variants) | `ConnectError` | Needs CDP-attach; or use RBI Bulletin proxy |
| CWC reservoir | `cwc.gov.in/reservoir-storage` | 401 (auth required?) | Investigate auth or use water-resources dashboard alternative |
| Agmarknet | `agmarknet.gov.in/` | 403 (UA blocked?) | Try with browser UA + cookies |
| POSOCO | `posoco.in/reports/...` | `ConnectError` | Site might have moved; check `grid-india.in` or `npp.gov.in` |
| NREGA | `nrega.nic.in/` | 200 but 451-byte shell | JS-rendered or login wall |
| Ministry of Tourism | `tourism.gov.in/` | 200, 98KB | Reachable — defer parsing |
| IBBI insolvency | `ibbi.gov.in/` | 200, 2.7MB home | Reachable — defer parsing |
| FCI food stocks | `fci.gov.in/stocks.php` | 200, 45KB but no inline data | JS-rendered table — needs Playwright |
| DPIIT FDI | `dpiit.gov.in/publications/fdi-statistics` | 200, Next.js SPA | Needs deeper Playwright with click-through |
| MOSPI PLFS | listing API works, all releases PDF-only | OK but no XLSX | PDF parsing required |
| PPAC fuel | `ppac.gov.in/` | 200, all data via PDF downloads | PDF parsing required |

**Network-blocked items** are likely solvable via the same CDP-attach pattern documented for AOFM (see [[feedback-aofm-fresh-profile-per-run]] in memory) — attach to user's daily Chrome session.

### Out of scope for the initial build

- ❌ Paid feeds — S&P Global PMI · CMIE high-frequency unemployment · CEIC/Macrobond mirror
- ❌ MOSPI PPI proper (pilot only — revisit when official series launches)
- ❌ Microdata (PLFS person-level, ASI plant-level, BSR branch-level) — only published aggregates
- ⏸ State-level fiscal + state-level CPI (defer to Phase 2)

---

## Appendix B — India Cluster Map cross-check

Cross-checking the 12-cluster *India Macro Read* dashboard (see image in
docs/) against the coverage plan above. Each bullet is tagged:
- ✅ in plan already
- ⚠ partial / needs a derivation step
- ❌ missing → added to checklist Group A24+ or B18+ above
- ⏸ deferred (paid feed / structural)

### Cluster 1 — Domestic Demand / Consumption

| Bullet | Status | Mapped to |
|---|:---:|---|
| Urban demand — salaried jobs | ⚠ | A20 EPFO payroll (formal employment) |
| Urban demand — services income | ❌ | derived from PFCE services component (1.1) |
| Urban demand — credit | ✅ | A5 RBI Sectoral Deployment — Personal Loans |
| Urban demand — confidence | ✅ | A5 RBI Consumer Confidence Survey (CCS) |
| Rural demand — farm income | ❌ | requires DAC crop output × MSP × MSP-procurement composite — derived |
| Rural demand — monsoon | ❌ | **A24 IMD rainfall — NEW** |
| Rural demand — wages | ✅ | A18 Labour Bureau rural wages + WRI |
| Rural demand — transfers (MGNREGA / PM-KISAN) | ❌ | **A29 MGNREGA + A30 PM-KISAN — NEW** |
| Rural demand — MSP | ❌ | **A31 MSP — NEW** (data + B21 events) |
| Household balance sheets — savings | ⚠ | derived from BoP / household financial assets |
| Household balance sheets — debt | ✅ | BIS DSR + Credit-to-GDP + Sectoral Deployment HH |
| Household balance sheets — real rates | ⚠ | derived = Repo − CPI YoY |
| Household balance sheets — housing wealth | ❌ | **A28 NHB Residex + RBI HPI — NEW** |
| Demographics — youth / migration / participation / mix | ⏸ | Census + NSSO microdata — structural, deferred |

### Cluster 2 — Investment / Capex / Construction

| Bullet | Status | Mapped to |
|---|:---:|---|
| Private capex — profits | ⚠ | RBI Corporate Sector statistics (A7) — annual lag |
| Private capex — capacity use | ✅ | A5 RBI OBICUS survey (quarterly) |
| Private capex — policy certainty | ⏸ | qualitative — picked up via §5 event corpus |
| Private capex — cost of capital | ✅ | A5 WALR / MCLR + CCIL corp bond curve (A17) |
| Public capex — central | ✅ | A14 CGA monthly accounts (capital expenditure split) |
| Public capex — state capex | ⚠ | A6 RBI State Govt finances (annual lag) |
| Real estate — affordability | ❌ | **A28 NHB Residex / RBI HPI — NEW** |
| Real estate — approvals / inventory | ⏸ | PropEquity / Knight Frank — paid |
| Real estate — financing | ✅ | A5 RBI Sectoral Deployment — Housing Loans |
| Manufacturing push — PLI | ❌ | **A34 DPIIT PLI commitments — NEW** + B20 events |
| Manufacturing push — China+1 | ⏸ | derived from DGCIS commodity-level trade composition |
| Manufacturing push — logistics | ❌ | LPI not refreshed annually; use port throughput / e-Way Bill (A44) |
| Manufacturing push — export capacity | ✅ | A13 DGCIS exports + ITPI indices |

### Cluster 3 — Labour / Supply / Productivity

| Bullet | Status | Mapped to |
|---|:---:|---|
| Employment quantity — job creation / unemployment / LFPR | ✅ | A11 MOSPI PLFS (Annual + Quarterly Urban) |
| Employment quantity — informal vs formal | ⚠ | PLFS reports the split; EPFO (A20) tracks formal-only |
| Employment quality — wages | ✅ | A18 Labour Bureau WRI + PLFS earnings |
| Employment quality — productivity | ⚠ | derived = GVA / employment from NAS + PLFS |
| Employment quality — skill mismatch | ⏸ | NSSO unit-level surveys — deferred |
| Supply capacity — utilisation | ✅ | RBI OBICUS (cross-ref 2.3) |
| Supply capacity — bottlenecks / intermediate imports | ⚠ | DGCIS HS-chapter import composition |
| Infrastructure — ports / roads / power / digital | ❌ | port throughput (IPA), Indian Railways monthly, **A27 POSOCO — NEW**; logistics → A44 e-Way Bill |

### Cluster 4 — Agriculture / Monsoon / Food

| Bullet | Status | Mapped to |
|---|:---:|---|
| Rainfall — onset / distribution / dry spells | ❌ | **A24 IMD — NEW** + B22 seasonal forecasts |
| Rainfall — reservoir levels | ❌ | **A25 CWC weekly — NEW** |
| Crops — kharif / rabi / sowing / yields / acreage | ❌ | **A26 DAC sowing area — NEW** |
| Food supply — cereals / pulses / vegetables / oils / milk | ⚠ | CPI sub-groups (A8) + Agmarknet wholesale (**A33 — NEW**) + FCI stocks (**A32 — NEW**) |
| Rural spillovers — incomes / migration / demand | ⚠ | composite — derives from A29 MGNREGA + A18 rural wages + A11 PLFS rural participation |

**Cluster 4 is the single largest gap in the original plan.** Six new data series (A24-A26, A32-A33, B22) and one new vendor cascade (IMD + CWC + DAC + Agmarknet + FCI) added.

### Cluster 5 — Inflation Pipeline

| Bullet | Status | Mapped to |
|---|:---:|---|
| Food — weather / perishables / MSP / stock mgmt | ⚠ → ✅ once Cluster 4 ships | A24 IMD, A31 MSP, A32 FCI, A33 Agmarknet |
| Fuel / energy — crude / LPG / electricity / taxes | ✅ | A19 PPAC + Customs notifications (B23) |
| Core goods — import prices / FX / supply chains | ⚠ | DGCIS UVI + Citi spot + global GSCPI proxy |
| Core services — housing / health / education / telecom / wages | ⚠ | CPI sub-groups (A8) + WPI services pilot (deferred) |
| Expectations — credibility / wage indexation | ✅ | A5 RBI IESH + DA-hike events (B-class) |

### Cluster 6 — Fiscal / Public Sector

| Bullet | Status | Mapped to |
|---|:---:|---|
| Revenue — GST / income tax / corporate tax / non-tax | ✅ | A14 CGA + A23 GSTN |
| Expenditure — capex / subsidies / welfare / defence / interest | ⚠ | A14 CGA totals; subsidies + interest-bill need explicit line-items (Budget annex) |
| States — capex / power subsidies / off-budget | ⚠ | A6 RBI State Govt finances; off-budget needs Budget annex parsing |
| Debt / deficit — borrowing / fiscal impulse / crowding out | ✅ | A6 RBI Central Govt Market Borrowings + DJPPR equivalent (none for IN — RBI is the issuer) |

New: **A35 DIPAM disinvestment** added (revenue side, important budget-arithmetic item).

### Cluster 7 — Monetary / Liquidity / Rates

| Bullet | Status | Mapped to |
|---|:---:|---|
| RBI stance — repo / corridor / liquidity / communication | ✅ | A5 Key Rates + B1-B3 MPC events |
| Transmission — deposits / lending rates / MIBOR / funding costs | ✅ | A5 WALR/WAFR/WATDR + A17 MIBOR/MIFOR |
| Bond market — G-sec yields / term premium / supply / OMO | ⚠ | A17 CCIL G-sec curve; term premium derived; OMO events scattered across press releases |
| Financial conditions — real rates / liquidity / spreads / equity | ✅ | A5 Daily LAF + corp bond spreads (A17) + equity domain |

Fully covered.

### Cluster 8 — Banking / Credit / Balance Sheets

| Bullet | Status | Mapped to |
|---|:---:|---|
| Bank health — NPLs / provisioning / capital / deposits | ✅ | A7 RBI Banking Performance |
| Credit cycle — retail / MSME / corporate / NBFC / rural | ⚠ | A5 Sectoral Deployment covers retail+corporate+rural; **A37 NBFC aggregates — NEW**; MSME sub-cut needs RBI MSME annex |
| Household leverage — mortgages / personal / unsecured | ✅ | A5 Sectoral Deployment Housing + Personal |
| Corporate balance sheets — leverage / cash flows / refi / insolvency | ⚠ | A7 RBI Corporate Sector; **A38 IBBI insolvency cases — NEW** |

### Cluster 9 — External Sector / Current Account

| Bullet | Status | Mapped to |
|---|:---:|---|
| Goods trade — oil / electronics / gold / chemicals / engineering | ✅ | A13 DGCIS commodity-level (HS chapter) |
| Services exports — IT / business / tourism / GIC | ⚠ → ✅ once A36 ships | RBI BoP services breakdown (A6) + **A36 Tourism FTA — NEW** + IT exports via RBI BoP; GIC not officially tracked |
| Remittances — Gulf / US / diaspora | ✅ | A6 RBI BoP Secondary Income + Remittances Survey |
| Current account — ToT / import demand / export demand | ✅ | A6 BoP CA + DGCIS UVI |

### Cluster 10 — Capital Flows / FX / Reserves

| Bullet | Status | Mapped to |
|---|:---:|---|
| FDI — manufacturing / services / infrastructure | ✅ | A15 DPIIT FDI quarterly |
| Portfolio flows — debt / equity / global risk / **index inclusion** | ⚠ → ✅ once A39 slice ships | A16 NSDL FPI total + **A39 index-inclusion slice — NEW** |
| INR — oil / USD / carry / relative rates / intervention | ✅ | A17 + A6 RBI Sale/Purchase USD + derived carry |
| Reserves — adequacy / buffer / FX management | ✅ | A1 RBI DBIE FX reserves 5-way breakdown |

### Cluster 11 — Structural / Institutional / Political

Mostly **event corpus**, not time-series. Mapped to §5 Events:

| Bullet | Status | Mapped to |
|---|:---:|---|
| Reforms — ease of doing business / labour / land / logistics | ⚠ | Press release scrape + Parliament passage events (B-class) |
| Federal politics — state-centre / elections / continuity | ❌ | **B18 ECI election dates — NEW** |
| Digitalisation — UPI / Aadhaar / formalisation / financial inclusion | ⚠ | NPCI UPI volumes monthly (public); Aadhaar enrolment events |
| Regulation — tariffs / localisation / taxes / compliance | ⚠ | **B19 GST Council + B23 Customs notifications — NEW** |

### Cluster 12 — Global / Geopolitical / Climate

| Bullet | Status | Mapped to |
|---|:---:|---|
| Global growth — US / China / Europe / trade cycle | ✅ | covered via existing US/EU/JP/CN/HK panels |
| Commodity shocks — oil / gas / fertilizer / food | ⚠ → ✅ once A40+A41 ship | A19 PPAC crude + **A40 fertilizer — NEW** + **A41 FAO Food Price Index — NEW** |
| Geopolitics — shipping / sanctions / supply chains | ⚠ | **A42 Baltic Dry — NEW** + Suez/Red Sea events via news |
| Climate stress — heatwaves / floods / water stress / power demand | ❌ | **A24 IMD + A25 CWC + A27 POSOCO — NEW** (cross-ref Clusters 4 + 3) |

### Summary of gap-closures from this cluster-map cross-check

**21 new line items** added to the checklist (Group A24-A44 + B18-B23):
- 14 new data series (IMD / CWC / DAC / POSOCO / NHB / MGNREGA / PM-KISAN / FCI / Agmarknet / PLI / DIPAM / Tourism FTA / NBFC / IBBI / NSDL slice / Fertilizer / FAO / Baltic Dry / SIAM / e-Way Bill)
- 7 new event sources (ECI / GST Council / PLI scheme launches / MoA MSP / IMD seasonal forecasts / CBIC customs / DEA mid-year)

**Biggest gaps closed:** Cluster 4 (Agriculture/Monsoon, was ❌ end-to-end), Cluster 2 housing-side (NHB Residex), Cluster 11 (Structural/Political event corpus).

**Vendor cascade additions:** IMD · CWC · DAC (Dept of Ag & Coop) · POSOCO · NHB · MoRD (MGNREGA) · MoA (MSP / PM-KISAN) · FCI · Agmarknet · DPIIT (PLI) · DIPAM · Ministry of Tourism · IBBI · DoF / FAI · FAO · ECI · GST Council secretariat · CBIC. Most have no formal API — HTML scrape / XLSX / PDF.

---

## Cross-refs

- [`index.md`](index.md) — landing page + access paths.
- [`_playground/rbi.md`](_playground/rbi.md) — RBI playground state.
- [`_playground/rbi_explore.md`](_playground/rbi_explore.md) — captured screenshots.
- [`../../../playground/econ/rbi/discovery/findings.md`](../../../playground/econ/rbi/discovery/findings.md) — full DBIE endpoint catalogue.
- [`../macro_economy_wiring_map.md#712-india-in`](../macro_economy_wiring_map.md#712-india-in) — coverage tracker.
- [`../onboarding_new_country.md`](../onboarding_new_country.md) — 5-step workflow.
- [`../indonesia/id_coverage_plan.md`](../indonesia/id_coverage_plan.md) — Indonesia analogue (worked example).
- [`../korea/kosis_kr_coverage_plan.md`](../korea/kosis_kr_coverage_plan.md) — Korea analogue.
