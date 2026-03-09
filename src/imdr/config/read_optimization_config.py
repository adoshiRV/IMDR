"""Read optimization configuration loader.

Reads read_optimization.yml and provides validated config objects
for columnstore indexes, views, and partitioning declarations.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

from imdr.config.pipeline_config import fq_name

_CONFIG_PATH = Path(__file__).parent / "read_optimization.yml"


class ColumnstoreConfig(BaseModel):
    schema_name: str = Field(alias="schema")
    table: str
    index_name: str
    columns: list[str]

    model_config = {"populate_by_name": True}

    @property
    def fully_qualified_table(self) -> str:
        return fq_name(self.schema_name, self.table)


class ViewConfig(BaseModel):
    schema_name: str = Field(alias="schema")
    name: str
    type: Literal["indexed", "regular"]
    index_columns: list[str] = []
    description: str = ""

    model_config = {"populate_by_name": True}

    @property
    def fully_qualified_name(self) -> str:
        return fq_name(self.schema_name, self.name)


class PartitionTableConfig(BaseModel):
    schema_name: str = Field(alias="schema")
    table: str
    partition_column: str
    grain: Literal["monthly", "yearly"] = "monthly"

    model_config = {"populate_by_name": True}


class PartitioningConfig(BaseModel):
    threshold_rows: int = 50_000_000
    tables: list[PartitionTableConfig] = []


class ReadOptimizationConfig(BaseModel):
    columnstore_indexes: list[ColumnstoreConfig] = []
    views: list[ViewConfig] = []
    partitioning: PartitioningConfig = PartitioningConfig()


@lru_cache(maxsize=1)
def load_read_optimization_config(
    config_path: Path = _CONFIG_PATH,
) -> ReadOptimizationConfig:
    """Load and validate read_optimization.yml. Cached after first call."""
    with open(config_path) as f:
        raw = yaml.safe_load(f)
    return ReadOptimizationConfig.model_validate(raw)
