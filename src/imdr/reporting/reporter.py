"""Post-append query-back verification and success reporting."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import structlog
from sqlalchemy import func
from sqlalchemy.orm import Session

from imdr.healthchecks.base import HealthReport
from imdr.models.audit import RunStatus

log = structlog.get_logger(__name__)


@dataclass
class AppendVerification:
    """Result of querying the DB to verify what was actually inserted."""

    rows_verified: int
    timestamp_range: tuple[datetime, datetime] | None
    missing: int


@dataclass
class SuccessReport:
    """Full pipeline run report — logged and persisted to audit table."""

    pipeline_name: str
    domain: str
    run_date: date
    started_at: datetime
    finished_at: datetime
    rows_extracted: int
    rows_loaded: int
    rows_verified_in_db: int
    missing_records: int
    timestamp_range: tuple[datetime, datetime] | None
    health_report: HealthReport | None
    status: RunStatus

    def to_dict(self) -> dict[str, Any]:
        ts_range = None
        if self.timestamp_range:
            ts_range = [self.timestamp_range[0].isoformat(), self.timestamp_range[1].isoformat()]

        return {
            "pipeline_name": self.pipeline_name,
            "domain": self.domain,
            "run_date": self.run_date.isoformat(),
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat(),
            "rows_extracted": self.rows_extracted,
            "rows_loaded": self.rows_loaded,
            "rows_verified_in_db": self.rows_verified_in_db,
            "missing_records": self.missing_records,
            "timestamp_range": ts_range,
            "health_report": self.health_report.to_dict() if self.health_report else None,
            "status": self.status.value,
        }


class PipelineReporter:
    """Query-back verification against the database after an append."""

    def __init__(self, session: Session, model: type, date_column: str) -> None:
        self._session = session
        self._model = model
        self._date_col = date_column

    def verify_append(self, run_date: date, expected_count: int) -> AppendVerification:
        """Query the DB to verify what was actually inserted."""
        col = getattr(self._model, self._date_col)

        actual_count: int = (
            self._session.query(func.count(self._model.id)).filter(col == run_date).scalar() or 0
        )
        ts_result = (
            self._session.query(
                func.min(self._model.created_at),
                func.max(self._model.created_at),
            )
            .filter(col == run_date)
            .one()
        )
        min_ts, max_ts = ts_result
        ts_range = (min_ts, max_ts) if min_ts and max_ts else None

        verification = AppendVerification(
            rows_verified=actual_count,
            timestamp_range=ts_range,
            missing=expected_count - actual_count,
        )

        log.info(
            "append_verified",
            rows_verified=verification.rows_verified,
            missing=verification.missing,
        )
        return verification
