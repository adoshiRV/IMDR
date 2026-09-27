# Business-critical — long-running post-ingest quality query on prod DB

- **Date filed**: 2026-07-17
- **Status**: open — fix in progress
- **Triggered by**: "Long Running Queries (Limit > 5 Minute)" monitor showed session 210 **suspended at 62 minutes** on prod. The query was the FX Rate pipeline's post-ingest `RobustStatisticalOutlierCheck` against `[fx].[fact_fx_rate]`.
- **Owner**: healthchecks / data-quality (shared `src/imdr/healthchecks/quality.py`)
- **Severity**: 🔴 **HIGH / business-critical** — a heavy analytical query runs on prod on the daily batch **and** every 3h (up to 9×/day on the largest fact table), contending with the ingest that just wrote the same table. Governed by the hard rule below.

> **HARD RULE (2026-07-17):** No long-running queries on the prod IMDR DB. Flag-only diagnostics belong OFF the ingest hot path. Any query surfaced by the >5-min monitor gets a HARD review, not a quick patch.

## TL;DR

The MAD-based outlier detector `RobustStatisticalOutlierCheck` (and the sibling `DistributionCheck`) in [`src/imdr/healthchecks/quality.py`](../../../src/imdr/healthchecks/quality.py) build a group median/MAD using the **windowed** form of `PERCENTILE_CONT`:

```sql
PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY [mid_rate]) OVER (PARTITION BY [pair_id],[tenor])
```

On SQL Server the windowed form does **not** collapse to one row per group — it emits a value for **every input row** and re-sorts the whole partition per row (which is why the code wraps each in `SELECT DISTINCT` to dedupe afterward). It is used **twice** per query (median, then MAD-of-abs-dev). Cost blows up superlinearly per partition, demanding a large memory grant + tempdb sort. Under concurrency with the ingest it goes `suspended` (waiting on memory grant / lock), which is the 62-minute observation.

Because the pattern lives in the **shared** check classes, every pipeline that runs post-ingest quality checks inherits it.

## Blast radius — scheduled consumers

| Sev | Pipeline | Scheduler | Fact table | Partition |
|---|---|---|---|---|
| 🔴 HIGH | `fx_rate_citi_live` **+ `_hourly`** ([`FXRatePipeline`](../../../src/imdr/domains/fx/pipeline_rate.py#L316)) | [`imdr_daily.py:41`](../../../scripts/imdr_daily.py#L41) **+ [`imdr_snapshots_citi.py:47`](../../../scripts/imdr_snapshots_citi.py#L47) every 3h → up to 9×/day** | `fx.fact_fx_rate` | `pair_id, tenor` |
| 🔴 HIGH | `rates_vol_citi_live` ([`RatesVolPipeline`](../../../src/imdr/domains/rates/pipeline_vol.py#L249)) | [`imdr_daily.py:39`](../../../scripts/imdr_daily.py#L39) | `rates.fact_swaption_vol` (~40k tags, heaviest feed) | `surface_id, option_expiry, swap_tenor` |
| 🔴 HIGH | `fx_vol_citi_live` ([`FXVolPipeline`](../../../src/imdr/domains/fx/pipeline_vol.py#L246)) | [`imdr_daily.py:40`](../../../scripts/imdr_daily.py#L40) | `fx.fact_vol` | `pair_id, strike, tenor, vol_type` (4-col) |
| 🟠 HIGH/MED | `cmdty_vol_citi_live` ([`CmdtyImpliedVolPipeline`](../../../src/imdr/domains/commodities/pipeline_vol.py#L204)) | [`imdr_daily.py:43`](../../../scripts/imdr_daily.py#L43) | `commodities.fact_implied_vol` | `commodity_id, strike, tenor` |

**Not currently scheduled** (would become HIGH if enabled): FX OHLC `_post_ingest_quality` ([`pipeline_ohlc.py:202`](../../../src/imdr/domains/fx/pipeline_ohlc.py#L202); bidfx hourly is commented out in `imdr_hourly.py`); all `imdr_clean.py` cleaning/validation scripts (the `RobustOutlierRule` correlated-subquery percentile in [`clean_implied_vol.py:137`](../../../src/imdr/domains/commodities/clean_implied_vol.py#L137) and every `DistributionCheck` call in `scripts/*/clean/` — some run **with no `where`**, scanning the full fact table).

## Two defects, one root cause

1. **The `PERCENTILE_CONT(...) OVER (PARTITION BY...)` antipattern** (perf). Findings above.
2. **The `where`-in-`trailing`-CTE bug** (correctness). The pipeline's run-window `where` (e.g. `AND obs_date BETWEEN start AND end`, [`pipeline_rate.py:299`](../../../src/imdr/domains/fx/pipeline_rate.py#L299)) is concatenated into the `trailing` CTE at [`quality.py:671`](../../../src/imdr/healthchecks/quality.py#L671), so the intended `DATEADD(MONTH, -trailing_months, ...)` baseline is intersected down to the narrow run window. The "6/12-month robust baseline" silently collapses to days → statistically meaningless **and** the reason the plan is unpredictable. Same shape recurs in `StatisticalOutlierCheck` and `PercentageChangeCheck`.
3. **(FX-rate only) no `frequency_id` scoping** — the trailing CTE mixes DAILY and HOURLY rows (the 3-hourly runner writes intraday rows to the same table), inflating the partitions the windowed percentile re-sorts.

## Grounding (2026-07-17, read-only)

- Session 210 has ended — no rows in `sys.dm_exec_requests`. No live fire.
- `fx.fact_fx_rate` ≈ **3.5M rows**, three frequencies pulled into the same `(pair_id, tenor)` partitions: `frequency_id=5` daily (2.58M, since 2007), `=4` hourly (671k, since 2026-04-23), `=2` (257k). The daily outlier check re-sorts the hourly rows too — direct partition inflation.

## The fix — decisions (2026-07-17)

**Note:** T-SQL has **no grouped `PERCENTILE_CONT` aggregate** — it exists *only* as the windowed `WITHIN GROUP ... OVER()` form. So "make it a GROUP BY aggregate" is not available. Chosen approach:

1. **Compute median/MAD/percentiles in pandas, not SQL.** The server does only a cheap indexed **range-scan SELECT** (no `OVER()`, no `SELECT DISTINCT` on large sets, no big memory grant / tempdb sort); all heavy stats move to the app tier. This aligns best with the hard rule (nothing heavy runs on prod) and matches the existing pandas rolling-MAD [`RobustOutlierRule`](../../../src/imdr/domains/fx/clean_fx_fact_fx_rate.py#L110). Applies to both `RobustStatisticalOutlierCheck` and `DistributionCheck`.
2. **Baseline = trailing N months, computed independently of the run-window `where`** (fixes the finding-2 collapse). Candidates to flag = the run-window rows. Concretely: pull the trailing baseline with its own date bound (`ts >= max_ts − trailing_months`), NOT intersected with the run window.
3. **Scope to a single frequency.** FX-rate consumer flags daily rows, so baseline + candidates must both be `frequency_id = 5` — hourly/other rows must not pollute the partition. Generic mechanism (e.g. a persistent `baseline_where`/frequency filter on the check).
4. **Hot-path policy: drop the outlier check from the 3-hourly (`imdr_snapshots_citi`) FX-rate path; keep it once/day on the daily path.** Hourly fires keep their cheap checks (positive / pct_change) only. (Chosen over "move fully offline" — daily per-ingest outlier flagging is still wanted.)

### Cost / risk

- Code-only change in the shared module + the FX-rate consumer + tests. No migration.
- Risk: MED — the pandas baseline pull transfers more rows (bounded by the trailing window + single-frequency scoping); verify the transfer volume is acceptable and the SELECT is a clean indexed range-scan. Correctness covered by `tests/unit/test_quality_robust.py` — extend it to (a) lock the trailing-window semantics so finding-2 can't regress and (b) assert no `PERCENTILE_CONT`/`OVER(` in any generated SQL.
- **Immediate mitigation**: the check is flag-only (non-essential to ingest); a stuck run is safe to kill.

## Checklist

- [ ] Ground the rewrite: read-only pull of table row counts + a query plan for the current SQL against `fact_fx_rate` (and confirm whether session 210 is still alive).
- [ ] Rewrite `RobustStatisticalOutlierCheck` SQL (set-based median/MAD; drop `where` from trailing CTE).
- [ ] Rewrite `DistributionCheck` SQL (same antipattern).
- [ ] Add `frequency_id` scoping to the FX-rate consumer.
- [ ] Decide + apply hot-path policy (relocate vs. keep) per scheduled consumer.
- [ ] Extend `tests/unit/test_quality_robust.py` — lock trailing-window semantics + assert no windowed-percentile in generated SQL.
- [ ] Plan-verify rewritten SQL against all four fact tables.
- [ ] Proper code review (`/code-review` or `imdr-code-reviewer`) before commit — business critical.
- [ ] File Linear issue under **IMDR** (`IMD-`), label `quality`/`fx`, link this doc. **(pending — Linear MCP not authorized this session; `imdr-pm` to sync.)**

## Related

- Memory rule: `feedback_no_long_running_prod_queries` (CRITICAL RULES).
- [`docs/admin/ops/quality_checks.md`](../ops/cleaning_framework.md) — flag-don't-block principle.
- [`docs/admin/development/quality_dispatch_helper.md`](quality_dispatch_helper.md) — adjacent quality-check refactor.
- [`docs/admin/fx/fx_overview.md`](../fx/fx_overview.md) — documents the two outlier implementations (SQL vs pandas).
