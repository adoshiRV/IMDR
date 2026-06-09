# ABS — `playground/econ/abs/`

Last updated: 2026-06-10

**Status:** DB-LIVE — 16 fetchers, **174 indicators / 15,616 obs** loaded (verified against `econ.fact_indicator` 2026-06-10). Australian Bureau of Statistics SDMX API (public, unauthenticated). 1,223 dataflows enumerated.

IIP loaded 2026-06-10 (+33 indicators / +4,951 obs; quarterly 1988 Q3 → 2026 Q1). Last gap closed for the AU 4×4 wiring map's stock side.

## Contents

| File | Purpose |
|---|---|
| `_abs_common.py` | Shared SDMX helpers (HTTP client, dimension-key builder, parquet writer). |
| `fetch_cpi.py` | ABS `CPI` dataflow — headline (INDEX=10001, Q NSA) + Trimmed Mean (999902, M) + Weighted Median (999903, M). 16 indicators. |
| `fetch_gdp.py` | ABS `ANA_AGG` dataflow — Chain-volume GDP, SA (DATA_ITEM=GPM). 7 indicators. |
| `fetch_labour.py` | ABS `LF` dataflow — Unemployment rate (M13), Participation rate (M12), Employed persons (M3), SA. 6 indicators. |
| `fetch_wpi.py` | ABS `WPI` dataflow — Wage Price Index (INDEX=OHRPEB, INDUSTRY=TOT). NSA only — SA not published. 6 indicators. |
| `fetch_ppi_fd.py` | ABS `PPI_FD` dataflow — Producer Prices Final Demand (TSEST=TOTXE, not TOTIE). 3 indicators. |
| `fetch_retail.py` | ABS Retail Trade dataflow — monthly retail sales. 10 indicators. |
| `fetch_bop.py` | ABS `BOP` dataflow — current/primary/secondary/capital/financial account + sub-items. 14 indicators. |
| `fetch_bop_goods.py` | ABS `BOP_GOODS` dataflow — chain-volume only (TSEST=10). 7 indicators. |
| `fetch_trade_prices.py` | ABS `ITPI_IMP` + `ITPI_EXP` — Import price index (headline IDX=6011001 + 9 SITC 1-digit input-cost codes 6013001..6013009 × Index+YoY) + Export price index (IDX=8093697, Index+QoQ+YoY). 24 indicators (cells 2.1 / 3.3). |
| `fetch_gdp_expenditure.py` | ABS `ANA_EXP` dataflow — GDP expenditure decomposition. 10 indicators. |
| `fetch_job_vacancies.py` | ABS Job Vacancies (`JV`) dataflow. 3 indicators. |
| `fetch_capex.py` | ABS `CAPEX` — private new capital expenditure (M1 actual, by asset class). 4 indicators (cell 1.4 macro core / 1.1 private investment). |
| `fetch_lending.py` | ABS `LEND_HOUSING` + `LEND_BUSINESS` + `LEND_PERSONAL` — new lending commitments. 11 indicators (2 business + 4 housing + 5 personal). Cell 4.1 Demand Transmission supplement. |
| `fetch_lf_under.py` | ABS `LF_UNDER` — sibling LF dataflow for underemployment / underutilisation (M21/M23/M24). 3 indicators (cell 1.4 labour slack). |
| `fetch_rppi.py` | ABS `RPPI` — residential property price index, weighted 8-capital + per-city (Sydney/Melbourne/Brisbane/…/Canberra) × Index/QoQ/YoY. 17 indicators (cells 4.2 housing wealth / 1.1 private demand). |
| `fetch_iip.py` | **NEW 2026-06-10** — ABS `IIP` International Investment Position. 33 indicators across headline (Net IIP, FA/FL totals, External Debt), Direct + Portfolio Investment (FA/FL × equity/debt), Other Investment (FA/FL), Financial Derivatives (FA/FL), Reserve Asset sub-decomp (gold, SDRs, debt securities short/long, currency & deposits, other). Quarterly stock since 1988 Q3. Cell 3.3 stock-side. **Sign convention:** Foreign Assets are recorded as negative in MEASURE=6 (BoP debit convention preserved into stocks); analytics layer must `abs()` for reader-facing display. |
| `discovery/probe_codelist.py` | Probe ABS codelists via `?references=all` — used to find real INDEX/MEASURE codes. |
| `discovery/probe_iip.py` | IIP dataflow probe: 8 dimensions (`MEASURE.DATA_ITEM.SECTOR.MATURITY.INDUSTRY.CURRENCY.TSEST.FREQ`), 129 DATA_ITEM codes, 22 sectors. Wildcard data live (Q1-2026 obs confirmed). |
| `discovery/probe_iip_keys.py` | Live-validates the 17-key headline IIP set with `CURRENCY=700` (AUD); `1704` (Total) returns 404. |
| `discovery/probe_iip_sectors.py` | Confirms SECTOR/MATURITY/INDUSTRY axes collapse to TOT at the headline DATA_ITEM level; sub-decomp lives in DATA_ITEM instead. |
| `discovery/iip_findings.md` | IIP probe findings + final 33-key proposal. |
| `discovery/probe_remaining.py` | Discovery probe for remaining dataflows. |
| `discovery/probe_failed_keys.py` | Probe for keys that failed initial enumeration. |
| `discovery/findings.md` | "ABS Source-Discovery Findings" — endpoint inventory. |
| `discovery/codelists_*.json` | Cached codelists for verified dataflows (incl. `codelists_IIP.json`). |
| `sample_output/2026/06/08/` | Original 3-fetcher sample parquet (29 indicators, 2,395 obs — superseded by full load). |

## Transport

API-based. `httpx` client + SDMX XML parsing (`xml.etree`). No auth, no rate limit observed. SDMX v2.1 (NSI Web Service v8.19.9.0).

## Key shapes verified (2026-06-10)

| Dataflow | National headline key | Obs range | Indicators |
|---|---|---|:---:|
| `CPI` | `1.10001.10.50.Q` | 1948 Q3 → present | 16 |
| `ANA_AGG` | `M1.GPM.20.AUS.Q` | 1959 Q3 → present | 7 |
| `ANA_EXP` | `VCH.GPM.SSS.20.AUS.Q` | 1959 Q3 → present | 10 |
| `LF` | `M13.3.1599.20.AUS.M` | 1978-02 → present | 6 |
| `LF_UNDER` | `M21.3.1599.20.AUS.M` | 1978-02 → present | 3 |
| `WPI` | `1.OHRPEB.7.TOT.10.AUS.Q` | ~1997 Q3 → present | 6 |
| `PPI_FD` | `1.TOT.TOT.TOTXE.Q` (TOTXE not TOTIE) | ~2000s → present | 3 |
| `RT` (Retail Trade) | `M1.20.20.AUS.M` | ~1982 → present | 10 |
| `BOP` | `1.{item}.10.Q` / `1.{item}.20.Q` | ~1960s → present | 14 |
| `BOP_GOODS` | `2.{item}.{EXP|IMP}.10.Q` (chain-volume) | ~1970s → present | 7 |
| `ITPI_IMP` | `1.6011001.Q` (headline) + 9 SITC at `1.6013xxx.Q` | ~1974 → present | 21 |
| `ITPI_EXP` | `{1|2|3}.8093697.Q` | ~1974 → present | 3 |
| `JV` | `M1.{1|2|7}.TOT.20.AUS.Q` | ~1979 → present | 3 |
| `CAPEX` | `M1.{CUR|CVM}.TOT.TOT.20.AUS.Q` | ~1987 → present | 4 |
| `LEND_HOUSING` | `FIN_{VAL|NUM}.NEWCOMMITS.DV8368.…` | ~2002 → present | 4 |
| `LEND_BUSINESS` | `FIN_VAL.NEWCOMMITS.DV8270.…` | ~2002 → present | 2 |
| `LEND_PERSONAL` | `FIN_VAL.NEWCOMMITS.DV8270.…` | ~2002 → present | 5 |
| `RPPI` | `{1\|2\|3}.{1\|2\|3}.{100\|1GSYD\|…}.Q` | ~2003 Q3 → present | 17 |
| `IIP` | `6.{DATA_ITEM}.TOT.TOT.T.700.10.Q` (CURRENCY=700 AUD; `1704` Total 404s) | 1988 Q3 → present | 33 |

## Next moves

Production promotion / Phase G:
1. Register ABS fetchers in the canonical production scheduler (needs explicit user OK per `feedback_no_prod_wiring_without_permission.md`).
2. Add scheduled refresh cadence (most ABS series: M or Q).
3. Confirm `country_iso=AU` and `vendor=abs` dim rows stable.
4. Consider RBA live-refresh once Playwright profile stabilises (see `rba.md`).

## Coverage

ABS provides the source-of-truth for AU real-economy series (replaces FRED-OECD mirrors). **16 fetchers across 19 dataflows loaded** (CPI, ANA_AGG, ANA_EXP, BOP, BOP_GOODS, CAPEX, IIP, ITPI_IMP, ITPI_EXP, JV, LEND_BUSINESS, LEND_HOUSING, LEND_PERSONAL, LF, LF_UNDER, PPI_FD, RPPI, RT, WPI).

The IIP add (2026-06-10) closes the cell-3.3 stock-side gap. The earlier `BOP_FACTOR` attempt was on the wrong dataflow (carries only SA adjustment factors, not levels).

## Related

- [`rba.md`](rba.md) — sibling AU vendor (monetary side)
