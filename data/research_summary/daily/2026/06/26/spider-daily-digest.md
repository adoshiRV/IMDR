---
edition: daily
date: 2026-06-26
---

# Spider — Daily Macro Research Digest

*Rolling day into Friday 26 June 2026. FX & rates PM desk read. Country-first. Every dashboard/calendar/trade row is grounded to a real DB row and picked up in the per-country prose below. Tags: FACT (printed data / booked event), VIEW (sell-side interpretation / desk colour / trade rec), SYN (Spider synthesis). Where a claim is <99% grounded, or two sources disagree, it is flagged inline.*

**The regime, in one line (SYN):** this is a *re-tightening / hawkish-shifted* cycle, not the 2024–25 easing one — RBA has hiked four times into 4.35%, BoJ is at 1.00% and hiking, Indonesia and Philippines both hiked in June, and the US–Iran peace deal has knocked Brent ~35% off its peak, flipping an energy shock into an EM-importer tailwind and firing a broad "debasement-trade" unwind. Read every note against that backdrop.

---

## 1. Central-bank / macro dashboard

*Current-state snapshot, one row per covered country. Policy rate + last move verified against `calendar.cb_events`. "Next meeting" is the next scheduled decision booked in cb_events; where not booked forward it is flagged. HK runs a currency-board (no independent policy rate) — flagged.*

| Country | Policy rate | Last move (date) | Next meeting | Bias / key issue (SYN) |
|---|---|---|---|---|
| US | 3.50–3.75% (FOMC lower/upper bound) | Held 18 Jun (prior 3.5) | 30 Jul 2026 | On hold; 9 dots carry a 2026 hike. Sticky core PCE (+0.3% m/m May) vs soft real spending — hold-vs-hike, not cut |
| AU | 4.35% cash rate | Held 16 Jun (hiked 3.60→4.35 Feb–May) | 11 Aug 2026 | Re-tightening cycle; trimmed mean rose to 3.6% y/y. Hawkish hold; some houses price +25 to 4.60 |
| JP | 1.00% call rate | **Hiked** +25 16 Jun (0.75→1.00) | 31 Jul 2026 | Normalising; Tokyo core CPI 1.6% but rise is policy-driven, not demand. Next hike Q4-priced |
| ID | 5.75% BI-Rate | **Hiked** +25 18 Jun (5.50→5.75) | 22 Jul 2026 | Currency-defence tightening; forecast had been +50. Instrument view PENDING DEEPAK |
| PH | 4.75% BSP o/n | **Hiked** +25 18 Jun (4.50→4.75) | 27 Aug 2026 | Tightening into peso pressure |
| IN | 5.25% repo | Held 5 Jun | *Not booked in cb_events* (Aug MPC, est.) | On hold but market prices +85bp of hikes; Gov actively pushing back |
| UK | 3.75% Bank Rate | Held 18 Jun | 30 Jul 2026 | On hold; econ depth thin (see ledger) |
| CA | 2.25% o/n | Held 10 Jun | *Not booked in cb_events* (Jul, est.) | On hold; econ depth thin |
| NZ | 2.25% OCR | Held 27 May | 8 Jul 2026 | Easing cycle largely done; houses "confident" vs AU "uncertain" |
| TH | 1.00% benchmark | **Held** 24 Jun (survey 1.0) | 26 Aug 2026 | Floor-ish; baht overvaluation the live debate |
| MY | 2.75% OPR | Held 7 May | 9 Jul 2026 | On hold; trade surplus surge (electronics/AI) the story |
| KR (context) | 2.50% base | Held 28 May | — | Carried for cross-market context; outside core narrative |
| HK | *Currency board — no policy rate* | Base rate tracks Fed | Tracks FOMC | USDHKD toward 7.75–7.85 mid; front-end HIBOR/IRS the trade |
| SG | *No policy rate — MAS runs S$NEER* | S$NEER band | MAS Oct (semi-annual) | No 2H MAS tightening priced; front-end SORA carry |

*Flags: (i) IN and CA next-meeting dates are NOT booked forward in cb_events — shown as estimated cadence, not a booked row. (ii) HK "Composite Interest Rate" is the only HK rate row and is stale (2008); HK has no independent policy rate — correctly represented as currency-board. (iii) SG/MY/TH/PH/SG carry no `econ.fact_indicator` depth (see §5).*

---

## 2. Calendar — what printed into 26 Jun, and what's imminent

*Pure calendar. Actual/survey/prior from `calendar.cb_events`. No view expressed here — views are in §4. Surprise = actual vs survey.*

### Printed in the rolling window (24–26 Jun)

| Date | Country | Event | Actual | Survey | Prior | Surprise (SYN) |
|---|---|---|---|---|---|---|
| 24 Jun | AU | CPI YoY (monthly, May) | 4.0 | 4.3 | 4.2 | Downside on headline (fuel) |
| 24 Jun | AU | CPI Trimmed Mean YoY | 3.6 | 3.5 | 3.4 | **Upside** — core sticky |
| 24 Jun | TH | BoT benchmark rate | 1.0 (held) | 1.0 | 1.0 | In line — held |
| 24 Jun | MX | Bi-weekly CPI YoY | 3.55 | 3.72 | 3.77 | Downside; core 4.12 |
| 24 Jun | US | New Home Sales (k) | 580 | 640 | 622 (rev 626) | Miss |
| 25 Jun | AU | Employment Change (k) | +40.3 | +32.5 | −18.6 (rev −40.7) | Beat — jobs rebound |
| 25 Jun | AU | Unemployment Rate | 4.4 | 4.4 | 4.5 | In line, down-tick |
| 25 Jun | US | GDP Annualized QoQ (Q1 final) | 2.1 | 1.6 | 1.6 | **Upward revision** |
| 25 Jun | US | Core PCE Price Index MoM (May) | 0.3 | 0.3 (fcst 0.2) | 0.2 | At/above; core firm |
| 25 Jun | US | Core PCE YoY (May) | 3.41 | 3.4 | 3.29 | Firm |
| 25 Jun | US | Personal Spending MoM | 0.71 | 0.6 | 0.5 (rev 0.4) | Beat (nominal) |
| 25 Jun | US | Durable Goods Orders MoM | −4.5 | −5.0 | +8.0 (rev 8.5) | Less-bad |
| 25 Jun | US | Initial Jobless Claims (k) | 215 | 225 | 226 (rev 227) | Low — labour firm |
| 26 Jun | JP | Tokyo CPI ex-Fresh Food YoY | 1.6 | 1.6 | 1.3 | In line; policy-driven rise |
| 26 Jun | JP | Tokyo CPI ex-FF & Energy YoY | 1.9 | 1.8 | 1.6 | **Above** — underlying firmer |
| 26 Jun | MX | Banxico Overnight Rate | 6.5 (held) | 6.5 | 6.5 | Held |
| 26 Jun | SG | Industrial Production YoY | 13.0 | 17.5 | 17.6 (rev 16.5) | Miss |
| 26 Jun | TH | Gross Intl Reserves ($bn) | 282.6 | — | 283.9 | Slight draw |
| 26 Jun | US | U. of Mich. Sentiment (final) | 49.5 | 50.0 | 48.9 | Soft, up-ticked |

### Imminent (27–30 Jun)

| Date | Country | Event | Survey | Prior |
|---|---|---|---|---|
| 29 Jun | IN | Industrial Production YoY | 4.5 | 4.9 |
| 29 Jun | JP | Retail Sales YoY | 3.0 | 2.1 |
| 29 Jun | UK | Mortgage Approvals (k) | 63.0 | 65.9 |
| 29 Jun | US | Dallas Fed Mfg Activity | 1.0 | 0.4 |
| 30 Jun | CA | GDP MoM | 0.4 | −0.1 |
| 30 Jun | JP | Jobless Rate | 2.5 | 2.5 |
| 30 Jun | UK | GDP QoQ (final) | 0.6 | 0.6 |

---

## 3. Cross-cutting trade-ideas table

*What the houses are floating into 26 Jun, across countries. One row per idea: the trade · key driver · assumption it rests on · falsifier · provenance. Not judged — surfaced. Each row is expanded in the relevant §4 country block. Capped and distilled from `research.fact_chunk` + Qdrant.*

| # | Trade | Key driver / rationale | Assumption | Falsifier | House (report id) |
|---|---|---|---|---|---|
| 1 | Receive 2y INR (OIS) | RBI Gov publicly pushing back on hike pricing; 1y OIS carries +85bp of hikes centred Oct/Dec that GS thinks won't be delivered | RBI won't use domestic rates to defend INR | RBI hikes o/n fix / policy to defend a sliding rupee | Goldman (12546) |
| 2 | Long 10y IGB vs OIS / on-curve | 10y IGB cheap on 5x10x30 fly (series highs) + FCNR flow distorting NDS/XCCY basis | Fiscal supply stays orderly; FCNR flow persists | 10y bond supply shock or fly re-richens | Goldman (12546) |
| 3 | Pay 1y1y THB (vs SGD) | THB fundamentally overvalued; surging investment + policy resistance make baht a funder | BoT resists baht strength; China excess-capacity drag persists | BoT tolerates strength / THB weakens on its own | JPM (13290) |
| 4 | Pay front-end HKD IRS vs USD | HKMA aggregate balance low → upward pressure on front IRS; dividend-season USD demand | Local liquidity tightens near-term | HKMA injects liquidity; HIBOR eases | Barclays (12523) |
| 5 | USDHKD toward 7.75–7.85 mid (upper band) | Carry + funding demand keep pair supported after 7.83–7.84 consolidation | Convertibility band holds; no HK rate spike unwind | Sharp HIBOR spike unwinds the carry demand | Barclays (12523) |
| 6 | Fade high HK vs US rates (bias, not yet on) | Low LDR + bearish HK equity momentum argue against sustained HK>US front rates | Liquidity normalises after dividend season | HK funding stress persists (à la 2022 jumbo-hike analogue) | Goldman (13372) |
| 7 | Receive front-end SORA (carry) | Clients see current inflation + USD-rally speed as insufficient to trigger MAS tightening in 2H | MAS holds S$NEER; no 2H tightening | MAS tightens the slope/band in Oct | Goldman (13372) / JPM |
| 8 | Closed: long AUDNZD (booked +0.72%) | Tactical long from 15 Jun taken off after AU data | — (realised) | — (closed) | BNP (12732) |
| 9 | NZD over AUD (rates/FX lean) | NZ inflation set to undershoot RBNZ; AU trimmed mean sticky → RBA can't ease | RBNZ delivers cuts, RBA stuck | AU inflation rolls fast / NZ reflates | JPM (12942), GS (13195) |
| 10 | AUD downside skew ("how low can you go") | AUD below equilibrium fair value; commodity/carry mix | Fair-value model holds; terms-of-trade soften | Iron-ore/terms-of-trade snap-back; RBA hike repriced | BofA (12638) |
| 11 | Fed hold 2026 (rates lean, vs 9 hawkish dots) | Tariff pass-through ending → core-goods disinflation; May PCE not a barrier to hold | Tariff impulse fades; labour cools gently | Core PCE re-accelerates → dots win, Fed hikes | Morgan Stanley (13336) |
| 12 | US reacceleration is a "mirage" (receive-lean bias) | Firm GDP/PCE headlines mask soft underlying demand + income | Real income/demand keep fading | Consumption + income re-accelerate durably | Barclays (13717) |
| 13 | UW THB FX (GBI-EM) | Same baht-overvaluation thesis as #3, expressed in cash FX | Baht mean-reverts from overvalued | Exporter flows keep baht bid | JPM (13290) |
| 14 | Relative SGD NEER resilience | Dollar risk-premium narrative + foreign inflows underpin SGD | USD stays soft into summer | Sharp USD rally / MAS eases slope | Barclays (12522) |
| 15 | Broad EM-local long into oil relief | US–Iran peace deal → Brent −35%; energy-importer EM Asia tailwind | Truce holds; oil stays sub-$80 | Truce breaks / oil re-spikes | Barclays (12523), Citi (13145) |
| 16 | Debasement-trade unwind (gold/USD-hedge reduction) | Post-"Warsh FOMC" positioning unwind top-of-mind at SG client meetings | Warsh-era Fed credible on inflation | Fiscal/inflation fear re-ignites the hedge | Goldman (13372) |

---

## 4. Per-country read

*Ordered by what genuinely moved into 26 Jun. Each block: A) Themes in play (ranked) · B) The "why" (how houses reason) · C) Consensus (≥2 banks: shared claim · evidence · what consensus misses) · D) Differentiated (Bank · Asset · View · Why different · Hidden assumption · Falsifier).*

---

### Australia — the day's biggest mover

#### A. Themes in play

| Rank | Theme | Puzzle piece | What drove it |
|---|---|---|---|
| 1 | Sticky underlying inflation | Inflation / CB reaction function | May trimmed mean 3.6% y/y (survey 3.5), above SoMP path |
| 2 | Labour rebound | CB reaction function | May employment +40.3k, UR 4.4% |
| 3 | RBA hold-vs-hike | Real rates / reaction function | 4.35% held 16 Jun after four hikes; some see +25 to 4.60 |
| 4 | AUD direction | Currency | Fuel-driven headline drop vs sticky core; fair-value debate |
| 5 | Housing re-acceleration | Inflation transmission | New-dwelling +5.6% y/y (May), rents +3.6% |

#### B. The "why" (SYN + VIEW)

Australia moved most this window because two prints pulled in opposite directions and forced the houses to take a side. **FACT:** the May monthly CPI (released 24 Jun) printed headline **4.0% y/y** — a downside miss to the 4.3% survey, driven almost entirely by fuel (automotive-fuel component decelerating as global crude fell) — while the **trimmed mean rose to 3.6% y/y**, *above* the 3.5% survey and up from 3.4% (`econ.fact_indicator` ABS.CPI.TRIMMED_MEAN_M_YOY.AU: Mar 3.3 → Apr 3.4 → May 3.6). The next day (25 Jun) **employment rebounded +40.3k** with unemployment ticking to 4.4%. So the desk is looking at a labour market that reheated and a core inflation gauge that is *rising* while the headline optically improves on cheap fuel.

The house reasoning splits cleanly on whether the headline or the core is the signal. The bulls-on-cuts read the fuel-led headline drop and call the future "lower"; the hawks read the trimmed-mean up-move plus the jobs beat and argue the RBA's re-tightening (3.60→4.35 across Feb–May, `cb_events`) isn't finished. Component depth supports the sticky-core camp: non-tradables held at 4.7% y/y, services firmed to 3.7% (from 3.5%), and new-dwelling inflation *accelerated* to 5.6% — the domestically-generated pieces are not cooling. The pure fuel disinflation is the only thing pulling headline down (electricity is still +21.1% y/y but decelerating off a very high base).

#### C. Consensus views

- **Shared claim (≥2 banks):** headline inflation is falling but underlying/core is too high for comfort; near-term RBA easing is off the table. **Evidence:** JPM (12553) "CPI tracking further below SoMP forecasts" on headline yet flags core; HSBC (12515) "Too high, but the future looks lower"; ANZ (12518/13270) tracks Q2 trimmed mean at ~3.7% q/q-equivalent; UBS (12561) notes fuel "has dropped sharply over Q2, obscuring underlying inflation." **What consensus is missing (SYN):** most notes frame the headline miss as the story and treat the trimmed-mean up-tick as noise; the component depth (services + new-dwelling *rising*) says the underlying impulse is broadening, which the "future looks lower" framing under-weights.

#### D. Differentiated / unique views

| Bank | Asset | View | Why different | Hidden assumption | Falsifier |
|---|---|---|---|---|---|
| Goldman (13195) | Rates | "RBA Uncertainty, RBNZ Confidence" — genuinely two-sided on RBA next move, high conviction RBNZ cuts | Refuses the consensus dovish lean on AU; splits AU vs NZ | Housing/balance-sheet strength keeps AU demand resilient | AU labour cracks → RBA cuts become obvious |
| JPM (12942) | Rates/FX | Positioning should favour **NZD over AUD** | Expresses the AU-stuck / NZ-cutting divergence as a cross | RBNZ eases while RBA can't | AU inflation rolls faster than NZ |
| BofA (12638) | FX | AUD "how low can you go" — below equilibrium fair value | Bearish AUD into a hawkish-RBA tape (contrarian on carry) | Fair-value model dominates near-term rate support | RBA hike repriced / terms-of-trade snap back |
| BNP (12732) | FX | **Closed** long AUDNZD at +0.72% after the data | Took risk off rather than press — colour on where the tactical crowd sits | AU/NZ spread had run its course | — (realised/closed) |

---

### United States — the core-PCE / GDP swing

#### A. Themes in play

| Rank | Theme | Puzzle piece | What drove it |
|---|---|---|---|
| 1 | Sticky core PCE | Inflation / Fed reaction function | May core PCE +0.3% m/m, 3.41% y/y |
| 2 | Growth revision up | Fiscal/growth | Q1 GDP final revised 1.6→2.1% |
| 3 | Hold-vs-hike (9 dots) | Real rates | June dots carry a 2026 hike; Fed held 18 Jun at 3.50–3.75 |
| 4 | Real-demand softness | Growth quality | Real PCE fell −0.1% m/m in May |
| 5 | Debasement-trade unwind | Cross-market flows | Post-"Warsh FOMC" positioning reversal |

#### B. The "why" (SYN + VIEW)

The US window was defined by a firm-nominal / soft-real split. **FACT:** May core PCE index rose to 130.082 from 129.63 = **+0.35% m/m** (rounds to 0.3; above the 0.2 sell-side forecast), core PCE **3.41% y/y** (`econ.fact_indicator` BEA.CPI.PCE_CORE_PRICE_IDX.US). Headline PCE index +0.48% m/m. Nominal personal spending beat at +0.71%, and Q1 GDP was revised *up* to 2.1% from 1.6%. But **real PCE actually fell** in May (16,792,132 → 16,773,429 = −0.11%), and durable-goods orders dropped −4.5%. So the reacceleration is in the price/nominal series, not in real volumes.

This is why the two flagship US notes land on opposite conclusions from the same data. The hold-camp (MS) reads the core-goods disinflation pipeline (tariff pass-through ending) and says the May PCE doesn't force a hike despite nine FOMC participants penciling one. The dovish-skeptic (Barclays) reads the real-demand and income softness and calls the whole reacceleration a "mirage," keeping a Fed-on-hold-then-eventually-easier bias. Citi ("The economy is not overheating") sits with the not-overheating read and a ~1.9% Q2 GDP track. The debate is squarely hold-vs-hike — nobody in this window is arguing for a near-term cut.

#### C. Consensus views

- **Shared claim (≥2 banks):** the Fed stays on hold in 2026; the June dots' hike bias is not the base case. **Evidence:** MS (13336) "The data road map to rate hikes" retains no-hike baseline despite 9 hawkish dots; Citi (13661) "The economy is not overheating," Q2 GDP ~1.9%; Barclays (13717) Fed "remains on hold." **What consensus is missing (SYN):** consensus leans on "tariff pass-through is ending" to deliver core-goods disinflation — if that pass-through instead lingers (or a fresh tariff round lands), the 0.3% m/m core prints stop being a one-off and the nine dots become the base case. Consensus is short that tail.

#### D. Differentiated / unique views

| Bank | Asset | View | Why different | Hidden assumption | Falsifier |
|---|---|---|---|---|---|
| Morgan Stanley (13336) | Rates | Fed **holds** all 2026 despite 9 dots carrying a hike; lays out exact data that would flip them | Explicitly maps its own falsifiers rather than asserting | Tariff pass-through ends → core-goods disinflation | Core PCE re-accelerates / labour stays hot → hike |
| Barclays (13717) | Rates/macro | Reacceleration is a **"mirage"** — headlines firm, underpinnings fragile | Fades the strong GDP/PCE tape on income/real-demand internals | Real income + demand keep decelerating | Durable consumption + income re-accelerate |
| Goldman (13372) | Cross-asset/FX | **Debasement-trade unwind** post-Warsh FOMC is the dominant client flow | Frames US via a positioning/flow lens, not a data lens | Warsh-era Fed seen as inflation-credible | Fiscal/inflation fear re-ignites the USD-hedge |

---

### India — the RBI-pushback / FCNR story

#### A. Themes in play

| Rank | Theme | Puzzle piece | What drove it |
|---|---|---|---|
| 1 | RBI reaction function | CB reaction function | Gov publicly pushes back on hike pricing (unscheduled ET interview) |
| 2 | FCNR / capital-attraction package | Fiscal / flows | Six-point RBI+MoF package incl. FCNR(B) swap window |
| 3 | Rate-hike pricing | Real rates | 1y OIS prices +85bp of hikes (Oct/Dec-centred) |
| 4 | IGB relative value | Cross-market | 10y IGB cheap on 5x10x30 fly at series highs |
| 5 | Inflation path | Inflation | CPI 4.5% y/y May; houses see peak ~5.9% Q3 FY27 |

#### B. The "why" (SYN + VIEW)

India is the cleanest reaction-function story in the window. **VIEW (GS 12546):** the RBI Governor used an unscheduled interview with ET to *directly push back* on market hike pricing — GS reads this as "little appetite to use domestic rates to defend the INR, either in policy rates or via a higher overnight fix within the corridor." Against that, the OIS curve carries **+85bp of hikes** in 1y, concentrated on the Oct/Dec meetings. That gap — market pricing tightening the Gov is signalling away from — is the entire trade.

Overlaid on it is the flow plumbing. **VIEW (Barclays 12522):** the June MPC's headline wasn't the repo pause (held 5.25%, `cb_events`) but a **six-point RBI+MoF package to attract foreign capital**, including a special FCNR(B) deposit-swap window that fully hedges banks' cost on 3–5y NRI deposits, plus a concessional FX-swap facility. GS notes the FCNR flow is distorting the NDS/XCCY basis and, together with an RBI discount, is a reason 10y IGBs look cheap (5x10x30 fly at series highs; 10y the best RV point on the curve). On inflation, Barclays sees CPI at 4.5% y/y (May), rising into June on fuel, peaking ~5.9% in Q3 FY27 near the top of the 2–6% band — but with core "contained so far," which is what lets the RBI hold and jawbone rather than hike.

#### C. Consensus views

- **Shared claim (≥2 banks):** RBI stays on hold near-term and the capital-attraction / FCNR package is the real policy lever, not the repo rate. **Evidence:** GS (12546) RBI pushing back on hike pricing; Barclays (12522) "repo pause was not the highlight… the slew of measures took the spotlight." **What consensus is missing (SYN):** consensus treats the FCNR/flow package as unambiguously INR-supportive; less discussed is that a fully-hedged bank swap window transmits into the FX-forward/XCCY basis and can move the *hedged* cost of INR assets even if spot behaves — a second-order effect the flow-desk (GS) sees but the macro notes underplay.

#### D. Differentiated / unique views

| Bank | Asset | View | Why different | Hidden assumption | Falsifier |
|---|---|---|---|---|---|
| Goldman (12546) | Rates | **Receive 2y INR** — fade the +85bp of priced hikes | Trades directly against market pricing on a reaction-function call | RBI won't use domestic rates to defend INR | RBI hikes / lifts o/n fix to defend a falling rupee |
| Goldman (12546) | Rates | **Long 10y IGB** (vs OIS / on-curve) — best RV point | Uses the FCNR/XCCY distortion as an entry, not a risk | FCNR flow persists; supply orderly | Bond-supply shock; fly re-richens |
| Barclays (12522) | Macro/FX | CPI peaks ~5.9% Q3 FY27, core contained → RBI can hold and jawbone | Explicit inflation-peak path underpinning the hold | Fuel pass-through is the transient driver | Core breaks higher → RBI forced to hike |

---

### Japan — Tokyo CPI up, but for the "wrong" reason

#### A. Themes in play

| Rank | Theme | Puzzle piece | What drove it |
|---|---|---|---|
| 1 | Tokyo CPI composition | Inflation | Core (ex-FF) 1.6% y/y (from 1.3); ex-FF&energy 1.9% |
| 2 | BoJ normalisation path | CB reaction function | 16 Jun hike to 1.00%; next hike Q4-priced |
| 3 | JGB curve / basis | Rates | BoJ purchase taper by bucket; 10y ~2.27% |
| 4 | Oil pass-through | Inflation | Higher crude pass-through "remains limited" |

#### B. The "why" (SYN + VIEW)

Japan's 26-Jun print is a composition story. **FACT:** Tokyo core CPI (ex-fresh-food) rose to **1.6% y/y** from 1.3% (in line), and ex-fresh-food-&-energy to **1.9%** (above the 1.8 survey). **VIEW (Nomura 13337):** the pick-up is "largely due to policy factors" — the disappearance of last year's water-charge subsidy base effect — and crude-oil pass-through "remains limited." So the underlying-underlying gauge (1.9%) firmed, but the headline core move is mechanical, not fresh demand-pull.

For rates, the plumbing note (Nomura Yen Rates Daily, 13407/12612) shows the BoJ's JGB purchases by maturity bucket and the taper progressing; the 10y sits ~2.27% with the basis grinding. **SYN:** with the BoJ already at 1.00% and Tokyo underlying at 1.9%, the composition split matters — a policy-driven headline gives the BoJ cover to *pause* while the ex-energy firming keeps the next-hike option (Q4-priced across the forecast tables) alive. Note the grounding caveat: Japan carries almost no `econ.fact_indicator` depth (5 series, stale), so the component read here leans on cb_events + sell-side, not on a loaded ABS-equivalent.

#### C. Consensus views

- **Shared claim (≥2 banks):** BoJ continues gradual normalisation; the next hike is a Q4-2026 event, not imminent. **Evidence:** cross-house forecast tables (Barclays 12897, SocGen 13657) both pencil a further +25 to 1.25% in Q4-2026; Nomura (13337) frames the CPI up-move as policy-driven, consistent with no rush. **What consensus is missing (SYN):** the ex-FF&energy 1.9% above-survey print is under-emphasised — if the mechanical base effects fade *and* underlying stays ~1.9%, the "gradual" cadence could compress faster than the Q4 base case.

#### D. Differentiated / unique views

| Bank | Asset | View | Why different | Hidden assumption | Falsifier |
|---|---|---|---|---|---|
| Nomura (13337) | Macro | Tokyo CPI rise is policy-driven, oil pass-through limited → discounts the headline | Reads *through* the print rather than reacting to the core up-tick | Base effects, not demand, drive the move | Underlying (1.9%) sustains after base effects roll off |

---

### Hong Kong — funding-driven, band-anchored

#### A. Themes in play

| Rank | Theme | Puzzle piece | What drove it |
|---|---|---|---|
| 1 | USDHKD toward upper band | Currency | Carry + dividend-season USD demand |
| 2 | Front-end HKD IRS/HIBOR | Rates / flows | Low HKMA aggregate balance → front-IRS pressure |
| 3 | HK-vs-US rate spread | Cross-market | Low LDR + weak HK equities argue against sustained HK>US |

#### B. The "why" (SYN + VIEW)

HK is a pure plumbing story — no policy rate (currency board; the only HK rate row in cb_events, "Composite Interest Rate," is stale to 2008, correctly flagged). **VIEW (Barclays 12523):** USD demand (dividend-payment season + carry) keeps USDHKD supported; after consolidating 7.83–7.84 they see it toward the 7.75–7.85 convertibility-band middle later this year. On rates, the HKMA aggregate balance has stayed low, keeping upward pressure on the front-end IRS curve, so Barclays expects HKD front IRS to underperform USD IRS near-term. **VIEW (GS 13372):** opposite side of the same coin — GS is *biased to eventually fade* high HK-vs-US rates given a low loan-to-deposit ratio and bearish HK equity momentum, invoking the 2022 jumbo-hike episode as the analogue for how these funding spikes eventually normalise. HK econ depth is modest (29 series) but the trade is a liquidity/basis call, not a data call.

#### C. Consensus views

- **Shared claim (≥2 banks):** HK front-end funding pressure is real and dividend-season-driven; the convertibility band is not in question. **Evidence:** Barclays (12523) low aggregate balance → front-IRS pressure; GS (13372) acknowledges high HK vs US rates now. **What consensus is missing (SYN):** the two houses agree on the *now* but disagree on *duration* — Barclays plays the near-term pressure, GS the eventual fade — which is the actual decision, and neither frames the crossover timing precisely.

#### D. Differentiated / unique views

| Bank | Asset | View | Why different | Hidden assumption | Falsifier |
|---|---|---|---|---|---|
| Goldman (13372) | Rates | **Bias to fade** high HK vs US rates (not yet on) | Contrarian to the near-term-pressure crowd | Liquidity normalises post-dividends; weak HK equities cap rates | Funding stress persists (2022-style) |
| Barclays (12523) | Rates/FX | Play the **near-term** front-IRS pressure + USDHKD to upper band | Trades the immediate plumbing, opposite horizon to GS | Aggregate balance stays low into dividend season | HKMA injects liquidity |

---

### Thailand — the baht-overvaluation funder

#### A. Themes in play

| Rank | Theme | Puzzle piece | What drove it |
|---|---|---|---|
| 1 | BoT on hold | CB reaction function | Held 1.00% on 24 Jun |
| 2 | Baht overvaluation | Currency | THB "fundamentally overvalued," competitiveness drag |
| 3 | Oil-relief tailwind | Cross-market | Brent sub-$80 helps the importer |

#### B. The "why" (SYN + VIEW)

**FACT:** BoT held at 1.00% on 24 Jun (survey 1.0). With the policy rate effectively at a floor, the live debate is the currency. **VIEW (JPM 13290):** the baht is "fundamentally overvalued," and surging investment plus policy resistance to a weaker currency make THB a natural *funder* — its strength is a vulnerability because Thai manufacturing competitiveness is challenged by China's excess-capacity export glut. JPM is bearish THB local-currency and expresses it two ways: pay 1y1y THB (vs SGD) in rates, and UW THB in cash FX on the GBI-EM. The oil-relief theme (Citi 13145, "Through the Oil Shock: Five Lenses on ASEAN") is a supportive macro backdrop for the importer but doesn't change the overvaluation call. Thailand carries no `econ.fact_indicator` depth (see §5), so this read is cb_events (the hold) plus sell-side.

#### C. Consensus views

- **Shared claim (≥2 banks):** BoT is at/near its floor and the baht's real strength is the key macro vulnerability. **Evidence:** JPM (13290) overvaluation + funder thesis; Citi (13145) frames ASEAN via the oil shock reversing, THB an importer beneficiary. **What consensus is missing (SYN):** the oil-relief bulls and the overvaluation bears are talking past each other — cheaper oil *improves* Thailand's external balance, which could keep the baht bid and delay the mean-reversion the funder trade needs.

#### D. Differentiated / unique views

| Bank | Asset | View | Why different | Hidden assumption | Falsifier |
|---|---|---|---|---|---|
| JPM (13290) | Rates/FX | **Pay 1y1y THB (vs SGD)** + **UW THB FX** — baht as funder | Turns a valuation view into a paired funding trade | Policy resists baht strength; China glut persists | BoT tolerates strength / exporter flows keep baht bid |

---

### Indonesia — surprise hawkish hold, then hike

#### A. Themes in play

| Rank | Theme | Puzzle piece | What drove it |
|---|---|---|---|
| 1 | BI hike (currency defence) | CB reaction function | +25 to 5.75% on 18 Jun (forecast had been +50) |
| 2 | Local-market carry | Cross-market | IndoGB / IDR positioning |
| 3 | Instrument view | — | PENDING DEEPAK |

#### B. The "why" (SYN + VIEW)

**FACT:** Bank Indonesia hiked the BI-Rate +25bp to **5.75%** on 18 Jun (from 5.50%; deposit-facility 4.75%, lending-facility 6.5% — `cb_events`). The sell-side forecast tables had carried a *larger* +50 move (Barclays 12897 shows "Tightening: 20 May 26 … Jun 26 (+50)"), so the delivered +25 is, relative to some house paths, a *dovish surprise within a hawkish action* — BI tightened for currency defence but by less than the hawks feared. Forecast tables now diverge on the path: BofA (13084) pencils cuts back toward 5.00% then 4.75% into 2027, while Barclays/SocGen carry BI flat-to-lower. **VIEW (Citi 13279):** the Asia model overlay shows a small IDR / 5y IndoGB overweight via cash. **SYN:** Indonesia has good `econ.fact_indicator` depth (303 series) but the day's action is a rate decision + flow call, not a component-data day.

**Instrument note (impersonal): the specific Indonesia instrument to wire into the standing read is PENDING DEEPAK and is not asserted here.**

#### C. Consensus views

- **Shared claim (≥2 banks):** BI's June hike is a currency-defence move, and the medium-term path is toward easing once IDR stabilises. **Evidence:** BofA (13084) forecasts BI to 5.00%/4.75% by 2027; Barclays (12522) IDR forecast path 17,600–18,200. **What consensus is missing (SYN):** the delivered +25 vs the feared +50 is the actual surprise, and houses have not fully re-anchored the front-end path to it — the forecast tables still range widely (5.00 to 5.75 near-term).

#### D. Differentiated / unique views

| Bank | Asset | View | Why different | Hidden assumption | Falsifier |
|---|---|---|---|---|---|
| BofA (13084) | Rates | BI **eases** back to 5.00% then 4.75% into 2027 | Most dovish forward path vs flat-carriers | IDR stabilises → BI can unwind defence | IDR pressure persists → BI holds/hikes |
| Citi (13279) | FX/Rates | Small **IDR + 5y IndoGB overweight** (model overlay) | Expresses constructive carry despite the hike | Carry compensates for residual FX risk | IDR sell-off overwhelms carry |

---

### Malaysia — the electronics/AI trade-surplus story

#### A. Themes in play

| Rank | Theme | Puzzle piece | What drove it |
|---|---|---|---|
| 1 | Trade-surplus surge | External / flows | Surplus doubled to ~19% GDP on electronics/AI capex |
| 2 | Exporter FX conversion | Currency | Excess FX deposits +$7bn to 6.2% GDP |
| 3 | BNM on hold | CB reaction function | OPR 2.75% (held 7 May) |

#### B. The "why" (SYN + VIEW)

**VIEW (JPM 13290):** Malaysia's trade surplus has *doubled to ~19% of GDP* over the past year on an electronics-export surge tied to "relentless AI-capex spending." The catch is conversion — exporters aren't repatriating, with excess FX deposits rising $7bn to 6.2% GDP, so the ringgit isn't getting the full benefit of the external strength. **SYN:** BNM is on hold at 2.75% (`cb_events`, 7 May), so MYR is a flow/conversion story rather than a rate story; the AI-capex export cycle (a genuine 2026 theme) is doing the macro work. Malaysia has no `econ.fact_indicator` depth loaded (§5), so this is a sell-side + cb_events read.

#### C. Consensus views

- **Shared claim (≥2 banks):** Malaysia's external position is strong on the electronics/AI cycle; BNM comfortably on hold. **Evidence:** JPM (13290) surplus doubling; ANZ (12890) "tech supercycle lends staying power." **What consensus is missing (SYN):** the poor exporter-conversion dynamic caps how much of the surplus translates into MYR strength — the bullish-external narrative may not deliver a bullish-currency outcome.

#### D. Differentiated / unique views

| Bank | Asset | View | Why different | Hidden assumption | Falsifier |
|---|---|---|---|---|---|
| JPM (13290) | FX/flows | External strength ≠ MYR strength while conversion lags | Focuses on the flow-plumbing, not the headline surplus | Exporters keep hoarding FX | Conversion normalises → MYR catches up |

---

### Singapore — SORA carry, no MAS tightening priced

#### A. Themes in play

| Rank | Theme | Puzzle piece | What drove it |
|---|---|---|---|
| 1 | Front-end SORA carry | Rates | Clients receiving front SORA for carry |
| 2 | S$NEER resilience | Currency | Dollar risk-premium + inflows underpin SGD |
| 3 | IP miss | Growth | Industrial production 13.0% y/y vs 17.5 survey |

#### B. The "why" (SYN + VIEW)

**FACT:** SG industrial production printed **13.0% y/y** on 26 Jun, a miss to the 17.5 survey (prior revised to 16.5). Singapore has no policy rate — MAS runs the S$NEER — so the trades are rates-carry and currency. **VIEW (GS 13372):** most clients still like *receiving front-end SORA for carry*, judging that current inflation and the speed of the USD rally are not enough to trigger MAS liquidity tightening in 2H. **VIEW (Barclays 12522):** SGD-NEER should stay relatively resilient on the broad dollar risk-premium narrative and foreign inflows. **SYN:** the IP miss is a growth wobble but doesn't touch the core view — the SG read is a carry + no-2H-MAS-tightening consensus.

#### C. Consensus views

- **Shared claim (≥2 banks):** no MAS tightening in 2H-2026; front-end SORA carry attractive, SGD-NEER resilient. **Evidence:** GS (13372) receive-SORA carry; Barclays (12522) SGD-NEER resilience. **What consensus is missing (SYN):** it's a consensus-crowded carry position — the risk isn't the base case but the exit, if a sharp USD rally forces MAS to lean on the slope.

#### D. Differentiated / unique views

| Bank | Asset | View | Why different | Hidden assumption | Falsifier |
|---|---|---|---|---|---|
| Goldman (13372) | Rates | Receive front-end **SORA** for carry | Positioning/colour from SG client meetings, not a model call | MAS holds; USD rally too slow to force tightening | MAS tightens slope in Oct |

---

### Philippines — quiet after the hike

#### A. Themes in play

| Rank | Theme | Puzzle piece | What drove it |
|---|---|---|---|
| 1 | BSP hike | CB reaction function | +25 to 4.75% on 18 Jun |

**B–D (short, honest note):** Beyond the 18 Jun BSP hike to 4.75% (from 4.50%, `cb_events`), nothing PH-specific resonated in the 24–26 Jun flow — PH appears in cross-EM forecast tables (Barclays USDPHP path 60.0–62.0; BofA) but no differentiated stand-alone PH note landed in the window. No `econ.fact_indicator` depth loaded for PH. Consensus (implicit, from forecast tables): BSP holds after the June hike, peso range-bound. No differentiated single-country view to surface. **Calendar-only / no differentiated flow this window.**

---

### New Zealand — the "confident-cuts" counterpart to AU

#### A. Themes in play

| Rank | Theme | Puzzle piece | What drove it |
|---|---|---|---|
| 1 | RBNZ easing confidence | CB reaction function | Houses see inflation undershooting RBNZ forecasts |
| 2 | NZD vs AUD | Currency | NZ cuts vs AU stuck |

#### B. The "why" (SYN + VIEW)

NZ is covered almost entirely as the mirror of Australia. **VIEW (GS 13195):** "RBNZ Confidence" — GS expects inflation to *undershoot* RBNZ forecasts, giving the RBNZ room to keep easing (OCR 2.25%, held 27 May, next 8 Jul). **VIEW (JPM 12942):** positioning should favour NZD over AUD precisely because RBNZ can cut while the RBA is stuck on sticky trimmed mean. **SYN:** NZ has deep `econ.fact_indicator` depth (1,112 series) but no NZ-specific data printed in this window (last obs 31 May) — so this is a reaction-function/relative-value read, not a data day. The RBNZ-confident / RBA-uncertain split is the single cleanest cross in the APAC flow.

#### C. Consensus views

- **Shared claim (≥2 banks):** RBNZ has more easing room than the RBA; NZ inflation undershoots. **Evidence:** GS (13195) undershoot call; JPM (12942) NZD-over-AUD. **What consensus is missing (SYN):** the trade is a *relative* one — if AU inflation rolls over faster than expected, the RBA catches down to the RBNZ and the divergence trade compresses.

#### D. Differentiated / unique views

| Bank | Asset | View | Why different | Hidden assumption | Falsifier |
|---|---|---|---|---|---|
| Goldman (13195) | Rates | RBNZ eases with **confidence**; inflation undershoots forecasts | Pairs high-conviction NZ against explicitly-uncertain AU | NZ disinflation sustained | NZ inflation re-firms |

---

### United Kingdom — calendar-only

**A–D (short, honest note):** No differentiated UK single-country note resonated in the 24–26 Jun flow; the UK appears only in cross-house global forecast tables (BoE Bank Rate 3.75% held 18 Jun, `cb_events`; houses split on the timing of the *next cut*, generally H2-2027 in the tables — Barclays 12897, HSBC 13112). Imminent: mortgage approvals (29 Jun, 63.0 survey) and final Q1 GDP (30 Jun, 0.6% q/q). **UK `econ.fact_indicator` depth is thin (6 series) — say so, no depth faked.** Consensus (from tables): BoE on hold; no near-term move. No differentiated view to surface.

---

### Canada — calendar-only

**A–D (short, honest note):** No differentiated Canada single-country note in the window; BoC held at 2.25% on 10 Jun (`cb_events`), appearing only in global forecast tables. The live item is imminent, not printed: **GDP MoM on 30 Jun (survey 0.4% vs prior −0.1%)** — a rebound the tables expect. **CA `econ.fact_indicator` depth is thin (4 series, stale to Apr) — no depth faked.** No differentiated view to surface this window. **Calendar-only.**

---

## 5. Grounding ledger

*Sources and layers only. Three layers kept separate: what printed (cb_events) · component depth (fact_indicator) · views/trades/quotes (fact_chunk + Qdrant semantic search + ingested Outlook rows). Confidence and disagreements flagged.*

**Layer 1 — What printed + surprise (`calendar.cb_events`).** All policy-rate levels, last-move dates, held/hiked/cut tags, and the §2 actual/survey/prior figures are read directly from cb_events rows for country_ids 3/7/20/22/24/26/27/30/31/35/37/42/43/46/47, event_date window 24–26 Jun (plus last-decision lookback and next-meeting forward scan). RBA hiking sequence (3.60→3.85→4.10→4.35, Feb–May) verified against four dated decision rows. BoJ +25→1.00, ID +25→5.75, PH +25→4.75 all verified against dated rows. Banxico (MX) held 6.5% and BoT held 1.0% verified.

**Layer 2 — Component depth (`econ.fact_indicator`).** Deep and used: **AU** (539 series; CPI headline/trimmed-mean/weighted-median + goods/services/non-tradables/housing/rents/new-dwelling/electricity components, latest obs 2026-05-01 — the print released 24 Jun); **US** (219 series; core & headline PCE chain indices + real PCE, latest obs 2026-05-01 — the May print released 25 Jun); **IN** (1,459), **NZ** (1,112), **ID** (303), **HK** (29) available. **Thin/absent — no depth faked:** JP (5 series, stale to Apr), CA (4, stale to Apr), UK (6). **No `econ.fact_indicator` rows at all:** TH, MY, SG, PH — those reads are cb_events + sell-side only, stated inline.

**Layer 3 — Views / trades / quotes (`research.dim_report` + `research.fact_chunk` + Qdrant semantic search + ingested Outlook rows).** ~1,400 reports in the 24–26 Jun window across 20+ vendors. Per-theme Qdrant semantic queries run for: CB reaction-function/trades, India RBI/FCNR/rupee, US core-PCE/GDP/Fed, Japan BoJ/Tokyo-CPI/JGB, ASEAN (TH/ID/MY/SG/PH) rates-FX. Report IDs cited: **AU/NZ** 13195, 12942, 12638, 12732, 12553, 12515, 12518, 13270, 12561, 13333; **US** 13336, 13717, 13661, 13372; **IN** 12546, 12522; **JP** 13337, 13407, 12612; **HK** 12523, 13372; **TH/ASEAN** 13290, 13145, 13279; **ID** 13084, 13279; **MY** 13290, 12890; **SG** 13372, 12522; cross-EM forecast tables 12897, 13112, 13657, 12688. Outlook desk-commentary rows (source_type=desk_commentary) present in the window for DB/GS/Nomura and folded into the flow read.

**Flags:**
- **Unreconciled (AU CPI):** cb_events carries two AU CPI representations on 24 Jun — a "CPI YoY" row (actual 4.0 vs survey 4.3) and a separate "trimmed mean YoY" row (actual 3.6 vs survey 3.5). Both are shown; the headline-miss / core-beat split is the real signal and is flagged rather than collapsed.
- **Sell-side-reported, not yet BQL-booked (~95%):** RBA "+25 to 4.60" hike-path calls, the India "+85bp priced in 1y OIS," and next-hike timings (BoJ Q4, etc.) are from house forecast tables, not booked cb_events rows — tagged VIEW.
- **Not booked forward:** IN and CA next-meeting dates are not in cb_events; shown as estimated cadence.
- **HK stale row:** the only HK rate row ("Composite Interest Rate") is dated 2008; HK is a currency board with no independent policy rate — represented as such, not as a live decision.
- **Indonesia instrument:** the specific standing-read instrument is PENDING DEEPAK — not asserted anywhere in this digest.
- **PH / UK / CA:** honest short notes — no differentiated single-country flow resonated in the window; not dropped.
