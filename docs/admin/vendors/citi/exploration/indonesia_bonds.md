# Citi Velocity — Indonesia Bonds & IDR Rates: Availability Probe

- **Probed**: 2026-10-12
- **Probe script**: `playground/bonds/probe_indonesia.py` (5 steps: `discover`, `measures`, `bonds`, `validate`, `swaps`)
- **Cache**: `data/cache/rates/idn_isin_citi_probe.json`, `data/cache/rates/idr_swap_5y.json`
- **Trigger**: a Citi Velocity UI screenshot showing INDOGB / INDOIS / INDORI bonds with ISINs under *Rates → Bonds*, which contradicted the standing "zero APAC EM bond coverage" verdict.

---

## Headline

Two findings, pulling in opposite directions:

1. **The bond namespace exists and accepts Indonesian ISINs.** `RATES.BOND.{ISIN}.{MEASURE}` is a real, dynamically-keyed namespace with 40 measures per bond. 22 of 26 INDOGB bonds return ~5 years of daily history. This **corrects** [`bonds_full.md`](bonds_full.md), whose "zero APAC EM bond coverage" verdict rested on enumeration alone and could not see this namespace.

2. **That bond data must not be used as a market mark.** It fails cross-vendor validation outright: it sits below Bloomberg/BQL on *every* bond and its daily changes are uncorrelated with the market (median r = +0.018). The curve *looks* plausible in levels, which is exactly what makes it dangerous.

**The usable Indonesian curve on Citi is `RATES.SWAP_LIBOR.IDR.*`** — 11,294 tags, 29 par tenors (1M–50Y), 1,219 daily points back to 2021-10-13, and levels that corroborate against Bank Indonesia's own SRBI auction yields.

---

## Why enumeration missed this

The three discovery endpoints disagree, and only one of them is authoritative:

| Prefix | `tagbrowsing` | `taglisting` | `fetch_historical` |
|---|---|---|---|
| `RATES.SOV.CMT.USA.10Y.YIELD` | OK | OK | data |
| `RATES.SOV_CMT.USA.10Y.YIELD` | ERROR | 0 tags | data (hidden alias) |
| `RATES.BOND.{ISIN}.YIELD` | `invalid prefix` | template only | **data** |
| `RATES.ZZZZ.ZZZZ.YIELD` | ERROR | 0 tags | `Bad tag` |

`fetch_tagbrowsing("RATES")` returns 24 sub-categories with **no `BONDS` node** — the UI's *Rates → Bonds* panel is a security-level browser, not a branch of the charting tree. But `fetch_taglisting("RATES.BOND.")` returns a **template** carrying the literal placeholder `<ISIN>`:

```
RATES.BOND.<ISIN>.YIELD
RATES.BOND.<ISIN>.PRICE
...40 measures
```

**Rule of thumb**: `tagbrowsing`/`taglisting` enumerate the *browsable* tree. Only `fetch_historical` can prove a tag's existence, because it discriminates a real-but-unlisted tag (`type: SERIES`) from a non-existent one (`type: ERROR`, `Bad tag: ...`). A dynamically-keyed namespace accepts any identifier without erroring — `RATES.BOND.ZZQQXX999.YIELD` returns an empty `SERIES`, not `Bad tag`.

### The 40 measures per ISIN

```
YIELD  YIELD_MAT  YIELD_NEXT  YIELD_WORST  SIMPLEYIELD  PRICE  PRICING_ACCRUED
DURATION  DV01  CONVEXITY  PRICING_CV01
ASW_RFR  ASW_4_{AUD,CHF,EUR,GBP,JPY,USD}  ASSNP_RFR  CAS_RFR  OAS_RFR  ICAS  BES
OISS_RFR  OISSMM_RFR  YYS_RFR  SPREAD_SWAP  SPREAD_TSY
CARRY.{1M,3M,6M,1Y}  ROLL.{1M,3M,6M,1Y}  ROLLCARRY.{1M,3M,6M,1Y}
```

For INDOGB only `YIELD` and `PRICE` populate; the other 38 return empty.

---

## The bond data fails validation

ISINs came from the Govy Monitor SQLite (`Z:\Business\Research\Dashboard\Govy Monitor\BBG.Yield.DB`, `country_code='INDOGB'`, read-only copy). 22 of 26 returned data; the 3 `IDQ*` treasury bills (INDOBL) returned empty, so **T-bills are not covered — INDOGB `IDG*` bonds only**.

Citi vs BQL on common dates, 20 bonds with ≥40 overlapping days:

| Horizon | Median correlation of changes |
|---|---|
| Daily | **+0.018** |
| Weekly | −0.048 |
| Monthly | **−0.193** |

A genuine mark converges toward +1 as the horizon lengthens. This one *falls*. Bonds with daily r > 0.5: **0 of 20**. The +0.79 level-on-level correlation is spurious — both series share a slow trend.

The level bias is negative on every single bond, widening sharply at the short end:

| Bond | Tenor | BQL | Citi | Diff |
|---|---|---|---|---|
| FR42 10¼ 07/15/27 | 1.0y | 7.352 | 5.113 | **−224 bp** |
| FR59 7 05/15/27 | 0.75y | 6.804 | 5.313 | −149 bp |
| FR95 6⅜ 08/15/28 | 2.0y | 6.893 | 5.841 | −105 bp |
| FR93 6⅜ 07/15/37 | 10.9y | 7.281 | 6.734 | −55 bp |
| FR89 6⅞ 08/15/51 | 25.0y | 7.313 | 6.960 | −35 bp |

### Ruled out

- **Not a yield-convention difference.** Citi's `YIELD` is internally consistent with Citi's own `PRICE`; `YIELD_MAT`/`YIELD_WORST`/`SIMPLEYIELD` are all empty. A convention difference would still co-move.
- **Not staleness.** A lag scan over ±150 days found no consistent lag — best fits differ per bond (+15d, −35d, −45d) with weak r, consistent with noise-mining across 61 tested lags.
- **Not BQL being wrong.** Bank Indonesia's SRBI auction yields settle it independently: SRBI 12M printed **7.369%** on 2026-08-14. BQL's 0.75y INDOGB at 6.804% sits plausibly below it; Citi's 5.313% would be 206bp *through* the 12-month BI bill. Directionally too, SRBI 12M rose 6.45% → 7.64% (May → July 2026) and BQL followed; Citi's same-bond series *fell* over that window.

**Do not build an Indonesian government curve from `RATES.BOND.*`.** This is the same failure mode as the synthetic Citi APAC long end (`10s30s` constant on CNY/CNH/AUD/INR/PHP/MYR).

---

## What *is* usable: `RATES.SWAP_LIBOR.IDR.*`

11,294 tags — a branch absent from the 2026-05-25 bonds sweep entirely.

```
RATES.SWAP_LIBOR.IDR.PAR.{TENOR}                  # 29 par tenors, 1M -> 50Y
RATES.SWAP_LIBOR.IDR.FWD.{START}.{TENOR}
RATES.SWAP_LIBOR.IDR.CURVES.{T1}.{T2}
RATES.SWAP_LIBOR.IDR.BFLY.{T1}.{T2}.{T3}
RATES.SWAP_LIBOR.IDR.ROLL_CARRY.{TENOR}.{CARRY|ROLL|TOTAL_CARRY}
```

Par curve: **1,219 daily points, 2021-10-13 → 2026-10-09** — the full 5 years, every tenor.

| Tenor | Latest | uniq% | flat days | median \|Δ\| |
|---|---|---|---|---|
| 1M | 6.507 | 99.3% | 0.2% | 2.08 bp |
| 1Y | 6.657 | 86.3% | 4.6% | 1.85 bp |
| 2Y | 6.740 | 99.8% | 0.0% | 1.71 bp |
| 5Y | 6.994 | 80.9% | 4.9% | 2.25 bp |
| 10Y | 7.210 | 76.9% | 5.4% | 2.10 bp |
| **15Y** | 7.196 | 69.8% | **10.3%** | 1.20 bp |
| **20Y** | 7.188 | 62.4% | **13.1%** | 1.00 bp |
| 30Y | 7.181 | 98.8% | 0.4% | 1.97 bp |
| 50Y | 7.177 | 99.3% | 0.2% | 2.69 bp |

**Corroboration**: IDR 1Y par swap = 6.657% against BI's SRBI 12M = 6.600% on the same date (2026-10-09). The curve shape is sane throughout — a shallow dip through 2M–5M, then a monotonic rise to a 10Y–12Y peak and a flat-to-marginally-inverted tail.

**Caveat**: 15Y and 20Y carry 10–13% unchanged days — mild stickiness, the same smell as the synthetic APAC long end, though far less severe than the bond series. 25Y/30Y/40Y/50Y are clean. Treat 15Y/20Y with care; prefer interpolating from 12Y and 25Y for anything that trades.

---

## Full Indonesia coverage on Citi

| Branch | Tags | Verdict |
|---|---|---|
| `RATES.SWAP_LIBOR.IDR.*` | 11,294 | **Usable** — 5y daily, par/fwd/curves/bfly/roll-carry |
| `FX.VOL.*IDR*` | 5,014 | Available (not validated here) |
| `FX.FORWARD.*IDR*` | 439 | Outright / point / pip, incl. IMM |
| `FX.SPOT.*IDR*` | 62 | 31 IDR-base + 31 IDR-quote |
| `RATES.BOND.{IDG*}` | 22 bonds | **Present but fails validation — do not use** |
| `ECONOMICS.SURPRISE_INDEX.*ID*` | 99 | Citi surprise indices |
| `ECONOMICS.{NEER,REER}_IDX.IDR` | 5 | Effective exchange rates |
| `ECONOMICS.EC_EMASIA_FCI.IDR` | 1 | EM Asia financial conditions |
| `RATES.OIS.*IDR*` | 0 | Absent |
| `RATES.XCCY_SWAP.*IDR*` / `XCCY_OIS_SWAP` | 0 | Absent |
| `RATES.FRA.*IDR*` | 0 | Absent |
| `CREDIT.SOV_CDS.*INDO*` | 0 | Absent — sovereign CDS is DM-only (21 names) |

`RATES.BOND.{ISIN}` is issuer-agnostic, so the same namespace should be re-probed for other APAC EM government bonds (KTB, MGS, THAIGB, RPGB, IGB) — but **every one must pass the same cross-vendor validation before use**.

---

## Notes for an ingest design

- **The namespace is bring-your-own-ISIN.** It cannot be enumerated by issuer, so any pipeline needs an external ISIN master. `dbo.dim_bond_instrument` already holds that shape (ISIN, bbg_ticker, issuer_code, maturity) but currently covers only IGB (20) and KTB (12) — no Indonesia.
- **Quota**: data fetches count against the 100K tag/24h budget *and* a separate per-tag 10-call/24h cap that the tracker cannot see. The probe caches every raw response so `validate` re-reads rather than re-fetches.
- **Encoding**: INDOGB descriptions carry vulgar fractions (`10⅜`) that crash cp1252 console output. Persist the response *before* printing, and normalise with NFKD for display.

---

## What was loaded (2026-10-12)

Both gates cleared by the user ("LOAD all of it … register the tasks into the daily").

### 1. INDOGB bonds — via Govy/BQL, **not** Citi

Citi's per-ISIN bond feed was rejected on the validation evidence above. The ISIN-grain
load runs off the Govy Monitor store instead (Track B in
[`../../../development/govt_bond_population.md`](../../../development/govt_bond_population.md)),
widened from the IGB+KTB pilot to **all 12 issuers**:

- **INDOGB: 25 bonds / 4,106 observations**, 2025-12-19 → 2026-08-13.
- 235 instruments / 24,390 obs / 221 auctions total, 0 skipped.
- Registered in `scripts/imdr_daily.py`.

> **Indonesia is stale at source.** The Govy store itself stops at 2026-08-13 for
> INDOGB (and UST) while the other ten issuers run to 2026-10-06. Nothing in IMDR
> will fix that — it needs the desktop app to resume, and a StaleCheck so it is
> never again discovered by accident.

### 2. IDR swap curve — full depth backfilled

The probe above used a 5-year window; the **real history goes back to 2008-01-02**.
The DB had been sitting on an artificial 2015-06-01 floor — the same fake floor
recorded for the G10 OIS curves.

`rates_citi_historical.py` run for `IDR.JIBOR`, quotes `par,spread,fwd,bfly`,
2008-01-02 → 2026-10-09: **+362,704 rows**. Curve 33 now holds **784,160 rows,
2008-01-02 → 2026-10-12**.

| Quote | Was | Now (daily lane) |
|---|---|---|
| `par` | 2015-06-01 | **2008-01-02** |
| `fwd` | 2020-01-02 | **2008-01-02** |
| `spread` | 2026-04-09 | **2008-01-02** |
| `bfly` | 2026-04-09 | **2008-01-02** |

The daily lane needs no new puller — `rates_citi_live` already pulls `par/spread/fwd`
every run and `bfly` on static-quote fires, and all four are current to 2026-10-09.

**Range-check note**: 144 of 124,205 backfilled `par` rows (0.12%) exceed the
configured `par` ceiling of 20%. They are **real**, not corrupt: all sit at 1M/2M on
known IDR stress dates (2013-06 taper tantrum, 2016-11, 2018-09, 2020-03). The
2013-06-20 curve decays smoothly and monotonically — 1M 47.98 → 3M 24.90 → 1Y 10.93
→ 5Y 6.89 → 50Y 6.81 — which corruption does not do. `expected_ranges.par` is tuned
for G10 and does not accommodate an EM front end under a currency run.

---

## Defects found on the way

### 1. `rc` (ROLL_CARRY) was dead estate-wide — FIXED IN CODE, **LOAD BLOCKED ON DDL**

`build_tags` emitted `rc` as a single-tenor quote (`{prefix}.ROLL_CARRY.{tenor}`),
but the real tag is `{prefix}.ROLL_CARRY.{HORIZON}.{FWD_START}.{TENOR}.{MEASURE}`
(IDR: 8,554 tags; USD_SOFR: 32,166). The emitted tag could never resolve, so `rc`
produced **0 rows in 29.4M across all 59 curves** since inception, despite sitting
in `pipelines.yml:default_quotes` the whole time.

Fixed 2026-10-14 as **one request family, three storage quotes**: `rc` stays the
request key (one fetch returns all three measures, so the tag-quota cost stays 1x)
and the parser fans the response into `rc_carry` / `rc_roll` / `rc_total`. A measure
then filters like any other quote, with no new column. 32 curated combos × 3
measures = 96 tags/curve, verified present on both IDR and USD_SOFR.

The fetch side now works — **411,244 IDR rows returned with 0 tag errors**. Three
validation layers had to agree, and they were discovered one at a time:

| Layer | Status |
|---|---|
| `build_tags` / `citi_tag_to_internal` tag shape | fixed |
| `schemas/rates.py` `ALLOWED_QUOTES` | fixed — now **derived** from the domain schema rather than a duplicated literal, which is how it drifted |
| DB `CHECK` constraint `ck_rates_quote` | **BLOCKED — needs a DBA** |

`migrations/133_extend_ck_rates_quote_for_roll_carry.sql` is authored and follows
`030_extend_ck_rates_quote_for_basis.sql` exactly (idempotent, purely additive — no
previously-valid value is removed, so it cannot fail on existing data). It is **not
applied**: the SQL account has no DDL rights, the same wall that parked migrations
120–122 and 132. Once a DBA runs 133, the load is one command:

```
# scripts/rates/citi/rates_citi_historical.py -> CURVES="IDR.JIBOR", QUOTES="rc"
python -m scripts.rates.citi.rates_citi_historical
```

> Correcting the record: this approach was chosen partly on the basis that it needed
> no DDL. That was wrong — the DB-level CHECK constraint was missed. Of the three
> options, only *encode the measure into `tenor`* would have avoided DDL entirely.

### 2. `spread`/`bfly` had no history before 2026-04-09 — BACKFILLED

Affected all 31 curves, not just IDR: both quotes were added to the live lane in
April 2026 and never backfilled. IDR was taken back to 2008-01-02 with the main
backfill; the remaining **30 curves** followed (720 tags, 2008-01-02 → 2026-10-13).

### 3. IDR hourly lane carries bad prints — NOT FIXED

1,058 rows violate their own configured range, including `par`/`fwd` down to
**−57.7%**. Pre-dates this work (the lane starts 2024-05-06) and is confined to
`frequency_id=4`; the daily lane is clean. Left alone deliberately — out of scope
and it needs its own look at the hourly cohort.

### 4. The Govy Monitor store may have stopped entirely

On 2026-10-12 the store ran to 2026-10-06 for ten issuers (INDOGB and UST already
stalled at 2026-08-13). On 2026-10-14 it **still** ran to 2026-10-06 — i.e. no new
data for 8 calendar days across every issuer, not just the two known-dark ones.
The staleness spec now registered (`rates.bonds_govy`) flags this; see
[`../../../development/govt_bond_population.md`](../../../development/govt_bond_population.md).
