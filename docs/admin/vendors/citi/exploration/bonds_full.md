# Citi Velocity — Sovereign Bonds & Adjacent Fixed Income: Full Exploration

- **Probed**: 2026-05-25
- **Probe script**: `playground/bonds/probe_citi_bonds_deep.py`
- **Follow-up probe**: `playground/bonds/probe_followups.py`
- **Cache**: `data/cache/rates/bonds_deep.json` (123 KB)
- **DO NOT re-run** — results documented below

This snapshot supersedes the "partial / not probed" entries for SOV, MBS, AGENCY_INVENTORY, MIDCURVES, SPREAD_OPTIONS, FRA, FRA_OIS, OIS_INVOICESPREAD, INVOICESPREAD, POS_MON, and FORECAST in [`rates_full.md`](rates_full.md). Some of those were stale; see corrections below.

---

## Headline

**Citi Velocity is a DM-only sovereign bond source.** 34 developed-market countries are covered comprehensively (yields, spreads, asset-swaps, forwards). **Zero APAC EM bond coverage**: no CN, KR, SG, IN, ID, TH, MY, HK, TW, PH, VN sovereign data exists anywhere in `RATES.*`.

The only APAC EM rate data on Citi is `RATES.FRA.KRW` (money-market FRAs, not bonds).

For an IMDR sovereign-bond pipeline, this means:
- **DM (US/UK/JP/DE/FR/AU + 28 more)**: Citi can serve as primary or fallback source, with substantially richer metrics than BBG CSV.
- **APAC EM (CN/KR/SG/IN/ID/TH/MY)**: BBG_mirror is the only source. No second-vendor recovery exists.

---

## Methodology

The probe used three Citi endpoints:

1. **`fetch_taglisting(prefix)`** — flat list of all tags under a prefix. Free of quota cost.
2. **`fetch_tagbrowsing(prefix)`** — tree structure one level at a time. Free of quota cost.
3. **`fetch_historical(tags, 30d)`** — sample 5 representative tags per branch to confirm data flow. Counts against the 100K/24h tag quota — ~95 tag-fetches used.

Schema decomposition: tags are dotted paths. Splitting on `.` and binning per-position yields the dimensional structure (e.g., position 1 = country, position 2 = tenor, etc.). The `analyze_schema()` helper in the probe script produces `positions: {0: {unique, top}, 1: {...}, ...}` for each branch.

For dead-looking branches (FORECAST in 30d window), a follow-up probe used a 365d window to distinguish "no data" from "infrequent publications."

---

## Branch-by-branch findings

### Confirmed working (14 branches)

| Branch | Tags | Shape | What it gives you |
|---|---|---|---|
| `RATES.SOV` | 11,773 | 34 DM countries × yields/spreads/ASW/forwards | The main sov-bond cube |
| `RATES.TSY` | 299 | US-only: OTR/CMT/BFLY/CURVES/OLD_1 | US Treasury constant-maturity + benchmark analytics |
| `RATES.T_BILL` | 12 | US-only: OTR × {1M, 3M, 6M, 1Y} | T-Bill yields, prices, spread-to-SOFR |
| `RATES.TIPS` | 26 | USD-only × {5Y, 10Y, 30Y} × 7 metrics | Real yield, breakeven, ASW-SOFR, carry — the only direct BEI source |
| `RATES.SSA` | 708 | 35 European supranational issuers | Spreads vs Bund, vs UST, vs composite — credit-stack reference |
| `RATES.SSA_CS` | 100 | 22 issuers × EUR/USD basis | Cross-currency spreads (UST_SPRD, COMP_SPRD) |
| `RATES.MBS` | 11,321 | 13 product types × 4 GSE issuers × coupon stack | US mortgage-backed (out-of-scope for sov bonds; possible future `credit.*`) |
| `RATES.AGENCY_INVENTORY` | 2,344 | US callable agency analytics | Niche; partial data |
| `RATES.MIDCURVES` | 3,516 | Swaption mid-curves (USD/EUR/GBP) | Vol product — out of scope for bonds |
| `RATES.SPREAD_OPTIONS` | 576 | Curve-spread options (2Y10Y, etc.) | Vol product — out of scope |
| `RATES.FRA` | 445 | 20 ccys incl. KRW, CLP, COP, CZK, HUF, MXN, PLN, ZAR | Money-market FRAs; **only APAC EM rate data on Citi** |
| `RATES.FRA_OIS` | 121 | 11 G10 × ~38 forward meeting dates | Meeting-dated FRA-OIS |
| `RATES.OIS_INVOICESPREAD` | 44 | UST + Bund + BTP + OAT bond futures | Cash-vs-futures invoice spreads — high-value for basis trading |
| `RATES.INFLATION` | 6,830 | 4 sub-cubes (SWAP, SWAPTION, INF_CARRY, INDEX) | Inflation expectations; see `rates_inflation.md` |
| `RATES.FORECAST` | 12 | 7 series × {QTR, ANNUAL} | DM rate/yield forecasts — confirmed populated with quarterly publications |

### Dead or entitlement-gated (3 branches)

| Branch | Tags | Status |
|---|---|---|
| `RATES.INVOICESPREAD` | 14 | All return 0 points — appears empty |
| `RATES.POS_MON` | 32 | All return 0 points — likely Citi-internal positioning monitor |
| `RATES.SOV_CMT` (root) | n/a | Not enumerable via taglisting/tagbrowsing — see resolution below |

---

## `RATES.SOV` — full structural map (the main bond dataset)

11,773 tags. Three sub-cubes:

```
# 1. Constant-maturity yields + spreads
RATES.SOV.CMT.{COUNTRY}.{TENOR}.YIELD                         # nominal CMT yield
RATES.SOV.CMT.{COUNTRY}.{TENOR}.{FWD_T}.EUROSTR_SPRD          # yield vs EUROSTR (EUR ccys)
RATES.SOV.CMT.{COUNTRY}.{TENOR}.{FWD_T}.ASW                   # asset-swap spread
RATES.SOV.CMT.{COUNTRY}.{TENOR}.{FWD_T}.CAS                   # cash spread
RATES.SOV.CMT.{COUNTRY}.{TENOR}.{FWD_T}.YYS                   # yield-on-yield spread

# 2. Forward yields
RATES.SOV.FWD.{COUNTRY}.{START}.{TENOR}.YIELD

# 3. Bond-specific analytics (OTR benchmarks, butterflies, curves)
RATES.SOV.SOV.{COUNTRY}.{OTR|OTR_OLD|BFLY|CURVES|...}.{...}
```

### Country list (34 — all DM)

| Region | Countries |
|---|---|
| **G7** | USA, GBR, JPN, DEU, FRA, ITA, CAN |
| **Core Europe** | AUT, AUTFULL, BEL, CHE, DNK, ESP, FIN, IRL, LUX, NLD, NOR, SWE |
| **Periphery / CEE** | CYP, CZE, GRC, HUN, POL, PRT, ROU, SVK, SVN |
| **Other DM** | AUS, NZL, ISR |
| **EM** | TUR, ZAF, RUS (RUS empty — sanctions) |

**Missing (relevant to IMDR's APAC bonds matrix)**: CHN, KOR, SGP, IND, IDN, THA, MYS, HKG, TWN, PHL, VNM.

### Tag-density skew

| Country | Tags |
|---|---|
| BEL, DEU | 719 each (richest forward + spread surface) |
| FRA | 714 |
| ITA, ESP, NLD, PRT | 681–691 |
| IRL, FIN, GRC | 635–655 |
| CYP, LUX, SVK, SVN | 550 each |
| AUTFULL | 484 (empty data) |
| JPN | 351 |
| GBR | 331 |
| USA | 260 |
| AUT | 235 |
| AUS | 192 |
| NZL | 136 |
| CAN, DNK, SWE, NOR | 100–116 |
| CHE | 70 |
| CZE, HUN, ISR, POL, ROU, RUS, TUR, ZAF | 30 each (basic yield-only) |

European countries get the full forward+spread cube; English-speaking and EM get yields-only or a narrower grid.

### Confirmed live data samples

| Tag | Value | Date |
|---|---|---|
| `RATES.SOV.CMT.AUS.10Y.YIELD` | 4.927 | 2026-05-22 |
| `RATES.SOV.CMT.IRL.4Y.2Y.EUROSTR_SPRD` | +38.5 bp | 2026-05-22 |
| `RATES.SOV.CMT.USA.10Y.YIELD` | 4.586 | 2026-05-22 |

### Spread vocabulary (position 4 of CMT tags)

- `YIELD` — absolute yield
- `EUROSTR_SPRD` — spread vs EUROSTR fixings (EUR countries)
- `ASW` — asset-swap spread
- `CAS` — cash spread
- `YYS` — yield-on-yield spread
- `PRICE` — bond price
- `CITI` — Citi composite measure

### Tenor grid

Position 2 (and position 3 for forward-starting) draws from 30 buckets:
`1M, 3M, 6M, 9M, 1Y, 18M, 2Y, 3Y, 4Y, 5Y, 6Y, 7Y, 8Y, 9Y, 10Y, 11Y, 12Y, 13Y, 14Y, 15Y, 16Y, 17Y, 18Y, 19Y, 20Y, 25Y, 30Y, 40Y, 50Y, 1B` (1B = 1 business day / overnight proxy).

Not every country populates every tenor; USA populates all 30, EM populates the basic 7–8.

---

## `RATES.SOV_CMT` vs `RATES.SOV.CMT` — resolved

Two paths returning identical data:

| Tag | Value (2026-05-22) |
|---|---|
| `RATES.SOV_CMT.USA.10Y.YIELD` | 4.5861 |
| `RATES.SOV.CMT.USA.10Y.YIELD` | 4.5861 |

But the discovery surfaces differ:

| Endpoint | `RATES.SOV_CMT` | `RATES.SOV.CMT` |
|---|---|---|
| `fetch_tagbrowsing` | ERROR (no node) | OK |
| `fetch_taglisting` root | 0 tags | n/a |
| `fetch_taglisting("RATES.SOV_CMT.")` | 0 tags | n/a |
| `fetch_taglisting("RATES.SOV_CMT.USA.")` | 0 tags | 260 tags via `RATES.SOV.CMT` |
| `fetch_historical("RATES.SOV_CMT.USA.10Y.YIELD")` | OK (data flows) | OK (data flows) |

**Verdict**: `RATES.SOV_CMT.*` is a hidden alias accessible only via direct `fetch_historical`. **The canonical browsable path is `RATES.SOV.CMT.*`**. IMDR should standardise on `RATES.SOV.CMT.*` for ingest pipelines (so discovery scripts work), but consumers can use either form when fetching specific tags.

The older [`rates_sov_cmt.md`](rates_sov_cmt.md) referenced `RATES.SOV_CMT.*` — that path still works for direct fetches but is not enumerable.

---

## `RATES.TSY` (US Treasuries — 299 tags)

```
RATES.TSY.OTR.{TENOR}.{YIELD|PRICE|CONVEXITY|DURATION}
RATES.TSY.BFLY.{T1}.{T2}.{T3}                     # static butterflies
RATES.TSY.CURVES.{T1}.{T2}                        # 2D curve spreads
RATES.TSY.CMT.{BFLY|PAR}.{...}                    # constant-maturity variants
RATES.TSY.OLD_1.{...}                             # previous-cycle bonds
```

Vocabulary unique to TSY (not on the BBG CSV side): **CONVEXITY**, **DURATION**. The OTR node has the on-the-run benchmark; OLD_1 has the previous one-cycle-old benchmark for OTR/OLD basis trading.

Sample: `RATES.TSY.BFLY.10Y.20Y.30Y` = +0.535 on 2026-05-22.

---

## `RATES.T_BILL` (US T-Bills — 12 tags)

```
RATES.T_BILL.OTR.{1M|3M|6M|1Y}.{YIELD|PRICE|ASS_SOFR}
```

Sample (2026-05-22): 1M yield 3.589%, 1M ASS_SOFR +81.8 bp.

---

## `RATES.TIPS` (US TIPS — 26 tags)

```
RATES.TIPS.USD.{5Y|10Y|30Y}.YIELD                     # real yield
RATES.TIPS.USD.{5Y|10Y|30Y}.PRICE                     # bond price
RATES.TIPS.USD.{5Y|10Y|30Y}.BREAKEVENS                # bond-derived breakeven
RATES.TIPS.USD.{5Y|10Y|30Y}.ASS_SOFR                  # spread to SOFR
RATES.TIPS.USD.{5Y|10Y|30Y}.CARRY.{1M|3M}             # carry over horizon
RATES.TIPS.USD.{5Y|10Y|30Y}.CARRY_BE.{1M|3M}          # breakeven carry
RATES.TIPS.EXT_POLATED.10Y.{BE_INFL|YIELD}            # empty
```

**The cleanest BEI source on Citi.** Matches BBG's `USGGBE10`-family semantic exactly for US. The `BREAKEVENS` measure is the nominal-minus-real bond-derived breakeven; the `CARRY_BE` measure is the forward breakeven.

Sample (2026-05-22): TIPS USD 30Y ASS_SOFR +110.5 bp, USD 10Y CARRY.3M = 15.6 bp.

`EXT_POLATED` returns no data; appears to be a stub.

---

## `RATES.SSA` (European supranationals — 708 tags)

```
RATES.SSA.{ISSUER}.SPOT.{TENOR}.{YIELD|DEU_SPRD|UST_SPRD|COMP_SPRD}
RATES.SSA.{ISSUER}.EUR_USD.{TENOR}.{...}                # FX-hedged
```

**35 issuers** (positions 0): AGFRNC, BNG, CADES, CAF, CDEP, COE, EFSF, EIB, ESM, EU, FLEMSH, IBRD, KFW, MADRID, NEDWBK, NRW, NRWBK, UNEDIC, WALLOO, and 16 more.

**4 spread/yield measures** per issuer per tenor (16 tenors: 1Y, 2Y, 3Y, 4Y, 5Y, 6Y, 7Y, 8Y, 10Y, 12Y, 15Y, 20Y, 30Y, 40Y, 50Y, and a 1-month bucket):
- `YIELD` — absolute yield
- `DEU_SPRD` — spread to Bund
- `UST_SPRD` — spread to UST
- `COMP_SPRD` — composite spread

Sample (2026-05-22): AGFRNC 10Y vs Bund = +83.3 bp; ESM 7Y vs Bund = +18.2 bp.

Useful sidecar to the Bund / OAT / BTP curve. Sits beside sovereigns in the IMDR fact table, not separately.

---

## `RATES.SSA_CS` (100 tags) — cross-currency SSA basis

```
RATES.SSA_CS.{ISSUER}.EUR_USD.{2Y|3Y|5Y|7Y|10Y}.{UST_SPRD|COMP_SPRD}
```

22 issuers including **ASIA, AIIB, JBIC** (Asian-headquartered, but Citi prices them as European-style supranationals). Data confirmed; ~12 points per 30 days.

---

## `RATES.FRA` (445 tags) — the only APAC EM rate node

```
RATES.FRA.{CCY}.{START}.{TENOR}
```

**20 currencies** including:

| Tier | Currencies |
|---|---|
| **G10** | AUD, CAD, CHF, DKK, EUR, GBP, NOK, NZD, SEK, USD |
| **EM** | CLP, COP, CZK, HUF, **KRW**, MXN, PLN, ZAR + 2 more |
| **Other** | ILS |

KRW is the only APAC EM currency anywhere in the bond-relevant Citi catalog. It's FRAs (money-market forward rates), not bonds, but it would be the funding leg for any KRW asset-swap analysis once we have KRW bonds from BBG.

Some tenors are calendar-anchored (`15_DEC_2027Y`, `16_JUN_2027Y`, etc.) — IMM-style forward start dates.

---

## `RATES.OIS_INVOICESPREAD` (44 tags) — bond-future cash basis

```
RATES.OIS_INVOICESPREAD.{ROOT}_{FRONTMONTH|BACKMONTH}.{FUTURE}
```

**24 distinct future roots**:

| Region | Futures |
|---|---|
| **US** | USD_SOFR, USD_FEDFUND |
| **Bund family** | EUR_FGBX (Buxl 30Y), EUR_FGBL (Bund 10Y), EUR_FGBM (Bobl 5Y), EUR_FGBS (Schatz 2Y) |
| **BTP family** | EUR_FBON (long BTP), EUR_FBTP (10Y), EUR_FBTM (5Y), EUR_FBTS (2Y) |
| **OAT family** | EUR_FOAT (10Y), EUR_FOAM (5Y) |

Sample (2026-05-22): Bund front-month invoice spread +58.0 bp; OAT front-month +48.3 bp.

**For cash-vs-futures basis trading this is exactly what desks need.** Doesn't help APAC, but it's a non-trivial addition for the DM half of any bond fact table. Worth ingesting alongside SOV.

---

## `RATES.INFLATION` (6,830 tags) — full inflation cube

Already documented separately in [`rates_inflation.md`](rates_inflation.md). Sub-structure:

```
RATES.INFLATION.INDEX.{COUNTRY_CPI}                              # raw CPI fixings
RATES.INFLATION.SWAP.{CCY_INDEX}.{TENOR}.{FWD_TENOR}             # ZC inflation swaps
RATES.INFLATION.SWAPTION.{CCY_INDEX}.{EXP}.{TENOR}.{...}         # vol surface
RATES.INFLATION.INF_CARRY.{CCY}_CARRY.{...}                      # carry analytics
```

**28 currency–index combos**:

| Coverage tier | Combos | Tag density |
|---|---|---|
| **Full surface** (swap + swaption) | EUR_CPTFEMU, GBP_UKRPI, USD_CPURNSA | ~935 tags each |
| **Swap surface only** | EUR_PLCPI, EUR_IECP2006, EUR_NECPIND, AUD_AUCPI, EUR_BECPHLTH, EUR_DNCPINEW, EUR_FRCPXTOB, EUR_GRCP2000, EUR_ITCPI, EUR_SPIPC, ILS_ISCPIL, JPY_JCPNGENF, SEK_SWCPI | ~289 tags each |
| **Carry only** | AUD_CARRY, DEU_CARRY, FRA_CARRY, GBP_CARRY, ITA_CARRY, USD_CARRY | 30 tags each |
| **Raw index** | EURO_HICPXT, FRANCE_CPI, SWEDEN_CPI, UK_RPI, US_CPIZU, US_CPI | 1–15 tags each |

**No APAC EM inflation** either. This is the swap-implied breakeven proxy for the 6 DM countries in the IMDR bonds matrix, but it is **not the same instrument** as the BBG `*GGBE10`-series bond-derived BEI. Different leg, different basis risk.

---

## `RATES.FORECAST` (12 tags) — resolved

Previously listed as "no data in 30-day probe — likely infrequent updates." Re-probe with 365-day window confirms:

| Tag | Points (1y) | Last observation | Value |
|---|---|---|---|
| `RATES.FORECAST.FED_FUNDS_FCST.QTR.CITI` | 4 | 2026-03-31 | 3.75% |
| `RATES.FORECAST.FED_FUNDS_FCST.ANNUAL.CITI` | 1 | 2025-12-31 | 3.75% |
| `RATES.FORECAST.ECB_DEPO_FCST.QTR.CITI` | 4 | 2026-03-31 | 2.00% |
| `RATES.FORECAST.UST_2Y_YLD_FCST.QTR.CITI` | 4 | 2026-03-31 | 3.82% |
| `RATES.FORECAST.UST_10Y_YLD_FCST.QTR.CITI` | 4 | 2026-03-31 | 4.33% |
| `RATES.FORECAST.GER_10Y_YLD_FCST.QTR.CITI` | 4 | 2026-03-31 | 2.83% |
| `RATES.FORECAST.UK_10Y_YLD_FCST.QTR.CITI` | 4 | 2026-03-31 | 4.49% |
| `RATES.FORECAST.JGB_10Y_YLD_FCST.QTR.CITI` | 4 | 2026-03-31 | 2.20% |
| `RATES.FORECAST.JGB_10Y_YLD_FCST.ANNUAL.CITI` | 1 | 2025-12-31 | 1.68% |

**Verdict**: Citi publishes quarterly forecasts (4 points/year) and annual forecasts (1 point/year) for Fed, ECB, UST 2Y/10Y, Gilt 10Y, Bund 10Y, JGB 10Y. Useful for `rates.fact_yield_forecast` (separate from the observed-yield fact).

---

## Coverage matrix — IMDR's 13-country bonds table

For the user-supplied APAC-anchored bonds matrix (US, UK, JP, DE, FR, AU, CN, KR, SG, IN, ID, TH, MY × {Nominal, BEI, Real}):

| Country | Nominal | BEI (true bond-derived) | BEI (swap-implied proxy) | Real | Citi spreads (ASW/EUROSTR/CAS) | Citi forwards |
|---|---|---|---|---|---|---|
| **US** | `SOV.CMT.USA` (30 tenors) | `TIPS.USD.{5,10,30}Y.BREAKEVENS` | `INFLATION.SWAP.USD_CPURNSA` | `TIPS.USD.{5,10,30}Y.YIELD` | partial | yes |
| **UK** | `SOV.CMT.GBR` | — | `INFLATION.SWAP.GBP_UKRPI` (full surface) | — | partial | yes |
| **Japan** | `SOV.CMT.JPN` | — | `INFLATION.SWAP.JPY_JCPNGENF` (swap only) | — | partial | yes |
| **Germany** | `SOV.CMT.DEU` (719 tags) | — | `INFLATION.SWAP.EUR_CPTFEMU` (full) | — | **rich** (ASW + EUROSTR_SPRD + forward) | yes |
| **France** | `SOV.CMT.FRA` (714 tags) | — | `INFLATION.SWAP.EUR_FRCPXTOB` | — | **rich** | yes |
| **Australia** | `SOV.CMT.AUS` | — | `INFLATION.SWAP.AUD_AUCPI` | — | partial | yes |
| **China** | — | — | — | — | — | — |
| **Korea** | — | — | — | — | — | — |
| **Singapore** | — | — | — | — | — | — |
| **India** | — | — | — | — | — | — |
| **Indonesia** | — | — | — | — | — | — |
| **Thailand** | — | — | — | — | — | — |
| **Malaysia** | — | — | — | — | — | — |

**6/13 nominals covered, 1/13 true BEI covered, 5/13 swap-implied BEI proxy. 7/13 APAC EM rows completely uncovered.**

---

## Implications for the IMDR sovereign-bond design

### 1. Vendor model

| Country group | Primary | Fallback |
|---|---|---|
| US, UK, JP, DE, FR, AU | BBG_mirror | Citi Velocity |
| 28 other DM (NL, IT, ES, CH, NO, SE, etc.) | Citi Velocity | none (BBG doesn't cover them by default) |
| APAC EM (CN, KR, SG, IN, ID, TH, MY) | BBG_mirror | **none** |

BBG_mirror is the only path for APAC EM sovereigns. SLA on the mirror is load-bearing for those countries; any outage takes IMDR's APAC sov coverage offline with no recovery.

### 2. Schema — `yield_type` taxonomy

The proposed `rates.fact_sov_yield` needs to distinguish bond-derived from swap-derived inflation expectations, because they trade differently:

| `yield_type` | Source instrument | Bond? |
|---|---|---|
| `NOMINAL` | Govt bond yield (CMT) | yes |
| `REAL` | TIPS / linker yield | yes |
| `BEI` | Bond-derived breakeven (`USGGBE10`, `TIPS.USD.{T}.BREAKEVENS`) | yes |
| `INFL_SWAP` | Inflation-swap-implied breakeven (`INFLATION.SWAP.*`) | no (separate fact) |

Conflating BEI and INFL_SWAP masks the swap-vs-cash basis that desks actually trade. The INFL_SWAP series should live in `rates.fact_inflation_swap` (or `macro.fact_inflation_expectations`), not in the bond fact.

### 3. Schema — `quote` vocabulary

The existing `rates.fact_observation.quote varchar(10)` won't fit Citi's spread vocabulary. The sovereign-bond fact needs:

```
quote ∈ {
  YIELD,         # bond yield (nominal/real/BEI)
  PRICE,         # bond price
  ASW,           # asset-swap spread
  CAS,           # cash spread
  YYS,           # yield-on-yield spread
  EUROSTR_SPRD,  # spread to EUROSTR
  UST_SPRD,      # spread to UST (SSA)
  DEU_SPRD,      # spread to Bund (SSA)
  COMP_SPRD,     # Citi composite spread
  BREAKEVENS,    # TIPS breakeven (bond-derived)
  CARRY,         # carry over a horizon
  DURATION,      # modified duration
  CONVEXITY,     # convexity
  INV_SPRD,      # bond-future invoice spread
}
```

Widen to `varchar(20)` and accept arbitrary upstream tokens; resolve to enum at the ORM layer.

### 4. Schema — `dim_curve` extension

Existing `rates.dim_curve.curve_type` enum: `basis`, `ccs`, `ibor`, `rfr`. Needs the additions:

- `sovereign` — for SOV/SOV.CMT data
- `ssa` — for European supranational issuers
- `bond_future_basis` — for OIS_INVOICESPREAD
- (deferred) `agency_callable`, `mbs` — not for sov-bond scope

The `instrument` enum needs: `govt_nominal`, `govt_real`, `govt_bei`, `govt_asw`, `govt_fwd`, `ssa_yield`, `ssa_spread`, `invoice_spread`.

### 5. Forecasts as a separate fact

Citi's `RATES.FORECAST` (12 tags) is forecast data, not observed yields. Doesn't belong in `fact_sov_yield`. Recommend a sibling `rates.fact_yield_forecast` with `(forecast_tag, vendor_id, publish_date, target_date, value, horizon)`.

### 6. Cash-vs-futures basis as a sibling fact

`OIS_INVOICESPREAD` (44 tags) is a contract-anchored basis dataset, not a yield. Either:
- a `quote='INV_SPRD'` lane in `fact_sov_yield` with `tenor='FRONT_MONTH'/'BACK_MONTH'` semantics, or
- a small sibling `rates.fact_bond_future_basis` with explicit `(future_code, contract_month, vendor, obs_date, basis_bp)`.

The sibling-fact approach is cleaner because the "future_code" axis (FGBL, FBTP, FOAT) doesn't fit the `(country, tenor, yield_type)` shape.

---

## `dim_curve` seed list for the bond rows

The following rows would be added to `rates.dim_curve` to register the sovereign-bond curves. These are derived from the new SOV exploration + the user's APAC-anchored matrix. Source vendor is suggestive — the actual primary is determined by `dim_curve.primary_from` once both vendors are live.

### DM sovereigns (6 in IMDR's bonds matrix + recommended extensions)

| ccy | curve | country_code | curve_type | instrument | citi_prefix | bbg_ticker_prefix |
|---|---|---|---|---|---|---|
| USD | UST | USA | sovereign | govt_nominal | `RATES.SOV.CMT.USA` | `USGG` |
| USD | UST_TIPS | USA | sovereign | govt_real | `RATES.TIPS.USD` | `GTII` |
| USD | UST_BEI | USA | sovereign | govt_bei | `RATES.TIPS.USD.{T}.BREAKEVENS` | `USGGBE` |
| GBP | GILT | GBR | sovereign | govt_nominal | `RATES.SOV.CMT.GBR` | `GUKG` |
| GBP | GILT_BEI | GBR | sovereign | govt_bei | — | `UKGGBE` |
| JPY | JGB | JPN | sovereign | govt_nominal | `RATES.SOV.CMT.JPN` | `GJGB` |
| JPY | JGB_BEI | JPN | sovereign | govt_bei | — | `JYGGBE` |
| EUR | BUND | DEU | sovereign | govt_nominal | `RATES.SOV.CMT.DEU` | `GDBR` |
| EUR | BUND_BEI | DEU | sovereign | govt_bei | — | `DEGGBE` |
| EUR | OAT | FRA | sovereign | govt_nominal | `RATES.SOV.CMT.FRA` | `GFRN` |
| EUR | OAT_BEI | FRA | sovereign | govt_bei | — | `FRGGBE` |
| AUD | ACGB | AUS | sovereign | govt_nominal | `RATES.SOV.CMT.AUS` | `GACGB` |
| AUD | ACGB_BEI | AUS | sovereign | govt_bei | — | `ADGGBE` |

### APAC EM sovereigns (BBG-only)

| ccy | curve | country_code | curve_type | instrument | citi_prefix | bbg_ticker_prefix |
|---|---|---|---|---|---|---|
| CNY | CGB | CHN | sovereign | govt_nominal | — | `GTCNY` (note: existing R pipeline uses `GCDB` = CDB agency, not CGB) |
| KRW | KTB | KOR | sovereign | govt_nominal | — | `GTKRW` (R pipeline uses `GVSK` on-the-run) |
| SGD | SIGB | SGP | sovereign | govt_nominal | — | `GTSGD` (R pipeline uses same) |
| INR | IGB | IND | sovereign | govt_nominal | — | `GTINR` (R pipeline uses `GIND`) |
| IDR | IDGB | IDN | sovereign | govt_nominal | — | `GTIDR` (R pipeline uses `GIDN`) |
| THB | THAIGB | THA | sovereign | govt_nominal | — | `GTTHB` (R pipeline uses `GVTL`) |
| MYR | MGS | MYS | sovereign | govt_nominal | — | `GTMYR` (R pipeline uses `MAGY`) |

**Ticker mismatch flag**: every APAC EM ticker in the existing R BBG pipeline differs from the table the user supplied (which uses `GT{CCY}10Y Index` generic series). Different underlying bonds — generic CMT vs on-the-run benchmark vs agency proxy. Decision required before seeding: whether to align to the user's table (re-ingest BBG with `GT*` tickers) or accept the R pipeline's current convention.

### Optional DM extensions (Citi-only, not in user's matrix)

The 28 additional Citi DM sovereigns (CAN, CHE, ITA, ESP, NLD, BEL, AUT, IRL, FIN, GRC, PRT, NOR, SWE, DNK, NZL, ISR, LUX, PLN, CZE, HUN, ROU, SVK, SVN, CYP, TUR, ZAF, plus AUTFULL) can be added in a second wave. Listed for completeness but out of scope for the initial 13-country build.

### SSA (sibling rows)

If we ingest `RATES.SSA` alongside sovereigns, ~35 issuer rows enter `dim_curve` with `curve_type='ssa'`. Spread axis (`DEU_SPRD`, `UST_SPRD`, `COMP_SPRD`) handled via `quote` column on the fact.

---

## Suggested next actions (ordered)

1. **Resolve BBG ticker convention for APAC EM** — generic `GT*` series vs current R-pipeline on-the-run tickers. Affects the `dim_curve` seed rows above. Coordinate with whoever owns the R pipeline / BBG xlsx.
2. **Confirm `BBG_mirror` plan for bonds** — folder layout, refresh cadence, file format. Per [`bbg_mirror_fx_cutover`](../../../fx/) precedent, IMDR should not read `Z:\...\BBG\BONDS\` directly.
3. **Resolve `dim_vendor` `BBG` vs `bloomberg` duplication** — blocker for any bond row.
4. **Write migration `NNN_create_fact_sov_yield.sql`** — see schema design above; include `yield_type` enum + widened `quote` vocab.
5. **Backfill from BBG historicals** — the `*price dump.xlsx` files in `Z:\...\BBG\BONDS\{CCY}\{GOVT|LINKER}\` may carry longer history than the live CSVs. Profile separately.
6. **Build Citi ingest as second-vendor source** — once `BBG_mirror` flow is live, add Citi as parallel for DM (US, UK, JP, DE, FR, AU + the 28 extension countries).
7. **`OIS_INVOICESPREAD` and `RATES.FORECAST` as siblings** — separate small facts, not crammed into `fact_sov_yield`.

---

## Cache files

`data/cache/rates/bonds_deep.json` — 123 KB, contains:
- `branches.*` — per-branch taglist count, schema decomposition, sample data flow
- `followups.sov_cmt_*` — resolution of SOV vs SOV_CMT
- `followups.forecast_year` — 1-year window forecast data

Do not re-run unless the structure of Citi's catalog changes. Each re-run consumes ~95 tag-fetches against the 100K/24h quota.

## Cross-references

- [`rates_full.md`](rates_full.md) — broader RATES catalog (135K tags); SOV/MBS/AGENCY_INVENTORY entries there are now superseded by this doc
- [`rates_sov_cmt.md`](rates_sov_cmt.md) — older SOV_CMT-as-canonical doc; the `SOV_CMT` path still works for direct fetches but the canonical browsable path is `SOV.CMT`
- [`rates_inflation.md`](rates_inflation.md) — INFLATION subcube
- `docs/admin/development/apac_macro_data_gaps.md` — desk-needs framing; this doc completes the bond row in that table
