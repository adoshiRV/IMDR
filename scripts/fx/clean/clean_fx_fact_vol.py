"""CLI script for cleaning FX vol data.

Detects and corrects data quality issues in [fx].[fact_vol].
Dry-run by default — pass --execute to apply changes.

Usage:
    python -m scripts.fx.clean.clean_fx_fact_vol
    python -m scripts.fx.clean.clean_fx_fact_vol --execute
    python -m scripts.fx.clean.clean_fx_fact_vol --year 2026
    python -m scripts.fx.clean.clean_fx_fact_vol --rule robust_outlier
    python -m scripts.fx.clean.clean_fx_fact_vol --n-mad 4.0 --trailing-months 12
"""

from __future__ import annotations

import argparse

from imdr.config.settings import get_settings
from imdr.connectors.mssql import MSSQLConnector
from imdr.connectors.reader import AnalyticalReader
from imdr.domains.fx.clean_fx_fact_vol import (
    HardBoundViolationRule,
    PercentageChangeRule,
    RobustOutlierRule,
)
from imdr.healthchecks.clean_cli import (
    add_common_clean_args,
    compute_overlap_stats,
    print_clean_summary,
)
from imdr.healthchecks.cleaning import CleaningRunner
from imdr.universe.fx import get_fx_universe

PIPELINE_NAME = "fx.vol"
TABLE = "[fx].[fact_vol]"
RULE_NAMES = ["hard_bound", "robust_outlier", "pct_change"]


def build_cleaning_rules(
    n_mad: float | None = None,
    trailing_months: int | None = None,
    pct_threshold: float | None = None,
    rule: str | None = None,
) -> list:
    """Build the ordered list of FX Vol cleaning rules.

    Defaults read from ``pipelines.yml`` (fx.vol.cleaning).
    CLI ``--n-mad`` / ``--trailing-months`` / ``--pct-threshold`` override when provided.
    """
    from imdr.config.pipeline_config import get_pipeline_config

    cfg = get_pipeline_config(PIPELINE_NAME).cleaning
    n_mad = n_mad if n_mad is not None else cfg.n_mad
    trailing_months = trailing_months if trailing_months is not None else cfg.trailing_months
    threshold = pct_threshold if pct_threshold is not None else cfg.pct_threshold

    universe = get_fx_universe()
    vq = universe.vol_quality_config()

    all_rules = [
        HardBoundViolationRule(ranges=vq.ranges),
        RobustOutlierRule(n_mad=n_mad, trailing_months=trailing_months),
        PercentageChangeRule(threshold_pct=threshold),
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
    args = parser.parse_args()

    settings = get_settings()
    connector = MSSQLConnector(settings)
    reader = AnalyticalReader(connector)

    rules = _build_rules(args)
    where = _build_where(args)
    dry_run = not args.execute

    if dry_run:
        print("\n  [DRY RUN] — no changes will be written.\n")
    else:
        print("\n  [EXECUTE] — corrections will be applied.\n")

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

    connector.dispose()


if __name__ == "__main__":
    main()
