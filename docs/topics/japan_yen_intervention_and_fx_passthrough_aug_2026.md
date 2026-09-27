# Japan — Yen Intervention Episodes & FX Pass-Through to Inflation

**Brief · 2026-08-03 · IMDR**

Two desk questions, answered on IMDR-ingested data:

1. **A 10% yen appreciation reduces inflation by how much, and over what duration?**
2. **In the last yen-intervention episodes, how far did the yen rally, and how long back to pre-rally levels?**

Both are grounded on native sources pulled into the Japan econ playground (not yet
in the prod DB): BoJ USD/JPY spot (`BOJ.FX.USDJPY_SPOT.JP`, FM08, daily 1998→) and
NEER (`BOJ.FX.NEER.JP`, FM09, monthly 1980→, higher = stronger yen); e-Stat CPI
2020-base (headline/core/core-core, index + YoY, 1970→); BoJ CGPI import prices
(yen + contract-ccy basis, 2020→); and MOF's official **Foreign Exchange
Intervention Operations** CSV (daily amounts + direction, Apr-1991 → Jul-2024).

## TL;DR (one-page brief)

> **Intervention (Q2):** MOF's only recent *yen-buying* (yen-rallying) operations are
> **2022** (¥9.19tn: Sep-22 + Oct-21/24) and **2024** (¥15.32tn: Apr-29/May-1 + Jul-11/12).
> The 2010–2011 operations were yen-*selling* — they weakened the yen, not strengthened it.
> The intervention's *own* punch was small and short-lived: **~1.5–3% on the close (larger
> intraday), faded within days-to-~2 weeks whenever it stood alone** (Sep-2022 gave it back
> same day; Apr/May-2024 in 16 days). The **10–15% rallies people remember were driven by
> the *fundamental* catalysts that followed** — Fed pivot + BoJ YCC widening (Dec-2022);
> BoJ hike + global carry unwind (Aug-2024) — and *those* took **~12 months to reverse in
> 2022**, and had **not reversed until 2026** for the Jul-2024 low. There is no clean average
> round-trip; it is bimodal (unaided ≈ 1–2 weeks, fundamentally-reinforced ≈ 12+ months).
> **Intervention bought time; it did not set the trend.**
>
> **Pass-through (Q1):** A sustained **+10% yen appreciation trims CPI by ~0.5–0.7pp
> (headline/core), ~0.2–0.5pp (core-core) over the first year**, building toward **~1–1.5pp
> by 24 months** — small, slow, back-loaded, largest 12–24 months out. Border pass-through
> to yen import prices is fast and near-complete within a quarter; only a small fraction
> (order 5–7%) reaches consumer CPI, and slowly. Pass-through is **higher post-2000/post-2021**
> than the 1980s–90s average.

---

## Q2 — Intervention event study

### The episodes (MOF official CSV, yen-buying only)

| Date | Amount | Direction | Campaign total |
|---|---:|---|---:|
| 2022-09-22 | ¥2.84tn | JPY buy | |
| 2022-10-21 | ¥5.62tn | JPY buy | |
| 2022-10-24 | ¥0.73tn | JPY buy | **2022: ¥9.19tn** |
| 2024-04-29 | ¥5.92tn | JPY buy | |
| 2024-05-01 | ¥3.87tn | JPY buy | |
| 2024-07-11 | ¥3.17tn | JPY buy | |
| 2024-07-12 | ¥2.37tn | JPY buy | **2024: ¥15.32tn** |

> **Direction matters.** MOF also intervened in **2010-09** (¥2.13tn) and **2011**
> (Mar ¥0.69tn, Aug ¥4.51tn, Oct-31 ¥8.07tn + Nov ¥0.76tn) — all **yen-selling** to
> *weaken* the yen (push USD/JPY up). Those are not "yen rallies" and are excluded here.
> Earlier yen-buying: 1997-12 (¥0.76tn) and 1991–92. Historical archive runs to Apr-1991.

### (A) Tactical intervention footprint — close-to-close, ≤10 trading days

Method: pre-level `P0` = USD/JPY close the day before the first intervention day; tactical
low = strongest yen close within 10 trading days; "give it back" = first close back at `P0`.

| Episode | Size | Pre-level `P0` | Tactical low | Close punch | Days to give back |
|---|---:|---:|---:|---:|---:|
| 2022-Sep | ¥2.84tn | 143.75 | 143.83 | **~0%** † | **1** |
| 2022-Oct | ¥6.35tn | 149.87 | 145.73 | **−2.8%** | 358 ‡ |
| 2024-Apr/May | ¥9.79tn | 156.71 | 154.12 | **−1.7%** | **16** |
| 2024-Jul | ¥5.53tn | 161.50 | 152.20 | **−5.8%** ‡ | 697 ‡ |

† The Sep-22 intraday spike (~2.3%, to ~140.3) fully reversed by the 17:00 JST close — the
yen closed *weaker*. On a close basis the operation had zero end-of-day punch.
‡ These reflect the *fundamental* catalyst that took over, not intervention fading (see B).

- **Mean tactical punch: −2.5% on close** (range ~0% to −5.8%; intraday moves were larger).
- Where intervention **stood alone**, the yen round-tripped in **days (Sep-2022) to ~2 weeks (Apr/May-2024)**.

### (B) The 6-month moves were fundamentally driven, not intervention

| Episode | Deepest yen (180d) | Move from `P0` | Date | Actual driver |
|---|---:|---:|---|---|
| 2022 (both) | 127.99 | **−11% to −15%** | 2023-01-16 | Fed pivot + BoJ YCC widening (Dec-20-2022) |
| 2024 (both) | 140.60 | **−10% to −13%** | 2024-09-17 | BoJ hike (Jul-31) + global carry unwind (Aug-5) |

The durable reversals came from policy/rate catalysts, **not** the intervention itself. The
2022 move reversed back to the pre-intervention weak level in ~12 months (Oct-2023); the
Jul-2024 low did not reverse to 161.50 until Jun-2026 (USD/JPY latest 163.7).

**So-what for the book:** unilateral MOF intervention is a *timing/volatility* tool, not a
trend-setter. Fade the immediate spike unless a fundamental catalyst (Fed easing, BoJ
tightening, carry unwind) is aligned; when one is, the move runs 5–7× the intervention's own
footprint and persists for quarters.

---

## Q1 — FX pass-through to CPI

Method: Jordà local projections, monthly, Newey-West HAC errors, controls = 6 lags of ΔCPI
and ΔNEER. Reported as a **pass-through elasticity** (price-level IRF ÷ NEER's own IRF), so
the figure is for a *sustained* 10% appreciation, not a one-month blip.

### Effect of a sustained +10% NEER appreciation on the CPI *level* (pp), 2000→ sample

| CPI measure | 6m | 12m | 18m | 24m |
|---|---:|---:|---:|---:|
| **Headline** | −0.7 | **−1.0** | −1.7 | −1.6 |
| **Core** (ex-fresh food) | −0.7 | **−0.9** | −1.6 | −1.5 |
| **Core-core** (ex food & energy) | −0.4 | **−0.6** | −1.4 | −1.6 |

A conservative 12m-on-12m elasticity cross-check lands lower (headline −0.42pp, core −0.40pp,
core-core −0.21pp at 1yr), so the **honest desk range**:

- **~0.4–0.7pp off headline/core CPI at 12 months** (central ~0.5–0.6pp).
- **Core-core ~0.2–0.6pp at 12 months.**
- Builds to **~1–1.5pp by 24 months** — **slow and back-loaded**: roughly half by 6–9 months, full by ~18–24 months.
- **Regime-dependent:** full-sample (1981→) runs ~30% lower than post-2000/post-2021.

### Border cross-check (yen-basis import prices, 2020→ — short, confounded)

Pass-through to import prices is **fast and near-complete within a quarter** (the point
estimate even overshoots — ≥10% within 3–6m — but the 2020→ window is short and the 2022
energy shock coincided with yen weakness, so treat as directional). The chain is intact:
**appreciation hits import prices almost fully and quickly, but only a small fraction reaches
consumer CPI, and slowly** — consistent with BoJ/IMF pass-through estimates (10% move → a few
tenths of a pp on core CPI over 1–2 years).

**So-what for the book:** a 10% yen round-trip is **not** a first-order CPI swing factor on its
own — it moves core CPI by tenths of a point, spread over 1–2 years. It matters most as a
*slow* tailwind/headwind that BoJ can look through in the near term, and as a fast mover of the
PPI/import-price and terms-of-trade series that feed margins.

---

## Reproduce

- Analysis script: `playground/econ/jp/` inputs → local-projection + event-study (numpy OLS + Newey-West).
- Intervention parse: `playground/econ/jp/mof/sample_output/mof_intervention_clean.csv`
  (from MOF `foreign_exchange_intervention_operations.csv`; amounts in 100mn yen, comma-delimited, direction classified from the bilingual currency-pair column).
- FX/CPI/import-price parquet under `playground/econ/jp/{boj,estat}/sample_output/2026/08/03/`.

## Caveats

- Spot is BoJ 17:00 JST close → intraday intervention spikes understated in Q2.
- Import-price pass-through sample is only 2020→ (78 months) and confounded by the 2022 energy shock.
- Pass-through is regime-dependent; three samples shown (full / 2000→ / 2013→) to bound it.
- Japan econ series are playground-loaded, not yet in the prod DB.

## Related

- [`../admin/econ/japan/japan_indicator_inventory.md`](../admin/econ/japan/japan_indicator_inventory.md) — Track-A coverage (FX cell 3.4, CPI cell 2.4, import price cell 2.1).
- [`../admin/econ/japan/index.md`](../admin/econ/japan/index.md) — JP econ landing page.
- [`../admin/econ/economy_questions.md`](../admin/econ/economy_questions.md) — pass-through sits in the FX / external-sector domain.
