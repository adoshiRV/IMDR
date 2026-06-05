# Deep-Dive Playbook

Last updated: 2026-06-03

How to turn a topical user question into a re-readable thematic report
that holds up under scrutiny.

Reference output: [`docs/topics/korea_capital_outflow.md`](../../topics/korea_capital_outflow.md)
(produced 2026-06-03 in response to *"what is the Korea capital account
outflow time series and what is it composed of?"*).

---

## 1. When this playbook applies

Trigger phrases (any of these from the user):

- *"What is X and what is it composed of?"*
- *"Explain Y"* (where Y is a series, concept, or relationship)
- *"Deep dive on Z"*
- *"Summarise our coverage of W"* / *"what do we know about W?"*
- *"Make a report on …"*

Does **not** apply if:

- The answer fits in one or two sentences (just answer directly)
- The user is asking for code (use the right engineering agent)
- The answer is already in `docs/` (point to that file, don't reproduce)
- The user is mid-task and needs a tactical next step (don't pivot into a
  100-line report; finish the task)

---

## 2. The seven stages

The deep-dive that produced the Korea report walked through these stages
in order. The order matters — earlier stages set the questions later
stages answer.

### Stage 1 — Define the term independently

Before pulling data, pin down what the user's term *actually means* under
the relevant framework. This is the most-skipped stage and the highest-
ROI one — a sloppy definition contaminates everything downstream.

For the Korea piece: *"capital account outflow"* colloquially means the
Assets side of the BPM6 Financial Account, **not** the narrow BPM6
Capital Account. Surfacing that distinction up-front saved us from
answering the wrong question.

**Tools**: `WebSearch` + `WebFetch` against authoritative public sources
(IMF manuals, central-bank press releases, FRED catalogs, BIS papers).
Distinguish:

| Source tier | Example | Use for |
|---|---|---|
| 1. **Source-agency primary** | BOK monthly BoP press release, BOK ECOS metadata page | Definitions, classification, methodology |
| 2. **International framework** | IMF BPM6 Manual ch. 6, IMF SDDS country page | Cross-country comparability, formal terminology |
| 3. **Statistical mirrors** | FRED, OECD, World Bank | Confirming the framework propagated correctly |
| 4. **Sell-side desk** | JPM, BNP, Barclays, etc. (via IMDR research store) | Current-state interpretation; never definitions |

If sources 1-3 conflict, use the source-agency. If 1 and 4 conflict on a
definition, the agency wins; if they conflict on *interpretation*, both
get cited.

### Stage 2 — Map the source-agency code system

Once the term is defined, find where the actual data lives at the lowest
useful granularity — table IDs, series codes, item codes. Without this
the answer can't be queried later.

For the Korea piece this surfaced:
- ECOS `STAT_CODE = 301Y013` ↔ KOSIS `tblId = DT_301Y013` (1:1)
- Five `BOPF1…` / `BOPF2…` / `BOPF3…` / `BOPF4…` / `BOPF5…` item-code roots
- The "debt" = "liabilities" English-UI mistranslation gotcha

This **always** belongs in `docs/admin/vendors/{vendor}/`. The deep-dive
report cites these but doesn't own them — they're a permanent vendor
fact, not a topic fact.

**Tools**: `WebSearch` for *"vendor X API documentation"*, the vendor's
own docs, Playwright discovery harnesses for browser-rendered catalogues
(see [`playground/econ/bok_ecos/discover_bop.py`](../../../playground/econ/bok_ecos/discover_bop.py)
for the pattern).

### Stage 3 — Acquire the time series

Two questions to answer up-front:
1. **What's the lowest-friction live path?** (Often FRED for OECD-mirrored series.)
2. **Where does that fall short?** (Aggregate-only, stale lag, or missing decomposition.)

Pull both the easy path *and* the high-friction-but-complete path so the
report can reconcile them. The Korea piece used FRED (8 series, easy) +
KOSIS Playwright (`DT_301Y013`, full 284-line decomposition, fresher by
12 months).

**Tools**: `playground/econ/{vendor}/` scripts. If a vendor isn't yet
scaffolded, add it under `playground/` (never `scripts/explore/`, never
the repo root — per CLAUDE.md). Save raw downloads to
`playground/{domain}/{vendor}/sample_output/{YYYY}/{MM}/{DD}/`.

Sanity-check the data: sum-of-components should tie out to the parent
line; magnitudes should match desk-cited numbers; signs should match
narrative direction.

### Stage 4 — Mine the IMDR research corpus

Pull every report in `research.dim_report` that touches the topic in the
last 1-2 months. The 2,423-row table has full PDF text via
`research.fact_chunk` (59k rows). The bar to include is *contains a
number or quote that adds to the story* — not just "mentions the term".

Query shape (good as a starting template):

```sql
SELECT TOP 40 r.id, v.vendor_code, r.publish_date, r.asset_class, r.title
FROM research.dim_report r
LEFT JOIN dbo.dim_vendor v ON v.id = r.vendor_id
WHERE (r.title LIKE '%{topic}%' OR r.title LIKE '%{alt_term}%')
  AND r.publish_date >= '{cutoff}'
ORDER BY r.publish_date DESC
```

Then pull full text for the most-relevant 5-15 reports — via a Python
script through `imdr.connectors.mssql` if the MCP truncates cell width
(the imdr-db MCP truncates `chunk_text` at ~60 chars per row; use Bash +
SQLAlchemy instead for full extraction).

What to extract from each piece:

- **Specific magnitudes** (e.g. "foreign equity outflow −$27bn in May" not just "large outflows")
- **Dates / forward-looking signals** ("BoK first hike in July, terminal 3.00%")
- **Counterintuitive observations** (e.g. NPS raising *domestic* target weight; that's the news, not the standing fact)
- **Cross-desk consensus or disagreement** (when multiple desks agree, the consensus is the signal; when they disagree, that's also the signal)

**Tag the report IDs** in the final output so the analyst can pull the
underlying PDFs. Don't paraphrase quietly — cite.

### Stage 5 — Save authoritative artifacts

At this point you have three categories of material that should land in
different places:

| Material | Lifetime | Goes to |
|---|---|---|
| Source-agency metadata (BOK contact, classification rules, BPM6 basis) | Permanent | `playground/{domain}/{vendor}/discovery/{probe_ts}/` + cross-reference in `docs/admin/vendors/{vendor}/` |
| Code/STAT_CODE inventory | Permanent — grows over time | `playground/{domain}/{vendor}/stat_code_inventory.md` + summary in `docs/admin/vendors/{vendor}/{api}_reference.md` |
| Raw downloaded data | Permanent (small) or ephemeral (large) | `playground/{domain}/{vendor}/sample_output/{YYYY}/{MM}/{DD}/` |
| Rules-of-thumb the deep-dive revealed | Cross-session | Memory file via auto-memory system |

Be careful about the **PLAYGROUND-ONLY** rule (per CLAUDE.md): exploration
artifacts never land in `docs/`. The thematic report itself goes in
`docs/topics/` (it's a finished deliverable, not exploration), but the
captured Playwright probes, raw xlsx, and stat-code growth files all
stay in `playground/`.

### Stage 6 — Synthesize the one-page TL;DR

The single hardest stage. The user must be able to read **the first
screen** of the report and walk away with:

1. **What the series is** — 1-2 sentences
2. **Thesis** — 1-paragraph blockquote that frames the current state
3. **Composition** — a table with the actual components, codes, and *latest live numbers*
4. **Where we are right now** — 5-8 bullets, each with a specific number and source
5. **How to think about it** — 1 short paragraph or list explaining the *reversibility / drivers* of each component
6. **Read-sequence pointers** — links into the appendices for anyone who wants more

The Korea TL;DR is ~600 lines worth of underlying material compressed
into one screen. The compression rule: every sentence either (a) reports
a *number with a source* or (b) gives the *reader a framework for
interpreting* such numbers. No throat-clearing.

### Stage 7 — Write the appendices

Appendix structure that has worked:

- **Appendix A — Framework detail.** The full classification, code structure, terminology gotchas. Stable through time — references the schema.
- **Appendix B — Current flow picture.** Time-snapshot tables of the data + a citation table mapping every desk-research signal to a report ID. This is the part that goes stale fastest; date it explicitly.
- **Appendix C — Forward drivers.** What's about to move the series. Calendar of upcoming events + structural reallocation tables (e.g. NPS new SAA weights).
- **Appendix D — Data + code pointers.** Where to find every series, every script. Cross-references back to the `docs/admin/vendors/` and `playground/` artifacts.

Order appendices roughly by **half-life**: A is stable, D is stable, B
decays fastest, C decays as events happen. This lets a future reader
quickly skip the stale parts.

---

## 3. Quality checklist

Before declaring done, every report must pass:

- [ ] **TL;DR is one screen** (~50-60 lines including the composition table).
- [ ] **Every number has a source** — either a code/series ID *and* a date, or a citation to a research report ID.
- [ ] **At least one sum-of-components check** in the composition table — e.g. ① + ② + ③ + ④ + ⑤ = headline. Show the arithmetic.
- [ ] **Translation/terminology gotchas called out** explicitly. The "debt = liabilities" gotcha would have silently corrupted any future analyst's reading; it's now footnoted prominently.
- [ ] **Honest about gaps** — what's blocked (e.g. ECOS API key requires Korean mobile), what's stale (FRED is T+15 months), what's missing decomposition (FRED has no Direct/Portfolio Assets at monthly frequency).
- [ ] **At least one statistical pull + one desk pull** in the same report, ideally cross-checked.
- [ ] **Read-sequence is explicit** at the bottom of the TL;DR — "*If you want X, jump to Appendix Y*".
- [ ] **Saved at the right level**: report → `docs/topics/`; vendor refs → `docs/admin/vendors/{vendor}/`; raw data + probes → `playground/`.

---

## 4. Output anatomy (template)

See [output_template.md](output_template.md) for a copy-pasteable skeleton.

The minimum sections:

```
# {Topic title}

**Brief · {ISO date} · IMDR**

{1-paragraph framing of what the series is, where it lives.}

## TL;DR (one-page brief)

> {1-paragraph blockquote thesis.}

### Composition

{Table: # | Component | Code | Latest value | What it is}

Identity / sum-of-components arithmetic.

### Where we are right now ({date})

- {Specific number} {(source)}
- ...

### How to think about it

{Component-by-component reversibility / drivers.}

### Read sequence

If you want X, jump to [Appendix A](#appendix-a-...).
...

---

## Appendix A — {framework detail}
## Appendix B — Current flow picture
## Appendix C — Forward drivers
## Appendix D — Data + code pointers
```

---

## 5. Anti-patterns to avoid

These all came up during the Korea deep-dive. Don't repeat them.

| Anti-pattern | Why it bites | Fix |
|---|---|---|
| Answering the colloquial question without the framework gotcha | User asks "capital account outflow"; technical BPM6 narrow Capital Account is ~zero. Wrong answer if you don't surface the distinction. | Stage 1 first. Always pin the framework. |
| Pulling FRED only because it's easy | FRED is mirror-of-mirror; T+15 month lag; missing decomposition. KOSIS had Mar-2026 the same day; FRED only had Mar-2025. | Always pull at least one source-agency-direct path even if it requires Playwright. |
| Skipping research store mining | The desk reports already say what's moving *right now*. Free Stage 4 if you skip it; report reads stale. | Stage 4 is non-optional for anything moving in markets. |
| Burying the composition | Reader has to scroll to find the 5-row breakdown that answers the question. | Composition belongs in the TL;DR, not Appendix A. |
| Long throat-clearing intros | Two paragraphs of "Korea is an important Asian economy…" before the answer. | Start with the answer. Three sentences max before the first useful table. |
| Reproducing data already in `docs/admin/vendors/{vendor}/` | Code structure is permanent vendor fact; report repeats it = drift risk. | Cite + link. Don't reproduce. |
| Saving exploration scripts under `docs/` or `scripts/explore/` | Violates PLAYGROUND-ONLY rule. | All exploratory code goes under `playground/{domain}/{vendor}/`. |
| Forgetting the BPM7 / framework-change note | When BOK migrates to BPM7 (live work as of 2026), every code in the report will re-key. Silent breakage in 12 months. | Always footnote known forthcoming framework changes. |

---

## 6. Reference materials

- **Worked example**: [`docs/topics/korea_capital_outflow.md`](../../topics/korea_capital_outflow.md)
- **Vendor docs convention**: [`docs/admin/vendors/index.md`](../vendors/index.md), [`docs/admin/vendors/citi/`](../vendors/citi/)
- **Country econ docs convention**: [`docs/admin/econ/`](../econ/), [`docs/admin/econ/korea/`](../econ/korea/)
- **Research store schema**: `research.dim_report` (2.4k rows), `research.fact_chunk` (60k rows). See [`docs/admin/research/`](../research/).
- **Playground convention**: CLAUDE.md memory entry "PLAYGROUND-ONLY FOR EXPLORATION".
- **Output skeleton**: [output_template.md](output_template.md)
