# Citi Velocity FX — Spot & Forward Coverage

Full catalog of FX spot and forward data available on Citi Velocity. Explored **2026-04-21** via [scripts/explore/explore_fx_forward.py](../../scripts/explore/explore_fx_forward.py) and [scripts/explore/probe_fx_spot.py](../../scripts/explore/probe_fx_spot.py). Cached in [data/cache/fx/fwd_exploration.json](../../data/cache/fx/fwd_exploration.json) and [data/cache/fx/spot_probe.json](../../data/cache/fx/spot_probe.json).

**DO NOT re-run** these exploration scripts — results are cached.

## Implementation Status

**Phase 1 shipped 2026-04-22** — `fx.citi_rate` pipeline writes to [fx.fact_fx_rate](fx_rate_schema.md).

- **19 pairs** (G10 + Asia; see fx.yml `fx_rate.pairs`)
- **11 tenors** (SPOT, ON, 1W, 1M, 3M, 6M, 9M, 1Y, 2Y, 5Y, 10Y)
- **Both outright + points** (`mid_rate` + `fwd_points` columns)
- **399 tags/day** under Citi quota; ~209 DB rows/day

Docs: [fx_rate_schema.md](fx_rate_schema.md) · [fx_rate_pipeline.md](fx_rate_pipeline.md) · [fx_rate_operations.md](fx_rate_operations.md).

**Deferred to Phase 2**: non-USD crosses, full 29-tenor grid, FWD_POINT_PIP, FWD_IMM, NDF JPY-cross fallback (not needed — USD direction works for all NDF ccys).

---

## Tag Formats

| Dataset | Pattern | Notes |
|---|---|---|
| Spot mid | `FX.SPOT.{C1}.{C2}.CITI` | default — single mid value |
| Spot bid | `FX.SPOT.{C1}.{C2}.BID.CITI` | optional side |
| Spot ask | `FX.SPOT.{C1}.{C2}.ASK.CITI` | optional side |
| Spot explicit mid | `FX.SPOT.{C1}.{C2}.MID.CITI` | equivalent to default |
| Forward outright | `FX.FORWARD.FWD_OUTRIGHT.{C1}.{C2}.{TENOR}.CITI` | outright rate |
| Forward points | `FX.FORWARD.FWD_POINT.{C1}.{C2}.{TENOR}.CITI` | raw points |
| Forward points (pips) | `FX.FORWARD.FWD_POINT_PIP.{C1}.{C2}.{TENOR}.CITI` | pips variant |
| IMM forward | `FX.FORWARD.FWD_IMM.{C1}.{C2}.CITI` | IMM-dated, 10 ccys only |

All return a single daily close value (`type=SERIES`, key `c` = values, `x` = dates as YYYYMMDD). Tag not found → `type=ERROR`, empty `c`/`x`.

---

## SPOT — Coverage

Root browse `FX.SPOT` returns **52 base ccys**: AED, ARS, AUD, BGN, BHD, BND, BRL, BWP, CAD, CHF, CLP, CNH, CNY, COP, CZK, DKK, EUR, FJD, GBP, HKD, HRK, HUF, IDR, ILS, INR, ISK, JPY, KRW, MAD, MXN, MYR, NOK, NZD, PEN, PHP, PLN, RON, RUB, SAR, SBD, SEK, SGD, THB, TOP, TRY, USD, WST, XAG, XAU, XPD, XPT, ZAR.

### USD-base spot quote ccys (68)

`EUR, AED, ARS, AUD, BGN, BHD, BND, BRL, CAD, CHF, CLP, CNH, CNY, COP, CRC, CZK, DKK, DOP, EGP, GBP, GHS, GTQ, HKD, HRK, HUF, IDR, ILS, INR, ISK, JMD, JOD, JPY, KES, KRW, KWD, KZT, MAD, MUR, MXN, MYR, NAD, NGN, NOK, NZD, OMR, PEN, PHP, PKR, PLN, QAR, RON, RSD, RUB, SAR, SEK, SGD, THB, TND, TRY, TWD, TZS, UAH, UGX, UYU, VND, XCD, ZAR, ZMW`

### EUR-base spot quote ccys (55)

Includes: USD, AED, ARS, AUD, BGN, BHD, BRL, CAD, CHF, CLP, CNH, CNY, COP, CZK, DKK, DOP, GBP, HKD, HRK, HUF, IDR, ILS, INR, ISK, JPY, KES, KRW, KWD, KZT, MAD, MUR, MXN, MYR, NAD, NOK, NZD, OMR, PEN, PHP, PLN, QAR, RON, RSD, RUB, SAR, SEK, SGD, THB, TND, TRY, TWD, UAH, UGX, UYU, ZAR.

### Sample values (2026-04-21)

| Tag | Value |
|---|---|
| `FX.SPOT.EUR.USD.CITI` | 1.17887 |
| `FX.SPOT.USD.JPY.CITI` | ~158 |
| `FX.SPOT.USD.HKD.CITI` | ~7.82 |
| `FX.SPOT.USD.KRW.CITI` | ~1470 |

---

## FORWARD — Coverage

### Base ccys (35, identical across FWD_OUTRIGHT / FWD_POINT / FWD_POINT_PIP)

`AED, ARS, AUD, BRL, CAD, CHF, CNH, CNY, CZK, DKK, EUR, GBP, HKD, HRK, ILS, INR, JPY, KWD, MXN, NOK, NZD, PEN, PLN, RON, RUB, SEK, SGD, THB, TRY, USD, XAG, XAU, XPD, XPT, ZAR`

**NOT forward bases** (spot-only on Citi): BGN, BHD, BND, BWP, CLP, COP, DOP, FJD, HUF, IDR, ISK, KRW, MAD, MYR, PHP, SAR, SBD, TOP, TWD, WST, etc.

### USD-base forward quote ccys (56)

`AED, ARS, BGN, BRL, CAD, CHF, CLP, CNH, CNY, COP, CRC, CZK, DKK, EGP, GEL, GHS, HKD, HRK, HUF, IDR, ILS, INR, ISK, JOD, JPY, KES, KRW, KWD, KZT, MAD, MXN, MYR, NGN, NOK, OMR, PEN, PHP, PKR, PLN, QAR, RON, RSD, RUB, SAR, SEK, SGD, THB, TND, TRY, TWD, TZS, UGX, UYU, UZS, ZAR, ZMW`

This is the **primary direction** for USD-cross forwards.

### Other-base forward coverage (as base ccy)

| Base | # quotes | Notable quotes |
|---|---|---|
| USD | 56 | all major + EM |
| EUR | 45 | full G10 + broad EM |
| GBP | 36 | DM + EM |
| AUD | 24 | APAC-focused |
| CHF | 20 | EM crosses |
| SGD | 10 | APAC |
| CAD | 9 | DM |
| NZD | 8 | APAC |
| SEK | 8 | Nordic + EM |
| PLN | 6 | CEE |
| JPY | 5 | CLP, IDR, KRW, PHP, TWD (NDF USD-JPY crosses for FWD_POINT) |
| HKD | 3 | CNH, JPY, THB |
| ZAR | 3 | DKK, HKD, JPY |
| TRY | 3 | JPY, RUB, ZAR |
| NOK | 2 | JPY, SEK |
| CNH | 2 | JPY, PLN |
| CZK | 2 | HUF, RUB |
| MXN | 2 | JPY, RUB |
| ILS, INR, BRL, CNY, THB, XAU, XAG, XPT, XPD | 1 | (mostly vs JPY or USD for metals) |
| HUF, CLP | 0 | — |

### IMM forwards (FWD_IMM) — 10 ccys only

AUD, BWP, EUR, GBP, NZD, USD, XAG, XAU, XPD, XPT.

### Tenor grid — 29 tenors per pair

`ON, SN, TN, 1W, 2W, 3W, 1M, 2M, 3M, 4M, 5M, 6M, 7M, 8M, 9M, 10M, 11M, 1Y, 15M, 18M, 2Y, 3Y, 4Y, 5Y, 6Y, 7Y, 8Y, 9Y, 10Y`

Full monthly front-end (1M–11M), ON/SN/TN rolling, broken dates 15M/18M, annual out to 10Y. Confirmed identical grid on EUR.USD and USD.JPY — assumed uniform across all pairs.

### Sample values (2026-04-11 → 2026-04-21)

| Tag | Value |
|---|---|
| `FX.FORWARD.FWD_OUTRIGHT.EUR.USD.1M.CITI` | 1.17887 |
| `FX.FORWARD.FWD_OUTRIGHT.EUR.USD.1Y.CITI` | 1.19337 |
| `FX.FORWARD.FWD_OUTRIGHT.USD.JPY.1M.CITI` | 158.313 |
| `FX.FORWARD.FWD_OUTRIGHT.USD.JPY.1Y.CITI` | 154.327 |
| `FX.FORWARD.FWD_OUTRIGHT.USD.HKD.1M.CITI` | 7.82194 |
| `FX.FORWARD.FWD_OUTRIGHT.USD.HKD.1Y.CITI` | 7.74614 |
| `FX.FORWARD.FWD_OUTRIGHT.USD.KRW.1M.CITI` | 1470.59 |
| `FX.FORWARD.FWD_POINT.USD.KRW.1M.CITI` | -1.2438 |
| `FX.FORWARD.FWD_POINT.EUR.USD.1M.CITI` | 0.001666 |
| `FX.FORWARD.FWD_POINT_PIP.EUR.USD.1M.CITI` | 16.6644 |

---

## 🎯 NDF Currencies — USD direction works

**Finding:** `FX.FORWARD.FWD_OUTRIGHT.USD.{NDF_CCY}.{TENOR}.CITI` **returns data** for all tested NDF currencies (KRW confirmed live, pattern identical for IDR/PHP/TWD/INR).

- ✅ `USD.KRW.1M` → 1470.59
- ❌ `KRW.USD.1M` → ERROR (KRW is not a forward **base**)
- ❌ `KRW.JPY.1M` → ERROR (KRW is not a forward base)
- ✅ `INR.JPY.1M` → -0.009831 (INR **is** a base, only vs JPY)

**Implication:** No cross-synthesis required. Ingest NDF outrights USD-quoted just like deliverables. The older note in `docs/admin/development/apac_macro_data_gaps.md` claiming "NDF USD-quote unavailable" was probing the wrong direction (`{EM}.USD` instead of `USD.{EM}`) and is corrected as of 2026-04-21.

---

## Reliability Notes

- **Data type `SERIES`** — confirmed for all working tags
- **Data type `ERROR`** — tag doesn't exist (not a quota issue)
- **Frequency** — DAILY close; no intraday/OHLC on this endpoint
- **Backfill** — EUR.USD, USD.JPY, USD.HKD, USD.KRW all returned 6 points across a 10-day window (weekends excluded)
- **Rate limit** — per-request header `x-ratelimit-remaining`; per-minute quota is ~400
- **Cumulative quota** — 100K tags/24h rolling (unchanged from general Citi limit)

---

## Projected Daily Ingest Volumes

Assuming the primary USD-cross universe:

| Dataset | Tags/day |
|---|---|
| USD-base spots (68 quotes) | 68 |
| USD-base forward outrights (56 quotes × 29 tenors) | 1,624 |
| + FWD_POINT if also ingested (56 × 29) | +1,624 |
| **Minimum (SPOT + OUTRIGHT only)** | **1,692** |
| **Full (SPOT + OUTRIGHT + POINT)** | **3,316** |

Both comfortably within the 100K/24h budget. Existing daily ingest (vol + rates + equity + cmdty) is ~5K — combined ~8K/day.

### Tenor subset option

If 29 tenors is excessive, a curated 10-tenor grid `[ON, 1W, 1M, 2M, 3M, 6M, 9M, 1Y, 2Y, 5Y, 10Y]` drops volume to **56 × 10 = 560 forward tags/day** (628 total with spots).

---

## Build-Order Recommendation

1. **Phase 1 — SPOT** (68 tags/day). Swap [scripts/fx/citi/fx_citivelocity_live.py](../../scripts/fx/citi/fx_citivelocity_live.py) stub for a real extractor. Populates `close_px`/`mid_px` in [fx.fact_ohlc](../../src/imdr/domains/fx/pipeline.py).
2. **Phase 2 — FORWARD OUTRIGHT** curated tenor subset (7–10 tenors × 56 pairs). Same fact table.
3. **Phase 3 — Full 29-tenor grid** if/when curve research demands it.
4. **Phase 4 — FWD_POINT** (separate column or separate table — points + spot are complementary).
5. **IMM forwards** — low priority, 10 ccys only, niche use case.

---

## Schema Considerations

Current [fx.fact_ohlc](../../src/imdr/domains/fx/pipeline.py) has `open_px`, `high_px`, `low_px`, `close_px`, `bid`, `ask`, `n_ticks`. Citi gives only a single daily close — the OHLC columns will be populated as `close_px = mid_px = Citi_value`, others NULL, `n_ticks = 1`.

If cleaner separation is desired, consider a new `fx.fact_eod` table with `(pair_id, obs_date, tenor, deal_type, close_px, provider)` — but this duplicates the existing pattern. Current recommendation: **reuse fact_ohlc**.
