# BI SEKI — Pre-prod playground notes

Last updated: 2026-06-10 (Phase I: bi_sbn_position)

Companion to [`bps.md`](bps.md) for the second Indonesia vendor. Where BPS
serves a clean REST JSON API, BI publishes Section-numbered XLSX tables at
a stable URL pattern with **no authentication and no API**. The XLSX
parsing infrastructure is the bulk of the engineering work; the fetcher
layer is thin once `_bi_seki.py` does its job.

## Playground location

```
playground/econ/bi/
├── _bi_seki.py         ← XLSX download + wide/annual sheet parsers
├── _bi_common.py       ← shared CLI / parquet / summarize scaffolding
├── _srbi.py            ← SRBI auction HTML page parser (exploratory; graduated to src/imdr/domains/econ/bi_srbi.py)
├── fetch_money_supply.py   (SEKI I.1, monthly, M0/M1/M2 + components)
├── fetch_fiscal.py         (SEKI IV.1/2/3, annual realisasi)
├── fetch_sbn.py            (SEKI IV.4, monthly SBN outstanding)
├── fetch_bop.py            (SEKI V.1, quarterly BoP summary)
├── fetch_fx_reserves.py    (SEKI V.9, monthly FX reserves position)
├── fetch_srbi.py           (SRBI auction yields, initial backfill, 2026-06-10; prod is scripts/econ/id/bi/bi_srbi.py)
├── fetch_sulni.py          (SEKI VI.1, quarterly external debt)
├── seki_raw/           ← cached XLSX downloads
└── sample_output/      ← parquet outputs (dim + fact pairs)
```

## Source URL patterns

**SEKI XLSX tables**:
```
https://www.bi.go.id/SEKI/tabel/TABEL{section}_{table}.xls
```

**Survey publications** (ZIP containing single XLSX, periodicity in filename):
```
https://www.bi.go.id/id/publikasi/laporan/Documents/{SLUG}.zip
```
Slugs: `SK` (Consumer Survey), `spe` (Retail Sales — lowercase), `SKDU` (Business Survey). Inner XLSX has `Tabel 1`..`Tabel N` sheets in SEKI-style wide format but with **row-indexed targets** (no line-number column) — see `_bi_survey.py`.

**SRBI auction results** (per-auction HTML page, ~2×/week):
```
https://www.bi.go.id/id/publikasi/lelang/operasi-moneter/Pages/Hasil-Lelang-SRBI-{D}-{Bulan-ID}-{YYYY}.aspx
```
`D` is the day number without zero-padding (e.g. `9`, not `09`). `Bulan-ID` is the Indonesian month name (Januari/Februari/…/Desember). Each page contains one 11-row HTML table; the canonical yield is row `Rata-Rata Tertimbang Pemenang (%)`. A 302 response means no auction was held on that date — skip. Parser: `src/imdr/domains/econ/bi_srbi.py`. Launched 2023-09-15; tenor mix shifted from 1/3/6/9/12M at launch to 6/9/12M only from mid-2024.

Examples:
- `TABEL1_1.xls` → I.1 Money Supply
- `TABEL4_1.xls` → IV.1 Government Revenue
- `TABEL5_1.xls` → V.1 Balance of Payments
- `TABEL6_1.xls` → VI.1 External Debt SULNI

All public, no auth, polite throttle (2 s/request) baked into
[`_bi_seki.download_seki()`](../../../../playground/econ/bi/_bi_seki.py).
Cached under `seki_raw/` between runs.

## SEKI section index

| Section | Topic | Tables shipped | Tables deferred |
|:---:|---|---|---|
| **I** | Uang dan Bank (Money & Banking) | I.1 Money Supply | I.2 M0 monetary base, I.3 commercial bank BS, I.4 bank credit |
| **II** | Non-Bank Financial Institutions | — | (out-of-scope) |
| **III** | Money & Capital Markets | — | III.x IDR bond yields (relevant for cell 4.3 — defer to rates domain) |
| **IV** | Keuangan Pemerintah (Govt Finance) | IV.1 Revenue, IV.2 Spending, IV.3 Financing, IV.4 SBN Position | (none — section complete) |
| **V** | Neraca Pembayaran (Balance of Payments) | V.1 BoP Summary, V.9 FX Reserves | V.2-V.8 (BoP detail sub-tables) |
| **VI** | Pinjaman Luar Negeri (External Debt) | VI.1 SULNI | VI.2+ (deeper external-debt breakdowns) |
| **VII** | GDP | — | (already covered by BPS) |
| **VIII** | Harga-Harga (Prices) | — | (already covered by BPS) |
| **IX** | International Economic & Monetary | — | (out-of-scope) |

## Critical XLSX-parsing gotchas

These all live in [`_bi_seki.py`](../../../../playground/econ/bi/_bi_seki.py) and
took the most engineering investment.

### 1. Year label placed at December, not January
TABEL1_1.xls 2024 block has `year=2024` at Dec column 196, not Jan column
185. Naive forward-fill on the year row mislabels Jan-Nov 2024 as 2023.

**Fix**: `_infer_years()` walks both year + month rows in lockstep and
detects month-rollbacks (Dec→Jan, Q4→Q1) to bump the year. Explicit year
anchors override at their column. Handles both forward and backward walks
from the first anchor.

### 2. Quarterly tables use Q1/Q2/Q3/Q4 with `*`/`**` suffix
BoP and similar BPM6 tables tag the last 1-2 quarters as `Q3*`
(preliminary) or `Q1**` (very preliminary).

**Fix**: `_parse_month()` strips trailing `*` before quarter-label lookup.

### 3. Multiple turtahun-style ID ranges
The SEKI tables don't have BPS-style turtahun IDs but the BoP tables
introduce alternate quarter encoding 321-324 (also handled by `_parse_month`).

### 4. Annual tables have NO month row
SEKI Section IV (fiscal) tables have year-only headers, no months. Each
data column is one annual value anchored at Jan 1.

**Fix**: `parse_seki_annual_sheet()` — separate parser variant that takes
only a `year_row` and emits (Jan 1 of year, value) tuples.

### 5. Year-row trailing English-label tail with stray years
SEKI IV.1 has a tail like `... 2023 2024 [English-label] 2019 2020` where
the last two years are NOT data columns but part of the English-label
section. Forward-fill would emit duplicate (year=2019, value=…) rows.

**Fix**: stop iterating the year row when we see year fail to STRICTLY
advance (`yi <= last_valid`). This catches both regressions AND duplicates.

### 6. Two-section tables — APBN (plan) + Realisasi (actual)
SEKI IV.1/2/3 tables contain TWO blocks: budget targets (APBN) and actuals
(realisasi). The current fetchers pull only the realisasi block via line-
number selection.

**Convention**: line numbers correspond to the 1-indexed `Keterangan`
sequence — APBN typically lines 2-27, Realisasi lines 28-47. See per-
fetcher `_TARGETS` for exact line numbers.

### 7. Survey publications use row-index addressing (no line_no column)
SK / SPE / SKDU XLSX inside the survey ZIPs do NOT have a numeric
`line_no` column 0 like SEKI tables do — the indicator hierarchy is
encoded via indentation in the Indonesian label column (col 2 or col 3).
Survey fetchers therefore index by **absolute row index** in the sheet,
not by line number. See `_bi_survey.parse_survey_rows()` and per-fetcher
`_TARGETS` lists.

### 8. String-marker year-row trailing sections
SPE Tabel 1 (and possibly others) appends an English-label / growth-rate
sub-section at the right end of the sheet, with a non-numeric year-row
label like `"DESCRIPTION"` or `"Perubahan"` followed by re-used month
labels (Jan/Feb…). Without a stop, `_infer_years` would keep
incrementing year on the rollover and emit ghost 2026/2027 observations.

**Fix**: `_infer_years` stops at the first column with a non-numeric
string in the year row AFTER the first numeric anchor. Strings BEFORE
the anchor (e.g. "DESKRIPSI" / "KETERANGAN" left-side header) are
ignored. See `_bi_seki.py` for the stop logic.

### 9. Roman numeral quarter labels (SKDU only)
SKDU header rows use Roman numerals `I` / `II` / `III` / `IV` for
quarters (vs SEKI's `Q1` / `Q2` / `Q3` / `Q4`). Handled in
`_QUARTER_LABEL_TO_MONTH` with both encodings.

## Phase D + D2 + D3 + D5 + D6 + H results (DB-loaded)

| Fetcher | Indicators | Obs | Cadence | Cell coverage |
|---|:---:|:---:|:---:|---|
| **SEKI XLSX tables** (`bi.go.id/SEKI/tabel/`) | | | | |
| `fetch_money_supply` (I.1) | 5 | 975 | Monthly 2010→ | 4.4 M1/M2 |
| `fetch_monetary_base` (I.2) | 5 | 385 | Monthly 2020→ | 4.4 M0 + CB BS |
| `fetch_bank_bs` (I.3) | 8 | 1,568 | Monthly 2010→ | 4.2 banking-system BS |
| `fetch_bank_credit` (I.4) | 15 | 1,590 | Monthly 2016→ | 4.1 credit channel (5 bank groups × total/business/consumer) |
| `fetch_bank_rates` (I.25.A + I.25.B + I.26 + I.28) | 13 | 827 | Monthly 2017→ | 4.3 Financial Conditions — policy + PUAB + INDONIA + bank lending/deposit aggregates |
| `fetch_fiscal` (IV.1-3) | 6 | 102 | Annual 2008→ | 1.2 Fiscal Demand |
| `fetch_sbn` (IV.4) | 5 | 990 | Monthly 2008→ | 1.2 + 4.4 |
| `fetch_bop` (V.1) | 13 | 845 | Quarterly 2010→ | 3.2 + 3.3 |
| `fetch_fx_reserves` (V.9) | 6 | 1,176 | Monthly 2010→ | 3.4 + 4.4 |
| `fetch_sulni` (VI.1) | 8 | 520 | Quarterly 2010→ | 3.3 + 4.2 |
| **Survey ZIP-XLSX publications** (`bi.go.id/.../Documents/`) | | | | |
| `fetch_consumer_survey` (SK.zip) | 9 | 1,503 | Monthly 2012→2025 | 1.1 Private Demand — IKK/CCI + 8 sub-indices |
| `fetch_retail_sales` (spe.zip) | 9 | 1,467 | Monthly 2012→2025 | 1.1 Private Demand — Real Sales Index + 8 categories |
| `fetch_business_survey` (SKDU.zip T1) | 18 | 234 | Quarterly 2022→2025 | 1.4 Macro Core / 1.1 — Business Activity SBT TOTAL + 17 sectors |
| `fetch_skdu_macro` (SKDU.zip T2 + T5 + T6) | 42 | 522 | Quarterly 2022→2025 | 2.3 Domestic Costs — Capacity Utilisation + Selling Prices + Inflation Expectations × sectors |
| **SRBI auction pages** (prod: `scripts.econ.id.bi.bi_srbi`) | | | | |
| `fetch_srbi` (SRBI 6M/9M/12M) | 3 | 485 | Event ~2×/week 2023-09-15→2026-06-10 | 4.3 Fin Conditions — SRBI weighted-avg winning yield by tenor; wired into `imdr_daily.py` 2026-06-10 |
| **SEKI IV.4 SBN position by holder** (prod-only: `scripts.econ.id.bi.bi_sbn_position`) | | | | |
| `bi_sbn_position` (TABEL4_4) | 19 | 3,630 | Monthly 2008-12→2026-05 | 4.2 Balance Sheets / 1.2 Fiscal — SBN outstanding by holder: 4 totals (SUN/ON/SPN/SBSN) + 8 ON bank-type holder decomp (govt/priv/mix/foreign/regional/BI/nasabah/other) + 7 SPN holder decomp. **No playground step** — built directly in prod using existing `bi_seki.py` library (TABEL4_4 follows standard wide-sheet offsets year_row=4, month_row=5, data_start=6). No new unit tests — parser covered by existing `_bi_seki` test suite. Wired into `id_monthly.py` 2026-06-10. |
| **TOTAL** | **184** | **16,819** | | All 16 wiring cells touched |

Spot-checked vs known reality:
- M2 March 2026 = 10,355 trillion IDR ✓
- FX Reserves April 2026 = $146bn ✓
- BoP Current Account Q1 2026 = -$4.0bn ✓ (small CA deficit)
- SUN outstanding April 2026 = $358bn ✓ (5,586 trillion / 15,600 IDR/USD)
- BI holdings of SUN = $99bn ≈ 27% of SUN (heavy QE-style exposure) ✓
- External debt Q1 2026 = $433bn (public $242bn + private $191bn) ✓
- Total fiscal balance 2024 = -509 trillion IDR ≈ -1.7% of GDP ✓

## Code conventions

All BI fetchers follow the same shape via `_bi_common.cli_main()`:

```python
from playground.econ.bi._bi_common import cli_main, filter_obs_date
from playground.econ.bi._bi_seki import download_seki, parse_seki_wide_sheet

_TARGETS = [(line_no, imdr_code, display), ...]

def run_fetch(since, until):
    # Download XLSX, parse sheet, emit indicators + observations
    ...

if __name__ == "__main__":
    sys.exit(cli_main(
        description="...",
        run_fetch=run_fetch,
        stem_prefix="bi_xxx",
    ))
```

Each fetcher is ~120-150 lines focused entirely on table-specific structure
(line numbers, vervar filters, frequency, unit). All argparse / parquet /
summary boilerplate lives in `_bi_common.py`.

## Migrations applied

- `081_seed_bps_dim_vendor.sql` — `vendor_code='bps'`
- `082_add_bps_dim_unit_frequency.sql` — `idr`, `idr_bn`, `SEMIANNUAL`
- `083_seed_bi_dim_vendor.sql` — `vendor_code='bi'`

## Known placeholders to revisit before promotion to prod

1. **`fetch_fiscal.py` uses `category="other"`** — fiscal data is a distinct
   concept and warrants a `"fiscal"` row in `econ.dim_indicator_category` +
   addition to `schema_prototype.VALID_CATEGORIES`. Tracked inline via
   `_FISCAL_CATEGORY_PLACEHOLDER` module constant.
2. **`fetch_sbn.py` uses `category="instr_outstand"`** — borrowed from HKMA's
   liquidity-ops convention; arguably belongs under `"fiscal"` or a new
   `"sov_debt"` category.
3. **`fetch_sulni.py` uses `category="bop"`** — external debt stock is at
   best adjacent to BoP flow data. Reasonable but worth a second look.

## Deferred (Phase D7+)

- Banking Survey SBP (lending stance survey) — Section II tables don't appear in current SEKI structure per BI portal navigation; may be published as separate PDF reports
- Money & Capital Markets (SEKI III.x) — IDR bond yields belong in the rates domain, not econ schema
- Deeper BoP sub-tables (V.2-V.8) — for FA / IIP detail
- Legacy bank-credit history (TABEL1_4 sheets "Th 2002-2017") — current fetcher reads "Th 2016-2024" only; pre-2016 data is a multi-sheet splice job
- 2025-2026 bank credit gap — current sub-sheets I.4_1/2/3 hold latest months but use different bank-group structure; splice with legacy "Th 2016-2024" data
- Bank-group × loan-type sectoral breakdown for I.26/I.28 — current fetcher carries Bank Umum aggregate only (4 bank groups × 3 loan types = 12 additional; same for deposits = 20 additional)
- SKDU T3 Finance + T4 Labour + T7 Investment — only T1/T2/T5/T6 covered so far
- BI Annual Report FX reserves currency composition — published only annually as part of BI Annual Report PDF

## Cross-refs

- [`bps.md`](bps.md) — BPS playground notes (sibling)
- [`../index.md`](../index.md) — Indonesia landing page
- [`../id_coverage_plan.md`](../id_coverage_plan.md) — cell ↔ vendor mapping
