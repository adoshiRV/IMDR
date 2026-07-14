"""Tests for src/imdr/domains/econ/eia_http.py.

No real network calls — httpx.Client.get is monkeypatched.

Covered:
- EiaClient raises RuntimeError when IMDR_ECON_EIA_KEY is empty.
- fetch_series returns a flat list of row dicts from a single-page response.
- fetch_series filters rows earlier than start_period client-side.
- fetch_series paginates when a full page (_PAGE_SIZE rows) is returned.
- fetch_series stops pagination on a partial page (len < _PAGE_SIZE).
- fetch_series raises RuntimeError when the API body carries an error key.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_eia_response(rows: list[dict], status_code: int = 200) -> MagicMock:
    """Build a fake httpx.Response-like object."""
    body = {"response": {"data": rows}}
    mock = MagicMock()
    mock.status_code = status_code
    mock.raise_for_status = MagicMock()
    mock.json = MagicMock(return_value=body)
    return mock


def _make_error_response(error_msg: str) -> MagicMock:
    body = {"response": {"data": [], "error": error_msg}}
    mock = MagicMock()
    mock.raise_for_status = MagicMock()
    mock.json = MagicMock(return_value=body)
    return mock


def _patch_settings(key: str = "testkey123"):
    """Patch get_settings() to return a settings object with a known EIA key."""
    settings_mock = SimpleNamespace(econ_eia_key=key)
    return patch("imdr.domains.econ.eia_http.get_settings", return_value=settings_mock)


# ---------------------------------------------------------------------------
# EiaClient — key gating
# ---------------------------------------------------------------------------

class TestEiaClientApiKey:
    def test_raises_runtime_error_when_key_empty(self) -> None:
        with _patch_settings(key=""):
            with pytest.raises(RuntimeError, match="IMDR_ECON_EIA_KEY not set"):
                from imdr.domains.econ.eia_http import EiaClient
                EiaClient()

    def test_accepts_non_empty_key(self) -> None:
        with _patch_settings(key="validkey"):
            with patch("imdr.domains.econ.eia_http.httpx.Client"):
                from imdr.domains.econ.eia_http import EiaClient
                client = EiaClient()
                assert client._key == "validkey"


# ---------------------------------------------------------------------------
# fetch_series — single-page response parsing
# ---------------------------------------------------------------------------

class TestFetchSeriesSinglePage:
    def _make_client(self) -> "EiaClient":
        from imdr.domains.econ.eia_http import EiaClient
        with _patch_settings():
            with patch("imdr.domains.econ.eia_http.httpx.Client"):
                client = EiaClient()
        return client

    def test_returns_flat_list_of_row_dicts(self) -> None:
        from imdr.domains.econ.eia_http import EiaClient
        rows = [
            {"period": "2024-01-02", "value": 73.5, "series": "RWTC"},
            {"period": "2024-01-03", "value": 74.1, "series": "RWTC"},
        ]
        response = _make_eia_response(rows)

        with _patch_settings():
            with patch("imdr.domains.econ.eia_http.httpx.Client") as mock_cls:
                mock_http = MagicMock()
                mock_http.get.return_value = response
                mock_cls.return_value = mock_http
                client = EiaClient()
                result = client.fetch_series(
                    "petroleum/pri/spt", frequency="daily",
                    facets={"series": "RWTC"}, throttle_sec=0
                )

        assert len(result) == 2
        assert result[0]["period"] == "2024-01-02"
        assert result[1]["value"] == pytest.approx(74.1)

    def test_start_period_filters_early_rows(self) -> None:
        from imdr.domains.econ.eia_http import EiaClient
        rows = [
            {"period": "2014-12-31", "value": 55.0, "series": "RWTC"},
            {"period": "2015-01-02", "value": 56.0, "series": "RWTC"},
        ]
        response = _make_eia_response(rows)

        with _patch_settings():
            with patch("imdr.domains.econ.eia_http.httpx.Client") as mock_cls:
                mock_http = MagicMock()
                mock_http.get.return_value = response
                mock_cls.return_value = mock_http
                client = EiaClient()
                result = client.fetch_series(
                    "petroleum/pri/spt", frequency="daily",
                    facets={"series": "RWTC"}, start_period="2015-01-01", throttle_sec=0
                )

        assert len(result) == 1
        assert result[0]["period"] == "2015-01-02"

    def test_raises_on_api_error_in_body(self) -> None:
        from imdr.domains.econ.eia_http import EiaClient
        response = _make_error_response("Invalid API Key.")

        with _patch_settings():
            with patch("imdr.domains.econ.eia_http.httpx.Client") as mock_cls:
                mock_http = MagicMock()
                mock_http.get.return_value = response
                mock_cls.return_value = mock_http
                client = EiaClient()
                with pytest.raises(RuntimeError, match="EIA API error"):
                    client.fetch_series(
                        "petroleum/pri/spt", frequency="daily", throttle_sec=0
                    )


# ---------------------------------------------------------------------------
# fetch_series — pagination
# ---------------------------------------------------------------------------

class TestFetchSeriesPagination:
    def test_paginates_when_full_page_returned(self) -> None:
        """Two calls: first returns _PAGE_SIZE rows, second returns 1 (partial)."""
        from imdr.domains.econ.eia_http import EiaClient, _PAGE_SIZE

        full_page = [{"period": f"2020-{i:04d}", "value": float(i)} for i in range(_PAGE_SIZE)]
        tail_page = [{"period": "2021-0001", "value": 99.0}]

        call_count = 0

        def fake_get(url, params=None):
            nonlocal call_count
            call_count += 1
            data = full_page if call_count == 1 else tail_page
            mock = MagicMock()
            mock.raise_for_status = MagicMock()
            mock.json = MagicMock(return_value={"response": {"data": data}})
            return mock

        with _patch_settings():
            with patch("imdr.domains.econ.eia_http.httpx.Client") as mock_cls:
                mock_http = MagicMock()
                mock_http.get.side_effect = fake_get
                mock_cls.return_value = mock_http
                client = EiaClient()
                result = client.fetch_series(
                    "petroleum/pri/spt", frequency="daily", throttle_sec=0
                )

        assert call_count == 2
        assert len(result) == _PAGE_SIZE + 1

    def test_stops_on_partial_page(self) -> None:
        """A partial-page first response → exactly one HTTP call."""
        from imdr.domains.econ.eia_http import EiaClient

        rows = [{"period": "2024-01-02", "value": 73.5}]  # len < _PAGE_SIZE
        response = _make_eia_response(rows)

        with _patch_settings():
            with patch("imdr.domains.econ.eia_http.httpx.Client") as mock_cls:
                mock_http = MagicMock()
                mock_http.get.return_value = response
                mock_cls.return_value = mock_http
                client = EiaClient()
                result = client.fetch_series(
                    "petroleum/pri/spt", frequency="daily", throttle_sec=0
                )

        assert mock_http.get.call_count == 1
        assert len(result) == 1

    def test_empty_first_response_returns_empty_list(self) -> None:
        from imdr.domains.econ.eia_http import EiaClient

        response = _make_eia_response([])

        with _patch_settings():
            with patch("imdr.domains.econ.eia_http.httpx.Client") as mock_cls:
                mock_http = MagicMock()
                mock_http.get.return_value = response
                mock_cls.return_value = mock_http
                client = EiaClient()
                result = client.fetch_series(
                    "petroleum/pri/spt", frequency="daily", throttle_sec=0
                )

        assert result == []
