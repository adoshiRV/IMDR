"""Smoke test for scripts/econ/kosis/kosis_cpi.py.

CPI is the representative KOSIS fetcher -- 5 cuts x 3 items = 15 indicators,
the largest topic by series count. If its `run_fetch` shape is right, the
other 19 follow the same template.

We monkeypatch fetch_kosis_table to return a tiny synthetic payload so
the test runs offline. Covered:

- run_fetch returns (indicators, observations) of the expected shapes.
- Every emitted indicator has imdr_code prefix 'KOSTAT.CPI.' and country
  'KR' / category 'cpi' / frequency 'MONTHLY' (the dim contract).
- since/until filters drop rows outside the window.
- The (C1, ITM_ID) pairs with no rows do NOT emit a dangling indicator
  (the empty-indicator pop logic in run_fetch).
- Every observation references an emitted indicator (no orphan facts).
"""

from __future__ import annotations

import datetime

import pytest

import scripts.econ.kosis.kosis_cpi as cpi_mod


def _fake_kosis_row(c1: str, itm_id: str, prd_de: str, value: str) -> dict:
    return {"C1": c1, "ITM_ID": itm_id, "PRD_DE": prd_de, "DT": value}


def _patched_fetch(*_args, **_kwargs) -> list[dict]:
    """Synthetic KOSIS payload covering 3 cuts x 2 items x 2 months."""
    rows: list[dict] = []
    # cuts that exist: 0 (HEADLINE), 1 (LIVING), 4 (EXFOOD_NRG)
    # items that exist: T02 (MOM), T03 (YOY)
    # months: 202601, 202602
    for c1 in ("0", "1", "4"):
        for itm in ("T02", "T03"):
            for prd_de, v in (("202601", "0.5"), ("202602", "0.7")):
                rows.append(_fake_kosis_row(c1, itm, prd_de, v))
    # Add a malformed PRD_DE row to confirm it gets skipped.
    rows.append(_fake_kosis_row("0", "T02", "BAD", "9.9"))
    # Add a row with empty DT to confirm value parses to None.
    rows.append(_fake_kosis_row("0", "T03", "202603", ""))
    return rows


@pytest.fixture(autouse=True)
def _stub_kosis(monkeypatch):
    monkeypatch.setattr(cpi_mod, "fetch_kosis_table", _patched_fetch)
    monkeypatch.setattr(cpi_mod, "make_session", lambda: None)


class TestKosisCpiRunFetch:
    def test_returns_indicators_and_observations(self) -> None:
        indicators, observations = cpi_mod.run_fetch(None, None)
        assert len(indicators) > 0
        assert len(observations) > 0

    def test_only_emits_indicators_for_present_cut_item_crosses(self) -> None:
        # _patched_fetch supplies 3 cuts * 2 items = 6 series with data.
        # The 5*3 = 15 nominal combos shrink to 6 emitted indicators.
        indicators, _ = cpi_mod.run_fetch(None, None)
        assert len(indicators) == 6

    def test_every_indicator_has_kr_cpi_contract(self) -> None:
        indicators, _ = cpi_mod.run_fetch(None, None)
        for row in indicators:
            assert row.imdr_code.startswith("KOSTAT.CPI.")
            assert row.country_iso == "KR"
            assert row.category == "cpi"
            assert row.frequency == "MONTHLY"
            assert row.vendor_name == "KOSIS"
            assert row.unit == "pct"

    def test_observations_reference_an_emitted_indicator(self) -> None:
        indicators, observations = cpi_mod.run_fetch(None, None)
        emitted_codes = {r.imdr_code for r in indicators}
        for o in observations:
            assert o.imdr_code in emitted_codes, \
                f"orphan observation: {o.imdr_code} has no dim row"

    def test_since_filter_drops_earlier_dates(self) -> None:
        _, observations = cpi_mod.run_fetch(since="2026-02-01", until=None)
        for o in observations:
            assert o.obs_date >= datetime.date(2026, 2, 1)

    def test_until_filter_drops_later_dates(self) -> None:
        _, observations = cpi_mod.run_fetch(since=None, until="2026-01-31")
        for o in observations:
            assert o.obs_date <= datetime.date(2026, 1, 31)

    def test_empty_dt_parses_to_none(self) -> None:
        # _patched_fetch includes one row with DT="" for (C1=0, ITM=T03, 202603).
        _, observations = cpi_mod.run_fetch(None, None)
        none_rows = [o for o in observations
                     if o.imdr_code == "KOSTAT.CPI.HEADLINE.YOY.KR"
                     and o.obs_date == datetime.date(2026, 3, 1)]
        assert len(none_rows) == 1
        assert none_rows[0].value is None

    def test_malformed_prd_de_is_skipped(self) -> None:
        # _patched_fetch includes PRD_DE='BAD' which parse_kosis_period returns
        # None for -- no observation should be emitted for it.
        _, observations = cpi_mod.run_fetch(None, None)
        # Bad row would have been imdr_code KOSTAT.CPI.HEADLINE.MOM.KR with a
        # date that can't exist; no obs should reference an out-of-grid date.
        valid_months = {datetime.date(2026, 1, 1),
                        datetime.date(2026, 2, 1),
                        datetime.date(2026, 3, 1)}
        for o in observations:
            assert o.obs_date in valid_months
