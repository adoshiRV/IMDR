# MOF — `playground/econ/jp/mof/`

**Status:** trade fetcher built (2026-06-23); JGB issuance + holder fetchers built (2026-07-10). Three fetchers, three distinct MOF sub-portals.

## `fetch_trade.py` — Trade Statistics (財務省貿易統計), cell 1.3

Ministry of Finance Trade Statistics — cell 1.3 External Demand.

### Mechanism
- **MOF Customs time-series flat CSVs** (NOT e-Stat): `https://www.customs.go.jp/toukei/suii/html/data/{stem}.csv`
- File list: `…/toukei/suii/html/time.htm` (JP) / `time_e.htm` (EN labels).
- **Shift-JIS (cp932); unit = thousand yen; monthly from 1979/01** (partner totals from 1988/01).
- Helper `_mof_common.py`; fetcher `fetch_trade.py`; probe `probe_trade_meta.py` (documents the e-Stat dead-end).

### Series (17 indicators, ~9,224 obs)
- **World**: exports / imports / balance (`d41ma.csv`); balance derived = exp−imp.
- **Regions**: Asia, North America, Western Europe, EU, ASEAN — exports + imports (`d42maNNN.csv`, clean `Exp-Total`/`Imp-Total` cols).
- **Partners**: US + China — exports + imports (`d52maNNN`/`d62maNNN.csv`, col 1 = 総額 grand total).
- `imdr_code = MOF.TRADE.{DETAIL}.JP`, `category="bop"`, `unit="jpy_thousand"`, MONTHLY.

Apr-2026 verified: world exports ¥10.51tn, imports ¥10.21tn, balance +¥0.30tn; China deficit, US surplus, Asia largest. ✓

### Gotchas (encoded in parser)
1. **Future-month placeholders** — rows 2026/05–12 pre-filled with `0` (region files) or `-` (partner files); parser drops both so latest = real (Apr-2026).
2. **Country sub-columns inside region files lag** — single countries (US/China) sourced from dedicated partner files, not region sub-columns.
3. **Two layouts** — region files clean (`Years/Months,Exp-Total,Imp-Total`); partner files multi-row commodity header with 総額 in col 1. Header located by content, not offset.

### Next moves
- Add value/volume **price indices** (貿易指数) if needed for cell 3.1 (BoJ CGPI export/import price already covers ToT).
- `category="bop"` per convention — flag at promotion if a dedicated trade category is wanted.

---

## `fetch_jgb_issuance.py` — JGB Issuance Plan (Debt Management Highlights PDF), NEW 2026-07-10

JGB supply side: how much the MOF auctions per fiscal year by tenor. Cells 1.2 (fiscal supply) and 4.3 (financial conditions — duration supply).

### Mechanism
- **Source:** MOF "Highlights of FY{YYYY} Debt Management Policy" PDF at `mof.go.jp/english/policy/jgbs/debt_management/plan/highlight{YYMMDD}.pdf`. The latest (FY2026, announced 26 Dec 2025) is `highlight251226.pdf`. Plan index: `.../plan/index.htm`; historical archive: `.../plan/historical_jgb.htm` (backfill = follow-on).
- **Parse:** PyMuPDF (`fitz`) extracts page-1 text; fetcher locates each tenor label and reads the next two numeric tokens (FY(n-1) supplementary budget + FY(n) initial). Anchor assertions: 10Y FY2026 = 31.2tn (±0.05), coupon 2–40Y subtotal = 112.2tn (±0.3) — fail-loud on layout drift.
- **Cadence:** ANNUAL. `obs_date` = fiscal-year start (Apr 1). Two fiscal years per PDF (prior + new).
- **Output:** 9 indicators / 17 obs. `MOF.JGB_ISSUANCE.{2Y,5Y,10Y,20Y,30Y,40Y,TBILL,HOUSEHOLD}.CALENDAR_BASE.JP` + derived `MOF.JGB_ISSUANCE.COUPON_2_40Y.CALENDAR_BASE.JP`. Unit = `jpy_tn`. Category = "other".

### FY2026 Initial values (¥ trillion)
2Y 33.6 · 5Y 30.0 · 10Y 31.2 · 20Y 8.4 · 30Y 7.2 · 40Y 1.8 (coupon 2–40Y subtotal 112.2) · T-Bills 40.8 · retail 5.9.

---

## `fetch_jgb_holders.py` — JGB Holder Breakdown (Flow of Funds PDF), NEW 2026-07-10

JGB demand side: who holds the outstanding stock by investor sector. Relates to cells 4.2 (balance sheets) and 4.3 (financial conditions).

### Mechanism
- **Source:** MOF "Breakdown by JGB and T-Bill Holders" PDF at `mof.go.jp/english/policy/jgbs/reference/Others/holdings01.pdf` (refreshed ~quarterly; backed by BoJ Flow of Funds data).
- **Parse:** PyMuPDF page-1 text. Three blocks in the PDF: JGB / T-Bill / combined. Parser reads only the **JGB block** (ends at first "Fiscal Loan Fund" row, which is T-Bill-only). Extracts (label, value, pct) triplets; maps label keyword → sector slug. Anchor: BoJ share must be > 40%.
- **Cadence:** QUARTERLY. `obs_date` = quarter-end (parsed from title, e.g. "Mar. 2026").
- **Output:** 19 indicators / 19 obs (single quarter as of latest PDF). `MOF.JGB_HOLDER.{BOJ,BANKS,INSURANCE,PUBLIC_PENSIONS,PENSION_FUNDS,FOREIGNERS,HOUSEHOLDS,GENERAL_GOVT,OTHERS}.{VALUE,SHARE}.JP` + `MOF.JGB_OUTSTANDING.TOTAL.JP`. VALUE unit = `jpy_tn`, SHARE unit = `pct`. Category = "other".

### Mar-2026 snapshot
Total JGB outstanding ¥1,013.8tn. BoJ ¥485.4tn (47.9%) · Insurance ¥155.3tn (15.3%) · Banks ¥149.7tn (14.8%) · Foreigners ¥82.0tn (8.1%) · Public Pensions (≈GPIF) ¥73.4tn (7.2%) · Pension Funds ¥31.7tn (3.1%).
