# United States Econ — Production Pipeline

Last updated: 2026-06-23 (completeness build-out: FRED-US scheduled + BIS REER + real PCE)

Operations reference for the United States economic data pipeline. Code was
promoted to `scripts/econ/us/` on 2026-06-23 and passed the G.6 code-review
gate (0 blockers). **Wired into `scripts/imdr_monthly.py:PIPELINES` +
`scripts/imdr_daily.py:PIPELINES` 2026-06-23 (PROD-LIVE).** US now runs on
the existing scheduler cadence alongside KR/ID/AU/NZ/IN. For the broader US
data landscape (sources, indicator inventory, coverage plan), see [index.md](index.md).

---

## Architecture

```
Source-agency API (BLS / BEA / Census / Treasury / EIA)
        │
        ▼
scripts/econ/us/{vendor}/{vendor}_{topic}.py   ← per-topic fetcher; delegates to _runner.run_main()
        │
        ├─ run_fetch(since, until)             ← vendor pull; returns (indicators, observations)
        │
        ├─ write_parquet()                     ← dim/fact pair under data/econ/us/{vendor}/{topic}/{Y}/{M}/{D}/
        │
        └─ invoke_loader()                     ← MERGE INTO econ.dim_indicator + econ.fact_indicator
```

Every prod fetcher is a thin wrapper: it defines a `run_fetch(since, until)` callback
and calls `scripts.econ._runner.run_main(vendor, topic, fetch_fn, description,
country_code="US")`. The runner owns CLI parsing, parquet write, and loader invocation.
`country_code="US"` is mandatory — omitting it raises `TypeError`.

Domain library code lives in `src/imdr/domains/econ/`:

| Module | Purpose |
|---|---|
| `schema.py` | `IndicatorRow`, `ObservationRow`, `indicators_to_records`, `observations_to_records` |
| `bls_http.py` | `BlsClient` — POST JSON to BLS v2; `bls_period_to_date` — `M01`/`Q01` period parser; 500 req/day, 50-series/req, 20yr/req limits |
| `bea_http.py` | `BeaClient` — GET JSON to BEA; 200-with-Error body detection; NIPA / ITA / IIP dataset dispatch |
| `census_http.py` | `CensusClient` — GET JSON to Census EITS (MARTS / resconst / intltrade); header-row + 2-D array response parser |
| `treasury_fiscaldata.py` | `TreasuryClient` — keyless GET JSON to `api.fiscaldata.treasury.gov`; pagination via `links.next` |
| `eia_http.py` | `EiaClient` — GET JSON to EIA v2; `response.data[]` shape; facet-based series selection |
| `fred_http.py` | `FredClient` — GET JSON to FRED REST API; key via `get_settings().econ_fred_key` + numbered-sibling env rotation; dual-key round-robin; 0.5s throttle; added 2026-06-23 |

---

## Note: FRED — cross-country mirror promoted to US scheduled fetchers

The cross-country OECD mirror portion of FRED (non-US series for EU/UK/JP/CA/etc.)
stays in `playground/econ/fred/` — it is the multilateral layer and is intentionally
not promoted to `scripts/econ/us/`, consistent with Korea/India.

However, the **US-specific FRED series** (108 curated active series in `seed_us.yml`)
are now on a **scheduled refresh** via two new fetchers added 2026-06-23:

- `scripts/econ/us/fred/fred_us_daily.py` — DAILY + WEEKLY series (56 series); wired into `us_daily`.
- `scripts/econ/us/fred/fred_us_monthly.py` — MONTHLY + QUARTERLY + ANNUAL series (52 series); wired into `us_monthly`.
- Shared seed loader: `scripts/econ/us/fred/_fred_seed.py`; curated spec: `scripts/econ/us/fred/seed_us.yml`.

`seed_us.yml` was generated from the DB active-set after migration 106 — it intentionally
**excludes the 26 source-dup series** migration 106 deactivated, so a scheduled reload
never re-activates them (verified: 26 still inactive post-load). It carries the post-106
categories and adds 2 macro-PM series: Philly Fed (`GACDFSA066MSFRBPHI`) + Dallas Fed
(`BACTSAMFRBDAL`) regional manufacturing surveys. Daily FRED-US history deepened to
2010+ (~165k obs). Library: `src/imdr/domains/econ/fred_http.py` (`FredClient`; key via
`get_settings().econ_fred_key` + numbered-sibling env rotation). Unit test:
`tests/unit/test_econ/test_fred_http.py`.

The US source agencies (BLS/BEA/Census/EIA) remain the authoritative publishers for
shared headline concepts. See [us_coverage_plan.md](us_coverage_plan.md#source-of-truth-policy-fred-vs-source-agencies)
and migration 106 for the FRED↔source reconciliation (26 exact-dup FRED rows
deactivated, BLS price indices recategorised `other → cpi`).

---

## Per-vendor fetcher inventory

### BLS (5 fetchers)

| Fetcher module | Topic | Wiring-map cells | Cadence |
|---|---|---|---|
| `scripts.econ.us.bls.bls_cpi` | CPI-U headline + core + component tree (shelter / energy / food / services); 9 series | 2.4 CPI Pressure | Monthly |
| `scripts.econ.us.bls.bls_ppi` | PPI final demand + stage-of-processing (6 series) | 2.2 Producer Prices | Monthly |
| `scripts.econ.us.bls.bls_employment_situation` | Payrolls (CES) + unemployment + LFPR + AHE (from BLS CES/CPS) | 1.4 Macro Core · 2.3 Domestic Costs | Monthly |
| `scripts.econ.us.bls.bls_eci_jolts` | ECI total compensation (Q) + JOLTS quits rate + job openings + productivity | 2.3 Domestic Costs | Monthly (ECI: Quarterly) |
| `scripts.econ.us.bls.bls_import_export_prices` | Import + export price indexes (EIUIR / EIUIQ) — also closes cell 3.1 ToT | 2.1 Input Costs · 3.1 Terms of Trade | Monthly |

Key: `IMDR_ECON_BLS_KEY`. POST to `https://api.bls.gov/publicAPI/v2/timeseries/data/`;
response newest-first; 20-yr window cap → chunked for deep history.

### BEA (4 fetchers)

| Fetcher module | Topic | Wiring-map cells | Cadence |
|---|---|---|---|
| `scripts.econ.us.bea.bea_gdp` | Real GDP %chg + levels from NIPA T10101/T10105 (adv/2nd/3rd-revision vintages) | 1.4 Macro Core | Quarterly |
| `scripts.econ.us.bea.bea_personal_income` | Personal income + PCE price (T20600/T20804) + **real PCE quantity (T20806/DPCERX, chained 2017 $mn, added 2026-06-23)** | 1.1 Private Demand · 2.4 CPI Pressure | Monthly |
| `scripts.econ.us.bea.bea_ita` | ITA current account + financial account decomposition (BalCurrAcct + Gds/Serv/PrimInc/SecInc) | 3.2 Current Account · 3.3 Capital Account | Quarterly |
| `scripts.econ.us.bea.bea_iip` | Net IIP stock (net international investment position) | 3.3 Capital Account | Quarterly |

Key: `IMDR_ECON_BEA_KEY`. GET to `https://apps.bea.gov/api/data`; errors come
back as HTTP 200 with `BEAAPI.Results.Error` in body — connector checks this.

### Census (3 fetchers)

| Fetcher module | Topic | Wiring-map cells | Cadence |
|---|---|---|---|
| `scripts.econ.us.census.census_retail` | MARTS retail + food services total + ex-auto | 1.1 Private Demand | Monthly |
| `scripts.econ.us.census.census_trade` | FT-900 goods + services trade balance | 1.3 External Demand | Monthly |
| `scripts.econ.us.census.census_housing` | New Residential Construction — starts + permits | 1.1 Private Demand | Monthly |

Key: `IMDR_ECON_CENSUS_KEY`. GET to
`https://api.census.gov/data/timeseries/eits/{program}` (marts / resconst /
intltrade); 2-D array response (header row + data rows).

### Treasury (2 fetchers)

| Fetcher module | Topic | Wiring-map cells | Cadence |
|---|---|---|---|
| `scripts.econ.us.treasury.treasury_mts` | Monthly Treasury Statement — receipts / outlays / deficit (MTS table 4 + table 5) | 1.2 Fiscal Demand | Monthly |
| `scripts.econ.us.treasury.treasury_debt` | Debt to the Penny — daily total public debt outstanding | 4.2 Balance Sheets | **Daily** |

Keyless. GET to `https://api.fiscaldata.treasury.gov/services/api/fiscal_service/{path}`;
paginated via `links.next`. `treasury_debt` is in `us_daily.py` (not monthly)
because daily resolution matters.

### EIA (1 fetcher)

| Fetcher module | Topic | Wiring-map cells | Cadence |
|---|---|---|---|
| `scripts.econ.us.eia.eia_energy` | WTI + Brent + Henry Hub spot prices (native EIA daily) | 2.1 Input Costs | **Daily** |

Key: `IMDR_ECON_EIA_KEY`. GET to `https://api.eia.gov/v2/{route}/data/`;
`response.data[]` shape; facet-based series selection.
`eia_energy` is in `us_daily.py` for 24h latency on energy prices.

### BIS (1 fetcher) — added 2026-06-23

| Fetcher module | Topic | Wiring-map cells | Cadence |
|---|---|---|---|
| `scripts.econ.us.bis.bis_us` | US NEER + REER broad (BIS WS_EER `M.N.B.US` + `M.R.B.US`) | 3.4 FX / REER | Monthly |

No key required — public BIS SDMX-JSON API. Endpoint:
`https://stats.bis.org/api/v2/data/dataflow/BIS/WS_EER/{ver}/M.{N,R}.B.US`.
Registers the first prod fetcher for cell 3.4, flipping ⚠️ → ✅.
Latest REER 107.26 / NEER 101.69 (broad index, Jan-2020=100).
`bis_us` is included in `us_monthly.py`.

### FRED-US (2 fetchers) — added 2026-06-23

108 curated US-specific FRED series promoted from playground to scheduled fetchers.
Shared seed loader: `scripts/econ/us/fred/_fred_seed.py`.
Series spec: `scripts/econ/us/fred/seed_us.yml` (generated from DB active-set;
see "Note: FRED" section above for seed-design and `is_active` guarantees).

| Fetcher module | Topic | Series | Cadence | Orchestrator |
|---|---|---|---|---|
| `scripts.econ.us.fred.fred_us_daily` | DAILY + WEEKLY US FRED series (rates, FX, claims, Fed BS, energy sentiment, etc.) | 56 series | Daily + Weekly | `us_daily` |
| `scripts.econ.us.fred.fred_us_monthly` | MONTHLY + QUARTERLY + ANNUAL US FRED series (macro aggregates, SLOOS, Z.1, etc.) | 52 series | Monthly / Quarterly / Annual | `us_monthly` |

Key: `IMDR_ECON_FRED_KEY` (+ `IMDR_ECON_FRED_KEY2` for dual-key rotation via
`get_settings().econ_fred_key` + numbered-sibling pattern in `fred_http.py`).
GET to `https://api.stlouisfed.org/fred/series/observations`. Daily series history
deepened to 2010+ (~165k obs across FRED-US series). Includes 2 macro-PM additions:
Philly Fed Mfg Survey (`GACDFSA066MSFRBPHI`) + Dallas Fed Mfg Activity (`BACTSAMFRBDAL`).

---

## Cadence and orchestrator placement

### Monthly (`scripts/econ/us/us_monthly.py`)

```
python -m scripts.econ.us.us_monthly
```

Fans out to 16 fetchers (BLS ×5 + BEA ×4 + Census ×3 + Treasury MTS + BIS ×1 + FRED-US monthly ×1 + FRED-US seed sub-calls)
sequentially. `frequency_scope=["MONTHLY", "QUARTERLY", "ANNUAL"]` — quarterly
and annual fetchers included because MERGE on PK makes them idempotent; a
monthly run catches every release window without a separate quarterly scheduler.
BIS `bis_us` and `fred_us_monthly` were added to `us_monthly` 2026-06-23.

**Scheduler registration: WIRED 2026-06-23** — registered in
`scripts/imdr_monthly.py:PIPELINES` as `["python", "-m", "scripts.econ.us.us_monthly"]`,
running alongside KR/ID/AU/NZ/IN.

### Daily (`scripts/econ/us/us_daily.py`)

```
python -m scripts.econ.us.us_daily
```

Fans out to 3 Track-A fetchers (EIA energy spot + Treasury Debt-to-the-Penny + FRED-US daily) where
24h latency matters, plus Track B filings (`ingest_filings --since-days 7`).
`frequency_scope=["DAILY"]`. All Track A fetchers are idempotent — re-running
on weekends / holidays when no new data is published is harmless.
`fred_us_daily` was added to `us_daily` 2026-06-23 to put the 56 daily/weekly FRED-US
series on a scheduled refresh (previously loaded once from playground).

**Scheduler registration: WIRED 2026-06-23** — registered in
`scripts/imdr_daily.py:PIPELINES` as
`{"cmd": [sys.executable, "-m", "scripts.econ.us.us_daily"], "estimated_tags": 0}`.
`us_daily` ran end-to-end rc=0 on first scheduled run (EIA + Treasury-debt
idempotent MERGE, Track B filings all-skip on clean corpus).

---

## On-demand invocation

### Run the full daily or monthly orchestrator

```
python -m scripts.econ.us.us_daily
python -m scripts.econ.us.us_monthly
```

### Run a single fetcher

```
python -m scripts.econ.us.bls.bls_cpi
python -m scripts.econ.us.bea.bea_gdp
python -m scripts.econ.us.census.census_retail
python -m scripts.econ.us.treasury.treasury_mts
python -m scripts.econ.us.eia.eia_energy
```

### Per-fetcher CLI flags (all fetchers via `_runner.run_main`)

| Flag | Effect |
|---|---|
| `--since YYYY-MM-DD` | Filter observations to `obs_date >= this date` |
| `--until YYYY-MM-DD` | Filter observations to `obs_date <= this date` |
| `--no-parquet` | Skip parquet write and DB load; print summary only |
| `--no-load` | Write parquet but skip the DB MERGE step |

Examples:

```
# Check what BLS CPI would produce without writing anything
python -m scripts.econ.us.bls.bls_cpi --no-parquet

# Fetch only 2026 data, write parquet, skip DB load
python -m scripts.econ.us.bea.bea_gdp --since 2026-01-01 --no-load

# Full fetch + load for a single topic
python -m scripts.econ.us.census.census_retail
```

---

## Data archive layout

Parquet files land under `data/econ/us/{vendor}/{topic}/{YYYY}/{MM}/{DD}/`:

```
data/econ/
└── us/
    ├── bls/
    │   ├── cpi/2026/06/23/bls_cpi_20260623_1002_dim.parquet
    │   │                   bls_cpi_20260623_1002_fact.parquet
    │   ├── ppi/...
    │   ├── employment_situation/...
    │   ├── eci_jolts/...
    │   └── import_export_prices/...
    ├── bea/
    │   ├── gdp/...
    │   ├── personal_income/...
    │   ├── ita/...
    │   └── iip/...
    ├── census/
    │   ├── retail/...
    │   ├── trade/...
    │   └── housing/...
    ├── treasury/
    │   ├── mts/...
    │   └── debt/...
    └── eia/
        └── energy/...
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

It is safe to re-run any fetcher at any time. If BLS later revises a historical
CPI print, a re-run of `bls_cpi` will upsert the corrected value.

---

## Migrations applied

- **Migration 105 (`105_seed_us_econ_vendors.sql`) — APPLIED 2026-06-22.**
  Registered `bls`, `bea`, `census` (all `official_statistics`) and `treasury_us`
  (`official_ministry`, suffixed to disambiguate from `treasury_au`). `fred`
  (`official_cb`) and `eia` (`official_statistics`) already existed.
- **Migration 106 (`106_us_econ_reconcile_fred_source.sql`) — APPLIED 2026-06-23.**
  UPDATE-only; reversible. 26 exact-dup FRED mirror rows deactivated
  (`is_active=0`) in favour of source-agency rows. BLS price indices (PPI ×6 +
  import/export ×2) recategorised `other → cpi`. Active US indicators after
  reconcile: 188 (FRED 106 · BEA 36 · BLS 29 · Census 10 · EIA 3 · Treasury 4).
- **Completeness build-out — APPLIED 2026-06-23 (no new migration; code + seed only).**
  FRED-US scheduled fetchers added (56 daily + 52 monthly series via `seed_us.yml`);
  `seed_us.yml` generated from DB active-set — the 26 migration-106-deactivated source-dup
  series are excluded, verified still inactive after reload. BIS `bis_us` fetcher added
  (NEER+REER). Real PCE (DPCERX) added to `bea_personal_income`. **Active US indicators: 193
  (FRED-US scheduled adds ~5 net-new series via Philly Fed + Dallas Fed additions; BIS adds 2).**
  Total observations: ~198,775. Score: 15 ✅ / 1 ⚠ / 0 ❌.

---

## Failure modes

### Missing API key

**Symptom**: `ValueError: IMDR_ECON_BLS_KEY not set` (or `BEA_KEY`, `CENSUS_KEY`,
`EIA_KEY`) on startup.

**Fix**: Ensure `.env` contains the relevant key variable. Treasury is keyless.
Each connector raises a descriptive error pointing at the env var name if the key
is absent.

### BLS 20-year window cap

**Symptom**: Response truncated; series missing data before a cutoff date.

**Cause**: BLS caps each API call at a 20-year window (`startyear`/`endyear`).

**Fix**: `BlsClient` in `bls_http.py` chunks requests automatically by 20-year
slices. If a new fetcher appears to miss deep history, verify it is routing
through `BlsClient` and not issuing a single-window call.

### BEA 200-with-Error

**Symptom**: Fetcher silently returns zero observations despite an HTTP 200.

**Cause**: BEA returns errors inside the JSON body (`BEAAPI.Results.Error`) even
when the HTTP status is 200.

**Fix**: `BeaClient` checks for this field and raises explicitly. If you see zero
observations from a BEA fetcher, check structlog output for the BEA error message.

### Census activation-link gate

**Symptom**: Census EITS returns a 401 or redirect to an activation page.

**Cause**: Census API keys require email activation before use.

**Fix**: Ensure `IMDR_ECON_CENSUS_KEY` has been activated at the Census developer
portal. The activation email link must be clicked before the key is live.

### FK resolution failure in the loader

**Symptom**: Loader aborts with `FK miss for vendor / country / unit / category / frequency`.

**Fix**: The loader is loud — it prints the exact FK miss. Either correct the fetcher
output to use the canonical code, or add the missing dimension row via a migration.
Do not work around by disabling FK checks.

### Loader exits rc != 0

**Fix**: Re-run the loader directly on the parquet pair that was written:

```
python -m scripts.migrations.load_econ_indicator_from_playground \
    --vendor bls \
    --dim-parquet data/econ/us/bls/cpi/2026/06/23/bls_cpi_20260623_1002_dim.parquet \
    --fact-parquet data/econ/us/bls/cpi/2026/06/23/bls_cpi_20260623_1002_fact.parquet
```

The parquet files are on disk — no need to re-fetch from the vendor.

---

## Smoke-test commands

```
# Verify daily bundle runs end-to-end (writes parquet + loads DB)
python -m scripts.econ.us.us_daily

# Verify monthly bundle (13 fetchers)
python -m scripts.econ.us.us_monthly

# Spot-check a single fetcher without touching DB
python -m scripts.econ.us.bls.bls_cpi --no-load
python -m scripts.econ.us.bea.bea_gdp --no-load

# Confirm idempotency: re-run and expect 0 new DB rows
python -m scripts.econ.us.bls.bls_cpi
```

68 unit tests for the 5 connector modules pass as of the G.6 review gate
(2026-06-23).

---

## Scheduler wiring — LIVE (2026-06-23)

Both orchestrators are **registered** in the top-level schedulers as of 2026-06-23.
No new Windows Task Scheduler entry was needed — US rides the existing cadence.

### `scripts/imdr_monthly.py:PIPELINES` — entry now present

```python
["python", "-m", "scripts.econ.us.us_monthly"],
```

Runs all 13 monthly/quarterly/annual fetchers (BLS ×5 + BEA ×4 + Census ×3
+ Treasury MTS) on the monthly cron alongside KR, ID, AU, NZ, IN.

### `scripts/imdr_daily.py:PIPELINES` — entry now present

```python
{"cmd": [sys.executable, "-m", "scripts.econ.us.us_daily"], "estimated_tags": 0},
```

Runs EIA energy spot + Treasury Debt-to-the-Penny daily (Track A) and
`ingest_filings --since-days 7` (Track B). Entry sits with the other
non-Citi econ pipelines (after `scripts.econ.in.in_daily`).

**Operational note:** `imdr_daily.py` scheduled task must run under the conda
`imdr` env (Python 3.11). Track B ingest requires tiktoken and qdrant_client,
which are not available in the system Python 3.13 env. `sys.executable` binds
all subprocesses to whatever interpreter runs `imdr_daily.py` — no per-subprocess
env override needed, as long as the task is pointed at the `imdr` env's Python binary.
This is the same requirement India's Track B already imposes.

Migrations 105 and 106 are already applied — no further schema work is required.

---

## Playground status

The playground fetchers under `playground/econ/us/{fred,bls,bea,census,treasury,eia}/`
are intentionally preserved as the legacy sandbox. They were the development path
and remain useful for ad-hoc exploration, but they bypass the canonical loader
invocation (they write parquet only; DB load requires running
`load_econ_indicator_from_playground` separately). **For anything production-bound,
use `scripts/econ/us/` — not `playground/econ/`.**

FRED in `playground/econ/fred/` is the permanent home for the FRED connector — it
is not a playground-to-be-promoted item; it is the cross-country mirror layer by
design.

---

## Related

- [index.md](index.md) — US landing page + Track B (FOMC) document sources
- [us_coverage_plan.md](us_coverage_plan.md) — cell → exact source-ID mapping, build order, API mechanics, migrations
- [united_states_indicator_inventory.md](united_states_indicator_inventory.md) — wiring-map score, load counts, playground fetcher inventory
- [../macro_economy_wiring_map.md](../macro_economy_wiring_map.md) §7.1 — 4×4 coverage grid
- [../economics_data_ingest.md](../economics_data_ingest.md) — schema + per-vendor build log
- [../econ_to_prod.md](../econ_to_prod.md) §G — promotion playbook (Phase G steps completed 2026-06-23)
