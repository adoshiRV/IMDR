# Citi Velocity — Quant Signal Library

Proprietary and derived signals available from Citi Velocity, organised by how a quantitative macro trader uses them.

- **Explored**: 2026-03-27
- **Total confirmed new tags**: ~40,000
- **DO NOT re-run** — all results documented here

---

## 1. Carry — "What do I earn for holding this position?"

Carry is the most persistent source of return in macro. A systematic carry strategy needs: the carry itself, how it decomposes across tenors, and whether it's being eroded by basis or inflation.

### Schema: `fx`

FX carry is derived from FX forward curves — it lives with FX data. When we build a signals layer later, it can be surfaced there, but the raw data belongs in `fx`.

### FX.CARRY — 15,246 tags — ALL WORKING

**Tag format**: `FX.CARRY.{CCY1}.{CCY2}.{TENOR}.{SIDE}.{FREQ}.CITI`

- 31 base currencies × all cross-pairs
- Tenors: 1M, 3M, 6M, 1Y, 2Y (and more)
- Sides: BID, ASK, MID
- Frequency: ANNUAL (annualised), DAILY (actual daily accrual)

**Sample** (2026-03-26):
| Pair | 1M Carry (ann.) | 1Y Carry (ann.) |
|---|---|---|
| AUD/USD | -0.42% | -0.83% |
| AUD/JPY | implied from above | implied from above |

**Why it matters**: This is the carry you actually earn, computed from Citi's forward curve, after bid/ask. Not a theoretical rate differential — it includes the basis and forward point distortions that eat into carry in practice.

### FX.SWAP — 430 tags — ALL WORKING

**Tag format**: `FX.SWAP.{CCY1}.{CCY2}.{START}.{END}`

IMM-dated FX swap points. Spot→IMM1, IMM1→IMM2, etc.

- 5 base ccys (AUD, EUR, GBP, NZD, USD) × crosses
- Used for: roll cost calculation, forward curve construction, carry decomposition around IMM rolls

**Why it matters**: Swap points move around quarter-end and IMM rolls. If you're rolling a carry trade, this tells you the exact cost. Also a funding stress signal — swap points blow out when USD funding is scarce.

### RATES.INFLATION.INF_CARRY — 180 tags — ALL WORKING

**Tag format**: `RATES.INFLATION.INF_CARRY.{CCY}_CARRY.{INDEX}.{METRIC}.{TENOR}`

- 6 currencies: USD, AUD, DEU, FRA, GBP, ITA
- Metrics: IOTA (inflation option-implied carry), CARRYADJIOTA (carry-adjusted), NETBEICARRY (net breakeven carry), NOMINALYIELDCARRY, REALYIELDCARRY
- Tenors: 2Y, 5Y, 7Y, 10Y, 20Y, 30Y

**Sample** (2026-03-26, USD):
| Tenor | Carry-Adj IOTA | Net BEI Carry | Real Yield Carry |
|---|---|---|---|
| 2Y | 97.5 bp | — | — |
| 5Y | 44.6 bp | — | — |
| 10Y | 33.4 bp | — | — |

**Why it matters**: Tells you whether an inflation breakeven trade carries positively or negatively. A 10Y breakeven might look cheap on level, but if the carry is -30bp/year, you're paying to hold it. This is the signal that separates a good idea from a good trade.

---

## 2. Valuation — "Is this rich or cheap?"

Every macro trade needs a valuation anchor. Without one, you're just trend-following with extra steps.

### Schema: `fx`

FX valuation models — derived from FX data, lives with FX. Signal layer can be built on top later.

### FX.CFV — 21,818 tags — ALL WORKING

**Tag format**: `FX.CFV.{MODEL}.{DM|EM}.{CCY1}.{CCY2}.{METRIC}`

Citi's equilibrium exchange rate models. Five models, each with a different theoretical foundation:

| Model | Full Name | Basis |
|---|---|---|
| **FERM** | Fundamental Equilibrium Rate Model | Current account sustainability |
| **GERM** | Global Equilibrium Rate Model | Weighted average of all models |
| **PPP_PROD_ADJ** | PPP Productivity-Adjusted | Purchasing power parity with Balassa-Samuelson |
| **RER** | Real Exchange Rate | Real effective exchange rate mean-reversion |
| **WERM** | World Equilibrium Rate Model | Global portfolio balance approach |

Metrics per pair: `FAIR_VALUE` (the model's estimate) and `MIS_VALUATION` (% deviation from fair).

**Sample** (2026-03-26, FERM DM):
| Pair | Fair Value | Misvaluation |
|---|---|---|
| AUD/JPY | 97.75 | +12.6% overvalued |
| AUD/CHF | 0.592 | -7.1% undervalued |
| AUD/EUR | 0.584 | +3.0% overvalued |
| AUD/GBP | 0.469 | +10.4% overvalued |

**Why it matters**: This is what Citi's quant FX team uses internally. Five independent valuation models × every pair = a rich signal for mean-reversion strategies. The misvaluation signal is directly tradeable — when misvaluation is extreme, the probability of reversion is historically elevated.

### FX.NEER_IDX — 133 tags — ALL WORKING

**Tag format**: `FX.NEER_IDX.{TYPE}.{CCY}`

Nominal Effective Exchange Rate indices. Trade-weighted currency baskets.

- Types: BROAD (50+ trading partners), NARROW (major partners only), NBI_ASIA, NBI_CEE, NBI_LATAM, NBI_MENA, NBI_SSA

**Sample**: JPY NEER Broad = 76.5 (historically weak), USD NEER Broad = 105.3

**Why it matters**: A currency can strengthen vs USD but weaken on a trade-weighted basis (or vice versa). NEER is the true measure of competitiveness that central banks target. The BOJ watches JPY NEER, not USD/JPY. If you're trading JPY, you need to think in NEER terms.

### FX.REER_IDX — 195 tags — ALL WORKING

Same as NEER but adjusted for relative inflation (real effective exchange rate). JPY REER Broad = 67.9 — the weakest in decades. This is why the BOJ is under political pressure despite not targeting the exchange rate.

### FX.GERM_WEIGHTS — 600 tags — ALL WORKING

**Tag format**: `FX.GERM_WEIGHTS.{DM|EM}.{CCY1}.{CCY2}.{MODEL}.WEIGHT`

The model composition weights inside GERM (which model gets how much weight per pair). Tells you *why* the fair value estimate is what it is.

**Sample**: AUD/USD: PPP = 0.643, PPP_PROD_ADJ = 0.311, WERM = 0.046, FERM = 0, RER = 0.

**Why it matters**: Model transparency. If you disagree with Citi's fair value, you can see which sub-model is driving it and form your own view on the weights.

---

## 3. Risk Regime — "What environment are we in?"

The same trade performs completely differently in risk-on vs risk-off, low vol vs high vol, growth vs inflation regimes. You need to know which regime you're in before doing anything.

### Schema: `regime`

These are regime classification inputs — the exact signals the blueprint's `fact_regime_indicators` table is designed to consume. They don't belong in `macro` (which is economic data) or `signals` (which is trade signals). They belong in `regime` because their purpose is to classify the environment, not to generate trade ideas directly.

### FX.MRICITI — Macro Risk Index — 23 tags — 22/23 WORKING

**Tag format**: `FX.MRICITI.{VARIANT}.{COMPONENT}`

Three variants: EM MRI, Long-term MRI, Short-term MRI.

Components (all normalised 0–1, higher = more stress):
- **MRI_CORPCDS**: Corporate CDS spreads
- **MRI_EMSPR**: EM sovereign spreads
- **MRI_EQVOL**: Equity volatility
- **MRI_FINCDS**: Financial CDS spreads
- **MRI_FIVOL**: Fixed income volatility
- **MRI_FXVOL**: FX volatility
- **MRI_TED**: TED spread (funding)
- **MRI_CORR**: Cross-asset correlation
- **MRI_DCI**: Default correlation index
- **MRI_ESI**: Equity sentiment index
- **MRI_ETF**: ETF flow signal
- **MRI_TL**: Overall (top-level composite)

**Sample** (2026-03-26):
| Component | LT MRI | ST MRI | EM MRI |
|---|---|---|---|
| Overall | 0.731 | — | 0.412 |
| Corp CDS | 0.868 | — | — |
| Equity Vol | 0.907 | — | — |
| Financial CDS | 0.965 | — | — |
| FX Vol | 0.661 | — | 0.777 |
| EM Spread | 0.536 | — | 0.537 |

**Why it matters**: This is a real-time, multi-asset risk barometer decomposed into components. LT MRI at 0.73 with financial CDS at 0.97 tells you the market is pricing significant financial stress even if equity markets look calm. The component decomposition is what makes this actionable — you can see *where* the stress is coming from.

### FX.FXFUI — Fundamental Uncertainty Index — 145 tags — ALL WORKING

**Tag format**: `FX.FXFUI.{TYPE}.{DM|EM}.{CCY}.CITI`

Four sub-indices:
- **CDF**: Current data flow uncertainty
- **FXF**: FX forecast dispersion
- **GDF**: Global data flow uncertainty
- **INF**: Inflation uncertainty

Per currency, DM and EM separately.

**Sample**: GBP CDF = 0.413 (high uncertainty), JPY CDF = 0.084 (low — market is certain about BOJ).

**Why it matters**: Uncertainty ≠ volatility. Vol can be low while uncertainty is high (market is complacent) or vice versa (market is repricing rapidly but direction is clear). This distinction matters for option strategies — sell vol when uncertainty is low, buy when high.

### FX.FXRMI — Global FX Risk Model Index — 34 tags — ALL WORKING

Per-currency risk score. CHF = -0.47 (safe haven bid), BRL = +0.18 (risk-on), USD = +0.04 (neutral).

**Why it matters**: Quick read on which currencies are in risk-on vs risk-off mode. Use as a filter on carry trades — don't run carry in a currency where the risk model is flashing red.

---

## 4. Multi-Factor Scoring — "What does the systematic model say?"

### Schema: `fx`

Citi's systematic FX model output — lives with FX data.

### FX.SC_SCORECARD — 460 tags — ALL WORKING

**Tag format**: `FX.SC_SCORECARD.{TYPE}.{FACTOR_OR_CCY}`

Citi's multi-factor FX scorecard. 32 currencies ranked across 12 factors:

| Factor | What It Measures |
|---|---|
| SC_CARRY | Rate differential / carry attractiveness |
| SC_VALUE | Deviation from fair value (CFV-derived) |
| SC_CTOT | Commodity terms of trade momentum |
| SC_ESI | Economic surprise (data beating/missing expectations) |
| SC_ISI | Inflation surprise |
| SC_GDP | Growth momentum |
| SC_BUDGET | Fiscal balance |
| SC_FERM | FERM model signal |
| SC_FXFC | FX forecast signal |
| SC_POS | Positioning signal |
| SC_RISKCORR | Risk-correlation signal |
| SC_EDC | External debt/current account |

Output types:
- **SC_AVGRANK**: Overall average rank per currency (1 = most bullish, 32 = most bearish)
- **SC_FACTOR.{factor}.{ccy}**: Individual factor score per currency
- **SC_SCORECARD_POS**: Model-implied position direction
- **FLOWPCT.{factor}**: Factor weight / flow percentage

**Sample** (2026-03-26):
| Currency | Avg Rank | Carry | Value | CTOT |
|---|---|---|---|---|
| AUD | 14 (neutral-bullish) | 14 | — | 3 (best) |
| EUR | 17.9 (neutral) | 28 | — | 21 |
| JPY | 20.4 (bearish) | 30 (worst) | — | 31 (worst) |
| USD | 22.4 (bearish) | 18 | — | 26 |

Updates ~weekly (5 data points in 30 days).

**Why it matters**: This is Citi's systematic FX strategy in a box. A quant can use it as: (a) a standalone signal, (b) a factor model to validate their own, (c) a contrarian indicator (fade the model when positioning is extreme), or (d) a factor decomposition to understand what's driving currencies. JPY at rank 30 on carry + 31 on CTOT = the model says sell JPY for fundamental reasons. If you're long JPY, you'd better have a strong thesis for why carry and terms of trade don't matter this time.

---

## 5. EM Early Warning — "Which EM currencies are vulnerable?"

### Schema: `regime`

EM vulnerability scoring is a regime input — it tells you which countries are at risk of crisis, capital flight, or CB intervention. It's not a trade signal (you don't buy/sell based on it directly) and it's not economic data. It's a risk classification.

### FX.CEWS — 491 tags — ALL WORKING (monthly)

**Tag format**: `FX.CEWS.CURRENCY.{CCY}.{FACTOR}`

Citi EM Early Warning System. 25 EM currencies scored across 15 vulnerability factors:

| Factor | What It Measures |
|---|---|
| CEWS_BANKS_SPD | Banking sector stress |
| CEWS_CDS_MOM | Sovereign CDS momentum |
| CEWS_CTOT_MOM | Terms of trade momentum |
| CEWS_ECO_SUP | Economic surprise |
| CEWS_EQTY_YOY | Equity market YoY performance |
| CEWS_EXP_YOY | Export growth |
| CEWS_EXT_FIN | External financing needs |
| CEWS_GBL_RISK | Global risk appetite |
| CEWS_IND_PRD | Industrial production |
| CEWS_LOAN_DEPO | Loan-to-deposit ratio |
| CEWS_LONG_EM | EM positioning (long signal) |
| CEWS_MON_SUP | Money supply growth |
| CEWS_OVERALL | Composite vulnerability score |
| CEWS_REER_MISVAL | REER misvaluation |
| CEWS_SHORT_EM | EM positioning (short signal) |

Also has regional aggregates under `FX.CEWS.REGION`.

**Sample** (CNY):
| Factor | Score |
|---|---|
| Overall | 0.407 (neutral) |
| CTOT Momentum | 0.809 (strong) |
| CDS Momentum | 0.580 (moderate) |
| Economic Surprise | 0.609 (positive) |
| External Financing | 0.207 (low need — safe) |
| Global Risk | 0.230 (benign) |
| REER Misvaluation | 0.161 (slightly undervalued) |

**Why it matters**: For an APAC desk, this is the China/India/Korea vulnerability dashboard. An overall score above 0.7 historically precedes EM FX crises. The factor decomposition tells you *why* — is it external financing (current account crisis) or CDS momentum (credit stress) or REER misvaluation (competitiveness loss)? Each has different implications for which trades to put on or take off.

---

## 6. Forecasts as Contrarian Signals — "What does the street think?"

### Schema: `fx` (FX forecasts), `commodities` (commodity forecasts)

Forecasts live with their respective asset class data.

### FX.FORECAST — 108 tags — ALL WORKING

**Tag format**: `FX.FORECAST.{CCY1}.{CCY2}.FCST_{HORIZON}.CITI`

Horizons: 3M, 6-12M, long-term.

**Sample**: AUD/USD 3M = 0.70 (Citi expects flat), AUD/JPY 3M = 106 (expects AUD strength vs JPY).

Daily updates (31 pts/30d) — you can see when Citi revises their forecasts.

### COMMODITIES.FORECAST — 115 tags — PARTIAL (point prices work)

Point price forecasts (0-3M, 6-12M) confirmed working. Annual/quarterly horizons return no data.

**Sample**: Corn 0-3M = 475, Soybeans 0-3M = 1250.

### RATES.FORECAST — 12 tags — NO DATA in 30d

Fed funds, ECB depo, UST 2Y/10Y, Bund 10Y, Gilt 10Y, JGB 10Y — quarterly + annual. May update less frequently than 30 days.

### EQUITY.FORECAST — 15 tags — NO DATA in 30d

SPX, TOPIX, KOSPI, HSI, ASX, MSCI EM targets. Same — possibly infrequent updates.

---

## 7. Effective Exchange Rates — "What's the true currency move?"

### Schema: `fx`

NEER/REER are trade-weighted FX indices — they live in `fx`. Central banks use them as macro indicators, but the underlying data is FX rates aggregated across trading partners.

### FX.NEER_IDX — 133 tags — ALL WORKING

Trade-weighted nominal indices. Broad (50+ partners) and narrow (majors) baskets, plus regional baskets (Asia, CEE, LatAm, MENA, SSA).

### FX.REER_IDX — 195 tags — ALL WORKING

Same but inflation-adjusted. JPY REER Broad at 67.9 = weakest in decades. This is the number the BOJ governor gets asked about in Diet hearings.

---

## Confirmed Not Working

| Dataset | Tags | Verdict |
|---|---|---|
| FX.CRFI (Risk Factor Index) | 2 | Tags exist, no data |
| FX.LIQUIDITY_IDX | 28 | Tags exist, no data |
| FX.CFWS (Frontier Weights) | 20 | No data |
| FX.XCCY_SWAP | 10,040 | No data (use RATES.XCCY_OIS_SWAP instead) |
| RATES.POS_MON | 32 | No data |
| RATES.FORECAST | 12 | No data in 30d probe |
| EQUITY.FORECAST | 15 | No data in 30d probe |

---

## Tag Budget Impact

| Signal Family | Tags Available | Daily Ingest Estimate |
|---|---|---|
| FX.CARRY (key pairs × tenors) | 15,246 | ~200 (20 pairs × 5 tenors × 2 freq) |
| FX.CFV (key pairs) | 21,818 | ~100 (20 pairs × 5 models) |
| NEER + REER (key ccys) | 328 | ~50 |
| MRI + FXFUI + FXRMI | 202 | ~50 (all — small dataset) |
| SC_SCORECARD (all) | 460 | ~460 (all — weekly, small) |
| CEWS (APAC ccys) | 491 | ~100 |
| FX.FORECAST | 108 | ~108 (all — small) |
| INF_CARRY | 180 | ~50 (USD + AUD + GBP) |
| GERM_WEIGHTS (ref data) | 600 | ~50 (monthly refresh) |
| **Total new** | | **~1,170 tags/day** |

Combined with existing (~61K) = ~62K total. Still well within 100K quota.
