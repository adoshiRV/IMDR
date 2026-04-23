"""CLI script for cleaning FX rate data in [fx].[fact_fx_rate].

Dry-run by default — pass --execute to apply changes (only HardBoundViolation
actually writes; robust_outlier and pct_change are flag-only).

Usage:
    python -m scripts.fx.clean.clean_fx_fact_fx_rate
    python -m scripts.fx.clean.clean_fx_fact_fx_rate --execute
    python -m scripts.fx.clean.clean_fx_fact_fx_rate --section all
    python -m scripts.fx.clean.clean_fx_fact_fx_rate --section health
    python -m scripts.fx.clean.clean_fx_fact_fx_rate --section coverage
    python -m scripts.fx.clean.clean_fx_fact_fx_rate --section quality
"""
from __future__ import annotations

import argparse

import pandas as pd

from imdr.config.pipeline_config import get_pipeline_config
from imdr.config.settings import get_settings
from imdr.connectors.mssql import MSSQLConnector
from imdr.connectors.reader import AnalyticalReader
from imdr.domains.fx.clean_fx_fact_fx_rate import (
    HardBoundViolationRule,
    PercentageChangeRule,
    RobustOutlierRule,
)
from imdr.domains.fx.coverage import get_fx_rate_coverage
from imdr.healthchecks.checks import (
    DuplicateCheck,
    FreshnessCheck,
    NullCheck,
    RowCountCheck,
    ValueRangeCheck,
)
from imdr.healthchecks.clean_cli import add_common_clean_args
from imdr.healthchecks.cleaning import CleaningRunner
from imdr.healthchecks.quality import (
    PercentageChangeCheck,
    PositiveValueCheck,
    RobustStatisticalOutlierCheck,
)
from imdr.models.fx_rate import FXFactFXRate
from imdr.universe.fx import get_fx_universe

PIPELINE_NAME = "fx.citi_rate"
TABLE = "[fx].[fact_fx_rate]"
RULE_NAMES = ["hard_bound", "robust_outlier", "pct_change"]


# ---------------------------------------------------------------------------
# Required builders (dashboard imports these by name)
# ---------------------------------------------------------------------------

def build_cleaning_rules(
    n_mad: float | None = None,
    trailing_months: int | None = None,
    pct_threshold: float | None = None,
    min_obs: int | None = None,
    rule: str | None = None,
) -> list:
    cfg = get_pipeline_config(PIPELINE_NAME).cleaning
    n_mad = n_mad if n_mad is not None else cfg.n_mad
    trailing_months = trailing_months if trailing_months is not None else cfg.trailing_months
    threshold = pct_threshold if pct_threshold is not None else cfg.pct_threshold
    min_obs = min_obs if min_obs is not None else cfg.min_obs

    universe = get_fx_universe()
    ranges_er = universe.fx_rate_expected_ranges()  # pair_code -> ExpectedRange
    ranges: dict[str, tuple[float, float]] = {
        code: (float(er.min), float(er.max)) for code, er in ranges_er.items()
    }

    all_rules = [
        HardBoundViolationRule(ranges=ranges),
        RobustOutlierRule(n_mad=n_mad, trailing_months=trailing_months, min_obs=min_obs),
        PercentageChangeRule(threshold_pct=threshold),
    ]
    if rule:
        return [r for r in all_rules if r.name == rule]
    return all_rules


def build_health_checks(freshness_hours: int | None = None) -> list:
    cfg = get_pipeline_config(PIPELINE_NAME)
    if freshness_hours is None:
        freshness_hours = cfg.health_checks.max_staleness_hours

    return [
        RowCountCheck(FXFactFXRate, "obs_date", expected_min=cfg.health_checks.row_count_min),
        NullCheck(FXFactFXRate, ["mid_rate"], "obs_date"),
        DuplicateCheck(
            FXFactFXRate,
            ["pair_id", "vendor_id", "frequency_id", "obs_date", "tenor"],
            "obs_date",
        ),
        FreshnessCheck(FXFactFXRate, "created_at", max_staleness_hours=freshness_hours),
        ValueRangeCheck(FXFactFXRate, "mid_rate", 0.00001, 100000.0, "obs_date"),
    ]


def build_quality_checks() -> list:
    cfg = get_pipeline_config(PIPELINE_NAME).cleaning
    return [
        PositiveValueCheck(columns=["mid_rate"], symbol_column="pair_id"),
        PercentageChangeCheck(
            value_column="mid_rate",
            group_columns=["pair_id", "tenor"],
            ts_column="obs_date",
            threshold_pct=cfg.pct_threshold,
            min_abs_value=1e-6,
        ),
        RobustStatisticalOutlierCheck(
            value_column="mid_rate",
            group_columns=["pair_id", "tenor"],
            n_mad=cfg.n_mad,
            trailing_months=cfg.trailing_months,
            ts_column="obs_date",
            min_obs=cfg.min_obs,
        ),
    ]


# ---------------------------------------------------------------------------
# Section runners
# ---------------------------------------------------------------------------

def _build_where(args: argparse.Namespace) -> str:
    parts: list[str] = []
    if args.year:
        parts.append(f"AND YEAR([obs_date]) = {args.year}")
    if getattr(args, "pair", None):
        parts.append(f"AND [pair_id] = {args.pair}")
    return " ".join(parts)


def run_coverage_section(reader: AnalyticalReader, years: list[int]) -> None:
    print("=" * 70)
    print("  SECTION: COVERAGE ANALYSIS")
    print("=" * 70)
    coverage = get_fx_rate_coverage(reader, TABLE, years)

    print("\n  Per-pair date coverage:")
    df_cov = coverage.tables.get("per_pair", pd.DataFrame())
    print(df_cov.to_string(index=False) if not df_cov.empty else "    No data.")

    print("\n  Tenor grid (latest date):")
    df_grid = coverage.tables.get("grid", pd.DataFrame())
    print(df_grid.to_string(index=False) if not df_grid.empty else "    No data.")

    print("\n  Row counts by pair:")
    df_counts = coverage.tables.get("row_counts", pd.DataFrame())
    if not df_counts.empty:
        print(df_counts.to_string(index=False))
        s = coverage.summary
        print(f"\n    Grand total: {s['grand_total_rows']:,} rows across {s['num_pairs']} pairs")
    else:
        print("    No data.")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Clean FX rate data quality issues.")
    add_common_clean_args(parser)
    parser.add_argument("--pair", type=int, help="Filter to a specific pair_id")
    parser.add_argument("--rule", choices=RULE_NAMES, help="Run a single rule instead of all")
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
        rules = build_cleaning_rules(
            n_mad=args.n_mad,
            trailing_months=args.trailing_months,
            pct_threshold=args.pct_threshold,
            min_obs=getattr(args, "min_obs", None),
            rule=getattr(args, "rule", None),
        )
        where = _build_where(args)
        dry_run = not args.execute
        print(f"\n  [{'DRY RUN' if dry_run else 'EXECUTE'}] cleaning {TABLE}\n")
        runner = CleaningRunner(
            connector=connector, reader=reader,
            rules=rules, table=TABLE, dry_run=dry_run,
        )
        results = runner.run(where=where)
        for r in results:
            print(f"  [{r.rule_name}] flagged={len(r.actions)} applied={r.rows_affected}")

    # --- Health section ---
    if run_all or section == "health":
        print("\n" + "=" * 70)
        print("  SECTION: HEALTH CHECKS")
        print("=" * 70)
        for c in build_health_checks():
            try:
                res = c.run(reader, TABLE)
                print(f"  [{res.check_name}] {res.status.value}: {res.message}")
            except Exception as e:
                print(f"  [{type(c).__name__}] ERROR: {e}")

    # --- Coverage section ---
    if run_all or section == "coverage":
        years = [args.year] if args.year else []
        run_coverage_section(reader, years)

    # --- Quality section ---
    if run_all or section == "quality":
        print("\n" + "=" * 70)
        print("  SECTION: QUALITY CHECKS")
        print("=" * 70)
        for c in build_quality_checks():
            try:
                res = c.run(reader, TABLE)
                print(f"  [{res.check_name}] {res.status.value}: {res.message}")
            except Exception as e:
                print(f"  [{type(c).__name__}] ERROR: {e}")


if __name__ == "__main__":
    main()
