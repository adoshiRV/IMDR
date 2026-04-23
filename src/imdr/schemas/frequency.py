"""Pydantic schemas for the dbo.dim_frequency dimension."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class FrequencyResponse(BaseModel):
    """Read schema for dbo.dim_frequency rows (rarely written post-seed)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    frequency_code: str = Field(..., min_length=3, max_length=10)
    display_name: str
    typical_seconds: int | None = None
    created_at: datetime
    updated_at: datetime
