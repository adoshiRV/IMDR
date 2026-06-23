"""Unit tests for src/imdr/domains/econ/bea_http.py.

Covered:
- bea_period_to_date: quarterly, monthly, annual, invalid inputs.
- parse_data_value: comma-stripping, (NA)/(D)/-- -> None, plain float.
- BeaClient: raises RuntimeError when key empty.
- BeaClient.get_data: 200-with-Error detection at BEAAPI level.
- BeaClient.get_data: 200-with-Error detection at Results level.
"""

from __future__ import annotations

import datetime
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# bea_period_to_date
# ---------------------------------------------------------------------------

class TestBeaPeriodToDate:
    def _fn(self):
        from imdr.domains.econ.bea_http import bea_period_to_date
        return bea_period_to_date

    def test_quarterly_q1(self) -> None:
        fn = self._fn()
        assert fn("2025Q1") == datetime.date(2025, 1, 1)

    def test_quarterly_q2(self) -> None:
        fn = self._fn()
        assert fn("2025Q2") == datetime.date(2025, 4, 1)

    def test_quarterly_q3(self) -> None:
        fn = self._fn()
        assert fn("2025Q3") == datetime.date(2025, 7, 1)

    def test_quarterly_q4(self) -> None:
        fn = self._fn()
        assert fn("2025Q4") == datetime.date(2025, 10, 1)

    def test_monthly(self) -> None:
        fn = self._fn()
        assert fn("2025M05") == datetime.date(2025, 5, 1)

    def test_monthly_january(self) -> None:
        fn = self._fn()
        assert fn("2024M01") == datetime.date(2024, 1, 1)

    def test_annual(self) -> None:
        fn = self._fn()
        assert fn("2025") == datetime.date(2025, 1, 1)

    def test_invalid_returns_none(self) -> None:
        fn = self._fn()
        assert fn("") is None
        assert fn("JUNK") is None
        assert fn(None) is None

    def test_bad_quarter_returns_none(self) -> None:
        fn = self._fn()
        assert fn("2025Q5") is None


# ---------------------------------------------------------------------------
# parse_data_value
# ---------------------------------------------------------------------------

class TestParseDataValue:
    def _fn(self):
        from imdr.domains.econ.bea_http import parse_data_value
        return parse_data_value

    def test_plain_float(self) -> None:
        fn = self._fn()
        assert fn("1234.56") == pytest.approx(1234.56)

    def test_comma_stripping(self) -> None:
        fn = self._fn()
        assert fn("1,234,567.89") == pytest.approx(1234567.89)

    def test_na_returns_none(self) -> None:
        fn = self._fn()
        assert fn("(NA)") is None

    def test_d_returns_none(self) -> None:
        fn = self._fn()
        assert fn("(D)") is None

    def test_double_dash_returns_none(self) -> None:
        fn = self._fn()
        assert fn("--") is None

    def test_none_input_returns_none(self) -> None:
        fn = self._fn()
        assert fn(None) is None

    def test_empty_string_returns_none(self) -> None:
        fn = self._fn()
        assert fn("") is None

    def test_negative_value(self) -> None:
        fn = self._fn()
        assert fn("-345,678") == pytest.approx(-345678.0)


# ---------------------------------------------------------------------------
# BeaClient — key gating
# ---------------------------------------------------------------------------

class TestBeaClientKeyGating:
    def test_raises_when_key_empty(self) -> None:
        from imdr.config.settings import Settings
        mock_settings = MagicMock(spec=Settings)
        mock_settings.econ_bea_key = ""
        with patch("imdr.domains.econ.bea_http.get_settings", return_value=mock_settings):
            from imdr.domains.econ import bea_http
            with pytest.raises(RuntimeError, match="IMDR_ECON_BEA_KEY not set"):
                bea_http.BeaClient()

    def test_raises_when_key_whitespace_only(self) -> None:
        from imdr.config.settings import Settings
        mock_settings = MagicMock(spec=Settings)
        mock_settings.econ_bea_key = "   "
        with patch("imdr.domains.econ.bea_http.get_settings", return_value=mock_settings):
            from imdr.domains.econ import bea_http
            with pytest.raises(RuntimeError, match="IMDR_ECON_BEA_KEY not set"):
                bea_http.BeaClient()


# ---------------------------------------------------------------------------
# BeaClient.get_data — 200-with-Error detection
# ---------------------------------------------------------------------------

class TestBeaClientGetData:
    def _make_client(self) -> "BeaClient":
        """Build a BeaClient with a mocked httpx.Client and a fake key."""
        from imdr.config.settings import Settings
        from imdr.domains.econ import bea_http

        mock_settings = MagicMock(spec=Settings)
        mock_settings.econ_bea_key = "testkey"

        with patch("imdr.domains.econ.bea_http.get_settings", return_value=mock_settings):
            client = bea_http.BeaClient.__new__(bea_http.BeaClient)
            client._key = "testkey"
            client._client = MagicMock()
        return client

    def _set_response(self, client, body: dict) -> None:
        mock_resp = MagicMock()
        mock_resp.json.return_value = body
        mock_resp.raise_for_status.return_value = None
        client._client.get.return_value = mock_resp

    def test_top_level_error_raises(self) -> None:
        from imdr.domains.econ.bea_http import BeaClient
        client = self._make_client()
        self._set_response(client, {
            "BEAAPI": {
                "Error": {
                    "APIErrorCode": "1",
                    "APIErrorDescription": "Invalid UserID",
                }
            }
        })
        with patch("imdr.domains.econ.bea_http.time") as mock_time:
            mock_time.sleep = MagicMock()
            with pytest.raises(RuntimeError, match="BEA API error: 1 — Invalid UserID"):
                client.get_data("NIPA", TableName="T10101", Frequency="Q", Year="ALL")

    def test_results_level_error_raises(self) -> None:
        client = self._make_client()
        self._set_response(client, {
            "BEAAPI": {
                "Results": {
                    "Error": {
                        "APIErrorCode": "200",
                        "APIErrorDescription": "Bad parameter value",
                    }
                }
            }
        })
        with patch("imdr.domains.econ.bea_http.time") as mock_time:
            mock_time.sleep = MagicMock()
            with pytest.raises(RuntimeError, match="BEA API error: 200 — Bad parameter value"):
                client.get_data("NIPA", TableName="T10101", Frequency="Q", Year="ALL")

    def test_success_returns_results_dict(self) -> None:
        client = self._make_client()
        self._set_response(client, {
            "BEAAPI": {
                "Results": {
                    "Data": [{"TimePeriod": "2024Q1", "DataValue": "27360.9"}]
                }
            }
        })
        with patch("imdr.domains.econ.bea_http.time") as mock_time:
            mock_time.sleep = MagicMock()
            result = client.get_data("NIPA", TableName="T10101", Frequency="Q", Year="ALL")
        assert "Data" in result
        assert result["Data"][0]["TimePeriod"] == "2024Q1"
