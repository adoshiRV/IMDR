# Stats NZ — `playground/econ/statsnz/`

**Status:** Discovery + parquet ready. Not yet loaded. 301 indicators discovered, 1622 metadata cells captured.

Statistics New Zealand. Three concurrent interfaces — REST API (`api.stats.govt.nz`), bulk CSV, legacy Infoshare. Per [[feedback-js-rendered-dont-bail]], release pages are JS-rendered: one Playwright pass with `networkidle` + 2s settle yields 6 download URLs per release.

## Contents

| File | Purpose |
|---|---|
| `explore.py` | Discovers working data interfaces; probes `api.stats.govt.nz`, bulk CSV, legacy Infoshare. |
| `discovery/findings.md` | "Stats NZ Source-Discovery Findings". |
| `discovery/findings_raw.json` | Raw discovery output. |
| `sample_output/2026/06/02/` | Parquet output (dim + fact pair) — ready for canonical loader. |
| `profile/` | Playwright browser cache (for JS-rendered release pages). |

## Transport

Mixed. `explore.py` validates 3 interfaces via `httpx`. JS-rendered release pages use Playwright (`profile/` is the cache). Bulk CSV is direct download once the URL is known.

## JS-rendering note

Per [[feedback-js-rendered-dont-bail]]: small-body HTTP response on a content-rich Stats NZ release page is **JS rendering**, not blocked. Don't bail — launch headed Playwright with `networkidle` + 2s settle. Confirmed 2026-05-something: 1 Playwright pass = 6 download URLs.

## Next moves

1. Confirm parquet shape matches `playground/econ/schema_prototype.py`.
2. Run canonical loader: `python -m scripts.migrations.load_econ_indicator_from_playground --vendor statsnz`.
3. Add `statsnz` row to `dbo.dim_vendor` if not present.

## Coverage potential

Stats NZ is the source-of-truth for NZ real-economy series. Would replace FRED-OECD mirrors with:
- CPI (headline + groups + 11 subgroups)
- GDP expenditure components
- HLFS labour force
- Retail trade
- Overseas trade

## Related

- [`rbnz.md`](rbnz.md) — sibling NZ vendor (monetary side)
