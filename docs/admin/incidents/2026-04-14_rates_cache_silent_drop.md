# Incident: Rates Curve Silent Data Drop

**Date detected**: 2026-04-14
**Date started**: 2026-03-20 (EM curves), 2026-04-03 (G10 curves)
**Duration**: ~14 business days for G10, ~18 for EM
**Severity**: High — 20/39 rate curves silently stopped loading
**Status**: Resolved

---

## Summary

The daily `rates.historical` pipeline stopped ingesting data for 20 out of 39
rate curves after Easter 2026.  The pipeline reported `success` every night
with ~748 rows — no errors, no warnings.  The missing curves included
USD SOFR, USD FEDFUND, CAD CORRA, EUR EURIBOR, and all EM IBOR curves.

The data was always available on the Citi Velocity API.  A direct probe on
2026-04-14 confirmed all 20 curves had data through April 13.

## Root Cause

The `CurveQuoteCache` (`src/imdr/domains/rates/cache.py`) — a JSON file cache
at `data/cache/rates/empty_combos.json` — was the cause.

### How the cache works

The cache tracks (ccy, curve, quote) combinations that return 0 rows from the
Citi API.  On subsequent runs, `should_skip()` returns `True` if the cached
entry is less than `stale_days` old.  The original `stale_days` was **30**.

### What happened

1. **Good Friday / Easter (Apr 3-6)**: The Citi API returned 0 rows for
   `par` and `ssw` quotes on certain curves for the Easter holiday date.
2. **The cache recorded these as "empty"**: `USD|SOFR|par → 2026-04-03`
3. **For the next 30 days**: `should_skip()` returned `True`, silently
   preventing the pipeline from ever re-fetching these curves.
4. **The pipeline reported success**: Because it still loaded ~748 rows/day
   from the remaining 19 curves, the audit trail showed `status=success`.

### EM curves (earlier drop)

EM curves (IDR JIBOR, INR MIFOR, PHP PHIREF) were cached as empty even
earlier (Mar 20-22).  These likely hit a similar transient API issue or
a local market holiday.

### Why it was silent

- `should_skip()` had no logging — skipped combos were invisible
- The extractor logged `cache_skipped count=N` at INFO level with no detail
  about WHICH combos were skipped
- The pipeline reported total rows but not per-curve breakdowns

## Timeline

| Date | Event |
|------|-------|
| 2026-03-20 | IDR JIBOR `par` cached as empty |
| 2026-03-21 | INR MIFOR `par` cached as empty |
| 2026-03-22 | PHP PHIREF `par` cached as empty |
| 2026-04-03 | USD SOFR/FEDFUND/CAD CORRA `par`+`ssw` cached as empty (Easter) |
| 2026-04-04 | EUR EURIBOR/NOK NIBOR/SEK STIBOR/CNH HIBOR `par` cached as empty |
| 2026-04-07 | CNY SHIBOR/NDIRS `par` cached as empty |
| 2026-04-03 → 2026-04-13 | Pipeline runs nightly, reports success, rows drop from 1,188 → 748 |
| 2026-04-14 | Staleness monitor detects 20/39 stale curves |
| 2026-04-14 | API probe confirms all curves have data — cache is the culprit |
| 2026-04-14 | Cache fixed, corrupted entries cleared, code hardened |

## Impact

- **20 out of 39 rate curves** received no `par` data for 10-25 business days
- **Affected currencies**: USD, CAD, EUR, NOK, SEK, CNH, CNY, IDR, INR, PHP
- **Unaffected**: GBP, JPY, CHF, AUD, NZD, HKD, KRW, MYR, TWD, VND, SGD, THB
  (their `par` quotes were never in the cache)
- **No downstream failures**: Dashboard showed stale "as-of" dates but no crashes
- **Data recoverable**: Historical backfill can re-pull all missing dates

## Fix

### Code changes

1. **`src/imdr/domains/rates/cache.py`**:
   - `stale_days` reduced from 30 → **2 days** for active/reformed curves
   - `par` and `ssw` quotes for active curves are **never cached as empty**
   - Ceased curves (LIBOR, CDOR, EONIA, etc.) retain 30-day window
   - Warning log added when `should_skip()` blocks a fetch
   - Added `clear_curve()` and `clear_all()` methods for manual recovery

2. **`src/imdr/domains/rates/extractors.py`**:
   - Passes `curve_status` from universe to cache methods
   - Upgraded skip log from INFO → WARNING with combo list

3. **`data/cache/rates/empty_combos.json`**:
   - Removed 43 corrupted `par`/`ssw` entries for active curves
   - Retained entries for genuinely ceased curves

### Recovery

```bash
# Backfill all missing data
python -m scripts.rates.citi.rates_citi_historical
# MODE="range", START="2026-03-17", END="2026-04-13"
```

## Prevention

1. **Staleness monitor** (`scripts/imdr_staleness_check.py`): Runs after every
   daily batch.  Checks per-key freshness across all domains and sends email
   alerts.  Would have caught this on day 4 (3-day threshold).

2. **Cache hardening**: The 2-day stale window and `par` protection ensure a
   holiday weekend can never lock out a live curve again.

3. **Warning logging**: Skipped combos now appear in daily logs at WARNING
   level, making them visible during routine log review.

## Lessons Learned

1. **Silent failures are worse than loud failures.**  The pipeline reported
   `success` for 2 weeks while half its data was missing.  Per-curve
   monitoring is essential.

2. **Caches need expiry proportional to the risk.**  A 30-day TTL for a
   cache that can block primary data fetches is too long by an order of
   magnitude.

3. **Primary data (par rates) should be treated differently from derived
   data (butterflies, forwards).**  Caching `par` as empty should never
   happen for a live curve.

4. **Holiday effects are transient.**  The API returning empty for one day
   (Good Friday) does not mean the curve is dead — it just means the market
   was closed.
