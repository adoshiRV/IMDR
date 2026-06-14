# Research ingest — content quality

Last updated: 2026-06-15

Cross-cutting mechanisms that keep chart-packs, data-dumps, and
duplicate rows out of the corpus. All of this was shipped on 2026-06-15
as part of the content-quality programme.

---

## 1. Prose-density gate — BUILT, EVALUATED, and REMOVED (2026-06-15)

The prose-density gate (`playground/research/ingest/prose_density.py`) was
built, calibrated to FN=0 on 187 labeled documents, and wired into
`pipeline.py`. It was then **evaluated for marginal contribution across the
full corpus and removed on 2026-06-15**. This section preserves the rationale
so the gate is not rebuilt.

### What it was

A two-arm rule applied after `parse_pdf()` and before upload/embed/DB write:

```
digit_frac >= 0.35
OR  (prose_sentences <= 3  AND  digit_frac >= 0.15)
```

where `digit_frac = digits / (letters + digits)` over the full PDF text,
and `prose_sentences` counted body sentences with ≥8 words, alpha-dominant
character ratio, and ≥2 function words (stripping disclaimer chunks first).

### Why it was removed

`playground/research/_coverage_audit/eval_prose_gate.py` measured the gate's
**marginal** contribution — docs it drops that the per-series title drop-lists
and `_noise` rules do NOT already catch.

Key results across 4,245 docs:

- Gate dropped 209 docs (5% of corpus).
- **192 of those were "gate-only" drops** — not caught by any other rule.
- Those 192 were concentrated in **3 vendors only**:
  - Barclays MBS analytics runs
  - Nomura Yen-Rates Daily Monitor / SDR FX Analysis
  - Citi Credit Snapshots / Index Roll Down
- **10 of 14 vendors had zero gate-only drops** — the gate added nothing for them.
- Markets-desk review of the 192 gate-only drops found them to be
  **valuable desk data-runs** — tabular data that extracted as text and is
  retrievable by a RAG query. These are NOT junk.

### Root insight (do not rebuild the gate without re-reading this)

`digit_frac` is an **inverted** signal in this corpus. High `digit_frac`
means the data EXTRACTED AS TEXT (tabular, retrievable, valuable to a
markets desk). The genuinely useless docs — chart-IMAGE dumps such as GS
MarketStrats and Tail StratBook — have **low** `digit_frac` (data locked
in images, little text extracted) and are caught precisely by the per-series
title drop-lists.

The gate therefore traded ~192 valuable data-runs dropped for ~5 incidental
CJK-mojibake catches — a bad trade. The correct, precise junk filter is the
per-series title drop-lists plus `_noise`. A global digit-based gate cannot
distinguish valuable data tables from chart-image junk.

### State after removal

- `playground/research/ingest/prose_density.py` — **deleted**.
- `playground/research/ingest/pipeline.py` — gate call removed; no
  `prose_gate()` import.
- `src/imdr/config/settings.py` — `research_prose_gate_enabled` field
  removed.
- `.env.example` — `IMDR_RESEARCH_PROSE_GATE_ENABLED` entry removed.
- The CJK-mojibake catches that the gate incidentally provided are now
  handled by per-vendor `_HAS_CJK` regex in `filters/citi.py` (added
  2026-06-15; Citi has no English-twin exemption — plain drop).

---

## 2. Per-series title drop-lists (the surviving junk mechanism)

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

**Defence summary (post-gate-removal):**

```
Chart-image-only docs   ──▶  per-series title    ──▶  dropped
(low digit_frac, images)     drop-lists (filters/)

CJK / mojibake titles   ──▶  _HAS_CJK per-vendor ──▶  dropped at discovery
                              regex (filters/)

Broad recurring junk    ──▶  _noise.classify_noise ──▶  dropped
```

The per-series title drop-lists and `_noise` are the complete, precise
junk filter. A global digit-density gate is not in use — see Section 1
for why it was evaluated and removed.

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
| Citi | ~40 records identified as digit-heavy data-table series (previously gate-only drops; now kept — confirmed as valuable desk data-runs per markets desk) | ~40 records |

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
