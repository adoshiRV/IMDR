# Cotality (formerly CoreLogic) — `playground/econ/cotality/`

Last updated: 2026-06-10

**Status:** DB-LIVE — 1 fetcher, **6 daily HVI indicators** loaded. New
vendor row in `dbo.dim_vendor` (`cotality`, id=69, vendor_type='web')
via migration 090. Domain rebranded `corelogic.com.au` → `cotality.com`
during 2025.

Why we care: ABS RPPI is quarterly. Cotality publishes a **daily**
Home Value Index — RBA cites it in every Financial Stability Review.
For high-frequency housing tracking this is the only free, traded-on
AU source.

## Contents

| File | Purpose |
|---|---|
| `fetch_hvi.py` | Playwright-renders `cotality.com/au/our-data/indices`, parses the daily HVI table, emits 6 daily-frequency `IndicatorRow`s + 1 obs each (today's value per series). |
| `profile_cotality/` | Per-run fresh Playwright profile (matches the RBA Akamai-bypass pattern). |
| `sample_output/` | Parquet snapshots per run. |

## Transport quirk

The Cotality indices page is server-rendered for chrome but the values
inside `<table>` elements are populated by JS on client. Plain `httpx`
returns the table headers with empty `<tbody>` — no useful data. We use
`playwright.sync_api` headed Chrome and wait on a `table tbody tr td`
selector before capturing `page.content()`.

## Loaded series

| IMDR code | Series |
|---|---|
| `COTALITY.HVI.SYDNEY.AU` | Daily HVI — Sydney, all dwellings |
| `COTALITY.HVI.MELBOURNE.AU` | Daily HVI — Melbourne |
| `COTALITY.HVI.BRISBANE.AU` | Daily HVI — Brisbane (incl. Gold Coast) |
| `COTALITY.HVI.ADELAIDE.AU` | Daily HVI — Adelaide |
| `COTALITY.HVI.PERTH.AU` | Daily HVI — Perth |
| `COTALITY.HVI.FIVE_CAPITAL_AGG.AU` | Daily HVI — 5-capital-city aggregate |

Frequency `DAILY`, unit `index`, category `housing`. Each run captures
ONE observation per series for today's date — daily reruns accumulate
the time-series in `econ.fact_indicator` via idempotent MERGE.

## Headline values (2026-06-10 snapshot)

| City | Today's index value |
|---|---:|
| Sydney | 244.6 |
| Melbourne | 182.6 |
| Brisbane | 236.6 |
| Adelaide | 236.8 |
| Perth | 220.7 |
| 5-capital aggregate | 225.0 |

## Next moves

1. Schedule daily fetch (Phase G — needs explicit user OK per `feedback_no_prod_wiring_without_permission.md`).
2. Optionally extend to the monthly table on the same page — 8 capitals × All Dwellings/Houses/Units (24 monthly series) — useful for the Houses-vs-Units split.

## Related

- [`../australia_indicator_inventory.md`](../australia_indicator_inventory.md) — backlog item 6 (CoreLogic) now ✅.
- [`../au_cb_documents.md`](../au_cb_documents.md) — RBA FSR references Cotality data each release.
