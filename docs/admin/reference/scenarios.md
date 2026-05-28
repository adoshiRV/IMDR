# Scenario registry (`dbo.dim_scenario` + windows + tags)

PM-curated set of historical market-stress scenarios used to slice fact tables for scenario P&L and stress backtests. Created 2026-05-20 via [migration 053_create_dim_scenario.sql](../../../migrations/053_create_dim_scenario.sql); rows are populated by [scripts/migrations/seed_dim_scenario.py](../../../scripts/migrations/seed_dim_scenario.py).

Four tables, all in `dbo`:

| Table | Purpose |
|---|---|
| `dim_scenario` | One row per named scenario (e.g. *SVB / US regional bank crisis*). Carries the raw freetext `stress_focus_raw`. |
| `scenario_window` | One row per date range. Multi-range scenarios supported via `seq`. `end_date NULL` ⇒ open / "to live". |
| `dim_stress_tag` | Normalized lowercase tag dictionary derived from comma-splitting `stress_focus_raw`. |
| `scenario_stress_tag` | Bridge: scenarios ↔ tags. Rebuilt on every seed run. |

---

## Why both freetext and tags

`stress_focus_raw` stays on `dim_scenario` for human readability — the comma list maps directly to how the PM thinks about each event. The `dim_stress_tag` + bridge use a **curated canonical vocabulary** (not parsed from the freetext) so analytics queries can group cleanly:

```sql
-- All scenarios that touch FX
SELECT s.display_name
  FROM dbo.dim_scenario s
  JOIN dbo.scenario_stress_tag x ON x.scenario_id = s.id
  JOIN dbo.dim_stress_tag        t ON t.id = x.tag_id
 WHERE t.tag = 'fx';
```

### Canonical taxonomy (23 tags)

Tags live in [`CANONICAL_TAGS`](../../../scripts/migrations/seed_dim_scenario.py) and are organized on three axes:

- **Asset class**: `fx`, `rates`, `credit`, `equities`, `commodities`, `vol`
- **Theme**: `inflation`, `liquidity`, `duration`, `banking-stress`, `sovereign-stress`, `carry-unwind`, `risk-off`, `oil-shock`, `geopolitical`
- **Region**: `us`, `europe`, `uk`, `japan`, `china`, `asia-em`, `em`, `middle-east`

The mapping from scenario → tags is hand-curated in `SCENARIO_TAGS` in the same file. The seed validates that every used tag is in `CANONICAL_TAGS` and every scenario has at least one tag. To add a tag, add it to `CANONICAL_TAGS` first, then reference it in `SCENARIO_TAGS`.

---

## Window encoding rules

The PM source uses several date formats. The seed normalizes them all into concrete `start_date` / `end_date`:

| Source | start_date | end_date |
|---|---|---|
| `2024-08-05` (single day) | 2024-08-05 | 2024-08-05 |
| `2023-03-08 to 2023-03-24` | 2023-03-08 | 2023-03-24 |
| `2022-02-24 to live` | 2022-02-24 | NULL |
| `2022-01 to 2022-10` (month-only) | 2022-01-01 | 2022-10-31 |
| `2025-04 to 2025-Q2` (quarter end) | 2025-04-01 | 2025-06-30 |
| `2016-06-23 / 24` (consecutive days) | 2016-06-23 | 2016-06-24 |
| `… ; …` (two ranges) | one row per range, ordered by `seq` |  |

---

## Updating

Edit `SCENARIOS` in [scripts/migrations/seed_dim_scenario.py](../../../scripts/migrations/seed_dim_scenario.py) and re-run:

```bash
python -m scripts.migrations.seed_dim_scenario
```

The seed is idempotent — matched on `dim_scenario.display_name`. Windows are deleted and re-inserted on every run, so date corrections take effect immediately. Tags are likewise rebuilt.

To **deactivate** rather than delete an old scenario, manually `UPDATE dbo.dim_scenario SET is_active = 0 WHERE display_name = …` (the seed never sets `is_active = 0` automatically).

---

## Common queries

**Active scenarios overlapping a date range** (FX P&L example):

```sql
DECLARE @from DATE = '2023-01-01', @to DATE = '2023-12-31';

SELECT s.display_name, w.start_date, w.end_date
  FROM dbo.dim_scenario s
  JOIN dbo.scenario_window w ON w.scenario_id = s.id
 WHERE s.is_active = 1
   AND w.start_date <= @to
   AND (w.end_date IS NULL OR w.end_date >= @from)
 ORDER BY w.start_date;
```

**Join scenarios onto a fact table** (label every fact row with its active scenarios):

```sql
SELECT f.obs_date, f.pair_id, f.mid_rate, s.display_name AS scenario
  FROM fx.fact_fx_rate    f
  LEFT JOIN dbo.scenario_window w
         ON f.obs_date >= w.start_date
        AND (w.end_date IS NULL OR f.obs_date <= w.end_date)
  LEFT JOIN dbo.dim_scenario s
         ON s.id = w.scenario_id
        AND s.is_active = 1;
```

Note: a single date can fall inside multiple scenarios (e.g. SVB and Credit Suisse overlap mid-March 2023), so this query fans out rows. Aggregate with `STRING_AGG(s.display_name, ', ')` if a flat per-date label is wanted.
