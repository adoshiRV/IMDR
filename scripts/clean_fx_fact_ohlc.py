"""CLI script for cleaning FX OHLC data.

Detects and corrects data quality issues in [fx].[fact_ohlc].
Dry-run by default — pass --execute to apply changes.

Usage:
    python -m scripts.clean_fx_fact_ohlc
    python -m scripts.clean_fx_fact_ohlc --execute
    python -m scripts.clean_fx_fact_ohlc --year 2024
    python -m scripts.clean_fx_fact_ohlc --symbol USDTWD
    python -m scripts.clean_fx_fact_ohlc --rule bid_ask
    python -m scripts.clean_fx_fact_ohlc --n-mad 4.0 --trailing-months 12
    python -m scripts.clean_fx_fact_ohlc --emit-gaps data/gaps/cleaning_gaps.txt
"""

from __future__ import annotations

import argparse
from pathlib import Path

from imdr.config.settings import get_settings
from imdr.connectors.mssql import MSSQLConnector
from imdr.connectors.reader import AnalyticalReader
from imdr.domains.fx.clean_fx_fact_ohlc import (
    BidAskInversionRule,
    CleaningResult,
    CleaningRunner,
    HardBoundViolationRule,
    NonPositivePriceRule,
    PercentageChangeRule,
    RobustOutlierRule,
)
from imdr.universe.fx import get_fx_universe

RULE_NAMES = ["non_positive", "hard_bound", "pct_change", "robust_outlier", "bid_ask"]


def _build_rules(
    args: argparse.Namespace,
) -> list:
    """Build the ordered list of cleaning rules."""
    universe = get_fx_universe()
    ranges = {
        sym: (r.min, r.max)
        for sym in universe.api_symbols()
        if (r := universe.expected_range_for(sym)) is not None
    }

    all_rules = [
        NonPositivePriceRule(),
        HardBoundViolationRule(ranges=ranges),
        PercentageChangeRule(threshold_pct=args.pct_threshold),
        RobustOutlierRule(
            n_mad=args.n_mad,
            trailing_months=args.trailing_months,
        ),
        BidAskInversionRule(),
    ]

    if args.rule:
        return [r for r in all_rules if r.name == args.rule]
    return all_rules


def _build_where(args: argparse.Namespace) -> str:
    """Build WHERE clause fragment from CLI filters."""
    parts: list[str] = []
    if args.year:
        parts.append(f"AND YEAR([ts]) = {args.year}")
    if args.symbol:
        parts.append(f"AND [symbol] = '{args.symbol.upper()}'")
    return " ".join(parts)


def _overlap_stats(
    results: list[CleaningResult],
) -> tuple[dict[str, set[int]], dict[str, int], int]:
    """Compute per-rule ID sets, unique-only counts, and global unique count.

    Returns (id_sets, unique_counts, total_unique) considering only
    null_prices rules (bid_ask is a separate action and excluded).
    """
    null_rules = [r for r in results if r.actions and r.actions[0].action == "null_prices"]
    id_sets: dict[str, set[int]] = {
        r.rule_name: {a.row_id for a in r.actions} for r in null_rules
    }
    all_ids = set().union(*id_sets.values()) if id_sets else set()

    unique_counts: dict[str, int] = {}
    for name, ids in id_sets.items():
        others = set().union(*(s for n, s in id_sets.items() if n != name)) if len(id_sets) > 1 else set()
        unique_counts[name] = len(ids - others)

    return id_sets, unique_counts, len(all_ids)


def _print_summary(results: list[CleaningResult], dry_run: bool) -> None:
    mode = "DRY RUN" if dry_run else "EXECUTED"
    total = sum(r.count for r in results)

    id_sets, unique_counts, total_unique = _overlap_stats(results)

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
        print(f"  {'UNIQUE (null_prices)':<20} {total_unique:>8}  ({overlap} overlapping)")
    print(f"{'=' * 60}\n")

    if dry_run and total > 0:
        print("  Re-run with --execute to apply these corrections.\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Clean FX OHLC data quality issues.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Apply corrections (default is dry-run)",
    )
    parser.add_argument("--year", type=int, help="Filter to a specific year")
    parser.add_argument("--symbol", type=str, help="Filter to a specific symbol")
    parser.add_argument(
        "--rule",
        choices=RULE_NAMES,
        help="Run a single rule instead of all",
    )
    parser.add_argument(
        "--pct-threshold",
        type=float,
        default=5.0,
        help="Percentage change threshold for bar-to-bar detection (default: 5.0)",
    )
    parser.add_argument(
        "--n-mad",
        type=float,
        default=4.0,
        help="MAD threshold for robust outlier detection (default: 4.0)",
    )
    parser.add_argument(
        "--trailing-months",
        type=int,
        default=1,
        help="Trailing window in months for robust stats (default: 1)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="Batch size for UPDATE statements (default: 500)",
    )
    parser.add_argument(
        "--emit-gaps",
        type=str,
        metavar="PATH",
        help="Write flagged timestamps to a gaps file for re-pull via fx_bidfx_historical",
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
        dry_run=dry_run,
        batch_size=args.batch_size,
    )

    results = runner.run(where=where)

    # Compute overlap sets for per-rule annotation
    id_sets, unique_counts, total_unique = _overlap_stats(results)

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

    _print_summary(results, dry_run)

    if args.emit_gaps:
        _write_gaps_file(results, args.emit_gaps)

    connector.dispose()


def _write_gaps_file(results: list[CleaningResult], path: str) -> None:
    """Write unique (symbol, timestamp) pairs for null_prices rows as a gaps file for re-pull."""
    pairs: set[tuple[str, str]] = set()
    for r in results:
        if not r.actions or r.actions[0].action != "null_prices":
            continue
        for a in r.actions:
            ts_str = a.ts.strftime("%Y-%m-%dT%H:%M:%S") if hasattr(a.ts, "strftime") else str(a.ts)
            pairs.add((a.symbol, ts_str))

    if not pairs:
        print("  No flagged rows — gaps file not written.")
        return

    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = sorted(pairs)
    out.write_text("\n".join(f"{sym},{ts}" for sym, ts in lines) + "\n")
    print(f"  Wrote {len(lines)} unique (symbol, timestamp) pairs to {out}")
    print(f"  → Set MODE='cleanup' and GAPS_FILE='{out}' in fx_bidfx_historical.py to re-pull.")


if __name__ == "__main__":
    main()
