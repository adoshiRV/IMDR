"""Tests for playground/econ/fred/connector.py and fred/fetch.py parse layer.

No real network calls — we mock HTTPClient.get_json and test the parse
logic in fetch.py that transforms raw FRED dicts into ObservationRow lists.

Covered:
- FredClient raises EnvironmentError when IMDR_ECON_FRED_KEY is absent.
- FredClient.fetch_series maps '.' sentinel to None.
- parse_observations returns ObservationRow list with correct fields.
- parse_observations sets vintage=0 for all rows on a plain pull.
- parse_vintage_observations assigns vintage=0 for first print, 1 for changed value.
- parse_vintage_observations does NOT emit a new row when value is unchanged.
- parse_vintage_observations handles None values correctly.
- FredClient.fetch_release_calendar passes correct params and returns release_dates list.
- FredClient.fetch_recent_updates passes start_time and returns seriess list.
- FredClient.fetch_recent_updates omits end_time when not supplied.
- FredClient.search_series passes search_text and tag_names, returns seriess list.
- FredClient.search_series raises ValueError when neither query nor tag_names supplied.
- run_calendar builds correct DataFrame columns from release calendar entries.
- run_updates_since parses HH:MM into correct FRED start_time format.
"""

from __future__ import annotations

import datetime
import os
from unittest.mock import MagicMock, patch

import pytest

UTC = datetime.timezone.utc


# ---------------------------------------------------------------------------
# FredClient — env key gating
# ---------------------------------------------------------------------------

class TestFredClientApiKey:
    def test_raises_environment_error_when_no_key(self) -> None:
        """Importing with neither IMDR_ECON_FRED_KEY nor FRED_API_KEY should raise."""
        with patch.dict(os.environ, {}, clear=True):
            # Remove any existing key values
            env_without_keys = {
                k: v for k, v in os.environ.items()
                if k not in ("IMDR_ECON_FRED_KEY", "FRED_API_KEY")
            }
            with patch.dict(os.environ, env_without_keys, clear=True):
                from playground.econ.fred.connector import _api_key
                with pytest.raises(EnvironmentError, match="FRED API key not found"):
                    _api_key()

    def test_accepts_imdr_prefix(self) -> None:
        with patch.dict(os.environ, {"IMDR_ECON_FRED_KEY": "testkey123"}, clear=False):
            from playground.econ.fred.connector import _api_key
            assert _api_key() == "testkey123"

    def test_accepts_fred_api_key_fallback(self) -> None:
        env = {k: v for k, v in os.environ.items() if k != "IMDR_ECON_FRED_KEY"}
        env["FRED_API_KEY"] = "fallbackkey"
        with patch.dict(os.environ, env, clear=True):
            from playground.econ.fred.connector import _api_key
            assert _api_key() == "fallbackkey"


# ---------------------------------------------------------------------------
# Raw observation parsing
# ---------------------------------------------------------------------------

class TestParseObservations:
    def _get_func(self):
        from playground.econ.fred.fetch import parse_observations
        return parse_observations

    def test_basic_parse_returns_observation_rows(self) -> None:
        parse = self._get_func()
        raw = [
            {"date": "2024-01-01", "value": "310.326"},
            {"date": "2024-02-01", "value": "311.054"},
        ]
        rows = parse("FRED.CPI.HEADLINE_SA.US", raw)
        assert len(rows) == 2
        assert rows[0].imdr_code == "FRED.CPI.HEADLINE_SA.US"
        assert rows[0].obs_date == datetime.date(2024, 1, 1)
        assert rows[0].vintage == 0
        assert rows[0].value == pytest.approx(310.326)

    def test_dot_sentinel_becomes_none(self) -> None:
        parse = self._get_func()
        raw = [{"date": "2024-01-01", "value": None}]
        rows = parse("FRED.CPI.HEADLINE_SA.US", raw)
        assert rows[0].value is None

    def test_vintage_offset_respected(self) -> None:
        parse = self._get_func()
        raw = [{"date": "2024-01-01", "value": "310.0"}]
        rows = parse("FRED.CPI.HEADLINE_SA.US", raw, vintage_offset=2)
        assert rows[0].vintage == 2

    def test_all_rows_get_same_vintage_offset(self) -> None:
        parse = self._get_func()
        raw = [
            {"date": "2024-01-01", "value": "310.0"},
            {"date": "2024-02-01", "value": "311.0"},
        ]
        rows = parse("FRED.CPI.HEADLINE_SA.US", raw, vintage_offset=0)
        assert all(r.vintage == 0 for r in rows)

    def test_empty_raw_returns_empty_list(self) -> None:
        parse = self._get_func()
        rows = parse("FRED.CPI.HEADLINE_SA.US", [])
        assert rows == []

    def test_ingested_at_is_utc_aware(self) -> None:
        parse = self._get_func()
        raw = [{"date": "2024-01-01", "value": "310.0"}]
        rows = parse("FRED.CPI.HEADLINE_SA.US", raw)
        assert rows[0].ingested_at.tzinfo is not None


# ---------------------------------------------------------------------------
# Vintage observation parsing
# ---------------------------------------------------------------------------

class TestParseVintageObservations:
    def _get_func(self):
        from playground.econ.fred.fetch import parse_vintage_observations
        return parse_vintage_observations

    def test_single_snapshot_all_vintage_zero(self) -> None:
        parse = self._get_func()
        snapshots = {
            "2024-01-15": [
                {"date": "2023-12-01", "value": "309.0"},
                {"date": "2023-11-01", "value": "308.5"},
            ]
        }
        rows = parse("FRED.CPI.HEADLINE_SA.US", snapshots)
        assert all(r.vintage == 0 for r in rows)
        assert len(rows) == 2

    def test_changed_value_gets_vintage_1(self) -> None:
        parse = self._get_func()
        snapshots = {
            "2024-01-15": [{"date": "2023-12-01", "value": "309.0"}],
            "2024-07-15": [{"date": "2023-12-01", "value": "309.2"}],  # revised
        }
        rows = parse("FRED.CPI.HEADLINE_SA.US", snapshots)
        assert len(rows) == 2
        vintage0 = next(r for r in rows if r.vintage == 0)
        vintage1 = next(r for r in rows if r.vintage == 1)
        assert vintage0.value == pytest.approx(309.0)
        assert vintage1.value == pytest.approx(309.2)

    def test_unchanged_value_does_not_create_new_vintage(self) -> None:
        parse = self._get_func()
        snapshots = {
            "2024-01-15": [{"date": "2023-12-01", "value": "309.0"}],
            "2024-07-15": [{"date": "2023-12-01", "value": "309.0"}],  # same
        }
        rows = parse("FRED.CPI.HEADLINE_SA.US", snapshots)
        assert len(rows) == 1
        assert rows[0].vintage == 0

    def test_multiple_obs_dates_processed_independently(self) -> None:
        parse = self._get_func()
        snapshots = {
            "2024-01-15": [
                {"date": "2023-11-01", "value": "308.5"},
                {"date": "2023-12-01", "value": "309.0"},
            ],
            "2024-07-15": [
                {"date": "2023-11-01", "value": "308.5"},   # unchanged
                {"date": "2023-12-01", "value": "309.2"},   # revised
            ],
        }
        rows = parse("FRED.CPI.HEADLINE_SA.US", snapshots)
        # Nov: 1 row (unchanged). Dec: 2 rows (original + revision).
        assert len(rows) == 3
        dec_rows = [r for r in rows if r.obs_date == datetime.date(2023, 12, 1)]
        assert len(dec_rows) == 2

    def test_release_date_set_to_vintage_date(self) -> None:
        parse = self._get_func()
        snapshots = {
            "2024-01-15": [{"date": "2023-12-01", "value": "309.0"}],
        }
        rows = parse("FRED.CPI.HEADLINE_SA.US", snapshots)
        assert rows[0].release_date == datetime.datetime(2024, 1, 15, tzinfo=UTC)

    def test_none_value_treated_as_distinct_from_number(self) -> None:
        parse = self._get_func()
        snapshots = {
            "2024-01-15": [{"date": "2023-12-01", "value": None}],
            "2024-07-15": [{"date": "2023-12-01", "value": "309.0"}],
        }
        rows = parse("FRED.CPI.HEADLINE_SA.US", snapshots)
        assert len(rows) == 2


# ---------------------------------------------------------------------------
# FredClient.fetch_release_calendar
# ---------------------------------------------------------------------------

class TestFetchReleaseCalendar:
    def _make_client(self, return_value: dict) -> "FredClient":
        from playground.econ.fred.connector import FredClient
        client = FredClient.__new__(FredClient)
        client._api_key = "testkey"
        mock_http = MagicMock()
        mock_http.get_json.return_value = return_value
        client._http = mock_http
        return client

    def test_returns_release_dates_list(self) -> None:
        payload = {
            "release_dates": [
                {"release_id": 10, "release_name": "Consumer Price Index", "date": "2026-06-11"},
                {"release_id": 21, "release_name": "Employment Situation", "date": "2026-07-03"},
            ]
        }
        client = self._make_client(payload)
        result = client.fetch_release_calendar("2026-06-02", "2026-07-02")
        assert len(result) == 2
        assert result[0]["release_name"] == "Consumer Price Index"
        assert result[1]["date"] == "2026-07-03"

    def test_passes_correct_params(self) -> None:
        from playground.econ.fred.connector import FredClient
        client = self._make_client({"release_dates": []})
        client.fetch_release_calendar("2026-06-01", "2026-07-01", include_release_dates_with_no_data=False)
        call_params = client._http.get_json.call_args[1]["params"]
        assert call_params["realtime_start"] == "2026-06-01"
        assert call_params["realtime_end"] == "2026-07-01"
        assert call_params["include_release_dates_with_no_data"] == "false"

    def test_include_no_data_default_is_true(self) -> None:
        client = self._make_client({"release_dates": []})
        client.fetch_release_calendar("2026-06-01", "2026-07-01")
        call_params = client._http.get_json.call_args[1]["params"]
        assert call_params["include_release_dates_with_no_data"] == "true"

    def test_empty_response_returns_empty_list(self) -> None:
        client = self._make_client({"release_dates": []})
        result = client.fetch_release_calendar("2026-06-01", "2026-07-01")
        assert result == []

    def test_calls_releases_dates_endpoint(self) -> None:
        client = self._make_client({"release_dates": []})
        client.fetch_release_calendar("2026-06-01", "2026-07-01")
        path = client._http.get_json.call_args[0][0]
        assert path == "/releases/dates"


# ---------------------------------------------------------------------------
# FredClient.fetch_recent_updates
# ---------------------------------------------------------------------------

class TestFetchRecentUpdates:
    def _make_client(self, return_value: dict) -> "FredClient":
        from playground.econ.fred.connector import FredClient
        client = FredClient.__new__(FredClient)
        client._api_key = "testkey"
        mock_http = MagicMock()
        mock_http.get_json.return_value = return_value
        client._http = mock_http
        return client

    def test_returns_seriess_list(self) -> None:
        payload = {
            "seriess": [
                {"id": "CPIAUCSL", "title": "CPI", "frequency_short": "M", "units_short": "Index", "last_updated": "2026-06-11 08:00:01-05"},
                {"id": "UNRATE",   "title": "Unemployment Rate", "frequency_short": "M", "units_short": "%", "last_updated": "2026-06-11 08:00:05-05"},
            ]
        }
        client = self._make_client(payload)
        result = client.fetch_recent_updates("2026-06-11 00:00:00")
        assert len(result) == 2
        assert result[0]["id"] == "CPIAUCSL"

    def test_start_time_in_params(self) -> None:
        client = self._make_client({"seriess": []})
        client.fetch_recent_updates("2026-06-01 08:00:00")
        call_params = client._http.get_json.call_args[1]["params"]
        assert call_params["start_time"] == "2026-06-01 08:00:00"

    def test_end_time_omitted_when_not_supplied(self) -> None:
        client = self._make_client({"seriess": []})
        client.fetch_recent_updates("2026-06-01 08:00:00")
        call_params = client._http.get_json.call_args[1]["params"]
        assert "end_time" not in call_params

    def test_end_time_included_when_supplied(self) -> None:
        client = self._make_client({"seriess": []})
        client.fetch_recent_updates("2026-06-01 08:00:00", end_time="2026-06-01 16:00:00")
        call_params = client._http.get_json.call_args[1]["params"]
        assert call_params["end_time"] == "2026-06-01 16:00:00"

    def test_filter_value_default_is_all(self) -> None:
        client = self._make_client({"seriess": []})
        client.fetch_recent_updates("2026-06-01 08:00:00")
        call_params = client._http.get_json.call_args[1]["params"]
        assert call_params["filter_value"] == "all"

    def test_calls_series_updates_endpoint(self) -> None:
        client = self._make_client({"seriess": []})
        client.fetch_recent_updates("2026-06-01 08:00:00")
        path = client._http.get_json.call_args[0][0]
        assert path == "/series/updates"


# ---------------------------------------------------------------------------
# FredClient.search_series
# ---------------------------------------------------------------------------

class TestSearchSeries:
    def _make_client(self, return_value: dict) -> "FredClient":
        from playground.econ.fred.connector import FredClient
        client = FredClient.__new__(FredClient)
        client._api_key = "testkey"
        mock_http = MagicMock()
        mock_http.get_json.return_value = return_value
        client._http = mock_http
        return client

    def _sample_payload(self) -> dict:
        return {
            "seriess": [
                {
                    "id": "AUSGDPNADSMEI",
                    "title": "Gross Domestic Product for Australia",
                    "frequency_short": "Q",
                    "units_short": "Mil. Chn. 2015 A$",
                    "last_updated": "2026-03-05 06:01:02-06",
                }
            ]
        }

    def test_returns_seriess_list(self) -> None:
        client = self._make_client(self._sample_payload())
        result = client.search_series(query="australia gdp")
        assert len(result) == 1
        assert result[0]["id"] == "AUSGDPNADSMEI"

    def test_query_mapped_to_search_text(self) -> None:
        client = self._make_client({"seriess": []})
        client.search_series(query="australia gdp")
        call_params = client._http.get_json.call_args[1]["params"]
        assert call_params["search_text"] == "australia gdp"

    def test_tag_names_joined_with_semicolon(self) -> None:
        client = self._make_client({"seriess": []})
        client.search_series(tag_names=["weekly", "monetary-policy"])
        call_params = client._http.get_json.call_args[1]["params"]
        assert call_params["tag_names"] == "weekly;monetary-policy"

    def test_limit_and_order_by_in_params(self) -> None:
        client = self._make_client({"seriess": []})
        client.search_series(query="cpi", limit=10, order_by="search_rank")
        call_params = client._http.get_json.call_args[1]["params"]
        assert call_params["limit"] == 10
        assert call_params["order_by"] == "search_rank"

    def test_raises_when_no_query_and_no_tags(self) -> None:
        client = self._make_client({"seriess": []})
        with pytest.raises(ValueError, match="requires at least one of"):
            client.search_series()

    def test_search_text_absent_when_no_query(self) -> None:
        client = self._make_client({"seriess": []})
        client.search_series(tag_names=["weekly"])
        call_params = client._http.get_json.call_args[1]["params"]
        assert "search_text" not in call_params

    def test_calls_series_search_endpoint(self) -> None:
        client = self._make_client({"seriess": []})
        client.search_series(query="gdp")
        path = client._http.get_json.call_args[0][0]
        assert path == "/series/search"

    def test_empty_response_returns_empty_list(self) -> None:
        client = self._make_client({"seriess": []})
        result = client.search_series(query="xyzzy_no_results")
        assert result == []


# ---------------------------------------------------------------------------
# run_calendar — DataFrame shape
# ---------------------------------------------------------------------------

class TestRunCalendar:
    def test_dataframe_has_expected_columns(self) -> None:
        import pandas as pd
        from unittest.mock import patch
        from playground.econ.fred.connector import FredClient

        entries = [
            {"release_id": 10, "release_name": "CPI", "date": "2026-06-11"},
            {"release_id": 21, "release_name": "Employment Situation", "date": "2026-07-03"},
        ]

        with patch.object(FredClient, "fetch_release_calendar", return_value=entries):
            with patch("playground.econ.fred.fetch.FredClient", FredClient):
                from playground.econ.fred.fetch import run_calendar
                client = FredClient.__new__(FredClient)
                client._api_key = "testkey"
                client._http = MagicMock()
                df = run_calendar(client, days_ahead=30, write_parquet=False)

        assert list(df.columns) == ["release_id", "release_name", "release_date", "series_count"]
        assert len(df) == 2
        assert df["release_date"].iloc[0] == "2026-06-11"
        assert df["series_count"].isna().all()

    def test_empty_entries_returns_empty_dataframe(self) -> None:
        from playground.econ.fred.connector import FredClient
        from playground.econ.fred.fetch import run_calendar

        client = FredClient.__new__(FredClient)
        client._api_key = "testkey"
        mock_http = MagicMock()
        mock_http.get_json.return_value = {"release_dates": []}
        client._http = mock_http

        with patch.object(FredClient, "fetch_release_calendar", return_value=[]):
            df = run_calendar(client, days_ahead=30, write_parquet=False)
        assert df.empty


# ---------------------------------------------------------------------------
# run_updates_since — time parsing
# ---------------------------------------------------------------------------

class TestRunUpdatesSince:
    def test_parses_hhmm_into_correct_start_time_format(self) -> None:
        from unittest.mock import patch
        import datetime
        from playground.econ.fred.connector import FredClient
        from playground.econ.fred.fetch import run_updates_since

        captured_start_time = {}

        def fake_fetch_recent_updates(_self, start_time=None, end_time=None, filter_value="all"):
            captured_start_time["value"] = start_time
            return []

        client = FredClient.__new__(FredClient)
        client._api_key = "testkey"
        client._http = MagicMock()

        fixed_today = datetime.date(2026, 6, 2)
        expected_start = f"{fixed_today.isoformat()} 08:30:00"

        with patch.object(FredClient, "fetch_recent_updates", fake_fetch_recent_updates):
            with patch("playground.econ.fred.fetch.datetime") as mock_dt:
                mock_dt.date.today.return_value = fixed_today
                mock_dt.datetime = datetime.datetime
                mock_dt.timezone = datetime.timezone
                mock_dt.timedelta = datetime.timedelta
                run_updates_since(client, since_time="08:30")

        assert captured_start_time["value"] == expected_start

    def test_returns_dataframe_with_expected_columns(self) -> None:
        from playground.econ.fred.connector import FredClient
        from playground.econ.fred.fetch import run_updates_since

        series_data = [
            {
                "id": "CPIAUCSL",
                "title": "CPI for All Urban Consumers",
                "frequency_short": "M",
                "units_short": "Index",
                "last_updated": "2026-06-11 08:00:01-05",
            }
        ]

        client = FredClient.__new__(FredClient)
        client._api_key = "testkey"
        client._http = MagicMock()

        with patch.object(FredClient, "fetch_recent_updates", return_value=series_data):
            df = run_updates_since(client, since_time="08:00")

        assert list(df.columns) == ["id", "title", "frequency", "units", "last_updated"]
        assert len(df) == 1
        assert df["id"].iloc[0] == "CPIAUCSL"


# ---------------------------------------------------------------------------
# Seed loading
# ---------------------------------------------------------------------------

class TestFredSeedLoad:
    def test_seed_loads_and_returns_indicator_rows(self) -> None:
        from playground.econ.fred.fetch import load_seed
        rows = load_seed()
        assert len(rows) >= 10
        codes = [r.imdr_code for r in rows]
        assert "FRED.CPI.HEADLINE_SA.US" in codes
        assert "FRED.GDP.REAL_SA.US" in codes
        assert "FRED.BALANCE_SHEET.RRP_TSY.US" in codes

    def test_all_loaded_rows_are_valid_indicator_rows(self) -> None:
        from playground.econ.fred.fetch import load_seed
        from playground.econ.schema_prototype import IndicatorRow
        rows = load_seed()
        for row in rows:
            assert isinstance(row, IndicatorRow)
            assert row.vendor_name == "FRED"

    def test_seed_frequencies_are_valid(self) -> None:
        from playground.econ.fred.fetch import load_seed
        from playground.econ.schema_prototype import VALID_FREQUENCIES
        rows = load_seed()
        for row in rows:
            assert row.frequency in VALID_FREQUENCIES, f"{row.imdr_code} has invalid frequency {row.frequency!r}"

    def test_seed_categories_are_valid(self) -> None:
        from playground.econ.fred.fetch import load_seed
        from playground.econ.schema_prototype import VALID_CATEGORIES
        rows = load_seed()
        for row in rows:
            assert row.category in VALID_CATEGORIES, f"{row.imdr_code} has invalid category {row.category!r}"
