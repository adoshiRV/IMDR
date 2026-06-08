# Macro brief generator — operator playbook

`imdr.research.brief` produces RV-Capital-styled HTML briefs from IMDR data
plus the local research-PDF mirror. Two report types share a common
design system, components, and pipeline:

- **weekly** — Sunday/Monday preview of the trading week ahead. Deep on
  Tier-1 events (US CPI, ECB, BoC, BoJ), medium on the rest. ~30 pp HTML
  when fully populated.
- **daily** — pre-open brief on today's prints + yesterday's surprises.
  Lite version of the weekly. 3-6 pp HTML.

This doc covers the operator surface — what to edit, what to run, what
to expect. Internal structure of the module lives in the docstrings.

---

## Quick start

```bash
# weekly
python -m imdr.research.brief weekly \
  --config src/imdr/research/brief/examples/weekly_2026-06-08_sample.yml

# daily
python -m imdr.research.brief daily \
  --config src/imdr/research/brief/examples/daily_2026-06-09_sample.yml

# parse-check only (no IMDR queries, no PDF rendering)
python -m imdr.research.brief validate \
  --config path/to/config.yml
```

Output lands at `data/daily_research_summary/{weekly|daily}/{YYYY}/{MM}/{DD}/`.

---

## Repository layout

```
src/imdr/research/brief/
├── __init__.py              # public surface — WeeklyConfig, DailyConfig, BriefPipeline
├── __main__.py              # python -m imdr.research.brief …
├── cli.py                   # weekly / daily / validate sub-commands
├── _paths.py                # output dir + SharePoint URL conventions
├── config.py                # Pydantic models for the YAML config (the one file you edit)
├── pipeline.py              # BriefPipeline + build_weekly / build_daily
│
├── data/
│   ├── cross_asset.py       # FX/UST/VIX/commodities snapshots from IMDR
│   └── reports.py           # research.dim_report lookup by report_id
├── charts/
│   ├── base.py              # RV palette + matplotlib defaults
│   └── builder.py           # 10 chart types, each callable on its own
├── pdf/
│   └── render.py            # PyMuPDF — render bank PDF money-pages
├── linking/
│   └── sharepoint.py        # SharePoint URL composition
│
├── templates/
│   ├── _base.html.j2        # head + brand bar + sticky nav + footer
│   ├── weekly.html.j2
│   ├── daily.html.j2
│   └── _components/         # 9 partials: kpi_mini, vendor_card, reaction_matrix,
│                            # pdf_augment, deep_dive, medium_section, trade_table,
│                            # tail_risks, appendix, event_calendar,
│                            # consensus_banner
├── assets/
│   ├── rv_theme.css         # palette + typography + components (the design system)
│   └── RV_Logo_Colour.png
└── examples/
    ├── weekly_2026-06-08_sample.yml
    └── daily_2026-06-09_sample.yml
```

---

## The pipeline — what runs end-to-end

```
        load_config(yaml)              ← edit this per cycle
              │
              ▼
   ┌──────────────────────────┐
   │ stage_assets             │  copy rv_theme.css + logo → out/assets/
   ├──────────────────────────┤
   │ stage_links              │  resolve every cited report_id → SharePoint URL
   │                          │  writes _report_links.json
   ├──────────────────────────┤
   │ stage_charts             │  matplotlib → 10 charts under out/charts/
   ├──────────────────────────┤
   │ stage_pdfs               │  PyMuPDF → bank PDF pages under out/bank_pdfs/
   ├──────────────────────────┤
   │ stage_render             │  Jinja2 → weekly_preview.html OR daily_brief.html
   ├──────────────────────────┤
   │ stage_audit              │  lightweight in-process checks
   │                          │  writes _audit.json
   └──────────────────────────┘
```

Each stage is idempotent and read-only against IMDR + the OneDrive PDF
mirror. The only write target is the output directory above.

---

## The config — what you edit

The YAML is the *only* thing that changes between cycles. The template,
palette, chart logic, and link wiring stay static.

### Top-level fields (both types)

```yaml
brief_type: weekly       # or "daily" — selects which template + Pydantic model
period_date: 2026-06-08  # anchor date; output goes to YYYY/MM/DD/
title: "Week of 8–14 June 2026"
subtitle_html: |
  <strong>...</strong> Inline HTML allowed in *_html fields.
story_callout: |
  The big-text callout under §0.
kpis:                    # compact mini-table at top (~8 cells)
  - { label: "EUR/USD", value: "1.1510", change: "−1.13%", change_sign: "neg", context: "into ECB" }
events:                  # the §1 calendar table
  - { day, time_utc, name, consensus, prior, vendor_lean, tier, deep_dive }
appendix:                # { topic: "vendor 4694 · vendor 4195 · ..." }
```

### Weekly-only

```yaml
deep_dives:              # §3..§N — Tier-1 events with vendor cards + reaction matrix
  - section_id: uscpi
    section_num: "§3"
    title: "..."
    label: "DEEP DIVE"
    lead: "narrative paragraph"
    consensus_number: "0.22"
    consensus_text: "Big-number banner copy"
    forecast_table_headers: [...]
    forecast_table_rows: [[...], ...]
    vendor_cards:        # per-bank thesis blocks with verbatim quotes
      - bank: "BNP Paribas"
        report_id: 3572  # → SharePoint URL resolved automatically
        thesis: "..."
        forecast: "..."
        quotes:
          - text: "..."  # verbatim from research.fact_chunk
        trade: "..."     # explicit entry/target/stop if available
        risk: "..."
    component_drivers: [[component, direction, view], ...]
    reaction_matrix:
      columns: ["UST 2y", "DXY/EURUSD", "SPX/risk"]
      bull: { label, prob, trigger, cells: { col: text } }
      base: { ... }
      bear: { ... }
    pdf_embeds:
      - report_id: 4694  # any cited report
        pages: [1]       # 1-indexed
        eyebrow: "Nomura · Soft-core forecast table"
        look_at: "Fig 1 — full component table"
medium_sections: []      # §5..§N — narrative + table + chart + 1 PDF embed
trades: []               # §M — the trade-ideas table
tail_risks: []           # §M+1
```

### Daily-only

```yaml
sections: []             # per-print medium sections (1-3 today)
yesterday_recap: ""      # narrative
yesterday_table: []      # rows of [print, actual, consensus, surprise, reaction]
top_trades: []           # 2-3 conviction trades for the day
watch_list: []           # "what would change my mind" bullets
```

---

## Public Python API

```python
from imdr.research.brief import build_weekly, build_daily, BriefPipeline

# Convenience — one call, run end-to-end:
result = build_weekly("path/to/weekly.yml")
print(result.out_html, result.audit)

# Manual — stage-by-stage (debug-friendly):
from imdr.research.brief.config import load_config
cfg = load_config("path/to/weekly.yml")
p = BriefPipeline(cfg)
p.stage_assets()
p.stage_links(conn)            # MSSQLConnector
p.stage_charts(conn)
p.stage_pdfs(conn)
p.stage_render()
p.stage_audit()
```

---

## SharePoint linking — how the IDs become URLs

Every cited `report_id` flows through `linking.build_report_links`,
which queries `research.dim_report` for the `pdf_path`, then composes:

```
https://itbillingrvcapitalfunds.sharepoint.com
  /teams/TradeKnowledgeCore/ResearchData1/IMDR/{url-encoded-pdf-path}
```

The resulting URLs are baked into the HTML at render time (templates
reference `report_links[str(rid)].sp_url`). No post-process regex pass
is needed in the new module — every link is structural.

The map is also persisted as `_report_links.json` for audit and reuse.

---

## Bank PDF embeds

Declare in the YAML:

```yaml
pdf_embeds:
  - report_id: 4694
    pages: [1]              # 1-indexed; can list multiple
    eyebrow: "Nomura · Soft-core forecast table"
    look_at: "Fig 1 — Mar/Apr Actual + May Nomura vs Consensus"
```

`stage_pdfs` looks up `pdf_path` via IMDR, opens the PDF from the local
OneDrive mirror (`C:\Users\<user>\OneDrive - RV Capital ...\Trade
Knowledge Core - IMDR\`), and renders the requested pages at 180 DPI
to `out/bank_pdfs/{rid:04d}_{vendor}_p{NN}.png`.

If the local file is missing (OneDrive offline / file not yet synced),
the page is skipped with a warning in the log — the HTML still renders,
just without that embed.

---

## Charts — what's included

`charts.builder.build_all_charts` produces ten standard charts by
default (toggleable via kwargs):

| File | Source | Reference lines |
|---|---|---|
| `fx_eurusd.png`    | `fx.fact_fx_rate`        | UBS year-end target |
| `fx_usdjpy.png`    | `fx.fact_fx_rate`        | MoF line 160 + UBS target 162 |
| `fx_usdkrw.png`    | `fx.fact_fx_rate`        | HSBC EOY 1450 + add-zone 1480-1500 |
| `fx_usdcad.png`    | `fx.fact_fx_rate`        | Range band 1.385-1.400 |
| `ust_curve_ytd.png`| `econ.fact_indicator`    | DGS 2/5/10/30 |
| `ust_2s10s.png`    | `econ.fact_indicator`    | Zero line |
| `us_cpi_yoy.png`   | `econ.fact_indicator`    | Fed target 2% + next-month consensus |
| `oil_gold_ytd.png` | `commodities.fact_spot`  | WTI + Gold dual-axis |
| `vix_term.png`     | `equities.fact_vix`      | 20-line |
| `equity_rebased.png` | `equities.fact_index_level` | SPX/SX5E/N225/KS200/NSEI |

To add a new chart: write a function in `charts/builder.py` matching the
existing pattern (takes `cx`, `out_dir`, returns `Path`), then add it
to `build_all_charts`. Theming is automatic via `configure_matplotlib`.

---

## Agentic QA — what gets checked

`stage_audit` writes `_audit.json` per run. Current checks:

| Check | What it verifies |
|---|---|
| `html_written`   | Output file exists |
| `has_charts`     | `len(charts) > 0` |
| `has_links`      | At least one SharePoint href in the HTML |
| `report_links_resolved` | Count of cited IDs that resolved to URLs |
| `sharepoint_href_count` | Total `href="…sharepoint.com…"` in HTML |
| `report_id_mentions`    | Count of bare 4-digit IDs in HTML |

Want to extend? Add checks to `stage_audit` in `pipeline.py`. The same
file structure as `playground/research/_verify_weekly_pdf.py` works —
text-content checks (required numbers/phrases), link audit, layout
density. The old script remains a useful pattern reference.

---

## Output layout

```
data/daily_research_summary/weekly/2026/06/08/
├── weekly_preview.html
├── assets/                         # rv_theme.css + RV_Logo_Colour.png (copied)
├── charts/                         # 10 PNGs
├── bank_pdfs/                      # rendered PDF pages, named {rid:04d}_{vendor}_pNN.png
├── _report_links.json              # {str(rid): {vendor, title, pdf_path, sp_url, folder_url}}
└── _audit.json                     # QA results
```

The HTML is self-contained — open `weekly_preview.html` directly in a
browser. All asset paths are relative (`assets/`, `charts/`, `bank_pdfs/`).

---

## When does each report run?

| | Cadence | Trigger | Read by |
|---|---|---|---|
| Weekly | Sun evening / Mon early UTC | Manual today; future cron in `scripts/imdr_weekly.py` after sign-off | PM doing the Sunday homework |
| Daily  | Each trading day 06:00 UTC | Manual today; future cron in `scripts/imdr_daily.py` after sign-off | Trader pre-open |

Per CLAUDE.md "no prod wiring without permission" — neither the cron
nor scheduler hooks are wired yet. The CLI is the interface; the
operator runs it.

---

## Improvement roadmap

The module is intentionally lean. Adjacent improvements I deferred:

1. **Cross-asset auto-fill** — currently the KPI mini-table and
   `kpis:` block in YAML are hand-typed. `data.load_cross_asset`
   already returns a `CrossAssetSnapshot`; a small adapter could
   auto-populate the KPI list. Keep YAML override-able for cases
   where the operator wants to fix a number.
2. **Money-page auto-pick** — bank PDFs vary; an LLM pass over
   rendered pages could pick the most info-dense page, cache the
   choice, and write back to the config.
3. **Week-over-week diff** — compare this week's vendor positions
   against last week's `_audit.json`; flag flips.
4. **Provenance attributes** — add `data-src="fx.fact_fx_rate@<ts>"`
   on every numeric span so audits can verify.
5. **Reaction matrix from a reusable library** — common matrices
   (US CPI 3-scenario, ECB 3-scenario) live in a separate YAML so
   each weekly just references them by name.
6. **Lite markdown export** — for Slack/email broadcast. Same content,
   no styling. Just another Jinja2 template.
7. **Daily feeds weekly** — quotes/numbers extracted for Friday's
   daily could be cached and reused as the Sunday weekly's draft.

---

## Why this isn't in `playground/`

Per the project's playground-vs-prod boundary:

- Prototypes that taught us the patterns lived in
  `playground/research/_make_weekly_charts_v2.py`,
  `_render_pdf_pages.py`, `_link_reports_in_html.py`,
  `_verify_weekly_pdf.py`.
- Once the shape was clear, it was promoted into `src/imdr/research/brief/`
  as a real module, mirroring how `imdr.research.auth` was promoted from
  the vendor-crawler playground.

The playground scripts remain as **reference implementations**; the
production module is the canonical entry point.
