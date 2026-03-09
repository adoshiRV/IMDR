"""Pipeline configuration loader.

Reads pipelines.yml and provides validated config objects
that pipelines, health checks, and reporters consume at runtime.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel

_CONFIG_PATH = Path(__file__).parent / "pipelines.yml"


def fq_name(schema: str, name: str) -> str:
    """Build a fully-qualified SQL Server identifier like [schema].[name]."""
    return f"[{schema}].[{name}]"


class ValueRangeConfig(BaseModel):
    min: float
    max: float


class HealthCheckConfig(BaseModel):
    row_count_min: int = 1
    max_staleness_hours: int = 24
    value_ranges: dict[str, ValueRangeConfig] = {}


class SourceConfig(BaseModel):
    type: str  # "rest", "csv", etc.
    # Extensible — domain-specific keys can be added via model_config extra="allow"

    model_config = {"extra": "allow"}


class PipelineConfig(BaseModel):
    domain: str
    target_schema: str
    target_table: str
    date_column: str
    unique_columns: list[str] = []
    required_columns: list[str] = []
    health_checks: HealthCheckConfig = HealthCheckConfig()
    sources: dict[str, SourceConfig] = {}

    @property
    def fully_qualified_table(self) -> str:
        return fq_name(self.target_schema, self.target_table)


class PipelinesConfig(BaseModel):
    pipelines: dict[str, PipelineConfig]


@lru_cache(maxsize=1)
def load_pipelines_config(config_path: Path = _CONFIG_PATH) -> PipelinesConfig:
    """Load and validate pipelines.yml. Cached after first call."""
    with open(config_path) as f:
        raw = yaml.safe_load(f)
    return PipelinesConfig.model_validate(raw)


def get_pipeline_config(pipeline_name: str, config_path: Path = _CONFIG_PATH) -> PipelineConfig:
    """Get config for a specific pipeline by name."""
    config = load_pipelines_config(config_path)
    if pipeline_name not in config.pipelines:
        available = ", ".join(config.pipelines.keys())
        msg = f"Pipeline '{pipeline_name}' not found in config. Available: {available}"
        raise KeyError(msg)
    return config.pipelines[pipeline_name]
