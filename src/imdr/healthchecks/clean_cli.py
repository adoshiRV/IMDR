"""Shared CLI helpers for cleaning scripts.

Provides reusable overlap analysis, summary printing, and argument parsing
that all domain-specific clean scripts use.

Usage:
    from imdr.healthchecks.clean_cli import compute_overlap_stats, print_clean_summary, add_common_clean_args
"""

from __future__ import annotations

import argparse

from imdr.healthchecks.cleaning import CleaningResult


def compute_overlap_stats(
    results: list[CleaningResult],
    null_action: str = "null_prices",
) -> tuple[dict[str, set[int]], dict[str, int], int]:
    """Compute per-rule ID sets, unique-only counts, and global unique count.

    Returns (id_sets, unique_counts, total_unique) considering only
    rules with the specified null action (excludes swap/other actions).
    """
    null_rules = [r for r in results if r.actions and r.actions[0].action == null_action]
    id_sets: dict[str, set[int]] = {
        r.rule_name: {a.row_id for a in r.actions} for r in null_rules
    }
    all_ids = set().union(*id_sets.values()) if id_sets else set()

    unique_counts: dict[str, int] = {}
    for name, ids in id_sets.items():
        others = set().union(*(s for n, s in id_sets.items() if n != name)) if len(id_sets) > 1 else set()
        unique_counts[name] = len(ids - others)

    return id_sets, unique_counts, len(all_ids)


def print_clean_summary(
    results: list[CleaningResult],
    dry_run: bool,
    null_action: str = "null_prices",
) -> None:
    """Print a formatted summary table of cleaning results."""
    mode = "DRY RUN" if dry_run else "EXECUTED"
    total = sum(r.count for r in results)

    id_sets, unique_counts, total_unique = compute_overlap_stats(results, null_action)

    print(f"\n{'=' * 60}")
    print(f"  CLEANING SUMMARY  [{mode}]")
    print(f"{'=' * 60}")
    print(f"  {'Rule':<20} {'Rows':>8} {'Unique':>8}  Action")
    print(f"  {'-' * 56}")
    for r in results:
        action = r.actions[0].action if r.actions else "-"
        uniq = unique_counts.get(r.rule_name)
        uniq_str = str(uniq) if uniq is not None else "-"
        print(f"  {r.rule_name:<20} {r.count:>8} {uniq_str:>8}  {action}")
    print(f"  {'-' * 56}")
    print(f"  {'TOTAL':<20} {total:>8}")

    if id_sets:
        null_total = sum(r.count for r in results if r.rule_name in id_sets)
        overlap = null_total - total_unique
        print(f"  {'UNIQUE (' + null_action + ')':<20} {total_unique:>8}  ({overlap} overlapping)")
    print(f"{'=' * 60}\n")

    if dry_run and total > 0:
        print("  Re-run with --execute to apply these corrections.\n")


def add_common_clean_args(parser: argparse.ArgumentParser) -> None:
    """Add shared CLI arguments for cleaning scripts."""
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Apply corrections (default is dry-run)",
    )
    parser.add_argument("--year", type=int, help="Filter to a specific year")
    parser.add_argument(
        "--n-mad",
        type=float,
        default=None,
        help="MAD threshold for robust outlier detection (default: from pipelines.yml)",
    )
    parser.add_argument(
        "--trailing-months",
        type=int,
        default=None,
        help="Trailing window in months for robust stats (default: from pipelines.yml)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="Batch size for UPDATE statements (default: 500)",
    )
    parser.add_argument(
        "--pct-threshold",
        type=float,
        default=None,
        help="Percentage change threshold for bar-to-bar detection (default: from pipelines.yml)",
    )
