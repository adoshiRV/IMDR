# Citi Velocity — Rates Inflation Deep Dive

Full inventory of RATES.INFLATION data available via the Citi Velocity API.

- **Explored**: 2026-03-26
- **Cache**: exploration results inline (no separate cache file)
- **DO NOT re-run** — all results documented here

---

## Overview

| Subcategory | Tags | Frequency | Data? | Description |
|---|---|---|---|---|
| **SWAP** | 5,999 | Daily | YES | Zero-coupon + forward inflation swaps |
| **SWAPTION** | 1,292 | Daily | YES | Inflation swaptions (EUR + USD) |
| **INF_CARRY** | 180 | Daily | YES | Inflation carry analytics |
| **INDEX** | 5 | Monthly | YES | CPI index levels |
| **TOTAL** | **7,476** | | | |

---

## 1. INDEX — CPI Index Levels (5 tags)

Direct leaf tags under `RATES.INFLATION.INDEX`.

| Tag | Index | Sample (2026-02-28) |
|---|---|---|
| `RATES.INFLATION.INDEX.US_CPIZU` | US CPI Urban All Items (NSA) | 326.79 |
| `RATES.INFLATION.INDEX.EURO_HICPXT` | Euro Area HICP ex-Tobacco | 100.66 |
| `RATES.INFLATION.INDEX.UK_RPI` | UK Retail Price Index | 408.20 |
| `RATES.INFLATION.INDEX.FRANCE_CPI` | France CPI ex-Tobacco | 100.20 |
| `RATES.INFLATION.INDEX.SWEDEN_CPI` | Sweden CPI | 125.37 |

**Update frequency**: Monthly (1 data point per month, published ~2 weeks after month-end).

---

## 2. SWAP — Inflation Swaps (5,999 tags)

The largest subcategory. Contains both zero-coupon (spot) and forward-starting inflation swap rates.

### Tag format

**Spot (zero-coupon)**: `RATES.INFLATION.SWAP.{CCY_INDEX}.SPOT.{TENOR}`
**Forward-starting**: `RATES.INFLATION.SWAP.{CCY_INDEX}.{FWD_START}.{SWAP_TENOR}`
**Short-dated**: `RATES.INFLATION.SWAP.{CCY_INDEX}.{SHORT_TENOR}` (1M, 3M, 6M)

### Currency/Index variants (17)

| Key | Description | Country |
|---|---|---|
| **USD_CPURNSA** | US CPI Urban NSA (full swap grid) | US |
| **US_CPI** | US CPI (spot-only, simpler grid) | US |
| **EUR_CPTFEMU** | Euro Area HICP ex-Tobacco | Eurozone |
| **GBP_UKRPI** | UK Retail Price Index | UK |
| **AUD_AUCPI** | Australia CPI | Australia |
| **JPY_JCPNGENF** | Japan CPI General (fresh) | Japan |
| **SEK_SWCPI** | Sweden CPI | Sweden |
| **ILS_ISCPIL** | Israel CPI | Israel |
| **EUR_BECPHLTH** | Belgium CPI Health | Belgium |
| **EUR_CPTFEMU** | Euro HICP | Eurozone |
| **EUR_DNCPINEW** | Denmark CPI | Denmark |
| **EUR_FRCPXTOB** | France CPI ex-Tobacco | France |
| **EUR_GRCP2000** | Greece CPI (base 2000) | Greece |
| **EUR_IECP2006** | Ireland CPI (base 2006) | Ireland |
| **EUR_ITCPI** | Italy CPI | Italy |
| **EUR_NECPIND** | Netherlands CPI | Netherlands |
| **EUR_PLCPI** | Poland CPI | Poland |
| **EUR_SPIPC** | Spain CPI | Spain |

### Tenor grid (USD_CPURNSA / EUR_CPTFEMU / GBP_UKRPI)

**Forward start tenors**: 1M, 3M, 6M, 1Y, 2Y, 3Y, 4Y, 5Y, 7Y, 10Y, 12Y, 15Y, 20Y, 25Y, 30Y, 40Y, SPOT
**Swap tenors per start**: 1Y, 2Y, 3Y, 4Y, 5Y, 6Y, 7Y, 8Y, 9Y, 10Y, 12Y, 15Y, 20Y, 25Y, 30Y, 40Y, 50Y

This gives a full forward-starting inflation swap surface (17 × 17 = up to 289 combinations per currency).

### Sample Data — Spot Rates (2026-03-25)

| Currency | 1Y | 2Y | 5Y | 10Y | 30Y |
|---|---|---|---|---|---|
| **USD (CPURNSA)** | 3.07% | 2.72% | 2.47% | 2.41% | 2.34% |
| **US_CPI** | 3.08% | 2.67% | 2.44% | 2.39% | 2.32% |
| **EUR (CPTFEMU)** | 3.08% | 2.60% | 2.22% | 2.17% | 2.31% |
| **GBP (UKRPI)** | 4.77% | 4.25% | 3.65% | 3.37% | 3.29% |

### Sample Data — Forward Swaps (2026-03-25)

| Currency | 2Yx5Y | 2Yx10Y | 5Yx5Y | 5Yx10Y |
|---|---|---|---|---|
| **USD** | 2.30% | 2.33% | 2.30% | 2.31% |
| **EUR** | — | — | 2.13% | 2.21% |
| **GBP** | — | — | 3.08% | 3.16% |

All swap rates are daily frequency, ~22 data points per 30-day window.

---

## 3. SWAPTION — Inflation Swaptions (1,292 tags)

**Tag format**: `RATES.INFLATION.SWAPTION.{CCY_INDEX}.ATM.{METRIC}.{OPTION_EXPIRY}.{SWAP_TENOR}`

Available for EUR (CPTFEMU) and USD (CPURNSA) only.

### Metrics

- **FWDPREMIUM**: Forward premium
- **NORMALVOL**: Normal (bp) volatility
- **STRADDLE_PREMIUM**: ATM straddle premium
- (possibly others)

### Expiry × Tenor grid

Same grid as SWAP: option_expiry (1Y–40Y) × swap_tenor (1Y–50Y), giving a 2D swaption vol surface similar to the rates swaption vol cube.

---

## 4. INF_CARRY — Inflation Carry Analytics (180 tags)

**Tag format**: `RATES.INFLATION.INF_CARRY.{CCY}_CARRY.{INDEX}.{METRIC}.{TENOR}`

### Currencies (6)

AUD, DEU (Germany), FRA (France), GBP, ITA (Italy), USD

### Metrics

- **IOTA**: Inflation option-implied carry
- **CARRYADJIOTA**: Carry-adjusted IOTA
- **NETBEICARRY**: Net breakeven inflation carry
- **NOMINALYIELDCARRY**: Nominal yield carry
- **REALYIELDCARRY**: Real yield carry

### Tenors

2Y, 5Y, 7Y, 10Y, 20Y, 30Y (6 tenors per metric per currency)

---

## Key Observations

1. **USD has two CPI indices**: `USD_CPURNSA` (full grid, 5,999-tag swap surface) and `US_CPI` (simpler spot-only grid). CPURNSA is the standard market convention for inflation swaps.

2. **EUR sub-indices are granular**: Beyond the headline Euro HICP, individual country CPIs (France, Italy, Spain, etc.) have their own swap curves — useful for relative value trades.

3. **Forward inflation swaps** are the most market-relevant: the 5Y5Y is the key metric watched by central banks and the market (US 5Y5Y = 2.30%, EUR = 2.13%, GBP = 3.08%).

4. **Inflation swaptions** are a niche but valuable dataset — ATM vol surfaces for EUR and USD inflation options.

---

## Build Priority

1. **INDEX** — 5 CPI levels, monthly, trivial to ingest
2. **SWAP (spot tenors)** — zero-coupon breakevens for USD/EUR/GBP, ~45 tags, daily
3. **SWAP (forward surface)** — full forward-starting grid, ~5K tags, daily
4. **INF_CARRY** — carry analytics, 180 tags, daily
5. **SWAPTION** — inflation vol surface, 1,292 tags, daily
