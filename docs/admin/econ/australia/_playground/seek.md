# SEEK — `scripts/econ/au/seek/` (library: `src/imdr/domains/econ/seek_jobads.py`)

Last updated: 2026-07-14

**Status:** DB-LIVE — 1 fetcher, **90 indicators / 14,526 obs** loaded (DB-verified 2026-07-14). New vendor row `seek` (`vendor_category='data_vendor'`, same model as `tradingeconomics`) via migration 109. Wired into `au_monthly`.

Why we care: SEEK's Job Ad Index and Advertised Salary Index are byproducts of Australia's dominant job-listings marketplace — a real-time, market-based leading indicator of labour demand and wage pressure that predates the official ABS Job Vacancies release by weeks.

## Source

`https://au.seek.com/about/news/article/seek-employment-data` — a server-rendered React page, so plain `httpx` works with no Playwright. **Note the hostname**: `au.seek.com` (this page) is reachable with a plain GET, while `www.seek.com.au` returns a 403 at the edge for the same request (confirmed not a general network issue — other sites returned 200 from the same client in the same session).

The page embeds two "Download the latest ... data here" links pointing at Hygraph/GraphCMS asset storage (`ap-southeast-2-seek-apac.graphassets.com`). Each link is a *content-hashed* URL that changes with every monthly release, so the fetcher re-scrapes the report page every run rather than hardcoding a download URL.

## Series

**SEEK Job Ad Index** (`AU_PUBLISHED_DATASET *.xlsx`, sheet "SEEK Job Ad Index") — monthly, 2001-07 → present. Australia only (no NZ in this file). Dimension: national Total + 8 states/territories (ACT/NSW/NT/QLD/SA/TAS/VIC/WA) — **no industry breakdown** in this workbook. Two variants per cut: seasonally adjusted and trend. Index base = 2016 average = 100.

| IMDR code | Series |
|---|---|
| `SEEK.JOBADS.INDEX.{NATIONAL\|STATE_x}.AU` | Job Ad Index, seasonally adjusted |
| `SEEK.JOBADS.INDEX_TREND.{NATIONAL\|STATE_x}.AU` | Job Ad Index, trend |

(National + 8 states) × 2 variants = **18 series**.

**SEEK Advertised Salary Index** (`seek_asi_*_upload.xlsx`, single sheet) — monthly, 2015-11 → present. Australia only. Two *separate* dimension cuts share one flat table: a state cut (`state` ≠ Total, `classification` == Total) and an industry/classification cut (`state` == Total, `classification` ≠ Total, 27 industries per SEEK's own taxonomy) — confirmed no state × industry cross-tab exists (0 rows with both non-Total). Plus one combined national headline row. Same SA/trend variant split.

| IMDR code | Series |
|---|---|
| `SEEK.SALARY.INDEX.{NATIONAL\|STATE_x\|IND_x}.AU` | Advertised Salary Index, seasonally adjusted |
| `SEEK.SALARY.INDEX_TREND.{NATIONAL\|STATE_x\|IND_x}.AU` | Advertised Salary Index, trend |

(National + 8 states + 27 industries) × 2 variants = **72 series**.

**Total: 18 + 72 = 90 indicators.**

## Not built (out of scope)

- SEEK Applications-per-Ad Index (candidate competition per ad, present in the same employment workbook, third sheet) — not ad volume/salary, out of scope for this fetcher.
- NZ data — SEEK also runs `nz.seek.com` but this workbook is AU-only; a distinct NZ dataset would need its own investigation.

## Known workaround

The salary workbook has a broken embedded-drawing relationship (points at a stripped `xl/drawings/drawing1.xml` not present in the zip) which raises `KeyError` in stock `openpyxl` on load — monkeypatched around in `_load_workbook` (swallows the `KeyError` from `find_images` and returns empty image lists).

## Related

- [`../australia_indicator_inventory.md`](../australia_indicator_inventory.md) — 4×4 tracker cell 1.4
- [`anz.md`](anz.md) — sibling non-official labour-market leading indicator (ANZ-Indeed Job Ads)
- ABS Job Vacancies (`abs.md`) — the official-source counterpart this triangulates against
