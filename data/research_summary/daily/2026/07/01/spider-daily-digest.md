# Spider — Daily Macro Research Digest (DRAFT)

**Window:** 2026-06-30 → 2026-07-02 (rolling day around 2026-07-01) · **Edition:** Daily · **Slices run:** dashboard + calendar + trade ideas + per-country read · **Status:** DRAFT / demo cut

> Read from an FX/rates PM chair. Number-first, low-opinion. Sell-side is treated as motivated until the numbers say otherwise. Trades are surfaced — never judged. Every table row is explained in the prose below it.
>
> **Grounding legend:** FACT = printed/decision (`calendar.cb_events`) · DEPTH = component series (`econ.fact_indicator`) · VIEW = sell-side interpretation (`research.fact_chunk` + Qdrant) · PRICING = market-implied · SYN = my synthesis.
>
> **Run flags (read first):**
> - **Window is partly forward-looking.** As of ingest, `cb_events` for this window carries `survey`/`forecast`/`prior` but many `actual` fields are still null (e.g. US NFP row 21819 shows survey 114K / forecast 110K / prior 172K, actual null). Where I cite an "actual" I say so and give the source row; where only a survey exists I tag it PRICING/consensus, not a print.
> - **Research corpus in-window runs 2026-06-30 → 2026-07-01.** No 2026-07-02 sell-side rows were ingested at run time (408 reports across 13 vendors, latest publish_date 2026-07-01). The Jul-2 US payrolls/factory-orders reactions are therefore calendar-only, not yet in the note flow.
> - **Qdrant semantic layer IS up** (127.0.0.1:6333, collection `research_gemini_embedding_2_3072d`); per-theme semantic sweeps were run and reconciled against the SQL scan. For the six mover countries the flagship/desk notes were read **in full at the chunk level** (not off titles) — see §5 for the report list. `retrieve.py` needs `PYTHONUTF8=1` to avoid a cp1252 crash on box-drawing chars (playground-tooling nit, not promoted).
> - **econ depth is uneven and I do not fake it:** deep AU/US/IN/ID/HK, thin NZ/UK, effectively absent JP/CA (1 obs each) and TH/MY/SG/PH (no in-window rows). Country reads flag this inline.
> - **Indonesia instrument: PENDING DEEPAK.** The "use the bonds" instruction (SRBI vs IDR-rates vs govvies) is *not* wired. ID views below are described at the theme level only; no instrument is asserted.

---

## 1. CB / macro dashboard  *(FACT — `calendar.cb_events`)*

One row per covered country. Rate = last decided policy rate verified against a real decision row; "last move" and "next" verified against event rows in `cb_events`.

| Country | Policy rate | Last move (date, verified) | Next scheduled | Bias / key issue |
|---|---|---|---|---|
| United States | 3.75% | Held 2026-06-17 (dots revised **up**) | FOMC minutes 07-08 | Hawkish repricing; market prices net **hikes**, not cuts (see §3) |
| Japan | 1.00% | **Hiked +25bp** 2026-06-16 (from 0.75%) | (post-window) | Tankan firm; JPY weakness + intervention watch |
| Indonesia | 5.75% | **Hiked +25bp** 2026-06-18 (from 5.50; +25bp again 06-09) | (post-window) | Two June hikes; rupiah defence; CPI lifted by fuel |
| Australia | 4.35% | Held 2026-06-16 | RBA speech (Hunter) 07-08 | Minutes: neutral-rate debate; houses split on hold-vs-hike-risk; OIS ~17% a hike by Aug |
| New Zealand | 2.25% | (prior decision) | **RBNZ MPR 2026-07-08** | Hike-cycle debate; ANZ calls +25bp Jul-8, Westpac holds → Sept (unreconciled) |
| United Kingdom | 3.75% | Held 2026-06-18 (vote 7/2/0 — **2 hike dissents**) | FSR 07-07; speakers in-window | Sticky; hawkish dissent; gilt supply |
| Canada | 2.25% | Held 2026-06-10 | BoC Business Outlook 07-06 | Steady BoC; weak growth, Macklem speech 07-01 |
| India | 5.25% | Held 2026-06-05 | (post-window) | Fiscal surplus (RBI dividend); monsoon/food-price watch |
| Philippines | 4.75% | **Hiked +25bp** 2026-06-18 (from 4.50) | (post-window) | Trade deficit narrowing; EM tightening cluster |
| Thailand | 1.00% | Held 2026-06-24 | BoT minutes 07-08 | Weak demand; current-account/energy shock in focus |
| Malaysia | 2.75% | (prior decision) | **BNM 2026-07-09** | "La pausa" — houses expect hold |
| Hong Kong | (USD peg / LAF) | — (linked to Fed) | — | Peg; retail sales soft; rides US pricing |
| Singapore | (MAS S\$NEER band) | — (band, not a rate) | — | 3M T-bill ~1.46%; property + bank-lending prints |

**SYN — the one-line state of the world:** this is a *hawkish-repricing* window, not an easing one. The Fed's June dots moved up (current-year projection 3.8% from 3.4%, FACT rows 21690-series), JGB is post-hike at 1.00%, and BI / BSP hiked in June. DM OIS curves price **net hikes** over the next 3–6m (§3). The differentiated debate is no longer "when do they cut" but "how much more tightening is already in the price, and where is it mispriced."

---

## 2. Calendar — releases + CB events with rate relevance  *(FACT — `cb_events`; pure calendar, no view)*

Consensus (`survey`/`forecast`) shown where present; `actual` shown only where the row carries one. Times are UTC per `event_datetime`.

| Date | Country | Event | Consensus | Prior | Actual (if printed) |
|---|---|---|---|---|---|
| 06-30 | AU | RBA June meeting **minutes** | — | — | released (row 21618/20370) |
| 06-30 | AU | Private-sector credit MoM | 0.6% | 0.7% | — |
| 06-30 | JP | **Tankan** large mfg index (Q2) | 16 | 17 | 16 (survey=actual, row 21708) |
| 06-30 | JP | Tankan large mfg **outlook** | 13 | 14 | 13 |
| 06-30 | JP | 2y JGB auction | — | 1.369% | — |
| 06-30 | UK | GDP QoQ / YoY (final) | 0.6% / 1.1% | 0.2% / 1.0% | 0.6% / 1.1% (final, rows 21639/40) |
| 06-30 | UK | Current account | £-24B | £-18.4B | — |
| 06-30 | CA | Monthly GDP MoM | 0.4% | -0.1% | — |
| 06-30 | US | JOLTS job openings | 7.6M | 7.618M | — |
| 06-30 | US | CB consumer confidence | 95 | 93.1 | — |
| 06-30 | US | Chicago PMI | 61 | 62.7 | — |
| 07-01 | ID | **CPI YoY** | 3.1% (BQL 3.2) | 3.08% | — |
| 07-01 | ID | Core CPI YoY | 2.4% | 2.59% | — |
| 07-01 | ID | Trade balance | \$4.0B | \$0.09B | — |
| 07-01 | JP | Consumer confidence | 32 | 33.6 | 34 (row 21742) |
| 07-01 | IN | HSBC mfg PMI (final) | 54.5 | — | 54.5 |
| 07-01 | US | ADP employment | 105K (fcst) | 122K | 118K (row 21767) |
| 07-01 | US | ISM manufacturing | 53.6 (fcst) | 54.0 | 53.7 (row 21770) |
| 07-01 | US | ISM prices paid | 80 | 82.1 | 79 (row 21774) |
| 07-01 | US | **Fed chair Warsh speech** | — | — | scheduled (row 53359, relevance 100) |
| 07-01 | UK | BoE Gov Bailey speech | — | — | scheduled |
| 07-01 | UK | Mfg PMI final | 53.1 | — | 53.1 |
| 07-02 | US | **Non-farm payrolls** | 110K (fcst) / 114K (survey) | 172K | — (Jul-2, not yet printed at run) |
| 07-02 | US | Unemployment rate | 4.3% | 4.3% | — |
| 07-02 | US | Avg hourly earnings MoM | 0.2% (fcst) | 0.3% | — |
| 07-02 | US | Factory orders MoM | 1.9% (fcst) | 4.8% | — |
| 07-02 | AU | Trade balance | A\$1.5B | A\$1.791B | — |
| 07-02 | UK | BoE credit conditions survey; **Mann speech** | — | — | scheduled |
| 07-02 | CA | S&P Global mfg PMI | 53.4 | 52.9 | — |
| **07-08** | NZ | **RBNZ Monetary Policy Review** | hold 2.25% (fcst) | 2.25% | forward |
| **07-08** | TH | BoT meeting minutes | — | — | forward |
| **07-08** | US | FOMC minutes | — | — | forward |
| **07-09** | MY | **BNM interest-rate decision** | hold 2.75% (fcst) | 2.75% | forward |

---

## 3. Cross-cutting trade-ideas table  *(VIEW / trade recommendation — provenance tagged; not judged)*

Distilled from the fact-chunk sweep + per-theme Qdrant search. Each row is expanded in the country read below.

| # | Trade | Key driver / rationale | Assumption it rests on | Falsifier | Provenance (report_id) |
|---|---|---|---|---|---|
| 1 | Short 5y5y Germany (add) | DM real-yield re-anchoring higher; hawkish ECB/Lagarde bias | Term-premium/real-rate repricing has further to run | Growth/inflation rolls over → bull-flattening | BNP (14319) |
| 2 | Long 30y Italian real yields @ 2.43% | "Re-anchoring real yields higher" rates map | Real yields structurally too low vs new regime | Risk-off bid for duration | UBS Global Strategy (14309) |
| 3 | Close **sell SGD/JPY** (take profit) | JPY leg of the trade played out; book the move | Yen weakness pace fades near intervention zone | Fresh yen leg lower → left money on table | HSBC FX (14595) |
| 4 | Take profit on **USD/JPY call EKO** (FX vol) | Vol/spot structure matured as USD/JPY ran to 40y high | Upside largely realised; intervention caps tail | Disorderly break higher past 162 | BNP FX vol (14478) |
| 5 | Antipodean rates: bias to **higher-for-longer / hike risk** | RBA minutes flag higher neutral; OIS ~17% a hike by Aug | Sticky AU services inflation persists | Labour market cracks → cut re-priced | Nomura (14304), BofA (14544), Westpac (14363) |
| 6 | NZ: position for RBNZ **start of a hike cycle** (timing split) | ANZ: hike +25bp to 2.50% Jul-8; Westpac: hold, lift-off Sept | RBNZ delivers the hikes it forecast; oil-shock persistence sticks | Growth/oil undershoot lets the Governor hold (his May off-ramp) | ANZ (14581), Westpac (14368) |
| 7 | Asia rates: fade recent move, **stability then TWD/IN outperform** | Post-selloff stabilisation; carry re-engages | No fresh US-rate shock into NFP | US NFP upside → renewed Asia-rates selloff | Nomura Asia rates (14421) |
| 8 | Tactically **bearish € duration** | Supply + inflation-surprise mix near-term | Supply indigestion into July | Dovish CPI surprise | Citi (14326) |
| 9 | 2H26: **take profits S&P / secular growth, buy Large-cap value** | Mid-year rotation call | Leadership broadens off mega-cap | Momentum persists in growth | BofA (14429) |
| 10 | US 10y: **stay on the sidelines** | Range-bound into data; poor risk/reward | No decisive NFP/CPI break | Clean payrolls beat/miss forces a break | Citi (14617) |

**SYN:** the live-trade cluster is overwhelmingly a **rates-higher / real-yield-re-anchoring** book (rows 1, 2, 5, 6, 8) plus **JPY-weakness profit-taking** (rows 3, 4). Two houses are explicitly *fading* the yen move rather than pressing it — worth flagging as a divergence from the "USD/JPY to new highs" narrative running elsewhere (Citi 14583, DB 14517).

---

## 4. Per-country read  *(JJ format: A themes · B the "why" · C consensus · D differentiated)*

Ordered by what actually moved in the window. For each mover country the flagship/desk notes were read in full (not off titles). Consensus (≥2 independent banks) and differentiated views are separated explicitly. Trades are surfaced with assumption + falsifier only — never judged.

---

### United States — the window's gravity well

**A. Themes in play**

| Rank | Theme | Assets | Banks talking | Why it matters to the PM |
|---|---|---|---|---|
| 1 | Fed reaction function turned **hawkish** (dots up); market prices net hikes | USD rates, front-end, USD | JPM, DB, UBS, Citi, Goldman | Re-anchors the whole DM curve; the "when do they cut" frame is dead this window |
| 2 | **Jul-2 payrolls** — headline vs internals disagree | USD rates, USD, risk | Goldman, UBS, Citi, MS | The binary event; a one-off beat over a cooling trend is the trap |
| 3 | **Core-PCE methodology change** mechanically lowers measured inflation | USD rates, TIPS/BE | Citi, Goldman, Barclays, DB | Changes the number the Fed reacts to by ~0.2–0.25pp; distorts the read |
| 4 | **Trend inflation still hot** — one house sees hikes to 4.1% | USD rates | DB (outlier) | The genuinely differentiated tail: a hiker, not a holder |
| 5 | Personnel noise (Warsh chair speech; Cook stays) | — | Barclays; calendar | Consensus filler; down-weighted, noted only |

**B. The "why" — how the houses are reasoning**

The frame is the June-17 FOMC: held at 3.75% but the **dots moved up** — current-year projection 3.8% (from 3.4%), 1st-yr 3.6% (from 3.1%), 2nd-yr 3.4% (from 3.1%), longer-run unchanged 3.1% (FACT, `cb_events` rows on 06-17). JPM's Quant Econ Dashboard (14494, VIEW/PRICING) shows the market has *followed* the Fed rather than fought it: US OIS prices **+7bp at 1m, +19bp at 3m, +32bp at 6m** off a 3.75% base — a net-tightening curve. The reasoning chain the houses share is: inflation has stopped falling, the labour market is stable enough to remove the cut-insurance case, and Fed communication (Hammack, Barkin both "inflation too high," per UBS 14508) validates the higher dots. That is the single most important fact in the whole digest, because it sets the real-yield-re-anchoring backdrop for the AU/NZ/UK trades in §3.

The **Jul-2 payrolls** debate is where the reasoning splits, and it splits on *mechanism*, not direction. Goldman (14557) is above consensus at **+130k vs 115k**, and is explicit about *why*: two special factors, with the World Cup category alone estimated at ~+40-45k (a category Goldman says "printed 45k"), plus a stabilisation in continuing claims. UBS (14508) and Citi (14480/14481) lean the other way on the *quality* channel — "hiring remains soft despite stronger payrolls," the labour-market differential falling, the April improvement narrow, consumer confidence disappointing on labour perceptions. So the set-up is a headline that could beat on a one-off while the internals corroborate cooling — the print and the trend disagree, and a PM has to decide which one the market trades. *Actual not yet printed at run (07-02 not ingested).*

The sleeper is the **core-PCE methodology change**, and here four houses converge on the fact but split on the *interpretation*. Citi (14437) calls it "a big deal": the BEA change (software + portfolio-management-services pricing, effective Sep-30, retroactive) mechanically **lowers 12m core PCE — 3.4% in May — by ~25bp**, because portfolio-management prices that rose with asset prices get re-measured. Goldman (14557) independently pegs the net effect at ~-0.2pp. Barclays (14371) frames the same revision as **"a measurement refinement"** — deliberately downplaying it. The PM-relevant point is that the inflation series the Fed is reacting to is about to get mechanically better without the underlying impulse changing — a wedge between measured and true inflation.

Against all of that sits the genuinely differentiated **DB (14516)**: its trend-inflation suite shows an overshoot that "significantly surpasses the pre-pandemic" norm (trimmed-mean PCE +7bp to 2.4%), and DB forecasts the **Fed hiking to 4.1% then holding** — the only house in-window explicitly modelling further hikes rather than a hold. Reasoning: the energy shock is feeding a broader, stickier inflation trend, so the higher dots are a floor, not a ceiling.

**C. Consensus views (≥2 independent banks)**

| Theme | Banks | Shared claim | Evidence cited | What consensus is missing (grounded) |
|---|---|---|---|---|
| Fed higher-for-longer | JPM, UBS, Citi, Goldman | No near-term cut; curve prices net hikes | Dots up (FACT); OIS +19bp 3m (14494); Hammack/Barkin "too high" (14508) | Doesn't price DB's *further-hike* tail; assumes 3.75% is the ceiling |
| Labour market cooling underneath | UBS, Citi, MS | Hiring soft despite firm headline | JOLTS steady but narrow; labour differential falling (14508); soft consumer labour perceptions | Jul-2 NFP + AHE actuals not yet in (FACT rows 21819/21) — consensus is pre-print |
| Core-PCE revision lowers measured inflation | Citi, Goldman, Barclays, DB | Methodology change trims core PCE ~0.2–0.25pp | BEA Sep-30 retroactive change; portfolio-mgmt-services re-measure (14437, 14557, 14371) | Splits on whether it's "a big deal" (Citi) or "refinement" (Barclays) — see D |

**D. Differentiated / unique views**

| Bank | Asset | The view | Why it's different | Hidden assumption | Falsifier |
|---|---|---|---|---|---|
| DB (14516) | USD rates | Fed **hikes to 4.1%** then holds | Only in-window house modelling *more* hikes, not a hold | Energy shock feeds a persistent, broad trend-inflation overshoot | A clean disinflation print / labour break re-opens the cut case |
| Goldman (14557) | USD rates, USD | Payrolls **+130k vs 115k** on World Cup +~45k | Above consensus via an identifiable one-off, not a trend call | The event bump lands cleanly in the establishment survey | Payback / no-show in July → reads as underlying weakness |
| Citi (14437) | TIPS/BE, USD rates | PCE methodology change is **"a big deal"** (−25bp) | Elevates a measurement wrinkle to a Fed-path input | The Fed reacts to the *measured* series, not the true impulse | Fed explicitly looks through the revision |
| Barclays (14371) | USD rates | Same revision is **"just a refinement"** | Directly *downplays* the Citi/Goldman read on identical data | Underlying momentum unchanged; optics ≠ policy | Fed cites the lower print as easing cover |

*Trade rows expanded:* #9 (BofA 2H rotation — take profits S&P/secular growth, buy large-cap value; assumption = leadership broadens off mega-cap; falsifier = growth momentum persists) and #10 (Citi — stay sidelined in US 10y into the data; assumption = the range holds; falsifier = a clean NFP break). Surfaced, not judged.

**DEPTH note:** US `econ.fact_indicator` is deep (165 indicators, ~3,218 obs since Apr, latest 06-29) — component labour/ISM detail was used above.

---

### Japan — post-hike, firm Tankan, yen at the intervention zone

**A. Themes in play**

| Rank | Theme | Assets | Banks talking | Why it matters to the PM |
|---|---|---|---|---|
| 1 | **June Tankan** — capex + inflation expectations support faster hikes | JGB, JPY, Japan equity | Goldman, DB, JPM, MS, Barclays, ANZ | The hike-path validator; large-mfg DI *rose* on the BoJ cut (see reconciliation) |
| 2 | **USD/JPY at 162+ / 40-yr high** — intervention watch | JPY, JGB, FX vol | Nomura, Citi, DB, SocGen, HSBC, BNP | The live tension: post-hike currency *weaker*, not stronger |
| 3 | Positioning: **fade the yen move vs press it** | JPY crosses, FX vol | HSBC (fade), BNP (fade) vs Citi/DB (continuation) | The tradeable split is on positioning, not direction |
| 4 | Inflation expectations rising (1/3/5y +0.1pt to ~2.7%) | JGB, BE | JPM, MS | Feeds the "earlier hike" case; JGB curve steepening on behind-the-curve fear |

**B. The "why" — how the houses are reasoning**

BoJ **hiked to 1.00%** on 06-16 (from 0.75%, FACT). The window's catalyst is the **June Tankan** (06-30), and the reasoning is near-unanimous that it supports *faster* tightening — but a PM needs the reconciliation first (see the unreconciled flag below). The desks are leaning on the **BoJ business-conditions diffusion index**, which *rose*: Goldman (14586) has large-manufacturers DI at **+37 (Mar +36), the fifth consecutive quarterly improvement** that "significantly exceeded" expectations, with the FY2026 capex plan "revised up sharply as usual." Barclays (14607) says the manufacturing DI hit its highest reading and the print supports its **October hike call**; DB (14624) is blunt — "business sentiment beats expectations, rising price pressures support **faster BoJ rate hikes**." The reasoning chain is: sentiment firm + capex plans revised up + output/input price DIs sharply higher + pass-through to output prices progressing = the corporate sector can absorb a higher policy rate.

The inflation-expectations leg is what turns a sentiment survey into a rates catalyst. JPM (14643) notes the all-firms sentiment index was *unchanged* but "the strongest corporate momentum in decades remains intact," and — critically — **1yr/3yr/5yr-ahead inflation expectations all rose +0.1pt to ~2.7%**. MS (14646) frames the outcome as a positive surprise that could "raise market participants' expectations for an *earlier* rate hike," while flagging the two-sided risks: payback after front-loaded demand, and exporters' assumed FX. That is the cleanest reaction-function read in the window — expectations drifting up give the BoJ cover to move sooner.

The currency is the paradox: a central bank that just hiked, with a currency that **broke above 162 to a 40-year high**. Nomura's intraday (14422) has USD/JPY into the July-2024 high with "intervention risk rising," BoJ's Sato striking a neutral tone, and the **JGB curve steepening on behind-the-curve concerns**. SocGen's Asia Pulse (14361) has spot holding above 162 with "usual jawboning," vols "exploding higher," and the market preparing for a move toward 163. Citi (14583) is blunt: "nobody stopping yen depreciation." The mechanism the bears cite is rate-differential + the hike being too slow relative to the Fed's higher dots — so JPY weakens *despite* the hike.

The tradeable split, and the highest-value divergence, is on **positioning near the intervention zone**. HSBC (14595) is *closing* its short SGD/JPY — it still sees "an intervention threat present" and books the move. BNP (14478) is *taking profit* on a USD/JPY call structure with spot approaching 163, noting "the forces of the Japanese government and central bank will likely" lean against it. Both are fading the easy money, against the continuation crowd (HSBC's own FX strategy piece 14348 "JPY: a new and higher range," DB 14517 "40-year high"). The fade assumption is that pace slows into intervention; the falsifier is a disorderly break past 162-163 that MoF/BoJ cannot lean on.

**C. Consensus views (≥2 independent banks)**

| Theme | Banks | Shared claim | Evidence cited | What consensus is missing (grounded) |
|---|---|---|---|---|
| Tankan supports faster/earlier hikes | Goldman, DB, JPM, MS, Barclays, ANZ | Firm sentiment + capex + rising price DIs = hike cover | Large-mfg DI +37 (14586); price DIs sharply higher (14607); infl-exp +0.1pt to 2.7% (14643) | The TE headline "large mfg index 16 vs 17" *fell* — a different series/vintage than the BoJ DI (unreconciled, see flag) |
| USD/JPY weak → intervention risk rising | Nomura, Citi, DB, SocGen | Spot 162+ at 40-yr high; jawboning present, action not yet | USD/JPY > 162 (14422); vols exploding (14361); "nobody stopping" it (14583) | No actual intervention has printed; the threat is verbal only — a positioning, not a policy, fact |

**D. Differentiated / unique views**

| Bank | Asset | The view | Why it's different | Hidden assumption | Falsifier |
|---|---|---|---|---|---|
| Barclays (14607) | JGB | Explicit **October hike** call, reinforced by Tankan | Puts a *date* on the next hike where others stay directional | Tariff/autos drag (the weak DI spot) stays contained | Autos/export DIs roll over → BoJ delays |
| HSBC (14595) | SGD/JPY | **Close the short** (take profit) | Fades the yen move where the tape says "new higher range" | Intervention threat caps further JPY downside near-term | Disorderly break past 163 with no official pushback |
| BNP (14478) | USD/JPY vol | **Take profit** on USD/JPY call structure | Books FX-vol gains as spot nears 163, rather than pressing | Gov/BoJ forces lean against the top of the range | A break higher that officials cannot contain |
| Citi (14583) | JPY | "**Nobody stopping**" the depreciation (continuation) | Directly opposite the HSBC/BNP fade on the same tape | Rate differential dominates; jawboning is empty | Actual intervention / a hawkish BoJ surprise |

**UNRECONCILED (flag):** the `cb_events` TE headline "Tankan large manufacturers **index 16 vs 17 prior**" (row 21708) shows a one-point *dip*, while every house note cites the BoJ **business-conditions DI improving to ~+37**. These are different cuts of the Tankan (TE's headline series vs the BoJ DI the desks quote) — not a contradiction, but I show both and do not silently pick one. The house-cited DI is the one driving the hike narrative.

**DEPTH flag:** JP `econ.fact_indicator` is effectively **absent** (1 obs). Every Japan number above is a `cb_events` print or a sell-side figure; no component depth is claimed.

---

### Australia — the "quiet tightening" debate over a static cash rate

**A. Themes in play**

| Rank | Theme | Assets | Banks talking | Why it matters to the PM |
|---|---|---|---|---|
| 1 | RBA **neutral-rate** debate from the June minutes | AUD rates, front-end | Nomura, BofA, Westpac, JPM | Re-frames whether 4.35% is neutral, tight, or easy — the whole AU rates view hangs on it |
| 2 | Is a static 4.35% actually **tightening**? (two opposite mechanisms) | AUD rates, AUD | BofA (short-run neutral *falls*) vs Nomura (long-run neutral *up*) | The differentiated crux: same "tighter" conclusion, opposite mechanism |
| 3 | **Sticky services/domestic inflation** vs soft tradables | AUD rates, ACGB | Westpac, BofA + ABS depth | The reason the Board is "still on edge"; corroborated by the CPI mix |
| 4 | **Two-speed housing** — firm credit, falling prices | AUD, banks, ACGB | ANZ, UBS, Goldman, MS | Complicates the tightening story; credit +8% YoY while Cotality falls |

**B. The "why" — how the houses are reasoning**

RBA **held 4.35%** (06-16); the **June minutes** (06-30, FACT) are the AU catalyst, and the whole debate is a *reaction-function* one about where neutral sits. Read in full, the houses actually *disagree on the mechanism* while landing on a similar "tighter for longer" conclusion — which is exactly the kind of split a PM wants surfaced. Nomura (14304) reads the minutes as flagging a **higher long-run neutral cash rate** ("a hawkish thought"), frames the terminal debate around ~4.10%, but — importantly — says the **board did not specifically consider a hike**, the neutral discussion "related to the tightness of policy," and Nomura keeps its cash-rate profile **unaltered (no further hikes, 4.35% into end-2026)**. So Nomura is *not* a hiker; it reads a hawkish nuance but holds its call. That is a more careful read than the "minutes = hawkish" headline.

BofA's flagship "**The Quiet Tightening**" (14544) runs the opposite mechanism to the same destination. Its argument is that the **short-run (cyclical) neutral rate is *falling***, so with the cash rate pinned at 4.35% the *stance* is passively getting tighter — policy transmits through yields, borrowing costs and housing-credit growth even without a hike. BofA pushes its first-cut expectation out to **August 2027** and says risks are "skewed towards another hike," explicitly citing "RBA's reaction function: why this time looks different." So Nomura says *long-run* neutral rose; BofA says *short-run* neutral fell — opposite claims about the neutral rate, both concluding the effective stance is tight. Westpac (14363) sits in between, reading the minutes and surrounding commentary as a Board "still on edge about inflation."

The pricing corroborates the "up, not down" tilt without endorsing an imminent hike: Westpac's What's-Priced-In (14364, PRICING) has RBA OIS at 4.350 with only ~**17% of a 25bp hike** priced by 11-Aug and ~32% by end-Sep — a curve nudging up, consistent with Nomura's "near-term OIS strip is fairly priced."

The **inflation depth** is where the ABS data does real work (AU `fact_indicator` is deep, 218 indicators). Latest monthly CPI (May): **headline 4.0% YoY, trimmed mean 3.6%, weighted median 3.6%**, with the persistence concentrated in **housing +6.5%, electricity +21.1%, rents +3.6%, services 3.7%** against tradables only +2.5%. That domestic/services stickiness is precisely what "still on edge about inflation" is about — the data corroborates the minutes rather than the sell-side spin. Meanwhile the **housing** picture is two-speed: the Cotality 5-capital index drifted **down** through June (225.0 → 223.9, Sydney/Melbourne leading lower; ANZ 14603, UBS 14650 both flag the downturn and slowing turnover), yet private-sector credit still ran **+0.7% MoM / ~8% YoY** (consensus 0.6%; Goldman 14245 "resilient at 0.7% mom"). Building approvals fell again in May (Goldman 14590, MS 14648). Firm credit, soft prices — which is exactly the transmission channel BofA's "quiet tightening" leans on.

**C. Consensus views (≥2 independent banks)**

| Theme | Banks | Shared claim | Evidence cited | What consensus is missing (grounded) |
|---|---|---|---|---|
| RBA effectively tight; no near-term cut | Nomura, BofA, Westpac | Stance is restrictive; cuts are distant | June minutes neutral-rate language; OIS ~17% a *hike* by Aug (14364) | They disagree on *why* neutral shifted (see D) — "tight" hides opposite mechanisms |
| Inflation still the binding constraint | Westpac, BofA | Domestic/services inflation keeps the Board cautious | CPI trimmed mean 3.6%, services 3.7%, electricity +21.1% (ABS DEPTH) | Tradables at 2.5% — the disinflation is real on the goods side; consensus under-weights it |
| Housing softening but credit resilient | ANZ, UBS, Goldman, MS | Prices down, approvals weak, credit still ~8% | Cotality 225.0→223.9; credit +0.7% mom (14245); approvals fall (14590/14648) | No one reconciles falling prices with +8% credit — the two-speed tension is left open |

**D. Differentiated / unique views**

| Bank | Asset | The view | Why it's different | Hidden assumption | Falsifier |
|---|---|---|---|---|---|
| BofA (14544) | AUD rates | "**Quiet tightening**": short-run neutral *falls*, so static 4.35% is passively tightening; first cut Aug-2027, risks skewed to a hike | Opposite mechanism to Nomura — argues *cyclical* neutral is dropping, not that long-run neutral rose | Transmission via yields/housing credit does the tightening the RBA won't | Neutral re-rises / demand re-accelerates → stance becomes easy again |
| Nomura (14304) | AUD rates | Minutes flag a **higher long-run neutral**, but **no hike** — profile unaltered at 4.35% into end-2026 | Reads the hawkish nuance yet explicitly holds its call; board "did not consider" a hike | The neutral-rate note is about policy tightness, not a signal to move | Board actually contemplates a hike at a coming meeting |

*Trade row expanded:* #5 (antipodean higher-for-longer / hike-risk bias; assumption = sticky services inflation keeps the stance restrictive; falsifier = labour-market cracks that re-price a cut). Provenance Nomura/BofA/Westpac. Surfaced, not judged — note the two provenance houses actually reason from opposite neutral-rate mechanisms.

---

### New Zealand — RBNZ Jul-8: a live hike-vs-hold split

**A. Themes in play**

| Rank | Theme | Assets | Banks talking | Why it matters to the PM |
|---|---|---|---|---|
| 1 | **RBNZ Jul-8 MPR** — hike now or hold to September | NZD rates, NZD, NZGB | ANZ (hike), Westpac (hold) | Binary, imminent, and the two lead local houses *disagree on the meeting* |
| 2 | RBNZ has a **pre-committed hike path** (its own forecast) | NZD rates | ANZ, Westpac | The question is timing, not direction — a hike is coming, when is the trade |
| 3 | **Oil-shock persistence** as the swing factor | NZD rates, BE | ANZ, Westpac | Governor's May off-ramp was explicitly oil/growth-conditional |

**B. The "why" — how the houses are reasoning**

OCR **2.25%**; the **RBNZ Monetary Policy Review is 2026-07-08** (FACT, forward) — the region's key near-term event. Read in full, the two lead NZ houses land on *opposite calls for the meeting itself*, which is the highest-value content here and corrects a softer "restart of tightening" framing. **ANZ (14581)** expects the RBNZ to **raise the OCR 25bp to 2.50% at Jul-8** — its preview is literally "let's get started." ANZ's reasoning: the Committee "was already planning on lifting the OCR" per the May MPS, it sees the risks tilted toward neutral being higher, and it flags core/wage-growth pressure that pre-dated the Middle East conflict and an oil-shock component "assumed to be fairly persistent and worth maybe +30bp on the TWI." ANZ even sketches a "hawkish hike" scenario. So ANZ reads a Committee that has telegraphed the move and has the inflation cover to deliver it now.

**Westpac (14368)** reads the *same* Governor and expects the OCR to **remain at 2.25% at Jul-8**, with lift-off brought forward to **September** rather than July. Its reasoning: the May press release was "more conditional," the Governor explicitly said "if we see oil prices falling really much more than expected… then we may not hike," the relatively quick resolution of Iran tensions removes some urgency, and the MPC will "want to review the key data" before committing — Jul-8 is only an MPR, not a full Statement, which Westpac reads as a natural spot to wait. So the split is genuinely on *timing and the Governor's conditionality*, not on direction — both expect hikes, ANZ says now, Westpac says September.

The pricing sits between them but nearer ANZ: ANZ's own What's-Priced-In (14510/14171, PRICING) shows the market carrying **~+17-19bp into Jul-8** and a curve rising to **~2.83 by December** — a genuine hiking path. Note the `cb_events` forecast field still tags Jul-8 as a *hold at 2.25%*, so there are effectively three readings on the table.

Supporting data: business confidence firmed (ANZ NZ Business Outlook "brightening," 14237; Westpac first-impressions 14262). NZGB tender previews (ANZ 14580/14602) are supply housekeeping.

**C. Consensus views (≥2 independent banks)**

| Theme | Banks | Shared claim | Evidence cited | What consensus is missing (grounded) |
|---|---|---|---|---|
| RBNZ is on a hiking path (direction agreed) | ANZ, Westpac | The OCR is going up; the only question is when | May MPS forward guidance; oil-shock persistence; firming confidence (14237/14262) | They do **not** agree on the Jul-8 meeting itself — direction-consensus masks a timing split (see D) |

**D. Differentiated / unique views**

| Bank | Asset | The view | Why it's different | Hidden assumption | Falsifier |
|---|---|---|---|---|---|
| ANZ (14581) | NZD rates, NZD | **Hike +25bp to 2.50% at Jul-8** ("let's get started") | Calls the hike *now*, at an MPR, ahead of the market | Committee delivers the path it forecast; oil-shock adds ~+30bp on the TWI and persists | Growth/oil undershoot → Governor invokes his May off-ramp and holds |
| Westpac (14368) | NZD rates | **Hold at 2.25% Jul-8; lift-off September** | Reads the same Governor as more conditional; waits for data at a non-Statement meeting | Iran de-escalation + data-review argue for patience over an MPR | RBNZ hikes Jul-8 anyway → Westpac's "September" is a meeting late |

**UNRECONCILED (flag):** three readings of Jul-8 coexist — ANZ hike / Westpac hold / `cb_events` forecast hold. Shown all three; not silently resolved.

**DEPTH flag:** NZ `fact_indicator` is **thin** (48 indicators, 94 obs, latest 05-31) — a sanity check, not a component deep-dive.

*Trade row expanded:* #6 (position for the start of an RBNZ hike cycle, timing split; assumption = RBNZ delivers its forecast path and oil-shock persistence sticks; falsifier = growth/oil undershoot lets the Governor hold). Provenance ANZ (hike Jul-8) vs Westpac (hold → Sept). Surfaced, not judged.

---

### Indonesia — two June hikes, rupiah defence, fuel-led CPI  *(INSTRUMENT PENDING DEEPAK)*

**A. Themes in play**

| Rank | Theme | Assets | Banks talking | Why it matters to the PM |
|---|---|---|---|---|
| 1 | **BI currency-defence reaction function** (two June hikes) | IDR, IDR rates | SocGen, JPM (context) | Policy is now hostage to the rupiah, not the growth cycle |
| 2 | **Rupiah under pressure**, spot defended at 18000 | IDR spot/NDF | SocGen | The defence level is explicit; break risk is the trade |
| 3 | **Fuel-led CPI uptick** (supply-side) | IDR rates, BE | Goldman | Complicates the trade-off: cost-push inflation into a currency defence |

**B. The "why" — how the houses are reasoning**

BI **hiked twice in June** — to 5.50% (06-09) then **5.75% (06-18)** (FACT). The reasoning across the flow is that this is a **currency-defence reaction function**, not a growth-driven one. SocGen's Asia Pulse (14361), read in full, describes the **rupiah selloff with onshore USD/IDR spot "capped at 18000"** for now, suspected smoothing in the NDF space (averaging ~100mio daily last week vs ~300mio the prior week), and the JCI down ~2.5% intraday — i.e. BI is leaning against depreciation with both rates and intervention, and the market is watching the 18000 line as the defence level. That makes IDR the variable driving policy.

The complication is inflation *mix*. The **Jul-1 CPI** (consensus 3.1% YoY, BQL 3.2; prior 3.08%; core prior 2.59% — FACT/PRICING) matters because Goldman (14633), read in full, attributes the June uptick to **higher unsubsidised fuel prices**, with the monthly index +0.4% mom NSA (from +0.3% in May) driven by transport and food & beverage. That is a *supply-side, cost-push* impulse — the awkward kind for a central bank already tightening to defend the currency, because hiking into cost-push inflation risks squeezing growth without addressing the source. JPM's Indonesia piece (14459) is equity-angled but usefully notes conditions with "policy rates / **SRBI yields at high levels**" and points to the 2027 draft budget (August) as the next catalyst — I cite that only as an observed condition, not as a Spider instrument call.

**C. Consensus views (≥2 independent banks)**

| Theme | Banks | Shared claim | Evidence cited | What consensus is missing (grounded) |
|---|---|---|---|---|
| BI policy is currency-led | SocGen, JPM (context) | Rates + intervention deployed to defend IDR | Spot defended ~18000, NDF smoothing (14361); SRBI yields "high" (14459) | Only two independent houses in-window on ID — thin corroboration; treat as low-n |

*(Only one genuine cross-house consensus theme cleared the ≥2-bank bar in-window; the fuel-CPI read is currently single-house Goldman — filed under D-adjacent, not C.)*

**D. Differentiated / unique views**

| Bank | Asset | The view | Why it's different | Hidden assumption | Falsifier |
|---|---|---|---|---|---|
| Goldman (14633) | IDR rates / BE | June CPI uptick is **fuel/cost-push**, not demand | Isolates the *source* of inflation where others see only the currency | The fuel impulse is supply-side and BI's hikes don't address it | Core CPI accelerates broadly → demand-pull, validating the hikes |
| SocGen (14361) | IDR spot/NDF | **18000 is the defended line**; smoothing is slowing | Puts a specific level and flow-size on the defence | BI keeps leaning until 18000; NDF flow-decay signals fatigue, not resolve | Clean break of 18000 with no larger intervention response |

**Puzzle fit:** currency + CB-reaction-function is the live axis; the fuel-led CPI is a cost-push overlay. **I deliberately name no Spider instrument** (SRBI vs IDR rates vs govvies). JPM's reference to "SRBI yields at high levels" is cited as an *observed market condition only* — the "use the bonds" instruction stays the open flag **PENDING DEEPAK**; I will not guess which instrument it means.

**DEPTH:** ID `fact_indicator` is reasonably deep (113 indicators, latest 06-26) — usable for CPI component follow-up once the print lands.

---

### United Kingdom — sticky inflation, hawkish dissent, a steepening gilt curve

**A. Themes in play**

| Rank | Theme | Assets | Banks talking | Why it matters to the PM |
|---|---|---|---|---|
| 1 | **Inflation shocks steepen the gilt curve** (UK most exposed) | Gilts, linkers, GBP | UBS (rates + equity) | The differentiated rates thread; quantified curve response |
| 2 | BoE **hawkish vote drift** (2 hike dissents) + firm GDP | Gilts, GBP | BoE (FACT); speaker-heavy window | Vote split + growth support a higher-for-longer front end |
| 3 | UK's **high inflation-linked debt share** amplifies the shock | Linkers, >15y gilts | UBS | Structural: an inflation shock hits UK fiscal/curve harder than peers |

**B. The "why" — how the houses are reasoning**

BoE **held 3.75%** on 06-18 with a **7/2/0 vote — two members dissenting to *hike*** (FACT; prior split 8 unchanged / 1 hike). The hawkish *drift* in the vote is the signal: the balance is tilting toward the hike camp, not the cut camp. The window is speaker-heavy — **Bailey (07-01, 07-03), Mann (07-02), the credit-conditions survey (07-02), FSR (07-07)** (FACT) — and final Q1 GDP confirmed a firmer **+0.6% QoQ / +1.1% YoY** (FACT rows 21639/40), which removes the growth alibi for cuts and supports the dissenters.

The genuinely differentiated content is UBS's gilt work, read in full. "Inflationary shocks steepen the gilt curve" (14426) makes a *quantified* structural argument: it models the response of the UK yield curve to a 1ppt positive inflation shock and finds the steepening is more front-end-driven in the UK than elsewhere ("whiplash in front-end UK rates dominated steepening"), and — the structural kicker — the **UK has the highest inflation-linked debt share across peers**, with >15y linkers having de-rated. So an inflation shock transmits more violently into UK rates and UK fiscal than into US or German curves. The companion "Simply UK: The Gilt Trip" (14310, an equity-strategy framing) carries the same thesis into cross-asset. The reasoning chain: sticky inflation + hawkish vote + heavy index-linked issuance = a steeper curve and a fiscal amplifier, which is why UBS expresses it in the curve rather than outright direction.

**C. Consensus views (≥2 independent banks)**

*None cleared the ≥2-independent-bank bar in-window.* UK flow this window was dominated by the BoE decision mechanics (FACT) and a single differentiated house (UBS) on the gilt curve. Honest low-n note rather than a manufactured consensus row.

**D. Differentiated / unique views**

| Bank | Asset | The view | Why it's different | Hidden assumption | Falsifier |
|---|---|---|---|---|---|
| UBS (14426) | Gilts, linkers | **Inflation shocks steepen the gilt curve**; UK most exposed via high linker share | Quantifies a UK-specific curve response and ties it to the index-linked debt structure | An inflation shock is the operative risk; front-end whiplash leads the move | A disinflation surprise / a flight-to-quality bull-flattening |
| UBS (14310) | UK equity / cross-asset | "**The Gilt Trip**" — carries the steepening thesis into equity positioning | Bridges the rates call into equity strategy, uncommon in-window | Gilt-curve dynamics dominate the UK equity risk premium | Rates stabilise and the equity read decouples from the curve |

**DEPTH flag:** UK `fact_indicator` is **thin** (2 indicators, 46 obs) — no component depth; the vote split and GDP are `cb_events` prints.

---

### Canada — steady BoC, growth the question

**CB (FACT).** BoC **held 2.25%** (06-10); **Macklem speaks 07-01** (in-window, row 53356), Business Outlook Survey + Consumer Expectations land 07-06. Monthly GDP (06-30) consensus **+0.4% MoM** rebounding from -0.1% prior (row 47579). BofA's mid-year (14376) is titled "**Weak growth, steady BoC**" — the consensus frame: no urgency either way. Nothing differentiated resonated in-window.

**DEPTH flag:** CA `fact_indicator` is **absent** (1 obs). No depth claimed — as expected per the coverage note.

---

### Thailand — soft prints, but the sell-side leans constructive

**A. Themes in play**

| Rank | Theme | Assets | Banks talking | Why it matters to the PM |
|---|---|---|---|---|
| 1 | **Data soft, houses lean constructive** (the tension) | THB rates, THB | JPM, Barclays, BofA | The print vs the narrative disagree — the classic spot to interrogate |
| 2 | **Oil-price relief → GDP** channel | THB rates, BE | BofA | Differentiated growth-positive mechanism from lower energy |
| 3 | **Energy shock → corporate margins** | THB equity, credit | HSBC | Cross-checks the oil story from the margin side |

**B. The "why" — how the houses are reasoning**

BoT **held 1.00%** (06-24); minutes 07-08 (FACT). The in-window hard data was soft — private consumption -2.1% MoM, private investment -5% MoM, current account -\$7.6B (FACT rows 27266-68) — yet the sell-side read leans *constructive on the margin*, which is the tension a PM should sit on. JPM (14528) titles its note "investment-led growth gains momentum in May," Barclays (14370) sees a "modest rebound," and BofA runs two angles: "limited recovery" (14545) on the activity side but "GDP relief from lower oil prices and AI wave" (14548) on the outlook. HSBC (14562) works the same oil theme from the other direction — what the energy shock means for corporate margins. The reasoning that lets the desks be constructive over soft prints is forward-looking: lower oil improves the terms of trade and the current account, and an AI/investment cycle supports capex — so they look through the weak May consumption/investment reads to a better H2. Nomura's Asia-rates note (14421) references a Thailand rates position with a defined ~10bp stop — surfaced, not judged.

**C. Consensus views (≥2 independent banks)**

| Theme | Banks | Shared claim | Evidence cited | What consensus is missing (grounded) |
|---|---|---|---|---|
| Soft now, stabilising ahead | JPM, Barclays, BofA | Look through weak May data to a firmer outlook | "Investment-led momentum" (14528); "modest rebound" (14370); "limited recovery" (14545) | The hard data (consumption -2.1%, investment -5%, CA -\$7.6B) is unambiguously weak *now* — the constructive read is a forecast, not a print |

**D. Differentiated / unique views**

| Bank | Asset | The view | Why it's different | Hidden assumption | Falsifier |
|---|---|---|---|---|---|
| BofA (14548) | THB rates / macro | **Oil-price relief + AI wave lift GDP** | Names a specific positive mechanism where others just see "stabilising" | Lower oil sustains and the AI/investment cycle broadens | Oil re-spikes / investment cycle stalls → the relief reverses |

**DEPTH flag:** TH has **no in-window `fact_indicator` rows** — all numbers are `cb_events` prints or sell-side.

---

### India — fiscal surplus, monsoon/food inflation tail, terminal-repo debate

**A. Themes in play**

| Rank | Theme | Assets | Banks talking | Why it matters to the PM |
|---|---|---|---|---|
| 1 | **Fiscal improvement** on a record RBI dividend | INR rates, IGB | Goldman, Nomura, MS | A flows/fiscal positive; eases supply pressure on govvies |
| 2 | **Monsoon/food-inflation upside tail** (weak start, El Niño) | INR rates, BE | MS, Citi | The main inflation risk to the RBI's on-hold stance |
| 3 | **RBI reaction function / terminal repo** | INR rates | DB, StanC (colour) | Where the rates path is decided; houses probing the terminal level |

**B. The "why" — how the houses are reasoning**

RBI **held 5.25%** (06-05). The window's positive is fiscal: three houses independently flag a **May fiscal surplus/improvement on a record RBI dividend** — Goldman (14492), Nomura (14467), MS (14466) — which reduces near-term govvie supply pressure and is a clean flows tailwind. Against that, the inflation risk is squarely monsoon/food: MS (14301) flags the **June rainfall deficit as the highest in 12 years** and Citi (14482) warns an intensifying El Niño and a weak monsoon start "warrant a closer watch" — a food-inflation upside tail that could test the RBI's hold. The reaction-function work sits on top: DB (14439) uses an AI approach to "decode the terminal repo" rate, and StanC (14423) brings client-positioning colour from London trip-notes. HSBC mfg PMI final 54.5 (07-01, FACT) confirms activity stays firm, so this is not a growth-scare story — it is a fiscal-positive / food-inflation-risk balance around a data-dependent RBI.

**C. Consensus views (≥2 independent banks)**

| Theme | Banks | Shared claim | Evidence cited | What consensus is missing (grounded) |
|---|---|---|---|---|
| Fiscal improved in May | Goldman, Nomura, MS | Deficit narrowed / surplus on record RBI dividend | May fiscal data + RBI dividend (14492/14467/14466) | A one-off dividend flatters the run-rate; underlying fiscal path unchanged |
| Monsoon/food is the inflation risk | MS, Citi | Weak monsoon + El Niño = food-price upside | June rainfall deficit 12-yr high (14301); El Niño watch (14482) | The tail is not yet in the CPI print — IN CPI DEPTH available to track it |

**D. Differentiated / unique views**

| Bank | Asset | The view | Why it's different | Hidden assumption | Falsifier |
|---|---|---|---|---|---|
| DB (14439) | INR rates | Uses AI to **decode the terminal repo** level | Method-differentiated attempt to pin the endpoint rather than the next move | The terminal rate is the tradeable variable, not the next meeting | RBI reaction function shifts on a food-inflation shock |

**Puzzle fit:** fiscal (RBI-dividend surplus) + inflation (monsoon/food tail) + reaction-function (terminal-repo). **DEPTH:** IN is deep (571 indicators) — food/CPI component follow-up (incl. the fresh-food nowcaster) is available to track the monsoon tail.

---

### Philippines — a quiet hike, narrowing trade gap

**CB (FACT).** BSP **hiked +25bp to 4.75%** on 06-18 (from 4.50%, survey 4.75%) — part of the June EM-tightening cluster (ID, PH). In-window: **trade deficit narrowed in May** (JPM 14291), exports +6.3% YoY, PPI +2.4% (rows 27245-48). Thin flow otherwise; filed as EM-tightening + external-balance improvement. No `fact_indicator` depth.

---

### Malaysia — BNM Jul-9 preview, "La pausa"

**CB (FACT + VIEW).** OPR **2.75%**; **BNM decides 2026-07-09** (forward). HSBC's preview is titled "**La pausa**" (14288) — consensus expects a hold. M3 ~5% YoY (06-30). Quiet otherwise; calendar-driven into next week. No in-window `fact_indicator` depth.

---

### Hong Kong — peg, soft retail

**Macro (FACT).** USD-linked (no independent policy rate; rides US pricing via the peg/LAF). In-window: **retail sales YoY** prior 6.4%, forecast 5.8% (07-02, row 29142) — softening. HK `fact_indicator` exists (20 indicators, latest 06-03) but nothing rate-relevant moved. Honest short note: peg-follows-Fed; no differentiated flow.

---

### Singapore — band, not a rate

**Macro (FACT).** MAS runs the S\$NEER band, not a policy rate — dashboard row is intentionally "band, not a rate." In-window: URA property index +0.9% QoQ prelim (07-01), bank lending S\$908.4B, SIPMM PMI 51 (07-02), 3M/6M T-bills ~1.46-1.47%. Citi Asia-Flow overview (14323) is the relevant flows read. Quiet; calendar-only. No differentiated call resonated.

---

## 5. Grounding ledger  *(SYN)*

- **FACT layer:** `calendar.cb_events`, window 2026-06-30→07-02, 212 rows across the 13 covered countries; all dates and held/hiked/held tags verified against real decision rows (RBA 06-16 hold, BoJ 06-16 hike, BI 06-09 & 06-18 hikes, BSP 06-18 hike, BoE 06-18 hold w/ 2 hike dissents, Fed 06-17 hold w/ dots up).
- **DEPTH layer:** `econ.fact_indicator` — deep AU (218)/US (165)/IN (571)/ID (113)/HK (20); thin NZ (48)/UK (2); absent CA/JP (1 each); **no in-window rows TH/MY/SG/PH.** No depth faked.
- **VIEW layer:** `research.fact_chunk` + Qdrant (`research_gemini_embedding_2_3072d`, live) — 408 in-window reports across 13 vendors. For the six movers (US/JP/AU/NZ/ID/UK) the flagship/desk notes were read **in full** at the chunk level (BofA 14544 Quiet Tightening; Nomura 14304 RBA; ANZ 14581 + Westpac 14368 RBNZ; Goldman 14586/DB 14624/Barclays 14607/JPM 14643/MS 14646 Tankan; Goldman 14633/SocGen 14361 ID; Citi 14437/DB 14516/Goldman 14557 US; UBS 14426/14310 UK), not summarised off titles. Per-theme semantic sweeps re-run for JPY/intervention, RBA neutral-rate, RBNZ Jul-8, Indonesia/SRBI, US-payrolls/Fed, JP-Tankan-DI and US-PCE-methodology; reconciled against the SQL scan.
- **Unreconciled / flagged inline:** (a) **NZ Jul-8** — three readings coexist: ANZ hike +25bp vs Westpac hold→Sept vs `cb_events` forecast hold. All three shown; not resolved. (b) **JP Tankan** — the `cb_events` TE headline "large-mfg index 16 vs 17" (a *dip*) is a different series/vintage from the BoJ business-conditions **DI ~+37 that improved**, which every house cites; both shown, neither silently picked. (c) **AU neutral rate** — Nomura (long-run neutral *up*, no hike) and BofA (short-run neutral *falls*, "quiet tightening") reach "stance is tight" via *opposite* mechanisms; surfaced as a differentiated split, not merged. (d) **US core-PCE revision** — Citi "big deal" vs Barclays "just a refinement" on identical BEA data; both shown. (e) Jul-2 US NFP + factory orders = calendar-only, no note flow ingested yet. (f) **Indonesia instrument pending Deepak** — JPM's "SRBI yields high" cited as observed condition only; no Spider instrument asserted.
- **Differentiated-view count (section 4.D):** US 4 · JP 4 · AU 2 · NZ 2 · UK 2 · India 1 · Thailand 1 · Indonesia 2 = **18 differentiated rows** across 8 countries. Quiet countries (CA/PH/MY/HK/SG) carry honest short reads, not forced tables.

*DRAFT — demo cut. Section 4 rebuilt in JJ A/B/C/D format for the movers; flagship notes read in full. Trades surfaced, never judged. Numbers first.*
