# MODS NSDP — `playground/econ/mods/`

**Status:** Scaffolded, NOT loaded. MODS press-release PDFs are useful as research context but not as time-series sources.

KOSTAT's MODS (NSDP) is a press-release board, not an indicator catalogue. Each row is a dated PDF announcement. Useful for "what was the headline number on release day" but not for time-series work — for that, KOSIS is the right path.

## Contents

- **`fetch.py`** — Press-release PDF fetcher. GETs board listings, parses rows, downloads PDFs to SharePoint (`ResearchData1/IMDR/`). HTTP scraper with Playwright fallback for the initial board discovery (corp TLS reset).
- **`discover_bop.py`** — Discovery of MODS BoP-related boards. **Result: MODS does not carry BoP**. KOSTAT scope only; BoP is BOK-exclusive. See [[korea-mods-no-bop]].
- **`discovery/`** — board-structure captures under `discover_bop_{TIMESTAMP}/`.
- **`manifests/`** — per-board PDF download manifests.

## Why not loaded

MODS is press-release distribution. Each PDF announces a number; the time-series carrying that number lives in KOSIS. Loading MODS into `econ.fact_indicator` would duplicate KOSIS rows without adding history. Treat as a research corpus, not an econ source.

## If we ever wire it

- It's scraper-based (no API). PDF URLs are stable once you have the board ID.
- SharePoint convention: `ResearchData1/IMDR/research/kostat_mods/` (per the SharePoint scope rule [[feedback-sharepoint-research-scope]]).
- Better candidate: KOSTAT direct via KOSIS (most KOSTAT tables are mirrored at `orgId=101`).

## Related

- [`kosis.md`](kosis.md) — the right Korea-data path
- [`mods_explore.md`](mods_explore.md) — UI exploration artifacts
