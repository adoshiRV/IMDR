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

#### FORWARD Sub-types (expanded 2026-04-21)

Full tag: `FX.FORWARD.{TYPE}.{C1}.{C2}.{TENOR}.CITI` — see [docs/fx/citi_velocity_fx.md](../fx/citi_velocity_fx.md) for complete coverage.

| Type | Description | Base ccys | USD-base quotes |
|---|---|---|---|
| `FWD_OUTRIGHT` | Forward outright rates | **35 bases** | **56 quotes** |
| `FWD_POINT` | Forward points (raw) | 35 bases | 56 quotes |
| `FWD_POINT_PIP` | Forward points (pips) | 35 bases | 56 quotes |
| `FWD_IMM` | IMM-dated forwards | 10 ccys only (AUD, BWP, EUR, GBP, NZD, USD, XAG, XAU, XPD, XPT) | — |

**Base ccys (35):** AED, ARS, AUD, BRL, CAD, CHF, CNH, CNY, CZK, DKK, EUR, GBP, HKD, HRK, ILS, INR, JPY, KWD, MXN, NOK, NZD, PEN, PLN, RON, RUB, SEK, SGD, THB, TRY, USD, XAG, XAU, XPD, XPT, ZAR.

**NDF currencies (KRW, IDR, PHP, TWD, etc.) are not forward bases** — they exist only as quotes under USD. Pattern `FX.FORWARD.FWD_OUTRIGHT.USD.KRW.1M.CITI` returns data; reverse direction `KRW.USD` errors.

**Tenor grid (29 tenors)** — confirmed identical on EUR.USD and USD.JPY:
`ON, SN, TN, 1W, 2W, 3W, 1M, 2M, 3M, 4M, 5M, 6M, 7M, 8M, 9M, 10M, 11M, 1Y, 15M, 18M, 2Y, 3Y, 4Y, 5Y, 6Y, 7Y, 8Y, 9Y, 10Y`.

#### SPOT

Tag: `FX.SPOT.{C1}.{C2}.CITI` (mid). Optional side variants: `.BID.CITI`, `.ASK.CITI`, `.MID.CITI`.

**USD-base quotes: 68 ccys** — much broader than forwards (includes KRW, IDR, PHP, TWD, VND, NGN, PKR, ZMW, etc., which have no forward tags).

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

## EQUITY (6 Subcategories + Index Level Namespace)

> **Deep dive**: `docs/equity/citi_velocity_equity.md` — full exploration with sample data (2026-03-26)

| Subcategory | Tags | Data? | Description | Structure |
|---|---|---|---|---|
| **EQUITY_INDEX** (separate namespace) | 24 | YES | Major global index levels | `EQUITY.EQUITY_INDEX..{TICKER}.LEVEL.REUTERS` |
| **VARSWAP** | 3,090 | YES | Index variance swap fair strikes | `EQUITY.VARSWAP.{TYPE}.{INDEX}.{TENOR}.FAIR_STRIKE.EOD.CITI` |
| **EQIVOL** | 2,643 | YES | Equity index implied vol/correlation | `EQUITY.EQIVOL.INDEX_CORR.{INDEX}.{...}` |
| **VOLSWAP** | 2,561 | YES | Single-stock vol swap levels (197 tickers) | `EQUITY.VOLSWAP.{TICKER}.FIXED_TENOR.{TENOR}` |
| **CITI_EQ_INDICES** | 1,063 | NO | Citi proprietary indices (subscription?) | `EQUITY.CITI_EQ_INDICES.{TYPE}.{REGION}` |
| **PRIME** | 407 | ? | Prime brokerage data | — |
| **FORECAST** | 15 | NO | Equity index forecasts | `EQUITY.FORECAST.{COUNTRY}.{INDEX}.{FREQ}` |

### Equity Index Levels (24 tickers)

Tag format: `EQUITY.EQUITY_INDEX..{TICKER}.LEVEL.REUTERS` (double-dot intentional, only LEVEL.REUTERS works).

**US**: SPX, NDX, RUT, MID, OEX, VIX, VIX3M, VIX9D, VVIX, VXN
**Europe**: STOXX50E, SX7E, FTSE, FCHI, OMXS30, WIG20
**Asia-Pacific**: N225, TOPX, HSI, HSCE, HSTECH, TWII, TAMSCI, AXJO, KS200, NSEI, SIMSCI, SET

Universe config: `src/imdr/universe/equity.yml`

### VOLSWAP Notable Tickers (197 total)

US: AAPL, AMZN, GOOGL, META, MSFT, NVDA, TSLA, JPM, BAC, GS, ...
EU: ASML, SAP, LVMH, NESN, NOVN, ROG, TOTAL, SAN, ...
Index ETFs: SPY, QQQ, IWM, EEM, EFA, FXI, EWZ, GLD, ...

### VARSWAP Indices

Constant Expiry: AEX, AXJO, BVSP, DAX, FTSE, HSCE, HSI, IBEX, NKY, NDX, RTY, SMI, SPX, SX5E, UKX, ...
Fixed Expiry: Same indices + DJX, RUT, various ETFs

---

## COMMODITIES (5 Subcategories — 1,202 tags total)

Deep dive explored 2026-03-25 via `scripts/explore/explore_commodities.py`. Full cache: `data/cache/commodities/commodities_deep.json`.

| Subcategory | Tags | Description | Structure |
|---|---|---|---|
| **SPOT** | 3 | Spot prices: OIL_PRICE_NYMEX, SPOT_GOLD, SPOT_SILVER | `COMMODITIES.SPOT.{NAME}` |
| **EIA** | 67 | US EIA weekly petroleum data (stocks, imports, exports, production, runs) | `COMMODITIES.EIA.{SERIES}.{REGION}` |
| **IMPLIED_VOL** | 1,011 | Full commodity vol surfaces (5 products x strikes x tenors) | See below |
| **INDEX** | 6 | Citi commodity strategy indices (CIGM family) | `COMMODITIES.INDEX.{NAME}.LEVEL.CITI` |
| **FORECAST** | 115 | Citi commodity price forecasts (6 sectors, ~30 products) | `COMMODITIES.FORECAST.{SECTOR}.{PRODUCT}.{FREQ}.PRICE_FCST.CITI` |

> **DATA VERIFIED (2026-03-26):** SPOT, EIA, IMPLIED_VOL, FORECAST all return data via `fetch_historical` with `frequency="DAILY"`. INDEX (CIGM) returns empty arrays — likely discontinued. EIA updates weekly (~52 pts/yr), FORECAST updates irregularly (analyst revisions).

### EIA Series (67 tags)

| Series | PADD Regions |
|---|---|
| CRUDE_STOCKS | PADD I–V + Total US + Cushing OK (7 regions) |
| CRUDE_IMPORTS | PADD I, III, V + Total US (4) |
| CRUDE_EXPORTS | Total US (1) |
| CRUDE_RUNS | PADD I–V + Total US (6) |
| DISTILLATE_STOCKS | PADD I–V + Total US (6) |
| DISTILLATE_IMPORTS | PADD I, III + Total US (3) |
| DISTILLATE_PRODUCTION | PADD I–V + Total US (6) |
| DISTILLATES_EXPORT | Total US (1) |
| GASOLINE_STOCKS | PADD I–V + Total US (6) |
| GASOLINE_IMPORTS | PADD I, III + Total US (3) |
| GASOLINE_PRODUCTION | PADD I–V + Total US (6) |
| GASOLINE_EXPORT | Total US (1) |
| JET_STOCKS | PADD I–V + Total US (6) |
| JET_PRODUCTION | PADD I–V + Total US (6) |
| HEATING_OIL_STOCKS | PADD I + Total US (2) |
| ULSD_STOCKS | PADD I, II + Total US (3) |

### FORECAST (115 tags)

Tag: `COMMODITIES.FORECAST.{SECTOR}.{PRODUCT}.{FREQ}.PRICE_FCST.CITI`

Frequencies: `ANNUAL`, `QTR`, `POINT_PRICES.0_3M`, `POINT_PRICES.6_12M`

| Sector | Products |
|---|---|
| ENERGY | IPE_BRENT, NYM_CL (WTI), US_NAT_GAS, JKM_LNG, TTF_LNG |
| P_METALS | GOLD, SILVER, PALLADIUM, PLATINUM, URANIUM |
| B_METALS | LME_AL, LME_CU, LME_LE (Lead), LME_NI, LME_TI (Tin), LME_ZI (Zinc) |
| BATT_METAL | CME_LITH_HY, COBALT, GFEX_LITH_CA |
| AGRI_COMM | CBOT_CORN, CBOT_SOY, CBOT_WHEAT, ICE_COCOA, ICE_COFFEE, SUGAR |
| BULK_COMM | HARD_COKE_COAL, IRON_ORE_SPOT, THERMAL_COAL_ASIA |

### IMPLIED_VOL (1,011 tags) — Deep Dive

**Oil products** — ATM only, contract month codes:
- Tag: `COMMODITIES.IMPLIED_VOL.{PRODUCT}.ATM.NEARBY{NN}_M`
- CR_IPE_BRENT: ATM x NEARBY01_M through NEARBY12_M (12 tags)
- CR_NYM_CL: ATM x NEARBY01_M through NEARBY12_M (12 tags)

**Precious metals** — full vol surfaces with strikes:
- Tag: `COMMODITIES.IMPLIED_VOL.{PRODUCT}.USD.{STRIKE}.{TENOR}`

| Product | Strikes | Tenors | Tags |
|---|---|---|---|
| **XAU** (Gold) | 13: ATM, 10RR, 10STR, 25RR, 25STR, 35RR, 35STR, C10, C25, C35, P10, P25, P35 + SVVSTAR, SVXI, XI | 14: ON, 1W, 2W, 1M, 2M, 3M, 6M, 9M, 1Y, 2Y, 3Y, 5Y, 7Y, 10Y | ~186 |
| **XAG** (Silver) | Same 13 + SVVSTAR, SVXI, XI | 14: same as XAU | ~186 |
| **XPT** (Platinum) | 13 + ASK, ATMF, BID, SVVSTAR, SVXI, XI (19 total) | 27: ON, 2D, 4D, 10D, 11D, 12D, 13D, 1W, 2W, 1M, 2M, 3M, 6M, 9M, 18M, 1Y, 2Y, 3Y, 4Y, 5Y, 6Y, 7Y, 8Y, 9Y, 10Y, 15Y, 30Y | ~513 |

**Strike types explained:**
- ATM = at-the-money
- 10/25/35 RR = risk reversal (call vol − put vol)
- 10/25/35 STR = strangle (avg of call + put vol)
- C10/C25/C35 = delta call vol
- P10/P25/P35 = delta put vol
- ASK/BID = bid-ask spread
- ATMF = ATM forward
- SVVSTAR/SVXI/XI = exotic vol indices

### INDEX (6 tags)

| Tag | Index |
|---|---|
| CIGMCCET | Citi Commodity Excess Return |
| CIGMCET3 | Citi Commodity Excess Return 3M |
| CIGMECET | Citi Energy Commodity Excess Return |
| CIGMEET3 | Citi Energy Commodity Excess Return 3M |
| CIGMGCET | Citi Gold Commodity Excess Return |
| CIGMGET3 | Citi Gold Commodity Excess Return 3M |

---

## RATES (28 Subcategories — ~170K+ tags)

> **Deep dives** (2026-03-26):
> - `docs/rates/citi_velocity_rates_full.md` — full catalog of all 24 remaining subcategories (135,915 tags)
> - `docs/rates/citi_velocity_inflation.md` — INFLATION deep dive (7,476 tags)
> - `docs/rates/sov_cmt_exploration.md` — SOV_CMT deep dive (8,250 tags, 32 countries confirmed)
> - `docs/rates/xccy_ois_exploration.md` — XCCY_OIS_SWAP deep dive (76,418 tags, all 90 G10 pairs)
> - `docs/rates/swaption_vol_schema.md` — VOL (swaption vol) schema + operations

### Tag counts by subcategory

| Subcategory | Tags | Data? | Description |
|---|---|---|---|
| **XCCY_OIS_SWAP** | 76,418 | YES | Cross-currency OIS basis (10 G10 ccys, all pairs) |
| **XCCY_SWAP** | 12,560 | NO* | Legacy LIBOR cross-currency basis |
| **MBS** | 11,321 | NO* | US mortgage-backed securities analytics |
| **SOV** | 10,909 | partial | Sovereign bond spreads, butterflies |
| **SOV_CMT** | 8,250 | YES | Sovereign constant-maturity yields (34 countries) |
| **BASIS_SWAPS** | 6,656 | partial | Tenor basis swaps |
| **INFLATION.SWAP** | 5,999 | YES | Zero-coupon + forward inflation swaps |
| **MIDCURVES** | 3,516 | ? | Swaption mid-curves |
| **AGENCY_INVENTORY** | 2,344 | ? | Agency bond analytics |
| **INFLATION.SWAPTION** | 1,292 | YES | Inflation swaptions (EUR + USD) |
| **FORWARD** | 864 | YES | Sovereign forward yields |
| **SSA** | 708 | YES | Supranational/agency spreads |
| **SPREAD_OPTIONS** | 576 | ? | Rate spread options |
| **OIS_MEETING** | 449 | NO* | CB meeting-dated OIS |
| **FRA** | 445 | ? | Forward rate agreements |
| **MONEY_MARKETS** | 229 | NO* | Short-term fixings |
| **INFLATION.INF_CARRY** | 180 | YES | Inflation carry analytics |
| **FRA_OIS** | 121 | ? | OIS-based FRA |
| **SSA_CS** | 100 | ? | SSA cross-currency spreads |
| **OIS_INVOICESPREAD** | 44 | ? | OIS invoice spreads |
| **POS_MON** | 32 | ? | Rates positioning monitor |
| **TIPS** | 26 | YES | US TIPS (breakevens, real yields, carry) |
| **TSY** | 299 | YES | US Treasuries (OTR yields, butterflies) |
| **T_BILL** | 12 | YES | US T-Bill yields, prices, SOFR spreads |
| **FORECAST** | 12 | NO* | Citi rate forecasts |
| **BENCH_RATES** | 10 | YES | Central bank policy rates |
| **INFLATION.INDEX** | 5 | YES | CPI index levels (monthly) |

Already built: OIS, SWAP_LIBOR (in `rates.yml` universe), VOL (swaption vol pipeline)
