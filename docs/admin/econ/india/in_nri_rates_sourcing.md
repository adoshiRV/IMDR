# India — NRI/FCNR flows + "actual rates" sourcing (scoping)

Scoping note created 2026-06-18 in response to the desk ask: *"FCNR flows +
actual rates data + anything related."* Companion to
[`in_coverage_plan.md`](in_coverage_plan.md). The flows side is being built
from the RBI Monthly Bulletin; this note scopes the **rates** side, which
is only partly in the Bulletin.

## 1. What the RBI Bulletin actually carries

A full sweep of all 58 May-2026 Bulletin "Current Statistics" tables
(harness: [`playground/econ/in/rbi/rbi_flows_rates_smoke.py`](../../../../playground/econ/in/rbi/rbi_flows_rates_smoke.py))
shows:

**Flows (non-resident + external) — all additive, none currently in IMDR:**
- **T34 Non-Resident Deposits** — FCNR(B) / NR(E)RA / NRO, Outstanding + Flows (US$ mn). ← the headline ask.
- T35 Foreign Investment Inflows · T36 Outward Remittances (LRS) · T38 External Commercial Borrowings
- T40/41 Overall BoP · T42/43 Standard Presentation of BoP · T44 International Investment Position

**Money-market rates — additive:**
- T26 T-Bill auction cut-offs (yields) · T27 Daily Call Money · T28 Certificates of Deposit (amount + rate range) · T29 Commercial Paper (amount + rate range) · T25 T-Bill ownership · T30 Market turnover · T3 LAF liquidity ops · T5 Standing Facilities

**Already covered better elsewhere (skip — dedupe):** T33 FX Reserves (DBIE weekly 2015→ beats Bulletin's ~6-week snapshot), T37 NEER/REER (BIS 1994→), T40 BoP + T27 call money (already in the playground bulletin fetcher).

## 2. The gap: FCNR / bank deposit interest *rates* are NOT in the Bulletin

There is **no FCNR-deposit-rate or bank deposit/lending-rate table** in the
Bulletin Current Statistics. Two distinct concepts, two different sources:

### 2a. FCNR(B) deposit rate **ceilings** — regulatory, event-based
- RBI caps FCNR(B) rates at comparable-maturity **ARR (Alternative Reference
  Rate, e.g. SOFR for USD) + a spread ceiling**. Banks price *within* the cap;
  actual rates vary by bank / currency / maturity.
- The ceiling is set by **RBI circular / Master Direction on Interest Rates
  on Deposits**, changed occasionally (e.g. temporarily widened to ARR+400bp
  1-3y / ARR+500bp 3-5y in Dec-2024, reverted Apr-2025). This is a **policy
  event log, not a statistical series**.
- **Source path**: RBI notifications page (`rbi.org.in/Scripts/NotificationUser.aspx`)
  filtered to the deposit-rate Master Direction + amendments. Fits the
  coverage plan's T1 "Notifications — FCNR/NRI/FPI/ECB regulatory windows"
  event tier. **Recommendation: build later as a circular watcher, not a
  fetcher.** Actual per-bank FCNR rates are not centrally published → out of
  scope (would need bank-by-bank scraping).

### 2b. Bank deposit/lending rates (WALR / WADTDR) — proper monthly series
- **WADTDR** = Weighted Average Domestic Term Deposit Rate; **WALR** =
  Weighted Average Lending Rate. Published **monthly** by RBI for the banking
  system. These are the real "actual bank rates" series.
- **Source path**: RBI **DBIE** (Statistics → Financial Sector → Key Rates /
  Interest Rates). Reachable either via the DBIE JSON gateway (same family as
  the working `dbie_foreignExchangeReserves` endpoint — see
  [`playground/econ/rbi/discovery/findings.md`](../../../../playground/econ/rbi/discovery/findings.md))
  or the SAP-BO report path. Medium effort: one reportId/endpoint discovery.
- **Quick-check first**: Bulletin **T1 "Select Economic Indicators"** may
  carry headline repo + WALR/WADTDR + deposit rate — if so, that's a
  zero-extra-source win folded into the bulletin build. (Flagged for the
  build to verify against the cached `T1.xlsx`.)

## 3. Recommendation summary

| Want | Source | Effort | This round |
|---|---|---|---|
| FCNR(B)/NRE/NRO flows + stock | Bulletin T34 | done (parser built) | **build** |
| FII / LRS / ECB / IIP flows | Bulletin T35/36/38/44 | low–med | **build** |
| Money-market rates (T-bill yields, CD/CP, call, LAF) | Bulletin T26/28/29/3/25/30/5 | med | **build** |
| WALR / WADTDR bank rates | DBIE (or T1 if present) | med (1 endpoint) | **scope** → discover reportId |
| FCNR rate ceilings | RBI circulars (event log) | low, but event-shaped | **defer** → circular watcher |

DBIE is the only **longer-history** path (FCNR monthly 1997→ via reportId 417;
WALR/WADTDR monthly) — the Bulletin gives only a handful of recent periods per
release and builds history by monthly append.

## 4. DBIE reportId 417 — build status (PROMOTED + LOADED + WIRED 2026-06-24)

`scripts/econ/in/rbi/rbi_dbie_nri_deposits.py` — promoted from playground,
loaded to `econ.fact_indicator` (792 obs), and wired into
`scripts/econ/in/in_monthly.py` (PIPELINES, just before `rbi_bulletin` — both
need headed Chrome). Codes `INDIA.DBIE.NRI_DEPOSITS.{NRI_TOTAL|FCNRB|NRERA|NRO}.{OUTSTANDING|FLOW}.IN`
(parallel prefix to the T34 `INDIA.RBI_BULLETIN.NRI_DEPOSITS.*` series — no
clobber). 29 parser unit tests at
`tests/unit/test_econ/test_rbi_dbie_nri_deposits_parser.py`. Requires a
display-equipped host (SAP-BO refuses headless).

Access path: DBIE Home → search "NRI Deposits" → click monthly leaf. The
"50 Macroeconomic Indicators" panel (`#/dbie/indicators`) does NOT carry this
report; it is under `Publication > Time-Series Publications > External Sector`.

Smoke results: 8 indicators (NRI_TOTAL/FCNRB/NRERA/NRO × OUTSTANDING/FLOW),
99 obs per series, date range 2018-02-01 → 2026-04-01, unit usd_mn.
FCNR(B) Outstanding Mar-2026 = 33,755.91 vs T34 anchor 33,756 — diff: -0.09
(PASS). SAP-BO currently renders ~99 months; full 1997 history requires
SAP-BO pagination (page navigation controls or export button — not yet built).
Parquet written under `data/econ/in/rbi/dbie_nri_deposits/`.
