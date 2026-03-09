"""Run report — in-memory event buffer flushed to JSONL.

Complementary to the MSSQL audit trail (PipelineRun):
- audit.pipeline_runs → queryable status ("did pipeline X succeed?")
- RunReport JSONL → detailed ops log ("which symbols failed, why, what was dropped")
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


class EventLevel(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class RunEvent:
    """A single event in a run report."""

    timestamp: datetime
    level: EventLevel
    category: str
    message: str
    details: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "timestamp": self.timestamp.isoformat(),
            "level": self.level.value,
            "category": self.category,
            "message": self.message,
        }
        if self.details:
            d["details"] = self.details
        return d


@dataclass
class RunReport:
    """Accumulates events during a pipeline run for detailed JSONL logging."""

    pipeline_name: str = ""
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None
    events: list[RunEvent] = field(default_factory=list)

    def _add(self, level: EventLevel, category: str, message: str, details: dict[str, Any] | None = None) -> None:
        self.events.append(RunEvent(
            timestamp=datetime.now(timezone.utc),
            level=level,
            category=category,
            message=message,
            details=details,
        ))

    def info(self, category: str, message: str, details: dict[str, Any] | None = None) -> None:
        self._add(EventLevel.INFO, category, message, details)

    def warning(self, category: str, message: str, details: dict[str, Any] | None = None) -> None:
        self._add(EventLevel.WARNING, category, message, details)

    def error(self, category: str, message: str, details: dict[str, Any] | None = None) -> None:
        self._add(EventLevel.ERROR, category, message, details)

    def finish(self) -> None:
        self.finished_at = datetime.now(timezone.utc)

    @property
    def has_errors(self) -> bool:
        return any(e.level == EventLevel.ERROR for e in self.events)

    @property
    def has_warnings(self) -> bool:
        return any(e.level == EventLevel.WARNING for e in self.events)

    def events_by_level(self, level: EventLevel) -> list[RunEvent]:
        return [e for e in self.events if e.level == level]

    def events_by_category(self, category: str) -> list[RunEvent]:
        return [e for e in self.events if e.category == category]

    def to_dict(self) -> dict[str, Any]:
        return {
            "pipeline_name": self.pipeline_name,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "event_count": len(self.events),
            "errors": len(self.events_by_level(EventLevel.ERROR)),
            "warnings": len(self.events_by_level(EventLevel.WARNING)),
            "events": [e.to_dict() for e in self.events],
        }

    def flush_jsonl(self, path: Path) -> None:
        """Write all events as newline-delimited JSON to a file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a") as f:
            header = {
                "type": "run_header",
                "pipeline_name": self.pipeline_name,
                "started_at": self.started_at.isoformat(),
                "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            }
            f.write(json.dumps(header) + "\n")
            for event in self.events:
                f.write(json.dumps(event.to_dict()) + "\n")
