"""Abstract ETL pipeline with audit trail, health checks, and reporting.

Subclasses implement extract/transform/load. The run() method orchestrates
the full flow including audit recording, post-append health checks, and
query-back verification.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Generic, TypeVar

import structlog

from imdr.connectors.mssql import MSSQLConnector
from imdr.healthchecks.base import HealthCheck, HealthCheckRunner, HealthReport
from imdr.models.audit import PipelineRun, RunStatus

RawT = TypeVar("RawT")
CleanT = TypeVar("CleanT")
ResultT = TypeVar("ResultT")


class BasePipeline(ABC, Generic[RawT, CleanT, ResultT]):
    """Abstract ETL pipeline with extract/transform/load stages.

    Subclasses define the concrete types and implement each stage.
    Optionally override ``get_health_checks()`` and ``get_run_context()``
    to enable post-append verification.
    """

    pipeline_name: str = ""
    domain: str = ""

    def __init__(self, connector: MSSQLConnector) -> None:
        self._connector = connector
        self._log = structlog.get_logger(self.__class__.__name__)

    @abstractmethod
    def extract(self) -> RawT:
        """Extract raw data from source."""
        ...

    @abstractmethod
    def transform(self, raw: RawT) -> CleanT:
        """Validate and transform raw data."""
        ...

    @abstractmethod
    def load(self, data: CleanT) -> ResultT:
        """Load transformed data into the database."""
        ...

    def validate(self, data: CleanT) -> CleanT:
        """Hook: pre-load validation. Filter/flag bad data, log missing.

        Returns approved data only. Default: pass-through.
        """
        return data

    def post_load(self, result: ResultT, data: CleanT) -> None:
        """Hook: after DB load succeeds. Archive (parquet), email, etc."""

    def get_health_checks(self) -> list[HealthCheck]:
        """Override to return domain-specific health checks."""
        return []

    def get_run_context(self) -> dict[str, Any]:
        """Override to pass context (e.g. run_date) to health checks."""
        return {}

    def run(self) -> ResultT:
        """Execute the full ETL pipeline with audit trail and health checks."""
        started_at = datetime.now(timezone.utc)
        audit_id = self._create_audit_record(started_at)

        try:
            raw = self.extract()
            self._log.info("extract_complete")
            rows_extracted = self._count_raw(raw)

            clean = self.transform(raw)
            self._log.info("transform_complete")

            approved = self.validate(clean)
            self._log.info("validate_complete")

            result = self.load(approved)
            self._log.info("load_complete")
            rows_loaded = result if isinstance(result, int) else None

            self.post_load(result, approved)
            self._log.info("post_load_complete")

            # Post-append health checks
            health_report = self._run_health_checks()

            self._finalize_audit(
                audit_id=audit_id,
                status=RunStatus.SUCCESS,
                started_at=started_at,
                rows_extracted=rows_extracted,
                rows_loaded=rows_loaded,
                health_report=health_report,
            )
            return result

        except Exception:
            self._finalize_audit(
                audit_id=audit_id,
                status=RunStatus.FAILED,
                started_at=started_at,
            )
            self._log.exception("pipeline_failed")
            raise

    # --- Audit helpers ---

    def _create_audit_record(self, started_at: datetime) -> int | None:
        """Insert a 'running' audit record. Returns the record ID."""
        if not self.pipeline_name:
            return None
        try:
            with self._connector.session() as session:
                run = PipelineRun(
                    pipeline_name=self.pipeline_name,
                    domain=self.domain,
                    run_status=RunStatus.RUNNING,
                    started_at=started_at,
                )
                session.add(run)
                session.flush()
                audit_id = run.id
            return audit_id
        except Exception:
            self._log.warning("audit_record_creation_failed", exc_info=True)
            return None

    def _finalize_audit(
        self,
        audit_id: int | None,
        status: RunStatus,
        started_at: datetime,
        rows_extracted: int | None = None,
        rows_loaded: int | None = None,
        health_report: HealthReport | None = None,
    ) -> None:
        """Update the audit record with final results."""
        if audit_id is None:
            return
        try:
            with self._connector.session() as session:
                run = session.get(PipelineRun, audit_id)
                if run is None:
                    return
                run.run_status = status
                run.finished_at = datetime.now(timezone.utc)
                run.rows_extracted = rows_extracted
                run.rows_loaded = rows_loaded
                if health_report:
                    run.health_check_passed = health_report.passed
                    run.health_check_details = json.dumps(health_report.to_dict())
        except Exception:
            self._log.warning("audit_record_finalize_failed", exc_info=True)

    # --- Health check helpers ---

    def _run_health_checks(self) -> HealthReport | None:
        """Run post-append health checks if the pipeline defines any."""
        checks = self.get_health_checks()
        if not checks:
            return None
        runner = HealthCheckRunner(checks)
        with self._connector.session() as session:
            report = runner.run_all(session, **self.get_run_context())
        if not report.passed:
            self._log.warning("health_checks_failed", report=report.to_dict())
        else:
            self._log.info("health_checks_passed")
        return report

    def _count_raw(self, raw: RawT) -> int | None:
        """Best-effort row count from raw data."""
        if hasattr(raw, "__len__"):
            return len(raw)  # type: ignore[arg-type]
        return None
