---
edition: daily
date: 2026-07-14
---

# RV CAPITAL · RATES & FX DESK — DAILY MACRO PULSE
# CPI day with the door to a hike now open: Waller says the FOMC will have to consider tightening if core is hot, Trump's renewed Hormuz blockade puts oil +9%, and the first universe print — India CPI — lands hot at 4.38%

### The Fed's hawk went public hours before the number. Governor Waller told the FOMC it "will need to consider tightening monetary policy in the near term" if core CPI is hot this week; Trump reimposed the Iran/Hormuz blockade and crude jumped ~9% (WTI $77.74, Brent $83); US cash yields backed up (2y 4.28% / 10y 4.61%), the dollar firmed (DXY 101.28), gold fell −2.8% and the AI/tech complex sold off (S&P 500 −0.79%, Nasdaq 100 −1.88%, Nikkei −1.92%, Korea tech −8% WoW). Into the 08:30 ET print, July-hike odds sit near 50%. The Tuesday pre-CPI tape is a coiled consolidation — DM rates near-flat, EM-Asia FX firmer as the USD eases a touch (IDR +0.29%, KRW +0.42%, INR +0.19%, NZD +0.23%) — while India's June CPI prints 4.38% on fuel and food but with benign core, and the RBNZ's most dovish official turns hawkish on price-setting.

**Window:** flow 2026-07-13 → 2026-07-14 · Monday US-session close + Tuesday pre-CPI open · **Compiled** 14 Jul 2026 (Tuesday) · **Edition:** Daily
**Universe:** AU · NZ · JP · IN · TH · ID · MY · SG · HK · PH · US · CA · UK

> FX/rates PM lens. Number-first, low-opinion, neutral — the daily does not judge. Sell-side is treated as motivated until the numbers say otherwise. Trades are surfaced with assumption + falsifier — never rated. Every table row is explained in the prose beneath it.
>
> **Grounding legend:** FACT = printed/decision (`calendar.cb_events`, `econ.fact_indicator`) · DEPTH = component series (`econ.fact_indicator`) · VIEW = sell-side interpretation (`research.fact_chunk` + Qdrant) · PRICING = market-implied · SYN = synthesis. Where a marquee number has not yet booked to the DB, it is labelled **per flow** (sell-side) or **official release**.

---

## Hero stat band

| Number | What it is | Memory / context |
|---|---|---|
| **"consider tightening… in the near term"** | Fed Gov. Waller, NY Assoc. of Business Economics, 13-Jul (GS 18016, UBS 18001, JPM 17985, Nomura 18055) | The clearest official hike-signal of the cycle — conditional on **a hot core CPI this week**. Holding stays "a reasonable outcome" if inflation resumes falling. A surprise from a Governor whose June dot was likely on-hold-2026; JPM NLP hawk-dove 34 vs 20 trailing. The Chair, Warsh, is the dove — no forward guidance. |
| **+9% / WTI $77.74 · Brent $83** | Crude DoD, on Trump's renewed Iran/Hormuz blockade (GS 18069, DB 18034, Citi 18008) | US declared "Guardian of the Hormuz Strait" + a 20% cargo levy; Iran says the Strait is closed to non-Iranian traffic (JPM 18048). Nomura's FX model (18081) has OIL as the dominant signal for a second day. IMDR WTI stale at 72.27 (07-10); live $77.74 / $83 are sell-side. |
| **2y 4.28% / 10y 4.61%** | US cash yields, Monday close (GS 18069, DB 18034) | Backed up ~6-7bp on the Waller-hike + oil session; DXY +0.3% to 101.28. **Tuesday pre-CPI is quiet:** IMDR SOFR OIS 2y +0.6bp / 10y −0.4bp DoD. ~10-11bp priced into the 29-Jul FOMC; July-hike odds near 50% (MS 18053, Citi 18007). |
| **4.38% (prov.)** | India June CPI headline — PRINTED (MOSPI official 17895), 18-month high | Above May's 3.93% (`fact_indicator`) and above the 4.2% the desks carried. Food CFPI **5.32%**, transport +7.5% — **but core benign** (headline-ex-food/fuel 3.9-4.2%, core-core ~2.5%). RBI seen looking through, on hold 2026 (Citi/JPM/Barclays); UBS holds INR payers on the H2 food risk. |
| **−1.88% / −1.92%** | Nasdaq 100 / Nikkei 225 DoD (07-13 close, `fact_index_level`) | AI/tech-led sell-off (S&P 500 −0.79% @ 7,515, Russell −0.83%, TOPIX −0.71%, HSTECH −0.96%, Korea tech −8% WoW) on higher yields + oil + memory-name positioning. Asia-ex-Japan value held (HSI +0.16%, Nifty flat, SIMSCI +0.10%). Bank earnings (BAC/C/GS/JPM/WFC) begin tomorrow. |
| **VIX 17.16 / gold −2.8%** | VIX DoD +2.1 (from 15.03, `fact_vix`); gold 4,005 (from 4,121, `fact_spot`) | Risk premium rebuilt: VIX9D +4.0, VXN +2.4, VVIX 87→95; gold and silver (−2.3%) sold with the higher-real-yield/stronger-USD move. Fresh to 07-13. |
| **~2% qoq saar** | China Q2 GDP (UBS 17686), prints 15-Jul | Weakest sequential quarter since 2022 (from ~6% Q1); ~4.5-4.7% y/y. UBS: targeted, incremental support pre-Politburo; StanC (18082): H2 infrastructure re-acceleration; GS: no rate/RRR cut 2026. Constructive RMB on internationalisation (DB 17696). |
| **5.7% y/y / hold 2.25%** | SG advance Q2 GDP (14-Jul, printed) · BoC (15-Jul) | SG Q2 GDP printed **5.7% y/y / 1.1% qoq** — above the 5.5% consensus, above trend a third year; the MAS decision is late-July (31-Jul), a live 3-way (ANZ +50bp slope vs BNP receive-SORA vs GS hold, 17773). BoC seen on hold — benign core, USMCA drag (JPM 17988, MS 18051, GS 18040). |

```spiderchart
{"type":"bar","title":"FX vs USD — day-over-day % (07-13 → 07-14, pre-CPI)","caption":"Grounded: FX.fact_fx_rate SPOT last-tick per day. Positive = local currency stronger. EM-Asia firmer as the USD eases into CPI; AUD/SGD/CNH lag. NZD/IDR/INR/KRW lead.","series":[{"name":"DoD %","color":"#2b5a86","points":[["IDR",0.29],["NZD",0.23],["INR",0.19],["MYR",0.09],["CAD",0.04],["PHP",0.04],["JPY",0.02],["GBP",0.02],["HKD",0.02],["THB",0.00],["SGD",-0.02],["CNH",-0.03],["AUD",-0.03]]}]}
```

```spiderchart
{"type":"bar","title":"Policy-rate divergence across the universe (%, current)","caption":"Grounded: calendar.cb_events verified decision rows. EM Asia (ID/IN/PH) sits high; Japan and Thailand at 1.00%. Excludes HK (peg), SG (S$NEER band), CN (LPR/OMO). Waller has just made a US hike a July-live question.","series":[{"name":"Policy rate %","color":"#1f6b4f","points":[["ID",5.75],["IN",5.25],["PH",4.75],["AU",4.35],["US",3.75],["UK",3.75],["MY",2.75],["NZ",2.50],["CA",2.25],["JP",1.00],["TH",1.00]]}]}
```

---

## The day in brief

The set-up hardened hawkish on the Monday US session, hours before the number that decides it. **Fed Governor Waller** (GS 18016, UBS 18001, JPM 17985, Nomura 18055), speaking at the NY Association for Business Economics, said "the FOMC will need to consider tightening monetary policy in the near term" **if "we get another hot reading on core inflation this week"** — balanced against a "still credible case for inflation to begin to fall… with policy at its current setting," but JPM's **Daily Economic Briefing (18048)** calls the urgency ("inflation and monetary policy are at a crossroads") a surprise from a Governor whose June dot was likely on-hold-2026, and GS reads it with the June minutes as a Committee increasingly open to hikes. At the same time **President Trump reimposed the Iran/Hormuz blockade** — the US now the self-declared "Guardian of the Hormuz Strait" with a 20% cargo levy, Iran declaring the Strait closed to non-Iranian traffic (JPM 18048) — and **crude jumped ~9%** (WTI $77.74, Brent $83, GS 18069 / DB 18034). The tape ran textbook-hawkish: US cash 2y +7bp to 4.28%, 10y +6bp to 4.61% (GS 18069); DXY +0.3% to 101.28; gold −2.8%; and an AI/tech-led equity sell-off (S&P 500 −0.79% @ 7,515, Nasdaq 100 −1.88%, Nikkei −1.92%, Korea tech −8% WoW, Momentum pair −6%) as memory-name positioning unwound. July-FOMC hike odds sit near 50% (MS 18053), with ~10-11bp priced into the 29-Jul meeting (Citi 18007).

Tuesday's pre-CPI tape is a coiled consolidation, leaning slightly the other way. DM rates are near-flat (IMDR SOFR OIS 2y +0.6bp / 10y −0.4bp; the biggest DM mover is EUR ESTR, 2y +6.9bp on an oil-driven, "too hot to hike" ECB read), and the dollar has eased against high-beta EM Asia — IDR +0.29%, KRW +0.42%, INR +0.19%, MYR +0.09%, NZD +0.23% firmer, while AUD (−0.03%), SGD (−0.02%) and CNH (−0.03%) lag flat-to-soft. The first universe marquee has already resolved, and it resolved hot: **India's June CPI prints 4.38%** (MOSPI official 17895, an 18-month high; `fact_indicator` holds the series through May at 3.93%) on fuel pass-through and food, but with benign core internals, so the houses read the RBI as looking through. In New Zealand, the RBNZ's most dovish official (Chief Economist Conway) turned openly hawkish on price-setting behaviour, and the Q2 QSBO showed acute pricing. The whole book now waits on the 08:30 ET US CPI print and Warsh's 10am House testimony — the intra-Fed split (hawk Waller, a Governor floating a hike, versus dove Warsh, the Chair refusing guidance) is exactly what the tape is trading around.

---

## Deltas *(SYN — lead with what changed)*

The Monday US-session repricing and the fresh 07-13/07-14 flow drive today's read (~408 reports swept, deep-read and unioned with structured `dim_report` window filters, the Outlook 13-folder taxonomy, and targeted per-catalyst Qdrant sweeps). **US CPI is pre-print** at compile (null actual in `cb_events`, forward/VIEW); the **MAS MPS is a late-July decision (31-Jul)**, not today. **SG advance Q2 GDP printed strong — 5.7% y/y / 1.1% qoq** (`cb_events` actual booked, above the 5.5% consensus). **India June CPI prints 4.38%** (official MOSPI 17895); the BQL/TE `cb_events` lane and `econ.fact_indicator` (loaded through May) do not yet hold June, so the number is grounded to the official release. There is **no BBG chat transcript for 2026-07-14** (none exists for the date) — noted, not blocking.

1. **Fed's Waller opens the door to a near-term HIKE (GS 18016, UBS 18001, JPM 17985/18048, Nomura 18055).** "The FOMC will need to consider tightening monetary policy in the near term" **if core CPI is hot this week**; holding stays "reasonable" if inflation resumes falling. His most hawkish speech in months, and — per JPM — a surprise from a Governor whose June dot was on-hold-2026. ~10-11bp priced into the 29-Jul FOMC; July-hike odds near 50% (MS 18053, Citi 18007). The hike is now a *July*-live question. (VIEW — 18016/18001/17985/18048)
2. **Trump reimposes the Iran/Hormuz blockade — crude +9% (Citi 18008, DB 18034, GS 18069).** US "Guardian of the Hormuz Strait" + a 20% cargo levy; Iran says the Strait is closed to non-Iranian traffic. WTI $77.74 / Brent $83 (from ~$70 a week ago). Citi flags materially higher escalation risk, base case still MoU-2 within 1-2 weeks. Nomura's FX model (18081) keeps OIL dominant; UBS Hormuz tracker (17960) at days 133-135. IMDR WTI stale at 72.27 (07-10). (VIEW/PRICING — 18008/18034/18069/18081)
3. **The Monday US session backed up cash yields, firmed the USD, sold tech + gold (GS 18069, DB 18034, MS 18053).** US 2y 4.28% / 10y 4.61%; DXY 101.28 (+0.3%); S&P −0.79% @ 7,515, Nasdaq −1.88%; gold −2.8%; VIX +2.1 to 17.16 (`fact_vix`). **Tuesday pre-CPI is a quiet consolidation** — DM rates near-flat, EM-Asia FX firmer (IDR +0.29%, KRW +0.42%, INR +0.19%, NZD +0.23%). (PRICING — sell-side closes + IMDR equities/VIX/gold to 07-13, FX/rates to 07-14)
4. **India June CPI prints hot at 4.38%, but internals benign (MOSPI 17895 + full house cluster).** 18-month high, up from 3.93% (`fact_indicator`), above the 4.2% cluster and 4.3% survey. Food CFPI 5.32%, transport +7.5%; core ~3.9%, core-core ~2.5% (JPM 18021, Barclays 17899). Citi (17966): RBI likely to cut its Aug forecast ~20bp, no 2026 hike unless core sustains >4.5%. UBS (17959) holds INR payers on the H2 food risk. **HSBC's bullish-INR trade (sell USD/INR) stops out on the oil spike (18074).** (FACT print + VIEW — 17895/17966/18021/17899/17959/18074)
5. **RBNZ Chief Economist Conway (its most dovish member) turns hawkish; QSBO shows acute pricing (GS 18068, JPM 18078, ANZ 18030, Westpac 18059).** Conway: "when above-target inflation changes expectations and price-setting behaviour, monetary policy may need to respond more firmly." GS reads it "clearly hawkish," keeps a Sep +25bp; ANZ (18030) now sees +25bp in both September and October on the QSBO selling-price jump (22→41). (VIEW + survey print — 18068/18078/18030/18059)
6. **GPIF FY25 results confirm a real rebalancing into JGBs (Barclays 18062); Katayama's repatriation comments cap the long end (SocGen 17813, DB 17731).** GPIF total assets up, rebalancing from domestic/foreign equities to JGBs (super-long impacts up). Katayama's Friday comments rallied 10-20y JGBs 12-13bp; SocGen closes its systematic short 30y; BNP opens a long 10s20s box (18063). TONAR 10y −0.9bp DoD (richer). (VIEW — 18062/17813/17731/18063)
7. **Australia data prints: NAB conditions steady, price pressures easing; consumer confidence up (GS 18073/18072, JPM 18076, Westpac 18084).** NAB June business conditions steady at +3, confidence +9pt to −5, price gauges eased — but the survey (23-Jun to 1-Jul) pre-dates the oil re-spike to ~$84. (Survey print + VIEW — 18073/18076/18084)
8. **SG advance Q2 GDP prints strong (5.7% y/y); new BNP SG trade into the late-July MAS (17773).** GDP 5.7% y/y / 1.1% qoq, above the 5.5% consensus (`cb_events`). BNP receives M27 1y SORA at 1.77% vs pays Dec/Mar FOMC spread at 9bp (entry 159bp, target 119, stop 179) — MAS "will not be in a hurry to tighten." The tighten-vs-hold-vs-receive three-way (ANZ +50bp slope vs BNP receive-SORA vs GS hold) runs into the 31-Jul MPS, not today. (FACT print + VIEW — 17773)
9. **Citi books the long-USD/THB profit (+82bp) and rolls the bearish PHP structure (17728/18064).** Long USD/THB 2m EKO exited +82bp as THB underperformed and 33 was "taken out." PHP 1x1.5 call ratio exited at a −10.5bp loss and rolled 3m (13-Oct). EM bond book: u/w THB (−0.9%) vs o/w MYR/IDR/INR (+0.3% each). (VIEW — 17728/18064)
10. **China: fiscal re-acceleration signalled for H2 (StanC 18082); GDP tomorrow the tell.** StanC: Q2 fiscal implementation slowed (broad spending −5.7% y/y Apr-May, LGSB issuance slowed) — a deliberate fine-tune; expects H2 infrastructure re-acceleration. Sits with UBS's "targeted, incremental support" and GS's "no rate/RRR cut 2026." (VIEW — 18082/17686)

---

## 4. Cross-asset moves matrix (DoD)

Day-over-day = **(07-14 last-tick) − (07-13 last-tick)**, last tick = max `ts` within the calendar day, for **FX (spot, `FX.fact_fx_rate`)** and **2y/10y swap/OIS par (`rates.fact_observation`, quote='par')**. 07-14 is the **current, pre-CPI session** (partial/intraday for some Asian curves). Every sign sanity-checked against the two closes. **Equities are fresh to 07-13** (`equities.fact_index_level` stops 07-13 — the Monday risk-off session, one behind the Tuesday FX/rates). FX % is **local vs USD** (positive = local stronger). `fact_bond_yield` is EMPTY — no cash govt yields loaded; rates are swap/OIS. "n/l" = not loaded / no fresh 07-14 tick.

| Country | FX vs USD (DoD %) | 2y (DoD bp) | 10y (DoD bp) | Equity (07-13 Monday) | One-line read |
|---|---|---|---|---|---|
| United States | EUR **+0.02%** | SOFR **+0.6** | SOFR **−0.4** | S&P 500 −0.79% / Nasdaq 100 −1.88% | Tuesday quiet; the move was Monday (cash 2y +7 / 10y +6) on Waller-hike + oil +9%. Tech sold off; VIX +2.1. CPI 08:30 ET the fork. |
| India | INR **+0.19%** | MIBOR **0.0** | MIBOR **0.0** | Nifty +0.02% (flat) | CPI prints 4.38% (hot headline, benign core); INR firmer as USD eases; curve flat. Citi long-INR vs UBS INR-payer vs HSBC stopped out. |
| Singapore | SGD **−0.02%** | SORA **0.0** | SORA **0.0** | SIMSCI +0.10% | **Advance Q2 GDP printed strong (5.7% y/y).** MAS MPS is 31-Jul (late-July); the ANZ +50bp-slope vs BNP receive-SORA vs GS hold three-way runs into it; SGD/rates ~flat. |
| New Zealand | NZD **+0.23%** | NZIONA **0.0** | NZIONA **0.0** | n/l | Kiwi firmest in the universe; QSBO acute pricing + Conway hawkish; ANZ now Sep+Oct hikes; Q2 CPI 21-Jul the fork. |
| Japan | JPY **+0.02%** | TONAR **0.0** | TONAR **−0.9** | Nikkei −1.92% / TOPIX −0.71% | JGB long-end richer on Katayama + GPIF FY25 rebalancing into JGBs; SocGen closed short 30y; JPY ~flat; memory-led equity sell-off. |
| China / Hong Kong | CNH **−0.03%** / HKD **+0.02%** | HIBOR **+0.4** | HIBOR **+0.1** | HSI +0.16% / HSCE +0.33% / HSTECH −0.96% | CNH ~flat (internationalisation bid); Q2 GDP 15-Jul (~2% qoq saar); StanC sees H2 infra re-accel; HKD firm on peg. |
| Canada | CAD **+0.04%** | CORRA **+0.6** | CORRA n/l | n/l | CAD firmer; front nudged up into **15-Jul BoC**; JPM/MS/GS benign-core hold vs StanC cut vs mkt +54bp to Jul-27; MS says 1.42 "too rich." |
| Indonesia | IDR **+0.29%** | JIBOR n/l | JIBOR n/l | n/l | Biggest FX gainer; USD give-back into EM Asia; Citi o/w IDR in the EM book; BI decides 22-Jul. |
| Euro area | EUR **+0.02%** | ESTR **+6.9** | ESTR **+3.3** | Euro Stoxx 50 +0.02% / CAC +0.31% | **Biggest DM rates mover:** ESTR backed up on the oil spike + HSBC's "too hot to hike" ECB read (17709); EUR ~flat. Context row for the US book. |
| Australia | AUD **−0.03%** | AONIA **+0.6** | AONIA **−0.3** | ASX 200 +0.03% (flat) | AUD flat-to-soft; NAB conditions steady + price pressures easing (pre oil-spike); front nudged up, belly richer; Q2 CPI 29-Jul. |
| Malaysia | MYR **+0.09%** | KLIBOR **0.0** | KLIBOR **0.0** | n/l | MYR firmer; rates flat; Johor (BN 48/56) — GS "continuity" vs Barclays "Anwar losing ground"; Barclays keeps Sep +25bp to 3.00%. |
| Philippines | PHP **+0.04%** | PHIREF **+0.2** | PHIREF **0.0** | n/l | Peso firmer; front barely moved; Citi rolled its bearish PHP 1x1.5 call ratio 3m; StanC 5.00% Aug + 2Y-3Y RPGB carry. |
| Thailand | THB **~flat** | THOR **+3.2** | THOR **+4.4** | SET −0.002% (flat) | THB flat; rates backed up most in EM Asia; **Citi booked long USD/THB +82bp**, expects intervention to anchor; BoT on hold. |
| United Kingdom | GBP **+0.02%** | SONIA **+0.2** | SONIA **−0.1** | FTSE n/l (07-13) | GBP ~flat, SONIA flat; Bailey speaks 14-Jul; GDP 16-Jul; Burnham to become PM 20-Jul; mkt still prices BoE hikes. |

*Oil/vol footnote:* IMDR WTI unrefreshed at **72.27** (`commodities.fact_spot`, 07-10) — the live level is **WTI $77.74 (+8.86%, GS 18069) / Brent $83.04 (+9.2%, DB 18034)**, sell-side, on Trump's renewed Iran/Hormuz blockade. Gold **4,005** (07-13, −2.8% DoD, `fact_spot`); silver 58.16 (−2.3%). **Nomura's FX-theme model (18081) keeps OIL the dominant short- and long-term signal** ("FX suffers from higher oil" −0.8% over 5d). **VIX** 17.16 (07-13, +2.1 DoD, `fact_vix`); VXN 27.3, VVIX 95.28, VIX9D 15.13. **DXY** not loaded (agent proxy via crosses; sell-side 101.28, +0.3% Monday). **Equity flag:** `equities.fact_index_level` fresh to **07-13** — one behind the Tuesday FX/rates. `fact_bond_yield` EMPTY — US cash 2y 4.28% / 10y 4.61% are sell-side (GS/DB). **KOSPI 200 shows −9.85% one-day (a rebasing/roll artifact; GS 18069 reports KOSPI −8% WoW) — excluded.** **Rows ordered by event proximity + move magnitude.**

---

## 5. CB / macro dashboard  *(FACT — `calendar.cb_events`)*

One row per covered country. Policy rate = last decided rate on a verified decision row; last move and next event verified against `cb_events`. No universe CB decides in-window; the forward decisions (BoC 15-Jul, MAS MPS 31-Jul; BoK 16-Jul outside the universe) are ahead. SG advance Q2 GDP has booked (5.7% y/y actual, `cb_events`); US CPI remains null (pre-print); India June CPI confirmed via official MOSPI, not yet in the BQL lane or `fact_indicator`.

| Country | Policy rate | Last move (verified) | Next scheduled | Bias / key issue |
|---|---|---|---|---|
| United States | **3.75%** (3.5-3.75 range) | Held 2026-06-17 (dots up: 1st-yr 3.6% from 3.1%) | **CPI + Warsh House testimony 14-Jul (today)**; PPI 15-Jul; FOMC 29-Jul | Waller floats a near-term HIKE if core hot; ~10-11bp into 29-Jul, July-odds ~50%; cooling camp GS 0.17%/2.76% vs BNP 0.37%; Chair Warsh dovish |
| India | **5.25%** | Held 2026-06-05 | RBI August; WPI 14-Jul | **CPI PRINTS 4.38% (hot headline, benign core)**; Citi/JPM/Barclays: RBI looks through, no 2026 hike; UBS holds INR payers on H2 food risk (to 6.5-7.0%) |
| Singapore | MAS S\$NEER band | — (band) | **MAS MPS 31-Jul** (advance Q2 GDP printed 14-Jul: 5.7% y/y) | GDP 5.7% y/y / 1.1% qoq (above 5.5% cons); ANZ +50bp slope vs BNP receive-SORA (won't tighten) vs GS hold-with-tilt into the 31-Jul MPS |
| New Zealand | **2.50%** | Hiked +25bp 2026-07-08 | Q2 CPI 21-Jul; 2-Sep MPS | **QSBO: acute pricing (selling price 22→41); Conway (dove) turns hawkish**; ANZ now Sep+Oct hikes; GS Sep +25bp |
| Japan | **1.00%** | Hiked +25bp 2026-06-16 | Machinery orders/IP 14-Jul; 20y JGB auction 14-Jul | GPIF FY25 rebalances into JGBs; Katayama repatriation caps the long end (SocGen closed short 30y); TONAR 10y −0.9bp; DB medium-term yen-higher |
| China | LPR / 7d OMO | — | **Q2 GDP + activity 15-Jul**; trade 14-Jul | Q2 ~2% qoq saar (weakest since 2022, UBS); StanC H2 infra re-accel; GS no rate/RRR cut 2026; constructive RMB (internationalisation) |
| Canada | **2.25%** | Held 2026-06-10 | **BoC + MPR 15-Jul** | JPM/MS/GS benign-core hold (excess supply, USMCA drag) vs StanC cut-by-year-end vs mkt +54bp to Jul-27; MS: USD/CAD "too rich at 1.42" |
| Australia | **4.35%** | Held 2026-06-16 | Q2 CPI 29-Jul; 11-Aug | NAB conditions steady, price pressures easing (pre oil-spike); consumer sentiment up; GS wealth-effect drag (house prices −5%); mkt ~13bp hike then fade |
| Malaysia | **2.75%** | Held 2026-07-09 | (post-window) | Johor: BN 48/56; GS "continuity" vs Barclays "Anwar losing ground"; Barclays keeps Sep +25bp to 3.00% |
| Hong Kong | USD peg / LAF | — (linked to Fed) | — | HKD firm on peg; HIBOR +0.4bp; HSBC "fine line" — 7.85 a risk not base; hawkish-Fed repricing + dividend season the offsets |
| Philippines | **4.75%** | Hiked +25bp 2026-06-18 | (post-window) | PHIREF front flat; Citi rolled bearish PHP 3m; StanC 5.00% Aug + 2Y-3Y RPGB carry; impeachment trial |
| Thailand | **1.00%** | Held 2026-06-24 | (post-window) | THB flat, THOR +3-4bp; Citi booked long USD/THB (+82bp), expects intervention; StanC BoT on hold both years |
| Indonesia | **5.75%** | Hiked +25bp 2026-06-18 | BI 22-Jul (post-window) | IDR biggest FX gainer (+0.29%); Citi o/w IDR in EM book; BI pro-stability stance anchoring the rupiah |
| United Kingdom | **3.75%** | Held 2026-06-18 (7/2/0) | Bailey speech 14-Jul; GDP 16-Jul | GBP/SONIA flat; Burnham PM 20-Jul; StanC hold-2026/cuts-H1-27; mkt still prices BoE hikes |

**SYN — state of the world:** the universe is coiled around one event — the 08:30 ET June CPI — into a backdrop that has hardened hawkish. Waller, a voting Governor, has said out loud that a hot core this week would put a near-term hike on the table (July-odds ~50%), and Trump's renewed Hormuz blockade has swung oil +9% back to the up-inflation side of the tail exactly as HSBC and Nomura warned. That combination re-priced US cash yields up 6-7bp on the Monday session, firmed the dollar, and sold the AI/tech complex and gold. The Tuesday pre-print tape is quiet and slightly the other way — EM-Asia FX firmer as the dollar eases a touch — a consolidation, not a reversal. The dovish anchor is unusual: it is the *Chair* (Warsh) who keeps saying inflation has declined and refuses forward guidance, against his own hawkish Governor. Around this, the Asia clocks keep their own time: India's CPI resolved hot-but-benign (RBI looks through), New Zealand added a rare double-hawkish signal (a dove turning hawkish plus acute QSBO pricing), Korea's BoK is a well-flagged +25bp Thursday (outside the universe), and China's Q2 GDP tomorrow should confirm the weakest sequential quarter since 2022 with H2 infrastructure the intended support. Singapore is today's live domestic call — a genuine three-way into advance GDP + MAS — and Canada tomorrow is a benign-core hold the market keeps trying to price 2027 hikes against. Oil is once again the shared falsifier, but now pointing up.

---

## 6. Themes in play + open questions

**Themes (who's talking + the number), stated neutrally:**
- **Waller opens the door to a near-term hike — into the print that decides it.** GS (18016): "the FOMC will need to consider tightening… in the near term" if core is hot. JPM (18048): the urgency is a surprise from an on-hold-2026 dot; if data run hotter than the June SEP (4.3% U-rate, ~0.22% core PCE) "hikes will likely come this year." Citi (18007): recent Fedspeak made July "live" (10-11bp priced), asymmetry USD-positive. Intra-Fed tension: hawk Waller (Governor) vs dove Warsh (Chair, no guidance, HSBC 17678).
- **Oil re-escalation is back — crude +9% on Trump's blockade.** Citi (18008): US "Guardian of the Hormuz Strait" + 20% cargo levy. JPM (18048): Iran declares the Strait closed to non-Iranian traffic; Brent toward JPM's $83 2H-avg. **Nomura (18081): OIL the dominant FX signal, second day.** GS (17798): a re-escalation to $100 adds only 3-4bp to monthly core, but the "fear" effect could exceed the passthrough math.
- **June CPI: cooling camp vs stickiness, with a live July-hike overlay.** GS (17923/18014): core CPI +0.17% m/m / 2.76% y/y (OER +0.23%, airfares +1.5%, hotels +0.3%). JPM (18047): headline −0.20% / core +0.22% (2.81% y/y), keeps 1Yx1Y/2Yx3Y inflation-swap steepeners; full-year core an "uncomfortably high 3%." Consensus core 0.3% m/m / 2.9% y/y. BNP 0.37% (carried).
- **India CPI resolves hot but benign.** MOSPI (17895): headline 4.38%, food 5.32%, transport +7.5%. Citi (17966): no 2026 hike unless core >4.5%. UBS (17959): holds INR payers on H2 food (6.5-7.0%). HSBC (18074): its bullish-INR trade stops out on the oil spike.
- **New Zealand: a dove turns hawkish.** Conway (GS 18068): "monetary policy may need to respond more firmly." QSBO (ANZ 18030): selling-price gauge 22→41; ANZ now Sep + Oct hikes.
- **Japan: GPIF flow turns concrete.** Barclays (18062): GPIF FY25 rebalanced from equities into JGBs. SocGen (17813): closes short 30y. BNP (18063): long 10s20s box.
- **China: weak Q2, H2 fiscal re-acceleration, RMB bid.** UBS (17686): Q2 ~2% qoq saar → targeted support. StanC (18082): H2 infrastructure re-accelerates using the existing quota. DB (17696): 15th FYP elevates RMB internationalisation.
- **Singapore: advance Q2 GDP prints strong (5.7% y/y); the MAS three-way runs into 31-Jul.** GDP above the 5.5% consensus (`cb_events`). ANZ (16838): +50bp slope. BNP (17773): receive front SORA vs pay Fed. GS (16862): hold with mild tilt.

**Open questions into the next sessions (neutral — the disagreement + what resolves it):**
1. **14-Jul US CPI (today, 08:30 ET)** — a hot core (≥0.3%) hands Waller his near-term-hike trigger and validates the ~50% July-odds; a soft print (GS/JPM ~0.2% core) reopens the fade and dents the USD (HSBC). Warsh testifies at 10am and speaks after the print.
2. **Oil / Strait of Hormuz** — does Trump's blockade escalate to energy-infrastructure damage (Citi: base case still MoU-2 in 1-2 weeks), and how far above $83 Brent runs; Nomura's model already has oil dominant.
3. **MAS MPS (31-Jul), with a strong Q2 GDP print (5.7% y/y) already in hand** — ANZ's +50bp slope vs BNP's won't-tighten (receive SORA) vs GS's hold-with-tilt; the above-trend growth print leans toward the tightening side, decided end-July.
4. **BoC (15-Jul)** — JPM/MS/GS benign-core hold vs StanC cut-by-year-end vs the market's +54bp to Jul-27; MS says USD/CAD "too rich at 1.42."
5. **China Q2 GDP (15-Jul)** — UBS's ~2% qoq saar and whether it forces support beyond "targeted and incremental"; StanC's H2 infrastructure re-acceleration vs GS's no-cut.
6. **India rate path** — CPI hot (4.38%) but core benign; does the RBI look through (Citi/JPM/Barclays) or does the food-H2 risk force it (UBS); the oil spike is a fresh energy-CPI risk.
7. **New Zealand** — after Conway's hawkish turn + acute QSBO pricing, is it ANZ's Sep+Oct (+50bp) or GS's Sep-only; the 21-Jul Q2 CPI the arbiter.
8. **BoK (16-Jul, outside universe)** — a well-flagged +25bp to 2.75%; UBS would pay Korea short-end if the governor endorses an extended cycle.

---

## 7. Calendar — releases + CB events with rate relevance  *(FACT — `cb_events`; pure calendar, no view)*

Consensus (`survey`/`forecast`) shown where present; `actual` shown only where the row carries one. `®` = prior revised. **US CPI is pre-print (null) in the BQL/TE lane at compile; the MAS MPS is a 31-Jul release, not today.** SG advance Q2 GDP has booked (5.7% y/y / 1.1% qoq actual). India June CPI is confirmed PRINTED via the official MOSPI release (17895) at 4.38%, though the BQL/TE `cb_events` row still shows null — flagged. Australia NAB + consumer confidence and NZ QSBO printed today (per flow / proprietary surveys). Sell-side-reported values tagged "per flow."

| Date | Country | Event | Consensus | Prior | Actual |
|---|---|---|---|---|---|
| 07-13 | IN | CPI YoY | 4.3% (survey) / 4.0% (fcst) | 3.93% | **4.38% — PRINTED (MOSPI official 17895); null in BQL/TE lane** |
| 07-13 | US | Fed Waller / Bowman speeches | — | — | **Waller: FOMC "will need to consider tightening… in the near term" if core hot (per flow, 18016)** |
| 07-13 | US | Monthly budget statement | −132.8B (survey) / +21.0B (fcst) | −293B | pre-print (null) |
| **07-14** | **US** | **CPI: core m/m** | **0.3% (survey) / 0.2% (fcst)** | **0.2%** | forward — GS 0.17% / JPM 0.22% / BNP 0.37% / cons 0.3% |
| **07-14** | **US** | **CPI: headline m/m / YoY** | **−0.1% / 3.9%** | **0.5% / 4.2%** | forward — GS −0.13% / +3.87% YoY; core YoY cons 2.9% |
| **07-14** | **US** | **Fed Warsh House testimony; Barr/Cook/Bowman/Goolsbee speak** | — | — | forward (Warsh 10am; also speaks after the 08:30 CPI) |
| **07-14** | **SG** | **Advance Q2 GDP YoY / qoq (adv)** | 5.5% / 1.1% qoq | 6.0% ® / 1.3% ® | **5.7% / 1.1% — PRINTED (`cb_events`), above consensus** |
| 07-14 | JP | Industrial production m/m; machinery orders m/m/y; 20y JGB auction | −4.2% / +12.9% (orders) | +0.5% (IP) / +8.7% | forward |
| 07-14 | AU | NAB business conditions / confidence; Westpac consumer conf | — | +3 / −14 / 80.6 | **NAB conditions +3, confidence −5; consumer sentiment up (per flow, 18073/18084)** |
| 07-14 | NZ | NZIER QSBO (Q2) | — | −4 (confidence) | **printed: activity soft, acute pricing (per flow, 18030)** |
| 07-14 | CN | Balance of trade / exports / imports | $121B / 18.2% / 24% | $105.4B / 19.4% / 27.4% | forward |
| 07-14 | US | Net long-term TIC flows | $128.5B | $103.1B | forward |
| 07-14 | UK | BoE Gov Bailey speech | — | — | forward |
| **07-15** | **CA** | **Bank of Canada Rate Decision + MPR** | hold 2.25% | 2.25% | forward — JPM/MS/GS hold vs StanC cut |
| **07-15** | **CN** | **GDP YoY / qoq / retail / IP / FAI** | 4.4% / 0.9% / −0.1% / 4.7% / −4.9% | 5.0% / 1.3% / −0.6% / 4.5% / −4.1% | forward — UBS ~2% qoq saar |
| 07-15 | US | PPI final demand / core m/m; Empire mfg; Warsh (Senate); Williams/Musalem | 0.2% / 0.4% / 8.7 | 1.1% / 0.4% / 5.7 | forward |
| 07-16 | US | Retail sales m/m; Philly Fed; initial claims | 0.3% / 12 / 218K | 0.9% / 10.3 / 215K | forward |
| 07-16 | CA | Housing starts | 260K (survey) / 220K (fcst) | 261.4K | forward |
| 07-16 | UK | GDP m/m / 3m; IP m/m | 0.1% / 0.6% / 0.1% | −0.1% / 0.7% / 0% | forward |
| 07-16 | KR | BoK base rate | hike 2.5→2.75% | 2.5% | forward (outside universe; UBS/HSBC/StanC +25bp) |
| 07-20 | UK | (political) Andy Burnham to become PM | — | — | forward (GS/StanC) |
| 07-21 | NZ | Q2 CPI | ~1.3% q/q (RBNZ) / 1.5% (ANZ) | — | forward |
| 07-22 | ID | Bank Indonesia decision | — | 5.75% | forward |
| 07-29 | US/AU | FOMC 29-Jul; AU Q2 CPI 29-Jul | hold / ~0.8% q/q (JPM) | 3.75% (upper) | forward — Waller floated a July hike |
| **07-31** | **SG** | **MAS Monetary Policy Statement** | — | — | forward — ANZ +50bp slope vs BNP receive-SORA vs GS hold-with-tilt |

---

## 8. Cross-cutting trade-ideas table  *(VIEW — provenance-tagged, never rated)*

The daily's single trade view — what the houses are floating across the universe. Each row: the idea, the assumption it rests on, its falsifier, provenance. **Never rated** — the PM judges. Expanded in the per-country reads below.

| # | Trade | Key driver / rationale | Assumption it rests on | Falsifier | Provenance |
|---|---|---|---|---|---|
| 1 | **Long USD (asymmetry USD-positive into the print) / long USD/JPY carry** | Waller floats a July hike; oil +9% reconnects the USD-oil link; "yield drives FX" | Hot-or-firm CPI keeps US yields bid; carry prevails | A "surprisingly soft" CPI dents the USD (HSBC); concrete GPIF repatriation lifts JPY | Citi 18007, GS 18016/17620, DB 18034, HSBC 17678 |
| 2 | **JPM 1Yx1Y / 2Yx3Y US inflation-swap steepeners into the print** | Tactically bearish June CPI (headline −0.20%, core +0.22%); energy reverts positive later | CPI prints soft near-term; longer-run inflation stays supported | A hot near-term core flattens the case | JPM 18047 |
| 3 | **BNP Dec-26/Mar-27 FOMC steepeners (~9bp) — now with a live July hike** | Front "discounts too-few hikes"; Waller made July "live"; core sticky (0.37%) | Multiple pathways to price 1Q27+ hikes | Core prints ~0.2% and Waller's soft-path scenario wins | BNP 17655 |
| 4 | **BNP receive M27 1y SORA vs pay Dec/Mar FOMC spread** (entry 159bp, tgt 119, stop 179) | SORA front carry attractive; MAS "won't hurry to tighten"; ME uptick = entry | MAS holds FX policy, SORA fixings stay low | MAS tightens the slope (ANZ's call) → SORA front repriced up | BNP 17773 |
| 5 | **Citi long INR vs USD/EUR/SGD basket (40/30/30) + NDOIS 1s5s steepener** | RBI FCNR measures landing; BoP improving; INR firmed +0.19% | FCNR inflows land; oil contained; no equity outflows | Oil to $100 (blockade) / equity outflows / El-Niño growth hit | Citi 17693 |
| 6 | **UBS hold INR-swap PAYERS (hedge)** | Hot 4.38% headline; food to 6.5-7.0% H2 on El-Niño; FY27 CPI 4.8% | Weather risk materialises; CPI re-accelerates into early-2027 | RBI looks through (core benign 2.5%); food base stays benign | UBS 17959/17686 |
| 7 | **SocGen close JGB short 30y; stay rec 1y1y vs JGB futures + short 10s on 5s10s30s fly; BNP long 10s20s box** | Katayama comments + GPIF FY25 rebalancing cap the long end; belly "behind the curve" | GPIF flow/ambiguity caps the long end; slow BoJ + weak FX + firm data | A credible consolidation signal, or fast BoJ-to-2% | SocGen 17813, BNP 18063, Barclays 18062 |
| 8 | **Position the Malaysia Sep-hike vs the hold camp (Johor overlay)** | Barclays keeps Sep +25bp to 3.00%; BN landslide → more pre-election fiscal spend | Growth firm; politics doesn't force a stability-first hold | Growth cools / early-election risk turns MYR-negative | Barclays 17691 (vs GS 17670 continuity) |
| 9 | **Citi: booked long-USD/THB EKO (+82bp); rolled bearish PHP 1x1.5 call ratio 3m** | THB underperformed / 33 taken out → expect intervention to anchor; limit to PHP strength | FX intervention anchors USD/THB; PHP strength capped | ME de-escalation + sharp oil drop; strong PHP inflows | Citi 17728/18064 |
| 10 | **ANZ MAS +50bp slope steepening (out-of-consensus, 31-Jul)** | Electricity +17% adds 0.47pp core; above-trend growth 3rd year (Q2 GDP 5.7% confirms) | Soft Apr/May core was discount-driven, reverses; growth above trend | Core stays soft into the 31-Jul MPS → status-quo hold | ANZ 16838 (vs GS 16862 hold, BNP 17773 receive-SORA) |
| 11 | **HSBC sell USD/INR — STOPPED OUT (96.20) on the oil spike** | RBI FX package a tailwind, but the INR "not immune" to oil-driven pressure | The 5-Jun FX package would outweigh oil risk | Oil re-escalation (materialised) | HSBC 18074 |

**SYN — where the book tilts:** the cross-universe tilt is *long-dollar / higher-for-longer* and gained conviction on the Monday session — Waller made a July hike a live possibility and the oil blockade re-lit the inflation leg, so the USD/carry complex (rows 1, 3) and the tactically-bearish-CPI expressions (row 2) are the cleanest reads into the print, with Citi (18007) explicitly framing the asymmetry as USD-positive. EM Asia is a split book: constructive-INR-FX (Citi, row 5) against pay-INR-rates as a weather hedge (UBS, row 6) — and HSBC's bullish-INR just stopped out on the oil spike (row 11), a live demonstration of the tension. Singapore printed a strong Q2 GDP (5.7% y/y) and carries a fresh three-way into the late-July MAS (ANZ tighten row 10 / BNP receive-SORA row 4 / GS hold), and Citi has rotated its ASEAN options (row 9). Japan's trade migrated from carry to curve: with GPIF FY25 confirming a rebalancing into JGBs, SocGen closed its short 30y and BNP put on a long 10s20s box (row 7). Every row still carries oil as the shared falsifier — but the blockade has swung it to the up-inflation side, which is what makes a hot CPI so consequential today.


---

## 9. Per-country read — A / B / C / D

Ordered by what moved this window and by event proximity (the book waits on 14-Jul US CPI; India and NZ prints have resolved and SG's advance GDP has printed; the MAS decision and BoC are ahead). Every country read at the chunk level, anchored on that desk's daily-cadence flagship. Movers get depth; genuinely quiet countries get the raised-floor read (A + B minimum) grounded in their flagship daily.


### United States — Waller floats a July hike, oil spikes, and June CPI adjudicates it today

*Flagships read: GS US Daily Download (17798), GS Morning Wrap (17785), GS US Economics Weekly Update (17923), GS Weekend Macro Call (17797); JPM Daily Economic Briefing (18048), JPM US Market Intelligence Morning (17869) / Trading CPI (17933), JPM Daily Financial Markets Monitor (18079); Citi The Global Point (17845) / The Daily Update (17908) / "Asymmetry leans USD-positive" (18007); DBDaily (18034) + Fed Watcher (18035); Barclays Macro Wrap "Strait back" (17822) / Inflation-Linked Daily (17768); Nomura US Daily Commentary (18055); MS "Oil and Hawkish Fed Repricing" (18053); HSBC "The week in 60 seconds" (17678); ANZ US Pulse (17720). Event notes: Waller (GS 18016, UBS 18001, JPM 17985); CPI previews (GS 18014, JPM 18047, Citi 17902); oil (Citi 18008, GS 17700).*

**A · Themes in play**

| Rank | Theme | Assets | Banks talking | Why it matters to the PM |
|---|---|---|---|---|
| 1 | Waller opens the door to a near-term hike | Rates, USD | GS, UBS, JPM, DB, Nomura | A voting Governor made the 29-Jul meeting "live" on a hot core |
| 2 | Oil +9% on Trump's Iran blockade | Rates, USD, commodities | Citi, DB, MS, Nomura, HSBC | Reconnects the USD-oil-inflation link; revives the up-inflation tail |
| 3 | June CPI: cooling call vs stickiness | Rates, USD | GS, JPM, BNP, HSBC | Decides whether the ~50% July-hike odds stick or fade |
| 4 | If the Fed hikes, equities struggle | Equities | GS | Growth hit, AI capital-intensity, hiking marks past bull-market peaks |

**B · The "why"** The Monday US session moved hawkish, and the daily flagships were unanimous on why. **Fed Governor Waller** (GS 18016, UBS 18001, JPM 17985, Nomura US Daily 18055), at the NY Association for Business Economics, said "the FOMC will need to consider tightening monetary policy in the near term" **if "we get another hot reading on core inflation this week"** — his "near term" read by UBS as pointing at the 29-Jul meeting itself; JPM's **Daily Economic Briefing (18048)** frames it as extending Waller's "earlier pivot," a surprise from a Governor whose June dot was likely on-hold-2026, and reiterates JPM's own line — the next Fed move is a hike, not necessarily this year, but "if incoming data run hotter than the Fed's June SEP… hikes will likely come this year." Simultaneously **Trump reimposed the Iran/Hormuz blockade** (Citi Oil Monitor 18008: US "Guardian of the Hormuz Strait" + 20% cargo levy; Iran declaring the Strait closed to non-Iranian traffic per JPM 18048), and **crude jumped ~9%** (WTI $77.74, Brent $83; GS 18069 / DB DBDaily 18034). The tape: US cash 2y +7bp to 4.28%, 10y +6bp to 4.61% (GS 18069); DXY +0.3% to 101.28; gold −2.8% (`fact_spot` 4,005); S&P −0.79% @ 7,515 (`fact_index_level`), Nasdaq −1.88%, Momentum pair −6%; VIX +2.1 (`fact_vix` 17.16); ~10-11bp priced into 29-Jul, July-odds near 50% (MS 18053, Citi 18007). Into today's 08:30 ET print the desks split: **GS US Economics Weekly (17923)** forecasts core CPI **+0.17% m/m / 2.76% y/y** (OER +0.23%, rent +0.17%, airfares +1.5%, hotels +0.3%); **JPM (18047)** headline −0.20% / core +0.22% (2.81% y/y), keeping 1Yx1Y/2Yx3Y inflation-swap steepeners; consensus core 0.3% m/m / 2.9% y/y; **BNP** 0.37% (carried). GS's **US Daily Download (17798)** adds the equity read: if the Fed hikes, stocks struggle short-term (growth hit, AI capital-intensity raises cost-of-capital sensitivity, hiking has marked prior high-concentration bull-market peaks), and a re-escalation to $100 oil adds only 3-4bp to monthly core — but the *fear* of further supply shocks could matter more than the passthrough math. **Citi (18007):** the asymmetry "still leans USD-positive over upcoming data prints." **HSBC (17678):** US figures would need to be "surprisingly soft to dent the USD." The governance split the market is trading: hawk Waller (a Governor) vs **Chair Warsh**, who "commented how inflationary pressures declined in recent weeks," refuses forward guidance, and testifies to the House at 10am plus speaks after the print. Tuesday pre-print, IMDR SOFR OIS is near-flat (2y +0.6bp, 10y −0.4bp) and the dollar has eased against EM Asia.

**C · Consensus views (≥2 independent banks)**

| Theme | Banks | Shared claim | Evidence cited | What consensus is missing |
|---|---|---|---|---|
| Headline falls on energy, core the question | GS, JPM, BNP, HSBC | Headline −0.1%/−0.2%; core ~0.2-0.4% | GS core 0.17%/2.76%; JPM −0.20% headline | Split on the core level (GS/JPM ~0.2 vs BNP 0.37) and whether it triggers Waller |
| Oil is the two-sided tail — now pointing up | Citi, DB, MS, Nomura, HSBC | The blockade revives up-inflation/hike risk | Crude +9%; Nomura oil-dominant model | Timing of MoU-2 (Citi 1-2 weeks) vs a sustained shock |
| The Fed is more open to hikes than a month ago | GS, JPM, UBS | Waller + June minutes shift the balance | Waller quote; NLP 34; ~10-11bp into 29-Jul | Whether Chair Warsh (dove) overrides the hawks |

**D · Differentiated / unique views**

| Bank | Asset | The view | Why it's different | Hidden assumption | Falsifier |
|---|---|---|---|---|---|
| GS | Rates/USD/equity | Core cooling (0.17% m/m, 2.76% y/y) yet flags the FOMC increasingly open to hikes; if it hikes, stocks struggle | Holds a cooling forecast, a hawkish-risk read, and an equity-fragility call together | Airfares/hotels/rent slow as modelled; USD on yield/carry | A 0.3%+ core (validates Waller) or a soft print that dents the USD |
| JPM | Rates | Tactically bearish June CPI (−0.20% headline); keeps inflation-swap steepeners | Trades the near-term print soft while long longer-run inflation (full-year core ~3%) | Energy reverts positive later; goods firm modestly | A hot near-term core flattens the steepener |
| Citi | USD | Asymmetry leans USD-positive into the data; July FOMC "live" | Frames the risk-reward around the dollar rather than the rate path | Fedspeak keeps July live; data don't undershoot sharply | A soft CPI + PPI that pulls July pricing back out |

Trade rows: **#1, #2, #3**. **DEPTH:** US `econ.fact_indicator` deep (193 active indicators) — but June CPI itself is forward, so the FACT layer here is the verified 2026-06-17 FOMC hold + dots (`cb_events`); the CPI numbers are sell-side forecasts (VIEW). **Flags:** CPI/PPI/retail-sales all forward (14-16 Jul); US cash yields (2y 4.28% / 10y 4.61%), WTI $77.74 / Brent $83, DXY 101.28 are sell-side (GS/DB); `fact_bond_yield` EMPTY.


### India — June CPI prints hot at 4.38% but benign at the core; RBI seen looking through

*Flagships read: GS India Wrap (17860) + India CPI note (17981); Citi "Food and Fuel Driven Uptick" (17966) + The Point for Asia Pacific (18032); JPM "June CPI firms but internals benign" (18021); UBS India Economic Comment (17959); Barclays "June CPI: Rising continuously" (17899) + Monsoon tracker (17722); HSBC "India: CPI and trade" (17932) + Asia FX trade update (18074); ANZ "India's CPI above target and expectations" (17896); MS "CPI Breaches 4% Mark" (17949); MOSPI official (17895). Trade: Citi "Long INR on basket and steepener" (17693).*

```spiderchart
{"type":"line","title":"India CPI headline YoY, 2026 (%) — the climb into a hot June","caption":"Grounded: econ.fact_indicator (INDIA.CPI.HEADLINE.C.YOY.IN) Jan-May; June (4.38%) from the official MOSPI release (17895), not yet ingested to fact_indicator. RBI's Q2 forecast was 4.2%.","series":[{"name":"CPI YoY %","color":"#a1382f","points":[["Jan",2.75],["Feb",3.21],["Mar",3.40],["Apr",3.48],["May",3.93],["Jun",4.38]]}]}
```

**A · Themes in play**

| Rank | Theme | Assets | Banks talking | Why it matters to the PM |
|---|---|---|---|---|
| 1 | CPI 4.38% — hot headline, benign core | Rates, INR | MOSPI, Citi, JPM, Barclays, GS, UBS, HSBC, MS, ANZ | Above the 4.2% cluster; fuel/food drove it, core-core ~2.5% |
| 2 | RBI reaction: look through (no 2026 hike) | Rates | Citi, JPM, Barclays | Citi: RBI to cut its Aug forecast ~20bp; no hike unless core >4.5% |
| 3 | Long-INR-FX vs pay-INR-rates vs stopped-out | INR, rates | Citi (long) vs UBS (payer) vs HSBC (stopped) | The oil spike just stopped HSBC's bullish-INR trade |
| 4 | Oil-blockade risk to energy CPI | Rates, INR | Citi, UBS, HSBC | A sustained oil spike re-lifts transport/LPG passthrough |

**B · The "why"** June CPI prints hot at the headline: **MOSPI (17895, official) 4.38%** (provisional), an 18-month high, up from 3.93% in May and above the sell-side 4.2% cluster and the 4.3% survey — food CFPI **5.32%** (from 4.78%), rural 4.74% vs urban 3.92%, housing 2.10%. `econ.fact_indicator` holds the headline series through May (2.75% Jan → 3.21 → 3.40 → 3.48 → 3.93 May); the June print is the official MOSPI release, pending DB ingestion. The house cluster is unanimous: a fuel-and-food surprise with benign core. **Citi (17966):** +45bp headline (food ~20bp + energy ~25bp; transport fuel +7.6%, cooking gas +4.6% — May pump-price hikes, pre-Brent-fall), **core unchanged at 3.9%** (core ex precious metals 2.5%); retains FY27 4.7% headline / 4.5% core; expects the RBI to cut its August headline forecast ~20bp and sees **no 2026 hike unless core sustains above 4.5%**. **JPM (18021):** headline surprised up to 4.4%, but **core-core 2.5%**, internals "benign." **Barclays (17899):** core/core-core 3.9%/2.5%, tracking July at 4.5%, RBI "to look through the supply shock and stay put in 2026." **GS (17981):** 18-month high on cereals/milk food + core goods, July prelim 4.5%. **UBS (17959):** crosses 4%, FY27 CPI 4.8%; **holds INR-swap PAYERS** on H2 food (to 6.5-7.0% on El-Niño + base) and a 2027 re-acceleration. The FX book split just widened: **Citi (17693)** is long INR (basket 40/30/30) + NDOIS 1s5s steepener on FCNR inflows, while **HSBC (18074)** just had its bullish-INR (sell USD/INR 1m NDF, opened 7-Jul at 95.65) **stopped out at 96.20 (−0.5%)** — "the INR is not immune" to the oil-driven depreciation pressure, notwithstanding the RBI's 5-June FX package. **INR firmed +0.19% DoD** to 95.91 on the broad USD give-back (`FX.fact_fx_rate`), and MIBOR was flat. Barclays (17722) flags the monsoon 19% below LPA — the food-H2 swing factor.

**C · Consensus views (≥2 independent banks)**

| Theme | Banks | Shared claim | Evidence cited | What consensus is missing |
|---|---|---|---|---|
| Hot headline, benign core | Citi, JPM, Barclays, GS, UBS, MS | 4.38% on fuel/food; core-core ~2.5% | MOSPI food 5.32%, transport +7.5%; core 3.9% | Food-H2 skew (UBS) vs the benign realised core |
| RBI looks through, on hold 2026 | Citi, JPM, Barclays | Supply shock, not demand; no near-term hike | Core <4.5% threshold (Citi); July ~4.5% | Whether an oil-blockade spike or El-Niño forces a re-think |

**D · Differentiated / unique views**

| Bank | Asset | The view | Why it's different | Hidden assumption | Falsifier |
|---|---|---|---|---|---|
| Citi | INR/rates | Long INR basket + NDOIS steepener; RBI cuts Aug forecast, no 2026 hike | Constructive-FX + steepener + explicit no-hike call on a hot print | FCNR inflows land; core stays <4.5%; oil contained | Oil-blockade spike / equity outflows / core >4.5% |
| UBS | Rates | Hold INR-swap PAYERS as a weather/2027 hedge | Fades the benign core on H2 food + re-acceleration | El-Niño lifts food to 6.5-7.0%; CPI re-accelerates early-2027 | June-quarter CPI keeps undershooting; food base benign |
| HSBC | INR | Bullish-INR (sell USD/INR) stopped out at 96.20 on the oil spike | Concedes the oil-driven INR pressure outweighs the FX-package tailwind, for now | The 5-Jun RBI package would cushion the INR | (Realised) — oil re-escalation forced the stop |

Trade rows: **#5, #6, #11**. **DEPTH:** IN `econ.fact_indicator` deep (~1,242 indicators; fresh-food nowcaster live) — CPI headline + component series loaded through May, giving a fully DB-grounded trajectory into the official June print. **Flags:** **June CPI PRINTED 4.38% (official MOSPI 17895); the BQL/TE `cb_events` row and `fact_indicator` do not yet hold June** — grounded to the official release. WPI 14-Jul forward.


### Singapore — advance Q2 GDP prints strong (5.7% y/y); the MAS three-way is a late-July call

*Flagships read: BNP "EM rates: Receive SORA 1y1y against paid FOMC Dec/Mar" (17773); UBS "Asia: Three things to watch" (17686); StanC advance-GDP read (17685, carried); Citi Auction Preview (17909) + The Point for Asia Pacific (18032).*

**A · Themes in play**

| Rank | Theme | Assets | Banks talking | Why it matters to the PM |
|---|---|---|---|---|
| 1 | Advance Q2 GDP prints strong (5.7% y/y) | SGD | StanC | Above the 5.5% consensus; QoQ 1.1% SA; growth above trend a third year |
| 2 | MAS (late-July, 31-Jul): tighten vs hold vs receive | SGD, rates | ANZ, BNP, GS | ANZ +50bp slope vs BNP won't-tighten vs GS hold-with-tilt |
| 3 | Front SORA carry vs the Fed | Rates | BNP | New receive-SORA-vs-pay-Fed trade (entry 159bp) |

**B · The "why"** Singapore's **advance Q2 GDP prints strong: 5.7% y/y** (above the 5.5% consensus, a touch below StanC's 5.9% call; Q1 was 6.0%) and **1.1% q/q SA** (`cb_events`, actual booked) — above-trend growth for a third year, and an input that leans toward the tightening side of the MAS debate. The MAS July MPS itself is a **late-July decision (31-Jul)**, not today, so the policy call remains a live three-way into month-end. **ANZ (16838)** keeps the out-of-consensus **+50bp slope steepening to 1.5%** — the soft Apr/May core was discount-driven and reverses, a 17% electricity-tariff hike adds 0.47pp to July core, and above-trend growth argues for policy closer to neutral (the firm GDP print supports this leg). **GS (16862)** counters that MAS holds with a mild hawkish tilt. Fresh this window, **BNP's EM-rates flagship (17773)** takes the other side of ANZ outright: with core "comfortably within" the MAS forecast, "MAS is unlikely to tighten FX policy further in the near term," so BNP **receives M27 1y SORA at 1.77% and pays the Dec/Mar FOMC spread at 9bp** (entry 159bp, target 119, stop 179, carry+roll 4.6bp/mo) — SORA acts as a secondary tightening lever only when FX policy is insufficient, and front-end SORA offers "one of the most attractive carry and roll-down within Asian rates." **UBS's "Asia three things" (17686)** does not press a fresh SG-specific call this week (BoK/China/India dominate). **SGD was flat (−0.02% DoD) and SORA unchanged** on the day (`FX.fact_fx_rate`, `rates.fact_observation`), the strong GDP print notwithstanding. The oil-blockade spike is a live cross-current under BNP's "oil off highs" premise.

**C · Consensus views** Inflation risk two-sided into the late-July MAS (ANZ, GS, StanC): a 17% electricity tariff (0.47pp mechanical to July core) plus the renewed oil spike lift H2 core, and Q2 growth printed above trend; the disagreement is whether MAS acts on the slope (ANZ), looks through (GS), or eases domestic liquidity via SORA (BNP's implied read).

**D · Differentiated / unique views**

| Bank | Asset | The view | Why it's different | Hidden assumption | Falsifier |
|---|---|---|---|---|---|
| ANZ | SGD | +50bp slope to 1.5% (out-of-consensus) at the late-July MAS | Only ~38% of the June MAS survey saw any move; strong Q2 GDP supports it | Soft Apr/May core was discount-driven, reverses; growth above trend | Core stays soft into 31-Jul → status-quo hold |
| BNP | Rates | MAS won't tighten → receive front SORA vs pay Fed | Trades the *no-tightening* thesis with a carry+roll expression | FX policy stays the tool; SORA fixings stay low | MAS tightens the slope (ANZ's call) → SORA front repriced up |

Trade rows: **#4, #10**. **DEPTH:** SG `econ.fact_indicator` moderate — **advance Q2 GDP printed 5.7% y/y / 1.1% qoq (FACT, `cb_events` actual booked, above the 5.5% consensus)**; the MAS MPS (31-Jul) is forward. **Flags:** MAS MPS 31-Jul forward (late-July); advance GDP resolved.


### New Zealand — a dove turns hawkish; QSBO shows acute pricing

*Flagships read: ANZ "NZIER QSBO: weak activity; acute inflation pressures" (18030) + NZD Update (18061); Westpac "First Impressions: NZIER QSBO" (18059) + NZD FX Weekly (18083); GS "RBNZ's Conway… respond more firmly" (18068) + QSBO read (18070); JPM "RBNZ, Conway: Finding signal in the inflation noise" (18078); DB "Macro Notes: NZ: Quick take on the QSBO" (18067); Westpac Weekly Economic Commentary (17687, carried).*

**A · Themes in play**

| Rank | Theme | Assets | Banks talking | Why it matters to the PM |
|---|---|---|---|---|
| 1 | Conway (dove) turns hawkish on price-setting | Rates | GS, JPM, DB | "Monetary policy may need to respond more firmly" |
| 2 | QSBO: acute inflation pressures | Rates | ANZ, Westpac | Selling-price gauge jumped 22→41; output gap still negative |
| 3 | ANZ now sees Sep + Oct hikes (+50bp) | Rates | ANZ | Data "justify" the July hike + signalled follow-ups |
| 4 | NZD firmest in the universe | FX | ANZ, Westpac | NZD +0.23% DoD on the USD give-back |

**B · The "why"** New Zealand produced a rare double-hawkish signal today. **RBNZ Chief Economist Paul Conway** — one of the MPC's most dovish members, who voted to hold in May — delivered a speech ("Finding signal in the inflation noise: oil shocks, price setting, and the path back to 2%") that **GS (18068) reads as "clearly hawkish":** "when above-target inflation changes expectations and price-setting behaviour, monetary policy may need to respond more firmly to re-anchor inflation expectations"; households' 2yr-ahead inflation expectations "have increased and become more dispersed since the onset of the Middle East conflict"; and firms have "become more likely to increase prices when costs increase, and less likely to cut them when costs fall," so "cost shocks may now pass through and become embedded in inflation more quickly than in the past." GS keeps a **Sep +25bp to 2.75%** and flags the risk of additional near-term hikes; JPM (18078) and DB (18067) read the same signal. Alongside, the **Q2 QSBO** printed (ANZ 18030): headline confidence rebounded (+1→+12 sa), activity soft (consistent with −0.2% q/q Q2 GDP, a negative output gap), but the **average selling-price gauge jumped to 41 from 22** — ANZ concludes the data "justify" the July kick-off and **maintains OCR +25bp in both September and October** (50bp more), more than the market's ~2 hikes. **NZD firmed +0.23% DoD** (the universe's biggest FX gainer, `FX.fact_fx_rate`) while NZIONA was unchanged pre-CPI. The 21-Jul Q2 CPI is the arbiter; the oil-blockade spike is a fresh cost-side risk exactly in the channel Conway highlighted.

**C · Consensus views**

| Theme | Banks | Shared claim | Evidence cited | What consensus is missing |
|---|---|---|---|---|
| More hikes coming; pricing pressure acute | ANZ, GS, JPM, DB, Westpac | OCR higher through Q4; cost pass-through sticky | Conway speech; QSBO selling-price 22→41 | How many: ANZ Sep+Oct (+50bp) vs GS Sep-only vs mkt ~2 |

**D · Differentiated / unique views**

| Bank | Asset | The view | Why it's different | Hidden assumption | Falsifier |
|---|---|---|---|---|---|
| ANZ | Rates | +25bp in both Sep and Oct on QSBO's acute pricing | Puts specific meeting-dates on the follow-up hikes | Pricing pressure persists; QSBO signal is real | Q2 CPI (21-Jul) undershoots, or activity rolls over |
| GS | Rates | Sep +25bp; reads Conway (a dove) turning hawkish as the key tell | Weights the dovish-member pivot over the noisy activity data | Inflation-expectations drift is the RBNZ's binding concern | A soft Q2 CPI re-anchors expectations |

Trade rows: **#1 (implicit — the RBNZ path).** **DEPTH:** NZ `econ.fact_indicator` moderate — FACT layer is the verified 2026-07-08 RBNZ +25bp to 2.50% (`cb_events`); QSBO is NZIER-proprietary (not in fact_indicator), grounded to the flow (ANZ/Westpac). **Flags:** QSBO + Conway speech printed (per flow); Q2 CPI 21-Jul forward.


### Japan — GPIF FY25 confirms a real rebalancing into JGBs; the long end is capped

*Flagships read: SocGen "Q&A on the latest GPIF comments" (17813); DB "FX Blog: Please come home" (17731); Barclays "JPY Flow Update: GPIF FY25 results" (18062); BNP "JPY rates: long 10s20s box" (18063); ANZ "JPY: the GPIFs policy asset mix" (17721); Nomura "Yen Rates Daily Monitor" (17880) / "Japan Research Pack" (18054) / "JPY Intraday Comment" (17878); Citi "The Point for Japan" (18011); MS "Fading Oil Shock, AI Capex and the BoJ's Next Step" (17746/17747).*

**A · Themes in play**

| Rank | Theme | Assets | Banks talking | Why it matters to the PM |
|---|---|---|---|---|
| 1 | GPIF FY25: rebalancing into JGBs | JGB, JPY | Barclays, SocGen, DB | Concrete flow behind the repatriation theme (super-long up) |
| 2 | Katayama's comments cap the long end | JGB | SocGen, ANZ | 10-20y −12-13bp; SocGen closed short 30y |
| 3 | Belly "behind the curve"; fiscal-vs-supply | JGB | SocGen, BNP | SocGen rec 1y1y; BNP long 10s20s box |
| 4 | Yen: medium-term higher, needs proof | JPY | DB | Repatriation supports the yen, but wants concrete policy |

**B · The "why"** The Japan story turns concrete on the flow side. **Barclays's JPY Flow Update (18062)** reports the **GPIF FY25 results: a rebalancing from domestic and foreign equities into JGBs**, with super-long impacts rising and JGBi (inflation-linked) investment falling — real behaviour behind the repatriation narrative. This sits under **SocGen's GPIF Q&A (17813):** FinMin Katayama said Friday the government wants to "encourage" households and pension funds including the GPIF into domestic assets; super-long JGB yields fell 12-13bp and the JPY firmed; SocGen reads it as a government circuit-breaker against rising yields, notes Reuters reporting the government is exploring buying **within existing allocation-deviation limits** (a ~$75bn envelope, capping the most-bullish scenario), and **closes its systematic short 30y** while staying received 1y1y vs JGB futures. **BNP (18063)** frames the same long end as a fiscal-vs-supply question and puts on a **long 10s20s box**. **DB's FX Blog (17731):** repatriation "makes sense" and underpins DB's medium-term yen-higher call, but it wants "concrete policies, or a change in flows" before calling notable yen strength. **TONAR 10y richened −0.9bp DoD** (`rates.fact_observation`) and USD/JPY was ~flat (+0.02%). Machinery orders/IP + a 20y JGB auction print today (forward); Japanese equities sold with the global memory-name/AI-tech unwind (Nikkei −1.92%, TOPIX −0.71%, `fact_index_level`).

**C · Consensus views**

| Theme | Banks | Shared claim | Evidence cited | What consensus is missing |
|---|---|---|---|---|
| GPIF signalling + FY25 flow cap the long end | Barclays, SocGen, DB, ANZ | Rebalancing into JGBs; comments a circuit-breaker | GPIF FY25 super-long up; 10-20y −12-13bp | Speed/scale of any incremental allocation shift |
| Yen higher medium-term, not yet | DB | Repatriation supports the yen eventually | Foreign-asset share; local returns | Timing; needs concrete policy or sustained flow |

**D · Differentiated / unique views**

| Bank | Asset | The view | Why it's different | Hidden assumption | Falsifier |
|---|---|---|---|---|---|
| SocGen | JGB | Close short 30y; stay rec 1y1y vs JGB futures + short 10s on 5s10s30s fly | Trades the long-end circuit-breaker while keeping the belly "behind-the-curve" | Policy ambiguity caps the long end; slow BoJ | A credible consolidation signal, or fast BoJ-to-2% |
| BNP | JGB | Long 10s20s box on the fiscal-vs-supply question | Isolates the super-long distortion rather than taking outright duration | GPIF/fiscal flow re-shapes the 10s20s segment | The distortion normalises without the box paying |

Trade rows: **#7, #1 (USD/JPY carry).** **DEPTH:** JP `econ.fact_indicator` thin (most macro not loaded) — FACT layer is the verified 2026-06-16 BoJ +25bp to 1.00% (`cb_events`); GPIF/JGB moves are market + sell-side. **Flags:** machinery orders/IP + 20y JGB auction 14-Jul forward.


### China (+ HK feed) — weak Q2 GDP tomorrow, H2 fiscal re-acceleration signalled; HK on the peg

*Flagships read: UBS "Asia: Three things to watch" (17686); DB DBDaily (18034) + "Rise of the RMB Financing Ecosystem" (17696); StanC "China – Infrastructure spending likely to pick up in H2" (18082); GS "China Consumer Pulse Check" (in GS Daily 18069) + "Rotation Temptation" (17703, carried); MS. HK: HSBC "HKD Walking a fine line" (17679) + "The week in 60 seconds" (17678).*

**A · Themes in play**

| Rank | Theme | Assets | Banks talking | Why it matters to the PM |
|---|---|---|---|---|
| 1 | Q2 GDP ~2% qoq saar (weakest since 2022) | CNH, rates | UBS | Prints 15-Jul; the growth signal is the tell |
| 2 | H2 fiscal re-acceleration (infrastructure) | Rates | StanC | Q2 fine-tuned down; H2 issuance to use the existing quota |
| 3 | Policy: no cut (GS) vs targeted support | Rates | GS, UBS, MS | GS no rate/RRR cut 2026; UBS incremental support pre-Politburo |
| 4 | HK: HKD firm on peg, HIBOR nudged | HKD, rates | HSBC | Hawkish-Fed repricing + dividend season; 7.85 a risk not base |

**B · The "why"** Into 15-Jul GDP, **UBS's "Asia three things" (17686)** frames Q2 at ~4.5-4.7% y/y but **~2% qoq saar, the weakest sequential quarter since 2022** — June activity improves only modestly on seasonal/front-loading effects, so the takeaway is the growth signal, and another weak quarter should catalyse targeted, incremental support ahead of the July Politburo. **StanC's fresh alert (18082)** adds the fiscal mechanics: Q2 fiscal implementation slowed (broad spending −5.7% y/y Apr-May, the broad deficit at a three-year low, LGSB issuance and land-sales weak) — a deliberate fine-tune after a strong Q1 — and StanC expects **H2 infrastructure re-acceleration**, accelerating issuance to fully use the existing quota before any further stimulus. **GS** holds the clearest no-easing call — no policy-rate or RRR cut in 2026 — and its **China Consumer Pulse Check (18069)** flags sequentially weaker Q2 consumption and pricing risks. All stay constructive RMB: **DB's DBDaily (18034)** and "RMB Financing Ecosystem" (17696) document the 15th Five-Year Plan elevating RMB internationalisation (FX-risk-reserve cuts, Southbound Bond Connect expansion, deepening CNH markets). **CNH was ~flat DoD (−0.03%)** (`FX.fact_fx_rate`), outperforming the modest USD moves. On the HK feed, **HSBC (17679)** keeps HKD firm on the peg (+0.02% DoD) with HIBOR barely changed (+0.4bp 2y, `rates.fact_observation`); the hawkish-Fed repricing + weak equity sentiment push USD-HKD up in the band, but dividend season (Jun-Sep), widening regulated channels and HKMA reserves at 200% of the base keep a 7.85 test a *risk, not the base case*.

**C · Consensus views**

| Theme | Banks | Shared claim | Evidence cited | What consensus is missing |
|---|---|---|---|---|
| Weak Q2, support stays targeted | GS, UBS, MS, StanC | No large stimulus; H2 infra re-accel | UBS ~2% qoq saar; StanC LGSB slowdown; GS no cut | Whether a weak Q2 forces more than "incremental" |
| Constructive RMB | GS, UBS, DB | Internationalisation + solid external balance | DB 15th FYP; USD/CNY fixings outpace forwards | Cross-border-flow scrutiny as a two-way risk |

**D · Differentiated / unique views**

| Bank | Asset | The view | Why it's different | Hidden assumption | Falsifier |
|---|---|---|---|---|---|
| GS | Rates | No policy-rate OR RRR cut in 2026 | The clearest no-easing call | Growth-inflation mix stays "comfortable"; exports resilient | A demand shortfall on 15-Jul GDP forces easing |
| StanC | Rates | H2 infrastructure re-acceleration via existing quota, not new stimulus | Ties the H2 support to a specific fiscal-implementation mechanism | Fiscal room is used before any fresh package | Exports/housing weaken enough to force front-loaded 2027 issuance |

Trade rows: none direct (CNH constructive; macro backdrop). **DEPTH:** CN `econ.fact_indicator` deep (CPI/PPI/activity loaded) — but the in-window China prints (trade 14-Jul, GDP/activity 15-Jul) are forward; FACT layer today is the prior loaded series + `cb_events` calendar. HK `econ.fact_indicator` moderate. **Flags:** Q2 GDP + activity + trade 14-15 Jul forward; GS-no-cut vs targeted-support camp unreconciled (both shown).


### Canada — BoC tomorrow shapes up as a benign-core hold

*Flagships read: JPM "Bank of Canada Preview: The more things change…" (17988); MS "BoC Preview: Balancing Oil and Slack" (18051); GS "Activity Data Improves in Canada" (18040) + GS BoC preview (17674, carried); ANZ "What's Priced In" (18004).*

**A · Themes in play**

| Rank | Theme | Assets | Banks talking | Why it matters to the PM |
|---|---|---|---|---|
| 1 | BoC 15-Jul: hold, benign core | Rates, CAD | JPM, MS, GS | Core 3m run-rates ~2%; excess supply persists |
| 2 | USMCA-review trade drag | Rates | JPM, MS | Annual reviews + section 232/301 tariffs cloud investment |
| 3 | USD/CAD "too rich at 1.42" | CAD | MS | Room to fall as USMCA uncertainty unwinds |
| 4 | Market prices 2027 hikes | Rates | ANZ | +54bp to Jul-27 — vs StanC's "premature" |

**B · The "why"** Into the 15-Jul BoC, the previews firm up a benign-core hold. **JPM (17988):** no change at 2.25%, limited guidance updates; core measures benign (3m run-rates ~2%), the economy in excess supply, the Q2 Business Outlook Survey "a bit stale" given the May-June oil fall; the oil shock is fading but the **USMCA trade drag intensified** (no USMCA extension, annual reviews, section 232/301 tariffs), keeping investment/hiring muted — on hold rest of 2026, MPR headline shaded down, core held at 2.0%. **MS (18051):** hold through year-end — "neither the bar for a hike nor the bar for a cut has been met" — June jobs signal stabilisation not reacceleration, and **USD/CAD is "too rich at 1.42" with room to fall** as USMCA uncertainty unwinds. This sits with **GS's dovish hold (17674)** — reinforced by GS's "Activity Data Improves in Canada" (18040) — and against **StanC** (a cut by year-end, calling H2-hike pricing "premature") and the market (ANZ 18004: +54bp to Jul-27). **CAD firmed +0.04% DoD** (`FX.fact_fx_rate`); the CORRA front nudged +0.6bp (no fresh 10y tick). June jobs (U-rate 6.5%) remain flow-confirmed, not booked in `cb_events`.

**C · Consensus views**

| Theme | Banks | Shared claim | Evidence cited | What consensus is missing |
|---|---|---|---|---|
| Hold 15-Jul; benign core, persistent slack | JPM, MS, GS | No change; core ~2%, excess supply | Core 3m run-rates ~2%; U-rate 6.5%; USMCA drag | Direction after: dovish (GS/StanC) vs the market's 2027 hikes |

**D · Differentiated / unique views**

| Bank | Asset | The view | Why it's different | Hidden assumption | Falsifier |
|---|---|---|---|---|---|
| MS | CAD | Hold; USD/CAD "too rich at 1.42," room to fall | Ties the hold to an explicit CAD-appreciation call | USMCA uncertainty unwinds; slack persists | A sustained oil shock or a hawkish BoC surprise lifts USD/CAD |
| StanC | Rates/CAD | A cut by year-end; H2-hike pricing "premature" | Only house calling an outright 2026 cut | Downside growth > upside inflation; core moderates | Growth regains momentum / oil re-spike |

Trade rows: none direct. **DEPTH:** CA `econ.fact_indicator` thin (most macro not loaded) — the FACT layer here is the verified 2026-06-10 BoC hold (`cb_events`); jobs/core figures are sell-side (VIEW/flow). **Flags:** BoC + MPR 15-Jul forward; June jobs pre-print (U-rate 6.5% per flow, carried).


### Australia — NAB conditions steady and price pressures easing (pre oil-spike); the wealth-effect drag stands

*Flagships read: GS "NAB Business Survey" (18073) + "Consumer Sentiment" (18072) + wealth-effect note (17645, carried); JPM "Australian NAB survey: Further improvement" (18076); Westpac "Consumer pessimism eases a little" (18084) + "AUD Faces Fresh Test" (17820) + Antipodean Daily Wrap (17761); ANZ "Roy Morgan Consumer Confidence" (18060) + Daily Rates RV Pack (18029); MS "Soft Conditions Across Consumer & Business Surveys" (18080).*

**A · Themes in play**

| Rank | Theme | Assets | Banks talking | Why it matters to the PM |
|---|---|---|---|---|
| 1 | NAB: conditions steady, price pressures easing | Rates | GS, JPM, MS | Final product prices +0.6% qoq, retail −0.3%; but pre oil-spike |
| 2 | Consumer sentiment improving | Rates | GS, Westpac, ANZ | Modest lift; confidence still negative |
| 3 | Has the RBA peaked? | Rates | GS, JPM vs Westpac/BNP | GS wealth-effect drag; mkt ~13bp hike then fade |
| 4 | AUD faces fresh ME/oil test | FX | Westpac | The oil-blockade risk revives the terms-of-trade debate |

**B · The "why"** Australia's June surveys printed today and read soft-but-stabilising. **GS's NAB Business Survey read (18073):** business conditions steady at +3 (a little below the long-run average), confidence recovered +9pt to −5, capacity utilisation 82.0%, and — the rates-relevant part — **price pressures generally eased** (purchase costs −50bp to 2.0% qoq, final product prices −30bp to 0.6%, retail prices −180bp to −0.3%), though labour costs firmed +50bp to 2.0%; crucially the survey ran 23-Jun to 1-Jul when Brent was ~$70, "but [prices] have since rebounded to around $84." **JPM (18076)** reads "further improvement"; **MS (18080)** frames the consumer + business surveys as "soft conditions." Consumer sentiment lifted modestly (GS 18072, Westpac 18084, ANZ Roy Morgan 18060). The structural debate carries: **GS (17645)** quantifies the RBA-has-peaked case — house prices −5% y/y to 1Q27 driving a 90bp wealth-effect drag, consumption to +1.3% y/y by end-2026, unemployment peaking 4.7% 1Q27, easing from early 2027 — against Westpac/BNP's August-hike case; the market (ANZ 18004) prices ~13bp of hike to end-2026 then a fade. On FX, **Westpac (17820)** flags the renewed ME/oil risk as the near-term AUD swing factor. **AUD was flat-to-soft (−0.03% DoD)** (`FX.fact_fx_rate`) — a laggard as the USD eased against higher-beta Asia — with AONIA 2y +0.6bp / 10y −0.3bp. Q2 CPI 29-Jul is the decider.

**C · Consensus views**

| Theme | Banks | Shared claim | Evidence cited | What consensus is missing |
|---|---|---|---|---|
| Conditions soft-but-stabilising; price pressures easing | GS, JPM, MS | NAB steady +3, price gauges lower, confidence recovering | Final product prices +0.6% qoq; retail −0.3%; capu 82% | The survey pre-dates the oil re-spike to ~$84 |
| Housing/consumption softening | GS, JPM, StanC (carried) | Wealth-effect drag on H2 consumption | GS −5% house prices, 90bp drag | Westpac/BNP's live August-hike case |

**D · Differentiated / unique views**

| Bank | Asset | The view | Why it's different | Hidden assumption | Falsifier |
|---|---|---|---|---|---|
| GS | Rates | House prices −5%, consumption +1.3%, easing from early-2027 | Quantifies the wealth channel (0.18% elasticity) into a peaked-RBA path | House prices fall as modelled; inflation normalises end-2026 | Q2 CPI ≥ RBA's ~1.4% (demand-driven) revives the hike |
| Westpac | FX | AUD faces a fresh ME/oil test near-term | Reads the currency off the renewed geopolitical/oil risk | Oil stays elevated; risk sentiment fragile | ME de-escalation / a sharp oil reversal |

Trade rows: (RBA leg two-sided; see NZ). **DEPTH:** AU `econ.fact_indicator` deep — but the NAB/consumer surveys are proprietary (NAB/Westpac/Roy Morgan), not in fact_indicator, so today's prints are flow-grounded; FACT layer is the verified 2026-06-16 RBA hold at 4.35% (`cb_events`). **Flags:** NAB + consumer confidence printed (per flow); Q2 CPI 29-Jul forward.


### Malaysia — Johor's BN landslide reads two ways; Barclays keeps the Sep hike

*Flagships read: GS Johor read (17670, carried); Barclays "Malaysia: Johor state election: PM Anwar losing ground" (17691).*

**A · Themes in play**

| Rank | Theme | Assets | Banks talking | Why it matters to the PM |
|---|---|---|---|---|
| 1 | Johor: BN 48/56 landslide | MYR, rates | GS, Barclays | Federal BN-PH dynamics the market focus |
| 2 | Continuity vs "Anwar losing ground" | MYR | GS vs Barclays | Policy-stability premium vs early-election/fiscal risk |
| 3 | BNM Sep hike still base case | Rates | Barclays | Keeps +25bp to 3.00% despite the politics |

**B · The "why"** The 11-July Johor state election is the political input and the two houses read the same result differently. **GS (17670):** BN won 48 of 56 seats (from 40 in 2022), signalling **continuity** in Johor's investment-led strategy; MYR stays choppy but Bank Negara's June FX-inflow measures cap volatility. **Barclays (17691, "PM Anwar losing ground"):** turnout surged to 69% (from 55%), BN's vote share to 60% (from 43%) while PH's rose only to 33% — evidence BN benefits more than Anwar's PH from opposition troubles; Barclays sees early-general-election risk rising (base case still Feb-2028), expects **more pre-election fiscal spending** (2026 deficit 3.6% vs 3.5% budgeted), and **keeps its base case for a BNM +25bp hike to 3.00% in September**. **MYR firmed +0.09% DoD** on the USD give-back (`FX.fact_fx_rate`); KLIBOR was flat. Next catalysts: Negeri Sembilan 1-Aug, DAP conference 16-Aug.

**C · Consensus views**

| Theme | Banks | Shared claim | Evidence cited | What consensus is missing |
|---|---|---|---|---|
| BN strengthened; federal dynamics the focus | GS, Barclays | BN 48/56, PH weaker | Official results; turnout 69% | Read direction: continuity (GS) vs Anwar-weakening (Barclays) |

**D · Differentiated / unique views**

| Bank | Asset | The view | Why it's different | Hidden assumption | Falsifier |
|---|---|---|---|---|---|
| Barclays | Rates/MYR | Anwar weaker → more fiscal spend, deficit 3.6%; keeps Sep BNM hike | Ties the political result to fiscal slippage while holding the hike | Anwar spends to shore up PH; growth still warrants a hike | An early election triggered, or growth cools enough to stay the hike |
| GS | MYR | Continuity; stability premium at risk only if federal cohesion frays | Reads the landslide as status-quo-positive | BN-PH federal coalition holds; inflows continue | Federal coalition fractures → the premium unwinds |

Trade rows: **#8**. **DEPTH:** MY `econ.fact_indicator` moderate (IP loaded) — FACT layer is the verified 2026-07-09 BNM hold at 2.75% (`cb_events`). **Flags:** Johor a VIEW-level political read; BNM path (hold vs Sep hike) unreconciled.


### Thailand — Citi banks the long-USD/THB profit (+82bp); BoT on hold

*Flagships read: Citi "TP on Long USDTHB Exposure; Rolling Over Bearish PHP" (17728 / 18064); StanC BoT read (16818, carried); GS cross-market short THB (17178, carried).*

**A · Themes in play**

| Rank | Theme | Assets | Banks talking | Why it matters to the PM |
|---|---|---|---|---|
| 1 | Citi books long USD/THB (+82bp) | THB | Citi | Now expects intervention to anchor USD/THB |
| 2 | Rates backed up most in EM Asia | THB, rates | (market) | THOR 2y +3.2 / 10y +4.4 DoD |
| 3 | BoT on hold this year & next | Rates, THB | StanC | Growth focus; fiscal H2 challenging |

**B · The "why"** THB was flat DoD but THOR backed up the most in EM Asia (2y +3.2bp / 10y +4.4bp, `rates.fact_observation`). The fresh event is a trade rotation: **Citi (17728 / 18064)** **books its long-USD/THB 2m EKO** (strike 32.75 / barrier 33.5) for **+82bp** (exit +104 vs entry +22; fwd ref 33.36), having been underweight THB on the disproportionate ME/oil impact during a seasonally weak BoP quarter — with 33 "taken out," Citi now expects "decent FX intervention to anchor expectations around USD/THB." In its EM bond book Citi stays u/w THB (−0.9%) vs o/w MYR/IDR/INR (+0.3% each). The domestic frame carries from **StanC (16818):** BoT on hold this year and next (rate "appropriate," oil-driven inflation "short-term"), with the pressure point fiscal (FY27 deficit 4.3%, debt ~67% vs a 70% ceiling, soft tourism), USD-THB 33.50 end-26; GS still holds a cross-market short THB (17178). The oil-blockade spike is a fresh THB-negative cross-current.

**C · Consensus views** Single-house dominant (StanC) on the domestic BoT call; Citi's realised long-USD/THB (now flat, expecting intervention) and GS's cross-market short both lean the same way structurally on the currency.

**D · Differentiated / unique views**

| Bank | Asset | The view | Why it's different | Hidden assumption | Falsifier |
|---|---|---|---|---|---|
| Citi | THB | Booked +82bp on long USD/THB; now expects intervention to anchor | Rotates from a directional short-THB to an intervention-anchored view | FX authorities defend near 33; ME/oil doesn't force a break | A sustained oil-blockade spike overwhelms intervention |
| StanC | Rates/THB | BoT on hold both years; FY27 deficit 4.3% | Fiscal-first read tying weak tourism + oil to a wider deficit | Tourism stays soft; disbursement delayed | Tourism rebounds in peak season; fiscal room used decisively |

Trade rows: **#9**. **DEPTH:** TH `econ.fact_indicator` moderate — FACT layer is the verified 2026-06-24 BoT hold at 1.00% (`cb_events`). **Flags:** StanC read carried; Citi USD/THB profit-take fresh.


### Philippines — Citi rolls the bearish PHP structure; StanC's Aug-hike carry stands

*Flagships read: Citi "TP on Long USDTHB; Rolling Over Bearish PHP" (17728 / 18064) + Auction Preview (17909); StanC BSP read (16822, carried). Structured + Qdrant sweeps confirm the country is thin in-window — no fresh independent macro note beyond Citi's trade + the carried StanC.*

**A · Themes in play**

| Rank | Theme | Assets | Banks talking | Why it matters to the PM |
|---|---|---|---|---|
| 1 | Citi rolls bearish PHP 1x1.5 ratio 3m | PHP | Citi | Booked −10.5bp on the old, rolled to 13-Oct; "limit to PHP strength" |
| 2 | One more BSP hike to 5.00% (Aug) | Rates | StanC | Terminal 5.00%; prefer 2Y-3Y RPGB carry |
| 3 | Peso firmer; front flat | PHP, rates | (market) | PHP +0.04% DoD; PHIREF 2y +0.2bp |

**B · The "why"** The peso firmed +0.04% DoD (USD give-back) and the PHIREF front barely moved (2y +0.2bp, `rates.fact_observation`). Fresh this window, **Citi (17728)** exits its long-USD/PHP 1x1.5 call ratio (long 1x strike 62.0 vs sell 1.5x strike 63.0) at +10bp for a **−10.5bp loss** (entry +20.5bp) but **rolls the bearish PHP structure another 3 months (13-Oct)** for +17bp, judging "there is a limit to PHP strength despite the improved external outlook." The domestic frame carries from **StanC (16822):** the Philippines is "between a rock and a hard place" — soft growth with elevated, broadening inflation — and StanC expects **one more 25bp BSP hike to 5.00% in August** then two 2027 cuts, preferring **2Y-3Y RPGBs (~125-150bp carry over ONRRP)** as supply pressure eases. Sara Duterte's impeachment trial remains the political overhang.

**C · Consensus views** Single-house dominant (StanC) on the domestic call; Citi's rolled bearish-PHP structure keeps a long-dollar EM-Asia lean.

**D · Differentiated / unique views**

| Bank | Asset | The view | Why it's different | Hidden assumption | Falsifier |
|---|---|---|---|---|---|
| StanC | Rates | Long 2Y-3Y RPGB carry into a final Aug hike then a hold | Ties the terminal-hike view to a specific belly-carry trade | BSP hikes once more then holds; RPGB supply eases | Oil-blockade re-spike lifts RPGB supply/yields |
| Citi | PHP | Rolls bearish PHP — "limit to PHP strength" | Fades further peso gains despite the better external outlook | External inflows don't push PHP through 61 | A strong-inflow episode extends PHP strength |

Trade rows: **#9**. **DEPTH:** PH `econ.fact_indicator` moderate — FACT layer is the verified 2026-06-18 BSP +25bp to 4.75% (`cb_events`). **Flags:** BSP decision post-window; StanC read carried, Citi PHP roll fresh; country thin in-window.


### Indonesia — biggest FX gainer on the USD give-back

*Flagships read: Citi EM FX & Rates Strategy / EM bond book (17728) + Indonesia MSCI-weight note (17839); UBS "ASEAN Economic Outlook 2026-27" deck (17716, chart-only); Citi domestic policy read (16845, carried).*

**A · Themes in play**

| Rank | Theme | Assets | Banks talking | Why it matters to the PM |
|---|---|---|---|---|
| 1 | IDR the biggest FX gainer DoD | FX | (market), Citi | IDR +0.29%; Citi o/w IDR in its EM bond book |
| 2 | BI pro-stability | FX, rates | Citi (carried) | Anchors IDR vs USD; BI 22-Jul |
| 3 | ASEAN growth backdrop | Rates | UBS | ASEAN 2026-27 deck (chart-only) |

**B · The "why"** IDR was the **biggest FX gainer in the universe (+0.29% DoD)** to 18,108 as the dollar eased against high-beta Asia (`FX.fact_fx_rate`); JIBOR had no fresh 07-14 tick (n/l). **Citi (17728)** keeps Indonesia **overweight in its EM bond book (+0.3%)** alongside MYR/INR. The policy frame carries from **Citi (16845):** BI runs a **pro-stability stance anchoring the rupiah vs the USD** (SRBI + selective hikes rather than automatic Fed-tracking), the 2026 deficit held under 3% via expenditure cuts, and the long-end IndoGB bid supported by lighter H2 issuance and the equity→bond rotation — the augmented-deficit risk (Danantara) the tail. **UBS's "ASEAN Economic Outlook 2026-27" (17716)** is an ID-tagged chart deck (image-only, noted-not-deep-read) corroborating the growth backdrop. BI decides 22-Jul.

**C · Consensus views** Single-house dominant (Citi, carried) on the domestic call; UBS's ASEAN deck corroborates the growth backdrop without a fresh rates trade.

**D · Differentiated / unique views**

| Bank | Asset | The view | Why it's different | Hidden assumption | Falsifier |
|---|---|---|---|---|---|
| Citi | Rates/FX | Long-end IndoGB bid continues; o/w IDR; BI anchors the rupiah | On-the-ground policymaker read + EM-book positioning | H2 issuance comes off; BI keeps IDR anchored | Augmented-deficit blowout or an oil-driven IDR sell-off forces BI to defend |

Trade rows: **#9 (EM-book o/w IDR).** **DEPTH:** ID `econ.fact_indicator` deep (CPI/activity loaded) — no in-window ID print; FACT layer is the verified 2026-06-18 BI +25bp to 5.75% (`cb_events`) + the prior loaded series. **Flags:** BI decides 22-Jul (post-window).


### United Kingdom — Bailey speaks today, Burnham to PM 20-Jul; GBP/SONIA flat

*Flagships read: GS Weekend Macro Call (17620, carried); Barclays "UK Themes: The signal from the noise" (17766) + "UK Rates Strategy" (17769); JPM UK Money Market Report (18077); StanC UK read (carried); ANZ "What's Priced In" (18004).*

**A · Themes in play**

| Rank | Theme | Assets | Banks talking | Why it matters to the PM |
|---|---|---|---|---|
| 1 | Burnham becomes PM 20-Jul | Rates, GBP | GS, StanC (carried) | Fiscal-agenda watch; "China Shock 2.0" |
| 2 | Bailey speaks 14-Jul; GDP 16-Jul | Rates, GBP | (calendar) | Into a market still pricing BoE hikes |
| 3 | GBP/SONIA flat DoD | GBP, rates | (market) | GBP +0.02%; SONIA 2y +0.2bp |

**B · The "why"** The UK is a political-fiscal story with a market that keeps pricing BoE hikes. **Andy Burnham is set to become PM on 20 July** — GS's Weekend Macro Call (17620) flags his "prospective fiscal policy agenda" as a global-macro watch item, and **StanC (carried)** has raised its 2026 UK CPI to 3.1% on lagged energy pass-through while expecting the BoE to hold through 2026 and cut twice in H1-2027 to 3.25%, with only slight fiscal-deficit narrowing. Barclays's "UK Themes" (17766) and UK Rates Strategy (17769) work the same fiscal/gilt-supply questions. The market, though, has repriced BoE hikes (ANZ 18004: ~+29bp by December). **BoE Governor Bailey speaks today (14-Jul)** and GDP prints 16-Jul (forward). **GBP was flat (+0.02% DoD)** (`FX.fact_fx_rate`) and SONIA roughly unchanged (2y +0.2bp / 10y −0.1bp — cash gilts not loaded, so this is the OIS read). The oil-blockade spike is a fresh upside inflation risk into the BoE debate.

**C · Consensus views** Limited independent in-window UK-macro coverage; the anchor is StanC's hold-2026/cuts-H1-27 frame plus GS's Burnham-fiscal flag and Barclays's gilt-supply work, against a market that prices BoE hikes.

**D · Differentiated / unique views**

| Bank | Asset | The view | Why it's different | Hidden assumption | Falsifier |
|---|---|---|---|---|---|
| StanC | Rates/GBP | BoE holds 2026, cuts H1-27 to 3.25%; CPI 3.1%; Burnham keeps fiscal rules | Ties the political transition to a constrained-fiscal, delayed-cut path — against a market pricing hikes | Wage pass-through limited; energy declines from 2027 | A hot wage/CPI print (validates the market's hike pricing) or a fiscal-rule loosening |

Trade rows: none direct. **DEPTH:** UK `econ.fact_indicator` thin (most macro not loaded) — FACT layer is the verified 2026-06-18 BoE hold 7-2 (`cb_events`); CPI/fiscal figures are sell-side (VIEW). **Flags:** Bailey speech 14-Jul, Burnham PM 20-Jul, UK GDP 16-Jul forward; StanC vs market-priced-hikes unreconciled (both shown).


---

## 10. Grounding ledger  *(SYN)*

**Sources by layer:**
- **`calendar.cb_events` + `econ.fact_indicator` (FACT):** **US CPI is pre-print (null) at compile** — forward/VIEW. **SG advance Q2 GDP has printed — 5.7% y/y / 1.1% qoq** (`cb_events` actual booked, above the 5.5% consensus); the **MAS MPS is a 31-Jul release** (forward), not a 14-Jul event. **India June CPI is confirmed PRINTED at 4.38%** via the official MOSPI release (17895); `econ.fact_indicator` holds the India CPI headline series through **May (3.93%)** and the June print is not yet ingested, so June is grounded to the official release (the chart uses fact_indicator Jan-May + MOSPI June). No universe CB decides in-window; forward decisions (BoC 15-Jul, ID BI 22-Jul, MAS MPS 31-Jul; BoK 16-Jul outside universe) verified against real rows. Policy-rate dashboard traced to verified decision rows: US 3.75% held 2026-06-17 (dots up); JP 1.00% hiked 06-16; NZ 2.50% hiked 07-08; ID 5.75% hiked 06-18; PH 4.75% hiked 06-18; IN 5.25% held 06-05; AU 4.35% held 06-16; CA 2.25% held 06-10; MY 2.75% held 07-09; TH 1.00% held 06-24; UK 3.75% held 06-18 (7-2).
- **Market layers — DoD 07-13 → 07-14, sign re-checked.** DoD computed strictly as (07-14 last-tick) − (07-13 last-tick), last tick = max `ts` per calendar day, `rates.fact_observation` quote='par'. **07-14 is the current, pre-CPI session** (partial for some Asian curves). Rates DoD: ESTR 2y +6.9 / 10y +3.3 (biggest DM mover), THOR 2y +3.2 / 10y +4.4, CORRA 2y +0.6, AONIA 2y +0.6 / 10y −0.3, SOFR 2y +0.6 / 10y −0.4, HIBOR 2y +0.4, PHIREF 2y +0.2, SONIA 2y +0.2; TONAR 10y −0.9 (richer); NZIONA/SORA/MIBOR/KLIBOR/CNH flat; JIBOR n/l. `FX.fact_fx_rate` (SPOT) runs to **07-14** — the USD eased against high-beta EM Asia (IDR +0.29, INR +0.19, MYR +0.09, PHP +0.04; NZD +0.23, CAD +0.04, JPY/HKD/EUR/GBP +0.02) while AUD −0.03, SGD −0.02, CNH −0.03 lagged; THB flat. `equities.fact_index_level` fresh to **07-13** (the Monday risk-off session — S&P −0.79 @ 7,515, Nasdaq −1.88, Nikkei −1.92, TOPIX −0.71, Russell −0.83, HSTECH −0.96; Asia-ex-Japan value held: HSI +0.16, HSCE +0.33, Nifty +0.02, SIMSCI +0.10, SET flat; CAC +0.31) — one behind the Tuesday FX/rates, flagged. `equities.fact_vix` fresh to 07-13 (VIX +2.1 to 17.16; VXN 27.3, VVIX 95.28, VIX9D 15.13). `commodities.fact_spot`: WTI **unrefreshed at 72.27 (07-10)**; gold 4,005 (07-13, −2.8%), silver 58.16 (−2.3%). **The live oil level — WTI $77.74 / Brent $83.04 (+9%) — and US cash 2y 4.28% / 10y 4.61% and DXY 101.28 are sell-side (GS 18069 / DB 18034).** `fact_bond_yield` EMPTY — no cash govt yields loaded. Credit spreads not in IMDR. **KOSPI 200 −9.85% one-day excluded as a rebasing/roll artifact (GS 18069: KOSPI −8% WoW).**
- **`research.fact_chunk` + Qdrant (VIEW):** in-window corpus (07-13 → 07-14 = ~408 reports) built structured-first — `dim_report` window filter across all vendors, scoped to each desk's daily-cadence flagship series and cross-checked against the Outlook 13-folder taxonomy — then supplemented with **targeted per-catalyst Qdrant sweeps** (US CPI/Waller, Hormuz-oil, MAS/SG, India CPI, China Q2, plus a Philippines thin-country fill). Full chunks read via the scratchpad dumper (`imdr-db` MCP truncates cell display). Prior-window frames carried where unchanged (GS 17620/17645/17650/17670/17671/17621, StanC 16818/16822/16845/17685, ANZ 16838, GS 16862, Citi 16845, GS 17178).

**Flagship series fed into each country block (series · report id):**
- **US:** GS US Daily Download 17798 · GS US Economics Weekly 17923 · GS Morning Wrap 17785 · GS Weekend Macro Call 17797 · JPM Daily Economic Briefing 18048 · JPM US Market Intelligence 17869 / Trading CPI 17933 · JPM Daily Financial Markets Monitor 18079 · Citi The Global Point 17845 / The Daily Update 17908 / Asymmetry-USD 18007 · DBDaily 18034 / Fed Watcher 18035 · Barclays Macro Wrap 17822 / Inflation-Linked Daily 17768 · Nomura US Daily Commentary 18055 · MS 18053 · HSBC "60 seconds" 17678 · ANZ US Pulse 17720. (+ event notes 18016/18014/18047/17902/18008)
- **India:** GS India Wrap 17860 / CPI 17981 · Citi CPI 17966 / Point Asia-Pacific 18032 · JPM CPI 18021 · UBS India Economic Comment 17959 · Barclays CPI 17899 / Monsoon 17722 · HSBC CPI+trade 17932 / Asia FX trade update 18074 · ANZ India CPI 17896 · MS 17949 · MOSPI 17895. (+ Citi trade 17693)
- **Singapore:** BNP SORA trade 17773 · UBS "Asia three things" 17686 · StanC 17685 · Citi Auction Preview 17909 / Point Asia-Pacific 18032.
- **NZ:** ANZ QSBO 18030 / NZD Update 18061 · Westpac First Impressions 18059 / NZD FX Weekly 18083 · GS Conway 18068 / QSBO 18070 · JPM Conway 18078 · DB NZ QSBO 18067 · Westpac Weekly 17687.
- **Japan:** Barclays GPIF FY25 18062 · SocGen GPIF Q&A 17813 · DB FX Blog 17731 · BNP JPY box 18063 · ANZ JPY/GPIF 17721 · Nomura Yen Rates Daily 17880 / Japan Research Pack 18054 / JPY Intraday 17878 · Citi Point Japan 18011 · MS 17746/17747.
- **China(+HK):** UBS 17686 · DB DBDaily 18034 / RMB Ecosystem 17696 · StanC China infra 18082 · GS China Consumer Pulse 18069 / Rotation Temptation 17703 · HSBC HKD 17679 / FX week 17678.
- **Canada:** JPM BoC Preview 17988 · MS BoC Preview 18051 · GS Canada activity 18040 / BoC 17674 · ANZ What's Priced In 18004.
- **Australia:** GS NAB 18073 / Consumer Sentiment 18072 / wealth-effect 17645 · JPM NAB 18076 · Westpac Consumer 18084 / AUD note 17820 / Antipodean Daily Wrap 17761 · ANZ Roy Morgan 18060 / Daily Rates RV Pack 18029 · MS Surveys 18080.
- **Malaysia:** GS Johor 17670 · Barclays Johor 17691.
- **Thailand:** Citi trade 17728 / 18064 · StanC 16818 · GS 17178.
- **Philippines:** Citi trade 17728 / 18064 / Auction Preview 17909 · StanC 16822.
- **Indonesia:** Citi EM book 17728 / MSCI note 17839 · UBS ASEAN deck 17716 · Citi 16845.
- **UK:** GS Weekend Macro Call 17620 · Barclays UK Themes 17766 / UK Rates 17769 · JPM UK Money Market 18077 · StanC (carried) · ANZ 18004.

**Targeted Qdrant sweeps run this window** (window 07-13→07-14, group-by-report):
1. "US CPI Waller July FOMC hike core inflation" → Nomura 18055, GS 17923/18016, UBS 18001, Citi 18007. (surfaced GS core 0.17%/2.76% + Citi asymmetry-USD; folded in)
2. "Strait of Hormuz oil blockade Brent crude forecast USD" → UBS 17960 (Hormuz tracker), Citi 18008, StanC 17816.
3. "MAS Singapore monetary policy SGD NEER slope advance GDP" → BNP 17773 (confirmed the flagship), JPM 18020.
4. "Philippines BSP peso rates inflation bonds" (thin-country fill) → Nomura 18057, Citi 17909 — confirmed PH is thin in-window; no new independent macro note.

**Per-country FACT-vs-flow grounding note:**

| Country | fact_indicator-grounded FACT | Sell-side / survey (VIEW/flow) | Coverage |
|---|---|---|---|
| US | 2026-06-17 FOMC hold + dots (`cb_events`); 193 active indicators | June CPI (forward), Waller quote, cash yields/DXY/Brent | deep |
| India | CPI headline + components Jan-May (`fact_indicator`); policy 5.25% | June CPI 4.38% = official MOSPI (not yet in DB) | deep (~1,242 ind) |
| China(+HK) | prior CPI/PPI/activity (`fact_indicator`); | Q2 GDP/trade forward; StanC fiscal, UBS qoq saar | deep |
| Indonesia | policy 5.75%; prior series | IDR move (FX layer); Citi EM-book positioning | deep |
| Australia | policy 4.35% (`cb_events`) | NAB/Westpac/Roy Morgan surveys (proprietary, flow) | deep ind, but today's prints flow |
| NZ | policy 2.50% (`cb_events`) | QSBO (NZIER-proprietary, flow); Conway speech | moderate |
| Japan | policy 1.00% (`cb_events`); market rates | GPIF FY25/flows, JGB moves (sell-side + market) | thin |
| SG/TH/MY/PH | verified policy rates (`cb_events`); **SG advance Q2 GDP 5.7% y/y printed**; market rates | MAS MPS 31-Jul forward; trades sell-side | moderate |
| Canada / UK | verified holds (`cb_events`) | jobs/CPI/fiscal sell-side | thin |

**Charts included (all grounded):**
1. *Tier1 — FX vs USD DoD % bar* — `FX.fact_fx_rate` SPOT last-tick 07-13 vs 07-14 across the 13 universe currencies; shows the EM-Asia-firmer / DM-lagged split.
2. *Tier1 — Policy-rate divergence bar* — `calendar.cb_events` verified decision rows, 11 universe policy rates; shows EM Asia high vs Japan/Thailand at 1.00%.
3. *India — CPI headline YoY trajectory Jan→Jun 2026 line* — `econ.fact_indicator` (INDIA.CPI.HEADLINE.C.YOY.IN) Jan-May + official MOSPI June (4.38%); shows the climb into the hot print vs the RBI's 4.2% forecast.

*(A US CPI-core trajectory chart and a rates-DoD bar were considered and dropped: US June core is a forward sell-side forecast, not a print, and the 07-14 rates DoD is near-flat outside ESTR/THOR — too sparse to be worth a visual.)*

**Source-of-record notes:** US CPI is null in `cb_events` (pre-print, sell-side previews are VIEW). SG advance Q2 GDP has booked (TE + BQL both carry 5.7% y/y / 1.1% qoq actual); the MAS MPS is a 31-Jul release (forward). For India CPI, the **official MOSPI release (17895) is the source of record** (4.38%), used over the still-null BQL/TE lane and the sell-side rounding (4.2%). US core-CPI consensus is itself split (BQL/TE survey 0.3% core vs the `forecast` field 0.2%; cons YoY 2.9%); both shown. Live oil is sell-side (WTI $77.74 GS / Brent $83.04 DB) vs the stale IMDR spot (72.27, 07-10) — both shown, IMDR flagged stale.

**Unreconciled / both-shown:**
- **US June core CPI:** GS 0.17% / JPM 0.22% / cons 0.3% / BNP 0.37% — full spread shown; the hot-vs-soft outcome is Waller's stated hike trigger.
- **US rate direction:** Governor Waller (open to a near-term hike) vs Chair Warsh (dove, no guidance) — both shown.
- **India:** Citi (long INR + steepener, no 2026 hike) vs UBS (INR-swap payer, food-H2 hedge) vs HSBC (bullish-INR stopped out on oil) — all shown.
- **Canada:** JPM/MS/GS (benign-core hold) vs StanC (cut by year-end) vs market (+54bp to Jul-27) — all shown.
- **Singapore MAS:** ANZ (+50bp slope) vs BNP (won't tighten, receive SORA) vs GS (hold-with-tilt) — all shown.
- **China policy:** GS (no rate/RRR cut 2026) vs the targeted-support camp (UBS/StanC/MS, H2 infra) — both shown.
- **Malaysia Johor:** GS (continuity) vs Barclays (Anwar losing ground, keeps Sep hike) — both shown.
- **New Zealand:** ANZ (Sep + Oct, +50bp) vs GS (Sep only) vs market (~2 hikes) — all shown.
- **UK:** StanC (hold-2026/cuts-H1-27) vs the market's priced BoE hikes — both shown.

**Not loaded / pre-print (flagged):** US June CPI pre-print (null) in `cb_events`; sell-side previews only. SG advance Q2 GDP has printed (5.7% y/y / 1.1% qoq, `cb_events`); the MAS MPS is a 31-Jul release (forward). India June CPI grounded to official MOSPI (17895); BQL/TE lane and `fact_indicator` do not yet hold June. Canada June jobs pre-print (U-rate 6.5% per flow, carried). IMDR WTI unrefreshed at 72.27 (07-10); the live WTI $77.74 / Brent $83, US cash yields and DXY are sell-side (GS/DB). Equities + VIX fresh only to 07-13 (one session behind the Tuesday FX/rates). `fact_bond_yield` EMPTY. Credit spreads not in IMDR (PH RPGB carry, Citi option strikes — sell-side, labelled). KOSPI 200 −9.85% excluded as a rebasing artifact. JP/CA/UK `econ.fact_indicator` thin/absent. AU NAB / NZ QSBO surveys are proprietary (not in fact_indicator) — flow-grounded. **No BBG chat transcript exists for 2026-07-14.**

**Differentiated-view count (§9.D):** US 3 · IN 3 · SG 2 · NZ 2 · CN 2 · JP 2 · CA 2 · AU 2 · MY 2 · TH 2 · PH 2 · ID 1 · UK 1 = **26 differentiated rows across 13 countries** (every covered country carries at least one).
