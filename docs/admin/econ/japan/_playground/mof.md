# MOF (customs trade) — `playground/econ/jp/mof/`

**Status:** trade fetcher built (2026-06-23). The **live monthly trade source** — e-Stat's MOF tables are commodity-by-country detail only (yearly/confirmed), not the timely headline.

Ministry of Finance Trade Statistics (財務省貿易統計) — cell 1.3 External Demand.

## Mechanism
- **MOF Customs time-series flat CSVs** (NOT e-Stat): `https://www.customs.go.jp/toukei/suii/html/data/{stem}.csv`
- File list: `…/toukei/suii/html/time.htm` (JP) / `time_e.htm` (EN labels).
- **Shift-JIS (cp932); unit = thousand yen; monthly from 1979/01** (partner totals from 1988/01).
- Helper `_mof_common.py`; fetcher `fetch_trade.py`; probe `probe_trade_meta.py` (documents the e-Stat dead-end).

## Series (17 indicators, ~9,224 obs)
- **World**: exports / imports / balance (`d41ma.csv`); balance derived = exp−imp.
- **Regions**: Asia, North America, Western Europe, EU, ASEAN — exports + imports (`d42maNNN.csv`, clean `Exp-Total`/`Imp-Total` cols).
- **Partners**: US + China — exports + imports (`d52maNNN`/`d62maNNN.csv`, col 1 = 総額 grand total).
- `imdr_code = MOF.TRADE.{DETAIL}.JP`, `category="bop"`, `unit="jpy_thousand"`, MONTHLY.

Apr-2026 verified: world exports ¥10.51tn, imports ¥10.21tn, balance +¥0.30tn; China deficit, US surplus, Asia largest. ✓

## Gotchas (encoded in parser)
1. **Future-month placeholders** — rows 2026/05–12 pre-filled with `0` (region files) or `-` (partner files); parser drops both so latest = real (Apr-2026).
2. **Country sub-columns inside region files lag** — single countries (US/China) sourced from dedicated partner files, not region sub-columns.
3. **Two layouts** — region files clean (`Years/Months,Exp-Total,Imp-Total`); partner files multi-row commodity header with 総額 in col 1. Header located by content, not offset.

## Next moves
- Add value/volume **price indices** (貿易指数) if needed for cell 3.1 (BoJ CGPI export/import price already covers ToT).
- `category="bop"` per convention — flag at promotion if a dedicated trade category is wanted.
