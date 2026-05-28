# Shared Vendor Dimension (`dbo.dim_vendor`)

## Overview

`dbo.dim_vendor` is a shared cross-domain dimension table that tracks data vendors/sources. It provides a single reference point for recording which vendor supplied each observation.

## Schema

| Column | Type | Description |
|--------|------|-------------|
| `id` | INT (PK) | Auto-increment |
| `vendor_code` | VARCHAR(30) UNIQUE | Machine-readable key (e.g. `citi_velocity`) |
| `display_name` | VARCHAR(50) | Human-readable name (e.g. `Citi Velocity`) |
| `vendor_type` | VARCHAR(20) | Delivery type: `api`, `file`, `terminal` |
| `is_active` | BIT | Whether vendor is currently in use |

## Seed Values

| id | vendor_code | display_name | vendor_type |
|----|-------------|-------------|-------------|
| 1 | citi_velocity | Citi Velocity | api |
| 2 | barclays | Barclays | file |
| 3 | bidfx | BidFX | api |
| 4 | bloomberg | Bloomberg | terminal |

## Usage

### Current

- `rates.fact_swaption_skew` — has `vendor_id` FK (migration 017)
- `rates.fact_bench_rates` — has `vendor_id` FK (migration 020), resolved to `citi_velocity` at transform time

### Future Plan

Add `vendor_id` column to all existing fact tables:
- `fx.fact_ohlc` (currently BidFX + Citi, no tracking)
- `fx.fact_vol` (Citi Velocity)
- `rates.fact_observation` (Citi Velocity)
- `rates.fact_swaption_vol` (Citi Velocity)
- `commodities.fact_spot` (Citi Velocity)
- `commodities.fact_eia` (Citi Velocity)
- `commodities.fact_implied_vol` (Citi Velocity)
- `equities.fact_index_level` (Citi Velocity)
- `equities.fact_vix` (Citi Velocity)

Migration strategy: ALTER TABLE ADD vendor_id NULL → backfill → ALTER NOT NULL → ADD FK.

## Adding a New Vendor

```sql
INSERT INTO [dbo].[dim_vendor] (vendor_code, display_name, vendor_type)
VALUES ('refinitiv', 'Refinitiv', 'api');
```

The ORM model is at `src/imdr/models/vendor.py` (`DimVendor`).

## Migration

`migrations/018_create_dim_vendor.sql` — creates the table and seeds the initial 4 vendors.
