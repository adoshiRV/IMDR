# BBG EconDashboards feed

**Status: PROD-LIVE (2026-07-29).** 219 econ indicators · ~16.2k observations · 14 markets
(AU CN HK ID IN JP KR MY NZ PH SG TH TW US) · history 2021→2026, under vendor `BBG`
(`dbo.dim_vendor` id 4). Includes 15 `core_cpi_yoy` (`BBG.CPI.CORE.YOY.{cc}`; AU carries two
— monthly `.AU` + quarterly `.AU.2`; MY is a rebased index not a YoY, unit `index`).

> **Other asset classes checked (2026-07-29):** FX — NEER/REER/TWI stay in econ (the `FX` schema
> is currency-*pair* spot/OHLC/vol; effective-rate *indices* are econ, per BIS/RBA). No equities
> or credit in the catalog. **Commodities** — the source added `oil_price` = `CO1 Comdty`
> (front-month Brent, USD/bbl); it is **excluded from econ** and was loaded into
> `commodities.fact_spot` (`CR_IPE_BRENT`, id 5, which was EMPTY) by
> `scripts/commodities/bbg_econdashboard_oil.py` — 61 month-end obs 2021→2026, latest $87.31.
> **Data-quality flag**: the 2021–2025 prints are clean, but Mar–Jul 2026 is very volatile
> ($72→$112→$118→$92→$73→$87 — a +55% MoM jump in Mar-26); verify against the actual oil tape
> before relying on the recent months.
>
> The source SQLite is **live and growing** — the ingest now WARNs (stderr) on any category it
> doesn't map, so upstream additions are never silently dropped.

> **Rates split (2026-07-29):** the 14 `swap_5y` and 14 `policy_rate` series are **not** in the
> econ mirror — market/rates data belongs in the dedicated `rates` schema. Landing outcome
> (imdr-dbm design; 18 of 28 turned out to already be live in `rates`):
>
> | Series | Disposition |
> |---|---|
> | **9 APAC policy rates** (RBA/HKMA/BI/RBI/BoK/BNM/RBNZ/BSP/BoT) | **DONE** → `rates.fact_bench_rates` (vendor BBG). 9 CBs seeded by migration 119; 16,457 obs loaded by `scripts/rates/bbg_econdashboard_policy.py`. Idempotent. |
> | US `FDTR` | Already `dim_central_bank` id 3 (Citi); not reloaded (bench key has no vendor_id → would collide). |
> | CN/JP/SG/TW "policy" + all 14 5Y swaps | Already live in `rates.fact_observation` via Citi / BBG-IRS mirror; values verified matching. **No load.** |
> | 5Y-swap pre-2021 history | 6 curves (AUD/HKD/KRW/MYR/TWD/THO) have gaps before their live feed starts — **optional** one-time backfill, not built. |
> | ID `GIDN5YR` (govt bond) | Belongs to pending migration 068 `BBGMirrorBondsFeed` (dims already seeded); not this feed. |
> | PH `CTPHP5Y` | Deferred — values look like a **price** not a yield; upstream BQL field needs confirming. |
>
> The remaining 15 econ concepts (CPI/PPI/GDP/current-account/fiscal/PMI/exports/imports/NEER/
> REER/TWI/Big-Mac/surprise/bilateral-trade) live under econ.

## What it is

A structured mirror of the **APAC EconDashboards** local Bloomberg cache into IMDR's econ
schema. EconDashboards is a separate app (`Z:\Business\Research\Dashboard\EconDashboards`)
that pulls ~232 `PX_LAST` series from a logged-in Terminal via BQL, release-gated, into a
SQLite (`data/econ_dashboard.sqlite3`). IMDR treats that SQLite as a **read-only staging
layer** and absorbs its `series` catalog + `observations` history — the dashboard app owns
the Terminal/BQL connection; IMDR never pulls Bloomberg directly for this feed.

## Layout

| Path | Role |
|---|---|
| `src/imdr/domains/econ/bbg_econdashboard.py` | Country-agnostic library: SQLite read + category/unit/frequency/concept resolution → `IndicatorRow`/`ObservationRow`; also `read_ticker_observations()`, the shared low-level SQLite reader the rates + commodities loaders reuse. |
| `scripts/econ/bbg/econdashboard.py` | **econ** ingest. Loops all 14 markets (the SQLite refreshes atomically for all markets, so there is no per-country cadence to fan out), writes country-first parquet under `data/econ/{cc}/bbg/econdashboard/{Y}/{M}/{D}/`, loads each via the canonical loader. |
| `scripts/rates/bbg_econdashboard_policy.py` | **rates** load: 9 APAC policy rates → `rates.fact_bench_rates` (reuses `CentralBankRepository`/`BenchRatesRepository`). |
| `scripts/commodities/bbg_econdashboard_oil.py` | **commodities** load: Brent `CO1` → `commodities.fact_spot` (reuses `CmdtySpotRepository`). |
| `scripts/migrations/load_econ_indicator_from_playground.py` | canonical econ loader — added `_VENDOR_ALIASES {"bbg":"BBG"}` (loader lower-cases `vendor_name`; the `BBG` dim_vendor row is upper-case). |
| `migrations/118_seed_dim_unit_bbg_trade_ccy.sql` | Seeds `myr_mn`/`thb_mn`/`php_mn`/`twd_bn` (trade currencies missing from `dim_unit`). Applied. Gitignored (DBA channel). |
| `migrations/119_seed_rates_dim_central_bank_apac.sql` | Seeds the 9 APAC central banks into `rates.dim_central_bank`. Applied. Gitignored (DBA channel). |

## Identity & mapping

- **Code**: `BBG.{CONCEPT}.{CC}` — e.g. `BBG.PMI.HEADLINE.AU`, `BBG.FX.BIGMAC.JP`,
  `BBG.SENTIMENT.CESI.KR`, `BBG.TRADE.EXPORTS.TW`. `source_code`/`bbg_ticker` = the raw
  Bloomberg ticker (the loader's MERGE key).
- **Categories**: the dashboard's econ categories map onto existing `econ.dim_indicator_category`
  themes (CPI/core-CPI/PPI→`cpi`, GDP→`gdp`, fiscal→`other`, trade/CA→`bop`,
  NEER/REER/TWI/BigMac→`fx`, PMI/surprise→`sentiment`). No new category rows. `swap_5y` +
  `policy_rate` route to the `rates` schema and `oil_price` to `commodities` (see
  `ECON_EXCLUDED_CATEGORIES`); any *other* unmapped category the source adds later is skipped
  with a stderr WARN, never silently dropped.
- **Units are metadata-driven, not guessed** — resolved from Bloomberg's own `currency` +
  `quote_units` fields in the SQLite. Trade series carry their true local currency at native
  scale (`aud_mn`, `idr_bn`, `inr_cr`, `jpy_bn`, `twd_bn`, `myr_mn`, …); bilateral CN/US trade
  = `usd_mn`; yoy prints = `pct_yoy`; rates/swaps = `pct_pa`; CA/fiscal = `pct_of_gdp`.
- **US trade special case**: `GDPTEXP%`/`GDPTIMP%` are a GDP-*contribution* percentage, not an
  absolute trade level, so they use a distinct concept `BBG.TRADE.{EXPORTS,IMPORTS}_CONTRIB.US`
  (unit `pct`) to stay commensurate with other countries' `BBG.TRADE.EXPORTS.{cc}`.

## Cross-check vendor — read before querying

~40 of the 219 econ concepts **also exist from an official source** (e.g. `BBG.CPI.YOY.AU`
alongside `ABS.CPI.HEADLINE_M_YOY.AU`; `BBG.FX.NEER.ID` alongside `BIS.NEER.BROAD.ID`).
This is intentional — BBG is a **parallel cross-check lane**, mirroring the existing
FRED-OECD mirror pattern. **Nothing in the schema marks "primary" vs "cross-check"**,
so any consumer querying by (country, category) without filtering `vendor_id` will
double-count. Filter by `vendor_id` (BBG = 4) or the `BBG.*` code prefix when you specifically
want the Bloomberg series. For the six econ-empty countries (CN, MY, TH, SG, PH, TW) and for
PMI / Big Mac / Citi-surprise / TWI / bilateral trade, BBG is the **only** source in IMDR.

## Refresh loop (idempotent)

```
EconDashboards app refreshes → SQLite advances
  → python -m scripts.econ.bbg.econdashboard        # all 14 markets, revision-aware load
```

The canonical loader is revision-aware: a brand-new obs inserts at vintage 0, a changed value
inserts a new vintage (verified 2026-07-29), an unchanged value is skipped, and a NULL never
clobbers a stored value. Re-runs are safe. `--no-load` / `--no-parquet` / `--country XX` /
`--since` / `--until` are available.

**`imdr_code` stability:** the ingest first reads the persisted `source_code → imdr_code` map for
vendor BBG and passes it to `fetch_econdashboard(existing_codes=…)`, so a code — including a
collision-disambiguation suffix like `BBG.CPI.CORE.YOY.AU.2` — assigned on a prior run is reused
verbatim and never migrates to a different ticker as the upstream catalogue grows.

**Tests:** `tests/unit/test_econ/test_bbg_econdashboard.py` (no-network) covers the unit/frequency/
concept resolvers, the US-trade-contrib override, the excluded-category skips, and the code-stability
contract above.

## Not wired to any scheduler

Deliberately **not** registered in `imdr_{daily,monthly}.py` or any country orchestrator —
that is a separate ask requiring explicit sign-off. Run manually (or wire later) once the
EconDashboards refresh cadence is settled.

## Caveats

- **obs_date labelling**: monthly index series (NEER/REER/PMI) are dated to period-end even
  when only part-month data has landed (Bloomberg convention). Harmless for the loader
  (revision logic keys on value), but treat a current-month print as in-progress, not final.
- **Point-in-time**: vintages accumulate forward from 2026-07-29; the 5y backfill is all
  vintage 0 (not real-time historical).
