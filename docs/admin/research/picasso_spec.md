# Picasso — render spec (A4 HTML → PDF)

Picasso is RV Capital's **renderer**. It takes a *locked content MD* (from Spider)
and produces a self-contained **A4 HTML** in one of two house looks, then renders
that HTML to an **A4 PDF**. Picasso owns design and layout; it never edits wording.

This spec replaces the retired `picasso_design_brief.md` + `picasso_operational_spec.md`
(archived under [`_archived_2026-07-10/`](_archived_2026-07-10/)), which described an
older multi-identity approach that was never the shipping path.

## Two looks — and only two

There is **one design system** with **two structural looks**, selected automatically
from the MD's YAML frontmatter. No other identities exist (the former
lois-weekly / lois-daily / mycroft-topical / country-overview / cluster identities are
gone).

| Look | Frontmatter | Shape |
|---|---|---|
| **`spider-daily`** | `edition: daily` | Single-H1 masthead (thesis title) + `###` deck; numbered sections; hero-tile dashboard; country-first A/B/C/D pulse. Neutral. |
| **`spider-weekly`** | *(no `edition: daily`)* | Two-H1 masthead (kicker + thesis title) + `###` deck; §-numbered Tier-1 summary; `# TIER 2/3` divider bands; per-country chapters with driver subheads, hero lines, verdict pills (Argument Audit), country trade boards; Tier-3 calendar + source register. Judges. |

Both share the same **A4 geometry and brand**: `@page size:A4` (14mm margins),
`210mm` sheet, white ground, **Newsreader** display + **Public Sans** body, green
(`#1f6b4f`) accents with blue / amber / red callout variants, hero-stat tiles,
left-stripe callout boxes, verdict pills (`Solid`/`Weak`/`Stale`/`Live`), inline-SVG
charts, banded tables, and a running footer (`title · Page X / Y · Internal`).

## Single source of truth for the look

The canonical CSS + MD-grammar parser is **[`playground/research/_build_spider_html.py`](../../../playground/research/_build_spider_html.py)**
(the `CSS` constant + `build()`). That file *is* the design — do not fork the palette,
type, or geometry into a separate stylesheet. The MD conventions each look consumes are
documented in [`spider_daily_spec.md`](spider_daily_spec.md) and
[`spider_weekly_spec.md`](spider_weekly_spec.md); Picasso does not re-specify them.

## Render pipeline (two stages, deterministic)

Run under the repo `imdr` conda env (Python 3.11):

```
# 1. locked MD -> self-contained A4 HTML (edition auto-detected)
python playground/research/_build_spider_html.py <locked.md> <out.html>

# 2. A4 HTML -> A4 PDF (Chromium print path; running footer + page numbers)
python playground/research/_html_to_pdf.py <out.html> <out.pdf> --title "<footer title>"
```

Output alongside the MD in its dated folder (`data/research_summary/{daily|weekly}/…`).
Filenames: daily → `rvc-daily-digest-{YYYYMMDD}.pdf`; weekly → `spider-weekly-digest.pdf`
(HTML mirrors the MD stem). The `.docx` from `_build_spider_docx.py` is a review-only
convenience, **not** a substitute for the PDF.

## Contract

- **Render only.** Picasso never changes a word of the MD. If wording is wrong, it
  hands back to Spider.
- **Structural push-back is allowed.** If a chart-spec is infeasible or a block
  overflows the A4 layout, Picasso flags it and hands back — it does not rewrite.
- **Self-contained output.** HTML inlines all CSS + SVG; no external assets, no chart
  libraries. PDF embeds via Chromium.
- **Two looks, no invention.** If the frontmatter is missing/ambiguous, Picasso asks
  before rendering rather than guessing an identity.

## What Picasso does NOT do

- Write or edit content (that's Spider).
- Define new looks / templates — the two above are the whole set. A genuinely new look
  is a design decision to raise with the user, not to improvise.
- Touch `memory/`, push to git, or run the IMDR orchestrators.
