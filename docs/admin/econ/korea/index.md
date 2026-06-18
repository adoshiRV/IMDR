# Korea — Econ Documentation

Last updated: 2026-06-16

> **Current corpus state (2026-06-16):**
> - **Track A (`econ.fact_indicator`)** — **173 indicators / ~53,757 obs**. KOSIS depth: GDP 1961→ (65yr), BoP 1980→ (45yr), CPI/retail/IIP 2000→. **BIS.POLICY_RATE.KR** (BOK Base Rate, daily 1999→, id 1435) added 2026-06-16 — cell 4.4 Policy Reaction now has the real Base Rate. FRED Discount Rate deactivated (migration 102). See [korea_prod_pipeline.md](korea_prod_pipeline.md) Track A section.
> - **Track B (`research.dim_report` + Qdrant + SharePoint)** — **2,135 govt policy filings** across 8 agencies. MOEF 2009→ (17yr), FSC 2020→ (6yr), FSS 2024→, BoK 2025-04→ (14mo, deep-backfill to 2011 pending decision). Backfill landed 2026-06-11; tracker at [`../../development/kr_govt_filings.md`](../../development/kr_govt_filings.md).

Korean macroeconomic data source. BOK's Economic Statistics System (ECOS)
is the authoritative publisher of Korea's Balance of Payments, IIP, FX
reserves, customs trade, national accounts, and policy rates. Statistics
Korea (KOSIS) mirrors most BOK series under `orgId=301`.

## Production pipeline (canonical as of 2026-06-10)

Korea econ ingest is fully automated in production across **three
cadences** (daily, weekly, monthly). The playground fetchers under
`playground/econ/kosis/` and `playground/econ/reb/` are preserved as
the legacy sandbox but are **not** the canonical path — use the prod
scripts below.

See **[korea_prod_pipeline.md](korea_prod_pipeline.md)** for the full
operations runbook: architecture, on-demand invocation, CLI flags,
data archive layout, idempotency, and failure-mode guide.

**Daily schedule** (`scripts/imdr_daily.py`):

```
python -m scripts.econ.kr.kr_daily
```

Runs govt policy filings ingest (BoK, MOEF, MOTIR, FSC, FSS, KCS, KDI,
MoDS) → `research.dim_report` + Qdrant + SharePoint. Self-contained
filings-aware email on completion (`[IMDR Daily KR] ...`). Wired
2026-06-10. See [`govt_doc_sources.md`](govt_doc_sources.md) for the
inventory + URL recipes.

**Weekly schedule** (`scripts/imdr_weekly.py`, pipeline #3):

```
python -m scripts.econ.kr.kr_weekly
```

Fans out to 2 fetchers: `scripts.econ.kr.reb.reb_housing` (REB R-ONE direct,
4 housing series) + `scripts.econ.kr.kosis.kosis_reb_housing` (KOSIS mirror,
4 housing series). Total ~22 s.

**Monthly schedule** (`scripts/imdr_monthly.py`, pipeline #1):

```
python -m scripts.econ.kr.kr_monthly
```

Fans out to 19 KOSIS fetchers + 1 BIS fetcher (`scripts.econ.kr.bis.bis_korea` — BOK Base Rate) covering all monthly/quarterly/annual/daily cadence topics. Total ~170 s. Sequential (KOSIS rate-limits concurrent connections). `frequency_scope` extended to DAILY 2026-06-16 to cover the BIS policy-rate series.

---

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
  **canonical reference**: all 173 Korea rows currently in
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
| **KOSIS OpenAPI** — `kosis.kr/openapi/Param/...` | KOSIS API key (`IMDR_KOSIS_API_KEY`, free, instant) | Fast (REST) | Full KOSIS catalogue inc. `orgId=301` BOK series | **Production — auto-load via `kr_monthly` (2026-06-05)** |
| **REB R-ONE OpenAPI** — data.go.kr | REB API key (`IMDR_REB_API_KEY`, 32-char hex) | Fast (REST) | 8 weekly housing tables (apt sale + jeonse) back to 2012-05-07 | **Production — auto-load via `kr_weekly` (2026-06-05)** |
| **BIS SDMX** — `WS_CBPOL D.KR` | None (public) | Fast (SDMX-JSON) | BOK Base Rate daily 1999→ (`BIS.POLICY_RATE.KR`, cell 4.4) | **Production — auto-load via `imdr_daily.py` + `kr_monthly` (2026-06-16)** |
| **FRED mirror** — `KORB6*CXCUM` family | FRED API key | Fast (REST) | Headline + selected sub-aggregates; no full FA decomposition; FRED KR Discount Rate deactivated 2026-06-16 | Live (manual load via `load_econ_indicator_from_playground`) |
| **KOSIS browser download** | None | Slow (Playwright) | Full table including all `BOPF…` line items | Legacy fallback (playground only) |
| **BOK ECOS Open API** — `ecos.bok.or.kr/api/` | ECOS API key | Fast (REST) | Full | **BLOCKED — registration requires Korean mobile + citizenship** |

`KORB6*CXCUM` series are wired into the FRED ingest at
[`playground/econ/fred/seed.yml`](../../../../playground/econ/fred/seed.yml).
KOSIS Playwright downloader (legacy) lives at
[`playground/econ/kosis/fetch_bop.py`](../../../../playground/econ/kosis/fetch_bop.py) —
superseded by `scripts/econ/kr/kosis/kosis_bop.py` in production.

## Quick links

| Topic | Doc |
|---|---|
| **Production pipeline ops** — architecture, CLI, failure modes | [korea_prod_pipeline.md](korea_prod_pipeline.md) |
| KOSIS OpenAPI — endpoints, limits, error codes | [kosis_openapi_reference.md](kosis_openapi_reference.md) |
| KR wiring-map cells → KOSIS tblIds | [kosis_kr_coverage_plan.md](kosis_kr_coverage_plan.md) |
| KR econ indicator shopping list (121 series) | [kr_indicator_targets.md](kr_indicator_targets.md) |
| BPM6 framework + Korea's BoP composition | [_playground/bop.md](_playground/bop.md) |
| Full `STAT_CODE` / `ITEM_CODE` inventory | [ecos_api_reference.md](ecos_api_reference.md) |
| "capital account outflow" series decomposition | [_playground/bop.md#composition](_playground/bop.md#composition) |
| English-UI translation gotcha ("debt" = liabilities) | [ecos_api_reference.md#translation-gotcha](ecos_api_reference.md#translation-gotcha) |

## Policy & fiscal document sources

Time-series APIs above; **document-style** sources for Korean ministries,
regulators, central bank, and quasi-govt agencies are catalogued separately
in [**govt_doc_sources.md**](govt_doc_sources.md) — 70+ streams across 10
categories (CB / ministries / regulators / statistical / think-tanks / etc.),
URL recipes proven end-to-end as of 2026-06-10, daily-pull discovery
running in [`playground/econ/kr/govt/`](../../../../playground/econ/kr/govt/).

These feed `research.dim_report` + Qdrant + SharePoint — the same corpus
Mycroft/Lois already pull from for sell-side research. Not
`econ.fact_indicator` material.

Tier-1 streams currently wired into daily discovery (317 baseline items
captured on 2026-06-10, ~9 new items/day expected):

| Vendor | Streams | Cadence | Body type |
|---|---|---|---|
| `bok` | News + Publications (all 8 menus — MPC Decision, MPR, FSR, Issue Notes, OMO, Speeches, etc.) | daily | PDF |
| `moef` | 10 RSS boards — press, budget, treasury_debt, international, tax, … | daily | HTML body (no PDFs) |
| `motir` | Press releases (Trade/Industry/Resources, renamed from MOTIE) | daily | HTML body (PDF blocked) |
| `fsc` | Press releases | weekly cadence, daily polling | PDF + HTML body |
| `fss` | Press releases (financial supervision) | weekly cadence | PDF |
| `kcs` | Customs News + FAQ/Notice | quarterly (stale), live boards TBD | JPG attachments |
| `kdi` | Monthly Economic Trends + Outlook + Bulletin (featured cards) | weekly cadence | PDF via base64 `atch_no` URL |
| **MoDS** (alias `mods`) | KOSTAT/Ministry of Data & Statistics — already in `dim_vendor` (id=24) | TBD | TBD |
| **NPS** | Investment Management (pension flows) | TBD | TBD |

## Source-agency contact

- **Agency**: Bank of Korea, Balance of Payments Team, Bureau of Economic Statistics
- **Email**: `bokdesb@bok.or.kr`
- **Phone**: Current Account: +82-2-759-4370 · Capital + Financial Account: +82-2-759-4333
- **Legal authority**: Article 86, Bank of Korea Act · Statistics Korea Approval No. 301008

## BPM6 → BPM7 transition

BOK is actively reviewing migration to **BPM7** (IMF released BPM7 in
March 2025). Currently published series are BPM6 (since 2005). Any
production ingest should expect a re-keying when BOK switches over.
