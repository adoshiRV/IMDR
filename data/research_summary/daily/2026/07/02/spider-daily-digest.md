---
edition: daily
date: 2026-07-02
---

# Spider — Daily Macro Research Digest

**Window:** rolling day into 2026-07-02 (flow 2026-07-01 → 2026-07-02) · **Edition:** Daily · **Universe:** AU · NZ · JP · IN · TH · ID · MY · SG · HK · PH · US · CA · UK

> FX/rates PM lens. Number-first, low-opinion. Sell-side is treated as motivated until the numbers say otherwise. Trades are surfaced with assumption + falsifier — never rated. Every table row is explained in the prose beneath it.
>
> **Grounding legend:** FACT = printed/decision (`calendar.cb_events`) · DEPTH = component series (`econ.fact_indicator`) · VIEW = sell-side interpretation (`research.fact_chunk` + Qdrant) · PRICING = market-implied · SYN = synthesis.

---

## 1. CB / macro dashboard  *(FACT — `calendar.cb_events`)*

One row per covered country. Policy rate = last decided rate on a verified decision row; last move and next event verified against `cb_events`.

| Country | Policy rate | Last move (verified) | Next scheduled | Bias / key issue |
|---|---|---|---|---|
| United States | 3.75% | Held 2026-06-17 (dots revised **up**) | NFP 07-02; FOMC minutes 07-08 | Hawkish repricing meets a dovish-tilted Warsh at Sintra (§4) |
| Japan | 1.00% | **Hiked +25bp** 2026-06-16 (from 0.75%) | S&P PMIs 07-03 | Tankan firm; USD/JPY 162+, intervention threat escalated (not executed) |
| Indonesia | 5.75% | **Hiked +25bp** 2026-06-18 (from 5.50; +25bp 06-09) | (post-window) | Inflation broadening; JPM sees further hikes to 6.00% |
| Australia | 4.35% | Held 2026-06-16 | RBA speech (Hunter) 07-08 | Neutral-rate debate; houses split hold-vs-hike-risk; OIS ~17% a hike by Aug |
| New Zealand | 2.25% | (prior decision) | **RBNZ decision 2026-07-08** | Hike-vs-hold split: ANZ +25bp Jul-8, Westpac hold→Sept (unreconciled) |
| United Kingdom | 3.75% | Held 2026-06-18 (vote 7/2/0 — **2 hike dissents**) | Bailey 07-03; services PMI 07-03 | Sticky inflation; hawkish vote drift; gilt-curve steepening thesis |
| Canada | 2.25% | Held 2026-06-10 | Business Outlook Survey 07-06 | Steady BoC; weak growth |
| India | 5.25% | Held 2026-06-05 | Services PMI 07-03 | RBI-inflows theme now the live axis; monsoon/food tail |
| Philippines | 4.75% | **Hiked +25bp** 2026-06-18 (from 4.50) | (post-window) | EM-tightening cluster; external balance improving |
| Thailand | 1.00% | Held 2026-06-24 | BoT minutes 07-08 | Soft prints; sell-side leans constructive on oil relief |
| Malaysia | 2.75% | (prior decision) | **BNM decision 2026-07-09** | "La pausa" — houses expect hold |
| Hong Kong | USD peg / LAF | — (linked to Fed) | — | Peg follows Fed; KRW/liquidity read a regional watch |
| Singapore | MAS S\$NEER band | — (band, not a rate) | **MAS review (July)** | Live: houses lean to a slight July easing (re-centre/slope) |

**SYN — state of the world:** the window sits on a hawkish-repricing base — Fed dots up (current-year projection 3.8% from 3.4%, FACT 06-17), post-hike BoJ at 1.00%, June hikes from BI and BSP — but two crosswinds appeared this window. First, **Fed chair Warsh at Sintra struck a dovish-leaning tone** ("inflation risks have come down"), reopening a two-way debate that the June dots had seemed to close. Second, **USD/JPY at 162+ pushed the intervention threat from verbal to near-imminent** (an official interview signalling "decisive action") without an executed intervention on the record. The set-piece — **US June payrolls (07-02)** — had not printed into `cb_events` at run time; the flow is a preview, not a reaction.

---

## 2. Calendar — releases + CB events with rate relevance  *(FACT — `cb_events`; pure calendar, no view)*

Consensus (`survey`/`forecast`) shown where present; `actual` shown only where the row carries one. Times UTC.

| Date | Country | Event | Consensus | Prior | Actual (if printed) |
|---|---|---|---|---|---|
| 07-01 | US | ADP employment | 105K fcst / 118K survey | 122K | not booked |
| 07-01 | US | ISM manufacturing | 53.6 fcst / 53.7 survey | 54.0 | not booked |
| 07-01 | US | ISM prices paid | 80 / 77.5 (BQL) | 82.1 | not booked |
| 07-01 | US | **Fed chair Warsh speech** (Sintra) | — | — | delivered (VIEW-covered) |
| 07-01 | JP | Consumer confidence | 34 / 32 | 33.6 | not booked |
| 07-01 | ID | CPI YoY | 3.1% / 3.2 (BQL) | 3.08% | not booked |
| 07-01 | ID | Trade balance | \$4.0B | \$0.09B | not booked |
| 07-01 | IN | HSBC mfg PMI final | 54.5 | — | not booked (declined to 3-mo low per VIEW) |
| 07-01 | UK | Bailey speech; mfg PMI final | 53.1 | 53.1 | not booked |
| **07-02** | **US** | **Non-farm payrolls** | **114K survey / 110K fcst** | 172K | **not booked at run** |
| 07-02 | US | Unemployment rate | 4.3% | 4.3% | not booked |
| 07-02 | US | Average hourly earnings MoM | 0.2% fcst / 0.3% survey | 0.3% | not booked |
| 07-02 | US | Initial jobless claims | 210K fcst / 220K survey | 215K | not booked |
| 07-02 | US | Factory orders MoM | 1.9% fcst / 2.1% survey | 4.8% | not booked |
| 07-02 | AU | Trade balance | A\$1.5B fcst / A\$2.2B survey | A\$1.791B | not booked |
| 07-02 | NZ | Building permits MoM | — | 10.9% | not booked |
| 07-02 | UK | BoE credit conditions survey; Mann speech | — | — | scheduled |
| 07-02 | CA | S&P Global mfg PMI | 53.4 | 52.9 | not booked |
| 07-02 | SG | Purchasing Managers Index | — | 51.0 | not booked |
| 07-03 | JP | S&P PMIs (composite/services) | — | 52.5 / 51.8 | forward |
| 07-03 | IN | HSBC PMIs (composite/services) | — | 57.4 / 57.3 | forward |
| 07-03 | UK | Services/composite PMI; Bailey; DMP 1y CPI exp | 48.75 / 49.4 | 48.7 / 49.4 / 3.7% | forward |
| **07-08** | NZ | **RBNZ interest-rate decision** | hold 2.25% (fcst) | 2.25% | forward |
| **07-08** | TH | BoT meeting minutes | — | — | forward |
| **07-08** | US | FOMC minutes | — | — | forward |
| **07-09** | MY | **BNM interest-rate decision** | hold 2.75% (fcst) | 2.75% | forward |

---

## 3. Cross-cutting trade-ideas table  *(VIEW / trade recommendation — provenance tagged; not judged)*

Distilled from the fresh-window fact-chunk sweep + per-theme Qdrant search. Each row is expanded in the country read.

| # | Trade | Key driver / rationale | Assumption it rests on | Falsifier | Provenance (report_id) |
|---|---|---|---|---|---|
| 1 | **Sell EUR/INR** | RBI measures drive INR inflows; lower INR vol | FCNR(B) swap / ECB-related inflows land as designed | Inflow measures stall / global risk-off hits INR | BNP FX (14665) |
| 2 | **Take profit on 5y INR NDOIS receiver** | Inflation concerns outweighed growth; move played out | Front-end has repriced enough; book it | Fresh dovish RBI shift extends the rally | Barclays EM FX & Rates (14709) |
| 3 | Constructive **INR FX + bonds** | Improving carry + narrowing C/A + RBI inflow measures | Carry holds; C/A deficit keeps narrowing | Oil re-spike widens C/A; carry erodes | Goldman (14730) |
| 4 | **Buy 10y TIPS with payer protection** | Breakevens cheap; current Fed pricing "looks hawkish" | Real yields near range-top; hawkish pricing overdone | Inflation rolls over / real yields break higher | MS US Rates (14751) |
| 5 | Antipodean rates: **higher-for-longer / hike-risk** bias | AU neutral-rate debate; OIS ~17% a hike by Aug | Sticky AU services inflation persists | Labour-market cracks re-price a cut | Nomura (14304), BofA (14544), Westpac (14363) |
| 6 | NZ: position for **start of a hike cycle** (timing split) | ANZ hike +25bp Jul-8; Westpac hold→Sept | RBNZ delivers its forecast path; oil-shock persists | Growth/oil undershoot → Governor holds | ANZ (14581), Westpac (14368) |
| 7 | **Fade the yen move** (close JPY shorts / take FX-vol profit) | Intervention threat now near-imminent; caps the tail | Mimura-signalled action deters a further leg | Disorderly break past 163 with no execution | HSBC (14595), BNP (14478) |
| 8 | HY credit: **cut duration** | Macro (rates) drives HY here, not spreads | Rate path stays the swing factor | Spread event dominates rates | Citi (14721) |
| 9 | 2H: rotate **out of S&P/secular growth into value / broadening** | Mid-year rotation; leadership broadens | Breadth improves off mega-cap | Growth momentum persists | BofA (14429/14611), Goldman (14585) |
| 10 | US 10y / duration: **stay sidelined into payrolls** | Range-bound; poor risk/reward pre-NFP | No decisive NFP break | Clean NFP beat/miss forces a break | Citi (14617/14669) |

**SYN:** the live-trade book has rotated toward an **India-inflows cluster** (rows 1-3, three houses, new this window) alongside the persistent **rates-higher / real-yield** book (rows 4, 5, 6, 8) and a **JPY-fade** into the intervention zone (row 7). The India FX/bonds trade is the freshest genuinely multi-house idea.

---

## 4. Per-country read  *(A themes · B the "why" · C consensus · D differentiated)*

Ordered by what moved this window. Flagship/desk notes read at the chunk level for the movers. Consensus (≥2 independent banks) and differentiated views separated. Trades surfaced with assumption + falsifier only.

---

### United States — hawkish base, but Warsh reopens the debate into payrolls

**A. Themes in play**

| Rank | Theme | Assets | Banks talking | Why it matters to the PM |
|---|---|---|---|---|
| 1 | **Warsh at Sintra dovish-tilted** vs the hawkish June dots | USD rates, USD | Goldman, UBS, HSBC, DB | The Fed chair reopens a two-way debate the dots had closed |
| 2 | **June payrolls (07-02)** — headline vs internals | USD rates, USD, risk | Goldman, Citi, JPM, MS | The binary event; a one-off beat over a cooling trend is the trap |
| 3 | Market has said **"farewell to Fed cuts"** (for now) | USD rates | StanC, JPM QED | The repricing is done near-term; the question is what re-opens it |
| 4 | **Core-PCE methodology change** lowers measured inflation | TIPS/BE, USD rates | Citi, Goldman, Barclays, DB | Trims measured core PCE ~0.2–0.25pp; measured ≠ true |
| 5 | **Trend inflation still hot** — one house sees hikes to 4.1% | USD rates | DB (outlier) | The differentiated tail: a hiker, not a holder |

**B. The "why" — how the houses are reasoning**

The base case is the June-17 FOMC: held at 3.75% with the **dots revised up** (current-year 3.8% from 3.4%, 1st-yr 3.6% from 3.1%; longer-run unchanged 3.1% — FACT). Market pricing followed rather than fought it: JPM's QED (14494/14897, PRICING) has US OIS pricing net tightening over the next two quarters, and StanC's Rates Alert (14703) captures the mood — "the market says farewell to Fed cuts," noting the oil impact "did not end in time to stop a hawkish shift in Fed messaging." So the near-term repricing looks complete; the live question is what re-opens the cut case.

That question got sharper this window because **Fed chair Warsh spoke at Sintra with a dovish tilt**. Goldman (14844) headlines "Warsh Says Inflation Risks Have Come Down"; UBS (14876) reads his three Sintra takeaways as not distancing himself from his prior writings on central-bank commitment to price stability; DB (14924) frames a "family fight in July, but no forward guidance." The tension a PM has to hold: the *institution's* dots are hawkish, but the *chair's* rhetoric leans the other way — a communication split that widens the distribution around the July meeting rather than narrowing it.

The set-piece is **June payrolls (07-02)** — not yet printed into `cb_events` at run time, so the flow is a preview. The split is on mechanism, not direction. Goldman (14893) is above consensus at **+130k vs 115k**, attributing ~+40k to a World Cup boost and flagging it lands below the breakeven threshold. Citi (14669) works the cross-market angle, seeing unemployment drifting to 4.6-4.7% by late summer and positioning for € underperformance on any USD-supportive print. The bear internals — soft hiring beneath a firm headline (Citi 14772 "low hiring continues," 14835 manufacturing employment only "modestly" improving) — set up the classic print-vs-trend disagreement.

The sleeper remains the **core-PCE methodology change**: Citi (14437) calls it "a big deal" that mechanically lowers 12m core PCE (3.4% in May) by ~25bp via re-measured portfolio-management-services prices; Goldman pegs the net at ~-0.2pp; Barclays (14371) frames the identical BEA revision as "just a measurement refinement." The wedge between measured and true inflation is the PM-relevant point. Against all of it, DB (14516) is the lone hiker — trend-inflation overshoot "significantly surpasses pre-pandemic," Fed funds to **4.1%** then hold.

**C. Consensus views (≥2 independent banks)**

| Theme | Banks | Shared claim | Evidence cited | What consensus is missing (grounded) |
|---|---|---|---|---|
| Near-term repricing done; no imminent cut | JPM, StanC, Citi | "Farewell to Fed cuts"; curve prices net hikes | Dots up (FACT); OIS net-tightening (14494/14897); "hawkish shift" (14703) | Under-weights Warsh's dovish tilt (14844/14876) — the chair cuts against the dots |
| Payrolls: headline could beat, internals cooling | Goldman, Citi, MS | Look through a possible one-off to soft hiring | GS +130k on World Cup (14893); low hiring (14772); U/E drift to 4.6-4.7% (14669) | The 07-02 actual is not in `cb_events` — the consensus is pre-print |
| Core-PCE revision lowers measured inflation | Citi, Goldman, Barclays, DB | Methodology change trims core PCE ~0.2–0.25pp | BEA Sep-30 retroactive change; portfolio-mgmt re-measure (14437/14557/14371) | Splits on "big deal" (Citi) vs "refinement" (Barclays) — see D |

**D. Differentiated / unique views**

| Bank | Asset | The view | Why it's different | Hidden assumption | Falsifier |
|---|---|---|---|---|---|
| DB (14516) | USD rates | Fed **hikes to 4.1%** then holds | Only in-window house modelling *more* hikes | Energy shock feeds a persistent, broad trend-inflation overshoot | A clean disinflation print / labour break |
| Goldman (14844) | USD rates, USD | Reads **Warsh as dovish-tilted** ("risks have come down") | Elevates the chair's tone over the institution's dots | The chair's rhetoric leads the reaction function | July meeting delivers a hawkish hold |
| MS (14751) | TIPS/BE | **Buy 10y TIPS + payer protection** — Fed pricing "looks hawkish" | Fades the hawkish rate pricing while staying long breakevens | Real yields near range-top; hawkish pricing overdone | Real yields break higher on a hot print |
| Citi (14437) | TIPS/BE | PCE methodology change is **"a big deal"** (−25bp) | Elevates a measurement wrinkle to a Fed-path input | The Fed reacts to the measured series | Fed explicitly looks through the revision |
| Barclays (14371) | USD rates | Same revision is **"just a refinement"** | Directly downplays the Citi/Goldman read on identical data | Underlying momentum unchanged; optics ≠ policy | Fed cites the lower print as easing cover |

*Trade rows expanded:* #4 (MS buy 10y TIPS + payer protection — see D). #9 (BofA/Goldman 2H rotation out of S&P/secular growth into value/broadening; assumption = breadth improves; falsifier = growth momentum persists). #10 (Citi stay sidelined in US 10y into NFP; assumption = the range holds; falsifier = a clean NFP break). Surfaced, not judged.

**Not loaded / flag:** US June-payrolls, AHE, claims and factory-orders actuals are not booked in `cb_events` at run (survey/consensus only). US `econ.fact_indicator` is deep (140 indicators, latest 06-29) — component labour/ISM detail was used.

---

### Japan — firm Tankan, yen at the intervention line

**A. Themes in play**

| Rank | Theme | Assets | Banks talking | Why it matters to the PM |
|---|---|---|---|---|
| 1 | **USD/JPY 162+ → intervention threat near-imminent** | JPY, JGB, FX vol | Nomura, Citi, SocGen, HSBC, BNP | Post-hike currency *weaker*; an official signalled "decisive action" |
| 2 | **June Tankan** supports faster/earlier hikes | JGB, JPY, Japan equity | Goldman, DB, JPM, MS, Nomura, Citi, UBS, Barclays | The hike-path validator; BoJ DI rose (see reconciliation) |
| 3 | Positioning: **fade the yen move vs press it** | JPY crosses, FX vol | HSBC/BNP (fade) vs Citi (continuation); SocGen (reversal) | The tradeable split is on positioning, not direction |
| 4 | Inflation expectations rising (1/3/5y +0.1pt to ~2.7%) | JGB, BE | JPM, MS, Nomura | Feeds the "earlier hike" case; JGB curve steepening |

**B. The "why" — how the houses are reasoning**

BoJ **hiked to 1.00%** on 06-16 (FACT). The window's dominant tension is that a central bank which just hiked has a currency at a **40-year low, USD/JPY 162+**. The escalation this window is verbal, not executed: Nomura (14752) reads an interview by **Mimura** as signalling that "intervention could [come]" and that the timing for "decisive action" was "drawing near" — an official pushing the threat toward imminence without an intervention on the record. SocGen (14702) frames it as "2024 trauma all over again for Yen shorts" and, tellingly, sets its FY26 USD/JPY forecast at **152.57** — i.e. it forecasts a *reversal* from spot, a differentiated mean-reversion call. Citi (14583) stays on the other side: "nobody stopping yen depreciation."

The Tankan (06-30) is the hike-path validator, and the near-unanimous read is that it supports *faster* tightening — but the reconciliation matters. Houses lean on the **BoJ business-conditions diffusion index, which rose**: Goldman (14586) has large-manufacturers DI at **+37 (Mar +36), the fifth consecutive quarterly improvement**, with FY2026 capex "revised up sharply"; DB (14624) says rising price pressures "support faster BoJ rate hikes"; Barclays (14607) says it reinforces its **October hike** call; Nomura's full review (14948) says the survey "justifies" the hike path via inflation forecasts. JPM (14643) notes the all-firms index was *unchanged* but "the strongest corporate momentum in decades remains intact," with **1/3/5yr-ahead inflation expectations all +0.1pt to ~2.7%** — the leg that turns a sentiment survey into a rates catalyst. UBS (14759) and Citi (14668) corroborate "solid corporate sentiment / resilient price outlook."

The tradeable split is on **positioning near the intervention line**. HSBC (14595) is *closing* its short SGD/JPY, still seeing "an intervention threat present"; BNP (14478) is *taking profit* on a USD/JPY call structure with spot near 163, expecting official forces to lean against the top of the range. Both fade the easy money, against Citi's continuation and with SocGen's outright reversal forecast on the other extreme.

**C. Consensus views (≥2 independent banks)**

| Theme | Banks | Shared claim | Evidence cited | What consensus is missing (grounded) |
|---|---|---|---|---|
| Tankan supports faster/earlier hikes | Goldman, DB, JPM, MS, Nomura, UBS, Citi, Barclays | Firm sentiment + capex + rising price/expectations DIs = hike cover | DI +37 (14586); "faster hikes" (14624); infl-exp +0.1pt to 2.7% (14643); "justifies" path (14948) | The `cb_events` TE headline "large-mfg index 16 vs 17" *fell* — a different series than the BoJ DI (see flag) |
| USD/JPY weak → intervention now near-imminent | Nomura, Citi, SocGen, HSBC | Spot 162+; official signalling "decisive action" | Mimura interview (14752); "nobody stopping" (14583); "2024 trauma" (14702) | No executed intervention on the record — the escalation is verbal only |

**D. Differentiated / unique views**

| Bank | Asset | The view | Why it's different | Hidden assumption | Falsifier |
|---|---|---|---|---|---|
| SocGen (14702) | USD/JPY | FY26 forecast **152.57** — a reversal from 162+ spot | Outright mean-reversion call vs the depreciation consensus | Intervention + 2024-style squeeze reverses yen shorts | Rate differential dominates; spot grinds past 163 |
| Barclays (14607) | JGB | Explicit **October hike** call, reinforced by Tankan | Puts a date on the next hike where others stay directional | Tariff/autos drag (the weak DI spot) stays contained | Autos/export DIs roll over → BoJ delays |
| HSBC (14595) / BNP (14478) | JPY crosses / FX vol | **Fade the yen move** (close short / take profit) | Books gains where the tape says "new higher range" | Intervention threat caps further downside near-term | Disorderly break past 163 with no execution |
| Citi (14583) | JPY | "**Nobody stopping**" the depreciation (continuation) | Directly opposite the fade and the SocGen reversal | Rate differential dominates; jawboning is empty | Actual intervention / a hawkish BoJ surprise |

**Unreconciled:** TE "Tankan large-mfg index 16 vs 17" (`cb_events` row 21708, a dip) vs the BoJ business-conditions **DI ~+37 that improved** (cited by every house) — different cuts of the survey; both shown, neither silently chosen. The house-cited DI drives the hike narrative. **Intervention:** signalled/near-imminent per Mimura interview, **not executed** on the record. **Not loaded:** JP `econ.fact_indicator` is effectively absent (1 obs) — all JP numbers are `cb_events` prints or sell-side.

---

### Indonesia — inflation broadening; a further-hike call emerges  *(INSTRUMENT PENDING DEEPAK)*

**A. Themes in play**

| Rank | Theme | Assets | Banks talking | Why it matters to the PM |
|---|---|---|---|---|
| 1 | **Inflation rising and broadening** in June | IDR, IDR rates | JPM, Nomura, Goldman | Shifts the story from fuel-only to broad-based; feeds more hikes |
| 2 | **BI reaction function: further hikes to 6.00%** | IDR rates | JPM (differentiated) | A named terminal above spot policy — a real path call |
| 3 | **Large swing to a May trade deficit** | IDR, C/A | JPM | External balance deteriorating alongside inflation — a squeeze |

**B. The "why" — how the houses are reasoning**

BI **hiked twice in June** (to 5.50% on 06-09, 5.75% on 06-18 — FACT), a currency-defence reaction function. This window sharpened the inflation read from "fuel-only" to broad-based. JPM (14806) reports June headline inflation rose to **0.4% m/m, ~2.9% oya from 0.8%**, with the pickup "rising and broadening" beyond administered/volatile items, and — the differentiated leg — expects BI to **hike further to 6.00% this month, with risks of additional hikes**. Nomura (14819) independently flags inflation "accelerated in June," and Goldman (14633) attributes the initial impulse to higher unsubsidised fuel prices (transport, food & beverage). The complication JPM adds (14862) is a **large swing to a May trade deficit** — a deteriorating external balance stacking on top of the inflation pickup, which is precisely the squeeze that forces a currency-defending central bank to keep tightening.

**C. Consensus views (≥2 independent banks)**

| Theme | Banks | Shared claim | Evidence cited | What consensus is missing (grounded) |
|---|---|---|---|---|
| Inflation accelerated/broadened in June | JPM, Nomura, Goldman | June CPI rose and broadened beyond fuel | 0.4% m/m, 2.9% oya (14806); "accelerated" (14819); fuel impulse (14633) | The 07-01 CPI actual is not booked in `cb_events` — the read is sell-side-reported |

**D. Differentiated / unique views**

| Bank | Asset | The view | Why it's different | Hidden assumption | Falsifier |
|---|---|---|---|---|---|
| JPM (14806) | IDR rates | BI **hikes to 6.00% this month**, more to come | Names a terminal above current policy; a path call, not a description | Broadening inflation + weak external balance force continued defence | Core CPI stabilises / rupiah steadies → BI pauses |
| Goldman (14633) | IDR rates / BE | June uptick is **fuel/cost-push** in origin | Isolates the source where others emphasise the currency | The fuel impulse is supply-side; hikes don't address it | Demand-pull broadening validates the hikes |

**Puzzle fit:** currency-defence reaction function + broadening inflation + deteriorating external balance. **No Spider instrument is named** (SRBI vs IDR rates vs govvies) — JPM's earlier reference to "SRBI yields at high levels" is an observed market condition only; the "use the bonds" instruction remains **PENDING DEEPAK**. **DEPTH:** ID `econ.fact_indicator` reasonably deep (91 indicators, latest 06-26) — CPI component follow-up available once the print books.

---

### Australia — the "quiet tightening" debate over a static cash rate

**A. Themes in play**

| Rank | Theme | Assets | Banks talking | Why it matters to the PM |
|---|---|---|---|---|
| 1 | RBA **neutral-rate** debate (June minutes) | AUD rates, front-end | Nomura, BofA, Westpac, JPM | Re-frames whether 4.35% is neutral, tight, or easy |
| 2 | Is a static 4.35% actually **tightening**? (opposite mechanisms) | AUD rates, AUD | BofA (short-run neutral falls) vs Nomura (long-run neutral up) | Same "tight" conclusion, opposite mechanism |
| 3 | **Sticky services/domestic inflation** vs soft tradables | AUD rates, ACGB | Westpac, BofA + ABS depth | Why the Board is "still on edge"; corroborated by the CPI mix |
| 4 | **Two-speed housing** — firm credit, falling prices | AUD, banks, ACGB | ANZ, UBS, Goldman, MS | Complicates the tightening story; credit ~8% YoY, prices down |

**B. The "why" — how the houses are reasoning**

RBA **held 4.35%** (06-16); the June minutes (06-30, FACT) frame a reaction-function debate. Read in full, the houses disagree on the *mechanism* while landing on "tight for longer." Nomura (14304) reads a **higher long-run neutral** ("a hawkish thought"), frames terminal ~4.10%, but stresses the board "did not specifically consider a hike," the neutral note "related to the tightness of policy," and keeps its profile **unaltered (no further hikes, 4.35% into end-2026)** — a careful read, not a hawkish one. BofA's "Quiet Tightening" (14544) runs the opposite mechanism: the **short-run (cyclical) neutral rate is *falling***, so a pinned 4.35% is passively getting tighter through yields, borrowing costs and housing credit — first cut pushed to **August 2027**, risks "skewed to another hike." Westpac (14363) sits between, a Board "still on edge about inflation." Pricing corroborates the tilt without an imminent hike: Westpac's What's-Priced-In (14364/14704, PRICING) has only ~**17% of a hike** by 11-Aug, ~32% by end-Sep.

The ABS data does the work. Latest monthly CPI (May, DEPTH): **headline 4.0% YoY, trimmed mean 3.6%, weighted median 3.6%**, persistence in **housing +6.5%, electricity +21.1%, rents +3.6%, services 3.7%** vs tradables only +2.5% — the domestic/services stickiness behind "on edge." Housing is two-speed: Cotality 5-capital drifted **down** through late June (Sydney/Melbourne leading; ANZ 14603/14705, UBS 14650 flag the downturn), yet private-sector credit ran **+0.7% MoM / ~8% YoY** (Goldman 14245). Building/dwelling approvals mixed-to-soft (Goldman 14590, MS 14648, Westpac 14653, JPM 14641). Firm credit, soft prices — the exact channel BofA's thesis leans on.

**C. Consensus views (≥2 independent banks)**

| Theme | Banks | Shared claim | Evidence cited | What consensus is missing (grounded) |
|---|---|---|---|---|
| RBA effectively tight; no near-term cut | Nomura, BofA, Westpac | Stance restrictive; cuts distant | June minutes neutral-rate language; OIS ~17% a hike by Aug (14364) | They disagree on *why* neutral shifted — "tight" hides opposite mechanisms (see D) |
| Inflation still the binding constraint | Westpac, BofA | Domestic/services inflation keeps the Board cautious | Trimmed mean 3.6%, services 3.7%, electricity +21.1% (ABS DEPTH) | Tradables at 2.5% — goods-side disinflation is real; under-weighted |
| Housing softening but credit resilient | ANZ, UBS, Goldman, MS | Prices down, approvals soft, credit ~8% | Cotality down; credit +0.7% mom (14245); approvals mixed (14590/14648) | No one reconciles falling prices with +8% credit — tension left open |

**D. Differentiated / unique views**

| Bank | Asset | The view | Why it's different | Hidden assumption | Falsifier |
|---|---|---|---|---|---|
| BofA (14544) | AUD rates | "**Quiet tightening**": short-run neutral *falls*, static 4.35% passively tightens; first cut Aug-2027, risks to a hike | Opposite mechanism to Nomura — cyclical neutral dropping, not long-run rising | Transmission via yields/housing credit does the tightening the RBA won't | Neutral re-rises / demand re-accelerates → stance turns easy |
| Nomura (14304) | AUD rates | Minutes flag **higher long-run neutral**, but **no hike** — profile unaltered | Reads the hawkish nuance yet holds its call; board "did not consider" a hike | The neutral note is about tightness, not a signal to move | Board actually contemplates a hike at a coming meeting |

*Trade row expanded:* #5 (antipodean higher-for-longer / hike-risk bias; assumption = sticky services inflation keeps the stance restrictive; falsifier = labour cracks re-price a cut). Provenance Nomura/BofA/Westpac — note the two lead houses reason from *opposite* neutral-rate mechanisms.

---

### New Zealand — RBNZ Jul-8: a live hike-vs-hold split

**A. Themes in play**

| Rank | Theme | Assets | Banks talking | Why it matters to the PM |
|---|---|---|---|---|
| 1 | **RBNZ Jul-8** — hike now or hold to September | NZD rates, NZD, NZGB | ANZ (hike), Westpac (hold) | Binary, imminent; the two lead local houses disagree on the meeting |
| 2 | RBNZ has a **pre-committed hike path** (its own forecast) | NZD rates | ANZ, Westpac | The question is timing, not direction |
| 3 | **Oil-shock persistence** as the swing factor | NZD rates, BE | ANZ, Westpac | Governor's May off-ramp was oil/growth-conditional |

**B. The "why" — how the houses are reasoning**

OCR **2.25%**; the **RBNZ decision is 2026-07-08** (FACT, forward). The two lead NZ houses land on opposite calls for the meeting. **ANZ (14581, refreshed pricing 14880)** expects **+25bp to 2.50% at Jul-8** ("let's get started"): the Committee "was already planning on lifting the OCR," risks tilted to neutral being higher, core/wage pressure predates the Middle East conflict, and the oil-shock component is "fairly persistent and worth maybe +30bp on the TWI." **Westpac (14368)** reads the *same* Governor and expects a **hold at 2.25%, lift-off September**: the May release was "more conditional," the Governor said "if we see oil prices falling really much more than expected… we may not hike," the quick Iran de-escalation removes urgency, and Jul-8 is only a review (not a full Statement) — a natural spot to wait. Pricing sits nearer ANZ: ANZ's What's-Priced-In carries **~+17-19bp into Jul-8**, a curve to **~2.83 by December**; the `cb_events` forecast still tags a hold. Business confidence firming (ANZ 14237; Westpac 14262/14955 building consents) supports the direction.

**C. Consensus views (≥2 independent banks)**

| Theme | Banks | Shared claim | Evidence cited | What consensus is missing (grounded) |
|---|---|---|---|---|
| RBNZ is on a hiking path (direction agreed) | ANZ, Westpac | The OCR is going up; only the timing is in question | May MPS guidance; oil-shock persistence; firming confidence (14237/14262) | They do **not** agree on the Jul-8 meeting itself — direction-consensus hides a timing split (see D) |

**D. Differentiated / unique views**

| Bank | Asset | The view | Why it's different | Hidden assumption | Falsifier |
|---|---|---|---|---|---|
| ANZ (14581) | NZD rates, NZD | **Hike +25bp to 2.50% at Jul-8** | Calls the hike now, at a review, ahead of the market | Committee delivers its path; oil-shock ~+30bp TWI persists | Growth/oil undershoot → Governor invokes his off-ramp |
| Westpac (14368) | NZD rates | **Hold Jul-8; lift-off September** | Reads the same Governor as more conditional; waits for data | Iran de-escalation + data-review argue for patience | RBNZ hikes Jul-8 anyway → Westpac a meeting late |

**Unreconciled:** three readings of Jul-8 coexist — ANZ hike / Westpac hold→Sept / `cb_events` forecast hold. All shown. **Not loaded:** NZ `econ.fact_indicator` thin (46 indicators, latest 05-31) — sanity-check only.

---

### United Kingdom — sticky inflation, hawkish dissent, a steepening gilt curve

**A. Themes in play**

| Rank | Theme | Assets | Banks talking | Why it matters to the PM |
|---|---|---|---|---|
| 1 | **Inflation shocks steepen the gilt curve** (UK most exposed) | Gilts, linkers, GBP | UBS | The differentiated rates thread; quantified curve response |
| 2 | BoE **hawkish vote drift** (2 hike dissents) + firm GDP | Gilts, GBP | BoE (FACT); speaker-heavy window | Vote split + growth support a higher-for-longer front end |
| 3 | **Leadership transition** communication risk | Gilts, GBP | UBS | A UK-specific institutional overhang into the July path |

**B. The "why" — how the houses are reasoning**

BoE **held 3.75%** on 06-18 with a **7/2/0 vote — two members dissenting to hike** (FACT; prior 8-1). The hawkish *drift* is the signal. The window is speaker-heavy — Bailey (07-01, 07-03), Mann (07-02), credit-conditions survey (07-02), the DMP 1y CPI-expectations series (07-03, prior 3.7%) — and final Q1 GDP confirmed a firmer **+0.6% QoQ / +1.1% YoY**, removing the growth alibi for cuts. UBS supplies the differentiated content: "Inflationary shocks steepen the gilt curve" (14426) models the UK curve response to a 1ppt inflation shock and finds it more front-end-driven than peers, with the **UK carrying the highest inflation-linked debt share** — so an inflation shock transmits harder into UK rates and fiscal. The companion "Simply UK: The Gilt Trip" (14310) carries the thesis cross-asset, and UBS's UK-leadership-transition note (14824) adds an institutional overhang to watch into the July path.

**C. Consensus views (≥2 independent banks)**

*None cleared the ≥2-independent-bank bar in-window.* UK flow was dominated by the BoE mechanics (FACT) and a single differentiated house (UBS) on the gilt curve. Stated as low-n rather than manufacturing a consensus row.

**D. Differentiated / unique views**

| Bank | Asset | The view | Why it's different | Hidden assumption | Falsifier |
|---|---|---|---|---|---|
| UBS (14426) | Gilts, linkers | **Inflation shocks steepen the gilt curve**; UK most exposed via high linker share | Quantifies a UK-specific curve response tied to the index-linked debt structure | An inflation shock is the operative risk; front-end whiplash leads | A disinflation surprise / flight-to-quality bull-flattening |
| UBS (14310) | UK equity / cross-asset | "**The Gilt Trip**" — carries the steepening thesis into equity positioning | Bridges the rates call into equity strategy | Gilt-curve dynamics dominate the UK equity risk premium | Rates stabilise; equity read decouples from the curve |

**Not loaded:** UK `econ.fact_indicator` thin (1 indicator, latest 06-02) — vote split and GDP are `cb_events` prints.

---

### India — the RBI-inflows theme goes live

**A. Themes in play**

| Rank | Theme | Assets | Banks talking | Why it matters to the PM |
|---|---|---|---|---|
| 1 | **RBI measures drive INR inflows** (FCNR(B) swap, ECB-related) | INR, IGB | BNP, Barclays, Goldman | A three-house FX/bonds cluster — the freshest tradeable theme |
| 2 | **Fiscal improvement** on a record RBI dividend | INR rates, IGB | Goldman, Nomura, MS | Eases govvie supply pressure |
| 3 | **Monsoon/food-inflation tail** (weak start, El Niño) | INR rates, BE | MS, Citi, JPM | The main inflation risk to the on-hold RBI |

**B. The "why" — how the houses are reasoning**

RBI **held 5.25%** (06-05). The theme that went live this window is **INR inflows**: BNP (14665), Barclays (14709) and Goldman (14730) independently build off RBI measures — the FCNR(B) swap facility and ECB-related steps — that are designed to draw inflows, lower INR volatility, and make bond inflows "less FX-hedged." BNP expresses it as **sell EUR/INR**; Barclays *takes profit* on a 5y INR NDOIS receiver, judging inflation concerns "outweighed growth" and the move played out; Goldman turns **constructive on INR FX and bonds** on "attractive carry and improving fundamentals," having narrowed its current-account-deficit forecast. That is a genuine multi-house convergence on the same flows mechanism, from three different expressions.

The supporting fiscal positive persists — a May surplus/improvement on a record RBI dividend (Goldman 14492, Nomura 14467, MS 14466) — easing govvie supply. The offsetting risk is monsoon/food: MS (14301) flags the June rainfall deficit at a 12-year high, Citi (14482) and JPM (14747) work the El Niño / food-inflation channel. HSBC mfg PMI declined to a 3-month low but "still solid" (Goldman 14675); services/composite PMIs land 07-03. So: a fiscal-positive, inflows-supported backdrop with a food-inflation tail — a constructive INR story with a clear negative catalyst to monitor.

**C. Consensus views (≥2 independent banks)**

| Theme | Banks | Shared claim | Evidence cited | What consensus is missing (grounded) |
|---|---|---|---|---|
| RBI measures support INR inflows / bonds | BNP, Barclays, Goldman | Inflow measures → constructive INR + bonds | FCNR(B) swap / ECB-related (14665/14709); carry + narrower C/A (14730) | Assumes measures land as designed and global risk stays benign |
| Fiscal improved in May | Goldman, Nomura, MS | Deficit narrowed / surplus on record RBI dividend | May fiscal + RBI dividend (14492/14467/14466) | A one-off dividend flatters the run-rate |
| Monsoon/food is the inflation risk | MS, Citi, JPM | Weak monsoon + El Niño = food-price upside | Rainfall deficit 12-yr high (14301); El Niño (14482/14747) | Not yet in the CPI print — IN DEPTH available to track it |

**D. Differentiated / unique views**

| Bank | Asset | The view | Why it's different | Hidden assumption | Falsifier |
|---|---|---|---|---|---|
| Barclays (14709) | INR rates | **Take profit** on 5y INR NDOIS receiver | Says the receiver move is done where others are still adding INR risk | Front-end has repriced enough; inflation concerns capped it | A fresh dovish RBI shift extends the rally |
| Goldman (14730) | INR FX + bonds | **Constructive** on carry + improving fundamentals | Broadest cross-asset INR-bull expression | Carry holds; C/A keeps narrowing | Oil re-spike widens C/A; carry erodes |

*Trade rows expanded:* #1 (BNP sell EUR/INR), #2 (Barclays take-profit INR NDOIS receiver), #3 (Goldman constructive INR FX+bonds) — see A/D. Surfaced, not judged. **DEPTH:** IN deep (279 indicators, latest 06-29) — food/CPI component follow-up (incl. fresh-food nowcaster) available for the monsoon tail.

---

### Thailand — soft prints, but the sell-side leans constructive

**A. Themes in play**

| Rank | Theme | Assets | Banks talking | Why it matters to the PM |
|---|---|---|---|---|
| 1 | **Data soft, houses lean constructive** (the tension) | THB rates, THB | JPM, Barclays, BofA | Print vs narrative disagree — the spot to interrogate |
| 2 | **Oil-price relief → GDP** channel | THB rates, BE | BofA | Differentiated growth-positive mechanism from lower energy |
| 3 | **Energy shock → corporate margins** | THB equity, credit | HSBC, UBS | Cross-checks the oil story from the margin side |

**B. The "why" — how the houses are reasoning**

BoT **held 1.00%** (06-24); minutes 07-08 (FACT). Hard data was soft — private consumption -2.1% MoM, private investment -5% MoM, current account -\$7.6B (FACT). Yet the sell-side leans constructive on the *outlook*: JPM (14528) "investment-led growth gains momentum in May," Barclays (14370) "modest rebound," BofA both "limited recovery" (14545) and "GDP relief from lower oil prices and AI wave" (14548). HSBC (14562) and UBS (14828) work the energy-shock-to-margins angle. The logic that permits constructiveness over soft prints is forward-looking: lower oil improves the terms of trade and current account, and an AI/investment cycle supports capex — so the desks look through the weak May consumption/investment reads. Nomura's Asia-rates note (14421) references a Thailand rates position with a defined ~10bp stop.

**C. Consensus views (≥2 independent banks)**

| Theme | Banks | Shared claim | Evidence cited | What consensus is missing (grounded) |
|---|---|---|---|---|
| Soft now, stabilising ahead | JPM, Barclays, BofA | Look through weak May data to a firmer outlook | "Investment-led momentum" (14528); "modest rebound" (14370); "limited recovery" (14545) | Hard data (consumption -2.1%, investment -5%, C/A -\$7.6B) is unambiguously weak now — the constructive read is a forecast |

**D. Differentiated / unique views**

| Bank | Asset | The view | Why it's different | Hidden assumption | Falsifier |
|---|---|---|---|---|---|
| BofA (14548) | THB rates / macro | **Oil relief + AI wave lift GDP** | Names a specific positive mechanism where others say "stabilising" | Lower oil sustains; the AI/investment cycle broadens | Oil re-spikes / investment cycle stalls |

**Not loaded:** TH has no in-window `econ.fact_indicator` rows — all numbers are `cb_events` prints or sell-side.

---

### Singapore — MAS review live; a slight-easing lean

**A. Themes in play**

| Rank | Theme | Assets | Banks talking | Why it matters to the PM |
|---|---|---|---|---|
| 1 | **MAS July review** — a close call, lean to slight easing | SGD NEER, SGS | Barclays, Nomura, Citi | The live regional CB event; band re-centre/slope in play |

**B. The "why" — how the houses are reasoning**

MAS runs the S\$NEER band, not a policy rate. This window it became a live event: three houses previewed the July review and converge on a **close call with a lean to slight easing**. Citi (14962) still expects a July slight easing (re-centre/slope), with inflation concerns "centred less on the level" and export prices/volumes the growth swing factor. Barclays (14656) frames it "a close call between near-term inflation [and growth]." Nomura (14815) sees "a possible" tentative easing. SIPMM PMI (07-02, prior 51.0) and bank-lending/property prints fill the data backdrop. Consensus direction (slight easing) with genuine two-sidedness on whether MAS moves in July at all.

**C. Consensus views (≥2 independent banks)**

| Theme | Banks | Shared claim | Evidence cited | What consensus is missing (grounded) |
|---|---|---|---|---|
| MAS July: close call, lean slight easing | Barclays, Nomura, Citi | A modest re-centre/slope easing is the base case | "Close call" (14656); "possible tentative" (14815); "still expect July slight easing" (14962) | The review date/outcome is forward — no MAS decision row in `cb_events` yet |

**Not loaded:** SG has no in-window `econ.fact_indicator` rows; the MAS band is not a `cb_events` policy-rate row.

---

### Canada — steady BoC, growth the question

BoC **held 2.25%** (06-10, FACT); Macklem spoke 07-01, Business Outlook Survey + Consumer Expectations land 07-06. Monthly GDP (06-30) consensus **+0.4% MoM** rebounding from -0.1% prior. BofA's mid-year (14376) is "Weak growth, steady BoC" — the frame is no urgency either way; nothing differentiated cleared the bar in-window. **Not loaded:** CA `econ.fact_indicator` absent (no in-window rows) — as expected for CA.

---

### Philippines — a quiet hike, external balance improving

BSP **hiked +25bp to 4.75%** on 06-18 (from 4.50%, FACT) — part of the June EM-tightening cluster with ID and PH. In-window: trade deficit narrowed in May (JPM 14291), exports +6.3% YoY, PPI +2.4%. Thin flow; filed as EM-tightening + external-balance improvement. **Not loaded:** no in-window `econ.fact_indicator` rows.

---

### Malaysia — BNM Jul-9 preview, "La pausa"

OPR **2.75%**; **BNM decides 2026-07-09** (FACT, forward). HSBC's preview (14288) is "La pausa" — houses expect a hold; JPM's Malaysia note (14748) is equity-angled. M3 ~5% YoY. Calendar-driven into next week. **Not loaded:** no in-window `econ.fact_indicator` rows.

---

### Hong Kong — peg follows Fed

USD-linked (no independent policy rate; rides US pricing via the peg/LAF). Regional read this window is Korea liquidity/KRW-tightening (Goldman 14778, country_id tagged HK) rather than anything HK-domestic. HK `econ.fact_indicator` exists (19 indicators, latest 06-03) but nothing rate-relevant moved. Peg-follows-Fed; no differentiated HK flow.

---

## 5. Grounding ledger  *(SYN)*

- **Rates / decisions / surprises → `calendar.cb_events`** (BQL → TradingEconomics), window 2026-07-01→07-03. Verified decision rows: RBA 4.35% (06-16 hold), BoJ 1.00% (06-16 hike), BI 5.75% (06-09 & 06-18 hikes), BSP 4.75% (06-18 hike), RBI 5.25% (06-05 hold), BoE 3.75% (06-18 hold, 7/2/0), Fed 3.75% (06-17 hold, dots up); RBNZ (07-08) and BNM (07-09) forward.
- **Component depth → `econ.fact_indicator`:** deep IN (279) / AU (215) / US (140) / ID (91); thin NZ (46) / HK (19) / UK (1); no in-window rows CA / JP / TH / MY / SG / PH. Latest obs 06-29 (IN/AU/US), 06-26 (ID).
- **Views / trades / quotes → `research.fact_chunk` + Qdrant (`research_gemini_embedding_2_3072d`) + ingested Outlook bodies:** 376 in-window reports across 13 vendors (all `source_type=research`; portal + desk/email bodies). Movers read at chunk level. Per-theme semantic sweeps: JPY/intervention, Warsh/Sintra, US payrolls, JP Tankan DI, US core-PCE, RBNZ Jul-8, AU neutral rate, Indonesia inflation, India inflows, MAS.
- **Unreconciled:** (a) JP Tankan — TE "large-mfg index 16 vs 17" (`cb_events`) vs BoJ business-conditions **DI ~+37** (house-cited); both shown. (b) NZ Jul-8 — ANZ hike / Westpac hold→Sept / `cb_events` forecast hold; all three shown. (c) AU neutral rate — Nomura (long-run up, no hike) vs BofA (short-run falls, quiet tightening) reach "tight" via opposite mechanisms. (d) US core-PCE revision — Citi "big deal" vs Barclays "refinement" on identical BEA data.
- **Not loaded / pre-print:** US June payrolls / AHE / claims / factory orders — survey/consensus in `cb_events`, actuals not booked at run. ID / JP / AU June-print actuals for 07-01/02 not booked; sell-side-reported figures tagged as such.
- **Japan intervention:** signalled near-imminent (Mimura interview, Nomura 14752) — **not executed** on the record.
- **Indonesia instrument:** no Spider instrument named — **PENDING DEEPAK**.
- **Differentiated-view count (§4.D):** US 5 · JP 4 · Indonesia 2 · AU 2 · NZ 2 · UK 2 · India 2 · Thailand 1 = **20 rows across 8 countries.** Quiet countries (CA / PH / MY / HK) carry honest short reads; SG carries a single consensus theme (MAS).
