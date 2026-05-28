# Bond Yield Integration — Design

- **Status**: IN PROGRESS — step 1 (Bloomberg `dim_vendor` consolidation) shipped as migrations `056`–`058`; bond-specific migrations `060`+ pending
- **Drafted**: 2026-05-25, finalized 2026-05-26
- **Companion exploration**: [`../vendors/citi/exploration/bonds_full.md`](../vendors/citi/exploration/bonds_full.md)
- **Reference desk gap**: [`../development/apac_macro_data_gaps.md`](../development/apac_macro_data_gaps.md)

This doc lays out the IMDR schema for bond-yield observations (sovereign + agency + SSA today; corporate / credit later), the vendor-mapping model, the seed rows derived from the current `BBG_mirror\BONDS\` inventory, and the migration order.

---

## Decision summary

| Choice | Decision | Why |
|---|---|---|
| **Identity dim** | `dbo.dim_bond_curve` | Cross-domain master. Sits with `dim_country`/`dim_currency`/`dim_vendor`. Prevents a duplicate master when credit / corp bonds arrive. |
| **Source map** | `rates.dim_bond_source` | Vendor→curve resolution; rates-flavored axes (tenor, quote_type, spread_anchor, fwd_start, horizon) |
| **Fact** | `rates.fact_bond_yield` | Rates-flavored observations |
| **Sibling fact (contracts)** | `rates.fact_bond_future_basis` | OIS_INVOICESPREAD is contract-anchored, not curve-anchored |
| **Sibling fact (forecasts)** | `rates.fact_yield_forecast` | Has publish_date + target_date — two dates, not one |
| **Sentinel values** | `'SPOT'`/`'NONE'` (not NULL) | UNIQUE works naturally; no SQL Server NULL-in-unique quirk |
| **Tenor representation** | `tenor_code VARCHAR(10)` + `tenor_days INT` | Display + sortable numeric |
| **`source_ticker` in fact** | denormalized for audit | 80B/row overhead worth the debuggability |
| **Storage** | rowstore clustered `(obs_date, bond_curve_id, tenor_code)` PAGE-compressed | Matches `fact_fx_rate`; right at ~6M-row lifetime scale |

---

## Why a separate fact (not extending `rates.fact_observation`)

Already debated. Short version: bonds look like swap curves on the surface but the tenor semantics, quote vocabulary, and growth paths differ. `fact_observation`'s `quote varchar(10)` was sized for swap BID/ASK/MID; bonds need YIELD/PRICE/ASW/CAS/BREAKEVEN/CARRY/DURATION/CONVEXITY. Splitting now while the table is empty avoids a forced migration later.

---

## Why `dim_bond_curve` lives in `dbo`, not `rates`

Bond identity is cross-domain. The same UST 10Y is observed:
- in **rates** as a yield, an ASW spread, a forward yield, duration, convexity
- in **credit** (future) as a benchmark for corporate Z-spreads, OAS computation, asset-swap basis

Placing the identity dim in a domain schema makes it a domain citizen. Worst case it forces a duplicate `credit.dim_credit_curve` later; even the best case (cross-schema FK from `credit.fact_*` to `rates.dim_*`) misnames ownership.

`dbo.*` is already where shared, cross-domain dims live: `dim_country`, `dim_currency`, `dim_vendor`, `dim_frequency`, `dim_scenario`. Bond/curve identity belongs in the same neighborhood. When credit arrives, it FKs to the same `dbo.dim_bond_curve.id` — issuer identity is normalized across both desks.

Source map and fact stay in `rates` because they carry rates-flavored axes (tenor/quote_type/spread_anchor); credit will get its own `credit.dim_credit_source` + `credit.fact_credit_spread` with its own axes (Z-spread, OAS, recovery, etc.), all referencing the same `dbo.dim_bond_curve.id`.

---

## The five axes — what every observation decomposes onto

| Axis | Meaning | Examples | Sentinel |
|---|---|---|---|
| `tenor_code` | Point on the curve | `10Y`, `3M`, `1B`, `25Y` | (always present) |
| `quote_type` | Kind of measurement | `YIELD`, `PRICE`, `SPREAD`, `CARRY`, `DURATION`, `CONVEXITY`, `BREAKEVEN`, `FWD_PREMIUM` | (always present) |
| `spread_anchor` | What a spread references | `BUND`, `UST`, `EUROSTR`, `SOFR`, `COMPOSITE` | `NONE` |
| `fwd_start` | Forward-start period | `5Y` (for 5Y10Y forward), `2Y` | `SPOT` |
| `horizon` | Look-ahead window (carry-like) | `1M`, `3M` | `NONE` |

Every Citi sub-cube and every BBG ticker we've inspected maps onto these 5 axes:

| Source ticker | tenor | quote_type | spread_anchor | fwd_start | horizon |
|---|---|---|---|---|---|
| `USGG10YR Index` (BBG) | `10Y` | `YIELD` | `NONE` | `SPOT` | `NONE` |
| `USGGBE10 Index` (BBG, when added) | `10Y` | `BREAKEVEN` | `NONE` | `SPOT` | `NONE` |
| `RATES.SOV.CMT.USA.10Y.YIELD` | `10Y` | `YIELD` | `NONE` | `SPOT` | `NONE` |
| `RATES.SOV.CMT.IRL.4Y.2Y.EUROSTR_SPRD` | `4Y` | `SPREAD` | `EUROSTR` | `2Y` | `NONE` |
| `RATES.TIPS.USD.10Y.BREAKEVENS` | `10Y` | `BREAKEVEN` | `NONE` | `SPOT` | `NONE` |
| `RATES.TIPS.USD.10Y.CARRY.1M` | `10Y` | `CARRY` | `NONE` | `SPOT` | `1M` |
| `RATES.TIPS.USD.10Y.CARRY_BE.3M` | `10Y` | `CARRY` | `NONE` | `SPOT` | `3M` |
| `RATES.SSA.KFW.SPOT.10Y.DEU_SPRD` | `10Y` | `SPREAD` | `BUND` | `SPOT` | `NONE` |
| `RATES.TSY.OTR.10Y.DURATION` | `10Y` | `DURATION` | `NONE` | `SPOT` | `NONE` |
| `RATES.TSY.OTR.10Y.CONVEXITY` | `10Y` | `CONVEXITY` | `NONE` | `SPOT` | `NONE` |

Adding new vendors / quote types / spread anchors is row-insert, never column-add.

---

## Schema

```sql
-------------------------------------------------------------------------------
-- DIM 1: Curve identity — one row per logical curve
-- Lives in dbo (cross-domain); rates AND credit reference it
-------------------------------------------------------------------------------
CREATE TABLE dbo.dim_bond_curve (
    id                  INT IDENTITY(1,1) NOT NULL,
    country_id          TINYINT       NOT NULL,             -- FK dbo.dim_country
    ccy                 VARCHAR(3)    NOT NULL,
    issuer_class        VARCHAR(20)   NOT NULL,             -- SOVEREIGN | AGENCY | SSA | GSE | CORPORATE | MUNICIPAL
    issuer_code         VARCHAR(30)   NOT NULL,             -- UST | JGB | BUND | OAT | CDB | KFW | FNMA | ...
    yield_type          VARCHAR(20)   NOT NULL,             -- NOMINAL | REAL | BEI | OTR_NOMINAL
    benchmark_kind      VARCHAR(20)   NOT NULL,             -- CMT | OTR | OLD_OTR | GENERIC
    curve_code          VARCHAR(40)   NOT NULL,             -- USD_UST_NOMINAL_CMT
    display_name        VARCHAR(100)  NOT NULL,
    primary_vendor_id   INT           NULL,                 -- FK dim_vendor (preferred read source)
    is_active           BIT           NOT NULL DEFAULT 1,
    notes               VARCHAR(500)  NULL,
    created_at          DATETIMEOFFSET NOT NULL DEFAULT SYSDATETIMEOFFSET(),
    updated_at          DATETIMEOFFSET NOT NULL DEFAULT SYSDATETIMEOFFSET(),
    CONSTRAINT pk_dim_bond_curve PRIMARY KEY (id),
    CONSTRAINT uq_dim_bond_curve_code UNIQUE (curve_code),
    CONSTRAINT fk_dim_bond_curve_country FOREIGN KEY (country_id) REFERENCES dbo.dim_country(id),
    CONSTRAINT fk_dim_bond_curve_primary_vendor FOREIGN KEY (primary_vendor_id) REFERENCES dbo.dim_vendor(id)
);

-------------------------------------------------------------------------------
-- DIM 2: Vendor source resolution — one row per (vendor, source_ticker)
-- Lives in rates (rates-flavored axes); credit gets its own sibling later
-------------------------------------------------------------------------------
CREATE TABLE rates.dim_bond_source (
    id                  INT IDENTITY(1,1) NOT NULL,
    bond_curve_id       INT NOT NULL,                       -- FK dbo.dim_bond_curve
    vendor_id           INT NOT NULL,                       -- FK dbo.dim_vendor
    source_ticker       VARCHAR(80)  NOT NULL,
    tenor_code          VARCHAR(10)  NOT NULL,
    tenor_days          INT          NOT NULL,
    quote_type          VARCHAR(20)  NOT NULL,
    spread_anchor       VARCHAR(20)  NOT NULL DEFAULT 'NONE',
    fwd_start           VARCHAR(10)  NOT NULL DEFAULT 'SPOT',
    horizon             VARCHAR(10)  NOT NULL DEFAULT 'NONE',
    units               VARCHAR(10)  NOT NULL,              -- PCT | BP | YR | YR2 | PRICE
    vendor_field        VARCHAR(30)  NULL,                  -- BBG: px_last | yld_ytm_mid ; Citi: NULL
    is_active           BIT          NOT NULL DEFAULT 1,
    notes               VARCHAR(500) NULL,
    created_at          DATETIMEOFFSET NOT NULL DEFAULT SYSDATETIMEOFFSET(),
    updated_at          DATETIMEOFFSET NOT NULL DEFAULT SYSDATETIMEOFFSET(),
    CONSTRAINT pk_dim_bond_source PRIMARY KEY (id),
    CONSTRAINT uq_dim_bond_source_ticker UNIQUE (vendor_id, source_ticker),
    CONSTRAINT uq_dim_bond_source_axes UNIQUE
        (bond_curve_id, vendor_id, tenor_code, quote_type, spread_anchor, fwd_start, horizon),
    CONSTRAINT fk_dim_bond_source_curve  FOREIGN KEY (bond_curve_id) REFERENCES dbo.dim_bond_curve(id),
    CONSTRAINT fk_dim_bond_source_vendor FOREIGN KEY (vendor_id)     REFERENCES dbo.dim_vendor(id)
);

-------------------------------------------------------------------------------
-- FACT: observations
-------------------------------------------------------------------------------
CREATE TABLE rates.fact_bond_yield (
    id                  BIGINT IDENTITY(1,1) NOT NULL,
    bond_curve_id       INT             NOT NULL,
    vendor_id           INT             NOT NULL,
    frequency_id        TINYINT         NOT NULL,
    obs_date            DATE            NOT NULL,
    obs_ts              DATETIMEOFFSET  NOT NULL,
    tenor_code          VARCHAR(10)     NOT NULL,
    tenor_days          INT             NOT NULL,
    quote_type          VARCHAR(20)     NOT NULL,
    spread_anchor       VARCHAR(20)     NOT NULL DEFAULT 'NONE',
    fwd_start           VARCHAR(10)     NOT NULL DEFAULT 'SPOT',
    horizon             VARCHAR(10)     NOT NULL DEFAULT 'NONE',
    value               FLOAT           NOT NULL,
    units               VARCHAR(10)     NOT NULL,
    source_ticker       VARCHAR(80)     NOT NULL,           -- denormalized audit trail
    created_at          DATETIMEOFFSET  NOT NULL DEFAULT SYSDATETIMEOFFSET(),
    updated_at          DATETIMEOFFSET  NOT NULL DEFAULT SYSDATETIMEOFFSET(),
    CONSTRAINT pk_fact_bond_yield PRIMARY KEY NONCLUSTERED (id),
    CONSTRAINT uq_fact_bond_yield UNIQUE
        (bond_curve_id, vendor_id, obs_date, tenor_code,
         quote_type, spread_anchor, fwd_start, horizon),
    CONSTRAINT fk_fact_bond_yield_curve  FOREIGN KEY (bond_curve_id) REFERENCES dbo.dim_bond_curve(id),
    CONSTRAINT fk_fact_bond_yield_vendor FOREIGN KEY (vendor_id)     REFERENCES dbo.dim_vendor(id),
    CONSTRAINT fk_fact_bond_yield_freq   FOREIGN KEY (frequency_id)  REFERENCES dbo.dim_frequency(id)
);

CREATE CLUSTERED INDEX ci_fact_bond_yield
   ON rates.fact_bond_yield (obs_date, bond_curve_id, tenor_code)
   WITH (DATA_COMPRESSION = PAGE);

CREATE NONCLUSTERED INDEX ix_fact_bond_yield_curve_date
   ON rates.fact_bond_yield (bond_curve_id, obs_date DESC)
   INCLUDE (tenor_code, quote_type, value);
```

### Why these axes don't change

| Pressure | Handled by |
|---|---|
| New vendor (Refinitiv, ICAP, MarketAxess) | Row in `dim_vendor`; rows in `dim_bond_source` |
| New country | `dim_country` row, then curve + source rows |
| New issuer class (CORPORATE, MUNICIPAL, GSE) | `issuer_class` is varchar |
| New quote type (Z_SPREAD, OAS, CDS_BASIS) | `quote_type` is varchar |
| New spread anchor (SARON, AONIA, RFR_X) | `spread_anchor` is varchar |
| Negative yields, weird tenors | values are floats; tenors are strings |
| BBG whitespace quirks (`GTJPYII5YR  govt`) | normalize at ingest; `source_ticker` carries canonical form |
| Intraday upgrade | `obs_ts` is DATETIMEOFFSET; `frequency_id` carries cadence |

### What this schema does NOT try to handle

Each goes in a sibling fact when needed:

| Shape | Sibling | Reason |
|---|---|---|
| Specific bond issues (ISIN, coupon, maturity_date, dirty price) | `rates.fact_bond_instrument_obs` | Different identity granularity; needs ISIN-level dim |
| Bond-future cash basis (`OIS_INVOICESPREAD`) | `rates.fact_bond_future_basis` | Identity is contract+month, not curve+tenor |
| Yield forecasts (`RATES.FORECAST.*`) | `rates.fact_yield_forecast` | Has publish_date + target_date (two dates) |
| Inflation swaps / swaptions | `rates.fact_inflation_swap` | Different instrument class (derivative on CPI) |
| CDS spreads | `credit.fact_cds_spread` | New schema; default-probability semantics |
| Z-spread / OAS on corporate bonds | `credit.fact_credit_spread` | Same `dbo.dim_bond_curve` FK; different observable measurements |

---

## Sibling facts (sketched)

```sql
CREATE TABLE rates.fact_bond_future_basis (
    id              INT IDENTITY(1,1) NOT NULL,
    future_code     VARCHAR(20)    NOT NULL,    -- USD_SOFR, EUR_FGBL, EUR_FBTP, EUR_FOAT, ...
    contract_month  VARCHAR(10)    NOT NULL,    -- FRONTMONTH | BACKMONTH
    vendor_id       INT            NOT NULL,
    obs_date        DATE           NOT NULL,
    invoice_spread  FLOAT          NOT NULL,
    units           VARCHAR(10)    NOT NULL,    -- BP
    source_ticker   VARCHAR(80)    NOT NULL,
    created_at, updated_at,
    CONSTRAINT pk_fact_bond_future_basis PRIMARY KEY (id),
    CONSTRAINT uq_fact_bond_future_basis UNIQUE (future_code, contract_month, vendor_id, obs_date)
);

CREATE TABLE rates.fact_yield_forecast (
    id              INT IDENTITY(1,1) NOT NULL,
    bond_curve_id   INT            NULL,         -- nullable: forecasts of Fed funds don't bind to a bond curve
    forecast_tag    VARCHAR(60)    NOT NULL,     -- FED_FUNDS_FCST | UST_10Y_YLD_FCST | ...
    vendor_id       INT            NOT NULL,
    publish_date    DATE           NOT NULL,     -- when the forecast was issued
    target_date     DATE           NOT NULL,     -- the date the forecast is FOR
    horizon         VARCHAR(10)    NOT NULL,     -- QTR | ANNUAL
    value           FLOAT          NOT NULL,
    units           VARCHAR(10)    NOT NULL,
    source_ticker   VARCHAR(80)    NOT NULL,
    created_at, updated_at,
    CONSTRAINT pk_fact_yield_forecast PRIMARY KEY (id),
    CONSTRAINT uq_fact_yield_forecast UNIQUE (forecast_tag, vendor_id, publish_date, target_date)
);
```

---

## Seed list — `dbo.dim_bond_curve` for the BBG_mirror inventory

Current `Z:\...\BBG_mirror\BONDS\` contains 8 CSVs covering 7 currencies. Each maps to exactly one `dim_bond_curve` row.

| curve_code | country | ccy | issuer_class | issuer_code | yield_type | benchmark_kind | display_name | notes |
|---|---|---|---|---|---|---|---|---|
| `USD_UST_NOMINAL_CMT` | USA | USD | SOVEREIGN | UST | NOMINAL | CMT | US Treasury Nominal CMT | From `USD_GOVT.csv` |
| `JPY_JGB_NOMINAL_GENERIC` | JPN | JPY | SOVEREIGN | JGB | NOMINAL | GENERIC | JGB Generic Yields | Uses `GTJPY*` generic series, not on-the-run `GJGB*` |
| `JPY_JGBI_REAL_GENERIC` | JPN | JPY | SOVEREIGN | JGBI | REAL | GENERIC | JGB Inflation-Linked Real Yields | From `JPY_LINKER.csv` |
| `CNY_CDB_NOMINAL_GENERIC` | CHN | CNY | AGENCY | CDB | NOMINAL | GENERIC | China Development Bank Yields | **NOT Chinese government** — CDB is quasi-sovereign agency |
| `IDR_IDGB_NOMINAL_GENERIC` | IDN | IDR | SOVEREIGN | IDGB | NOMINAL | GENERIC | Indonesia Govt Generic Yields | Uses `GIDN*` not user's `GTIDR*` |
| `KRW_KTB_NOMINAL_OTR` | KOR | KRW | SOVEREIGN | KTB | NOMINAL | OTR | Korea Treasury Bond On-The-Run | Uses `GVSK*` on-the-run, not generic |
| `MYR_MGS_NOMINAL_GENERIC` | MYS | MYR | SOVEREIGN | MGS | NOMINAL | GENERIC | Malaysia Govt Securities | Uses `MAGY*` not user's `GTMYR*` |
| `AUD_ACGBI_REAL_GENERIC` | AUS | AUD | SOVEREIGN | ACGBI | REAL | GENERIC | Australia Inflation-Linked Real Yields | From `AUD_LINKER.csv`; **AUD nominal NOT in mirror** |

**8 curves seeded** from the current mirror.

### Curves PENDING (active=0 placeholders for mirror gaps)

| curve_code | Reason | Required upstream change |
|---|---|---|
| `USD_UST_BEI_CMT` | No USD breakeven series in mirror | Add `USGGBE10` etc. to mirror |
| `USD_UST_REAL_CMT` | No US TIPS in mirror | Add TIPS file (`GTII*` or `USGGT*`) |
| `GBP_GILT_NOMINAL_CMT` | No UK folder in mirror | Add `GBP/GOVT/GBP_GOVT.csv` |
| `GBP_GILT_BEI_CMT` | No UK BEI | Add `UKGGBE*` |
| `EUR_BUND_NOMINAL_CMT` | No DE folder | Add `EUR/GOVT/DE_*` or split per country |
| `EUR_BUND_BEI_CMT` | No DE BEI | Add `DEGGBE*` |
| `EUR_OAT_NOMINAL_CMT` | No FR folder | Add FR file |
| `EUR_OAT_BEI_CMT` | No FR BEI | Add `FRGGBE*` |
| `JPY_JGB_BEI_CMT` | No Japan BEI | Add `JYGGBE*` |
| `AUD_ACGB_NOMINAL_CMT` | No AUD GOVT in mirror — only LINKER | Add `AUD/GOVT/AUD_GOVT.csv` |
| `AUD_ACGB_BEI_CMT` | No AUD BEI | Add `ADGGBE*` |
| `SGD_SIGB_NOMINAL_CMT` | No SG folder in mirror | Add SG file |
| `INR_IGB_NOMINAL_CMT` | No IN folder | Add IN file |
| `THB_THAIGB_NOMINAL_CMT` | No TH folder | Add TH file |
| `CNY_CGB_NOMINAL_CMT` | Mirror has CDB only (agency, not sovereign) | Add `GTCNY*` or equivalent for actual CGB |

These get seeded with `is_active=0` so the FK structure is ready; rows flip to `is_active=1` and the source map gets populated when upstream lands the data.

---

## Seed list — `rates.dim_bond_source` for BBG_mirror (54 active rows)

One row per CSV column (= one row per BBG ticker). All quote_type='YIELD' for GOVT files; the `JPY_LINKER.csv` and `AUD_LINKER.csv` also carry yield (real yield), not breakeven — note the curve they bind to is `*_REAL_*`.

`vendor_field` = `px_last` for GOVT, `yld_ytm_mid` per the R refresh script (line 192: `if(iden == "USD_LINKER"){ COL_NAME = "yld_ytm_mid" } else { COL_NAME = "px_last" }`).

### USD UST Nominal (10 rows) — `USD_UST_NOMINAL_CMT`

| source_ticker | tenor_code | tenor_days | quote_type | units | vendor_field |
|---|---|---|---|---|---|
| `USGG1M Index` | 1M | 30 | YIELD | PCT | px_last |
| `USGG6M Index` | 6M | 180 | YIELD | PCT | px_last |
| `USGG12M Index` | 1Y | 365 | YIELD | PCT | px_last |
| `USGG2YR Index` | 2Y | 730 | YIELD | PCT | px_last |
| `USGG3YR Index` | 3Y | 1095 | YIELD | PCT | px_last |
| `USGG5YR Index` | 5Y | 1825 | YIELD | PCT | px_last |
| `USGG7YR Index` | 7Y | 2555 | YIELD | PCT | px_last |
| `USGG10YR Index` | 10Y | 3650 | YIELD | PCT | px_last |
| `USGG20YR Index` | 20Y | 7300 | YIELD | PCT | px_last |
| `USGG30YR Index` | 30Y | 10950 | YIELD | PCT | px_last |

### JPY JGB Nominal (11 rows) — `JPY_JGB_NOMINAL_GENERIC`

| source_ticker | tenor_code | tenor_days |
|---|---|---|
| `GTJPY1Y govt` | 1Y | 365 |
| `GTJPY2Y govt` | 2Y | 730 |
| `GTJPY3Y govt` | 3Y | 1095 |
| `GTJPY4Y govt` | 4Y | 1460 |
| `GTJPY5Y govt` | 5Y | 1825 |
| `GTJPY6Y govt` | 6Y | 2190 |
| `GTJPY7Y govt` | 7Y | 2555 |
| `GTJPY10Y govt` | 10Y | 3650 |
| `GTJPY15Y govt` | 15Y | 5475 |
| `GTJPY20Y govt` | 20Y | 7300 |
| `GTJPY30Y govt` | 30Y | 10950 |

All `quote_type=YIELD`, `units=PCT`, `vendor_field=px_last`.

### JPY JGBI Real (6 rows) — `JPY_JGBI_REAL_GENERIC`

`source_ticker` values have **double internal whitespace** (`GTJPYII5YR  govt`). The ingest layer must preserve them byte-for-byte to match the CSV header; a `normalize_bbg_ticker()` helper that collapses whitespace would break the lookup. Store canonical (double-space) form in `dim_bond_source.source_ticker`.

| source_ticker | tenor_code | tenor_days |
|---|---|---|
| `GTJPYII5YR  govt` | 5Y | 1825 |
| `GTJPYII6YR  govt` | 6Y | 2190 |
| `GTJPYII7YR  govt` | 7Y | 2555 |
| `GTJPYII8YR  govt` | 8Y | 2920 |
| `GTJPYII9YR  govt` | 9Y | 3285 |
| `GTJPYII10YR  govt` | 10Y | 3650 |

All `quote_type=YIELD`, `units=PCT`, `vendor_field=px_last`.

### CNY CDB Agency Nominal (3 rows) — `CNY_CDB_NOMINAL_GENERIC`

| source_ticker | tenor_code | tenor_days |
|---|---|---|
| `GCDB1YR INDEX` | 1Y | 365 |
| `GCDB5YR INDEX` | 5Y | 1825 |
| `GCDB10YR INDEX` | 10Y | 3650 |

All `quote_type=YIELD`, `units=PCT`, `vendor_field=px_last`.

### IDR IDGB Nominal (7 rows) — `IDR_IDGB_NOMINAL_GENERIC`

| source_ticker | tenor_code | tenor_days |
|---|---|---|
| `GIDN1YR INDEX` | 1Y | 365 |
| `GIDN3YR INDEX` | 3Y | 1095 |
| `GIDN5YR INDEX` | 5Y | 1825 |
| `GIDN7YR INDEX` | 7Y | 2555 |
| `GIDN10YR INDEX` | 10Y | 3650 |
| `GIDN20YR INDEX` | 20Y | 7300 |
| `GIDN30YR Index` | 30Y | 10950 |

Note last row uses `Index` (mixed case) instead of `INDEX`. Match exact-string from the CSV header. All `quote_type=YIELD`, `units=PCT`, `vendor_field=px_last`.

### KRW KTB OTR Nominal (8 rows) — `KRW_KTB_NOMINAL_OTR`

| source_ticker | tenor_code | tenor_days |
|---|---|---|
| `GVSK3MON Index` | 3M | 90 |
| `GVSK6MON Index` | 6M | 180 |
| `GVSK1YR Index` | 1Y | 365 |
| `GVSK2YR Index` | 2Y | 730 |
| `GVSK3YR Index` | 3Y | 1095 |
| `GVSK5YR Index` | 5Y | 1825 |
| `GVSK10YR Index` | 10Y | 3650 |
| `GVSK20YR Index` | 20Y | 7300 |

All `quote_type=YIELD`, `units=PCT`, `vendor_field=px_last`.

### MYR MGS Nominal (5 rows) — `MYR_MGS_NOMINAL_GENERIC`

| source_ticker | tenor_code | tenor_days |
|---|---|---|
| `MAGY3YR INDEX` | 3Y | 1095 |
| `MAGY5YR INDEX` | 5Y | 1825 |
| `MAGY7YR INDEX` | 7Y | 2555 |
| `MAGY10YR INDEX` | 10Y | 3650 |
| `MAGY20YR INDEX` | 20Y | 7300 |

All `quote_type=YIELD`, `units=PCT`, `vendor_field=px_last`.

### AUD ACGBI Real (4 rows) — `AUD_ACGBI_REAL_GENERIC`

| source_ticker | tenor_code | tenor_days |
|---|---|---|
| `CTAUDII5Y Govt` | 5Y | 1825 |
| `CTAUDII10Y Govt` | 10Y | 3650 |
| `CTAUDII15Y Govt` | 15Y | 5475 |
| `CTAUDII20Y Govt` | 20Y | 7300 |

All `quote_type=YIELD`, `units=PCT`, `vendor_field=px_last`. (Note: R code uses `px_last` for all linkers except `USD_LINKER` which switches to `yld_ytm_mid`. AUD linker uses `px_last`.)

### Total: **8 curves, 54 source rows** for BBG_mirror coverage today

---

## Migration sequence

Each step is small and reversible. Steps 1–3 are universal blockers; steps 4+ are bond-specific.

Step 1 is **DONE** — the Bloomberg `dim_vendor` consolidation shipped across `056`–`058` (056 repointed calendar FKs and started the rename; 057 attempted the fact-table FK repoint; 058 resolved the id=5 duplicate-key collisions and finished the rename). `dbo.dim_vendor` now holds a single Bloomberg row: `id=4, vendor_code='BBG'`. Migration `059` is already taken (`059_seed_bnp_dim_vendor.sql`), so the bond-specific work starts at `060`.

1. ~~**`NNN_dim_vendor_consolidate_bloomberg.sql`**~~ — **DONE** as `056`–`058`. Single Bloomberg row `id=4, vendor_code='BBG'`.
2. **`060_create_dim_bond_curve.sql`** — DDL for `dbo.dim_bond_curve`.
3. **`061_seed_dim_bond_curve_bbg_mirror.sql`** — 8 active + 15 inactive (pending) rows per the lists above.
4. **`062_create_dim_bond_source.sql`** — DDL for `rates.dim_bond_source`.
5. **`063_seed_dim_bond_source_bbg_mirror.sql`** — 54 rows per the tables above.
6. **`064_create_fact_bond_yield.sql`** — DDL + clustered index + NCI.
7. **`065_backfill_fact_bond_yield_bbg_mirror.sql`** — load history from the 8 mirror CSVs (~210K rows, single transaction; rebuild stats after).
8. **`066_create_fact_bond_future_basis.sql`** + Citi seed/ingest for `RATES.OIS_INVOICESPREAD.*` (44 tags).
9. **`067_create_fact_yield_forecast.sql`** + Citi seed/ingest for `RATES.FORECAST.*` (12 tags).
10. **`068_seed_dim_bond_curve_citi_dm_tier2.sql`** — add Citi DM extensions (28 sovereign curves: CAN, CHE, ITA, ESP, NLD, BEL, AUT, IRL, FIN, GRC, PRT, NOR, SWE, DNK, NZL, ISR, LUX, PLN, CZE, HUN, ROU, SVK, SVN, CYP, TUR, ZAF).
11. **`069_seed_dim_bond_curve_ssa.sql`** — ~35 SSA issuers from Citi.

After step 7, the user's APAC bonds dashboard works end-to-end for the 7 currencies the mirror covers (US, JP, CN-CDB, ID, KR, MY + AUD-linker only). The remaining 6 countries from the user's matrix (UK, DE, FR, SG, IN, TH) wait on upstream mirror additions.

---

## Pipelines

### `BBGMirrorBondsFeed` (new VendorFeed)

- Class: `src/imdr/vendors/feeds/bbg_mirror_bonds.py`
- Reads: `Z:\...\BBG_mirror\BONDS\{CCY}\{GOVT|LINKER}\*.csv` (read-only — never moves or writes back)
- Parses: 3-row header (Identifier=BBG ticker, Ticker=internal alias, Maturity=decimal years), then DD/MM/YYYY data rows in descending date order
- For each (date, ticker, value) triple: lookup `rates.dim_bond_source` by `(vendor=bloomberg, source_ticker=ticker)`; reject if no match (loud, not silent)
- Upsert into `rates.fact_bond_yield`
- Whitespace handling: preserve exact source_ticker form (including `GTJPYII5YR  govt` double-space)
- Idempotent on `(bond_curve_id, vendor_id, obs_date, tenor_code, quote_type, spread_anchor, fwd_start, horizon)`

### `BondsCitiPipeline` (new pipeline, existing framework)

- Pipeline name: `rates.bonds_citi_live`
- Tag list generated FROM `dim_bond_source` rows where `vendor_id=citi_velocity AND is_active=1` — no hard-coded tickers
- Scheduled in `scripts/imdr_daily.py`
- Estimated daily tags after full DM rollout: 32 countries × ~10 tenors × 1–4 quotes ≈ 500–1500 tags/day (well within quota)

### Daily ordering

```
imdr_daily.py:
   ...
   rates.citi_live              (existing swap curves)
   rates.bonds_citi_live        (NEW)
   rates.bonds_bbg_mirror       (NEW; runs after R completes ~06:00 HK)
   ...
```

---

## Quality checks

Per the existing `get_health_checks()` pattern:

| Check | Threshold | Catches |
|---|---|---|
| `RowCountCheck` | tier-1 curves × tenor grid (per vendor) | Partial fetches / missing files |
| `RangeCheck` | NOMINAL ∈ [-2%, 30%]; REAL ∈ [-5%, 15%]; BEI ∈ [-2%, 10%]; SPREAD ∈ [-500, 500] bp | Sign/scale errors |
| `NullCheck` | `value IS NOT NULL` | Empty cells (e.g. early-history NaN — handled by skipping at ingest, not erroring) |
| `StaleCheck` | per curve, gap ≤ 2 weekdays in target market timezone | Silent vendor staleness |
| `CurveSpreadCheck` | If both NOMINAL & REAL exist for date, BEI ≈ NOMINAL − REAL ± 50bp | Cross-validates 3 yield_types per country |
| `UnitConsistencyCheck` | Per `dim_bond_source.units` row, fact values must respect unit ranges | Catches PCT-vs-BP confusion (BREAKEVENS in bp can look like 200% if mis-unit'd) |

---

## Backfill

Single batch from BBG_mirror, ~210K rows:

```sql
ALTER INDEX ix_fact_bond_yield_curve_date ON rates.fact_bond_yield DISABLE;
BULK INSERT … FROM all 8 mirror CSVs …  (one transaction)
ALTER INDEX ix_fact_bond_yield_curve_date ON rates.fact_bond_yield REBUILD;
UPDATE STATISTICS rates.fact_bond_yield WITH FULLSCAN;
```

Per-file history depth (from the mirror inventory):

| File | First date | Rows in CSV |
|---|---|---|
| USD_GOVT | 2007-01-01 | 5,061 |
| KRW_GOVT | 2007-01-01 | 5,047 |
| IDR_GOVT | 2007-06-05 | 4,762 |
| AUD_LINKER | 2010-10-01 | 4,075 |
| MYR_GOVT | 2011-12-13 | 3,756 |
| JPY_GOVT | 2014-05-15 | 3,138 |
| JPY_LINKER | 2016-10-14 | 2,459 |
| CNY_GOVT | 2017-02-21 | 2,235 |

NaN cells (5,588 in USD_GOVT, 1,270 in AUD_LINKER) are early-history tenors not yet published — skip at ingest, don't insert NULL rows.

---

## Open questions (still need a call before SQL)

1. **APAC EM ticker convention**: user's matrix wanted generic `GT{CCY}10Y` series; BBG_mirror provides country-specific tickers (`GVSK`, `GIDN`, `GTJPY`, `GCDB`, `MAGY`). The seed list above uses what's IN the mirror. Decision: live with the mirror's choices, or request upstream to add the user's `GT*` series alongside (which would be a parallel curve_code in `dim_bond_curve`, since they reference different bonds).
2. ~~**Bloomberg vendor dedup** (`BBG` vs `bloomberg` in `dim_vendor`): pick one, repoint FKs. Migration step 1.~~ **RESOLVED** — consolidated to `id=4, vendor_code='BBG'` via migrations `056`–`058`.
3. **Mirror gaps**: 15 pending `dim_bond_curve` rows are inactive placeholders. Either pursue upstream mirror additions (UK, DE, FR, SG, IN, TH, AUD GOVT, USD LINKER, BEI series for all 6 DM) or accept that those rows of the user's matrix are uncovered.
4. **Citi as a parallel source for DM**: when do we start populating `dim_bond_source` rows with `vendor_id=citi_velocity` for the same DM curves? After BBG ingest is stable, or in parallel.

---

## Cross-references

- [`../vendors/citi/exploration/bonds_full.md`](../vendors/citi/exploration/bonds_full.md) — Citi bonds catalog deep dive (the source of the 5-axis vocabulary)
- [`../vendors/citi/exploration/rates_full.md`](../vendors/citi/exploration/rates_full.md) — broader Citi rates catalog
- [`../vendors/citi/exploration/rates_sov_cmt.md`](../vendors/citi/exploration/rates_sov_cmt.md) — older SOV_CMT note (canonical path is `RATES.SOV.CMT.*`, not `RATES.SOV_CMT.*`)
- [`../development/apac_macro_data_gaps.md`](../development/apac_macro_data_gaps.md) — desk-needs framing
- [`rates_schema.md`](rates_schema.md) — existing rates DB schema reference
- [`rates_bbg.md`](rates_bbg.md) — Bloomberg rates pipeline operations (IRS/OIS pattern reference)
- `Z:\Business\Research\Dashboard\DataSources\BBG_mirror\BONDS\` — current upstream files (read-only)
- `data/cache/rates/bonds_deep.json` — Citi probe cache; DO NOT re-run
