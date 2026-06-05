# Thailand — Econ Documentation

Last updated: 2026-06-05

TH macroeconomic data. **Status: pre-prod.** No native ingest.

Primary source: **Bank of Thailand (BoT)** — operates a REST JSON API for economic statistics (rates, FX, monetary, banking, balance of payments) with a free key. National statistics office (NSO) covers CPI/labour/national accounts but with no real API — XLSX scraping. BoT is the cleanest API in ASEAN after Singapore + Malaysia.

## Access paths

| Path | Auth | Speed | Coverage | Status |
|---|---|---|---|---|
| **BoT API** — `apiportal.bot.or.th` | Free key (`BOT_API_KEY`) | Fast (REST JSON) | Rates, FX, monetary aggregates, BoP, banking | **Not onboarded** |
| **BoT statistics portal** — `bot.or.th/en/statistics` | None | Slow (HTML/XLSX) | Discovery root for series codes | **Not onboarded** |
| **NSO Thailand** — `nso.go.th` | None | Slow (XLSX) | CPI, labour, national accounts | **Not onboarded** — no API |
| **FRED OECD mirror** | FRED API key | Fast | Headline TH series | Live (partial) |

## Policy & fiscal document sources

`bot.or.th` is crawler-friendly (HTTP 200 on probe). Document URLs follow AEM CMS conventions (`/content/dam/bot/documents/en/...`).

| Source | URL | Cadence | Notes |
|---|---|:---:|---|
| **BoT MPC meeting schedule & releases** | bot.or.th/en/our-roles/monetary-policy/mpc-meeting.html | reference | Operational trigger page. |
| **BoT edited MPC minutes** | bot.or.th/en/our-roles/monetary-policy/mpc-publication/edited-minutes.html | per meeting | Primary minutes archive. |
| **BoT Monetary Policy Report** | bot.or.th/en/our-roles/monetary-policy/mpc-publication/Monetary-Policy-Report.html | quarterly | Forecast revisions. |
| **BoT speeches** | bot.or.th/en/news-and-media/speeches.html | regular | AEM-driven (custom child discovery required). |

Sample minutes PDF for parser prototyping: `bot.or.th/content/dam/bot/documents/en/research-and-publications/reports/monetary-policy/minutes-mpc/mpc-minutes-{YYYY}-{N}.pdf`.

## Related

- [`../macro_economy_wiring_map.md`](../macro_economy_wiring_map.md) — TH coverage state.
- [`../onboarding_new_country.md`](../onboarding_new_country.md) — onboarding playbook.
