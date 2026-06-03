# Topic Report — Output Template

Copy this skeleton into `docs/topics/{topic_slug}.md` and fill it in.
The headings and the "Read sequence" pointer scheme are load-bearing —
keep them, even if you re-name an appendix. The worked example at
[`docs/topics/korea_capital_outflow.md`](../../topics/korea_capital_outflow.md)
follows this exact shape.

---

```markdown
# {Topic title}

**Brief · {ISO publish date} · IMDR**

{One paragraph: what the series/concept is, where it lives in the
authoritative source. Two sentences naming the framework + the
canonical table/code. One sentence on why it matters right now.}

## TL;DR (one-page brief)

> {1-paragraph blockquote thesis. State the current regime + the key
> tension in one sentence. Then 1-2 sentences expanding why. Total
> ≤4 sentences.}

### Composition

| # | Component | Code | Latest value | What it is |
|---|---|---|---:|---|
| ① | ... | `CODE1` | ... | ... |
| ② | ... | `CODE2` | ... | ... |
| ... |
| **Σ** | **Headline aggregate** | (sum) | ... | The series the user asked about |

Identity: {show the arithmetic — e.g. CA + Cap + Errors ≈ FA; Σ children = parent ✓}.

### Where we are right now ({reporting period})

- {Specific magnitude} ({citation — research-report ID or series code})
- {Specific magnitude} ({citation})
- {Specific magnitude} ({citation})
- ...

### How to think about it

{Component-by-component reversibility / driver framing. One bullet per
component, ≤2 sentences each.}

- ① **{component} ≈ {regime}** — {driver}. {Direction expected.}
- ② **{component} ≈ {regime}** — {driver}.
- ...

### Read sequence

If you want the technicals, jump to [Appendix A](#appendix-a--{anchor}).
If you want the flow picture in detail, [Appendix B](#appendix-b--{anchor}).
If you want forward drivers, [Appendix C](#appendix-c--{anchor}).
If you want to pull the data yourself, [Appendix D](#appendix-d--{anchor}).

---

## Appendix A — {framework / definition detail}

{Full BPM6-equivalent framework. Classification trees. Item-code
structure. Terminology gotchas in a table:}

| Source | Says | Means |
|---|---|---|
| ... |

For the full code structure, see [`docs/admin/vendors/{vendor}/{api}_reference.md`](...).

---

## Appendix B — Current flow picture ({reporting period})

### Source-agency statistical view ({table_id}, pulled {date})

{Table of latest N periods × line items, or other compact tabular
presentation. Cite where it was pulled from + when.}

### Sell-side desk view ({date range})

| Desk | Date | Flow signal | Magnitude |
|---|---|---|---|
| {Vendor} | {date} | {one-line signal} | {number with units} |
| ... |

### Flow narrative

{6-step "mechanisms operating right now" — what every actor is doing.}

---

## Appendix C — Forward drivers

{One subsection per major forward signal. Tables when there are
weights/targets/dates; prose when there are themes.}

### {Driver 1}

{Pre-vs-post weighting table, calendar, etc.}

### {Driver 2}

...

### Calendar (next 90 days)

| Date | Event | Implication |
|---|---|---|
| ... |

---

## Appendix D — Data + code pointers

### Time series, by source

| Path | What | Lag | Notes |
|---|---|---|---|
| **{Source 1}** `{code}` | ... | T+N | Cross-link to wired-in pipeline |
| **{Source 2}** `{table}` | ... | T+N | Cross-link to Playwright fetcher |
| ... |

### Code

- [`{path/to/fetcher.py}`](...) — {one-line description}
- [`{path/to/discover.py}`](...) — {one-line description}
- [`docs/admin/vendors/{vendor}/`](...) — full vendor documentation tree

### Desk research used in Appendix B

| ID | Vendor | Date | Title |
|---|---|---|---|
| {report_id} | {vendor_code} | {ISO date} | {title} |
| ... |

### Public references

- {Source-agency primary URL}
- {International framework URL — IMF / BIS / OECD}
- {Statistical mirror URL — FRED / KOSIS / etc.}
- ...

---

*Compiled by IMDR research workflow, {ISO date}. Statistical data
verified against {source-agency-metadata file path}.*
```
