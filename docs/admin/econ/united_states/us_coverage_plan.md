# United States (US) — coverage plan (FRED / BLS / BEA / Census / Treasury / EIA)

Last updated: 2026-06-23 (completeness build-out: 3.4 FX/REER ✅, real PCE added, FRED-US on schedule)

> **PROD-LIVE 2026-06-23 (wired into `imdr_monthly` + `imdr_daily`).** 15
> fetchers (BLS ×5 + BEA ×4 + Census ×3 + Treasury ×2 + EIA ×1), 5 connector
> modules at `src/imdr/domains/econ/`, 2 orchestrators (`us_monthly` +
> `us_daily`). 68 unit tests passing; G.6 code-review gate passed (0 blockers).
> Migrations 105 + 106 applied. **Wired into `scripts/imdr_monthly.py:PIPELINES`
> + `scripts/imdr_daily.py:PIPELINES` 2026-06-23.** US now auto-refreshes on the
> existing scheduler cadence alongside KR/ID/AU/NZ/IN. See
> [`united_states_prod_pipeline.md`](united_states_prod_pipeline.md) §"Scheduler
> wiring" for the registered PIPELINES entries.
>
> **Completeness build-out — 2026-06-23.** Three additions (no new migrations):
> (1) **FRED-US scheduled fetchers** — `scripts/econ/us/fred/fred_us_daily.py` (56 series,
> DAILY+WEEKLY, in `us_daily`) + `fred_us_monthly.py` (52 series, MONTHLY+QUARTERLY+ANNUAL,
> in `us_monthly`); shared seed `_fred_seed.py` + `seed_us.yml`. `seed_us.yml` generated from
> the DB active-set after migration 106 — the 26 source-dup series deactivated by migration 106
> are excluded, so a scheduled reload never re-activates them (verified: 26 still inactive
> post-reload). Adds Philly Fed (`GACDFSA066MSFRBPHI`) + Dallas Fed (`BACTSAMFRBDAL`).
> Library: `src/imdr/domains/econ/fred_http.py` (`FredClient`; `get_settings().econ_fred_key`
> + numbered-sibling env rotation). The cross-country OECD mirror (non-US FRED) stays in playground.
> (2) **BIS US NEER/REER** — `scripts/econ/us/bis/bis_us.py` (WS_EER `M.{N,R}.B.US`; in
> `us_monthly`; no key) — **closes cell 3.4 FX/REER ✅**. (3) **Real PCE** — BEA T20806/DPCERX
> (chained 2017 $mn, monthly) added to `bea_personal_income.py` — **closes the 1.1 consumption
> quantity leg**. Hard code review passed; `is_active` landmine confirmed avoided. **Active US
> indicators: 193 / ~198,775 obs. Score: 15 ✅ / 1 ⚠ / 0 ❌.**
>
> The cross-country OECD mirror portion of FRED (non-US FRED) stays in playground,
> consistent with the pattern for Korea/India. Migration 106 reconciled FRED↔source
> (26 exact-dup FRED rows deactivated; BLS price indices recategorised `other → cpi`).

Maps every US cell of the
[macro_economy_wiring_map.md §7.1](../macro_economy_wiring_map.md#71-united-states-us)
to specific vendor identifiers per source agency.

Wiring-map score before this effort: **4 ✅ / 11 ⚠️ / 1 ❌** (only Terms-of-Trade ❌).
Target after Track A: **16/16 ✅** (Korea/Indonesia parity).
**Achieved 2026-06-23: 15 ✅ / 1 ⚠ / 0 ❌** — 3.4 FX/REER closed via BIS; 4.1 Demand Trans is the cosmetic ⚠ (FRED is source-clean, no upstream upgrade warranted).

## Scope (per user 2026-06-22)

- **FRED** (`IMDR_ECON_FRED_KEY`, dual-key) — existing baseline; the multilateral
  mirror (Tier 4). Stays as the cross-country comparison layer + the cells where
  no cleaner source exists (financial conditions, policy rates, FX).
- **BLS** (`IMDR_ECON_BLS_KEY`) — Tier 2 statistical office. CPI, PPI, ECI, JOLTS,
  Employment Situation (CES+CPS), Import/Export Price Indexes, productivity.
  POST JSON API v2, 500 q/day, 50 series/q, 20 yr/q.
- **BEA** (`IMDR_ECON_BEA_KEY`) — Tier 2. GDP/NIPA, Personal Income/PCE, ITA
  (balance of payments), IIP, international trade. GET JSON API.
- **Census** (`IMDR_ECON_CENSUS_KEY`) — Tier 2. MARTS retail sales, FT-900
  international trade, New Residential Construction (housing starts/permits).
  GET JSON (EITS time-series API).
- **Treasury Fiscal Data** (keyless) — Tier 3. Monthly Treasury Statement (MTS),
  Debt-to-the-Penny. REST JSON at `api.fiscaldata.treasury.gov`.
- **EIA** (`IMDR_ECON_EIA_KEY`) — Tier 4 sectoral. Energy spot prices (native,
  beyond FRED's WTI/Brent). v2 JSON API.

**Track B (govt/CB documents, Phase H):** Federal Reserve / FOMC — statements,
minutes, SEP dot-plot, Monetary Policy Report, speeches & testimony. Lands in
`research.dim_report` + Qdrant, **not** `fact_indicator`. See
[`us_govt_doc_sources.md`](us_govt_doc_sources.md) (to be written) and
[`index.md` § Policy & fiscal document sources](index.md).

**Documented gaps (paid / no clean API):**
- **ISM PMI** (Mfg + Services) — subscription. 1.4 PMI leg stays a gap; FRED has
  limited proxies. Conference Board CCI also paid → use Michigan (UMCSENT, free).
- **Treasury TIC** (foreign holdings of US securities) — published as CSV/XML at
  `home.treasury.gov/data/treasury-international-capital-tic-system`, **not** in
  the fiscaldata API. Tier-3 scrape; deferred to a 3.3 follow-up.

---

## The 16-cell source map

Legend for **New?**: ➕ new vendor work · ⤴ promote existing FRED · ✓ FRED already strong.
Source IDs are the **starting shopping list** — verify each against the live API at
build (per [wiring-map §8.1](../macro_economy_wiring_map.md#81-known-fred-code-gaps-to-revisit),
even good-looking IDs occasionally 404; confirm before seeding).

### Growth Engine

| Cell | FRED baseline (now) | Tier-1 upgrade — source IDs | Vendor | Min cadence | New? |
|---|---|---|---|:---:|:---:|
| **1.1 Private Demand** | retail sales, real DPI, cap-goods orders | **Census MARTS** retail & food svcs (`44000` total, `44X72` ex-auto) · **BEA NIPA** T20600 Personal Income, T20804 PCE price · **T20806/DPCERX real PCE chained 2017 $mn (added 2026-06-23 — closes 1.1 consumption quantity leg)** | Census, BEA | M | ➕ |
| **1.2 Fiscal Demand** | FGEXPND/FGRECPT/FYFSGDA188S + monthly MTS | **Treasury MTS** `mts_table_4` (receipts & outlays by category), `mts_table_5` (deficit) · Debt-to-Penny `v2/accounting/od/debt_to_penny` | Treasury | M | ➕ |
| **1.3 External Demand** | EXPGS, IMPGS, NETEXP | **Census FT-900** intltrade (`intltrade/...` goods+services) · **BEA NIPA** T40100 net exports | Census, BEA | M | ➕ |
| **1.4 Macro Core** | GDP, GDPNow, INDPRO, payrolls, CFNAI | **BEA NIPA** T10101 real GDP % chg / T10105 levels (adv/2nd/3rd vintages) · **BLS** CES0000000001 payrolls, LNS14000000 unemp rate, LNS11300000 participation. *PMI = ISM gap.* | BEA, BLS | Q (GDP) / M (labour) | ➕ |

### Inflation Engine

| Cell | FRED baseline (now) | Tier-1 upgrade — source IDs | Vendor | Min cadence | New? |
|---|---|---|---|:---:|:---:|
| **2.1 Input Costs** | WTI, Brent, HH gas, gold | **BLS Import/Export Price** EIUIR (imports all), EIUIQ (exports all) · **EIA** petroleum/pri/spt (WTI/Brent native) | BLS, EIA | M | ➕ |
| **2.2 Producer Prices** | PPIACO, PPIFIS, IR import price | **BLS PPI** WPSFD4 (final demand SA), WPSFD49116 (FD ex food&energy), stage-of-processing WPSID61/WPSID62 | BLS | M | ➕ |
| **2.3 Domestic Costs** | AHE, ECI wages, MICH 1Y exp | **BLS ECI** CIU1010000000000A (total comp civilian, Q) · **BLS JOLTS** quits rate JTS000000000000000QUR · CES0500000003 AHE · productivity PRS85006092 | BLS | Q (ECI) / M | ➕ |
| **2.4 CPI Pressure** | CPI + Core + PCE + 6 more | **BLS CPI-U** CUSR0000SA0 (SA all), CUSR0000SA0L1E (core SA), component tree (shelter SAH1, energy SA0E, food SAF1) · **BEA** PCE price T20804 | BLS, BEA | M | ➕ |

### External & FX

| Cell | FRED baseline (now) | Tier-1 upgrade — source IDs | Vendor | Min cadence | New? |
|---|---|---|---|:---:|:---:|
| **3.1 Terms of Trade** ❌→✅ | *(none — the only ❌)* | **BLS** export-price / import-price ratio (EIUIQ ÷ EIUIR) — closes the last ❌ directly | BLS | M | ➕ |
| **3.2 Current Account** | IEABC, BOPGSTB | **BEA ITA** Indicator=BalCurrAcct + BalGds/BalServ/BalPrimInc/BalSecInc, Frequency=Q | BEA | Q | ➕ |
| **3.3 Capital Account** ❌ | *(none)* | **BEA ITA** financial-account indicators (DI/PI/Other/Reserves) + **BEA IIP** dataset (Net IIP stock). *Treasury TIC = deferred scrape.* | BEA | Q | ➕ |
| **3.4 FX / REER** ✅ | DTWEXBGS, AFE, EME | FRED DXY/H.10 + **BIS NEER+REER broad via `scripts/econ/us/bis/bis_us.py`** (WS_EER `M.{N,R}.B.US`; in `us_monthly`; no key) — **PROD-LIVE 2026-06-23, closes ⚠ → ✅** | FRED, BIS | D / M | ✅ |

### Policy Transmission

| Cell | FRED baseline (now) | Tier-1 upgrade — source IDs | Vendor | Min cadence | New? |
|---|---|---|---|:---:|:---:|
| **4.1 Demand Transmission** | SLOOS, mortgage rates, BUSLOANS | FRED already carries SLOOS (DRTSCILM), H.8 (TOTBKCR), MORTGAGE30US — keep FRED | FRED | Q / W | ✓ |
| **4.2 Balance Sheets** | TDSP, FODSP, CMDEBT, HH mortgage debt | FRED Z.1 flow-of-funds family (CMDEBT, TDSP, HNOREMQ027S) — keep FRED; NY Fed HH-debt optional | FRED | Q | ✓ |
| **4.3 Financial Conditions** | UST curve + IG/HY/BAA OAS + NFCI + VIX | Already strong via FRED (DGS*, BAMLC0A0CM, NFCI, VIXCLS) | FRED | D | ✓ |
| **4.4 Policy Reaction** | Fed funds, EFFR, SOFR, IORB, Fed BS, RRP | Already strong via FRED (FEDFUNDS, EFFR, SOFR, IORB, WALCL, RRPONTSYD) · SEP dot-plot = Track B | FRED | D | ✓ |

**Net:** 4 cells stay FRED-only (4.1–4.4 — Fed is itself the source, FRED mirrors it
cleanly + same-day). 1 cell promotes FRED+BIS (3.4). **11 cells get a ➕ Tier-1
agency** (BLS ×6, BEA ×6, Census ×3, Treasury ×1, EIA ×2 — overlapping).

---

## Build order — headline-first punch list

Per [onboarding_new_country.md §3](../onboarding_new_country.md#step-3--headline-first-in-this-build-order).
Each row = one playground fetcher; promote in batches after sign-off.

### Phase 0 — promote what exists
| # | Work | Cells | Effort |
|---|---|---|:---:|
| P0 | Promote `playground/econ/fred/` → `scripts/econ/us/fred/`; build `us_daily` (rates/FX) + `us_monthly` orchestrators; register in `imdr_daily`/`imdr_monthly` | all baseline | M (gated) |

### Phase 1 — Tier-1 headline pair (BLS + BEA)
| # | Fetcher | Cell | Source | Effort |
|---|---|---|---|:---:|
| 1 | `bls_cpi` — CPI-U headline + core + component tree | 2.4 | BLS | S |
| 2 | `bea_gdp` — real GDP %chg + levels (adv/2nd/3rd) | 1.4 | BEA NIPA | M |
| 3 | `bls_employment_situation` — payrolls, unemp, participation, AHE | 1.4 | BLS | S |
| 4 | `bls_ppi` — final demand + stage-of-processing | 2.2 | BLS | S |

### Phase 2 — pipeline inflation + external
| # | Fetcher | Cell | Source | Effort |
|---|---|---|---|:---:|
| 5 | `bls_import_export_prices` — also closes 3.1 ToT (the ❌) | 2.1 · 3.1 | BLS | S |
| 6 | `bls_eci_jolts` — ECI comp + JOLTS quits/openings + productivity | 2.3 | BLS | M |
| 7 | `bea_ita` — current account + financial account decomposition | 3.2 · 3.3 | BEA ITA | M |
| 8 | `bea_iip` — net IIP stock | 3.3 | BEA IIP | S |

### Phase 3 — demand + fiscal + trade
| # | Fetcher | Cell | Source | Effort |
|---|---|---|---|:---:|
| 9 | `census_retail` — MARTS retail & food services | 1.1 | Census | S |
| 10 | `bea_personal_income` — personal income + real PCE | 1.1 | BEA NIPA | S |
| 11 | `census_trade` — FT-900 goods+services | 1.3 | Census | M |
| 12 | `treasury_mts` — receipts/outlays/deficit + debt-to-penny | 1.2 | Treasury | S |
| 13 | `census_housing` — New Residential Construction (starts/permits) | 1.1 | Census | S |
| 14 | `eia_energy` — WTI/Brent/HH gas spot (native) | 2.1 | EIA | S |

### Expected gaps (acknowledge, don't block)
| Cell | Gap | Workaround |
|---|---|---|
| 1.4 PMI | ISM Mfg/Services paid | Conference Board paid too → Michigan UMCSENT (free) as sentiment proxy; PMI stays ❌-leg |
| 3.3 TIC | foreign holdings = CSV/XML scrape, not fiscaldata API | BEA ITA financial account covers the flow; TIC stock = deferred follow-up |

---

## Per-vendor API mechanics (build notes)

- **BLS v2** — POST `https://api.bls.gov/publicAPI/v2/timeseries/data/` with
  `{seriesid:[...≤50], startyear, endyear, registrationkey, catalog:false}`.
  Response `Results.series[].data[]` is **newest-first**, `period` = `M01..M12`
  (monthly), `Q01..Q05` (quarterly, Q05=annual avg), `value` is a string. 20-year
  window cap per call → chunk for deep history. Throttle to stay under 500/day.
- **BEA** — GET `https://apps.bea.gov/api/data` with `UserID`, `method=GetData`,
  `datasetname` (NIPA/NIUnderlyingDetail/ITA/IIP), `TableName`/`Indicator`,
  `Frequency`, `Year=ALL`, `ResultFormat=JSON`. Errors come back **200-with-Error**
  inside `BEAAPI.Results.Error` — must check, not just HTTP status.
- **Census EITS** — GET `https://api.census.gov/data/timeseries/eits/{program}`
  (`marts`, `resconst`, `ressales`) with `get=cell_value,time_slot_id,...`,
  `category_code`, `seasonally_adj`, `data_type_code`, `time=from+YYYY`, `key`.
  Returns a header-row + data-rows 2-D array (not objects). Activation-link gated.
- **Treasury** — GET `https://api.fiscaldata.treasury.gov/services/api/fiscal_service/{path}`
  with `fields`, `filter`, `sort=-record_date`, `page[size]`, `page[number]`.
  Keyless. Pagination via `links.next`; `meta.total-pages`.
- **EIA v2** — GET `https://api.eia.gov/v2/{route}/data/` with `api_key`,
  `frequency`, `data[0]=value`, `facets[...]`, `sort[0][column]=period`,
  `length`/`offset`. Response under `response.data[]`.

All connectors reuse `src/imdr/connectors/http.py:HTTPClient` where GET-only; BLS
needs a POST helper (add a thin `post_json` or use `httpx` directly in the
connector, mirroring `FredClient`). Library modules land at
`src/imdr/domains/econ/{bls_http,bea_http,census_http,treasury_fiscaldata}.py` on
promotion (country-agnostic, vendor-keyed — see the layout rule).

## Migrations

- **`migrations/105_seed_us_econ_vendors.sql` — APPLIED 2026-06-22.** Registered
  `bls`, `bea`, `census` (`official_statistics`) and `treasury_us`
  (`official_ministry`, suffixed to disambiguate from the existing `treasury_au`).
  `fred` (`official_cb`) and `eia` (`official_statistics`) already existed.
- No new `econ.dim_indicator_category` rows needed — the existing 17 categories
  cover the US series (PPI/MTS/import-export landed under `other`; debt under
  `balance_sheet`).
- **Data loaded** post-migration via `load_econ_indicator_from_playground --vendor {v}`
  (explicit parquet paths) — 82 indicators / 30,563 obs.
- **`migrations/106_us_econ_reconcile_fred_source.sql` — APPLIED 2026-06-23** (UPDATE-only,
  reversible). See the source-reconciliation policy below.
- **2026-06-23: Track A PROD-LIVE** — fetchers at `scripts/econ/us/`, connectors at
  `src/imdr/domains/econ/`, orchestrators wired into `imdr_monthly.py:PIPELINES` +
  `imdr_daily.py:PIPELINES` 2026-06-23. No further migrations required — 105 + 106
  cover all schema needs.

## Source-of-truth policy (FRED vs source agencies)

Decided 2026-06-23: **keep whichever vendor has the better/higher-frequency series.**
For US the source agencies (BLS/BEA/Census/EIA) are the authoritative publisher at
equal frequency for shared headline concepts, so **26 exact-dup FRED mirror rows were
deactivated** (`is_active=0`, reversible) in favour of the source. **FRED is retained
for every series where it is unique or has an edge** — weekly jobless claims, GDPNow,
INDPRO, capacity utilisation, durable/cap-goods orders, sticky CPI, U6, emp-pop ratio,
Case-Shiller, gold, the real-GDP chained *level* (BEA publishes only real %-change),
market-based PCE, the full rates/credit/fx/sentiment/cb_* families, and the OECD
cross-country mirror. Active US dim_indicator after reconcile: **188** (FRED 106 +
BEA 36 + BLS 29 + Census 10 + EIA 3 + Treasury 4).

Category alignment (same migration): the 8 BLS price-index series (PPI ×6 + import/
export ×2) moved `other → cpi`, matching how FRED files the identical US concept and
the KR/ID convention (price indices under `cpi`). MTS fiscal + Census retail left in
`other`.

**Deferred/known gaps (updated 2026-06-23):** vintages stay at vintage-0 (FRED connector
supports point-in-time if a backtest later needs it); real PCE (T20806/DPCERX) **added 2026-06-23
— no longer deferred**; BIS REER **added 2026-06-23 via `bis_us.py` — no longer pending**;
TIC foreign-holdings deferred (scrape); ISM PMI + Conference Board are paid → documented gaps
(Michigan UMCSENT covers sentiment). Regional Fed further surveys (beyond Philly + Dallas now
in `seed_us.yml`) are optional follow-ups.

## Related

- [macro_economy_wiring_map.md §7.1](../macro_economy_wiring_map.md#71-united-states-us) — the 4×4 grid this plan fills
- [united_states_indicator_inventory.md](united_states_indicator_inventory.md) — the canonical "what we have" tracker
- [onboarding_new_country.md](../onboarding_new_country.md) — 5-step playbook + hard rules
- [econ_to_prod.md](../econ_to_prod.md) — gated prod-promotion playbook (Phase G)
- [index.md](index.md) — US landing page + Track B document sources
