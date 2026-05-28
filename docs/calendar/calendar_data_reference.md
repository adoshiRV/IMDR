# Calendar Data — Consumer Reference

Last updated: 2026-05-14

## What's in this domain

The calendar domain provides three categories of queryable reference data. **Holiday calendars** (`calendar.market_holidays` + `calendar.dim_calendar`) cover 27 named trading calendars across 21 countries (NYSE, LSE, TSE, ASX, etc.) with holiday dates sourced from Bloomberg; the table holds 9,957 holiday rows spanning 2007–2042. **Central bank meeting events** (`calendar.cb_events`) hold scheduled CB meeting dates, actual/survey/prior policy rate outcomes, and other macro economic event data from Bloomberg Excel exports; 16,540 rows from 2008 to end-2026. **Country and currency metadata** (`dbo.dim_country`, `dbo.dim_currency`) underpins the calendar joins and provides timezone, trading hours, and weekend conventions for 52 countries.

There is no pre-computed trading day grid in IMDR. The legacy `calendar.dim_trading_day` table was renamed to `calendar.dim_trading_day_old` in migration 050 (2026-05-13) and will be dropped in a future release. Do not query the `_old` tables. Instead, compute trading day status on the fly from `dbo.dim_country.weekend_days` and `calendar.market_holidays` — query recipes are provided in this document. Consumer-facing calendar documentation (this file) is distinct from the maintainer documentation at [`docs/admin/calendar/`](../admin/calendar/).

## Coverage

### calendar.dim_calendar — 27 calendars

| Code | Name | Country |
|---|---|---|
| FD | Federal Reserve Board | US |
| GT | US Govt Bond Market (SIFMA) | US |
| NY | NYSE | US |
| YO | NYSE (New York, alt) | US |
| TE | TARGET2 | EU |
| AU | Australia (ASX) | AU |
| CA | Toronto Stock Exchange | CA |
| HK | Hong Kong (HKEX) | HK |
| I6 | China Interbank | CN |
| IB | Xetra (Deutsche Boerse) | DE |
| ID | Indonesia (IDX) | ID |
| JN | Japan (TSE) | JP |
| KD | Auckland (NZX) | NZ |
| LS | LSE (London) | UK |
| MA | Malaysia (Bursa) | MY |
| NO | Oslo Boers | NO |
| OK | Osaka Exchange | JP |
| PH | Philippines (PSE) | PH |
| +P | Philippines FX Settlement | PH |
| RB | India (RBI) | IN |
| S5 | SIX Swiss Exchange | CH |
| SI | Singapore (SGX) | SG |
| SK | South Korea (KRX) | KR |
| SW | Nasdaq Stockholm | SE |
| TA | Taiwan (TWSE) | TW |
| TH | Thailand (SET) | TH |
| WL | Wellington (RBNZ) | NZ |

**Important: US has four separate calendars.** GT (SIFMA/Govt Bond) and NY (NYSE) differ on ~45 dates per year: GT is closed Veterans Day and Columbus Day but open Good Friday; NYSE is closed Good Friday but observes Columbus/Veterans differently. For rates contexts use GT; for equity contexts use NY. FD is the Fed's own calendar; YO is a NY-region banking calendar.

**Countries with no DB calendar (cannot look up holidays in IMDR):** AR, BR, CL, CO, MX, DK, PL, CZ, HU, TR, IL, SA, AE, EG, ZA, VN, plus EU members FR/IT/ES/NL/FI.

**Vendor:** BBG is the only vendor with rows in `market_holidays` today (all 9,957 rows). Filter `vendor_code = 'BBG'` in all holiday queries.

### calendar.cb_events — 16,540 rows

Category values: `Central Banks` (the vast majority), `Unknown` (a small number of uncategorized rows).

Event date range: 2008-01-02 to 2026-12-28. This covers historic meeting dates with actual outcomes, plus scheduled forward dates for 2026 (with estimated outcomes flagged by `is_estimated = 1`).

Filter by country via `country_id` JOIN to `dbo.dim_country` (the `country_code` varchar column was dropped in migration 051 — do not use it). Key CB countries covered: US (FED), EU, UK, JP, AU, CA, NZ, and others from the Bloomberg import.

### dbo.dim_country — 52 rows

Trading hours and weekend conventions for all countries referenced in the calendar and domain tables. 48 countries use Sat+Sun as weekend; 4 use Fri+Sat (SA, IL, EG, BD). 3 pseudo-country rows (EU, WW, XX) exist for aggregate instruments.

---

## Schema — full dump

### `calendar.dim_calendar`

One row per named holiday calendar. Use `calendar_code` as the primary query key.

| Column | Type | Nullable | FK | Description |
|---|---|---|---|---|
| `id` | TINYINT | NO | — | Surrogate PK |
| `calendar_code` | VARCHAR(5) | NO | — | Short code (e.g. GT, NY, TE, JN) |
| `calendar_name` | VARCHAR(100) | NO | — | Full name |
| `country_id` | TINYINT | NO | `dbo.dim_country(id)` | Country anchor |
| `description` | NVARCHAR | YES | — | BBG canonical label |
| `is_active` | BIT | NO | — | 1 for active calendars |
| `created_at` | DATETIMEOFFSET | NO | — | Row insertion time |
| `updated_at` | DATETIMEOFFSET | NO | — | Last update time |

---

### `calendar.market_holidays`

One row per (calendar, vendor, holiday date). The replacement for the retired `dim_trading_day` table.

| Column | Type | Nullable | FK | Description |
|---|---|---|---|---|
| `id` | INT | NO | — | Surrogate PK |
| `calendar_id` | TINYINT | NO | `calendar.dim_calendar(id)` | Which calendar |
| `vendor_id` | INT | NO | `dbo.dim_vendor(id)` | Source vendor — use BBG (id=5) |
| `holiday_date` | DATE | NO | — | The holiday date |
| `holiday_name` | NVARCHAR(200) | YES | — | Name (e.g. "Veterans Day", "Golden Week") |
| `is_custom` | BIT | NO | — | 1 for MANUAL override rows |
| `load_batch` | VARCHAR(50) | YES | — | Batch traceability tag |
| `created_at` | DATETIMEOFFSET | NO | — | Row insertion time |
| `updated_at` | DATETIMEOFFSET | NO | — | Last update time |

Date range: 2007-01-01 to 2042-10-10 (BBG forward calendar loaded through 2042)

**Currently only BBG rows exist.** Filter:
```sql
JOIN [dbo].[dim_vendor] v ON v.id = mh.vendor_id
WHERE v.vendor_code = 'BBG'
```

---

### `calendar.cb_events`

One row per central bank or macro event.

| Column | Type | Nullable | FK | Description |
|---|---|---|---|---|
| `id` | INT | NO | — | Surrogate PK |
| `event_date` | DATE | NO | — | Date of the event |
| `event_datetime` | DATETIMEOFFSET | YES | — | Exact time if known (NULL for many historic entries) |
| `category` | VARCHAR(50) | NO | — | `Central Banks` or `Unknown` |
| `event_name` | VARCHAR(200) | NO | — | Event description (e.g. "FOMC Rate Decision") |
| `ticker` | VARCHAR(50) | YES | — | Bloomberg ticker if applicable |
| `period_value` | DATE | YES | — | Reference period date |
| `survey` | VARCHAR(50) | YES | — | Consensus estimate |
| `actual` | VARCHAR(50) | YES | — | Actual outcome (NULL for future events) |
| `prior_value` | VARCHAR(50) | YES | — | Prior period value |
| `revised` | VARCHAR(50) | YES | — | Revised prior value if revised |
| `relevance` | FLOAT | YES | — | Bloomberg relevance score |
| `frequency` | VARCHAR(20) | YES | — | Meeting frequency description |
| `is_estimated` | BIT | NO | — | 1 for forward-scheduled dates with no actual yet |
| `source` | VARCHAR(50) | YES | — | Source of the event record |
| `country_id` | TINYINT | NO | `dbo.dim_country(id)` | Country anchor for this event |
| `created_at` | DATETIMEOFFSET | NO | — | Row insertion time |
| `updated_at` | DATETIMEOFFSET | NO | — | Last update time |

Date range: 2008-01-02 to 2026-12-28

Note: `actual`, `survey`, `prior_value`, `revised` are VARCHAR because the Bloomberg source encodes rate outcomes as strings (e.g. "5.25-5.50%", "25bp"). Cast to FLOAT at query time if needed, filtering out non-numeric values.

---

### `dbo.dim_country`

One row per country (52 rows, including 3 pseudo-country rows: EU, WW, XX).

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | TINYINT | NO | Surrogate PK (preserved from legacy dim_market.id) |
| `country_code` | VARCHAR(3) | NO | IMDR canonical key (e.g. US, UK, EU, JP) |
| `iso_alpha3` | CHAR(3) | YES | ISO 3166-1 alpha-3 (e.g. USA, GBR; NULL for pseudo-countries) |
| `display_name` | VARCHAR(100) | NO | Human-readable name |
| `is_pseudo` | BIT | NO | 1 for EU, WW, XX (aggregate/non-sovereign) |
| `timezone` | VARCHAR(50) | YES | IANA TZ string; NULL for pseudo |
| `weekend_days` | VARCHAR(10) | YES | CSV of Python weekday ints (Mon=0…Sun=6). `'5,6'` = Sat+Sun (default). `'4,5'` = Fri+Sat for SA/IL/EG/BD. NULL = treat as `'5,6'`. |
| `trading_open` | VARCHAR(5) | YES | Local market open (HH:MM); NULL for OTC/24h |
| `trading_close` | VARCHAR(5) | YES | Local market close (HH:MM) |
| `lunch_start` | VARCHAR(5) | YES | Lunch break start; non-NULL for JP, CN, HK |
| `lunch_end` | VARCHAR(5) | YES | Lunch break end |
| `is_active` | BIT | NO | 1 for active countries |
| `created_at` | DATETIMEOFFSET | NO | Row insertion time |
| `updated_at` | DATETIMEOFFSET | NO | Last update time |

**Weekend day formula** — `DATEPART(weekday, date)` is locale-dependent. Use this `@@DATEFIRST`-independent formula to get a Python-style weekday:
```sql
((DATEDIFF(day, '1900-01-01', @d) % 7) + 7) % 7
-- Result: Mon=0, Tue=1, Wed=2, Thu=3, Fri=4, Sat=5, Sun=6
```

---

### `dbo.dim_currency`

One row per tracked currency (47 rows).

| Column | Type | Nullable | FK | Description |
|---|---|---|---|---|
| `id` | TINYINT | NO | — | Surrogate PK |
| `code` | VARCHAR(3) | NO | — | ISO currency code (USD, EUR, CNY, CNH…) |
| `display_name` | VARCHAR(100) | NO | — | Human-readable name |
| `is_active` | BIT | NO | — | 1 if actively traded |
| `country_id` | TINYINT | NO | `dbo.dim_country(id)` | Country this currency belongs to |
| `variant` | VARCHAR(20) | YES | — | `offshore` for CNH, `onshore` for IDO/MYO; NULL for standard |
| `created_at` | DATETIMEOFFSET | NO | — | Row insertion time |
| `updated_at` | DATETIMEOFFSET | NO | — | Last update time |

CNH and CNY both map to `country_code = 'CN'`; differentiate with `variant`.

---

## How to query — examples

**1. Is a given date a trading day for the US Govt Bond market (SIFMA)?**

```sql
DECLARE @country_code varchar(3)  = 'US';
DECLARE @calendar_code varchar(5) = 'GT';   -- SIFMA / US Govt Bond
DECLARE @d date                   = '2026-11-11';  -- Veterans Day

SELECT
    CASE
        WHEN EXISTS (
            SELECT 1
            FROM [dbo].[dim_country] c
            CROSS APPLY STRING_SPLIT(ISNULL(c.weekend_days, '5,6'), ',') wd
            WHERE c.country_code = @country_code
              AND CAST(wd.value AS int) = ((DATEDIFF(day,'1900-01-01',@d) % 7) + 7) % 7
        ) THEN 'weekend'
        WHEN EXISTS (
            SELECT 1
            FROM [calendar].[market_holidays] mh
            JOIN [calendar].[dim_calendar] dc ON dc.id = mh.calendar_id
            JOIN [dbo].[dim_vendor]        v  ON v.id  = mh.vendor_id
            WHERE dc.calendar_code = @calendar_code
              AND v.vendor_code    = 'BBG'
              AND mh.holiday_date  = @d
        ) THEN 'holiday'
        ELSE 'trading day'
    END AS day_status;
-- Expected: 'holiday' (Veterans Day — SIFMA is closed; NYSE is open)
```

---

**2. All US NYSE trading days in a date range**

```sql
DECLARE @start date = '2026-11-09';
DECLARE @end   date = '2026-11-13';

WITH date_range AS (
    SELECT @start AS calendar_date
    UNION ALL
    SELECT DATEADD(day, 1, calendar_date)
    FROM date_range WHERE calendar_date < @end
),
weekdays AS (
    SELECT CAST(value AS int) AS py_weekday
    FROM [dbo].[dim_country]
    CROSS APPLY STRING_SPLIT(ISNULL(weekend_days, '5,6'), ',')
    WHERE country_code = 'US'
),
holidays AS (
    SELECT mh.holiday_date
    FROM [calendar].[market_holidays] mh
    JOIN [calendar].[dim_calendar] dc ON dc.id = mh.calendar_id
    JOIN [dbo].[dim_vendor]        v  ON v.id  = mh.vendor_id
    WHERE dc.calendar_code = 'NY'
      AND v.vendor_code    = 'BBG'
      AND mh.holiday_date BETWEEN @start AND @end
)
SELECT dr.calendar_date
FROM date_range dr
LEFT JOIN weekdays w ON w.py_weekday = ((DATEDIFF(day,'1900-01-01',dr.calendar_date) % 7)+7) % 7
LEFT JOIN holidays h ON h.holiday_date = dr.calendar_date
WHERE w.py_weekday IS NULL AND h.holiday_date IS NULL
ORDER BY dr.calendar_date
OPTION (MAXRECURSION 1000);
```

---

**3. All US holidays in 2026 (SIFMA / Govt Bond calendar)**

```sql
SELECT
    mh.holiday_date,
    mh.holiday_name
FROM [calendar].[market_holidays] mh
JOIN [calendar].[dim_calendar] dc ON dc.id = mh.calendar_id
JOIN [dbo].[dim_vendor]        v  ON v.id  = mh.vendor_id
WHERE dc.calendar_code = 'GT'
  AND v.vendor_code    = 'BBG'
  AND YEAR(mh.holiday_date) = 2026
ORDER BY mh.holiday_date;
```

---

**4. Next scheduled FOMC meeting (estimated or confirmed)**

```sql
SELECT TOP 1
    ev.event_date,
    ev.event_name,
    ev.actual,
    ev.survey,
    ev.is_estimated
FROM [calendar].[cb_events] ev
JOIN [dbo].[dim_country] c ON c.id = ev.country_id
WHERE c.country_code = 'US'
  AND ev.category    = 'Central Banks'
  AND ev.event_date  >= CAST(GETDATE() AS date)
ORDER BY ev.event_date;
```

---

**5. All central bank meeting dates in 2026, with outcomes where available**

```sql
SELECT
    c.country_code,
    ev.event_name,
    ev.event_date,
    ev.actual,
    ev.prior_value,
    ev.is_estimated
FROM [calendar].[cb_events] ev
JOIN [dbo].[dim_country] c ON c.id = ev.country_id
WHERE ev.category    = 'Central Banks'
  AND YEAR(ev.event_date) = 2026
ORDER BY ev.event_date, c.country_code;
```

---

**6. Singapore (SGX) market — is 2026-08-09 (National Day) a holiday?**

```sql
SELECT
    mh.holiday_date,
    mh.holiday_name,
    dc.calendar_name
FROM [calendar].[market_holidays] mh
JOIN [calendar].[dim_calendar] dc ON dc.id = mh.calendar_id
JOIN [dbo].[dim_vendor]        v  ON v.id  = mh.vendor_id
WHERE dc.calendar_code = 'SI'   -- Singapore (SGX)
  AND v.vendor_code    = 'BBG'
  AND mh.holiday_date  = '2026-08-09';
-- Returns a row if it's a holiday; returns empty if it's a trading day.
```

---

## Connection details

- **Server:** read from `IMDR_MSSQL_SERVER` environment variable
- **Database:** `IMDR` (never connect to any other database)
- **Auth:** Windows Authentication (`Trusted_Connection=yes`)
- **Driver:** `SQL Server` (legacy ODBC driver; set via `IMDR_MSSQL_DRIVER=SQL+Server`)
- **Access level:** analysts have read-only SELECT on `calendar`, `dbo`, `audit` schemas

---

## Vendor notes

**Bloomberg** is the only vendor with data in `market_holidays` today (all 9,957 rows, `vendor_code = 'BBG'`). Holiday data was imported from a Bloomberg Excel master calendar. The table is modelled as multi-vendor (with `dbo.dim_vendor` FKs for BBG, MANUAL, HOLIDAYS_LIB, EXCHANGE_CALENDARS) so future vendor layers can coexist without key conflicts. Until a second vendor is loaded, always filter `vendor_code = 'BBG'`.

**Manual overrides** (`is_custom = 1`, `vendor_code = 'MANUAL'`) take priority over BBG rows in IMDR's own pipeline logic. Currently no MANUAL rows exist in the DB, but the model supports them. India holiday overrides sourced from an Excel audit were written to `market_holidays` under vendor=MANUAL via `scripts/calendar/populate_asia_em_2026.py`.

---

## Migration notes (2026-05-13 — important for existing query consumers)

The legacy trading-day tables were renamed on 2026-05-13 (migration 050) and will be physically dropped in a future release:

| Old table | Status | Replacement |
|---|---|---|
| `calendar.dim_market` | Renamed to `calendar.dim_market_old` | `dbo.dim_country` |
| `calendar.dim_market_currency` | Renamed to `calendar.dim_market_currency_old` | `dbo.dim_currency.country_id` |
| `calendar.dim_market_calendar` | Renamed to `calendar.dim_market_calendar_old` | Application-level mapping; see [2026-05-13 migration guide](../admin/updates/2026-05-13_country-anchor-calendar-restructure.md) |
| `calendar.dim_trading_day` | Renamed to `calendar.dim_trading_day_old` | Compute from `dim_country.weekend_days` + `market_holidays` |

The `cb_events.country_code` varchar column was also dropped in migration 051 (2026-05-14). Use `JOIN dbo.dim_country ON country_id` to filter by country code.

See also: consumer-facing migration guide at [docs/admin/updates/2026-05-13_country-anchor-calendar-restructure.md](../admin/updates/2026-05-13_country-anchor-calendar-restructure.md).

---

## Where ops detail lives

- Calendar module design (maintainer): [`docs/admin/calendar/calendar_module.md`](../admin/calendar/calendar_module.md)
- Country-anchor design: [`docs/admin/calendar/country_anchor_design.md`](../admin/calendar/country_anchor_design.md)
- CB events refresh runbook: [`docs/admin/calendar/cb_events_refresh.md`](../admin/calendar/cb_events_refresh.md)
- Country config YAML: [`src/imdr/market_calendar/countries.yml`](../../src/imdr/market_calendar/countries.yml)

---

## Last verified

2026-05-14. Row counts, date ranges, and column lists confirmed against live IMDR DB.
