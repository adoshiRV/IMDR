# Citi Velocity — Rates Full Catalog

Complete inventory of all RATES data available via the Citi Velocity API (excluding OIS, SWAP_LIBOR, VOL, and INFLATION which have their own docs).

- **Explored**: 2026-03-26
- **DO NOT re-run** — all results documented here
- **Superseded for bond branches** (2026-05-25): SOV/MBS/AGENCY_INVENTORY/MIDCURVES/SPREAD_OPTIONS/FRA/FRA_OIS/OIS_INVOICESPREAD/INVOICESPREAD/POS_MON/FORECAST entries in this doc are stale. See [bonds_full.md](bonds_full.md) for the current picture (most "not probed" / "partial" claims have been resolved).

---

## Overview

**Already built/documented separately:**
- OIS — swap curves (in `rates.yml` universe)
- SWAP_LIBOR — legacy LIBOR swaps (in `rates.yml` universe)
- VOL — swaption vol (see `docs/admin/rates/swaption_vol_schema.md`)
- INFLATION — CPI/inflation swaps (see [`rates_inflation.md`](rates_inflation.md))

**Remaining 24 subcategories — 135,915 tags total:**

| Subcategory | Tags | Data? | Description |
|---|---|---|---|
| **XCCY_OIS_SWAP** | 76,418 | YES | Cross-currency OIS basis swaps (largest) |
| **XCCY_SWAP** | 12,560 | NO* | Cross-currency LIBOR basis swaps |
| **MBS** | 11,321 | NO* | Mortgage-backed securities analytics |
| **SOV** | 10,909 | partial | Sovereign bond spreads, butterflies, curves |
| **SOV_CMT** | 8,250 | YES | Sovereign constant-maturity yields (34 countries) |
| **BASIS_SWAPS** | 6,656 | partial | Tenor basis swaps (3s1s, 6s3s, etc.) |
| **MIDCURVES** | 3,516 | ? | Swaption mid-curve options |
| **AGENCY_INVENTORY** | 2,344 | ? | Agency bond inventory/analytics |
| **FORWARD** | 864 | YES | Sovereign forward yield rates |
| **SSA** | 708 | YES | Supranational/agency spreads vs govvies |
| **SPREAD_OPTIONS** | 576 | ? | Spread options (cap/floor on curves) |
| **OIS_MEETING** | 449 | NO* | Central bank meeting-dated OIS |
| **FRA** | 445 | ? | Forward rate agreements |
| **MONEY_MARKETS** | 229 | NO* | Short-term fixings (SOFR, EURIBOR, etc.) |
| **FRA_OIS** | 121 | ? | OIS-based FRA |
| **SSA_CS** | 100 | ? | SSA cross-currency spreads |
| **OIS_INVOICESPREAD** | 44 | ? | OIS invoice spreads |
| **POS_MON** | 32 | ? | Rates positioning monitor |
| **TIPS** | 26 | YES | US TIPS (breakevens, real yields, carry) |
| **INVOICESPREAD** | 14 | NO* | Treasury invoice spreads |
| **T_BILL** | 12 | YES | US T-Bill yields, prices, SOFR spreads |
| **FORECAST** | 12 | NO* | Citi rate forecasts (Fed, ECB, yields) |
| **BENCH_RATES** | 10 | YES | Central bank policy rates |

*NO = tag format guesses didn't return data; may need different patterns.

---

## Tier 1: Confirmed Working, High Macro Value

### SOV_CMT — Sovereign Constant-Maturity Yields (8,250 tags)

**Tag format**: `RATES.SOV_CMT.{COUNTRY}.{TENOR}.YIELD`

**34 countries** (ISO-3166 codes):

| Region | Countries |
|---|---|
| **G7** | USA, DEU, GBR, FRA, JPN, CAN, ITA |
| **Core Europe** | AUT, BEL, CHE, DNK, ESP, FIN, LUX, NLD, NOR, SWE |
| **Periphery Europe** | CYP, CZE, GRC, HUN, IRL, POL, PRT, ROU, SVK, SVN |
| **Other DM** | AUS, NZL, ISR |
| **EM** | TUR, ZAF, RUS |

**Sample data (2026-03-25):**

| Country | 2Y | 10Y |
|---|---|---|
| USA | 3.89% | 4.34% |
| DEU | 2.58% | 2.98% |
| GBR | 4.29% | 4.84% |
| JPN | 1.30% | 2.24% |
| AUS | — | 4.95% |
| CAN | — | 3.48% |

All daily, 22 pts/30d. Also has AUTFULL (Austria full curve).

---

### BENCH_RATES — Central Bank Policy Rates (10 tags)

| Tag | Description | Last Value |
|---|---|---|
| `RATES.BENCH_RATES.ECB` | ECB deposit facility rate | 2.15% |
| `RATES.BENCH_RATES.FED_FUNDS` | Fed effective funds rate | 3.64% |
| `RATES.BENCH_RATES.US_FED_FUNDS_TARGET` | Fed target rate | 3.75% |
| `RATES.BENCH_RATES.US_FED_PRIME` | US prime rate | 6.75% |
| `RATES.BENCH_RATES.UK_BASE` | BoE bank rate | 3.75% |
| `RATES.BENCH_RATES.US_FED_CP_1M` | Fed commercial paper 1M | 3.65% |
| `RATES.BENCH_RATES.US_FED_CP_2M` | Fed commercial paper 2M | 3.65% |
| `RATES.BENCH_RATES.US_FED_CP_3M` | Fed commercial paper 3M | 3.77% |
| `RATES.BENCH_RATES.JPY_DISCOUNT` | BoJ discount rate | NO DATA |
| `RATES.BENCH_RATES.JPY_TARGET` | BoJ target rate | NO DATA |

---

### TSY — US Treasuries (299 tags)

**Confirmed working patterns:**

| Tag | Description | Last Value |
|---|---|---|
| `RATES.TSY.OTR.2Y.YIELD` | On-the-run 2Y UST yield | 3.76% |
| `RATES.TSY.OTR.5Y.YIELD` | On-the-run 5Y UST yield | 3.97% |
| `RATES.TSY.OTR.10Y.YIELD` | On-the-run 10Y UST yield | 4.32% |
| `RATES.TSY.OTR.30Y.YIELD` | On-the-run 30Y UST yield | 4.89% |
| `RATES.TSY.BFLY.5Y.10Y.30Y` | 5s10s30s butterfly | -0.22 |

Also has ASW (asset swap spreads) and SPREAD patterns — not all confirmed.

---

### T_BILL — US Treasury Bills (12 tags)

**Tag format**: `RATES.T_BILL.OTR.{TENOR}.{METRIC}`

Tenors: 1M, 3M, 6M, 1Y. Metrics: YIELD, PRICE, ASS_SOFR (spread to SOFR).

| Tenor | Yield | Price | SOFR Spread |
|---|---|---|---|
| 1M | 3.68% | 99.74 | -4.56 bp |
| 3M | 3.66% | 99.08 | -4.17 bp |
| 6M | 3.64% | 98.18 | -5.40 bp |
| 1Y | 3.72% | 96.41 | -3.35 bp |

---

### TIPS — US Inflation-Protected Securities (26 tags)

**Tag format**: `RATES.TIPS.USD.{TENOR}.{METRIC}`

Tenors: 5Y, 10Y, 30Y. Metrics: YIELD, PRICE, BREAKEVENS, ASS_SOFR, CARRY.1M, CARRY.3M, CARRY_BE.1M, CARRY_BE.3M.

| Tenor | Real Yield | Breakeven | Price |
|---|---|---|---|
| 5Y | 1.39% | 257.9 bp | 98.82 |
| 10Y | 2.01% | 230.3 bp | 98.77 |
| 30Y | 2.70% | 219.8 bp | 93.42 |

Also has `RATES.TIPS.EXT_POLATED` (extrapolated curve) — returned no data in probe.

---

### FORWARD — Sovereign Forward Yields (864 tags)

**Tag format**: `RATES.FORWARD.{COUNTRY}.{START}.{TENOR}.CITI`

**Sample data (2026-03-25):**

| Country | Forward | Value |
|---|---|---|
| USA | 5Y5Y | 4.77% |
| USA | 2Y10Y | 5.48% |
| DEU | 5Y5Y | 3.32% |
| GBR | 5Y5Y | 5.40% |
| JPN | 5Y5Y | 2.83% |

---

### XCCY_OIS_SWAP — Cross-Currency OIS Basis (76,418 tags)

**Tag format**: `RATES.XCCY_OIS_SWAP.{CCY1}.{CCY2}.{START}.{TENOR}.BASE_LEG.BASIS_SPREAD`

**Sample data (2026-03-25):**

| Pair | Tenor | Basis (bp) |
|---|---|---|
| EUR/USD | 2Y | -4.98 |
| EUR/USD | 5Y | -5.99 |
| EUR/USD | 10Y | -7.40 |
| GBP/USD | 5Y | -0.78 |
| JPY/USD | 5Y | -39.51 |

Massive dataset — full forward-starting cross-currency basis surface.

---

### SSA — Supranational/Agency Spreads (708 tags)

**Tag format**: `RATES.SSA.{ISSUER}.SPOT.{TENOR}.DEU_SPRD`

Spreads of supranational issuers vs German Bunds.

| Issuer | 5Y Spread | 10Y Spread |
|---|---|---|
| KFW | 22.3 bp | 21.2 bp |
| EIB | 22.0 bp | 24.4 bp |

---

## Tier 2: Partially Working / Needs More Exploration

### BASIS_SWAPS (6,656 tags)
EUR 3s1s basis confirmed (8.94 bp). USD format needs investigation.

### SOV (10,909 tags)
Only USA butterfly confirmed. Spread format may differ by country.

### FORECAST (12 tags)
Citi forecasts for Fed funds, ECB depo, UST 2Y/10Y, Gilt 10Y, Bund 10Y, JGB 10Y — quarterly + annual. Data didn't return in 30-day probe (likely infrequent updates).

### OIS_MEETING (449 tags)
Meeting-dated OIS. Format `RATES.OIS_MEETING.{CCY}.{YEAR}.{DATE}`. Didn't return data — may need exact upcoming meeting dates.

### MONEY_MARKETS (229 tags)
9 currencies × multiple fixings (SOFR, EURIBOR, LIBOR, etc.). Browsing reveals structure but data probes returned nothing — may need different qualifier.

---

## Tier 3: Not Yet Probed for Data

| Subcategory | Tags | Notes |
|---|---|---|
| MIDCURVES | 3,516 | Swaption mid-curves (EUR, possibly USD) |
| AGENCY_INVENTORY | 2,344 | Callable agency analytics |
| MBS | 11,321 | US mortgage-backed (OAS, basis, perf, etc.) |
| XCCY_SWAP | 12,560 | Legacy LIBOR cross-currency basis |
| SPREAD_OPTIONS | 576 | Rate spread options |
| FRA | 445 | Forward rate agreements |
| FRA_OIS | 121 | OIS-based FRA |
| SSA_CS | 100 | SSA cross-currency spreads |
| OIS_INVOICESPREAD | 44 | OIS invoice spreads |
| POS_MON | 32 | Rates positioning monitor |
| INVOICESPREAD | 14 | Treasury invoice spreads |

---

## Macro Hedge Fund Priority

For a global macro fund, the most actionable datasets to ingest first:

1. **SOV_CMT** — global sovereign yield curves (34 countries), the backbone of rates analysis
2. **BENCH_RATES** — central bank policy rates
3. **XCCY_OIS_SWAP** — cross-currency basis (key for FX-hedged bond analysis)
4. **FORWARD** — forward yield rates (5Y5Y, etc.)
5. **TSY + T_BILL + TIPS** — US fixed income core
6. **SSA** — supranational spreads
7. **BASIS_SWAPS** — tenor basis
