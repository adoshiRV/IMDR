"""Tests for connectors/citi_velocity.py — mocked HTTP, no real API calls."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import httpx
import pytest

from imdr.config.settings import Settings
from imdr.connectors.citi_velocity import CitiVelocityClient


@pytest.fixture
def settings():
    return Settings(
        citi_host="api.test.com",
        citi_client_id="test_id",
        citi_client_secret="test_secret",
        citi_scope="/api",
        citi_token_path="/oauth/token",
        citi_data_path="/data",
        citi_taglisting_path="/taglisting",
        citi_tagbrowsing_path="/tagbrowsing",
        citi_timeout=10,
        citi_token_ttl=3600,
    )


@pytest.fixture
def mock_transport():
    return MagicMock(spec=httpx.HTTPTransport)


def _mock_response(status_code=200, json_data=None, text=""):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.text = text or ""
    resp.json.return_value = json_data or {}
    return resp


# ── Token Management ────────────────────────────────────────────

class TestGetToken:
    def test_posts_correct_payload(self, settings):
        with CitiVelocityClient(settings) as client:
            mock_resp = _mock_response(200, {"access_token": "tok123", "expires_in": 3600})
            client._client.post = MagicMock(return_value=mock_resp)

            token = client.get_token()

            assert token == "tok123"
            call_args = client._client.post.call_args
            assert "/oauth/token" in call_args.args[0]
            assert "grant_type=client_credentials" in call_args.kwargs["content"]

    def test_caches_token(self, settings):
        with CitiVelocityClient(settings) as client:
            mock_resp = _mock_response(200, {"access_token": "tok123", "expires_in": 3600})
            client._client.post = MagicMock(return_value=mock_resp)

            client.get_token()
            client.get_token()

            # Only one HTTP call — second uses cache
            assert client._client.post.call_count == 1

    def test_raises_on_error(self, settings):
        with CitiVelocityClient(settings) as client:
            mock_resp = _mock_response(401, text="Unauthorized")
            client._client.post = MagicMock(return_value=mock_resp)

            with pytest.raises(RuntimeError, match="Token fetch failed"):
                client.get_token()

    def test_raises_on_missing_access_token(self, settings):
        with CitiVelocityClient(settings) as client:
            mock_resp = _mock_response(200, {"error": "invalid_grant"})
            client._client.post = MagicMock(return_value=mock_resp)

            with pytest.raises(RuntimeError, match="missing access_token"):
                client.get_token()


# ── Historical Data ─────────────────────────────────────────────

class TestFetchHistorical:
    def _setup_client(self, settings):
        client = CitiVelocityClient(settings)
        # Pre-populate token
        client._token = "tok123"
        client._token_expiry = float("inf")
        return client

    def test_returns_parsed_json(self, settings):
        client = self._setup_client(settings)
        expected = {"status": "OK", "body": {"RATES.OIS.USD_SOFR.PAR.5Y": {"x": [20240101], "c": [3.85]}}}
        client._client.post = MagicMock(return_value=_mock_response(200, expected))

        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 31, tzinfo=timezone.utc)
        result = client.fetch_historical(["RATES.OIS.USD_SOFR.PAR.5Y"], start, end)

        assert result["status"] == "OK"
        assert "RATES.OIS.USD_SOFR.PAR.5Y" in result["body"]

    def test_appends_client_id(self, settings):
        client = self._setup_client(settings)
        client._client.post = MagicMock(return_value=_mock_response(200, {"status": "OK", "body": {}}))

        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 31, tzinfo=timezone.utc)
        client.fetch_historical(["TAG"], start, end)

        url = client._client.post.call_args.args[0]
        assert "client_id=test_id" in url

    def test_raises_on_http_error(self, settings):
        client = self._setup_client(settings)
        client._client.post = MagicMock(return_value=_mock_response(500, text="Server Error"))

        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 31, tzinfo=timezone.utc)

        with pytest.raises(RuntimeError, match="Citi API error"):
            client.fetch_historical(["TAG"], start, end)

        client.close()


# ── Tag Listing ─────────────────────────────────────────────────

class TestFetchTaglisting:
    def test_with_prefix(self, settings):
        client = CitiVelocityClient(settings)
        client._token = "tok123"
        client._token_expiry = float("inf")

        expected = {"status": "OK", "tags": ["RATES.OIS.USD_SOFR.PAR.5Y"]}
        client._client.post = MagicMock(return_value=_mock_response(200, expected))

        result = client.fetch_taglisting("RATES.OIS.USD_SOFR.PAR")
        assert result["tags"] == ["RATES.OIS.USD_SOFR.PAR.5Y"]

        payload = client._client.post.call_args.kwargs["json"]
        assert payload["prefix"] == "RATES.OIS.USD_SOFR.PAR"

        client.close()

    def test_with_regex(self, settings):
        client = CitiVelocityClient(settings)
        client._token = "tok123"
        client._token_expiry = float("inf")

        client._client.post = MagicMock(return_value=_mock_response(200, {"status": "OK", "tags": []}))

        client.fetch_taglisting("RATES.OIS", regex=".*5Y$")
        payload = client._client.post.call_args.kwargs["json"]
        assert payload["regex"] == ".*5Y$"

        client.close()


# ── Tag Browsing ────────────────────────────────────────────────

class TestFetchTagbrowsing:
    def test_root(self, settings):
        client = CitiVelocityClient(settings)
        client._token = "tok123"
        client._token_expiry = float("inf")

        expected = {"status": "OK", "fields": {"RATES": {}}, "leaves": []}
        client._client.post = MagicMock(return_value=_mock_response(200, expected))

        result = client.fetch_tagbrowsing("")
        assert "fields" in result

        client.close()


# ── Metadata ────────────────────────────────────────────────────

class TestFetchMetadata:
    def test_sends_metadata_flag(self, settings):
        client = CitiVelocityClient(settings)
        client._token = "tok123"
        client._token_expiry = float("inf")

        client._client.post = MagicMock(return_value=_mock_response(200, {"status": "OK"}))

        client.fetch_metadata(["RATES.OIS.USD_SOFR.PAR.5Y"])
        payload = client._client.post.call_args.kwargs["json"]
        assert payload["metadata"] is True
        assert payload["tags"] == ["RATES.OIS.USD_SOFR.PAR.5Y"]

        client.close()


# ── Context Manager ─────────────────────────────────────────────

class TestContextManager:
    def test_closes_client(self, settings):
        client = CitiVelocityClient(settings)
        client._client.close = MagicMock()

        with client:
            pass

        client._client.close.assert_called_once()
