# Bloomberg Rates Pipeline — operations

> ## ⚠️ READ-ONLY ACCESS TO Z:\BBG\IRS and Z:\BBG\OIS ⚠️
>
> IMDR must NEVER move, rename, delete, or modify any file under
> `Z:\Business\Research\Dashboard\DataSources\BBG\`. The upstream R
> pipeline owns these files and overwrites them in place every batch.
> Moving a file breaks both the next IMDR poll and the R overwrite
> loop. Enforced by `archive_after_load=False` on the
> `bbg_rates_snapshot` feed + the lock-in test
> `tests/unit/test_vendors/test_bbg_rates_snapshot_no_move.py`.

Bloomberg sits alongside Citi Velocity as a second vendor on
[`rates.fact_observation`](../../migrations/029_add_vendor_id_to_rates_fact_observation.sql).
This doc covers BBG-specific operational details. Schema-level
information lives in the existing rates docs; the FX equivalent of this
doc is [`fx_rate_bbg.md`](../fx/fx_rate_bbg.md).

For upstream R-pipeline architecture see
[`docs/admin/vendors/bbg/`](../admin/vendors/bbg/).

---

## At a glance

| Property | Value |
|---|---|
| Vendor code | `bloomberg` (vendor_id=4) |
| Live cadence | Half-hourly fires 09:45–20:45 SGT (23 fires/day) — rides the existing FX orchestrator |
| Source files | `Z:\...\BBG_mirror\IRS\{CURVE}\PAR\IRS_PAR_{CURVE}.csv` + `Z:\...\BBG_mirror\OIS\{CURVE}\PAR\OIS_PAR_{CURVE}.csv` |
| Live curves | 29 fresh curves (17 IRS + 12 OIS) — auto-seeded into `dim_curve` on first fire |
| Pipeline | `BloombergRatesPipeline` ([src](../../src/imdr/domains/rates/pipeline_bbg.py)) |
| Vendor feed | `bbg_rates_snapshot` ([spec](../../src/imdr/vendors/specs/bbg_rates_snapshot.py)) |
| Orchestrator | [`scripts/imdr_snapshots_bbg.py`](../../scripts/imdr_snapshots_bbg.py) |
| Health check | [`scripts/bbg_rates_health_check.py`](../../scripts/bbg_rates_health_check.py) |

---

## Schema

Migration 029 added `vendor_id INT NOT NULL` to `rates.fact_observation`
with FK to `dbo.dim_vendor(id)`. The unique constraint became:

```
(curve_id, vendor_id, ts, quote, tenor, frequency_id)
```

— 6 columns, mirrors the post-migration-027 shape of `fx.fact_fx_rate`.
All pre-existing 5.85M rows were backfilled to `vendor_id = citi_velocity`
in 500K-row chunks.

The Citi rates pipeline ([pipeline.py](../../src/imdr/domains/rates/pipeline.py))
now stamps `vendor_id = citi_velocity` on every row it writes. The BBG
pipeline stamps `vendor_id = bloomberg`. Both share the same target
table; the unique key dimensionality keeps them apart.

---

## CSV format

The R pipeline writes one CSV per curve with a 3-row header. Verified
across all 47 in-scope curves (audited 2026-04-25):

```
Row 0: Ticker,BBSW 3M INDEX,ADSWFQ BGN Curncy,...
Row 1: <varies: Tenor|Term|Ticker|Tickers|Date|Dates|rv Iden>,IRS_PAR_AUQ_SPOT_3M,...
Row 2: Maturity,0.25,0.5,...
Row 3+: dd/mm/yyyy,<rate>,<rate>,...
```

Values are in **percent** (4.35 = 4.35%) — match the existing Citi
storage convention exactly, no unit conversion needed.

### Format quirks the parser handles (full list)

The format is messier than FX. Eleven distinct quirks observed —
[`extractors_rate_bbg.py`](../../src/imdr/domains/rates/extractors_bbg.py)
docstring covers them all:

| Quirk | Example | How parser handles |
|---|---|---|
| Row-1 first cell varies | `Date`, `Dates`, `Tenor`, `Term`, `Ticker`, `Tickers`, `rv Iden` | Treated as label-source regardless of cell text |
| Tenor-label ccy prefix varies | `AUQ`, `EUQ`, `DT6`, `INR`, `ILS`, `EUS`, `SOFR`, `JPY`, `JPY_PAR_OIS` | Trailing-tenor regex `_(\d+[YMWD]\|ON)$` |
| `ON` overnight tenor | `OIS_PAR_CHF_SPOT_ON` | Regex matches `ON` token |
| Mixed schemes within ONE file | JPY-TONAR-JSCC: `JPY_PAR_OIS_SPOT_1D` + `OIS_PAR_JPY_SPOT_1Y` | Trailing-tenor regex works on both |
| Duplicate tenor cols | USD-LIBOR-3M two `IRS_PAR_USD_SPOT_6M` cols (fixings + swap) | Dedupe via `keep='last'` |
| Folder vs label ccy mismatch | PLN-WIBOR-6M tenor labels say `IRS_PAR_EUR_*` but tickers are `PZSW*` | **Folder name wins**; tenor-label ccy ignored |
| Multi-space ticker headers | `"EESWE1Z  BGN Curncy"` | Stripped before processing |
| `-ori.csv` filename | USD-LIBOR-3M | Allowed by file glob |
| Negative rates | CHF-SARON-ON spot = -0.039025 | Pass through unchanged (FLOAT column) |
| Date format `dd/mm/yyyy` | All curves | Universal — single parse path |
| 12M tenor | Some files use `12M` instead of `1Y` | Normalized to `1Y` |

---

## Curve mapping — IMDR vs BBG identity

BBG splits IRS curves by reset tenor (`AUD-BBSW-3M` vs `AUD-BBSW-6M`)
where the existing IMDR `dim_curve` has just `(AUD, BBSW)`. The BBG
pipeline auto-seeds NEW dim_curve rows for each BBG-specific variant
on first run:

| BBG folder | IMDR `(ccy, curve)` | citi_prefix |
|---|---|---|
| `AUD-BBSW-3M` | `(AUD, BBSW_3M)` | `BBG:AUD-BBSW-3M` |
| `AUD-BBSW-6M` | `(AUD, BBSW_6M)` | `BBG:AUD-BBSW-6M` |
| `USD-SOFR-ON` | `(USD, SOFR)` (reuse existing) | `BBG:USD-SOFR-ON` |
| `JPY-TONAR-ON-JSCC` | `(JPY, TONAR_JSCC)` (reuse existing) | `BBG:JPY-TONAR-ON-JSCC` |
| `PLN-WIBOR-6M` | `(PLN, WIBOR_6M)` (NEW — PLN absent before) | `BBG:PLN-WIBOR-6M` |

`citi_prefix` is repurposed as a vendor-tag — `BBG:{folder}` marks
BBG-only curves. Net additions: ~22 new dim_curve rows once all 47
backfill curves load.

---

## Curve inventory

### 29 fresh curves (live polled)

**IRS (16)**: AUD-BBSW-3M, AUD-BBSW-6M, CNO-REPO-7D, CNY-REPO-7D,
CNY-SHIBOR-3M, EUR-EURIBOR-3M, EUR-EURIBOR-6M, HKD-HIBOR-3M,
KRO-91D_CD-3M, KRW-91D_CD-3M, MYO-KLIBOR-3M, MYR-KLIBOR-3M,
NOK-NIBOR-6M, NZD-BKBM-3M, PLN-WIBOR-6M, SEK-STIBOR-3M, TWD-TAIBOR-3M

**OIS (12)**: AUD-AONIA-ON, CAD-CORRA-ON, CHF-SARON-ON, EUR-ESTR-ON,
ILS-SHIR-ON, INR-MIBOR-ON, JPY-TONAR-ON-JSCC, NZD-NZOCRS-ON,
THB-THOR-ON, THO-THOR-ON, USD-FEDFUNDS-ON, USD-SOFR-ON

### 18 stale curves (historical backfill only, no live poll)

**IRS (14)**: CAD-CDOR-3M, CHF-LIBOR-6M, CNH-HIBOR-3M, GBP-LIBOR-3M,
GBP-LIBOR-6M, INR-MIFOR-6M, JPY-DTIBOR-3M, JPY-DTIBOR-6M, JPY-LIBOR-6M,
PLN-WIBOR-3M, SGD-SOR-6M, THB-THBFIX-6M, THO-THBFIX-6M, USD-LIBOR-3M

**OIS (4)**: GBP-SONIA-ON, JPY-TONAR-ON, SGD-SOR-ON, (one more)

### Skipped entirely

- `IRS/USD-CPURNSA` — inflation CPI swaps (different curve type)
- `IRS/MS` — master spreads aggregate
- `OIS/AUD-AONIA.MD-ON`, `OIS/USD-FEDFUNDS.MD-ON` — FOMC/RBA meeting forwards
- `IRS/AUD-BBSW.IAUS-3M` — empty PAR/ folder

---

## Operations

### Live ingest

Half-hourly fires from `imdr_snapshots_bbg.py` call `bbg_rates_snapshot`
alongside `bbg_fx_snapshot`. Each fire:

1. Globs for the 29 fresh-curve PAR CSVs (only — stale curves are not polled)
2. Filters by `min_mtime_age=72h` (excludes weekend-stale files)
3. Reads the **latest data row** from each CSV
4. Stamps `ts = file mtime UTC`, `vendor_id=bloomberg`, `frequency_id=SNAPSHOT`
5. MERGE-upserts to `rates.fact_observation`

Idempotent: re-firing within the same BBG batch window is a MERGE no-op
because `ts` (CSV mtime) hasn't changed.

### End-of-day health check

```
python -m scripts.bbg_rates_health_check                    # today, sends email
python -m scripts.bbg_rates_health_check --no-email         # console only
python -m scripts.bbg_rates_health_check --date 2026-04-28  # specific date
```

Per-curve report: which of the 6 expected batches landed and which
didn't. Cross-references `Z:\...\BBG\log\bbgCheck\` so genuine upstream
BBG outages are distinguished from IMDR-side ingest failures.

---

## Common operations

| Need | Command |
|---|---|
| Fire one snapshot manually (in-window) | `python -m scripts.run_vendor_feed bbg_rates_snapshot` |
| Fire all BBG (FX + rates) for current 30-min window | `python -m scripts.imdr_snapshots_bbg` |
| Health check today | `python -m scripts.bbg_rates_health_check` |
| Cross-vendor recon (Citi vs BBG) | `SELECT vendor_id, AVG(value) ... GROUP BY vendor_id` over overlap curves |
