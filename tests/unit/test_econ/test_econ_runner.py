"""Tests for scripts/econ/_runner.py (write_parquet + invoke_loader + run_main).

Network- and DB-free. We monkeypatch:
  - _DATA_ECON_ROOT     -> tmp_path, so writes land in a sandbox.
  - subprocess.call     -> a stub, so invoke_loader's command-line is checked
                           without actually launching a subprocess.

Covered:
- write_parquet writes a (dim, fact) pair under
  data/econ/{cc}/{vendor}/{topic}/{Y}/{M}/{D}/ with the correct stem.
- write_parquet adds a ``ts`` column to both DataFrames.
- write_parquet preserves history (repeated calls produce distinct files
  with second-precision timestamps in the stem).
- invoke_loader builds the EXACT command the canonical loader expects
  (--vendor / --dim-parquet / --fact-parquet flags + module path).
- invoke_loader propagates the subprocess return code.
- run_main with --no-parquet skips writes and returns 0.
- run_main with --no-load writes parquet but does NOT invoke the loader.
- run_main returns 1 when the fetch produces zero observations.
- country_code is mandatory and rejects bad input.
"""

from __future__ import annotations

import datetime
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ import _runner

UTC = datetime.timezone.utc


def _ind(code: str = "X.Y.Z.KR") -> IndicatorRow:
    return IndicatorRow(
        imdr_code=code,
        vendor_name="KOSIS",
        source_code="101/DT_X/C1=0",
        display_name="test indicator",
        unit="pct",
        frequency="MONTHLY",
        country_iso="KR",
        category="cpi",
    )


def _obs(code: str = "X.Y.Z.KR", d: datetime.date | None = None) -> ObservationRow:
    return ObservationRow(
        imdr_code=code,
        obs_date=d or datetime.date(2026, 1, 1),
        vintage=0,
        release_date=datetime.datetime(2026, 2, 1, tzinfo=UTC),
        value=1.23,
    )


class TestWriteParquet:
    def test_writes_pair_under_expected_path(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(_runner, "_DATA_ECON_ROOT", tmp_path)
        fixed = datetime.datetime(2026, 6, 5, 14, 30, tzinfo=UTC)
        dim_path, fact_path = _runner.write_parquet(
            "KR", "kosis", "cpi", [_ind()], [_obs()], now_utc=fixed,
        )
        assert dim_path == tmp_path / "kr" / "kosis" / "cpi" / "2026" / "06" / "05" / "kosis_cpi_20260605_1430_dim.parquet"
        assert fact_path == tmp_path / "kr" / "kosis" / "cpi" / "2026" / "06" / "05" / "kosis_cpi_20260605_1430_fact.parquet"
        assert dim_path.exists()
        assert fact_path.exists()

    def test_dim_parquet_has_ts_column(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(_runner, "_DATA_ECON_ROOT", tmp_path)
        dim_path, _ = _runner.write_parquet("KR", "kosis", "cpi", [_ind()], [_obs()])
        df = pd.read_parquet(dim_path)
        assert "ts" in df.columns
        assert "imdr_code" in df.columns
        assert df.loc[0, "imdr_code"] == "X.Y.Z.KR"

    def test_fact_parquet_has_ts_column(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(_runner, "_DATA_ECON_ROOT", tmp_path)
        _, fact_path = _runner.write_parquet("KR", "kosis", "cpi", [_ind()], [_obs()])
        df = pd.read_parquet(fact_path)
        assert "ts" in df.columns
        assert "value" in df.columns
        assert df.loc[0, "value"] == pytest.approx(1.23)

    def test_preserves_history_on_distinct_minute_writes(self, tmp_path, monkeypatch) -> None:
        # Two writes at different minutes must yield two distinct files
        # rather than overwriting -- archive must keep prior fetches.
        monkeypatch.setattr(_runner, "_DATA_ECON_ROOT", tmp_path)
        t1 = datetime.datetime(2026, 6, 5, 14, 30, tzinfo=UTC)
        t2 = datetime.datetime(2026, 6, 5, 14, 31, tzinfo=UTC)
        d1, f1 = _runner.write_parquet("KR", "kosis", "cpi", [_ind()], [_obs()], now_utc=t1)
        d2, f2 = _runner.write_parquet("KR", "kosis", "cpi", [_ind()], [_obs()], now_utc=t2)
        assert d1 != d2
        assert f1 != f2
        assert d1.exists() and d2.exists()
        assert f1.exists() and f2.exists()

    def test_creates_nested_dirs(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(_runner, "_DATA_ECON_ROOT", tmp_path)
        # tmp_path has no kr/kosis/cpi/Y/M/D structure -- write_parquet must
        # create the full chain.
        _runner.write_parquet("KR", "kosis", "cpi", [_ind()], [_obs()])
        assert (tmp_path / "kr" / "kosis" / "cpi").is_dir()

    def test_country_code_is_lowercased_on_disk(self, tmp_path, monkeypatch) -> None:
        # Filesystem layout pins lowercase 2-letter ISO. We assert via the
        # *returned path string* because Windows filesystems are
        # case-insensitive; on Windows ``(tmp / "KR").exists()`` would still
        # return True even though the on-disk segment is lowercase.
        monkeypatch.setattr(_runner, "_DATA_ECON_ROOT", tmp_path)
        dim_path, _ = _runner.write_parquet("KR", "kosis", "cpi", [_ind()], [_obs()])
        assert "kr" in dim_path.parts
        assert "KR" not in dim_path.parts

    @pytest.mark.parametrize("bad_cc", ["", "  ", "K", "KRX", "12", "k_"])
    def test_country_code_value_error_on_bad_shape(self, bad_cc) -> None:
        # Shape errors (length, non-alpha, whitespace-only) -> ValueError.
        with pytest.raises(ValueError):
            _runner.write_parquet(bad_cc, "kosis", "cpi", [_ind()], [_obs()])

    @pytest.mark.parametrize("bad_cc", [None, 0, b"KR", ("K", "R")])
    def test_country_code_type_error_on_non_string(self, bad_cc) -> None:
        # Type errors (None, int, bytes, tuple, ...) -> TypeError.
        with pytest.raises(TypeError):
            _runner.write_parquet(bad_cc, "kosis", "cpi", [_ind()], [_obs()])


class TestInvokeLoader:
    def test_builds_exact_command(self, monkeypatch) -> None:
        captured: dict[str, list[str]] = {}

        def stub(cmd, *a, **kw):
            captured["cmd"] = list(cmd)
            return 0

        monkeypatch.setattr(subprocess, "call", stub)
        rc = _runner.invoke_loader(
            "kosis",
            Path("data/econ/kr/kosis/cpi/2026/06/05/kosis_cpi_20260605_1430_dim.parquet"),
            Path("data/econ/kr/kosis/cpi/2026/06/05/kosis_cpi_20260605_1430_fact.parquet"),
        )
        assert rc == 0
        assert captured["cmd"][0] == sys.executable
        assert captured["cmd"][1] == "-m"
        assert captured["cmd"][2] == "scripts.migrations.load_econ_indicator_from_playground"
        assert "--vendor" in captured["cmd"]
        assert "kosis" in captured["cmd"]
        assert "--dim-parquet" in captured["cmd"]
        assert "--fact-parquet" in captured["cmd"]
        # The exact paths must come through as strings.
        assert any(
            "kosis_cpi_20260605_1430_dim.parquet" in arg for arg in captured["cmd"]
        )
        assert any(
            "kosis_cpi_20260605_1430_fact.parquet" in arg for arg in captured["cmd"]
        )

    def test_propagates_subprocess_rc(self, monkeypatch) -> None:
        monkeypatch.setattr(subprocess, "call", lambda *a, **kw: 7)
        rc = _runner.invoke_loader(
            "reb", Path("d.parquet"), Path("f.parquet"),
        )
        assert rc == 7


class TestRunMain:
    def test_no_parquet_skips_writes_and_load(self, monkeypatch, capsys) -> None:
        # No parquet should be written and no loader subprocess invoked.
        called = {"write": 0, "load": 0}

        def fail_write(*a, **kw):
            called["write"] += 1
            raise AssertionError("write_parquet must not run under --no-parquet")

        def fail_load(*a, **kw):
            called["load"] += 1
            raise AssertionError("invoke_loader must not run under --no-parquet")

        monkeypatch.setattr(_runner, "write_parquet", fail_write)
        monkeypatch.setattr(_runner, "invoke_loader", fail_load)
        monkeypatch.setattr(sys, "argv", ["kosis_cpi", "--no-parquet"])

        def fetch(since, until):
            return [_ind()], [_obs()]

        rc = _runner.run_main("kosis", "cpi", fetch, country_code="KR")
        assert rc == 0
        assert called["write"] == 0
        assert called["load"] == 0

    def test_no_load_writes_but_skips_loader(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(_runner, "_DATA_ECON_ROOT", tmp_path)
        called = {"load": 0}

        def fail_load(*a, **kw):
            called["load"] += 1
            raise AssertionError("invoke_loader must not run under --no-load")

        monkeypatch.setattr(_runner, "invoke_loader", fail_load)
        monkeypatch.setattr(sys, "argv", ["kosis_cpi", "--no-load"])

        def fetch(since, until):
            return [_ind()], [_obs()]

        rc = _runner.run_main("kosis", "cpi", fetch, country_code="KR")
        assert rc == 0
        assert called["load"] == 0
        # Parquet pair should now exist somewhere under tmp_path.
        written = list(tmp_path.rglob("*_fact.parquet"))
        assert len(written) == 1
        # ...and specifically under the lowercase country-code anchor.
        assert any("kr" in p.parts for p in written)

    def test_returns_1_when_no_observations(self, monkeypatch) -> None:
        monkeypatch.setattr(sys, "argv", ["kosis_cpi"])

        def fetch(since, until):
            return [_ind()], []

        rc = _runner.run_main("kosis", "cpi", fetch, country_code="KR")
        assert rc == 1

    def test_run_main_rejects_missing_country_code(self, monkeypatch) -> None:
        monkeypatch.setattr(sys, "argv", ["kosis_cpi"])

        def fetch(since, until):
            return [_ind()], [_obs()]

        with pytest.raises(TypeError):
            # country_code is keyword-only AND mandatory.
            _runner.run_main("kosis", "cpi", fetch)  # type: ignore[call-arg]

    def test_invokes_loader_on_full_run(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(_runner, "_DATA_ECON_ROOT", tmp_path)
        captured: dict = {}

        def stub_load(vendor, dim_path, fact_path):
            captured["vendor"] = vendor
            captured["dim_path"] = dim_path
            captured["fact_path"] = fact_path
            return 0

        monkeypatch.setattr(_runner, "invoke_loader", stub_load)
        monkeypatch.setattr(sys, "argv", ["kosis_cpi"])

        def fetch(since, until):
            return [_ind()], [_obs()]

        rc = _runner.run_main("kosis", "cpi", fetch, country_code="KR")
        assert rc == 0
        assert captured["vendor"] == "kosis"
        assert captured["dim_path"].name.endswith("_dim.parquet")
        assert captured["fact_path"].name.endswith("_fact.parquet")
        assert captured["dim_path"].exists()
        assert captured["fact_path"].exists()

    def test_propagates_loader_rc(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(_runner, "_DATA_ECON_ROOT", tmp_path)
        monkeypatch.setattr(_runner, "invoke_loader", lambda v, d, f: 3)
        monkeypatch.setattr(sys, "argv", ["kosis_cpi"])

        def fetch(since, until):
            return [_ind()], [_obs()]

        assert _runner.run_main("kosis", "cpi", fetch, country_code="KR") == 3
