# Korea — Capital Account Outflow

**Brief · 2026-06-03 · IMDR**

The headline series Korean desks call "**capital account outflow**" is the
Assets side of Korea's **Financial Account** under IMF BPM6 — published
monthly by Bank of Korea, mirrored on KOSIS (`DT_301Y013`) and (partially)
on FRED (`KORB6FATC01CXCUM`). It composes Korea's outward financial flows
into five BPM6 functional categories: Direct Investment, Securities
(Portfolio) Investment, Financial Derivatives, Other Investment, and
Reserve Assets — each (except Reserves and Derivatives) split into the
Assets leg (outflow) and the Liabilities leg (inflow).

## TL;DR (one-page brief)

> Korea is running a **record-pace current-account surplus** (~$24bn/month
> in Q1 2026) and recycling almost all of it back out as financial-account
> outflows. The story has shifted in 2026 from "passive recycling" to
> "active outbound positioning by domestic actors", while foreigners
> simultaneously **sell down their Korean equity overweights** despite a
> +90% YTD KOSPI rally — putting the won under structural pressure even
> as terms-of-trade improve.

### Composition (BPM6, monthly, USD)

| # | Component | Outflow code | Mar-26 (KOSIS, $mn) | What it is |
|---|---|---|---:|---|
| ① | **Direct Investment Assets** (outward FDI) | `BOPF11000000` | **+8,885** | Samsung/SK/Hyundai building offshore capacity; equity + reinvested earnings + intercompany loans |
| ② | **Portfolio Investment Assets** | `BOPF21000000` + `BOPF31xxxxxxx` | **+4,003** | NPS / KIC / insurers / banks / corporates buying foreign equity + debt securities |
| ③ | **Financial Derivatives, Net** | `BOPF3xxxxxxx` | **+5,604** | Net cashflows; mostly forwards (+$5.8bn) — exporter hedging + corp FX recycling |
| ④ | **Other Investment Assets** | `BOPF41000000` | **−1,563** | Banks repatriating offshore deposits; net negative = bringing dollars home |
| ⑤ | **Reserve Assets** | `BOPF50000000` | **−1,849** | BOK *drew down* reserves — intervening to defend KRW |
| **Σ** | **Net Acquisition of Financial Assets** | (sum) | **+15,080** | The headline outflow series |
| | Errors & Omissions | `BOPO00000000` | −319 | residual |

Identity: Current Acct +37,327 − Capital Acct (narrow) +17 + Errors −319 ≈ Financial Acct **+36,991**. Σ children = +36,991 ✓.

### Where we are right now (May-Jun 2026)

- **Current account surplus is at record-territory**: $37bn in March 2026 alone, $24bn/month average in Q1, driven by red-hot semiconductor exports (+202% YoY, May 2026).
- **Foreign portfolio outflow is structurally large**: −$14bn/month average Q1 (JPM), ~−$27bn May alone (HSBC), −$76bn YTD (BNP). Concentrated in Samsung Electronics + SK Hynix (~all of it per Barclays).
- **Domestic recycling is the dominant outflow channel**: JPM estimates the unhedged FA outflow at ~−$26bn/month, including $3bn local FDI-out and $9bn local portfolio-out per month — plus exporters parking earnings in FX (NFC offshore portfolio + cash holdings doubled to **$211bn** end-2025 vs $96bn end-2023 per ANZ).
- **NPS is the swing actor**: On 2026-05-28, NPS raised target domestic-equity weight from **14.9% → 20.8%** and trimmed foreign-equity target from 38.9% → 35.6%. This *slows* but does not stop the outflow — Barclays still models KRW36.6tn (~$25bn) of NPS overseas asset purchases in 2027, funded via the new BoK FX swap line so the KRW spot impact is muted.
- **Retail RIA flips the retail leg**: Reshoring Investment Account (launched late March 2026, capital-gain tax exemption for repatriated foreign-equity proceeds) — Korean retail had been net buyers offshore (−$3.4bn/month Q1) but flipped to net repatriation in April-May (+$0.5bn April, +$1.3bn May per ANZ; BNP reads "meaningful deceleration"). 240k+ RIA accounts, ~$1.3bn balance.
- **BoK is hawkish but only marginally supportive of the won**: May-2026 meeting held 2.50% with 2 dissents for a hike; Gov. Shin said "a hike would have been justified at this meeting." Desk consensus: first 25bp hike in **July**, terminal **3.00%** by year-end. BNP, JPM, ANZ all say flow dominates rates — won move is structural-outflow-bound, not policy-rate-bound.
- **KRW is "unfairly beaten down"** (ANZ BEER fair value 1,200 vs spot ~1,510): record CA surplus + improving terms-of-trade not yet reflected. Catalysts: outflow exhaustion, MSCI EM→DM watchlist review (June 2026).

### How to think about it

The five sub-components have *very* different reversibility, and the
direction of each tells a different story right now:

- ① **Outward FDI ≈ structural & sticky** — Korean corporates building chip + battery capacity abroad. Won't reverse.
- ② **Portfolio outward ≈ cyclical & policy-sensitive** — NPS reallocation matters; RIA tax incentive matters. *Slowing in May 2026.*
- ③ **Derivatives ≈ FX-hedging artefact** — exporters hedging the CA surplus is what creates the recycled USD demand JPM flags.
- ④ **Other Investment ≈ banking-sector signal** — Mar 2026 negative = banks bringing offshore dollars home; reads as wholesale-funding stress easing.
- ⑤ **Reserves ≈ BOK intervention** — Mar 2026 negative = BOK selling reserves to defend the won. Modest scale (−$1.85bn) for now.

### Read sequence

If you want the technicals, jump to [Appendix A](#appendix-a--bpm6-composition-detail).
If you want the flow picture in detail, [Appendix B](#appendix-b--current-flow-picture-may-jun-2026).
If you want forward drivers, [Appendix C](#appendix-c--forward-drivers).
If you want to pull the data yourself, [Appendix D](#appendix-d--data--code-pointers).

---

## Appendix A — BPM6 composition detail

Korea's BoP statement follows IMF BPM6 since 2005. The full statement has
four sections:

1. **Current Account** — trade balance + services + primary income (incl. investment income) + secondary/transfer income
2. **Capital Account** (narrow BPM6) — capital transfers + non-produced non-financial assets (trademarks, debt forgiveness). For Korea this is a trivial line (~$0-200m/month, often near zero).
3. **Financial Account** — the five categories below (this is the "capital account" in trader vocabulary)
4. **Errors and Omissions** — residual closing the BoP identity

The Financial Account is split into five **functional categories** per BPM6.
Each (except Reserves and Derivatives) is recorded both as Assets (Korean
residents' acquisition of foreign claims = outflow) and Liabilities
(foreigners' acquisition of Korean claims = inflow):

| # | Category | Sub-decomposition (KOSIS layout) | BOK item code root |
|---|---|---|---|
| ① | **Direct Investment** | Equity stocks · Reinvestment of profits · Debt instruments (intercompany loans) | `BOPF1xxxxxxx` |
| ② | **Portfolio Investment** | Equity securities · Long-term debt securities · Short-term debt securities — each by KR-resident sector (central bank / govt / deposit-taking / OFI / NFC) | `BOPF2xxxxxxx` (equity) + `BOPF3xxxxxxx` (debt) |
| ③ | **Financial Derivatives & ESOs** | Forward-type contracts · Options · By counterparty sector | `BOPF3xxxxxxx` (net, no asset/liab split) |
| ④ | **Other Investment** | Trade credit & advances · Loans (long/short × counterparty) · Currency & deposits · Other accounts · Other equity · SDR allocations (liab side only) | `BOPF4xxxxxxx` |
| ⑤ | **Reserve Assets** | Monetary gold · SDRs · IMF reserve position · FX currency/deposits · FX securities · Other claims | `BOPF50000000` |

**Net Acquisition of Financial Assets** (the headline "outflow") = sum of
(① + ② + ④ + ⑤) Assets-side + ③ Net.

For the full item-code structure (`BOPF…` 12-char keys, counterparty
encoding, etc.), see
[`docs/admin/econ/korea/ecos_api_reference.md`](../admin/econ/korea/ecos_api_reference.md).

### Terminology gotchas

| Source | Says | Means |
|---|---|---|
| BOK English UI ("ECOS") | "Direct investment (debt)" | Liabilities side (inward FDI) — *not* debt securities |
| BOK English UI | "Securities Investment" | What BPM6 / KOSIS call "Portfolio Investment" |
| KOSIS English UI | "Liabilities" | Liabilities |
| KOSIS English UI | "Portfolio investment" | What BOK calls "Securities Investment" |

KOSIS English is BPM6-standard; the BOK English UI uses BOK's house translation. Same underlying data.

---

## Appendix B — Current flow picture (May-Jun 2026)

### Source-agency statistical view (KOSIS `DT_301Y013`, pulled 2026-06-03)

USD millions, last 6 months available:

| Component | Oct-25 | Nov-25 | Dec-25 | Jan-26 | Feb-26 | Mar-26 |
|---|---:|---:|---:|---:|---:|---:|
| Current account | 7,568 | 12,898 | 18,703 | 13,259 | 23,193 | 37,327 |
| Capital account (narrow) | +0.0 | +0.0 | +0.0 | +0.0 | +0.0 | -16.8 |
| **Financial Account (outflow)** | ... | ... | ... | ... | ... | **36,992** |
| └ ① DI Assets | ... | ... | ... | ... | ... | 8,885 |
| └ ② PI Assets | ... | ... | ... | ... | ... | 4,003 |
| └ ③ Derivatives, Net | ... | ... | ... | ... | ... | 5,604 |
| └ ④ OI Assets | ... | ... | ... | ... | ... | -1,563 |
| └ ⑤ Reserve Assets | ... | ... | ... | ... | ... | -1,849 |
| Errors & Omissions | ... | ... | ... | ... | ... | -319 |

Full monthly breakdown available in
[`playground/econ/kosis/sample_output/2026/06/03/kosis_DT_301Y013_20260603_0935.parquet`](../../playground/econ/kosis/sample_output/2026/06/03/kosis_DT_301Y013_20260603_0935.parquet)
(284 line items × 6 months). For full 1980-present history use the KOSIS
period selector before re-running [`fetch_bop.py`](../../playground/econ/kosis/fetch_bop.py).

### Sell-side desk view (May 2026 prints, all USD)

| Desk | Date | Flow signal | Magnitude |
|---|---|---|---|
| JPM (KRW: The woes of the won) | 2026-06-03 | CA surplus → unhedged FA outflows | CA $24bn/mo Q1 (Mar: $37bn); FA outflow ≈ **-$26bn/mo** |
| JPM | 2026-06-03 | Local FDI-out + portfolio-out | $3bn FDI + $9bn portfolio per month |
| JPM | 2026-06-03 | Foreign portfolio outflow | **-$14bn/mo avg Q1** |
| BNP (Contextualizing record retail buying) | 2026-06-02 | Domestic retail bought KR equity | **$23.6bn in May (record)** |
| BNP | 2026-06-02 | Foreign net sold KR equity | **-$29.8bn in May** |
| BNP | 2026-06-02 | Retail outbound (RIA) | $2.5tn KRW reshored, "meaningful deceleration of outbound" |
| HSBC (FX Snap KRW – Do no harm) | 2026-05-29 | Foreign equity outflow May | ~**-$27bn** in May; 16 consecutive trading days outflow |
| HSBC | 2026-05-29 | NPS Q1 selling | -$2.3bn KR equities, +$8.7bn foreign equities |
| ANZ (KRW unfairly beaten down) | 2026-05-28 | NFC offshore holdings | Doubled to **$211bn** end-2025 (from $96bn end-2023) |
| ANZ | 2026-05-28 | Retail RIA reversal | -$3.4bn/mo Q1 → +$0.5bn (Apr) → +$1.3bn (May) onshore |
| ANZ | 2026-05-28 | Trade-side | Semi exports +202% YoY May; total exports +52.6% YoY (working-day adjusted) |
| Goldman (Foreign outflows) | 2026-05-22 | KR foreign portfolio YTD | **-$62bn YTD** |
| Goldman | 2026-05-22 | KR domestic retail YTD | **+$35bn since late Feb** |
| Barclays (Parabolic rally) | 2026-05-28 | Outflow regime change | 2026 foreign sell-rate during *rallies* doubled vs 2021-25; 89% prob of outflow on KOSPI-up day |
| Barclays | 2026-05-28 | Outflow concentration | Samsung Electronics + SK Hynix = ~ALL of 2026 foreign net selling |

### Flow narrative

The five mechanisms operating right now, summed up:

1. **Korea earns $24-37bn/month** from the current account (chip super-cycle + autos).
2. **Foreign investors recycle some of that back out by selling Korean equities** (~−$14 to −$27bn/month) — concentrated in Samsung + SK Hynix where their structural overweight is largest.
3. **Domestic retail is reabsorbing the foreign selling** (record $23.6bn buy in May) — KOSPI +35% in May (BNP) / +97% YTD (GS) is a *retail-driven* rally.
4. **Korean corporates and pension funds simultaneously deploy abroad** — NPS overseas additions, NFC offshore holdings doubling, $3bn/mo local FDI out (JPM).
5. **The Reshoring Investment Account (RIA)** is a tax-incentive flip — retail outbound is decelerating; this is the cleanest near-term outflow brake.
6. **BOK is starting to defend the KRW with reserves** (−$1.85bn in March), but small scale so far.

Net of all this: **flow > rates as a KRW driver**. JPM, BNP, ANZ all explicitly state the hawkish BoK won't fix the KRW — outflow magnitude is the binding constraint.

---

## Appendix C — Forward drivers

### NPS (National Pension Service)

Pre-eminent domestic actor. New 2026 SAA targets set 2026-05-28:

| Asset | May-2025 target | May-2026 target | End-2027 target | Delta |
|---|---:|---:|---:|---:|
| Korean equities | 14.9% | **20.8%** | 20.8% | **+5.9 pp** |
| Korean bonds | 23.7% | 21.8% | 21.8% | -1.9 pp |
| Foreign equities | 38.9% | **35.6%** | 35.6% | **-3.3 pp** |
| Foreign bonds | 8.0% | 7.4% | 7.4% | -0.6 pp |
| Alternatives | 15.0% | 14.3% | 14.3% | -0.7 pp |

(Source: HSBC #1958 — table from NPS via CEIC.)

**Implication**: NPS shifting *target* allocation toward Korea but the
*portfolio is currently still significantly over its old target* on
Korean equities. Barclays #1808 estimates rebalancing in 2026-27 will
favor domestic bonds (+KRW84tn) and overseas assets (+KRW109tn 2026,
+KRW30tn 2027), while reducing the forced sell of domestic equity (which
would otherwise have been -KRW210tn). Net: **overseas portfolio outflow
~KRW36.6tn ($25bn) in 2027** — sized but mitigable.

**FX-impact mitigation**: NPS's new FX hedging framework (live since
2026-04-15) uses a swap line with BoK to fund overseas purchases —
spot-FX-neutral. So ② Portfolio-Assets goes up on the BoP, but the FX
spot market doesn't see most of it.

### Retail RIA (Reshoring Investment Account)

Launched late March 2026. Capital-gains-tax exemption for retail
investors who repatriate foreign-equity proceeds and reinvest in
Korean equities via a designated account. Effect to date:

- 240k+ accounts opened
- ~$1.3bn / KRW2.5tn aggregate balance
- Retail outbound flow flipped from **−$3.4bn/mo (Q1)** → **+$0.5bn April → +$1.3bn May** (onshore)

Reads as a meaningful structural brake on ② Portfolio Assets going
forward, *for the retail leg specifically*. Institutional (NPS) leg
unaffected.

### Bank of Korea — hawkish pivot

- 2026-05-28 meeting: held 2.50%, but **2 dissents for an immediate hike**, and Gov. Shin (new in May): "a rate hike would have been justified at this meeting."
- Desk consensus first hike: **July 2026**, 25bp to 2.75%
- Terminal rate: **3.00%** by year-end 2026 (Barclays/BNP/ANZ all agree)
- Drivers: CPI 3.1% YoY May (above target); semi-driven growth; housing pressure; KRW weakness
- **KRW impact: limited** per BNP/JPM — flows dominate; hawkish surprise narrows the US-KR rate gap *marginally*.

### MSCI EM → DM reclassification watchlist

Annual MSCI Market Classification Review in June 2026 may put Korea on the
watchlist for reclassification from EM to DM. ANZ flags this as a
**positive catalyst for KRW**: would unlock passive DM flows into KOSPI
(net portfolio inflow on the liabilities side) and reduce the perceived
fragility of EM-bucketed Korea.

### Calendar (next 90 days)

| Date | Event | Outflow-relevant signal |
|---|---|---|
| ~Jun 10 | MSCI Market Classification Review | EM→DM watchlist? KRW catalyst |
| Jul 8-9 | BoK MPC | First hike (25bp)? |
| Early May/Jun/Jul | Monthly BoP release (BOK, T+2 lag) | Apr/May/Jun prints |
| Q3 2026 | WGBI inclusion flows | Bond inflows on liabilities side |
| Late Q3 | NPS rebalancing kicks in | Increased FX swap-funded overseas purchases |

---

## Appendix D — Data + code pointers

### Time series, monthly, by source

| Path | What | Lag | Notes |
|---|---|---|---|
| **FRED** `KORB6FATC01CXCUM` | Headline FA Assets (outflow) | T+15 mo | Through Mar 2025; 8 KR BoP series in [`playground/econ/fred/seed.yml`](../../playground/econ/fred/seed.yml) Bucket 11b |
| **KOSIS** `DT_301Y013` | Master monthly BoP, full 284-item hierarchy | T+2 mo | Through Mar 2026; pulled via [`playground/econ/kosis/fetch_bop.py`](../../playground/econ/kosis/fetch_bop.py); default download is 6 mo only — expand period selector for full history |
| **BOK ECOS API** (blocked) | Same as above, via REST | T+2 mo | Requires Korean mobile + citizenship for API key — see [`docs/admin/econ/korea/ecos_api_reference.md`](../admin/econ/korea/ecos_api_reference.md) |
| **KOSIS** `DT_301Y016` | Capital + Financial Account by counterparty region | T+12 mo (annual) | 2006-2024; bilateral outflow decomposition by country/region — not yet pulled |
| **KOSIS** `DT_311Y001` etc. | International Investment Position | Quarterly | Stock counterparts to BoP financial-account flows |
| **FRED** `KORB6CATT00CXCUM` | Narrow Capital Account balance | T+15 mo | The BPM6 narrow line (transfers + non-produced assets) |
| **KOSIS** `DT_732Y001` | Foreign Exchange Reserves | Monthly | Stock counterpart to ⑤ Reserve Assets flow |

### Code

- [`playground/econ/fred/fetch.py`](../../playground/econ/fred/fetch.py) — FRED ingest CLI
- [`playground/econ/kosis/fetch_bop.py`](../../playground/econ/kosis/fetch_bop.py) — KOSIS Playwright downloader (auto-click + manual fallback)
- [`playground/econ/kosis/capture_download.py`](../../playground/econ/kosis/capture_download.py) — Endpoint-discovery harness for new KOSIS tables
- [`playground/econ/bok_ecos/discover_bop.py`](../../playground/econ/bok_ecos/discover_bop.py) — ECOS tree explorer
- [`playground/econ/bok_ecos/stat_code_inventory.md`](../../playground/econ/bok_ecos/stat_code_inventory.md) — Full ECOS STAT_CODE inventory by branch
- [`docs/admin/econ/korea/`](../admin/econ/korea/) — full Korea econ documentation tree

### Desk research used in Appendix B

All accessible via the IMDR research store (`research.dim_report` /
`research.fact_chunk`). Report IDs:

| ID | Vendor | Date | Title |
|---|---|---|---|
| 2737 | JPM | 2026-06-03 | KRW: The woes of the won |
| 2572 | BNP | 2026-06-02 | South Korea: Contextualizing the record equity buying by domestic individuals in May |
| 1958 | HSBC | 2026-05-29 | FX Snap KRW – Do no harm |
| 1433 | ANZ | 2026-05-28 | South Korea: KRW unfairly beaten down |
| 1438 | ANZ | 2026-05-28 | Bank of Korea: hawkish pivot sets stage for July lift-off |
| 1450 | BNP | 2026-05-28 | Bank of Korea: Hawkish signals likely to lead to a rate hike in July |
| 1787 | Barclays | 2026-05-28 | Korea: BoK: The stars are aligned |
| 1808 | Barclays | 2026-05-28 | Korea: NPS raises domestic equity target weight |
| 1823 | Barclays | 2026-05-28 | Korea: The irony of the parabolic rally |
| 1909 | Barclays | 2026-05-26 | Korea: NPS Asset allocation preview: Make hay while the sun shines |
| 1165 | Goldman | 2026-05-22 | Another week of large foreign outflows, led by Korea |
| 1397 | BNP | 2026-05-26 | EM rates: Take profit on KRW 1y receiver, roll paid position |

### Public references

- IMF BPM6 manual, Chapter 6 — Financial Account: https://www.imf.org/external/pubs/ft/bop/2007/pdf/chap6.pdf
- BOK Monthly BoP press release: https://www.bok.or.kr/eng/bbs/E0000634/
- FRED Korea series catalog: https://fred.stlouisfed.org/searchresults/?st=KORB6
- KOSIS English entry: https://kosis.kr/statHtml/statHtml.do?orgId=301&tblId=DT_301Y013&vw_cd=MT_ETITLE&language=en&conn_path=E3
- IMF DSBB Korea BoP metadata: https://dsbb.imf.org/sdds/dqaf-base/country/KOR/category/BOP00

---

*Compiled by IMDR research workflow, 2026-06-03. Statistical data
verified directly against BOK source-agency metadata at [`playground/econ/bok_ecos/discovery/discover_bop_20260603T082056Z/bok_metadata_captured.md`](../../playground/econ/bok_ecos/discovery/discover_bop_20260603T082056Z/bok_metadata_captured.md).*
