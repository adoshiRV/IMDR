# India — Agmarknet Mandi Prices (OGD / data.gov.in)

Last updated: 2026-06-22

> **STATUS: PRE-PROD.** The library, fetcher, and tests are built and reviewed.
> Migration 104 is drafted but NOT yet applied. The fetcher lives in
> `playground/` and is NOT wired into any production orchestrator.
> Do not treat any part of this pipeline as live until the gated steps below
> are signed off. See [§ Gated next steps](#gated-next-steps).

---

## Overview

Daily wholesale mandi (market) prices for ~3,000 mandis across India,
sourced via the **data.gov.in Open Government Data (OGD) REST API** for
the Agmarknet dataset. This is the comprehensive per-mandi price source —
every market, every commodity, every day — as opposed to the existing
UPAg IMC series, which is a lightweight weekly aggregate of 3–5 anchor
commodities across 4 sections (see [§ Coexistence with UPAg IMC](#coexistence-with-upag-imc)).

**Prices only.** This resource carries min/max/modal price (INR/quintal) per
market × commodity × date. It does **not** carry arrival quantities. Arrivals
data is available via a separate UPAg "Mandi Arrival Quantity" Dash path
(not yet built); the schema has a nullable `arrivals_tonnes` column reserved
for it when that work lands.

### Source facts

| Item | Value |
|---|---|
| API provider | data.gov.in — Open Government Data Platform India |
| Resource ID | `35985678-0d79-46b4-9ed6-6f13308a1d24` |
| Resource name | "Variety-wise Daily Market Prices Data of Commodity" (Agmarknet) |
| Coverage | ~80M rows of history; ~22,000 records/day at current run |
| Data lag | 1–2 days from market date |
| Price unit | INR / quintal |
| Arrivals | NOT present in this resource — deferred |

---

## API key

The data.gov.in platform uses **one personal API key per account**, shared
across all OGD resources (not scoped per-resource).

| Item | Value |
|---|---|
| Env var | `IMDR_DATA_GOV_IN_API_KEY` |
| Settings field | `src/imdr/config/settings.py` → `data_gov_in_api_key` |
| `.env.example` | Entry added |
| Registration | `https://data.gov.in/user/register` — free, personal account |

**Never commit the key value.** The HTTP connector (`src/imdr/connectors/http.py`)
redacts it from all log lines via `_redact_params` before any request is
logged. Tests verify this redaction explicitly (see [§ Tests](#tests)).

---

## Why a dedicated table (not `econ.fact_indicator`)

`econ.fact_indicator` is designed for ~1,000s of named macro indicators.
Agmarknet mandi data is a cube: `(arrival_date, market_id, commodity_id)` is
the grain, with 4 metrics per cell (min/max/modal price + arrivals). Full
coverage would generate 50,000–300,000 pseudo-indicator IDs, which would
pollute `dim_indicator` and make the table unqueryable for cross-country
macro work.

The decision (made in consultation with imdr-dbm) is a **dedicated star schema**
in `econ.` that mirrors the Agmarknet cube directly.

---

## Schema — migration 104 (DRAFT, NOT applied)

Migration file: `migrations/104_india_mandi_prices.sql` (drafted; must be
applied by a privileged account before `--load` can be used).

### Tables

**`econ.fact_india_mandi`** — fact table, grain `(arrival_date, market_id, commodity_id)`:

| Column | Type | Notes |
|---|---|---|
| `arrival_date` | DATE NOT NULL | Market date (not ingest date) |
| `market_id` | INT NOT NULL | FK → `econ.dim_india_mandi_market` |
| `commodity_id` | INT NOT NULL | FK → `econ.dim_india_mandi_commodity` |
| `price_min` | DECIMAL NOT NULL | INR/quintal |
| `price_max` | DECIMAL NOT NULL | INR/quintal |
| `price_modal` | DECIMAL NOT NULL | INR/quintal |
| `arrivals_tonnes` | DECIMAL NULL | Reserved; NULL until UPAg arrivals path built |
| `vendor_id` | INT NOT NULL | FK → `dbo.dim_vendor` ('ogd') |

Clustered PK is partition-aligned on `ps_india_mandi_annual` (annual
partitioning). PAGE-compressed. Two covering indexes on common query shapes
(market + date range; commodity + date range).

**`econ.dim_india_mandi_market`** — market dimension:

| Column | Notes |
|---|---|
| `market_id` | PK |
| `state` | State name as received from OGD |
| `district` | District name |
| `market` | Market/mandi name |
| `country_id` | FK → `dbo.dim_country` (IN) |

**`econ.dim_india_mandi_commodity`** — commodity dimension:

| Column | Notes |
|---|---|
| `commodity_id` | PK |
| `commodity` | Commodity name (e.g. "Wheat", "Onion") |
| `variety` | Variety name (NOT NULL DEFAULT '') |
| `grade` | Grade (NOT NULL DEFAULT '') |
| `commodity_code` | OGD commodity code |
| `group` | Commodity group |

**Seeds**: `dbo.dim_vendor` row `'ogd'` ("data.gov.in OGD (Agmarknet)") and
`dbo.dim_unit` row `'inr_qtl'` are seeded by migration 104.

**Volume estimate**: ~8M rows/year, ~1 GB/year compressed.

---

## Library

`src/imdr/domains/econ/ogd_mandi.py`

Key responsibilities:
- **API key loading** — reads from `settings.data_gov_in_api_key`; raises
  `ConfigurationError` if absent.
- **Retrying session** — wraps `imdr.connectors.http.HTTPClient`; retries on
  429 / 502 / 503 / 504 with backoff; key is redacted in all log output via
  `_redact_params`.
- **Pagination** — 1,000 records per page; `max_pages` guard to prevent
  runaway fetches on a large backfill window.
- **Record normalisation** — maps OGD field names to schema columns; coerces
  INR string prices to `Decimal`; emits a `MandiFact` dataclass per row.

---

## Fetcher (playground — NOT yet promoted)

`playground/econ/in/ogd/ogd_mandi.py`

### CLI flags

| Flag | Default | Notes |
|---|---|---|
| `--since DATE` | 5 days ago | Start of fetch window (catches 1–2 day lag) |
| `--until DATE` | today | End of fetch window |
| `--backfill-from DATE` | — | Triggers backfill mode; window capped at 366 days |
| `--no-load` | **default** | Writes parquet only; no DB touch |
| `--load` | — | Runs dim upserts + idempotent MERGE into fact table; aborts with a clear message if migration 104 has not been applied |

### Archive layout (--no-load)

```
data/econ/in/ogd/mandi/{YYYY}/{MM}/{DD}/
    mandi_{YYYY}-{MM}-{DD}.parquet
```

Files are written under `data/` which is gitignored.

### Idempotency

The `--load` path uses an idempotent MERGE on the fact PK
`(arrival_date, market_id, commodity_id)`. Re-running for the same date
window is safe and will not duplicate rows.

---

## Runtime smoke (--no-load, 2026-06-19)

```
Date: 2026-06-19
Rows fetched: 21,555
Pages: 22
Output: data/econ/in/ogd/mandi/2026/06/19/mandi_2026-06-19.parquet
```

---

## Security

- API key stored in `.env` only, never in source code.
- `src/imdr/connectors/http.py` `_redact_params` strips the key from all
  logged URLs and error messages before any output is written.
- Tests assert that the key value does not appear in log output (see test
  `test_key_redacted_in_logs` in the test suite below).

---

## Tests

`tests/unit/test_econ/test_ogd_mandi.py` — 44 tests, all passing.

Coverage includes:
- Record normalisation (field mapping, type coercion, NULL arrivals)
- Pagination logic (page boundary, max-pages guard)
- Retry behaviour (429 → backoff → retry; 502/503/504 similarly)
- Key-redaction assertion (key value absent from log output)
- `--load` MERGE path (dim upserts, fact MERGE, idempotency)
- `--load` guard when migration 104 is absent (clear error message)

---

## Coexistence with UPAg IMC

Both sources coexist and are intentionally kept:

| | OGD Agmarknet (this doc) | UPAg IMC |
|---|---|---|
| Granularity | Per-mandi × per-commodity × daily | National 4-section aggregate (~16 indicators) |
| History | ~80M rows | 8 anchor-date snapshots per run (~128 obs/run) |
| Cadence | Daily (1–2d lag) | Weekly |
| Table | `econ.fact_india_mandi` | `econ.fact_indicator` |
| Vendor | `ogd` | `upag` |
| Status | **PRE-PROD** | **PROD-LIVE** |
| Script path | `playground/econ/in/ogd/ogd_mandi.py` | `scripts/econ/in/upag/upag_imc.py` |

There is no key collision between the two sources — they use different
tables, vendor codes, and grains.

---

## Gated next steps

The following must happen in order before this pipeline goes to production:

1. **DBA applies migration 104** — creates `econ.fact_india_mandi`,
   `econ.dim_india_mandi_market`, `econ.dim_india_mandi_commodity`, seeds
   `dbo.dim_vendor 'ogd'` and `dbo.dim_unit 'inr_qtl'`.
2. **`--load` validation** — run `ogd_mandi.py --since 2026-06-17 --load`
   (or similar recent window) against the live DB; verify row counts, spot-check
   prices for a known market × commodity pair.
3. **Promote playground fetcher** — move `playground/econ/in/ogd/` →
   `scripts/econ/in/ogd/`; fix imports; clean `sys.path` hacks if any.
4. **Wire into `scripts/econ/in/in_daily.py`** — add the daily incremental
   call (default `--since` 5 days covers the lag); wire into `scripts/imdr_daily.py`
   after user OK per the no-prod-wiring-without-permission rule.

---

## Related

- [`index.md`](index.md) — India econ index (loading status / coverage)
- [`in_coverage_plan.md`](in_coverage_plan.md) — Cluster 4 agriculture section
- [`../macro_economy_wiring_map.md`](../macro_economy_wiring_map.md) — §7.12
  India, Cluster 4 / Input Costs cell
- [`india_prod_pipeline.md`](india_prod_pipeline.md) — Track A prod ops
  reference (existing prod fetchers)
- `src/imdr/domains/econ/ogd_mandi.py` — library
- `playground/econ/in/ogd/ogd_mandi.py` — fetcher (not yet promoted)
- `tests/unit/test_econ/test_ogd_mandi.py` — 44 unit tests
- `migrations/104_india_mandi_prices.sql` — schema migration (DRAFT, not applied)
