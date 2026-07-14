# EIA — `playground/econ/us/eia/`

**Status:** Discovery built (playground). Dry-run clean. `EIA` vendor row already exists in `dbo.dim_vendor` — loads clean with no migration required. Not yet loaded into `econ.fact_indicator`. No `scripts/econ/us/` entry. Not wired into any orchestrator.

Energy Information Administration (EIA) v2 API. GET `https://api.eia.gov/v2/{route}/data/`, key `IMDR_ECON_EIA_KEY`. Offset/length pagination (5,000 rows/page). Response under `response.data[]`.

## Contents

| File | Purpose |
|---|---|
| `connector.py` | `EiaClient` — GET wrapper with auto-pagination via `offset`/`length`. `fetch_series()` accepts a route, frequency, facets dict, and optional `start_period` (ISO date string for client-side early-date trim). |
| `fetch_energy.py` | 3 daily energy spot price series — WTI, Brent, Henry Hub. Cell 2.1. |

## Series breakdown

### `fetch_energy` — 3 series (category `energy`, unit `usd`, daily, NSA)

| Route | EIA series ID | IMDR code | Description |
|---|---|---|---|
| petroleum/pri/spt | RWTC | EIA.ENERGY.WTI_SPOT.US | WTI Cushing Crude Oil Spot Price (USD per barrel) |
| petroleum/pri/spt | RBRTE | EIA.ENERGY.BRENT_SPOT.US | Europe Brent Crude Oil FOB Spot Price (USD per barrel) |
| natural-gas/pri/fut | RNGWHHD | EIA.ENERGY.HH_GAS_SPOT.US | Henry Hub Natural Gas Spot Price (USD per MMBtu) |

Unit is `usd` (present in `dbo.dim_unit`); per-unit basis (barrel vs MMBtu) is noted in `display_name`. The EIA series descriptions include the unit basis in their titles. WTI and Brent share the same route (`petroleum/pri/spt`); Henry Hub uses `natural-gas/pri/fut` despite being a spot price — that is the confirmed live route as of 2026-06-22.

## Gotchas

- **Henry Hub route is `natural-gas/pri/fut`, not `/spt`.** Despite RNGWHHD being a daily spot price, EIA's v2 API publishes it under the futures route. This was confirmed via live API exploration — do not change the route on the assumption it should be `/spt`.
- **EIA does not have a formal `start_period` query parameter.** The connector requests all data from offset 0 and filters client-side by `start_period` after the last page is received.
- **`EIA` vendor row already in `dbo.dim_vendor`.** No new vendor migration is needed for this fetcher — it can load via the standard playground loader once parquet is produced.
- **Daily series from 2015 → present is ~4,000 obs per series.** Weekend/holiday gaps are normal (EIA does not publish on non-trading days).

## Canonical loader

```bash
python -m playground.econ.us.eia.fetch_energy
# EIA vendor already registered:
python -m scripts.migrations.load_econ_indicator_from_playground --vendor eia
```

## Related

- [us_coverage_plan.md](../us_coverage_plan.md) — cells + build order
- [united_states_indicator_inventory.md](../united_states_indicator_inventory.md) — playground fetcher inventory
