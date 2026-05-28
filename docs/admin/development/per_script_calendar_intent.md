# Tech Debt — Per-script calendar intent mismatch

- **Date filed**: 2026-05-13
- **Status**: open (deferred — surfaced by Phase D Step 7 migration; out of Step 7 scope)
- **Triggered by**: choosing the project-wide `DEFAULT_CALENDAR_BY_COUNTRY["US"] = "GT"` during Step 7. Pre-Step-7, every `last_business_day("US")` call silently resolved to `NY` (NYSE) via the legacy bridge's `is_default=True` row. Post-Step-7, they all resolve to `GT` (SIFMA US Govt Bond).
- **Severity**: 🟡 silent calendar mismatch on a small number of dates per year (e.g. Veterans Day, MLK observed-day variants); **no data correctness impact** today — Citi serves data for whatever date we ask for. Affects which date the daily ingest *picks* as its target.

## TL;DR

We replaced one silent default (`NY`) with another (`GT`) for `last_business_day("US")`. That's right for rates ingest (which dominates the call sites), wrong for equity/commodity ingest that anchors on NYSE-style trading days. Filing a per-script audit + fix queue so we can replace each ambiguous default-lookup with an explicit, domain-correct `calendar_code` at the call site.

## What changed in Step 7

[`countries.py`](../../../src/imdr/market_calendar/countries.py) now defines:

```python
DEFAULT_CALENDAR_BY_COUNTRY = {
    "US": "GT",   # SIFMA US Govt Bond (NOT "NY" / NYSE)
    "JP": "JN", "NZ": "WL", "PH": "+P",
    "AU": "AU", "CA": "CA", "CH": "S5", "CN": "I6", "DE": "IB",
    "EU": "TE", "HK": "HK", "ID": "ID", "IN": "RB", "KR": "SK",
    "MY": "MA", "NO": "NO", "SE": "SW", "SG": "SI",
    "TH": "TH", "TW": "TA", "UK": "LS",
}
```

Pre-Step-7 (bridge defaults via `is_default=True`):

| Country | Pre-Step-7 default | Step 7 default |
|---|---|---|
| US | `NY` (NYSE) | **`GT` (SIFMA Govt Bond)** ⚠ semantic flip |
| EU | `TE` (TARGET2) | `TE` — same |
| JP | `JN` (TSE) | `JN` — same |
| NZ | `KD` (NZX) | **`WL` (RBNZ)** ⚠ semantic flip |
| PH | `PH` (PSE) | **`+P` (FX Settlement)** ⚠ semantic flip |
| (everyone else with 1 calendar) | their only calendar | same |

The 3 semantic flips (US, NZ, PH) were chosen deliberately to match the dominant consumer's intent (rates pipelines anchor on US/GT; FX settlement uses PH/+P; central-bank-event tooling uses NZ/WL). Other domains that happen to use the same default may now be on the wrong calendar.

## Affected call sites (audit needed)

Each row below is a `last_business_day("US")` call from Step 7's inventory. Today they all use `GT` via the project default. **The "Intended calendar" column is my best guess from script context; needs sign-off before changing.**

| Script | Domain | Today (after Step 7) | Likely intended | Mismatch? |
|---|---|---|---|---|
| `scripts/rates/citi/rates_citi_live.py:158` | Rates | `GT` | `GT` | ✅ correct |
| `scripts/rates/citi/rates_citi_historical.py:182` | Rates | `GT` | `GT` | ✅ correct |
| `scripts/rates/citi/rates_bench_citi_live.py:65` | Rates (bench) | `GT` | `GT` | ✅ correct |
| `scripts/rates/citi/rates_bench_citi_historical.py:124` | Rates (bench) | `GT` | `GT` | ✅ correct |
| `scripts/rates/citi/rates_vol_citi_live.py:78` | Rates (swaption vol) | `GT` | `GT` | ✅ correct |
| `scripts/rates/citi/rates_vol_citi_historical.py:177` | Rates (swaption vol) | `GT` | `GT` | ✅ correct |
| `scripts/fx/citi/fx_rate_citi_live.py:78` | FX (rates/forwards) | `GT` | `GT` (FX settles off US rates) | ✅ probably correct |
| `scripts/fx/citi/fx_vol_citi_live.py:81` | FX (vol) | `GT` | `GT` (FX vol same as rates) | ✅ probably correct |
| `scripts/fx/citi/fx_vol_citi_historical.py:145` | FX (vol) | `GT` | `GT` | ✅ probably correct |
| `scripts/equity/citi/equity_index_citi_live.py:52` | Equity indices | `GT` | **`NY`** | ⚠ MISMATCH |
| `scripts/equity/citi/equity_vix_citi_live.py:52` | Equity VIX | `GT` | **`NY`** | ⚠ MISMATCH |
| `scripts/equity/citi/equity_citi_historical.py:124` | Equity historical | `GT` | **`NY`** | ⚠ MISMATCH |
| `scripts/commodities/citi/cmdty_spot_citi_live.py:52` | Commodities spot | `GT` | **`NY`** (NYMEX/COMEX track NYSE) | ⚠ MISMATCH |
| `scripts/commodities/citi/cmdty_vol_citi_live.py:55` | Commodities vol | `GT` | **`NY`** | ⚠ MISMATCH |
| `scripts/commodities/citi/cmdty_citi_historical.py:132` | Commodities historical | `GT` | **`NY`** | ⚠ MISMATCH |

6 of the 15 audited call sites are arguably on the wrong calendar today.

## When the mismatch matters

Days where `GT` and `NY` diverge are the only dates affected. From SIFMA/NYSE 2026 calendars:

- **Veterans Day (Nov 11)** — NYSE open, SIFMA closed
- **Good Friday** — NYSE closed, SIFMA closed (no divergence)
- **Day before/after major holidays with early-close variants** — sometimes `GT` has a recommended early close, `NY` is full session
- Some Monday-after-weekend SIFMA recommendations

In practice this means equity/commodity ingest *might* skip a target day per year (target falls to the previous trading day instead of Veterans Day), with the day's data picked up the next run. Idempotent MERGE means no data is lost.

## Fix plan

Per-call-site rewrite. Two patterns:

**Pattern A — explicit calendar at call site:**

```python
# Before (after Step 7):
target = last_business_day("US")   # uses DEFAULT_CALENDAR_BY_COUNTRY["US"] = "GT"

# After:
target = last_business_day("US", "NY")   # explicit NYSE for equity ingest
```

**Pattern B — script-specific default constant:**

```python
# At top of equity script:
_CALENDAR_ANCHOR = ("US", "NY")

# Then:
target = last_business_day(*_CALENDAR_ANCHOR)
```

Pattern A is fine for one-off calls; Pattern B documents the script's calendar choice up top. Probably do A for the 6 sites (single call each).

## Why not fix in Step 7

- Step 7 is mechanical migration. Changing the calendar *and* the API in the same diff buries the semantic change.
- The 6 mismatched call sites are equity/commodity scripts that are working fine today (idempotent ingest, MERGE handles re-pulls). The mismatch shifts which date the script picks as "today's run," not data correctness.
- Cleaner story: Step 7 lands the API migration; this follow-up lands the per-script calendar correctness in one focused diff.

## Suggested sequencing

1. Phase D Step 7 lands the mechanical API migration with `DEFAULT_CALENDAR_BY_COUNTRY["US"] = "GT"` everywhere.
2. Follow-on PR (small, ~6-line diff): replace `last_business_day("US")` → `last_business_day("US", "NY")` in the 6 equity + commodity scripts.
3. After running production for ~1 week, verify no surprise gaps from the rates → bond calendar shift in fx/rates scripts.
4. Strip this doc once the follow-on lands.

## Cross-references

- The default map + helper: [src/imdr/market_calendar/countries.py](../../../src/imdr/market_calendar/countries.py) (`DEFAULT_CALENDAR_BY_COUNTRY`, `default_calendar()`)
- Phase D progress: [country_anchor_restructure_progress.md](country_anchor_restructure_progress.md)
- Related (different bug, same script): [rates_hourly_classify_missing_equity_proxy.md](rates_hourly_classify_missing_equity_proxy.md) — the `_classify_missing` equity-hours mismatch in `rates_citi_live_hourly.py`
