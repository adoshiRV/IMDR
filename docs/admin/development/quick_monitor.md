# Quick Monitor — a per-country economy snapshot (master spec)

**Status:** design spec (nothing wired/built without explicit OK) · **Reconciled + DB-verified:** 2026-07-22
· **Scope countries (Phase 1):** India, Korea

> One line: *for every country, a single grounded snapshot that fuses the **markets layer**
> (FX · rates · vol · curves the desk watches) with the **econ/macro layer** (the cross-country
> `Econ` board + the 8-domain × 6-archetype economy read) — the data feed behind a full-scale
> country dashboard.*

This is the **single authoritative spec**. It reconciles what used to be split across the
Quick Monitor umbrella, the per-country ticker audits, and the econ coverage state
(`econ_data_state.md` / `macro_economy_wiring_map.md`). The **"econ monitor"** — the cross-country
macro board (`Econ` sheet of the workbook) plus the per-country macro decomposition — is folded in
here as **Layer B**; it is not a separate initiative.

**Companion detail (not competing specs):** the exact Bloomberg-ticker → IMDR-source audits stay in
[`quick_monitor/india.md`](quick_monitor/india.md) (161 tickers) and
[`quick_monitor/korea.md`](quick_monitor/korea.md). Read those for panel-level, ticker-by-ticker
truth; this file is the reconciled spec + current data state + the IN/KR completion punch-list.

This is the automated, IMDR-grounded successor to the manual Bloomberg workbooks in
`data/quick_monitor/` (`Quick Monitor v4 9.xlsm` cross-country board + per-country
`MarketMonitor *.xlsm` / `Market India 1.xlsm`). Those are live BBG spreadsheets refreshed by hand.
Quick Monitor rebuilds that snapshot from IMDR data and bolts on the macro-decomposition layer
(the economy-questions framework, [`economy_questions.md`](../econ/economy_questions.md)).

---

## 1 · What it is (and is not)

| | |
|---|---|
| **Is** | A standing, refreshable **per-country snapshot**: where FX/rates/vol are *now* + how they've moved (Δ1d/1w/1m, z-scores, momentum), **plus** the macro decomposition (what the economy is made of, what's driving it, what's priced), **plus** the cross-country `Econ` board (GDP/CPI/PPI/CA/fiscal/policy/5y-swap/PMI + real-rate rank). Charts + tables. |
| **Is not** | A trade signal (Atlas/Mycroft), a weekly narrative (Perry/Atlas), or a durable framework-only doc. It's the *numbers snapshot*, not the view. |

### Scope decisions (standing)

1. **This project is the *data side*.** The end product is a **full-scale interactive dashboard**,
   but that render surface is a *downstream consumer*. Quick Monitor's deliverable is the
   **grounded per-country data-assembly layer** — every panel/tile resolved to a query + derivation
   (Δ, z-score, surprise, weight), served in a structured, render-agnostic shape. Charts/HTML in
   this repo are validation proofs, not the product.
2. **India + Korea first** (Phase 1), built as the template.
3. **Build the missing market pipelines** (KRW cross-ccy basis, CDS) rather than stubbing N/A — each
   is its own scoped sub-project (§8), pulled forward where it blocks a Phase-1 panel.

**Relationship to the existing layers** (consume, don't duplicate):

| Layer | Doc / agent | Quick Monitor's use of it |
|---|---|---|
| Econ coverage state | [`econ_data_state.md`](../econ/econ_data_state.md) · [`macro_economy_wiring_map.md`](../econ/macro_economy_wiring_map.md) | The macro-layer *inventory* — which `econ.fact_indicator` series exist per country per domain. |
| Economy questions (8×6) | [`economy_questions.md`](../econ/economy_questions.md) · **Smith** | The macro-layer *structure* — Q1 decompose + Q5/Q6 numbers become the monitor's macro panels. |
| Cluster map (what to track) | `cluster_map_spec.md` · **Mercator** | The list of series each country panel must show. |
| 8-driver taxonomy | [`macro_driver_taxonomy.md`](../econ/macro_driver_taxonomy.md) | The surprise/impulse scoring behind the "what moved" tiles. |
| Manual BBG monitors | `data/quick_monitor/*.xls[mb]` | The **markets-layer reference design** — the exact panels/columns to reproduce from IMDR. |

Quick Monitor is the **structured data feed** (numbers, refreshed often, one per tile); Smith is the
**narrative profile** (prose, refreshed on a regime shift). Same framework, same grounding,
different surface. The dashboard consumes the feed; it may also surface Smith's prose as annotations.

---

## 2 · The reference workbooks (decoded)

Six files in `data/quick_monitor/`. Two archetypes:

### 2a · `Quick Monitor v4 9.xlsm` — the **cross-country** board ("the econ monitor")
13 sheets. The template for the *global* top layer:
- **Monitor** — FX board: spot, %ΔCCY, momentum (5v30 DMA), Δbps vol / 25D-RR / rates, 5v30 z,
  term-diff, per-pair rank heat. Plus a KRW rates z-score/vol block (1y…10Y1y forward grid).
- **Econ** — the macro cross-country table: **GDP · CPI · PPI · Current Account · Fiscal Deficit ·
  Policy Rate · 5y Swap · PMI (+ΔPMI)** per country, with *next-release* dates; and a **real-rate
  ranking** (Policy Rate − CPI) sorted across 14 countries. *This is the "econ monitor" proper.*
- **Heat Maps · FX · FX Options · Govvies · ASW · Basis XCCY · Inflation/Inflation2 · seag-infp ·
  GDP Components** — the per-asset detail tabs.

### 2b · `MarketMonitor {Korea,India,China,Australia} 1.xlsm` + `Market India 1.xlsm` — the **per-country** monitor
The template for each country page. Consistent block layout (IN/KR confirmed):
- **Header** — country, ccy, REER (z-score), 50d–100d MA, 3m carry, 3m vol, Sharpe, 25D RR/BF 3M;
  context refs: Oil (Brent), S&P, US 10y.
- **Returns** — equity index, ccy, 10y bond index (level, 1d/1w).
- **Credit** — 5Y CDS on local names (SBI/ICICI/REL for IN; sovereign for KR) — level + Δ.
- **FX forwards** — onshore vs offshore points + implied yields, 1m…12m + fly (1s2s…1s12s).
- **IRS** — onshore/offshore swap curve, Δ1w/1m/6m, offsh−onsh spread.
- **Govt bonds** — curve level, Δ, 3m/6m fwd curve, roll.
- **Bond-swap spread · butterflies** — ASW + fly grid.
- **FX vol** — implied vs realized by tenor (onshore/offshore), 25D RR / 25D BF term structure.
- **Trade** — top exports (to) / imports (from) by counterparty + product, with counterpart GDP.

**Takeaway:** the per-country monitor is a **rates+FX desk snapshot**; the cross-country board is the
**macro/econ snapshot**. Quick Monitor = both, rebuilt from IMDR + the 8×6 macro-decomposition.

---

## 3 · Target deliverable — the per-country data feed

**The deliverable is a structured, render-agnostic data object per country** — one entry per
tile/panel below, each carrying: value(s), the derivations (Δ1d/1w/1m, z-score, momentum,
standardised surprise, weight), the series metadata, and the source trace. A full-scale dashboard is
the downstream consumer; charts/HTML here are *proofs the feed is correct*, not the product. The
panel taxonomy mirrors the BBG monitors — two layers:

### Layer A — Markets snapshot (reproduce the per-country BBG monitor from IMDR)
1. **Header tiles** — spot, %Δ, REER z-score, carry, vol, Sharpe, RR/BF; oil/S&P/UST context.
2. **FX** — spot + forwards (onshore/offshore, implied yields), FX vol surface (implied/realized, RR/BF term).
3. **Rates** — IRS curve + Δ, curve fwds/roll, ASW/butterflies, cross-ccy basis.
4. **Equity + credit** — local index level/Δ; CDS (where sourced).

### Layer B — Econ/macro decomposition (the "econ monitor" + the 8×6 read)
5. **Cross-country `Econ` board** — GDP/CPI/PPI/CA/Fiscal/Policy/5y-swap/PMI + **real-rate rank**.
6. **The 8 domains**, each a compact panel answering the archetypes it can support from data:
   - **Q1 Decompose** → stacked-weight chart (CPI baskets; GDP by expenditure/sector; BoP).
   - **Q5 Surprise** → recent releases vs consensus, standardised surprise (`cb_events` + `fact_indicator`).
   - **Q6 Priced** → policy path vs OIS-implied (where the curve supports it).
   - Q2/Q3/Q4 (driver/sensitivity/history) → sourced from Smith's profile / research corpus, shown
     as annotations, not recomputed here.

### Feed shape & validation charts (see §6)
Each panel → a typed record: `{tile, value, deltas, zscore, surprise, weight, series_id, source}`.
Validation proofs render the families the dashboard will need: time-series (level + Δ),
stacked-weight (decomposition), heat (z-score/rank), surprise bar.

---

## 4 · Data state — **India & Korea** (DB-verified 2026-07-22)

> Level-1 question: *"do we have the data to recreate the monitor in its entirety?"* The
> ticker-by-ticker audit lives in the companion docs ([`india.md`](quick_monitor/india.md) ·
> [`korea.md`](quick_monitor/korea.md)). This section is the reconciled, current rollup.

Legend: ✓✓ deep · ✓ present/fresh · ◐ derivable/partial/stale · ✗ gap (needs a pipeline or a source decision).

### 4.0 · Headline econ coverage (live `econ.fact_indicator`, 2026-07-22)

| | India | Korea |
|---|---|---|
| Active indicators (with obs) | **~1,580** (1,564 with data) | **197** |
| Observations | ~105,300 | ~173,100 |
| Latest actual | 2026-07 (weekly/daily series to 2026-07) | 2026-07-21 |
| Vendors | rbi 569 · upag 368 · ogd 207 · dgcis 198 · mospi 133 · nsdl 33 · cga 30 · dpiit 26 · fred 7 · bis 6 · imd 3 | kosis 164 · **kofia 25** · reb 4 · fred 3 · bis 1 |

> **Reconciliation note:** Korea is **197 active** now (not the 172 in the 2026-06-24
> `econ_data_state.md` snapshot) — the **KOFIA freeSIS round (25 daily indicators, 2026-07-20)** is
> live in `kr_daily`. Re-run the §4.0 queries to refresh `econ_data_state.md` when convenient.

### 4a · Markets layer

| Panel | Source table | India (INR) | Korea (KRW) |
|---|---|---|---|
| **FX spot + forwards** | `fx.fact_fx_rate` | ✓✓ USD/INR, 22 tenors, fresh | ✓✓ USD/KRW, 22 tenors, fresh |
| **FX vol (implied/RR/BF)** | `fx.fact_vol` | ✓✓ fresh | ✓✓ fresh |
| **IRS / swap curve** | `rates.fact_observation` | ✓ INR MIFOR (id 34, fresh to today) + MIBOR OIS (id 54, fresh) | ✓ KRW CD (id 35) + 91D_CD_3M (id 48), both fresh to today |
| **Onshore OIS** | `rates.fact_observation` | ✓ INR MIBOR (rfr/ois) fresh | ◐ **KOFR (id 61) STALE — latest 2026-05-28** (verified 2026-07-22; ops refresh) |
| **Cross-ccy basis** | `rates.*` | ✗ no INR basis curve (minor for IN) | ✗ **KRW basis** shown in monitor — not in IMDR (only EUR/AUD/USD basis exist) |
| **Govt bond curve** | `rates.fact_bond_instrument_obs` | ✅ IGB **20 bonds / 3,052 obs**, fresh to 2026-07-17 (Govy Track B) + 28 auctions | ✅ KTB **12 bonds / 1,500 obs**, fresh to 2026-07-17 (Track B); deep CMT via Track A pending |
| **Equity index** | `equities.fact_index_level` | ✓ Nifty 50 (NSEI), fresh | ✓ KOSPI 200 (KS200), fresh |
| **CDS / credit** | — | ✗ no credit schema (SBI/ICICI/REL 5Y CDS) | ✗ sovereign CDS not held |
| **REER z-score** | `econ` | ✓ `BIS.REER.BROAD.IN` (monthly) | ✗ **not ingested** (extend BIS fetch — trivial) |
| **carry / Sharpe / MA** | derived | ◐ computable from `fx.*` | ◐ computable from `fx.*` |

### 4b · Econ/macro layer (the 8 domains + the `Econ` board)

Active-indicator counts by category (DB-verified 2026-07-22):

| Domain | India | Korea | Notes |
|---|---|---|---|
| **D1 Inflation** | ✓✓ Consumer prices **206** | ✓ Consumer prices **25** (incl. **6 PPI** `BOK.PPI.*`) | IN deep (tradable/non-tradable + basket weights). **KR PPI IS held** (mis-filed under Consumer prices) — the old korea.md "PPI ◐ confirm" is resolved. |
| **D2 Growth** | ✓ GDP **88** | ✓✓ GDP **51** | Both support Q1 GDP-by-expenditure decompose. |
| **D3 Labour** | ✗ **no `econ` labour category** (only PMI/unemp via `cb_events`) | ✓ Labour **10** + Sentiment **15** | **IN labour is a genuine gap.** |
| **D4 Housing & credit** | ✗ **no `econ` housing/credit category** | ◐ Housing **8** + Credit aggregates **3** | IN housing/credit essentially absent; KR thin (loans, not a price index). |
| **D5 External & FX** | ✓✓ BoP **506** + FX&reserves **31** | ✓ BoP **30** | IN external is the deepest domain; KR adequate. |
| **D6 Fiscal** | ✓ CGA deficits held (`INDIA.FISCAL.DEFICIT.*`) — **mis-filed under "Other / uncategorised"** | ✓ **held** — `BOK.FISCAL.*` (Revenue/Expenditure/Net Lending/Taxes) **mis-filed under "GDP and components"** | **RECONCILED: KR fiscal is NOT a data gap** (old korea.md said "no KR fiscal at all" — wrong). Both countries: data present, category wrong → recategorise (trivial). |
| **D7 CB reaction** | ✓✓ Policy rates **43** + CB balance sheet **72** + CB liquidity **15** | ◐ Policy rates **12** + CB liquidity **9** + CB balance sheet **2** | Consensus via `cb_events` both; KR CB balance-sheet thin (KOFIA adds fund-AUM/MMF to 4.2). |
| **D8 Global transmission** | cross | cross | Oil/UST/S&P context in monitors; China/semis beta needs external series. US econ live. |

**Consensus/surprise inputs** (`calendar.cb_events`) — both well-covered (IN ~35 event categories,
KR similar). This powers Q5 surprise + the `Econ` board's next-release dates.

**The cross-country `Econ` board — IN & KR rows, current verdicts:**

| Econ field | India source | KR source | IN | KR |
|---|---|---|---|---|
| GDP (YoY) | `econ` GDP (88) | `econ` GDP (51) | ✓ | ✓ |
| CPI (YoY) | `econ` CPI (206) | `econ` CPI (25) | ✓ | ✓ |
| PPI / WPI | `econ` WPI (DPIIT) | `econ` `BOK.PPI.TOTAL.LEVEL.KR` | ✓ | ✓ *(was ◐)* |
| Current Account | `econ` BoP (506) | `econ` `BOK.BOP.CA.TOTAL.KR` | ✓ | ✓ |
| Fiscal Deficit | `INDIA.FISCAL.DEFICIT.FISCAL.IN` | `BOK.FISCAL.NET_LENDING.KR` | ✓ ◐ recat | ✓ ◐ recat *(was ✗)* |
| Policy Rate | `econ` Policy rates (43) | `BIS.POLICY_RATE.KR` / `econ` (12) | ✓ | ✓ |
| 5y Swap | `rates` INR MIFOR/MIBOR 5Y | `rates` KRW CD 5Y | ✓ | ✓ |
| PMI + ΔPMI | `calendar.cb_events` | `calendar.cb_events` | ◐ | ◐ |
| Exports / Imports | `econ` BoP | `econ` BoP | ✓ | ✓ |

**Verdict:** both `Econ` rows are recreatable from IMDR today — **8/9 fields ✓** each; PMI via
`cb_events` (◐); fiscal held but mis-categorised for both.

### 4c · Completeness edges (neither country is blocked on the *core* snapshot)

FX, rates, vol, CPI, GDP, PPI, BoP, policy, PMI, equity, govt bonds, real-rate rank all exist today.
The remaining gaps are the completeness edges — sequenced in §7 punch-lists.

---

## 5 · Architecture (proposed — for review, not built)

Per project rules, **nothing is wired or built without explicit OK**. Proposed shape:

- **Data access:** read-only, reuse existing tables — `econ.fact_indicator`, `rates.fact_observation`,
  `rates.fact_bond_instrument_obs`, `fx.fact_fx_rate`, `fx.fact_vol`, `equities.fact_index_level`,
  `calendar.cb_events`. No new DDL for Phase 1.
- **Assembly (the deliverable):** a per-country builder (playground first, per PLAYGROUND-ONLY rule)
  that pulls each panel's series, computes the Δ / z-score / momentum / surprise / weight derivations,
  and emits the **structured, render-agnostic feed object** (§3). One record per tile; stable schema.
- **Missing-source pipelines (build, don't stub):** KRW cross-ccy basis, CDS — each a scoped
  ingestion sub-project (§8), pulled forward when it blocks a Phase-1 panel.
- **Render:** out of scope — a downstream **full-scale dashboard** consumes the feed. This repo only
  produces validation charts (dataviz skill). No dashboard here without a separate OK.
- **Grounding discipline:** every tile traces to a query/series. Actuals from
  `econ.vw_fact_indicator_latest` (latest vintage per obs; base `econ.fact_indicator` keeps
  revision vintages); consensus from `cb_events` (low-trust actual); no number without a source.

---

## 6 · Charts spec (first pass)

Follow the `dataviz` skill (load before writing any chart code). Chart families:
1. **Level + Δ time-series** — FX spot, curve levels, index — with 1d/1w/1m markers.
2. **Curve** — IRS/govt curve snapshot + fwd/roll overlay.
3. **Stacked-weight decomposition** — CPI baskets (tradable/non-tradable, food/energy/services), GDP by expenditure/sector, BoP.
4. **Heat / z-score** — cross-country real-rate rank, per-pair momentum, vol z.
5. **Surprise** — actual vs consensus, standardised surprise bar (per release).

Light + dark theme-aware; brand-neutral palette per the skill; wide tables scroll in their own container.

---

## 7 · Completion punch-lists — India & Korea

Ranked by ease. Citi checked: Citi Velocity is **DM-only for sovereign bonds** (no APAC EM govvies)
and carries **no credit/CDS**; its cross-ccy basis (`XCCY_OIS`) is **G10-only (no KRW)**. Citi *does*
cover the context feeds (UST/TSY, REER_IDX/NEER_IDX for 50+ ccys incl. KRW).

### 7a · India — remaining to "fully ready"

| # | Item | Fix path | Difficulty |
|---|---|---|---|
| 1 | **Fiscal recategorise** — `INDIA.FISCAL.DEFICIT.*` sit in "Other / uncategorised" | metadata reassignment, data already held | **trivial** |
| 2 | **US context** — UST cash 10y, US 3M | Citi **TSY** + **T_BILL** + **BENCH_RATES** (accessible) | **easy** |
| 3 | **PMI into `econ`** · **onshore fwd/vol cut** | promote PMI from `cb_events`; add onshore or accept offshore-only | easy–medium |
| 4 | **Govt-bond read-time derivation** — CMT curve tiles, Δ-from-history, flies/roll, derived ASW *(data ✅ loaded)* | read-side builder over `fact_bond_instrument_obs`; see [`govt_bond_population.md`](govt_bond_population.md) | medium |
| 5 | **`econ` Labour + Housing/credit domains** | new fetchers (D3/D4 currently empty for IN) | medium |
| 6 | **Context indices** — DXY, ADXY, Brent | Citi has NEER proxy + WTI; true DXY/Brent = BBG | medium (minor tiles) |
| 7 | **Single-name CDS** (SBI/ICICI/REL) | not on Citi — new vendor + new credit schema | **hard** |

### 7b · Korea — remaining to "fully ready"

| # | Item | Fix path | Difficulty |
|---|---|---|---|
| 1 | **REER** — `BISBKRR` not ingested | Citi **REER_IDX** *or* extend the existing BIS REER fetch (India's is loaded) to add KR | **trivial** |
| 2 | **KOFR (onshore OIS) staleness** — latest 2026-05-28 (verified 2026-07-22) | refresh the KOFR feed (curve already exists) | **trivial** (ops fix) |
| 3 | **Fiscal recategorise** — `BOK.FISCAL.*` sit under "GDP and components" | metadata reassignment, data already held *(NOT a data gap — reconciled 2026-07-22)* | **trivial** |
| 4 | **US context** — UST 10y, US 3M | Citi **TSY**/**T_BILL** (accessible) | **easy** |
| 5 | **Govt-bond read-time derivation** — CMT/Δ/fly *(KTB data ✅ loaded)*; deep-history CMT via **BBG_mirror Track A** (GVSK 2007+, still gated) | read-side builder; Track A load for long history | medium |
| 6 | **House-price index** — have HH loans, not prices | add a KR house-price series (KOSIS/REB) | medium |
| 7 | **Deepen CPI** (services/non-tradable split) + **CB balance sheet** (thin: 2 series) | targeted KOSIS/BOK fetchers | medium |
| 8 | **KRW cross-currency basis** — a whole monitor panel | not on Citi (G10-only) — BBG_mirror or derive | **hard** |
| 9 | **Sovereign CDS** | not on Citi — new vendor + credit schema | **hard** |

---

## 8 · Phased plan (proposed)

- **Phase 0 — spec (this doc)** + IN/KR data state. ✅ (reconciled 2026-07-22)
- **Phase 1 — India + Korea data feeds.** Build the per-country builder → structured feed (§3) for
  every panel buildable from existing tables (FX, vol, IRS, govt bonds, CPI, GDP, PPI, BoP, policy,
  PMI, equity, real-rate rank). Validation charts as proof. Settle the open questions in §9.
- **Phase 2 — cross-country `Econ` board** (real-rate rank across the roster) + trivial fills
  (IN/KR fiscal recategorise, KR REER, KOFR refresh).
- **Phase 3 — build the gap pipelines** (each a scoped ingestion sub-project; pulled forward if it
  blocks a Phase-1 panel): ~~govt-bond curves (IN + KR)~~ ✅ **DONE 2026-07-20** (Govy Track B; see
  [`govt_bond_population.md`](govt_bond_population.md)) · KRW cross-ccy basis · CDS · IN `econ` labour
  + housing/credit · KR house-price index · deepen KR CPI/CB-BS.
- **Phase 4 — cadence + roster rollout** (China, Australia next per
  [`quick_monitor/README.md`](quick_monitor/README.md)); hand the stable feed to the dashboard build
  (separate project).

---

## 9 · Open questions

**Resolved:** render surface = full-scale dashboard, downstream (this project is the data side);
markets gaps = build the pipelines, don't stub; scope = India + Korea first.

Still open:
1. **Refresh cadence** — on-demand vs scheduled (daily markets, monthly macro)? Not wired without OK.
2. **Macro-layer depth** — how much of Smith's Q2/Q3/Q4 prose does the feed carry vs leave the
   dashboard to fetch from the profile?
3. **Feed schema + transport** — exact record shape, and how the dashboard reads it (DB table?
   parquet? JSON API?). Decides whether a small `quick_monitor` output store is needed (new DDL →
   explicit OK).
4. **Derivation defaults** — Δ windows, z-score lookback, surprise standardisation — reuse 8-driver
   defaults unless a panel needs otherwise.

---

## 10 · Checklist (Phase 1 entry — India + Korea feeds)

- [ ] Feed record schema agreed (§9 Q3) — fields + transport (table/parquet/JSON).
- [ ] IN/KR fiscal recategorised out of "Other" / "GDP and components" (§7 — trivial, data held).
- [ ] KR REER ingested (extend BIS fetch) + KOFR staleness refreshed (§7b #1–#2).
- [ ] Panel-by-panel query inventory written for IN + KR — one read-only query per tile.
- [ ] Derivation rules pinned (Δ windows, z-score lookback, surprise standardisation).
- [ ] Chart family prototypes (dataviz skill) reviewed as validation proofs.
- [ ] Explicit OK to build in `playground/` (no prod wiring).

---

**References:** [`quick_monitor/india.md`](quick_monitor/india.md) ·
[`quick_monitor/korea.md`](quick_monitor/korea.md) · [`govt_bond_population.md`](govt_bond_population.md) ·
[`econ_data_state.md`](../econ/econ_data_state.md) · [`macro_economy_wiring_map.md`](../econ/macro_economy_wiring_map.md) ·
[`economy_questions.md`](../econ/economy_questions.md) · [`macro_driver_taxonomy.md`](../econ/macro_driver_taxonomy.md) ·
Smith (`.claude/agents/smith.md`) · reference workbooks `data/quick_monitor/`.
