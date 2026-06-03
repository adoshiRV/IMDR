# KOSIS OpenAPI — Reference

Last updated: 2026-06-03

KOSIS (Statistics Korea — 통계청) operates the **KOSIS 공유서비스 OpenAPI**, a
REST/JSON gateway over the full National Statistical Information System.
It mirrors the data the [browser-rendered statHtml.do](ecos_api_reference.md)
path serves, but as machine-readable JSON/XML/SDMX with no Playwright
session required.

This doc captures access, limits, endpoints, error codes, and data scope.
Discovery and smoke-test data here was confirmed 2026-06-03 against the
production endpoint.

## Status — capability upgrade

| Path | Auth | Speed | Coverage | Status |
|---|---|---|---|---|
| **KOSIS OpenAPI (this doc)** | API key (free, instant) | Fast (REST) | Full KOSIS catalogue inc. BOK `orgId=301` | **Live as of 2026-06-03** |
| KOSIS browser download via Playwright | None | Slow | Same coverage | Legacy fallback |
| BOK ECOS Open API | ECOS key (Korean mobile + citizenship) | Fast | Full BOK series | Blocked for IMDR |
| FRED mirror | FRED key | Fast | Headline subset, ~6–12 mo lag | Live, complementary |

The OpenAPI **replaces the Playwright path** for any series KOSIS exposes.
Keep the browser path for download-only views or oversized result sets
(>40,000 rows per call — see limits).

## Authentication

| Item | Value |
|---|---|
| Key env var | `IMDR_KOSIS_API_KEY` |
| Username env var | `IMDR_KOSIS_USERNAME` (portal login, not API) |
| Password env var | `IMDR_KOSIS_PASSWORD` (portal login, not API) |
| Base URL env var | `IMDR_KOSIS_URL` = `https://kosis.kr/openapi/Param/statisticsParameterData.do` |
| Param name | `apiKey=` (querystring, plaintext) |
| Key format | base64 of a 32-char hex (e.g. `Njk…MzM=`, length 44) |
| Quota | 1 user → 1 key; same key works across **all** KOSIS API endpoints |
| Activation | Immediate after registration at `https://kosis.kr/openapi/index/index.jsp` |
| IP binding | None — key works from any IP unless restricted in the application form |

## Transport — TLS pinning required

**Force TLS 1.2.** KOSIS edge silently resets TLS 1.3 handshakes from
several corporate networks (including ours). All Python/curl calls must
pin to TLS 1.2 or fail with `ConnectionResetError [WinError 10054]`.

| Client | Working flag |
|---|---|
| `curl` | `--tlsv1.2 --tls-max 1.2` |
| Python `requests` | custom `HTTPAdapter` with `ssl_context.maximum_version = TLSVersion.TLSv1_2` |
| Python `httpx` | `httpx.AsyncClient(verify=ssl_context_tls12)` |

HTTP (port 80) returns a 302 → HTTPS, and KOSIS posted a 2026-02-05 notice
deprecating plaintext HTTP. Always use HTTPS.

## Rate limits and quotas

Compiled from KOSIS notices and our own probe burst (5 sequential calls,
all `<0.5s`, no throttle response):

| Limit | Value | Source |
|---|---|---|
| **Per-minute call rate** | Throttled (exact number unpublished) | KOSIS notice dated 2026-02-05 |
| **Per-day call quota** | No documented hard cap | KOSIS dev manual v1.0 |
| **Records per single call** | **40,000** | KOSIS dev manual v1.0 |
| **Concurrent connections** | Not documented | — |

**Practical guidance**: For tables that exceed 40k rows on a single
`itmId` × `objL1` cross, either page via `prdInterval` (period stride) or
use the large-volume endpoint (`statisticsBigData.do`, requires separate
catalogue subscription per table). Keep ingest call cadence ≤ ~30 calls/min
until the throttle threshold is published.

If you hit the throttle, expect a TLS reset (not a 429) — KOSIS drops
the connection rather than returning JSON.

## Endpoint catalogue

All confirmed reachable with our key over TLS 1.2 on 2026-06-03. Paths
are relative to `https://kosis.kr/openapi/`.

| Endpoint | Path | Purpose |
|---|---|---|
| **Statistics data** | `Param/statisticsParameterData.do` | The workhorse — fetch values for a specific `(orgId, tblId, itmId, objL1…)` cross |
| **Statistics list** | `statisticsList.do` | Catalogue browse (org / topic / theme trees) |
| **Statistics big-data** | `statisticsBigData.do` | Large-volume tables (per-table subscription) |
| **Statistics explanation** | `statisticsExplanation.do` | Metadata, methodology notes, units |
| **Statistics table explanation** | `statisticsTableExplanation.do` | Table-level definitions, source agency, update cadence |
| **Integrated search** | `statisticsSearch.do` | Free-text search across the catalogue |
| **Key indicators** | `statisticsBigData/statisticsBigDataList.do` | Curated key-indicator set |

Output formats: `format=json|xml|sdmx|xls` plus `jsonVD=Y` (verbose
field-named JSON) vs `jsonVD=N` (compact positional JSON).

### `statisticsParameterData.do` — required parameters

| Param | Required | Example | Notes |
|---|---|---|---|
| `method` | yes | `getList` | Only documented value |
| `apiKey` | yes | (env) | URL-encoded base64 key |
| `orgId` | yes | `101` (Stats Korea), `301` (BOK) | Source agency code |
| `tblId` | yes | `DT_1B040A3` | Table ID — `DT_` prefix mirrors ECOS `STAT_CODE` |
| `itmId` | yes | `T20`, `BOPF100000` | Item code — schema differs per table (see [ecos_api_reference.md](ecos_api_reference.md) for BoP) |
| `objL1` | yes | `00`, `8500`, `ALL` | First classification axis; `ALL` works on some tables, fails (`err=21`) on others |
| `objL2`…`objL8` | when used | `00` | Second+ classification axes if table is multi-dim |
| `prdSe` | yes | `Y`/`Q`/`M`/`D` | Period cycle |
| `newEstPrdCnt` | one of | `3` | Last N periods |
| `startPrdDe` + `endPrdDe` | one of | `202301`/`202512` | Explicit period range |
| `prdInterval` | optional | `1` | Stride |
| `format` | optional | `json` | Default `xml` |
| `jsonVD` | optional | `Y` | Field-named JSON |

## Error codes

Confirmed from the wire on 2026-06-03:

| `err` | `errMsg` (Korean) | Meaning | Common cause |
|---|---|---|---|
| `11` | 유효하지 않은 인증KEY입니다 | Invalid auth key | Key not yet approved, wrong key, or typo |
| `20` | 필수요청변수값이 누락되었습니다 | Required parameter missing | One of `orgId`/`tblId`/`itmId`/`objL1`/`prdSe` not supplied |
| `21` | 잘못된 요청 변수를 호출 하였습니다 | Invalid request parameter | Wrong code for the table (e.g. `objL1=ALL` on a table that requires explicit code) |
| `21` | 해당 통계표가 존재하지 않습니다 | Statistical table does not exist | Wrong `(orgId, tblId)` pair — table not on that org, or doesn't exist |
| `30` | 데이터가 존재하지 않습니다 | No data exists | Period range outside the series window, or item/object cross is empty |

Additional codes documented in the KOSIS dev manual but not seen on our
wire yet: `01` (success/system error variants), `10` (maintenance),
`22` (param format), `99` (system error). Treat any non-list JSON
response with `err` field as a failure and log `errMsg`.

Note: **all errors return HTTP 200** with a JSON `{err, errMsg}` body.
Do not rely on HTTP status to detect failures.

## Data scope

KOSIS aggregates statistics from every Korean public agency that
publishes through the national portal. The OpenAPI exposes essentially
the full catalogue. Top-level organisations relevant to IMDR:

| `orgId` | Agency | Coverage |
|---|---|---|
| **101** | Statistics Korea (통계청) | Population, CPI/PPI, employment, household income, retail trade, industrial production |
| **301** | Bank of Korea (한국은행) | Balance of Payments, IIP, FX reserves, M1/M2, policy rate, banking statistics |
| **343** | Korea Customs Service | Customs-basis trade (≠ BoP-basis goods trade) |
| **133** | Ministry of Economy & Finance | Fiscal data |
| **350** | Korea Exchange (KRX) | Listed-company aggregates |
| **194** | Ministry of Employment | Wage / employment surveys |

A full org enumeration is available via `statisticsList.do?method=getOrgList`
(intermittent — TLS reset risk; retry).

### Tables already in scope for IMDR

| Series | `orgId` | `tblId` | Cadence | Use |
|---|---|---|---|---|
| Balance of Payments (master) | 301 | `DT_301Y013` | Monthly | BoP / capital-flow analysis — see [exploration/bop.md](exploration/bop.md) |
| BoP — SA Current Account | 301 | `DT_301Y017` | Monthly | Seasonally adjusted CA |
| BoP — regional CA (Asia/EU) | 301 | `DT_301Y015` / `DT_301Y016` | Monthly | Regional decomposition |
| IIP / External Debt | 301 | `DT_311Y…` family | Quarterly | Stock counterparts to BoP flows |
| FX Reserves | 301 | `DT_732Y…` family | Monthly | Stock — counterpart to Reserve Assets flow |
| Customs trade | 343 | `DT_901Y…` family | Monthly | Customs-basis goods trade |
| Population (admin region) | 101 | `DT_1B040A3` | Annual | Smoke-test table — confirmed working |

The KOSIS `tblId` is the ECOS `STAT_CODE` with `DT_` prefix
(e.g. ECOS `301Y013` ↔ KOSIS `DT_301Y013`). All ECOS-side codes
documented in [ecos_api_reference.md](ecos_api_reference.md) work
1:1 against the KOSIS OpenAPI.

## Smoke-test response shape

Sample for `orgId=101 / tblId=DT_1B040A3 / itmId=T20 / objL1=00 /
prdSe=Y / newEstPrdCnt=3`:

```json
[
  {
    "TBL_ID": "DT_1B040A3",
    "TBL_NM": "행정구역(시군구)별 성별 인구수",
    "ORG_ID": "101",
    "ITM_ID": "T20",
    "ITM_NM": "총인구수",
    "ITM_NM_ENG": "Koreans (Total)",
    "C1": "00",
    "C1_NM": "전국",
    "C1_NM_ENG": "Whole country",
    "C1_OBJ_NM": "행정구역(시군구)별",
    "C1_OBJ_NM_ENG": "By Administrative District",
    "PRD_DE": "2025",
    "PRD_SE": "A",
    "DT": "51117378",
    "UNIT_NM": "명",
    "UNIT_NM_ENG": "Person",
    "LST_CHN_DE": "2026-01-05"
  }
]
```

Every row carries Korean **and** English labels (`*_NM_ENG`), original
unit (`UNIT_NM`), the period (`PRD_DE`, `PRD_SE`), and the last-changed
date (`LST_CHN_DE`) — sufficient to drive a fact-table load without
side-channel metadata calls.

## Open questions / TODO

- Per-minute throttle threshold not published — instrument the connector
  to count calls/min and warn before any future ingest crosses 30/min
  until the limit is observed empirically.
- `statisticsBigData.do` requires a per-table subscription in the portal
  (not auto-granted with key issue). Apply per-table if any series
  exceeds the 40k-row cap.
- Cross-org error semantics (`err=21` on BoP probes): the BoP table
  expects specific 4-digit area codes for `objL1`, not the `ALL` shortcut.
  See [exploration/bop.md](exploration/bop.md) for the proper code set.
