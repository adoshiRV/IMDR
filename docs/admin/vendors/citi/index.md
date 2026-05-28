# Citi Velocity — Vendor Documentation

Last updated: 2026-05-13

IMDR's primary market-data vendor. Provides rates, FX, equity, and commodities data via the Citi Velocity Historical Data API.

- **[tag_catalog.md](tag_catalog.md)** — Complete inventory of all data available via the Citi Velocity `tagbrowsing` API, discovered 2026-03-11. 4 categories: RATES (28 subcats), FX (24), EQUITY (6), COMMODITIES (5).
- **[api_reference.md](api_reference.md)** — API endpoints, authentication (OAuth2 client-credentials), rate limits, `fetch_historical()` request shape, response format, and error handling.
- **[exploration/](exploration/)** — Frozen discovery snapshots, one per category/subcategory. Do not re-run the underlying scripts — results are cached in `data/cache/`.

## Quick links

| Domain | Live pipeline | Exploration doc |
|---|---|---|
| Rates (OIS/SWAP) | `rates.citi_live` | [exploration/rates_full.md](exploration/rates_full.md) |
| Rates (inflation) | `rates.inflation` | [exploration/rates_inflation.md](exploration/rates_inflation.md) |
| Rates (sov CMT) | planned | [exploration/rates_sov_cmt.md](exploration/rates_sov_cmt.md) |
| Rates (XCCY OIS) | planned | [exploration/rates_xccy_ois.md](exploration/rates_xccy_ois.md) |
| Rates (OIS meeting) | planned | [exploration/rates_ois_meeting.md](exploration/rates_ois_meeting.md) |
| FX (spot + forward) | `fx.citi_rate` | [exploration/fx_spot_forward.md](exploration/fx_spot_forward.md) |
| Equity | `equity.citi_live` | [exploration/equity.md](exploration/equity.md) |
| Commodities | `commodities.citi_live` | [exploration/commodities.md](exploration/commodities.md) |
