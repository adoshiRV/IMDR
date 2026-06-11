# India (IN) — coverage plan (RBI DBIE / RBI CIMS / MOSPI / DGCIS / MoF / BIS)

Last updated: 2026-06-11

Maps every India (IN) cell of the
[macro_economy_wiring_map.md §7.12](../macro_economy_wiring_map.md#712-india-in)
to specific vendor identifiers per source agency.

This is the **scoping plan** for filling `econ.dim_indicator` India rows — as of
2026-06-09 there are **0 indicators × 0 observations** loaded in
`econ.fact_indicator` for IN. 36 series are discovered-but-unloaded in
`playground/econ/rbi/sample_output/2026/` (FX 5 + Bulletin 31).

**Scope (per user 2026-06-09):**
- **RBI** — both DBIE (legacy SPA, partial discovery complete) AND CIMS (10
  successor portals, unprobed). Dual-ingest as insurance against DBIE
  deprecation.
- **MOSPI** — CPI / IIP / NAS / GDP / ASI / PLFS. No public API; XLSX + PDF
  release scraping.
- **DGCIS** — Foreign-trade statistics at HS-chapter and partner-country
  granularity. No public API; XLSX scraping.
- **MoF / Budget Division / CGA / BTr-equivalent** — central-govt fiscal
  realisations.
- **BIS + FRED OECD mirror** — fallback for REER / NEER / credit-to-GDP and
  headline series.

**Critical gotcha — read before adding new RBI fetchers**: the DBIE `authorization`
header value captured 2026-06-03 (`gjl6p01780417269959196`) ends in an
epoch-microseconds timestamp. It worked in fresh httpx calls shortly after
capture but may rotate per-session or per-day. If auth fails, replay the
`security_generateSessionToken` + `login_getSapToken` bootstrap flow seen in
[`playground/econ/rbi/discovery/dbie_payloads.json`](../../../playground/econ/rbi/discovery/dbie_payloads.json).
All DBIE endpoints respond **POST only**, with a `{"body": {...}}` envelope, and
return **HTML-escaped JSON** — must call `html.unescape(text)` before parsing.

**DBIE → CIMS migration**: DBIE is being phased out across 10 CIMS portals
(BoP, FLAIR, SMS, FED, CISBI, FIRMS + 4 more). No firm deprecation date.
Dual-track plan: ship DBIE-based fetchers first (faster), probe + port each
endpoint to CIMS in parallel, switch the read side over per-portal as CIMS
stabilises. See [_playground/rbi.md](_playground/rbi.md) for current state.

## What's left to fetch — prioritized punch list (2026-06-11)

This is the operational checklist. Each row maps to an A/B-item further down; the **Group** column tags the gating infra (so you can attack a whole group at once instead of cherry-picking).

### Tier 1 — high-value, infra not yet built (the big remaining unlocks)

| # | Series / corpus | Cell | Group | Est. indicators | Effort |
|---|---|---|---|---:|---|
| A2-A7 | RBI DBIE expansion — Bulletin tables · BoP · External Debt · NIIP · NRI/**FCNR(B)**/NRE/NRO · ECB · RBI sale/purchase USD · forward book · Sectoral Deployment · Money Market · Daily LAF · IESH · OBICUS · SPF · Consumer Confidence · Corporate sector · Banking BSR-1/2 · NBFC stats · GNPA/NNPA/CRAR | 1.1 · 1.2 · 3.2 · 3.3 · 4.1 · 4.2 · 4.3 | **DBIE Playwright discovery** (1 session captures all leaves) | ~80-120 | M |
| A17 | CCIL feed — MIBOR · MIFOR · FBIL onshore fwd premia · G-Sec 1Y/5Y/10Y · corp bond curve · OIS curve | 4.3 | **Credentials** (desk has terminal login; need machine-readable creds) | ~25 | S once creds land |
| ~~A13~~ DGCIS multi-month loop | **done 2026-06-11** — built at [`playground/econ/in/dgcis/dgcis_trade.py`](../../../playground/econ/in/dgcis/dgcis_trade.py); see § "A13 end-to-end log" below | 1.3 · 3.1 | n/a | 198 indicators (98 chapters + TOTAL × 2 dirs), ~29k obs Apr 2014 → today | ✅ |

### Tier 2 — corp-firewall-blocked from `rvsg-fs01` (CDP-attach to user's daily Chrome, AOFM pattern)

| # | Series | Cell | Notes |
|---|---|---|---|
| A16 | NSDL FPI flows (debt + equity, daily) | 3.3 | `RemoteProtocolError` from our net; same family as AOFM |
| A39 | NSDL FPI index-inclusion slice (GBI-EM eligible / Bloomberg EM eligible) | 3.3 | derivable from A16 once unblocked |
| A18 | Labour Bureau CPI-IW · CPI-AL · WRI (Wage Rate Index) | 2.3 | `ConnectError`; RBI Bulletin carries CPI-IW as fallback |
| A20 | EPFO monthly payroll release | 1.1 · 1.4 | formal employment proxy |
| A25 | CWC reservoir levels (4 zones weekly) | Cluster 4 (agri) | 401 from our net |
| A27 | POSOCO national power demand (daily peak + energy met) | Cluster 3 (activity) | site moved? `grid-india.in` candidate |
| A29 | MGNREGA spend + person-days (weekly) | Cluster 4 (rural distress) | `nrega.nic.in` |
| A33 | Agmarknet mandi prices (~3,000 mandis × ~300 commodities, daily) | 2.4 (CPI food leading) | 403 UA-blocked |
| A44 | GST e-Way Bill volumes (monthly + daily) | 1.3 · Cluster 1 | `ewaybillgst.gov.in` |

### Tier 3 — SPA / deep-Playwright (click-through + form submit per vendor)

| # | Series | Cell | Notes |
|---|---|---|---|
| A15 | DPIIT FDI quarterly inflows | 3.3 | Next.js SSR; `_next/data` returns HTML; needs `wait_for_selector` |
| A28 | NHB Residex + RBI HPI quarterly (50+ cities) | 4.2 · housing | quarterly publication |
| A32 | FCI food stocks (rice + wheat buffer vs norm) | Cluster 4 | JS-rendered |
| A34 | DPIIT PLI scheme commitments + sanctioned investment + actual deployment | 1.4 · Cluster 11 | scheme-specific dashboards |
| A35 | DIPAM disinvestment proceeds | 1.2 fiscal | event-driven |
| A36 | Ministry of Tourism FTA monthly | Cluster 9 (external) | services credit context |
| A37 | NBFC sector aggregates (quarterly, RBI FSR annex) | 4.2 | also under A7 via DBIE |
| A38 | IBBI quarterly newsletter — insolvency cases | 4.2 corporate stress | refinancing wall proxy |
| A40 | DoF / FAI fertilizer prices monthly | 2.1 input costs | subsidy dashboard |
| A43 | SIAM auto sales (PVs + 2W + tractors) | 1.1 private demand | industry assoc, login-gated |

### Tier 4 — PDF parsing pipeline (downloads tested ✓ on 237 PDFs / 250 MB harvested)

These need the PDF→Markdown→Qdrant pipeline (migrations 086/087 done; pipeline scaffold in [`playground/econ/in/govt/ingest_filings.py`](../../../playground/econ/in/govt/ingest_filings.py)):

- **Data series stuck in PDFs**: A11 MOSPI PLFS (LFPR/unemp/WPR) · A19 PPAC monthly Flash Reports + Indian Crude Basket · part of A26 DAC sowing
- **Event corpora**: B1-B8 RBI (MPC resolutions · MPC minutes · MPR · FSR · Bulletin "State of the Economy" · Annual Report · Notifications · Speeches) · B9-B11 Union Budget · Economic Survey · DEA Mid-Year · B12 CGA press · B13 Borrowing calendar · B14 GST monthly (PIB encrypted titles) · B17 DPIIT FDI policy notifications · B20 PLI launches · B21 MSP announcements · B22 IMD seasonal forecasts · B23 CBIC customs notifications

### Tier 5 — quick light additions (<30 min each, no infra needed)

| # | Series | Cell | Notes |
|---|---|---|---|
| ~~A26~~ DAC crop sowing | Cluster 4 | `agricoop.gov.in` **corp-firewall blocked** 2026-06-11. Path forward: **UPAg via Plotly Dash** — see § "UPAg unlock" below |
| ~~A30~~ PM-KISAN | 1.2 fiscal | likely needs PIB press archive (reachable) — defer to govt-filings Korea-pattern |
| ✅ **A31 MSP levels** | Cluster 4 | **DONE 2026-06-11** via UPAg Plotly Dash (`mip-msp-data2` callback prefix). 28 crops × 14 FYs (2013-14 → 2026-27) × 353 obs at [`playground/econ/in/upag/upag_msp.py`](../../../playground/econ/in/upag/upag_msp.py). Wheat 2026-27 ₹2,585 ✓ |
| ~~A42~~ Baltic Dry | Cluster 12 | **Not on FRED** — all candidates (BDIY/DEXBDIY/MAXNGUSDM/IXSPSMOCN) return 404. Baltic Exchange is a commercial index; only via Bloomberg terminal feed |
| B15 | SEBI board outcomes (bond-market structure events) | 3.3 | document corpus |
| B16 | IRDAI board outcomes (insurance G-Sec demand) | 4.2 | document corpus |
| B18 | ECI election dates | Cluster 11 | event corpus |
| B19 | GST Council meeting outcomes | 1.2 fiscal · Cluster 6 | event corpus |

### UPAg unlock (new path for A26 + A31 + A33, 2026-06-11)

[`upag.gov.in`](https://upag.gov.in/) — **Unified Portal for Agricultural Statistics**, run by DoEcSt of MoAg — is the consolidated reachable replacement for the firewall-blocked DAC/CACP/Agmarknet sources. Verified reachable from `rvsg-fs01` while `agricoop.gov.in` / `cacp.dacnet.nic.in` / `farmer.gov.in` / `ppms.nic.in` are all DNS-blocked.

Two distinct UPAg surfaces, **both reachable**:

| Surface | Endpoint | Auth | Use for |
|---|---|---|---|
| **UPAg Data Share API** (documented) | `data.upag.gov.in/api/v1/...` — OpenAPI/Redoc at `data.upag.gov.in/redoc`, spec at `/api/v1/openapi.json` | login required (`POST /v1/upag/api-data-share/login`) | 7 documented endpoints: `apy/statewise`, `crop/production`, `crop/master`, `sources/{name}`, etc. Credential-gated. |
| **UPAg Plotly Dash reports** (undocumented but un-gated) | `dash.upag.gov.in/_dash-update-component` POST with reportID-bound payload | **none observed** — SPA loads without login | Each report page (`upag.gov.in/dash-reports/{slug}?rtype=dashboard`) is a Plotly Dash app. Examples discovered:<br>• `mipmspstatement` (MSP, reportID=52) → A31<br>• `progressivecropareasown` → A26<br>• `apymajorstates` → A26 expansion<br>• `desdistrictwisecompletedatasetreport` → A26 district-level |

Plotly Dash callback contract: POST `/_dash-update-component` with `{"output":..., "inputs":[...], "state":[...], "changedPropIds":[...]}` returns Plotly figures + table data as JSON. Captured initial-page-load payload at [`playground/econ/rbi/discovery/upag_msp_xhrs.json`](../../../playground/econ/rbi/discovery/upag_msp_xhrs.json); next session: trigger the *data* callback (user-interaction simulation in Playwright, capture the body, then replay via httpx).

**Coverage UPAg unlocks** when fetcher built:
- **A26 DAC sowing** — Progressive Crop Area Sown report (weekly during Kharif Jun-Sep + Rabi Oct-Mar) + APY State/District tables (annual, ~15 crops × 30 states × 20+ years history)
- **A31 MSP levels** — Commodity-wise MSP statement (~22 crops × annual since 2000)
- **A33 Agmarknet** (partial) — "Market Intelligence" section likely carries mandi-prices aggregates (needs probing)
- **Cluster 4 (agriculture)** — full coverage path, was previously thought blocked

Estimated end-to-end build: ~2-3hr for the Plotly Dash callback decoder (Playwright captures data-callback payload → reproduce via httpx → parse Plotly figure JSON → emit IndicatorRow/ObservationRow). Single decoder unlocks all 30+ UPAg Dash reports.

#### UPAg end-to-end build log (2026-06-11)

**Dash callback decoder pattern proven**:
1. `GET dash.upag.gov.in/_dash-dependencies` → full 805-callback graph (no auth)
2. Find the data-store callback for the target report (prefix-based)
3. `POST dash.upag.gov.in/_dash-update-component` with the data-store callback signature (`outputs`, `inputs`, `changedPropIds`, `state`) and filter values in `inputs[0].value`
4. Response has the actual data list under `response.{prefix}-{store-name}.data`

**Vendor + first fetcher shipped to playground**:
- Library helpers: callback POST shape ported in-line per fetcher (no shared helper module yet — pattern is small enough to inline for 1-2 fetchers; consolidate to `src/imdr/domains/econ/upag.py` when 3rd lands).
- A31 MSP fetcher at [`playground/econ/in/upag/upag_msp.py`](../../../playground/econ/in/upag/upag_msp.py) — prefix `mip-msp-data2`, callback `mip-msp-data2-store2.data`, filter values `{from_year, to_year}` in FY string format. Smoke-verified end-to-end 2026-06-11: **28 indicators × 353 obs · 2013-14 → 2026-27**, all in INR/Qtl, annual cadence. Wheat Rabi 2026-27 = ₹2,585 ✓ (matches public news). 

**A26 AIAPY end-to-end (2026-06-11)** — built at [`playground/econ/in/upag/upag_aiapy.py`](../../../playground/econ/in/upag/upag_aiapy.py). Same Dash decoder pattern as MSP. 60 years of Area/Production/Yield by crop × season — the foundational India ag dataset. Sanity check: Wheat Rabi 2025-26 Production = 958.5 Lakh Tonnes (~95.85 Mt) ✓ matches public reports. The fetcher reads the live callback signature from `_dash-dependencies` (resilient to UPAg adding/removing output slots).

**Reports probed but deferred for next session**:

| Prefix | Report | Status | Why deferred |
|---|---|---|---|
| `pcas` | Progressive Crop Area Sown (A26 weekly) | callback decoded; returns latest 2 years of cumulative-since-monsoon snapshot only | Useful as a nowcast indicator but not a deep time series — promote when monsoon nowcasting becomes desk-priority |
| `swapy` / `swapyse` | Statewise APY · APY by Season | not probed | AIAPY already covers All-India; add per-state when state-level desk question lands |
| `imc-{oilseeds,pulses,cereals,topcrops,othercrops}` | Market Intelligence Centre mandi prices (A33 path via Agmarknet) | **DONE 2026-06-11** — [`playground/econ/in/upag/upag_imc.py`](../../../playground/econ/in/upag/upag_imc.py). 16 indicators × 128 obs (4 sections × 3-5 commodities × 8 anchor dates per run). Decoded the Plotly binary `y` array (`{dtype: "f8", bdata: base64}`) and anchor-date timeline format. Each request returns 3-5 traces for ONE section. | Weekly orchestrator extends the time series via the sliding 8-anchor snapshots. |
| `cwwg-dash` | CWWG Crop Weather Watch Group (map + trend) | not probed | Defer; AIAPY annual + IMC monthly covers most use cases |
| `cwmps`, `cterwne`, `wpi-report`, `dgcis-prov`, `gvagdp`, `customduties`, `ncdx-report`, `enamvsagmarknet`, … | ~46 additional myGrid-backed UPAg reports | catalog | Build-on-demand per desk question |

**Coverage UPAg unlocks** (one fetcher per report on the pattern above):
- A26 DAC sowing — **✅ AIAPY done** (60-year area/production/yield); `pcas` weekly snapshot deferred
- A31 MSP — ✅ done
- A33 Agmarknet — `imc-*` reports filter shape decoded, fetcher build deferred
- Cluster 4 (agriculture) — **broadly covered** via MSP (input prices) + AIAPY (output area/production/yield)

### Tier 6 — promotion-side gating (no new data — sign-offs only)

- **Cadence sign-off** for the 8 pre-prod playground fetchers built 2026-06-11 (MOSPI CPI/IIP/NAS · DPIIT WPI/8-Core · CGA · IMD · FAO). Two options documented in `index.md` § Loading status — pick one, then wire into `imdr_monthly.py:PIPELINES`.
- **Promotion-DB cleanup** if needed (15,081 obs / 197 dim rows from build-session smoke load — currently in DB but harmless; idempotent on re-run).
- **In-coverage gaps after Tier 1-5 land**: 1.1 Private Demand (no formal retail-sales index in IN) · 2.3 Domestic Costs proper wage series (Labour Bureau WRI sits in Tier 2) · 3.1 Terms of Trade (derivable from A13 once multi-month).

### A13 end-to-end log — DGCIS multi-month loop (2026-06-11)

**History reachable**: calendar **Apr 2013 → Mar 2026** end-to-end verified. The MEIDB form's year dropdown shows only 2018-2026, but the POST endpoint accepts `ddYear=2014..2026` and returns distinct, correct data for each — verified by sampling HS01 (Live Animals) across multiple FYs. Each response carries 6 value columns: prior-year-same-month / current-month / YoY% / prior-FY-YTD / current-FY-YTD / FY YoY%. The fetcher exploits the prior-year-same-month column to extend back-history by **12 free months** (walk starts at Apr 2014 → captured Apr 2013 via clean[3]).

**Cadence**: monthly. Real publication lag is **2-3 months at the FY edge** (not the 15-day "typical" lag often quoted). As of 2026-06-11 the latest released month is March 2026; April + May 2026 are not yet on the portal. The fetcher detects unreleased months by the "≥50% zero values across the 99 HS chapters" sentinel and drops them automatically. Re-running monthly catches every release; MERGE on `(indicator_id, obs_date, vintage)` makes it idempotent. DGCIS revises older months (e.g. "(R)" suffix on column headers); latest fetch wins.

**Performance**: 145 months × 2 directions = **290 POSTs**. CSRF rotates per request, so each POST is preceded by a GET; ~2s/cycle (1s server + 1s polite throttle). Full backfill ≈ 10 min wall-clock.

**Output shape**:
- `INDIA.TRADE.{EXPORT|IMPORT}.HS{nn}.USD_MN.IN` — one per HS-2 chapter (98 chapters live; HS77 reserved/unused per WCO)
- `INDIA.TRADE.{EXPORT|IMPORT}.TOTAL.USD_MN.IN` — headline (parsed from the trailing "India's Total {Export|Import}" row)
- Unit `usd_mn`, frequency `MONTHLY`, category `bop`, country `IN`
- **End-to-end verified 2026-06-11**: 198 indicators / 31,284 obs raw / **~30,888 obs after unreleased-month filter** / window 2013-04 → 2026-03.

**Cell coverage**:
- 1.3 External Demand — `INDIA.TRADE.EXPORT.TOTAL` + `INDIA.TRADE.IMPORT.TOTAL` + per-HS series feed the headline trade balance + sector decomposition
- 3.1 Terms of Trade — derivable from HS-chapter USD price proxies if quantity series added (`ddReportVal=2`); ToT computation is a downstream transform, not a new fetch

**Loading plan (DECISION DEFERRED per user 2026-06-11)**:
- Cadence: monthly. Belongs in `imdr_monthly.py` once promoted.
- Volume note: at HS-4 granularity the same approach would generate ~99k obs (1,224 HS-4 codes vs 98 HS-2 chapters); HS-6 would push ~500k obs. HS-2 is the right starting granularity — extend to HS-4 later if a desk question needs commodity-level cuts.

**Known runner.py quirk** (not specific to A13): `scripts/econ/_runner.py:_summary` prints `latest=<value>` per indicator using the LAST-INSERTED obs, not the chronologically latest. Misleading at a glance; the parquet/DB always has the correct per-obs-date values. Worth fixing but not load-bearing.

**Promotion preconditions when ready**:
1. Move [`playground/econ/in/dgcis/dgcis_trade.py`](../../../playground/econ/in/dgcis/dgcis_trade.py) → `scripts/econ/in/dgcis/`
2. Confirm `dgcis` vendor in `dbo.dim_vendor` (already there from migration 089).
3. Run with default args (full backfill) once for initial load; subsequent monthly invocations only re-fetch the latest ~6 months for revision-catch (consider a `--latest-only` flag later).
4. Add to `imdr_monthly.py:PIPELINES` after user OK.

### A2-A7 — RBI DBIE end-to-end scoping (2026-06-11)

**Architectural finding** — after a Playwright discovery session against `data.rbi.org.in/DBIE/`, the 1,225-report catalogue ([`playground/econ/rbi/discovery/all_reports.json`](../../../playground/econ/rbi/discovery/all_reports.json)) is reachable via **three distinct paths** with very different effort profiles. This rewires the A2-A7 plan.

**1. AES encryption decoded** (was the blocker; now reproducible) — DBIE's SPA encrypts `reportId` / `portal` / `lang` params before POST. The full algorithm + hardcoded keys are extracted from `main.fae0f40836c7fe13.js` class `Ll`:

```
AES-256-CBC, PKCS7 padding
password (UTF-8 of hex string):  "48d6b976d7135745b47b407cd8e659a45d8ebaca4ee95f87d5d939604f472268"
salt (hex):                       "577bd45a17977269694908d80905c32a"
IV   (hex):                       "dc0da04af8fee58593442bf834b30739"
key = PBKDF2-HMAC-SHA1(password, salt, iterations=1000, dklen=32)
output = base64( AES-CBC( utf8(plaintext) ).ciphertext )
```

Verified end-to-end at [`playground/econ/rbi/probe_crypto.py`](../../../playground/econ/rbi/probe_crypto.py): `encrypt("DBIE")` reproduces the captured ciphertext `jw4rTB1+6RG1SG1fTzXNbg==`; `decrypt("A0ZmOM+gv6iQvJWbTebS4w==")` returns `"575"` (Exchange Rate's plain reportId). SPA has a `setTokens()` method that can rotate these dynamically — first-load defaults are what's hardcoded; track for rotation.

**2. The 3-tier data-reach architecture**:

| Tier | What | Reports covered | Effort |
|---|---|---|---|
| **DBIE-JSON** | Dedicated JSON endpoints. POST `{"body":{...}}` returns time series directly. | ~2 of 1,225 — `dbie_foreignExchangeReserves` (5 reserve codes) + `dbie_getPublicationDataImpala` (Key Rates dashboard ONLY — wedded to one report regardless of `reportId`) | ✅ DONE (A1 + A5 partial) |
| **DBIE-SAP-BO** | Click report → `dbie_getReportLink` returns encrypted `sapLink` → decrypts to `/BOE/OpenDocument/opendoc/openDocument.jsp?sIDType=CUID&iDocID=...&token=...secEnterprise:guest_user...` → SAP BO renders the report in an iframe with a guest_user session token. **Data is NOT a JSON response** — it's a server-rendered table inside the iframe. To extract programmatically: either drive the SAP BO viewer's `Export to Excel/CSV` button via Playwright, or hit SAP BO's export API directly if reachable as guest_user. | ~1,000+ of the catalogue — Exchange Rate, BoP, External Debt, NRI/FCNR/NRE/NRO, Money Market, G-Sec, Bulletin tables, Survey results, BSR-1/2, NBFC stats, Banking Performance, etc. | M-L — Playwright iframe automation, ~30min per report-class to build, then loop |
| **RBI-Bulletin-XLSX** | Direct XLSX downloads at `rbidocs.rbi.org.in/rdocs/Bulletin/DOCs/*.XLSX`. Behind **Akamai TSPD bot-protection** — requires headed Chrome to clear the JS challenge. Each XLSX is one bulletin table (e.g. T19C CPI, T27 Call Money, T1 SEI). Already scaffolded at [`playground/econ/rbi/fetch_bulletin.py`](../../../playground/econ/rbi/fetch_bulletin.py); CPI Combined + Call Money + SEI XLSX samples decoded cleanly (see [`playground/econ/rbi/discovery/bulletin_downloads/`](../../../playground/econ/rbi/discovery/bulletin_downloads/)). | Subset of the 200+ Bulletin tables — covers headline CPI back to 2014, Call Money daily, Money Stock weekly/monthly, etc. **Same data as DBIE-SAP-BO but XLSX instead of iframe** — much cleaner. | S-M — TSPD-cleared headed Chrome + bs4 HTML-table parser (XLSX files are HTML-table-with-XLSX-extension), already 70% built |

**3. Practical mapping of the A4-A7 checklist to a path**:

| Item | Cell(s) | Best path | Status |
|---|---|---|---|
| ~~A4~~ RBI Bulletin tables | 2.4 · 4.3 · 1.1 · 1.4 · **3.1 · 3.2 · 3.3** · 3.4 · 4.4 | **RBI-Bulletin-XLSX** | **DONE 2026-06-11 (11 tables)** — [`playground/econ/in/rbi/rbi_bulletin.py`](../../../playground/econ/in/rbi/rbi_bulletin.py); **317 indicators × 847 obs**. Tables: T19C CPI · T27 Call Money · T23 IIP · T6 Money Stock M0/M1/M3 · T11 Reserve Money · T37 NEER/REER · T22 WPI · T2 RBI Balance Sheet · **T33 FX Reserves (dual-unit)** · **T32 Foreign Trade (dual-unit)** · **T40 BoP Credit/Debit/Net × 2 quarters (151 indicators alone — Current Acc, Merchandise, Invisibles, Software Services, etc.)**. Three parser helpers cover all layouts. **Effectively eliminates the A5-A7 SAP-BO iframe requirement** for the BoP cells. Remaining: SEI T1 (multi-block quarterly tags — defer). Headed Chrome only (TSPD). |
| A5 Exchange Rate · Money Market · G-Sec Turnover · Reserve Money · RBI Balance Sheet · Payment System · Central Govt Market Borrowings · Business of Scheduled Banks · Daily LAF · Sectoral Deployment | 1.2 · 3.4 · 4.3 · 4.4 | Mostly DBIE-SAP-BO (Bulletin covers some — e.g. T6 Money Stock, T16 Reserve Money) | partial via Bulletin |
| A6 BoP · ITS Services · External Debt · NIIP · NRI/**FCNR(B)** · ECB · FDI · RBI sale/purchase USD · forward book | 3.1 · 3.2 · 3.3 · 3.4 | **DBIE-SAP-BO** — Bulletin doesn't carry BoP-level detail | needs SAP BO iframe automation |
| A7 Corporate sector · Banking BSR-1/2 · NBFC · GNPA/NNPA/CRAR | 4.2 | **DBIE-SAP-BO** | needs SAP BO iframe automation |

**Recommended next moves (pick one):**
- **Path X — Build A4 via RBI-Bulletin-XLSX route**: ~30-60 min. Reuse the `fetch_bulletin.py` scaffold; add the 10-15 highest-priority bulletin tables (CPI/Call Money/Money Stock/Reserve Money/Payment System/SEI/Banking Performance). Closes 4 wiring-map cells (1.1 / 1.2 / 2.4 / 4.3 / 4.4 partial). All series have deep history (CPI back to 2014, Call Money back to 1972).
- **Path Y — Build the generic DBIE-SAP-BO iframe extractor**: ~2-3 hr. Playwright that: encrypts the reportId → POST `dbie_getReportLink` → decrypts the sapLink → opens it in a new tab → triggers the "Export to Excel" button in SAP BO → captures the download → parses. Once built, every reportId in the 1,225-catalogue becomes reachable. Closes A5-A7 in one stroke (~80-120 indicators).
- **Path Z — Just document + stop**: declare the encryption breakthrough + architecture is the deliverable; punt the actual fetcher build to next session.

### A5-A7 SAP-BO pipeline end-to-end VERIFIED through sapLink decryption (2026-06-11)

After the encryption breakthrough, the full pipeline up to the SAP-BO entry URL is now reachable from `rvsg-fs01`:

1. `DBIEClient.bootstrap()` → session token (already prod-built)
2. `encrypt("DBIE")` → portal param ciphertext (verified)
3. `encrypt(<reportId>)` → reportId ciphertext (verified)
4. POST `dbie_getReportLink` with encrypted params → returns encrypted `sapLink`
5. `decrypt(sapLink)` → `/BOE/OpenDocument/opendoc/openDocument.jsp?sIDType=CUID&iDocID=<id>&token=`
6. GET that URL → 200 OK, SAP BO BI Launchpad bootstrap HTML

Verified 2026-06-11 with **reportId=417 (NRI Deposits monthly 1997→2026)**:
- Decrypted sapLink: `/BOE/OpenDocument/opendoc/openDocument.jsp?sIDType=CUID&iDocID=Ab8bdZWzZ9RNixmFYdscUO8&token=`
- HTTP 200 from `data.rbi.org.in/BOE/...` with body matching SAP OpenDocument bootstrap.

**27 desk-priority reportIds catalogued and ready** (sample from [`playground/econ/rbi/discovery/all_reports.json`](../../../playground/econ/rbi/discovery/all_reports.json)):

| reportId | Freq | Window | Name |
|---:|---|---|---|
| 417 | Monthly | 1997 → 2026 | **NRI Deposits** (the desk-critical FCNR/NRE/NRO breakdown) |
| 421 | Annual | 1991 → 2026 | NRI Deposits Outstanding (INR) |
| 628 | Annual | 1991 → 2026 | NRI Deposits Outstanding (USD) |
| 55  | Monthly | 2004 → 2026 | External Commercial Borrowings (ECBs) |
| 698 | Daily | 2003 → 2026 | Daily Forward Premia (Inter-Bank) |
| 558 | Monthly | 1993 → 2026 | Forward Premia Monthly Average |
| 1534 | Annual | 2019 → 2025 | Consolidated Balance Sheet of NBFCs |
| 1543/1544 | Annual | 2022 → 2025 | Financial Performance NBFC-UL/ML |
| 1198 | Annual | 2016 → 2018 | Credit to Various Sectors by NBFCs |

**Last-mile remaining** (deferred to next focused session): the SAP-BO viewer page is a JS bootstrap that loads the actual report content via iframe + further redirects. To extract data programmatically, two paths:

- **Playwright iframe automation** (~2-3hr): drive the SAP-BO viewer in headed Chrome → wait for iframe load → click "Export as Excel" → capture download → parse XLSX
- **JS-reverse-engineer the data-fetch endpoint** (~2-3hr, brittle): trace SAP BO's `/BOE/sap/...` REST calls in the network log, replicate via httpx

For the Current Account / BoP cell, the **RBI Bulletin T40 path (already built this session)** delivers the same data without needing SAP-BO. So the SAP-BO automation effort is most valuable for the FCNR / NRI / ECB / NBFC streams that have no Bulletin equivalent.

### A4 path original update (2026-06-11) — partial smoke
Two TSPD-cleared XLSX downloads decoded cleanly:
- `cpi_combined.xlsx` (T19C) → 23 rows, 13 division labels × 4-6 monthly periods per release
- `call_money_rates.xlsx` (T27) → 34 rows, ~28 daily observations per release

**Key insight: each Bulletin XLSX is a single-month snapshot, NOT a deep back-history file**. T19C carries ~4-6 monthly periods (latest month + same-month-prior-year + FY-avg); T27 carries ~28 daily observations (one month). To build deep history via Bulletin, the orchestrator must accumulate snapshots month-over-month (monthly tick → +1-4 weeks of data per indicator). Idempotent MERGE on `(indicator_id, obs_date, vintage)` handles dedup.

For deep history, the better RBI source is the **Handbook of Statistics on the Indian Economy** (annual XLSX with 30+ years of monthly tables for each indicator). Not yet probed; lives under DBIE-Publications tree. Recommend adding **A4b Handbook of Statistics** as a separate item.

**A4 + A4b production layout (when promoted)**:
- `scripts/econ/in/rbi/rbi_bulletin.py` — monthly tick; appends 1-4 weeks of new data to ~10 tables. **Requires headed Chrome (TSPD)**.
- `scripts/econ/in/rbi/rbi_handbook.py` — annual tick; replaces the deep back-history snapshot once a year when RBI updates the Handbook. (Future work.)
- Cell coverage when complete: 1.1 (CPI core), 1.2 (WPI), 2.4 (CPI division YoY), 4.3 (Call Money daily, Repo/Reverse Repo curve), 4.4 (Reserve Money M0, Money Stock M3).

### Government filings + events — Korea-pattern roadmap (new 2026-06-11)

Today: India has a bulk-PDF corpus harvest at [`playground/econ/in/govt/daily_pull.py`](../../../playground/econ/in/govt/daily_pull.py) + [`ingest_filings.py`](../../../playground/econ/in/govt/ingest_filings.py) — 237 PDFs / 250 MB on disk, 210 reports / 4,446 chunks in Qdrant. That's a *corpus-build* shape (one-shot bulk download, then ingest).

Target: a *daily watch* shape modelled on [`scripts/econ/kr/govt/`](../../../scripts/econ/kr/govt/) — per-agency fetcher module + shared dedup orchestrator that only catches NEW items each day, then pushes through `imdr.research.filings.ingest_filing` into `research.dim_report` + `research.fact_chunk` + Qdrant + SharePoint. Each agency vendor lives at `scripts/econ/in/govt/fetch_{agency}.py`; the orchestrator is `scripts/econ/in/govt/ingest_filings.py`; rolling dedup state at `data/econ/in/govt/{agency}/seen.json`; per-day snapshot at `data/econ/in/govt/{agency}/snapshots/{YYYY-MM-DD}.json`.

Agencies to build (Korea has 8; India needs ≥10):

| Agency | Fetcher module | Maps to B-items | Current state | Priority |
|---|---|---|---|---|
| RBI (press releases · MPC resolutions · MPC minutes · MPR · FSR · Bulletin chapters · Annual Report · Notifications · Speeches) | `fetch_rbi.py` | B1-B8 | bulk corpus only — needs per-section listing scrapers | **P0** (governor meetings, MPC, speeches drive desk narrative) |
| MoF / DEA / Budget Division | `fetch_mof.py` | B9 Union Budget · B10 Economic Survey · B11 Mid-Year Analysis | bulk corpus only | **P0** (Budget Day + Mid-Year are calendar-anchor events) |
| MOSPI (CPI / IIP / NAS / PLFS press notes) | `fetch_mospi.py` | B5+B6 deferred + general MOSPI press | listing API discovered (companion to A8-A11) | **P1** |
| CGA (monthly accounts press notes) | `fetch_cga.py` | B12 | bulk corpus only | **P1** |
| PIB (cross-cutting press release archive) | `fetch_pib.py` | B14 GST monthly · B20 PLI launches · B23 CBIC notifs | not probed — encrypted-title aggregator | P2 (decode encrypted titles first) |
| SEBI | `fetch_sebi.py` | B15 | not probed | P2 |
| IRDAI | `fetch_irdai.py` | B16 | not probed | P2 |
| DPIIT | `fetch_dpiit.py` | B17 FDI policy notifs | not probed | P2 |
| ECI (Election Commission) | `fetch_eci.py` | B18 election dates | not probed | P2 |
| GST Council | `fetch_gst_council.py` | B19 council outcomes | not probed | P2 |
| MoA (PM-KISAN · MSP · sowing) | `fetch_moa.py` | B21 MSP · A26 sowing | not probed | P3 |
| IMD (seasonal forecasts) | `fetch_imd.py` | B22 forecasts | not probed (A24 covers daily rainfall data) | P3 |
| CBIC (customs notifications) | `fetch_cbic.py` | B23 | not probed | P3 |

Korea-style state lives at `data/econ/in/govt/{agency}/`. Each fetcher's output is a `list[FilingItem]` (per `_models.py` in the Korea reference); dedup_key matches the Korea convention (vendor_code + canonical URL + publish_date).

This whole roadmap is **gated on a PDF→Markdown→Qdrant production pipeline** — the playground scaffold ([`ingest_filings.py`](../../../playground/econ/in/govt/ingest_filings.py)) works end-to-end against the local DB+Qdrant, but the prod-shape model loader path (with proper resolvers, retry, embedding rate-limit handling) is the Korea reference at [`scripts/econ/kr/govt/ingest_filings.py`](../../../scripts/econ/kr/govt/ingest_filings.py) — port that shape for India.

---

## Coverage status at a glance (updated 2026-06-11)

### Prod-live in `econ.fact_indicator`

| Source | Cadence | Indicators | Obs | Window |
|---|---|---:|---:|---|
| BIS India (A21) | DAILY/MONTHLY/QUARTERLY | 6 | 24,957 | 1946→2026 |
| FRED India (A22) | DAILY/MONTHLY/ANNUAL | 7 | 11,589 | 1990→2026 |
| RBI DBIE FX reserves (A1) | WEEKLY | 5 | 3,015 | 2015→2026 |
| RBI DBIE Key Rates (A5 partial) | EVENT | 8 | 8 | snapshots |
| **Prod total** | | **26** | **39,569** | |

### Pre-prod playground (built + smoke-tested 2026-06-11; awaiting cadence sign-off)

Code at `playground/econ/in/{vendor}/`; shared MOSPI helper at [`src/imdr/domains/econ/mospi.py`](../../../src/imdr/domains/econ/mospi.py); orchestrator scaffold at [`playground/econ/in/in_monthly.py`](../../../playground/econ/in/in_monthly.py). 197 indicators × 15,081 obs landed in `econ.fact_indicator` during the build session and stay in place (idempotent MERGE) until cadence + promotion sign-off; the code itself is pre-prod until then.

| Source | Cadence | Release window | Indicators | Obs | Window |
|---|---|---|---:|---:|---|
| MOSPI CPI (A8) | MONTHLY | ~12th for prior-month | 78 | 150 | Jan-Apr 2026 (2024-base only; 2012-base deferred) |
| MOSPI IIP (A9) | MONTHLY | ~12th for M-2 | 20 | 3,350 | Apr 2012→Mar 2026 (Level + YoY) |
| MOSPI NAS GDP (A10) | QUARTERLY+ANNUAL | Q4≈May30, Q1≈Aug30, Q2≈Nov30, Q3≈Feb28 | 35 | 272 | 2022-23 base; 4 FY + 16 Q |
| DPIIT WPI (A12) | MONTHLY | ~14th for prior-month | 8 | 1,352 | Apr 2012→Apr 2026 |
| DPIIT 8-Core (A45) | MONTHLY | last working day for M-2 | 18 | 3,150 | Apr 2011→Apr 2026 (Level + YoY) |
| CGA fiscal (A14) | MONTHLY | last working day for M-1 | 30 | 4,182 | Apr 2014→Feb 2026 |
| IMD rainfall (A24) | DAILY (Jun-Sep) | refreshed daily | 3 | 3 | snapshot — All-India aggregate |
| FAO FPI (A41) | MONTHLY | ~first Friday | 6 | 2,622 | Jan 1990→May 2026 |
| DGCIS trade (A13) | MONTHLY | 2-3 mo lag at FY edge (latest released: Mar 2026) | 198 | ~30,888 | Apr 2013→Mar 2026 (HS-2 chapters × Export+Import; unreleased-month filter drops Apr+May 2026) |
| UPAg MSP (A31) | ANNUAL | Kharif (Jun) + Rabi (Oct) announcement events | 28 | 353 | 2013-14→2026-27 (14 FYs × 28 crops × MSP level INR/Qtl; Δ + Δ% derivable) |
| UPAg AIAPY (A26) | ANNUAL | Estimation cycles M-1 yr (Third Adv) through M-3 yr (Final) | 324 | 15,030 | **1966-67→2025-26 (60 FYs)** × 37 crops × {Kharif, Rabi, Summer, Total} × {Area Lakh-Ha, Production Lakh-Tonnes, Yield Kg/Ha}; cycle-dedup prefers Final over Third Advance |
| UPAg IMC (A33) | WEEKLY | Daily mandi prices, anchor-date snapshot timeline | 16 | 128 | 4 sections × 3-5 commodities × 8 anchor dates per run (3yr / 2yr / 1yr / 1mo / 3wk / 2wk / 1wk / today). Wholesale Agmarknet INR/Qtl. Cereals (Paddy/Rice/Wheat) · Pulses (Tur/Gram/Lentil/Moong/Urad) · Oilseeds (Rapeseed-Mustard/Soybean/Groundnut/Sesamum/Sunflower) · Topcrops (Onion/Potato/Tomato). |
| RBI Bulletin (A4) | MONTHLY/DAILY/WEEKLY/QUARTERLY | Bulletin publishes mid-month for prior month | 317 | 847 | **11 tables**: CPI T19C (28×84), Call Money T27 (3×84), IIP T23 (9×36), Money Stock T6 (15×45), Reserve Money T11 (10×30), NEER/REER T37 (2×32 — section-detection needs refinement), WPI T22 (48×144), RBI BS T2 (29×78), **FX Reserves T33 (12×24, dual-unit INR Cr + USD Mn)**, **Foreign Trade T32 (10×54, dual-unit)**, **BoP T40 (151×236, Credit/Debit/Net × 2 quarters — includes Current Acc / Merchandise / Invisibles / Services / Software Services / etc.)**. Three parser helpers cover all layouts: `parse_wide_table` (6 tables) · `parse_dual_unit` (2 tables) · `parse_bop` (T40). Single-month snapshot per release — monthly orchestrator accumulates back-history MoM. **Headed Chrome required (TSPD).** |
| **Pre-prod subtotal** | | | **~1,081** | **~62,414** | |

Two prod-wire-up options for the user to pick:

1. **Single monthly trigger** (Indonesia/Korea pattern) — all 8 fetchers go into `imdr_monthly.py:PIPELINES`. Fetchers are MERGE-idempotent so re-running monthly catches every release window. IMD becomes slightly stale (up to ~30 days off-monsoon) but the rainfall narrative cares about cumulative deviation, not single-day freshness.
2. **Cadence-split** — IMD into `imdr_daily.py` (correct freshness during monsoon), other 7 into `imdr_monthly.py`. Extra wire-up step but matches the actual release cadence.

### Still in playground (NOT in DB)

| Source | Status | Gating |
|---|---|---|
| DGCIS MEIDB (A13) | scaffold — single-month POST proven | multi-month loop + IndicatorRow emission still needed |
| MOSPI PDF download (B5/B6 deferred) | PDF corpus harvested | PDF→Markdown→Qdrant pipeline (post migrations 086/087, done — pipeline next) |

### Deferred — known but blocked / hard

| Class | Items | Blocker |
|---|---|---|
| **PDF-only** (downloads tested ✅) | A11 PLFS · A19 PPAC · B1-B8 RBI events · B9-B11 Budget/Survey/DEA · B12-B14 fiscal events · B17 DPIIT notifications · B20-B21 PLI/MSP · B22 IMD forecast · B23 CBIC notifications | Needs PDF→Markdown→Qdrant pipeline (post-migrations 086/087) |
| **Network-blocked from corp net** | A16 NSDL FPI · A18 Labour Bureau · A20 EPFO · A25 CWC · A27 POSOCO · A29 MGNREGA · A33 Agmarknet · A44 e-Way Bill | CDP-attach to user's daily Chrome (AOFM-style — see [[feedback-aofm-fresh-profile-per-run]]) |
| **SPA-rendered, needs deep Playwright** | A15 DPIIT FDI · A28 NHB Residex · A34 PLI scheme · A35 DIPAM · A36 Tourism · A38 IBBI · A40 FAI · A43 SIAM | Click-through Playwright session per vendor |
| **RBI DBIE expansion** | A2 Indicators-tree payload capture · A3 Generic Impala wrapper · A4 Bulletin tables · A5 full · A6 BoP/NRI/FCNR · A7 Corp+Banking | Playwright session against DBIE SPA to decode per-leaf endpoints (~50-100 series each) |
| **Cross-checks deferred** | A23 GSTN (subsumed by A14) · A42 Baltic Dry (FRED timeouts) · B15 SEBI · B16 IRDAI · B18 ECI · B19 GST Council | Each requires its own approach |
| **Credentials gating** | A17 CCIL feed (MIBOR/MIFOR/G-Sec/OIS) | Desk has terminal login; needs machine-readable creds |

### Headline counts

- **Group A data series**: 15 done (4 prod + 11 playground) / 30 deferred or blocked / 45 total
- **Group B events**: 0 done / 24 pending (PDF download contract verified for MOSPI + RBI + PPAC)
- **Wiring map §7.12**: 12 of 16 cells now covered (5 ✅ prod + 5 ✅ playground + 4 ⚠ partial + 2 ❌ no data)

### Critical capability gaps

The remaining items break into **3 distinct infrastructure capabilities**, each substantial:

1. **PDF parsing pipeline** — pymupdf-based extract → Markdown → Qdrant chunking. Already validated: download contract works for all PDF sources via [`scripts/admin/test_pdf_downloads_india.py`](../../../scripts/admin/test_pdf_downloads_india.py). Migrations 086/087 needed to land schema side. Unblocks: ~14 items (PLFS / PPAC / all B-class events).
2. **CDP-attach Playwright** to user's daily Chrome (same pattern as AOFM). Unblocks: ~8 items behind corp-net TLS inspection or login walls (NSDL / Labour Bureau / EPFO / CWC / POSOCO / Agmarknet / MGNREGA / e-Way Bill).
3. **Deep Playwright with click-through + form submit** for SPAs. Unblocks: ~8 items (DPIIT FDI / NHB Residex / PLI / DIPAM / Tourism / IBBI / FAI / SIAM).

Plus 2 vertical work-items:
4. **RBI DBIE Playwright discovery session** — capture per-leaf endpoint patterns from the Indicators / Statistics trees. One focused session unlocks A2-A7 (~50-100 more series across BoP / NRI / FCNR / Corporate / Banking / Bulletin tables).
5. **CCIL credentials** with the desk — A17 MIBOR / MIFOR / forward premia / G-Sec yields / OIS — needs user action.

After those 5 capabilities, India coverage is materially complete.

---

## Status legend

| Marker | Meaning |
|---|---|
| ✅ **confirmed** | Smoke-tested — endpoint returned rows for the candidate identifier |
| ⚠ **candidate** | Documented in vendor portal; not yet probed against API |
| ❓ **unknown** | Wiring-map concept exists in IN statistics, but the right dataset hasn't been identified — needs catalogue browse |
| ❌ **vendor-absent** | Confirmed absent (e.g. no published series); fallback path required |

## Vendor cascade for IN

Per the [onboarding playbook](../onboarding_new_country.md#step-2--resolve-each--via-the-vendor-cascade) Tier table. India has the weakest API landscape in our Asia coverage — only RBI offers structured access, and even that is SPA-mediated.

| Tier | Source | Transport | Coverage |
|---|---|---|---|
| **T1** | **RBI DBIE** — `data.rbi.org.in/DBIE/` | SPA + `CIMS_Gateway_DBIE` REST (POST, static auth headers) | FX reserves, Exchange Rate, Key Rates, Money Market, G-Sec, Reserve Money, RBI Balance Sheet, Bulletin tables, Weekly Statistical Supplement, Handbook of Statistics, BoP, External Debt |
| **T1 (succ.)** | **RBI CIMS** — 10 portals (BoP / FLAIR / SMS / FED / CISBI / FIRMS / +4) | unprobed — presumed similar JSON gateway | Successor to DBIE; migration in progress |
| **T2** | **MOSPI** — `mospi.gov.in`, `mospi.nic.in` | XLSX + PDF release downloads (no API) | CPI (Rural/Urban/Combined), WPI (DPIIT site), IIP, NSO National Accounts (GDP/GVA), ASI (Annual Survey of Industries), PLFS (Periodic Labour Force Survey) |
| **T2** | **DGCIS** — `dgciskol.gov.in` / `tradestat.commerce.gov.in` | XLSX downloads (no API; HTML query forms) | Foreign-trade statistics by HS chapter + partner country; principal commodities monthly summary |
| **T2** | **DPIIT** — `dpiit.gov.in` (Office of Economic Adviser) | XLSX + PDF | WPI primary publication + WPI sub-indices; FDI inflows |
| **T2** | **MoF / Budget Division** — `indiabudget.gov.in` + `cga.nic.in` | XLSX + PDF | Union Budget; monthly receipts/expenditure via CGA Monthly Accounts |
| **T3** | **CCIL** — `ccilindia.com` | XLSX + login-gated CSV | G-Sec yields, INR OIS, FBIL benchmarks (MIBOR, FBIL-USD/INR), repo turnover |
| **T3** | **NSE / BSE** — `nseindia.com`, `bseindia.com` | JSON-ish but bot-hostile | Equity indices (NIFTY, SENSEX), bond indices, currency derivatives (USDINR futures + options) |
| **T3** | **NSDL / CDSL** — `nsdl.co.in/publications/fpi.php` | XLSX + HTML | FPI monthly flows (debt + equity), DII flows |
| **T4** | **BIS** — `stats.bis.org/api/v2/data/dataflow/BIS/...` | SDMX-JSON REST (free, no auth) | REER / NEER broad + narrow, credit-to-GDP gap, DSR private NFS, CBPOL policy rate, total credit |
| **T4** | **FRED** — OECD India mirror | REST (paid key in `IMDR_ECON_FRED_KEY`) | Headline subset — CPI YoY, IP, OECD India unemployment, 10Y G-Sec yield, OECD India IR |
| **T6** | **CMIE / CEIC / Macrobond** | paid API | Last resort if a series is on no free source |

When a series is published by both RBI Bulletin AND its primary issuer (e.g. CPI
in RBI Bulletin T19C reproduces MOSPI's release), prefer the **primary issuer**
(MOSPI). RBI Bulletin tables are convenient but lag the original by 1-2 days
and occasionally trim sub-components.

---

## 1. Growth Engine

### 1.1 Private Demand (consumption, retail, household credit)

| Concept | Vendor | Dataset / table | Cadence | Status |
|---|:---:|---|:---:|:---:|
| Private Final Consumption Expenditure (PFCE) | MOSPI | NSO National Accounts — expenditure side | Q | ✅ playground (mospi_nas_gdp.py) |
| Auto sales (passenger vehicles + 2-wheelers) | SIAM | siam.in monthly press release | M | ❓ industry assoc, paid behind login |
| Retail sales — not formally tracked | — | (no national retail trade index in IN) | — | ❌ vendor-absent |
| Consumer Confidence Index (CCI) | RBI | DBIE — Consumer Confidence Survey (Urban + Rural) | BiM | ⚠ DBIE Unit Level Data section |
| Inflation Expectations Survey | RBI | DBIE — IESH | BiM | ⚠ DBIE Unit Level Data section |
| Household credit aggregate (personal loans) | RBI | DBIE — Statistics → Financial Sector → Banking → Sectoral Deployment of Bank Credit | M | ⚠ DBIE |
| Housing loans (HFC + bank) | RBI | DBIE — Sectoral Deployment | M | ⚠ DBIE |
| Credit card outstanding | RBI | DBIE — Payment System Indicators | M | ⚠ DBIE |

### 1.2 Fiscal Demand (govt spending, taxes, deficit)

| Concept | Vendor | Dataset / table | Cadence | Status |
|---|:---:|---|:---:|:---:|
| Central govt receipts (tax + non-tax) | CGA / MoF | Monthly Accounts of GoI | M | ✅ playground (cga_monthly.py) |
| Central govt expenditure (revenue + capital) | CGA / MoF | Monthly Accounts | M | ✅ playground (cga_monthly.py) |
| Central govt fiscal deficit (cumulative) | CGA / MoF | Monthly Accounts | M | ✅ playground (cga_monthly.py) |
| Direct tax collections (income + corporate) | CBDT | press release | M | ⚠ press release scrape |
| Indirect tax — GST collections | GSTN | gstn.gov.in monthly bulletin | M | ⚠ HTML/PDF scrape |
| Govt final consumption (GFCE, NAS basis) | MOSPI | NSO National Accounts — expenditure | Q | ✅ playground (mospi_nas_gdp.py) |
| Govt investment / GFCF | MOSPI | NSO National Accounts | Q | ✅ playground (mospi_nas_gdp.py) |
| Central govt market borrowings (gross + net) | RBI | DBIE Indicators → Financial Sector → Central Govt Market Borrowings | W | ⚠ DBIE |
| State govt market borrowings (SDL) | RBI | DBIE — State Government Securities Auctions | W | ⚠ DBIE |
| Govt debt outstanding (% of GDP) | MoF / RBI | DBIE Statistics → Public Finance | Q | ⚠ DBIE |
| State govt finances (combined) | RBI | DBIE Statistics → Public Finance → State Govt | A | ⚠ DBIE |

### 1.3 External Demand (trade)

| Concept | Vendor | Dataset / table | Cadence | Status |
|---|:---:|---|:---:|:---:|
| Merchandise exports (USD) | DGCIS / MoCommerce | tradestat.commerce.gov.in monthly summary | M | ⚠ XLSX scrape |
| Merchandise imports (USD) | DGCIS | tradestat | M | ⚠ |
| Merchandise trade balance | DGCIS | tradestat | M | ⚠ |
| Services exports (Receipts) | RBI | DBIE Statistics → External Sector → International Trade in Services | M | ⚠ DBIE |
| Services imports (Payments) | RBI | DBIE Statistics → External Sector → ITS | M | ⚠ DBIE |
| Services balance | RBI | DBIE — ITS | M | ⚠ DBIE |
| Petroleum vs Non-petroleum exports | DGCIS | tradestat split | M | ⚠ XLSX |
| Petroleum vs Non-petroleum imports | DGCIS | tradestat split | M | ⚠ XLSX |
| Gold imports (USD + tonnes) | DGCIS / RBI Bulletin | DGCIS commodity-level; RBI summary | M | ⚠ |
| Exports by partner country | DGCIS | tradestat country-wise | M | ⚠ XLSX (large, ~30MB/release) |
| Imports by partner country | DGCIS | tradestat country-wise | M | ⚠ |
| Exports by HS chapter (98 chapters) | DGCIS | tradestat commodity-wise | M | ⚠ |
| Imports by HS chapter | DGCIS | tradestat commodity-wise | M | ⚠ |
| Net exports (NAS basis) | MOSPI | NSO National Accounts — expenditure | Q | ✅ playground (mospi_nas_gdp.py) |

### 1.4 Macro Core (GDP, IIP, labour, sentiment)

| Concept | Vendor | Dataset / table | Cadence | Status |
|---|:---:|---|:---:|:---:|
| Real GDP YoY | MOSPI | NSO NAS — GDP at constant 2011-12 prices | Q | ✅ playground (mospi_nas_gdp.py) |
| Real GDP level (chain-linked) | MOSPI | NSO NAS | Q | ✅ playground (mospi_nas_gdp.py) |
| Nominal GDP level | MOSPI | NSO NAS | Q | ✅ playground (mospi_nas_gdp.py) |
| Real GVA YoY (basic prices) | MOSPI | NSO NAS — GVA decomp | Q | ✅ playground (mospi_nas_gdp.py) |
| Real GVA by sector (Ag / Mining / Mfg / Construction / Services 5-way) | MOSPI | NSO NAS sectoral | Q | ✅ playground (mospi_nas_gdp.py) |
| GDP deflator YoY | MOSPI | NSO NAS derived | Q | ✅ playground (mospi_nas_gdp.py) |
| GDP YoY (RBI Bulletin reissue) | RBI | DBIE Indicators → Real Sector → GDP | Q | ⚠ DBIE |
| Index of Industrial Production (IIP, total) | MOSPI | IIP monthly release (general / mfg / mining / electricity) | M | ✅ playground (mospi_iip.py) |
| IIP — Use-based (Cap goods, Cons durables, etc.) | MOSPI | IIP use-based | M | ✅ playground (mospi_iip.py) |
| IIP (RBI Bulletin reissue) | RBI | DBIE Indicators → Real Sector → IIP-Monthly | M | ⚠ DBIE |
| 8-Core Industries Index | DPIIT (OEA) | dpiit.gov.in monthly | M | ✅ playground (dpiit_core_industries.py) |
| Manufacturing PMI | S&P Global | paid | M | ❌ paid |
| Services PMI | S&P Global | paid | M | ❌ paid |
| Unemployment rate | MOSPI | PLFS Annual + Quarterly Urban | A + Q | ⚠ PLFS XLSX |
| Labour force participation rate | MOSPI | PLFS | A + Q | ⚠ |
| Employment growth (formal) | EPFO | epfindia.gov.in payroll release | M | ⚠ |
| CMIE unemployment (high-frequency) | CMIE | unemploymentinindia.cmie.com | W + M | ❌ paid |
| Business Sentiment (RBI IOS — Industrial Outlook Survey) | RBI | DBIE — Surveys | Q | ⚠ DBIE |
| Order Books, Inventories & Capacity Utilisation (OBICUS) | RBI | DBIE — Surveys | Q | ⚠ DBIE |

---

## 2. Inflation Engine

### 2.1 Input Costs

| Concept | Vendor | Dataset / table | Cadence | Status |
|---|:---:|---|:---:|:---:|
| Crude oil import basket (USD/bbl) | PPAC | ppac.gov.in monthly | D + M | ⚠ XLSX |
| Domestic petrol / diesel prices | PPAC | ppac.gov.in city-wise | D | ⚠ |
| LPG / kerosene prices | PPAC | ppac.gov.in | M | ⚠ |
| Coal stock + prices | CIL / CEA | press release | M | ⚠ |
| Food article wholesale prices | DPIIT | WPI Food Articles sub-index | M | ✅ playground (dpiit_wpi.py) |
| Fuel & Power WPI sub-index | DPIIT | WPI Fuel | M | ✅ playground (dpiit_wpi.py) |
| Commodity import volumes (gold, oil, edible oil) | DGCIS | tradestat commodity | M | ⚠ |
| Supply-chain pressure (global) | FRED | `NYFEDGSCPI` | M | ❓ cross-country |
| FX pass-through gauge | derived | INR depreciation × import-price differential | M | ❓ analytics-side |

### 2.2 Producer Prices (WPI is India's PPI)

| Concept | Vendor | Dataset / table | Cadence | Status |
|---|:---:|---|:---:|:---:|
| WPI All Commodities (2011-12=100) | DPIIT (OEA) | dpiit.gov.in monthly | M | ✅ playground (dpiit_wpi.py) |
| WPI Primary Articles | DPIIT | sub-index | M | ✅ playground (dpiit_wpi.py) |
| WPI Fuel & Power | DPIIT | sub-index | M | ✅ playground (dpiit_wpi.py) |
| WPI Manufactured Products | DPIIT | sub-index | M | ✅ playground (dpiit_wpi.py) |
| WPI Food Index (cross-Primary + Mfg food) | DPIIT | derived published index | M | ⚠ |
| Producer Price Index (proper PPI — pilot) | MOSPI | NSO PPI pilot (April 2024+ experimental) | Q | ❓ pilot only |
| Export Unit Value Index | DGCIS | trade indices | M | ⚠ |
| Import Unit Value Index | DGCIS | trade indices | M | ⚠ |

### 2.3 Domestic Costs (wages, rents, expectations)

| Concept | Vendor | Dataset / table | Cadence | Status |
|---|:---:|---|:---:|:---:|
| Rural wages (Labour Bureau) | Labour Bureau | labourbureaunew.gov.in monthly | M | ⚠ XLSX |
| Wage Rate Index (WRI) | Labour Bureau | WRI publication | M | ⚠ |
| PLFS earnings (urban + rural by activity) | MOSPI | PLFS Annual | A | ⚠ |
| Mfg capacity utilisation (OBICUS) | RBI | DBIE — Surveys | Q | ⚠ DBIE |
| Inflation Expectations Survey of Households | RBI | DBIE — Surveys (IESH 3M + 1Y) | BiM | ⚠ DBIE |
| Survey of Professional Forecasters (CPI median forecast) | RBI | DBIE — Surveys | Q | ⚠ DBIE |
| Housing rents (CPI sub-index) | MOSPI | CPI Housing sub-group | M | ✅ playground (mospi_cpi.py) |

### 2.4 CPI Pressure

| Concept | Vendor | Dataset / table | Cadence | Status |
|---|:---:|---|:---:|:---:|
| Headline CPI Combined (Rural + Urban) YoY | MOSPI | NSO CPI release | M | ✅ playground (mospi_cpi.py) |
| Headline CPI Combined level (2012=100) | MOSPI | NSO CPI | M | ✅ playground (mospi_cpi.py) |
| CPI Rural YoY + level | MOSPI | NSO CPI | M | ✅ playground (mospi_cpi.py) |
| CPI Urban YoY + level | MOSPI | NSO CPI | M | ✅ playground (mospi_cpi.py) |
| Core CPI (CPI ex Food & Fuel) | MOSPI / derived | NSO sub-indices | M | ⚠ |
| CPI Food & Beverages | MOSPI | sub-index | M | ✅ playground (mospi_cpi.py) |
| Consumer Food Price Index (CFPI) | MOSPI | sub-index | M | ✅ playground (mospi_cpi.py) |
| CPI Fuel & Light | MOSPI | sub-index | M | ✅ playground (mospi_cpi.py) |
| CPI Housing (urban only) | MOSPI | sub-index | M | ✅ playground (mospi_cpi.py) |
| CPI sub-group (6 major + Misc 5-way) | MOSPI | NSO CPI | M | ✅ playground (mospi_cpi.py) |
| CPI (RBI Bulletin T19C reissue) | RBI | DBIE Indicators → Real Sector → CPI | M | ⚠ DBIE (partial discovery — see Phase A captured XLSX) |
| CPI for Agricultural Labourers (CPI-AL) | Labour Bureau | press release | M | ⚠ |
| CPI for Industrial Workers (CPI-IW) | Labour Bureau | press release | M | ⚠ |

---

## 3. External & FX

### 3.1 Terms of Trade

| Concept | Vendor | Dataset / table | Cadence | Status |
|---|:---:|---|:---:|:---:|
| Net Barter ToT | DGCIS / derived | from Export UVI / Import UVI | M | ⚠ derive in analytics |
| Income ToT | DGCIS / derived | NBToT × volume ratio | M | ⚠ derive |
| Export Unit Value Index | DGCIS | trade indices | M | ⚠ |
| Import Unit Value Index | DGCIS | trade indices | M | ⚠ |
| Export Quantum Index | DGCIS | trade indices | M | ⚠ |
| Import Quantum Index | DGCIS | trade indices | M | ⚠ |

### 3.2 Current Account

| Concept | Vendor | Dataset / table | Cadence | Status |
|---|:---:|---|:---:|:---:|
| Current Account Balance (USD bn) | RBI | DBIE Statistics → External Sector → BoP | Q | ⚠ DBIE |
| Current Account % of GDP | RBI | DBIE BoP summary | Q | ⚠ |
| Goods balance (BoP basis) | RBI | DBIE BoP | Q | ⚠ |
| Services balance (Net Invisibles — Travel, Transportation, Software, GNIE, Misc) | RBI | DBIE BoP | Q | ⚠ |
| Primary income balance (Investment income) | RBI | DBIE BoP | Q | ⚠ |
| Secondary income (Private Transfers / Remittances) | RBI | DBIE BoP | Q | ⚠ |
| Software services exports | RBI | DBIE — separately published, also via BoP | Q | ⚠ |
| Remittances inflow (Private Transfers) | RBI | DBIE BoP + RBI Bulletin Remittances Survey | Q + A | ⚠ |

### 3.3 Capital + Financial Account

| Concept | Vendor | Dataset / table | Cadence | Status |
|---|:---:|---|:---:|:---:|
| Capital Account total | RBI | DBIE BoP | Q | ⚠ |
| Foreign Direct Investment (FDI inflows / outflows / net) | RBI / DPIIT | DBIE BoP + DPIIT quarterly | Q + M | ⚠ |
| Foreign Portfolio Investment (FPI) — Equity | NSDL | nsdl.co.in/publications/fpi.php monthly | M + D | ⚠ NSDL XLSX |
| Foreign Portfolio Investment — Debt | NSDL | NSDL FPI | M + D | ⚠ |
| External Commercial Borrowings (ECB) | RBI | DBIE — ECB / Trade Credit / Loans | M | ⚠ DBIE |
| NRI Deposits flows (BoP basis) | RBI | DBIE BoP | Q | ⚠ |
| **FCNR(B) outstanding stock** | RBI | DBIE — Liabilities to Others / NRI Deposits | M | ⚠ DBIE — drives FX-swap hedging volume; key for forward-premia transmission |
| **NRE rupee account outstanding stock** | RBI | DBIE — NRI Deposits | M | ⚠ DBIE |
| **NRO rupee account outstanding stock** | RBI | DBIE — NRI Deposits | M | ⚠ DBIE |
| Other Investment (Banking capital + Loans + Misc) | RBI | DBIE BoP | Q | ⚠ |
| Reserve Assets, transactional change | RBI | DBIE BoP | Q | ⚠ |
| Errors and Omissions | RBI | DBIE BoP | Q | ⚠ |
| Net IIP (International Investment Position) | RBI | DBIE — IIP quarterly | Q | ⚠ |
| External Debt (total + components) | RBI / MoF | DBIE External Debt | Q | ⚠ |
| FX Reserves Total (USD) | RBI | DBIE `dbie_foreignExchangeReserves` `reserveCode=TR` | W | ✅ `scripts.econ.in.rbi.rbi_fx_reserves` (603 obs, 2015→) |
| FX Reserves — Foreign Currency Assets | RBI | DBIE `reserveCode=FCA` | W | ✅ `scripts.econ.in.rbi.rbi_fx_reserves` (603 obs, 2015→) |
| FX Reserves — Gold | RBI | DBIE `reserveCode=GOLD` | W | ✅ `scripts.econ.in.rbi.rbi_fx_reserves` (603 obs, 2015→) |
| FX Reserves — SDR | RBI | DBIE `reserveCode=SDR` | W | ✅ `scripts.econ.in.rbi.rbi_fx_reserves` (603 obs, 2015→) |
| FX Reserves — Reserve position in IMF | RBI | DBIE `reserveCode=IMF` | W | ✅ `scripts.econ.in.rbi.rbi_fx_reserves` (603 obs, 2015→) |

### 3.4 FX / REER

| Concept | Vendor | Dataset / table | Cadence | Status |
|---|:---:|---|:---:|:---:|
| Spot INR vs USD | (FX domain — Citi `FX.SPOT.USD.INR.CITI`) | — | D | ✅ via market data |
| Spot INR vs EUR / JPY / GBP / CNY | (FX domain — Citi crosses) | — | D | ✅ via market data |
| NDF curve INR (offshore — restricted currency) | (FX domain) | — | D | ✅ via market data |
| Onshore USD/INR forward points | (FX domain — Citi) | — | D | ✅ |
| FX implied vol (INR) | (FX domain — Citi) | — | D | ✅ |
| RBI Reference Rate INR/USD | RBI | DBIE Indicators → External Sector → Exchange Rate | D | ⚠ DBIE |
| INR vs USD / EUR / JPY / GBP (RBI ref) | RBI | DBIE Exchange Rate | D | ⚠ |
| NEER 6-currency + 40-currency (trade-weighted) | RBI | DBIE — NEER + REER Bulletin tables | M | ⚠ DBIE — XLSX captured in `discovery/samples/neer_reer.xlsx` |
| REER 6-currency + 40-currency | RBI | DBIE — same publication | M | ⚠ DBIE — XLSX captured |
| BIS NEER broad | BIS | `WS_EER` key=M.N.B.IN | M | ✅ `scripts.econ.in.bis.bis_india` (388 obs, 1994→) |
| BIS REER broad | BIS | `WS_EER` key=M.R.B.IN | M | ✅ `scripts.econ.in.bis.bis_india` (388 obs, 1994→) |
| CB FX intervention (spot + forward book) | RBI | DBIE — Sale/Purchase of US Dollar (RBI net interv.) | M | ⚠ DBIE |
| Forward book outstanding (RBI net long/short USD fwd) | RBI | DBIE — RBI's outstanding forward sales/purchases | M | ⚠ |
| **FBIL onshore USD/INR forward premia** 1M / 3M / 6M / 1Y | FBIL via CCIL | fbil.org.in daily reference fixings (annualised %) | D | ⚠ CCIL — desk-reference fwd premia, distinct from Citi market-data fwd points |

---

## 4. Policy Transmission

### 4.1 Demand Transmission (lending standards, credit channel)

| Concept | Vendor | Dataset / table | Cadence | Status |
|---|:---:|---|:---:|:---:|
| Bank Credit (Non-food, total) | RBI | DBIE — Business of Scheduled Banks | F (fortnightly) | ⚠ DBIE |
| Sectoral Deployment of Bank Credit (Agri/Industry/Services/Personal) | RBI | DBIE Statistics → Banking → Sectoral Deployment | M | ⚠ DBIE |
| Sub-sector credit (e.g. industry by size, services by sub-sector) | RBI | DBIE Sectoral Deployment | M | ⚠ DBIE |
| Bank Deposits (Aggregate) | RBI | DBIE — Business of Scheduled Banks | F | ⚠ DBIE |
| Credit-Deposit ratio | RBI / derived | DBIE | F | ⚠ |
| Mortgage rates (new origination, WALR) | RBI | DBIE — Bank lending rates | M | ⚠ DBIE |
| WALR / WAFR / WATDR (lending + funding rates) | RBI | DBIE — Interest Rate Statistics | M | ⚠ DBIE |
| MCLR (Marginal Cost of Funds based Lending Rate) | RBI | DBIE Key Rates | M | ⚠ DBIE |
| External Benchmark Lending Rate (EBLR) | RBI | DBIE Key Rates | M | ⚠ DBIE |
| BIS credit-to-GDP gap | BIS | `WS_CREDIT_GAP` key=Q.IN.P.A.C | Q | ✅ `scripts.econ.in.bis.bis_india` (258 obs, 1961→) |
| MFI / NBFC credit | RBI | DBIE — NBFC statistics | Q | ⚠ |

### 4.2 Balance Sheets (sectoral leverage, NPL)

| Concept | Vendor | Dataset / table | Cadence | Status |
|---|:---:|---|:---:|:---:|
| Household debt to GDP | BIS | `WS_CREDIT` key=Q.IN.H.A.M.770.A | Q | ⚠ BIS |
| Household DSR | BIS | `WS_DSR` key=Q.IN.H | Q | ❌ confirmed absent — BIS returns HTTP 404 (EM coverage gap); use private NFS |
| NFC (non-financial corp) DSR | BIS | `WS_DSR` key=Q.IN.N | Q | ❌ confirmed absent — BIS returns HTTP 404 for IN; use private NFS |
| Private NFS DSR | BIS | `WS_DSR` key=Q.IN.P | Q | ✅ `scripts.econ.in.bis.bis_india` (107 obs, 1999→) |
| Credit-to-GDP ratio | BIS | `WS_CREDIT_GAP` key=Q.IN.P.A.A | Q | ✅ `scripts.econ.in.bis.bis_india` (298 obs, 1951→) |
| Corporate sector financials (Listed Non-Govt Non-Financial Companies) | RBI | DBIE Statistics → Corporate Sector | A + Q | ⚠ DBIE — 5 sub-categories |
| Bank Asset Quality (GNPA + NNPA ratio) | RBI | DBIE Statistics → Banking → Performance | H | ⚠ DBIE |
| Bank CRAR / Tier-1 / CET1 | RBI | DBIE — Capital Adequacy | H | ⚠ DBIE |
| Bank Sector Aggregates (Stat. Tables Relating to Banks) | RBI | DBIE — STRBI annual publication | A | ⚠ DBIE |
| BSR-1 / BSR-2 (Basic Statistical Returns) | RBI | DBIE Publications | A + Q | ⚠ DBIE |
| Central Govt Debt / GDP | MoF / RBI | DBIE Public Finance | Q | ⚠ |
| Combined Centre+State Debt / GDP | RBI | DBIE Statistics → Public Finance → Central+State Combined | A | ⚠ DBIE |
| NBFC sector balance sheet | RBI | DBIE — NBFC statistics | Q | ⚠ DBIE |
| Financial Stability composite | RBI | Financial Stability Report (semi-annual) | H | ⚠ PDF parse |

### 4.3 Financial Conditions (rates, curve, spreads)

| Concept | Vendor | Dataset / table | Cadence | Status |
|---|:---:|---|:---:|:---:|
| Repo rate | RBI | DBIE Indicators → Financial Sector → Key Rates | EVENT | ✅ prod (rbi_key_rates.py) |
| Standing Deposit Facility (SDF) rate | RBI | DBIE Key Rates | EVENT | ✅ prod (rbi_key_rates.py) |
| Marginal Standing Facility (MSF) rate | RBI | DBIE Key Rates | EVENT | ⚠ DBIE |
| Bank Rate | RBI | DBIE Key Rates | EVENT | ⚠ DBIE |
| CRR / SLR | RBI | DBIE Key Rates | EVENT | ✅ prod (rbi_key_rates.py) |
| Reverse Repo rate (historical, pre-SDF) | RBI | DBIE Key Rates | EVENT | ✅ prod (rbi_key_rates.py) |
| Call Money rate (WACR) | RBI | DBIE Indicators → Money Market | D | ✅ prod (rbi_key_rates.py) — latest snapshot; full time-series still ⚠ DBIE |
| TREPS rate | RBI | DBIE Money Market | D | ⚠ DBIE |
| Market Repo rate | RBI | DBIE Money Market | D | ⚠ |
| MIBOR (overnight + 14D + 1M + 3M term) | FBIL via CCIL | fbil.org.in / ccilindia.com daily fixings | D | ⚠ CCIL |
| **MIFOR / MMIFOR fixings** 1M / 3M / 6M / 1Y (SOFR-linked post-LIBOR cessation) | FBIL via CCIL | fbil.org.in daily | D | ⚠ CCIL — FX-fwd-premium + SOFR composite; key fixing for INR IRS/OIS arbitrage |
| **MIOIS (Modified MIBOR-OIS) fixings** | FBIL via CCIL | fbil.org.in daily | D | ⚠ CCIL |
| 91-day T-bill rate | RBI | DBIE Money Market | D | ⚠ DBIE |
| 182-day T-bill rate | RBI | DBIE Money Market | D | ⚠ |
| 364-day T-bill rate | RBI | DBIE Money Market | D | ⚠ |
| CD (Certificate of Deposit) issuance + rate | RBI | DBIE Money Market | F | ⚠ |
| CP (Commercial Paper) issuance + rate | RBI | DBIE Money Market | F | ⚠ |
| 1Y / 5Y / 10Y G-Sec yield | CCIL / RBI | DBIE G-Sec Market + CCIL terminal | D | ⚠ |
| G-Sec Turnover (NDS-OM) | RBI | DBIE Indicators → G-Sec → G-Sec Turnover | D | ⚠ DBIE |
| Term spread (10Y – 2Y G-Sec) | derived | from G-Sec curve | D | ⚠ |
| Sovereign CDS 5Y (USD) | (rates domain — market data) | — | D | ✅ via market data |
| INR OIS curve (1Y / 5Y) | CCIL / Citi | CCIL terminal; market data | D | ⚠ + ✅ |
| Corporate bond yields (AAA / AA / A — 5Y / 10Y) | CCIL / SEBI | CCIL daily yields | D | ⚠ CCIL |
| NIFTY 50 level | (equity domain — Citi `EQUITY.EQUITY_INDEX.NIFTY.LEVEL.REUTERS`) | — | D | ✅ via market data |
| SENSEX level | (equity domain) | — | D | ✅ via market data |
| Daily LAF (Liquidity Adjustment Facility) net operation | RBI | DBIE Indicators → Financial Sector → Daily LAF Operation | D | ⚠ DBIE |

### 4.4 Policy Reaction (rate + liquidity + macroprudential)

| Concept | Vendor | Dataset / table | Cadence | Status |
|---|:---:|---|:---:|:---:|
| Repo rate level + changes | RBI | DBIE Key Rates + MPC resolution | EVENT | ✅ prod (rbi_key_rates.py) |
| MPC voting record + statements | RBI | press release scrape (`BS_PressReleaseDisplay.aspx`) | per meeting | ⚠ scrape |
| MPC minutes | RBI | rbi.org.in/Scripts/PublicationReport.aspx?ID=911 | per meeting | ⚠ HTML scrape |
| Monetary Policy Report (forecasts) | RBI | semi-annual MPR PDF | H | ⚠ PDF parse |
| Reserve Money (M0) | RBI | DBIE Indicators → Financial Sector → Reserve Money | W | ⚠ DBIE — XLSX captured |
| M1 (narrow money) | RBI | DBIE — Monetary Statistics | F | ⚠ DBIE — XLSX captured |
| M3 (broad money) | RBI | DBIE — Monetary Statistics | F | ⚠ DBIE — XLSX captured |
| Currency in circulation | RBI | DBIE — Reserve Money | W | ⚠ DBIE |
| RBI Balance Sheet (assets + liabilities) | RBI | DBIE Indicators → Financial Sector → RBI Balance Sheet | W | ⚠ DBIE |
| Policy rate (BIS cross-check) | BIS | `WS_CBPOL` key=D.IN | D / EVENT | ✅ `scripts.econ.in.bis.bis_india` (23,518 obs, 1946→ — daily RBI repo rate) |
| Net OMO (outright open market operations) | RBI | DBIE — OMO publications | EVENT | ⚠ |
| **VRR (Variable Rate Repo) auction history** — durable liquidity infusion | RBI | DBIE — Auctions / RBI press release | EVENT | ⚠ DBIE + press release scrape |
| **VRRR (Variable Rate Reverse Repo) auction history** — durable absorption (sterilisation post-FCNR-type inflows) | RBI | DBIE — Auctions / RBI press release | EVENT | ⚠ DBIE + press release scrape |
| **Centre's cash balance with RBI** + Ways & Means Advances | RBI | DBIE — Reserve Money + Public Finance | W | ⚠ DBIE — orthogonal liquidity drain to FCNR-style inflow |
| **Bank NDTL (Net Demand & Time Liabilities)** — CRR sizing base | RBI | DBIE — Business of Scheduled Banks | F | ⚠ DBIE — explicit row (was implicit in BSB) |
| FX intervention spot + forward (cross-ref 3.4) | RBI | DBIE — Sale/Purchase USD | M | ⚠ DBIE |
| LCR / NSFR (bank liquidity rules) | RBI | DBIE — Liquidity Coverage Ratio | Q | ⚠ DBIE |
| Macroprudential — Countercyclical Capital Buffer (CCyB) | RBI | press release | EVENT | ⚠ |
| Macroprudential — LTV / Risk weights | RBI | press release | EVENT | ⚠ |

---

## 5. Events, Press Releases & Document Sources

Data series alone don't answer questions like "will FCNR flows lower MIBOR
fixings" — the regulatory window, the MPC reaction function, and qualitative
RBI communication are essential context. These ingest as **document corpus +
event-stamped records**, not as time series in `econ.fact_indicator`.

Storage convention (per Picasso / Lois corpus pattern):
- Documents → `data/research/in/{vendor}/{YYYY}/{MM}/{DD}/{filename}.pdf` +
  `.md` extract.
- Event stamps → `econ.fact_event` (new table TBD) with
  `(country_id, vendor_id, event_type, event_ts, document_url, summary_text)`.
- Vectorise extracts into Qdrant `imdr-research` collection for retrieval by
  Mycroft + Lois.

### 5.1 RBI events

| Event class | Source URL pattern | Cadence | What to extract |
|---|---|:---:|---|
| **MPC resolution** (rate decision + Governor statement) | `rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=...` | 6 / yr | Date · repo / SDF / MSF / CRR / SLR changes · stance (accommodative / neutral / hawkish) · vote count |
| **MPC minutes** | `rbi.org.in/Scripts/PublicationReport.aspx?ID=911` | 6 / yr (14d after meeting) | Per-member rationale + vote |
| **Monetary Policy Report (MPR)** | `rbi.org.in/Scripts/Publications.aspx?head=Monetary%20Policy%20Report` | semi-annual | Inflation + GDP forecast bands · risk balance |
| **Financial Stability Report (FSR)** | `rbi.org.in/Scripts/PublicationReportDetails.aspx?ID=...` | semi-annual | Systemic-risk dashboard · stress-test results · macro-prudential calls |
| **RBI Bulletin — State of the Economy** chapter | `rbi.org.in/Scripts/BS_ViewBulletin.aspx` | M | Staff macro view |
| **RBI Annual Report** | `rbi.org.in/Scripts/AnnualReportPublications.aspx` | A | RBI balance sheet + monetary operations narrative |
| **Notifications — FCNR / NRI / FPI / ECB regulatory windows** | `rbi.org.in/Scripts/NotificationUser.aspx` | EVENT | Rate caps · withholding tax · CRR waivers · forex regulatory changes |
| **Notifications — Liquidity ops (VRR / VRRR / OMO calendars)** | `rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx` | weekly + EVENT | Auction size · cut-off rate · maturity |
| **G-Sec auction calendar + results** | `rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx` (auction tags) | weekly | Issuance size · cut-off yield · bid-cover |
| **Governor + Deputy Governor speeches** | `rbi.org.in/scripts/BS_speechesview.aspx` | irregular | Forward guidance signals |
| **Sectoral Deployment / Credit aggregates press notes** | `rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx` | M | Sectoral credit growth narrative (companion to DBIE Sectoral Deployment) |

### 5.2 MoF / Fiscal events

| Event class | Source URL pattern | Cadence | What to extract |
|---|---|:---:|---|
| **Union Budget** (Budget Speech + Receipts + Expenditure books) | `indiabudget.gov.in` | A (Feb) | Fiscal deficit target · borrowing programme size · revenue assumptions |
| **Interim Budget** (election year) | `indiabudget.gov.in` | A (Feb in poll yr) | Vote-on-account |
| **Economic Survey** | `indiabudget.gov.in/economicsurvey/` | A (day before Budget) | Govt's macro view + sectoral analysis |
| **Mid-Year Economic Analysis** | `dea.gov.in` | A (Dec) | Mid-year fiscal review |
| **CGA Monthly Accounts** press release | `cga.nic.in/MonthlyReport.aspx` | M | Tax/non-tax receipts + expenditure split + fiscal deficit% |
| **Borrowing calendar (H1 + H2 issuance plan)** | RBI press release | semi-annual | G-Sec + T-bill + SDL size by tenor |
| **GST monthly collections** | `gstn.gov.in` press release | M | GST collections + IGST split |
| **Fortnightly tax receipts** (CBDT / CBIC) | press release | F | Direct + indirect tax momentum |

### 5.3 MOSPI / Statistical-system events

| Event class | Source URL pattern | Cadence | What to extract |
|---|---|:---:|---|
| **CPI press release** | `mospi.gov.in/cpi-press-release` | M | Headline / rural / urban / sub-group + base-revision notes |
| **IIP press release** | `mospi.gov.in/iip` | M | Total + use-based + sectoral + revision flags |
| **NAS Quarterly GDP press release** | `mospi.gov.in/QuarterlyEstimatesGDP` | Q | Real GDP / GVA + sectoral + revision history |
| **NAS Provisional + Revised Annual GDP** | `mospi.gov.in` | A (May + Jan) | Annual baseline + base-year rebase notifications |
| **PLFS Annual + Quarterly Urban** | `mospi.gov.in/plfs` | A + Q | Unemployment / LFPR / earnings |
| **ASI** | `mospi.gov.in/asi-press-release` | A (lag 2y) | Manufacturing structural data |

### 5.4 Sector / other regulator events

| Event class | Source URL pattern | Cadence | Why |
|---|---|:---:|---|
| **SEBI board meeting outcomes** | `sebi.gov.in` press release | M | Bond market structure (FPI debt limits · T+1 settlement · derivative norms) |
| **IRDAI board outcomes** | `irdai.gov.in` | M | Insurance-sector G-Sec demand shifts |
| **DPIIT FDI policy notifications** | `dpiit.gov.in` | EVENT | Capital-account FDI rules |
| **NSE / BSE — F&O turnover + open interest** | NSE EOD reports | D | Derivative-market positioning |
| **EPFO payroll release** | `epfindia.gov.in` | M | Formal-sector employment proxy |

### 5.5 Storage + retrieval pattern

- All documents archived under `data/research/in/{rbi|mof|mospi|sebi|...}/...`
- Markdown extracts of PDFs via `pymupdf` text extraction (per the Picasso / Mycroft PDF embed pattern).
- Vectorise via existing `imdr-research` Qdrant pipeline (see [[project-research-mcp-owner-only]]).
- Event-stamped records (rate decisions, intervention disclosures, FCNR notification dates) flow into a new `econ.fact_event` table for time-series joins.

---

## Discovery → Production phase plan

Plan follows the [onboarding playbook](../onboarding_new_country.md). Phases are
deliberately small because of the dual DBIE/CIMS track and the heavy MOSPI
XLSX scraping work.

| Phase | Scope | Outputs |
|---|---|---|
| **A0 — DBIE auth durability check** | Verify the captured `authorization` header still works 1d / 7d / 30d after capture. If it rotates, build the bootstrap-replay flow first. | `playground/econ/rbi/probe_auth_durability.py` + finding note |
| **A — DBIE FX reserves load** | Already-decoded endpoint. 5 reserve codes × Weekly. | First IN rows in `econ.fact_indicator` (5 indicators); load via `scripts.migrations.load_econ_indicator_from_playground --vendor rbi` |
| **B — DBIE Indicators-tree payload capture** | Click-through Playwright + network interception for each leaf in the Indicators menu (Exchange Rate, Key Rates, Money Market, G-Sec Turnover, Reserve Money, RBI Balance Sheet, Payment System, Central Govt Market Borrowings, Business of Scheduled Banks, IIP, CPI, GDP, Daily LAF, Sectoral Deployment). | `discovery/payloads_indicators.json` with one POST body per leaf; coverage of wiring cells 1.4/2.4/3.3/3.4/4.1/4.3/4.4 partial |
| **C — Generic `dbie_getPublicationDataImpala` wrapper** | Likely many Statistics + Bulletin tables route through the Impala endpoint with `{publication_id, table_id, ...}`. Decode body shape from 2-3 menus and ship a generic fetcher. | `playground/econ/rbi/fetch_publication.py` |
| **D — RBI Bulletin tables** | T19C (CPI), T27 (call money), Remittances Survey, Inflation Expectations, Consumer Confidence — already in metadata, get them loading via the wrapper from Phase C. | 31 Bulletin indicators loaded |
| **E — CIMS portal probe** | Open each of the 10 CIMS sub-portals (`BoP`, `FLAIR`, `SMS`, `FED`, `CISBI`, `FIRMS` + 4) in headed Playwright; capture endpoint inventories. | `discovery/cims_endpoints.json` + per-portal payload samples |
| **F — DBIE↔CIMS endpoint mapping** | For each DBIE endpoint in production by end of Phase D, find the CIMS equivalent and record both. Build the read layer behind a `vendor_route` flag so we can flip per-endpoint. | `playground/econ/rbi/route_map.md` |
| **G — MOSPI CPI release scrape** | MOSPI publishes monthly CPI on `mospi.gov.in/cpi-press-release`. PDF + XLSX. Parse the press release table for Headline / Rural / Urban / CFPI / sub-groups. Promotes 2.4 from ⚠ → ✅. | `playground/econ/mospi/fetch_cpi.py` |
| **H — MOSPI IIP release scrape** | IIP monthly release on `mospi.gov.in/iip`. XLSX + PDF. Promotes 1.4 IIP. | `playground/econ/mospi/fetch_iip.py` |
| **I — MOSPI NAS quarterly GDP** | Quarterly press release with detailed sectoral + expenditure tables (XLSX). Promotes 1.4 GDP + 1.1 PFCE + 1.3 NetExp + 1.2 GFCE. | `playground/econ/mospi/fetch_nas.py` |
| **J — DGCIS trade scrape** | `tradestat.commerce.gov.in` monthly XLSX (totals + petroleum split + partner country + HS chapter). Promotes 1.3 External Demand + 3.1 ToT. | `playground/econ/dgcis/fetch_trade.py` |
| **K — DPIIT WPI scrape** | Monthly WPI release XLSX. Promotes 2.2. | `playground/econ/dpiit/fetch_wpi.py` |
| **L — MoF / CGA fiscal scrape** | Monthly Accounts of GoI XLSX from `cga.nic.in`. Promotes 1.2. | `playground/econ/mof/fetch_monthly_accounts.py` |
| **M — BIS IN package** ✅ | `scripts/econ/in/bis/bis_india.py` shipped 2026-06-10. 6 of 8 candidate indicators live (DSR.HOUSEHOLDS + DSR.NFC return HTTP 404 — confirmed BIS gap for IN). **24,957 obs loaded** to `econ.fact_indicator` covering NEER/REER 1994→, Private-NFS DSR 1999→, Credit-to-GDP ratio 1951→, Credit-to-GDP gap 1961→, RBI repo rate daily 1946→. | `scripts.econ.in.bis.bis_india` |
| **N — Audit + promotion** | Run the load-from-playground command per vendor; verify Phase G coverage map; update wiring map §7.12 and §6 tables; commit. | `econ.fact_indicator` IN rows live; coverage table flipped |
| **O — Prod wiring** | Build `scripts/econ/in/in_monthly.py` (BBG-style orchestrator); user-OK before registering in `scripts/imdr_monthly.py:PIPELINES`. | Orchestrator script committed but **not auto-wired** until user signs off (per [[feedback-no-prod-wiring-without-permission]]) |

Phase A is the unblocker — until DBIE auth proves stable (or we have the replay
flow), nothing downstream is reliable.

Estimate: **6-10 working days end-to-end** for everything except CIMS Phase E/F
(which is parallel and best-effort). The MOSPI / DGCIS scrapes are the biggest
single time sink (Phases G-K), each is ~½-1 day per release format.

## Open questions for the next pass

1. **Auth-header rotation** — does `gjl6p01780417269959196` survive a fresh
   day? If not, what does `security_generateSessionToken` actually return and
   how do we plumb it through `httpx`?
2. **`dbie_getPublicationDataImpala` body shape** — is it `{publication_id,
   table_id}` or is the publication-key hidden inside a deeper structure?
3. **CIMS reachability** — are the 10 CIMS portals on `*.rbi.org.in` and does
   our network pass them through?
4. **MOSPI release format stability** — does MOSPI keep the same XLSX schema
   month-to-month, or do they rebase / restructure mid-year? (We hit this on
   BPS Indonesia.)
5. **DGCIS query-form vs export endpoint** — can we hit the XLSX download URL
   directly with `httpx`, or does the site require a session cookie / token
   from the query form?
6. **CCIL access** — desk has a CCIL terminal login; do we have machine-readable
   credentials we can use for G-Sec yields + MIBOR + corporate bond curve, or
   do we treat CCIL as out-of-scope and live with RBI Bulletin lag?

---

## Appendix A — Worked desk question: "Will increased onshore liquidity translate to lower MIBOR/MIFOR fixings post FCNR flows?"

This is the litmus test for whether the India build can answer real desk
questions. The transmission chain and the corresponding shopping list:

```
FCNR(B) inflow (USD into Indian bank deposit)
  → bank sells USD spot, buys INR              [3.4 spot FX]
  → onshore INR liquidity ↑                    [4.3 LAF / 4.4 Reserve Money]
  → bank hedges FX: USD/INR sell-buy swap      [3.4 RBI fwd book + fwd premia]
  → forward premia compress                    [3.4 FBIL fwd fixings]
  → MIFOR ≈ SOFR + fwd premium → MIFOR ↓       [4.3 MIFOR + 4.3 MIBOR]
  → INR OIS reprices via arbitrage             [4.3 OIS curve]
  → RBI sterilises via VRRR / fwd-buy          [4.4 VRRR + 3.4 RBI fwd book]
  → net effect on MIBOR depends on sterilisation intensity
```

| Step | Series | Cell | Status |
|---|---|---|:---:|
| 1. FCNR stock + flow | FCNR(B) outstanding · NRE · NRO outstanding · NRI Deposits BoP flow | 3.3 | ⚠ DBIE |
| 2. Spot FX absorbed | USD/INR spot · RBI Reference Rate | 3.4 | ✅ + ⚠ |
| 3. Onshore liquidity print | LAF Daily net · Reserve Money M0 · Bankers' Deposits w/ RBI | 4.3 + 4.4 | ⚠ DBIE |
| 4. Bank hedging activity | RBI outstanding forward book · USD intervention spot/fwd | 3.4 | ⚠ DBIE |
| 5. Forward premia signal | FBIL onshore fwd premia 1M/3M/6M/1Y · Citi NDF curve | 3.4 | ⚠ CCIL + ✅ |
| 6. MIFOR transmission | MIFOR/MMIFOR fixings 1M/3M/6M/1Y | 4.3 | ⚠ CCIL — newly added row |
| 7. MIBOR transmission | MIBOR ON/14D/1M/3M | 4.3 | ⚠ CCIL |
| 8. Term-rate arbitrage | INR OIS curve 1M-5Y | 4.3 | ⚠ + ✅ |
| 9. RBI sterilisation | VRRR auction history · Net OMO · Govt cash balance | 4.4 | ⚠ DBIE — newly added rows |
| 10. Regulatory event context | FCNR notification (rate cap / CRR waiver) · MPC stance | §5.1 | ⚠ press-release scrape — needs FCNR-keyword filter |
| 11. Policy reaction function | MPC minutes (forward-guidance language) | §5.1 | ⚠ HTML scrape |

The answer cannot come from data series alone — step 10's regulatory window
(was FCNR(B) rate cap waived? was the special swap window opened?) gates the
size of step 1, and step 11's MPC language gates step 9's sterilisation
intensity. The document corpus in §5 is therefore **load-bearing**, not
optional.

Other desk-question archetypes the build needs to support:

1. **"Where is INR going next month?"** — needs BoP flows · FPI flows (NSDL) · RBI intervention · fwd premia · DXY context · seasonality of remittances.
2. **"How dovish was the latest MPC?"** — needs MPC minutes (votes) + Governor speech + MPR forecast revision history.
3. **"Is the fiscal slippage risk priced in?"** — needs CGA monthly accounts · GST collections · borrowing calendar · 10Y G-Sec yield · term spread · Budget Estimates.
4. **"Are food prices going to push CPI through 6% again?"** — needs CPI sub-groups · CFPI · monsoon data (IMD) · MSP announcements · global commodity proxies.

---

## Final India Checklist

Master punch-list to take India from **0 indicators / 0 events** today to a
production state where the desk-question patterns above are answerable.
Group A = data series, Group B = events/documents, Group C = infra, Group D = sign-off.

Mark items in PRs that close them.

### A. Data series (target: ~150 indicators across 16 cells)

- [x] **A0** DBIE auth durability — captured header confirmed dead 2026-06-10 (returns errorCode 4302). Bootstrap flow live: POST `security_generateSessionToken` w/o auth header → new token in **HTTP response header** `authorization`. Client at `src/imdr/domains/econ/rbi_dbie.py` re-bootstraps on token-expiry mid-call.
- [x] **A1** DBIE FX reserves (TR + FCA + GOLD + SDR + IMF) — `scripts.econ.in.rbi.rbi_fx_reserves` shipped 2026-06-10; **3,015 obs × 5 indicators** loaded covering 2015→2026, weekly. Latest TR = $682.32 bn (2026-05-28).
- [x] **A5 (partial) — Key Rates dashboard snapshot** — `scripts.econ.in.rbi.rbi_key_rates` shipped 2026-06-10. The Impala endpoint (`dbie_getPublicationDataImpala`) is wedded to one dashboard regardless of `reportId`, returning 9 rows: Repo / SDF / Reverse Repo / CRR / SLR (event-stamped step functions) + CPI YoY / WPI YoY (monthly latest) + WACR (daily) + Exchange Rate (ambiguous, deferred). 8 indicators emitted; obs_date = last-change / last-release date so MERGE skips on re-run unless a value moved. Discovered also: `dbie_getAllDBIEReports` returns the full 1,225-report catalogue ([discovery/all_reports.json](../../../playground/econ/rbi/discovery/all_reports.json)) — but the time-series-per-report endpoint is still unknown (candidates: `dbie_getElementsDataQuery`, `dbie_getEntityDataQuery`, `dbie_getImpalaDQAction`, `dbie_firstEBRBaseReport`).
- [ ] **A2** DBIE Indicators-tree payload capture — Playwright + network interception for all leaves; produces `discovery/payloads_indicators.json`
- [ ] **A3** Generic `dbie_getPublicationDataImpala` wrapper — decode body shape; ship `playground/econ/rbi/fetch_publication.py`
- [ ] **A4** RBI Bulletin tables (T19C CPI, T27 call money, IESH, Consumer Confidence, etc.) — 31 indicators
- [ ] **A5** RBI DBIE — Exchange Rate · Key Rates · Money Market · G-Sec Turnover · Reserve Money · RBI Balance Sheet · Payment System · Central Govt Market Borrowings · Business of Scheduled Banks · Daily LAF · Sectoral Deployment · Surveys (IESH / OBICUS / SPF / Consumer Confidence)
- [ ] **A6** RBI DBIE — BoP · ITS Services trade · External Debt · NIIP · NRI Deposits (incl. **FCNR(B) / NRE / NRO** stocks) · ECB · FDI · RBI sale/purchase USD · forward book outstanding
- [ ] **A7** RBI DBIE — Corporate sector (5 sub-categories) · Banking Performance (GNPA/NNPA/CRAR) · BSR-1/BSR-2 · NBFC statistics
- [x] **A8 (playground)** MOSPI CPI release scrape — Combined/Rural/Urban + 13 divisions × Index + YoY → **78 indicators × 4 months (Jan-Apr 2026) decoded** in playground 2026-06-10. Listing API `POST /api/latest-release/get-web-latest-release-list` with `search_term="CPI for"` paginates the press-release archive; XLSX path lives at `/uploads/PressRelease/`. Annexure-I parser works for the post-Jan-2026 "2024-base" format; older "2012-base" releases (Annex-I, 7 sheets) still need a second parser. RBI Bulletin T19C carries headline rural+urban back to 2014 as a fallback for the deep-history gap. See [`playground/econ/mospi/discovery/findings.md`](../../../playground/econ/mospi/discovery/findings.md). **Prod-promotion gated on**: (a) `mospi` vendor migration, (b) legacy-format parser, (c) CFPI + Core extraction, (d) user sign-off.
- [x] **A9 (playground)** MOSPI IIP release scrape — total + sectoral (Mining/Mfg/Electricity) + 6 UBC. **20 indicators × 168 months = 3,350 obs decoded** in playground 2026-06-10 via same listing API as A8 (`search_term="Quick Estimates of IIP"`). One XLSX = full history back to Apr 2012; re-runs are MERGE-skip until a new release lands. See [`playground/econ/mospi/discovery/findings.md`](../../../playground/econ/mospi/discovery/findings.md) §"A9 IIP". **Prod-promotion gated on**: shared `mospi` vendor migration + user sign-off (same gates as A8).
- [x] **A10 (playground)** MOSPI NAS quarterly + annual GDP — **35 indicators × 336 obs** decoded 2026-06-10 via same listing API as A8/A9 (`search_term="Provisional Estimates of Annual GDP"`). 12 annual headlines × real + nominal × 4 FYs ≈ 96 obs annual; 11 quarterly headlines × 16 Q ≈ 176 obs quarterly. Date window 2022-04-01 → 2026-01-01. **Critical**: new 2022-23 base year (rolled out Feb 2026) — only 4 FYs/16 Q of back-history in current release; pre-rebase 2011-12-base series live in older releases (deep history backfill deferred). See [`playground/econ/mospi/discovery/findings.md`](../../../playground/econ/mospi/discovery/findings.md) §"A10 NAS GDP". **Prod-promotion gated on**: shared `mospi` vendor + extend to Statement 6/7/8 (nominal + growth rates) + 2011-12-base backfill + user sign-off.
- [~] **A11 (PDF-only — deferred)** MOSPI PLFS — listing API confirms releases live (Annual Report + Quarterly Bulletin + Monthly Bulletin since 2025-08), but **`file_two=null` on every PLFS release** — they ship PDF-only press notes. Headline LFPR / unemployment / worker-population-ratio numbers are embedded in the PDF text. Defer to a PDF-parsing-equipped session.
- [x] **A12 (playground)** DPIIT WPI release scrape — **8 indicators × 1,352 obs** decoded 2026-06-10. One XLS at `eaindustry.nic.in/indx_download_1112/monthly_index_{YYYYMM}.xls` carries the full WPI back to April 2012 (Base 2011-12=100). 870 rows × 169 monthly cols. Headlines emitted: HEADLINE + PRIMARY + FOOD_ART + NONFOOD_ART + MINERALS + CRUDE_NG + FUEL_POWER + MFG (April 2026 headline = 167.0). Auto-discovery via `download_data_1112.asp` link page. See [`playground/econ/dpiit/discovery/findings.md`](../../../playground/econ/dpiit/discovery/findings.md). Bonus discovery: same site has 8-Core Industries XLSX (relates to A26 cluster 1.4). **Prod-promotion gated on**: `dpiit` vendor migration, mfg sub-group extension (14 more series for core-WPI decomp), user sign-off.
- [x] **A13 (playground, end-to-end 2026-06-11)** DGCIS MEIDB monthly trade — multi-month loop **built + verified** at [`playground/econ/in/dgcis/dgcis_trade.py`](../../../playground/econ/in/dgcis/dgcis_trade.py). Full backfill: **198 indicators × ~30,888 obs · Apr 2013 → Mar 2026** (HS-2 chapters × Export + Import). Unreleased-month sentinel filter handles DGCIS's 2-3 month FY-edge publication lag. See § "A13 end-to-end log" above for the full record.
- [x] **A14 (playground)** MoF / CGA Monthly Accounts scrape — **30 line items × 143 months = 4,182 obs** decoded in playground 2026-06-10. Single `.xlsm` (~520KB) at `cga.nic.in/writereaddata/MonthAccount/MonthAccountDashboard/DAMA dashboard {Month YYYY} Data file{...}.xlsm` carries the full series back to FY 2014-15. Covers: direct taxes (Corp/Inc/STT) · indirect taxes (CGST/IGST/UTGST/CompCess/Customs/Excise/Service Tax legacy) · non-tax receipts (Interest/Dividends/Other) · capital receipts (Loan Recovery/Disinvestment) · expenditure decomp (Revenue/Capital/Interest Pmts/Defence/Pensions/Subsidies/Grants) · 4 deficits (Revenue/Effective Revenue/Fiscal/Primary). Values in INR crore, **cumulative-since-April** (Indian FY convention). See [`playground/econ/cga/discovery/findings.md`](../../../playground/econ/cga/discovery/findings.md). **Prod-promotion gated on**: `cga` vendor migration, BERE + GDP sheet parsers for Budget vs Actual variance, user sign-off.
- [~] **A15 (Next.js SPA — deferred)** DPIIT FDI quarterly — page is a Next.js SSR/SSG SPA at `dpiit.gov.in/publications/fdi-statistics`. The `_next/data/{build}/publications/fdi-statistics.json` endpoint returns HTML not JSON; 0 XHRs captured on plain Playwright load (page might need extra interaction to fetch data). Defer to a session with deeper Playwright work (likely needs `wait_for_selector` or click-through to data tabs).
- [⊘] **A16 (network-blocked)** NSDL FPI — `www.fpi.nsdl.co.in` and `nsdl.co.in` both return `RemoteProtocolError` from our network (HTTP/2 protocol issues, same family as the AOFM blocker per [[project-aofm-blocked]]). Needs the user's daily Chrome via CDP attach (see AOFM workflow) OR an alternate route (Citi vendor feed).
- [ ] **A17** CCIL feed — MIBOR + **MIFOR/MMIFOR** + **FBIL onshore fwd premia** + G-Sec yields 1Y/5Y/10Y + corp bond curve + OIS curve (credentials check needed)
- [⊘] **A18 (network-blocked)** Labour Bureau — `labourbureau.gov.in` / `labourbureaunew.gov.in` / `labourbureau.nic.in` all return `ConnectError` from our network. Needs CDP-attach or alternate route (RBI Bulletin carries CPI-IW too).
- [~] **A19 (PDF-only — deferred)** PPAC — `ppac.gov.in` reachable, but Indian Crude Basket (ICB) + ICR + monthly Flash Reports are all PDF-only at `ppac.gov.in/download.php?file=menu/{timestamp}_{name}.pdf`. No inline data tables, no XLSX. Defer to PDF-parsing session — page lists ~17 monthly PDFs on `prices/internationalprices`.
- [ ] **A20** EPFO monthly payroll release
- [x] **A21** BIS package for IN — `scripts.econ.in.bis.bis_india` shipped 2026-06-10; 6/8 indicators × 24,957 obs live (NEER/REER broad · DSR PNFS · credit-to-GDP ratio · credit-to-GDP gap · RBI repo rate daily 1946→). DSR.HOUSEHOLDS + DSR.NFC return 404 — confirmed BIS gap for IN.
- [x] **A22** FRED OECD India mirror — 7/16 candidates validated 2026-06-10; **11,589 obs loaded**. Live: CPI YoY (1990→) · CPI level (1990→2024) · IIP (1994→2023) · Real GDP annual (PWT, 1990→2023) · Call money rate (1990→) · INR/USD daily (1990→) + monthly (1990→). Confirmed FRED-absent for IN: OECD harmonised unemployment (`LRHUTTTT*IN*` 400) · OECD 10Y govt yield (`IRLTLT01INM156N` 400) · OECD 3M interbank (`IR3TIB01INM156N` 400) · IMF IFS quarterly GDP (`NGDPRSAXDCINQ` 400). Discount Rate `INTDSRINM193N` validates but is stale (last 2022-07) — use `BIS.POLICY_RATE.IN` instead.
  - **Reproducibility caveat (carried over from FRED architecture):** FRED India entries live in `playground/econ/fred/seed.yml` (gitignored). Same as every other FRED country today. Tracked via Linear `IMD-FRED-PROMOTE` (TBD): move `seed.yml` + `connector.py` to `src/imdr/domains/econ/fred*` so the seed becomes reproducible. Until then, anyone re-running `python -m playground.econ.fred.fetch` must hand-add the India rows from the locally-loaded DB state.
- [~] **A23 (deprioritised 2026-06-10)** GSTN monthly GST collections — investigation found no clean public source. GST Council archive stops at Sept 2023; PIB press releases obfuscate titles inside client-decoded encrypted HTML blobs; gst.gov.in / gstn.org.in are empty shells. **Likely already covered by A14** — CGA Monthly Accounts XLSM carries CGST + IGST + UTGST + GST Compensation Cess as separate line items (sum = total GST collection). PIB monthly press releases are the in-month flash but CGA is the finalised version (~1 month lag). Recommend: treat A14 as authoritative for the *data series*; keep B14 (PIB monthly GST collections release) only as a *document corpus* item. See [`playground/econ/gstn/discovery/findings.md`](../../../playground/econ/gstn/discovery/findings.md).

### B. Events + documents

- [ ] **B1** RBI MPC resolutions — `BS_PressReleaseDisplay.aspx` scraper + per-meeting structured extract (date, repo/SDF/MSF/CRR/SLR, stance, vote)
- [ ] **B2** RBI MPC minutes — `PublicationReport.aspx?ID=911` scraper + per-member vote + rationale extraction
- [ ] **B3** RBI Monetary Policy Report (MPR) PDF — semi-annual; forecast band extraction
- [ ] **B4** RBI Financial Stability Report (FSR) PDF — semi-annual; systemic-risk dashboard + stress-test results
- [ ] **B5** RBI Bulletin "State of the Economy" chapter — monthly PDF extract
- [ ] **B6** RBI Annual Report PDF — annual
- [ ] **B7** RBI Notifications — full archive scrape from `NotificationUser.aspx`; classifier tags (FCNR · NRI · FPI · ECB · CRR · SLR · LRS · macro-prudential · liquidity-ops · G-Sec auction)
- [ ] **B8** RBI Governor + Deputy Governor speeches archive — `BS_speechesview.aspx`
- [ ] **B9** Union Budget speech + Receipts/Expenditure books (annual) — `indiabudget.gov.in`
- [ ] **B10** Economic Survey (annual) — `indiabudget.gov.in/economicsurvey/`
- [ ] **B11** Mid-Year Economic Analysis (annual Dec) — `dea.gov.in`
- [ ] **B12** CGA Monthly Accounts press release — companion to the data scrape in A14
- [ ] **B13** Borrowing calendar (H1 + H2) — RBI press release
- [ ] **B14** GST monthly collections press release — companion to A23
- [ ] **B15** SEBI board outcomes — bond-market structure (FPI debt limits, T+1, derivative norms)
- [ ] **B16** IRDAI board outcomes — insurance G-Sec demand context
- [ ] **B17** DPIIT FDI policy notifications

### C. Infrastructure

- [ ] **C1** `econ.fact_event` table — new migration; columns `(country_id, vendor_id, event_type, event_ts, document_url, summary_text)`
- [ ] **C2** Document storage convention — `data/research/in/{vendor}/{YYYY}/{MM}/{DD}/...` archived; markdown extracts via `pymupdf`
- [ ] **C3** Qdrant `imdr-research` IN-namespace — ingest extracts so Mycroft / Lois can retrieve
- [ ] **C4** **CIMS portal probe** — open all 10 CIMS sub-portals; capture endpoint inventories; produces `discovery/cims_endpoints.json`
- [ ] **C5** **DBIE↔CIMS endpoint mapping** — per-endpoint route-flag in the read layer; produces `playground/econ/rbi/route_map.md`
- [ ] **C6** CCIL terminal credentials — desk has login; confirm machine-readable access for A17
- [ ] **C7** PDF extractor cleanups — base-year change detector for MOSPI CPI / WPI; revision-flag handling
- [ ] **C8** Identity reconciliation — DBIE FX reserves vs FRED OECD mirror · WPI vs DPIIT site · RBI ref rate vs Citi spot
- [ ] **C9** `dim_indicator` IN rows — ~150 codes registered with imdr_code + frequency_id + currency_id

### D. Promotion + sign-off

- [ ] **D1** Wiring-map §7.12 flip — ❌→⚠→✅ per cell, update with each phase
- [ ] **D2** Coverage rollup in `india/index.md` — "X indicators / Y observations / Z events live in IN"
- [ ] **D3** Build `scripts/econ/in/in_monthly.py` orchestrator (BBG-style)
- [ ] **D4** Build `scripts/econ/in/in_daily.py` orchestrator (FX reserves W, FBIL/MIBOR/MIFOR D, LAF D, FPI D)
- [ ] **D5** Build `scripts/econ/in/in_weekly.py` (Reserve Money W, OMO/VRR/VRRR auction results)
- [ ] **D6** Build `scripts/econ/in/in_quarterly.py` (BoP, IIP-Q-rev, NAS GDP, BSR, IIP, Sectoral Deployment publication)
- [ ] **D7** User-OK before registering any of the above in `scripts/imdr_{daily,weekly,monthly,quarterly}.py:PIPELINES` (per [[feedback-no-prod-wiring-without-permission]])
- [ ] **D8** Linear epic created — `IMD-INDIA-ECON` parent + per-phase sub-issues mapped to this checklist
- [ ] **D9** Smoke test on the FCNR-MIFOR worked example end-to-end before declaring "production"

### A. Data series — India Cluster Map additions (2026-06-10)

New rows added after cross-checking the 12-cluster India Macro Read map (see [Appendix B](#appendix-b--india-cluster-map-cross-check) for the full mapping). These live alongside the wiring-cell rows in Groups A–D above; numbering picks up at A24.

- [x] **A24 (playground)** **IMD district-wise cumulative rainfall** — 761 districts × (actual_mm, normal_mm, departure_pct) parsed cleanly from inline JS in `https://mausam.imd.gov.in/responsive/rainfallinformation.php` 2026-06-10. No API call needed — single static GET returns ~250KB HTML w/ amcharts `dataProvider.areas` array. To build a time series: scrape daily, stamp fetch-date as obs_date. Smoke test: 723 districts with valid data, mean departure -35% (early June 9 monsoon, expected). See [`playground/econ/imd/discovery/findings.md`](../../../playground/econ/imd/discovery/findings.md). **Prod-promotion gated on**: (a) `imd` vendor migration, (b) sub-divisional aggregate (36 met regions) — `subDivisionWiseWarningGIS.php` needs probing, (c) `imdr_daily.py` registration, (d) user sign-off.
- [ ] **A25** **CWC reservoir levels** — weekly, 4 zones (N/S/E/W). `cwc.gov.in/reservoir-storage`. Predicts hydropower output + Rabi sowing conditions + drinking-water stress.
- [ ] **A26** **DAC crop sowing area** — weekly during sowing season (Kharif Jun-Sep, Rabi Oct-Mar). `agricoop.gov.in`. Per crop + total acreage YoY.
- [ ] **A27** **POSOCO national power demand** — daily peak load + energy met. `posoco.in/reports/daily-reports`. High-frequency activity proxy (alternative to monthly IIP).
- [ ] **A28** **NHB Residex / RBI HPI** — quarterly housing price indices, 50+ cities. NHB `nhb.org.in/residex/` + RBI quarterly HPI publication.
- [ ] **A29** **MGNREGA spend + person-days** — weekly. MoRD `nrega.nic.in`. Rural distress proxy (counter-cyclical to farm income).
- [ ] **A30** **PM-KISAN disbursement** — installment events. MoA press release.
- [ ] **A31** **MSP minimum support price levels** — annual + event when announced. MoA press release per crop.
- [ ] **A32** **FCI food stocks** — monthly. FCI `fci.gov.in/stocks.php`. Rice + wheat buffer vs norm.
- [ ] **A33** **Agmarknet mandi prices** — daily, ~3,000 mandis × ~300 commodities. `agmarknet.gov.in`. Food-CPI leading indicator at granularity.
- [ ] **A34** **DPIIT PLI scheme commitments** — quarterly (scheme-wise applications + sanctioned investment + actual deployment). `dpiit.gov.in` + scheme-specific dashboards.
- [ ] **A35** **DIPAM disinvestment proceeds** — event-driven. `dipam.gov.in`.
- [ ] **A36** **Ministry of Tourism FTA (Foreign Tourist Arrivals)** — monthly. `tourism.gov.in/Statistics`.
- [ ] **A37** **NBFC sector aggregates** — quarterly. RBI NBFC publication / Financial Stability Report annex.
- [ ] **A38** **IBBI quarterly newsletter — insolvency cases** — quarterly. `ibbi.gov.in`. Corporate stress / refinancing wall proxy.
- [ ] **A39** **NSDL FPI — index-inclusion slice** — daily. Slice the existing NSDL FPI debt flow (A16) into JPM GBI-EM-eligible vs ineligible bonds, and Bloomberg EM-eligible slice. Tracks index-inclusion flow specifically.
- [ ] **A40** **DoF / FAI fertilizer prices** — monthly. `faidelhi.org` + Dept of Fertilizers subsidy dashboard.
- [x] **A41 (playground)** **FAO Food Price Index** — **6 indicators × 437 months = 2,622 obs** decoded 2026-06-10 from `fao.org/.../food_price_indices_data.csv` (47KB CSV, monthly Jan 1990 → May 2026, base 2014-2016=100). Series: HEADLINE + MEAT + DAIRY + CEREALS + OILS + SUGAR. Cross-country global benchmark; country_iso=`WLD`. See [`playground/econ/fao/fetch_fpi.py`](../../../playground/econ/fao/fetch_fpi.py).
- [ ] **A42** **Baltic Dry Index** — daily (commercial proxy via FRED `BDIY` or paid). Shipping-cost proxy.
- [ ] **A43** **SIAM auto sales** — monthly. `siam.in` press release. PVs + 2-wheelers + tractors (TAMA via separate channel for tractors — rural demand proxy).
- [ ] **A44** **GST e-Way Bill volumes** — monthly + daily. `ewaybillgst.gov.in`. Real-time trade activity proxy.

### B. Events + documents — India Cluster Map additions

- [ ] **B18** **Election Commission of India (ECI) dates** — General + State elections + by-poll dates. `eci.gov.in`. Drives federal-politics + policy-continuity risk.
- [ ] **B19** **GST Council meeting outcomes** — per-meeting notification. `gstcouncil.gov.in`. Tax-reform event corpus.
- [ ] **B20** **MoCI / DPIIT PLI scheme launches + reviews** — event press releases.
- [ ] **B21** **MoA MSP announcements** — Kharif (May/Jun) + Rabi (Oct) annual cycles.
- [ ] **B22** **IMD seasonal forecasts** — Long-Range Forecast Apr + update Jun for SW monsoon; NE-monsoon forecast Oct. Document corpus.
- [ ] **B23** **Customs notifications (CBIC)** — BCD changes, tariff revisions. `cbic.gov.in`. Trade-policy event corpus.
- [ ] **B24** **DEA Mid-Year Economic Analysis** (already in B11) — confirmed within cluster-11 coverage.

### A45 — 8-Core Industries (added 2026-06-10; previously mis-numbered A26)

- [x] **A45 (playground)** 8-Core Industries Index — same `eaindustry.nic.in` vendor as A12 WPI. One XLSX (`/eight_core_infra/Core_Industries_2011_12_{YYYYMMDD}.xlsx`) carries full history Apr 2011 → Apr 2026 (180 months). 9 sectors (Overall + Coal/Crude/NG/Petroleum/Fertilizers/Steel/Cement/Electricity) × LEVEL + YOY = **18 indicators × 3,150 obs** in playground 2026-06-10. ICI leads the IIP by ~10 days each month — important high-frequency activity indicator. Shares `dpiit` vendor migration with A12. (Numbered A45 to avoid collision with original A26 = DAC crop sowing.)

### Reachability findings (2026-06-10) for vendors NOT yet decoded

| Vendor | URL | Status | Disposition |
|---|---|---|---|
| NSDL FPI | `fpi.nsdl.co.in`, `nsdl.co.in` | `RemoteProtocolError` from our network | Needs CDP-attach or Citi feed |
| Labour Bureau | `labourbureau.gov.in/.nic.in` (all variants) | `ConnectError` | Needs CDP-attach; or use RBI Bulletin proxy |
| CWC reservoir | `cwc.gov.in/reservoir-storage` | 401 (auth required?) | Investigate auth or use water-resources dashboard alternative |
| Agmarknet | `agmarknet.gov.in/` | 403 (UA blocked?) | Try with browser UA + cookies |
| POSOCO | `posoco.in/reports/...` | `ConnectError` | Site might have moved; check `grid-india.in` or `npp.gov.in` |
| NREGA | `nrega.nic.in/` | 200 but 451-byte shell | JS-rendered or login wall |
| Ministry of Tourism | `tourism.gov.in/` | 200, 98KB | Reachable — defer parsing |
| IBBI insolvency | `ibbi.gov.in/` | 200, 2.7MB home | Reachable — defer parsing |
| FCI food stocks | `fci.gov.in/stocks.php` | 200, 45KB but no inline data | JS-rendered table — needs Playwright |
| DPIIT FDI | `dpiit.gov.in/publications/fdi-statistics` | 200, Next.js SPA | Needs deeper Playwright with click-through |
| MOSPI PLFS | listing API works, all releases PDF-only | OK but no XLSX | PDF parsing required |
| PPAC fuel | `ppac.gov.in/` | 200, all data via PDF downloads | PDF parsing required |

**Network-blocked items** are likely solvable via the same CDP-attach pattern documented for AOFM (see [[feedback-aofm-fresh-profile-per-run]] in memory) — attach to user's daily Chrome session.

### Out of scope for the initial build

- ❌ Paid feeds — S&P Global PMI · CMIE high-frequency unemployment · CEIC/Macrobond mirror
- ❌ MOSPI PPI proper (pilot only — revisit when official series launches)
- ❌ Microdata (PLFS person-level, ASI plant-level, BSR branch-level) — only published aggregates
- ⏸ State-level fiscal + state-level CPI (defer to Phase 2)

---

## Appendix B — India Cluster Map cross-check

Cross-checking the 12-cluster *India Macro Read* dashboard (see image in
docs/) against the coverage plan above. Each bullet is tagged:
- ✅ in plan already
- ⚠ partial / needs a derivation step
- ❌ missing → added to checklist Group A24+ or B18+ above
- ⏸ deferred (paid feed / structural)

### Cluster 1 — Domestic Demand / Consumption

| Bullet | Status | Mapped to |
|---|:---:|---|
| Urban demand — salaried jobs | ⚠ | A20 EPFO payroll (formal employment) |
| Urban demand — services income | ❌ | derived from PFCE services component (1.1) |
| Urban demand — credit | ✅ | A5 RBI Sectoral Deployment — Personal Loans |
| Urban demand — confidence | ✅ | A5 RBI Consumer Confidence Survey (CCS) |
| Rural demand — farm income | ❌ | requires DAC crop output × MSP × MSP-procurement composite — derived |
| Rural demand — monsoon | ✅ | A24 IMD rainfall — playground (imd_rainfall.py); All-India aggregate only; sub-divisional ⚠ |
| Rural demand — wages | ✅ | A18 Labour Bureau rural wages + WRI |
| Rural demand — transfers (MGNREGA / PM-KISAN) | ❌ | **A29 MGNREGA + A30 PM-KISAN — NEW** |
| Rural demand — MSP | ❌ | **A31 MSP — NEW** (data + B21 events) |
| Household balance sheets — savings | ⚠ | derived from BoP / household financial assets |
| Household balance sheets — debt | ✅ | BIS DSR + Credit-to-GDP + Sectoral Deployment HH |
| Household balance sheets — real rates | ⚠ | derived = Repo − CPI YoY |
| Household balance sheets — housing wealth | ❌ | **A28 NHB Residex + RBI HPI — NEW** |
| Demographics — youth / migration / participation / mix | ⏸ | Census + NSSO microdata — structural, deferred |

### Cluster 2 — Investment / Capex / Construction

| Bullet | Status | Mapped to |
|---|:---:|---|
| Private capex — profits | ⚠ | RBI Corporate Sector statistics (A7) — annual lag |
| Private capex — capacity use | ✅ | A5 RBI OBICUS survey (quarterly) |
| Private capex — policy certainty | ⏸ | qualitative — picked up via §5 event corpus |
| Private capex — cost of capital | ✅ | A5 WALR / MCLR + CCIL corp bond curve (A17) |
| Public capex — central | ✅ | A14 CGA monthly accounts (capital expenditure split) |
| Public capex — state capex | ⚠ | A6 RBI State Govt finances (annual lag) |
| Real estate — affordability | ❌ | **A28 NHB Residex / RBI HPI — NEW** |
| Real estate — approvals / inventory | ⏸ | PropEquity / Knight Frank — paid |
| Real estate — financing | ✅ | A5 RBI Sectoral Deployment — Housing Loans |
| Manufacturing push — PLI | ❌ | **A34 DPIIT PLI commitments — NEW** + B20 events |
| Manufacturing push — China+1 | ⏸ | derived from DGCIS commodity-level trade composition |
| Manufacturing push — logistics | ❌ | LPI not refreshed annually; use port throughput / e-Way Bill (A44) |
| Manufacturing push — export capacity | ✅ | A13 DGCIS exports + ITPI indices |

### Cluster 3 — Labour / Supply / Productivity

| Bullet | Status | Mapped to |
|---|:---:|---|
| Employment quantity — job creation / unemployment / LFPR | ✅ | A11 MOSPI PLFS (Annual + Quarterly Urban) |
| Employment quantity — informal vs formal | ⚠ | PLFS reports the split; EPFO (A20) tracks formal-only |
| Employment quality — wages | ✅ | A18 Labour Bureau WRI + PLFS earnings |
| Employment quality — productivity | ⚠ | derived = GVA / employment from NAS + PLFS |
| Employment quality — skill mismatch | ⏸ | NSSO unit-level surveys — deferred |
| Supply capacity — utilisation | ✅ | RBI OBICUS (cross-ref 2.3) |
| Supply capacity — bottlenecks / intermediate imports | ⚠ | DGCIS HS-chapter import composition |
| Infrastructure — ports / roads / power / digital | ❌ | port throughput (IPA), Indian Railways monthly, **A27 POSOCO — NEW**; logistics → A44 e-Way Bill |

### Cluster 4 — Agriculture / Monsoon / Food

| Bullet | Status | Mapped to |
|---|:---:|---|
| Rainfall — onset / distribution / dry spells | ✅ | A24 IMD — playground (imd_rainfall.py); All-India aggregate ✅; sub-divisional ⚠; B22 seasonal forecasts ⚠ |
| Rainfall — reservoir levels | ❌ | **A25 CWC weekly — NEW** |
| Crops — kharif / rabi / sowing / yields / acreage | ❌ | **A26 DAC sowing area — NEW** |
| Food supply — cereals / pulses / vegetables / oils / milk | ⚠ | CPI sub-groups (A8) + Agmarknet wholesale (**A33 — NEW**) + FCI stocks (**A32 — NEW**) |
| Rural spillovers — incomes / migration / demand | ⚠ | composite — derives from A29 MGNREGA + A18 rural wages + A11 PLFS rural participation |

**Cluster 4 is the single largest gap in the original plan.** Six new data series (A24-A26, A32-A33, B22) and one new vendor cascade (IMD + CWC + DAC + Agmarknet + FCI) added.

### Cluster 5 — Inflation Pipeline

| Bullet | Status | Mapped to |
|---|:---:|---|
| Food — weather / perishables / MSP / stock mgmt | ⚠ → ✅ once Cluster 4 ships | A24 IMD, A31 MSP, A32 FCI, A33 Agmarknet |
| Fuel / energy — crude / LPG / electricity / taxes | ✅ | A19 PPAC + Customs notifications (B23) |
| Core goods — import prices / FX / supply chains | ⚠ | DGCIS UVI + Citi spot + global GSCPI proxy |
| Core services — housing / health / education / telecom / wages | ⚠ | CPI sub-groups (A8) + WPI services pilot (deferred) |
| Expectations — credibility / wage indexation | ✅ | A5 RBI IESH + DA-hike events (B-class) |

### Cluster 6 — Fiscal / Public Sector

| Bullet | Status | Mapped to |
|---|:---:|---|
| Revenue — GST / income tax / corporate tax / non-tax | ✅ | A14 CGA + A23 GSTN |
| Expenditure — capex / subsidies / welfare / defence / interest | ⚠ | A14 CGA totals; subsidies + interest-bill need explicit line-items (Budget annex) |
| States — capex / power subsidies / off-budget | ⚠ | A6 RBI State Govt finances; off-budget needs Budget annex parsing |
| Debt / deficit — borrowing / fiscal impulse / crowding out | ✅ | A6 RBI Central Govt Market Borrowings + DJPPR equivalent (none for IN — RBI is the issuer) |

New: **A35 DIPAM disinvestment** added (revenue side, important budget-arithmetic item).

### Cluster 7 — Monetary / Liquidity / Rates

| Bullet | Status | Mapped to |
|---|:---:|---|
| RBI stance — repo / corridor / liquidity / communication | ✅ | A5 Key Rates + B1-B3 MPC events |
| Transmission — deposits / lending rates / MIBOR / funding costs | ✅ | A5 WALR/WAFR/WATDR + A17 MIBOR/MIFOR |
| Bond market — G-sec yields / term premium / supply / OMO | ⚠ | A17 CCIL G-sec curve; term premium derived; OMO events scattered across press releases |
| Financial conditions — real rates / liquidity / spreads / equity | ✅ | A5 Daily LAF + corp bond spreads (A17) + equity domain |

Fully covered.

### Cluster 8 — Banking / Credit / Balance Sheets

| Bullet | Status | Mapped to |
|---|:---:|---|
| Bank health — NPLs / provisioning / capital / deposits | ✅ | A7 RBI Banking Performance |
| Credit cycle — retail / MSME / corporate / NBFC / rural | ⚠ | A5 Sectoral Deployment covers retail+corporate+rural; **A37 NBFC aggregates — NEW**; MSME sub-cut needs RBI MSME annex |
| Household leverage — mortgages / personal / unsecured | ✅ | A5 Sectoral Deployment Housing + Personal |
| Corporate balance sheets — leverage / cash flows / refi / insolvency | ⚠ | A7 RBI Corporate Sector; **A38 IBBI insolvency cases — NEW** |

### Cluster 9 — External Sector / Current Account

| Bullet | Status | Mapped to |
|---|:---:|---|
| Goods trade — oil / electronics / gold / chemicals / engineering | ✅ | A13 DGCIS commodity-level (HS chapter) |
| Services exports — IT / business / tourism / GIC | ⚠ → ✅ once A36 ships | RBI BoP services breakdown (A6) + **A36 Tourism FTA — NEW** + IT exports via RBI BoP; GIC not officially tracked |
| Remittances — Gulf / US / diaspora | ✅ | A6 RBI BoP Secondary Income + Remittances Survey |
| Current account — ToT / import demand / export demand | ✅ | A6 BoP CA + DGCIS UVI |

### Cluster 10 — Capital Flows / FX / Reserves

| Bullet | Status | Mapped to |
|---|:---:|---|
| FDI — manufacturing / services / infrastructure | ✅ | A15 DPIIT FDI quarterly |
| Portfolio flows — debt / equity / global risk / **index inclusion** | ⚠ → ✅ once A39 slice ships | A16 NSDL FPI total + **A39 index-inclusion slice — NEW** |
| INR — oil / USD / carry / relative rates / intervention | ✅ | A17 + A6 RBI Sale/Purchase USD + derived carry |
| Reserves — adequacy / buffer / FX management | ✅ | A1 RBI DBIE FX reserves 5-way breakdown |

### Cluster 11 — Structural / Institutional / Political

Mostly **event corpus**, not time-series. Mapped to §5 Events:

| Bullet | Status | Mapped to |
|---|:---:|---|
| Reforms — ease of doing business / labour / land / logistics | ⚠ | Press release scrape + Parliament passage events (B-class) |
| Federal politics — state-centre / elections / continuity | ❌ | **B18 ECI election dates — NEW** |
| Digitalisation — UPI / Aadhaar / formalisation / financial inclusion | ⚠ | NPCI UPI volumes monthly (public); Aadhaar enrolment events |
| Regulation — tariffs / localisation / taxes / compliance | ⚠ | **B19 GST Council + B23 Customs notifications — NEW** |

### Cluster 12 — Global / Geopolitical / Climate

| Bullet | Status | Mapped to |
|---|:---:|---|
| Global growth — US / China / Europe / trade cycle | ✅ | covered via existing US/EU/JP/CN/HK panels |
| Commodity shocks — oil / gas / fertilizer / food | ⚠ | A19 PPAC crude ⚠ PDF-only; A40 fertilizer ❌ SPA-blocked; A41 FAO FPI ✅ playground (fao_fpi.py) |
| Geopolitics — shipping / sanctions / supply chains | ⚠ | **A42 Baltic Dry — NEW** + Suez/Red Sea events via news |
| Climate stress — heatwaves / floods / water stress / power demand | ⚠ | A24 IMD — playground (imd_rainfall.py) ✅ All-India; A25 CWC ❌ 401; A27 POSOCO ❌ ConnectError |

### Summary of gap-closures from this cluster-map cross-check

**21 new line items** added to the checklist (Group A24-A44 + B18-B23):
- 14 new data series (IMD / CWC / DAC / POSOCO / NHB / MGNREGA / PM-KISAN / FCI / Agmarknet / PLI / DIPAM / Tourism FTA / NBFC / IBBI / NSDL slice / Fertilizer / FAO / Baltic Dry / SIAM / e-Way Bill)
- 7 new event sources (ECI / GST Council / PLI scheme launches / MoA MSP / IMD seasonal forecasts / CBIC customs / DEA mid-year)

**Biggest gaps closed:** Cluster 4 (Agriculture/Monsoon, was ❌ end-to-end), Cluster 2 housing-side (NHB Residex), Cluster 11 (Structural/Political event corpus).

**Vendor cascade additions:** IMD · CWC · DAC (Dept of Ag & Coop) · POSOCO · NHB · MoRD (MGNREGA) · MoA (MSP / PM-KISAN) · FCI · Agmarknet · DPIIT (PLI) · DIPAM · Ministry of Tourism · IBBI · DoF / FAI · FAO · ECI · GST Council secretariat · CBIC. Most have no formal API — HTML scrape / XLSX / PDF.

---

## Cross-refs

- [`index.md`](index.md) — landing page + access paths.
- [`_playground/rbi.md`](_playground/rbi.md) — RBI playground state.
- [`_playground/rbi_explore.md`](_playground/rbi_explore.md) — captured screenshots.
- [`../../../playground/econ/rbi/discovery/findings.md`](../../../playground/econ/rbi/discovery/findings.md) — full DBIE endpoint catalogue.
- [`../macro_economy_wiring_map.md#712-india-in`](../macro_economy_wiring_map.md#712-india-in) — coverage tracker.
- [`../onboarding_new_country.md`](../onboarding_new_country.md) — 5-step workflow.
- [`../indonesia/id_coverage_plan.md`](../indonesia/id_coverage_plan.md) — Indonesia analogue (worked example).
- [`../korea/kosis_kr_coverage_plan.md`](../korea/kosis_kr_coverage_plan.md) — Korea analogue.
