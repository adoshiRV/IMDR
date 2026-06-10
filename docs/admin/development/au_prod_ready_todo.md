# Australia — Prod-Ready TODO

Last updated: 2026-06-11

End-to-end checklist to take AU from discovery-complete to prod-live, mirroring Korea's 2026-06-10 reference end-state.

## Current state (audit, 2026-06-11)

**Track A — Data series (econ.fact_indicator):**
- **463 indicators / 397,053 obs** loaded across 5 vendors (ABS 178 / RBA 119 / AOFM 157 / Cotality 6 / FRED 3)
- 15/16 wiring-map cells ✅ (cell 3.1 ToT is the only ❌, explicitly derivable from ITPI ratio)
- 31 playground fetchers under `playground/econ/{abs,rba,aofm,cotality}/` (vendor-first; OK per playbook playground soft-preference, but Phase G promotion will move to `scripts/econ/au/{vendor}/`)
- Per-vendor playground docs at `docs/admin/econ/australia/_playground/{abs,rba,aofm,cotality}.md`
- Inventory at `docs/admin/econ/australia/australia_indicator_inventory.md` ✓
- Migrations 090 (cotality vendor) + 091 (`aud_th` unit) already applied
- Migrations 086 (vendor_category column) + 087 (KR official vendors) already in (cross-country)

**Track B — Filings (research.dim_report + Qdrant + SharePoint):**
- 10 playground fetchers at `playground/econ/au/govt/` (~67 items/day baseline)
- Inventory at `docs/admin/econ/australia/au_cb_documents.md` ✓
- Vendor seeds present for 6 of the 10 streams: rba (official_cb), abs (official_statistics), aofm (official_ministry), fred (official_cb), cotality (sell_side), westpac (sell_side)
- **3 vendor seeds MISSING**: `apra` (regulator) + `treasury_au` (ministry) + `nab` (sell_side)
- E2E ingest smoke proven 2026-06-11 — three paths confirmed working:
  - **body_text path** (report_id=6147, RBA Governor's Statement) → 2 Qdrant chunks, no SP mirror
  - **source-PDF path** (report_id=6148, RBA SMP May 2026) → 83 Qdrant chunks + SP at `2026/05/01/econ/au/rba/statement-on-monetary-policy-may-2026_4cb0a00a.pdf`
  - **HTML-render-to-PDF path** (report_id=6151, RBA Board Minutes 5 May 2026) → 9 Qdrant chunks + SP at `2026/05/05/econ/au/rba/minutes-of-the-monetary-policy-board-meeting-5-may-2026_8d53eb10.pdf`

## Known gaps before prod promotion

1. **`apra`, `treasury_au`, `nab` vendor seeds missing** — their filings can't be ingested without rows in `dbo.dim_vendor`
2. ~~**Westpac CCI PDF returns HTTP 500**~~ — **RESOLVED 2026-06-11**. Root cause: wrong host. Real URL pattern is `library.westpaciq.com.au/content/dam/public/westpaciq/secure/economics/documents/aus/{YYYY}/{MM}/er{YYYYMMDD}BullConsumerSentiment.pdf` (NOT `www.westpaciq.com.au/{YYYY}/{MM}/...`). All 6 probed 2026 PDFs return 200 OK direct over plain httpx, no auth needed despite the "secure" path segment. Discovered via the sell-side `crawler_westpac.py` reference at `playground/research/ingest/`. `fetch_westpac_cci.py` patched.
3. **No AU resolver module** — Korea has `scripts/econ/kr/govt/resolvers.py` per-agency body+PDF resolution recipes; AU needs the equivalent
4. **Cell 3.1 ToT not loaded** — derivable from ITPI ratio. Either ship a one-series derived loader OR leave as documented ❌ per playbook
5. **Identity checks never formally run** (playbook §Step 4) — recommended quality gate before declaring complete
6. **AiG PMI blocked** (Flourish-only viz; FRED API connection-fails from RV's network today)
7. **NAB BSI / Westpac CCI numeric extraction deferred** — only filing-discovery shipped; actual BSI/CCI numbers live inside the PDFs and require parsing

---

## Phase G — Data series → prod (per `econ_to_prod.md`)

### G.0 Pre-flight (no rule violation)

- [ ] Confirm zero `playground.*` imports in current scripts (none today — AU has no `scripts/econ/au/` yet)
- [ ] Draft migration `{NNN}_seed_cotality_dim_vendor.sql` — **already drafted as 090, already applied** (idempotent — leave as-is)
- [ ] Draft migration `{NNN}_seed_dim_unit_aud_th.sql` — **already drafted as 091, already applied** (idempotent)

### G.1 Promote shared helpers

- [ ] `git mv playground/econ/abs/_abs_common.py → src/imdr/domains/econ/abs_common.py` (drop leading `_`)
- [ ] `git mv playground/econ/rba/_rba_common.py → src/imdr/domains/econ/rba_common.py`
- [ ] `git mv playground/econ/rba/_rba_csv.py → src/imdr/domains/econ/rba_csv.py`
- [ ] `git mv playground/econ/aofm/_aofm_common.py → src/imdr/domains/econ/aofm_common.py`
- [ ] Update `_REPO_ROOT = Path(__file__).resolve().parents[N]` in each (typically `parents[4]` from `src/imdr/domains/econ/`)
- [ ] For any module with a raw-data cache (RBA samples dir), bake country into path: `_REPO_ROOT / "data" / "econ" / "au" / "rba" / ...`
- [ ] No `playground.*` imports allowed in `src/imdr/domains/econ/` — verify with `grep -r "playground" src/imdr/domains/econ/`

### G.2 Re-implement fetchers as country-first prod scripts

For each playground fetcher, create `scripts/econ/au/{vendor}/{vendor}_{topic}.py`:

**ABS (16 fetchers → ~16 files):**
- [ ] `scripts/econ/au/abs/abs_cpi.py`
- [ ] `scripts/econ/au/abs/abs_gdp.py`
- [ ] `scripts/econ/au/abs/abs_labour.py`
- [ ] `scripts/econ/au/abs/abs_lf_under.py`
- [ ] `scripts/econ/au/abs/abs_wpi.py`
- [ ] `scripts/econ/au/abs/abs_ppi_fd.py`
- [ ] `scripts/econ/au/abs/abs_retail.py`
- [ ] `scripts/econ/au/abs/abs_capex.py`
- [ ] `scripts/econ/au/abs/abs_lending.py`
- [ ] `scripts/econ/au/abs/abs_rppi.py`
- [ ] `scripts/econ/au/abs/abs_bop.py`
- [ ] `scripts/econ/au/abs/abs_bop_goods.py`
- [ ] `scripts/econ/au/abs/abs_trade_prices.py`
- [ ] `scripts/econ/au/abs/abs_gdp_expenditure.py`
- [ ] `scripts/econ/au/abs/abs_job_vacancies.py`
- [ ] `scripts/econ/au/abs/abs_iip.py`
- [ ] `scripts/econ/au/abs/abs_building_approvals.py`

**RBA (9 fetchers → ~9 files):**
- [ ] `scripts/econ/au/rba/rba_rates.py` (F1+F2 incl. TIB)
- [ ] `scripts/econ/au/rba/rba_fx.py` (F11.1)
- [ ] `scripts/econ/au/rba/rba_monetary.py` (D3)
- [ ] `scripts/econ/au/rba/rba_credit_balsheet.py` (D2+E1+E2+A2)
- [ ] `scripts/econ/au/rba/rba_icp.py` (I2 commodity index)
- [ ] `scripts/econ/au/rba/rba_reer.py` (F15)
- [ ] `scripts/econ/au/rba/rba_zerocoupon.py` (F17)
- [ ] **RBA live-refresh sourcing decision** — currently CSV snapshots; prod needs a Playwright auto-refresh OR scheduled manual capture into `data/econ/au/rba/{table}/`

**AOFM (5 fetchers → ~5 files):**
- [ ] `scripts/econ/au/aofm/aofm_foreign_holdings.py`
- [ ] `scripts/econ/au/aofm/aofm_portfolio_aggregate.py`
- [ ] `scripts/econ/au/aofm/aofm_term_premium.py`
- [ ] `scripts/econ/au/aofm/aofm_turnover.py`
- [ ] `scripts/econ/au/aofm/aofm_issuance_buybacks.py`
- [ ] **AOFM XLSX sourcing decision** — currently manual Edge download (corp-firewall block on Chrome/Playwright). Prod needs a documented monthly manual-refresh runbook OR IT whitelist for the host

**Cotality (1 fetcher → 1 file):**
- [ ] `scripts/econ/au/cotality/cotality_hvi.py` (Playwright daily snapshot)

**Each fetcher:** main() one-liner → `scripts.econ._runner.run_main(vendor, topic, fetch_fn, country_code="AU")`. Mandatory keyword-only `country_code` enforced by `_normalise_country_code`.

### G.3 Country orchestrators

- [ ] `scripts/econ/au/au_daily.py` — Cotality daily HVI (the only daily-cadence Track-A fetcher)
- [ ] `scripts/econ/au/au_weekly.py` — RBA F1/F2/F11.1 rate refresh (if Playwright auto-refresh wired) or skip
- [ ] `scripts/econ/au/au_monthly.py` — ABS monthly + RBA monthly + Cotality monthly aggregations
- [ ] `scripts/econ/au/au_quarterly.py` — ABS quarterly (GDP / BOP / IIP / CAPEX / RPPI) + AOFM monthly XLSX refresh window

Reference shape: `scripts/econ/kr/kr_{daily,weekly,monthly}.py`.

### G.4 Scheduler registration (GATED — explicit user OK required)

- [ ] Register `scripts.econ.au.au_daily` in `scripts/imdr_daily.py:PIPELINES`
- [ ] Register `scripts.econ.au.au_weekly` in `scripts/imdr_weekly.py:PIPELINES` (if used)
- [ ] Register `scripts.econ.au.au_monthly` in `scripts/imdr_monthly.py:PIPELINES`
- [ ] Register `scripts.econ.au.au_quarterly` in `scripts/imdr_quarterly.py:PIPELINES` (or fold into monthly)

### G.5 Code-review gate (HARD GATE)

- [ ] Run `imdr-code-reviewer` on the new `scripts/econ/au/` tree
- [ ] Verify zero `playground.*` imports
- [ ] Verify mandatory `country_code="AU"` on every `run_main()` call
- [ ] Verify `_REPO_ROOT` parent depth correct in promoted helpers

### G.6 Docs to update on prod-promotion

- [ ] Create `docs/admin/econ/australia/australia_prod_pipeline.md` (mirrors `korea/korea_prod_pipeline.md` shape)
- [ ] Update `docs/admin/econ/index.md` AU row status from "DB-LIVE (manual load)" to "LIVE"
- [ ] Update `docs/admin/econ/australia/index.md` — add "Loaded" section, mark playground references as historical
- [ ] Update `docs/admin/econ/australia/australia_indicator_inventory.md` — "Next moves" reflects prod registration

---

## Phase J — Filings → prod (per `econ_to_prod.md`)

### J.0 Pre-flight

- [ ] Verify `migrations/086_add_dim_vendor_category.sql` applied — **already applied** ✓
- [ ] E2E smoke (one filing through `ingest_filing` end-to-end) — **DONE 2026-06-11** ✓ (report_id 6147)

### J.1 Draft and apply per-country vendor seed

- [ ] Draft `migrations/{NNN}_seed_au_official_vendors.sql` with:
  - `apra` — Australian Prudential Regulation Authority, `vendor_category='official_regulator'`, vendor_type='web'
  - `treasury_au` — Department of the Treasury, `vendor_category='official_ministry'`, vendor_type='web'
  - `nab` — National Australia Bank (private bank), `vendor_category='sell_side'`, vendor_type='web'
- [ ] Apply migration (GATED — privileged DB account)
- [ ] Verify `vendor_category` set on existing AU vendors (`abs`, `aofm`, `cotality`, `fred`, `rba`, `westpac`) — already in. May need to recategorise `cotality` from `sell_side` to something more specific if relevant

### J.2 Build AU resolvers module

Korea has `scripts/econ/kr/govt/resolvers.py` with per-agency body+PDF recipes. AU needs the equivalent.

**Resolver contract — every AU stream produces `pdf_bytes`** (decided 2026-06-11). Body-text-only ingest is explicitly off the table for AU — we want every stream to land in SharePoint, identical to Korea's PDF streams. Two transport flavours:

| Flavour | Use case | How |
|---|---|---|
| **Publisher PDF** | Source publishes a PDF (RBA SMP / FSR, AOFM Annual Report, NAB / Westpac CCI when cookies work, APRA glossary PDFs) | Resolver fetches the `.pdf` URL via Playwright `ctx.request.get` (re-using the warmed Akamai/CDN cookie from page navigation) |
| **HTML-rendered PDF** | HTML-only source (RBA Governor's Statement / Board Minutes / Speeches, ABS release commentary, Treasury detail pages, NAB articles) | Resolver does `page.emulate_media("print")` then `page.pdf(format="A4", print_background=True, margin=12mm)` on the rendered article |

Both produce `pdf_bytes` → `FilingInput(pdf_bytes=...)` → `ingest_filing` → DB row + Qdrant chunks + SharePoint mirror, indistinguishable in `research.dim_report`.

**Decision per stream:**

- [ ] `scripts/econ/au/govt/resolvers.py` covering:
  - **RBA Governor's Statement / Board Minutes / Speeches** (HTML-only): render via Playwright `page.pdf()` — proven 2026-06-11 with report_id 6151 (Board Minutes, 130 KB rendered PDF, 9 chunks, SP mirror ✅)
  - **RBA SMP / FSR** (HTML + publisher PDF): fetch the publisher PDF via Playwright `ctx.request.get` — proven 2026-06-11 with report_id 6148 (SMP, 4.9 MB publisher PDF, 78 pages, 83 chunks, SP mirror ✅)
  - **Treasury publications**: plain httpx render → fallback to render-to-PDF via headless Playwright (no Akamai gate, so headless is fine)
  - **APRA quarterly stats**: each page has BOTH XLSX downloads AND a glossary PDF. Option A — render landing page to PDF; keep XLSX URL in `tags`. Option B — fetch the glossary PDF as primary, keep XLSX URL in `tags`. Pick A for now (page narrative is more useful than glossary)
  - **ABS commentary** (CPI / Labour Force / National Accounts): plain httpx render → render-to-PDF
  - **Westpac CCI**: **investigate PDF 500** — likely needs cookie/session from the topic page navigation. Fallback: render article landing page to PDF if PDF stays gated
  - **NAB BSI**: plain httpx → render article body to PDF

### J.3 Promote playground fetchers + orchestrator to `scripts/econ/au/govt/`

- [ ] `git mv playground/econ/au/govt/{_http.py, _models.py, _playwright.py, fetch_*.py} → scripts/econ/au/govt/`
- [ ] **Rename** `daily_pull.py` → `ingest_filings.py` (Korea convention)
- [ ] Adjust internal imports (sys.path.insert pattern survives the move; no fix needed)
- [ ] Verify zero `playground.*` imports: `grep -r "playground" scripts/econ/au/govt/`

### J.4 Wire the country daily orchestrator

- [ ] `scripts/econ/au/au_daily.py` — calls `scripts.econ.au.govt.ingest_filings --ingest` (note: same `au_daily.py` ALSO carries the Cotality HVI daily fetcher per G.3)
- [ ] Inline filings-aware email (per Korea's `scripts/econ/kr/kr_daily.py:~250 LoC` pattern)
- [ ] Register `scripts.econ.au.au_daily` in `scripts/imdr_daily.py:PIPELINES` (GATED — explicit user OK)

### J.5 Code-review gate (HARD GATE)

- [ ] Zero `playground.*` imports in `scripts/econ/au/govt/`
- [ ] `filings.ingest_filing()` honours both `pdf_bytes` and `body_text` paths — already does
- [ ] No relevance-filter / classifier code copied from sell-side
- [ ] Per-agency fetchers all return uniform `FetchResult` of `FilingItem` — ✓
- [ ] Runtime state at `data/econ/au/govt/{vendor}/seen.json` + `snapshots/`; orchestrator log at parent — needs adjustment from current playground layout
- [ ] All AU vendor inserts include `vendor_category`

### J.6 Docs to update

- [ ] Create `docs/admin/development/au_govt_filings.md` (tracker mirroring `kr_govt_filings.md`)
- [ ] Update `docs/admin/econ/australia/index.md` — Phase H/J both LIVE
- [ ] Update `docs/admin/econ/australia/au_cb_documents.md` — status from "discovery scaffold + 10 fetchers" to "LIVE in prod"

### J.7 Westpac PDF gating — separate sub-task

- [ ] **Investigate Westpac CCI PDF 500** — visit westpaciq.com.au with a fresh browser session, capture cookies + headers needed to fetch the PDF directly
- [ ] Update `fetch_westpac_cci.py` to either (a) carry the cookie/session, or (b) fall back to body-text from the article landing page
- [ ] Re-verify with E2E smoke after fix

---

## Track-A specific TODOs (data side)

### Cell 3.1 ToT — decide derived series or leave as ❌

- [ ] **Option A** (close the cell): ship one quarterly derived indicator `ABS.TOT.NET_BARTER.AU = ITPI_EXP_HEADLINE_INDEX / ITPI_IMP_HEADLINE_INDEX × 100`. Trivial — both inputs already in DB. Closes the last red cell.
- [ ] **Option B** (leave as documented ❌): keep the playbook-permitted note in the inventory; analytics layer derives on read.
- [ ] Decide which, mark in inventory

### Identity-check smoke (playbook §Step 4 quality gate)

- [ ] CA ≈ FA − E&O for AU BOP — pull ABS.BOP.* from DB and verify CA matches sum of components within rounding
- [ ] Goods exports − imports = Goods balance from ABS.BOP_GOODS
- [ ] DI + PI + Deriv + OI + Reserves = FA total from ABS.BOP financial account
- [ ] Real GDP ≈ weighted sum of expenditure components from ABS.ANA_EXP
- [ ] M2 growth = currency + deposits weighted (from RBA D3)
- [ ] Document results in `australia_indicator_inventory.md` §quality-bar

### Indicator value spot-check (sample-of-5)

Pick 5 random `ABS.*` / `RBA.*` / `AOFM.*` / `COTALITY.*` indicators, query the latest value, compare against the source page. Catches loader-units bugs (the kind that produced the earlier `aud_th` issue + IIP sign-convention surprise).

---

## Misc / nice-to-have

- [ ] **AiG PMI** — retry FRED-mirror search when corp-firewall transient clears, or design a Playwright + Flourish-iframe scraper. Currently blocked.
- [ ] **State govt bonds (semis curve)** — TCV/NSWTC/QTC/WATC/SAFA — 3 of 5 sites Akamai-gated, would be a half-day per source. Defer until requested.
- [ ] **RBA F16 per-bond AGB yields** (62 ISINs) — defer to future `dbo.dim_bond_instrument` schema rather than `econ.dim_indicator`. Snapshot already captured.
- [ ] **Westpac CCI / NAB BSI numeric extraction** — currently filing-discovery only. Numeric BSI/CCI values live inside the PDFs — extraction work for the research-doc pipeline, not Track A.
- [ ] **Playground tidy-up** — `git mv playground/econ/{abs,rba,aofm,cotality} → playground/econ/au/{abs,rba,aofm,cotality}` to align with playground country-first soft preference. Mechanical-promotion ergonomics; not a rule violation if left as-is.

---

## Reference Korean tree to mimic

| Layer | Korea path |
|---|---|
| Domain library | `src/imdr/domains/econ/{kosis_*,reb_*}.py` |
| Per-vendor fetchers (A) | `scripts/econ/kr/kosis/`, `scripts/econ/kr/reb/` |
| Per-agency fetchers (B) | `scripts/econ/kr/govt/fetch_*.py` |
| Resolvers (B) | `scripts/econ/kr/govt/resolvers.py` |
| Govt-filings daily entry (B) | `scripts/econ/kr/govt/ingest_filings.py` |
| Country DAILY orchestrator (B) | `scripts/econ/kr/kr_daily.py` |
| Country WEEKLY/MONTHLY orchestrator (A) | `scripts/econ/kr/kr_{weekly,monthly}.py` |
| Scheduler wiring | `scripts/imdr_{daily,weekly,monthly}.py:PIPELINES` |
| Track A prod-pipeline doc | `docs/admin/econ/korea/korea_prod_pipeline.md` |
| Track B execution tracker | `docs/admin/development/kr_govt_filings.md` |

`diff` against Korea is the fastest correct path for any AU promotion step.
