# MHLW (wages) — `playground/econ/jp/mhlw/`

**Status:** wages fetcher built (2026-06-23). Cell 2.3 Domestic Costs.

Monthly Labour Survey (毎月勤労統計調査) — total cash earnings + nominal/real YoY.

## Mechanism — e-Stat **file-catalog**, not getStatsData
The entire Monthly Labour Survey in e-Stat's `getStatsData`/`getMetaInfo` API (statsCode `00450071`, ~552 tables) is **frozen at the 2018 re-benchmark — every table's time axis ends 2009-2015** (verified across the newest monthly tables; the prior `0003138108`=Nov-2015 finding generalises).

The live machine-readable series is the e-Stat **file catalog** ("長期時系列表 / 実数・指数累積データ"), discovered via the `getDataCatalog` REST endpoint. Two CSVs with stable URLs:

| CSV | statInfId | content |
|---|---|---|
| 実数 (actual ¥) | `000032189776` | total / scheduled / overtime cash earnings (JPY/month) |
| 指数・伸び率 | `000032189777` | nominal index (2020=100) + YoY % + real-wage YoY % |

URL: `https://www.e-stat.go.jp/stat-search/file-download?statInfId={id}&fileKind=1`. **Gotcha: body is Shift-JIS (cp932)** despite a `charset=UTF-8` header. Helper `_common.py`; fetcher `fetch_wages.py`.

## Series (6 indicators, ~2,574 obs)
`MHLW.WAGES.{DETAIL}.JP`, scope = 調査産業計 (all industries), 5人以上 establishments (規模=`T`), 就業形態計. `category="labour"`, MONTHLY.
- CASH_EARNINGS_TOTAL ¥318,563 · SCHEDULED ¥292,612 · OVERTIME ¥20,441 (Mar-2026, ¥/month)
- CASH_EARNINGS_YOY +3.1% · SCHEDULED_YOY +3.3% · REAL_YOY +1.4%
- History: actuals 1990→, YoY/real 1991→. Sanity ✓ (nominal +3.1% in the +2-3% band; real near-zero/slightly positive).

## Gotchas / promotion notes
- Scope discriminator: 規模=`T` (5人以上) verified by cross-checking jisuu-derived YoY against the published 伸び率 (size-`T` matches +3.1%; size `0`=30人以上 differs).
- These cumulative CSVs are **確報 (final)** values, lagging the **速報 (preliminary)** by ~1 month (so "latest" sits ~3 months back). Preliminary 概況 is PDF/Excel only.
- `statInfId` is tied to a monthly release — **re-query `getDataCatalog(statsCode='00450071', dataType='CSV')` at promotion** rather than hard-coding IDs.
