"""Tests for src/imdr/domains/econ/bls_http.py.

No live network calls — BlsClient._client.post is monkeypatched.

Covered:
- bls_period_to_date: M01 -> first of month.
- bls_period_to_date: M12 -> December 1.
- bls_period_to_date: M13 (annual avg) -> None.
- bls_period_to_date: Q01 -> January 1 (quarter start).
- bls_period_to_date: Q03 -> July 1.
- bls_period_to_date: Q05 (annual avg) -> None.
- bls_period_to_date: A01 -> Jan 1.
- bls_period_to_date: S01/S02 -> Jan 1 / Jul 1.
- bls_period_to_date: bad year string -> None.
- BlsClient raises RuntimeError when key is empty.
- fetch_series parses a well-formed BLS response into {sid: [obs]}.
- fetch_series raises RuntimeError on non-REQUEST_SUCCEEDED status.
"""

from __future__ import annotations

import datetime
import json
from unittest.mock import MagicMock, patch

import pytest

from imdr.domains.econ.bls_http import BlsClient, bls_period_to_date


# ---------------------------------------------------------------------------
# bls_period_to_date
# ---------------------------------------------------------------------------

class TestBlsPeriodToDate:
    def test_monthly_m01(self) -> None:
        assert bls_period_to_date("2024", "M01") == datetime.date(2024, 1, 1)

    def test_monthly_m12(self) -> None:
        assert bls_period_to_date("2024", "M12") == datetime.date(2024, 12, 1)

    def test_monthly_m13_annual_avg_returns_none(self) -> None:
        assert bls_period_to_date("2024", "M13") is None

    def test_quarterly_q01_is_jan(self) -> None:
        assert bls_period_to_date("2024", "Q01") == datetime.date(2024, 1, 1)

    def test_quarterly_q03_is_jul(self) -> None:
        assert bls_period_to_date("2024", "Q03") == datetime.date(2024, 7, 1)

    def test_quarterly_q05_annual_avg_returns_none(self) -> None:
        assert bls_period_to_date("2024", "Q05") is None

    def test_annual_a01_is_jan1(self) -> None:
        assert bls_period_to_date("2024", "A01") == datetime.date(2024, 1, 1)

    def test_semiannual_s01_is_jan(self) -> None:
        assert bls_period_to_date("2024", "S01") == datetime.date(2024, 1, 1)

    def test_semiannual_s02_is_jul(self) -> None:
        assert bls_period_to_date("2024", "S02") == datetime.date(2024, 7, 1)

    def test_bad_year_returns_none(self) -> None:
        assert bls_period_to_date("notayear", "M01") is None


# ---------------------------------------------------------------------------
# BlsClient — key gating
# ---------------------------------------------------------------------------

class TestBlsClientKeyGating:
    def test_raises_runtime_error_when_key_empty(self) -> None:
        with patch("imdr.domains.econ.bls_http.get_settings") as mock_settings:
            mock_settings.return_value.econ_bls_key = ""
            with pytest.raises(RuntimeError, match="IMDR_ECON_BLS_KEY not set"):
                BlsClient()


# ---------------------------------------------------------------------------
# BlsClient.fetch_series — response parsing (mocked)
# ---------------------------------------------------------------------------

def _make_bls_response(series_id: str, data: list[dict]) -> MagicMock:
    """Build a mock httpx.Response with a well-formed BLS payload."""
    payload = {
        "status": "REQUEST_SUCCEEDED",
        "responseTime": 100,
        "message": [],
        "Results": {
            "series": [
                {"seriesID": series_id, "data": data}
            ]
        },
    }
    mock_resp = MagicMock()
    mock_resp.json.return_value = payload
    mock_resp.raise_for_status.return_value = None
    return mock_resp


class TestBlsClientFetchSeries:
    def _make_client(self, mock_response: MagicMock) -> BlsClient:
        with patch("imdr.domains.econ.bls_http.get_settings") as mock_settings:
            mock_settings.return_value.econ_bls_key = "testkey123"
            client = BlsClient.__new__(BlsClient)
            client._key = "testkey123"
            mock_http = MagicMock()
            mock_http.post.return_value = mock_response
            client._client = mock_http
            return client

    def test_parses_monthly_obs_correctly(self) -> None:
        data = [
            {"year": "2024", "period": "M03", "periodName": "March", "value": "312.332", "footnotes": []},
            {"year": "2024", "period": "M02", "periodName": "February", "value": "311.054", "footnotes": []},
        ]
        client = self._make_client(_make_bls_response("CUSR0000SA0", data))
        with patch("imdr.domains.econ.bls_http.time.sleep"):
            result = client.fetch_series(["CUSR0000SA0"], 2024, 2024)
        assert "CUSR0000SA0" in result
        assert len(result["CUSR0000SA0"]) == 2
        assert result["CUSR0000SA0"][0]["value"] == "312.332"

    def test_raises_on_failed_status(self) -> None:
        payload = {
            "status": "REQUEST_FAILED",
            "message": ["Invalid API key"],
            "Results": {},
        }
        mock_resp = MagicMock()
        mock_resp.json.return_value = payload
        mock_resp.raise_for_status.return_value = None
        client = self._make_client(mock_resp)
        with patch("imdr.domains.econ.bls_http.time.sleep"):
            with pytest.raises(RuntimeError, match="BLS request failed"):
                client.fetch_series(["CUSR0000SA0"], 2024, 2024)

    def test_empty_series_data_returns_empty_list(self) -> None:
        client = self._make_client(_make_bls_response("CUSR0000SA0", []))
        with patch("imdr.domains.econ.bls_http.time.sleep"):
            result = client.fetch_series(["CUSR0000SA0"], 2024, 2024)
        assert result["CUSR0000SA0"] == []
