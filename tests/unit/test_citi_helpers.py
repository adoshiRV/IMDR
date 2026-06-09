"""Tests for the shared Citi Velocity helpers."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from imdr.connectors.citi_helpers import (
    TagQuotaExceeded,
    _collect_tag_errors,
    _fetch_with_retry,
    _parse_quota_error,
    citi_response_to_rows,
    parse_x_to_ts_utc,
    summarize_tag_errors,
)
from imdr.connectors.citi_velocity import CitiAPIError


# ── parse_x_to_ts_utc ────────────────────────────────────────────────────────


class TestParseXToTsUtc:
    def test_yyyymmdd_daily(self) -> None:
        assert parse_x_to_ts_utc(20260514) == datetime(2026, 5, 14, tzinfo=timezone.utc)

    def test_yyyymmddhh_hourly(self) -> None:
        assert parse_x_to_ts_utc(2026051410) == datetime(2026, 5, 14, 10, tzinfo=timezone.utc)

    def test_yyyymmddhhmm_minutely(self) -> None:
        assert parse_x_to_ts_utc(202605141045) == datetime(
            2026, 5, 14, 10, 45, tzinfo=timezone.utc
        )

    def test_yyyymmddhhm_ten_minutely(self) -> None:
        # 11-digit format: last digit = tens of minutes
        # 20260514104 → 2026-05-14 10:40
        assert parse_x_to_ts_utc(20260514104) == datetime(
            2026, 5, 14, 10, 40, tzinfo=timezone.utc
        )

    def test_yyyymm_monthly(self) -> None:
        # 6-digit format with mm in 01..12 → monthly
        assert parse_x_to_ts_utc(202605) == datetime(2026, 5, 1, tzinfo=timezone.utc)

    def test_yyyyww_weekly_fallback(self) -> None:
        # 6-digit format with mm > 12 → ISO week parser
        # 202614 = year 2026, week 14, monday → 2026-03-30
        result = parse_x_to_ts_utc(202614)
        assert result.tzinfo == timezone.utc
        assert result.year == 2026

    def test_unrecognized_length_raises(self) -> None:
        with pytest.raises(ValueError, match="Unrecognized x timestamp format"):
            parse_x_to_ts_utc(12345)  # 5 digits — not a valid format


# ── citi_response_to_rows ────────────────────────────────────────────────────


class TestCitiResponseToRows:
    def _ok_resp(self, body: dict) -> dict:
        return {"status": "OK", "body": body}

    def test_happy_path_returns_rows(self) -> None:
        resp = self._ok_resp({
            "TAG.A.CITI": {"x": [20260101, 20260102], "c": [1.0, 2.0]},
        })
        rows = citi_response_to_rows(resp, tag_parser=lambda t: {"tag": t})
        assert len(rows) == 2
        assert rows[0]["value"] == 1.0
        assert rows[0]["tag"] == "TAG.A.CITI"
        assert rows[0]["ts"] == datetime(2026, 1, 1, tzinfo=timezone.utc)

    def test_skips_none_values(self) -> None:
        resp = self._ok_resp({
            "T": {"x": [20260101, 20260102, 20260103], "c": [1.0, None, 3.0]},
        })
        rows = citi_response_to_rows(resp, tag_parser=lambda t: {"tag": t})
        assert len(rows) == 2
        assert all(r["value"] is not None for r in rows)

    def test_error_series_skipped(self) -> None:
        resp = self._ok_resp({
            "GOOD": {"x": [20260101], "c": [1.0]},
            "BAD": {"type": "ERROR", "message": "unsupported tag"},
        })
        rows = citi_response_to_rows(resp, tag_parser=lambda t: {"tag": t})
        assert len(rows) == 1
        assert rows[0]["tag"] == "GOOD"

    def test_unparseable_tag_skipped(self) -> None:
        resp = self._ok_resp({
            "TAG.A": {"x": [20260101], "c": [1.0]},
            "TAG.B": {"x": [20260101], "c": [1.0]},
        })

        def selective_parser(tag: str) -> dict | None:
            return {"tag": tag} if tag.endswith(".A") else None

        rows = citi_response_to_rows(resp, tag_parser=selective_parser)
        assert len(rows) == 1
        assert rows[0]["tag"] == "TAG.A"

    def test_non_ok_status_raises(self) -> None:
        resp = {"status": "ERROR", "message": "internal server error"}
        with pytest.raises(RuntimeError, match="API status not OK"):
            citi_response_to_rows(resp, tag_parser=lambda t: {"tag": t})

    def test_quota_message_raises_tag_quota_exceeded(self) -> None:
        resp = {
            "status": "ERROR",
            "message": "Exceeded max tag count. Current usage: 95001 Available usage: 0",
        }
        with pytest.raises(TagQuotaExceeded) as exc_info:
            citi_response_to_rows(resp, tag_parser=lambda t: {"tag": t})
        assert exc_info.value.current_usage == 95001
        assert exc_info.value.available == 0


# ── _parse_quota_error ───────────────────────────────────────────────────────


class TestParseQuotaError:
    def test_recognizes_canonical_message(self) -> None:
        err = _parse_quota_error({
            "message": "Exceeded max tag count. Current usage: 100000 Available usage: 0",
        })
        assert err is not None
        assert err.current_usage == 100000
        assert err.available == 0

    def test_returns_none_for_unrelated_error(self) -> None:
        assert _parse_quota_error({"message": "bad request"}) is None

    def test_handles_missing_match_groups(self) -> None:
        err = _parse_quota_error({"message": "max tag count exceeded"})
        assert err is not None
        # No numeric matches → fields default to None
        assert err.current_usage is None
        assert err.available is None


# ── _collect_tag_errors + summarize_tag_errors ───────────────────────────────


class TestCollectTagErrors:
    def test_response_level_error(self) -> None:
        sink: list[dict] = []
        _collect_tag_errors({"status": "ERROR", "message": "bad gateway"}, sink)
        assert len(sink) == 1
        assert sink[0]["type"] == "RESPONSE"
        assert sink[0]["message"] == "bad gateway"

    def test_per_tag_error_type(self) -> None:
        sink: list[dict] = []
        _collect_tag_errors({
            "status": "OK",
            "body": {"T": {"type": "ERROR", "message": "rate limited"}},
        }, sink)
        assert len(sink) == 1
        assert sink[0]["type"] == "ERROR"
        assert sink[0]["tag"] == "T"

    def test_empty_payload(self) -> None:
        sink: list[dict] = []
        _collect_tag_errors({
            "status": "OK",
            "body": {"T": {"x": [], "c": []}},
        }, sink)
        assert len(sink) == 1
        assert sink[0]["type"] == "EMPTY"

    def test_malformed_series_value(self) -> None:
        sink: list[dict] = []
        _collect_tag_errors({"status": "OK", "body": {"T": "not a dict"}}, sink)
        assert len(sink) == 1
        assert sink[0]["type"] == "MALFORMED"

    def test_healthy_series_not_recorded(self) -> None:
        sink: list[dict] = []
        _collect_tag_errors({
            "status": "OK",
            "body": {"T": {"x": [20260101], "c": [1.0]}},
        }, sink)
        assert sink == []


class TestSummarizeTagErrors:
    def test_empty_input(self) -> None:
        assert summarize_tag_errors([]) == []

    def test_groups_by_type_and_message(self) -> None:
        entries = [
            {"tag": "A", "type": "ERROR", "message": "rate limit"},
            {"tag": "B", "type": "ERROR", "message": "rate limit"},
            {"tag": "C", "type": "EMPTY", "message": None},
        ]
        summary = summarize_tag_errors(entries)
        assert len(summary) == 2
        # Sorted by descending count
        assert summary[0]["count"] == 2
        assert summary[0]["type"] == "ERROR"
        assert set(summary[0]["sample_tags"]) == {"A", "B"}
        assert summary[1]["count"] == 1
        assert summary[1]["message"] == "(no message)"

    def test_sample_size_limit(self) -> None:
        entries = [
            {"tag": f"T{i}", "type": "ERROR", "message": "x"} for i in range(10)
        ]
        summary = summarize_tag_errors(entries, sample_size=3)
        assert summary[0]["count"] == 10
        assert len(summary[0]["sample_tags"]) == 3


# ── _fetch_with_retry ────────────────────────────────────────────────────────


class TestFetchWithRetry:
    def test_success_on_first_try(self) -> None:
        client = MagicMock()
        client.fetch_historical.return_value = {"status": "OK", "body": {}}

        result = _fetch_with_retry(
            client, ["T"], datetime(2026, 1, 1, tzinfo=timezone.utc),
            datetime(2026, 1, 2, tzinfo=timezone.utc), "DAILY", 1, 1,
        )
        assert result == {"status": "OK", "body": {}}
        assert client.fetch_historical.call_count == 1

    @patch("imdr.connectors.citi_helpers.time.sleep")
    def test_retries_on_5xx_then_succeeds(self, mock_sleep: MagicMock) -> None:
        client = MagicMock()
        client.fetch_historical.side_effect = [
            CitiAPIError("gateway", status_code=503),
            {"status": "OK", "body": {}},
        ]
        result = _fetch_with_retry(
            client, ["T"], datetime(2026, 1, 1, tzinfo=timezone.utc),
            datetime(2026, 1, 2, tzinfo=timezone.utc), "DAILY", 1, 1,
        )
        assert result == {"status": "OK", "body": {}}
        assert client.fetch_historical.call_count == 2
        mock_sleep.assert_called_once_with(5.0)  # first retry delay

    def test_4xx_propagates_without_retry(self) -> None:
        client = MagicMock()
        client.fetch_historical.side_effect = CitiAPIError("bad request", status_code=400)
        with pytest.raises(CitiAPIError):
            _fetch_with_retry(
                client, ["T"], datetime(2026, 1, 1, tzinfo=timezone.utc),
                datetime(2026, 1, 2, tzinfo=timezone.utc), "DAILY", 1, 1,
            )
        assert client.fetch_historical.call_count == 1
