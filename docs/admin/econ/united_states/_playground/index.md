# US Econ — playground vendor index

**Status:** Track A + Track B discovery complete (2026-06-22). All fetchers produce loader-valid parquet via `--dry-run`. Nothing promoted to `scripts/econ/us/`; nothing wired into any orchestrator. Promotion is gated on migration 105 (vendor row registration for BLS/BEA/CENSUS/TREASURY).

## Track A — time-series vendors

| Vendor | Note | Cells |
|---|---|---|
| [fred.md](fred.md) | FRED — 173 indicators LIVE in `econ.fact_indicator`; playground-resident + unpromoted | All baseline (132 US-specific + 41 OECD mirrors) |
| [bls.md](bls.md) | BLS Public Data API v2 — 5 fetchers, 29 series across CPI / PPI / employment / ECI+JOLTS / trade prices | 1.4 · 2.1–2.4 · 3.1 |
| [bea.md](bea.md) | BEA JSON API — 4 fetchers, 36 series across GDP / personal income / ITA / IIP | 1.1 · 1.4 · 2.4 · 3.2 · 3.3 |
| [census.md](census.md) | Census EITS + intltrade — 3 fetchers, 10 series across retail sales / goods trade / housing | 1.1 · 1.3 |
| [treasury.md](treasury.md) | Treasury Fiscal Data (keyless) — 2 fetchers, 4 series across MTS fiscal flows + debt-to-penny | 1.2 · 4.2 |
| [eia.md](eia.md) | EIA v2 — 1 fetcher, 3 daily energy spot prices (WTI / Brent / Henry Hub). EIA vendor row already in `dbo.dim_vendor`. | 2.1 |

## Track B — government document probes (`playground/econ/us/govt/`)

Discovery-only (no `econ.fact_indicator` writes). Fetchers write manifest snapshots (title/url/date/doc_type) to `data/snapshots/{YYYY-MM-DD}.json`. These feed the research-document pipeline (`research.dim_report` + Qdrant), not the time-series schema.

| Probe file | Stream |
|---|---|
| `probe_fomc_statements.py` | FOMC policy statements (per-meeting) |
| `probe_fomc_minutes.py` | FOMC minutes (3-week lag after meeting) |
| `probe_fomc_sep.py` | Summary of Economic Projections / dot-plot (quarterly) |
| `probe_fed_speeches.py` | Fed speeches and congressional testimony |
| `daily_pull.py` | Orchestrator: runs all probes, deduplicates against `seen.json`, writes daily manifest |

Full Track B source taxonomy (Fed / FOMC / 12 regional banks / Treasury / BLS / BEA / Census / CBO / OMB / FDIC / OCC, Tier 1/2/3): [`us_govt_doc_sources.md`](../us_govt_doc_sources.md).

## Gaps (acknowledged — do not block)

- **ISM PMI** (Mfg + Services) — subscription only; cell 1.4 PMI leg stays ❌.
- **Treasury TIC** foreign holdings — CSV/XML at `home.treasury.gov`, not in the Fiscal Data API. Cell 3.3 flow is covered by BEA ITA; TIC stock is a deferred scrape.

## Related

- [us_coverage_plan.md](../us_coverage_plan.md) — cell → exact source-ID mapping + build order
- [united_states_indicator_inventory.md](../united_states_indicator_inventory.md) — wiring-map score + full fetcher inventory
