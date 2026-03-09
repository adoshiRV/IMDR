"""Tests for pipeline audit trail integration in BasePipeline."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from imdr.models.audit import PipelineRun


class TestPipelineRunModel:
    def test_tablename(self) -> None:
        assert PipelineRun.__tablename__ == "pipeline_runs"

    def test_schema(self) -> None:
        assert PipelineRun.__table_args__["schema"] == "audit"

    def test_required_columns_exist(self) -> None:
        columns = {c.name for c in PipelineRun.__table__.columns}
        expected = {
            "id",
            "pipeline_name",
            "domain",
            "run_status",
            "started_at",
            "finished_at",
            "rows_extracted",
            "rows_loaded",
            "error_message",
            "health_check_passed",
            "health_check_details",
            "created_at",
            "updated_at",
        }
        assert expected.issubset(columns)


class TestAuditSchemas:
    def test_pipeline_run_create(self) -> None:
        from imdr.schemas.audit import PipelineRunCreate

        data = PipelineRunCreate(
            pipeline_name="fx.spot_rates",
            domain="fx",
            started_at=datetime.now(timezone.utc),
        )
        assert data.run_status == "running"

    def test_pipeline_run_update(self) -> None:
        from imdr.schemas.audit import PipelineRunUpdate

        data = PipelineRunUpdate(
            finished_at=datetime.now(timezone.utc),
            run_status="success",
            rows_extracted=100,
            rows_loaded=95,
        )
        assert data.rows_loaded == 95

    def test_pipeline_run_response(self) -> None:
        from imdr.schemas.audit import PipelineRunResponse

        now = datetime.now(timezone.utc)
        data = PipelineRunResponse(
            id=1,
            pipeline_name="fx.spot_rates",
            domain="fx",
            run_status="success",
            started_at=now,
            finished_at=now,
            created_at=now,
            updated_at=now,
        )
        assert data.id == 1
