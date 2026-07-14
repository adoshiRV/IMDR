"""Unit tests for the promoted FRED connector (imdr.domains.econ.fred_http).

The legacy test_fred_connector.py targets the playground module; this covers the
production connector. All HTTP is mocked — no live FRED calls.
"""

from __future__ import annotations

import pytest

from imdr.domains.econ import fred_http
from imdr.domains.econ.fred_http import FredClient, _api_keys


class _FakeSettings:
    def __init__(self, key: str) -> None:
        self.econ_fred_key = key


def test_api_keys_primary_from_settings(monkeypatch):
    monkeypatch.setattr(fred_http, "get_settings", lambda: _FakeSettings("PRIMARY"))
    for i in range(2, 10):
        monkeypatch.delenv(f"IMDR_ECON_FRED_KEY{i}", raising=False)
    assert _api_keys() == ["PRIMARY"]


def test_api_keys_with_numbered_siblings(monkeypatch):
    monkeypatch.setattr(fred_http, "get_settings", lambda: _FakeSettings("P"))
    monkeypatch.setenv("IMDR_ECON_FRED_KEY2", "SECOND")
    monkeypatch.setenv("IMDR_ECON_FRED_KEY3", "THIRD")
    assert _api_keys() == ["P", "SECOND", "THIRD"]


def test_api_keys_missing_raises(monkeypatch):
    monkeypatch.setattr(fred_http, "get_settings", lambda: _FakeSettings(""))
    for i in range(2, 10):
        monkeypatch.delenv(f"IMDR_ECON_FRED_KEY{i}", raising=False)
    with pytest.raises(EnvironmentError, match="FRED API key not found"):
        _api_keys()


def test_key_rotation_round_robin():
    c = FredClient(api_keys=["A", "B"])
    assert [c._next_key() for _ in range(4)] == ["A", "B", "A", "B"]


def test_fetch_series_maps_dot_sentinel_to_none(monkeypatch):
    c = FredClient(api_keys=["K"])
    monkeypatch.setattr(
        c._http, "get_json",
        lambda path, params: {"observations": [
            {"date": "2026-01-01", "value": "1.5"},
            {"date": "2026-02-01", "value": "."},
        ]},
    )
    obs = c.fetch_series("CPIAUCSL", start="2026-01-01")
    assert obs[0]["value"] == "1.5"
    assert obs[1]["value"] is None


def test_series_info_not_found_raises(monkeypatch):
    c = FredClient(api_keys=["K"])
    monkeypatch.setattr(c._http, "get_json", lambda path, params: {"seriess": []})
    with pytest.raises(ValueError, match="not found"):
        c.series_info("BADID")
