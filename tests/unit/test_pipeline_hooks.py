"""Tests for BasePipeline validate() and post_load() hooks."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from imdr.pipelines.base import BasePipeline


class _StubPipeline(BasePipeline[list[int], list[int], int]):
    """Minimal pipeline for testing hook call order."""

    pipeline_name = ""  # skip audit
    domain = "test"

    def __init__(self) -> None:
        connector = MagicMock()
        super().__init__(connector)
        self.call_order: list[str] = []

    def extract(self) -> list[int]:
        self.call_order.append("extract")
        return [1, 2, 3]

    def transform(self, raw: list[int]) -> list[int]:
        self.call_order.append("transform")
        return [x * 10 for x in raw]

    def validate(self, data: list[int]) -> list[int]:
        self.call_order.append("validate")
        return [x for x in data if x > 10]  # filter out 10

    def load(self, data: list[int]) -> int:
        self.call_order.append("load")
        return len(data)

    def post_load(self, result: int, data: list[int]) -> None:
        self.call_order.append("post_load")


class _DefaultHooksPipeline(BasePipeline[str, str, str]):
    """Pipeline that doesn't override validate/post_load."""

    pipeline_name = ""
    domain = "test"

    def __init__(self) -> None:
        connector = MagicMock()
        super().__init__(connector)

    def extract(self) -> str:
        return "raw"

    def transform(self, raw: str) -> str:
        return raw.upper()

    def load(self, data: str) -> str:
        return data


def test_hook_call_order():
    """validate() and post_load() are called in correct order."""
    pipeline = _StubPipeline()
    result = pipeline.run()

    assert pipeline.call_order == ["extract", "transform", "validate", "load", "post_load"]
    assert result == 2  # [20, 30] after filtering out 10


def test_validate_filters_data():
    """validate() can filter data before load."""
    pipeline = _StubPipeline()
    result = pipeline.run()
    # extract: [1, 2, 3] -> transform: [10, 20, 30] -> validate: [20, 30] -> load: 2
    assert result == 2


def test_default_validate_passthrough():
    """Default validate() passes data through unchanged."""
    pipeline = _DefaultHooksPipeline()
    result = pipeline.run()
    assert result == "RAW"


def test_default_post_load_noop():
    """Default post_load() does nothing (no error)."""
    pipeline = _DefaultHooksPipeline()
    # Should not raise
    pipeline.run()
