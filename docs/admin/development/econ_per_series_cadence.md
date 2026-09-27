# Per-series publication cadence for econ staleness

- **Date filed**: 2026-09-15
- **Status**: **HIGH PRIORITY** — not started. Design settled below; storage decision deferred (see *The one open decision*).
- **Triggered by**: building the India bank-credit fetchers (`docs/admin/econ/india/india_sectoral_credit.md`), which would be flagged stale from the day they land. The measurement below showed the problem is estate-wide, not specific to them.
- **Seeding decision already taken (2026-09-15)**: **leave NULL and fill on touch** — existing series fall back to a corrected per-frequency default; a series gets an explicit lag only when someone next touches its fetcher. No bulk empirical seeding pass.

## The problem, measured

`src/imdr/notifications/econ_snapshot.py` flags a series stale when
`today − MAX(obs_date) > _STALE_DAYS[frequency_code]`. The thresholds are keyed on
frequency alone, with the comment *"Staleness threshold = 2 × typical cadence, in days"*.

Measured against the live DB on **2026-09-15**:

| Frequency | Active series | Flagged stale | Of which, fetcher ran in last 14d | No ingest in 90d |
|---|--:|--:|--:|--:|
| MONTHLY | 1,565 | **1,148 (73%)** | 63 | 312 |
| QUARTERLY | 1,859 | 446 | 6 | 153 |
| DAILY | 307 | 175 | 29 | 60 |
| WEEKLY | 283 | 80 | 2 | 5 |
| ANNUAL | 432 | 59 | 0 | 21 |
| SEMIANNUAL | 12 | 4 | 0 | 4 |
| **Total** | **4,470** | **1,912 (43%)** | 100 | 555 |

Much of that is *genuine* staleness — built-but-unwired fetchers, discontinued upstream
series. That is the point: **the flag cannot distinguish a dead series from a healthy
lagged one**, so it carries no information either way.

The false-positive class is visible and unambiguous. Every alive-fetcher monthly series in
the list sits at **exactly 76 days behind**:

```
KOSTAT.RETAIL.SPECIALISED.VALUE.KR   76 days behind, ingested 14d ago
BOK.BOP.GOODS.EXPORTS.KR             76 days behind, ingested 10d ago
BLS.JOLTS.HIRES_RATE.US              76 days behind, ingested 10d ago
ABS.BA.HOUSES_UNITS_NSA.AU           76 days behind, ingested 14d ago
BPS.TRADE.IMPORT.TOTAL.USD.ID        76 days behind, ingested 10d ago
FRED.CREDIT.CONS_OUTSTAND.US         76 days behind, ingested  5d ago
...
```

All healthy. All current. Their latest print is the **July** reference month, dated
`2026-07-01` under the month-start `obs_date` convention; 2026-09-15 is day 76 of that
month. Threshold 60. Every one is a false positive, across five countries and five vendors.

## Root cause

`days_since_last_obs` conflates two quantities that need to be modelled separately:

1. the **period the observation covers** — implied by `frequency_code`, already handled; and
2. the **publication lag** before the next observation arrives — **not modelled at all**.

The "2 × cadence" rule was computed as if publication were instantaneous. Real monthly
macro publishes 4–8 weeks after the reference period, so a healthy month-start-dated
monthly series routinely sits 60–90 days behind.

**No frequency-only threshold can fix this.** Raise MONTHLY to ~100 and the 76-day cluster
stops firing — but a genuinely dead monthly series then hides for three months. The
dead-vs-lagged ambiguity is structural to keying on frequency.

## The fix

```
expected_next_arrival = last_obs_date
                      + period_length(frequency_code)        # have it
                      + publication_lag                      # per series, missing
                      + grace

is_stale = today > expected_next_arrival
```

`publication_lag` is a property of the **publisher's schedule**, not of our code, which is
why it belongs on the indicator. Fetcher authors know it at build time — e.g. RBI publishes
Sectoral Deployment for month *M* at the end of *M+1*, so `publication_lag_days = 31`.

Per the seeding decision: `publication_lag` is **nullable**, and NULL falls back to a
corrected per-frequency default that includes a realistic lag. Correcting those defaults is
part of this work, not a separate step — it is what carries the ~4,400 series nobody will
touch soon.

## The one open decision

Where the per-series value lives. Deferred deliberately; pick before starting.

| Option | Cost |
|---|---|
| **`publication_lag_days SMALLINT NULL` on `econ.dim_indicator`** (recommended) | DDL migration (drafted here, applied by the privileged DB account per `econ_to_prod.md` §G.4) + a new optional field on `IndicatorRow`, which every fetcher shares. Backward compatible — defaults to `None`, existing fetchers unchanged. Travels with the data, queryable in SQL, correct from a series' first print. |
| Code-side registry keyed by `imdr_code` prefix | No migration, ships immediately. But it is another hand-maintained layer that drifts from the data and is invisible to SQL — the failure mode the data-gap register keeps re-learning. |
| Derived empirically at snapshot time | No declaration anywhere and self-maintaining, but: needs a real per-run query (cuts against *no long-running prod queries*), is wrong for backfilled series where every observation arrived in one run, has nothing to go on for a series' first print, and a series broken for months quietly trains its own tolerance upward — the failure that matters most. |

## Two adjacent defects found while measuring

Both are small, both are prerequisites for doing this well, and both are worth fixing
regardless of which storage option wins.

1. **`release_date` is written as `now` by every fetcher checked**, so it duplicates
   `ingested_at` and the publisher's actual release date is nowhere in the database.
   Verified on `INDIA.CPI.YOY_LATEST.IN` and the `INDIA.FOODNOWCAST.*` family — identical
   timestamps, differing only by timezone rendering. This makes publication lag
   unrecoverable retrospectively and removes the obvious way to *validate* a declared lag.
   `scripts/econ/in/rbi/rbi_sectoral_credit.py` already parses the true publication date out
   of the RBI filename (`_release_date_from_name`) and then discards it — fix that one as
   the worked example.
2. **`econ.fact_indicator` has no spec in the cross-domain monitor.**
   `src/imdr/healthchecks/staleness.py` carries `DEFAULT_SPECS` for rates, FX and
   commodities but nothing for econ, so `econ_snapshot` is the only staleness path for
   4,470 series. That monitor already has per-spec `max_stale_days` and a `business_days`
   mode — the same family of problem solved at domain level. Converging the two is the
   right end state but is a larger rework, and the healthchecks subsystem is already flagged
   for redesign (`project_healthchecks_needs_rework`, Linear "Healthchecks subsystem
   redesign"). **Keep them separate for this piece of work**; note the convergence as a
   follow-on there rather than widening this.

## Checklist

- [ ] Decide storage (above)
- [ ] Correct `_STALE_DAYS` to include a realistic per-frequency publication lag — this is what serves every NULL series
- [ ] Add the per-series lag in whichever form is chosen; NULL → frequency default
- [ ] Rework `econ_snapshot.snapshot()` to the `period + lag + grace` model
- [ ] Update `tests/unit/test_staleness.py` and add cases for the lagged-but-healthy class (the 76-day cluster is the fixture to write)
- [ ] Fix `release_date` to carry the publisher's date where a fetcher can know it; start with `rbi_sectoral_credit.py`
- [ ] Re-measure the table above and record the new false-positive count here

## Related

- [`../econ/econ_to_prod.md`](../econ/econ_to_prod.md) §G.4 — schema additions land in two places (`schema.py` + `econ_snapshot.py`) and a migration is drafted, never auto-applied
- [`../econ/india/india_sectoral_credit.md`](../econ/india/india_sectoral_credit.md) — the build that surfaced this; its *Not wired* section carries the same decision scoped to those 82 series
- `src/imdr/notifications/econ_snapshot.py` — `_STALE_DAYS`, `snapshot()`
- `src/imdr/healthchecks/staleness.py` — the cross-domain monitor, econ absent
