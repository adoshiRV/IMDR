# Citi Velocity — FX Proprietary Indices (`FX.<PRODUCT>`)

The Citi FX proprietary-index group — CESI (Citi Economic Surprise Index) and
its siblings, effective-exchange-rate indices (NEER/REER), commodity terms of
trade (CTOT), the Macro Risk Index (MRI), the Pain Index, and more. All land in
one **generic, product-neutral** framework: `fx.dim_index_series` (catalog, one
row per leaf tag) + `fx.fact_index_value` (vintage-aware daily values), vendor id
**1** (`citi_velocity`), migrations **120–122**. Probed + onboarded 2026-07-30.

- **Probe caches:** `data/cache/fx/fx_indices_probe.json` (all products), `data/cache/fx/surprise_index_probe.json` (CESI detail)
- **Probe script:** `playground/fx/citi/probe_fx_indices.py`
- **Library:** `src/imdr/domains/fx/citi_fx_indices.py`
- **Prod ingest:** `scripts/fx/citi/fx_indices.py`

## Products (probed 2026-07-30, 3,334 leaf tags; all daily)

| Product | Tags | What it is | History | Status |
|---|---|---|---|---|
| **SURPRISE_INDEX** | 2,415 | Economic/Inflation Surprise Indices — branded **CESI** + siblings | 2005+ | ✅ ingest |
| **NEER_IDX** | 133 | Nominal Effective Exchange Rate (basket × ccy) | 2005+ | ✅ ingest |
| **REER_IDX** | 195 | Real Effective Exchange Rate (basket × ccy) | 2005+ | ✅ ingest |
| **CTOT** | 68 | Commodity Terms of Trade (DM/EM × ccy) | 2005+ | ✅ ingest |
| **MRICITI** | 23 | Macro Risk Index (family × component; no ccy) | 2005+ | ✅ ingest |
| **CITIPAIN** | 10 | Citi Pain Index (G10 positioning, one ccy/tag) | 2006+ | ✅ ingest |
| **CRFI** | 2 | Citi Risk Factor Index (EM_VALUE / G10_VALUE) | 2014–**Oct 2025** | ⚠️ stale |
| **LIQUIDITY_IDX** | 28 | FX liquidity indices (region [× quote-leg] density) | 2021–**Oct 2025** | ⚠️ stale |
| **SC_SCORECARD** | 460 | FX Scorecard multi-factor model | mixed / **some tags dataless** | ⏸ deferred (Phase 2) |

**⚠️ CRFI & LIQUIDITY_IDX** stop updating in Oct 2025 — a backfill gets their full
history, but daily runs return no fresh points (likely discontinued upstream).
**⏸ SC_SCORECARD** is deferred: its probe sample (`FLOWPCT.BUDGET`) returned **zero
data points**; needs a per-tag data probe before ingest (the dim already parses
its shape, so no schema change is required to add it later).

## Tag anatomy → dim columns (the parser contract)

`fx.dim_index_series` uses five **nullable** semantic columns reused across
products *by role*, plus `product_code` (discriminator), `region_currency_id`
(FK, resolved only when a token is a tracked ISO currency), `frequency_id`,
`display_name`. Which columns a product populates:

| Product | Tag shape (after `FX.<PRODUCT>`) | `series_family` | `index_type` | `series_group` | `component` | `region_code` | `sector_code` |
|---|---|---|---|---|---|---|---|
| SURPRISE_INDEX | `family.type.group.region[.sector]` | ESI/ISI | CESI/CECI/CEDI/CERI/EFUI/SI_CISI/SI_CIDI/SI_CICI | DM/EM/SI_GM | — | SI_USD, G10_HARD, EUROSTAT… | 11 sectors + TOTAL (ESI) |
| NEER_IDX / REER_IDX | `basket.ccy` | — | basket (BROAD/NARROW/NBI_*/USD) | — | — | ccy | — |
| CTOT | `group.CTOT_ccy` | — | — | DM/EM | — | `CTOT_<ccy>` | — |
| MRICITI | `family.component` | — | MRI_EMMRI/LTMRI/STMRI | — | MRI_CORR/MRI_FXVOL/… | — | — |
| CITIPAIN | `ccy` | — | — | — | — | ccy | — |
| CRFI | `type` | — | EM_VALUE/G10_VALUE | — | — | — | — |
| LIQUIDITY_IDX | `region[.quote_leg].DENSITY.CITI` | — | DENSITY | — | quote-leg ccy | region/base ccy or block | — |

`region_currency_id` resolves from `region_code` only (CTOT strips its `CTOT_`
prefix; SURPRISE_INDEX strips `SI_`), never from `component`. Aggregate blocks
(`G10_HARD`, `EM`, `EUROSTAT`) and untracked currencies (UAH) stay NULL.

## Data shape & load

- Daily; `x` = 8-digit `YYYYMMDD`, `c` = value; floats, can be negative/zero.
- **Vintage-aware** fact: Citi restandardizes some indices, so a re-pull whose
  value differs appends a new vintage rather than overwriting (same contract as
  `econ.fact_indicator`; [shared predicate](../../../../src/imdr/utils/vintage.py)).
  Read via `fx.vw_fact_index_value_latest` / `_current`.
- Full backfill of the 8 live products ≈ 2,874 series; the fact load **streams
  per batch** (never holds a full backfill in memory), via the shared
  `citi_helpers.iter_fetched_batches` (5xx retry + tag-quota tracking + per-tag
  error capture). Products are isolated — one product's hard failure is logged
  and skipped, quota exhaustion stops the run cleanly.
- **Quota:** ~2,900 tags/run ≈ 3% of the 100k rolling-24h tag quota.

Migrations 120–122 are **net-new DDL** — a DBA must apply them (CRUD-only app
account can't run DDL). The dim rows are populated by the ingest script from the
live catalog, not by migration INSERTs.

## Running the ingest

```bash
# dry run — fetch + report, write nothing (default, safe):
python -m scripts.fx.citi.fx_indices --no-load

# one product:
python -m scripts.fx.citi.fx_indices --product NEER_IDX --no-load

# full backfill of all 8 live products (after migrations applied):
python -m scripts.fx.citi.fx_indices --mode backfill --load

# daily catch-up:
python -m scripts.fx.citi.fx_indices --mode daily --load
```

Flags: `--product` (repeatable, default all 8), `--start/--end`, `--batch-size`
(≤100), `--limit N` (cap tags/product, testing). Not yet scheduler-wired.

---

## Boundary: Citi indices (here) vs BBG in the econ monitor — do not double-count

The **econ monitor** (`econ.fact_indicator`) already carries **Bloomberg**-sourced
headline versions of some of these, per country, via the EconDashboards mirror
([`bbg_econdashboard.py`](../../../../src/imdr/domains/econ/bbg_econdashboard.py)):
`BBG.SENTIMENT.CESI.{cc}` (surprise), `BBG.FX.NEER/REER.{cc}`. Those are a
*different vendor's* single number per country, kept as convenience tiles.

The Citi `fx.*` tables are the **granular / authoritative** source (full family ×
sectors × regions × baskets); the BBG-in-econ numbers are per-country tiles only.
For the deep read use the Citi `fx.*` tables; do not sum the two vendors' figures.
CTOT / MRI / CITIPAIN / CRFI / LIQUIDITY have **no** econ-monitor counterpart.
