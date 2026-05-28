# `last_business_day` Call Sites — Review

- **Date**: 2026-05-13
- **Status**: REVIEW / TODO. All 16 production call sites use the **legacy single-arg form** `last_business_day("US")`. Phase D Step 2 added the modern signature `last_business_day(country_code, calendar_code)`; Step 7 is the consumer migration; Step 11 deletes the legacy branch.
- **Related**: [country_anchor_restructure_progress.md](country_anchor_restructure_progress.md), [`src/imdr/market_calendar/calendar.py`](../../../src/imdr/market_calendar/calendar.py)

---

## The function

```python
def _last_business_day_core(country_code: str, calendar_code: str) -> datetime:
    """Most recent completed trading day as a UTC-midnight datetime."""
```

[`calendar.py:202-227`](../../../src/imdr/market_calendar/calendar.py#L202-L227). Behaviour:

1. Resolve the country's local timezone via `get_country(country_code).timezone` (currently `countries.yml`; moves to `dbo.dim_country.timezone` later in Phase D).
2. If **today (local)** is a trading day for `calendar_code` AND `now_local >= market_close`, return **today** as `YYYY-MM-DD 00:00 UTC`.
3. Otherwise fall through to `_last_trading_day_core(country_code, calendar_code, before=today_local)` and return that date as `YYYY-MM-DD 00:00 UTC`.

Two consequences worth pinning down:

- The return is **midnight UTC of a local trading date** — not an instant. Every caller treats it as a *date proxy* and either uses `.date()` or overrides with `.replace(hour=..., minute=..., ...)`.
- The "today if closed" branch only fires when `country.trading_hours` is set. OTC/24h markets (FX) always return the **previous** trading day, even mid-session, because the close check is skipped.

---

## Call sites (16) — all legacy form

Every site currently calls `last_business_day("US")`, hitting the legacy `calendar_code is None` branch which:
1. Emits `DeprecationWarning` ("market_code, segment=..." → "country_code, calendar_code"), and
2. Resolves via `_legacy_resolve_calendar("US", "DEFAULT")` → bridge lookup → sentinel fallback if no row.

| Script | Line | Domain | Pattern |
|---|---|---|---|
| `scripts/fx/citi/fx_rate_citi_live.py` | 78 | FX | `target = last_business_day("US")` |
| `scripts/fx/citi/fx_vol_citi_live.py` | 81 | FX | `target = last_business_day("US")` |
| `scripts/fx/citi/fx_vol_citi_historical.py` | 145 | FX | `end = last_business_day("US").replace(hour=23, minute=59, ...)` (catchup mode) |
| `scripts/rates/citi/rates_citi_live.py` | 158 | Rates | `target = last_business_day("US")` (region == "all" only) |
| `scripts/rates/citi/rates_citi_historical.py` | 182 | Rates | catchup `end = last_business_day("US").replace(...)` |
| `scripts/rates/citi/rates_bench_citi_live.py` | 65 | Rates | `target = last_business_day("US")` |
| `scripts/rates/citi/rates_bench_citi_historical.py` | 124 | Rates | catchup `end = last_business_day("US").replace(...)` |
| `scripts/rates/citi/rates_vol_citi_live.py` | 78 | Rates | `target = last_business_day("US")` |
| `scripts/rates/citi/rates_vol_citi_historical.py` | 177 | Rates | catchup `end = last_business_day("US").replace(...)` |
| `scripts/equity/citi/equity_index_citi_live.py` | 52 | Equity | `target = last_business_day("US")` |
| `scripts/equity/citi/equity_vix_citi_live.py` | 52 | Equity | `target = last_business_day("US")` |
| `scripts/equity/citi/equity_citi_historical.py` | 124 | Equity | catchup `end = last_business_day("US").replace(...)` |
| `scripts/commodities/citi/cmdty_spot_citi_live.py` | 52 | Commodities | `target = last_business_day("US")` |
| `scripts/commodities/citi/cmdty_vol_citi_live.py` | 55 | Commodities | `target = last_business_day("US")` |
| `scripts/commodities/citi/cmdty_citi_historical.py` | 132 | Commodities | catchup `end = last_business_day("US").replace(...)` |

`rates_citi_live.py` also has a `target_for_region(region)` path for non-`"all"` regions — that helper should be reviewed in tandem since it likely shares the same legacy assumptions.

---

## Issues to address (Step 7)

### 1. Hardcoded `"US"` for non-US-anchored domains
- **FX**: OTC, no formal close. Using a US calendar means the function always returns "yesterday" (close check is skipped because `trading_hours` is None or not US-relevant). For FX live runs anchored on a regional cutoff, the regional path (`target_for_region`) is the correct mechanism — but historical/catchup still uses `last_business_day("US")`.
- **Equity**: Uses `"US"` even though the equity universe has 6 US + 6 Europe + 12 Asia-Pacific tickers (per `equity.yml`). NYSE/NASDAQ holidays would be the right calendar for the US slice; non-US tickers are silently anchored to US dates.
- **Commodities**: Brent/WTI/XAU/XAG/XPT are global. US is a reasonable default but it's implicit, not documented.
- **Rates**: `"US"` is correct for the global "what was the last business day" question, but the relevant calendar is **SIFMA / Treasury (`GT`)**, not the default NYSE-ish fallback. Bench/vol/swap pipelines are SIFMA-anchored.

### 2. No `calendar_code` — implicit DEFAULT segment
The legacy path resolves via `_legacy_resolve_calendar("US", "DEFAULT")` which hits the `dim_market_calendar` bridge. Live DB has the bridge populated, so it picks **whichever calendar has `is_default=1`** for US. That's brittle — it can change with a row update — and silently shifts every catchup window.

After Step 7, each call should pass an explicit `calendar_code`:

| Caller | Recommended (country, calendar) |
|---|---|
| `rates_*_live.py`, `rates_*_historical.py` | `("US", "GT")` — SIFMA US Govt Bond |
| `equity_*_live.py`, `equity_*_historical.py` (US slice) | `("US", "NY")` — NYSE |
| `fx_*_live.py`, `fx_*_historical.py` | `("US", "GT")` is the pragmatic default — FX has no native calendar; SIFMA is the canonical US "did markets settle" anchor |
| `cmdty_*_live.py`, `cmdty_*_historical.py` | `("US", "NY")` for screen-equity-style products; `("US", "GT")` for settlement-anchored |

### 3. Return type mismatch with usage
- `last_business_day()` returns `datetime` at 00:00 UTC.
- 7 of 16 sites immediately overwrite with `.replace(hour=23, minute=59, second=0, microsecond=0)` — they want the END of that day, not midnight.
- The other 9 use `target.date()` downstream or pass `target` to `_start_of_window(target, args.lookback)`.

Worth considering as part of Step 7: either
- Split into `last_business_date()` returning `date` (cleaner for the date-only consumers), and keep `last_business_day()` for the datetime form; or
- Document that the returned datetime is **a date proxy** and that callers must explicitly assign an hour/minute when they need a window bound.

### 4. Deprecation warning noise
Every scheduled run currently logs `DeprecationWarning` 1× per pipeline. `imdr_daily.py` triggers ~10 of these per day. They're harmless but pollute the audit log and obscure real warnings. Step 7 fix.

---

## Step 7 migration checklist

- [ ] Decide on `calendar_code` per domain (see table above) — confirm with downstream consumers.
- [ ] Migrate all 16 call sites to `last_business_day(country_code, calendar_code)`.
- [ ] Consider replacing the `.replace(hour=23, minute=59, ...)` pattern with a helper like `end_of_business_day(country_code, calendar_code) -> datetime` (local-close-of-trading expressed as UTC datetime). Avoids the "midnight UTC of trading date + adjust" two-step.
- [ ] Audit `target_for_region` in `rates_citi_live.py` for the same migration.
- [ ] Run the full test suite — expect `DeprecationWarning` count to drop to zero from modern paths.
- [ ] Add a `@pytest.mark.filterwarnings("error::DeprecationWarning")` smoke test on the daily entry-points to catch regression once Step 7 lands.
- [ ] Step 11 removes the legacy branch — verify no remaining single-arg calls before that lands.
