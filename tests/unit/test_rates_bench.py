"""Unit tests for bench rates pipeline — tag parsing, schemas, parquet, pipeline metadata."""
from __future__ import annotations

import json
import math
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from pydantic import ValidationError

from imdr.domains.rates.pipeline_bench import (
    BenchRatesPipeline,
    citi_bench_response_to_df,
    citi_bench_tag_to_internal,
    parquet_write,
    COLUMNS,
    PARQUET_NATURAL_KEY,
)
from imdr.schemas.rates_bench import BenchRateCreate, CentralBankCreate
from imdr.universe.rates import get_rates_universe


# ── Tag Parsing ─────────────────────────────────────────────────────


class TestCitiBenchTagToInternal:
    def test_ecb(self):
        result = citi_bench_tag_to_internal("RATES.BENCH_RATES.ECB")
        assert result == {"cb_code": "ECB"}

    def test_fed_funds(self):
        result = citi_bench_tag_to_internal("RATES.BENCH_RATES.FED_FUNDS")
        assert result == {"cb_code": "FED_FUNDS"}

    def test_uk_base(self):
        result = citi_bench_tag_to_internal("RATES.BENCH_RATES.UK_BASE")
        assert result == {"cb_code": "UK_BASE"}

    def test_invalid_prefix(self):
        assert citi_bench_tag_to_internal("FX.BENCH_RATES.ECB") is None

    def test_wrong_category(self):
        assert citi_bench_tag_to_internal("RATES.OIS.ECB") is None

    def test_too_few_parts(self):
        assert citi_bench_tag_to_internal("RATES.BENCH_RATES") is None

    def test_too_many_parts(self):
        assert citi_bench_tag_to_internal("RATES.BENCH_RATES.ECB.EXTRA") is None

    def test_empty_cb_code(self):
        assert citi_bench_tag_to_internal("RATES.BENCH_RATES.") is None


# ── Response Parsing ────────────────────────────────────────────────


class TestCitiBenchResponseToDf:
    def test_valid_response(self):
        resp = {
            "status": "OK",
            "body": {
                "RATES.BENCH_RATES.ECB": {
                    "x": ["20260415"],
                    "c": ["2.15"],
                }
            },
        }
        df = citi_bench_response_to_df(resp)
        assert list(df.columns) == COLUMNS
        assert len(df) == 1
        assert df.iloc[0]["cb_code"] == "ECB"
        assert df.iloc[0]["value"] == 2.15

    def test_empty_body(self):
        resp = {"status": "OK", "body": {}}
        df = citi_bench_response_to_df(resp)
        assert list(df.columns) == COLUMNS
        assert len(df) == 0

    def test_error_status_raises(self):
        with pytest.raises(RuntimeError, match="API status not OK"):
            citi_bench_response_to_df({"status": "ERROR"})

    def test_multiple_tags(self):
        resp = {
            "status": "OK",
            "body": {
                "RATES.BENCH_RATES.ECB": {
                    "x": ["20260415"],
                    "c": ["2.15"],
                },
                "RATES.BENCH_RATES.FED_FUNDS": {
                    "x": ["20260415"],
                    "c": ["3.64"],
                },
            },
        }
        df = citi_bench_response_to_df(resp)
        assert len(df) == 2
        assert set(df["cb_code"]) == {"ECB", "FED_FUNDS"}


# ── Pydantic Schema Validation ──────────────────────────────────────


class TestBenchRateCreateSchema:
    def test_valid(self):
        item = BenchRateCreate(cb_id=1, vendor_id=1, obs_date=date(2026, 4, 15), rate=3.75)
        assert item.rate == 3.75

    def test_rejects_nan(self):
        with pytest.raises(ValidationError, match="finite"):
            BenchRateCreate(cb_id=1, vendor_id=1, obs_date=date(2026, 4, 15), rate=float("nan"))

    def test_rejects_inf(self):
        with pytest.raises(ValidationError, match="finite"):
            BenchRateCreate(cb_id=1, vendor_id=1, obs_date=date(2026, 4, 15), rate=float("inf"))

    def test_rejects_negative_inf(self):
        with pytest.raises(ValidationError, match="finite"):
            BenchRateCreate(cb_id=1, vendor_id=1, obs_date=date(2026, 4, 15), rate=float("-inf"))

    def test_rejects_out_of_range_high(self):
        with pytest.raises(ValidationError, match="outside expected range"):
            BenchRateCreate(cb_id=1, vendor_id=1, obs_date=date(2026, 4, 15), rate=25.0)

    def test_rejects_out_of_range_low(self):
        with pytest.raises(ValidationError, match="outside expected range"):
            BenchRateCreate(cb_id=1, vendor_id=1, obs_date=date(2026, 4, 15), rate=-5.0)

    def test_accepts_boundary_values(self):
        low = BenchRateCreate(cb_id=1, vendor_id=1, obs_date=date(2026, 4, 15), rate=-2.0)
        high = BenchRateCreate(cb_id=1, vendor_id=1, obs_date=date(2026, 4, 15), rate=20.0)
        assert low.rate == -2.0
        assert high.rate == 20.0

    def test_positive_cb_id_required(self):
        with pytest.raises(ValidationError):
            BenchRateCreate(cb_id=0, vendor_id=1, obs_date=date(2026, 4, 15), rate=3.75)

    def test_positive_vendor_id_required(self):
        with pytest.raises(ValidationError):
            BenchRateCreate(cb_id=1, vendor_id=-1, obs_date=date(2026, 4, 15), rate=3.75)


class TestCentralBankCreateSchema:
    def test_uppercase_cb_code(self):
        item = CentralBankCreate(
            cb_code="ecb", display_name="ECB Rate", currency="eur",
            country_code="eu", citi_tag="RATES.BENCH_RATES.ECB",
        )
        assert item.cb_code == "ECB"
        assert item.currency == "EUR"
        assert item.country_code == "EU"


# ── Parquet Store ───────────────────────────────────────────────────


class TestParquetWrite:
    def _sample_df(self) -> pd.DataFrame:
        return pd.DataFrame({
            "ts": [
                pd.Timestamp("2026-04-15", tz="UTC"),
                pd.Timestamp("2026-04-15", tz="UTC"),
            ],
            "cb_code": ["ECB", "FED_FUNDS"],
            "value": [2.15, 3.64],
        })

    def test_roundtrip(self, tmp_path: Path):
        df = self._sample_df()
        written = parquet_write(df, data_root=tmp_path)
        assert len(written) == 1
        assert written[0].exists()

        result = pd.read_parquet(written[0])
        assert len(result) == 2
        assert set(result["cb_code"]) == {"ECB", "FED_FUNDS"}

    def test_dedup_on_natural_key(self, tmp_path: Path):
        df1 = self._sample_df()
        parquet_write(df1, data_root=tmp_path)

        # Write again with updated value — should dedup
        df2 = pd.DataFrame({
            "ts": [pd.Timestamp("2026-04-15", tz="UTC")],
            "cb_code": ["ECB"],
            "value": [2.25],
        })
        parquet_write(df2, data_root=tmp_path)

        result = pd.read_parquet(tmp_path / "2026-04.parquet")
        ecb_rows = result[result["cb_code"] == "ECB"]
        assert len(ecb_rows) == 1
        assert ecb_rows.iloc[0]["value"] == 2.25

    def test_manifest_written(self, tmp_path: Path):
        df = self._sample_df()
        manifest = {"source": "test", "rows_loaded": 2}
        parquet_write(df, data_root=tmp_path, manifest=manifest)

        manifest_path = tmp_path / "2026-04_manifest.json"
        assert manifest_path.exists()
        data = json.loads(manifest_path.read_text())
        assert data["source"] == "test"
        assert "write_ts" in data

    def test_tmp_cleanup_on_failure(self, tmp_path: Path):
        """Verify temp file is cleaned up when parquet write fails."""
        df = self._sample_df()

        with patch("imdr.domains.rates.pipeline_bench.pd.DataFrame.to_parquet",
                    side_effect=OSError("disk full")):
            with pytest.raises(OSError, match="disk full"):
                parquet_write(df, data_root=tmp_path)

        # No orphaned .tmp.parquet files
        tmp_files = list(tmp_path.glob("*.tmp.parquet"))
        assert len(tmp_files) == 0

    def test_empty_df_returns_empty(self, tmp_path: Path):
        df = pd.DataFrame(columns=COLUMNS)
        written = parquet_write(df, data_root=tmp_path)
        assert written == []


# ── Pipeline Metadata ───────────────────────────────────────────────


class TestBenchRatesPipelineMetadata:
    def test_pipeline_name(self):
        assert BenchRatesPipeline.pipeline_name == "rates.bench_rates"

    def test_domain(self):
        assert BenchRatesPipeline.domain == "rates"


# ── Universe Integration ────────────────────────────────────────────


class TestUniverseBenchRates:
    @pytest.fixture
    def universe(self):
        return get_rates_universe()

    def test_bench_rates_tags_returns_list(self, universe):
        tags = universe.bench_rates_tags()
        assert isinstance(tags, list)
        assert len(tags) == 8

    def test_bench_rates_tags_format(self, universe):
        for tag in universe.bench_rates_tags():
            assert tag.startswith("RATES.BENCH_RATES.")

    def test_bench_rates_entries_returns_list(self, universe):
        entries = universe.bench_rates_entries()
        assert len(entries) == 8

    def test_bench_rates_tag_to_cb_code(self, universe):
        mapping = universe.bench_rates_tag_to_cb_code()
        assert "RATES.BENCH_RATES.ECB" in mapping
        assert mapping["RATES.BENCH_RATES.ECB"] == "ECB"
