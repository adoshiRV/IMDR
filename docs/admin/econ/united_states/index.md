# United States — Econ Documentation

Last updated: 2026-06-05

US macroeconomic data. FRED (Federal Reserve Economic Data, St. Louis Fed) is the primary vendor; covers ~170 series across rates, GDP, CPI, labour, credit, housing, sentiment, balance sheet, FX, BoP, and energy. Some series are FRED-native (US data); others are OECD mirrors hosted on FRED for cross-country comparisons.

## Access paths

| Path | Auth | Speed | Coverage | Status |
|---|---|---|---|---|
| **FRED REST API** | API key (`IMDR_ECON_FRED_KEY` + `IMDR_ECON_FRED_KEY2`) | Fast | Full FRED catalogue (~800k series) | **Live** |
| **BLS Public Data API** | Free key (`BLS_API_KEY`) | Fast | CPI/PPI, employment, JOLTS, ECI, productivity — primary publisher | **Not onboarded** |
| **BEA Data API** | Free key (`BEA_API_KEY`) | Fast | GDP/NIPA, personal income, trade, regional, international transactions | **Not onboarded** |
| **Census Bureau API** | Free key (`CENSUS_API_KEY`) | Fast | Retail sales (MRTS), wholesale trade, housing starts, international trade | **Not onboarded** |

Dual-key rotation lives in the connector — per-request round-robin with 0.5s throttle. Added 2026-06-04 after a 429 storm during the BOPBCA/MBST/CFSI discontinued-series replacement work.

### Why FRED isn't the whole story

FRED is a *mirror* — most US headline series originate at BLS / BEA / Census and land on FRED with a publication lag. For real-time releases (CPI day, NFP day, retail sales) and for granular sub-series that FRED doesn't index, the source-agency APIs are the right primary. All three are JSON, free-key, and Tier-1 cleanliness — comparable to KOSIS/SingStat.

## What's loaded

170+ indicators in `econ.dim_indicator` (countries: US-primary, plus EU/UK/JP/CA/AU/CH/DE/NZ/KR via OECD mirror).

## Pre-prod

- [`_playground/fred.md`](_playground/fred.md) — FRED playground (fetchers, seed.yml, validation scripts).

## Policy & fiscal document sources

Time-series APIs above; the table below covers **document-style** sources (statements, minutes, projections, speeches) for the Federal Reserve. These are not `econ.fact_indicator` material — they feed the policy-document / research pipeline.

| Source | URL | Cadence | Notes |
|---|---|:---:|---|
| **FOMC calendar & meeting materials** | federalreserve.gov/monetarypolicy/fomccalendars.htm | reference | Hub listing meeting dates, statements, minutes, press conf, SEP. Crawl trigger. |
| **FOMC statements archive** | (same calendar hub) | per meeting | Policy decision text. |
| **FOMC minutes archive** | (same calendar hub) | per meeting (3-week lag) | Discussion record. |
| **Summary of Economic Projections** | federalreserve.gov/monetarypolicy/fomcprojtabl... | quarterly | Dot plot + central tendency forecasts. URL pattern: `fomcprojtabl{YYYYMMDD}.pdf`. |
| **Monetary Policy Report** | federalreserve.gov/monetarypolicy/publications/mpr_default.htm | semi-annual | Congressional testimony. |
| **Speeches & testimony** | federalreserve.gov/newsevents/speeches-testimony.htm | regular | Chair, Governors, Reserve Bank presidents. |

## Related

- [`../macro_economy_wiring_map.md`](../macro_economy_wiring_map.md) — coverage by cluster (US is the most-mapped country alongside Korea).
- [`../economics_data_ingest.md`](../economics_data_ingest.md) — schema + loader.
- [[project-econ-loaded]] — current live counts across all econ vendors.
