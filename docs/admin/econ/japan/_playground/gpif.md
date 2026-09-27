# GPIF (asset-allocation profile) — `playground/econ/jp/gpif/`

**Status:** discovery complete (2026-07-10). One fetcher, parquet-only, no DB load.

Government Pension Investment Fund (年金積立金管理運用独立行政法人) — the world's largest pension fund (~¥290tn AUM). Primary relevance: GPIF is the largest single non-BoJ owner of JGBs; its allocation shifts are material to JGB demand (cells 4.2 balance sheets, 4.3 financial conditions).

## Source

**GPIF "Portfolio holdings by asset category" — annual Excel workbooks.**
- Listing: `https://www.gpif.go.jp/en/performance/past-performances.html`
- File patterns: `unyoujoukyou_*_en.xlsx` and `portfolio_holdings_*.xlsx`
- **Cadence:** ANNUAL, fiscal-year-end (Mar 31). History: Mar-2015 → Mar-2024 (the detailed holdings Excel lags the headline summary by ~1 fiscal year; see Tip-lag caveat below).
- Auth: none. TLS: `check_hostname=False` (GPIF uses a legacy cert chain).

## Sheet structure

Each workbook has **one sheet per asset class** (Domestic Bonds / Foreign Bonds / Domestic Equities / Foreign Equities / Alternative Assets). Each sheet lists every security held (ISIN + market value in JPY). The fetcher:

1. Scans sheet titles for asset-class keywords (case-insensitive; longest-match first).
2. Reads the as-of date from a `"as of <Mon> <d>, <YYYY>"` header cell in the first 7 rows of each sheet.
3. Sums each sheet's Market Value column to derive asset-class totals. The **Total row** (a single `"Total"` cell in the first column) is used as the authoritative figure; individual security rows are summed separately as a cross-check (>0.5% divergence is flagged but does not abort).
4. Derives portfolio shares and total AUM across all five classes.

## Output

**11 indicators / 100 obs**, ANNUAL, unit = `jpy` (VALUE) or `pct` (SHARE).

| imdr_code | description | unit |
|---|---|---|
| `GPIF.ALLOC.DOMESTIC_BONDS.VALUE.JP` | Domestic bonds — market value | jpy |
| `GPIF.ALLOC.DOMESTIC_BONDS.SHARE.JP` | Domestic bonds — portfolio share | pct |
| `GPIF.ALLOC.FOREIGN_BONDS.VALUE.JP` | Foreign bonds — market value | jpy |
| `GPIF.ALLOC.FOREIGN_BONDS.SHARE.JP` | Foreign bonds — portfolio share | pct |
| `GPIF.ALLOC.DOMESTIC_EQUITY.VALUE.JP` | Domestic equities — market value | jpy |
| `GPIF.ALLOC.DOMESTIC_EQUITY.SHARE.JP` | Domestic equities — portfolio share | pct |
| `GPIF.ALLOC.FOREIGN_EQUITY.VALUE.JP` | Foreign equities — market value | jpy |
| `GPIF.ALLOC.FOREIGN_EQUITY.SHARE.JP` | Foreign equities — portfolio share | pct |
| `GPIF.ALLOC.ALTERNATIVES.VALUE.JP` | Alternative assets — market value | jpy |
| `GPIF.ALLOC.ALTERNATIVES.SHARE.JP` | Alternative assets — portfolio share | pct |
| `GPIF.AUM.TOTAL.JP` | Total AUM (securities-level sum) | jpy |

`category = "other"` (no dedicated pension-allocation category code). `frequency = "ANNUAL"`.

## Caveats

### Securities-level vs reported policy-mix allocation
GPIF's **reported** policy-mix allocation (the headline %) reclassifies JPY-hedged foreign bonds and yen cash into "domestic bonds", and foreign-currency cash into "foreign bonds". This fetcher sums the raw securities sheets, so the domestic-bond figure is the pure securities book and will run **~2 percentage points below** the reported headline (e.g. ~24–25% vs reported ~26.9%). This is documented, not a bug — the securities view is the machine-clean, ISIN-auditable series and is what a maturity-ladder analysis would build on. When comparing against GPIF's published breakdown, use their annual report directly.

### Tip-lag: Excel lags the headline summary by ~1 fiscal year
The detailed holdings Excel series currently ends Mar-2024. The latest **headline allocation** (Mar-2026: ¥293.6tn AUM — domestic bonds 26.9% / foreign bonds 24.5% / domestic equities 23.8% / foreign equities 24.8%) is published in the FY annual-report **summary PDF** only, not yet in the holdings Excel. Closing this tip-lag with a summary-PDF parser is a noted follow-on.

## Infrastructure

- **`_gpif_common.py`** — thin `cli_main` wrapper fixing `out_root` to `sample_output/` (mirrors `_mof_common.py` pattern).
- **`fetch_gpif.py`** — main fetcher. Uses `urllib.request` (stdlib, no `requests` dep) + `openpyxl` (local import, heavy).
- **`__init__.py`** — empty package marker.

## Next moves
- Summary-PDF parser to close the ~1-year tip-lag (Mar-2026 headline not in holdings Excel).
- Wire GPIF domestic-bonds value against JGB holder PUBLIC_PENSIONS (~¥73tn from `fetch_jgb_holders.py`) as a cross-check (GPIF's domestic-bond book ≈ JGB+FILP allocations to GPIF).
