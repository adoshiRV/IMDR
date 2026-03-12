"""CLI script for cleaning FX OHLC data.

Detects and corrects data quality issues in [fx].[fact_ohlc].
Dry-run by default — pass --execute to apply changes.

Usage:
    python -m scripts.fx.clean.clean_fx_fact_ohlc
    python -m scripts.fx.clean.clean_fx_fact_ohlc --execute
    python -m scripts.fx.clean.clean_fx_fact_ohlc --year 2024
    python -m scripts.fx.clean.clean_fx_fact_ohlc --symbol USDTWD
    python -m scripts.fx.clean.clean_fx_fact_ohlc --rule bid_ask
    python -m scripts.fx.clean.clean_fx_fact_ohlc --n-mad 4.0 --trailing-months 12
    python -m scripts.fx.clean.clean_fx_fact_ohlc --emit-gaps data/gaps/cleaning_gaps.txt
    python -m scripts.fx.clean.clean_fx_fact_ohlc --section health
    python -m scripts.fx.clean.clean_fx_fact_ohlc --section coverage
    python -m scripts.fx.clean.clean_fx_fact_ohlc --section quality --basis-threshold 3
    python -m scripts.fx.clean.clean_fx_fact_ohlc --section all
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from imdr.config.settings import get_settings
from imdr.connectors.mssql import MSSQLConnector
from imdr.connectors.reader import AnalyticalReader
from imdr.domains.fx.clean_fx_fact_ohlc import (
    BidAskInversionRule,
    HardBoundViolationRule,
    NonPositivePriceRule,
    OHLCOrderRule,
    PercentageChangeRule,
    RobustOutlierRule,
)
from imdr.domains.fx.coverage import get_ohlc_coverage
from imdr.healthchecks.checks import (
    DuplicateCheck,
    FreshnessCheck,
    NullCheck,
    RowCountCheck,
    ValueRangeCheck,
)
from imdr.healthchecks.clean_cli import (
    add_common_clean_args,
    compute_overlap_stats,
    print_clean_summary,
)
from imdr.healthchecks.cleaning import CleaningResult, CleaningRunner
from imdr.healthchecks.quality import (
    DistributionCheck,
    ReturnDistributionCheck,
    SeriesBasisCheck,
)
from imdr.healthchecks.reporter import HealthReporter
from imdr.models.fx_ohlc import FXFactOHLC
from imdr.universe.fx import get_fx_universe

PIPELINE_NAME = "fx.ohlc"
TABLE = "[fx].[fact_ohlc]"
RULE_NAMES = ["non_positive", "ohlc_order", "hard_bound", "pct_change", "robust_outlier", "bid_ask"]
PRICE_COLUMNS = [
    "open_px", "high_px", "low_px", "close_px",
    "mid_px", "mid_mean_px", "mid_median_px", "bid", "ask",
]


# ---------------------------------------------------------------------------
# Cleaning rules (existing)
# ---------------------------------------------------------------------------

def build_cleaning_rules(
    n_mad: float | None = None,
    trailing_months: int | None = None,
    pct_threshold: float | None = None,
    min_obs: int | None = None,
    rule: str | None = None,
) -> list:
    """Build the ordered list of FX OHLC cleaning rules.

    Defaults read from ``pipelines.yml`` (fx.ohlc.cleaning).
    CLI ``--n-mad`` / ``--trailing-months`` / ``--pct-threshold`` / ``--min-obs`` override when provided.
    """
    from imdr.config.pipeline_config import get_pipeline_config

    cfg = get_pipeline_config(PIPELINE_NAME).cleaning
    n_mad = n_mad if n_mad is not None else cfg.n_mad
    trailing_months = trailing_months if trailing_months is not None else cfg.trailing_months
    pct_threshold = pct_threshold if pct_threshold is not None else cfg.pct_threshold
    min_obs = min_obs if min_obs is not None else cfg.min_obs

    universe = get_fx_universe()
    ranges = {
        sym: (r.min, r.max)
        for sym in universe.api_symbols()
        if (r := universe.expected_range_for(sym)) is not None
    }

    all_rules = [
        NonPositivePriceRule(),
        OHLCOrderRule(),
        HardBoundViolationRule(ranges=ranges),
        PercentageChangeRule(threshold_pct=pct_threshold),
        RobustOutlierRule(n_mad=n_mad, trailing_months=trailing_months, min_obs=min_obs),
        BidAskInversionRule(),
    ]

    if rule:
        return [r for r in all_rules if r.name == rule]
    return all_rules


def _build_rules(args: argparse.Namespace) -> list:
    """CLI wrapper — forwards argparse values to build_cleaning_rules."""
    return build_cleaning_rules(
        n_mad=args.n_mad,
        trailing_months=args.trailing_months,
        pct_threshold=args.pct_threshold,
        min_obs=getattr(args, "min_obs", None),
        rule=getattr(args, "rule", None),
    )


def _build_where(args: argparse.Namespace) -> str:
    """Build WHERE clause fragment from CLI filters."""
    parts: list[str] = []
    if args.year:
        parts.append(f"AND YEAR([ts]) = {args.year}")
    if args.symbol:
        parts.append(f"AND [symbol] = '{args.symbol.upper()}'")
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Health checks (per-year, via HealthReporter)
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
# Quality checks (diagnostic only — not covered by cleaning)
# ---------------------------------------------------------------------------

def build_quality_checks(basis_threshold: float = 5.0) -> list:
    """Build quality checks that are diagnostic-only (not covered by cleaning rules)."""
    return [
        SeriesBasisCheck(
            base_series="SPOT",
            compare_series=["FORWARD_1M", "NDF_1M"],
            value_column="close_px",
            threshold_pct=basis_threshold,
        ),
        ReturnDistributionCheck(
            value_column="close_px", group_column="symbol",
            ts_column="ts", series_filter="SPOT",
        ),
        DistributionCheck(
            value_column="close_px", group_column="symbol",
            series_filter="SPOT",
        ),
    ]


# ---------------------------------------------------------------------------
# Coverage section
# ---------------------------------------------------------------------------

def run_coverage_section(reader: AnalyticalReader, years: list[int]) -> None:
    """Analyse coverage gaps per symbol, excluding FX market close hours."""
    print("=" * 70)
    print("  COVERAGE ANALYSIS (market-hours aware)")
    print("=" * 70)

    coverage = get_ohlc_coverage(reader, TABLE, years)
    df_cov = coverage.tables.get("per_symbol", pd.DataFrame())
    df_gaps = coverage.tables.get("gaps", pd.DataFrame())

    # Per-symbol coverage
    print("\n  A) Per-symbol coverage (actual vs expected market hours):")
    if not df_cov.empty:
        display_cols = ["symbol", "class", "actual_hours", "expected_hours",
                        "missing_hours", "coverage_pct"]
        print(df_cov[display_cols].to_string(index=False))
    else:
        print("    No data found.")

    # Largest gaps (market hours only)
    print("\n  B) Largest gaps (market hours, excluding weekends, top 20):")
    if not df_gaps.empty:
        display_cols = ["symbol", "series", "gap_start", "gap_end",
                        "calendar_gap_hours", "market_gap_hours"]
        print(df_gaps[display_cols].to_string(index=False))
    else:
        print("    No significant market-hour gaps detected.")

    # Summary
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
# Helpers for clean section
# ---------------------------------------------------------------------------

def _print_freshness(reader: AnalyticalReader, table: str = TABLE) -> None:
    """Query MAX(created_at) and print staleness."""
    from datetime import datetime, timezone

    df = reader.read_sql(f"SELECT MAX([created_at]) AS latest FROM {table}")
    if df.empty or pd.isna(df.iloc[0]["latest"]):
        print("  Freshness: no data")
        return
    latest = pd.to_datetime(df.iloc[0]["latest"], utc=True)
    age = datetime.now(timezone.utc) - latest
    hours = age.total_seconds() / 3600
    print(f"  Freshness: latest record {latest:%Y-%m-%d %H:%M} UTC ({hours:.1f}h ago)")


def _print_distribution(reader: AnalyticalReader, table: str = TABLE) -> None:
    """Run DistributionCheck and print summary."""
    check = DistributionCheck(
        value_column="close_px", group_column="symbol", series_filter="SPOT",
    )
    result = check.run(reader, table)
    if result.summary is not None and not result.summary.empty:
        print(f"\n  Distribution summary:")
        print(result.summary.to_string(index=False))


def _write_gaps_file(results: list[CleaningResult], path: str) -> None:
    """Write unique (symbol, timestamp) pairs for null_prices rows as a gaps file for re-pull."""
    pairs: set[tuple[str, str]] = set()
    for r in results:
        if not r.actions or r.actions[0].action != "null_prices":
            continue
        for a in r.actions:
            ts_str = a.ts.strftime("%Y-%m-%dT%H:%M:%S") if hasattr(a.ts, "strftime") else str(a.ts)
            symbol = a.context.get("symbol", "")
            pairs.add((symbol, ts_str))

    if not pairs:
        print("  No flagged rows — gaps file not written.")
        return

    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = sorted(pairs)
    out.write_text("\n".join(f"{sym},{ts}" for sym, ts in lines) + "\n")
    print(f"  Wrote {len(lines)} unique (symbol, timestamp) pairs to {out}")
    print(f"  → Set MODE='cleanup' and GAPS_FILE='{out}' in fx_bidfx_historical.py to re-pull.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Clean FX OHLC data quality issues.",
    )
    add_common_clean_args(parser)
    parser.add_argument("--symbol", type=str, help="Filter to a specific symbol")
    parser.add_argument(
        "--rule",
        choices=RULE_NAMES,
        help="Run a single rule instead of all",
    )
    parser.add_argument(
        "--emit-gaps",
        type=str,
        metavar="PATH",
        help="Write flagged timestamps to a gaps file for re-pull via fx_bidfx_historical",
    )
    parser.add_argument(
        "--section",
        choices=["clean", "health", "coverage", "quality", "all"],
        default="clean",
        help="Which section to run (default: clean)",
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

    section = args.section
    run_all = section == "all"

    # --- Clean section ---
    if run_all or section == "clean":
        rules = _build_rules(args)
        where = _build_where(args)
        dry_run = not args.execute

        if dry_run:
            print("\n  [DRY RUN] — no changes will be written.\n")
        else:
            print("\n  [EXECUTE] — corrections will be applied.\n")

        _print_freshness(reader)

        runner = CleaningRunner(
            connector=connector,
            reader=reader,
            rules=rules,
            table=TABLE,
            dry_run=dry_run,
            batch_size=args.batch_size,
        )

        results = runner.run(where=where)

        # Compute overlap sets for per-rule annotation
        id_sets, unique_counts, total_unique = compute_overlap_stats(results)

        # Print flagged rows detail
        for r in results:
            if r.count > 0:
                uniq = unique_counts.get(r.rule_name)
                if uniq is not None:
                    overlap = r.count - uniq
                    print(f"\n  {r.rule_name} — {r.count} rows ({uniq} unique, {overlap} overlap):")
                else:
                    print(f"\n  {r.rule_name} — {r.count} rows:")
                for a in r.actions[:20]:
                    print(f"    {a.detail}")
                if r.count > 20:
                    print(f"    ... and {r.count - 20} more")

        print_clean_summary(results, dry_run)

        if args.emit_gaps:
            _write_gaps_file(results, args.emit_gaps)

        _print_distribution(reader)

    # --- Health section ---
    if run_all or section == "health":
        reporter = HealthReporter(connector, PIPELINE_NAME)
        if args.year:
            years = [args.year]
        else:
            years = reporter.discover_years()

        print(f"\n{'=' * 70}")
        print(f"  HEALTH CHECKS")
        print(f"{'=' * 70}")
        print(f"  Years: {years}\n")

        health_checks = build_health_checks()
        reporter.run_health_section(health_checks, years)

    # --- Coverage section ---
    if run_all or section == "coverage":
        if args.year:
            years = [args.year]
        else:
            reporter = HealthReporter(connector, PIPELINE_NAME)
            years = reporter.discover_years()
        run_coverage_section(reader, years)

    # --- Quality section ---
    if run_all or section == "quality":
        reporter = HealthReporter(connector, PIPELINE_NAME)
        if args.year:
            years = [args.year]
        else:
            years = reporter.discover_years()

        print(f"\n{'=' * 70}")
        print(f"  QUALITY CHECKS (diagnostic)")
        print(f"{'=' * 70}")
        print(f"  Years: {years}\n")

        quality_checks = build_quality_checks(args.basis_threshold)
        reporter.run_quality_section(quality_checks, years)

    connector.dispose()


if __name__ == "__main__":
    main()
