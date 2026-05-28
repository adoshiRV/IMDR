# Country Anchor Design

The design rationale for `dbo.dim_country` as the single anchor for all geographically-scoped data in IMDR. Companion doc: [country_anchor_restructure_progress.md](../development/country_anchor_restructure_progress.md) tracks the migration timeline.

## What changed

Before May 2026, every dim table that needed a "where on earth is this thing" reference FK'd to `calendar.dim_market(id)`. The market table was 50 rows, each 1:1 with a country, and the split was forcing awkward fictions (`market_code='EU'` with `country_code_iso='DE'`) and inconsistent column widths (varchar(2) on `dim_market`, varchar(3) on `dim_calendar`, varchar(5) on `cb_events`).

Migrations 037–049 reshape this with `dbo.dim_country` as the canonical anchor.

## The anchor

`dbo.dim_country` — 52 rows, `TINYINT` surrogate `id`. Columns:

| Column | Type | Purpose |
|---|---|---|
| `id` | `TINYINT` IDENTITY PK | Surrogate for all FKs |
| `country_code` | `VARCHAR(3) UNIQUE` | Canonical business key: `US`, `UK`, `EU`, `JP`, `WW`, `XX` |
| `iso_alpha3` | `CHAR(3) UNIQUE NULL` | `USA`, `GBR`, `JPN`; `NULL` for pseudo-countries |
| `display_name` | `VARCHAR(100)` | Human-readable |
| `is_pseudo` | `BIT` | `1` for `EU`, `WW`, `XX` |
| `timezone` | `VARCHAR(50) NULL` | IANA — `America/New_York`. `NULL` for pseudo |
| `weekend_days` | `VARCHAR(10) NULL` | Python weekday ints: `5,6`=Sat/Sun, `4,5`=Fri/Sat |
| `trading_open` / `trading_close` | `VARCHAR(5) NULL` | Local clock, `HH:MM` |
| `lunch_start` / `lunch_end` | `VARCHAR(5) NULL` | Local clock, `HH:MM` |

`CHECK (is_pseudo=0 AND iso_alpha3 IS NOT NULL OR is_pseudo=1 AND iso_alpha3 IS NULL)` enforces the pseudo-country invariant.

## Pseudo-countries

Some entities don't map cleanly to a single sovereign. These get pseudo-countries with `is_pseudo=1` and `iso_alpha3 NULL`:

| Code | Display name | Purpose |
|---|---|---|
| `EU` | Eurozone | TARGET2, EUR currency, ECB-driven instruments |
| `WW` | Worldwide | Global / multi-country calendars (rare; mostly CB events that span jurisdictions) |
| `XX` | Non-sovereign | Precious metals (`XAU`, `XAG`, `XPT`, `XPD`), commodity-quoted "currencies", future crypto |

## Country code vs ISO alpha-3

| | `country_code` | `iso_alpha3` |
|---|---|---|
| Width | `VARCHAR(3)` | `CHAR(3)` |
| Source | Financial convention (`UK`, not `GB`) | ISO 3166-1 |
| Used by | Every FK chain, every business join | External interop only |
| Pseudo countries | All have one (`EU`, `WW`, `XX`) | All `NULL` |

The split intentionally lets the canonical key be `country_code` (the one financial systems use — `UK`/`HK`/`KR`/etc) while still holding ISO alpha-3 for any caller that needs it.

## The 1:N relationships

### One country, N currencies

`dim_currency.country_id NOT NULL` FK → `dim_country(id)`. Plus an optional `variant` column:

| `country_code` | `dim_currency.code` | `variant` |
|---|---|---|
| `CN` | `CNY` | `NULL` (canonical onshore) |
| `CN` | `CNH` | `offshore` |
| `CN` | `CNO` | `bbg_onshore` (Bloomberg's onshore variant) |
| `MY` | `MYR` | `NULL` |
| `MY` | `MYO` | `onshore` |
| `ID` | `IDR` | `NULL` |
| `ID` | `IDO` | `onshore` |
| `XX` | `XAU` / `XAG` / `XPT` / `XPD` | `NULL` (metals) |
| `EU` | `EUR` | `NULL` |

"Canonical currency for a country" = `WHERE country_id = X AND variant IS NULL`. There is no bridge table — the FK on `dim_currency` is enough.

### One country, N calendars

`calendar.dim_calendar.country_id NOT NULL` FK → `dim_country(id)`. The US owns four:

| `calendar_code` | `description` | Purpose |
|---|---|---|
| `FD` | Federal Reserve Board | Central-bank schedule |
| `GT` | US Govt Bond Market (SIFMA) | Rates / Treasury settlement |
| `YO` | NY-region commercial banking | Legacy NY-Fed-region |
| `NY` | NYSE | Equity exchange |

Callers select the relevant calendar by `(country_code, calendar_code)` — no segment routing through a bridge table.

### One country pair, one currency pair

`fx.dim_currency_pair` is the only case where the country anchor is per-leg, not per-row:

| Column | FK |
|---|---|
| `base_currency_id` | `dim_currency(id)` |
| `quote_currency_id` | `dim_currency(id)` |

Each leg resolves to a country via its currency. The pair itself doesn't have a `country_id` (it has two — one per leg).

## Why country and not market

A "market" is a venue (NYSE, SIFMA, TARGET2). A "country" is the sovereign. The 50 rows of `dim_market` were 100% 1:1 with countries, but the table was *named* market, which:

1. Forced fake markets (`market_code='EU'` with country `DE`).
2. Pulled venue-specific columns (`timezone`, `trading_open`) onto a country-shaped table.
3. Made the segment bridge (`dim_market_calendar`) necessary to express "this country has multiple calendars" — solving the wrong direction. The right way: one country can OWN multiple calendars.

After 037–049, `dbo.dim_country` is the noun. The remaining `calendar.dim_market` rows are kept only because three internal `calendar.*` tables still FK there; those drop in Phase H once the calendar library is refactored.

## What still uses `market_code` (transient)

The schema is country-anchored as of migration 049. The library API in [src/imdr/market_calendar/](../../src/imdr/market_calendar/) was migrated to country-anchored signatures during Phase D Steps 2–8 (2026-05-13). Modern callers use `is_trading_day(country_code, calendar_code, d)`; legacy `(market_code, d, segment=…)` paths still live behind a `DeprecationWarning` and get deleted in Phase D Step 11.

`HolidayHit.market_code` was renamed to `HolidayHit.country_code` in Step 8 — all 8 ingest email templates + ~22 formatter dict-builders moved over in lockstep. The `cb_events.py` filter keyword was renamed in Step 4.

## Why the surrogate value is preserved

Migration 037 used `SET IDENTITY_INSERT dbo.dim_country ON` to inject 50 rows with the same `id` values they had in `calendar.dim_market`. This means `country_id = market_id` for every row that existed pre-restructure. The Phase E backfills (043–049) could therefore do `UPDATE … SET country_id = market_id` with zero risk of misalignment.

Two rows were added that have no `dim_market` counterpart: `XX` (id=51, metals) and `RU` (id=52, for `RUB` currency anchor). Neither appears in any fact table's `market_id` history, so they never collide.

## Reading the chain

```
country (1) ──┬── (N) currencies        dim_currency.country_id
              ├── (N) calendars         calendar.dim_calendar.country_id
              ├── (1) fact dim (rates)  rates.dim_curve.country_id, etc.
              ├── (1) fact dim (equity) equities.dim_index.country_id
              └── (1) event             calendar.cb_events.country_id
```

Every join from a fact row back to "what country is this" is one hop through a dim_*.country_id FK. No string normalization, no bridge tables, no segment routing.

## See also

- [country_anchor_restructure_progress.md](development/country_anchor_restructure_progress.md) — what was applied when, with verified row counts
- [schema_conventions.md](../reference/schema_conventions.md) §3.5 — the new-table FK convention
- [dim_frequency.md](../reference/dim_frequency.md) — companion cross-domain enum
- [calendar_module.md](calendar_module.md) — the calendar library
