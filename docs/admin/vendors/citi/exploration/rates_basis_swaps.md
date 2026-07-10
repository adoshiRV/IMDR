# BASIS_SWAPS — Deep Exploration

- **Initial exploration**: 2026-06-03 (3s6s only)
- **Other-bases probe**: 2026-06-05 (verdict matrix below)
- **Caches**:
  - [data/cache/rates/basis_swaps_probe.json](../../../../../data/cache/rates/basis_swaps_probe.json) — initial tag listings + 3s6s sample data
  - `data/cache/rates/basis_swaps_other_bases_probe.json` — per-base live-data verdict (gitignored; regenerate via the probe script above)
- **DO NOT re-run** — all results documented here

---

## Tag Format

```
RATES.BASIS_SWAPS.{BASE}.{CCY}.{START}.{TENOR}.{QUOTE}
```

Examples:
- `RATES.BASIS_SWAPS.3S6S_BASIS.AUD.SPOT.10Y.BASIS_SPREAD`
- `RATES.BASIS_SWAPS.SOFR_FEDFUND_BASIS.USD.SPOT.5Y.BASIS_SPREAD`

The quote (`BASIS_SPREAD`) is **LAST**, after the tenor. This is unlike
OIS / SWAP_LIBOR which put the quote BEFORE the tenor. The universe encodes
this via `instruments.basis_swaps.tag_format: "tenor_first"`.

---

## Bases under BASIS_SWAPS — verdict matrix (probed 2026-06-05)

A `live` status means tags listing AND last-30-day historical fetch both
returned data; `no_data` means the tag prefix resolves in the catalog but
the historical endpoint returns zero values (catalog ghosts from the
pre-LIBOR-cessation era).

| Base | CCY | Status | Tags | Latest | Wired? |
|---|---|---|---|---|---|
| `3S6S_BASIS` | EUR | live | 20 | 2026-06-04 | ✅ |
| `3S6S_BASIS` | AUD | live | 19 | 2026-06-04 | ✅ |
| `3S6S_BASIS` | USD | dead | 20 | 2025-02-21 (ceased) | ❌ dropped 2026-06-05 |
| `3S6S_BASIS` | GBP | dead | 20 | 2025-02-21 (ceased) | ❌ dropped 2026-06-05 |
| `SOFR_FEDFUND_BASIS` | USD | live | 25 | 2026-06-04 | ✅ added 2026-06-05 |
| `EUROSTR_EURIBOR_BASIS` | EUR | live | 25 | 2026-06-04 | ✅ added 2026-06-05 |
| `3S_OIS_BASIS` | AUD | live | 21 | 2026-06-04 | ✅ added 2026-06-05 |
| `3S_OIS_BASIS` | USD | no_data | 21 | n/a | ❌ |
| `3S_OIS_BASIS` | EUR | no_data | 21 | n/a | ❌ |
| `3S_OIS_BASIS` | GBP | no_data | 21 | n/a | ❌ |
| `3S1S_BASIS` | EUR | live | 20 | 2026-06-04 | ❌ tenor microstructure, low macro value |
| `3S1S_BASIS` | AUD | live | 20 | 2026-06-04 | ❌ tenor microstructure, low macro value |
| `3S1S_BASIS` | USD | no_data | 20 | n/a | ❌ |
| `3S1S_BASIS` | GBP | no_data | 20 | n/a | ❌ |
| `SOFR_LIBOR_BASIS` | USD | no_data | 25 | n/a | ❌ post-LIBOR dead |

**Key reframe**: the catalog still *lists* IBOR–OIS basis tags for USD /
EUR / GBP (21 each) and SOFR–LIBOR basis (25), but Citi no longer
publishes values for them — the "classic LIBOR–OIS funding stress gauge"
is **not available** through Citi for these currencies. AUD remains the
only ccy where 3M IBOR-vs-OIS basis is live, because BBSW didn't cease.

---

## Wired curves (5)

Two families: tenor basis (legacy) and funding stress (modern RFR-vs-IBOR
or RFR-vs-RFR).

### Tenor basis — `3S6S_BASIS`

| CCY | Tenors | Notes |
|-----|--------|-------|
| EUR | 20 (3M…30Y) | 3M vs 6M EURIBOR |
| AUD | 19 (no 3M) | 3M vs 6M BBSW; BBSW market starts at 6M so no 3M tenor |

### Funding stress — added 2026-06-05

| CCY | Curve | Description |
|-----|-------|-------------|
| USD | `SOFR_FEDFUND_BASIS` | SOFR vs Fed Funds — repo-vs-unsecured stress (Sep-2019 repo spike, Mar-2023 SVB-era squeeze). Modern US equivalent of LIBOR–OIS. 25 tags published. |
| EUR | `EUROSTR_EURIBOR_BASIS` | ESTR vs EURIBOR — modern EUR RFR-vs-IBOR funding gauge. 25 tags published. |
| AUD | `3S_OIS_BASIS` | 3M BBSW vs AONIA OIS — AUD funding stress. Lives because BBSW persists. 21 tags published. |

All 5 curves use the standard 20-tenor `basis_swaps` maturity grid —
this skips 5 extra tenors (13Y, 14Y, 16Y, 17Y, 19Y) that
`SOFR_FEDFUND_BASIS` and `EUROSTR_EURIBOR_BASIS` publish. Accepted on
purpose to keep the daily tag budget bounded.

---

## Dropped curves (2026-06-05)

Removed from [rates.yml](../../../../../src/imdr/universe/rates.yml)
entirely because Citi no longer returns data:

| CCY | Curve | Reason |
|-----|-------|--------|
| USD | `3S6S_BASIS` | Last Citi value 2025-02-21. USD LIBOR ceased 2023-06-30 |
| GBP | `3S6S_BASIS` | Last Citi value 2025-02-21. Synthetic GBP LIBOR ceased 2024-03-28 |

Their existing observations (2015-01 → 2025-02) remain in
`[rates].[fact_observation]` under the curve IDs that existed before the
drop; only future ingest stops. If the historical backfill is re-run,
those `dim_curve` rows must be re-seeded manually first.

---

## Tenor Grid

Universal grid in [rates.yml](../../../../../src/imdr/universe/rates.yml)
under `maturities.basis_swaps` (20 tenors):

```
3M, 6M, 9M, 1Y, 18M, 2Y, 3Y, 4Y, 5Y, 6Y, 7Y, 8Y, 9Y,
10Y, 11Y, 12Y, 15Y, 20Y, 25Y, 30Y
```

AUD `3S6S_BASIS` lacks 3M; `SOFR_FEDFUND_BASIS` and
`EUROSTR_EURIBOR_BASIS` have additional 13Y/14Y/16Y/17Y/19Y in the
catalog that this grid intentionally skips.

---

## Sample Values

### 3s6s tenor basis (2026-06-02)

| CCY | 1Y | 5Y | 10Y | 20Y |
|-----|----|----|-----|-----|
| EUR | ~16.8 | ~9.6 | ~6.9 | ~3.0 |
| AUD | ~31.2 | ~25.3 | ~19.0 | ~16.0 |

Sign convention: positive = 6M leg pays more than 3M leg (6M IBOR
fixing trades richer; widens in funding stress).

### Funding stress (2026-06-04, captured during first live run)

Run completed 2026-06-05 14:41 UTC. 594 rows loaded across 6 trading
days × 5 curves. See `[rates].[fact_observation]` joined to `dim_curve`
on `curve_id` for live values.

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

## Pipeline integration

- **Universe**: 5 active curves under `instruments.basis_swaps` in
  [rates.yml](../../../../../src/imdr/universe/rates.yml)
- **Live runner**: [scripts/rates/citi/rates_basis_swaps_citi_live.py](../../../../../scripts/rates/citi/rates_basis_swaps_citi_live.py)
  filters `providers.citi.instrument == 'basis_swaps' and status != 'ceased'`,
  fetches quote `basis` only, 5-trading-day lookback. Email subject:
  `[IMDR] Rates Basis Daily Ingest {OK|ERROR} | YYYY-MM-DD | N obs`.
- **Latest-day coverage (added 2026-07-09)**: `AUD 3S6S_BASIS` publishes at
  Citi ~1 business day later than its sibling basis curves, so on the day-of
  run its newest trading day is often absent — it then backfills on the next
  run via the 5-day window. The runner's window-level coverage check
  (`missing` = zero rows across the whole window) is blind to this partial
  gap, so it also emits a **behind** list (`_behind_curves()`): active curves
  that returned rows but are missing the target trading day, measured in
  business days and skipping holiday markets. When non-empty the subject
  gains a `| N behind` suffix and the body shows a **CURVES BEHIND** section —
  so a one-day lag no longer reads as a clean chit. The signal is additive:
  the shared `RatesIngestFormatter`/`rates_ingest.html` only render it when a
  runner populates `behind_curves`, so bench/historical emails are unchanged.
  The cross-run safety net is the staleness monitor's `rates.historical` spec
  (business-day mode, 2-day threshold — see `docs/admin/ops/staleness_monitor.md`).
- **Historical backfill**: [scripts/rates/citi/rates_basis_swaps_citi_historical.py](../../../../../scripts/rates/citi/rates_basis_swaps_citi_historical.py).
  Built for the original 4-curve 3s6s set — does not yet cover the
  3 funding-stress curves added 2026-06-05; historical backfill of
  those is pending.
- **Orchestrator**: registered in [scripts/imdr_daily.py](../../../../../scripts/imdr_daily.py)
  at `estimated_tags=100` (5 curves × 20-tenor standard grid).

---

## Probe script

Reusable: [playground/rates/probe_basis_swaps_other_bases.py](../../../../../playground/rates/probe_basis_swaps_other_bases.py)

Hits actual historical-data endpoint for each (base, ccy) combo with
non-zero tag count, classifies as `live` / `stale` / `no_data` based on
the latest observation date returned, writes a fresh verdict cache. Use
this if Citi adds a new base under BASIS_SWAPS or to re-verify dead
combos.
