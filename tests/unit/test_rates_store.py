"""Tests for domains/rates/store.py — Hive-partitioned parquet store."""

import pandas as pd
import pytest

from imdr.domains.rates.store import read, write


def _sample_df(value=3.50):
    """Create a small DataFrame matching the rates schema."""
    return pd.DataFrame({
        "ts": pd.to_datetime(["2024-01-02", "2024-01-03"], utc=True),
        "ccy": ["USD", "USD"],
        "curve": ["SOFR", "SOFR"],
        "quote": ["par", "par"],
        "tenor": ["5Y", "5Y"],
        "value": [value, value + 0.02],
    })


class TestWrite:
    def test_creates_hive_partitions(self, tmp_path):
        df = _sample_df()
        written = write(df, data_root=tmp_path)
        assert len(written) == 1
        assert (tmp_path / "ccy=USD" / "curve=SOFR" / "quote=par" / "2024-01.parquet").exists()

    def test_empty_df_returns_empty(self, tmp_path):
        df = pd.DataFrame(columns=["ts", "ccy", "curve", "quote", "tenor", "value"])
        written = write(df, data_root=tmp_path)
        assert written == []

    def test_missing_columns_raises(self, tmp_path):
        df = pd.DataFrame({"ts": [1], "ccy": ["USD"]})
        with pytest.raises(ValueError, match="Missing columns"):
            write(df, data_root=tmp_path)

    def test_no_tmp_files_remain(self, tmp_path):
        write(_sample_df(), data_root=tmp_path)
        tmp_files = list(tmp_path.rglob("*.tmp.parquet"))
        assert len(tmp_files) == 0


class TestWriteReadRoundtrip:
    def test_roundtrip(self, tmp_path):
        df = _sample_df()
        write(df, data_root=tmp_path)
        result = read(ccy="USD", curve="SOFR", quote="par", data_root=tmp_path)
        assert len(result) == 2
        assert list(result.columns) == ["ts", "ccy", "curve", "quote", "tenor", "value"]

    def test_dedup_keeps_last(self, tmp_path):
        df1 = _sample_df(value=3.50)
        df2 = _sample_df(value=3.75)
        write(df1, data_root=tmp_path)
        write(df2, data_root=tmp_path)
        result = read(ccy="USD", data_root=tmp_path)
        # Second write should overwrite first
        assert result["value"].iloc[0] == 3.75


class TestWriteManifest:
    def test_manifest_written(self, tmp_path):
        write(_sample_df(), data_root=tmp_path, manifest={"source": "test"})
        manifest_path = tmp_path / "ccy=USD" / "curve=SOFR" / "quote=par" / "2024-01_manifest.json"
        assert manifest_path.exists()


class TestRead:
    def test_read_empty_root(self, tmp_path):
        result = read(data_root=tmp_path)
        assert result.empty

    def test_read_nonexistent_root(self, tmp_path):
        result = read(data_root=tmp_path / "nonexistent")
        assert result.empty

    def test_filter_by_tenor(self, tmp_path):
        df = pd.DataFrame({
            "ts": pd.to_datetime(["2024-01-02", "2024-01-02"], utc=True),
            "ccy": ["USD", "USD"],
            "curve": ["SOFR", "SOFR"],
            "quote": ["par", "par"],
            "tenor": ["5Y", "10Y"],
            "value": [3.50, 3.80],
        })
        write(df, data_root=tmp_path)
        result = read(tenor="5Y", data_root=tmp_path)
        assert len(result) == 1
        assert result["tenor"].iloc[0] == "5Y"

    def test_filter_by_date_range(self, tmp_path):
        df = pd.DataFrame({
            "ts": pd.to_datetime(["2024-01-02", "2024-01-15", "2024-02-01"], utc=True),
            "ccy": ["USD", "USD", "USD"],
            "curve": ["SOFR", "SOFR", "SOFR"],
            "quote": ["par", "par", "par"],
            "tenor": ["5Y", "5Y", "5Y"],
            "value": [3.50, 3.55, 3.60],
        })
        write(df, data_root=tmp_path)
        result = read(start="2024-01-10", end="2024-01-31", data_root=tmp_path)
        assert len(result) == 1
        assert result["value"].iloc[0] == 3.55

    def test_filter_by_ccy(self, tmp_path):
        df1 = _sample_df()
        df2 = df1.copy()
        df2["ccy"] = "EUR"
        df2["curve"] = "EUROSTR"
        combined = pd.concat([df1, df2], ignore_index=True)
        write(combined, data_root=tmp_path)

        result = read(ccy="EUR", data_root=tmp_path)
        assert all(result["ccy"] == "EUR")

    def test_annotate_benchmark(self, tmp_path):
        write(_sample_df(), data_root=tmp_path)
        result = read(ccy="USD", annotate_benchmark=True, data_root=tmp_path)
        assert "curve_type" in result.columns
        assert "curve_status" in result.columns
        assert result["curve_type"].iloc[0] == "rfr"


class TestMultiplePartitions:
    def test_multiple_months(self, tmp_path):
        df = pd.DataFrame({
            "ts": pd.to_datetime(["2024-01-15", "2024-02-15"], utc=True),
            "ccy": ["USD", "USD"],
            "curve": ["SOFR", "SOFR"],
            "quote": ["par", "par"],
            "tenor": ["5Y", "5Y"],
            "value": [3.50, 3.60],
        })
        written = write(df, data_root=tmp_path)
        assert len(written) == 2  # two month files

        result = read(data_root=tmp_path)
        assert len(result) == 2

    def test_multiple_curves(self, tmp_path):
        df = pd.DataFrame({
            "ts": pd.to_datetime(["2024-01-02", "2024-01-02"], utc=True),
            "ccy": ["USD", "USD"],
            "curve": ["SOFR", "FEDFUND"],
            "quote": ["par", "par"],
            "tenor": ["5Y", "5Y"],
            "value": [3.50, 3.30],
        })
        write(df, data_root=tmp_path)
        assert (tmp_path / "ccy=USD" / "curve=SOFR").exists()
        assert (tmp_path / "ccy=USD" / "curve=FEDFUND").exists()
