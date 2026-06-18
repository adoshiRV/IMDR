"""Offline test for scripts/econ/kr/bis/bis_korea.py.

Fills the BOK Base Rate coverage gap (FRED discount-rate proxy id 388 was
stuck at 1.0%). We monkeypatch bis_fetch_series so run_fetch runs offline.
Covered:

- run_fetch returns (indicators, observations) of the expected shapes.
- The single emitted indicator carries the BIS.POLICY_RATE.KR dim contract
  (vendor BIS / country KR / category rates / DAILY / pct).
- since/until filters drop rows outside the window.
- Every observation references the emitted indicator (no orphan facts).
- A None value in the source series is preserved as None.
"""

from __future__ import annotations

import datetime

import pytest

import scripts.econ.kr.bis.bis_korea as kr_mod


def _patched_series(*_args, **_kwargs) -> list[tuple[str, float | None]]:
    """Synthetic BIS CBPOL D.KR payload: 4 daily points + one None."""
    return [
        ("2026-06-01", 2.5),
        ("2026-06-02", 2.5),
        ("2026-06-03", None),
        ("2026-06-04", 2.5),
    ]


@pytest.fixture(autouse=True)
def _stub_bis(monkeypatch):
    monkeypatch.setattr(kr_mod, "bis_fetch_series", _patched_series)


class TestBisKoreaRunFetch:
    def test_returns_indicators_and_observations(self) -> None:
        indicators, observations = kr_mod.run_fetch(None, None)
        assert len(indicators) == 1
        assert len(observations) == 4

    def test_indicator_has_kr_policy_rate_contract(self) -> None:
        (ind,), _ = kr_mod.run_fetch(None, None)
        assert ind.imdr_code == "BIS.POLICY_RATE.KR"
        assert ind.vendor_name == "BIS"
        assert ind.source_code == "BIS/WS_CBPOL/1.0/D.KR"
        assert ind.country_iso == "KR"
        assert ind.category == "rates"
        assert ind.frequency == "DAILY"
        assert ind.unit == "pct"
        assert ind.is_seasonally_adjusted is False

    def test_observations_reference_the_emitted_indicator(self) -> None:
        indicators, observations = kr_mod.run_fetch(None, None)
        emitted = {r.imdr_code for r in indicators}
        for o in observations:
            assert o.imdr_code in emitted

    def test_since_filter_drops_earlier_dates(self) -> None:
        _, observations = kr_mod.run_fetch(since="2026-06-03", until=None)
        for o in observations:
            assert o.obs_date >= datetime.date(2026, 6, 3)
        assert len(observations) == 2

    def test_until_filter_drops_later_dates(self) -> None:
        _, observations = kr_mod.run_fetch(since=None, until="2026-06-02")
        for o in observations:
            assert o.obs_date <= datetime.date(2026, 6, 2)
        assert len(observations) == 2

    def test_none_value_is_preserved(self) -> None:
        _, observations = kr_mod.run_fetch(None, None)
        none_rows = [o for o in observations
                     if o.obs_date == datetime.date(2026, 6, 3)]
        assert len(none_rows) == 1
        assert none_rows[0].value is None
