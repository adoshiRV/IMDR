"""One-shot historical backfill: BBG_mirror rates → rates.fact_observation (DAILY).

Reads the FULL historical tail of every PAR CSV under
``Z:\\Business\\Research\\Dashboard\\DataSources\\BBG_mirror\\{IRS,OIS,BASIS,CCS}\\``
and bulk-upserts each row stamped with:
  - ``frequency_id = DAILY``
  - ``ts = midnight UTC of obs_date``
  - ``vendor_id = bloomberg``
  - ``quote = 'par'`` for IRS/OIS/CCS, ``quote = 'basis'`` for BASIS

Reuses ``BloombergRatesDailyPipeline(historical=True)`` — same class
that powers the live ``bbg_rates_daily`` feed, just with the
``historical`` flag flipped so the extractor returns ALL rows rather
than just the latest.

Idempotent on ``(curve_id, vendor_id, ts, quote, tenor, frequency_id)``
— re-runs are MERGE no-ops.

**HARD RULE — Z:\\BBG_mirror\\ is read-only.** This script only
``glob``s + ``read_csv``s; never writes/moves/deletes.

Usage:
    python -m scripts.migrations.load_bbg_rates_historical                    # dry-run
    python -m scripts.migrations.load_bbg_rates_historical --execute          # write
    python -m scripts.migrations.load_bbg_rates_historical --kind IRS         # subset
    python -m scripts.migrations.load_bbg_rates_historical --curve AUD-BBSW-3M
"""
from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore")

from imdr.config.settings import get_settings
from imdr.connectors.mssql import MSSQLConnector
from imdr.domains.rates.extractors_bbg import (
    BloombergCSVRatesExtractor,
    discover_bbg_rates_files,
)
from imdr.domains.rates.pipeline_bbg_daily import BloombergRatesDailyPipeline


BBG_ROOT = Path(r"Z:\Business\Research\Dashboard\DataSources\BBG_mirror")
DEFAULT_KINDS: tuple[str, ...] = ("IRS", "OIS", "BASIS", "CCS")


def _per_curve_report(df: pd.DataFrame) -> pd.DataFrame:
    """Trader-mindset summary by (kind, ccy, curve)."""
    if df.empty:
        return pd.DataFrame()
    grp = df.groupby(["ccy", "curve", "quote"]).agg(
        rows=("value", "size"),
        n_tenors=("tenor", "nunique"),
        min_date=("ts", "min"),
        max_date=("ts", "max"),
        val_min=("value", "min"),
        val_max=("value", "max"),
        val_median=("value", "median"),
        nan_count=("value", lambda s: int(s.isna().sum())),
    ).reset_index()
    grp["min_date"] = grp["min_date"].dt.strftime("%Y-%m-%d")
    grp["max_date"] = grp["max_date"].dt.strftime("%Y-%m-%d")
    return grp


def main() -> int:
    desc = (__doc__ or "BBG rates historical backfill").split("\n")[0]
    p = argparse.ArgumentParser(description=desc)
    p.add_argument("--execute", action="store_true",
                   help="Write to DB (default: dry-run report only)")
    p.add_argument("--kind", choices=list(DEFAULT_KINDS), default=None,
                   help="Restrict to one BBG domain (e.g. IRS)")
    p.add_argument("--curve", default=None,
                   help="Restrict to one curve folder (e.g. AUD-BBSW-3M)")
    args = p.parse_args()

    kinds = (args.kind,) if args.kind else DEFAULT_KINDS

    print("=" * 100, flush=True)
    print(f"BBG rates historical backfill — {'EXECUTE' if args.execute else 'DRY-RUN'}",
          flush=True)
    print(f"Source: {BBG_ROOT}", flush=True)
    print(f"Kinds:  {kinds}", flush=True)
    if args.curve:
        print(f"Curve:  {args.curve}", flush=True)
    print("=" * 100, flush=True)

    print("\nDiscovering source files (READ-ONLY)...", flush=True)
    sources = discover_bbg_rates_files(BBG_ROOT, kinds=kinds)
    if args.curve:
        sources = [s for s in sources if s.folder == args.curve]
    print(f"Found {len(sources)} curves across {len(set(s.kind for s in sources))} domains",
          flush=True)
    if not sources:
        print("No matching curves — exiting.", flush=True)
        return 1

    # Group source files by kind for the report
    by_kind: dict[str, int] = {}
    for s in sources:
        by_kind[s.kind] = by_kind.get(s.kind, 0) + 1
    for k, n in sorted(by_kind.items()):
        print(f"  {k}: {n} curves", flush=True)

    print("\nExtracting full history (historical mode)...", flush=True)
    extractor = BloombergCSVRatesExtractor(mode="historical")
    df = extractor.extract(sources)
    if extractor.errors:
        print(f"\n[!] Extraction errors on {len(extractor.errors)} file(s):", flush=True)
        for e in extractor.errors[:5]:
            print(f"    {e['folder']}: {e['error']}", flush=True)

    if df.empty:
        print("Extraction returned 0 rows — exiting.", flush=True)
        return 1

    # Stamp ts at midnight UTC of obs_date (historical convention).
    # The extractor already did this for mode='historical' — just verify.
    df["ts"] = pd.to_datetime(df["ts"]).dt.tz_convert("UTC")

    # ── Per-curve sanity report ────────────────────────────────────
    rep = _per_curve_report(df)
    print("\n" + "=" * 100, flush=True)
    print("PER-CURVE SUMMARY (for trader-mindset review)", flush=True)
    print("=" * 100, flush=True)
    with pd.option_context("display.max_rows", 100, "display.width", 200,
                            "display.max_colwidth", 30):
        print(rep.to_string(index=False), flush=True)

    print("\n" + "=" * 100, flush=True)
    print(f"GRAND TOTAL: {len(df):,} rows across {rep['curve'].nunique()} curves",
          flush=True)
    print(f"  Quote distribution: {df['quote'].value_counts().to_dict()}", flush=True)
    print(f"  ts range: {df['ts'].min()} -> {df['ts'].max()}", flush=True)
    print("=" * 100, flush=True)

    if not args.execute:
        print("\nDRY-RUN ONLY — no DB writes.", flush=True)
        print("Re-run with --execute to upsert.", flush=True)
        return 0

    # ── Real run: instantiate pipeline with historical=True, run load ──
    print("\nWriting to rates.fact_observation (idempotent MERGE)...", flush=True)
    settings = get_settings()
    if settings.mssql_database != "IMDR":
        raise RuntimeError(
            f"Refusing to run: IMDR_MSSQL_DATABASE={settings.mssql_database!r}"
        )
    connector = MSSQLConnector(settings)

    # Build a list of file Paths (the pipeline reconstructs sources from them)
    file_paths = [s.path for s in sources]
    pipeline = BloombergRatesDailyPipeline(
        files=file_paths,
        connector=connector,
        settings=settings,
        bbg_root=BBG_ROOT,
        historical=True,
        chunk_size=10_000,  # 473K rows → ~48 chunks; keeps lock counts low
    )
    rows_loaded = pipeline.run()
    print(f"\nDONE — {rows_loaded:,} rows upserted.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
