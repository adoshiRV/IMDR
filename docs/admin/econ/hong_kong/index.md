# Hong Kong — Econ Documentation

Last updated: 2026-06-05

HK macroeconomic data. HKMA (Hong Kong Monetary Authority) covers the right half of the HK wiring map: FX (USD/HKD peg defence, intervention), rates (HIBOR family), banking (M-aggregates, FX reserves, asset quality, loans by sector). The left half (CPI, GDP, unemployment, trade) is C&SD-published and not yet onboarded — new vendor needed.

## Access paths

| Path | Auth | Speed | Coverage | Status |
|---|---|---|---|---|
| **HKMA public API** | None (no auth) | Fast | FX / rates / monetary / banking | **Live** |
| **C&SD (Census & Statistics Dept)** | TBD | TBD | CPI / GDP / unemployment / trade | **NOT onboarded** |

## What's loaded

29 indicators × 192,083 obs in `econ.fact_indicator`:
- FX rates 1981→
- HIBOR fixings 1996→
- Money aggregates (M1/M2/M3)
- FX reserves
- Banking asset quality + loans by sector

## Pre-prod

- [`_playground/hkma.md`](_playground/hkma.md) — HKMA fetcher (10 endpoints, config-driven `_ENDPOINTS` dict pattern).

## Related

- [`../macro_economy_wiring_map.md`](../macro_economy_wiring_map.md) §7.10 — HK coverage (29 indicators, 7 of 16 cells ⚠).
- [[feedback-econ-vendor-config-driven]] — HKMA's `_ENDPOINTS` dict pattern is the reference for any multi-endpoint vendor (one dict entry per endpoint, single generic loop).
- C&SD wiring is the largest HK gap — would map cleanly to a new vendor following the FRED/HKMA shape.
