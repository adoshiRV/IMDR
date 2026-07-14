# ANZ-Indeed Australian Job Ads — `scripts/econ/au/anz/` (library: `src/imdr/domains/econ/anz_indeed_jobads.py`)

Last updated: 2026-07-14

**Status:** DB-LIVE — 1 fetcher, **3 indicators / 1,854 obs** loaded (DB-verified 2026-07-14). Reuses the pre-existing `anz` vendor row (ANZ Research is already an AU econ vendor for other series). Wired into `au_monthly`.

Why we care: ANZ-Indeed Australian Job Ads is the successor to ANZ's long-running "Job Advertisements" series, co-produced with Indeed's Hiring Lab. It's a second, methodologically-independent read on job-ad volumes alongside SEEK's (see `seek.md`), and its history is much longer (1975 vs SEEK's 2001).

## Investigation (2026-07-14)

Two candidates considered:

1. **Indeed Hiring Lab open data** (`github.com/hiring-lab/job_postings_tracker`, `AU/aggregate_job_postings_AU.csv` + `AU/job_postings_by_sector_AU.csv`) — Indeed's own *raw* postings-volume index, daily, 2020-02 → present, CC-BY licensed, no auth. Real and freely downloadable, but this is Indeed's global "Job Postings Index" product, **not** the branded ANZ-Indeed series (different base, different methodology, national+sector only for AU, no state cut).
2. **ANZ Research release** — the branded monthly series. Guessed `anz.com`/`anz.com.au` URLs 404'd (not a network block — the same client got 200s from `anz.com.au/bluenotes/`, `github.com`, `duckduckgo.com` in the same session), but the newsroom archive page `https://www.anz.com.au/newsroom/media/release-dates/` is reachable with a plain GET and embeds a "Download data" link to a structured XLSX — the same idiom as SEEK (see `seek.md`): a stable landing page, scraped every run, pointing at a content-dated download URL that changes with each monthly release.

Chose (2): ANZ's own official series, full history back to the newspaper-ad era spliced through internet ads to today's Indeed-sourced methodology, monthly, base 2019=100, Original + Seasonally Adjusted + Trend cuts. Confirmed via the downloaded workbook: 1975-01 → 2026-06 (619 monthly obs), single sheet `ANZ-Indeed Australian Job Ads` (the `% mm` / `% yy` sheets are derived growth-rate transforms of the same three series — not ingested).

## Series

National only — no state or industry/occupation breakdown is published in this workbook (the monthly release PDF's prose mentions state colour, e.g. "Job Ads in New South Wales rose the most", but does not tabulate it).

| IMDR code | Series |
|---|---|
| `ANZ.JOBADS.INDEX.NATIONAL.AU` | Seasonally Adjusted, 2019=100 |
| `ANZ.JOBADS.INDEX_ORIG.NATIONAL.AU` | Original |
| `ANZ.JOBADS.INDEX_TREND.NATIONAL.AU` | Trend |

**3 indicators**, monthly, 1975-01 → present (619 obs each).

## Not built (out of scope)

- Indeed Hiring Lab's own AU CSVs (candidate 1 above) — a distinct, differently-based dataset; a future fetcher could add it separately (e.g. under an `indeed` vendor) rather than conflating it with this series.

## Transport

Plain `httpx.Client` GET on the release-dates archive page → regex-match the "Download data" XLSX link → plain GET for the XLSX → `openpyxl` parse. No auth, no Playwright.

## Related

- [`../australia_indicator_inventory.md`](../australia_indicator_inventory.md) — 4×4 tracker cell 1.4
- [`seek.md`](seek.md) — sibling non-official labour-market leading indicator (SEEK Job-Ad/Salary indices)
