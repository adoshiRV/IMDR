# Japan — Indicator Inventory (Track A)

Last updated: 2026-06-22

Forked from [`../country_econ_blueprint.md`](../country_econ_blueprint.md) §1-4. Tracks what's covered per wiring-map cell and which vendor/table supplies it.

**Status: discovery — 17 fetchers built, ~186 indicators / ~70,800 obs in sample parquet (no DB load yet).** All 16 wiring-map cells covered (15 ✅ full, 1 ⚠ partial — only 1.2 fiscal funding-side). Eight sources across 5 mechanisms (the 8th = BIS for cell 4.2):
- **e-Stat API** (`api.e-stat.go.jp` REST 3.0, appId) — CPI (6), Labour (8), Economy Watchers (8), METI IIP (5, 2020-base), MHLW wages (6, file-catalog CSV).
- **Cabinet Office ESRI QE** (`esri.cao.go.jp`, no auth) — GDP (57, real/nominal SA + QoQ, expenditure decomposition, 1994→2026 live).
- **BoJ flat-file zips** (`stat-search.boj.or.jp/info/*.zip`) — BoP (14, BPM6 identity verified), CGPI/PPI (10), SPPI (8), IIP/IIP-position (5, identity verified), TANKAN (10: biz-conditions + lending-attitude + financial-position, recent rounds).
- **BoJ mtshtml direct CSV** (`stat-search.boj.or.jp/ssi/mtshtml/csv/`, bypasses famecgi2) — rates (2), money (8: monetary base + M1/M2/M3/L), FX (3: USD/JPY + NEER/REER). Deep history (call rate 1998→, monetary base 1980→).
- **MOF customs time-series CSV** (`customs.go.jp/toukei/suii/`, Shift-JIS) — trade (17: exports/imports/balance × world/Asia/NA/W.Europe/EU/ASEAN/US/China, 1979→).
- **METI site XLSX** (`meti.go.jp/statistics/tyo/syoudou/`) — retail (14: total/wholesale/retail/dept/super/CVS × value+YoY, 1980→).

Cross-cell identities verified: BoP `CA+Capital+E&O=Financial account`; IIP `assets−liabilities=net`; labour `employed+unemployed=labour force`.
Deferred (stale/fragmented e-Stat vintages): **wages** (Monthly Labour `0003138108` frozen 2015 — needs post-2018-rebenchmark table), **construction** (`0004000400` ends 2024-12 + is buildings not dwelling-units — needs MLIT direct), **Flow of Funds** (BIS credit-to-GDP covers cell 4.2).

Marker key: ✅ route proven + fetcher built · 🔧 route confirmed, fetcher pending · ⚠ partial (FRED mirror only) · ❓ source unconfirmed · ❌ not available.

## 4×4 coverage tracker

| Cell | Status | Headline indicator (source) | Notes |
|---|:---:|---|---|
| 1.1 Private Demand    | ✅ | Economy Watchers DI (e-Stat) + retail (METI XLSX) | EW SA DI **built**; **retail built** (`meti/fetch_retail.py` — total/wholesale/retail/dept/super/CVS, ¥13.3tn Apr-2026, identities hold; e-Stat 商業動態 was frozen at Dec-2020 → METI site XLSX is the live source) |
| 1.2 Fiscal Demand     | ⚠ | ESRI QE gov consumption + public investment | demand-side **built** (gov consumption + public investment via ESRI QE). Funding-side (tax revenue / balance / debt) **not on e-Stat** (only Meiji-era + local-gov tables) → MOF site (annual, PDF/Excel) or FRED gov-debt mirror; deferred, low-priority annual |
| 1.3 External Demand   | ✅ | BoJ BoP + **MOF customs trade** | BoP goods exports/imports **built**; **MOF monthly trade built** (`mof/fetch_trade.py` — exports ¥10.5tn / imports ¥10.2tn / balance, world+regions+US/China, 1979→, Apr-2026; MOF customs time-series CSV, not e-Stat) |
| 1.4 Macro Core        | ✅ | **GDP — ESRI QE (live)** + Labour + IIP + TANKAN | GDP 57-series expenditure decomp; Labour rates+levels; **METI IIP built** (`meti/fetch_iip.py` — production/shipments/inventory/inv-ratio/capacity-util SA, 2020-base, prod 102.0 Mar-2026); TANKAN biz-conditions DI. e-Stat SNA stale (2007); FRED = backup |
| 2.1 Input Costs       | ✅ | BoJ CGPI import price (yen + contract-ccy) | **built** — FX-pass-through pair (`IMPORT_PRICE.YEN/CONTRACT_CCY`) |
| 2.2 Producer Prices   | ✅ | BoJ CGPI (`cgpi_m_en`) + SPPI (`sppi_m_en`) | **built** — PPI all+5 groups, SPPI all+7 groups |
| 2.3 Domestic Costs    | ✅ | **MHLW wages** + services CPI + TANKAN | **wages built** (`mhlw/fetch_wages.py` — total/scheduled/overtime cash earnings + nominal/real YoY, ¥318k +3.1%/+1.4% real Mar-2026, 1990→). e-Stat getStatsData frozen 2015 → live via e-Stat **file-catalog** (getDataCatalog CSV, Shift-JIS). Services CPI + TANKAN capacity also present |
| 2.4 CPI Pressure      | ✅ | e-Stat CPI 2020-base (`0003427113`) | **built** — headline `0001` / core `0161` / core-core `0178`, index+YoY, 1970→ |
| 3.1 Terms of Trade    | ✅ | BoJ CGPI export ÷ import price | **built** — export+import price indices (yen + contract-ccy) emitted; ToT derivable |
| 3.2 Current Account   | ✅ | BoJ BoP CA net (`BPBP6JYNCB`) | **built** — CA / G&S / goods / services / primary-income net |
| 3.3 Capital/Fin Acct  | ✅ | BoJ BoP financial account + IIP | **built** — BoP FA (DI/PI/OI/reserves/E&O) + IIP (`qiip_q_en`: net/assets/liabs/reserves/external-debt, identity verified) |
| 3.4 FX / REER         | ✅ | BoJ FX `FM08` (USD/JPY) + EER `FM09` (NEER/REER) | **built** via mtshtml `fetch_fx.py`; USD/JPY daily 1998→, NEER/REER monthly 1980→; BIS REER available as cross-check |
| 4.1 Demand Trans      | ✅ | **TANKAN lending-attitude + financial-position DI** | **built** via `boj/fetch_tankan.py` items 612/609 (lending attitude of banks +15 mfg, financial position +11, Q1-2026). The pure BoJ SLOOS survey (`LA05`) is **PDF-only** (loos*.pdf) / famecgi2 — TANKAN is the machine-readable equivalent |
| 4.2 Balance Sheets    | ✅ | **BIS credit-to-GDP gap + DSR** | **built** (`playground/econ/bis/fetch_japan.py` — DSR households/NFC/private + credit-to-GDP ratio 175% / gap, to 1964). BoJ Flow of Funds (`fof.zip`) deferred (BIS covers the headline) |
| 4.3 Fin Conditions    | ✅ | call rate `FM01` + USD/JPY; 10Y JGB `FRED.RATES.GOVT_10Y.JP` ⚠ | **built** via mtshtml `fetch_rates.py`/`fetch_fx.py`; JGB full curve via MOF CSV ❓ pending |
| 4.4 Policy Reaction   | ✅ | policy = call rate `FM01`; discount `IR01`; M1/M2/M3 `MD02`; monetary base `MD01` | **built** via mtshtml `fetch_rates.py` + `fetch_money.py`; monetary base to 1980, call rate to 1998 |

## Source routes

| Route | Auth | Covers | Mechanism | Status |
|---|---|---|---|---|
| **BoJ flat-file** | none | BoP, IIP, TANKAN, CGPI(PPI), SPPI, Flow of Funds, BIS-in-Japan | GET `stat-search.boj.or.jp/info/{name}.zip` → 1 CSV (wide or long layout) | ✅ proven (BoP) |
| **BoJ mtshtml direct CSV** | none | call/policy rate, discount rate, money stock, monetary base, FX, NEER/REER | plain GET `…/ssi/mtshtml/csv/{code}_{freq}_{n}_en.csv` — **bypasses famecgi2** | ✅ built (rates/money/fx) |
| **BoJ famecgi2 (fallback)** | none | residual categories absent from mtshtml: SLOOS `LA05`, FM02 money-mkt, MD07 reserves | `famecgi2` JS POST form | ❓ only if a residual series is needed |
| **e-Stat API** | appId (`IMDR_ECON_ESTAT_KEY`) | CPI ✅, Labour Force (rates+levels), Economy Watchers, wages, construction | REST 3.0 JSON `getStatsList`/`getMetaInfo`/`getStatsData`. **English API covers MIC+MOF+Cabinet only; search METI/MHLW/MLIT by Japanese name + ingest `lang=J`** | ✅ proven (CPI); 5 more tables verified |
| **Cabinet Office ESRI (QE)** | none | **live GDP** (real/nominal, SA, full expenditure decomp) | `esri.cao.go.jp/jp/sna/sokuhou/` → release page → `tables/{ritu\|gaku}-{j\|m}{k\|g}{ver}.csv` (Shift-JIS, wide). Auto-discover latest via top page | ✅ discovered + structure-confirmed |
| **FRED OECD mirror** | FRED key | Real GDP, IIP, unemployment, CPI-YoY, 10Y JGB | already in `playground/econ/fred/validate_and_seed.py` | ⚠ live (thin) — **backup only**; native sources supersede |
| **METI site XLSX** | none | retail (商業動態, live monthly) | `meti.go.jp/statistics/tyo/syoudou/result-2/` → `excel/*.xlsx` (per-format sheets; YoY published as 100-base ratio) | ✅ built (`meti/fetch_retail.py`) — e-Stat 商業動態 frozen at Dec-2020 |
| **METI IIP via e-Stat** | appId | industrial production (2020-base SA) | e-Stat `0004052177`-`231`; **time axis is a 7-digit METI item code, NOT `YYYY00mmMM`** — resolve via getMetaInfo | ✅ built (`meti/fetch_iip.py`) |
| **MHLW wages via e-Stat file-catalog** | appId | Monthly Labour cash earnings + index | `getDataCatalog` → `e-stat.go.jp/stat-search/file-download?statInfId={id}` CSV (Shift-JIS); getStatsData API frozen 2015 | ✅ built (`mhlw/fetch_wages.py`) — statInfId tied to release, re-query at promotion |
| **MOF customs time-series** | none | monthly trade value/balance (world+regions+partners) | `customs.go.jp/toukei/suii/html/data/{stem}.csv` (Shift-JIS, ¥thousand, 1979→) | ✅ built (`mof/fetch_trade.py`) — e-Stat MOF is commodity-detail only |
| **MOF JGB yields** | none | JGB benchmark curve | `mof.go.jp/.../interest_rate/` yearly CSV | ❓ unprobed (FRED 10Y live as backup) |
| **BIS** | none | credit-to-GDP gap + DSR (cell 4.2) | `playground/econ/bis/fetch_japan.py` (reuses `_bis_sdmx.py`, ref-area `JP`; REER/NEER/policy-rate omitted — BoJ native) | ✅ built (`fetch_japan.py`) |

## Build order (headline-first, per playbook)

1. ✅ CPI (e-Stat `0003427113`) · ✅ BoP (BoJ flat-file) — done
2. ✅ Policy/call rate + discount rate + money stock + monetary base + FX/NEER/REER (BoJ mtshtml) — **built**
3. 🔧 **GDP — Cabinet Office ESRI QE** (`ritu-jk`/`gaku-jk` CSVs) — live source, user-priority
4. 🔧 Labour — e-Stat rates (`0003005865`) + levels (`0003005798`)
5. 🔧 Economy Watchers DI — e-Stat (`0003348423`)
6. 🔧 Wages — e-Stat Monthly Labour (`0003138108`, total cash earnings)
7. 🔧 CGPI/PPI + SPPI (BoJ flat-file) · TANKAN sentiment (BoJ `co.zip`)
8. 🔧 Construction starts — e-Stat (`0004000400`)
9. ❓ Retail (METI 商業動態速報 direct) · IIP (METI direct / FRED) · trade monthly (MOF customs) — **source-agency probes, e-Stat versions stale/awkward**
10. ✅ BIS balance-sheet metrics (`bis/fetch_japan.py` — DSR + credit-to-GDP); Flow of Funds deferred

## Related
- [`index.md`](index.md) — country landing page
- [`_playground/boj.md`](_playground/boj.md) · [`_playground/estat.md`](_playground/estat.md) — per-vendor discovery notes
- [`../macro_economy_wiring_map.md`](../macro_economy_wiring_map.md) §7.4 — JP coverage grid
- [`../onboarding_new_country.md`](../onboarding_new_country.md) — playbook
