# Japan — Econ Documentation

Last updated: 2026-06-05

JP macroeconomic data. **Status: pre-prod.** No native ingest; partial coverage via FRED's OECD-mirror feeds.

Japan has two clean primary sources: **e-Stat** (Statistics Bureau aggregator — the KOSIS analog) and **BOJ Time-Series Data Search**. Plus a rich document-source set (decisions, minutes, outlook, speeches) on `boj.or.jp` that crawls cleanly (no Akamai-style block).

## Access paths

| Path | Auth | Speed | Coverage | Status |
|---|---|---|---|---|
| **e-Stat API** — `api.e-stat.go.jp` | Free key | Fast (REST/JSON) | Full Statistics Bureau catalogue: CPI, GDP, labour, retail, trade, IIP | **Not onboarded** |
| **BOJ Time-Series Data Search** — `boj.or.jp/en/statistics/...` | None | Fast (CSV by series code) | Monetary aggregates, rates, FX reserves, BoP, Tankan | **Not onboarded** |
| **FRED OECD mirror** | FRED API key | Fast | Headline JP series via OECD | Live (partial) |

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

- [`../macro_economy_wiring_map.md`](../macro_economy_wiring_map.md) — JP coverage state.
- [`../onboarding_new_country.md`](../onboarding_new_country.md) — onboarding playbook.
