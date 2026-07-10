# Macro Driver Taxonomy — the shared 8-driver lens

**One taxonomy, three consumers.** This is the canonical bridge between the
[macro wiring map](macro_economy_wiring_map.md) (the four loops) and the three
per-country macro lenses that read a country through it:

| Lens | Doc | How it uses the drivers |
|---|---|---|
| **Mercator** — cluster map | [`../research/cluster_map_spec.md`](../research/cluster_map_spec.md) | The bucket-legend chips on each cluster box are these 8 drivers (+ a country-specific bucket). |
| **Atlas** — global weekly | [`../research/atlas_brief_spec.md`](../research/atlas_brief_spec.md) | The per-country "Macro read" dimensions + the **L4 data-surprise ladder** rank countries by the composite driver score computed here. |
| **Rates playbook** — Mercator's quant sibling | [`../research/rates_playbook_spec.md`](../research/rates_playbook_spec.md) *(pending)* | The "Macro impulse by driver" diverging bar + the page-3 monitoring web are these 8 drivers; the composite is their weighted sum. |

Authoring this once means the playbook's surprise-scoring engine feeds Atlas's L4
ladder for free, and all three lenses speak the same language.

- **Status:** active — the canonical driver set + the machine-readable mapping.
- **Machine-readable mapping:** `playground/econ/rates_playbook/driver_taxonomy.yaml`
  (prototype location; promotes to `src/imdr/config/` when the engine is
  productionised). The YAML is the source of truth for the row-level
  `category → driver + polarity` map; this doc is the human spec.
- **Date:** 2026-06-22.

---

## 1 · The 8 drivers

Drawn from the wiring map's four loops (Growth → Inflation → External/FX →
Policy), split to the granularity the playbooks use:

| # | Driver | Wiring-map loop | What it captures |
|---|---|---|---|
| 1 | **Inflation/Wages** | Inflation | CPI, core, PPI, GDP deflator, wages, overtime, expectations |
| 2 | **Labour** | Growth | Unemployment, jobs-to-applicants, payrolls, participation |
| 3 | **Growth/Activity** | Growth | GDP, IP, tertiary/activity indices, machinery/machine-tool orders, leading index |
| 4 | **Demand** | Growth | Consumption, retail, household spending, capex/private investment, confidence |
| 5 | **External/Liquidity** | External/FX | Current account, trade balance, exports, imports, reserves |
| 6 | **Housing/Credit** | (Credit) | Bank lending/loan growth, money/monetary base, housing starts, credit aggregates |
| 7 | **Surveys** | (cross) | PMIs (mfg/services/composite), business-survey indices, eco-watchers/sentiment surveys |
| 8 | **Policy/Fiscal** | Policy | Policy-rate decisions, fiscal impulse, guidance |

These 8 are the **fixed spine**. Mercator additionally rotates in **one
country-specific bucket** for its cluster legend (Tech for TW, Dairy for NZ,
Wages-as-its-own for JP, Commodities for AU) — that's a *display* lens on top of
these 8, not a 9th scoring driver. The playbook + Atlas L4 score on the 8 only.

> **Scoring drivers ≠ display dimensions.** These 8 are the **scoring** drivers
> (what `cb_events` releases get aggregated into). They are not the full set of
> *display* lenses the three consumers show: **FX** and **Policy/Fiscal** are
> first-class on Atlas's scorecard and on Mercator's cluster grid, but they carry
> little *surprise* signal (FX has no scheduled release in `cb_events`; policy-rate
> decisions are usually priced, so Policy/Fiscal scores ≈ 0 — see the exemplars'
> +0.00/+0.02). So FX sits *alongside* the 8 as a display/price dimension, not as
> a 9th scoring driver. Don't read the absence of an FX scoring driver as a gap —
> FX enters via the repricing ladder + the scorecard, not the surprise engine.

> **Overlap is real: Surveys vs Growth/Activity.** A manufacturing PMI is *both* a
> survey and a growth signal; it lives in **Surveys** by convention so it isn't
> double-counted. Note the consequence: three of the eight drivers (Labour,
> Growth/Activity, Demand) are growth-flavoured, so the composite is structurally
> **growth-weighted**. That's intentional (rates react hard to the growth pulse)
> but worth knowing when a composite looks growth-driven — it partly reflects the
> taxonomy's shape, not only the data.

## 2 · Polarity — what "hawkish" means per driver

The surprise score is signed so that **positive = sell-off / hike pressure** and
**negative = rally / cut pressure** (matching the playbooks' convention). Polarity
maps a data surprise to that sign:

| Driver | Higher actual vs survey ⇒ | Polarity (+1 = higher is hawkish) |
|---|---|---|
| Inflation/Wages | hotter inflation ⇒ hawkish | **+1** |
| Labour — unemployment rate | more slack ⇒ dovish | **−1** |
| Labour — jobs-to-applicants / payrolls / vacancies | tighter labour ⇒ hawkish | **+1** |
| Growth/Activity | stronger growth ⇒ hawkish | **+1** |
| Demand | stronger demand ⇒ hawkish | **+1** |
| External/Liquidity — current account / trade balance / exports | stronger external ⇒ hawkish | **+1** |
| External/Liquidity — imports | (demand-led, but worsens balance) | **+1** with low weight |
| Housing/Credit | faster credit/money/housing ⇒ hawkish | **+1** |
| Surveys | higher PMI/sentiment ⇒ hawkish | **+1** |
| Policy/Fiscal | tighter/hawkish surprise ⇒ hawkish | **+1** |

Polarity is **per-indicator** (the YAML carries it row-by-row), because within a
driver a few series invert (unemployment in Labour). The per-driver table above is
a *reading guide* — **the YAML's 63 row-level entries are the source of truth.**
When a new `cb_events` `category` appears that isn't mapped, the engine logs it as
`unmapped` (neutral, zero weight) rather than guessing — and it's added to the
YAML on review.

> **Regime-ambiguous series — money/credit aggregates.** A handful of series have
> a sign that genuinely depends on the policy regime, and the taxonomy makes a
> *documented choice* rather than pretending it's clean:
> - **Monetary base / money-growth** is mapped **+1** (faster money growth ⇒
>   inflationary ⇒ hawkish), matching the exemplars' convention (*"Sell-off:
>   money growth accelerates"*). **Caveat:** for a country in active **QT** (e.g.
>   Japan, monetary base YoY negative), a *bigger-than-expected contraction* is
>   really a *tighter policy stance* (hawkish), but under the +1 money-growth
>   framing it scores **dovish**. We keep +1 because (a) it matches the exemplar
>   oracle's Housing/Credit sign and (b) flipping to −1 would misread money-growth
>   regimes. Treat this driver's contribution as low-confidence in QT/QE regimes.
> - **Imports** is mapped **+1 at low weight** — higher imports signal stronger
>   domestic demand (hawkish) *but* worsen the trade balance (the External read),
>   so the sign is contested; the low weight reflects that, it isn't a clean read.
>
> The rule: where a series is regime-ambiguous, pick the exemplar-consistent sign,
> **mark it low-confidence in the YAML comment**, and never let it dominate a
> driver. Don't silently encode a contested sign as if it were settled.

## 3 · Scoring (the surprise engine)

For each release with both `actual` and `survey` in `calendar.cb_events`:

```
raw_surprise = (actual − survey)                     # parse %/¥B/index strings to float
z            = raw_surprise / scale(indicator)        # see "scale calibration" below
score        = clamp(polarity × z × k, −3, +3)        # capped at ±3, matching the exemplars
```

- **No survey?** Fall back to `actual − prior` at **lower weight** (the exemplars
  say so explicitly: *"When no survey exists, read uses actual versus prior with
  lower weight"*).
- **Driver impulse** = recency-weighted mean of its releases' scores over the
  window (more recent prints weigh more).
- **Composite macro impulse** = relevance-weighted **mean** of the 8 driver
  impulses, **normalized** so it stays in the exemplars' small range (their
  composites run ≈ −0.5..+0.5, e.g. JP +0.04, IN +0.42 — a raw *sum* of eight
  ±3-capped impulses would blow past that, so the composite is a weighted mean,
  not a sum; high-`relevance` events like rate decisions, NFP, CPI weight more).
- **Sell-off / rally risk** (each /5) = scaled functions of the positive vs
  negative score mass.
- **Indicator balance** = counts of hawkish / neutral / dovish reads.

### Scale calibration — the highest-leverage, least-settled choice

`scale(indicator)` is the divisor that turns a raw surprise into a comparable
z-score, and it **dominates the magnitude** of every driver impulse (it decides
whether a driver prints +0.3 or +1.2). It is **not yet principled**: the prototype
YAML carries hand-set per-category "typical 1-σ surprise" seeds (CPI 0.2pp, wages
0.3pp, current account ¥500B, PMI 1.0 idx…) chosen to land the JP run near the
oracle. Treat those as **seed defaults, not calibrated values.**

> **Target method (pending the `cb_events` backfill):** replace each seed with the
> **rolling standard deviation of that category's own surprises** over a trailing
> window (per country). This makes the score a true normalized surprise and removes
> the hand-tuning. It needs ≥12 months of `cb_events` history to be stable — which
> is the *same* backfill that fixes the driver-sign gap (below). Until then, the
> seeds are a stopgap and absolute magnitudes are indicative, not authoritative.

### The dominant failure mode: window / data-completeness fragility

**This is the #1 caveat.** The composite is a recency-weighted score over a *fixed
window*, so it is fragile to exactly the gaps `cb_events` has. The JP prototype
proved it: with ~5 of 16 weeks missing (`cb_events` only reaches back to ~Apr-2026
for most countries), three driver **signs flipped** versus the oracle — because the
Feb–Mar dovish counterweight simply wasn't in the data. The engine logic was
correct; the window was incomplete.

Consequences to honour:
- A playbook built on a partial window can carry the **wrong sign**, not just a
  wrong magnitude — never present it as authoritative until the window is complete.
- **Tier honestly** (same A/B/C reality Atlas surfaced): a country/window with few
  scored releases shows fewer indicators and *says so*, rather than faking a read.
- The fix is upstream: **backfill `cb_events` to ≥12 months** of TradingEconomics
  history. That single action both fills the window AND enables real scale
  calibration above.

The exemplars are the **structural oracle**, not a to-the-decimal one — they were
built from an uploaded workbook snapshot, so IMDR-computed numbers will be very
close (same TE releases) but not identical (snapshot timing, occasional revised
survey, window completeness). Validate on *structure + sign + rough magnitude*,
not exact equality.

## 4 · Driver → curve transmission (the monitoring web)

Each driver maps to the rate tenors it most moves (playbook page 3 "Tenor focus").
Default mapping (overridable per country):

| Driver | Tenor focus |
|---|---|
| Inflation/Wages | 6m · 1y · 6m6m |
| Labour | 1y · 2y · 1y1y |
| Growth/Activity | 2y · 2y1y · 5y |
| Demand | 1y · 2y · 2y1y |
| External/Liquidity | 2y1y · 5y · 10y |
| Housing/Credit | 2y · 5y · 1y1y |
| Surveys | 6m6m · 1y1y |
| Policy/Fiscal | 6m · 1y · front futures |

These tenors resolve to `rates.fact_observation` rows on the country's primary OIS
curve: spot `6M/1Y/2Y/5Y/10Y` (`quote='par'`) + forwards `6M.6M / 1Y.1Y / 2Y.1Y /
5Y.5Y` (`quote='fwd'`). Confirmed present for the full playbook roster (26 ccy in
`rates.dim_curve`, ~90-108 tenors per curve, updated daily).

## 5 · Data sources in IMDR (verified 2026-06-22)

> **⚠ `cb_events` IS NOT TRUTH.** It's a scraped TradingEconomics calendar. Its
> truth domain is exactly two things: **the consensus/survey/forecast (the
> "expected")** and **the event calendar (timing)**. Its `actual` is a low-trust
> placeholder and its implied hike/hold is NOT reliable (it stores post-meeting
> *levels*, so a hike that was expected reads as "hold"). **Never treat
> `cb_events.actual` or a `cb_events`-derived policy action as authoritative.** The
> realised value, and whether a CB actually moved, come from official sources / the
> corpus. (Confirmed 2026-06-23: `cb_events` stored BI & BSP as holds when the
> corpus is unambiguous they *hiked* 25bp.)

| Engine input | Source of TRUTH (in priority order) | Notes |
|---|---|---|
| **Consensus / survey / forecast** (the "expected") | `calendar.cb_events` | This IS cb_events' truth domain — the only consensus source. Backfilled to ~13-month trailing (May-2025 → present, vendor_id=73). |
| **Event calendar** (what releases when) | `calendar.cb_events` | Also cb_events' truth domain — timing/scheduling. |
| **Actual** (the realised value) | (1) `econ.fact_indicator` official first-party → (2) the research **corpus**'s stated figure → (3) `cb_events.actual` **LAST-RESORT, low-trust, flag it** | Official econ pipelines (BLS/BEA/ABS/BPS/RBI/KOSTAT/…) are cleaner, revised, and carry series TE misses (e.g. Q1 Tankan). Surprise = (official/corpus actual) − (cb_events consensus). |
| **Policy action** (hike / hold / cut) | (1) official policy-rate series (`econ.fact_indicator` BIS/CB) → (2) corpus | Derived from `actual vs prior` on the **official** rate series — NOT from cb_events' label. This is a separate axis from the *surprise* (`actual vs consensus`): a fully-expected hike has zero surprise but is still a hike. |
| Curve repricing (spot + forwards by tenor) | `rates.fact_observation` (20.96M rows) + `rates.dim_curve` | Full roster, ~90+ tenors, daily to today. JP 10y move reconciled to ~1bp vs exemplar. |
| Indicator → driver + polarity | `driver_taxonomy.yaml` (this taxonomy) | Authored here. |

> **The exemplar is a STRUCTURAL oracle, not a sign-by-sign one.** The repricing
> ladder reconciles to ~1bp (rates are one market). But surprise *scores* depend
> on which releases + which survey values you feed — and `cb_events` (TE) is a
> *different dataset* than whoever built the exemplar workbook. The 2026-06-23
> backfill (filling the JP Feb–Mar window) moved the drivers toward the exemplar
> but did NOT flip the 3 mismatched signs, proving the residual is a **data-source
> difference** (different events/surveys; Q1 Tankan absent from TE) compounded by
> recency-weighting, **not** a window gap. **Do not validate the engine by matching
> the exemplar's driver signs.** Validate on (a) the repricing ladder, (b) internal
> consistency, (c) spot-checked individual release scores, and (d) first-party
> actuals from `econ.fact_indicator`. The exemplar defines the *format + the
> ladder*, not the ground-truth scores.

> The surprise-coverage skew is the same A/B/C reality Atlas surfaced — a playbook
> for a thin-coverage country (TW/SG/PH/TH/NZ) shows fewer scored indicators and
> says so, rather than faking a full snapshot.

---

**Eight drivers, one polarity convention, one scoring rule — shared by Mercator's
map, Atlas's ladder, and the rates playbook's impulse bar. Author once, consume
three times.**
