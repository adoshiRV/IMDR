"""Shared health report orchestrator.

Runs domain-composed health checks and quality checks,
handles year/window filtering, timing, and formatted printing.

Each domain report script composes its own check list from existing
check classes and passes it to HealthReporter. The reporter does NOT
know which checks to run — only how to orchestrate and print them.

Usage:
    reporter = HealthReporter(connector, "fx.vol")

    # Rolling window (dashboard)
    report = reporter.run_health_window(health_checks, lookback_days=30)

    # Per-year (individual diagnostic scripts)
    years = reporter.discover_years()
    reporter.run_health_section(health_checks, years)
    reporter.run_quality_section(quality_checks, years)
"""

from __future__ import annotations

import time
from datetime import date, timedelta
from typing import Any, Callable

import pandas as pd
from sqlalchemy import text

from imdr.config.pipeline_config import get_pipeline_config
from imdr.connectors.mssql import MSSQLConnector
from imdr.connectors.reader import AnalyticalReader
from imdr.healthchecks.base import (
    CheckStatus,
    HealthCheck,
    HealthCheckRunner,
    HealthReport,
)
from imdr.healthchecks.quality import QualityCheck, QualityResult


class HealthReporter:
    """Orchestrates health checks and quality checks for any domain."""

    def __init__(self, connector: MSSQLConnector, pipeline_name: str) -> None:
        self.config = get_pipeline_config(pipeline_name)
        self.connector = connector
        self.reader = AnalyticalReader(connector)

    def discover_years(self) -> list[int]:
        """Query DISTINCT years from the target table's date column."""
        table = self.config.fully_qualified_table
        date_col = self.config.date_column
        with self.connector.read_engine.connect() as c:
            df = pd.read_sql(
                text(f"SELECT DISTINCT YEAR([{date_col}]) AS yr FROM {table} ORDER BY yr"),
                c,
            )
            return df["yr"].tolist()

    # ── Rolling window health checks ──────────────────────────────

    def run_health_window(
        self,
        checks: list[HealthCheck],
        lookback_days: int = 30,
        quiet: bool = False,
    ) -> HealthReport:
        """Run health checks over a rolling window (last N days)."""
        today = date.today()
        window_start = today - timedelta(days=lookback_days)
        context: dict[str, Any] = {
            "window_start": window_start,
            "window_end": today,
        }

        if not quiet:
            print("=" * 70)
            print(f"  SECTION 1: HEALTH CHECKS (last {lookback_days} days)")
            print("=" * 70)

        runner = HealthCheckRunner(checks)
        t0 = time.perf_counter()

        with self.connector.session() as session:
            report = runner.run_all(session, **context)

        if not quiet:
            status = "PASS" if report.passed else "FAIL"
            elapsed = time.perf_counter() - t0
            print(f"\n  [{status}] Last {lookback_days} days ({window_start} → {today}):")
            for r in report.results:
                icon = "OK" if r.status != CheckStatus.FAILED else "!!"
                print(f"    [{icon}] {r.check_name}: {r.message}")
            print(f"\n  Completed in {elapsed:.1f}s\n")

        return report

    # ── Per-year health checks ────────────────────────────────────

    def run_health_section(
        self,
        checks: list[HealthCheck],
        years: list[int],
        quiet: bool = False,
    ) -> list[HealthReport]:
        """Run ORM health checks per-year via HealthCheckRunner."""
        if not quiet:
            print("=" * 70)
            print("  SECTION 1: HEALTH CHECKS (per-year)")
            print("=" * 70)

        runner = HealthCheckRunner(checks)
        reports: list[HealthReport] = []
        t0 = time.perf_counter()

        for year in years:
            context: dict[str, Any] = {
                "window_start": date(year, 1, 1),
                "window_end": date(year, 12, 31),
            }
            with self.connector.session() as session:
                report = runner.run_all(session, **context)
            if not quiet:
                self.print_year_report(report, year)
            reports.append(report)

        if not quiet:
            self.print_grand_summary(reports, years, time.perf_counter() - t0)
        return reports

    # ── Section: Quality Checks ───────────────────────────────────

    def run_quality_section(
        self,
        checks: list[QualityCheck],
        years: list[int],
        quiet: bool = False,
        enrich: Callable[[QualityResult], QualityResult] | None = None,
    ) -> list[QualityResult]:
        """Run analytical quality checks using AnalyticalReader."""
        if not quiet:
            print("=" * 70)
            print("  SECTION 3: DATA QUALITY")
            print("=" * 70)

        table = self.config.fully_qualified_table
        date_col = self.config.date_column

        year_filter = ""
        params: dict = {}
        if years and len(years) < 6:
            placeholders = ", ".join(f":y{i}" for i in range(len(years)))
            year_filter = f"AND YEAR([{date_col}]) IN ({placeholders})"
            params = {f"y{i}": y for i, y in enumerate(years)}

        results: list[QualityResult] = []
        for check in checks:
            try:
                result = check.run(self.reader, table, where=year_filter, params=params)
                if enrich is not None:
                    result = enrich(result)
                if not quiet:
                    self.print_quality_result(result)
                results.append(result)
            except Exception as exc:
                if not quiet:
                    print(f"\n  [!!] {type(check).__name__}: ERROR — {exc}")

        if not quiet:
            print()
        return results

    # ── Printers ──────────────────────────────────────────────────

    @staticmethod
    def print_year_report(report: HealthReport, year: int) -> None:
        """Print results for a single year."""
        status = "PASS" if report.passed else "FAIL"
        print(f"\n  [{status}] Year {year}:")
        for r in report.results:
            icon = "OK" if r.status != CheckStatus.FAILED else "!!"
            print(f"    [{icon}] {r.check_name}: {r.message}")

    @staticmethod
    def print_grand_summary(
        reports: list[HealthReport],
        years: list[int],
        elapsed: float,
    ) -> None:
        """Print summary across all years."""
        passed = sum(1 for r in reports if r.passed)
        total = len(reports)
        print(f"\n  Summary: {passed}/{total} years passed ({elapsed:.1f}s)")
        if passed < total:
            failed_years = [y for y, r in zip(years, reports) if not r.passed]
            print(f"  Failed years: {failed_years}")
        print()

    @staticmethod
    def print_quality_result(result: QualityResult) -> None:
        """Print a single quality check result."""
        icon = "OK" if result.status.value == "passed" else "!!"
        print(f"\n  [{icon}] {result.check_name}: {result.message}")

        if result.summary is not None and not result.summary.empty:
            print()
            pd.set_option("display.max_columns", 12)
            pd.set_option("display.width", 120)
            print(result.summary.to_string(index=False))

        if result.flagged is not None and not result.flagged.empty:
            print(f"\n  Flagged rows ({len(result.flagged)}):")
            print(result.flagged.to_string(index=False))
