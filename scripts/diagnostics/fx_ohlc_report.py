"""FX OHLC diagnostic report — health checks, missing data, and data quality.

Reusable CLI script that uses the existing health check framework,
quality check framework, and CoverageAnalyzer for a full DB diagnostic.

Usage:
    python -m scripts.diagnostics.fx_ohlc_report
    python -m scripts.diagnostics.fx_ohlc_report --year 2024
    python -m scripts.diagnostics.fx_ohlc_report --section health
    python -m scripts.diagnostics.fx_ohlc_report --section missing
    python -m scripts.diagnostics.fx_ohlc_report --section quality
    python -m scripts.diagnostics.fx_ohlc_report --section quality --sigma 3
    python -m scripts.diagnostics.fx_ohlc_report --basis-threshold 3
"""

from __future__ import annotations

import argparse
import time

import pandas as pd
from sqlalchemy import text

from imdr.config.settings import get_settings
from imdr.connectors.mssql import MSSQLConnector
from imdr.connectors.reader import AnalyticalReader
from imdr.healthchecks.quality import (
    ColumnOrderCheck,
    CoverageAnalyzer,
    DistributionCheck,
    PositiveValueCheck,
    QualityResult,
    ReturnDistributionCheck,
    RobustStatisticalOutlierCheck,
    SeriesBasisCheck,
    StatisticalOutlierCheck,
    SymbolRangeCheck,
)
from imdr.universe.fx import get_fx_universe
from scripts.migrations.load_fx_fact_ohlc import (
    discover_years,
    print_grand_summary,
    print_year_report,
    run_year_health_checks,
)

TABLE = "[fx].[fact_ohlc]"
PRICE_COLUMNS = [
    "open_px", "high_px", "low_px", "close_px",
    "mid_px", "mid_mean_px", "mid_median_px", "bid", "ask",
]


# ---------------------------------------------------------------------------
# Section 1: Health checks (reuses load script's per-year checks)
# ---------------------------------------------------------------------------

def run_health_section(connector: MSSQLConnector, years: list[int]) -> None:
    """Run per-year health checks and print summary."""
    print("=" * 70)
    print("  SECTION 1: HEALTH CHECKS (per-year)")
    print("=" * 70)

    reports = []
    t0 = time.perf_counter()
    for year in years:
        rpt = run_year_health_checks(connector, year)
        print_year_report(rpt)
        reports.append(rpt)

    print_grand_summary(reports, time.perf_counter() - t0)


# ---------------------------------------------------------------------------
# Section 2: Missing data analysis (market-hours aware)
# ---------------------------------------------------------------------------

def run_missing_section(reader: AnalyticalReader, years: list[int]) -> None:
    """Analyse coverage gaps per symbol, excluding FX market close hours."""
    print("=" * 70)
    print("  SECTION 2: MISSING DATA ANALYSIS (market-hours aware)")
    print("=" * 70)

    universe = get_fx_universe()

    year_filter = ""
    params: dict = {}
    if years and len(years) < 6:
        placeholders = ", ".join(f":y{i}" for i in range(len(years)))
        year_filter = f"AND YEAR(ts) IN ({placeholders})"
        params = {f"y{i}": y for i, y in enumerate(years)}

    analyzer = CoverageAnalyzer(
        ts_column="ts",
        symbol_column="symbol",
        is_market_open=universe.is_fx_open,
    )

    # 2A: Per-symbol coverage
    print("\n  A) Per-symbol coverage (actual vs expected market hours):")
    df_cov = analyzer.coverage(reader, TABLE, where=year_filter, params=params)
    if not df_cov.empty:
        # Add classification column
        def _classify(sym: str) -> str:
            non_usd = sym.replace("USD", "")
            try:
                return universe.classification_for(non_usd)
            except KeyError:
                return "unknown"

        df_cov.insert(1, "class", df_cov["symbol"].apply(_classify))
        # Format for display
        display_cols = ["symbol", "class", "actual_hours", "expected_hours",
                        "missing_hours", "coverage_pct"]
        print(df_cov[display_cols].to_string(index=False))
    else:
        print("    No data found.")

    # 2B: Largest gaps (market hours only)
    print("\n  B) Largest gaps (market hours, excluding weekends, top 20):")
    df_gaps = analyzer.gaps(reader, TABLE, where=year_filter, params=params)
    if not df_gaps.empty:
        display_cols = ["symbol", "series", "gap_start", "gap_end",
                        "calendar_gap_hours", "market_gap_hours"]
        print(df_gaps[display_cols].to_string(index=False))
    else:
        print("    No significant market-hour gaps detected.")

    # 2C: Summary
    print("\n  C) Overall coverage summary:")
    if not df_cov.empty:
        total_missing = int(df_cov["missing_hours"].sum())
        avg_coverage = df_cov["coverage_pct"].mean()
        worst = df_cov.iloc[0]
        best = df_cov.iloc[-1]
        print(f"    Total missing market hours (all symbols): {total_missing:,}")
        print(f"    Average coverage: {avg_coverage:.1f}%")
        print(f"    Worst:  {worst['symbol']} ({worst['coverage_pct']:.1f}%)")
        print(f"    Best:   {best['symbol']} ({best['coverage_pct']:.1f}%)")
        print()
        print("    Note: EM Asian currencies (INR, KRW, TWD, THB, IDR, PHP) have")
        print("    naturally lower hourly coverage due to restricted local trading hours.")
    print()


# ---------------------------------------------------------------------------
# Section 3: Data quality
# ---------------------------------------------------------------------------

def _print_quality_result(result: QualityResult) -> None:
    """Print a single quality check result."""
    icon = "OK" if result.status.value == "passed" else "!!"
    print(f"\n  [{icon}] {result.check_name}: {result.message}")

    if result.summary is not None and not result.summary.empty:
        print()
        # Limit wide DataFrames
        pd.set_option("display.max_columns", 12)
        pd.set_option("display.width", 120)
        print(result.summary.to_string(index=False))

    if result.flagged is not None and not result.flagged.empty:
        print(f"\n  Flagged rows ({len(result.flagged)}):")
        print(result.flagged.to_string(index=False))


def run_quality_section(
    reader: AnalyticalReader,
    years: list[int],
    sigma: float,
    basis_threshold: float,
) -> None:
    """Run data quality checks using the quality check framework."""
    print("=" * 70)
    print(f"  SECTION 3: DATA QUALITY (sigma={sigma}, basis={basis_threshold}%)")
    print("=" * 70)

    universe = get_fx_universe()

    year_filter = ""
    params: dict = {}
    if years and len(years) < 6:
        placeholders = ", ".join(f":y{i}" for i in range(len(years)))
        year_filter = f"AND YEAR(ts) IN ({placeholders})"
        params = {f"y{i}": y for i, y in enumerate(years)}

    # Build per-symbol ranges from config
    ranges: dict[str, tuple[float, float]] = {}
    for sym in universe.api_symbols():
        er = universe.expected_range_for(sym)
        if er:
            ranges[sym] = (er.min, er.max)

    checks = [
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
            trailing_months=12,
        ),
        SeriesBasisCheck(
            base_series="SPOT",
            compare_series=["FORWARD_1M", "NDF_1M"],
            value_column="close_px",
            threshold_pct=basis_threshold,
        ),
    ]

    for check in checks:
        try:
            result = check.run(reader, TABLE, where=year_filter, params=params)
            _print_quality_result(result)
        except Exception as exc:
            print(f"\n  [!!] {type(check).__name__}: ERROR — {exc}")

    print()


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
        default=4.0,
        help="Statistical outlier z-score threshold (default: 4.0)",
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
    reader = AnalyticalReader(connector)

    # Determine years
    if args.year:
        years = [args.year]
    else:
        with connector.read_engine.connect() as c:
            df = pd.read_sql(
                text("SELECT DISTINCT YEAR(ts) AS yr FROM [fx].[fact_ohlc] ORDER BY yr"),
                c,
            )
            years = df["yr"].tolist()

    print(f"\nFX OHLC Diagnostic Report")
    print(f"Years: {years}")
    print(f"{'=' * 70}\n")

    run_all = args.section is None

    if run_all or args.section == "health":
        run_health_section(connector, years)

    if run_all or args.section == "missing":
        run_missing_section(reader, years)

    if run_all or args.section == "quality":
        run_quality_section(reader, years, args.sigma, args.basis_threshold)

    connector.dispose()
    print("Diagnostic report complete.")


if __name__ == "__main__":
    main()
