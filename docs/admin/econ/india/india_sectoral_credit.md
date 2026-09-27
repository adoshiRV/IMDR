# India — bank credit (RBI)

Last updated: 2026-09-15 (first build)

| | |
|---|---|
| Sectoral fetcher | [`scripts/econ/in/rbi/rbi_sectoral_credit.py`](../../../../scripts/econ/in/rbi/rbi_sectoral_credit.py) |
| Aggregate fetcher | [`scripts/econ/in/rbi/rbi_dbie_scb_business.py`](../../../../scripts/econ/in/rbi/rbi_dbie_scb_business.py) |
| Shared helpers | [`src/imdr/domains/econ/rbi_tspd.py`](../../../../src/imdr/domains/econ/rbi_tspd.py) (headed download) · [`rbi_parse.py`](../../../../src/imdr/domains/econ/rbi_parse.py) (date/number scalars) |
| Tests | `tests/unit/test_econ/test_rbi_sectoral_credit_parser.py` (51) · `test_rbi_dbie_scb_business_parser.py` (16) · `test_rbi_dbie_sapbo.py` (+7 for `dismiss_modal`) — no network |
| Review | `imdr-code-reviewer` per [`econ_to_prod.md`](../econ_to_prod.md) §G.6, 2026-09-15 — **no blocking findings**; §G.6's 8-item checklist clean |

**Status: built, smoke-passed against the live sources, NOT wired to any
orchestrator and NOT loaded to the database.** Wiring needs explicit sign-off
(see *Not wired*).

## Why this exists

The econ-monitor dashboard's data-gap register carries **DG24 — India sectoral
bank credit & deposits** as class *no source*: IMDR held **no India credit series
of any kind**, against a live `credit_aggregates` dashboard category with AU 33 /
KR 3 / **IN 0**. The gap is country-shaped, not concept-shaped, which is what made
it a coverage request rather than a design question.

DG24 names a history floor rather than just a latest print — **≥ 25 monthly
observations**, because the consuming chart is % YoY and the surrounding prose
makes a two-year-CAGR claim. It also warns that filing the table under the
existing `INDIA.RBI_BULLETIN.*` theme would inherit that theme's depth defect
(542 series, median 5 observations). These are therefore their **own themes**,
and they carry real history.

## What is now held

### `INDIA.SECTORAL_CREDIT.*` — 82 series × 90 months, Jan-2019 → Jul-2026, gapless

Monthly, `unit=inr_cr`, `category=credit`, `country_iso=IN`. 7,380
observations. Source: the monthly RBI press release *Sectoral Deployment of Bank
Credit*, Statements 1 and 2.

| Statement | Series | Covers |
|---|--:|---|
| 1 — Deployment by Major Sectors | 40 | `AGRICULTURE_AND_ALLIED_ACTIVITIES` · `INDUSTRY` (+ `MICRO_AND_SMALL`, `MEDIUM`, `LARGE`) · `SERVICES` (+ `NON_BANKING_FINANCIAL_COMPANIES`, `HOUSING_FINANCE_COMPANIES`, `PUBLIC_FINANCIAL_INSTITUTIONS`, `TRADE`/`WHOLESALE_TRADE`/`RETAIL_TRADE`, `COMMERCIAL_REAL_ESTATE`, …) · `PERSONAL_LOANS` (+ `HOUSING`, `VEHICLE_LOANS`, `LOANS_AGAINST_GOLD_JEWELLERY`, `CREDIT_CARD_OUTSTANDING`, `EDUCATION`, `CONSUMER_DURABLES`, …) · 10 `PRIORITY_SECTOR_*` memo rows |
| 2 — Industry-wise Deployment | 42 | 19 industries + sub-industries: `PETROLEUM_COAL_PRODUCTS_AND_NUCLEAR_FUELS` · `EDIBLE_OILS_AND_VANASPATI` · `ALL_ENGINEERING` · `GEMS_AND_JEWELLERY` · `TEXTILES` (4 sub) · `BASIC_METAL_AND_METAL_PRODUCTS` · `INFRASTRUCTURE` (7 sub) · `CHEMICALS_AND_CHEMICAL_PRODUCTS` (4 sub) · … |

### `INDIA.SCB_BUSINESS.*` — 3 series × 43 months, Oct-2022 → Aug-2026

Monthly (last reporting fortnight of each month), `unit=inr_cr`. Source: DBIE
reportId 1130, the fortnightly Section-42 return. `BANK_CREDIT` ·
`FOOD_CREDIT` · `NON_FOOD_CREDIT`, **for all scheduled commercial banks**.

### The two prefixes are two universes, deliberately

RBI's own note (1) on the sectoral release says it: bank / food / non-food credit
come from the fortnightly **Section-42** return covering ALL scheduled commercial
banks, while the sectoral rows come from the **SIBC** return covering ~41 select
banks (~95 % of non-food credit). The sectoral XLSX prints both in one statement,
rows I–III above rows 1–4.

So rows I–III are **excluded** from `INDIA.SECTORAL_CREDIT.*` and owned by
`INDIA.SCB_BUSINESS.*` instead. Every code under the sectoral prefix is now one
universe. That is DG24's second trap ("bars sourced from the two cannot share an
as-of stamp even when they share a month") made structural rather than left as a
footnote. Verified against DBIE reportId 1130 on 2026-09-15 — Mar-2026 food
credit ties to the crore (70,271) and bank credit differs only by revision
vintage.

**Levels only.** The release also carries YoY and financial-year variation
columns; they are deliberately dropped. A % change is the consumer's kernel, not
a stored series — DG24 says as much ("the chart's % YoY is ours to compute").

## Verification

Recomputed from the written parquet, not from the scraper's own state
(2026-09-15):

| Check | Result |
|---|---|
| RBI's published Jul-2026 YoY: agriculture 17.0 %, industry 20.0 %, services 22.9 %, personal loans 16.2 % | ours 16.98 / 19.95 / 22.94 / 16.23 — **all four tie to rounding** |
| `MICRO_AND_SMALL + MEDIUM + LARGE` vs `INDUSTRY`, Jul-2026 | exact to 0.00 |
| Coverage | 82 × 90 = 7,380 observations, **zero gaps** |

The first check is the one that matters, because it is the only one that catches
the vintage rule being wrong — see below.

## Source and access

Monthly RBI press release, indexed at
[`Data_Sectoral_Deployment.aspx`](https://rbi.org.in/Scripts/Data_Sectoral_Deployment.aspx).
Access is deliberately two-stage:

| Stage | Host | Wall | Cost |
|---|---|---|---|
| Release index (year tree) | `rbi.org.in` | none — the year switch is an **ASP.NET postback** on a hidden `hdnYear` field, driven with plain `httpx` | 1 GET + 1 POST/year |
| Press-release page → XLSX href | `rbi.org.in` | none | 1 GET/release |
| The XLSX itself | `rbidocs.rbi.org.in` | **Akamai TSPD** — plain httpx and headless Playwright both get an HTML challenge served under the `.xlsx` name | **headed Chrome** |

Only the last stage costs a browser. Downloads are cached under
`data/econ/in/rbi/_downloads_sibc/` (gitignored via `data/*`), so a backfill is
paid once — 85 files, about 7 minutes — and the monthly tick costs one file.

### Two Chrome-profile failure modes, both fixed and both worth knowing

1. **A shared profile dir deadlocks.** `launch_persistent_context` takes an
   exclusive lock on `user_data_dir`. Pointing this fetcher at `rbi_bulletin.py`'s
   `_profile` produced `TargetClosedError` on every download while another headed
   Chrome held it (a live BofA research-profile session). Each fetcher now owns
   its dir.
2. **A REUSED profile dir kills the browser on the first download.** Even alone,
   a profile that has been used before (or left behind by a killed run) tears the
   browser down on download 1, after which every remaining item times out at 60 s
   each — one fault becomes a half-hour stall that reads as a TSPD block.
   `rbi_tspd.download_all` now recreates its profile per run and relaunches once
   if the browser dies mid-batch. Nothing is lost: TSPD is cleared by live JS in
   the session, not by anything persisted, which is why a first-run profile works.

The standing rule that no two headed Playwright sessions run at once still
applies.

### And one for the DBIE side

A **stale DBIE session** greets the next run with a timeout/logout `<app-modal>`
whose backdrop swallows every click, so the search box never receives the term
and Playwright retries until it times out — three attempts, several minutes, and
an empty result that looks like a scraping failure rather than a dialog.
`rbi_dbie_sapbo.dismiss_modal` now closes it before searching. This was hitting
the shared module, so it fixes the two pre-existing prod DBIE fetchers
(reportIds 417 and 698) as well.

## Coverage, and the two eras that are declined

All 189 sectoral releases back to 2011 were indexed on 2026-09-15. XLSX
attachments start with **June 2019**; everything earlier is PDF-only.

| Years | Releases | With XLSX |
|---|--:|--:|
| 2026 (to July) | 7 | 7 |
| 2020–2025 | 71 | 71 |
| 2019 | 12 | **7** (June onward) |
| 2011–2018 | 99 | **0** |

Of the 85 downloadable files, **20 are declined** by two gates that decline
rather than guess:

- **Unit.** June and July 2019 are in **Rs. billion**. Reading them as crore
  would understate every value 100×.
- **Layout *and taxonomy*.** Every release from Aug-2019 to Dec-2020 is in crore
  but splits the row label across a separate `Sr.No` column and a `Sector`
  column — and carries a **different taxonomy**, not just a different shape:
  `Agriculture & Allied Activities` for `Agriculture and Allied Activities`,
  `Micro & Small` for `Micro and Small`, no `Aviation` and no `Loans against gold
  jewellery` row, a priority-sector block with `Micro-Credit` and
  `State-Sponsored Orgs. for SC/ST` that the current block does not have, and
  section numbers that mean different things either side of the break (3.5 is
  Aviation now and Professional Services then). Splicing that onto the current
  codes would manufacture parallel half-series and fake level breaks.

**Nothing is lost at the start of the record.** The first current-layout release
(Jan-2021) carries `18.Jan,2019` as its oldest column, so the back-references
reach the Jan-2019 SIBC recast anyway — which is exactly where DBIE says the
current series begins. Hence 90 gapless months from 65 usable releases.

Extending to the two declined eras is a deliberate follow-up, not an oversight,
and it needs an alias map plus a decision about whether pre-2021 is the same
series at all.

## Two breaks a consumer must know about

1. **Reporting-date definition changed 31 December 2025.** Under the Banking
   Laws (Amendment) Act 2025 the "last reporting fortnight" became the last
   **day** of the month. From Dec-2025 onward RBI's own YoY compares a month-end
   against the year-ago month's old-definition fortnight, and so does anything
   computed off these series.
2. **The sectoral table is ~41 select SCBs**, ~95 % of non-food credit — see
   *two universes* above.

## Design notes worth knowing before editing

**Five columns per release, and which one wins a month.** Each XLSX carries five
"Outstanding as on" columns: the reported month, the two year-ago anchors its YoY
columns use, and two financial-year anchors. All five are read — that is what
makes the record gapless from Jan-2019 — and a month resolves by:

1. the **latest reported date inside that calendar month**, then
2. the **latest release** to print that date.

Rule 1 stops an FY anchor from displacing a genuine month-end: the FY2024-25
anchor prints as `4.Apr,2025`, while the April-2025 release itself reports
`18.Apr,2025`. Rule 2 makes a restatement win, and **this one was got wrong
first**: an earlier build attributed each month to the release that reports it,
which stores first prints. That reproduces agriculture's 17.0 % but gives
services 21.2 % against a published 22.9 %, because the Jul-2025 services level
was revised from 5,113,966 down to 5,040,440 a year later. RBI's own YoY compares
against the year-ago figure *as restated today*. Both rules are pinned by tests,
and the published-YoY check above is what catches a regression.

**Statement 1 re-declares its dates mid-sheet.** The credit block and the sector
block disagree on the FY anchor (`4.Apr,2025` vs `21.Mar,2025`), so a parser that
latched the first header dates every sector row wrongly.

**Codes come from names, not RBI's row numbers.** RBI renumbers rows when it
inserts one but renames them rarely, so the slug carries the concept and the
section number goes to `source_code` for traceability. Three consequences:

- `Gross Bank Credit` (pre-rename) and `Bank Credit` alias to one code.
- Statement 2 carries **three** `Others` rows (2.2.4 Food Processing, 2.9.4
  Chemicals, 2.14.2 All Engineering). They are qualified by parent —
  `FOOD_PROCESSING_OTHERS` and so on — or three concepts become one series.
- The priority-sector memo block restates sectors on a different definition and
  is namespaced `PRIORITY_SECTOR_*`, or `(i) Agriculture` and `(iv) Housing`
  overwrite the all-bank rows.

**A genuine collision raises.** Two RBI rows landing on one code fails loudly
rather than merging; the fix is an entry in `_SLUG_ALIASES` or `_GENERIC_SLUGS`.
This guard is what found the Aug-2019→Dec-2020 taxonomy break during the
backfill, rather than letting it through as a silent merge.

**Report 1130 publishes broken rows.** When the credit figure has not landed it
prints Bank Credit blank and Non-Food Credit as `0 − Food Credit`, i.e. negative.
11 such rows in the live 101-row scrape. A row missing Bank Credit is dropped
whole.

## Invocation

```
# monthly tick — latest 3 releases (>1 so a late-published month is caught)
python -m scripts.econ.in.rbi.rbi_sectoral_credit
python -m scripts.econ.in.rbi.rbi_dbie_scb_business

# smoke, no DB write
python -m scripts.econ.in.rbi.rbi_sectoral_credit --no-load

# full backfill of the current-layout era (~7 min, 85 downloads)
python -m scripts.econ.in.rbi.rbi_sectoral_credit --since 2019-01-01 --no-load
```

Both require a host with a display (headed Chrome), same constraint as
`rbi_bulletin.py`, and must not run concurrently with another headed session.

## Not wired

Per the standing rule, nothing is registered into `imdr_monthly.py` or
`scripts/econ/in/in_monthly.py` without explicit sign-off. When it is, both
belong at the **end** of the monthly list beside `rbi_bulletin` — all three need
headed Chrome and none may overlap.

The sectoral release lands on the last working day of the month for the previous
month (July-2026 data published 31 Aug 2026), so a monthly cadence with a
3-release window is the right shape.

**Dimension prerequisites — all satisfied, no migration needed** (checked against
the live DB 2026-09-15): vendor `rbi` exists (`official_cb`), category `credit`
exists (id 9, "Credit aggregates"), frequency `MONTHLY` exists, unit **`inr_cr`**
exists. That last one is worth stating because the first build used `inr_crore`,
which is not a `dim_unit` code — every indicator would have failed to load. The
code review could not catch it (no DB access), so **check `unit` / `category` /
`vendor_name` / `frequency` against the live dimensions by hand before any load.**

**These 82 series will be flagged permanently stale, and that is an estate-wide
defect rather than anything specific to them.** `_STALE_DAYS["MONTHLY"] = 60` in
`src/imdr/notifications/econ_snapshot.py` measures `today − MAX(obs_date)` and
models no publication lag at all. RBI publishes month *M* at the end of *M+1*, so
with month-start `obs_date` the gap sits at **60–91 days all month**.

Measuring it showed the same fault hits **1,148 of 1,565 active monthly series
(73%)** across every country — US JOLTS, Korea BoP, ABS building approvals and
Indonesia trade all sit at exactly 76 days behind today, all healthy, all last
ingested within a fortnight. Tracked as a high-priority item with the full
measurement and design:
[`../../development/econ_per_series_cadence.md`](../../development/econ_per_series_cadence.md).

Nothing about that blocks wiring these fetchers — they would simply join a large
existing class of false positives. Worth knowing before anyone reads the stale
count in a country econ email and believes it.

A related fix belongs to this fetcher specifically: `run_fetch` sets
`release_date=now`, the same as every other econ fetcher, even though
`_release_date_from_name()` has already parsed RBI's **true** publication date out
of the XLSX filename. That is the worked example named in the tracking doc.

## What is still open

DG24 asks for three things. Two are served.

| Ask | Status |
|---|---|
| Sectoral deployment of gross bank credit — Chart A's bank bars, the agri bar, the housing-share-of-retail denominator | **served** — 82 series, 90 months |
| Aggregate SCB business: total bank **credit** | **served** — `INDIA.SCB_BUSINESS.*`, 43 months |
| Aggregate SCB business: total **deposits** | **OPEN.** DBIE reportId 9 carries aggregate / demand / time deposits, but its SAP-BO grid is **horizontally panelled** and the DOM scrape lands on a different panel run to run: three live scrapes on 2026-09-15 returned, in order, a 101-row monthly panel whose 15 columns included `2.1 Aggregate Deposits`, then twice a 748-row fortnightly panel (back to Jun-1997) carrying only interbank-liability columns and no deposits. `scrape_iframe_table` picks the largest leaf table by row count, so the deeper panel now wins. Reaching deposits needs the grid's horizontal scroll or its **Export** button (`#__button60`, noted in `playground/econ/in/rbi/rbi_dbie_report.py`). The column map is kept, tested and marked in `BLOCKED_REPORTS` so it need not be re-derived. Without this, the credit−deposit gap and the CD ratio cannot be computed. |
| NBFC credit — total and retail (Chart A's 20.3 % bar) | **not available.** DBIE reportId 1198 ("Credit to Various Sectors by NBFCs") is annual and **stops at 31-MAR-2018**. DG24 already flags that a request scoped to "sectoral bank credit" leaves this bar open, and that a bank-credit chart carrying an NBFC bar is a concept mix worth raising with the feature side regardless of sourcing. |

Also unaddressed and separately filed: **DG25** (monthly PLFS labour) and **DG28**
(auto & tractor sales) — different publishers entirely; the dashboard's Chart B
needs all three.

**Fortnightly grain.** `dbo.dim_frequency` has no FORTNIGHTLY member (11 rows), so
`INDIA.SCB_BUSINESS.*` keeps the last reporting fortnight of each month and
declares MONTHLY — the grain the card plots, the grain RBI headlines, and the same
bucketing the sectoral series uses, so the two are directly comparable. The
mid-month print is dropped, not lost: one migration seeding a FORTNIGHTLY row and
a one-line change recovers it. That decision is left open rather than taken here.

## Related

- [`india_prod_pipeline.md`](india_prod_pipeline.md) — Track A ops reference
- [`../economics_data_ingest.md`](../economics_data_ingest.md) — the schema this writes
- `playground/econ/in/rbi/probe_sectoral_credit.py` — the DBIE probe that mapped
  reportIds 999 / 541 / 1130 / 9 out of the 1,225-report catalog
- `playground/econ/in/rbi/probe_sectoral_pressrelease.py` — the press-release probe
  that established the 2019 XLSX floor across all 189 releases
