# Follow-up: BBG pipeline configs piggybacking on `fx.citi_rate`

- **Date filed**: 2026-05-19
- **Status**: deferred — affects `pipelines.yml` shape; needs DBM/config-owner review
- **Triggered by**: imdr-code-reviewer agent review of the FX walk (commit `a8e98c4`)

## The smell

[`src/imdr/domains/fx/pipeline_rate_bbg.py`](../../../src/imdr/domains/fx/pipeline_rate_bbg.py) (`__init__`):

```python
# Use Citi rate config for thresholds — it shares the target table
self._config = get_pipeline_config("fx.citi_rate")
```

`BloombergFXRatePipeline` (and its `BloombergFXRateDailyPipeline` subclass)
inherit *all* configuration — cleaning thresholds, health-check row-count
minimums, value ranges, max-staleness hours, date-column name — from the
`fx.citi_rate` config entry. There is no `fx.bloomberg_snapshot` or
`fx.bloomberg_daily` entry in `pipelines.yml`.

## Why this is a problem

The two pipelines write to the same table (`fx.fact_fx_rate`) but with
different `vendor_id` + `frequency_id`. Several config knobs make different
sense per vendor / cadence:

- **`row_count_min`** — Citi sees 209 rows/day at DAILY cadence; BBG sees
  ~209 rows × 6 snapshots/day = ~1,254 at SNAPSHOT cadence and ~209 at DAILY.
  Sharing the threshold means a sensible Citi value is wrong for at least
  one of the BBG fires.
- **`max_staleness_hours`** — Citi runs every 24h; BBG snapshot fires every
  ~4h. Same threshold can't be right for both.
- **`pct_threshold` / `n_mad` (cleaning)** — vendor-specific noise
  characteristics may diverge.

The current code masks the problem by sharing, but the moment Citi's
config is tuned for any of the above, BBG silently inherits a now-wrong
threshold.

## The fix

Add explicit entries to `pipelines.yml`:

```yaml
fx.citi_rate:
  table: fx.fact_fx_rate
  ...

fx.bloomberg_snapshot:
  table: fx.fact_fx_rate
  date_column: obs_date
  unique_columns: [pair_id, vendor_id, frequency_id, obs_ts, tenor]
  required_columns: [pair_id, obs_date, obs_ts, tenor, mid_rate]
  health_checks:
    row_count_min: 1000   # ~6 snapshots × ~209 rows
    max_staleness_hours: 5
    value_ranges: { ... }  # may inherit via yaml anchor if values match
  cleaning:
    pct_threshold: ...

fx.bloomberg_daily:
  table: fx.fact_fx_rate
  ...
  health_checks:
    row_count_min: 200
    max_staleness_hours: 26
```

Use YAML anchors (`&fx_rate_value_ranges` / `<<: *fx_rate_value_ranges`)
for the genuinely-shared sections so the duplication is honest and
short.

In code:

```python
class BloombergFXRatePipeline(BasePipeline[...]):
    pipeline_name = "fx.bloomberg_snapshot"
    ...
    def __init__(self, ...):
        ...
        self._config = get_pipeline_config(self.pipeline_name)
```

`pipeline_name` is already `"fx.bloomberg_snapshot"`, so the entire fix
is one yml edit plus one source line — once the yml structure is agreed.

## Coupling

Loop in `imdr-dbm` if `pipelines.yml` is treated as schema-controlled
(it should be — config drift is a hidden source of false-positive /
false-negative health-check fires).

## Effort

M — yml edits + per-entry threshold review (need empirical row counts
for BBG snapshot + daily fires from production audit log). Test sweep
is small (1-2 tests pinning `pipeline._config.pipeline_name`).
