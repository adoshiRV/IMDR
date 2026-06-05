# Korea — Full Econ Indicator Inventory

**Date**: 2026-06-05 (post gap-closure round)
**Scope**: Every Korea row in `econ.dim_indicator` (`country_id=27`). Market data (FX spot, KRW rates curve, KRW vol, KOSPI) is **out of scope** of this doc — those live in `fx.*` and `rates.*` and have their own reference docs.
**Total**: **172 indicators / ~47,000 observations** across 3 vendors (KOSIS 164 + REB 4 + FRED 4).

KR is the most-populated country in `econ.dim_indicator`, ahead of US (133).

---

## 1. Top-line summary

| Vendor | Indicators | Earliest | Latest |
|---|---:|---|---|
| KOSIS (BOK + KOSTAT via KOSIS OpenAPI) | 164 | 1961-Q1 | 2026-06 |
| REB (R-ONE Open API direct) | 4 | 2012-05-07 | 2026-06-01 |
| FRED (St Louis Fed mirror of OECD/BOK) | 4 | 1990-01 | 2026-04 |
| **Total** | **172** | | |

| Category (`dim_indicator_category`) | Indicators | What it covers |
|---|---:|---|
| `gdp` | 51 | GDP + components (QoQ-SA + YoY), retail sales, government fiscal aggregates, IIP, Mfg capacity util |
| `bop` | 32 | Balance of Payments (Current + Financial + E&O), Terms of Trade, trade indices |
| `cpi` | 25 | CPI (headline + cores), PPI, Import & Export price indices |
| `balance_sheet` | 18 | Household Credit, Mfg Corporate financial ratios × 13, FSS Bank NPL |
| `sentiment` | 11 | BOK Lending Attitude Survey + Consumer Tendency Survey CCI components |
| `labour` | 10 | EAPS (employment, LFPR, unemployment), wages |
| `rates` | 10 | Bank deposit-side rates + FRED Korea Discount/Call/3M/10Y |
| `housing` | 8 | REB weekly Apartment Sale + Jeonse × Nationwide + Seoul (KOSIS-mirror + REB-direct) |
| `cb_balance_sheet` | 2 | BOK M2 + Lf monetary aggregates |
| `credit` | 3 | Household Loans by purpose (monthly) |

---

## 2. Growth Engine

### 2.1 GDP & components (BOK quarterly, 1961-Q1 → 2026-Q1, % change)

| `imdr_code` | Freq | Why important |
|---|:---:|---|
| `BOK.GDP.GDP.QOQ_SA.KR` | Q | Headline growth momentum stripped of seasonality — the rate that markets quote first. |
| `BOK.GDP.GDP.YOY.KR` | Q | Through-the-year growth — comparable to global Y/Y benchmarks. |
| `BOK.GDP.MFG.QOQ_SA.KR` | Q | Manufacturing tracks the chip cycle — Korea's swing factor. |
| `BOK.GDP.MFG.YOY.KR` | Q | Yearly mfg growth — proxy for global semi demand. |
| `BOK.GDP.SVC.QOQ_SA.KR` | Q | Services growth — the domestic-demand thermometer. |
| `BOK.GDP.SVC.YOY.KR` | Q | Yearly services growth — services job creation driver. |
| `BOK.GDP.AGRI.QOQ_SA.KR` | Q | Tiny share but moves food CPI — input to inflation forecast. |
| `BOK.GDP.AGRI.YOY.KR` | Q | Agri yearly — feeds fresh-food CPI volatility. |
| `BOK.GDP.CONSTR.QOQ_SA.KR` | Q | Construction GDP — the housing-channel transmission gauge. |
| `BOK.GDP.CONSTR.YOY.KR` | Q | Yearly construction — multi-quarter housing-cycle signal. |
| `BOK.GDP.PCE.QOQ_SA.KR` | Q | Private consumption — 50%+ of GDP, the consumer pulse. |
| `BOK.GDP.PCE.YOY.KR` | Q | Yearly PCE — wage growth → spending → CPI services. |
| `BOK.GDP.GOV_CONS.QOQ_SA.KR` | Q | Government consumption — fiscal impulse to GDP. |
| `BOK.GDP.GOV_CONS.YOY.KR` | Q | Yearly govt cons — counter-cyclical policy proxy. |
| `BOK.GDP.FACIL_INV.QOQ_SA.KR` | Q | Equipment investment — leading indicator for mfg cycle. |
| `BOK.GDP.FACIL_INV.YOY.KR` | Q | Yearly facilities investment — capex appetite gauge. |
| `BOK.GDP.CONSTR_INV.QOQ_SA.KR` | Q | Construction investment — housing-supply cycle. |
| `BOK.GDP.CONSTR_INV.YOY.KR` | Q | Yearly construction investment — multi-year supply pipeline. |
| `BOK.GDP.EXP_GOODS.QOQ_SA.KR` | Q | Real goods exports — KRW-disconnected demand for KR output. |
| `BOK.GDP.EXP_GOODS.YOY.KR` | Q | Yearly real exports — global-cycle pulse. |
| `BOK.GDP.IMP_GOODS.QOQ_SA.KR` | Q | Real goods imports — domestic demand signal stripping out price. |
| `BOK.GDP.IMP_GOODS.YOY.KR` | Q | Yearly real imports — demand strength gauge. |
| `BOK.GDP.DOMESTIC_DEMAND.QOQ_SA.KR` | Q | Final domestic demand ex-inventories — the cleanest domestic-cycle read. |
| `BOK.GDP.DOMESTIC_DEMAND.YOY.KR` | Q | Yearly domestic demand — separates external boom from domestic boom. |

### 2.2 Retail Sales (KOSTAT monthly, 2000-01 → 2026-04, 2020=100)

| `imdr_code` | Freq | Why important |
|---|:---:|---|
| `KOSTAT.RETAIL.DEPT_STORES.VALUE.KR` | M | High-income consumer pulse — K-shaped recovery signal. |
| `KOSTAT.RETAIL.DEPT_STORES.SA.KR` | M | SA dept-store sales — luxury demand cycle. |
| `KOSTAT.RETAIL.DISCOUNT.VALUE.KR` | M | Mass-market consumer; sensitive to real-wage squeeze. |
| `KOSTAT.RETAIL.DISCOUNT.SA.KR` | M | SA discount sales — mid-income spending gauge. |
| `KOSTAT.RETAIL.SUPERMARKET.VALUE.KR` | M | Daily-essentials spend — broad consumer base. |
| `KOSTAT.RETAIL.SUPERMARKET.SA.KR` | M | SA supermarkets — staple-goods volume. |
| `KOSTAT.RETAIL.CONVENIENCE.VALUE.KR` | M | Convenience-store sales — single-household + young-consumer indicator. |
| `KOSTAT.RETAIL.CONVENIENCE.SA.KR` | M | SA convenience — demographic-shift read. |
| `KOSTAT.RETAIL.DUTY_FREE.VALUE.KR` | M | Inbound-tourism proxy — China-tourist recovery gauge. |
| `KOSTAT.RETAIL.DUTY_FREE.SA.KR` | M | SA duty-free — geopolitics-sensitive retail bucket. |
| `KOSTAT.RETAIL.CARS_FUEL.VALUE.KR` | M | Big-ticket + fuel spend — interest-rate-sensitive. |
| `KOSTAT.RETAIL.CARS_FUEL.SA.KR` | M | SA cars+fuel — credit-cycle barometer. |
| `KOSTAT.RETAIL.SPECIALISED.VALUE.KR` | M | Specialised stores — pharma/cosmetics/clothing splice. |
| `KOSTAT.RETAIL.SPECIALISED.SA.KR` | M | SA specialised — narrower discretionary measure. |

### 2.3 Fiscal Aggregates (BOK annual, 2007 → 2024, ₩bn)

| `imdr_code` | Freq | Why important |
|---|:---:|---|
| `BOK.FISCAL.REVENUE_TOTAL.KR` | A | Government total revenue — fiscal capacity benchmark. |
| `BOK.FISCAL.EXPENDITURE_TOTAL.KR` | A | Government total spending — fiscal impulse magnitude. |
| `BOK.FISCAL.NET_LENDING.KR` | A | Fiscal balance (deficit/surplus) — bond-supply signal. |
| `BOK.FISCAL.CONSUMPTION_FINAL.KR` | A | Government consumption — directly enters GDP. |
| `BOK.FISCAL.TAX_INCOME.KR` | A | Direct taxes — income-cycle and corporate-profit proxy. |
| `BOK.FISCAL.TAX_PRODUCTION.KR` | A | Indirect taxes — consumption-cycle proxy. |
| `BOK.FISCAL.SAVING_GROSS.KR` | A | Government gross saving — closes the (S−I) ≡ CA identity. |

---

## 3. Inflation Engine

### 3.1 CPI (KOSTAT monthly, 2000-01 → 2026-05, % change)

| `imdr_code` | Freq | Why important |
|---|:---:|---|
| `KOSTAT.CPI.HEADLINE.YOY.KR` | M | The headline inflation print — markets and BOK target this. |
| `KOSTAT.CPI.HEADLINE.MOM.KR` | M | Month-on-month momentum — tipping-point indicator. |
| `KOSTAT.CPI.HEADLINE.YTD.KR` | M | Year-to-date — vs BOK's 2% target trajectory. |
| `KOSTAT.CPI.EXFOOD_NRG.YOY.KR` | M | Core CPI (standard) — the cleanest underlying inflation read. |
| `KOSTAT.CPI.EXFOOD_NRG.MOM.KR` | M | Core MoM — second-derivative inflation signal. |
| `KOSTAT.CPI.EXFOOD_NRG.YTD.KR` | M | Core YTD — persistence vs transitory test. |
| `KOSTAT.CPI.EXAGRI_OIL.YOY.KR` | M | Core (trimmed, ex-agri+oil) — BOK's own preferred core. |
| `KOSTAT.CPI.EXAGRI_OIL.MOM.KR` | M | BOK-core MoM — direct BOK reaction-function input. |
| `KOSTAT.CPI.EXAGRI_OIL.YTD.KR` | M | BOK-core YTD — trend-vs-policy signal. |
| `KOSTAT.CPI.LIVING.YOY.KR` | M | Living-cost CPI (necessities) — political-pressure gauge. |
| `KOSTAT.CPI.LIVING.MOM.KR` | M | Necessities MoM — household-stress indicator. |
| `KOSTAT.CPI.LIVING.YTD.KR` | M | Necessities YTD — real-wage erosion measure. |
| `KOSTAT.CPI.FRESH_FOOD.YOY.KR` | M | Fresh-food inflation — volatile but high public-perception weight. |
| `KOSTAT.CPI.FRESH_FOOD.MOM.KR` | M | Fresh-food MoM — early-warning weather/harvest signal. |
| `KOSTAT.CPI.FRESH_FOOD.YTD.KR` | M | Fresh-food YTD — drives 'expensive markets' headlines. |

### 3.2 Producer Prices (BOK monthly, 1990-01 → 2026-04, 2020=100)

| `imdr_code` | Freq | Why important |
|---|:---:|---|
| `BOK.PPI.TOTAL.LEVEL.KR` | M | All-items PPI — pipeline-inflation leading indicator vs CPI. |
| `BOK.PPI.MFG.LEVEL.KR` | M | Manufacturing PPI — direct read on chip/steel/auto output prices. |
| `BOK.PPI.SVC.LEVEL.KR` | M | Services PPI — sticky-inflation component, mirrors core CPI. |
| `BOK.PPI.AGRI.LEVEL.KR` | M | Agri/forestry/marine PPI — fresh-food CPI upstream. |
| `BOK.PPI.MINING.LEVEL.KR` | M | Mining PPI — commodity-cycle pass-through. |
| `BOK.PPI.UTIL.LEVEL.KR` | M | Electricity/gas/water PPI — energy-pass-through to CPI. |

### 3.3 Import & Export Prices (BOK monthly, 1980-01 → 2026-04, 2020=100)

| `imdr_code` | Freq | Why important |
|---|:---:|---|
| `BOK.IMPORT_PRICE.ALL.WON.KR` | M | KRW-denom import prices — direct CPI feed via FX pass-through. |
| `BOK.IMPORT_PRICE.ALL.USD.KR` | M | USD-denom import prices — world-price input ex-FX move. |
| `BOK.EXPORT_PRICE.ALL.WON.KR` | M | KRW export prices — KRW-translated revenue of exporters. |
| `BOK.EXPORT_PRICE.ALL.USD.KR` | M | USD export prices — Korean output's world-price competitiveness. |

**Won-vs-USD spread is the cleanest single FX-pass-through gauge.**

---

## 4. External & FX

### 4.1 Balance of Payments — Current Account (BOK monthly, 1980-01 → 2026-03, USD mn)

| `imdr_code` | Freq | Why important |
|---|:---:|---|
| `BOK.BOP.CA.TOTAL.KR` | M | Headline CA balance — KRW's long-run anchor. |
| `BOK.BOP.CA.GOODS.KR` | M | Goods balance — the dominant CA component for Korea. |
| `BOK.BOP.CA.SERVICES.KR` | M | Services balance — chronic deficit (travel, IP rentals). |
| `BOK.BOP.CA.PRIMARY_INC.KR` | M | Primary income balance — return on KR's foreign assets. |
| `BOK.BOP.CA.SECONDARY_INC.KR` | M | Secondary income — small, structural. |
| `BOK.BOP.GOODS.EXPORTS.KR` | M | Goods exports (BoP basis) — chip cycle's monthly print. |
| `BOK.BOP.GOODS.IMPORTS.KR` | M | Goods imports (BoP basis, FOB) — energy + intermediate-goods demand. |
| `BOK.BOP.SVC.TRAVEL.KR` | M | Travel balance — tourism in vs out (Chinese-tourist sensitive). |
| `BOK.BOP.SVC.TRANSPORT.KR` | M | Transport balance — Korean shipping/airline cycle. |
| `BOK.BOP.SVC.CONSTRUCTION.KR` | M | Overseas construction — Middle East mega-projects exposure. |
| `BOK.BOP.PRIMARY.INVEST_INC.KR` | M | Investment income (dividends + interest crossing border) — stock of NIIP × yield. |

### 4.2 Balance of Payments — Financial Account (BOK monthly, 1980-01 → 2026-03, USD mn)

| `imdr_code` | Freq | Why important |
|---|:---:|---|
| `BOK.BOP.FA.TOTAL.KR` | M | Headline financial flows — funding-of-CA identity. |
| `BOK.BOP.FA.DI.NET.KR` | M | Net Direct Investment — long-term capital quality. |
| `BOK.BOP.FA.DI.ASSETS.KR` | M | Outward FDI — Korean corp foreign expansion. |
| `BOK.BOP.FA.DI.LIAB.KR` | M | Inward FDI — foreign appetite for KR plants/equity. |
| `BOK.BOP.FA.PI.NET.KR` | M | Net Portfolio Investment — fast-money equity + bond flows. |
| `BOK.BOP.FA.PI.ASSETS.KR` | M | Outward PI — KR resident foreign-asset accumulation. |
| `BOK.BOP.FA.PI.LIAB.KR` | M | Inward PI — foreigner KR equity + bond holdings flow. |
| `BOK.BOP.FA.OI.NET.KR` | M | Net Other Investment — bank loans + trade credit, the volatile bucket. |
| `BOK.BOP.FA.OI.ASSETS.KR` | M | OI Assets — KR bank lending offshore. |
| `BOK.BOP.FA.OI.LIAB.KR` | M | OI Liabilities — foreign-bank lending into KR. |
| `BOK.BOP.FA.DERIV.NET.KR` | M | Net financial derivatives — large for KR (FX/CCS-hedging by exporters). |
| `BOK.BOP.FA.RESERVES.KR` | M | Reserve-Asset transactional change — BOK intervention proxy. |
| `BOK.BOP.EO.KR` | M | Errors & Omissions — proxy for unrecorded capital flight. |

### 4.3 Terms of Trade + Trade Indices (BOK monthly, 1988-01 → 2026-04, 2020=100)

| `imdr_code` | Freq | Why important |
|---|:---:|---|
| `BOK.TOT.NET_BARTER.LEVEL.KR` | M | Commodity ToT — price of KR exports per unit of imports. |
| `BOK.TOT.INCOME.LEVEL.KR` | M | Income ToT — purchasing power of KR exports (vol-adjusted). |
| `BOK.TRADE.EXPORT_VALUE.KR` | M | Export value index — nominal demand for KR output. |
| `BOK.TRADE.EXPORT_VOLUME.KR` | M | Export volume index — real demand stripped of price moves. |
| `BOK.TRADE.IMPORT_VALUE.KR` | M | Import value index — nominal demand × import-price level. |
| `BOK.TRADE.IMPORT_VOLUME.KR` | M | Import volume index — real domestic absorption. |

---

## 5. Policy Transmission

### 5.1 Bank Deposit-Side Rates (BOK monthly, 1996-01 → 2026-04, % p.a.)

| `imdr_code` | Freq | Why important |
|---|:---:|---|
| `BOK.BANK_RATE.DEPOSITS_EX_DEBENT.KR` | M | Banks' avg new-deposit funding rate — pass-through from policy rate. |
| `BOK.BANK_RATE.TIME_DEPOSITS.KR` | M | Time-deposit rate — household savings competition for KTBs. |
| `BOK.BANK_RATE.CD_91D.KR` | M | CD 91-day rate — the KRW money-market benchmark used in IRS. |
| `BOK.BANK_RATE.REPO.KR` | M | Repo rate — wholesale-funding cost for banks. |
| `BOK.BANK_RATE.MARKET_FI.KR` | M | Marketable-FI composite rate — short-funding diversification. |
| `BOK.BANK_RATE.FIN_DEBENT.KR` | M | Bank debenture rate — bank-balance-sheet funding cost. |

### 5.2 FRED Korea Rates (FRED monthly, 1990 → 2026-04, % p.a.)

| `imdr_code` | Freq | Why important |
|---|:---:|---|
| `FRED.RATES.KR_DISCOUNT.KR` | M | BOK Discount Rate — historical BOK Base-Rate proxy (1964 start). |
| `FRED.RATES.KR_CALL.KR` | M | Korea overnight call money rate — BOK's policy-rate target proxy. |
| `FRED.RATES.KR_3M_INTERBANK.KR` | M | KR 3M interbank — money-market term-premium gauge. |
| `FRED.RATES.KR_10Y_GOV.KR` | M | 10Y KTB yield — long-end fixed-income benchmark, USD-DM-rate cointegrated. |

### 5.6 Monetary Aggregates (BOK monthly, 2003-10 → 2026-03, KRW bn, SA)

| `imdr_code` | Freq | Why important |
|---|:---:|---|
| `BOK.MONEY.M2.LEVEL.KR` | M | M2 (broad money) — BOK's primary monetary aggregate; tracks deposit + savings stock. |
| `BOK.MONEY.LF.LEVEL.KR` | M | Lf (Liquidity Aggregate of Financial Institutions) — broader-than-M2 liquidity gauge incl. non-bank financial liabilities. |

### 5.7 Consumer Tendency Survey / CCI (BOK monthly, 2008-09 → 2026-05, diffusion index, >100 = optimistic)

| `imdr_code` | Freq | Why important |
|---|:---:|---|
| `BOK.CCI.LIVING_STD.KR` | M | Current living-standard perception — household sentiment thermometer. |
| `BOK.CCI.ECON_SITUATION.KR` | M | Current economic-situation perception — concurrent business-cycle pulse. |
| `BOK.CCI.EXP_LIVING_STD.KR` | M | Expected living standard — forward consumption-confidence gauge. |
| `BOK.CCI.EXP_ECON_SITUATION.KR` | M | Expected economic situation — leading BSI substitute for households. |
| `BOK.CCI.EXP_EMPLOYMENT.KR` | M | Expected employment situation — leading labour-market signal. |
| `BOK.CCI.EXP_INTEREST_RATES.KR` | M | Expected interest rates — household rate-direction expectations (proxy for BOK policy expectations). |

### 5.8 Business Sentiment Index / BSI (BOK monthly, 2009-08 → 2026-06, diffusion index, >100 = expansionary)

| `imdr_code` | Freq | Why important |
|---|:---:|---|
| `BOK.BSI.REALISED.ALL.KR` | M | All-industries Business Condition BSI (realised) — concurrent corp-sentiment gauge. |
| `BOK.BSI.REALISED.MFG.KR` | M | Manufacturing Business Condition BSI (realised) — chip+auto cycle pulse. |
| `BOK.BSI.OUTLOOK.ALL.KR` | M | All-industries BSI Outlook (1M ahead) — leading corp sentiment. |
| `BOK.BSI.OUTLOOK.MFG.KR` | M | Manufacturing BSI Outlook (1M ahead) — leading export+industrial cycle. |

---

## 5A. Industrial Production + Capacity (KOSTAT monthly)

### 5A.1 All-Industry Production Index (DT_1JH20202 monthly, 2000-01 → 2026-04, 2020=100, SA)

| `imdr_code` | Freq | Why important |
|---|:---:|---|
| `KOSTAT.IIP.ALL.SA.KR` | M | All-Industry Production Index — broadest monthly real-activity gauge. |
| `KOSTAT.IIP.INDUSTRY.SA.KR` | M | Industrial Production — manufacturing cycle headline. |
| `KOSTAT.IIP.SERVICES.SA.KR` | M | Services Production — domestic-demand-driven activity. |
| `KOSTAT.IIP.CONSTRUCTION.SA.KR` | M | Construction Production — housing-cycle activity gauge. |
| `KOSTAT.IIP.PUBLIC.SA.KR` | M | Public Administration Production — counter-cyclical baseline. |

### 5A.2 Manufacturing Capacity Utilisation (DT_1F32002 monthly, %)

| `imdr_code` | Freq | Why important |
|---|:---:|---|
| `KOSTAT.CAP_UTIL.MFG.KR` | M | Mfg Capacity Utilisation Rate — output-gap proxy for inflation forecasting (high util → pricing power). |

---

## 5B. Corporate Financial Ratios (BOK annual, 2009 → 2024, %)

Manufacturing sector × All Enterprises × 13 financial ratios from BOK's
`DT_501Y007` (자산/자본 지표). Captures Korean corp balance-sheet health,
critically the chip + auto + ship sectors that drive exports.

| `imdr_code` | Freq | Why important |
|---|:---:|---|
| `BOK.CORP_FIN.EQUITY_TO_ASSETS.MFG.KR` | A | Stockholders' equity ÷ total assets — primary capitalisation metric. |
| `BOK.CORP_FIN.DEBT_RATIO.MFG.KR` | A | Debt ÷ Equity — leverage headline. |
| `BOK.CORP_FIN.CURRENT_RATIO.MFG.KR` | A | Current assets ÷ current liabilities — short-term solvency. |
| `BOK.CORP_FIN.QUICK_RATIO.MFG.KR` | A | (Current assets − inventory) ÷ current liabilities — strict liquidity. |
| `BOK.CORP_FIN.CASH_RATIO.MFG.KR` | A | Cash ÷ current liabilities — ultra-short-term liquidity. |
| `BOK.CORP_FIN.NONCURRENT_LIAB_RATIO_A.MFG.KR` | A | Long-term liabilities ratio (variant A) — long-term solvency. |
| `BOK.CORP_FIN.NONCURRENT_LIAB_RATIO_B.MFG.KR` | A | Long-term liabilities ratio (variant B) — alternate calc. |
| `BOK.CORP_FIN.CURRENT_LIAB_RATIO.MFG.KR` | A | Current liabilities ratio — short-term debt burden. |
| `BOK.CORP_FIN.FIXED_RATIO.MFG.KR` | A | Non-current assets ÷ (equity + non-current liab) — long-term asset-funding match. |
| `BOK.CORP_FIN.BORROWINGS_TO_ASSETS.MFG.KR` | A | Total borrowings + bonds ÷ total assets — debt-loading gauge. |
| `BOK.CORP_FIN.BORROWINGS_TO_SALES.MFG.KR` | A | Total borrowings + bonds ÷ sales — debt servicing capacity gauge. |
| `BOK.CORP_FIN.RECEIVABLES_PAYABLES.MFG.KR` | A | Receivables ÷ payables — working-capital tension. |
| `BOK.CORP_FIN.NET_WC_TO_ASSETS.MFG.KR` | A | Net working capital ÷ total assets — short-term operational health. |

### 5.3 Lending Attitude Survey (BOK quarterly, 2003-Q1 → 2026-Q2, diffusion index)

| `imdr_code` | Freq | Why important |
|---|:---:|---|
| `BOK.LEND_STANCE.BANK_OVERALL.KR` | Q | Banks' aggregate lending stance — SLOOS-equivalent leading indicator. |
| `BOK.LEND_STANCE.BANK_LARGE_CORP.KR` | Q | Stance to large corps — investment-grade credit-channel pulse. |
| `BOK.LEND_STANCE.BANK_SME.KR` | Q | Stance to SMEs — small-business credit-stress signal. |
| `BOK.LEND_STANCE.BANK_HH.KR` | Q | Stance to households — consumer-credit gating gauge. |
| `BOK.LEND_STANCE.BANK_HH_HOUSING.KR` | Q | Stance to housing — mortgage-supply tightness, drives home prices. |

### 5.4 Household Loans (BOK monthly, 2003-10 → 2026-03, ₩bn)

| `imdr_code` | Freq | Why important |
|---|:---:|---|
| `BOK.LOANS.HH.DEP_TOTAL.KR` | M | Total HH loans at depository institutions — leverage cycle headline. |
| `BOK.LOANS.HH.HOUSING.KR` | M | Housing-related HH loans (mortgages + Jeonse loans) — direct house-price feed. |
| `BOK.LOANS.HH.OTHER.KR` | M | Non-housing HH loans — credit-card + unsecured consumer credit. |

### 5.5 Balance Sheets (quarterly)

| `imdr_code` | Freq | Window | Why important |
|---|:---:|---|---|
| `BOK.HH_CREDIT.TOTAL.KR` | Q | 2002-Q4 → 2026-Q1 | Total household debt stock — Korea's #1 macro-prudential risk. |
| `BOK.HH_CREDIT.LOANS.KR` | Q | 2002-Q4 → 2026-Q1 | HH loans stock subset — credit-channel-of-policy gauge. |
| `FSS.BANK.LOANS_TOTAL.KR` | Q | 2000-Q3 → 2016-Q3 ⚠ | Domestic-bank loan stock (table discontinued; legacy). |
| `FSS.BANK.NPL_LEVEL.KR` | Q | 2000-Q3 → 2016-Q3 ⚠ | Bank NPL absolute level (legacy). |
| `FSS.BANK.NPL_RATIO.KR` | Q | 2000-Q3 → 2016-Q3 ⚠ | Bank NPL ratio (% of total loans) — financial-stability gauge (legacy). |

**Note** — FSS series stop 2016; current NPL data needs a different source (FSS website direct or newer BOK FSR table).

---

## 6. Labour Market (KOSTAT EAPS, monthly, 1999-06 → 2026-04)

| `imdr_code` | Freq | Why important |
|---|:---:|---|
| `KOSTAT.LABOUR.POP_15_OVER.KR` | M | Working-age population — denominator for all labour ratios. |
| `KOSTAT.LABOUR.ACTIVE_POP.KR` | M | Labour force ('000) — engaged-population stock. |
| `KOSTAT.LABOUR.EMPLOYED.KR` | M | Employment level — most-watched single labour indicator. |
| `KOSTAT.LABOUR.UNEMPLOYED.KR` | M | Unemployment level — recession early-warning signal. |
| `KOSTAT.LABOUR.INACTIVE.KR` | M | Inactive population — discouraged-worker effect. |
| `KOSTAT.LABOUR.LFPR.KR` | M | Labour Force Participation Rate — structural slack measure. |
| `KOSTAT.LABOUR.UNEMP_RATE.KR` | M | Unemployment rate — BOK's labour-side reaction-function input. |
| `KOSTAT.LABOUR.EMP_POP_RATIO.KR` | M | Employment-to-Population ratio — broadest utilisation gauge. |

### 6.1 Wages (KOSTAT annual, 2011 → 2025)

| `imdr_code` | Freq | Why important |
|---|:---:|---|
| `KOSTAT.WAGE.WAGE_LEVEL.NATIONAL.KR` | A | Regular workers' avg monthly wage — services-inflation upstream. |
| `KOSTAT.WAGE.WAGE_YOY.NATIONAL.KR` | A | Wage growth rate — wage-price spiral risk gauge. |

---

## 7. Housing (Real Estate Board weekly, 2020-02-02=100 / REB-direct; 2025-03-31=100 / KOSIS-mirror)

### 7.1 KOSIS-mirror cuts (2021-07-05 → 2026-02-02, ~5 years history)

| `imdr_code` | Freq | Why important |
|---|:---:|---|
| `REB.HOUSING.APT_SALE.LEVEL.KR_NAT` | W | Nationwide apartment sale prices — KR household-wealth dominant component. |
| `REB.HOUSING.APT_SALE.LEVEL.KR_SEOUL` | W | Seoul apartment sale prices — luxury-tier signal + Gangnam-cycle gauge. |
| `REB.HOUSING.APT_JEONSE.LEVEL.KR_NAT` | W | Nationwide jeonse (deposit-rent) — KR rental-market signal. |
| `REB.HOUSING.APT_JEONSE.LEVEL.KR_SEOUL` | W | Seoul jeonse — proxies young-household leverage stress. |

### 7.2 REB-direct cuts (`.REB_DIRECT` suffix, 2012-05-07 → 2026-06-01, **14 years history**)

| `imdr_code` | Freq | Why important |
|---|:---:|---|
| `REB.HOUSING.APT_SALE.LEVEL.KR_NAT.REB_DIRECT` | W | Same series as above with full 14-yr history covering 2 cycles + 2022 drawdown. |
| `REB.HOUSING.APT_SALE.LEVEL.KR_SEOUL.REB_DIRECT` | W | Seoul long-history sale prices — Gangnam cycle vs nationwide divergence. |
| `REB.HOUSING.APT_JEONSE.LEVEL.KR_NAT.REB_DIRECT` | W | Long-history jeonse — multi-cycle rental-yield trend. |
| `REB.HOUSING.APT_JEONSE.LEVEL.KR_SEOUL.REB_DIRECT` | W | Seoul long-history jeonse — generational housing-affordability arc. |

YoY % reconciles 0 bp between REB-direct and KOSIS-mirror; levels differ due to different rebasings.

---

## 8. Coverage audit — what's *not* here

### 8.1 By wiring-map cell

| Cell | Coverage | Gap |
|---|:---:|---|
| 1.1 Private Demand | ✅ | (closed — added BOK Consumer Tendency Survey CCI components 2026-06-05) |
| 1.2 Fiscal Demand | ✅ | (none) |
| 1.3 External Demand | ✅ | Monthly customs trade by country (MOTIE direct) — non-blocking |
| 1.4 Macro Core | ✅ | (closed — added KOSTAT IIP + BSI Realised+Outlook 2026-06-05). PMI Manufacturing still vendor-gated (S&P Global). |
| 2.1 Input Costs | ✅ | Commodities pass-through is implicit only (no oil/gas/metals indicator on KR side) — non-blocking |
| 2.2 Producer Prices | ✅ | (none) |
| 2.3 Domestic Costs | ✅ | (closed — added Mfg Capacity Util + BOK Expected Interest Rates as inflation-expectations proxy 2026-06-05) |
| 2.4 CPI Pressure | ✅ | (none) |
| 3.1 Terms of Trade | ✅ | (none) |
| 3.2 Current Account | ✅ | (none) |
| 3.3 Capital Account | ✅ | (none) |
| 3.4 FX / REER | parked | **User-parked this session.** Add Citi spot + FRED `RBKRBIS`/`NBKRBIS` when needed. |
| 4.1 Demand Transmission | ✅ | (none) |
| 4.2 Balance Sheets | ✅ | (closed — added BOK Corporate × 13 financial ratios for Mfg 2026-06-05). FSS NPL still stale to 2016 — non-blocking. |
| 4.3 Financial Conditions | ⚠ | Bank deposit rates ✅; **KR corporate credit spreads** missing; equities are market-data domain |
| 4.4 Policy Reaction | ✅ | (closed — added BOK M2 + Lf monetary aggregates 2026-06-05). Macroprudential tools (LTV/DTI) still FSC-press-release sourced — non-blocking. |

**Final score: 15 ✅ / 1 ⚠ / 1 parked**. Only cell 4.3 retains a known gap (no KR corporate credit spreads).

### 8.2 Remaining non-KOSIS gaps

After the 2026-06-05 gap-closure round, the only outstanding work needs external sources:

| Gap | Why outstanding | Path forward |
|---|---|---|
| **3.4 FX / REER** | User-parked this session | Citi spot already loaded in `fx.fact_fx_rate`; FRED `RBKRBIS` + `NBKRBIS` (BIS REER/NEER) easy add to econ when needed |
| **4.3 Corp credit spreads** | KOSIS has no KR corporate spread series | Citi corp bond curves or vendor like Markit — separate domain |
| **BOK Base Rate via Citi** | Citi BENCH_RATES catalogue has only 10 entries (no KR) | Citi-side request to add `KR_BASE`. FRED Discount Rate already covers cell 4.4 |
| **Current bank NPL (post-2016)** | FSS KOSIS table discontinued | FSS website direct scrape or newer BOK FSR table — catalogue browse |
| **PMI Manufacturing** | S&P Global — paid vendor | Out of cheap-data scope |
| **Monthly customs trade by country** | KOSIS only has annual; MOTIE not yet wired | New MOTIE vendor — separate work |

### 8.3 Out-of-scope (lives elsewhere by design)

| Topic | Lives in |
|---|---|
| KRW spot / forwards / NDF | `fx.fact_fx_rate` (Citi feed) |
| KRW vol surface | `fx.fact_vol` (Citi feed) |
| KRW IRS / SOV_CMT (KTB) yield curve | `rates.fact_observation` curves 35/47/48/61 |
| KOSPI / KOSPI200 | Equity domain (separate) |

---

## 9. Loaders + cross-refs

- All KOSIS fetchers: `playground/econ/kosis/fetch_*.py` (15 files; shared TLS-1.2 helper `_kosis_http.py`)
- REB-direct fetcher: `playground/econ/reb/fetch_housing.py`
- FRED Korea seed entries: `playground/econ/fred/seed.yml` (4 KR rate series)
- Loader CLI: `python -m scripts.migrations.load_econ_indicator_from_playground --vendor kosis|reb|fred`
- Vendor row migrations: 077 (kosis) + 078 (reb); fred row pre-existed
- Wiring map cross-ref: [macro_economy_wiring_map.md §7.13](../macro_economy_wiring_map.md#713-south-korea-kr)
- API mechanics: [kosis_openapi_reference.md](kosis_openapi_reference.md)
- Target list reference: [kr_indicator_targets.md](kr_indicator_targets.md)
