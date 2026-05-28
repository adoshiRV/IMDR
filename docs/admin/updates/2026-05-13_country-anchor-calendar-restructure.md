# DB Migration Guide — Country-Anchor Calendar Restructure (2026-05-13)

- **Release date**: 2026-05-13
- **Who this is for**: anyone querying IMDR tables directly from outside the IMDR codebase — your own app, a BI tool (Power BI, Excel, Tableau), a scheduled SQL job, an ad-hoc analysis.
- **What's changing**: the legacy calendar tables (`calendar.dim_market`, `dim_market_currency`, `dim_market_calendar`, `dim_trading_day`) are being **renamed to `_old`** this release and **dropped** in a later release. Domain tables already lost their `market_code` / `market_id` columns in earlier releases; this guide also covers the SQL shape you need to adopt instead.
- **Reversibility**: the `_old` rename is reversible by a single `sp_rename` until a later release physically drops them.

See also: [docs/calendar/calendar_data_reference.md](../../calendar/calendar_data_reference.md) — the consumer-facing reference for the new calendar schema (`dbo.dim_country`, `calendar.dim_calendar`, `calendar.market_holidays`), including query recipes for trading-day checks and holiday lookups.

---

## TL;DR

**Stop reading these tables — they're going away:**

```
calendar.dim_market
calendar.dim_market_currency
calendar.dim_market_calendar
calendar.dim_trading_day
```

**Read these instead:**

```
dbo.dim_country            -- 52 rows, was calendar.dim_market
dbo.dim_currency           -- now has country_id FK (replaces dim_market_currency)
calendar.dim_calendar      -- 27 named calendars (GT/NY/TE/etc.) — already existed
calendar.market_holidays   -- 9,957 holiday rows, vendor-aware (replaces dim_trading_day)
```

Domain tables (fx, rates, equity, research, cb_events) **already** had their `market_code` / `market_id` columns dropped in earlier releases (043–049). They now have `country_id` (FK to `dbo.dim_country`). If you've been compiling against the old column names, your queries are already broken — see the [domain tables](#domain-tables-already-changed) section below.

---

## Affected tables — what's changing

### 1. Legacy tables — being renamed `_old` (then dropped later release)

| Old table | New replacement | Notes |
|---|---|---|
| `calendar.dim_market` (50 rows) | `dbo.dim_country` (52 rows) | The 50 surrogate `id` values were preserved 1:1 during migration 037, so `dim_country.id` matches what `dim_market.id` was. Plus 2 new rows: `RU` and pseudo-country `XX`. |
| `calendar.dim_market_currency` (43 rows) | `dbo.dim_currency.country_id` (FK column) | The N:M bridge collapsed to a N:1 FK because every ccy mapped to exactly one market in practice. CNH/CNY both anchor to `country_code='CN'`. |
| `calendar.dim_market_calendar` (26 rows) | **no server-side replacement** | The `(market, segment) → calendar_code` resolution moved into application code. See the [calendar-code lookup table](#calendar-code-lookup-replaces-dim_market_calendar) below for the literal mapping. |
| `calendar.dim_trading_day` (420,050 rows) | Computed on the fly from `dbo.dim_country.weekend_days` + `calendar.market_holidays` | No pre-computed grid any more. See the [query recipes](#how-to-rewrite-your-queries) for the SQL. |

### 2. Domain tables — already changed (043–049)

These changed in earlier releases. If you haven't updated your queries already, they're failing now:

| Table | Old column dropped | New column |
|---|---|---|
| `fx.dim_currency_pair` | `market_code`, `market_id` | `base_currency_id` (FK → `dbo.dim_currency.id`), `quote_currency_id` (same) |
| `rates.dim_curve` | `market_code`, `market_id` | `country_id` (FK → `dbo.dim_country.id`) |
| `rates.dim_vol_surface` | `market_code`, `market_id` | `country_id` |
| `rates.dim_skew_surface` | `market_code`, `market_id` | `country_id` |
| `rates.dim_central_bank` | `market_code`, `market_id` | `country_id` |
| `equities.dim_index` | `market_code` | `country_id` (NOT NULL) |
| `research.dim_report` | `market_code` | `country_id` (NULL allowed) |
| `calendar.cb_events` | — | `country_id` added; **`country_code` varchar(5) still present** as a one-release buffer (dropped in a future release — start migrating to `country_id` now) |

### 3. New replacement tables — read these going forward

#### `dbo.dim_country` (52 rows)

```
id              tinyint        NOT NULL  -- preserved from dim_market.id
country_code    varchar(3)     NOT NULL  -- 'US', 'UK', 'EU', 'WW', 'XX', …
iso_alpha3      char(3)        NULL      -- 'USA', 'GBR', …; NULL for pseudo-countries
display_name    varchar(100)   NOT NULL
is_pseudo       bit            NOT NULL  -- 1 for EU, WW, XX (aggregate/non-sovereign)
timezone        varchar(50)    NULL      -- IANA TZ; NULL for pseudo
weekend_days    varchar(10)    NULL      -- CSV of Python weekday ints, e.g. '5,6' = Sat,Sun.
                                         -- 4 Middle East countries use '4,5' (Fri,Sat).
                                         -- NULL for pseudo → treat as '5,6'.
trading_open    varchar(5)     NULL      -- 'HH:MM' local time; NULL for OTC / 24h
trading_close   varchar(5)     NULL
lunch_start     varchar(5)     NULL      -- JP/CN/HK have a lunch break
lunch_end       varchar(5)     NULL
is_active       bit            NOT NULL
created_at      datetimeoffset NOT NULL
updated_at      datetimeoffset NOT NULL
```

Notable: `country_code` is **our canonical key** (`UK`, `EU`), distinct from `iso_alpha3` (`GBR`, NULL for EU since it's a multi-country pseudo). Pseudo rows (`EU`, `WW`, `XX`) have NULL trading hours and weekend_days — they exist so domain tables can FK to a "country" for aggregate / metals / global instruments.

#### `dbo.dim_currency` (47 rows)

```
id            tinyint        NOT NULL
code          varchar(3)     NOT NULL  -- 'USD', 'EUR', 'CNY', 'CNH', …
country_id    tinyint        NOT NULL  -- FK → dbo.dim_country.id  (N:1, was N:M)
variant       varchar(20)    NULL      -- 'offshore' for CNH, 'onshore' for IDO/MYO, …
… (other columns unchanged)
```

Replacement for `dim_market_currency`. Get the country for a currency via `JOIN dim_country ON dim_country.id = dim_currency.country_id`. Filter for "canonical" currencies with `variant IS NULL`.

#### Weekend convention — `dim_country.weekend_days`

`dim_country.weekend_days` is a **CSV of Python-style weekday integers**, where `Mon=0, Tue=1, Wed=2, Thu=3, Fri=4, Sat=5, Sun=6`. So `'5,6'` means Sat+Sun, and `'4,5'` means Fri+Sat. NULL is treated as `'5,6'` (Sat/Sun).

Live values today:

| weekend_days | Countries |
|---|---|
| `'5,6'` (Sat+Sun) | 48 countries — the global default |
| `'4,5'` (Fri+Sat) | SA, IL, EG, BD — four Middle East / Bangladesh markets |
| NULL | EU, WW, XX (pseudo-countries) — treat as `'5,6'` |

**SQL Server gotcha**: `DATEPART(weekday, date)` is locale-dependent (depends on `@@DATEFIRST`). Use this `@@DATEFIRST`-independent formula to get a Python-style weekday from any date:

```sql
-- Returns Mon=0, Tue=1, ..., Sat=5, Sun=6 regardless of @@DATEFIRST setting.
-- 1900-01-01 was a Monday, so days-since-then mod 7 = Python weekday.
((DATEDIFF(day, '1900-01-01', @d) % 7) + 7) % 7
```

Verified against live DB:

| Date | Day of week | Formula result |
|---|---|---|
| 2026-03-20 | Friday | 4 |
| 2026-03-21 | Saturday | 5 |
| 2026-03-22 | Sunday | 6 |
| 2026-03-23 | Monday | 0 |

A reusable "is this date a weekend in this country?" pattern:

```sql
-- Returns 1 if @d is a weekend day in @country_code, 0 otherwise.
SELECT CASE
    WHEN EXISTS (
        SELECT 1
        FROM dbo.dim_country c
        CROSS APPLY STRING_SPLIT(ISNULL(c.weekend_days, '5,6'), ',') wd
        WHERE c.country_code = @country_code
          AND CAST(wd.value AS int) = ((DATEDIFF(day, '1900-01-01', @d) % 7) + 7) % 7
    ) THEN 1 ELSE 0
END AS is_weekend;
```

This works for any country in `dim_country` and any date, regardless of the SQL Server's `@@DATEFIRST` setting.

#### `calendar.dim_calendar` (27 rows)

Already existed; nothing new in this release. Lists the named holiday calendars (each row = one calendar). Used as the join target for `market_holidays`.

```
id               tinyint        NOT NULL
calendar_code    varchar(5)     NOT NULL  -- 'GT', 'NY', 'TE', 'JN', …; unique
calendar_name    varchar(100)   NOT NULL  -- 'US Govt Bond Market', 'NYSE', 'TARGET2', …
country_id       tinyint        NOT NULL  -- FK → dbo.dim_country.id
description      varchar(200)   NULL      -- BBG canonical label
is_active        bit            NOT NULL
```

Full list (post Phase D):

| country | calendar_code | calendar_name |
|---|---|---|
| US | GT | US Govt Bond Market (SIFMA) |
| US | NY | NYSE |
| US | YO | NYSE (New York, alt) |
| US | FD | Federal Reserve Board |
| EU | TE | TARGET2 |
| CN | I6 | China Interbank |
| JP | JN | Japan (TSE) |
| JP | OK | Osaka Exchange |
| NZ | KD | Auckland (NZX) |
| NZ | WL | Wellington (RBNZ) |
| PH | PH | Philippines (PSE) |
| PH | +P | Philippines FX Settlement |
| AU | AU | Australia (ASX) |
| CA | CA | Toronto Stock Exchange |
| CH | S5 | SIX Swiss Exchange |
| DE | IB | Xetra (Deutsche Boerse) |
| HK | HK | Hong Kong (HKEX) |
| ID | ID | Indonesia (IDX) |
| IN | RB | India (RBI) |
| KR | SK | South Korea (KRX) |
| MY | MA | Malaysia (Bursa) |
| NO | NO | Oslo Boers |
| SE | SW | Nasdaq Stockholm |
| SG | SI | Singapore (SGX) |
| TH | TH | Thailand (SET) |
| TW | TA | Taiwan (TWSE) |
| UK | LS | LSE (London) |

**Countries with no calendar in the DB** (you cannot resolve holidays for these from IMDR yet): AR, BR, CL, CO, MX, PE, BM, DK, PL, CZ, HU, RO, TR, RU, IL, SA, AE, EG, NG, BD, KZ, LK, VN, ZA, plus EU member states FR/IT/ES/NL/FI.

#### `calendar.market_holidays` (9,957 rows)

```
id              int            NOT NULL  -- surrogate
calendar_id     tinyint        NOT NULL  -- FK → calendar.dim_calendar.id
vendor_id       int            NOT NULL  -- FK → dbo.dim_vendor.id
holiday_date    date           NOT NULL
holiday_name    nvarchar(200)  NULL      -- "Veterans Day", "TARGET2 Christmas", etc.
is_custom       bit            NOT NULL  -- 1 for MANUAL overrides
load_batch      varchar(50)    NULL      -- batch tag for traceability
created_at      datetimeoffset NOT NULL
updated_at      datetimeoffset NOT NULL
```

Replacement for `dim_trading_day`'s `is_holiday`/`holiday_name` columns. Multi-vendor: BBG, MANUAL, HOLIDAYS_LIB, EXCHANGE_CALENDARS can all contribute rows for the same `(calendar_id, holiday_date)`. Typical query filters `vendor_code='BBG'` (see [vendor selection](#which-vendor-should-i-pick)).

#### `dbo.dim_vendor`

Already existed; relevant rows for the calendar:

```
id   vendor_code         display_name
4    bloomberg           Bloomberg                    -- legacy code, prefer 'BBG'
5    BBG                 Bloomberg                    -- canonical for market_holidays
6    MANUAL              Manual override
7    HOLIDAYS_LIB        Python holidays package
8    EXCHANGE_CALENDARS  Python exchange_calendars package
```

---

## How to rewrite your queries

### A. "Is this date a trading day for market X?"

This was the most common shape against `dim_trading_day`. You need to decide which **calendar_code** is the right one for your application's intent — see the [calendar-code lookup table](#calendar-code-lookup-replaces-dim_market_calendar) below.

```sql
-- ❌ OLD — will fail post-migration 050 ("Invalid object name dim_trading_day"):
SELECT is_trading_day
FROM calendar.dim_trading_day
WHERE market_code = 'US' AND calendar_date = '2026-11-11';
```

```sql
-- ✅ NEW — compute it. Two pieces: weekend check + holiday check.
DECLARE @country_code varchar(3)   = 'US';
DECLARE @calendar_code varchar(5)  = 'GT';   -- SIFMA US Govt Bond
DECLARE @d date                    = '2026-11-11';
DECLARE @vendor_code varchar(50)   = 'BBG';

SELECT
    CASE
        -- Weekend check: country's weekend_days CSV is Python-style (Mon=0..Sun=6).
        -- The DATEDIFF formula gives Python weekday regardless of @@DATEFIRST —
        -- see the "Weekend convention" section above.
        WHEN EXISTS (
            SELECT 1
            FROM dbo.dim_country c
            CROSS APPLY STRING_SPLIT(ISNULL(c.weekend_days, '5,6'), ',') wd
            WHERE c.country_code = @country_code
              AND CAST(wd.value AS int) = ((DATEDIFF(day, '1900-01-01', @d) % 7) + 7) % 7
        )
            THEN CAST(0 AS bit)
        -- Holiday check on the chosen calendar + trusted vendor
        WHEN EXISTS (
            SELECT 1
            FROM calendar.market_holidays mh
            JOIN calendar.dim_calendar dc ON dc.id = mh.calendar_id
            JOIN dbo.dim_vendor v        ON v.id  = mh.vendor_id
            WHERE dc.calendar_code = @calendar_code
              AND v.vendor_code    = @vendor_code
              AND mh.holiday_date  = @d
        )
            THEN CAST(0 AS bit)
        ELSE CAST(1 AS bit)
    END AS is_trading_day;
```

### B. "Give me all trading days between two dates for market X"

```sql
-- ❌ OLD:
SELECT calendar_date
FROM calendar.dim_trading_day
WHERE market_code = 'US'
  AND calendar_date BETWEEN '2026-03-16' AND '2026-03-20'
  AND is_trading_day = 1
ORDER BY calendar_date;
```

```sql
-- ✅ NEW — inline view that returns the same `(calendar_date, is_trading_day)` shape.
-- Easiest if you wrap it as a TVF or view in your own schema once and re-use.
DECLARE @country_code varchar(3)  = 'US';
DECLARE @calendar_code varchar(5) = 'GT';
DECLARE @start date = '2026-03-16';
DECLARE @end date   = '2026-03-20';

WITH country AS (
    SELECT TOP 1 ISNULL(weekend_days, '5,6') AS weekend_days
    FROM dbo.dim_country WHERE country_code = @country_code
),
date_range AS (
    SELECT @start AS calendar_date
    UNION ALL
    SELECT DATEADD(day, 1, calendar_date)
    FROM date_range WHERE calendar_date < @end
),
weekend_set AS (
    SELECT CAST(value AS int) AS py_weekday
    FROM country
    CROSS APPLY STRING_SPLIT(weekend_days, ',')
),
holidays AS (
    SELECT mh.holiday_date
    FROM calendar.market_holidays mh
    JOIN calendar.dim_calendar dc ON dc.id = mh.calendar_id
    JOIN dbo.dim_vendor v        ON v.id  = mh.vendor_id
    WHERE dc.calendar_code = @calendar_code
      AND v.vendor_code    = 'BBG'
      AND mh.holiday_date BETWEEN @start AND @end
)
SELECT dr.calendar_date
FROM date_range dr
LEFT JOIN weekend_set ws ON ws.py_weekday = ((DATEDIFF(day, '1900-01-01', dr.calendar_date) % 7) + 7) % 7
LEFT JOIN holidays h     ON h.holiday_date = dr.calendar_date
WHERE ws.py_weekday IS NULL
  AND h.holiday_date IS NULL
ORDER BY dr.calendar_date
OPTION (MAXRECURSION 1000);
```

(Tip: if you do this query often, materialize a view in your own database/schema — IMDR no longer caches a pre-computed grid.)

### C. "What's the most recent business day for market X?"

```sql
-- ❌ OLD:
SELECT TOP 1 calendar_date
FROM calendar.dim_trading_day
WHERE market_code = 'US'
  AND calendar_date <= CAST(SYSDATETIMEOFFSET() AS date)
  AND is_trading_day = 1
ORDER BY calendar_date DESC;
```

```sql
-- ✅ NEW — walk back up to 30 days from today.
DECLARE @country_code varchar(3)  = 'US';
DECLARE @calendar_code varchar(5) = 'GT';

WITH dates AS (
    SELECT CAST(SYSDATETIMEOFFSET() AS date) AS calendar_date, 0 AS n
    UNION ALL
    SELECT DATEADD(day, -1, calendar_date), n + 1 FROM dates WHERE n < 30
),
weekend_set AS (
    SELECT CAST(value AS int) AS py_weekday
    FROM dbo.dim_country
    CROSS APPLY STRING_SPLIT(ISNULL(weekend_days, '5,6'), ',')
    WHERE country_code = @country_code
),
holidays AS (
    SELECT mh.holiday_date
    FROM calendar.market_holidays mh
    JOIN calendar.dim_calendar dc ON dc.id = mh.calendar_id
    JOIN dbo.dim_vendor v        ON v.id  = mh.vendor_id
    WHERE dc.calendar_code = @calendar_code
      AND v.vendor_code = 'BBG'
)
SELECT TOP 1 d.calendar_date
FROM dates d
LEFT JOIN weekend_set ws ON ws.py_weekday = ((DATEDIFF(day, '1900-01-01', d.calendar_date) % 7) + 7) % 7
LEFT JOIN holidays h     ON h.holiday_date = d.calendar_date
WHERE ws.py_weekday IS NULL
  AND h.holiday_date IS NULL
ORDER BY d.calendar_date DESC
OPTION (MAXRECURSION 100);
```

### D. "Which currencies trade in market X?"

```sql
-- ❌ OLD:
SELECT ccy FROM calendar.dim_market_currency WHERE market_code = 'US';
```

```sql
-- ✅ NEW:
SELECT cu.code
FROM dbo.dim_currency cu
JOIN dbo.dim_country  c ON c.id = cu.country_id
WHERE c.country_code = 'US';
```

The new model is N:1 (each currency belongs to exactly one country). CNH and CNY both return for `country_code='CN'`.

### E. "What countries are configured? Their trading hours? Weekend convention?"

```sql
-- ❌ OLD:
SELECT market_code, market_name, timezone, country_code_iso, weekend_days,
       trading_open, trading_close, lunch_start, lunch_end
FROM calendar.dim_market
WHERE 1=1   -- no is_active flag previously
ORDER BY market_code;
```

```sql
-- ✅ NEW:
SELECT country_code, display_name, iso_alpha3, is_pseudo,
       timezone, weekend_days,
       trading_open, trading_close, lunch_start, lunch_end
FROM dbo.dim_country
WHERE is_active = 1
ORDER BY country_code;
```

Differences:
- `market_code` → `country_code` (rename only; values are identical except 2 additions: `RU`, `XX`)
- `market_name` → `display_name`
- `country_code_iso` (2-letter) → `iso_alpha3` (3-letter; NULL for pseudo)
- `is_pseudo` is new; filter `is_pseudo = 0` if you want only sovereign countries.

### F. "Central bank events filtered by country"

`cb_events.country_code` (the varchar(5) column) **still works this release** but is deprecated:

```sql
-- ❌ OLD — country_code column was dropped by migration 051; this errors with
--    "Invalid column name 'country_code'":
SELECT * FROM calendar.cb_events WHERE country_code = 'US';
```

```sql
-- ✅ NEW — JOIN to dbo.dim_country to filter by the canonical country code:
SELECT ev.*
FROM calendar.cb_events ev
JOIN dbo.dim_country c ON c.id = ev.country_id
WHERE c.country_code = 'US';
```

### G. Joins from domain tables to the calendar

If you had queries like:

```sql
-- ❌ OLD — these columns no longer exist on rates.dim_curve:
SELECT cu.curve_code, dm.market_name
FROM rates.dim_curve cu
JOIN calendar.dim_market dm ON dm.market_code = cu.market_code;
```

```sql
-- ✅ NEW:
SELECT cu.curve_code, c.display_name
FROM rates.dim_curve cu
JOIN dbo.dim_country c ON c.id = cu.country_id;
```

Same pattern for every domain table in the [table above](#2-domain-tables--already-changed-043049). `country_id` is the universal join key now.

### H. fx pair tables — special case (two countries per pair)

`fx.dim_currency_pair` doesn't have a single `country_id` — a pair has two countries (one per leg). Use the currency FKs:

```sql
-- ❌ OLD:
SELECT base_ccy, quote_ccy FROM fx.dim_currency_pair WHERE market_code = 'EU';
```

```sql
-- ✅ NEW — query by base or quote country:
SELECT bc.code AS base_ccy, qc.code AS quote_ccy
FROM fx.dim_currency_pair p
JOIN dbo.dim_currency bc ON bc.id = p.base_currency_id
JOIN dbo.dim_currency qc ON qc.id = p.quote_currency_id
JOIN dbo.dim_country  bcc ON bcc.id = bc.country_id
JOIN dbo.dim_country  qcc ON qcc.id = qc.country_id
WHERE bcc.country_code = 'EU' OR qcc.country_code = 'EU';
```

The string columns `base_ccy` and `quote_ccy` on `fx.dim_currency_pair` are still there for backwards compat (slated to drop in a future release tracked separately). The FK ids `base_currency_id` / `quote_currency_id` are the forward-compat path.

---

## Calendar-code lookup (replaces `dim_market_calendar`)

The old `dim_market_calendar` bridge let you ask "given market X and segment Y, which calendar do I use?" That table is going away. The literal mapping it would have returned is below. Embed this in your application code, or copy it into a view in your own schema.

| country | "rates" intent | "equity" intent | "central bank" intent | "FX settlement" intent |
|---|---|---|---|---|
| US | `GT` (SIFMA) | `NY` (NYSE) | `FD` (Fed) | `GT` |
| EU | `TE` (TARGET2) | `IB` (Xetra) | — | `TE` |
| CN | `I6` (Interbank) | — | — | `I6` |
| UK | (none — use `LS`) | `LS` (LSE) | — | `LS` |
| JP | (none — use `JN`) | `JN` (TSE) | — | `JN` |
| NZ | (none — use `WL`) | `KD` (NZX) | `WL` (RBNZ) | `KD` |
| PH | (none — use `+P`) | `PH` (PSE) | — | `+P` |
| IN | (none — use `RB`) | (none — use `RB`) | `RB` (RBI) | `RB` |
| AU, CA, CH, DE, HK, ID, KR, MY, NO, SE, SG, TH, TW | their only calendar code (see [calendar list](#calendardim_calendar-27-rows)) for all intents | | | |

**Country has no DB calendar entry at all**: AR, BR, CL, CO, MX, PE, BM, DK, PL, CZ, HU, RO, TR, RU, IL, SA, AE, EG, NG, BD, KZ, LK, VN, ZA, plus EU members FR/IT/ES/NL/FI. There is no IMDR-resident calendar to query for these — you'll need an external holiday source for now.

---

## Which vendor should I pick?

**Today: BBG only.** Verified against the live DB on 2026-05-13:

| vendor_code | display_name | rows in market_holidays | distinct calendars covered |
|---|---|---|---|
| BBG | Bloomberg | 9,957 | 27 (all of them) |

No other vendor has any rows. So your filter just needs:

```sql
JOIN dbo.dim_vendor v ON v.id = mh.vendor_id WHERE v.vendor_code = 'BBG'
```

That's it — there's no choice to make.

**Why is the table modeled as multi-vendor then?** `dbo.dim_vendor` defines four calendar vendors (`BBG`, `MANUAL`, `HOLIDAYS_LIB`, `EXCHANGE_CALENDARS`) so that future loads can coexist with BBG without conflicting on the `(calendar_id, holiday_date)` key. None of `MANUAL` / `HOLIDAYS_LIB` / `EXCHANGE_CALENDARS` has rows today. If/when they get loaded, this guide gets a new entry in `docs/admin/updates/` spelling out the layering rules (typical pattern: MANUAL wins on conflict; BBG is the fallback). For now, ignore the multi-vendor shape and always filter `vendor_code = 'BBG'`.

---

## Timeline

### ✅ Already happened (in previous releases)

Migrations 037–049 ran over earlier sessions. **If your code still references `*.market_code` or `*.market_id` on any of the domain tables (fx/rates/equity/research/cb_events), it's broken now** — those columns are gone. See section [2. Domain tables](#2-domain-tables--already-changed-043049) for the replacements.

### ⚠ Just shipped (2026-05-13 / 2026-05-14)

- **Migration 050 — applied 2026-05-13.** Renamed the 4 legacy calendar tables to `_old` suffix:
  - `calendar.dim_market` → `calendar.dim_market_old` (50 rows preserved)
  - `calendar.dim_market_currency` → `calendar.dim_market_currency_old` (43 rows preserved)
  - `calendar.dim_market_calendar` → `calendar.dim_market_calendar_old` (26 rows preserved)
  - `calendar.dim_trading_day` → `calendar.dim_trading_day_old` (420,050 rows preserved)

  Any query against the un-suffixed name now fails with **`Invalid object name 'calendar.dim_market'`** (or equivalent). Verified live as of this release.

- **Migration 051 — applied 2026-05-14.** Dropped `calendar.cb_events.country_code` varchar(5) column; the 3 supporting indexes were rebuilt on `country_id` with their original `WHERE ticker IS NULL` / `WHERE ticker IS NOT NULL` filters preserved. A redundant single-column `ix_cb_events_country_id` was also dropped (it became a strict leftmost prefix of the rebuilt `IX_cb_events_country (country_id, event_date)`).

  Row count preserved at 16,540; zero NULL `country_id`; zero orphan FKs. Any query still using `WHERE country_code = …` against `calendar.cb_events` now fails with **`Invalid column name 'country_code'`**. Switch to the JOIN form shown in [recipe F](#f-central-bank-events-filtered-by-country).

### 🗓 Deferred to a later release

- **Later release — physical `DROP TABLE` of the 4 `_old` tables.** Once this ships, the data is gone (420,050 rows in `dim_trading_day_old` especially). You will not be able to recover via rename. Date TBD; expect ≥1 release of stability after the rename first. Migration number assigned at ship time.

---

## Verification

Before this release ships, run these against your codebase / query log to find anything that still needs updating:

### Check your source code / saved queries

```bash
# Bash:
grep -rE "calendar\.dim_market\b|calendar\.dim_market_currency|calendar\.dim_market_calendar|calendar\.dim_trading_day" your_repo/
grep -rE "\bmarket_code\s*=|\bmarket_id\s*=" your_repo/   # likely false positives, but worth scanning
```

### Check your BI / query-log metadata

If your reporting platform captures executed query text (SQL Server query store, Power BI's query log, dbt's run results, etc.), scan it:

```sql
-- Adapt to your query log table:
SELECT TOP 100 query_text, executed_at
FROM your_query_log
WHERE query_text LIKE '%calendar.dim_market%'
   OR query_text LIKE '%calendar.dim_trading_day%'
   OR query_text LIKE '%dim_market_currency%'
ORDER BY executed_at DESC;
```

### Post-deploy smoke

Once migration 050 has been applied, this should fail (table renamed):

```sql
SELECT TOP 1 1 FROM calendar.dim_market;
-- Expected: "Invalid object name 'calendar.dim_market'." If it succeeds,
-- you're not on the post-050 state yet.
```

And this should succeed:

```sql
SELECT TOP 1 country_code, display_name FROM dbo.dim_country;
SELECT TOP 1 calendar_code, calendar_name FROM calendar.dim_calendar;
SELECT TOP 1 holiday_date, holiday_name FROM calendar.market_holidays;
```

### Spot-check parity

For a given date, the old `dim_trading_day` answer should match the new computed answer. Run this against a recent business day before the rename to confirm your migrated query returns the same result:

```sql
-- Before migration 050:
SELECT calendar_date, is_trading_day, holiday_name
FROM calendar.dim_trading_day
WHERE market_code = 'US' AND calendar_date BETWEEN '2026-11-09' AND '2026-11-13';

-- Your migrated query against dim_country + market_holidays should return the
-- same is_trading_day flags for those dates (with calendar_code='GT' for rates
-- intent, 'NY' for equity intent — they differ on Veterans Day, 2026-11-11).
```

---

## Reversibility

| Step | Reversible? | How |
|---|---|---|
| Migrations 037–049 (already shipped) | Effectively no — would require restoring `market_code`/`market_id` columns from a backup and re-pointing FKs. Data preserved in `country_id` columns. | Restore the pre-release DB backup. |
| Migration 050 (rename `_old`) | Yes — one `sp_rename` per table reverses it. Data intact. | `EXEC sp_rename 'calendar.dim_market_old', 'dim_market';` etc. |
| Migration 051 (drop `cb_events.country_code`) | Yes, but expensive — re-add column, `UPDATE cb_events SET country_code = c.country_code FROM dim_country c WHERE c.id = country_id`, rebuild 3 indexes. | Add column + UPDATE + recreate indexes. |
| Physical DROP of `_old` tables (future migration) | **No** — destroys 420,050+ rows in `dim_trading_day_old` plus the smaller dims. | Restore from backup. Schedule explicitly. |

---

## Got a query that doesn't fit any pattern above?

Open a ticket / Slack and share the offending SQL. The four legacy tables (`dim_market`, `dim_market_currency`, `dim_market_calendar`, `dim_trading_day`) have no remaining read consumers inside IMDR itself after this release — everything is built off `dim_country` / `dim_calendar` / `market_holidays`. If your query can't be expressed against the new tables, that's worth knowing before the future physical-DROP migration ships.
