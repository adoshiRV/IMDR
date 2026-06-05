# RBA — `playground/econ/rba/`

**Status:** Discovery only. Not loaded. **Playwright required** (Akamai protection).

Reserve Bank of Australia statistical tables (rba.gov.au/statistics). Excel + CSV downloads only — no JSON API. Direct GET is blocked by Akamai; persistent Playwright profile is required.

## Contents

| File | Purpose |
|---|---|
| `fetch.py` | Downloads RBA Excel statistical tables; extracts rates/yields. Docstring explicitly calls out Playwright requirement. |
| `explore.py` | Discovery — extracts table links from `rba.gov.au/statistics`. |
| `discovery/webfetch_inventory.md` | "RBA Statistical Tables — Inventory" — table-by-table catalogue. |
| `discovery/samples/` | CSV samples per table. |
| `bulletin_downloads/` | Cached RBA bulletin PDFs (research context, not time-series). |
| `profile/` | Playwright persistent Chrome profile (Akamai bypass). |

## Transport

Playwright-based, headed. Persistent profile in `profile/`. GET to `rba.gov.au/statistics` without the profile = 403 / JS challenge. With the profile (warmed once) the download links work.

## Why Akamai-protected

RBA fronts statistics behind Akamai Bot Manager. Plain `requests`/`httpx` GET = blocked. Headed Playwright with persistent profile cookies = allowed. Treat the profile dir as part of the vendor's state — don't delete it casually.

## Next moves (to go LIVE)

1. Stabilise the Playwright profile path under `playground/econ/rba/profile/` (already there — confirm it survives a fresh checkout).
2. Standardise the Excel→parquet conversion (each RBA table has its own header layout).
3. Wire into the canonical loader: `python -m scripts.migrations.load_econ_indicator_from_playground --vendor rba`.
4. **Anti-detection guardrail:** per [[feedback-no-anti-detection-research]], do NOT add stealth plugins / automation-hiding flags / aggressive parallelism. If the profile breaks, warm a fresh one manually — don't try to evade.

## Coverage potential

RBA tables cover:
- Cash rate target + corridor (F1)
- Government bond yields by tenor (F2)
- Money market rates (F1)
- FX rates incl. TWI (F11)
- Banking aggregates (D)
- Monetary aggregates (D)

## Related

- [`abs.md`](abs.md) — sibling AU vendor (real-economy side)
