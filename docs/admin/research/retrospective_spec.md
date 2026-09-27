# The Retrospective — spec (DRAFT for sign-off)

**Working agent name:** **Janus** (looks back over the record; forward only in the "rules" section).
**Cadence:** periodic look-back — monthly or quarterly, not daily. First edition is a **two-month
back-run** over 2026-06-24 → 2026-08-24.
**Output path:** `data/retrospective/{YYYY}/{period_end}/` (e.g. `data/retrospective/2026/08-24/`).
**Render:** grounded **markdown only** in v1. No new Picasso look — Picasso has exactly two, and this
is not one of them. Render decision (spider-weekly look vs the desk-chat look) is deferred until the
content is signed off.

---

## 1. What this is

An **ex-post** document. Spider, Hermes and the weeklies write the record forward; the Retrospective
judges it backward, marked to IMDR. It answers three questions:

1. **What actually happened** — a chronological narrative, globally and per market.
2. **What was timely and worked** — the trade ideas that were right, and right *when it mattered*.
3. **What was poor** — the recommendations that lost money or were wrong, with a diagnosis of *how*
   they were wrong.

It is not a re-write of the weeklies. The weeklies argue about the future from inside the week; this
argues about the past with prices that did not exist when the call was made.

## 2. Inputs — four layers, kept separate

| Layer | Source | Role | Never used for |
|---|---|---|---|
| **A · Ground truth** | IMDR: `FX.fact_fx_rate`, `rates.fact_observation`, `equities.fact_index_level`, `econ.fact_indicator`, `calendar.cb_events` | What prices did. The spine. Every number in the narrative. | Anything about what a desk *thought* |
| **B · Published sell-side** | `data/research_summary/daily/**/spider-daily-digest.md`, `weekly/**/spider-weekly-digest.md`, and behind them `research.dim_report` / `fact_chunk` | What the street recommended, dated to publication | Facts, levels, outcomes |
| **C · Dealer chat** | `data/research_summary/daily/**/bbg_chat_summary_*.md` | Intraday flow colour, where desks disagreed, RV's own RFQ execution | Published house views (chat ≠ research) |
| **D · Our own framing** | Spider's `Bottom line`, `PM dashboard`, `Mini Argument Audit` verdicts | RVC's own judgement, graded like any house | — |

**Separation rule (inherited from Spider):** a fact comes from A and carries its IMDR provenance; a
view comes from B/C/D and carries its house plus publication date. They are never blended in one
sentence without both attributions.

## 3. Corpus as at 2026-08-24

33 daily digests · 18 desk-chat reads · 8 weeklies · window 2026-06-24 → 2026-08-24.

Known gaps, to be stated in the appendix rather than papered over: no desk-chat read for **14, 17
and 21 Aug**; no daily for 06-27..06-30, 07-17..07-20, 08-10, 08-17, 08-24 (weekends aside, these
are genuine production gaps). **Friday 21 Aug chat is a separate Hermes job** — it needs the Outlook
`BBG_chats` emails, and is a prerequisite if the retrospective is to claim full August chat coverage.

## 4. Requirements — the ones that decide whether this is honest

These are load-bearing. A retrospective that skips them flatters itself.

**R1 · No look-ahead in extraction.** The ledger is built from what a document said **on its
publication date**. Extraction passes write `outcome`, `pnl`, `verdict` as `null`. Marking is a
separate deterministic code pass. Verdicts are written only after marking. An extractor that has
seen the outcome will unconsciously re-word the call.

**R2 · No survivorship.** Every trade found is carried, including ones that cannot be marked.
Unmarkable trades appear in a **`tracked`** tier with an explicit reason — dropping them is a bias,
because the unmarkable instruments (cash KTB, IndoGB, ASW, EM NDIRS, credit) are exactly where a lot
of the ideas live.

**R3 · Entry is the desk's stated entry, or the close on first publication.** Never the best price
in the window.

**R4 · Close-basis marking only.** Daily close = last observation on the date. Target and stop are
checked on closes; intraday touches are not captured, and this is stated. Closed or stopped trades
are **frozen at the desk's close date**, not marked to as-of (the July prototype MTM'd them — fix).

**R5 · Timeliness is measured separately from outcome.** "Timely" needs three numbers per trade, not
one:

- **P&L to as-of** — did it work in the end
- **Peak favourable excursion (PFE)** and **days-to-PFE** — did it work *when published*
- **Maximum adverse excursion (MAE)** — what it cost you to hold it

A call that made 20bp only after a 15bp drawdown three weeks later is not timely. A call that made
12bp in four sessions is.

**R6 · Cross-asset normalisation.** 10bp on a rates trade and 1% on an FX trade are not comparable.
Every P&L is also reported in **realised-vol units** (P&L ÷ the instrument's realised daily vol over
the holding period × √days), so the scorecard can rank across asset classes. Raw bp/% stays alongside.

**R7 · Small-n honesty.** Two months is a small sample. Per-house tables show **n** on every row; any
house with **n < 5** is reported but **not ranked**; no hit rate is quoted to more than whole
percentage points. No league table pretends to be significant.

**R8 · Failure taxonomy, not a verdict word.** "Poor" is decomposed:

- `wrong-thesis` — the argument was falsified by the data
- `right-thesis-wrong-instrument` — the view was correct, the expression was not
- `right-but-early` — falsified on the horizon given, vindicated after
- `stopped-then-vindicated` — the stop was the error, not the call
- `unfalsifiable` — no instrument, no level, no horizon (itself a finding about a house)
- `stale` — carried in the book long after its rationale lapsed

**R9 · Grade ourselves too.** Layer D. Spider's `Mini Argument Audit` calls (Solid / Weak / Stale)
are scored against what happened — a directly checkable prediction record, and the most useful
feedback loop in the document.

**R10 · Every claim traceable.** Each narrative assertion carries either an IMDR series plus date, or
a document path plus house plus date. The audit appendix lists coverage, gaps, unmarkables, proxies.

**R11 · One base date across all layers.** FX prints Sundays (full 22-pair coverage); rates and
equities do not, and the rates feed also stamps a *partial* Sunday print (19 of 58 curves on 16 Aug
2026). Anchoring each layer to "the last close before the window" therefore silently compares a
Sunday FX level with a Friday rates level. The base is **one common business day** for every layer —
the last pre-window date with broad coverage in all of them — so a window move means the same thing
across asset classes, and the weekend gap sits inside the first session where it belongs. Any series
lacking a close on that exact date falls back to its own last prior close and is flagged `stale`.

**R12 · Screen the ground truth, then verify externally.** Layer A is not automatically correct, so
every series entering the tape is screened for plausibility (average and maximum absolute daily move
against its peer group in the same table). But the screen only says *what to check* — it does not say
the series is wrong. A flagged series is verified against an outside source before it is either used
**or** discarded, and the resolution is logged in `data_notes.md`.

This matters in both directions. KS200 failed the screen badly in the first run — 4.57% average
absolute daily move against 0.44–1.85% for all 22 peers, including a +19.98% session — and was very
nearly quarantined. External checks confirmed every outlier: Korea posted the largest single-day gain
in KOSPI history on 31 July 2026 and went bear-to-bull inside a month on the AI trade. The screen was
right that it was an outlier and wrong about why. Discarding it would have deleted the most
consequential market in the window; the extreme series *was* the story.

## 5. Structure of the document

**Part 0 · Method and coverage.** Short, front-loaded so the reader knows what they are reading:
window, corpus counts, gaps, marking conventions, what "timely" means here.

**Part 1 · The tape — what actually happened, from IMDR only.** A computed table, no prose: period
move, path, high/low date and realised vol for every market in the universe — rates (2y/5y/10y/30y
per curve), FX (22 pairs), equities (23 indices) — plus the econ-surprise record (`cb_events.survey`
vs `.actual`, ~2,093 scoreable events in-window).

**Part 2 · Chronological narrative.**

- **2a · The global spine** — the window told as **regime episodes**, not a week-by-week diary. Each
  episode: what changed, what the street said at the time, what price did, when the regime broke. The
  episode boundaries are **derived from the tape**, not asserted.
- **2b · Per-market lanes** — one lane per country, same shape each time: *what the street believed
  entering the window → what the data delivered → what price did → where the belief broke.* This is
  the answer to "changes through time for a particular economy based on sell-side reccs".

**Part 3 · What was timely and worked.** Ranked trade table (marked tier) with PFE / days-to-PFE /
MAE / vol-units, then **why it worked** — was the thesis right, or was the P&L luck from an unrelated
driver? A trade that made money for a reason the desk did not state is flagged
`right-for-wrong-reason` and does not count as a win.

**Part 4 · What was poor.** Same table, other end, grouped by the R8 taxonomy. Plus the **calls**
ledger (non-trade views) resolved against prints and decisions.

**Part 5 · Scorecards.**

- Per house: n, hit rate, P&L in vol-units, median days-to-PFE, taxonomy mix
- RVC / Spider's own Argument Audit record
- Dealer chat: where the chat led or lagged the published research (Layer C vs B)
- RV execution log: the RFQ post-mortems already in the chat reads, aggregated

**Part 6 · Rules learned.** The only forward-looking section. Durable, falsifiable statements — "when
X, this desk's Y call has been early by n sessions" — each tied to evidence in Parts 3–5. Capped at
~8 rules; no rule without at least three supporting instances, and that count is shown.

**Appendix · Audit.** Coverage sweep, gaps, unmarkable register with reasons, proxy register, method
caveats.

## 6. Markability — current state (checked 2026-08-24, better than the July prototype assumed)

| Instrument class | Source | Status |
|---|---|---|
| FX spot / cross / NDF | `FX.fact_fx_rate` (256,933 rows to 08-24) | ✅ full |
| Swap / OIS outright, spread, forward | `rates.fact_observation` — **58 live curves**, incl. KRW CD, THB THOR, SGD SORA, HKD HIBOR, INR MIBOR/MIFOR, IDR JIBOR, TWD TAIBOR, PHP PHIREF, CNY NDIRS | ✅ full |
| Basis (3s6s, SOFR/FF, ESTR/EURIBOR, SOR/SOFR, SHIR/SOFR) | `rates.fact_observation` basis curves | ✅ full |
| Equity index | `equities.fact_index_level` — **23 indices, daily to 08-21** | ✅ full *(was thin in July)* |
| US cash Treasuries, TIPS, breakevens | `econ.fact_indicator` FRED lane (`FRED.RATES.UST_*`, `TIPS_*`, `BEI_*`) | ✅ full |
| US credit (IG / HY OAS) | `econ.fact_indicator` (`FRED.CREDIT.*_OAS.US`) | ✅ full |
| AU cash ACGB 2/3/5/10y | `econ.fact_indicator` (`RBA.RATES.GOVTBOND_*`) | ✅ full |
| Korea CD 91d, Indonesia SRBI | `KOFIA.CD.YIELD.KR`, `BI.RATES.SRBI_*` | ✅ full |
| **Cash KTB / IGB / IndoGB / JGB / gilt / ASW** | `rates.fact_bond_yield` | ❌ **0 rows** → OIS proxy (flagged) or `tracked` |
| Policy calls | `calendar.cb_events` + `rates.fact_bench_rates` | ✅ resolve on the decision |
| Econ-surprise calls | `cb_events.survey` vs `.actual` | ✅ 2,093 in-window |

Any proxy mark is labelled as a proxy in the row. A proxy is never presented as the instrument.

## 7. Data model

Extend, do not duplicate, the existing prototype at `playground/research/scorecard/`
(`ledger_trades.json` · `ledger_calls.json` · `mark_trades.py`). It already has stable `trade_id`
dedup, `first_seen` / `last_seen`, `source_doc_ids`, `markability`, and a working mark engine.

Additions required:

- `equity_index` mark kind; `econ_series` mark kind (FRED / RBA / KOFIA-sourced instruments)
- PFE, days-to-PFE, MAE, realised-vol normalisation (R5, R6)
- freeze-at-desk-close for closed trades (R4)
- `failure_class` field (R8) and a `right_for_wrong_reason` flag
- `layer` field: `research` | `chat` | `rvc_own`

Promotion to `research.fact_sellside_trade` / `fact_sellside_call` stays **deferred** — it needs a
migration and explicit sign-off, and the JSON ledger is sufficient for v1.

## 8. Non-goals for v1

- No new Picasso look.
- No DB writes of any kind (read-only against IMDR).
- No attempt to reconstruct RV's actual P&L — the RFQ log shows execution quality, not positions.
- No statistical-significance claims (see R7).
