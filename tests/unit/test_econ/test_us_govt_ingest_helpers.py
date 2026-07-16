"""Unit tests for the US govt filings ingest helper functions.

No network / DB. Covers the pure helpers in
``scripts.econ.us.govt.ingest_filings``: window→cap scaling, the recent-years
cutoff, the probe→DocType map, and HTML body extraction.
"""

from __future__ import annotations

import datetime

from scripts.econ.us.govt.ingest_filings import (
    _scale_kwargs,
    _cutoff_date,
    _strip_html_body,
    _DOCTYPE_MAP,
)


class TestScaleKwargs:
    def test_daily_window_left_untouched(self) -> None:
        # years <= 1 is the daily fast-path — caps must not change.
        assert _scale_kwargs({"limit": 40}, years=1) == {"limit": 40}

    def test_limit_scales_up_for_multi_year(self) -> None:
        # 240/yr * 5yr = 1200, well above the daily-sized 40 default.
        assert _scale_kwargs({"limit": 40}, years=5)["limit"] == 1200

    def test_quarters_and_meetings_scale(self) -> None:
        assert _scale_kwargs({"quarters": 8}, years=20)["quarters"] == 80
        assert _scale_kwargs({"meetings": 8}, years=20)["meetings"] == 160

    def test_never_shrinks_below_default(self) -> None:
        # A large default with a small window keeps the larger of the two.
        assert _scale_kwargs({"limit": 500}, years=2)["limit"] == 500

    def test_non_count_kwargs_preserved(self) -> None:
        out = _scale_kwargs({"limit": 40, "save_raw_html": False}, years=3)
        assert out["save_raw_html"] is False

    def test_does_not_mutate_input(self) -> None:
        src = {"limit": 40}
        _scale_kwargs(src, years=5)
        assert src == {"limit": 40}


class TestCutoffDate:
    def test_subtracts_n_years(self) -> None:
        today = datetime.date.today()
        cutoff = _cutoff_date(2)
        assert cutoff.year == today.year - 2


class TestDocTypeMap:
    def test_known_probe_types_map_to_valid_doctypes(self) -> None:
        assert _DOCTYPE_MAP["decision"] == "decision"
        assert _DOCTYPE_MAP["minutes"] == "minutes"
        assert _DOCTYPE_MAP["projection"] == "report"   # SEP not a DocType
        assert _DOCTYPE_MAP["testimony"] == "speech"     # testimony is a speech
        assert _DOCTYPE_MAP["survey"] == "report"
        assert _DOCTYPE_MAP["refunding"] == "report"

    def test_unknown_type_falls_back_to_report(self) -> None:
        assert _DOCTYPE_MAP.get("something_new", "report") == "report"


class TestStripHtmlBody:
    def test_extracts_body_text_and_drops_script_style(self) -> None:
        html = (
            "<html><head><style>.x{color:red}</style></head>"
            "<body><nav>menu menu</nav>"
            "<main><p>Real content here.</p></main>"
            "<script>var x = 1;</script></body></html>"
        )
        text = _strip_html_body(html)
        assert "Real content here." in text
        assert "var x" not in text
        assert "color:red" not in text

    def test_empty_html_returns_empty_string(self) -> None:
        assert _strip_html_body("").strip() == ""
