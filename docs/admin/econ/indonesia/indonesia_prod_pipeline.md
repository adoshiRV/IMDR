# Indonesia Econ — Production Pipeline

Last updated: 2026-06-09

Operations reference for the Indonesia economic data ingest that was
prod-promoted on 2026-06-09. For the broader Indonesia data landscape
(sources, indicator inventory, coverage plan, BPS API reference), see
[index.md](index.md).

**Status: live as of 2026-06-09.** `scripts/econ/id/id_monthly.py` is wired into
`scripts/imdr_monthly.py:PIPELINES` 2026-06-09.

---

## Architecture

```
Vendor API/portal
  BPS REST JSON (webapi.bps.go.id)
  BI SEKI XLSX (bi.go.id/SEKI/tabel/)
  BI Survey ZIPs (bi.go.id/.../Documents/{SK,spe,SKDU}.zip)
  BIS SDMX-JSON (stats.bis.org/api/v2/)
        │
        ▼
scripts/econ/{vendor}/{topic}.py   ← per-topic fetcher; delegates to _runner.run_main()
        │
        ├─ fetch_fn()              ← vendor-specific pull; returns (indicators, observations)
        │
        ├─ write_parquet()         ← writes (dim, fact) pair under data/econ/{vendor}/{topic}/{Y}/{M}/{D}/
        │
        └─ invoke_loader()         ← calls scripts.migrations.load_econ_indicator_from_playground
                                       --vendor {vendor} --dim-parquet {path} --fact-parquet {path}
                                           │
                                           ▼
                                   MERGE INTO econ.dim_indicator
                                   MERGE INTO econ.fact_indicator
```

Every prod fetcher is a thin wrapper: it defines a `run_fetch(since, until)`
callback and calls `scripts.econ._runner.run_main(vendor, topic, fetch_fn)`.
The runner owns CLI parsing, parquet write, and loader invocation.

Domain library code lives in `src/imdr/domains/econ/`:

| Module | Purpose |
|---|---|
| `schema.py` | `IndicatorRow`, `ObservationRow`, `indicators_to_records`, `observations_to_records` |
| `bps_http.py` | `bps_fetch_data_chunked`, `parse_datacontent`, composite-key reverse-map, 3-year `th` chunking |
| `bi_seki.py` | SEKI XLSX downloader + sheet parser; `_infer_years` Dec→Jan year rollover logic |
| `bi_survey.py` | Survey ZIP downloader (SK / spe / SKDU); single-XLSX assertion + row-indexed parser |
| `bis_sdmx.py` | `fetch_sdmx_series` — SDMX-JSON dataflow helper; no auth; Indonesia key=`ID` |

---

## Cadence and orchestrator placement

### Daily (`scripts/imdr_daily.py:PIPELINES`)

`scripts.econ.bis.bis_indonesia` is registered in `scripts/imdr_daily.py:PIPELINES`
(non-Citi block, `estimated_tags=0`) in addition to its place in the monthly bundle.

**Rationale**: BIS's `WS_CBPOL` policy rate is event-driven — it changes only when
BI's RDG (Rapat Dewan Gubernur) meeting moves the rate. Daily wiring catches the move
within 24h of the meeting. The monthly run remains the backstop: the loader MERGEs on
PK so daily re-runs are free, and any transient daily failure is cleaned up at month-end.
This is the same pattern Korea uses to keep quarterly/annual KOSIS fetchers under
`kr_monthly.py` — running idempotent fetchers more often than strictly necessary trades
a few extra API calls for tighter latency.

### Monthly (`scripts/econ/id/id_monthly.py`)

```
python -m scripts.econ.id.id_monthly
```

Wired into `scripts/imdr_monthly.py:PIPELINES` 2026-06-09. Runs as part of the monthly scheduler.

Indonesia has no WEEKLY-cadence series — no `id_weekly.py` counterpart is
needed. Semi-annual (BPS Sakernas), annual (BI fiscal/SBN), and daily (BIS
policy rate) series all live under the monthly trigger because fetchers are
idempotent (MERGE on PK): running them monthly catches every release window
without per-cadence scheduling.

Fans out to **25 fetchers sequentially** (BPS/BI portal throttle discourages
concurrency; BIS is fast enough that parallelism adds no benefit):

| Fetcher | Vendor | Primary cadence | Approx indicators |
|---|---|:---:|---:|
| `scripts.econ.bis.bis_indonesia` | BIS SDMX-JSON | Daily / Monthly / Quarterly | 6 |
| `scripts.econ.bps.bps_cpi` | BPS REST JSON | Monthly | 4 |
| `scripts.econ.bps.bps_cpi_groups` | BPS REST JSON | Monthly | 11 |
| `scripts.econ.bps.bps_gdp` | BPS REST JSON | Quarterly | 7 |
| `scripts.econ.bps.bps_gdp_components` | BPS REST JSON | Quarterly | 24 |
| `scripts.econ.bps.bps_ip` | BPS REST JSON | Quarterly | 4 |
| `scripts.econ.bps.bps_labour` | BPS REST JSON | Monthly / Annual | 3 |
| `scripts.econ.bps.bps_ppi` | BPS REST JSON | Quarterly / Monthly | 8 |
| `scripts.econ.bps.bps_prices_current` | BPS REST JSON | Quarterly / Monthly | 8 |
| `scripts.econ.bps.bps_sakernas` | BPS REST JSON | Semi-annual | 12 |
| `scripts.econ.bps.bps_trade` | BPS REST JSON | Monthly | 6 |
| `scripts.econ.bi.bi_bank_bs` | BI SEKI XLSX | Monthly | 8 |
| `scripts.econ.bi.bi_bank_credit` | BI SEKI XLSX | Monthly | 15 |
| `scripts.econ.bi.bi_bank_rates` | BI SEKI XLSX | Monthly | 13 |
| `scripts.econ.bi.bi_bop` | BI SEKI XLSX | Quarterly | 5 |
| `scripts.econ.bi.bi_business_survey` | BI Survey ZIP (SKDU) | Quarterly | 18 |
| `scripts.econ.bi.bi_consumer_survey` | BI Survey ZIP (SK) | Monthly | 9 |
| `scripts.econ.bi.bi_fiscal` | BI SEKI XLSX | Annual | 6 |
| `scripts.econ.bi.bi_fx_reserves` | BI SEKI XLSX | Monthly | 5 |
| `scripts.econ.bi.bi_monetary_base` | BI SEKI XLSX | Monthly | 5 |
| `scripts.econ.bi.bi_money_supply` | BI SEKI XLSX | Monthly | 10 |
| `scripts.econ.bi.bi_retail_sales` | BI Survey ZIP (spe) | Monthly | 9 |
| `scripts.econ.bi.bi_sbn` | BI SEKI XLSX | Monthly | 5 |
| `scripts.econ.bi.bi_skdu_macro` | BI SEKI XLSX | Quarterly | 36 |
| `scripts.econ.bi.bi_sulni` | BI SEKI XLSX | Quarterly | 8 |

Annual and semi-annual fetchers (Sakernas, fiscal) are included here: MERGE on
PK makes them idempotent — running monthly catches every release window without
needing separate schedulers.

---

## On-demand invocation

### Run the full monthly bundle

```
python -m scripts.econ.id.id_monthly
```

### Run a single fetcher

```
# BIS (smallest, no auth, fast smoke-test)
python -m scripts.econ.bis.bis_indonesia

# BPS examples
python -m scripts.econ.bps.bps_cpi
python -m scripts.econ.bps.bps_gdp
python -m scripts.econ.bps.bps_sakernas

# BI examples
python -m scripts.econ.bi.bi_money_supply
python -m scripts.econ.bi.bi_bop
python -m scripts.econ.bi.bi_bank_rates
```

### Per-fetcher CLI flags (all fetchers via `_runner.run_main`)

| Flag | Effect |
|---|---|
| `--since YYYY-MM-DD` | Filter observations to obs_date >= this date |
| `--until YYYY-MM-DD` | Filter observations to obs_date <= this date |
| `--no-parquet` | Skip parquet write and DB load; print summary only |
| `--no-load` | Write parquet but skip the DB MERGE step |

Examples:

```
# Check what BPS CPI would produce without writing anything
python -m scripts.econ.bps.bps_cpi --no-parquet

# Fetch only 2026 data, write parquet, skip DB load
python -m scripts.econ.bi.bi_bop --since 2026-01-01 --no-load

# Full fetch + load for a single topic
python -m scripts.econ.bis.bis_indonesia
```

---

## Data archive layout

Parquet files land under `data/econ/{vendor}/{topic}/{YYYY}/{MM}/{DD}/`:

```
data/econ/
├── bps/
│   ├── cpi/2026/06/09/bps_cpi_20260609_1015_dim.parquet
│   │                   bps_cpi_20260609_1015_fact.parquet
│   ├── gdp/2026/06/09/bps_gdp_20260609_1017_dim.parquet
│   │                   bps_gdp_20260609_1017_fact.parquet
│   └── ...
├── bi/
│   ├── seki_raw/        ← XLSX cache (raw BI SEKI downloads)
│   ├── money_supply/2026/06/09/bi_money_supply_20260609_1020_dim.parquet
│   │                            bi_money_supply_20260609_1020_fact.parquet
│   └── ...
└── bis/
    └── indonesia/2026/06/09/bis_indonesia_20260609_1014_dim.parquet
                              bis_indonesia_20260609_1014_fact.parquet
```

Each run appends a timestamped `{vendor}_{topic}_{YYYYMMDD}_{HHMM}_{dim|fact}.parquet`
pair inside the daily folder. Re-runs do not overwrite — history is preserved by
the timestamp in the filename.

---

## Idempotency

The canonical loader uses `MERGE INTO` on the primary key:

- `econ.dim_indicator`: keyed on `(vendor_id, source_code)` — repeat runs update
  `display_name` and metadata but do not create duplicate rows.
- `econ.fact_indicator`: keyed on `(indicator_id, obs_date, vintage)` — re-running
  after a data revision updates `value`; `release_date` is preserved on existing rows.

It is safe to re-run any fetcher. If BPS or BI later revises a historical print,
a re-run of the affected fetcher will upsert the corrected value.

---

## Failure modes

### BPS — `th` parameter caps at 3 years

**Symptom**: only ~3 years of data returned even when requesting a longer range.

**Cause**: BPS API caps the `th` (year) parameter at 3 year-values per call.

**Fix**: `src/imdr/domains/econ/bps_http.py::bps_fetch_data_chunked()` automatically
splits long ranges into 3-year chunks and concatenates results. Always use
`bps_fetch_data_chunked()`, not a direct multi-year call.

### BPS — vervar IDs renumber across base-year revisions

**Symptom**: a fetcher that previously returned INDONESIA-level data returns
empty or unexpected rows after a BPS base-year revision.

**Cause**: the national-rollup `vervar_id` is NOT stable. CPI pre-2024 uses
`vervar_id=9999`; the 2024+ 150-kab/kota series renumbered to `vervar_id=151`.

**Fix**: always auto-detect the national vervar by `vervar_label == "INDONESIA"` —
never hard-code. This pattern is applied in all current BPS prod fetchers. See
[bps_api_reference.md](bps_api_reference.md#other-gotchas-observed) for full context.

### BPS — composite-key parser (variable-width IDs)

**Symptom**: `parse_datacontent()` mis-assigns values to the wrong series; roughly
30% of variables have the wrong obs linked.

**Cause**: `datacontent` keys concatenate `{vervar}{var}{turvar}{tahun}{turtahun}`
without zero-padding; naive fixed-width splits fail where IDs have different digit counts.

**Fix**: `src/imdr/domains/econ/bps_http.py::parse_datacontent()` uses a cartesian-
product reverse map to unambiguously decode variable-width composite keys. Do not
replace this with a width-split approach.

### BI SEKI — year-label-at-Dec quirk

**Symptom**: 11 months of a calendar year are parsed one year too early (e.g.
Jan–Nov 2024 data is labelled as 2023).

**Cause**: SEKI XLSX files stamp the year label at the **December column**, not the
January column. A naive forward-fill assigns the Dec year-label to Jan of the
following year's block.

**Fix**: `src/imdr/domains/econ/bi_seki.py::_infer_years()` walks month-by-month
with a Dec→Jan year increment instead of forward-filling. This is already applied
in all BI SEKI prod fetchers.

### BI Survey — single-XLSX-per-ZIP assertion

**Symptom**: `AssertionError` when running any BI Survey fetcher
(`bi_consumer_survey`, `bi_retail_sales`, `bi_business_survey`).

**Cause**: each Survey ZIP is expected to contain exactly one XLSX. If BI changes
their archive structure, the assertion raises before any data is parsed.

**Fix**: inspect the ZIP contents manually; update `src/imdr/domains/econ/bi_survey.py`
if the structure has changed.

### BIS — SDMX dataflow paths must match exactly

**Symptom**: HTTP 404 or empty SDMX response from `stats.bis.org`.

**Cause**: the BIS SDMX-JSON API requires exact dataflow IDs. Supported dataflows
for Indonesia are: `WS_EER` (NEER/REER), `WS_DSR` (debt service ratios),
`WS_CREDIT_GAP` (credit-to-GDP), `WS_CBPOL` (central bank policy rate).
The Indonesia country key is `ID` (2-letter ISO).

**Fix**: verify the dataflow ID against the BIS portal. Do not guess or abbreviate.

### Missing API key (`IMDR_BPS_API_KEY`)

**Symptom**: `KeyError` or `ValueError: IMDR_BPS_API_KEY not set` on startup of
any BPS fetcher.

**Fix**: ensure `.env` contains:
```
IMDR_BPS_API_KEY=...    # Free key from webapi.bps.go.id (see index.md for registration steps)
```

BI and BIS fetchers require no API key.

### FK resolution failure in the loader

**Symptom**: loader aborts with `FK miss for vendor / country / unit / category / frequency`.

**Cause**: a dimension value in the fetcher output does not match any row in
`dbo.dim_vendor`, `dbo.dim_country`, `dbo.dim_unit`, `dbo.dim_category`, or
`dbo.dim_frequency`.

**Fix**: the loader is loud — it prints the exact FK miss. Either correct the fetcher
output to use the canonical code, or add the missing dimension row via a migration.
Translation maps are in `scripts/migrations/load_econ_indicator_from_playground.py`.
Do not work around by disabling FK checks.

### Loader exits rc != 0

**Symptom**: fetcher wrote parquet successfully but `invoke_loader()` returns non-zero.

**Fix**: re-run the loader directly on the parquet pair that was written:

```
python -m scripts.migrations.load_econ_indicator_from_playground \
    --vendor bps \
    --dim-parquet data/econ/bps/cpi/2026/06/09/bps_cpi_20260609_1015_dim.parquet \
    --fact-parquet data/econ/bps/cpi/2026/06/09/bps_cpi_20260609_1015_fact.parquet
```

The parquet files are on disk — no need to re-fetch from the vendor.

---

## Smoke-test commands

```
# Smallest fetcher — BIS, no auth, fast (~5 s)
python -m scripts.econ.bis.bis_indonesia

# Spot-check a BPS fetcher without touching DB
python -m scripts.econ.bps.bps_cpi --no-load

# Spot-check a BI SEKI fetcher without touching DB
python -m scripts.econ.bi.bi_money_supply --no-load

# Confirm idempotency: re-run and expect 0 new DB rows
python -m scripts.econ.bis.bis_indonesia

# Full monthly bundle (expect several minutes)
python -m scripts.econ.id.id_monthly
```

---

## Playground status

The playground fetchers under `playground/econ/bps/` (10 scripts),
`playground/econ/bi/` (14 scripts), and `playground/econ/bis/fetch_indonesia.py`
are intentionally preserved as the legacy sandbox. They were the development
path and remain useful for ad-hoc exploration, but they bypass the canonical
loader invocation (they write parquet only; DB load requires running
`load_econ_indicator_from_playground` separately). **For anything
production-bound, use `scripts/econ/` — not `playground/econ/`.**
