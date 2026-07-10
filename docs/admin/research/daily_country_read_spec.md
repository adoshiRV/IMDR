# The Daily Country Read — start-of-day + end-of-day spec

The **daily** companion to the [Weekly Country Read](weekly_country_read_spec.md):
a lean, country-first daily anchored on a **cross-asset tape**, produced **twice a
day** — a **start-of-day (AM)** edition and an **end-of-day (PM)** edition. All 14
roster countries appear on the tape every edition; per-country *depth* scales with
the day's events/coverage (a country with a decision or marquee print gets a read +
cited desk views + any fresh trade; a quiet country is a one-line tape entry).

- **Owner:** **Perry** — the same editor as the weekly. Perry now owns BOTH recurring
  country reads: the daily (lean, AM/PM) and the weekly (deep). This supersedes the
  old "daily = Lois event-first roundup" framing in [weekly_brief_spec.md](weekly_brief_spec.md)
  (which now governs only Lois's sell-side *mechanics*, reused here).
- **Status:** active spec.
- **The core idea:** the daily is the *tape + what-moved-and-why*, not the weekly's
  full per-country A–F. It inherits every rule the weekly hardened (semantic-grounded,
  time-bound, official-first actuals, govt-bond-yield tape, cited verbatim); it
  differs only in **cadence, window, and weight**.

---

## 1 · The two editions

### AM · Start-of-day (the "what to watch today" tape)
- **Overnight tape** — cross-asset move since the prior close, all 14 (FX, equity,
  govt-bond yield where loaded, the Asia→Europe→US handoff).
- **2–3 overnight themes** — what drove the session (cited desk reads from the
  overnight window).
- **Day-ahead calendar** — today's prints + decisions, with TE consensus **and** the
  street's expectation (desk previews from the corpus).
- **Movers** — countries with overnight action get a tight read + the key desk quote.

### PM · End-of-day (the "what happened" tape)
- **Close tape** — where the day settled, all 14 (move on the session).
- **What printed today** — actual vs consensus → surprise (**actuals official-first**;
  policy actions from official/corpus, not the calendar's stored level).
- **Desk reactions** — the day's marquee events read through the corpus (cited), + any
  **fresh trade** ideas published intraday.

Each edition is one MD. The tape is the spine of both; the difference is the window
(overnight vs the session just closed) and the lean (day-ahead vs what-happened).

## 2 · Structure (both editions)

- **The tape (backbone) — all 14, every edition.** Country · policy rate · move on the
  window (FX, equity, **govt-bond yield**). Same rates-source rule as the weekly:
  govt bond yields (DM OIS swap an OK labelled proxy), **never a money-market/IBOR
  fixing**; EM "—" where the benchmark isn't loaded, flagged not faked.
- **Per-country — depth scales with events/coverage.** A country with a decision /
  marquee print / big move gets: a 2–3 line read · cited desk view(s) · any fresh
  trade `[vendor·report_id·chunk_idx]`. A quiet country gets the tape line only. **All
  14 are always on the tape; only the loud ones get a written block.** (This is the
  user's "all-14 depth depending on events/coverage.")
- **Each country section opens with a one-line NEWS SNIPPET** — `📰` then the freshest
  **date-checked, tier-1 / primary** wire headline for that country (overnight/today),
  tagged with source + verified date. It's the web-watch (§3b discipline) applied
  *per country*: it frames the country and sits ABOVE the corpus desk reads, which it
  is distinct from. It catches off-corpus/off-calendar moves at the country level
  (worked example 24-Jun: the UK snippet surfaced **PM Starmer's resignation, 22-Jun,
  Bloomberg** — which the corpus had only as a "leadership risk"). Hard date-gate: a
  snippet's event must be in-window or a clearly-labelled standing/forward catalyst;
  no undated backgrounders.

## 3 · Pipeline (lean — NOT the weekly's 6-agent fan-out)

1. **Tape pull** (Perry, `mcp__imdr-db`): FX/equity/rates moves over the window
   (AM = prior close → now; PM = the session).
2. **ONE time-bound semantic sweep** — `retrieve.py "<question>" --since <window-start>
   --until <today>` for the movers' desk reads + the day-ahead street expectations.
   **A single sweep scoped to what moved/prints — not a 4-region fan-out.**
3. **Perry assembles** the edition MD. (Picasso render optional; reuses the
   weekly-country-read components, lighter — register `daily-country-read` if/when a
   styled daily is wanted.)

Cost: ~1–2 agents per edition — runnable twice daily, unlike the weekly.

## 3b · Live-wire web check (date-gated — major breaking moves only)

A **small** web pass to catch a major economic / macro / geopolitical move the
lagged corpus + scheduled calendar haven't picked up yet (a re-escalation, a shock,
a surprise policy action). It is a *supplement* — the body stays corpus/official-
grounded — and it runs under **hard date discipline**:

- **Major moves only — and specifically the categories the corpus + calendar MISS.**
  Not routine colour. The highest-value catches are events that sit in *neither*
  the sell-side corpus nor `cb_events`:
  - **Index-provider actions** — **MSCI / FTSE Russell** market-classification &
    accessibility reviews, reclassifications, rebalances, free-float / inclusion
    changes, watch-list flags. Big passive/EM-flows impact, no `cb_events` row, often
    only local-desk corpus coverage. (Worked example: MSCI's 18-Jun-2026 review kept
    Indonesia EM but cut its Information Flow rating to *negative*, reassessment to
    Nov-2026 — a real flows risk the weekly's ID block missed.)
  - Surprise **geopolitical / policy shocks**, **sovereign-rating** actions, and
    other off-calendar market-movers.
- **HARD DATE GATING — verify the EVENT date, not the article's.** Include an item
  ONLY if its event date is confirmed inside the edition window (prior session +
  today) via a **date-specific source** (a dated news digest/article). **Undated
  backgrounders — Wikipedia, think-tank explainers, model papers — are NOT
  date-proof and are rejected for dating**: they describe an event at its *peak*,
  which resurfaces as if current (e.g. a "oil >$100 / Strait closed" hit that is
  weeks stale).
- **Check, don't assume.** WebSearch *surfaces*; then **WebFetch a date-stamped
  source to confirm the CURRENT state** before including. (Worked example
  2026-06-24: the search threw "Hormuz closed / oil >$100 / largest disruption";
  the date-confirmed 23-Jun digest showed the real state was *de-escalating, oil
  soft* — date-gating correctly rejected the stale crisis.)
- **Check mainly tier-1 wires + the primary source.** Verify and cite against
  **Bloomberg / Reuters / FT** and the **primary/official source** (e.g. MSCI's own
  review report, a central-bank release) — NOT aggregators, translated, or local-blog
  republishes. (Crawler note 2026-06-24: Reuters + FT block our web fetcher → use
  **Bloomberg + the primary/official source** for the date-check and citation.)
- **Cite + label every item:** URL + the verified event date, one line, tagged
  `[web · date-checked DD Mon]`.
- **Corroborate or contradict:** if it confirms the corpus → "confirmed"; if it
  CONTRADICTS (a move the desks/calendar missed) → flag prominently as a breaking
  update, and note the corpus is lagged.

(The same date-gated web check is available to the weekly for a major mid-/end-of-
week break; same discipline.)

## 4 · Inherited rules (do not re-derive — these bind here too)

- **Semantic search is the primary discovery, time-bound** — [weekly spec §0](weekly_country_read_spec.md);
  every retrieval `--since/--until` the edition's window.
- **Source-of-truth hierarchy** — `cb_events` = consensus + calendar only; **actuals**
  official `econ.fact_indicator` → corpus → cb_events.actual; **policy actions** from
  the official rate series / corpus. ([macro_driver_taxonomy.md §5](../econ/macro_driver_taxonomy.md))
- **Rates-tape = govt bond yields, never JIBOR-type fixings**; flag the gap where not loaded.
- **Verbatim, cited, no invention.** No web. Read-only DB.

## 5 · Output

```
data/research_summary/daily/{YYYY}/{MM}/{DD}/daily_country_read_{YYYY-MM-DD}_am.md
data/research_summary/daily/{YYYY}/{MM}/{DD}/daily_country_read_{YYYY-MM-DD}_pm.md
```

Stays under the existing daily home (`data/research_summary/daily/`). Two files/day.

## 6 · Invocation

| User says | What Perry does |
|---|---|
| "the daily" / "morning tape" / "start-of-day" | AM edition (overnight tape + day-ahead). |
| "EOD" / "end-of-day" / "the close" | PM edition (close tape + what-printed + reactions). |
| "the weekly" | The deep Weekly Country Read ([weekly_country_read_spec.md](weekly_country_read_spec.md)) — not this. |

## 7 · What the daily is NOT

- **Not** the weekly's 6-agent regional fan-out — that's unsustainable daily.
- **Not** a full A–F block for all 14 every day — only the movers get a written block;
  the rest are tape lines.
- **Not** a re-grounding of standing theses — it's the *delta*: what moved overnight /
  today, and what's next.

---

**The weekly is the deep country review; the daily is the tape and the delta. Same
editor (Perry), same rules, same corpus — lighter, twice a day, movers in depth.**
