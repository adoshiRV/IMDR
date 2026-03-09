"""Pydantic schemas for pipeline run audit records."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from imdr.models.audit import RunStatus


class PipelineRunCreate(BaseModel):
    pipeline_name: str
    domain: str
    run_status: RunStatus = RunStatus.RUNNING
    started_at: datetime


class PipelineRunUpdate(BaseModel):
    finished_at: datetime
    run_status: RunStatus
    rows_extracted: int | None = None
    rows_loaded: int | None = None
    error_message: str | None = None
    health_check_passed: bool | None = None
    health_check_details: str | None = None


class PipelineRunResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    pipeline_name: str
    domain: str
    run_status: RunStatus
    started_at: datetime
    finished_at: datetime | None = None
    rows_extracted: int | None = None
    rows_loaded: int | None = None
    error_message: str | None = None
    health_check_passed: bool | None = None
    created_at: datetime
    updated_at: datetime
