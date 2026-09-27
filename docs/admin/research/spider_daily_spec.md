# Spider — DAILY digest spec (self-contained)

The **DAILY** edition of Spider, from a cross-asset macro PM's chair. It is **one run
that produces a layered set of three products from the same underlying work** — not one
37-page sequential read. The research depth is an asset; the *delivery* is layered so
each reader gets the right altitude.

| Product | Pages | Reader | Stops when |
|---|---|---|---|
| **A · PM morning note** | 1–2 | The PM, time-constrained | This is the daily reading product — a reader can stop after page 2 |
| **B · Selective deep-dive** | 3–N | Analyst drill-down | Optional; only the markets that moved get a block |
| **C · Audit appendix** | last | Internal QA | Grounding + source register + all production machinery |

The organising principle: **structure follows the importance of the content, not a
template.** The report's edge is the *disagreement* and the *news-vs-price* read — those
lead. Data recap, per-country completeness, and sourcing machinery are support, not the
headline.

Shared fundamentals — persona, coverage universe (**Asia + G10, ~17 markets** — all of
Asia-Pacific incl. China/Korea/Taiwan (Vietnam is OUT of scope — dropped 2026-07-27) + the
core G10/DM US·Eurozone·UK·Canada·Japan·Australia·NZ; the peripheral CH/NO/SE are out of
scope), asset classes, grounding
layers, hard rules — live in `spider.md` and apply here. This doc is the daily's
*structure*.

**Grounding-tag legend (defined in the appendix, tagged throughout):**
`FACT` = official print / decision (`calendar.cb_events` **or** IMDR's own
`econ.fact_indicator`) · `DEPTH` = component series (`econ.fact_indicator`) · `VIEW` =
attributed sell-side interpretation/forecast (`research.fact_chunk` + Qdrant) · `PRICING`
= observed market move / implied path · `SYN` = the desk's neutral organisation of the
evidence (not a recommendation).

**Editorial principle — be explicit about the two kinds of neutrality:**
- **Neutral on execution** — never rate a trade good/bad, never say whether the reader
  *should* put it on. That is the PM's call. Surface idea + assumption + falsifier.
- **Opinionated on relevance and causal interpretation** — you *do* judge what matters
  today and how the pieces connect ("soft PPI confirms the CPI signal", "the gravity
  shifted to China"). That is the desk's job and it is honest to own it.
Do not claim to be "low-opinion / no-judge" and then write interpretive prose — state the
principle above instead.

---

## PRODUCT A — PM morning note (pages 1–2)

The complete time-constrained briefing. A busy PM should learn more from *"what are the
market's live debates"* than from the same print restated five ways. **No production
machinery on these pages** (no Qdrant / dim_report / report-ids / "thin depth" /
"fact_bond_yield EMPTY" / missing-BBG) — those live in the appendix. The only data note is
a single stamp (below).

### Masthead
- Header rule: `RV CAPITAL · RATES & FX DESK · DAILY MACRO PULSE` (left) · `{DD MONTH YYYY}
  · {HH:MM} {TZ} CUT` (right). **The cutoff is mandatory and explicit** — the reader must
  know the as-of time.
- Kicker `MORNING IN 90 SECONDS`, then a **short, specific thesis title** (one line — the
  day's single argument, naming the actual driver, not a vague mood), then a one-line deck.
- **Explicit dates, never relative day-names.** Write "June PPI (released 16 Jul)" not
  "Tuesday's PPI" — a reader opening this on any later day must not have to reconstruct which
  Tuesday. Reference the release month for data (June PPI, June CPI) and the calendar date for
  events. "Yesterday/Tuesday/last week" are banned in the body.

### Contents index (page 1, above the Bottom line)

**Generated from the document's own headings — never hand-maintained**, so it cannot drift from
the edition. It does two jobs:

- **Navigation.** Every section and country block with a **page number**, grouped: summary
  sections, deep-dive country blocks, quiet-market monitor, trade map, relative-value. Page
  numbers come from a **two-pass render** — print, map each heading to its page, inject, print
  again, and repeat until a print produces the numbers it was printed with. **Fail loudly rather
  than ship a wrong number**: a heading-count mismatch, an order desync or a failure to converge
  must exit non-zero, never guess.
- **Coverage.** One line stating **how much of the roster this edition actually covers** — the
  market count, how many got a full block and how many a monitor line. **Count markets, not
  index entries**: a block heading may cover several markets ("Greater China" is CN + HK;
  "ASEAN and India" is five). Reconcile against the standing 17-market roster, and where blocks
  plus monitor do not sum to 17, **say so explicitly and name the missing markets**. This line
  exists to surface a coverage gap, so it must never quietly print the smaller number.
  **Tie-break:** a market that has its own quiet-monitor row is credited to the **monitor**, not
  to the group block that contains it — so an ASEAN-and-India block scores 5, not 6, when the
  Philippines is monitored separately. A market may be counted **once**; a market appearing in
  both a block and the monitor, or in two blocks, is an error and must fail loudly, not be
  silently deduplicated.

The index sits on page 1 and may take the page. **The trade matrix may start on page 2** — do not
compress or demote the index to keep the matrix on page 1.

**PDF bookmarks** accompany it: every section and country heading as a nested, clickable outline
entry (H1 → H2 → H3), with verbatim titles. The internal appendix appears in **neither** the index
nor the bookmarks of the print PDF.

### Bottom line (a boxed callout)
**Bullets, not a paragraph — 3–5 of them.** This is the single most-read element and it must
be scannable in one pass. The **first bullet states the working regime**; each remaining bullet
states **one** cleaner relative-value question that regime raises. One sentence per bullet, each
self-contained and leading with its subject (the market, country or driver), never with a
connective. No bullet may run past two lines at A4 width. Verify the bullets survive the render
into the boxed callout in **both** the HTML and the PDF — a callout that collapses to a single
run-on line has failed this section.

### Trade matrix (immediately below the Bottom line, above the hero band)

The summary's second element, and for most readers the reason they opened the file. **Five
columns, one row per trade, 8–12 rows:**

| Trade | Levels | Why | Street | Since | Kills it |

- **Trade** — direction + instrument in bold, then `House · status · conviction delta · sug
  {date}` on a second line (`HSBC · NEW · sug 18 Sep`, `Nomura · ON · conv 3→4 · sug 2 Sep`).
  The trade leads; the house is a subtitle. This collapses the old New / Revalidated / Closed
  split into one table. **`sug` is the date the idea was FIRST suggested**, not the date it was
  last reaffirmed — that is the honest scorecard. Where a house has re-struck the trade at a
  new level or conviction, append the re-strike in parentheses: `sug 2 Sep (re-struck 18 Sep)`.
- **Levels** — numbers only: `entry → target`, stop, spot/mark, and carry as a sign
  (`carry +` / `carry −` / `carry flat`). Where no stop was published, write
  **`no stop published`** — that absence is itself a judgement on the trade.
- **Why** — the mechanism, **≤ 20 words**. Not the narrative.
- **Street** — **≤ 12 words.** Count with, count against, and **name the house on the other
  side** (`2 with · 1 against — Nomura's long TWD/KRW is the opposite KRW leg`), or
  **`alone`**. This column is the one thing a multi-house corpus can say that no single bank's
  note can. Do not omit it; if the corpus is genuinely silent, write `no other house in window`.
- **Since** — the mark, **from IMDR, as of the edition cut**. Two lines: `{level at suggestion}
  → {level now}`, then `{move} · onside|offside · {days held}`. **The move is signed to the
  trade's direction, never raw** — a raw percentage on a short reads backwards and will be
  misread at speed. Run it from the **first-suggested** date, not the re-strike.
- **Kills it** — falsifier **and** the dated catalyst that resolves it, **≤ 15 words**.

**Sort contested-first** — by disagreement in the Street column, not by house or asset class.
Where the street splits is the fastest insight on the page; a trade eight houses agree on is
already in the price.

**Structures that do not fit a 20-word Why** (a hybrid digital, a conditional spread — where the
structure *is* the argument) get **one italic continuation line directly under their row**, never
a bloated cell.

**Closed / take-profit trades drop out of the matrix** into a compact three-column strip beneath
it — `Trade · Result · What it teaches`. Scoring belongs in the record, but a closed trade is
not actionable and must not compete with live ones for the top of the page.

**This matrix is a summary layer.** The per-country detail, full rationale, horizon and sizing
stay in the "Street trade map" in Product B — which carries the same mark, folded into its
existing levels column rather than as a seventh column (seven will not hold at A4 portrait).

#### Marking rules (the `Since` column)

**Mark from IMDR only. Never mark from a sell-side run, and never estimate.**

- **Markable:** FX outrights and **crosses** (triangulate off the USD legs — SGD/KRW from
  USD/SGD and USD/KRW — hour-matched on both dates, vendor 1 / `frequency_id = 4`); swap and
  OIS par-curve levels, spreads and flies — **except on a tenor `check_curve_tenors.py` calls
  SYNTHETIC**, which is the 10Y plus a construction constant and marks nothing. Print
  `not markable · synthetic tenor ({curve} {tenor} is the 10Y plus a constant)`. See
  § Grounding → *RATES: not every tenor on a curve is a market quote*; equity indices.
- **Not markable, and it must say so:** option structures, digitals and ERKOs (a level is not a
  price — these need a vol surface); **any cash-bond leg**. `rates.fact_bond_yield` is **not
  empty** — 278,921 rows across 45 curves — but it holds **one tenor only (10Y generic/CMT)**
  and stops at **31 Aug 2026**, so it cannot mark a 5s20s, a 2s10s or anything current. Also
  unmarkable: **meeting-dated OIS** (IMDR carries par tenors and standard forwards, not
  meeting-date strips — deriving one from the par curve is bootstrapping, which these rules
  bar); anything with no IMDR instrument. Print **`not markable · {reason}`** — never a blank
  cell, never a guess, never a sell-side mark substituted in.
- Where the suggestion pre-dates IMDR coverage of that instrument, print
  `not markable · no history at suggestion`.
- The mark is computed at the **edition cut**, and the cut time is already stamped on the
  masthead — do not restate it per row.
- **Always write the literal token `onside` / `offside` / `not markable`.** The renderer tints
  the `Since` cell off that token (green `#1f6b4f`, red `#a1382f`, grey `#6b6658`) and **never
  off the sign of the number** — a short that has fallen is onside while showing a minus. Drop
  the token and the row renders uncoloured.
- Red/green asserts a **verdict**, so it appears **only** in the `Since` column, the same mark
  in the Product B trade map, and the closed-trade `Result` cell. **Never** tint reaction
  panels, curve-move tables, hero tiles or drawdown columns — a −4bp move is not "good", and
  colouring it would assert something false.

### Hero band — 4 tiles (precise, decompositional captions)
Exactly **four** big number tiles (the day's decisive prints). The caption says **WHY the
number is what it is** — the categories/components behind it (e.g. "energy −6.4%, core goods
flat, OER cooling → core-PCE ~0.18%") plus the memory (survey/prior). **Numbers and drivers,
never a literary metaphor** — ban "the second shoe", "the gravity shifts", "the tide", etc.
If a category decomposition isn't at hand, say what you do know, not a mood. When an IMDR econ
pipeline has just loaded a release, that print is a strong tile candidate.

**Hard cap: 30 words per tile caption.** The tile carries the print, the surprise against
survey/prior, and the single driver — nothing else. Board splits, quotes, revisions, forecast
changes and second-order read-through belong in the country block, not here. A caption that
runs past 30 words has failed this section; cut it, do not shrink the type.

### What moved — and did price agree (ONE place; kills the repetition)
This **consolidates** what used to be three overlapping sections (a "five things" list, a
"news-vs-price" box grid, and the tiles' prose). Cover the day's **4–6 decisive developments
ONCE each** — do not restate the same event in a tile caption *and* a bullet *and* a box. For
each item, together in one place:
- **The development, decomposed** — the number *and the driver behind it* (which categories
  moved core/headline), not just the headline print.
- **How price reacted**, and **did it agree with the news?** If the market moved as the
  narrative implies, one clause. If it did **not** (credit missed but the currency ~flat; a
  front end sold off in a global rally), that divergence is the high-value content — lead with it.
- **Every divergence is attributed or flagged RV.** When a market moves against the tide, name
  the cause — a data print, a speech / CB-speak, a fiscal/policy announcement. If there is **no
  identifiable catalyst**, say so and flag it as a **relative-value divergence** (an unexplained
  move *is* the trade). Never leave "X was the exception" hanging.
- **One thread per item.** Never staple unrelated threads together (a JGB long-end read does
  not share a line with "and the BoK decides today and US retail sales are due").

### Market reaction — session-scoped, then go the next mile
Separate panels by capture session (never one false like-for-like matrix): DM 2y = US EOD
(post-catalyst); Asia 2y = the earlier Asian close (captures the **prior** US session). But the
session label is table-stakes — **the value is the inference:**
- **No methodology/caveat intro on the reader page.** Do NOT open the section with "session-scoped
  — never a like-for-like matrix… equities stale… ladders in the appendix" — that is machinery.
  The cutoff lives in each **panel label** (`FX · {date} close`, `DM 2Y · post-{catalyst} EOD`,
  `Asia 2Y · earlier Asian close`); the session/stale-data caveats live in the **appendix**. Go
  straight to the panels + the inference below.
- **State the cross-session beta and the implied open.** Given the overnight US-session move
  (e.g. US 2y −X bp after the print) and each Asian front end's historical beta to the US 2y,
  say where Asian rates should **open today** and whether that catch-up is already priced.
  "Asian rates haven't caught today's move" is only useful if you then quantify the catch-up.
- Top movers on the note; the **full DoD ladders live in the appendix**.
- **Stale series** (equities/VIX/commodities a session behind) are **OMITTED** here, not footnoted.
- Attribute a move only to the window it captures (a Canada 2y fall is *PPI + BoC*, not clean BoC).

### PM dashboard — the live debates (the report's real edge)
A table of the day's **unresolved disagreements**, up front, in one place — not dispersed
across cover/deltas/themes/country blocks. Columns:
**Debate · Centre of gravity · Differentiated view · Resolver (what settles it, and when)**.
Aim for the 3–5 debates a PM should carry into the day (e.g. US core-PCE 0.17–0.19% vs JPM
0.20%; BoC-on-hold houses vs market pricing ~50bp of hikes; Citi July-China-easing vs JPM
"no urgency"; the ANZ/UBS/HSBC NZ-path split).

### Three priority expressions (Street trade map — condensed)
The 2–4 best *fresh* expressions distilled from the register: **# · Theme · Why it's live ·
Falsifier**. This is the executive view of the trade book; the full register is in Product B.

### Today's catalysts · What breaks the regime
Two short boxes: the day's decision-grade events (with expectations), and the specific,
measurable conditions that would break the working regime.

### Data stamp (one line, foot of the note)
`Data through {date}, {HH:MM} {TZ} · {N} reports processed · {k} stale-data exclusions`.
That is the *only* production metadata allowed on the reader-facing pages.

---

## PRODUCT B — Selective deep-dive (pages 3–N)

Optional drill-down for the analyst. **Structure follows importance, not a fixed template.**

**Charts sit here, before the deep-dive.** A "THE DAY IN CHARTS" band renders between the PM
note and the first deep-dive block — the day's grounded charts (not buried at the tail). Each is a
single-unit `spiderchart` fenced JSON block (the builder renders it to inline SVG); **never mix
units or day-vs-WoW within one chart** (no twin axis; a `%`-vs-`bp` or level-vs-delta mix buries
the smaller series — split it). Choose editorial axis bounds — the builder gives a clean 0-based
axis for all-positive charts and a zero baseline for charts with negatives. The standing chart set
(surface what is grounded; label the as-of on any series that lags the cut):
- **Rates / yields** — a front-to-belly move **across tenors including 5y** (`2y / 5y / 10y`, as a
  grouped single-unit bp chart), for the key markets (US + the big movers); day or WoW move,
  whichever is the cleaner grounded story. Grounded from the swap/OIS par curves.
- **FX** — the day's currency moves (% vs USD, day or WoW), one consistent sign convention.
- **Equities** — index moves (day or WoW %). If the equities tape is a session stale at the cut,
  chart the **last grounded session and label the as-of date** — never fabricate a same-day move;
  omit any series whose move looks distorted rather than assert it. **Label the x-axis with short
  index codes/tickers, not full index names** (SPX/NDX/RTY/N225/TOPIX/TAIEX/TW-MSCI/SX5E/CAC/ASX/
  NIFTY/SG-MSCI/HSI/HSCEI/HSTECH, ≤6 chars) — at ~12–15 bars the full names collide and overlap.
  The caption spells out the full names + moves, so the short codes stay unambiguous to the reader.
  (Rates/FX/commodities/credit labels are already short — no change.)
- **Commodities** — oil plus whatever else is material (levels or move). If `commodities.fact_spot`
  lags, label the as-of; a Monday/overnight move known only from sell-side stays **labelled VIEW**,
  not asserted as a FACT-layer print.
- **Credit** — spread **levels** (bp) *and* a **companion WoW-change (bp) chart** beside/below it
  (levels and deltas are the same unit but wildly different magnitudes, so a grouped bar buries the
  deltas — use two single-unit charts). Ground the WoW delta as `level − value ~5 sessions prior`
  from the OAS series; do not eyeball, and drop any bucket whose delta can't be grounded.
- A day's decisive **print decomposition** (e.g. CPI/durables components) where one exists.

**No methodology narration — ever.** Do NOT explain the report's own construction to the reader:
lines like "movers get a block; quiet markets get a monitor row… surfaced selectively, not
dumped", "one row each for the non-movers, thin-coverage carries a flag", "split by status,
multi-leg bundles split, regime views tagged macro-view-only" are internal build rules — the
reader asks *"why are we saying this?"*. The sections simply **present their content**; the
status sub-headers and the table columns already convey the structure. The **Street trade map
carries no subtitle disclaimer** — the section header and the status sub-headers are enough. The
single "not RV Capital's book" caveat lives once, on the Product-A priority-expressions line
(*"what the Street is floating — not RV Capital's book"*), and nowhere else.

### Selective coverage — this SUPERSEDES the old "raised-floor / every country a full block" rule
Keep generating the full clustered research (see Grounding & depth below) — it is the *input*.
But **surface it selectively**:
- Countries with **material developments** get a real deep-dive block (region-grouped where it
  reads better — e.g. "North America: US + Canada", "China + Japan"). On a typical day that is
  ~4–6 markets (07/16: US, Canada, China, Japan, NZ, Australia).
- A market with a lighter but real analytical point gets a **short note**, not a padded block.
- Genuinely **quiet markets go in a single "quiet-market monitor" table** (one row each: level /
  DoD / next event / one-line read) — NOT four half-empty A/B/C/D blocks. "No independent
  cluster / no differentiated view / carried / quiet in-window" filler is a template-driven
  failure; do not manufacture it.
- **Korea is a full roster member surfaced selectively** — a deep-dive block on a BoK/semis day,
  the quiet monitor when quiet. It is NOT "context-only".
- **A country with a fresh IMDR econ release always earns at least a short note** — a print we
  loaded ourselves must not be relegated to the quiet monitor (see "IMDR econ releases").

### Deep-dive block shape (default spine, disagreement-centric)

Lead with the *why* and the *debate*, not a data recap. The spine below is the **default**, not a
template — depart from it where a country genuinely needs a different shape, but the **lens and
the decider are mandatory in every block**:

1. **Decision lens — one line, directly under the heading. MANDATORY.** Name the rates/FX
   decision the block informs, and nothing else: *"Informs: whether to hold KRW receivers through
   Chuseok, and whether short-KRW expressions survive the exporter bid."* The heading names the
   observation; the lens names what it is **for**. Everything in the block sits under it. This is
   not a recommendation — Spider stays neutral on execution — it is the question the block
   answers.
2. **What changed** — a short prose lead, hour-matched marks, no data recap.
3. **Why, attributed** — the mechanism and who says it.
4. **House divergence table**, where a real disagreement exists (e.g.
   `House · Core-PCE tracking · Interpretation` — the core-PCE cluster appears **once**, here,
   not eleven times). Immediately beneath it, **one bolded line quantifying the spread and naming
   what resolves it**: *"Goldman 1,350 against Barclays 1,430 — 5.9% apart on a 12-month view;
   resolves on whether exporter conversion survives Chuseok."* **Never average two houses** —
   averaging destroys the information the divergence carries. Do not leave the reader to compute
   the spread, and do not bury it paragraphs later.
5. **IMDR's own data** — the flow/money-market/pipeline series that the sell-side does not have.
6. **Decider — one line closing the block. MANDATORY.** The dated event that resolves the
   block's open question, and what it would change: *"Decider: 28 September, whether exporter
   conversion resumes after the holiday. Goldman's 1,350 floor breaks if it does not."* This is
   the country-block analogue of the matrix's `Kills it`, and it is what makes a block
   re-readable a week later.

**Primary over digest — tag only where a primary exists.** Where a central bank has actually
spoken in the window, say whether the statement/minutes/speech was read, or only a house's
paraphrase of it: `— BoK statement read` vs `— per Goldman's read, primary not checked`. A
sell-side characterisation of a central bank is a claim, not a fact, and has repeatedly
contradicted the primary text. **Do not** tag blocks where no primary was published — a universal
tag is noise.

**Coverage ceiling — name the houses, in the body.** Where the corpus is thin or a house is
absent, say so in the block: *"No UBS, Deutsche Bank or Morgan Stanley view on Korea surfaced in
the window."* That is editorial information about how complete the section is, and it belongs on
the reader pages. **Phrase it as what surfaced, not as what a house published** — the cluster
register evidences the first and not the second, and a house absent from one topic may be all
over another in the same edition. Never assert a hard negative about a house's output.
**File paths, parser states, report-ids and ingest failures are machinery** and stay in the
Product C appendix with the hazard register — never in the body.

For a **marquee Americas event** (US CPI/PCE/NFP/retail sales, FOMC/Fed-speaker cluster, BoC
decision/MPR), add a compact **within-window official-voice-vs-sell-side timeline** (release +
policymaker comms as FACT/official in one column; the desk read as VIEW in the other) — strictly
inside the edition's timeframe.

### Street trade map — the trade register, split by STATUS
One table is not enough because it mixes different things. Split by status, **one trade per row**:

| Status | Meaning |
|---|---|
| **New expression** | Introduced because of today's information |
| **Revalidated** | A carried trade strengthened/weakened by today's news |
| **Closed / take-profit** | The source has exited |
| **No entry / cancelled** | A planned trade never initiated |
| **Macro view only** | A forecast without a specified instrument (e.g. "Citi expects a PBoC cut") |

For every *genuine* trade row: **current level · entry/target/stop · horizon · catalyst date ·
carry/roll · a specific measurable falsifier**. Multi-leg bundles are split into their legs; a
regime view ("goldilocks summer") is `Macro view only` until an instrument is specified.
Title it **"Street trade map"** (aggregated sell-side positioning) — never "where the book
tilts", which reads as RV Capital's own positions — and, per above, **no subtitle line** under
that title.

Every trade row here carries the **suggestion date and the IMDR mark**, on the same rules as the
summary matrix above: `sug {date}` in the Source cell, and `{level at suggestion} → {level now}
· {move} · onside|offside` appended to the level/entry/target/stop cell. Folded into the
existing columns — this table does **not** gain a seventh. Unmarkable legs print
`not markable · {reason}`.

### Regional relative-value
Where the cleaner expression is a *pair* (AU vs NZ rather than broad short-USD), say so — this
is often the highest-value idea and should not be buried in two separate country blocks.

---

## PRODUCT C — Audit appendix (INTERNAL — HTML only, NOT in the production PDF)

Everything that proves the note without interrupting it. Preserves auditability; carries all
the machinery the reader pages exclude.

**This is internal-use only.** The audit appendix renders in the **HTML** (for the desk / QA)
but is **excluded from the client-facing PDF** (the renderer hides it under `@media print`). The
production PDF ends at the deep-dive / trade map. No internal comms — source registers, report-ids,
Qdrant/depth logs, data-ops/healthcheck warnings ("incomplete tenor coverage… escalate…
imdr-data-ops… SLA T+N BD"), and the like — ever reach the printed deliverable; they live here,
in the HTML, only.

- **Editorial method** — the FACT/VIEW/PRICING/SYN definitions and the neutral-on-execution /
  opinionated-on-relevance principle.
- **Timing & data caveats** — the exact cutoffs, session mismatches, stale-data exclusions,
  swap/OIS-not-cash, Korea/roster notes.
- **Official events used** — `Cluster · Verified inputs`, split by source lane so IMDR-loaded
  prints are visible: `econ.fact_indicator` (IMDR's own pipelines) vs `cb_events` (TE/BQL
  calendar). This is where the FACT layer is auditable.
- **Sell-side source register** — `Cluster · Report IDs`. **All report-ids live here**, not on
  the reader pages.
- **Production / data-quality log** — Qdrant queries run, corpus size, deep-read vs
  noted-not-read counts, thin-DB-depth flags, missing-BBG, and **which IMDR econ pipelines
  posted a fresh in-window release** (so a missed one is caught).
- **Data hazard register — MANDATORY, every edition.** Walk the standing hazard list below and
  record, for each one, whether it **touched this edition's dataset** and **how it was handled**.
  Write `checked — did not apply` where it did not: an absent line is indistinguishable from an
  unchecked one, and the point of the register is that each edition carries its own record of
  what went wrong with that day's data. Add any new hazard found during the run, and say so.

  Standing list (re-verify each item's status — several have changed and will change again):
  1. `econ.fact_indicator` carries forecasts out to 2029 — always
     `obs_date <= CAST(GETDATE() AS date)`.
  2. Bloomberg quarterly CPI forward-fills (NZ, AU) set `release_date` to the ingest date, so
     `obs_date <= release_date` does **not** remove them.
  3. Bloomberg daily curves (INR 54, CNY 43) carry Saturday/Sunday rows holding stale values.
  4. **Frozen series** — flag any run of ≥ 5 identical values. Known: Indonesia JIBOR 10Y, the
     vendor-4 `*:10` lane (CAD 2Y sat at 3.3090 across six consecutive marks), AUD 6M BBSW.
  5. `calendar.cb_events` survey / actual / prior are **varchar** — cast before arithmetic.
  6. **Oil.** `commodities.fact_spot` has held no Brent since 29 Jul 2026. The EIA lane
     `EIA.ENERGY.BRENT_SPOT.US` stalled at 15 Sep on **USD130.80**, roughly 34 dollars above
     where desks mark — an unconfirmed print, not a usable level. Never forward-fill it.
  7. **Vendor lanes are not interchangeable.** Filter on `(curve_id, vendor_id, frequency_id)`.
     Vendor 1 / frequency 4 is on-the-hour; vendor 4 / frequency 2 is stamped `*:10` and carries
     frozen repeats. `check_session_scope.py` does **not** filter by vendor, so its mark times
     will disagree with a vendor-1 read.
  8. **FX.** The batch writes a 00:00 UTC row carrying the prior 23:00Z close and has
     double-written the same value intraday. Hour-match both dates; never use the back-stamped
     daily lane; sanity-bracket for bad ticks (a USDIDR 17,477.9 print sat between 17,750.0 and
     17,700.5).
  9. `rates.fact_bond_yield` is **not empty** — 278,921 rows, 45 curves — but holds **10Y
     generic only** and stops **31 Aug 2026**. It cannot mark a 5s20s, a 2s10s, or anything
     current.
  10. `research.dim_report.pdf_text` and `summary` have been NULL since ~10 Aug 2026 (parser
      outage) — retrieve through `research.fact_chunk`.
  11. **Qdrant drift.** A bulk-upsert bug aborted large reports *after* the SQL commit, so
      `dim_report` / `fact_chunk` can look complete while Qdrant holds nothing for that report.
      A thin semantic sweep is a drift symptom, not proof of a quiet corpus — run the structured
      SQL title inventory first and cross-check.
  12. `event_date` is a **vendor day-bucket**, not the release date (TE buckets by UTC, BQL by
      SGT). Truth is `event_datetime` + `dim_country.timezone`.
  13. **Equity index ingest lag** — FTSE 100 runs ~1–2 days behind. Check `created_at`, not
      `obs_date`, before calling anything a gap.
  14. The `imdr-db` MCP query tool rejects `;`, `--`, `sp_`, `xp_` — single statement, no
      comments.
  15. Government-shutdown gap: Oct 2025 US CPI and unemployment are missing.
  16. **Corpus outages.** JPMorgan published nothing 15–17 Sep 2026 and it was never
      backfilled; `short_uuid()` collides on JPM filenames, dropping same-title same-date
      re-issues. Report the day's JPM volume.
  17. **A scheduled release neither lane carries an actual for.** TE and BQL both hold the
      event with a null actual. Name every release sourced from a sell-side write-up instead,
      and prefer a figure several houses agree on to a single-house number.
  18. **Lanes carrying incompatible definitions**, not merely different dates (UK PSNB: TE
      −18.3 against BQL survey 15.5, prior 1.8, no actual). Show both, flag unreconciled,
      prefer neither without independent corroboration.
  19. **Exchange-holiday marks read as zero change.** A shut market's curve prints 0.0 at every
      tenor and its last equity close is days old. Label it a holiday carry in the row itself —
      never read it as an unchanged market.
  20. **The last hourly FX row of the day (21:00 UTC) is the one most likely to be a bad tick**
      in thin Asian crosses — USD/INR printed 94.4684 against 95.9980 an hour earlier, a 1.6%
      jump with no corroboration in any other pair, and USD/TWD 31.6329 against 31.8159 on the
      same row. Strike the FX panel at **15:00 UTC** and bracket every cross against its
      neighbours before use.
- **Reader rule** — a one-box reminder: pages 1–2 are the complete briefing; 3–N are selective
  drill-down; this page preserves auditability without production metadata interrupting the read.

---

## MANDATORY — the per-country "what has happened" sweep (COVERAGE FIRST)

**Coverage is the first obligation of the daily. A missed development is the worst
possible defect — worse than a thin section, worse than a late edition, worse than a
clumsy sentence.** Before any writing, run this sweep for **every market in the
universe**, and be able to answer "what has happened here?" for each one. This is not
optional and it is not satisfied by looking at the last session.

**1. Never read a market from a single session.** A day-over-day change cannot see a
multi-week move. For **every** market, compute and eyeball the **level plus DoD, WoW,
MTD and drawdown-from-high** (with the date of the high) before deciding a market is
quiet. A market can print −1% on the day and be −27% from its high — that has happened
and it was missed (KOSPI 200, 19 Aug 2026: −1.47% DoD, −26.75% from its 22 June high,
while every other index in the roster was within 9% of its own high). **A market at an
extreme on ANY horizon is by definition not quiet and cannot go in the monitor table.**

**2. Sweep every asset class, not just the one that moved.** Rates · FX · equities ·
credit · commodities-exposure — plus the linkages between them. Equity index levels and
moves are a first-class layer with the same standing as rates and FX; they are not
colour. The same multi-horizon test applies to FX (move since the start of the quarter
or from the recent extreme, not just DoD) and to rates (level and curve shape, not just
the daily change).

**3. Hunt cross-asset divergences explicitly.** Each run, ask per country: *are this
market's asset classes telling the same story?* Equities down hard with the currency
strong, rates selling off with the currency firm, credit calm against an equity slide —
**a divergence between asset classes within one country is the highest-value observation
the daily can carry**, and it is invisible if each layer is only checked on the day. When
one is found, name the two candidate readings and state which observable would break the
tie.

**4. "No note in the corpus" is never the same as "nothing happened."** Sell-side flow
is evidence *toward* the topics, not the definition of them. If the data shows a market
at an extreme and no bank wrote about it in the window, that is itself the finding —
report the move from the data and say the flow is silent. Conversely, do not conclude a
market is quiet because a thematic search returned nothing; search the **data** first,
then go looking for the flow that explains it (see the two-way retrieval rule below).

**5. Missing data is a prompt to investigate, not a licence to drop a market.** A gap in
a series (an exchange holiday, a feed miss) must be resolved — check whether the market
was closed, and look at the surrounding sessions — never converted into "thin coverage"
or a quiet-monitor row by default.

**6. Non-market developments count.** Policy announcements, central-bank speak,
political and fiscal events, regulatory and geopolitical developments, supply/logistics
shocks (a closed strait, a sanctions change) — sweep for these per country too, not only
for printed data. The question is "what has happened in this country", not "what
released".

---

## Grounding & depth (the INPUT that feeds Products A–C)

The layered products are only as good as the underlying sweep. Keep it exhaustive — the depth
just gets *surfaced selectively*, not dumped.

- **Five-layer grounding, separated:** event dates/decisions ⟵ `calendar.cb_events`; printed
  actuals + component depth ⟵ **IMDR's own `econ.fact_indicator`**; views/quotes ⟵
  `research.fact_chunk` + Qdrant + Outlook; official-web fallback where the DB lacks it; market
  moves ⟵ market layers (`FX.fact_fx_rate` · `equities.fact_index_level` ·
  `rates.fact_observation` · `commodities.fact_spot`). Separate FACT from VIEW everywhere.

- **IMDR econ releases must come through effectively (first-class FACT/DEPTH).** IMDR runs its
  own country econ pipelines (`scripts/econ/{cc}/…` → `econ.fact_indicator`, e.g. US BLS/BEA/
  Census, India CPI + fresh-food nowcaster, AU labour/housing, and the rest). When one of these
  loads a fresh in-window release, it is the **preferred, most authoritative actual** — richer
  and more granular than the TE/BQL calendar lane or a sell-side rounding. Therefore:
  - **Actively sweep `econ.fact_indicator` per country each run** for observations whose latest
    obs date falls in the window (a *new IMDR print*), not just `cb_events`. Do not rely on the
    calendar lane to tell you an actual exists — our pipeline may hold it when TE/BQL don't yet
    (and vice-versa).
  - **Dual-source rule:** `actual` ⟵ prefer `econ.fact_indicator` where IMDR holds it; `consensus`
    ⟵ `cb_events` (survey/forecast). Label which lane carried the actual when they differ or when
    one is missing.
  - **`cb_events` BQL/TE lanes do not reconcile with each other (2026-07-27).** The same release
    can be bucketed under a different `event_date` in each lane (BQL on the SGT local day, TE on
    the true-UTC day — often the prior day for Asian-morning releases) **and** carry a different
    `event_name` in each. A single-lane, single-date lookup can miss the other lane's row
    entirely — this is what caused a Japan CPI print to be overlooked in a prior daily digest.
    Check both vendor lanes for a country/date window before concluding "nothing released."
    Detail: `docs/admin/calendar/bql_calendar.md` § Known limitation.
  - A fresh IMDR econ print must **reach the right product** — a hero tile / reaction line / the
    relevant deep-dive / the calendar `Actual` — and **never be dropped** because it wasn't in
    `cb_events`. If IMDR loaded it and the digest didn't surface it, that is a coverage FAILURE.
  - Where IMDR's `fact_indicator` genuinely does *not* yet hold a print (e.g. loaded only through
    a prior month), say so and fall back to the official release / sell-side, labelled — but treat
    that as a gap to close, not the normal path.

- **Exhaustive per-country corpus — BOTH halves are mandatory, and the structured half comes
  first.** Retrieve each country's in-window flow **two ways and reconcile**: (1) structured SQL
  over `research.dim_report`/`fact_chunk` scoped to country + window across all vendors,
  producing a **complete inventory** of in-scope titles that is actually read through; (2)
  targeted Qdrant per-country + per-theme sweeps. Qdrant alone is a *sample*, not coverage —
  a top-K semantic search silently drops the globally-titled flagship and the note whose
  subject you did not think to query. On 18 Aug 2026 the Qdrant-only run left ~171 in-scope
  reports unexamined and missed a −27% equity drawdown that a positioning note in the corpus
  described directly. Run the structured sweep, review every in-scope title, then use Qdrant
  to go deep on what it surfaces. Deep-read every
  substantive note; only genuine noise (single-name/sector equity, quotesheets, MBS/muni CUSIP
  packs) is noted-not-read. Read full chunk text via the scratchpad reader (the MCP truncates).
- **Hunt each country's flagship daily** as its spine (Citi *The Point*, GS *Views/Wraps*, JPM
  *Global Data Diary* + morning notes, Nomura *Research Packs*, DB/StanC/HSBC/UBS/Barclays
  rates/FX dailies, ANZ/Westpac/NAB wraps). Name them in the appendix source register.
- **DoD sign discipline (critical):** any DoD move = `(latest full session's LAST tick) −
  (prior session's LAST tick)` — last tick per calendar day, two adjacent days. NEVER from an
  intraday first-tick/open/low/high/mean to the close (an intraday low-to-close recovery is not
  a DoD move and mislabelling it flips the sign — this inverted the whole front-end thesis on
  2026-07-10). Sanity-check every rates/FX sign against the two closes before writing on top.
- **FX: never mix frequency lanes, and treat the DAILY row as a back-stamp, not a close
  (critical).** `FX.fact_fx_rate` carries the SAME vendor tick twice. `bbg_fx_snapshot`
  writes it at the file's mtime with `frequency_id = 2` (SNAPSHOT); `bbg_fx_daily` re-reads
  the identical latest row and re-stamps it at **midnight UTC of its own obs_date** with
  `frequency_id = 5` (DAILY). So a "last tick per day" read that does not filter
  `frequency_id` compares a live intraday tick on one day against a 00:00Z row that is
  really the *previous* evening's last mark. On 11 Sep 2026 the 00:00Z DAILY row and the
  15:10Z SNAPSHOT row both read EURUSD 1.16150 — one tick, two stamps — while the true
  11:10Z-to-11:10Z move was three times larger. Therefore:
  - **Always filter `frequency_id` in the WHERE clause.** One lane per query, never both.
  - **Prefer an hour-matched SNAPSHOT comparison** (same UTC hour on both days) over
    last-tick-per-day. It is the only comparison immune to the back-stamp.
  - The DAILY row is **not a close.** `imdr_daily.py` fires `bbg_fx_daily` four times a day
    (~00:5x / 06:3x / 12:3x / 18:3x UTC) and each run rewrites that date's 00:00Z row with
    whatever the mirror CSV holds at the time; where it lands is an accident of scheduling.
    Never quote it as a closing mark.
  - The DAILY row for *today* does not exist until the first run whose CSV has rolled to
    today's date — typically the ~14:3x SGT run, not the 08:5x SGT one. Its absence in the
    morning is normal and is **not** evidence of a feed failure. (The 08:00 SGT rule in
    `daily_batch_timing.md` governs the Citi lane, `vendor_id = 1`, which does land by then.)
- **RATES: not every tenor on a curve is a market quote (critical).** A vendor curve is fitted
  to a handful of liquid points and interpolated or extrapolated everywhere else. On several
  APAC curves the long end is simply **the 10Y plus a fixed constant**, so its spread to the 10Y
  never moves — the point does not trade, a "move" in it is the 10Y's move, and a change in the
  constant is a config change wearing a market's clothes. On **22 Sep 2026** the daily led its
  Greater China section with *"the 30-year is +17.3bp month-to-date against a 10-year −2.7bp, a
  20bp steepening nobody in the window writes about."* Nobody wrote about it because it did not
  happen: CNY NDIRS 10s30s sat at **0.00bp every session** through 04 Sep (the 30Y equalled the
  10Y to five decimals, with the 20Y ~2bp *above* both — an inverted hump no desk would quote),
  then stepped to exactly **20.00bp** on 07 Sep and froze again. So `+17.3 = −2.7 + 20.0`, the
  printed number exactly. The real China long end went the other way — CGB 10s30s *flattened*
  about 3bp on the month — and IMDR holds no CGB curve to have caught it. Therefore:
  - **Run `check_curve_tenors.py` and treat its SYNTHETIC list as a do-not-quote list.** Never
    print a level, a change, a spread or a curve trade from a flagged tenor — not in prose, not
    in a curve table, not in a hero tile.
  - In a curve table, a flagged cell is **`n/a`**, never a number and never a blank, with one
    footnote under the table naming the curves and why. The other rows keep their real 30Y.
  - **A month-to-date or week-to-date window that spans a STEP date is the trap**, because the
    step is indistinguishable from a move in any two-point comparison. The checker names the
    date and size; if your window spans it, the number is not quotable at any horizon.
  - The flagged set is **not static** — the constants get re-cut. Read the current run's output
    rather than a remembered list. As of 23 Sep 2026 it covers **CNY NDIRS 5Y/30Y · CNY SHIBOR
    30Y · CNH HIBOR 2Y/5Y/30Y · AUD BBSW_6M 2Y/5Y/30Y (the whole curve) · INR MIFOR 30Y ·
    MYR KLIBOR 30Y · PHP PHIREF 30Y**.
  - This is the vendor's curve construction, faithfully ingested — there is no ingest bug to
    wait on, and the guard exists only here, at authoring time.
- **Cluster fan-out** is the build method (working files: `_pmnote.md` / regional deep-dive
  clusters / `_appendix.md`), stitched into the final MD. The clusters are the research input;
  the products are the synthesis.

---

## Cadence, window, voice

- **Cadence & window.** Runs daily (ingest ~every 3h). Window = the rolling day + the prior
  session's flow.
- **Fresh standalone edition — no changelog voice.** Present tense, as-of-today. Never "updated
  from / was forward, now confirmed / reconciled vs prior day". Facts-with-memory (today's value
  vs the prior print) stays — that's the daily's job; it just isn't framed as correcting an
  earlier report. A light `(carried)` on an individual older view is fine.
- **Succinct, no-bullshit language.** Short declarative sentences, numbers over adjectives, cut
  filler and hedging. Shorten anything shortenable — but never drop a fact, number, citation, or
  flag to save words.
- **No rhetorical padding — lead with the fact.** Ban the empty tension-restating wrapper:
  "Not whether X but Y", "The question isn't … it's …", "it's not about X, it's about Y", "the real
  story is …", "the tell/takeaway/upshot is …", "make no mistake". These add words, not information.
  Open every line with the informative content — the number, the surprise, the named house view —
  not a rhetorical setup, and let the fact carry the point. A genuine *causal attribution* that names
  the driver and rejects an alternative ("oil, not local news, was the driver") is not padding —
  it carries content and is kept; the ban is on framings that restate a tension without adding a
  fact, number, or attribution. Headers are descriptive of the content, not clever ("a soft durables
  headline, a firm capex core", not "a durables miss that isn't").
- **No process narration in the report body.** Method/tooling caveats go to the appendix
  (machinery) and the closing operator message — never the reader pages.
- **Indonesia** — express via the FX leg as-is; do not wire a specific rates instrument. Internal
  note only: **never surface it in the report** (no "pending", no names, no "not wired").

---

## Repetition budget

The single-doc habit of making every section self-standing produced measurable repetition (the
core-PCE nowcast ~11×, the JP 20y auction ~12×, the NZ 2y ~8×, the China loan print ~7× on
07/16). Under the layered model: each fact appears **once in its home** — the number in the hero
band / reaction panel / house table, the debate in the PM dashboard, the drill-down in the
deep-dive, the id in the appendix. Cross-reference, don't restate.

### Compression pass (run on the finished draft, before the render)

A separate editing pass over the whole document once the content is written. For every
sentence, ask: **can this be said shorter without losing a fact?** If yes, cut it. Specifically:

- **No analogies, metaphors or scene-setting.** "A supply-side headline did in one session what
  a 25bp hike could not" is a flourish; "oil fell 6%, and every G10 curve rallied with it" is
  the same fact in half the words. Ban "the second shoe", "the tide", "the gravity shifted".
- **No "not X but Y" constructions** where Y alone carries the meaning. Write the claim; drop
  the strawman it is being contrasted against.
- **Never restate a number that appears in an adjacent table or tile.** Refer to it, don't
  reprint it.
- **No throat-clearing.** "It is worth noting that", "the key question is whether", "this
  raises the question of" — delete and start at the verb.
- **One clause per idea.** A sentence carrying three subordinate clauses is three sentences
  that have not been separated yet, or two that should have been cut.

The pass **removes words; it does not restructure sections**. Structure is governed by the
Product A / B / C definitions above.

---

## MANDATORY PRE-LOCK CHECKS — run ALL FIVE before saying the edition is done

An edition is not finished until these four mechanical checks have been run and their
output read. None is a gate you can wave through: they exist because each caught a
real defect that shipped.

**1. Calendar sort** — `python scripts/research/check_calendar_sort.py <the MD>`
Every table with a `Date` / `When` / `Time` column must be chronological. Note the
checker matches the header **exactly**: use a bare `When`, not `When (SGT)`, or the
table is silently skipped and reports as "0 calendar tables".

**2. Session scope** — `python scripts/research/check_session_scope.py --prev <prior> --curr <reported> --event <UTC time>`
**This is the timezone check, and it is the one that catches attribution errors.**
`rates.fact_observation` stamps each curve whenever the feed last snapped it, and those
times differ by up to twelve hours across markets — grouping by `CAST(ts AS date)` does
**not** give a common session. The checker prints each curve's last-mark time on both
days and splits the universe into those that *could* have traded a given release and
those marked before it.

Read the output against your own prose. **Never attribute a move in the CANNOT column
to that release.** Also act on its two flags: `MISMATCH` means the two days' marks are
taken far enough apart that the day-over-day comparison itself is broken, and
`NO PAIRED MARK` means the market cannot be marked at all and belongs in the
unmarkable list, not the reaction table.

*Why this rule exists:* the 26 Aug 2026 edition attributed a global rates rally to US
releases published at 14:00 UTC — but nine of sixteen curves, including India's −7.2bp
(the largest move in the universe), were last marked at 11:00–11:10 UTC, hours before
the data existed. The magnitudes were right; the causal story was impossible. A
same-calendar-day move is not a same-session move.

**3. Feed freshness** — `python scripts/research/check_feed_freshness.py --as-of <edition date>`
**Run this BEFORE drafting too, not only at lock** — it is what licences (or refuses) every
staleness claim in the edition. Exit 0 = every family within tolerance. Quote its dates.

A staleness claim from a prior edition is **not evidence**: re-measure it every cut. Never
write "still not loaded", "Nth consecutive edition", or a session count this run of the
check did not produce. Two rules the checker encodes, which must also govern the prose:
- **Judge against the source's publication lag, not the cut date.** FRED H.15 (cash
  Treasuries, OAS, VIX) lands T+1, so an observation dated the previous session is
  *current*. One session behind is normal and needs no caveat.
- **Never generalise a weekly series' cadence to a daily block.**
  `FRED.SENTIMENT.NFCI_CREDIT.US` reads as "credit" but is a Chicago Fed *weekly*
  (Wednesday release for the prior Friday); it is unrelated to the daily credit-OAS block.

*Why this rule exists:* the 25 and 26 Aug 2026 editions both reported FRED credit, VIX and
cash Treasuries as unloaded past 19 Aug — the 26th calling it "seven sessions stale" — when
the data was present through 24 Aug and had been ingested that morning. Two editions dropped
a credit and volatility read that was sitting in the database. See `spider.md` hard rule 6.

**4. Event dates** — `python scripts/research/check_event_dates.py --as-of <edition date> <the MD>`
**A calendar lane's `event_date` is a day-bucket, not a release date.** Never print one
without this check. It recomputes every event's date from `event_datetime` plus
`dim_country.timezone` — the instant in the release country's own calendar, which is the
only ground truth — and reports three things: rows whose stored date is wrong (A),
releases carrying two different dates across lanes (B), and dates in the digest itself
that fall on the wrong day (C). Exit 0 = every date agrees.

**Neither lane can referee the other, so never "just use the other one":**
- **TradingEconomics buckets by UTC** (100% of rows). Its `event_date` is a day early for
  every release before 08:00 UTC — i.e. most of Asia-Pacific. In the 7–28 Sep window it is
  wrong for **37 of 73** Japan rows, 19 of 30 New Zealand, 13 of 28 Korea, 10 of 54 Australia.
- **Bloomberg BQL buckets by SGT** (93.5% of rows) — the ingest box's own timezone, not the
  release country's. It is a day *late* across the Americas: 94 of 122 Mexico rows, 63 of 306
  US. It dates the 2:00 PM ET Beige Book to the following day.

When A or B fires, take the date the checker computes, not either lane's. When C fires, fix
the digest. A row with no `event_datetime` is skipped, not failed — those are the estimated /
placeholder rows, which carry guessed dates and must never be printed as hard anyway.

*Why this rule exists:* the 07 Sep 2026 weekly printed "Japan Q2 GDP, final | 07 Sep". The
release is 08:50 JST on **8 September**; both lanes held the correct instant
(`2026-09-07 23:50+00:00`) and disagreed only on the derived date. The edition read the TE
lane, published the wrong day, and then listed the same release a second time on 08 Sep from
the BQL lane, as if they were two events. The root cause is in `te_scraper.parse_calendar_html`,
which stores the TE page's GMT day verbatim; `_parse_time` even says *"consumers can shift by
`event_date_offset` if needed"*, but no `event_date_offset` exists anywhere in the repo, so no
consumer ever shifted. This gate is the failsafe and stays in force regardless of any upstream
fix to the ingest.

**5. Curve tenors** — `python scripts/research/check_curve_tenors.py <the MD>`
**A tenor whose spread to the 10Y never moves is not a market quote.** It is the 10Y plus a
construction constant, so its level marks nothing and its "change" is the 10Y's. The check
measures every active and reformed par curve over the last 90 sessions, prints the SYNTHETIC
list with each one's frozen share and the dates its constant was re-cut, then scans the MD —
both prose (`CNY NDIRS … 30-year`) and **curve tables, where the tenor is a column header and
no single line carries both tokens**. Exit 0 = the edition quotes no flagged tenor.

The survey alone never blocks: the construction is the vendor's and no edit to an MD changes
it, so gating on it would leave this check permanently red, which is how a gate stops being
read (the same reasoning as `check_event_dates.py`). It exits 1 only when **this edition**
quotes a flagged tenor — which is the one thing an author can fix. Replace the cell with `n/a`
plus a one-line footnote; see § Grounding → *RATES: not every tenor on a curve is a market quote*.

*Why this rule exists:* the 22 Sep 2026 daily built its Greater China headline on *"a 20bp
steepening nobody in the window writes about"* in CNY NDIRS 10s30s. The spread had sat at
**0.00bp every session** since June and stepped to exactly **20.00bp** on 07 Sep — a Citi
curve-config change, not a market — so the reported `30Y +17.3bp MTD` was just `10Y −2.7bp`
plus the step. The real CGB 10s30s *flattened* ~3bp on the month. Twelve lines of that edition
quoted a synthetic tenor, six of them table cells that a line-wise scan cannot see, which is
why this check reads tables by column.

---

## Render & output — the layered PDF

- MD → `data/research_summary/daily/{YYYY}/{MM}/{DD}/spider-daily-digest.md` (MD + intermediate
  HTML keep the `spider-daily-digest` stem).
- **PDF deliverable — MANDATORY filename** `rvc-daily-digest-{YYYYMMDD}.pdf` (dash-joined compact
  date), same dated folder. The client-facing name; do NOT ship `spider-daily-digest.pdf`.
- Render path (owned by Picasso / the redesigned-layout builder): `_build_spider_html.py <MD>` →
  self-contained A4 HTML → `_html_to_pdf.py <HTML> rvc-daily-digest-{YYYYMMDD}.pdf`. The renderer
  is **edition-aware** (`edition: daily` frontmatter) and **product-aware** — it renders the
  Product-A front-of-book (cutoff header, 4 hero tiles, bottom-line box, session reaction panels,
  news-vs-price boxes, PM-dashboard table, priority-expressions), the Product-B selective
  deep-dives + Street-trade-map status register + quiet-market monitor, and the Product-C audit
  appendix — each with its page kicker.
- **Charts** render as inline SVG. **Chart hygiene (from the redesign review):** never mix m/m
  and y/y on one axis (the monthly surprise vanishes next to the annual bar — split them or use a
  second panel); choose **editorial axis bounds**, not machine-generated ones (`6.72 / −0.82` and
  `4,071.6 / −301.6` read as auto-generated — round them). Every chart title must match exactly
  what is plotted (no over-claim). Charts are visually checked before shipping.
- **Layout hygiene:** no orphan pages (a page holding only the tail of one bullet); no table row
  split across a page break; the stated country order must match the actual order. For the full
  pack, generate a **clickable contents page + PDF bookmarks**.
- **Production PDF = Product A + THE DAY IN CHARTS + Product B only.** The renderer hides the
  audit appendix under `@media print`, so the client PDF ends at the deep-dive / trade map; the
  appendix stays in the **HTML** (internal). Charts render in their own band **before** the
  deep-dive, not at the tail.
- The `.docx` via `_build_spider_docx.py` is an unstyled review fallback — **never** the
  deliverable.

---

## Non-negotiables (daily)

1. **Layered delivery.** Three products from one run: PM note (1–2) · selective deep-dive (3–N) ·
   audit appendix (last). The PM note is the reading product and must stand alone.
2. **No machinery on reader pages** — only the one-line data stamp. All ids/Qdrant/depth-flags →
   appendix.
3. **Reaction is session-scoped, never a false like-for-like matrix.** Stale series omitted, not
   footnoted. Moves attributed only to the window they actually capture — **verified with
   `check_session_scope.py`, not assumed from the calendar date.** Curve marks range from
   ~11:00 to 23:00 UTC across markets; an Asian curve marked at 11:00 UTC cannot have
   traded a US release at 14:00 UTC. State the mark times in the reaction table whenever
   they differ materially across the markets shown.
3a. **A mark hour must sit inside that market's own session, and any two-market comparison
   must be struck on ONE clock hour at which both markets are open.** Two distinct failures,
   both shipped in the first build of the 25 Sep 2026 daily:
   - **Out-of-session mark.** NZIONA was marked at 20:00 UTC. New Zealand is UTC+12, so
     20:00 UTC is 08:00 NZST — *before* the Auckland open. A 23-to-24 September change on
     that hour therefore compares New Zealand's 24 Sep opening indication with its 25 Sep
     opening indication: it is not the 24 September session at all, and the 23 Sep 20:00
     print (3.97778%) was itself a 9.7bp isolated spike against 3.88034% at 21:00. Before
     using a curve's mark hour, convert it to local time and confirm it falls inside that
     market's trading day **on both dates**. Prefer the market's own local close:
     05:00 UTC = Auckland 17:00, 07:00 UTC = Sydney 17:00, 08:00 UTC = Tokyo 17:00.
   - **Mixed-clock comparison.** The same build set Australia's +7.7bp (09:00 UTC) against
     New Zealand's −8.5bp (20:00 UTC) and called it a 16.2bp one-session divergence, with
     the mark-hour difference disclosed in the prose as though disclosure repaired it. **It
     does not.** A spread, a divergence, a beta or a relative-value bullet built from two
     different clock hours is not an observation about the two markets; it is an artefact of
     the snapshot times. Re-struck at a common 05:00 UTC, Australia was +9.3bp and New
     Zealand **+11.2bp** — New Zealand was *higher*, at every one of the ten UTC hours where
     both curves carry vendor-1 marks on both dates, and the published sign was wrong.
   So: find the hours at which **both** legs quote on **both** dates, pick one inside both
   sessions, and strike both legs there. If no such hour exists, the comparison cannot be
   made and the bullet does not run — say the legs do not overlap instead of disclosing a
   caveat and printing the number anyway. `check_session_scope.py` flags MARK-TIME MISMATCH
   for exactly this; the flag is **blocking for any cross-market claim**, not advisory.
4. **Disagreement leads.** The live debates (PM dashboard) and the news-vs-price reads are the
   edge and sit in Product A.
4a. **Never invent a precision. Quote the unrounded figure where one is evidenced.** The
   failure to avoid is a number **no source states**: an ABS unemployment rate of **4.646%**
   re-rounded to a two-decimal **4.65%** is fabricated precision and reads as a different print.
   Where an unrounded value is evidenced — IMDR's own series carry it (indicator 715 stores
   4.4618246900 for July), and houses quote it — **use the unrounded figure throughout,
   including the title, deck, hero tile and block heading**, and give the agency's published
   rounding alongside it on first use in the block: *"4.646%, which the ABS publishes as 4.6%"*.
   Where no unrounded value is evidenced, quote the published figure and stop there — never
   manufacture decimals to fill the gap. The headline and the body must always carry the **same**
   figure at the **same** precision.
5. **Trades split by status, one per row, with levels + falsifier.** "Street trade map", not
   "where the book tilts".
6. **Selective coverage** (movers get blocks; quiet markets → one monitor table) — supersedes the
   old every-country-a-full-block rule. Korea is a full roster member, surfaced selectively.
   **"Selective" governs SURFACING, never SWEEPING.** Every market is swept in full every run
   per the mandatory per-country sweep above; only the surfacing is selective. A market may be
   placed in the quiet monitor **only after** its level, DoD, WoW, MTD and drawdown-from-high
   have been checked across rates, FX and equities and none is at an extreme. Calling a market
   quiet without having looked is a coverage FAILURE, and it is the most serious defect in the
   edition.
7. **IMDR econ releases come through effectively** — sweep `econ.fact_indicator` per country every
   run; a print we loaded ourselves is a first-class FACT and must reach the note, never be
   dropped for not being in `cb_events`.
8. **Neutral on execution, opinionated on relevance/causation** — state the principle, don't
   pretend to be opinion-free.
9. **Fresh standalone voice; exhaustive grounding; DoD sign-checked; no process narration.**
10. **Precise, not flowy.** Decompose prints into their category drivers; ban literary metaphors
    ("the second shoe", "gravity shifts", "the tide"). Every divergence attributed or flagged RV.
    One thread per item. Explicit dates, never relative day-names. **Sharp, specific headers** —
    a heading must name the actual content ("Soft PPI locks in the summer hold", not "Market
    reaction"); vague section titles are a defect. Each fact lives in exactly one place.
11. **No methodology narration, no internal comms in the PDF.** Sections present their content, not
    their own build rules ("movers get a block…", "split by status, multi-leg split…"). The audit
    appendix + all ids/logs/data-ops-healthcheck warnings are HTML-internal only; the production PDF
    (Product A + charts + Product B) carries none of it.
12. **The mechanical checks run before lock — calendar sort, session scope AND curve
    tenors.** The session-scope check (`check_session_scope.py`) is the timezone guard:
    curve mark times differ by up to twelve hours, so a same-calendar-day move is not a
    same-session move, and a move marked before a release cannot be attributed to it.
    The curve-tenor check (`check_curve_tenors.py`) is the instrument guard: a tenor
    whose spread to the 10Y never moves is the 10Y plus a constant, and quoting it
    prints a number that describes nothing. See "Mandatory pre-lock checks" above.
13. **Calendars are chronological.** Any calendar / event table — the day-ahead / week-ahead
    calendar and any within-block official-voice-vs-sell-side timeline (any table with a
    `Date` / `When` / `Time` column) — MUST be sorted ascending by date/time. Before locking,
    run `python scripts/research/check_calendar_sort.py <the MD>` and fix any flag. See
    `spider.md` hard rule 5 (applies to daily & weekly; auto-run as a PostToolUse hook).
