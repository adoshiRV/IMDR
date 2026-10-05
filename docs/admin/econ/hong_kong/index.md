# Hong Kong — Econ Documentation

Last updated: 2026-10-05

> **⚠ Data stale since 29 May 2026 — the HKMA lane was never scheduled.** There is no
> `scripts/econ/hk/` and no `hkma` entry in any orchestrator; every load has been a hand-run of
> the gitignored `playground/econ/hkma/fetch.py`. Treat every series below as a 2026-05-29
> snapshot until the backfill lands. For live HIBOR use
> [HKAB](https://www.hkab.org.hk/en/rates/hibor) (primary, 11:15 HKT); the Aggregate Balance has
> no free mirror. Detail and fetcher hardening: [`_playground/hkma.md`](_playground/hkma.md).

HK macroeconomic data. HKMA (Hong Kong Monetary Authority) covers the right half of the HK wiring map: FX (USD/HKD peg defence, intervention), rates (HIBOR family), banking (M-aggregates, FX reserves, asset quality, loans by sector). The left half (CPI, GDP, unemployment, trade) is C&SD-published and not yet onboarded — new vendor needed.

## Access paths

| Path | Auth | Speed | Coverage | Status |
|---|---|---|---|---|
| **HKMA public API** | None (no auth) | Fast | FX / rates / monetary / banking | **Onboarded, NOT scheduled** — manual runs only, stale since 29 May 2026 |
| **HKAB** (HIBOR fixings) | None | Fast | HIBOR O/N–12M, 11:15 HKT | **Fallback only** — not ingested, used when the HKMA API is down |
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
