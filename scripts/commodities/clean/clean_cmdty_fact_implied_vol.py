"""Commodity Implied Vol cleaning / health / quality / coverage CLI.

Usage:
    python -m scripts.commodities.clean.clean_cmdty_fact_implied_vol --section all
    python -m scripts.commodities.clean.clean_cmdty_fact_implied_vol --section health
    python -m scripts.commodities.clean.clean_cmdty_fact_implied_vol --section clean --execute
"""
from __future__ import annotations

import argparse
import sys

import structlog

from imdr.config.pipeline_config import get_pipeline_config
from imdr.config.settings import get_settings
from imdr.connectors.mssql import MSSQLConnector
from imdr.connectors.reader import AnalyticalReader
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
from imdr.models.commodities import CmdtyFactImpliedVol
from imdr.universe.commodities import get_commodities_universe
from imdr.utils.logging import configure_logging

log = structlog.get_logger(__name__)

PIPELINE_NAME = "commodities.vol"
TABLE = "[commodities].[fact_implied_vol]"


def build_cleaning_rules(
    n_mad: float | None = None,
    trailing_months: int | None = None,
    pct_threshold: float | None = None,
    rule: str | None = None,
) -> list:
    """Build cleaning rules with defaults from pipelines.yml."""
    from imdr.domains.commodities.clean_implied_vol import (
        HardBoundViolationRule,
        PercentageChangeRule,
        RobustOutlierRule,
    )

    cfg = get_pipeline_config(PIPELINE_NAME).cleaning
    universe = get_commodities_universe()

    n_mad = n_mad if n_mad is not None else cfg.n_mad
    trailing_months = trailing_months if trailing_months is not None else cfg.trailing_months
    pct_threshold = pct_threshold if pct_threshold is not None else cfg.pct_threshold
    min_obs = cfg.min_obs

    # Hard bounds from universe quality config
    quality_ranges = universe.vol_quality_ranges()

    all_rules = [
        HardBoundViolationRule(ranges=quality_ranges),
        RobustOutlierRule(n_mad=n_mad, trailing_months=trailing_months, min_obs=min_obs),
        PercentageChangeRule(threshold_pct=pct_threshold),
    ]

    if rule:
        return [r for r in all_rules if r.name == rule]
    return all_rules


def build_health_checks(freshness_hours: int | None = None) -> list:
    """Build health check instances for the implied vol table."""
    cfg = get_pipeline_config(PIPELINE_NAME).health_checks
    if freshness_hours is None:
        freshness_hours = cfg.max_staleness_hours

    universe = get_commodities_universe()
    quality_ranges = universe.vol_quality_ranges()
    vol_min = min(lo for lo, _ in quality_ranges.values()) if quality_ranges else 0
    vol_max = max(hi for _, hi in quality_ranges.values()) if quality_ranges else 300

    return [
        RowCountCheck(CmdtyFactImpliedVol, "obs_date", cfg.row_count_min),
        NullCheck(CmdtyFactImpliedVol, ["vol"], "obs_date"),
        DuplicateCheck(CmdtyFactImpliedVol, ["commodity_id", "obs_date", "strike", "tenor"], "obs_date"),
        FreshnessCheck(CmdtyFactImpliedVol, "created_at", max_staleness_hours=freshness_hours),
        ValueRangeCheck(CmdtyFactImpliedVol, "vol", vol_min, vol_max, "obs_date"),
    ]


def build_quality_checks() -> list:
    """Build quality check instances for diagnostic use."""
    from imdr.healthchecks.quality import DistributionCheck

    return [
        DistributionCheck(value_column="vol", group_column="strike"),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Commodity Implied Vol Cleaning CLI")
    add_common_clean_args(parser)
    parser.add_argument("--section", default="all",
                        choices=["clean", "health", "coverage", "quality", "all"])
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings)
    connector = MSSQLConnector(settings)
    reader = AnalyticalReader(connector)

    try:
        sections = (
            ["clean", "health", "coverage", "quality"]
            if args.section == "all"
            else [args.section]
        )

        if "health" in sections:
            reporter = HealthReporter(connector, PIPELINE_NAME)
            years = reporter.discover_years()
            reporter.run_health_section(build_health_checks(), years)

        if "quality" in sections:
            reporter = HealthReporter(connector, PIPELINE_NAME)
            years = reporter.discover_years()
            reporter.run_quality_section(build_quality_checks(), years)

        if "clean" in sections:
            rules = build_cleaning_rules(
                n_mad=args.n_mad,
                trailing_months=args.trailing_months,
                pct_threshold=args.pct_threshold,
            )
            runner = CleaningRunner(
                connector=connector, reader=reader,
                rules=rules, table=TABLE,
                dry_run=not args.execute,
                batch_size=args.batch_size,
            )

            where = ""
            if hasattr(args, "year") and args.year:
                where = f"AND YEAR([obs_date]) = {args.year}"

            results = runner.run(where=where)
            print_clean_summary(results, dry_run=not args.execute, null_action="null_vol")

        return 0
    except Exception:
        log.exception("cleaning_failed")
        return 1
    finally:
        connector.dispose()


if __name__ == "__main__":
    sys.exit(main())
