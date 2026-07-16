# Spider — DAILY digest spec (self-contained)

The **DAILY** edition of Spider: the *pulse*, from a cross-asset macro PM's chair. It
opens with a **~5-page executive summary** (the weekly-style Tier 1) and then a
country-first **A/B/C/D** body. This spec is **self-contained**. The daily borrows the
weekly's *summary shape* (thesis masthead · hero band · brief · a moves matrix · themes)
but stays its own edition: **neutral / no-judge** (no `Solid`/`Weak` verdicts), **DoD**
moves (not WoW), the **A/B/C/D** country body (not the weekly's per-country trade tables
or deep 4-block layout), and tighter overall. The committed 07/03 edition's body is the
gold standard for the A/B/C/D detail.

Shared fundamentals — persona, coverage universe, asset classes, the grounding
layers, voice/stance, and hard rules — live in `spider.md` and apply here. This doc
is only the daily's *structure*.

**Cadence & window.** Runs daily (ingestion ~every 3 hours, so late notes land in
the right day). Window = the rolling day + the prior session's flow. Tighter than
the weekly — the pulse, not the thesis map. Movers get depth; quiet countries get a
short honest read. Never drop a covered country.

**Grounding-tag legend — put it at the top and tag every section/claim:**
`FACT` = printed / decision (`calendar.cb_events`) · `DEPTH` = component series
(`econ.fact_indicator`) · `VIEW` = sell-side interpretation (`research.fact_chunk`
+ Qdrant) · `PRICING` = market-implied · `SYN` = your synthesis.

---

## Structure — Tier 1 (executive summary, ~5pp) then Tier 2 (the detail)

The daily opens with a **~5-page executive summary modelled on the weekly's Tier 1**,
then drops into the detailed per-country body. Same shared design system, BUT the daily
stays **neutral / no-judge** (no `Solid`/`Weak` verdicts — that judging layer is the
weekly's alone), uses **day-over-day (DoD)** moves (not the weekly's WoW), and keeps its
**A/B/C/D** country body (not the weekly's per-country trade tables / deep blocks).

### Tier 1 — Executive summary (~5 pages)

#### 0 · Masthead
Kicker (`RV CAPITAL · RATES & FX DESK — DAILY MACRO PULSE`), an **editorial thesis title
+ one-line deck** (the day's single argument), the window line (`flow YYYY-MM-DD →
YYYY-MM-DD`), universe line, and the grounding-tag legend. (Authored as two `#` H1s —
kicker then thesis title — plus a `###` deck, exactly like the weekly masthead.)

#### 1 · Hero stat band
~6–8 numbers with one-line captions: the day's biggest prints/decisions and moves — the
CB rate just decided, the surprise print, the standout FX / yield / equity move — each
set against its memory (prior/consensus). Grounded to cb_events / econ / market layers.
Renders as dashboard tiles.

#### 2 · The day in brief
1–2 tight synthesis paragraphs: the day's gravity, the cross-country throughline, what
resolved vs what's still live. The narrative the PM reads first.

#### 3 · Deltas since [prior day] — *lead with what changed* (SYN)
A **numbered list of what changed since the last run**. Each item: the delta, grounded
(FACT/VIEW + `cb_events` row or report_id), and *what it supersedes* from the prior read
(e.g. "supersedes the 07-02 hawkish-repricing frame"). New prints, new house calls,
new/closed trades, converging or diverging calls. Most-read block — every line
decision-useful and complete.

#### 4 · Cross-asset moves matrix (DoD)
One row per universe country: **FX vs USD (DoD %) · 2y (DoD bp) · 10y (DoD bp) · equity
(DoD %) · one-line read**, with an oil/vol footnote. **Day-over-day** (prior session →
today's last), rates as swap/OIS par (`fact_bond_yield` empty; label swap/OIS), "n/l"
where a series isn't loaded. This is the daily's own matrix — DoD, not the weekly's WoW.
- **DoD is defined precisely: `(latest full session's LAST tick) − (prior session's LAST
  tick)`.** Take the last tick per calendar day (max `ts` within the day) for each series,
  then difference two adjacent days. NEVER compute a delta from an intraday first-tick,
  open, low, high, or mean to the close — an intraday low-to-close recovery is NOT a DoD
  move, and mislabelling one flips the sign. This exact trap inverted the whole "front end"
  thesis on the 2026-07-10 run (SOFR/SONIA/CORRA 2y all reported +bp when they had each
  *fallen* DoD). Sanity-check every rates/FX sign against the direction of the two closes
  before writing the narrative on top of it.

#### 5 · CB / macro dashboard (FACT) + a SYN synthesis
One row per universe country: **policy rate · last move (verified date) · next scheduled
event · bias / key issue**, every rate and date traced to a `cb_events` decision row.
Follow with a **"SYN — state of the world"** paragraph: how the pieces fit today
(the day's gravity, where the divergences are).

#### 6 · Themes in play + open questions
The day's cross-country themes (who's talking, the number behind each) and the **open
questions** into the next sessions — stated **neutrally**: surface the disagreement and
what would resolve it; do NOT rate it (the daily does not judge).

### Tier 2 — The detail

#### 7 · Calendar (FACT — pure, no view)
Releases + CB events with rate relevance, today + imminent. Columns:
**Date · Time (local) · Country · Event · Consensus (survey/forecast) · Prior · Actual**.
- **Time + chronological order.** Take the release time from `cb_events.event_datetime`
  (a timezone-aware `DATETIMEOFFSET`) and **order the table chronologically by absolute
  release time** (`event_datetime` ascending), so the reader sees the day's sequence as it
  will actually unfold — not grouped by country. Display the time in the **event's own local
  market time with a tz label** (e.g. `10:00 KST`, `07:00 BST`, `08:30 ET`) — the literal
  "actual time of release". Where a row's `event_datetime` is a midnight/`00:00` placeholder
  (time unknown — common on estimated or date-only rows), show `— (time TBC)` and sort those
  to the end of their date rather than falsely ordering them at midnight.
- Show `actual` **only where the row carries one**, and mark `®` where a prior was revised.
- **Keep cells terse — the table must fit A4 width (7 columns).** The `Actual` column is
  the value(s) + at most a one-word tag (`PRINTED` / `SOFT` / `MISS` / `HELD`); do **NOT**
  put report-id grounding lists (`(60972/60979)`) in the calendar — those live in the country
  reads and the §10 ledger. Same for `Consensus`/`Prior`: values only, no prose. If a row's
  actual + tag still overflows, shorten the `Event` label, not by clipping `Actual`.
This is how the daily carries the surprise scorecard — the actual/®-revised columns
*are* the "what printed", folded into the calendar; no separate surprise table.

#### 8 · Cross-cutting trade-ideas table (VIEW — provenance-tagged, never rated)
The daily's **single** trade view — what the houses are floating right now, across
countries (this is the daily's shape; do NOT use per-country trade tables here).
Columns: **# · Trade · Key driver / rationale · Assumption it rests on · Falsifier ·
Provenance (report_id)**. **Keep the Falsifier column** — "surface the idea, its
assumption, and its falsifier" is Spider's core discipline; the daily's cross-cutting
table is exactly where it belongs. Distil from the fresh-window fact-chunk sweep +
per-theme Qdrant search. Follow with a short **SYN** summary of where the book tilts.
Every row is expanded in the relevant country read below.

#### 9 · Per-country read — A / B / C / D (the body)
Ordered by **what moved this window**. **Every country is read at the chunk level, not
just the movers** — see the depth rules below. For each country, four labelled blocks:

**Depth rules (the daily is a pulse, but the tail must not go sparse):**
- **Hunt each country's flagship DAILY as the spine.** Every country has a daily/near-daily
  sell-side flagship — find it and read it in full; it anchors that country's read the way
  the weekly leans on the weeklies. Hunt them by series: Citi *The Point* (per country) ·
  Goldman *…Views / Wraps / Kickstart* (daily) · J.P. Morgan *Global Data Diary* + regional
  morning notes · Nomura *Research Packs* (daily) · DB / StanC / HSBC / UBS / Barclays
  morning + rates/FX dailies · ANZ/Westpac/NAB daily wraps. Search `dim_report.title` (+
  `fact_chunk`), scoped to the country + window, for `%the point%`, `%wrap%`, `%daily%`,
  `%data diary%`, `%research pack%`, `%first impressions%`, `%morning%`. If a country has
  no flagship daily in-window, say so — don't thin the read to a line.
- **Check ALL in-window reports per country — exhaustively.** Sweep the full in-window
  corpus tagged to each country across every house and note type, and deep-read every
  substantive one. The `imdr-db` MCP truncates long text — read full chunks via the
  scratchpad reader. Coverage is measured by how much of each country's flow was read.
- **Raised floor — no one-line tail.** A genuinely quiet country still gets a **real read**:
  block **A** (themes in play) + block **B** (the "why", ≥1 solid paragraph grounded in its
  flagship daily) at minimum, plus **C**/**D** whenever ≥2 banks or a differentiated view
  exist. "Nothing happened" is only acceptable after the corpus has actually been checked,
  and even then you state *what the flagship daily said* and *the one thing to watch*.

For each active country, four labelled blocks:

- **A · Themes in play** — a table: **Rank · Theme · Assets · Banks talking · Why it
  matters to the PM**.
- **B · The "why"** — prose: how the houses are reasoning, the numbers behind it,
  what changed vs the prior read. Content-first (lead with the number and the read,
  not the citation); compact `(house)` tags + report_ids where a claim needs one.
- **C · Consensus views (≥2 independent banks)** — a table: **Theme · Banks · Shared
  claim · Evidence cited · What consensus is missing (grounded)**.
- **D · Differentiated / unique views** — a table: **Bank · Asset · The view · Why
  it's different · Hidden assumption · Falsifier**. This is the high-value content;
  **the Falsifier column stays here** (it's reasoned, not mechanical).
- **B2 · Big-event timeline (marquee AMERICAS events only).** When a marquee Americas
  event lands in the window — US CPI/PCE/NFP/retail sales, an FOMC decision or a Fed-speaker
  cluster, a BoC decision/MPR — add a compact **timeline-ordered** sub-panel to that country's
  block that layers the **official voice** and the **sell-side read** of it, in two explicit
  columns: **When (within-window) · Official voice (FACT/official) · Sell-side read (VIEW)**.
  - *Official voice* = the release itself (BLS/BEA/BoC print, as FACT) **plus** policymaker
    communications — Fed/BoC speeches, testimony, statement/MPR/press-conference — quoted and
    attributed, grounded to `cb_events` speaker/release rows + the research library / official web.
  - *Sell-side read* = how the desks interpret that official sequence, grounded to `fact_chunk`/Qdrant.
  - Sequence **chronologically** (pre-event setup → the print/decision → official reaction →
    market/desk reaction). **Stay strictly inside the edition's timeframe** — no "week ahead",
    no multi-week narrative; a single one-line *in-window* next-catalyst pointer is the only
    forward reference allowed. A resolved event (e.g. a decision already taken) is written as
    known FACT; a still-pending one is framed as the scheduled official leg + desk expectations,
    clearly forward. Keep it tight (a short table or chronological paragraph) — never bloat the block.
  - Do the enrichment properly: a targeted `fact_chunk`+Qdrant dig (several queries by house +
    angle) on the marquee event, quoting the actual desk words; surface distinct voices, and if
    the corpus carries **no** dissenting/contrarian take, say so rather than invent one.
  - Trigger only on genuine *Americas* marquee events; ordinary prints stay in blocks A–D.

Close each country with the **trade rows expanded** (from §4), **DEPTH** notes
(`econ.fact_indicator` coverage + any component detail), and **carry-forward /
re-verified / unreconciled** flags. **Quiet countries** get the raised-floor read above
(A + B minimum, grounded in the flagship daily) — never a bare line, never dropped,
never padded with filler.

#### 10 · Grounding ledger (SYN)
- **Sources by layer**: `cb_events` (BQL→TE) verified decision rows; `econ.fact_indicator`
  depth with per-country indicator counts + latest obs; `research.fact_chunk` + Qdrant
  + Outlook — the in-window report count and per-theme semantic sweeps run.
- **Source-of-record notes** where TE and BQL disagree (which carries the actual).
- **Unreconciled** — every cross-source / cross-house disagreement, *both shown*.
- **Not loaded / pre-print** — flagged, with sell-side-reported figures tagged.
- **Differentiated-view count** (§5.D) — e.g. "US 4 · JP 3 · … = N rows across M countries".

---

## Render & output — HTML → A4 → PDF (same look as the weekly)
- MD → `data/research_summary/daily/{YYYY}/{MM}/{DD}/spider-daily-digest.md` (the MD +
  intermediate HTML keep the `spider-daily-digest` stem).
- **PDF deliverable filename — MANDATORY:** `rvc-daily-digest-{YYYYMMDD}.pdf` (dash-joined,
  compact date, e.g. `rvc-daily-digest-20260710.pdf`), written into the same dated folder.
  This is the client-facing name; do NOT ship `spider-daily-digest.pdf`.
- Render path (the deliverable is a PDF, in the shared RVC design system):
  1. `python playground/research/_build_spider_html.py <the MD>` → self-contained A4 HTML.
  2. `python playground/research/_html_to_pdf.py <the HTML> rvc-daily-digest-{YYYYMMDD}.pdf --title "…"`
     → A4 PDF (pass the mandatory filename as the explicit `[pdf]` output arg).
  The renderer is **edition-aware** via the YAML frontmatter (`edition: daily`): it
  renders the **two-H1 masthead** (kicker + thesis title) plus the `###` deck, turns the
  **hero stat band** table into dashboard tiles, numbers `##` sections from their own
  leading `N.` (the `Deltas` lead stays numberless), page-breaks each main section, and
  styles the per-country `### Country — subtitle` reads as green country subheads.
  **The deliverable is the branded PDF via this HTML path — always run both steps.**
  `_build_spider_docx.py` produces only an unstyled fallback .docx; it is NOT the
  deliverable and must never be handed over in place of the PDF.
- **Masthead authoring:** line 1 `# RV CAPITAL · RATES & FX DESK — DAILY MACRO PULSE`
  (kicker), line 2 `# {thesis title}`, then `### {deck}`, then the window/legend lines —
  same pattern as the weekly. Keep the `edition: daily` / `date:` frontmatter block.
- H1 masthead, `##` for numbered sections, `###` for country reads / A–D, GFM pipe
  tables. Every line fully understandable on its own — no cryptic shorthand.

## Non-negotiables (daily)
- **Succinct, no-bullshit language.** Short declarative sentences, one idea each, active
  voice, numbers over adjectives. Cut filler and hedging ("it is worth noting",
  "arguably", "somewhat", "that said", "in terms of"), throat-clearing, and any word that
  doesn't change the meaning. Shorten anything that can be shortened without losing
  meaning — but never drop a fact, number, citation, or flag to save words.
- Neutral, low-opinion, **never rate a trade** — surface idea + assumption + falsifier.
  The daily borrows the weekly's *summary shape* but NOT its judging: no `Solid`/`Weak`
  verdicts, no per-country trade tables, no deep 4-block layout, DoD not WoW.
- **Fresh standalone edition — no changelog voice.** Each daily reads as one clean,
  present-tense edition, NOT a revision of the prior one. Never narrate "updated from /
  revised from / previously flagged / was forward, now confirmed / reconciled vs prior day".
  Write a just-resolved event as the plain known fact of the day. **Facts-with-memory stays**
  (today's value vs the prior print) — that is the daily's job; it just must not be framed as
  correcting an earlier report. A light `(carried)` tag on an individual older sell-side view
  is fine; day-over-day version/diff narration is not.
- Content over citation everywhere (see `spider.md`); tag sources compactly.
- **Exhaustive per-country coverage — EVERY report checked, no sampling, no exceptions.**
  For each country, retrieve the **complete** in-window corpus **two ways and reconcile them**:
  (1) structured — SQL over `research.dim_report`/`fact_chunk` scoped to the country + window
  across **all vendors**; and (2) **semantic — Qdrant** per-country + per-theme sweeps to catch
  what title/keyword matching misses. Union the two; the union is the country's corpus.
  **Every report in that union must be checked** — opened at the chunk level and classified as
  either *deep-read* (any macro / rates / FX / credit-macro / policy / cross-asset **view or
  forecast**) or *noted-not-read* (only genuinely out-of-scope noise: single-name/sector
  equity, pure quotesheets/data-plumbing, MBS/muni CUSIP packs). **Deep-read every substantive
  one — there is no "too large to read" escape.** A ~N-of-corpus sample (e.g. "read ~40 of 394")
  is a coverage FAILURE.
- **Every bank's view must be accounted for — especially the firehoses.** For each country,
  the **top publishers by in-window volume** (GS, JPM, Citi, Nomura, StanC… — whoever is
  largest that day) must have their **opinion/forecast** notes read, not just their data
  prints. Using only a house's data releases (jobless-claims/home-sales prints) while skipping
  its US Daily / Views / forecast notes is a FAILURE — this is the exact GS-in-US gap from the
  2026-07-10 run. In §10, log per country: **corpus size · deep-read count · noted-not-read
  count with reasons · the Qdrant queries run**, and confirm no top-3 publisher was reduced to
  data-points-only.
- **Deliverable = branded PDF (HTML path), never the fallback .docx.** Run
  `_build_spider_html.py` → `_html_to_pdf.py` every time; the .docx is not a substitute.
- This is the DAILY spec — its own edition. The ~5pp Tier-1 summary is modelled on the
  weekly's, but the body stays the tight country-first A/B/C/D pulse.
