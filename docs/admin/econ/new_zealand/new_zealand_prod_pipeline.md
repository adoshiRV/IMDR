# New Zealand — Track A production pipeline

Last updated: 2026-06-19

Stats NZ macro data, promoted from playground to production per [`../econ_to_prod.md`](../econ_to_prod.md) Phase G. **Track A LIVE in DB** (loaded to `econ.dim_indicator` + `econ.fact_indicator`). **Wired into `scripts/imdr_monthly.py:PIPELINES` 2026-06-18** — alongside KR/ID/AU; the user runs `imdr_monthly` on the weekly Windows-task cadence (~4×/month) per [[feedback-monthly-via-weekly-cadence]], which catches the monthly ECT/OMT releases.

## Architecture

Two access paths, one vendor (`statsnz`, `dbo.dim_vendor.id=25`, `official_statistics`):

| Path | Library | Transport | Datasets |
|---|---|---|---|
| **Release-page CSV** | `src/imdr/domains/econ/statsnz_common.py` | plain `httpx` (Chrome UA, no Playwright) | CPI, GDP, BoP/IIP |
| **Infoshare** | `src/imdr/domains/econ/statsnz_infoshare.py` | headless Playwright (ASP.NET tree-nav → select-all → wide-CSV) | PPI, CGPI, OTI, HLPI, LCI, QES, ECT, OMT, RTS, HLFS |

Infoshare quirks (pxID non-stable, session via tree postback, 2-dim wide-CSV) are documented in the module header and in [[reference-statsnz-infoshare-recipe]]. The persistent browser profile lives at `data/econ/nz/statsnz/_pw_profile` (gitignored).

## Production fetchers

`scripts/econ/nz/statsnz/statsnz_{topic}.py`, each delegating to `scripts.econ._runner.run_main(vendor="statsnz", topic=…, fetch_fn=run_fetch, country_code="NZ")`:

| Topic | Path | Cell | Cadence |
|---|---|---|---|
| cpi | `statsnz_cpi.py` | 2.4 | quarterly |
| gdp | `statsnz_gdp.py` | 1.4 | quarterly |
| bop | `statsnz_bop.py` | 3.2/3.3 | quarterly |
| ppi | `statsnz_ppi.py` | 2.2 | quarterly |
| cgpi | `statsnz_cgpi.py` | 2.2 | quarterly |
| oti | `statsnz_oti.py` | 3.1 | quarterly |
| hlpi | `statsnz_hlpi.py` | 2.4 | quarterly |
| lci | `statsnz_lci.py` | 2.3 | quarterly |
| qes | `statsnz_qes.py` | 1.4/2.3 | quarterly |
| ect | `statsnz_ect.py` | 1.1 | monthly |
| omt | `statsnz_omt.py` | 1.3 | monthly |
| rts | `statsnz_rts.py` | 1.1 | quarterly |
| hlf | `statsnz_hlf.py` | 1.4 | quarterly |
| cpi_core | `statsnz_cpi_core.py` | 2.4 | quarterly — **NOT in `nz_monthly.py` yet; gated pending user OK** |

Deferred (not promoted): **BLD** (building consents — every monthly Infoshare table times out generating; cell 1.1 covered by ECT+RTS). The shallow release-XLSX HLFS is superseded by `statsnz_hlf` (Infoshare, full history 1986→).

`statsnz_cpi_core.py` (added 2026-06-19) covers 42 quarterly series via Infoshare — two source tables under `Economic indicators › Consumers Price Index - CPI`:
- **27 exclusion cores** (`STATSNZ.CPI.EXCL.{grouping}.NZ`) — index levels, 1988-Q4→. Includes the ex-food-&-energy analog (`ALL_GROUPS_LESS_FOOD_GROUP_HOUSEHOLD_ENERGY_SUBGROUP_AND_VEHICLE_FUELS`, index ≈ 1323 at latest period).
- **15 statistical cores** (`STATSNZ.CPI.TRIM.QUARTERLY_*.NZ`) — QoQ % change: 5/10/15/20/25/30% trimmed means, weighted median (incl. tradable/non-tradable splits), 10/25/75/90th weighted percentiles. The 93 "Annual *" weight-base vintage columns are dropped wholesale.

**The standard CPI release-CSV carries no core / analytical series — Infoshare is the only source for these.** To register, add `statsnz_cpi_core` to `PIPELINES` in `nz_monthly.py` and get explicit user sign-off.

## Cadence + orchestrator

`scripts/econ/nz/nz_monthly.py` runs all 13 fetchers as sequential subprocesses via `scripts.econ._country_runner.run(...)`, `frequency_scope=["MONTHLY","QUARTERLY"]`. Monthly + quarterly fold under one trigger (idempotent MERGE on PK makes over-running free); per [[feedback-monthly-via-weekly-cadence]] the monthly orchestrator is folded into the weekly Windows task by the user. **No `nz_weekly.py`** (no weekly-cadence Stats NZ series).

## Invocation + DB load

```
# one topic (writes data/econ/nz/statsnz/{topic}/{Y}/{M}/{D}/ then MERGEs to DB):
python -m scripts.econ.nz.statsnz.statsnz_cpi
python -m scripts.econ.nz.statsnz.statsnz_ppi --no-load     # parquet only
python -m scripts.econ.nz.statsnz.statsnz_cpi --no-parquet  # counts only

# full country run:
python -m scripts.econ.nz.nz_monthly
```

The loader (`scripts.migrations.load_econ_indicator_from_playground`, invoked by `run_main`) resolves FKs against `dbo.dim_vendor / dim_country / dim_frequency / dim_unit` + `econ.dim_indicator_category` and aborts loudly on any miss. **No migration was needed**: vendor `statsnz`, country `NZ`, all units (incl. `th_persons`, `nzd_mn`, `index`) and categories already exist. dim_indicator MERGE key = `(vendor_id, source_code)`; fact MERGE key = `(indicator_id, obs_date, vintage)` — fully idempotent.

## Failure modes

- **Infoshare slow tables**: LCI industry/occupation cross-tabs and all monthly BLD tables time out generating server-side (>120s, retried once). The fetchers either restrict to the fast tables (LCI headline) or are deferred (BLD). Not a parser bug — same-size QES tables load fine.
- **Playwright**: each Infoshare fetcher spawns one headless Chromium and navigates the browse tree; a full `nz_monthly` run is ~20-30 min (10 browser sessions). Acceptable on monthly/weekly cadence.

## Track B (govt / central-bank documents) — planned

CB events / policy docs (RBNZ Monetary Policy Statements, OCR decisions, speeches) follow the Korea Track B pattern ([`../econ_to_prod.md`](../econ_to_prod.md) Phase J; reference impl `scripts/econ/kr/govt/` + `scripts/econ/kr/kr_daily.py`). Status + plan:

- **Vendor already seeded**: `rbnz` exists in `dbo.dim_vendor` (`official_cb`, id=28) from migration 086 — **no new migration needed**.
- **Generic ingest reused**: `src/imdr/research/filings.py:ingest_filing()` is implemented and vendor-agnostic (PDF or body_text → chunk → embed → `research.dim_report` + Qdrant + SharePoint). No relevance/classifier filter (official sources always-keep).
- **To build**: `scripts/econ/nz/govt/{_models.py,_http.py,resolvers.py,fetch_rbnz.py,ingest_filings.py}` + `scripts/econ/nz/nz_daily.py` (mirror Korea). RBNZ sources: MPS (`rbnz.govt.nz/monetary-policy/monetary-policy-statement`), OCR decisions (`/monetary-policy/monetary-policy-decisions`), speeches (`/hub/publications/speech`).
- **⚠ Cloudflare gate (probed 2026-06-18)**: the RBNZ doc pages (MPS / OCR decisions / speeches) return **HTTP 403 "Just a moment…"** (Cloudflare JS interstitial) to **both headless AND headed** Playwright with the persistent profile — headed did not auto-clear within ~20s. Stealth/anti-detection is a hard no ([[feedback-no-anti-detection-research]]). The legit unblock (mirrors how Infoshare was cracked) is a **user-supplied `cf_clearance` + `__cf_bm` cookie** from a real browser session that has passed the challenge, reused in the Playwright `ctx` — or a DevTools "Copy as cURL" of an authenticated MPS request. Until then `fetch_rbnz` / `nz_daily` are **held** (user decision 2026-06-18). Everything downstream (vendor row, `ingest_filing`, orchestrator shape, SharePoint layout) is ready; this is the only blocker.

## Related

- [`new_zealand_indicator_inventory.md`](new_zealand_indicator_inventory.md) — playground tracker + per-fetcher table
- [`index.md`](index.md) — landing page
- [`../econ_to_prod.md`](../econ_to_prod.md) — promotion playbook (Phase G = Track A, Phase J = Track B)
- [`../korea/korea_prod_pipeline.md`](../korea/korea_prod_pipeline.md) — Track A reference
