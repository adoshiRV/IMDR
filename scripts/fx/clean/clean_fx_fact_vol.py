"""CLI script for cleaning FX vol data.

Detects and corrects data quality issues in [fx].[fact_vol].
Dry-run by default — pass --execute to apply changes.

Usage:
    python -m scripts.fx.clean.clean_fx_fact_vol
    python -m scripts.fx.clean.clean_fx_fact_vol --execute
    python -m scripts.fx.clean.clean_fx_fact_vol --year 2026
    python -m scripts.fx.clean.clean_fx_fact_vol --rule robust_outlier
    python -m scripts.fx.clean.clean_fx_fact_vol --n-mad 4.0 --trailing-months 12
    python -m scripts.fx.clean.clean_fx_fact_vol --section health
    python -m scripts.fx.clean.clean_fx_fact_vol --section coverage
    python -m scripts.fx.clean.clean_fx_fact_vol --section quality
    python -m scripts.fx.clean.clean_fx_fact_vol --section all
"""

from __future__ import annotations

import argparse

import pandas as pd

from imdr.config.settings import get_settings
from imdr.connectors.mssql import MSSQLConnector
from imdr.connectors.reader import AnalyticalReader
from imdr.domains.fx.clean_fx_fact_vol import (
    HardBoundViolationRule,
    PercentageChangeRule,
    RobustOutlierRule,
)
from imdr.domains.fx.coverage import get_vol_coverage
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
from imdr.healthchecks.cleaning import CleaningRunner
from imdr.healthchecks.quality import DistributionCheck
from imdr.healthchecks.reporter import HealthReporter
from imdr.models.fx_vol import FXFactVol
from imdr.universe.fx import get_fx_universe

PIPELINE_NAME = "fx.vol"
TABLE = "[fx].[fact_vol]"
RULE_NAMES = ["hard_bound", "robust_outlier", "pct_change"]


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
    """Build the ordered list of FX Vol cleaning rules.

    Defaults read from ``pipelines.yml`` (fx.vol.cleaning).
    CLI ``--n-mad`` / ``--trailing-months`` / ``--pct-threshold`` / ``--min-obs`` override when provided.
    """
    from imdr.config.pipeline_config import get_pipeline_config

    cfg = get_pipeline_config(PIPELINE_NAME).cleaning
    n_mad = n_mad if n_mad is not None else cfg.n_mad
    trailing_months = trailing_months if trailing_months is not None else cfg.trailing_months
    threshold = pct_threshold if pct_threshold is not None else cfg.pct_threshold
    min_obs = min_obs if min_obs is not None else cfg.min_obs

    universe = get_fx_universe()
    vq = universe.vol_quality_config()

    all_rules = [
        HardBoundViolationRule(ranges=vq.ranges),
        RobustOutlierRule(n_mad=n_mad, trailing_months=trailing_months, min_obs=min_obs),
        PercentageChangeRule(
            threshold_pct=threshold,
            abs_change_strikes=vq.abs_change_thresholds,
            pct_thresholds=vq.pct_thresholds,
            abs_change_vol_types=vq.abs_change_vol_types,
        ),
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
        parts.append(f"AND YEAR([obs_date]) = {args.year}")
    if hasattr(args, "pair") and args.pair:
        parts.append(f"AND [pair_id] = {args.pair}")
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Health checks (per-year, via HealthReporter)
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
# Quality checks (diagnostic only)
# ---------------------------------------------------------------------------

def build_quality_checks() -> list:
    """Build quality checks — distribution by strike only."""
    return [
        DistributionCheck(
            value_column="value",
            group_column="strike",
        ),
    ]


# ---------------------------------------------------------------------------
# Coverage section
# ---------------------------------------------------------------------------

def run_coverage_section(reader: AnalyticalReader, years: list[int]) -> None:
    """Analyse coverage: per-pair dates, strike x tenor grid, row counts."""
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

    print("\n  B) Strike x tenor grid completeness (latest obs_date, per pair):")
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
        value_column="value",
        group_column="strike",
    )
    result = check.run(reader, table)
    if result.summary is not None and not result.summary.empty:
        print(f"\n  Distribution summary:")
        print(result.summary.to_string(index=False))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Clean FX vol data quality issues.",
    )
    add_common_clean_args(parser)
    parser.add_argument(
        "--pair",
        type=int,
        help="Filter to a specific pair_id",
    )
    parser.add_argument(
        "--rule",
        choices=RULE_NAMES,
        help="Run a single rule instead of all",
    )
    parser.add_argument(
        "--section",
        choices=["clean", "health", "coverage", "quality", "all"],
        default="clean",
        help="Which section to run (default: clean)",
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
        id_sets, unique_counts, total_unique = compute_overlap_stats(
            results, null_action="null_value",
        )

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

        print_clean_summary(results, dry_run, null_action="null_value")

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

        quality_checks = build_quality_checks()
        reporter.run_quality_section(quality_checks, years)

    connector.dispose()


if __name__ == "__main__":
    main()
