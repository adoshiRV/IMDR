# Cotality (formerly CoreLogic) — `scripts/econ/au/cotality/` (library: `src/imdr/domains/econ/cotality_hvi.py`)

Last updated: 2026-07-14

**Status:** DB-LIVE — 2 fetchers, **16 indicators / ~206 obs** loaded (DB-verified 2026-07-14: 6 daily HVI + 10 monthly HVI). New
vendor row in `dbo.dim_vendor` (`cotality`, id=69, vendor_type='web')
via migration 090. Domain rebranded `corelogic.com.au` → `cotality.com`
during 2025. Daily fetcher wired into `au_daily`; monthly fetcher wired
into `au_monthly` (added 2026-07-14).

Why we care: ABS RPPI is quarterly. Cotality publishes a **daily**
Home Value Index — RBA cites it in every Financial Stability Review.
For high-frequency housing tracking this is the only free, traded-on
AU source.

## Contents

| File | Purpose |
|---|---|
| `scripts/econ/au/cotality/cotality_hvi.py` | Daily fetcher — Playwright-renders `cotality.com/au/our-data/indices`, parses the daily HVI table, emits 6 daily-frequency `IndicatorRow`s + 1 obs each (today's value per series). |
| `scripts/econ/au/cotality/cotality_hvi_monthly.py` | **NEW 2026-07-14** — monthly fetcher reading the same rendered page's "Monthly Values" tab; emits 10 monthly-frequency `IndicatorRow`s + 1 obs each (latest published month-end value per region). One Playwright render serves both the daily and monthly parsers (`_fetch_html()` waits on both tab selectors before returning). |
| `profile_cotality/` (now `data/econ/au/cotality/profile/`) | Per-run fresh Playwright profile (matches the RBA Akamai-bypass pattern). |
| `sample_output/` | Parquet snapshots per run. |

## Transport quirk

The Cotality indices page is server-rendered for chrome but the values
inside `<table>` elements are populated by JS on client. Plain `httpx`
returns the table headers with empty `<tbody>` — no useful data. We use
`playwright.sync_api` headed Chrome and wait on a `table tbody tr td`
selector before capturing `page.content()`.

## Loaded series — daily

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

## Loaded series — monthly (NEW 2026-07-14)

`cotality_hvi_monthly.py` reads the same page's "Monthly Values" tab — a
superset of the daily table's 5 capitals, plus 3 more capitals (Darwin,
Canberra, Hobart) and a second Brisbane metro definition (ABS GCCSA
boundary, excluding Gold Coast) alongside the daily table's "Brisbane
(incl. Gold Coast)" cut:

| IMDR code | Series |
|---|---|
| `COTALITY.HVI_MONTHLY.SYDNEY.AU` | Sydney |
| `COTALITY.HVI_MONTHLY.MELBOURNE.AU` | Melbourne |
| `COTALITY.HVI_MONTHLY.BRISBANE.AU` | Brisbane (incl. Gold Coast) — same cut as the daily table |
| `COTALITY.HVI_MONTHLY.BRISBANE_GCCSA.AU` | Brisbane (ABS GCCSA boundary, excl. Gold Coast) — only available via this monthly tab |
| `COTALITY.HVI_MONTHLY.ADELAIDE.AU` | Adelaide |
| `COTALITY.HVI_MONTHLY.PERTH.AU` | Perth |
| `COTALITY.HVI_MONTHLY.FIVE_CAPITAL_AGG.AU` | 5-capital-city aggregate |
| `COTALITY.HVI_MONTHLY.DARWIN.AU` | Darwin — only available via this monthly tab |
| `COTALITY.HVI_MONTHLY.CANBERRA.AU` | Canberra — only available via this monthly tab |
| `COTALITY.HVI_MONTHLY.HOBART.AU` | Hobart — only available via this monthly tab |

Frequency `MONTHLY`, unit `index`, category `housing`, all dwellings only. Each run captures ONE observation per series for the latest published month-end date (no backfill — history accumulates forward from the first run, 2026-06-30).

**Investigated but not obtainable (2026-07-14):** confirmed against Cotality's own "Home Value Hedonic Indices FAQs" (Oct 2023) §5.1/§5.3 that Rent Value Index, Gross Rental Yield, and Total Return indices — while part of Cotality's published methodology (Table 1 of the index-series whitepaper) — are **subscriber-only** ("CoreLogic Indices — Research Pack"), as are the National / Combined Rest-of-State / Capital+Rest-of-state aggregates ("Full Research Indices suite"). No rent/yield/national table exists anywhere in the rendered DOM of the public page. The rent/vacancy gap is filled instead by SQM Research (see [`sqm.md`](sqm.md)).

## Headline values (2026-06-10 snapshot, daily)

| City | Today's index value |
|---|---:|
| Sydney | 244.6 |
| Melbourne | 182.6 |
| Brisbane | 236.6 |
| Adelaide | 236.8 |
| Perth | 220.7 |
| 5-capital aggregate | 225.0 |

## Next moves

1. Schedule daily fetch (Phase G — needs explicit user OK per `feedback_no_prod_wiring_without_permission.md`). **Monthly fetch built + wired into `au_monthly` 2026-07-14**; both still need `imdr_daily.py`/`imdr_monthly.py` scheduler registration (separate user sign-off gate).
2. ~~Optionally extend to the monthly table on the same page~~ — **done 2026-07-14**, see above. Rents/yield/national confirmed subscriber-only rather than pursued further.

## Related

- [`../australia_indicator_inventory.md`](../australia_indicator_inventory.md) — backlog item 6 (CoreLogic) now ✅; 4×4 tracker cells 4.2 / 1.1.
- [`../au_cb_documents.md`](../au_cb_documents.md) — RBA FSR references Cotality data each release.
- [`sqm.md`](sqm.md) — SQM Research rents + vacancy (NEW 2026-07-14), the demand-side complement to this price index.
