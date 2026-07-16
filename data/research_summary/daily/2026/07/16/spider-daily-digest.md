---
edition: daily
date: 2026-07-16
---

# RV CAPITAL · RATES & FX DESK — DAILY MACRO PULSE
# The disinflation one-two lands: after Tuesday's soft core CPI, June PPI prints soft too — the Fed-on-hold read cements, the dollar keeps sagging, and the Bank of Canada holds — while China's Q2 GDP miss is compounded by record-low credit growth that pulls the desks toward a policy pivot

### The second shoe dropped soft. **June PPI fell −0.3% m/m (survey 0%, forecast +0.1%) and core PPI rose just +0.2% (survey +0.4%)**, following Tuesday's flat core CPI — the one-two that pins the core-PCE nowcast at ~0.17-0.19% (GS 0.17, MS 0.17, Citi 0.18, Barclays 0.19; JPM the outlier, revised *up* to 0.20). Every house reads July-hike odds as effectively gone (ANZ: OIS ~15% vs ~45% pre-CPI) and the Fed as parked on hold for the summer. The **Bank of Canada held at 2.25%** as expected, cut its 2026 growth forecast but struck a more optimistic domestic tone (Macklem dropped the consecutive-hike language) — on-hold-through-2026 is now unanimous across GS/JPM/HSBC/UBS/Nomura against a market still pricing ~50bp of hikes by mid-2027. The dollar kept weakening (**GBP +1.03%**, NZD +0.64%, AUD +0.44%, EUR +0.35% DoD), and the Asia-Pacific front-ends that backed up on Tuesday's pre-CPI Asian close now **rallied on the relief** (NZ 2y −9.2bp, PH −7.4bp, HK −5.8bp). In Asia the gravity shifted to **China**, where **June credit missed hard — new yuan loans CNY1,610bn (survey CNY2,000bn), loan growth 5.2% and total social financing 7.4%, both fresh record lows** — compounding Tuesday's Q2 GDP miss (4.3%) and pulling the desks to trim full-year forecasts (Citi/MS to 4.6%) and price a Politburo policy pivot late this month. Japan's long end found temporary relief on a strong 20y auction and government verbal intervention (BNP called off its long 10s20s box; SocGen booked term-premium trades). US retail sales (today) and the Bank of Korea (+25bp expected, outside the universe) are the remaining live prints.

**Window:** flow 2026-07-15 → 2026-07-16 · Wednesday US-session close (post-PPI/BoC) + Thursday Asian open · **Compiled** 16 Jul 2026 (Thursday) · **Edition:** Daily
**Universe:** AU · NZ · JP · IN · TH · ID · MY · SG · HK · PH · US · CA · UK

> FX/rates PM lens. Number-first, low-opinion, neutral — the daily does not judge. Sell-side is treated as motivated until the numbers say otherwise. Trades are surfaced with assumption + falsifier — never rated. Every table row is explained in the prose beneath it.
>
> **Grounding legend:** FACT = printed/decision (`calendar.cb_events`, `econ.fact_indicator`) · DEPTH = component series (`econ.fact_indicator`) · VIEW = sell-side interpretation (`research.fact_chunk` + Qdrant) · PRICING = market-implied · SYN = synthesis. Where a marquee number has not booked to the DB, it is labelled **per flow** (sell-side) or **official release**.

---

## Hero stat band

| Number | What it is | Memory / context |
|---|---|---|
| **−0.3% m/m · 5.5% y/y** | US June **PPI** — PRINTED SOFT (`cb_events` 60972/60979) | The second shoe. Headline PPI fell −0.3% m/m (survey 0%, forecast +0.1%, prior revised **down** from 1.1% to 0.6%®) on energy −6.4%; YoY 5.5% (survey 6.2%). **Core PPI +0.2% m/m** (survey 0.4%, prior revised 0.4%→0.1%®), core YoY **4.7%** (survey 5.2%). Ex-food/energy/trade +0.1% m/m. Coming the day after the flat core CPI, this is the disinflation one-two — the PCE-relevant details set the core-PCE nowcast at ~0.17-0.19%. |
| **Core PCE ~0.17-0.19%** | June core-PCE nowcast after CPI+PPI (VIEW, house cluster) | GS **0.17%** (YoY 3.32%, from 0.18% pre-PPI, 18770), MS **0.17%** (18798), Citi **0.18%** (lowered from 0.21%, 18757/18758), Barclays **0.19%** (18750). **JPM is the outlier — raised to 0.202%** as PPI services feeding PCE ran firmer, "still not mission accomplished on inflation" (18787). Citi: "softest since March 2025… takes the July hike off the table… price out hikes altogether over the summer." |
| **BoC held 2.25%** | Bank of Canada decision + MPR + Macklem presser — RESOLVED (`cb_events` 60980) | Held as expected (survey/GS/median 2.25%). MPR cut the 2026 Q4/Q4 GDP forecast 0.4pp to 1.4% but called the outlook "broadly unchanged"; opening statement returned to "policy is appropriate"; Macklem dropped the consecutive-hike scenario but kept it alive on oil. **On-hold-through-2026 is unanimous (GS/JPM/HSBC/UBS/Nomura) vs a market pricing ~50bp of hikes by mid-2027** (HSBC 18822). |
| **CNY1,610bn** | China June new yuan loans — PRINTED MISS (`cb_events` 108198) | Well below the CNY2,000bn survey (weakest June since 2021); loan growth slipped to **5.2% y/y** and total social financing to **7.4%** — both fresh record lows (108200/108201); M2 8.0% (survey 8.5%). JPM cut its year-end loan/TSF forecasts and pushed its rate-cut call to Q4 (18719); Nomura: "the AI economy cannot cure China's economic woes" (18723). Compounds Tuesday's Q2 GDP miss (4.3%). |
| **GBP +1.03% · NZD +0.64% · AUD +0.44%** | FX vs USD DoD, 07-14→07-15 (`FX.fact_fx_rate`, last-tick) | The dollar kept weakening the day after the soft CPI — sterling led the universe (UK GDP due today), EUR +0.35%, IDR +0.27%, CAD +0.14%, SGD +0.14%, KRW +0.13%. **THB −0.24% and MYR/TWD −0.15% are the laggards.** INR flat (−0.05%), recovered from Tuesday's −0.45%. |
| **NZ 2y −9.2bp · PH −7.4bp · HK −5.8bp** | 2y OIS DoD, 07-14→07-15 (`rates.fact_observation`, par) | The soft-CPI relief reached the Asia-Pacific front-ends that had backed up on Tuesday's pre-print Asian close — the reversal yesterday's edition flagged as pending. US SOFR 2y −4.5bp, UK −4.3bp, CA −4.9bp (into the BoC). **Australia is the exception — AONIA +3.2bp**, the hawkish outlier after Assistant Governor Hunter said higher unemployment may be needed. |
| **US retail sales — today** | June advance retail sales (FORWARD at compile, `cb_events` 65717) | Survey **+0.2% m/m** (forecast +0.5%), control group +0.5%, ex-auto −0.1%; prior 0.9%. Initial claims survey 217K. The day's live US data — refines the consumer read into the 29-Jul FOMC. Frame forward; use the actual if it books by run time. |
| **BoK +25bp expected — today (context)** | Bank of Korea decision (`cb_events` 65683; outside universe) | Survey/forecast hike to **2.75%** (prior 2.50%). Korea is not in the 13-country roster — carried as Asia-rates/KRW context only. Korea unemployment eased to 2.7% on 07-15 (`cb_events` 41371, survey 2.8%). |

```spiderchart
{"type":"bar","title":"US June PPI — actual undershot survey across the board (the CPI→PPI one-two)","caption":"Grounded: calendar.cb_events TE lane (ids 60972/60973/60975/60979/60977), printed actual vs survey. Headline PPI fell on energy; core PPI and the ex-food/energy/trade cut both came in soft. Following Tuesday's flat core CPI, the PCE-relevant details set the June core-PCE nowcast at ~0.17-0.19%.","series":[{"name":"Actual","color":"#2b5a86","points":[["PPI m/m",-0.3],["Core PPI m/m",0.2],["PPI y/y",5.5],["Core PPI y/y",4.7]]},{"name":"Survey","color":"#b5761f","points":[["PPI m/m",0.0],["Core PPI m/m",0.4],["PPI y/y",6.2],["Core PPI y/y",5.2]]}]}
```

```spiderchart
{"type":"bar","title":"FX vs USD — day-over-day % (07-14 → 07-15): the dollar kept sagging","caption":"Grounded: FX.fact_fx_rate SPOT last-tick per day. Positive = local currency stronger vs USD. The soft CPI/PPI kept the dollar on the back foot into the BoC — sterling led ahead of today's UK GDP, then NZD/AUD/EUR. THB and MYR/TWD are the laggards; INR recovered to flat after Tuesday's −0.45%.","series":[{"name":"DoD %","color":"#1f6b4f","points":[["GBP",1.03],["NZD",0.64],["AUD",0.44],["EUR",0.35],["IDR",0.27],["CAD",0.14],["SGD",0.14],["KRW",0.13],["CNH",0.06],["PHP",0.02],["JPY",0.01],["HKD",-0.02],["INR",-0.05],["TWD",-0.15],["MYR",-0.15],["THB",-0.24]]}]}
```

```spiderchart
{"type":"bar","title":"2y OIS/swap — day-over-day bp (07-14 → 07-15): the relief reaches Asia","caption":"Grounded: rates.fact_observation par, 2y, last-tick per day. US/UK/CA front-ends fell further (US EOD is post-PPI/BoC). The Asia-Pacific curves that backed up on Tuesday's pre-CPI Asian close now rallied on the soft-CPI relief — NZ/PH/HK/SG led. Australia is the hawkish exception (AONIA +3.2bp) after Assistant Governor Hunter's higher-unemployment remark; Japan nudged up as the verbal-intervention relief was already priced.","series":[{"name":"DoD bp","color":"#a1382f","points":[["NZ",-9.2],["PH",-7.4],["HK",-5.8],["CA",-4.9],["US",-4.5],["UK",-4.3],["SG",-3.5],["EUR",-1.5],["TH",-1.0],["IN",-0.8],["ID",0.3],["JP",0.6],["MY",1.0],["AU",3.2]]}]}
```

```spiderchart
{"type":"bar","title":"China June credit missed — new yuan loans and TSF below consensus","caption":"Grounded: calendar.cb_events (ids 108198/108201), printed actual vs survey (CNY bn). New yuan loans and total social financing both undershot; loan growth (5.2% y/y) and TSF growth (7.4% y/y) are fresh record lows, and M2 slowed to 8.0% (survey 8.5%). The credit miss compounds Tuesday's Q2 GDP miss (4.3%) and pulled the desks to trim FY forecasts and price a late-July Politburo policy pivot.","series":[{"name":"Actual (CNY bn)","color":"#2b5a86","points":[["New yuan loans",1610],["Total social financing",3360]]},{"name":"Survey (CNY bn)","color":"#b5761f","points":[["New yuan loans",2000],["Total social financing",3770]]}]}
```

---

## The day in brief

The soft print that resolved the hike scare on Tuesday got its confirmation on Wednesday. **June PPI fell −0.3% m/m** (survey 0%, forecast +0.1%; prior revised down from 1.1% to 0.6%®) on a 6.4% drop in energy, and **core PPI rose just +0.2%** (survey 0.4%, with May's core revised 0.4%→0.1%®), core YoY 4.7% vs a 5.2% survey (`cb_events` 60972-60979). Stacked on Tuesday's flat core CPI, the PCE-relevant details fix the June core-PCE nowcast in a tight ~0.17-0.19% band — GS 0.17% (YoY 3.32%), MS 0.17%, Citi 0.18% (lowered from 0.21%), Barclays 0.19% — with JPM the sole outlier, *raising* its tracking to 0.202% because the PPI services that feed PCE ran a touch firmer, and warning it is "still not mission accomplished on inflation" (18787). Citi's read is the cleanest: the softest core-PCE since March 2025, "cool enough to take the potential for a July rate hike off the table," with more subdued summer data expected to "price out the chance of hikes altogether" and softer labour data starting to "shift risks back toward cuts" (18757). ANZ marks OIS July-hike odds at ~15%, down from ~45% pre-CPI (18597). The **Beige Book** described "slight to moderate" growth with prices rising "at the same or slower pace," and Chairman **Warsh**, on his Senate day, argued AI is "structurally disinflationary" — while Governors Cook and NY Fed's Williams kept a vigilant line (UBS 18864/18865).

The **Bank of Canada held at 2.25%**, as every house expected, but the tone turned more constructive: the statement noted "clear signs that economic growth has resumed," the MPR cut the 2026 Q4/Q4 GDP forecast 0.4pp to 1.4% while calling the outlook "broadly unchanged," and Macklem dropped the June scenario of consecutive hikes (keeping it alive only if oil stays elevated). The read is unanimous — on hold through 2026 (GS/JPM/UBS/Nomura), HSBC and UBS not seeing a hike until H2-2027 — against a market still pricing ~50bp of hikes by mid-2027 (HSBC 18822). The dollar stayed soft into all of this (**GBP +1.03%**, NZD +0.64%, AUD +0.44%, EUR +0.35% DoD, `FX.fact_fx_rate`), US/UK/CA front-ends fell further, and the Asia-Pacific 2y curves that had backed up on Tuesday's pre-CPI Asian close now **rallied on the relief** — NZ −9.2bp, PH −7.4bp, HK −5.8bp — exactly the reversal yesterday's edition flagged as pending. Australia was the hawkish exception (AONIA +3.2bp) after Assistant Governor Hunter said higher unemployment may be needed to return inflation to target.

In Asia the gravity is **China**. **June credit missed hard** — new yuan loans CNY1,610bn against a CNY2,000bn survey (weakest June since 2021), loan growth 5.2% y/y and total social financing 7.4%, both fresh record lows, M2 8.0% vs 8.5% (`cb_events` 108198-108201) — compounding Tuesday's Q2 GDP miss (4.3%, weakest sequential quarter since 2022). The desks trimmed full-year forecasts (Citi and MS to 4.6%, JPM cut its year-end loan/TSF growth) and turned to policy: Citi expects a 10bp PBoC cut "as soon as July" and a late-July Politburo pivot (18647), UBS frames the weak print as "good news for the market" because it raises the odds of a meaningful policy response (18632), while JPM read the 2Q MPC as showing "no urgency for near-term easing" and pushed its low-conviction cut call from Q3 to Q4 (18719). Japan's long end got temporary relief on an "extraordinarily strong" 20y auction and a barrage of government verbal intervention — BNP called off its intended long 10s20s box (the 20y richened past its target before entry) and SocGen booked term-premium trades, both flagging the relief as unlikely to last; the consumption-tax-cut probability fell (BNP 18646, SocGen 18630). June core machine orders collapsed −12.4% m/m (survey −4.2%), a volatile May-activity pullback. US retail sales (today) and the BoK (+25bp expected, outside the universe) close out the live calendar.

---

## Deltas *(SYN — lead with what changed)*

The Wednesday US session (post-PPI, post-BoC) and the fresh 07-15/07-16 flow drive today's read (~286 in-window reports swept and deep-read — structured `dim_report` window filters across all vendors unioned with the Outlook 13-folder taxonomy and per-theme Qdrant sweeps). **US June PPI, the BoC decision + MPR + presser, China June credit + activity, Japan core machine orders + tertiary index, Korea unemployment and NZ card spending are all PRINTED** and grounded to `cb_events` rows. **US retail sales (today) and the BoK decision (today, outside universe) are the remaining forward events.** No BBG chat transcript exists for 2026-07-16 — noted, not blocking.

1. **US June PPI prints SOFT — the disinflation one-two confirmed; core-PCE nowcast ~0.17-0.19% (GS 18770, MS 18798, Citi 18757/18758, JPM 18787, Barclays 18750, Nomura 18832, SocGen 18863).** Headline −0.3% m/m (survey 0%), core +0.2% (survey 0.4%, May core revised down to 0.1%®), core YoY 4.7%. Every house pins core PCE at 0.17-0.19% except JPM, which *raised* its tracking to 0.20% on firmer PPI services. Read: July hike off the table, Fed on hold for the summer. **Supersedes the 07-15 "PPI forward" line.** (FACT print + VIEW — 60972-60979 / house cluster)
2. **Bank of Canada HELD at 2.25% — more optimistic tone, on-hold-through-2026 now unanimous (GS 18819, JPM 18828, HSBC 18822, UBS 18834, Nomura 18862).** Held as expected; MPR cut 2026 Q4/Q4 GDP to 1.4% but called the outlook "broadly unchanged"; Macklem dropped the consecutive-hike scenario (kept alive only on oil) and returned to "policy is appropriate." Nomura read it as "modestly hawkish" on the growth upgrade; all houses stay on hold vs a market pricing ~50bp of hikes by mid-2027. CAD +0.14% DoD, CORRA 2y −4.9bp. **Supersedes the 07-15 forward BoC decision.** (FACT print + VIEW — 60980 / house cluster)
3. **China June credit MISSED — loan growth and TSF at record lows; the desks trim forecasts and price a policy pivot (JPM 18719, Nomura 18723, Citi 18647/18763, UBS 18632, MS 18626, DB 18605, HSBC 18707, Barclays 18678).** New yuan loans CNY1,610bn (survey 2,000bn), loan growth 5.2% and TSF 7.4% both record lows, M2 8.0%. Citi/MS trim FY GDP to 4.6%; JPM cut year-end loan/TSF growth and pushed its cut call to Q4. **Split on PBoC easing: Citi sees a 10bp cut "as soon as July"; JPM "no urgency," pushed to Q4; UBS expects a policy-tone pivot at the late-July Politburo.** Compounds the 07-15 Q2 GDP miss (4.3%). (FACT print + VIEW — 108198-108201 / 60929-60935 / house cluster)
4. **The dollar kept weakening and the Asia-Pacific front-ends rallied on the relief (`FX.fact_fx_rate` / `rates.fact_observation`).** GBP +1.03% (ahead of today's UK GDP), NZD +0.64%, AUD +0.44%, EUR +0.35%; US/UK/CA 2y −4-5bp. The Asia curves that backed up on Tuesday's pre-CPI Asian close reversed: NZ 2y −9.2bp, PH −7.4bp, HK −5.8bp, SG −3.5bp. **Supersedes the 07-15 "soft-CPI relief lands 07-15" pending note — it landed.** (PRICING — IMDR market layers)
5. **Japan's long end got temporary relief on a strong 20y auction + government verbal intervention; BNP and SocGen booked/pulled their long-end trades (BNP 18646, SocGen 18630).** The 20y auction printed ~2bp through the market with zero tail; the 10s20s box richened past BNP's take-profit before it could enter, so BNP called off the trade. SocGen took profit on term-premium expressions, put the "policy put" at 2.90% in 10s, and now sees "much lower likelihood of consumption tax cuts." TONAR 2y +0.6bp / 10y +1.3bp (relief already priced). **Supersedes the 07-15 "long end richening on GPIF repatriation" frame.** (VIEW — 18646/18630)
6. **Warsh (Senate, Day 2): "AI structurally disinflationary"; Beige Book "slight to moderate," prices slower (UBS 18864/18865).** Warsh downplayed near-term price rises as a level shift and leaned on AI's longer-run disinflation; Cook "prepared to act if I don't see disinflation soon," Williams sees the current stance returning inflation to target. Empire manufacturing jumped to 15.6 (survey 9.2), prices-paid/received both fell (JPM 18788). (FACT/official + VIEW — 60998 / house cluster)
7. **New Zealand: HSBC opens a more-dovish RBNZ view (100bp of hikes by end-2027 vs market 135bp) on the missing housing wealth effect (HSBC 18821).** HSBC sees the growth upswing proceeding "without housing" (prices −16% from the 2021 peak, no wealth effect), so a less-aggressive hiking phase than the market — against ANZ's Sep+Oct and UBS's Sep+Dec. Card spending fell −1.4% m/m (`cb_events` 108259). NZD +0.64%, NZIONA 2y −9.2bp. Q2 CPI 21-Jul the arbiter. (Survey/FACT + VIEW — 108259 / 18821)
8. **Australia: Assistant Governor Hunter says higher unemployment may be needed — door open to tightening; AONIA the hawkish exception (ANZ 18597/18342).** Hunter's remark ("higher unemployment may be needed to return inflation to target") kept the door open to further RBA tightening; ANZ holds its short-AUD-rates / paid Dec-26 RBA OIS. AONIA 2y +3.2bp / 10y +3.3bp — the only universe curve that backed up. Q2 CPI 29-Jul. (VIEW — 18597/18342)
9. **India: ANZ decodes the "core inflation puzzle" — refined core subdued at 2.5%, lets the MPC wait but the risk factors are shifting (ANZ 18641); unemployment steady at 5.5% (Barclays 18753).** Refined core CPI (ex-precious-metals) is near the bottom of the 2-6% band (record-low 2.1% in Q1) despite 7%+ growth — investment-led growth the driver — but those factors are turning, so ANZ warns caution; the weak core still lets the MPC wait on US rates/oil/weather. Unemployment 5.5% (survey 5.4%). INR flat (−0.05%). (FACT + VIEW — 60961 / 18641/18753)
10. **UK: UBS sees 20bp of gilt-rally room if the Autumn Budget sticks to the fiscal rules; Burnham confirmed Friday (UBS 18734, Barclays 18599).** ~20bp of fiscal risk premium is priced into 10y gilts; a rule-compliant Budget unwinds it. UBS was stopped out of long BoE Dec'26 on oil but still sees the next BoE move as a cut; stays long 2s10s. GBP +1.03% (universe-leading), SONIA 2y −4.3bp. UK GDP prints today. (VIEW — 18734/18599)

---

## 4. Cross-asset moves matrix (DoD)

Day-over-day = **(07-15 last-tick) − (07-14 last-tick)**, last tick = max `ts` within the calendar day, for **FX (spot, `FX.fact_fx_rate`)** and **2y/10y swap/OIS par (`rates.fact_observation`)**. **Equity, VIX and commodities are stale to 07-14** at compile (no fresh 07-15 tick), so the equity column carries the 07-14 close (DoD 07-13→07-14) and is flagged. **Timing caveat:** US/UK/CA/EU curves' 07-15 last tick is their EOD, *after* the 08:30 PPI and the 13:30 BoC; Asia-Pacific curves' 07-15 last tick is the Asian close, which now captures the soft-CPI relief from the prior US session (the reversal of Tuesday's pre-print backup) but not the 07-15 US PPI/BoC. FX % is **local vs USD** (positive = local stronger). `fact_bond_yield` is EMPTY — rates are swap/OIS.

| Country | FX vs USD (DoD %) | 2y (DoD bp) | 10y (DoD bp) | Equity (07-14, stale) | One-line read |
|---|---|---|---|---|---|
| United States | EUR **+0.35%** | SOFR **−4.5** | SOFR **−2.6** | S&P 500 +0.38% / Nasdaq 100 +1.10% | **Soft PPI confirms the one-two.** Front-end fell further; core-PCE nowcast ~0.17-0.19%; July hike off the table. Beige Book "slight to moderate"; Warsh "AI structurally disinflationary." Retail sales today. |
| Canada | CAD **+0.14%** | CORRA **−4.9** | CORRA **−3.7** | n/l | **BoC HELD 2.25%.** More optimistic tone, MPR growth cut but "broadly unchanged"; Macklem dropped consecutive-hike language. On-hold-2026 unanimous vs market's ~50bp of mid-2027 hikes. CAD firmer, front rallied. |
| China / Hong Kong | CNH **+0.06%** / HKD **−0.02%** | HIBOR **−5.8** | HIBOR **0.0** | HSI +0.52% / HSCE +0.46% / HSTECH +0.06% | **June credit MISSED** — loans/TSF record lows, compounding the Q2 GDP miss (4.3%). Desks trim FY to 4.6%, price a Politburo pivot. HK front rallied on the soft-CPI relief; CNH ~flat. |
| United Kingdom | GBP **+1.03%** | SONIA **−4.3** | SONIA **−4.0** | FTSE 100 +0.30% (07-14) | **Sterling led the universe** ahead of today's GDP. UBS sees 20bp of gilt-rally room on a rule-compliant Budget (Burnham confirmed Fri); next BoE move a cut. Front-end rallied with the US. |
| New Zealand | NZD **+0.64%** | NZIONA **−9.2** | NZIONA **−2.8** | n/l | Kiwi second-firmest; front-end rallied hardest in the universe on the relief. HSBC more dovish (100bp hikes by end-2027 vs mkt 135bp, no housing wealth effect); card spending −1.4%. Q2 CPI 21-Jul. |
| Japan | JPY **+0.01%** | TONAR **+0.6** | TONAR **+1.3** | Nikkei +0.74% / TOPIX +0.79% | Long end nudged up as the verbal-intervention relief was priced; strong 20y auction; BNP called off long 10s20s box, SocGen booked term-premium trades; consumption-tax-cut odds fell. Core machine orders −12.4%. |
| Australia | AUD **+0.44%** | AONIA **+3.2** | AONIA **+3.3** | ASX 200 flat (stale) | **The hawkish exception** — AONIA backed up after Hunter said higher unemployment may be needed. AUD firm; ANZ stays short AUD rates. Q2 CPI 29-Jul. |
| Indonesia | IDR **+0.27%** | JIBOR **+0.3** | JIBOR **−1.2** | n/l | IDR firmest in ASEAN on the soft USD. HSBC "big test for 2H" — stability delivered (rates up, fiscal reined in) but a growth cost; external debt $444.4bn. BI 22-Jul. |
| Singapore | SGD **+0.14%** | SORA **−3.5** | SORA **−3.3** | SIMSCI +0.31% | SGD firmer; front rallied on the relief. HSBC "SGD weaker than normal" — NEER flat, MAS FX reserves fell $4.7bn in June; slope-normalisation timing debated. MAS MPS 27-31 Jul. |
| Euro area | EUR **+0.35%** | ESTR **−1.5** | ESTR **+1.0** | Euro Stoxx 50 +0.15% / Banks +0.51% | EUR firmer with the soft USD; ESTR little changed (front slightly lower, long end nudged up). Context row for the US/UK book. |
| India | INR **−0.05%** | MIBOR **−0.8** | MIBOR **−0.4** | Nifty 50 −0.66% (07-14) | INR flat, recovered from Tuesday's −0.45%; rates edged back after the hot-prints backup. ANZ "core inflation puzzle" — refined core 2.5% lets the MPC wait; unemployment 5.5%. RBI August. |
| Philippines | PHP **+0.02%** | PHIREF **−7.4** | PHIREF **−1.2** | n/l | Peso ~flat; front rallied hard on the relief (reversing Tuesday's +11.5bp backup). No fresh domestic catalyst; remittances +2.0%. Citi's bearish-PHP roll carried. |
| Malaysia | MYR **−0.15%** | KLIBOR **+1.0** | KLIBOR **+0.5** | n/l | MYR softer; rates nudged up. **CPI (survey 2.0%) + Q2 GDP prelim (fcst 5.3%) both TODAY (17-Jul)** — the fork. Quiet in-window. |
| Thailand | THB **−0.24%** | THOR **−1.0** | THOR **−1.7** | SET −0.16% (07-14) | THB the universe laggard; rates edged lower. No domestic catalyst; Citi's booked long USD/THB carried; BoT on hold. |

*Oil/vol footnote (stale to 07-14):* WTI **$79.89** (`commodities.fact_spot`, 07-14, **+1.4%** from $78.78 on 07-13 — the Hormuz-blockade level holding); Brent ~**$83-84** remains sell-side (GS/DB); the BoC's MPR assumed US$70-75/bbl, ~$10 below spot (JPM 18828). Gold **4,055** (07-14, +1.34% DoD, `fact_spot`); silver 59.25 (+1.87%). **VIX** 16.5 (07-14, −0.66 DoD); VXN 26.28, VVIX 93.53, VIX9D 13.46. **DXY** not loaded (agent proxy via crosses). **Equity flag:** `fact_index_level` fresh only to **07-14** (no 07-15 tick), so the equity column repeats the 07-14 close — MSCI Taiwan −1.42% the regional laggard, KOSPI 200 +1.25%. `fact_bond_yield` EMPTY — cash govt yields not loaded; rates are swap/OIS. **Rows ordered by event proximity + move magnitude.**

---

## 5. CB / macro dashboard  *(FACT — `calendar.cb_events`)*

One row per covered country. Policy rate = last decided rate on a verified decision row; last move and next event verified against `cb_events`. The BoC held today (2.25%, resolved). US PPI printed soft; China credit printed a miss. Korea's BoK is a well-flagged +25bp Thursday (outside the universe). US retail sales, UK GDP, and the BoK are today's forward events.

| Country | Policy rate | Last move (verified) | Next scheduled | Bias / key issue |
|---|---|---|---|---|
| United States | **3.75%** (3.5-3.75 range) | Held 2026-06-17 (dots up) | **Retail sales 16-Jul; FOMC 29-Jul** | **June PPI SOFT (−0.3% m/m / core +0.2%)** — the disinflation one-two; core-PCE nowcast ~0.17-0.19% (JPM outlier 0.20%). July hike off the table; hold for the summer. Warsh "AI structurally disinflationary" |
| Canada | **2.25%** | **Held 2026-07-15 (today) + MPR + presser** | Next BoC meeting (post-window) | **HELD as expected.** More optimistic tone; MPR Q4/Q4 GDP cut to 1.4% but "broadly unchanged"; consecutive-hike language dropped. On-hold-2026 unanimous vs market ~50bp of mid-2027 hikes |
| China | LPR / 7d OMO | — | Politburo (late-Jul); LPR fixing | **June credit MISSED** — loans 5.2% / TSF 7.4% both record lows, compounding the Q2 GDP miss (4.3%). FY trimmed to 4.6% (Citi/MS); split on PBoC easing (Citi 10bp July vs JPM Q4); policy-tone pivot the Politburo watch |
| United Kingdom | **3.75%** | Held 2026-06-18 (7/2/0) | **GDP 16-Jul (today)**; MPR 30-Jul | GBP led the universe (+1.03%); SONIA rallied with the US. UBS: 20bp of gilt-rally room on a rule-compliant Autumn Budget; next BoE move a cut; Burnham confirmed Friday |
| New Zealand | **2.50%** | Hiked +25bp 2026-07-08 | **Q2 CPI 21-Jul**; 2-Sep MPS | Front-end rallied hardest (−9.2bp). HSBC more dovish (100bp by end-2027 vs mkt 135bp, no housing wealth effect) vs ANZ Sep+Oct / UBS Sep+Dec; card spending −1.4%; NZD firm |
| Japan | **1.00%** | Hiked +25bp 2026-06-16 | (post-window) | Long end found temporary relief (strong 20y auction + verbal intervention); "policy put" 2.90% 10s (SocGen); BNP called off long 10s20s box; consumption-tax-cut odds fell; core machine orders −12.4% |
| Australia | **4.35%** | Held 2026-06-16 | **Q2 CPI 29-Jul**; 11-Aug | **The hawkish exception** — AONIA +3.2bp after Hunter said higher unemployment may be needed. ANZ short AUD rates (paid Dec-26 RBA OIS); labour force 23-Jul |
| Indonesia | **5.75%** | Hiked +25bp 2026-06-18 | **BI 22-Jul** | IDR firmest in ASEAN. HSBC "big test for 2H" — stability delivered (rates up, fiscal reined in, underlying inflation down) but a growth cost; external debt $444.4bn |
| Singapore | MAS S\$NEER band | — (band) | **MAS MPS 27–31 Jul window** | HSBC "SGD weaker than normal" — NEER flat, MAS FX reserves fell $4.7bn in June, slope-normalisation timing debated (inflation soft, growth robust); SORA rallied |
| India | **5.25%** | Held 2026-06-05 | RBI August | ANZ "core inflation puzzle" — refined core 2.5% (near band floor) lets the MPC wait; risk factors (US rates/oil/weather) shifting; unemployment 5.5%; INR flat |
| Hong Kong | USD peg / LAF | — (linked to Fed) | **Unemployment 17-Jul** | HKD flat on peg; HIBOR 2y −5.8bp as the soft-CPI relief eased the Fed-linked pressure; HK equities tracked the China tape |
| Philippines | **4.75%** | Hiked +25bp 2026-06-18 | (post-window) | PHIREF front −7.4bp (relief reversed Tuesday's backup); remittances +2.0%; Citi's bearish-PHP roll carried; StanC 5.00% Aug carried |
| Malaysia | **2.75%** | Held 2026-07-09 | **CPI + Q2 GDP prelim 17-Jul** | CPI survey 2.0%, GDP prelim fcst 5.3% — today's double print the fork; MYR softer; quiet in-window |
| Thailand | **1.00%** | Held 2026-06-24 | (post-window) | THB the universe laggard (−0.24%); rates edged lower; Citi's booked long USD/THB carried; BoT on hold both years (StanC) |

**SYN — state of the world:** the marquee resolved dovish on Tuesday and got confirmed on Wednesday. June PPI came soft in the details that matter for PCE, so the core-PCE nowcast sits in a tight ~0.17-0.19% band and the entire desk now treats the July hike as off the table and the Fed as parked for the summer — Warsh's "AI is structurally disinflationary" and a Beige Book of "slight to moderate" growth with slower prices reinforce the tone. The lone dissent is JPM, which nudged its core-PCE tracking *up* to 0.20% and keeps warning it is "not mission accomplished." The Bank of Canada held and leaned a shade more optimistic without opening the door to hikes, so the North-American front-ends and the dollar both drifted lower, and the Asia-Pacific curves that had backed up on Tuesday's pre-CPI Asian close finally caught the relief — the clearest single-session move being a broad Asia front-end rally (NZ, PH, HK, SG). The one hawkish exception is Australia, where an official floated higher unemployment as the price of returning inflation to target. With the US and Canada resolved, the live risk is China: a June credit miss on top of the Q2 GDP miss has the desks trimming full-year growth and arguing over whether the PBoC cuts in July (Citi) or Q4 (JPM), with a late-July Politburo the pivot everyone is watching. Japan's long end bought a reprieve on a strong auction and official jawboning that the desks themselves call temporary. The soft US data are the tide; China's policy response and today's US retail sales are the next currents.

---

## 6. Themes in play + open questions

**Themes (who's talking + the number), stated neutrally:**
- **The disinflation one-two — CPI then PPI.** Core PPI +0.2% (survey 0.4%), headline −0.3% on energy −6.4%; core-PCE nowcast GS 0.17% / MS 0.17% / Citi 0.18% / Barclays 0.19%, JPM the outlier up at 0.20% ("not mission accomplished"). Citi (18757): softest core PCE since March 2025, "price out hikes altogether over the summer," softer labour "shift risks back toward cuts." The debate is pace of disinflation and September's ~25bp downward PCE revision, not direction.
- **China: the credit miss forces the policy question.** New loans CNY1,610bn (survey 2,000bn), loan growth 5.2% / TSF 7.4% record lows on top of the Q2 GDP miss (4.3%). Citi (18647): 10bp PBoC cut "as soon as July," Politburo pivot. JPM (18719): "no urgency," cut pushed to Q4. UBS (18632): the weak print is "good news" — it raises the odds of a policy-tone shift. Nomura (18723): "the AI economy cannot cure China's economic woes"; Li Qiang urged "countercyclical" support. The split is timing/magnitude of easing.
- **The Bank of Canada hold as the DM template.** Held 2.25%, more optimistic tone, MPR growth cut but "broadly unchanged," consecutive-hike language dropped. GS/JPM/UBS/Nomura on-hold-2026; HSBC/UBS no hike until H2-2027. The tension: unanimous house holds vs a market pricing ~50bp of hikes by mid-2027 on the oil tail.
- **Japan's long end — verbal intervention buys temporary relief.** Strong 20y auction (2bp through, zero tail); SocGen (18630) puts the "policy put" at 2.90% 10s and books term-premium trades; BNP (18646) calls off its long 10s20s box (richened past target) but won't short yet (BoJ's higher SLF charge, chronic current-issue richness). Consumption-tax-cut probability fell. The read: the relief is real but the desks call it unlikely to last.
- **The NZ hike path — a three-way house split.** ANZ Sep+Oct (18030, carried), UBS Sep+Dec (18107, carried), HSBC now the dove — 100bp by end-2027 vs the market's 135bp, on the missing housing wealth effect (18821). Q2 CPI 21-Jul the arbiter.
- **Australia — the hawkish universe outlier.** Assistant Governor Hunter: higher unemployment may be needed to return inflation to target (ANZ 18597); AONIA the only universe curve that backed up. ANZ stays short AUD rates. Q2 CPI 29-Jul.
- **The dollar's continued sag.** GBP +1.03%, NZD +0.64%, AUD +0.44%, EUR +0.35% DoD — the soft CPI/PPI kept the dollar on the back foot into the BoC. Carried tension (Nomura vs Citi): stretched long-USD positioning that struggles to rally vs residual USD-asymmetry on the oil/Middle-East tail.
- **Oil / Hormuz — the persistent two-sided tail.** WTI $79.89 (holding the blockade level); the BoC's MPR ran ~$10/bbl below spot (JPM), HSBC flags the upside-inflation risk. Still the shared falsifier under the soft-data relief.

**Open questions into the next sessions (neutral — the disagreement + what resolves it):**
1. **US retail sales (today)** — survey +0.2% m/m / control +0.5% against a 0.9% prior; a soft control-group print firms the on-hold read, a hot one revives the two-sided debate into the 29-Jul FOMC.
2. **China policy timing** — Citi's 10bp PBoC cut "as soon as July" vs JPM's "no urgency / Q4" vs UBS's "policy-tone pivot"; the late-July Politburo is the resolver, with the size of any fiscal/monetary step still open after the credit miss.
3. **The core-PCE divergence** — the ~0.17-0.19% consensus vs JPM's 0.20% and the September ~25bp downward annual revision (Citi); how firm core-services-ex-shelter proves over the summer.
4. **New Zealand's hike count** — ANZ (+50bp Sep+Oct) vs UBS (+50bp Sep+Dec) vs HSBC (100bp total by end-2027, below market); the 21-Jul Q2 CPI decides.
5. **The BoC vs the market** — unanimous house holds through 2026 vs a market pricing ~50bp of hikes by mid-2027; the oil path and the USMCA renegotiation are the swing factors.
6. **Japan's long end** — is the auction/verbal-intervention relief durable, or (BNP/SocGen) a reprieve that fades once August supply lands and the "loose monetary + fiscal" drivers reassert; the consumption-tax-cut debate is the fiscal wildcard.
7. **BoK (today, outside universe)** — a well-flagged +25bp to 2.75%; relevant for KRW and the Asia-rates read.

---

## 7. Calendar — releases + CB events with rate relevance  *(FACT — `cb_events`; pure calendar, no view)*

Consensus (`survey`/`forecast`) shown where present; `actual` shown only where the row carries one. `®` = prior revised. US PPI, the BoC decision, China credit + activity, Japan machine orders/tertiary, Korea unemployment and NZ card spending all PRINTED (`cb_events` actual rows). US retail sales, UK GDP and the BoK are today's forward events.

| Date | Country | Event | Consensus | Prior | Actual |
|---|---|---|---|---|---|
| **07-15** | **US** | **PPI m/m; y/y** | **0% / 6.2%** | **0.6%® / 6%®** | **−0.3% / 5.5% — PRINTED SOFT (60972/60979)** |
| **07-15** | **US** | **Core PPI m/m; y/y** | **0.4% / 5.2%** | **0.1%® / 4.6%®** | **0.2% / 4.7% — PRINTED SOFT (60973/60975)** |
| 07-15 | US | PPI ex food/energy/trade m/m; y/y | 0.3% / — | 0.8% / 5.1% | **0.1% / 5.1% — PRINTED (60977/60978)** |
| 07-15 | US | Empire manufacturing; Beige Book | 9.2 / — | 5.7 / — | **15.6 — PRINTED (per flow, JPM 18788); Beige "slight to moderate" (60998)** |
| **07-15** | **CA** | **Bank of Canada decision + MPR + presser** | **hold 2.25%** | **2.25%** | **2.25% — HELD (60980); on hold, more optimistic tone** |
| **07-15** | **CN** | **New yuan loans; TSF; M2 y/y** | **CNY2,000B / 3,770B / 8.5%** | **CNY520B / 2,030B / 8.6%** | **CNY1,610B / 3,360B / 8.0% — PRINTED MISS (108198/108201/108199)** |
| 07-15 | CN | Loan growth y/y (outstanding) | 5.4% | 5.5% | **5.2% — record low (108200)** |
| 07-15 | JP | Core machine orders m/m; y/y | −4.2% / 12.3% | 8.67% / 15.6% | **−12.4% / −1.9% — PRINTED SOFT (41368/41369)** |
| 07-15 | JP | Tertiary industry index m/m | 0.4% | 0.8%® | **1.1% — PRINTED (60937)** |
| 07-15 | KR | Unemployment rate SA | 2.8% | 2.8% | **2.7% — PRINTED (41371, context)** |
| 07-15 | NZ | Card spending retail m/m; total m/m | — | 1.7% (1.6®) / 2.2% (1.9®) | **−1.4% / −1.2% — PRINTED SOFT (108259/108260)** |
| 07-15 | IN | Unemployment rate | 5.4% | 5.5% | **5.5% — PRINTED (60961)** |
| 07-15 | ID | External debt ($bn) | — | 439.8 (440.2®) | **444.4 — PRINTED (108249)** |
| 07-15 | PH | Overseas remittances y/y | 2.1% | 2.0% | **2.0% — PRINTED (41372)** |
| **07-16** | **US** | **Retail sales m/m; control group; ex-auto** | **0.2% / 0.5% / −0.1%** | **0.9% / 0.7% / 0.8%** | forward |
| 07-16 | US | Initial jobless claims; continuing | 217K / 1,820K | 215K / 1,814K | forward |
| 07-16 | US | Philadelphia Fed business outlook | 10.3 | 10.3 | forward |
| **07-16** | **UK** | **GDP m/m / y/y; IP m/m** | **0.1% / 1.4% / −0.1%** | **−0.1% / 1.2% / 0%** | forward |
| 07-16 | NZ | Food inflation y/y | 3.0% | 3.2% | forward |
| 07-16 | KR | BoK base rate | hike 2.5→2.75% | 2.5% | forward (outside universe) |
| 07-17 | MY | CPI y/y; Q2 GDP prelim y/y | 2.0% / 5.3% | 2.0% / 5.4% | forward |
| 07-17 | HK | Unemployment rate | — | 3.7% | forward |
| 07-17 | SG | Balance of trade (NODX) | $6.0B | $5.57B | forward |
| 07-17 | US | Industrial production m/m | 0.2% | 0.1% | forward |
| 07-21 | NZ | Q2 CPI | ~1.3% q/q (RBNZ) | — | forward |
| 07-22 | ID | Bank Indonesia decision | — | 5.75% | forward |
| 07-27–31 | SG | MAS MPS (window) | — | band | forward — NOT today |
| 07-29 | US/AU | FOMC; AU Q2 CPI | hold / ~0.8% q/q | 3.75% (upper) | forward — soft data eased the hike risk |

---

## 8. Cross-cutting trade-ideas table  *(VIEW — provenance-tagged, never rated)*

The daily's single trade view — what the houses are floating across the universe. Each row: the idea, the assumption it rests on, its falsifier, provenance. **Never rated** — the PM judges. Expanded in the per-country reads below.

| # | Trade | Key driver / rationale | Assumption it rests on | Falsifier | Provenance |
|---|---|---|---|---|---|
| 1 | **Citi: hold the "goldilocks-summer" tilt — Fed on hold, carry in a range, add EMFX carry** | Soft CPI + soft PPI → core PCE ~0.18%, July hike off the table; front-end & USD range-bound (carried from 07-15 rotation) | US data stay soft-ish; oil doesn't spike; front-end range-bound | A hot retail sales / PPI reversal re-lights the Fed; oil spike lifts USD | Citi 18757/18682 |
| 2 | **SocGen: receive JPY 5y5y vs paid SOFR (dv01-neutral), enter 107bp, target 125bp, stop 98bp** | Government verbal intervention + lower issuance/consumption-tax-cut risk lets JPY term premium compress vs the US near-term | The JGB relief holds short-term; positions stay reduced | The relief fades as August supply lands / BoJ turns; SOFR term premium falls faster | SocGen 18630 |
| 3 | **BNP: call off the long JGB 10s20s box (no entry) — too early to short the superlong** | The 20y auction richened the box past the take-profit before entry; chronic current-issue richness + BoJ higher SLF charge argue against shorting | The richening is not yet a durable reversal; wait for August supply | A clean consolidation signal / faster BoJ path re-cheapens the long end | BNP 18646 |
| 4 | **UBS: stay long 2s10s gilt steepeners; 20bp of gilt-rally room on a rule-compliant Autumn Budget** | ~20bp of fiscal risk premium priced into 10y gilts; a compliant Budget unwinds it; next BoE move a cut | Burnham sticks to the fiscal rules; oil/BoE don't force a re-steepening | A fiscal-rule loosening re-prices risk premium; oil extends the front-end sell-off | UBS 18734 |
| 5 | **ANZ: short AUD rates — hold paid Dec-26 RBA OIS** | RBA reaction function stays inflation-skewed (Hunter: higher unemployment may be needed); terminal underpriced | RBA stays inflation-focused; supply shocks keep the long-end high | A dovish RBA pivot / soft 29-Jul Q2 CPI / oil drops | ANZ 18342/18597 |
| 6 | **SocGen (Japan book): take profit on close rec 1y1y vs JGB futures (+3bp), receive 6m10y AUD vs JPY (+30bp), systematic short 30y (+12bp)** | Government "cloud cover" put the brakes on the behind-the-curve trades; book the gains, wait for better levels to get bearish the belly again | The relief is a tactical top; re-enter bearish later | The relief becomes durable and the belly richens further | SocGen 18630 |
| 7 | **Citi: expect a 10bp PBoC rate cut as soon as July + fiscal acceleration (China express via CNH/rates/HK)** | Q2 GDP + June credit miss force incremental policy; Politburo pivot late-July | Beijing responds to the data miss with near-term easing | Beijing holds off (JPM's "no urgency," cut in Q4); AI-export strength papers over it | Citi 18647 |
| 8 | **JPM (Indonesia, carried): MW IDR FX, MW IndoGBs, reduce UW INDONs; long INR vs PHP & IDR (RV)** | Fiscal consolidation encouraging; BI anchor vs weak seasonals; HSBC's "big 2H test" the growth risk | BI stays hawkish; FA flows improve; consolidation delivers | Fiscal slippage / FX pressure widens IndoGB risk premia; growth undershoot forces easing | JPM 18151 (carried), HSBC 18781 |
| 9 | **Citi (carried): booked long USD/THB (+82bp); rolled bearish PHP 1x1.5 call ratio 3m** | THB underperformance + FX-intervention anchor; cap PHP strength | Intervention anchors USD/THB; PHP strength capped | ME de-escalation + sharp oil drop; strong PHP inflows | Citi 18064 (carried) |
| 10 | **Nomura (carried): long EUR/INR (113), short USD/THB (32), pay Sep 5y India NDOIS, Korea Dec-1s4s steepener, pay AU3m1y vs US3m1y, short GBP/NZD** | Cross-Asia RV; each leg's local driver holds; oil contained | Each leg's local driver holds; oil contained | Oil to $100; a hawkish Fed re-steepens US; local surprises | Nomura 18221 (carried) |

**SYN — where the book tilts:** the confirming soft PPI hardened the cross-universe tilt the CPI opened — *fade-the-dollar, carry-in-a-range, Fed-on-hold*. Citi keeps its goldilocks-summer tilt (row 1); the new risk-taking is in Japan rates, where the government's jawboning and a strong 20y auction let SocGen put on a JPY-5y5y-vs-SOFR term-premium-compression trade (row 2) and book its behind-the-curve gains (row 6) while BNP steps aside from shorting the superlong (row 3) — the shared view being that the relief is real but tactical. In DM the trades lean dovish-to-market: UBS's gilt steepener into a rule-compliant Budget (row 4) and, as the hawkish counterweight, ANZ's short-AUD-rates on the RBA's inflation skew (row 5). China is expressed through the policy-pivot bet (Citi's July PBoC cut, row 7) against JPM's "no urgency." Asia EM stays a carried RV book — JPM's Indonesia MW package against HSBC's "big 2H test" (row 8), Citi's THB/PHP options (row 9) and Nomura's cross-Asia legs (row 10). The through-line: the US resolved dovish twice, so the book is short-dollar and long-carry, with oil the shared falsifier and China's policy timing the live swing factor.

---
## 9. Per-country read — A / B / C / D (the body)

Ordered by what moved this window: the US disinflation one-two (PPI) and the resolved Bank of Canada lead, then China's credit miss, Japan's long-end relief, New Zealand, Australia, India, the UK, Singapore, Indonesia, and the quiet tail (Hong Kong, Thailand, Malaysia, Philippines). Every country is read at the chunk level; quiet countries get the raised-floor A+B read grounded in the flagship daily/tape.

### United States — The second shoe drops soft: June PPI confirms the disinflation, core PCE ~0.17-0.19%

*Flagships read: GS "USA: Producer Price Index Below Expectations… Estimating 0.17% for June Core PCE" (18770) + GS Daily "benign June CPI" (18585) + GS US Daily Download (18652) + "Oil, the Fed, and AI" (18850); Citi "The Daily Update – Cool core CPI" (18682) + "PPI details benign for PCE inflation" (18757) + "June core PCE tracking 0.18%MoM after PPI" (18758) + The Global Point (18687); JPM "US: PPI moderates in June, though core PCE tracking up" (18787) + "US: July manufacturing surveys off to a good start" (18788) + US Market Intelligence Morning/Afternoon (18711/18852); MS "We forecast June core PCE at 0.17% after PPI" (18798) + "Empire Manufacturing: Strong Demand, Cooling Prices" (18800); Barclays "US Economics: June core PCE price inflation at 0.19% m/m" (18750); Nomura "First Insights — US: June PPI data suggest a benign reading" (18832); SocGen "June 2026 US PPI: Mixed Services Implies a Soft June Core PCE" (18863); DB "US Economic Notes: June inflation recap" (18848); UBS US Daily Data Recap (18833) + "Beige Book — slow and steady" (18864) + "Warsh: AI structurally disinflationary" (18865).*

**A · Themes in play**

| Rank | Theme | Assets | Banks talking | Why it matters to the PM |
|---|---|---|---|---|
| 1 | June PPI SOFT — the disinflation one-two after CPI | Rates, USD | GS, JPM, Citi, MS, Barclays, Nomura, SocGen, DB, UBS | Confirms the soft CPI; core-PCE nowcast ~0.17-0.19%; July hike off the table |
| 2 | Core-PCE nowcast dispersion (0.17-0.20%) | Rates | GS/MS 0.17, Citi 0.18, Barclays 0.19, JPM 0.20 | The one number the Fed watches; JPM the hawkish outlier |
| 3 | Warsh Senate Day 2 — "AI structurally disinflationary" | Rates | UBS | Chair leans structurally dovish; Cook/Williams keep a vigilant line |
| 4 | Beige Book "slight to moderate"; Empire jumped | Rates, equities | UBS, JPM, MS | Prices slower across all districts; manufacturing surveys firm |

**B · The "why"** The soft core CPI got its confirmation from the soft PPI. **June PPI fell −0.3% m/m** (`cb_events` 60972; survey 0%, forecast +0.1%, and — importantly — May's headline was revised *down* from 1.1% to 0.6%®) on a 6.4% energy decline; **core PPI rose just +0.2%** (60973; survey 0.4%, with May's core revised 0.4%→0.1%®) and PPI ex-food/energy/trade +0.1% (60977). Core PPI YoY printed 4.7% (60975; survey 5.2%). The move that matters is in the PCE-relevant details, and the desks converged tightly: **GS marks core PCE at 0.17%** m/m (YoY 3.32%, down from its 0.18% pre-PPI estimate; headline PCE −0.07%, market-based core 0.19%, trimmed mean 0.14% — 18770), **MS 0.17%** (18798), **Citi 0.18%** (lowered from 0.21% — "the softest monthly increase in core PCE since March 2025… should be cool enough to take the potential for a July rate hike off the table," and it expects further summer softening to "price out the chance of hikes altogether," with softer labour data "starting to shift risks back toward cuts," 18757/18758), **Barclays 0.19%** (18750). The one dissenter is **JPM (18787):** it *raised* its core-PCE tracking from 0.168% to **0.202%** because the PPI services feeding PCE ran firmer than its post-CPI assumptions — YoY 3.3-3.4%, 3m annualised 3.1% — and it paraphrased Warsh that this is "still not mission accomplished on inflation." ANZ marks OIS July-hike odds at ~15% vs ~45% pre-CPI (18597). The **Beige Book** reported "slight to moderate" growth in 11 of 12 districts with prices rising "at the same or slower pace… across all districts," a bifurcated consumer trading down to value, and more visible AI adoption (UBS 18864). **Empire manufacturing** jumped to 15.6 (survey 9.2), pushing the ISM-weighted composite to 57.5, with prices-paid (52.3 from 61.0) and prices-received (27.6 from 31.4) both moderating (JPM 18788, MS 18800). The tape: **SOFR 2y −4.5bp / 10y −2.6bp** (the front-end kept rallying, US EOD is post-PPI/BoC), the dollar broadly softer (EUR +0.35%, GBP +1.03%), gold holding 4,055, VIX 16.5.

**B2 · Americas timeline — PPI within-window (official voice vs sell-side read, 15→16 Jul)**

The layers kept separate: **official** (the BLS release + Fed communications = FACT / official voice) vs **sell-side** (desk interpretation = VIEW). The sequence is the point — a soft official print that confirmed Tuesday's CPI, then an official-voice reaction that leaned structurally dovish.

| When (within-window) | Official voice (FACT / official) | Sell-side read (VIEW) |
|---|---|---|
| **15 Jul 08:30 ET — the print** | **BLS June PPI release** (`cb_events` 60972-60979): headline **−0.3% m/m / 5.5% y/y** (May revised down to +0.6%®); **core +0.2% m/m / 4.7% y/y** (May core revised to +0.1%®); ex-food/energy/trade +0.1%. Energy −6.4%. Empire manufacturing 15.6 (prior 5.7). | Unanimous "benign," with a tight nowcast spread. **GS (18770):** core PCE **0.17%** (YoY 3.32%). **MS (18798):** **0.17%**. **Citi (18757):** lowered to **0.18%**, "softest since March 2025… takes the July hike off the table," expects the summer to "price out hikes altogether." **Barclays (18750):** **0.19%**. **JPM (18787):** the outlier — *raised* to **0.202%** on firmer PPI services, "still not mission accomplished." **Nomura (18832):** "a benign reading." **SocGen (18863):** "mixed services implies a soft June core PCE." |
| **15 Jul — official reaction (Fed comms)** | **Chair Warsh**, Senate testimony Day 2 (`cb_events` context; UBS 18865), verbatim: *"Do I believe that the productivity improvement over time will be structurally disinflationary? I do… everything technology touches ultimately gets cheaper."* He downplayed near-term price rises as a level shift. **Gov. Cook / NY Fed Williams** also spoke: Cook "prepared to act if I don't see disinflation soon"; Williams sees the current stance returning inflation to target. **Fed Beige Book** (`cb_events` 60998 / 20376): "slight to moderate" growth, prices "same or slower pace." | **UBS (18865):** the "most policy-relevant part" was Warsh's AI-disinflation thesis — a theme UBS "has been writing he would embrace." The other speakers' vigilance kept a two-sided tone, but no house read the print as a head-fake. **UBS (18864):** Beige Book "slow and steady," a bifurcated consumer, prices decelerating — corroborates the disinflation. **DB (18848):** June inflation recap — "getting a break." |
| **16 Jul — next official checkpoint (in-window)** | **June advance retail sales + initial claims** (`cb_events` 65717/65718): survey retail **+0.2% m/m** (control +0.5%, ex-auto −0.1%; prior 0.9%), claims 217K. **Philadelphia Fed** business outlook (survey 10.3). All forward at compile. | Desks watch the control group for the consumer read into the 29-Jul FOMC: a soft control-group print firms the on-hold call; Citi (18757) already flags "softer labour market data starting to shift risks back toward cuts." |

*Next catalyst pointer (one line, in-window): the 16-Jul retail sales + claims are the day's remaining official checkpoint before the 29-Jul FOMC — a soft control group cements the on-hold-for-the-summer read.*

**C · Consensus views (≥2 independent banks)**

| Theme | Banks | Shared claim | Evidence cited | What consensus is missing |
|---|---|---|---|---|
| June PPI is soft and confirms the disinflation | GS, MS, Citi, Barclays, Nomura, SocGen, DB | Core PPI +0.2%, headline −0.3% on energy; core PCE ~0.17-0.19% | May PPI revised down; PCE-relevant services benign | JPM's 0.20% tracking-up dissent; how firm core services prove over the summer |
| The Fed can hold for the summer; July hike off the table | GS, Citi, MS, Barclays, UBS | Soft CPI+PPI, core PCE 0.2% handle, July-hike odds ~15% | Core-PCE nowcast; Empire prices moderating; Warsh's AI-disinflation line | Whether retail sales (today) re-firms the two-sided debate |

**D · Differentiated / unique views**

| Bank | Asset | The view | Why it's different | Hidden assumption | Falsifier |
|---|---|---|---|---|---|
| JPM | Rates | Core-PCE tracking *up* to 0.202% — PPI services firmer; "not mission accomplished" | The only house that raised its nowcast after PPI; least willing to extrapolate the softness | Core-services-ex-shelter softness reverses; goods firm | A second soft core print confirms the summer disinflation |
| Citi | Rates/FX | Softest core PCE since March 2025; summer to "price out hikes altogether," risks "shift back toward cuts" | The most dovish read — from hold to a cut-risk narrative | Labour data soften; oil doesn't spike | A hot retail sales / labour re-acceleration revives the hike case |
| UBS | Rates | Warsh's AI-disinflation thesis is the policy signal, not the near-term print | Reads the Chair's structural view over the monthly data | AI productivity gains show up in supply / prices over time | Near-term price rises broaden rather than fade |

Trade rows: **#1**. **DEPTH:** US `econ.fact_indicator` deep (193 active). June PPI is FACT in `cb_events` (60972-60979); the verified policy anchor is the 2026-06-17 FOMC hold + dots. **Flags:** retail sales + claims 16-Jul forward; core-PCE figures are sell-side nowcasts (VIEW); WTI $79.89 (07-14, `fact_spot`), Brent ~$83-84 sell-side; DXY not loaded; `fact_bond_yield` EMPTY.

### Canada — BoC holds at 2.25%; a more optimistic tone, but on-hold-through-2026 unanimous

*Flagships read: GS "BoC Remains on Hold and Characterizes Policy Stance as 'Appropriate'" (18819) + "GS FX Morning Notes: CAD into the BoC" (18705); JPM "Bank of Canada: Slightly sunnier days" (18828) + "BoC Monetary policy decision" (18783) + "BoC, Macklem: Press Conference" (18782); HSBC "Bank of Canada (July) Little reason to hike" (18822); UBS "Canada Economic Perspectives: Bank of Canada becoming more optimistic" (18834); Nomura "Policy Watch — July BoC Recap" (18862).*

**A · Themes in play**

| Rank | Theme | Assets | Banks talking | Why it matters to the PM |
|---|---|---|---|---|
| 1 | BoC HELD 2.25% — more optimistic domestic tone | Rates, CAD | GS, JPM, HSBC, UBS, Nomura | Growth outlook upgraded; on-hold-2026 unanimous |
| 2 | MPR: 2026 Q4/Q4 GDP cut to 1.4%, "broadly unchanged" | Rates | GS, JPM | Q1 weakness the drag; 2027 raised to 1.9% |
| 3 | Consecutive-hike language dropped (kept alive on oil) | Rates | UBS, Nomura, GS | Macklem "not the base case, multiple times" |
| 4 | House holds vs market's ~50bp of mid-2027 hikes | Rates, CAD | HSBC, GS | The unreconciled gap; oil the swing factor |

**B · The "why"** The Bank of Canada held at 2.25%, exactly as consensus, the market and every house expected, but the communication turned a shade more constructive. **GS (18819):** the statement noted "clear signs that economic growth has resumed" after it "stalled"; the MPR lowered the **2026 Q4/Q4 GDP forecast by 0.4pp to +1.4%** (reflecting a "weaker-than-expected" start) while calling the outlook "broadly unchanged"; the output-gap assessment moved to −1.5%/−0.5% ("slightly more excess supply than anticipated in April," a dovish addition); headline CPI ticked to 3.2% but ex-gasoline was only 2.2% and core "close to 2%"; the policy section returned to the pre-war guidance that the rate is "appropriate." GS stays on hold through 2026, dovish to market pricing. **JPM (18828, "Slightly sunnier days"):** the tone was "more positive" — 2Q growth was revised up to 2.5% (from 1.5%) and 2027 to 1.9%, but the Q1 weakness pulled the Q4/Q4 forecast to 1.4% (from 1.8%); Macklem stressed the MPR's US$70-75/bbl oil assumption runs ~$10 below spot, dropped the consecutive-hike mention from his opening statement, and reaffirmed policy is "appropriately calibrated." **UBS (18834):** "becoming more optimistic" — the notable shift was from external factors to the domestic picture; UBS sees no hike until H2-2027. **Nomura (18862):** read the statement as "modestly hawkish" on the growth upgrade, base case 65% no more moves (EOP 2.25%), and dropped the "look-through" language on the war. **HSBC (18822):** "little reason to hike" — 2026 inflation raised to 2.5% (oil), 2027 cut to 2.0%; "insufficient evidence of broadening inflationary pressures," against a market "pricing in 50bp of hikes by mid-2027." **CAD firmed +0.14% DoD** on the soft US data; CORRA 2y −4.9bp / 10y −3.7bp into and after the hold.

**B2 · Americas timeline — BoC within-window (official voice vs sell-side read, 15 Jul)**

The layers kept separate; the decision **RESOLVED** on 15-Jul — the official leg is the decision + MPR + Macklem presser, and the sell-side leg is the reaction.

| When (within-window) | Official voice (FACT / official) | Sell-side read (VIEW) |
|---|---|---|
| **15 Jul 13:30 ET — the decision + MPR + presser** | **BoC held the policy rate at 2.25%** (`cb_events` 60980; Bank Rate 2.5%, deposit 2.20%). Statement: "Canada's economy is showing signs of improvement… inflation is projected to ease gradually." MPR cut 2026 Q4/Q4 GDP 0.4pp to **1.4%**, raised 2027 to **1.9%**; output gap −1.5%/−0.5%; core "close to 2%," ex-gasoline CPI 2.2%. Macklem: policy "appropriate to sustain the economic recovery"; dropped the June consecutive-hike scenario (kept it alive "only if oil stays elevated — not the base case," MPR oil assumption US$70-75). | **GS (18819):** a hold with a dovish output-gap addition; on hold through 2026, dovish to market. **JPM (18828):** "slightly sunnier days" — growth upgraded, but Q1 weakness dragged the forecast; on hold rest of year. **UBS (18834):** "more optimistic," first hike not until H2-2027. **Nomura (18862):** "modestly hawkish" on growth; base case no more moves through 2026. **HSBC (18822):** "little reason to hike" — insufficient broadening. |
| **15 Jul — the split into the decision** | *(the decision resolved the base case; the direction-of-next-move debate is now about the oil tail and USMCA)* | On direction after: **the house consensus is on-hold-through-2026** (GS/JPM/UBS/Nomura), with HSBC/UBS not seeing a hike until H2-2027; **the market still prices ~50bp of hikes by mid-2027** (HSBC 18822) — the gap the desks are fading. **StanC's** carried year-end-cut call sits at the dovish extreme. |

*Next catalyst pointer (one line, in-window): with the decision resolved, the CAD read now hinges on the oil path (MPR ~$10/bbl below spot) and the USMCA renegotiation — the swing factors between the unanimous house hold and the market's hike pricing.*

**C · Consensus views**

| Theme | Banks | Shared claim | Evidence cited | What consensus is missing |
|---|---|---|---|---|
| Hold 2.25%; on hold through 2026 | GS, JPM, UBS, Nomura, HSBC | No change; more optimistic tone but no hike this year | Core ~2%; excess supply; MPR growth cut but "broadly unchanged" | The market's ~50bp of mid-2027 hikes; the oil tail |

**D · Differentiated / unique views**

| Bank | Asset | The view | Why it's different | Hidden assumption | Falsifier |
|---|---|---|---|---|---|
| Nomura | Rates | Read the hold as "modestly hawkish" on the growth upgrade; on hold through 2026 | The only house tagging the statement hawkish rather than neutral/dovish | The growth broadening is real; rates stay near the neutral floor | A growth relapse / oil drop pulls the outlook back dovish |
| HSBC | Rates/CAD | "Little reason to hike"; no hike through 2027, fading the market's ~50bp | The clearest fade of the market's hike pricing | Energy inflation stays contained; no broadening; weak jobs | A sustained oil spike broadens inflation (MPR ~$10 below spot) |

Trade rows: (BoC resolved; CAD expressed via Nomura's carried book). **DEPTH:** CA `econ.fact_indicator` thin (most macro not loaded) — the verified anchor is the 2026-07-15 BoC hold (60980). **Flags:** the MPR/oil assumptions and growth forecasts are official-release/sell-side; unanimous house hold vs the market's ~50bp mid-2027 hike pricing unreconciled (both shown); `fact_bond_yield` EMPTY (CORRA is OIS).

### United Kingdom — Sterling leads the universe; UBS sees gilt-rally room on a rule-compliant Budget

*Flagships read: UBS "Global Rates Strategy: Room to rally by 20bps on 10y gilts from sticking to fiscal rules" (18734); Barclays "UK Economics Research: June inflation preview" (18599); JPM UK Money Market Report (18591); HSBC "Europe macro tracker: Tensions rise, water falls" (18823).*

**A · Themes in play**

| Rank | Theme | Assets | Banks talking | Why it matters to the PM |
|---|---|---|---|---|
| 1 | Sterling led the universe (+1.03%); front rallied with US | GBP, rates | (market) | Biggest DoD FX move; GDP prints today |
| 2 | UBS: 20bp of gilt-rally room on a rule-compliant Autumn Budget | Rates | UBS | Burnham confirmed Friday; ~20bp fiscal risk premium priced |
| 3 | June CPI preview / GDP today | Rates, GBP | Barclays | The data into the 30-Jul MPR |

**B · The "why"** The UK is a fiscal-and-rates story with sterling out in front. **GBP firmed +1.03% DoD** — the universe leader — on the soft US CPI/PPI and ahead of today's GDP print, and **SONIA rallied with the US** (2y −4.3bp / 10y −4.0bp; cash gilts not loaded, so this is the OIS read). **UBS (18734)** estimates ~20bp of extra risk premium is priced into 10y gilts from fiscal-policy uncertainty (dating to Mandelson's February resignation and the questions over the Labour leadership), and reasons that if the Autumn Budget complies with the current fiscal rules — its base case, with Burnham set to be confirmed as Labour leader Friday and having tied himself to the rules — gilts have room to rally at least 20bp; a rule *loosening* would instead re-price the premium (a 1ppt deficit shock steepens 2s30s ~8bp). UBS was stopped out of a long BoE Dec'26 trade on the oil-driven front-end sell-off but still holds that the next BoE move is a cut ("front-end real rates remain too high"), and stays long 2s10s steepeners. **Barclays (18599)** previews June CPI into the 30-Jul MPR. UK GDP prints today (m/m survey +0.1%, y/y +1.4%).

**C · Consensus views** Limited independent in-window UK-macro coverage; the anchor is UBS's constructive gilt view tied to fiscal-rule compliance plus Barclays' CPI preview, against a market that trimmed BoE-hike pricing with the US front-end.

**D · Differentiated / unique views**

| Bank | Asset | The view | Why it's different | Hidden assumption | Falsifier |
|---|---|---|---|---|---|
| UBS | Rates | 20bp of gilt-rally room + long 2s10s if the Autumn Budget sticks to the fiscal rules; next BoE move a cut | Actively trades the fiscal-credibility premium, not the BoE path | Burnham complies with the fiscal rules; oil/BoE don't force a re-steepening | A fiscal-rule loosening re-prices the premium; oil extends the front-end sell-off |

Trade rows: **#4**. **DEPTH:** UK `econ.fact_indicator` thin (most macro not loaded) — the verified anchor is the 2026-06-18 BoE hold 7-2. **Flags:** UK GDP 16-Jul forward; cash gilts not loaded (SONIA is OIS); fiscal/CPI figures sell-side (VIEW).
### China — June credit misses on top of the Q2 GDP miss; the desks trim forecasts and price a policy pivot

*Flagships read: JPM "China: Loan weakness triggers year-end growth forecast cut" (18719) + "China: Growth weakened despite activity stabilization" (18717) + "China: Housing activity index trended lower" (18625); Citi "All Eyes on Incremental Policies Following the 26Q2 GDP Miss" (18647) + "Another Miss in Credit Data, and Will It Turn Around?" (18763); Nomura "China: Credit growth slowed to a record low" (18723) + "Q2 GDP growth posted the lowest post-Covid" (18628); UBS "Low 2Q GDP data is good news for the market" (18632) + "New credit remained soft in June" (18731); MS "FY GDP Trimmed to 4.6%; Faster Budget Rollout to Lift 2H Growth" (18626) + "June Credit Slowed Further" (18722); DB "China Macro: Q2 GDP: Catalyzing a Policy Pivot" (18605); HSBC "China credit: Softer growth may be a 'new normal'" (18707) + "China GDP and activity: A mid-year lull" (18614); Barclays "China: Credit growth slows further in June" (18678) + "China: Demand trails supply" (18644); SocGen "Two-speed economy, no big easing ahead" (18671); StanC "China — Focusing on existing policies for now" (18729); GS "Weaker-than-expected money and credit data in June" (18768) + "Real GDP growth slowed meaningfully in Q2" (18608); ANZ "China: GDP downgrade" (18598); Westpac "China has need for urgent stimulus" (18635).*

**A · Themes in play**

| Rank | Theme | Assets | Banks talking | Why it matters to the PM |
|---|---|---|---|---|
| 1 | June credit MISSED — loans/TSF record lows | Rates, CNH, equities | JPM, Nomura, Citi, UBS, HSBC, Barclays | Compounds the Q2 GDP miss; weak domestic demand confirmed |
| 2 | FY GDP forecasts trimmed to ~4.6% | Equities, CNH | Citi, MS, JPM | Q2 4.3% (lowest since 2023); the AI-export engine can't carry it |
| 3 | Policy pivot priced — the split on PBoC easing | Rates, equities | Citi, JPM, UBS, DB, Westpac | Citi 10bp cut July vs JPM Q4; Politburo late-July the resolver |
| 4 | June activity stabilised (IP 5.3%, retail +1.0%) | Equities | DB, Citi, UBS | The counterpoint — momentum improved even as the level missed |

**B · The "why"** China's growth story darkened at the credit layer. **June new yuan loans printed CNY1,610bn** (`cb_events` 108198; survey CNY2,000bn) — the weakest June since 2021 — pushing **outstanding loan growth to a fresh record low of 5.2% y/y** (108200) and **total social financing to a record-low 7.4%** (108201; TSF flow CNY3,360bn vs CNY3,770bn survey); M2 slowed to 8.0% (108199; survey 8.5%). **JPM (18719):** the weakness was in medium- and long-term lending to both households and corporates; it cut its year-end loan/TSF growth forecasts by 0.3pp to 5.0%/7.1%, and — reading the 2Q MPC as showing "no urgency for near-term easing" and a shift toward a price-based framework — **pushed its low-conviction rate-cut call from Q3 to Q4**. **Nomura (18723):** aggregate-financing growth at a record-low 7.4% "is indicative of weak domestic demand," and the June data "further convinced us that… the new AI economy will [not] cure China's economic woes"; Premier Li Qiang's 13-July call to "step up countercyclical policy adjustment" points to a more accommodative, if moderate, H2. This lands on top of Tuesday's **Q2 GDP miss (4.3% y/y, 0.9% qoq — the weakest sequential quarter since 2022; `cb_events` 60929/60933)** with FAI still contracting (−5.7% ytd, 60932) even as **June activity stabilised** (industrial production 5.3% vs 4.6% survey, retail +1.0% vs −0.1% — 60930/60931). The forecast cuts followed: **Citi trims FY GDP to 4.6% from 4.7%** and expects "incremental policies" — a **10bp PBoC rate cut "as soon as July"** and fiscal acceleration, with the late-July **Politburo** the signal (18647); **MS to 4.6%** on a "faster budget rollout" (18626); **DB holds 4.7%** but titles its note "Catalyzing a Policy Pivot," expecting stepped-up H2 support (18605). **UBS (18632)** is the contrarian: "low 2Q GDP data is good news for the market," because a weak reading "increases the odds of getting" a meaningful policy response, and the most important change would be a shift in overall policy *tone* to pro-growth. **CNH was ~flat (+0.06% DoD)**; the soft-CPI relief pulled HK's HIBOR 2y −5.8bp (the linked front-end); HK equities were carried at the 07-14 close (HSI +0.52%, HSCE +0.46%).

**C · Consensus views**

| Theme | Banks | Shared claim | Evidence cited | What consensus is missing |
|---|---|---|---|---|
| June credit at record lows — weak domestic demand | JPM, Nomura, Citi, UBS, HSBC, Barclays | Loans 5.2% / TSF 7.4% both record lows; MLT demand the drag | New loans 1,610bn vs 2,000bn; M2 8.0% | The size/timing of the policy response the data force |
| Policy support steps up in H2 | Citi, MS, DB, UBS, Westpac, Nomura | Countercyclical support / faster fiscal deployment; Politburo pivot | Li Qiang symposium; FY trims; existing LGSB quota | Whether easing is monetary (PBoC cut) or a tone/fiscal shift |

**D · Differentiated / unique views**

| Bank | Asset | The view | Why it's different | Hidden assumption | Falsifier |
|---|---|---|---|---|---|
| Citi | Rates/equities | A 10bp PBoC rate cut "as soon as July" + fiscal acceleration | The most explicit near-term easing call | Beijing responds fast to the data miss | JPM's "no urgency" — the PBoC waits to Q4 |
| JPM | Rates | Cut year-end loan/TSF forecasts; pushed its rate-cut call from Q3 to Q4 — "no urgency" | Reads the 2Q MPC as reluctant, defers easing | The PBoC tolerates slower credit amid the property/infra shift | A sharp activity relapse forces an earlier cut |
| UBS | Equities | The weak GDP is "good news for the market" — raises the odds of a policy-tone pivot | Trades the reaction function, not the print | A low reading pressures policymakers into a pro-growth tone | The Politburo disappoints / keeps the "don't over-invest" tone |

Trade rows: **#7** (Citi policy-pivot bet, via CNH/rates/HK). **DEPTH:** China/HK `econ.fact_indicator` deep. Q2 GDP + June activity + June credit all FACT in `cb_events` (60929-60935, 108198-108201). **Flags:** the house FY-GDP cuts and PBoC-easing calls are sell-side (VIEW); split on easing timing unreconciled (Citi July vs JPM Q4, both shown); the Politburo pivot is a forward catalyst.

### Japan — The long end buys temporary relief on a strong 20y auction + government jawboning

*Flagships read: BNP "JPY rates: Calling off long 10s20s box, but too early to short" (18646); SocGen "JPY Rates: Verbal interventions = temporary relief" (18630); Nomura Yen Rates Daily Monitor (18669) + Yen RV Analytics (18668) + "JPY Intraday Comment — Debate over consumption tax cut set to…" (18726); JPM "Japan: Machinery orders pull back in May" (18621) + "Japan: July manufacturing sentiment holds up on AI demand" (18623); GS "July Reuters Tankan: Manufacturers' DI Flat" (18584); DB "Japan Macro & Fixed Income Strategy: The Battle for 3%" (18694) + "FX seasonality: August favours the yen" (18695); MS "2025 CPI rebase: MIC released new CPI weights" (18799); Citi The Point for Japan (18846).*

**A · Themes in play**

| Rank | Theme | Assets | Banks talking | Why it matters to the PM |
|---|---|---|---|---|
| 1 | Strong 20y auction + verbal intervention = temporary relief | JGBs, JPY | BNP, SocGen, Nomura | Long end richened; the behind-the-curve trades paused |
| 2 | "Policy put" at 2.90% in 10s | JGBs | SocGen | The government's implicit yield ceiling |
| 3 | Consumption-tax-cut probability fell | Rates, JPY | SocGen, Nomura | Lower issuance risk supports term premium near-term |
| 4 | Core machine orders collapsed (−12.4% m/m) | Rates | JPM | Volatile May pullback; Tankan/AI-sentiment held |

**B · The "why"** Japan's long-end sell-off found a floor — for now. The government has "grown anxious about the rise in yields and peppered the market with plans" to stop the selloff (SocGen 18630), and a **20y JGB auction printed extraordinarily strong** — issued ~2bp below the pre-auction market level with a zero tail — so the **10s20s box richened ~5bp and bull-flattened 8bp** (BNP 18646). The result: **BNP called off the long 10s20s box** it had intended to put on before the auction, because the 20y richened past its take-profit before entry, and it holds off shorting the superlong given "chronic" current-issue richness, the start of the quarterly issuance cycle, and the BoJ's higher SLF charge (GC-50bp from GC-25bp this week). **SocGen** takes the same read — it puts the government's "policy put" at **2.90% in 10s** (the level consistent with debt/GDP falling), takes profit on its behind-the-curve expressions (close rec 1y1y vs JGB futures +3bp; receive 6m10y AUD vs JPY +30bp; systematic short 30y +12bp), and enters a new tactical **receive JPY 5y5y vs paid SOFR (107bp, target 125bp, stop 98bp)** to play near-term term-premium compression — while flagging the relief is "unlikely to last medium term" because the plans (Basic Policy draft, GPIF reallocation, NISA) "do not fix the fundamental drivers: loose monetary and fiscal policy." Notably, SocGen now sees a "much lower likelihood of consumption tax cuts," which lowers issuance risk. **TONAR nudged up** (2y +0.6bp / 10y +1.3bp) as the relief was already priced and short positions reduced. On data, **June core machine orders collapsed −12.4% m/m** (`cb_events` 41368; survey −4.2%) — a volatile pullback from the May surge — while the July Reuters Tankan manufacturers' DI was flat (GS 18584) and JPM (18623) noted manufacturing sentiment held up on AI demand; the tertiary industry index rose 1.1% (60937). JPY was flat (+0.01%). DB (18695) flags that FX seasonality favours the yen in August.

**C · Consensus views**

| Theme | Banks | Shared claim | Evidence cited | What consensus is missing |
|---|---|---|---|---|
| The long-end relief is real but tactical | BNP, SocGen, Nomura | Strong 20y auction + jawboning richened the long end; positions reduced | 20y 2bp through, zero tail; 10s20s +5bp | Whether the relief survives August supply and the "loose policy" drivers |

**D · Differentiated / unique views**

| Bank | Asset | The view | Why it's different | Hidden assumption | Falsifier |
|---|---|---|---|---|---|
| SocGen | JGBs | Receive JPY 5y5y vs paid SOFR — a "policy put" at 2.90% 10s compresses term premium near-term | Turns the jawboning into a specific tactical long | The relief holds short-term; positions stay reduced; tax-cut odds low | August supply / a BoJ turn reasserts the "loose policy" driver |
| BNP | JGBs | Call off the long 10s20s box (no entry); too early to short the superlong | Steps aside rather than chase — the richening isn't yet a durable reversal | Current-issue richness + BoJ SLF charge deter shorting | A clean consolidation signal cheapens the long end |

Trade rows: **#2, #3, #6**. **DEPTH:** Japan `econ.fact_indicator` thin/partial (machine orders + tertiary index booked; most macro not loaded). The verified anchor is the 2026-06-16 BoJ +25bp hike. **Flags:** the auction/verbal-intervention read is qualitative (VIEW); the CPI rebase (MS 18799) is a forthcoming data change; JGB long-end is swap/OIS (`fact_bond_yield` EMPTY).

### Hong Kong — Quiet; HKD firm on the peg, the soft-CPI relief pulls HIBOR lower

*Flagships read: HSBC "China Macro Tracker: Expanding consumption, led by services" (18359, HK/China); GS "ASIA: Need to Know — Midday Regional Update" (18658); Citi The Point for Australia/NZ + Asia dailies (18845/18846). No dedicated HK-macro flagship in-window — HK trades off the China tape and the Fed-linked peg.*

**A · Themes in play**

| Rank | Theme | Assets | Banks talking | Why it matters to the PM |
|---|---|---|---|---|
| 1 | Fed-linked peg; soft US CPI/PPI eases pressure | HKD, HIBOR | (peg mechanics) | Lower US front-end pulled HIBOR 2y −5.8bp |
| 2 | HK equities track the China tape | Equities | (market) | HSI/HSCE carried at the 07-14 close on the China read |

**B · The "why"** Hong Kong is a genuinely quiet in-window read, trading off the China tape and the Fed-linked peg rather than any domestic catalyst. **HKD was flat (−0.02% DoD)** on the peg; **HIBOR fell (2y −5.8bp / 10y flat)** as the soft US CPI/PPI relieved the Fed-linked front-end — the reversal of Tuesday's pre-CPI backup, and one of the larger Asia front-end moves this session. HK equities were carried at the 07-14 close on the China read (HSI +0.52%, HSCE +0.46%, HSTECH +0.06%). The one thing to watch: **HK unemployment prints 17-Jul** (prior 3.7%). No house floated a fresh HK-specific rates or FX trade in-window.

**C · Consensus views** No independent HK-specific macro cluster in-window; HK sits inside the China read and the Fed-linked-peg mechanics above.

**D · Differentiated / unique views** None HK-specific in-window.

Trade rows: none. **DEPTH:** HK `econ.fact_indicator` deep (loaded); the verified anchor is the USD-peg / LAF band (no HKMA decision — linked to the Fed). **Flags:** HKD/HIBOR track the peg and the China tape; HK unemployment 17-Jul forward.
### New Zealand — The front-end rallied hardest on the relief; HSBC opens the dovish end of the hike-path split

*Flagships read: HSBC "New Zealand Digest: A growth upswing without housing" (18821); Westpac "First Impressions: NZ retail card spending, June 2026" (18372) + "First Impressions: REINZ house sales and prices" (18373); ANZ NZ REINZ housing (18340); UBS "Global FX Strategy: FX Compass" (18633, tagged NZ). Carried: ANZ QSBO Sep+Oct (18030), UBS QSBO Sep+Dec (18107).*

**A · Themes in play**

| Rank | Theme | Assets | Banks talking | Why it matters to the PM |
|---|---|---|---|---|
| 1 | NZIONA front rallied hardest in the universe (−9.2bp) | Rates, NZD | (market) | The soft-CPI relief reached the freshly-started hiking curve |
| 2 | HSBC: less-aggressive RBNZ than market (100bp by end-2027 vs 135bp) | Rates | HSBC | The dove of the hike-path split — no housing wealth effect |
| 3 | Card spending soft (−1.4% m/m); housing subdued | Rates | Westpac, ANZ, HSBC | Activity uneven; the wealth-effect channel is missing |
| 4 | NZD second-firmest (+0.64%) | NZD | (market) | Soft US data + the RBNZ tailwind |

**B · The "why"** New Zealand's front-end rallied the hardest in the universe as the soft-CPI relief reached its freshly-started hiking curve: **NZIONA 2y −9.2bp / 10y −2.8bp**, and **NZD firmed +0.64% DoD** (second only to sterling). The fresh house voice is **HSBC (18821)**, and it sits at the *dovish* end of the hike-path debate. Its thesis — "a growth upswing without housing" — is that the recovery finally got going early this year but has lacked the usual housing-driven wealth-effect thrust (prices are ~16% below their late-2021 peak, ~36% in real terms, and have tracked sideways since 2023), which "quite a drag on consumer spending." HSBC sees only a modest housing-price rise in H2-2026/2027, not enough to generate a strong wealth effect, so it expects the RBNZ to hike further but **only 100bp by end-2027 versus market pricing of 135bp** — housing the key factor in its more-dovish view. That undercuts the carried hawkish cluster (ANZ's Sep+Oct back-to-back, UBS's Sep+Dec to 3.00%). The data corroborate the uneven activity: **June retail card spending fell −1.4% m/m** (`cb_events` 108259; total −1.2%), and Westpac (18372/18373) and ANZ (18340) both flagged subdued housing (REINZ). The 21-Jul Q2 CPI is the arbiter of the split.

**C · Consensus views**

| Theme | Banks | Shared claim | Evidence cited | What consensus is missing |
|---|---|---|---|---|
| The RBNZ keeps hiking; the upswing is underway | ANZ, UBS, HSBC | More hikes coming; growth recovering | QSBO pricing (carried); HSBC growth upswing | The count/pace — ANZ Sep+Oct vs UBS Sep+Dec vs HSBC's below-market 100bp |
| Activity uneven; the housing wealth effect is missing | HSBC, Westpac, ANZ | Card spending soft; housing subdued | Card −1.4%; prices −16% from peak | How much the missing wealth effect caps the hiking need |

**D · Differentiated / unique views**

| Bank | Asset | The view | Why it's different | Hidden assumption | Falsifier |
|---|---|---|---|---|---|
| HSBC | Rates | 100bp of hikes by end-2027 — below the market's 135bp — because there is no housing wealth effect | The dove of the cluster; ties the hike count to the wealth-effect channel | Housing prices rise only modestly; consumption stays capped | A housing-price re-acceleration revives the wealth effect / a hot Q2 CPI |
| ANZ (carried) | Rates | +25bp in both Sep and Oct — the most front-loaded path | Fastest hikes in the cluster | QSBO pricing stays acute; the cost shock doesn't reverse | A soft 21-Jul Q2 CPI / pricing gauge rolls over |

Trade rows: (Nomura short GBP/NZD, row 10 carried). **DEPTH:** NZ `econ.fact_indicator` loaded; card spending is FACT in `cb_events` (108259). The verified anchor is the 2026-07-08 RBNZ +25bp hike. **Flags:** Q2 CPI 21-Jul forward; HSBC (100bp) vs market (135bp) vs ANZ/UBS hike paths unreconciled (all shown).

### Australia — The hawkish universe exception: Hunter floats higher unemployment, AONIA backs up

*Flagships read: ANZ "AUD Midweek Highlights: geopolitics in front seat" (18597) + "AUD Rates Update: inflation risks favour being short AUD rates" (18342, carried) + Daily Rates RV Pack (18341); Westpac Antipodean Daily Wrap (18634) + "What's Priced In" (18674) + "Macro FX Trade Ideas" (18675); ANZ "Monetary Policy Expectations Analysis: What's Priced In" (18841).*

**A · Themes in play**

| Rank | Theme | Assets | Banks talking | Why it matters to the PM |
|---|---|---|---|---|
| 1 | AONIA the only universe curve to back up (+3.2bp) | Rates | (market) | The hawkish exception to the global relief |
| 2 | Hunter: higher unemployment may be needed | Rates | ANZ | RBA door open to further tightening |
| 3 | ANZ stays short AUD rates (paid Dec-26 RBA OIS) | Rates | ANZ | RBA reaction function inflation-skewed; terminal underpriced |
| 4 | AUD firm (+0.44%); AUD/NZD at a March low | AUD | ANZ | Soft US data + the RBNZ-relative move |

**B · The "why"** Australia was the hawkish outlier in a session of global front-end relief. **AONIA backed up (2y +3.2bp / 10y +3.3bp)** — the only universe curve that rose — even as the US/UK/Asia front-ends rallied, because the domestic signal leaned hawkish. **ANZ (18597):** RBA Assistant Governor Sarah Hunter "suggested higher unemployment may be needed to return inflation to target, leaving the door open to further policy tightening" — and ANZ holds its carried short-AUD-rates stance (**paid Dec-26 RBA OIS**, favouring the 1y/1y1y/2y1y belly fly), reasoning that the RBA's reaction function is "heavily skewed" to inflation and terminal pricing doesn't fully factor a supply-shock world (18342). **AUD firmed +0.44% DoD** on the soft US data, and **AUD/NZD pulled back to its lowest since late March** after the RBNZ hike and strong NZ data. ANZ flags that with little domestic data before the 23-Jul labour force survey, the AUD is driven by geopolitics and US data (tonight's PPI, Friday's Michigan sentiment). Q2 CPI (29-Jul) is the domestic fork.

**C · Consensus views** Limited independent in-window AU-macro cluster (the NAB/consumer surveys were Tuesday's prints, carried); ANZ's short-AUD-rates read on the RBA's inflation skew is the anchor, corroborated by the hawkish AONIA move.

**D · Differentiated / unique views**

| Bank | Asset | The view | Why it's different | Hidden assumption | Falsifier |
|---|---|---|---|---|---|
| ANZ | Rates | Short AUD rates (paid Dec-26 RBA OIS); pay the belly fly — terminal underpriced, RBA inflation-skewed | Actively trades the RBA's inflation skew + a supply-shock long-end thesis; the hawkish universe outlier | RBA stays inflation-focused (Hunter); supply shocks keep the long-end high | A dovish RBA pivot / soft 29-Jul Q2 CPI / oil drops |

Trade rows: **#5** (and Nomura pay AU3m1y vs US3m1y, row 10 carried). **DEPTH:** AU `econ.fact_indicator` deep (loaded). The verified anchor is the 2026-06-16 RBA hold. **Flags:** Hunter's remark is per flow (ANZ 18597); Q2 CPI 29-Jul + labour force 23-Jul forward; AONIA is the pre-US-session Asian close.
### Singapore — HSBC flags an unusually flat SGD NEER into the late-July MPS; SORA rallied on the relief

*Flagships read: HSBC "Asian FX Focus: SGD Weaker than normal" (18706); Citi "CN Export, SG 2Q26 GDP, KR 2Q26 NDF Data" (18601); SocGen SG inflation monitor (carried 18226). Carried: JPM "unbowed, unbent, unbroken" (18103), Citi July S$NEER steepening (18125).*

**A · Themes in play**

| Rank | Theme | Assets | Banks talking | Why it matters to the PM |
|---|---|---|---|---|
| 1 | HSBC: SGD NEER "weaker than normal"; MAS FX reserves fell $4.7bn | SGD | HSBC | An unusual reserve drop suggests MAS defending the NEER |
| 2 | Slope-normalisation timing debated (soft inflation, robust growth) | Rates, SGD | HSBC, Citi | The July MPS setup — Citi's carried steepening call vs a softer NEER |
| 3 | SORA rallied on the soft-CPI relief | Rates | (market) | 2y −3.5bp / 10y −3.3bp |

**B · The "why"** Singapore's fresh voice is a currency read. **HSBC (18706):** the MAS's weekly SGD NEER index has been "flatter than normal" — basically unchanged since the April MPS despite the band-slope increase — sitting ~1.3-1.4% above the midpoint (vs 1.6% in mid-April), reflecting slower capital inflows and portfolio "recycling" into foreign assets. Tellingly, **the MAS's FX reserves fell an unusual USD4.7bn in June** even as it kept redeeming RMGS, which HSBC reads as the MAS becoming "more active about supporting the SGD NEER" — the trigger being upside activity-data surprises (1Q GDP revised to +1% q/q) and local distillate/electricity prices not following crude lower (3Q tariffs +17%). The conclusion: risk-reward "does not favour using the SGD as a funder for carry trades." The **timing of further slope normalisation is debated** — inflation running a touch soft (2Q ~1.4% vs the MAS's 1.7% forecast) but growth "surprisingly robust" (Tuesday's advance Q2 GDP 5.7%, carried) — which is exactly the tension into the **late-July MPS (27-31 Jul window)**. **SGD firmed +0.14% DoD**; **SORA rallied (2y −3.5bp / 10y −3.3bp)** on the soft-CPI relief.

**C · Consensus views** Limited fresh independent SG cluster in-window (the strong advance Q2 GDP is Tuesday's print, carried); HSBC's flat-NEER/reserve-drop read is the anchor, sitting against Citi's carried July S$NEER steepening call.

**D · Differentiated / unique views**

| Bank | Asset | The view | Why it's different | Hidden assumption | Falsifier |
|---|---|---|---|---|---|
| HSBC | SGD | SGD NEER "weaker than normal" — MAS defending it (reserves −$4.7bn); don't use SGD as a carry funder | Reads the reserve data as covert MAS support, not a slope signal | The reserve drop reflects NEER defence, not RMGS mechanics | A resumption of capital inflows lifts the NEER without MAS action |
| Citi (carried) | Rates | Reiterate July S$NEER steepening on above-trend 2Q GDP | The explicit MAS-slope trade off the strong growth | MAS tilts hawkish at the late-Jul MPS; growth stays firm | A dovish MAS hold / a softer-NEER outcome (HSBC's read) |

Trade rows: (Citi July S$NEER steepening, carried). **DEPTH:** SG `econ.fact_indicator` loaded; the advance Q2 GDP (carried) is FACT in `cb_events`. The verified anchor is the MAS S$NEER band (no rate decision). **Flags:** MAS MPS 27-31 Jul forward (NOT today); the NEER/reserve figures are HSBC's estimates (VIEW); NODX 17-Jul forward.

### Indonesia — HSBC frames 2H as the "big test": stability delivered, but a growth cost looms into BI 22-Jul

*Flagships read: HSBC "Indonesia's big test for 2H: The economy in charts" (18781); UBS "Indonesia Market Strategy: Outlook for the rest of the year" (18805, equity). Carried: JPM "Indonesia: Fiscal outlook and market implications" (18151).*

**A · Themes in play**

| Rank | Theme | Assets | Banks talking | Why it matters to the PM |
|---|---|---|---|---|
| 1 | Macro stability delivered (rates up, fiscal reined in, core inflation down) | Rates, IDR | HSBC | The tightening worked; inflows trickled in |
| 2 | The 2H growth cost — will authorities keep policy tight? | Rates, IDR | HSBC | The key question into BI 22-Jul |
| 3 | IDR firmest in ASEAN (+0.27%); external debt $444.4bn | IDR | (market) | Soft USD tailwind; debt edged up |

**B · The "why"** Indonesia is a stability-versus-growth read this window. **HSBC (18781, "The economy in charts"):** over recent months Indonesia "ramped up macro stability" — rates raised, liquidity tightened, fiscal excesses reined in — and it worked: inflows "trickled in" and underlying inflation fell. But HSBC flags "there could be a growth cost," and frames the central 2H question as **whether the authorities keep policy tight if growth slows further** — the "big test" into the 22-Jul BI decision. This complements JPM's carried positioning read (MW IDR, MW IndoGBs, reduce UW INDONs; long INR vs PHP & IDR — 18151). **IDR was the firmest ASEAN currency (+0.27% DoD)** on the soft USD; **external debt edged up to $444.4bn** (`cb_events` 108249, from 439.8/440.2®). UBS (18805) published an equity-market outlook. JIBOR was little changed (2y +0.3bp / 10y −1.2bp). BI decides 22-Jul.

**C · Consensus views** No independent second-house Indonesia-*macro* cluster in-window beyond HSBC; HSBC's stability-vs-growth read is the anchor, sitting with JPM's carried MW positioning.

**D · Differentiated / unique views**

| Bank | Asset | The view | Why it's different | Hidden assumption | Falsifier |
|---|---|---|---|---|---|
| HSBC | Rates/IDR | Stability delivered, but 2H is the "big test" — a growth cost may force a policy choice | Frames the 2H trade-off explicitly around whether BI stays tight into slowing growth | The tightening's growth cost materialises in 2H | Growth holds up, letting BI stay tight without a trade-off |
| JPM (carried) | FX/rates/credit | MW IDR, MW IndoGBs, reduce UW INDONs; long INR vs PHP & IDR | The most complete cross-asset Indonesia positioning read | BI stays hawkish; FA flows keep improving; consolidation delivers | Fiscal slippage / a growth undershoot forces easing and FX pressure |

Trade rows: **#8** (JPM Indonesia package, carried). **DEPTH:** ID `econ.fact_indicator` deep (loaded); external debt is FACT in `cb_events`. The verified anchor is the 2026-06-18 BI +25bp hike. **Flags:** BI decision 22-Jul forward; HSBC's 2H-growth-cost framing is a forecast (VIEW); the FX leg is expressed as-is.

### Thailand — Quiet; THB the universe laggard, rates edged lower, BoT on hold

*Flagships read: SocGen EM/FX Asia Pulse (18672); Nomura SDR FX Analysis — Asia (18859). Carried: Citi "TP on Long USDTHB Exposure; Rolling Over Bearish PHP" (18064), StanC BoT-on-hold. No dedicated Thailand-macro flagship in-window.*

**A · Themes in play**

| Rank | Theme | Assets | Banks talking | Why it matters to the PM |
|---|---|---|---|---|
| 1 | THB the universe FX laggard (−0.24%) | THB | (market) | The only material G10/EM-Asia underperformer this session |
| 2 | Citi's booked long USD/THB carries; BoT on hold | Rates, THB | Citi (carried), StanC | FX-intervention anchor; no domestic catalyst in-window |

**B · The "why"** Thailand is quiet in-window and, unusually, the universe's weakest currency. **THB fell −0.24% DoD** — the only material underperformer against a broadly soft dollar — while **THOR edged lower (2y −1.0bp / 10y −1.7bp)** with the regional relief. There was no fresh Thailand-specific macro print or house-forecast note in-window; the read carries **Citi's booked long USD/THB (+82bp, 18064)** and its expectation that FX intervention anchors the pair, plus StanC's carried BoT-on-hold stance (both years). CPI/policy are post-window. The one thing to watch: whether the THB underperformance reflects a positioning/flow shift or FX-intervention mechanics — no house flagged a fresh catalyst.

**C · Consensus views** No independent Thailand-macro cluster in-window; THB sits inside Citi's carried EM options book and the on-hold BoT read.

**D · Differentiated / unique views** None fresh Thailand-specific in-window (Citi's USD/THB is a booked/managed position, row 9).

Trade rows: **#9** (carried). **DEPTH:** TH `econ.fact_indicator` partial. The verified anchor is the 2026-06-24 BoT hold. **Flags:** no in-window Thailand-macro flagship (traded off FX + BoT-on-hold); THOR is the pre-US-session Asian close.

### Malaysia — Quiet into today's CPI + Q2 GDP double print

*Flagships read: no dedicated Malaysia-macro flagship in-window; MYR/rates trade off the regional tape into the 17-Jul releases. Carried: Barclays Sep-hike call, GS "continuity" on Johor.*

**A · Themes in play**

| Rank | Theme | Assets | Banks talking | Why it matters to the PM |
|---|---|---|---|---|
| 1 | CPI + Q2 GDP prelim both today (17-Jul) | Rates, MYR | (calendar) | CPI survey 2.0%, GDP prelim fcst 5.3% — the fork |
| 2 | MYR softer (−0.15%); rates nudged up | MYR, rates | (market) | The rare ASEAN currency down on the soft USD |

**B · The "why"** Malaysia is genuinely quiet in-window, ahead of today's double print. **CPI (17-Jul, survey 2.0% yoy) and advance Q2 GDP (17-Jul, forecast 5.3%, prior 5.4%)** are the fork; no dedicated Malaysia-macro flagship landed on 07-15/07-16. **MYR softened −0.15% DoD** — one of the few universe currencies lower against a broadly weak dollar — and KLIBOR nudged up (2y +1.0bp / 10y +0.5bp). The carried house frame (Barclays keeping a September +25bp to 3.00% vs GS "continuity" on Johor politics) awaits today's growth/inflation data. The one thing to watch: whether the Q2 GDP prelim confirms above-5% growth that would keep the Barclays Sep-hike case alive.

**C · Consensus views** No independent Malaysia-macro cluster in-window; the read waits on today's CPI + GDP.

**D · Differentiated / unique views** None fresh Malaysia-specific in-window (carried: Barclays Sep-hike vs GS continuity).

Trade rows: none direct. **DEPTH:** MY `econ.fact_indicator` partial. The verified anchor is the 2026-07-09 BNM hold at 2.75%. **Flags:** CPI + Q2 GDP prelim 17-Jul forward; no in-window Malaysia flagship.

### Philippines — Quiet; PHIREF front rallied hard on the relief, peso flat

*Flagships read: Nomura SDR FX Analysis — Asia (18859); Citi The Point for Asia dailies. Carried: Citi bearish-PHP 1x1.5 call ratio 3m (18064), StanC 5.00% Aug + RPGB carry, UBS local-equity conviction (18233). No dedicated Philippines-rates/FX-macro flagship in-window.*

**A · Themes in play**

| Rank | Theme | Assets | Banks talking | Why it matters to the PM |
|---|---|---|---|---|
| 1 | PHIREF front rallied hard (−7.4bp) | Rates | (market) | The soft-CPI relief reversed Tuesday's +11.5bp backup |
| 2 | Peso flat (+0.02%); remittances +2.0% | PHP | (market) | No domestic catalyst; Citi's bearish-PHP roll carried |

**B · The "why"** The Philippines is quiet in-window on the macro side, trading off the front-end and FX positioning. **PHIREF rallied hard (2y −7.4bp / 10y −1.2bp)** — one of the largest Asia front-end moves — as the soft-CPI relief reversed Tuesday's +11.5bp pre-print backup. **PHP was flat (+0.02% DoD)** on the soft USD, with June overseas remittances steady at +2.0% (`cb_events` 41372). **Citi (18064)** keeps its bearish PHP 1x1.5 call ratio 3m (carried), capping expected peso strength, and Nomura carries long INR vs PHP (row 10). No fresh Philippines-rates or CPI print landed in-window; StanC's carried frame (5.00% August, 2Y-3Y RPGB carry) awaits the next data. The one thing to watch: any BSP guidance ahead of the August meeting.

**C · Consensus views** No independent Philippines-macro cluster in-window; the read sits inside Citi's carried EM options book and the front-end relief.

**D · Differentiated / unique views** None fresh Philippines-macro in-window (carried: Citi bearish-PHP roll; StanC 5.00% Aug + RPGB carry).

Trade rows: **#9** (Citi PHP roll, carried) + Nomura long INR vs PHP (row 10). **DEPTH:** PH `econ.fact_indicator` deep (loaded); remittances FACT in `cb_events`. The verified anchor is the 2026-06-18 BSP +25bp hike. **Flags:** no in-window Philippines flagship; PHIREF is the pre-US-session Asian close; StanC 5.00% Aug carried.
### India — ANZ decodes the "core inflation puzzle"; INR recovers to flat, unemployment steady at 5.5%

*Flagships read: ANZ "India: decoding the core inflation puzzle" (18641); Barclays "India: June labour data: stable unemployment rate" (18753); GS "India QC" (18606) + "India Brew" (18609) + "India F&O: Positioning Changes" (18611); MOSPI "Monthly Press note June 2026" (18749); RBI "Developments in India's Balance of Payments" (18837). Carried: MS June WPI all-time-high (18152), Barclays WPI "relentless rise" (18171), SocGen short-EUR/INR take-profit (18227), Nomura long-EUR/INR (18221), Citi long-INR-basket (17693), UBS INR-payer hedge (17959).*

**A · Themes in play**

| Rank | Theme | Assets | Banks talking | Why it matters to the PM |
|---|---|---|---|---|
| 1 | ANZ "core inflation puzzle" — refined core subdued at 2.5% | Rates, INR | ANZ | Weak core lets the MPC wait; the risk factors are turning |
| 2 | INR recovered to flat (−0.05%) after Tuesday's −0.45% | INR | (market) | The hot-prints/oil selloff stabilised |
| 3 | Unemployment steady at 5.5% | Rates | Barclays, MOSPI | Labour market stable; no fresh demand-inflation impulse |
| 4 | The EUR/INR split (Nomura long vs SocGen short-TP) | INR | Nomura, SocGen (carried) | Opposite sides on the same cross |

**B · The "why"** India stabilised after Tuesday's hot CPI/WPI selloff, and the fresh house voice reframes the rate debate. **ANZ (18641, "decoding the core inflation puzzle"):** India's "refined" core CPI — headline ex-food, fuel and precious metals, a cleaner gauge of domestic demand pressure — is surprisingly weak, near the bottom of the MPC's 2-6% band (a record-low 2.1% in Q1-2026, 2.5% y/y in June) despite four years of 7%+ growth; ANZ attributes this to investment-led growth (capacity outpacing consumption demand) among four identifiable factors. The catch: "the same set of factors are now shifting, portending a rebound in underlying inflation," so ANZ warns caution even as the currently weak core "allows the MPC to wait for greater clarity" — with US policy rates, oil prices and weather-driven food shocks on the risk radar. That is the analytical backbone for the carried look-through camp (Citi/JPM/Barclays: no 2026 hike unless core sustains higher). On the data, **June unemployment held at 5.5%** (`cb_events` 60961; survey 5.4%, Barclays 18753 "stable"), a steady labour market with no fresh demand-inflation impulse. The market read: **INR recovered to flat (−0.05% DoD)** after Tuesday's −0.45%, and **MIBOR edged back down (2y −0.8bp / 10y −0.4bp)** as the hot-prints backup faded. The carried EUR/INR positions remain split — **Nomura long EUR/INR (target 113)** against **SocGen's booked short-EUR/INR profit-take** "as headwinds rise" (both carried, opposite sides).

**C · Consensus views**

| Theme | Banks | Shared claim | Evidence cited | What consensus is missing |
|---|---|---|---|---|
| Weak core lets the RBI look through the hot headline | ANZ, Citi/JPM/Barclays (carried) | Refined core ~2.5%, near the band floor; no 2026 hike unless core sustains higher | ANZ refined-core series; carried WPI/CPI look-through | Whether ANZ's "factors now shifting" pulls underlying inflation back up |
| Labour market stable; no fresh demand impulse | Barclays, MOSPI | Unemployment steady at 5.5% | June labour data (60961) | How the monsoon/food path feeds H2 CPI |

**D · Differentiated / unique views**

| Bank | Asset | The view | Why it's different | Hidden assumption | Falsifier |
|---|---|---|---|---|---|
| ANZ | Rates/INR | Refined core is weak (2.5%) but the four drivers are turning — caution warranted despite the look-through | The most analytical read — decomposes *why* core is low and flags the turn | The investment-led-growth disinflation reverses as the factors shift | Core stays subdued (investment keeps outpacing consumption) |
| SocGen (carried) | FX | Took profit on short EUR/INR — INR headwinds building | Books the INR-long as hot prints + oil + deficit turn the headwind | The INR-supportive window is closing near-term | INR resumes strengthening (FCNR inflows / oil drops) |
| Nomura (carried) | FX | Long EUR/INR (target 113) | The opposite side of SocGen on the same cross | INR underperforms into the deficit/oil backdrop | INR strengthens (the soft-USD tailwind + carry) |

Trade rows: **#10** (Nomura long EUR/INR + pay Sep 5y India NDOIS) + carried SocGen short-EUR/INR TP, Citi long-INR-basket, UBS INR-payer hedge. **Note:** Nomura (long EUR/INR) and SocGen (short-EUR/INR TP) sit on opposite sides of the same cross — both carried, unreconciled. **DEPTH:** India `econ.fact_indicator` deep (~1,242+ indicators; fresh-food MoM nowcaster live). Unemployment is FACT in `cb_events` (60961); CPI/WPI/trade were Tuesday's prints (carried). The verified anchor is the 2026-06-05 RBI hold at 5.25%. **Flags:** ANZ's refined-core series is a proprietary reconstruction (VIEW); INR rates are MIBOR OIS (`fact_bond_yield` EMPTY); NDOIS levels sell-side; RBI August the next decision.
---

## 10. Grounding ledger  *(SYN)*

**Sources by layer**

- **`calendar.cb_events` (FACT — printed / decisions).** Verified against real rows for the 07-15→07-17 window. **Printed this window:** US June PPI (headline −0.3% m/m / 5.5% y/y, prior revised down to 0.6%®; core +0.2% / 4.7%, May core revised to 0.1%®; ex-food/energy/trade +0.1% / 5.1% — ids 60972-60979) + Empire manufacturing 15.6 (per flow) + Beige Book "slight to moderate" (60998); **Bank of Canada held 2.25%** (60980, + MPR + Macklem presser); China June credit — new yuan loans CNY1,610bn (108198), TSF CNY3,360bn / growth 7.4% (108201), loan growth 5.2% (108200), M2 8.0% (108199); Japan core machine orders −12.4% m/m / −1.9% y/y (41368/41369) + tertiary industry index +1.1% (60937); Korea unemployment 2.7% (41371, context); NZ card spending retail −1.4% / total −1.2% (108259/108260); India unemployment 5.5% (60961); Indonesia external debt $444.4bn (108249); Philippines remittances +2.0% (41372). **Forward at compile:** US retail sales + claims + Philly Fed 16-Jul (65717/65718); UK GDP + IP 16-Jul (65687/65695/65691); NZ food inflation 16-Jul (65745); KR BoK 16-Jul (65683, outside universe); MY CPI + Q2 GDP 17-Jul (66302/66303); HK unemployment 17-Jul (66311); SG NODX 17-Jul (66297); US IP 17-Jul (66332); NZ Q2 CPI 21-Jul; BI 22-Jul; MAS MPS 27-31 Jul window; FOMC + AU Q2 CPI 29-Jul.
- **`econ.fact_indicator` (DEPTH).** Deep for US (193 active), India (~1,242+), AU, NZ, ID, PH, HK/CN, SG. Thin/partial for JP (machine orders + tertiary index this window), CA, UK, TH, MY. Cash govt yields NOT loaded (`rates.fact_bond_yield` EMPTY) — all 2y/10y are swap/OIS (`rates.fact_observation`, par).
- **Market layers.** `FX.fact_fx_rate` (DoD 07-14→07-15, last-tick per day — FX fresh to 07-15); `rates.fact_observation` (2y/10y par, DoD 07-14→07-15 — rates fresh to 07-15, US EOD post-PPI/BoC, Asia the Asian close); `equities.fact_index_level` (fresh only to **07-14** — no 07-15 tick, so the equity column carries the 07-14 close, flagged stale); `equities.fact_vix` (VIX 16.5, 07-14); `commodities.fact_spot` (Gold 4,055.53 / WTI 79.89, both 07-14). Credit spreads NOT in IMDR — none cited as fact.
- **`research.fact_chunk` + Qdrant + Outlook.** ~286 in-window reports (07-15/07-16) swept two ways — structured `dim_report` window filters across all vendors (JPM 59, GS 57, Citi 30, UBS/RBI/Nomura 18, Barclays 17, DB/HSBC 12, ANZ 10, MS/SocGen 9, Westpac 6, BNP 3, StanC/BoK/Fed 2) + the Outlook 13-folder taxonomy (incl. desk_commentary body-only notes) — and reconciled. Deep-read the full US PPI-reaction and BoC-reaction clusters and each country's flagship daily. **Qdrant sweeps run (multi-angle, 07-15→07-16):** "June PPI soft benign core PCE tracking Fed on hold"; "core PCE nowcast after PPI July hike"; "Warsh testimony AI disinflationary structural productivity"; "Bank of Canada hold MPR Macklem optimistic growth oil"; "China June credit new loans TSF record low policy easing PBoC"; "China Q2 GDP miss Politburo stimulus policy pivot"; "Japan JGB 20y auction verbal intervention long end GPIF consumption tax"; "New Zealand RBNZ hike path housing wealth effect"; "Singapore SGD NEER MAS reserves slope MPS". Each reconciled with structured; distinct voices folded into the PPI and BoC B2 timelines (PPI nowcasts GS 18770 / MS 18798 / Citi 18757 / Barclays 18750 / JPM 18787; Warsh UBS 18865; BoC GS 18819 / JPM 18828 / UBS 18834 / Nomura 18862 / HSBC 18822).

**Flagship dailies that fed each country block:**
- **US** — GS "Producer Price Index Below Expectations… 0.17% for Core PCE" (18770) + GS US Daily Download (18652), Citi "The Daily Update – Cool core CPI" (18682) + PPI notes (18757/18758), JPM "PPI moderates… core PCE tracking up" (18787), MS "core PCE at 0.17%" (18798), Barclays "core PCE 0.19%" (18750), UBS Beige Book (18864) + Warsh (18865).
- **Canada** — GS "BoC Remains on Hold" (18819), JPM "Slightly sunnier days" (18828), HSBC "Little reason to hike" (18822), UBS "becoming more optimistic" (18834), Nomura "July BoC Recap" (18862).
- **China** — JPM "Loan weakness triggers forecast cut" (18719), Nomura "Credit growth… record low" (18723), Citi "All Eyes on Incremental Policies" (18647), UBS "Low 2Q GDP… good news" (18632), MS "FY trimmed to 4.6%" (18626), DB "Catalyzing a Policy Pivot" (18605).
- **Japan** — BNP "Calling off long 10s20s box" (18646), SocGen "Verbal interventions = temporary relief" (18630), JPM machine orders (18621), GS Reuters Tankan (18584).
- **New Zealand** — HSBC "A growth upswing without housing" (18821), Westpac card spending / REINZ (18372/18373).
- **Australia** — ANZ "AUD Midweek Highlights" (18597) + short-AUD-rates (18342).
- **UK** — UBS "Room to rally 20bps on 10y gilts" (18734), Barclays CPI preview (18599).
- **Singapore** — HSBC "SGD Weaker than normal" (18706). **Indonesia** — HSBC "big test for 2H" (18781). **India** — ANZ "core inflation puzzle" (18641), Barclays labour (18753). **Hong Kong / Thailand / Malaysia / Philippines** — no dedicated in-window flagship; traded off the regional tape (HK China/peg; TH/PH front-end + carried FX; MY into today's CPI/GDP).

**Source-of-record notes (TE vs BQL):**
- **US June PPI** — TE lane carries the actuals used (headline −0.3%/5.5%, core +0.2%/4.7%; ids 60972-60979). Sell-side (GS/JPM/Citi) corroborates the headline/core split and the ~0.17-0.19% core-PCE read.
- **Bank of Canada** — TE lane (60980, 2.25% held) carries the actual; the BQL row (41366) still shows null actual at compile. Used TE.
- **China June credit** — the bloomberg_bql lane (108198-108201) carries the actuals for new loans / TSF / M2 / loan growth; used for the miss vs survey.

**Unreconciled (both shown):**
- **US core-PCE nowcast** — GS/MS **0.17%** and Citi **0.18%** / Barclays **0.19%** vs **JPM 0.202%** (raised on firmer PPI services); both shown.
- **China PBoC easing timing** — Citi **10bp cut "as soon as July"** (18647) vs JPM **"no urgency," cut pushed to Q4** (18719) vs UBS **policy-tone pivot** (18632); all shown.
- **Canada** — unanimous house **hold through 2026** (GS/JPM/UBS/Nomura/HSBC) vs the **market's ~50bp of hikes by mid-2027** (HSBC 18822); both shown. Nomura tags the statement "modestly hawkish," the others neutral/dovish.
- **New Zealand hike path** — HSBC **100bp by end-2027 (below market's 135bp)** (18821) vs ANZ **Sep+Oct** vs UBS **Sep+Dec** (carried); all shown.
- **India EUR/INR** — Nomura **long EUR/INR (113)** (18221) vs SocGen **short-EUR/INR take-profit** (18227) — opposite sides, both carried, shown.

**Day-over-day vs the prior edition (07-15 → 07-16):** the prior day's marquee — the soft core CPI — got **confirmed** by a soft June PPI, cementing the ~0.17-0.19% core-PCE read and the Fed-on-hold call (JPM the lone tracking-up dissent at 0.20%). The **BoC hold RESOLVED** (2.25%, more optimistic tone, no door to hikes). The **soft-CPI relief that was "pending" on 07-15 landed** — the Asia-Pacific front-ends (NZ/PH/HK/SG) rallied. **China deteriorated** at the credit layer (loans/TSF record lows), turning the desks to forecast cuts and a policy-pivot bet. **Japan's long end** flipped from a repatriation-rally frame to a strong-auction/verbal-intervention relief that the desks call tactical (BNP called off its box, SocGen booked trades). New voices: **HSBC** (dovish NZ, Indonesia 2H test, SGD NEER), **ANZ** (India core puzzle, AU Hunter-hawkish), **UBS** (gilt-rally room).

**Not loaded / pre-decision (flagged):** US retail sales + claims / UK GDP / BoK (all 16-Jul forward); JP/CA/UK/TH/MY macro depth thin in `econ.fact_indicator`; `rates.fact_bond_yield` EMPTY (no cash govt yields — all swap/OIS); credit spreads not in IMDR (none cited as fact); DXY not loaded (agent proxy via crosses); Brent (~$83-84) sell-side (WTI booked $79.89); **`equities.fact_index_level` / `fact_vix` / `fact_spot` are stale to 07-14** (no fresh 07-15 tick), so the equity/vol/commodity column repeats the 07-14 close; **no BBG chat transcript exists for 2026-07-16** (noted).

**Differentiated-view count (§9.D):** US 3 · Canada 2 · UK 1 · China 3 · Japan 2 · Hong Kong 0 · New Zealand 2 · Australia 1 · Singapore 2 · Indonesia 2 · Thailand 0 · Malaysia 0 · Philippines 0 · India 3 = **21 differentiated-view rows across 14 country/region blocks** (quiet-country floor met for HK/TH/MY/PH with a real A+B read grounded in the flagship/tape).

---

## Source register — in-window report IDs by cluster

- **US / DM (c2):** **US** 18770, 18585, 18652, 18653, 18850, 18682, 18757, 18758, 18687, 18711, 18852, 18787, 18788, 18798, 18800, 18750, 18832, 18863, 18848, 18833, 18864, 18865, 18817 · **CA** 18819, 18705, 18828, 18783, 18782, 18822, 18834, 18862 · **UK** 18734, 18599, 18591, 18823.
- **North Asia (c1):** **CN** 18719, 18717, 18625, 18647, 18763, 18723, 18628, 18632, 18731, 18626, 18722, 18605, 18707, 18614, 18678, 18644, 18671, 18729, 18768, 18608, 18598, 18635, 18359 · **JP** 18646, 18630, 18669, 18668, 18726, 18621, 18623, 18584, 18694, 18695, 18799, 18846 · **HK** 18359, 18658, 18845.
- **ANZ (c3):** **NZ** 18821, 18372, 18373, 18340, 18633 (+carried 18030, 18107) · **AU** 18597, 18342, 18341, 18634, 18674, 18675, 18841.
- **ASEAN (c4):** **SG** 18706, 18601 (+carried 18103, 18125, 18226) · **ID** 18781, 18805 (+carried 18151) · **TH** 18672, 18859 (+carried 18064) · **MY** (none in-window) · **PH** 18859 (+carried 18064, 18233).
- **India (c5):** 18641, 18753, 18606, 18609, 18611, 18749, 18837 (+carried 18152, 18171, 18227, 18221, 17693, 17959).
- **Cross-asset / trades / context:** Nomura FX Themes (18593), FX Insights "Thoughts on USD" (18725), SDR FX G10/Asia (18858/18859); ANZ Monthly FX Signals (18640) + Asia Portfolio Flows (18639); DB "FX seasonality: August favours the yen" (18695), Commodities Outlook (18811); UBS "Hormuz tracker: day 137" (18835); GS "Oil, the Fed, and AI" (18850) + IR Kick-Start (18653); Korea context (outside universe, BoK 16-Jul) — GS Korea Daily (18586), JPM Korea employment/trade-prices (18624/18665), BoK export/import prices (18374), FSC reforms (18636).

*Note: report IDs are internal grounding references; the reader-facing digest carries the data and the read, not the ID parade.*
