"""Health check framework: base classes and runner."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from sqlalchemy.orm import Session


class CheckStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"


@dataclass
class CheckResult:
    check_name: str
    status: CheckStatus
    message: str
    details: dict[str, Any] | None = None


@dataclass
class HealthReport:
    passed: bool
    results: list[CheckResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "checks": [
                {
                    "name": r.check_name,
                    "status": r.status.value,
                    "message": r.message,
                    "details": r.details,
                }
                for r in self.results
            ],
        }


class HealthCheck(ABC):
    """Single post-append check. Receives a session and context kwargs."""

    @abstractmethod
    def run(self, session: Session, **context: Any) -> CheckResult:
        ...


class HealthCheckRunner:
    """Runs a list of checks and aggregates into a HealthReport."""

    def __init__(self, checks: list[HealthCheck]) -> None:
        self._checks = checks

    def run_all(self, session: Session, **context: Any) -> HealthReport:
        results = [check.run(session, **context) for check in self._checks]
        passed = all(r.status != CheckStatus.FAILED for r in results)
        return HealthReport(passed=passed, results=results)
