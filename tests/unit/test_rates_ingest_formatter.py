"""Tests for the RatesIngestFormatter — focused on latest-day coverage.

The window-level coverage check can't see a curve that returned rows but
is missing the *target* trading day, so the formatter grew a "behind"
signal (subject suffix + CURVES BEHIND section). These tests pin that
behaviour and, critically, that it stays inert when no runner populates
it — so the shared formatter's other callers are unchanged.
"""

from __future__ import annotations

from datetime import datetime, timezone

from imdr.notifications.formatters.rates_ingest import RatesIngestFormatter


def _rd() -> datetime:
    return datetime(2026, 7, 8, tzinfo=timezone.utc)


CURVES = [
    {"ccy": "AUD", "curve": "3S6S_BASIS", "classification": "G10",
     "status": "active", "tenors": 19, "rows": 114},
]


class TestSubjectBehind:
    def test_behind_appended_when_present(self) -> None:
        f = RatesIngestFormatter()
        subj = f.format_subject(run_date=_rd(), rows_loaded=693,
                                has_errors=False, mode="Basis Daily", n_behind=1)
        assert subj.endswith("| 1 behind")
        assert "OK" in subj

    def test_no_behind_suffix_by_default(self) -> None:
        f = RatesIngestFormatter()
        subj = f.format_subject(run_date=_rd(), rows_loaded=693,
                                has_errors=False, mode="Basis Daily")
        assert "behind" not in subj

    def test_error_takes_precedence_over_behind(self) -> None:
        """A hard error stays ERROR and does not also advertise 'behind'."""
        f = RatesIngestFormatter()
        subj = f.format_subject(run_date=_rd(), rows_loaded=0,
                                has_errors=True, mode="Basis Daily", n_behind=2)
        assert "ERROR" in subj
        assert "behind" not in subj


class TestBodyBehindSection:
    def test_section_rendered_when_populated(self) -> None:
        f = RatesIngestFormatter()
        body = f.format_body(
            run_date=_rd(), rows_loaded=693, n_curves=5, curves=CURVES,
            behind_curves=[{"ccy": "AUD", "curve": "3S6S_BASIS",
                            "latest": "2026-07-07", "days_behind": 1}],
        )
        assert "CURVES BEHIND (1)" in body
        assert "3S6S_BASIS" in body
        assert "2026-07-07" in body
        # The green all-clear must be replaced by the amber caveat.
        assert "is behind the target day" in body
        assert "All 5 curves produced observations." not in body

    def test_section_absent_by_default(self) -> None:
        """No behind_curves (e.g. other rates runners) => no section, green note."""
        f = RatesIngestFormatter()
        body = f.format_body(run_date=_rd(), rows_loaded=693, n_curves=5, curves=CURVES)
        assert "CURVES BEHIND" not in body
        assert "All 5 curves produced observations." in body
