"""Tests for playground/econ/hkma/fetch.py parse layer.

No live API calls. Tests cover:
- _parse_value handles float, int, None, and non-numeric strings.
- _build_indicator produces valid IndicatorRow for each series key.
- run_fetch date filtering (since/until) on synthetic records.
- Pagination helper stops when fewer than PAGE_SIZE records returned.
- fetch_all_records correctly concatenates multiple pages.
- Endpoint routing: agg_bal uses interbank endpoint; mon_base/ci_out/efbn_out
  use monetary-base endpoint.
- Series filter limits which indicators are returned.
"""

from __future__ import annotations

import datetime
from unittest.mock import MagicMock, patch

import pytest

UTC = datetime.timezone.utc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_interbank_record(
    date: str,
    closing_balance: float | None = 50000.0,
) -> dict:
    return {"end_of_date": date, "closing_balance": closing_balance}


def _make_monbase_record(
    date: str,
    mb_total: float | None = 2_000_000.0,
    cert_of_indebt: float | None = 600_000.0,
    outstanding_efbn: float | None = 1_300_000.0,
) -> dict:
    return {
        "end_of_date": date,
        "mb_bf_disc_win_total": mb_total,
        "cert_of_indebt": cert_of_indebt,
        "outstanding_efbn": outstanding_efbn,
    }


def _hkma_api_response(records: list[dict], datasize: int | None = None) -> dict:
    return {
        "header": {"success": True, "err_code": "0000", "err_msg": "No error found"},
        "result": {
            "datasize": datasize if datasize is not None else len(records),
            "records": records,
        },
    }


# ---------------------------------------------------------------------------
# _parse_value
# ---------------------------------------------------------------------------

class TestParseValue:
    def test_float_passthrough(self) -> None:
        from playground.econ.hkma.fetch import _parse_value
        assert _parse_value(53997.0) == pytest.approx(53997.0)

    def test_int_to_float(self) -> None:
        from playground.econ.hkma.fetch import _parse_value
        assert _parse_value(53997) == pytest.approx(53997.0)

    def test_none_returns_none(self) -> None:
        from playground.econ.hkma.fetch import _parse_value
        assert _parse_value(None) is None

    def test_string_float_parses(self) -> None:
        from playground.econ.hkma.fetch import _parse_value
        assert _parse_value("1234.5") == pytest.approx(1234.5)

    def test_non_numeric_string_returns_none(self) -> None:
        from playground.econ.hkma.fetch import _parse_value
        assert _parse_value("n.a.") is None

    def test_empty_string_returns_none(self) -> None:
        from playground.econ.hkma.fetch import _parse_value
        assert _parse_value("") is None


# ---------------------------------------------------------------------------
# _build_indicator
# ---------------------------------------------------------------------------

class TestBuildIndicator:
    @pytest.mark.parametrize("series_key,expected_imdr,expected_cat", [
        ("agg_bal", "HKMA.AGG_BAL", "liquidity"),
        ("mon_base", "HKMA.MON_BASE", "cb_balance_sheet"),
        ("ci_out", "HKMA.CI_OUT", "instr_outstand"),
        ("efbn_out", "HKMA.EFBN_OUT", "instr_outstand"),
    ])
    def test_indicator_fields(
        self, series_key: str, expected_imdr: str, expected_cat: str
    ) -> None:
        from playground.econ.hkma.fetch import _build_indicator
        ind = _build_indicator(series_key, "DAILY")
        assert ind.imdr_code == expected_imdr
        assert ind.category == expected_cat
        assert ind.frequency == "DAILY"
        assert ind.country_iso == "HK"
        assert ind.vendor_name == "HKMA"
        assert ind.unit == "hkd_mn"

    def test_agg_bal_bbg_ticker(self) -> None:
        from playground.econ.hkma.fetch import _build_indicator
        ind = _build_indicator("agg_bal", "DAILY")
        assert ind.bbg_ticker == "HKMAAGGB Index"

    def test_mon_base_bbg_ticker_present(self) -> None:
        from playground.econ.hkma.fetch import _build_indicator
        ind = _build_indicator("mon_base", "DAILY")
        # Ticker is a best-effort guess per design.md; just verify it's populated.
        assert ind.bbg_ticker is not None

    def test_ci_out_no_bbg_ticker(self) -> None:
        from playground.econ.hkma.fetch import _build_indicator
        ind = _build_indicator("ci_out", "DAILY")
        assert ind.bbg_ticker is None

    def test_indicator_row_validates_category(self) -> None:
        from playground.econ.hkma.fetch import _build_indicator
        from playground.econ.schema_prototype import VALID_CATEGORIES
        for key in ("agg_bal", "mon_base", "ci_out", "efbn_out"):
            ind = _build_indicator(key, "DAILY")
            assert ind.category in VALID_CATEGORIES


# ---------------------------------------------------------------------------
# Pagination helper
# ---------------------------------------------------------------------------

class TestIterPages:
    def test_single_full_page_then_empty_stops(self) -> None:
        from playground.econ.hkma.fetch import _iter_pages, PAGE_SIZE

        records_page1 = [_make_interbank_record(f"2026-01-{i:02d}") for i in range(1, PAGE_SIZE + 1)]
        records_page2: list = []

        responses = [
            MagicMock(json=lambda r=r: _hkma_api_response(r))
            for r in [records_page1, records_page2]
        ]
        for resp in responses:
            resp.raise_for_status = MagicMock()

        with patch("playground.econ.hkma.fetch.requests.get", side_effect=responses):
            with patch("playground.econ.hkma.fetch.time.sleep"):
                pages = list(_iter_pages("daily-figures-interbank-liquidity"))

        assert len(pages) == 1
        assert len(pages[0]) == PAGE_SIZE

    def test_partial_page_stops_without_extra_request(self) -> None:
        from playground.econ.hkma.fetch import _iter_pages

        records = [_make_interbank_record("2026-01-01"), _make_interbank_record("2026-01-02")]
        mock_resp = MagicMock(json=lambda: _hkma_api_response(records))
        mock_resp.raise_for_status = MagicMock()

        with patch("playground.econ.hkma.fetch.requests.get", return_value=mock_resp) as mock_get:
            pages = list(_iter_pages("daily-figures-interbank-liquidity"))

        assert mock_get.call_count == 1
        assert len(pages) == 1
        assert len(pages[0]) == 2

    def test_api_error_raises_runtime_error(self) -> None:
        from playground.econ.hkma.fetch import _iter_pages

        error_resp = {
            "header": {"success": False, "err_code": "E00001", "err_msg": "API not found"},
            "result": {},
        }
        mock_resp = MagicMock(json=lambda: error_resp)
        mock_resp.raise_for_status = MagicMock()

        with patch("playground.econ.hkma.fetch.requests.get", return_value=mock_resp):
            with pytest.raises(RuntimeError, match="HKMA API error"):
                list(_iter_pages("bad-endpoint"))


# ---------------------------------------------------------------------------
# run_fetch — date filtering
# ---------------------------------------------------------------------------

class TestRunFetchDateFilter:
    def _patch_fetch_all(self, interbank_records: list[dict], monbase_records: list[dict]):
        """Return a context manager patching fetch_all_records."""
        def _side_effect(endpoint_slug: str) -> list[dict]:
            if "interbank" in endpoint_slug:
                return interbank_records
            return monbase_records

        return patch("playground.econ.hkma.fetch.fetch_all_records", side_effect=_side_effect)

    def test_since_filter_excludes_older_records(self) -> None:
        from playground.econ.hkma.fetch import run_fetch

        interbank = [
            _make_interbank_record("2026-01-10"),
            _make_interbank_record("2026-01-05"),
            _make_interbank_record("2025-12-31"),
        ]
        with self._patch_fetch_all(interbank, []):
            _, obs = run_fetch(["agg_bal"], since="2026-01-01", until=None)

        dates = {o.obs_date for o in obs}
        assert datetime.date(2025, 12, 31) not in dates
        assert datetime.date(2026, 1, 5) in dates
        assert datetime.date(2026, 1, 10) in dates

    def test_until_filter_excludes_newer_records(self) -> None:
        from playground.econ.hkma.fetch import run_fetch

        interbank = [
            _make_interbank_record("2026-03-01"),
            _make_interbank_record("2026-02-15"),
            _make_interbank_record("2026-01-31"),
        ]
        with self._patch_fetch_all(interbank, []):
            _, obs = run_fetch(["agg_bal"], since=None, until="2026-02-28")

        dates = {o.obs_date for o in obs}
        assert datetime.date(2026, 3, 1) not in dates
        assert datetime.date(2026, 2, 15) in dates
        assert datetime.date(2026, 1, 31) in dates

    def test_no_date_filter_returns_all_records(self) -> None:
        from playground.econ.hkma.fetch import run_fetch

        interbank = [_make_interbank_record(f"2026-0{m}-01") for m in range(1, 4)]
        with self._patch_fetch_all(interbank, []):
            _, obs = run_fetch(["agg_bal"], since=None, until=None)

        assert len(obs) == 3


# ---------------------------------------------------------------------------
# run_fetch — series filter and endpoint routing
# ---------------------------------------------------------------------------

class TestRunFetchSeriesFilter:
    def _patch_fetch_all(self, interbank_records: list[dict], monbase_records: list[dict]):
        def _side_effect(endpoint_slug: str) -> list[dict]:
            if "interbank" in endpoint_slug:
                return interbank_records
            return monbase_records

        return patch("playground.econ.hkma.fetch.fetch_all_records", side_effect=_side_effect)

    def test_agg_bal_only_does_not_call_monbase(self) -> None:
        from playground.econ.hkma.fetch import run_fetch

        interbank = [_make_interbank_record("2026-01-01")]
        with patch("playground.econ.hkma.fetch.fetch_all_records") as mock_fetch:
            mock_fetch.return_value = interbank
            inds, obs = run_fetch(["agg_bal"], since=None, until=None)

        assert mock_fetch.call_count == 1
        called_slug = mock_fetch.call_args[0][0]
        assert "interbank" in called_slug

        assert len(inds) == 1
        assert inds[0].imdr_code == "HKMA.AGG_BAL"

    def test_mon_base_only_does_not_call_interbank(self) -> None:
        from playground.econ.hkma.fetch import run_fetch

        monbase = [_make_monbase_record("2026-01-01")]
        with patch("playground.econ.hkma.fetch.fetch_all_records") as mock_fetch:
            mock_fetch.return_value = monbase
            inds, obs = run_fetch(["mon_base"], since=None, until=None)

        assert mock_fetch.call_count == 1
        called_slug = mock_fetch.call_args[0][0]
        assert "monetary-base" in called_slug

        assert any(i.imdr_code == "HKMA.MON_BASE" for i in inds)

    def test_ci_out_uses_monbase_endpoint_not_interbank(self) -> None:
        from playground.econ.hkma.fetch import run_fetch

        monbase = [_make_monbase_record("2026-01-01")]
        with patch("playground.econ.hkma.fetch.fetch_all_records") as mock_fetch:
            mock_fetch.return_value = monbase
            inds, _ = run_fetch(["ci_out"], since=None, until=None)

        assert mock_fetch.call_count == 1
        assert mock_fetch.call_args[0][0].endswith("daily-figures-monetary-base")
        assert any(i.imdr_code == "HKMA.CI_OUT" for i in inds)

    def test_efbn_out_uses_monbase_endpoint(self) -> None:
        from playground.econ.hkma.fetch import run_fetch

        monbase = [_make_monbase_record("2026-01-01")]
        with patch("playground.econ.hkma.fetch.fetch_all_records") as mock_fetch:
            mock_fetch.return_value = monbase
            inds, _ = run_fetch(["efbn_out"], since=None, until=None)

        assert mock_fetch.call_count == 1
        assert any(i.imdr_code == "HKMA.EFBN_OUT" for i in inds)

    def test_mon_base_and_ci_out_share_single_api_call(self) -> None:
        from playground.econ.hkma.fetch import run_fetch

        monbase = [_make_monbase_record("2026-01-01")]
        with patch("playground.econ.hkma.fetch.fetch_all_records") as mock_fetch:
            mock_fetch.return_value = monbase
            inds, _ = run_fetch(["mon_base", "ci_out"], since=None, until=None)

        # Both series come from same endpoint — only one fetch call.
        assert mock_fetch.call_count == 1
        imdr_codes = {i.imdr_code for i in inds}
        assert "HKMA.MON_BASE" in imdr_codes
        assert "HKMA.CI_OUT" in imdr_codes

    def test_original_four_series_make_two_api_calls(self) -> None:
        # The four v1 daily series come from exactly two endpoints (interbank +
        # monetary-base); requesting them explicitly must hit each endpoint once.
        # (run_fetch(None) now spans the v2-expanded endpoint set, so scope the
        # 2-call invariant to the original four.)
        from playground.econ.hkma.fetch import run_fetch

        interbank = [_make_interbank_record("2026-01-01")]
        monbase = [_make_monbase_record("2026-01-01")]
        call_count = 0

        def side_effect(slug: str) -> list[dict]:
            nonlocal call_count
            call_count += 1
            return interbank if "interbank" in slug else monbase

        with patch("playground.econ.hkma.fetch.fetch_all_records", side_effect=side_effect):
            inds, _ = run_fetch(
                ["agg_bal", "mon_base", "ci_out", "efbn_out"], since=None, until=None
            )

        assert call_count == 2
        assert len(inds) == 4

    def test_empty_series_filter_returns_empty(self) -> None:
        from playground.econ.hkma.fetch import run_fetch

        with patch("playground.econ.hkma.fetch.fetch_all_records") as mock_fetch:
            inds, obs = run_fetch(["nonexistent_key"], since=None, until=None)

        assert inds == []
        assert obs == []
        mock_fetch.assert_not_called()


# ---------------------------------------------------------------------------
# Observation shape
# ---------------------------------------------------------------------------

class TestObservationShape:
    def test_observations_have_correct_imdr_codes(self) -> None:
        from playground.econ.hkma.fetch import run_fetch

        interbank = [_make_interbank_record("2026-01-15", closing_balance=55000.0)]
        with patch("playground.econ.hkma.fetch.fetch_all_records", return_value=interbank):
            _, obs = run_fetch(["agg_bal"], since=None, until=None)

        assert len(obs) == 1
        assert obs[0].imdr_code == "HKMA.AGG_BAL"
        assert obs[0].obs_date == datetime.date(2026, 1, 15)
        assert obs[0].value == pytest.approx(55000.0)
        assert obs[0].vintage == 0
        assert obs[0].ingested_at.tzinfo is not None

    def test_null_field_produces_none_value(self) -> None:
        from playground.econ.hkma.fetch import run_fetch

        interbank = [_make_interbank_record("2026-01-15", closing_balance=None)]
        with patch("playground.econ.hkma.fetch.fetch_all_records", return_value=interbank):
            _, obs = run_fetch(["agg_bal"], since=None, until=None)

        assert obs[0].value is None

    def test_monbase_extracts_correct_value(self) -> None:
        from playground.econ.hkma.fetch import run_fetch

        monbase = [_make_monbase_record(
            "2026-01-15",
            mb_total=2_100_000.0,
            cert_of_indebt=655_255.0,
            outstanding_efbn=1_348_372.0,
        )]
        with patch("playground.econ.hkma.fetch.fetch_all_records", return_value=monbase):
            _, obs = run_fetch(["mon_base"], since=None, until=None)

        assert len(obs) == 1
        assert obs[0].imdr_code == "HKMA.MON_BASE"
        assert obs[0].value == pytest.approx(2_100_000.0)
