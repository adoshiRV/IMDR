# Research ingest — content quality

Last updated: 2026-06-15

Cross-cutting mechanisms that keep chart-packs, data-dumps, and
duplicate rows out of the corpus. All of this was shipped on 2026-06-15
as part of the content-quality programme.

---

## 1. Prose-density gate

**Purpose.** Many sell-side portals publish recurring "series" that
consist almost entirely of numbers, chart images, and legal disclaimer —
e.g. DB "Fixed Income Chart Of The Day", Nomura "Yen Rates Daily
Monitor", Citi "Credit Snapshot", GS "Rates MarketStrats", Barclays MBS
OAS reports. PyMuPDF extracts the text overlay of a PDF but cannot OCR
chart images. The result is extracted text that is just a disclaimer
block plus a sprinkling of numbers: near-zero retrieval value and token
waste.

**Code.** `playground/research/ingest/prose_density.py` — the
`prose_gate(text)` function; wired into the per-PDF pipeline in
`playground/research/ingest/pipeline.py` after `parse_pdf()` completes
and before the upload/embed/DB write phases. A gated-out doc costs
nothing beyond the already-completed fetch+parse.

**Setting.**
- Field: `Settings.research_prose_gate_enabled` (default `True`).
- Env var: `IMDR_RESEARCH_PROSE_GATE_ENABLED=false` to disable for a
  backfill that should pull everything.

**Gate rule.** A document is skipped if either condition holds:

```
digit_frac >= 0.35
OR  (prose_sentences <= 3  AND  digit_frac >= 0.15)
```

> **Re-calibrated 2026-06-15** (was `digit_frac >= 0.20` on the pure-digit arm).
> The 0.20 threshold wrongly flagged table-heavy NARRATIVE notes — confirmed example:
> JPM "Credit Strategy Weekly Update" has `digit_frac` ~0.23–0.24 but contains genuine
> credit-strategy prose alongside spread tables. Raising the pure-digit threshold to
> 0.35 spares those notes; RICH documents top out at `digit_frac = 0.138` so 0.35
> has wide clearance and FN=0 is maintained. Net boilerplate drop: 64/128 vs 66/138
> — the 2 now-spared docs are per-series-list candidates handled by Section 2.

**Metric definitions.**

- `digit_frac` = `digits / (letters + digits)` over the **full** PDF
  text. Number-dump tables run 0.4–0.7; analytical prose runs below
  0.15 even when terse.

- `prose_sentences` is counted over the **body** text only — disclaimer
  chunks are stripped first. The process:

  1. The full text is split into ~1500-char pseudo-chunks on blank lines
     (or at a fixed character boundary if paragraphs are absent), mirroring
     how the calibration script works.
  2. A chunk is classified as a **disclaimer chunk** if the combined
     count of legal-phrase regex hits (`_DISCLAIMER_RE`) and bank-name
     regex hits (`_BANK_RE`) is >= 3. Legal phrases alone anchor the
     rule; bank names are included only in the density count so that a
     body chunk that incidentally names the bank (e.g. "Deutsche Bank
     Research") is not stripped.
  3. A sentence in a body chunk is a **prose sentence** if it satisfies
     all three of: >= 8 words, alpha-dominant (`alpha / len >= 0.55`),
     and >= 2 function words from a fixed vocabulary. Ticker-list rows,
     number rows, and chart-axis label runs are alpha-heavy but contain
     no function words, so they do not count.

**Calibration.** Run against 187 labeled documents
(`playground/research/_coverage_audit/calibrate_prose_density.py`,
2026-06-15):

| Class | Count | Dropped by gate | False negatives |
|---|---|---|---|
| BOILERPLATE | 138 | 66 (48%) | — |
| RICH | 49 | 0 | **0 (FN=0)** |

RICH documents top out at `digit_frac = 0.138`; number-dumps run
0.4–0.7. The two-arm rule is set conservatively to guarantee zero
false-negatives at the expense of leaving ~52% of BOILERPLATE uncaught
(those rely on the per-series title lists — see Section 2 below).

**Log output.** When the gate fires, the pipeline prints:

```
[~] goldman/GS Rates MarketStrats … SKIPPED prose-density: prose-density:digit_frac=0.472 (ps=1, df=0.472)
```

Return value: `IngestResult(report_id=-1, was_inserted=False, ...)`.

---

## 2. Per-series title drop-lists (defence-in-depth)

The prose gate catches **high-digit** number-dumps. A second class of
low-value docs — chart-only publications where the analysis is embedded
in images — has **low** `digit_frac` (few numbers in the text overlay)
but near-zero prose body. These are caught by explicit series-name
drop-lists in the per-vendor discovery filters.

| Filter file | Series dropped (sample) |
|---|---|
| `filters/goldman.py` (`_CHART_ONLY_TITLE_PREFIXES`) | GS Rates MarketStrats, Commodity Futures Volatility/Curve/Roll Reports, Views From the Treasury Desk, FX Forward Point Roll, FX Carry Vol Monitor, GS Credit MarketStrats, GS CLO Secondary, GS Credit Reports - Credit Volatility Report, GS What is Priced In |
| `filters/barclays.py` (`_CHART_ONLY_TITLE_SUBSTRINGS`) | Valuation Overview, Valuation Summary (QPS Presentation decks dropped by separate `publication_type` check) |
| `filters/ms.py` (`_CHART_ONLY_TITLE_PREFIXES`) | Strait of Hormuz - Daily Tracker, Key Data Watch Calendar, Factor Effectiveness, Key Forecasts |
| `filters/nomura.py` (`_CHART_ONLY_TITLE_PREFIXES`) | USD/CNY Fix Model, G10 FX Month-End Model, FX and Rates Portfolio Update, Credit Portfolio Update, Macro Portfolio Update |
| `filters/citi.py` (`EXCLUDED_TITLE_PREFIXES`) | iBoxx Snapshot (others in that block are Excel-rendered products — a different drop reason) |
| `filters/db.py` (existing `EXCLUDED_PRODUCT_TYPES`) | All `product_type == "Charts"` (DB uses a vendor-native product type) |

Note on **DB "Fixed Income Chart Of The Day"**: this series was briefly
added to a macro-keep list during 2026-06-14 work, then reverted on
2026-06-15 when the content audit confirmed its extractable text is
watermark + disclaimer + contact boilerplate only — the analysis lives
in chart images. It now drops via the cross-vendor `_noise` rule
`"chart of the day"` in `filters/_noise.py::classify_noise`.

**Two-layer defence summary:**

```
High digit_frac docs   ──▶  prose-density gate  ──▶  dropped
(number-dump tables)         (pipeline.py)

Low digit_frac / image  ──▶  per-series title    ──▶  dropped
chart-only docs              drop-lists (filters/)
```

The two layers are complementary: neither is sufficient alone.

---

## 3. Cross-vendor content audit findings (2026-06-15)

A systematic audit of the corpus identified the following per-vendor
boilerplate series. Numbers are approximate based on sampled
`dim_report` titles:

| Vendor | Issue | Volume (approx.) |
|---|---|---|
| Goldman | ~24 of 25 sampled recurring series were boilerplate (chart-packs, data-tables, pure disclaimer-fill); only ~1/25 were analytical prose | high (~24/25 sampled) |
| Barclays | ~24% of ingested rows were low-value chart/valuation-sheet series | ~24% |
| Nomura | Large token bloat from Agency MBS chart books, FX fixing model output, Yen rates tables | substantial |
| MS | 5 distinct series confirmed boilerplate in audit | ~5 series |
| DB | "Fixed Income Chart Of The Day" confirmed chart-only (reverted to drop); broader `product_type=Charts` drop already live | ongoing |
| Citi | ~40 records identified as digit-heavy data-table series | ~40 records |

The canonical example of the "recovered-then-reverted" pattern is DB
"Fixed Income Chart Of The Day" — added to a macro-keep exception list,
then removed after the audit verified zero prose extraction.

---

## 4. Deduplication fix

**Problem.** Several vendors (DB, Goldman, STANC, and others) embed
per-download watermarks — a 32-char hex UID or the licensee email —
directly into the PDF binary. Two downloads of the same logical report
therefore produce different byte-level SHA-256 hashes, so the original
content-hash gate was silently skipping dedup: every re-download of a
watermarked report created a new `dim_report` row. By 2026-06-15 this
had accumulated 447 duplicate rows representing only 149 distinct real
documents; cascading fact_chunk rows totalled ~11.7k extra chunks.

**Fix: two-layer gate in `pipeline.py`.**

```
Layer 1 (pre-fetch):   (vendor_id, pdf_path)           — primary key
Layer 2 (post-parse):  content_hash                    — byte-hash after
                                                          watermark stripping
Fallback in db.py:     (vendor_id, publish_date, LOWER(title))
```

- **Layer 1** (`pipeline.py`, before any fetch) checks `(vendor_code,
  pdf_path)`. The path is derived from the vendor's own stable document
  UUID + date + title slug (see `ingest/paths.py`), so it is stable
  across re-runs. A hit returns immediately with zero network or DB cost.
- **Layer 2** (`pipeline.py`, after parse) checks `content_hash`. For
  watermarked vendors the hash will always differ between downloads, so
  this is a safety net for the rare case where the same bytes arrive
  under a different path.
- **Fallback in `db.py`** (`_get_existing_by_date_title`) checks
  `(vendor_id, publish_date::date, LOWER(title))` — catches case-variant
  title duplicates (e.g. "Tracking Shelf Space" vs "Tracking shelf space"
  across runs).

**Cleanup.** `playground/research/cleanup_research_dupes.py` — finds and
(with `--commit`) removes duplicate rows. Deletion order:
1. Qdrant points (chunk ids belonging to duplicate reports)
2. Fact_chunk + fact_chunk_embedding rows in DB
3. map_report_tag, map_report_market, dim_report rows

For each duplicate group the earliest row `id` (MIN) is kept; the later
ids are removed. PDFs on SharePoint are **never deleted** by this script
(shared with the kept row).

Post-cleanup result (2026-06-15 run): 471 surplus `dim_report` rows and
~11.7k surplus `fact_chunk` rows deleted across 13 vendors.

Dry-run (default, no `--commit`):

```powershell
python playground/research/cleanup_research_dupes.py
```

---

## 5. Coverage harness

`playground/research/_coverage_audit/macro_event_coverage.py` — a
repeatable, **read-only** per-vendor funnel harness. Re-run any week to
verify that every live vendor is ingesting macro-event research
(central-bank decisions, key data releases, event calendars) and flag
any macro-event titles that are being dropped at discovery or relevance.

**Usage:**

```powershell
# Default: all live-session vendors, last 7 days
python playground/research/_coverage_audit/macro_event_coverage.py

# Specific vendors / window
python playground/research/_coverage_audit/macro_event_coverage.py \
    --vendors nomura,socgen,stanc --days 7

# Longer lookback
python playground/research/_coverage_audit/macro_event_coverage.py --days 14
```

Each vendor's `discover_reports` output is captured via
`contextlib.redirect_stdout` so the harness can parse `[SKIP]`/`[DROP]`
lines from discovery and relevance filtering while reporting post-filter
survivors. Expired-session vendors (barclays, hsbc, ubs) are caught and
reported as "SESSION FAILED" rather than crashing the harness.

Known limitation: the harness sees only what each crawler discovered.
Silent discovery gaps — where the listing API was misconfigured or a
hub was missed — require full-firehose instrumented smokes per vendor.
