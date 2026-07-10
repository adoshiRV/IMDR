# Cabinet Office ESRI (QE) — `playground/econ/jp/esri/`

**Status:** GDP fetcher built (2026-06-22). The **live GDP source** — supersedes the stale e-Stat SNA (ends 2007Q1) and the thin `FRED.GDP.REAL.JP` mirror (backup only).

Cabinet Office ESRI publishes the **QE速報** (Quarterly Estimates of GDP, preliminary), the market-watched release ~6 weeks after quarter-end. Not on the e-Stat API — fetched directly from `esri.cao.go.jp`.

## Mechanism (`_esri_qe.py`)
- **`discover_latest_release()`** — parses `…/jp/sna/sokuhou/sokuhou_top.html` for the current release dir (regex `files/{YYYY}/(qe\d+_\d+)/gde…\.html`); newest by (year, code). Derives the CSV version suffix as `release.replace("qe","").replace("_","")` (e.g. `qe261_2` → `2612`). Version bumps each quarter — re-discovered every run.
- **`download_table(name, release)`** — GET `…/{release}/tables/{name}{ver}.csv`, decode **Shift-JIS (cp932)**.
- **`parse_qe_wide(text)`** — the CSV is wide with a 7-row bilingual header, then quarterly rows. Time label in col 0: a year-start row reads `YYYY/ 1- 3.`, follow-on rows `4- 6.`/`7- 9.`/`10-12.` (year carried forward). Footnote rows start with `＊`.

### Table naming (verified from CSV headers)
`{gaku|ritu}-{m|j}{k|g|cy|fy}{ver}.csv`:
- `gaku` 額 = levels (¥bn) · `ritu` 率 = growth rate (%)
- **`j` 実質 = REAL · `m` 名目 = nominal** *(easy to invert — verified `gaku-jk` header says 実質)*
- `k` 季調 = seasonally adjusted · `g` original · `cy` calendar-year · `fy` fiscal-year
- → real SA levels `gaku-jk`, **real SA QoQ growth `ritu-jk`** (headline), nominal SA levels `gaku-mk`

## Fetcher
- **`fetch_gdp.py`** ✅ — pulls `gaku-jk` (real SA level), `gaku-mk` (nominal SA level), `ritu-jk` (real SA QoQ %). 19 expenditure columns each → **57 indicators, ~6,050 obs, 1994Q1→2026Q1**. Columns: GDP, private consumption (+household, ex-imputed-rent), private residential, private non-resi investment, private/public inventories, govt consumption, public investment, net exports/exports/imports, GDI, GNI, domestic/private/public demand, GFCF. Verified Q1-2026: real GDP ¥593.2tn, nominal ¥675.6tn, QoQ +0.5%.

## Promotion note
On promotion this is a **Cabinet Office vendor** (vendor_name `ESRI`), distinct from e-Stat and BoJ — its own `scripts/econ/jp/esri/` dir + `dim_vendor` row. Quarterly cadence; the QE calendar (~mid Feb/May/Aug/Nov for 1st preliminary, ~mid Mar/Jun/Sep/Dec for 2nd) drives the pull schedule.
