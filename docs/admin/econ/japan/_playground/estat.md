# e-Stat — `playground/econ/jp/estat/`

**Status:** deep discovery complete (2026-06-22). API confirmed; CPI fetcher proven; full blueprint sweep + hard checks done.

e-Stat (`api.e-stat.go.jp`) is Japan's official statistics portal — the **KOSIS analog**. REST 3.0 JSON, single `appId` query param (free; one per account). Key read from `IMDR_ECON_ESTAT_KEY` in `.env` via `python-dotenv` (mirrors the FRED connector's env-direct pattern; **not** in `settings.py` yet — wire on promotion).

## API mechanics
Base `https://api.e-stat.go.jp/rest/3.0/app/json/`, three endpoints:
- **`getStatsList`** — find tables. Filter by `statsCode` (8-digit govt-statistics code) or `searchWord`. Returns `statsDataId` + title + `CYCLE` + `OPEN_DATE` + `GOV_ORG`.
- **`getMetaInfo`** — classification axes (`CLASS_OBJ` per `@id`: `tab`, `cat01…`, `area`, `time`) for a `statsDataId`.
- **`getStatsData`** — observations. Filter by `cdTab`/`cdCat01`/`cdArea`/`cdTimeFrom`-`cdTimeTo`/`limit`/`startPosition`. `VALUE[]` carry `@tab/@cat01/@area/@time/@unit/$`.

`RESULT.STATUS==0` = success; `STATUS==1` "no data" = empty/over-filtered (the helper raises — catch it for `cdTimeFrom` probes). Single-element arrays collapse to dict → normalise via `as_list()`.

### Time-code format (standard tables)
`YYYY00mmMM` — positions [4:6]=='00' → monthly (month in [8:10]); quarterly uses quarter-start/end months in the two trailing pairs (`…0103`=Q1, `0406`=Q2, `0709`=Q3, `1012`=Q4); annual/fiscal codes use [4:6]!='00' and are skipped. **Caveat:** some agency tables (METI IIP) put the period in a `cat` axis, NOT `@time` — see below.

## ⚠ Headline finding — English API ≠ Japanese API
e-Stat's **English** (`lang=E`) search/metadata only covers a subset of agencies. Verified:

| Agency | English (`lang=E`) | Japanese (`lang=J`) |
|---|:---:|:---:|
| **MIC** / Statistics Bureau (CPI, Labour Force, Population, Family Income) | ✅ full | ✅ |
| **MOF** Trade Statistics | ✅ | ✅ |
| **Cabinet Office** (Economy Watchers, SNA) | ⚠ partial | ✅ |
| **METI** (retail 商業動態, IIP 鉱工業) | ❌ none | ✅ |
| **MHLW** (Monthly Labour / wages) | ❌ none | ✅ |
| **MLIT** (construction starts) | ❌ none | ✅ |

**Implication:** search METI/MHLW/MLIT/Cabinet by **Japanese** survey name; ingest with `lang=J`. Source labels come back Japanese — fine, because `display_name` (English) is set by us in `schema_prototype.IndicatorRow`. The `searchWord` AND-matching is strict (multi-word queries often return "no data"); use the single most distinctive Japanese term.

## ✅ Verified canonical tables (clean monthly/quarterly, real data confirmed)

| Indicator | statsDataId | Provider | Cadence | Unit | Cell | Notes |
|---|---|---|:---:|---|:---:|---|
| **CPI 2020-base** | `0003427113` | MIC | M | index 2020=100 / % | 2.4 | ✅ **`fetch_cpi.py`** — items `0001`/`0161`/`0178`; tab `1`=Index `3`=YoY; 1970→ |
| **Labour Force — rates** | `0003005865` | MIC | M | ％ | 1.4 | ✅ **`fetch_labour.py`** — participation/employment/unemployment, tab `02`, cat02 `01/13/08` |
| **Labour Force — levels** | `0003005798` | MIC | M | 万人 (10k persons) | 1.4 | ✅ **`fetch_labour.py`** — pop-15+/labour-force/employed/unemployed/not-in-force, cat02 `00/01/02/08/09`; identity verified |
| **Economy Watchers DI** | `0003348423` | Cabinet | M | DI | 1.1/1.4 | ✅ **`fetch_economy_watchers.py`** — `lang=J`; field `100/110/590/940` × dir `100/110`; Apr-2026 live |
| **Monthly Labour Survey (wages)** | `0003138108` | MHLW | M | 円 | 2.3 | ⛔ **DEFERRED — frozen at Nov 2015** (2018 re-benchmark split table). tab `741`=現金給与総額; needs post-2016 vintage statsDataId |
| **Construction starts** | `0004000400` | MLIT | M | 棟 / ㎡ / 円 | 1.1 | ⛔ **DEFERRED — ends 2024-12** (frozen) + is buildings-count/floor/cost, not the headline 新設住宅着工戸数 dwelling-units → use MLIT direct |

## ⚠ Present on e-Stat but NOT the right lane → prefer source agency

| Indicator | e-Stat id | Why not | Use instead |
|---|---|---|---|
| **GDP / SNA quarterly** | `0003399805` | **STALE — data ends 1996Q1‥2007Q1.** It's the historical finalized-SNA archive, not the live release | **Cabinet Office ESRI QE** (see below) — the live preliminary GDP |
| **IIP (industrial production)** | `0003272952` | Non-standard layout — **no `@time` attribute** (period encoded in a `cat` axis); 2010=100 base, no clean 2020-base on API | METI site (`meti.go.jp`) direct, or `FRED.IIP.INDEX.JP` mirror (already live) |
| **Retail (商業販売額)** | `0003395211` + family | Fragmented into **yearly-published snapshot tables**; no single monthly-updating series | METI 商業動態統計速報 on `meti.go.jp` direct |
| **Trade (commodity×country)** | `0003228116` family | Only **detailed commodity-by-country, yearly/confirmed** — not the timely monthly value/balance headline | MOF customs portal (`customs.go.jp`) monthly トレード概況, or FRED |

## ⭐ Live GDP source — Cabinet Office ESRI QE (the user-mandated lane)
The market-watched GDP is the **QE速報** (Quarterly Estimates, preliminary), released ~6 weeks after quarter-end by Cabinet Office ESRI — NOT on the e-Stat API. Discovered + structure-confirmed (`probe_esri_qe.py`):

- **Entry:** `https://www.esri.cao.go.jp/jp/sna/sokuhou/sokuhou_top.html` (200, no block). Links to the current release page, e.g. `…/sna/data/data_list/sokuhou/files/{YYYY}/qe{YYQ}_{n}/gdemenuja.html` → **72 CSV/XLS** download links under `…/tables/`.
- **CSV naming:** `{gaku|ritu}-{m|j}{k|g|cy|fy}{ver}.csv`
  - `gaku` 額 = levels · `ritu` 率 = growth rate
  - **`j` 実質 = REAL · `m` 名目 = nominal** *(verified from CSV header — easy to get backwards)*
  - `k` 季調 = seasonally adjusted · `g` = original · `cy` = calendar-year · `fy` = fiscal-year
  - → **headline real GDP QoQ = `ritu-jk{ver}.csv`**; real SA levels = `gaku-jk{ver}.csv`
- **Format:** Shift-JIS (`cp932`), wide, **bilingual headers** (~8 header rows), quarterly rows 1994→latest. Columns = full expenditure decomposition: GDP (expenditure approach), Private Consumption (incl. ex-imputed-rent), Private Residential, Private Non-Resi Investment, Private Inventories, Govt Consumption, Public Investment, Net Exports / Exports / Imports, GNI, Domestic Demand, Private/Public Demand, GFCF.
- **Latest-release discovery:** parse `sokuhou_top.html` each run for the current `qe{YYQ}_{n}` link (version bumps quarterly). On promotion this becomes `playground/econ/jp/esri/` (country-first: a Cabinet Office vendor, distinct from e-Stat).

## Probe scripts (all in this dir)
`probe_estat.py` (statsCode confirm) · `probe_cpi_meta.py` (CPI axes) · `fetch_cpi.py` ✅ · `probe_deep_search.py` (EN sweep) · `probe_jp_search.py` (JP sweep) · `probe_jp_refine.py` (headline narrowing) · `probe_hardcheck.py` (real-data gate) · `probe_gdp_iip_retail.py` (timeliness/axis) · `probe_esri_qe.py` (live GDP). Raw responses + findings JSON under `raw/`.

## Next moves
1. **GDP**: build `playground/econ/jp/esri/fetch_gdp_qe.py` — parse `ritu-jk`/`gaku-jk` from the auto-discovered latest release (real SA QoQ + levels + components).
2. **Labour**: `fetch_labour.py` — rates (`0003005865`) + levels (`0003005798`); resolve cat codes via getMetaInfo.
3. **Wages**: `fetch_wages.py` — `0003138108`, filter to total cash earnings.
4. **Economy Watchers**: `fetch_economy_watchers.py` — `0003348423`, SA national DI (current + outlook).
5. **Construction**: `fetch_construction.py` — `0004000400`, dwelling starts (count + floor area).
6. **IIP / retail / trade**: probe METI + MOF-customs source sites (separate from e-Stat) — defer.
7. Extend `fetch_cpi.py` with broad groups (food/energy/services/goods) + SA variants (`0901/0902/0906`).

> `.env` note: the `IMDR_BPS_API_URL=http://test.localhost:57683/` line is an unused orphan (BPS base is hard-coded in `bps_http.py`) — recommend deleting.
