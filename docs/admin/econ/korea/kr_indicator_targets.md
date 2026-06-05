# Korea (KR) — economic indicator target list

Last updated: 2026-06-05

This is the **concrete shopping list** of Korea economic time series we want
loaded into `econ.dim_indicator`. Companion to
[kosis_kr_coverage_plan.md](kosis_kr_coverage_plan.md), which maps wiring-map
cells to KOSIS tables at the **concept** level. This doc translates those
concepts into specific `dim_indicator` rows, one line per series.

## Build progress (2026-06-05)

**141 indicators loaded** in `econ.dim_indicator` for Korea (`country_id=27`)
across 3 vendors (KOSIS 133 + REB 4 + FRED 4). KR is now the most-populated
country in the econ schema, ahead of the US (133).

| Group | Loaded | Fetcher | DB? |
|---|:---:|---|:---:|
| KOSTAT CPI (DT_1J22042) | 15 | `playground/econ/kosis/fetch_cpi.py` | ✅ |
| BOK PPI (DT_404Y014) | 6 | `playground/econ/kosis/fetch_ppi.py` (40k-cap solved) | ✅ |
| BOK GDP-Quarterly (DT_200Y102) | 24 | `playground/econ/kosis/fetch_gdp.py` | ✅ |
| BOK Terms of Trade (DT_403Y005) | 2 | `playground/econ/kosis/fetch_tot.py` | ✅ |
| BOK Bank Deposit Rates (DT_121Y002) | 6 | `playground/econ/kosis/fetch_bank_rates.py` | ✅ |
| KOSIS-mirror REB Housing (2021-07→) | 4 | `playground/econ/kosis/fetch_reb_housing.py` | ✅ |
| BOK BoP (DT_301Y013) | 24 | `playground/econ/kosis/fetch_bop.py` (OpenAPI refactor done) | ✅ |
| REB-direct Housing (2012-05→ deeper history) | 4 | `playground/econ/reb/fetch_housing.py` — `.REB_DIRECT` suffix | ✅ |
| KOSTAT EAPS Labour (DT_1DA7001S) | 8 | `playground/econ/kosis/fetch_labour.py` | ✅ |
| KOSTAT Retail Sales (DT_1K41013) | 14 | `playground/econ/kosis/fetch_retail.py` | ✅ |
| BOK Fiscal Aggregates (DT_200Y154, 2-axis) | 7 | `playground/econ/kosis/fetch_fiscal.py` — annual 2007→ | ✅ |
| BOK Import + Export Prices (DT_401Y015 + DT_402Y014, 2-axis) | 4 | `playground/econ/kosis/fetch_trade_prices.py` — × Won/USD basis | ✅ |
| BOK Lending Survey + HH Loans (DT_514Y001 + DT_151Y005) | 8 | `playground/econ/kosis/fetch_lending.py` — 5 stance Q + 3 HH loans M | ✅ |
| BOK Household Credit + FSS NPL (DT_151Y001 + DT_376_10_SDMA051V_3) | 5 | `playground/econ/kosis/fetch_balance_sheets.py` — FSS stale to 2016 | ✅ |
| KOSTAT Wages (DT_1YL15006) | 2 | `playground/econ/kosis/fetch_wages.py` — annual national only | ✅ |
| BOK Trade Value + Volume Indices (DT_403Y001-004) | 4 | `playground/econ/kosis/fetch_trade_indices.py` | ✅ |
| FRED Korea Rates (Discount / Call / 3M Interbank / 10Y Govt) | 4 | seed.yml additions; `playground.econ.fred.fetch` | ✅ |

**Naming reality vs the target rows below**: today's fetchers diverged
slightly from the placeholder imdr_codes drafted before implementation. Examples:
target `BOK.GDP.REAL.QOQ.KR` shipped as `BOK.GDP.GDP.QOQ_SA.KR`; target
`BOK.CPI.HEADLINE.LEVEL.KR` shipped as `KOSTAT.CPI.HEADLINE.YOY.KR` (KOSTAT
publishes pct-change rates, not level — naming reflects that). The list
below is the **plan**; the source-of-truth is now `econ.dim_indicator`.

## Scope

| In scope | Out of scope (covered by market-data layer) |
|---|---|
| GDP + components, labour, industrial activity, sentiment | KOSPI / KOSPI200 / KQ150 (equity domain — Citi `EQUITY.EQUITY_INDEX.KS200.LEVEL.REUTERS`) |
| CPI, PPI, import/export prices, wages | KRW spot / forwards / NDF (FX domain — Citi `FX.SPOT.USD.KRW.CITI`, `FX.FORWARD.FWD_OUTRIGHT.USD.KRW.*.CITI`) |
| BoP, IIP, external debt, customs trade, terms of trade | KRW FX vol surface (FX domain — Citi `FX.VOL.USD.KRW.*.*.IMPLIED.CITI`) |
| FX reserves, REER, NEER | KRW SOV_CMT yield curve (rates domain — Citi `RATES.SOV_CMT.KOR.*.CITI`) |
| BOK Base Rate, money supply, bank loans, household credit | KRW IRS curve + swaption vol (rates domain — Citi `RATES.SWAP_LIBOR.KRW.*.CITI`, `RATES.VOL.KRW.*.*.CITI`) |
| BSI / CCI surveys, inflation expectations | KRW XCCY basis (rates domain — Citi `RATES.XCCY_OIS_SWAP.KRW.USD.*.CITI`) |
| Bank NPL ratio, government debt | |

If a concept is published in **both** market data and an econ source
(notably BOK Base Rate, KORIBOR, CD 91-day), we keep **both** for
cross-validation — same convention used for FRED Fed Funds + market
EFFR in `econ.dim_indicator`.

## Source priority

| Source | `orgId` (KOSIS) | Use for |
|---|:---:|---|
| BOK (한국은행) | 301 | National accounts, BoP/IIP, money & banking, rates, CPI/PPI reissue, TOT |
| Statistics Korea (통계청 / KOSTAT) | 101 | Population, labour survey, industrial production, retail sales, wages, housing |
| Korea Customs Service | 343 | Customs-basis monthly trade |
| BOK direct (non-KOSIS) | — | FX rates + FX reserves (KOSIS mirror missing for `731Y…`/`732Y…`) — Playwright fallback under `playground/econ/kosis/` |
| BIS | — | REER / NEER for KRW (not in KOSIS) — FRED mirror `RBKRBIS` (REER) + `NBKRBIS` (NEER) |
| FRED | — | Cross-check / fallback for any of the above |

## Indicator schema

Each row below corresponds to one `econ.dim_indicator` insertion. Columns
match the table:

- **`imdr_code`** — IMDR-side stable identifier. Convention: `{SOURCE}.{TOPIC}.{VARIANT}.KR`
- **`source_code`** — vendor-side identifier. For KOSIS: `{orgId}/{tblId}/{itmId}[/{objL1}]`
- **`category_id`** — FK to `econ.dim_indicator_category` (column shown is the `category_code`)
- **`frequency_id`** — D / M / Q / A
- **`is_seasonally_adjusted`** — Y/N where the series itself is SA, not where we apply SA

Status legend (matches [kosis_kr_coverage_plan.md](kosis_kr_coverage_plan.md)):

- ✅ confirmed — table probed and returning rows
- ⚠ candidate — concept clear, KOSIS table likely correct, `itmId`/`objL1` needs nailing down
- ❓ unknown — table not yet identified, needs catalogue browse
- ❌ KOSIS-absent — use a non-KOSIS source (BOK direct, FRED, BIS)

---

## 1. Growth Engine

### 1a. National accounts (category `gdp`, source BOK orgId=301)

| `imdr_code` | Display name | `source_code` | Freq | SA | Status |
|---|---|---|:---:|:---:|:---:|
| `BOK.GDP.REAL.LEVEL.KR` | Real GDP, level (chain-linked, 2020 prices) | `301/DT_200Y113/ALL/ALL` | Q | Y | ⚠ |
| `BOK.GDP.REAL.QOQ.KR` | Real GDP, QoQ % SA | `301/DT_200Y102/<QoQ item>` | Q | Y | ✅ table |
| `BOK.GDP.REAL.YOY.KR` | Real GDP, YoY % | `301/DT_200Y102/<YoY item>` | Q | N | ✅ table |
| `BOK.GDP.NOMINAL.LEVEL.KR` | Nominal GDP, KRW bn | `301/DT_200Y113/<nominal>` | Q | Y | ⚠ |
| `BOK.GDP.DEFLATOR.KR` | GDP deflator | `301/DT_200Y111/ALL/ALL` | Q | N | ⚠ |
| `BOK.GNI.REAL.LEVEL.KR` | Real GNI, level | `301/DT_200Y113/<GNI item>` | Q | Y | ⚠ |
| `BOK.GDP.PRIVATE_CONS.QOQ.KR` | Private consumption, QoQ % | `301/DT_200Y107/<PCE>` | Q | Y | ⚠ |
| `BOK.GDP.GOV_CONS.QOQ.KR` | Government consumption, QoQ % | `301/DT_200Y151/ALL/ALL` | Q | Y | ⚠ |
| `BOK.GDP.GFCF.QOQ.KR` | Gross fixed capital formation, QoQ % | `301/DT_200Y135/ALL/ALL` | Q | Y | ⚠ |
| `BOK.GDP.EQUIP_INV.YOY.KR` | Equipment investment, YoY % | `301/DT_200Y138/ALL/ALL` | Q | N | ⚠ |
| `BOK.GDP.CONSTR_INV.YOY.KR` | Construction investment, YoY % | `301/DT_200Y135/<constr>` | Q | N | ⚠ |
| `BOK.GDP.EXPORTS.QOQ.KR` | Exports of goods & services (vol), QoQ % | `301/DT_200Y107/<X>` | Q | Y | ⚠ |
| `BOK.GDP.IMPORTS.QOQ.KR` | Imports of goods & services (vol), QoQ % | `301/DT_200Y107/<M>` | Q | Y | ⚠ |
| `BOK.GDP.NETEX_CONTRIB.KR` | Net exports — contribution to GDP growth | `301/DT_200Y123/ALL/ALL` | Q | Y | ⚠ |
| `BOK.GDP.INVENT_CONTRIB.KR` | Inventories — contribution to GDP growth | `301/DT_200Y123/<invent>` | Q | Y | ⚠ |
| `BOK.SAVING_RATE.KR` | Gross national saving rate (% of GNI) | `301/DT_200Y156/ALL/ALL` | Q | N | ⚠ |
| `BOK.HH_DISP_INCOME.YOY.KR` | Household disposable income, YoY % | `301/DT_200Y159/ALL/ALL` | Q | N | ⚠ |

### 1b. Labour market (category `labour`, source KOSTAT orgId=101)

| `imdr_code` | Display name | `source_code` | Freq | SA | Status |
|---|---|---|:---:|:---:|:---:|
| `KOSTAT.EMPLOY.LEVEL.KR` | Employed persons, thousands | `101/<EAPS table>/<employed>` | M | Y | ❓ |
| `KOSTAT.UNEMPLOY.RATE.SA.KR` | Unemployment rate, %, SA | `101/<EAPS table>/<unemp rate SA>` | M | Y | ❓ |
| `KOSTAT.UNEMPLOY.RATE.NSA.KR` | Unemployment rate, %, NSA | `101/<EAPS table>/<unemp rate>` | M | N | ❓ |
| `KOSTAT.LFPR.KR` | Labour force participation rate, % | `101/<EAPS table>/<LFPR>` | M | Y | ❓ |
| `KOSTAT.EMPLOY_RATIO.KR` | Employment-to-population ratio, % | `101/<EAPS table>/<E/P>` | M | Y | ❓ |
| `KOSTAT.EMPLOY.YOY.KR` | Employed persons, YoY change ('000) | derived from above | M | N | derived |
| `KOSTAT.EMPLOY.MFG.YOY.KR` | Manufacturing employment, YoY | `101/<EAPS by industry>` | M | N | ❓ |
| `KOSTAT.YOUTH_UNEMP.RATE.KR` | Youth (15-29) unemployment rate, % | `101/<EAPS by age>` | M | Y | ❓ |

### 1c. Industrial activity / sales (category `gdp`, source KOSTAT orgId=101)

| `imdr_code` | Display name | `source_code` | Freq | SA | Status |
|---|---|---|:---:|:---:|:---:|
| `KOSTAT.IIP.YOY.KR` | Industrial production, YoY % | `101/<IIP table>` | M | N | ❓ |
| `KOSTAT.IIP.MFG.YOY.KR` | Mfg production, YoY % | `101/<IIP mfg>` | M | N | ❓ |
| `KOSTAT.CAP_UTIL.KR` | Manufacturing capacity utilisation, % | `101/<IIP cap util>` | M | Y | ❓ |
| `KOSTAT.MFG_INVENT.YOY.KR` | Mfg inventories, YoY % | `101/<IIP invent>` | M | N | ❓ |
| `KOSTAT.RETAIL_SALES.YOY.KR` | Retail sales index, YoY % | `101/<retail sales>` | M | N | ❓ |
| `KOSTAT.SVC_PROD.YOY.KR` | Services production index, YoY % | `101/<services prod>` | M | N | ❓ |

### 1d. Surveys / sentiment (category `sentiment`, source BOK orgId=301)

| `imdr_code` | Display name | `source_code` | Freq | SA | Status |
|---|---|---|:---:|:---:|:---:|
| `BOK.BSI.MFG.KR` | Business Sentiment Index, manufacturing | `301/<BSI table>` | M | N | ❓ |
| `BOK.BSI.NONMFG.KR` | Business Sentiment Index, non-manufacturing | `301/<BSI table>` | M | N | ❓ |
| `BOK.CCI.KR` | Consumer Composite Sentiment Index | `301/<CCI table>` | M | N | ❓ |
| `BOK.INFL_EXP.1Y.KR` | 1-year-ahead inflation expectation (CCI sub) | `301/<CCI inflation exp>` | M | N | ❓ |

### 1e. Fiscal (category `gdp`)

| `imdr_code` | Display name | `source_code` | Freq | SA | Status |
|---|---|---|:---:|:---:|:---:|
| `BOK.GOV.TOT_REVENUE.KR` | Government total revenue, KRW bn | `301/DT_200Y154/<revenue>` | A | N | ⚠ |
| `BOK.GOV.TOT_EXPEND.KR` | Government total expenditure, KRW bn | `301/DT_200Y154/<expend>` | A | N | ⚠ |
| `BOK.GOV.BALANCE.KR` | Government balance (revenue − expenditure) | derived | A | N | derived |
| `BOK.GOV.DEBT.GDP.KR` | General government debt / GDP, % | `101/<fiscal table>` | A | N | ❓ |

---

## 2. Inflation Engine

### 2a. CPI (category `cpi`, source BOK orgId=301)

| `imdr_code` | Display name | `source_code` | Freq | SA | Status |
|---|---|---|:---:|:---:|:---:|
| `BOK.CPI.HEADLINE.LEVEL.KR` | CPI headline, 2020=100 | `301/DT_404Y014/*AA/ALL` | M | N | ✅ |
| `BOK.CPI.HEADLINE.YOY.KR` | CPI headline, YoY % | derived from level | M | N | derived |
| `BOK.CPI.HEADLINE.MOM.KR` | CPI headline, MoM % | derived from level | M | Y | derived |
| `BOK.CPI.CORE.LEVEL.KR` | Core CPI (ex food & energy), 2020=100 | `301/DT_404Y014/<core>` | M | N | ⚠ |
| `BOK.CPI.CORE.YOY.KR` | Core CPI, YoY % | derived | M | N | derived |
| `BOK.CPI.FOOD.YOY.KR` | CPI food, YoY % | `301/DT_404Y014/<food>` | M | N | ⚠ |
| `BOK.CPI.ENERGY.YOY.KR` | CPI energy, YoY % | `301/DT_404Y014/<energy>` | M | N | ⚠ |
| `BOK.CPI.SERVICES.YOY.KR` | CPI services, YoY % | `301/DT_404Y014/<services>` | M | N | ⚠ |
| `BOK.CPI.GOODS.YOY.KR` | CPI goods, YoY % | `301/DT_404Y014/<goods>` | M | N | ⚠ |
| `BOK.CPI.HOUSING_RENT.YOY.KR` | CPI housing & rents, YoY % | `301/DT_404Y014/<housing>` | M | N | ⚠ |
| `BOK.CPI.LIVING_NECESS.YOY.KR` | CPI necessities (생활물가지수), YoY % | `301/<necessity table>` | M | N | ⚠ |
| `BOK.CPI.FRESH_FOOD.YOY.KR` | CPI fresh food (신선식품), YoY % | `301/<fresh food>` | M | N | ⚠ |

### 2b. PPI / import-export prices (category `cpi`, source BOK orgId=301)

| `imdr_code` | Display name | `source_code` | Freq | SA | Status |
|---|---|---|:---:|:---:|:---:|
| `BOK.PPI.HEADLINE.YOY.KR` | PPI total, YoY % | `301/<PPI table>` | M | N | ⚠ |
| `BOK.PPI.MFG.YOY.KR` | PPI manufacturing, YoY % | `301/<PPI mfg>` | M | N | ⚠ |
| `BOK.PPI.SERVICES.YOY.KR` | PPI services, YoY % | `301/<PPI svc>` | M | N | ⚠ |
| `BOK.IMPORT_PRICE.YOY.KR` | Import price index, YoY % | `301/<import price>` | M | N | ⚠ |
| `BOK.EXPORT_PRICE.YOY.KR` | Export price index, YoY % | `301/<export price>` | M | N | ⚠ |
| `BOK.IMPORT_PRICE.NONOIL.YOY.KR` | Import price ex oil, YoY % | `301/<import ex oil>` | M | N | ⚠ |

### 2c. Wages (category `labour`, source KOSTAT orgId=101)

| `imdr_code` | Display name | `source_code` | Freq | SA | Status |
|---|---|---|:---:|:---:|:---:|
| `KOSTAT.WAGE.AVG_ALL.YOY.KR` | Avg monthly wage, all industries, YoY % | `101/<wage survey>` | M | N | ❓ |
| `KOSTAT.WAGE.MFG.YOY.KR` | Avg monthly wage, manufacturing, YoY % | `101/<wage mfg>` | M | N | ❓ |
| `KOSTAT.MIN_WAGE.HOURLY.KR` | Statutory minimum wage, KRW/hour | `101/<minimum wage>` | A | — | ❓ |

---

## 3. External & FX

### 3a. Balance of Payments — Current Account (category `bop`, source BOK orgId=301, tblId=DT_301Y013)

| `imdr_code` | Display name | `source_code` | Freq | SA | Status |
|---|---|---|:---:|:---:|:---:|
| `BOK.BOP.CA.TOTAL.NSA.KR` | Current Account, total, NSA, USD mn | `301/DT_301Y013/100000` | M | N | ✅ |
| `BOK.BOP.CA.GOODS.KR` | CA — Goods balance | `301/DT_301Y013/110000` | M | N | ✅ |
| `BOK.BOP.CA.SERVICES.KR` | CA — Services balance | `301/DT_301Y013/200000` | M | N | ✅ |
| `BOK.BOP.CA.PRIMARY_INC.KR` | CA — Primary income balance | `301/DT_301Y013/3A0000+3B0000` | M | N | ✅ |
| `BOK.BOP.CA.SECONDARY_INC.KR` | CA — Secondary income balance | `301/DT_301Y013/<secondary>` | M | N | ⚠ |
| `BOK.BOP.CA.TOTAL.SA.KR` | Current Account, SA | `301/DT_301Y017/100000` | M | Y | ⚠ |
| `BOK.BOP.GOODS.EXPORTS.KR` | Goods exports (BoP-basis) | `301/DT_301Y013/<X goods>` | M | N | ⚠ |
| `BOK.BOP.GOODS.IMPORTS.KR` | Goods imports (BoP-basis) | `301/DT_301Y013/<M goods>` | M | N | ⚠ |
| `BOK.BOP.SVC.TRAVEL.KR` | Services — Travel balance | `301/DT_301Y013/<travel>` | M | N | ⚠ |
| `BOK.BOP.SVC.TRANSPORT.KR` | Services — Transport balance | `301/DT_301Y013/<transport>` | M | N | ⚠ |
| `BOK.BOP.PRIMARY.DI_INC.KR` | Primary income — direct investment income | `301/DT_301Y013/3BA000` | M | N | ✅ |
| `BOK.BOP.PRIMARY.SI_INC.KR` | Primary income — securities investment income | `301/DT_301Y013/3BC000` | M | N | ✅ |

### 3b. Balance of Payments — Financial Account (category `bop`, source BOK orgId=301, tblId=DT_301Y013)

| `imdr_code` | Display name | `source_code` | Freq | SA | Status |
|---|---|---|:---:|:---:|:---:|
| `BOK.BOP.FA.TOTAL.KR` | Financial Account, total net | `301/DT_301Y013/BOPF00000000` | M | N | ✅ |
| `BOK.BOP.FA.DI.ASSETS.KR` | Direct Investment Assets (outward FDI) | `301/DT_301Y013/BOPF11000000` | M | N | ✅ |
| `BOK.BOP.FA.DI.LIAB.KR` | Direct Investment Liabilities (inward FDI) | `301/DT_301Y013/BOPF12000000` | M | N | ✅ |
| `BOK.BOP.FA.SI_EQ.ASSETS.KR` | Securities Investment Equity Assets | `301/DT_301Y013/BOPF21000000` | M | N | ✅ |
| `BOK.BOP.FA.SI_EQ.LIAB.KR` | Securities Investment Equity Liabilities | `301/DT_301Y013/BOPF22000000` | M | N | ✅ |
| `BOK.BOP.FA.SI_DEBT.ASSETS.KR` | Securities Investment Debt Assets | `301/DT_301Y013/BOPF31000000` | M | N | ✅ |
| `BOK.BOP.FA.SI_DEBT.LIAB.KR` | Securities Investment Debt Liabilities | `301/DT_301Y013/BOPF32000000` | M | N | ✅ |
| `BOK.BOP.FA.OI.ASSETS.KR` | Other Investment Assets | `301/DT_301Y013/BOPF41000000` | M | N | ✅ |
| `BOK.BOP.FA.OI.LIAB.KR` | Other Investment Liabilities | `301/DT_301Y013/BOPF42000000` | M | N | ✅ |
| `BOK.BOP.FA.RES.KR` | Reserve Assets — transactional change | `301/DT_301Y013/BOPF50000000` | M | N | ✅ |
| `BOK.BOP.EO.KR` | Errors & Omissions | `301/DT_301Y013/BOPO00000000` | M | N | ✅ |

### 3c. International Investment Position (category `bop`, source BOK orgId=301)

| `imdr_code` | Display name | `source_code` | Freq | SA | Status |
|---|---|---|:---:|:---:|:---:|
| `BOK.IIP.NET.KR` | Net IIP (assets − liabilities), USD bn | `301/DT_311Y001/<net>` | Q | N | ⚠ |
| `BOK.IIP.ASSETS.TOTAL.KR` | IIP — total assets stock | `301/DT_311Y005/<total>` | Q | N | ⚠ |
| `BOK.IIP.LIAB.TOTAL.KR` | IIP — total liabilities stock | `301/DT_311Y001/<liab>` | Q | N | ⚠ |
| `BOK.EXT_DEBT.TOTAL.KR` | External debt, total | `301/DT_311Y004/<total>` | Q | N | ⚠ |
| `BOK.EXT_DEBT.ST.KR` | External debt, short-term (≤1Y) | `301/DT_311Y004/<short>` | Q | N | ⚠ |
| `BOK.EXT_DEBT.LT.KR` | External debt, long-term | `301/DT_311Y004/<long>` | Q | N | ⚠ |
| `BOK.NET_EXT_ASSETS.KR` | Net external assets | `301/DT_311Y006/<net>` | Q | N | ⚠ |

### 3d. Customs trade (category `bop`, source KOSTAT orgId=101 or Customs orgId=343)

| `imdr_code` | Display name | `source_code` | Freq | SA | Status |
|---|---|---|:---:|:---:|:---:|
| `KOSTAT.TRADE.EXPORTS.USD.KR` | Customs exports, USD bn | `101/<trade overview>` | M | N | ❓ |
| `KOSTAT.TRADE.IMPORTS.USD.KR` | Customs imports, USD bn | `101/<trade overview>` | M | N | ❓ |
| `KOSTAT.TRADE.BALANCE.KR` | Customs trade balance | derived | M | N | derived |
| `KOSTAT.TRADE.EXP.CHIPS.KR` | Exports — semiconductors, USD bn | `101/<trade by nature>` | M | N | ❓ |
| `KOSTAT.TRADE.EXP.AUTO.KR` | Exports — automobiles, USD bn | `101/<trade by nature>` | M | N | ❓ |
| `KOSTAT.TRADE.EXP.CHINA.KR` | Exports to China, USD bn | `101/<trade by country>` | M | N | ❓ |
| `KOSTAT.TRADE.EXP.US.KR` | Exports to US, USD bn | `101/<trade by country>` | M | N | ❓ |
| `KOSTAT.TRADE.IMP.OIL.KR` | Imports — crude oil, USD bn | `101/<trade by nature>` | M | N | ❓ |

### 3e. Terms of trade (category `bop`, source BOK orgId=301, tblId=DT_403Y005)

| `imdr_code` | Display name | `source_code` | Freq | SA | Status |
|---|---|---|:---:|:---:|:---:|
| `BOK.TOT.COMMODITY.KR` | Commodity terms of trade, 2020=100 | `301/DT_403Y005/TERMS_TRADE_TYPE.A` | M | N | ✅ |
| `BOK.TOT.INCOME.KR` | Income terms of trade, 2020=100 | `301/DT_403Y005/<income>` | M | N | ⚠ |
| `BOK.XP_PRICE_IDX.KR` | Export price index, 2020=100 | `301/DT_403Y005/<X>` | M | N | ⚠ |
| `BOK.MP_PRICE_IDX.KR` | Import price index, 2020=100 | `301/DT_403Y005/<M>` | M | N | ⚠ |

### 3f. FX reserves + REER/NEER (category `fx`, source: see Source column)

| `imdr_code` | Display name | `source_code` | Freq | SA | Status |
|---|---|---|:---:|:---:|:---:|
| `BOK.FX_RES.TOTAL.KR` | FX reserves, total stock, USD bn | BOK direct or FRED `TRESEGKRM052N` | M | N | ❌ KOSIS mirror missing |
| `BOK.FX_RES.SDR.KR` | FX reserves — SDR holdings | BOK direct | M | N | ❌ |
| `BOK.FX_RES.GOLD.KR` | FX reserves — gold valuation | BOK direct | M | N | ❌ |
| `BIS.REER.KRW.KR` | BIS REER for KRW, broad index | FRED `RBKRBIS` | M | N | ❌ via FRED |
| `BIS.NEER.KRW.KR` | BIS NEER for KRW, broad index | FRED `NBKRBIS` | M | N | ❌ via FRED |

FX **rates** themselves (KRW spot, NDF, forwards, vol) sit in the market-
data domain (Citi) — NOT seeded into `econ.dim_indicator`.

---

## 4. Policy Transmission

### 4a. Policy rate (category `rates`, source BOK orgId=301, tblId=DT_121Y002)

| `imdr_code` | Display name | `source_code` | Freq | SA | Status |
|---|---|---|:---:|:---:|:---:|
| `BOK.BASE_RATE.KR` | BOK Base Rate, % | `301/DT_121Y002/ACC_ITEM.BEABAA1` | M | N | ✅ |
| `BOK.CALL_RATE.ON.KR` | Overnight call money rate, % | `301/DT_121Y002/<call>` | M | N | ⚠ |
| `BOK.CD_RATE.91D.KR` | CD 91-day rate, % | `301/DT_121Y002/<CD 91d>` | M | N | ⚠ |
| `BOK.KORIBOR.1M.KR` | KORIBOR 1-month fixing, % | `301/DT_121Y002/<KORIBOR 1M>` | D/M | N | ⚠ |
| `BOK.KORIBOR.3M.KR` | KORIBOR 3-month fixing, % | `301/DT_121Y002/<KORIBOR 3M>` | D/M | N | ⚠ |
| `BOK.KORIBOR.6M.KR` | KORIBOR 6-month fixing, % | `301/DT_121Y002/<KORIBOR 6M>` | D/M | N | ⚠ |

### 4b. Money supply (category `cb_balance_sheet`, source BOK orgId=301, tblId=DT_101Y004)

| `imdr_code` | Display name | `source_code` | Freq | SA | Status |
|---|---|---|:---:|:---:|:---:|
| `BOK.MS.M1.LEVEL.KR` | M1 (narrow money), KRW tn | `301/DT_101Y004/<M1>` | M | Y | ✅ table |
| `BOK.MS.M2.LEVEL.KR` | M2 (broad money), KRW tn | `301/DT_101Y004/<M2>` | M | Y | ✅ table |
| `BOK.MS.LF.LEVEL.KR` | Lf (liquidity aggregate), KRW tn | `301/DT_101Y004/<Lf>` | M | Y | ✅ table |
| `BOK.MS.M2.YOY.KR` | M2, YoY % | derived | M | N | derived |
| `BOK.CURRENCY.CIRC.KR` | Currency in circulation | `301/DT_101Y004/<currency>` | M | N | ⚠ |

### 4c. Bank loans / lending (category `credit`, source BOK orgId=301)

| `imdr_code` | Display name | `source_code` | Freq | SA | Status |
|---|---|---|:---:|:---:|:---:|
| `BOK.LOANS.TOTAL.KR` | Total loans of deposit-taking institutions | `301/<bank loans tot>` | M | N | ⚠ |
| `BOK.LOANS.HOUSEHOLD.KR` | Household loans, total | `301/<HH loans>` | M | N | ⚠ |
| `BOK.LOANS.HH.MORTGAGE.KR` | Household mortgage loans | `301/<HH mortgage>` | M | N | ⚠ |
| `BOK.LOANS.HH.UNSEC.KR` | Household unsecured loans | `301/<HH unsec>` | M | N | ⚠ |
| `BOK.LOANS.CORP.KR` | Corporate loans, total | `301/<corp loans>` | M | N | ⚠ |
| `BOK.LOAN_RATE.NEW.HH.KR` | Avg new loan rate, households, % | `301/DT_121Y002/<HH loan rate>` | M | N | ⚠ |
| `BOK.LOAN_RATE.NEW.CORP.KR` | Avg new loan rate, corporates, % | `301/DT_121Y002/<corp loan rate>` | M | N | ⚠ |
| `BOK.DEPOSIT_RATE.NEW.KR` | Avg new deposit rate, % | `301/DT_121Y002/<deposit rate>` | M | N | ⚠ |

### 4d. Balance sheets / credit aggregates (category `balance_sheet`)

| `imdr_code` | Display name | `source_code` | Freq | SA | Status |
|---|---|---|:---:|:---:|:---:|
| `BOK.HH_CREDIT.TOTAL.KR` | Household credit, total stock, KRW tn | `301/<HH credit FSR>` | Q | N | ⚠ |
| `BOK.HH_CREDIT.GDP.KR` | Household credit / GDP, % | derived | Q | N | derived |
| `BOK.CORP_DEBT.GDP.KR` | Corporate debt / GDP, % | `301/<corp debt FSR>` | Q | N | ❓ |

### 4e. Bank quality (category `balance_sheet`, source BOK orgId=301 / FSS)

| `imdr_code` | Display name | `source_code` | Freq | SA | Status |
|---|---|---|:---:|:---:|:---:|
| `BOK.BANK.NPL_RATIO.KR` | Bank substandard-and-below ratio, % | `301/<FSR NPL>` | Q | N | ❓ |
| `BOK.BANK.BIS_RATIO.KR` | Bank BIS capital ratio, % | `301/<FSR capital>` | Q | N | ❓ |
| `BOK.BANK.LDR.KR` | Bank loan-to-deposit ratio, % | `301/<FSR LDR>` | Q | N | ❓ |

### 4f. Housing (category `housing`)

**Apartment price indices — REB R-ONE (weekly, 2012-05-07 → present):**

| `imdr_code` | Display name | `source_code` | Freq | SA | Status |
|---|---|---|:---:|:---:|:---:|
| `REB.HOUSING.APT_SALE.LEVEL.KR_NAT` | Nationwide apartment sale price index | `REB/T244183132827305/CLS_ID=50001` | W | N | ✅ playground |
| `REB.HOUSING.APT_SALE.LEVEL.KR_SEOUL` | Seoul apartment sale price index | `REB/T244183132827305/CLS_ID=50008` | W | N | ✅ playground |
| `REB.HOUSING.APT_JEONSE.LEVEL.KR_NAT` | Nationwide apartment jeonse price index | `REB/T247713133046872/CLS_ID=50001` | W | N | ✅ playground |
| `REB.HOUSING.APT_JEONSE.LEVEL.KR_SEOUL` | Seoul apartment jeonse price index | `REB/T247713133046872/CLS_ID=50008` | W | N | ✅ playground |

Fetcher: [`playground/econ/reb/fetch_housing.py`](../../../../playground/econ/reb/fetch_housing.py).
Confirmed 2026-06-04: 4 series × 732 weeks each = 2,928 observations,
window 2012-05-07 → 2026-06-01. Levels are 2026-02-02 = 100.0 base.

**Same 4 indicators via KOSIS mirror (orgId=408, weekly, ~2021-07 → present):**
Cross-check path at
[`playground/econ/kosis/fetch_reb_housing.py`](../../../../playground/econ/kosis/fetch_reb_housing.py) —
uses `DT_304004_WEEK_002_A` (sale) + `DT_304004_WEEK_004_A` (jeonse) with
`objL1=a0`/`a7`. Reconciled to 0 bp YoY drift against REB on 2025-06-02,
2025-12-29, 2026-01-26 anchors. Same `imdr_code`s, `vendor_name=KOSIS`.
KOSIS uses 2025-03-31 = 100.0 base — different from REB, identical YoY.

**Other housing (KOSTAT, monthly, lower-frequency cuts):**

| `imdr_code` | Display name | `source_code` | Freq | SA | Status |
|---|---|---|:---:|:---:|:---:|
| `KOSTAT.HOUSING_TRANS.KR` | Housing transactions, monthly count | `101/<transactions>` | M | N | ❓ |
| `KOSTAT.HOUSING_STARTS.KR` | New housing starts, monthly count | `101/<housing starts>` | M | N | ❓ |

---

## 5. Summary counts

| Engine | Cluster cells covered | Indicator rows | Confirmed (✅) | Candidate (⚠) | Unknown (❓) | KOSIS-absent (❌) |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| Growth | 1.1 / 1.2 / 1.3 / 1.4 | 35 | 0 (2 table-confirmed) | 16 | 19 | 0 |
| Inflation | 2.1 / 2.2 / 2.3 / 2.4 | 21 | 1 | 17 | 3 | 0 |
| External | 3.1 / 3.2 / 3.3 / 3.4 | 35 | 13 | 17 | 0 | 5 |
| Policy | 4.1 / 4.2 / 4.3 / 4.4 | 30 | 0 (5 table-confirmed) | 19 | 11 | 0 |
| **Total** | **16 / 16** | **121** | **14 ✅** | **69 ⚠** | **33 ❓** | **5 ❌** |

121 target rows for KR — that puts Korea between Hong Kong (29) and US
(133) in coverage density, consistent with the country's market weight
in Asia ex-Japan.

## 6. Build sequence (refines plan §6)

Strict priority order — each row below is a ~1-day fetcher + load:

| # | Fetcher | Tables | Indicators landed | Status |
|---|---|---|:---:|---|
| 1 | `kosis_bop.py` (already in playground) | `DT_301Y013` + `DT_301Y017` | 12 ✅ + 11 ✅ = 23 | playground only; needs DB loader |
| 2 | `kosis_cpi.py` | `DT_404Y014` | 12 (1 ✅, rest ⚠) | new |
| 3 | `kosis_rates.py` | `DT_121Y002` | 9 (1 ✅, rest ⚠) | new |
| 4 | `kosis_money.py` | `DT_101Y004` | 5 (table ✅, items ⚠) | new |
| 5 | `kosis_gdp.py` | `DT_200Y102` + `DT_200Y107`-`110` + `DT_200Y113` | 17 | new |
| 6 | `kosis_tot.py` | `DT_403Y005` | 4 (1 ✅, rest ⚠) | new |
| 7 | `kosis_iip.py` | `DT_311Y001`-`006` | 7 | new |
| 8 | `kostat_labour.py` | EAPS survey tables (orgId=101) | 8 | needs catalogue browse |
| 9 | `kostat_iip.py` | IIP / retail / services prod | 6 | needs catalogue browse |
| 10 | `kostat_trade.py` | Customs trade tables (orgId=101) | 8 | needs catalogue browse |
| 11 | `kostat_housing.py` | Housing tables (orgId=101) | 5 | needs catalogue browse |
| 12 | `bok_sentiment.py` | BSI + CCI tables (orgId=301) | 4 | needs catalogue browse |
| 13 | `bok_loans.py` | Bank loans + loan rates (orgId=301) | 8 | needs catalogue browse |
| 14 | `bok_fsr.py` | Financial Stability Report tables | 6 | needs catalogue browse |
| 15 | `bok_fx_reserves.py` | BOK Currency/Finance branch (NOT KOSIS) | 3 | Playwright/scrape — branch 1 unexplored |
| 16 | `bis_reer_neer.py` | FRED `RBKRBIS` + `NBKRBIS` | 2 | wire into FRED ingest |
| 17 | `bok_ppi.py` | `404Y…` PPI sub-tables | 6 | new |
| 18 | `kostat_wages.py` | Wage survey tables | 3 | needs catalogue browse |

Total: 121 indicators across 18 fetchers. Steps 1-6 are quickest (tables confirmed) — should fill ~50 indicators in the first week.

## 7. Open questions before starting

- **`econ.dim_indicator.frequency_id`**: existing rows mix M (HKMA) and other cadences. Confirm M=7 vs Q=8 conventions before seeding.
- **`is_seasonally_adjusted` flag**: BOK publishes both SA and NSA for many series. Default to keeping both rows where available (e.g. `BOK.BOP.CA.TOTAL.NSA.KR` + `BOK.BOP.CA.TOTAL.SA.KR`) — same convention as the wiring map's KR ⚠ on §3.2 already.
- **Derivation policy**: rows marked "derived" (YoY from level, balances from gross flows) — load the underlying source row and compute the derivation at query time, OR materialise the derived row? Existing pattern: HKMA loaders materialise. Recommend: keep derivations as separate `dim_indicator` rows with `source_code` referencing the source `imdr_code` (e.g. `derived from BOK.MS.M2.LEVEL.KR yoy`).
- **`dim_vendor`**: need entries for `KOSIS` and `KOSTAT` (or single `KOSIS` covering both since they're the same API endpoint). Pattern from HKMA: one vendor row.
- **Country FK**: `country_id=27` for Korea (confirmed from `dbo.dim_country`).

## Cross-refs

- KOSIS mechanics: [kosis_openapi_reference.md](kosis_openapi_reference.md)
- Concept-level cluster mapping: [kosis_kr_coverage_plan.md](kosis_kr_coverage_plan.md)
- BoP item codes (BOPF…/BOPO…): [ecos_api_reference.md](ecos_api_reference.md) + [_playground/bop.md](_playground/bop.md)
- Wiring map KR row: [macro_economy_wiring_map.md §7.13](../macro_economy_wiring_map.md#713-south-korea-kr)
- Sister country with similar density: [HKMA wiring §7.10](../macro_economy_wiring_map.md#710-hong-kong-hk) — 29 indicators, 7 of 16 cells ⚠
