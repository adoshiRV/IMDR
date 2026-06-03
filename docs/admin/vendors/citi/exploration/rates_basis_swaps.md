# BASIS_SWAPS — Tenor Basis Swaps: Deep Exploration

- **Explored**: 2026-06-03
- **Cache**: [data/cache/rates/basis_swaps_probe.json](../../../../../data/cache/rates/basis_swaps_probe.json)
- **DO NOT re-run** — all results documented here

---

## Tag Format

```
RATES.BASIS_SWAPS.{BASIS}.{CCY}.{START}.{TENOR}.{QUOTE}
```

Example: `RATES.BASIS_SWAPS.3S6S_BASIS.AUD.SPOT.10Y.BASIS_SPREAD`

The quote (`BASIS_SPREAD`) is **LAST**, after the tenor. This is unlike
OIS / SWAP_LIBOR which put the quote BEFORE the tenor. The universe encodes
this via `instruments.basis_swaps.tag_format: "tenor_first"`.

---

## Bases under BASIS_SWAPS

| Base                  | Description                                         | Live data? |
|-----------------------|-----------------------------------------------------|------------|
| `3S6S_BASIS`          | 3M vs 6M IBOR tenor basis (this doc)                | Yes (EUR/AUD) |
| `3S1S_BASIS`          | 3M vs 1M IBOR tenor basis                           | Not probed end-to-end |
| `3S_OIS_BASIS`        | 3M IBOR vs OIS basis                                | Listed for USD/EUR/GBP/AUD (21 tags each) |
| `EUROSTR_EURIBOR_BASIS` | ESTR vs EURIBOR basis (EUR only)                  | Listed for EUR (25 tags) |
| `SOFR_FEDFUND_BASIS`  | SOFR vs Fed Funds basis (USD only)                  | Listed for USD (25 tags) |
| `SOFR_LIBOR_BASIS`    | SOFR vs USD LIBOR basis (USD only)                  | Listed for USD (25 tags); USD LIBOR ceased |

Currently wired in [imdr.universe.rates](../../../../../src/imdr/universe/rates.yml):
**3S6S_BASIS only**. Other bases can be added by appending curve entries
referencing the same `basis_swaps` instrument.

---

## 3S6S_BASIS — Currency Coverage

| CCY | Tags listed | Live data through | Tag count notes |
|-----|-------------|-------------------|-----------------|
| EUR | 20 | 2026-06-02 (active) | All 20 tenors (3M..30Y) |
| AUD | 19 | 2026-06-02 (active) | No 3M (BBSW market starts at 6M) |
| USD | 20 | 2025-02-21 (ceased) | History from 2015-01-02; ~2,564 daily pts |
| GBP | 20 | 2025-02-21 (ceased) | History from 2015-01-01; ~2,604 daily pts |
| JPY, CHF, NZD, CAD, NOK, SEK | 0 | n/a | No catalog entries |

USD / GBP stop publishing 2026 onward — consistent with the LIBOR
cessation cascade (USD LIBOR ceased 2023-06-30, synthetic GBP LIBOR
2024-03-28; Citi kept publishing the residual basis for a year, then
discontinued). Both wired as `status: ceased` so the historical
backfill script captures their full history but the daily live runner
skips them.

---

## Tenor Grid

Universal grid in [rates.yml](../../../../../src/imdr/universe/rates.yml)
under `maturities.basis_swaps` (20 tenors):

```
3M, 6M, 9M, 1Y, 18M, 2Y, 3Y, 4Y, 5Y, 6Y, 7Y, 8Y, 9Y,
10Y, 11Y, 12Y, 15Y, 20Y, 25Y, 30Y
```

AUD is missing 3M; all other tenors exist for all 4 wired ccys.

---

## Sample Values (2026-06-02)

| CCY | 1Y    | 5Y    | 10Y   | 20Y   |
|-----|-------|-------|-------|-------|
| EUR | ~16.8 | ~9.6  | ~6.9  | ~3.0  |
| AUD | ~31.2 | ~25.3 | ~19.0 | ~16.0 |

All values in basis points. Sign convention: positive means the 6M leg
pays more than the 3M leg (i.e. the 6M IBOR fixing trades richer).

---

## Schema Mapping

- **Internal quote**: `basis` (shared with BBG cross-currency basis;
  curve identity disambiguates)
- **Citi quote code**: `BASIS_SPREAD`
- **curve_type**: `basis`
- **instrument**: `basis_swaps`
- **Expected range**: `{ min: -300, max: 50 }` bps (existing `basis`
  entry in [rates.yml](../../../../../src/imdr/universe/rates.yml)
  `expected_ranges`)

Rows land in `[rates].[fact_observation]` keyed by
`(curve_id, vendor_id, ts, quote='basis', tenor, frequency_id)`.

---

## Scripts

- **Historical backfill**: [scripts/rates/citi/rates_basis_swaps_citi_historical.py](../../../../../scripts/rates/citi/rates_basis_swaps_citi_historical.py)
  — 2015-01 → 2026-06 across all 4 curves (incl. ceased USD/GBP for history)
- **Daily live**: [scripts/rates/citi/rates_basis_swaps_citi_live.py](../../../../../scripts/rates/citi/rates_basis_swaps_citi_live.py)
  — EUR + AUD only (ceased curves filtered out), 5-trading-day lookback
- **Daily orchestrator**: registered in [scripts/imdr_daily.py](../../../../../scripts/imdr_daily.py)
  with estimated_tags=40 (2 ccys × ~20 tenors)
