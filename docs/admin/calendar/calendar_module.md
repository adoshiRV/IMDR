# Global Trading Calendar Module

> ℹ **Status (2026-05-13).** Schema-side country-anchor restructure complete (migrations 037–049). **Phase D code refactor complete — 11 of 11 steps done.** Only Block 5 (Phase H: rename legacy `calendar.dim_market*` tables to `_old`, then drop in a following release) remains.
>
> - **Step 1**: `is_weekend()` now reads `dbo.dim_country.weekend_days`; `countries.yml.weekend_days` is deprecated.
> - **Step 2**: A modern `is_holiday(country_code, calendar_code, d)` / `last_business_day(country_code, calendar_code)` API surface exists alongside the legacy `(market_code, …, segment=…)` signatures. Legacy calls still work and emit `DeprecationWarning`. New code should use the modern signatures.
> - **Step 3**: The `calendar.dim_market_calendar` segment bridge is no longer used by `holidays_db.py`. Modern callers query `market_holidays` directly by `calendar_code`. The bridge cache survives privately in `calendar.py` to support legacy callers until Step 11.
> - **Step 4**: `cb_events.py` migrated to the country-anchor chain. `events_for_currency` now resolves ccy → `dim_currency.country_id` → `cb_events.country_id` (the old impl queried since-dropped `market_code` columns and was silently broken).
> - **Step 5**: `markets.py` / `markets.yml` renamed to `countries.py` / `countries.yml`. Public symbols `get_market` → `get_country`, `MarketConfig` → `CountryConfig`, `load_markets` → `load_countries`, `markets_for_currency` → `countries_for_currency`, `market_local_date` → `country_local_date`. Top-level YAML key is now `countries:`. No deprecation shims — all call sites migrated in lockstep.
> - **Step 6**: `countries_for_currency()` returns sorted output for deterministic `[0]` access. All 43 ccys in `countries.yml` map to exactly 1 country today, so no behavior change — sort is preventive against future multi-country ccys (e.g. peg arrangements).
> - **Step 7**: ~25 consumer call sites migrated to the modern API (`is_holiday(country, calendar_code, d)`, `last_business_day(country, calendar_code)`, etc.). New `DEFAULT_CALENDAR_BY_COUNTRY` map in `countries.py` replaces the bridge's silent default resolution; `US` defaults to `GT` (SIFMA rates), not `NY` (NYSE). Equity/commodity scripts inherit `GT` provisionally — tracked in `docs/admin/development/per_script_calendar_intent.md`.
> - **Step 8**: `HolidayHit.market_code` renamed to `HolidayHit.country_code`. 8 ingest email templates (`rates_ingest.html`, `fx_rate_ingest.html`, etc.) + 22 formatter dict-builders + 3 docs updated in lockstep. Templates' "Market" column header also renamed to "Country" for consistency.
> - **Step 9**: Seed scripts cleaned up. New `seed_dim_country.py` (idempotent INSERT-only into `dbo.dim_country`). Deleted legacy `seed_dim_market.py`, `seed_trading_days.py`, `backfill_market_codes.py`. `populate_asia_em_2026.py` now writes India holiday overrides to `calendar.market_holidays` under vendor=MANUAL instead of the deprecated `dim_trading_day` table.
> - **Step 10**: Silent fallback to the Python `holidays` library is now OFF by default. Unknown `calendar_code` → raises `CalendarDBError` instead of quietly using country-level holidays. All 27 DB-resident calendars have ≥156 rows in `market_holidays`, so no production call site trips the gate. The `_FALLBACK_ALLOWED` flag lives for tests that explicitly exercise the legacy branch; both flag + branch get deleted in Step 11.
> - **Step 11**: Legacy API surface deleted. `calendar.py` rewritten as modern-only (~370 → ~230 lines): no `_FALLBACK_ALLOWED`, no `_legacy_is_holiday`, no `_LEGACY_BRIDGE` state, no deprecation wrappers. Every public function has exactly one signature shape: `(country_code, calendar_code, …)`. `last_business_day` now requires both args explicitly. `CalendarDBError` re-exported from `imdr.market_calendar`. Calendar test suite (119 tests) runs cleanly with `pytest -W error`.
>
> Calls below using `segment=` and the bridge work as documented but will emit `DeprecationWarning`. The whole legacy surface is removed in Phase D Step 11. See [country_anchor_design.md](country_anchor_design.md) and [country_anchor_restructure_progress.md](../development/country_anchor_restructure_progress.md).
>
> **Recommended call form** (modern, no warnings):
> ```python
> from datetime import date
> from imdr.market_calendar import is_holiday, last_business_day
> is_holiday("US", "GT", date(2026, 11, 11))   # SIFMA US Govt Bond → True (Veterans Day)
> is_holiday("US", "NY", date(2026, 11, 11))   # NYSE                → False
> last_business_day("US", "GT")
> ```

## Overview

The `src/imdr/market_calendar/` module provides a unified, config-driven trading calendar for all IMDR domains (FX, Rates, Equity, Commodities). It combines:

- **Curated holiday calendars** in `calendar.market_holidays`, multi-vendor (BBG, MANUAL, EXCHANGE_CALENDARS, HOLIDAYS_LIB), with priority order `MANUAL > BBG > EXCHANGE_CALENDARS > HOLIDAYS_LIB`.
- **Multiple calendars per country** — e.g. US has FD (Fed CB), GT (SIFMA / Govt Bond), YO (NY-banking), NY (NYSE) — selected per call by passing `calendar_code` explicitly.
- **Weekend awareness** per country (supports non-standard weekends: Israel Fri/Sat, Saudi Fri/Sat, Egypt Fri/Sat, Bangladesh Fri/Sat); read from `dbo.dim_country.weekend_days`.
- **Trading hours** per exchange (open/close in local time, lunch breaks for Asian markets); stored in `countries.yml`.
- **ISDA financial center** settlement calendars.
- **IMM dates** (monthly + quarterly, algorithmically computed).
- **Central bank events** from Bloomberg Excel exports (stored in DB).
- **Custom events** (early closes, data blackouts) from YAML.

### Calendar selection (Post-Phase-D)

Pass `(country_code, calendar_code)` directly — no `segment` parameter, no bridge lookup:

```python
from imdr.market_calendar import is_trading_day, last_business_day
is_trading_day("US", "GT", date(2026, 11, 11))   # False — SIFMA/Govt Bond closed (Veterans Day)
is_trading_day("US", "NY", date(2026, 11, 11))   # True  — NYSE open
last_business_day("US", "GT")                    # Most recent US govt-bond trading day
```

`DEFAULT_CALENDAR_BY_COUNTRY` in `countries.py` maps each country to its default calendar (e.g. `US → GT`). Callers that don't need the distinction can use the default via `default_calendar("US")`.

### Resolution order

1. `(calendar_code)` is passed directly by the caller (no bridge lookup).
2. Query `calendar.market_holidays` for that calendar, vendor-priority filtered: `MANUAL > BBG > EXCHANGE_CALENDARS > HOLIDAYS_LIB`.
3. If no vendor has rows for the calendar, raise `CalendarDBError` (no silent fallback since Step 10).

`MANUAL` sits at the top of the priority order so any manually-added override row wins without changing `trusted_vendor_id`.

## Calendars

After migrations 031 + 034, `calendar.dim_calendar` has **30 rows**. Codes match the BBG master spreadsheet.

| Code | Name | Country | Segment | Loader |
|------|------|---------|---------|--------|
| FD | Federal Reserve Board | USA | CENTRAL_BANK | BBG xlsx |
| GT | US Govt Bond Market (SIFMA) | USA | GOVT_BOND | BBG xlsx |
| YO | NewYork — NY-region banking | USA | EQUITY | BBG xlsx |
| NY | NYSE | USA | EQUITY | BBG xlsx (added in m034) |

> **YO vs NY are deliberately distinct.** `YO` is a NY-region commercial banking calendar (closed Veterans Day & Columbus Day, **open** Good Friday, no NYSE half-day closes). `NY` is the NYSE proper (closed Good Friday, July 3 / Christmas Eve early closes). They diverge on ~45 dates over the BBG window. The `US/EQUITY` bridge points at `NY` (post-m035); equity pipelines therefore correctly observe NYSE rules. `YO` stays registered for callers that need NY-region banking holidays directly.
| TE | TARGET2 | EUR | SETTLEMENT | BBG xlsx |
| AU | Australia (ASX) | AUS | EQUITY | BBG xlsx |
| JN | Japan (TSE) | JPN | EQUITY | BBG xlsx |
| OK | Osaka Exchange | JPN | EQUITY_DERIV | BBG xlsx (added in m034) |
| WL | Wellington (RBNZ) | NZL | CENTRAL_BANK | BBG xlsx |
| KD | Auckland (NZX) | NZL | EQUITY | BBG xlsx |
| SK | South Korea (KRX) | KOR | EQUITY | BBG xlsx |
| RB | India (RBI) | IND | CENTRAL_BANK | BBG xlsx |
| I6 | China Interbank | CHN | INTERBANK | BBG xlsx |
| TH | Thailand (SET) | THA | EQUITY | BBG xlsx |
| MA | Malaysia (Bursa) | MYS | EQUITY | BBG xlsx |
| HK | Hong Kong (HKEX) | HKG | EQUITY | BBG xlsx |
| SI | Singapore (SGX) | SGP | EQUITY | BBG xlsx |
| TA | Taiwan (TWSE) | TWN | EQUITY | BBG xlsx |
| ID | Indonesia (IDX) | IDN | EQUITY | BBG xlsx |
| PH | Philippines (PSE) | PHL | EQUITY | BBG xlsx |
| +P | Philippines FX Settlement | PHL | SETTLEMENT | BBG xlsx (added in m034) |
| IB | Xetra (DAX) | DEU | EQUITY | BBG xlsx (renamed from XE in m034) |
| LS | LSE (FTSE) | GBR | EQUITY | BBG xlsx (renamed from LN in m034) |
| S5 | SIX Swiss Exchange (SMI) | CHE | EQUITY | BBG xlsx (renamed from SX in m034) |
| CA | Canada (TSX) | CAN | EQUITY | BBG xlsx (renamed from TX in m034) |
| SW | Nasdaq Stockholm (OMX) | SWE | EQUITY | BBG xlsx (renamed from OM in m034) |
| NO | Oslo Børs | NOR | EQUITY | BBG xlsx (renamed from OB in m034) |
| CN | SSE/SZSE (CSI 300) | CHN | EQUITY | exchange_calendars (future) |
| NS | NSE/BSE (Nifty 50) | IND | EQUITY | exchange_calendars (future) |
| CB | CBOE (US options) | USA | EQUITY_DERIV | deferred |

> **YO vs NY are deliberately distinct** (see table note above). `YO` is a NY-region commercial banking calendar; `NY` is the NYSE proper. The `US/EQUITY` default points at `NY` (post-m035). Use `YO` only if you specifically need NY-region banking holidays.

## Loading the BBG master spreadsheet

The 2026-05 refresh shipped under a renamed file (`calendar_pasted.xlsx`) with a one-row layout shift and 9 additional calendars; use the v2 loader, which auto-detects the codes / data rows by scanning for the `DATES` header:

```bash
python -m scripts.calendar.load_calendar_pasted_xlsx \
    --xlsx "Z:\Business\Personnel\Arjun\IMDR_MANUAL_UPLOADS\May 2026\calendar_pasted.xlsx"
```

Idempotent — re-running with the same file is a no-op. Use `--load-batch` to tag snapshots for later rollback by batch:

```bash
python -m scripts.calendar.load_calendar_pasted_xlsx \
    --xlsx "..." --load-batch bbg_xlsx_2026_05
```

The original `load_market_holidays_xlsx.py` is preserved for the older `Calendar pasted.xlsx` template (codes on row 9, sheet `master_config`) — only relevant if you need to re-load a pre-2026-05 snapshot.

## Reconciliation

When multiple vendors have rows for the same calendar, surface dates where they disagree:

```python
from imdr.market_calendar import vendor_disagreements
from datetime import date

rows = vendor_disagreements("LS", date(2026, 1, 1), date(2026, 12, 31))
for r in rows:
    print(r.holiday_date, "holiday:", r.vendors_say_holiday, "trading:", r.vendors_say_trading)
```

Currently only `BBG` has rows in `calendar.market_holidays` so this returns empty. The schema supports adding `MANUAL` overrides or a future direct-BBG-API loader on top without code changes.


## Countries Reference

~40 countries defined in `src/imdr/market_calendar/countries.yml`:

| Market | Timezone | Currencies | Weekend | Trading Hours | ISDA Centers |
|--------|----------|------------|---------|---------------|-------------|
| US | America/New_York | USD | Sat-Sun | 09:30-16:00 | NYSE, XNYS |
| UK | Europe/London | GBP | Sat-Sun | 08:00-16:30 | IFEU |
| EU | Europe/Berlin | EUR | Sat-Sun | 09:00-17:30 | ECB, TAR, XECB |
| JP | Asia/Tokyo | JPY | Sat-Sun | 09:00-15:30 (lunch 11:30-12:30) | - |
| CH | Europe/Zurich | CHF | Sat-Sun | 09:00-17:30 | - |
| AU | Australia/Sydney | AUD | Sat-Sun | 10:00-16:00 | - |
| NZ | Pacific/Auckland | NZD | Sat-Sun | 10:00-16:45 | - |
| CA | America/Toronto | CAD | Sat-Sun | 09:30-16:00 | - |
| NO | Europe/Oslo | NOK | Sat-Sun | 09:00-16:20 | - |
| SE | Europe/Stockholm | SEK | Sat-Sun | 09:00-17:30 | - |
| DK | Europe/Copenhagen | DKK | Sat-Sun | 09:00-17:00 | - |
| CN | Asia/Shanghai | CNY, CNH | Sat-Sun | 09:30-15:00 (lunch 11:30-13:00) | - |
| HK | Asia/Hong_Kong | HKD | Sat-Sun | 09:30-16:00 (lunch 12:00-13:00) | - |
| KR | Asia/Seoul | KRW | Sat-Sun | 09:00-15:30 | - |
| IN | Asia/Kolkata | INR | Sat-Sun | 09:15-15:30 | BSE, NSE, XBOM, XNSE |
| SG | Asia/Singapore | SGD | Sat-Sun | 09:00-17:00 | - |
| TW | Asia/Taipei | TWD | Sat-Sun | 09:00-13:30 | - |
| TH | Asia/Bangkok | THB | Sat-Sun | 10:00-16:30 (lunch 12:30-14:30) | - |
| ID | Asia/Jakarta | IDR | Sat-Sun | 09:00-16:15 (lunch 11:30-13:30) | - |
| MY | Asia/Kuala_Lumpur | MYR | Sat-Sun | 09:00-17:00 (lunch 12:30-14:30) | - |
| PH | Asia/Manila | PHP | Sat-Sun | 09:30-15:30 | - |
| VN | Asia/Ho_Chi_Minh | VND | Sat-Sun | 09:00-15:00 (lunch 11:30-13:00) | - |
| BR | America/Sao_Paulo | BRL | Sat-Sun | 10:00-17:00 | B3, BVMF |
| MX | America/Mexico_City | MXN | Sat-Sun | 08:30-15:00 | - |
| ZA | Africa/Johannesburg | ZAR | Sat-Sun | 09:00-17:00 | - |
| TR | Europe/Istanbul | TRY | Sat-Sun | 10:00-18:00 | - |
| PL | Europe/Warsaw | PLN | Sat-Sun | 09:00-17:00 | - |
| CZ | Europe/Prague | CZK | Sat-Sun | 09:00-16:30 | - |
| HU | Europe/Budapest | HUF | Sat-Sun | 09:00-17:00 | - |
| RO | Europe/Bucharest | RON | Sat-Sun | 10:00-17:45 | - |
| IL | Asia/Jerusalem | ILS | **Fri-Sat** | 09:59-17:15 | - |
| SA | Asia/Riyadh | SAR | **Fri-Sat** | 10:00-15:00 | - |
| AE | Asia/Dubai | AED | Sat-Sun | 10:00-14:00 | - |
| EG | Africa/Cairo | EGP | **Fri-Sat** | 10:00-14:30 | - |
| NG | Africa/Lagos | NGN | Sat-Sun | 09:30-14:30 | - |
| AR | America/Argentina/Buenos_Aires | ARS | Sat-Sun | 11:00-17:00 | - |
| CL | America/Santiago | CLP | Sat-Sun | 09:30-16:00 | - |
| CO | America/Bogota | COP | Sat-Sun | 09:30-16:00 | - |
| PE | America/Lima | PEN | Sat-Sun | 09:00-15:30 | - |
| KZ | Asia/Almaty | KZT | Sat-Sun | 11:00-17:00 | - |
| BD | Asia/Dhaka | BDT | **Fri-Sat** | 10:00-14:30 | - |
| LK | Asia/Colombo | LKR | Sat-Sun | 09:30-14:30 | - |

## API Reference

All functions importable from `imdr.market_calendar`:

### Core Calendar (`calendar.py`)

```python
from imdr.market_calendar import (
    is_weekend, is_holiday, is_trading_day,
    is_market_open, last_trading_day, next_trading_day,
    trading_days_between, last_business_day,
)
```

| Function | Signature | Description |
|----------|-----------|-------------|
| `is_weekend` | `(country_code: str, d: date) -> bool` | Check if date falls on country's weekend days (reads `dbo.dim_country`) |
| `is_holiday` | `(country_code: str, calendar_code: str, d: date) -> bool` | Check if date is a public/financial holiday for that calendar |
| `is_trading_day` | `(country_code: str, calendar_code: str, d: date) -> bool` | True if NOT weekend and NOT holiday |
| `is_market_open` | `(country_code: str, calendar_code: str, utc_dt: datetime) -> bool` | Converts to local time, checks trading hours + lunch |
| `last_trading_day` | `(country_code: str, calendar_code: str, before: date = None) -> date` | Most recent trading day before given date |
| `next_trading_day` | `(country_code: str, calendar_code: str, after: date = None) -> date` | Next trading day after given date |
| `trading_days_between` | `(country_code: str, calendar_code: str, start: date, end: date) -> list[date]` | All trading days in [start, end] |
| `last_business_day` | `(country_code: str, calendar_code: str) -> datetime` | Holiday-aware, returns UTC datetime at midnight; both args required |

### IMM Dates (`imm.py`)

```python
from imdr.market_calendar import (
    imm_date, imm_dates_monthly, imm_dates_quarterly,
    is_imm_date, is_quarterly_imm_date, next_imm_date,
)
```

| Function | Signature | Description |
|----------|-----------|-------------|
| `imm_date` | `(year: int, month: int) -> date` | 3rd Wednesday of given month |
| `imm_dates_monthly` | `(year: int) -> list[date]` | All 12 monthly IMM dates |
| `imm_dates_quarterly` | `(year: int) -> list[date]` | Quarterly IMM dates (Mar/Jun/Sep/Dec) |
| `is_imm_date` | `(d: date) -> bool` | True if date is any monthly IMM date |
| `is_quarterly_imm_date` | `(d: date) -> bool` | True if date is a quarterly IMM date |
| `next_imm_date` | `(after: date = None, quarterly_only: bool = False) -> date` | Next IMM date after given date |

### ISDA & Holidays (`holidays.py`)

```python
from imdr.market_calendar import (
    isda_holidays, is_settlement_holiday,
    holiday_hits_for_date, holiday_hits_for_timestamp,
)
```

| Function | Signature | Description |
|----------|-----------|-------------|
| `isda_holidays` | `(center_code: str, year: int) -> dict[date, str]` | Holidays for an ISDA financial center |
| `is_settlement_holiday` | `(market_code: str, d: date) -> bool` | Check all ISDA centers for the market |
| `holiday_hits_for_date` | `(currencies: list[str], check_date: date) -> list[HolidayHit]` | Which currencies have a holiday |
| `holiday_hits_for_timestamp` | `(currencies: list[str], utc_dt: datetime) -> list[HolidayHit]` | Holiday check at UTC timestamp |

Supported ISDA financial centers (holidays v0.92): NYSE, XNYS, ECB, TAR, XECB, B3, BVMF, BSE, NSE, XBOM, XNSE, IFEU.

### CB Events (`cb_events.py`)

```python
from imdr.market_calendar.cb_events import upcoming_cb_events, recent_cb_events, rate_decisions
```

| Function | Signature | Description |
|----------|-----------|-------------|
| `upcoming_cb_events` | `(session, country_code=None, days_ahead=30)` | Upcoming CB events from DB |
| `recent_cb_events` | `(session, country_code=None, days_back=30)` | Recent CB events from DB |
| `rate_decisions` | `(session, country_code=None, days_back=90, days_ahead=90)` | High-relevance rate decisions |

### Health Check Integration

```python
from imdr.healthchecks.quality import should_relax_checks

if should_relax_checks(run_date, market_code="US"):
    # Skip row-count checks or use relaxed thresholds
    pass
```

## CB Events Import

### Monthly Excel Import

Bloomberg delivers `10yr CB events 1.xlsx` monthly with 4 sheets (2008-2012, 2012-2018, 2018-2023, 2023-2026). The import script normalizes all formats and upserts to `calendar.cb_events`.

```bash
# Default: load events within 1 month back/forward from today
python -m scripts.calendar.import_cb_events --file "<PATH_TO_XLSX>"

# Custom window
python -m scripts.calendar.import_cb_events --file "path/to/file.xlsx" --months-back 2 --months-forward 3

# Load everything (no date filter)
python -m scripts.calendar.import_cb_events --file "path/to/file.xlsx" --all

# Dry run (parse only, don't write to DB)
python -m scripts.calendar.import_cb_events --file "path/to/file.xlsx" --dry-run
```

### Bloomberg Country Code Mapping

| Bloomberg | IMDR | Country |
|-----------|------|---------|
| JN | JP | Japan |
| EC | EU | ECB/Eurozone |
| SW | SE | Sweden |
| SZ | CH | Switzerland |
| SK | KR | South Korea |
| MA | MY | Malaysia |
| PO | PL | Poland |
| SI | SG | Singapore |
| PD | PH | Philippines |

## Configuration

### Adding a New Country

Add to `src/imdr/market_calendar/countries.yml`:

```yaml
XX:
  timezone: "Region/City"       # IANA timezone
  currencies: [XXX]             # ISO currency codes
  exchanges: [EXCHANGE]         # Exchange codes
  calendar_type: country_type   # For holiday lookup
  country_code: XX              # ISO-3166 alpha-2
  weekend_days: [5, 6]          # Python weekday integers
  isda_centers: []              # ISDA financial center codes (if available)
  trading_hours:                # Optional — omit for 24h/OTC
    open: "09:00"
    close: "17:00"
    lunch_start: "12:00"        # Optional
    lunch_end: "13:00"          # Optional
```

### Adding Custom Events

Add to `src/imdr/market_calendar/events.yml`:

```yaml
- date: "2026-12-24"
  market: US
  type: early_close             # central_bank | early_close | data_blackout
  description: "Christmas Eve early close"
  close_hour: 13                # Optional, for early_close type
```

## Database Schema

Table `calendar.cb_events`:

| Column | Type | Description |
|--------|------|-------------|
| id | INT IDENTITY | Primary key |
| event_date | DATE | Event date |
| event_datetime | DATETIMEOFFSET | Bloomberg raw timestamp (see convention note below) |
| country_code | VARCHAR(5) | Bloomberg/IMDR market code |
| category | VARCHAR(50) | Central Banks, Economic Releases, Economic Events |
| event_name | NVARCHAR(500) | Event description |
| ticker | VARCHAR(50) | Bloomberg ticker (if applicable) |
| period_value | DATE | Reporting period |
| survey | VARCHAR(20) | Market survey/consensus |
| actual | VARCHAR(20) | Actual value |
| prior_value | VARCHAR(20) | Prior value |
| revised | VARCHAR(20) | Revised prior |
| relevance | FLOAT | Bloomberg relevance score (0-100) |
| frequency | VARCHAR(5) | D, M, Q, etc. |

Migration: `migrations/008_create_calendar_schema.sql`

### `event_datetime` Convention (IMPORTANT)

Bloomberg's `event_datetime` is **NOT UTC and NOT consistently convertible**. Do NOT attempt automatic timezone conversion. Use `event_date` for all calendar logic.

**Convention by event state:**

| State | Convention | Example |
|-------|-----------|---------|
| **Past events** (actuals filled) | Actual announcement time in **local timezone** of the country | BOJ at `11:23` = 11:23 JST, BI at `15:20` = 15:20 WIB |
| **Future events** (no actuals) | Placeholder — either `00:00` (unknown) or scheduled estimate | BOK future = `00:00`, RBA future = `11:30` AEST |
| **US FOMC** | Anomalous — `02:00`/`03:00` is a Bloomberg internal code, not a real time | Real FOMC is 14:00 ET = 18:00/19:00 UTC |

**Country-specific patterns:**
- **AU (RBA)**: Local AEST/AEDT — shifts with DST (11:30 winter, 12:30 summer)
- **NZ (RBNZ)**: Local NZST/NZDT — same DST shift pattern
- **JP (BOJ)**: `00:00` for future; actual JST time (~11:00-11:30) for past
- **KR (BOK)**: `00:00` for future; actual KST time (~08:50) for past
- **ID (BI)**: Consistent `15:20` WIB (Jakarta local)
- **TH (BoT)**: Consistent `15:00` ICT (Bangkok local)
- **MY (BNM)**: Consistent `15:00` MYT (Kuala Lumpur local)

## Universe Coverage Cross-Reference

Every currency in `fx.yml` and `rates.yml` maps to a country in `countries.yml`:

| Currency | Domain | Market | Notes |
|----------|--------|--------|-------|
| USD | FX, Rates | US | |
| EUR | FX, Rates | EU | TARGET2 calendar |
| GBP | FX, Rates | UK | |
| JPY | FX, Rates | JP | |
| CHF | FX, Rates | CH | |
| AUD | FX, Rates | AU | |
| NZD | FX, Rates | NZ | |
| CAD | FX, Rates | CA | |
| NOK | FX, Rates | NO | |
| SEK | FX, Rates | SE | |
| CNH | FX, Rates | CN | Offshore Yuan, same holidays as onshore |
| CNY | Rates | CN | |
| INR | FX, Rates | IN | BSE/NSE ISDA centers |
| KRW | FX, Rates | KR | |
| TWD | FX, Rates | TW | |
| THB | FX, Rates | TH | |
| IDR | FX, Rates | ID | |
| PHP | FX, Rates | PH | |
| SGD | FX, Rates | SG | |
| HKD | Rates | HK | |
| MYR | Rates | MY | |
| VND | Rates | VN | Added for rates coverage |
| DKK | Rates | DK | Added for rates coverage |
| ILS | Rates | IL | Fri/Sat weekend |
| MXN | Rates | MX | |
| ZAR | Rates | ZA | |
| PLN | Rates | PL | |
| CZK | Rates | CZ | |
| HUF | Rates | HU | |
| TRY | Rates | TR | |
| BRL | Rates | BR | B3/BVMF ISDA centers |
| CLP | Rates | CL | |
| COP | Rates | CO | |
| AED | Rates | AE | |
| ARS | Rates | AR | |
| EGP | Rates | EG | Fri/Sat weekend |
| SAR | Rates | SA | Fri/Sat weekend |
| NGN | Rates | NG | |
| RON | Rates | RO | |
| KZT | Rates | KZ | |
| BDT | Rates | BD | Fri/Sat weekend |
| LKR | Rates | LK | |
| PEN | Rates | PE | |

## Custom Entries (2026)

**Source**: `imdr_asia_em_calendar_2026.xlsx` audit (2026-03-24)
**Script**: `python -m scripts.calendar.populate_asia_em_2026` (idempotent)

### India Holiday Fixes (`calendar.market_holidays`, `vendor=MANUAL`)

| Date | Action | Detail |
|------|--------|--------|
| 2026-05-01 | Name fix | Buddha Purnima -> Maharashtra Day (NSE confirmed) |
| 2026-03-26 | Added | Shri Ram Navami |
| 2026-04-14 | Added | Dr. Baba Saheb Ambedkar Jayanti |
| 2026-09-14 | Added | Ganesh Chaturthi |
| 2026-11-10 | Added | Diwali Balipratipada |

### CB Events Added (`cb_events`)

| Country | Central Bank | Events | Dates | Source |
|---------|-------------|--------|-------|--------|
| CN | PBOC | 12 monthly LPR | ~20th each month | tradingeconomics.com |
| SG | MAS | 4 quarterly MPS | Jan 29, Apr 14*, Jul 14*, Oct 14* | mas.gov.sg |
| TW | CBC | 4 quarterly | Mar 19, Jun 18, Sep 17, Dec 17 | cbc.gov.tw (confirmed) |
| PH | BSP | 6 meetings | Feb 19, Apr 23, Jun 18, Aug 27, Oct 22, Dec 17 | bsp.gov.ph (confirmed) |
| IN | RBI | 4 additional | Jun 5, Aug 5, Oct 7, Dec 4 | hellobanker.in (confirmed) |

\* = estimated dates; update when MAS publishes exact schedule.

### Not Added

- **VN (SBV)**: No fixed meeting schedule; rate decisions are ad-hoc.
- **BD (Bangladesh Bank)**: Semi-annual policy (H1/H2 FY); no discrete meeting dates.
