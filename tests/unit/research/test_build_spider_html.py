"""Smoke test for `_build_spider_html.py` — daily audit-appendix print-hide.

Locks down the fix for the daily digest's AUDIT APPENDIX section: it must render
in the on-screen HTML but be hidden under `@media print` so it never reaches the
client PDF (spider_daily_spec.md, Render section). Also asserts the weekly path
(which has no `## AUDIT APPENDIX` section) is unaffected.
"""
from __future__ import annotations

import sys
from pathlib import Path

_PR = Path(__file__).resolve().parents[3] / "playground" / "research"
if str(_PR) not in sys.path:
    sys.path.insert(0, str(_PR))

import _build_spider_html as m  # noqa: E402

_DAILY_MD = """\
---
edition: daily
title: RV Capital — Daily Macro Pulse
---

# RV CAPITAL · RATES & FX DESK · DAILY MACRO PULSE
# A thesis title for the day

*A one-line deck.*

**23 July 2026 · 08:00 SGT CUT**

> **Bottom line.** Two sentences.

## Hero band — the day's decisive prints

| A | B |
|---|---|
| **1** | **2** |
| desc a | desc b |

## What moved — and did price agree

- Something happened.

## THE DAY IN CHARTS

- Chart 1 — a chart.

## SELECTIVE DEEP-DIVE

## North America — a block

Body text.

## AUDIT APPENDIX *(internal — not in the client PDF)*

### Editorial method

- Grounding tags.

### Sell-side source register (report_ids)

| Cluster | Report IDs |
|---|---|
| US | 12345 (BNP) |
"""

_WEEKLY_MD = """\
---
edition: weekly
title: RV Capital — Weekly Cross-Bank Synthesis
---

# RV CAPITAL · RATES & FX · WEEKLY CROSS-BANK SYNTHESIS
# The week the hawks took the mic

### A tight one-line deck for the week

**Window: 14-20 Jul · Compiled 21 Jul**

## Universe hero stat band

| v | t | d |
|---|---|---|
| 4.15% | US 2y | rose on oil |

# TIER 2 — Per-country deep sections

## United States — the FOMC set-up

Body.

# TIER 3 — Universe appendices

## Appendix table

| a | b |
|---|---|
| 1 | 2 |
"""


def test_daily_appendix_wrapped_and_hidden_in_print():
    html = m.build(_DAILY_MD)
    assert html.count('<div class="daily-appendix">') == 1
    assert "@media print{ .daily-appendix{ display:none !important; } }" in html
    idx_wrapper = html.index('<div class="daily-appendix">')
    idx_appendix = html.index("AUDIT APPENDIX")
    assert idx_wrapper < idx_appendix


def test_daily_non_appendix_sections_render_outside_wrapper():
    html = m.build(_DAILY_MD)
    idx_wrapper = html.index('<div class="daily-appendix">')
    for label in ("THE DAY IN CHARTS", "SELECTIVE DEEP-DIVE", "North America"):
        assert html.index(label) < idx_wrapper


def test_daily_masthead_and_body_intact():
    html = m.build(_DAILY_MD)
    assert "<h1>A thesis title for the day</h1>" in html
    assert "Bottom line" in html
    assert "What moved" in html


def test_weekly_path_has_no_appendix_wrapper():
    html = m.build(_WEEKLY_MD)
    assert '<div class="daily-appendix">' not in html
    assert "<h1>The week the hawks took the mic</h1>" in html
    assert html.count('class="tier"') == 2


def test_daily_hero_band_renders_as_four_tiles():
    html = m.build(_DAILY_MD)
    assert html.count('<div class="tile">') == 2
    assert '<div class="v"><strong>1</strong></div>' in html
    assert '<div class="t">A</div>' in html
    assert '<div class="d">desc a</div>' in html
    assert '<div class="v"><strong>2</strong></div>' in html
    assert '<div class="t">B</div>' in html
    assert '<div class="d">desc b</div>' in html


def test_weekly_hero_band_still_row_oriented():
    html = m.build(_WEEKLY_MD)
    assert html.count('<div class="tile">') == 1
    assert '<div class="v">4.15%</div>' in html
    assert '<div class="t">US 2y</div>' in html
    assert '<div class="d">rose on oil</div>' in html


# --------------------------------------------------- weekly Tier-3 print-hide + contents
# Locks down the weekly render reaching parity with the daily: the `# TIER 3` audit
# appendix renders in the HTML but is hidden under `@media print` (the printed weekly
# ends at the Tier-2 country sections), plus a clickable contents page with resolving
# anchors, all gated so the daily HTML is untouched.

def test_weekly_tier3_wrapped_and_print_hidden():
    html = m.build(_WEEKLY_MD)
    assert html.count('<div class="weekly-appendix">') == 1
    assert "@media print{ .weekly-appendix{ display:none !important; } }" in html
    # the TIER 3 band + its content sit INSIDE the print-hidden wrapper
    idx_wrapper = html.index('<div class="weekly-appendix">')
    idx_tier3 = html.index("Universe appendices")
    idx_appendix_tbl = html.index("Appendix table")
    assert idx_wrapper < idx_tier3 < idx_appendix_tbl


def test_weekly_tier2_country_prints_outside_wrapper():
    html = m.build(_WEEKLY_MD)
    idx_wrapper = html.index('<div class="weekly-appendix">')
    # the Tier-2 country chapter prints (comes before the appendix wrapper)
    assert html.index("United States") < idx_wrapper


def test_weekly_contents_page_present_and_anchors_resolve():
    import re
    html = m.build(_WEEKLY_MD)
    assert '<nav class="toc">' in html
    # contents sits after the masthead, before the first tier band
    assert html.index('<nav class="toc">') < html.index('<div class="tier"')
    hrefs = set(re.findall(r'href="#([^"]+)"', html))
    ids = set(re.findall(r'id="([^"]+)"', html))
    assert hrefs, "contents page produced no links"
    assert hrefs <= ids, f"unresolved contents anchors: {sorted(hrefs - ids)}"
    # hero + the one country are linked
    assert "toc-hero" in hrefs
    assert "toc-c1" in hrefs


def test_weekly_tier3_subsection_absent_from_contents():
    import re
    html = m.build(_WEEKLY_MD)
    nav = re.search(r'<nav class="toc">.*?</nav>', html, re.S).group(0)
    # the Tier-3 `## Appendix table` must not appear as a contents entry
    assert "Appendix table" not in nav


def test_daily_gets_no_weekly_extra_css_or_contents():
    daily = m.build(_DAILY_MD)
    assert '<div class="weekly-appendix">' not in daily
    assert '<nav class="toc">' not in daily
    assert ".weekly-appendix" not in daily  # the weekly-only CSS block is not appended
    weekly = m.build(_WEEKLY_MD)
    assert ".weekly-appendix" in weekly


def test_derive_client_pdf_name():
    import pathlib
    import _html_to_pdf as pdf  # noqa: E402  (same playground/research dir, on sys.path)
    d = pdf.derive_client_pdf_name(
        pathlib.Path("data/research_summary/daily/2026/07/02/spider-daily-digest.html"))
    assert d is not None and d.name == "rvc-daily-digest-20260702.pdf"
    w = pdf.derive_client_pdf_name(
        pathlib.Path("data/research_summary/weekly/2026/07/27/spider-weekly-digest.html"))
    assert w is not None and w.name == "rvc-weekly-digest-20260727.pdf"
    # an unrecognised (non-dated / non-edition) folder falls back to None
    assert pdf.derive_client_pdf_name(pathlib.Path("some/place/x.html")) is None


# ------------------------------------------------------- section-number "§" glyph
# The house style bars the "§" glyph from the output. It is authored into some
# weekly Tier-1 section titles ("## §8 — This week…") as a manual section number
# that duplicates the builder's own numbered badge; the weekly path strips that
# leading "§N —" prefix. The daily's in-prose "§4" / "§4.D" cross-references are
# content and are left untouched.
_SECN = "§"  # §

_WEEKLY_SECN_MD = f"""\
---
edition: weekly
---
# RV CAPITAL · WEEKLY
# A weekly title

## {_SECN}8 — This week: estimates & where the desks split

Body one.

## {_SECN}9 — The week ahead: preview

Body two.

# TIER 2 — Per-country deep sections

## JAPAN — a read

Country body.
"""

_DAILY_GLYPH_MD = f"""\
---
edition: daily
---
# RV CAPITAL · DAILY
# A daily title

## 1. A section

See {_SECN}4 for detail; the cross-view count ({_SECN}4.D) held.
"""


def test_weekly_strips_section_number_glyph():
    html = m.build(_WEEKLY_SECN_MD)
    assert _SECN not in html  # zero "§" anywhere in the weekly output
    # badge numbering stays coherent; the redundant "§N —" prefix is gone
    assert '<span class="n">01</span>This week: estimates' in html
    assert '<span class="n">02</span>The week ahead: preview' in html
    # the contents page mirrors the cleaned titles + anchors them
    assert '<span class="tt">This week: estimates' in html
    assert '<span class="tt">The week ahead: preview' in html


def test_daily_prose_section_glyph_preserved():
    html = m.build(_DAILY_GLYPH_MD)
    # the weekly strip is scoped to weekly section titles; daily prose is verbatim
    assert f"{_SECN}4" in html
    assert f"{_SECN}4.D" in html


# ---------------------------------------------- price-level line: tight axis floor
# A price-LEVEL line (FX / index / oil / bond price) sits in a thin band far above
# zero; a 0-floor compresses it into a flat line. Such series get editorial NON-ZERO
# bounds. Rates / percentages (< ~20) and bars keep the zero baseline. An explicit
# `"baseline"` on the spec overrides the heuristic.

def _yticks(svg: str) -> list[str]:
    import re
    return re.findall(r'text-anchor="end" fill="#8a8578">([-\d.]+)</text>', svg)


def test_axis_bounds_tight_level_line_uses_nonzero_floor():
    vmin, vmax = m._axis_bounds([163.8, 161.2, 159.4, 158.6], tight=True)
    assert vmin > 100.0                 # hugs the 158–164 band, not floored at 0
    assert vmin <= 158.6 and vmax >= 163.8


def test_axis_bounds_tight_false_keeps_zero_floor():
    assert m._axis_bounds([4.75, 5.75, 5.5], tight=False)[0] == 0.0


def test_svg_level_line_auto_tightens_and_drops_zero_tick():
    svg = m._svg_chart({"type": "line", "title": "USDJPY", "series": [
        {"name": "USDJPY", "points": [["a", 163.8], ["b", 159.4], ["c", 158.6]]}]})
    assert "0" not in _yticks(svg)      # no zero baseline for a level line


def test_svg_rate_line_keeps_zero_baseline():
    svg = m._svg_chart({"type": "line", "title": "THOR", "series": [
        {"name": "THOR", "points": [["a", 1.98], ["b", 1.55], ["c", 1.70]]}]})
    assert "0" in _yticks(svg)          # sub-20 rate line retains the zero baseline


def test_svg_bar_never_tightens():
    svg = m._svg_chart({"type": "bar", "title": "levels", "series": [
        {"name": "x", "points": [["a", 158.0], ["b", 164.0]]}]})
    assert "0" in _yticks(svg)          # bars always keep the zero baseline


def test_svg_baseline_override_forces_tight_on_sub20_line():
    svg = m._svg_chart({"type": "line", "baseline": "tight", "title": "x", "series": [
        {"name": "x", "points": [["a", 5.75], ["b", 4.75]]}]})
    assert "0" not in _yticks(svg)      # explicit override tightens even a <20 series


# --------------------------------------------------------------- y-axis scaling
# Locks down the fix for the chart auto-scaler manufacturing a negative floor
# on non-negative data (e.g. a credit-spread bar chart rendering -21.44 to
# 289.44 for values [78, 96, 157, 268], or a WTI line chart rendering -6.88 to
# 92.88 for values ~[80..92]). All-non-negative series must floor at 0;
# series with real negatives must keep the zero baseline visible.

def test_axis_bounds_all_nonnegative_bar_series_floors_at_zero():
    vmin, vmax = m._axis_bounds([78.0, 96.0, 157.0, 268.0])
    assert vmin == 0.0
    assert vmax >= 268.0


def test_axis_bounds_all_nonnegative_line_series_floors_at_zero():
    vmin, vmax = m._axis_bounds([80.5, 84.2, 91.9])
    assert vmin == 0.0
    assert vmax >= 91.9


def test_axis_bounds_with_negatives_keeps_span_and_zero_visible():
    vmin, vmax = m._axis_bounds([-25.0, 8.0, -12.0, 3.0])
    assert vmin <= -25.0
    assert vmax >= 8.0
    assert vmin < 0.0 < vmax


def test_axis_bounds_all_negative_series_still_shows_zero_baseline():
    vmin, vmax = m._axis_bounds([-30.0, -10.0, -22.0])
    assert vmin <= -30.0
    assert vmax >= 0.0


def test_axis_bounds_snaps_to_nice_round_numbers():
    vmin, vmax = m._axis_bounds([78.0, 96.0, 157.0, 268.0])
    assert vmin == 0.0
    assert vmax == 300.0


def test_nice_num_rounds_to_clean_1_2_5_step():
    assert m._nice_num(70.8, round_=True) == 100.0
    assert m._nice_num(23.24, round_=True) == 20.0
    assert m._nice_num(0.0, round_=True) == 0.0


# ------------------------------------------- daily hero band: row-per-tile fallback
# The 01 and 02 Sep 2026 editions authored the daily hero band in the WEEKLY
# row-per-tile shape, whose header row is empty (`| | | |`). Read as the
# column-oriented daily layout, that silently produced garbage: tiles with BLANK
# titles, each row cell promoted into its own tile's big-value slot, and every
# row past the second dropped. Both editions rendered 3 scrambled tiles from a
# 6-row table. The renderer now detects the SHAPE rather than trusting the
# edition flag, and warns because the MD is non-conforming.

_DAILY_ROW_HERO_MD = """\
---
edition: daily
title: RV Capital — Daily Macro Pulse
---

# RV CAPITAL · RATES & FX DESK · DAILY MACRO PULSE
# A thesis title for the day

*A one-line deck.*

**01 September 2026 · 08:00 SGT CUT**

## Hero band — the day's decisive numbers

| | | |
|---|---|---|
| **US 2y (Fri, cash)** | **+14bp** | Warsh · 10s2s 47→39 |
| **SOFR 30y (Mon)** | **+5.0bp** | shape flipped to steepening |
| **Payroll benchmark** | **−79K** | vs −911K prior · GS called up |

## What moved

Body text.
"""


def test_daily_row_oriented_hero_keeps_every_tile():
    """All three rows must survive — the old path dropped the third."""
    html = m.build(_DAILY_ROW_HERO_MD)
    assert html.count('<div class="tile">') == 3


def test_daily_row_oriented_hero_maps_label_value_caption():
    """Daily rows are `label | value | caption`.

    NOT the weekly band's `Number | What it is | Memory`, which leads with the
    value — mapping this through the weekly reader would swap title and value.
    """
    html = m.build(_DAILY_ROW_HERO_MD)
    assert '<div class="t"><strong>US 2y (Fri, cash)</strong></div>' in html
    assert '<div class="v"><strong>+14bp</strong></div>' in html
    assert '<div class="d">Warsh · 10s2s 47→39</div>' in html
    assert '<div class="t"><strong>Payroll benchmark</strong></div>' in html
    assert '<div class="v"><strong>−79K</strong></div>' in html


def test_daily_row_oriented_hero_has_no_blank_titles():
    """The visible symptom of the bug: every tile title rendered empty."""
    html = m.build(_DAILY_ROW_HERO_MD)
    assert '<div class="t"></div>' not in html


def test_daily_row_oriented_hero_warns(capsys):
    """Picasso owns layout, never wording — so the MD itself is Spider's fix."""
    m.build(_DAILY_ROW_HERO_MD)
    err = capsys.readouterr().err
    assert "row-per-tile" in err
    assert "spider_daily_spec.md" in err


def test_conforming_daily_hero_does_not_warn(capsys):
    m.build(_DAILY_MD)
    assert "row-per-tile" not in capsys.readouterr().err


def test_dash_grid_class_tracks_tile_count():
    """A fixed 4-column grid leaves a hole when the band isn't 4 tiles."""
    assert 'class="dash n3"' in m.build(_DAILY_ROW_HERO_MD)
    assert 'class="dash n2"' in m.build(_DAILY_MD)
    assert 'class="dash n1"' in m.build(_WEEKLY_MD)


def test_dash_column_overrides_exist_for_off_default_counts():
    css = m.CSS
    for n in (1, 2, 3, 5, 6):
        assert f".dash.n{n}{{" in css.replace(" ", "")


# ------------------------------------------------------- print-break hygiene (orphans)
# The 09 Sep 2026 PDF stranded a repeated `DEBATE` table header plus one sliver
# row alone on page 10, and a single 115-char sentence on page 31; the 08 Sep
# edition left 522 chars on p8. Tables must still be allowed to split — the PM
# dashboard is taller than an A4 page — but not to strand a header or straddle a
# row.

def test_tables_may_still_split_across_pages():
    """`break-inside:avoid` on a page-taller table would overflow the sheet."""
    assert "break-inside:auto" in m.CSS


def test_table_header_and_rows_are_break_protected():
    css = m.CSS.replace(" ", "")
    assert "thead{break-after:avoid;break-inside:avoid;}" in css
    assert "tr{break-inside:avoid;}" in css


def test_prose_has_orphan_and_widow_control():
    css = m.CSS.replace(" ", "")
    assert "orphans:2" in css
    assert "widows:2" in css
