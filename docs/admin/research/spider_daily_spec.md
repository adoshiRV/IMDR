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

### Bottom line (a boxed callout)
2–3 sentences: the working regime + the cleaner relative-value questions it raises. This is
the single most-read element.

### Hero band — 4 tiles (precise, decompositional captions)
Exactly **four** big number tiles (the day's decisive prints). The caption says **WHY the
number is what it is** — the categories/components behind it (e.g. "energy −6.4%, core goods
flat, OER cooling → core-PCE ~0.18%") plus the memory (survey/prior). **Numbers and drivers,
never a literary metaphor** — ban "the second shoe", "the gravity shifts", "the tide", etc.
If a category decomposition isn't at hand, say what you do know, not a mood. When an IMDR econ
pipeline has just loaded a release, that print is a strong tile candidate.

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

### Deep-dive block shape (flexible, disagreement-centric)
Lead with the *why* and the *debate*, not a data recap. A block typically carries: a short
"what changed" prose lead; a compact house-view table where a real disagreement exists (e.g.
`House · Core-PCE tracking · Interpretation` — the core-PCE cluster appears **once**, here, not
eleven times); a "why it matters" note; and, for a **marquee Americas event** (US CPI/PCE/NFP/
retail sales, FOMC/Fed-speaker cluster, BoC decision/MPR), a compact **within-window
official-voice-vs-sell-side timeline** (release + policymaker comms as FACT/official, in one
column; the desk read as VIEW, in the other) — strictly inside the edition's timeframe.

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
  noted-not-read counts, thin-DB-depth flags, missing-BBG, `fact_bond_yield` empty, and **which
  IMDR econ pipelines posted a fresh in-window release** (so a missed one is caught).
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

---

## MANDATORY PRE-LOCK CHECKS — run ALL THREE before saying the edition is done

An edition is not finished until these three mechanical checks have been run and their
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
4. **Disagreement leads.** The live debates (PM dashboard) and the news-vs-price reads are the
   edge and sit in Product A.
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
12. **Both mechanical checks run before lock — calendar sort AND session scope.** The
    session-scope check (`check_session_scope.py`) is the timezone guard: curve mark
    times differ by up to twelve hours, so a same-calendar-day move is not a
    same-session move, and a move marked before a release cannot be attributed to it.
    See "Mandatory pre-lock checks" above.
13. **Calendars are chronological.** Any calendar / event table — the day-ahead / week-ahead
    calendar and any within-block official-voice-vs-sell-side timeline (any table with a
    `Date` / `When` / `Time` column) — MUST be sorted ascending by date/time. Before locking,
    run `python scripts/research/check_calendar_sort.py <the MD>` and fix any flag. See
    `spider.md` hard rule 5 (applies to daily & weekly; auto-run as a PostToolUse hook).
