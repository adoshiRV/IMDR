# Japan — Econ Documentation

Last updated: 2026-07-10

JP macroeconomic data. **Status: pre-prod (discovery).** DB shows only 5 FRED stub series. A large native-source playground build exists (20 fetchers, ~225 indicators) — not loaded, not wired. See [`japan_indicator_inventory.md`](japan_indicator_inventory.md).

Japan sources split across seven mechanisms:

## Access paths

| Path | Auth | Speed | Coverage | Status |
|---|---|---|---|---|
| **e-Stat API** — `api.e-stat.go.jp` | Free key (`IMDR_ECON_ESTAT_KEY`) | Fast (REST/JSON) | CPI, Labour Force, Economy Watchers, METI IIP (2020-base), MHLW wages (file-catalog) | Playground-built |
| **Cabinet Office ESRI QE** — `esri.cao.go.jp` | None | Fast (Shift-JIS CSV) | Live GDP (real/nominal SA + QoQ, full expenditure decomp, 1994→) | Playground-built |
| **BoJ flat-file zips** — `stat-search.boj.or.jp/info/` | None | Fast (ZIP/CSV) | BoP, CGPI/PPI, SPPI, IIP position, TANKAN | Playground-built |
| **BoJ mtshtml direct CSV** — `stat-search.boj.or.jp/ssi/mtshtml/csv/` | None | Fast (plain CSV) | Rates (call + discount), money stock (M1/M2/M3/L + monetary base), FX/NEER/REER | Playground-built |
| **MOF customs time-series CSV** — `customs.go.jp/toukei/suii/` | None | Fast (Shift-JIS CSV) | Monthly trade (exports/imports/balance, world + regions + partners, 1979→) | Playground-built |
| **MOF JGB debt-management PDFs** — `mof.go.jp/english/policy/jgbs/` | None | PyMuPDF parse | JGB market issuance by tenor (ANNUAL, Highlights PDF) + JGB holder breakdown by investor sector (QUARTERLY, Flow of Funds PDF) | Playground-built (NEW 2026-07-10) |
| **METI site XLSX** — `meti.go.jp/statistics/tyo/syoudou/` | None | XLSX via primed session | Retail (商業動態, total/wholesale/retail/dept/super/CVS, 1980→). WAF requires browser UA + `Referer` + cookie-priming; e-Stat mirror frozen at Dec-2020. | Playground-built (WAF fix 2026-07-10) |
| **GPIF annual Excel** — `gpif.go.jp/en/performance/past-performances.html` | None | XLSX download | Asset-allocation profile: domestic bonds / foreign bonds / domestic eq / foreign eq / alternatives — market value + share + AUM, ANNUAL, Mar-2015→Mar-2024 | Playground-built (NEW 2026-07-10) |
| **FRED OECD mirror** | FRED API key | Fast | Headline JP series via OECD | Live (5 stubs, backup only) |

## Policy & fiscal document sources

`boj.or.jp` is crawler-friendly — all archives below returned HTTP 200 on probe.

| Source | URL | Cadence | Notes |
|---|---|:---:|---|
| **BoJ monetary policy meetings calendar** | boj.or.jp/en/mopo/mpmsche_minu/index.htm | reference | Schedule + minutes + summaries of opinions. |
| **BoJ Statements on Monetary Policy** | boj.or.jp/en/mopo/mpmdeci/index.htm | per meeting | Policy decision archive (short-term rate, YCC). |
| **BoJ minutes & summaries of opinions** | boj.or.jp/en/mopo/mpmsche_minu/index.htm | per meeting | Discussion record. |
| **BoJ Outlook for Economic Activity and Prices** | boj.or.jp/en/mopo/outlook/index.htm | quarterly | Core forecast layer. |
| **BoJ speeches** | boj.or.jp/en/about/r_menu_koen/index.htm | regular | Governor / deputy / board members. |

URL patterns for direct documents:
- Minutes PDFs: `boj.or.jp/en/mopo/mpmsche_minu/minu_{YYYY}/g{YYMMDD}.pdf`
- Statement PDFs: `boj.or.jp/en/mopo/mpmdeci/mpr_{YYYY}/k{YYMMDD}a.pdf`

## Related

- [`japan_indicator_inventory.md`](japan_indicator_inventory.md) — full 4×4 coverage tracker, source routes, freshness audit.
- [`_playground/boj.md`](_playground/boj.md) · [`_playground/estat.md`](_playground/estat.md) · [`_playground/esri.md`](_playground/esri.md) · [`_playground/meti.md`](_playground/meti.md) · [`_playground/mhlw.md`](_playground/mhlw.md) · [`_playground/mof.md`](_playground/mof.md) · [`_playground/gpif.md`](_playground/gpif.md) — per-vendor discovery notes.
- [`../macro_economy_wiring_map.md`](../macro_economy_wiring_map.md) — JP coverage state.
- [`../onboarding_new_country.md`](../onboarding_new_country.md) — onboarding playbook.
