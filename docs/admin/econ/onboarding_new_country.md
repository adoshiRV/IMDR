# Onboarding a new country — econ data playbook

Last updated: 2026-06-09

The 5-step workflow for adding a new country to `econ.dim_indicator`. Korea ([korea/](korea/)) is the worked reference example.

The **what** lives in [country_econ_blueprint.md](country_econ_blueprint.md) (indicator catalogue) and [macro_economy_wiring_map.md](macro_economy_wiring_map.md) (16-cell coverage map).
The **where** lives in the country-specific `_playground/{vendor}.md` notes you'll write along the way.

## Folder you'll create

```
docs/admin/econ/{country}/
├── index.md                          ← country landing page (required)
├── {country}_indicator_inventory.md  ← canonical "what we have" (mirrors blueprint §1-4)
├── {vendor}_api_reference.md         ← per-vendor API mechanics, if API has quirks
├── {country}_coverage_plan.md        ← maps wiring-map cells to vendor table IDs
├── {country}_indicator_targets.md    ← shopping list with imdr_code + source_code
└── _playground/                      ← only when playground/econ/{vendor}/ code exists
    ├── index.md                      ← only when multiple vendors
    ├── {vendor}.md                   ← one per playground/econ/{vendor}/ folder
    └── ...
```

You don't need every doc on day one. The minimum to graduate from "discovery only" to "loaded" is: `index.md` + `_playground/{vendor}.md` + parquet at `playground/econ/{vendor}/sample_output/`. A source-catalogue-only country (no playground code yet) needs only `index.md`.

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
- **Canonical loader**: `python -m scripts.migrations.load_econ_indicator_from_playground --vendor {vendor}`. Works for any vendor producing parquet pairs at `playground/econ/{vendor}/sample_output/**/*_{dim,fact}.parquet` matching `playground/econ/schema_prototype.py`. Vendor-agnostic.
- **No prod wiring without sign-off** ([[feedback-no-prod-wiring-without-permission]]): build the playground fetcher + canonical loader run. Do NOT register into `scripts/imdr_daily.py` etc. without explicit user OK.
- **Add vendor row**: every new vendor needs a `dbo.dim_vendor` migration before its first row goes into `econ.dim_indicator`.

---

---

## Phase G — Promote to production

> Lessons from the Korea (2026-06-05) and Indonesia (2026-06-09) promotions. Both countries followed this sequence; it is now the stable playbook.

### G.1 Hard rule — zero playground imports in prod

`scripts/econ/{vendor}/` and `src/imdr/domains/econ/` must have **zero `playground.*` imports**. Playground stays as the development surface; production is its own tree. Verify with a grep before any docs step:

```
grep -r "playground" scripts/econ/{vendor}/ src/imdr/domains/econ/
```

No matches = safe to proceed.

### G.2 Promotion sequence

**Step 1 — Promote helpers to `src/`.**
Copy `playground/econ/{vendor}/_{vendor}_*.py` to `src/imdr/domains/econ/{vendor}_*.py` (drop the leading underscore — they become first-class library modules). Update `_REPO_ROOT = Path(__file__).resolve().parents[N]` to match the new depth (typically `parents[4]` for `src/imdr/domains/econ/`).

**Step 2 — Re-implement fetchers as prod scripts.**
For each `playground/econ/{vendor}/fetch_*.py`, create `scripts/econ/{vendor}/{vendor}_{topic}.py`. Reference pattern: `scripts/econ/kosis/kosis_cpi.py`.

Required structure:
- Short docstring (1-2 paragraphs; trim playground exploration commentary)
- Imports from `imdr.domains.econ.{helper}` + `imdr.domains.econ.schema` + `scripts.econ._runner`
- `run_fetch(since, until) -> (indicators, observations)` — body lifted from playground, import paths swapped
- `main()` delegates to `scripts.econ._runner.run_main(vendor, topic, fetch_fn, description)`
- Strip: `sys.stdout = io.TextIOWrapper(...)`, `sys.path.insert(0, str(_REPO_ROOT))`, leftover `cli_main(...)` stubs

**Step 3 — Build the country orchestrator.**
`scripts/econ/{cc}/{cc}_monthly.py` calls `scripts.econ._country_runner.run(...)`. Do NOT fork a per-country `_runner.py` — `_country_runner.py` is parametrised by `country_code`, `country_label`, `country_name`, `orchestrator_path`, `pipelines`, `frequency_scope`. Reuse it.

**Step 4 — Register into the scheduler (gated).**
Add the orchestrator to `scripts/imdr_monthly.py:PIPELINES`. **Requires explicit user sign-off** per the no-prod-wiring rule before this line is flipped. Build the code first; let the user flip the switch.

### G.3 One orchestrator, many cadences

`frequency_scope` accepts `["MONTHLY","QUARTERLY","SEMIANNUAL","ANNUAL","DAILY"]` in one bundle. Idempotent MERGE makes over-running cheap. Default: a single `{cc}_monthly.py`. Only add `{cc}_weekly.py` if the country actually has weekly-cadence data (Korea has REB; Indonesia doesn't).

For policy-rate-style series that change rarely (e.g. BIS `WS_CBPOL`), wire the fetcher into `scripts/imdr_daily.py:PIPELINES` *in addition to* the monthly bundle when 24h-latency matters. The same fetcher in both schedulers is fine — MERGE-on-PK makes daily re-runs free; monthly stays as backstop. Indonesia BIS uses this pattern.

### G.4 Schema additions land in two places

If the country needs a new `frequency_code` (e.g. `SEMIANNUAL` for BPS Sakernas), add to both:
- `src/imdr/domains/econ/schema.py:VALID_FREQUENCIES`
- `src/imdr/notifications/econ_snapshot.py:_STALE_DAYS`

A migration to seed `dbo.dim_frequency` is also required.

### G.5 Category placeholder pattern

If a vendor emits a topic that doesn't fit an existing `dim_indicator_category` code, bucket it under `"other"` with a named constant + comment pointing at the follow-on work:

```python
# Bucketed under "other" until a dedicated "fiscal" code is added to
# econ.dim_indicator_category + VALID_CATEGORIES in
# src/imdr/domains/econ/schema.py. Tracked in
# docs/admin/econ/{country}/{cc}_coverage_plan.md (Phase E follow-on).
_FISCAL_CATEGORY_PLACEHOLDER = "other"
```

Also: avoid `if/elif` on a prefix string when building `imdr_code` — encode variable dimensions (suffix, category) as columns in your `_TABLES` row tuples instead.

### G.6 Code-review gate (HARD GATE)

Run `imdr-code-reviewer` on the new prod tree before touching docs. Hard checklist (8 items max):

1. Zero `playground.*` imports in `scripts/econ/{vendor}/` and `src/imdr/domains/econ/`
2. No back-compat shims for files deleted during generalisation
3. Existing countries (Korea) still pass their smoke tests
4. Fetcher structure matches `scripts/econ/kosis/kosis_cpi.py`
5. `imdr_code` built via dimension columns in `_TABLES`, not `if/elif` on a prefix string
6. Placeholder constants carry their rationale comment
7. `_REPO_ROOT` depth correct for new file location
8. No `sys.path` manipulation in prod scripts

Address all IMPORTANT findings before the docs step.

### G.7 Docs to update on prod-promotion

| Doc | What to do |
|---|---|
| NEW `docs/admin/econ/{country}/{country}_prod_pipeline.md` | Create mirroring `korea_prod_pipeline.md` section-by-section (architecture → library code table → cadence → invocation → CLI flags → archive layout → idempotency → failure modes → smoke tests → playground footer) |
| `docs/admin/econ/{country}/index.md` | Flip Phase G row to ✅; add Quick Links row to new prod-pipeline doc |
| `docs/admin/econ/{country}/{cc}_coverage_plan.md` | Strike "Phase G pending"; add prod-live timestamp |
| `docs/admin/econ/{country}/{country}_indicator_inventory.md` | Add a "Production fetchers" section listing the N prod fetcher modules |
| `docs/admin/econ/macro_economy_wiring_map.md` §{country} | Extend with prod-wiring sentence |
| `docs/admin/econ/economics_data_ingest.md` | Add country roster row referencing the orchestrator(s) |

Canonical prod-live wording for any of these docs:
> "Wired into `scripts/imdr_monthly.py:PIPELINES` YYYY-MM-DD"
Extend with `+ scripts/imdr_daily.py` if the country has a daily-bound fetcher.

### G.8 Email formatter

The country orchestrator's email report is produced by `imdr.notifications.formatters.country_econ_ingest.CountryEconIngestFormatter` (template at `templates/country_econ_ingest.html`). No per-country formatter needed — it's parametrised.

### G.9 Worked examples

- **Korea** — `docs/admin/econ/korea/korea_prod_pipeline.md`, `scripts/econ/kr/kr_monthly.py`, `scripts/econ/kosis/`
- **Indonesia** — `docs/admin/econ/indonesia/indonesia_prod_pipeline.md`, `scripts/econ/id/id_monthly.py`, `scripts/econ/{bps,bi,bis}/`

---

## Cross-refs

- [country_econ_blueprint.md](country_econ_blueprint.md) — the indicator catalogue (§1-4, the *what*)
- [macro_economy_wiring_map.md](macro_economy_wiring_map.md) — the 16-cell coverage tracker
- [economics_data_ingest.md](economics_data_ingest.md) — schema + loader + per-vendor build log
- [korea/](korea/) — worked reference example (Korea prod pipeline: [korea/korea_prod_pipeline.md](korea/korea_prod_pipeline.md))
- [indonesia/](indonesia/) — second worked example (Indonesia prod pipeline: [indonesia/indonesia_prod_pipeline.md](indonesia/indonesia_prod_pipeline.md))
