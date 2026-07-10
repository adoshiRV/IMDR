# The Weekly Country Read — pipeline + assembly spec

This is the canonical spec for **the weekly** — restructured (2026-06-23) from an
**event-first** roundup into a **country-first** structured economic read: per
country, the macro events, the analysis, the sell-side desk view, and the
estimates — all in one fixed structure. It supersedes the event-first weekly
layout in [weekly_brief_spec.md](weekly_brief_spec.md) (which now governs the
*daily* summary + Lois's sell-side stage within this pipeline).

The mental model: **a combined, very structured, concise read into each economy +
sell-side thoughts + macro events + estimates.** The unit is the **country**.

- **Status:** active spec — the restructured weekly ships from here.
- **Owner:** **Perry** (editor-in-chief). Perry does not author the macro view or
  the sell-side summaries himself — he **commissions** the four input layers,
  enforces the fixed per-country structure + coverage floor, stitches them into
  one MD, and hands the locked MD to Picasso. He is the assembler, not a content
  author. (Newsroom: Perry edits; Lois reports; Atlas strategises; the engine
  computes; Picasso designs.)
- **Cadence:** weekly. Default period = the Sunday-prior (matches the old weekly).

---

## 0 · Perry's MAIN SWITCH — the flagship sell-side sweep (do this FIRST)

**Before any per-country assembly, sweep the banks' flagship weeklies — and do NOT
select sell-side by title keyword.** This is the governing rule, established
2026-06-23 after an audit found a country-keyword title match used **~1% of the
~3,200 reports** in the run-up week and was *structurally blind* to the best
content:

- **Flagship weeklies are GLOBAL-titled** — "Global Fixed Income Markets Weekly"
  (JPM, ~200-288 chunks), "Global Rates Weekly" (Barclays), "FX and Rates Weekly"
  (Nomura, ~181), "Global Economics Weekly" (Barclays, ~130), "Global FI Weekly"
  (DB), "Global Rates Ideas" (HSBC). No country in the title → a country-name join
  drops every one. **These carry per-country rates/FX sections and are the BACKBONE
  of a country-first weekly** — read them in full and parse their per-country views.
- **MS and BofA title thematically** — MS macro = "A Pause, Not a Peak",
  "Assessing the Trade-Offs"; BofA rates = "EUR/Dollar/POUND SSA Report", "Treasury
  RV/Basis Report", "Task force hawkish". No "weekly", no country, no "rates"
  keyword → invisible to any title filter despite being deep rates content
  (BofA SSA suite alone ~200+100+97+63 chunks). Reach them by **`asset_class` +
  `region` + vendor**, not title.

**The sweep — COMPREHENSIVE, every bank, BOTH directions:**
0. **Cover EVERY bank's macro weeklies in the preceding week — both families:** the
   backward *past-week* reviews ("…Weekly", "Week in Review", "Recap", "Global
   Rates/FI/Economics Weekly") AND the forward *week-ahead* pieces ("Week Ahead",
   "Weekly Prospects", "Look Ahead", "Preview"). Both are well-populated every week
   (21-Jun run-up: JPM 19 / DB 16 backward weeklies; GS 12 / DB 9 / Citi 8 / JPM 5
   week-ahead pieces). **"All banks" means all** — the sweep is exhaustive over the
   macro/rates/FX/econ set, not a sample.
1. **Select by `dim_report.asset_class` (MACRO / RATES / FIXED INCOME / FX / ECON /
   STRATEGY) + `region`** — NOT title. (Audit: MS files **128 macro-relevant reports**
   [102 MACRO + 18 RATES + 8 FX] in one week, 69 `country_id=NULL` and all
   thematically-titled — "A Pause, Not a Peak" — invisible to a title/country filter
   but trivially caught by `asset_class`. That is why MS looked "missed.") The
   flagship-weekly title patterns are a SEED on top, never the gate.
2. **PRIMARY discovery = Qdrant semantic search (MANDATORY) — this is the point
   of the corpus, not optional.** Use the CLI:
   `python playground/research/retrieve.py "<question>" --k N [--vendor X] [--group-by-report]`
   — Qdrant ANN over the embedded corpus, returns cited chunks
   (`vendor · report_id · chunk_idx · page · score`). Run a query **per country ×
   theme/event** ("what does the street say on the Fed / JGBs / BI / RBA / AU
   labour / EU inflation?"). Semantic retrieval finds the right passages
   **regardless of title / asset_class / country tagging** — which keyword SQL
   structurally cannot. The SQL `asset_class`/`region` selection (point 1) is the
   **COMPLEMENT** — for the exhaustive coverage tally and the long tail — NOT a
   substitute for semantic search.
   - Access: Qdrant on `127.0.0.1:6333`, collection `research_gemini_embedding_2_3072d`;
     the CLI embeds the query via Gemini. Env needs `google-genai`/`qdrant-client`/
     `voyageai` (installed 2026-06-23 per the owner-recovery note).
   - **RULE — every semantic query MUST be time-bound.** Always pass
     `--since/--until` scoped to the edition: backward (1A) reads use
     `--since <edition−7d> --until <edition>`; forward (1B) week-ahead reads use
     the publish window of the days just before the edition. A macro weekly must
     **never** surface a stale desk note as "this week's view" — an un-windowed
     retrieval is a defect. (The `--since/--until` DatetimeRange filter was fixed
     2026-06-23; it now filters server-side correctly — no client-side date-dropping.)
3. **Read the flagship cross-asset/rates/econ weeklies in full** and parse their
   per-country sections → these seed each country's Block D + the cross-country
   narrative. Country-specific notes are added *after* this spine, not instead.
4. Report the sweep coverage (reports considered vs used) so the miss is visible.

This is **Lois's job at scale** (Stage 3 below), but Perry owns the *switch* — he
does not accept a sell-side layer built off a country-name title match.

## 1 · The pipeline — who does what

A **4-source pipeline into one MD**, assembled by Perry:

```
STAGE 1  ENGINE (deterministic)        per-country macro events + surprises + estimates
         rates-playbook engine          → blocks B (events) + E (estimates) DATA
         + calendar.cb_events            (actual vs consensus → surprise score; forecasts)

STAGE 2  ATLAS (content)               cross-country layer + per-country read
         atlas_brief_spec.md             → Part 1 (narrative · tape · ladders)
                                         → blocks A (read) + C (what it means)

STAGE 3  LOIS (content)                per-country sell-side summaries, keyed to
         weekly_brief_spec.md            stage-1 events → block D
                                         (verbatim-grounded from the research corpus)

STAGE 4  PERRY (assembly)              stitch Part 1 + per-country A-E blocks into
         THIS spec                       one country-first MD; enforce the coverage
                                         floor + depth tiering; Sources appendix

STAGE 5  YOU                           review + lock wording

STAGE 6  PICASSO (design)              render locked MD → HTML (country-first weekly
         picasso_operational_spec.md     template)
```

Stages 1-3 can run in parallel (they're independent); Perry (stage 4) joins them.
The engine is deterministic and runs first because stages 2-3 reference its event
set (Atlas comments on the events; Lois summarises the desk view *on those
events*).

> **Each agent stays in its lane.** Atlas does not summarise sell-side reports
> (that's Lois); Lois does not compute surprises (that's the engine); Perry does
> not invent macro views (he arranges what the three produce). This is the
> "pipeline → one MD" model, not "one agent does everything."

## 2 · Document structure

### Part 1 — The macro calendar (the spine: past week → moving ahead)

Structure Part 1 as a **full-scale macro calendar in two halves**, each synthesising
**every bank's** weeklies (per §0 — backward reviews feed 1A, week-ahead pieces feed 1B):

**1A · The week that was.**
- **Narrative** — 3-5 cross-country themes.
- **The tape + ladders** — cross-asset scorecard (all roster) + the RV ladders
  (real-rate · carry · growth-momentum · data-surprise · CB-pricing).
  - **RATES-TAPE SOURCE RULE.** The tape's rates columns use **government bond
    yields** — the tradeable benchmark a macro desk actually reads (IndoGB for
    Indonesia, UST / ACGB / JGB / Bund / gilt for DM). **NEVER use a money-market
    IBOR fixing (JIBOR, etc.) as the rates read** — it is not the curve anyone
    trades off. A DM **OIS swap** curve (SOFR/SONIA/ESTR/TONAR/AONIA) is an
    acceptable *explicitly-labelled* proxy for the DM curve move; an **EM IBOR
    fixing is not** a substitute for the govt bond yield. Where the govt bond
    yield isn't loaded in IMDR, show "—" and **flag the gap** — do not paper over
    it with a money-market rate. (Data state 2026-06-24: `rates.fact_bond_yield`
    is empty; **IndoGB and most EM benchmark yields are NOT loaded** — that's the
    onboarding gap behind the EM "—" cells.)
- **What printed** — the past-week event calendar (actual vs consensus → surprise).
- **Street synthesis (backward)** — what the banks' *past-week* weeklies (Global
  Rates/FI Weekly, Global Economics Weekly, FX & Rates Weekly …) concluded about the
  week, grouped by theme, cited.

**1B · Moving ahead.**
- **The forward calendar** — upcoming 1-2 wks, consensus + street estimate.
- **Street synthesis (forward)** — the banks' *week-ahead* pieces (Week Ahead,
  Weekly Prospects, Look Ahead) — what the desks expect and how they're positioned,
  grouped by theme/event, cited.

Part 2 then drills into each country (the calendar's read, applied country-by-country).

### Part 2 — Country sections (regional groups; the heart)

Every country gets the **same fixed 5-part block** (§3). Regional order: North Asia
· South/SE Asia · Developed Markets · Antipodes (Atlas roster order).

## 3 · The per-country block (the fixed unit)

```
### <Country> (<ISO>)  · regime <tag> · conviction <1-5> · tier <A|B|C>

A. READ            2-3 sentences: the regime + this week's bias + conviction.
                   The concise "read into the economy". [Atlas]

B. MACRO EVENTS    Table — two halves:
                     • Printed this week: date · indicator · actual · consensus
                       · surprise (the engine's signed score) · 1-line read
                     • Upcoming (1-2 wks): date · indicator · TE consensus
                       · **+ the SELL-SIDE reading/expectation where a desk
                       previewed it** (what the street expects, not just TE's
                       number — pulled from the corpus, see block D sourcing)
                   [engine + cb_events + corpus]

C. WHAT IT MEANS   Country-wise commentary connecting the events to the read —
                   what the prints/decisions changed, what they confirm. [Atlas]

D. SELL-SIDE DESK  Structured summaries of the reports ON those events, grouped
                   (consensus / dissent / tail), **VERBATIM** with
                   [vendor, report_id, chunk_idx]. Organised by event/theme, not
                   by vendor. [Lois]
                   ── Sourcing (READ THIS): the corpus is the SQL table
                   `research.fact_chunk.chunk_text` (174k rows), reachable via
                   `mcp__imdr-db` EVEN WHEN the Qdrant semantic-search MCP is
                   offline. Block D is NEVER titles-only when the DB is up.
                   • **Flagship-first (§0): start from the global weeklies +
                     `asset_class`/`region`, NOT a title keyword.** Country-name
                     title matching is structurally blind to the best content —
                     global-titled weeklies (JPM/Barclays/Nomura/DB/HSBC) and
                     thematically-titled MS/BofA notes — and to `country_id=NULL`
                     (which the big desks all use). Title/keyword is a supplement.
                   • Pull `chunk_index` 1-4 (chunk 0 is usually a disclaimer /
                     watermark), cherry-pick 2-3 substantive verbatim sentences
                     per vendor. Never paraphrase; quote or omit.

E. ESTIMATES & CALL  Consensus + street + house estimate for the upcoming prints;
                   the positioning / trade expression if there is one.
                   **The "street" number is a real desk forecast/reading from the
                   corpus (block D sourcing), not a restatement of TE consensus.**
                   [engine + Lois + Atlas]

F. POTENTIAL TRADES  A TABLE of the actionable trade ideas the desks published for
                   this country this week. Columns: **Trade · Expression ·
                   Rationale · Desk(s) [report_id·chunk_idx]**. Verbatim-sourced
                   from block D — rates/FX/credit expressions (e.g. 2s10s flattener,
                   pay 2y, receive OCR, long INR carry, BTP/Bund tightener, long
                   AUDNZD). **Every row cites the report it came from; never invent a
                   trade.** If no desk trade is cited for a country, write "no desk
                   trade ideas cited this week" rather than fabricating one. [Lois ← corpus]
```

Read top-to-bottom it answers: **the read → the events → what they mean → what the
street says → the estimates.** That is the deliverable in one block.

## 4 · Coverage rule (the decided policy)

**Dynamic depth, but a hard floor: every roster country gets the complete A-E
block every week.** No country ever collapses to a bare read line.

- **Floor (all countries):** the full 5-part block — Read + at least the event
  table + a sell-side line + the estimate. Proper coverage everywhere.
- **Spotlight (the week's live 3-5):** *expanded* depth on top of the floor —
  more events detail, broader sell-side (more desks, dissent + tail), a scenario
  map on the marquee print, and charts. Depth follows the week's action.
- A country with a genuinely quiet week still shows its block; block B simply
  reads "no high-relevance prints; next: <upcoming>" rather than being dropped.
- **Tier (A/B/C) is shown, not used to drop coverage.** A thin-data country
  (tier C) still gets its block; it just carries fewer scored events + leans more
  on sell-side/qualitative — and says so. Tier limits *grounding*, never coverage.

> The failure mode this rule kills: the old instinct to collapse quiet countries
> to one line. You asked for proper coverage for all + more depth where it's
> warranted — the floor enforces the first, the spotlight delivers the second.

## 5 · Source mapping + the estimates layer

| Layer | Source | Notes |
|---|---|---|
| Surprises (block B "printed") | rates-playbook engine over `calendar.cb_events` | signed surprise score per the [driver taxonomy](../econ/macro_driver_taxonomy.md) |
| Upcoming events + consensus (B/E) | `calendar.cb_events` `forecast`/`survey` + known CB calendars | consensus = the estimate; never invent one |
| Cross-country narrative · tape · ladders (Part 1) | Atlas | the data-surprise ladder = the engine composite |
| Read + what-it-means (A/C) | Atlas | per-country thesis + event commentary |
| Sell-side summaries (D) | Lois ← **`research.fact_chunk.chunk_text`** (verbatim) joined to `dim_report` | Match by **title/event keyword + `publish_date`**, NOT `country_id` (big desks file NULL). Chunks 1-4, cherry-pick. SQL-reachable without Qdrant. |
| Street consensus on the WEEK (B-upcoming + E) | Lois ← corpus desk previews/forecasts | The calendar's upcoming events carry the **sell-side reading/expectation** for the week, alongside TE consensus — what the desks expect, sourced + cited. Distinct from `cb_events` consensus; show both. |
| Structural "what to watch" spine | Mercator cluster map (per country) | informs A/C; not rendered inline |

**Estimates are first-class.** Block E carries *three* numbers where they exist:
**consensus** (`cb_events`), **street** (sell-side desk forecasts via Lois), and
**house** (the desk's call). Show the spread between them — that spread is the
setup.

## 6 · Sources appendix

Same discipline as the sibling specs. Every number, surprise, quote, and estimate
traces to an entry. Because this MD is assembled from three authors, **Perry
preserves each stage's source citations** — he does not re-derive them. Blocks:
§ SQL (engine queries + Atlas's IMDR pulls) · § research (Lois's report IDs +
chunk indices) · § repo/docs · § web. HTML surfaces research + web (per the
Picasso §3.5 carve-out).

## 7 · Output

```
data/research_summary/weekly/{YYYY}/{MM}/{DD}/weekly_country_read_{YYYY-MM-DD}.md   ← assembled (Perry)
data/research_summary/weekly/{YYYY}/{MM}/{DD}/weekly_country_read_{YYYY-MM-DD}.html ← rendered (Picasso)
data/research_summary/weekly/{YYYY}/{MM}/{DD}/{charts,bank_pdfs,assets}/            ← per-brief assets
```

Stays under the existing weekly home (`data/research_summary/weekly/`) — this IS
the weekly. Per-brief-folder asset discipline applies.

## 8 · Hard rules

1. **Country-first.** The unit is the country; events/sell-side/estimates nest
   inside the per-country block — never the reverse.
2. **Every country, full block, every week.** Coverage floor is non-negotiable
   (§4). Spotlight adds depth; it never licenses dropping a country.
3. **Stay in lane.** Engine computes; Atlas reads; Lois summarises sell-side;
   Perry assembles. No agent does another's job.
4. **Estimates are first-class** — consensus + street + house where they exist;
   show the spread; never invent a consensus. The **calendar's upcoming events
   carry the sell-side reading** for the week (street expectation), not just TE's
   number.
5. **Sell-side is VERBATIM from `research.fact_chunk`** (SQL-reachable via
   `mcp__imdr-db` even with Qdrant offline) — titles-only is a defect when the DB
   is up. Match reports by **title/event keyword + publish_date**, not
   `country_id` (big desks file NULL). Grouped by event/theme, not vendor; cited
   `[vendor, report_id, chunk_idx]`.
6. **Numbers re-queried live** each week (surprises, levels, estimates).
6b. **`cb_events` is NOT truth.** It is the source for the *consensus/forecast* and
   the *event calendar* only. The realised **actual** comes from official sources
   (`econ.fact_indicator`) or the **corpus**; the **policy action** (hike/hold/cut)
   comes from the official rate series or the corpus — never from `cb_events`'
   label (it stores levels, so an expected hike reads as a "hold"). If `cb_events`
   and the corpus disagree on what happened, the **corpus/official source wins** and
   the reconciliation is flagged. See [macro_driver_taxonomy.md §5](../econ/macro_driver_taxonomy.md).
7. **Tier shown, not used to drop coverage** (§4).
8. **Perry preserves citations** from each stage; the assembled MD is fully traced.
9. **Content locks at your review** (stage 5); Picasso never edits wording.
10. **No prod-wiring without explicit OK**; read-only DB; commits via `imdr-git`.

## 9 · Pre-ship checklist (Perry, stage 4)

- [ ] Part 1 present (narrative 3-5 themes · tape + 5 ladders · consolidated event map).
- [ ] **Every roster country has a complete A-E block** (the floor) — none collapsed.
- [ ] Spotlight countries (the week's live set) carry expanded depth (extra events/
      sell-side/scenario/charts).
- [ ] Block B shows surprise on printed + consensus on upcoming; no invented consensus.
- [ ] Block D grouped by event/theme, verbatim, cited; block E shows consensus/street/house spread where available.
- [ ] Source citations from all three stages preserved; nothing un-traced.
- [ ] Path under `data/research_summary/weekly/...`; per-brief assets local.

## 10 · Invocation

| User says | What happens |
|---|---|
| "the weekly" / "weekly summary" / "weekly country read" | Full pipeline → Perry assembles → you lock → Picasso renders. |
| "weekly, spotlight Japan + India" | Same; JP/IN get expanded depth, all others still full block. |
| "just the cross-country frame" | Part 1 only (Atlas tape + ladders + narrative). |
| "the daily" | **Not this** — daily summary is Lois's event-first lane ([weekly_brief_spec.md](weekly_brief_spec.md)). |
| "global macro weekly" (standalone) | Atlas's own deliverable ([atlas_brief_spec.md](atlas_brief_spec.md)) — here it's a *stage*, not the product. |

## 11 · Reference

| Asset | Location | Role |
|---|---|---|
| Perry agent def | `.claude/agents/perry.md` | The assembler |
| Atlas spec | [atlas_brief_spec.md](atlas_brief_spec.md) | Stage 2 — cross-country + read |
| Lois spec | [weekly_brief_spec.md](weekly_brief_spec.md) | Stage 3 — sell-side summaries; also owns the daily |
| Rates-playbook engine | `playground/econ/rates_playbook/` | Stage 1 — events + surprises + estimates |
| Driver taxonomy | [../econ/macro_driver_taxonomy.md](../econ/macro_driver_taxonomy.md) | The surprise scoring shared by Part 1 + block B |
| Mercator spec | [cluster_map_spec.md](cluster_map_spec.md) | Structural spine informing the per-country read |
| Picasso spec | [picasso_operational_spec.md](picasso_operational_spec.md) | Stage 6 — render |

---

**Country-first. Every country covered, the live ones deeper. The engine finds the
events, Atlas reads them, Lois brings the street, Perry sets the page, Picasso
prints it. One structured read into each economy.**
