"""Tests for scripts/econ/kr/kr_weekly.py + kr_monthly.py orchestrators.

Verifies:
- Every command in PIPELINES is a valid `python -m scripts.econ.…` invocation.
- Weekly bucket holds REB + KOSIS REB-mirror only (the 8 weekly indicators).
- Monthly bucket holds the other 19 KOSIS fetchers exactly once each.
- No overlap between weekly and monthly buckets.
- main() returns 0 when every subprocess exits 0, 1 when any fails.

Subprocesses are stubbed -- we never actually launch a fetcher.
"""

from __future__ import annotations

import subprocess
import sys

from scripts.econ.kr import kr_monthly, kr_weekly


def _modules_in(pipelines: list[list[str]]) -> list[str]:
    """Extract the module dotted path each entry runs."""
    out = []
    for cmd in pipelines:
        # Shape is [<python>, "-m", "scripts.econ.…", *extra_args]
        assert cmd[1] == "-m", f"unexpected pipeline shape: {cmd!r}"
        out.append(cmd[2])
    return out


class TestPipelineShapes:
    def test_kr_weekly_uses_module_invocation_and_current_python(self) -> None:
        for cmd in kr_weekly.PIPELINES:
            assert cmd[0] == sys.executable
            assert cmd[1] == "-m"
            assert cmd[2].startswith("scripts.econ.")

    def test_kr_monthly_uses_module_invocation_and_current_python(self) -> None:
        for cmd in kr_monthly.PIPELINES:
            assert cmd[0] == sys.executable
            assert cmd[1] == "-m"
            assert cmd[2].startswith("scripts.econ.")


class TestPipelineMembership:
    def test_kr_weekly_contains_only_weekly_fetchers(self) -> None:
        # WEEKLY cadence (per dim_indicator.frequency_code): REB direct (4
        # series) + KOSIS REB mirror (4 series). Exactly two fetchers.
        modules = _modules_in(kr_weekly.PIPELINES)
        assert set(modules) == {
            "scripts.econ.kr.reb.reb_housing",
            "scripts.econ.kr.kosis.kosis_reb_housing",
        }

    def test_kr_monthly_contains_all_non_weekly_fetchers(self) -> None:
        expected = {
            # BOK Base Rate via BIS CBPOL (added after this test was written).
            "scripts.econ.kr.bis.bis_korea",
            "scripts.econ.kr.kosis.kosis_balance_sheets",
            "scripts.econ.kr.kosis.kosis_bank_rates",
            "scripts.econ.kr.kosis.kosis_bop",
            "scripts.econ.kr.kosis.kosis_bsi",
            "scripts.econ.kr.kosis.kosis_consumer_survey",
            "scripts.econ.kr.kosis.kosis_corp_debt",
            "scripts.econ.kr.kosis.kosis_cpi",
            "scripts.econ.kr.kosis.kosis_fiscal",
            "scripts.econ.kr.kosis.kosis_gdp",
            "scripts.econ.kr.kosis.kosis_industrial",
            "scripts.econ.kr.kosis.kosis_labour",
            "scripts.econ.kr.kosis.kosis_lending",
            "scripts.econ.kr.kosis.kosis_money_aggregates",
            "scripts.econ.kr.kosis.kosis_ppi",
            "scripts.econ.kr.kosis.kosis_retail",
            "scripts.econ.kr.kosis.kosis_tot",
            "scripts.econ.kr.kosis.kosis_trade_indices",
            "scripts.econ.kr.kosis.kosis_trade_prices",
            "scripts.econ.kr.kosis.kosis_wages",
        }
        assert set(_modules_in(kr_monthly.PIPELINES)) == expected

    def test_buckets_do_not_overlap(self) -> None:
        weekly = set(_modules_in(kr_weekly.PIPELINES))
        monthly = set(_modules_in(kr_monthly.PIPELINES))
        assert weekly.isdisjoint(monthly)

    def test_kr_monthly_has_no_duplicate_modules(self) -> None:
        modules = _modules_in(kr_monthly.PIPELINES)
        assert len(modules) == len(set(modules))


class TestMainReturnCodes:
    def test_kr_weekly_returns_0_when_all_subprocesses_succeed(self, monkeypatch) -> None:
        monkeypatch.setattr(subprocess, "call", lambda *a, **kw: 0)
        assert kr_weekly.main() == 0

    def test_kr_weekly_returns_1_when_any_subprocess_fails(self, monkeypatch) -> None:
        calls = {"n": 0}

        def stub(*a, **kw):
            calls["n"] += 1
            return 2 if calls["n"] == 1 else 0  # first one fails

        monkeypatch.setattr(subprocess, "call", stub)
        assert kr_weekly.main() == 1
        # Still ran all of them (no early exit).
        assert calls["n"] == len(kr_weekly.PIPELINES)

    def test_kr_monthly_returns_0_when_all_subprocesses_succeed(self, monkeypatch) -> None:
        monkeypatch.setattr(subprocess, "call", lambda *a, **kw: 0)
        assert kr_monthly.main() == 0

    def test_kr_monthly_returns_1_when_any_subprocess_fails(self, monkeypatch) -> None:
        calls = {"n": 0}

        def stub(*a, **kw):
            calls["n"] += 1
            return 5 if calls["n"] == 3 else 0  # third one fails

        monkeypatch.setattr(subprocess, "call", stub)
        assert kr_monthly.main() == 1
        assert calls["n"] == len(kr_monthly.PIPELINES)
