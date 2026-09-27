# Weekly macro brief — author spec

This document is the **complete instruction set** for producing an RV-Capital-styled
weekly (or daily) macro brief HTML from IMDR data + ingested sell-side research.
It is written for an LLM agent (see [Lois](#lois)) but is equally usable by a human.

Hand it the date and let Lois drive — the brief is one self-contained `.html`
file with banded tables, scenario reaction matrices, embedded bank-PDF page
renders, and SharePoint links on every cited report ID.

- **Status:** active spec — Lois ships from this directly.
- **Reference example:** [`brief_assets/example_weekly_2026-06-08.html`](brief_assets/example_weekly_2026-06-08.html) (the v3 output of this spec; chart/PDF image refs won't resolve in the repo — open the live output for the rendered version).

---

## 1 · Inputs

| Input | Form | Notes |
|---|---|---|
| Period date | `YYYY-MM-DD` | Anchor: Sunday-prior for weekly; today for daily |
| Report type | `weekly` or `daily` | Drives section depth (see §3) |
| (Optional) Event focus | list of event names | Defaults: scan calendar for Tier-1 prints in scope |
| (Optional) Vendor scope | list of vendor codes | Defaults: all 15 ingested |

## 2 · Output

| Field | Value |
|---|---|
| Path (weekly) | `data/research_summary/weekly/{YYYY}/{MM}/{DD}/weekly_preview.html` |
| Path (daily)  | `data/research_summary/daily/{YYYY}/{MM}/{DD}/daily_brief.html` |
| Format | Single self-contained HTML file |
| Sub-assets | `charts/`, `bank_pdfs/`, `assets/` (logo + theme.css) — same dir |
| Theme | Inline `<style>` block, sourced from [`brief_assets/rv_theme.css`](brief_assets/rv_theme.css) |
| Font | Public Sans (loaded from Google Fonts CDN) |
| Responsive | Mobile-first; sticky nav; print-friendly via `@media print` |

The output is **portable** — moving the folder anywhere still renders correctly.
Tear off the HTML alone (image refs break) for plaintext-only consumption.

## 3 · Section structure

**A preview is forward-looking sell-side commentary on the week ahead — and the
week ahead is not only central-bank decisions.** Marquee *economic-data releases*
(CPI, payrolls/labour, GDP, activity, retail sales, PMIs) get the same preview
treatment as policy decisions: what the desks expect, where the dispersion is,
and the rates read. A brief that is wall-to-wall CB previews with the data
relegated to bare calendar rows is incomplete — the **Data Preview** section
(below) exists so the data leg is always covered, not assumed.

### Weekly — deep on Tier-1, medium on others

```
0. Sticky nav (12 anchors)
1. Brand bar (logo + meta)
2. Hero (h1 + subtitle + KPI mini-table)
3. §0 Story of the Week (big callout)
4. §1 Event Calendar (UTC, desktop table + mobile day-cards)
5. §2 Cross-Asset Markets Snapshot (4-8 charts)
6. §2x Data Preview — STANDING SECTION (the week's key economic-data releases)
   - One consolidated section covering every non-CB data print of consequence:
     consensus · prior · sell-side expectation (verbatim) · rates/market read.
   - Lead with the prints that would otherwise get no treatment (the US data
     cluster — CPI/retail sales/IP/claims; JP CPI; PPIs; PMIs). Fold in any
     data-driven medium sections (China activity, NZ GDP, UK labour) by
     reference so the data lives in ONE place, not scattered.
   - A data release big enough to be Tier-1 (e.g. a marquee US CPI or payrolls)
     graduates to a full DEEP DIVE in §3..§N — the Data Preview then carries a
     one-line pointer to it. Tier-2/monitored data stays inline here.
   - **Honesty rule:** where no desk previewed a print in scope, say so
     ("no sell-side preview indexed — consensus/prior only") rather than
     manufacture a view. Mirrors the brief's "flagged-not-papered-over" habit.
7. §3..§N DEEP DIVES (one per Tier-1 event — CB decision OR marquee data print)
   per deep dive:
     a. lead paragraph
     b. consensus banner (big number + text)
     c. vendor forecast table
     d. vendor cards grid (per-bank thesis + verbatim quotes + trade/risk)
     e. component drivers table
     f. scenario reaction matrix (bull/base/bear × 3 markets)
     g. PDF embeds (1-3 bank pages with "look at" notes)
8. §N+1..§N+M MEDIUM SECTIONS (BoC, Japan, China, Korea, India, ...)
   per medium section:
     a. lead paragraph
     b. optional callout (alert/warn)
     c. table + optional chart + 1 PDF embed
9. §N+M+1 Trade Ideas (table FIRST, supporting charts AFTER — augmentation)
10. §N+M+2 Tail Risks (numbered list — what breaks the consensus)
11. Appendix · Reports Referenced (every cited ID linked to SharePoint)
12. Footer rule (RV brand mark + date + version)
```

### Daily — same components, lighter

Replace deep-dives with medium sections (1-3 today). Add:
- `Yesterday's Surprises` (small table: print / actual / consensus / surprise / reaction)
- `Data on Deck` (the day's economic-data releases + any sell-side preview line — the daily-cadence equivalent of the weekly §2x Data Preview; keep it to a compact table)
- `Top Conviction Today` (2-3 trades from the spec)
- `Watch For` (3-5 bullets — what would change my mind)

Length target: 3-6 pages equivalent HTML.

## 4 · Design system

### Palette (light theme, sourced from `IMDR_Lens/out/assets/theme.css`)

```
--bg          #FFFFFF   white
--panel       #F4F1EA   cream
--panel-2     #FAF8F2   cream-light (banded-row tint)
--fg          #3D3E3E   dark grey body
--muted       #8A8B8B   meta text
--border      #DDD8CC   warm border
--border-soft #ECE8DE   lighter divider
--accent      #004527   deep RV green (sig colour)
--accent-ink  #FFFFFF   text on accent
--pos         #1F7D4A   green
--neg         #8B2E1E   burgundy
--warn        #B58A2C   amber
--light-green #6FA77E   accent tertiary
```

Full theme (~300 lines) is at [`brief_assets/rv_theme.css`](brief_assets/rv_theme.css)
— **inline it into the HTML** under `<style>`; do not link via `<link>` for portability.

### Typography

- Body: Public Sans 16px / 1.62 line-height, tabular numerics on.
- h1 (hero): clamp 26-38px, weight 600, accent green.
- h2 (section): clamp 20-26px, weight 600, accent green, underline 2px.
- h3 (subsection): clamp 15-17px, weight 600, accent green.
- h4 (label): 10.5px caps, letter-spacing 1.3px, muted.
- **Strict hierarchy:** h1 > h2 > h3 > h4. Subtitles never larger than titles.

### Component patterns (all defined in the CSS)

| Class | Use |
|---|---|
| `.brand-bar` | Top logo + meta strip |
| `.hero` | Title + lead paragraph |
| `.kpi-mini` | 8-cell vertical-stacked KPI table (label / value / 5d-chg · context) |
| `.callout`, `.callout.warn`, `.callout.alert` | Big highlight blocks |
| `.consensus-banner` | Big-number + text (e.g. "10/10 vendors expect…") |
| `.vendor-grid` + `.vendor-card` | Per-bank thesis cards with `blockquote` quotes |
| `.rxn-grid` | Scenario reaction matrix (auto-stacks on mobile via `data-label`) |
| `.pdf-augment` | Bank PDF page embed (eyebrow + title + img + `pa-note`) |
| `.tag.hot/warm/calm` | Event tier pills |
| `.trade-tag.rates/fx/eq/cmd` | Trade-type pills |
| `.day-cards` | Mobile alternative for §1 calendar |
| `.tbl-scroll` | Horizontal-scroll wrapper for wide tables on mobile |

### Banded rows

`tbody tr:nth-child(even) { background: var(--panel-2); }` — already in `rv_theme.css`.

## 5 · Per-section content rubric

### Hero subtitle

2 sentences, factual. Lead with the week's headline event count.
Example:
> Three central-bank decisions in 28 hours. ECB hikes Thu (10/10 consensus) ·
> BoC holds late Wed · US May CPI between them · BoJ June hike telegraphed (10/10).
> Compiled from **15 vendors · ~2,400 reports indexed last 7 days**.

### Story callout

5-8 sentences. Names the regime shift. Quote 1-2 bank phrases verbatim if salient.
Don't editorialise — describe what the desks are saying.

### KPI mini-table (8 cells)

Standard set: EUR/USD · USD/JPY · USD/KRW · USD/CAD · UST 10y · UST 2y · VIX · WTI.
Each cell: label / value / **5-day change (signed)** / 1-3 word context.
**Numbers are verified vs IMDR directly** (see §6). Never carried over from a
prior brief.

### Event calendar (§1)

Every event Mon-Fri (UTC). Columns: Day · Time · Event · Consensus · Prior ·
Vendor lean · Tier pill. Highlight Tier-1 rows with `.hi-strong`. Mobile view
groups by day-card.

### Cross-asset chart grid (§2)

4-8 charts. **Each chart needs research-driven reference lines** — not bare price.
- USDJPY → MoF 160 + UBS target 162 (horizontal dashed)
- USDKRW → HSBC EOY target + add zone shaded
- UST curve → DGS2/5/10/30, all 4 lines, end-of-line annotations
- US CPI YoY → next-month consensus marker + Fed 2% target
- 2s10s → zero line + event vertical
- VIX → 20-line + pulse annotation
- Equities rebased → SPX, SX5E, N225, KS200, NSEI

Captions cite the IMDR source table.

### Data Preview (§2x) — standing section

The data-leg counterpart to the CB deep-dives. **One table** is the backbone:

| Column | Content |
|---|---|
| Release (day/time UTC) | e.g. "US retail sales · Wed 12:30" |
| Consensus | the street number (cite source) |
| Prior | last print |
| Sell-side view | **verbatim** desk expectation from `research.fact_chunk` (data-preview notes — "US Data Weekly", "JP CPI preview", labour/retail previews) |
| Rates / market read | one line: what the print does to the front end / curve / FX |

Rules:
- **Order by importance, not by day.** Lead with the prints that carry the
  most rates content and that would otherwise be invisible (the US data
  cluster, JP CPI). A bare calendar already exists in §1 — this section is the
  *commentary*, not a second calendar.
- **Consolidate.** Data that already has a medium/deep section (China activity,
  NZ GDP, UK CPI under BoE, UK labour) is referenced here with a one-line
  pointer, not duplicated — the reader sees the whole data leg in one place.
- **No manufactured consensus.** Where no desk previewed a release, write
  "no sell-side preview indexed — consensus/prior only" and move on.
- 1 optional PDF embed (a desk's data-week table) if a money-page exists.

### Deep dive (§3+)

Each deep-dive section has **all seven sub-blocks**. Skipping any is a defect.

1. **Lead** — 4-6 sentences. The print, why it matters, where the dispersion is.
2. **Consensus banner** — one big number (e.g. `0.22`, `10/10`, `3/3`) + 2 sentences.
3. **Forecast table** — every vendor's number side-by-side. Highlight extremes.
4. **Vendor cards** — one per bank in scope (typically 4-6 banks):
   - Bank label · clickable report ID (→ SharePoint)
   - 1-line thesis (italic)
   - Forecast row (numbers)
   - 2-3 **verbatim quotes** from `research.fact_chunk` (no paraphrase)
   - Optional trade callout (warn-tinted) with explicit entry/target/stop
   - Optional risk callout (neg-tinted)
5. **Component drivers table** — Component | Direction | Vendor view.
6. **Scenario reaction matrix** — 3 scenarios (bull/base/bear) × 3 markets
   (rates / fx / equities). Each cell ~1 line. Include probabilities.
7. **PDF embeds** — 1-3 bank pages with eyebrow, title, image, and a `pa-note`
   that tells the reader **what to look at on the page**.

### Medium section (§N+)

3 sub-blocks: lead + optional callout · table · 1 PDF embed. ~½ the depth of
a deep-dive.

### Trade ideas

**Table first, charts after.** Image is augmentation, never the primary content.
10 trades for weekly, 2-3 for daily. Columns: # · Trade · Type pill · Thesis ·
Risk · Owner banks (each owner-bank ID hyperlinked).

### Tail risks

Numbered list, 5-7 items. Each item: 1 sentence, leads with `<strong>` summary
then the implication. Cover both directions (hot CPI / soft CPI; hawkish ECB /
dovish ECB).

### Appendix

Topic-grouped reference table. Every cited report ID has a SharePoint hyperlink.

## 6 · Data sources

### Cross-asset numbers (KPIs + chart data) — query IMDR directly

| Asset | Table | Query approach |
|---|---|---|
| FX spot | `fx.fact_fx_rate` | `WHERE tenor='SPOT'` join `fx.dim_currency_pair` on `base_ccy/quote_ccy` |
| UST yields | `econ.fact_indicator` | join `dim_indicator` on `source_code IN ('DGS2','DGS5','DGS10','DGS30')` |
| US CPI | `econ.fact_indicator` | `source_code='CPIAUCSL'`; date-based 12m lag (Oct-25 is null) |
| VIX | `equities.fact_vix` | `WHERE ticker IN ('VIX','VIX9D','VIX3M','VVIX','VXN')` |
| Equities | `equities.fact_index_level` | join `dim_index` on ticker |
| Commodities | `commodities.fact_spot` | symbols: `CR_NYM_CL` (WTI), `XAU`, `XAG`, `CR_IPE_BRENT` |

For 5-day change: row-number partitioned over `obs_date DESC`, compare `rn=1` vs `rn=6`.
For FX intraday: anchor at `GETUTCDATE()` and 6-day-prior window.

**Verify before writing.** Take the spot rate query, re-run against IMDR, compare
to the number you're about to put in the doc. **Numbers in the brief never come
from another brief — always live IMDR.**

### Bank quotes + official-source quotes (vendor cards) — `research.fact_chunk`

For each in-scope event, identify the priority report IDs in `research.dim_report`,
**blending sell-side and official sources by default**:

```sql
SELECT r.id, v.vendor_code, v.vendor_category, r.title, r.publish_date
FROM research.dim_report r
JOIN dbo.dim_vendor v ON v.id = r.vendor_id
WHERE r.publish_date >= DATEADD(day, -7, GETUTCDATE())
  AND v.vendor_category IN (
        'sell_side',
        'official_cb', 'official_ministry', 'official_regulator',
        'official_thinktank', 'official_statistics', 'official_supranational'
      )
  AND (r.title LIKE '%<event-name>%' OR r.asset_class = '<asset>')
ORDER BY r.publish_date DESC;
```

Default filter includes both sell-side banks AND govt agencies (BoK,
MOEF, FSS, FSC, KDI, KCS, MOTIR for Korea — 2026-06-10; the same
pattern will cover other countries as their per-country prod scripts go
live). Vendor categorisation added in [migration 086](../../../migrations/086_add_dim_vendor_category.sql).

If the brief wants *only* sell-side voices, scope to
`vendor_category = 'sell_side'`. If it wants *only* official voices
(rare in weekly briefs — more common in Mycroft topical), scope to
`vendor_category LIKE 'official_%'`.

Then pull chunks (typically chunk_index 0-3 has the meat):

```sql
SELECT chunk_index, chunk_text
FROM research.fact_chunk
WHERE report_id = :rid AND chunk_index < 4
ORDER BY chunk_index;
```

Extract direct sentences. **Quotes are verbatim** — never paraphrase.
If you can't find a quote, don't manufacture one — leave the field blank
or pick a different report.

**When citing**: distinguish sell-side from official-source quotes
visually. Sell-side cards stay as today's vendor cards. Official-source
quotes go in their own card with the agency name as the byline
("Bank of Korea Monetary Policy Board", "Korea Ministry of Economy &
Finance, Treasury Bureau") — never an analyst name. Pre-discuss with
Picasso if a new card identity is needed.

### Bank PDF page renders

PDFs sync locally via OneDrive at
`C:\Users\adoshi\OneDrive - RV Capital Management Private Ltd\Trade Knowledge Core - IMDR\`.
The relative path is `research.dim_report.pdf_path`.

Two layouts coexist under that root:

| Source | Path shape | Example |
|---|---|---|
| Sell-side research | `{YYYY}/{MM}/{DD}/{vendor}/{slug}_{uuid}.pdf` | `2026/06/10/jpm/Global_Markets_Daily_..._abc12345.pdf` |
| Govt filings | `{YYYY}/{MM}/{DD}/econ/{country}/{vendor}/{slug}_{hash}.pdf` | `2026/06/10/econ/kr/bok/financial-statement-analysis-for-2025_3e438373.pdf` |

Both share the date-first hierarchy so "what landed on 2026-06-10?" is a
single folder walk. Govt filings under HTML-body-only path (e.g. MOEF
press releases, MOTIR articles) have no PDF file — `pdf_path` is empty,
chunks are synthesized from `body_text`.

To render a page to PNG:
```python
import fitz                              # PyMuPDF
doc = fitz.open(str(local_pdf_path))
page = doc[page_num - 1]                 # 1-indexed input, 0-indexed PyMuPDF
mat = fitz.Matrix(180/72, 180/72)        # 180 DPI
pix = page.get_pixmap(matrix=mat, alpha=False)
pix.save(out_path)
doc.close()
```

Save to `bank_pdfs/{rid:04d}_{vendor}_p{NN:02d}.png` next to the HTML.

**Money-page selection:** Page 1 is usually cover/summary. Pages 2-3 have the
forecast tables, scenario charts, or trade ladders. For long Citi-style chart
packs, page 2-5 has the most info-dense visuals. Open the PDF to confirm before
rendering.

### SharePoint URL composition

```
https://itbillingrvcapitalfunds.sharepoint.com
  /teams/TradeKnowledgeCore/ResearchData1/IMDR/{url-encoded pdf_path}
```

The encoded `pdf_path` uses `quote(rel, safe='/')` — slashes are not encoded.

## 7 · Hard rules

1. **Every number is sourced from IMDR live.** No carry-over from prior briefs.
2. **Every quote is verbatim.** From `research.fact_chunk`. No paraphrase.
3. **Every cited report ID is hyperlinked** to its SharePoint PDF.
4. **No hallucination.** If a quote/number isn't available, leave the field
   empty or drop the vendor card. Never invent.
5. **Tier-1 events get the full deep-dive.** Skipping a sub-block (no reaction
   matrix, no quotes, no PDF embed) is a defect. "Tier-1 event" includes a
   marquee *data release*, not only a CB decision.
5b. **The data leg is always covered.** The Data Preview (§2x) is a standing
   section — a weekly that previews the central banks but leaves the week's
   economic-data releases as bare calendar rows is incomplete. Where no desk
   previewed a print, say so; never manufacture a consensus.
6. **Text + tables come BEFORE images.** Images augment, never lead.
7. **Headings hierarchy strict:** h1 > h2 > h3 > h4. Subtitles never larger
   than titles.
8. **KPI numbers verified vs the chart YoY math.** If your KPI says +0.19% and
   the chart annotation says +0.51%, one is wrong — fix before shipping.
9. **Banded rows always on.** `tbody tr:nth-child(even)` background.
10. **Mobile responsive.** Test sticky nav, KPI 2-col, reaction-matrix stacked,
    calendar day-cards, PDF embeds single-col under 760px.
11. **Append RV brand mark to footer.** "RV Capital · Internal · {date}" left;
    "IMDR Weekly Macro Preview · {ver}" right.
12. **Inline the CSS** (don't `<link>`) so the HTML is portable.

## 8 · Pre-ship checklist

Before declaring done:

- [ ] Open the HTML in a browser; resize to 375px; visual layout still works
- [ ] Every Tier-1 event has all 7 sub-blocks present
- [ ] Data Preview (§2x) present and covers the week's key data releases (US data cluster + any JP/EZ/UK data); no print left as a bare calendar row; "no preview indexed" stated where true
- [ ] All KPI numbers match a fresh IMDR query (re-run, compare)
- [ ] All vendor quotes grep against `chunk_text` in `research.fact_chunk`
- [ ] All `<a href="…sharepoint.com…">` URLs reachable (200 / 302 OK)
- [ ] Chart references on page → all PNGs exist under `charts/`
- [ ] PDF embeds → all PNGs exist under `bank_pdfs/` and `pa-note` is non-empty
- [ ] Heading order: h1 once, h2 underline, h3 inline, h4 caps — no rogue sizes
- [ ] Print stylesheet doesn't break — try Cmd+P preview
- [ ] No "TODO" / "TBD" / "lorem" / "fixme" in the rendered text
- [ ] Appendix lists every report ID that appeared in the body

## 9 · Reference example

The committed example at [`brief_assets/example_weekly_2026-06-08.html`](brief_assets/example_weekly_2026-06-08.html)
is the v3 build for week of 8-14 Jun 2026. Open it to see:
- Hero / story callout / KPI mini-table
- Event calendar (Mon-Fri, UTC, with tier pills)
- Cross-asset chart grid (8 charts with research-driven reference lines)
- 2 deep dives (US CPI · ECB) — each with 4-5 vendor cards, reaction matrix,
  PDF embeds with `pa-note` guidance
- 5 medium sections (BoC · Japan · China · Korea · India)
- 10-trade ideas table + 4 augmentation charts
- 6 tail risks
- Appendix with 60 SharePoint-linked report IDs

The chart `<img>` and `bank_pdfs/<img>` refs in that file won't resolve in the
repo (the binary PNGs are gitignored at `data/research_summary/_legacy_v1_v3/`).
The value of the committed example is the **structure, copy, and CSS hookup**.

---

## Lois

Lois is the IMDR sub-agent that ships briefs from this spec. See
[`.claude/agents/lois.md`](../../../.claude/agents/lois.md).

Invoke her by name when you want a new brief:

> Hand to Lois — weekly brief for 8-14 Jun 2026.

She'll:
1. Read this spec + the reference example.
2. Query IMDR for in-scope events + cross-asset numbers + research IDs.
3. Render the charts.
4. Pull the PDF money-pages.
5. Compose the HTML and write it to the canonical output path.
6. Run the §8 pre-ship checklist.
7. Return the path + the audit summary.
