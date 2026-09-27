# Curve arrival-pass drift check

Last updated: 2026-09-18

`scripts/rates/health/check_curve_arrival.py` — **which scheduled loader pass
actually built each curve's row, and has that drifted later than it used to
be?**

This is a different question from staleness. The staleness monitor
(`src/imdr/healthchecks/staleness.py`) asks whether the latest observation is
*old*; this asks *when in the day* it arrives. A curve can be perfectly fresh
— today's row, complete, every tenor — and still have moved from the 08:00
pass to the 14:00 pass, which is invisible to a freshness check and very
visible to anyone who looks at the data before lunch.

## Why it exists

A 2026-09-17 ops note reported that Citi's EUR basis curves had, "for the
third day running", arrived entirely on the 14:00 SGT pass "with nothing in
the 08:00 batch". Read off `rates.fact_observation.created_at`, curve 63
(`EUR 3S6S_BASIS`) had actually done this:

| value date | 08:00 pass | 14:00 pass | morning share |
|---|---|---|---|
| 2026-09-14 | 19 of 20 (08:21) | 1 (14:22) | 95% |
| 2026-09-15 | 5 of 20 (08:03) | 15 (14:23) | 25% |
| 2026-09-16 | — | 20 (14:03) | 0% |
| 2026-09-17 | 20 of 20 (08:03) | — | 100% |

A three-day deterioration that then recovered — not three days of absence.
The same note put USD `SOFR_FEDFUND_BASIS` (curve 66) in the "EUR basis
family", and asserted that "nothing runs after 09:15" when `IMDR_daily`
repeats every 6 hours from 08:01 and it was that task's 14:01 firing that
wrote the rows being complained about.

Three wrong claims in one note, all mechanically checkable. Hence this script:
run it and quote the output rather than reading `created_at` by hand.

## The model

**Passes.** Bucketed from the two Windows tasks that write this table:

| Task | Repeat | SGT hours |
|---|---|---|
| `IMDR_daily` | 6h from 08:01 | 08, 14, 20, 02 |
| `IMDR_snapshots_citi` | 3h from 23:00 | 23, 02, 05, 08, 11, 14, 17, 20 |

A load stamp is assigned to the latest scheduled hour at or before it, so a
retry at 16:21 rolls into the 14:00 pass.

**Passes are relative to the value date, in business days.** A Friday row
loaded Monday 02:27 and a Monday row loaded Tuesday 08:21 are both `B+1`. On
calendar offsets every curve would look two days drifted each weekend.

**The baseline is learned, and keyed on completion.** A series' expected pass
is the modal pass at which it reaches `--min-on-time`% of the day's rows, over
the window *excluding the newest value date* — so a run of bad days cannot
redefine "normal" as itself. Ties break to the earlier pass.

Completion rather than first arrival, because the two curve shapes differ:

- **Single-build** (basis swaps): one pass delivers the whole grid.
- **Progressive** (par / fwd curves on the 3-hourly snapshot task): EUR
  EURIBOR par lands ~8% of its 432 rows at 14:00 and finishes at 02:00 the
  next morning, *every day*. Keyed on first arrival it reads 8% on-time
  forever and the check is pure noise.

`created_at` is the first-arrival stamp — the loader upserts, so a re-run that
only rewrites a value moves `updated_at` instead. A delete-and-reload would
reset the history.

## Statuses

| Status | Meaning | Exit 1 |
|---|---|---|
| `LATE` | Newest value date completed later than baseline | yes |
| `INTERMITTENT` | Newest date is clean, but more than `--max-late-days` in the window finished late | yes |
| `BEHIND` | Missing the cohort's newest value date, and its baseline pass has already fired | yes |
| `PENDING` | Missing it, but this series' baseline pass has not fired yet | no |
| `SPARSE` | Fewer than 3 value dates — no baseline can be learned | no |
| `OK` | Completed on baseline | no |

`INTERMITTENT` is the one that matters most here. Run on 2026-09-18, EUR
`3S6S_BASIS` was back to a clean 100% on the 08:00 pass; judging on the latest
day alone would have printed "all clear" over exactly the multi-day pattern
the check exists to surface.

`PENDING` matters for the opposite reason: USD `SOFR_FEDFUND_BASIS` has a
genuine `B+1 14:00` baseline, so at 11:49 it is not late, it is not due.
Without that distinction every afternoon-arriving curve would flag every
morning and the check would be ignored by its second run.

## Usage

```bash
python scripts/rates/health/check_curve_arrival.py                        # active basis_swaps, 10d
python scripts/rates/health/check_curve_arrival.py --curve EUR.3S6S_BASIS --detail
python scripts/rates/health/check_curve_arrival.py --instrument swap_libor --quote par
python scripts/rates/health/check_curve_arrival.py --days 20 --tenors
python scripts/rates/health/check_curve_arrival.py --expect-pass "B+1 08:00"
```

| Flag | Default | Notes |
|---|---|---|
| `--days` | 10 | Value-date window, max 90 |
| `--curve CCY.CURVE` | — | Repeatable. Ignores the active-status filter, so ceased curves can be examined |
| `--instrument` | `basis_swaps` | Repeatable, active only |
| `--quote` | all | Repeatable |
| `--all` | off | Every curve, ceased included — pair with a short `--days` |
| `--expect-pass` | learned | e.g. `B+1 08:00`, `1@8` |
| `--min-on-time` | 90 | Share of a day's rows that defines "complete" |
| `--max-late-days` | 2 | Late dates tolerated before `INTERMITTENT` |
| `--detail` | off | Per-pass breakdown for every series, not just flagged ones |
| `--tenors` | off | Which tenors landed in which pass, for flagged series |

Exit 0 = every series completed on its baseline pass; 1 = something flagged,
or a bad argument / empty cohort.

**Scope guard.** This reads a 23M-row table on the production server, so the
default cohort is deliberately narrow and the aggregation is done server-side
(one row per curve × quote × value date × load stamp). `--all` over a long
`--days` is not a cheap query — see the no-long-running-prod-queries rule in
`docs/admin/ops/`.

## Not wired

Diagnostic only — run on demand. It is **not** registered in any
`imdr_*.py` scheduler.

Tests: `tests/unit/test_rates/test_curve_arrival.py` (27 cases, no DB). The
fixtures are real observed arrivals for curves 63 and 18, including the
progressive-build shape and the afternoon-baseline shape, because both have
already broken a draft of this checker.
