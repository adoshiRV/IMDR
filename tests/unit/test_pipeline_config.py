"""Tests for pipeline config loading and validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from imdr.config.pipeline_config import (
    PipelinesConfig,
    get_pipeline_config,
    load_pipelines_config,
)


class TestPipelineConfig:
    def test_load_default_config(self) -> None:
        config = load_pipelines_config()
        assert "fx.citi_rate" in config.pipelines

    def test_fx_citi_rate_config(self) -> None:
        cfg = get_pipeline_config("fx.citi_rate")
        assert cfg.domain == "fx"
        assert cfg.target_schema == "fx"
        assert cfg.target_table == "fact_fx_rate"
        assert cfg.date_column == "obs_date"
        assert "mid_rate" in cfg.required_columns

    def test_fully_qualified_table(self) -> None:
        cfg = get_pipeline_config("fx.citi_rate")
        assert cfg.fully_qualified_table == "[fx].[fact_fx_rate]"

    def test_unknown_pipeline_raises(self) -> None:
        with pytest.raises(KeyError, match="not found"):
            get_pipeline_config("nonexistent.pipeline")

    def test_value_ranges_parsed(self) -> None:
        cfg = get_pipeline_config("commodities.spot")
        assert "price" in cfg.health_checks.value_ranges
        vr = cfg.health_checks.value_ranges["price"]
        assert vr.min == 0.01
        assert vr.max == 100000.0

    def test_load_custom_yaml(self, tmp_path: Path) -> None:
        yml = tmp_path / "test_pipelines.yml"
        yml.write_text(
            "pipelines:\n"
            "  test.pipeline:\n"
            "    domain: test\n"
            "    target_schema: dbo\n"
            "    target_table: test_data\n"
            "    date_column: dt\n"
        )
        # Clear lru_cache to allow loading a different file
        load_pipelines_config.cache_clear()
        config = load_pipelines_config(yml)
        assert "test.pipeline" in config.pipelines
        assert config.pipelines["test.pipeline"].domain == "test"
        # Reset cache
        load_pipelines_config.cache_clear()


class TestPipelinesConfigValidation:
    def test_minimal_config(self) -> None:
        data = {
            "pipelines": {
                "x.y": {
                    "domain": "x",
                    "target_schema": "dbo",
                    "target_table": "t",
                    "date_column": "dt",
                }
            }
        }
        cfg = PipelinesConfig.model_validate(data)
        assert cfg.pipelines["x.y"].health_checks.row_count_min == 1  # default

    def test_health_check_defaults(self) -> None:
        data = {
            "pipelines": {
                "a.b": {
                    "domain": "a",
                    "target_schema": "s",
                    "target_table": "t",
                    "date_column": "d",
                }
            }
        }
        cfg = PipelinesConfig.model_validate(data)
        hc = cfg.pipelines["a.b"].health_checks
        assert hc.row_count_min == 1
        assert hc.max_staleness_hours == 24
        assert hc.value_ranges == {}
