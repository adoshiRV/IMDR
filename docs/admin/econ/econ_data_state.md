# Econ Data — Full State (All Countries)

> Snapshot as of **2026-07-28**, pulled live from the IMDR database (`econ.fact_indicator`,
> `econ.dim_indicator`, `dbo.dim_country`, `dbo.dim_vendor`) and cross-referenced with the
> project onboarding history. (Prior snapshot 2026-06-24 — deltas since: IN 1,475→1,580, AU
> 539→818 (housing/labour buildout + industry employment), KR 172→197 (KOFIA freeSIS +25).)

## 1. Headline

- **4,293 indicators** defined in `econ.dim_indicator` (**4,265 active**), across **14 countries**.
- **~1,555,569 observations** in `econ.fact_indicator` (active indicators; counts all vintages).
- Two tiers:
  - **Tier 1 — deep native-source onboarding** (7 countries): IN, NZ, AU, ID, US, KR, HK.
    Wired into the scheduled orchestrators, pulling directly from official statistical agencies.
  - **Tier 2 — thin FRED-only baselines** (7 entries): UK, JP, DE, EU, CA, CH, WW.
    A handful of FRED/FAO mirror series for cross-country comparison; **not** natively onboarded.

## 2. Master table — indicators + observations by country

| cc | Country | Indicators | Active | Vendors | Observations | Earliest | Latest |
|----|---------|-----------:|-------:|--------:|-------------:|----------|--------|
| IN | India | 1,580 | 1,580 | 11 | 108,361 | 1946-01-01 | 2029-05-01* |
| NZ | New Zealand | 1,112 | 1,112 | 2 | 164,383 | 1914-06-30 | 2026-06-30 |
| AU | Australia | 818 | 818 | 10 | 578,683 | 1948-07-01 | 2026-07-28 |
| ID | Indonesia | 303 | 303 | 4 | 114,638 | 1975-01-01 | 2026-07-24 |
| KR | South Korea | 219 | 217 | 7 | 183,923 | 1961-01-01 | 2026-08-10 |
| US | United States | 219 | 193 | 7 | 214,750 | 1947-01-01 | 2026-07-28 |
| HK | Hong Kong | 29 | 29 | 1 | 192,083 | 1981-01-02 | 2026-06-03 |
| WW | Worldwide | 6 | 6 | 1 | 2,629 | 1990-01-01 | 2026-06-01 |
| UK | United Kingdom | 6 | 6 | 1 | 1,927 | 2020-01-01 | 2026-06-02 |
| JP | Japan | 5 | 5 | 1 | 255 | 2020-01-01 | 2026-04-01 |
| DE | Germany | 5 | 5 | 1 | 290 | 2020-01-01 | 2026-04-01 |
| EU | Eurozone (TARGET2) | 5 | 5 | 1 | 488 | 2020-01-01 | 2026-05-29 |
| CA | Canada | 4 | 4 | 1 | 214 | 2020-01-01 | 2026-04-01 |
| CH | Switzerland | 2 | 2 | 1 | 80 | 2020-01-01 | 2025-04-01 |

> US shows 219 defined / 193 active — the 26 inactive are migration-106-deactivated FRED
> duplicates (deliberately excluded from the reload so they never re-activate). KR shows 219 / 217
> — 2 inactive (1 policy-rate + 1 CB-liquidity dup). KR grew 197→217 since the 07-28 snapshot: BBG
> EconDashboards +16 (2026-07-29) and KSD/FSC CD issuance +4 (loaded 2026-08-11).
>
> \* IN "Latest" = **2029-05-01** reflects forward-dated projection/announcement rows (e.g. MSP /
> forward-scheduled series), not actual observations — actual macro series are fresh to 2026-07.

## 3. Tier 1 — deep native-source onboarding

Each of these went through the full onboarding playbook: source-agency HTTP connectors →
fetchers under `scripts/econ/{cc}/{vendor}/` → promoted into `econ.fact_indicator` → wired into
the scheduled `imdr_daily` / `imdr_monthly` runs.

### IN — India (1,580 active / 108k obs / 1946→now)

| Vendor | Name | Active ind |
|--------|------|-----------:|
| rbi | Reserve Bank of India (DBIE / Bulletin) | 569 |
| upag | UPAg — India Agriculture Statistics Portal | 368 |
| ogd | data.gov.in OGD (Agmarknet) | 207 |
| dgcis | DGCIS — India trade statistics | 198 |
| mospi | MoSPI — India Statistics Ministry | 133 |
| nsdl | NSDL — India FPI flows depository | 33 |
| cga | Controller General of Accounts (India MoF) | 30 |
| dpiit | DPIIT / Office of Economic Adviser | 26 |
| fred | FRED (St. Louis Fed) | 7 |
| bis | Bank for International Settlements | 6 |
| imd | India Meteorological Department | 3 |

- **Status:** PROD-LIVE. Track A (15 fetchers, ~1,242 indicators baseline) + Track B
  (govt filings/speeches → `research.dim_report` + Qdrant, ~209 docs).
- **Fresh-food MoM nowcaster:** the OGD ~205 indicators (`INDIA.FOODNOWCAST.*`) cover the
  volatile veg/fruit/spice CPI slice (weekly-median feed + MoM composite). The granular
  `econ.fact_india_mandi` table is intentionally **parked / empty** (pivoted to the focused nowcaster).
- **Track B note:** `imdr_daily` task must run under the conda `imdr` env (Py3.11) for Track B deps.

### NZ — New Zealand (1,112 active / 164k obs / 1914→now)

| Vendor | Name | Active ind |
|--------|------|-----------:|
| statsnz | Stats NZ | 1,105 |
| fred | FRED (St. Louis Fed) | 7 |

- **Status:** PROD-LIVE. Quarterly-dominant (1,064 quarterly series).

### AU — Australia (818 active / 579k obs / 1948→now)

| Vendor | Name | Active ind |
|--------|------|-----------:|
| abs | Australian Bureau of Statistics | 384 |
| aofm | Australian Office of Financial Management | 157 |
| rba | Reserve Bank of Australia | 119 |
| seek | SEEK (job-ad + salary indices) | 90 |
| sqm research | SQM Research (asking rents + vacancy) | 33 |
| cotality | Cotality (formerly CoreLogic) | 16 |
| apra | Australian Prudential Regulation Authority | 8 |
| asx | ASX (Australian Securities Exchange) | 5 |
| anz | ANZ Research (ANZ-Indeed job ads) | 3 |
| fred | FRED (St. Louis Fed) | 3 |

- **Status:** PROD-LIVE. Highest observation count (deep history). Dual-track daily pattern is
  the reference template re-used by IN and US Track B. **2026-07 buildout:** housing + labour
  sources (Cotality HVI, SQM rents/vacancy, APRA by-bank loans, SEEK + ANZ-Indeed job ads) and ABS
  employed-by-industry (LFS Table 04, +60 series) took AU from 539 → 818 active.

### ID — Indonesia (303 active / 115k obs / 1975→now)

| Vendor | Name | Active ind |
|--------|------|-----------:|
| bi | Bank Indonesia | 179 |
| bps | Badan Pusat Statistik (Statistics Indonesia) | 82 |
| djppr | DJPPR Indonesia (Kemenkeu debt-mgmt directorate) | 36 |
| bis | Bank for International Settlements | 6 |

- **Status:** PROD-LIVE.

### US — United States (193 active / 215k obs / 1947→now)

| Vendor | Name | Active ind |
|--------|------|-----------:|
| fred | FRED (St. Louis Fed) | 108 |
| bea | U.S. Bureau of Economic Analysis | 37 |
| bls | U.S. Bureau of Labor Statistics | 29 |
| census | U.S. Census Bureau | 10 |
| treasury_us | U.S. Department of the Treasury (Fiscal Data) | 4 |
| eia | US Energy Information Administration | 3 |
| bis | Bank for International Settlements | 2 |

- **Status:** PROD-LIVE (2026-06-23). Track A (source-agency connectors + 15 fetchers,
  `us_monthly` + dual-track `us_daily`) + Track B (NY Fed/Fed/Treasury filings →
  `research.dim_report` + Qdrant + SharePoint, ~145 docs / 2,320 chunks).
- **Track B note:** `imdr_daily` must run under conda `imdr` env (Py3.11) for Track B deps.

### KR — South Korea (217 active / 184k obs / 1961→now)

| Vendor | Name | Active ind |
|--------|------|-----------:|
| kosis | Korean Statistical Information Service | 164 |
| kofia | Korea Financial Investment Association (freeSIS) | 25 |
| BBG | Bloomberg (EconDashboards, 2026-07-29) | 16 |
| ksd | Korea Securities Depository — CD issuance (via FSC data.go.kr 1160100) | 4 |
| reb | Korea Real Estate Board (R-ONE Open API) | 4 |
| fred | FRED (St. Louis Fed) | 3 |
| bis | Bank for International Settlements | 1 |

- **Status:** PROD-LIVE. **KOFIA freeSIS (25 daily indicators — CD 91d money-market yield + CD
  turnover + MMF flows + fund-AUM by asset class) wired into `kr_daily` 2026-07-20** (migs 115+116).
  **KSD/FSC CD issuance (4 daily indicators — issuance volume/count/avg-rate + outstanding, 5,569 obs
  2020→) built + wired into `kr_daily` 2026-08-04, full history loaded 2026-08-11** (vendor `ksd`, via
  the FSC data.go.kr org 1160100 endpoint; no new migration).
- **Categorisation note (reconciled 2026-07-22 for Quick Monitor):** KR **fiscal** is held
  (`BOK.FISCAL.*` — General Government Revenue/Expenditure/Net Lending/Taxes) but filed under
  "GDP and components"; KR **PPI** is held (`BOK.PPI.*` — 6 series) filed under "Consumer prices".
  Both are recategorise candidates, not data gaps.

### HK — Hong Kong (29 active / 192k obs / 1981→now)

| Vendor | Name | Active ind |
|--------|------|-----------:|
| hkma | Hong Kong Monetary Authority Open Data | 29 |

- **Status:** Loaded. Few indicators but very deep daily history (192k obs).

## 4. Tier 2 — thin FRED-only baselines

These exist only as a handful of FRED mirror series (policy rate, CPI, GDP, etc.) — or FAO food
prices for Worldwide — as placeholders for cross-country comparison. **Not** native-source onboarded.

| cc | Active ind | Obs | Source |
|----|-----------:|----:|--------|
| UK | 6 | 1,927 | FRED |
| JP | 5 | 255 | FRED only |
| DE | 5 | 290 | FRED |
| EU | 5 | 488 | FRED |
| CA | 4 | 214 | FRED |
| CH | 2 | 80 | FRED |
| WW | 6 | 2,622 | UN FAO (food prices) |

### ⚠️ Japan — large discovery built but NOT loaded

The DB shows only 5 FRED series for JP. **However**, a substantial native-source discovery
already exists in `playground/econ/jp/` (NOT loaded, NOT wired):

- **20 fetchers / ~225 indicators / ~70,900+ obs** across 9 sources: e-Stat API, Cabinet Office
  ESRI QE (live GDP), BoJ flat-files + mtshtml CSV, MOF customs CSV + JGB PDFs, METI site XLSX
  (WAF fix 2026-07-10), e-Stat file-catalog (MHLW wages), GPIF annual Excel (NEW 2026-07-10), BIS (DSR + credit-to-GDP).
- Three new fetchers added 2026-07-10: `gpif/fetch_gpif.py` (11 ind, asset-allocation ANNUAL Mar-2015→Mar-2024),
  `mof/fetch_jgb_issuance.py` (9 ind, JGB issuance by tenor ANNUAL), `mof/fetch_jgb_holders.py`
  (19 ind, JGB holder breakdown QUARTERLY Mar-2026, BoJ 47.9% / ¥1,013.8tn outstanding).
- Freshness audit 2026-07-10: 16/17 existing fetchers pull current data. meti/retail WAF fixed (browser UA + primed session; live re-test pending cooldown). meti/iip lags ~1Q (confirmed e-Stat series, not broken).
- Passed code review. Funding-side (tax revenue / deficit) still deferred. Construction deferred (MLIT direct).
- See `docs/admin/econ/japan/japan_indicator_inventory.md`.

**This is the single biggest promotion gap:** Japan is built but not promoted/loaded/wired.

## 5. Indicators by category (active)

| Category | Indicators |
|----------|-----------:|
| Other / uncategorised | 1,257 |
| Balance of payments | 645 |
| Consumer prices | 643 |
| Labour market | 616 |
| GDP and components | 247 |
| Policy rates | 177 |
| Instruments outstanding | 121 |
| CB balance sheet | 100 |
| Sector balance sheets | 96 |
| Housing market | 86 |
| Sentiment & surveys | 84 |
| FX & reserves | 70 |
| Credit aggregates | 67 |
| CB liquidity | 27 |
| Energy market | 26 |
| CB standing facilities | 3 |

## 6. Frequency mix by country (active)

| cc | Breakdown |
|----|-----------|
| AU | Monthly 379 · Quarterly 323 · Daily 88 · Weekly 24 · Event 4 |
| CA | Monthly 3 · Quarterly 1 |
| CH | Quarterly 1 · Monthly 1 |
| DE | Monthly 4 · Quarterly 1 |
| EU | Quarterly 2 · Monthly 2 · Weekly 1 |
| HK | Daily 19 · Monthly 10 |
| ID | Quarterly 127 · Monthly 112 · Daily 37 · Annual 12 · Semiannual 12 · Event 3 |
| IN | Monthly 708 · Annual 377 · Weekly 244 · Quarterly 193 · Daily 53 · Event 5 |
| JP | Monthly 4 · Quarterly 1 |
| KR | Monthly 107 · Quarterly 34 · Daily 26 · Annual 22 · Weekly 8 |
| NZ | Quarterly 1,064 · Monthly 48 |
| UK | Monthly 4 · Daily 1 · Quarterly 1 |
| US | Monthly 87 · Quarterly 45 · Daily 42 · Weekly 18 · Annual 1 |
| WW | Monthly 6 |

## 7. Supporting structures (why the data is here)

The econ indicators feed the research-brief stack and the rates lens:

- **`calendar.cb_events`** — central-bank / macro event calendar; backfilled ~13 months of
  consensus via Bloomberg BQL + TradingEconomics calendar refresh.
- **Rates-playbook engine** (`playground/econ/rates_playbook/`) — per-country quant lens
  (8-driver impulse + repricing ladder + snapshot + monitoring web), grounded in
  `rates.fact_observation` curves + econ actuals (actual ⟵ `econ.fact_indicator`,
  consensus ⟵ `cb_events`).
- **Shared 8-driver taxonomy** — `docs/admin/econ/macro_driver_taxonomy.md`, unifying the
  Atlas / Mercator / playbook lenses.
- **Brief agents** — Atlas (Global Macro Weekly), Mercator (cluster maps), Perry (Weekly Country
  Read) consume these indicators as their quantitative grounding.

## 8. Gaps / next steps

1. **Japan** — fully built in `playground/econ/jp/`, zero loaded. The obvious next promotion
   (~225 indicators, 9 native sources, already code-reviewed; GPIF + JGB fetchers added 2026-07-10).
2. **Tier-2 G10 (UK / DE / EU / CA / CH)** — only FRED stubs; no native-source onboarding yet.
3. **Observation-vs-indicator skew** — AU and HK carry huge obs counts (deep history) for few
   indicators; IN and NZ are indicator-heavy but shallower per series.
4. **US inactive series** — 26 deactivated FRED duplicates retained as inactive (intentional;
   excluded from reload).

---

*Generated from a live DB snapshot. Re-run the queries in `econ.fact_indicator` /
`econ.dim_indicator` to refresh.*
