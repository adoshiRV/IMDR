"""Tests for scripts/econ/kr/ksd/ksd_cd_issuance.py.

Network-free -- imdr.domains.econ.datagokr_http.fetch_datagokr_rows is mocked.
Covers the load-bearing semantics of this fetcher:
- dedup by isinCd for the FLOW aggregation
- FLOW grouped by codpIssuDt (volume / count / amount-weighted avg rate)
- STOCK (outstanding) summed per basDt with NO dedup (repetition IS the stock)
- live-mode basDt probing (skips empty snapshots, e.g. weekends)
- empty-key dormant path
"""

from __future__ import annotations

import datetime
from unittest.mock import patch

import pytest

from scripts.econ.kr.ksd.ksd_cd_issuance import (
    _dedup_by_isin,
    _flow_by_issue_date,
    _flow_observations,
    _stock_by_bas_dt,
    _stock_observations,
    run_fetch,
)

UTC = datetime.timezone.utc
_NOW = datetime.datetime(2026, 8, 4, tzinfo=UTC)


def _row(isin: str, bas_dt: str, issue_dt: str, amt: str, rate: str) -> dict:
    return {
        "isinCd": isin,
        "basDt": bas_dt,
        "codpIssuDt": issue_dt,
        "codpExprDt": "20260911",
        "codpIssuAmt": amt,
        "codpDcRat": rate,
    }


# ---------------------------------------------------------------------------
# _dedup_by_isin
# ---------------------------------------------------------------------------

class TestDedupByIsin:
    def test_keeps_one_row_per_isin_first_occurrence(self) -> None:
        rows = [
            _row("A", "20260801", "20260612", "1000", "1.5"),
            _row("A", "20260802", "20260612", "1000", "1.5"),
            _row("B", "20260801", "20260701", "2000", "1.6"),
        ]
        deduped = _dedup_by_isin(rows)
        assert set(deduped.keys()) == {"A", "B"}
        assert deduped["A"]["basDt"] == "20260801"

    def test_rows_missing_isin_are_skipped(self) -> None:
        rows = [{"basDt": "20260801"}, _row("A", "20260801", "20260612", "1000", "1.5")]
        deduped = _dedup_by_isin(rows)
        assert list(deduped.keys()) == ["A"]


# ---------------------------------------------------------------------------
# _flow_by_issue_date
# ---------------------------------------------------------------------------

class TestFlowByIssueDate:
    def test_groups_unique_isins_by_issue_date(self) -> None:
        isin_rows = {
            "A": _row("A", "20260801", "20260701", "1000", "1.5"),
            "B": _row("B", "20260801", "20260701", "2000", "1.6"),
            "C": _row("C", "20260801", "20260702", "3000", "1.7"),
        }
        grouped = _flow_by_issue_date(
            isin_rows, datetime.date(2026, 6, 1), datetime.date(2026, 8, 4),
        )
        assert set(grouped.keys()) == {datetime.date(2026, 7, 1), datetime.date(2026, 7, 2)}
        assert len(grouped[datetime.date(2026, 7, 1)]) == 2
        assert len(grouped[datetime.date(2026, 7, 2)]) == 1

    def test_issue_date_outside_window_excluded(self) -> None:
        isin_rows = {"A": _row("A", "20260801", "20260101", "1000", "1.5")}
        grouped = _flow_by_issue_date(
            isin_rows, datetime.date(2026, 6, 1), datetime.date(2026, 8, 4),
        )
        assert grouped == {}

    def test_missing_issue_date_excluded(self) -> None:
        isin_rows = {"A": {"isinCd": "A", "codpIssuAmt": "1000"}}
        grouped = _flow_by_issue_date(
            isin_rows, datetime.date(2026, 1, 1), datetime.date(2026, 8, 4),
        )
        assert grouped == {}


# ---------------------------------------------------------------------------
# _flow_observations — volume / count / amount-weighted avg rate
# ---------------------------------------------------------------------------

class TestFlowObservations:
    def test_volume_count_and_weighted_avg_rate(self) -> None:
        issue_dt = datetime.date(2026, 7, 1)
        grouped = {
            issue_dt: [
                _row("A", "20260801", "20260701", "100000000000", "1.0"),   # 100bn @ 1.0%
                _row("B", "20260801", "20260701", "300000000000", "2.0"),   # 300bn @ 2.0%
            ],
        }
        obs = _flow_observations(grouped, _NOW)
        by_code = {o.imdr_code: o for o in obs}

        assert by_code["KSD.CD.ISSUANCE.VOLUME.KR"].value == pytest.approx(400.0)  # krw_bn
        assert by_code["KSD.CD.ISSUANCE.COUNT.KR"].value == pytest.approx(2.0)
        # weighted avg = (100*1.0 + 300*2.0) / 400 = 700/400 = 1.75
        assert by_code["KSD.CD.ISSUANCE.AVG_RATE.KR"].value == pytest.approx(1.75)
        assert all(o.obs_date == issue_dt for o in obs)

    def test_missing_rate_excluded_from_weighted_average_but_amount_still_counted(self) -> None:
        issue_dt = datetime.date(2026, 7, 1)
        grouped = {
            issue_dt: [
                _row("A", "20260801", "20260701", "100000000000", "1.0"),
                {**_row("B", "20260801", "20260701", "100000000000", ""), "codpDcRat": None},
            ],
        }
        obs = _flow_observations(grouped, _NOW)
        by_code = {o.imdr_code: o for o in obs}
        assert by_code["KSD.CD.ISSUANCE.VOLUME.KR"].value == pytest.approx(200.0)
        assert by_code["KSD.CD.ISSUANCE.COUNT.KR"].value == pytest.approx(2.0)
        # weighted rate uses only the row with a rate: 100*1.0 / 200 total amt = 0.5
        assert by_code["KSD.CD.ISSUANCE.AVG_RATE.KR"].value == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# _stock_by_bas_dt / _stock_observations — STOCK, no dedup
# ---------------------------------------------------------------------------

class TestStockByBasDt:
    def test_sums_all_rows_for_a_snapshot_no_dedup(self) -> None:
        rows = [
            _row("A", "20260801", "20260612", "100000000000", "1.0"),
            _row("B", "20260801", "20260701", "50000000000", "1.2"),
        ]
        totals = _stock_by_bas_dt(rows, datetime.date(2026, 8, 1), datetime.date(2026, 8, 1))
        assert totals == {datetime.date(2026, 8, 1): 150000000000.0}

    def test_multiple_snapshots_kept_separate(self) -> None:
        rows = [
            _row("A", "20260801", "20260612", "100000000000", "1.0"),
            _row("A", "20260802", "20260612", "100000000000", "1.0"),  # same CD, next day
        ]
        totals = _stock_by_bas_dt(rows, datetime.date(2026, 8, 1), datetime.date(2026, 8, 2))
        assert totals == {
            datetime.date(2026, 8, 1): 100000000000.0,
            datetime.date(2026, 8, 2): 100000000000.0,
        }

    def test_outside_window_excluded(self) -> None:
        rows = [_row("A", "20260101", "20251201", "100000000000", "1.0")]
        totals = _stock_by_bas_dt(rows, datetime.date(2026, 8, 1), datetime.date(2026, 8, 2))
        assert totals == {}

    def test_stock_observations_converts_to_krw_bn(self) -> None:
        totals = {datetime.date(2026, 8, 1): 150_000_000_000.0}
        obs = _stock_observations(totals, _NOW)
        assert len(obs) == 1
        assert obs[0].imdr_code == "KSD.CD.OUTSTANDING.KR"
        assert obs[0].obs_date == datetime.date(2026, 8, 1)
        assert obs[0].value == pytest.approx(150.0)


# ---------------------------------------------------------------------------
# run_fetch — dormant path + live probing
# ---------------------------------------------------------------------------

class TestRunFetchDormant:
    def test_no_key_returns_empty(self, monkeypatch) -> None:
        monkeypatch.delenv("IMDR_KSD_API_KEY", raising=False)
        import scripts.econ.kr.ksd.ksd_cd_issuance as mod
        monkeypatch.setattr(mod, "_REPO_ROOT", mod._REPO_ROOT.parent / "___no_env_here___")
        indicators, observations = run_fetch(None, None)
        assert indicators == []
        assert observations == []


class TestRunFetchLiveProbing:
    def test_probes_back_through_empty_snapshots(self, monkeypatch) -> None:
        monkeypatch.setenv("IMDR_KSD_API_KEY", "testkey")
        import scripts.econ.kr.ksd.ksd_cd_issuance as mod

        until_dt = datetime.date(2026, 8, 3)  # probe starts here (empty), falls back one day
        calls: list[str] = []

        def fake_fetch(session, url, key, params, page_size=1000):
            calls.append(params["basDt"])
            if params["basDt"] == until_dt.strftime("%Y%m%d"):
                return []  # Sunday -- empty
            return [_row("A", params["basDt"], "20260701", "100000000000", "1.5")]

        monkeypatch.setattr(mod, "fetch_datagokr_rows", fake_fetch)
        monkeypatch.setattr(mod, "make_session", lambda: object())

        indicators, observations = run_fetch(None, until_dt.isoformat())

        assert len(calls) == 2  # 08-03 (empty) then 08-02 (found)
        assert calls[0] == "20260803"
        assert calls[1] == "20260802"
        codes = {o.imdr_code for o in observations}
        assert "KSD.CD.OUTSTANDING.KR" in codes
        assert "KSD.CD.ISSUANCE.VOLUME.KR" in codes

    def test_no_snapshot_found_within_probe_window_returns_indicators_only(self, monkeypatch) -> None:
        monkeypatch.setenv("IMDR_KSD_API_KEY", "testkey")
        import scripts.econ.kr.ksd.ksd_cd_issuance as mod

        monkeypatch.setattr(mod, "fetch_datagokr_rows", lambda *a, **k: [])
        monkeypatch.setattr(mod, "make_session", lambda: object())

        indicators, observations = run_fetch(None, "2026-08-03")
        assert len(indicators) == 4
        assert observations == []
