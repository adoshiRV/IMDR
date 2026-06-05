# Korea — Econ Documentation

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
  every cell of the [KR wiring map §7.13](../macro_economy_wiring_map.md#713-south-korea-kr)
  to specific KOSIS `tblId`s with ✅ confirmed / ⚠ candidate / ❓ unknown
  / ❌ KOSIS-absent status, plus a recommended build sequence.
- **[kr_indicator_targets.md](kr_indicator_targets.md)** — concrete
  shopping list of 121 KR economic time series we want in
  `econ.dim_indicator`, with `imdr_code` + `source_code` + category
  + frequency for each. Treats KRW market data (FX, KTB curve, KOSPI)
  as already covered.
- **[korea_indicator_inventory.md](korea_indicator_inventory.md)** —
  **canonical reference**: all 141 Korea rows currently in
  `econ.dim_indicator`, grouped by macro engine (Growth / Inflation /
  External / Policy), with date ranges, frequency, and a one-line
  "why this matters" annotation per indicator. The doc to hand to
  someone asking "what Korea econ data do we have?".
- **[ecos_api_reference.md](ecos_api_reference.md)** — ECOS Open API,
  KOSIS mirror URL pattern, `STAT_CODE` namespaces, and the dual
  ITEM_CODE structure (`BOPF…`/`BOPO…` for Financial Account vs
  short hierarchical codes for Current Account).
- **[_playground/bop.md](_playground/bop.md)** — Balance-of-Payments
  composition under BPM6, with the full Financial-Account item-code
  catalog and the "capital account outflow" decomposition.

## Access paths

| Path | Auth | Speed | Coverage | Status |
|---|---|---|---|---|
| **KOSIS OpenAPI** — `kosis.kr/openapi/Param/...` | KOSIS API key (`IMDR_KOSIS_API_KEY`, free, instant) | Fast (REST) | Full KOSIS catalogue inc. `orgId=301` BOK series | **Live 2026-06-03** |
| **REB R-ONE OpenAPI** — data.go.kr | REB API key (`IMDR_REB_API_KEY`, 32-char hex) | Fast (REST) | 8 weekly housing tables (apt sale + jeonse) back to 2012-05-07 | **Live** |
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
| KR econ indicator shopping list (121 series) | [kr_indicator_targets.md](kr_indicator_targets.md) |
| BPM6 framework + Korea's BoP composition | [_playground/bop.md](_playground/bop.md) |
| Full `STAT_CODE` / `ITEM_CODE` inventory | [ecos_api_reference.md](ecos_api_reference.md) |
| "capital account outflow" series decomposition | [_playground/bop.md#composition](_playground/bop.md#composition) |
| English-UI translation gotcha ("debt" = liabilities) | [ecos_api_reference.md#translation-gotcha](ecos_api_reference.md#translation-gotcha) |

## Policy & fiscal document sources

Time-series APIs above; the table below covers **document-style** sources for Bank of Korea, Ministry of Economy & Finance (MOEF), and National Pension Service. Not `econ.fact_indicator` material — feeds the policy-document / research pipeline.

| Source | URL | Cadence | Notes |
|---|---|:---:|---|
| **BoK Monetary Policy Decision & Opening Remarks** | bok.or.kr/eng/singl/newsDataEng/list.do (search "Monetary Policy Decision") | per meeting | Policy decision text. AJAX listing — search-backed crawl path. |
| **BoK MPC minutes** | (same search hub, kwd "Minutes of the Monetary Policy Board Meeting") | per meeting | Minutes archive. |
| **BoK Korea Economic Outlook** | (same, kwd "Korea Economic Outlook") | quarterly | Forecast revisions. |
| **BoK Monetary Policy Report** | (same, kwd "Monetary Policy Report") | semi-annual | Forecast layer. |
| **BoK Recent Economic Developments** | (same, kwd "Recent Economic Developments") | quarterly | High-freq state-of-economy snapshot. |
| **BoK speeches** | (same, kwd "Speech") | regular | Governor / deputy / board members. |
| **MOEF press releases (RSS)** | english.moef.go.kr/pc/engmosfrss.do?boardCd=N0001 | regular | Cross-cutting fiscal/FX/macro policy. |
| **MOEF budget/fiscal management (RSS)** | english.moef.go.kr/ec/engmosfpolicyrss.do?boardCd=E0002 | event-driven | Supplementary budgets — first-class regime input. |
| **MOEF treasury/debt RSS** | english.moef.go.kr/ec/engmosfpolicyrss.do?boardCd=E0009 | regular | Bond issuance + borrowing plans. |
| **NPS Investment Management** | fund.nps.or.kr/eng/main.do | regular | Pension flows — rates / KRW demand context. |

## Source-agency contact

- **Agency**: Bank of Korea, Balance of Payments Team, Bureau of Economic Statistics
- **Email**: `bokdesb@bok.or.kr`
- **Phone**: Current Account: +82-2-759-4370 · Capital + Financial Account: +82-2-759-4333
- **Legal authority**: Article 86, Bank of Korea Act · Statistics Korea Approval No. 301008

## BPM6 → BPM7 transition

BOK is actively reviewing migration to **BPM7** (IMF released BPM7 in
March 2025). Currently published series are BPM6 (since 2005). Any
production ingest should expect a re-keying when BOK switches over.
