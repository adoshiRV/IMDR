# Quick Monitor — India data audit

> **Companion to the master spec** [`../quick_monitor.md`](../quick_monitor.md) — this file is the
> ticker-by-ticker reference detail, not a competing spec. Read the master for the reconciled data
> state (India ~1,580 active econ indicators as of 2026-07-22) + the completion punch-list.

**Reference:** `data/quick_monitor/Market India 1.xlsm` (sheets: `India`, `Government Bonds`,
`Soverignratings`). **Audited:** 2026-07-17, against IMDR. **Tickers extracted:** 161 on the
`India` sheet (the core monitor). The `Soverignratings` sheet is a 550-name issuer lookup list
(peripheral); `Government Bonds` is a derived curve sheet with no external tickers.

Verdict key: ✓ held & fresh · ◐ derivable / partial · ✗ gap.

## Headline

**The rates + FX + vol + macro core is fully recreatable from IMDR.** USD/INR spot·forwards·vol,
the onshore (OIS/MIBOR) and offshore (MIFOR) swap curves, CPI/GDP/BoP/fiscal/reserves, REER, and
FPI flows all exist and are fresh to today. **Genuine gaps are four blocks:** the **govt-bond
curve** (and everything derived off it — bond-swap spreads, bond flies), **single-name CDS**,
a handful of **market-context indices** (DXY, ADXY, UST cash 10y, Brent), and the **onshore-vs-offshore
nuance** on forwards/vol (IMDR holds the offshore/NDF cut; onshore is partial).

Rough recreatability: **~80% of tiles today**; the rest is one pipeline (govt bonds) + a few
context feeds + a CDS-source decision.

## Panel-by-panel coverage

### A · Header & market context (rows 1–10, 72–80, 173–180)
| Tile | BBG ticker | IMDR source | Verdict |
|---|---|---|---|
| USD/INR spot | `INR Curncy` | `fx.fact_fx_rate` USD/INR | ✓ |
| REER (z-score) | `BISBINR Index` | `econ` `BIS.REER.BROAD.IN` (monthly, 389 obs) | ✓ (z on monthly) |
| 50d–100d MA · 3m carry · 3m vol · Sharpe · 25D RR/BF 3M | *(derived)* | from spot + fwd + vol below | ◐ derive |
| S&P 500 | `SPX Index` / `S&P Index` | `equities.fact_index_level` SPX | ✓ |
| Gold | `XAU Curncy` / `Gold Index` | `commodities.fact_spot` Gold | ✓ |
| Oil (Brent) | `CO1 Comdty` | `commodities.fact_spot` **WTI only** | ◐ WTI proxy; Brent ✗ |
| US 10y | `USGG10YR Index` | UST cash not held; `rates` USD SOFR 10Y par | ◐ proxy; cash ✗ |
| US 3M | `US0003M Index` | SOFR 3M | ◐ proxy |
| DXY · Asia-$ | `DXY Index` · `ADXY Index` | — | ✗ |
| EUR/USD | `EURUSD Curncy` | `fx.fact_fx_rate` EUR/USD | ✓ |
| BRL · ZAR · TRY | `*Curncy` | not in the 25-pair set | ✗ (EM context) |

### B · Returns (rows 2–5)
| Nifty 50 | `NIFTY`/`NSER`/`NSERO Index` | `equities` NSEI | ✓ |
| INR level | `INR Curncy` | `fx` USD/INR | ✓ |
| 10y bond index | `INRPYLDP`/`10yr Bond Index` | derivable from loaded IGB curve (10Y nearest-tenor) | ◐ derive (see F) |

### C · Credit (rows 7–10)
| SBI / ICICI / REL 5Y CDS | *(names)* | no credit schema in IMDR | ✗ **gap** |

### D · FX forwards — onshore & offshore (rows 11–19, 170–175)
| Tile | BBG ticker | IMDR source | Verdict |
|---|---|---|---|
| Offshore fwd points 1m–12m | `IRN1M`…`IRN12M Curncy` | `fx.fact_fx_rate` USD/INR `fwd_points` (Citi = NDF/offshore) | ✓ |
| Offshore implied yield | `IRNI1M`…`IRNI12M` | derived from fwd points | ◐ derive |
| Onshore fwd points / yield | `IRO*` / `IROI*` | IMDR cut is offshore | ◐ onshore ✗ |
| Fwd flies 1s2s…1s12s | `.IRN1M2M`…`.IRN1M12M Index` | derived | ◐ derive |

### E · Swaps / IRS — onshore & offshore (rows 20–29, 170–178)
| Offshore IRS 1Y–10Y (+fwd, roll) | `IRSWO1`…`IRSWO10`, `IRSWM*`, `IRSWN*` | `rates` INR **MIFOR** (`swap_libor`: par+fwd 28 tenors, fly, spread), fresh | ✓✓ |
| Onshore OIS 1Y–10Y | `IRSWNI1`…`IRSWNI10`, `IRSWNIC/F/I` | `rates` INR **MIBOR** (`ois` par, 13 tenors), fresh | ✓ |
| Offsh − onsh spread | *(derived)* | MIFOR − MIBOR | ◐ derive |
| Generic IRS `.GINIRS1`…`10` | `Index` | = MIFOR/MIBOR par | ◐ derive |

### F · Govt bonds + bond-swap spread + flies (rows 30–44)
| G-sec curve 1Y–30Y, fwd curve, roll | `GIND10YR`, `IGTR10YR`, `GDDBINDA`, `INRPYLDP`, `BCEY4T Index` | ✅ **`rates.fact_bond_instrument_obs`** (Govy Track B, loaded 2026-07-20): IGB 20 ISIN-level bonds, 3,046 obs, fresh to 2026-07-17, ~7mo history; CMT tiles = read-time nearest-tenor view (to build) | ✓ (data) ◐ (curve-tile derivation pending) |
| CCIL call / bond indices | `CCILCALL`, `CCILCOPX`, `CCILCTPX Index` | not in Govy | ✗ (minor) |
| Overnight rate | `IN00O/N Index` | MIBOR o/n (partial) | ◐ |
| Bond-swap (ASW) spread · bond flies | *(derived)* | ASW loaded but **thin** (3 bonds, stale 2026-06-21) → better derived vs INR MIFOR/MIBOR (both held); flies derivable off the curve | ◐ derive |

> The govt-bond **data** gap is now closed (Govy Track B). What remains is the read-time derivation
> (CMT curve tiles, Δ from history, flies/roll, derived ASW) — see `../govt_bond_population.md`.

### G · FX vol (rows 45–57, 185–189)
| Offshore ATM vol 1w–1y | `USDINRV1W`…`USDINRV1Y Curncy` | `fx.fact_vol` USD/INR `IMPLIED`/`ATM` | ✓ |
| 25D risk-reversal | `USDINR25R* Index` | `fact_vol` strike `25RR` | ✓ |
| 25D butterfly | `USDINR25B* Index` | `fact_vol` strike `25STR` | ✓ |
| 10D RR/BF | *(implied)* | `10RR` / `10STR` also held | ✓ |
| Realized vol | *(col)* | `fact_vol` `REALISED` | ✓ |
| Onshore vol / RR / BF | `USDINROV*`, `USDINR25OR*`, `USDINR25OB*` | IMDR cut is offshore/NDF | ◐ onshore ✗ |
| `USDINRH*` | hedge/settlement variant | — | ◐ minor |

### H · Macro / Econ block (rows 145–165)
| CPI YoY | `INFINFY Index` | `econ` cpi (206 ind) | ✓ |
| WPI | `INFUTOTY Index` | `econ` cpi/wpi | ✓ |
| IIP YoY | `INPIINDY Index` | `econ` | ✓ |
| GDP YoY | `INQGGDPY Index` | `econ` gdp (88) | ✓ |
| Trade balance / exp / imp YoY | `INMTBAL$`, `INMTEXUY`, `INMTIMUY`, `INMTIMP$` | `econ` bop (506) | ✓ |
| FX reserves | `INMORES$ Index` | `econ` fx (31) | ✓ |
| Current account | `EHCAIN` / `IBOPCURR Index` | `econ` bop | ✓ |
| Fiscal deficit | `INDFFISC`, `INFFFIDE`, `INFDTOT$` | `econ` (CGA deficits, filed under `other`) | ✓ ◐ recategorise |
| Mfg PMI | `MPMIINMA Index` | not in `econ`; `calendar.cb_events` (mfg pmi) | ◐ |

### I · FPI / FII flows (rows 84, 145–146, 229–230)
| Net FPI equity / debt (USD & INR, MTD) | `FII Equity`, `FIINNET$`, `FIINDNT$`, `FIINMTDN`, `FIINDMTD Index` | `econ` **NSDL FPI** (equity/debt/hybrid/MF net + gross, daily) | ✓✓ |
| Nifty future | `IH1 Index` | index futures not held | ✗ (minor) |

### J · Trade partners (rows 58–63, 297–301)
| Top exports/imports by counterparty + product | *(table)* | partner/product breakdown not in IMDR | ✗ |
| Export-destination GDP | `EHGDUS/AEY/CN/HK/SG Index` | other-country `econ` GDP (US/CN/etc. live) | ◐ partial |

## Gap list — ranked by ease, with Citi checked (2026-07-17)

**Citi verdict:** Citi Velocity is **DM-only for sovereign bonds** (`bonds_full.md`: "Zero APAC EM
bond coverage… BBG_mirror is the only source") and carries **no credit/CDS**. So the two structural
gaps below are *not* Citi tag-flips. Citi *does* cover the context feeds (TSY, REER_IDX).

| # | Gap | Fix path | Difficulty |
|---|---|---|---|
| 1 | **Fiscal recategorise** — CGA deficits sit in `other` | metadata reassignment, data already held | **trivial** (no new data) |
| 2 | **US context** — UST cash 10y, US 3M | Citi **TSY** + **T_BILL** + **BENCH_RATES** (already accessible) | **easy** (Citi tags) |
| 3 | **PMI into `econ`** · **onshore fwd/vol cut** | promote PMI from `cb_events`; add onshore or accept offshore-only | easy–medium |
| 4 | ~~**Govt-bond curve** (G-sec)~~ ✅ **DONE 2026-07-20** — Govy Track B ingested (IGB 20 bonds, 3,046 yield obs + ASW + 28 auctions) into `rates.fact_bond_instrument_obs`/`fact_bond_auction`. Remaining = read-time curve/Δ/fly derivation, not ingest. | ~~medium~~ done |
| 5 | **Context indices** — DXY, ADXY, Brent | Citi has NEER proxy + WTI; true DXY/Brent = BBG | medium (minor tiles) |
| 6 | **Single-name CDS** (SBI/ICICI/REL) | **not on Citi** — new vendor + new credit schema | **hard** |

## Quick Monitor `Econ` tab — macro snapshot coverage

The cross-country `Econ` sheet (`Quick Monitor v4 9.xlsm`) carries a compact 9-field macro row per
country. India's block (row 114) + the shared column set, mapped to IMDR `econ.fact_indicator`:

| Econ field | BBG ticker | IMDR source | Verdict |
|---|---|---|---|
| GDP (YoY) | `IGQREGDY Index` | `econ` gdp (88 ind) | ✓ |
| CPI (YoY) | `INFINFY Index` | `econ` cpi (206) | ✓ |
| PPI / WPI | `INFUTOTY Index` | `econ` cpi/wpi | ✓ |
| Current Account | `IBOPCURR Index` | `econ` bop (506) | ✓ |
| Fiscal Deficit | `IGS%IND` / `INDFFISC Index` | `econ` CGA deficits (filed under `other`) | ✓ ◐ recategorise |
| Policy Rate | *(repo)* | `econ` rates (43) | ✓ |
| 5y Swap | *(INR IRS 5y)* | `rates` INR MIFOR/MIBOR 5Y | ✓ |
| PMI + ΔPMI | `MPMIINMA Index` | `calendar.cb_events` (not in `econ`) | ◐ |
| Exports / Imports | `IGQREXP` / `IGQRIMP Index` | `econ` bop | ✓ |

**Verdict:** the India Econ row is **fully recreatable** from IMDR today — 7/9 fields ✓, PMI via
`cb_events` (◐), fiscal held but mis-categorised. This is the macro layer of the per-country monitor.

## Derivations the builder must compute (data all held)
z-score (REER, rates, vol) · 50/100d MA · 3m carry (fwd points) · 3m vol · Sharpe · implied
yields from fwd points · fwd flies · offsh−onsh spread · RR/BF from `fact_vol` strikes ·
standardised surprise (`cb_events` + `fact_indicator`).
