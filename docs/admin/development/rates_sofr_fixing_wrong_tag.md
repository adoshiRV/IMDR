# Follow-up: USD MONEY_MARKETS fixings (SOFR + LIBOR) are un-ingested

- **Date filed**: 2026-05-14 (SOFR), 2026-05-15 (LIBOR added)
- **Status**: deferred
- **Triggered by**: LIBOR→RFR conversion prototype (`playground/libor_to_rfr/`)
  surfaced gross errors in USD compounded SOFR for stress periods. Follow-up
  probes confirmed the same root cause affects USD LIBOR fixings: we ingest
  the **swap curve** (`RATES.SWAP_LIBOR.USD`), not the **published fixing**
  (`RATES.MONEY_MARKETS.USD.LIBOR.3M.MM_LIBOR_FIXING`). Both fixings live in
  the Citi `MONEY_MARKETS` tree that we don't currently ingest from at all.

## Problem 1 — USD SOFR ingest pulls the OIS curve, not the published fixing

`rates.dim_curve.id=1` is the row labelled USD `SOFR` (curve_type `rfr`).
Its `citi_prefix` is `RATES.OIS.USD_SOFR` — that's the **OIS swap curve**.
The `tenor='1D'` slot of that curve is the curve's overnight point, which
is **curve-implied** (a stale or forecast value) rather than the actual
published NY Fed SOFR fixing.

The published fixing lives at a different Citi tag entirely:
`RATES.MONEY_MARKETS.USD.SOFR.ON`. That tag is **un-ingested** — zero
references in `src/imdr/`, zero references in `scripts/`, zero rows
in `fact_observation` that came from it.

### Evidence — Sept 2019 repo squeeze

| Date       | NY Fed SOFR | `dim_curve.SOFR` tenor `1D` (our DB) | `MONEY_MARKETS.USD.SOFR.ON` (probed) |
|------------|------------:|--------------------------------------:|--------------------------------------:|
| 2019-09-13 | 2.20        | 2.5                                   | 2.20 ✓                                 |
| 2019-09-16 | 2.43        | 2.5                                   | 2.43 ✓                                 |
| 2019-09-17 | **5.25**    | **2.5**                               | **5.25** ✓                             |
| 2019-09-18 | 2.55        | 2.5                                   | 2.55 ✓                                 |
| 2019-09-19 | 1.90        | 2.5                                   | 1.95 ✓ (5 bp diff, publication rounding) |
| 2019-09-20 | 1.90        | 2.5                                   | 1.86 ✓                                 |

The DB value is flat `2.5` through the entire repo squeeze — that's the
upper bound of the Fed Funds target range. It misses the 5.25% spike
entirely. Any analytics, conversion, or backtest that depends on
"compounded SOFR" since 2019-07-01 currently uses curve-implied data
that diverges materially from the published rate during stress periods.

Additionally the first 4 business days of the DB SOFR series
(2019-07-01 .. 2019-07-05) are `0.0` — junk.

## Scope of the problem

Only USD. Confirmed by direct probe across stress windows:

| Currency | Our `RATES.OIS.{ccy}.{rfr}` tenor `1D` |
|----------|-----------------------------------------|
| USD      | **Broken** — curve-implied, misses Sept 2019 spike |
| GBP SONIA | OK — moves on Mar 2020 emergency cuts                |
| CHF SARON | OK — moves on Mar 17 2020 emergency cut              |
| JPY TONA  | OK — moves on rate-cut days                          |

`RATES.MONEY_MARKETS.{ccy}.{rfr}.ON` tags do **not exist** for GBP / CHF / JPY
under that tree (only LIBOR fixings live there). The SOFR anomaly is
specifically a SOFR-publication-lag artifact: SOFR is published next-business-day
at 8 am NY, so the OIS curve uses a forecast/upper-bound until the fixing lands.
SONIA / SARON / TONA publish same-day, so the OIS curve `1D` IS the fixing in
real time for those.

## Problem 2 — USD LIBOR fixings differ from `SWAP_LIBOR.par` on stress days

The same `RATES.MONEY_MARKETS.*` tree carries the **canonical published LIBOR
fixings** at `RATES.MONEY_MARKETS.{ccy}.LIBOR.{tenor}.MM_LIBOR_FIXING`, with
tenors ON / 1W / 2W / 1M / 2M / … / 1Y. None of these are ingested. What we
*do* have (`dim_curve.LIBOR / GBP_LIBOR / CHF_LIBOR / JPY_LIBOR`, citi_prefix
`RATES.SWAP_LIBOR.{ccy}`) is the LIBOR-discounted **swap curve**, where the
sub-1Y `par` quotes are conceptually the LIBOR fixing but actually a
curve-calibrated value.

For GBP / JPY / CHF this almost never matters — the swap-curve par and the
published fixing match to floating-point. For **USD it materially diverges on
stress days**:

| Date | DB `SWAP_LIBOR.USD` 3M `par` | `MM_LIBOR_FIXING` USD 3M | Diff (bp) |
|---|---:|---:|---:|
| 2015-12-16 (Fed liftoff)        | 0.538417 | 0.532500 | +0.6  |
| 2018-12-19 (Fed final hike)     | 2.789630 | 2.789630 |  0.0 ✓ |
| 2020-03-09 (COVID panic)        | 0.785200 | 0.768130 | **+1.7** |
| 2020-03-16 (post-Fed 0% cut)    | 0.909144 | 0.889380 | **+2.0** |
| 2021-06-01 (quiet)              | 0.131356 | 0.128500 | +0.3  |
| **2022-07-27 (Fed 75 bp hike)** | 2.866860 | 2.805860 | **+6.1** |
| **2023-06-30 (cessation day)**  | 5.679880 | 5.545430 | **+13.4** |

Same pattern as SOFR — Citi's swap-curve calibration drifts from the actual
ICE fixing when the market is moving fast. USD 3M was the most-referenced
LIBOR series in the world; the cessation-day fixing is wrong by 13 bp in
our DB. GBP / CHF / JPY were spot-checked and match to 6 decimals on the
same probe (CHF has a single ~1.7 bp deviation on Mar-19-2020, otherwise OK).

### Scope of problem 2

| Currency / Tenor | DB `SWAP_LIBOR.par` vs published `MM_LIBOR_FIXING` |
|---|---|
| **USD 3M** | **Diverges on stress days, up to +13 bp** |
| USD other tenors (1W/1M/2M/6M/12M) | Untested, likely similar pattern |
| GBP 3M | Matches exactly (6/6 probed dates) |
| JPY 6M | Matches within 0.1 bp |
| CHF 3M | Matches except Mar-19-2020 (1.7 bp) |

`SWAP_LIBOR` is still the right source for the multi-year swap curve
(3Y / 5Y / 10Y par swaps against LIBOR floating). The bug is only that the
**sub-1Y par points are being used as if they were the LIBOR fixing**.

## Fix recommendations

Both problems share a root cause: the `RATES.MONEY_MARKETS.*` Citi tag tree
is not wired into any ingest path. A single MONEY_MARKETS-routed connector
can backfill both fixing types in one pass.

### Tags to ingest

| Purpose | Citi tag pattern | Coverage |
|---|---|---|
| **Published SOFR fixing** | `RATES.MONEY_MARKETS.USD.SOFR.ON` | 2018-04-03 → present |
| **Published LIBOR fixings** | `RATES.MONEY_MARKETS.{ccy}.LIBOR.{tenor}.MM_LIBOR_FIXING` for `ccy ∈ {USD,GBP,CHF,JPY}` and `tenor ∈ {ON,1W,2W,1M,2M,3M,4M,5M,6M,7M,8M,9M,10M,11M,1Y}` | 2015-06-01 → cessation date per ccy |

LIBOR cessation dates already in `dim_curve.cessation_date`: CHF/JPY 2021-12-31,
USD 2023-06-30, GBP 2024-03-28. Backfill end-date should respect those.

### Schema actions

1. **New `dim_curve` row for SOFR fixing** — do *not* retrofit id=1:

   | ccy | curve         | curve_type | citi_prefix                         |
   |-----|---------------|------------|--------------------------------------|
   | USD | `SOFR_FIXING` | `rfr`      | `RATES.MONEY_MARKETS.USD.SOFR.ON`    |

   Leave existing `SOFR` (id=1) untouched so OIS-curve consumers (rates-pipeline
   curve builders, vol pipelines, etc.) keep working — they want the
   curve-implied O/N number.

2. **New `dim_curve` rows for LIBOR fixings** — separate from `SWAP_LIBOR`:

   | ccy | curve              | curve_type | citi_prefix                                        |
   |-----|--------------------|------------|----------------------------------------------------|
   | USD | `USD_LIBOR_FIXING` | `ibor`     | `RATES.MONEY_MARKETS.USD.LIBOR` (tenor in path)    |
   | GBP | `GBP_LIBOR_FIXING` | `ibor`     | `RATES.MONEY_MARKETS.GBP.LIBOR`                    |
   | CHF | `CHF_LIBOR_FIXING` | `ibor`     | `RATES.MONEY_MARKETS.CHF.LIBOR`                    |
   | JPY | `JPY_LIBOR_FIXING` | `ibor`     | `RATES.MONEY_MARKETS.JPY.LIBOR`                    |

   Leave the existing `LIBOR / GBP_LIBOR / CHF_LIBOR / JPY_LIBOR` curves
   (with `RATES.SWAP_LIBOR.*` prefix) for their original purpose — the
   multi-year LIBOR-discounted swap curve. Anything ≥2Y is real swap data
   and isn't affected by this bug.

3. **Bad-data cleanup in existing `SOFR` curve**: delete or skip-on-insert
   the rows for 2019-07-01 .. 2019-07-05 with `value=0.0`. They are wrong
   even for the curve-O/N interpretation (the curve cannot be 0% with
   positive rates everywhere else).

### Migration impact

None if new `dim_curve` rows are added (recommended). If existing rows are
retrofitted instead, every consumer that pulls `tenor='1D'` from `SOFR` or
`tenor IN ('1W','1M','2M','3M','6M','1Y')` from `LIBOR / GBP_LIBOR / …`
needs an audit — values would change shape on stress days, breaking any
saved snapshots or hash-based reproducibility.

## Playground workaround

While this task is deferred, `playground/libor_to_rfr/` already fetches
`RATES.MONEY_MARKETS.USD.SOFR.ON` directly from Citi and caches it to
`playground/libor_to_rfr/data/sofr_fixings.parquet`. The conversion
prototype's USD SOFR output uses that parquet instead of the DB curve.

The USD LIBOR fixing problem currently has **no playground workaround**.
The prototype still uses `RATES.SWAP_LIBOR.USD` `par` values, which are
correct in calm periods and biased a few bp on stress days (up to 13 bp
on cessation day). If the bias matters for what the prototype is being
used for, the same fetcher pattern as `fetch_citi_sofr.py` can be used —
just call `MM_LIBOR_FIXING` per (ccy, tenor) and cache to parquet.

## Done when

### SOFR fix
- [ ] New `dim_curve` row `SOFR_FIXING` for published SOFR fixing
- [ ] Backfill 2018-04-03 → present from `RATES.MONEY_MARKETS.USD.SOFR.ON`
- [ ] Bad-data cleanup or skip-on-insert for the 0.0 rows 2019-07-01..05
- [ ] LIBOR→RFR converter switched off the playground parquet onto the new DB curve

### LIBOR fixings
- [ ] New `dim_curve` rows `{USD,GBP,CHF,JPY}_LIBOR_FIXING`
- [ ] Backfill `RATES.MONEY_MARKETS.{ccy}.LIBOR.{tenor}.MM_LIBOR_FIXING`
      for the 15 published tenors per ccy, from 2015-06-01 (or earlier if
      Citi has it) to each ccy's `cessation_date`
- [ ] LIBOR→RFR converter switched off `SWAP_LIBOR` par onto the new fixing curves
- [ ] Spot-check: re-probe the USD 3M stress-day table above against the new
      DB rows; expect zero divergence from `MM_LIBOR_FIXING`
