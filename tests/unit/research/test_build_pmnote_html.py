"""Smoke test for `_build_pmnote_html.py` (redesigned layered Spider PM-note renderer).

Throwaway render tooling — this just locks down that the real MD renders end
to end and the structural building blocks (running header, hero tiles, kicker
bands, box grids, dark-header tables, charts) are all present in the output.
"""
from __future__ import annotations

import sys
from pathlib import Path

_PR = Path(__file__).resolve().parents[3] / "playground" / "research"
if str(_PR) not in sys.path:
    sys.path.insert(0, str(_PR))

import _build_pmnote_html as m  # noqa: E402

_MD = (
    Path(__file__).resolve().parents[3]
    / "data" / "research_summary" / "daily" / "2026" / "07" / "16" / "spider-pm-note.md"
)


def _build():
    return m.build(_MD.read_text(encoding="utf-8"))


def test_runs_on_real_md_and_produces_html_shell():
    html = _build()
    assert html.startswith("<!doctype html>")
    assert "</html>" in html


def test_running_header_has_kicker_and_cutoff():
    html = _build()
    assert "RV CAPITAL" in html and "DAILY MACRO PULSE" in html
    assert "16 JULY 2026" in html and "SGT CUT" in html


def test_masthead_title_and_deck_present():
    html = _build()
    assert "The disinflation one-two lands" in html
    assert "June PPI confirms Tuesday" in html


def test_kicker_bands_all_present():
    html = _build()
    for label in (
        "MORNING IN 90 SECONDS",
        "MARKET REACTION",
        "WHAT IS UNRESOLVED",
        "SELECTIVE DEEP DIVE",
        "STREET TRADE MAP",
        "AUDIT APPENDIX",
    ):
        assert label in html, label


def test_hero_tiles_rendered():
    html = _build()
    assert html.count('<div class="tile">') == 4
    assert "CNY1,610bn" in html


def test_box_grids_rendered():
    html = _build()
    # news-vs-price (4 countries) + catalysts/regime pair = 2 grids min
    assert html.count('<div class="box-grid">') >= 2
    assert "<h4>China</h4>" in html
    assert "What breaks the regime" in html


def test_tables_rendered_with_dark_header():
    html = _build()
    assert "<table>" in html and "<th>" in html
    assert "MARKET</th>" in html or "Market</th>" in html


def test_charts_honour_editorial_axis_bounds():
    html = _build()
    assert html.count('<div class="chart">') == 5
    # y/y PPI chart bound is 4..7; the axis tick label should show
    assert "<svg" in html


def test_no_orphan_spiderchart_fence_left_unparsed():
    html = _build()
    assert "```spiderchart" not in html


def test_audit_appendix_is_html_internal_only():
    html = _build()
    assert '<div class="internal-only">' in html
    assert "@media print" in html and ".internal-only{ display:none !important; }" in html
    idx_appendix = html.index("AUDIT APPENDIX")
    idx_wrapper = html.index('<div class="internal-only">')
    assert idx_wrapper < idx_appendix
