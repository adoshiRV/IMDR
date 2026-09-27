"""Unit tests for scripts/econ/in/nsdl/fpi_flows.py::run_fetch.

No network / no Playwright / no live CDP-attach -- ``fetch_export_xls`` is
monkeypatched to return the real trimmed 2-day fixture
(tests/unit/test_econ/fixtures/nsdl_current_month_trimmed.xls) instead of
driving a live download. The Current Month export always contains at
least the days published so far this month, so the failure modes below
MUST raise loudly rather than return an empty (indicators, observations)
pair that would exit rc=0.
"""

from __future__ import annotations

import datetime
import importlib
from pathlib import Path

import pytest

# `scripts.econ.in.nsdl` can't be imported via a normal `from X.in.Y import`
# dotted statement because `in` is a Python reserved keyword -- use
# importlib.import_module instead (same pattern as
# test_in_govt_daily_pull.py / test_rbi_bulletin_parsers.py). The module is
# still ever invoked via `python -m scripts.econ.in.nsdl.fpi_flows`.
mod = importlib.import_module("scripts.econ.in.nsdl.fpi_flows")

_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "nsdl_current_month_trimmed.xls"


class TestRunFetchHappyPath:
    def test_returns_33_indicators_across_both_fixture_days(self, monkeypatch) -> None:
        monkeypatch.setattr(mod, "fetch_export_xls", lambda **kw: _FIXTURE)
        indicators, observations = mod.run_fetch(None, None)
        assert len(indicators) == 33
        assert len(observations) == 64 + 2  # 8 asset classes x 4 measures x 2 days + 2 conversion obs

        eq_net_usd_jul1 = next(
            o for o in observations
            if o.imdr_code == "INDIA.NSDL.FPI.EQUITY.NET.USD_MN.IN" and o.obs_date == datetime.date(2026, 7, 1)
        )
        assert eq_net_usd_jul1.value == -188.27

        aif_net_usd_jul1 = next(
            o for o in observations
            if o.imdr_code == "INDIA.NSDL.FPI.AIF.NET.USD_MN.IN" and o.obs_date == datetime.date(2026, 7, 1)
        )
        total_net_usd_jul1 = next(
            o for o in observations
            if o.imdr_code == "INDIA.NSDL.FPI.TOTAL.NET.USD_MN.IN" and o.obs_date == datetime.date(2026, 7, 1)
        )
        assert aif_net_usd_jul1.value == 0.0
        assert total_net_usd_jul1.value == 58.46

    def test_since_filter_keeps_only_matching_day(self, monkeypatch) -> None:
        monkeypatch.setattr(mod, "fetch_export_xls", lambda **kw: _FIXTURE)
        indicators, observations = mod.run_fetch("2026-07-02", None)
        obs_dates = {o.obs_date for o in observations}
        assert obs_dates == {datetime.date(2026, 7, 2)}

    def test_until_filter_keeps_only_matching_day(self, monkeypatch) -> None:
        monkeypatch.setattr(mod, "fetch_export_xls", lambda **kw: _FIXTURE)
        indicators, observations = mod.run_fetch(None, "2026-07-01")
        obs_dates = {o.obs_date for o in observations}
        assert obs_dates == {datetime.date(2026, 7, 1)}

    def test_since_until_outside_fixture_range_raises(self, monkeypatch) -> None:
        monkeypatch.setattr(mod, "fetch_export_xls", lambda **kw: _FIXTURE)
        with pytest.raises(RuntimeError, match="0 rows"):
            mod.run_fetch("2026-08-01", "2026-08-31")


class TestRunFetchFailureModesRaiseLoudly:
    """The MUST-FIX inherited from the prior DOM-scrape build: these must
    never return ([], []) silently."""

    def test_raises_when_export_has_fewer_than_2_tables(self, monkeypatch, tmp_path) -> None:
        bad_path = tmp_path / "single_table.xls"
        bad_path.write_text(
            "<html><body><table><tr><td>only one table</td></tr></table></body></html>",
            encoding="utf-8",
        )
        monkeypatch.setattr(mod, "fetch_export_xls", lambda **kw: bad_path)
        with pytest.raises(RuntimeError, match="Expected 2 tables"):
            mod.run_fetch(None, None)

    def test_raises_when_table_found_but_labels_dont_map(self, monkeypatch, tmp_path) -> None:
        # 2 tables present (so load_export_tables succeeds) but every
        # asset-class/route label in table 0 is unrecognised -- simulates
        # an NSDL relabel. Must raise, not silently return empty.
        relabelled = (
            "<html><body>"
            "<table><tr><td>01-Jul-2026</td><td>Equities</td><td>Grand Sub-Total</td>"
            "<td>1</td><td>2</td><td>3</td><td>4</td><td>Rs.95.0</td></tr></table>"
            "<table><tr><td>derivatives placeholder</td></tr></table>"
            "</body></html>"
        )
        bad_path = tmp_path / "relabelled.xls"
        bad_path.write_text(relabelled, encoding="utf-8")
        monkeypatch.setattr(mod, "fetch_export_xls", lambda **kw: bad_path)
        with pytest.raises(RuntimeError, match="0 rows resolved"):
            mod.run_fetch(None, None)

    def test_fetch_export_xls_cdp_attach_failure_raises(self, monkeypatch) -> None:
        def _boom(**kw):
            raise RuntimeError("Could not attach to Chrome via CDP")
        monkeypatch.setattr(mod, "fetch_export_xls", _boom)
        with pytest.raises(RuntimeError, match="Could not attach to Chrome"):
            mod.run_fetch(None, None)


class TestAllowEmptyDefault:
    def test_run_main_does_not_pass_allow_empty_true(self) -> None:
        # Regression guard: there is no genuine empty-period state on the
        # Current Month export, so `main()` must rely on run_main's default
        # (allow_empty=False), not opt in to allow_empty=True.
        import inspect

        src = inspect.getsource(mod.main)
        assert "allow_empty=True" not in src
