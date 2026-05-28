# Follow-up: Physical DROP of legacy `calendar.dim_market*` + `dim_trading_day_old` tables

- **Date filed**: 2026-05-14
- **Status**: deferred — ready when PM picks it up
- **Triggered by**: migration 050 (renamed legacy tables to `*_old`) shipped 2026-05-13; the originally-planned migration 051 (physical DROP) was deferred so the rename could sit in prod for a stability period. Migration 051 was instead reused for the cb_events.country_code column drop.
- **Severity**: 🟢 zero IMDR-internal risk (no production code reads these tables); ⚠ destructive to row data (~420K rows in `dim_trading_day_old`) — reversal requires a full DB backup restore.

## TL;DR

Four legacy tables were renamed `_old` on 2026-05-13 and have been dormant since. They have no read consumers inside IMDR (verified by Phase D Step 11 + ongoing test runs). Consumer migration guide [`docs/admin/updates/2026-05-13_country-anchor-calendar-restructure.md`](../updates/2026-05-13_country-anchor-calendar-restructure.md) warned external SQL consumers about the rename + impending drop. Once we confirm no external consumer is still hitting the `*_old` tables, run the DROP.

## Tables to drop

Live state as of 2026-05-14 (rename verified):

| Table | Rows | FKs in (referencing this table) |
|---|---|---|
| `calendar.dim_market_old` | 50 | 3 FKs from the other 3 `*_old` tables |
| `calendar.dim_market_currency_old` | 43 | 1 FK to `dim_market_old` |
| `calendar.dim_market_calendar_old` | 26 | 3 FKs (to `dim_market_old`, `dim_calendar`, `dim_vendor`) |
| `calendar.dim_trading_day_old` | 420,050 | 1 FK to `dim_market_old` |

The `*_old` cluster has 5 internal FKs from the audit on 2026-05-13:
```
FK_calendar_dim_market_calendar_calendar : dim_market_calendar_old → dim_calendar
FK_calendar_dim_market_calendar_market   : dim_market_calendar_old → dim_market_old
FK_calendar_dim_market_calendar_vendor   : dim_market_calendar_old → dim_vendor
FK_market_currency_market                : dim_market_currency_old → dim_market_old
FK_trading_day_market                    : dim_trading_day_old     → dim_market_old
```

Two of these (`_calendar` and `_vendor`) point OUT to currently-active tables. Those FKs need to drop before the legacy tables can be dropped — otherwise SQL Server will error.

## Pre-conditions before running DROP

1. **External-consumer check**: confirm via your reporting / query log that no external app has queried `calendar.dim_market*` or `calendar.dim_trading_day*` (with or without the `_old` suffix) for ≥1 full business cycle. The migration guide warned consumers; this confirms they actually migrated.

   ```sql
   -- Adapt to your query-log source:
   SELECT TOP 100 query_text, executed_at, user_name
   FROM your_query_log
   WHERE (query_text LIKE '%calendar.dim_market%'
       OR query_text LIKE '%calendar.dim_trading_day%')
     AND executed_at > DATEADD(month, -1, SYSDATETIMEOFFSET());
   ```

   If hits return: contact the user, give them a deadline, defer DROP.

2. **Backup**: full IMDR DB backup verified restorable. The DROP is irreversible without a restore.

3. **Maintenance window**: dropping 420,050 rows + 4 tables is fast (seconds) but should land in a window where ingest is paused, so any nightly job that imports new cb_events isn't fighting for locks.

## Migration sketch

```sql
-- Migration ???_drop_legacy_calendar_tables.sql
-- (Phase H closeout — physical DROP of the 4 *_old tables renamed in migration 050.)
--
-- Pre-conditions:
--   * Migration 050 applied (tables suffixed _old).
--   * External-consumer check completed; no app reading these tables.
--   * Full DB backup verified.
--
-- Order of operations:
--   1. Drop the 3 FKs pointing OUT to active tables (dim_calendar, dim_vendor).
--      These exist because dim_market_calendar_old references the active
--      dim_calendar + dim_vendor. SQL Server requires the FK to be dropped
--      before the parent table can be dropped, but here the *parent* is
--      active — the constraint is on the *child* (the _old table).
--   2. DROP TABLE the 4 *_old tables. The intra-cluster FKs (between the
--      4 _old tables) cascade-drop when their parent tables drop.
--
-- Reversal: NONE. Restore from backup if needed.

-- Step 1: drop outward-pointing FKs.
ALTER TABLE [calendar].[dim_market_calendar_old]
    DROP CONSTRAINT FK_calendar_dim_market_calendar_calendar;
GO

ALTER TABLE [calendar].[dim_market_calendar_old]
    DROP CONSTRAINT FK_calendar_dim_market_calendar_vendor;
GO

-- Step 2: drop the 4 tables.
-- Order: children first, then parent dim_market_old.
DROP TABLE [calendar].[dim_market_calendar_old];
GO
DROP TABLE [calendar].[dim_market_currency_old];
GO
DROP TABLE [calendar].[dim_trading_day_old];
GO
DROP TABLE [calendar].[dim_market_old];
GO

-- Verification:
-- SELECT name FROM sys.tables
-- WHERE schema_id = SCHEMA_ID('calendar')
--   AND (name LIKE '%_old' OR name LIKE 'dim_market%' OR name LIKE 'dim_trading_day%');
-- expected: 0 rows.
```

## Why deferred

The original Phase H plan deferred this DROP **explicitly** as decision 3 of the country-anchor restructure (see [country_anchor_restructure_progress.md](country_anchor_restructure_progress.md)):

> rename old tables to `_old` in migration 050; physical DROP in a future release (number assigned at ship time).

Reasons:
- One release of stability gives external consumers time to discover that any query against the un-suffixed names is broken, with the `*_old` table still available as an emergency-unblock SELECT.
- 420,050 rows in `dim_trading_day_old` is real data. The dim itself is small but the trading-day grid has a year of pre-computed flags per market. If a consumer turns out to need it, recovery without backup-restore is impossible after the DROP.
- `MEMORY.md` hard rule: **NO DDL DROPS** without explicit authorization. The deferral keeps Block 5's release-day diff non-destructive.

## Estimated work

- 1 hour: external-consumer audit (query-log scan + Slack/email to anyone who hit the tables in the past month).
- 30 min: write + dry-run the DROP migration.
- 15 min: apply during maintenance window.
- 15 min: verify + update progress doc + migration guide (move "deferred to a later release" → "shipped").

Total: ~2 hours of focused work, spread across an audit cycle that depends on how quickly any external consumer responds.

## Pre-flight checklist (copy-paste when PM picks this up)

- [ ] Pull query-log hits for `calendar.dim_market*` and `calendar.dim_trading_day*` over the past month
- [ ] Reach out to any external consumer with hits; give them a deadline (suggested: 2 weeks)
- [ ] Confirm no remaining hits after the deadline
- [ ] Take + verify a full DB backup
- [ ] Schedule a maintenance window (ingest paused)
- [ ] Apply the DROP migration (sketch above)
- [ ] Run verification SQL (expect 0 `_old` tables remaining)
- [ ] Update `docs/admin/updates/2026-05-13_country-anchor-calendar-restructure.md` timeline ("Deferred" → "Just shipped")
- [ ] Update `docs/admin/development/country_anchor_restructure_progress.md` final-status line
- [ ] Delete this doc once the DROP ships

## Cross-references

- Rename migration: [`migrations/050_rename_legacy_calendar_tables.sql`](../../../migrations/050_rename_legacy_calendar_tables.sql)
- Consumer migration guide: [`docs/admin/updates/2026-05-13_country-anchor-calendar-restructure.md`](../updates/2026-05-13_country-anchor-calendar-restructure.md)
- Full restructure progress: [`country_anchor_restructure_progress.md`](country_anchor_restructure_progress.md)
- Original design rationale: [`docs/admin/country_anchor_design.md`](../country_anchor_design.md)
