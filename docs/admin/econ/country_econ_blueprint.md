# Country Econ Data Blueprint — Indicator Catalogue

**Purpose**: The exhaustive, country-agnostic catalogue of every econ time-series we want per cluster. The *what*.

- The **how-to-use this catalogue** (fork into a country tracker, vendor cascade, build order, identity checks, wiring-map reconciliation) lives in [onboarding_new_country.md](onboarding_new_country.md).
- The **per-country status** (which cells have which indicators) lives in [macro_economy_wiring_map.md](macro_economy_wiring_map.md).
- The **per-country reference** (vendor + table id + source code per series) lives in `docs/admin/econ/{country}/` (e.g. [korea/korea_indicator_inventory.md](korea/korea_indicator_inventory.md)).

Structure mirrors [macro_economy_wiring_map.md](macro_economy_wiring_map.md) — 4 engines × 4 cells × N indicators per cell. Each item carries:
- **What** — the series name
- **Cadence** — the *minimum acceptable* frequency
- **Why** — the macro mechanism this feeds

Status convention: ✅ have, ⚠ partial, ❓ unknown source, ❌ not available.

---

## 1. Growth Engine

### 1.1 Private Demand

Household-side demand and credit dynamics.

| Indicator | Min cadence | Why |
|---|:---:|---|
| Retail sales index (value, nominal) | M | Headline consumption proxy — captures both volume and price effects |
| Retail sales index (volume, real) | M | Real consumption growth, the cleanest demand read |
| Retail sales (seasonally adjusted) | M | MoM momentum read — what markets quote |
| Retail sales by segment (department / discount / convenience / specialised) | M | K-shape and discretionary-vs-staples splits |
| Auto sales (units) | M | Big-ticket discretionary; rate-sensitive |
| Consumer Confidence Index (composite) | M | Sentiment thermometer; leading indicator for consumption |
| Consumer survey: current living standard | M | Concurrent household stress gauge |
| Consumer survey: expected economic situation | M | Forward-looking confidence |
| Consumer survey: expected employment | M | Leading labour signal |
| Consumer survey: expected interest rates | M | Household rate-cycle expectations |
| Household credit aggregate (stock) | Q | Leverage cycle — primary macropru concern |
| Household loans flow (monthly) | M | Credit-cycle pulse, splits housing/unsecured |
| Household disposable income | Q | Real purchasing-power base |

### 1.2 Fiscal Demand

Government's direct contribution to demand + the funding side.

| Indicator | Min cadence | Why |
|---|:---:|---|
| Central government total revenue | A (M preferred) | Fiscal capacity; tax-collection cycle |
| Central government total expenditure | A (M preferred) | Fiscal impulse magnitude |
| Central government balance / net lending | A | Fiscal deficit, primary bond-supply driver |
| Direct taxes (income, corporate, capital gains) | A (M preferred) | Tied to nominal-income + asset-price cycle |
| Indirect taxes (VAT, excise, customs) | A (M preferred) | Tied to nominal-consumption cycle |
| Government final consumption expenditure | Q | Direct GDP contribution from gov purchases |
| Government investment / GFCF | Q | Infrastructure cycle |
| Gross government saving | A | Closes the public-sector capital account |
| Government debt-to-GDP (gross + net) | Q | Sovereign-risk anchor |
| Sub-national fiscal balances (states/provinces) | A | Hidden fiscal stance for federal economies |
| Sovereign bond issuance schedule | EVENT | Supply-cycle for rates desk |

### 1.3 External Demand

The export-led component of growth.

| Indicator | Min cadence | Why |
|---|:---:|---|
| Goods exports (BoP basis, USD) | M | Cleanest external-demand pulse, FX-adjusted by definition |
| Goods imports (BoP basis, USD) | M | Domestic-absorption + capex demand proxy |
| Goods trade balance (BoP basis) | M | Headline trade gauge |
| Goods exports (customs basis) | M | Faster release than BoP; first-look read |
| Goods imports (customs basis) | M | Same — early-month signal |
| Export value index (2020=100) | M | Smoothed nominal-trade gauge |
| Export volume index (2020=100) | M | Real-trade gauge ex price moves |
| Import value index | M | Symmetric to export side |
| Import volume index | M | Real domestic absorption |
| Exports by country (top 5-8 partners) | M | Geopolitical-exposure + trade-war signal |
| Exports by product (top 5-8 categories) | M | Sector-mix exposure (tech, autos, commodities, etc.) |
| Inventories / stock cycle | Q | GDP-volatility contributor |
| GDP exports + imports (real, QoQ + YoY) | Q | Cycle position vs nominal headline |

### 1.4 Macro Core

GDP itself + the activity + labour reads that nowcast it.

| Indicator | Min cadence | Why |
|---|:---:|---|
| Real GDP (QoQ SA %) | Q | Concurrent growth momentum |
| Real GDP (YoY %) | Q | Through-the-year growth — comparable internationally |
| Real GDP level (chain-linked) | Q | Used for ratio denominators |
| Nominal GDP level | Q | Inflation-adjusted balance sheet anchor |
| GDP deflator | Q | Implicit price index — second core inflation read |
| GDP by economic activity (mfg, services, construction, agri, mining) | Q | Sector decomposition |
| GDP by expenditure (PCE, Gov, GFCF, X, M, Inv) | Q | Demand-side decomposition |
| Growth contribution by component (% pts) | Q | Identifies the swing factor |
| All-Industry Production Index (IIP) | M | Monthly real-activity headline |
| Industrial Production Index | M | Manufacturing cycle |
| Services Production Index | M | Domestic-services cycle |
| Mfg Capacity Utilisation Rate | M | Output gap proxy |
| Business Sentiment Index — current/realised (all + mfg) | M | Concurrent corp sentiment |
| Business Sentiment Index — outlook (all + mfg) | M | Leading corp sentiment |
| Manufacturing PMI | M | S&P Global / Markit — global comparability |
| Services PMI | M | Same — services cycle |
| Employment level | M | Labour-side headline |
| Unemployment rate (SA) | M | BOK/CB reaction-function input |
| Labour force participation rate | M | Structural slack |
| Employment-to-population ratio | M | Broadest utilisation |
| Job openings / vacancy rate | M | Slack — leading wage signal |
| Hires + quits + separations | M | Labour-market churn (US-style JOLTS) |

---

## 2. Inflation Engine

### 2.1 Input Costs

Upstream price pressures + FX-pass-through.

| Indicator | Min cadence | Why |
|---|:---:|---|
| Import price index (local-ccy basis) | M | Direct CPI feed including FX move |
| Import price index (USD basis) | M | World-price input ex-FX |
| Import price ex-oil / ex-energy | M | Core import inflation read |
| Energy supply prices (electricity, gas tariffs) | M | Direct CPI energy-component input |
| Commodity import volumes (oil, gas, food, metals) | M | Volume × world-price decomp for trade-effect modelling |
| Supply-chain pressure index (NY Fed GSCPI / similar) | M | Global-bottleneck overlay |
| FX pass-through gauge (Import KRW vs USD spread) | M | Country-specific pass-through magnitude |

### 2.2 Producer Prices

Pipeline-inflation indicators that lead CPI.

| Indicator | Min cadence | Why |
|---|:---:|---|
| PPI total / All-items | M | Headline pipeline-inflation gauge |
| PPI by sector (mfg, services, agri, utilities, mining) | M | Identifies cost-push origin |
| PPI excl. food + energy | M | Core PPI for trend |
| Export price index (own production) | M | Output-pricing power gauge |
| Domestic-input vs imported-input price split | M | Local vs imported inflation share |
| Wholesale margins / inventory-to-sales | M | Pricing-power gauge between PPI and CPI |
| Stage-of-processing PPI (raw → intermediate → final) | M | Pipeline timing through inflation chain |

### 2.3 Domestic Costs

Wages, rents, services, expectations — the sticky-inflation drivers.

| Indicator | Min cadence | Why |
|---|:---:|---|
| Average hourly earnings | M | Direct wage-side inflation feed |
| Wage growth rate (YoY %) | M | Pace of wage-price spiral risk |
| Wages by sector (mfg, services, public) | M | Composition of wage growth |
| Wage tracker indices (Atlanta Fed style) | M | Cohort-controlled wage gauge |
| Mfg capacity utilisation | M | Output gap — high util → pricing power |
| Services capacity / vacancy rate | M | Sticky-services pricing power |
| Inflation expectations 1Y (survey) | M | Direct CB reaction-function input |
| Inflation expectations 3Y / 5Y (survey) | Q | Anchoring measure |
| Inflation perceptions (current) | M | Behavioural-pricing proxy |
| Rent component of CPI | M | Largest sticky-services bucket |
| Services CPI ex-energy | M | Underlying services inflation |
| Wage-bargaining outcomes (where applicable) | EVENT | Step-changes in wage costs |

### 2.4 CPI Pressure

The headline inflation prints + structural-persistence measures.

| Indicator | Min cadence | Why |
|---|:---:|---|
| Headline CPI (index level, base year) | M | The headline print |
| Headline CPI (MoM %) | M | Concurrent momentum |
| Headline CPI (YoY %) | M | Through-the-year — markets + CB target |
| Headline CPI (YTD or year-average %) | M | CB target-trajectory check |
| Core CPI ex-food + energy (YoY) | M | Standard core measure |
| Core CPI — country-specific (trimmed mean / sticky / median) | M | CB's own preferred core |
| CPI by major group (food, energy, services, goods, housing) | M | Component contributions |
| CPI services component | M | Sticky-inflation gauge |
| CPI goods component | M | Trade-side inflation gauge |
| Living-cost CPI / necessities | M | Public-perception + political-pressure gauge |
| Fresh-food CPI | M | Volatile short-term shock |
| CPI breadth (share of components above 2%) | M | Persistence vs transitory test |
| Sticky-flexible CPI split (Atlanta Fed style) | M | Component-by-component decomposition |
| Real income squeeze (CPI – wages, YoY) | M | Real-purchasing-power gauge |

---

## 3. External & FX

### 3.1 Terms of Trade

Export vs import price ratio — the national-income shock channel.

| Indicator | Min cadence | Why |
|---|:---:|---|
| Net barter ToT (commodity ToT) | M | Price-of-exports / price-of-imports |
| Income ToT (vol-adjusted) | M | Purchasing-power of exports — captures volume + price |
| Export price index (own series, not the one in 2.1) | M | Output-side price |
| Import price index | M | Already captured in 2.1 — listed here for cross-ref |
| Real income gain/loss from ToT change | A | Annual national-income effect (derived) |

### 3.2 Current Account

The flow-of-goods/services/income across the border.

| Indicator | Min cadence | Why |
|---|:---:|---|
| Current Account total balance (NSA) | M | KRW/EM-FX long-run anchor |
| Current Account total balance (SA) | M | Cycle-stripped read |
| Current Account % of GDP | Q | Sustainability metric |
| Goods balance | M | Dominant CA component for most countries |
| Services balance | M | Often chronic deficit (travel, IP) |
| Primary income balance | M | Return on the country's NIIP |
| Secondary income balance (transfers, remittances) | M | Structural; large for some EM |
| Goods exports (already in 1.3 External Demand) | M | Cross-ref |
| Goods imports (already in 1.3) | M | Cross-ref |
| Services sub-cuts: travel, transport, IP rights, construction, business services | M | Identify which service drives the balance |
| Primary income sub-cuts: compensation of employees, investment income | M | Investment-income tied to NIIP × yield |

### 3.3 Capital Account / Financial Account (BPM6)

The funding side of the CA — what's financing or being financed.

| Indicator | Min cadence | Why |
|---|:---:|---|
| Financial Account, total net | M | Headline capital-flow gauge |
| Direct Investment, net | M | Long-term capital — quality |
| Direct Investment, assets (outward FDI) | M | Domestic-corp foreign expansion |
| Direct Investment, liabilities (inward FDI) | M | Foreign appetite for local equity/plants |
| Portfolio Investment Equity, net | M | Fast-money equity flows |
| Portfolio Investment Equity, assets | M | Outward equity holdings |
| Portfolio Investment Equity, liabilities | M | Foreigner equity holdings — vol-sensitive |
| Portfolio Investment Debt, net | M | Fast-money bond flows |
| Portfolio Investment Debt, assets | M | Outward debt holdings |
| Portfolio Investment Debt, liabilities | M | Foreigner bond holdings — yield-sensitive |
| Financial Derivatives, net assets | M | Hedging-flow proxy |
| Other Investment, net (loans + currency + trade credit) | M | Most-volatile bucket; bank-funding gauge |
| Other Investment, assets | M | Domestic-bank lending offshore |
| Other Investment, liabilities | M | Foreign-bank lending into country |
| Reserve Assets, transactional change | M | CB FX intervention proxy |
| Errors and Omissions | M | Unrecorded-capital-flight proxy |
| International Investment Position (IIP) — net | Q | Stock counterpart to FA flows |
| External debt total (short + long) | Q | External-financing-risk gauge |

### 3.4 FX / REER

The exchange-rate side — sits at the intersection with the market-data layer.

| Indicator | Min cadence | Why |
|---|:---:|---|
| Spot FX rate vs USD | D | Headline; cointegrates with rate differentials |
| Spot FX rate vs key crosses (EUR, JPY, CNY) | D | Trade-weight differentials |
| NDF curve (for restricted ccys) | D | Forward-rate market view |
| FX implied volatility (ATM, 1M / 3M / 12M) | D | Risk gauge |
| FX risk reversal (25-delta) | D | Asymmetric risk premium |
| BIS Nominal Effective Exchange Rate (NEER, broad) | M | Trade-weighted FX gauge |
| BIS Real Effective Exchange Rate (REER, broad) | M | Competitiveness gauge (FX adjusted for inflation differentials) |
| FX reserves total (stock) | M | Intervention-headroom gauge |
| FX reserves composition (USD / EUR / JPY / GBP / Gold / SDR) | M | Diversification + valuation effects |
| CB FX intervention proxy (reserve change minus valuation) | M | Active vs passive reserve management |
| FX swap-line drawings (CB-CB) | EVENT | Liquidity-stress flag |

---

## 4. Policy Transmission

### 4.1 Demand Transmission

How policy reaches consumption + capex via the credit channel.

| Indicator | Min cadence | Why |
|---|:---:|---|
| Bank lending standards / attitude survey — overall | Q | SLOOS-equivalent — credit-cycle leading indicator |
| Bank lending standards — by borrower type (large corp, SME, household, mortgage) | Q | Where the channel is open/closed |
| Bank loan demand survey | Q | Demand-side credit pulse |
| Total bank loans (stock) | M | Aggregate credit headline |
| Household loans (stock + flow) | M | Consumer-credit cycle |
| Household mortgage loans | M | Primary housing-wealth channel feed |
| Household unsecured / credit-card debt | M | Stress-test bucket |
| Corporate loans (stock + flow) | M | Capex-cycle pulse |
| Loan rates — new vs outstanding split | M | Pass-through speed gauge |
| Mortgage rates (new origination) | M | Direct housing-channel input |
| BIS credit-to-GDP gap | Q | Macro-financial cycle gauge |
| Loan-to-deposit ratio | M | Bank funding stress |
| Loan growth (YoY %) | M | Credit-impulse derived |
| Housing transactions (volume + price) | M | Wealth-channel concurrent gauge |

### 4.2 Balance Sheets

Sectoral leverage + asset-quality. The constraint that gates transmission.

| Indicator | Min cadence | Why |
|---|:---:|---|
| Household debt / GDP | Q | Top-line household-leverage |
| Household debt service ratio (DSR, BIS) | Q | Servicing burden — sensitivity to rate moves |
| Corporate debt / GDP | Q | Top-line corp-leverage |
| Corporate financial ratios — Equity-to-Assets | A | Capitalisation |
| Corporate financial ratios — Debt ratio | A | Leverage |
| Corporate financial ratios — Current ratio | A | Short-term solvency |
| Corporate financial ratios — Quick ratio | A | Strict liquidity |
| Corporate financial ratios — Interest coverage | A | Debt-service capacity |
| Corporate financial ratios — Total borrowings to assets | A | Debt loading |
| Bank Tier-1 / CET1 capital ratio | Q | Bank capitalisation |
| Bank Total Capital Ratio (BIS) | Q | Regulatory capital |
| Bank Non-Performing Loan (NPL) ratio | Q | Asset-quality headline |
| Bank loan-loss provisions / loans | Q | Forward-looking NPL signal |
| Bank Return on Assets (ROA) | Q | Profitability under stress |
| Government debt / GDP | Q | Sovereign-leverage |
| External debt total (already in 3.3) | Q | Cross-ref |
| Financial Stability Indicator composite (CB FSR) | EVENT | CB's own stress read |

### 4.3 Financial Conditions

Real rates, curve, spreads — the price of credit + risk.

| Indicator | Min cadence | Why |
|---|:---:|---|
| Policy rate (current) | EVENT | The reaction-function output |
| Money-market rate (call money / overnight) | D | Closest concurrent policy-rate proxy |
| 1M / 3M / 6M / 12M T-bill or interbank rates | D | Short-end curve |
| 2Y / 5Y / 10Y / 30Y govt bond yields | D | Belly + long-end curve |
| Term spread (10Y - 2Y, 10Y - 3M) | D | Yield-curve signal |
| Real rates (nominal yields − inflation expectations) | D | True monetary stance |
| Breakeven inflation rates (linker - nominal) | D | Market inflation expectations |
| IRS curve key tenors (1Y, 2Y, 5Y, 10Y) | D | Bank-funding curve |
| Corporate bond yields by rating (IG, HY) | D | Credit-risk pricing |
| Credit spreads (IG OAS, HY OAS, BBB-Treasury) | D | Risk-appetite gauge |
| Sovereign CDS (5Y) | D | Sovereign-risk premium |
| Bank lending rates — new HH + corp | M | Concurrent retail price of credit |
| Bank deposit rates — new + outstanding | M | Bank funding cost |
| Composite cost of funds | M | Aggregate bank-funding gauge |
| Equity index level (broad market) | D | Wealth-channel + sentiment |
| Equity index volatility (VIX-equivalent) | D | Risk-appetite gauge |

### 4.4 Policy Reaction

Central bank + fiscal reaction function inputs and outputs.

| Indicator | Min cadence | Why |
|---|:---:|---|
| Policy rate (level) | EVENT | The action |
| Policy rate (changes) | EVENT | Magnitude + direction of moves |
| Discount rate / Lombard rate | EVENT | Penalty rate at the corridor edge |
| Reserve requirement ratio | EVENT | Quantity tool — applies in some EM |
| M1 (narrow money) | M | Highest-frequency monetary aggregate |
| M2 (broad money) | M | Standard monetary-policy stance gauge |
| M3 / Lf / broad liquidity | M | Broadest monetary aggregate |
| Currency in circulation | M | Cash-demand cycle |
| Central bank balance sheet total | W | QT/QE pace gauge |
| Central bank balance sheet — securities holdings | W | Asset-purchase footprint |
| Central bank balance sheet — repo / reverse-repo outstanding | W | Liquidity-management ops |
| Central bank lending facilities outstanding | W | Stress-window usage |
| FX reserves transactional change (already in 3.4) | M | Cross-ref |
| Fiscal stance (cyclically-adjusted balance) | A | The fiscal counterpart |
| Macroprudential measures: LTV ceiling | EVENT | Housing-credit gating tool |
| Macroprudential measures: DTI / DSR ceiling | EVENT | Household-debt-service gating |
| Macroprudential measures: Countercyclical Capital Buffer | EVENT | Bank-capital macropru |
| Macroprudential events log | EVENT | Date + tool + magnitude |

---

## Cross-refs

- [onboarding_new_country.md](onboarding_new_country.md) — how to use this catalogue (workflow, vendor cascade, build order, identity checks, quality bar)
- [macro_economy_wiring_map.md](macro_economy_wiring_map.md) — per-country coverage status (4×4 grids)
- [economics_data_ingest.md](economics_data_ingest.md) — schema + vendor-agnostic loader + build log
- [korea/korea_indicator_inventory.md](korea/korea_indicator_inventory.md) — Korea as the worked reference (172 indicators)
