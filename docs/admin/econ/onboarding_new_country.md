# Onboarding a new country — econ data playbook

Last updated: 2026-06-10

> ## ⛔ HARD RULE — directory layout (data strict, scripts strict, playground free-form)
>
> Codified 2026-06-10 after the country-first refactor (Phases 1-3) reshuffled every existing vendor into per-country buckets. This rule is **non-negotiable** for new country onboardings — don't recreate the vendor-first mess we just unwound.
>
> | Tree | Layout | Why |
> |---|---|---|
> | `data/econ/` | **STRICTLY country-first.** `data/econ/{cc}/{vendor}/{topic}/{Y}/{M}/{D}/...` for series, `data/econ/{cc}/govt/{vendor}/...` for filings. No vendor-at-root, ever — even for multi-country vendors (BIS gets sliced: `data/econ/id/bis/`, `data/econ/in/bis/`). | The on-disk artefact tree is the inventory of who-publishes-what for each country. Vendor-at-root collapses Indonesia and India's BIS slices into one folder, losing the country anchor. |
> | `scripts/econ/` | **Country-first.** `scripts/econ/{cc}/{vendor}/{vendor}_{topic}.py` for series, `scripts/econ/{cc}/govt/...` for filings. Country orchestrators at `scripts/econ/{cc}/{cc}_{cadence}.py`. | Production code should be predictable and country-scoped. New fetchers always land under the country, never under a vendor folder at the root. |
> | `playground/econ/` | **Free-form.** Vendor-first is allowed, multi-country probes are allowed, profile dirs are allowed. Soft preference (not enforced) — when discovery work clearly belongs to a single country, prefer `playground/econ/{cc}/{vendor}/` to make the eventual promotion mechanical. | Discovery is exploratory; messy ad-hoc shapes during a probe are fine. The strict layout kicks in **at promotion**, not during discovery. |
> | `src/imdr/domains/econ/` | Unchanged — library modules are country-agnostic, keyed by vendor name. | Library code is reused across countries; it doesn't have a "country" axis. |
>
> Mandatory `country_code` plumbing: `scripts/econ/_runner.py:run_main(...)` takes a **mandatory keyword-only** `country_code` arg. Every prod fetcher must pass an explicit 2-letter ISO code. `_normalise_country_code` raises `TypeError` (non-string) or `ValueError` (wrong shape) — no silent rogue paths.
>
> Multi-country vendors (BIS, FAO, FRED-mirrors of foreign series) emit per-country slices that each live under the country's tree. The same Python module may produce data for multiple countries — that's fine; it just gets invoked once per country with the appropriate `country_code` and `topic`.

> ## ⛔ HARD RULE — playground-only until user sign-off
>
> **Everything in this playbook stays inside `playground/econ/` (any shape — see the layout rule above) until the work is finished AND the user has explicitly approved promotion.**
>
> Do NOT, under any circumstance, without explicit user OK:
> - Create files under `scripts/econ/{cc}/{vendor}/` or `src/imdr/domains/econ/`
> - Register pipelines in `scripts/imdr_{daily,hourly,weekly,monthly,quarterly,retry}.py:PIPELINES`
> - Apply migrations that touch `dbo.dim_vendor`, `econ.*`, or any prod schema
> - Write to `econ.fact_indicator`, `research.dim_report`, Qdrant, or SharePoint from a production code path
>
> Build the playground discovery + manifest-only output, summarise findings to the user, and **stop**. Promotion is a separate, gated workflow — see **[`econ_to_prod.md`](econ_to_prod.md)** for the prod-promotion playbook (Track A Phase G + Track B Phase J). Never inline prod-promotion work into a discovery PR.
>
> Reinforces [[feedback-no-prod-wiring-without-permission]] + [[feedback-playground-only-for-exploration]].

The workflow for adding a new country has **two parallel tracks**:

- **Track A — Data series** (Steps 1-5 + Phase G): time-series indicators that land in `econ.fact_indicator`. Korea ([korea/](korea/)) + Indonesia ([indonesia/](indonesia/)) are the worked references.
- **Track B — Government & CB documents** (Phase H): policy text (MPC minutes, SMP, FSR, Budget Papers, ministry press) that lands in `research.dim_report` + Qdrant + SharePoint — same RAG corpus as sell-side research, discriminated by `dim_vendor.vendor_category`. Korea ([korea/govt_doc_sources.md](korea/govt_doc_sources.md)) + Australia ([australia/au_cb_documents.md](australia/au_cb_documents.md)) are the worked references.

The two tracks share the country folder + index.md but produce different artifacts, hit different storage layers, and use different transports. Don't conflate.

The **what** lives in [country_econ_blueprint.md](country_econ_blueprint.md) (indicator catalogue) and [macro_economy_wiring_map.md](macro_economy_wiring_map.md) (16-cell coverage map).
The **where** lives in the country-specific `_playground/{vendor}.md` notes you'll write along the way.

## Folder you'll create

```
docs/admin/econ/{country}/
├── index.md                          ← country landing page (required)
│
│   ── Track A: data series ──
├── {country}_indicator_inventory.md  ← canonical "what we have" (mirrors blueprint §1-4)
├── {vendor}_api_reference.md         ← per-vendor API mechanics, if API has quirks
├── {country}_coverage_plan.md        ← maps wiring-map cells to vendor table IDs
├── {country}_indicator_targets.md    ← shopping list with imdr_code + source_code
│
│   ── Track B: govt/CB documents (Phase H) ──
├── {country}_govt_doc_sources.md     ← agency × stream inventory + Tier 1/2/3 + crawl-pattern clusters
│                                       (Korea uses `govt_doc_sources.md`; AU uses `au_cb_documents.md`;
│                                       both names are acceptable — country folder picks one and sticks)
│
└── _playground/                      ← only when playground/econ/{vendor}/ code exists
    ├── index.md                      ← only when multiple vendors
    ├── {vendor}.md                   ← one per playground/econ/{vendor}/ folder
    └── ...
```

You don't need every doc on day one. The minimum to graduate from "discovery only" to "loaded" on **Track A** is: `index.md` + `_playground/{vendor}.md` + parquet at `playground/econ/{vendor}/sample_output/`. The minimum to graduate **Track B** is: `index.md` § Policy & fiscal document sources + `{country}_govt_doc_sources.md` + `playground/econ/{cc}/govt/fetch_*.py` per Tier-1 agency + a `daily_pull.py` orchestrator writing manifest-only snapshots (no DB writes yet). A source-catalogue-only country (no playground code yet) needs only `index.md`.

### Naming conventions

- **Country folder name** = lowercase + `_`-separated form of `dbo.dim_country.display_name`. E.g. `country_code=US` → "United States" → `united_states/`; `EU` → "Eurozone (TARGET2)" → `eurozone/` (drop the parenthetical qualifier). Cross-check the canonical list with `SELECT country_code, display_name FROM dbo.dim_country`.
- **Country codes in docs** use `dbo.dim_country.country_code` (e.g. `EU` not `EA`, `UK` not `GB`, `KR` not `KOR`).
- **Established exception**: `korea/` (not `south_korea/`). KR's `dim_country.display_name` is "South Korea" but the folder uses the common short-form. Don't rename — many inbound links across MEMORY.md, topics/, and memory files depend on this path.

### Required country index.md structure

Follow this section order so anyone reading the tree can predict where to look:

```markdown
# {Country} — Econ Documentation

Last updated: YYYY-MM-DD

{1-2 line intro: who publishes what; status (LIVE / discovery only / source catalogue only).}

## Access paths
{Path × Auth × Speed × Coverage × Status table. Include FRED OECD mirror row if any partial coverage flows through it.}

## What's loaded            ← only when status is LIVE
{Counts in econ.fact_indicator; coverage summary.}

## Pre-prod                 ← only when _playground/ exists
- [`_playground/{vendor}.md`](_playground/{vendor}.md) — one bullet per vendor

## Policy & fiscal document sources
{Document-style sources — statements, minutes, projections, speeches. Source × URL × Cadence × Notes table. Not econ.fact_indicator material — feeds the research-document pipeline.}

## Source-agency contact    ← optional, only when known
{Agency / email / phone / legal authority}

## Related
- Wiring-map link (§7.N)
- Onboarding playbook link
- Country-specific cross-refs
```

### Crawl-complexity flag for document sources

When listing URLs in the **Policy & fiscal document sources** table, distinguish direct-archive URLs from search-hub URLs. Same row shape hides very different crawl complexity:

| Pattern | Crawl complexity | Example |
|---|---|---|
| **Direct archive URL** | Low — single GET, parse list, follow links | BoJ: `boj.or.jp/en/mopo/mpmsche_minu/index.htm` |
| **Search-hub with keyword filter** | Medium — search-listing scraper required | BoK: `bok.or.kr/eng/singl/newsDataEng/list.do` + `?kwd=...` |
| **JS-rendered listing (`networkidle`)** | High — Playwright + settle delay | per [[feedback-js-rendered-dont-bail]] |
| **SharePoint `.aspx` listing** | Medium — structured HTML lists, often paginated | BSP: `bsp.gov.ph/SitePages/.../...aspx` |
| **AEM CMS (`/content/dam/...`)** | Low — predictable PDF URL patterns | BoT: `bot.or.th/content/dam/bot/documents/en/...` |
| **Akamai-gated (HTTP 403 to plain GET)** | High — Playwright + persistent profile | RBA, RBNZ |

Note the crawl complexity per row when it differs from "direct GET". Helps the downstream document-pipeline planner pick the right tooling.

---

## Step 1 — Fork the blueprint into a country tracker

Copy [country_econ_blueprint.md §1-4](country_econ_blueprint.md) (the four engines × four cells × N indicators) into `docs/admin/econ/{country}/{country}_indicator_inventory.md`. Mark each row with one status marker:

| Marker | Meaning |
|---|---|
| ✅ | At least one indicator on disk + production fetcher registered |
| ⚠ | Partial — headline present, sub-bullets missing |
| ❓ | Unknown source — needs catalogue browse |
| ❌ | Not available (vendor-gated, expected gap) |

At the top of the country file, paste this 4×4 tracker template (replace `XX` with ISO-3 code):

```
| Cell | Status | Headline indicator (vendor) | Sub-bullets covered | Gap |
|---|:---:|---|:---:|---|
| 1.1 Private Demand    | ? | XX.RETAIL.* | x/8 | |
| 1.2 Fiscal Demand     | ? | XX.FISCAL.* | x/6 | |
| 1.3 External Demand   | ? | XX.BOP.GOODS.* | x/10 | |
| 1.4 Macro Core        | ? | XX.GDP.GDP.QOQ_SA | x/15 | |
| 2.1 Input Costs       | ? | XX.IMPORT_PRICE.* | x/5 | |
| 2.2 Producer Prices   | ? | XX.PPI.TOTAL | x/7 | |
| 2.3 Domestic Costs    | ? | XX.WAGE.* | x/10 | |
| 2.4 CPI Pressure      | ? | XX.CPI.HEADLINE.YOY | x/13 | |
| 3.1 Terms of Trade    | ? | XX.TOT.NET_BARTER | x/4 | |
| 3.2 Current Account   | ? | XX.BOP.CA.TOTAL | x/10 | |
| 3.3 Capital Account   | ? | XX.BOP.FA.TOTAL | x/16 | |
| 3.4 FX / REER         | ? | (market data + BIS REER) | x/9 | |
| 4.1 Demand Trans      | ? | XX.LEND_STANCE.* | x/12 | |
| 4.2 Balance Sheets    | ? | XX.HH_CREDIT / NPL | x/15 | |
| 4.3 Fin Conditions    | ? | XX.RATES.* + spreads | x/15 | |
| 4.4 Policy Reaction   | ? | XX.POLICY_RATE + M2 | x/16 | |
```

---

## Step 2 — Resolve each ❓ via the vendor cascade

For every ❓ row, browse the country's primary central bank + statistical office. Always prefer the source highest in the cascade that actually publishes the series:

| Tier | Source type | Why preferred |
|---|---|---|
| 1 | **Central bank direct API** | Authoritative publisher; matches the printed bulletin |
| 2 | **National statistical office API** | Authoritative for production-side data (CPI, labour, retail) |
| 3 | **Customs / Treasury direct API** | Authoritative for fiscal, trade |
| 4 | **Multilateral mirror** (FRED / OECD / IMF / BIS / World Bank) | Standardised + reliable, but may lag and lose detail |
| 5 | **Market-data vendor** (Citi / BBG) | Acceptable for rates, FX, equity; not for econ counterparts |
| 6 | **Web scrape / PDF parse** | Last resort; high maintenance, fragile |

Tag the chosen tier on every row — makes downstream vendor swap-outs traceable.

### Cadence ladder

Use the highest-cadence available *that's still authoritative*. Don't synthesise — a monthly series interpolated to daily is not daily data.

```
DAILY  →  WEEKLY  →  MONTHLY  →  QUARTERLY  →  ANNUAL  →  EVENT
```

For each cell, the *minimum acceptable* cadence is given in the blueprint. Higher is fine.

---

## Step 3 — Headline-first, in this build order

Don't chase sub-bullets before headlines. Most countries hit 12/16 ✅ within 3-4 days using this order; the last 4 cells are usually vendor-gated and warrant separate work.

1. **CPI** (cell 2.4) + **GDP** (1.4) — the headline macro pair, always available
2. **Policy rate** (4.4) + **money-market + key bond yields** (4.3) — market-side anchors
3. **BoP** (3.2 + 3.3) — usually a single quarterly publication
4. **Labour** (1.4 labour leg) — separate stat-office publication
5. **PPI** (2.2) + **Import/Export prices** (2.1) — pipeline-inflation
6. **Trade indices** (1.3) + **Terms of Trade** (3.1)
7. **Fiscal** (1.2) — often annual; comes later
8. **Retail sales** (1.1) — KOSTAT-equivalent monthly
9. **Sentiment surveys** (CCI + BSI) — 1.1 + 1.4
10. **Lending standards** (4.1) — quarterly survey
11. **Balance sheets** (4.2) — HH credit + corp ratios
12. **Monetary aggregates** (4.4) — M1/M2/Lf
13. **FX reserves + REER** (3.4) — usually CB direct, sometimes blocked
14. **Industrial Production + Capacity Util** (1.4/2.3) — KOSTAT-equivalent
15. **Macroprudential event log** (4.4)

### Cells that are *expected* to be ❌

Acknowledge these in the tracker rather than blocking on them:

| Cell | Common gap | Workaround |
|---|---|---|
| 1.4 Macro Core — PMI | S&P Global is paid; FRED has limited coverage | Use BSI Mfg as the country-specific equivalent |
| 2.3 Domestic Costs — wages | Few EM publish monthly wages | Annual + capacity-util as the cycle proxy |
| 3.4 FX/REER — REER | Some EM don't compute their own BIS REER | Use FRED BIS mirror where available; skip otherwise |
| 4.1 Demand Trans — lending standards survey | Only ~20 countries publish a SLOOS-equivalent | Loan-growth YoY is the headline fallback |
| 4.2 Balance Sheets — corporate ratios | Available in DM + KR + JP; sparse in EM | BIS credit-to-GDP gap as the headline |
| 4.3 Fin Conditions — corporate spreads | Most EM have no published IG/HY OAS | Sovereign CDS as the country-credit-risk proxy |
| 4.4 Policy Reaction — macropru tools | Tool changes are announcements not series | Maintain an event log in `econ.dim_indicator` with `frequency_id=EVENT` |

---

## Step 4 — Cross-cell identity checks

Run these whenever adjacent cells land — they catch loader/units bugs before they propagate:

| Identity | Check |
|---|---|
| `CA ≈ FA − E&O` | BoP closes (within rounding) |
| `Active + Inactive = Population 15+` | EAPS labour identity |
| `Employed + Unemployed = Active` | EAPS labour identity |
| `Goods exports − Goods imports = Goods balance` | BoP CA identity |
| `Goods balance + Services balance + Primary income + Secondary income = CA total` | BoP CA decomposition |
| `DI + PI + Deriv + OI + Reserves = FA total` | BoP FA decomposition |
| `Revenue − Expenditure ≈ Net lending` (plus capital transfers) | Fiscal identity |
| `Real GDP YoY ≈ weighted sum of sector contributions` | GDP supply-side identity |
| `Real GDP YoY ≈ weighted sum of expenditure contributions` | GDP demand-side identity |
| `Nominal = Real × Deflator / 100` | GDP price identity |
| `Import price (LC) / Import price (USD) ≈ inverse of FX move` | FX pass-through reconciliation |
| `M2 growth = Currency growth + Deposits growth (weighted)` | Money aggregate identity |
| `Total assets − Total liabilities = Equity` | Corporate balance-sheet identity |

### Quality bar for ✅

For a country to count as **"fully covered"** in a cell, the headline indicator must meet:

| Quality bar | Threshold |
|---|---|
| **History depth** | 10+ years for trend analysis; 5+ years acceptable for new vendors |
| **Update lag** | ≤ 60 days after period end (most published series are <30 days) |
| **Cadence** | At least the *Min cadence* in the blueprint table |
| **Identity-check pass** | Cross-cell identities (above) hold within rounding |
| **Vendor stability** | Source has a published refresh schedule (not a one-off snapshot) |

A country that fails any of these gets ⚠ in the wiring map and the gap is documented in §8 of its inventory doc.

---

## Step 5 — Reconcile against the wiring map

Promotion rules for [macro_economy_wiring_map.md §7.x](macro_economy_wiring_map.md):

- ❌ → ⚠️: first ✅ headline indicator lands in the cell
- ⚠️ → ✅: every bullet in the cluster has at least one indicator, with vintage-0 sample on disk + production fetcher registered

When you flip a cell, edit the country's 4×4 grid in `macro_economy_wiring_map.md §7.x` directly. Append new countries by adding a new `### 7.N {Country} ({CC})` block in the same shape — keep cluster columns identical.

If the country needs something genuinely off-map (e.g. China RRR ratios, India SLR), record it in §8 (regime-dependence) rather than reshaping the map. The 16-cell taxonomy is stable on purpose.

---

## Code conventions

- **Playground first**: every vendor starts at `playground/econ/{vendor}/` with a `fetch.py` (or discovery probe). Document it in `docs/admin/econ/{country}/_playground/{vendor}.md`. See [korea/_playground/](korea/_playground/) for the shape.
- **Canonical loader (playground-scoped)**: `python -m scripts.migrations.load_econ_indicator_from_playground --vendor {vendor}`. Works for any vendor producing parquet pairs at `playground/econ/{vendor}/sample_output/**/*_{dim,fact}.parquet` matching `playground/econ/schema_prototype.py`. This loader is acceptable from playground during discovery because it reads from `playground/` and writes via the user-supervised one-shot path; **prod scheduler wiring is still gated** ([`econ_to_prod.md`](econ_to_prod.md)).
- **NO prod wiring without sign-off** — see the ⛔ HARD RULE banner at the top of this doc and [`econ_to_prod.md`](econ_to_prod.md). Reinforces [[feedback-no-prod-wiring-without-permission]].
- **Add vendor row**: every new vendor needs a `dbo.dim_vendor` migration before its first row goes into `econ.dim_indicator`. **Drafting** the migration during discovery is fine; **applying** it is part of [`econ_to_prod.md`](econ_to_prod.md).

---

---

## End-of-discovery — STOP HERE pending user sign-off

After Steps 1-5 + Phase H discovery work below, the country has:

- A populated `{country}_indicator_inventory.md` + `_playground/{vendor}.md` (Track A)
- `playground/econ/{vendor}/sample_output/*.parquet` paired files matching `schema_prototype.py` (Track A)
- A populated `{country}_govt_doc_sources.md` + `playground/econ/{cc}/govt/{fetch_*.py, daily_pull.py}` (Track B)
- `playground/econ/{cc}/govt/data/snapshots/{YYYY-MM-DD}.json` manifest-only output (Track B)

**That is the deliverable.** Summarise findings to the user (counts, blockers, Tier-1 coverage) and **stop**. Do NOT proceed to prod promotion in the same session unless explicitly instructed.

Prod promotion — copying helpers to `src/imdr/domains/econ/`, building `scripts/econ/{cc}/{vendor}/` (country-first per the layout rule above), the country orchestrator at `scripts/econ/{cc}/{cc}_monthly.py` and (for Track B) `scripts/econ/{cc}/{cc}_daily.py`, scheduler registration, code-review gate, prod-pipeline doc — is a **separate, gated workflow**. See **[`econ_to_prod.md`](econ_to_prod.md)** for the full playbook (Track A Phase G + Track B Phase J, including migration apply + scheduler wiring gates).

**Reference end-state** (Korea, 2026-06-10): both tracks live in prod. Discovery deliverables above + applied migrations + promoted `scripts/econ/kr/govt/` tree + `scripts/econ/kr/kr_{daily,weekly,monthly}.py` orchestrators + registered in all three `scripts/imdr_{daily,weekly,monthly}.py:PIPELINES`. Use Korea's file tree as the template when promoting any new country.

---

## Phase H — Government & CB document sources (Track B)

> ⭐ **Korea is the complete reference** — every Phase-H artefact below has a worked example in `docs/admin/econ/korea/` or `scripts/econ/kr/govt/`. Korea progressed end-to-end on 2026-06-10: inventory (~960-line `govt_doc_sources.md`) → 7-agency playground fetchers → multi-agent review (code/db/docs/security) → migrations 086+087 applied → `filings.py` impl → `scripts/econ/kr/govt/` promotion (with `daily_pull.py` → `ingest_filings.py` rename) → `scripts/econ/kr/kr_daily.py` orchestrator with inline filings-aware email → registered in `scripts/imdr_daily.py:PIPELINES`. **307+ official-source rows in `research.dim_report` as of 2026-06-10**; daily cron self-sustains.
>
> Australia ([australia/au_cb_documents.md](australia/au_cb_documents.md), 6 fetchers, ~33 items/day baseline) is the lighter discovery example — sample for "what does Phase H look like in playground" before promotion. AU has NOT entered Phase J (no migrations applied, no orchestrator built, no prod wire-up). Use it for the discovery shape; use Korea for the prod shape.
>
> Use whichever pattern is the closest fit per agency — Korea is the deep-discovery example (5 crawler shapes, patient-retry TLS, body+PDF resolution recipes per agency); AU adds the RBA Akamai-bypass via Playwright + Treasury/APRA plain httpx variant.

### H.1 What Track B is — and is NOT

**IS**: PDF and HTML documents from central banks, ministries, regulators, statistical agencies, fiscal councils, debt-management offices, quasi-government think tanks, and market infrastructure. The text that **accompanies** the data — MPC minutes, monetary-policy statements, financial-stability reviews, budget papers, ministry press releases, think-tank outlooks, governor speeches.

**IS NOT**: time-series data. Anything that lands in `econ.fact_indicator` is Track A and belongs in `{country}_indicator_inventory.md`. The 10-day customs trade quick-estimate is Track A; the customs press release that narrates it is Track B.

**Where it lands**: `research.dim_report` + Qdrant chunks + SharePoint mirror — the **same RAG corpus as sell-side research** (JPM/MS/Goldman/etc.). Discrimination is by `dbo.dim_vendor.vendor_category` (`official_cb` / `official_ministry` / `official_regulator` / `official_thinktank` / `official_statistics` / `official_market_infra` / `official_supranational`). One filter flag separates "sell-side view" from "official voice" in Mycroft/Lois prompts.

### H.2 Inventory shape — `{country}_govt_doc_sources.md`

Mirror the section structure Korea uses. Each agency gets a table with `Stream × URL × Cadence × Lang × Listing × Auth × Crawl × Why it matters`. Group into sections by agency category:

1. **Central bank** (BoK / RBA / BoJ / BoT / BI / …) — the highest-signal source. Subsections: monetary-policy decisions, MPC minutes, monetary-policy report, financial-stability report, working papers, regional report ("Beige Book" equivalent), governor speeches, press releases.
2. **Cabinet ministries** — finance/treasury, trade/industry, labour, housing, foreign affairs. Each has a press-release stream + topical RSS / sub-boards.
3. **Financial-system regulators** — banking supervisor, capital-market regulator, deposit insurance.
4. **Statistical agencies** — CPI / labour / trade releases come with narrative commentary distinct from the time-series.
5. **Quasi-government think tanks** — state-funded research institutes (KDI / KIEP / KIF / KIET in KR; PC / Grattan / e61 in AU). Para-public voice on policy direction.
6. **Fiscal council & legislative research** — independent budget projections (NABO in KR; PBO in AU).
7. **Debt management / state banks / deposit insurance** — issuance plans, auction results, AOFM/PDMO publications, KDB/KDIC IR.
8. **Market infrastructure** — exchange notices (KRX / ASX), securities depository, clearing.
9. **Pensions & sovereign wealth** — NPS / KIC / Future Fund / GPIF / NZ Super. Allocation-flow signal.
10. **Other / cross-cutting** — antitrust, energy regulator, data-protection commissioner, all-government aggregator (korea.net-style).

Within each section, mark already-known sources from `index.md` § Policy & fiscal document sources with **(already-known)**; flag unverified URLs with **❓**.

### H.3 Crawl-complexity legend (per row)

Reuse the legend from the "Required country index.md structure" section above, plus four named **crawler shapes** that the Korea+AU probes confirmed cover ~80% of agencies:

| Shape | Pattern | Where it appears | Transport |
|---|---|---|---|
| **Shape 1 — RSS-fan** | One handler reads N RSS URLs and normalises | MOEF (10 boards in KR), most ministries with `/rss.do` endpoints | plain httpx |
| **Shape 2 — egov BBS GET-listing** | `/eng/bbs/{board}/list.do?menuNo={m}` server-renders rows; `fileDown.do?atchFileId=…&fileSn=…` for attachments | FSS, KCS, KDIC, KIPF; most KR statistical agencies | plain httpx + patient retry |
| **Shape 3 — egov BBS POST-listing** | Chrome at `list.do`, rows via **POST** to `listCont.do` with `X-Requested-With: XMLHttpRequest` + Referer | BoK (20+ board streams from one config) | plain httpx + patient retry |
| **Shape 4 — DT-rendered list / Akamai-gated** | Server-rendered `<dt>` titles inside `<dl>`; sometimes Akamai-protected (RBA-style 403 to plain `requests`) | FSC (KR, patient retry), RBA (AU, Playwright fresh-profile per run) | plain httpx + patient retry **OR** Playwright headed |
| **Shape 5 — JS-onclick article handler** | Listing uses `onclick="article.view('id','type')"`; detail URL assembled from JS | MOTIR (KR) | plain httpx + JS-handler parsing |

Document which shapes apply to which agencies in `{country}_govt_doc_sources.md` § "Crawl-pattern clustering" — this directly maps to how many distinct fetcher templates the country needs.

### H.4 Tier classification

Triage every row into one of three tiers. Korea's split (15 / 20 / 25+) and AU's split (6 / 2 / 4) are the calibration points.

| Tier | Definition | Build now? |
|---|---|---|
| **Tier 1** | Drives FX / govt-bond / equity curve within 24h of release **OR** carries the canonical policy text behind a market-moving decision | Yes — Phase H must ship Tier 1 |
| **Tier 2** | Useful colour: depth, divergence signal, sector-specific insight; not market-moving on release | Build after Tier 1 + a topic filter exists if volume is high |
| **Tier 3** | Reference, academic, sectoral. Defer until 1-2 operational | Skip in v1 |

### H.5 Discovery-probe workflow

Mirror the Korea pattern at `playground/econ/{cc}/govt/`:

1. **Inventory first** — write `{country}_govt_doc_sources.md` from web research; do not write code yet. The act of writing the table forces the Tier decision per stream.
2. **Per-cluster probe** — for each crawler shape present in the inventory, write one probe script in `playground/econ/{cc}_govt_docs/probe_{cluster}.py` (Korea has `probe_moef_rss.py`, `probe_bok_ajax.py`, `probe_cdef.py`, `probe_corrections.py`). Save raw HTML/RSS responses under `raw/{cluster}/` for downstream debugging.
3. **Resolve recipes** — for each agency, capture BOTH `body_text` AND `pdf_bytes` paths in `probe_resolve.py`. Most agencies have one but not the other; some have neither (KCS publishes JPG scans, MOTIR PDFs are TLS-blocked from our network). Document recipes in `{country}_govt_doc_sources.md` § "Per-agency body + PDF resolution recipes".
4. **Per-agency fetchers** — once probes confirm a cluster works, lift the probe into `playground/econ/{cc}/govt/fetch_{agency}.py` returning a uniform `FetchResult` of `FilingItem` rows. Each fetcher is ~100-200 LoC.
5. **Daily-pull orchestrator** — `playground/econ/{cc}/govt/daily_pull.py` runs all fetchers, dedupes via rolling `data/seen.json`, writes per-day snapshot to `data/snapshots/{YYYY-MM-DD}.json`, prints summary table. Cadence is **daily even though most agencies publish less frequently** — empty days are evidence of cadence drift, not bugs. **On promotion this file moves to `scripts/econ/{cc}/govt/ingest_filings.py`** (Korea pattern) — keep the playground name during discovery for clarity that no DB writes are happening yet.

### H.6 Network reality checks (HARD GATE)

Before declaring an agency Tier 3 "blocked", verify the block is real:

- **TLS flakiness vs. corp firewall** — many KR govt edges (FSC, KCS, MOTIR, BoK) intermittently reset TLS 1.2 from RV's network. User-browser loads fine. Default 4-retry helper is too short. Confirmed pattern: 10-retry session with 2.5s base backoff fixes it. **Do NOT declare "blocked" without confirming the URL fails in the user's browser too.**
- **Akamai 403** — RBA blocks plain `requests`/`httpx` but works with Playwright headed + fresh profile per run. Treat as "needs Playwright transport", not "blocked".
- **Host-specific corp firewall** — AOFM `aofm.gov.au/sites/default/files/*` is genuinely blocked from RV's network. APRA's identical Drupal-path pattern at `apra.gov.au/sites/default/files/*` works fine. The AOFM block is host-specific, not a `.gov.au` blanket rule. Test the actual host before assuming.
- **Subscriber-gated** — KCIF (KR FX desk reports) carries the highest signal but most reports are subscriber-only. Confirm with user whether institutional credentials exist before scoping for inclusion.

See [[feedback-kr-govt-flaky-tls-patient-retry]] and [[project_motie_renamed_to_motir]] for the canonical patient-retry + URL-rename lessons.

### H.7 Discovery deliverable — STOP HERE

At the end of Phase H discovery, the country has:

- `{country}_govt_doc_sources.md` populated (sections 1-10 + crawl-pattern clusters + Tier 1/2/3 + per-agency resolution recipes)
- `playground/econ/{cc}/govt/fetch_{agency}.py` per Tier-1 agency
- `playground/econ/{cc}/govt/daily_pull.py` running end-to-end, writing **manifest-only** snapshots to `data/snapshots/{YYYY-MM-DD}.json`
- `data/seen.json` rolling-dedup proving the daily-pull is idempotent

**Do NOT, without explicit user OK:**
- Apply `migrations/086_add_dim_vendor_category.sql` or any `{NNN}_seed_{cc}_official_vendors.sql` to the database
- Implement `src/imdr/research/filings.py:ingest_filing()` beyond the existing skeleton
- Register `scripts/econ/{cc}/{cc}_govt_daily.py` into `scripts/imdr_daily.py:PIPELINES`
- Write a single `FilingItem` to `research.dim_report`, Qdrant, or SharePoint from any production code path

Summarise findings (item counts per agency, blockers, Tier-1 coverage) and stop. Prod promotion of Track B — migrations apply, ingest helper completion, scheduler wiring, prod-pipeline doc — is covered in **[`econ_to_prod.md`](econ_to_prod.md) § Track B (Phase J)**.

### H.8 Worked examples

- **Korea — fully promoted to prod 2026-06-10.** 7 agencies (bok / moef / motir / fsc / fss / kcs / kdi) + 8th via existing `mods` vendor (id=24, KOSTAT). 5 crawler shapes proven (RSS-fan / egov-GET / egov-POST / dt-list / JS-handler). Body+PDF resolution recipes for 6/8 agencies (KCS deferred — image-only; MOTIR PDF TLS-blocked, body path live). Inventory at `docs/admin/econ/korea/govt_doc_sources.md` (~1014 lines). Migrations 086 + 087 **applied**. `scripts/econ/kr/govt/{_http,_models,resolvers,fetch_*,ingest_filings,backfill_mods}.py` + `scripts/econ/kr/kr_daily.py` live in `scripts/`. Wired into `scripts/imdr_daily.py:PIPELINES`. **307 official rows in `research.dim_report` + ~600 Qdrant chunks** as of 2026-06-10. See [`../development/kr_govt_filings.md`](../development/kr_govt_filings.md) for the full execution tracker.
- **Australia — discovery only.** 6 fetchers (RBA Governor's Statement + Board Minutes + SMP + FSR via Playwright + Treasury + APRA via plain httpx), ~33 items/day baseline. RBA Akamai-bypass via fresh-profile-per-run. Inventory at `docs/admin/econ/australia/au_cb_documents.md` (~150 lines). Phase J not entered — replicate the Korea pattern when promoting.

---

## Cross-refs

- **[`econ_to_prod.md`](econ_to_prod.md)** — prod-promotion playbook (Track A Phase G + Track B Phase J). DO NOT do prod work without going through this doc.
- [country_econ_blueprint.md](country_econ_blueprint.md) — the indicator catalogue (§1-4, the *what*)
- [macro_economy_wiring_map.md](macro_economy_wiring_map.md) — the 16-cell coverage tracker
- [economics_data_ingest.md](economics_data_ingest.md) — schema + loader + per-vendor build log

### Worked references by track

| Country | Track A (indicators) | Track B (filings) | Combined? |
|---|---|---|---|
| **Korea** ([korea/](korea/)) | ✅ LIVE — `kr_weekly` + `kr_monthly`, 172 indicators across 4 vendors. Prod pipeline doc: [korea/korea_prod_pipeline.md](korea/korea_prod_pipeline.md) | ✅ LIVE — `kr_daily` + `scripts/econ/kr/govt/ingest_filings.py`, 307+ filings. Inventory: [korea/govt_doc_sources.md](korea/govt_doc_sources.md). Tracker: [`../development/kr_govt_filings.md`](../development/kr_govt_filings.md) | ⭐ **YES — full end-to-end reference** for both tracks. Replicate this country's shape for any new onboarding. |
| **Indonesia** ([indonesia/](indonesia/)) | ✅ LIVE — `id_monthly`, 250 indicators across BPS+BI+BIS. Prod pipeline doc: [indonesia/indonesia_prod_pipeline.md](indonesia/indonesia_prod_pipeline.md) | ❌ not started | Track A only |
| **Australia** ([australia/](australia/)) | ⚠ manual-load (412 indicators across ABS+RBA+AOFM+FRED, prod promotion pending) | ⚠ discovery only — 6 fetchers in `playground/econ/au/govt/`. Inventory: [australia/au_cb_documents.md](australia/au_cb_documents.md) | Phase H done for B; Phase G + Phase J pending |
