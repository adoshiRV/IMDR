"""CLI script for cleaning rates observation data.

Detects and corrects data quality issues in [rates].[fact_observation].
Dry-run by default — pass --execute to apply changes.

Usage:
    python -m scripts.rates.clean.clean_rates_fact_observation
    python -m scripts.rates.clean.clean_rates_fact_observation --execute
    python -m scripts.rates.clean.clean_rates_fact_observation --year 2026
    python -m scripts.rates.clean.clean_rates_fact_observation --rule robust_outlier
    python -m scripts.rates.clean.clean_rates_fact_observation --n-mad 4.0
    python -m scripts.rates.clean.clean_rates_fact_observation --curve 1 --quote par
    python -m scripts.rates.clean.clean_rates_fact_observation --section health
    python -m scripts.rates.clean.clean_rates_fact_observation --section coverage
    python -m scripts.rates.clean.clean_rates_fact_observation --section quality
    python -m scripts.rates.clean.clean_rates_fact_observation --section all
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone

import pandas as pd

from imdr.config.settings import get_settings
from imdr.connectors.mssql import MSSQLConnector
from imdr.connectors.reader import AnalyticalReader
from imdr.domains.rates.clean_rates_fact_observation import (
    HardBoundViolationRule,
    PercentageChangeRule,
    RobustOutlierRule,
)
from imdr.domains.rates.coverage import get_rates_coverage
from imdr.healthchecks.checks import (
    DuplicateCheck,
    FreshnessCheck,
    NullCheck,
    RowCountCheck,
)
from imdr.healthchecks.clean_cli import (
    add_common_clean_args,
    compute_overlap_stats,
    print_clean_summary,
)
from imdr.healthchecks.cleaning import CleaningRunner
from imdr.healthchecks.quality import DistributionCheck
from imdr.healthchecks.reporter import HealthReporter
from imdr.models.rates import RatesObservation
from imdr.universe.rates import get_rates_universe

PIPELINE_NAME = "rates.historical"
TABLE = "[rates].[fact_observation]"
RULE_NAMES = ["hard_bound", "robust_outlier", "pct_change"]


def build_cleaning_rules(
    n_mad: float | None = None,
    trailing_months: int | None = None,
    pct_threshold: float | None = None,
    min_obs: int | None = None,
    rule: str | None = None,
) -> list:
    """Build the ordered list of rates cleaning rules.

    Defaults read from ``pipelines.yml`` (rates.historical.cleaning).
    CLI ``--n-mad`` / ``--trailing-months`` / ``--pct-threshold`` / ``--min-obs`` override when provided.
    """
    from imdr.config.pipeline_config import get_pipeline_config

    cfg = get_pipeline_config(PIPELINE_NAME).cleaning
    n_mad = n_mad if n_mad is not None else cfg.n_mad
    trailing_months = trailing_months if trailing_months is not None else cfg.trailing_months
    pct_threshold = pct_threshold if pct_threshold is not None else cfg.pct_threshold
    min_obs = min_obs if min_obs is not None else cfg.min_obs

    universe = get_rates_universe()
    ranges = {
        quote: (er.min, er.max)
        for quote, er in universe.expected_ranges.items()
    }

    all_rules = [
        HardBoundViolationRule(ranges=ranges),
        RobustOutlierRule(n_mad=n_mad, trailing_months=trailing_months, min_obs=min_obs),
        PercentageChangeRule(threshold_pct=pct_threshold),
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
    if args.curve:
        parts.append(f"AND [curve_id] = {args.curve}")
    if args.quote:
        parts.append(f"AND [quote] = '{args.quote.lower()}'")
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Health checks (per-year, via HealthReporter)
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
# Quality checks
# ---------------------------------------------------------------------------

def build_quality_checks() -> list:
    """Compose rates-specific quality check list (distribution only)."""
    return [
        DistributionCheck(
            value_column="value",
            group_column="quote",
        ),
    ]


# ---------------------------------------------------------------------------
# Coverage analysis
# ---------------------------------------------------------------------------

def run_coverage_section(reader: AnalyticalReader, years: list[int]) -> None:
    """Analyse coverage: per-curve dates, tenor completeness, quote distribution."""
    print("=" * 70)
    print("  COVERAGE ANALYSIS")
    print("=" * 70)

    coverage = get_rates_coverage(reader, TABLE, years)

    print("\n  A) Per-curve date coverage:")
    df_cov = coverage.tables.get("per_curve", pd.DataFrame())
    if not df_cov.empty:
        print(df_cov.to_string(index=False))
    else:
        print("    No data found.")

    print("\n  B) Tenor count per curve x quote (latest date):")
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
# Helpers: freshness + distribution printers
# ---------------------------------------------------------------------------

def _print_freshness(reader: AnalyticalReader) -> None:
    """Query MAX(created_at) from fact_observation and print staleness."""
    df = reader.read_sql(f"SELECT MAX([created_at]) AS max_ts FROM {TABLE}")
    max_ts = df["max_ts"].iloc[0]
    if pd.isna(max_ts):
        print("  Freshness: no data in table.\n")
        return
    max_ts = pd.to_datetime(max_ts, utc=True)
    delta = datetime.now(timezone.utc) - max_ts
    hours = delta.total_seconds() / 3600
    print(f"  Freshness: last record created {hours:.1f}h ago ({max_ts})\n")


def _print_distribution(reader: AnalyticalReader) -> None:
    """Run DistributionCheck and print summary."""
    check = DistributionCheck(value_column="value", group_column="quote")
    result = check.run(reader, TABLE)
    if result.summary is not None and not result.summary.empty:
        print(f"\n  Distribution summary:")
        print(result.summary.to_string(index=False))
    else:
        print("  Distribution: no data.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Clean rates observation data quality issues.",
    )
    add_common_clean_args(parser)
    parser.add_argument(
        "--curve",
        type=int,
        help="Filter to a specific curve_id",
    )
    parser.add_argument(
        "--quote",
        type=str,
        help="Filter to a specific quote type (par, spread, fwd, bfly, ssw, rc)",
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
        help="Section to run (default: clean)",
    )
    args = parser.parse_args()

    settings = get_settings()
    connector = MSSQLConnector(settings)
    reader = AnalyticalReader(connector)

    section = args.section
    run_all = section == "all"

    # Determine years for health/coverage/quality sections
    if run_all or section in ("health", "coverage", "quality"):
        reporter = HealthReporter(connector, PIPELINE_NAME)
        if args.year:
            years = [args.year]
        else:
            years = reporter.discover_years()

    # -- CLEAN section --
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

    # -- HEALTH section --
    if run_all or section == "health":
        health_checks = build_health_checks()
        reporter.run_health_section(health_checks, years)

    # -- COVERAGE section --
    if run_all or section == "coverage":
        run_coverage_section(reporter.reader, years)

    # -- QUALITY section --
    if run_all or section == "quality":
        quality_checks = build_quality_checks()
        reporter.run_quality_section(quality_checks, years)

    connector.dispose()


if __name__ == "__main__":
    main()
