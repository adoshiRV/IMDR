"""FX OHLC diagnostic report — health checks, missing data, and data quality.

Reusable CLI script that uses the HealthReporter framework,
quality check framework, and CoverageAnalyzer for a full DB diagnostic.

Usage:
    python -m scripts.fx.health.fx_ohlc_report
    python -m scripts.fx.health.fx_ohlc_report --year 2024
    python -m scripts.fx.health.fx_ohlc_report --section health
    python -m scripts.fx.health.fx_ohlc_report --section missing
    python -m scripts.fx.health.fx_ohlc_report --section quality
    python -m scripts.fx.health.fx_ohlc_report --section quality --sigma 3
    python -m scripts.fx.health.fx_ohlc_report --basis-threshold 3
"""

from __future__ import annotations

import argparse

import pandas as pd

from imdr.config.settings import get_settings
from imdr.connectors.mssql import MSSQLConnector
from imdr.connectors.reader import AnalyticalReader
from imdr.domains.fx.coverage import get_ohlc_coverage
from imdr.healthchecks.checks import (
    DuplicateCheck,
    FreshnessCheck,
    NullCheck,
    RowCountCheck,
    ValueRangeCheck,
)
from imdr.healthchecks.quality import (
    ColumnOrderCheck,
    DistributionCheck,
    PositiveValueCheck,
    ReturnDistributionCheck,
    RobustStatisticalOutlierCheck,
    SeriesBasisCheck,
    StatisticalOutlierCheck,
    SymbolRangeCheck,
)
from imdr.healthchecks.reporter import HealthReporter
from imdr.models.fx_ohlc import FXFactOHLC
from imdr.universe.fx import get_fx_universe

PIPELINE_NAME = "fx.ohlc"
TABLE = "[fx].[fact_ohlc]"
PRICE_COLUMNS = [
    "open_px", "high_px", "low_px", "close_px",
    "mid_px", "mid_mean_px", "mid_median_px", "bid", "ask",
]


# ---------------------------------------------------------------------------
# Section 1: Health checks (per-year, via HealthReporter)
# ---------------------------------------------------------------------------

def build_health_checks(freshness_hours: int | None = None) -> list:
    """Compose OHLC-specific health check list.

    Args:
        freshness_hours: Max staleness for FreshnessCheck. Defaults to
            ``max_staleness_hours`` from pipelines.yml (fx.ohlc).
    """
    if freshness_hours is None:
        from imdr.config.pipeline_config import get_pipeline_config
        freshness_hours = get_pipeline_config(PIPELINE_NAME).health_checks.max_staleness_hours

    # Derive value range bounds from per-symbol expected ranges in fx.yml
    universe = get_fx_universe()
    all_ranges = [
        universe.expected_range_for(sym)
        for sym in universe.api_symbols()
    ]
    all_ranges = [r for r in all_ranges if r is not None]
    price_min = min(r.min for r in all_ranges) if all_ranges else 0.0001
    price_max = max(r.max for r in all_ranges) if all_ranges else 100000.0

    return [
        RowCountCheck(FXFactOHLC, "ts", expected_min=10),
        NullCheck(FXFactOHLC, PRICE_COLUMNS, "ts"),
        DuplicateCheck(FXFactOHLC, ["ts", "symbol", "series", "tenor"], "ts"),
        FreshnessCheck(FXFactOHLC, "created_at", max_staleness_hours=freshness_hours),
        ValueRangeCheck(FXFactOHLC, "close_px", price_min, price_max, "ts"),
        ValueRangeCheck(FXFactOHLC, "mid_px", price_min, price_max, "ts"),
    ]


# ---------------------------------------------------------------------------
# Section 2: Missing data analysis (market-hours aware) — OHLC-specific
# ---------------------------------------------------------------------------

def run_missing_section(reader: AnalyticalReader, years: list[int]) -> None:
    """Analyse coverage gaps per symbol, excluding FX market close hours."""
    print("=" * 70)
    print("  SECTION 2: MISSING DATA ANALYSIS (market-hours aware)")
    print("=" * 70)

    coverage = get_ohlc_coverage(reader, TABLE, years)
    df_cov = coverage.tables.get("per_symbol", pd.DataFrame())
    df_gaps = coverage.tables.get("gaps", pd.DataFrame())

    # 2A: Per-symbol coverage
    print("\n  A) Per-symbol coverage (actual vs expected market hours):")
    if not df_cov.empty:
        display_cols = ["symbol", "class", "actual_hours", "expected_hours",
                        "missing_hours", "coverage_pct"]
        print(df_cov[display_cols].to_string(index=False))
    else:
        print("    No data found.")

    # 2B: Largest gaps (market hours only)
    print("\n  B) Largest gaps (market hours, excluding weekends, top 20):")
    if not df_gaps.empty:
        display_cols = ["symbol", "series", "gap_start", "gap_end",
                        "calendar_gap_hours", "market_gap_hours"]
        print(df_gaps[display_cols].to_string(index=False))
    else:
        print("    No significant market-hour gaps detected.")

    # 2C: Summary
    print("\n  C) Overall coverage summary:")
    s = coverage.summary
    if s:
        print(f"    Total missing market hours (all symbols): {s['total_missing_hours']:,}")
        print(f"    Average coverage: {s['avg_coverage_pct']:.1f}%")
        print(f"    Worst:  {s['worst_symbol']} ({s['worst_pct']:.1f}%)")
        print(f"    Best:   {s['best_symbol']} ({s['best_pct']:.1f}%)")
        print()
        print("    Note: EM Asian currencies (INR, KRW, TWD, THB, IDR, PHP) have")
        print("    naturally lower hourly coverage due to restricted local trading hours.")
    print()


# ---------------------------------------------------------------------------
# Section 3: Data quality (via HealthReporter)
# ---------------------------------------------------------------------------

def build_quality_checks(sigma: float | None = None, basis_threshold: float = 5.0) -> list:
    """Compose OHLC-specific quality check list.

    Args:
        sigma: Outlier z-score threshold. Defaults to ``n_mad`` from
            pipelines.yml (fx.ohlc.cleaning).
        basis_threshold: Forward/spot basis threshold %.
    """
    from imdr.config.pipeline_config import get_pipeline_config

    cfg = get_pipeline_config(PIPELINE_NAME).cleaning
    sigma = sigma if sigma is not None else cfg.n_mad
    trailing_months = cfg.trailing_months

    universe = get_fx_universe()

    ranges: dict[str, tuple[float, float]] = {}
    for sym in universe.api_symbols():
        er = universe.expected_range_for(sym)
        if er:
            ranges[sym] = (er.min, er.max)

    return [
        PositiveValueCheck(columns=PRICE_COLUMNS),
        ColumnOrderCheck(rules=[
            ("bid", "<=", "ask"),
            ("low_px", "<=", "open_px"),
            ("low_px", "<=", "close_px"),
            ("high_px", ">=", "open_px"),
            ("high_px", ">=", "close_px"),
        ]),
        SymbolRangeCheck(ranges=ranges, value_column="close_px"),
        DistributionCheck(
            value_column="close_px", group_column="symbol",
            series_filter="SPOT",
        ),
        ReturnDistributionCheck(
            value_column="close_px", group_column="symbol",
            ts_column="ts", series_filter="SPOT",
        ),
        StatisticalOutlierCheck(
            value_column="close_px", group_column="symbol",
            n_sigma=sigma, series_filter="SPOT",
        ),
        RobustStatisticalOutlierCheck(
            value_column="close_px",
            group_columns=["symbol", "series"],
            n_mad=sigma,
            trailing_months=trailing_months,
        ),
        SeriesBasisCheck(
            base_series="SPOT",
            compare_series=["FORWARD_1M", "NDF_1M"],
            value_column="close_px",
            threshold_pct=basis_threshold,
        ),
    ]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="FX OHLC diagnostic report -- health checks, missing data, data quality"
    )
    parser.add_argument("--year", type=int, help="Restrict to a single year")
    parser.add_argument(
        "--section",
        choices=["health", "missing", "quality"],
        help="Run only one section (default: all)",
    )
    parser.add_argument(
        "--sigma",
        type=float,
        default=None,
        help="Statistical outlier z-score threshold (default: from pipelines.yml)",
    )
    parser.add_argument(
        "--basis-threshold",
        type=float,
        default=5.0,
        help="Forward/spot basis threshold %% (default: 5.0)",
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

    print(f"\nFX OHLC Diagnostic Report")
    print(f"Years: {years}")
    print(f"{'=' * 70}\n")

    run_all = args.section is None

    if run_all or args.section == "health":
        health_checks = build_health_checks()
        reporter.run_health_section(health_checks, years)

    if run_all or args.section == "missing":
        run_missing_section(reporter.reader, years)

    if run_all or args.section == "quality":
        quality_checks = build_quality_checks(args.sigma, args.basis_threshold)
        reporter.run_quality_section(quality_checks, years)

    connector.dispose()
    print("Diagnostic report complete.")


if __name__ == "__main__":
    main()
