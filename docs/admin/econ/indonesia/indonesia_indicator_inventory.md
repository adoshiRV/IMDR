# Indonesia (ID) — Econ Indicator Inventory

Last updated: 2026-06-09

Tracker forked from [`../country_econ_blueprint.md`](../country_econ_blueprint.md) §1-4 per the [onboarding playbook](../onboarding_new_country.md#step-1--fork-the-blueprint-into-a-country-tracker).

**Today (2026-06-09 post-Phase G):** **250 indicators × 26,757 observations live in `econ.fact_indicator`** across 3 vendors (BPS 82 + BI 162 + BIS 6); migrations 081-084 applied. **All 16 wiring-map cells covered; 13 of 16 are full ✅.** Orchestrator wired into `scripts/imdr_monthly.py:PIPELINES` 2026-06-09 — Phase G complete.

## Production fetchers (2026-06-09)

25 fetchers under `scripts/econ/` cover all 250 indicators. Orchestrator:
`scripts/econ/id/id_monthly.py` — wired into `scripts/imdr_monthly.py:PIPELINES` 2026-06-09.
See [indonesia_prod_pipeline.md](indonesia_prod_pipeline.md).

| Fetcher | Indicators (approx) |
|---|---:|
| `scripts.econ.bis.bis_indonesia` | 6 |
| `scripts.econ.bps.bps_cpi` | 4 |
| `scripts.econ.bps.bps_cpi_groups` | 11 |
| `scripts.econ.bps.bps_gdp` | 7 |
| `scripts.econ.bps.bps_gdp_components` | 24 |
| `scripts.econ.bps.bps_ip` | 4 |
| `scripts.econ.bps.bps_labour` | 3 |
| `scripts.econ.bps.bps_ppi` | 8 |
| `scripts.econ.bps.bps_prices_current` | 8 |
| `scripts.econ.bps.bps_sakernas` | 12 |
| `scripts.econ.bps.bps_trade` | 6 |
| `scripts.econ.bi.bi_bank_bs` | 8 |
| `scripts.econ.bi.bi_bank_credit` | 15 |
| `scripts.econ.bi.bi_bank_rates` | 13 |
| `scripts.econ.bi.bi_bop` | 5 |
| `scripts.econ.bi.bi_business_survey` | 18 |
| `scripts.econ.bi.bi_consumer_survey` | 9 |
| `scripts.econ.bi.bi_fiscal` | 6 |
| `scripts.econ.bi.bi_fx_reserves` | 5 |
| `scripts.econ.bi.bi_monetary_base` | 5 |
| `scripts.econ.bi.bi_money_supply` | 10 |
| `scripts.econ.bi.bi_retail_sales` | 9 |
| `scripts.econ.bi.bi_sbn` | 5 |
| `scripts.econ.bi.bi_skdu_macro` | 36 |
| `scripts.econ.bi.bi_sulni` | 8 |
| **Total** | **250** |

---

## Status markers

| Marker | Meaning |
|---|---|
| ✅ | At least one indicator on disk + production fetcher registered |
| ⚠ | Partial — headline present, sub-bullets missing |
| ❓ | Unknown source — needs catalogue browse |
| ❌ | Not available (vendor-gated, expected gap) |

## 4×4 Tracker

| Cell | Status | Headline indicator (vendor) | Sub-bullets covered | Gap / Tier |
|---|:---:|---|:---:|---|
| 1.1 Private Demand    | ✅ | BI.SENTIMENT.CCI + BI.RETAIL_SALES.TOTAL + SKDU TOTAL | 36/13 | BI Consumer Survey IKK (9 sub-indices, M 2012→) + Retail Sales INDEKS TOTAL (9 categories, M 2012→) + SKDU Business Activity (18 sectoral, Q 2022→) |
| 1.2 Fiscal Demand     | ✅ | BI.FISCAL.REVENUE / EXPEND / BALANCE | 6/11 | BI SEKI IV.1-3 annual realisasi (2008→2024); MoF APBN portal PDF-only |
| 1.3 External Demand   | ✅ | BPS.TRADE.EXPORT / IMPORT.TOTAL.USD.ID | 6/13 | BPS customs trade (2009→2026 monthly + Migas/Non-Migas annual) |
| 1.4 Macro Core        | ✅ | BPS.GDP.GDP.YOY.ID + Sakernas + IP | 9/22 | BPS GDP (7) + Sakernas labour (12) + Industrial Production (4) |
| 2.1 Input Costs       | ✅ | BPS.IMPORT_PRICE.YOY.ID | 2/7 | BPS Import Price Index 2023=100 (Q); import-price decomp pending |
| 2.2 Producer Prices   | ✅ | BPS.PPI.TOTAL_2016.YOY + WPI 2023 | 4/7 | BPS PPI 2010+2016 base (Q) + WPI 2000+2023 base (M) |
| 2.3 Domestic Costs    | ✅ | BPS wages + BI.CAP_UTIL.TOTAL + BI.INFL_EXP.TOTAL + BI.SELL_PRICES.TOTAL | 42/12 | BPS Sakernas wages + SKDU T2 capacity utilisation (18 sectors) + T5 selling prices (18 sectors) + T6 inflation expectations (18 sectors) |
| 2.4 CPI Pressure      | ✅ | BPS.CPI.HEADLINE.MOM + 11-group breakdown | 15/14 | BPS CPI MoM continuous 1979→ + 11-group YoY 2024→ |
| 3.1 Terms of Trade    | ⚠ | BPS.EXPORT_PRICE / IMPORT_PRICE.LEVEL (NBToT derivable in analytics) | 2/5 | BPS Export + Import Price indices 2023=100 (Q); NBToT = Pₓ/Pₘ + Income ToT derived in analytics (no separate fetcher needed) |
| 3.2 Current Account   | ✅ | BI.BOP.CA.TOTAL.USD.ID | 5/11 | BI BoP V.1 quarterly (CA total + 4 components) |
| 3.3 Capital Account   | ✅ | BI.BOP.FA.TOTAL + SULNI external debt | 13/17 | BI BoP FA (5) + SULNI external debt (8 quarterly) |
| 3.4 FX / REER         | ✅ | BIS.NEER.BROAD + REER + BI.RESERVES.* | 8/11 | BIS broad NEER+REER (1994→) + BI FX reserves stock by component |
| 4.1 Demand Trans      | ✅ | BI.BANK_CREDIT.*.TOTAL/BUSINESS/CONSUMER | 15/14 | BI Bank Credit I.4 — 5 bank groups × total/business/consumer monthly 2016→ |
| 4.2 Balance Sheets    | ✅ | BI.BANK_BS.* + BIS.DSR + BIS.CREDIT_TO_GDP | 11/17 | BI commercial bank BS (8) + BIS DSR PNFS + Credit-to-GDP ratio + gap |
| 4.3 Fin Conditions    | ✅ | BI.RATES.INDONIA + lending + deposit + BIS policy | 13/16 | BIS policy rate + BI Deposit/Lending Facility + PUAB overnight + INDONIA + 30d/90d compounded + Bank Umum lending (3 loan types) + deposit (3 tenors); IDR bond yields are rates-domain |
| 4.4 Policy Reaction   | ✅ | BI.M2 + BI.M0 + BI.RESERVES + SBN | 13/18 | BI M1/M2/M0 (10) + reserves + SBN; BIS policy rate cross-ref |

**Score (2026-06-09 post-Phase D6)**: **All 16 cells covered; 13 of 16 are full ✅.** **250 indicators × 26,757 observations** in `econ.fact_indicator`. Three cells remain ⚠ partial: 2.1 Input Costs (BPS import prices headline only — 2/7 sub-bullets), 3.1 Terms of Trade (BPS export+import price indices in DB; NBToT + Income ToT derivable in analytics — 2/5), 3.4 FX/REER (NEER+REER+reserves total; reserves composition + intervention proxy still derivable — 8/11). Production wiring (Phase G) and OJK NPL deep-dive are the only remaining deliverables.

## Headline-first build order (per playbook §3)

1. **CPI** (2.4) — BPS monthly; headline pair anchor.
2. **GDP** (1.4) — BPS quarterly; second anchor.
3. **Policy rate + key bond yields** (4.4 + 4.3) — BI 7-Day RR Rate + IBPA INDOGB curve.
4. **BoP** (3.2 + 3.3) — BI SEKI XLSX, quarterly. **First non-API ingest** — sets the SEKI-scraper pattern.
5. **Labour** (1.4 labour leg) — BPS Sakernas semi-annual.
6. **PPI** (2.2) + **Import/Export prices** (2.1) — BPS pipeline-inflation pair.
7. **Trade indices** (1.3) + **Terms of Trade** (3.1) — BPS export/import indices.
8. **Fiscal** (1.2) — MoF APBN annual.
9. **Retail sales** (1.1) — BPS monthly retail sales survey (penjualan eceran).
10. **Sentiment surveys** (CCI, CTI) — BI consumer + business surveys, monthly XLSX.
11. **Lending standards** (4.1) — BI Banking Survey (SBP), quarterly.
12. **Balance sheets** (4.2) — BI SEKI HH credit + OJK NPL.
13. **Monetary aggregates** (4.4) — BI SEKI M1/M2 monthly.
14. **FX reserves + REER** (3.4) — BI SEKI; REER from BIS where available.
15. **Industrial Production + Cap Util** (1.4/2.3) — BPS IBS quarterly.
16. **Macropru event log** (4.4) — BI Board of Governors news releases.

## Expected ❌ cells

Acknowledged gaps per playbook §3:

| Cell | Reason | Workaround |
|---|---|---|
| 1.4 Macro Core — PMI | S&P Global paid; not on FRED for ID | Use BI Business Survey (SK) as PMI-equivalent |
| 2.3 Domestic Costs — monthly wages | BPS Sakernas is semi-annual not monthly | Sakernas Aug + Feb as best available; capacity-util as cycle proxy |
| 3.4 FX/REER — REER | BIS broad REER does carry IDR — should be available | Confirm during Phase B FRED-mirror probe |
| 4.1 Demand Trans — lending standards survey | BI Banking Survey **does** publish a SLOOS-equivalent (quarterly) | Usable; Tier 1 |
| 4.2 Balance Sheets — corporate ratios | Sparse for EM | BIS credit-to-GDP gap (BIS table F1.1) as headline |
| 4.3 Fin Conditions — corporate spreads | No published IDR IG/HY OAS | Sovereign CDS 5Y as country-credit proxy |

## Cross-refs

- [`../country_econ_blueprint.md`](../country_econ_blueprint.md) — the *what* (catalogue of every indicator).
- [`id_coverage_plan.md`](id_coverage_plan.md) — cell → BPS/BI table-ID mapping (filled as discovery happens).
- [`id_indicator_targets.md`](id_indicator_targets.md) — concrete `dim_indicator` shopping list.
- [`../macro_economy_wiring_map.md#717-indonesia-id`](../macro_economy_wiring_map.md#717-indonesia-id) — ID grid in the master tracker.
- [`../korea/korea_indicator_inventory.md`](../korea/korea_indicator_inventory.md) — Korea worked reference (172 indicators).
