# Bloomberg Desk-Chat Read — spec (self-contained)

The **desk-chat synthesis**: a recurring cross-house read over the raw **Bloomberg IB
(Instant Bloomberg) dealer-desk chat**. This is a distinct product from Spider — Spider
grounds on published research + IMDR data; this grounds on the **raw intraday dealer
chatter**: flow, axes, sizing arguments, the tape as the desks saw it, and RV's own live
RFQs. That last layer the portal PDFs never capture at all.

Owned by the **Hermes** agent (`.claude/agents/hermes.md`).

The read is written from the PM's chair and answers four questions the chat uniquely can:
*what moved and why per the desks · where the houses disagree and who was right · how did my
own price requests execute · which desk to ping first tomorrow.*

**Triggers** — "bbg chat summary" / "bbg chat read" / "desk chat read" plus either
(a) **a path** to a pasted dump, or (b) **"go through my emails"** / no path at all, which
means the Outlook `BBG_chats` intake.

---

## Inputs & I/O

| | Path |
|---|---|
| **Raw chat — pasted** | `data/bloomberg/chats/<freeform>.txt` — naming inconsistent (`bbg 20jul.txt`, `17jul.txt`, `Tuesday, July 7, 2026.txt`). Copy into this folder if handed a path elsewhere (e.g. `Downloads`), and keep it verbatim. |
| **Raw chat — email** | Outlook folder **`BBG_chats`** — one email per dealer window (~26–36/day), forwarded by Deepak Suri (`dsuri12@bloomberg.net`). **No raw `.txt` is written for email-sourced days** — do not fabricate one. |
| **Read (output)** | `data/research_summary/daily/{YYYY}/{MM}/{DD}/bbg_chat_summary_{YYYY-MM-DD}.md` |
| **Rendered** | `…/bbg_chat_summary_{YYYY-MM-DD}.html` **and** `…/bbg_chat_summary_{YYYY-MM-DD}.pdf` — both land beside the MD. All three are deliverables. |

One session → one read. A weekly Mon–Fri variant uses the same folder with the week-ending
date (see §Weekly variant).

## Source shape

**Pasted dump** — organised bank-by-bank: a house header (`GS:`, `JPM:`, `HSBC:`,
`Nomura:AMANDA CHUA`, `Stanc:JOHN SZ-TO`, …) then that desk's window in full; the top block
is usually one house with no header. Within a house: `SENDER NAME` (ALL-CAPS) lines then
`HH:MM:SS message`. Country tags in braces: `{SK}`, `{ID}`, `{TA}`, `{CH}`, `{us}`,
`{RA}`/`{ZZ}`. **A dump is often a multi-day scrollback** — check the date headers before
assuming one session; summarise the extra days in a short backfill appendix rather than
dropping them.

**Email intake** — pull with `outlook_email_search` (folderName `BBG_chats`) then
`read_resource` on `mail:///messages/{id}`. Graph throttles this mailbox hard (HTTP 429,
~62s retry): fire bursts of ~3 reads, wait it out, repeat. Subjects are sometimes mis-dated
— **trust the `**19AUG2026**` body header over the subject line.**

**Oversized windows.** A credit axe-sheet or a rates run-monitor window (50k–100k chars)
exceeds the read-tool token cap; the harness persists it to a `tool-results/*.txt`. Extract
`body.content` with a small Python pass and then grep — always with
`PYTHONIOENCODING=utf-8` (emoji in the bodies crash cp1252 stdout). Fetch-then-grep for the
RV roster names is much cheaper than reading a window in full, and is the right screen for
the long tail.

Times are **Asia (SGT/HKT)**. Copy-paste mangles run tables into one line ending
`Click to view full table` — treat those numbers as **indicative**.

### RV's own traders (attribute by role)

A name **requesting** a price is buy-side; a name **quoting** is the dealer.

| Name | Beat |
|---|---|
| **Saswat Panda** | SGD / INR / NZD rates, FX swaps, JPY OIS + swaptions |
| **Ruida Wu** | HKD / AUD rates, HKD vol flies, JPY LCH calendars, TWD calendars |
| **Anant Himatsingka** | TWD FX swaps |
| **Dan Su** | PHP govvies (RPGB orders) |
| **Deepak Suri** | AUD STIR / RBA meeting spreads — *also the person forwarding the dumps* |
| **Nikhil Dangayach** | **Primary credit / new issues** — NOT rates RFQs. His lines are new-issue orders ("HDFC NI Order: 100mm 5y, dw skip"); keep him out of the RFQ post-mortem. |

## Coverage rule — read all of it

**Read every window.** Do not unilaterally narrow a day's read to a "high-value" subset:
on 20 Aug 2026 a 5-of-36 sample missed two RFQs *including the day's only clear*, and got
the macro conclusion wrong. Where a window genuinely cannot be read in full (over the
token cap), extract and grep it — and say which bucket each window fell into in the source
register. If coverage is incomplete for a real reason, the ceiling is **stated in §Source
register**, never left implied.

**Reconcile the house list against the prior day.** An absent window is a forwarding gap,
not a quiet desk — say which, rather than implying the desk was silent.

## Grounding rule

Ground every claim in the messages, attributed to the house/trader who said it. Do not
import outside facts or Spider-style econ grounding — the chat *is* the source. Separate
**what the desks said** from **what actually printed** (auctions, fixings, official
headlines on the tape). Where a number sits inside a mojibake table, or a house/name is
inferred from context, say so. Keep NDF points / implied-yield curve distinct from the
cash-bond curve, and attribute by the *speaking* desk (FX vs rates) — never collapse
"across the curve" into bonds. No process narration in the document; caveats about the
read itself belong in §Source register or in operator chat, not in the body.

---

## Output structure

A masthead, a stat band, then numbered sections: the variable market blocks first, the four
fixed closers last. Section numbering is automatic in the renderer — write the headings,
not the numbers.

### Masthead

1. **`# Headline`** — a thesis, not a label. The day's argument in ~6–9 words
   ("Buyback Day: Strong Signal, No Staying Power").
2. **`### deck`** — one standfirst sentence naming the day's threads.
3. **`**Source:** …`** — meta line: date · intake channel · **window accounting**
   (`36 per-house windows (18 read in full, 2 extracted programmatically, 16 verified
   no-RV)`) · forwarded time · timezone · continuity vs the prior read.

### Hero band — 6 stat tiles

`## Hero band` + a table. Each tile = one decisive number with a decompositional caption.
Pick numbers that settle an argument, not merely large ones: the day's cleanest price move,
the consensus figure, the flow number that contradicts the narrative, the auction's
decisive statistic, the position that unwound, the RFQ scoreline (`1 / 4`).

### 1 — The one-line

One paragraph: the driver, the mechanical leg with actual deltas, the cut against the
grain, and the net-for-the-book. Deltas and surprise, never levels alone.

### 2…k — Market blocks (variable)

One numbered section per country/theme that actually moved, in descending order of
importance, each with `###` subsections. The shapes that carry weight:

- **The sizing / the dispute** — where N houses put N numbers on one event. Show the
  spread as an `hbar` chart plus the per-house arithmetic; the range *is* the information.
- **The mechanical leg** vs **what clients actually did** — two tables. Flow evidence
  (franchise net /01, client summaries) beats commentary when they disagree.
- **Who positioned, and where** — entry / target / stop / rationale, per house.
- **The event that printed** — auction/fixing/minutes stats table, then the desks'
  post-mortem. Read the *composition* (unknown takedown, directs/indirects, tail), not the
  headline bid-to-cover.
- **The dissents — and who was right on the day** — a distinct table. Naming the
  contrarian who was right is the highest-value output of a cross-house read.

### k+1 — Your price requests — post-mortem (`N asked, M done`)

The highest-value section: a **dealer execution-quality log**. Per RFQ, a `### [DONE]` /
`[NO FILL]` / `[NO TRADE]` chip head with the ask, then a table of
**dealer (house · trader) · quote · width · outcome**, normalised to one stated convention.
Then the execution read: who won and by how much (best-of-street? through the bid?), why
the others were passed (skew, width, off-market, couldn't price), and what cleared vs what
didn't (outrights vs levered calendars vs cross-market).

Two standing elements:

- **The pricing/booking error ledger** — a running `date · house · error · status` table.
  Dealer mis-prints and PV discrepancies RV caught, carried until resolved. This is the
  section that turns into a relationship conversation.
- **The routing map** — `flow → route to → condition`, i.e. what the week teaches about
  where each product should be asked, and by when.

### k+2 — Who gave good colour — dealer scorecard

`market → best desk(s) today → why it matters`. Name the individual, not just the house.
Accumulates into a "who to ping first" map.

### k+3 — Call audit

`status · call · assessment`, with chips: **RIGHT** / **WRONG** / **OPEN** / **TENSION**.
Score the *prior* reads' calls against what printed, and mark genuine cross-house tensions
(same facts, different reference points) as TENSION rather than picking a side.

### k+4 — Carry-forward / how to use

The thesis to carry (a callout), then:

- **Live next — the calendar with stakes attached**: `when / what → what's at stake, who
  says what`. Chronological.
- **Cross-asset tells the chat surfaced that the portal PDFs miss** — numbered. Standing
  examples: KOSPI-down/KRW-up = equity-hedge unwind + ADR conversion > outflow;
  JGB-up/JPY-flat = repatriation vs domestic rotation.
- **Execution takeaways** — numbered, imperative, ours: routing shifts, cut-off times,
  unresolved discrepancies.

### k+5 — Source register & coverage ceilings

`bucket → windows / read depth` for **read in full** / **extracted programmatically** /
**verified no-RV, not read**, naming every window. Then a **Ceilings** paragraph: intake
gaps vs the prior day, roster changes, where figures are indicative rather than reconciled.

---

## Authoring grammar (what the renderer understands)

Everything below is optional except the `# H1`. Plain markdown otherwise.

| Write | Get |
|---|---|
| `# Headline` | display headline |
| `### deck sentence` (first `###`, before any `##`) | standfirst |
| `**Source:** …` | small meta line under the deck |
| `## Hero band` + table | stat tiles (header row = values, body row = captions) |
| `## Section title` | auto-numbered section with the navy tick |
| `## ~ Section title` | section, deliberately **not** numbered |
| `### Subhead` | auto-numbered `{sec}.{n}` subhead |
| `### [DONE] RFQ 1 — …` | status chip + RFQ head (`DONE`/`NO FILL`/`NO TRADE`/…) |
| `#### Label` | bold lead-in label, never numbered |
| pipe table | navy-header table; a cell that is *exactly* `RIGHT`/`WRONG`/`OPEN`/`TENSION`/`DONE`/`NO FILL`/… (bare or `[bracketed]`) becomes a status chip |
| `> body` | grey callout box |
| `> [!ALERT] body` | red callout (also `!DATA` blue, `!NOTE` navy, `!FLAG`/`!WARN` amber) |
| `> **TAG** — body` | callout with an uppercase tag line |
| ` ```deskchart {json}``` ` | inline SVG chart |
| `**Footer:** …` | replaces the default footer line |

**Charts.** `{"type":"hbar"|"bar"|"line"|"grouped", "title":…, "caption":…}`.
`hbar` (the cross-house comparison workhorse) takes `points: [[label, value, "note"]]`,
optional `highlight: ["DB"]` for the outlier bar and `axis` for the x-axis title. `bar` /
`line` / `grouped` take `series: [{"name":…, "points":[[label, value]]}]`. Every chart
needs a caption saying what it is and where it came from; two or three charts a day, at the
places where the *shape* of a disagreement beats a sentence — not decoration.

## Rendering

The MD is canonical; the HTML and PDF are rendered artifacts. Two stages, one command
(stage 1 shells stage 2), under the repo `imdr` env:

```
PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8 \
  "C:/Users/adoshi/.conda/envs/imdr/python.exe" \
  playground/research/_build_deskchat_html.py \
  data/research_summary/daily/{Y}/{M}/{D}/bbg_chat_summary_{date}.md --pdf
```

- **Stage 1** — `playground/research/_build_deskchat_html.py`: MD → self-contained A4 HTML
  in the RVC *research synthesis* look (navy rail, sans display headline, stat tiles,
  numbered sections, navy-header tables, status chips, left-stripe callouts, inline-SVG
  charts). Imports the inline-markdown renderer + vertical chart engine from
  `_build_spider_html.py`; only the horizontal-bar geometry is local. **Always keeps the
  HTML** beside the MD — the folder is meant to hold `{.md, .html, .pdf}`.
- **Stage 2** — `playground/research/_html_to_pdf.py`: HTML → A4 PDF via
  Chromium/Playwright (`@page A4`, print backgrounds, running footer, PDF outline).

Smoke fixture exercising every block: `playground/research/_fixtures/deskchat_sample.md`.
`_build_desknote_html.py` is the older plain serif desk-note renderer, kept for one-off
notes; it is **not** the desk-chat path. Both builders live under `playground/`
(gitignored) — same as `_build_spider_html.py` / `_html_to_pdf.py`.

## Weekly variant

A **Mon–Fri roundup**, same folder, named `bbg_chat_summary_{week-ending-date}.md`
(or `_weekly` suffix). Same masthead/render path; emphasis shifts:

- the week in one paragraph → day-by-day tied to the traffic →
- **RFQ weekly post-mortem** as a 5-day *pattern* (what consistently cleared where, what
  never cleared regardless of ccy/size/legs) →
- who gave good colour (the week) → call audit for the week →
- carry-forward incl. a **central-bank scorecard** (who hiked/held/repriced) and next
  week's live events.

## Cadence & wiring

**Manual, on-request.** No scheduler, no ingestion pipeline — raw chat is not routed into
`research.fact_chunk` (a possible future step, distinct from this read). Not a Spider
edition and not rendered by Picasso. There is **no BBG-chat extraction script**;
`playground/research/outlook/outlook_mapi_pull.py` (local MAPI, high-water mark) is the
obvious base if one is ever built — it would sidestep both the Graph throttling and the
read-tool cap.

## Related

- `spider_daily_spec.md` / `spider_weekly_spec.md` — the published-research editions
  (different source, different grounding).
- `outlook_email_channel.md` — the `source_type=desk_commentary` Outlook route (adjacent
  desk-colour layer, not this one).
- Memory: `project_bbg_desk_chat_reads.md`.
