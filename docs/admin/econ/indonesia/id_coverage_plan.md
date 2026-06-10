# Indonesia (ID) — coverage plan (BPS / BI / MoF / DJPPR)

Last updated: 2026-06-10

Maps every Indonesia (ID) cell of the
[macro_economy_wiring_map.md §7.17](../macro_economy_wiring_map.md#717-indonesia-id)
to specific vendor identifiers per source agency.

This is the **plan** for filling `econ.dim_indicator` Indonesia rows — as of
2026-06-10 there are **308 indicators × 114,106 observations** in
`econ.fact_indicator` (BPS 82 + BI 184 + BIS 6 + DJPPR 36). Wired into
`scripts/imdr_monthly.py:PIPELINES` 2026-06-09 and `scripts/imdr_daily.py:PIPELINES`
2026-06-09/10 (see [indonesia_prod_pipeline.md](indonesia_prod_pipeline.md)).

**Critical gotcha — read before adding new BPS fetchers**: the national-rollup
`vervar_id` is NOT stable across base-year revisions. CPI pre-2024 series use
`vervar_id=9999` (INDONESIA); the 2024+ 150-kab/kota CPI series renumbered the
geographic axis and uses `vervar_id=151`. Always auto-detect by
`vervar_label == "INDONESIA"` — never hard-code. See
[`bps_api_reference.md`](bps_api_reference.md#other-gotchas-observed) and
[[feedback-bps-data-endpoint-gotchas]] for full context.

## Status legend

| Marker | Meaning |
|---|---|
| ✅ **confirmed** | Smoke-tested — endpoint returned rows for the candidate identifier |
| ⚠ **candidate** | Documented in BPS/BI portals; not yet probed against API |
| ❓ **unknown** | Wiring-map concept exists in ID statistics, but the right dataset hasn't been identified — needs catalogue browse |
| ❌ **vendor-absent** | Confirmed absent (e.g. BPS doesn't publish corporate ratios); fallback path required |

## Vendor cascade for ID

Per the [onboarding playbook](../onboarding_new_country.md#step-2--resolve-each--via-the-vendor-cascade) Tier table:

| Tier | Source | Coverage |
|---|---|---|
| **T1** | Bank Indonesia (BI) — `bi.go.id/en/statistik/seki/` | BoP, IIP, FX reserves, money & banking, policy rate, banking survey, financial stability |
| **T2** | BPS — `webapi.bps.go.id` (REST JSON) + `bps.go.id` browse | CPI, GDP, labour (Sakernas), customs trade, retail (penjualan eceran), industrial production (IBS) |
| **T3** | Kementerian Keuangan (MoF) — `data-apbn.kemenkeu.go.id` | APBN budget, revenue, spending |
| **T3** | DJPPR — `djppr.kemenkeu.go.id` | SBN/SUN/SBSN issuance, auctions |
| **T4** | FRED OECD mirror | Headline subset (CPI, IP, policy rate, reserves) |
| **T4** | BIS | Effective exchange rates (REER/NEER), credit-to-GDP gap |
| **T6** | OJK — `ojk.go.id` | Bank NPL, banking sector aggregates (mostly PDF) |

When a series is published by both BI and BPS (notably CPI from BPS publication + BI's reissue in SEKI), prefer **BPS** — it's the original publisher.

---

## 1. Growth Engine

### 1.1 Private Demand (consumption, retail, household credit)

| Concept | Vendor | Dataset / table | Cadence | Status |
|---|:---:|---|:---:|:---:|
| Retail sales index (penjualan eceran) | BI | SK / SEKI | M | ⚠ |
| Retail sales by segment | BI | SEKI | M | ⚠ |
| Consumer Tendency Index (ITK) | BPS | Survei Tendensi Konsumen | Q | ⚠ |
| Consumer Confidence Index (IKK) | BI | SK — Survei Konsumen | M | ⚠ |
| Household credit aggregate | BI | SEKI Tabel 2.x | M | ⚠ |
| Household loans flow | BI | SEKI | M | ⚠ |
| Auto sales (units) | GAIKINDO (industry assoc., not gov) | — | M | ❓ |

### 1.2 Fiscal Demand (govt spending, taxes, deficit)

| Concept | Vendor | Dataset / table | Cadence | Status |
|---|:---:|---|:---:|:---:|
| Central govt revenue | MoF | APBN realisasi | M (A budget vs realisasi) | ⚠ |
| Central govt expenditure | MoF | APBN realisasi | M | ⚠ |
| Central govt balance | MoF | APBN | A | ⚠ |
| Direct + indirect tax revenue | MoF / DJP | Tax dashboard | M | ⚠ |
| Government final consumption (GDP component) | BPS | GDP expenditure decomposition | Q | ⚠ |
| Government investment / GFCF | BPS | GDP expenditure decomposition | Q | ⚠ |
| Government debt / GDP | DJPPR | Debt profile | M | ⚠ |
| SBN issuance schedule | DJPPR | Auction calendar | EVENT | ⚠ |

### 1.3 External Demand (trade)

| Concept | Vendor | Dataset / table | Cadence | Status |
|---|:---:|---|:---:|:---:|
| Goods exports (BoP basis, USD) | BI | SEKI BoP | M | ⚠ |
| Goods imports (BoP basis, USD) | BI | SEKI BoP | M | ⚠ |
| Goods trade balance (BoP) | BI | SEKI BoP | M | ⚠ |
| Goods exports (customs basis) | BPS | sub=8 `var=196` vervar=9999 | M | ✅ Phase C ([fetch_trade.py](../../../playground/econ/bps/fetch_trade.py)) |
| Goods imports (customs basis) | BPS | sub=8 `var=497` vervar=9999 | M | ✅ Phase C |
| Exports — Oil&Gas vs Non-Oil&Gas | BPS | sub=8 `var=203` vervar=1/2 turvar=439 | A | ✅ Phase C |
| Imports — Oil&Gas vs Non-Oil&Gas | BPS | sub=8 `var=203` vervar=1/2 turvar=440 | A | ✅ Phase C |
| Export value index | BPS | Indeks Unit Nilai Ekspor | M | ⚠ pending Phase C2 |
| Export volume index | BPS | Indeks Volume Ekspor | M | ⚠ pending Phase C2 |
| Import value index | BPS | Indeks Unit Nilai Impor | M | ⚠ pending Phase C2 |
| Import volume index | BPS | Indeks Volume Impor | M | ⚠ pending Phase C2 |
| Exports by partner country | BPS | Customs trade by country | M | ⚠ |
| Exports by product (HS chapter) | BPS | Customs trade by product | M | ⚠ |

### 1.4 Macro Core (GDP, IIP, labour, sentiment)

| Concept | Vendor | Dataset / table | Cadence | Status |
|---|:---:|---|:---:|:---:|
| Real GDP (YoY) | BPS | sub=11 `var=104` vervar=99003 turvar=5 | Q | ✅ Phase C ([fetch_gdp.py](../../../playground/econ/bps/fetch_gdp.py)) |
| Real GDP (QoQ chained) | BPS | sub=11 `var=104` vervar=99003 turvar=4 | Q | ✅ Phase C |
| Real GDP level (constant 2010) | BPS | sub=11 `var=65` vervar=99003 turvar=237 | Q | ✅ Phase C |
| Nominal GDP level | BPS | sub=11 `var=65` vervar=99003 turvar=238 | Q | ✅ Phase C |
| GDP deflator YoY (supply-side) | BPS | sub=11 `var=105` vervar=99003 turvar=236 | Q | ✅ Phase C |
| GDP YoY (expenditure side) | BPS | sub=169 `var=108` vervar=800 turvar=5 | Q | ✅ Phase C |
| GDP deflator YoY (expenditure) | BPS | sub=169 `var=109` vervar=800 turvar=236 | Q | ✅ Phase C |
| GDP by sector (mfg, services, agri, mining, construction) | BPS | sub=11 `var=104` vervar=11000-18000 | Q | ⚠ pending Phase C2 (sectoral decomp) |
| GDP by expenditure (C, I, G, X, M) | BPS | sub=169 `var=108` vervar=100-700 | Q | ⚠ pending Phase C2 (expenditure decomp) |
| Industrial Production Index (IBS — Mfg) | BPS | Indeks Produksi IBS | Q | ⚠ pending Phase C2 |
| Industrial Production Index (IMK — Small Mfg) | BPS | Indeks Produksi IMK | Q | ⚠ pending Phase C2 |
| Mfg Capacity Utilisation | BI | SK — Business Survey | Q | ⚠ |
| Business Sentiment (Survei Kegiatan Dunia Usaha) | BI | SKDU | Q | ⚠ |
| Manufacturing PMI | S&P Global | paid | M | ❌ (use SKDU equiv) |
| Unemployment rate | BPS | sub=6 `var=543` vervar=9999 (Sakernas) | Feb + Aug | ✅ Phase C ([fetch_labour.py](../../../playground/econ/bps/fetch_labour.py)) |
| Employment level | BPS | Sakernas — pending Phase C2 | Aug + Feb | ⚠ |
| Labour force participation rate | BPS | Sakernas — pending Phase C2 | Aug + Feb | ⚠ |

---

## 2. Inflation Engine

### 2.1 Input Costs

| Concept | Vendor | Dataset / table | Cadence | Status |
|---|:---:|---|:---:|:---:|
| Import price index (IDR basis) | BPS | Indeks Unit Nilai Impor — `var` TBD | M | ⚠ |
| Import price index (USD basis) | BPS | Indeks Unit Nilai Impor (USD denomination) | M | ⚠ |
| Energy supply prices (electricity, gas, fuel) | BPS | CPI energy components | M | ⚠ |
| Commodity import volumes (oil, gas, food) | BPS | Customs trade by product | M | ⚠ |
| Supply-chain pressure index (NY Fed GSCPI) | FRED | NYFEDGSCPI | M | ❓ (cross-country, not ID-specific) |
| FX pass-through gauge | derived | IDR move × import-price differential | M | ❓ |

### 2.2 Producer Prices (PPI / WPI)

| Concept | Vendor | Dataset / table | Cadence | Status |
|---|:---:|---|:---:|:---:|
| PPI level (Indeks Umum, 2010=100) | BPS | sub=36 `var=369` vervar=45 | Q | ✅ Phase C ([fetch_ppi.py](../../../playground/econ/bps/fetch_ppi.py)) — stalls 2023-Q4 |
| PPI QoQ growth | BPS | sub=36 `var=378` vervar=45 | Q | ✅ Phase C — stalls 2023-Q4 |
| PPI YoY growth | BPS | sub=36 `var=380` vervar=45 | Q | ✅ Phase C — stalls 2023-Q4 |
| WPI level (Indeks Umum) | BPS | sub=20 `var=24` vervar=90 | M | ✅ Phase C — stalls 2019-11 |
| Current-base PPI/WPI (post-rebase var_ids) | BPS | TBD | Q/M | ⚠ pending Phase C2 probe (legacy series stopped publishing on the listed var_ids) |
| PPI by sector | BPS | sub=36 `var=369` vervar=1-44 | Q | ⚠ pending Phase C2 (sectoral decomp) |
| Export price index | BPS | Indeks Unit Nilai Ekspor | M | ⚠ pending Phase C2 |
| Wholesale margins / inventory-to-sales | — | not published by Indonesia | — | ❌ |

### 2.3 Domestic Costs (wages, rents, expectations)

| Concept | Vendor | Dataset / table | Cadence | Status |
|---|:---:|---|:---:|:---:|
| Provincial minimum wage (avg) | BPS | sub=19 `var=220` vervar=9999 | A | ✅ Phase C ([fetch_labour.py](../../../playground/econ/bps/fetch_labour.py)) — stalls 2020 |
| Average wages (formal sector) | BPS | Sakernas — Upah | Aug + Feb | ⚠ pending Phase C2 (full Sakernas) |
| Wages by sector | BPS | Sakernas — sektor lapangan usaha | Aug + Feb | ⚠ pending Phase C2 |
| Current minimum wage (post-2020 var_id) | BPS | TBD | A | ⚠ pending Phase C2 probe |
| Mfg capacity utilisation | BI | SKDU | Q | ⚠ (dup of 1.4) |
| Inflation expectations | BI | Consumer Survey (SK) | M | ⚠ |
| Rent component of CPI | BPS | CPI sub-index (Perumahan) | M | ⚠ |

### 2.4 CPI Pressure

**Base-year revision note**: BPS rebased the headline CPI index in 2020 (var=2 → 1709) and again in 2024 (1709 → 2245). The 2024+ revision **renumbered the geographic vervar axis** — INDONESIA is `vervar_id=151` in var=2245 vs `9999` in older vars. The MoM rate (var=1) is continuous across all rebases.

| Concept | Vendor | Dataset / table | Cadence | Status |
|---|:---:|---|:---:|:---:|
| Headline CPI MoM (continuous 1979→) | BPS | sub=3 `var=1` vervar=9999 | M | ✅ Phase C ([fetch_cpi.py](../../../playground/econ/bps/fetch_cpi.py)) |
| CPI level — pre-2020 series | BPS | sub=3 `var=2` vervar=9999 | M | ✅ Phase C (1979-2019) |
| CPI level — 90-city 2018=100 (2020-23) | BPS | sub=3 `var=1709` vervar=9999 | M | ✅ Phase C |
| CPI level — 150-kab/kota 2022=100 (2024+) | BPS | sub=3 `var=2245` vervar=151 | M | ✅ Phase C |
| Headline CPI YoY | derived | from level series in analytics | M | ⚠ derived downstream |
| Core CPI (BPS core measure) | BPS | inti / core publication | M | ⚠ pending Phase C2 |
| CPI by major group (7+ groups) | BPS | sub=3 `var=1890+` (per-group vars) | M | ⚠ pending Phase C2 (CPI groups) |
| Volatile food / Administered prices CPI | BPS | sub=3 — sub-aggregates | M | ⚠ pending Phase C2 |

---

## 3. External & FX

### 3.1 Terms of Trade

| Concept | Vendor | Dataset / table | Cadence | Status |
|---|:---:|---|:---:|:---:|
| Net barter ToT | BPS | derived: Pₓ / Pₘ from unit-value indices | M | ⚠ |
| Income ToT | BPS | derived: NBToT × volume | M | ⚠ |
| Export price index (own) | BPS | Indeks Unit Nilai Ekspor (cross-ref 2.2) | M | ⚠ |
| Import price index | BPS | Indeks Unit Nilai Impor (cross-ref 2.1) | M | ⚠ |

### 3.2 Current Account

| Concept | Vendor | Dataset / table | Cadence | Status |
|---|:---:|---|:---:|:---:|
| Current Account total | BI | SEKI BoP — `Neraca Pembayaran Indonesia` | Q | ⚠ |
| Current Account % of GDP | BI / BPS derived | NPI / nominal GDP | Q | ⚠ |
| Goods balance | BI | SEKI BoP | Q | ⚠ |
| Services balance | BI | SEKI BoP | Q | ⚠ |
| Primary income balance | BI | SEKI BoP | Q | ⚠ |
| Secondary income (transfers, remittances) | BI | SEKI BoP | Q | ⚠ |
| Services sub-cuts (travel, transport, etc.) | BI | SEKI BoP detail | Q | ⚠ |
| Primary income sub-cuts | BI | SEKI BoP detail | Q | ⚠ |

### 3.3 Capital + Financial Account

| Concept | Vendor | Dataset / table | Cadence | Status |
|---|:---:|---|:---:|:---:|
| Financial Account total | BI | SEKI BoP | Q | ⚠ |
| Direct Investment (net + assets + liabilities) | BI | SEKI BoP | Q | ⚠ |
| Portfolio Investment Equity (net + a + l) | BI | SEKI BoP | Q | ⚠ |
| Portfolio Investment Debt (net + a + l) | BI | SEKI BoP | Q | ⚠ |
| Other Investment (net + a + l) | BI | SEKI BoP | Q | ⚠ |
| Reserve Assets, transactional change | BI | SEKI BoP | Q + M | ⚠ |
| Errors and Omissions | BI | SEKI BoP | Q | ⚠ |
| IIP — net | BI | SEKI IIP | Q | ⚠ |
| External debt (short + long) | BI | SULNI (Statistik Utang Luar Negeri Indonesia) | M | ⚠ |

### 3.4 FX / REER

| Concept | Vendor | Dataset / table | Cadence | Status |
|---|:---:|---|:---:|:---:|
| Spot IDR vs USD | (FX domain — Citi `FX.SPOT.USD.IDR.CITI`) | — | D | ✅ via market data |
| NDF curve (IDR is restricted) | (FX domain) | — | D | ✅ via market data |
| FX implied vol | (FX domain — Citi) | — | D | ✅ via market data |
| BIS NEER broad | BIS | `WS_EER` key=M.N.B.ID | M | ✅ Phase D4 ([fetch_indonesia.py](../../../playground/econ/bis/fetch_indonesia.py)) |
| BIS REER broad | BIS | `WS_EER` key=M.R.B.ID | M | ✅ Phase D4 |
| FX reserves total + composition | BI | SEKI V.9 | M | ✅ Phase D ([fetch_fx_reserves.py](../../../playground/econ/bi/fetch_fx_reserves.py)) |
| CB FX intervention proxy | BI | reserve change minus valuation (derived) | M | ⚠ derived in analytics |

---

## 4. Policy Transmission

### 4.1 Demand Transmission (lending standards, credit channel)

| Concept | Vendor | Dataset / table | Cadence | Status |
|---|:---:|---|:---:|:---:|
| Bank Lending Standards Survey (SBP) | BI | Survei Perbankan | Q | ⚠ |
| Loan demand survey | BI | Survei Perbankan | Q | ⚠ |
| Total bank loans (stock) | BI | SEKI 2.x | M | ⚠ |
| Household loans (stock + flow) | BI | SEKI HH credit | M | ⚠ |
| Mortgage rates (new origination) | BI | SEKI suku bunga KPR | M | ⚠ |
| Loan rates (new + outstanding) | BI | SEKI suku bunga kredit | M | ⚠ |
| Loan-to-deposit ratio (LDR) | BI / OJK | banking aggregates | M | ⚠ |
| Housing transactions | BI | SHPR Residential Property Survey | Q | ⚠ |
| BIS credit-to-GDP gap | BIS | F1.1 table | Q | ⚠ |

### 4.2 Balance Sheets (sectoral leverage, NPL)

| Concept | Vendor | Dataset / table | Cadence | Status |
|---|:---:|---|:---:|:---:|
| Household DSR (BIS) | BIS | `WS_DSR` key=Q.ID.H | Q | ❌ BIS doesn't publish HH-only for ID (EM); use PNFS aggregate |
| Private NFS DSR (aggregate) | BIS | `WS_DSR` key=Q.ID.P | Q | ✅ Phase D4 ([fetch_indonesia.py](../../../playground/econ/bis/fetch_indonesia.py)) |
| Credit-to-GDP ratio | BIS | `WS_CREDIT_GAP` key=Q.ID.P.A.A | Q | ✅ Phase D4 |
| Credit-to-GDP gap (HP-filter) | BIS | `WS_CREDIT_GAP` key=Q.ID.P.A.C | Q | ✅ Phase D4 |
| Commercial bank deposits + claims composition | BI | SEKI I.3 — 8 series | M | ✅ Phase D3 ([fetch_bank_bs.py](../../../playground/econ/bi/fetch_bank_bs.py)) |
| **SBN outstanding by holder (bank-type decomp)** | **BI** | **SEKI IV.4 TABEL4_4 — 19 series (4 totals + 8 ON + 7 SPN)** | **M** | **✅ Phase I 2026-06-10 (`bi_sbn_position`); enriches existing BI SBN aggregate (IV.4 totals already in `bi_sbn`) with bank-type investor cut; complements DJPPR investor-category view** |
| External debt (govt + private split) | BI | SEKI VI.1 — 8 series | Q | ✅ Phase D2 ([fetch_sulni.py](../../../playground/econ/bi/fetch_sulni.py)) |
| Corporate financial ratios | — | sparse for ID; OJK has limited published | A | ❌ deferred |
| Bank Tier-1 / CET1 ratio | OJK | SPI (Statistik Perbankan Indonesia) | M | ⚠ pending OJK PDF parsing |
| Bank CAR / NPL / ROA / ROE | OJK | SPI | M | ⚠ pending OJK PDF parsing |
| Government debt / GDP | DJPPR | Debt profile | M | ⚠ pending DJPPR scraping |
| Financial Stability composite | BI | Kajian Stabilitas Keuangan (semi-annual) | EVENT | ⚠ pending PDF parse |

### 4.3 Financial Conditions (rates, curve, spreads)

| Concept | Vendor | Dataset / table | Cadence | Status |
|---|:---:|---|:---:|:---:|
| Policy rate (BI 7-Day Reverse Repo Rate) | BIS | `WS_CBPOL` key=D.ID | D / EVENT | ✅ Phase D4 ([fetch_indonesia.py](../../../playground/econ/bis/fetch_indonesia.py)) |
| BI Deposit Facility / Lending Facility rate | BI | SEKI I.25.A/I.25.B | M | ✅ Phase D6 (`bi_bank_rates`) |
| PUAB overnight / INDONIA | BI | SEKI I.26 | M | ✅ Phase D6 (`bi_bank_rates`) |
| INDONIA compounded 30d / 90d | BI | SEKI I.28 | M | ✅ Phase D6 (`bi_bank_rates`) |
| Bank lending rates (Bank Umum 3 loan types) | BI | SEKI I.26 lending | M | ✅ Phase D6 (`bi_bank_rates`) |
| Bank deposit rates (3 tenors) | BI | SEKI I.28 deposit | M | ✅ Phase D6 (`bi_bank_rates`) |
| **SRBI auction yield 6M / 9M / 12M** | BI | Auction result pages (Hasil Lelang SRBI) | EVENT ~2×/wk | ✅ Phase H 2026-06-10 (`bi_srbi`, `imdr_daily.py`) |
| JIBOR / IndONIA curve (full tenors) | BI | SEKI / IBPA | D | ⚠ — ON + 30d/90d live; full tenor curve deferred |
| 1Y / 3Y / 5Y / 10Y govt bond yields (INDOGB) | IBPA / BI | IBPA daily curve | D | ⚠ |
| Term spread (10Y – 2Y) | derived | from INDOGB | D | ⚠ |
| Sovereign CDS 5Y (USD) | (rates / FX domain — market data) | — | D | ✅ via market data |
| Equity index level (IHSG / JCI) | (equity domain — Citi `EQUITY.EQUITY_INDEX.JCI.LEVEL.REUTERS`) | — | D | ✅ via market data |

### 4.4 Policy Reaction

| Concept | Vendor | Dataset / table | Cadence | Status |
|---|:---:|---|:---:|:---:|
| Policy rate level + changes | BI | press release + SEKI | EVENT | ⚠ |
| Deposit Facility / Lending Facility rate | BI | press release | EVENT | ⚠ |
| Reserve requirement (GWM) | BI | press release | EVENT | ⚠ |
| M1 (uang kartal + giral) | BI | SEKI uang beredar | M | ⚠ |
| M2 (broad money) | BI | SEKI uang beredar | M | ⚠ |
| Currency in circulation | BI | SEKI | M | ⚠ |
| BI balance sheet total | BI | SEKI BI assets/liabilities | M | ⚠ |
| FX reserves (cross-ref 3.4) | BI | SEKI | M | ⚠ |
| Macropru — LTV ceiling | BI | press release | EVENT | ⚠ |
| Macropru — MIR/RIM | BI | press release | EVENT | ⚠ |
| Macropru — Countercyclical Capital Buffer | OJK | press release | EVENT | ⚠ |
| Macroprudential event log | BI / OJK | derived from press releases | EVENT | ⚠ |

---

## Phase C status (2026-06-08)

| Cell | Phase C coverage | Indicators shipped | Remaining gap |
|---|---|:---:|---|
| 1.3 External Demand | Customs exports/imports total + Migas/Non-Migas decomp | 6 | BoP basis (BI), trade indices (BPS C2), partner breakdown |
| 1.4 Macro Core | GDP supply + demand sides at total, unemployment | 9 | Sectoral GDP decomp (C2), IBS/IMK, full Sakernas |
| 2.2 Producer Prices | PPI level + QoQ + YoY + WPI level | 4 | Current-base var_ids (post-2024 rebase) |
| 2.3 Domestic Costs | Provincial min wage | 1 | Full Sakernas wages (C2), inflation expectations (BI) |
| 2.4 CPI Pressure | Headline MoM + 3 base-year-spliceable level series | 4 | YoY (derived), core, group decomp, volatile/administered (C2) |

All 16 cells covered as of 2026-06-09. 13 of 16 are full ✅; 3 remain ⚠ partial (2.1, 3.1, 3.4). Wired into `scripts/imdr_monthly.py:PIPELINES` 2026-06-09 — Phase G complete.

## Cross-refs

- [`indonesia_indicator_inventory.md`](indonesia_indicator_inventory.md) — 4×4 tracker.
- [`id_indicator_targets.md`](id_indicator_targets.md) — concrete `imdr_code` shopping list.
- [`index.md`](index.md) — landing page + access paths + BPS registration.
- [`../onboarding_new_country.md`](../onboarding_new_country.md) — 5-step workflow.
- [`../korea/kosis_kr_coverage_plan.md`](../korea/kosis_kr_coverage_plan.md) — Korea analogue (worked example).
