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
"""

from __future__ import annotations

import argparse
from pathlib import Path

from imdr.config.settings import get_settings
from imdr.connectors.mssql import MSSQLConnector
from imdr.connectors.reader import AnalyticalReader
from imdr.domains.fx.clean_fx_fact_ohlc import (
    BidAskInversionRule,
    HardBoundViolationRule,
    NonPositivePriceRule,
    PercentageChangeRule,
    RobustOutlierRule,
)
from imdr.healthchecks.clean_cli import compute_overlap_stats, print_clean_summary
from imdr.healthchecks.cleaning import CleaningResult, CleaningRunner
from imdr.universe.fx import get_fx_universe

PIPELINE_NAME = "fx.ohlc"
TABLE = "[fx].[fact_ohlc]"
RULE_NAMES = ["non_positive", "hard_bound", "pct_change", "robust_outlier", "bid_ask"]


def build_cleaning_rules(
    n_mad: float | None = None,
    trailing_months: int | None = None,
    pct_threshold: float | None = None,
    rule: str | None = None,
) -> list:
    """Build the ordered list of FX OHLC cleaning rules.

    Defaults read from ``pipelines.yml`` (fx.ohlc.cleaning).
    CLI ``--n-mad`` / ``--trailing-months`` / ``--pct-threshold`` override when provided.
    """
    from imdr.config.pipeline_config import get_pipeline_config

    cfg = get_pipeline_config(PIPELINE_NAME).cleaning
    n_mad = n_mad if n_mad is not None else cfg.n_mad
    trailing_months = trailing_months if trailing_months is not None else cfg.trailing_months
    pct_threshold = pct_threshold if pct_threshold is not None else cfg.pct_threshold

    universe = get_fx_universe()
    ranges = {
        sym: (r.min, r.max)
        for sym in universe.api_symbols()
        if (r := universe.expected_range_for(sym)) is not None
    }

    all_rules = [
        NonPositivePriceRule(),
        HardBoundViolationRule(ranges=ranges),
        PercentageChangeRule(threshold_pct=pct_threshold),
        RobustOutlierRule(n_mad=n_mad, trailing_months=trailing_months),
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
        default=None,
        help="Percentage change threshold for bar-to-bar detection (default: from pipelines.yml)",
    )
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

    connector.dispose()


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


if __name__ == "__main__":
    main()
