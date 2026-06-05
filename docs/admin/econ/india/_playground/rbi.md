# RBI DBIE — `playground/econ/rbi/`

**Status:** Discovery + partial parquet. Not loaded. Playwright + XHR capture required (SPA, no public REST API).

Reserve Bank of India Database on Indian Economy. Single-Page App that makes XHR/fetch calls to an internal `CIMS_Gateway` endpoint with opaque payloads. Probe strategy: load SPA in headed Playwright, intercept network, dump request bodies + headers.

## Contents

| File | Purpose |
|---|---|
| `probe.py` | Open landing page, capture XHR/fetch requests, dump API patterns. |
| `probe_payloads.py` | Capture DBIE request bodies + headers via Playwright network interception. |
| `probe_click_through.py` | Click SPA menu items, capture `CIMS_Gateway` POST payloads per menu node. |
| `discovery/dbie_probe.json` | Captured XHR endpoints. |
| `discovery/dbie_probe.md` | "RBI DBIE Discovery" — endpoint inventory. |
| `discovery/dbie_payloads.json` | Captured POST bodies. |
| `discovery/findings.md` | "RBI DBIE Source-Discovery Findings" — overall summary. |
| `discovery/menu_full.json` | Full DBIE menu tree (table hierarchy). |
| `sample_output/2026/06/02/` | Parquet output (partial — FX + Bulletin only). |
| `profile/` | Playwright persistent context. |

## Transport

All three probe scripts are Playwright-driven. Network interception captures the XHR shape; once we have the request bodies for a given series, we can replay them via `httpx` for the bulk loader.

## DBIE → CIMS migration

DBIE is being phased out. **RBI CIMS** is the successor, split across 10 portals:
- BoP
- FLAIR (External Investment Position)
- SMS (Sectoral / Monetary Statistics)
- FED (Forex Exchange Database)
- CISBI (Centralised Information System for Banking Infrastructure)
- FIRMS (Foreign Investment Reporting and Management System)
- (and 4 others)

No firm deprecation date for DBIE. Probe work captured here should be re-validated against CIMS before committing to a daily-ingest path.

## What's been captured

Per [[project-econ-loaded]]:
- **RBI FX**: 5 indicators / 1305 metadata cells
- **RBI Bulletin**: 31 indicators / 168 metadata cells

Total: 36 indicators discovered, 1473 cells, 0 loaded.

## Next moves

1. Decide DBIE vs CIMS as the production endpoint (CIMS likely, but probe it first).
2. Confirm parquet shape matches `playground/econ/schema_prototype.py`.
3. Run canonical loader: `python -m scripts.migrations.load_econ_indicator_from_playground --vendor rbi`.

## Related

- [`rbi_explore.md`](rbi_explore.md) — captured screenshots + HTML snapshots
