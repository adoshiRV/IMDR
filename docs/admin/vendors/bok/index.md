# Bank of Korea (BOK) — Vendor Documentation

Last updated: 2026-06-03

Korean macroeconomic data source. BOK's Economic Statistics System (ECOS)
is the authoritative publisher of Korea's Balance of Payments, IIP, FX
reserves, customs trade, national accounts, and policy rates. Statistics
Korea (KOSIS) mirrors most BOK series under `orgId=301`.

- **[kosis_openapi_reference.md](kosis_openapi_reference.md)** —
  KOSIS 공유서비스 OpenAPI: endpoints, parameters, error codes,
  TLS 1.2 pinning requirement, 40k-row per-call cap, and the
  catalogue of tables in scope. **Live as of 2026-06-03.**
- **[kosis_kr_coverage_plan.md](kosis_kr_coverage_plan.md)** — maps
  every cell of the [KR wiring map §7.13](../../development/macro_economy_wiring_map.md#713-south-korea-kr)
  to specific KOSIS `tblId`s with ✅ confirmed / ⚠ candidate / ❓ unknown
  / ❌ KOSIS-absent status, plus a recommended build sequence.
- **[ecos_api_reference.md](ecos_api_reference.md)** — ECOS Open API,
  KOSIS mirror URL pattern, `STAT_CODE` namespaces, and the dual
  ITEM_CODE structure (`BOPF…`/`BOPO…` for Financial Account vs
  short hierarchical codes for Current Account).
- **[exploration/bop.md](exploration/bop.md)** — Balance-of-Payments
  composition under BPM6, with the full Financial-Account item-code
  catalog and the "capital account outflow" decomposition.

## Access paths

| Path | Auth | Speed | Coverage | Status |
|---|---|---|---|---|
| **KOSIS OpenAPI** — `kosis.kr/openapi/Param/...` | KOSIS API key (`IMDR_KOSIS_API_KEY`, free, instant) | Fast (REST) | Full KOSIS catalogue inc. `orgId=301` BOK series | **Live 2026-06-03** |
| **FRED mirror** — `KORB6*CXCUM` family | FRED API key | Fast (REST) | Headline + selected sub-aggregates; no full FA decomposition | Live |
| **KOSIS browser download** | None | Slow (Playwright) | Full table including all `BOPF…` line items | Legacy fallback |
| **BOK ECOS Open API** — `ecos.bok.or.kr/api/` | ECOS API key | Fast (REST) | Full | **BLOCKED — registration requires Korean mobile + citizenship** |

`KORB6*CXCUM` series are wired into the FRED ingest at
[`playground/econ/fred/seed.yml`](../../../../playground/econ/fred/seed.yml).
KOSIS Playwright downloader lives at
[`playground/econ/kosis/fetch_bop.py`](../../../../playground/econ/kosis/fetch_bop.py).

## Quick links

| Topic | Doc |
|---|---|
| KOSIS OpenAPI — endpoints, limits, error codes | [kosis_openapi_reference.md](kosis_openapi_reference.md) |
| KR wiring-map cells → KOSIS tblIds | [kosis_kr_coverage_plan.md](kosis_kr_coverage_plan.md) |
| BPM6 framework + Korea's BoP composition | [exploration/bop.md](exploration/bop.md) |
| Full `STAT_CODE` / `ITEM_CODE` inventory | [ecos_api_reference.md](ecos_api_reference.md) |
| "capital account outflow" series decomposition | [exploration/bop.md#composition](exploration/bop.md#composition) |
| English-UI translation gotcha ("debt" = liabilities) | [ecos_api_reference.md#translation-gotcha](ecos_api_reference.md#translation-gotcha) |

## Source-agency contact

- **Agency**: Bank of Korea, Balance of Payments Team, Bureau of Economic Statistics
- **Email**: `bokdesb@bok.or.kr`
- **Phone**: Current Account: +82-2-759-4370 · Capital + Financial Account: +82-2-759-4333
- **Legal authority**: Article 86, Bank of Korea Act · Statistics Korea Approval No. 301008

## BPM6 → BPM7 transition

BOK is actively reviewing migration to **BPM7** (IMF released BPM7 in
March 2025). Currently published series are BPM6 (since 2005). Any
production ingest should expect a re-keying when BOK switches over.
