# Tech Debt — Rates hourly cohort drifts silently from the universe

- **Date filed**: 2026-05-18
- **Updated**: 2026-05-19 — KRW.CD was not an isolated incident; the same drift affected **12 active curves**. All have been backfilled and 11 added to `DEFAULT_CURVES` (JPY.TONAR_JSCC excluded due to a separate vendor-side issue documented below).
- **Status**: open (the underlying structural drift is unaddressed; the per-curve symptom is patched)
- **Triggered by**: investigation into a KRW.CD hourly coverage gap (2026-05-06 → 2026-05-15). The gap turned out not to be a vendor change or a recent code change — it was caused by KRW.CD never being in the hourly script's hardcoded cohort, with the prior data having been loaded by ad-hoc manual runs.
- **Owner**: rates ingest
- **Severity**: 🟡 silent data-coverage drift; missed curves don't surface as errors

## TL;DR

[`scripts/rates/citi/rates_citi_live.py`](../../../scripts/rates/citi/rates_citi_live.py) (daily) derives its cohort from the universe:

```python
cohort = select_curves(universe.all_curves(), region)
```

[`scripts/rates/citi/rates_citi_live_hourly.py`](../../../scripts/rates/citi/rates_citi_live_hourly.py) (hourly) starts from a **hardcoded allowlist**:

```python
DEFAULT_CURVES: list[tuple[str, str]] = [
    ("USD", "SOFR"), ("EUR", "EUROSTR"), ...
]
candidate_entries = [universe.get_curve(ccy, curve) for ccy, curve in DEFAULT_CURVES]
```

Every new active curve added to [`src/imdr/universe/rates.yml`](../../../src/imdr/universe/rates.yml) is **automatically picked up by the daily runner**, but **silently absent from the hourly runner** until someone manually edits `DEFAULT_CURVES`. There is no comment warning about this in either file, no test asserting parity, and no email alert when an active universe curve is missing from intraday coverage.

The hourly runner currently emits a `coverage_gap` warning only for curves *in its cohort* that returned no data — curves *missing from the cohort* are invisible to the report.

## Full scope — 12 active curves affected, identified 2026-05-19

A follow-up DB sweep across every `frequency_id = HOURLY` row in `rates.fact_observation` against `rates.dim_curve` revealed that **KRW.CD was not unique** — eleven other active curves had identical symptoms (hourly data through 2026-05-05, nothing intraday after).

| curve_id | Curve            | Status   | Pre-cutoff last hourly | Post-cutoff backfill (rows) | In `DEFAULT_CURVES`? |
|----------|------------------|----------|------------------------|------------------------------|------------------------|
| 35       | KRW CD           | active   | 2026-05-05 09:00       | 6,016 (backfilled 2026-05-18) | ✓ added 2026-05-18    |
| 2        | USD FEDFUND      | active   | 2026-05-05 11:00       | 12,384                       | ✓ added 2026-05-19    |
| 22       | AUD BBSW         | active   | 2026-05-05 09:00       | 5,888                        | ✓ added 2026-05-19    |
| 18       | EUR EURIBOR      | reformed | 2026-05-05 11:00       | 6,144                        | ✓ added 2026-05-19    |
| 25       | NOK NIBOR        | active   | 2026-05-05 11:00       | 6,144                        | ✓ added 2026-05-19    |
| 26       | SEK STIBOR       | active   | 2026-05-05 11:00       | 6,144                        | ✓ added 2026-05-19    |
| 23       | NZD BKBM         | active   | 2026-05-05 07:00       | 5,888                        | ✓ added 2026-05-19    |
| 33       | IDR JIBOR        | active   | 2026-05-05 11:00       | 4,704                        | ✓ added 2026-05-19    |
| 34       | INR MIFOR        | reformed | 2026-05-05 11:00       | 5,824                        | ✓ added 2026-05-19    |
| 37       | PHP PHIREF       | active   | 2026-05-05 11:00       | 5,376                        | ✓ added 2026-05-19    |
| 39       | VND VND_REF      | active   | 2026-05-05 11:00       | 5,376                        | ✓ added 2026-05-19    |
| 8        | JPY TONAR_LCH    | active   | 2026-05-05 10:00       | 4,136                        | ✓ added 2026-05-19    |
| **7**    | **JPY TONAR_JSCC** | **active** | **2026-05-04 00:00** | **0 (vendor not serving)**  | **✗ — see below**    |

Total: 12 curves with the drift symptom. 11 backfilled and added to `DEFAULT_CURVES`. **JPY.TONAR_JSCC is a vendor-side problem, not a cohort drift**: the backfill request for that curve at HOURLY returned 0 rows and 72 tag_errors across all 8 BDs. Pre-cutoff data for this curve was already thin (1,006 rows Apr–May 5, started only 2025-05-05), suggesting Citi has been winding down HOURLY support for this CCP-specific OIS variant. Adding it to `DEFAULT_CURVES` today would just burn 72 tag-errors per fire with no payload, so it's excluded until either Citi resumes service or we re-source from another vendor.

This validates the structural-drift hypothesis from the original KRW investigation: the perfect 1-to-1 correspondence between "active curve not in `DEFAULT_CURVES`" and "active curve missing post-2026-05-06 hourly data" — with no false positives — means the prior ad-hoc historical-script runs were covering exactly the universe minus the hourly cohort, and they stopped on 2026-05-05.

## Ceased curves correctly absent (not part of this incident)

For the record, the following curves are also missing post-2026-05-06 hourly data but legitimately so (they were retired well before the cutoff):

| curve_id | Curve | Status | Last hourly | Reason |
|----------|-------|--------|-------------|--------|
| 24 | CAD CDOR        | ceased | 2025-02-21 | LIBOR cessation |
| 21 | CHF CHF_LIBOR   | ceased | 2025-02-21 | LIBOR cessation |
| 4  | EUR EONIA       | ceased | 2025-09-08 | replaced by ESTR |
| 19 | GBP GBP_LIBOR   | ceased | 2025-02-21 | LIBOR cessation |
| 20 | JPY JPY_LIBOR   | ceased | 2025-02-21 | LIBOR cessation |
| 27 | SGD SOR         | ceased | 2025-02-21 | replaced by SORA |
| 17 | USD LIBOR       | ceased | 2025-02-21 | LIBOR cessation |

## The original KRW.CD incident — preserved for context

DB query against `rates.fact_observation` for `curve_id=35` (KRW.CD, `RATES.SWAP_LIBOR.KRW`):

| Period                  | Coverage                                              |
|-------------------------|-------------------------------------------------------|
| through 2026-05-05      | Hourly snaps 08:00–19:00 KST, 64 tenors/hour (par+fwd)|
| 2026-05-06 → 2026-05-15 | Single 09:00 KST snap/day, 82 tenors (daily fire)     |
| 2026-05-15 onwards      | Same: single 09:00 KST daily snap                     |

A live probe of Citi's Historical Data API at HOURLY frequency for 2026-05-13 confirmed the vendor still serves intraday KRW data (12 hourly bars, 36 par + 28 fwd tenors). So the gap was on our side.

Git history was silent between 2026-04-23 and 2026-05-14, so the cutoff was not a code change. Three parallel forensic agents (git history, run logs, code-review) converged on:

1. KRW.CD has **never** been in `DEFAULT_CURVES` of the hourly script (since the script was added in commit `c72d5e0` on 2026-04-23). The omission has no comment or justification; every other active APAC IBOR/NDIRS curve is present.
2. The pre-cutoff hourly data was almost certainly loaded by ad-hoc runs of [`scripts/rates/citi/rates_citi_historical.py`](../../../scripts/rates/citi/rates_citi_historical.py), which passes `curves=None` to `RatesHistoricalPipeline` and therefore falls back to the **entire universe** at HOURLY frequency. The script's top-of-file knobs are edited in place and not committed, so there is no git record of which date ranges were backfilled.
3. The cohort filter ([`src/imdr/domains/rates/run_cohorts.py:select_curves`](../../../src/imdr/domains/rates/run_cohorts.py)) does *not* silently drop KRW — for `region="all"` and `region="asia"`, KRW.CD survives the filter. The omission is entirely upstream at `DEFAULT_CURVES`.

## What was done

**2026-05-18 — KRW.CD only:**
1. **Burner backfill** — [`playground/rates/backfill_krw_hourly.py`](../../../playground/rates/backfill_krw_hourly.py) loaded 6,016 rows of KRW.CD hourly data for 2026-05-06 → 2026-05-15 using `sp_client_id` / `sp_client_secret` (independent OAuth bucket). Idempotent via the MERGE upsert.
2. **Added `("KRW", "CD")`** to `DEFAULT_CURVES` in `scripts/rates/citi/rates_citi_live_hourly.py` under the existing APAC IBOR/NDIRS block.

**2026-05-19 — remaining 11 curves:**
1. **Burner backfill** — [`playground/rates/backfill_intraday_drift_gap.py`](../../../playground/rates/backfill_intraday_drift_gap.py) loaded 68,008 rows across 11 curves for 2026-05-06 → 2026-05-15. JPY.TONAR_JSCC returned 0 rows (vendor-side issue documented above).
2. **Added 11 curves** to `DEFAULT_CURVES`: USD FEDFUND (new "US OIS" mini-block), AUD BBSW + EUR EURIBOR + NOK NIBOR + NZD BKBM + SEK STIBOR (new "G10 IBOR" block), JPY TONAR_LCH (new "CCP OIS" block with JSCC excluded comment), and IDR JIBOR + INR MIFOR + PHP PHIREF + VND VND_REF (added to existing APAC IBOR/NDIRS block).
3. **Updated docstring** to reflect new totals (30 curves) and revised budget (~49K tags/day, ~52% of the hourly OAuth client's 95K cap).

These changes address **the specific 12-curve symptom**, but they do **not** fix the underlying structural drift — see the next section.

## The structural problem (this doc's actual subject)

`DEFAULT_CURVES` is a hardcoded list with no enforcement that it matches the set of active intraday-eligible curves in the universe. The two intraday-eligible categories today are RFRs and APAC IBOR/NDIRS, both of which are inferrable from `rates.yml` (`type: rfr` or `type: ibor` with status `active`, optionally restricted to a configured intraday region). The hourly script doesn't query that — it just reads its own hardcoded list.

### Concrete failure modes

- **Future currency additions**: a new APAC IBOR added to `rates.yml` (say IDR THBFIX or PHP PHIREF) will land in the daily runner immediately and the hourly runner *never*, until someone notices the asymmetry.
- **Status flips**: if a currently-ceased curve in `DEFAULT_CURVES` becomes active again in `rates.yml`, the hourly will try to fetch it. If the reverse — a curve in `DEFAULT_CURVES` gets marked `status: ceased` in `rates.yml` — the hourly may keep requesting it and burning quota.
- **Universe deletes**: if a curve in `DEFAULT_CURVES` is removed from `rates.yml`, `universe.get_curve(ccy, curve)` raises and the whole hourly run dies, taking down all the other active curves' intraday coverage as collateral.

### What the report doesn't tell you

The hourly script's `coverage_gap` warning only fires for curves **in the cohort** that produced no data. Curves silently absent from the cohort produce no rows, no warning, no email line. The only way to detect the drift today is to compare the universe against `DEFAULT_CURVES` by hand — which is exactly what failed in the KRW.CD case.

## Options for the fix

These are not mutually exclusive. Listed roughly cheapest → most invasive.

1. **Add a parity test.** A unit test that asserts every active universe curve whose `type` is in `{rfr, ibor}` and whose classification matches a region in `INTRADAY_REGIONS` appears in `DEFAULT_CURVES`. CI catches the omission on the next universe edit. ~1 hour. Doesn't change runtime behavior, just makes drift loud.
2. **Derive `DEFAULT_CURVES` from the universe.** Replace the hardcoded list with a function that filters `universe.all_curves()` by an `intraday: true` (or equivalent) field on each curve in `rates.yml`. New additions opt in via the universe file alone. The hardcoded list goes away. ~half a day. Requires schema addition to `rates.yml` and migration of the existing list into yml flags.
3. **Add a coverage-drift email line.** At end of each hourly run, log universe-minus-cohort actively-published curves not pulled today. Pure observability — doesn't fix the structural issue but makes it visible.

A reasonable bundle is (1) + (3): cheap, low-risk, and gives both static (CI) and runtime (email) signals. (2) is the proper fix but worth doing alongside the next time the universe schema is touched.

## Related

- `docs/admin/development/rates_hourly_classify_missing_equity_proxy.md` — adjacent bug in the same script (`_classify_missing` uses equity-exchange hours as a proxy for rates publish state). Same locus of code; could be fixed in the same pass.
- `docs/admin/development/rates_run_cohorts.md` — describes the `select_curves` design that the daily runner relies on. The structural fix here is to make the hourly use the same upstream selection.
