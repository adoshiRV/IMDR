# Economy Questions — Building Log (per-country tracked questions)

**The living, accumulating log of country-specific questions.** The *generic
framework* — the 8 domains × 6 question archetypes + the overlay mechanism — lives
in [`economy_questions.md`](economy_questions.md). **This** doc is where
country-specific questions get **built up and refined over time** as they surface
(from research digests, PM input, incoming reports). It's the working list; the
spec is the theory.

- **Status:** active, append-only working log. Not a spec — a backlog of what to
  ask per country, refined as reports land.
- **Consumer:** **Smith** (the country economist) reads this when authoring or
  refreshing a country's [Country Economy Profile](economy_questions.md#8--the-deliverable--the-country-economy-profile-smith)
  (`data/economy_profiles/{cc}/`). New questions are appended **here**, not in the
  generic spec (which stays country-agnostic).
- **Date:** 2026-07-10.

---

## How to use this doc

Each country has a section: its **dominant domains** + a table of **tracked
questions**. Every question:

1. **Maps to a domain × archetype** (from the [generic framework](economy_questions.md) —
   D1–D8 × Q1–Q6), so it plugs into the same lens as everything else.
2. Carries a **data-status flag** — what's answerable from IMDR *today*
   (✅ loaded · ⚠️ partial/gap · ❌ absent).
3. Where it came from a **research view**, the numbers are the *current
   annotation* — **a thesis to test, verified against `econ.fact_indicator` before
   it graduates from thesis to fact.** The framework keeps facts (data) and views
   (research) separate on purpose; this doc respects that.

**Adding a question:** append it to the country's table (create the country
section if new), map it to a domain × archetype, flag the data status, and note the
source if it's a research view. Keep the generic spec untouched.

---

## India (IN)

**Dominant domains:** D1 (Inflation), D2 (Growth). Standing overlay: **rural vs
urban** runs through D1/D2/D3; **monsoon → food → D1**.

| Question | Domain · archetype | Data in IMDR |
|---|---|---|
| **Credit-growth deep-dive** — which *sectors* are driving bank-credit growth (agri / industry / services / personal), and are the growing sectors the **productive** ones that lead the activity cycle at a lag (capex, industry, infra) or just **personal-consumption** credit? At what lag does sectoral credit lead the growth pulse? | **D4** Q1 Decompose + Q2 Driver + Q4 History | ⚠️ **Gap** — needs RBI DBIE *Sectoral Deployment of Bank Credit* (the A7 path); this is India's ❌ cell **4.1 Demand Transmission**, not yet onboarded. Aggregate credit + BIS credit-to-GDP present; sectoral split is the missing leg. |
| **Rural vs urban consumption (last 6m)** — how is **rural** consumption growing over the last 6 months, and how does it **contrast with urban**? | **D2** Q1 Decompose + Q2 Driver (the IN rural/urban overlay) | ⚠️ Partial — MOSPI PFCE is aggregate; rural/urban split needs proxies (rural: two-wheeler/tractor sales, FMCG rural volumes, MGNREGA demand, rural wages; urban: PV sales, urban FMCG, card spend). |
| **FCNR(B) flows** — size + direction of NRI deposit flows (FCNR(B) / NRE / NRO); sticky vs hot, and the FX-sensitivity of the flows as an external-funding read. | **D5** Q1 Decompose + Q2 Driver | ✅ RBI Bulletin **T34 NRI Deposits** (FCNRB / NRERA / NRO) loaded. |

---

## United States (US)

**Dominant domains:** D7 (Fed reaction function), D1 (Inflation), D3 (Labour) — the
read is reaction-function-led; the trade lives in what's priced vs implied.

| Question | Domain · archetype | Data in IMDR |
|---|---|---|
| **Where is core PCE** now (level), and where does it sit vs the 2% target? | **D1** Q1 Decompose | ✅ BEA **core PCE** price index (ex food & energy), monthly (cell 2.4). |
| **What trend** in core PCE — 3m / 6m annualised, and direction (re-accelerating or cooling)? | **D1** Q2 Driver + Q4 History | ✅ same series; derive 3m / 6m annualised + sequential. |
| **What has surprised** up / down in the last 3–6m, across the key releases (PCE, CPI, NFP, retail, ISM)? | **D1–D3** Q5 Surprise | ✅ surprise = `econ.fact_indicator` actual − `cb_events` consensus; sign + magnitude per release. |
| **Where is momentum building** — which domain's pulse is accelerating (inflation, labour, activity)? | **D2 / D1** Q2 Driver + Q4 History | ✅ activity / labour / inflation series; momentum from sequential history. |
| **Effect on 1y Fed pricing** of those surprises — how much has the 1y path repriced per unit of surprise? | **D7** Q6 Reaction/pricing + Q5 | ⚠️ 1y Fed pricing in `rates.fact_observation`; the *conditional repricing* computation is the §5 vol layer — **not built**; answer qualitatively + flag until built. |

---

## South Korea (KR)

**Dominant domains:** D1 (Inflation), D4 (Housing & credit), D8 (Global
transmission). **Country-specific thesis** (research desk's *wealth-effect
flywheel*, Korea digest): a self-reinforcing wealth machine — wages → consumption →
housing wealth → investment → pro-market policy — is switching on. The reads below
are the *current annotation*; **verify vs `econ.fact_indicator` / REB when Smith
answers** — the flywheel is a thesis to test, not an asserted fact.

| Question | Domain · archetype | Data in IMDR |
|---|---|---|
| **Is the wealth-effect flywheel compounding?** — the self-reinforcing loop wages → consumption → housing wealth → investment → pro-market policy. | Cross-domain (**D4** Q3 anchor + D2/D3/D6) | ✅ the pillar components below; the *loop* is a synthesis read. |
| **Housing wealth → consumption** — Seoul home prices strong (thesis: +9.6% y/y, Apr-2026); how much of the consumption pickup is the **wealth effect** vs income / stimulus? | **D4** Q3 Sensitivity (wealth-effect pass-through) + Q1/Q2 | ✅ REB housing (R-ONE) prices; BOK household income; KOSTAT retail / private consumption. |
| **Labour tightness → domestic demand** — unemployment low (thesis: ~2.6%), real wages turning positive, employment +YoY; is tight labour feeding **domestic-services** demand? | **D3** Q1 Decompose + Q2 Driver | ✅ KOSTAT EAPS unemployment / employment + Wages. |
| **Investment / capex revival** — facility investment strong (thesis: +6.6% q/q, strongest in 4y); is the **semi super-cycle** driving a broader capex cycle? | **D2** Q1/Q2 + **D8** (semis) | ✅ BOK GDP facility-investment component; ties to the existing semi-export overlay. |
| **Pro-market policy / tax architecture** — separate dividend tax (14/20/25/30%, passed Dec-2025), supplementary budgets, US tariff cap ~15%; structural tilt supporting asset prices + the BoK 2026 GDP upgrade (thesis: 2.6%). | **D6** Fiscal (stance / structural) + **D7** (BoK forecast) | ⚠️ Fiscal series (BOK Public Sector) present; the tax-reform + tariff facts are **corpus / news**, not a data series. |

---

## Countries with no tracked questions yet

These carry a standing overlay in [`economy_questions.md` §6](economy_questions.md#6--axis-3--the-country-overlay)
(dominant domains + the country-specific one-liner) but haven't accumulated a
tracked-question list yet. Add a section here when questions surface:

- **JP** (D7, D8) — how a domestic print percolates to JGBs; Shunto wages as the binding D1 test.
- **AU** (D4, D5, D8) — housing → GDP; terms of trade / iron ore; China beta.
- **NZ** (D5, D8) — dairy / GDT rural-income pulse; oil-import sensitivity.
- **TW** (D8, D2) — semiconductor cycle dominates; headline GDP AI-distorted.
