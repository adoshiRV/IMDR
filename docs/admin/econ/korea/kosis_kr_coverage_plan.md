# KOSIS — Korea (KR) coverage plan

Last updated: 2026-06-03

Maps every Korea (KR) cell of the
[macro_economy_wiring_map.md §7.13](../macro_economy_wiring_map.md#713-south-korea-kr)
to specific KOSIS `(orgId, tblId)` candidates.

This is the **plan** for filling `econ.dim_indicator` Korea rows — today
there are **zero** KR rows in the DB. Once a table is probed and the
relevant `itmId`/`objL1` codes are nailed down, the indicator can move
from this plan into a fetcher under
[`playground/econ/kosis/`](../../../../playground/econ/kosis/) and then
into `dim_indicator` via the standard econ loader pattern.

## Status legend

For each candidate table below:

| Marker | Meaning |
|---|---|
| ✅ **confirmed** | Smoke-tested 2026-06-03 — returned rows for `orgId/tblId` with `prdSe=M/Q` and `itmId=ALL & objL1=ALL` |
| ⚠ **candidate** | Code follows the documented BOK ECOS prefix; KOSIS mirror should exist but hasn't been probed |
| ❓ **unknown** | The wiring-map concept exists in Korea statistics, but the right table hasn't been identified — needs catalogue browse |
| ❌ **KOSIS-absent** | Probed with `err=21 "해당 통계표가 존재하지 않습니다"` — the table is NOT mirrored to KOSIS at the BOK orgId; fallback path required |

## Default `orgId` policy

| Source | `orgId` | Use for |
|---|---|---|
| BOK (한국은행) | **301** | BoP, IIP, national accounts, money & banking, interest rates, CPI/PPI (BOK reissue), terms of trade |
| Statistics Korea (통계청) | **101** | Population, employment (KOSTAT survey), wages, retail sales, housing, customs trade (KOSTAT publication) |
| Korea Customs Service (관세청) | **343** | Customs-basis trade (alternative to KOSTAT publication of same data) |

When a series is published by more than one agency (e.g. CPI from both
KOSTAT and BOK ECOS reissue), prefer **BOK orgId=301** — it's the
reference book and matches the ECOS `STAT_CODE` 1:1.

---

## 1. Growth Engine

### 1.1 Private Demand (consumption, capex, housing, wages, household credit)

| Concept | orgId | tblId | Cadence | Status |
|---|:---:|---|:---:|:---:|
| Household final consumption expenditure (by purpose) | 301 | `DT_200Y140` … `DT_200Y143` | Q | ⚠ |
| Final consumption expenditure (alt cuts) | 301 | `DT_200Y144` … `DT_200Y149` | Q | ⚠ |
| Total capital formation by type / industry | 301 | `DT_200Y127` … `DT_200Y134` | Q | ⚠ |
| Gross fixed capital formation | 301 | `DT_200Y135` … `DT_200Y137` | Q | ⚠ |
| Equipment investment by economic activity | 301 | `DT_200Y138` … `DT_200Y139` | Q | ⚠ |
| Retail sales index (services + retail) | 101 | needs catalogue browse | M | ❓ |
| Housing transactions / housing start permits | 101 | needs catalogue browse | M | ❓ |
| Household income / wages | 101 | needs catalogue browse | Q | ❓ |
| Household credit aggregates | 301 | `DT_101Y…` family (Money & Banking) | M | ⚠ |

### 1.2 Fiscal Demand (govt spending, taxes, deficit)

| Concept | orgId | tblId | Cadence | Status |
|---|:---:|---|:---:|:---:|
| General government final consumption | 301 | `DT_200Y151` | Q | ⚠ |
| Total expenditures of the government | 301 | `DT_200Y152` | Q/A | ⚠ |
| General government's sectoral accounts | 301 | `DT_200Y153` | A | ⚠ |
| Gross revenue, gross expenditure (Govt) | 301 | `DT_200Y154` | A | ⚠ |
| Capital accounts by institutional sector | 301 | `DT_200Y122` | Q | ⚠ |

### 1.3 External Demand (exports, imports, net exports, inventories)

| Concept | orgId | tblId | Cadence | Status |
|---|:---:|---|:---:|:---:|
| Overseas Transactions — Current (SNA cut) | 301 | `DT_200Y118` | Q | ⚠ |
| Overseas Transactions — Capital (SNA cut) | 301 | `DT_200Y119` | Q | ⚠ |
| Customs-basis trade overview | 301 | `DT_901Y118` (or KOSTAT mirror) | M | ❌ at org 301 → use KOSTAT publication |
| Customs trade by continent | 301 | `DT_901Y119` | M | ❌ at org 301 → use KOSTAT publication |
| Customs trade by country | 301 | `DT_901Y121` | M | ❌ at org 301 → use KOSTAT publication |
| Customs trade by nature | 301 | `DT_901Y092` | M | ❌ at org 301 → use KOSTAT publication |

The `901Y…` customs tables exist in BOK ECOS but the BOK-org KOSIS
mirror returns `err=21`. Customs Service (orgId=343) publishes the same
data; alternative is KOSTAT orgId=101.

### 1.4 Macro Core (GDP, productivity, employment, slack)

| Concept | orgId | tblId | Cadence | Status |
|---|:---:|---|:---:|:---:|
| **Key indicators (annual)** | 301 | `DT_200Y101` | A | ⚠ |
| **Key indicators (quarterly)** | 301 | **`DT_200Y102`** | Q | ✅ |
| GDP and GNI by economic activity | 301 | `DT_200Y103` … `DT_200Y106` | Q | ⚠ |
| Expenditure on GDP | 301 | `DT_200Y107` … `DT_200Y110` | Q | ⚠ |
| Nominal GDP by value added | 301 | `DT_200Y160`, `DT_200Y161` | Q | ⚠ |
| Gross domestic product (level series) | 301 | `DT_200Y113` | Q | ⚠ |
| Gross domestic value added | 301 | `DT_200Y114` | Q | ⚠ |
| Growth contribution (demand / activity / expenditure) | 301 | `DT_200Y123` … `DT_200Y126` | Q | ⚠ |
| Employment / unemployment rate | 101 | KOSTAT economically-active-population survey | M | ❓ |

---

## 2. Inflation Engine

### 2.1 Input Costs (commodities, food, energy, FX pass-through)

| Concept | orgId | tblId | Cadence | Status |
|---|:---:|---|:---:|:---:|
| Import prices (BOK reissue) | 301 | `DT_404Y…` family — import price index | M | ⚠ |
| Producer / wholesale input cost cuts | 301 | `DT_404Y…` PPI sub-series | M | ⚠ |
| Energy supply prices (gas, electricity) | 101 | KOSTAT energy survey | M | ❓ |

### 2.2 Producer Prices (PPI, margins, pipeline)

| Concept | orgId | tblId | Cadence | Status |
|---|:---:|---|:---:|:---:|
| PPI — total | 301 | `DT_404Y…` PPI sub-table | M | ⚠ |
| Import / export price indices | 301 | `DT_404Y…` (paired with PPI) | M | ⚠ |
| Manufacturer inventories | 101 | KOSTAT industrial activity report | M | ❓ |

### 2.3 Domestic Costs (wages, rents, services, expectations)

| Concept | orgId | tblId | Cadence | Status |
|---|:---:|---|:---:|:---:|
| Wage index by industry | 101 | KOSTAT wage survey | M | ❓ |
| Capacity utilisation | 101 | KOSTAT industrial activity report | M | ❓ |
| Inflation expectations survey | 301 | BOK Consumer Survey index | M | ❓ |

### 2.4 CPI Pressure (headline, core, breadth, persistence)

| Concept | orgId | tblId | Cadence | Status |
|---|:---:|---|:---:|:---:|
| **CPI item-level (BOK reissue)** | 301 | **`DT_404Y014`** | M | ✅ |
| CPI headline + core (full series) | 301 | `DT_404Y…` CPI sub-tables | M | ⚠ |
| Wholesale / producer price (paired) | 301 | `DT_404Y…` | M | ⚠ |

CPI confirmed working via `DT_404Y014` with `itmId=ALL&objL1=ALL` —
returned 2020=100 base values. Replaces the "MODS press-release PDFs"
fallback currently in the wiring map (KOSIS gives structured numerics
instead of OCR/PDF parsing).

---

## 3. External & FX

### 3.1 Terms of Trade (export prices vs import prices)

| Concept | orgId | tblId | Cadence | Status |
|---|:---:|---|:---:|:---:|
| **Terms of Trade Index** | 301 | **`DT_403Y005`** | M | ✅ |
| Trade Index (price + volume) | 301 | `DT_403Y…` family | M | ⚠ |

Terms of Trade confirmed — returned `TERMS_TRADE_TYPE.A` (commodity
TOT) base 2020=100 at 107.02 for the latest period.

### 3.2 Current Account (trade, services, income, remittances)

| Concept | orgId | tblId | Cadence | Status |
|---|:---:|---|:---:|:---:|
| **Balance of Payments (master)** | 301 | **`DT_301Y013`** | M | ✅ Already wired in playground |
| Current Account (SA) | 301 | `DT_301Y017` | M | ⚠ |
| Trade detail by EBOPS classification | 301 | `DT_301Y014` | M | ⚠ |
| Current Account by region | 301 | `DT_301Y015` | A | ⚠ |

### 3.3 Capital Account (FDI, portfolio, bank flows, reserves, E&O)

| Concept | orgId | tblId | Cadence | Status |
|---|:---:|---|:---:|:---:|
| Financial Account (in master BoP) | 301 | `DT_301Y013` — `BOPF…` codes | M | ✅ via fetch_bop.py |
| Capital/Financial Account by region | 301 | `DT_301Y016` | A | ⚠ |
| International Investment Position | 301 | `DT_311Y001` | Q | ⚠ probe returned `err=30` empty for current period — try wider window |
| IIP for nations | 301 | `DT_311Y002` | A | ⚠ |
| IIP for currencies | 301 | `DT_311Y003` | A | ⚠ |
| External Debt | 301 | `DT_311Y004` | Q | ⚠ |
| External Assets | 301 | `DT_311Y005` | Q | ⚠ |
| Net External Assets | 301 | `DT_311Y006` | Q | ⚠ |

### 3.4 FX / REER (spot, NEER, REER, intervention)

| Concept | orgId | tblId | Cadence | Status |
|---|:---:|---|:---:|:---:|
| Daily FX rates (KRW vs majors) | 301 | `DT_731Y001` / `DT_731Y003` | D | ❌ at org 301 → use BIS/Citi instead |
| FX Reserves (stock) | 301 | `DT_732Y001` | M | ❌ at org 301 → check BOK Currency/Finance branch |
| BIS NEER / REER for KRW | n/a | KOSIS doesn't republish BIS effective indices | M | Source from BIS or FRED mirror |

For FX series: KOSIS `731Y…`/`732Y…` codes returned `err=21 "해당 통계표가
존재하지 않습니다"` against `orgId=301` — these BOK tables exist in ECOS
but the KOSIS-side mirror likely sits under a different branch (Currency
/ Finance, branch 1 — not yet mapped in
[`stat_code_inventory.md`](../../../playground/econ/bok_ecos/stat_code_inventory.md)).
Until found, source FX rates from Citi `FX.SPOT.USD.KRW.CITI` (already
live) and FX reserves from FRED mirror.

---

## 4. Policy Transmission

### 4.1 Demand Transmission (lending growth, lending standards)

| Concept | orgId | tblId | Cadence | Status |
|---|:---:|---|:---:|:---:|
| Bank loans (total, by sector) | 301 | `DT_101Y…` Money & Banking | M | ⚠ |
| Mortgage / housing loans | 301 | `DT_101Y…` housing loans subset | M | ⚠ |
| BOK Loan Officer survey (lending standards) | 301 | `DT_511Y…` BOK Financial Stability survey | Q | ❓ |

### 4.2 Balance Sheets (household + corporate + bank + sovereign)

| Concept | orgId | tblId | Cadence | Status |
|---|:---:|---|:---:|:---:|
| Household credit (BOK Financial Stability Report) | 301 | `DT_101Y…` household credit table | Q | ⚠ |
| Corporate debt / leverage | 301 | `DT_101Y…` corporate sector | Q | ⚠ |
| Bank NPL ratio | 301 | `DT_511Y…` Financial Stability Report tables | Q | ❓ |
| Government debt / GDP | 101 | KOSTAT fiscal stats | A | ❓ |

### 4.3 Financial Conditions (rates curve, credit spreads, equities)

| Concept | orgId | tblId | Cadence | Status |
|---|:---:|---|:---:|:---:|
| **Bank deposit-side rates (CD 91d, time deposits, repo, FinDebent)** | 301 | **`DT_121Y002`** | M | ✅ **loaded 2026-06-05** — 6 indicators 1996→ |
| Money market rates (call money, CD) | 301 | `DT_121Y002` (same table) | M | ✅ loaded (CD 91d, repo) |
| KORIBOR / CD curve detail | 301 | `DT_121Y…` family | D/M | ⚠ |
| Corporate bond credit spreads | 301 | `DT_121Y…` corporate yields | M | ⚠ |

> **Correction (2026-06-05)**: An earlier draft listed `DT_121Y002` as
> "market interest rates incl. base rate". After loading, the table is
> actually **DEPOSIT-SIDE bank rates** (예금은행 수신금리) — Time Deposits,
> CDs, Repos, Financial Debentures. The 2.88% return that looked like
> a "policy rate" was Time & Savings Deposits ex-debentures. The actual
> BOK Base Rate is NOT in KOSIS — it's only accessible via the BOK
> website or via Citi market data.

### 4.4 Policy Reaction (BOK Base Rate, fiscal stance, macropru)

| Concept | orgId | tblId | Cadence | Status |
|---|:---:|---|:---:|:---:|
| **BOK Base Rate** | — | NOT IN KOSIS | M | ❌ — use BOK direct page or Citi `RATES.BENCH_RATES.KR` (TBD) |
| **M2 components** | 301 | **`DT_101Y004`** | M | ⚠ — table confirmed, 16 sub-cuts; not yet built |
| Money supply M1/M2/Lf headline | 301 | `DT_102Y…` family (monetary base) or similar — needs probing | M | ❓ |
| Currency in circulation | 301 | `DT_102Y…` family | M | ⚠ |
| Macroprudential ratios (LTV, DTI) | n/a | not in BOK / KOSTAT standard catalogue — likely FSC press releases | event | ❓ |

---

## 5. Summary — what KOSIS covers vs gaps (refreshed 2026-06-05)

After two build rounds (2026-06-03 housing+CPI, 2026-06-05 PPI+GDP-Q+ToT+Bank Rates),
KR cells in [macro_economy_wiring_map.md §7.13](../macro_economy_wiring_map.md#713-south-korea-kr)
break down as:

| Status | Count | Cells |
|---|:---:|---|
| **✅ Loaded in `econ.dim_indicator`** | 14 | 1.1 Retail · 1.2 Fiscal · 1.3 External · 1.4 Macro Core · 2.1 Input Costs · 2.2 PPI · 2.3 Wages · 2.4 CPI · 3.1 ToT · 3.2 CA · 3.3 Capital Acc · 4.1 Demand Trans · 4.2 Balance Sheets · 4.4 Policy Reaction (BIS CBPOL — BOK Base Rate `BIS.POLICY_RATE.KR` as of 2026-06-16; KOSIS DT_121Y002 carries deposit-side rates only) |
| **⚠ Partial — KOSIS deposit-side only** | 1 | 4.3 Fin Conds (KOSIS DT_121Y002 carries deposit-side rates; BOK Base Rate confirmed absent from KOSIS — lives in ECOS only; covered in cell 4.4 via BIS CBPOL) |
| **parked — user-deferred** | 1 | 3.4 FX/REER (route via Citi spot + FRED BIS REER/NEER when needed) |
| **❓ Concept exists, table unknown** | 0 | — |
| **❌ KOSIS-absent — fallback required** | 0 | (4.4 now ✅ via BIS CBPOL 2026-06-16 — the BOK Base Rate is not on KOSIS and was never on Citi BENCH_RATES; BIS WS_CBPOL D.KR is the correct source) |

Net: KR is at **14 ✅ / 1 ⚠ partial / 1 parked**. All cells either filled or
explicitly deferred. The Citi BENCH_RATES gap is now moot — cell 4.4 is covered by `BIS.POLICY_RATE.KR` (BIS SDMX WS_CBPOL, wired 2026-06-16).

**Closed 2026-06-05:**
- BoP refactor: `fetch_bop.py` rewritten Playwright → OpenAPI; 24 BoP indicators loaded; cells 3.2 + 3.3 ⚠ → ✅.
- REB-direct vendor: migration 078 added `reb` row to `dbo.dim_vendor`; 4 REB-direct housing indicators loaded under `.REB_DIRECT` imdr_code suffix to coexist with KOSIS-mirror rows. REB-direct adds 11 years of history (2012-05 vs KOSIS-mirror's 2021-07).

## 6. Recommended sequencing (refreshed 2026-06-05)

**DONE (loaded into `econ.dim_indicator`):**

1. ✅ **CPI monthly** — `KOSTAT DT_1J22042` → 15 series. Cell 2.4. Loaded 2026-06-03.
2. ✅ **REB Housing weekly** — KOSIS-mirror + REB-direct → 4 series. Cells 4.1/4.2 partial. Loaded 2026-06-03 (KOSIS mirror) + parquet on disk for REB-direct.
3. ✅ **PPI monthly** — `BOK DT_404Y014` → 6 series. Cell 2.2. Loaded 2026-06-05 (40k-cap solved).
4. ✅ **GDP quarterly** — `BOK DT_200Y102` → 24 series. Cell 1.4 + parts of 1.3. Loaded 2026-06-05.
5. ✅ **Terms of Trade monthly** — `BOK DT_403Y005` → 2 series. Cell 3.1. Loaded 2026-06-05.
6. ✅ **Bank Rates monthly** — `BOK DT_121Y002` → 6 series. Cell 4.3 partial. Loaded 2026-06-05.

7. ✅ **KOSIS BoP** — `BOK DT_301Y013` → 24 series (CA total + Goods/Services/Primary/Secondary balances + sub-cuts + 12 FA components + E&O), monthly 1980-01→. Cells 3.2 + 3.3 ⚠ → ✅. `fetch_bop.py` rewritten Playwright → OpenAPI. Loaded 2026-06-05.

8. ✅ **REB-direct vendor + housing load** — migration 078 added `reb` row to `dbo.dim_vendor`; 4 housing series loaded with `.REB_DIRECT` imdr_code suffix to coexist with KOSIS-mirror rows. 2012-05 → present (11 yr deeper than KOSIS mirror). Loaded 2026-06-05.
9. ✅ **KOSTAT EAPS Labour** — `DT_1DA7001S` → 8 series, monthly 1999-06→. Cell 1.4 labour leg ⚠ → ✅. Loaded 2026-06-05.
10. ✅ **KOSTAT Retail Sales** — `DT_1K41013` → 14 series, monthly 2000-01→. Cell 1.1 ⚠ → ✅. Loaded 2026-06-05.
11. ✅ **BOK Fiscal** — `DT_200Y154` (2-axis) → 7 series annual 2007→ (Revenue / Expenditure / Net Lending / Saving / Direct + Indirect Taxes / Final Cons). Cell 1.2 ❌ → ✅. Loaded 2026-06-05.
12. ✅ **BOK Trade Prices** — `DT_401Y015` + `DT_402Y014` (2-axis) → 4 series monthly 1980→ (Import/Export × Won/USD). Cell 2.1 ⚠ → ✅. Loaded 2026-06-05.
13. ✅ **FRED Korea Rates** — added 4 series to FRED seed (Discount / Call / 3M Interbank / 10Y Govt). Cell 4.4 ❌ → ✅. Loaded 2026-06-05. Citi BENCH_RATES gap (no KR) documented for future addition.
14. ✅ **BOK Lending** — `DT_514Y001` + `DT_151Y005` → 8 series (5 lending stance survey Q + 3 HH loans M, 2003→). Cell 4.1 ⚠ → ✅. Loaded 2026-06-05.
15. ✅ **BOK Balance Sheets** — `DT_151Y001` HH Credit + `DT_376_10_SDMA051V_3` FSS NPL → 5 series (2 HH credit Q 2002→ + 3 FSS NPL Q 2000-2016 stale). Cell 4.2 ⚠ → ✅. Loaded 2026-06-05.
16. ✅ **KOSTAT Wages** — `DT_1YL15006` → 2 annual national series. Cell 2.3 ❓ → ✅. Loaded 2026-06-05.
17. ✅ **BOK Trade Indices** — `DT_403Y001-004` → 4 monthly series (Export/Import × Value/Volume, 1988→). Cell 1.3 ⚠ → ✅. Loaded 2026-06-05.

**NEXT (build order — remaining gaps):**
9. **KOSTAT labour / EAPS** — Employment, unemployment rate, LFPR. Cell 1.4 ⚠ → ✅. Needs catalogue browse to pin `tblId`.
10. **KOSTAT retail sales + industrial production** — Cell 1.1 + 1.3 ⚠ → ✅. Needs catalogue browse.
11. **KOSTAT customs trade** — Cell 1.3 ⚠ → ✅ at goods level. ~`orgId=101` mirror of `901Y…`.
12. **IIP + External Debt** — `BOK DT_311Y001` … `DT_311Y006` → stock counterpart to BoP. Cell 3.3 deeper.
13. **Import/Export price indices** — `BOK DT_401Y…` + `DT_402Y…` → fills 2.1 Input Costs.
14. **BOK Base Rate via Citi** — add `RATES.BENCH_RATES.KR` to Citi (not KOSIS). Cell 4.4 ❌ → ✅.
15. **BIS REER/NEER via FRED** — `RBKRBIS` + `NBKRBIS`. Cell 3.4 ❌ → ⚠.
8. **Customs trade via orgId=101** — fills 1.3 with M-frequency goods trade.
9. **PPI + import/export prices** — `DT_404Y…` family → fills 2.1 + 2.2.
10. **FX/REER** — defer pending BOK Currency/Finance branch exploration; bridge via Citi spot in the meantime.

## 7. Open follow-ups

- **BOK branch 1 (Currency/Finance) `stat_code_inventory.md` is unexplored** — `731Y…`/`732Y…` (FX rates + reserves) are documented in ECOS but `err=21` against KOSIS `orgId=301`. The BOK→KOSIS mirror is not 1:1 for all branches. Need a Playwright session against branch 1 to capture the right codes (and possibly different orgId).
- **`prdSe` cycle handling** — many KOSIS tables only carry one cycle (`Q` for SNA, `M` for prices). The fetcher must read `LST_CHN_DE` per row to detect cadence rather than assume.
- **`itmId=ALL & objL1=ALL` not safe everywhere** — works on `200Y102`, `404Y014`, `121Y002`, `101Y004`, `403Y005`. Fails (`err=20 (objL)`) on KOSTAT tables `DT_1DA7012S`/`DT_1DA7102S` which require explicit `objL1`. Per-table calibration needed.
- **Probe budget**: building all 6 fetchers above should stay under ~200 calls/day, well within the unpublished per-minute throttle observed.

## Cross-refs

- KOSIS OpenAPI mechanics: [kosis_openapi_reference.md](kosis_openapi_reference.md)
- BOK STAT_CODE inventory (source for `tblId` candidates): [playground inventory](../../../../playground/econ/bok_ecos/stat_code_inventory.md)
- Cluster definitions / KR coverage state: [macro_economy_wiring_map.md §7.13](../macro_economy_wiring_map.md#713-south-korea-kr)
- Existing BoP fetcher: [`playground/econ/kosis/fetch_bop.py`](../../../../playground/econ/kosis/fetch_bop.py)
- Econ schema: `econ.dim_indicator` / `econ.fact_indicator` (see [economics_data_ingest.md](../economics_data_ingest.md))
