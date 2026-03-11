# Citi Velocity — Full Tag Catalog

Complete inventory of all data available via the Citi Velocity API, discovered via `tagbrowsing` on 2026-03-11.

For API endpoints, authentication, and rate limits, see `docs/rates/citi_velocity_api.md`.

**Exploration scripts** (DO NOT re-run — results cached):
- `scripts/explore/explore_rates_categories.py` → `data/cache/rates/rates_tree.json`
- `scripts/explore/explore_other_categories.py` → `data/cache/{fx,equity,commodities}/*_tree.json`

---

## Root Categories

| Category | Subcategories | Description |
|---|---|---|
| **RATES** | 28 | Interest rates, sovereign yields, inflation, vol, basis, xccy |
| **FX** | 24 | Spot, forwards, options, vol, carry, indices, deposits |
| **EQUITY** | 6 | Var/vol swaps, indices, implied vol, forecasts |
| **COMMODITIES** | 5 | Spot prices, EIA data, implied vol, indices, forecasts |

---

## FX (24 Subcategories)

### Market Data — Core

| Subcategory | Children | Description | Structure |
|---|---|---|---|
| **SPOT** | 52 ccys | FX spot rates (cross pairs) | `FX.SPOT.{CCY1}.{CCY2}` → leaf |
| **FORWARD** | 4 types | FX forward points/outrights/IMM | `FX.FORWARD.{TYPE}.{CCY1}.{CCY2}.{TENOR}` |
| **DEPOSIT** | 50 ccys | Deposit rates (1W–10Y, 13 tenors) | `FX.DEPOSIT.{CCY}.{TENOR}` |
| **OPTION** | 21 ccys | FX option vol surfaces | `FX.OPTION.{CCY1}.{CCY2}.{SURFACE}` |
| **VOL** | 39 ccys | FX vol (implied + realized) — see [FX VOL Deep Dive](#fx-vol-deep-dive) below | `FX.VOL.{CCY1}.{CCY2}.{STRIKE}.{TENOR}.{TYPE}.CITI` |
| **SWAP** | 5 ccys (AUD, EUR, GBP, NZD, USD) | FX swap points | `FX.SWAP.{CCY1}.{CCY2}.{TENOR}` |
| **XCCY_SWAP** | 20 ccys | FX cross-currency swaps | `FX.XCCY_SWAP.{CCY}.USD.{TENOR}` |
| **CARRY** | 31 ccys | FX carry (rate differentials) | `FX.CARRY.{CCY1}.{CCY2}` |

#### FORWARD Sub-types

| Type | Description | Coverage |
|---|---|---|
| `FWD_OUTRIGHT` | Forward outright rates | 20+ ccys |
| `FWD_POINT` | Forward points (raw) | 20+ ccys |
| `FWD_POINT_PIP` | Forward points (pips) | 20+ ccys |
| `FWD_IMM` | IMM-dated forwards | AUD, BWP, EUR, GBP, NZD, USD, XAG, XAU, XPD, XPT |

### FX VOL Deep Dive

Explored 2026-03-11 via `scripts/explore/explore_fx_vol.py`. Full cache: `data/cache/fx/fx_vol_tree.json`.

**Tag format:** `FX.VOL.{CCY1}.{CCY2}.{STRIKE}.{TENOR}.{TYPE}.CITI`

Example: `FX.VOL.EUR.USD.ATM.1M.IMPLIED.CITI`

#### Base Currencies (39)

ARS, AUD, BRL, CAD, CHF, CLP, CNH, COP, CZK, DKK, EUR, GBP, HKD, HUF, IDR, ILS, INR, JPY, KRW, MXN, MYR, NOK, NZD, PEN, PHP, PLN, RON, RUB, SEK, SGD, THB, TRY, TWD, USD, XAG, XAU, XPT, ZAR + more

USD has 33 quote currencies; EUR has broad cross coverage.

#### Strike Types (11)

| Strike | Description |
|---|---|
| **ATM** | At-the-money (has IMPLIED, REALISED, and SPREAD leaf types) |
| **25RR** | 25-delta risk reversal |
| **10RR** | 10-delta risk reversal |
| **25STR** | 25-delta strangle |
| **10STR** | 10-delta strangle |
| **STRIKE_C10** | 10-delta call |
| **STRIKE_C25** | 25-delta call |
| **STRIKE_C35** | 35-delta call |
| **STRIKE_P10** | 10-delta put |
| **STRIKE_P25** | 25-delta put |
| **STRIKE_P35** | 35-delta put |

#### Tenors (14)

`ON`, `1W`, `2W`, `1M`, `2M`, `3M`, `6M`, `9M`, `1Y`, `2Y`, `3Y`, `5Y`, `7Y`, `10Y`

#### Leaf Types

| Leaf Type | Available For | Description |
|---|---|---|
| **IMPLIED** | All 11 strikes | Implied volatility (mid) |
| **REALISED** | ATM only | Realized/historical volatility |
| **SPREAD** | ATM only | Implied minus realized spread |

#### Tags Per Pair

~180 total: (11 strikes × 14 tenors × 1 IMPLIED) + (14 tenors × 2 extra ATM types) = 154 + 28 = 182

Consistent structure across G10 and EM pairs. Verified on: EUR/USD, GBP/USD, USD/JPY, AUD/USD, USD/MXN, USD/CNH, USD/KRW.

### Citi Proprietary Indices

| Subcategory | Children | Description |
|---|---|---|
| **NEER_IDX** | 7 (BROAD, NARROW, regional) | Nominal Effective Exchange Rate indices (50+ ccys) |
| **REER_IDX** | 8 (BROAD, NARROW, regional, USD) | Real Effective Exchange Rate indices (50+ ccys) |
| **CITIPAIN** | 10 G10 ccys (leaf tags) | Citi Pain Index (positioning indicator) |
| **CTOT** | DM (11 ccys), EM (50+ ccys) | Commodity Terms of Trade |
| **LIQUIDITY_IDX** | 7 (AUD, EM, EUR, G10, GBP, NZD, USD) | FX liquidity indices |
| **MRICITI** | 3 (EM, LT, ST MRI) | Macro Risk Index (EM spread, FX vol, correlation, etc.) |
| **CRFI** | 2 (EM_VALUE, G10_VALUE) | Citi Risk Factor Index |
| **SURPRISE_INDEX** | ESI (5 sub-indices), ISI (3) | Economic/Inflation Surprise Indices (CESI, CEDI, etc.) |
| **SC_SCORECARD** | 4 (FLOWPCT, AVGRANK, FACTOR, POS) | FX Scorecard (multi-factor model: carry, value, ToT, etc.) |

### Citi Fair Value Models

| Subcategory | Children | Description |
|---|---|---|
| **CFV** | 5 (FERM, GERM, PPP_PROD_ADJ, RER, WERM) | Citi Fair Value (equilibrium exchange rate models) — DM/EM splits |
| **GERM_WEIGHTS** | DM, EM | GERM model currency weights |
| **FXFUI** | 4 (CDF, FXF, GDF, INF) | FX Fundamental Uncertainty Index — DM/EM splits |
| **FXRMI** | 1 (GFRMI) | FX Risk Model Index — DM/EM |
| **CFWS** | 1 (CURRENCY, 20 frontier ccys) | Citi Frontier Weights (AOA, CRC, DOP, EGP, GHS, etc.) |
| **CEWS** | CURRENCY (25 EM ccys), REGION (4) | Citi EM Weights (by currency and region) |

### Forecasts

| Subcategory | Children | Description |
|---|---|---|
| **FORECAST** | 6 base ccys | Citi FX forecasts (EUR/USD, GBP/USD, AUD/JPY, etc.) |

---

## EQUITY (6 Subcategories)

| Subcategory | Children | Description | Structure |
|---|---|---|---|
| **VOLSWAP** | 197 tickers | Single-stock vol swap levels (AAPL, AMZN, MSFT, etc.) | `EQUITY.VOLSWAP.{TICKER}.FIXED_TENOR.{EXPIRY}` |
| **VARSWAP** | CONSTANT_EXPIRY, FIXED_EXPIRY | Index variance swap levels (SPX, NDX, SX5E, NKY, etc.) | `EQUITY.VARSWAP.{TYPE}.{INDEX}.{TENOR}` |
| **EQIVOL** | INDEX_CORR | Equity index implied correlation (SPX, DAX, NKY, etc.) | `EQUITY.EQIVOL.INDEX_CORR.{INDEX}.{TENOR}` |
| **CITI_EQ_INDICES** | CIS_INDEX (public), DELTAONE (regional) | Citi equity strategy indices | `EQUITY.CITI_EQ_INDICES.{TYPE}.{REGION}` |
| **FORECAST** | 15 countries/regions | Citi equity index forecasts (S&P, ASX, Nikkei, etc.) | `EQUITY.FORECAST.{COUNTRY}.{INDEX}.{FREQ}` |
| **PRIME** | (empty) | Prime brokerage data (no tags found) | — |

### VOLSWAP Notable Tickers (197 total)

US: AAPL, AMZN, GOOGL, META, MSFT, NVDA, TSLA, JPM, BAC, GS, ...
EU: ASML, SAP, LVMH, NESN, NOVN, ROG, TOTAL, SAN, ...
Index ETFs: SPY, QQQ, IWM, EEM, EFA, FXI, EWZ, GLD, ...

### VARSWAP Indices

Constant Expiry: AEX, AXJO, BVSP, DAX, FTSE, HSCE, HSI, IBEX, NKY, NDX, RTY, SMI, SPX, SX5E, UKX, ...
Fixed Expiry: Same indices + DJX, RUT, various ETFs

---

## COMMODITIES (5 Subcategories)

| Subcategory | Children | Description | Structure |
|---|---|---|---|
| **SPOT** | 3 (leaf tags) | Spot prices: OIL_PRICE_NYMEX, SPOT_GOLD, SPOT_SILVER | `COMMODITIES.SPOT.{NAME}` |
| **EIA** | 16 series | US EIA weekly petroleum data (stocks, imports, exports, production, runs) | `COMMODITIES.EIA.{SERIES}.{REGION}` |
| **IMPLIED_VOL** | 5 (Brent, WTI, Gold, Silver, Platinum) | Commodity option ATM implied vol | `COMMODITIES.IMPLIED_VOL.{PRODUCT}.ATM.{TENOR}` |
| **INDEX** | 6 Citi indices | Citi commodity strategy indices (CIGM family) | `COMMODITIES.INDEX.{NAME}.LEVEL` |
| **FORECAST** | 6 sectors | Citi commodity price forecasts | `COMMODITIES.FORECAST.{SECTOR}.{PRODUCT}.{FREQ}` |

### EIA Series

| Series | PADD Regions |
|---|---|
| CRUDE_STOCKS | PADD I–V + Total US |
| CRUDE_IMPORTS | PADD I, III, V + Total US |
| CRUDE_EXPORTS | Total US |
| CRUDE_RUNS | PADD I–V + Total US |
| DISTILLATE_STOCKS/IMPORTS/PRODUCTION/EXPORT | Various |
| GASOLINE_STOCKS/IMPORTS/PRODUCTION/EXPORT | Various |
| JET_STOCKS/PRODUCTION | Various |
| HEATING_OIL_STOCKS, ULSD_STOCKS | Various |

### FORECAST Sectors

| Sector | Products |
|---|---|
| ENERGY | Crude oil, natural gas, refined products |
| P_METALS | Precious metals (gold, silver, platinum, palladium) |
| B_METALS | Base metals (copper, aluminum, zinc, nickel, etc.) |
| BATT_METAL | Battery metals (lithium, cobalt) |
| AGRI_COMM | Agriculture (corn, soybeans, wheat, cocoa, coffee, sugar) |
| BULK_COMM | Bulk (iron ore, coal) |

### IMPLIED_VOL Products

| Tag Prefix | Product |
|---|---|
| CR_IPE_BRENT | ICE Brent crude |
| CR_NYM_CL | NYMEX WTI crude |
| XAU | Gold |
| XAG | Silver |
| XPT | Platinum |

---

## RATES (28 Subcategories)

Full details in `docs/rates/citi_velocity_api.md` — "Full Tag Tree" section.

Summary: OIS (20 pairs), SWAP_LIBOR (45 ccys), SOV_CMT (34 countries), SOV (21), XCCY_SWAP (23 ccys), XCCY_OIS_SWAP (12), BASIS_SWAPS (6 types), VOL (11 ccys), INFLATION (4 sub-types), TSY (5), BENCH_RATES (10 series), MONEY_MARKETS (9 ccys), FRA (9 EM ccys), FRA_OIS (11 G10), OIS_MEETING (10), FORWARD (24 countries), TIPS (3), T_BILL (4 tenors), FORECAST (7), INVOICESPREAD (7 tenors), + 8 niche (SSA, MBS, midcurves, spread options, etc.)
