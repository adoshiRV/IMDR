# Korea — `_playground/` index

Pre-prod / discovery notes for everything under `playground/econ/{vendor}/` that feeds Korea data into IMDR.

| Vendor | Status | Notes |
|---|---|---|
| **KOSIS OpenAPI** | LIVE (2026-06-03) | [kosis.md](kosis.md) — 20 production fetchers, 164 indicators loaded |
| **REB R-ONE OpenAPI** | LIVE (2026-06-04) | [reb.md](reb.md) — weekly housing indices 2012→ |
| **BOK ECOS direct API** | Blocked (citizenship) | [bok_ecos.md](bok_ecos.md) — Playwright discovery only |
| **MODS NSDP press releases** | Scaffolded, not loaded | [mods.md](mods.md) — KOSTAT press-release PDF scraper |
| **BoP composition** | Reference | [bop.md](bop.md) — BPM6 framework + Korea Financial-Account item codes |
| **KOSIS UI exploration** | Discovery artifacts | [kosis_explore.md](kosis_explore.md) — page snapshots, no fetcher |
| **MODS UI exploration** | Discovery artifacts | [mods_explore.md](mods_explore.md) — page snapshots, no fetcher |

## Convention

These notes describe what's at `playground/econ/{vendor}/` — the *pre-prod* shape. As each vendor stabilises, the canonical reference moves up one level (e.g. `kosis_openapi_reference.md`) and this folder keeps only discovery + testing detail.
