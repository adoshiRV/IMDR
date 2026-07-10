# METI (retail + IIP) — `playground/econ/jp/meti/`

**Status:** retail + IIP fetchers built (2026-06-23). Two METI statistics via two different mechanisms.

## `fetch_retail.py` — Current Survey of Commerce (商業動態統計), cell 1.1
- **Source: METI site XLSX (LIVE)** — `https://www.meti.go.jp/statistics/tyo/syoudou/result-2/` → `excel/{stem}.xlsx`. e-Stat survey `00550030` is **frozen** (every monthly statsDataId opened 2020/2021, ends Dec-2020) → not viable.
- Files: `h2slt11j.xlsx` (total/wholesale/retail), `h2slt31j.xlsx` (dept+super), `h2slt41j.xlsx` (CVS).
- **14 indicators, ~7,358 obs**, `METI.RETAIL.{SECTOR}_{MEASURE}.JP`, SECTOR ∈ total/wholesale/retail/dept_super/dept/super/cvs, MEASURE ∈ value (¥bn) / YoY (%). `category="other"`, MONTHLY, 1980→ (CVS 1997→).
- Apr-2026 verified: retail ¥13.3tn (+2.8% YoY); identities hold (total = wholesale + retail; dept_super = dept + super). ✓
- **Gotchas**: YoY sheets publish a **100-base ratio** (100 = unchanged) → parser subtracts 100. Heterogeneous per-(file,sheet) layouts captured in a `SPECS` table. Time codes are e-Stat-style `YYYY00mmMM` → reuses estat's `time_to_date_monthly`. Downloads cached under `raw/`.

## `fetch_iip.py` — Indices of Industrial Production (鉱工業指数), cell 1.4
- **Source: e-Stat REST, 2020-base** (tables `0004052177`-`0004052231`, opened 2026-05-19 — the first 2020-base vintage). Reuses `estat/_estat_http` + `_estat_common`, `lang='J'`.
- **5 indicators** (SA, 2020=100, MONTHLY, 2018→): production `0004052177`, shipments `…78`, inventory `…79`, inventory-ratio `…80`, capacity-utilisation `0004052231`. `METI.IIP.{DETAIL}_SA.JP`, `category="gdp"`, `is_seasonally_adjusted=True`.
- Mar-2026 verified: production 102.0 (expected 100-105 band). ✓
- **Gotcha (load-bearing)**: e-Stat labels the period axis `@id='time'` but the VALUE `@time` is a **7-digit METI item code, NOT `YYYY00mmMM`** (`0500100`=201801, step +200/month). Fetcher resolves each table's `time` axis via `getMetaInfo` into a code→YYYYMM map and skips the index-weight rows. Industry total = `cat01=0001000` (鉱工業); capacity-util is manufacturing-only `cat02=1100000000`.
- Older 2015-base (`000401xxxx`) / 2010-base (`000327xxxx`) families exist for longer history. `FRED.IIP.INDEX.JP` remains a backup but native is one base-revision ahead.

## Next moves
- Retail: add by-sector retail breakdown (fabrics/food/auto/machinery) if needed.
- IIP: add by-industry production (155 industries available) or longer history via base-linking.
