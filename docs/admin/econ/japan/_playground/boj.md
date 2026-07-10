# BoJ — `playground/econ/jp/boj/`

**Status:** discovery (2026-06-22). Flat-file route proven; market-side search route unresolved.

Bank of Japan publishes time-series two ways, both at `stat-search.boj.or.jp` (no auth, **no Akamai block** — plain `requests` returns HTTP 200):

## Route 1 — flat-file zips ✅ (the bulk-CSV route)

Index page `stat-search.boj.or.jp/info/dload_en.html` lists ~16 category zips at `…/info/{name}.zip`. Each zip holds one CSV. Two layouts:

- **wide** — `code, name, component, unit, v1, v2, …`; header row's trailing cells are `YYYYpp` period tokens. Used by BoP, CGPI, SPPI, IIP, Flow of Funds.
- **long** — `code, freq, period, value`, no header. Used by TANKAN (`co.zip`); labels from the `tankan_code_en.html` master.

**Period encoding gotcha:** the `YYYYpp` token is `YYYY` + sequence-number-within-year, **not** a calendar month — monthly series use 01-12, quarterly 01-04, semiannual 01-02, annual 00/01. `period_to_date()` is therefore frequency-aware.

| Zip | Statistic | Cell | Layout | Cadence |
|---|---|---|---|---|
| `bp_m_en.zip` | Balance of Payments (BPM6) | 3.2 / 3.3 / 1.3 | wide | M |
| `cgpi_m_en.zip` | Corporate Goods Price Index (= PPI) | 2.2 / 2.1 | wide | M |
| `sppi_m_en.zip` | Services Producer Price Index | 2.2 | wide | M |
| `qiip_q_en.zip` | International Investment Position | 3.3 / 4.2 | wide | Q |
| `co.zip` | TANKAN (business sentiment) | 1.4 / 2.3 | long | Q |
| `fof.zip` / `fof2_en.zip` | Flow of Funds | 4.2 | wide | Q |
| `bis1-*/bis2-*_q_en.zip` | BIS banking stats in Japan | 4.2 | wide | Q |

### Shared infra + fetchers
- **`_boj_flatfile.py`** — `download_zip()`, `read_csv_from_zip()`, `parse_wide()`, `period_to_date(token, freq)`, `parse_value()`.
- **`_boj_common.py`** — `emit_wide(zip, code_map, freq, unit, category, …)` (the shared wide-table emitter every flat-file fetcher uses) + `cli_main` wrapper fixing `out_root`.
- **`fetch_bop.py`** ✅ — 14 BoP series (CA/G&S/goods/services/primary-income net; FA net + DI/PI/OI/reserves; capital account; E&O). 5,096 obs 1996→2026. **BPM6 identity verified** (`CA + Capital + E&O = Financial account`).
- **`fetch_cgpi.py`** ✅ — CGPI 2020-base: PPI all+5 groups (cell 2.2) + Import Price (yen+contract-ccy, cell 2.1 FX pass-through) + Export Price (yen+contract-ccy, cell 3.1). 10 indicators, 2020→.
- **`fetch_sppi.py`** ✅ — Services PPI all-items + 7 major groups (cell 2.2). 8 indicators, 2020→.
- **`fetch_iip.py`** ✅ — International Investment Position (quarterly): net/assets/liabilities/reserves/gross-external-debt. 5 indicators, 2014→. **Identity verified** (`assets − liabilities = net`).
- **`fetch_tankan.py`** ✅ — TANKAN DIs, **10 indicators**. Codes decoded from the 20-char scheme in `tankan_code_en.html` (`TK99·F·{1000 mfg/2000 non-mfg}·{item}·G diffusion·CQ·{0 actual/1 fcst}·{1 large/0 all}·000`):
  - **Business conditions** (item 601): large + all-size × mfg + non-mfg, actual + forecast (6). Verified large-mfg Q1-2026 = +17.
  - **Lending attitude of banks** (item 612) + **financial position** (item 609): large mfg + non-mfg (4) — **cell 4.1 demand transmission**, the machine-readable stand-in for the BoJ SLOOS survey (which is PDF-only). Verified lending-attitude large-mfg = +15.
  - **NOTE: `co.csv` carries only recent rounds (~5 quarters), not full history** — back-series needs famecgi2.
- Pending: `fetch_fof.py` (Flow of Funds — deferred; BIS credit-to-GDP covers cell 4.2).

## Route 2 — "Main Time-series Statistics" direct CSV (mtshtml) ✅ UNBLOCKED

The market-side series (rates, money, FX) download as **plain CSV** — no famecgi2 form, no auth, no cookies:

```
https://www.stat-search.boj.or.jp/ssi/mtshtml/csv/{code}_{freq}_{n}_en.csv
  freq: d=daily, m=monthly, q=quarterly ; n = file index within the category
```

(User-found URL `ir01_d_1_en.csv`; DevTools cURL confirmed a plain GET with a `Referer` header.) Helper **`_boj_mtshtml.py`** (`download_mtshtml`, `parse_mtshtml`). CSV is wide: metadata rows (`Name of time-series` / `Series code` / `Unit`), then `YYYY/MM/DD, v1, v2, …` data rows.

| Series | File | Cell | History |
|---|---|---|---|
| **FM01** uncollateralized overnight call rate (policy-rate target) | `fm01_d_1` | 4.4/4.3 | daily 1998→ |
| **IR01** basic discount/loan rate | `ir01_d_1` | 4.4 | daily |
| **MD01** monetary base (level + YoY, 8 cols) | `md01_m_1` | 4.4 | monthly **1980→** |
| **MD02** money stock M1/M2/M3/L (level + YoY, 16 cols) | `md02_m_1` | 4.4 | monthly 2003→ |
| **FM08** USD/JPY spot + central rate | `fm08_d_1` | 3.4 | daily 1998→ |
| **FM09** NEER + REER (CY2020=100) | `fm09_m_1` | 3.4 | monthly 1980→ |

Fetchers: **`fetch_rates.py`** ✅ (call + discount rate), **`fetch_money.py`** ✅ (monetary base + M1/M2/M3/L), **`fetch_fx.py`** ✅ (USD/JPY + NEER/REER). All via `_boj_common.emit_mtshtml`.

**Still missing from the mtshtml set** (404 — curated "main" subset only): FM02 short-term money-market rates, MD07 reserves, **LA05 Senior Loan Officer Survey / SLOOS** (cell 4.1). These would need the famecgi2 form (deferred) or another file index. The interactive famecgi2 form (`cgi=$nme_a000_en&lstSelection={CODE}`, JS POST) is **no longer needed** for the headline rates/money/FX — keep as fallback only for the residual categories.

Probes under `raw/` (`dload_index_en.html`, `search_top_en.html`, `cat_FM01.html`) + `raw/mtshtml/`.

## Network
- No Akamai / firewall block from RV's network — all `stat-search.boj.or.jp` + `boj.or.jp` endpoints returned 200.
- Windows console: set `PYTHONIOENCODING=utf-8` for any script that prints BoJ labels.

## Next moves
1. Cell 4.1 demand transmission is covered via **TANKAN lending-attitude/financial-position DI** (item 612/609, in `fetch_tankan.py`). The pure BoJ SLOOS survey (`LA05`) is **PDF-only** (`boj.or.jp/.../loos/release/loos*.pdf`, quarterly) — only worth a PDF-parse if the exact SLOOS DI is specifically needed; not in mtshtml.
2. FM02 short-term money-market rates + MD07 reserves — absent from mtshtml "main" set; famecgi2 fallback if needed.
3. Flow of Funds fetcher (deferred — BIS credit-to-GDP covers cell 4.2).
