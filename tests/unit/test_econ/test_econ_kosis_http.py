"""Tests for src/imdr/domains/econ/kosis_http.py.

Network-free. We exercise:
- parse_kosis_period: pure function, every cadence + every malformed-input branch.
- load_kosis_key: env-var path, .env fallback path, missing-key error path.
- fetch_kosis_table: argument validation (mutually-exclusive window vs newEstPrdCnt).

The HTTP retry loop itself talks to KOSIS; we don't mock requests at that
depth -- those paths are exercised by the per-fetcher smoke test in
test_kosis_cpi_fetcher.py.
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from imdr.domains.econ.kosis_http import (
    fetch_kosis_table,
    load_kosis_key,
    parse_kosis_period,
)


class TestParseKosisPeriod:
    def test_monthly_parses_yyyymm_to_first_of_month(self) -> None:
        assert parse_kosis_period("202603", "M") == (2026, 3, 1)

    def test_monthly_wrong_length_returns_none(self) -> None:
        assert parse_kosis_period("20260301", "M") is None
        assert parse_kosis_period("2026", "M") is None

    def test_quarterly_parses_yyyyqq_to_first_of_quarter(self) -> None:
        assert parse_kosis_period("202601", "Q") == (2026, 1, 1)
        assert parse_kosis_period("202602", "Q") == (2026, 4, 1)
        assert parse_kosis_period("202603", "Q") == (2026, 7, 1)
        assert parse_kosis_period("202604", "Q") == (2026, 10, 1)

    def test_quarterly_out_of_range_returns_none(self) -> None:
        assert parse_kosis_period("202605", "Q") is None
        assert parse_kosis_period("202600", "Q") is None

    def test_annual_parses_yyyy_to_jan_1(self) -> None:
        assert parse_kosis_period("2026", "A") == (2026, 1, 1)

    def test_annual_wrong_length_returns_none(self) -> None:
        assert parse_kosis_period("202601", "A") is None

    def test_weekly_parses_yyyymmdd(self) -> None:
        assert parse_kosis_period("20260605", "W") == (2026, 6, 5)

    def test_daily_parses_yyyymmdd(self) -> None:
        assert parse_kosis_period("20260605", "D") == (2026, 6, 5)

    def test_none_input_returns_none(self) -> None:
        assert parse_kosis_period(None, "M") is None

    def test_empty_input_returns_none(self) -> None:
        assert parse_kosis_period("", "M") is None

    def test_non_numeric_returns_none(self) -> None:
        assert parse_kosis_period("abcd", "A") is None
        assert parse_kosis_period("20XX", "A") is None

    def test_unknown_prd_se_returns_none(self) -> None:
        # H (half-yearly) isn't in the parser's switch.
        assert parse_kosis_period("202601", "H") is None


class TestLoadKosisKey:
    def test_returns_env_var_when_set(self) -> None:
        with patch.dict(os.environ, {"IMDR_KOSIS_API_KEY": "envkey-abc"}, clear=False):
            assert load_kosis_key() == "envkey-abc"

    def test_raises_with_exact_message_when_missing(self, tmp_path, monkeypatch) -> None:
        monkeypatch.delenv("IMDR_KOSIS_API_KEY", raising=False)
        # Repoint the module's _REPO_ROOT to a directory with no .env so the
        # fallback can't find one.
        import imdr.domains.econ.kosis_http as mod
        monkeypatch.setattr(mod, "_REPO_ROOT", tmp_path)
        with pytest.raises(RuntimeError) as excinfo:
            load_kosis_key()
        assert str(excinfo.value) == "IMDR_KOSIS_API_KEY not set in env or .env"

    def test_falls_back_to_dotenv(self, tmp_path, monkeypatch) -> None:
        monkeypatch.delenv("IMDR_KOSIS_API_KEY", raising=False)
        env_file = tmp_path / ".env"
        env_file.write_text("OTHER_VAR=foo\nIMDR_KOSIS_API_KEY=dotenv-xyz\n", encoding="utf-8")
        import imdr.domains.econ.kosis_http as mod
        monkeypatch.setattr(mod, "_REPO_ROOT", tmp_path)
        assert load_kosis_key() == "dotenv-xyz"


class TestFetchKosisTableArgValidation:
    def test_both_window_and_newest_cnt_raises(self) -> None:
        with pytest.raises(ValueError) as excinfo:
            fetch_kosis_table(
                session=None,  # never used -- validation happens first
                org_id="301",
                tbl_id="DT_X",
                start_prd_de="202601",
                end_prd_de="202612",
                new_est_prd_cnt=5,
            )
        assert str(excinfo.value) == "Use either start/end date OR newEstPrdCnt, not both"
