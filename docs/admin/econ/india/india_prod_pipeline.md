# India Econ — Production Pipeline

Last updated: 2026-06-19

Operations reference for the India economic data ingest that was prod-promoted
on 2026-06-19. For the broader India data landscape (sources, indicator
inventory, wiring map), see [index.md](index.md).

**Status: live as of 2026-06-19.** Two cadence-split orchestrators are wired
into `scripts/imdr_daily.py` and `scripts/imdr_monthly.py`. (The quarterly
orchestrator was folded into monthly 2026-06-19; see Monthly section below.)

---

## Architecture

```
Vendor API / portal / XLSX
  IMD daily rainfall portal          (imddrishti.imd.gov.in)
  BIS SDMX-JSON API                  (stats.bis.org/api/v2/)
  FAO FPI REST API                   (fao.org)
  RBI FX Reserves DBIE               (data.rbi.org.in/CIMS_Gateway_DBIE/)
  RBI Key Rates DBIE                 (data.rbi.org.in/CIMS_Gateway_DBIE/)
  MOSPI CPI XLSX release             (mospi.gov.in)
  MOSPI IIP XLSX release             (mospi.gov.in)
  DPIIT WPI XLSX release             (dpiit.gov.in)
  DPIIT 8-Core Industries XLSX       (dpiit.gov.in)
  CGA Monthly Accounts XLSX          (cga.nic.in)
  DGCIS MEIDB trade form POST        (dgciskol.gov.in)
  UPAg Plotly Dash callback          (dash.upag.gov.in)
  RBI Bulletin XLSX (headed Chrome)  (rbidocs.rbi.org.in)  *** requires display ***
  MOSPI NAS GDP XLSX                 (mospi.gov.in)
  UPAg MSP Dash callback             (dash.upag.gov.in)
  UPAg AIAPY Dash callback           (dash.upag.gov.in)
        │
        ▼
scripts/econ/in/{vendor}/{vendor}_{topic}.py   ← per-topic fetcher
        │
        ├─ run_fetch(since, until)              ← vendor pull; returns (indicators, obs)
        │
        ├─ write_parquet()                      ← dim/fact pair under data/econ/in/{vendor}/{topic}/{Y}/{M}/{D}/
        │
        └─ invoke_loader()                      ← MERGE INTO econ.dim_indicator + econ.fact_indicator
```

Every prod fetcher is a thin wrapper: it defines a `run_fetch(since, until)` callback
and calls `scripts.econ._runner.run_main(vendor, topic, fetch_fn, description, country_code="IN")`.
The runner owns CLI parsing, parquet write, and loader invocation. `country_code="IN"` is
mandatory — omitting it raises `TypeError`.

Domain library code lives in `src/imdr/domains/econ/`:

| Module | Purpose |
|---|---|
| `schema.py` | `IndicatorRow`, `ObservationRow`, `indicators_to_records`, `observations_to_records` |
| `mospi.py` | MOSPI listing API — discovers current XLSX release URLs for CPI / IIP / NAS |
| `upag.py` | UPAg Plotly Dash callback decoder — `POST /_dash-update-component`; handles binary Plotly `{dtype: "f8", bdata: base64}` y-arrays and anchor-date timeline format |

---

## Headed-Chrome constraint — RBI Bulletin

**`scripts/econ/in/rbi/rbi_bulletin.py` REQUIRES a headed Chrome session.**

RBI's Bulletin XLSX download endpoint (`rbidocs.rbi.org.in`) is protected by
Akamai TSPD bot-detection. The JS challenge requires a live browser context
with an active DOM — headless Chromium and persistent-cookie-only approaches
are both rejected. Consequences:

- The monthly orchestrator (`in_monthly.py`) **must run on a host with a
  display**. A headless CI server or a cron on a displayless Linux box will
  fail at the RBI Bulletin step.
- The recommended host is the same Windows machine used for other
  headed-Chrome fetchers (UBS Neo, BofA, etc.) — the same `data/econ/in/rbi/_profile`
  persistent Chrome profile is reused across bulletin runs.
- The XLSX cache lands at `data/econ/in/rbi/_downloads/` (gitignored via
  top-level `data/*` rule; relocated out of the scripts tree at prod-promotion).
- URL auto-discovery scrapes `BS_ViewBulletin.aspx` at run start — no
  monthly maintenance of hash-suffix URLs is required.
- If rbi_bulletin fails on a headless host, `_country_runner` continues with
  the remaining fetchers (failure-isolation semantics — see G.8 in
  [econ_to_prod.md](../econ_to_prod.md)) and sends an email with the bulletin
  pipeline listed under `failed_pipelines`.

---

## Cadence and orchestrator placement

### Daily (`scripts/imdr_daily.py:PIPELINES`)

```
python -m scripts.econ.in.in_daily
```

Wired into `scripts/imdr_daily.py:PIPELINES` 2026-06-19.
`frequency_scope=["DAILY"]`.

| Fetcher | Vendor | Series | Cadence |
|---|---|---|---|
| `scripts.econ.in.imd.imd_rainfall` | IMD | All-India aggregate rainfall (3 indicators) | DAILY (refreshed daily on the IMD portal during monsoon Jun-Sep; snapshot otherwise) |

### Monthly (`scripts/imdr_monthly.py:PIPELINES`)

```
python -m scripts.econ.in.in_monthly
```

Wired into `scripts/imdr_monthly.py:PIPELINES` 2026-06-19.
`frequency_scope=["MONTHLY", "WEEKLY", "DAILY", "QUARTERLY", "ANNUAL"]`.

Fans out to 15 fetchers sequentially. The three quarterly/annual fetchers
(`mospi_nas_gdp`, `upag_msp`, `upag_aiapy`) were originally in a separate
`in_quarterly.py` but were folded here 2026-06-19 — fetchers are idempotent
(MERGE on PK) so pulling quarterly/annual data every month is harmless and
avoids a separate trigger. RBI Bulletin runs last (slowest, headed-Chrome).

| Fetcher | Topics | Primary cadence |
|---|---|---|
| `scripts.econ.in.bis.bis_india` | BIS India — NEER/REER + Credit-to-GDP + DSR + CBPOL + Total Credit | DAILY/MONTHLY/QUARTERLY |
| `scripts.econ.in.fao.fao_fpi` | FAO Food Price Index (6 series) | MONTHLY |
| `scripts.econ.in.rbi.rbi_fx_reserves` | RBI FX Reserves via DBIE (5 components) | WEEKLY |
| `scripts.econ.in.rbi.rbi_key_rates` | RBI Key Rates via DBIE (Repo / SDF / Reverse Repo / CRR / SLR + others) | EVENT |
| `scripts.econ.in.mospi.mospi_cpi` | MOSPI CPI — 78 series (2024-base) | MONTHLY |
| `scripts.econ.in.mospi.mospi_iip` | MOSPI IIP — 20 series | MONTHLY |
| `scripts.econ.in.mospi.mospi_nas_gdp` | MOSPI NAS GDP — 35 series (GDP + 11 components × QoQ + YoY; FY + quarterly) | QUARTERLY + ANNUAL |
| `scripts.econ.in.dpiit.dpiit_wpi` | DPIIT WPI — 8 series | MONTHLY |
| `scripts.econ.in.dpiit.dpiit_core_industries` | DPIIT 8-Core Industries — 18 series | MONTHLY |
| `scripts.econ.in.cga.cga_monthly` | CGA Monthly Accounts — 30 fiscal line items | MONTHLY |
| `scripts.econ.in.dgcis.dgcis_trade` | DGCIS HS-2 trade — 198 indicators (98 HS chapters × Export + Import + TOTAL × 2 directions) | MONTHLY |
| `scripts.econ.in.upag.upag_imc` | UPAg IMC mandi prices — 16 indicators (4 sections × 3-5 commodities × 8 anchor dates) | WEEKLY |
| `scripts.econ.in.upag.upag_msp` | UPAg MSP — 28 crops × MSP level INR/Qtl | ANNUAL |
| `scripts.econ.in.upag.upag_aiapy` | UPAg AIAPY — 324 indicators (37 crops × 4 seasons × Area/Production/Yield, 1966-67 → 2025-26) | ANNUAL |
| `scripts.econ.in.rbi.rbi_bulletin` | RBI Bulletin — ~450 indicators across 23 tables (CPI · Call Money · IIP · Money Stock · Reserve Money · NEER/REER · WPI · RBI BS · FX Reserves · Foreign Trade · BoP T40 · NRI Deposits T34 + 11 more tables added 2026-06-18) | MONTHLY — **headed Chrome required** |

---

## On-demand invocation

### Run a full orchestrator

```
python -m scripts.econ.in.in_daily
python -m scripts.econ.in.in_monthly
```

### Run a single fetcher

```
python -m scripts.econ.in.mospi.mospi_cpi
python -m scripts.econ.in.rbi.rbi_bulletin
python -m scripts.econ.in.upag.upag_aiapy
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
python -m scripts.econ.in.mospi.mospi_cpi --no-parquet

# Fetch only 2026 DGCIS data, write parquet, skip DB load
python -m scripts.econ.in.dgcis.dgcis_trade --since 2026-01-01 --no-load

# Full fetch + load for a single fetcher
python -m scripts.econ.in.upag.upag_aiapy
```

---

## Data archive layout

Parquet files land under `data/econ/in/{vendor}/{topic}/{YYYY}/{MM}/{DD}/`:

```
data/econ/in/
├── bis/
│   └── india/2026/06/19/bis_india_20260619_1200_dim.parquet
│                         bis_india_20260619_1200_fact.parquet
├── mospi/
│   ├── cpi/2026/06/19/mospi_cpi_20260619_1205_dim.parquet
│   │                   mospi_cpi_20260619_1205_fact.parquet
│   └── iip/ ...
├── rbi/
│   ├── _profile/       ← headed Chrome persistent profile (gitignored)
│   ├── _downloads/     ← Bulletin XLSX cache (gitignored)
│   ├── rbi_bulletin/2026/06/19/ ...
│   └── rbi_fx_reserves/2026/06/19/ ...
├── dpiit/ ...
├── cga/ ...
├── dgcis/ ...
├── upag/ ...
├── fao/ ...
└── imd/ ...
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

It is safe to re-run any fetcher or orchestrator. DGCIS revises recent months (R-suffix
on columns); the latest fetch wins via MERGE.

---

## Failure modes

### RBI Bulletin — TSPD challenge on headless host

**Symptom**: `rbi_bulletin.py` exits non-zero; log shows `magic_bytes_rejected` or
`tspd_challenge_not_cleared`; obs returned = 0.

**Cause**: The orchestrator was run on a host without a display (CI server, headless
Linux). Akamai TSPD requires live JS execution in a headed browser.

**Fix**: Run `in_monthly.py` (or `rbi_bulletin.py` directly) on the Windows
desktop machine. The persistent Chrome profile at `data/econ/in/rbi/_profile` must
exist and have a valid post-challenge session cached. Re-run the fetcher manually
once to re-clear the challenge if the session has expired.

### DBIE auth rotation

**Symptom**: `rbi_fx_reserves` or `rbi_key_rates` exits non-zero;
`authorization` header rejected (HTTP 401 or empty response body).

**Cause**: DBIE `authorization` header value contains an epoch-microseconds
timestamp that may rotate per-session or per-day.

**Fix**: Replay the `security_generateSessionToken` + `login_getSapToken` bootstrap
flow. Reference: [`playground/econ/rbi/discovery/dbie_payloads.json`](../../../playground/econ/rbi/discovery/dbie_payloads.json).

### DGCIS CSRF rotation

**Symptom**: DGCIS trade returns HTTP 403 or empty rows on the trade-data POST.

**Cause**: DGCIS MEIDB rotates its CSRF token per GET request. Each POST must be
preceded by a GET to obtain a fresh token.

**Fix**: This is already handled inside `dgcis_trade.py` (GET then POST per
month-direction cycle). If 403 persists, check whether DGCIS has added a new
interstitial page or changed its CSRF-field name.

### FK resolution failure in the loader

**Symptom**: Loader aborts with `FK miss for vendor / country / unit / category / frequency`.

**Cause**: A dimension value in the fetcher output does not match any row in
`dbo.dim_vendor`, `dbo.dim_country`, `dbo.dim_unit`, `dbo.dim_category`, or
`dbo.dim_frequency`.

**Fix**: The loader is loud — it prints the exact FK miss. Either correct the fetcher
output to use the canonical code, or add the missing dimension row via a migration.
Do not work around by disabling FK checks.

**Historical note**: UPAg fetchers (`upag_imc`, `upag_msp`, `upag_aiapy`) were blocked
by this error until **migration 103** (`migrations/103_seed_upag_vendor.sql`) seeded the
`upag` vendor row in `dbo.dim_vendor`. Migration 089 had added other IN-session vendors
but omitted `upag`.

### Loader exits rc != 0

**Symptom**: Fetcher wrote parquet successfully but `invoke_loader()` returns non-zero.

**Fix**: Re-run the loader directly on the parquet pair that was written:

```
python -m scripts.migrations.load_econ_indicator_from_playground \
    --vendor mospi \
    --dim-parquet data/econ/in/mospi/cpi/2026/06/19/mospi_cpi_20260619_1205_dim.parquet \
    --fact-parquet data/econ/in/mospi/cpi/2026/06/19/mospi_cpi_20260619_1205_fact.parquet
```

The parquet files are on disk — no need to re-fetch from the vendor.

### DGCIS full backfill runtime

**Symptom**: First run of `dgcis_trade` takes ~10 minutes (290 POSTs × ~2s each).

**Cause**: Each POST is preceded by a GET (CSRF rotation); 145 months × 2 directions.
This is expected behaviour for the initial backfill. Subsequent monthly runs are fast
(only the latest ~6 months are re-fetched for revision-catch).

---

## Smoke-test commands

```
# Verify daily bundle (IMD rainfall — fast, no headed Chrome required)
python -m scripts.econ.in.in_daily

# Spot-check a single monthly fetcher without touching DB
python -m scripts.econ.in.mospi.mospi_cpi --no-load

# Verify DGCIS produces the correct obs count (no-parquet = fast dry run)
python -m scripts.econ.in.dgcis.dgcis_trade --no-parquet

# Test RBI Bulletin on a display-capable host
python -m scripts.econ.in.rbi.rbi_bulletin --no-load

# Confirm idempotency: re-run CPI and expect 0 new DB rows
python -m scripts.econ.in.mospi.mospi_cpi
```

---

## Playground status

The playground fetchers under `playground/econ/in/{vendor}/` are intentionally
preserved as the legacy sandbox. They were the development path and remain useful
for ad-hoc exploration, but they bypass the canonical loader invocation (they write
parquet only; DB load requires running `load_econ_indicator_from_playground`
separately). **For anything production-bound, use `scripts/econ/in/` — not
`playground/econ/in/`.**

Library code (`mospi.py`, `upag.py`) lives in `src/imdr/domains/econ/` and is shared
between playground and prod — no duplication.
