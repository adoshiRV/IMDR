# BPS Web API — Reference

Last updated: 2026-06-08

Compiled from the official BPS documentation at
[`https://webapi.bps.go.id/documentation/`](https://webapi.bps.go.id/documentation/)
and confirmed against the smoke-probe at
[`playground/econ/bps/discovery/`](../../../../playground/econ/bps/discovery/).

This is the **technical reference**. For the higher-level "what we're loading from BPS",
see [`index.md`](index.md), [`id_coverage_plan.md`](id_coverage_plan.md), and
[`id_indicator_targets.md`](id_indicator_targets.md).

## Base URL

```
https://webapi.bps.go.id/v1/api/
```

All requests are HTTPS GET. JSON only — no XML mode.

## Authentication

- Free application key (`api_key`), 32-char hex. Register at the developer
  portal linked from the documentation home page.
- Passed as query-string parameter `?key={...}`.
- Newly issued keys carry `status=actif` (active).
- No OAuth, no header-based auth, no per-request signature.
- Each registered email gets 2-3 keys; treat them as semi-disposable.
- Rate limits are **not documented**. The Korea/KOSIS pattern of ~1 req/sec
  is a safe default; treat sustained 429/503 as a request to back off.
- Support: `dataweb@bps.go.id`.

## Endpoint families

There are **three** distinct URL paths — they look similar but the `domain`
endpoint is its own family. Don't unify them into one helper.

| Family | URL | Purpose |
|---|---|---|
| **Domain** | `/v1/api/domain` | Master list of BPS web-domain IDs (national + 34 provinces + ~514 regencies). Distinct sub-path; does NOT accept `?model=...`. |
| **List** | `/v1/api/list` | Catalogue listings (subjects, subcat, variables, units, periods, static tables, press releases, publications, news). Discriminated by `?model=…`. |
| **View** | `/v1/api/view` | Detail/show by ID (single press release, publication, static table, news article). Discriminated by `?model=…`. |
| **Interoperabilitas** | `/v1/api/interoperabilitas/datasource/{sensus,simdasi}/id/{N}/` | Census and SIMDASI services. Out of scope for the econ time-series ingest. |

## Domain catalogue (`/v1/api/domain`)

Returns the list of BPS web-domains. Indonesia national is `domain_id=0000`.

| Param | Required | Allowed values | Notes |
|---|:---:|---|---|
| `type` | ✅ | `all`, `prov`, `kab`, `kabbyprov` | `all` = everything; `prov` = 34 provinces; `kab` = all regencies; `kabbyprov` = regencies under one province (needs `prov`) |
| `prov` | when `type=kabbyprov` | 4-digit province domain ID (e.g. `3100`) | — |
| `key` | ✅ | — | — |

Response shape — `data[1]` is the list of rows:

```json
{
  "status": "OK",
  "data-availability": "available",
  "data": [
    {"page": 1, "pages": 1, "total": 3},
    [
      {"domain_id": "0000", "domain_name": "Pusat", "domain_url": "https://www.bps.go.id"},
      {"domain_id": "1100", "domain_name": "Aceh", "domain_url": "https://aceh.bps.go.id"}
    ]
  ]
}
```

**IMDR use**: the econ ingest only needs `domain_id=0000` (national rollup).
Per-province data is downstream of the macro layer and not in the
[`country_econ_blueprint.md`](../country_econ_blueprint.md) catalogue.

## List endpoint (`/v1/api/list`)

Catalogue listings, discriminated by `?model=…`. All variants share the same
paginated `[meta, rows]` envelope.

### Models

| `model` | Lists | Required params | Optional params |
|---|---|---|---|
| `subcat` | Subject categories (top-level — currently 4 at national level) | `domain`, `key` | `lang`, `page` |
| `subject` | Subjects (currently 52 at national, in 4 subcats) | `domain`, `key` | `subcat`, `lang`, `page` |
| `var` | Variables (datasets) — the **time-series-level catalogue entries** | `domain`, `key` | `subject`, `year`, `area`, `vervar`, `lang`, `page` |
| `vervar` | Vertical variables (typically the geographic cut: 9999 = INDONESIA, 11 = Aceh, …) | `domain`, `key` | `var`, `lang`, `page` |
| `turvar` | Derived variables (the "by what" axis — e.g. fuel type, age cohort) | `domain`, `key` | `var`, `group`, `nopage`, `lang`, `page` |
| `th` | Period data (year IDs) — `th_id=117 → 2017`, etc. | `domain`, `key` | `var`, `lang`, `page` |
| `turth` | Derived period data (monthly/quarterly grouping IDs) | `domain`, `key` | `var`, `lang`, `page` |
| `unit` | Unit-of-measure dictionary | `domain`, `key` | `lang`, `page` |
| `statictable` | Pre-built static tables (Excel downloads) | `domain`, `key` | `month`, `year`, `keyword`, `lang`, `page` |
| `pressrelease` | BPS press releases | `domain`, `key` | `lang`, `subject`, `month`, `year`, `keyword`, `page` |
| `publication` | BPS publications | `domain`, `key` | `lang`, `subject`, `month`, `year`, `keyword`, `page` |
| `news` | BPS news | `domain`, `key` | `lang`, `category`, `month`, `year`, `keyword`, `page` |
| `kategorinews` | News categories | `domain`, `key` | `lang`, `page` |
| `subcatcsa` | CSA (Classification of Statistical Activities) subcategories | `domain`, `key` | — |
| `subjectcsa` | CSA subjects | `domain`, `key` | `subcatcsa`, `lang`, `page` |
| `indicator` | Strategic Indicators (`IPM`, `Pertumbuhan Ekonomi`, etc.) | `domain`, `key` | `lang`, `page` |
| `infographic` | Infographics | `domain`, `key` | `lang`, `page` |
| `glosarium` | Glossary terms | `domain`, `key` | `keyword`, `lang`, `page` |
| `sdgs` | SDG indicators | `domain`, `key` | `lang`, `page` |
| `sdds` | SDDS indicators | `domain`, `key` | `lang`, `page` |
| `classification` | Statistical classifications (KBLI, KBKI, KKI, …) | `domain`, `key` | `lang`, `page` |
| `data` | **Data values** — the actual time series. See next section. | `domain`, `var`, `th`, `key` | `turvar`, `vervar`, `turth`, `lang` |

### Paginated envelope

Every `list` response shares this shape:

```json
{
  "status": "OK",
  "data-availability": "available",
  "data": [
    { "page": 1, "pages": 6, "per_page": 10, "count": 10, "total": 52 },
    [ {row 1}, {row 2}, ... ]
  ]
}
```

- `data[0]` is metadata (page, pages, per_page, count, total).
- `data[1]` is the list of rows.
- `per_page` defaults to 10; iterate `page=1..pages` to get everything.
- `nopage=1` (where supported) returns everything in one call.

### Language switch

`lang=ind` (default) returns Indonesian field values; `lang=eng` returns
English. Field **schema** is identical — only `title`, `subcat`,
`sub_name`, etc. change. Smoke-confirmed: `subject` returns 52 rows
in either language.

**Recommendation**: store **both** in the playground sample output for cross-
checking, but use `lang=eng` titles in the `dim_indicator.name` field downstream.
The Indonesian title belongs in `dim_indicator.alt_name` (if we add one) or in
a vendor-specific notes field.

## Data endpoint (`?model=data`)

The single most important endpoint — returns the actual time-series values.

### Parameters

| Param | Required | Allowed values | Notes |
|---|:---:|---|---|
| `model` | ✅ | `data` | Discriminator |
| `domain` | ✅ | 4-digit domain ID, typically `0000` | National rollup |
| `var` | ✅ | Single variable ID (from `model=var`) | One series per request |
| `th` | ✅ | Single period ID (`1`), semicolon-list (`2;3`), or range (`2:6`) | Year IDs from `model=th` |
| `turvar` | ❌ | Derived-variable ID | Cut along the "by what" axis |
| `vervar` | ❌ | Vertical-variable ID | Cut along the geographic axis |
| `turth` | ❌ | Derived-period ID | E.g. `0` = annual, `1` = January, … |
| `key` | ✅ | — | — |
| `lang` | ❌ | `ind`, `eng` | — |

### Response shape

```json
{
  "status": "OK",
  "data-availability": "available",
  "var": [
    {"val": 145, "label": "Persentase Rumah Tangga …",
     "unit": "Persen", "subj": "Lingkungan Hidup", "def": "", "decimal": "", "note": "..."}
  ],
  "turvar": [
    {"val": 289, "label": "Listrik PLN"},
    {"val": 290, "label": "Listrik Non-PLN"}
  ],
  "labelvervar": "Provinsi",
  "vervar": [
    {"val": 9999, "label": "INDONESIA"},
    {"val": 11,   "label": "Aceh"}
  ],
  "tahun":    [{"val": 100, "label": "2000"}, ...],
  "turtahun": [{"val": 0,   "label": "Tahun"}, ...],
  "metadata": { ... },
  "datacontent": {
    "99991452891000": 83.68,
    "11145289100000": 67.31,
    ...
  }
}
```

### CRITICAL: composite-key parsing

The `datacontent` dict keys are a **string concatenation** of five IDs in this order:

```
{vervar}{var}{turvar}{tahun}{turtahun}
```

**Component widths are NOT fixed** across the API — they depend on the
catalogues. For example `"99991452891000"` decomposes as:

| Component | Value | Width |
|---|---|---|
| `vervar`   | `9999` | 4 |
| `var`      | `145`  | 3 |
| `turvar`   | `289`  | 3 |
| `tahun`    | `100`  | 3 |
| `turtahun` | `0`    | 1 |

The correct parsing approach (and the one any IMDR BPS fetcher MUST use):

1. The response's `vervar`, `turvar`, `tahun`, `turtahun` lists give the
   **complete catalogue** of allowed IDs for this `var`.
2. Iterate the `datacontent` keys and **match-from-left** against the longest
   ID in each catalogue, in order: `vervar`, `var`, `turvar`, `tahun`, `turtahun`.
3. Or: precompute the unique width per component from the catalogue
   (max digit-length of all IDs in that catalogue) and split the key by
   those widths — same outcome, faster.

A naive "split at fixed offsets" parser **will silently produce wrong
records** for ~30% of variables, because BPS variable IDs span 1 to 5
digits and turvar IDs can reach 4 digits. This is the BPS analogue of the
KOSIS PRD_DE/ITEM_CODE gotcha — must be tested against ≥3 variables
from different subjects before promoting.

### Time-axis quirks

- **`tahun` lists "year-bucket" IDs**, not actual years. To get the year,
  look up `tahun_id → tahun.label`.
- **`turtahun` is the sub-period** (`0=Tahun`/annual, `1=Januari`, …,
  `12=Desember`, plus quarterly `13=Triw1`, `14=Triw2`, ...). The exact
  catalogue is variable-specific — always read from the response.
- For monthly CPI: `tahun` will give annual buckets, `turtahun` will give
  Jan-Dec; the loader composes `(year, month, 1)` for `dim_period`.
- For quarterly GDP: `tahun` annual + `turtahun` Q1-Q4.
- For daily/weekly series: BPS does NOT publish these — confirm via
  `turtahun` catalogue having only annual/monthly/quarterly cuts.

### Multi-period requests — CAPPED AT 3 YEARS

The `th` parameter accepts `2;3` (semicolon list) or `2:6` (range)
syntax. **But the live API enforces a 3-year cap not documented in the
spec**. Requests spanning more years return:

```
"The maximum allowed number of years for the 'th' parameter is 3.
 You provided N. Please reduce the number of years accordingly."
```

Use ``bps_fetch_data_chunked()`` in
[`playground/econ/bps/_bps_http.py`](../../../../playground/econ/bps/_bps_http.py)
which auto-splits multi-year requests into 3-year chunks and concatenates
the parsed long-format rows. Each chunk costs ~1s under the default
throttle, so a 48-year backfill (~16 chunks) takes ~30 s.

The 10-row default pagination does NOT apply to data responses (the
whole `datacontent` dict comes back at once within each 3-year chunk).
Watch response-size growth: a 3-year × 514-regency × 12-month variable
returns ~18,000 cells per request and is fine; a deeper cut can blow
past a few MB.

## View endpoint (`/v1/api/view`)

For showing a single resource detail. Models:

| `model` | Shows | Required params |
|---|---|---|
| `statictable` | One static table by ID (returns metadata + XLSX URL) | `domain`, `id`, `key` |
| `pressrelease` | One press release by ID | `domain`, `id`, `key` |
| `publication` | One publication by ID | `domain`, `id`, `key` |
| `news` | One news article by ID | `domain`, `id`, `key` |
| `subjectcsa` | One CSA subject detail | `domain`, `id`, `key` |

Out of scope for time-series ingest. The static-table detail endpoint
is useful for historical XLSX harvesting when a dataset has been
discontinued from the dynamic API.

## Pagination strategy

Two patterns we use:

1. **Catalogue browse** (subject, subcat, var, vervar, …): iterate
   `page=1..pages` until `pages == page`. Cache the full catalogue to
   `playground/econ/bps/discovery/catalogue/{model}.json` to avoid
   re-fetching on every dev run.
2. **Big var listing** (`model=var&subject=3` → 130 rows, 13 pages):
   prefer `nopage=1` where supported; otherwise loop.

`per_page` is **always 10**; the API does not honour a request for
larger pages.

## Error model

BPS errors return HTTP **200** with `status=Error` in the body — the
same pattern as KOSIS. Examples observed:

| Error message | Cause |
|---|---|
| `"Parameter Domain is Missing."` | Hitting `/v1/api/list?model=domain` instead of `/v1/api/domain` |
| `"User not found"` | Wrong/expired key |

Always check `payload.get("status") == "OK"` before treating the
response as data. The IMDR helper `playground.econ.bps._bps_http.bps_get`
already raises `RuntimeError` on `status=Error`.

## Worked example — fetching CPI headline

The CPI subject is `sub_id=3` (Inflasi). Walking the full chain:

1. **Subject discovery** → `GET /list?model=subject&domain=0000` → find row
   `{sub_id: 3, title: "Inflasi"}`.
2. **Variable listing** → `GET /list?model=var&domain=0000&subject=3` → 130
   variables; row 1 is `{var_id: 1, title: "Inflasi Bulanan (M-to-M)"}`.
3. **Period catalogue** → `GET /list?model=th&domain=0000&var=1` → year
   IDs available for var 1.
4. **Data fetch** → `GET /list?model=data&domain=0000&var=1&th={recent}`
   → parse `datacontent` against catalogues.

Confirmed CPI var_ids (post-Phase C, 2026-06-08):

| Series | var_id | vervar (INDONESIA) | Coverage |
|---|:---:|:---:|---|
| MoM inflation (continuous) | 1 | 9999 | 1979-01 → present |
| CPI level — pre-2020 series | 2 | 9999 | 1979-01 → 2019-12 |
| CPI level — 90-city (2018=100) | 1709 | 9999 | 2020-01 → 2023-12 |
| CPI level — 150-kab/kota (2022=100) | 2245 | **151** ⚠ | 2024-01 → present |

YoY is derived from level series in analytics — BPS does not publish a
continuous headline national YoY var. See
[`id_coverage_plan.md#24-cpi-pressure`](id_coverage_plan.md#24-cpi-pressure)
for the full Phase C var_id map across CPI / GDP / trade / PPI / labour.

## What lives where in the BPS catalogue (post-2026-06-08 probe)

| Subject | `sub_id` | Variables (n) | Notes |
|---|:---:|:---:|---|
| Inflasi (CPI) | 3 | ~130 | Headline + MoM/YoY + by-group + city-level |
| Kependudukan (Population) | 12 | ~25 | Census-derived; mostly stock + projections |
| Gender | 40 | TBD | Out-of-scope for econ ingest |
| Climate | 151 | TBD | Out-of-scope |
| _… 48 other subjects_ | _various_ | _TBD_ | To be enumerated in Phase B catalogue dump |

A complete catalogue dump lands at
`playground/econ/bps/discovery/catalogue/subjects.json` after the next
discovery pass.

## Cross-refs

- [`index.md`](index.md) — landing page, BPS registration steps, access paths
- [`id_coverage_plan.md`](id_coverage_plan.md) — cell-to-`var_id` mapping
- [`id_indicator_targets.md`](id_indicator_targets.md) — concrete `imdr_code` shopping list
- [`../korea/kosis_openapi_reference.md`](../korea/kosis_openapi_reference.md) — KOSIS analogue (worked example)
- [`../korea/ecos_api_reference.md`](../korea/ecos_api_reference.md) — ECOS reference (analogous reference shape)
