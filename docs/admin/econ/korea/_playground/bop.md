# Korea Balance of Payments — Composition under BPM6

Last updated: 2026-06-03

This doc answers the question: **"What is Korea's capital-account-outflow
time series, and what is it composed of?"** Reference is BOK's published
Balance of Payments statement, source table ECOS `STAT_CODE = 301Y013`
(KOSIS mirror `DT_301Y013`).

## Top-level BoP framework

Korea follows the IMF Balance of Payments Manual, 6th edition (BPM6),
since 2005. BoP statement is divided into four sections:

1. **Current Account** — trade, services, primary income, secondary income
2. **Capital Account** (narrow BPM6) — capital transfers, non-produced/non-financial assets
3. **Financial Account** — five functional categories below
4. **Errors and Omissions**

By identity: Current + Capital + Errors = Financial Account (with signs).

### A note on terminology

Under strict BPM6, the term *"Capital Account"* refers only to capital
transfers (debt forgiveness, migrants' transfers) + acquisition/disposal of
non-produced non-financial assets (trademarks, marketing assets). That's
a tiny residual line (~$0-200 million per month for Korea).

The colloquial trader phrase **"capital account outflow"** usually means
the Assets side of the **Financial Account** — i.e. Korean residents
acquiring foreign financial assets. That's what the rest of this doc
focuses on.

## Composition

<a id="composition"></a>

The Financial Account decomposes into **five BPM6 functional categories**.
Each (except Reserves and Derivatives) is split into Assets and Liabilities.
The Assets side = "outflow" leg.

| # | Category | KOSIS / BPM6 label | ECOS / BOK label | Outflow code | What it is |
|---|---|---|---|---|---|
| ① | Direct Investment | "Direct investment" | "Direct investment" | `BOPF11000000` | Korean residents acquiring ≥10% stakes in foreign enterprises |
| ② | Portfolio Investment | "Portfolio investment" | "Securities Investment" | `BOPF21000000` + `BOPF31xxxxxxx` | Korean residents buying foreign equity + debt securities (without control) |
| ③ | Financial Derivatives & ESOs | "Financial derivatives, Net Assets" | "Derivative Financial Instruments" | `BOPF3xxxxxxx` (net) | Cross-border derivative transactions; recorded net, not split assets/liabilities |
| ④ | Other Investment | "Other investment" | "Other Investments" | `BOPF41000000` | Outward loans, deposits, trade credits, other claims, by counterparty sector |
| ⑤ | Reserve Assets | "Reserve assets" | "Reserve Assets" | `BOPF50000000` | Transactional change in BOK FX reserves (excludes valuation) |

Plus **Errors and Omissions** (`BOPO00000000`) outside the five — the
residual that closes the BoP identity.

**Net Acquisition of Financial Assets** (the colloquial "capital account
outflow" series) = sum of (① + ② + ④ + ⑤) Assets + ③ Net.

## Worked example — Mar 2026

From the live KOSIS download
([`playground/econ/kosis/sample_output/2026/06/03/kosis_DT_301Y013_20260603_0935.xlsx`](../../../../playground/econ/kosis/sample_output/2026/06/03/kosis_DT_301Y013_20260603_0935.xlsx)),
values in USD millions:

| Component | Mar 2026 | Interpretation |
|---|---:|---|
| Current account balance | 37,327.1 | Korea running large CA surplus |
| Capital account balance (narrow) | -16.8 | Trivial — the BPM6 residual line |
| **Financial Account** | **36,991.6** | Net acquisition of foreign claims |
| ① Direct Investment Assets | 8,885.3 | Outward FDI: KR corporates building offshore capacity |
| ② Portfolio Investment Assets | 4,002.7 | NPS / KIC / insurers / asset managers — outward portfolio |
| ③ Financial Derivatives Net | 5,604.1 | Net derivatives — forwards $5,776 + options -$172 |
| ④ Other Investment Assets | -1,563.3 | Net **repatriation** — banks bringing deposits home |
| ⑤ Reserve Assets | -1,848.8 | **BOK drew down reserves** (negative outflow) |
| Errors & Omissions | -318.7 | |

Sum = 8885.3 + 4002.7 + 5604.1 + (-1563.3) + (-1848.8) = **15,080.0** ≈
**$15.1 bn** is the **Mar-2026 capital account outflow headline**.

Decomposition tells the story:
- $8.9bn outward FDI is *structural* (Samsung/Hyundai/SK chip + battery
  capex offshore) — sticky, hard to reverse.
- $4.0bn outward portfolio is *cyclical* (NPS chasing US/EU equities) —
  reversible quickly.
- ④ negative = banks repatriating dollars from offshore deposits.
- ⑤ negative = BOK intervening to defend the won (selling USD reserves).

## Time series sources

### A. FRED — `KORB6*CXCUM` family

Wired into [`playground/econ/fred/seed.yml`](../../../../playground/econ/fred/seed.yml) (Bucket 11b).
Pulled monthly via the standard FRED ingest:

| `imdr_code` | FRED `source_code` | BPM6 line |
|---|---|---|
| `FRED.BOP.FA_ASSETS.KR` | `KORB6FATC01CXCUM` | Financial Account: Net Acquisition of Assets (outflow headline) |
| `FRED.BOP.FA_NET.KR` | `KORB6FATT01CXCUM` | Financial Account Net (Assets − Liabilities) |
| `FRED.BOP.RESERVE_ASSETS.KR` | `KORB6FARA01CXCUM` | ⑤ Reserve Assets |
| `FRED.BOP.OTHER_INV_ASSETS.KR` | `KORB6FAOI02CXCUM` | ④ Other Investment Assets |
| `FRED.BOP.OTHER_INV_LIAB.KR` | `KORB6FAOI03CXCUM` | ④ Other Investment Liabilities |
| `FRED.BOP.OTHER_INV_NET.KR` | `KORB6FAOI01CXCUM` | ④ Other Investment Net |
| `FRED.BOP.CAPITAL_ACCT_BAL.KR` | `KORB6CATT00CXCUM` | Capital Account (narrow BPM6) |
| `FRED.BOP.CAPITAL_TRANSFERS.KR` | `KORB6CATT02CXCUM` | Capital Transfers |

**Caveat**: FRED only mirrors the OECD-relayed subset. Direct Investment
Assets and Portfolio Investment Assets at monthly frequency are **NOT** on
FRED. Annual sums work; monthly decomposition requires KOSIS.

**Time coverage**: 2005-01 → 2025-03 (~12-month lag vs KOSIS).

### B. KOSIS — `DT_301Y013` (full decomposition)

Pull via [`playground/econ/kosis/fetch_bop.py`](../../../../playground/econ/kosis/fetch_bop.py)
(headed Playwright; corp network TLS-resets direct HTTP).

- 284 line items, full BPM6 hierarchy
- Monthly, 1980-01 → present
- **Default UI download: most recent 6 months only**. To get full history,
  expand the KOSIS period selector before clicking Download.

### C. Other useful KOSIS tables

| KOSIS tblId | ECOS code | Statistics |
|---|---|---|
| `DT_301Y013` | `301Y013` | Master Balance of Payments (monthly) |
| `DT_301Y017` | `301Y017` | Current Account (Seasonally Adjusted) |
| `DT_301Y016` | `301Y016` | **Capital Account / Financial Account by Region** — bilateral capital flows (annual 2006-) |
| `DT_311Y001` | `311Y001` | International Investment Position — stock counterpart |
| `DT_311Y005` | `311Y005` | External Assets — stock |
| `DT_732Y001` | `732Y001` | Foreign Exchange Reserves — stock |

## Annual outflow scale (USD bn, FRED `KORB6FATC01CXCUM`)

| Year | FA Assets (outflow) | Note |
|---:|---:|---|
| 2005 | 48.9 | |
| 2007 | 102.9 | Pre-GFC peak |
| 2008 | -33.0 | **GFC flight home — banks repatriating dollar assets** |
| 2013 | 101.4 | |
| 2017 | 120.2 | |
| 2020 | 130.6 | COVID-era reserve build + portfolio |
| **2021** | **186.0** | **Peak outflow — post-COVID surge** |
| 2022 | 96.5 | |
| 2023 | 64.5 | |
| 2024 | 139.1 | |
| 2025 (3 mo) | 25.5 | Through Mar-2025 only |

## Cross-references

- [ecos_api_reference.md](../ecos_api_reference.md) — full STAT_CODE / ITEM_CODE catalog
- Wiring map cluster: [`docs/admin/econ/macro_economy_wiring_map.md`](../../macro_economy_wiring_map.md) §3.3 Capital Account
- Discovery probe metadata: [`playground/econ/bok_ecos/discovery/discover_bop_20260603T082056Z/bok_metadata_captured.md`](../../../../../playground/econ/bok_ecos/discovery/discover_bop_20260603T082056Z/bok_metadata_captured.md)
