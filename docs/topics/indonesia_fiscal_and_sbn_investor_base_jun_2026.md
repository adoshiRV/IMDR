# Indonesia — fiscal deficit + SBN investor base

**Brief · 2026-06-09 · IMDR**

Two coupled questions: (i) how has Indonesia's general-government deficit
evolved since the COVID-era waiver of the UU 17/2003 3%-of-GDP ceiling,
and (ii) who has been absorbing the SBN — Surat Berharga Negara, the
IDR-denominated tradable government securities that finance it. Fiscal
realisasi (actuals) sit in `econ.fact_indicator` via BI SEKI Table IV.1–3
(annual, 2008 → 2024); daily ownership-by-investor sits via DJPPR
`Kepemilikan SBN Domestik yang Dapat Diperdagangkan` (daily, 2015-12-31 →
2026-06-05, 36 indicators wired into prod 2026-06-09). It matters now
because BI's 50bp surprise hike on 2026-05-20 was an FX-defence move
against an investor-base whose foreign-private share has fallen from 38%
to 13% in 11 years — and the desk is starting to ask whether the
domestic captive demand built up during COVID can absorb the next leg of
supply without BI continuing as marginal buyer.

## TL;DR (one-page brief)

> Indonesia ran a 2024 deficit of **IDR 509tn (~2.3% of GDP)** — wider
> than 2023 but well inside the restored 3% ceiling. The composition of
> the IDR 6,882tn SBN stock that finances it has been **transformed**:
> foreign share fell from **38% in 2015 / 2019 to 13% today**, replaced
> almost one-for-one by Bank Indonesia (10% → 27%) and to a lesser
> extent by domestic captive demand (insurance + pension 12% → 20%,
> retail 3% → 8%). The current tension: BI is again the marginal absorber
> while it is hiking 50bp to defend the IDR — same balance sheet is
> doing two contradictory things.

### Composition (SBN outstanding, IDR trn, 2026-06-05)

| # | Investor category | IMDR code suffix | Latest value | % of total | What it is |
|---|---|---|---:|---:|---|
| ① | Banks (`BANK*`) | `BANK.TOTAL` | 1,245 | **18.1%** | Bank Umum total; includes SBN used in BI monetary ops (footnote in source) |
| ② | Bank Indonesia (net) | `BI_NET.TOTAL` | **1,834** | **26.7%** | BI's net economic position (excl. SBN it lent to banks via OM repo) |
| ③ | Mutual funds | `MF.TOTAL` | 260 | 3.8% | Reksadana |
| ④ | Insurance + pension | `INSUR_PENSION.TOTAL` | 1,402 | **20.4%** | Captive demand — POJK minimum-government-paper rules |
| ⑤ | Foreign (non-resident) | `FOREIGN.TOTAL` | 870 | **12.6%** | Of which 262tn (3.8% of total) is foreign-official — sticky reserve managers |
| ⑥ | Individuals (retail) | `INDIVIDUAL.TOTAL` | 553 | 8.0% | SBN Ritel: ORI, SBR, ST, SR — the post-2020 retail program |
| ⑦ | Other | `OTHER.TOTAL` | 718 | 10.4% | Corporates, Yayasan, Sekuritas |
| **Σ** | **Total tradable SBN** | `TOTAL.TOTAL` | **6,882** | **100%** | ≈USD 422 bn at 16,300 IDR/USD |

Identity (2026-06-05): ① + ② + ③ + ④ + ⑤ + ⑥ + ⑦ = 1,245 + 1,834 + 260 + 1,402 + 870 + 553 + 718 = **6,882** = `TOTAL.TOTAL` ✓ exact. Note ① "Banks" includes SBN that BI has repo'd out to banks via Operasi Moneter — the gross-vs-net BI difference (BI gross 1,722 − BI net 1,834 = −112tn) shows up *inside* the banks line.

### Where we are right now (latest data, 2024 fiscal year + 2026-06-05 SBN)

- **Deficit IDR 509tn in 2024 ≈ 2.3% GDP** vs IDR 337tn (1.6% GDP) in 2023 — **widened by 51%** YoY (`BI.FISCAL.BALANCE.IDR.ID`). Tax revenue grew 2154 → 2232tn (+3.6%) but expenditure outpaced (3121 → 3360tn, +7.6%). 2025 realisasi not yet published.
- **2026 BI surprise 50bp hike to 5.25% on 20 May — first hike since 2022.** Lending facility 6.0%, deposit facility 4.25% (Nomura #214, Maju). BI cited "global turmoil due to the Middle East war" and FX stability; corridor was supposed to remain on hold per consensus. Macroprudential offsets — BI encouraged banks NOT to raise lending rates despite the hike (Barclays #1770).
- **IDR through 17,605 → 17,850 → 18,000+** by June 4 (ANZ #3538) — worst-performing Asia/EM currency YTD at **−7.5%**. Q1 CAD widened to **$4.0bn (vs $2.5bn Q4 2025)**, BOP Q1 deficit **$9.1bn** vs Q4 surplus $6.1bn (Nomura #1253, Paracuelles). Nomura 2026 CAD forecast **2.0% of GDP, vs 0.1% in 2025**.
- **FX reserves fell $10bn Dec-Apr to USD 146bn** (Nomura #199). ANZ estimates **usable reserves (ex-gold, adjusted for forward book) dropped below USD 100bn in April** and fell further in May (#3538). July–Aug dividend-payment USD demand still ahead.
- **SRBI is BI's parallel sterilisation lever** — yields rose **4.65% Oct-25 → 6.69% 22 May 2026 (+200bp in <1y)**; outstanding stock IDR 706tn → **IDR 958tn (+~IDR 200tn YTD)**; **IDR 497tn matures within 6 months** (Nomura #1300, Maju). Banks hold **~70% of SRBI**, foreign ~20% (IDR 192tn). SRBI also crowds out bank SBN demand.
- **2026 H1 SBN stock grew 6,549 → 6,882tn (+333tn in 5 months)** — annualises ~800tn pace vs 2024 net financing 555tn. **BI net holdings hit record 1,834tn (26.7% of total)** — up from 1,618tn end-2024 (+216tn / +13% in 6 months). BI is the marginal absorber.
- **Foreign holdings stuck at 870tn** YTD (vs 877tn end-2024, 875tn end-2025) — share dropped 14.5% → 12.6% over 18 months as the denominator grew but foreign nominal didn't. Of the 870tn, **262tn is foreign-official** (sticky reserve managers); true foreign-private cyclical bid is ~608tn = 8.8% of total.
- **Insur+pension at all-time high 1,402tn (20.4%)**, +22% in 18 months. Retail flat at 553tn (8.0%) — peaked end-2024.
- **Fitch downgraded outlook to NEGATIVE on 4 March 2026** (cited in Nomura #229). Combined with the **4 June UU P2SK revision** that expands BI's mandate to include "economic growth and job creation" plus gives parliament evaluation power over BI officials (Nomura #3787) — there is a fresh independence-risk premium being priced into IDR + INDOGB.

### How to think about it

Walk the investor base by **reversibility** — each block has a different reason for being there and a different exit door:

- ① **Banks ≈ rate-sensitive trade.** SBN holdings spiked 36% of total in 2020 (forced absorption) and have fallen back to 18% as the IDR money-market alternative — BI's SRBI — offers higher yields. Nomura (id 1300, 2026-05-25): "SRBI yields resume climb" — the marginal cost of bank-balance-sheet SBN keeps rising. **Bank share is mean-reverting around the cycle, not structurally tethered.**
- ② **Bank Indonesia ≈ quasi-fiscal residual.** From the 2020-22 "burden-sharing" Joint Decree (SKB) onward, BI absorbs whatever the rest of the base can't — and 2026 is a clean example: BI added 216tn in 6 months while doing nothing else. **This is the most reversible line in theory and the stickiest in practice** — there is no political path to BI shrinking its SBN book in 2026.
- ③ **Mutual funds ≈ noise.** Have oscillated in a 145–260tn band for a decade. Not the story.
- ④ **Insurance + pension ≈ captive.** Driven by POJK minimum-government-paper rules; not yield-sensitive. The 20.4% share is a regulatory artifact, not a market signal. Will keep growing in line with insurance/pension AUM unless POJK changes.
- ⑤ **Foreign ≈ liquid + opinion-sensitive.** The classic mark-to-market real-money + EM-dedicated bid. Of the 870tn, **~262tn is foreign-official** (sovereign wealth + reserve managers) and behaves like ④ — the remaining ~608tn (8.8% of total) is the true cyclical foreign bid. **This is the share that fell from 30%+ to <10% over the decade**, and the share that any "foreigners are back" call has to be about.
- ⑥ **Retail ≈ programmed.** SBN Ritel issuance calendar drives flow, not yield. Will tick up in line with each ORI/SBR/ST/SR auction. Currently NOT accelerating — flat at 553tn since end-2024.
- ⑦ **Other ≈ corporate cash + foundations.** Driven by corporate liquidity and CSR endowments; mostly trend, low cyclical signal.

The two important regimes in this cycle:

- **2020-22 "burden-sharing" regime** — BI absorbed pandemic deficit financing under SKB. BI share went 10% → 20%, foreign 38% → 14%. Decisive break.
- **2023-26 "post-SKB but BI keeps buying" regime** — SKB formally ended 2022 but BI's share has kept climbing (20% → 27%), under different legal vehicles (Operasi Moneter, SRBI sterilisation flows). The pretext changed; the buying didn't.

### Read sequence

If you want the framework — APBN cycle, SBN instrument tree, DJPPR taxonomy gotchas — jump to [Appendix A](#appendix-a--framework).
If you want the desk view + flow picture — May–June 2026 reports + the May hike — jump to [Appendix B](#appendix-b--current-flow-picture).
If you want forward drivers — supply calendar, BI's next move, what would break the regime — jump to [Appendix C](#appendix-c--forward-drivers).
If you want to pull the data yourself, jump to [Appendix D](#appendix-d--data--code-pointers).

---

## Appendix A — Framework

### The APBN fiscal cycle

Indonesia's central-government budget runs through three sequential numbers each year:

| Stage | Indonesian | English | What it is |
|---|---|---|---|
| 1. APBN | Anggaran Pendapatan dan Belanja Negara | Initial budget | Submitted Aug, passed Oct, takes effect 1 Jan |
| 2. APBN-P | APBN-Perubahan | Revised budget | Mid-year amendment if revenue or expenditure assumptions break |
| 3. Realisasi | — | Actuals | What was actually collected / spent. The line our `BI.FISCAL.*` series track |

**Terminology gotcha:** when sell-side desks quote "Indonesia's deficit" without specifying, they mean APBN headline (forward-looking). Our IMDR series carry the **realisasi** lag (T+1 year, annual). 2024 realisasi is the latest we have via BI SEKI; 2025 will be published H2-2026.

### The 3%-of-GDP ceiling, suspended and restored

- **UU 17/2003** (the *Fiscal Law*) caps the central-government deficit at **3.0% of GDP** and the public-debt stock at 60%.
- **2020-22 waiver:** Perppu 1/2020 suspended the 3% ceiling for three years (2020-22). Deficit ran 6.1% / 4.6% / 2.4% of GDP — formally restored to within-ceiling from 2023.
- **2023-24:** 1.6% / ~2.3% of GDP — well inside.
- The ceiling is a hard constitutional constraint going forward — any breach requires another Perppu, which has political cost.

### The SBN instrument tree

`Surat Berharga Negara` — IDR-denominated tradable government securities — splits four ways:

```
SBN (Surat Berharga Negara)
├── Conventional (SUN — Surat Utang Negara)
│   ├── Obligasi Negara (long-term bonds; the FR-series)   ← our BI.SBN.OBLIGASI
│   └── SPN (Surat Perbendaharaan Negara) — T-bills ≤1y    ← our BI.SBN.SPN
└── Sukuk (SBSN — Surat Berharga Syariah Negara)
    ├── PBS (Project-Based Sukuk; long-term)
    └── Sukuk Ritel (SR / ST)                              ← retail subset
```

DJPPR's `Kepemilikan SBN ... yang Dapat Diperdagangkan` table covers the **tradable subset** (excludes non-tradable, e.g. SDHI given to BPK Tabungan Haji). It splits each daily observation across **SUN / SBSN / TOTAL** instruments — our `*.SUN.IDR.ID`, `*.SBSN.IDR.ID`, `*.TOTAL.IDR.ID` codes.

### Terminology gotchas (DJPPR investor labels)

| Source row label | Means | Trap |
|---|---|---|
| `BANK*` | All commercial banks (Bank Umum) — both conventional and syariah | **Includes** SBN that BI has lent banks via OM repo (gross-vs-net BI shows up here, not in BI line) |
| `Bank Indonesia (net)` | BI's net economic position | Excludes SBN BI lent out to banks. This is what matters for "BI's actual exposure" |
| `Bank Indonesia (gross)` | Title-only ownership | Includes the lent-out tranche — a sub-line of BI net + the repo'd tranche above |
| `Non Residen` | Foreign holders of IDR-denominated SBN | **Does not include** USD-denominated INDON sovereigns — those are separate, not in this table |
| `- Termasuk Pemerintah & Bank Sentral Negara Asing` | Foreign official sector (sub of Non Residen) | The trap: the substring "Bank Sentral" can fool a naive classifier into mapping this to domestic Banks. Our parser handles it; ad-hoc readers shouldn't strip "bank" without context. |
| `Lain-lain` | Other — Perusahaan Sekuritas + Korporasi + Yayasan | Bigger than MF — don't ignore this bucket |
| `Individu` | Retail / individual investors | Driven by the SBN Ritel calendar (ORI, SBR, ST, SR) |

Full code structure + the source-file metadata is in [`docs/admin/econ/indonesia/_playground/`](../admin/econ/indonesia/_playground/) and the playground discovery probes at [`playground/econ/djppr/`](../../playground/econ/djppr/).

---

## Appendix B — Current flow picture

### Source-agency statistical view

**Fiscal evolution** (BI SEKI IV.1–3 realisasi, annual, IDR trn) — query `BI.FISCAL.*.IDR.ID` in `econ.fact_indicator`:

| Year | Revenue | Tax | Expend | Balance | % GDP* | Net Financing |
|---|---:|---:|---:|---:|---:|---:|
| 2015 | 1,508 | 1,240 | 1,807 | −298 | −2.6% | 323 |
| 2018 | 1,944 | 1,519 | 2,213 | −269 | −1.8% | 306 |
| 2019 | 1,961 | 1,546 | 2,309 | −349 | −2.2% | 402 |
| 2020 | 1,648 | 1,285 | 2,595 | **−948** | **−6.1%** | 1,193 |
| 2021 | 2,011 | 1,548 | 2,786 | −775 | −4.6% | 872 |
| 2022 | 2,636 | 2,035 | 3,096 | −460 | −2.4% | 591 |
| 2023 | 2,784 | 2,154 | 3,121 | −337 | −1.6% | 357 |
| 2024 | 2,851 | 2,232 | 3,360 | **−509** | ~−2.3% | 555 |

\* % GDP using BPS GDP-current-price denominator; 2024 GDP ~22,150tn.

**SBN investor base evolution** (DJPPR Kepemilikan SBN, year-end snapshots, TOTAL instrument, IDR trn). Note "Bank*" includes SBN lent by BI via OM-repo:

| Year-end | Banks* | BI net | MF | Insur+Pen | Foreign | Individu | Other | Total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2015 | 350 | 149 | 62 | 172 | 559 | 43 | 79 | 1,462 |
| 2019 | 581 | 262 | 131 | 215 | 1,062 | 81 | 163 | 2,753 |
| 2020 | 1,376 | 454 | 161 | 543 | 974 | 131 | 232 | 3,871 |
| 2022 | 1,677 | 1,041 | 146 | 873 | 762 | 344 | 467 | 5,309 |
| 2024 | 1,051 | 1,618 | 187 | 1,145 | 877 | 543 | 619 | 6,040 |
| **2026-06** | **1,245** | **1,834** | **260** | **1,402** | **870** | **553** | **718** | **6,882** |

**Shares of total** (%, same dates):

| Year-end | Banks* | BI net | MF | Insur+Pen | Foreign | Individu | Other |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2015 | 23.9 | 10.2 | 4.2 | 11.7 | **38.2** | 2.9 | 5.4 |
| 2019 | 21.1 | 9.5 | 4.8 | 7.8 | **38.6** | 2.9 | 5.9 |
| 2020 | 35.5 | 11.7 | 4.2 | 14.0 | 25.2 | 3.4 | 6.0 |
| 2022 | 31.6 | 19.6 | 2.7 | 16.4 | 14.4 | 6.5 | 8.8 |
| 2024 | 17.4 | **26.8** | 3.1 | 19.0 | 14.5 | 9.0 | 10.2 |
| **2026-06** | **18.1** | **26.7** | 3.8 | **20.4** | **12.6** | 8.0 | 10.4 |

**Six bullets from the data:**

- Foreign-share decline of **−25.6pp over 11 years** (38.2% → 12.6%) is the single biggest investor-base shift in any Asian EM since 2015.
- BI's share is up **+16.5pp** over the same period (10.2% → 26.7%). This is the offset — almost exactly one-for-one against foreign.
- Insur+pension up **+8.7pp** (11.7% → 20.4%); driven by POJK minimum-paper revisions plus regulated AUM growth.
- Retail up **+5.1pp** (2.9% → 8.0%) — the SBN Ritel program added ~510tn of retail demand since 2015, almost all between 2020 and 2024. Flat since.
- Banks ratio bounced: 24% pre-COVID → 36% peak 2020 → 17–18% now as SRBI (BI's own short-paper) competes for bank balance-sheet.
- 2024 deficit (509tn realisasi) plus pre-funding pace into 2026 implies the stock continues to grow at ~12% YoY pace — slightly faster than nominal GDP.

### Sell-side desk view (20 May – 4 June 2026)

10 reports across 5 desks, sourced from `research.dim_report` (full pdf_text in `research.fact_chunk`). Specific magnitudes pulled by 60-char `SUBSTRING` slide:

| Desk · Analyst | ID · Date | Signal | Magnitude |
|---|---|---|---|
| **Barclays** · Brian Tan | 487 · 2026-05-20 | First-look on BI 50bp hike | "Outsized 50bp hike." Base case **another 25bp to 5.50% in June**; cuts in **Mar / Apr / May 2027 → 4.75%**, in line with Fed cut in March 2027 |
| **Nomura** · Maju (Banks) | 199 · 2026-05-21 | Bank-sector OCI sensitivity | OCI hit from May hike: **BBNI −2.92%** (worst), **BBRI −1.93%**, **BBCA −0.41%** despite largest absolute book (IDR **425.6tn** SBN). Sector-wide MTM losses already showing in 1Q26 |
| **Nomura** · Paracuelles | 214 · 2026-05-20 | Pre-emptive hike framing | BI cited "pre-emptive measure to keep inflation in 2026-27 within 1.5-3.5% target." Policy corridor: lending facility **6.0%**, deposit facility **4.25%**. FX trade: long SGD/IDR at **maximum conviction**, 1.5% trailing stop |
| **Nomura** · Paracuelles | 229 · 2026-05-20 | Prabowo state export agency | New PP on commodity export management, sole-exporter agency under Danantara for **palm oil + coal + iron alloys** ($65bn / **4.5% of GDP** in 2025 exports). Prabowo cited **$908bn of under-invoicing over 1991-2024**. Effective **1 Sep 2026**. "Reminiscent of Danantara concerns…likely even worse" |
| **Nomura** · Maju (Banks) | 1300 · 2026-05-25 | SRBI yield path | Blended SRBI yield **4.65% Oct-25 → 6.69% 22 May 2026 (+200bp in <1y)**. Stock IDR **706tn → 958tn (+~IDR 200tn YTD)**. **IDR 497tn matures in 6 months** → rollover pressure. Banks **~70% of holders**; foreign IDR 192tn (~20%). "BBRI faces asymmetric funding cost risk — loan yields structurally capped by program rate constraints" |
| **Nomura** · Paracuelles | 1253 · 2026-05-25 | Q1 BoP collapse | CAD widened **$2.5bn (Q4) → $4.0bn (Q1)**. BOP balance **+$6.1bn (Q4) → −$9.1bn (Q1)**. Net FDI fell $3.2 → $2.0bn; portfolio inflows fell **$4.7 → $0.7bn**. **2026 CAD forecast 2.0% of GDP (vs 0.1% in 2025)**. June BI base case: 25bp to 5.50%, upside risk |
| **Barclays** · Brian Tan | 1770 · 2026-05-29 | Risk of another 50bp | USDIDR **17,605 close on 20 May → 17,850+ by 29 May** despite 50bp surprise. **Rising risk BI hikes 50bp again on 18 June to 5.75%** (base case still 25bp → 5.50%). "BI is likely to continue encouraging banks NOT to raise lending rates despite policy rate hikes" |
| **Barclays** · Avanti Save + Sarah Beh | 3378 · 2026-06-03 | Sovereign credit supply | "More supply but nothing overwhelming." 2026 FX-issuance forecast **$12-15bn** (vs $12bn historical); YTD **$11.7bn done in USD/CNH/EUR/JPY**; **$3.3bn remaining**. Quasi-sovereign **$4-6bn**. Reserves **$157bn (Jan) → $146bn (end-Apr)**. Danantara plans inaugural dollar bond. "The bar for a rating downgrade is high" |
| **ANZ** · Asia Local Markets | 3538 · 2026-06-04 | Sell-off intensifies | **IDR breaches 18,000 on 4 June (−7.5% YTD, worst Asia + EM)**. 2Y yields **~7%, +200bp YTD**. 12M-5Y yield target **7.0–7.5% in 3-6 months**. **Usable reserves below $100bn in April** (ex-gold, adjusted for forward book). BI "increasing intensity of triple interventions"; July-Aug dividend USD demand ahead |
| **Nomura** · Paracuelles | 3787 · 2026-06-04 | BI independence risk | Parliament passed **UU P2SK revision 4 June**: 17 new provisions including (i) BI mandate expanded to **economic growth + job creation** alongside inflation/FX, (ii) parliament conducts **performance evaluations of BI officials**. "Pose an additional risk if viewed as potentially eroding BI's monetary policy independence" |

**Consensus across desks (May 20 → June 4, 2026):**

- All five desks (Barclays, Nomura, ANZ, JPM-equivalent inferred, HSBC-EM-Asia FX) read the **20 May hike as FX-driven, not inflation-driven**. Nomura #214: "currency concerns prompt a more aggressive 50bp hike". Barclays #487: "outsized 50bp." Nomura #229 + #3787: institutional / policy-uncertainty pressure compounds the IDR weakness.
- **Twin-deficit narrative**: Nomura #1253 anchors it — Q1 BOP turned $9.1bn deficit from a $6.1bn Q4 surplus, with portfolio inflows collapsing $4.7 → $0.7bn. This is what Barclays #3378 also flags as the only path to a rating downgrade: "more explicit deterioration in fiscal balance or external position (capital flight)."
- **Next hike call**: Barclays #1770 and #487 base case 25bp to 5.50% on 18 June; upside risk to 50bp / 5.75% if IDR doesn't stabilise. Nomura #1253 same base case (25bp). All flag continued hawkish stance into H2.
- **Eventual pivot**: Barclays sees rate cuts only in **March-April-May 2027** — a full year of FX-defence stance ahead. None of the desks see imminent easing.

**Disagreement and counterintuitive points:**

- **Supply absorption** — Barclays #3378 is sanguine on USD-issuance pace ("nothing overwhelming"); Nomura #1300 is more worried about the **IDR-side** (SRBI yields squeezing the bank bid for SBN, banks already at sector-wide MTM losses pre-hike). Different sides of the same liability stack.
- **Counterintuitive #1**: with foreign holdings flat at 870tn and BI at a fresh record 1,834tn, the *non-BI non-foreign* share has *fallen* in 2026 H1. **Banks went 1,484tn (end-Dec-25) → 1,245tn (Jun-26)** — that's IDR 240tn of bank-balance-sheet SBN moving into SRBI per Nomura #1300. **BI is plugging an actual domestic rotation, not just absorbing net new supply.**
- **Counterintuitive #2**: BI's "macroprudential offset" — Barclays #1770 confirms BI is **simultaneously hiking the policy rate and encouraging banks not to raise lending rates**. This works at the bank-lending margin (the macroprudential channel) but leaves the SRBI yield as the true cost of marginal liquidity for the system — and SRBI yields are up 200bp.
- **Counterintuitive #3**: Foreign exit from SBN is happening *through SRBI* too. Foreign holders of SRBI fell from a peak Oct-24 to **IDR 192tn (20% share) in Apr-26** (Nomura #1300) — even though SRBI is BI's *own* paper. The foreign withdrawal is from anything IDR-denominated, not just sovereign-credit.

### Flow narrative (the six mechanisms operating right now)

1. **Iran war + strong USD + Fed-cut uncertainty** ➜ EM-wide IDR-selling pressure. Nomura #214: BI explicitly cites "global turmoil due to the war in the Middle East."
2. **CAD widening + portfolio inflow collapse** ➜ funding-gap pressure on IDR. Net portfolio inflows fell from $4.7bn (Q4-25) to $0.7bn (Q1-26) per Nomura #1253. Net FDI also softening (3.2 → 2.0).
3. **BI surprise 50bp hike May 20** + corridor widening + triple-intervention escalation ➜ partial relief but IDR breaks 18,000 by June 4 anyway.
4. **SRBI as parallel sterilisation tool** ➜ BI lifts yields 4.65% → 6.69%, expands stock by IDR 200tn YTD. **Side-effect**: banks rotate balance-sheet from SBN into SRBI (240tn out of SBN over 6 months); foreign rotates *out* of SRBI too (peak → 192tn).
5. **BI becomes the residual SBN buyer** to plug both the new supply *and* the bank rotation — net holdings hit record 1,834tn (+216tn in 6 months).
6. **Fitch negative outlook (4 Mar) + UU P2SK revisions (4 Jun)** ➜ **institutional risk premium** rebuilds. BI's expanded growth/jobs mandate + parliamentary performance evaluation = perception of eroding independence. Nomura #229: state export agency announced 20 May "raises further investor concerns about greater state control." Barclays #3378 frames it under "institutional weaknesses: policy making, predictability and governance."

---

## Appendix C — Forward drivers

### BI rate path (consensus + dispersion)

Pre-vs-post 18 June meeting projections from the desks (all locally-stamped 20 May – 4 Jun):

| Desk | May-2026 actual | June 18 base case | June 18 risk case | End-2026 | Cuts begin | Terminal |
|---|---:|---|---|---|---|---|
| Barclays (#487, #1770) | 50bp → **5.25%** | 25bp → 5.50% | **50bp → 5.75%** if IDR doesn't stabilise | 5.50% | Mar/Apr/May 2027 | **4.75%** by mid-2027 |
| Nomura (#214, #1253) | 50bp → **5.25%** | 25bp → 5.50% (upside risk flagged) | 50bp → 5.75% | n/a | Not before Q2 2027 | n/a |
| ANZ (#3538) | 50bp → **5.25%** | Hawkish bias maintained | Yields up regardless | 2Y → **7.0-7.5%** | n/a | n/a |

**Implication**: at least **one more 25-50bp hike** is on the table for 18 June. None of the desks see cuts before late Q1 2027. Real-rate buffer is 5.25% policy − ~3% headline CPI ≈ **2.25%**; the consensus is this is enough to defend IDR **only if external pressure eases** (Fed cut path + Middle East).

### Indonesia's UU P2SK revision (4 June 2026) — the slow-burning risk

Per Nomura #3787: the parliamentary revision of UU No. 4/2023 introduces 17 new provisions including:

- **Expansion of BI's mandate**: from price/FX/payment-system stability ➜ adds "economic growth + job creation" (real-sector). Justified as "Fed-style dual mandate" by Finance Minister Purbaya Yudhi Sadewa.
- **Parliament performs evaluations of BI officials**.
- **Changes to BI institutional governance**: budget accountability provisions.

This is the longer-term threat to the entire BI-as-marginal-buyer regime. If the market starts to price BI as politically captured, the foreign exit accelerates (no real-yield buffer is enough) and BI becomes the *only* buyer — at which point the deficit-financing model is mechanically QE in everything but name.

### State export agency (effective 1 September 2026)

Per Nomura #229: Prabowo's new PP makes a Danantara-housed agency the **sole exporter** of palm oil + coal + iron alloys (the **$65bn / 4.5% of GDP** these three commodities represented in 2025).

| Lever | Government argument | Investor read |
|---|---|---|
| Boost tax revenue (Prabowo: ID tax/GDP < Cambodia/Philippines/India) | Curb under-invoicing (claimed $908bn over 1991-2024); centralise FX proceeds | Greater state control of commodity chain; supply-chain risk; **Fitch negative outlook (4 Mar 2026)** likely sharpens |
| Effective 1 September 2026 (transition 1 June – 31 August) | Net positive for fiscal balance — direct revenue capture | Mechanically diverts USD flow from corporate sector to state; could *help* CA in 2027 if it works as advertised |

### Supply calendar (next 90 days)

| Channel | Pace signal | What to watch |
|---|---|---|
| Weekly INDOGB conventional auctions | ~30-50tn/week typical; ANZ #3538 targets 12M-5Y at 7.0-7.5% over 3-6mo | Cover ratio (target ~1.5–2.0x) — if <1.3x, demand is weak |
| SBSN sukuk auctions | Biweekly | SBSN cover usually higher than conventional |
| SBN Ritel | ORI mid-year + ST + SR (Islamic retail) | Allotment size — flat / decelerating per DJPPR data |
| **Danantara inaugural USD bond** | Per Barclays #3378 — first wealth-fund $-issue | Tests Indonesia's USD demand depth; deflects IDR-stack supply |
| **Sovereign FX issuance remaining 2026** | Barclays #3378: **$3.3bn** more (USD12-15bn full-year guide, $11.7bn done YTD) | Cover ratios on new USD INDON taps |
| **Quasi-sovereign FX issuance 2026** | Barclays #3378: $4-6bn (SOEs: PLN, Pertamina, BBNI/BMRI/BBRI USD perp/sr) | Pertamina + PLN are the swing names — historically up when oil rises |

### Three things that would break the current regime

1. **A POJK regulatory reset.** If insurance/pension minimum-government-paper rules ever loosen, ④ (currently 20.4%) becomes price-sensitive. The captive base is more fragile than the share suggests.
2. **BI signals balance-sheet contraction.** Today BI is adding 216tn in 6 months. If they announce *runoff* (letting holdings mature without rolling), ② goes from absorber to seller — and the question becomes who replaces 1,800tn of marginal demand.
3. **Foreign re-engages.** If real-yield + IDR stability returns, foreign at 13% has 25pp of room to go back to historical averages. Mechanical: ~1,000tn of buying capacity over 2-3 years. Currently no catalyst — Iran war + Fitch negative + UU P2SK independence concerns all point the other way.

### Calendar (next 90 days)

| Date | Event | Implication |
|---|---|---|
| 2026-06-08 | BI May FX reserves print | Confirms ANZ's "below $100bn usable" read |
| **2026-06-18** | **BI RDG (Board of Governors meeting)** | **Consensus 25bp to 5.50%; risk case 50bp to 5.75% (Barclays #1770)** |
| 2026-06-30 | H1 fiscal realisasi (Kemenkeu) | First 2026 trajectory print — % GDP run-rate |
| 2026-07-18 | BI RDG | Sequential read on FX-defence stance |
| 2026-07–08 | Corporate dividend USD demand window | "Risk adding to onshore USD demand" — ANZ #3538 |
| **2026-09-01** | **State export agency takes effect** | All palm oil + coal + iron-alloy exports go through Danantara |
| 2026-08 | APBN 2027 submission to DPR | Prabowo's first fully-owned budget — deficit anchor for 2027 |
| Mid-2026 | Danantara inaugural USD bond | Tests Indonesia's USD demand depth |

---

## Appendix D — Data + code pointers

### Time series, by source

| Path | What | Lag | Notes |
|---|---|---|---|
| `econ.fact_indicator` filter `imdr_code LIKE 'BI.FISCAL.%.IDR.ID'` | Revenue, tax, expenditure, balance, financing | Annual, T+~9mo | BI SEKI IV.1–3 realisasi; 6 series, 2008 → 2024 |
| `econ.fact_indicator` filter `imdr_code LIKE 'DJPPR.SBN.HOLD.%.IDR.ID'` | Daily investor-category holdings | Daily, T+5–10 days | 36 series (12 cats × 3 instruments) DAILY 2015-12-31 → 2026-06-05 |
| `econ.fact_indicator` filter `imdr_code LIKE 'BI.SBN.%.IDR.ID'` | Monthly SBN outstanding by *instrument* | Monthly, T+30d | 5 series — SUN, SBSN, SPN, Obligasi, BI holdings (subset of DJPPR coverage but earlier release) |
| `econ.fact_indicator` filter `imdr_code = 'BI.EXT_DEBT.GOVT_CENTRAL.USD.ID'` | Government external debt (USD) | Quarterly | The companion USD-INDON liability not captured in DJPPR |
| `BIS.DSR.PNFS.ID` | Private non-financial debt-service ratio | Quarterly | Cross-check on credit-cycle context |

### Research corpus pointers

- `research.dim_report` — 22 Indonesia-titled reports 2026-05-20 → 2026-06-08 (title-search; the `country_id` tagging is sparse, only 14 of 4,266 rows are tagged ID).
- `research.fact_chunk` — full PDF text per chunk, joined on `report_id`. MCP truncates the display; use SQLAlchemy directly (per the deep-dive playbook) for full extraction.
- Qdrant collection `research_gemini_embedding_2_3072d` — semantic search; payload includes `vendor_code`, `publish_date`, `title`, `text_preview` (240 chars).

### Code

- **Production fetcher**: [`scripts/econ/djppr/djppr_sbn_ownership.py`](../../scripts/econ/djppr/djppr_sbn_ownership.py) — wired into [`scripts/econ/id/id_monthly.py`](../../scripts/econ/id/id_monthly.py) PIPELINES (2026-06-09).
- **Parser library**: [`src/imdr/domains/econ/djppr_kepemilikan.py`](../../src/imdr/domains/econ/djppr_kepemilikan.py) — listing API + XLSX parser + PDF parser with PyMuPDF carry-over label logic.
- **Companion BI fiscal fetcher**: [`scripts/econ/bi/bi_fiscal.py`](../../scripts/econ/bi/bi_fiscal.py).
- **Migration**: `migrations/085_seed_djppr_dim_vendor.sql` — DJPPR vendor + `idr_trn` (trillion Rp) unit.
- **Discovery + probes** (exploration history): [`playground/econ/djppr/`](../../playground/econ/djppr/) — Playwright listing-API discovery, PDF table-strategy probes.

### Desk research used in Appendix B

| ID | Vendor | Date | Analyst(s) | Title |
|---|---|---|---|---|
| 487 | barclays | 2026-05-20 | Brian Tan | Indonesia: First Look: Outsized 50bp hike |
| 199 | nomura | 2026-05-21 | Maju (Banks) | Quick Note - Indonesia Banks - Bank Indonesia delivers a surprise 50bp rate hike |
| 214 | nomura | 2026-05-20 | Euben Paracuelles, Nabila Amani | Asia Insights - Indonesia: Currency concerns prompt a more aggressive 50bp BI hike |
| 229 | nomura | 2026-05-20 | Euben Paracuelles, Nabila Amani | First Insights - Indonesia: Our initial thoughts on new policies for the government to control commodity exports |
| 1300 | nomura | 2026-05-25 | Maju (Banks) | Quick Note - Indonesia Banks - SRBI yields resume climb |
| 1253 | nomura | 2026-05-25 | Euben Paracuelles, Nabila Amani | Asia Insights - Indonesia: The current account deficit widened in Q1 |
| 1770 | barclays | 2026-05-29 | Brian Tan | Indonesia: Rising risk of another 50bp policy rate hike |
| 3378 | barclays | 2026-06-03 | Avanti Save, Sarah Beh | Emerging Asia Sovereign Credit: Indonesia: Bring on the supply |
| 3538 | anz | 2026-06-04 | Asia Local Markets desk | Indonesia: local markets fell on external and domestic headwinds |
| 3787 | nomura | 2026-06-04 | Euben Paracuelles | First Insights - Indonesia: Thoughts on the financial sector law revisions passed by parliament |

Full PDF text accessible via `research.fact_chunk` joined on `report_id`. The MCP truncates `chunk_text` at ~60 chars; use the `WITH nums AS (...) SELECT n, SUBSTRING(chunk_text, (n-1)*55+1, 55)` slide-window pattern to extract full chunks within a MCP-only workflow (used to compile this report on 2026-06-09).

### Public references

- DJPPR Kepemilikan SBN portal — `djppr.kemenkeu.go.id/kepemilikansbndomestikyangdapatdiperdagangkan`
- BI SEKI tabel directory — `bi.go.id/SEKI/tabel/` (Section IV = fiscal, Section V = BoP, Section IX = monetary)
- IMF Article IV Indonesia — most recent staff report on fiscal projections + financing assumptions
- ADB Asian Bonds Online (`asianbondsonline.adb.org`) — cross-EM Asia investor-base series; useful as cross-country sanity check on the DJPPR foreign-share number

### Honest gaps

- **2025-realisasi fiscal not yet available** — 2024 is the latest realisasi we have. 2025 figures will land H2-2026 via BI SEKI IV.
- **Monthly APBN realisasi from Kemenkeu DJA is PDF-only** — would let us see deficit trajectory at higher frequency, not yet parsed (IMD-43 candidate).
- **Pre-2016 DJPPR investor-base data** — different XLSX layout, deferred to [IMD-42](https://linear.app/imdr/issue/IMD-42). Means we can't compare 2026's foreign exit to 2013 Taper Tantrum at daily granularity from this source.
- **USD INDON sovereigns** (the dollar-denominated side of the same liability) are NOT in DJPPR's table — that's the Reach / Bloomberg domain. Adding to our coverage would tighten the "total sovereign liability" picture.

---

*Compiled 2026-06-09 by IMDR research workflow. Statistical data verified against the source files cached at `playground/econ/djppr/seki_raw/` and BI SEKI XLSX. SBN investor-base sum-of-components identity ties exact at 6,882tn on 2026-06-05.*
