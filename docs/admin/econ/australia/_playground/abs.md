# ABS — `playground/econ/abs/`

**Status:** Discovery only. Not loaded.

Australian Bureau of Statistics. SDMX API is public and unauthenticated. CPI workbook fetcher prototyped, not yet wired into the canonical loader.

## Contents

| File | Purpose |
|---|---|
| `fetch.py` | Downloads ABS CPI workbook via SDMX API; extracts CPI series. |
| `explore.py` | Source-discovery script — validates real API endpoints for ABS Data Explorer. |
| `discovery/findings.md` | "ABS Source-Discovery Findings" — endpoint inventory. |
| `discovery/findings.json`, `samples/` | Raw discovery JSON + sample SDMX responses. |

## Transport

API-based. `httpx` client + SDMX XML parsing (`xml.etree`). No auth, no rate limit observed during discovery.

## Next moves (to go LIVE)

1. Match parquet shape to `playground/econ/schema_prototype.py` (dim + fact pair).
2. Confirm `country_iso=AU` populates correctly.
3. Run canonical loader: `python -m scripts.migrations.load_econ_indicator_from_playground --vendor abs`.
4. Add `abs` row to `dbo.dim_vendor` if not present.

## Coverage potential

ABS is the source-of-truth for AU real-economy series. Going native would replace the FRED-OECD mirrors with:
- CPI (headline + core + 11 subcategories) — currently OECD mirror only
- GDP expenditure components — currently OECD mirror only
- Labour force survey — currently OECD mirror only
- Retail sales
- Trade balance

## Related

- [`rba.md`](rba.md) — sibling AU vendor (monetary side)
