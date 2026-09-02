# Spider — WEEKLY digest spec (self-contained)

The **WEEKLY** edition of Spider: **ONE document covering the whole universe**, in two
tiers — a **~5-page cross-universe executive summary** on top, then a **per-country
deep section** for every country, each written in the gold-standard *driver-sectioned,
judging* style (the RVC single-country rates & FX weeklies: Korea "50bp on the Table",
Japan "Strong Data Meets Fiscal Dominance"). This spec is **independent of the
daily** — it defines the weekly's complete structure. **Never import the daily's
structure** (the daily's "Deltas-since" lead, its universe CB dashboard, its per-country
A/B/C/D layout). The weekly is its own shape.

Shared fundamentals — persona, coverage universe, asset classes, the grounding
layers, voice, hard rules — live in `spider.md` and apply here, **with two weekly-only
departures**: the weekly is organised **by driver within each country** (not a fixed
block template), and the weekly **JUDGES** (an Argument Audit per country + a
cross-universe tensions read + "so-what for the book" callouts), where the daily is
neutral. This doc is only the weekly's *structure*.

---

## The three defining choices

1. **One doc, the full Asia + G10 roster** (~17 markets — see `spider.md` coverage
   universe; **Vietnam is OUT of scope**, dropped 2026-07-27 — no VN section, matrix row,
   or calendar line). Not one file per country. The universe is covered in
   a single weekly, so a PM reads the global picture and then drills into any country.
   Coverage floor: **every country gets a real section**; depth scales with what moved
   (a live-regime country runs deep; a quiet one collapses to an honest short read —
   never dropped, never padded).
2. **Topic-organised, then driver-deep — not a fixed template.** Each country section
   starts by naming **the topics that matter for that country this week**, chosen from
   two sources: (a) what is **structurally relevant** to that economy (its real macro
   drivers — external funding, the fiscal/supply picture, the currency channel, the
   policy-rate path), and (b) **what the banks are actually discussing** this week. Derive
   both from the in-window corpus — do not pre-load a fixed topic list per country. Those topics — not a
   rigid block, and not "whatever the sell-side weekly happened to cover" — decide which
   **driver sections** exist. Each driver then goes deep on one topic/force (inflation ·
   the CB decision · govt-bond supply/demand · the currency · the fiscal shock · the
   equity-macro transmission …). The week's *real story* leads. If a country has no live
   topic, it does not get manufactured drivers — it gets an honest short read (see the
   quiet-country rule).
3. **It JUDGES.** Unlike the daily (neutral, no-judge), the weekly carries explicit
   judgment — a cross-universe tensions read in the summary, a **mini Argument Audit**
   (`Solid`/`Weak`/`Stale`) per country, and "so-what for the book" callouts. This is
   the highest-value layer and a deliberate weekly-only override of Spider's daily
   no-judge rule (flagged in `spider.md`).

**Cadence.** Published **Sunday night**, ahead of the Monday open. **Length scales with
the week** — the ~5-page summary is fixed; the country tier is as long as the drivers
warrant (movers deep, quiet countries short). Length comes from real drivers + insight,
never padding.

## The temporal spine — three buckets (the Sunday-night vantage)

The weekly is read across **three time buckets**, and this spine runs through **both
tiers** — the Tier-1 summary gives the universe view of each bucket; every Tier-2
country gives its own. **All three carry the same rigour and structure** (② is the
largest only because estimates + assumptions + divergence live there — it is not
"more important", it is heavier). This is **additive**: it sits on top of everything
already in the structure below; nothing is removed.

- **① The week that was** (prior Mon–Sun) — *what actually happened.* The prints,
  decisions and moves; actual vs consensus vs prior; the surprises and the tape.
  Grounded to `cb_events` actuals + `econ.fact_indicator` + the market-moves layer.
- **② The week that is** (the trading week now starting) — **the heaviest, most
  analytical bucket.** The scheduled prints/decisions with **consensus / estimates** and
  **what's already priced**, and — the point of the whole edition — a **cross-cut** that
  **digs into the assumptions each call rests on, the themes in play, and exactly where
  the desks differ and why.** Lay it out **tabular** first, then reason underneath. This
  is where the weekly earns its keep.
- **③ The week ahead** (the following week) — **lighter, but the same depth of thought
  and the same structure** — never a bare calendar line. The setup, the consensus/prior,
  what each event *tests*, and the early lean.

---

## The reusable kit (components both tiers draw from)

- **Editorial thesis line + deck — factual, not a slogan.** A plain, descriptive line
  that states the week's dominant *fact* (what actually happened / what dominated the
  tape), used for the doc masthead and again per country. **Factual > headline:** no
  flashy wordplay, no punchy slogans, no forced narrative arc. If the week has **no single
  clean argument**, say that plainly ("a mixed week; two unrelated stories") — never
  manufacture a thesis to have one. The title reports; it does not sell.
- **Hero stat band — decompose the *why* in the cell** (the daily's bar). A row of big
  numbers, but each caption **decomposes the number** — the components/categories behind
  it *and* the memory (survey / prior) — not a one-line label. Not "US CPI 3.5% (survey
  3.8%)" but "US CPI **3.5%** — energy −6.4%, core goods flat, OER cooled to +0.24% → core
  0.0% m/m; survey 3.8%, prior 4.2%". Universe-level band (~6–8 numbers) in the summary; a
  compact 3–5-number line per country. Numbers and drivers, **never a literary metaphor**.
- **Desk-read table — consensus & divergence, with the logic IN the cell** (this is the
  single biggest lift to the daily's bar). For every topic, a proper cross-bank read:
  **state the consensus in a line above the table**, then a detailed divergence table whose
  columns carry the *full argument*, not labels — **Desk · View / Call (with the house's own
  number) · Assumption → Falsifier · Resolver / when**. Rules for the cells:
  - **The View cell carries the house's specific number**, not a qualitative label — "raised
    the hike prob to 35% (from 25%)", "core-PCE tracking 0.18% m/m", "terminal 3.25% (Oct +
    Jan)" — never just "more dovish on the path".
  - **The `Assumption → Falsifier` lives IN the table**, one cell per house — the assumption
    the call rests on and the concrete, measurable thing that breaks it. Do **not** exile it
    to a callout below; the row must be an argument on its own.
  - **The `Resolver / when` column** names what settles the debate and the date (the print,
    the meeting, the data) — so the PM sees what to watch.
  Where a topic is a rate/level call, pair it with the **scoreboard** (House · Call ·
  Terminal / Target · Vehicle) so the consensus and the outliers are both legible at a glance.
- **Scoreboard table** — **House · Call · Terminal / Target · Vehicle** (rate calls), or
  **Leg · Evidence · Counterpoint** (a decision tree).
- **"So-what for the book" callout box** — short, boxed, titled; converts synthesis →
  position implication. Types: **PRICING WRINKLE WORTH TRADING · STOP-DISCIPLINE FLAG ·
  CARRY ARITHMETIC · BOOK-LEVEL NOTE · INTERNAL COHERENCE CHECK**. Use where a section
  has a clean edge; don't force one everywhere.
- **Chart-spec placeholder** — every major driver names one visual:
  `[FIG. {CC}_{KEY} — one-line caption]` (e.g. `[FIG. KR_CPI — the y/y peak has not
  printed yet]`). Author the placeholder + caption + the series it needs; **rendering
  is deferred**.
- **Reconciliation prose** — beneath each table: what the disagreement *means for
  positioning*, every number set against **the memory of what it was**.

---

## Table & language standards (the daily's bar)

The weekly must read like the daily's front-of-book, at the week horizon. Bring the
daily's content density and language discipline into every country section.

**Grounding-tag legend (tag throughout, define once in the appendix):**
`FACT` = official print / decision (`calendar.cb_events` **or** IMDR's own
`econ.fact_indicator`) · `DEPTH` = component series (`econ.fact_indicator`) · `VIEW` =
attributed sell-side interpretation / forecast (`research.fact_chunk` + Qdrant + Outlook)
· `PRICING` = observed market move / implied path · `SYN` = the desk's neutral
organisation of the evidence. Never let a `VIEW` read as a `FACT`.

**Language — lead with the surprise and whether price agreed.**
- **News-vs-price leads each driver.** Open with what surprised and **did price confirm the
  narrative or diverge?** — the w/w move set against the story. A divergence (the CB turned
  hawkish but the curve rallied; credit tightened but the currency didn't) is the
  high-value content — lead with it, don't bury it under the consensus.
- **Attribute every divergence, or flag it `[RV — …]`.** Name the catalyst behind a move; if
  there's no identifiable catalyst, say so and flag it as a **relative-value divergence**
  (the unexplained move *is* the idea). Never leave "X was the exception" hanging.
- **Separate the desk's own read from the houses'.** An attributed house view is `VIEW`
  with the house named; the desk's *own* inference is flagged inline `[RV — …]`, never
  slipped in as if a bank said it.
- **A number and its driver in (nearly) every clause.** Numbers over adjectives; cut the
  narrative connective tissue. Not "the front end sold off sharply" but "2y +19bp on the
  Iran/oil bid and a live July-hike premium".
- **No literary metaphor. Explicit dates, never relative day-names.** Ban "the second
  shoe / the tide / the gravity shifts". Write "June CPI (released 14 Jul)", never
  "Tuesday's CPI" or "last week's print".

**Repetition budget.** Each fact appears **once in its home** — the number in the hero band
/ matrix / house table, the debate in the tensions/dashboard, the drill-down in the country
driver, the report-id in the appendix — and is **cross-referenced, not restated**. The
single-doc habit of making every section self-standing is what produced the earlier
edition's repeated core-PCE / GPIF / FCNR restatements; do not repeat it.

---

## Structure

### Tier 1 — Cross-universe executive summary (~5 pages)
The global read a PM could stop after. **Lead with the edge, not a data march** — the live
debates, the news-vs-price divergences and the trade book come first; the data recap
(matrix, desk-by-desk, themes) is support underneath. Order:

1. **Masthead** — running header `RV CAPITAL · RATES & FX · WEEKLY CROSS-BANK
   SYNTHESIS`, the **editorial thesis line + deck** (factual, not a slogan — see the kit),
   the desk line (`{window} · Compiled {date}`), and a **Sources** line (houses covered
   + official docs, IMDR library).
2. **Bottom line (boxed).** 2–4 sentences: the working cross-universe regime this week and
   the cleaner relative-value questions it raises. The single most-read element — the edge,
   not a recap.
3. **Universe hero stat band** — ~6–8 numbers, each caption **decomposing the why** +
   memory (see the kit). Grounded to the market / econ / CB layers.
4. **PM dashboard — the live debates (the edge; leads).** A table of the week's
   **unresolved cross-universe disagreements**, the highest-value content, up front:
   **Debate · Centre of gravity · Differentiated view (assumption → falsifier) · Resolver /
   when**. The `Differentiated view` cell carries the house's *own number*; a brief
   `Solid`/`Weak`/`Stale` where the audit already resolves it. This is the fattened successor
   to the old "key tensions" preview and it *leads* the summary.
5. **What moved — and did price agree? (cross-universe).** The week's 5–8 decisive
   developments, **each once**: the move *decomposed* (which driver/components), then **did
   price confirm the narrative or diverge?** A divergence (a CB turned hawkish but the curve
   rallied; credit tightened but the currency didn't) leads and is **attributed to a catalyst
   or flagged `[RV — …]`** as a relative-value divergence. This is the weekly-horizon version
   of the daily's news-vs-price read.
6. **Cross-asset moves matrix** — the WoW table backing §5, all countries (ordered by what
   moved): **FX vs USD (WoW %) · 2y (WoW bp) · 10y (WoW bp) · equity (WoW %) · one-line
   read**, oil/vol/credit footnote. "n/l" where a series isn't loaded (label swap/OIS; cash
   govt yields not loaded). WoW moves obey the sign-discipline in Grounding.
7. **Street trade map — the universe book, split by STATUS.** One consolidated register
   feeding (not replacing) the per-country boards: **Status · House · Trade · Level / Entry ·
   Target / Stop · Why (rationale) · Risk · Falsifier**, grouped by status — **New
   expression · Revalidated · Closed / take-profit · No entry / cancelled · Macro view
   only**. One trade per row; multi-leg bundles split; a regime view is `Macro view only`
   until an instrument is named. Titled "Street trade map" (aggregated sell-side
   positioning) — **never "where the book tilts"** (that reads as RV's own book).
8. **The big cross-cutting themes (support).** The 4–8 strands the whole street is
   discussing, each *built up*: who introduced it, who corroborated with what numbers, who
   dissented, what breaks it. A `Sources:` line of report_ids ends each theme.
9. **Universe desk-by-desk (support / evidence).** **Bank · This week's flagship(s) ·
   Cross-country core message** — the map of what each house pushed. This is *evidence*
   under the edge above, not the spine — it sits here, demoted, not at the top.

   *(Sections 1–9 above carry **bucket ①, the week that was** — what printed and moved.
   Sections 10–11 below carry buckets ② and ③.)*

10. **This week — estimates & where the desks split (bucket ②, the heaviest).** The
    cross-cut. A **tabular** grid of the coming week's decision-grade events/themes across
    the universe: **Event / theme · Date · Consensus / estimate · What's priced · Range of
    house calls · The key assumption · Where they differ & why**. Then prose that **digs
    into the assumptions** (what has to be true for each call to work, and the tell that
    would break it) and the **theme divergences** (why two desks looking at the same data
    land in different places). This is the analytical heart of the weekly — give it room.
11. **The week ahead — preview (bucket ③, lighter, same structure).** A lighter table of
    the *following* week's setup: **Event · Date · Consensus / prior · What it tests ·
    Early lean** — plus a few tight lines. Lighter than §10, but the same discipline: no
    bare calendar dump, every line says what it *tests*.

### Tier 2 — Per-country deep sections (ordered by what moved)
Each country is a compressed gold-standard block. Assemble from the kit as the country
warrants:
- **Country header** — `{COUNTRY}` + a one-line country thesis + a compact hero-stat
  line (3–5 numbers).
- **Topics that matter (the lead — this decides the section). Built from "what has
  EVERYONE said".** Before any driver, run the **full cross-bank sweep on the country** —
  read what *every* house said about it in the window (the whole in-window corpus tagged to
  that country, all vendors, all note types), plus what's structurally live. The **union of
  that commentary surfaces the topic set** — typically **3–10 topics depending on the
  country** (a live, heavily-covered market yields 8–10; a quiet one 3 or fewer). This is a
  **relevance filter, not a view** — you are deciding *what to cover and what to ask*, not
  asserting a house call. Then:
  - **Dive into each topic PROPERLY** — one driver sub-section per topic, each carrying the
    full consensus-vs-divergence read (the fattened desk-read table above) built from *what
    everyone said* on that topic, not one flagship's take.
  - **Ensure every surfaced topic SHOWS UP.** If the cross-bank sweep found a topic, it
    appears in the output — a driver if it has grounded content, or a named **open question
    to watch** if it doesn't. A topic that everyone is discussing must never be silently
    dropped. (Conversely: **no topic may be invented to fill the template** — if the banks
    aren't discussing it and nothing structural is live, it isn't a topic.)
  - **Topics are NOT limited to scheduled macro events / data releases.** The most valuable
    topics are the **country-specific stories playing out in the corpus within the window**
    — a supply shock, a policy operation, a structural flow, a political event, a
    sector/commodity story — not just the calendar, and standing *alongside* (not instead
    of) the scheduled print or CB meeting. **Surface them from the in-window corpus**
    (Qdrant + `fact_chunk`) rather than from a pre-set list — let the notes tell you what's
    live — and **date-ground every one to the window** so an old story doesn't masquerade
    as this week's. Most countries will have a handful of these real, happening-now topics
    — find the ones the corpus actually carries.
- **Driver sub-sections** — **one per topic named above**, ordered by what moved that
  country's week; each = a title/kicker + whichever of {desk-read table · scoreboard ·
  chart-spec · reconciliation prose · so-what callout} the driver needs, always closing on
  a **position implication**. Cover rates · FX · equities · credit + the wealth-effect
  channel where live.
- **Country trade board** — the sell-side trade suggestions for the country, **with the
  why and the risk** (the proven format, reused from the older daily rates/FX trade
  tables): **# · House · Trade · Type · Level / Entry · Target / Stop · Why (rationale,
  verbatim where quoted) · Risk (what breaks it) · Status** (new / persists / target-hit
  / stopped / evolved). The **Why** and **Risk** columns are mandatory — a trade without
  its rationale and its risk is not tradeable content. Use `n/s` where a desk did not
  publish a field; never fabricate an entry/target/stop or a carry number. Close with an
  **INTERNAL COHERENCE CHECK** where trades interact (do two houses' trades express the
  same view, or contradict?).
- **Mini Argument Audit** — the country's 1–3 key tensions: **Tension · The two sides ·
  Assessment** with `Solid`/`Weak`/`Stale` and whose logic holds.
- **This week & next week (the country's buckets ② and ③).** In addition to the drivers
  above (which carry **bucket ①, what happened**), close each country with its forward
  read — a compact table: **When (this wk / next wk) · Event · Consensus / estimate ·
  The assumption · Where desks differ / what's priced**, then a line or two of the
  positioning read. Same discipline as the Tier-1 cross-cut, country-specific. A quiet
  country gets a short honest version; it is never dropped.
- **Quiet countries** — collapse to a short honest read (a paragraph + the forward
  table): the state of play, the one thing to watch this week and next, why it's quiet.
  Never dropped.

### Tier 3 — Audit appendix (INTERNAL — HTML only, NOT in the print PDF)
Everything that proves the doc without interrupting it. Like the daily's Product C, this
tier renders in the **HTML** (for the desk / QA) but is **excluded from the client-facing
PDF** — the renderer hides it under `@media print`, so the printed weekly ends at the
country sections. No machinery (report-ids, Qdrant/depth logs, coverage counts, the tag
legend, data-ops flags) reaches the printed deliverable; it all lives here.
- **Grounding-tag legend + editorial method** — the `FACT/DEPTH/VIEW/PRICING/SYN`
  definitions and the judging (Argument-Audit) principle.
- **Total macro calendar** — one chronological whole-universe calendar (releases + CB
  events, week ahead + a >1-week watchlist), Consensus + Prior where they exist, BQL vs
  TE labelled, each line framed by what it tests. **Note:** the two lanes do not
  reconcile — same release can land under a different `event_date` and a different
  `event_name` in each (see `docs/admin/calendar/bql_calendar.md` § Known limitation) —
  check both lanes rather than assuming one lane's silence means nothing released.
  *(This is reference material, retained in the appendix; the week-ahead the reader trades
  off lives in Tier-1 §10–11 and the per-country forward tables, which DO print.)*
- **Source register** — **Bank · Document · Date · report_id · IMDR folder** across all
  houses, plus an honest **"deeper reads not yet performed"** line, and the internal-use /
  not-investment-advice disclaimer. **All report-ids live here**, not on the reader pages.
- **Production / data-quality log** — Qdrant sweeps run, corpus size, deep-read vs
  noted-not-read counts, thin-DB flags, `fact_bond_yield` empty, and which IMDR econ
  pipelines posted a fresh in-window release (so a missed one is caught).
- **Coverage line** — total in-window reports · swept · deep-read · distinct cited ·
  page count.

---

## Grounding (weekly)
Same five layers as `spider.md` (`calendar.cb_events` · `econ.fact_indicator` ·
`research.fact_chunk` + Qdrant + Outlook · official-web fallback · market-prices), kept
separate and each item tagged. Weekly emphases:
- **Hunt the per-country sell-side WEEKLIES — a key input to each country read (not its
  spine).** The **spine is the topic set** (Tier 2, "topics that matter"); the sell-side
  weeklies are the richest *evidence* for what the banks are discussing and how they read
  each topic. Every country in the universe has at least one sell-side *weekly* flagship
  in the library; **find it and read it in full** — but it *informs the topics*, it does
  not dictate the section's shape, and it is never a licence to write up a view the note
  does not actually state.
  Hunt them **explicitly** by the vendor weekly series, not by hoping a title scan
  catches them. Search `research.dim_report.title` (+ `fact_chunk`), scoped to the
  country and window, for patterns like `%weekly%`, `%kickstart%`, `%local markets%`,
  `%macro watch%`, `%what's priced%`, `%research pack%`, `%data diary%`, `%strategy
  weekly%`, `%economics weekly%`. Known series to chase: JPM *Japan GPS* / *AU-NZ Weekly
  Prospects* / *Global Data Diary*; Barclays *Japan Rates Strategy* / *Global Economics
  Weekly*; DB *Asia Local Markets Weekly*; Citi *EM Strategy Weekly* / *The Point*;
  Nomura *Macro Strategy Weekly* / *Research Packs*; Goldman *Weekly Kickstart* (Korea /
  APAC) / *India Wraps*; MS *…Rates Weekly*; UBS *Japan Macro Watch*; StanC / HSBC Asia
  weeklies; ANZ / Westpac / NAB *Weekly* + *What's Priced In*. **If a country's weekly
  isn't found, that is a gap to flag — not a country to thin out.**
- **Country-wise exhaustive hunt — depth where there are live topics.** For **every
  country**, sweep the *entire* in-window corpus tagged to it — across **all houses and
  all note types** (weeklies, dailies, strategy notes, rates/FX notes, data flashes, econ
  comments, desk colour) — and **deep-read every substantive note in full**, not just the
  flagship. Coverage per country is measured by how much of its in-window flow was
  actually read, not by titles scanned. **But depth follows topics: a country with no live
  topic gets an honest short read, not padded drivers. Reading more is how you find the
  topics — never a reason to manufacture one.**
- **Deep-read the flagships in FULL** — the desk-read tables and the audits depend on
  actually mining the house notes, not their titles.
- **Qdrant semantic search is mandatory — but ground every hit on its date.** Run Qdrant
  (`playground/research/retrieve.py`) per country / per theme / per driver — a keyword
  title-scan alone misses globally- or thematically-titled flagships, so **do not skip
  it.** BUT **date-ground every semantic hit**: check each result's `publish_date`
  against the intended bucket (① prior week · ② this week · ③ next-week-relevant) and
  **discard or explicitly date-tag stale hits** — an out-of-window semantic match must
  never masquerade as this week's view.
- **Judge only what's grounded** — every `Solid`/`Weak` verdict rests on a cited number
  or a stated house logic, never tone. Where two sources disagree, show both and flag
  unreconciled; never silently pick one.
- **Push econ depth (the depth lever).** Go deeper on `econ.fact_indicator`: pull the
  **component series** behind each headline — CPI core / tradables / services / the
  subsidy-suppressed slice; labour participation, hours, job-offer ratios; PMI
  sub-indices; export / IP / capex breakdowns — and set each against its **3–6-month
  trajectory and forecast path**, not just the last print. The economic snapshot (bucket
  ①) and the estimate cross-cut (bucket ②) are **real decompositions**, not a headline
  restated. Where IMDR lacks a component, use the official-web fallback.
- **WoW sign-discipline (critical).** Every WoW move = `(this Friday's LAST tick) − (prior
  Friday's LAST tick)` — last tick per day, the two week-end sessions. NEVER from an
  intraday first-tick / open / low / high / mean to a close (an intraday low-to-close
  recovery is not a WoW move; mislabelling it flips the sign). Sanity-check every rates / FX
  sign against the two closes before writing on top. Where a series lags to mid-week, label
  the as-of and don't assert a full-week move you can't ground.

## Render & output — HTML → A4 → PDF (client PDF), audit appendix HTML-only
- MD → `data/research_summary/weekly/{YYYY}/{MM}/{DD}/spider-weekly-digest.md`
  (one whole-universe file; do NOT collide with Perry's `weekly_country_read_*`).
- **Render path (the deliverable is a PDF) — owned by Picasso.** Spider writes and
  locks the MD; hand it to Picasso (`/picasso <md>`) to render. See
  [`picasso_spec.md`](picasso_spec.md). The two-stage pipeline (run under the `imdr`
  env, Py3.11):
  1. `_build_spider_html.py <the MD>` → a self-contained, A4-print styled HTML (RVC
     design system: white sheet, Newsreader/Public Sans, hero tiles, §-numbered
     sections, left-stripe callout boxes, verdict pills, inline-SVG charts). The
     renderer parses the MD *conventions* below.
  2. `_html_to_pdf.py <the HTML> [pdf] --title "…"` → the A4 PDF via Chromium (print
     backgrounds, running footer + `Page X / Y`).
  (`_build_spider_docx.py` still exists for a quick review-only .docx, but the PDF is
  the real output.)
- **Client PDF — MANDATORY filename** `rvc-weekly-digest-{YYYYMMDD}.pdf` (dash-joined
  compact date), same dated folder. The MD + intermediate HTML keep the
  `spider-weekly-digest` stem; the **client-facing PDF does NOT** — do not ship
  `spider-weekly-digest.pdf`.
- **The print PDF ends at the country sections.** Tier-1 + Tier-2 print; the **Tier-3 audit
  appendix is HTML-only, hidden under `@media print`** (like the daily's Product C). The
  reader's forward calendar lives in Tier-1 §10–11 + the per-country forward tables (which
  print); the full reference calendar + source register + machinery stay in the appendix.
- **Navigation (the doc is long — ~40+ pages).** Generate a **clickable contents page** (the
  country roster + the Tier-1 sections, linked) and **PDF bookmarks / outline** for every
  Tier-1 section and every country chapter. A PM must be able to jump to a country, not
  scroll 40 pages.
- **Chart hygiene (from the daily's redesign review):**
  - **Never mix units on one axis** — a `%`-vs-`bp` or level-vs-delta pair buries the
    smaller series; split into two single-unit charts. Never mix m/m and y/y on one axis.
  - **Editorial axis bounds, not machine-generated** — round the bounds (`6.72 / −0.82` and
    `4,071.6 / −301.6` read as auto-junk); 0-based for all-positive, a zero baseline where
    there are negatives.
  - **The title must match exactly what is plotted** — no over-claim; the caption names the
    grounding source and the as-of. Visually check every chart before shipping.
- **MD conventions the renderer keys on** (author the MD to these):
  - `# KICKER` (line 1) = running header; the next `# Title` + a following `### deck` =
    masthead; a `**date · Compiled …**` line + a `**Sources** — …` line = the sub-line.
  - `## Universe hero stat band` followed by a `| Number | What it is | Memory |` table →
    dashboard tiles. Per-country, a `**Hero line:** a **x** · b **y** …` line → stat strip.
  - `# TIER 2 — …` / `# TIER 3 — …` = dark tier bands (page-break before). `## COUNTRY —
    subtitle` under Tier 2 = a country chapter head; `### Driver N — …` = driver subhead.
  - **Callout boxes** = a `> **TAG** — body` blockquote. Colour is auto by TAG: STOP* →
    red, *FLAG/PENDING/INTEGRITY/INSTRUMENT* → amber, PRICING/CARRY/BOOK-LEVEL/COHERENCE →
    blue, else green. Use the kit's box names.
  - **Verdict pills** = `Solid` / `Weak` / `Stale` / `Live` render as coloured pills
    (leading a table cell, or as `**Solid**`).
  - **Charts** = a fenced ```` ```spiderchart ```` block of JSON
    `{"type":"bar"|"grouped"|"line","title","caption","series":[{"name","color","points":[["label",val],…]}]}` →
    inline SVG. A bare `[FIG. KEY — caption]` with no data renders as a dashed
    "chart pending" frame — always prefer emitting the data block so the chart is real.

## Non-negotiables (weekly)
- **One doc, all countries, driver-organised, judging** — the three defining choices
  above are the point of this edition; do not revert them toward the daily.
- **The three-bucket temporal spine** (① week that was · ② this week, heaviest · ③ week
  ahead) runs through both tiers, at the same rigour. It is **additive — nothing already
  in the structure is removed to make room for it.**
- Coverage floor: every country a real section; depth scales, none dropped.
- **Topics = "what has everyone said" → 3–10 per country, each shows up.** Build each
  country's topic set from the full cross-bank sweep on that country (the union of what
  every house said, plus what's structurally live); dive into each properly with the
  fattened consensus-vs-divergence table; and **guarantee every surfaced topic appears** in
  the output (driver, or a named open-question-to-watch). None silently dropped, none
  invented.
- **Table & language at the daily's bar.** Tables carry the argument *in the cell* —
  house-specific numbers, `Assumption → Falsifier`, and a `Resolver / when` column, not
  labels; hero tiles decompose the *why*. Prose leads with news-vs-price (did price agree?),
  attributes every divergence or flags it `[RV — …]`, tags `FACT/DEPTH/VIEW/PRICING/SYN`,
  carries a number+driver per clause, bans literary metaphor, uses explicit dates, and
  respects the repetition budget (each fact once, cross-referenced). See "Table & language
  standards".
- **Tier 1 leads with the edge.** The live-debates PM dashboard, the "what moved — did price
  agree?" read, and the Street trade map come first; the data recap (matrix, desk-by-desk,
  themes) is support underneath. The desk-by-desk map is *evidence*, demoted — not the top.
- **One consolidated Street trade map, split by status** (New / Revalidated / Closed /
  No-entry / Macro-view-only), one trade per row with level·entry·target·stop·Why·Risk·
  falsifier — feeding, not replacing, the per-country boards. Titled "Street trade map",
  never "where the book tilts".
- **Audit appendix is HTML-only.** The client PDF ends at the country sections; Tier-3
  (tag legend · full reference calendar · source register · report-ids · coverage/machinery)
  renders in the HTML but is hidden under `@media print`. No report-ids or machinery on the
  printed reader pages. Client PDF filename `rvc-weekly-digest-{YYYYMMDD}.pdf`; ship a
  clickable contents page + PDF bookmarks (the doc is 40+ pages). Charts obey the hygiene
  rules (no mixed units, editorial axis bounds, title matches plot).
- **Calendars are chronological.** The Tier-3 total macro calendar, the Tier-1 §10
  "This week" and §11 "The week ahead" grids, and every per-country "This week & next
  week" board MUST be sorted ascending by date (out-of-window / soft rows last; range
  cells sort on their start date). Before locking, run
  `python scripts/research/check_calendar_sort.py <the MD>` and fix any flag. See
  `spider.md` hard rule 5 (applies to daily & weekly; auto-run as a PostToolUse hook).
- **Session scope — verify mark times before attributing any move.** Before locking, run
  `python scripts/research/check_session_scope.py --prev <prior> --curr <reported> --event <UTC>`
  for each attribution the week rests on. Curve marks in `rates.fact_observation` are
  stamped anywhere from ~11:00 to 23:00 UTC depending on the market, so **a same-calendar-day
  move is not a same-session move** — and a WoW delta inherits the error at both ends. Never
  attribute a move to a release the curve was marked before; never present curves with
  materially different mark times as a like-for-like reaction matrix without saying so. Act
  on the checker's flags: `MISMATCH` = the two days' marks are too far apart for the
  comparison to hold; `NO PAIRED MARK` = the market is unmarkable and belongs in the
  unmarkable list, not the reaction table. The same discipline applies to FX (is the latest
  row a real session or one carried tick?) and equities (Asian closes capture the *prior* US
  session). See `spider.md` hard rule 0b.
- **Staleness is MEASURED at every cut, never carried forward.** Before declaring any feed
  stale — or dropping a section for want of data — run
  `python scripts/research/check_feed_freshness.py --as-of <edition date>` (exit 0 = every
  family within tolerance) and quote its dates. A staleness claim from a prior edition is
  **not evidence**: re-measure it. Never write "still not loaded", "Nth consecutive edition",
  or a session count this run did not produce. Judge against the source's **publication lag**,
  not the cut date (FRED H.15 lands T+1, so the prior session's observation is current), and
  never generalise a **weekly** series' cadence to a daily/weekly block
  (`FRED.SENTIMENT.NFCI_CREDIT.US` is a Chicago Fed weekly, unrelated to credit OAS). See
  `spider.md` hard rule 6.
- **No-bullshit language.** Write plainly and directly. State what happened, what's
  priced, what the assumption is, and where it breaks — in the fewest honest words. No
  filler, no hedging-for-cover, no throat-clearing, no consultant-speak ("navigating
  headwinds", "cautiously optimistic", "remains to be seen"), no restating the question.
  Short declarative sentences, active voice, numbers over adjectives. If something is
  unknown, say "unknown" and why; if a call is weak, say `Weak`. Conviction comes from
  the evidence, not the volume.
- **Factual > headline. No force-fitting. No opinion beyond your understanding.** The
  masthead and every country thesis are **factual and descriptive**, not flashy — report
  what happened, don't coin a slogan. Do **not force-fit** the week into a tidy narrative
  or a false through-line; if the stories are unrelated, present them as unrelated. The
  Argument Audit judges **only within what the evidence supports** — where the data is
  thin or two-sided, the verdict is "unresolved / unknown", not a manufactured `Solid`.
  Understate before you over-reach; a smaller, true claim beats a bigger, forced one.
- Content over citation; every line understandable on its own; every table row explained
  in the prose; no cherry-picked pull-quotes; number-first, with the memory of what each
  number *was*.
- **Topics in, fabrication out.** Coverage is driven by relevant topics + what the banks
  discuss — never by a template that must be filled. A citation must contain the claim
  attached to it (verify — don't decorate); a temporal / before-after claim ("a month ago
  the market priced cuts") needs a source that actually spans the period, not a current
  snapshot; and no country gets a view, trade, "bias", or terminal call the corpus does
  not support. Where there is nothing, say so — an honest short read beats an invented one.
- Every **country trade board** carries the sell-side trades **with a Why and a Risk**
  column (see Tier 2) — the rationale and what-breaks-it are not optional.
- This is the WEEKLY spec. It **deliberately adopts the daily's craft** — edge-first Tier-1
  ordering, argument-in-the-cell tables, the grounding-tag legend, and the HTML-only audit
  appendix. But it **keeps its own identity and must not collapse into the daily**: the
  weekly *judges* (Argument Audit), goes per-country driver-deep for every market, and runs
  the three-bucket spine. Do **not** port the daily's Deltas-since lead, its per-country
  A/B/C/D template, its quiet-market monitor collapse, or its neutral-no-judge stance.
