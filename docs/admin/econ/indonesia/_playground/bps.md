# BPS — Pre-prod playground notes

Last updated: 2026-06-08

Companion to [`../bps_api_reference.md`](../bps_api_reference.md) (the durable
API spec). This file captures the **what-we-found** during Phase B
discovery — concrete catalogue contents, observed dataset shapes,
gotchas hit, and the var_ids that wire up the headline targets.

## Playground location

```
playground/econ/bps/
├── _bps_http.py                  ← shared HTTP helper (session, paginator, parser)
├── discovery/
│   ├── catalogue/                ← full national-level catalogue dump
│   │   ├── provinces.json        ← 34 province domains
│   │   ├── subcats.json          ← 4 top-level categories
│   │   ├── subjects.json         ← 52 subjects (bilingual)
│   │   ├── vars/{sub_id}.json    ← variable list per subject (1,655 total)
│   │   └── _summary.json
│   ├── dump_catalogue.py         ← re-run to refresh
│   ├── probe_endpoints.py        ← initial endpoint shape probe (history)
│   ├── probe_data_fetch.py       ← composite-key parser smoke test
│   └── probe_{TIMESTAMP}/        ← per-run raw responses (history)
└── sample_output/
    └── data_probe/               ← parser-validated raw + parsed payloads
```

## Phase B findings (2026-06-08)

### Catalogue surface

- **52 subjects** at national domain (0000), in **4 categories**
  (Sosial dan Kependudukan / Ekonomi dan Perdagangan / Pertanian dan
  Pertambangan / Lainnya).
- **1,655 distinct variables** across all subjects.
- **34 provinces** registered as separate BPS web-domains (each gets its
  own subdomain — `aceh.bps.go.id` etc.). For econ ingest we only need
  `domain=0000` (national rollup); per-province data comes through the
  `vervar` axis of the national datasets.
- Bilingual (`ind` + `eng`) merged catalogue stored. English titles drive
  the downstream `dim_indicator.name` field.

### Subject inventory (econ-relevant)

| sub_id | Title (eng) | Vars | Used by IMDR? |
|:---:|---|:---:|---|
| 3 | Consumer Prices Indices | **130** | ✅ CPI headline + 150-city + group/sub-group |
| 169 | GDP Expenditure | **36** | ✅ GDP demand-side decomposition |
| 11 | GDP Industrial Origin | 8 | ✅ GDP supply-side |
| 36 | Producer Price Indices | 13 | ✅ PPI YoY/QoQ + sectoral |
| 20 | Wholesale Price Indices | 32 | ✅ WPI + construction materials |
| 6 | Employment | 48 | ✅ Sakernas — unemployment, LFPR, LF by education |
| 19 | Labour Wages | 28 | ✅ Wages by sector + minimum wage |
| 8 | Foreign Trade | **40** | ✅ Customs exports/imports + by country/HS |
| 102 | Retail | 2 | ⚠ Limited — mostly retail rice prices |
| 25 | Business & Consumer Tendency | 1 | ✅ Combined ITB + ITK sentiment index |
| 13 | Public Finance | **78** | ⚠ Mostly banking + cooperative aggregates; APBN proper comes from MoF |
| 22 | Farmer Terms of Trade | 45 | ✅ NTP — leading indicator for rural income |
| 9 | Large and Medium Manufacturing | 32 | ✅ IBS — Industrial Production Mfg |
| 170 | Micro and Small Manufacturing | 18 | ✅ IMK |
| 5 | Consumption and Expenditure | 53 | ⚠ Susenas survey-based, slow cadence |
| 7 | Energy | 15 | Optional — supply-side energy prices/volumes |
| 30 | Health | 41 | Out of scope for macro ingest |
| 26 | Human Development Indices | 12 | ⚠ Annual HDI — out-of-scope for high-cadence ingest |
| 23 | Poverty and Inequality | 23 | ⚠ Annual — out-of-scope |
| 17 | Transportation | 23 | Optional |
| 16 | Tourism | 31 | Optional |

The remaining 30 subjects (Gender, Climate, Geography, SDGs, Construction, etc.) are off-scope for the econ-cluster ingest.

### Confirmed headline var_ids

| Cell | imdr_code (target) | sub_id | var_id | Title | Unit | Notes |
|---|---|:---:|:---:|---|---|---|
| 2.4 | `BPS.CPI.HEADLINE.LEVEL.ID` | 3 | **2** | Consumer Price Index (General) | — (Tidak Ada Satuan) | At city level — filter `vervar_id=9999` for INDONESIA aggregate |
| 2.4 | `BPS.CPI.HEADLINE.MOM.ID` | 3 | **1** | Month-to-Month Inflation | Persen | Filter `vervar_id=9999` |
| 2.4 | `BPS.CPI.150KAB.YOY.ID` | 3 | **2249** | Y-on-Y Inflation 150 Regency/City | — | New from 2024 base-year revision |
| 1.4 | `BPS.GDP.GDP.LEVEL.ID` | 11 | **8** | GDP By Industrial Origin | Milyar Rupiah | |
| 1.4 | `BPS.GDP.GDP.YOY.ID` | 11 | **9** | Growth rate of GDP By Industrial Origin | Persen | |
| 1.4 | `BPS.GDP.EXPEND.YOY.ID` | 169 | **108** | Growth Rate of GDP at Constant Prices by Expenditure | Persen | Demand-side |
| 2.2 | `BPS.PPI.TOTAL.LEVEL.ID` | 36 | **369** | Producer Price Index (2010=100) | — | |
| 2.2 | `BPS.PPI.TOTAL.QOQ.ID` | 36 | **378** | PPI QoQ | Persen | |
| 2.2 | `BPS.PPI.TOTAL.YOY.ID` | 36 | **380** | PPI YoY | — | |
| 2.2 | `BPS.WPI.TOTAL.LEVEL.ID` | 20 | **24** | Wholesale Price Index | — | |
| 1.4 | `BPS.LABOUR.UE_RATE.LEVEL.ID` | 6 | **520** | Open Unemployment Rate 15+ | — | Sakernas, semi-annual |
| 1.3 | `BPS.TRADE.EXPORT.USD.ID` | 8 | **196** | Value of Exports | Juta US$ | Customs basis |
| 1.3 | `BPS.TRADE.IMPORT.USD.ID` | 8 | **497** | Value of Imports | Juta US$ | Customs basis |
| 1.1 | `BPS.SENTIMENT.ITB_ITK.LEVEL.ID` | 25 | **43** | ITB + ITK (Business + Consumer Tendency) | — | Combined index — only sentiment series at BPS |
| 1.1 | `BPS.FTOT.LEVEL.ID` | 22 | **10** | Farmer Terms of Trade by Province | — | NTP — rural-income proxy |

### Composite-key parsing gotcha — RESOLVED

The `?model=data` response's `datacontent` dict keys concatenate
`{vervar}{var}{turvar}{tahun}{turtahun}` **with each ID written in its
natural decimal width — no leading-zero padding**. Sample key
`9471201199` decomposes as `9471|2|0|119|9` for city Jayapura (vervar
9471) × CPI level (var 2) × no derived cut (turvar 0) × year-bucket 2019
(tahun 119) × September (turtahun 9).

A naive "split by max-width" parser fails for ~30% of variables. The
correct approach (now in `_bps_http.parse_datacontent`) is to enumerate
the cartesian product of the four axis catalogues returned in the same
payload, build a reverse `concatenated_str → tuple` map, and look up
each `datacontent` key. Even a deep cut (514 regencies × 13 months × 5
years × multiple turvars) is ~35k tuples — trivial to enumerate.

Validated against 3 variables with different ID-width regimes:

| Var | vervar IDs | Result |
|---|---|---|
| 2 (CPI level)  | 4-digit city codes incl. 9999 INDONESIA | 1,992 rows ✅ |
| 1 (M-to-M)     | 4-digit city codes incl. 9999 INDONESIA | 2,567 rows ✅ |
| 2249 (150-city YoY) | 1-3 digit codes (1-152, new schema) | 2,567 rows ✅ |

If any future variable returns a key that doesn't map cleanly,
parse_datacontent raises `RuntimeError` rather than silently emitting
wrong rows.

### Other gotchas observed

1. **`/v1/api/domain` is a distinct sub-path** — does NOT accept
   `?model=domain`. Hitting `/list?model=domain` returns
   `"Parameter Domain is Missing."`. Documented in
   [`../bps_api_reference.md`](../bps_api_reference.md#endpoint-families).
2. **`turvar` values are sometimes serialised as strings** (`"0"`) not
   ints. Parser coerces with `int()`.
3. **`per_page` is fixed at 10** regardless of request. Use the
   `iter_list_pages` paginator or `nopage=1` (where supported).
4. **150-city CPI is a 2024 revision** of the previous 90-city series.
   For pre-2024 history use var_id=1709 (CPI of 90 City — General). The
   bases also changed (2007=100 → 2012=100 → 2018=100 → 2022=100).
5. **`th` parameter caps at 3 years per request** — undocumented in the
   official spec but enforced live. Use `bps_fetch_data_chunked()` from
   `_bps_http.py` which auto-splits multi-year requests.
6. **National-rollup vervar code is NOT stable across base-year revisions.**
   - var=2 / var=1709 (pre-2024 CPI series) → `vervar_id=9999` = INDONESIA
   - var=2245 (2024+ 150-kab/kota CPI) → `vervar_id=151` = INDONESIA
   The 2024 base revision renumbered the geographic axis (150 kab/kota +
   1 national rollup, indexed 1-151). **Always auto-detect the national
   row by `vervar_label == "INDONESIA"`** rather than hard-coding 9999.
   Other subjects may have similar quirks for newly-rebased series.

### Phase C fetchers — shipped 2026-06-08

Five fetchers shipped, **23 indicators × 2,599 observations** total, all
written to
[`playground/econ/bps/sample_output/{YYYY}/{MM}/{DD}/`](../../../../playground/econ/bps/sample_output/).

#### CPI — [`fetch_cpi.py`](../../../../playground/econ/bps/fetch_cpi.py)

| imdr_code | n_obs | Window | Source var |
|---|---:|---|:---:|
| `BPS.CPI.HEADLINE.MOM.ID` | 569 | 1979-01 → 2026-05 | var=1 (continuous across rebases) |
| `BPS.CPI.HEADLINE_PRE2020.LEVEL.ID` | 492 | 1979-01 → 2019-12 | var=2 |
| `BPS.CPI.HEADLINE_90CITY.LEVEL.ID` | 48 | 2020-01 → 2023-12 | var=1709 (2018=100 base) |
| `BPS.CPI.HEADLINE_150KAB.LEVEL.ID` | 29 | 2024-01 → 2026-05 | var=2245 (2022=100 base) |

3 level series + 1 continuous MoM rate. **1,138 obs.** Splice in analytics
(distinct base years per level series). Auto-detects national rollup by
`vervar_label == "INDONESIA"` (9999 in old series, 151 in new).

#### Trade — [`fetch_trade.py`](../../../../playground/econ/bps/fetch_trade.py)

| imdr_code | n_obs | Window | Source |
|---|---:|---|:---:|
| `BPS.TRADE.EXPORT.TOTAL.USD.ID` | 208 | 2009-01 → 2026-04 | var=196 vervar=9999 (monthly) |
| `BPS.TRADE.IMPORT.TOTAL.USD.ID` | 136 | 2015-01 → 2026-04 | var=497 vervar=9999 (monthly) |
| `BPS.TRADE.EXPORT.OILGAS.USD.ID` | 50 | 1975 → 2024 | var=203 vervar=1 turvar=439 |
| `BPS.TRADE.EXPORT.NONOILGAS.USD.ID` | 50 | 1975 → 2024 | var=203 vervar=2 turvar=439 |
| `BPS.TRADE.IMPORT.OILGAS.USD.ID` | 50 | 1975 → 2024 | var=203 vervar=1 turvar=440 |
| `BPS.TRADE.IMPORT.NONOILGAS.USD.ID` | 50 | 1975 → 2024 | var=203 vervar=2 turvar=440 |

6 indicators, **544 obs.** Monthly totals + annual Migas/Non-Migas decomp.
Trade balance derived in analytics (exports − imports).

#### GDP — [`fetch_gdp.py`](../../../../playground/econ/bps/fetch_gdp.py)

Current 2010-base series only (var=8/9 = old 2000-base 2000-2014; deferred).
All at PRODUK DOMESTIK BRUTO total level.

| imdr_code | n_obs | Window | Source |
|---|---:|---|:---:|
| `BPS.GDP.GDP.LEVEL_REAL.ID` | 65 | 2010-Q1 → 2026-Q1 | var=65 vervar=99003 turvar=237 |
| `BPS.GDP.GDP.LEVEL_NOM.ID` | 65 | 2010-Q1 → 2026-Q1 | var=65 vervar=99003 turvar=238 |
| `BPS.GDP.GDP.YOY.ID` | 61 | 2011-Q1 → 2026-Q1 | var=104 vervar=99003 turvar=5 |
| `BPS.GDP.GDP.QOQ.ID` | 61 | 2011-Q1 → 2026-Q1 | var=104 vervar=99003 turvar=4 |
| `BPS.GDP.DEFLATOR.YOY.ID` | 61 | 2011-Q1 → 2026-Q1 | var=105 vervar=99003 turvar=236 |
| `BPS.GDP.EXP_GDP.YOY.ID` | 65 | 2010-Q1 → 2026-Q1 | var=108 vervar=800 turvar=5 |
| `BPS.GDP.EXP_DEFLATOR.YOY.ID` | 65 | 2010-Q1 → 2026-Q1 | var=109 vervar=800 turvar=236 |

7 indicators, **443 obs.** Quarterly. Supply-side (var=65/104/105) + demand-side
(var=108/109). Latest YoY = 5.61% (2026-Q1). Sectoral / expenditure-component
decomposition is a Phase C2 follow-on.

#### PPI / WPI — [`fetch_ppi.py`](../../../../playground/econ/bps/fetch_ppi.py)

| imdr_code | n_obs | Window | Source |
|---|---:|---|:---:|
| `BPS.PPI.TOTAL.LEVEL.ID` | 56 | 2010-Q1 → 2023-Q4 | var=369 vervar=45 (INDEKS UMUM) |
| `BPS.PPI.TOTAL.QOQ.ID` | 55 | 2010-Q2 → 2023-Q4 | var=378 vervar=45 |
| `BPS.PPI.TOTAL.YOY.ID` | 40 | 2014-Q1 → 2023-Q4 | var=380 vervar=45 |
| `BPS.WPI.TOTAL.LEVEL.ID` | 239 | 2000-01 → 2019-11 | var=24 vervar=90 (Indeks Umum) |

4 indicators, **390 obs.** PPI 2010=100 series stalls at 2023-Q4; WPI at
2019-11. Likely both moved to different var_ids post-base-revision —
Phase C2 follow-on to locate current vars.

#### Labour — [`fetch_labour.py`](../../../../playground/econ/bps/fetch_labour.py)

| imdr_code | n_obs | Window | Cadence | Source |
|---|---:|---|:---:|:---:|
| `BPS.LABOUR.UE_RATE.LEVEL.ID` | 61 | 1986-02 → 2026-02 | SEMIANNUAL | var=543 vervar=9999 |
| `BPS.LABOUR.MIN_WAGE_AVG.IDR.ID` | 23 | 1997 → 2020 | ANNUAL | var=220 vervar=9999 |

2 indicators, **84 obs.** Sakernas semi-annual (Feb + Aug releases). Latest
unemployment 4.68% (Feb 2026). Min wage publication stalls at 2020 — Phase
C2 follow-on. `SEMIANNUAL` added to `schema_prototype.VALID_FREQUENCIES`.

### Phase C totals

| Domain | Fetchers | Indicators | Observations |
|---|:---:|:---:|:---:|
| CPI | 1 | 4 | 1,138 |
| Trade | 1 | 6 | 544 |
| GDP | 1 | 7 | 443 |
| PPI/WPI | 1 | 4 | 390 |
| Labour | 1 | 2 | 84 |
| **TOTAL** | **5** | **23** | **2,599** |

## Build progress

Phase B (discovery): **complete** 2026-06-08.
Phase C (production fetchers, headline-first): **complete** 2026-06-08 — 5 fetchers, 23 indicators × 2,599 obs in playground parquet.

Code review pass 2026-06-08: DRY refactor extracted shared scaffolding to
[`_bps_common.py`](../../../../playground/econ/bps/_bps_common.py)
(`all_th_ids`, `write_parquet`, `summarize`, `cli_main`). Each fetcher now
~80 lines instead of ~150. Smoke-tested all 5 post-refactor with identical
output to pre-refactor.

Next:
- **Phase F — DB load** (the immediate next step per PM review):
  `dim_vendor` migration for BPS + run
  `python -m scripts.migrations.load_econ_indicator_from_playground --vendor BPS`
  to push the 2,599 obs into `econ.fact_indicator`. This flips the 5 ⚠ cells to ✅.
- **Phase C2 — follow-ons** (deferrable):
  - GDP sectoral decomposition (vervar 11000-18000 for var=104)
  - GDP expenditure component decomp (vervar 100-700 for var=108)
  - CPI 7-group breakdown (vars 1890+ at vervar=9999)
  - Current-base PPI/WPI var_ids (PPI stalls 2023-Q4, WPI 2019-11)
  - Full Sakernas (LFPR, employment-by-sector, wage tables)
  - Farmer ToT (var=10), ITB+ITK sentiment (var=43), Retail/IBS/IMK
- **Phase D — BI/SEKI XLSX** (the hard part): unblocks cells 3.2, 3.3, 4.x.

## Cross-refs

- [`../bps_api_reference.md`](../bps_api_reference.md) — durable API reference
- [`../index.md`](../index.md) — country landing
- [`../id_coverage_plan.md`](../id_coverage_plan.md) — cell ↔ var_id mapping
- [`../id_indicator_targets.md`](../id_indicator_targets.md) — concrete shopping list
- Korea analogue: [`../../korea/_playground/bop.md`](../../korea/_playground/bop.md)
