"""Rates observation diagnostic report — health checks, coverage, and data quality.

Reusable CLI script that uses the HealthReporter framework,
quality check framework, and custom coverage SQL for a full DB diagnostic.

Usage:
    python -m scripts.rates.health.rates_fact_observation_report
    python -m scripts.rates.health.rates_fact_observation_report --year 2026
    python -m scripts.rates.health.rates_fact_observation_report --section health
    python -m scripts.rates.health.rates_fact_observation_report --section coverage
    python -m scripts.rates.health.rates_fact_observation_report --section quality
    python -m scripts.rates.health.rates_fact_observation_report --section quality --sigma 4
    python -m scripts.rates.health.rates_fact_observation_report --ccy USD
"""

from __future__ import annotations

import argparse

import pandas as pd

from imdr.config.settings import get_settings
from imdr.connectors.mssql import MSSQLConnector
from imdr.connectors.reader import AnalyticalReader
from imdr.domains.rates.coverage import get_rates_coverage
from imdr.healthchecks.checks import (
    DuplicateCheck,
    FreshnessCheck,
    NullCheck,
    RowCountCheck,
)
from imdr.healthchecks.quality import (
    DistributionCheck,
    RobustStatisticalOutlierCheck,
    SymbolRangeCheck,
)
from imdr.healthchecks.reporter import HealthReporter
from imdr.models.rates import RatesObservation
from imdr.universe.rates import get_rates_universe

PIPELINE_NAME = "rates.historical"
TABLE = "[rates].[fact_observation]"


# ---------------------------------------------------------------------------
# Section 1: Health checks (per-year, via HealthReporter)
# ---------------------------------------------------------------------------

def build_health_checks(freshness_hours: int | None = None) -> list:
    """Compose rates-specific health check list.

    Args:
        freshness_hours: Max staleness for FreshnessCheck. Defaults to
            ``max_staleness_hours`` from pipelines.yml (rates.historical).
    """
    if freshness_hours is None:
        from imdr.config.pipeline_config import get_pipeline_config
        freshness_hours = get_pipeline_config(PIPELINE_NAME).health_checks.max_staleness_hours

    return [
        RowCountCheck(RatesObservation, "ts", expected_min=1),
        NullCheck(RatesObservation, ["value"], "ts"),
        DuplicateCheck(
            RatesObservation,
            ["curve_id", "ts", "quote", "tenor"],
            "ts",
        ),
        FreshnessCheck(RatesObservation, "created_at", max_staleness_hours=freshness_hours),
    ]


# ---------------------------------------------------------------------------
# Section 2: Coverage analysis (custom SQL — rates-specific dimensions)
# ---------------------------------------------------------------------------

def run_coverage_section(reader: AnalyticalReader, years: list[int]) -> None:
    """Analyse coverage: per-curve dates, tenor completeness, quote distribution."""
    print("=" * 70)
    print("  SECTION 2: COVERAGE ANALYSIS")
    print("=" * 70)

    coverage = get_rates_coverage(reader, TABLE, years)

    print("\n  A) Per-curve date coverage:")
    df_cov = coverage.tables.get("per_curve", pd.DataFrame())
    if not df_cov.empty:
        print(df_cov.to_string(index=False))
    else:
        print("    No data found.")

    print("\n  B) Tenor count per curve×quote (latest date):")
    df_tenor = coverage.tables.get("tenor", pd.DataFrame())
    if not df_tenor.empty:
        print(df_tenor.to_string(index=False))
    else:
        print("    No data found.")

    print("\n  C) Row count by quote type:")
    df_quote = coverage.tables.get("quote_dist", pd.DataFrame())
    if not df_quote.empty:
        print(df_quote.to_string(index=False))
        s = coverage.summary
        print(f"\n    Grand total: {s['grand_total_rows']:,} rows across {s['num_quote_types']} quote types")
    else:
        print("    No data found.")

    print("\n  D) Total row count by curve:")
    df_counts = coverage.tables.get("row_counts", pd.DataFrame())
    if not df_counts.empty:
        print(df_counts.to_string(index=False))
    else:
        print("    No data found.")
    print()


# ---------------------------------------------------------------------------
# Section 3: Data quality (via HealthReporter)
# ---------------------------------------------------------------------------

def build_quality_checks(sigma: float | None = None) -> list:
    """Compose rates-specific quality check list.

    Args:
        sigma: Outlier z-score threshold. Defaults to ``n_mad`` from
            pipelines.yml (rates.historical.cleaning).
    """
    from imdr.config.pipeline_config import get_pipeline_config

    cfg = get_pipeline_config(PIPELINE_NAME).cleaning
    sigma = sigma if sigma is not None else cfg.n_mad
    trailing_months = cfg.trailing_months

    universe = get_rates_universe()

    # Per-quote-type ranges from rates.yml expected_ranges
    ranges: dict[str, tuple[float, float]] = {}
    for quote, er in universe.expected_ranges.items():
        ranges[quote] = (er.min, er.max)

    return [
        SymbolRangeCheck(
            ranges=ranges,
            value_column="value",
            symbol_column="quote",
        ),
        RobustStatisticalOutlierCheck(
            value_column="value",
            group_columns=["curve_id", "quote", "tenor"],
            n_mad=sigma,
            trailing_months=trailing_months,
        ),
        DistributionCheck(
            value_column="value",
            group_column="quote",
        ),
    ]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Rates observation diagnostic report -- health, coverage, quality"
    )
    parser.add_argument("--year", type=int, help="Restrict to a single year")
    parser.add_argument(
        "--section",
        choices=["health", "coverage", "quality"],
        help="Run only one section (default: all)",
    )
    parser.add_argument(
        "--sigma",
        type=float,
        default=None,
        help="Statistical outlier z-score threshold (default: from pipelines.yml)",
    )
    parser.add_argument(
        "--ccy",
        type=str,
        help="Filter to a specific currency (for display only)",
    )
    parser.add_argument(
        "--curve",
        type=int,
        help="Filter to a specific curve_id",
    )
    args = parser.parse_args()

    settings = get_settings()
    connector = MSSQLConnector(settings)
    reporter = HealthReporter(connector, PIPELINE_NAME)

    # Determine years
    if args.year:
        years = [args.year]
    else:
        years = reporter.discover_years()

    print(f"\nRates Observation Diagnostic Report")
    print(f"Years: {years}")
    print(f"{'=' * 70}\n")

    run_all = args.section is None

    if run_all or args.section == "health":
        health_checks = build_health_checks()
        reporter.run_health_section(health_checks, years)

    if run_all or args.section == "coverage":
        run_coverage_section(reporter.reader, years)

    if run_all or args.section == "quality":
        quality_checks = build_quality_checks(args.sigma)
        reporter.run_quality_section(quality_checks, years)

    connector.dispose()
    print("Diagnostic report complete.")


if __name__ == "__main__":
    main()
