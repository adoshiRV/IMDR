# 01 — Global product master (`dbo.dim_product`) + vendor-ticker registry

- **Date filed**: 2026-05-15
- **Status**: design DRAFT — awaiting sign-off before migrations land
- **Triggered by**: HKMA Aggregate Balance ingest (no `macro` schema exists
  yet). Decision to build the indicator master cross-domain in `dbo`
  rather than `macro` so FX/rates/equity/commodities products can adopt
  the same registry over time.
- **Numbering note**: first dev doc using the new `NN_` prefix
  convention. Future development docs continue `02_`, `03_`, …

## Problem

A consumer who only sees the database tables comes to IMDR with a
vendor-native identifier — a BBG ticker, a FRED series, a Citi tag —
and wants to find the data. Today:

- Rates and FX vendor-native identifiers live in
  [src/imdr/universe/rates.yml](../../../src/imdr/universe/rates.yml)
  and `fx.yml`. They are not queryable from SQL.
- There is no schema concept of "product" — each domain rolls its own
  dim (`fx.dim_currency_pair`, `rates.dim_curve`, etc.).
- Macro has no schema at all (`src/imdr/domains/macro/` is a stub).

Result: every consumer encodes the vendor-ticker → IMDR-identity
mapping in client code. There is no SQL-level discovery path.

## Goal

A small set of `dbo.` tables that let any consumer:

1. Resolve a vendor-native ticker → IMDR product identity.
2. Discover which vendors have data for a given product.
3. Query the underlying fact for any subset of those vendors.

Without forcing a choice of vendor. The schema surfaces options; the
consumer picks.

## Schema

Three new tables. None of them are macro-specific; macro is just the
first domain to adopt them.

### `dbo.dim_product` — canonical product identity

One row per product. Initially seeded with macro indicators; future
work extends to FX pairs, rates curves, equity tickers, etc.

| Column | Type | Notes |
|---|---|---|
| `id` | `INT IDENTITY` | PK. |
| `imdr_code` | `VARCHAR(40) NOT NULL UNIQUE` | Dotted IMDR-side identifier, e.g. `HKMA.AGG_BAL`. Human shorthand; no code parses it. |
| `display_name` | `VARCHAR(160) NOT NULL` | `HKMA Aggregate Balance`. |
| `description` | `VARCHAR(800) NULL` | One-paragraph definition. |
| `product_type` | `VARCHAR(20) NOT NULL` | `MACRO_INDICATOR` for v0.1. Future: `FX_PAIR`, `RATES_CURVE`, `EQ_TICKER`, `COMM_FUTURE`. CHECK-constrained. |
| `category` | `VARCHAR(20) NULL` | Within product_type. For MACRO_INDICATOR: `LIQUIDITY`, `CB_FACILITY`, `CB_BS`, `GOV_BALANCE`, `INSTR_OUTSTAND`, `CB_RATE`. |
| `central_bank_id` | `TINYINT NULL` | FK → `dbo.dim_central_bank(id)`. NOT NULL for CB-issued indicators. |
| `country_id` | `TINYINT NOT NULL` | FK → `dbo.dim_country(id)`. |
| `currency_id` | `SMALLINT NULL` | FK → `dbo.dim_currency(id)`. NULL when not currency-denominated. |
| `value_scale` | `VARCHAR(5) NOT NULL DEFAULT 'UNIT'` | `UNIT` / `K` / `MM` / `BN`. |
| `value_type` | `VARCHAR(10) NOT NULL` | `AMOUNT` / `RATE_PCT` / `RATE_BPS` / `RATIO` / `COUNT`. |
| `frequency_id` | `TINYINT NOT NULL` | FK → `dbo.dim_frequency(id)`. |
| `source_url` | `VARCHAR(400) NULL` | Canonical publication URL. |
| `is_active` | `BIT NOT NULL DEFAULT 1` | Soft-delete. |
| `created_at`, `updated_at` | `DATETIMEOFFSET` | Standard. |

No `bbg_ticker` column. No `primary_vendor_id`. The dim does not take
a side on which vendor is canonical.

### `dbo.dim_central_bank` — central bank master

One row per central bank. Lifted to `dbo` because it's referenced from
`dim_product` and will be referenced from future tables (CB meetings,
CB balance sheet observations, policy-rate fixings).

| Column | Type | Notes |
|---|---|---|
| `id` | `TINYINT IDENTITY` | PK. |
| `cb_code` | `VARCHAR(10) NOT NULL UNIQUE` | `HKMA`, `FED`, `ECB`, `BOJ`, `BOE`, `PBOC`, `RBA`, `RBI`, … |
| `display_name` | `VARCHAR(120) NOT NULL` | `Hong Kong Monetary Authority`. |
| `country_id` | `TINYINT NOT NULL` | FK → `dbo.dim_country(id)`. ECB → `EU` pseudo-country. |
| `currency_id` | `SMALLINT NOT NULL` | FK → `dbo.dim_currency(id)`. Primary issuing currency. |
| `website_url` | `VARCHAR(400) NULL` | Stats portal homepage. |
| `created_at`, `updated_at` | `DATETIMEOFFSET` | Standard. |

Seeded with 8 rows at migration time: HKMA, FED, ECB, BOJ, BOE, PBOC,
RBA, RBI.

### `dbo.dim_product_vendor` — vendor-ticker registry

One row per (product, vendor) we have data for. This is the discovery
layer — the table a consumer queries when they have a vendor ticker
and want to find what IMDR has.

| Column | Type | Notes |
|---|---|---|
| `id` | `INT IDENTITY` | PK. |
| `product_id` | `INT NOT NULL` | FK → `dbo.dim_product(id)`. |
| `vendor_id` | `TINYINT NOT NULL` | FK → `dbo.dim_vendor(id)`. |
| `vendor_ticker` | `VARCHAR(80) NOT NULL` | Native vendor identifier — `HKMAAGGB Index`, `WALCL`, Citi tag, HKMA portal field ID. |
| `notes` | `VARCHAR(400) NULL` | E.g. "Stale after 2024", "Same series, BBG ticker differs from FRED". |
| `created_at`, `updated_at` | `DATETIMEOFFSET` | Standard. |

Indexes:
- `UQ(product_id, vendor_id)` — one mapping per (product, vendor).
- `UQ(vendor_id, vendor_ticker)` — a vendor ticker resolves to exactly
  one product.

No `is_primary` flag. No "canonical vendor" hint. Surfacing the choice,
not forcing one.

## Discovery query patterns

The three queries this design must answer cleanly, with the schema
above:

### Q1 — "I have a BBG ticker, what does IMDR call it?"

```sql
SELECT p.imdr_code, p.display_name
FROM dbo.dim_product_vendor pv
JOIN dbo.dim_product p ON p.id = pv.product_id
JOIN dbo.dim_vendor v ON v.id = pv.vendor_id
WHERE v.vendor_code = 'BBG'
  AND pv.vendor_ticker = 'HKMAAGGB Index';
```

### Q2 — "What sources do we have for this product?"

```sql
SELECT v.vendor_code, pv.vendor_ticker, pv.notes
FROM dbo.dim_product_vendor pv
JOIN dbo.dim_vendor v ON v.id = pv.vendor_id
WHERE pv.product_id = (
    SELECT id FROM dbo.dim_product WHERE imdr_code = 'HKMA.AGG_BAL'
);
-- → returns one row per vendor we have, with their native ticker.
--   The consumer sees the options and decides.
```

### Q3 — "Give me the time series (any/all vendors)"

```sql
SELECT obs_date, vendor_id, observed_value
FROM macro.fact_indicator
WHERE product_id = 42
ORDER BY obs_date, vendor_id;
```

If the consumer wants only one source, they filter `vendor_id`. If they
want to reconcile, they don't.

A thin convenience view — proposed `dbo.v_product_coverage` — collapses
Q2 + first/last obs date + obs count into one row per (product,
vendor). Useful, not required by the design.

## What this solves

- **`vendor-ticker → product` resolution.** Q1. SQL-only, no client
  code needed.
- **`product → vendors available` discovery.** Q2. The consumer sees N
  vendors, decides for themselves.
- **Multi-vendor storage.** Already handled by `fact.vendor_id`; the
  registry table makes it discoverable.
- **Cross-domain reuse.** Same three tables serve macro today; FX,
  rates, equity, commodities can adopt them in later migrations
  without schema change here.

## What this does NOT solve

Worth being explicit so a future reader doesn't expect it to:

- **Vendor-ticker history / renames.** If BBG renames a ticker
  mid-history, the schema stores one current `vendor_ticker` per
  (product, vendor). Old tickers can live in `notes` or as a second
  row. A proper alias table is a v0.2 problem.
- **"Equivalent but not identical" products across vendors.** E.g. one
  vendor publishes close-of-day, another publishes intraday-last. The
  schema treats them as the same product if mapped that way — the
  semantic difference lives in vendor-level docs, not the registry.
- **Cross-product relationships (families/surfaces).** A swaption vol
  surface is many `(expiry, tenor)` points sharing a parent. This
  schema is flat. Hierarchical relationships are out of scope.
- **Retroactive adoption by existing domains.** `rates.dim_curve`,
  `fx.dim_currency_pair`, etc. continue to exist; this design does
  not migrate them. A future project plans the unification.
- **Vendor preference / "which one should I use".** Intentional — see
  the rationale in the next section.

## Why no "primary vendor" hint

Considered: `primary_vendor_id` on `dim_product`, or `is_primary` on
`dim_product_vendor`. Rejected. Reasons:

1. The right vendor depends on the question (history depth, latency,
   revision policy) — the dim can't encode that for every use case.
2. Hard-coding a primary creates a hidden default that quietly skews
   downstream analytics. A view that filters by `primary` looks like
   "the answer" but is just one of several valid answers.
3. The cost of asking the consumer to pick is one extra `WHERE
   vendor_id = ?` clause in Q3. Cheap.

If a specific use case needs a default vendor, it lives in that
pipeline / report / view, not on the dim.

## Migrations

Sequential, all additive:

1. `053_create_dbo_dim_central_bank.sql` — table + 8-row seed.
2. `054_create_dbo_dim_product.sql` — table.
3. `055_create_dbo_dim_product_vendor.sql` — table.

Then the macro fact follows in a subsequent dev doc:

4. (separate dev doc) `056_create_macro_fact_indicator.sql` + seed +
   HKMA scraper + FRED backfill.

## Open questions before migrations land

1. **Naming**: `dbo.dim_product` vs `dbo.dim_instrument` vs
   `dbo.dim_series`. "Product" is broad but fits everything from FX
   pair to macro indicator; "instrument" reads more financial but
   doesn't fit macro cleanly; "series" reads time-series-y. Current
   pick: `dim_product`.
2. **`product_type` enum scope**: only `MACRO_INDICATOR` seeded for
   v0.1. CHECK constraint should list all anticipated values from day
   one to avoid an ALTER per domain adoption.
3. **`dim_central_bank` worth ~20 rows of dim?** Yes — the CB anchor
   pays off when we add CB-level facts (meetings, balance sheets,
   policy rates) and gives us a natural join target.
4. **`dim_vendor` rows needed**: `HKMA`, `FRED` (web/API scrapes for
   central-bank-published series). Confirm naming convention with
   existing `CITI`, `BIDFX`, `bloomberg` rows — see the parallel
   `dim_vendor_cleanup.md` follow-up.

## Status / next steps

- [ ] Sign-off on the schema shape above.
- [ ] Sign-off on naming (`dim_product` vs alternatives).
- [ ] Sign-off on `product_type` initial CHECK enum.
- [ ] Write migrations 053–055.
- [ ] Then move to the macro-fact dev doc (separate file, next in
      sequence: `02_`).
