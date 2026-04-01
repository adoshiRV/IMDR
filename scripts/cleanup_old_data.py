"""IMDR Data Cleanup — prune old parquet backups and log files.

Walks the ``data/parquet/`` and ``data/logs/`` directories and removes any
files whose embedded date is older than a configurable retention period
(default: 3 months).  Cache and other reference directories are never touched.

Folder conventions
------------------
* **Parquet (FX)** — ``data/parquet/fx/{table}/{YYYY}/{MM}/{DD}/*.parquet``
  Date is derived from the ``YYYY/MM/DD`` directory path.
* **Parquet (Rates)** — ``data/parquet/rates/.../YYYY-MM.parquet``
  Hive-style partitioning with ``YYYY-MM`` monthly files.  Date is extracted
  from the filename.  Accompanying ``_manifest.json`` files are also removed.
* **Logs** — ``data/logs/{schema}/{table}/*_{YYYYMMDD}_*.jsonl``
  Date is extracted from the ``_YYYYMMDD_`` segment in the filename.

After deleting files, empty parent directories are pruned bottom-up so the
tree stays tidy.

Safety
------
* **Dry-run by default** — pass ``--execute`` to actually delete.  Without it
  the script only prints what *would* be removed.
* Only targets ``data/parquet/`` and ``data/logs/``.  ``data/cache/`` and
  ``data/gaps/`` are explicitly excluded.

Usage::

    # Preview what would be deleted (safe)
    python -m scripts.cleanup_old_data

    # Actually delete
    python -m scripts.cleanup_old_data --execute

    # Custom retention (e.g. 6 months)
    python -m scripts.cleanup_old_data --months 6 --execute
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import date, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# Resolve project root (two levels up from this script)
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"

# Directories to clean
PARQUET_DIR = DATA_DIR / "parquet"
LOGS_DIR = DATA_DIR / "logs"

# Regex for YYYYMMDD in log filenames
_DATE_RE = re.compile(r"_(\d{8})_")

# Regex for YYYY-MM.parquet (rates Hive-style monthly files)
_MONTHLY_RE = re.compile(r"^(\d{4})-(\d{2})\.parquet$")


def _cutoff_date(months: int) -> date:
    """Return the date *months* months before today.

    Uses a simple 30-day-per-month approximation so the behaviour is
    predictable and doesn't depend on calendar quirks.
    """
    return date.today() - timedelta(days=months * 30)


# ---------------------------------------------------------------------------
# Parquet cleanup
# ---------------------------------------------------------------------------

def _cleanup_parquet(cutoff: date, *, execute: bool) -> tuple[int, int]:
    """Delete parquet files older than *cutoff*.

    Handles two layout conventions:

    1. **Date-folder layout** (FX): ``{schema}/{table}/{YYYY}/{MM}/{DD}/``
       — date derived from the folder path.
    2. **Hive-style layout** (Rates): ``{schema}/.../YYYY-MM.parquet``
       — date derived from the filename.  The accompanying
       ``YYYY-MM_manifest.json`` is also removed.

    Returns ``(files_deleted, bytes_freed)``.
    """
    files_deleted = 0
    bytes_freed = 0

    if not PARQUET_DIR.exists():
        return files_deleted, bytes_freed

    # Walk the entire parquet tree and handle files based on naming convention
    for root, _dirs, files in os.walk(PARQUET_DIR):
        root_path = Path(root)

        # --- Strategy 1: date-folder layout (YYYY/MM/DD) ---
        # Check if this directory looks like a DD folder inside MM/YYYY
        parts = root_path.relative_to(PARQUET_DIR).parts
        # pattern: schema/table/YYYY/MM/DD  →  5 parts
        if len(parts) >= 5:
            try:
                folder_date = date(int(parts[2]), int(parts[3]), int(parts[4]))
            except (ValueError, IndexError):
                folder_date = None

            if folder_date is not None and folder_date < cutoff:
                for fname in files:
                    fp = root_path / fname
                    size = fp.stat().st_size
                    if execute:
                        fp.unlink()
                    print(f"{'DEL' if execute else 'DRY'}  {fp}  ({_fmt_size(size)})")
                    files_deleted += 1
                    bytes_freed += size

                if execute:
                    # schema/table is 2 levels deep
                    table_dir = PARQUET_DIR / parts[0] / parts[1]
                    _remove_empty_parents(root_path, stop_at=table_dir)
                continue  # already handled all files in this dir

        # --- Strategy 2: Hive-style monthly files (YYYY-MM.parquet) ---
        for fname in files:
            m = _MONTHLY_RE.match(fname)
            if not m:
                continue
            try:
                file_date = date(int(m.group(1)), int(m.group(2)), 1)
            except ValueError:
                continue

            if file_date >= cutoff:
                continue

            # Delete the parquet file
            fp = root_path / fname
            size = fp.stat().st_size
            if execute:
                fp.unlink()
            print(f"{'DEL' if execute else 'DRY'}  {fp}  ({_fmt_size(size)})")
            files_deleted += 1
            bytes_freed += size

            # Also delete the accompanying manifest if present
            manifest = root_path / fname.replace(".parquet", "_manifest.json")
            if manifest.exists():
                msize = manifest.stat().st_size
                if execute:
                    manifest.unlink()
                print(f"{'DEL' if execute else 'DRY'}  {manifest}  ({_fmt_size(msize)})")
                files_deleted += 1
                bytes_freed += msize

    # Final pass: prune empty directories
    if execute:
        _prune_empty_dirs(PARQUET_DIR)

    return files_deleted, bytes_freed


# ---------------------------------------------------------------------------
# Log cleanup
# ---------------------------------------------------------------------------

def _cleanup_logs(cutoff: date, *, execute: bool) -> tuple[int, int]:
    """Delete log files whose embedded YYYYMMDD is older than *cutoff*.

    Returns ``(files_deleted, bytes_freed)``.
    """
    files_deleted = 0
    bytes_freed = 0

    if not LOGS_DIR.exists():
        return files_deleted, bytes_freed

    for root, _dirs, files in os.walk(LOGS_DIR):
        for fname in files:
            m = _DATE_RE.search(fname)
            if not m:
                continue
            try:
                file_date = date(
                    int(m.group(1)[:4]),
                    int(m.group(1)[4:6]),
                    int(m.group(1)[6:8]),
                )
            except ValueError:
                continue

            if file_date >= cutoff:
                continue

            fp = Path(root) / fname
            size = fp.stat().st_size
            if execute:
                fp.unlink()
            print(f"{'DEL' if execute else 'DRY'}  {fp}  ({_fmt_size(size)})")
            files_deleted += 1
            bytes_freed += size

    # Prune empty directories under logs
    if execute:
        _prune_empty_dirs(LOGS_DIR)

    return files_deleted, bytes_freed


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _subdirs(path: Path) -> list[Path]:
    """Return sorted list of immediate subdirectories."""
    if not path.is_dir():
        return []
    return sorted(p for p in path.iterdir() if p.is_dir())


def _remove_empty_parents(start: Path, *, stop_at: Path) -> None:
    """Remove *start* and its parents up to (but not including) *stop_at*
    as long as they are empty."""
    current = start
    while current != stop_at:
        try:
            current.rmdir()  # only succeeds if empty
        except OSError:
            break
        current = current.parent


def _prune_empty_dirs(root: Path) -> None:
    """Walk *root* bottom-up and remove any empty directories."""
    for dirpath, dirnames, filenames in os.walk(root, topdown=False):
        if not dirnames and not filenames:
            p = Path(dirpath)
            if p != root:
                try:
                    p.rmdir()
                except OSError:
                    pass


def _fmt_size(nbytes: int) -> str:
    """Human-readable file size."""
    for unit in ("B", "KB", "MB", "GB"):
        if nbytes < 1024:
            return f"{nbytes:.1f} {unit}"
        nbytes /= 1024  # type: ignore[assignment]
    return f"{nbytes:.1f} TB"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Delete old parquet backups and log files from data/.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually delete files. Without this flag the script only prints "
             "what would be removed (dry-run).",
    )
    parser.add_argument(
        "--months",
        type=int,
        default=3,
        help="Retention period in months (default: 3).",
    )
    args = parser.parse_args()

    cutoff = _cutoff_date(args.months)
    mode = "EXECUTE" if args.execute else "DRY-RUN"
    print(f"Cleanup mode: {mode}  |  Cutoff date: {cutoff}  |  Retention: {args.months} months\n")

    pq_files, pq_bytes = _cleanup_parquet(cutoff, execute=args.execute)
    log_files, log_bytes = _cleanup_logs(cutoff, execute=args.execute)

    total_files = pq_files + log_files
    total_bytes = pq_bytes + log_bytes

    print(f"\n{'Deleted' if args.execute else 'Would delete'}: "
          f"{total_files} files  ({_fmt_size(total_bytes)})")
    print(f"  Parquet: {pq_files} files  ({_fmt_size(pq_bytes)})")
    print(f"  Logs:    {log_files} files  ({_fmt_size(log_bytes)})")

    if not args.execute and total_files > 0:
        print("\nRe-run with --execute to delete these files.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
