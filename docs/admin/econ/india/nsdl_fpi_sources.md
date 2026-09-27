# India — NSDL FPI Data Sources (Foreign Portfolio Investor flows, holdings & derivatives)

Last updated: 2026-07-14
Status: **SCOPING → Stage 2 connector in build (2026-07-14).** Portal: **https://www.fpi.nsdl.co.in/**

SEBI authorised NSDL to run the **FPI Monitor** — the canonical public source for Foreign Portfolio Investor
**cash flows** (debt + equity), **derivative trades/positions**, **holdings** (Assets Under Custody),
**debt-limit utilisation**, and **ODI/P-Note** values. This is the **real-time capital-account proxy**
for the FCNR / BoP / external-sector thread (wiring-map cell 3.3 Capital Account, coverage-plan A16/A39).

Cross-refs: [in_coverage_plan.md](in_coverage_plan.md) (A16 NSDL FPI, A39 index-inclusion slice) ·
[../macro_economy_wiring_map.md](../macro_economy_wiring_map.md) §7.12 (3.3 Capital Account) ·
[index.md](index.md).

---

## Access constraint (IMPORTANT)

- **`fpi.nsdl.co.in` is BLOCKED from the RV corporate network** for a direct `httpx`/Playwright-launch fetch
  (`RemoteProtocolError` — confirmed corp-firewall block). It loads normally inside the user's ordinary Chrome.
- Therefore the connector uses the **CDP-attach-to-user-Chrome pattern** (same as the AOFM AU fetchers —
  `scripts/econ/au/aofm/*`, `src/imdr/domains/econ/aofm_xlsx.py`; see memory `feedback-aofm-fresh-profile-per-run`).
  The user starts Chrome with a remote-debugging port and the NSDL page open; the fetcher attaches and reads the DOM.
- **Do NOT use the page's "Export to Excel" button** — it breaks the page/session ("ruins the link", user-confirmed
  2026-07-14). Scrape the live **HTML DOM table** instead (also the automatable path).
- Menu page footer shows a stale "Website updated as on: 03 Jul 2026", but **`Latest.aspx` itself is current**
  (served 14-Jul-2026 data on 14-Jul-2026) — trust the report pages, not the footer stamp.

---

## Report menu (Home » FPI Investments)

Crawl-complexity legend per [onboarding_new_country.md](../onboarding_new_country.md): LOW / MED / HIGH / BLOCKED.
All rows are **BLOCKED from corp net → via CDP-attach**; the flag below is the *page shape* once reachable.
Tier per [§H.4](../onboarding_new_country.md): **T1** moves the FX/BoP narrative; **T2** colour; **T3** reference.

| # | Stream (menu label) | URL | Cadence | Content | Shape | Tier | Ingest scope |
|---|---|---|:---:|---|:---:|:---:|---|
| 1 | **Latest** — Daily Trends in FPI Investments | [`/Reports/Latest.aspx`](https://www.fpi.nsdl.co.in/Reports/Latest.aspx) | **Daily** (T+prev) | Cash flows by asset class + derivatives (see structure below) | MED (DOM table) | **T1** | **Stage 2 — primary daily pull** |
| 2 | **Current Month** | (submenu) | Daily, MTD | Month-to-date daily trends | MED | T1 | Stage 2 (MTD reconcile) |
| 3 | **Archive ▸** | (submenu) | Daily history | **Past daily-trends reports by date — the daily-history BACKFILL path** | MED | **T1** | **Stage 2 backfill** |
| 4 | FPI Investment Details (Calendar Year) | [`/Reports/Yearwise.aspx?RptType=6`](https://www.fpi.nsdl.co.in/Reports/Yearwise.aspx?RptType=6) | Annual (CY) | Net investment by asset class, calendar-year history | MED | T2 | backfill aggregate |
| 5 | FPI Investment Details (Financial Year) | [`/Reports/Yearwise.aspx?RptType=5`](https://www.fpi.nsdl.co.in/Reports/Yearwise.aspx?RptType=5) | Annual (FY) | Net investment, financial-year history | MED | T2 | backfill aggregate |
| 6 | Quarterly FPI Net Investment Details (CY) | [`/web/Reports/QuarterlyWise.aspx`](https://www.fpi.nsdl.co.in/web/Reports/QuarterlyWise.aspx) | Quarterly | Net investment, quarterly | MED | T2 | optional |
| 7 | Fortnightly Sector-wise FPI Investment Data | [`/web/Reports/FPI_Fortnightly_Selection.aspx`](https://www.fpi.nsdl.co.in/web/Reports/FPI_Fortnightly_Selection.aspx) | Fortnightly | Equity holdings by SECTOR — sectoral rotation | MED | T2 | optional (sector layer) |
| 8 | **Debt Utilisation Status** | [`/Reports/ReportDetail.aspx?RepID=1`](https://www.fpi.nsdl.co.in/Reports/ReportDetail.aspx?RepID=1) | Daily/periodic | FPI debt-limit **headroom** by route (General / VRR / FAR) — how much room before limits bind | MED | **T1** | **candidate** (FCNR/BoP-adjacent) |
| 9 | **Asset Under Custody (AUC) data ▸** | (submenu) | Monthly | FPI **HOLDINGS/STOCK** by asset class & sector — the investor-base equivalent (cf. Indonesia DJPPR) | MED | **T1** | **candidate** (stock layer) |
| 10 | Monitoring of Utilization of 3% Breach Limit ▸ | (submenu) | Periodic | Single-FPI 3%-of-issue breach monitoring | MED | T3 | skip |
| 11 | Bidding Details | (page) | Event | Debt-limit auction bidding results | MED | T2 | optional |
| 12 | ODI Breach Limit ▸ | (submenu) | Periodic | Offshore-derivative breach monitoring | MED | T3 | skip |
| 13 | Trade-Wise Equity data of FPI | (page) | Daily | Trade-level equity (granular) | MED | T2 | optional |
| 14 | Trade-Wise Debt data of FPI | (page) | Daily | Trade-level debt (granular) | MED | T2 | optional |
| 15 | **Value of ODIs / Participatory Notes (PNs)** | (page) | Monthly | Outstanding **P-Note** value — offshore FPI exposure | MED | **T1** | **candidate** |
| 16 | List of FPIs ▸ | (submenu) | Rolling | Registered-FPI directory | MED | T3 | skip |
| 17 | DDP wise pendency of FPI applications | (page) | Periodic | Registration pipeline | MED | T3 | skip |

---

## `Latest.aspx` table structure (the Stage 2 parse target)

Two tables per day. Values in **₹ Crore** and **US$ million**, plus the day's USD/INR conversion.

**A. Daily Trends in FPI Investments** (cash) — rows = asset class × investment route:
- Asset classes: **Equity · Debt-General Limit · Debt-VRR · Debt-FAR · Hybrid · Mutual Funds · AIFs · Total**
- Investment routes: `Stock Exchange` · `Primary market & others` · `Sub-total` (Mutual Funds split by scheme type; AIFs by route)
- Columns: `Gross Purchases (₹cr)` · `Gross Sales (₹cr)` · `Net Investment (₹cr)` · `Net Investment US$mn` · `Conversion (1 USD→INR)`
- Example (14-Jul-2026): Equity Sub-total Net **−₹2,521.10cr / −$263.07mn**; Debt-General +$15.31mn; Debt-VRR −$35.86mn; Debt-FAR −$29.18mn; Hybrid +$1.33mn; **Total −₹2,972.72cr / −$310.20mn**; conversion ₹95.8336.
- Note: `Net` is shown in parentheses when negative (outflow) — parser must treat `(x)` as `−x`.

**B. Daily Trends in FPI Derivative Trades** — rows = derivative product:
- Products: Index Futures · Index Options · Stock Futures · Stock Options · Interest Rate Futures · Currency Futures · Currency Options · Commodity Futures · Commodity Options
- Columns: Buy (No. of Contracts, Amount ₹cr) · Sell (Contracts, ₹cr) · **Open Interest at end of date** (Contracts, ₹cr)
- Compiled from NSE/BSE/MSEI/NCDEX/MCX; represents the **previous trading day's** position.

**Proposed indicator codes** (`INDIA.NSDL.FPI.*`, vendor NSDL, country IN):
- Cash net flows: `INDIA.NSDL.FPI.{EQUITY|DEBT_GENERAL|DEBT_VRR|DEBT_FAR|HYBRID|MUTUAL_FUNDS|AIF|TOTAL}.NET.{USD_MN|INR_CR}.IN` (daily) — gross purchase/sales optional.
- (Optional) derivatives OI: `INDIA.NSDL.FPI.DERIV.{INDEX_FUT|INDEX_OPT|STOCK_FUT|...}.OI_AMT_INR_CR.IN`.
- (Candidate) holdings: `INDIA.NSDL.FPI.AUC.*` ; debt headroom: `INDIA.NSDL.FPI.DEBT_UTIL.{GENERAL|VRR|FAR}.*` ; P-Notes: `INDIA.NSDL.FPI.ODI_PN.VALUE.IN`.

---

## Historical data — YES, available

- **Daily history** → **Archive ▸** (menu #3): past daily-trends reports selectable by date. This is the backfill
  path for the full daily asset-class breakdown. **Current Month** (#2) gives the running MTD.
- **Aggregate history** → Calendar-Year (#4) / Financial-Year (#5) / Quarterly (#6) net-investment tables, and
  Fortnightly sector-wise holdings (#7) — coarser than daily but longer history.
- **Static fortnightly archive** (no CDP needed?): `…/StaticReports/Fortnightly_Sector_wise_FII_Investment_Data/…`
  surfaced in search — a static-HTML historical dump worth probing.
- Build plan: Stage 2 connector pulls **Latest.aspx daily** (append) + a one-off **Archive backfill** over the
  desired lookback; AUC / Debt-Utilisation / ODI-PN are candidate follow-on streams (holdings + P-Note layers).

---

## Related external sources (cross-check)

- **CDSL** FPI investments: `cdslindia.com/Publications/ForeignPortInvestor.html` (the other depository — partial coverage).
- **SEBI** FPI curation: `sebi.gov.in/curation/fpi.html`.
- **RBI Bulletin T35 Foreign Investment** (already in IMDR) and **T40 BoP FPI line** — the RBI-side monthly/quarterly view; NSDL is the higher-frequency (daily) counterpart.
