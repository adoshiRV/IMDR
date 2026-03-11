"""Data model for the weekly health dashboard email.

Aggregates health reports, coverage data, quality results, and cleaning
dry-run results across all domains into a single structure for rendering.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pandas as pd

from imdr.healthchecks.base import HealthReport
from imdr.healthchecks.cleaning import CleaningResult
from imdr.healthchecks.quality import QualityResult


@dataclass
class CoverageData:
    """Domain-specific coverage tables."""

    tables: dict[str, pd.DataFrame] = field(default_factory=dict)
    summary: dict[str, Any] = field(default_factory=dict)


@dataclass
class DomainReport:
    """All health data for one domain."""

    domain_name: str  # "FX OHLC", "FX Vol", "Rates"
    table_name: str  # "[fx].[fact_ohlc]"
    years: list[int] = field(default_factory=list)
    health_reports: list[HealthReport] = field(default_factory=list)
    coverage: CoverageData = field(default_factory=CoverageData)
    quality_results: list[QualityResult] = field(default_factory=list)
    cleaning_results: list[CleaningResult] = field(default_factory=list)

    @property
    def health_passed(self) -> bool:
        return all(r.passed for r in self.health_reports)

    @property
    def total_cleaning_flags(self) -> int:
        return sum(r.count for r in self.cleaning_results)


@dataclass
class WeeklyDashboard:
    """Container for all domain reports."""

    generated_at: datetime
    domains: list[DomainReport] = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        return all(d.health_passed for d in self.domains)
