# Econ Data — Full State (All Countries)

> Snapshot as of **2026-06-24**, pulled live from the IMDR database (`econ.fact_indicator`,
> `econ.dim_indicator`, `dbo.dim_country`, `dbo.dim_vendor`) and cross-referenced with the
> project onboarding history.

## 1. Headline

- **3,883 indicators** defined in `econ.dim_indicator` (**3,823 active**), across **14 countries**.
- **~1,284,549 observations** in `econ.fact_indicator`.
- Two tiers:
  - **Tier 1 — deep native-source onboarding** (7 countries): IN, NZ, AU, ID, US, KR, HK.
    Wired into the scheduled orchestrators, pulling directly from official statistical agencies.
  - **Tier 2 — thin FRED-only baselines** (7 entries): UK, JP, DE, EU, CA, CH, WW.
    A handful of FRED/FAO mirror series for cross-country comparison; **not** natively onboarded.

## 2. Master table — indicators + observations by country

| cc | Country | Indicators | Active | Vendors | Observations | Earliest | Latest |
|----|---------|-----------:|-------:|--------:|-------------:|----------|--------|
| IN | India | 1,475 | 1,475 | 10 | 101,783 | 1946-01-01 | 2026-06-23 |
| NZ | New Zealand | 1,112 | 1,112 | 2 | 160,594 | 1914-06-30 | 2026-05-31 |
| AU | Australia | 539 | 539 | 6 | 440,410 | 1948-07-01 | 2026-06-24 |
| ID | Indonesia | 303 | 303 | 4 | 113,286 | 1975-01-01 | 2026-06-24 |
| US | United States | 219 | 193 | 7 | 211,434 | 1947-01-01 | 2026-06-24 |
| KR | South Korea | 173 | 172 | 4 | 59,083 | 1961-01-01 | 2026-06-15 |
| HK | Hong Kong | 29 | 29 | 1 | 192,083 | 1981-01-02 | 2026-06-03 |
| WW | Worldwide | 6 | 6 | 1 | 2,622 | 1990-01-01 | 2026-05-01 |
| UK | United Kingdom | 6 | 6 | 1 | 1,927 | 2020-01-01 | 2026-06-02 |
| JP | Japan | 5 | 5 | 1 | 255 | 2020-01-01 | 2026-04-01 |
| DE | Germany | 5 | 5 | 1 | 290 | 2020-01-01 | 2026-04-01 |
| EU | Eurozone (TARGET2) | 5 | 5 | 1 | 488 | 2020-01-01 | 2026-05-29 |
| CA | Canada | 4 | 4 | 1 | 214 | 2020-01-01 | 2026-04-01 |
| CH | Switzerland | 2 | 2 | 1 | 80 | 2020-01-01 | 2025-04-01 |

> US shows 219 defined / 193 active — the 26 inactive are migration-106-deactivated FRED
> duplicates (deliberately excluded from the reload so they never re-activate).

## 3. Tier 1 — deep native-source onboarding

Each of these went through the full onboarding playbook: source-agency HTTP connectors →
fetchers under `scripts/econ/{cc}/{vendor}/` → promoted into `econ.fact_indicator` → wired into
the scheduled `imdr_daily` / `imdr_monthly` runs.

### IN — India (1,475 active / 102k obs / 1946→now)

| Vendor | Name | Active ind |
|--------|------|-----------:|
| rbi | Reserve Bank of India (DBIE / Bulletin) | 499 |
| upag | UPAg — India Agriculture Statistics Portal | 368 |
| ogd | data.gov.in OGD (Agmarknet) | 205 |
| dgcis | DGCIS — India trade statistics | 198 |
| mospi | MoSPI — India Statistics Ministry | 133 |
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

### NZ — New Zealand (1,112 active / 161k obs / 1914→now)

| Vendor | Name | Active ind |
|--------|------|-----------:|
| statsnz | Stats NZ | 1,105 |
| fred | FRED (St. Louis Fed) | 7 |

- **Status:** PROD-LIVE. Quarterly-dominant (1,064 quarterly series).

### AU — Australia (539 active / 440k obs / 1948→now)

| Vendor | Name | Active ind |
|--------|------|-----------:|
| abs | Australian Bureau of Statistics | 249 |
| aofm | Australian Office of Financial Management | 157 |
| rba | Reserve Bank of Australia | 119 |
| cotality | Cotality (formerly CoreLogic) | 6 |
| asx | ASX (Australian Securities Exchange) | 5 |
| fred | FRED (St. Louis Fed) | 3 |

- **Status:** PROD-LIVE. Highest observation count (deep history). Dual-track daily pattern is
  the reference template re-used by IN and US Track B.

### ID — Indonesia (303 active / 113k obs / 1975→now)

| Vendor | Name | Active ind |
|--------|------|-----------:|
| bi | Bank Indonesia | 179 |
| bps | Badan Pusat Statistik (Statistics Indonesia) | 82 |
| djppr | DJPPR Indonesia (Kemenkeu debt-mgmt directorate) | 36 |
| bis | Bank for International Settlements | 6 |

- **Status:** PROD-LIVE.

### US — United States (193 active / 211k obs / 1947→now)

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

### KR — South Korea (172 active / 59k obs / 1961→now)

| Vendor | Name | Active ind |
|--------|------|-----------:|
| kosis | Korean Statistical Information Service | 164 |
| reb | Korea Real Estate Board (R-ONE Open API) | 4 |
| fred | FRED (St. Louis Fed) | 3 |
| bis | Bank for International Settlements | 1 |

- **Status:** PROD-LIVE.

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

- **17 fetchers / ~186 indicators / ~70.8k obs** across 8 sources: e-Stat API, Cabinet Office
  ESRI QE (live GDP), BoJ flat-files + mtshtml CSV, MOF customs CSV, METI site XLSX,
  e-Stat file-catalog (MHLW wages), BIS (DSR + credit-to-GDP).
- Passed code review with fixes applied. Funding-side (tax/debt) still partial; construction deferred.
- See `docs/admin/econ/japan/japan_indicator_inventory.md`.

**This is the single biggest promotion gap:** Japan is built but not promoted/loaded/wired.

## 5. Indicators by category (active)

| Category | Indicators |
|----------|-----------:|
| Other / uncategorised | 1,255 |
| Balance of payments | 604 |
| Consumer prices | 596 |
| Labour market | 388 |
| GDP and components | 244 |
| Policy rates | 175 |
| Instruments outstanding | 121 |
| CB balance sheet | 100 |
| Sentiment & surveys | 84 |
| Sector balance sheets | 82 |
| Credit aggregates | 59 |
| FX & reserves | 58 |
| Housing market | 43 |
| Energy market | 26 |
| CB liquidity | 18 |
| CB standing facilities | 3 |

## 6. Frequency mix by country (active)

| cc | Breakdown |
|----|-----------|
| AU | Quarterly 263 · Monthly 184 · Daily 88 · Event 4 |
| CA | Monthly 3 · Quarterly 1 |
| CH | Quarterly 1 · Monthly 1 |
| DE | Monthly 4 · Quarterly 1 |
| EU | Quarterly 2 · Monthly 2 · Weekly 1 |
| HK | Daily 19 · Monthly 10 |
| ID | Quarterly 127 · Monthly 112 · Daily 37 · Annual 12 · Semiannual 12 · Event 3 |
| IN | Monthly 641 · Annual 377 · Weekly 243 · Quarterly 192 · Daily 17 · Event 5 |
| JP | Monthly 4 · Quarterly 1 |
| KR | Monthly 107 · Quarterly 34 · Annual 22 · Weekly 8 · Daily 1 |
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
   (~186 indicators, 8 native sources, already code-reviewed).
2. **Tier-2 G10 (UK / DE / EU / CA / CH)** — only FRED stubs; no native-source onboarding yet.
3. **Observation-vs-indicator skew** — AU and HK carry huge obs counts (deep history) for few
   indicators; IN and NZ are indicator-heavy but shallower per series.
4. **US inactive series** — 26 deactivated FRED duplicates retained as inactive (intentional;
   excluded from reload).

---

*Generated from a live DB snapshot. Re-run the queries in `econ.fact_indicator` /
`econ.dim_indicator` to refresh.*
