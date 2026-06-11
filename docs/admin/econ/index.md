# IMDR Econ Documentation

Last updated: 2026-06-10 (AU: 3 cells closed; ID: SRBI + SBN-position-by-holder added)

Macro / country-economy data: the indicators sitting in `econ.dim_indicator` / `econ.fact_indicator`, the vendors that feed them, and the country-by-country wiring plan.

**The single place to look for any country econ question.** If you're asking "what Korea data do we have", "what's our HK CPI source", "which RBI tables aren't loaded yet" — start here, not under `vendors/`.

---

## Quick links

| Doc | Purpose |
|---|---|
| **[onboarding_new_country.md](onboarding_new_country.md)** | **5-step playbook** for adding a new country. Read this first. |
| [macro_economy_wiring_map.md](macro_economy_wiring_map.md) | 16-cell coverage tracker (4 engines × 4 clusters × N countries). The *what we cover, where the gaps are*. |
| [country_econ_blueprint.md](country_econ_blueprint.md) | The exhaustive country-agnostic indicator catalogue (§1-4). The *what indicators exist per cell*. |
| [economics_data_ingest.md](economics_data_ingest.md) | Schema + vendor-agnostic loader + per-vendor build log. The *how* and *what's done*. |

---

## Countries

Each country has a folder with prod reference docs at the top + a `_playground/` for testing/discovery. Wiring-map anchors jump to the 4×4 grid for that country.

| Country | Status | Folder | Wiring map | Indicator inventory |
|---|---|---|---|---|
| **Korea (KR)** | LIVE — 172 indicators across KOSIS + REB + FRED + BOK-mirror. **KOSIS + REB auto-load via `kr_weekly`/`kr_monthly` since 2026-06-05.** Ops: [korea_prod_pipeline.md](korea/korea_prod_pipeline.md) | [korea/](korea/) | [§7.13](macro_economy_wiring_map.md#713-south-korea-kr) | [korea_indicator_inventory.md](korea/korea_indicator_inventory.md) |
| **United States (US)** | LIVE — 133 indicators via FRED | [united_states/](united_states/) | [§7.1](macro_economy_wiring_map.md#71-united-states-us) | — |
| **Hong Kong (HK)** | LIVE — 29 indicators via HKMA | [hong_kong/](hong_kong/) | [§7.10](macro_economy_wiring_map.md#710-hong-kong-hk) | — |
| **Australia (AU)** | DB-LIVE (manual load) — **464 indicators / 397,118 obs**; ABS 18 fetchers / 21 dataflows (179 indicators incl. derived ToT) + RBA 9 fetchers via CSV snapshot (119 indicators incl. TIB + ICP + REER + ZCY) + AOFM 5 fetchers (157) + Cotality (6 daily HVI) + FRED-mirror (3); **16 of 16 cells ✅** (3.1 ToT closed 2026-06-11). Phase G blocker lifted. Production promotion pending user sign-off. | [australia/](australia/) | [§7.7](macro_economy_wiring_map.md#77-australia-au) | [australia_indicator_inventory.md](australia/australia_indicator_inventory.md) |
| **New Zealand (NZ)** | Discovery only (RBNZ, Stats NZ) | [new_zealand/](new_zealand/) | [§7.8](macro_economy_wiring_map.md#78-new-zealand-nz) | — |
| **India (IN)** | Prod-live 26 × 39,569 (BIS + FRED + RBI DBIE FX reserves/Key Rates). Pre-prod playground: **13 fetchers / ~1,081 indicators / ~62,414 obs** (MOSPI CPI/IIP/NAS · DPIIT WPI/8-Core · CGA · IMD · FAO · DGCIS · UPAg MSP+AIAPY+IMC · **RBI Bulletin 11 tables incl. BoP T40 — 151 Credit/Debit/Net indicators**). 2026-06-11 unlocks: DGCIS multi-month trade (198 × 30.9k obs · 2013→); UPAg via Plotly Dash (closes Cluster 4 agri — AIAPY 60 FYs + A33 mandi prices); RBI Bulletin 11 tables via headed-Chrome TSPD (BoP T40 effectively eliminates the A5-A7 SAP-BO iframe requirement for BoP cells); DBIE SPA AES encryption decoded. | [india/](india/) | [§7.12](macro_economy_wiring_map.md#712-india-in) | — |
| **Japan (JP)** | Source catalogue only (e-Stat, BOJ, BoJ docs) | [japan/](japan/) | [§7.4](macro_economy_wiring_map.md#74-japan-jp) | — |
| **Eurozone (EU)** | Source catalogue only (ECB SDW, Eurostat, ECB docs) | [eurozone/](eurozone/) | [§7.2](macro_economy_wiring_map.md#72-eurozone-eu) | — |
| **Philippines (PH)** | Source catalogue only (BSP, PSA, DBM, BTr) | [philippines/](philippines/) | [§7.15](macro_economy_wiring_map.md#715-philippines-ph) | — |
| **Thailand (TH)** | Source catalogue only (BoT, NSO) | [thailand/](thailand/) | [§7.16](macro_economy_wiring_map.md#716-thailand-th) | — |
| **Indonesia (ID)** | DB-LIVE — **308 indicators × 114,106 obs** (2026-06-10), all 16 wiring-map cells covered, 13 of 16 are full ✅. BPS (82, REST JSON) + BI (184 across SEKI tables + Survey publications + bank rates + SRBI auction yields + SBN position by holder) + BIS (6, SDMX) + DJPPR (36, daily SBN ownership). 28 prod fetchers; 2 registered in `imdr_daily.py` (BIS policy rate + SRBI). True tenor-by-investor SBN cross-tab is outstanding gap (requires Kemenkeu Buku Saku APBN); bank-type decomp now live via BI SEKI IV.4. | [indonesia/](indonesia/) | [§7.17](macro_economy_wiring_map.md#717-indonesia-id) | [indonesia_indicator_inventory.md](indonesia/indonesia_indicator_inventory.md) |

Other countries appear in the wiring map (UK, CA, CH, DE, CN, SG, TW) via FRED OECD mirrors — they don't have their own folder yet. When one graduates from FRED-mirror to native-vendor, create a folder following the Korea reference shape.

---

## Multi-country reference sources

Aggregators useful as cross-country sanity checks or as a fallback when a primary vendor is gated. Treat as Tier-4 in the [vendor cascade](onboarding_new_country.md#step-2--resolve-each--via-the-vendor-cascade) — never the source-of-truth when a national publisher exists.

| Source | Coverage | Access | Notes |
|---|---|---|---|
| **World Bank — Open Data** (`data.worldbank.org`) | WDI, GDF, BoP, fiscal, demographics, ~200 countries | Web + bulk CSV | Annual / quarterly only — no monthly. |
| **World Bank — Indicators API** (`api.worldbank.org/v2`) | Same as above, programmatic | REST JSON, no key | Indicator-code-based, stable since v2. |
| **BIS Data Portal** (`data.bis.org`) | CB-policy rates, FX, debt securities, credit, property prices, locational + consolidated banking | REST SDMX-JSON / bulk CSV | Property-prices dataset is the only place for harmonised cross-country housing. |
| **OECD Data Explorer** (`data-explorer.oecd.org`) | OECD-country macro: GDP, CPI, labour, trade, fiscal, financial | REST SDMX, no key | Direct source — distinct from the FRED-hosted OECD mirror. |
| **ECB SDW / Data Portal** (`data.ecb.europa.eu`) | Euro-area + per-country EU stats, plus global rates/FX | REST SDMX-JSON, no key | Also indexed under [`eurozone/`](eurozone/) as the primary EU source. |

---

## Conventions for cross-country reporting

When asked for a cross-country availability matrix, default to **country × data-availability**. Do **not** name specific sources unless the user explicitly asks ("which vendor", "what's the URL", etc.) — this keeps registry detail private by default and avoids leaking a curated source list.

---

## Folder conventions

```
docs/admin/econ/
├── index.md                          ← you are here
├── onboarding_new_country.md         ← playbook
├── macro_economy_wiring_map.md       ← coverage tracker
├── country_econ_blueprint.md         ← indicator catalogue
├── economics_data_ingest.md          ← schema + build log
└── {country}/
    ├── index.md                      ← country landing (required)
    ├── *.md                          ← prod reference docs (API ref, coverage plan, indicator inventory, indicator targets, {country}_prod_pipeline.md once in production)
    └── _playground/                  ← optional: only when playground/econ/{vendor}/ code exists
        ├── index.md                  ← only when multiple vendors
        └── {vendor}.md               ← one per playground/econ/{vendor}/
```

- **Country codes follow [`dbo.dim_country`](../db_audit/) canonical**: `country_code` (e.g. `EU` for Eurozone, `UK` for United Kingdom, `KR` for South Korea). Folder names use the lowercase + underscore form of `display_name` (`united_states/`, `hong_kong/`, `eurozone/`, `new_zealand/`).
- **`_playground/{vendor}.md`** mirrors `playground/econ/{vendor}/` — discovery probes, item-code inventories, fetcher status. Graduates to a top-level prod doc as the vendor stabilises. Pre-discovery countries (no playground code yet) have no `_playground/` at all.
- **No vendor-namespacing at the top level**: a country's data may flow through 3+ vendors (Korea = KOSIS + REB + FRED + BOK-mirror); the country folder is the unit of consumption.

## Related

- Country-econ topic deep-dives (one-off analytical write-ups) live under [`docs/topics/`](../../topics/) and link back here.
- Vendor-framework feeds (Barclays email-linked, Citi Velocity, BBG) — the *non-econ* market-data side — stay under [`../vendors/`](../vendors/).
- [[project-econ-loaded]] — current live counts in `econ.fact_indicator` (drifts; query the DB before quoting numbers).

## Adjacent: government policy filings (text corpus)

A country's macro picture has two distinct data shapes:

| Shape | Storage | Doc |
|---|---|---|
| **Numeric time-series** — CPI, GDP, BoP, FX reserves, etc. | `econ.fact_indicator` | this index + per-country docs above |
| **Policy text** — CB minutes, ministry press, regulator releases | `research.dim_report` + Qdrant + SharePoint | [`../research/index.md`](../research/index.md) — see "Adjacent corpus" |

The two share `dim_country` and `dbo.dim_vendor`. The `vendor_category`
column (added by [migration 086](../../../migrations/086_add_dim_vendor_category.sql))
discriminates sell-side research from official sources. A central bank
like `rba` is one row used as the source for both its indicator data
feed AND its policy minutes.

**Per-country filings inventories** (as completed):
- Korea — [`korea/govt_doc_sources.md`](korea/govt_doc_sources.md) (70+ streams; daily-pull discovery live in playground 2026-06-10).
- Australia / Indonesia / Japan / India / Thailand / Philippines — pending the Korea pattern replicating.
