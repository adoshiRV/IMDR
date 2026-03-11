"""FX Vol diagnostic report — health checks, coverage, and data quality.

Reusable CLI script that uses the HealthReporter framework,
quality check framework, and custom coverage SQL for a full DB diagnostic.

Usage:
    python -m scripts.fx.health.fx_vol_report
    python -m scripts.fx.health.fx_vol_report --year 2026
    python -m scripts.fx.health.fx_vol_report --section health
    python -m scripts.fx.health.fx_vol_report --section coverage
    python -m scripts.fx.health.fx_vol_report --section quality
    python -m scripts.fx.health.fx_vol_report --section quality --sigma 4
    python -m scripts.fx.health.fx_vol_report --pair 1
"""

from __future__ import annotations

import argparse

import pandas as pd

from imdr.config.settings import get_settings
from imdr.connectors.mssql import MSSQLConnector
from imdr.connectors.reader import AnalyticalReader
from imdr.domains.fx.coverage import get_vol_coverage
from imdr.healthchecks.checks import (
    DuplicateCheck,
    FreshnessCheck,
    NullCheck,
    RowCountCheck,
    ValueRangeCheck,
)
from imdr.healthchecks.quality import (
    CompositeRangeCheck,
    DistributionCheck,
    PercentageChangeCheck,
    RobustStatisticalOutlierCheck,
)
from imdr.healthchecks.reporter import HealthReporter
from imdr.models.fx_vol import FXFactVol
from imdr.universe.fx import get_fx_universe

PIPELINE_NAME = "fx.vol"
TABLE = "[fx].[fact_vol]"


# ---------------------------------------------------------------------------
# Section 1: Health checks (per-year, via HealthReporter)
# ---------------------------------------------------------------------------

def build_health_checks(freshness_hours: int | None = None) -> list:
    """Compose vol-specific health check list.

    Args:
        freshness_hours: Max staleness for FreshnessCheck. Defaults to
            ``max_staleness_hours`` from pipelines.yml (fx.vol).
    """
    if freshness_hours is None:
        from imdr.config.pipeline_config import get_pipeline_config
        freshness_hours = get_pipeline_config(PIPELINE_NAME).health_checks.max_staleness_hours

    # Derive value range bounds from per-(strike, vol_type) ranges in fx.yml
    universe = get_fx_universe()
    vq = universe.vol_quality_config()
    vol_min = min(r[0] for r in vq.ranges.values())
    vol_max = max(r[1] for r in vq.ranges.values())

    return [
        RowCountCheck(FXFactVol, "obs_date", expected_min=50),
        NullCheck(FXFactVol, ["value"], "obs_date"),
        DuplicateCheck(
            FXFactVol,
            ["pair_id", "obs_date", "strike", "tenor", "vol_type"],
            "obs_date",
        ),
        FreshnessCheck(FXFactVol, "created_at", max_staleness_hours=freshness_hours),
        ValueRangeCheck(FXFactVol, "value", vol_min, vol_max, "obs_date"),
    ]


# ---------------------------------------------------------------------------
# Section 2: Coverage analysis (custom SQL — vol-specific dimensions)
# ---------------------------------------------------------------------------

def run_coverage_section(reader: AnalyticalReader, years: list[int]) -> None:
    """Analyse coverage: per-pair dates, strike×tenor grid, row counts."""
    print("=" * 70)
    print("  SECTION 2: COVERAGE ANALYSIS")
    print("=" * 70)

    coverage = get_vol_coverage(reader, TABLE, years)

    print("\n  A) Per-pair date coverage:")
    df_cov = coverage.tables.get("per_pair", pd.DataFrame())
    if not df_cov.empty:
        print(df_cov.to_string(index=False))
    else:
        print("    No data found.")

    print("\n  B) Strike×tenor grid completeness (latest obs_date, per pair):")
    df_grid = coverage.tables.get("grid", pd.DataFrame())
    if not df_grid.empty:
        print(df_grid.to_string(index=False))
    else:
        print("    No data found.")

    print("\n  C) Total row count by pair:")
    df_counts = coverage.tables.get("row_counts", pd.DataFrame())
    if not df_counts.empty:
        print(df_counts.to_string(index=False))
        s = coverage.summary
        print(f"\n    Grand total: {s['grand_total_rows']:,} rows across {s['num_pairs']} pairs")
    else:
        print("    No data found.")
    print()


# ---------------------------------------------------------------------------
# Section 3: Data quality (via HealthReporter)
# ---------------------------------------------------------------------------

def build_quality_checks(sigma: float | None = None) -> list:
    """Compose vol-specific quality check list.

    Args:
        sigma: Outlier z-score threshold. Defaults to ``n_mad`` from
            pipelines.yml (fx.vol.cleaning).
    """
    from imdr.config.pipeline_config import get_pipeline_config

    cfg = get_pipeline_config(PIPELINE_NAME).cleaning
    sigma = sigma if sigma is not None else cfg.n_mad
    trailing_months = cfg.trailing_months
    pct_threshold = cfg.pct_threshold

    universe = get_fx_universe()
    vq = universe.vol_quality_config()

    return [
        CompositeRangeCheck(
            range_map=vq.ranges,
            key_columns=["strike", "vol_type"],
            value_column="value",
        ),
        PercentageChangeCheck(
            value_column="value",
            group_columns=["pair_id", "strike", "tenor", "vol_type"],
            ts_column="obs_date",
            threshold_pct=pct_threshold,
        ),
        RobustStatisticalOutlierCheck(
            value_column="value",
            group_columns=["pair_id", "strike", "tenor", "vol_type"],
            n_mad=sigma,
            trailing_months=trailing_months,
        ),
        DistributionCheck(
            value_column="value",
            group_column="strike",
        ),
    ]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="FX Vol diagnostic report -- health checks, coverage, data quality"
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
        "--pair",
        type=int,
        help="Filter to a specific pair_id",
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

    print(f"\nFX Vol Diagnostic Report")
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
