# IMDR Data Gap Analysis — APAC Macro Desk

What does the desk need to see every morning, and what can we deliver?

- **Date**: 2026-03-27
- **Blueprint**: `docs/IMDR_blueprint/RVCapital - IMDR Global Blueprint.pdf`
- **Playbook**: `docs/admin/new_product_playbook.md`

---

## How This Doc Is Organised

Not by data source or API namespace — by **what question the desk is asking**. Each section maps to a user need, then shows what we have, what's confirmed available, and what's missing.

---

## 1. "Where are rates?" — Yield Curves & Sovereign Bonds

The most basic question. Every morning starts here.

| What the desk needs | Table | Schema | Status | Source |
|---|---|---|---|---|
| OIS/IRS swap curves (20 indices, full tenor) | `fact_ois` | rates | BUILT | Citi Velocity |
| Govt bond yields — 32 countries, 30 tenors | `fact_govtbond` | rates | READY — SOV_CMT 8,250 tags confirmed | Citi Velocity |
| US Treasuries OTR (2Y/5Y/10Y/30Y) | `fact_govtbond` | rates | READY — TSY confirmed | Citi Velocity |
| US T-Bills (1M–1Y yield, price, SOFR spread) | `fact_govtbond` | rates | READY — 12 tags confirmed | Citi Velocity |
| Forward yields (USA/JPN/AUS/DEU/GBR 5Y5Y) | `fact_fwd_curve` | rates | READY — 5 countries confirmed | Citi Velocity |
| Curve butterflies (2s5s10s, 5s10s30s) | `fact_butterfly` | rates | READY — 5 countries, both wings | Citi Velocity |
| TIPS real yields + breakevens + carry | `fact_real_yield` | rates | READY — 24/26 tags confirmed | Citi Velocity |

**Gap**: Forward yields only work for USA, JPN, AUS, DEU, GBR, NZL. No KOR, CHN, IND — derive from SOV_CMT. Curve spreads (2s10s) NOT returning from Citi — only butterflies work.

---

## 2. "What's the market pricing for central banks?" — CB Policy

The most important APAC question. BOJ, RBA, RBNZ decisions drive everything.

| What the desk needs | Table | Schema | Status | Source |
|---|---|---|---|---|
| Current policy rates (Fed, ECB, BOJ, BoE) | `fact_policy_rates` | macro | READY — BENCH_RATES 8/10 confirmed | Citi Velocity |
| Market-implied rate path per CB meeting | `fact_cb_meeting_ois` | macro | READY — all 10 G10 CBs, 449 tags | Citi Velocity |
| CB meeting calendar + speakers | `fact_cb_events` | calendar | BUILT | Bloomberg + scrapers |
| Historical CB decisions + hike/cut classification | `fact_cb_policy_stance` | macro | NOT BUILT | FRED / CB websites |

**Key finding**: `fact_cb_meeting_ois` is the single most actionable new dataset. Daily time series of what the swap market prices for each upcoming BOJ/RBA/Fed/ECB meeting. As of 2026-03-25: BOJ priced at +40bp of hikes by Oct (0.50% → 1.14%), Fed flat (no cuts), RBA +38bp tightening.

**Schema rationale**: `macro` not `calendar`. "When is the BOJ meeting?" = calendar. "What's the market pricing for the BOJ meeting?" = macro. Split from blueprint's `fact_imm_dates` — IMM dates are mechanical quarterly settlement dates (algorithmic, already in `imm.py`), meeting-dated OIS is market pricing (daily time series). Different grain, different source, different purpose. See `docs/rates/ois_meeting_exploration.md`.

**Gap**: No BOK, RBI, PBoC meeting-dated OIS — only G10 central banks on Citi.

---

## 3. "What's the risk environment?" — Vol & Risk-Off Signals

Before sizing any trade, the desk needs to know the vol regime.

| What the desk needs | Table | Schema | Status | Source |
|---|---|---|---|---|
| FX vol surface (17 pairs, full strike/tenor) | `fact_vol_surface` | fx | BUILT | Citi Velocity |
| Swaption vol cube (11 ccys, 3D surface) | `fact_swaption_vol` | rates | BUILT | Citi Velocity |
| VIX, VIX3M, VIX9D, VVIX, VXN | `fact_vix` | equities | READY — all 5 confirmed | Citi Velocity |
| MOVE index (rates vol) | `fact_move` | equities | **NOT ON CITI** — ICE/BofA proprietary | Bloomberg |
| Equity vol swaps (197 tickers × 13 tenors) | `fact_equity_vol` | equities | READY — VOLSWAP confirmed | Citi Velocity |
| Variance swaps (SPX, NDX, N225 etc.) | `fact_equity_vol` | equities | READY — VARSWAP confirmed | Citi Velocity |
| Commodity vol (XAU, XAG, oil ATM) | `fact_commodity_vol` | commodities | BUILT | Citi Velocity |
| Equity-bond correlation (regime switch) | `fact_equity_bond_corr` | regime | NOT BUILT — derived | Derived |

**Gap**: MOVE is the #1 missing risk signal. Must come from Bloomberg. No European vol indices (V2X/VSTOXX/VDAX) on Citi either.

---

## 4. "What's funding doing?" — Cross-Currency Basis & Money Markets

Funding stress is the earliest warning signal. APAC desks watch JPY and AUD basis obsessively.

| What the desk needs | Table | Schema | Status | Source |
|---|---|---|---|---|
| Cross-currency OIS basis (all G10 pairs) | `fact_xccy_basis` | rates | READY — all 90 pairs, 76K tags | Citi Velocity |
| Tenor basis (3s1s, 6s3s) | `fact_basis_swap` | rates | PARTIAL — EUR confirmed, USD needs work | Citi Velocity |
| USD BGCR + Fed funds effective | `fact_rfr_fixing` | funding | READY — BGCR 3.63%, FFT 3.75% | Citi Velocity |
| AUD BBSW fixings (1M/2M/3M) | `fact_rfr_fixing` | funding | READY — confirmed | Citi Velocity |
| KRW FRA grid | `fact_fra_ois` | funding | READY — 36 tags, all returning | Citi Velocity |
| JPY money markets (TONAR) | `fact_rfr_fixing` | funding | **NOT WORKING** — JPY tags empty | Bloomberg / FRED |
| JGB repo & specials | `fact_repo_jgb` | funding | **NOT ON CITI** | Barclays/PAML emails |
| Fed RRP, TGA, reserves | `fact_fed_rrp` / `fact_tga` | funding | NOT BUILT — available on FRED | FRED |
| FX forward points (CNH/JPY, INR/JPY) | `fact_fwd_points` | fx | READY — CNH 58 tags, INR 29 tags | Citi Velocity |

**Gap**: JPY funding data is critical for APAC and largely missing from Citi. FX forward points are cross-pair only (vs JPY, PLN) — no CCY/USD NDFs, those need BidFX.

---

## 5. "What's the macro picture?" — Economic Data & Surprise Indices

Every rates trade has a macro thesis. This is the fundamental layer.

| What the desk needs | Table | Schema | Status | Source |
|---|---|---|---|---|
| Citi Economic Surprise (CESI) — 66 regions | `fact_surprise_index` | macro | READY — 2,415 tags, all daily | Citi Velocity |
| Citi PAIN Index (FX positioning) | `fact_surprise_index` | macro | READY — 10 G10 ccys | Citi Velocity |
| Citi Terms of Trade (CTOT) | `fact_surprise_index` | macro | READY — 68 DM+EM ccys | Citi Velocity |
| Inflation breakevens (5Y5Y, spot) | `fact_inflation_expectations` | macro | READY — USD/EUR/GBP | Citi Velocity |
| Inflation swap surface (17 ccys) | `fact_inflation_swap` | macro | READY — 5,999 tags | Citi Velocity |
| CPI by country | `fact_cpi` | macro | NOT BUILT | FRED / national stats |
| US PCE deflator | `fact_pce` | macro | NOT BUILT | FRED |
| GDP, labour, PMI/ISM | `fact_gdp` etc. | macro | NOT BUILT | FRED |
| China TSF / social financing | `fact_social_financing` | macro | **NOT ON CITI** | PBoC / Bloomberg |
| China property prices | `fact_property` | macro | **NOT ON CITI** | NBS |
| Financial conditions (NFCI) | `fact_fin_conditions` | macro | NOT BUILT | FRED |

**Schema rationale**: CESI, CITIPAIN, CTOT come from the FX namespace on Citi, but they're macro regime signals. Inflation breakevens come from the RATES namespace, but "what's the market pricing for inflation?" is a macro question. All live in `macro`.

**Gap**: The entire `macro` schema beyond Citi surprise indices is empty. FRED connector is the highest-leverage build — unlocks CPI, PCE, GDP, labour, financial conditions in one go.

---

## 6. "Where is everyone positioned?" — Flows & Positioning

Price tells you where the market is. Positioning tells you who's vulnerable.

| What the desk needs | Table | Schema | Status | Source |
|---|---|---|---|---|
| CFTC COT (Treasury futures) | `fact_cftc_cot` | positioning | NOT BUILT | CFTC (free, weekly) |
| CFTC TFF (institutional breakdown) | `fact_cftc_tff` | positioning | NOT BUILT | CFTC (free, weekly) |
| EPFR bond fund flows | `fact_epfr_flows` | positioning | NOT BUILT | EPFR (commercial) |
| TIC foreign UST holdings | `fact_tic` | positioning | NOT BUILT | US Treasury (free, monthly) |
| CB FX reserves (BOJ, PBOC, RBI) | `fact_cb_reserves` | positioning | NOT BUILT | National CBs |
| Fed custody holdings | `fact_fed_custody` | positioning | NOT BUILT | Fed (free, weekly) |

**Gap**: Entire positioning schema is empty. CFTC and Fed data are free public APIs — low-hanging fruit.

---

## 7. "What are equity markets telling us?" — Cross-Asset Signals

For a rates desk, equities are regime inputs, not a book.

| What the desk needs | Table | Schema | Status | Source |
|---|---|---|---|---|
| Global index levels (24 tickers) | `fact_index_futures` | equities | READY — SPX through SET | Citi Velocity |
| Equity vol (VOLSWAP, VARSWAP) | `fact_equity_vol` | equities | READY | Citi Velocity |
| VIX family | `fact_vix` | equities | READY | Citi Velocity |
| Sector rotation (cyclicals vs defensives) | `fact_sector_rotation` | equities | NOT BUILT | Bloomberg |
| Energy + metals spot | `fact_energy_spot` / `fact_metals_spot` | commodities | BUILT | Citi Velocity |

---

## 8. "What does the quant model say?" — Signals & Factor Scores

Full exploration: **`docs/admin/development/quant_signals_citi.md`**

~40,000 new tags of pure quant signals confirmed on Citi. Summary:

| What the desk needs | Dataset | Tags | Schema | Status |
|---|---|---|---|---|
| FX carry per pair (bid/ask/mid, all tenors) | FX.CARRY | 15,246 | fx | ALL WORKING |
| FX fair value (5 models × every pair) | FX.CFV | 21,818 | fx | ALL WORKING |
| Multi-factor FX scorecard (12 factors × 32 ccys) | FX.SC_SCORECARD | 460 | fx | ALL WORKING |
| Inflation carry (IOTA, BEI carry, real yield carry) | INF_CARRY | 180 | rates | ALL WORKING |
| FX swap points (IMM-dated) | FX.SWAP | 430 | fx | ALL WORKING |
| Citi FX forecasts (3M, 12M, LT) | FX.FORECAST | 108 | fx | ALL WORKING |
| GERM model weights (valuation transparency) | GERM_WEIGHTS | 600 | fx | ALL WORKING |
| NEER/REER effective exchange rates | NEER_IDX + REER_IDX | 328 | fx | ALL WORKING |
| Macro Risk Index (EM, LT, ST — decomposed) | FX.MRICITI | 23 | regime | 22/23 WORKING |
| Fundamental Uncertainty Index | FX.FXFUI | 145 | regime | ALL WORKING |
| FX Risk Model Index | FX.FXRMI | 34 | regime | ALL WORKING |
| EM Early Warning System (25 ccys × 15 factors) | FX.CEWS | 491 | regime | ALL WORKING |
| Commodity price forecasts | COMMODITIES.FORECAST | 115 | commodities | PARTIAL |

---

## Schema Placement Audit

Data lives where the **user expects to find it**, not where the API serves it from.

| Data | Citi Namespace | Blueprint Says | We Recommend | Rationale |
|---|---|---|---|---|
| CB meeting-dated OIS | RATES.OIS_MEETING | `calendar.fact_imm_dates` | **`macro.fact_cb_meeting_ois`** | Market pricing of policy = macro, not calendar. Split from IMM dates (different grain). |
| Policy rates (Fed, ECB, BOJ) | RATES.BENCH_RATES | `macro.fact_policy_rates` | **`macro.fact_policy_rates`** | "What's the current Fed rate?" = macro question |
| CESI / CITIPAIN / CTOT | FX.SURPRISE_INDEX / FX.CITIPAIN / FX.CTOT | `macro.fact_surprise_index` | **`macro.fact_surprise_index`** | Regime signals, not FX instruments |
| Inflation breakevens (5Y5Y) | RATES.INFLATION.SWAP | — | **`macro.fact_inflation_expectations`** | "What's the market pricing for inflation?" = macro |
| Inflation swap full surface | RATES.INFLATION.SWAP | `rates.fact_real_yield` | **`rates.fact_inflation_swap`** | Forward inflation = macro signal. Full swap surface may also serve rates. |
| TIPS real yields | RATES.TIPS | `rates.fact_real_yield` | **`rates.fact_real_yield`** | Bond yield — rates correct |
| VIX / VVIX | EQUITY.EQUITY_INDEX | `equities.fact_vix` | **`equities.fact_vix`** | Correct |
| Equity index levels | EQUITY.EQUITY_INDEX | `equities.fact_index_futures` | **`equities.fact_index_futures`** | Correct |
| SOV butterflies | RATES.SOV | `rates.fact_butterfly` | **`rates.fact_butterfly`** | Correct |
| XCCY basis | RATES.XCCY_OIS_SWAP | `rates.fact_xccy_basis` | **`rates.fact_xccy_basis`** | Correct |
| FX carry | FX.CARRY | — | **`fx.fact_carry`** | FX rate differential data, lives with FX |
| FX fair value (CFV) | FX.CFV | — | **`fx.fact_fair_value`** | FX valuation models, lives with FX |
| FX scorecard | FX.SC_SCORECARD | — | **`fx.fact_scorecard`** | FX factor model, lives with FX |
| FX forecasts | FX.FORECAST | — | **`fx.fact_forecast`** | FX forecasts, lives with FX |
| NEER / REER | FX.NEER_IDX / FX.REER_IDX | — | **`fx.fact_effective_rate`** | Trade-weighted FX indices, lives with FX |
| FX swap points | FX.SWAP | — | **`fx.fact_swap_points`** | IMM-dated FX swap data |
| GERM weights | FX.GERM_WEIGHTS | — | **`fx.dim_germ_weights`** | Reference data for CFV models |
| Inflation carry | RATES.INFLATION.INF_CARRY | — | **`rates.fact_inf_carry`** | Inflation carry analytics, rates-linked |
| Macro Risk Index | FX.MRICITI | — | **`regime.fact_mri`** | Risk-on/off classification input |
| Uncertainty Index | FX.FXFUI | — | **`regime.fact_uncertainty`** | Regime classification input |
| FX Risk Model | FX.FXRMI | — | **`regime.fact_fx_risk`** | Per-currency risk classification |
| EM Early Warning | FX.CEWS | — | **`regime.fact_em_warning`** | EM vulnerability scoring |
| Commodity forecasts | COMMODITIES.FORECAST | — | **`commodities.fact_forecast`** | Commodity forecasts |

---

## Build Priority — By User Workflow

Ordered by **"what unblocks the most desk workflows"**, not by data source convenience.

### Sprint 1: The Morning Dashboard
> *"Give me the full picture in one screen"*

1. **SOV_CMT** → `rates.fact_govtbond` — 15 core countries × 13 tenors (195 tags/day)
2. **CB Meeting OIS** → `macro.fact_cb_meeting_ois` — 10 CBs, ~70 meetings (70 tags/day)
3. **Equity indices** → `equities.fact_index_futures` — 24 global indices (24 tags/day)
4. **BENCH_RATES** → `macro.fact_policy_rates` — current CB rates (10 tags/day)
5. **VIX family** → `equities.fact_vix` — risk-off signal (5 tags/day)

**304 tags/day. Unblocks: morning brief, risk dashboard, CB pricing monitor.**

### Sprint 2: Trade Construction
> *"Help me build and size this trade"*

6. **XCCY_OIS_SWAP** → `rates.fact_xccy_basis` — 13 pairs × 9 tenors (117 tags/day)
7. **INFLATION.SWAP** → `macro.fact_inflation_expectations` — breakevens (71 tags/day)
8. **SOV butterflies** → `rates.fact_butterfly` — curve RV
9. **VOLSWAP/VARSWAP** → `equities.fact_equity_vol` — cross-asset hedging (320 tags/day)

**~510 tags/day. Unblocks: RV trades, basis trades, cross-asset hedging.**

### Sprint 3: Macro Context
> *"What's the macro regime?"*

10. **CESI / CITIPAIN / CTOT** → `macro.fact_surprise_index` — select ~100 key tags
11. **FRED connector** → `macro.fact_cpi`, `fact_pce`, `fact_gdp`, `fact_labour`, `fact_fin_conditions`
12. Full inflation swap surface → `macro.fact_inflation_swap`

**Unblocks: regime classification, trade thesis validation.**

### Sprint 4: Positioning & Funding
> *"Who's long, who's short, where's the squeeze risk?"*

13. **CFTC COT/TFF** → `positioning.fact_cftc_cot` / `fact_cftc_tff`
14. **FRED funding** → `funding.fact_fed_rrp`, `fact_tga`, `fact_fed_balance_sheet`
15. **KRW FRA** → `funding.fact_fra_ois`

**Unblocks: positioning overlay, funding stress monitor.**

### Sprint 5: APAC-Specific Gaps
> *"What's happening in China/Japan specifically?"*

16. **China TSF** → `macro.fact_social_financing` — PBoC / Bloomberg
17. **JGB repo** → `funding.fact_repo_jgb` — email parsing
18. **MOVE index** → `equities.fact_move` — Bloomberg
19. **EM sovereign CDS** → `credit.fact_cds_em_sovereign` — Bloomberg

### Sprint 6: Regime Detection
> *"Just tell me what regime we're in"*

20. `regime.fact_regime_indicators` → 20-30 core signals from all above
21. `regime.fact_regime_classification` → daily regime scoring
22. `regime.fact_equity_bond_corr` → the #1 hedge framework signal

---

## Citi Tag Quota Budget

Current daily: ~55-60K tags. Quota: 100K rolling 24h.

| Sprint | New Tags/Day | Cumulative |
|---|---|---|
| Sprint 1 (morning dashboard) | 304 | ~60,304 |
| Sprint 2 (trade construction) | 510 | ~60,814 |
| Sprint 3 (CESI/CITIPAIN subset) | 100 | ~60,914 |
| Sprint 4 (KRW FRA) | 36 | ~60,950 |
| **Total new Citi tags** | **~950** | **~61K** |

Plenty of headroom. The constraint isn't quota — it's building the pipelines.

---

## Confirmed Not on Citi — Don't Re-Explore

Exhaustively probed 2026-03-26. These are dead ends on the Citi Velocity charting API:

| Data | What We Tried | Verdict |
|---|---|---|
| Credit/CDS (CDX, iTraxx, sovereign) | CREDIT, CDS, CDX, ITRAXX, FI, BOND, SPREAD + 6 more | Not on charting API |
| MOVE index | Multiple RATES.* prefixes | ICE/BofA proprietary, Bloomberg only |
| FX deposit rates | FX.DEPOSIT — 50 ccys browsable | Tag tree exists, zero data returns |
| FX NDF points vs USD | FX.FORWARD.FWD_POINT.{CCY}.USD | No USD-quote tags; cross-pairs only (vs JPY) |
| JPY money markets (TONAR) | RATES.MONEY_MARKETS.JPY | Tags exist, all empty |
| European vol indices (V2X, VSTOXX, VDAX) | EQUITY.EQUITY_INDEX | No data |
| China/EM macro data | Various root prefixes | Not on any Citi API |
| EM CB meeting-dated OIS (BOK, RBI, PBoC) | RATES.OIS_MEETING | Only G10 central banks |
