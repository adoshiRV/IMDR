# Economics Data Ingest

**Canonical doc.** All public economic-data prints — CPI, GDP, labour, balance of payments, central-bank balance sheets, official rates, government-bond auctions and holdings — flow through the schema and pipelines defined here. Schema decisions, source additions, and sign-offs related to economic data live in this file.

- **Date**: 2026-06-19 (India Track A Phase G prod-promotion; prior entry 2026-06-16 BIS KR)
- **Owner**: TBD
- **Status**: **SCHEMA APPLIED + 4 VENDORS LOADED + KOREA + INDONESIA + INDIA IN PRODUCTION** (FRED 173 + HKMA 29 + KOSIS 164 + REB 4 + BIS KR 1 + ID 308 + IN ~1,242 = **~1,921 dim total**). All loaded indicators have observations. Schema migrations 068–073 + 076 + 077 + 078 + 102 + **103** live. **Korea KOSIS + REB ingest is now automated**: 21 prod fetchers under `scripts/econ/kr/` wire into `scripts/imdr_weekly.py` (2 weekly housing fetchers) and `scripts/imdr_monthly.py` (19 KOSIS + 1 BIS). **Indonesia**: 28 prod fetchers at `scripts/econ/id/`; `id_monthly.py` wired into `imdr_monthly.py`; BIS + SRBI also in `imdr_daily.py`. **India (NEW 2026-06-19)**: 15 prod fetchers at `scripts/econ/in/`; cadence-split across **two** orchestrators — `in_daily.py` (frequency_scope=["DAILY"]) + `in_monthly.py` (frequency_scope=["MONTHLY","WEEKLY","DAILY","QUARTERLY","ANNUAL"]) — wired into `scripts/imdr_daily.py:PIPELINES` + `scripts/imdr_monthly.py:PIPELINES` 2026-06-19. (`in_quarterly.py` was created then folded into monthly on 2026-06-19; `imdr_quarterly.py` has no India entry.) rbi_bulletin.py requires headed Chrome (TSPD). Ops runbook: [india/india_prod_pipeline.md](india/india_prod_pipeline.md). **Korea cell 4.4 now has the real BOK Base Rate** (BIS.POLICY_RATE.KR). Remaining vendors (FRED, HKMA) still use the manual `load_econ_indicator_from_playground` path. **Korea wiring map = 16/16 covered** (14 ✅ fully + 1 ⚠ partial 4.3 + 1 parked 3.4).
- **Companion**: [apac_macro_data_gaps.md](apac_macro_data_gaps.md) — what the desk needs and what's already on Citi. This doc covers the **non-Citi public-data** complement.
- **Coverage map**: [macro_economy_wiring_map.md](macro_economy_wiring_map.md) — 16-cluster macro framework (Growth / Inflation / External-FX / Policy Transmission), used as the per-country coverage checklist. Every indicator we ingest should map to at least one cluster; every cluster should have at least one indicator per country we care about.
- **Indicator catalogue**: [country_econ_blueprint.md](country_econ_blueprint.md) — exhaustive country-agnostic indicator catalogue (§1-4, the *what*).
- **Onboarding playbook**: [onboarding_new_country.md](onboarding_new_country.md) — 5-step workflow (fork blueprint → vendor cascade → build order → identity checks → reconcile wiring map). Read first when adding a new country.
- **Source inventories**: `C:\Users\adoshi\Downloads\whitelisted_websites.md` + `AU NZ PUBLIC DATA.xlsx` (Y/N priority flags per series).
- **Supersedes**: ad-hoc planning in `playground/macro/funding/design.md` (sandbox) and the econ-schema questions blocking [IMD-15](https://linear.app/imdr/issue/IMD-15) / [IMD-16](https://linear.app/imdr/issue/IMD-16) / [IMD-17](https://linear.app/imdr/issue/IMD-17). Those tickets reference the old `macro` schema name — they'll need updating to `econ` when the schema lands.

---

## 0. Build status snapshot (2026-06-05)

**Schema live + 4 vendors loaded; Korea coverage 16/16.** As of 2026-06-05:

- `econ` schema applied (migrations 068–073 + 076 + 078)
- **339 indicators / 320,609 observations** in `econ.fact_indicator`
- 4 vendors loaded end-to-end (FRED + HKMA + KOSIS + REB); 4 more have parquet on disk pending DB load
- Loader (`scripts/migrations/load_econ_indicator_from_playground.py`) is vendor-agnostic — `--vendor X` for any source matching `IndicatorRow` / `ObservationRow` shape
- **KOSIS jumped 19 → 164 indicators across this session** (20 fetchers built — CPI, REB housing, PPI, GDP-Q, ToT, Bank Rates, BoP, EAPS Labour, Retail Sales, Fiscal, Trade Prices, Lending, Balance Sheets, Wages, Trade Indices, **M-Aggregates, IIP+Capacity Util, Consumer Survey, BSI, Corporate Debt**). Shared `_kosis_http.py` helper (TLS 1.2 pin + retry + period parser) used by all. **40k-cap solved** via discovery-first + per-cut iteration for any wide tables (used by PPI, Trade Prices, CCI, BSI, Corp Debt). **BoP refactor closed** — `fetch_bop.py` rewritten from Playwright + single-parquet to OpenAPI + dim/fact split.
- **REB R-ONE direct vendor + 4 housing series loaded** — migration 078 added `reb` row to `dbo.dim_vendor`. `.REB_DIRECT` imdr_code suffix lets REB-direct (2012→) and KOSIS-mirror (2021→) coexist for the same 4 housing series. YoY % change reconciles 0 bp across overlap.
- **FRED Korea rates added** — 4 monthly series (Discount Rate / Call Money / 3M Interbank / 10Y Govt) seeded + loaded. **2026-06-16 update**: FRED Discount Rate (`FRED.RATES.KR_DISCOUNT.KR`) was the BOK *discount* rate, not the Base Rate; deactivated is_active=0 via migration 102. Cell 4.4 Policy Reaction is now covered by `BIS.POLICY_RATE.KR` (BIS SDMX WS_CBPOL D.KR, daily, 1999-05-06→present, id 1435). KOSIS confirmed not to carry the BOK Base Rate (KOSIS 금리 branch has deposit/loan rates only; BOK Base Rate lives in ECOS, not mirrored to KOSIS OpenAPI). Fetcher: `scripts/econ/kr/bis/bis_korea.py`, wired into `imdr_daily.py` + `kr_monthly.py` 2026-06-16.

| Source | Path | Parquet | Loaded to DB | Notes |
|---|---|---|---|---|
| **FRED** | `playground/econ/fred/fetch.py` (httpx + dual-key rotation) | ✅ 169 indicators × 81,231 obs | ✅ 169 / 169 / 81,231 obs | 9 countries (US deep + EU/UK/JP/CA/AU/CH/DE/NZ headline via OECD mirror). Phase 1 wiring-map cells: 4 ✅ / 11 ⚠️ / 1 ❌ for US. Connector accepts `IMDR_ECON_FRED_KEY` + `IMDR_ECON_FRED_KEY2` (round-robin per request, halves per-key load); throttle bumped to 0.5s for safety after a 429 storm 2026-06-04 AM. |
| **HKMA** | `playground/econ/hkma/fetch.py` (config-driven, httpx, no auth) | ✅ 29 indicators × 192,083 obs | ✅ 29 / 192,083 | FX rates 1981→today, HIBOR 1996→today, M1/M2/M3 1997→today. v2 (2026-06-03) added 25 series across 6 wiring-map clusters. |
| **Stats NZ (release pages)** | `playground/econ/statsnz/fetch.py` (headless Playwright) | ✅ 301 indicators × 1,622 obs (Mar-2026 CPI release) | ❌ not yet | One-quarter snapshot per release; multi-release backfill loop pending. |
| **RBA — bulletin tables** | discovery samples via WebFetch | ⚠️ 5 CSVs sampled (F1 / F2 / F11.1 / G1 / D3) — no production fetcher yet | ❌ | Akamai bot-protected; WebFetch + headed Playwright both work. |
| **ABS — CPI** | discovery sample only | ⚠️ 1 XLSX format-mapped (~150 series per release) — no production fetcher yet | ❌ | XLSX-with-metadata-sheets pattern. |
| **RBI — DBIE FX reserves** | `playground/econ/rbi/fetch.py` (httpx + static auth headers) | ✅ 5 indicators × 1,305 obs (5y weekly) | ❌ not yet | Plaintext POST. Sum-of-components matches RBI's published total to the dollar. |
| **RBI — Bulletin** | `playground/econ/rbi/fetch_bulletin.py` (headed Playwright + per-table parsers) | ✅ 31 indicators × 168 obs (Table 27 Call Money + Table 19C CPI Combined) | ❌ not yet | Akamai TSPD wall; **headed Chrome required**. 10 more priority tables URL-catalogued, parsers pending. |
| **Korea — MODS press-release PDFs** | `playground/econ/mods/fetch.py` (headless Playwright + in-page `fetch()`) | ✅ 10 CPI PDFs (Sept-2025 → May-2026) on OneDrive | N/A (raw PDFs) | PDF text parsing → `fact_indicator` is a future task. |
| **Korea — KOSIS OpenAPI** | **PROD**: `scripts/econ/kr/kosis/kosis_{topic}.py` × 20 fetchers (all route through `src/imdr/domains/econ/kosis_http.py` for TLS 1.2 pin + retry). Wired into `scripts/imdr_monthly.py`. Playground originals at `playground/econ/kosis/fetch_{topic}.py` preserved as legacy sandbox. | ✅ 164 indicators × 47,748 obs | ✅ 164 / 47,748 — **auto-load via `kr_monthly`** | Production 2026-06-05. Key in `IMDR_KOSIS_API_KEY`. Mirrors BOK ECOS 1:1 via `tblId=DT_{code}`. 20 fetchers: CPI (15 series 2000-01→), PPI (6 series 1990-01→), GDP-Q (24 series 1961-Q1→), ToT (2 series 1988-01→), Bank Rates (6 deposit-side 1996-01→), REB Housing mirror (4 series 2021-07→), BoP (24 series 1980-01→), Labour EAPS (8 series 1999-06→), Retail Sales (14 series 2000-01→), Fiscal (7 annual 2007→), Trade Prices (4 series 1980→), Lending (8 series), Balance Sheets (5 series), Wages (2 annual), Trade Indices (4 monthly), M-Aggregates (M2+Lf), IIP+Capacity Util, Consumer Survey (CCI+15 sub), BSI (Mfg Realised+Outlook), Corp Debt (13 ratios). See §2.6 + [korea_prod_pipeline.md](korea/korea_prod_pipeline.md). |
| **Korea — REB R-ONE direct** | **PROD**: `scripts/econ/kr/reb/reb_housing.py`. Wired into `scripts/imdr_weekly.py` via `kr_weekly`. Playground original at `playground/econ/reb/fetch_housing.py` preserved. | ✅ 4 indicators × 2,928 obs (Apartment Sale + Jeonse × KR_NAT + KR_SEOUL, weekly 2012-05-07→) | ✅ 4 / 2,928 — **auto-load via `kr_weekly`** | Production 2026-06-05. Key `IMDR_REB_API_KEY` via data.go.kr service-id 15134761. Migration 078 added `reb` vendor row. `.REB_DIRECT` imdr_code suffix coexists with KOSIS-mirror rows. Reconciles 0 bp YoY vs KOSIS mirror across 3 anchor weeks. |
| **Korea — BIS CBPOL policy rate** | **PROD**: `scripts/econ/kr/bis/bis_korea.py`. Wired into `scripts/imdr_daily.py:PIPELINES` + `scripts/econ/kr/kr_monthly.py` 2026-06-16. No auth — public BIS SDMX-JSON API. | ✅ 1 indicator × 6,757 obs (`BIS.POLICY_RATE.KR`, id 1435, daily 1999-05-06→present, latest 2.5%) | ✅ — **auto-load via `imdr_daily.py` + `kr_monthly`** | Production 2026-06-16. No key required. Migration 102: deactivated `FRED.RATES.KR_DISCOUNT.KR` (BOK discount rate, NOT Base Rate, flat 1.0%). Same BIS SDMX WS_CBPOL dataflow used for Indonesia (id 600) and India (id 900). Cell 4.4 Policy Reaction for KR. KOSIS confirmed not to expose the BOK Base Rate. |
| **Indonesia — BPS + BI + BIS + DJPPR** | **PROD**: `scripts/econ/{bps,bi,bis,djppr}/` × 28 fetchers. Orchestrator `scripts/econ/id/id_monthly.py` — **wired into `scripts/imdr_monthly.py:PIPELINES` 2026-06-09**. `scripts.econ.id.bis.bis_indonesia` + `scripts.econ.id.bi.bi_srbi` also registered in `scripts/imdr_daily.py:PIPELINES` for same-day capture of event-driven series. Playground originals at `playground/econ/{bps,bi,bis}/` preserved as legacy sandbox. | ✅ **308 indicators × 114,106 obs** (BPS 82 + BI 184 + BIS 6 + DJPPR 36) — **updated 2026-06-10** | ✅ 308 / 114,106 — **auto-load via `id_monthly` in `imdr_monthly.py`** (+ daily via `imdr_daily.py` for BIS + SRBI) | Production 2026-06-09/10. 4 vendors: BPS (key `IMDR_BPS_API_KEY`), BI (no key — XLSX/ZIP/HTML), BIS (no key — public SDMX-JSON), DJPPR (no key — listing API + XLSX/PDF). Migrations 081-085 applied. Phase I 2026-06-10: BI SEKI IV.4 SBN position by holder (19 indicators × 3,630 obs; reuses `bi_seki.py`). Ops: [indonesia/indonesia_prod_pipeline.md](indonesia/indonesia_prod_pipeline.md). |
| **India — IMD + BIS + FAO + RBI + MOSPI + DPIIT + CGA + DGCIS + UPAg** | **PROD**: `scripts/econ/in/{imd,bis,fao,rbi,mospi,dpiit,cga,dgcis,upag}/` × 15 fetchers. **Two** cadence-split orchestrators: `scripts/econ/in/in_daily.py` (frequency_scope=["DAILY"]) + `scripts/econ/in/in_monthly.py` (frequency_scope=["MONTHLY","WEEKLY","DAILY","QUARTERLY","ANNUAL"]). (`in_quarterly.py` was created then folded into monthly 2026-06-19; `imdr_quarterly.py` has no India entry.) **Wired into `scripts/imdr_daily.py:PIPELINES` + `scripts/imdr_monthly.py:PIPELINES` 2026-06-19.** Playground originals at `playground/econ/in/{vendor}/` preserved as legacy sandbox. Library: `src/imdr/domains/econ/mospi.py` + `src/imdr/domains/econ/upag.py`. Migration 103 seeded `upag` vendor in `dbo.dim_vendor` (migration 089 had omitted it — blocker resolved). | ✅ **~1,242 indicators × ~99,810 obs** (DB-verified 2026-06-19; incl. DGCIS 198/31,086 + UPAg AIAPY 324/15,030 + UPAg MSP 28/353 + UPAg IMC 16/128 + RBI Bulletin 23 tables ~478/~1,188 + pre-existing BIS/FRED/DBIE 26/39,569) | ✅ — **auto-load via `in_daily` / `in_monthly`** | Production 2026-06-19. No keys required (MOSPI/DPIIT/CGA/DGCIS/UPAg/FAO/BIS all public; RBI DBIE uses static auth headers). **rbi_bulletin.py requires headed Chrome (TSPD) — monthly orchestrator must run on a display-capable host.** FCNR/NRI T34 live (T34 NRI Deposits: FCNR(B)/NR(E)RA/NRO outstanding+flow, 8 ind). Ops: [india/india_prod_pipeline.md](india/india_prod_pipeline.md). |

Blocked / parked:

| Source | Why | Workaround |
|---|---|---|
| **RBNZ** | Cloudflare "access restricted" denial page from this corp network | Email `Servicedesk@rbnz.govt.nz` for IP whitelisting. NZ macro data via FRED-OECD mirrors in the meantime (stale CPI, monthly govt yield). |
| **Stats NZ ADE API** | Catalogue is demographics-heavy (Census / LEED / HES / income); no CPI / PPI / SPI / labour | Use release-page Playwright scrape (working — see Stats NZ above). |
| **DBIE non-FX endpoints** | SAP BusinessObjects with AES-encrypted reportIds | Use bulletin XLSX path via headed Playwright. |

Queued for exploration:

| Source | URL | Status |
|---|---|---|
| **HK Census & Statistics Department (cnstat)** | `data.gov.hk` | New vendor needed for HK CPI / GDP / unemployment / trade (left half of HK wiring map). HKMA covers right half (FX / rates / banking / reserves) but not real-economy series. |
| **RBI CIMS family** | 10 portals (BoP / FLAIR / SMS / FED / CISBI / FIRMS / etc.) | Migration successor to DBIE. No firm deprecation date. |
| **KOSIS OpenAPI** | `kosis.kr/openapi/Param/statisticsParameterData.do` | **IN PRODUCTION** (2026-06-05). 20 prod fetchers under `scripts/econ/kr/kosis/`; wired into `imdr_monthly.py`. (`playground/econ/kosis/fetch_bop.py` was the first playground fetcher — superseded.) Key in `IMDR_KOSIS_API_KEY`. TLS 1.2 pin + 40k-row cap handled by `src/imdr/domains/econ/kosis_http.py`. Ops: [korea/korea_prod_pipeline.md](korea/korea_prod_pipeline.md). |
| **BOK ECOS direct API** | `ecos.bok.or.kr` | Still blocked (Korean mobile + citizenship required). Use KOSIS mirror instead — KOSIS carries ECOS 1:1 with `tblId = DT_{STAT_CODE}`. |

Tooling built or improved this session:

- `playground/research/portal_explorer.py` — refactored to accept `profile_dir` + `out_dir` kwargs so econ wrappers can reuse it (backwards-compatible with the 10 existing research wrappers).
- `playground/econ/explore_{rbi,mods,kosis}.py` — three econ wrappers around `portal_explorer.explore()`; profile + snapshots land under `playground/econ/{vendor}_explore/`.
- `playground/econ/schema_prototype.py` — `IndicatorRow` / `ObservationRow` dataclasses shared by every econ fetcher (engineer-built earlier; `description` field renamed to `display_name` 2026-06-03 to match `econ.dim_indicator.display_name`).
- **`playground/econ/storage.py`** (new, 2026-06-03) — single source of truth for the raw-artefact storage convention. `econ_sharepoint_path(vendor, release_date, filename)` returns the canonical OneDrive-synced path `{YYYY}/{MM}/{DD}/econ/{vendor}/{filename}`. Every econ fetcher that persists raw files (PDFs, XLSX, CSV releases) routes through this. See §4.4.
- **`playground/econ/mods/fetch.py`** (new, 2026-06-03) — MODS press-release PDF downloader; 3 boards × 10 entries/page × `--max-pages` paginated, dedup-on-disk, manifest parquet per run.
- **`playground/econ/hkma/fetch.py`** (refactored 2026-06-03) — switched from hardcoded 2-endpoint layout to **config-driven dispatch**: `_ENDPOINTS` dict carries `(path, date_field, frequency, field_map)` per endpoint; one generic loop drives any number of endpoints. Same DAILY (`YYYY-MM-DD`) + MONTHLY (`YYYY-MM` → first-of-month) date parsing path. Adding a new HKMA endpoint = 1 dict entry. This pattern transplants cleanly to any other multi-endpoint REST-JSON vendor.
- **`scripts/migrations/load_econ_indicator_from_playground.py`** (new, 2026-06-03) — **vendor-agnostic** loader. Reads latest `{vendor}_*_dim.parquet` + `{vendor}_*_fact.parquet`, resolves 5 FKs against canonical dims, applies translation maps (unit / country / vendor-case), `MERGE INTO dim_indicator` on `(vendor_id, source_code)`, staging-table MERGE into `fact_indicator` on PK. Idempotent; loud abort on FK miss; works for FRED, HKMA today, and any future vendor without code changes.
- `src/imdr/connectors/http.py` — API-key redaction in structured logs (`api_key`, `apikey`, `access_token`, `token`, `secret`, `password` masked); `follow_redirects=True` default.
- `playground/econ/fred/{connector,validate_and_seed,fetch,search}.py` — `seriess` typo fix on FRED `/series` endpoint; rate-limit throttle (≥0.6s); FRED `/series/search` CLI exists at `search.py` (used to discover the right OECD MEI IIP code pattern when v1 guesses 400'd).
- Feedback memories added: [`feedback_js_rendered_dont_bail.md`](../../../../memory/feedback_js_rendered_dont_bail.md), [`feedback_slow_down.md`](../../../../memory/feedback_slow_down.md).

### 0.1 DB stock-take (2026-06-05, post-KOSIS-expansion)

Direct counts from `econ.dim_indicator` + `econ.fact_indicator`. Refresh by running the queries in [`scripts/explore/`](../../../../scripts/explore/) — or copy from this section as a starting point.

**Top-line**

| | |
|---|---|
| Indicators (dim rows) | **370** |
| Observations (fact rows) | **325,579** |
| Vendors loaded | 4 (FRED + HKMA + KOSIS + REB) |
| Countries with ≥1 indicator | 11 |
| Categories used | 15 of 17 (`tourism` + `other` unused) |
| Date range | 1961-01-01 → 2026-06-04 |

**By vendor**

| Vendor | Indicators (dim) | Indicators (with facts) | Observation rows | First obs | Last obs |
|---|---:|---:|---:|---|---|
| HKMA  | 29  | 29  | 192,083 | 1981-01-02 | 2026-06-03 |
| FRED  | 173 | 173 | 82,820  | 1990-01-01 | 2026-06-04 |
| KOSIS | 164 | 164 | 47,748  | 1961-01-01 | 2026-06-01 |
| REB   | 4   | 4   | 2,928   | 2012-05-07 | 2026-06-01 |

**Today's deltas vs 2026-06-04:**

- KOSIS: +114 indicators / +37,071 obs across 13 new fetchers — Korea coverage went 1/16 ✅ → **14/16 ✅** in the wiring map.
- FRED: +4 Korea rate series (INTDSRKRM193N Discount / IRSTCI01KRM156N Call Money / IR3TIB01KRM156N 3M Interbank / IRLTLT01KRM156N 10Y Govt). Originally treated as filling cell 4.4, but INTDSRKRM193N is the BOK *discount* rate not the Base Rate. **2026-06-16**: Discount Rate deactivated (migration 102); cell 4.4 transferred to `BIS.POLICY_RATE.KR` (see BIS entry below).
  - **PPI** (DT_404Y014): 6 series (Total + 5 sectors — Agri / Mining / Mfg / Utilities / Services), monthly, 1990-01 → 2026-04. **40k-cell cap resolved** via discovery-first + per-cut iteration (one call per top-level C1 instead of `obj_l1=ALL`).
  - **GDP Quarterly** (DT_200Y102): 24 series (GDP + 11 components, each × QoQ-SA + YoY), quarterly, 1961-Q1 → 2026-Q1.
  - **Terms of Trade** (DT_403Y005): 2 series (Net Barter + Income ToT, 2020=100), monthly, 1988-01 → 2026-04.
  - **Bank Deposit Rates** (DT_121Y002): 6 series (CD 91d, Time Deposits, Repo, FinDebent, Marketable FI composite, headline ex-debent), monthly, 1996-01 → 2026-04. **NOTE: this is deposit-side rates, NOT the BOK Base Rate.** The BOK Base Rate is confirmed absent from KOSIS (Base Rate lives in ECOS, not mirrored to the KOSIS OpenAPI). Cell 4.4 Policy Reaction is covered by `BIS.POLICY_RATE.KR` (BIS SDMX WS_CBPOL D.KR, wired 2026-06-16).
  - **BoP** (DT_301Y013): 24 series, monthly USD mn, 1980-01 → 2026-03. CA total + 4 balances (Goods / Services / Primary / Secondary income) + 2 goods sub (X/M) + 3 services sub (Transport / Travel / Construction) + 12 FA components (DI/PI/Deriv/OI/Reserves × net/assets/liab) + E&O. Identity check `CA = FA − E&O` holds within ~$100M of rounding. Refactored from earlier Playwright-based `fetch_bop.py`.
  - Shared `_kosis_http.py` helper extracted — TLS 1.2 pin + retry + `parse_kosis_period` for M/Q/A/W cycles. Used by all 7 KOSIS fetchers.
  - Coverage-plan correction: `DT_404Y014` was originally labelled CPI in the coverage plan — it's actually **PPI**. Real CPI lives at KOSTAT `DT_1J22042` (orgId=101, loaded yesterday).
- REB R-ONE direct: **new vendor row** via migration 078. +4 indicators / +2,928 obs (KR_NAT + KR_SEOUL × Sale + Jeonse, weekly 2012-05-07 → 2026-06-01). Same 4 housing concepts as the KOSIS-mirror set but distinguished via `.REB_DIRECT` imdr_code suffix to satisfy the `uq_dim_indicator_imdr_code` constraint. REB-direct provides 11 extra years of history (2012-05 vs KOSIS's 2021-07 floor).
- KOSTAT EAPS Labour + Retail Sales: +22 indicators / +6,288 obs.
  - **Labour** (DT_1DA7001S): 8 series (Population 15+ / Active / Employed / Unemployed / Inactive / LFPR / Unemployment Rate / E-P Ratio), monthly, 1999-06 → 2026-04. Identity check passes (Active + Inactive = Pop15+).
  - **Retail Sales** (DT_1K41013): 14 series — 7 retail types × Value + SA index, monthly. Earliest start 2000-01 for headline categories; discount/duty-free start 2010-01.

**By country** (indicator count)

```
KR 172   US 133   HK 29   NZ 7   UK 6   JP 5   DE 5   EU 5   CA 4   AU 3   CH 2
```

KR jumps from 0 → 141 across three sessions (yesterday: CPI + REB Housing; today round 1: PPI + GDP-Q + ToT + Bank Rates + BoP + REB-direct + EAPS Labour + Retail Sales; today round 2: Fiscal + Trade Prices + FRED Korea rates + Lending + Balance Sheets + Wages + Trade Indices). **KR overtakes the US** as the most-populated country in `econ.dim_indicator`.

**By category** (indicator count, top 10)

```
rates 44 · gdp 51 · cpi 30 · bop 26 · labour 21 · sentiment 17 ·
credit 16 · balance_sheet 14 · fx 13 · cb_balance_sheet 10 · housing 4
```

KR adds (cumulative): cpi +15 (KOSTAT CPI), gdp +24 (BOK GDP-Q), cpi +6 (PPI uses `cpi` category), bop +26 (24 BoP + 2 ToT), rates +6 (Bank Rates), housing +4 (REB).

**By frequency** (rows)

```
DAILY     258,742  (88.9%)  ← UST yields + HIBOR + HKD spot + BEI spreads (mostly HKMA back to 1981)
MONTHLY    16,930  (5.8%)   ← CPI, PPI, ToT, bank rates, employment, IIP, M-aggregates
QUARTERLY   6,936  (2.4%)   ← Real GDP (KR), BoP, household debt-service, ECI wages
WEEKLY      6,972  (2.4%)   ← US Fed BS items, jobless claims, mortgage rates, REB housing
ANNUAL          6           ← FYFSGDA188S US federal deficit % of GDP
```

**Implication for schema decisions**: still 89% DAILY. Indexing `(obs_date, indicator_id)` clustered remains the right call. Columnstore conversion stays deferred (~290k rows still well under the ~50M threshold).

**Known data-quality gaps**:
- ~~3 FRED dim rows had zero observations~~ — **resolved 2026-06-04**.
- ~~KOSIS BoP refactor pending~~ — **resolved 2026-06-05**. `fetch_bop.py` rewritten OpenAPI + dim/fact. 24 indicators × 13,234 obs loaded; CA-FA-E&O identity holds within rounding.
- ~~REB-direct housing not loaded~~ — **resolved 2026-06-05**. Migration 078 added `reb` vendor row; 4 indicators × 2,928 obs loaded with `.REB_DIRECT` imdr_code suffix to coexist with KOSIS-mirror rows. Same 4 series, 11 extra years of history (2012-05 vs 2021-07).

---

## 1. Scope

**In scope** — everything below lands via the schema in §4:

- National statistics offices (ABS, Stats NZ, BLS, ONS, Destatis, etc.).
- Central-bank statistical releases (RBA, RBNZ, Fed, ECB, BoJ, BoK, MAS, RBI, …).
- Debt management offices (AOFM, US Treasury, RBNZ DMO, DMO UK, …).
- Multilateral aggregators (FRED, IMF, World Bank, BIS, OECD, DBnomics).
- Energy / commodity public data where it's macro-relevant (MBIE NZ Energy Quarterly, EIA petroleum reports).

**Out of scope** — these have other homes:

- **Bank research views / trade ideas** (e.g. `NZ_RBNZ_Research_Collation.xlsx` — Bank Views Matrix, Trade Ideas, View-Change Triggers) → research-RAG ingest under `imdr-research`, not here.
- **Anything already on Citi Velocity** — see [apac_macro_data_gaps.md](apac_macro_data_gaps.md). CESI / CITIPAIN / CTOT belong with the Citi pipelines.
- **Single-name / corporate** issuance — out per the standing [relevance filter](../../../../memory/project_research_relevance_filter.md).
- **Market microstructure** (tick / quote / depth) — that's the FX/rates live pipelines, not macro.

---

## 2. Source catalogue

Cadence / format / why for every source we intend to ingest. Priority comes from the desk's Y/N pass on `AU NZ PUBLIC DATA.xlsx`.

### 2.1 Australia

**Status 2026-06-11:** Track A (data series) DB-LIVE manually-loaded — **464 indicators / 397,118 obs**, 16 of 16 wiring-map cells ✅. Phase G prod-promotion pending (scripts/econ/au/{abs,rba,aofm,cotality}/ not yet built; `australia_prod_pipeline.md` not yet drafted). Track B (govt filings) **Phase J PROD-BUILT 2026-06-11** — `scripts/econ/au/govt/` + `scripts/econ/au/au_daily.py` in place; 8 official streams writing to `research.dim_report` + Qdrant + SharePoint; 9 reports / 201 chunks live. Final gate: `scripts/imdr_daily.py:PIPELINES` registration pending OK. See [`australia/australia_govt_prod_pipeline.md`](australia/australia_govt_prod_pipeline.md).

| Source | Cadence | Format | Why we want it |
|---|---|---|---|
| **ABS — CPI** ([url](https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/consumer-price-index-australia)) | Monthly + quarterly | XLSX, Data Explorer | Headline + component CPI, trimmed mean / weighted median, tradables vs non-tradables, capital-city splits. |
| **AOFM — Data Hub** ([url](https://www.aofm.gov.au/data-hub)) | Daily / monthly / per-event | XLSX, CSV | AGS outstanding by tenor, bond/TIB issuance & buybacks, syndication investor breakdowns, non-resident holdings, AGS turnover, **daily yield decomposition + term-premium estimates**, AUD IRS + XCCY swap transactions. |
| **ASX — Bonds + Austraclear** ([url](https://www.asx.com.au/markets/trade-our-cash-market/equity-market-prices/bonds)) | Intraday (delayed) / daily | Web, XLSX, CSV (subscriber) | Exchange-traded AGB prices, AGB yield-curve chart data, AGB ISIN/RIC/BBG cross-ref, Austraclear debt/repo/money-market activity. |
| **RBA — Statistics** ([url](https://www.rba.gov.au/statistics/)) | Daily → annual | XLSX, CSV | OCR, balance sheet (weekly), monetary + financial aggregates, AUD FX + TWI, money-market rates, govt-bond yields, zero-coupon analytical series, household + business finance distributions, payments stats, market-economist forecasts, historical RBA forecasts, Chart Pack. |
| **RBA — Historical Data** ([url](https://www.rba.gov.au/statistics/historical-data.html)) | One-shot | XLSX, CSV | Long-run series: FX since 1969, money-market & govt-bond yields to mid-90s, annual macro/banking to 1949. |

**Skip-list** (flagged N): banknotes/counterfeits, individual-bank assets/liabilities 1991-98, Treasury-bond tender history pre-2006, RMBS pre-2020, retail register buybacks, ATM/RTGS payment stats.

#### 2.1.1 RBA — deep dive (2026-06-02)

**Why we want it:** AUD short rates + govt-bond yields + AUD FX cross to G10 + APAC + monetary aggregates + CPI. The RBA Chart Pack is also useful background.

**What's there:** ~90 statistical tables organised A-J:

| Series | Coverage |
|---|---|
| **A** | RBA balance sheet, FX intervention, banknotes (A1 RBA BS, A3 monetary policy ops, A3.1 AGS holdings, A4-A5 FX intervention) |
| **B** | Banking system A/L, international banking (B1-B20, includes country-level claims and exposures) |
| **C** | Payments system: cards, ATM, RTGS, cheques, NPP, merchant fees |
| **D** | Money + credit aggregates: D1 growth, D2 lending, **D3 monetary aggregates (M1/M3/Broad/MB)**, D4 debt securities, IMF-framework monetary stats |
| **E** | Household balance sheets (E1 ratios, E3-E7 distribution, E13 mortgage payments) |
| **F** | **Interest rates + FX (highest desk relevance)**: F1 money market daily, F2 govt bond yields daily, F3 corporate yields, F4-F8 lending rates, F11.1 daily FX 23 ccys, F15 real FX, F17 zero-coupon analytical |
| **G** | **Inflation**: G1 quarterly CPI, G4 monthly CPI collection, G3 expectations |
| **H** | **Output + labour**: H1 GDP/income, H3 monthly activity, H5 labour force |
| **I** | External: I1 trade + BoP, I2 commodity prices, I4-I5 foreign A/L |
| **J** | Market economist forecasts (J1) |

**URL pattern (confirmed working via WebFetch):**

```
https://www.rba.gov.au/statistics/tables/csv/{code}-data.csv
```

Where `{code}` is lower-case with literal dots (e.g. `a3.2`, `f1.1`, `f11.1`, `g4`).

**Access mechanism:**

- Plain curl → **Akamai 403** on `/statistics/...` paths (root `https://www.rba.gov.au/` works fine)
- WebFetch (headless Chrome under the hood) → ✅ works on both the index page (`/statistics/tables/`) and direct CSV URLs
- Headed Playwright with `channel="chrome"` → expected to work same as WebFetch (untested with persistent profile)
- The CSV URLs themselves return **real CSV** (not HTML-disguised) once you get past the Akamai check — first 10 rows are metadata (Title / Description / Frequency / Type / Units / Source / Publication date / Series ID), then date in column 0 + values across

**Sample CSV format** (from F1 money market, 3,909 daily rows):

```
F1 INTEREST RATES AND YIELDS – MONEY MARKET
Title,Cash Rate Target,...,EOD 1-month BABs/NCDs,...,1-month OIS,...
Description,Cash Rate Target on date,...
Frequency,Daily,as announced,Daily,...
Source,RBA,RBA,RBA,...,ASX,ASX,ASX,FENICS,FENICS,FENICS,RBA,RBA,RBA
Publication date,02-Jun-2026,02-Jun-2026,...
Series ID,FIRMMCRTD,FIRMMCCRT,...,FIRMMBAB30D,...,FIRMMOIS1D,...
04-Jan-2011,4.75,,4.75,,,,,100.000000,4.83,4.97,5.14,4.75,4.79,4.86,4.81,4.84
...
```

**Working integration:** none yet (production fetcher pending). 5 CSVs sampled via WebFetch live at `playground/econ/rba/discovery/samples/`:

| Code | Series | Rows | Notes |
|---|---|---|---|
| F1 | Money market interest rates | 17 series × 3,909 daily | OIS, BABs, T-Notes, Cash Rate Target |
| F2 | Govt bond yields | 5 series × ~3,300 daily | 2Y/3Y/5Y/10Y + indexed |
| F11.1 | FX rates daily 2023+ | 23 currency pairs × ~600 daily | AUD vs USD/JPY/EUR/CNY/INR/THB/NZD/TWD/MYR/IDR/VND/AED/PGK/HKD/CAD/ZAR/CHF/PHP/SDR/TWI |
| G1 | CPI quarterly | 20 series × ~140 quarterly | Headline + tradables/non-tradables + trimmed mean + weighted median; YoY + QoQ |
| D3 | Monetary aggregates | 14 series × monthly back to 1959 | M1 / M3 / Broad / Money Base (original + SA) |

**Mistakes we made / things we tried:**

- ❌ **Assumed XLSX**: the first engineer's `fetch.py` hardcoded `/statistics/tables/f1.xlsx` URLs. RBA serves these as CSV, not XLSX, and the path is `/statistics/tables/csv/{code}-data.csv` not `/statistics/tables/{code}.xlsx`. 404 across the board.
- ❌ **Curl with browser User-Agent**: still 403 on `/statistics/` even with full Chrome headers. Akamai bot-scoring this network.
- ❌ **Plain Playwright headless on `/statistics/tables/`**: also 403.
- ✅ **WebFetch worked first try** on the index page (gave full inventory of 90+ tables) and on the data CSVs themselves.

**Open gaps / TODO:**

- Write proper RBA fetcher (`playground/econ/rba/fetch.py` rewrite — current one is broken / placeholder).
- Confirm headed Playwright with `channel="chrome"` + persistent profile works the same as WebFetch for CSV downloads (it should, but not yet tested).
- Per-table parsers: F1 / F2 / F11.1 / G1 / D3 are the desk-priority subset; structure is consistent (multi-row header + Series ID + date-indexed data).
- Cross-reference vs `mitcda/raustats` (R package) for stable URL patterns and series-ID conventions.

**Reachability:** RBA root `https://www.rba.gov.au/` returns 200 to curl. Deep paths (`/statistics/tables/`) are Akamai-protected. **No corp-network block** — both WebFetch and headed Playwright should work.

#### 2.1.2 ABS — deep dive (2026-06-02)

**Why we want it:** AU CPI (headline + trimmed mean + weighted median + capital-city splits + tradables/non-tradables), plus GDP, labour force, BoP — all the ABS time-series products.

**What's there: two access paths**, both reachable from corp network (no anti-bot at file level):

**Path A — release-page XLSX downloads** (proven working):

```
https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/consumer-price-index-australia/{month}-{YYYY}/640103.xlsx
```

The file numbers (`640101`, `640102`, …) are stable per ABS "Time Series Workbook" table number. The release URL slug (`apr-2026`) updates per release.

**Path B — SDMX REST API** (different host than the engineer initially guessed):

```
https://data.api.abs.gov.au/rest/data/{flow_id}/{key}?detail=Full&format=csv
```

(Real host is `data.api.abs.gov.au`, NOT `api.data.abs.gov.au` which the engineer's initial `fetch.py` used → 301 redirect; old `HTTPClient` didn't follow redirects.) Once that's fixed (now default in `HTTPClient`), the SDMX endpoint is reachable but the right series-key structure needs more discovery — all 9 candidate key patterns tried (`1.INX.20.50.Q`, `CPI.INX.10.50.Q`, etc.) returned 404. The dataflows index works:

```
GET https://data.api.abs.gov.au/rest/dataflow/ABS/all/latest
-> 1,223 dataflows enumerated (CPI dataflow confirmed as 'CPI')
```

**Sample format** (Time Series Workbook for CPI Table 3):

```
Sheets: Index | Data1 | Data2 | Data3 | Enquiries

Index sheet (metadata, row 11+):
  Description="Index Numbers; All groups CPI; Australia"
  Series Type=Original  Series ID=A130393720C  Start=2024-04-01

Data1 (Index Numbers, ~50 series):
  Rows 1-10: metadata header (Unit / Series Type / Frequency / Series ID)
  Row 11+: ISO date in col 0, values across

Data2: same shape but values = % change YoY
Data3: same shape but values = % change QoQ
```

ABS Series IDs are stable 11-character codes (e.g. `A130393720C`). Each CPI release workbook contains **~150 distinct series** (subgroups + cities + analytical series, each × 3 measures).

**Working integration:** discovery sample only. Sample XLSX saved at `playground/econ/abs/discovery/samples/640103.xlsx` (CPI Table 3, ~298 KB, downloaded via curl with browser UA).

**Mistakes we made / things we tried:**

- ❌ **Wrong API host**: `api.data.abs.gov.au` (engineer's initial code) returns 301 → `data.api.abs.gov.au:443/rest/data/...`. The old `HTTPClient` didn't follow redirects. Fixed.
- ❌ **SDMX series keys are guesses**: tried 9 candidate patterns for CPI series, all 404. The right key structure is in `/rest/datastructure/ABS/CPI` but needs proper SDMX decoding (which the previous engineer's explore.py didn't do).
- ✅ **XLSX direct download works fine** with browser User-Agent. No bot challenge at file level.

**Open gaps / TODO:**

- Decode the SDMX datastructure to find the correct CPI key format (so we can pull individual series via API rather than parsing XLSX). For now, the XLSX path is sufficient.
- Per-release URL discovery: the release-month slug (`apr-2026`) needs to be looked up dynamically; the CPI release page (`https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/consumer-price-index-australia/latest-release`) links to it.
- Write the production fetcher: download every Time Series Workbook, parse Index sheet for series metadata, parse Data1/Data2/Data3 for values. The XLSX format is stable so this is mostly mechanical.
- ABS optional API key: register at `https://api.gov.au/` if the SDMX path becomes preferred — would live under `IMDR_ECON_ABS_KEY` in `.env`.

**Reachability:** ABS public web + SDMX API both reachable from corp network without anti-bot. Just need `follow_redirects=True` on the HTTP client (now default in `imdr.connectors.http.HTTPClient`).

### 2.2 New Zealand

| Source | Cadence | Format | Why we want it |
|---|---|---|---|
| **Stats NZ — Price indexes** ([url](https://www.stats.govt.nz/topics/price-indexes/)) | Monthly (SPI) + quarterly (CPI, PPI, HLPI, LCI, OTI) | XLSX, CSV, Infoshare | Quarterly CPI + components, monthly SPI (food / fuel / rents / accommodation / airfares), Household Living-Costs PIs, PPI (output + input), CGPI, FEPI, LCI, overseas trade indexes. |
| **RBNZ — Statistics** ([url](https://www.rbnz.govt.nz/statistics)) | Daily → quarterly | XLSX, XLS | OCR, Real TWI, wholesale + retail rates, FX (daily + monthly + historical), monetary aggregates, registered-bank balance sheets, non-bank balance sheets, govt-bond turnover + non-resident holdings, RBNZ balance sheet + OMO, settlement-cash influences, standing facilities, official overseas reserves, NZ IMF position, household balance sheet, business + consumer expectations surveys. |
| **data.govt.nz / MBIE** ([url](https://catalogue.data.govt.nz/)) | Weekly → annual | XLSX, CSV, JSON | Weekly fuel-price monitoring, Energy Quarterly (oil/gas/coal/electricity/prices), petroleum reserves, MRTE tourism estimates, labour-market reports. |

#### 2.2.1 Stats NZ — deep dive (2026-06-03)

**Why we want it:** NZ CPI + PPI + SPI + HLPI + LCI + HLFS unemployment + GDP + BoP + Overseas Trade. Quarterly cadence for most, monthly for SPI + select price indexes.

**Three distinct web properties** (this confused us at first):

| URL | What it is | Has CPI? | API? |
|---|---|---|---|
| `www.stats.govt.nz` | Public release pages — one per quarterly release | ✅ Buried in release pages, JS-rendered | ❌ |
| `infoshare.stats.govt.nz` | Legacy data portal (custom queries, CSV export) | ✅ Canonical historical store | ❌ Web-form only |
| `explore.data.stats.govt.nz` (ADE) | New "Aotearoa Data Explorer" SPA on .Stat Suite | ❌ Census + LEED + HES only | ✅ `api.data.stats.govt.nz/rest/v2` |

**Critical finding**: the ADE API (the one with developer keys) **does NOT carry CPI / PPI / SPI / labour**. Its 911 dataflows are 80% Census, 10% LEED (employer-employee linked), 5% population projections, 5% income/business demography/justice/HES. Macro-desk-relevant data still lives on the legacy release pages or Infoshare.

**Working integration: release-page Playwright scrape**

- Fetcher: `playground/econ/statsnz/fetch.py` (headless Playwright + persistent profile)
- URL pattern for releases:
  ```
  https://www.stats.govt.nz/information-releases/{topic-slug}/
  ```
  e.g. `consumers-price-index-march-2026-quarter`
- Each release page has a "Download data" section with 5-6 CSV/XLSX files. The canonical one for ingest is `*-infoshare-data.csv` (long-format time-series).
- File URL pattern (stable):
  ```
  https://www.stats.govt.nz/assets/Uploads/{Topic-Capitalised}/{Topic-Month-Year-quarter}/Download-data/*.csv
  ```
- Crawl strategy:
  1. Top-level catalogue: `https://www.stats.govt.nz/az-of-information-releases` → per-topic publications URLs
  2. Per-topic publications page: `/publications?categoryFiltersID={N}` → latest release `/information-releases/{slug}/`
  3. Per release: `/Download-data/*.csv`

**Sample on disk** (Mar-2026 CPI release, 6 files captured):

```
playground/econ/statsnz/sample_output/2026/06/02/
  statsnz_20260602_1615_dim.parquet    -- 301 indicators
  statsnz_20260602_1615_fact.parquet   -- 1,622 observations (one quarter snapshot)
```

Each indicator: `STATSNZ.CPI.{slug}.NZ` with `Series_Reference` (e.g. `CPIQ.SAP0200`) as source_code. Mix of `unit=nzd` (weighted-avg prices for items like "Beer bottles", "Whisky") and `unit=index` (CPI subgroup/class/division indexes).

**Limitation**: one release CSV contains only the **latest quarter snapshot** (~1,760 rows for Mar-2026, all `Period=2026.03`). For full history we'd need to loop through past release URLs (each quarterly release back N years), or use Infoshare's bulk-CSV export (web-form only).

**ADE API status** (for completeness):

- Base: `https://api.data.stats.govt.nz/rest/v2`
- Auth: `Ocp-Apim-Subscription-Key: $IMDR_ECON_STATSNZ_PRIMARY_KEY` (Azure APIM standard; secondary key also provisioned)
- 911 dataflows enumerable via `/structure/dataflow/STATSNZ`
- Data: `GET /data/dataflow/STATSNZ/{flow_id}` with `Accept: application/vnd.sdmx.data+csv;version=1.0.0`
- Proven working end-to-end: pulled `HES_HES_001` (Household Expenditure) → 4,172 rows, parquet at `playground/econ/statsnz/sample_output/2026/06/02/statsnz_ade_hes001_*_raw.parquet`
- **Use case for the key**: HES (household-expenditure breakdowns for CPI-weight context), LEED (employment patterns), Census aggregates — none of which the macro desk asks for directly. Park the key, use it when those datasets become useful.

**Mistakes we made / things we tried:**

- ❌ **`api.infoshare.stats.govt.nz` was invented**: the original engineer scaffolded `fetch.py` against this hostname. It doesn't resolve (DNS NXDOMAIN). Real ADE host is `api.data.stats.govt.nz` (Azure-hosted).
- ❌ **Static HTTP on release pages**: `httpx.get(...)` returns boilerplate HTML; the file URLs are JavaScript-rendered by the page's Coveo / Sitecore-style search component. No `.csv` URLs in the static HTML.
- ❌ **WebFetch couldn't extract release-page links**: its small-model summary returned the page title only — JS rendering happens but the link extraction model dropped them.
- ❌ **Declared "blocked" too quickly**: in an earlier pass I said "Stats NZ release pages are JS-rendered, would need Playwright OR registration; defer." The user pushed back ("I can access this easily — use simple headed search, don't overdo the speed"). One Playwright headed pass on the CPI Mar-2026 release page extracted 6 download URLs immediately. → saved as [`feedback_js_rendered_dont_bail.md`](../../../../memory/feedback_js_rendered_dont_bail.md).

**Open gaps / TODO:**

- Extend the release-page scraper to other topics (PPI, SPI, HLPI, LCI, HLFS unemployment, GDP, BoP, Overseas Trade) — each is a different `category_filter` ID; the per-release file pattern is identical.
- Fix the `imdr_code` collision: 1,760 CSV rows → 301 indicators means some series share descriptions and get deduped under one code. Use `source_code` (e.g. `CPIQ.SAP0200`) as the discriminator instead.
- Wire history backfill: loop past release URLs (Dec-2025, Sep-2025, …) to assemble full historical series. Each release's infoshare-data.csv has only the latest quarter.

**Reachability:** all three Stats NZ properties are reachable from this corp network with Chrome User-Agent + follow_redirects=True. No anti-bot challenge observed.

#### 2.2.2 RBNZ — blocked status (2026-06-03)

**Why we want it:** OCR + wholesale rates (B1) + monetary aggregates (B2) + reserves (B3) + NZD/USD/AUD/TWI (EX1) + RBNZ balance sheet — none of which Stats NZ carries.

**Status: BLOCKED at the network layer.** RBNZ serves a Cloudflare denial page from our corp network:

> "Reserve Bank of New Zealand – Te Pūtea Matua
> [Cloudflare CAPTCHA] Verify you are human
> **Your access to the Reserve Bank website has been restricted.**
> If you think you should be able to access our website please email Servicedesk@rbnz.govt.nz."

This is **not** a soft CAPTCHA / JS-challenge that auto-solves. It's an explicit deny page.

**Things we tried:**

- ❌ Plain curl with browser headers → 403 / 200 (with deny HTML) depending on path
- ❌ Headless Playwright (Chromium) on `/statistics` sub-pages → 403 / "Just a moment..." Cloudflare interstitial that never clears
- ❌ Headed Playwright (real Chrome via `channel="chrome"`) → user sees the "Verify you are human" page + "access restricted" message. CAPTCHA solving doesn't help; it's an IP-based deny
- ❌ Persistent profile + cookie warm-up → cookies are never granted because IP is denied upstream

**Recovery path (operational, not technical):** email `Servicedesk@rbnz.govt.nz` requesting IP whitelisting. Draft email saved earlier in the session — request access for programmatic retrieval of public statistics (B1 / B2 / B3 / EX1), explaining the use case and politeness pattern (single-threaded, ≥1s spacing, no NZ public holidays).

**NZ macro fallback while RBNZ is blocked:** added **6 NZ series to the FRED seed** via OECD republishing (`playground/econ/fred/seed.yml`):

| imdr_code | FRED series | What we lose vs RBNZ direct |
|---|---|---|
| `FRED.CPI.HEADLINE_YOY.NZ` | CPALTT01NZQ657N (quarterly) | Stale: last obs 2023-10. RBNZ would be current. |
| `FRED.CPI.INDEX.NZ` | CPALTT01NZQ659N | Same staleness issue. |
| `FRED.CPI.INDEX_ALT.NZ` | NZLCPIALLQINMEI | Slightly fresher (2025-01). |
| `FRED.LABOUR.UNRATE.NZ` | LRUNTTTTNZQ156S | Current; quarterly. |
| `FRED.RATES.GOVT_10Y.NZ` | IRLTLT01NZM156N | Monthly (RBNZ would be daily). |
| `FRED.RATES.IBR_3M.NZ` | IR3TIB01NZM156N | Monthly proxy for OCR / short-end. |

**Reachability** (verified 2026-06-03): `www.rbnz.govt.nz` returns the Cloudflare deny page from rvcapital network IPs. Other networks (mobile hotspot, home) likely work — useful for one-off bootstrapping if needed before service-desk whitelisting lands.

### 2.3 Hong Kong

| Source | Cadence | Format | Why we want it |
|---|---|---|---|
| **HKMA — Daily Monetary Statistics** ([api](https://api.hkma.gov.hk/public/market-data-and-statistics/daily-monetary-statistics/)) | Daily | REST JSON (paginated, no auth) | HKMA Aggregate Balance, Monetary Base, Exchange Fund Bills+Notes outstanding (combined), Certificates of Indebtedness. The Aggregate Balance is the desk's #1 HK liquidity signal. Full daily history from 1997. |

**Known gap**: the public API combines EF Bills + EF Notes outstanding into one series (`outstanding_efbn`). Separating them needs BBG (`HKEFBOUT Index` / `HKEFNOUT Index`) or an HKMA data-services contact.

#### 2.3.1 HKMA — deep dive (2026-06-02)

**Why we want it:** Hong Kong central-bank liquidity signals — the **Aggregate Balance** is the desk's #1 HK liquidity datapoint (peg-band interventions, IPO drainage, USD-rate transmission). Full daily history from 1997.

**What's there:** public REST JSON API, no auth, paginated by `pagesize` + `offset`.

```
https://api.hkma.gov.hk/public/market-data-and-statistics/
  daily-monetary-statistics/{endpoint}?lang=en&pagesize={N}&offset={M}
```

**Working endpoints (confirmed):**

| Endpoint | What it returns | Status |
|---|---|---|
| `daily-figures-interbank-liquidity` | Aggregate Balance (closing) | ✅ Daily, back to 1997 |
| `daily-figures-monetary-base` | Monetary Base + EFB+EFN combined + CI outstanding | ✅ Daily |

**Probe results for separate EFB / EFN endpoints**: 12 URL variants under `daily-monetary-statistics/` all returned HTTP 400. The two confirmed endpoints are the full public surface; everything else is bundled inside them.

**4 indicators wired** (from the 2 endpoints):

```
HKMA.AGG_BAL     -- Aggregate Balance (closing)    [hkd_mn, daily]
HKMA.MON_BASE    -- Monetary Base                  [hkd_mn, daily]
HKMA.EFBN_OUT    -- EF Bills + Notes (combined)    [hkd_mn, daily]
HKMA.CI_OUT      -- Certificates of Indebtedness   [hkd_mn, daily]
```

**Working integration:**

- Fetcher: `playground/econ/hkma/fetch.py` (httpx, no auth, polite 0.2s between pages)
- Sample on disk: `playground/econ/hkma/sample_output/2026/06/02/` — 90 days × 2 series + EFBN/CI extracted as free by-products of the monetary-base call. ~19 KB parquet.
- Verified value (2026-06-01): Aggregate Balance = HKD 53,997 mn (~53.997 bn) — matches HKMA's published number.

**Origin / migration:** the working fetcher started as `playground/macro/funding/fetch_hkma_*.py` (HKD-only scratch from a 2026-05-15 thread). Migrated into `playground/econ/hkma/` during this session; the `playground/macro/funding/` sandbox + `design.md` were deleted. The category set in `schema_prototype.VALID_CATEGORIES` grew to include `liquidity`, `cb_facility`, `cb_balance_sheet`, `instr_outstand` to support the HKMA taxonomy (these now apply to RBI + Fed reserve series too).

**Mistakes we made / things we tried:**

- ❌ Initially scoped this as a separate "macro funding" pipeline. Pivoted to fold it into the main econ ingest after recognising the schema shape was identical (country + indicator + date + value).
- ❌ Tried to probe EFB and EFN endpoints separately (`daily-figures-exchange-fund-bills`, etc.). All 12 URL variants → 400. Combined `outstanding_efbn` is the canonical public series.
- ✅ The pagination wrapper from the original scripts is unchanged; we just renamed and consolidated.

**Open gaps / TODO:**

- Separating EFB from EFN needs Bloomberg tickers (`HKEFBOUT Index` / `HKEFNOUT Index`) or a private HKMA data-services contact. Out of scope for now.
- Hourly intraday data: HKMA publishes intraday Aggregate Balance via a different page. Not investigated.
- Discount Window Borrowing: listed as desired in the original `design.md` but not in the public API endpoints. Confirm via HKMA before continuing to chase.

**Reachability:** HKMA public API reachable from corp network with no anti-bot. Polite throttle of 0.2s between paginated pages is sufficient.

### 2.4 Global / multi-country

| Source | Access | Best use |
|---|---|---|
| **FRED** ([url](https://fred.stlouisfed.org/)) | REST API, free key | US macro (CPI/PCE/GDP/labour/NFCI), Fed RRP/TGA/balance sheet, plus mirrored ECB/BoJ/BoE/IMF series. **Highest-leverage single connector.** |
| **IMF Data** ([url](https://data.imf.org/)) | SDMX + REST | WEO, IFS, BoP, FSI — global macro & cross-country comparability. |
| **World Bank — Open Data + Indicators** ([url](https://data.worldbank.org/)) | REST (no key) | WDI + International Debt Statistics + Global Economic Monitor; ~16k indicators across 45 databases. |
| **BIS — Data Portal** ([url](https://data.bis.org/)) | CSV, SDMX, REST | Credit-to-GDP gaps, debt-service ratios, OTC + FX turnover (Triennial), residential + commercial property prices, central-bank total assets, policy rates. |
| **ECB — Data Portal / SDW** ([url](https://data.ecb.europa.eu/), [API docs](https://data.ecb.europa.eu/help/api/overview)) | CSV, SDMX, REST | HICP + components, MFI lending, euro-area yield curves, ESTR + compounded ESTR, ECB balance sheet, TARGET balances, Consumer Expectations Survey. |
| **OECD — Data Explorer** ([url](https://data-explorer.oecd.org/), [API docs](https://www.oecd.org/en/data/insights/data-explainers/2024/09/api.html)) | SDMX API (XML/JSON/CSV) | DM macro: GDP / CPI / unemployment / Economic Outlook projections, PPPs, foundations-for-growth indicators. |
| **DBnomics** ([url](https://db.nomics.world/)) | REST, free | Convenience router over ECB/IMF/OECD/FRED/national stats — fallback when an upstream API is flaky. |
| **Trading Economics** ([url](https://tradingeconomics.com/)) | REST (paid for full) | Economic calendar + macro API. Cross-check vs Bloomberg calendar. |
| **BOJ — Statistics** ([url](https://www.boj.or.jp/en/statistics/)) | XLSX, CSV | Japan macro + JGB data not on Citi. |
| **BoK — ECOS** ([url](https://ecos.bok.or.kr/)) | REST, free | Korea macro + rates. |
| **MAS — Statistics** ([url](https://www.mas.gov.sg/statistics)) | XLSX | Singapore FX intervention, liquidity ops, money-market rates. |
| **RBI — DBIE** ([url](https://dbie.rbi.org.in/)) | XLSX, REST | India GSecs, banking, FX reserves. |
| **MODS (Korea)** ([url](https://mods.go.kr/anse/)) | TBD | Korean Open Data Statistics portal — pending exploration. |

#### 2.4.1 FRED — deep dive (2026-06-02)

**Why we want it:** single highest-leverage connector. US headline series (CPI / PCE / GDP / labour / NFCI / stress indices / credit OAS / Treasury yields), plus OECD-republished cross-country mirrors (EU / UK / JP / NZ govt yields, headline CPI, rates) when the direct connector for that country is broken or pending.

**Access mechanism:** REST API + free key (registered at `https://fred.stlouisfed.org/docs/api/api_key.html`).

- Base: `https://api.stlouisfed.org/fred/`
- Auth: `?api_key={IMDR_ECON_FRED_KEY}` query param (key lives in `.env`)
- Rate limit: **120 requests/minute** per key. We throttle to ~100/min (0.6s between calls) for safety.
- Response format: JSON. Note FRED's `seriess` typo (one S, double-s) on the `/series` endpoint — caught + fixed (see "Mistakes" below).

**4 endpoints wired** in `playground/econ/fred/connector.py`:

| Endpoint | CLI | Purpose |
|---|---|---|
| `/series/observations` | `fetch.py --since YYYY-MM-DD` | The actual data. Optional `vintage_dates` for revision history. |
| `/releases/dates` | `fetch.py --calendar [--calendar-days N]` | Release calendar — foundation for release-time-scheduling per §4.4. |
| `/series/updates` | `fetch.py --updates-since HH:MM` | Incremental refresh — series updated since timestamp. |
| `/series/search` | `search.py "query" / --tag-names ...` | Discovery — find new series by keyword or tag. |
| `/series` | (via `FredClient.series_info(sid)`) | Series metadata lookup. Used by `validate_and_seed.py` to drop invalid IDs from the seed. |

**Seed**: `playground/econ/fred/seed.yml` — **129 indicators** across the 9 macro-PM morning-screen buckets:

1. **Rates** (29): UST 1M→30Y CMTs, TIPS 5/10/30Y, BEI 5Y/10Y/5y5y, curve slopes T10Y2Y / T10Y3M, EFFR, SOFR, IORB, Fed funds target range, prime
2. **CB balance sheet / facilities** (10): WALCL, TREAST (Tsy holdings), MBST (MBS), RRPONTSYD, WTREGEN (TGA), WLRRAL (foreign repo), DISCBORR, TOTRESNS, WRESBAL, BOGMBASE
3. **CPI/PCE/inflation** (13): headline + core CPI/PCE, shelter, housing, sticky CPI variants (Atlanta), market-based PCE, Michigan 1y expectations
4. **GDP / activity** (10): real + nominal GDP, GDPNow, INDPRO, capacity util, retail control + headline, real DPI, durable goods, capgoods orders, CFNAI, Empire State, Leading Index
5. **Labour** (14): UNRATE, U6, NFP, initial+continuing claims, participation, emp-pop, AHE, ECI, hours, full JOLTS (openings/quits/hires/layoffs)
6. **Financial conditions** (17): NFCI + 3 subindexes, ANFCI, STLFSI, KCFSI, CFSI, HY/IG/BBB/BB OAS, AAA/BAA spreads, mortgage 30/15Y
7. **Risk environment** (12): VIX, VXN, WTI, Brent, natgas, broad/AFE/EM TWI, gold (IQ12260), NBER recession + recession-prob, EPU index
8. **Cross-country (transitional FRED mirrors)** (8): Eurozone HICP + ECB total assets + German 10Y; UK 10Y + BoE bank rate; Japan 10Y; **6 NZ series** (added 2026-06-03 to fill the RBNZ block)
9. **Bank credit / housing** (15): BUSLOANS, REALLN, CONSUMER, TOTBKCR, DPSACBW deposits, HOUST, PERMIT, EXHOSLUSM existing sales, Case-Shiller national + 20-city, SLOOS C&I tightening, total consumer credit

Plus **2 Treasury supply** (GFDEBTN, MTSDS133FMS — federal debt + monthly deficit).

**Working integration:**

- Validator: `playground/econ/fred/validate_and_seed.py` — iterates the candidate list, validates each ID against `/series`, drops invalid/discontinued ones, regenerates `seed.yml` grouped by bucket. Idempotent.
- Fetcher: `playground/econ/fred/fetch.py` — loads seed, pulls observations for every series, writes parquet (dim + fact) to `sample_output/{YYYY}/{MM}/{DD}/`. Polite 0.6s between calls.
- Sample on disk: `fred_20260602_1539_*.parquet` — **129 indicators × 79,104 observations** (2020-01-01 → today). 315 KB total. Numbers sanity-checked: UST 10Y 4.45%, 2s10s +42bp, SOFR 3.65%, IORB 3.65%, HY OAS 272bp, VIX 16.05, Fed BS $6.70 tn, WTI $97.63, Atlanta GDPNow Q2 +3.0%.

**Mistakes we made / things we tried:**

- ❌ **`seriess` typo**: FRED's `/series` endpoint returns `{"seriess": [...]}` (the canonical FRED API typo — single S, double-s). The engineer's `FredClient.series_info()` read `data.get("serieses")` which returned `[]` for everything. Result: the first validation pass dropped 127/127 candidates including `UNRATE`, `CPIAUCSL`, `GDP`. Trivial 1-character fix once we caught it.
- ❌ **Rate-limit blowout**: ran validation (~120 req) then fetch (~129 req) back-to-back. The fetch ran while the validation requests were still in the 60-second window → 429 on 50/123 series. Fix: added 0.6s throttle in `run_fetch`.
- ❌ **API key in logs**: `HTTPClient.get_json` was structlog-logging the full `params=` dict on every request, exposing the FRED key in plaintext. Fix: redact `api_key` / `apikey` / `access_token` / `token` / `secret` / `password` / `Authorization` etc. in [`src/imdr/connectors/http.py`](src/imdr/connectors/http.py). User declined to rotate the key (low-blast-radius internal exposure).
- ❌ **Unicode arrow in print**: `→` in the success-print blew up on Windows cp1252. Replaced with `->`.
- ❌ **5 discontinued / mislabeled FRED IDs** dropped during validation: `CPISERV`, `CPIRENTSL`, `PCETRIM12M158SFRBDAL`, `GOLDAMGBD228NLBM` (London gold fixing discontinued 2015), `CPALTT01EZM657N` (Eurozone CPI YoY — needs different code). Documented in `validate_and_seed.py` candidate-list comment.
- ❌ **Cadence labels off**: 4 series initially declared WEEKLY were actually MONTHLY (DISCBORR, BUSLOANS, REALLN, CONSUMER). Validator warned; we corrected the labels.
- ✅ FRED is well-behaved. Once the connector is right, everything works.

**Open gaps / TODO:**

- Promote to `src/imdr/connectors/fred.py` + `src/imdr/domains/econ/seeds/fred.yml` + `scripts/econ/fred/fred_daily.py` once the schema migration lands.
- Wire `/releases/dates` into the daily scheduler for release-time-aware refreshes (§4.4).
- Use `/series/updates` for incremental ingest in production to halve daily quota usage.
- Consider adding ~30 more series for ECB / IMF / BIS / OECD direct connectors when they're built — current FRED mirrors are transitional.

**Reachability:** FRED is fully open from corp network. No anti-bot. The only constraint is the 120-req/min quota.

### 2.5 India — RBI deep dive (2026-06-03)

Two working paths into RBI data + one major future-risk + a captured URL catalogue.

#### Path A — DBIE CIMS gateway (FX reserves live)

- Base URL: `https://data.rbi.org.in/CIMS_Gateway_DBIE/GATEWAY/SERVICES/`
- Static three-header auth: `authorization` / `datatype` / `channelkey`
- `dbie_foreignExchangeReserves` confirmed working in plaintext POST body (5 components: TR / FCA / GOLD / SDR / IMF; verified $681.4 bn total matches RBI's published number)
- Most other DBIE endpoints sit behind SAP BusinessObjects with encrypted reportIds (hard to drive programmatically — would need to reverse-engineer the SPA's AES key)
- Fetcher: `playground/econ/rbi/fetch.py` (headless httpx). 5 years × weekly = 1,305 obs committed to parquet.

#### Path B — Monthly Bulletin XLSX (headed Chrome required)

- URL pattern: `https://rbidocs.rbi.org.in/rdocs/Bulletin/DOCs/{N}T_BULL{ddmmyyyy}{hash}.XLSX` where `{N}` is the bulletin table number (1, 2, 3, … 19A/B/C … 52A/B)
- **127 download URLs catalogued** (58 XLSX + 69 PDF) from the May 2026 bulletin — see `playground/econ/rbi_explore/snapshots.jsonl` (snapshot idx=0)
- Files are real XLSX binaries (PK ZIP archives), NOT HTML-disguised-as-XLSX
- **Protected by Akamai TSPD** — requires headed Chrome with active JS execution to download. Headless + persistent cookies alone are NOT sufficient (TSPD challenge requires live JS context)
- Fetcher: `playground/econ/rbi/fetch_bulletin.py` (headed Playwright + `page.expect_download()` + persistent profile)
- Per-table parsers required — each bulletin table has its own layout. Two working today:
  - `parse_call_money_27` — Table 27 Daily Call Money Rates (wavg + range_low + range_high; 28 dates × 3 = 84 obs/month)
  - `parse_cpi_combined_19c` — Table 19C CPI Combined (14 divisions × 2 measures × 3 periods = 84 obs/month)
- ~10 more priority tables have URLs captured but no parser yet (Money Stock / Reserve Money / WPI / IIP / NEER-REER / BoP / Foreign Trade / RBI L&A); each ~20 min of per-table work when needed

#### CIMS migration risk

RBI states "Existing XBRL, DBIE and SAARC portal will be discontinued once complete CIMS project goes LIVE." Replacement = 10 new portals:

- BoP — `https://bop.rbi.org.in/`
- FLAIR — `https://flair.rbi.org.in/`
- SMS — `https://sms.rbi.org.in/`
- FED — `https://fed.rbi.org.in/`
- CISBI — `https://cisbi.rbi.org.in`
- FIRMS — `https://firms.rbi.org.in/firms`
- Data Collector — `https://datacollector.rbi.org.in/`
- ADEPT — `https://adept.rbi.org.in/CBSL`
- CIMS DRM — `https://sankalan.rbi.org.in`
- CIMS Common Login — `https://cims.rbi.org.in`

When DBIE goes dark, the FX-reserves endpoint above will break and we'll need to migrate to one of the CIMS-family endpoints. No firm deprecation date as of 2026-06-03.

#### Exploration playbook for RBI (reusable)

1. `python playground/econ/explore_rbi.py` — opens headed Chrome (real Chrome via `channel="chrome"`) with persistent profile at `playground/econ/profiles/rbi/`. Drive around, hit Enter in terminal to snapshot each useful page. Quit with `q`.
2. Snapshots land at `playground/econ/rbi_explore/` (PNG + raw HTML + JSONL of all link/heading metadata).
3. Read `snapshots.jsonl` to identify download URL patterns + the SPA's backing API endpoints.
4. Write a fetcher targeted at confirmed-real URLs (NOT guessed URLs — that was the previous engineer's failure mode).

This same explore-first pattern (using the shared `playground/research/portal_explorer.py`) now applies to every new econ source — see `playground/econ/explore_rbi.py` as the template.

### 2.6 Korea — KOSIS OpenAPI (IN PRODUCTION 2026-06-05), MODS PDFs (playground), BOK ECOS (blocked)

> **2026-06-05 update:** KOSIS + REB are now fully automated in production. 20 prod fetchers live under `scripts/econ/kr/kosis/` + `scripts/econ/kr/reb/`, wired into `imdr_weekly.py` + `imdr_monthly.py`. The playground fetchers referenced below are preserved as the legacy sandbox. Ops runbook: [korea/korea_prod_pipeline.md](korea/korea_prod_pipeline.md).

**Status (2026-06-03 PM — historical, see update above):**

- **KOSIS OpenAPI is LIVE.** Key registered, in `.env` as `IMDR_KOSIS_API_KEY`. First fetcher at `playground/econ/kosis/fetch_bop.py` (BoP series via `orgId=301`). Reference at [`docs/admin/econ/korea/kosis_openapi_reference.md`](korea/kosis_openapi_reference.md). See [[project-kosis-openapi-live]].
- **MODS press-release PDFs LIVE** (earlier in session) — `playground/econ/mods/fetch.py`, 10 CPI PDFs on OneDrive.
- **BOK ECOS direct API still blocked** (Korean mobile + citizenship). **KOSIS mirrors ECOS 1:1** with `tblId = DT_{STAT_CODE}` so the block is no longer load-bearing.

#### Why we want it

Korea is a major APAC macro venue (won, KOSPI, BOK policy, USD/KRW NDF). For the macro-screen we need: CPI, GDP, IIP, unemployment, BoP / current account, FX reserves, BOK policy rate, M1/M2. The Bank of Korea (BOK) publishes most of these; the Ministry of Data and Statistics (MODS, the renamed/English-fronted KOSTAT) publishes CPI / employment / housing / industrial production via press releases.

#### What we tried, in order (initially)

**1. KOSIS API (`kosis.kr/openapi/`) — initially DENIED, NOW LIVE.**

First attempt 2026-06-03 AM hit Statistics Korea's mobile-number gate. Later same day the key was issued (see [`project_kosis_openapi_live.md`](../../../../memory/project_kosis_openapi_live.md) for the registration path). Caveats:

- **TLS 1.2 pinning required.** Default Python `requests` negotiates TLS 1.3 which KOSIS edge silently resets. Use an `HTTPAdapter` with `ssl_context.maximum_version = ssl.TLSVersion.TLSv1_2`.
- 40,000 rows per call hard cap. Page via `prdInterval` / `startPrdDe`+`endPrdDe`, or apply for `statisticsBigData.do` for big tables.
- Per-minute throttle exists but threshold unpublished. Throttle response is a **TLS reset**, not HTTP 429.
- All errors return HTTP 200 + JSON `{err, errMsg}`. Codes: `11` invalid auth · `20` missing param · `21` invalid value · `30` no data.

This is now the canonical Korea data path. Playground KOSIS scraper (Playwright headed) stays as fallback for tables not exposed via OpenAPI.

**2. BOK ECOS direct API (`ecos.bok.or.kr`) — still blocked.** Korean mobile + citizenship required. **Workaround**: KOSIS mirrors ECOS series with `tblId = DT_{STAT_CODE}`. Specifically `301Y013` (BOK BoP master) is mirrored at KOSIS `tblId=DT_301Y013`. See [[bok-ecos-bop-codes]] for the BoP item-code structure (`BOPF…` Financial Account + `BOPO…` Errors & Omissions).

**3. KOSIS `statHtml.do` direct HTML scraping (explored, parked).**

The user provided a catalogue file `ETITLE.xls` (copied locally as [`playground/econ/kosis_etitle.xls`](../../../../playground/econ/kosis_etitle.xls)) — 4,083 rows / 7 columns, with **3,263 hyperlinks** to KOSIS English Statistical Tables. Every link is the same shape:

```
https://kosis.kr/statHtml/statHtml.do
  ?orgId=101&tblId={TBL}&vw_cd=MT_ETITLE&list_id={LID}&language=en&conn_path=E3
```

Catalogue example: `tblId=DT_1IN1502, list_id=A11_2015_1` → "Population, Households and Housing Units, Annual 2015~2024".

Discovery via `playground/econ/explore_kosis.py` (kept as a reference wrapper):

- **kosis.kr resets plain TLS** from this corp network — both `requests` and `curl` get `ECONNRESET` immediately. Headed Chrome via Playwright gets through (we proved both navigation and full table render).
- The page is a **SSO-redirected jqGrid SPA** (jQuery 1.9 + jqGrid + FusionCharts). Outer URL becomes `?sso=ok&returnurl=...` then loads the actual table client-side via XHR.
- The "Download" toolbar button is `javascript:fn_downGridSubmit();` — a hidden-form POST. Dialog offers 5 formats (xlsx / xls / CSV / TXT / SDMX 2.0) plus cell-merge / time-alignment / decimal-point toggles.

**Why we stopped here:** templatising `fn_downGridSubmit` across 3,263 tables would need a network-capture script per format choice plus per-table jqGrid-readiness handling. The user explicitly chose to defer ("PDFs might honestly be easier than so much work sometimes"). Snapshot artefacts (HTML + screenshots) remain under `playground/econ/kosis_explore/` if we ever revisit. ETITLE.xls is retained as a ready-made index of every English-translated KOSIS dataset.

**4. MODS press-release PDFs (LIVE) ✅.**

MODS publishes English press releases as static PDFs on per-topic "boards". Each release page exposes a stable download URL — no SSO, no SPA, no form submission. The board listing page itself already carries title + release date + download href, so we don't even need to fetch per-release view pages.

URL pattern (templatisable across every release):

```
GET https://mods.go.kr/board.es?mid={MID}&bid={BID}&ref_bid={REFS}&nPage={N}
    → parse list rows → {list_no, title, release_date, [bf_pdf hrefs]}

GET https://mods.go.kr/boardDownload.es?bid={BID}&list_no={N}&seq={S}
    → raw PDF bytes
```

`bf_pdf` is the HTML class on the file-link anchor; if MODS adds HWP / XLSX attachments to a release we'll see `bf_hwp` / `bf_xlsx` in the same scrape.

#### Boards mapped

| Code | Board | mid | bid | ref_bid |
|---|---|---|---|---|
| `prices` | Prices (CPI) | a20109010000 | a201090100 | 11751,11752 |
| `employment_labour` | Employment and Labour (EAPS, jobs) | a20105010000 | a201050100 | 11732,11733,11734,11735,12051,11786,0068 |
| `housing` | Housing | a20107010000 | a201070100 | 11739,11740,11741 |

Still to map (do via `explore_mods.py` snapshot + add to `BOARDS` dict): Business Trends, Monthly Industrial Statistics (IIP), Foreign Trade, Services Index, Population. The user supplied a list of useful menu IDs in the initial menu nav (a201XX prefix) — see `playground/econ/mods_explore/snapshots.jsonl`.

#### Storage convention (applies to ALL econ raw-file downloads, not just MODS)

`playground/econ/storage.py` is the single source of truth. PDFs (and any future XLSX/CSV raw releases) land at:

```
C:\Users\{user}\OneDrive - RV Capital Management Private Ltd\Trade Knowledge Core - IMDR\
  └── {YYYY}\{MM}\{DD}\         <- release date of the file, not download date
        └── econ\
              └── {vendor}\     <- mods, hkma, rbi, rba, statsnz, ...
                    └── {vendor}_{listing_id}_{slug}.pdf
```

Same convention applies when HKMA / RBA / RBI fetchers start persisting raw artefacts. OneDrive sync handles the upload to the IMDR SharePoint library; nothing here uses Graph or direct SharePoint API.

Verified samples on OneDrive (10 Prices PDFs, 2025-10 → 2026-06):

```
.../2025/10/02/econ/mods/mods_438859_consumer-price-index-in-september-2025.pdf   519 KB
.../2025/11/04/econ/mods/mods_439121_consumer-price-index-in-october-2025.pdf     509 KB
.../2025/12/02/econ/mods/mods_439516_consumer-price-index-in-november-2025.pdf    487 KB
...
.../2026/06/02/econ/mods/mods_445352_consumer-price-index-in-may-2026.pdf         378 KB
```

#### Mistakes hit (worth not repeating)

1. **Assumed `requests` would work for MODS based on "MODS is reachable".** It's reachable via headed Chrome (which we'd proved with `explore_mods.py`), but not from plain Python TLS — corp WAF resets non-browser handshakes for any `.go.kr` host. Doc comment was untested → wrong. **Always test the actual transport before claiming it works.**
2. **`Playwright APIRequestContext` (`ctx.request.get()`) also gets reset on `.go.kr`.** Its UA string contains `HeadlessChrome/...` which the WAF flags even though the underlying TLS is Chrome's. The fix is to do all HTTP via **in-page `fetch()`** evaluated on a live MODS page — that uses Chrome's real TLS *and* a clean UA. Pattern lives in `ModsClient` in `mods/fetch.py` and is reusable for any other Korean govt host that resets API-context requests.
3. **`&amp;` vs `&` in scraped HTML.** Snapshots taken via `page.content()` serialize entities (`&amp;`); responses fetched via in-page `fetch()` return them decoded (`&`). The regex `_DOWNLOAD_RX` was written against the snapshot and broke against the live fetch. Fix: accept both — `(?:&amp;|&)` between query params.
4. **Title-extractor scope bug.** The row-chunk slicer cuts on `list_no=N` text occurrences. The first occurrence is *inside the `<a href="javascript:addSearchParam(...list_no=N...)">` opening tag*, so the per-row chunk starts AFTER `<a` and the title-extraction regex couldn't anchor on the anchor. Fix: pass full HTML to `_extract_title`, which self-targets by `list_no`.
5. **Wrote a single-purpose `probe.py` and then a `capture_download.py` for KOSIS before slowing down.** Both were premature given that the user later chose MODS PDFs instead. `probe.py` was deleted; `capture_download.py` to be deleted as part of the next cleanup pass.

### 2.7 Explore-first pattern (canonical for every new econ source)

**Lesson from this session** (saved as [`feedback_js_rendered_dont_bail`](../../../../memory/feedback_js_rendered_dont_bail.md) + [`feedback_slow_down`](../../../../memory/feedback_slow_down.md)): every new econ source goes through interactive exploration **before** any fetcher code is written. Don't guess URLs — let the user drive the browser and snapshot each useful page.

**Shared exploration tool**: `playground/research/portal_explorer.py` — vendor-agnostic since 2026-06-03 (refactor accepted `profile_dir` and `out_dir` kwargs without breaking the 10 existing research wrappers).

**Per-source wrapper** (5 lines, see `playground/econ/explore_rbi.py` as the template):

```python
from portal_explorer import explore  # imported from playground/research/
explore(
    "{source_code}",
    "{portal_landing_url}",
    profile_dir=Path(__file__).parent / "profiles" / "{source_code}",
    out_dir=Path(__file__).parent / "{source_code}_explore",
)
```

**Interactive REPL controls** (in the explorer's terminal, NOT via Bash subprocess — input() needs a real TTY):

- `Enter` → snapshot current page (PNG + raw HTML + headings + every `<a href>` to JSONL)
- `l Enter` → list all snapshots so far
- `q Enter` → quit (browser closes, profile is preserved)

**Why this matters:** the FIRST engineer pass at the AU/NZ sources scaffolded fetchers against PLACEHOLDER URLs that were never tested live. URLs like `/statistics/tables/f1-1.xlsx` (RBA), `/assets/Uploads/Statistics/B1/hb1-daily.csv` (RBNZ), `api.infoshare.stats.govt.nz` (Stats NZ) — all 404 / 403 / DNS-failure. Unit tests passed because they mocked HTTP. Quality gap to avoid repeating.

**Snapshot deliverables per source:**

```
playground/econ/{source}_explore/
  snapshots.jsonl    # one record per Enter-press: url + title + headings + links + screenshot + html refs
  screenshots/       # PNGs
  pages/             # raw HTML (capped at 2 MB per page)
```

After exploration: read `snapshots.jsonl` programmatically, extract the URL patterns + API endpoints + auth requirements, **then** write the fetcher.

---

## 3. Schema

Two schemas: **`econ`** for time-series indicators (the bulk of the data), **`funding`** for per-event and per-line records that don't fit the indicator shape (auctions, holdings, CB balance-sheet lines).

### 3.1 Why a generic indicator table

Most public economic data is "country + indicator + date + value". A per-release table (`fact_cpi_au`, `fact_cpi_nz`, `fact_cpi_us`, …) would explode into hundreds of sparse tables. The desk's question is "give me CPI YoY across G10 + APAC on one chart" — that's one `WHERE` clause on a generic table, not a UNION across dozens.

Carve-outs go to dedicated tables only when the data has enough structure to justify it: auctions (bid-cover, tail, investor breakdown), holdings (per-ISIN × holder-country month-end), CB balance sheets (line-item asset/liability tagging).

### 3.2 `econ.dim_indicator` — the catalog

One row per (vendor, source_code). Every series we ingest is registered here first.

**Migration files** (authored + applied 2026-06-03; `display_name` renamed from `description` during apply for consistency with other dbo dims):

| Migration | Purpose |
|---|---|
| `068_create_econ_schema.sql` | `CREATE SCHEMA econ` |
| `069_create_econ_dim_unit.sql` | `dbo.dim_unit_category` (8 rows) + `dbo.dim_unit` + 65 seed units (both live in dbo — universal, not econ-specific; rates / fx / equity will FK here too) |
| `070_create_econ_dim_indicator_category.sql` | `econ.dim_indicator_category` + 17 seed categories |
| `071_seed_econ_dim_vendor.sql` | Adds 21 econ vendors to `dbo.dim_vendor` |
| `072_create_econ_dim_indicator.sql` | This table |
| `073_create_econ_fact_indicator.sql` | Fact table (§3.3) |

**Supporting dims (new in this design)**:

- `dbo.dim_unit` + `dbo.dim_unit_category` — replace free-text `unit` column. Live in `dbo` because units are universal (HKD, USD, percent, bp aren't econ-specific); rates / fx / equity pipelines will FK here too as they migrate away from free-text unit columns. `dim_unit_category` (8 rows: percentage / currency / count / index / ratio / physical / time / rate) sits between `dim_unit` and free-text drift. `dim_unit` carries `unit_code`, `display_name`, `symbol`, `unit_category_id` (FK), `currency_id` (FK to `dbo.dim_currency` — NULL for non-currency units), and `scale` (multiplier to base unit, so `usd_mn` → 1,000,000). Sixty-five units seeded; one INSERT per new unit.
- `econ.dim_indicator_category` — lives in `econ` because the category set (cpi / gdp / labour / bop / …) is specific to indicator-shaped data; FX has `pair`, rates has `tenor`. Replaces the CHECK enum on `dim_indicator.category`. Adding a category (e.g. `tourism`, `credit_aggregates`) becomes a one-row INSERT, not a migration.

**Already-existing dims reused** (no migration needed):

- `dbo.dim_vendor` (16 rows pre-existing; migration 071 adds the 21 econ-domain ones)
- `dbo.dim_country` (52 rows, all econ-target countries present including KR/IN/HK/AU/NZ/US/EU/UK)
- `dbo.dim_frequency` (10 rows: DAILY → ANNUAL + intraday + EVENT)

```sql
CREATE TABLE [econ].[dim_indicator] (
    id                      INT IDENTITY(1,1) NOT NULL,
    imdr_code               VARCHAR(128)   NOT NULL,   -- 'FRED.CPI.HEADLINE.US', 'HKMA.AGG_BAL', 'MODS.CPI.HEADLINE.KR'
    vendor_id               INT            NOT NULL,   -- FK dbo.dim_vendor(id)
    source_code             VARCHAR(128)   NOT NULL,   -- vendor's native series id (e.g. 'CPIAUCSL', 'agg_bal')
    bbg_ticker              VARCHAR(64)        NULL,   -- 'CPI YOY Index' when one exists
    display_name            NVARCHAR(512)  NOT NULL,
    unit_id                 TINYINT        NOT NULL,   -- FK dbo.dim_unit(id)
    frequency_id            TINYINT        NOT NULL,   -- FK dbo.dim_frequency(id)
    country_id              TINYINT            NULL,   -- FK dbo.dim_country(id); NULL = global aggregate
    category_id             TINYINT        NOT NULL,   -- FK econ.dim_indicator_category(id)
    is_seasonally_adjusted  BIT            NOT NULL CONSTRAINT df_dim_indicator_sa     DEFAULT 0,
    is_active               BIT            NOT NULL CONSTRAINT df_dim_indicator_active DEFAULT 1,
    created_at              DATETIMEOFFSET NOT NULL CONSTRAINT df_dim_indicator_ct     DEFAULT SYSDATETIMEOFFSET(),
    updated_at              DATETIMEOFFSET NOT NULL CONSTRAINT df_dim_indicator_ut     DEFAULT SYSDATETIMEOFFSET(),

    CONSTRAINT pk_dim_indicator         PRIMARY KEY NONCLUSTERED (id),
    CONSTRAINT uq_dim_indicator_imdr_code UNIQUE (imdr_code),
    CONSTRAINT uq_dim_indicator_source  UNIQUE (vendor_id, source_code),
    CONSTRAINT fk_dim_indicator_vendor    FOREIGN KEY (vendor_id)    REFERENCES [dbo].[dim_vendor](id),
    CONSTRAINT fk_dim_indicator_frequency FOREIGN KEY (frequency_id) REFERENCES [dbo].[dim_frequency](id),
    CONSTRAINT fk_dim_indicator_country   FOREIGN KEY (country_id)   REFERENCES [dbo].[dim_country](id),
    CONSTRAINT fk_dim_indicator_unit      FOREIGN KEY (unit_id)      REFERENCES [dbo].[dim_unit](id),
    CONSTRAINT fk_dim_indicator_category  FOREIGN KEY (category_id)  REFERENCES [econ].[dim_indicator_category](id)
);

CREATE INDEX ix_dim_indicator_category_country
    ON [econ].[dim_indicator] (category_id, country_id) INCLUDE (imdr_code);

CREATE INDEX ix_dim_indicator_vendor
    ON [econ].[dim_indicator] (vendor_id) INCLUDE (source_code, imdr_code);
```

**`imdr_code` naming**: dotted, namespaced, stable — `{SOURCE}.{CATEGORY}.{KEY}[.{COUNTRY}]`. Examples: `FRED.CPI.HEADLINE.US`, `ABS.CPI.HEADLINE.AU`, `RBNZ.OCR`, `BIS.CGDP_GAP.US`. NEVER changes once issued — consumers depend on it. `source_code` may change if the vendor recodes; the public `imdr_code` stays stable.

**Why two FKs replaced free-text strings**:

- `unit_id` (was `unit VARCHAR(32)`): seeing `'pct_yoy'` vs `'%_yoy'` vs `'% yoy'` in the wild meant analysts couldn't `GROUP BY unit` reliably. `dim_unit` makes it a single canonical row per unit, and the `scale` column lets a loader normalise (e.g. RBA `aud_mn` vs ABS `aud_bn`) when desk asks.
- `category_id` (was `category VARCHAR(32)` with CHECK enum): the CHECK locked the enum into DDL; adding `tourism` meant a migration. `dim_indicator_category` makes that an INSERT.

**Category seeds** (loaded by migration 070): `cpi`, `gdp`, `labour`, `bop`, `balance_sheet`, `rates`, `fx`, `housing`, `credit`, `sentiment`, `energy`, `tourism`, `liquidity`, `cb_facility`, `cb_balance_sheet`, `instr_outstand`, `other`. The CB-liquidity quartet (`liquidity` / `cb_facility` / `cb_balance_sheet` / `instr_outstand`) was added during the HKMA playground prototype (2026-06-02) to distinguish central-bank-side from sector-side balance-sheet items.

**Unit seeds** (loaded by migration 069, ~50 rows across 8 categories): `pct` / `pct_yoy` / `bp` / `pp` / `pct_of_gdp`; `index` / `index_2015_100`; currency-scaled (`usd_mn`, `hkd_mn`, `aud_mn`, `inr_cr`, `krw_bn`, `eur_mn`, `jpy_bn`, `gbp_mn`, `sgd_mn`, plus base units and `_bn` siblings); counts (`persons`, `th_persons`, `mn_persons`, `dwellings`); physical (`tonnes`, `barrels`, `kbd`, `gwh`); ratios + time + yields. Extend via INSERT.

### 3.3 `econ.fact_indicator` — the data

Vintage-aware: every print we ever see is kept. `vintage = 0` is the first print; `1+` is each revision.

```sql
CREATE TABLE [econ].[fact_indicator] (
    indicator_id   INT             NOT NULL,
    obs_date       DATE            NOT NULL,         -- reference-period START (2026-04-01 = "April 2026 CPI")
    vintage        SMALLINT        NOT NULL,         -- 0 = first print, 1+ = revisions
    release_date   DATETIMEOFFSET  NOT NULL,         -- when the print actually hit
    value          DECIMAL(28, 10)     NULL,         -- NULL = row published with no value yet
    is_preliminary BIT             NOT NULL CONSTRAINT df_fact_indicator_prelim   DEFAULT 0,
    ingested_at    DATETIMEOFFSET  NOT NULL CONSTRAINT df_fact_indicator_ingested DEFAULT SYSDATETIMEOFFSET(),

    CONSTRAINT pk_fact_indicator
        PRIMARY KEY NONCLUSTERED (indicator_id, obs_date, vintage),
    CONSTRAINT fk_fact_indicator_indicator
        FOREIGN KEY (indicator_id) REFERENCES [econ].[dim_indicator](id),
    CONSTRAINT ck_fact_indicator_vintage_nonneg
        CHECK (vintage >= 0)
)
WITH (DATA_COMPRESSION = PAGE);

-- Clustered on obs_date for cross-indicator time-range scans
-- ("CPI YoY across G10, last 2y" pivots on obs_date first).
CREATE CLUSTERED INDEX cix_fact_indicator_obs
    ON [econ].[fact_indicator] (obs_date, indicator_id)
    WITH (DATA_COMPRESSION = PAGE);

-- "Latest vintage per indicator" covering index for single-series lookups.
CREATE INDEX ix_fact_indicator_latest
    ON [econ].[fact_indicator] (indicator_id, obs_date DESC, vintage DESC)
    INCLUDE (release_date, value)
    WITH (DATA_COMPRESSION = PAGE);
```

**Why rowstore + PAGE, not clustered columnstore (yet)**: expected v1 volume is ~1M rows (129 FRED + planned ~200 more × ~365 days × ~10 years history). PAGE compression on rowstore is enough at that scale and keeps trickle inserts (live releases) cheap. Revisit CCI at ~50M+ rows or when analytical scans become the bottleneck.

Query patterns this supports cheaply:

- "CPI YoY across AU/NZ/US, last 2y, latest vintage" — `WHERE category='cpi'`, filter to `MAX(vintage)` per `(indicator_id, obs_date)`.
- "Real-time CPI history as it was known on date X" — `WHERE vintage = 0 AND release_date <= X`.
- "Latest print per indicator" — `ROW_NUMBER() OVER (PARTITION BY indicator_id ORDER BY obs_date DESC, vintage DESC) = 1`.

### 3.4 `funding.fact_govt_auction` — per-event auctions

AOFM, RBNZ DMO, US Treasury, DMO UK all fit.

```sql
CREATE TABLE funding.fact_govt_auction (
    auction_id        BIGINT IDENTITY(1,1) NOT NULL,
    vendor_id         INT            NOT NULL,        -- FK dbo.dim_vendor (AOFM / RBNZ DMO / etc.)
    country_id        INT            NOT NULL,        -- FK dbo.dim_country
    auction_date      DATE           NOT NULL,
    settlement_date   DATE           NULL,
    isin              VARCHAR(12)    NULL,
    security_code     VARCHAR(32)    NOT NULL,        -- AOFM line ('TB145'), Treasury CUSIP, RBNZ code
    security_type     VARCHAR(16)    NOT NULL,        -- 'bond'|'tib'|'note'|'bill'|'syndication'|'switch'|'buyback'|'tap'
    coupon            DECIMAL(8,5)   NULL,
    maturity_date     DATE           NULL,
    amount_offered    DECIMAL(18,2)  NULL,            -- face value
    amount_allotted   DECIMAL(18,2)  NULL,
    bid_to_cover      DECIMAL(8,4)   NULL,
    cutoff_yield      DECIMAL(10,6)  NULL,
    weighted_avg_yld  DECIMAL(10,6)  NULL,
    tail_bp           DECIMAL(8,4)   NULL,            -- cutoff − weighted-avg, bp
    high_price        DECIMAL(14,8)  NULL,
    weighted_avg_pr   DECIMAL(14,8)  NULL,
    investor_breakdown_json NVARCHAR(MAX) NULL,       -- syndication books when published
    ingested_at       DATETIMEOFFSET NOT NULL CONSTRAINT DF_fact_govt_auction_ingested DEFAULT SYSDATETIMEOFFSET(),

    CONSTRAINT PK_fact_govt_auction PRIMARY KEY NONCLUSTERED (auction_id),
    CONSTRAINT UQ_fact_govt_auction_natural UNIQUE (vendor_id, country_id, auction_date, security_code, security_type),
    CONSTRAINT FK_fact_govt_auction_vendor  FOREIGN KEY (vendor_id)  REFERENCES dbo.dim_vendor(vendor_id),
    CONSTRAINT FK_fact_govt_auction_country FOREIGN KEY (country_id) REFERENCES dbo.dim_country(country_id),
    CONSTRAINT CK_fact_govt_auction_type CHECK (security_type IN
        ('bond','tib','note','bill','syndication','switch','buyback','tap'))
)
WITH (DATA_COMPRESSION = PAGE);

CREATE CLUSTERED INDEX CIX_fact_govt_auction_date
    ON funding.fact_govt_auction(auction_date, country_id);
```

### 3.5 `funding.fact_govt_holdings` — per-line holdings snapshots

AOFM non-resident holdings, RBNZ non-resident bond holdings, US TIC custody.

```sql
CREATE TABLE funding.fact_govt_holdings (
    country_id        INT            NOT NULL,  -- FK dbo.dim_country (issuing country)
    isin              VARCHAR(12)    NOT NULL,
    security_code     VARCHAR(32)    NOT NULL,
    holder_type       VARCHAR(32)    NOT NULL,  -- 'non_resident'|'central_bank'|'official_sector'|'aggregate'
    holder_country_id INT            NULL,      -- FK dbo.dim_country (when broken out by holder country)
    obs_date          DATE           NOT NULL,  -- month-end (or as published)
    face_value        DECIMAL(18,2)  NULL,
    market_value      DECIMAL(18,2)  NULL,
    pct_outstanding   DECIMAL(8,5)   NULL,
    vendor_id         INT            NOT NULL,
    ingested_at       DATETIMEOFFSET NOT NULL CONSTRAINT DF_fact_govt_holdings_ingested DEFAULT SYSDATETIMEOFFSET(),

    CONSTRAINT PK_fact_govt_holdings PRIMARY KEY NONCLUSTERED
        (country_id, isin, holder_type, ISNULL(holder_country_id, 0), obs_date),
    CONSTRAINT FK_fact_govt_holdings_country FOREIGN KEY (country_id)        REFERENCES dbo.dim_country(country_id),
    CONSTRAINT FK_fact_govt_holdings_holder  FOREIGN KEY (holder_country_id) REFERENCES dbo.dim_country(country_id),
    CONSTRAINT FK_fact_govt_holdings_vendor  FOREIGN KEY (vendor_id)         REFERENCES dbo.dim_vendor(vendor_id)
)
WITH (DATA_COMPRESSION = PAGE);

CREATE CLUSTERED INDEX CIX_fact_govt_holdings_obs
    ON funding.fact_govt_holdings(obs_date, country_id);
```

### 3.6 `funding.fact_cb_balance_sheet` — central-bank line items

Weekly Fed H.4.1, weekly RBA, weekly ECB WFS, RBNZ.

```sql
CREATE TABLE funding.fact_cb_balance_sheet (
    country_id      INT            NOT NULL,  -- FK dbo.dim_country (CB's home country)
    line_item_code  VARCHAR(64)    NOT NULL,  -- 'WALCL.TREASURIES', 'RBA.AGS_HOLDINGS', 'RBNZ.SETTLEMENT_CASH'
    obs_date        DATE           NOT NULL,
    value           DECIMAL(20,2)  NOT NULL,
    unit            VARCHAR(16)    NOT NULL,  -- 'usd_mn'|'aud_mn'|'nzd_mn'|'eur_mn'
    side            CHAR(1)        NOT NULL,  -- 'A' assets | 'L' liabilities | 'C' capital
    vendor_id       INT            NOT NULL,
    ingested_at     DATETIMEOFFSET NOT NULL CONSTRAINT DF_fact_cb_bs_ingested DEFAULT SYSDATETIMEOFFSET(),

    CONSTRAINT PK_fact_cb_balance_sheet PRIMARY KEY NONCLUSTERED (country_id, line_item_code, obs_date),
    CONSTRAINT FK_fact_cb_bs_country FOREIGN KEY (country_id) REFERENCES dbo.dim_country(country_id),
    CONSTRAINT FK_fact_cb_bs_vendor  FOREIGN KEY (vendor_id)  REFERENCES dbo.dim_vendor(vendor_id),
    CONSTRAINT CK_fact_cb_bs_side    CHECK (side IN ('A','L','C'))
)
WITH (DATA_COMPRESSION = PAGE);

CREATE CLUSTERED INDEX CIX_fact_cb_bs_obs
    ON funding.fact_cb_balance_sheet(obs_date, country_id);
```

### 3.7 Dim reuse — nothing new to build

| Dim | Source | Already used by |
|---|---|---|
| `dbo.dim_vendor` | Existing | All fact tables |
| `dbo.dim_frequency` | Migration 023 (TICK/SNAPSHOT/MINUTE/HOURLY/DAILY/WEEKLY/MONTHLY/QUARTERLY/ANNUAL/EVENT) | `fx.fact_fx_rate` |
| `dbo.dim_country` | Country-anchor calendar restructure | `equities.dim_index.country_id`, calendar tables |

### 3.8 Migrations

Per the `{NNN}_{description}.sql` convention. Order matters — schemas first, then `dim_indicator` (referenced by `fact_indicator`), then facts.

```
migrations/
  0NN_create_econ_schema.sql               -- CREATE SCHEMA econ; CREATE SCHEMA funding;
  0NN_create_econ_dim_indicator.sql
  0NN_create_econ_fact_indicator.sql
  0NN_create_funding_fact_govt_auction.sql
  0NN_create_funding_fact_govt_holdings.sql
  0NN_create_funding_fact_cb_balance_sheet.sql
```

---

## 4. Pipeline conventions

Every economic-data pipeline follows the standard IMDR layout, with a few specifics for this domain.

### 4.1 File layout

```
src/imdr/connectors/
  fred.py                          # one connector per source
  rba.py
  rbnz.py
  abs.py
  statsnz.py
  bis.py
  ecb.py
  oecd.py
  imf.py
  worldbank.py
  ...

src/imdr/domains/econ/
  __init__.py
  pipeline_indicator.py            # generic fact_indicator pipeline base
  pipeline_auction.py              # govt_auction pipeline (funding schema)
  pipeline_holdings.py             # govt_holdings pipeline (funding schema)
  pipeline_cb_balance_sheet.py     # cb_balance_sheet pipeline (funding schema)
  seeds/
    fred.yml                       # series-id → indicator metadata
    rba.yml
    rbnz.yml
    ...

scripts/econ/{source}/
  {source}_daily.py
  {source}_monthly.py
  ...

migrations/0NN_*.sql
```

### 4.2 Seeding `dim_indicator`

Each source has a YAML seed file enumerating the series to ingest. The pipeline's `transform()` calls a shared `bulk_seed_indicators()` helper (idempotent), so `dim_indicator` self-populates on first run — same pattern as `dim_curve` in the rates pipeline.

```yaml
# src/imdr/domains/econ/seeds/fred.yml
indicators:
  - source_code: CPIAUCSL
    imdr_code: FRED.CPI.HEADLINE_SA.US
    display_name: Consumer Price Index for All Urban Consumers
    unit: index
    frequency: MONTHLY
    country: US
    category: cpi
    is_seasonally_adjusted: true
    bbg_ticker: CPI INDX Index
  - source_code: UNRATE
    imdr_code: FRED.LABOUR.UNRATE.US
    ...
```

### 4.3 Raw archive — parquet (per-pull snapshots)

Like the Citi pipelines, every raw API pull is parquet-archived before normalisation. Folder pattern matches existing convention:

```
data/parquet/econ/{source}/{YYYY}/{MM}/{DD}/{source}_{YYYYMMDD}_{HHMM}.parquet
```

Re-processing into `fact_indicator` becomes cheap when the indicator mapping changes.

### 4.4 Raw artefact storage — vendor PDFs / XLSX / CSV releases

Distinct from §4.3 — these are the vendor's *original published files* (press-release PDFs, statistical-bulletin XLSXs, CSV downloads), not our parquet-normalised snapshots. They live on OneDrive (synced to the IMDR SharePoint library) so analysts can pull the source file alongside our normalised numbers without git-cloning the repo.

**Single source of truth**: [`playground/econ/storage.py`](../../../../playground/econ/storage.py) — every econ fetcher that persists a raw artefact MUST route through `econ_sharepoint_path(vendor, release_date, filename)`.

**Path convention**:

```
C:\Users\{user}\OneDrive - RV Capital Management Private Ltd\
    Trade Knowledge Core - IMDR\
      └── {YYYY}\{MM}\{DD}\         # release date of the artefact, not download date
            └── econ\
                  └── {vendor}\     # mods, hkma, rbi, rba, statsnz, ...
                        └── {vendor}_{listing_id}_{slug}.{ext}
```

**Why date-first, then `econ/{vendor}/`**: the OneDrive root already groups by `{YYYY}/{MM}/{DD}` for unrelated workflows; co-locating econ artefacts inside the same date folder keeps everything-on-this-day in one place. Within a date folder, `econ/` segregates from other workflows; within `econ/`, the vendor subdir keeps sources from colliding.

**Override**: set `IMDR_ECON_SP_ROOT` env var if the OneDrive mount point differs (e.g. different machine layout). Default resolves from `%USERPROFILE%`.

**Failure mode**: the helper raises `FileNotFoundError` if the OneDrive root isn't on disk (sync stopped, library unmounted) — fail loud rather than silently writing to a partial path.

**Manifest** (separate, repo-local): per-run parquet manifest at `playground/econ/{vendor}/manifests/releases_{YYYYMMDD}_{HHMM}.parquet` carries `(vendor, release_date, list_no, title, file_ext, sharepoint_path, sha1, size_bytes)`. This lets us reconstruct what landed on SharePoint without listing the SharePoint tree.

**Idempotence**: fetchers must check `sp_path.exists()` before re-downloading; re-runs are cheap and skip already-synced files.

**First user**: `playground/econ/mods/fetch.py` (§2.6) — 10 CPI PDFs end-to-end-verified on disk. HKMA / RBI / RBA fetchers will adopt the same convention when they start persisting raw artefacts (today they only write to local parquet under §4.3).

### 4.5 Scheduling

- **Release-time discipline**: ABS / Stats NZ / RBNZ / Fed publish on fixed clocks. Pipelines must run *after* the official release time, not on a generic 06:00 UTC cron. Each pipeline owns a release-time-aware scheduler entry.
- **Daily / monthly / quarterly schedulers**: register pipelines in the existing `scripts/imdr_daily.py`, `imdr_monthly.py`, `imdr_quarterly.py` per cadence.
- **RBNZ scraping**: RBNZ publishes terms-of-use for automated access. Use a clear `User-Agent`, throttle to ≤ 4 concurrent on a single host, no NZ public holidays. Aligns with [no anti-detection in research scrapers](../../../../memory/feedback_no_anti_detection_research.md).

### 4.6 Revision handling

- All sources that publish revisions are pulled in full each run; the pipeline diffs against `fact_indicator` and inserts a new `vintage` row only when the value changed for an existing `(indicator_id, obs_date)`.
- `vintage = 0` is the first time we ever see the row. Each later change is `vintage = MAX(vintage) + 1`.
- For sources that *don't* publish history (rare), `vintage` stays at 0 forever.

### 4.7 Quality checks

Standard `RowCountCheck` + `NullCheck` per pipeline. Add domain-specific checks:

- **CPI / GDP** — `PercentageChangeCheck` on YoY values to catch units mistakes (10× / 100× errors).
- **Balance sheets** — `BalanceSheetIdentityCheck`: `SUM(side='A') ≈ SUM(side='L') + SUM(side='C')` per `(country_id, obs_date)`.
- **Auctions** — `bid_to_cover > 0`, `cutoff_yield BETWEEN -5 AND 30` (catches unit slips).

---

## 5. Build sequence

Ordered by leverage (data per unit of build effort) and what unblocks other work.

### Phase 0 — Playground prototype (current)

Prove out connectors, indicator mapping, and parquet shape under `playground/econ/` **before** any migration lands. Per the standing [playground-only-for-exploration](../../../../memory/feedback_playground_only_for_exploration.md) rule. The promotion path (Phases 1–2 below) only kicks in once the desk has reviewed the parquet samples and signed off on the dim/fact shape.

```
playground/econ/
  README.md                         # status, promotion checklist
  schema_prototype.py               # dataclasses mirroring §3 dim_indicator + fact_indicator
  fred/
    connector.py                    # REST + key
    seed.yml                        # ~12 US headline indicators
    fetch.py                        # one-shot: pull → parquet sample
    sample_output/
  rba/
    fetch.py                        # OCR + monetary aggregates + FX + bond yields
    sample_output/
  rbnz/
    fetch.py                        # OCR + TWI + balance sheet
    sample_output/
  abs/
    fetch.py                        # CPI workbook
    sample_output/
  statsnz/
    fetch.py                        # quarterly CPI + monthly SPI
    sample_output/
```

### Phase 1 — Promote schema + FRED to production

Only after Phase 0 review:

1. Land `econ` + `funding` schemas + `dim_indicator` + `fact_indicator` migrations. Unblocks [IMD-17](https://linear.app/imdr/issue/IMD-17) (which will become `econ.fact_policy_rates`).
2. Promote playground FRED connector → `src/imdr/connectors/fred.py`.
3. Promote `fred.yml` seed → `src/imdr/domains/econ/seeds/fred.yml`.
4. Daily ingest `scripts/econ/fred/fred_daily.py`; register in `imdr_daily.py`.

### Phase 2 — Promote APAC central-bank data

5. **RBA** statistical tables → `econ.fact_indicator`. Seed: OCR, monetary aggregates (D3), credit aggregates (D2), FX rates (F11), money-market rates (F1), govt-bond yields (F2).
6. **RBNZ** → `econ.fact_indicator`: OCR, TWI, wholesale + retail rates, balance sheet, monetary aggregates.
7. **ABS CPI** monthly job (`imdr_monthly.py`).
8. **Stats NZ** quarterly CPI / PPI / HLPI / LCI / OTI + monthly SPI.

### Phase 3 — Auctions, holdings, term premia

9. **AOFM** daily yield-decomposition + term-premium CSV. Auctions → `funding.fact_govt_auction`. Non-resident holdings → `funding.fact_govt_holdings`.
10. **RBNZ debt-securities** (govt-bond turnover, non-resident holdings, Kauri bonds) → `funding.fact_govt_holdings`.
11. **RBA + Fed + RBNZ + ECB** weekly balance sheets → `funding.fact_cb_balance_sheet`.

### Phase 4 — Global aggregators

12. **BIS**: credit-to-GDP gaps, debt-service ratios, central-bank policy rates, CB total assets (SDMX endpoint).
13. **ECB SDW**: HICP, ESTR + compounded ESTR, MFI lending.
14. **OECD**: Economic Outlook projections, PPPs.
15. **World Bank WDI** (annual schedule).
16. **IMF IFS / WEO** (cross-country comparability layer).

### Phase 5 — Asia singles + sector data

17. **BOJ**, **BoK ECOS**, **MAS**, **RBI DBIE** — country-specific connectors, all into the generic `fact_indicator`.
18. **MBIE NZ Energy Quarterly** + weekly fuel prices.
19. **MRTE tourism estimates** (NZ).

---

## 6. Sign-off status

**Resolved 2026-06-02**:

1. ~~Schema split~~ — **`econ` + `funding`**. Two schemas (renamed from `macro` for brevity).
2. ~~Govt-bond yields routing~~ — go into **`rates.fact_govtbond`** (when [IMD-15](https://linear.app/imdr/issue/IMD-15) lands), with `vendor_id` distinguishing Citi vs AOFM vs RBNZ. They stay out of `econ.fact_indicator`.
3. ~~Phase-1 scope~~ — **FRED + RBA + RBNZ + ABS CPI + Stats NZ price indexes** in the first build.

**Also resolved 2026-06-03 (this session)**:

8. ~~FRED seed depth~~ — **129 indicators** across 9 macro-PM morning-screen buckets (Rates / CB BS / CPI/PCE / GDP / Labour / Conditions / Risk / Cross-country / Credit-Housing), validated against `/series`. Sample on disk.
9. ~~Stats NZ ADE keys~~ — registered, live in `.env` as `IMDR_ECON_STATSNZ_PRIMARY_KEY` + `IMDR_ECON_STATSNZ_SECONDARY_KEY`. **Caveat**: ADE catalogue doesn't carry CPI; real CPI ingest is via release-page Playwright scrape (see §2.2.1).
10. ~~Stats NZ working fetcher~~ — `playground/econ/statsnz/fetch.py` (release-page Playwright) ships first sample on disk (Mar-2026 CPI: 301 indicators × 1,622 obs).
11. ~~RBI FX reserves~~ — DBIE API working, 5 components × 1,305 weekly obs on disk, totals match RBI's published number.
12. ~~RBI Bulletin path~~ — headed Playwright + `page.expect_download()` works past Akamai TSPD. 2 per-table parsers shipped (Table 27 Call Money + Table 19C CPI Combined), 31 indicators × 168 obs sample on disk. 10 more priority tables URL-catalogued; parsers pending.
13. ~~RBNZ status~~ — network-blocked at Cloudflare layer ("access restricted" page). NZ data routed via FRED-OECD mirrors meantime. Email path to `Servicedesk@rbnz.govt.nz` queued.
14. ~~HKMA sample~~ — 4 indicators × 90-day sample on disk. 2 endpoints sufficient; full daily history back to 1997 available.
15. ~~Exploration pattern~~ — `portal_explorer.py` refactored to accept explicit profile/out paths (§2.7). Every new econ source now starts with `explore_{source}.py` before any fetcher code is written.
19. ~~Korea path~~ — Three-path resolution (2026-06-03):
    1. **KOSIS OpenAPI LIVE** (later in session) — key in `.env` as `IMDR_KOSIS_API_KEY`. TLS 1.2 pinning + 40k-row cap. First fetcher at `playground/econ/kosis/fetch_bop.py` for BoP. Mirrors ECOS 1:1 so the BOK direct gate is no longer blocking.
    2. **MODS press-release PDFs LIVE** — `playground/econ/mods/fetch.py` working, 10 CPI PDFs on OneDrive. Three boards mapped (Prices / Employment & Labour / Housing).
    3. **BOK ECOS direct API still blocked** (mobile+citizenship) but worked around via KOSIS mirror.
20. ~~Raw-artefact storage~~ — convention codified at `playground/econ/storage.py` (§4.4): all econ PDFs / XLSX / CSV releases land at `{onedrive}/{YYYY}/{MM}/{DD}/econ/{vendor}/`. Applies to every econ vendor going forward; HKMA / RBI / RBA will adopt when they start persisting raw files.
21. ~~MODS transport lessons~~ — `.go.kr` hosts reset both plain `requests` AND Playwright `APIRequestContext` (HeadlessChrome UA flagged by corp WAF). Workaround pattern: headless Playwright + in-page `fetch()` evaluated on a live page — uses real Chrome TLS + clean UA. Reusable for any future Korean-govt source.
22. ~~Unit + category as dimensions~~ (2026-06-03) — `unit` and `category` moved from free-text columns to FK chains. `dbo.dim_unit` (universal across domains) FKs into both `dbo.dim_unit_category` (8-row enum of measurement types) and `dbo.dim_currency` (for currency-typed units). `econ.dim_indicator_category` (17 rows, econ-specific) replaces the CHECK enum on the indicator dim. `dim_unit.scale` lets the loader normalise vendors that quote the same series in different scales (e.g. RBA AUD mn vs ABS AUD bn).
24. **Free-linkage audit deferred** (2026-06-03):
    - **`dbo.dim_vendor.vendor_type`** is a free-text VARCHAR(20) with no CHECK constraint, currently carrying `'api' / 'file' / 'terminal' / 'web'`. Same drift risk that `dim_unit_category` solves. Promotion to `dbo.dim_vendor_type` recommended but DEFERRED — touches existing live `dim_vendor` rows so it needs its own migration with ALTER TABLE + data backfill, not bundled into the econ rollout.
    - **`econ.dim_indicator.bbg_ticker`** is free-text VARCHAR(64) NULL. There is no canonical BBG-ticker dim in IMDR yet. Refactor when one arrives; until then, the column is descriptive only (no joins are made against it).
23. ~~Migrations authored + applied~~ (2026-06-03) — six idempotent migration files (068–073) covering schema + 3 new dims (`dbo.dim_unit_category`, `dbo.dim_unit`, `econ.dim_indicator_category`) + 21 econ-vendor seed + `dim_indicator` + `fact_indicator`. **All applied**. Schema-naming tweak during apply: `description NVARCHAR(512)` → `display_name NVARCHAR(512)` on `econ.dim_indicator` for consistency with `dim_vendor` / `dim_country` / `dim_frequency`. Playground fetchers' `IndicatorRow.description` renamed to `display_name` in lockstep (`schema_prototype.py` + 8 fetcher call sites).
25. ~~Migration 076 applied~~ (2026-06-03) — added `hours` + `units_th` to `dbo.dim_unit` (needed by 4 FRED indicators: `LABOUR.HOURS_AVG` + `HOUSING.{STARTS,PERMITS,EXISTING_SALES}`). Original number 074 collided with already-applied research-vendor seed; renumbered.
26. ~~FRED loaded end-to-end~~ (2026-06-03) — 170 indicators / 80,810 obs. v1 was 129 (US-heavy + 6 non-US headline). v2 expanded with US BoP / PPI / fiscal / HH balance-sheet (+18) and OECD-mirror G10 CPI YoY / Unemployment / Real GDP / Industrial Production (+23 net, after dropping 5 dead OECD codes and 3 collisions with prior NZ/JP/GB OECD CPI series). IIP code pattern discovered via `playground/econ/fred/search.py` — correct slugs are `{ISO3}PROIND{M,Q}ISMEI` for OECD MEI.
27. ~~HKMA v2 loaded end-to-end~~ (2026-06-03) — 29 indicators / 192,083 obs. Fetcher refactored from hardcoded 2-endpoint dispatch to config-driven N-endpoint loop. New series across 6 clusters: HIBOR ×6, HKD spot vs 6 majors, NEERI 2020 ×3 weights, Composite IR, FX Reserves Total, M1/M2/M3 + Currency in Circulation, NPL/Classified/Overdue ratios ×3, Total Loans in HK. FX history goes back to 1981 (24 years daily). HKMA Open Data API catalogue enumerated via `apidocs.hkma.gov.hk` documentation pages.
28. ~~Vendor-agnostic loader~~ (2026-06-03) — `scripts/migrations/load_econ_indicator_from_playground.py` works for any vendor whose parquet matches `IndicatorRow` / `ObservationRow`. Used unchanged for FRED v1 → FRED v2 → FRED+IIP → HKMA v2. Pattern: 5 FK lookups via small `dim_*` JOINs, translation maps for vendor-specific spellings (`%`→`pct`, `FRED`→`fred`), MERGE dim by `(vendor_id, source_code)`, staging-table MERGE fact by PK. Idempotent + loud on FK miss.
29. ~~Migration 079: FRED imdr_code realignment to dim_country~~ (2026-06-05) — 9 imdr_code suffixes realigned: 6 `.GB → .UK` and 3 `.EZ → .EU` to match `dbo.dim_country.country_code` canonical (UK / EU). Companion changes: FRED `seed.yml` + `validate_and_seed.py` updated; loader `_COUNTRY_ALIASES = {"GB": "UK"}` map emptied. Zero string consumers of these imdr_codes existed in `src/`, `scripts/`, tests, or notebooks (fact joins are on integer FK, not the imdr_code string) so the rename was safe.

**Still open**:

4. **Vintage column** — keep from day one? (Adds 2 bytes/row; enables real-time history.) Default recommendation: yes. → Engineer will build with vintage; if you want it stripped, say so before the migration lands.
5. **`value DECIMAL(28,10)`** — enough for both pp-level rates and trillion-AUD balance-sheet figures. OK?
6. **`investor_breakdown_json NVARCHAR(MAX)`** on auctions — semi-structured here, or break into a child `fact_auction_investors` table? (Only matters at Phase 3; safe to defer.)
7. ~~FRED API key~~ — registered, lives under `IMDR_ECON_FRED_KEY` in `.env` (resolved 2026-06-02).
16. **Indian fiscal-year collision** (new): RBI Table 19C has an "FY 2025-26 mean" column that resolves to `obs_date = 2025-04-01` (FY start in April), which collides with monthly April 2025 data. Fix options: use FY-end (`2026-03-31`) as the date, or add a vintage/annotation field. Not blocking sample-quality validation; resolve before migration.
17. **RBI bulletin URL refresh** (new): the URL hashes change each month (`{N}T_BULL{ddmmyyyy}{hash}.XLSX`). Need to discover the current month's URLs from the bulletin landing page before downloading — currently hardcoded to May-2026 URLs in `fetch_bulletin.py`.
18. **CIMS migration** (new): DBIE deprecation planned (no firm date). When it lands, our FX-reserves API breaks; migration target is one of the 10 CIMS-family portals (BoP / FLAIR / SMS / FED / CISBI / FIRMS / Data Collector / ADEPT / CIMS DRM / Common Login).

---

## 7. Next steps

**Done this session (2026-06-03)**:

- [x] ~~Schema apply~~ — migrations 068–073 + 076 applied. `econ` schema live with 199 indicators / 272,893 obs.
- [x] ~~Vendor-agnostic loader~~ — `scripts/migrations/load_econ_indicator_from_playground.py` works for any vendor.
- [x] ~~FRED loaded~~ — 170 indicators / 80,810 obs (US deep + G10 OECD-mirror + IIP).
- [x] ~~HKMA loaded~~ — 29 indicators / 192,083 obs (HIBOR + FX + reserves + M-aggregates + banking quality + loans).
- [x] ~~Explore Korea MODS~~ — done. 10 CPI PDFs on OneDrive. See §2.6.
- [x] ~~Macro economy wiring map~~ — see [macro_economy_wiring_map.md](macro_economy_wiring_map.md). 14 countries × 16 clusters per-country tracker.

**Open — next data loads** (loader is ready, just need to point it at each vendor):

- [ ] **Load Stats NZ** — `--vendor statsnz`. Today's parquet is 301 indicators / 1,622 obs from one CPI release; multi-release backfill is a separate task.
- [ ] **Load RBI FX reserves** — `--vendor rbi`. 5 indicators / 1,305 weekly obs. May need imdr_code namespace decision (RBI FX is `rbi/` vendor or split?).
- [ ] **Load RBI Bulletin** — `--vendor rbi` (same vendor). 31 indicators / 168 obs (Table 27 + Table 19C). Resolve §6 #16 (Indian FY collision) before load.
- [ ] **C&SD (Hong Kong)** — new vendor needed for HK CPI / GDP / unemployment / trade. Fills the left half of HK on the wiring map (currently all ❌). Explore at `data.gov.hk`.
- [ ] **KOSIS** — first OpenAPI fetcher (`playground/econ/kosis/fetch_bop.py`) exists. Extend to CPI / GDP / IIP / unemployment via the KOSIS↔ECOS `tblId` map, then load via the canonical loader. KOSIS unlocks Korea's left half of the wiring map (currently all ❌ except the MODS PDFs which aren't parsed yet).

**Open — fetcher work**:

- [ ] **Korea — map remaining MODS boards**: Business Trends / Monthly Industrial Statistics (IIP) / Foreign Trade / Services Index / Population. ~4-line dict add per board via `explore_mods.py` snapshot of the board's listing URL.
- [ ] **Korea — backfill run**: once boards mapped, `python -m playground.econ.mods.fetch --boards all --max-pages 5 --since 2025-01-01` to pull ~18 months of all available macro releases to OneDrive.
- [ ] **Korea — PDF text parsing**: extract headline numbers from MODS PDFs (`pdfplumber` over the OneDrive copy → `econ.fact_indicator`).
- [ ] **Write production RBA fetcher** (currently only discovery samples exist) — Akamai handling via headed Playwright; CSV parsing is mechanical.
- [ ] **Write production ABS fetcher** (XLSX path; SDMX path TBD once dataflow keys decoded).
- [ ] **Write the remaining ~10 RBI Bulletin per-table parsers** (Money Stock 6 / Reserve Money 11 / WPI 22 / IIP 23 / Foreign Trade 32 / FX Reserves bulletin 33 / NEER-REER 37 / BoP 40 / RBI L&A 2 / Select Economic Indicators 1) when desk asks for them.
- [ ] **Send the RBNZ whitelisting email** to `Servicedesk@rbnz.govt.nz` (draft in session log; not yet sent).
- [ ] **Delete obsolete KOSIS Playwright artefacts** — `playground/econ/kosis/capture_download.py` was written for the SPA-scrape path that's now obsoleted by the OpenAPI. `kosis_explore/` snapshots can stay as reference. The `fetch_bop.py` OpenAPI fetcher is what production uses now.

**Open — production wiring** (per CLAUDE.md "no prod wiring without permission"):

- [ ] **Build daily-scrape templates** at `scripts/econ/{vendor}/{vendor}_daily.py` — thin wrappers that call existing fetch + load. NO scheduler registration yet; flips on once user signs off.
- [ ] **Register in `scripts/imdr_daily.py`** with release-time-aware schedule per vendor. Defer until templates are reviewed.
- [ ] Add a recurring Linear issue for **release-calendar curation** — each source's cadence needs to be honoured and calendars drift.

**Open — FRED gap-fill (§8.1 of wiring map)**:

- [ ] Find correct FRED codes for AU/EZ CPI YoY, CH Unemployment + GDP, NZ Real GDP (5 candidates failed `/series` validation). Use `playground/econ/fred/search.py`.

**Open — design Qs** (deferred earlier):

- [ ] Sign-off on §6 #4–6 (vintage column, DECIMAL precision, investor-breakdown JSON shape) and #16–18 (RBI FY collision, bulletin URL refresh, CIMS migration).
