# Indonesia (ID) — economic indicator target list

Last updated: 2026-06-08 (targets doc — pre-build planning, superseded by actual inventory)

> **Note (2026-06-10):** This doc was written as a pre-build shopping list before
> any indicators were loaded. As of 2026-06-10, **289 indicators are live in
> `econ.fact_indicator`** (BPS 82 + BI 165 + BIS 6 + DJPPR 36). The authoritative
> live inventory is [`indonesia_indicator_inventory.md`](indonesia_indicator_inventory.md).
> This file is retained as the original design intent (it shows which concepts
> were targeted and the initial vendor-table mapping). It has **not** been
> retroactively updated to reflect what was actually built — the inventory doc
> is the source of truth.

The **concrete shopping list** of Indonesia economic time series we want
loaded into `econ.dim_indicator`. Companion to
[`id_coverage_plan.md`](id_coverage_plan.md) (which maps wiring-map cells
to vendor tables at the **concept** level). This doc translates those
concepts into specific `dim_indicator` rows, one line per series.

**Status (2026-06-08 original): 0 indicators loaded.** Targets below are planning
placeholders; actual `imdr_code` strings will be finalised post-Phase B
when BPS `domain`/`var`/`turvar` identifiers are confirmed against the
live API. Codes follow the Korea convention: `{VENDOR}.{CATEGORY}.{SUB}.{FREQ_OR_TRANSFORM}.{COUNTRY}`.

## Build progress

| Group | Target rows | Vendor | DB? |
|---|:---:|---|:---:|
| BPS CPI (headline + groups + core) | ~14 | BPS | ⏳ |
| BPS GDP (level + components × sector × expenditure) | ~22 | BPS | ⏳ |
| BPS Labour (Sakernas) | ~8 | BPS | ⏳ |
| BPS PPI / WPI | ~7 | BPS | ⏳ |
| BPS Import + Export Price indices | ~6 | BPS | ⏳ |
| BPS Trade Value + Volume indices (4 series × value/volume) | ~8 | BPS | ⏳ |
| BPS Customs Trade (goods exports/imports/balance) | ~5 | BPS | ⏳ |
| BPS Retail Sales (penjualan eceran) | ~6 | BPS | ⏳ |
| BPS Industrial Production (IBS + IMK) | ~4 | BPS | ⏳ |
| BI BoP (CA + FA + items) | ~24 | BI | ⏳ |
| BI Monetary aggregates (M1, M2, currency, broad liq) | ~5 | BI | ⏳ |
| BI Bank credit (HH + corp, stock + flow) | ~8 | BI | ⏳ |
| BI Interest rates (policy + JIBOR + lending + deposit) | ~10 | BI | ⏳ |
| BI Banking Survey (SBP — lending standards) | ~6 | BI | ⏳ |
| BI Consumer / Business surveys (SK + SKDU) | ~10 | BI | ⏳ |
| BI FX reserves (stock + valuation-adj change) | ~3 | BI | ⏳ |
| BI External debt (SULNI) | ~6 | BI | ⏳ |
| MoF Fiscal aggregates (APBN revenue + spending + balance) | ~6 | MoF | ⏳ |
| DJPPR Govt debt + SBN | ~4 | DJPPR | ⏳ |
| OJK Banking sector (CAR, NPL, ROA) | ~5 | OJK | ⏳ |
| IBPA INDOGB curve key tenors | ~6 | IBPA / BI | ⏳ |
| BIS REER / NEER / DSR | ~5 | BIS | ⏳ |
| FRED ID mirror (carry from existing seed) | ~4 | FRED | ⏳ |

**Estimated total target**: ~170 indicators (similar magnitude to Korea).

## Scope

| In scope | Out of scope (covered by market-data layer) |
|---|---|
| GDP + components, labour, industrial, sentiment | IHSG / JCI equity index (equity domain — Citi `EQUITY.EQUITY_INDEX.JCI.LEVEL.REUTERS`) |
| CPI, PPI, import/export prices, wages | IDR spot / forwards / NDF (FX domain — Citi `FX.SPOT.USD.IDR.CITI`, `FX.FORWARD.FWD_OUTRIGHT.USD.IDR.*.CITI`) |
| BoP, IIP, external debt, customs trade, terms of trade | IDR FX vol surface (FX domain — Citi `FX.VOL.USD.IDR.*.*.IMPLIED.CITI`) |
| FX reserves, REER, NEER | IDR SOV_CMT yield curve (rates domain — Citi `RATES.SOV_CMT.IDN.*.CITI`) |
| BI 7-Day RR Rate, money supply, bank loans, household credit | IDR IRS curve + swaption vol (rates domain — Citi `RATES.SWAP_LIBOR.IDR.*.CITI`) |
| SK / SKDU / ITK / IKK sentiment surveys | IDR XCCY basis (rates domain — Citi `RATES.XCCY_OIS_SWAP.IDR.USD.*.CITI`) |
| Bank NPL ratio, government debt, SBN issuance | |

If a concept is published in **both** market data and an econ source
(notably BI 7-Day RR Rate, JIBOR), we keep **both** for cross-validation —
same convention as Korea's BOK Base Rate + KORIBOR.

## Indicator targets (placeholders — finalised after Phase B)

### 1. Growth Engine

#### 1.1 Private Demand

| `imdr_code` (target) | Freq | Source | Notes |
|---|:---:|---|---|
| `BPS.RETAIL.ITK.QOQ.ID` | Q | BPS Survei Tendensi Konsumen | Consumer Tendency Index |
| `BI.RETAIL.ECERAN.MOM.ID` | M | BI SK | Penjualan Eceran headline (BI publishes via Consumer Survey supplement) |
| `BI.SENTIMENT.IKK.LEVEL.ID` | M | BI SK | Consumer Confidence Index |
| `BI.SENTIMENT.IKE.LEVEL.ID` | M | BI SK | Current Conditions Index |
| `BI.SENTIMENT.IEK.LEVEL.ID` | M | BI SK | Consumer Expectations Index |
| `BI.HH_CREDIT.STOCK.LEVEL.ID` | M | BI SEKI | Household credit stock |
| `BI.HH_CREDIT.FLOW.MOM.ID` | M | BI SEKI | Household credit flow |

#### 1.2 Fiscal Demand

| `imdr_code` (target) | Freq | Source | Notes |
|---|:---:|---|---|
| `MOF.FISCAL.REVENUE.YTD.ID` | M | MoF APBN | Central govt revenue YTD |
| `MOF.FISCAL.EXPEND.YTD.ID` | M | MoF APBN | Central govt expenditure YTD |
| `MOF.FISCAL.BALANCE.YTD.ID` | M | MoF APBN | Central govt fiscal balance |
| `MOF.FISCAL.TAX_REV.YTD.ID` | M | MoF / DJP | Tax revenue YTD |
| `BPS.GDP.GOVT_C.QOQ.ID` | Q | BPS PDB Penggunaan | Govt final consumption |
| `BPS.GDP.GOVT_I.QOQ.ID` | Q | BPS PDB Penggunaan | Govt investment |
| `DJPPR.DEBT.GOVT.GDP.ID` | M | DJPPR debt profile | Govt debt / GDP |

#### 1.3 External Demand

| `imdr_code` (target) | Freq | Source | Notes |
|---|:---:|---|---|
| `BPS.TRADE.EXPORT.USD.ID` | M | BPS Statistik Ekspor | Goods exports (customs, USD) |
| `BPS.TRADE.IMPORT.USD.ID` | M | BPS Statistik Impor | Goods imports (customs, USD) |
| `BPS.TRADE.BALANCE.USD.ID` | M | BPS derived | Goods trade balance |
| `BPS.EXPORT_PRICE.INDEX.ID` | M | BPS Indeks Unit Nilai Ekspor | Export unit-value index |
| `BPS.EXPORT_VOL.INDEX.ID` | M | BPS Indeks Volume Ekspor | Export volume index |
| `BPS.IMPORT_PRICE.INDEX.ID` | M | BPS Indeks Unit Nilai Impor | Import unit-value index |
| `BPS.IMPORT_VOL.INDEX.ID` | M | BPS Indeks Volume Impor | Import volume index |
| `BI.BOP.GOODS.EXP.USD.ID` | Q | BI SEKI BoP | Goods exports (BoP basis) |
| `BI.BOP.GOODS.IMP.USD.ID` | Q | BI SEKI BoP | Goods imports (BoP basis) |
| `BI.BOP.GOODS.BAL.USD.ID` | Q | BI SEKI BoP | Goods balance (BoP basis) |

#### 1.4 Macro Core

| `imdr_code` (target) | Freq | Source | Notes |
|---|:---:|---|---|
| `BPS.GDP.GDP.QOQ_SA.ID` | Q | BPS PDB Triwulanan | Headline real GDP QoQ-SA |
| `BPS.GDP.GDP.YOY.ID` | Q | BPS PDB Triwulanan | Headline real GDP YoY |
| `BPS.GDP.GDP.LEVEL_REAL.ID` | Q | BPS PDB Triwulanan | Real GDP level (constant 2010 prices) |
| `BPS.GDP.GDP.LEVEL_NOM.ID` | Q | BPS PDB Triwulanan | Nominal GDP level |
| `BPS.GDP.DEFLATOR.YOY.ID` | Q | derived | GDP deflator |
| `BPS.GDP.MFG.YOY.ID` | Q | BPS PDB Lapangan Usaha | Manufacturing GDP |
| `BPS.GDP.SVC.YOY.ID` | Q | BPS PDB Lapangan Usaha | Services GDP |
| `BPS.GDP.AGRI.YOY.ID` | Q | BPS PDB Lapangan Usaha | Agriculture GDP |
| `BPS.GDP.MINING.YOY.ID` | Q | BPS PDB Lapangan Usaha | Mining GDP |
| `BPS.GDP.CONSTR.YOY.ID` | Q | BPS PDB Lapangan Usaha | Construction GDP |
| `BPS.GDP.PCE.YOY.ID` | Q | BPS PDB Penggunaan | Private consumption (PCE) |
| `BPS.GDP.GFCF.YOY.ID` | Q | BPS PDB Penggunaan | Gross fixed capital formation |
| `BPS.GDP.EXPORTS.YOY.ID` | Q | BPS PDB Penggunaan | GDP exports |
| `BPS.GDP.IMPORTS.YOY.ID` | Q | BPS PDB Penggunaan | GDP imports |
| `BPS.IP.MFG.YOY.ID` | Q | BPS IBS | Industrial Production — Large/Medium Mfg |
| `BPS.IP.SMALL_MFG.YOY.ID` | Q | BPS IMK | Industrial Production — Small Mfg |
| `BI.CAPUTIL.MFG.LEVEL.ID` | Q | BI SKDU | Manufacturing capacity utilisation |
| `BI.SENTIMENT.SKDU.LEVEL.ID` | Q | BI SKDU | Business sentiment composite |
| `BPS.LABOUR.EMPLOYED.LEVEL.ID` | SA | BPS Sakernas | Employed persons (Aug + Feb) |
| `BPS.LABOUR.UE_RATE.LEVEL.ID` | SA | BPS Sakernas | Unemployment rate |
| `BPS.LABOUR.LFPR.LEVEL.ID` | SA | BPS Sakernas | Labour force participation rate |
| `BPS.LABOUR.EMP_POP.LEVEL.ID` | SA | BPS Sakernas | Employment-to-population ratio |

### 2. Inflation Engine

#### 2.1 Input Costs

| `imdr_code` (target) | Freq | Source | Notes |
|---|:---:|---|---|
| `BPS.IMPORT_PRICE.IDR.YOY.ID` | M | BPS Unit Nilai Impor | Import price (IDR basis) |
| `BPS.IMPORT_PRICE.USD.YOY.ID` | M | BPS Unit Nilai Impor | Import price (USD basis) |

#### 2.2 Producer Prices

| `imdr_code` (target) | Freq | Source | Notes |
|---|:---:|---|---|
| `BPS.PPI.TOTAL.YOY.ID` | M | BPS IHP | Producer Price Index — total |
| `BPS.PPI.MFG.YOY.ID` | M | BPS IHP | Manufacturing PPI |
| `BPS.PPI.AGRI.YOY.ID` | M | BPS IHP | Agriculture PPI |
| `BPS.WPI.TOTAL.YOY.ID` | M | BPS IHPB | Wholesale Price Index — total |
| `BPS.EXPORT_PRICE.INDEX.YOY.ID` | M | BPS Unit Nilai Ekspor | Export price index |

#### 2.3 Domestic Costs

| `imdr_code` (target) | Freq | Source | Notes |
|---|:---:|---|---|
| `BPS.WAGE.AVG_NATIONAL.IDR.ID` | SA | BPS Sakernas Upah | Average wage |
| `BPS.WAGE.MFG.IDR.ID` | SA | BPS Sakernas | Mfg sector wage |
| `BPS.WAGE.SVC.IDR.ID` | SA | BPS Sakernas | Services wage |
| `BI.INFL_EXP.1Y.LEVEL.ID` | M | BI SK | 1Y inflation expectation |
| `BPS.CPI.RENT.YOY.ID` | M | BPS IHK | Housing/rent component |

#### 2.4 CPI Pressure

| `imdr_code` (target) | Freq | Source | Notes |
|---|:---:|---|---|
| `BPS.CPI.HEADLINE.LEVEL.ID` | M | BPS IHK | Headline CPI level (2022=100) |
| `BPS.CPI.HEADLINE.YOY.ID` | M | BPS derived | Headline CPI YoY |
| `BPS.CPI.HEADLINE.MOM.ID` | M | BPS derived | Headline CPI MoM |
| `BPS.CPI.CORE.YOY.ID` | M | BPS IHK Inti | BPS official core measure |
| `BPS.CPI.VOLATILE.YOY.ID` | M | BPS IHK | Volatile food component |
| `BPS.CPI.ADMIN.YOY.ID` | M | BPS IHK | Administered prices component |
| `BPS.CPI.FOOD.YOY.ID` | M | BPS IHK | Food, beverage, tobacco group |
| `BPS.CPI.HOUSING.YOY.ID` | M | BPS IHK | Housing, water, electricity, fuel group |
| `BPS.CPI.CLOTHING.YOY.ID` | M | BPS IHK | Clothing & footwear group |
| `BPS.CPI.HEALTH.YOY.ID` | M | BPS IHK | Health group |
| `BPS.CPI.TRANSPORT.YOY.ID` | M | BPS IHK | Transportation group |
| `BPS.CPI.EDUCATION.YOY.ID` | M | BPS IHK | Education group |

### 3. External & FX

#### 3.1 Terms of Trade

| `imdr_code` (target) | Freq | Source | Notes |
|---|:---:|---|---|
| `BPS.TOT.NET_BARTER.LEVEL.ID` | M | BPS derived | Net barter ToT |
| `BPS.TOT.INCOME.LEVEL.ID` | M | BPS derived | Income ToT |

#### 3.2 Current Account

| `imdr_code` (target) | Freq | Source | Notes |
|---|:---:|---|---|
| `BI.BOP.CA.TOTAL.USD.ID` | Q | BI SEKI BoP | Current Account total |
| `BI.BOP.CA.GDP.ID` | Q | BI derived | CA % of GDP |
| `BI.BOP.SERV.BAL.USD.ID` | Q | BI SEKI BoP | Services balance |
| `BI.BOP.PRIM_INCOME.USD.ID` | Q | BI SEKI BoP | Primary income |
| `BI.BOP.SEC_INCOME.USD.ID` | Q | BI SEKI BoP | Secondary income |

#### 3.3 Capital / Financial Account

| `imdr_code` (target) | Freq | Source | Notes |
|---|:---:|---|---|
| `BI.BOP.FA.TOTAL.USD.ID` | Q | BI SEKI BoP | Financial account total |
| `BI.BOP.DI.NET.USD.ID` | Q | BI SEKI BoP | Direct investment net |
| `BI.BOP.PI_EQ.NET.USD.ID` | Q | BI SEKI BoP | Portfolio equity net |
| `BI.BOP.PI_DEBT.NET.USD.ID` | Q | BI SEKI BoP | Portfolio debt net |
| `BI.BOP.OI.NET.USD.ID` | Q | BI SEKI BoP | Other investment net |
| `BI.BOP.RESERVES.DELTA.USD.ID` | Q | BI SEKI BoP | Reserve assets change |
| `BI.BOP.ERR_OM.USD.ID` | Q | BI SEKI BoP | Errors & omissions |
| `BI.IIP.NET.USD.ID` | Q | BI SEKI IIP | Net IIP |
| `BI.SULNI.TOTAL.USD.ID` | M | BI SULNI | External debt total |
| `BI.SULNI.PUBLIC.USD.ID` | M | BI SULNI | Public external debt |
| `BI.SULNI.PRIVATE.USD.ID` | M | BI SULNI | Private external debt |

#### 3.4 FX / REER

| `imdr_code` (target) | Freq | Source | Notes |
|---|:---:|---|---|
| `BIS.NEER.BROAD.LEVEL.ID` | M | BIS | Broad NEER |
| `BIS.REER.BROAD.LEVEL.ID` | M | BIS | Broad REER (competitiveness gauge) |
| `BI.RESERVES.TOTAL.USD.ID` | M | BI press release | FX reserves total |
| `BI.RESERVES.INTERVENTION.USD.ID` | M | derived | Intervention proxy |

### 4. Policy Transmission

#### 4.1 Demand Transmission

| `imdr_code` (target) | Freq | Source | Notes |
|---|:---:|---|---|
| `BI.SBP.LEND_STANCE.LEVEL.ID` | Q | BI SBP | Bank lending stance (overall) |
| `BI.SBP.LEND_HH.LEVEL.ID` | Q | BI SBP | Lending stance — household |
| `BI.SBP.LEND_CORP.LEVEL.ID` | Q | BI SBP | Lending stance — corporate |
| `BI.LOANS.TOTAL.STOCK.ID` | M | BI SEKI | Total bank loans (stock) |
| `BI.LOANS.MORTGAGE.RATE.ID` | M | BI SEKI | Mortgage rate (new origination) |
| `BI.LOANS.CORP.RATE.ID` | M | BI SEKI | Corporate loan rate (new) |
| `BIS.CREDIT_GDP_GAP.ID` | Q | BIS F1.1 | Credit-to-GDP gap |

#### 4.2 Balance Sheets

| `imdr_code` (target) | Freq | Source | Notes |
|---|:---:|---|---|
| `BI.HH_DEBT.GDP.ID` | Q | derived | Household debt / GDP |
| `BIS.DSR.HH.ID` | Q | BIS DSR Household | HH debt service ratio |
| `BIS.DSR.PNFS.ID` | Q | BIS DSR Non-fin corp | Corp debt service ratio |
| `OJK.BANK.CAR.LEVEL.ID` | M | OJK SPI | Bank capital adequacy ratio |
| `OJK.BANK.NPL.LEVEL.ID` | M | OJK SPI | Bank NPL ratio |
| `OJK.BANK.ROA.LEVEL.ID` | M | OJK SPI | Bank ROA |
| `OJK.BANK.LDR.LEVEL.ID` | M | OJK SPI | Loan-to-deposit ratio |

#### 4.3 Financial Conditions

| `imdr_code` (target) | Freq | Source | Notes |
|---|:---:|---|---|
| `BI.POLICY.7DRR.LEVEL.ID` | EVENT | BI press release | BI 7-Day Reverse Repo Rate |
| `BI.RATES.JIBOR_ON.LEVEL.ID` | D | BI SEKI / IBPA | JIBOR overnight |
| `BI.RATES.JIBOR_3M.LEVEL.ID` | D | BI SEKI | JIBOR 3M |
| `BI.RATES.JIBOR_1Y.LEVEL.ID` | D | BI SEKI | JIBOR 1Y |
| `IBPA.YIELD.GOVT.1Y.LEVEL.ID` | D | IBPA | 1Y INDOGB yield |
| `IBPA.YIELD.GOVT.5Y.LEVEL.ID` | D | IBPA | 5Y INDOGB yield |
| `IBPA.YIELD.GOVT.10Y.LEVEL.ID` | D | IBPA | 10Y INDOGB yield |
| `IBPA.YIELD.GOVT.10Y_2Y.SPREAD.ID` | D | derived | 10Y-2Y term spread |
| `BI.LEND_RATE.HH.LEVEL.ID` | M | BI SEKI | Bank lending rate — household |
| `BI.LEND_RATE.CORP.LEVEL.ID` | M | BI SEKI | Bank lending rate — corporate |
| `BI.DEPOSIT_RATE.LEVEL.ID` | M | BI SEKI | Bank deposit rate |

#### 4.4 Policy Reaction

| `imdr_code` (target) | Freq | Source | Notes |
|---|:---:|---|---|
| `BI.POLICY.7DRR.LEVEL.ID` | EVENT | BI press release | Cross-ref 4.3 |
| `BI.POLICY.DF.LEVEL.ID` | EVENT | BI press release | Deposit Facility rate |
| `BI.POLICY.LF.LEVEL.ID` | EVENT | BI press release | Lending Facility rate |
| `BI.RR.GWM.LEVEL.ID` | EVENT | BI press release | Reserve requirement (Giro Wajib Minimum) |
| `BI.M1.LEVEL.ID` | M | BI SEKI | M1 narrow money |
| `BI.M2.LEVEL.ID` | M | BI SEKI | M2 broad money |
| `BI.CURRENCY.CIRC.LEVEL.ID` | M | BI SEKI | Currency in circulation |
| `BI.BS.TOTAL.LEVEL.ID` | M | BI SEKI | BI balance sheet total |

---

## Naming notes

- Codes follow the Korea-established convention: `{VENDOR}.{CATEGORY}.{SUB}.{FREQ_OR_TRANSFORM}.{COUNTRY}`.
- `BPS` for Badan Pusat Statistik publications (CPI, GDP, labour, trade, retail, industrial).
- `BI` for Bank Indonesia publications (BoP, monetary, banking, rates, surveys, reserves).
- `MOF` for Kementerian Keuangan APBN data.
- `DJPPR` for Direktorat Jenderal Pengelolaan Pembiayaan dan Risiko (debt + SBN auctions).
- `OJK` for Otoritas Jasa Keuangan (banking sector statistics).
- `IBPA` for Indonesia Bond Pricing Agency (govt + corp bond yields).
- `BIS` / `BPS` collision: `BPS` is the Indonesian statistical office; `BIS` is the Bank for International Settlements. We use the 2-3 char vendor token unambiguously.

When fetchers ship, this list will be reconciled against `econ.dim_indicator` reality (see the Korea-pattern note: shipped `imdr_code` may differ from these placeholders if the BPS dataset structure dictates a cleaner shape).

## Cross-refs

- [`indonesia_indicator_inventory.md`](indonesia_indicator_inventory.md) — 4×4 tracker.
- [`id_coverage_plan.md`](id_coverage_plan.md) — concept → vendor-table mapping.
- [`index.md`](index.md) — landing page + BPS registration.
- [`../korea/kr_indicator_targets.md`](../korea/kr_indicator_targets.md) — Korea analogue (worked example).
