# Citi Velocity — Equity Deep Dive

Full inventory of all EQUITY data available via the Citi Velocity API.

- **Explored**: 2026-03-26
- **Scripts**: `scripts/explore/explore_equity.py`, `scripts/explore/explore_equity_indices.py`, `scripts/explore/explore_equity_indices2.py`
- **Cache**: `data/cache/equity/equity_deep.json`, `data/cache/equity/equity_indices_universe.json`
- **DO NOT re-run** — all results cached

---

## Overview

| Subcategory | Tags | Frequency | Data? | Description |
|---|---|---|---|---|
| **VARSWAP** | 3,090 | Daily | YES | Variance swap fair strikes |
| **EQIVOL** | 2,643 | Daily | YES | Equity implied vol / index correlation |
| **VOLSWAP** | 2,561 | Daily | YES | Vol swap levels by tenor |
| **CITI_EQ_INDICES** | 1,063 | — | NO | Citi proprietary indices (subscription?) |
| **PRIME** | 407 | — | ? | Prime brokerage data |
| **FORECAST** | 15 | Irregular | NO | Equity index forecasts |
| **EQUITY_INDEX** (separate namespace) | 24* | Daily | YES | Major global index levels |
| **TOTAL** | **~9,803** | | | |

*EQUITY_INDEX uses a different tag namespace (`EQUITY.EQUITY_INDEX..{TICKER}.LEVEL.REUTERS`) not discoverable via tagbrowsing.

---

## 1. Equity Index Levels (24 tickers)

**Tag format**: `EQUITY.EQUITY_INDEX..{TICKER}.LEVEL.REUTERS`

The double-dot is intentional (empty issuer segment). Only `LEVEL.REUTERS` qualifier works — no OHLCV, no CITI source. ETFs are NOT available via this namespace. Tags cannot be browsed via tagbrowsing but can be fetched directly.

### Universe

**US (6)**

| Ticker | Index | Currency | Sample (2026-03-25) |
|---|---|---|---|
| SPX | S&P 500 | USD | 6,591.90 |
| NDX | Nasdaq 100 | USD | 24,163.00 |
| RUT | Russell 2000 | USD | 2,536.38 |
| MID | S&P MidCap 400 | USD | 3,413.98 |
| OEX | S&P 100 | USD | 3,217.87 |
| VIX | CBOE Volatility Index | USD | 25.33 |

**Europe (6)**

| Ticker | Index | Currency | Sample (2026-03-25) |
|---|---|---|---|
| STOXX50E | Euro Stoxx 50 | EUR | 5,649.33 |
| SX7E | Euro Stoxx Banks | EUR | 243.87 |
| FTSE | FTSE 100 | GBP | 10,106.80 |
| FCHI | CAC 40 | EUR | 7,846.55 |
| OMXS30 | OMX Stockholm 30 | SEK | 2,943.35 |
| WIG20 | Warsaw WIG 20 | PLN | 3,312.41 |

**Asia-Pacific (12)**

| Ticker | Index | Currency | Sample (2026-03-26) |
|---|---|---|---|
| N225 | Nikkei 225 | JPY | 53,603.70 |
| TOPX | TOPIX | JPY | 3,642.80 |
| HSI | Hang Seng | HKD | 24,856.40 |
| HSCE | Hang Seng China Enterprises | HKD | 8,389.93 |
| HSTECH | Hang Seng Tech | HKD | 4,761.54 |
| TWII | Taiwan Weighted | TWD | 33,337.60 |
| TAMSCI | MSCI Taiwan | TWD | 1,470.66 |
| AXJO | ASX 200 | AUD | 8,525.70 |
| KS200 | KOSPI 200 | KRW | 808.89 |
| NSEI | Nifty 50 | INR | 23,306.50 |
| SIMSCI | MSCI Singapore | SGD | 441.84 |
| SET | SET Index | THB | 6,613.36 |

### Volatility Indices

Also available via `EQUITY.EQUITY_INDEX..{TICKER}.LEVEL.REUTERS`:

| Ticker | Index | Last Value |
|---|---|---|
| VIX | CBOE VIX (S&P 500 30d implied vol) | 25.33 |
| VIX3M | CBOE VIX 3-Month | 25.63 |
| VIX9D | CBOE VIX 9-Day | 25.26 |
| VVIX | CBOE Vol-of-VIX | 119.37 |
| VXN | CBOE Nasdaq 100 Volatility | 27.65 |

Not available: V2X/VSTOXX (Euro vol), VDAX, VFTSE, SKEW, VIX1D.

**Note**: MOVE index (rates vol) is NOT available on Citi Velocity — it's an ICE/BofA proprietary index.

### Not available

Probed but returned no data: DAX, SX5E, SXXP, IBEX, SMI, AEX, FTMIB, HSCEI, SHCOMP, CSI300, KOSPI, IBOV, BVSP, MEXBOL, STI, KLCI, JCI, PCOMP, and all ETFs (SPY, QQQ, etc.).

### Universe config

- **YAML**: `src/imdr/universe/equity.yml`
- **Python**: `src/imdr/universe/equity.py` — `EquityUniverse` class

---

## 2. VOLSWAP — Vol Swap Levels (2,561 tags)

**Tag format**: `EQUITY.VOLSWAP.{TICKER}.FIXED_TENOR.{TENOR}`

Vol swap fair value levels for 197 single-stock and index tickers, each with 13 tenors.

### Structure

- **197 tickers**: US large-cap (AAPL_O, MSFT_O, NVDA_O, ...), European (LVMH_PA, SAPG_DE, ...), global indices (SPX, NDX, GDAXI, FTSE, ...)
- **13 tenors**: 1M, 2M, 3M, 6M, 9M, 1Y, 2Y, 3Y, 4Y, 5Y, 6Y, 7Y, 10Y
- **Leaf tag**: the tenor itself (e.g. `EQUITY.VOLSWAP.AAPL_O.FIXED_TENOR.3M`)

### Sample Data (30 days, AAPL_O)

| Tenor | Vol Swap Level | Points |
|---|---|---|
| 1M | 0.258–0.276 | 22 |
| 3M | 0.284–0.308 | 22 |
| 1Y | 0.293–0.314 | 22 |
| 5Y | 0.309–0.323 | 22 |
| 10Y | 0.330–0.346 | 22 |

Values are annualized vol levels (decimal, not %).

### Ticker naming convention

- `_O` = Nasdaq listed (AAPL_O, MSFT_O, AMZN_O)
- `_N` = NYSE listed (JPM_N, BAC_N, JNJ_N)
- `_PA` = Euronext Paris (LVMH_PA, TOTF_PA)
- `_DE` = Xetra (SAPG_DE, SIEGN_DE)
- `_L` = London (BP_L, GLEN_L)
- `_AS` = Amsterdam (ASML_AS, INGA_AS)
- `_MI` = Milan (ENEI_MI, ISP_MI)
- `_MC` = Madrid (SAN_MC, ITX_MC)
- No suffix = indices (SPX, NDX, GDAXI, FTSE, HSI, etc.)

---

## 3. VARSWAP — Variance Swap Fair Strikes (3,090 tags)

**Tag format**: `EQUITY.VARSWAP.{EXPIRY_TYPE}.{INDEX}.{TENOR}.FAIR_STRIKE.EOD.CITI`

Variance swap fair strike values for major indices, available in two expiry types.

### Structure

- **CONSTANT_EXPIRY**: 20+ indices — rolling constant-maturity tenors
- **FIXED_EXPIRY**: 20+ indices — fixed IMM expiry dates

### Indices (CONSTANT_EXPIRY sample)

AEX, AXJO, BVSP, CECEEUR, EEM_P, EFA_P, FCHI, FTMIB, FTSE, FXI_P, GDAXI, HSCE, HSI, IBEX, IWM_P, JTOPI, KS200, MNX, N225, NDX, ...

### Sample Data (30 days, SPX + NDX constant expiry)

| Index | Tenor | Fair Strike | Points |
|---|---|---|---|
| SPX | 3M | 0.219–0.250 | 21 |
| SPX | 1Y | 0.245–0.260 | 22 |
| SPX | 5Y | 0.254–0.263 | 19 |
| NDX | 3M | 0.271–0.304 | 20 |
| NDX | 1Y | 0.300–0.314 | 21 |
| NDX | 10Y | 0.300–0.302 | 22 |

Values are annualized variance swap fair strikes (decimal).

---

## 4. EQIVOL — Index Implied Vol Correlation (2,643 tags)

**Tag format**: `EQUITY.EQIVOL.INDEX_CORR.{INDEX}.{...}`

Implied volatility and cross-index correlation data for 11 major indices: AS51, DAX, HSCEI, HSI, NDX, NKY, RTY, SMI, SPX, SX5E, UKX.

### Sample Data (30 days)

SPX, SX5E, NKY cross-correlation data confirmed returning ~21 pts / 30 days.

---

## 5. CITI_EQ_INDICES (1,063 tags)

Citi proprietary equity indices under two branches:

- **CIS_INDEX → PUBLIC**: Citi investment strategy public indices
- **DELTAONE**: Regions ALL, APAC, EMEA, GLOBAL, NAM — hundreds of proprietary Citi factor/thematic indices per region (e.g. CGUSANLG, CGUSBIO, CGUSCYCL, ...)

Data probes returned 0 rows — likely requires a separate subscription or entitlement.

---

## 6. PRIME (407 tags)

Prime brokerage data. Top-level browse returned 0 children in shallow cache, but taglisting found 407 tags. Not probed for data.

---

## 7. FORECAST (15 tags)

Equity index forecasts for 15 countries/regions:

ASIA_EX_JPN, AUS, CHL, CHN, GBR, GEMS, GLOBAL, HKG, IDN, JPN, KOR, MEX, PAN_EURO, SGP, USA

Each country maps to one benchmark index (e.g. USA → S&P_500, GBR → FTSE_100). Data probes returned 0 rows — possibly Citi-internal or discontinued.

---

---

## Related: Citi Macro Indices (FX namespace)

These are Citi proprietary macro indicators found under the FX category, useful for macro hedge fund analysis:

### FX.CITIPAIN — Citi PAIN Index (10 tags)

Citi's FX positioning/pain indicator per G10 currency. Daily, all confirmed.

| Tag | Currency | Last Value |
|---|---|---|
| `FX.CITIPAIN.USD` | US Dollar | -0.94 |
| `FX.CITIPAIN.EUR` | Euro | -3.85 |
| `FX.CITIPAIN.GBP` | Sterling | 8.65 |
| `FX.CITIPAIN.JPY` | Yen | -13.82 |
| `FX.CITIPAIN.AUD` | Aussie | 37.59 |
| `FX.CITIPAIN.CAD` | Canadian | -16.68 |
| `FX.CITIPAIN.CHF` | Swiss Franc | -20.64 |
| `FX.CITIPAIN.NOK` | Norwegian Krone | 22.71 |
| `FX.CITIPAIN.NZD` | Kiwi | 24.84 |
| `FX.CITIPAIN.SEK` | Swedish Krona | 11.20 |

### FX.CTOT — Citi Terms of Trade (68 tags)

Citi's commodity terms-of-trade model. Two groups: DM (developed) and EM (emerging).

**Tag format**: `FX.CTOT.{DM|EM}.CTOT_{CCY}`

Sample DM values (2026-03-25): AUD +53.7, CAD +16.2, JPY -31.6, NOK +103.0.

---

## Build Priority

1. **Equity Index Levels** — simplest, 24 tickers, daily close, direct pipeline
2. **VOLSWAP** — richest single-stock data, 197 tickers × 13 tenors
3. **VARSWAP** — index variance swaps, useful for vol surface analysis
4. **EQIVOL** — cross-index correlation, useful for portfolio analytics
