"""BBG FX rate backfill — repair a gap in fx.fact_fx_rate from the BBG CSVs.

Target table: [fx].[fact_fx_rate]  (frequency DAILY, vendor BBG)
Schedule: MANUAL — this is a repair tool, not a cron job.
Source: the BBG R-pipeline CSVs on Z:, read-only.

Built for the onshore-EM outage: ``BBG_mirror\\FX`` was provisioned with 22
currency folders and none of CNY/CNO/MYO/IDO, so USD/CNY, USD/IDO and USD/MYO
stopped at 2026-04-24 — the day the FX feed cut over to the mirror. The legacy
``BBG\\FX`` tree kept carrying them, so the gap was recoverable from files
already on disk.

Defaults to the onshore ccys read from the legacy root, which is the case it
was written for, but ``--ccy`` and ``--root`` make it usable for any BBG FX
gap.

CNO is NOT a default: ``FX_CNO.csv`` labels its tenors ``FX_CNY_*`` against a
``CNO`` folder, so ``alias_to_tenor`` rejects every row and the file yields
nothing. USD/CNO has never held a fact row.

Usage::

    # Show what would load, write nothing (ALWAYS run this first)
    python -m scripts.fx.bbg.fx_rate_bbg_backfill --since 2026-04-25 --dry-run

    # Load it
    python -m scripts.fx.bbg.fx_rate_bbg_backfill --since 2026-04-25

    # A single pair, bounded window
    python -m scripts.fx.bbg.fx_rate_bbg_backfill --ccy MYO \\
        --since 2026-04-25 --until 2026-06-30 --dry-run

Idempotent: rows are MERGEd on
``(pair_id, vendor_id, frequency_id, obs_ts, tenor)`` with obs_ts fixed at
midnight UTC of obs_date, so re-running the same window is a no-op.
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

import structlog

from imdr.config.settings import get_settings
from imdr.connectors.mssql import MSSQLConnector
from imdr.domains.fx.pipeline_rate_bbg_backfill import (
    BloombergFXRateBackfillPipeline,
)
from imdr.universe.fx import get_fx_universe
from imdr.utils.logging import configure_logging
from imdr.vendors.specs._bbg_factory import BBG_LEGACY_FX_ROOT, ONSHORE_FX_CCYS

log = structlog.get_logger(__name__)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--ccy", action="append", default=None,
                   help=f"BBG ccy folder to backfill; repeatable. "
                        f"Default: {' '.join(ONSHORE_FX_CCYS)}")
    p.add_argument("--root", default=str(BBG_LEGACY_FX_ROOT),
                   help="FX root holding <CCY>/FX_<CCY>.csv (read-only).")
    p.add_argument("--since", default=None,
                   help="Earliest obs_date to load, YYYY-MM-DD.")
    p.add_argument("--until", default=None,
                   help="Latest obs_date to load, YYYY-MM-DD.")
    p.add_argument("--dry-run", action="store_true",
                   help="Extract and report only — writes nothing.")
    return p.parse_args()


def _date(v: str | None, flag: str) -> dt.date | None:
    if v is None:
        return None
    try:
        return dt.date.fromisoformat(v)
    except ValueError:
        print(f"!! {flag} must be YYYY-MM-DD, got {v!r}", file=sys.stderr)
        raise SystemExit(1)


def _report(df) -> None:
    """Print a per-pair breakdown of whatever the extract produced."""
    if df is None or df.empty:
        print("\nNo rows extracted — nothing to load.")
        return
    import pandas as pd

    print(f"\n{'pair':<10}{'rows':>7}{'tenors':>8}{'dates':>7}  "
          f"{'first':>12}  {'last':>12}")
    print("-" * 60)
    for (base, quote), grp in df.groupby(["base_ccy", "quote_ccy"]):
        obs = pd.to_datetime(grp["obs_date"]).dt.date
        print(f"{base + '/' + quote:<10}{len(grp):>7}"
              f"{grp['tenor'].nunique():>8}{obs.nunique():>7}  "
              f"{str(obs.min()):>12}  {str(obs.max()):>12}")
    print(f"{'TOTAL':<10}{len(df):>7}")


def main() -> int:
    args = parse_args()
    settings = get_settings()
    configure_logging(settings)

    since = _date(args.since, "--since")
    until = _date(args.until, "--until")
    if since and until and since > until:
        print(f"!! --since {since} is after --until {until}", file=sys.stderr)
        return 1

    ccys = args.ccy or list(ONSHORE_FX_CCYS)
    root = Path(args.root)
    if not root.exists():
        print(f"!! root does not exist: {root}", file=sys.stderr)
        return 1

    files: list[Path] = []
    missing: list[str] = []
    for ccy in ccys:
        f = root / ccy / f"FX_{ccy}.csv"
        (files if f.is_file() else missing).append(f if f.is_file() else ccy)
    if missing:
        print(f"!! no CSV for: {', '.join(str(m) for m in missing)}",
              file=sys.stderr)
    if not files:
        print("!! no source files found — nothing to do", file=sys.stderr)
        return 1

    print(f"BBG FX backfill — {len(files)} file(s) under {root}")
    print(f"  ccys   : {' '.join(ccys)}")
    print(f"  window : {since or 'file start'} .. {until or 'file end'}")
    print(f"  mode   : {'DRY RUN (no writes)' if args.dry_run else 'LOAD'}")

    connector = MSSQLConnector(settings)
    try:
        pipeline = BloombergFXRateBackfillPipeline(
            files=files,
            connector=connector,
            settings=settings,
            universe=get_fx_universe(),
            bbg_fx_root=root,
            since=since,
            until=until,
        )

        if args.dry_run:
            # Extract only. transform() seeds dim_currency_pair and load()
            # writes facts, so neither may run on a dry pass.
            df = pipeline.extract()
            _report(df)
            for err in pipeline._extraction_errors[:10]:
                print(f"   ERR {err}")
            print("\nDRY RUN — fx.fact_fx_rate untouched.")
            return 0

        rows = pipeline.run()
        _report(pipeline._raw_df)
        for err in pipeline._extraction_errors[:10]:
            print(f"   ERR {err}")
        print(f"\nLoaded {rows} rows into [fx].[fact_fx_rate]")
        log.info("bbg_fx_backfill_complete", rows=rows, ccys=ccys)
        return 0
    finally:
        connector.dispose()


if __name__ == "__main__":
    sys.exit(main())
