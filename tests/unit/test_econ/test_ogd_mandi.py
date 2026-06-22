"""Tests for src/imdr/domains/econ/ogd_mandi.py.

Network-free. Exercises:
  - _parse_arrival_date: valid format, wrong format, error message.
  - _parse_price: numeric, blank, NR, dash, zero, negative.
  - normalise_record: full record, grade normalisation, trimming.
  - load_key: env-var path, .env fallback, missing-key error (exact message).
  - iter_pages_for_date: offset progression, stop on short page, stop on empty.
  - _get_page: retryable status retried, non-retryable raises redacted RuntimeError (key never leaks).
  - load_rows: MERGE path, missing country guard, dim deduplication.
  - _REPO_ROOT depth: both lib and playground resolve to the repo root.
  - iter_pages_for_date: _MAX_PAGES_PER_DAY sentinel stops infinite loop.
"""

from __future__ import annotations

import datetime
import os
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest
import requests

from imdr.domains.econ.ogd_mandi import (
    _MAX_PAGES_PER_DAY,
    _PAGE_SIZE,
    _REPO_ROOT,
    _get_page,
    _parse_arrival_date,
    _parse_price,
    iter_pages_for_date,
    load_key,
    normalise_record,
)


# ---------------------------------------------------------------------------
# _parse_arrival_date
# ---------------------------------------------------------------------------

class TestParseArrivalDate:
    def test_parses_ddmmyyyy(self) -> None:
        assert _parse_arrival_date("15/06/2026") == datetime.date(2026, 6, 15)

    def test_parses_with_surrounding_whitespace(self) -> None:
        assert _parse_arrival_date("  01/01/2020  ") == datetime.date(2020, 1, 1)

    def test_raises_value_error_on_wrong_format(self) -> None:
        with pytest.raises(ValueError) as excinfo:
            _parse_arrival_date("2026-06-15")
        assert "OGD Arrival_Date has unexpected format: '2026-06-15'" in str(excinfo.value)
        assert "expected DD/MM/YYYY" in str(excinfo.value)

    def test_raises_value_error_on_empty(self) -> None:
        with pytest.raises(ValueError) as excinfo:
            _parse_arrival_date("")
        assert "OGD Arrival_Date has unexpected format: ''" in str(excinfo.value)

    def test_raises_value_error_on_garbage(self) -> None:
        with pytest.raises(ValueError) as excinfo:
            _parse_arrival_date("not-a-date")
        assert "OGD Arrival_Date has unexpected format: 'not-a-date'" in str(excinfo.value)

    def test_raises_on_yyyymmdd(self) -> None:
        with pytest.raises(ValueError):
            _parse_arrival_date("20260615")


# ---------------------------------------------------------------------------
# _parse_price
# ---------------------------------------------------------------------------

class TestParsePrice:
    def test_integer_string(self) -> None:
        assert _parse_price("1200") == Decimal("1200")

    def test_decimal_string(self) -> None:
        assert _parse_price("1234.50") == Decimal("1234.50")

    def test_blank_string_returns_none(self) -> None:
        assert _parse_price("") is None

    def test_nr_returns_none(self) -> None:
        assert _parse_price("NR") is None
        assert _parse_price("nr") is None

    def test_dash_returns_none(self) -> None:
        assert _parse_price("-") is None

    def test_zero_string_returns_none(self) -> None:
        assert _parse_price("0") is None
        assert _parse_price("0.0") is None
        assert _parse_price("0.00") is None

    def test_none_input_returns_none(self) -> None:
        assert _parse_price(None) is None

    def test_na_returns_none(self) -> None:
        assert _parse_price("N/A") is None
        assert _parse_price("n/a") is None

    def test_negative_returns_none(self) -> None:
        assert _parse_price("-500") is None

    def test_garbage_string_returns_none(self) -> None:
        assert _parse_price("abc") is None

    def test_integer_input_coerces(self) -> None:
        assert _parse_price(1500) == Decimal("1500")

    def test_float_input_coerces(self) -> None:
        result = _parse_price(1234.5)
        assert result is not None
        assert float(result) == pytest.approx(1234.5)


# ---------------------------------------------------------------------------
# normalise_record
# ---------------------------------------------------------------------------

class TestNormaliseRecord:
    def _raw(self, **overrides) -> dict:
        base = {
            "Arrival_Date": "15/06/2026",
            "State": " Maharashtra ",
            "District": "Pune",
            "Market": "  Pune Mkt  ",
            "Commodity": "Wheat",
            "Commodity_Code": "W001",
            "Variety": "Lokwan",
            "Grade": "FAQ",
            "Min_Price": "1800",
            "Max_Price": "2200",
            "Modal_Price": "2000",
        }
        base.update(overrides)
        return base

    def test_full_valid_record(self) -> None:
        result = normalise_record(self._raw())
        assert result["arrival_date"] == datetime.date(2026, 6, 15)
        assert result["state"] == "Maharashtra"
        assert result["market"] == "Pune Mkt"
        assert result["commodity"] == "Wheat"
        assert result["variety"] == "Lokwan"
        assert result["grade"] == ""          # FAQ → '' (null-sentinel normalised to empty string)
        assert result["min_price"] == Decimal("1800")
        assert result["max_price"] == Decimal("2200")
        assert result["modal_price"] == Decimal("2000")

    def test_names_are_stripped(self) -> None:
        result = normalise_record(self._raw(
            State="  Rajasthan  ",
            Market="\tJaipur\t",
        ))
        assert result["state"] == "Rajasthan"
        assert result["market"] == "Jaipur"

    def test_grade_nr_becomes_empty_string(self) -> None:
        result = normalise_record(self._raw(Grade="NR"))
        assert result["grade"] == ""

    def test_grade_dash_becomes_empty_string(self) -> None:
        result = normalise_record(self._raw(Grade="-"))
        assert result["grade"] == ""

    def test_grade_blank_becomes_empty_string(self) -> None:
        result = normalise_record(self._raw(Grade=""))
        assert result["grade"] == ""

    def test_grade_real_value_preserved(self) -> None:
        result = normalise_record(self._raw(Grade="Grade A"))
        assert result["grade"] == "Grade A"

    def test_blank_prices_become_none(self) -> None:
        result = normalise_record(self._raw(Min_Price="", Max_Price="NR", Modal_Price="-"))
        assert result["min_price"] is None
        assert result["max_price"] is None
        assert result["modal_price"] is None

    def test_raises_on_bad_date(self) -> None:
        with pytest.raises(ValueError) as excinfo:
            normalise_record(self._raw(Arrival_Date="2026-06-15"))
        assert "OGD Arrival_Date has unexpected format" in str(excinfo.value)

    def test_commodity_code_stripped(self) -> None:
        result = normalise_record(self._raw(Commodity_Code="  W001  "))
        assert result["commodity_code"] == "W001"


# ---------------------------------------------------------------------------
# load_key
# ---------------------------------------------------------------------------

class TestLoadKey:
    def test_returns_env_var_when_set(self) -> None:
        with patch.dict(os.environ, {"IMDR_DATA_GOV_IN_API_KEY": "testkey-abc"}, clear=False):
            assert load_key() == "testkey-abc"

    def test_raises_with_exact_message_when_missing(self, tmp_path, monkeypatch) -> None:
        monkeypatch.delenv("IMDR_DATA_GOV_IN_API_KEY", raising=False)
        import imdr.domains.econ.ogd_mandi as mod
        monkeypatch.setattr(mod, "_REPO_ROOT", tmp_path)
        with pytest.raises(RuntimeError) as excinfo:
            load_key()
        assert str(excinfo.value) == "IMDR_DATA_GOV_IN_API_KEY not set in env or .env"

    def test_falls_back_to_dotenv(self, tmp_path, monkeypatch) -> None:
        monkeypatch.delenv("IMDR_DATA_GOV_IN_API_KEY", raising=False)
        env_file = tmp_path / ".env"
        env_file.write_text(
            "OTHER_VAR=foo\nIMDR_DATA_GOV_IN_API_KEY=dotenv-xyz\n",
            encoding="utf-8",
        )
        import imdr.domains.econ.ogd_mandi as mod
        monkeypatch.setattr(mod, "_REPO_ROOT", tmp_path)
        assert load_key() == "dotenv-xyz"

    def test_empty_env_var_falls_through_to_dotenv(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("IMDR_DATA_GOV_IN_API_KEY", "")
        env_file = tmp_path / ".env"
        env_file.write_text("IMDR_DATA_GOV_IN_API_KEY=from-dotenv\n", encoding="utf-8")
        import imdr.domains.econ.ogd_mandi as mod
        monkeypatch.setattr(mod, "_REPO_ROOT", tmp_path)
        assert load_key() == "from-dotenv"


# ---------------------------------------------------------------------------
# iter_pages_for_date — mocked HTTP
# ---------------------------------------------------------------------------

def _make_page(records: list[dict], total: int) -> dict:
    return {"total": total, "records": records}


def _make_record(i: int) -> dict:
    return {
        "Arrival_Date": "15/06/2026",
        "State": f"State{i}",
        "District": f"District{i}",
        "Market": f"Market{i}",
        "Commodity": "Wheat",
        "Commodity_Code": "W001",
        "Variety": "Lokwan",
        "Grade": "",
        "Min_Price": str(1000 + i),
        "Max_Price": str(2000 + i),
        "Modal_Price": str(1500 + i),
    }


class TestIterPagesForDate:
    def _session(self, pages: list[dict]) -> MagicMock:
        """Return a mock session whose _get_page calls yield successive pages."""
        return MagicMock()

    def test_single_short_page_stops(self, monkeypatch) -> None:
        """A page shorter than PAGE_SIZE signals the last page."""
        records = [_make_record(i) for i in range(5)]
        page = _make_page(records, 5)

        import imdr.domains.econ.ogd_mandi as mod
        monkeypatch.setattr(mod, "_get_page", lambda *a, **kw: page)
        monkeypatch.setattr(mod, "_THROTTLE_S", 0)

        session = MagicMock()
        results = list(iter_pages_for_date(session, "fakekey",
                                           datetime.date(2026, 6, 15)))
        assert len(results) == 1
        recs, total = results[0]
        assert len(recs) == 5
        assert total == 5

    def test_empty_page_stops_immediately(self, monkeypatch) -> None:
        page = _make_page([], 0)
        import imdr.domains.econ.ogd_mandi as mod
        monkeypatch.setattr(mod, "_get_page", lambda *a, **kw: page)
        monkeypatch.setattr(mod, "_THROTTLE_S", 0)

        results = list(iter_pages_for_date(MagicMock(), "fakekey",
                                           datetime.date(2026, 6, 15)))
        assert results == []

    def test_two_full_pages_then_short(self, monkeypatch) -> None:
        """PAGE_SIZE + PAGE_SIZE + N < PAGE_SIZE — three fetches total."""
        full_page = [_make_record(i) for i in range(_PAGE_SIZE)]
        short_page = [_make_record(i) for i in range(7)]

        call_count = 0
        offsets: list[int] = []

        def fake_get_page(session, key, *, offset, arrival_date=None, timeout=30):
            nonlocal call_count
            offsets.append(offset)
            call_count += 1
            if call_count <= 2:
                return _make_page(full_page, _PAGE_SIZE * 2 + 7)
            return _make_page(short_page, _PAGE_SIZE * 2 + 7)

        import imdr.domains.econ.ogd_mandi as mod
        monkeypatch.setattr(mod, "_get_page", fake_get_page)
        monkeypatch.setattr(mod, "_THROTTLE_S", 0)

        results = list(iter_pages_for_date(MagicMock(), "fakekey",
                                           datetime.date(2026, 6, 15)))
        assert len(results) == 3
        assert offsets == [0, _PAGE_SIZE, _PAGE_SIZE * 2]
        assert len(results[0][0]) == _PAGE_SIZE
        assert len(results[1][0]) == _PAGE_SIZE
        assert len(results[2][0]) == 7

    def test_date_formatted_as_ddmmyyyy_in_filter(self, monkeypatch) -> None:
        """Arrival_Date filter must be DD/MM/YYYY for the OGD API."""
        captured: list[str] = []

        def fake_get_page(session, key, *, offset, arrival_date=None, timeout=30):
            captured.append(arrival_date)
            return _make_page([], 0)

        import imdr.domains.econ.ogd_mandi as mod
        monkeypatch.setattr(mod, "_get_page", fake_get_page)
        monkeypatch.setattr(mod, "_THROTTLE_S", 0)

        list(iter_pages_for_date(MagicMock(), "key",
                                 datetime.date(2026, 6, 7)))
        assert captured == ["07/06/2026"]


# ---------------------------------------------------------------------------
# T1. API key must never appear in exception messages
# ---------------------------------------------------------------------------

class TestKeyNotInExceptionMessage:
    """T1: RuntimeError from retryable-status exhaustion must not contain the raw key."""

    def test_key_not_in_exception_message(self, monkeypatch) -> None:
        import imdr.domains.econ.ogd_mandi as mod

        secret_key = "SECRET-API-KEY-12345"

        # Build a mock response that always returns 429.
        mock_resp = MagicMock()
        mock_resp.status_code = 429

        mock_session = MagicMock()
        mock_session.get.return_value = mock_resp

        monkeypatch.setattr(mod, "_RETRIES", 1)
        monkeypatch.setattr(mod, "_RETRY_SLEEP_S", 0)

        with pytest.raises(RuntimeError) as excinfo:
            _get_page(mock_session, secret_key, offset=0)

        assert secret_key not in str(excinfo.value)
        assert "***REDACTED***" in str(excinfo.value)


# ---------------------------------------------------------------------------
# T2. Retryable HTTP statuses are retried; non-retryable 4xx propagate immediately
# ---------------------------------------------------------------------------

class TestRetryableHttpStatus:
    """T2: 429/502/503/504 are retried; 400/403 propagate on first attempt."""

    def test_429_is_retried_and_succeeds(self, monkeypatch) -> None:
        import imdr.domains.econ.ogd_mandi as mod

        call_count = 0

        def make_resp(status: int) -> MagicMock:
            resp = MagicMock()
            resp.status_code = status
            resp.json.return_value = {"total": 1, "records": [_make_record(0)]}
            resp.raise_for_status.side_effect = (
                None if status == 200
                else requests.exceptions.HTTPError(f"HTTP {status}", response=resp)
            )
            return resp

        def mock_get(url, params=None, timeout=30):
            nonlocal call_count
            call_count += 1
            return make_resp(429 if call_count == 1 else 200)

        mock_session = MagicMock()
        mock_session.get.side_effect = mock_get

        monkeypatch.setattr(mod, "_RETRY_SLEEP_S", 0)

        result = _get_page(mock_session, "fakekey", offset=0)
        assert call_count == 2
        assert result["total"] == 1

    def test_400_propagates_immediately_as_redacted_runtimeerror(self, monkeypatch) -> None:
        import imdr.domains.econ.ogd_mandi as mod

        secret_key = "SECRET-API-KEY-12345"
        call_count = 0

        def mock_get(url, params=None, timeout=30):
            nonlocal call_count
            call_count += 1
            resp = MagicMock()
            resp.status_code = 400
            # Simulate the REAL requests message, which embeds the full URL
            # (incl. ?api-key=...) — the leak the redaction must suppress.
            leaky = requests.exceptions.HTTPError(
                "400 Client Error: Bad Request for url: "
                f"https://api.data.gov.in/resource/X?api-key={secret_key}&format=json",
                response=resp,
            )
            resp.raise_for_status.side_effect = leaky
            return resp

        mock_session = MagicMock()
        mock_session.get.side_effect = mock_get
        monkeypatch.setattr(mod, "_RETRY_SLEEP_S", 0)

        # Non-retryable status now raises a REDACTED RuntimeError, not the raw
        # HTTPError (which would carry the key in its URL).
        with pytest.raises(RuntimeError) as excinfo:
            _get_page(mock_session, secret_key, offset=0)

        assert call_count == 1                       # not retried
        assert secret_key not in str(excinfo.value)  # key redacted
        assert excinfo.value.__cause__ is None        # chained original suppressed

    def test_403_propagates_immediately_as_redacted_runtimeerror(self, monkeypatch) -> None:
        import imdr.domains.econ.ogd_mandi as mod

        secret_key = "SECRET-API-KEY-12345"
        call_count = 0

        def mock_get(url, params=None, timeout=30):
            nonlocal call_count
            call_count += 1
            resp = MagicMock()
            resp.status_code = 403
            leaky = requests.exceptions.HTTPError(
                "403 Client Error: Forbidden for url: "
                f"https://api.data.gov.in/resource/X?api-key={secret_key}&format=json",
                response=resp,
            )
            resp.raise_for_status.side_effect = leaky
            return resp

        mock_session = MagicMock()
        mock_session.get.side_effect = mock_get
        monkeypatch.setattr(mod, "_RETRY_SLEEP_S", 0)

        with pytest.raises(RuntimeError) as excinfo:
            _get_page(mock_session, secret_key, offset=0)

        assert call_count == 1
        assert secret_key not in str(excinfo.value)
        assert excinfo.value.__cause__ is None


# ---------------------------------------------------------------------------
# Helpers: load the playground module by file path so sys.path hacks don't
# interfere with the test session. Each test that uses this helper gets a
# fresh module object.
# ---------------------------------------------------------------------------

def _load_playground_module(name: str = "pg_ogd_mandi"):
    import importlib.util
    pf = (
        Path(__file__).resolve().parents[3]
        / "playground" / "econ" / "in" / "ogd" / "ogd_mandi.py"
    )
    spec = importlib.util.spec_from_file_location(name, pf)
    pg = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pg)
    return pg


def _make_rows(n: int, same_market: bool = False) -> list[dict]:
    """Return n normalised rows. When same_market=False, rows cycle between
    two distinct markets so there are always 2 unique (state, district, market)
    tuples regardless of n (for n >= 2). All rows share one commodity."""
    return [
        {
            "arrival_date": datetime.date(2026, 6, 15),
            "state": "S",
            "district": "D",
            "market": "Market0" if same_market else f"Market{i % 2}",
            "commodity": "Wheat",
            "commodity_code": "W001",
            "variety": "Lokwan",
            "grade": "",
            "min_price": Decimal("1000"),
            "max_price": Decimal("2000"),
            "modal_price": Decimal("1500"),
        }
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# T3. load_rows MERGE path (mocked engine + DB)
# ---------------------------------------------------------------------------

class TestLoadRowsMergePath:
    """T3: load_rows calls _upsert_market/_upsert_commodity for unique dims
    and passes all enriched rows to _merge_fact_batch."""

    def test_load_rows_deduplicates_dims_and_merges_facts(self, monkeypatch) -> None:
        pg = _load_playground_module("pg_ogd_mandi_t3")

        # 3 rows: markets cycle Market0 / Market1 / Market0 → 2 unique markets,
        # 1 unique commodity.
        rows = _make_rows(3, same_market=False)

        upsert_market_calls: list[str] = []
        upsert_commodity_calls: list[str] = []
        merge_batch_calls: list[int] = []

        market_ids = iter([10, 11])

        def fake_upsert_market(conn, state, district, market, country_id):
            upsert_market_calls.append(market)
            return next(market_ids)

        def fake_upsert_commodity(conn, commodity, variety, grade, commodity_code):
            upsert_commodity_calls.append(commodity)
            return 99

        def fake_merge_fact_batch(conn, batch, vendor_id):
            merge_batch_calls.append(len(batch))
            return len(batch)

        # Build a mock conn whose execute() handles the two sequential SELECT
        # calls in pass-1 of load_rows: _resolve_vendor_id then dim_country.
        from contextlib import contextmanager

        def _make_row_mock(val):
            r = MagicMock()
            r.__getitem__ = lambda s, i: val
            return r

        execute_n = [0]

        def smart_execute(stmt, params=None):
            execute_n[0] += 1
            result = MagicMock()
            # load_rows pass-1 calls: (1) dim_country SELECT
            # (_resolve_vendor_id is patched out, so only 1 raw conn.execute)
            result.fetchone.return_value = _make_row_mock(42)  # country_id
            return result

        mock_conn = MagicMock()
        mock_conn.execute = smart_execute

        @contextmanager
        def fake_begin():
            yield mock_conn

        mock_engine = MagicMock()
        mock_engine.begin.side_effect = fake_begin

        monkeypatch.setattr(pg, "_get_load_engine", lambda: mock_engine)
        monkeypatch.setattr(pg, "_check_tables_exist", lambda e: True)
        monkeypatch.setattr(pg, "_resolve_vendor_id", lambda conn, vc: 7)
        monkeypatch.setattr(pg, "_upsert_market", fake_upsert_market)
        monkeypatch.setattr(pg, "_upsert_commodity", fake_upsert_commodity)
        monkeypatch.setattr(pg, "_merge_fact_batch", fake_merge_fact_batch)

        pg.load_rows(rows)

        assert len(upsert_market_calls) == 2, (
            f"Expected 2 _upsert_market calls (2 distinct markets), got {upsert_market_calls}"
        )
        assert len(upsert_commodity_calls) == 1, (
            f"Expected 1 _upsert_commodity call, got {upsert_commodity_calls}"
        )
        assert sum(merge_batch_calls) == 3, (
            f"Expected 3 total merged rows, got {merge_batch_calls}"
        )


# ---------------------------------------------------------------------------
# T4. load_rows raises on missing country_code='IN'
# ---------------------------------------------------------------------------

class TestLoadRowsMissingCountry:
    """T4: RuntimeError with the pinned message when dim_country has no IN row."""

    def test_load_rows_missing_country_raises(self, monkeypatch) -> None:
        pg = _load_playground_module("pg_ogd_mandi_t4")

        from contextlib import contextmanager

        def smart_execute(stmt, params=None):
            result = MagicMock()
            result.fetchone.return_value = None  # dim_country missing
            return result

        mock_conn = MagicMock()
        mock_conn.execute = smart_execute

        @contextmanager
        def fake_begin():
            yield mock_conn

        mock_engine = MagicMock()
        mock_engine.begin.side_effect = fake_begin

        monkeypatch.setattr(pg, "_get_load_engine", lambda: mock_engine)
        monkeypatch.setattr(pg, "_check_tables_exist", lambda e: True)
        monkeypatch.setattr(pg, "_resolve_vendor_id", lambda conn, vc: 7)

        rows = _make_rows(1, same_market=True)

        with pytest.raises(RuntimeError) as excinfo:
            pg.load_rows(rows)

        assert str(excinfo.value) == "dbo.dim_country missing country_code='IN'"


# ---------------------------------------------------------------------------
# T5. _REPO_ROOT depth — both lib and playground resolve to the repo root
# ---------------------------------------------------------------------------

class TestRepoRootResolvesToRepo:
    """T5: guards the parents[] depth — would have caught M1."""

    def test_lib_repo_root_has_pyproject(self) -> None:
        assert (_REPO_ROOT / "pyproject.toml").exists(), (
            f"Lib _REPO_ROOT={_REPO_ROOT} does not contain pyproject.toml"
        )

    def test_playground_repo_root_has_pyproject(self) -> None:
        import importlib.util
        pf = Path(__file__).resolve().parents[3] / "playground" / "econ" / "in" / "ogd" / "ogd_mandi.py"
        spec = importlib.util.spec_from_file_location("pg_ogd_mandi_t5", pf)
        pg = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(pg)
        assert (pg._REPO_ROOT / "pyproject.toml").exists(), (
            f"Playground _REPO_ROOT={pg._REPO_ROOT} does not contain pyproject.toml"
        )


# ---------------------------------------------------------------------------
# T6. iter_pages_for_date stops at _MAX_PAGES_PER_DAY sentinel
# ---------------------------------------------------------------------------

class TestIterPagesMaxPagesGuard:
    """T6: infinite-full-page API must stop at _MAX_PAGES_PER_DAY, not loop forever."""

    def test_stops_at_max_pages_sentinel(self, monkeypatch) -> None:
        import imdr.domains.econ.ogd_mandi as mod

        full_page = [_make_record(i) for i in range(_PAGE_SIZE)]

        call_count = [0]

        def always_full(session, key, *, offset, arrival_date=None, timeout=30):
            call_count[0] += 1
            return _make_page(full_page, _PAGE_SIZE * 1000)

        monkeypatch.setattr(mod, "_get_page", always_full)
        monkeypatch.setattr(mod, "_THROTTLE_S", 0)

        results = list(iter_pages_for_date(MagicMock(), "key",
                                           datetime.date(2026, 6, 15)))

        assert len(results) == _MAX_PAGES_PER_DAY
        assert call_count[0] == _MAX_PAGES_PER_DAY
