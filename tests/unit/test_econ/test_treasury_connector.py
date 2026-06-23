"""Tests for src/imdr/domains/econ/treasury_fiscaldata.py and the prod fetcher parse layer.

No real network calls — TreasuryClient.get_all is monkeypatched with synthetic
responses that exercise the parse logic in treasury_mts.py and treasury_debt.py.

Covered:
- TreasuryClient.get_all returns all data from a single-page response.
- TreasuryClient.get_all concatenates data across multiple pages.
- TreasuryClient.get_all stops at meta.total-pages and does not over-fetch.
- _obs_date_from_row skips prior-FY block rows (src_line_nbr < 15).
- _obs_date_from_row maps Oct/Nov/Dec to the FY-opening calendar year.
- _obs_date_from_row maps Jan-Sep to FY-opening year + 1.
- _obs_date_from_row returns None for non-month classification_desc values.
- Debt run_fetch divides tot_pub_debt_out_amt by 1e6 and stores as usd_mn.
- MTS run_fetch keeps only the latest record_date value per obs_date.
- MTS deficit sign-flip: positive raw value (deficit) stored as negative.
"""

from __future__ import annotations

import datetime
from unittest.mock import MagicMock, patch

import pytest

UTC = datetime.timezone.utc


# ---------------------------------------------------------------------------
# TreasuryClient.get_all — pagination
# ---------------------------------------------------------------------------

class TestTreasuryClientGetAll:
    def _make_client(self) -> object:
        from imdr.domains.econ.treasury_fiscaldata import TreasuryClient
        client = TreasuryClient.__new__(TreasuryClient)
        client._timeout = 30
        client._session = MagicMock()
        return client

    def test_single_page_returns_all_data(self) -> None:
        client = self._make_client()
        body = {"data": [{"record_date": "2026-01-31", "value": "100"}], "meta": {"total-pages": 1}}
        client._session.get.return_value = MagicMock(json=lambda: body)
        client._session.get.return_value.raise_for_status = lambda: None

        from imdr.domains.econ.treasury_fiscaldata import TreasuryClient
        result = TreasuryClient.get_all(client, "v1/some/endpoint")
        assert len(result) == 1
        assert result[0]["record_date"] == "2026-01-31"

    def test_multi_page_concatenates_data(self) -> None:
        client = self._make_client()
        page1 = {"data": [{"record_date": "2026-01-31"}], "meta": {"total-pages": 2}}
        page2 = {"data": [{"record_date": "2026-02-28"}], "meta": {"total-pages": 2}}
        responses = [page1, page2]
        call_count = [0]

        def fake_get(url, params=None, timeout=None):
            body = responses[call_count[0]]
            call_count[0] += 1
            resp = MagicMock()
            resp.json.return_value = body
            resp.raise_for_status = lambda: None
            return resp

        client._session.get.side_effect = fake_get

        from imdr.domains.econ.treasury_fiscaldata import TreasuryClient
        with patch("imdr.domains.econ.treasury_fiscaldata.time.sleep"):
            result = TreasuryClient.get_all(client, "v1/some/endpoint")

        assert len(result) == 2
        assert call_count[0] == 2

    def test_stops_at_total_pages(self) -> None:
        client = self._make_client()
        # total-pages = 1, so only one request should fire regardless.
        body = {"data": [{"record_date": "2026-01-31"}], "meta": {"total-pages": 1}}
        client._session.get.return_value = MagicMock(json=lambda: body)
        client._session.get.return_value.raise_for_status = lambda: None

        from imdr.domains.econ.treasury_fiscaldata import TreasuryClient
        TreasuryClient.get_all(client, "v1/some/endpoint")
        assert client._session.get.call_count == 1


# ---------------------------------------------------------------------------
# MTS obs_date derivation
# ---------------------------------------------------------------------------

class TestObsDateFromRow:
    def _fn(self):
        from scripts.econ.us.treasury.treasury_mts import _obs_date_from_row
        return _obs_date_from_row

    def test_prior_fy_block_skipped(self) -> None:
        f = self._fn()
        row = {"src_line_nbr": "3", "record_date": "2026-05-31", "classification_desc": "November"}
        assert f(row) is None

    def test_oct_maps_to_fy_start_year(self) -> None:
        f = self._fn()
        # pub_date 2026-05-31 => fy_start_year = 2025; Oct -> cal_year 2025
        row = {"src_line_nbr": "16", "record_date": "2026-05-31", "classification_desc": "October"}
        result = f(row)
        assert result == datetime.date(2025, 10, 1)

    def test_jan_maps_to_fy_start_plus_one(self) -> None:
        f = self._fn()
        # pub_date 2026-05-31 => fy_start_year = 2025; Jan -> cal_year 2026
        row = {"src_line_nbr": "16", "record_date": "2026-05-31", "classification_desc": "January"}
        result = f(row)
        assert result == datetime.date(2026, 1, 1)

    def test_non_month_name_returns_none(self) -> None:
        f = self._fn()
        row = {"src_line_nbr": "16", "record_date": "2026-05-31", "classification_desc": "Total"}
        assert f(row) is None

    def test_missing_key_returns_none(self) -> None:
        f = self._fn()
        assert f({}) is None


# ---------------------------------------------------------------------------
# MTS run_fetch — dedup + sign-flip
# ---------------------------------------------------------------------------

class TestMtsFetch:
    def _make_raw_row(
        self,
        record_date: str,
        month_name: str,
        src: int,
        rcpt: str,
        outly: str,
        dfct: str,
    ) -> dict:
        return {
            "record_date": record_date,
            "classification_desc": month_name,
            "src_line_nbr": str(src),
            "current_month_gross_rcpt_amt": rcpt,
            "current_month_gross_outly_amt": outly,
            "current_month_dfct_sur_amt": dfct,
            "record_type_cd": "MTH",
        }

    def test_deficit_sign_flip(self) -> None:
        from scripts.econ.us.treasury.treasury_mts import run_fetch
        from imdr.domains.econ.treasury_fiscaldata import TreasuryClient

        # dfct_sur_amt positive = deficit in raw API; we negate to surplus convention.
        raw_row = self._make_raw_row(
            "2026-05-31", "April", 16,
            rcpt="500000000000",   # 500e9 => 500_000 usd_mn
            outly="700000000000",  # 700e9 => 700_000 usd_mn
            dfct="200000000000",   # raw positive deficit => stored as -200_000 usd_mn
        )

        with patch.object(TreasuryClient, "get_all", return_value=[raw_row]):
            indicators, observations = run_fetch("2026-01-01", "2026-12-31")

        deficit_obs = [o for o in observations if o.imdr_code == "TREASURY.FISCAL.DEFICIT.US"]
        assert len(deficit_obs) == 1
        assert deficit_obs[0].value == pytest.approx(-200_000.0)

    def test_dedup_keeps_latest_record_date(self) -> None:
        from scripts.econ.us.treasury.treasury_mts import run_fetch
        from imdr.domains.econ.treasury_fiscaldata import TreasuryClient

        # Two rows for the same obs_date (April 2026): newer record_date first (API sorts -record_date).
        row_new = self._make_raw_row("2026-05-31", "April", 16, "600000000000", "700000000000", "100000000000")
        row_old = self._make_raw_row("2026-04-30", "April", 16, "500000000000", "700000000000", "200000000000")

        with patch.object(TreasuryClient, "get_all", return_value=[row_new, row_old]):
            _, observations = run_fetch("2026-01-01", "2026-12-31")

        rcpt_obs = [o for o in observations if o.imdr_code == "TREASURY.FISCAL.RECEIPTS.US"]
        assert len(rcpt_obs) == 1
        # newer row's receipts = 600e9 / 1e6 = 600_000 usd_mn
        assert rcpt_obs[0].value == pytest.approx(600_000.0)


# ---------------------------------------------------------------------------
# Debt run_fetch — unit conversion
# ---------------------------------------------------------------------------

class TestDebtFetch:
    def test_divides_by_1e6(self) -> None:
        from scripts.econ.us.treasury.treasury_debt import run_fetch
        from imdr.domains.econ.treasury_fiscaldata import TreasuryClient

        raw_row = {
            "record_date": "2026-06-01",
            "tot_pub_debt_out_amt": "36500000000000",  # 36.5e12 USD => 36_500_000 usd_mn
        }

        with patch.object(TreasuryClient, "get_all", return_value=[raw_row]):
            indicators, observations = run_fetch("2026-01-01", "2026-12-31")

        assert len(observations) == 1
        assert observations[0].imdr_code == "TREASURY.DEBT.TOTAL_PUBLIC.US"
        assert observations[0].value == pytest.approx(36_500_000.0)
        assert observations[0].obs_date == datetime.date(2026, 6, 1)

    def test_none_raw_value_stores_none(self) -> None:
        from scripts.econ.us.treasury.treasury_debt import run_fetch
        from imdr.domains.econ.treasury_fiscaldata import TreasuryClient

        raw_row = {"record_date": "2026-06-01", "tot_pub_debt_out_amt": None}

        with patch.object(TreasuryClient, "get_all", return_value=[raw_row]):
            _, observations = run_fetch("2026-01-01", "2026-12-31")

        assert observations[0].value is None
