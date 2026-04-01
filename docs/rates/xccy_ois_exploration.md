# XCCY_OIS_SWAP — Cross-Currency OIS Basis: Deep Exploration

- **Explored**: 2026-03-26
- **Total tags**: 76,418
- **DO NOT re-run** — all results documented here

---

## Tag Format

**Spot**: `RATES.XCCY_OIS_SWAP.{CCY1}.{CCY2}.SPOT.{TENOR}.{LEG}.BASIS_SPREAD`
**Forward-starting**: `RATES.XCCY_OIS_SWAP.{CCY1}.{CCY2}.{FWD_START}.{TENOR}.{LEG}.BASIS_SPREAD`

Where:
- `{CCY1}` / `{CCY2}` = currency pair
- `{FWD_START}` = forward start tenor (or `SPOT` for zero-start)
- `{TENOR}` = swap tenor
- `{LEG}` = `BASE_LEG` or `SPREAD_LEG`

---

## Currency Pairs

### CCY1 base currencies (12)

AUD, AUD_BBSW, CAD, CHF, EUR, GBP, JPY, NOK, NZD, NZD_BKBM, SEK, USD

(AUD_BBSW and NZD_BKBM are IBOR-linked variants)

### EUR cross-currency pairs (9)

EUR vs: AUD, CAD, CHF, GBP, JPY, NOK, NZD, SEK, USD

### Full pair matrix

All 10 G10 currencies × 9 counterparts = 90 directional pairs. **All 90 return data** at the 5Y SPOT point.

---

## Tenor Grid

### Spot tenors (20)

3M, 6M, 9M, 18M, 1Y, 2Y, 3Y, 4Y, 5Y, 6Y, 7Y, 8Y, 9Y, 10Y, 11Y, 12Y, 15Y, 20Y, 25Y, 30Y

### Forward start tenors (19)

1M, 3M, 6M, 1Y, 2Y, 3Y, 4Y, 5Y, 6Y, 7Y, 8Y, 9Y, 10Y, 11Y, 12Y, 15Y, 20Y, 25Y, 30Y

Each forward start has the same 20-tenor grid as SPOT.

---

## Sample Spot Basis Data (2026-03-25, 5Y BASE_LEG)

### G10 vs USD

| Pair | 5Y Basis (bp) | Notes |
|---|---|---|
| EUR/USD | -5.99 | Tight, stable |
| GBP/USD | -0.78 | Near zero |
| JPY/USD | -39.51 | Wide — reflects BOJ policy divergence |
| CHF/USD | -18.28 | Moderate |
| AUD/USD | +15.67 | Positive (AUD funding premium) |
| NZD/USD | +19.12 | Similar to AUD |
| CAD/USD | -3.28 | Near zero |
| NOK/USD | +8.46 | Slight positive |
| SEK/USD | -7.78 | Moderate negative |

### Cross-G10 highlights

| Pair | 5Y Basis (bp) |
|---|---|
| JPY/AUD | +56.70 |
| JPY/NZD | +59.85 |
| JPY/EUR | +33.47 |
| CHF/AUD | +35.27 |
| EUR/JPY | -33.40 |
| AUD/JPY | -54.32 |

---

## Structure Notes

- **BASE_LEG vs SPREAD_LEG**: Both legs available. BASE_LEG is the conventional quotation (basis on the non-USD leg). SPREAD_LEG shows the spread from the other side.
- **Symmetric pairs exist**: Both EUR/USD and USD/EUR are available with (approximately) opposite signs.
- **76,418 tags** breakdown estimate: 90 pairs × 20 spot tenors × 2 legs = 3,600 spot tags. Plus 90 × 19 forward starts × 20 tenors × 2 legs = ~68,400 forward tags. Total ≈ 72,000 (remaining tags likely from AUD_BBSW/NZD_BKBM variants).
- **All daily frequency**: 21–22 data points per 30-day window.

---

## Pipeline Considerations

### Spot-only (recommended first phase)

- **Core pairs**: 10 G10 currencies vs USD = 9 pairs (EUR/USD, GBP/USD, JPY/USD, CHF/USD, AUD/USD, NZD/USD, CAD/USD, NOK/USD, SEK/USD)
- **Plus key cross pairs**: EUR/GBP, EUR/CHF, EUR/JPY, AUD/NZD = 4 more
- **Tenors**: 1Y, 2Y, 3Y, 5Y, 7Y, 10Y, 15Y, 20Y, 30Y (9 tenors)
- **Tags per day**: 13 pairs × 9 tenors × 1 leg = 117 tags

### Full surface (phase 2)

- All 90 pairs × 20 spot tenors × BASE_LEG = 1,800 tags/day
- Forward surface adds ~34,200 tags — would need to be selective

### Data considerations

- Quote convention: positive basis means CCY1 funding is more expensive than CCY2
- JPY basis is by far the widest (reflects structural USD demand from Japanese investors)
- EUR/USD basis is the most liquid and traded cross-currency basis in the world
