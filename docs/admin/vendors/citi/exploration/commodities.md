# Citi Velocity — Commodities Deep Dive

Full inventory of all COMMODITIES data available via the Citi Velocity API.

- **Explored**: 2026-03-25 (tag tree), verified data probes 2026-03-26
- **Script**: `scripts/explore/explore_commodities.py`
- **Cache**: `data/cache/commodities/commodities_deep.json`
- **DO NOT re-run** — all results cached

---

## Overview

| Subcategory | Tags | Frequency | Data? | Description |
|---|---|---|---|---|
| **IMPLIED_VOL** | 1,011 | Daily | YES | Commodity option vol surfaces |
| **FORECAST** | 115 | Irregular | YES | Citi analyst price forecasts |
| **EIA** | 67 | Weekly (Wed) | YES | US EIA petroleum status report |
| **INDEX** | 6 | — | NO | Citi CIGM indices (likely discontinued) |
| **SPOT** | 3 | Daily | YES | Oil, Gold, Silver spot prices |
| **TOTAL** | **1,202** | | | |

---

## 1. SPOT (3 tags)

Direct leaf tags — no hierarchy.

| Tag | Product | Update | Sample (2026-03-25) |
|---|---|---|---|
| `COMMODITIES.SPOT.SPOT_GOLD` | Gold (XAU/USD) | Daily | $4,507 |
| `COMMODITIES.SPOT.SPOT_SILVER` | Silver (XAG/USD) | Daily | $72.64 |
| `COMMODITIES.SPOT.OIL_PRICE_NYMEX` | WTI Crude (front month) | Daily | $91.51 |

Note: Brent crude spot is NOT available in COMMODITIES.SPOT (only WTI). Brent vol IS available under IMPLIED_VOL.

---

## 2. EIA — US Weekly Petroleum Status Report (67 tags)

**Source**: U.S. Energy Information Administration weekly petroleum report, published every Wednesday at 10:30 AM ET.

**Tag format**: `COMMODITIES.EIA.{SERIES}.{REGION}`

**Update frequency**: Weekly (~52 data points/year)

### Series x Region Matrix

| Series | Total US | PADD I (East) | PADD II (Midwest) | PADD III (Gulf) | PADD IV (Rocky Mtn) | PADD V (West) | Cushing OK |
|---|---|---|---|---|---|---|---|
| **CRUDE_STOCKS** | x | x | x | x | x | x | x |
| **CRUDE_IMPORTS** | x | x | | x | | x | |
| **CRUDE_EXPORTS** | x | | | | | | |
| **CRUDE_RUNS** | x | x | x | x | x | x | |
| **DISTILLATE_STOCKS** | x | x | x | x | x | x | |
| **DISTILLATE_IMPORTS** | x | x | | x | | | |
| **DISTILLATE_PRODUCTION** | x | x | x | x | x | x | |
| **DISTILLATES_EXPORT** | x | | | | | | |
| **GASOLINE_STOCKS** | x | x | x | x | x | x | |
| **GASOLINE_IMPORTS** | x | x | | x | | | |
| **GASOLINE_PRODUCTION** | x | x | x | x | x | x | |
| **GASOLINE_EXPORT** | x | | | | | | |
| **JET_STOCKS** | x | x | x | x | x | x | |
| **JET_PRODUCTION** | x | x | x | x | x | x | |
| **HEATING_OIL_STOCKS** | x | x | | | | | |
| **ULSD_STOCKS** | x | x | x | | | | |

### PADD Region Reference

| Region | Area | Significance |
|---|---|---|
| PADD I | East Coast (Maine to Florida) | Largest consumption center |
| PADD II | Midwest (Ohio to Dakotas) | Cushing, OK = WTI delivery point |
| PADD III | Gulf Coast (TX, LA, MS, AL, NM, AR) | >50% of US refining capacity |
| PADD IV | Rocky Mountain (MT, WY, CO, UT, ID) | Smallest, landlocked |
| PADD V | West Coast (WA, OR, CA, AK, HI, NV, AZ) | Isolated market, CA refineries |
| Cushing, OK | WTI futures delivery hub | THE key storage indicator for crude pricing |

### Key Series Explained

| Series | Measures | Units | Market Impact |
|---|---|---|---|
| CRUDE_STOCKS | Total barrels in storage | Thousands of barrels | Headline number — builds = bearish, draws = bullish |
| CRUDE_RUNS | Barrels processed by refineries | Thousands of barrels/day | Refinery utilization / demand proxy |
| CRUDE_IMPORTS | Barrels imported | Thousands of barrels/day | Supply inflows |
| CRUDE_EXPORTS | Barrels exported | Thousands of barrels/day | US as swing supplier signal |
| GASOLINE_STOCKS | Gasoline in storage | Thousands of barrels | Seasonal demand (summer driving season) |
| DISTILLATE_STOCKS | Diesel + heating oil in storage | Thousands of barrels | Industrial demand proxy |

### Sample Data

- Crude stocks Total US: 456,185 thousand barrels (2026-03-20)
- Crude imports Total US: 6,464 thousand barrels/day (2026-03-20)
- Data range: weekly from 2025-03-28 to 2026-03-20 (52 points in 1 year)

---

## 3. IMPLIED_VOL — Commodity Vol Surfaces (1,011 tags)

The largest subcategory. Full option implied vol surfaces for 5 products.

### 3a. Precious Metals Vol (XAU, XAG, XPT)

**Tag format**: `COMMODITIES.IMPLIED_VOL.{PRODUCT}.USD.{STRIKE}.{TENOR}`

#### Strike Types

| Strike | Description | Available for |
|---|---|---|
| ATM | At-the-money | All 3 |
| 10RR / 25RR / 35RR | Risk reversal (call vol - put vol) | All 3 |
| 10STR / 25STR / 35STR | Strangle (avg of OTM call + put vol) | All 3 |
| C10 / C25 / C35 | Delta call absolute vol | All 3 |
| P10 / P25 / P35 | Delta put absolute vol | All 3 |
| SVVSTAR | Stochastic vol-of-vol star | All 3 |
| SVXI | Stochastic vol xi | All 3 |
| XI | Vol xi index | All 3 |
| ASK | Ask-side vol | XPT only |
| BID | Bid-side vol | XPT only |
| ATMF | ATM forward vol | XPT only |

#### Tenor Grids

| Product | Tenors | Count |
|---|---|---|
| **XAU** (Gold) | ON, 1W, 2W, 1M, 2M, 3M, 6M, 9M, 1Y, 2Y, 3Y, 5Y, 7Y, 10Y | 14 |
| **XAG** (Silver) | ON, 1W, 2W, 1M, 2M, 3M, 6M, 9M, 1Y, 2Y, 3Y, 5Y, 7Y, 10Y | 14 |
| **XPT** (Platinum) | ON, 2D, 4D, 10D, 11D, 12D, 13D, 1W, 2W, 1M, 2M, 3M, 6M, 9M, 18M, 1Y, 2Y, 3Y, 4Y, 5Y, 6Y, 7Y, 8Y, 9Y, 10Y, 15Y, 30Y | 27 |

#### Tag Counts

| Product | Standard Strikes | Exotic Strikes | Tenors | Total Tags |
|---|---|---|---|---|
| XAU | 13 x 14 | 3 x 2 (SVVSTAR/SVXI/XI have fewer tenors) | 14 | ~186 |
| XAG | 13 x 14 | 3 x 2 | 14 | ~186 |
| XPT | 13 x 27 | 6 x 27 | 27 | ~513 |

#### Sample Values (2026-03-25)

| Tag | Value |
|---|---|
| XAU.USD.ATM.1M | 34.03% |
| XAU.USD.ATM.1W | 38.97% |
| XAU.USD.ATM.1Y | 25.58% |
| XAU.USD.ATM.10Y | 25.26% |
| XAG.USD.25RR.1M | -1.75 (put skew) |
| XAG.USD.10STR.1M | 6.45 |

### 3b. Oil Vol (CR_IPE_BRENT, CR_NYM_CL)

**Tag format**: `COMMODITIES.IMPLIED_VOL.{PRODUCT}.ATM.NEARBY{NN}_M`

ATM vol only (no smile), indexed by **contract month** rather than calendar tenor.

| Product | Contracts | Tags |
|---|---|---|
| CR_IPE_BRENT (ICE Brent) | NEARBY01_M to NEARBY12_M | 12 |
| CR_NYM_CL (NYMEX WTI) | NEARBY01_M to NEARBY12_M | 12 |

**Note**: Oil vol data is sparser than precious metals due to contract roll effects. WTI Nearby01 had only 4 data points in 30 days.

#### Sample Values (2026-03-19)

| Tag | Value |
|---|---|
| CR_NYM_CL.ATM.NEARBY01_M | 91.31% |
| CR_NYM_CL.ATM.NEARBY02_M | 76.78% |
| CR_NYM_CL.ATM.NEARBY03_M | 65.25% |

---

## 4. FORECAST — Citi Commodity Price Forecasts (115 tags)

**Tag format**: `COMMODITIES.FORECAST.{SECTOR}.{PRODUCT}.{FREQ}.PRICE_FCST.CITI`

**Update frequency**: Irregular — updates when Citi analysts revise forecasts.

### Frequencies

| Frequency | Tag segment | Description |
|---|---|---|
| Annual | `ANNUAL` | Full-year average forecast |
| Quarterly | `QTR` | Quarterly average forecast |
| Short-term | `POINT_PRICES.0_3M` | 0-3 month price forecast |
| Medium-term | `POINT_PRICES.6_12M` | 6-12 month price forecast |

### Products by Sector

| Sector | Products | Tag Prefix |
|---|---|---|
| **ENERGY** | ICE Brent (`ICE_BRNT`), WTI (`NYM_CL`), Henry Hub Natural Gas (`HH_NGAS`), JKM LNG (`JKM_LNG`), TTF LNG (`TTF_LNG`) | `ENERGY` |
| **P_METALS** | Gold (`COMEX_GOLD`), Silver (`SILVER`), Palladium (`PALLADIUM`), Platinum (`PLATINUM`), Uranium (`URANIUM`) | `P_METALS` |
| **B_METALS** | Aluminum (`LME_AL`), Copper (`LME_CU`), Lead (`LME_LE`), Nickel (`LME_NI`), Tin (`LME_TI`), Zinc (`LME_ZI`) | `B_METALS` |
| **BATT_METAL** | CME Lithium Hydroxide (`CME_LITH_HY`), Cobalt (`COBALT`), GFEX Lithium Carbonate (`GFEX_LITH_CA`) | `BATT_METAL` |
| **AGRI_COMM** | CBOT Corn (`CBOT_CORN`), Soybeans (`CBOT_SOY`), Wheat (`CBOT_WHEAT`), ICE Cocoa (`ICE_COCOA`), Coffee (`ICE_COFFEE`), Sugar (`SUGAR`) | `AGRI_COMM` |
| **BULK_COMM** | Iron Ore Spot (`IRON_ORE_SPOT`), Hard Coke Coal (`HARD_COKE_COAL`), Thermal Coal Asia (`THERMAL_COAL_ASIA`) | `BULK_COMM` |

### Sample Values

| Tag | Points | Value |
|---|---|---|
| `ENERGY.ICE_BRNT.ANNUAL.PRICE_FCST.CITI` | 1 (2025-12-31) | $68.00 |
| `ENERGY.HH_NGAS.POINT_PRICES.0_3M.PRICE_FCST.CITI` | 259 (daily revisions) | $2.50 |
| `ENERGY.HH_NGAS.QTR.PRICE_FCST.CITI` | 4 (quarterly) | $3.70 |
| `P_METALS.COMEX_GOLD.QTR.PRICE_FCST.CITI` | 3 (older vintage, 2025) | $2,800 |
| `P_METALS.PALLADIUM.ANNUAL.PRICE_FCST.CITI` | 1 | $1,140 |

**Note**: Energy forecasts are most actively updated (nat gas point prices had 259 data points). Precious metals forecasts appear staler (gold quarterly still showing 2025 vintage at $2,800 vs current $4,500).

---

## 5. INDEX — Citi CIGM Commodity Indices (6 tags) — LIKELY DISCONTINUED

| Tag | Index |
|---|---|
| `COMMODITIES.INDEX.CIGMCCET.LEVEL.CITI` | Citi Commodity Excess Return |
| `COMMODITIES.INDEX.CIGMCET3.LEVEL.CITI` | Citi Commodity Excess Return 3M |
| `COMMODITIES.INDEX.CIGMECET.LEVEL.CITI` | Citi Energy Commodity Excess Return |
| `COMMODITIES.INDEX.CIGMEET3.LEVEL.CITI` | Citi Energy Commodity Excess Return 3M |
| `COMMODITIES.INDEX.CIGMGCET.LEVEL.CITI` | Citi Gold Commodity Excess Return |
| `COMMODITIES.INDEX.CIGMGET3.LEVEL.CITI` | Citi Gold Commodity Excess Return 3M |

All 6 tags return empty arrays across all date ranges tested. Tags are browsable/listable but contain no data. Likely discontinued.

---

## Pipeline Priority Assessment

| Priority | Subcategory | Rationale |
|---|---|---|
| **1** | IMPLIED_VOL (precious metals) | 885 tags, daily, proprietary Citi pricing, analogous to FX vol pipeline |
| **2** | SPOT | 3 tags, daily, essential benchmark prices |
| **3** | EIA | 67 tags, weekly, clean fundamental data |
| **4** | IMPLIED_VOL (oil) | 24 tags, daily but sparse (contract rolls) |
| **5** | FORECAST | 115 tags, unique Citi research data but irregular updates |
| **Skip** | INDEX | No data |
