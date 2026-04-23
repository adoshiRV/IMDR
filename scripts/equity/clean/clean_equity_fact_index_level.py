"""CLI script for cleaning equity index level data.

Detects and corrects data quality issues in [equities].[fact_index_level].
Dry-run by default — pass --execute to apply changes.

Usage:
    python -m scripts.equity.clean.clean_equity_fact_index_level
    python -m scripts.equity.clean.clean_equity_fact_index_level --execute
    python -m scripts.equity.clean.clean_equity_fact_index_level --section health
    python -m scripts.equity.clean.clean_equity_fact_index_level --section coverage
    python -m scripts.equity.clean.clean_equity_fact_index_level --section all
"""

from __future__ import annotations

import argparse

from imdr.config.pipeline_config import get_pipeline_config
from imdr.config.settings import get_settings
from imdr.connectors.mssql import MSSQLConnector
from imdr.connectors.reader import AnalyticalReader
from imdr.domains.equity.clean_index import IndexHardBoundViolationRule
from imdr.domains.equity.coverage import get_index_coverage
from imdr.healthchecks.checks import (
    DuplicateCheck,
    FreshnessCheck,
    NullCheck,
    RowCountCheck,
    ValueRangeCheck,
)
from imdr.healthchecks.clean_cli import add_common_clean_args, print_clean_summary
from imdr.healthchecks.cleaning import CleaningRunner
from imdr.healthchecks.reporter import HealthReporter
from imdr.models.equity import EquityFactIndexLevel

PIPELINE_NAME = "equity.index"
TABLE = "[equities].[fact_index_level]"


# ---------------------------------------------------------------------------
# Builders (MUST be importable by dashboard + imdr_clean.py)
# ---------------------------------------------------------------------------


def build_cleaning_rules(rule: str | None = None) -> list:
    """Build cleaning rules for equity index levels."""
    cfg = get_pipeline_config(PIPELINE_NAME)
    vr = cfg.health_checks.value_ranges.get("close_level")
    min_val = vr.min if vr else 1.0
    max_val = vr.max if vr else 100_000.0

    all_rules = [IndexHardBoundViolationRule(min_val=min_val, max_val=max_val)]

    if rule:
        return [r for r in all_rules if r.name == rule]
    return all_rules


def build_health_checks(freshness_hours: int | None = None) -> list:
    """Build health checks for equity index levels."""
    cfg = get_pipeline_config(PIPELINE_NAME)
    hc = cfg.health_checks
    freshness = freshness_hours or hc.max_staleness_hours

    checks = [
        RowCountCheck(EquityFactIndexLevel, cfg.date_column, hc.row_count_min),
        NullCheck(EquityFactIndexLevel, cfg.required_columns, cfg.date_column),
        DuplicateCheck(EquityFactIndexLevel, cfg.unique_columns, cfg.date_column),
        FreshnessCheck(EquityFactIndexLevel, "created_at", freshness),
    ]
    for col_name, vr in hc.value_ranges.items():
        checks.append(
            ValueRangeCheck(EquityFactIndexLevel, col_name, vr.min, vr.max, cfg.date_column)
        )
    return checks


def build_quality_checks() -> list:
    """Build quality checks for equity index levels."""
    return []


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="Equity Index Level Cleaning CLI")
    add_common_clean_args(parser, rule_names=["hard_bound"])
    args = parser.parse_args()

    settings = get_settings()
    connector = MSSQLConnector(settings)
    reader = AnalyticalReader(connector.read_engine)

    section = getattr(args, "section", "clean")

    if section in ("health", "all"):
        reporter = HealthReporter(connector, PIPELINE_NAME)
        health_report = reporter.run_health_window(build_health_checks(), lookback_days=30)
        print(health_report)

    if section in ("coverage", "all"):
        years = [args.year] if hasattr(args, "year") and args.year else [2025, 2026]
        cov = get_index_coverage(reader, TABLE, years)
        for name, df in cov.tables.items():
            print(f"\n=== {name} ===")
            print(df.to_string())
        print(f"\nSummary: {cov.summary}")

    if section in ("clean", "all"):
        rules = build_cleaning_rules(rule=getattr(args, "rule", None))
        runner = CleaningRunner(
            connector=connector, reader=reader, rules=rules,
            table=TABLE, dry_run=not getattr(args, "execute", False),
        )
        results = runner.run()
        print_clean_summary(results)

    connector.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
