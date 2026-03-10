"""One-time migration: convert legacy FX parquet files to new format.

Reads from the old FX_data repo layout:
    FX_data/data/raw/hourly_batches/{YYYY}/{MM}/{DD}/fx_bars_{YYYYMMDD}_{HH}.parquet

Writes to IMDR's parquet archive layout:
    IMDR/data/parquet/fx/fact_ohlc/fx_ohlc_{YYYYMMDD}_{HH}00.parquet

Transforms applied:
    1. Rename price columns:  open -> open_px, high -> high_px, low -> low_px,
       close -> close_px, quote_mid -> mid_px, mid_mean -> mid_mean_px,
       mid_median -> mid_median_px
    2. Strip dot from symbol: EUR.USD -> EURUSD
    3. Timestamps are already UTC-aware — passed through unchanged.

Usage:
    python -m scripts.migrations.convert_legacy_parquet
    python -m scripts.migrations.convert_legacy_parquet --dry-run
    python -m scripts.migrations.convert_legacy_parquet --year 2025
    python -m scripts.migrations.convert_legacy_parquet --year 2024 --month 6
"""

from __future__ import annotations

import argparse
import glob
import multiprocessing as mp
import os
import sys
import time
from pathlib import Path

import pandas as pd

# ── Paths ────────────────────────────────────────────────────────────────────
LEGACY_ROOT = Path("Z:/Business/Personnel/Arjun/GitHub/FX_data/data/raw/hourly_batches")
OUTPUT_ROOT = Path("Z:/Business/Personnel/Arjun/GitHub/IMDR/data/parquet/fx/fact_ohlc")

# ── Column rename map (legacy -> new) ────────────────────────────────────────
COLUMN_RENAME = {
    "open": "open_px",
    "high": "high_px",
    "low": "low_px",
    "close": "close_px",
    "quote_mid": "mid_px",
    "mid_mean": "mid_mean_px",
    "mid_median": "mid_median_px",
}

# Columns expected in the final output (order matches the DB model)
EXPECTED_COLUMNS = [
    "ts", "symbol", "series", "tenor", "deal_type", "pair_used",
    "open_px", "high_px", "low_px", "close_px",
    "mid_px", "mid_mean_px", "mid_median_px",
    "bid", "ask", "n_ticks",
]


def _convert_one(args: tuple[str, str, bool]) -> tuple[int, str]:
    """Worker function for multiprocessing. Takes (src, dst, dry_run) as strings.

    Returns (row_count, status) where status is 'converted', 'skipped', 'warn:...',
    'reject:...', or 'error:...'.
    """
    src, dst, dry_run = Path(args[0]), Path(args[1]), args[2]

    if not dry_run and dst.exists():
        return 0, "skipped"

    try:
        df = pd.read_parquet(src)
    except Exception as exc:
        return 0, f"error:{src.name} {type(exc).__name__}: {exc}"

    # 1. Verify ts is UTC-aware (hard gate — reject non-UTC files)
    if df["ts"].dt.tz is None:
        return 0, f"reject:{src.name} ts is timezone-naive"
    if str(df["ts"].dt.tz) != "UTC":
        return 0, f"reject:{src.name} ts timezone is {df['ts'].dt.tz}, expected UTC"

    # 2. Rename price columns
    df = df.rename(columns=COLUMN_RENAME)

    # 3. Strip dot from symbol: EUR.USD -> EURUSD
    df["symbol"] = df["symbol"].str.replace(".", "", regex=False)

    # 4. Validate expected columns are present
    missing = set(EXPECTED_COLUMNS) - set(df.columns)
    if missing:
        return 0, f"warn:{src.name} missing columns {missing}"

    # 5. Reorder to canonical column order
    df = df[EXPECTED_COLUMNS]

    if dry_run:
        return len(df), "converted"

    dst.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(dst, index=False)
    return len(df), "converted"


def derive_output_path(src: Path) -> Path:
    """Map legacy filename to new filename, preserving YYYY/MM/DD/ folder structure.

    Legacy:  .../2025/06/15/fx_bars_20250615_21.parquet
    New:     .../2025/06/15/fx_ohlc_20250615_2100.parquet
    """
    name = src.stem  # fx_bars_20250615_21
    parts = name.split("_")
    # parts = ['fx', 'bars', '20250615', '21']
    date_str = parts[2]  # 20250615
    hour_str = parts[3]  # 21
    yyyy = date_str[:4]
    mm = date_str[4:6]
    dd = date_str[6:8]
    new_name = f"fx_ohlc_{date_str}_{hour_str}00.parquet"
    return OUTPUT_ROOT / yyyy / mm / dd / new_name


def gather_files(year: int | None = None, month: int | None = None) -> list[Path]:
    """Collect legacy parquet files, optionally filtered by year/month."""
    if year and month:
        pattern = str(LEGACY_ROOT / str(year) / f"{month:02d}" / "**" / "*.parquet")
    elif year:
        pattern = str(LEGACY_ROOT / str(year) / "**" / "*.parquet")
    else:
        pattern = str(LEGACY_ROOT / "**" / "*.parquet")
    return sorted(Path(f) for f in glob.glob(pattern, recursive=True))


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert legacy FX parquet to new format")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing files")
    parser.add_argument("--year", type=int, help="Filter to a specific year")
    parser.add_argument("--month", type=int, help="Filter to a specific month (requires --year)")
    parser.add_argument("--workers", type=int, default=os.cpu_count(), help="Number of parallel workers (default: CPU count)")
    args = parser.parse_args()

    if args.month and not args.year:
        parser.error("--month requires --year")

    files = gather_files(year=args.year, month=args.month)
    print(f"Found {len(files)} legacy parquet files")
    print(f"Using {args.workers} workers")

    if not files:
        return

    if args.dry_run:
        print("DRY RUN — no files will be written\n")

    # Ensure output dir exists before workers try to write
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    # Build work items: (src_str, dst_str, dry_run)
    work = [(str(src), str(derive_output_path(src)), args.dry_run) for src in files]

    total_rows = 0
    converted = 0
    skipped = 0
    warnings: list[str] = []
    rejected: list[str] = []
    errors: list[str] = []
    t0 = time.perf_counter()

    with mp.Pool(processes=args.workers) as pool:
        for i, (rows, status) in enumerate(pool.imap_unordered(_convert_one, work), 1):
            if status == "skipped":
                skipped += 1
            elif status.startswith("warn:"):
                warnings.append(status[5:])
            elif status.startswith("reject:"):
                rejected.append(status[7:])
            elif status.startswith("error:"):
                errors.append(status[6:])
            else:
                converted += 1
                total_rows += rows

            if i % 1000 == 0:
                elapsed = time.perf_counter() - t0
                rate = i / elapsed
                print(f"  [{i}/{len(files)}] {rate:.0f} files/s — {total_rows:,} rows so far")

    elapsed = time.perf_counter() - t0
    print(f"\nDone in {elapsed:.1f}s")
    print(f"  Converted: {converted}")
    print(f"  Skipped (already exist): {skipped}")
    print(f"  Total rows: {total_rows:,}")
    if errors:
        print(f"  ERRORS (corrupt/unreadable): {len(errors)}")
        for e in errors[:20]:
            print(f"    {e}")
    if rejected:
        print(f"  REJECTED (non-UTC): {len(rejected)}")
        for r in rejected[:20]:
            print(f"    {r}")
    if warnings:
        print(f"  Warnings: {len(warnings)}")
        for w in warnings[:10]:
            print(f"    {w}")

    if args.dry_run and files:
        sample_src = files[0]
        sample_dst = derive_output_path(sample_src)
        print(f"\nSample mapping:")
        print(f"  {sample_src.name}  ->  {sample_dst.name}")
        df = pd.read_parquet(sample_src)
        df = df.rename(columns=COLUMN_RENAME)
        df["symbol"] = df["symbol"].str.replace(".", "", regex=False)
        df = df[EXPECTED_COLUMNS]
        print(f"\nSample output ({len(df)} rows):")
        print(df.head(3).to_string(index=False))


if __name__ == "__main__":
    main()
