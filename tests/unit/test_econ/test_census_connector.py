"""Tests for src/imdr/domains/econ/census_http.py.

No real network calls — CensusClient._get is monkeypatched at the httpx.Client
level. Covered:

- CensusClient raises RuntimeError when key is empty.
- 2-D array (header + data rows) is zipped into list-of-dicts correctly.
- Empty 2-D array returns [].
- 204 response returns [].
- time=from+YYYY parameter: the literal '+' is preserved in the final URL
  (not percent-encoded as %2B).
- API key is appended to every request.
- get_eits builds the correct /timeseries/eits/{program} URL prefix.
- get_intltrade builds the correct /timeseries/intltrade/{sub_path} URL prefix.
"""

from __future__ import annotations

import datetime
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client(key: str = "testkey123") -> "CensusClient":
    """Return a CensusClient with a fake key, no real HTTP client created."""
    from imdr.domains.econ.census_http import CensusClient
    with patch("imdr.domains.econ.census_http.get_settings") as mock_settings:
        mock_settings.return_value.econ_census_key = key
        client = CensusClient.__new__(CensusClient)
        client._key = key.strip()
        client._client = MagicMock()
    return client


def _mock_response(json_body, status_code: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_body
    resp.raise_for_status = MagicMock()
    return resp


# ---------------------------------------------------------------------------
# Key gating
# ---------------------------------------------------------------------------

class TestCensusClientKeyGating:
    def test_raises_runtime_error_when_key_empty(self) -> None:
        from imdr.domains.econ.census_http import CensusClient
        with patch("imdr.domains.econ.census_http.get_settings") as mock_settings:
            mock_settings.return_value.econ_census_key = ""
            with pytest.raises(RuntimeError, match="Census API key is empty"):
                CensusClient()

    def test_accepts_explicit_key(self) -> None:
        from imdr.domains.econ.census_http import CensusClient
        with patch("imdr.domains.econ.census_http.get_settings") as mock_settings:
            mock_settings.return_value.econ_census_key = ""
            with patch("imdr.domains.econ.census_http.httpx.Client"):
                client = CensusClient(api_key="explicit_key")
        assert client._key == "explicit_key"

    def test_strips_whitespace_from_key(self) -> None:
        from imdr.domains.econ.census_http import CensusClient
        with patch("imdr.domains.econ.census_http.get_settings") as mock_settings:
            mock_settings.return_value.econ_census_key = "  mykey  "
            with patch("imdr.domains.econ.census_http.httpx.Client"):
                client = CensusClient()
        assert client._key == "mykey"


# ---------------------------------------------------------------------------
# 2-D array → list-of-dicts zipping
# ---------------------------------------------------------------------------

class TestArrayZipping:
    def test_header_row_zipped_with_data_rows(self) -> None:
        client = _make_client()
        raw = [
            ["category_code", "cell_value", "time"],
            ["44000",          "650000",     "2024-01"],
            ["44000",          "660000",     "2024-02"],
        ]
        client._client.get.return_value = _mock_response(raw)
        with patch("imdr.domains.econ.census_http.time.sleep"):
            result = client._get("https://api.census.gov/data/timeseries/eits/marts", {})
        assert len(result) == 2
        assert result[0] == {"category_code": "44000", "cell_value": "650000", "time": "2024-01"}
        assert result[1]["time"] == "2024-02"

    def test_empty_raw_returns_empty_list(self) -> None:
        client = _make_client()
        client._client.get.return_value = _mock_response([])
        with patch("imdr.domains.econ.census_http.time.sleep"):
            result = client._get("https://api.census.gov/data/timeseries/eits/marts", {})
        assert result == []

    def test_header_only_returns_empty_list(self) -> None:
        client = _make_client()
        raw = [["category_code", "cell_value", "time"]]
        client._client.get.return_value = _mock_response(raw)
        with patch("imdr.domains.econ.census_http.time.sleep"):
            result = client._get("https://api.census.gov/data/timeseries/eits/marts", {})
        assert result == []

    def test_204_returns_empty_list(self) -> None:
        client = _make_client()
        client._client.get.return_value = _mock_response(None, status_code=204)
        with patch("imdr.domains.econ.census_http.time.sleep"):
            result = client._get("https://api.census.gov/data/timeseries/eits/marts", {})
        assert result == []


# ---------------------------------------------------------------------------
# time=from+YYYY — '+' must not be percent-encoded
# ---------------------------------------------------------------------------

class TestTimePlusPreservation:
    def test_plus_in_time_param_is_not_percent_encoded(self) -> None:
        """Census range syntax 'time=from+2015' must reach the server with a
        literal '+', not '%2B'. Verify the final URL string passed to
        httpx.Client.get contains 'time=from+2015'."""
        client = _make_client()
        client._client.get.return_value = _mock_response([])
        with patch("imdr.domains.econ.census_http.time.sleep"):
            client._get(
                "https://api.census.gov/data/timeseries/eits/marts",
                {"time": "from+2015", "get": "cell_value"},
            )
        called_url = client._client.get.call_args[0][0]
        assert "time=from+2015" in called_url, (
            f"Expected literal '+' in URL but got: {called_url}"
        )

    def test_percent2b_not_in_url(self) -> None:
        client = _make_client()
        client._client.get.return_value = _mock_response([])
        with patch("imdr.domains.econ.census_http.time.sleep"):
            client._get(
                "https://api.census.gov/data/timeseries/eits/resconst",
                {"time": "from+2020"},
            )
        called_url = client._client.get.call_args[0][0]
        assert "%2B" not in called_url, (
            f"'+' was percent-encoded as '%2B' in URL: {called_url}"
        )

    def test_api_key_appended_to_url(self) -> None:
        client = _make_client(key="myapikey")
        client._client.get.return_value = _mock_response([])
        with patch("imdr.domains.econ.census_http.time.sleep"):
            client._get("https://api.census.gov/data/timeseries/eits/marts", {"get": "x"})
        called_url = client._client.get.call_args[0][0]
        assert "key=myapikey" in called_url


# ---------------------------------------------------------------------------
# URL prefix routing
# ---------------------------------------------------------------------------

class TestUrlRouting:
    def test_get_eits_uses_eits_prefix(self) -> None:
        client = _make_client()
        client._client.get.return_value = _mock_response([])
        with patch("imdr.domains.econ.census_http.time.sleep"):
            client.get_eits("marts", {"get": "cell_value", "time": "from+2020"})
        called_url = client._client.get.call_args[0][0]
        assert "/timeseries/eits/marts" in called_url

    def test_get_intltrade_uses_intltrade_prefix(self) -> None:
        client = _make_client()
        client._client.get.return_value = _mock_response([])
        with patch("imdr.domains.econ.census_http.time.sleep"):
            client.get_intltrade("exports/enduse", {"get": "ALL_VAL_MO", "time": "from+2020"})
        called_url = client._client.get.call_args[0][0]
        assert "/timeseries/intltrade/exports/enduse" in called_url
