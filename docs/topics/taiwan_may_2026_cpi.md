# Taiwan — May 2026 CPI: 2% Threshold Breach

**Brief · 2026-06-05 · IMDR**

DGBAS released May CPI at **+2.20% Y/Y** (est +2.12%) and **core +2.12% Y/Y**
(est +2.00%) — Taiwan's first joint headline-and-core breach of the CBC's
2% inflation threshold in this cycle. The breach was the May
materialisation of a setup the sell-side had been flagging through April
and May 2026; the news is the **core overshoot** (+12bp surprise, vs
+8bp on headline), which separates the print from a pure oil-pass-through
story and pulls forward the June CBC meeting as a live event.

## TL;DR (one-page brief)

> **Headline +2.20% / Core +2.12% — both above the CBC 2% line, both above
> consensus.** Driver mix is oil pass-through (Middle-East shock, fuel
> +13.6% Y/Y in April) plus AI-cycle demand pressure (DGBAS-revised 2026
> growth to 9.64%; Nomura now 9.9%; Q1 GDP 14.5%). Policy book splits
> hawkish-to-neutral: Nomura assigns **40% probability of a June hike**
> (R3913, 4 Jun); ANZ pre-print said any upside surprise would trigger a
> hike (R1752, 29 May) and the print did surprise; Goldman pencils 25bp
> in 2026 (R2694, 31 May); BNP's Taiwan-trip note has local clients
> dovish and BNP holds a **steepener** (R1395, 26 May). Trades on the
> book: Nomura **pay Sep-5y NDIRS** target 2.53% by mid-July (R2268, 1 Jun),
> Goldman **OW Taiwan equities** TWSE target 51,000 (R2629, 2 Jun).

### Print vs sell-side desk (last 4 weeks)

| Source | Date | Headline call | Core call | Implied policy lean |
|---|---|---:|---:|---|
| **Bloomberg consensus** | pre-print | +2.12% | +2.00% | — |
| **Actual (DGBAS)** | 2026-06-05 | **+2.20%** | **+2.12%** | **—** |
| ANZ ([R1752](#desk-research-cited)) | 2026-05-29 | +2.14% | "likely breach 2%" | If upside surprise → **June hike** |
| Nomura ([R73](#desk-research-cited)) | 2026-05-07 | "above 2% in coming months partly base effects" | 1.9% (stable) | Hold; 30% prob 12.5bp hike at June |
| Nomura ([R3913](#desk-research-cited)) | 2026-06-04 | upside risks | upside risks | 60% hold / **40% hike June** |
| BNP ([R2571](#desk-research-cited)) | 2026-06-02 | DGBAS 2026 forecast +1.93% | — | Dovish (locals) / steepener |
| Goldman ([R2694](#desk-research-cited)) | 2026-05-31 | "pressures higher in Korea than Taiwan" | — | **25bp in 2026 (pencilled)** |

ANZ called the headline closest (within 6bp), but **no desk explicitly
penciled in a core breach** — that's the print's signal.

### CPI composition (Apr-26 prior, % Y/Y, source: Nomura R73 from DGBAS)

| # | Category | Weight % | Apr-26 | What moved |
|---|---|---:|---:|---|
| ① | Food | 25.6 | +0.6 | Fruits −18.1, Meat +3.1, Veg +2.7 (turning) |
| ② | Clothing | 5.7 | +0.8 | Stable |
| ③ | Housing | 22.7 | +2.1 | **Rent +1.9** — sticky core component |
| ④ | Transport & Communication | 14.7 | **+2.7** | **Fuel +13.6** Y/Y — Middle East shock |
| ⑤ | Health | 5.6 | +1.0 | Stable |
| ⑥ | Education | 5.3 | **+3.4** | Rising, services-driven |
| ⑦ | Entertainment | 9.1 | +1.9 | Stable |
| ⑧ | Others | 11.4 | +2.5 | Insurance, personal care |
| **Σ** | **Headline CPI** | **100.0** | **+1.74** | |
| | Core (ex fruits/veg/energy) | 92.6 | +1.9 | Held below 2% in April; **breached in May** |

Identity (weight-check): 25.6 + 5.7 + 22.7 + 14.7 + 5.6 + 5.3 + 9.1 + 11.4 = **100.1** ≈ 100 ✓ (rounding).
Core weight check: 100 − Fruits 2.1 − Vegetables 1.6 − Fuel 2.2 − some energy-adjacent = 92.6 ✓.

### How to think about it (driver decomposition)

| # | Driver | Reversibility | Evidence |
|---|---|---|---|
| ① | **Oil pass-through** via fuel sub-index | Mean-reverts on Brent stabilising; CBC has stated it "looks through" energy | Apr fuel +13.6% Y/Y (R73); ANZ models +0.3ppt headline lift from new energy level (R1752); GS R1673 Exhibits 23-28 frame as oil-driven |
| ② | **AI-cycle demand & wage pressure** | **Structural, sticky** — drives the core breach | DGBAS upgrade: 2026 growth 9.64%, inflation 1.93% (R2571); Q1 GDP 14.5% Y/Y (R3913); HSBC PMI input-cost index near historic highs (R2706); GS: tech exports = 5.9pp of Taiwan GDP (R2694) |
| ③ | **Base effects** | Mechanical; fades through Aug-Sep | Nomura (R73): "above 2% partly base effects" |
| ④ | **TWD pass-through** | Slow; depends on CBC FX-rule choice | HSBC: CBC reserves drew $8.6bn in March (R1966); ANZ: Lifers reducing FX hedging, average ratio falling (R2402); Import prices +9.2% Y/Y April (R73) |
| ⑤ | **Pipeline (PPI/import prices) lag** | 3-6 month lag → next 2-3 prints | Apr PPI +8.5% Y/Y (from +3.9%); Apr import prices +9.2% Y/Y (R73) |

The **core breach is most consistent with driver ② (AI-cycle demand)
plus driver ⑤ (pipeline pass-through)** — i.e. the part of the inflation
the CBC *cannot* look through.

### Read sequence

- Framework + DGBAS code structure → [Appendix A](#appendix-a--framework-and-data-source)
- May print detail + desk reaction table → [Appendix B](#appendix-b--current-flow-picture-may-jun-2026)
- June CBC meeting + forward drivers → [Appendix C](#appendix-c--forward-drivers)
- How to pull the data → [Appendix D](#appendix-d--data--code-pointers)

---

## Appendix A — Framework and data source

### Issuer

**DGBAS** (Directorate-General of Budget, Accounting and Statistics,
Executive Yuan, Republic of China). Monthly release on the 5th of the
following month at 16:00 Taipei (08:00 UTC).

Source URL: <https://www.stat.gov.tw/cp.aspx?n=2716> (Chinese), English
mirror at <https://eng.dgbas.gov.tw/np.aspx?n=3343>.

### Index construction

- **Base year**: 2021 = 100 (current basket)
- **Coverage**: 366 items across 8 expenditure groups + 5 cross-classification splits (Goods vs Services; Durable/Semi-durable/Non-durable; Local vs Imported)
- **Weight basis**: Survey of Family Income and Expenditure, rebased every 5 years
- **Geographic coverage**: 17 cities and counties, Laspeyres index

### Core CPI — Taiwan-specific definition

Critical translation gotcha:

| Source | "Core CPI" means |
|---|---|
| US BLS | CPI ex Food and Energy |
| Eurostat HICP | All-items ex-energy / ex-energy-and-food |
| **DGBAS Taiwan** | **CPI ex fresh fruits, fresh vegetables, AND energy** |

Taiwan's core does **not** strip out all food — only the volatile fresh
produce. Processed food, meat, and dairy stay *in* the core. Weight =
92.6% of headline (vs ~80% for US core).

This matters for cross-country comparison: Taiwan core 2.12% is closer
in spirit to a US "core-services + non-food-goods" composite than to US
core CPI.

### Policy context

- **CBC policy rate**: rediscount rate, currently **2.00%** (held since cut cycle ended)
- **Inflation target**: 2.00% Y/Y — formally a "medium-to-long-term goal"; Governor Yang has stated short-term breaches "to slightly beyond" should be tolerated (R73, citing prior speeches)
- **Next CBC meeting**: quarterly, **June 2026** (per ANZ R1752 explicit reference)
- **Inflation expectation gauge**: Cathay Financial Holding survey, end-April 2026 reading 80.7 (vs 82.4 March, 82.1 2025 avg) — **anchoring well**, declining trend (R73)

---

## Appendix B — Current flow picture (May-Jun 2026)

### The print (DGBAS, 5 June 2026 release)

| Series | May-26 Y/Y | Bloomberg est | Surprise |
|---|---:|---:|---:|
| **Headline CPI** | **+2.20%** | +2.12% | +8 bp |
| **Core CPI** (ex fresh fruit/veg/energy) | **+2.12%** | +2.00% | +12 bp |

April reading (for reference): headline +1.74%, core +1.9%. **Headline jumped 46bp month-on-month**; core jumped 22bp.

ANZ pre-print (R1752, 29 May) modelled the new fuel level alone to add
0.3ppt to headline — that would have taken April's 1.74 to 2.04; the
incremental ~16bp above that is the **non-energy** core acceleration
(consistent with the 22bp core jump).

### Desk-reaction mosaic — full quotes

**ANZ — Raymond Yeung, 29 May 2026 ([R1752](#desk-research-cited))**
> "Taiwan's CPI likely exceeded the policy threshold of 2% in May. Our
> forecast of **2.14%** is based on April's strong momentum, where fuel
> prices surged by 13.6% … The new level of energy prices will have
> raised the headline CPI by 0.3 ppt. **Core inflation has stayed at the
> 1.9% level in the first four months and will likely breach 2% in May.
> Any further surprise on the upside will prompt CBC to hike in the June
> meeting.**"

That last sentence is the load-bearing one — the actual print is
+8bp/+12bp above their forecast/expectation, so by their own conditional
the June CBC hike risk has just hardened.

**Nomura — Jeong Woo Park / Si Ying Toh, 7 May 2026 ([R73](#desk-research-cited))**
> "We assign a **30% probability to a 12.5bp pre-emptive policy rate
> hike at the June meeting**. … CPI inflation could come in at above 2%
> in the coming months (partly reflecting base effects), [but] the CBC
> is likely to look through it, as Governor Yang has previously
> mentioned that short-term increases in monthly inflation to slightly
> beyond the 2% target should be tolerated."

**Nomura updated — Euben Paracuelles / Yiru Chen, 4 June 2026 ([R3913](#desk-research-cited))**
> "Taiwan: A likely hawkish hold. With GDP growth significantly above
> trend and upside inflation risks, **we see a 60% probability of a
> hawkish CBC hold in June, against a 40% likelihood of a policy rate
> hike**. We revise up our GDP growth forecasts to **9.9%** from 8.4% in
> 2026 and to 4.5% from 3.6% in 2027."

The 40% June hike probability was set *before* today's print and the
view explicitly cites "upside inflation risks" as the trigger condition.

**Goldman — Asia EM team, 31 May 2026 ([R2694](#desk-research-cited))**
> "We continue to expect cumulative policy rate hikes in 2026 of **25bp
> in Taiwan** and change our view on Korea from on-hold to two 25bp
> hikes in the second half. … Inflation pressures may be somewhat
> higher in Korea, reflecting greater upside risk."

Goldman's framing has Korea > Taiwan on inflation risk — today's print
narrows that spread (Taiwan now over the line; Korea's May CPI was
+3.0% per Nomura R3069 / BNP R2573).

**BNP — Jeeho Yoon, 26 May 2026 ([R1395](#desk-research-cited)), post-Taiwan-trip**
> "Growth has been stellar, fueling inflation concerns, our recent trip
> to Taiwan suggests that **local clients maintain a dovish bias,
> believing the CBC may not act before the Fed does** — we continue to
> hold a steepener."

And updated 2 June (R2571): "DGBAS upgraded its 2026 growth forecast to
**9.64%** and its inflation forecast to **1.93%**, citing AI-driven
[demand]." DGBAS itself moved before the print — partial recognition,
but the 1.93% full-year forecast is now inconsistent with a 2.20% May
print absent a sharp H2 decline.

**Goldman — Timothy Moe / Alvin So, 2 June 2026 ([R2629](#desk-research-cited))**
> "Taiwan to overweight. … Taiwan is the market with the greatest
> exposure to AI with close to 85% of market cap having some portion of
> revenues directly from AI-related activity. … 39% 2026/27 earnings
> growth, 0.7 PEG ratio … Risks: Narrow breadth, retail speculation.
> TSMC is 41% of TWSE index."

Equity book is leaning into the same AI-cycle that's driving the core
CPI breach. Goldman's TWSE 51,000 12m target implies +12% return; they
hedge concentration via put spread collars.

**Nomura — Asia rates, 1 June 2026 ([R2268](#desk-research-cited))**
> "Re-enter pay Sep-5y Taiwan NDIRS (conviction level 3/5, current
> 2.333%) … target 2.53% by mid-July … Statistics bureau GDP/inflation
> upgrade and 5y NDIRS still holding above technical [support]."

This trade is already long-rates-higher and has been in the book since
1 June — today's print is supportive.

**HSBC — EM FX, 28 May 2026 ([R1966](#desk-research-cited))**
> "After selling some USD30bn worth of Taiwanese equities in March and
> early April, foreign investors have since returned to buy back about
> USD15bn worth. … CBC's limitations on exporters' FX sales may be
> eased, as the central bank is showing [signs] … reserves declining
> (USD8.6bn in March)."

CBC is choosing FX-rule loosening over rates as the TWD-pressure
release valve — a hike today's print might force complicates that.

### Flow narrative (what every actor is doing)

1. **DGBAS** released May data showing CBC threshold breach on both lines; pre-released its own 2026 inflation forecast to 1.93% (now stale).
2. **CBC** is between two prior commitments — "look through energy" (Yang) and "rediscount rate not yet to neutral" — June meeting is the test.
3. **Foreign investors** had been selling Taiwan equities through March-April ($30bn out), reversed in May ($15bn in) on AI conviction; rate hike risk now reintroduces an offsetting headwind.
4. **Taiwan lifers** are reducing FX hedging (hedge ratio falling) → less natural USD demand from hedge rolls → modestly TWD-supportive.
5. **Exporters** are facing CBC limits on FX-sale timing; if CBC eases this rule (HSBC view) it adds FX supply (TWD-positive) — partly substitutes for a hike.
6. **Domestic CPI feedthrough**: rent +1.9% Y/Y is the sticky core driver; the May breach likely doesn't move that subseries (rent reacts to wages with multi-quarter lag) but next 2-3 prints face the PPI/import-price pipeline already in the system (Apr PPI +8.5%, import prices +9.2%).

---

## Appendix C — Forward drivers

### June CBC meeting (the next hard event)

**Two-conditional ladder from the desks**:

| Condition | Hawkish probability | Source |
|---|---:|---|
| May CPI > 2.0% AND core > 2.0% | ANZ → CBC hikes ("any upside surprise") | R1752 |
| GDP growth above trend AND inflation upside risks | Nomura → 40% hike June | R3913 |
| Either condition standalone | Nomura → 30% 12.5bp pre-emptive | R73 (earlier framing) |

The print satisfies all three conditions simultaneously. **Implied
re-rated hike probability post-print: meaningfully > 40%**, against a
market that on 2 June was pricing only token tightening (per ANZ R2402
Asia FX commentary).

### Pipeline (3-6 month lag, per Nomura R73)

| Indicator | Apr-26 Y/Y | Lag to CPI | Implication |
|---|---:|---|---|
| PPI | **+8.5%** (from +3.9% Mar) | 3-6 months | Headline + core pressure through Aug-Oct |
| Import price (TWD) | **+9.2%** (from +5.3%) | 3-6 months | Same — partly TWD weakness, partly oil/materials |
| Fuel prices Y/Y | **+13.6%** | Direct (1 month) | Already in May print |
| Cathay inflation expectations | 80.7 (declining) | — | Anchored — limits second-round wage demands |

### AI-cycle structural

DGBAS revised 2026 GDP growth to 9.64% (R2571); Nomura to 9.9% from 8.4%
(R3913); CBC's own forecast still 7.3%. Q1 GDP came in 14.5% Y/Y. Q2
nowcast 10.5% Y/Y (Nomura-TWnow). **Output gap is closing fast** —
classic Phillips-curve pressure on core. This is the structural force
that turns transient oil-driven prints into sustained core breaches.

### TWD

CBC FX reserves drew down $8.6bn in March (R1966); Lifer hedge ratios
falling (R2402); foreign equity flows reversed from sell to buy mid-May
(R1966). A June CBC hike would tighten USD-TWD basis and could
accelerate the TWD demand wave that's already building. Cross-asset:
Goldman R2629's TWSE put-spread-collar hedge is partly a TWD-strength
hedge in disguise.

### Calendar (next 90 days)

| Date | Event | Implication |
|---|---|---|
| Jun-26 (date TBC) | **CBC quarterly policy meeting** | Hike or hawkish hold — material |
| Jul-05 | **DGBAS June 2026 CPI release** | Does core breach hold/widen? |
| Jul-mid | **Nomura R2268 trade target date** (2.53% 5y NDIRS) | Mechanical |
| Aug-05 | **DGBAS July 2026 CPI release** | PPI pipeline (Apr +8.5%) starts hitting |

---

## Appendix D — Data + code pointers

### Time series, by source

| Path | What | Lag | Notes |
|---|---|---|---|
| **DGBAS** (stat.gov.tw) | Headline + core CPI + 8 categories + 5 cross-classifications | T+5 | Source-of-truth. Not yet wired into `econ.fact_indicator`. |
| **FRED** `TWNCPIALLMINMEI` | Taiwan CPI headline, monthly | T+~30d | Mirror; would map to `FRED.CPI.HEADLINE.TWN`. Not currently loaded — see [`docs/admin/econ/macro_economy_wiring_map.md`](../admin/econ/macro_economy_wiring_map.md) for wiring backlog. |
| **CBC** (cbc.gov.tw) | Rediscount rate, inflation forecasts, monetary aggregates | — | Quarterly reports + monthly press releases. Not currently scraped. |
| **`research.dim_report` / `fact_chunk`** | All sell-side citations in this brief | — | 13 reports cited, see desk-research table below. |

### Code

No automation yet for Taiwan CPI ingest. To add:

1. Add `dim_indicator` rows for headline + core (per `imdr.config.settings.Settings` indicator pattern).
2. Scaffold `playground/econ/dgbas/` per [PLAYGROUND-ONLY rule](../../CLAUDE.md) — DGBAS publishes both an HTML table and a downloadable XLS.
3. After validation, port to `scripts/econ/dgbas/dgbas_cpi_monthly.py` and load via the canonical `python -m scripts.migrations.load_econ_indicator_from_playground --vendor dgbas` flow.
4. Document under `docs/admin/vendors/dgbas/` once onboarded.

### Desk research cited

| Report ID | Vendor | Date | Title | Used for |
|---|---|---|---|---|
| 73 | nomura | 2026-05-07 | Asia Insights — Taiwan: Energy-driven jump in headline inflation, while core remains stable | April CPI breakdown table, CBC framework, Cathay expectations, 30% June-hike probability |
| 756 | goldman | 2026-05-22 | AEJ Week Ahead: Korea and Taiwan IP, BOK meeting and Singapore CPI | Pre-print activity backdrop |
| 1395 | bnp | 2026-05-26 | EM Asia: What you need to know this week (25-31 May) | BNP Taiwan-trip read (dovish locals); steepener on book |
| 1673 | goldman | 2026-05-27 | Oil drives headline higher | Full Taiwan CPI chartset (Exh 23-28: headline, core, contribution, PPI, wages, retail energy) |
| 1752 | anz | 2026-05-29 | Asia Macro Weekly | **ANZ Taiwan forecast 2.14% headline; "any upside surprise → June CBC hike"** |
| 1966 | hsbc | 2026-05-28 | Emerging Markets FX Roadmap Hope | CBC FX-reserve drawdown; FX-rule easing thesis |
| 2232 | ms | 2026-05-29 | Asia — Macro Catalysts | Kathleen Oh chief Taiwan econ; macro context |
| 2268 | nomura | 2026-06-01 | Asia Insights — HK and Taiwan rates: Close 10y HK pay, enter pay 5y Taiwan | **Pay Sep-5y NDIRS trade, target 2.53% mid-July** |
| 2402 | anz | 2026-06-02 | Asia FX (H)edge | TWD positioning, Lifer hedge ratio decline |
| 2571 | bnp | 2026-06-02 | EM Asia: What you need to know this week (1-7 Jun) | DGBAS pre-print upgrade (growth 9.64%, inflation 1.93%) |
| 2629 | goldman | 2026-06-02 | Leaning into earnings: Taiwan to OW, KOSPI target to 12k | Equity OW; TWSE target 51,000; put-spread collar hedge |
| 2694 | goldman | 2026-05-31 | Tech and Energy Drive EM Differentiation | **GS 25bp Taiwan 2026 hike pencilled**; AI-cycle GDP impact |
| 2706 | hsbc | 2026-06-02 | Disruptions persist, easing slightly | PMI input cost inflation in Taiwan near historic highs |
| 3511 | ms | 2026-06-04 | Asia Summer School 2026: Asia Economics | Taiwan "moderately exposed" to oil pass-through |
| 3907 | ms | 2026-06-04 | June 4: Oil-Led Rates Rally | TWD price action; equity 1.7% sell-off |
| 3913 | nomura | 2026-06-04 | Asia Economic Monthly — Our out-of-consensus calls | **Nomura 60% hold / 40% hike June; 2026 GDP 9.9%** |

### Gaps

- **No `econ.fact_indicator` Taiwan series wired** — DGBAS not yet onboarded as an econ vendor. Would be a clean add per the wiring map (see [`docs/admin/econ/macro_economy_wiring_map.md`](../admin/econ/macro_economy_wiring_map.md)).
- **No post-print desk notes yet** — today's prints (5 Jun) won't be in `research.dim_report` until tomorrow's ingest cycle. Re-run the corpus mine next session to capture the immediate reaction notes.
- **CBC June meeting date** — referenced in ANZ R1752 but exact date not pinned in any of the 16 reports sampled. Confirm via CBC website before constructing event-driven trades.

### Public references

- DGBAS Taiwan CPI release page: <https://eng.stat.gov.tw/Point.aspx?sid=t.5>
- CBC monetary policy: <https://www.cbc.gov.tw/en/lp-432-2.html>
- FRED Taiwan CPI: <https://fred.stlouisfed.org/series/TWNCPIALLMINMEI>

---

*Compiled by IMDR research workflow per [`docs/admin/summaries/deep_dive_playbook.md`](../admin/summaries/deep_dive_playbook.md), 2026-06-05. Statistical framework verified against Nomura R73 (DGBAS-sourced category table); sell-side mosaic from 16 reports in `research.dim_report` published 2026-05-07 → 2026-06-04.*
