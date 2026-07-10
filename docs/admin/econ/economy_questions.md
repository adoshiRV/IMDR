# Economy Questions — the country-decomposition framework

**How an economy thinks, turned into a standing set of questions.** This is the
*analytical* layer that sits on top of the three structural layers we already
have. Those say where the data lives, how a surprise scores, and what to track.
None of them ask the reasoning questions — *why is the economy here, what moves
it, by how much, what has it done before, and what's priced* — which is what a
rates / macro / FX PM actually needs to decompose a country. This doc is that set.

| Layer | Doc | What it answers |
|---|---|---|
| **Wiring map** | [`macro_economy_wiring_map.md`](macro_economy_wiring_map.md) | *Where the data lives* — 4 loops × 4 clusters = 16 cells; the coverage target. |
| **8-driver taxonomy** | [`macro_driver_taxonomy.md`](macro_driver_taxonomy.md) | *How a surprise scores* — the signed impulse engine. |
| **Cluster map** | [`../research/cluster_map_spec.md`](../research/cluster_map_spec.md) | *What to track + where to get it* — 12 standing clusters per country. |
| **Economy questions** *(this doc)* | — | *Why / how much / what before / what's priced* — the reasoning + decomposition + sensitivity + history + vol layer. |

- **Status:** active spec — the country-generic question framework. Country
  instantiation (filling the overlay in §6 per country) is a follow-on step.
- **Relationship to the others:** this is a *consumer* of the same infrastructure,
  not a replacement. **Q1 (decompose) ≈ the cluster map; Q5 (surprise/vol) ≈ the
  8-driver engine + `cb_events` + `rates.fact_observation`; Q6 (reaction/pricing)
  ≈ the rates playbook.** The framework names the questions; the existing engines
  supply the grounding.
- **Date:** 2026-06-26.

---

## 1 · The model — three axes

An economy is decomposed by crossing two generic axes, then applying a
country-specific overlay. The **standing question set is the cross-product**.

- **Axis 1 — Domains (the *what*).** Eight structural domains, anchored to the
  wiring-map loops so every question resolves to data we already chase (§2).
- **Axis 2 — Archetypes (the *how you interrogate*).** Six reasoning shapes —
  the part that's genuinely new here. Each domain is read through all six (§3).
- **Axis 3 — Country overlay.** Per country: which domains *dominate*, which
  *"may not matter,"* and the country-specific questions that don't generalise
  (India rural/urban; Japan "does the print even move JGBs"; AU housing; NZ
  dairy; KR services + semis). The overlay re-weights and extends the set (§6).

> **The point of the archetypes.** A cluster map says *"track CPI."* The 8-driver
> engine says *"this CPI print scored +0.4."* Neither asks *"what share of CPI is
> non-tradable, why is that the bit deviating from target, how many bp does a 15%
> FX move add and over what lag, when was services inflation last this high and
> what broke it, and is any of that priced?"* The archetypes are exactly those
> missing reasoning shapes.

---

## 2 · Axis 1 — the eight domains

Anchored to the wiring map's four loops (Growth → Inflation → External/FX →
Policy), split to the granularity a PM decomposes a country at:

| # | Domain | Wiring-map loop | What it covers |
|---|---|---|---|
| **D1** | **Inflation** | Inflation | Tradable vs non-tradable · core vs non-core · food · energy · rents · services · wages · FX pass-through · expectations |
| **D2** | **Growth & output** | Growth | GDP by expenditure *and* by supply sector (each weighted) · the swing sector · potential GDP / output gap |
| **D3** | **Labour** | Growth | Slack · hiring vs firing flows · participation · hours · wage-setting · NAIRU |
| **D4** | **Housing & credit** | Policy (credit) | Price · activity · mortgage credit (fixed/floating mix) · household balance sheet · wealth effect |
| **D5** | **External & FX** | External/FX | Terms of trade · current account · funding need & quality (sticky vs hot) · FX level & sensitivity · reserves/intervention |
| **D6** | **Fiscal** | Policy | Stance/impulse (need) · deficit cyclical vs structural · financing & issuance (funding) · debt sustainability |
| **D7** | **CB reaction function** | Policy | Mandate weights · the binding variable this cycle · step size & communication · what's priced vs implied |
| **D8** | **Global transmission** | (cross) | Exposure to US rates/DXY · China demand · commodities · global tech/semis · risk sentiment — and *how each percolates in* |

These eight are the **fixed spine**, deliberately parallel to the wiring map and
the 8-driver set so the three layers speak the same language. D7 and D8 are
broken out as their own domains here (vs folded into "Policy/Fiscal" and treated
as cross-cutting in the driver taxonomy) because the *reasoning* questions about
the reaction function and global percolation are first-class for a PM — they're
where most of the trade lives.

---

## 3 · Axis 2 — the six question archetypes

Each domain is read through all six. This is the reusable interrogation grammar.

| # | Archetype | The question shape | Maps to |
|---|---|---|---|
| **Q1** | **Decompose** | What are the parts, and their *weights*? Which part carries the most weight, which the most variance? | Cluster map (what to track) |
| **Q2** | **Driver & reasoning** | *Why* is each part where it is — the causal mechanism — and which part is driving the current deviation? | Mycroft / Atlas read |
| **Q3** | **Sensitivity / elasticity** | A move in a *named* shock changes this by how much, over what lag? (the elasticities) | Scenario / playbook |
| **Q4** | **History / regime** | How has it behaved across past cycles? When did this driver matter, when was it ignored — and *why*? | Historical analysis |
| **Q5** | **Surprise & volatility** | Which release moves rates most? Conditional rates vol on a surprise of *x*? What's the leading indicator of a vol-regime change? | 8-driver engine + `cb_events` + `rates.fact_observation` |
| **Q6** | **Reaction & pricing** | Given all the above, what does the policymaker do — and how does that differ from what's *priced*? | Rates playbook |

The archetypes escalate: **Q1–Q2 establish structure, Q3–Q4 establish behaviour,
Q5–Q6 establish the trade.** A country read that stops at Q2 is a description; the
value for a rates/FX desk is in Q3–Q6.

---

## 4 · The standing question set (domain × archetype)

The cross-product, instantiated country-generic. Bracketed `[…]` notes are
illustrative country anchors, not part of the generic question. Each is phrased
to be answerable from `econ.fact_indicator` + `cb_events` + `rates.fact_observation`
+ the research corpus.

### D1 · Inflation

- **Q1 Decompose** — What are CPI's shares by **tradable vs non-tradable**, **core
  vs non-core**, and the big sub-baskets (food, energy, housing/rents, services)
  *by basket weight*? Which buckets carry the most weight, and which the most
  month-to-month variance?
- **Q2 Driver** — Which bucket is driving the current deviation from target, and is
  the impulse **domestically generated** (services, wages, rents, capacity) or
  **imported** (food, energy, FX pass-through)? Is it broad (breadth/persistence)
  or narrow? [KR: services inflation running hot — non-tradable, domestic.]
- **Q3 Sensitivity** — For each external shock, the **pass-through elasticity and
  lag**: oil ±$10/bbl → headline & core bp? FX ±10–15% → tradable-CPI bp over how
  many months? An agri/food shock → headline bp? [AU/NZ: oil import sensitivity;
  KR: a 15% FX move → tradable inflation.]
- **Q4 History** — When was **non-tradable (services) inflation** last this high or
  low, and what broke the trend? Has the tradable/non-tradable mix shifted regime
  (e.g. post-COVID services stickiness)?
- **Q5 Surprise/vol** — Which inflation release (headline vs core vs trimmed-mean vs
  a sub-component) has historically moved the **front end** most, and is that still
  the market's focus?
- **Q6 Reaction/pricing** — Do realised + expected inflation sit inside the CB's
  tolerance? What CPI path is priced vs what the reaction function implies?

### D2 · Growth & output

- **Q1 Decompose** — GDP by **expenditure** (C / I / G / NX + inventories) and by
  **supply sector**, each *with its weight*. Which single sector is the **swing
  factor** (largest weight × volatility)?
- **Q2 Driver** — What's driving the current pulse — private demand, fiscal,
  external, or the inventory cycle? Is it **income-led or credit-led**?
- **Q3 Sensitivity** — If the swing sector contracts X%, what's the GDP hit (direct
  + multiplier)? [AU: housing −X% → large GDP drag.] What's growth's sensitivity to
  the key external channel (China demand, global tech cycle, terms of trade)?
- **Q4 History** — What is **potential GDP / trend**, and is the economy above or
  below (the output gap)? How has the gap behaved into past turning points?
- **Q5 Surprise/vol** — Which activity release (GDP, IP, retail, PMI, the nowcast)
  is the highest-frequency, most market-moving read of the pulse? When did a
  previously-ignored series start mattering?
- **Q6 Reaction/pricing** — Does the growth pulse argue for the CB to lean against
  or with current pricing? What growth path is the curve implying?

### D3 · Labour

- **Q1 Decompose** — Employment by sector, participation, hours, and the
  **unemployment vs underemployment** gap. What share of slack is cyclical vs
  structural?
- **Q2 Driver** — Is the market loosening via **firing** (layoffs / claims rising)
  or just **less hiring** (vacancies / hires falling) — and which matters more for
  wages here? [the hiring-vs-firing distinction.]
- **Q3 Sensitivity** — What unemployment rate corresponds to the CB's
  full-employment / NAIRU estimate? How sensitive are wages to a 1pp move in the
  unemployment gap (the Phillips slope)?
- **Q4 History** — Where is unemployment vs past cycle troughs/peaks? Has the
  wage–unemployment relationship shifted regime?
- **Q5 Surprise/vol** — Which labour release moves rates most — payrolls vs
  unemployment vs wages vs vacancies? [US: NFP.] What's the **conditional rates
  move** on a 1σ labour surprise (see §5)?
- **Q6 Reaction/pricing** — Is the labour market consistent with the
  full-employment leg of the mandate, and what's priced off the next print?

### D4 · Housing & credit

- **Q1 Decompose** — Housing **price** (which index), **activity** (starts /
  approvals / sales), **credit** (mortgage growth, investor vs owner-occupier),
  and the **household balance sheet** (debt/income, debt-service ratio). What is
  housing's GDP weight (construction + ownership transfer + renovation)?
- **Q2 Driver** — Is housing demand **income-led or rate/credit-led**? How
  **fixed-vs-floating** is the mortgage stock — i.e. how fast does policy
  transmit?
- **Q3 Sensitivity** — How sensitive is housing to a **100bp policy move** (price,
  activity, credit)? What's the **wealth-effect pass-through** to consumption?
  [AU: the housing → consumption channel.]
- **Q4 History** — Where are prices/credit vs past cycles? Is there a **refinancing
  wall or a fixed-rate reset cliff** ahead?
- **Q5 Surprise/vol** — Which housing/credit release is the market's leading read on
  the policy-transmission channel?
- **Q6 Reaction/pricing** — Is the household balance sheet a **binding constraint**
  on how far the CB can hike (the financial-stability leg)?

### D5 · External & FX

- **Q1 Decompose** — The BoP: current account (trade, services, income,
  transfers/remittances), capital account (FDI vs portfolio vs bank), reserves.
  What is the external **funding need**?
- **Q2 Driver** — Is funding **sticky** (FDI, CA surplus) or **hot** (portfolio,
  short-term debt) — how reversible? What drives the **terms of trade** (which
  export commodity / sector)?
- **Q3 Sensitivity** — Terms-of-trade sensitivity to the key commodity (±$X →
  national income / fiscal). **FX sensitivity**: what global move (US rates,
  risk-off, commodity) drives the currency, and what's the beta? Then FX
  pass-through back into D1.
- **Q4 History** — Where is the CA / REER vs history? Has the funding mix shifted
  regime? What's the intervention track record?
- **Q5 Surprise/vol** — Which external release (trade balance, reserves, CA) is
  market-moving? For EM, what's the FX / NDF vol around it?
- **Q6 Reaction/pricing** — Does the external position constrain the CB (the FX /
  reserves leg)? Is intervention or a FX-defensive hike on the table?

### D6 · Fiscal

- **Q1 Decompose** — The fiscal stance: deficit/GDP, primary balance, the
  spending-vs-revenue split, the **cyclical vs structural** component. What is the
  gross **financing need (issuance)**?
- **Q2 Driver** — Is fiscal **adding or subtracting** from demand (the impulse)? Is
  the funding need rising for cyclical or **structural** reasons (demographics,
  debt service)? [the "need" half.]
- **Q3 Sensitivity** — How sensitive is the deficit to growth / rates
  (auto-stabilisers + debt-service)? How much **net issuance** hits the curve, at
  what tenor? [the "funding" half.]
- **Q4 History** — Where are debt/GDP and the deficit vs history? Is there a
  debt-service or **rollover wall**? Fiscal-dominance risk?
- **Q5 Surprise/vol** — Which fiscal event (budget, issuance calendar, funding
  update) moves the curve — especially the **long end / term premium**?
- **Q6 Reaction/pricing** — Is fiscal working **with or against** the CB? What
  supply is priced into the term premium vs the funding path?

### D7 · CB reaction function

- **Q1 Decompose** — The mandate: what does this CB actually weight — inflation,
  growth/employment, FX, financial stability — and **in what order**? Single vs
  dual mandate; explicit target?
- **Q2 Driver** — What is the CB *currently* reacting to (the **binding variable**
  this cycle)? Is the focus **common across CBs** (global disinflation) or
  **country-specific** (FX defence, housing)? [CB focus — across all or
  country-specific.]
- **Q3 Sensitivity** — For a 1pp inflation or growth surprise, what's the implied
  change in the **rate path** (the reaction-function slope)?
- **Q4 History** — How has this CB behaved at past turning points (lead/lag vs
  data, step size, communication style)? Credibility / forward-guidance track
  record.
- **Q5 Surprise/vol** — Which CB communication (decision, minutes, speeches,
  projections) moves the front end most? How is **meeting-day vol** distributed?
- **Q6 Reaction/pricing** — What's **priced** (OIS path, terminal rate, cut/hike
  timing) vs what the reaction function + data imply? *This is the core trade
  question.*

### D8 · Global transmission

- **Q1 Decompose** — Map exposure to each global factor: **US rates / DXY**,
  **China demand**, **global commodity** (oil, metals, food), **global tech/semis
  cycle**, **global risk sentiment**. Which dominates?
- **Q2 Driver** — Through **which domain** does each global move percolate first
  (oil → D1 + D5; China → D2 + D5; US rates → D7 + the curve directly)? [JP: does a
  domestic print even move JGBs, or is it all BoJ / global — *how does it
  percolate*?]
- **Q3 Sensitivity** — **Betas**: rates/FX sensitivity to a 25bp Fed move, a $10 oil
  move, a China-growth surprise, a global risk-off. Which is the dominant *external*
  driver of local rates?
- **Q4 History** — Has the country's global beta shifted regime (decoupling, a
  de-peg, a supply-chain shift)?
- **Q5 Surprise/vol** — Which **global** release/event drives local rates vol more
  than any domestic print? (For some countries the most vol-inducing series is
  foreign.)
- **Q6 Reaction/pricing** — How much of local pricing is the domestic reaction
  function vs **imported** from global curves — and where's the dislocation?

---

## 5 · The quantitative layer (Q5) — surprise & volatility

Q5 is the one archetype that is *computed*, not narrated, and it's the heart of
the user's vol questions. It is a natural extension of the 8-driver engine —
**not yet built**; this is the analysis spec.

All inputs already exist (per the [driver taxonomy §5](macro_driver_taxonomy.md)):
realised **actual** ⟵ `econ.fact_indicator`, **consensus** ⟵ `calendar.cb_events`,
and the **curve** (spot + forwards by tenor) ⟵ `rates.fact_observation`.

1. **Surprise** — `surprise = actual − consensus`, standardised by the rolling σ
   of that release's own surprises (the [taxonomy's scale-calibration target](macro_driver_taxonomy.md#scale-calibration--the-highest-leverage-least-settled-choice)).
2. **Realised surprise vol (last 3 months / 1–3y)** — the dispersion of recent
   surprises per release; "how noisy has this print been lately vs its own history."
3. **Conditional rates move** — regress `Δ(1y / 2y / 3y OIS)` on the standardised
   surprise, per release type per country → *"a 1σ NFP surprise moves the 2y by
   X bp."* This is the user's "vol in 1y/2y/3y when surprise is x% of NFP."
4. **Most vol-inducing release** — rank releases by `|Δrate|` (or event-day rate
   vol) attributable to them; *which data has historically been most vol-inducing.*
5. **Vol-regime leading indicator** — track each release's **rolling beta to
   rates**; flag a series whose market-sensitivity is *rising* (a print the market
   used to ignore that's starting to matter). This is the user's "find the key
   driver / leading indicator of a vol change — and why a series that wasn't
   important before now is."

> Same caveats as the driver engine: a thin `cb_events` window can carry the wrong
> *sign*, not just magnitude, and `cb_events.actual` is low-trust — use
> `econ.fact_indicator` for actuals. Tier honestly when coverage is thin.

---

## 6 · Axis 3 — the country overlay

The standing set is generic; the overlay makes it a *country* read. For each
country, record three things:

1. **Domain weights** — tag each domain `Dominant` / `Standard` / `Low` / `N/A`.
   This is where **"may not matter"** is captured explicitly — the user's Japan
   note is a `Low` tag on several domestic domains, not their omission.
2. **Country-specific questions** — the questions that don't generalise, bolted
   onto the relevant domain.
3. **The data anchor** — the country's series for each (from its indicator
   inventory + wiring-map row).

Illustrative overlays (to be filled out per country in a follow-on):

| Country | Dominant domains | Country-specific questions | "May not matter" |
|---|---|---|---|
| **IN** | D1, D2 | **Rural vs urban** split runs through D1 (rural/urban CPI), D2 (rural vs urban consumption), D3 (rural wages / MGNREGA); **monsoon → food → D1**. | — |
| **JP** | D7, D8 | How does a domestic print **percolate** to JGBs under a CB-anchored curve? **Wages / Shunto** as the binding D1 test. | Several domestic D1–D4 prints (lead with D8-Q2). |
| **AU** | D4, D5, D8 | **Housing → GDP/consumption** (D4-Q3); **terms of trade / iron ore** (D5); **oil import** pass-through (D1-Q3); **China beta** (D8). | — |
| **NZ** | D5, D8 | **Dairy / GDT** as the rural-income pulse (D5); **oil import** sensitivity (D1-Q3); small-open-economy global beta (D8). | — |
| **KR** | D1, D4, D8 | **Wealth-effect flywheel** (wages → consumption → housing wealth → investment → policy; D4-Q3 + D2/D3/D6); **services (non-tradable) inflation** (D1); **15% FX → tradable** pass-through (D1-Q3); **semiconductor export/capex cycle** (D2/D8). | — |
| **TW** | D8, D2 | **Semiconductor cycle** dominates the whole economy; headline GDP is AI-distorted so the domestic economy reads weaker than aggregates. | Headline GDP as a domestic-demand read. |
| **US** | D7, D1, D3 | **Core PCE** level + trend (D1); what's **surprised** in the last 3–6m and its effect on **1y Fed pricing** (D7-Q6 + Q5); where **growth momentum** is building (D2). | External funding constraint (reserve-currency issuer — D5 least binding). |

The overlay is a **judgment call from the country's structure** — the same call
Mercator makes when it rotates a country-specific cluster to the front. The
generic set + the overlay together are the country's full read.

### 6.1 · India — tracked country-specific questions

The running list of India-specific questions to carry into India's Country Economy
Profile (Smith). Each maps to a domain × archetype; the data-status flag says what's
answerable from IMDR today. This is the template for accumulating country-specific
questions — other countries get their own §6.x as questions surface.

| Question | Domain · archetype | Data in IMDR |
|---|---|---|
| **Credit-growth deep-dive** — which *sectors* are driving bank-credit growth (agri / industry / services / personal), and are the growing sectors the **productive** ones that lead the activity cycle at a lag (capex, industry, infra) or just **personal-consumption** credit? At what lag does sectoral credit lead the growth pulse? | **D4** Q1 Decompose + Q2 Driver + Q4 History | ⚠️ **Gap** — needs RBI DBIE *Sectoral Deployment of Bank Credit* (the A7 path); this is India's ❌ cell **4.1 Demand Transmission**, not yet onboarded. Aggregate credit + BIS credit-to-GDP present; sectoral split is the missing leg. |
| **Rural vs urban consumption (last 6m)** — how is **rural** consumption growing over the last 6 months, and how does it **contrast with urban**? | **D2** Q1 Decompose + Q2 Driver (the IN rural/urban overlay) | ⚠️ Partial — MOSPI PFCE is aggregate; rural/urban split needs proxies (rural: two-wheeler/tractor sales, FMCG rural volumes, MGNREGA demand, rural wages; urban: PV sales, urban FMCG, card spend). |
| **FCNR(B) flows** — size + direction of NRI deposit flows (FCNR(B) / NRE / NRO); sticky vs hot, and the FX-sensitivity of the flows as an external-funding read. | **D5** Q1 Decompose + Q2 Driver | ✅ RBI Bulletin **T34 NRI Deposits** (FCNRB / NRERA / NRO) loaded. |

### 6.2 · United States — tracked country-specific questions

US dominant domains are **D7 (Fed reaction function), D1 (inflation), D3 (labour)** —
the read is reaction-function-led and the trade lives in what's priced vs implied.
Living list — refined as US reports land.

| Question | Domain · archetype | Data in IMDR |
|---|---|---|
| **Where is core PCE** now (level), and where does it sit vs the 2% target? | **D1** Q1 Decompose | ✅ BEA **core PCE** price index (ex food & energy), monthly (cell 2.4). |
| **What trend** in core PCE — 3m / 6m annualised, and direction (re-accelerating or cooling)? | **D1** Q2 Driver + Q4 History | ✅ same series; derive 3m / 6m annualised + sequential. |
| **What has surprised** up / down in the last 3–6m, across the key releases (PCE, CPI, NFP, retail, ISM)? | **D1–D3** Q5 Surprise | ✅ surprise = `econ.fact_indicator` actual − `cb_events` consensus; sign + magnitude per release. |
| **Where is momentum building** — which domain's pulse is accelerating (inflation, labour, activity)? | **D2 / D1** Q2 Driver + Q4 History | ✅ activity / labour / inflation series; momentum from sequential history. |
| **Effect on 1y Fed pricing** of those surprises — how much has the 1y path repriced per unit of surprise? | **D7** Q6 Reaction/pricing + Q5 | ⚠️ 1y Fed pricing in `rates.fact_observation`; the *conditional repricing* computation is the §5 vol layer — **not built**; answer qualitatively + flag until built. |

### 6.3 · South Korea — tracked country-specific questions

Sourced from the research desk's **wealth-effect flywheel** thesis (Korea digest).
The reads below are the *current annotation* — **verify vs `econ.fact_indicator` /
REB when Smith answers**; the flywheel is a thesis to test, not an asserted fact.
Dominant domains **D1, D4, D8**; the country-specific thesis is that a
self-reinforcing wealth machine is switching on. Living list.

| Question | Domain · archetype | Data in IMDR |
|---|---|---|
| **Is the wealth-effect flywheel compounding?** — the self-reinforcing loop wages → consumption → housing wealth → investment → pro-market policy. | Cross-domain (**D4** Q3 anchor + D2/D3/D6) | ✅ the pillar components below; the *loop* is a synthesis read. |
| **Housing wealth → consumption** — Seoul home prices strong (thesis: +9.6% y/y, Apr-2026); how much of the consumption pickup is the **wealth effect** vs income / stimulus? | **D4** Q3 Sensitivity (wealth-effect pass-through) + Q1/Q2 | ✅ REB housing (R-ONE) prices; BOK household income; KOSTAT retail / private consumption. |
| **Labour tightness → domestic demand** — unemployment low (thesis: ~2.6%), real wages turning positive, employment +YoY; is tight labour feeding **domestic-services** demand? | **D3** Q1 Decompose + Q2 Driver | ✅ KOSTAT EAPS unemployment / employment + Wages. |
| **Investment / capex revival** — facility investment strong (thesis: +6.6% q/q, strongest in 4y); is the **semi super-cycle** driving a broader capex cycle? | **D2** Q1/Q2 + **D8** (semis) | ✅ BOK GDP facility-investment component; ties to the existing semi-export overlay. |
| **Pro-market policy / tax architecture** — separate dividend tax (14/20/25/30%, passed Dec-2025), supplementary budgets, US tariff cap ~15%; structural tilt supporting asset prices + the BoK 2026 GDP upgrade (thesis: 2.6%). | **D6** Fiscal (stance / structural) + **D7** (BoK forecast) | ⚠️ Fiscal series (BOK Public Sector) present; the tax-reform + tariff facts are **corpus / news**, not a data series. |

> Living list — refined as KR reports land. Each pillar's read must reconcile to
> first-party data before it graduates from thesis to fact.

---

## 7 · How this consumes existing infrastructure

This framework adds **no new data pipeline**. It re-reads what's built:

| Archetype | Consumes | Notes |
|---|---|---|
| Q1 Decompose | `econ.fact_indicator` (weights/shares) + the cluster map | The decomposition *is* the cluster map's "what to track," read for weights. |
| Q2 Driver | research corpus (Qdrant) + Atlas/Mycroft reads | The narrative "why," grounded in ingested research + official releases. |
| Q3 Sensitivity | `econ.fact_indicator` history + scenario logic | Elasticities estimated from history; some are desk priors, flag which. |
| Q4 History | `econ.fact_indicator` long history | Cross-cycle behaviour; deep-history countries (AU, NZ, KR) support this best. |
| Q5 Surprise/vol | `cb_events` + `econ.fact_indicator` + `rates.fact_observation` | The 8-driver engine extended to conditional rates vol (§5). |
| Q6 Reaction/pricing | `rates.fact_observation` (OIS path) + `cb_events` + corpus | The rates-playbook composite; what's priced vs implied. |

---

## 8 · The deliverable — the Country Economy Profile (Smith)

The agent that answers this framework per country is **Smith** (the country
economist), at [`.claude/agents/smith.md`](../../../.claude/agents/smith.md).
Smith is the *answering* sibling to Mercator: **Mercator draws the map (what to
track); Smith fills it in (the answers).** Smith decomposes, estimates, and states
what's priced — Mercator never does. Smith writes grounded MD; rendering is
deferred (Picasso later).

**Deliverable:** the **Country Economy Profile** — a standing, durable per-country
decomposition. Refreshed on a structural / regime shift, not weekly.

**Format (first pass): plain structured markdown, no render.** Sections, in order:

1. **Front matter** — country · iso · regime tagline · as_of · status.
2. **Country overlay** (§6) — the domain-weight table (`Dominant`/`Standard`/
   `Low`/`N/A`, the "may-not-matter" tags) + the country-specific questions.
3. **The 8 domains**, each answered through **Q1–Q6** (§4), grounded. `Dominant`
   domains get the full six; `Low`/`N/A` domains get a short why-it-doesn't-matter
   note (the tag is a finding, not an omission).
4. **What's priced vs implied** — the six Q6 answers pulled into one short read.
   The closest the profile comes to a view; grounded, not a trade call.
5. **Sources appendix** — every number + desk attribution traced (DB query ·
   research `[vendor, report_id, chunk_idx]` · web URL + timestamp).

**Path:** `data/economy_profiles/{cc}/{cc}-economy-profile-{YYYY-MM}.md`
(`{cc}` = lower-case ISO). **Accumulate versions** — each refresh is a new
`{YYYY-MM}` file; never overwrite. Convenience latest at `{cc}-latest.md`.

**Pre-ship checklist:**
- [ ] Front matter complete (country, iso, regime, as_of, status).
- [ ] Country overlay set — every domain tagged; country-specific Qs listed.
- [ ] All 8 domains present; `Dominant` ones answer Q1–Q6; `Low`/`N/A` carry a one-liner.
- [ ] Every number cited (DB / curve / cb_events / corpus); actuals from `econ.fact_indicator`.
- [ ] Q5 conditional-vol items the engine can't yet compute are *flagged*, not faked.
- [ ] Desk attributions trace to real cited reports (or removed).
- [ ] "What's priced vs implied" is grounded; no sizing/conviction.
- [ ] Path correct; prior `{YYYY-MM}` version not overwritten.

## 9 · Hard rules

1. **Framework, not a signal.** Like the cluster map, this is a structured way to
   *read* a country, not a directional call. Conviction is Atlas's / Mycroft's job.
2. **Country-generic spine, country overlay.** The eight domains × six archetypes
   are fixed; per-country relevance and country-specific questions live in the §6
   overlay. Don't fork the spine per country — re-weight it.
3. **"May not matter" is recorded, not omitted.** A `Low` domain weight is a real
   finding (JP domestic prints) — tag it, don't silently drop the domain.
4. **Every answered question is grounded.** Q1/Q3/Q4/Q5 → `econ.fact_indicator` /
   `rates.fact_observation` / `cb_events`; Q2/Q6 → cited research corpus. Same
   discipline as the briefs; no number without a source.
5. **Reuse the existing engines.** Q1 ≈ cluster map, Q5 ≈ 8-driver engine, Q6 ≈
   rates playbook. This doc names the questions; it does not re-implement scoring.
6. **`cb_events.actual` is low-trust.** Actuals come from `econ.fact_indicator` /
   corpus; `cb_events` is the consensus + calendar only.
7. **No DDL, no prod-wiring without explicit user OK.** Read-only DB.

---

**Eight domains, six archetypes, one country overlay. The wiring map says where
the data is; the driver taxonomy says how a surprise scores; the cluster map says
what to track. This says what to *ask* — and the answers are the country read.**
