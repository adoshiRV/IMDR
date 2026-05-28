# Country-Anchor Schema Restructure — Progress & Remaining Work

- **Date**: 2026-05-13
- **Full plan**: local Claude Code plan (`okay-lets-do-that-validated-puzzle.md`)
- **Related follow-up doc**: `docs/admin/development/fx_dim_currency_pair_string_cleanup.md`
- **Status (2026-05-14)**: Phases A, B, C, D, E, F, G, H **all complete in IMDR's current release scope**. Phase D code refactor (Steps 1–11) shipped. Phase H Block 5 sub-steps 5.1 (legacy ORM model deletion), 5.2 (migration 050: rename `calendar.dim_market*` + `dim_trading_day` → `*_old`), and 5.3 (migration 051: drop `calendar.cb_events.country_code` varchar(5) buffer column + rebuild 3 supporting indexes on `country_id` with original WHERE filters preserved) all applied and verified live. 947 unit tests passing, same 6 pre-existing FX/EIA failures, 0 new regressions throughout. **Only deferred work**: physical `DROP TABLE` of the 4 `*_old` legacy tables — migration number assigned at ship time, scheduled ≥1 release after stability is confirmed.
- **Sibling docs**:
  - [tech_debt_ruff_findings.md](tech_debt_ruff_findings.md) — 33 pre-existing ruff F-class findings (27 unused imports, 4 unused vars, 2 false positives) surfaced during the Step 4 cleanup scan. Not blockers for Phase D; chip away opportunistically.
  - [fx_dim_currency_pair_string_cleanup.md](fx_dim_currency_pair_string_cleanup.md) — deferred work: drop string `base_ccy`/`quote_ccy` from `fx.dim_currency_pair` once 20+ consumers migrate to FK ids.
  - [rates_hourly_classify_missing_equity_proxy.md](rates_hourly_classify_missing_equity_proxy.md) — surfaced during Step 6 review: `rates_citi_live_hourly._classify_missing` uses equity-exchange hours as a proxy for rates publish times. Misleading email status labels, no data-correctness impact. Out of Phase D scope (modeling error, not naming).
  - [per_script_calendar_intent.md](per_script_calendar_intent.md) — surfaced during Step 7 planning: project-wide `DEFAULT_CALENDAR_BY_COUNTRY["US"] = "GT"` is right for rates ingest (the dominant consumer) but the same default flows through equity/commodity scripts that should anchor on NYSE (`NY`). 6 mismatched call sites; small follow-on PR after Step 7 lands.
  - [legacy_calendar_tables_physical_drop.md](legacy_calendar_tables_physical_drop.md) — deferred Phase H closeout: physical `DROP TABLE` of `calendar.dim_market_old`, `dim_market_currency_old`, `dim_market_calendar_old`, `dim_trading_day_old` after ≥1 release of stability. Pre-flight checklist + DROP migration sketch ready for PM pickup.

This doc is a single-page summary of what was completed and what's left, for anyone picking up the work.

---

## Why this restructure

The pre-restructure `calendar.*` schema treated `dim_market` as the cross-domain anchor, but every market was 1:1 with a country and the split forced awkward fictions (e.g. `market_code='EU', country_code_iso='DE'`). Country codes were duplicated as free text with mismatched widths across `dim_market` (varchar 2), `dim_calendar` (varchar 3), and `cb_events` (varchar 5). FK chains were inconsistent — some hard, some soft.

The restructure replaces this with `dbo.dim_country` as the single anchor:

- One country owns N currencies (CN → CNY, CNH, CNO via `dim_currency.country_id`)
- One country owns N calendars (US → FD, GT, NY, YO via `calendar.dim_calendar.country_id`)
- Operational hours (timezone, weekend_days, trading_*) live on `dim_country`
- Pseudo-countries (`EU`, `WW`, `XX`) carry non-sovereign entities (Eurozone, Worldwide, metals)
- `country_code` ('US', 'UK', 'EU') is the canonical business key everywhere
- `iso_alpha3` ('USA', 'GBR') is held for ISO interop

---

## What was completed (Phases A–C + D-1..D-4)

| Phase | Deliverable | Verified state |
|---|---|---|
| **A** | `scripts/calendar/pre_restructure_cleanup.py` — audit + safe-fix script with `--ack <hash>` gate | 4 blockers resolved: trimmed `'RUB '` whitespace, seeded 6 missing ccys (BDT, DKK, EGP, KZT, LKR, NGN), demoted CN/CNH `is_primary`, deleted 3 empty calendars (ids 25/26/27) + their bridge rows |
| **B / 037** | `dbo.dim_country` created with `IDENTITY_INSERT` to preserve `dim_market.id` values | 52 rows: 50 markets (ids 1-50) + XX (51) + RU (52). 3 pseudo with `iso_alpha3 NULL`. Filtered unique index on `iso_alpha3`. CHECK constraint enforces pseudo invariant. |
| **B / 038** | Remediation migration — replaced bad UNIQUE constraint on `iso_alpha3` with filtered unique index | Resolved UNIQUE-on-NULL bug from 037's partial apply |
| **B / 039** | `dim_currency.country_id NOT NULL` FK + `variant` column added | All 47 rows linked. Variants set for CNH=offshore, CNO=bbg_onshore, IDO=onshore, MYO=onshore. Russia (`RU`) added to `dim_country` for RUB anchor (no `dim_market` counterpart — fine since no fact data refs it). |
| **B / 040** | `dim_calendar.country_id NOT NULL` FK; dropped `country_code_iso` | 27 rows linked. CHECK constraint `ck_calendar_dim_calendar_segment` blocked drop of `calendar_segment` — remediation in 041 |
| **B / 041** | Dropped CHECK constraint + `calendar_segment` column | `dim_calendar` now: id, calendar_code, calendar_name, country_id, description, is_active + audit |
| **C / 042** | BBG xlsx description backfill via generator script + 27 UPDATE statements | All 27 calendars now have BBG-canonical labels: FD='Federal Reserve Board', YO='NewYork', TE='Target', LS='LSE', etc. |
| **D-1** | `src/imdr/models/calendar.py` `DimCalendar` model updated to match DB | Drops `country_code_iso`, `calendar_segment`. Adds `country_id` FK. Verified via ORM smoke test + live query. |
| **D-2** | `src/imdr/models/country.py` NEW — `DimCountry` model | All 14 columns mapped, CHECK constraint declared, `__repr__` clean |
| **D-3** | `src/imdr/models/currency.py` updated with `country_id` FK + `variant` | Both new columns mapped; ORM JOIN through DimCountry → DimCurrency works for "all CN currencies" |
| **D-4** | ORM smoke test + live query verification | `sa.orm.configure_mappers()` clean; CN/CNY+CNH+CNO and YO→US queries return correct results |
| **E / 043** | `fx.dim_currency_pair`: drop `market_id`/`market_code` + 2 legacy FKs; add `base_currency_id` + `quote_currency_id` FKs to `dim_currency` | 26 rows, both new FKs NOT NULL; `FXCurrencyPair` model updated; EUR/USD live query through new chain verified |
| **E / 044** | `rates.dim_curve`: drop `market_id`/`market_code` + 2 duplicate FKs + index; add `country_id` NOT NULL FK + index | 60 rows; backfill via market_id + dim_currency.country_id + KRO→KR/THO→TH special-case; `RatesCurve` model updated |
| **E / 045** | `rates.dim_vol_surface`: drop `market_id`/`market_code` + 2 duplicate FKs + index; add `country_id` | 243 rows; `RatesVolSurface` model updated |
| **E / 046** | `rates.dim_skew_surface`: drop `market_id`/`market_code` + FK + index; add `country_id` | 12 rows (backfill via existing `currency_id`); `RatesSkewSurface` model updated |
| **E / 047** | `rates.dim_central_bank`: drop `market_id`/`market_code` + FK + index; add `country_id`. Full code cascade: `RatesDimCentralBank` model, `CentralBankCreate` schema (`market_code`→`country_code`), `BenchRateEntry` universe py, `rates.yml` (8 entries), `pipeline_bench.py` (kwarg + repository country_code→country_id resolution), `rates_bench_citi_live.py` dict key, `rates_bench_ingest.html` template | 8 rows; ORM smoke test passes; `test_rates_bench.py` updated for renamed schema field |
| **F / 048** | `equities.dim_index` fully subtractive: drop `market_code` + `FK_equities_dim_index_market` + `ix_equities_dim_index_market_code`; add `country_id NOT NULL` FK + index. `research.dim_report` partial: drop `market_code` + `fk_research_dim_report_market` + composite `(market_code, publish_date)` index, replace with `publish_date`-only index (already present, made idempotent), add `country_id NULL` FK + index. Full equity code cascade: `EquityDimIndex` model, `IndexCreate` schema (`market_code`→`country_code` required), `equity.yml` (29 entries), `equity.py` universe loader, `EquityIndexRepository` (`country_code`→`country_id` resolution at seed), `coverage.py` SQL (JOIN `dim_country`). Tests `test_equity_schema.py` + `test_equity_universe.py` updated | 23 equity rows + 119 research rows. Verified: country_id NOT NULL on dim_index, NULL on dim_report; all 14 equity country codes resolve cleanly |
| **G / 049** | `calendar.cb_events`: add `country_id NOT NULL` FK to `dim_country`, backfill via `country_code` join (all 31 distinct values resolve cleanly), drop `FK_cb_events_market`. `country_code` varchar(5) column KEPT (one-release deprecation buffer; load-bearing for 2 unique constraints + 1 search index + `cb_events.py` reads). `CBEvent` model updated with `country_id` field | 16,540 rows; 0 NULL `country_id`, 0 country_code/country_id mismatches. ORM mappers clean |
| **D / Step 1** | Weekend source switched from `markets.yml` to `dbo.dim_country.weekend_days`. Added `get_weekend_days(country_code)` helper in `holidays_db.py` with cached DB load + dedupe'd warning for unknown codes; `is_weekend()` now reads from DB. `markets.yml.weekend_days` annotated as deprecated (still present until Step 5). | 48 countries verified via live DB (4 ME use `4,5`, rest `5,6`; pseudo-countries fall back to `{5,6}`). 10 new unit tests (`TestGetWeekendDays`, `TestWeekendCacheRefresh`, `TestIsWeekendThroughDbCache`) all pass. |
| **D / Step 2** | Modern public API added alongside legacy. Signatures `is_holiday(country_code, calendar_code, d)`, `is_trading_day(...)`, `is_market_open(...)`, `last_trading_day(...)`, `next_trading_day(...)`, `trading_days_between(...)`, `last_business_day(country_code, calendar_code)`. Type-based dispatch on 2nd-arg type for 6 functions; `last_business_day` dispatches on whether `calendar_code` is provided. Legacy signatures still work, emit `DeprecationWarning`, removed in Step 11. Shared `_*_core` helpers reduce duplication. | All 94 existing tests pass via legacy paths (with expected warnings). 23 new tests added: `TestModernIsHoliday` (5), `TestModernIsTradingDay` (4), `TestModernLastTradingDay` (2), `TestModernNextTradingDay` (1), `TestModernTradingDaysBetween` (1), `TestModernLastBusinessDay` (2), `TestDeprecationWarnings` (5), `TestDispatchTypeErrors` (2). Modern path emits zero warnings (verified via `simplefilter("error")`). |
| **D / Step 3** | `dim_market_calendar` segment bridge removed from `holidays_db.py`. Module now purely a `(calendar_code, vendor) → holiday-set` lookup. Bridge code moved to `calendar.py` as private state (`_LEGACY_BRIDGE`, `_LEGACY_DEFAULT_BY_MARKET`, `_legacy_load_bridge()`, `_legacy_refresh_bridge()`, `_legacy_bridge_lookup()`) — used only by the legacy dispatch paths, deleted wholesale in Step 11. Public export `get_calendar_for_market` removed from `__init__.py` (smoke-verified). `_get_engine` shared cross-module with leaky-private comment. | 959 tests pass; same 6 pre-existing FX/EIA failures, 0 new regressions. `holidays_db.py` LoC reduced ~60 lines. New `TestLegacyBridgeLookup` (4 tests) covers the moved helper directly. Production runtime unchanged: legacy callers transparently use the new local bridge cache. |

---

## Verified state — 2026-05-13

```
dbo.dim_country       52 rows  (50 + XX + RU)         FKs in: dim_currency, dim_calendar, fx.dim_currency_pair (x2), rates.dim_curve, rates.dim_vol_surface, rates.dim_skew_surface, rates.dim_central_bank
dbo.dim_currency      47 rows  (all country_id NOT NULL; 4 variants set)
fx.dim_currency_pair  26 rows  (base/quote_currency_id NOT NULL; no more market_id/market_code)
rates.dim_curve       60 rows  (country_id NOT NULL; no more market_id/market_code)
rates.dim_vol_surface 243 rows (country_id NOT NULL; no more market_id/market_code)
rates.dim_skew_surface 12 rows (country_id NOT NULL; no more market_id/market_code)
rates.dim_central_bank 8 rows  (country_id NOT NULL; no more market_id/market_code)
calendar.dim_calendar 27 rows  (all country_id NOT NULL; all descriptions populated)
calendar.market_holidays  9,957 rows  (FK to dim_calendar + dim_vendor, no orphans)

FKs to calendar.dim_market remaining (3 — all INTERNAL to the legacy calendar schema):
  calendar.dim_market_currency  FK_market_currency_market
  calendar.dim_market_calendar  FK_calendar_dim_market_calendar_market
  calendar.dim_trading_day      FK_trading_day_market

No domain (fx, rates, equity, research, cb_events) references calendar.dim_market anymore.

LEGACY calendar.* tables (still present, scheduled for Phase H rename):
  calendar.dim_market           50 rows  (only intra-calendar FKs remain)
  calendar.dim_market_currency  43 rows
  calendar.dim_market_calendar  26 rows  (still queried by calendar.py's _LEGACY_BRIDGE; goes away in Step 11)
  calendar.dim_trading_day      420,050 rows  (no read consumers)
```

### Block 4 — Phase D code refactor (COMPLETE, 11/11 steps)

| Step | Status | Files touched | Test delta |
|---|---|---|---|
| 1 — weekend source switch | ✅ done | `holidays_db.py`, `calendar.py`, `markets.yml` (deprecated banner) | +10 tests |
| 2 — modern public API + dispatch | ✅ done | `calendar.py` (full rewrite), `tests/test_market_holidays.py` | +23 tests |
| 3 — remove bridge from holidays_db | ✅ done | `holidays_db.py` (~60 LoC removed), `calendar.py` (private bridge cache added), `__init__.py` (`get_calendar_for_market` unexported), `tests/test_market_holidays.py` (bridge tests migrated) | -3 +4 tests |
| 4 — cb_events.py rename + dim_currency lookup | ✅ done | `cb_events.py` (rewrite incl. fix for latent bug querying dropped `market_code` columns), 3 doc files. Also: B (`.upper()` normalization on country_code kwarg), A (new `tests/test_cb_events.py` with 9 tests), C (ruff scan → tech-debt doc filed) | +9 tests |
| 5 — markets.py → countries.py rename | ✅ done | `markets.py`→`countries.py`, `markets.yml`→`countries.yml` (top-level key `markets:`→`countries:`); `MarketConfig`→`CountryConfig`, `MarketsConfig`→`CountriesConfig`, `_MARKETS_PATH`→`_COUNTRIES_PATH`, `load_markets`→`load_countries`, `get_market`→`get_country`, `markets_for_currency`→`countries_for_currency`, `market_local_date`→`country_local_date` (last two added during self-review — pulling them forward avoided re-touching the same lines in Step 6 and the misleading "market" naming in a `countries.py` module). 9 importers updated: `__init__.py`, `calendar.py`, `holidays.py`, `run_cohorts.py`, `rates_citi_live_hourly.py`, `seed_dim_market.py`, `seed_trading_days.py`, `test_market_calendar.py`. Local var names `market_codes`/`mc`/`markets`/`primary_markets` renamed to country-flavored equivalents at each call site. Docs touched: `calendar_module.md`, `new_product_playbook.md`, `rates/schema.md`. No deprecation shims — all call sites migrated in lockstep. | tests renamed in lockstep; net 0 |
| 6 — countries_for_currency deterministic ordering | ✅ done | `countries.py` (`sorted(...)` on the comprehension + docstring noting `[0]` is alphabetical, not semantic primary). 0 production-call-site changes needed: live verification confirmed every currency in `countries.yml` maps to exactly 1 country today (43 ccys, 0 multi-country), so `[0]` returns the same value pre/post sort. Future-proofs the function for cases like a pegged currency listed under both home + peg country. New test `test_countries_for_currency_sorted` exercises the sort path with a synthetic 3-country fixture. Self-review pass: 4 callers audited (2 `[0]` callers in `run_cohorts.py` + `rates_citi_live_hourly.py`; 2 iterate-all callers in `holidays.py`, both sort-insensitive). Docstrings in `run_cohorts.py:14` + `rates_citi_live_hourly.py:_classify_missing` updated to flag that "primary" = alphabetic, not semantic. | +1 test |
| 7 — consumer migration to modern API | ✅ done | Added `DEFAULT_CALENDAR_BY_COUNTRY` + `default_calendar()` in `countries.py` (21 countries; US=GT, EU=TE, CN=I6, JP=JN, NZ=WL, PH=+P; rest use their single calendar). Migrated **~25 call sites across 17 files**: rates (8 scripts + `run_cohorts.py`), fx (3 scripts), equity (3 scripts), commodities (3 scripts), library (`healthchecks/quality.py`), tests (`test_calendar.py`). Legacy `segment="RATES"` lookup in `run_cohorts.target_for_region` replaced with `default_calendar(anchor)`. All non-rates scripts (equity, commodities) inherit `"GT"` provisionally; mismatch tracked in `per_script_calendar_intent.md` for follow-on. Deprecation warnings dropped 47 → 9 (remaining 9 are intentional in `test_market_holidays.py` testing the legacy fallback). | +0/-0 tests; warnings drop |
| 8 — HolidayHit field + templates rename | ✅ done | `HolidayHit.market_code` → `HolidayHit.country_code` (dataclass field + 4 kwarg sites in `holidays.py`). 22 dict-builders across 12 scripts updated (`"market_code": h.market_code` → `"country_code": h.country_code`). 8 Jinja templates: cell value `{{ h.market_code }}` → `{{ h.country_code }}` + column header `Market` → `Country` for consistency. 3 doc files migrated: `country_anchor_design.md`, `fx/calendar_integration.md`, `new_product_playbook.md`. Production code zero stale references; remaining `market_code` hits are intentional historical doc references or the legacy API surface (Step 11 territory). | tests unchanged; 0 new regressions |
| 9 — rename seed scripts; delete obsolete | ✅ done | **Created** `scripts/calendar/seed_dim_country.py` — idempotent INSERT-only seed from `countries.yml` into `dbo.dim_country` (52 existing rows untouched; designed for future country additions). INSERT-only by design: avoids clobbering DB-side weekend_days/timezone changes from the YAML's stale view. **Deleted** `seed_dim_market.py` (legacy `calendar.dim_market` writer), `seed_trading_days.py` (legacy `dim_trading_day` writer), `backfill_market_codes.py` (market_code columns already dropped by migrations 043–047). **Rewrote** `populate_asia_em_2026.py` Part 1: India holiday fixes now write to `calendar.market_holidays` keyed by `(calendar_id=RB, vendor_id=MANUAL, holiday_date)`. Added `_resolve_calendar_id` + `_resolve_vendor_id` helpers with explicit error messages. Dry-run verified against live DB. Stale `dim_trading_day` comment in `rates_citi_live_hourly.py:318` cleaned up in the same pass. | 0 new tests; 0 regressions |
| 10 — remove silent fallback (`_FALLBACK_ALLOWED=False`) | ✅ done | `calendar.py`: added `_FALLBACK_ALLOWED: bool = False` module flag + `CalendarDBError(LookupError)` exception class. `_holiday_check_core` now raises `CalendarDBError` when `is_holiday_db` returns `None` and the flag is off (the default). All 27 calendars in `dim_calendar` have ≥156 holiday rows in `market_holidays`, so no production call site lands on the new error path. Tests touched: deleted redundant `test_israel_sunday_is_trading` (Sunday weekend semantics covered by `TestIsWeekend::test_israel_sunday`); monkeypatched `_FALLBACK_ALLOWED=True` on the 2 `TestFallbackToLegacy` tests + the 1 `test_unknown_calendar_falls_through_to_legacy` modern-API test that deliberately exercise the legacy branch; added 2 new tests covering the hard-gate (one via modern API, one via legacy bridge resolving to a calendar with no rows). | +2/-1 tests; net +1 |
| 11 — remove deprecation wrappers; delete `_LEGACY_*` bridge code | ✅ done | **`calendar.py` rewritten as modern-only** (~370 lines → ~230 lines). Deleted: `_FALLBACK_ALLOWED` flag, `_legacy_is_holiday`, `_LEGACY_BRIDGE`/`_LEGACY_DEFAULT_BY_MARKET`/`_LEGACY_BRIDGE_LOCK` state, `_legacy_load_bridge`/`_legacy_refresh_bridge`/`_legacy_bridge_lookup`/`_legacy_resolve_and_check_holiday`/`_legacy_resolve_calendar` helpers, `_warn_legacy` + `_LEGACY_DEPRECATION_MSG`, all type-based dispatch branches in the 7 public API functions. Cleaned-up imports: removed `threading`, `warnings`, `sqlalchemy.text`, `sqlalchemy.exc.*`, `structlog`, `_get_engine`, `_get_country_holidays`, `_target2_holidays`. Public signatures simplified to single-shape `(country_code, calendar_code, …)`. `last_business_day` no longer has the `country_code="US"` default — both args are now required. **`CalendarDBError` re-exported** from `__init__.py`. **`test_market_holidays.py` rewritten**: deleted `TestLegacyBridgeLookup` (4), `TestSegmentAwareTradingDay` (5), `TestFallbackToLegacy` (3), `TestDeprecationWarnings` (5), `TestDispatchTypeErrors` (2), plus 5 legacy-shape tests inside the Modern-* classes. Stale comments in `test_calendar.py`, `holidays_db.py` refresh docstring cleaned. Calendar test suite (119 tests) passes with `-W error` (zero `DeprecationWarning`s emitted from any code path). | -24 tests (net); suite 970 → 946 |

**Total test delta across Block 4**: +43 - 24 + 19 new modern-API tests = **+38 net** since Block 4 start (suite at 946 passing, same 6 pre-existing FX/EIA failures, 0 new regressions). Modern API is the only path; the legacy surface is gone.

---

## Key decisions locked in

1. **UK country code**: keep `country_code='UK'`, `iso_alpha3='GBR'` (financial convention; matches existing data).
2. **Pseudo-country for metals/non-sovereign**: `XX`.
3. **Drop strategy**: rename old tables to `_old` in migration 050; physical DROP in a future release (number assigned at ship time). Migration 051 was reused for the cb_events.country_code column drop since the legacy-table physical drop was deferred.
4. **Pre-cleanup audit**: print report, require `--ack <hash>` flag before any DB writes.
5. **Pseudo-country operational hours**: `timezone`, `trading_*`, `weekend_days` all NULL for EU/WW/XX.
6. **No `is_primary` on `country_currency`**: callers pick the currency they want. "Canonical" recovered via `variant IS NULL` on `dim_currency`.
7. **No `country_currency` bridge at all**: the 1:N relationship is captured by `dim_currency.country_id`. Bridge table is redundant.
8. **Phase E rollout: additive-only**: migrations 043-047 ADD `country_id` alongside `market_id`. Subtractive cleanup after Phase D code refactor lands (originally penciled as migration 052; turned out empty for domain tables since Phase E went subtractive in-place — the only remaining cleanup was cb_events.country_code, landed as migration 051).
9. **Phase D must precede any code path that loads `DimCalendar`**: Done in D-1.
10. **Migration 043 reshape (2026-05-13)**: `fx.dim_currency_pair` migration is NOT additive-style "ADD country_id". A pair has 2 countries (one per leg). Instead, add `base_currency_id` + `quote_currency_id` FKs to `dim_currency`, drop the awkward `market_id`/`market_code` columns + their 2 duplicate FKs to `dim_market`. Keep `base_ccy`/`quote_ccy` string columns for now (20+ code consumers depend on them); deferred drop documented in `docs/admin/development/fx_dim_currency_pair_string_cleanup.md`.
11. **Resequencing (2026-05-13)**: Do remaining additive DB migrations (E/F/G) BEFORE Phase D code refactor. D-1..D-4 (model layer alignment) was the only blocking Phase D work; the rest of D is API-surface refactor that's safer done after DB is fully shaped.
12. **Subtractive rollout (2026-05-13, revised)**: Migrations 044–047 originally drafted as additive-only. After actual consumer-surface grep, the live read-path for `market_id`/`market_code` on `dim_curve` / `dim_vol_surface` / `dim_skew_surface` turned out to be empty (ORM only — no schemas, no pipelines, no scripts). For `dim_central_bank` the surface is bounded (5 files: model, schema, universe.py + yaml, pipeline_bench seeder, bench live script, bench template). All four rewritten as fully subtractive: same migration adds country_id + drops market_id/market_code. Cleanup migration 052 is no longer needed for the rates schema. The original "additive + cleanup in 052" pattern remains the right call for 048 (equity/research) and 049 (cb_events) where the consumer surface is larger.
13. **Block 4 self-review cadence**: after each Step lands, do a small review pass (existing-test parity + new-test coverage + smoke against live DB + grep for stale references) BEFORE moving to the next step. Surfaces issues like the `cb_events.events_for_currency` latent bug (caught at Step 1 review, fixed in Step 4) before they snowball. The review-then-fix loop has added ~30 min per step but avoided ~3 latent bugs so far.
14. **Tech-debt sidecar (2026-05-13)**: code-cleanup findings unrelated to the country-anchor restructure (ruff F-class: unused imports/vars/false-positive forward refs) are tracked in [tech_debt_ruff_findings.md](tech_debt_ruff_findings.md), NOT in this doc. Keeps the restructure timeline clean. Fix opportunistically when touching the affected files.

---

## Remaining execution sequence

Five linear blocks. Estimated total: 3-4 days of focused work.

### ✅ Block 1 — Phase E migrations (DB + code, fully subtractive). DONE 2026-05-13.

Applied 043–047 as fully subtractive (not additive — see decision 12 below). Each migration adds `country_id` + FK + index, drops the legacy market FKs + market_id index + market_id + market_code columns, in one transaction. ORM models updated in lockstep. For 047, full code cascade landed: model + schema + universe.py + universe.yml + pipeline_bench seeder + live script + template.

### Block 2 — Phase F migration (DB-only, additive). 1 hour.

6. Write + apply `048_equity_research_add_country.sql` — adds `country_id` to `equities.dim_index` (23 rows) and `research.dim_report` (119 rows; nullable `market_code`, so some rows may have NULL `country_id` post-backfill — decision needed: leave nullable or backfill via dim_currency from row context?). Update `src/imdr/models/equity.py` + `src/imdr/schemas/equity.py`. `research.dim_report` may need a new model file if none exists.

### Block 3 — Phase G migration (DB-only, additive). 30 min.

7. Write + apply `049_cb_events_add_country.sql` — adds `country_id` to `calendar.cb_events` (16,540 rows). Backfill via existing `FK_cb_events_market` join through `dim_market.id == dim_country.id`. ALTER NOT NULL. Add new FK. Keep `country_code` varchar(5) column for one release as deprecation buffer (drop in cleanup 052). Update `CBEvent` model in `src/imdr/models/calendar.py` to add `country_id`. Audit pre-check should whitelist EU=145, UK=29, WW=4 rows (all resolve via existing FK).

### Block 4 — Phase D code refactor (calendar library). 1–2 days.

Re-sequenced 2026-05-13 into 11 atomic increments. Original plan labels D-5..D-13 are preserved in the right column. Each step is independently landable and testable; the migration window allows old + new APIs to coexist (Steps 2–10) so consumer scripts can move in batches.

| # | Original | What changes | Files | Risk |
|---|---|---|---|---|
| **Step 1** | *(new)* — added from weekend-source discussion 2026-05-13 | `is_weekend(market_code, d)` reads `weekend_days` from `dbo.dim_country` (DB) instead of `markets.yml`. Same answer for 48/52 countries (4 ME use `4,5`; rest `5,6`); pseudo-countries fall back to `[5,6]`. Proves the YAML→DB cutover pattern on the smallest surface. | `holidays_db.py` (add cached helper), `calendar.py:32-35` (1-line body change) | ⚪ very low |
| **Step 2** | **D-5** | Public API: `is_holiday(country_code, calendar_code, d)`, `is_trading_day(...)`, `last_business_day(...)`, `next_trading_day(...)` — drop `segment`, rename `market_code` → `country_code`, take explicit `calendar_code`. Old signature kept as thin deprecation wrapper for one release. | `calendar.py` | 🟡 medium |
| **Step 3** | **D-6** | Rewrite `holidays_db.py`: remove `dim_market_calendar` bridge lookup. Caller passes `calendar_code` directly; resolve `calendar_id` from `(country_id, calendar_code)` and query `market_holidays`. | `holidays_db.py` | 🟡 medium |
| **Step 4** | **D-7** | `cb_events.py`: renamed `market_code` → `country_code` kwarg on `upcoming_cb_events`, `recent_cb_events`, `rate_decisions`. Rewrote `events_for_currency` on the country-anchor chain: resolve ccy → `dim_currency.country_id` → filter `cb_events.country_id`, find affected FX pairs via `base_currency_id|quote_currency_id`, find affected curves via `dim_curve.country_id`. **Also fixed a latent bug** (the old impl queried `fx.dim_currency_pair.market_code` and `rates.dim_curve.market_code` — both dropped in migrations 043/044). Added `.upper()` normalization on `country_code` kwarg. New `tests/test_cb_events.py` with 9 tests (5 events_for_currency + 4 normalization). Tech-debt scan filed as [tech_debt_ruff_findings.md](tech_debt_ruff_findings.md). | `cb_events.py`, 3 doc files, new test file | 🟢 mechanical |
| **Step 5** | **D-8** | Rename `markets.py` → `countries.py`, `markets.yml` → `countries.yml`. `MarketConfig` → `CountryConfig`, `load_markets()` → `load_countries()`, `get_market()` → `get_country()`. | ~10 importers | 🟢 mechanical |
| **Step 6** | **D-9** | `countries_for_currency()` gets sorted output for deterministic `[0]`. Callers using `[0]`: `run_cohorts.py:134`, `rates_citi_live_hourly.py:175`. (Doc previously listed `cb_events.py:112` as a third caller — Step 4's rewrite removed that dependence. Function renamed from `markets_for_currency` during Step 5 self-review.) | 1 fn + 2 callers | ⚪ low |
| **Step 7** | **D-10** | Refactor ~16 consumer scripts to new API. Batch order: rates → fx → equity → commodity. Mechanical rewrite: `is_holiday("US", date, segment="RATES")` → `is_holiday("US", "GT", date)`. | rates/fx/equity/commodity live + historical scripts | 🟡 medium per batch |
| **Step 8** | **D-11** | 8 Jinja templates: `{{ h.market_code }}` → `{{ h.country_code }}`. Update `HolidayHit` dataclass field name + the formatters that build the dict from it. Templates: `rates_ingest.html`, `fx_rate_ingest.html`, `rates_bench_ingest.html`, `cmdty_ingest.html`, `rates_vol_ingest.html`, `equity_ingest.html`, `fx_vol_ingest.html`, `fx_ingest.html`. | `holidays.py` (`HolidayHit`), 8 templates, ~5 formatters | 🟢 mechanical |
| **Step 9** | **D-12** | Rename `seed_dim_market.py` → `seed_dim_country.py` (reads `countries.yml`). Delete `seed_trading_days.py` and `backfill_market_codes.py`. Update `populate_asia_em_2026.py` to write `market_holidays` not `dim_trading_day`. | seed scripts | ⚪ low |
| **Step 10** | **D-13** | Remove silent fallback in `holidays_db.py` — `_FALLBACK_ALLOWED = False` flag (default false). Missing calendar raises `CalendarDBError`. Full smoke: ORM mappers, unit suite, dry-run daily pipelines. | `holidays_db.py`, `holidays.py` | 🟠 high — last gate |
| **Step 11** | follow-up | Remove deprecation wrappers from Step 2. Old `is_holiday(market_code, d, segment=…)` errors loudly. | `calendar.py` cleanup | ⚪ low |

**Why this order:**
- Step 1 first — lowest-blast-radius read-site switch, proves the DB read pattern, de-risks Step 3.
- Step 2 before Step 3 so the new public API is the entry point; Step 3 wires the body.
- Step 7 (consumer migration) only after Steps 2–6 so consumers always have both old + new signatures available.
- Step 10 (remove silent fallback) is deliberately near the end — once it lands, any coverage gap throws hard. Catching those during Step 7 is safer than tripping them mid-rename.
- Step 11 cleanup last so we never have a moment where consumers exist that call only the old signature.

### Block 5 — Cleanup + Phase H + tests + docs. 1 day.

17. Write + apply `migrations/052_drop_legacy_market_columns.sql` — drops `market_id`/`market_code` columns + their old FKs from the 4 rates dim tables + equity + research + cb_events. Includes `ALTER COLUMN market_code NULL` on `rates.dim_central_bank` before DROP. Updates 7 ORM model files in lockstep.
18. Write + apply `migrations/050_rename_legacy_tables.sql` — renames `calendar.dim_market`, `dim_market_currency`, `dim_market_calendar`, `dim_trading_day` to `_old` suffix. Pre-condition: 052 dropped all FKs pointing at these tables.
19. Update 10 test files — 8 modified + 2 new (`test_dim_country.py`, `test_country_currency.py`).
20. Update 15 doc files + 1 new (`docs/admin/country_anchor_design.md`).

---

## Migration numbering

| # | Status | Description |
|---|---|---|
| 037 | ✅ applied | create dbo.dim_country (partial — UNIQUE-on-NULL bug) |
| 038 | ✅ applied | repair dim_country seed (filtered UNIQUE + complete seed) |
| 039 | ✅ applied | alter dim_currency: add country_id + variant, FK + index |
| 040 | ✅ applied | alter dim_calendar: add country_id, drop country_code_iso |
| 041 | ✅ applied | drop ck_calendar_dim_calendar_segment + segment column |
| 042 | ✅ applied | backfill calendar descriptions from BBG xlsx (27 UPDATEs) |
| 043 | drafted | fx.dim_currency_pair: ADD base_currency_id + quote_currency_id; DROP market_id + market_code + 2 legacy FKs |
| 044 | pending | rates.dim_curve add country_id |
| 045 | pending | rates.dim_vol_surface add country_id |
| 046 | pending | rates.dim_skew_surface add country_id |
| 047 | pending | rates.dim_central_bank add country_id (market_code is NOT NULL) |
| 048 | pending | equities.dim_index + research.dim_report add country_id |
| 049 | pending | cb_events add country_id |
| 050 | pending | rename legacy tables to _old |
| 051 | pending apply | drop cb_events.country_code column + rebuild 3 indexes on country_id |
| (later release, TBD) | pending | DROP TABLE the _old tables |
| (n/a) | retired | originally penciled as 052 (drop residual market_id/market_code on domain tables) — turned into a no-op when migrations 043-047 went fully subtractive |

---

## Future blocks (not in this restructure)

- Future migration (number TBD) — physical DROP of the 4 `*_old` tables after ≥1 release of stability. **Scoped + checklisted in [`legacy_calendar_tables_physical_drop.md`](legacy_calendar_tables_physical_drop.md) for PM pickup.**
- Drop string `base_ccy`/`quote_ccy` from `fx.dim_currency_pair` — see `docs/admin/development/fx_dim_currency_pair_string_cleanup.md`
- KRO/THO curve dedup in `rates.dim_curve` (29K observations to merge)

---

## How to resume work

1. Open the full plan: local Claude Code plan `okay-lets-do-that-validated-puzzle.md` (has all design rationale, audit findings, and detailed migration templates).
2. Check `migrations/` for the highest applied number — pick up at the next.
3. Verify DB state with the queries in the "Verified state" section above.
4. Continue from Block 1 step 1 (apply migration 043).
