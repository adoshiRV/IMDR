# Japan — Indicator Inventory (Track A)

Last updated: 2026-07-10

Forked from [`../country_econ_blueprint.md`](../country_econ_blueprint.md) §1-4. Tracks what's covered per wiring-map cell and which vendor/table supplies it.

**Status: discovery — 20 fetchers built, ~225 indicators / ~70,900+ obs in sample parquet (no DB load yet).** All 16 wiring-map cells covered (15 ✅ full, 1 ⚠ partial — 1.2 fiscal funding-side partially addressed). Nine sources across 6 mechanisms (the 9th = BIS for cell 4.2; GPIF new 2026-07-10):
- **e-Stat API** (`api.e-stat.go.jp` REST 3.0, appId) — CPI (6), Labour (8), Economy Watchers (8), METI IIP (5, 2020-base), MHLW wages (6, file-catalog CSV).
- **Cabinet Office ESRI QE** (`esri.cao.go.jp`, no auth) — GDP (57, real/nominal SA + QoQ, expenditure decomposition, 1994→2026 live).
- **BoJ flat-file zips** (`stat-search.boj.or.jp/info/*.zip`) — BoP (14, BPM6 identity verified), CGPI/PPI (10), SPPI (8), IIP/IIP-position (5, identity verified), TANKAN (10: biz-conditions + lending-attitude + financial-position, recent rounds).
- **BoJ mtshtml direct CSV** (`stat-search.boj.or.jp/ssi/mtshtml/csv/`, bypasses famecgi2) — rates (2), money (8: monetary base + M1/M2/M3/L), FX (3: USD/JPY + NEER/REER). Deep history (call rate 1998→, monetary base 1980→).
- **MOF customs time-series CSV** (`customs.go.jp/toukei/suii/`, Shift-JIS) — trade (17: exports/imports/balance × world/Asia/NA/W.Europe/EU/ASEAN/US/China, 1979→).
- **MOF JGB debt-management PDFs** (`mof.go.jp/english/policy/jgbs/`, PyMuPDF) — JGB issuance by tenor (9 ind, ANNUAL, 2 FYs), JGB holder breakdown (19 ind, QUARTERLY, Mar-2026). NEW 2026-07-10.
- **METI site XLSX** (`meti.go.jp/statistics/tyo/syoudou/`) — retail (14: total/wholesale/retail/dept/super/CVS × value+YoY, 1980→). WAF fix applied 2026-07-10; IIP lags ~1Q vs confirmed METI site — see freshness notes below.
- **GPIF annual Excel files** (`gpif.go.jp/en/performance/past-performances.html`) — asset-allocation profile (11 ind, ANNUAL, Mar-2015→Mar-2024). NEW 2026-07-10.

Cross-cell identities verified: BoP `CA+Capital+E&O=Financial account`; IIP `assets−liabilities=net`; labour `employed+unemployed=labour force`.
Deferred (stale/fragmented e-Stat vintages): **wages** (Monthly Labour `0003138108` frozen 2015 — needs post-2018-rebenchmark table), **construction** (`0004000400` ends 2024-12 + is buildings not dwelling-units — needs MLIT direct), **Flow of Funds** (BIS credit-to-GDP covers cell 4.2).

### Freshness audit (2026-07-10 live run, 16/17 current)
| Fetcher | Latest obs | Cadence | Note |
|---|---|---|---|
| boj/fx | 2026-07-08 | Daily | Current |
| boj/rates | 2026-07-08 | Daily | Current |
| esri/gdp | Q1-2026 | Quarterly | Current |
| boj/iip | Q1-2026 | Quarterly | Current |
| boj/tankan | Jul-2026 survey | Quarterly | Current |
| bis/japan | Q4-2025 | Quarterly | Current (BIS release lag) |
| boj/cgpi | Jun-2026 | Monthly | Current |
| boj/money | Jun-2026 | Monthly | Current |
| boj/bop | May-2026 | Monthly | Current |
| boj/sppi | May-2026 | Monthly | Current |
| estat/cpi | May-2026 | Monthly | Current |
| estat/economy\_watchers | May-2026 | Monthly | Current |
| estat/labour | May-2026 | Monthly | Current |
| mof/trade | May-2026 | Monthly | Current |
| mhlw/wages | Apr-2026 | Monthly | Current (final ~3mo lag vs preliminary) |
| meti/retail | — | Monthly | **Fixed 2026-07-10**: METI WAF blocks `IMDR-econ-discovery` UA. Fix: browser UA + `Referer` header + primed `requests.Session` (GET index once for WAF cookie) + ZIP magic-byte validation with retry. METI throttles rapid access with empty-body HTTP 202; a clean end-to-end re-test is pending host cooldown. Fix confirmed — a single clean browser request returned the valid 462KB xlsx. |
| meti/iip | Mar-2026 | Monthly | **Lagging (not broken)**: e-Stat mirrors METI's *confirmed* IIP series ~1 quarter behind current date. Table `0004052177` is the current 2020-base table (updated 2026-06-03), NOT superseded. Fresher *preliminary* IIP lives on METI's own website — a separate parser is a follow-on. Leave as-is with this caveat. |

Marker key: ✅ route proven + fetcher built · 🔧 route confirmed, fetcher pending · ⚠ partial (FRED mirror only) · ❓ source unconfirmed · ❌ not available.

## 4×4 coverage tracker

| Cell | Status | Headline indicator (source) | Notes |
|---|:---:|---|---|
| 1.1 Private Demand    | ✅ | Economy Watchers DI (e-Stat) + retail (METI XLSX) | EW SA DI **built**; **retail built** (`meti/fetch_retail.py` — total/wholesale/retail/dept/super/CVS, ¥13.3tn Apr-2026, identities hold; e-Stat 商業動態 was frozen at Dec-2020 → METI site XLSX is the live source) |
| 1.2 Fiscal Demand     | ⚠ | ESRI QE gov consumption + public investment | demand-side **built** (gov consumption + public investment via ESRI QE). Funding-side (tax revenue / balance) still deferred (MOF site annual PDF/Excel or FRED gov-debt mirror). **JGB issuance by tenor now built** (`mof/fetch_jgb_issuance.py` — 9 ind, ANNUAL, FY2025 supp + FY2026 initial; partially addresses the fiscal supply/debt dimension). |
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
| 4.2 Balance Sheets    | ✅ | **BIS credit-to-GDP gap + DSR** | **built** (`playground/econ/bis/fetch_japan.py` — DSR households/NFC/private + credit-to-GDP ratio 175% / gap, to 1964). BoJ Flow of Funds (`fof.zip`) deferred (BIS covers the headline). **JGB holder breakdown** now adds institutional balance-sheet lens (`mof/fetch_jgb_holders.py` — BoJ 47.9%, Insurance 15.3%, Banks 14.8%, Foreigners 8.1%, Public Pensions 7.2%, Pension Funds 3.1%; Mar-2026 ¥1,013.8tn outstanding; QUARTERLY). **GPIF asset allocation** (`gpif/fetch_gpif.py` — 11 ind, ANNUAL Mar-2015→Mar-2024, domestic bonds/foreign bonds/domestic eq/foreign eq/alternatives value+share + AUM). |
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
| **MOF JGB issuance (Highlights PDF)** | none | JGB market issuance by tenor (2/5/10/20/30/40Y + T-Bills + retail), ANNUAL | PyMuPDF parse of `mof.go.jp/english/policy/jgbs/debt_management/plan/highlight{YYMMDD}.pdf`, page-1 table; anchored on 10Y=31.2 + coupon subtotal=112.2 | ✅ built (`mof/fetch_jgb_issuance.py`) NEW 2026-07-10 |
| **MOF JGB holder breakdown (Flow of Funds PDF)** | none | JGB outstanding by investor sector (BoJ, banks, insurance, public pensions, pension funds, foreigners, households), QUARTERLY | PyMuPDF parse of `mof.go.jp/english/policy/jgbs/reference/Others/holdings01.pdf`; anchored on BoJ share > 40% | ✅ built (`mof/fetch_jgb_holders.py`) NEW 2026-07-10 |
| **MOF JGB yields** | none | JGB benchmark curve | `mof.go.jp/.../interest_rate/` yearly CSV | ❓ unprobed (FRED 10Y live as backup) |
| **GPIF annual Excel holdings** | none | asset-allocation profile (domestic bonds / foreign bonds / domestic eq / foreign eq / alternatives), value + share + AUM, ANNUAL | Enumerate Excel links from `gpif.go.jp/en/performance/past-performances.html`; sum each sheet's Market Value column (GPIF Total row preferred; securities sum as cross-check); as-of date read from sheet header, not filename | ✅ built (`gpif/fetch_gpif.py`) NEW 2026-07-10 |
| **BIS** | none | credit-to-GDP gap + DSR (cell 4.2) | `playground/econ/bis/fetch_japan.py` (reuses `_bis_sdmx.py`, ref-area `JP`; REER/NEER/policy-rate omitted — BoJ native) | ✅ built (`fetch_japan.py`) |

## Build order (headline-first, per playbook)

1. ✅ CPI (e-Stat `0003427113`) · ✅ BoP (BoJ flat-file) — done
2. ✅ Policy/call rate + discount rate + money stock + monetary base + FX/NEER/REER (BoJ mtshtml) — **built**
3. ✅ GDP — Cabinet Office ESRI QE (`ritu-jk`/`gaku-jk` CSVs) — **built** (`esri/fetch_gdp.py`)
4. ✅ Labour — e-Stat rates (`0003005865`) + levels (`0003005798`) — **built**
5. ✅ Economy Watchers DI — e-Stat (`0003348423`) — **built**
6. ✅ Wages — e-Stat Monthly Labour file-catalog — **built** (`mhlw/fetch_wages.py`)
7. ✅ CGPI/PPI + SPPI (BoJ flat-file) · TANKAN sentiment (BoJ `co.zip`) — **built**
8. 🔧 Construction starts — e-Stat (`0004000400`) — deferred (ends 2024-12; needs MLIT direct)
9. ✅ Retail (METI site XLSX, WAF fix 2026-07-10) · ✅ IIP (e-Stat 2020-base) · ✅ trade (MOF customs) — **all built**
10. ✅ BIS balance-sheet metrics (`bis/fetch_japan.py` — DSR + credit-to-GDP); Flow of Funds deferred
11. ✅ JGB issuance by tenor (`mof/fetch_jgb_issuance.py`) + JGB holder breakdown (`mof/fetch_jgb_holders.py`) — **built** 2026-07-10
12. ✅ GPIF asset-allocation profile (`gpif/fetch_gpif.py`) — **built** 2026-07-10

**Remaining follow-ons (discovery):** construction starts (MLIT direct), preliminary IIP on METI website (fresher than e-Stat confirmed series), GPIF tip-lag via summary PDF parser (headline Mar-2026 allocation not yet in holdings Excel), JGB yield curve full-history backfill (MOF historical archive).

## Related
- [`index.md`](index.md) — country landing page
- [`_playground/boj.md`](_playground/boj.md) · [`_playground/estat.md`](_playground/estat.md) · [`_playground/esri.md`](_playground/esri.md) · [`_playground/meti.md`](_playground/meti.md) · [`_playground/mhlw.md`](_playground/mhlw.md) · [`_playground/mof.md`](_playground/mof.md) · [`_playground/gpif.md`](_playground/gpif.md) — per-vendor discovery notes
- [`../macro_economy_wiring_map.md`](../macro_economy_wiring_map.md) §7.4 — JP coverage grid
- [`../onboarding_new_country.md`](../onboarding_new_country.md) — playbook
