# Economics Data Ingest

**Canonical doc.** All public economic-data prints — CPI, GDP, labour, balance of payments, central-bank balance sheets, official rates, government-bond auctions and holdings — flow through the schema and pipelines defined here. Schema decisions, source additions, and sign-offs related to economic data live in this file.

- **Date**: 2026-06-02
- **Owner**: TBD
- **Status**: PLANNING — schema not built; pipelines not started.
- **Companion**: [apac_macro_data_gaps.md](apac_macro_data_gaps.md) — what the desk needs and what's already on Citi. This doc covers the **non-Citi public-data** complement.
- **Source inventories**: `C:\Users\adoshi\Downloads\whitelisted_websites.md` + `AU NZ PUBLIC DATA.xlsx` (Y/N priority flags per series).
- **Supersedes**: ad-hoc planning in `playground/macro/funding/design.md` (sandbox) and the econ-schema questions blocking [IMD-15](https://linear.app/imdr/issue/IMD-15) / [IMD-16](https://linear.app/imdr/issue/IMD-16) / [IMD-17](https://linear.app/imdr/issue/IMD-17). Those tickets reference the old `macro` schema name — they'll need updating to `econ` when the schema lands.

---

## 1. Scope

**In scope** — everything below lands via the schema in §4:

- National statistics offices (ABS, Stats NZ, BLS, ONS, Destatis, etc.).
- Central-bank statistical releases (RBA, RBNZ, Fed, ECB, BoJ, BoK, MAS, RBI, …).
- Debt management offices (AOFM, US Treasury, RBNZ DMO, DMO UK, …).
- Multilateral aggregators (FRED, IMF, World Bank, BIS, OECD, DBnomics).
- Energy / commodity public data where it's macro-relevant (MBIE NZ Energy Quarterly, EIA petroleum reports).

**Out of scope** — these have other homes:

- **Bank research views / trade ideas** (e.g. `NZ_RBNZ_Research_Collation.xlsx` — Bank Views Matrix, Trade Ideas, View-Change Triggers) → research-RAG ingest under `imdr-research`, not here.
- **Anything already on Citi Velocity** — see [apac_macro_data_gaps.md](apac_macro_data_gaps.md). CESI / CITIPAIN / CTOT belong with the Citi pipelines.
- **Single-name / corporate** issuance — out per the standing [relevance filter](../../../../memory/project_research_relevance_filter.md).
- **Market microstructure** (tick / quote / depth) — that's the FX/rates live pipelines, not macro.

---

## 2. Source catalogue

Cadence / format / why for every source we intend to ingest. Priority comes from the desk's Y/N pass on `AU NZ PUBLIC DATA.xlsx`.

### 2.1 Australia

| Source | Cadence | Format | Why we want it |
|---|---|---|---|
| **ABS — CPI** ([url](https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/consumer-price-index-australia)) | Monthly + quarterly | XLSX, Data Explorer | Headline + component CPI, trimmed mean / weighted median, tradables vs non-tradables, capital-city splits. |
| **AOFM — Data Hub** ([url](https://www.aofm.gov.au/data-hub)) | Daily / monthly / per-event | XLSX, CSV | AGS outstanding by tenor, bond/TIB issuance & buybacks, syndication investor breakdowns, non-resident holdings, AGS turnover, **daily yield decomposition + term-premium estimates**, AUD IRS + XCCY swap transactions. |
| **ASX — Bonds + Austraclear** ([url](https://www.asx.com.au/markets/trade-our-cash-market/equity-market-prices/bonds)) | Intraday (delayed) / daily | Web, XLSX, CSV (subscriber) | Exchange-traded AGB prices, AGB yield-curve chart data, AGB ISIN/RIC/BBG cross-ref, Austraclear debt/repo/money-market activity. |
| **RBA — Statistics** ([url](https://www.rba.gov.au/statistics/)) | Daily → annual | XLSX, CSV | OCR, balance sheet (weekly), monetary + financial aggregates, AUD FX + TWI, money-market rates, govt-bond yields, zero-coupon analytical series, household + business finance distributions, payments stats, market-economist forecasts, historical RBA forecasts, Chart Pack. |
| **RBA — Historical Data** ([url](https://www.rba.gov.au/statistics/historical-data.html)) | One-shot | XLSX, CSV | Long-run series: FX since 1969, money-market & govt-bond yields to mid-90s, annual macro/banking to 1949. |

**Skip-list** (flagged N): banknotes/counterfeits, individual-bank assets/liabilities 1991-98, Treasury-bond tender history pre-2006, RMBS pre-2020, retail register buybacks, ATM/RTGS payment stats.

### 2.2 New Zealand

| Source | Cadence | Format | Why we want it |
|---|---|---|---|
| **Stats NZ — Price indexes** ([url](https://www.stats.govt.nz/topics/price-indexes/)) | Monthly (SPI) + quarterly (CPI, PPI, HLPI, LCI, OTI) | XLSX, CSV, Infoshare | Quarterly CPI + components, monthly SPI (food / fuel / rents / accommodation / airfares), Household Living-Costs PIs, PPI (output + input), CGPI, FEPI, LCI, overseas trade indexes. |
| **RBNZ — Statistics** ([url](https://www.rbnz.govt.nz/statistics)) | Daily → quarterly | XLSX, XLS | OCR, Real TWI, wholesale + retail rates, FX (daily + monthly + historical), monetary aggregates, registered-bank balance sheets, non-bank balance sheets, govt-bond turnover + non-resident holdings, RBNZ balance sheet + OMO, settlement-cash influences, standing facilities, official overseas reserves, NZ IMF position, household balance sheet, business + consumer expectations surveys. |
| **data.govt.nz / MBIE** ([url](https://catalogue.data.govt.nz/)) | Weekly → annual | XLSX, CSV, JSON | Weekly fuel-price monitoring, Energy Quarterly (oil/gas/coal/electricity/prices), petroleum reserves, MRTE tourism estimates, labour-market reports. |

### 2.3 Hong Kong

| Source | Cadence | Format | Why we want it |
|---|---|---|---|
| **HKMA — Daily Monetary Statistics** ([api](https://api.hkma.gov.hk/public/market-data-and-statistics/daily-monetary-statistics/)) | Daily | REST JSON (paginated, no auth) | HKMA Aggregate Balance, Monetary Base, Exchange Fund Bills+Notes outstanding (combined), Certificates of Indebtedness. The Aggregate Balance is the desk's #1 HK liquidity signal. Full daily history from 1997. |

**Known gap**: the public API combines EF Bills + EF Notes outstanding into one series (`outstanding_efbn`). Separating them needs BBG (`HKEFBOUT Index` / `HKEFNOUT Index`) or an HKMA data-services contact.

### 2.4 Global / multi-country

| Source | Access | Best use |
|---|---|---|
| **FRED** ([url](https://fred.stlouisfed.org/)) | REST API, free key | US macro (CPI/PCE/GDP/labour/NFCI), Fed RRP/TGA/balance sheet, plus mirrored ECB/BoJ/BoE/IMF series. **Highest-leverage single connector.** |
| **IMF Data** ([url](https://data.imf.org/)) | SDMX + REST | WEO, IFS, BoP, FSI — global macro & cross-country comparability. |
| **World Bank — Open Data + Indicators** ([url](https://data.worldbank.org/)) | REST (no key) | WDI + International Debt Statistics + Global Economic Monitor; ~16k indicators across 45 databases. |
| **BIS — Data Portal** ([url](https://data.bis.org/)) | CSV, SDMX, REST | Credit-to-GDP gaps, debt-service ratios, OTC + FX turnover (Triennial), residential + commercial property prices, central-bank total assets, policy rates. |
| **ECB — Data Portal / SDW** ([url](https://data.ecb.europa.eu/), [API docs](https://data.ecb.europa.eu/help/api/overview)) | CSV, SDMX, REST | HICP + components, MFI lending, euro-area yield curves, ESTR + compounded ESTR, ECB balance sheet, TARGET balances, Consumer Expectations Survey. |
| **OECD — Data Explorer** ([url](https://data-explorer.oecd.org/), [API docs](https://www.oecd.org/en/data/insights/data-explainers/2024/09/api.html)) | SDMX API (XML/JSON/CSV) | DM macro: GDP / CPI / unemployment / Economic Outlook projections, PPPs, foundations-for-growth indicators. |
| **DBnomics** ([url](https://db.nomics.world/)) | REST, free | Convenience router over ECB/IMF/OECD/FRED/national stats — fallback when an upstream API is flaky. |
| **Trading Economics** ([url](https://tradingeconomics.com/)) | REST (paid for full) | Economic calendar + macro API. Cross-check vs Bloomberg calendar. |
| **BOJ — Statistics** ([url](https://www.boj.or.jp/en/statistics/)) | XLSX, CSV | Japan macro + JGB data not on Citi. |
| **BoK — ECOS** ([url](https://ecos.bok.or.kr/)) | REST, free | Korea macro + rates. |
| **MAS — Statistics** ([url](https://www.mas.gov.sg/statistics)) | XLSX | Singapore FX intervention, liquidity ops, money-market rates. |
| **RBI — DBIE** ([url](https://dbie.rbi.org.in/)) | XLSX, REST | India GSecs, banking, FX reserves. |

---

## 3. Schema

Two schemas: **`econ`** for time-series indicators (the bulk of the data), **`funding`** for per-event and per-line records that don't fit the indicator shape (auctions, holdings, CB balance-sheet lines).

### 3.1 Why a generic indicator table

Most public economic data is "country + indicator + date + value". A per-release table (`fact_cpi_au`, `fact_cpi_nz`, `fact_cpi_us`, …) would explode into hundreds of sparse tables. The desk's question is "give me CPI YoY across G10 + APAC on one chart" — that's one `WHERE` clause on a generic table, not a UNION across dozens.

Carve-outs go to dedicated tables only when the data has enough structure to justify it: auctions (bid-cover, tail, investor breakdown), holdings (per-ISIN × holder-country month-end), CB balance sheets (line-item asset/liability tagging).

### 3.2 `econ.dim_indicator` — the catalog

One row per (vendor, source_code). Every series we ingest is registered here first.

```sql
CREATE TABLE econ.dim_indicator (
    indicator_id            INT IDENTITY(1,1) NOT NULL,
    imdr_code               VARCHAR(128)   NOT NULL,   -- 'FRED.CPIAUCSL', 'RBNZ.OCR', 'ABS.CPI.HEADLINE.AU'
    vendor_id               INT            NOT NULL,   -- FK dbo.dim_vendor
    source_code             VARCHAR(128)   NOT NULL,   -- vendor's native series id
    bbg_ticker              VARCHAR(64)    NULL,       -- 'CPI YOY Index' when one exists
    description             NVARCHAR(512)  NOT NULL,
    unit                    VARCHAR(32)    NOT NULL,   -- '%_yoy', 'index', 'aud_mn', 'bp', 'persons'
    frequency_id            TINYINT        NOT NULL,   -- FK dbo.dim_frequency
    country_id              INT            NULL,       -- FK dbo.dim_country (NULL = global aggregate)
    category                VARCHAR(32)    NOT NULL,
    is_seasonally_adjusted  BIT            NOT NULL CONSTRAINT DF_dim_indicator_sa DEFAULT 0,
    is_active               BIT            NOT NULL CONSTRAINT DF_dim_indicator_active DEFAULT 1,
    created_at              DATETIMEOFFSET NOT NULL CONSTRAINT DF_dim_indicator_ct DEFAULT SYSDATETIMEOFFSET(),
    updated_at              DATETIMEOFFSET NOT NULL CONSTRAINT DF_dim_indicator_ut DEFAULT SYSDATETIMEOFFSET(),

    CONSTRAINT PK_dim_indicator PRIMARY KEY NONCLUSTERED (indicator_id),
    CONSTRAINT UQ_dim_indicator_imdr_code UNIQUE (imdr_code),
    CONSTRAINT UQ_dim_indicator_source UNIQUE (vendor_id, source_code),
    CONSTRAINT FK_dim_indicator_vendor    FOREIGN KEY (vendor_id)    REFERENCES dbo.dim_vendor(vendor_id),
    CONSTRAINT FK_dim_indicator_frequency FOREIGN KEY (frequency_id) REFERENCES dbo.dim_frequency(frequency_id),
    CONSTRAINT FK_dim_indicator_country   FOREIGN KEY (country_id)   REFERENCES dbo.dim_country(country_id),
    CONSTRAINT CK_dim_indicator_category  CHECK (category IN
        ('cpi','gdp','labour','bop','balance_sheet','rates','fx','housing','credit','sentiment','energy','tourism',
         'liquidity','cb_facility','cb_balance_sheet','instr_outstand','other'))
);

CREATE INDEX IX_dim_indicator_category_country
    ON econ.dim_indicator(category, country_id) INCLUDE (imdr_code);
```

**`imdr_code` naming**: dotted, namespaced, stable — `{SOURCE}.{CATEGORY}.{KEY}[.{COUNTRY}]`. Examples: `FRED.CPIAUCSL`, `ABS.CPI.HEADLINE.AU`, `RBNZ.OCR`, `BIS.CGDP_GAP.US`. Matches the `playground/macro/funding/design.md` convention.

**Category set evolution note**: The original set (`cpi`, `gdp`, `labour`, `bop`, `balance_sheet`, `rates`, `fx`, `housing`, `credit`, `sentiment`, `energy`, `tourism`, `other`) was extended during the HKMA playground prototype (2026-06-02) to add four CB-liquidity-focused values: `liquidity` (aggregate balance / reserve levels), `cb_facility` (standing facilities — RRP, discount window, SRF), `cb_balance_sheet` (monetary base and total-assets aggregates), and `instr_outstand` (outstanding instrument counts — EF Bills+Notes, CIs). The original `balance_sheet` value is kept for non-CB balance sheets (e.g. household, registered-bank). The set may grow further as FRED/BIS/ECB sources land in Phase 4.

### 3.3 `econ.fact_indicator` — the data

Vintage-aware: every print we ever see is kept. `vintage = 0` is the first print; `1+` is each revision.

```sql
CREATE TABLE econ.fact_indicator (
    indicator_id   INT             NOT NULL,
    obs_date       DATE            NOT NULL,         -- reference-period START (2026-04-01 = "April 2026 CPI")
    vintage        SMALLINT        NOT NULL,         -- 0 = first print, 1+ = revisions
    release_date   DATETIMEOFFSET  NOT NULL,         -- when the print actually hit
    value          DECIMAL(28, 10) NULL,             -- NULL = row published with no value yet
    is_preliminary BIT             NOT NULL CONSTRAINT DF_fact_indicator_prelim DEFAULT 0,
    ingested_at    DATETIMEOFFSET  NOT NULL CONSTRAINT DF_fact_indicator_ingested DEFAULT SYSDATETIMEOFFSET(),

    CONSTRAINT PK_fact_indicator PRIMARY KEY NONCLUSTERED (indicator_id, obs_date, vintage),
    CONSTRAINT FK_fact_indicator_indicator FOREIGN KEY (indicator_id) REFERENCES econ.dim_indicator(indicator_id)
)
WITH (DATA_COMPRESSION = PAGE);

-- Clustered on obs_date for time-range scans.
CREATE CLUSTERED INDEX CIX_fact_indicator_obs
    ON econ.fact_indicator(obs_date, indicator_id);

-- "Latest vintage" covering index.
CREATE INDEX IX_fact_indicator_latest
    ON econ.fact_indicator(indicator_id, obs_date DESC, vintage DESC)
    INCLUDE (release_date, value);
```

Query patterns this supports cheaply:

- "CPI YoY across AU/NZ/US, last 2y, latest vintage" — `WHERE category='cpi'`, filter to `MAX(vintage)` per `(indicator_id, obs_date)`.
- "Real-time CPI history as it was known on date X" — `WHERE vintage = 0 AND release_date <= X`.
- "Latest print per indicator" — `ROW_NUMBER() OVER (PARTITION BY indicator_id ORDER BY obs_date DESC, vintage DESC) = 1`.

### 3.4 `funding.fact_govt_auction` — per-event auctions

AOFM, RBNZ DMO, US Treasury, DMO UK all fit.

```sql
CREATE TABLE funding.fact_govt_auction (
    auction_id        BIGINT IDENTITY(1,1) NOT NULL,
    vendor_id         INT            NOT NULL,        -- FK dbo.dim_vendor (AOFM / RBNZ DMO / etc.)
    country_id        INT            NOT NULL,        -- FK dbo.dim_country
    auction_date      DATE           NOT NULL,
    settlement_date   DATE           NULL,
    isin              VARCHAR(12)    NULL,
    security_code     VARCHAR(32)    NOT NULL,        -- AOFM line ('TB145'), Treasury CUSIP, RBNZ code
    security_type     VARCHAR(16)    NOT NULL,        -- 'bond'|'tib'|'note'|'bill'|'syndication'|'switch'|'buyback'|'tap'
    coupon            DECIMAL(8,5)   NULL,
    maturity_date     DATE           NULL,
    amount_offered    DECIMAL(18,2)  NULL,            -- face value
    amount_allotted   DECIMAL(18,2)  NULL,
    bid_to_cover      DECIMAL(8,4)   NULL,
    cutoff_yield      DECIMAL(10,6)  NULL,
    weighted_avg_yld  DECIMAL(10,6)  NULL,
    tail_bp           DECIMAL(8,4)   NULL,            -- cutoff − weighted-avg, bp
    high_price        DECIMAL(14,8)  NULL,
    weighted_avg_pr   DECIMAL(14,8)  NULL,
    investor_breakdown_json NVARCHAR(MAX) NULL,       -- syndication books when published
    ingested_at       DATETIMEOFFSET NOT NULL CONSTRAINT DF_fact_govt_auction_ingested DEFAULT SYSDATETIMEOFFSET(),

    CONSTRAINT PK_fact_govt_auction PRIMARY KEY NONCLUSTERED (auction_id),
    CONSTRAINT UQ_fact_govt_auction_natural UNIQUE (vendor_id, country_id, auction_date, security_code, security_type),
    CONSTRAINT FK_fact_govt_auction_vendor  FOREIGN KEY (vendor_id)  REFERENCES dbo.dim_vendor(vendor_id),
    CONSTRAINT FK_fact_govt_auction_country FOREIGN KEY (country_id) REFERENCES dbo.dim_country(country_id),
    CONSTRAINT CK_fact_govt_auction_type CHECK (security_type IN
        ('bond','tib','note','bill','syndication','switch','buyback','tap'))
)
WITH (DATA_COMPRESSION = PAGE);

CREATE CLUSTERED INDEX CIX_fact_govt_auction_date
    ON funding.fact_govt_auction(auction_date, country_id);
```

### 3.5 `funding.fact_govt_holdings` — per-line holdings snapshots

AOFM non-resident holdings, RBNZ non-resident bond holdings, US TIC custody.

```sql
CREATE TABLE funding.fact_govt_holdings (
    country_id        INT            NOT NULL,  -- FK dbo.dim_country (issuing country)
    isin              VARCHAR(12)    NOT NULL,
    security_code     VARCHAR(32)    NOT NULL,
    holder_type       VARCHAR(32)    NOT NULL,  -- 'non_resident'|'central_bank'|'official_sector'|'aggregate'
    holder_country_id INT            NULL,      -- FK dbo.dim_country (when broken out by holder country)
    obs_date          DATE           NOT NULL,  -- month-end (or as published)
    face_value        DECIMAL(18,2)  NULL,
    market_value      DECIMAL(18,2)  NULL,
    pct_outstanding   DECIMAL(8,5)   NULL,
    vendor_id         INT            NOT NULL,
    ingested_at       DATETIMEOFFSET NOT NULL CONSTRAINT DF_fact_govt_holdings_ingested DEFAULT SYSDATETIMEOFFSET(),

    CONSTRAINT PK_fact_govt_holdings PRIMARY KEY NONCLUSTERED
        (country_id, isin, holder_type, ISNULL(holder_country_id, 0), obs_date),
    CONSTRAINT FK_fact_govt_holdings_country FOREIGN KEY (country_id)        REFERENCES dbo.dim_country(country_id),
    CONSTRAINT FK_fact_govt_holdings_holder  FOREIGN KEY (holder_country_id) REFERENCES dbo.dim_country(country_id),
    CONSTRAINT FK_fact_govt_holdings_vendor  FOREIGN KEY (vendor_id)         REFERENCES dbo.dim_vendor(vendor_id)
)
WITH (DATA_COMPRESSION = PAGE);

CREATE CLUSTERED INDEX CIX_fact_govt_holdings_obs
    ON funding.fact_govt_holdings(obs_date, country_id);
```

### 3.6 `funding.fact_cb_balance_sheet` — central-bank line items

Weekly Fed H.4.1, weekly RBA, weekly ECB WFS, RBNZ.

```sql
CREATE TABLE funding.fact_cb_balance_sheet (
    country_id      INT            NOT NULL,  -- FK dbo.dim_country (CB's home country)
    line_item_code  VARCHAR(64)    NOT NULL,  -- 'WALCL.TREASURIES', 'RBA.AGS_HOLDINGS', 'RBNZ.SETTLEMENT_CASH'
    obs_date        DATE           NOT NULL,
    value           DECIMAL(20,2)  NOT NULL,
    unit            VARCHAR(16)    NOT NULL,  -- 'usd_mn'|'aud_mn'|'nzd_mn'|'eur_mn'
    side            CHAR(1)        NOT NULL,  -- 'A' assets | 'L' liabilities | 'C' capital
    vendor_id       INT            NOT NULL,
    ingested_at     DATETIMEOFFSET NOT NULL CONSTRAINT DF_fact_cb_bs_ingested DEFAULT SYSDATETIMEOFFSET(),

    CONSTRAINT PK_fact_cb_balance_sheet PRIMARY KEY NONCLUSTERED (country_id, line_item_code, obs_date),
    CONSTRAINT FK_fact_cb_bs_country FOREIGN KEY (country_id) REFERENCES dbo.dim_country(country_id),
    CONSTRAINT FK_fact_cb_bs_vendor  FOREIGN KEY (vendor_id)  REFERENCES dbo.dim_vendor(vendor_id),
    CONSTRAINT CK_fact_cb_bs_side    CHECK (side IN ('A','L','C'))
)
WITH (DATA_COMPRESSION = PAGE);

CREATE CLUSTERED INDEX CIX_fact_cb_bs_obs
    ON funding.fact_cb_balance_sheet(obs_date, country_id);
```

### 3.7 Dim reuse — nothing new to build

| Dim | Source | Already used by |
|---|---|---|
| `dbo.dim_vendor` | Existing | All fact tables |
| `dbo.dim_frequency` | Migration 023 (TICK/SNAPSHOT/MINUTE/HOURLY/DAILY/WEEKLY/MONTHLY/QUARTERLY/ANNUAL/EVENT) | `fx.fact_fx_rate` |
| `dbo.dim_country` | Country-anchor calendar restructure | `equities.dim_index.country_id`, calendar tables |

### 3.8 Migrations

Per the `{NNN}_{description}.sql` convention. Order matters — schemas first, then `dim_indicator` (referenced by `fact_indicator`), then facts.

```
migrations/
  0NN_create_econ_schema.sql               -- CREATE SCHEMA econ; CREATE SCHEMA funding;
  0NN_create_econ_dim_indicator.sql
  0NN_create_econ_fact_indicator.sql
  0NN_create_funding_fact_govt_auction.sql
  0NN_create_funding_fact_govt_holdings.sql
  0NN_create_funding_fact_cb_balance_sheet.sql
```

---

## 4. Pipeline conventions

Every economic-data pipeline follows the standard IMDR layout, with a few specifics for this domain.

### 4.1 File layout

```
src/imdr/connectors/
  fred.py                          # one connector per source
  rba.py
  rbnz.py
  abs.py
  statsnz.py
  bis.py
  ecb.py
  oecd.py
  imf.py
  worldbank.py
  ...

src/imdr/domains/econ/
  __init__.py
  pipeline_indicator.py            # generic fact_indicator pipeline base
  pipeline_auction.py              # govt_auction pipeline (funding schema)
  pipeline_holdings.py             # govt_holdings pipeline (funding schema)
  pipeline_cb_balance_sheet.py     # cb_balance_sheet pipeline (funding schema)
  seeds/
    fred.yml                       # series-id → indicator metadata
    rba.yml
    rbnz.yml
    ...

scripts/econ/{source}/
  {source}_daily.py
  {source}_monthly.py
  ...

migrations/0NN_*.sql
```

### 4.2 Seeding `dim_indicator`

Each source has a YAML seed file enumerating the series to ingest. The pipeline's `transform()` calls a shared `bulk_seed_indicators()` helper (idempotent), so `dim_indicator` self-populates on first run — same pattern as `dim_curve` in the rates pipeline.

```yaml
# src/imdr/domains/econ/seeds/fred.yml
indicators:
  - source_code: CPIAUCSL
    imdr_code: FRED.CPI.HEADLINE_SA.US
    description: Consumer Price Index for All Urban Consumers
    unit: index
    frequency: MONTHLY
    country: US
    category: cpi
    is_seasonally_adjusted: true
    bbg_ticker: CPI INDX Index
  - source_code: UNRATE
    imdr_code: FRED.LABOUR.UNRATE.US
    ...
```

### 4.3 Raw archive

Like the Citi pipelines, every raw pull is parquet-archived before normalisation. Folder pattern matches existing convention:

```
data/parquet/econ/{source}/{YYYY}/{MM}/{DD}/{source}_{YYYYMMDD}_{HHMM}.parquet
```

Re-processing into `fact_indicator` becomes cheap when the indicator mapping changes.

### 4.4 Scheduling

- **Release-time discipline**: ABS / Stats NZ / RBNZ / Fed publish on fixed clocks. Pipelines must run *after* the official release time, not on a generic 06:00 UTC cron. Each pipeline owns a release-time-aware scheduler entry.
- **Daily / monthly / quarterly schedulers**: register pipelines in the existing `scripts/imdr_daily.py`, `imdr_monthly.py`, `imdr_quarterly.py` per cadence.
- **RBNZ scraping**: RBNZ publishes terms-of-use for automated access. Use a clear `User-Agent`, throttle to ≤ 4 concurrent on a single host, no NZ public holidays. Aligns with [no anti-detection in research scrapers](../../../../memory/feedback_no_anti_detection_research.md).

### 4.5 Revision handling

- All sources that publish revisions are pulled in full each run; the pipeline diffs against `fact_indicator` and inserts a new `vintage` row only when the value changed for an existing `(indicator_id, obs_date)`.
- `vintage = 0` is the first time we ever see the row. Each later change is `vintage = MAX(vintage) + 1`.
- For sources that *don't* publish history (rare), `vintage` stays at 0 forever.

### 4.6 Quality checks

Standard `RowCountCheck` + `NullCheck` per pipeline. Add domain-specific checks:

- **CPI / GDP** — `PercentageChangeCheck` on YoY values to catch units mistakes (10× / 100× errors).
- **Balance sheets** — `BalanceSheetIdentityCheck`: `SUM(side='A') ≈ SUM(side='L') + SUM(side='C')` per `(country_id, obs_date)`.
- **Auctions** — `bid_to_cover > 0`, `cutoff_yield BETWEEN -5 AND 30` (catches unit slips).

---

## 5. Build sequence

Ordered by leverage (data per unit of build effort) and what unblocks other work.

### Phase 0 — Playground prototype (current)

Prove out connectors, indicator mapping, and parquet shape under `playground/econ/` **before** any migration lands. Per the standing [playground-only-for-exploration](../../../../memory/feedback_playground_only_for_exploration.md) rule. The promotion path (Phases 1–2 below) only kicks in once the desk has reviewed the parquet samples and signed off on the dim/fact shape.

```
playground/econ/
  README.md                         # status, promotion checklist
  schema_prototype.py               # dataclasses mirroring §3 dim_indicator + fact_indicator
  fred/
    connector.py                    # REST + key
    seed.yml                        # ~12 US headline indicators
    fetch.py                        # one-shot: pull → parquet sample
    sample_output/
  rba/
    fetch.py                        # OCR + monetary aggregates + FX + bond yields
    sample_output/
  rbnz/
    fetch.py                        # OCR + TWI + balance sheet
    sample_output/
  abs/
    fetch.py                        # CPI workbook
    sample_output/
  statsnz/
    fetch.py                        # quarterly CPI + monthly SPI
    sample_output/
```

### Phase 1 — Promote schema + FRED to production

Only after Phase 0 review:

1. Land `econ` + `funding` schemas + `dim_indicator` + `fact_indicator` migrations. Unblocks [IMD-17](https://linear.app/imdr/issue/IMD-17) (which will become `econ.fact_policy_rates`).
2. Promote playground FRED connector → `src/imdr/connectors/fred.py`.
3. Promote `fred.yml` seed → `src/imdr/domains/econ/seeds/fred.yml`.
4. Daily ingest `scripts/econ/fred/fred_daily.py`; register in `imdr_daily.py`.

### Phase 2 — Promote APAC central-bank data

5. **RBA** statistical tables → `econ.fact_indicator`. Seed: OCR, monetary aggregates (D3), credit aggregates (D2), FX rates (F11), money-market rates (F1), govt-bond yields (F2).
6. **RBNZ** → `econ.fact_indicator`: OCR, TWI, wholesale + retail rates, balance sheet, monetary aggregates.
7. **ABS CPI** monthly job (`imdr_monthly.py`).
8. **Stats NZ** quarterly CPI / PPI / HLPI / LCI / OTI + monthly SPI.

### Phase 3 — Auctions, holdings, term premia

9. **AOFM** daily yield-decomposition + term-premium CSV. Auctions → `funding.fact_govt_auction`. Non-resident holdings → `funding.fact_govt_holdings`.
10. **RBNZ debt-securities** (govt-bond turnover, non-resident holdings, Kauri bonds) → `funding.fact_govt_holdings`.
11. **RBA + Fed + RBNZ + ECB** weekly balance sheets → `funding.fact_cb_balance_sheet`.

### Phase 4 — Global aggregators

12. **BIS**: credit-to-GDP gaps, debt-service ratios, central-bank policy rates, CB total assets (SDMX endpoint).
13. **ECB SDW**: HICP, ESTR + compounded ESTR, MFI lending.
14. **OECD**: Economic Outlook projections, PPPs.
15. **World Bank WDI** (annual schedule).
16. **IMF IFS / WEO** (cross-country comparability layer).

### Phase 5 — Asia singles + sector data

17. **BOJ**, **BoK ECOS**, **MAS**, **RBI DBIE** — country-specific connectors, all into the generic `fact_indicator`.
18. **MBIE NZ Energy Quarterly** + weekly fuel prices.
19. **MRTE tourism estimates** (NZ).

---

## 6. Sign-off status

**Resolved 2026-06-02**:

1. ~~Schema split~~ — **`econ` + `funding`**. Two schemas (renamed from `macro` for brevity).
2. ~~Govt-bond yields routing~~ — go into **`rates.fact_govtbond`** (when [IMD-15](https://linear.app/imdr/issue/IMD-15) lands), with `vendor_id` distinguishing Citi vs AOFM vs RBNZ. They stay out of `econ.fact_indicator`.
3. ~~Phase-1 scope~~ — **FRED + RBA + RBNZ + ABS CPI + Stats NZ price indexes** in the first build.

**Still open**:

4. **Vintage column** — keep from day one? (Adds 2 bytes/row; enables real-time history.) Default recommendation: yes. → Engineer will build with vintage; if you want it stripped, say so before the migration lands.
5. **`value DECIMAL(28,10)`** — enough for both pp-level rates and trillion-AUD balance-sheet figures. OK?
6. **`investor_breakdown_json NVARCHAR(MAX)`** on auctions — semi-structured here, or break into a child `fact_auction_investors` table? (Only matters at Phase 3; safe to defer.)
7. ~~FRED API key~~ — registered, lives under `IMDR_ECON_FRED_KEY` in `.env` (resolved 2026-06-02).

---

## 7. Next steps

- [ ] Sign-off on §3 (schema) and §6 (open questions).
- [ ] File Linear issues for Phase 1: (a) schema migration, (b) FRED connector, (c) seed file + indicators, (d) daily script.
- [ ] Add a recurring Linear issue for **release-calendar curation** — each source's cadence needs to be honoured and calendars drift.
- [ ] Once schema lands, retire `playground/macro/funding/` sandbox (close [IMD-35](https://linear.app/imdr/issue/IMD-35)).
