"""Standard health check implementations.

Each check queries the database to verify data quality after an append.
Context kwargs (e.g. run_date) are passed from the pipeline at runtime.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import case, func, literal
from sqlalchemy.orm import Session

from imdr.healthchecks.base import CheckResult, CheckStatus, HealthCheck


class RowCountCheck(HealthCheck):
    """Verify that at least ``expected_min`` rows exist for the run date."""

    def __init__(self, model: type, date_column: str, expected_min: int = 1) -> None:
        self._model = model
        self._date_col = date_column
        self._expected_min = expected_min

    def run(self, session: Session, **context: Any) -> CheckResult:
        run_date: date = context["run_date"]
        col = getattr(self._model, self._date_col)
        count: int = session.query(func.count(self._model.id)).filter(col == run_date).scalar() or 0
        passed = count >= self._expected_min
        return CheckResult(
            check_name="row_count",
            status=CheckStatus.PASSED if passed else CheckStatus.FAILED,
            message=f"Found {count} rows (expected >= {self._expected_min})",
            details={"actual": count, "expected_min": self._expected_min},
        )


class NullCheck(HealthCheck):
    """Check that critical columns have no NULLs in the latest batch."""

    def __init__(self, model: type, columns: list[str], date_column: str) -> None:
        self._model = model
        self._columns = columns
        self._date_col = date_column

    def run(self, session: Session, **context: Any) -> CheckResult:
        run_date: date = context["run_date"]
        date_col = getattr(self._model, self._date_col)
        null_counts: dict[str, int] = {}

        # Single query with conditional aggregation (instead of N queries)
        agg_exprs = [
            func.sum(case((getattr(self._model, c).is_(None), 1), else_=0)).label(c)
            for c in self._columns
        ]
        result = session.query(*agg_exprs).filter(date_col == run_date).one()
        for col_name, count in zip(self._columns, result):
            if count and count > 0:
                null_counts[col_name] = count

        if null_counts:
            return CheckResult(
                check_name="null_check",
                status=CheckStatus.FAILED,
                message=f"NULLs found in columns: {', '.join(null_counts.keys())}",
                details={"null_counts": null_counts},
            )
        return CheckResult(
            check_name="null_check",
            status=CheckStatus.PASSED,
            message=f"No NULLs in {len(self._columns)} checked columns",
        )


class DuplicateCheck(HealthCheck):
    """Detect duplicate rows based on a set of unique-key columns."""

    def __init__(self, model: type, unique_columns: list[str], date_column: str) -> None:
        self._model = model
        self._unique_columns = unique_columns
        self._date_col = date_column

    def run(self, session: Session, **context: Any) -> CheckResult:
        run_date: date = context["run_date"]
        date_col = getattr(self._model, self._date_col)
        group_cols = [getattr(self._model, c) for c in self._unique_columns]

        dupes = (
            session.query(*group_cols, func.count(self._model.id).label("cnt"))
            .filter(date_col == run_date)
            .group_by(*group_cols)
            .having(func.count(self._model.id) > 1)
            .all()
        )

        if dupes:
            return CheckResult(
                check_name="duplicate_check",
                status=CheckStatus.FAILED,
                message=f"Found {len(dupes)} duplicate group(s)",
                details={"duplicate_groups": len(dupes)},
            )
        return CheckResult(
            check_name="duplicate_check",
            status=CheckStatus.PASSED,
            message="No duplicates detected",
        )


class FreshnessCheck(HealthCheck):
    """Verify that the most recent record is within an acceptable staleness window."""

    def __init__(self, model: type, timestamp_column: str, max_staleness_hours: int = 24) -> None:
        self._model = model
        self._ts_col = timestamp_column
        self._max_hours = max_staleness_hours

    def run(self, session: Session, **context: Any) -> CheckResult:
        col = getattr(self._model, self._ts_col)
        latest: datetime | None = session.query(func.max(col)).scalar()

        if latest is None:
            return CheckResult(
                check_name="freshness",
                status=CheckStatus.FAILED,
                message="No records found in table",
            )

        now = datetime.now(timezone.utc)
        if latest.tzinfo is None:
            age_hours = (now.replace(tzinfo=None) - latest).total_seconds() / 3600
        else:
            age_hours = (now - latest).total_seconds() / 3600

        passed = age_hours <= self._max_hours
        return CheckResult(
            check_name="freshness",
            status=CheckStatus.PASSED if passed else CheckStatus.WARNING,
            message=f"Latest record is {age_hours:.1f}h old (max {self._max_hours}h)",
            details={"age_hours": round(age_hours, 2), "max_staleness_hours": self._max_hours},
        )


class ValueRangeCheck(HealthCheck):
    """Verify a numeric column falls within [min_val, max_val] for the batch."""

    def __init__(
        self, model: type, column: str, min_val: float, max_val: float, date_column: str
    ) -> None:
        self._model = model
        self._column = column
        self._min_val = min_val
        self._max_val = max_val
        self._date_col = date_column

    def run(self, session: Session, **context: Any) -> CheckResult:
        run_date: date = context["run_date"]
        date_col = getattr(self._model, self._date_col)
        val_col = getattr(self._model, self._column)

        result = (
            session.query(func.min(val_col), func.max(val_col))
            .filter(date_col == run_date)
            .one()
        )
        actual_min, actual_max = result

        if actual_min is None:
            return CheckResult(
                check_name=f"value_range_{self._column}",
                status=CheckStatus.WARNING,
                message=f"No values for column '{self._column}' on {run_date}",
            )

        in_range = actual_min >= self._min_val and actual_max <= self._max_val
        return CheckResult(
            check_name=f"value_range_{self._column}",
            status=CheckStatus.PASSED if in_range else CheckStatus.FAILED,
            message=f"{self._column}: [{actual_min}, {actual_max}] vs allowed [{self._min_val}, {self._max_val}]",
            details={
                "actual_min": float(actual_min),
                "actual_max": float(actual_max),
                "allowed_min": self._min_val,
                "allowed_max": self._max_val,
            },
        )
