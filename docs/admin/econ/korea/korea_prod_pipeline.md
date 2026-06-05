# Korea Econ — Production Pipeline

Last updated: 2026-06-05

Operations reference for the Korea economic data ingest that landed in
production on 2026-06-05. For the broader Korea data landscape (sources,
indicator inventory, KOSIS API reference), see [index.md](index.md).

---

## Architecture

```
Vendor API (KOSIS / REB)
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

Every prod fetcher is a thin wrapper: it defines a `run_fetch(since, until)` callback
and calls `scripts.econ._runner.run_main(vendor, topic, fetch_fn)`. The runner owns
CLI parsing, parquet write, and loader invocation.

Domain library code lives in `src/imdr/domains/econ/`:

| Module | Purpose |
|---|---|
| `schema.py` | `IndicatorRow`, `ObservationRow`, `indicators_to_records`, `observations_to_records` |
| `kosis_http.py` | `make_session`, `load_kosis_key`, `fetch_kosis_table`, `parse_kosis_period` — TLS 1.2 pin + retry |

---

## Cadence and orchestrator placement

### Weekly (`scripts/imdr_weekly.py`, position #3 of 5)

```
python -m scripts.econ.kr.kr_weekly
```

Runs after the canonical holiday-calendar merge and before the health dashboard.
Fans out to 2 fetchers sequentially:

| Fetcher | Vendor | Series | Cadence |
|---|---|---|---|
| `scripts.econ.reb.reb_housing` | REB R-ONE | 4 (KR_NAT + KR_SEOUL × Sale + Jeonse) | Weekly (apt sale + jeonse data) |
| `scripts.econ.kosis.kosis_reb_housing` | KOSIS mirror of REB | 4 (same 4 series, 2021-07→) | Weekly |

Smoke result 2026-06-05: 22 s total, 2/2 OK, 4 parquet files written.

### Monthly (`scripts/imdr_monthly.py`, position #1 of 1)

```
python -m scripts.econ.kr.kr_monthly
```

Fans out to 19 KOSIS fetchers **sequentially** (KOSIS rate-limits concurrent
connections from the same API key):

| Fetcher | Topics | Primary cadence |
|---|---|---|
| `kosis_balance_sheets` | HH credit + FSS bank NPL | Quarterly |
| `kosis_bank_rates` | Deposit + CD + repo rates | Monthly |
| `kosis_bop` | BoP CA + FA + E&O (24 series) | Monthly |
| `kosis_bsi` | Business Survey Index (Mfg Realised + Outlook) | Monthly |
| `kosis_consumer_survey` | CCI + 15 sub-components | Monthly |
| `kosis_corp_debt` | Corporate financial ratios × 13 metrics | Annual |
| `kosis_cpi` | CPI headline + components (15 series) | Monthly |
| `kosis_fiscal` | Public Revenue / Expenditure / Net Lending | Annual |
| `kosis_gdp` | GDP-Q + 11 components × QoQ-SA + YoY (24 series) | Quarterly |
| `kosis_industrial` | IIP (Industrial Output Index) + Mfg Capacity Util | Monthly |
| `kosis_labour` | EAPS 8 labour-force series | Monthly |
| `kosis_lending` | Lending Attitude Survey + HH loans by purpose | Monthly / Quarterly |
| `kosis_money_aggregates` | M2 + Lf monetary aggregates | Monthly |
| `kosis_ppi` | PPI total + 5 sectors | Monthly |
| `kosis_retail` | Retail Sales × 7 types × Value + SA | Monthly |
| `kosis_tot` | Terms of Trade (Net Barter + Income) | Monthly |
| `kosis_trade_indices` | Export + Import × Value + Volume indices | Monthly |
| `kosis_trade_prices` | Import + Export prices × Won + USD | Monthly |
| `kosis_wages` | National avg wage level + YoY growth | Annual |

Annual and quarterly fetchers are included here: MERGE on PK makes them
idempotent — running monthly catches every release window without needing
separate quarterly/annual schedulers.

Smoke result 2026-06-05: 170 s total, 19/19 OK, 38 parquet files written,
+24 DB rows (April-2026 BoP print; all other series already present = 0 new rows).

---

## On-demand invocation

### Run the full weekly or monthly bucket

```
python -m scripts.econ.kr.kr_weekly
python -m scripts.econ.kr.kr_monthly
```

### Run a single fetcher

```
python -m scripts.econ.kosis.kosis_cpi
python -m scripts.econ.reb.reb_housing
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
# Check what CPI would produce without writing anything
python -m scripts.econ.kosis.kosis_cpi --no-parquet

# Fetch only 2026 data, write parquet, skip DB load
python -m scripts.econ.kosis.kosis_bop --since 2026-01-01 --no-load

# Full fetch + load for a single topic
python -m scripts.econ.kosis.kosis_gdp
```

---

## Data archive layout

Parquet files land under `data/econ/{vendor}/{topic}/{YYYY}/{MM}/{DD}/`:

```
data/econ/
├── kosis/
│   ├── cpi/2026/06/05/kosis_cpi_20260605_1437_dim.parquet
│   │                   kosis_cpi_20260605_1437_fact.parquet
│   ├── bop/2026/06/05/kosis_bop_20260605_1441_dim.parquet
│   │                   kosis_bop_20260605_1441_fact.parquet
│   └── ...
└── reb/
    └── housing/2026/06/05/reb_housing_20260605_1436_dim.parquet
                            reb_housing_20260605_1436_fact.parquet
```

Each run appends a timestamped `{vendor}_{topic}_{YYYYMMDD}_{HHMM}_{dim|fact}.parquet`
pair inside the daily folder. Re-runs do not overwrite — history is preserved by the
timestamp in the filename.

---

## Idempotency

The canonical loader uses `MERGE INTO` on the primary key:

- `econ.dim_indicator`: keyed on `(vendor_id, source_code)` — repeat runs update
  `display_name` and metadata but do not create duplicate rows.
- `econ.fact_indicator`: keyed on `(indicator_id, obs_date, vintage)` — re-running
  after a data revision updates `value`; `release_date` is preserved on existing rows.

It is safe to re-run any fetcher. If KOSIS later revises a historical print, a
re-run of the affected fetcher will upsert the corrected value.

---

## Failure modes

### KOSIS TLS handshake reset

**Symptom**: `ConnectionResetError` or `SSLError` on the first request.

**Cause**: KOSIS pins TLS 1.2 and rejects TLS 1.3 negotiation.

**Fix**: `src/imdr/domains/econ/kosis_http.py::make_session()` forces TLS 1.2 via
`ssl.TLSVersion.TLSv1_2`. This is already applied in all prod fetchers — if you see
this error, verify you are running through `kosis_http.make_session()` and not a
bare `requests.Session`.

### Missing API key

**Symptom**: `KeyError` or `ValueError: IMDR_KOSIS_API_KEY not set` on startup.

**Fix**: Ensure `.env` contains:
```
IMDR_KOSIS_API_KEY=...       # KOSIS OpenAPI key (free, register at kosis.kr)
IMDR_REB_API_KEY=...         # REB R-ONE key (32-char hex, from data.go.kr service 15134761)
```

`kosis_http.load_kosis_key()` raises a descriptive error pointing at the env var name
if the key is absent.

### KOSIS 40k-row cap

**Symptom**: Response truncated at exactly 40,000 rows; some series missing from output.

**Cause**: KOSIS caps each API call at 40,000 cells.

**Fix**: Wide tables are fetched per-cut (one call per top-level category code rather
than `obj_l1=ALL`). This is already implemented in the affected fetchers (PPI,
Trade Prices, CCI, BSI, Corp Debt). If a new fetcher hits the cap, apply the same
discovery-first + per-cut iteration pattern from those scripts.

### FK resolution failure in the loader

**Symptom**: Loader aborts with `FK miss for vendor / country / unit / category / frequency`.

**Cause**: A dimension value in the fetcher output does not match any row in
`dbo.dim_vendor`, `dbo.dim_country`, `dbo.dim_unit`, `dbo.dim_category`, or
`dbo.dim_frequency`.

**Fix**: The loader is loud — it prints the exact FK miss. Either correct the fetcher
output to use the canonical code, or add the missing dimension row via a migration.
Do not work around by disabling FK checks.

### Loader exits rc != 0

**Symptom**: Fetcher wrote parquet successfully but `invoke_loader()` returns non-zero.

**Fix**: Re-run the loader directly on the parquet pair that was written:

```
python -m scripts.migrations.load_econ_indicator_from_playground \
    --vendor kosis \
    --dim-parquet data/econ/kosis/cpi/2026/06/05/kosis_cpi_20260605_1437_dim.parquet \
    --fact-parquet data/econ/kosis/cpi/2026/06/05/kosis_cpi_20260605_1437_fact.parquet
```

The parquet files are on disk — no need to re-fetch from the vendor.

---

## Smoke-test commands

```
# Verify weekly bundle runs end-to-end (writes parquet + loads DB)
python -m scripts.econ.kr.kr_weekly

# Verify monthly bundle (expect ~170 s)
python -m scripts.econ.kr.kr_monthly

# Spot-check a single fetcher without touching DB
python -m scripts.econ.kosis.kosis_cpi --no-load

# Confirm idempotency: re-run and expect 0 new DB rows
python -m scripts.econ.kosis.kosis_cpi
```

---

## Playground status

The playground fetchers under `playground/econ/kosis/` (20 scripts) and
`playground/econ/reb/fetch_housing.py` are intentionally preserved as the
legacy sandbox. They were the development path and remain useful for ad-hoc
exploration, but they bypass the canonical loader invocation (they write
parquet only; DB load requires running `load_econ_indicator_from_playground`
separately). **For anything production-bound, use `scripts/econ/` — not
`playground/econ/`.**
