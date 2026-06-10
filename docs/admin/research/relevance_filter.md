# Relevance filter — drop single-name equity research

The relevance filter is a discovery-time gate that drops single-name
equity research (company-coverage notes like "Tate & Lyle: Post Results
Agenda" or "FY25/26 results, EPS 1% below... LMPL.L") before any PDF
gets fetched. The goal is a cleaner, lower-volume corpus focused on
macro / rates / FX / commodities / sector research — the material that
informs cross-asset decisions, rather than per-issuer earnings notes.

Lives at [`playground/research/ingest/relevance.py`](../../../playground/research/ingest/relevance.py).

## Where it runs

After the discovery filter (which drops admin/logistics posts) and
before the limit cap or any per-PDF work. See the pipeline map in
[`index.md`](index.md). All seven daily ingest scripts (`ingest_today_*.py`)
call `apply_relevance_filter()` immediately after their respective
`discover_reports()` returns.

## Off-switch

Default ON via `Settings.research_drop_single_name_equity = True`. To
disable for a one-off run (e.g. a backfill that legitimately wants
single-name coverage):

```powershell
$env:IMDR_RESEARCH_DROP_SINGLE_NAME_EQUITY = "false"
python playground\research\ingest_today_goldman.py
```

Or set `IMDR_RESEARCH_DROP_SINGLE_NAME_EQUITY=false` in `.env` if you
want it off across the project.

## The decision

For each `ReportRef` survived from the discovery filter:

```
                    classify(ref) → ClassifyResult
                                │
                                ▼
                  ┌─────────────────────────────┐
                  │ asset_class == "EQUITY" ?   │
                  └────────────┬────────────────┘
                       no      │      yes
                  ┌────────────┘
                  │                        ▼
                  ▼              ┌─────────────────────┐
                KEEP             │ ticker tag count?   │
                                 └─────────┬───────────┘
                              ┌────────────┼────────────┐
                              │            │            │
                            == 1         == 0          ≥ 2
                              │            │            │
                              ▼            ▼            ▼
                           DROP    vendor fallback   KEEP
                       "1-ticker"   (see below)   (multi-name
                                                   comparison /
                                                   sector basket)
```

### Vendor fallback when `n_tickers == 0`

The `n_tickers == 1` rule is the cleanest cross-vendor signal but
relies on the classifier extracting tickers. Two vendors don't
populate ticker tags reliably and get vendor-specific fallbacks:

- **Barclays.** Their listing API ships no ticker fields. The cleanest
  single-name marker is `L1_BRANDING == "Equity Research"` (bottom-up
  corporate coverage). `L1_BRANDING == "Equity Strategy"` /
  `"Equity Quantitative"` are sector / top-down → kept. The filter
  inspects the `discipline` tag from `ClassifyResult.tags` for this.
  Reason logged: `single-name-equity:barclays-discipline`.

- **MS.** MS titles are plain English ("Steady Progress", "1Q26
  Results"). Tickers don't appear in titles; MS uses
  `publication_type` as the company name for single-stock notes.
  There's no reliable way to distinguish a single-name note from a
  sector preview from listing-API metadata alone, and MS publishes
  overwhelmingly single-name (95%+ of the daily firehose). The filter
  default-drops all MS `EQUITY` that didn't already match the
  `n_tickers == 1` branch. Reason logged:
  `single-name-equity:ms-default-drop`.

## Per-vendor signals + observed drop rates

Snapshot from a 24h dry test on 2026-05-21:

| Vendor   | Drop signal that fires | Discovered | Dropped | Kept | Drop rate |
|----------|------------------------|-----------:|--------:|-----:|----------:|
| anz      | n/a (no EQUITY in feed)|         18 |       0 |   18 |        0% |
| barclays | `barclays-discipline`  |        236 |     143 |   93 |       61% |
| bnp      | n/a (no EQUITY in feed)|         12 |       0 |   12 |        0% |
| goldman  | `1-ticker` (incl. RIC) |        271 |     135 |  136 |       49% |
| hsbc     | `1-ticker` (title regex, added 2026-06-02) |         11 |       0 |   11 |        0% |
| ms       | `ms-default-drop`      |        280 |     265 |   15 |       95% |
| nomura   | `1-ticker` (BB pair)   |         95 |      29 |   66 |       31% |
| **total**|                        |    **923** | **572** | **351** | **62%** |

The 2026-05-21 snapshot shows HSBC dropping 0/11 — but that's stale.
Re-running on 2026-06-02 we discovered that the HSBC ``Equities`` feed
*does* carry heavy single-name coverage (HK/CH/IN/US tickers), it just
wasn't being recognised because the HSBC classifier didn't mine
tickers. Title-regex ticker extraction landed in ``classifiers/hsbc.py``
on 2026-06-02; HSBC now drops ~5/day (Dis-Chem, UPL, Meituan-style
notes) via the standard ``1-ticker`` branch. The pre-filter cleanup at
[`cleanup_hsbc_single_name.py`](../../../playground/research/cleanup_hsbc_single_name.py)
removed 60 leaked single-name HSBC rows already in the corpus.

ANZ and BNP still drop nothing at this stage — their daily feeds are
overwhelmingly macro/rates/FX/commodities and never tag
``tickers``/``issuers``. BNP additionally drops ~9/day at the *earlier*
discovery filter (chart-pack boilerplate, see
[scrapers/bnp.md](scrapers/bnp.md#filter-scope--recommendation)), so
the "Discovered" column above is already net of that. MS drops
aggressively because of the default-drop rule. Goldman and Nomura
drop a healthy minority via ticker extraction.

## How each vendor surfaces tickers (for the n_tickers==1 rule)

| Vendor   | Source of ticker tags |
|----------|------------------------|
| anz      | none (feed is mostly macro / rates / FX) |
| barclays | none (falls back to `barclays-discipline`) |
| bnp      | none — feed is pure macro/strategy; never tags `tickers`/`issuers`. Relevance filter is a no-op (the chart-pack drop happens at the discovery filter instead) |
| goldman  | `primaryCompanyTickers[]` + `companyTickers[]` listing fields. **Title-regex fallback** when both are empty — catches RIC `(601231.SS, NC)` and Bloomberg-pair `(AAPL US)` formats. |
| hsbc     | title regex `_BB_TICKER` (Bloomberg pair `(SYM EXCH)` — added 2026-06-02). HSBC titles encode single-name coverage as `{Company} ({SYM} {EXCH}) {Buy\|Hold\|Sell\|Initiate}: {topic}`. SYM 2–9 alnum, EXCH from the global Bloomberg code list. `Equity Strategy` product is excluded from the drop. |
| ms       | title regex `\(([A-Z0-9.]{1,12})\s+([A-Z]{2,3})\)` — works in theory, but MS titles rarely include tickers. Default-drop handles the rest. |
| nomura   | title regex (same Bloomberg-pair format as MS). Nomura titles routinely include tickers — e.g. "Gift Holdings (9279 JP) (Buy)". |

## Cross-vendor EQUITY conf / sales-event drop (2026-06-10)

Per-vendor allowlists (`_GS_EQUITY_KEEP`, `_CITI_EQUITY_KEEP`, etc.)
default-drop EQUITY but escape via macro-flavoured title keywords —
`themes` / `positioning` / `cross-asset` / `strategy`. A 2026-06-10
content audit ([`_takeaway_samples.txt`](../../../playground/research/_takeaway_samples.txt))
showed that 45 conference / sales-event takeaways were slipping through
these allowlists because their titles read like macro content but their
bodies were stock-pick takeaways from sell-side conferences (Goldman
Communacopia, Barclays REITWeek / KOL lunches, DB dbAccess, Citi UB
client briefings, etc.).

Added [`_is_equity_conf_event(title)`](../../../playground/research/ingest/relevance.py)
which fires immediately after the `asset_class != EQUITY` early-return,
**before** the per-vendor allowlist. The regex matches:

* `takeaways?` stem (Trip Takeaways, Key Takeaways from X, Meeting
  takeaways, Takeaways from Bain's report, etc.)
* `trip notes` / `field trip` / `investor field trip` / `NDR` / `CMD` /
  `investor day` / `investor event`
* `KOL` / sales-event meal formats (`lunch with`, `lunchtime snack`,
  `breakfast with`, `analyst dinner`, `fireside chat`)
* Branded conferences — `dbAccess`, `Communacopia`, `REITWeek`,
  `Money20/20`, `AGA Financial Forum`, `ASCO Gynecology/Breast/Lung`,
  `GS Travel Conference`
* Sector-anchored conferences — `<sector> conference` where sector ∈
  {utilities, financials, tech, banks, healthcare, biotech, pharma,
  materials, energy, autos, retail, insurance, REITs, TMT,
  semiconductors}

The regex is intentionally coarse — MACRO-tagged titles like
*"Romania: takeaways from May liquidity"* or *"Trip Notes from Berlin"*
or *"IMF Second Review: Our 10 Takeaways"* also match the regex but
bypass the drop via the asset_class gate. That's the contract: the
asset_class is the discriminator, not the title pattern.

Net effect (smoke against 4,498 dim_report titles):

| vendor | EQUITY conf-event drops |
|---|---|
| goldman | 27 |
| barclays | 10 |
| db | 3 |
| nomura | 2 |
| MACRO-bypass (regex hit, kept) | 10 (ms 4, jpm 3, citi 2, goldman 1) |

Test pin: [`test_relevance_conf_event.py`](../../../playground/research/test_relevance_conf_event.py).
Smoke harness: [`_smoke_conf_event.py`](../../../playground/research/_smoke_conf_event.py).

### Goldman classifier Tier-4 backfill

The cross-vendor regex relies on `asset_class == EQUITY`. The 2026-06-02
DB audit had flagged 144 Goldman rows with **blank `asset_class`** —
Tiers 0-3 (focus, girAssetTypes, disciplines, title-regex) all returned
empty. These rows silently bypass the entire relevance filter because
`if result.asset_class != ASSET_CLASS_EQUITY: return False, ""` exits
early on blank.

Added a Tier-4 fallback to
[`classifiers/goldman.py::classify`](../../../playground/research/ingest/classifiers/goldman.py)
in the same 2026-06-10 milestone:

* `Macro` in `subjects[]` → asset_class = MACRO
* Non-empty `industries[]` OR `focus` not "Issuer" → asset_class = EQUITY

Routes the 144 historical Goldman blank-asset_class docs into the right
bucket; the EQUITY ones then fall through `_is_equity_conf_event` and
the existing `_GS_EQUITY_KEEP` allowlist.

## Trade-offs to know about

- **MS sector previews are caught by default-drop.** Things like "IT
  Hardware: Off-Cycle Earnings Preview" (a sector-level multi-name
  preview) get dropped along with single-stock notes. If you want
  those back, build a sector-pubtype allowlist for MS rather than
  relaxing the rule globally — MS's listing genuinely doesn't ship
  enough signal to tell sector from single-name otherwise.
- **Goldman has ~5% slip-through.** EQUITY reports where neither
  metadata nor title has tickers (sector views, conference roundups,
  multi-pipe digests) survive the filter — most are correctly kept,
  but the occasional single-name note that omits parenthesised
  tickers (e.g. "USI Mgmt. visit") will slip through. Inspect with
  [`inspect_goldman_survivors.py`](../../../playground/research/inspect_goldman_survivors.py).
- **No country-of-ticker inference yet.** A single-name note that
  happens to be a USD-rates relevant single name (e.g. a Citi bank
  note that touches treasury issuance) gets dropped along with pure
  consumer-coverage. Trade-off accepted: cleaner corpus matters more
  than catching every relevant edge.

## Files

| Where | What |
|---|---|
| [`playground/research/ingest/relevance.py`](../../../playground/research/ingest/relevance.py) | `apply_relevance_filter()`, `is_single_name_equity()` |
| [`playground/research/ingest/classifiers/`](../../../playground/research/ingest/classifiers/) | Per-vendor `classify(ref) -> ClassifyResult` (produces the signal the filter reads) |
| [`playground/research/ingest_today.py`](../../../playground/research/ingest_today.py) | Multi-vendor orchestrator — wired into `_run_vendor()` immediately after `discover()`. Gated on `settings.research_drop_single_name_equity`. |
| [`playground/research/ingest_today_*.py`](../../../playground/research/) | Per-vendor scripts — wired immediately after `discover_reports()` (same gate). |
| [`playground/research/test_orchestrator_filter_wired.py`](../../../playground/research/test_orchestrator_filter_wired.py) | Regression test pinning the orchestrator's filter call (AST check). |
| [`playground/research/cleanup_filter_violations.py`](../../../playground/research/cleanup_filter_violations.py) | One-shot cleanup tool — replays `is_single_name_equity()` from persisted classifier output to find and remove leaked rows (DB + Qdrant + OneDrive). |
| [`playground/research/cleanup_hsbc_single_name.py`](../../../playground/research/cleanup_hsbc_single_name.py) | Vendor-specific cleanup for HSBC single-name notes ingested before the 2026-06-02 classifier update. Dry-run by default; `--commit` deletes DB rows + Qdrant points + OneDrive PDFs. 60 reports removed on 2026-06-02. |
| [`playground/research/probe_hsbc_single_name.py`](../../../playground/research/probe_hsbc_single_name.py) | Probe — runs the HSBC crawler + draft single-name regex against the live listing, prints kept/dropped split. Used to design the title regex before wiring it into the classifier. |
| [`playground/research/dry_test_all_vendors.py`](../../../playground/research/dry_test_all_vendors.py) | Dry-run across all 7 vendors with the filter applied — no fetches |
| [`playground/research/inspect_goldman_survivors.py`](../../../playground/research/inspect_goldman_survivors.py) | Per-vendor survivor inspection — quantifies slip-through |
| [`src/imdr/config/settings.py`](../../../src/imdr/config/settings.py) | `research_drop_single_name_equity: bool = True` |

## Adding a new vendor

When a new vendor is added (e.g. JPM Markets eventually goes live):

1. Add `classifiers/{vendor}.py` exposing `classify(ref) -> ClassifyResult`
   that emits ticker tags where the listing API supports it.
2. Register in `classifiers/__init__.py:_VENDOR_CODES` + `get_classifier`.
3. If the vendor doesn't ship tickers, add a vendor-specific branch to
   `relevance.is_single_name_equity()` with a one-line `[!]` justification
   describing what signal you're using and why.
4. Run `python playground\research\dry_test_all_vendors.py` once to
   eyeball drop rate and a sample classification, then add the vendor's
   row to the snapshot table above.

## Wiring rule

The filter must be called immediately after `discover()` / `discover_reports()`
and **before** any limit / dedup step. Two entry points exist today
(`ingest_today.py` orchestrator + per-vendor `ingest_today_{vendor}.py`)
and **both** must call it. Loss of the call in the orchestrator silently
leaked single-name equity coverage for ~2 weeks (cleanup on 2026-05-23,
[`cleanup_filter_violations.py`](../../../playground/research/cleanup_filter_violations.py));
the AST regression test pins the wiring so it can't happen again.
