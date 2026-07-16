---
edition: daily
date: 2026-07-15
---

# RV CAPITAL · RATES & FX DESK — DAILY MACRO PULSE
# The soft print resolves the hike scare: June core CPI lands at 0.0% m/m / 2.6% y/y, well under the hot number Waller needed, so the dollar sags and front-ends rally — while a mixed China Q2 GDP and the Bank of Canada carry the day in Asia and North America

### The adjudicator resolved dovish. June core CPI printed **flat on the month (0.0% vs 0.2% survey)** and decelerated to **2.6% y/y (from 2.9%)**; headline fell **−0.4% m/m** on a 5.7% energy drop. That is exactly the "surprisingly soft" outcome the hawks did not get: US front-end rallied (SOFR 2y −8.8bp, bull steepener), the dollar broadly weakened (NZD +0.85%, AUD +0.82%, CAD +0.64%, KRW +0.55%), gold +1.3%, Nasdaq +1.1%, VIX back to 16.5. The houses read the Fed as bought time to stay on hold. In Asia, **China's Q2 GDP** paints a mixed, stabilising-on-stimulus picture — headline 4.3% y/y misses (the weakest sequential quarter since 2022) but June industrial production (5.3%) and retail sales (+1.0%) beat — while the **Bank of Canada** decides later today (survey hold 2.25% + MPR + press conference). Singapore's advance Q2 GDP printed strong at 5.7%, China's June trade set a record surplus, and India's CPI/WPI ran hot into a widening trade deficit — the one universe currency that fell.

**Window:** flow 2026-07-14 → 2026-07-15 · Tuesday US-session close (post-CPI) + Wednesday Asian open · **Compiled** 15 Jul 2026 (Wednesday) · **Edition:** Daily
**Universe:** AU · NZ · JP · IN · TH · ID · MY · SG · HK · PH · US · CA · UK

> FX/rates PM lens. Number-first, low-opinion, neutral — the daily does not judge. Sell-side is treated as motivated until the numbers say otherwise. Trades are surfaced with assumption + falsifier — never rated. Every table row is explained in the prose beneath it.
>
> **Grounding legend:** FACT = printed/decision (`calendar.cb_events`, `econ.fact_indicator`) · DEPTH = component series (`econ.fact_indicator`) · VIEW = sell-side interpretation (`research.fact_chunk` + Qdrant) · PRICING = market-implied · SYN = synthesis. Where a marquee number has not booked to the DB, it is labelled **per flow** (sell-side) or **official release**.

---

## Hero stat band

| Number | What it is | Memory / context |
|---|---|---|
| **0.0% m/m · 2.6% y/y** | US June **core** CPI — PRINTED (`cb_events`, both lanes) | The marquee resolved SOFT. Core fell −0.02% m/m (survey +0.2%, prior +0.2%); YoY dipped from 2.9% to 2.6% (survey 2.8%). GS/JPM had ~0.2%; the print undershot everyone. Broad-based declines — auto insurance −2.0%, wireless −3.1%, hotels −2.8% (World Cup payback). **This is the hot-core reading Waller warned would put a July hike on the table — and it did not come.** Confirmed on both the TE (60904/60905) and BQL (41362 core YoY 2.6, 41360 CPI YoY 3.5; core-CPI index SA 336.065 vs 336.121) lanes. |
| **−0.4% m/m · 3.5% y/y** | US June **headline** CPI — PRINTED (`cb_events` 60906/60907; index 333.95 vs 334.70 survey, 60908) | Headline −0.42% m/m (survey −0.1%), YoY 4.2%→3.5%, on a 5.7% energy drop (motor fuel −9.6% as retail gas fell from its peak). GS estimates core PCE at just **0.18% m/m**; JPM 0.168%. Every house calls it disinflationary and "buys the Fed time" (Barclays 18267). |
| **SOFR 2y −8.8bp** | US 2y OIS DoD, 07-13→07-14 (`rates.fact_observation`, par) | Front-end rallied hard on the soft print — a bull steepener (10y −2.6bp). The ~50% July-hike odds and the ~10-11bp priced into 29-Jul deflated. Citi (18317): "one print does not constitute momentum, but softer-than-consensus June data can allow the Fed to remain on hold for the summer." |
| **NZD +0.85% · AUD +0.82% · CAD +0.64%** | FX vs USD DoD, 07-13→07-14 (`FX.fact_fx_rate`, last-tick) | Broad dollar weakness on the soft CPI — KRW +0.55%, EUR +0.36%, GBP +0.35%, SGD +0.28%, IDR +0.27%. Citi (18316) flags DXY recovered "a majority" of its intraday losses by the US close, so the fade is partial. **INR −0.45% is the sole universe FX lower** — hot India CPI/WPI + oil + a wider trade deficit. |
| **$125.6bn record surplus** | China June trade — PRINTED (`cb_events` 60864; exports +27% yoy, imports +36% yoy) | A new record, well above consensus (surplus survey $121bn; exports survey +18.2%). AI/semis (semiconductor export value +121.9% yoy, but volume −0.5% — price, not units) and autos (+69.6%) led. GS (18092): price-driven. The export machine is the growth engine offsetting a soft headline Q2 GDP (4.3%). |
| **5.7% y/y** | Singapore advance Q2 GDP — PRINTED (`cb_events` 60857; qoq 1.1%) | Beat survey 5.5%; 1Q revised UP to 6.3% (from 6.0%). JPM (18103) "unbowed, unbent, unbroken" — manufacturing rebounded 23.1% ar; keeps FY at an above-consensus 4.6%. Citi (18125) reiterates its July S$NEER steepening call on above-trend growth. The MAS MPS is the **late-July (24–31 Jul) window — not today.** |
| **Nasdaq +1.1% · gold +1.3% · VIX 16.5** | US equity / gold DoD (07-14, `fact_index_level`/`fact_spot`); VIX (07-14, `fact_vix`) | Risk-on relief on the soft print: S&P 500 +0.38%, Nasdaq 100 +1.10%, gold 4,055 (+1.3%), silver +1.9%; VIX −0.66 to 16.5, VVIX −1.75 to 93.5. Strong bank earnings (JPM/BAC) added to the tape. Asia rebounded from Monday's rout (KOSPI 200 +1.25%, Nikkei +0.75%). |
| **GDP 4.3% · IP 5.3% · retail +1.0%** | China Q2 GDP + June activity — PRINTED (`cb_events` 60929/60930/60931) | A mixed, stabilising-on-stimulus print. Headline GDP 4.3% y/y **missed** (survey 4.5% / prior 5.0%) — the weakest sequential quarter since 2022 (qoq 0.9%, in line with survey) — and fixed-asset investment stayed weak (−5.7% ytd). But June activity **beat**: industrial production 5.3% (survey 4.6%) and retail sales turned positive at +1.0% (survey −0.1%, prior −0.6%); unemployment eased to 5.0%. The 07-15 market reaction is still forming. Li Qiang (Nomura 18156) has urged "countercyclical" H2 support. |

```spiderchart
{"type":"bar","title":"US June CPI — actual undershot survey across the board","caption":"Grounded: calendar.cb_events TE lane (ids 60904-60907), printed actual vs survey. Core CPI flat m/m and 2.6% y/y both undershot; headline fell on energy. The soft print deflated the July-hike setup Governor Waller had made conditional on a hot core.","series":[{"name":"Actual","color":"#2b5a86","points":[["Core m/m",0.0],["Core y/y",2.6],["Headline m/m",-0.4],["Headline y/y",3.5]]},{"name":"Survey","color":"#b5761f","points":[["Core m/m",0.2],["Core y/y",2.8],["Headline m/m",-0.1],["Headline y/y",3.8]]}]}
```

```spiderchart
{"type":"bar","title":"FX vs USD — day-over-day % (07-13 → 07-14, the soft-CPI session)","caption":"Grounded: FX.fact_fx_rate SPOT last-tick per day. Positive = local currency stronger vs USD. The soft CPI weakened the dollar broadly — NZD/AUD/CAD/KRW led. INR is the sole universe currency lower (hot CPI/WPI + oil + wider trade deficit). Per Citi 18316, DXY recovered part of the drop into the US close.","series":[{"name":"DoD %","color":"#1f6b4f","points":[["NZD",0.85],["AUD",0.82],["CAD",0.64],["KRW",0.55],["EUR",0.36],["GBP",0.35],["SGD",0.28],["IDR",0.27],["MYR",0.25],["TWD",0.23],["CNH",0.18],["THB",0.14],["JPY",0.14],["PHP",0.10],["HKD",0.00],["INR",-0.45]]}]}
```

```spiderchart
{"type":"bar","title":"2y OIS/swap — day-over-day bp (07-13 → 07-14)","caption":"Grounded: rates.fact_observation par, 2y, last-tick per day. US front-end rallied 8.8bp on the soft CPI (US EOD = post-print), dragging UK/CA/AU/NZ lower. Asia-Pacific EM curves' 07-14 last tick is the Asian close = BEFORE the US CPI, so they still carry the pre-print hawkish/oil/strong-local-data tape (INR/PHP/SGD/THB/HKD backed up); their soft-CPI relief lands on 07-15. EUR is the divergent DM mover (oil/ECB read).","series":[{"name":"DoD bp","color":"#a1382f","points":[["IN",14.1],["PH",11.5],["EUR",8.5],["SG",4.8],["TH",4.3],["HK",6.3],["ID",0.9],["MY",2.3],["NZ",-2.1],["CA",-1.9],["JP",-2.3],["AU",-2.7],["UK",-2.7],["US",-8.8]]}]}
```

---

## The day in brief

The number that had the whole book coiled came soft, and it came soft everywhere. **US June core CPI fell −0.02% on the month — flat to one decimal, 0.0% m/m against a 0.2% survey — and the year-over-year rate dipped from 2.9% to 2.6%** (`cb_events` TE lane 60904/60905). Headline dropped −0.42% m/m (survey −0.1%; YoY 4.2%→3.5%) on a 5.7% fall in energy (`cb_events` 60906/60907). The internals were broad, not a single-line fluke: auto insurance −2.0% (second big monthly decline), wireless services −3.1%, hotels −2.8% (World Cup payback), apparel −0.6% (GS 18251). GS and JPM had penciled ~0.2% core; the print undershot the entire desk. GS now marks **core PCE at just 0.18% m/m** (JPM 0.168%, 3-month annualised 3.0%). Twenty-four hours after Governor Waller told the market a hot core "this week" would put a near-term hike on the table, the reading that would have triggered him did not arrive. Every house drew the same conclusion — the print "buys time for the FOMC to remain on hold" (Barclays 18267), takes "near-term pressure off the Fed" (JPM 18282), and lets the Fed "remain on hold for the summer" (Citi 18317).

The tape did what a dovish surprise does. US front-end OIS rallied hard — SOFR 2y −8.8bp into a bull steepener (10y −2.6bp) — the dollar weakened across the board (NZD +0.85%, AUD +0.82%, CAD +0.64%, KRW +0.55%, EUR +0.36%), gold rose +1.3% to 4,055, the Nasdaq 100 added +1.1% and VIX slipped to 16.5. Two nuances keep it from being a clean one-way move: Citi (18316) notes the DXY recovered *a majority* of its intraday CPI losses by the US close and still leans USD-asymmetric on Middle-East risk, and the oil blockade sits unresolved in the background (WTI booked at $78.78 in IMDR, +9% off the pre-spike level). In Asia, **China's Q2 GDP** delivers a mixed read: headline growth **misses at 4.3% y/y** (survey 4.5%, from 5.0%) with the weakest sequential quarter since 2022 (0.9% qoq), and fixed-asset investment stays weak (−5.7% ytd) — but June activity **beats**, with industrial production 5.3% (survey 4.6%) and retail sales turning positive at +1.0% (survey −0.1%), on top of a record June trade surplus; the 07-15 market reaction is still forming. The remaining live event is the **Bank of Canada** (survey hold 2.25%, with MPR and press conference later today). Around them, Singapore's advance Q2 GDP printed strong (5.7%), New Zealand's QSBO showed acute pricing that keeps the RBNZ hiking, India's CPI (4.38%) and WPI (9.87%) both ran hot into a widening trade deficit, and Japan's long end kept rallying on the GPIF/Katayama repatriation theme.

---

## Deltas *(SYN — lead with what changed)*

The Tuesday US-session (post-CPI) repricing and the fresh 07-14/07-15 flow drive today's read (~334 reports swept — 316 on 07-14, ~18 early-07-15 — deep-read and unioned with structured `dim_report` window filters, the Outlook 13-folder taxonomy, and a targeted China-GDP Qdrant sweep). **US June CPI (both TE and BQL lanes), China Q2 GDP + June activity, SG advance Q2 GDP, China June trade, India June WPI and the Australia NAB/Westpac surveys are all PRINTED** and grounded to `cb_events` rows. **The Bank of Canada is the day's remaining forward decision** (survey hold 2.25%, MPR + presser later today). There is **no BBG chat transcript for 2026-07-15** (none exists for the date) — noted, not blocking.

1. **US June core CPI prints SOFT — 0.0% m/m / 2.6% y/y — and the July-hike scare deflates (GS 18251, JPM 18282, Citi 18239/18317, DB 18349, MS 18265, Nomura 18292, Barclays 18267, SocGen 18293, UBS 18295).** Core −0.02% m/m (survey +0.2%), YoY 2.9%→2.6%; headline −0.42% m/m / 3.5% y/y on energy −5.7%. Core PCE tracking ~0.17-0.18% (GS/JPM). Unanimous read: disinflation resumed, the Fed can stay on hold. **Supersedes the 07-14 "Waller opens the door to a hike" hawkish setup** — the hot core that was the trigger did not print. (FACT print + VIEW — 60904-60908 / house cluster)
2. **The dollar weakened and front-ends rallied on the print (`rates.fact_observation` / `FX.fact_fx_rate`).** SOFR 2y −8.8bp (bull steepener), UK/CA front-ends lower; USD broadly softer (NZD +0.85%, AUD +0.82%, CAD +0.64%, KRW +0.55%). Nasdaq +1.1%, gold +1.3%, VIX −0.66 to 16.5. **Nuance:** Citi (18316) — DXY recouped most of the intraday drop into the close; Nomura (18221) — the USD "struggled to make gains" even on hawkish Waller + oil, so spec positioning is leaning long USD and the bar to further USD upside is higher. (PRICING — IMDR market layers + house colour)
3. **China Q2 GDP prints a mixed, stabilising-on-stimulus read; June trade set a record surplus (GS 18092, JPM 18216, Barclays 18117, UBS 18231, Nomura 18156/18161, DB 18091, HSBC 18098).** Headline GDP **4.3% y/y misses** (survey 4.5%, prior 5.0%) — the weakest sequential quarter since 2022 (0.9% qoq, in line with survey) — and fixed-asset investment stays weak (−5.7% ytd). But June activity **beats**: industrial production 5.3% (survey 4.6%) and retail sales turn positive at +1.0% (survey −0.1%, prior −0.6%); unemployment eases to 5.0%. June trade set a record surplus ($125.6bn; exports +27%, imports +36%, semis/autos-led, "booming yet bifurcated," Barclays). Nomura (18156): Li Qiang urged "countercyclical" policy be stepped up in H2. The 07-15 market reaction is still forming. (FACT print + VIEW — 60929/60930/60931/60932/60864 / house cluster)
4. **Singapore advance Q2 GDP beats at 5.7% y/y; Citi reiterates its July S$NEER steepening call (JPM 18103, Citi 18125, Nomura 18157, GS 18096).** 5.7% vs 5.5% survey; 1Q revised up to 6.3%; manufacturing rebounded 23.1% ar. JPM keeps FY at an above-consensus 4.6%. Citi (18125): above-trend 2Q supports its July MAS steepening. **The MAS MPS is the 24–31 Jul window — not today.** SORA 2y +4.8bp (Asian close, pre-US-CPI). (FACT print + VIEW — 60856/60857 / house cluster)
5. **New Zealand QSBO shows acute pricing; ANZ and UBS both keep the RBNZ hiking (ANZ 18030, UBS 18107, JPM 18078, GS 18068/18070, DB 18067, Westpac 18059).** Selling-price gauge jumped 22→41; business confidence rebounded to +12 (sa). ANZ keeps +25bp in **both September and October**; UBS keeps +25bp in **Sep and Dec** to 3.00%. Conway (RBNZ Chief Economist) flagged "unhelpful asymmetry" in price-setting. NZD firmest in the universe (+0.85%). (Survey print + VIEW — 18030/18107)
6. **India CPI (4.38%) and WPI (9.87%) both run hot; June trade deficit widens to $30.4bn (MS 18152, Barclays 18171, JPM 18260, Nomura 18160, SocGen 18227).** WPI 9.87% (survey 9.15%; food 6.14%, fuel 27.41%, manufacturing 7.48% — "relentless rise," Barclays); trade deficit above the $26.5bn consensus on oil imports. INR −0.45% (sole universe FX down); MIBOR 2y +14bp / 10y +15bp (pre-CPI Asian tape). **SocGen takes profit on short EUR/INR "as headwinds rise" (18227).** (FACT print + VIEW — 60882-60885 / 90517 / house cluster)
7. **Japan's long end keeps rallying on the GPIF/Katayama repatriation theme (Citi 18123, Nomura 18291, BNP 18063, Barclays 18062, MS 18288).** Citi: FM Katayama's push for GPIF/pension repatriation is likely "incremental" (the basic-portfolio review is not due until 2029), but corporate pension funds could add JGBs — JPY-supportive. TONAR 10y −9.5bp DoD (richer). Nomura (18291): the government is revising Basic Policy wording on monetary policy after the long-end rise. (VIEW — 18123/18291/18063)
8. **Bank of Canada decides today — benign-core hold the base case; Nomura books its long USD/CAD (Nomura 18221).** BoC survey hold 2.25% + MPR + press conference (all forward). Nomura took profit on long USD/CAD at 1.4090 (+2.1% from 1.38), flagging stretched short-CAD positioning and the risk the BoC can't meet the market's hike pricing. CORRA 2y −1.9bp into the meeting. (Forward + VIEW — 41366/60980 / 18221)
9. **Australia data improved; ANZ stays short AUD rates (GS 18072/18073, JPM 18076, UBS 18164, Westpac 18084/18112, ANZ 18342).** NAB business confidence −5 (from −14), Westpac consumer confidence +4.1% — both beat. ANZ (18342): RBA reaction function "heavily skewed" to inflation; holds paid Dec-26 RBA OIS, favours being short AUD rates as supply shocks keep long-end yields higher. AONIA 2y −2.7bp (Asian close). (FACT print + VIEW — 60858/60860 / house cluster)
10. **UK: HSBC opens a receive-GBP-1Y1Y-OIS trade fading the Middle-East-driven hike repricing; Burnham budget in focus (HSBC 18254, JPM 18264, UBS 18109).** HSBC: ~60bp of hikes and an 80% Sep-hike probability are priced after the oil-led front-end sell-off; it sees the BoE staying on hold (only 2 MPC hike votes in June) and receives GBP 1Y1Y at 4.35% (target 4.00%, stop 4.60%). JPM (18264): Burnham's Budget brings "significant policy announcements," no large net stimulus. (VIEW — 18254/18264)

---

## 4. Cross-asset moves matrix (DoD)

Day-over-day = **(07-14 last-tick) − (07-13 last-tick)**, last tick = max `ts` within the calendar day, for **FX (spot, `FX.fact_fx_rate`)**, **2y/10y swap/OIS par (`rates.fact_observation`)** and **equity close (`fact_index_level`)**. **07-14 is the last complete session** — the Tuesday US-CPI-reaction day; the 07-15 (Wednesday) Asian session is unpopulated / stale in the rates & FX layers at compile, so DoD uses 07-13→07-14. **Timing caveat:** US/UK/CA/EU curves' 07-14 last tick is their EOD, *after* the 12:30 GMT CPI (so SOFR/SONIA/CORRA capture the reaction); Asia-Pacific curves & equities' 07-14 last tick is the Asian close, *before* the CPI, so they still carry the pre-print tape. FX % is **local vs USD** (positive = local stronger). `fact_bond_yield` is EMPTY — rates are swap/OIS.

| Country | FX vs USD (DoD %) | 2y (DoD bp) | 10y (DoD bp) | Equity (07-14) | One-line read |
|---|---|---|---|---|---|
| United States | EUR **+0.36%** | SOFR **−8.8** | SOFR **−2.6** | S&P 500 +0.38% / Nasdaq 100 +1.10% | **Soft CPI = the move.** Front-end rallied hard (bull steepener); July-hike scare priced out; USD broadly weaker; tech + gold +1.3% rallied; VIX −0.66 to 16.5. |
| China / Hong Kong | CNH **+0.18%** / HKD **0.00%** | HIBOR **+6.3** | HIBOR **+4.3** | HSI +0.52% / HSCE +0.46% / HSTECH +0.07% | **Q2 GDP mixed** — headline 4.3% misses, but IP (5.3%) + retail (+1.0%) beat; June trade record surplus $125.6bn. CNH firmer; HK curve backed up (pre-CPI Asian close); 07-15 reaction still forming. |
| Singapore | SGD **+0.28%** | SORA **+4.8** | SORA **+5.8** | SIMSCI +0.31% | **Advance Q2 GDP beat 5.7%.** SORA backed up on the strong print (pre-CPI close); Citi reiterates July S$NEER steepening. MAS MPS is late-Jul, not today. |
| Canada | CAD **+0.64%** | CORRA **−1.9** | CORRA **+1.1** | n/l | **BoC + MPR + presser today** (hold 2.25% base case). CAD firmed on soft US CPI; front nudged lower. Nomura booked long USD/CAD (+2.1%); MS "1.42 too rich." |
| New Zealand | NZD **+0.85%** | NZIONA **−2.1** | NZIONA **−1.3** | n/l | Kiwi firmest in the universe. QSBO acute pricing (selling price 22→41); ANZ Sep+Oct, UBS Sep+Dec hikes; Q2 CPI 21-Jul the fork. |
| India | INR **−0.45%** | MIBOR **+14.1** | MIBOR **+15.0** | Nifty 50 −0.66% | **Only universe FX lower.** Hot CPI (4.38%) + WPI (9.87%) + oil + trade deficit $30.4bn; rates backed up most in the universe (pre-CPI Asian tape); equities off. SocGen booked short EUR/INR. |
| Japan | JPY **+0.14%** | TONAR **−2.3** | TONAR **−9.5** | Nikkei +0.75% / TOPIX +0.79% | Long end rallied hard on GPIF/Katayama repatriation (Citi: incremental); equities rebounded from Monday's rout; JPY ~flat. IP final soft (0.1% m/m). |
| Australia | AUD **+0.82%** | AONIA **−2.7** | AONIA **−2.6** | ASX 200 flat (stale) | AUD strong on soft US CPI. NAB confidence −5, Westpac consumer +4.1% (both beat); ANZ stays short AUD rates (paid Dec-26 RBA OIS); Q2 CPI 29-Jul. |
| Euro area | EUR **+0.36%** | ESTR **+8.5** | ESTR **+3.6** | Euro Stoxx 50 +0.15% / Banks +0.51% | **Divergent DM mover:** ESTR backed up (oil / "too hot to hike" ECB read); EUR firmer vs USD. Context row for the US book. |
| Philippines | PHP **+0.10%** | PHIREF **+11.5** | PHIREF **+3.7** | n/l | Peso firmer modestly; front backed up hard (pre-CPI Asian tape); UBS local-conviction equity note; StanC 5.00% Aug + RPGB carry (carried). |
| Thailand | THB **+0.14%** | THOR **+4.3** | THOR **+5.9** | SET −0.16% | THB ~flat; rates backed up (pre-CPI close); Citi took profit on long USD/THB, rolled bearish PHP (18064); BoT on hold. |
| Indonesia | IDR **+0.27%** | JIBOR **+0.9** | JIBOR **+5.3** | n/l | IDR firmer on soft USD; 2026 fiscal deficit target raised to 2.85% (fuel subsidy); JPM MW IDR / MW IndoGBs; BI 22-Jul. |
| Malaysia | MYR **+0.25%** | KLIBOR **+2.3** | KLIBOR **+2.5** | n/l | MYR firmer; rates nudged up; CPI (survey 2.0%) + Q2 GDP prelim (fcst 5.3%) both **17-Jul** — forward. Quiet in-window. |
| United Kingdom | GBP **+0.35%** | SONIA **−2.7** | SONIA **−1.9** | FTSE n/l (07-14) | GBP firmer, front-end rallied with US. HSBC receives GBP 1Y1Y (fades the ~80% Sep-hike pricing); GDP 16-Jul; Burnham Budget in focus. |

*Oil/vol footnote:* WTI now **booked in IMDR at $78.78** (`commodities.fact_spot`, 07-13 — the Hormuz-blockade spike, +9% from 72.27 on 07-10); no 07-14 tick yet. Brent ~**$83-84** remains sell-side (DB/GS). Gold **4,055** (07-14, **+1.34%** DoD, `fact_spot`); silver 59.25 (+1.87%). **VIX** 16.5 (07-14, **−0.66** DoD, `fact_vix`); VXN 26.28 (−1.02), VVIX 93.53 (−1.75), VIX9D 13.46 (−1.67) — risk premium came off on the soft print. **DXY** not loaded (agent proxy via crosses; Citi 18316 has it recovering most of the intraday CPI drop). **Equity flag:** `fact_index_level` fresh to **07-14**; ASX 200 shows an unchanged 8,808.5 (stale — no fresh tick). MSCI Taiwan −1.42% / Nifty −0.66% the regional laggards. `fact_bond_yield` EMPTY — cash govt yields not loaded; rates are swap/OIS. **Rows ordered by event proximity + move magnitude.**

---

## 5. CB / macro dashboard  *(FACT — `calendar.cb_events`)*

One row per covered country. Policy rate = last decided rate on a verified decision row; last move and next event verified against `cb_events`. The BoC decides later today (the day's remaining forward event); China's Q2 GDP + June activity have printed (mixed — headline miss, activity beat); Korea's BoK is a well-flagged +25bp Thursday (outside the universe). The 07-15 macro prints in `cb_events` are China GDP/IP/retail/FAI; the 07-14 prints (US CPI, SG GDP, China trade, India WPI, AU surveys) are all confirmed.

| Country | Policy rate | Last move (verified) | Next scheduled | Bias / key issue |
|---|---|---|---|---|
| United States | **3.75%** (3.5-3.75 range) | Held 2026-06-17 (dots up) | PPI 15-Jul; retail sales 16-Jul; **FOMC 29-Jul** | **Core CPI 0.0% m/m / 2.6% y/y — SOFT.** July-hike scare deflated; houses see a hold "for the summer"; core PCE ~0.17-0.18%. Warsh (Chair) dovish, no guidance |
| China | LPR / 7d OMO | — | Aug activity; LPR fixing | **Q2 GDP 4.3% y/y (miss) / 0.9% qoq** — weakest sequential since 2022; but June IP 5.3% + retail +1.0% beat; record trade surplus $125.6bn; Li Qiang urges "countercyclical" H2 support |
| Singapore | MAS S\$NEER band | — (band) | **MAS MPS 24–31 Jul window** | **Advance Q2 GDP 5.7% (beat 5.5%)**; 1Q revised up to 6.3%; JPM FY 4.6% above-cons; Citi reiterates July steepening. MAS is late-Jul, NOT today |
| Canada | **2.25%** | Held 2026-06-10 | **BoC + MPR + presser 15-Jul (today)** | Hold base case (benign core, excess supply, USMCA drag — JPM/MS/GS) vs StanC cut-by-year-end vs mkt hike pricing; Nomura booked long USD/CAD |
| New Zealand | **2.50%** | Hiked +25bp 2026-07-08 | Q2 CPI 21-Jul; 2-Sep MPS | **QSBO acute pricing (selling price 22→41)**; ANZ Sep+Oct, UBS Sep+Dec hikes to 3.00%; Conway flags pricing asymmetry; NZD firmest |
| India | **5.25%** | Held 2026-06-05 | RBI August | **CPI 4.38% + WPI 9.87% both hot**; trade deficit $30.4bn on oil; INR −0.45%; RBI seen looking through benign core; SocGen booked short EUR/INR |
| Japan | **1.00%** | Hiked +25bp 2026-06-16 | (post-window) | GPIF/Katayama repatriation caps + rallies the long end (TONAR 10y −9.5bp); govt revising Basic Policy MP wording; June hike "retrospectively" supported |
| Australia | **4.35%** | Held 2026-06-16 | Q2 CPI 29-Jul; 11-Aug | NAB confidence −5, consumer +4.1% (both beat); ANZ short AUD rates (paid Dec-26 RBA OIS), RBA "heavily skewed" to inflation |
| Indonesia | **5.75%** | Hiked +25bp 2026-06-18 | **BI 22-Jul** | 2026 fiscal deficit target raised to 2.85% (fuel subsidy); JPM MW IDR / MW IndoGBs, reduces UW INDONs; BI hawkish pivot anchors IDR |
| Hong Kong | USD peg / LAF | — (linked to Fed) | Unemployment 17-Jul | HKD flat on peg; HIBOR +6.3bp (pre-CPI Asian tape); soft US CPI eases the Fed-linked pressure into 07-15 |
| Thailand | **1.00%** | Held 2026-06-24 | (post-window) | THB flat; THOR +4-6bp (pre-CPI close); Citi booked long USD/THB, rolled bearish PHP; BoT on hold both years (StanC) |
| Philippines | **4.75%** | Hiked +25bp 2026-06-18 | (post-window) | PHIREF front +11.5bp (pre-CPI tape); UBS local-conviction equity note; StanC 5.00% Aug + 2Y-3Y RPGB carry (carried) |
| Malaysia | **2.75%** | Held 2026-07-09 | **CPI + Q2 GDP prelim 17-Jul** | CPI survey 2.0%, GDP prelim fcst 5.3%; MYR firmer; quiet in-window ahead of Thursday's double print |
| United Kingdom | **3.75%** | Held 2026-06-18 (7/2/0) | GDP 16-Jul; MPR 30-Jul | GBP/SONIA firmer with US; HSBC receives GBP 1Y1Y (fades ~80% Sep-hike pricing); Burnham Budget "significant policy," no big net stimulus |

**SYN — state of the world:** the single event the universe was coiled around has resolved, and it resolved dovish. June core CPI at 0.0% m/m / 2.6% y/y is the "surprisingly soft" outcome the hawks did not get — it undershot the entire sell-side desk, it was broad-based rather than a one-line quirk, and it maps to a core-PCE nowcast of just ~0.17-0.18%. That took the hot-core trigger Waller had named off the table for now; the front-end rallied, the dollar sagged, and every house shifted to "the Fed can stay on hold for the summer." Two things keep it from being a clean risk-on: the dollar recovered a chunk of its intraday drop into the close (Citi), and the Hormuz oil blockade is still live in the background as the two-sided inflation tail. With the US resolved, the gravity sits in Asia and Canada — China's Q2 GDP is a mixed, stabilising print (headline 4.3% missed and the sequential quarter was the weakest since 2022, but June industrial production and retail sales beat and June trade set a record surplus, the export machine led by AI/semiconductors and autos doing the heavy lifting), and the BoC is a benign-core hold the market keeps trying to price hikes against. The rest of the universe keeps its own clock: Singapore printed a strong 5.7%, New Zealand added another hawkish signal (acute QSBO pricing, a dovish official flagging price-setting asymmetry), India ran hot on both CPI and WPI into a wider trade deficit (the one currency that fell), and Japan's long end kept richening on the pension-repatriation theme. The soft US print is the tide; the Asian data are the local currents.

---

## 6. Themes in play + open questions

**Themes (who's talking + the number), stated neutrally:**
- **June CPI resolves the hike scare — disinflation resumed.** Core −0.02% m/m / 2.6% y/y; headline −0.42% / 3.5% on energy −5.7%. GS (18251): core PCE 0.18%. JPM (18282): "takes near-term pressure off the Fed," core PCE 0.168%, 3m 3.0%. Barclays (18267): "buys time for the FOMC to remain on hold." Citi (18317): "allows the Fed to remain on hold for the summer." SocGen (18293): "a big downside surprise." Universal read, with the caveat that some core-services-ex-shelter softness may be one-off (JPM).
- **The dollar's non-reaction to hawkish catalysts.** Nomura (18221): USD "struggled to make gains" even on hawkish Waller + Middle-East re-escalation → spec positioning leans long USD, the bar to further USD upside is higher; books long USD/CAD. Citi (18316): DXY recovered a majority of its intraday CPI losses, asymmetry still leans USD on ME risk. The tension: soft data vs stretched long-USD positioning.
- **China: mixed Q2 GDP — headline miss, activity beat.** Headline GDP 4.3% y/y missed (survey 4.5%; weakest sequential quarter since 2022), and FAI stayed weak (−5.7% ytd) — but June industrial production (5.3% vs 4.6% survey) and retail sales (+1.0% vs −0.1%) beat, a stabilising-on-stimulus signal. On trade, GS (18092): record $125.6bn surplus, semis/autos-led (semis value +121.9% but volume −0.5% = price); Barclays (18117): "booming yet bifurcated"; UBS (18231): "another positive surprise in exports." Nomura (18156): Li Qiang urges "countercyclical" H2 policy.
- **The RBNZ hiking cycle has corroboration.** ANZ (18030): QSBO selling-price 22→41, keeps Sep+Oct. UBS (18107): keeps Sep+Dec to 3.00%. Conway: "unhelpful asymmetry" in price-setting as the fuel shock fades. Q2 CPI 21-Jul the arbiter.
- **India's twin hot prints.** MS (18152): June WPI at an all-time high. Barclays (18171): WPI/PPI "relentless rise" (9.87%). JPM (18260): trade deficit $30.4bn on oil. SocGen (18227): books short EUR/INR "as headwinds rise." The read: headline hot, core the swing factor for the RBI.
- **Japan's pension-repatriation flow.** Citi (18123): Katayama's GPIF push likely "incremental" (portfolio review not due until 2029) but JPY-supportive; corporate pensions may add JGBs. Nomura (18291): govt revising Basic Policy MP wording after the long-end rise. BNP (18063): long 10s20s box. TONAR 10y −9.5bp.
- **Oil / Hormuz — the live two-sided tail.** WTI booked at $78.78 (+9%). Barclays Inflation-Linked (18119): "blockade reinstated." StanC (18336): a Middle-East ceasefire breakdown scenario. Still the shared falsifier under the soft-CPI relief.

**Open questions into the next sessions (neutral — the disagreement + what resolves it):**
1. **China's mixed Q2 print** — does the June activity beat (IP 5.3%, retail +1.0%) mark genuine stabilisation, or does the headline GDP miss (4.3%, weakest sequential quarter since 2022) and weak FAI (−5.7%) pull forward more support beyond Li Qiang's "countercyclical" language; the 07-15 CNH/equity reaction is still forming.
2. **BoC (today)** — JPM/MS/GS benign-core hold vs StanC's cut-by-year-end vs the market's hike pricing; Nomura just booked long USD/CAD flagging the BoC "may be unable to meet market pricing for hikes." MPR + presser the guidance.
3. **Does the soft CPI hold, or was some of it one-off?** — JPM flags core-services-ex-shelter softness as possibly transitory; PPI (15-Jul) and retail sales (16-Jul) refine the core-PCE read (GS 0.18%, Barclays "0.2% handle").
4. **The dollar** — stretched long-USD positioning (Nomura) + soft data vs Citi's ME-driven USD asymmetry; which wins into a range-bound summer front-end.
5. **India rate path** — CPI 4.38% + WPI 9.87% hot, but the RBI is seen looking through benign core; oil is the fresh energy-CPI risk into the August meeting.
6. **New Zealand** — ANZ's Sep+Oct (+50bp) vs UBS's Sep+Dec; the 21-Jul Q2 CPI the arbiter, with QSBO pricing already acute.
7. **BoK (16-Jul, outside universe)** — a well-flagged +25bp to 2.75% (DB: "hawkish but measured 25bp steps"; StanC: cycle starts July); relevant for KRW and the Asia-rates read.

---

## 7. Calendar — releases + CB events with rate relevance  *(FACT — `cb_events`; pure calendar, no view)*

Consensus (`survey`/`forecast`) shown where present; `actual` shown only where the row carries one. `®` = prior revised. **The BoC decision is the day's remaining pre-decision row (null).** US June CPI, China Q2 GDP + June activity, SG advance GDP, China June trade, India June WPI and the Australia surveys all PRINTED (`cb_events` actual rows). Sell-side-reported values tagged "per flow."

| Date | Country | Event | Consensus | Prior | Actual |
|---|---|---|---|---|---|
| 07-13 | IN | CPI YoY / MoM | 4.3% / — | 3.93% | **4.38% / 1.03% — PRINTED (59043/59044)** |
| 07-13 | IN | Balance of trade | −$26.5B | −$28.21B | **−$30.43B — PRINTED (90517)** |
| **07-14** | **US** | **CPI: core m/m / y/y** | **0.2% / 2.8%** | **0.2% / 2.9%** | **0.0% / 2.6% — PRINTED SOFT (60904/60905)** |
| **07-14** | **US** | **CPI: headline m/m / y/y; index NSA** | **−0.1% / 3.8%; 334.70** | **0.5% / 4.2%; 335.12** | **−0.4% / 3.5%; 333.95 — PRINTED (60906-60908)** |
| 07-14 | US | Fed Warsh House testimony | — | — | **held (dovish tone; "make sure price spikes don't broaden out," GS 18324)** |
| 07-14 | US | Federal budget balance | −$129B | +$27.0B | **−$120.3B — PRINTED (41363)** |
| **07-14** | **SG** | **Advance Q2 GDP y/y / qoq** | 5.5% / 1.1% | 6.3%® / 1.3%® | **5.7% / 1.1% — PRINTED STRONG (60857/60856)** |
| **07-14** | **CN** | **Balance of trade; exports/imports y/y** | $121B / 18.2% / 24% | $105.4B / 19.4% / 27.4% | **$125.6B / 27% / 36% — PRINTED RECORD (60864-60866)** |
| 07-14 | IN | WPI inflation y/y; food; fuel; mfg | 9.15% / — / — / — | 9.68% / 4.49% / 30.33% / 7.48% | **9.87% / 6.14% / 27.41% / 7.48% — PRINTED HOT (60882-60885)** |
| 07-14 | JP | Industrial production m/m / y/y (final) | 0.5% / — | 0.5% / 2.0% | **0.1% / −2.1% — PRINTED SOFT (60870/60871)** |
| 07-14 | AU | NAB confidence; Westpac consumer conf | — / — | −14 / −2.9% | **−5 / +4.1% — PRINTED (60860/60858)** |
| 07-14 | NZ | NZIER QSBO (Q2) | — | −4 (conf) | **confidence +12 sa; selling price 22→41 (per flow, 18030)** |
| **07-15** | **CN** | **GDP y/y / qoq; IP; retail; FAI ytd** | 4.5% / 0.9% / 4.6% / −0.1% / −4.9% | 5.0% / 1.3% / 4.5% / −0.6% / −4.1% | **4.3% / 0.9% / 5.3% / +1.0% / −5.7% — PRINTED MIXED (60929-60932); headline miss, IP+retail beat** |
| **07-15** | **CA** | **Bank of Canada decision + MPR + presser** | hold 2.25% | 2.25% | forward — JPM/MS/GS hold vs StanC cut |
| 07-15 | US | PPI m/m / core m/m; Warsh (Senate) | 0% / 0.4% | 1.1% / 0.4% | forward |
| 07-16 | US | Retail sales m/m; initial claims | 0.2% / 217K | 0.9% / 215K | forward |
| 07-16 | UK | GDP m/m / y/y; IP m/m | 0.1% / 1.4% / −0.1% | −0.1% / 1.2% / 0% | forward |
| 07-16 | NZ | Food inflation y/y | — | 3.2% | forward |
| 07-16 | KR | BoK base rate | hike 2.5→2.75% | 2.5% | forward (outside universe) |
| 07-17 | MY | CPI y/y; Q2 GDP prelim y/y | 2.0% / 5.3% | 2.0% / 5.4% | forward |
| 07-17 | HK | Unemployment rate | — | 3.7% | forward |
| 07-17 | SG | Balance of trade (NODX) | — | $5.57B | forward |
| 07-21 | NZ | Q2 CPI | ~1.3% q/q (RBNZ) | — | forward |
| 07-22 | ID | Bank Indonesia decision | — | 5.75% | forward |
| 07-24–31 | SG | MAS MPS (window) | — | band | forward — NOT today |
| 07-29 | US/AU | FOMC; AU Q2 CPI | hold / ~0.8% q/q | 3.75% (upper) | forward — soft CPI eased the hike risk |

---

## 8. Cross-cutting trade-ideas table  *(VIEW — provenance-tagged, never rated)*

The daily's single trade view — what the houses are floating across the universe. Each row: the idea, the assumption it rests on, its falsifier, provenance. **Never rated** — the PM judges. Expanded in the per-country reads below.

| # | Trade | Key driver / rationale | Assumption it rests on | Falsifier | Provenance |
|---|---|---|---|---|---|
| 1 | **Citi: add EMFX carry; close GBP + CAD rates-RV vs USD-payer; move short-EURUSD → flat** | Soft CPI + slow payrolls → Fed on hold for the summer, US front-end & USD range-bound = "goldilocks" for carry | US data stay soft-ish; front-end range-bound; oil doesn't spike | A hot PPI/retail re-lights the Fed; Iran escalation drives oil + USD | Citi 18317 |
| 2 | **Citi: take profit on short-inflation trade after the soft CPI** | June core flat validated the short-inflation view; core PCE tracking 0.21% | The disinflation print is the payoff, book it | A re-acceleration in PPI/energy reverses it | Citi 18240/18241 |
| 3 | **Nomura: take profit on long USD/CAD (+2.1% at 1.4090), cut conviction 2/5** | USD struggled to gain on hawkish Waller + oil → long-USD positioning stretched; BoC may miss hike pricing | Spec long-USD is crowded; short-CAD stretched | US data suddenly surprise up; BoC hawkish | Nomura 18221 |
| 4 | **HSBC: receive GBP 1Y1Y OIS at 4.35% (tgt 4.00%, stop 4.60%)** | ~60bp of hikes / 80% Sep-hike priced on the oil-led front-end sell-off; HSBC sees BoE on hold | Oil/ME stabilises; weak UK growth undermines the hike case | Higher oil / hawkish data extend the sell-off (stop 4.60%) | HSBC 18254 |
| 5 | **Citi: reiterate July S$NEER steepening on above-trend 2Q GDP** | Advance Q2 GDP 5.7% (beat); third year of above-trend growth supports a steeper slope | MAS tilts hawkish at the late-Jul MPS; growth stays firm | A dovish MAS hold / growth undershoot | Citi 18125 |
| 6 | **SocGen: take profit on short EUR/INR "as headwinds rise"** | INR headwinds building — hot CPI/WPI, oil, wider trade deficit → book the short-EURINR gain | The INR-supportive window is closing; book it | INR resumes strengthening (FCNR inflows, oil drops) | SocGen 18227 |
| 7 | **Nomura trade book: long EUR/INR (113), short USD/THB (32), pay Sep 5y India NDOIS (6.45%), Korea Dec-1s4s NDIRS steepener, pay AU3m1y vs US3m1y, short GBP/NZD (2.25)** | Cross-Asia RV: INR/THB/India-rates/Korea-curve/AU-US-rates/NZD-strength expressions | Each leg's local driver holds; oil contained | Oil to $100; a hawkish Fed re-steepens US; local surprises | Nomura 18221 |
| 8 | **BNP: long JGB 10s20s box; SocGen stay rec 1y1y vs JGB futures** | Katayama/GPIF repatriation + belly "behind the curve" cap the long end | Pension-flow ambiguity caps the long end; slow BoJ | A credible consolidation signal / fast BoJ-to-2% | BNP 18063, SocGen (carried) |
| 9 | **ANZ: short AUD rates — hold paid Dec-26 RBA OIS; pay the 1y/1y1y/2y1y belly fly** | RBA reaction function "heavily skewed" to inflation; supply shocks keep AUD long-end high; terminal underpriced | RBA stays inflation-focused; supply shocks persist | A dovish RBA pivot / growth cools / oil drops | ANZ 18342 |
| 10 | **JPM (Indonesia): MW IDR FX, MW IndoGBs, reduce UW INDONs; long INR vs PHP & IDR (RV)** | Fiscal deficit raised to 2.85% but consolidation encouraging; BI anchor vs weak seasonals | BI stays hawkish; FA flows keep improving; consolidation delivers | Fiscal slippage / FX pressure widens IndoGB risk premia | JPM 18151 |
| 11 | **Citi (carried): booked long USD/THB (+82bp); rolled bearish PHP 1x1.5 call ratio 3m** | THB underperformance + intervention anchor; cap PHP strength | FX intervention anchors USD/THB; PHP strength capped | ME de-escalation + sharp oil drop; strong PHP inflows | Citi 18064 |

**SYN — where the book tilts:** the soft CPI flipped the cross-universe tilt from *long-dollar / higher-for-longer* to *fade-the-dollar / carry-in-a-range*. Citi's rotation is the cleanest expression — closing its GBP and CAD receiver-vs-USD-payer RV trades, moving short-EURUSD to flat, and adding EMFX carry into a "goldilocks summer" of a range-bound Fed (row 1); Nomura books long USD/CAD on the same logic that long-USD positioning is stretched (row 3); and HSBC fades the oil-driven UK front-end sell-off by receiving GBP 1Y1Y (row 4). The counterweight is oil: every row still carries the Hormuz blockade as the two-sided tail, and Citi keeps a residual USD-asymmetry on that risk (18316). In Asia the book is data-led and constructive — Citi's SG steepener on the strong GDP (row 5), SocGen booking the short-EUR/INR gain as India's prints turn the headwind (row 6), Nomura's cross-Asia RV book (row 7), and JPM's Indonesia MW package (row 10). Japan stays a curve trade (row 8) and Australia a short-rates trade on the RBA's inflation skew (row 9). The through-line: the marquee resolved dovish, so the trades that assumed a hawkish US are being unwound, and carry/curve is where the book is putting risk while oil stays the shared falsifier.

---

## 9. Per-country read — A / B / C / D (the body)

Ordered by what moved this window: the resolved US CPI leads, then China's mixed Q2 GDP, Singapore's strong GDP, New Zealand, and Canada's live decision, then India's hot prints, Japan's curve, Australia, the UK, Indonesia, and the quiet tail (Hong Kong, Thailand, Malaysia, Philippines). Every country is read at the chunk level; quiet countries get the raised-floor A+B read grounded in the flagship/tape.

### United States — The soft CPI resolves the hike scare; the Fed is bought time

*Flagships read: JPM Daily Economic Briefing (18330), JPM US Market Intelligence Morning/Afternoon (18206/18362), JPM Daily Financial Markets Monitor (18079); GS US Daily Download (18133), GS Morning Wrap (18141), GS Morning (18129), GS FX Morning Notes (18193); Citi The Global Point (18180) + The Daily Update "From Waller to Warsh" (18244); DBDaily "Big miss on US CPI" (18349); Nomura US Daily Commentary (18334) + Monthly Inflation Monitor (18367); MS "July 14: Softer CPI, Weaker Dollar" (18365); UBS US Daily Data Recap (18337). CPI-reaction notes: GS 18251, JPM 18282, Citi 18239/18240/18241, MS 18265/18333, Nomura 18292, Barclays 18267/18312/18313/18266, SocGen 18293, BNP 18315, UBS 18295. Warsh: GS 18324, JPM 18328/18255, UBS 18338.*

**A · Themes in play**

| Rank | Theme | Assets | Banks talking | Why it matters to the PM |
|---|---|---|---|---|
| 1 | June core CPI SOFT (0.0% m/m / 2.6% y/y) — disinflation resumed | Rates, USD | GS, JPM, Citi, MS, Nomura, Barclays, SocGen, BNP, UBS | The hot-core trigger Waller named did not print; the Fed is bought time |
| 2 | Front-end rally + softer dollar | Rates, USD | Citi, Nomura, MS | Bull steepener; the hike scare priced out; USD range-bound |
| 3 | The dollar's non-reaction to hawkish catalysts | USD | Nomura, Citi | Long-USD positioning stretched; bar to further USD upside higher |
| 4 | Warsh testimony — dovish, idiosyncratic | Rates | GS, JPM, UBS | Chair refuses guidance, "make sure price spikes don't broaden out" |

**B · The "why"** The number that had the book coiled came soft, and the daily flagships were unanimous. **June core CPI fell −0.02% m/m** — flat to one decimal, **0.0% against a 0.2% survey — and the year-over-year rate dipped from 2.9% to 2.6%** (`cb_events` TE lane 60904/60905); headline dropped −0.42% m/m (survey −0.1%; YoY 4.2%→3.5%) on a 5.7% energy decline (60906/60907). GS's note (18251) documents the breadth: auto insurance −2.0% (second consecutive large monthly decline, −7bp on core), wireless services −3.1% (−5bp, reversing a May jump), hotels −2.8% (−4bp, World Cup payback), apparel −0.6%, medical −0.1% — with only software/accessories firmer (+2.2%, larger weight in PCE). GS marks **core PCE at 0.18% m/m** (vs its 0.24% pre-CPI), headline PCE −0.06%. **JPM (18282):** core −0.02% m/m (JPMC had 0.22%), YoY 2.9%→2.6%; "it is still an encouraging report that takes a little near-term pressure off the Fed," core PCE 0.168% m/m (3m annualised 3.0%, trimmed mean 2.4%→2.3%) — though it flags some core-services-ex-shelter softness as "probably one-off." **Barclays (18267):** the data "likely buy time for the FOMC to remain on hold and wait," with shelter deceleration and a core-PCE "0.2% handle" comforting, but stays attuned to energy/ME/AI price pressures; maintains a hold rest-of-year. **Citi (18317):** "one print does not constitute momentum, but the June softer-than-consensus data can allow the Fed to remain on hold for the summer," keeping the USD and front-end range-bound. **SocGen (18293):** "a big downside surprise." The tape confirmed it: **SOFR 2y −8.8bp into a bull steepener** (10y −2.6bp), the dollar broadly weaker (EUR +0.36%, and NZD/AUD/CAD +0.6-0.9%), gold +1.3%, Nasdaq +1.1%, VIX −0.66 to 16.5 — with strong bank EPS (JPM/BAC) adding to the risk-on tone (GS 18353). Two nuances: **Citi (18316)** notes the DXY recovered "a majority" of its intraday CPI losses into the US close and still leans USD-asymmetric on Middle-East risk; **Nomura (18221)** frames the more important signal as the USD's *failure* to rally on hawkish Waller + oil — spec positioning is stretched long-USD, so the bar to further USD outperformance is higher. On Warsh's House testimony (GS 18324, UBS 18338), the Chair kept his dovish, idiosyncratic line — the FOMC's job is to "make sure price spikes don't broaden out," current inflation measures are inadequate ("I am super interested in finding new measures"), and the balance sheet's "size and duration" are worth review — but offered no forward guidance.

**B2 · CPI within-window timeline — official voice vs sell-side read (13→15 Jul)**

The layers kept separate: **official** (Fed communications / the BLS release = FACT / official voice) vs **sell-side** (desk interpretation = VIEW). The sequence is the point — a hawkish official setup, a soft official print that undercut it, then an official reaction that clawed a little back.

| When (within-window) | Official voice (FACT / official) | Sell-side read (VIEW) |
|---|---|---|
| **13 Jul — pre-print setup** | **Gov. Waller** (Fed speech, `cb_events` 70629), verbatim (via UBS 18001): "there is still a credible case for inflation to begin to fall back to our 2 percent goal with policy at its current setting. But I am concerned about the equally plausible case that data in the coming weeks will show that inflation will remain at its elevated level or even trend higher, **requiring tighter monetary policy in the near term**" — outcomes "equally balanced," but he "will need to see several months of lower readings." **Gov. Bowman** also spoke (70625). | Read as the clearest hike-signal of the cycle. **UBS (18001):** "Waller: rates may need to be higher" — "near term" points to the July FOMC itself. **Nomura (18055), DB Fed Watcher (18035), JPM (17985)** echo the hawkish pivot. **Citi (18244, "From Waller to Warsh"):** given Warsh's "no forward guidance" stance it will be "difficult for him to strongly guide against hikes" — he may downplay Waller as "dots written in pencil with big erasers." July odds ~50%; the market prices a hike this year. |
| **14 Jul 08:30 ET — the print** | **BLS June CPI release** (`cb_events` 60904-60908): headline **−0.4% m/m / 3.5% y/y**; core **0.0% m/m / 2.6% y/y**; index 333.95 (vs 334.70 survey). Energy −5.7% (gasoline −9.7%); shelter slowed (OER +0.24%). | Unanimous "soft," with distinct emphases. **Citi (18239):** core "essentially flat… weakness largely across the board… all but rule out a July rate hike," and "similar data in coming months will lead markets to price out hikes altogether" (core PCE tracking 0.21% — flags the CPI-vs-PCE divergence). **Nomura (18334):** the "first monthly decline since May 2020"; cuts core-PCE to 0.168% (~2% annual) — "supports our Fed call of **no rate hikes indefinitely**," while noting the softness was "amplified by some one-off factors." **GS (18251/18252):** core PCE ~0.18%. **JPM (18282):** "takes near-term pressure off the Fed." **Barclays (18267):** "buys time for the FOMC to remain on hold." **SocGen (18293):** "a big downside surprise." **DB (18349):** "big miss." **MS (18365):** July-hike odds cut to **16% from ~50%** on Monday; 2y breakevens −14.4bp; US rates bull-steepened (2y −8.8bp). |
| **14 Jul — official reaction** | **Chair Warsh**, House testimony (`cb_events` 60911; GS 18324, UBS 18338): "a **sea change in new thinking**… a hinge point in history"; the FOMC's job is to "make sure price spikes don't broaden out"; he said the inflation "mission" is **not "accomplished"** and reiterated no tolerance for persistently elevated inflation; wants "new measures" of underlying inflation (backed away from trimmed-mean, implied core PCE inadequate too); balance-sheet changes would be "deliberate, publicly announced… over time." Barr / Cook / Bowman / Goolsbee also spoke (68427/68428/68429/60913). | **UBS (18338):** "little information content in the three hours"; the market seized on the "not declaring mission accomplished" line and **bonds sold off a smidge** — so yields **retraced part** of the CPI-driven decline (MS 18365: "the curve nevertheless closed materially steeper"). **Nomura (18334):** Warsh "did not break new ground," but the "regime change"/"sea change" rhetoric leaves "risk for more substantive policy changes." **Citi (18316):** DXY recovered a majority of its intraday CPI drop, still leans USD-asymmetric on ME risk. No house read the print as a head-fake — the debate is *pace of disinflation*, not direction. |
| **15 Jul — next official checkpoints (in-window)** | **Chair Warsh** Senate testimony (`cb_events` 68372); **Cook / Musalem / Williams** speak (68374/67507/67506); **June PPI + Beige Book** due (forward). | Desks watch PPI to firm the core-PCE read: Nomura (18334) expects a "modest positive contribution from PCE-relevant PPI," Citi's 0.21% PCE tracking "will change with PPI"; Citi (18317): the soft data "can allow the Fed to remain on hold for the summer." |

*Next catalyst pointer (one line, in-window): the 15-Jul PPI + the Warsh Senate leg are the day's remaining official checkpoints before the 29-Jul FOMC.*

**C · Consensus views (≥2 independent banks)**

| Theme | Banks | Shared claim | Evidence cited | What consensus is missing |
|---|---|---|---|---|
| June CPI is soft and disinflationary | GS, JPM, Citi, MS, Nomura, Barclays, SocGen, BNP, UBS | Core flat m/m, YoY to 2.6%; core PCE ~0.17-0.18% | Broad category declines; energy −5.7% | Split on how much of core-services-ex-shelter softness is one-off (JPM flags it) |
| The Fed is bought time to hold | JPM, Barclays, Citi, MS | The print supports a hold "for the summer"/rest of year | Core PCE 0.2% handle; slower payrolls | Whether PPI/retail (15-16 Jul) re-firm the core-PCE read |
| The dollar's reaction is muted vs the data | Nomura, Citi | USD gave back / didn't rally on the catalysts | DXY intraday round-trip; stretched CFTC longs | Directional resolution — carry-in-a-range (Nomura) vs residual ME asymmetry (Citi) |

**D · Differentiated / unique views**

| Bank | Asset | The view | Why it's different | Hidden assumption | Falsifier |
|---|---|---|---|---|---|
| Citi | Rates/FX | Rotate the book: add EMFX carry, close GBP+CAD receiver-vs-USD-payer RV, short-EURUSD → flat | Trades the soft print as a regime shift to "goldilocks" range-bound carry, not just a rate view | US data stay soft-ish; oil doesn't spike; front-end range-bound | A hot PPI/retail re-lights the Fed; Iran escalation lifts oil + USD |
| Nomura | FX | The USD's non-reaction is the signal — long-USD stretched, bar to upside higher; books long USD/CAD | Reads positioning over the data print; fades the crowded long-USD | Spec long-USD is the marginal driver now | US data surprise up and clear the stretched positioning |
| JPM | Rates | Encouraging but partly one-off — core-services-ex-shelter softness may not persist; core PCE stays firm YoY | Least willing to extrapolate the softness; keeps a "next move a hike" bias longer-run | Some June softness reverses; goods firm modestly | A second soft core print confirms the trend |

Trade rows: **#1, #2, #3**. **DEPTH:** US `econ.fact_indicator` deep (193 active indicators); June CPI is FACT in `cb_events`, confirmed across the TE (60904-60908) and BQL (41360/41362, index 333.952/336.065) lanes. The verified policy anchor is the 2026-06-17 FOMC hold + dots. **Flags:** PPI 15-Jul / retail sales 16-Jul forward; core-PCE figures are sell-side nowcasts (VIEW); WTI $78.78 (07-13, `fact_spot`), Brent ~$83-84 sell-side; DXY not loaded; `fact_bond_yield` EMPTY.

### Canada — BoC decides today; benign-core hold the base case, market keeps pricing hikes

*Flagships read: Nomura Strategy Trade Update "Take profit on long USD/CAD" (18221); JPM US High Grade Basis (country-tagged CA, 18200); carried BoC previews — JPM (17988), MS "Balancing Oil and Slack" (18051), GS "Activity Data Improves" (18040); ANZ "What's Priced In" (18004/18310).*

**A · Themes in play**

| Rank | Theme | Assets | Banks talking | Why it matters to the PM |
|---|---|---|---|---|
| 1 | BoC 15-Jul: hold 2.25% + MPR + presser | Rates, CAD | JPM, MS, GS | Benign core ~2%; excess supply; USMCA drag |
| 2 | Long USD/CAD booked (+2.1%) | CAD | Nomura | Long-USD stretched; BoC may not meet hike pricing |
| 3 | Market vs house on the path | Rates | ANZ, StanC | Market prices hikes; StanC sees a cut |

**B · The "why"** Into today's decision, the base case is a benign-core hold. The carried previews are aligned: **JPM (17988)** no change at 2.25%, limited guidance, core 3m run-rates ~2%, economy in excess supply, oil shock fading but the **USMCA trade drag intensified** (no extension, annual reviews, section 232/301 tariffs) — on hold rest of 2026, MPR headline shaded down. **MS (18051):** hold through year-end, "neither the bar for a hike nor the bar for a cut has been met," and USD/CAD "too rich at 1.42" with room to fall. **GS (18040):** a dovish hold, activity data improving. Against them: **StanC** (a cut by year-end, H2-hike pricing "premature") and the market (ANZ 18004: hikes priced). The fresh input today is **Nomura's (18221) profit-take on long USD/CAD at 1.4090 (+2.1% from a 22-May 1.38 entry)** — it lowers conviction to 2/5 and flags that short-CAD positioning is "especially stretched" (CFTC/CTA), that the BoC "may be unable to meet market pricing for rate hikes," and that it wants to re-express short CAD later on the "underwhelming macro backdrop." **CAD firmed +0.64% DoD** on the soft US CPI (`FX.fact_fx_rate`); CORRA 2y −1.9bp into the meeting (10y +1.1bp).

**B2 · BoC within-window timeline — official voice vs sell-side read (15 Jul)**

The layers kept separate; the decision is **pre-announcement at compile** — the official leg is the scheduled event and the BoC's own prior framing (as quoted in the flow), not yet an outcome.

| When (within-window) | Official voice (FACT / official) | Sell-side read (VIEW) |
|---|---|---|
| **15 Jul — scheduled + BoC's standing framing** | **BoC rate decision + Monetary Policy Report + Governor Macklem press conference** (`cb_events` 60980/60981/60982). Survey **hold at 2.25%** (prior 2.25%); no actual booked at run time — **forward**. The BoC's own quoted threshold (via JPM 17988): it would tighten only on a **"broadening"** of inflation, has stressed it "will deliver price stability," and has judged the economy in **"excess supply."** | Base case a benign-core hold. **JPM (17988):** "little evidence of the broadening that the BoC flagged as its threshold for tightening"; core 3m run-rates ~2%; oil shock fading but the **USMCA drag intensified** (no extension 1-Jul, annual reviews, section 232/301 tariffs); the 2Q Business Outlook Survey "a bit stale"; MPR headline shaded down, core held at 2.0%. **MS (18051):** hold through year-end — "contained core inflation, persistent slack, and trade uncertainty argue for patience"; June jobs "signal stabilization, not reacceleration." **GS (18040):** dovish hold on improving activity. |
| **15 Jul — the split into the decision** | *(pending — decision / statement / MPR / Macklem presser not yet released at compile)* | On direction after: **StanC** calls a cut by year-end (H2-hike pricing "premature"); the **market** prices hikes; **MS (18051):** USD/CAD "too rich at 1.42," room to fall as USMCA uncertainty unwinds; **Nomura (18221)** booked long USD/CAD (+2.1%), flagging the BoC "may be unable to meet market pricing for rate hikes." |

*Next catalyst pointer (one line, in-window): the decision, statement, MPR and Macklem presser land later on 15-Jul — the official voice that resolves the hold-vs-cut-vs-hike split above.*

**C · Consensus views**

| Theme | Banks | Shared claim | Evidence cited | What consensus is missing |
|---|---|---|---|---|
| Hold 15-Jul; benign core, persistent slack | JPM, MS, GS | No change; core ~2%, excess supply | Core 3m ~2%; USMCA drag | Direction after: dovish (GS/StanC) vs market's hike pricing |

**D · Differentiated / unique views**

| Bank | Asset | The view | Why it's different | Hidden assumption | Falsifier |
|---|---|---|---|---|---|
| Nomura | CAD | Booked long USD/CAD; wants to re-short CAD later — BoC may miss market hike pricing | Trades the positioning + the macro-vs-pricing gap, not the decision itself | Short-CAD stretched now; BoC underdelivers vs pricing later | A hawkish BoC surprise / US data surprise up lifts USD/CAD |
| StanC | Rates/CAD | A cut by year-end; H2-hike pricing "premature" | Only house calling an outright 2026 cut | Downside growth > upside inflation; core moderates | Growth regains momentum / oil re-spike |

Trade rows: **#3**. **DEPTH:** CA `econ.fact_indicator` thin (most macro not loaded) — the verified anchor is the 2026-06-10 BoC hold. **Flags:** BoC decision + MPR + presser 15-Jul forward (all `cb_events` actual null, 41366/60980/60981/60982); jobs/core figures sell-side (VIEW).

### United Kingdom — HSBC fades the oil-driven hike pricing; GDP 16-Jul, Burnham Budget in focus

*Flagships read: HSBC "UK Rates Trade Idea: Receive GBP 1Y1Y OIS" (18254); JPM "UK politics: Ten views on the path ahead" (18264) + UK Money Market Report (18077) + Bailey speech note (18326); UBS European Economic Perspectives "UK & France: Fiscal risk scenarios" (18109); carried StanC UK read; ANZ "What's Priced In" (18004/18310).*

**A · Themes in play**

| Rank | Theme | Assets | Banks talking | Why it matters to the PM |
|---|---|---|---|---|
| 1 | HSBC receives GBP 1Y1Y — fade the hike repricing | Rates, GBP | HSBC | ~60bp of hikes / 80% Sep-hike priced on the oil sell-off |
| 2 | Burnham Budget: significant policy, no big net stimulus | Rates, GBP | JPM | Fiscal-credibility watch; compositional changes |
| 3 | GBP firmer with US; GDP 16-Jul | GBP, rates | (market/calendar) | GBP +0.35%; SONIA 2y −2.7bp |

**B · The "why"** The UK is a fade-the-hike-pricing story on top of a fiscal-politics backdrop. **HSBC (18254)** opens a new trade to **receive GBP 1Y1Y OIS at 4.35% (target 4.00%, stop 4.60%)**: fresh Middle-East tension put upward pressure on oil and re-lit the correlation with the front-end, so ~60bp of hikes and an ~80% September-hike probability are now priced — but HSBC holds a more dovish view (the MPC "kept its options open" in June with only two hike votes, and it sees rates unchanged before easing resumes in late 2027), argues the front-end "has begun to find support around these levels," and reasons that tighter market conditions via higher forward rates "help to do the BoE's job," allowing patience into the 30-Jul MPR. **JPM (18264):** Andy Burnham's Budget will bring "several significant policy announcements and compositional fiscal changes" but "no large net stimulus for next year" as he builds market credibility (net favourability improving). **UBS (18109)** works the UK/France fiscal-risk scenarios. **GBP firmed +0.35% DoD** on the soft US CPI (`FX.fact_fx_rate`) and SONIA rallied with the US (2y −2.7bp / 10y −1.9bp — cash gilts not loaded, so this is the OIS read). UK GDP prints 16-Jul (m/m survey 0.1%).

**C · Consensus views** Limited independent in-window UK-macro coverage; the anchor is HSBC's dovish fade of the oil-driven hike pricing plus JPM's Burnham-fiscal read, against a market pricing an ~80% September hike.

**D · Differentiated / unique views**

| Bank | Asset | The view | Why it's different | Hidden assumption | Falsifier |
|---|---|---|---|---|---|
| HSBC | Rates/GBP | Receive GBP 1Y1Y (4.35%) — the oil-led hike repricing overshoots; BoE stays patient | Actively fades a market pricing ~80% Sep hike; ties it to ME/oil stabilising | Oil/ME stabilises; weak growth undermines the hike case | Higher oil / hawkish data extend the sell-off (stop 4.60%) |
| JPM | Rates/GBP | Burnham Budget: significant policy, no big net stimulus; two years of parliament already gone | Frames the fiscal transition as credibility-building, not stimulus | Burnham prioritises market credibility over pre-election spend | A larger-than-expected net stimulus / fiscal-rule loosening |

Trade rows: **#4**. **DEPTH:** UK `econ.fact_indicator` thin (most macro not loaded) — the verified anchor is the 2026-06-18 BoE hold 7-2. **Flags:** UK GDP 16-Jul forward; HSBC's dovish fade vs the market's ~80% Sep-hike pricing unreconciled (both shown); CPI/fiscal figures sell-side (VIEW).

### China — Q2 GDP prints mixed: headline misses, June activity beats; record trade surplus

*Flagships read: GS "Trade growth accelerated further in June" (18092) + "15th FYP for Expanding Consumption" (18093); JPM "China: Trade resilient, but hard to sustain growth alone" (18216); Barclays "China: Booming yet bifurcated exports" (18117); UBS China Economic Comment "Another positive surprise in exports" (18231); Nomura "Li Qiang urges countercyclical policy" (18156) + "Growth of both exports and imports surged" (18161); DB China Macro (18090 consumption pivot / 18091 trade surge); HSBC "China trade: Surging higher" (18098) + China Macro Tracker (18359); ANZ China trade (18115/18085); Citi "AI Supercycle Powers a Structural Export Upswing" (18122); StanC "Infrastructure spending likely to pick up in H2" (18082, carried).*

**A · Themes in play**

| Rank | Theme | Assets | Banks talking | Why it matters to the PM |
|---|---|---|---|---|
| 1 | Q2 GDP mixed — headline 4.3% miss, June activity beat | Rates, CNH, equities | GS, UBS, StanC, Nomura | Weakest sequential since 2022, but IP + retail firmer than expected |
| 2 | Record June trade surplus ($125.6bn) | CNH, rates, equities | GS, JPM, Barclays, UBS, Nomura, HSBC, DB | Export machine offsets soft domestic demand — the growth engine |
| 3 | H2 "countercyclical" policy signalled | Rates, equities | Nomura, StanC, DB | Li Qiang urges stepped-up support; H2 infra re-acceleration |
| 4 | Exports "bifurcated" — price not volume | Equities | Barclays, GS, Citi | Semis value +121.9% but volume −0.5% — AI-price-led, not broad |

**B · The "why"** China's Q2 GDP delivered a two-sided print. **Headline growth came in at 4.3% y/y** (`cb_events` 60929; survey 4.5%, forecast 4.6%, from 5.0% in Q1) — a **miss**, and with the sequential pace at **0.9% qoq** (60933; in line with survey, below the 1.0% forecast) the **weakest sequential quarter since 2022**. Fixed-asset investment stayed weak at **−5.7% ytd** (60932; worse than the −4.9% survey). But June activity ran **firmer than expected**: **industrial production 5.3% y/y** (60930; survey 4.6%) and **retail sales turned positive at +1.0%** (60931; survey −0.1%, prior −0.6%) — the first positive retail print in the run — with **industrial capacity utilisation 73%** (60934) and unemployment easing to **5.0%** (60935, from 5.1%). The net is a mixed, stabilising-on-stimulus read: the level of growth disappointed but the momentum in the two most-watched activity gauges improved. The 07-15 CNH/equity reaction is still forming. This sits on top of a **record June trade surplus** (`cb_events` 60864-60866): $125.6bn (from $105.4bn), **exports +27% yoy, imports +36% yoy** — both far above consensus. **GS (18092):** sequential exports +6.9% sa non-annualised, led by AI-related products and autos (motor-vehicle exports +69.6% yoy, aluminium +77%); semiconductor export *value* rose +121.9% yoy but *volume* fell −0.5% — strength is price, not units; exports to the US decelerated (+13.9% yoy vs +35.4% May) while ASEAN (+34.5%) stayed strong. **Barclays (18117):** "booming yet bifurcated." **UBS (18231):** "another positive surprise" in exports. **JPM (18216):** trade is resilient but "hard to sustain growth alone" — the activity beat is the counterpoint. **Nomura (18156):** at a 13-July symposium Premier Li Qiang urged "countercyclical" policy be "stepped up again" in H2; **StanC (18082):** H2 infrastructure should pick up using the existing quota. CNH firmed +0.18% DoD; HIBOR backed up (2y +6.3bp / 10y +4.3bp — the Asian close, pre-US-CPI), and Hong Kong equities rose (HSI +0.52%, HSCE +0.46%).

```spiderchart
{"type":"bar","title":"China Q2: headline GDP missed, but June IP and retail beat","caption":"Grounded: calendar.cb_events (ids 60929/60930/60931), printed actual vs survey. Headline GDP y/y undershot while industrial production and retail sales came in above consensus — a mixed, stabilising-on-stimulus print. Retail turned positive (+1.0%) against a call for a further contraction.","series":[{"name":"Actual","color":"#2b5a86","points":[["GDP y/y",4.3],["IP y/y",5.3],["Retail y/y",1.0]]},{"name":"Survey","color":"#b5761f","points":[["GDP y/y",4.5],["IP y/y",4.6],["Retail y/y",-0.1]]}]}
```

**C · Consensus views**

| Theme | Banks | Shared claim | Evidence cited | What consensus is missing |
|---|---|---|---|---|
| Exports strong but price/AI-driven and bifurcated | GS, Barclays, UBS, HSBC, Nomura | Record surplus; semis value up on price, volume flat | Semis +121.9% value / −0.5% volume; autos +69.6% | The June activity beat (IP 5.3%, retail +1.0%) partly answers the domestic-demand doubt |
| H2 needs / will get more policy support | Nomura, StanC, DB | Countercyclical support steps up; H2 infra re-accelerates | Li Qiang symposium; existing LGSB quota | Magnitude — the headline GDP miss + weak FAI vs the activity beat leaves the size of any push open |

**D · Differentiated / unique views**

| Bank | Asset | The view | Why it's different | Hidden assumption | Falsifier |
|---|---|---|---|---|---|
| GS | Equities | Trade + 15th FYP "supply-side push" for consumption; exports price-led, not a demand signal | Reads the surplus as nominal/price, not a growth-strength tell | AI-price effect flatters headline exports; volume flat | Sustained broad-based volume acceleration (the June retail beat is an early counter-signal) |
| JPM | Macro | Trade resilient but "hard to sustain growth alone" — domestic demand the binding constraint | Least willing to read the trade beat as a growth upgrade | External strength doesn't fix domestic weakness | A run of firmer domestic prints (June IP + retail already beat) |
| Citi | Equities | An "AI Supercycle" powers a *structural* export upswing | Frames the semis strength as durable/structural, not a one-off price effect | AI-capex demand persists; not just a price spike | The semis price effect fades / volume stays flat |

Trade rows: none direct (China expressed via CNH/HK). **DEPTH:** China `econ.fact_indicator` deep (HK/CN loaded); Q2 GDP + June activity (IP/retail/FAI) and June trade are all FACT in `cb_events` (60929-60935, 60864-60866). **Flags:** the 07-15 CNH/equity reaction to the print is still developing; a detailed by-country/product trade breakdown is due 20-Jul (GS).

### Japan — The long end keeps richening on the GPIF/Katayama repatriation theme

*Flagships read: Citi "Will Japanese pension funds repatriate investment?" (18123) + "The BoJ's JGB Holdings as of July 10" (18348) + The Point for Japan (18319); Nomura Japan Economic Weekly (18291) + Yen Rates Daily Monitor (18159) + Yen RV Analytics (18158) + JPY Intraday (18222) + Japan Research Pack (18368); GS "CPI Base-Year Revision" (18138) + GS Tokyo Daily (18357) + JGBs note (18351); UBS Japan Economic Comment "Limited impact of 2025 benchmark change" (18106); MS "The Viewpoint: 10 questions about BoJ policy" (18288); BNP "JPY rates: long 10s20s box" (18063); Barclays "GPIF FY25 rebalancing" (18062, carried).*

**A · Themes in play**

| Rank | Theme | Assets | Banks talking | Why it matters to the PM |
|---|---|---|---|---|
| 1 | GPIF/Katayama repatriation caps the long end | JGBs, JPY | Citi, Nomura, BNP, Barclays | 10-20y JGBs richer; JPY-supportive flow |
| 2 | Govt revising Basic Policy MP wording | Rates | Nomura | After the long-end rise; still favours accommodation |
| 3 | June hike "retrospectively" supported | Rates | Nomura | Branch managers report proactive price hikes |
| 4 | CPI base-year revision (Jan-Jun to be restated) | Rates | GS, UBS | Data-continuity issue; limited signal impact |

**B · The "why"** Japan's long end kept rallying on the pension-repatriation theme. **Citi (18123):** Finance Minister Katayama's 10-July call for the GPIF and other public pension funds to invest in Japanese assets fits the Takaichi government's JPY-defence and its aim to *stabilise JGB yields* (critical to its public/private capex program). But Citi reads it as likely **incremental**: the GPIF basic-portfolio review is not due until late 2029 (any change applies from spring 2030), and the March-2026 annual review left the portfolio unchanged — so the near-term route is the allowance for deviation from the basic portfolio, plus corporate pension funds gradually adding JGBs on higher yields, which "should provide some support to the JPY." **Nomura (18291):** the government is revising the Basic Policy wording on monetary policy after the market reaction (rising long-term rates) but will keep favouring accommodation; the July BoJ branch-managers' meeting reported solid corporate activity and proactive price hikes in response to higher oil — "retrospective support for the June rate hike," though no fresh signal on the outlook. **TONAR 10y −9.5bp DoD** (richer; 2y −2.3bp) — the long-end rally is the clearest universe rates move. **GS (18138):** a CPI base-year revision will restate Jan-Jun 2026 inflation (UBS 18106: "limited impact"). Equities rebounded from Monday's rout (Nikkei +0.75%, TOPIX +0.79%); June IP final was soft (0.1% m/m, −2.1% yoy). JPY ~flat (+0.14%).

**C · Consensus views**

| Theme | Banks | Shared claim | Evidence cited | What consensus is missing |
|---|---|---|---|---|
| Pension-repatriation flow caps/richens the long end | Citi, Nomura, BNP, Barclays | 10-20y JGBs supported; JPY tailwind | Katayama comments; GPIF FY25 rebalancing; TONAR 10y −9.5bp | Timing/size — incremental (Citi: 2029 review) vs a faster signal |

**D · Differentiated / unique views**

| Bank | Asset | The view | Why it's different | Hidden assumption | Falsifier |
|---|---|---|---|---|---|
| Citi | JGBs/JPY | Repatriation is real but incremental (2029 basic-portfolio review) — corporate pensions the near-term channel | Tempers the repatriation narrative with the institutional timeline | Katayama can't change GPIF policy at will; change applies 2030 | A discretionary policy-mix change inside the deviation allowance |
| BNP | JGBs | Long 10s20s box — belly "behind the curve" | A specific curve expression of the flow-caps-the-long-end view | Flow ambiguity caps the long end; slow BoJ, weak FX | A credible consolidation signal / fast BoJ-to-2% |

Trade rows: **#8**. **DEPTH:** Japan `econ.fact_indicator` thin/partial (IP final booked; most macro not loaded — see the JP econ discovery backlog). The verified anchor is the 2026-06-16 BoJ +25bp hike. **Flags:** GPIF flow qualitative (VIEW); CPI base-year revision a forthcoming data change; JGB long-end is swap/OIS (`fact_bond_yield` EMPTY).

### Hong Kong — Quiet; HKD firm on the peg, HIBOR backed up, soft US CPI eases Fed-linked pressure

*Flagships read: HSBC China Macro Tracker (18359, HK/China); GS Asia midday regional update (18139); Citi The Point for Asia Pacific (18347); MS China/HK Flows & Positioning Monthly (18366). No dedicated HK-macro flagship in-window — HK trades off the China tape and the Fed-linked peg.*

**A · Themes in play**

| Rank | Theme | Assets | Banks talking | Why it matters to the PM |
|---|---|---|---|---|
| 1 | Fed-linked peg; soft US CPI eases pressure | HKD, HIBOR | (peg mechanics / GS, Citi) | Lower US front-end relieves the linked-rate pressure into 07-15 |
| 2 | HK equities track the China trade beat | Equities | MS, GS | HSI +0.52%, HSCE +0.46% on the record surplus |

**B · The "why"** Hong Kong is a genuinely quiet in-window read, trading off the China tape and the Fed-linked peg rather than any domestic catalyst. **HKD was flat (0.00% DoD)** on the peg; **HIBOR backed up (2y +6.3bp / 10y +4.3bp)** — but that last tick is the Tuesday Asian close, *before* the soft US CPI, so it carries the pre-print hawkish/Fed-linked tone; the soft US front-end (SOFR 2y −8.8bp) should relieve that pressure on the 07-15 session. HK equities tracked the record China trade surplus higher (HSI +0.52%, HSCE +0.46%, HSTECH +0.07%). The one thing to watch: HK unemployment prints 17-Jul (prior 3.7%). No house floated a fresh HK-specific rates or FX trade in-window.

**C · Consensus views** No independent HK-specific macro cluster in-window; HK sits inside the China-trade and Fed-linked-peg reads above.

**D · Differentiated / unique views** None HK-specific in-window.

Trade rows: none. **DEPTH:** HK `econ.fact_indicator` deep (loaded); the verified anchor is the USD-peg / LAF band (no HKMA decision — linked to the Fed). **Flags:** HKD/HIBOR moves are the pre-US-CPI Asian close (the soft-CPI relief lands 07-15); HK unemployment 17-Jul forward.

### New Zealand — QSBO shows acute pricing; ANZ and UBS both keep the RBNZ hiking

*Flagships read: ANZ "NZ NZIER QSBO: weak activity; acute inflation pressures" (18030) + NZD Update (18061) + REINZ housing (18340); UBS "New Zealand Economic Comment: QSBO pricing intentions surge" (18107) + Australian/NZ Rates Strategy "flatten NZ's 3s..." (18165); JPM "RBNZ, Conway: Finding signal in the inflation noise" (18078); GS "Conway: Monetary policy may need to respond more firmly" (18068) + "NZIER QSBO: activity improves, inflation measures..." (18070); DB "Macro Notes: NZ: Quick take on the QSBO" (18067); Westpac "First Impressions: NZIER QSBO" (18059) + NZD FX Weekly (18083).*

**A · Themes in play**

| Rank | Theme | Assets | Banks talking | Why it matters to the PM |
|---|---|---|---|---|
| 1 | QSBO: acute pricing (selling price 22→41) | Rates, NZD | ANZ, UBS, GS, JPM, DB, Westpac | Corroborates the RBNZ's July kick-off and signalled follow-up hikes |
| 2 | Conway (dove) flags price-setting asymmetry | Rates | ANZ, GS, JPM | A dovish official warns firms pass costs up but not down |
| 3 | Activity soft but improving; negative output gap | Rates | ANZ, UBS, DB | Q2 GDP forecast −0.2% q/q; capacity consistent with slack |
| 4 | NZD firmest in the universe (+0.85%) | NZD | ANZ, Westpac | Soft US CPI + hawkish RBNZ tailwind |

**B · The "why"** New Zealand added a second hawkish signal to its freshly-started hiking cycle. The **NZIER Q2 QSBO** (ANZ 18030) showed a partial rebound in headline business confidence (to +12 sa, from +1) but **acute cost and pricing pressures — the average selling-price gauge jumped 22→41** — alongside soft activity and capacity indicators "very much consistent with a negative output gap." ANZ: today's cost/pricing signals "will be of some concern" to the RBNZ, and the data are "consistent with the view that the July kick-off to the hiking cycle (and signalled follow-up hikes) was justified" — it keeps **+25bp in both September and October**, its Q2 GDP forecast at −0.2% q/q (annual growth accelerating to 1.9% y/y). **UBS (18107):** "QSBO pricing intentions surge despite lower oil," selling prices "remain relatively high compared with the RBNZ's 2% target midpoint," domestic trading activity ticked up to +1 (implying a real-GDP recovery), employment intentions bounced to −1 — UBS keeps **+25bp in September and December to 3.00%**, though it cautions the confidence rebound (survey ran 10-Jun to 7-Jul, spanning the fuel-crisis MoU) "may be overstated." **GS (18068):** Chief Economist Conway (the RBNZ's most dovish member) noted "unhelpful asymmetry" — firms pass the cost shock into prices but may not pass the reversal back — read as "clearly hawkish." **NZD was the firmest currency in the universe (+0.85% DoD)** on the soft US CPI plus the hawkish domestic tone; NZIONA front rallied slightly (2y −2.1bp, the Asian close). The 21-Jul Q2 CPI is the arbiter.

**C · Consensus views**

| Theme | Banks | Shared claim | Evidence cited | What consensus is missing |
|---|---|---|---|---|
| QSBO pricing is acute; RBNZ hikes are justified | ANZ, UBS, GS, JPM, DB | Selling-price gauge surged; more hikes coming | Selling price 22→41; Conway asymmetry | Sep+Oct (ANZ) vs Sep+Dec (UBS) — the timing/pair of hikes |
| Activity soft but improving; output gap negative | ANZ, UBS, DB | Trading activity +1; capacity consistent with slack | QSBO capacity/activity; GDP −0.2% q/q | How fast the recovery firms vs how sticky the pricing is |

**D · Differentiated / unique views**

| Bank | Asset | The view | Why it's different | Hidden assumption | Falsifier |
|---|---|---|---|---|---|
| ANZ | Rates | +25bp in *both* Sep and Oct (a back-to-back pair) | Most front-loaded hike path in the cluster | Pricing stays acute; the cost shock doesn't reverse cleanly | A soft 21-Jul Q2 CPI / pricing gauge rolls over |
| UBS | Rates | +25bp Sep and Dec to 3.00%; confidence rebound "may be overstated" | Spaces the hikes and discounts the confidence bounce | The MoU-driven confidence lift is not durable | A durable confidence/activity acceleration pulls hikes forward |

Trade rows: (Nomura short GBP/NZD 2.25, row 7; UBS flatten-NZ-3s carried). **DEPTH:** NZ `econ.fact_indicator` loaded; QSBO is a proprietary survey (per flow, not `cb_events`). The verified anchor is the 2026-07-08 RBNZ +25bp hike. **Flags:** Q2 CPI 21-Jul forward; QSBO figures per flow (18030); ANZ Sep+Oct vs UBS Sep+Dec unreconciled (both shown).

### Australia — Data improved (NAB, consumer confidence); ANZ stays short AUD rates on the RBA's inflation skew

*Flagships read: GS "Consumer Sentiment: Modest improvement" (18072) + "NAB Business Survey: Conditions Steady" (18073); JPM "Australian NAB survey: Further improvement" (18076); UBS "Australian Economic Comment: Business conditions steady" (18164) + Global Strategy "Rates Map — Waller's wake-up call" (18110); Westpac "Consumer pessimism eases" (18084) + "Australian Business Conditions and Confidence" (18112) + Antipodean Daily Wrap (18167); ANZ "AUD Rates Update: inflation risks favour being short AUD rates" (18342) + Daily Rates RV Pack (18029/18341) + Roy Morgan Consumer Confidence (18060).*

**A · Themes in play**

| Rank | Theme | Assets | Banks talking | Why it matters to the PM |
|---|---|---|---|---|
| 1 | NAB + consumer confidence improved | Rates, AUD | GS, JPM, UBS, Westpac | Firmer surveys support the RBA's inflation focus |
| 2 | ANZ: short AUD rates (paid Dec-26 RBA OIS) | Rates | ANZ | RBA reaction function "heavily skewed" to inflation; terminal underpriced |
| 3 | Supply-shock world keeps long-end yields high | Rates | ANZ, UBS | Goods-inflation/unemployment beta has risen |
| 4 | AUD strong on soft US CPI (+0.82%) | AUD | (market) | Second-firmest universe currency |

**B · The "why"** Australia's surveys improved and the rates desk stayed hawkish. **NAB business confidence rose to −5** (from −14, `cb_events` 60860) and conditions held steady at +3 (GS 18073); **Westpac consumer confidence rose +4.1%** (from −2.9%, 60858; GS 18072 "modest improvement," Westpac 18084 "pessimism eases"). **ANZ (18342)** is the sharpest read: it "remains short AUD and USD rates," holding its **paid Dec-26 RBA OIS** recommendation because the RBA's reaction function is "heavily skewed towards concerns about too-high inflation" and terminal pricing "doesn't fully factor this risk in." ANZ leans on Assistant Governor Hunter's recent speech (the labour-market/inflation trade-off has worsened) and argues the world is "more prone to supply shocks," which should keep AUD long-end yields "in a higher range" — noting the unusual steepening in the goods-inflation/unemployment beta reflects global supply chains rather than domestic drivers. It favours paying the belly on a 1y/1y1y/2y1y fly (lower duration beta than curve trades). **UBS's Rates Map (18110)** frames the global backdrop as "Waller's wake-up call" (pre-CPI). **AUD firmed +0.82% DoD** on the soft US CPI; AONIA front rallied slightly (2y −2.7bp, the Asian close). Q2 CPI (29-Jul) is the domestic fork.

**C · Consensus views**

| Theme | Banks | Shared claim | Evidence cited | What consensus is missing |
|---|---|---|---|---|
| Surveys improved; RBA stays inflation-focused | GS, JPM, UBS, Westpac | NAB confidence −5, consumer +4.1%; conditions steady | NAB survey; Westpac consumer conf | Whether the improvement survives the oil re-spike (surveys pre-date it) |

**D · Differentiated / unique views**

| Bank | Asset | The view | Why it's different | Hidden assumption | Falsifier |
|---|---|---|---|---|---|
| ANZ | Rates | Short AUD rates (paid Dec-26 RBA OIS); pay the belly fly — terminal underpriced | Actively trades the RBA's inflation skew + a supply-shock long-end thesis | RBA stays inflation-focused; supply shocks keep long-end high | A dovish RBA pivot / growth cools / oil drops / soft Q2 CPI |

Trade rows: **#9** (and Nomura pay AU3m1y vs US3m1y, row 7). **DEPTH:** AU `econ.fact_indicator` deep (loaded); NAB/consumer confidence booked in `cb_events`. The verified anchor is the 2026-06-16 RBA hold. **Flags:** the NAB/consumer surveys pre-date the oil re-spike (a data-timing caveat); Q2 CPI 29-Jul forward; AONIA is the pre-US-CPI Asian close.

### Singapore — Advance Q2 GDP beats at 5.7%; Citi reiterates its July S$NEER steepening call

*Flagships read: JPM "Singapore: Growth momentum unbowed, unbent, unbroken" (18103); Citi "Reiterating Our Jul Steepening Call On Above-trend 2Q26 GDP" (18125); Nomura "First Insights — Singapore: Strong growth momentum sustained" (18157); GS "Growth holds firm, led by tech and services" (18096); SocGen SG Inflation Newsflow Monitor (18226).*

**A · Themes in play**

| Rank | Theme | Assets | Banks talking | Why it matters to the PM |
|---|---|---|---|---|
| 1 | Advance Q2 GDP 5.7% (beat 5.5%) | Rates, SGD | JPM, Citi, Nomura, GS | Third year of above-trend growth; 1Q revised up to 6.3% |
| 2 | Citi reiterates July S$NEER steepening | Rates | Citi | Above-trend growth supports a steeper slope into the MAS |
| 3 | Manufacturing rebounded (23.1% ar) | Rates | JPM, GS | Tech/semis + trade-related services lead |
| 4 | MAS MPS is the late-Jul window — NOT today | Rates | (calendar) | The resolved SG event is the GDP; MAS is 24–31 Jul |

**B · The "why"** Singapore's advance Q2 GDP came in strong. **5.7% y/y** (`cb_events` 60857; survey 5.5%, forecast 5.0%) with 1Q revised **up to 6.3% (from 6.0%)**; sequential 1.1% qoq (4.6% ar). **JPM (18103)** — "unbowed, unbent, unbroken" — GDP "powered ahead despite Middle-East conflict": manufacturing momentum rebounded to 23.1% ar (cycle-high 12.2% yoy) after the 1Q pharma-unwind contraction, trade-related services stayed the driver, construction still +12.5% ar for 1H; it maintains an above-consensus **4.6% full-year forecast** (consensus 3.7%) but expects growth to step down to ~1% ar in 2H on moderating trade-services and slower real manufacturing even as tech prices flatter nominal exports. **Citi (18125):** the above-trend 2Q print supports **reiterating its July S$NEER steepening call**. **Nomura (18157):** "strong growth momentum sustained." **GS (18096):** "growth holds firm, led by tech and services." **SGD firmed +0.28% DoD** on the soft US CPI; **SORA backed up (2y +4.8bp / 10y +5.8bp)** on the strong print (the Asian close, pre-US-CPI). **Important:** the MAS MPS is the **24–31 July window — not today**; the resolved SG event is the advance GDP. (Any prior `cb_events` row placing MAS on 14-Jul was a bad estimated row, since deleted.)

**C · Consensus views**

| Theme | Banks | Shared claim | Evidence cited | What consensus is missing |
|---|---|---|---|---|
| Q2 GDP beat; growth above trend, tech/manufacturing-led | JPM, Citi, Nomura, GS | 5.7% beat; 1Q revised up; manufacturing rebound | 5.7% vs 5.5%; mfg 23.1% ar | The 2H step-down (JPM ~1% ar) vs the current momentum |

**D · Differentiated / unique views**

| Bank | Asset | The view | Why it's different | Hidden assumption | Falsifier |
|---|---|---|---|---|---|
| Citi | Rates | Reiterate July S$NEER steepening on above-trend growth | The only house with an explicit MAS-slope trade off the GDP | MAS tilts hawkish at the late-Jul MPS; growth stays firm | A dovish MAS hold / a 2H growth undershoot |
| JPM | Macro | Above-consensus 4.6% FY, but a sharp 2H step-down to ~1% ar | Pairs the beat with the most explicit deceleration call | Trade-services moderate; tech prices flatter, not volumes | 2H momentum holds / manufacturing stays hot |

Trade rows: **#5**. **DEPTH:** SG `econ.fact_indicator` loaded; advance Q2 GDP is FACT in `cb_events`. The verified anchor is the MAS S$NEER band (no rate decision). **Flags:** MAS MPS 24–31 Jul forward (NOT today); SORA is the pre-US-CPI Asian close.

### Indonesia — 2026 fiscal deficit target raised to 2.85%; JPM stays MW IDR / MW IndoGBs

*Flagships read: JPM "Indonesia: Fiscal outlook and market implications" (18151).*

**A · Themes in play**

| Rank | Theme | Assets | Banks talking | Why it matters to the PM |
|---|---|---|---|---|
| 1 | 2026 deficit target raised to 2.85% (from 2.68%) | Rates, IDR | JPM | Higher fuel-subsidy spend, still below the statutory ceiling |
| 2 | BI hawkish pivot anchors the rupiah | IDR | JPM | BOP firm but sentimental; weak seasonals a headwind |
| 3 | IndoGB risk premia skew wider but bottoming | Rates | JPM | Net debt issuance the key catalyst to watch |

**B · The "why"** Indonesia is a fiscal-and-positioning read this window. **JPM (18151):** the **2026 fiscal deficit target was raised to 2.85% of GDP (from 2.68%)**, reflecting higher fuel-subsidy spending but remaining below the statutory ceiling; the planned consolidation via expenditure cuts is "encouraging," though implementation faces the government's growth objectives. On strategy: BOP fundamentals are "firm but sentimental," with foreign-inflow signs improving; a hawkish BI pivot provides an anchor, but weak seasonals and a stronger USD point to "moderate IDR underperformance ahead." JPM stays **MW IDR FX and MW IndoGBs** (net debt issuance the catalyst; heavy UW positioning already prices well-known fiscal risks; risk premia may widen further on FX pressure and reduced BI support), and expresses relative value as **long INR vs PHP and IDR**. On credit, it **reduces its UW in INDONs**, taking partial profit on a 116bp underperformance while still calling valuations rich. **IDR firmed +0.27% DoD** on the soft US CPI; JIBOR 10y +5.3bp (the Asian close). BI decides 22-Jul.

**C · Consensus views** No independent second-house Indonesia-macro cluster in-window; JPM's fiscal-and-positioning note is the anchor, sitting with Citi's carried EM-book o/w IDR.

**D · Differentiated / unique views**

| Bank | Asset | The view | Why it's different | Hidden assumption | Falsifier |
|---|---|---|---|---|---|
| JPM | FX/rates/credit | MW IDR, MW IndoGBs, reduce UW INDONs; long INR vs PHP & IDR | The most complete cross-asset Indonesia positioning read in-window | BI stays hawkish; FA flows keep improving; consolidation delivers | Fiscal slippage / FX pressure widens IndoGB risk premia |

Trade rows: **#10**. **DEPTH:** ID `econ.fact_indicator` deep (loaded). The verified anchor is the 2026-06-18 BI +25bp hike. **Flags:** BI decision 22-Jul forward; the fiscal-deficit figure is a government target (per flow / JPM 18151).

### Thailand — Quiet; Citi's booked long USD/THB carries, BoT on hold; THB flat, rates backed up

*Flagships read: Citi "Strategy: TP on Long USDTHB Exposure; Rolling Over Bearish [PHP]" (18064); Citi The Point for Asia Pacific (18347); SocGen EM/FX Asia Pulse (18163); Nomura SDR FX Analysis — Asia (18370). No dedicated Thailand-macro flagship in-window.*

**A · Themes in play**

| Rank | Theme | Assets | Banks talking | Why it matters to the PM |
|---|---|---|---|---|
| 1 | Citi's booked long USD/THB (+82bp), FX-intervention anchor | THB | Citi | Expects intervention to anchor USD/THB after the profit-take |
| 2 | BoT on hold; THB flat, rates backed up | Rates, THB | StanC (carried), Nomura | THOR +4-6bp (Asian close); no domestic catalyst in-window |

**B · The "why"** Thailand is quiet in-window, trading off FX-positioning and the BoT's on-hold stance. **Citi (18064)** took profit on its long USD/THB (2m EKO) exposure (+82bp, carried from the prior window) and expects FX intervention to anchor the pair — while rolling over its bearish PHP structure. **THB was ~flat (+0.14% DoD)**; **THOR backed up (2y +4.3bp / 10y +5.9bp)** on the Tuesday Asian close (pre-US-CPI), the most in ASEAN alongside SG — the soft-CPI relief should temper that on 07-15. StanC (carried) keeps the BoT on hold both years. No fresh Thailand-specific macro print or house-forecast note landed in-window; CPI/policy are post-window.

**C · Consensus views** No independent Thailand-macro cluster in-window; THB sits inside Citi's EM options book and the on-hold BoT read.

**D · Differentiated / unique views** None fresh Thailand-specific in-window (Citi's USD/THB is a booked/managed position, row 11).

Trade rows: **#11** (carried). **DEPTH:** TH `econ.fact_indicator` partial. The verified anchor is the 2026-06-24 BoT hold. **Flags:** no in-window Thailand-macro flagship (traded off FX + BoT-on-hold); THOR is the pre-US-CPI Asian close.

### Malaysia — Quiet ahead of Thursday's CPI + Q2 GDP double print

*Flagships read: no dedicated Malaysia-macro flagship in-window; MYR/rates trade off the regional tape into the 17-Jul releases. (Prior-window: Barclays Sep-hike call, GS "continuity" on Johor — carried.)*

**A · Themes in play**

| Rank | Theme | Assets | Banks talking | Why it matters to the PM |
|---|---|---|---|---|
| 1 | CPI + Q2 GDP prelim both 17-Jul | Rates, MYR | (calendar) | CPI survey 2.0%, GDP prelim fcst 5.3% — Thursday's fork |
| 2 | MYR firmer on soft US CPI (+0.25%) | MYR | (market) | Rates nudged up (KLIBOR +2-3bp, Asian close) |

**B · The "why"** Malaysia is genuinely quiet in-window, ahead of a Thursday double print. **CPI (17-Jul, survey 2.0% yoy) and advance Q2 GDP (17-Jul, forecast 5.3%, prior 5.4%)** are the fork; no dedicated Malaysia-macro flagship landed on 07-14/07-15. **MYR firmed +0.25% DoD** on the soft US CPI; KLIBOR nudged up (2y +2.3bp / 10y +2.5bp, the Asian close). The carried house frame — Barclays keeping a September +25bp to 3.00% vs GS "continuity" on the Johor politics — awaits Thursday's growth/inflation data to advance. The one thing to watch: whether the Q2 GDP prelim confirms above-5% growth that would keep the Barclays Sep-hike case alive.

**C · Consensus views** No independent Malaysia-macro cluster in-window; the read waits on the 17-Jul CPI + GDP.

**D · Differentiated / unique views** None fresh Malaysia-specific in-window (carried: Barclays Sep-hike vs GS continuity).

Trade rows: none direct. **DEPTH:** MY `econ.fact_indicator` partial. The verified anchor is the 2026-07-09 BNM hold at 2.75%. **Flags:** CPI + Q2 GDP prelim 17-Jul forward; no in-window Malaysia flagship.

### Philippines — Quiet; peso firmer, PHIREF backed up, UBS flags local equity conviction

*Flagships read: UBS "Philippine Equity Strategy: Word on the Street — local conviction" (18233); Citi rolled bearish PHP 1x1.5 call ratio 3m (18064); Nomura SDR FX Analysis — Asia (18370). No dedicated Philippines-rates/FX-macro flagship in-window.*

**A · Themes in play**

| Rank | Theme | Assets | Banks talking | Why it matters to the PM |
|---|---|---|---|---|
| 1 | PHIREF front backed up (Asian close) | Rates | (market) | 2y +11.5bp on the pre-CPI tape; soft-CPI relief lands 07-15 |
| 2 | Citi's rolled bearish PHP structure | PHP | Citi | Caps expected PHP strength; rolled 3m |
| 3 | UBS: local equity conviction | Equities | UBS | Domestic-investor positioning read |

**B · The "why"** The Philippines is quiet in-window on the macro side, trading off FX-positioning and the front-end. **PHP firmed modestly (+0.10% DoD)** on the soft US CPI; **PHIREF backed up sharply (2y +11.5bp / 10y +3.7bp)** — but that is the Tuesday Asian close (pre-US-CPI), so the soft-CPI relief should ease it on 07-15. **Citi (18064)** rolled its bearish PHP 1x1.5 call ratio 3m (carried), capping expected peso strength. **UBS (18233)** flags local-investor conviction in the equity market ("word on the street"). No fresh Philippines-rates or CPI print landed in-window; StanC's carried frame (5.00% August, 2Y-3Y RPGB carry) awaits the next data. The one thing to watch: the impeachment-trial backdrop and any BSP guidance ahead of the August meeting.

**C · Consensus views** No independent Philippines-macro cluster in-window; the read sits inside Citi's EM options book and UBS's equity-positioning note.

**D · Differentiated / unique views** None fresh Philippines-macro in-window (carried: Citi bearish-PHP roll; StanC 5.00% Aug + RPGB carry).

Trade rows: **#11** (Citi PHP roll, carried) + Nomura long INR vs PHP (row 7 / row 10). **DEPTH:** PH `econ.fact_indicator` deep (loaded). The verified anchor is the 2026-06-18 BSP +25bp hike. **Flags:** no in-window Philippines flagship; PHIREF is the pre-US-CPI Asian close; StanC 5.00% Aug carried.

### India — CPI (4.38%) and WPI (9.87%) both run hot into a widening trade deficit; INR the sole universe FX lower

*Flagships read: JPM "India Trade: June deficit widened on higher imports" (18260); Nomura "Asia Insights — India: Both inflation and the trade deficit..." (18160); MS "June WPI at an All-time High" (18152) + "June Trade: Tech Leads, the Rest Catch Up" (18153) + "Monsoon Update" (18105); Barclays "India: June WPI and PPI inflation: relentless rise" (18171); SocGen "Short EUR/INR: take profit as headwinds rise" (18227); GS India F&O Positioning (18094); carried Citi long-INR-basket (17693), UBS INR-payer hedge (17959).*

**A · Themes in play**

| Rank | Theme | Assets | Banks talking | Why it matters to the PM |
|---|---|---|---|---|
| 1 | CPI 4.38% + WPI 9.87% both hot | Rates, INR | MS, Barclays, Nomura, JPM | 18-month-high CPI; all-time-high WPI; headline hot, core the swing |
| 2 | Trade deficit widens to $30.4bn on oil | INR | JPM, MS, Nomura | Above consensus; oil imports the driver; BoP pressure |
| 3 | INR the sole universe FX lower (−0.45%) | INR | (market), SocGen | Hot prints + oil + deficit; SocGen books short EUR/INR |
| 4 | RBI seen looking through benign core | Rates | (carried Citi/JPM/Barclays) | No 2026 hike unless core sustains higher |

**B · The "why"** India ran hot on both inflation gauges into a wider trade deficit — the one place the soft-US-CPI dollar move did not help the local currency. On prices: **June CPI printed 4.38%** (`cb_events` 59043; survey 4.3%, prior 3.93%, an 18-month high, MoM 1.03%), and **June WPI printed 9.87%** (60884; survey 9.15%, prior 9.68%) with **food +6.14%, fuel +27.41%, manufacturing +7.48%** — Barclays (18171) calls it a "relentless rise," MS (18152) "an all-time high." On trade: **the June deficit widened to $30.4bn** (JPM 18260; JPM had $25.6bn, consensus $26.5bn, from $28.2bn in May), driven by higher oil imports — net oil imports broadly unchanged at $14.5bn as the recent oil-price softening hasn't yet fed through on timing; JPM expects oil imports to ease but by less than prices suggest (inventory rebuilding). MS (18153): "tech leads, the rest catch up." Nomura (18160): "both inflation and the trade deficit" moved the wrong way. The market read: **INR weakened −0.45% DoD** (the only universe currency lower), and **MIBOR backed up hardest in the universe (2y +14bp / 10y +15bp)** — the Tuesday Asian close, carrying the hot-prints + oil tone. **SocGen (18227)** took profit on its short EUR/INR "as headwinds rise." The carried house frame is a look-through: Citi/JPM/Barclays see the RBI holding through 2026 (no hike unless core sustains above ~4.5%), against UBS's carried INR-payer hedge on H2 food risk. Nifty 50 fell −0.66% on the hot prints + oil.

**C · Consensus views**

| Theme | Banks | Shared claim | Evidence cited | What consensus is missing |
|---|---|---|---|---|
| Headline inflation hot (CPI + WPI) | MS, Barclays, Nomura, JPM | CPI 4.38%, WPI 9.87% both above expectations | Food 6.14%, fuel 27.41%, mfg 7.48% | Whether core stays benign enough for the RBI to look through |
| Trade deficit widened on oil; BoP pressure | JPM, MS, Nomura | $30.4bn deficit, oil the driver | Net oil imports $14.5bn; deficit vs $26.5bn cons | How fast oil-import softening feeds through (timing/inventory) |

**D · Differentiated / unique views**

| Bank | Asset | The view | Why it's different | Hidden assumption | Falsifier |
|---|---|---|---|---|---|
| SocGen | FX | Take profit on short EUR/INR — INR headwinds are building | Reads the hot prints + oil + deficit as the moment to book the INR-long | The INR-supportive window is closing near-term | INR resumes strengthening (FCNR inflows land / oil drops) |
| UBS (carried) | Rates | Hold INR-swap payers as an H2-food hedge (CPI to 6.5-7.0%) | Trades the food/weather upside vs the look-through consensus | El-Niño/food risk materialises; CPI re-accelerates | RBI looks through; benign core (~2.5%) holds; food base stays low |
| Citi/JPM/Barclays (carried) | Rates | RBI looks through — no 2026 hike unless core sustains >4.5% | The look-through camp against the hot headline | Core stays benign; food is transitory/base-driven | Core-core sustains above 4.5% / oil pass-through broadens |

Trade rows: **#6** (SocGen short EUR/INR TP) + Nomura long EUR/INR (113) and pay Sep 5y India NDOIS (6.45%) (row 7) + carried Citi long-INR-basket / UBS INR-payer. **Note:** the Nomura long-EUR/INR (18221) and SocGen short-EUR/INR (18227) sit on opposite sides — SocGen books its short as INR headwinds rise, Nomura holds a long targeting 113; both shown, unreconciled. **DEPTH:** India `econ.fact_indicator` deep (~1,242+ indicators; fresh-food MoM nowcaster live). CPI + WPI + trade all FACT in `cb_events`. The verified anchor is the 2026-06-05 RBI hold at 5.25%. **Flags:** the Indonesia-instrument question does not apply here; INR rates are MIBOR OIS (`fact_bond_yield` EMPTY); NDOIS levels are sell-side. RBI August the next decision.

---

## 10. Grounding ledger  *(SYN)*

**Sources by layer**

- **`calendar.cb_events` (FACT — printed / decisions).** Verified against real rows for the 07-13→07-17 window. **Printed this window:** US June CPI (core m/m 0.0% / y/y 2.6%, headline −0.4% / 3.5%, index 333.95 — confirmed across the TE lane 60904-60908 and the BQL lane 41360/41362 + index 333.952/336.065); US federal budget −$120.3B (41363); China Q2 GDP 4.3% y/y / 0.9% qoq + IP 5.3% + retail +1.0% + FAI −5.7% ytd + capacity 73% + unemployment 5.0% (60929-60935); SG advance Q2 GDP 5.7% y/y / 1.1% qoq (60857/60856, 1Q revised ® to 6.3%); China June trade surplus $125.6B, exports +27%, imports +36% (60864-60866); India June WPI 9.87% + food/fuel/mfg (60882-60885) and June CPI 4.38% / trade −$30.43B from 07-13 (59043/59044/90517); Japan IP final 0.1% m/m / −2.1% y/y + capacity utilisation +0.1% (60870/60871/60869); Australia NAB confidence −5 (60860) + Westpac consumer +4.1% / index 83.9 (60858/60859). **Forward at compile:** BoC decision + MPR + presser (41366/60980/60981/60982, all null — the day's remaining decision); US PPI 15-Jul; US retail sales + claims 16-Jul; UK GDP 16-Jul; KR BoK 16-Jul (outside universe); MY CPI + Q2 GDP 17-Jul; HK unemployment 17-Jul; BI 22-Jul; MAS MPS 24–31 Jul window.
- **`econ.fact_indicator` (DEPTH).** Deep for US (193 active), India (~1,242+), AU, NZ, ID, PH, HK/CN, SG. Thin/partial for JP (IP final only this window), CA, UK, TH, MY. Cash govt yields NOT loaded (`rates.fact_bond_yield` EMPTY) — all 2y/10y are swap/OIS (`rates.fact_observation`, par).
- **Market layers.** `FX.fact_fx_rate` (DoD 07-13→07-14, last-tick per day); `rates.fact_observation` (2y/10y par, DoD 07-13→07-14 — 07-15 unpopulated/stale at compile); `equities.fact_index_level` (fresh to 07-14; ASX 200 stale); `equities.fact_vix` (VIX 16.5, 07-14); `commodities.fact_spot` (Gold 4,055 07-14; WTI $78.78 07-13 — the Hormuz spike now booked). Credit spreads NOT in IMDR — none cited as fact.
- **`research.fact_chunk` + Qdrant + Outlook.** ~334 in-window reports (07-14: 316; early-07-15: ~18) swept two ways — structured `dim_report` window filters across all vendors + the Outlook 13-folder taxonomy (incl. desk_commentary body-only notes: DB Fed Watcher / DBDaily, Citi The Daily Update, Nomura US Daily, SocGen) — and reconciled. Deep-read the full US CPI-reaction cluster and each country's flagship daily. **Qdrant sweeps run (multi-angle, all 07-13→07-15):** "Waller consider tightening near term hawkish Fed hike"; "June CPI soft downside surprise buys the Fed time on hold"; "Warsh testimony Fed chair stance guidance"; "soft CPI dollar reaction front-end rally July FOMC odds"; "soft CPI one-off transitory head-fake core services still firm hawkish risk PPI" (no head-fake voice surfaced — debate is pace, not direction); "Bank of Canada decision hold cut MPR Macklem"; "Canada BoC benign core excess supply USMCA"; "USD/CAD rates BoC pricing hikes"; and the earlier "China Q2 GDP outlook policy support H2 stimulus". Each reconciled with structured; distinct voices folded into the US-CPI and BoC B2 timelines (Waller/Warsh official quotes via UBS 18001/18338, GS 18324; reaction spread Citi 18239 / Nomura 18334 / MS 18365 / Barclays 18267 / SocGen 18293 / DB 18349 / GS 18251-18252; BoC JPM 17988 / MS 18051 / Nomura 18221).

**Flagship dailies that fed each country block:**
- **US** — JPM Daily Economic Briefing (18330), GS US Daily Download (18133) + Morning Wrap (18141), Citi The Global Point (18180) + Daily Update "From Waller to Warsh" (18244), DBDaily "Big miss on US CPI" (18349), Nomura US Daily Commentary (18334), MS "July 14: Softer CPI, Weaker Dollar" (18365), UBS US Daily Data Recap (18337). CPI-reaction: GS 18251, JPM 18282, Barclays 18267, SocGen 18293, MS 18265.
- **China** — GS "Trade growth accelerated" (18092), JPM 18216, Barclays 18117, UBS 18231, Nomura 18156/18161, DB 18090/18091, HSBC 18098/18359, Citi 18122.
- **Singapore** — JPM "unbowed, unbent, unbroken" (18103), Citi 18125, Nomura 18157, GS 18096.
- **New Zealand** — ANZ QSBO (18030), UBS 18107, JPM 18078, GS 18068/18070, DB 18067, Westpac 18059.
- **Canada** — Nomura "Take profit on long USD/CAD" (18221) + carried BoC previews (JPM 17988, MS 18051, GS 18040).
- **India** — JPM Trade (18260), Nomura 18160, MS 18152/18153, Barclays 18171, SocGen 18227.
- **Japan** — Citi 18123/18348, Nomura Japan Economic Weekly (18291) + Yen Rates Daily (18159), GS 18138, BNP 18063, MS 18288.
- **Australia** — GS 18072/18073, JPM 18076, UBS 18164/18110, ANZ 18342, Westpac 18084/18112.
- **UK** — HSBC 18254, JPM 18264/18077/18326, UBS 18109.
- **Indonesia** — JPM 18151. **Hong Kong** — HSBC 18359 + China tape (no dedicated HK flagship). **Thailand** — Citi 18064 + Point for AsiaPac (18347) (no dedicated TH flagship). **Malaysia** — no in-window flagship (awaits 17-Jul CPI/GDP). **Philippines** — UBS 18233 + Citi 18064 (no dedicated PH rates/FX flagship).

**Source-of-record notes (TE vs BQL):**
- **US June CPI %** — confirmed on **both lanes**: TE (core 0.0% m/m / 2.6% y/y, headline −0.4% / 3.5%; ids 60904-60907, index 60908 333.95) and BQL (CPI YoY 3.5% / Core YoY 2.6%; ids 41360/41362, CPI index NSA 333.952 / core index SA 336.065 vs 336.121). Sell-side (GS core −0.02%/2.59%, JPM core −0.02%/2.6%) corroborates.
- **China Q2 GDP + activity** — TE lane carries the actuals (60929-60935); used TE for GDP/IP/retail/FAI.
- **China June trade** — TE (60864, $125.62B) and BQL agree on strength; used TE for the headline surplus/exports/imports.

**Unreconciled (both shown):**
- **India EUR/INR** — Nomura holds **long EUR/INR (target 113)** (18221) while SocGen **took profit on short EUR/INR** "as headwinds rise" (18227) — opposite sides on the same cross; both shown.
- **US dollar direction** — Nomura reads the USD's non-reaction as long-USD-stretched (fade the dollar) (18221); Citi keeps a residual **USD-asymmetry on Middle-East risk** even after the soft CPI (18316); both shown.
- **NZ hike path** — ANZ **Sep+Oct** (18030) vs UBS **Sep+Dec** (18107); both shown.
- **UK** — HSBC's dovish fade (receive GBP 1Y1Y) vs the market's **~80% Sep-hike pricing** (18254); both shown.
- **Canada** — JPM/MS/GS benign-core **hold** vs StanC **cut-by-year-end** vs the market's **hike pricing**; all shown.

**Day-over-day vs the prior edition (07-14 → 07-15):** the prior day's marquee question — the hawkish Waller setup and the ~50% July-hike odds — resolved **dovish**: June core CPI at 0.0% m/m / 2.6% y/y undershot the entire desk, and the houses moved to "the Fed can hold for the summer." The oil/Hormuz tail persists (WTI booked at $78.78). SG advance GDP came in **strong** (5.7%); China trade **record**; China Q2 GDP **mixed** (headline 4.3% miss, June IP/retail beat); India CPI/WPI **hot**. The **BoC decision** is the sole remaining live event into the US afternoon.

**Not loaded / pre-decision (flagged):** BoC decision + MPR + presser (the day's remaining forward event); US PPI/retail (forward); JP/CA/UK/TH/MY macro depth thin in `econ.fact_indicator`; `rates.fact_bond_yield` EMPTY (no cash govt yields — all swap/OIS); credit spreads not in IMDR (none cited as fact); DXY not loaded (Citi 18316 sell-side); Brent (~$83-84) sell-side (WTI booked); the 07-15 Asian rates/FX session unpopulated at compile (DoD uses the last complete 07-14 session), so the China-GDP market reaction is still developing; **no BBG chat transcript exists for 2026-07-15** (noted).

**Differentiated-view count (§9.D):** US 3 · Canada 2 · UK 2 · China 3 · Japan 2 · Hong Kong 0 · Singapore 2 · Indonesia 1 · Thailand 0 · Malaysia 0 · Philippines 0 · New Zealand 2 · Australia 1 · India 3 = **23 differentiated-view rows across 13 countries** (quiet-country floor met for HK/TH/MY/PH with a real A+B read grounded in the flagship/tape).

---

## Source register — in-window report IDs by cluster

- **US / DM (c2):** 18251, 18252, 18282, 18267, 18312, 18293, 18315, 18295, 18265, 18333, 18365, 18239, 18240, 18241, 18292, 18349, 18334, 18367, 18330, 18206, 18362, 18079, 18133, 18141, 18129, 18193, 18180, 18244, 18337, 18316, 18317, 18324, 18328, 18255, 18338, 18220, 18306, 18375 (+pre-print Waller/Fed-comms 07-13, carried in-window: 18001, 18055, 18035, 17985, 18007) · **CA:** 18221, 18200 (+carried 17988, 18051, 18040, 18004, 18310) · **UK:** 18254, 18264, 18077, 18326, 18109.
- **North Asia (c1):** **CN** 18092, 18093, 18216, 18117, 18231, 18156, 18161, 18090, 18091, 18098, 18359, 18115, 18085, 18122, 18242, 18371, 18366, 18082 · **JP** 18123, 18348, 18319, 18291, 18159, 18158, 18222, 18368, 18138, 18357, 18351, 18106, 18288, 18063, 18062, 18296, 18289, 18290 · **HK** 18359, 18139, 18347, 18366.
- **ANZ (c3):** **NZ** 18030, 18061, 18340, 18107, 18165, 18078, 18068, 18070, 18067, 18059, 18083 · **AU** 18072, 18073, 18076, 18164, 18110, 18084, 18112, 18167, 18342, 18029, 18341, 18060, 18080.
- **ASEAN (c4):** **SG** 18103, 18125, 18157, 18096, 18226 · **ID** 18151 · **TH** 18064, 18163, 18370 · **MY** (none in-window) · **PH** 18233 (+carried 18064).
- **India (c5):** 18260, 18160, 18152, 18153, 18105, 18171, 18227, 18094, 18095 (+carried 17693, 17959).
- **Cross-asset / trades / context:** Nomura FX Themes (18081), SDR FX G10/Asia (18369/18370), Global Economic Outlook Monthly (18223); Citi Local Markets Scanner (18274); Barclays Inflation-Linked "Blockade reinstated" (18119), "Emerging Asia: The Fed stoics" (18118); StanC Commodity Roadmap ME (18336); UBS Hormuz tracker day 136 (18298); GS "Go Short AUD/NZD" (18352), KOSPI Reset (18278); DB Korea Macro (18245), MS Korea (18154), Nomura Korea (18155), StanC Korea (18335), HSBC BoK Watch (18043/18198) — Korea context (outside universe, BoK 16-Jul).

*Note: report IDs are internal grounding references; the reader-facing digest carries the data and the read, not the ID parade.*
