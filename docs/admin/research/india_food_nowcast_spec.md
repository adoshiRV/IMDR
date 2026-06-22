# India Fresh-Food Inflation Nowcaster — Design Spec

Last updated: 2026-06-22

> **Status: DESIGN / PRE-BUILD.** No code has been written for this
> feature yet. This spec governs the build. The foundational config artifact
> (`src/imdr/domains/econ/india_food_basket.py`) is already built and tested.
> The data source pipeline (`econ.fact_india_mandi` / OGD Agmarknet) is
> pre-prod — see [india_mandi_prices.md](../econ/india/india_mandi_prices.md).

---

## 1. Goal & thesis

MoSPI publishes the headline CPI print roughly on the 12th of each month,
covering the prior calendar month. The **volatile, mandi-observable slice** of
the food basket — Vegetables + Fruits + Spices — is the sub-group where
month-on-month surprises actually live. Cereals, pulses, and oils are
anchored by MSPs, buffer stocks, or import flows; they move slowly and are
explicitly excluded from this nowcast.

Wholesale mandi (mandated agricultural market) prices lead retail CPI by
**approximately 1–3 weeks**. Farmers and traders sell at the mandi; the
price then propagates through the wholesale–retail chain before it registers
in the NSO price-collector survey used by MoSPI. This lag is the forecasting
opportunity.

**The thesis:** a CPI-weight-blended index of weekly mandi medians for the
~150 FOCUS commodities (vegetables/fruits/spices), computed on a month-to-date
basis, is a leading indicator of the MoSPI perishables print. An above-seasonal
signal on the composite by the end of week 2 of a month gives a directional
view on the official number a month before MoSPI releases it.

This work ties directly into the broader monsoon/food-price framework:
the regional layer (§9) tracks which deficit zones (Maharashtra, MP, Karnataka)
are driving the spike, and whether it is a genuine supply shock (price up +
arrivals down) or a transient demand flush (price up + arrivals up).

**What this is not:** a full CPI forecast. Milk, meat, eggs, cereals, and
prepared food (collectively ~26% of CPI) are outside scope. The composite
covers ≈11.4% of CPI. It is a **perishables nowcast**, not a headline forecast.

---

## 2. Basket decomposition

### 2a. Mandi-coverable volatile slice (this nowcast)

| CPI Sub-group | 2012-base weight (% of total CPI) | Mandi-observable? | Included |
|---|---:|---|---|
| Vegetables | 6.04% | Yes — daily per-mandi | Yes |
| Fruits | 2.89% | Yes — daily per-mandi | Yes |
| Spices | 2.50% | Partially (fresh spices yes; dried/processed less so) | Yes |
| **Volatile perishables total** | **11.43%** | | **Yes** |

**Onion + Potato + Tomato (TOP trio) ≈ 2.2% of CPI** and account for the
majority of vegetable-inflation volatility. They are all Tier A (≥150 reporting
markets) and sit on the composite spine.

### 2b. Excluded by design — slow movers

| CPI Sub-group | 2012-base weight | Reason excluded |
|---|---:|---|
| Cereals & products | 9.67% | MSP-anchored; buffer stocked; price floors constrain downside |
| Pulses & products | 2.38% | Import-driven; government stock releases smooth shocks |
| Oils & fats | 3.56% | Import-parity driven (palm/soya); not mandi-determined |

These three sub-groups are present in Agmarknet but are in the `EXCLUDE`
list in `india_food_basket.py`. They are neither fetched nor aggregated.

### 2c. Not mandi-coverable (flagged, not excluded)

| CPI Sub-group | 2012-base weight | Note |
|---|---:|---|
| Milk & milk products | 6.61% | Co-operative / procurement-price driven |
| Meat, fish & eggs | 4.04% (Meat&fish 3.61 + Egg 0.43) | Partial Agmarknet coverage; not in FOCUS |
| Prepared meals & snacks | 5.56% | Retail/service sector; not mandi-priced |
| Non-alcoholic beverages | ~0.8% | Not mandi-priced |

**Memo:** 2024-base sub-item weights are pending from MoSPI. The 2024-base
shifted Vegetables to ≈5.08% and Fruits to ≈2.44%; exact spice sub-item
weights not yet published. This spec uses **2012-base throughout** until MoSPI
releases the full 2024-base sub-item table.

---

## 3. Commodity universe and cleanup

The live `econ.dim_india_mandi_commodity` table holds **248 distinct
commodity names** as sourced from OGD Agmarknet (loaded 2026-06).
Evaluating that universe against the CPI basket produced three lists:

| List | Count | Description |
|---|---:|---|
| **FOCUS** | ~150 | Vegetables + Fruits + Spices — fetched and aggregated |
| **EXCLUDE** | ~58 | Grain / pulse / oilseed / sugar / meat-fish — not fetched |
| **STRIP** | ~40 | Non-food entirely — not fetched |

**STRIP highlights:** `Wood` (148 reporting markets — the single most-reported
non-food commodity), `Firewood`, flower varieties (Marigold, Rose, Jasmine,
Lotus, Carnation, Orchid, Gladiolus, ~20 names), livestock (Cow, Buffalo, Goat,
Sheep, Hen), and industrial/medicinal/stimulant crops (Rubber, Cotton, Jute,
Tobacco, Arecanut, Betal Leaves, Ashwagandha, Cocoa, Coffee).

### Naming judgement calls resolved in the config

The following ambiguous cases were resolved during the commodity classification
pass and are fixed in `src/imdr/domains/econ/india_food_basket.py`:

| Agmarknet name | Decision | Rationale |
|---|---|---|
| `Bhindi(Ladies Finger)` / `Ladies Finger` | Merge → `Bhindi(Ladies Finger)` canonical; `Ladies Finger` is an alias | Same crop, two spellings in Agmarknet |
| `Mango` | FRUITS (Tier A) | Ripe fruit |
| `Mango(Raw-Ripe)` | VEGETABLES (Tier A) | Raw/green mango — veg/pickle use, priced with vegetable seasonality |
| `Banana` | FRUITS (Tier A) | Ripe eating banana |
| `Banana - Green` | VEGETABLES (Tier A) | Cooking banana — used as a vegetable |
| `Coriander(Leaves)` | SPICES (Tier A) | Fresh herb — CPI spices |
| `Corriander seed` (sic) | SPICES (Tier C) | Dried seed — distinct price dynamic from leaves |
| `Ginger(Green)` | SPICES (Tier A) | CPI files green ginger under spices |
| `Ginger(Dry)` | SPICES (Tier C) | Processed/dried — different supply chain |
| `Garlic` | SPICES (Tier A) | CPI spices |
| `Green Chilli` | SPICES (Tier A) | CPI files green chilli under spices |
| `Onion` | VEGETABLES (Tier A) | Bulb onion |
| `Onion Green` | VEGETABLES (Tier A) | Spring/green onion — distinct seasonality |
| `Tender Coconut` | FRUITS (Tier B) | Fresh immature coconut — fruit market |
| `Coconut` / `Copra` | EXCLUDE → oilseed | Mature coconut / copra are oilseed supply chain |
| `Gram Raw(Chholia)` | VEGETABLES (Tier C) | Fresh green chickpea — eaten as veg |
| `Bengal Gram(Gram)(Whole)` | EXCLUDE → pulse | Dried pulse |
| `Pegeon Pea(Arhar Fali)` | VEGETABLES (Tier C) | Fresh tur pods — veg |
| `Red gram/Arhar/Tur(whole)` | EXCLUDE → pulse | Dried dal |
| `Gur(Jaggery)` / `Sugar` | EXCLUDE → sugar | Sweeteners; buffer-stocked / import-driven |
| `Papaya` | FRUITS (Tier A) | Ripe |
| `Papaya(Raw)` | VEGETABLES (Tier C) | Green/raw papaya — veg use |

**Source of truth:** `src/imdr/domains/econ/india_food_basket.py` is the
authoritative artifact. The alias map (`ALIASES`), sub-group assignments, and
tier labels there take precedence over any informal list in docs. Tests:
`tests/unit/test_econ/test_india_food_basket.py` (9 passing).

---

## 4. Confirmed judgement calls (2026-06-22)

The following design decisions are locked:

1. **Ginger / garlic / green-chilli → SPICES.** This matches the MoSPI CPI
   sub-group filing. All three are Tier A (abundant market coverage).

2. **Gur / Sugar → excluded from volatile focus.** Gur (jaggery) is a
   semi-processed sugar product; pricing is affected by cane support prices and
   seasonal crushing patterns, not fresh-market supply shocks.

3. **Tender Coconut = fruit (keep); mature Coconut + Copra = oilseed
   (exclude).** Tender coconut prices reflect fresh-fruit demand (summer
   hydration); copra prices are oilseed-equivalent and import-parity influenced.

4. **Composite spine = Tier A, Tier B supporting, Tier C stored but out of
   the headline composite.** A commodity appears in the weekly headline number
   only if it has at least 150 reporting markets on a normal trading day. Tier B
   commodities (50–150 markets) are stored and visible in drill-downs; they
   enter the composite only when coverage holds on a given week. Tier C commodities
   (<50 markets) are stored and searchable but never enter the composite.

5. **No arrivals in the composite (v1).** The OGD resource does not carry
   arrivals quantities. The `arrivals_tonnes` column in `econ.fact_india_mandi`
   is NULL until the UPAg path is built (see §11).

---

## 5. Fetch strategy

The OGD Agmarknet API (`data.gov.in` resource `35985678-0d79-46b4-9ed6-6f13308a1d24`)
supports `filters[Commodity]` as a query parameter, enabling a
**commodity-scoped pull** that fetches only the FOCUS set.

Contrast with a full daily pull: the unfiltered resource returns ~22,000
records/day (all markets × all commodities × all dates in the window).
A FOCUS-scoped pull returns roughly **~8,000–12,000 records/day** (the
non-food STRIP and slow-mover EXCLUDE categories account for ~40–55% of
daily rows by record count). This makes both the daily incremental and
multi-year backfill cheaper and faster.

**Backfill scope:** 5 years of history (≈ 2021 → today) gives sufficient
seasonal-normal computation (§8 uses 5-yr ISO-week normals). The full
Agmarknet history goes back to 2010; the 5-yr window is the minimum viable
target. Full history is a v2 option.

**The nowcast aggregates land in `econ.fact_indicator`** (see §13), not in the
raw `econ.fact_india_mandi` star schema. The fetcher for the raw star schema is
separate from the aggregation pipeline that produces the stored indicators.

---

## 6. Metric stack

Computed weekly (ISO week), per commodity, at national level and for key
deficit states:

| Metric | Description | Notes |
|---|---|---|
| `median_modal_price` | Weekly median of the per-mandi modal price across all reporting markets | Median is robust to the ₹0.66/qtl garbage values found in Agmarknet (see §10) |
| `price_min_band` | 10th-percentile of weekly per-mandi modal | Lower bound of distribution |
| `price_max_band` | 90th-percentile of weekly per-mandi modal | Upper bound of distribution |
| `n_markets` | Count of distinct markets contributing to the week | Confidence metric; governs Tier inclusion |
| `wow_pct` | Week-on-week % change in median | Short momentum |
| `wow4_pct` | 4-week rolling % change in median | Medium momentum |
| `mom_pct` | Month-on-month % change vs same month last year's median | Seasonal-uncorrected MoM |
| `yoy_pct` | Year-on-year % change in median | Annual comparison |
| `vs_seasonal_norm_pct` | % above/below the 5-year ISO-week normal for this commodity (§8) | **Primary shock signal** — strips calendar seasonality |

The **`vs_seasonal_norm_pct`** metric is the key analytical signal. A tomato
spike in September is not a shock if September is always expensive; the vs-norm
metric distinguishes a genuine supply disruption from calendar seasonality.

---

## 7. MoM nowcast

The official CPI is a **monthly average** of surveyed prices, not a point-in-time
observation. To produce an apples-to-apples estimate:

```
nowcast_mom_pct(commodity, month M) =
    (MTD_avg_mandi_median(commodity, M) / prior_month_avg_mandi_median(commodity, M-1)) - 1
```

Where:
- `MTD_avg` = simple average of all ISO-week medians within month M up to
  the most recent complete week
- `prior_month_avg` = average of all complete ISO-week medians within M−1

**Composite perishables MoM:**

The per-commodity MTD MoM figures are then **blended using 2012-base CPI
sub-group weights** (vegetables 6.04 / fruits 2.89 / spices 2.50, normalised
to sum to 1 within the focus set):

```
composite_mom_pct = Σ w_i × nowcast_mom_pct(commodity_i)
```

Where `w_i` is the within-focus CPI weight share. Within a sub-group,
individual commodities are equally weighted (no intra-sub-group item weights
available from MoSPI 2012-base at the required granularity).

**Confidence label:** each nowcast point carries a `(MTD, N/30 days)` label.
A reading on day 7 of the month (N=7) is directional only; a reading on day
25 (N=25) is near-complete.

**Weighting caveat — no arrivals:** ideally each market's contribution would
be weighted by arrivals volume. The OGD resource carries prices only (no
arrivals). Until the UPAg arrivals path is built (§11), the composite uses an
**unweighted cross-mandi median** (i.e., each reporting market contributes
equally). This is flagged on all outputs.

---

## 8. Seasonality

Fresh-food prices are strongly seasonal. Tomatoes are always expensive in
March–May before the summer flush; onions collapse post-kharif harvest.
A naive MoM comparison during a seasonal peak can look alarming even when
supply is normal.

**Per-(commodity, ISO-week) 5-year normal:**

```
seasonal_norm(commodity, ISO_week) =
    median of { weekly_median_price(commodity, ISO_week, yr) : yr in [T-5, T-1] }
```

Computed from the targeted 5-year backfill. The `vs_seasonal_norm_pct` metric
(§6) is then:

```
vs_seasonal_norm_pct = (current_weekly_median / seasonal_norm) - 1
```

A value of +30% means the commodity is 30% above its typical level for that
ISO week of the year — a genuine supply-side signal. The seasonal-norm
computation requires at least 3 complete prior-year observations per
(commodity, ISO-week) cell before a value is published; cells with fewer than
3 observations are stored as NULL with a flag.

**Seasonal patterns to be aware of:**
- Vegetables: kharif harvest flush (Aug–Nov) deflates; pre-kharif lean
  season (Apr–Jun) inflates.
- Onion/Potato: storage-crop dynamics; price often inverted relative to
  harvest date (Maharashtra/Rajasthan storage drawdown Jan–Mar).
- Tomato: strong dual-peak seasonality (winter peak Dec–Feb, summer trough
  after March flush).
- Fruits: mango season (Apr–Jun) collapses mango price; Diwali proximity
  inflates dry-fruit adjacents.
- Spices: green chilli peaks Apr–May pre-monsoon; drops post-kharif.

---

## 9. Regional and monsoon layer

The national median is a blunt instrument during a supply shock, which is
typically concentrated in 2–3 deficit states. The regional layer provides
the diagnostic.

**Key deficit zones tracked (by-state weekly medians):**

| State | Relevance |
|---|---|
| Maharashtra | Onion (Lasalgaon — the dominant national onion market), tomato |
| Madhya Pradesh | Onion (Mandsaur), soyabean/pulse adjacents |
| Karnataka | Tomato (Kolar/Chikballapur, the other dominant tomato market), vegetables south |
| Telangana / Andhra Pradesh | Chilli (Guntur — world's largest), vegetables south |
| Gujarat | Potato (Deesa), vegetable north-west |
| Uttar Pradesh | Potato (Agra), vegetables north |

**Monsoon link:** IMD gridded rainfall data (already live in
`econ.fact_indicator` via `scripts.econ.in.imd.imd_rainfall`) provides the
seasonal deficit/excess context. When a deficit state has a below-seasonal
rainfall deficit AND a vs-seasonal-norm spike in a perishable commodity, the
combination is a persistent-shock signal.

Regional medians are stored at `(state, commodity, ISO-week)` grain alongside
the national figure. They inform the "regional hotspot" section of the
Fresh-Food Pulse brief (§14) but are not included in the headline composite
MoM nowcast.

---

## 10. Data hygiene

### Known quality issues in the OGD source

The OGD Agmarknet data has documented entry errors:

- **Sub-₹100/qtl outliers:** in one day's pull of 17,935 rows, approximately
  46 records had modal prices below ₹100/quintal. The lowest confirmed example
  was ₹0.66/qtl — an obvious data-entry error (likely paise vs rupees, or a
  decimal misplacement). These are dropped.
- **Implausible highs:** occasional records show prices 10× the commodity
  median for that market. These are winsorised at the 99.5th percentile per
  (commodity, state) pair over a rolling 90-day window before the weekly
  aggregation.

### Per-commodity hygiene rules

| Rule | Implementation |
|---|---|
| Drop if `price_modal < floor(commodity)` | Per-commodity floor table (hard-coded minimums: e.g., Onion ≥ ₹200/qtl, Tomato ≥ ₹100/qtl, spices ≥ ₹500/qtl) |
| Drop if `price_modal > ceiling(commodity)` | Per-commodity ceiling or 99.5th-pctile winsorise |
| Weekly point requires `n_markets >= 3` | Fewer than 3 markets → NULL for that (commodity, week) cell |
| Tier A composite requires `n_markets >= 50` for that ISO-week | Below 50 → commodity excluded from composite for that week (flagged) |

### Median choice

The weekly **median** of per-mandi modal prices is chosen over the mean
specifically because of the known garbage values. The median is robust to
the ₹0.66 outliers without requiring a hand-tuned clipping step per commodity.
Winsorisation provides a secondary backstop for high outliers before the median
is computed.

---

## 11. Arrivals (deferred v2)

Price alone conflates supply shocks from demand pulses. The diagnostic requires
the arrivals dimension:

| Price signal | Arrivals signal | Interpretation |
|---|---|---|
| Price rising | Arrivals falling | Supply shock — persistent; intervention-worthy |
| Price rising | Arrivals flat/rising | Demand pulse or front-loading — transient |
| Price falling | Arrivals rising | Harvest flush — seasonal |
| Price falling | Arrivals falling | Demand collapse (unusual for perishables) |

The OGD Agmarknet resource (`35985678-0d79-46b4-9ed6-6f13308a1d24`) carries
prices only. Arrivals (in quintals) are separately available via the
**UPAg "Mandi Arrival Quantity" Dash path**, which has not yet been built.

The `econ.fact_india_mandi` schema already has an `arrivals_tonnes` column
(NULL until the UPAg path lands). The arrivals diagnostic is a v2 feature;
v1 outputs flag "prices only — no arrivals confirmation" on any persistent-shock
alert.

---

## 12. Validation

### Planned backtest

Once the 5-year backfill is complete (§8), backtest the composite perishables
MoM nowcast against:

1. **MoSPI CPI — Food & Beverages sub-index** (`INDIA.CPI.FOOD_BEV.*` in
   `econ.fact_indicator`, loaded via `mospi_cpi.py`). This is the closest
   available series to the perishables composite.
2. **DPIIT WPI — Food Articles sub-index** (`INDIA.WPI.FOOD_ARTICLES.*` in
   `econ.fact_indicator`). WPI food articles is more vegetable-heavy and closer
   in spirit to the FOCUS set; WPI is published earlier than CPI.

**Caveats:**
- The IMDR DB does not currently hold the CPI **vegetable sub-index** or the
  CPI **fruit sub-index** as separate stored indicators; validation is therefore
  at the food-group level (Food & Beverages composite), not at the
  vegetables-specific level. If the vegetable sub-index is added later
  (it is available in MOSPI XLSX releases), the validation should be re-run.
- Mandi-to-retail wedge varies by season and by commodity. The nowcast
  measures wholesale; the CPI measures retail. The relationship is directionally
  reliable but not mechanically tight.
- The lead time (1–3 weeks) means the optimal use is directional CPI
  surprise-direction forecasting, not point estimates.

### Metric

Primary validation metric: **directional accuracy** (correct sign on MoM
surprise) + **correlation** of the composite vs the Food & Beverages sub-index
MoM. Secondary: RMSE relative to a naïve seasonal model.

---

## 13. Storage and indicator scheme

### Target: `econ.fact_indicator`

The **nowcast aggregates** (weekly medians, momentum, vs-seasonal-norm, and the
composite MoM nowcast) are **small** — roughly 2,000–5,000 imdr_code rows
covering the FOCUS commodity set across national + key states. These land in
`econ.fact_indicator` alongside CPI/WPI, using the standard indicator scheme.

### Proposed `imdr_code` stem convention

| Signal | imdr_code pattern | Example |
|---|---|---|
| Weekly national median | `INDIA.FOODNOWCAST.{subgroup}.{commodity_slug}.MEDIAN_WK.NATL.IN` | `INDIA.FOODNOWCAST.VEG.TOMATO.MEDIAN_WK.NATL.IN` |
| Weekly state median | `INDIA.FOODNOWCAST.{subgroup}.{commodity_slug}.MEDIAN_WK.{STATE}.IN` | `INDIA.FOODNOWCAST.VEG.TOMATO.MEDIAN_WK.MH.IN` |
| MoM % change | `INDIA.FOODNOWCAST.{subgroup}.{commodity_slug}.MOM_PCT.NATL.IN` | `INDIA.FOODNOWCAST.VEG.TOMATO.MOM_PCT.NATL.IN` |
| WoW % change | `INDIA.FOODNOWCAST.{subgroup}.{commodity_slug}.WOW_PCT.NATL.IN` | `INDIA.FOODNOWCAST.SPICE.GREENCHILLI.WOW_PCT.NATL.IN` |
| YoY % change | `INDIA.FOODNOWCAST.{subgroup}.{commodity_slug}.YOY_PCT.NATL.IN` | `INDIA.FOODNOWCAST.FRUIT.MANGO.YOY_PCT.NATL.IN` |
| vs 5-yr seasonal norm | `INDIA.FOODNOWCAST.{subgroup}.{commodity_slug}.VS_SEASNORM.NATL.IN` | `INDIA.FOODNOWCAST.VEG.ONION.VS_SEASNORM.NATL.IN` |
| Composite MoM nowcast | `INDIA.FOODNOWCAST.PERISHABLE.MOM_NOWCAST.IN` | — |
| Composite vs seasonal | `INDIA.FOODNOWCAST.PERISHABLE.VS_SEASNORM.IN` | — |
| n_markets (confidence) | `INDIA.FOODNOWCAST.{subgroup}.{commodity_slug}.N_MARKETS.NATL.IN` | stored as supporting indicator |

`{commodity_slug}` is an uppercase ASCII slug derived from the canonical
Agmarknet name (e.g., `BHINDI_LADIES_FINGER`, `BITTER_GOURD`,
`CORIANDER_LEAVES`). The mapping is defined in the aggregation code.

### Note on migration 104 and the raw star schema

**Migration 104** (`migrations/104_india_mandi_prices.sql`) created
`econ.fact_india_mandi` (raw per-mandi daily prices) + two dims. This schema
is **being parked as the storage target for the nowcast**; its ~18,000 test
rows are to be `DELETE`d from the fact table once the migration-104 gate
decision is finalised. The nowcast aggregates go to `econ.fact_indicator`
instead, keeping the macro table as the single query surface.

The no-DDL-drop rule (`Base.metadata.drop_all()` forbidden) means the empty
tables will remain in the DB unless a DBA-run drop migration is explicitly
commissioned later. This is acceptable — empty tables carry no operational risk.

The raw granular pipeline (OGD daily fetch → `econ.fact_india_mandi`) is
**not** required for the nowcast to function. The nowcast fetcher will
commodity-filter the OGD API directly (§5) and compute aggregates in memory
before landing them in `econ.fact_indicator`. The star schema is a potential
future analytical layer (ad-hoc per-mandi queries, arrivals integration) but
is not on the critical path for P1–P3.

---

## 14. Outputs

### Stored indicator set (primary)
All metrics from §6 and §7 landed in `econ.fact_indicator`. Queryable alongside
CPI/WPI via the standard indicator API.

### Weekly "Fresh-Food Pulse" brief (Lois / Atlas territory)
A weekly brief covering:
- **Top movers:** the 5 commodities with the largest WoW % change (positive and
  negative).
- **The MoM number:** the composite perishables MoM nowcast with its `(MTD,
  N/30 days)` confidence label.
- **Regional hotspots:** by-state median flags for TOP and other Tier A
  commodities where a deficit zone is diverging from the national median.
- **Above-seasonal flags:** commodities where `vs_seasonal_norm_pct > +20%`
  (configurable threshold).
- **Arrivals caveat:** present until the UPAg v2 path is live.

Format: consistent with the Lois/Atlas brief design system (see
`docs/admin/research/weekly_brief_spec.md`).

### Threshold alerts
Configurable alert triggers stored alongside the indicator series:
- Composite MoM nowcast exceeds +1.5% or drops below −1.5% MTD (CPI
  surprise territory).
- Any TOP commodity `vs_seasonal_norm_pct > +40%` (sustained-shock threshold).
- Any Tier A commodity with `n_markets < 30` for two consecutive weeks (data
  quality degradation).

---

## 15. Phased build plan

| Phase | Deliverables | Gates / dependencies |
|---|---|---|
| **P1 — Weekly fetch + medians** | Commodity-filtered OGD daily fetch (FOCUS set only); weekly aggregation to national median + WoW/MoM/YoY; load into `econ.fact_indicator`; wire into `in_daily.py` (gated on user OK). | Migration 104 applied (or fetch runs without star schema — aggregates only); `india_food_basket.py` config (done). |
| **P2 — 5-year backfill + seasonal norms** | Targeted backfill 2021 → today for FOCUS commodities; compute `seasonal_norm(commodity, ISO_week)`; compute `vs_seasonal_norm_pct`; store alongside weekly medians. | P1 complete; confirm backfill cost (expected: ~8M FOCUS rows / 5 years). |
| **P3 — CPI-weighted composite MoM nowcast** | `INDIA.FOODNOWCAST.PERISHABLE.MOM_NOWCAST.IN` composite series with MTD confidence label; backtest vs FOOD_BEV and WPI Food Articles (§12); document lead-time findings. | P2 complete (needs seasonal norms for credible nowcast); FOOD_BEV sub-index in DB (already live via `mospi_cpi.py`). |
| **P4 — Regional layer + brief + alerts** | By-state weekly medians for the 6 deficit zones (§9); Fresh-Food Pulse brief template (Lois integration); threshold alert wiring. | P3 complete; confirm state-code mapping from Agmarknet state names to `dbo.dim_country` or a new state-dim table. |
| **P5 — Arrivals via UPAg** | Build UPAg "Mandi Arrival Quantity" Dash path; populate `arrivals_tonnes` in `econ.fact_india_mandi` (or a parallel `fact_india_mandi_arrivals` table); add price×arrivals composite signal; update brief to show arrivals diagnostics. | P4 complete; UPAg arrivals path discovery (not yet probed). |

---

## Related

- [`india_mandi_prices.md`](../econ/india/india_mandi_prices.md) — OGD
  Agmarknet data-source pipeline (schema, fetcher, gated next steps). The
  upstream source for this nowcast.
- [`../econ/india/index.md`](../econ/india/index.md) — India econ index
  (prod-live indicator inventory, cadence map).
- [`../econ/india/in_coverage_plan.md`](../econ/india/in_coverage_plan.md) —
  Cluster 4 agriculture section (mandi / food price cells).
- `src/imdr/domains/econ/india_food_basket.py` — commodity basket config
  (FOCUS / EXCLUDE / STRIP lists; `CPI_SUBGROUP_WEIGHT_PCT`; tier definitions).
- `tests/unit/test_econ/test_india_food_basket.py` — 9 unit tests covering
  basket integrity.
- [`weekly_brief_spec.md`](weekly_brief_spec.md) — Lois/Atlas brief design
  system (output format for the Fresh-Food Pulse brief in §14).
- [`../econ/macro_economy_wiring_map.md`](../econ/macro_economy_wiring_map.md)
  — §7.12 India, Cluster 4 / Input Costs cell.
