# Korea — Government & Quasi-Government Document Sources

Last updated: 2026-06-10
Status: LIVE — daily-pull discovery running; Tier-1 agencies ingesting via filings.py (migrations 086/087 applied 2026-06-10).

This file is the master inventory of **Korean policy / macro-relevant text** sources
(Bank of Korea, ministries, regulators, statistical agencies, quasi-government
think-tanks, fiscal council, debt/market infrastructure, pensions/SWF, state
banks). Sell-side research (JPM/MS/Goldman/etc.) is already covered in the
broader research/Qdrant corpus; this document is the **official-voice
counterpart** that has not been ingested yet.

The 9 entries already listed in [`index.md`](./index.md) under "Policy & fiscal
document sources" are merged in below and marked **(already-known)**. Anything
without that tag was newly surfaced by 2026-06-09 web research.

Crawl-complexity flag legend:
- **LOW** — RSS feed or stable static HTML listing
- **MED** — search-hub, AJAX listing with predictable parameters, or sitemap walk
- **HIGH** — JS-rendered SPA, login-aware, or session-coupled archive
- **BLOCKED** — corp-firewall / TLS-inspection issues likely (AOFM-style); unknown

URLs marked with **❓** are unverified to current shape (page existed at one
point but listing mechanism not confirmed in this research pass).

---

## 1. Central bank — Bank of Korea (BoK / 한국은행)

| # | Stream | URL | Cadence | Lang | Listing | Auth | Crawl | Why it matters |
|---|---|---|---|---|---|---|---|---|
| 1.1 | Monetary Policy Decision & Opening Remarks **(already-known)** | https://www.bok.or.kr/eng/bbs/E0000634/list.do?menuNo=400069 | per meeting (~8/yr) | EN/KO | AJAX listing (`bbs/.../list.do`) | none | MED | Verbatim policy decision + governor opening statement |
| 1.2 | Monetary Policy Decisions board **(separate menu)** | https://www.bok.or.kr/eng/bbs/E0000627/list.do?menuNo=400022 | per meeting | EN/KO | AJAX listing | none | MED | Same content as 1.1 indexed under "Monetary Policy" menu; dedupe vs 1.1 |
| 1.3 | MPC Minutes **(already-known)** | https://www.bok.or.kr/eng/bbs/E0000634/list.do?menuNo=400069 (kwd "Minutes of the Monetary Policy Board Meeting") | per meeting (lagged ~2 wks) | EN/KO | search-hub on press release board | none | MED | Granular vote breakdown, dovish/hawkish dissent count |
| 1.4 | Monetary Policy Report **(already-known)** | https://www.bok.or.kr/eng/bbs/E0000628/list.do?menuNo=400215 | semi-annual (Mar/Sep) | EN/KO | AJAX listing | none | MED | Forecast layer, macroprudential commentary |
| 1.5 | Korea Economic Outlook **(already-known)** | https://www.bok.or.kr/eng/bbs/E0000634/list.do?menuNo=400069 (kwd "Korea Economic Outlook") | quarterly | EN/KO | search-hub | none | MED | GDP / CPI forecast updates — moves curve |
| 1.6 | Recent Economic Developments **(already-known)** | same search hub, kwd "Recent Economic Developments" | quarterly (between MPRs) | EN/KO | search-hub | none | MED | High-freq state-of-economy assessment |
| 1.7 | Governor / Board speeches **(already-known)** | same search hub, kwd "Speech" | regular (~2–3/mo) | EN/KO | search-hub | none | MED | Forward guidance + cross-asset signal |
| 1.8 | Financial Stability Report (FSR) | https://www.bok.or.kr/eng/bbs/E0000737/list.do?menuNo=400219 | semi-annual (Jun/Dec) | EN/KO | AJAX listing | none | MED | Household-debt / property-market risk read |
| 1.9 | BOK Working / Discussion Papers (Research dept) | https://www.bok.or.kr/eng/bbs/B0000268/list.do?menuNo=400067 | rolling (~30/yr) | EN+KO mix | AJAX listing | none | MED | Methodology preview of future official-stance shifts |
| 1.10 | BOK Working Paper (ERI English channel) | https://www.bok.or.kr/imerEng/bbs/B0000268/list.do?menuNo=600354 | rolling | EN | AJAX listing | none | MED | English-only mirror — overlaps 1.9, pick canonical |
| 1.11 | BOK Issue Notes | (no stable English landing — surfaces via 1.1 search hub kwd "BOK Issue Note") ❓ | event-driven (~12+/yr) | KO primary, occasional EN | search-hub | none | MED | Topical analytic notes (e.g. "Issue Note 2026-12 AI productivity") — punchier than working papers |
| 1.12 | Annual Report | https://www.bok.or.kr/eng/bbs/E0000740/list.do?menuNo=400221 | annual | EN/KO | AJAX listing | none | LOW | Reference doc; lower-freq signal |
| 1.13 | Quarterly Bulletin (DISCONTINUED) | https://www.bok.or.kr/eng/bbs/E0000628/list.do?menuNo=400216 | discontinued | EN | listing remains for historical | none | LOW | Skip for going-forward ingest; archive value only |
| 1.14 | BOK Regional Economic Report ("Golden Book") | (same Periodicals menu — Korean portal `bok.or.kr/portal/...`) ❓ | quarterly | KO primary, EN summary | AJAX listing | none | MED | Beige-book analogue: 16 regional offices' assessments |
| 1.15 | Economic Research Institute (ERI) — Economic Analysis journal | https://www.bok.or.kr/imerEng/main/contents.do?menuNo=600345 | quarterly | KO primary | listing page | none | MED | Academic journal — lowest urgency |
| 1.16 | ERI — Korean Economy book series | https://www.bok.or.kr/eng/bbs/E0000744/list.do?menuNo=400227 | irregular | EN | AJAX listing | none | LOW | Book-length — reference only |
| 1.17 | Press Releases (all-other / cross-cutting) | https://www.bok.or.kr/eng/bbs/E0000634/list.do?menuNo=400069 | daily-ish | EN/KO | AJAX listing | none | MED | FX intervention, swap-line, data releases (BoP, IIP, GDP advance) |
| 1.18 | BOK Newsletter Service (email push) | https://www.bok.or.kr/eng/singl/newsLetter/reqInput.do?menuNo=400236 | release-driven | EN | email subscription | email | LOW | Convenience push channel — not a crawl target by itself |

**BoK note**: there is no clean per-publication RSS endpoint exposed on
`bok.or.kr/eng`. All publication boards follow the same `bbs/{boardId}/list.do`
AJAX pattern. Standard list-then-detail crawl applies.

---

## 2. Cabinet ministries

| # | Stream | URL | Cadence | Lang | Listing | Auth | Crawl | Why it matters |
|---|---|---|---|---|---|---|---|---|
| 2.1 | **MOEF** press releases (RSS) **(already-known)** | http://english.moef.go.kr/pc/engmosfrss.do?boardCd=N0001 | regular (daily) | EN | RSS | none | LOW | Headline fiscal/FX/macro announcements |
| 2.2 | **MOEF** budget/fiscal management (RSS) **(already-known)** | http://english.moef.go.kr/ec/engmosfpolicyrss.do?boardCd=E0002 | event-driven | EN | RSS | none | LOW | Supplementary budgets — regime input |
| 2.3 | **MOEF** treasury/debt (RSS) **(already-known)** | http://english.moef.go.kr/ec/engmosfpolicyrss.do?boardCd=E0009 | regular | EN | RSS | none | LOW | KTB issuance plans (monthly), borrowing strategy |
| 2.4 | **MOEF** government-wide cooperation (RSS) | http://english.moef.go.kr/ec/engmosfpolicyrss.do?boardCd=E0001 | event-driven | EN | RSS | none | LOW | Inter-ministerial econ packages |
| 2.5 | **MOEF** tax & customs (RSS) | http://english.moef.go.kr/ec/engmosfpolicyrss.do?boardCd=E0003 | event-driven | EN | RSS | none | LOW | Tax-code shifts → corp earnings outlook |
| 2.6 | **MOEF** public institutions policy (RSS) | http://english.moef.go.kr/ec/engmosfpolicyrss.do?boardCd=E0004 | event-driven | EN | RSS | none | LOW | SOE governance / public-corp reform |
| 2.7 | **MOEF** international economic affairs (RSS) | http://english.moef.go.kr/ec/engmosfpolicyrss.do?boardCd=E0007 | event-driven | EN | RSS | none | LOW | FX swap lines, G20, IMF Article IV |
| 2.8 | **MOEF** speeches (DPM/Finance Minister) (RSS) | http://english.moef.go.kr/mi/engmosfpublicrss.do?boardCd=M0002 | regular | EN | RSS | none | LOW | DPM Koo (current as of 2026) — verbatim views |
| 2.9 | **MOEF** media schedule (RSS) | http://english.moef.go.kr/pc/engmosfrss.do?boardCd=N0002 | weekly | EN | RSS | none | LOW | Forward calendar of releases |
| 2.10 | **MOEF** KTB portal (auction results + issuance plans) | https://ktb.moef.go.kr/eng/aucRes.do | per auction (~3/mo) | EN | HTML table | none | LOW | Primary-market auction tails, bid-cover ratios |
| 2.11 | **MOEF** "Green Book" — Current Economic Situation monthly | https://english.moef.go.kr/pc/selectTbPressCenterList.do?boardCd=N0001 (kwd "Current Economic Situation") | monthly | EN | search-hub (overlaps 2.1) | none | LOW | MOEF's own monthly state-of-economy narrative — distinct voice from BoK 1.6 |
| 2.12 | **MOTIE** press releases | https://english.motie.go.kr/eng/article/EATCLdfa319ada/{seq}/view (listing entry under PRESS CENTER) | regular (daily) | EN | HTML listing | none | MED | Monthly trade/export statistics narrative (first-of-month release) |
| 2.13 | **MOTIE** monthly export/import release | (within 2.12, identifiable by title pattern "Exports in {Month} {Year}") | monthly (1st business day) | EN | HTML | none | MED | THE canonical Korea export read — drives KRW + KOSPI |
| 2.14 | **MOLIT** press releases (housing policy) | https://www.molit.go.kr/english/USR/WPGE0201/m_28266/DTL.jsp ❓ (English subsite has limited listing — Korean portal has the comprehensive archive) | regular | EN limited / KO comprehensive | HTML | none | MED | Housing supply policy, jeonse market interventions, LTV/DSR macroprudential overlap |
| 2.15 | **MoEL** (Employment & Labor) News | https://www.moel.go.kr/english/news/moelNews.do | regular | EN | HTML listing | none | LOW | Wage-bargaining, minimum-wage decisions, employment situation commentary |
| 2.16 | **MoEL** publications | https://www.moel.go.kr/english/pas/pasPubli.jsp | irregular | EN | HTML listing | none | LOW | White papers, labor statistics yearbooks |
| 2.17 | **MoFA** press releases (sanctions/econ-relevant) | https://www.mofa.go.kr/eng/brd/m_5676/list.do | regular | EN | HTML listing | none | LOW | Russia / DPRK / sanctions enforcement — geopolitical risk for FX |
| 2.18 | **MOIS** (Interior & Safety) press releases | https://www.mois.go.kr/eng/sub/a02/aboutMinistry/screen.do (English portal sparse; Korean has full archive) ❓ | regular | EN limited | HTML | none | MED | Local fiscal transfers, election admin (limited macro signal) |
| 2.19 | **Office of the President** briefing room | https://eng.president.go.kr/briefing | event-driven | EN | HTML listing | none | LOW | Presidential statements on econ policy, summits, vetoes |
| 2.20 | **korea.net** Briefing Room (all-gov hub) | https://www.korea.net/Government/Briefing-Room/Press-Releases | daily | EN | HTML listing w/ filter by `insttCode` | none | LOW | Single aggregator covering >40 agencies — useful as crawl-spine even if dedupe overhead |
| 2.21 | **korea.net** Presidential Speeches | https://www.korea.net/Government/Briefing-Room/Presidential-Speeches | event-driven | EN | HTML listing | none | LOW | Verbatim presidential speeches in EN |

---

## 3. Financial-system regulators

| # | Stream | URL | Cadence | Lang | Listing | Auth | Crawl | Why it matters |
|---|---|---|---|---|---|---|---|---|
| 3.1 | **FSC** press releases (English) | https://www.fsc.go.kr/eng/pr010101 | daily-ish | EN | HTML listing w/ `srchCtgry` filter | none | MED | Macroprudential rules (LTV/DSR), household-debt envelope, capital-market rules |
| 3.2 | **FSC** Korean press release archive | https://www.fsc.go.kr/no010101 ❓ | daily-ish | KO | HTML listing | none | MED | More-granular than English mirror; ~2x volume |
| 3.3 | **FSS** press releases (English) | https://fss.or.kr/eng/bbs/B0000211/list.do?menuNo=400010 | regular | EN | AJAX listing | none | MED | Banking-sector reviews, NPL ratios, loan-classification stats |
| 3.4 | **FSS** publications (annual reports, financial statistics) | https://www.fss.or.kr/eng/main/main.do (Publications menu) ❓ | annual / quarterly | EN | listing | none | MED | Bank capital adequacy, FX-loan supervision |
| 3.5 | **FSS** English DART (corporate filings repo) | https://englishdart.fss.or.kr/ | daily | EN | search + listing | none | HIGH | Single-name corp filings — out of scope (sell-side already covers); included for completeness |
| 3.6 | **KOFIA** publications (capital markets self-reg) | https://eng.kofia.or.kr/brd/m_20/list.do | irregular | EN | HTML listing | none | LOW | Market structure changes, retail-investor stats (FREESIS) |
| 3.7 | **KOFIA** Annual Review | https://eng.kofia.or.kr/brd/m_20/list.do (filter Annual Review) | annual | EN | HTML | none | LOW | Industry survey — reference only |
| 3.8 | **KCMI** (Capital Market Institute) research | https://www.kcmi.re.kr/en/ ❓ | rolling | EN/KO | HTML listing | none | MED | Independent capital-market policy commentary (gov-funded think-tank but adjacent to FSC) |

---

## 4. Statistical agencies

| # | Stream | URL | Cadence | Lang | Listing | Auth | Crawl | Why it matters |
|---|---|---|---|---|---|---|---|---|
| 4.1 | **KOSTAT** / Ministry of Data & Statistics — Press Releases (English) | https://kostat.go.kr/menu.es?mid=a20101010000 ❓ | per release | EN | listing | none | LOW | CPI, IIP, retail, employment narratives — pair with KOSIS time series |
| 4.2 | **KOSTAT** CPI press release archive | https://mods.go.kr/menu.es?mid=a20109020000 | monthly | EN | HTML listing | none | LOW | The narrative attached to each CPI print |
| 4.3 | **KOSTAT** statistical-calendar schedule | https://kostat.go.kr/menu.es?mid=a20301000000 | continuous | EN | HTML | none | LOW | Forward calendar of releases (overlaps 2.9) |
| 4.4 | **MODS** (Ministry of Data & Statistics — successor brand) Press Center | https://mods.go.kr/ (top-level press hub) | per release | EN/KO | HTML listing | none | MED | New branding 2025+; URL transition risk — watch for redirect |
| 4.5 | **KCS** (Korea Customs Service) Trade Statistics narrative | https://www.customs.go.kr/english/main.do (press / news menu) ❓ | 10-day (1st/11th/21st-day quick estimates) + monthly final | EN partial | HTML listing | none | MED | **10-day quick trade estimates** are the highest-freq Korea trade signal; precedes MOTIE monthly |
| 4.6 | **KCS** Unipass trade data portal | https://unipass.customs.go.kr/ets/index_eng.do | continuous | EN | data portal | none | MED | Data-extraction side; narrative is on customs.go.kr main |
| 4.7 | **KITA** (Korea International Trade Association) Monthly Trade Report | https://kita.org/kitaTradeReport/kitaTradeReport/kitaTradeReportList.do | monthly | KO primary, EN summaries | HTML listing | none | MED | Industry-association commentary on monthly trade; complements MOTIE 2.13 |
| 4.8 | **KITA** Institute of Intl Trade research | https://www.kita.org/ (research menu) ❓ | rolling | EN/KO | listing | none | MED | Sector / country deep-dives |

---

## 5. Quasi-government think tanks (para-public voice)

These are state-funded research institutes that act as policy-signal amplifiers
for their lead ministries (KDI ↔ MOEF, KIET ↔ MOTIE, etc.). All are nominally
independent; in practice their forecasts and policy recommendations are highly
correlated with ministry stance.

| # | Stream | URL | Cadence | Lang | Listing | Auth | Crawl | Why it matters |
|---|---|---|---|---|---|---|---|---|
| 5.1 | **KDI** Economic Outlook (semi-annual) | https://www.kdi.re.kr/eng/research/economy | 2× / yr (May / Nov) | EN/KO | HTML listing | none | LOW | KDI's main forecast — KDI ↔ MOEF channel |
| 5.2 | **KDI** Monthly Economic Trends | https://www.kdi.re.kr/eng/research/monTrends | monthly | EN/KO | HTML listing | none | LOW | High-freq state-of-economy from semi-official voice |
| 5.3 | **KDI** Economic Bulletin | https://www.kdi.re.kr/eng/research/monEb | monthly | EN | HTML listing | none | LOW | English-first monthly digest |
| 5.4 | **KDI** Current Affairs / analysis | https://www.kdi.re.kr/eng/research/analysisList | event-driven | EN | HTML listing | none | LOW | One-off policy notes (e.g. potential growth, fertility) |
| 5.5 | **KDI** Journal of Economic Policy | https://www.kdi.re.kr/eng/... ❓ | quarterly | EN | listing | none | LOW | Academic journal — low signal urgency |
| 5.6 | **KIEP** Working Papers | https://www.kiep.go.kr/gallery.es?mid=a20305000000&bid=0001&cg_code=C08 | rolling | EN | HTML listing | none | LOW | External-balance, capital-flow research |
| 5.7 | **KIEP** World Economic Outlook (annual) | https://www.kiep.go.kr/eng/ (Publications) ❓ | annual | EN | listing | none | LOW | Global view through Korean lens |
| 5.8 | **KIEP** APEC Study Series / Policy References | https://www.kiep.go.kr/eng/ ❓ | irregular | EN | listing | none | LOW | Regional integration / FTA topics |
| 5.9 | **KIF** Korea Institute of Finance publications | https://www.kif.re.kr/kif4/eng/publication/pub_list?mid=222 | rolling | EN partial / KO primary | HTML listing | none | MED | Banking + capital-markets policy research |
| 5.10 | **KIF** Journal of Money & Finance | https://www.kif.re.kr/kif4/eng/ ❓ | quarterly | EN | listing | none | LOW | Academic — lower freq |
| 5.11 | **KIF** Financial Research Brief | https://www.kif.re.kr/kif4/eng/ ❓ | weekly-ish | KO primary | listing | none | MED | Punchier note format; KO-heavy |
| 5.12 | **KCIF** (Center for International Finance) reports | https://www.kcif.or.kr/report/reportList (KO) · https://www.kcif.or.kr/eng (EN) · https://www.kcifny.org/eng/board/newsList (NY office) | daily-ish | KO primary, EN partial | HTML listing | login on some content | HIGH | **The de-facto FX/global-markets early-warning desk for MOEF + BoK; subscriber-gated for many reports — may need user/MOEF cred** |
| 5.13 | **KIET** Industrial Economic Review | https://www.kiet.re.kr/en/pub/ecoreview | monthly | EN | HTML listing | none | LOW | Sector / industrial-policy outlook |
| 5.14 | **KIET** Monthly Industrial Economics | https://www.kiet.re.kr/en/pub/economy | monthly | EN | HTML listing | none | LOW | Manufacturing PMI-equivalent commentary |
| 5.15 | **KIET** i-KIET Issues & Analysis | https://www.kiet.re.kr/en/pub/issueList | rolling | EN | HTML listing | none | LOW | Topical industrial-policy notes (e.g. US chip-export controls) |
| 5.16 | **KIET** Research Reports | https://www.kiet.re.kr/en/pub/reportList | rolling | EN | HTML listing | none | LOW | Long-form research |
| 5.17 | **KLI** (Labor Institute) Publications in English | https://www.kli.re.kr/kli_eng/selectEngPblctListList.do?key=218 | rolling | EN | HTML listing | none | LOW | Wage / hours / labor-market structural research |
| 5.18 | **KLI** Employment & Labor Brief | https://www.kli.re.kr/kli_eng/selectEngPdicalList.do?key=440&schPdicalKnd=4 | quarterly | EN | HTML listing | none | LOW | Concise English digest |
| 5.19 | **KLI** Monthly Labor Review | https://www.kli.re.kr/kli_eng/engPdicalView.do?key=437&pblctListNo=6300&schPdicalKnd=1 | monthly | KO primary, EN partial | listing | none | MED | KO-language flagship |
| 5.20 | **KIPF** Korea Institute of Public Finance | https://www.kipf.re.kr/eng/index.do | rolling | EN | HTML listing | none | LOW | Tax / public-finance research — MOEF channel |
| 5.21 | **KIPF** Open Access Repository | https://repository.kipf.re.kr/ | rolling | KO primary | repo listing | none | MED | Full back-catalogue archive |
| 5.22 | **KRIHS** Korea Research Institute for Human Settlements | https://www.krihs.re.kr/eng/ · https://eng.krihs.re.kr/ | rolling | EN/KO | HTML listing | none | MED | **Housing / jeonse market deep-dives** — complements MOLIT 2.14 + REB time series |
| 5.23 | **STEPI** Science & Technology Policy Institute | https://www.stepi.re.kr/site/stepien/main.do | rolling | EN | HTML listing | none | LOW | Tech / semi / R&D policy — adjacent to MOTIE |
| 5.24 | **KEEI** Korea Energy Economics Institute | https://www.keei.re.kr/eng | rolling | EN partial / KO primary | HTML listing | subscription on some | MED | Energy outlook, oil/gas/power balance — KRW current-account driver |

---

## 6. Fiscal council & legislative research

| # | Stream | URL | Cadence | Lang | Listing | Auth | Crawl | Why it matters |
|---|---|---|---|---|---|---|---|---|
| 6.1 | **NABO** (National Assembly Budget Office) Publications in English | https://korea.nabo.go.kr/En//notiComm/findPublicationsInfo.do?boardId=3350 ❓ (entry varies) | rolling | EN | HTML listing | none | MED | Independent budget / fiscal projections — counterweight to MOEF |
| 6.2 | **NABO** Economic Outlook | https://korea.nabo.go.kr/En/report/findPolicyInfo.do?gubunCd=B154002 ❓ | annual + updates | EN | HTML listing | none | MED | Macro forecast distinct from KDI/MOEF |
| 6.3 | **NABO** Long-term Fiscal Projections (50-year) | (within 6.1, "NABO Long-term Fiscal Projections 2025-2072") | every ~5 years | EN | PDF | none | LOW | Demographic/fiscal sustainability — sovereign rating input |
| 6.4 | **NABO** Focus / Industry Trends & Issues | https://korea.nabo.go.kr/En/notiComm/findPublicationsAllInfo.do?boardId=2960 ❓ | rolling | EN | HTML listing | none | MED | Shorter bulletins |
| 6.5 | **NARS** (National Assembly Research Service) | https://www.nars.go.kr/eng/index.do | irregular | EN limited | HTML listing | none | MED | Legislative briefs — less macro, more policy-mechanics |

---

## 7. Debt management / deposit insurance / state banks

| # | Stream | URL | Cadence | Lang | Listing | Auth | Crawl | Why it matters |
|---|---|---|---|---|---|---|---|---|
| 7.1 | **MOEF / PDMO** KTB Issuance Plan (monthly) | https://english.moef.go.kr/pc/selectTbPressCenterList.do?boardCd=N0001 (filter title "KTB Issuance Plan, {Month} {Year}") | monthly | EN | HTML | none | LOW | Korea has no separate PDMO — debt management sits inside MOEF Treasury Bureau; covered via 2.3 + 2.10 |
| 7.2 | KTB Auction Results | https://ktb.moef.go.kr/eng/aucRes.do | per auction | EN | HTML table | none | LOW | Bid-cover, stop-out yield, tail |
| 7.3 | **KDIC** Korea Deposit Insurance Corp — Press / Brochures | https://www.kdic.or.kr/en/eng/selectbrochureDtl.do | irregular | EN | HTML listing | none | MED | Bank-resolution / risk-surveillance commentary |
| 7.4 | **KDIC** Annual Reports / Statistics | https://www.kdic.or.kr/en/eng/ (Publications menu) ❓ | annual | EN | listing | none | LOW | Insured-deposit base, NPL coverage |
| 7.5 | **KDB** Korea Development Bank — IR / Annual Report | https://www.kdb.co.kr/CHGLIR05N00.act?_mnuId=IHIHEN0028&JEX_LANG=EN | annual + investor decks | EN | HTML listing | none | LOW | State-bank balance-sheet view; quasi-sovereign credit |
| 7.6 | **KDB** research (industry analysis) | https://www.kdb.co.kr/ (research menu) ❓ | rolling | KO primary | listing | none | MED | Industry / sector reports parallel to KIET 5.13 |
| 7.7 | **KEXIM** Korea Eximbank — research | https://www.koreaexim.go.kr/ ❓ (English: https://www.koreaexim.go.kr/site/main/index003 ❓) | rolling | EN partial | listing | none | MED | Overseas-investment, EM credit, EDCF — quasi-MOFA |
| 7.8 | **KAMCO** Korea Asset Management Corp — IR | https://www.kamco.or.kr/eng/ | irregular | EN | listing | none | LOW | NPL resolution, public asset disposal |
| 7.9 | **HF** Korea Housing Finance Corp — IR / Reports | https://www.hf.go.kr/en/sub04/sub04_03.do | annual + ad hoc | EN | HTML | none | LOW | Mortgage / MBS issuance, bogeumjari loan stats — housing-market read |

---

## 8. Market infrastructure

| # | Stream | URL | Cadence | Lang | Listing | Auth | Crawl | Why it matters |
|---|---|---|---|---|---|---|---|---|
| 8.1 | **KRX** Korea Exchange — market notices (Global site) | https://global.krx.co.kr/main/main.jsp | continuous | EN | HTML listing | none | MED | Circuit breakers, short-sale rule changes, listing-eligibility |
| 8.2 | **KRX** Information Data System (KIND) | https://data.krx.co.kr/contents/MDC/MAIN/main/index.cmd?locale=en | continuous | EN | data portal | none | HIGH | Time series side — out of scope for doc corpus |
| 8.3 | **KRX** ESG / disclosure announcements ❓ | within 8.1 | event-driven | EN | HTML | none | MED | Tagged disclosures (e.g. fair-disclosure violations) |
| 8.4 | **KSD** Korea Securities Depository — Press | https://www.ksd.or.kr/en/ (News menu) ❓ | irregular | EN | HTML listing | none | MED | Cross-border holdings, foreign-investor settlement data |
| 8.5 | **KOSCOM** (KRX subsidiary, market data) ❓ | https://www.koscom.co.kr/eng/ ❓ | irregular | EN limited | listing | none | MED | Infra-side notices |

---

## 9. Pensions & sovereign wealth

| # | Stream | URL | Cadence | Lang | Listing | Auth | Crawl | Why it matters |
|---|---|---|---|---|---|---|---|---|
| 9.1 | **NPS** Investment Management **(already-known)** | https://fund.nps.or.kr/eng/main.do | rolling | EN | HTML hub | none | MED | KRW 1,000+ tn fund — allocation shifts move KRW + KTB |
| 9.2 | **NPS** Annual / Sustainability Reports | https://fund.nps.or.kr/eng/orinsm/ovvw/getOHFD0013M0.do ❓ | annual | EN | HTML / PDF | none | LOW | Strategic asset allocation, target weights |
| 9.3 | **NPS** Responsible Investment & Governance Report | https://fund.nps.or.kr/eng/riacvt/overview/getOHFE0001M0.do | annual | EN | HTML | none | LOW | ESG / engagement disclosures |
| 9.4 | **KIC** Korea Investment Corporation — Annual Report | https://www.kic.kr/en/04/02/01.jsp | annual | EN | HTML | none | LOW | Sovereign wealth fund ($200B+ AUM) — global allocation view |
| 9.5 | **KIC** Sustainable Investment Report | within 9.4 | annual | EN | PDF | none | LOW | TCFD-aligned disclosures |
| 9.6 | **GEPS** Government Employees Pension Service | https://www.geps.or.kr/en/benefit_pension-system | irregular | EN limited | HTML | none | MED | $30B+ fund — secondary to NPS |
| 9.7 | **KTP** Korea Teachers' Pension | https://www.ktpf.or.kr/ ❓ (EN limited) | irregular | KO primary | HTML | none | HIGH | $15B+ fund; coverage gappy in English |
| 9.8 | **POBA** Public Officials Benefit Association | https://www.poba.or.kr/ ❓ (EN limited) | irregular | KO primary | HTML | none | HIGH | Local-gov officials pension; PE/RE-heavy allocator |
| 9.9 | **Private School Teachers Pension** (sa-rip / TP) ❓ | (separate from KTP — TPS site) ❓ | irregular | KO | listing | none | HIGH | Smaller fund; low priority |

---

## 10. Other / cross-cutting

| # | Stream | URL | Cadence | Lang | Listing | Auth | Crawl | Why it matters |
|---|---|---|---|---|---|---|---|---|
| 10.1 | **Korea.net** consolidated press hub | https://www.korea.net/Government/Briefing-Room/Press-Releases | daily | EN | filterable HTML listing | none | LOW | Single feed covering most ministries — high-recall spine for any gap-fill strategy (overlaps but dedupe-friendly) |
| 10.2 | **PIPC** Personal Information Protection Commission ❓ | https://www.pipc.go.kr/eng/ ❓ | irregular | EN | listing | none | MED | Data-protection rulings — low macro signal, fintech tail-risk |
| 10.3 | **KFTC** Korea Fair Trade Commission ❓ | https://www.ftc.go.kr/eng/ ❓ | regular | EN | listing | none | MED | M&A rulings, chaebol governance — earnings-pass-through angle |
| 10.4 | **KEPCO** Korea Electric Power IR / tariff filings ❓ | https://home.kepco.co.kr/kepco/EN/main.do ❓ | quarterly + tariff events | EN | HTML | none | MED | Electricity tariff = CPI sub-component swing; SOE-credit angle |

---

## Coverage observations

1. **Bank of Korea is one site, ~14 distinct streams** — they all live under
   `bok.or.kr/eng/bbs/{boardId}/list.do`. The same content sometimes appears
   under multiple `menuNo` paths (e.g. Monetary Policy Decision shows up in
   board E0000627 AND E0000634). A single AJAX-listing crawler with
   per-board configs handles them all; dedupe by `nttId`.

2. **MOEF has 10 distinct RSS endpoints** (N0001, E0001–E0007, E0009, M0001,
   M0002, N0002). The three already-known (N0001, E0002, E0009) miss
   tax-customs (E0003), public-institutions (E0004), international (E0007),
   and DPM speeches (M0002) — all of which carry direct macro signal. **The
   inventory should formalize all 10 RSS feeds, not just 3.**

3. **MOEF "Green Book" Current Economic Situation, BoK "Recent Economic
   Developments", KDI "Monthly Economic Trends", and NABO Economic Outlook
   are four parallel monthly state-of-economy narratives** — same data,
   four distinct policy voices. Trader-useful precisely because they
   diverge at the margin (e.g. KDI more dovish than MOEF during pre-rate-cut
   periods). Keep all four; don't dedupe across institutions.

4. **MOTIE monthly exports + KCS 10-day quick estimates + KITA monthly
   trade report = the export-narrative triple-stream**. KCS 10-day is the
   highest-frequency Korea trade signal anywhere — it precedes the
   MOTIE month-end release.

5. **No separate Public Debt Management Office** — Korea's PDMO function
   is inside MOEF Treasury Bureau. KTB issuance plans and auction results
   are MOEF outputs (covered by 2.3 / 2.10 / 7.1 / 7.2 — same content,
   different access paths).

6. **KCIF is the highest-value, hardest-access source** — KCIF's daily
   global-markets reports are how the BoK FX desk and MOEF International
   Bureau staff start their day. Much of the high-signal content is
   subscriber-gated (paid corporate / government access). Cleanly-public
   content is thin. Treat as Tier-1 ambition but Tier-2/HIGH-complexity
   in practice.

7. **BOK Issue Notes are KO-primary** — the headline BOK Working Papers
   board is bilingual, but Issue Notes (punchier, more topical) are
   primarily Korean. If single-language constraint applied, would drop
   into Tier 2.

8. **English coverage is thinner than it appears at first pass** —
   MOLIT, MOIS, KIF Financial Research Brief, KCIF reports, KOFIA Korean
   feed, KLI Monthly Labor Review, KEEI, KAMCO, KEXIM, KTP, POBA all
   have richer Korean archives than English mirrors. Korean-language
   ingest expands the addressable corpus by ~2–3×, but adds OCR /
   translation pipeline burden.

9. **Korea.net is the cross-government aggregator** — if a build-time
   trade-off arises ("crawl 30 sites or one aggregator"), korea.net
   single-handedly covers >40 ministries and quasi-gov bodies. Useful
   as a recall spine; not a substitute for direct site crawls (loses
   structured metadata + lags by 1–2 days).

10. **Two press-hub URL families to watch for transition risk**: KOSTAT
    is migrating to `mods.go.kr` (Ministry of Data & Statistics rebrand,
    2025+). MOEF has been stable for ~5 years. KRX has a separate
    `global.krx.co.kr` mirror that lags the Korean site.

---

## Recommended priority tiers

### Tier 1 — must-have for policy reasoning (≈15 streams)

Anything that directly drives KRW / KTB / KOSPI within 24h of release, OR
contains the canonical policy text behind a market-moving decision.

- 1.1 BoK Monetary Policy Decision & Opening Remarks
- 1.3 BoK MPC Minutes
- 1.4 BoK Monetary Policy Report
- 1.5 BoK Korea Economic Outlook
- 1.7 BoK Governor / Board speeches
- 1.8 BoK Financial Stability Report
- 1.11 BoK Issue Notes (event-driven topical notes)
- 1.17 BoK Press Releases (FX intervention, BoP, GDP advance)
- 2.1 / 2.3 / 2.10 MOEF Press, Treasury RSS, KTB portal
- 2.8 MOEF DPM speeches
- 2.11 MOEF "Green Book"
- 2.13 MOTIE monthly export release
- 3.1 FSC press releases (macroprudential / household-debt)
- 4.5 KCS 10-day trade quick estimates
- 5.1 / 5.2 / 5.3 KDI Economic Outlook + Monthly Trends + Bulletin

### Tier 2 — useful colour (≈20 streams)

Adds depth, divergence signal, or sector-specific insight; not market-moving
on release.

- 1.6 BoK Recent Economic Developments
- 1.9 / 1.10 BoK Working Papers (EN + ERI)
- 1.14 BoK Regional Economic Report ("Golden Book")
- 2.2 / 2.4 / 2.5 / 2.7 MOEF budget / cooperation / tax / international RSS feeds
- 2.12 MOTIE other press releases
- 2.14 MOLIT housing policy (Korean-side adds value)
- 2.15 MoEL news
- 2.17 MoFA sanctions
- 2.19 Presidential briefings
- 3.3 FSS press releases
- 3.8 KCMI research
- 4.2 KOSTAT CPI narratives (companion to time series)
- 4.7 KITA Monthly Trade Report
- 5.6 / 5.7 KIEP Working Papers + WEO
- 5.9 KIF Korea Institute of Finance publications
- 5.12 KCIF reports (the public-side ones)
- 5.13 / 5.14 / 5.15 KIET monthly publications
- 5.22 KRIHS housing research
- 6.1 / 6.2 NABO publications + Economic Outlook
- 9.1 / 9.4 NPS Investment Management + KIC annual

### Tier 3 — nice-to-have / sectoral / academic (≈25+ streams)

Reference material, academic depth, or sectoral angles with low macro
signal. Defer until Tier 1–2 are operational.

- 1.12 / 1.13 / 1.15 / 1.16 BoK Annual / discontinued QB / Economic Analysis journal / Korean Economy book series
- 2.6 MOEF public institutions policy
- 2.9 MOEF media schedule
- 2.16 MoEL publications
- 2.18 MOIS press releases
- 2.20 / 2.21 korea.net aggregators
- 3.2 FSC Korean press archive
- 3.4 FSS publications
- 3.5 FSS English DART (out of corpus scope)
- 3.6 / 3.7 KOFIA
- 4.1 / 4.3 / 4.4 KOSTAT press / calendar / MODS hub
- 4.6 KCS Unipass portal
- 4.8 KITA Institute research
- 5.4 / 5.5 KDI Current Affairs + Journal
- 5.8 KIEP APEC / Policy References
- 5.10 / 5.11 KIF Journal + Financial Research Brief
- 5.16 KIET Research Reports
- 5.17 / 5.18 / 5.19 KLI publications
- 5.20 / 5.21 KIPF + repository
- 5.23 STEPI
- 5.24 KEEI
- 6.3 / 6.4 NABO long-term + Focus
- 6.5 NARS
- 7.3 / 7.4 KDIC
- 7.5 / 7.6 KDB
- 7.7 KEXIM
- 7.8 KAMCO
- 7.9 HF
- 8.1 / 8.3 / 8.4 / 8.5 KRX notices, KSD, KOSCOM
- 9.2 / 9.3 NPS reports
- 9.5 KIC sustainability
- 9.6–9.9 GEPS / KTP / POBA / Private School Teachers
- 10.2 / 10.3 / 10.4 PIPC / KFTC / KEPCO

---

## Crawl-pattern clustering

Five distinct crawler shapes cover everything in this inventory:

### A. RSS-fan (10 streams)
All MOEF feeds: `english.moef.go.kr/{pc|ec|mi}/eng...rss.do?boardCd={code}`.
One handler reads N RSS URLs, normalizes to common schema. Lowest complexity.
Tier-1 wins for MOEF coverage.

**Members**: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, (+ any future MOEF
board added — pattern is stable).

### B. AJAX-listing on BoK `bbs/{boardId}/list.do` (≈12 streams)
All BoK content. Single crawler config-driven by `(boardId, menuNo)` pair.
Each detail page follows `bbs/{boardId}/view.do?nttId={id}&menuNo={m}`.
PDFs attached via `atchFileId` parameter on a separate downloader endpoint.
Dedupe by `nttId`.

**Members**: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 1.10, 1.12, 1.13, 1.14, 1.16, 1.17.

### C. AJAX-listing on regulator portals (≈4 streams)
Same shape as B but on different domains. `fsc.go.kr/eng/pr...`, `fss.or.kr/eng/bbs/...`,
`kofia.or.kr/brd/...`. Each has different pagination params but identical pattern:
listing page → detail page → optional PDF.

**Members**: 3.1, 3.3, 3.6, 3.7.

### D. HTML-listing on ministry / agency portals (≈15 streams)
Plain server-rendered HTML with table-style listings. Walk pagination links.
URL patterns differ per ministry but no JS rendering needed.

**Members**: 2.10, 2.12, 2.13, 2.14, 2.15, 2.16, 2.17, 2.18, 2.19, 2.20, 2.21,
4.1, 4.2, 4.5, 6.1, 6.2, 6.5, 7.3, 7.5, 7.8, 7.9, 8.1, 8.4, 9.1, 9.4.

### E. Think-tank publication-list pages (≈15 streams)
Similar to D but each institute has bespoke URL patterns. KDI / KIEP / KIF /
KIET / KLI / KIPF / KCMI / KCIF / KRIHS / STEPI / KEEI. All static HTML; most
have separate KO + EN listings with different IDs. Some (KCIF, KEEI) have
login-gated content that requires auth strategy.

**Members**: 5.1–5.24.

### F. Special / data-portal (≈4 streams)
Not document-corpus crawl shape — these are data portals or special
search interfaces.

- 3.5 English DART (corporate-filings search — out of policy-corpus scope)
- 4.6 KCS Unipass (trade-data portal)
- 8.2 KRX KIND (market-data portal)
- 1.18 BoK Newsletter (email push — not crawled)

**Implication**: 75–80% of in-scope streams collapse into 4 crawler shapes
(A/B/C/D). E is the long-tail per-institute work. F is mostly out of scope
for the policy-document corpus.

---

## Open questions

1. **Korean-only ingest?** Many sources (KCIF, KEEI subscribers' content, KLI
   Monthly Labor Review, MOLIT comprehensive archive, KIF Financial Research
   Brief, BOK Issue Notes) are richer in Korean than English. Does the corpus
   accept KO + translation step, or English-only? This is a binary product
   decision that gates ~30% of the inventory.

2. **KCIF subscriber access** — KCIF reports are the de-facto FX desk feed for
   MOEF + BoK. Confirm whether RV Capital has subscriber credentials (via
   institutional relationship) or only the public-side reports are
   addressable. Public-side only ≈ 10% of KCIF output.

3. **BoK Issue Notes English availability** — research surfaced examples (e.g.
   "Issue Note 2026-12 AI productivity") in title metadata but did not
   confirm an English landing URL distinct from the general press-release
   board. Need a direct probe.

4. **BoK Regional Economic Report ("Golden Book")** — exists as a Korean
   publication; English summary availability + permanent URL pattern not
   confirmed in this pass.

5. **KOSTAT → MODS transition** — the 2025+ rebrand from `kostat.go.kr` to
   `mods.go.kr` is in progress. Some press releases live on the new domain,
   others on the old. URL stability through 2027 is uncertain — pin both for
   the medium term.

6. **MOLIT English coverage** — English subsite has dozens of pages but the
   press-release archive is sparse vs the Korean main site. For housing
   policy completeness, Korean ingest may be mandatory (re-ask Q1).

7. **PIPC / KFTC / KEPCO inclusion** — all three are listed in §10 as
   "other / cross-cutting" with uncertain macro signal. Confirm whether
   data-protection (PIPC), antitrust (KFTC), and electricity-tariff (KEPCO)
   feeds belong in the macro corpus or sit in a separate
   regulatory/sectoral corpus.

8. **Pension fund deep coverage** — beyond NPS + KIC, the GEPS / KTP / POBA /
   private-school-teachers funds publish in Korean. Confirm whether their
   allocation shifts have enough KRW / KOSPI signal to warrant inclusion
   (NPS dominates allocation flows ≈ 10× the next-largest fund).

9. **Korea.net as crawl spine vs direct site crawl** — korea.net carries
   most of the press-release content from §2 but adds 1–2 day latency and
   strips some metadata. Confirm whether it's a recall back-stop or a
   primary feed.

10. **Forward-calendar feed (statistical-release schedule)** — KOSTAT (4.3)
    and MOEF media schedule (2.9) overlap on this. Picking a single canonical
    forward-calendar source would simplify downstream "what's the next print"
    queries; defer until ingest design phase.

---

## End-to-end probe evidence (2026-06-10)

Discovery scripts in [`playground/econ/kr_govt_docs/`](../../../../playground/econ/kr_govt_docs/)
fetched at least one representative source per crawl-pattern cluster and saved
raw artifacts under `raw/{cluster}/`. All probes use the KOSIS-pattern
TLS-1.2-pinned `_kr_http.make_session()` helper — corp-network egress resets
TLS 1.3 handshakes against KR govt edges.

### Cluster A — RSS-fan (MOEF) ✅ LIVE

Script: [`probe_moef_rss.py`](../../../../playground/econ/kr_govt_docs/probe_moef_rss.py).
Saved artifacts: `raw/moef_rss/`.

| Board | URL family | Items | Latest item | Status |
|---|---|:---:|---|:---:|
| N0001 press releases | `pc/engmosfrss.do?boardCd=N0001` | 10 | 2026-06-04 "Emergency Economic Headquarters Meeting" | ✅ Fresh |
| E0009 treasury/debt | `ec/engmosfpolicyrss.do?boardCd=E0009` | 30 | 2025-12-29 "KTB Issuance Plan, January 2026" | ✅ Fresh (slow cadence) |
| M0002 DPM speeches | `mi/engmosfpublicrss.do?boardCd=M0002` | 9 | 2023-07-20 "Kyungho Choo @ WB Korea Office 10th" | ⚠ STALE — DPM changed since |

**Schema**: standard RSS 2.0, channel/item with `title`, `link`, `description`,
`pubDate`, `guid`, `dc:date`. All fields populated.

**Detail-page gotcha**: links in feed point to `/pc/selectTbPressCenterDtl.do?boardCd=…&seq=…`
on the **http:// scheme** (not https). N0001 detail page renders the full
article HTML (73 KB, body in `<div class="content">` likely). But E0009 and
M0002 detail-page responses are byte-identical (72,818 B) → these board
families share a session-expired/empty-content template when accessed without
a referrer; needs investigation before production use.

**No PDF attachments** on any of the 3 sample detail pages. Body text appears
to be inline HTML.

**Parser skeleton** (works today, ~20 lines):
```python
import requests, xml.etree.ElementTree as ET
r = session.get(f"https://english.moef.go.kr/pc/engmosfrss.do?boardCd={code}")
for item in ET.fromstring(r.content).findall(".//item"):
    yield {
        "title": item.findtext("title"),
        "link":  item.findtext("link"),
        "pubdate": item.findtext("pubDate"),
        "summary": item.findtext("description"),
    }
```

**Verdict**: ship-ready pattern. Add http→https rewrite on detail-page URLs +
a referrer header to fix the empty-detail issue on E0009/M0002. The DPM-
speeches feed (M0002) is stale and may be deprecated; cross-check with
korea.net before production wiring.

### Cluster B — BoK boards ✅ LIVE (corrected 2026-06-10)

Initial probe through `/eng/bbs/{boardId}/list.do` and via GET on
`/eng/singl/newsDataEng/list.do` returned chrome only — see initial
investigation in [`probe_bok_ajax.py`](../../../../playground/econ/kr_govt_docs/probe_bok_ajax.py)
and [`probe_bok_playwright.py`](../../../../playground/econ/kr_govt_docs/probe_bok_playwright.py).
The breakthrough URL came from the user's browser DevTools:

```
https://www.bok.or.kr/eng/singl/newsDataEng/list.do
  ?pageIndex=&targetDepth=&menuNo=400007&syncMenuChekKey=1
  &searchCnd=1&searchKwd=&date=&sdate=&edate=&sort=1&pageUnit=10
```

`menuNo=400007` is the top-level "News & Publications" parent. The page chrome
still doesn't include listing rows in the static HTML — those are populated by
a **POST** to `/eng/singl/newsDataEng/listCont.do` (we'd only tested GET on
that endpoint, which returns 7,185 bytes of date-picker JS only).

**Working recipe** ([`probe_corrections.py`](../../../../playground/econ/kr_govt_docs/probe_corrections.py),
artifact `raw/bok_ajax/listCont_POST.html`):

```http
POST /eng/singl/newsDataEng/listCont.do HTTP/1.1
Host: www.bok.or.kr
Referer: https://www.bok.or.kr/eng/singl/newsDataEng/list.do?menuNo=400007
X-Requested-With: XMLHttpRequest
Content-Type: application/x-www-form-urlencoded

pageIndex=1&targetDepth=&menuNo=400007&syncMenuChekKey=1
&searchCnd=1&searchKwd=&date=&sdate=&edate=&sort=1&pageUnit=10
```

Returns 14,991 bytes of HTML fragment with 10 `(nttId, title)` pairs. Live
items from the 2026-06-10 probe (matches the user's browser screenshot):

| nttId | Item |
|---|---|
| 10098402 | MSB Issuance Notice(02900-2705-0101) |
| 10098400 | Does AI Adoption Improve Productivity? Effects Over the First Three Years [BOK Issue Note 2026-12] |
| 10098385 | Gross National Income: First Quarter of 2026 (Preliminary) |
| 10098383 | National Accounts in the Year 2025 (Preliminary) |
| 10098353 | Industrial Loans of Depository Corporations during Q1 2026 |
| 10098344 | MSB Issuance Notice(DC026-0908-0910) |
| 10098324 | Balance of Payments during April 2026 (preliminary) |
| 10098321 | Notice for Competitive Bidding on Buybacks of Monetary Stabilization Bonds |
| 10098302 | Official Foreign Reserves(May 2026) |
| 10098297 | MSB Issuance Notice(03420-2804-0206) |

**`menuNo` catalogue enumerated from page links** (no rediscovery needed):

| menuNo | Stream |
|:---:|---|
| 400007 | All News & Publications (parent — homepage "featured" subset, server-side capped) |
| 400021/400022 | News subcategories |
| 400067/400068 | BOK Working/Discussion Papers, Conference papers |
| 400215 | Monetary Policy Report |
| 400219 | Financial Stability Report |
| 400221 | Annual Report |
| 400217/400218/400222–400225 | Other Periodicals |
| 400409/400411/400413 | CBDC research |
| 400073/400074/400077 | Speeches |
| 400427/400429/400496 | Issue Notes / additional boards |
| 400423 | Press Releases (use this — full firehose, see below) |

> ### ⚠ `menuNo=400007` gotcha — capped at 250 items / 7 months
>
> **Discovered 2026-06-11** ([`playground/econ/kr_govt_docs/probe_backfill_depth.py`](../../../../playground/econ/kr_govt_docs/probe_backfill_depth.py)).
> The `listCont.do` endpoint has a server-side filter on `menuNo=400007`
> that caps the result set at **~250 items / ~7 months back**. Other
> sub-menus do NOT have this filter — the API returns the same 5,000+
> item firehose going back to **2011-09-08** regardless of which
> sub-menu you pass:
>
> | menuNo probed         | Items   | Earliest date |
> |---|---|---|
> | 400007 (top news)     | 250     | 2025-11-07 ← capped |
> | 400215 (MPR)          | 5000+   | 2011-09-08 |
> | 400219 (FSR)          | 5000+   | 2011-09-08 |
> | 400221 (Annual)       | 5000+   | 2011-09-08 |
> | 400067 (Working Pap.) | 5000+   | 2011-09-08 |
> | 400409 (Issue Notes)  | 5000+   | 2011-09-08 |
> | 400403 (Open Market)  | 5000+   | 2011-09-08 |
> | 400423 (Press Rel.)   | 5000+   | 2011-09-08 |
> | 400411 (CBDC)         | 0       | dead endpoint |
> | 400069 (News)         | 0       | dead endpoint |
>
> The 7 working sub-menus return **identical content** — the BoK API
> doesn't actually filter server-side on those values. Only 400007 has
> the "featured-subset" filter.
>
> **Prod fix (commit `9c9d1ae`, 2026-06-11)**: [`scripts/econ/kr/govt/fetch_bok.py`](../../../../scripts/econ/kr/govt/fetch_bok.py)
> switched from `menuNo=400007` to `400423` (Press Releases). The daily
> ingest now sees the full firehose; backfill of historical 2011-2025
> tracked in [[#bok-backfill-status]] below.

**Verdict**: BoK is now **fully accessible from Python**, no Playwright
needed. One config-driven crawler taking `(menuNo, pageUnit)` reuses this
POST recipe across all 20+ board streams. Per-detail-page (`view.do?nttId=…`)
and per-PDF download (`CommonDownload.do?atchFileId=…&fileSn=…`) endpoints
still need their own probe but are likely the same egov shape as FSS.

### Cluster C — Regulator (FSS works, FSC blocked) — MIXED

Scripts: [`probe_cdef.py`](../../../../playground/econ/kr_govt_docs/probe_cdef.py),
[`probe_followup.py`](../../../../playground/econ/kr_govt_docs/probe_followup.py).
Saved artifacts: `raw/fsc_ajax/`.

**FSS** ✅ **LIVE** — `fss.or.kr/eng/bbs/B0000211/list.do?menuNo=400010`:
- Listing page **server-renders** — 10 nttId-bearing anchors extracted directly
- Latest items dated 2026-04 (e.g. "Corporate Debt and Equity Issues, April 2026",
  "Foreign Investors' Stock and Bond Investment, April 2026")
- Detail URL pattern: `/eng/bbs/B0000211/view.do?nttId={id}&menuNo={m}&pageIndex=1`
- **Attachment URL pattern (confirmed by raw HTML inspection)**:
  ```
  /eng/cmmn/file/fileDown.do?menuNo={menuNo}&atchFileId={hash}&fileSn={n}&bbsId=
  ```
- File metadata exposed inline: `<i class="ico-pdf">`, `<span class="name">{filename}.pdf<span>(fileSize: 220KB)</span></span>`.
- Title appears multiple times in the page (`<title>`, h-tags, plus inside
  `<dl class="file-list">` as the attachment filename).

**FSC** ✅ **LIVE (corrected 2026-06-10)** — `fsc.go.kr/eng/pr010101`:
- Initial 4-attempt TLS-1.2 retry failed (ConnectionReset).
- **With 10-retry patient loop (2.5s base sleep), succeeds on attempt 6.**
- Not corp-firewall blocked (user confirmed it loads in their browser).
  The TLS edge is just intermittently flaky from Python; longer back-off
  fixes it.
- Page returns 77 KB with **20+ press-release titles in `<dt>` elements**:
  - "Network Separation Rules to be Eased in Financial Sector to Boost
    Innovation and Cybersecurity in AI Transformation" (2026-05-25)
  - "NICE Credit Information (NICE CI) Obtains Certificate to Operate in
    Vietnam from the State Bank of Vietnam" (2026-05-22)
  - "FSC Chairman Holds Media Briefing and Outlines Progress and
    Achievements of Financial Policy Implementation" (2026-05-21)
  - "Revised Rules on Whistleblower Reward and Strengthened Sanctions on
    Accounting Fraud to Take Effect from May 26"
  - "Household Loans, April 2026"
  - …14 more.
- Click handlers use `fn_saveBookmark`/`fn_sendSns` for sharing; article-detail
  navigation uses URLs with `no=N` query param (40+ occurrences in HTML).
- Total archive: 1,771 press releases across 89 pages.

**Verdict**: FSS is **the cleanest production target** (egov bbs, dates in
titles, deterministic attachment URLs — use as framework reference). FSC also
production-ready with a patient-retry HTTP helper; share the helper between
FSC + KCS + MOTIR (all show the same flaky-TLS pattern from this network).

### Cluster D — Ministry HTML (MOTIR + KCS, both LIVE) ✅ corrected 2026-06-10

Saved artifacts: `raw/motie_html/`, `raw/kcs_html/`.

**CRITICAL CORRECTION**: The ministry was **renamed** — it is now
**MOTIR** (Ministry of Trade, Industry and **R**esources, formerly MOTIE
"Energy"). The original inventory hostname `motie.go.kr` shows a real 404
page; the new hostname is `motir.go.kr`. The English subdomain
`english.motir.go.kr` is fully functional.

**MOTIR** ✅ **LIVE** — `english.motir.go.kr/eng/article/EATCLdfa319ada`:
- Article-listing URL is keyed on a **category code** (`EATCLdfa319ada` =
  Press Releases category — opaque hash, not numeric).
- HTML 200 / 52 KB / **75 anchors / 8 year-tagged items** — the press-release
  listing is fully server-rendered.
- Live items (2026-06-10 probe):
  - "MOTIR Reviews Economic Cooperation Projects with Uzbekistan Ahead of 1st
    Korea-Central Asia Summit 2026" (Bae Jun-hyoung)
  - "Korea, Kazakhstan Strengthen Economic Cooperation on Supply Chains and
    Energy"
  - "Korea and ASEAN Hold First Official Round of FTA Upgrade Negotiations"
  - "Korea and Mongolia Hold Fifth Round of Official CEPA Negotiations"
  - "MOTIR Minister to Visit Kazakhstan, the Middle East, and the Czech
    Republic to Strengthen Supply Chain and Industrial Cooperation"
  - "Korea and Serbia Conclude Comprehensive Economic Partnership Agreement"
- **Navigation is JS**: titles use `onclick="javascript:article.view('2649', '2')"`
  — article ID + type. Detail-page URL must be assembled from the JS handler
  (likely `english.motir.go.kr/eng/article/view?articleId=2649&type=2` or a
  POST to a load endpoint). Needs follow-up probe.
- **Monthly export release**: not located in this first probe — likely lives
  in a separate sub-category code under MOTIR. The category-code-as-URL
  pattern (`EATCLxxxxxxxx`) makes it harder to enumerate categories without
  walking the nav menu.

**KCS** ✅ **LIVE** — `customs.go.kr/english/main.do`:
- Same flaky TLS as FSC — 4 fails then success on attempt 5 with patient retry.
- 40 KB home page; **16 archive nav candidates** discovered including the
  press-release archive:
  ```
  News             /english/na/ntt/selectNttList.do?mi=8016&bbsId=1744
  Video Gallery    /english/na/ntt/selectNttList.do?mi=8013&bbsId=1743
  FAQ & Notice     /english/na/ntt/selectNttList.do?mi=11767&bbsId=2740
  Trade Statistics /english/cm/cntnts/cntntsView.do?mi=8042&cntntsId=2724
  ```
- KCS uses the **egov `selectNttList.do?mi={menuId}&bbsId={boardId}`** pattern.
  Detail-page IDs surface as `nttSn=10125434` + `nttSnUrl=9d619b53...` —
  the egov "encrypted" detail-link variant.
- Sample English items already visible on the homepage (no archive walk needed):
  - "Advanced Bilateral Training Program"
  - "Playing a Role as a Global Pivotal State in the International Community"
  - "Tackling illegal activities while reviving public economy"
  - "Support measures to drive economic growth and export"
- **10-day quick estimate** not yet located — likely under "Trade Statistics"
  (`mi=8042&cntntsId=2724`) which is a content page; needs sub-link follow.

**Verdict**: Both MOTIR and KCS are **production-ready** with the patient-
retry helper. KCS uses the standard egov-BBS pattern (one config covers
News + FAQ + Notice). MOTIR's category-hash URL scheme makes the framework
slightly more bespoke — needs a one-off discovery of the JS `article.view`
endpoint and a category-code → name map.

### Cluster E — Think-tank (KDI) ⚠ PARTIAL

Script: [`probe_cdef.py`](../../../../playground/econ/kr_govt_docs/probe_cdef.py).
Saved artifacts: `raw/kdi_html/`.

**KDI** — `kdi.re.kr/eng/research/{monTrends,economy,monEb}`:
- All 3 listing URLs return ~80–99 KB pages with ✅ content
- **But all 3 return IDENTICAL "featured publications" card list** (Economic
  Outlook 2026-1H + 3 KDI FOCUS papers) — i.e. the `/eng/research/monTrends`
  URL is a SPA shell, not a per-publication-stream listing.
- Real publication-stream archive is JS-rendered on KDI side.
- Per-publication detail URL pattern is clean: `/eng/research/economy?pub_no=19180`
  — `pub_no` is the canonical doc ID.
- Detail page (99 KB) contains the title "KDI Economic Outlook 2026-1st Half"
  but **PDF download links are not in the static HTML** (only 1 `.pdf` string
  occurrence on the page).

**Verdict**: KDI needs Playwright OR a hidden POST listing endpoint
(same investigation as BoK). The `pub_no` URL pattern is the right doc ID
scheme. The inventory's claim that Cluster E is "static HTML, bespoke per
institute" is partly correct (it IS bespoke) but partly wrong (it's NOT
static — needs JS rendering for back-issue lists).

---

## Probe summary: what we learned about cluster-shape claims

After the 2026-06-10 corrections, **all 5 probed clusters are LIVE and
production-feasible from this network**. Two non-obvious gotchas:

1. The corp network is not blocking these sites — TLS 1.2 is just flaky from
   Python. A patient-retry HTTP helper (10 attempts, 2.5s base backoff)
   fixes FSC + KCS + MOTIR. Document at [`_kr_http.py`](../../../../playground/econ/kr_govt_docs/_kr_http.py)
   and the patient variant in [`probe_corrections.py`](../../../../playground/econ/kr_govt_docs/probe_corrections.py).
2. BoK serves listing rows via a hidden **POST** to `listCont.do`, not via
   GET on the visible list URL. Recipe in §Cluster-B above.

| Cluster | Inventory claim | Probe result | Final verdict |
|---|---|---|---|
| A (MOEF RSS) | RSS-fan | ✅ Works first try, 3 boards confirmed | **A unchanged** — ship as-is |
| B (BoK boards) | AJAX, single crawler | ✅ Works **after POST recipe found**: `listCont.do` form-POST + Referer + XHR header. menuNo catalogue enumerated. | **B re-classified** — "form-POST AJAX, requests-friendly" |
| C (regulator) | AJAX | ✅ FSS server-renders egov BBS pattern. FSC server-renders `<dt>`-titled list with patient retry. | C split: C1 egov-BBS / C2 dt-list with retry |
| D (ministry HTML) | Plain HTML | ✅ MOTIR (renamed from MOTIE) `article` category URL works. KCS `selectNttList.do` egov path works. | D unchanged — but **MOTIE→MOTIR hostname fix is critical** |
| E (think-tank) | Static HTML | ⚠ KDI listings need JS rendering OR direct `?pub_no=N` URL when ID is known | **E partially deferred** — featured cards work without JS; full back-issue list needs Playwright |

**Implication for framework design**: the original "4 shapes cover 80%" claim
is closer to correct than I thought yesterday — with patient-retry + the BoK
POST recipe, **5 unified shapes cover everything probed**:

- **Shape 1 — RSS-fan**: MOEF (10 streams).
- **Shape 2 — egov BBS GET-listing**: FSS, KCS, likely KDIC/KIPF/most
  statistical agencies. URL family `/eng/bbs/{board}/list.do?menuNo={m}` +
  `/eng/cmmn/file/fileDown.do?atchFileId=…&fileSn=…` for attachments.
- **Shape 3 — egov BBS POST-listing**: BoK. URL `…/list.do?menuNo={m}&pageUnit=10`
  for the chrome, **POST** to `…/listCont.do` with form data for the rows.
  Likely also covers FSS/KCS variants that fall back to AJAX rows.
- **Shape 4 — DT/section-rendered list**: FSC (`<dt>` titles inside
  `<dl class="board-list">`-style markup). Same pattern likely applies to
  MoFA, MoEL pages.
- **Shape 5 — JS-onclick article-handler**: MOTIR (`article.view('id','type')`
  via JS). Detail-page URL needs assembly from the JS function — minor
  framework support code.

**Recommended next step (when build is greenlit)**:
1. Ship the patient-retry HTTP helper as the **shared** transport for all
   non-RSS crawlers (`_kr_http.make_session()` already has the TLS 1.2 pin;
   add the 10-attempt patient retry on top).
2. Ship the RSS-fan framework against MOEF — 10 streams, lowest complexity.
3. Ship the egov-BBS framework against FSS — proves the `(boardId, menuNo,
   atchFileId, fileSn)` URL family that generalizes to KCS/KDIC/KIPF.
4. Ship the BoK POST-recipe framework — unlocks the **whole BoK English
   corpus** (20+ board streams from one config-driven crawler).
5. Add FSC + MOTIR + KDI as a second wave once Shapes 1-3 are stable.

The probe data also reveals that the **MOEF feed alone covers** Treasury/debt
press, fiscal management, DPM speeches, budget RSS, and tax-policy RSS — five
of the Tier-1 streams. Starting Korea govt-doc ingest at MOEF (Shape 1) +
BoK (Shape 3) delivers ~70% of Tier-1 coverage on day 1.

---

## Build state (2026-06-10 — LIVE)

### Schema ✅ APPLIED
- [`migrations/086_add_dim_vendor_category.sql`](../../../../migrations/086_add_dim_vendor_category.sql)
  — `ADD COLUMN dbo.dim_vendor.vendor_category` + 10-value CHECK enum +
  full 47-row backfill + post-condition assertion. Applied 2026-06-10.
- [`migrations/087_seed_kr_official_vendors.sql`](../../../../migrations/087_seed_kr_official_vendors.sql)
  — Seeded 7 Korea Tier-1 agencies (`bok`, `moef`, `motir`, `fsc`, `fss`,
  `kcs`, `kdi`; ids 52-58). `mods` (id=24) already covers KOSTAT — no
  duplicate seeded. Applied 2026-06-10.

### Filings helper ✅ LIVE
- [`src/imdr/research/filings.py`](../../../../src/imdr/research/filings.py)
  implements `ingest_filing(FilingInput) -> FilingResult` end-to-end.
  Bypasses the sell-side classifier + relevance filter; delegates to
  existing primitives (parse / chunk / embed / upload / write) in
  `playground/research/ingest/`. Accepts EITHER `pdf_bytes` (parse via
  PyMuPDF → 800-token chunks) OR `body_text` (synthesize a single-page
  Document for HTML-only sources). Same Qdrant collection as sell-side,
  with payload `vendor_category` + `country_code` + `doc_type` + `stream`
  added to the keyword indexes via
  [`src/imdr/connectors/qdrant_schema.py`](../../../../src/imdr/connectors/qdrant_schema.py).

### Daily pull ✅ LIVE
- Location: [`playground/econ/kr/govt/`](../../../../playground/econ/kr/govt/)
  while in playground; eventual prod home is
  `scripts/econ/kr/kr_govt_daily.py` (not wired yet — no-prod-wiring rule).
- 7 fetcher modules (`fetch_{bok,moef,motir,fsc,fss,kcs,kdi}.py`) each
  return `FilingItem` records via the proven URL recipes (see
  [§Per-agency resolution recipes](#per-agency-body--pdf-resolution-recipes-probed-2026-06-10) below).
- 7 resolver helpers in [`resolvers.py`](../../../../playground/econ/kr/govt/resolvers.py)
  turn each `FilingItem` into PDF bytes or body text.
- Orchestrator [`daily_pull.py`](../../../../playground/econ/kr/govt/daily_pull.py):
  - default: discover + dedup via `seen.json` + daily snapshot
  - `--ingest` : also resolve + call `ingest_filing()` (writes to
    research.dim_report + fact_chunk + Qdrant + SharePoint)
  - `--no-embed`: skip Qdrant; chunks land but no vectors (cheap iteration)
  - `--limit N`: round-robin across vendors, smoke 1-of-each
- Failed resolves/ingests don't enter `seen.json` — retryable next run.
- Daily cadence is intentional even though most agencies publish weekly /
  per-meeting / quarterly — sub-second per fetcher, and we want visibility
  into cadence drift (e.g. BoK skipping an Issue Note month, FSS pausing
  press for a regulatory window).

### SharePoint layout (govt filings)

```
Trade Knowledge Core - IMDR/{YYYY}/{MM}/{DD}/econ/{country}/{vendor}/{slug}_{hash8}.pdf
```

Date-first hierarchy — fits inside the existing
`{YYYY}/{MM}/{DD}/{vendor}/...` convention used by sell-side research
(see [`playground/research/ingest/paths.py`](../../../../playground/research/ingest/paths.py)).
Govt filings insert `econ/{country}/` between the date and vendor so a
single day folder shows both sell-side vendors (top-level) and govt
filings (under `econ/`) grouped by country.

Example day:

```
Trade Knowledge Core - IMDR/2026/06/10/
├── anz/                         (sell-side)
├── jpm/
├── nomura/
├── …
└── econ/
    └── kr/
        ├── bok/
        │   ├── financial-statement-analysis-for-2025_3e438373.pdf
        │   └── …
        ├── fsc/
        ├── fss/
        └── …
```

HTML-only sources (MOEF, MOTIR press) produce no PDF file — `pdf_path`
is empty, chunks are synthesized from `body_text` via
`synthesize_document_from_text` in [`filings.py`](../../../../src/imdr/research/filings.py).

### Daily output shape (illustrative)

```
2026-06-10 Korea govt filings daily pull
  bok     new: 2    BoK Issue Note 2026-12, MSB Issuance 02900-2705-0101
  moef    new: 0
  motir   new: 1    MOTIR Reviews Cooperation Projects with Uzbekistan
  fsc     new: 0
  fss     new: 1    Capital Ratios of Banks, Q1 2026
  kcs     new: 0    (next 10-day estimate expected 2026-06-11)
  kdi     new: 0
TOTAL: 4 new items
```

The "may not have data" days are the point: empty days for FSC/KCS/KDI/MOEF
between cadence windows are evidence, not a bug.

---

## Per-agency body + PDF resolution recipes (probed 2026-06-10)

Each fetcher emits a `FilingItem` with `source_url`. The ingest step needs
to convert that into **either** PDF bytes (preferred — full document for
chunking) **or** body text (HTML-only or PDF-blocked sources). Recipes
below are confirmed by [`probe_resolve_v2.py`](../../../../playground/econ/kr/govt/_explore/probe_resolve_v2.py)
(plus the earlier deleted `probe_resolve.py`); raw samples archived under
[`playground/econ/kr_govt_docs/resolve_samples/{vendor}/`](../../../../playground/econ/kr_govt_docs/resolve_samples/).

### Summary

| vendor | path | body container | PDF download | first-page text preview |
|---|---|---|---|---|
| bok | view.do → `<a href=".pdf">` | (PDF) | direct `/fileSrc/eng/{h1}/{i}/{h2}.pdf` (47 KB sample) | "Monetary Stabilization Bond 02900-2705-0101 Issuance Notice" ✅ |
| fss | view.do → `<dl class="file-list">` | (PDF) | `/eng/cmmn/file/fileDown.do?menuNo={m}&atchFileId={hash}&fileSn={n}&bbsId=` (225 KB sample) | "Corporate Debt and Equity Issues, April 2026" ✅ |
| moef | detail.do → body div | `div.board-view-cont` or largest body div (3.7 KB) | none (HTML-only releases) | — |
| fsc | /eng/pr010101/{id} | `div.board-view-wrap > div.body` (9.6 KB) | `/comm/getFile?srvcId=BBSTY1&upperNo={article_id}&fileTy=ATTACH&fileNo=1` (318 KB sample) | "NETWORK SEPARATION RULES TO BE EASED IN FINANCIAL SECTOR…" ✅ |
| kcs | selectNttInfo.do | — | attached files are typically **JPG images** (1.5 MB sample), not PDFs — for text use title only | (would need OCR) |
| motir | `/eng/article/{cat}/{bbsSeqN}/view?bbsCdN={type}` | `div.detail-cont` | `/attach/down/{h1}/{h2}/{h3}` — **TLS-blocks our Python session** even with Referer + cookies | body path only for v1 |
| kdi | `?pub_no={id}` (static) | (PDF) | `<button onclick="location.href='/eng/file/download?atch_no={url-encoded-base64}'">` — parse onclick attribute | "kdi ECONOMIC OUTLOOK Vol.43 No.2 2026-1st Half" ✅ |

### Recipe details

**BoK** ([fetch_bok.py](../../../../playground/econ/kr/govt/fetch_bok.py) → resolve):
```python
detail = session.get(item.source_url)   # view.do?nttId=…
soup = BeautifulSoup(detail.text, "html.parser")
pdf_href = next(
    a["href"] for a in soup.find_all("a", href=True)
    if ".pdf" in a["href"].lower() and "hwp" not in a["href"].lower()
)
pdf_bytes = session.get(urljoin("https://www.bok.or.kr", pdf_href)).content
```
URLs look like `/fileSrc/eng/{hash1}/2/{hash2}.pdf` — direct file path, no
intermediate download.do. Anchor text discriminates `.pdf` from `.hwp`
(BoK attaches both; we want the PDF).

**FSS** ([fetch_fss.py](../../../../playground/econ/kr/govt/fetch_fss.py) → resolve):
```python
soup = BeautifulSoup(detail.text, "html.parser")
file_list = soup.find("dl", class_="file-list")
pdf_href = file_list.find("a")["href"]   # only attachment per release
pdf_bytes = session.get("https://www.fss.or.kr" + pdf_href).content
```
URL pattern includes the per-release `atchFileId` hash + `fileSn`.

**MOEF** — HTML-only, use body_text. Container is one of
`board-view-cont` / `view_cont` / largest body `<div>`. Bodies run
3-10 KB of clean press text. No PDF resolution step.

**FSC** ([fetch_fsc.py](../../../../playground/econ/kr/govt/fetch_fsc.py) → resolve):
```python
soup = BeautifulSoup(detail.text, "html.parser")
wrap = soup.find("div", class_="board-view-wrap")
body_text = wrap.find("div", class_="body").get_text()    # 9-15 KB body
pdf_url = f"https://www.fsc.go.kr/comm/getFile?srvcId=BBSTY1&upperNo={article_id}&fileTy=ATTACH&fileNo=1"
pdf_bytes = session.get(pdf_url).content
```
**Both** body and PDF are available. `article_id` is the last path
segment of the source_url (`/eng/pr010101/{article_id}`).

**KCS** — attachments are commonly **JPG images** of program documents,
not PDFs. For v1, ingest title + listing metadata only (no body, no
PDF). When live boards are mapped (Korean-side press releases), revisit.

**MOTIR** ([fetch_motir.py](../../../../playground/econ/kr/govt/fetch_motir.py) → resolve):
```python
detail_url = (
    f"https://english.motir.go.kr/eng/article/{category_hash}/{article_id}/view"
    f"?pageIndex=1&bbsCdN={article_type}"
)
session.get(detail_url)   # seeds cookies + JSESSIONID
soup = BeautifulSoup(detail.text, "html.parser")
body_text = soup.find("div", class_="detail-cont").get_text()
# PDF download via /attach/down/{h1}/{h2}/{h3} is **TLS-blocked** from this
# network even with Referer + session cookies. Use body_text path for v1.
```
The body container is `div.detail-cont` (NOT `div.board-detail` — that
wraps the attachment list, not the article text). Body runs ~5-10 KB
of release prose, which is the main signal for Mycroft/Lois.

**KDI** ([fetch_kdi.py](../../../../playground/econ/kr/govt/fetch_kdi.py) → resolve):
```python
detail = session.get(item.source_url)   # /eng/research/economy?pub_no=19180
m = re.search(r"onclick=\"location\.href='(/eng/file/download[^']+)'\"", detail.text)
pdf_url = "https://www.kdi.re.kr" + m.group(1)
pdf_bytes = session.get(pdf_url).content
# Each KDI detail has multiple download buttons (Summary EN + Full Korean).
# Pick the first; both yield 100-700 KB text-based PDFs.
```
`atch_no` query is url-encoded base64 (`%3D%3D` padding) — pass through
verbatim, don't double-decode.

### What this means for `filings.py` impl

The skeleton already accepts EITHER `pdf_bytes` OR `body_text` on `FilingInput`.
At wiring time, each fetcher gets a `resolve(item) -> bytes | str` helper:

| vendor | resolve returns | downstream path |
|---|---|---|
| bok | `pdf_bytes` | parse_pdf → chunk_doc → embed → write |
| fss | `pdf_bytes` | same |
| fsc | `pdf_bytes` | same |
| kdi | `pdf_bytes` | same |
| moef | `body_text` | synth single-page Document → chunk → embed → write |
| motir | `body_text` | same |
| kcs | (defer — image attachments need OCR or skip) | skip until live boards mapped |

### Open items before first ingest

1. **MOTIR PDF download is the only true regression** — the body-text
   path is solid (5-10 KB of release prose per item, 8 items/day, 60/month)
   but full PDF would have any annexed tables / formatting we lose. If the
   Mycroft outputs eventually flag "missing chart context on MOTIR items",
   revisit with a Playwright-rendered ingest path (slower but works).
2. **KCS-on-this-board is image-only** — not a code problem, the board
   genuinely publishes JPG scans. The high-value KCS 10-day trade
   estimates live on a different (Korean-side) URL not yet mapped.
   Defer KCS to phase 2.
3. **MOEF detail-page `#fn_download` anchors** — the press-release detail
   pages have 4 anchor placeholders that JS turns into download buttons.
   Body text alone is sufficient for v1; if Mycroft starts asking for
   appendix tables, follow up.

All other agencies (BoK, FSS, FSC, KDI) are **fully wireable** with
requests + BeautifulSoup. No new dependencies, no OCR, no Gemini extra
calls. PyMuPDF parses every sampled PDF cleanly with real first-page text.
