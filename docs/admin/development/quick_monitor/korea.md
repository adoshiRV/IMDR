# Quick Monitor — Korea data audit

> **Companion to the master spec** [`../quick_monitor.md`](../quick_monitor.md) — this file is the
> ticker-by-ticker reference detail, not a competing spec. Read the master for the reconciled data
> state + completion punch-list. Reconciled 2026-07-22: KR **fiscal is held** (`BOK.FISCAL.*`, not a
> data gap) and KR **PPI is held** (`BOK.PPI.*`) — see the corrected verdicts below.

**Reference:** `data/quick_monitor/MarketMonitor Korea 1.xlsm` (single sheet `Korea`, 633×1140).
**Audited:** 2026-07-17, against IMDR (reconciled 2026-07-22). Tickers extracted from cells +
formulas (the sheet is formula-driven). Panel structure confirmed from the sheet layout.

Verdict key: ✓ held & fresh · ◐ derivable / partial · ✗ gap.

## Headline

**The USD/KRW FX + vol + swap-curve + core-macro snapshot is recreatable.** Spot·forwards·vol,
the offshore CD swap curve (deep), KOSPI, CPI/GDP/current-account/unemployment/household-credit
all exist and are fresh. **Korea has more markets gaps than India:** the **cross-currency basis**
panel (prominent in the KR monitor), the **govt-bond curve**, **sovereign CDS**, and **REER** are
all missing; the **onshore OIS (KOFR)** curve is held but **stale**, and there's a **house-price
index** gap (loans held, prices not).

Rough recreatability: **~70% of tiles today**; the KRW basis + govt bonds + REER are the notable adds.

## Panel-by-panel coverage

### A · Header & context (rows 4–12)
| Tile | BBG ticker | IMDR source | Verdict |
|---|---|---|---|
| USD/KRW spot | `KRW Curncy` | `fx.fact_fx_rate` USD/KRW | ✓ |
| REER (z-score) | `BISBKRR Index` | **not ingested** (India's BIS REER exists; KR not) | ✗ (easy fill) |
| 50/100d MA · carry · vol · Sharpe · 25D RR/BF | *(derived)* | from FX + vol below | ◐ derive |
| KOSPI | `KOSPI Index` | `equities` KS200 (KOSPI 200) | ✓ ◐ (200 vs composite) |
| S&P 500 | `SPX Index` | `equities` SPX | ✓ |
| Oil | `CO1 Comdty` | `commodities` WTI | ◐ WTI proxy |
| US 10y · 3M | `USGG10YR` · `US0003M` | SOFR proxy; UST cash ✗ | ◐ |

### B · Credit (rows 9–12)
| Sovereign CDS (level, default prob, seniority) | *(names)* | no credit schema | ✗ **gap** |

### C · FX forwards (rows 13–21)
| KRW NDF fwd points 1M–3Y | `KWN1M`…`KWN12M`, `KWN2Y`, `KWN3Y`, `KWN5Y Curncy` | `fx.fact_fx_rate` USD/KRW `fwd_points` | ✓ |
| Fwd Δ / z-score | *(derived)* | from held fwd points | ◐ derive |

### D · Swaps / IRS (rows 22–29, 388–400)
| Offshore CD swap 3M–20Y (+ fwd, roll) | `KWSWO1`…`KWSWO20`, `KWCDC`, `KWSWOF/I Curncy` | `rates` KRW **CD** (`swap_libor`: par 36 tenors + fwd 28 + fly + spread), fresh | ✓✓ |
| Onshore KRW OIS 1Y–10Y | `KWSWNI1`…`KWSWNI10 Curncy` | `rates` KRW **KOFR** (`ois` par, 15 tenors) — **latest 2026-05-28** | ◐ **stale** |
| 91D CD 3M | — | `rates` KRW `91D_CD_3M` (14 tenors), fresh | ✓ |
| IRS spread / butterfly grid | *(derived)* | from CD curve | ◐ derive |

### E · Cross-currency basis (rows 30–37)
| KRW basis 1Y / 2Y / 1Y1Y / 2Y1Y / 3Y / 5Y / 7Y | *(basis tickers)* | IMDR holds only EUR/AUD/USD basis curves — **no KRW basis** | ✗ **gap** |

### F · FX vol (rows 49–61)
| ATM implied 1w–1y | `USDKRWV3M Curncy` (+ tenors) | `fx.fact_vol` USD/KRW `IMPLIED`/`ATM` | ✓ |
| 25D RR / butterfly | `USDKRW25R3M`, `USDKRW25B3M Curncy` | `fact_vol` `25RR` / `25STR` | ✓ |
| Realized vol | *(col)* | `fact_vol` `REALISED` | ✓ |

### G · Govt bonds
| KTB curve | `GDDBSOKO`, `KOBONTL`, `KOBLLCML Index` | ✅ **`rates.fact_bond_instrument_obs`** (Govy Track B, loaded 2026-07-20): KTB 12 ISIN-level bonds, 1,494 obs, fresh to 2026-07-17. NB vendor `chg_1d`=0 for KTB → Δ recomputed from history. CMT tiles = read-time view (to build). Deep-history CMT (GVSK, 2007+) still available via **BBG_mirror Track A** (not yet loaded). | ✓ (data) ◐ (derivation pending) |

### H · Macro / Econ (header + rows 31, 50, 62–67)
| CPI YoY | `KOCPIYOY Index` | `econ` cpi (25 ind) | ✓ |
| GDP YoY (Q) | `KOGDPYOY`/`kogdpyoy Index` | `econ` gdp (51) | ✓ |
| Exports / imports YoY | `KOEXTOTY`, `KOIMTOTY Index` | `econ` bop (30) | ✓ |
| Current account | `EHCAKR Index` | `econ` `BOK.BOP.CA.TOTAL.KR` | ✓ |
| FX reserves | `KOFETOT Index` | `econ` `BOK.BOP.FA.RESERVES` (flow, not level) | ◐ |
| Unemployment | `KOEAUERS Index` | `econ` `KOSTAT.LABOUR.UNEMP_RATE.KR` | ✓ |
| House price YoY | `KOHPTYOY Index` | `econ` has household **loans/credit**, not a **price** index | ◐ **price gap** |
| PPI | *(KR PPI)* | `econ` `BOK.PPI.*` (6 series: Total + Mfg/Mining/Svc/Agri/Util, filed under Consumer prices) | ✓ *(reconciled 2026-07-22)* |
| Fiscal (Net Lending / Rev / Exp) | `IGS%KOR Index` | `econ` `BOK.FISCAL.*` (General Government, annual; filed under GDP and components) | ✓ ◐ recategorise *(reconciled 2026-07-22 — was recorded as a gap)* |
| Mfg PMI | `Aig PMI Index` | `calendar.cb_events` | ◐ |
| REER | `BISBKRR Index` | not ingested | ✗ |
| Export-dest GDP · JP/US carry | `EHBBKRW/Y`, `EHGD*`, `JEUSCARY`, `JEEUCARY` | partner `econ` / derived | ◐ |

## Gap list — ranked by ease, with Citi checked (2026-07-17)

**Citi verdict:** Citi is **DM-only for sovereign bonds** (no KTB), has **no credit/CDS**, and its
cross-ccy basis (`XCCY_OIS`) is **G10-only — no KRW**. So basis, KTB and CDS are *not* Citi fixes.
But Citi **does** carry **REER_IDX/NEER_IDX (50+ ccys, incl. KRW)** and full US Treasury context.

| # | Gap | Fix path | Difficulty |
|---|---|---|---|
| 1 | **REER** — `BISBKRR` not ingested | Citi **REER_IDX** *or* extend the existing **BIS REER** fetch (India's loaded) to add KR | **trivial** |
| 2 | **Onshore OIS (KOFR) staleness** — last obs 2026-05-28 | refresh the KOFR feed (curve already exists) | **trivial** (ops fix) |
| 3 | **US context** — UST 10y, US 3M | Citi **TSY**/**T_BILL** (already accessible) | **easy** |
| 4 | ~~**Govt-bond curve** (KTB)~~ ✅ **DONE 2026-07-20** (Track B) — Govy KTB ingested (12 bonds, 1,494 obs + ASW). Read-time curve/Δ derivation pending. **Track A** (BBG_mirror GVSK deep CMT 2007+) still gated/unloaded for long history. | ~~medium~~ done (B) |
| 5 | **House-price index** — have HH loans, not prices | add a KR house-price series (KOSIS/REB) | medium |
| 6 | ~~**Fiscal domain** — no KR fiscal indicators at all~~ **RECONCILED 2026-07-22: NOT a gap.** `BOK.FISCAL.*` (Revenue / Expenditure / Net Lending / Taxes, General Government annual) is held — mis-filed under "GDP and components". | metadata recategorise, data already held | **trivial** |
| 7 | **KRW cross-currency basis** — a whole panel | **not on Citi** (G10-only) — BBG_mirror or derive | **hard** |
| 8 | **Sovereign CDS** | **not on Citi** — new vendor + credit schema | **hard** |

## Quick Monitor `Econ` tab — macro snapshot coverage

The cross-country `Econ` sheet carries a 9-field macro row per country. Korea's block (row 108) +
the shared columns, mapped to IMDR `econ.fact_indicator`:

| Econ field | BBG ticker | IMDR source | Verdict |
|---|---|---|---|
| GDP (YoY) | `KOGDPYOY Index` | `econ` gdp (51 ind) | ✓ |
| CPI (YoY) | `KOCPIYOY Index` | `econ` cpi (25) | ✓ |
| PPI | *(KR PPI)* | `econ` `BOK.PPI.TOTAL.LEVEL.KR` (+5 sectors) | ✓ *(was ◐)* |
| Current Account | `EHCAKR Index` | `econ` `BOK.BOP.CA.TOTAL.KR` | ✓ |
| Fiscal Deficit | `IGS%KOR Index` | `econ` `BOK.FISCAL.NET_LENDING.KR` (mis-filed under GDP components) | ✓ ◐ recategorise *(was ✗)* |
| Policy Rate | `KORP7DR Index` | `econ` rates (10) / `BIS.POLICY_RATE.KR` | ✓ |
| 5y Swap | *(KRW IRS 5y)* | `rates` KRW CD 5Y | ✓ |
| PMI + ΔPMI | `Aig PMI Index` | `calendar.cb_events` | ◐ |
| Exports / Imports | `KOECSTOT` / `KOECSIMP Index` | `econ` bop | ✓ |

**Verdict (reconciled 2026-07-22):** Korea's Econ row is **8/9 recreatable** — GDP · CPI · **PPI** ·
CA · **Fiscal (Net Lending)** · Policy · 5y Swap · Exports/Imports all ✓; PMI via `cb_events` (◐).
Fiscal and PPI are held (both were previously recorded as gaps/unconfirmed); the only residual on
fiscal is a metadata recategorise, not a data pull.

## Derivations the builder must compute (data all held)
z-score (fwd, swap, vol — the monitor leans heavily on 2y z-scores) · MA · carry · Sharpe ·
RR/BF from `fact_vol` strikes · IRS spread/fly grid · standardised surprise (`cb_events` + `fact_indicator`).
