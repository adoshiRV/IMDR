---
edition: daily
date: 2026-07-03
---

# Spider — Daily Macro Research Digest

**Window:** rolling day into 2026-07-03 (flow 2026-07-02 → 2026-07-03) · **Edition:** Daily · **Universe:** AU · NZ · JP · IN · TH · ID · MY · SG · HK · PH · US · CA · UK

> FX/rates PM lens. Number-first, low-opinion. Sell-side is treated as motivated until the numbers say otherwise. Trades are surfaced with assumption + falsifier — never rated. Every table row is explained in the prose beneath it.
>
> **Grounding legend:** FACT = printed/decision (`calendar.cb_events`) · DEPTH = component series (`econ.fact_indicator`) · VIEW = sell-side interpretation (`research.fact_chunk` + Qdrant) · PRICING = market-implied · SYN = synthesis.

---

## Deltas since 07-02  *(SYN — lead with what changed)*

1. **US June payrolls printed a large downside miss: +57K vs 110K consensus, prior revised down to 129K (from 172K)** (FACT, `cb_events` row 21819). Private payrolls +49K; unemployment *fell* to 4.2% but on a **falling participation rate (61.5% from 61.8%)** — a mechanical, not a healthy, decline. This supersedes the 07-02 "hawkish repricing / farewell to Fed cuts" frame: the sell-side pivoted the same day to "the hike case was just revised away," with the live debate now hike-dead-but-is-the-cut-case-alive.
2. **Australia swung to a goods-trade deficit: A\$-3.018B vs A\$2.2B survey** (FACT, row 21802) — a sharp miss on weaker metal-ore exports.
3. **New Zealand's Jul-8 call converged toward a hike:** `cb_events` forecast now **2.50%** (was hold-2.25% at the 07-02 run); UBS, HSBC, Nomura joined ANZ calling a July +25bp; Westpac remains the lone hold-to-September holdout.
4. **BNP raised its BoJ terminal-rate forecast to 2.50%** (VIEW, 15399) — a new hawkish outlier on Japan, on AI-boom growth and firm household spending; USD/JPY came *off* its highs post-NFP.
5. **UBS turned outright bearish IDR** ("Pause or Turning Point?", 15130) — sees USD/IDR to 18,500-19,000 in 2H and BI's 100bp of hikes "insufficient," cutting against the "defence holds" read.
6. **New post-NFP trades:** MS re-enter UST curve steepeners (15365); BNP close JPY 2s5s10s (15134); DB take profit on sterling longs / kiwi shorts (15145); HSBC close sell SGD-INR — stopped at 74.00 (15099).

---

## 1. CB / macro dashboard  *(FACT — `calendar.cb_events`)*

One row per covered country. Policy rate = last decided rate on a verified decision row; last move and next event verified against `cb_events`.

| Country | Policy rate | Last move (verified) | Next scheduled | Bias / key issue |
|---|---|---|---|---|
| United States | 3.75% | Held 2026-06-17 (dots up) | FOMC minutes 07-08 | **NFP miss (57K) reopens the cut debate**; Warsh dovish-tilted |
| Japan | 1.00% | **Hiked +25bp** 2026-06-16 (from 0.75%) | (post-window) | Tankan firm; BNP lifts terminal to 2.50%; USD/JPY off highs |
| Indonesia | 5.75% | **Hiked +25bp** 2026-06-18 (from 5.50; +25bp 06-09) | (post-window) | Inflation broadening; UBS bearish IDR vs JPM further-hikes-to-6.00% |
| Australia | 4.35% | Held 2026-06-16 | RBA speech (Hunter) 07-08 | **Trade swings to deficit**; neutral-rate debate; PMIs back >50 |
| New Zealand | 2.25% | (prior decision) | **RBNZ decision 2026-07-08** | Now near-consensus **+25bp to 2.50%**; Westpac lone hold |
| United Kingdom | 3.75% | Held 2026-06-18 (vote 7/2/0 — 2 hike dissents) | Bailey 07-03; services PMI 07-03 | Sticky; hawkish vote drift; gilt-curve steepening thesis |
| Canada | 2.25% | Held 2026-06-10 | Business Outlook Survey 07-06 | Steady BoC; mfg PMI back to 53.0 |
| India | 5.25% | Held 2026-06-05 | Services PMI 07-03 | RBI-inflows theme live; June CPI/monsoon the watch |
| Philippines | 4.75% | **Hiked +25bp** 2026-06-18 (from 4.50) | (post-window) | EM-tightening cluster; external balance improving |
| Thailand | 1.00% | Held 2026-06-24 | BoT minutes 07-08 | Soft H2; StanC "challenging H2"; oil-relief overlay |
| Malaysia | 2.75% | (prior decision) | **BNM decision 2026-07-09** | "La pausa" — houses expect hold |
| Hong Kong | USD peg / LAF | — (linked to Fed) | — | Peg follows Fed; May data soft (JPM 15266) |
| Singapore | MAS S\$NEER band | — (band, not a rate) | **MAS review (July)** | Composite PMI 57.4 strong; houses lean to a slight July easing |

**SYN — state of the world:** the hawkish base of the past week (Fed dots up, post-hike BoJ, June EM hikes) met a **dovish US labour shock**. The June payrolls miss (57K, prior revised down, participation falling) is the day's gravity — it kills the reacceleration/hike narrative and reopens a two-way Fed debate, with houses split between "cuts are coming" (Citi, BNP) and "noise, steady Fed" (DB, MS). Around it: Antipodean divergence widened (RBNZ toward a July hike; AU into a trade deficit), Japan's hike-path debate hardened (BNP terminal 2.50%), and Indonesia gained a genuine bear (UBS) against the further-hiker (JPM).

---

## 2. Calendar — releases + CB events with rate relevance  *(FACT — `cb_events`; pure calendar, no view)*

Consensus (`survey`/`forecast`) shown where present; `actual` shown only where the row carries one. `®` = prior revised. Times UTC.

| Date | Country | Event | Consensus | Prior | Actual |
|---|---|---|---|---|---|
| **07-02** | **US** | **Non-farm payrolls** | 110K | 129K ® (was 172K) | **57K** |
| 07-02 | US | Private payrolls | 110K | 97K ® | **49K** |
| 07-02 | US | Unemployment rate | 4.3% | 4.3% | **4.2%** |
| 07-02 | US | Participation rate | 61.7% fcst | 61.8% | **61.5%** |
| 07-02 | US | Average hourly earnings MoM / YoY | 0.3% / — | 0.3% / 3.4% | 0.3% / 3.5% |
| 07-02 | US | Initial jobless claims | 220K | 216K ® | 215K |
| 07-02 | US | U-6 unemployment | — | 8.1% | 7.9% |
| 07-02 | US | Factory orders MoM | -1.8% | 5.3% ® | -1.3% |
| **07-02** | **AU** | **Balance of trade** | A\$2.2B | A\$1.383B ® | **A\$-3.018B** |
| 07-02 | AU | Services / composite PMI final | 49.9 / 49.8 | 48.7 / 48.7 | 50.5 / 50.4 |
| 07-02 | CA | S&P Global mfg PMI | 53.4 fcst | 52.9 | 53.0 |
| 07-02 | SG | SIPMM manufacturing PMI | 50.4 fcst | 51.0 | 51.3 |
| 07-03 | JP | Composite / services PMI final | 52.5 / 51.8 | 51.1 / 50.0 | 52.8 / 52.2 |
| 07-03 | SG | S&P Global PMI | 51.5 fcst | 56.7 | 57.4 |
| 07-03 | IN | HSBC services / composite PMI final | 58 / 57.4 | 59.8 / 59.3 | not booked |
| 07-03 | UK | Services / composite PMI final; Bailey; DMP 1y CPI exp | 48.7 / 49.4 | 49.3 / 49.7 / 3.7% | not booked |
| **07-08** | NZ | **RBNZ interest-rate decision** | **hike 2.50%** (fcst) | 2.25% | forward |
| **07-08** | TH | BoT meeting minutes | — | — | forward |
| **07-08** | US | FOMC minutes | — | — | forward |
| **07-09** | MY | **BNM interest-rate decision** | hold 2.75% (fcst) | 2.75% | forward |

---

## 3. Cross-cutting trade-ideas table  *(VIEW / trade recommendation — provenance tagged; not judged)*

Distilled from the fresh-window fact-chunk sweep + per-theme Qdrant search. Each row is expanded in the country read.

| # | Trade | Key driver / rationale | Assumption it rests on | Falsifier | Provenance (report_id) |
|---|---|---|---|---|---|
| 1 | **Re-enter UST curve steepeners** (6-7y sector) | Soft NFP + expected more soft prints; carry + roll | Labour softening drives front-end lower over time | A re-accelerating jobs trend / sticky inflation | MS US Rates (15365) |
| 2 | **Buy 10y TIPS with payer protection** | Breakevens cheap; investors "paying for protection vs 6% rates" | Real-yield range-top; hawkish tail overpriced | Inflation rolls over / real yields break higher | MS (14751, 15186) |
| 3 | **Close JPY 2s5s10s** (belly 5y→10y) | Post-BoJ curve repositioning; 2s5s10s richened | The belly move has played out | Fresh BoJ hawkish surprise re-steepens | BNP JPY rates (15134) |
| 4 | **Take profit: long GBP (vs EUR) / cover kiwi shorts** | Trades matured; UK Chancellor choice a residual risk | GBP strength + NZD downside largely realised | UK leadership shock / RBNZ hold reverses NZD | DB FX (15145) |
| 5 | **Sell EUR/INR** | RBI inflow measures; lower INR vol | FCNR(B)/ECB inflows land; risk stays benign | Inflows stall / global risk-off hits INR | BNP FX (14665) |
| 6 | Constructive **INR FX + bonds** | Improving carry + narrowing C/A + RBI measures | Carry holds; C/A keeps narrowing | Oil re-spike widens C/A | Goldman (14730) |
| 7 | NZ: position for **RBNZ +25bp Jul-8** | Near-consensus hike; forecast now 2.50% | RBNZ delivers; oil-shock persistence sticks | Governor invokes his oil/growth off-ramp | ANZ (14581), UBS (15127), HSBC (15246) |
| 8 | **Fade the yen move** (close JPY shorts / take FX-vol profit) | Intervention threat near-imminent; USD/JPY off highs | Threat + soft NFP cap the top | Disorderly break past 163 with no execution | HSBC (14595), BNP (14478) |
| 9 | Receive **2Y MYR NDIRS / THB curve** | Post-Iran EM tightening-expectations unwind; liquidity | Regional rates re-rally as risk premium fades | Renewed oil/geopolitical shock | StanC (15035) |
| 10 | HY credit: **cut duration** | Macro (rates) drives HY here, not spreads | Rate path stays the swing factor | A spread event dominates rates | Citi (14721) |

**SYN:** the post-NFP book tilts toward **duration/steepeners** (rows 1, 2) and **profit-taking on trades that had run** (rows 3, 4, 8). The India-inflows cluster (rows 5, 6) persists; a fresh Asia-rates receiver theme (row 9) emerged on the post-Iran unwind. HSBC's SGD-INR was stopped at 74.00 — noted in the India read.

---

## 4. Per-country read  *(A themes · B the "why" · C consensus · D differentiated)*

Ordered by what moved this window. Flagship/desk notes read at the chunk level for the movers. Consensus (≥2 independent banks) and differentiated views separated. Trades surfaced with assumption + falsifier only.

---

### United States — a soft payrolls print reopens the Fed debate

**A. Themes in play**

| Rank | Theme | Assets | Banks talking | Why it matters to the PM |
|---|---|---|---|---|
| 1 | **NFP miss (57K) — hike case dead; is the cut case alive?** | USD rates, USD, risk | Citi, BNP, MS, Barclays, DB, JPM, Goldman, UBS, Nomura | The day's gravity; a dovish shock into a hawkish base |
| 2 | **Unemployment fell for the wrong reason** (participation 61.5%) | USD rates | Barclays, UBS, Citi | The 4.2% U/E is a supply-driven mirage, not strength |
| 3 | **Noise vs signal** — how much to read into one print | USD rates | DB, MS (noise) vs Citi, BNP (signal) | The interpretive split that sets positioning |
| 4 | **Curve steepeners / duration** as the expression | UST curve, TIPS | MS | The trade the soft print pulls forward |
| 5 | Core-PCE methodology change lowers measured inflation | TIPS/BE | Citi, Goldman, Barclays, DB | Still live; trims measured core PCE ~0.2–0.25pp |

**B. The "why" — how the houses are reasoning**

The June payrolls print is the delta that reframes the week: **+57K vs 110K consensus, with the prior revised down to 129K (from 172K) and private payrolls +49K** (FACT). Unemployment *fell* to 4.2%, but the sell-side is near-unanimous that it fell for the wrong reason — **participation dropped to 61.5% from 61.8%** and U-6 eased to 7.9%. Barclays (15283) frames it as "a challenge to the reacceleration [narrative]," reading the U/E decline as lower immigration/labour-supply rather than demand strength. That is the crux: a headline miss plus a mechanically-lower jobless rate.

The interpretive split sets the trade. On the dovish side, Citi (15292) is blunt — "the case for hikes was just revised away" — and sees unemployment *rising* in coming months; BNP (15228) goes further, arguing the market is *underpricing* the number of cuts, flags likely Fed dissents, and pencils a new 50-75k monthly payroll trend. On the fade side, DB (15337) calls it "more noise than signal" (consensus 113k, net -74k revisions, Fed officials likely to look through it, citing Daly's "policy in a slightly restrictive position"), and MS (15270) reads net hiring as having "rebounded" despite the revisions — "patience over hikes, steady Fed." UBS (15276) splits the difference: "not bad, slower and lower," core views intact. So the debate has moved off "how hawkish" onto "is this the print that turns the Fed" — and the desks genuinely disagree.

The trade the soft print pulls forward is duration/steepeners. MS (15365) says "now is the time to re-enter Treasury curve steepeners," expecting more soft prints, with the 6-7y sector rolling best; it also flags investors "paying for protection against 6% rates" (15186), i.e. the market still carries a hawkish tail MS thinks is overpriced (echoing its buy-10y-TIPS-with-payer-protection idea, 14751). The still-live structural wrinkle is the **core-PCE methodology change** (Citi 14437 "big deal" -25bp vs Barclays 14371 "refinement"), which would mechanically improve measured inflation into the same soft-labour backdrop.

**C. Consensus views (≥2 independent banks)**

| Theme | Banks | Shared claim | Evidence cited | What consensus is missing (grounded) |
|---|---|---|---|---|
| Payrolls miss kills the hike case | Citi, BNP, MS, Barclays | The reacceleration/hike narrative is off the table | 57K vs 110K; -74k revisions; U/E fell on participation (15292/15228/15283) | Splits on whether cuts now come (Citi/BNP) vs steady Fed (DB/MS) — see D |
| U/E fall is supply-driven, not strength | Barclays, UBS, Citi | 4.2% reflects lower participation, not demand | Participation 61.5% from 61.8% (FACT); "lower immigration inflows" (15283) | Doesn't resolve whether soft supply is itself disinflationary or capacity-tightening |
| Core-PCE revision lowers measured inflation | Citi, Goldman, Barclays, DB | Methodology change trims core PCE ~0.2–0.25pp | BEA Sep-30 retroactive change (14437/14557/14371) | Splits "big deal" (Citi) vs "refinement" (Barclays) |

**D. Differentiated / unique views**

| Bank | Asset | The view | Why it's different | Hidden assumption | Falsifier |
|---|---|---|---|---|---|
| BNP (15228) | USD rates | Market **underpricing cuts**; new 50-75k payroll trend; Fed dissents likely | Most dovish read; sees the miss as a trend-break | Labour demand is genuinely cooling, not just supply | A rebound / revisions up next month |
| DB (15337) | USD rates | Payrolls miss is **"more noise than signal"**; Fed looks through | Most hawkish read; downplays the print | One noisy month shouldn't move a "slightly restrictive" Fed | A second soft print confirms a trend |
| MS (15365) | UST curve | **Re-enter curve steepeners** (6-7y); more soft prints ahead | Turns the macro call into a specific curve trade | Labour softening feeds through to front-end over time | Re-accelerating jobs / sticky inflation flattens |
| Citi (14437) | TIPS/BE | Core-PCE methodology change is **"a big deal"** (−25bp) | Elevates a measurement wrinkle to a Fed input | The Fed reacts to the measured series | Fed explicitly looks through the revision |

*Trade rows expanded:* #1 (MS steepeners), #2 (MS 10y TIPS + payer protection) — see D/B. Surfaced, not judged. **Warsh (carry-forward, re-verified):** Goldman (14844) still has him "inflation risks have come down"; DB (15337) frames a July "family fight, no forward guidance" — the dovish-chair-vs-hawkish-dots tension now sits alongside a dovish data print, tilting the balance. **DEPTH:** US `econ.fact_indicator` deep (140 indicators, latest 06-29); NFP/factory-orders actuals now booked in `cb_events` (TE source; BQL rows for the same events still show null actuals — TE is the source of record here).

---

### Japan — hike-path debate hardens; yen eases off the highs

**A. Themes in play**

| Rank | Theme | Assets | Banks talking | Why it matters to the PM |
|---|---|---|---|---|
| 1 | **Terminal-rate debate escalates** — BNP to 2.50% | JGB, JPY | BNP (new), Barclays, Nomura, MS | The hike path is being re-rated *up*, not just the next move |
| 2 | **USD/JPY off highs** post-NFP; intervention threat lingers | JPY, FX vol | MS, SocGen, Nomura, HSBC, BNP | The soft US print did what jawboning couldn't |
| 3 | **Behind-the-curve / fiscal-policy concern** | JGB, curve | Barclays | The market's worry: BoJ too slow vs rising inflation/fiscal risk |
| 4 | Tankan (comprehensive) confirms **more aggressive pricing** | JGB, BE, equity | Nomura, Citi, UBS | Corroborates the firmer hike path |

**B. The "why" — how the houses are reasoning**

BoJ **at 1.00%** (06-16 hike, FACT). The delta this window is that the *terminal* debate hardened. **BNP (15399) raised its BoJ terminal-rate forecast to 2.50%**, citing significantly lifted Japan growth forecasts on the AI boom, household spending exceeding expectations, and continued wage growth alongside energy subsidies — a house explicitly re-rating the *path*, not just the next hike. Barclays (15072/15286) works the mirror-image risk — "concerns over fiscal policy and a behind-the-curve BoJ" — i.e. if the BoJ is too slow, the JGB curve prices the catch-up and fiscal risk. Nomura's comprehensive Tankan data set (15221) reads "more aggressive" corporate price-setting, and Citi (15236) and UBS reiterate the survey is supportive of the hike path and of Japanese equities. So the Tankan (carried from 07-02) is now fully corroborated across houses and feeds a firmer, higher terminal.

The currency did what jawboning could not: **USD/JPY came off its highs post-NFP** (MS 15318 "USD/JPY off highs"; SocGen 15123 "short covering lifts JPY"). That reframes the intervention story from the 07-02 run — the near-imminent official threat (Mimura interview) is now reinforced by a dovish US print narrowing the rate differential, so the fade looks better supported. Nomura (15187) notes the market "grows increasingly wary of positioning" into a possibly-turning yen. The tradeable expression rotated: BNP (15134) closed its **JPY 2s5s10s** as the belly richened 5y→10y post-BoJ — a curve-positioning cleanup rather than a directional call.

**C. Consensus views (≥2 independent banks)**

| Theme | Banks | Shared claim | Evidence cited | What consensus is missing (grounded) |
|---|---|---|---|---|
| Tankan supports a firmer hike path | Nomura, Citi, UBS, Barclays | Firm sentiment + aggressive price-setting = more hikes | "More aggressive" pricing (15221); "supportive" (15236) | The `cb_events` TE Tankan headline "index 16 vs 17" fell — a different series than the BoJ DI (carry-forward flag) |
| USD/JPY off highs; fade better supported | MS, SocGen, Nomura | Soft NFP + intervention threat cap the top | "Off highs" (15318); "short covering" (15123) | No executed intervention on the record — the top-cap is data + threat, not action |

**D. Differentiated / unique views**

| Bank | Asset | The view | Why it's different | Hidden assumption | Falsifier |
|---|---|---|---|---|---|
| BNP (15399) | JGB | **Terminal rate to 2.50%** | Re-rates the whole path up; most hawkish terminal in-window | AI-boom growth + firm household spending + wages sustain hikes | Growth/wage momentum stalls → BoJ stops well short of 2.50% |
| Barclays (15072) | JGB / curve | **Behind-the-curve + fiscal-risk** steepener framing | Prices the risk the BoJ is too *slow*, not too fast | Fiscal concerns + delayed hikes steepen the curve | BoJ front-loads / fiscal risk recedes |
| SocGen (14702) | USD/JPY | FY26 forecast **152.57** — a reversal from spot | Outright mean-reversion vs the depreciation crowd | Intervention + soft-US squeeze reverse yen shorts | Rate differential re-widens; spot grinds higher |

**Unreconciled (carry-forward, re-verified):** TE "Tankan large-mfg index 16 vs 17" (`cb_events`) vs BoJ business-conditions **DI ~+37** (house-cited) — both shown. **Intervention:** signalled near-imminent (Mimura), **not executed**; USD/JPY eased on the US print, not on action. **Not loaded:** JP `econ.fact_indicator` effectively absent (1 obs) — JP numbers are `cb_events` prints or sell-side.

---

### Australia — trade swings to deficit; the neutral-rate debate persists

**A. Themes in play**

| Rank | Theme | Assets | Banks talking | Why it matters to the PM |
|---|---|---|---|---|
| 1 | **Goods trade swings to a A\$3.0B deficit** | AUD, ACGB | Goldman, JPM, Westpac, UBS | A sharp external-balance miss on weak ore exports |
| 2 | RBA **neutral-rate** debate (opposite mechanisms) | AUD rates | Nomura, BofA, Westpac | Same "tight" conclusion, opposite mechanism (carry-forward) |
| 3 | **PMIs back above 50** (services 50.5, composite 50.4) | AUD, equity | ABS/`cb_events`, Westpac | Activity firming even as trade/housing soften |
| 4 | **Two-speed housing** — firm credit, falling prices | AUD, banks | ANZ, UBS, Goldman, MS | Complicates the tightening story (carry-forward) |

**B. The "why" — how the houses are reasoning**

The AU delta is the **trade balance swinging to a A\$-3.018B deficit** (survey A\$2.2B, prior A\$1.383B revised — FACT). JPM (15029) attributes it to a drop in metal-ore exports after April's strength, with imports also rising and rural goods still firming (+2.6% m/m); Goldman (14966), Westpac (15069) and UBS (15065) read it similarly as an export-led swing rather than a demand signal. It is a terms-of-trade wobble more than a growth scare, but it removes an external tailwind the AUD had leaned on. Against that, **services and composite PMIs moved back above 50** (50.5 / 50.4, FACT), so domestic activity is firming even as the external and housing sides soften.

The rates debate is unchanged from the prior read and re-verified: the June minutes frame a *reaction-function* question where the houses reach "tight for longer" via opposite mechanisms. Nomura (14304) reads a higher long-run neutral but keeps its profile unaltered (no hike, 4.35% into end-2026); BofA (14544) argues the short-run neutral is *falling* so a static 4.35% is passively tightening ("quiet tightening," first cut Aug-2027). ANZ's Australian Macro Weekly (15386) frames the minutes as hawkish with the housing downturn continuing. Housing stays two-speed — prices soft, credit ~8% YoY (carry-forward, DEPTH). Pricing carries only ~17% of a hike by 11-Aug (Westpac 15131).

**C. Consensus views (≥2 independent banks)**

| Theme | Banks | Shared claim | Evidence cited | What consensus is missing (grounded) |
|---|---|---|---|---|
| Trade deficit is export-led, not a demand signal | JPM, Goldman, Westpac, UBS | Ore-export drop after April strength drove the swing | Metal-ore exports down; imports up (15029); May account (15069) | The terms-of-trade hit still pressures the AUD regardless of cause |
| RBA effectively tight; no near-term cut | Nomura, BofA, Westpac | Stance restrictive; cuts distant | Minutes neutral-rate language; OIS ~17% a hike by Aug (15131) | Disagree on *why* neutral shifted — opposite mechanisms (see D) |
| Housing softening but credit resilient | ANZ, UBS, Goldman, MS | Prices down, credit ~8% | Cotality down; credit +0.7% mom (14245) | Falling prices vs +8% credit left unreconciled |

**D. Differentiated / unique views**

| Bank | Asset | The view | Why it's different | Hidden assumption | Falsifier |
|---|---|---|---|---|---|
| BofA (14544) | AUD rates | "**Quiet tightening**": short-run neutral falls; first cut Aug-2027 | Opposite mechanism to Nomura — cyclical neutral dropping | Transmission via yields/housing credit tightens for the RBA | Neutral re-rises / demand re-accelerates |
| Nomura (14304) | AUD rates | Higher **long-run** neutral, but **no hike** — profile unaltered | Reads the hawkish nuance yet holds the call | The neutral note is about tightness, not a signal to move | Board contemplates a hike at a coming meeting |

*Trade context:* DB (15145) took profit on kiwi shorts (an Antipodean-adjacent FX cleanup) — see NZ. **DEPTH:** AU deep (215 indicators, latest 06-29) — trade, PMI and CPI-component detail available.

---

### New Zealand — Jul-8 converges toward a hike

**A. Themes in play**

| Rank | Theme | Assets | Banks talking | Why it matters to the PM |
|---|---|---|---|---|
| 1 | **RBNZ Jul-8 now near-consensus +25bp to 2.50%** | NZD rates, NZD, NZGB | ANZ, UBS, HSBC, Nomura (hike); Westpac (hold) | The 07-02 three-way split has collapsed toward a hike |
| 2 | **Framework vs forward guidance** shift | NZD rates | Westpac | How the RBNZ communicates the path, beyond the level |
| 3 | Firming confidence + oil-shock persistence | NZD rates, BE | ANZ | The data supporting the hike case |

**B. The "why" — how the houses are reasoning**

OCR **2.25%**; the **RBNZ decision is 2026-07-08** (FACT, forward). The delta is that the call converged: the `cb_events` forecast moved to **2.50%** (a hike; it was hold-2.25% at the 07-02 run), and UBS (15127 "+25bp hike in July," OCR to rise "sooner"), HSBC (15246 "we expect a hike in July," noting a 3Q hike had been its view and that the Governor was the deciding vote holding steady last time) and Nomura (15033) all joined ANZ (14581, "let's get started," +25bp to 2.50%). Westpac (15419 "from forward guidance to framework guidance") remains the lone hold-to-September holdout, still leaning on the Governor's conditionality. ANZ's weekly (15384) calls it "a nail biter," so even the hike camp concedes it is close. Pricing carries the hike into Jul-8. Confidence firmed further (ANZ-Roy Morgan bouncing back, 15330).

**C. Consensus views (≥2 independent banks)**

| Theme | Banks | Shared claim | Evidence cited | What consensus is missing (grounded) |
|---|---|---|---|---|
| RBNZ hikes +25bp to 2.50% at Jul-8 | ANZ, UBS, HSBC, Nomura | July delivery of the forecast hike | "+25bp hike in July" (15127); "we expect a hike" (15246); forecast now 2.50% (FACT) | Westpac still holds → Sept; ANZ itself calls it "a nail biter" — not a done deal |

**D. Differentiated / unique views**

| Bank | Asset | The view | Why it's different | Hidden assumption | Falsifier |
|---|---|---|---|---|---|
| Westpac (15419) | NZD rates | **Hold Jul-8; lift-off later**; "framework not forward guidance" | Lone holdout as the Street converges on a hike | The Governor stays conditional and communicates a framework, not a date | RBNZ hikes Jul-8 → Westpac a meeting late |

**Reconciled vs 07-02:** the earlier three-way (ANZ hike / Westpac hold / `cb_events` hold) has narrowed — the calendar consensus and three more houses now align with ANZ on a July hike; Westpac is the remaining dissent. **Not loaded:** NZ `econ.fact_indicator` thin (46 indicators, latest 05-31).

---

### Indonesia — a bear emerges against the further-hiker  *(INSTRUMENT PENDING DEEPAK)*

**A. Themes in play**

| Rank | Theme | Assets | Banks talking | Why it matters to the PM |
|---|---|---|---|---|
| 1 | **IDR: pause or turning point?** — a genuine bull/bear split | IDR, IDR rates | UBS (bearish) vs JPM (further hikes) | The window's cleanest two-sided EM debate |
| 2 | **Inflation broadening** + a large May trade deficit | IDR, C/A | JPM, Nomura, Goldman | The squeeze forcing continued defence |
| 3 | BI's **100bp of hikes "insufficient"** so far | IDR | UBS | The bear's core claim about the defence |

**B. The "why" — how the houses are reasoning**

BI **at 5.75%** (two June hikes, FACT). This window the Indonesia debate sharpened into a genuine two-sided call. **UBS (15130) turned outright bearish IDR** — "Pause or Turning Point?" sees **USD/IDR drifting to 18,500-19,000 in 2H**, argues BI's cumulative 100bp of hikes "so far appear insufficient," and pins the outlook on three drivers: the Fed, Indonesia's current-account deficit, and the ID-US rate differential (with rate-sensitive loan/deposit flows down ~1ppt of GDP). Against that, **JPM (14806, carry-forward, re-verified) expects BI to hike further to 6.00% with risks of more**, on broadening June inflation (0.4% m/m, ~2.9% oya) and the large May trade-deficit swing (14862). So the same facts — broadening inflation, a deteriorating external balance, 100bp already delivered — produce opposite conclusions: UBS says the defence is failing and the currency breaks weaker; JPM says the defence continues via more hikes. That is the trade to interrogate. Goldman (14633) supplies the supply-side framing (fuel-led CPI origin).

**C. Consensus views (≥2 independent banks)**

| Theme | Banks | Shared claim | Evidence cited | What consensus is missing (grounded) |
|---|---|---|---|---|
| Inflation broadened; external balance deteriorating | JPM, Nomura, Goldman | June CPI rose/broadened; May trade swung to deficit | 0.4% m/m, 2.9% oya (14806); "accelerated" (14819); deficit (14862) | Agreement on the facts masks opposite currency conclusions (see D) |

**D. Differentiated / unique views**

| Bank | Asset | The view | Why it's different | Hidden assumption | Falsifier |
|---|---|---|---|---|---|
| UBS (15130) | IDR | **Bearish IDR** to 18,500-19,000; 100bp of hikes "insufficient" | Says the currency defence is *failing* where JPM says it continues | Fed + C/A deficit + rate differential overwhelm BI's hikes | BI over-delivers hikes / Fed turns dovish enough to relieve IDR |
| JPM (14806) | IDR rates | BI **hikes to 6.00%**, more to come | Names a terminal above spot; defence continues | Broadening inflation + weak external balance force continued tightening | Core CPI stabilises / rupiah steadies → BI pauses (the UBS "pause") |

**Puzzle fit:** currency-defence reaction function + broadening inflation + deteriorating external balance, now with a live bull/bear split. **No Spider instrument is named** (SRBI vs IDR rates vs govvies); JPM's prior "SRBI yields high" reference is an observed condition only — the "use the bonds" instruction remains **PENDING DEEPAK**. **DEPTH:** ID `econ.fact_indicator` reasonably deep (91 indicators, latest 06-26).

---

### India — the RBI-inflows theme persists; CPI/monsoon the next test

**A. Themes in play**

| Rank | Theme | Assets | Banks talking | Why it matters to the PM |
|---|---|---|---|---|
| 1 | **RBI measures drive INR inflows** (FCNR(B), ECB-related) | INR, IGB | BNP, Goldman (+ Barclays, prior) | The persistent FX/bonds cluster; one expression stopped out |
| 2 | **June CPI likely rose; monsoon progress key** | INR rates, BE | StanC, Citi, JPM | The next inflation test into 07-03 data |
| 3 | **Fiscal improvement** on RBI dividend | INR rates, IGB | Goldman, Nomura, MS | Eases govvie supply (carry-forward) |

**B. The "why" — how the houses are reasoning**

RBI **at 5.25%** (06-05 hold, FACT). The RBI-inflows theme carries forward and remains the live axis: BNP (14665, sell EUR/INR) and Goldman (14730, constructive INR FX + bonds on carry + a narrowed C/A deficit) still lean on RBI measures — the FCNR(B) swap facility and ECB-related steps — drawing inflows and lowering INR volatility. One expression *failed the tape*: HSBC's sell SGD-INR was **stopped out at 74.00** (15099) — a neutral fact worth noting against the constructive-INR consensus, showing the trade is not one-way. StanC's "A sigh of relief" (15035) frames the broader post-Iran EM unwind of tightening expectations that supports INR carry.

The next test is inflation: StanC (15326) and Citi expect **June CPI likely rose, with monsoon progress the key swing** (weak-start/El Niño tail, carry-forward from MS 14301, JPM 14747). HSBC PMIs (07-03) point to still-firm-but-cooling activity (composite prior 59.3, services 59.8 — a step down from very high levels). So: an inflows-supported constructive INR story, with a food-inflation tail and one stopped-out cross as the counter-evidence.

**C. Consensus views (≥2 independent banks)**

| Theme | Banks | Shared claim | Evidence cited | What consensus is missing (grounded) |
|---|---|---|---|---|
| RBI measures support INR inflows / bonds | BNP, Goldman, Barclays | Inflow measures → constructive INR + bonds | FCNR(B)/ECB (14665); carry + narrower C/A (14730) | HSBC SGD-INR stopped at 74.00 (15099) — the trade is not one-way |
| June CPI rose; monsoon is the swing | StanC, Citi, JPM | Food/monsoon drives the near-term inflation risk | "CPI likely rose; monsoon key" (15326); El Niño (14747) | The 07-03 CPI/PMI actuals not yet booked in `cb_events` |
| Fiscal improved on RBI dividend | Goldman, Nomura, MS | Deficit narrowed on record dividend | May fiscal + RBI dividend (14492/14467) | A one-off dividend flatters the run-rate |

**D. Differentiated / unique views**

| Bank | Asset | The view | Why it's different | Hidden assumption | Falsifier |
|---|---|---|---|---|---|
| Goldman (14730) | INR FX + bonds | **Constructive** on carry + improving fundamentals | Broadest cross-asset INR-bull expression | Carry holds; C/A keeps narrowing | Oil re-spike widens C/A; monsoon-food inflation spikes |

*Trade rows expanded:* #5 (BNP sell EUR/INR), #6 (Goldman constructive INR). Surfaced, not judged. **DEPTH:** IN deep (279 indicators, latest 06-29) — food/CPI component follow-up (incl. fresh-food nowcaster) available for the monsoon tail.

---

### Singapore — MAS review live; a slight-easing lean

**A. Themes in play**

| Rank | Theme | Assets | Banks talking | Why it matters to the PM |
|---|---|---|---|---|
| 1 | **MAS July review** — close call, lean to slight easing | SGD NEER, SGS | Barclays, Nomura, Citi | The live regional CB event |
| 2 | **Composite PMI 57.4** — activity strong | SGD, equity | `cb_events`/FACT | A firm growth print into the review |

**B. The "why" — how the houses are reasoning**

MAS runs the S\$NEER band, not a policy rate. Three houses preview the July review and converge on a **close call with a lean to slight easing**: Citi (14962) "still expect July slight easing" (re-centre/slope), with inflation concerns "centred less on the level"; Barclays (14656) "a close call between near-term inflation [and growth]"; Nomura (14815) "a possible tentative easing." The data cut against an easy easing call, though — the **S&P composite PMI printed 57.4** (well above the 51.5 forecast, FACT) and SIPMM manufacturing 51.3, so activity is firm. The tension is inflation-comfort vs still-solid growth.

**C. Consensus views (≥2 independent banks)**

| Theme | Banks | Shared claim | Evidence cited | What consensus is missing (grounded) |
|---|---|---|---|---|
| MAS July: close call, lean slight easing | Barclays, Nomura, Citi | A modest re-centre/slope easing is the base case | "Close call" (14656); "possible tentative" (14815); "still expect" (14962) | Composite PMI 57.4 (FACT) argues against urgency to ease |

**Not loaded:** the MAS band is not a `cb_events` policy-rate row; SG has no in-window `econ.fact_indicator` rows (PMIs are `cb_events`).

---

### Thailand — a challenging H2, oil-relief the counterweight

BoT **at 1.00%** (06-24 hold, FACT); minutes 07-08. The delta is StanC's "Thailand — A challenging H2" (15036), reinforcing the soft-demand read (weak May consumption/investment, C/A deficit, carry-forward). The constructive counter persists via the oil-relief-to-GDP channel: BofA (14548) "GDP relief from lower oil prices and AI wave," HSBC/UBS (14562/14828) on energy-shock-to-margins. StanC's rates note (15035) favours receiving the THB curve as post-Iran EM tightening-expectations unwind — surfaced (trade #9), not judged. Consensus: soft now, constructive on the outlook; the hard data remains weak. **Not loaded:** no in-window `econ.fact_indicator` rows.

---

### United Kingdom — sticky, hawkish dissent, gilt-curve steepening

BoE **at 3.75%** (06-18 hold, 7/2/0 with 2 hike dissents, FACT). Speaker-heavy into 07-03 (Bailey, the DMP 1y CPI-expectations series prior 3.7%, services/composite PMI finals). The differentiated thread carries forward and firmed: UBS (14426) "inflation shocks steepen the gilt curve," UK most exposed via the highest inflation-linked debt share; Barclays added "UK: Gilts in motion" (15289) and "leadership transition" risk (UBS 14824). UBS also closed a **BoE Sep'26 receiver at 5bps** (15279) — a tactical rates cleanup. JPM's read of Mann (15250) flags "mixed signals" from the hawk. Consensus did not clear the ≥2-bank bar this window beyond the BoE mechanics; the gilt-steepening call remains UBS-led. **Not loaded:** UK `econ.fact_indicator` thin (1 indicator, latest 06-02).

---

### Canada — steady BoC, mfg PMI firms

BoC **at 2.25%** (06-10 hold, FACT); Business Outlook Survey + Consumer Expectations land 07-06. Manufacturing PMI printed **53.0** (from 52.9, back in expansion, FACT). BofA's frame stays "Weak growth, steady BoC" (14376) — no urgency either way; nothing differentiated cleared the bar. **Not loaded:** CA `econ.fact_indicator` absent (no in-window rows).

---

### Philippines — quiet hike, external balance improving

BSP **at 4.75%** (06-18 hike, FACT), part of the June EM-tightening cluster. In-window flow thin; filed as EM-tightening + external-balance improvement (trade deficit narrowed in May, JPM 14291). **Not loaded:** no in-window `econ.fact_indicator` rows.

---

### Malaysia — BNM Jul-9 preview, "La pausa"

OPR **2.75%**; **BNM decides 2026-07-09** (FACT, forward). HSBC's preview (14288) is "La pausa" — houses expect a hold; StanC (15035) favours receiving 2Y MYR NDIRS as a liquidity/rates expression. Calendar-driven into next week. **Not loaded:** no in-window `econ.fact_indicator` rows.

---

### Hong Kong — peg follows Fed

USD-linked (no independent policy rate; rides US pricing via the peg/LAF). JPM's "Hong Kong: May data wrap-up" (15266) is the in-window read; nothing rate-relevant moved domestically. HK `econ.fact_indicator` exists (19 indicators, latest 06-03). Peg-follows-Fed; the soft US print flows through the peg, not through a domestic reaction function.

---

## 5. Grounding ledger  *(SYN)*

- **Rates / decisions / surprises → `calendar.cb_events`** (BQL → TradingEconomics), window 2026-07-02→07-04. Verified decision rows: RBA 4.35% (06-16 hold), BoJ 1.00% (06-16 hike), BI 5.75% (06-09 & 06-18 hikes), BSP 4.75% (06-18 hike), RBI 5.25% (06-05 hold), BoE 3.75% (06-18 hold, 7/2/0), Fed 3.75% (06-17 hold, dots up); RBNZ Jul-8 forecast **2.50%** (moved from hold), BNM Jul-9 forecast hold. US June-payrolls block actuals now booked (NFP 57K, U/E 4.2%, participation 61.5%, factory orders -1.3%) and AU trade balance (A\$-3.018B).
- **Component depth → `econ.fact_indicator`:** deep IN (279) / AU (215) / US (140) / ID (91); thin NZ (46) / HK (19) / UK (1); no in-window rows CA / JP / TH / MY / SG / PH. Latest obs 06-29 (IN/AU/US), 06-26 (ID).
- **Views / trades / quotes → `research.fact_chunk` + Qdrant (`research_gemini_embedding_2_3072d`) + ingested Outlook bodies:** 432 in-window reports across 13 vendors. Movers read at chunk level. Per-theme semantic sweeps: US payrolls reaction, BoJ terminal, RBNZ Jul-8, IDR turning-point, AU trade deficit, India inflows, MAS, post-Iran EM rates.
- **Source-of-record note:** where TE and BQL rows cover the same US labour events, the TE rows carry the booked `actual` and the BQL rows still show null — TE is the source of record for the NFP block this window.
- **Unreconciled:** (a) US NFP interpretation — Citi/BNP "cuts coming" vs DB/MS "noise, steady Fed"; both shown. (b) JP Tankan — TE "index 16 vs 17" vs BoJ **DI ~+37**; both shown. (c) Indonesia — UBS bearish IDR (defence failing) vs JPM further-hikes-to-6.00% (defence continues); both shown. (d) US core-PCE revision — Citi "big deal" vs Barclays "refinement". (e) AU neutral rate — Nomura (long-run up, no hike) vs BofA (short-run falls); opposite mechanisms.
- **Reconciled vs 07-02:** NZ Jul-8 narrowed from a three-way split to a near-consensus +25bp hike (ANZ/UBS/HSBC/Nomura + `cb_events` forecast 2.50%), Westpac the lone hold.
- **Not loaded / pre-print:** IN and UK 07-03 PMI/CPI actuals not booked at run (survey/consensus only); sell-side-reported figures tagged as such.
- **Japan intervention:** signalled near-imminent (Mimura interview) — **not executed**; USD/JPY eased on the US print, not on action.
- **Indonesia instrument:** no Spider instrument named — **PENDING DEEPAK**.
- **Differentiated-view count (§4.D):** US 4 · JP 3 · Indonesia 2 · AU 2 · NZ 1 · India 1 = **13 rows across 6 countries.** Quiet countries (SG single consensus theme; TH / UK / CA / PH / MY / HK short reads).
