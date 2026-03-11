"""Shared cleaning infrastructure — domain-agnostic rule ABC, runner, and result types.

Used by all domain-specific cleaning modules (FX OHLC, FX Vol, Rates, etc.).
Each domain implements its own CleaningRule subclasses; the CleaningRunner
orchestrates detection + batch correction with dry-run support.

Usage:
    from imdr.healthchecks.cleaning import CleaningRule, CleaningRunner, CleaningAction, CleaningResult
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pandas as pd
import structlog
from sqlalchemy import text

from imdr.connectors.mssql import MSSQLConnector
from imdr.connectors.reader import AnalyticalReader

log = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class CleaningAction:
    """One correction applied (or proposed in dry-run) to a single row."""

    rule_name: str
    row_id: int
    ts: datetime
    action: str  # e.g. "null_prices", "null_value", "swap_bid_ask"
    detail: str  # human-readable description
    context: dict[str, Any] = field(default_factory=dict)
    # context holds domain-specific fields:
    #   FX OHLC: {"symbol": ..., "series": ...}
    #   FX Vol:  {"pair_id": ..., "strike": ..., "tenor": ...}
    #   Rates:   {"curve_id": ..., "quote": ..., "tenor": ...}


@dataclass
class CleaningResult:
    """Aggregate result for one rule across all detected rows."""

    rule_name: str
    actions: list[CleaningAction] = field(default_factory=list)
    dry_run: bool = True

    @property
    def count(self) -> int:
        return len(self.actions)


# ---------------------------------------------------------------------------
# ABC
# ---------------------------------------------------------------------------

class CleaningRule(ABC):
    """Base class for cleaning rules.

    Each rule knows how to *detect* bad rows and how to *fix* them.
    Subclasses are domain-specific; the runner is generic.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Short identifier for this rule (e.g. 'non_positive')."""
        ...

    @property
    @abstractmethod
    def action_label(self) -> str:
        """What this rule does (e.g. 'null_prices', 'null_value')."""
        ...

    @abstractmethod
    def detect(
        self,
        reader: AnalyticalReader,
        table: str,
        where: str = "",
        params: dict[str, Any] | None = None,
    ) -> pd.DataFrame:
        """Return DataFrame of rows needing correction.  MUST include 'id'."""
        ...

    @abstractmethod
    def build_update_sql(self, ids: list[int]) -> str:
        """Return UPDATE statement for a batch of row IDs."""
        ...

    def build_action(self, row: pd.Series) -> CleaningAction:
        """Build a CleaningAction from a detected row.

        Subclasses should override to populate context with domain-specific fields.
        """
        return CleaningAction(
            rule_name=self.name,
            row_id=int(row["id"]),
            ts=row.get("ts", row.get("obs_date", None)),
            action=self.action_label,
            detail=self.describe(row),
        )

    def describe(self, row: pd.Series) -> str:
        """Human-readable description of the correction for one row."""
        return f"{self.name}: {self.action_label} for row {row.get('id', '?')} @ {row.get('ts', row.get('obs_date', '?'))}"


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

class CleaningRunner:
    """Orchestrates cleaning rules with dry-run support.

    Domain-agnostic: takes a table name and a list of CleaningRule instances.
    """

    def __init__(
        self,
        connector: MSSQLConnector,
        reader: AnalyticalReader,
        rules: list[CleaningRule],
        table: str,
        dry_run: bool = True,
        batch_size: int = 500,
    ) -> None:
        self._connector = connector
        self._reader = reader
        self._rules = rules
        self._table = table
        self._dry_run = dry_run
        self._batch_size = batch_size

    def run(
        self,
        where: str = "",
        params: dict[str, Any] | None = None,
    ) -> list[CleaningResult]:
        results: list[CleaningResult] = []

        # Phase 1: detect all rules on unmodified data (snapshot)
        for rule in self._rules:
            log.info("cleaning_detect", rule=rule.name, dry_run=self._dry_run)
            detected = rule.detect(self._reader, self._table, where, params)

            result = CleaningResult(rule_name=rule.name, dry_run=self._dry_run)

            if detected.empty:
                log.info("cleaning_none", rule=rule.name)
                results.append(result)
                continue

            for _, row in detected.iterrows():
                action = rule.build_action(row)
                result.actions.append(action)

            log.info("cleaning_detected", rule=rule.name, rows=result.count)
            results.append(result)

        # Phase 2: apply all corrections at once (no intra-run cascading)
        if not self._dry_run:
            for rule, result in zip(self._rules, results):
                if result.actions:
                    all_ids = [a.row_id for a in result.actions]
                    self._execute_batches(rule, all_ids)
                    log.info("cleaning_applied", rule=rule.name, rows=result.count)

        return results

    def _execute_batches(self, rule: CleaningRule, ids: list[int]) -> None:
        """Execute UPDATE in batches within a single session."""
        with self._connector.session() as session:
            for i in range(0, len(ids), self._batch_size):
                batch = ids[i : i + self._batch_size]
                sql = rule.build_update_sql(batch)
                session.execute(text(sql))
