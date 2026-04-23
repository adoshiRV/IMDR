"""Rates Swaption Skew Loader — Barclays/S&P Excel files.

Target table: [rates].[fact_swaption_skew]
Source: Barclays Trading / S&P Global Market Intelligence Excel exports.

Drop .xlsx files in data/skew/ and run:
    python -m scripts.rates.barclays.rates_skew_load

Or specify files directly:
    python -m scripts.rates.barclays.rates_skew_load --files path1.xlsx path2.xlsx
    python -m scripts.rates.barclays.rates_skew_load --start 2024-01-01 --end 2024-12-31
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import structlog

from imdr.config.settings import get_settings
from imdr.connectors.mssql import MSSQLConnector
from imdr.domains.rates.pipeline_skew import RatesSkewPipeline
from imdr.notifications.email import send_outlook_email
from imdr.notifications.formatters.rates_skew_ingest import RatesSkewIngestFormatter
from imdr.reporting.run_report import RunReport
from imdr.utils.logging import configure_logging

log = structlog.get_logger(__name__)

DEFAULT_SKEW_DIR = Path("data/skew")
ARCHIVE_SUBDIR = "old"
VENDOR_NAME = "barclays"


def _archive_files(files: list[Path], archive_dir: Path) -> list[tuple[Path, Path]]:
    """Move processed files into archive_dir, tagging each with the run date.

    Name pattern: ``{stem}_{YYYY-MM-DD}{suffix}``. On collision (same file archived
    twice in one day) a HHMMSS timestamp is appended as well.

    Returns a list of (src, dst) tuples for the files that were moved.
    """
    archive_dir.mkdir(parents=True, exist_ok=True)
    run_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    moved: list[tuple[Path, Path]] = []
    for src in files:
        if not src.exists():
            continue
        dst = archive_dir / f"{src.stem}_{run_date}{src.suffix}"
        if dst.exists():
            ts = datetime.now(timezone.utc).strftime("%H%M%S")
            dst = archive_dir / f"{src.stem}_{run_date}_{ts}{src.suffix}"
        src.replace(dst)
        moved.append((src, dst))
    return moved


def _resolve_vendor_id(connector: MSSQLConnector) -> int:
    """Look up the vendor_id for 'barclays' from dbo.dim_vendor."""
    from sqlalchemy import select, text

    with connector.session() as session:
        result = session.execute(
            text("SELECT id FROM [dbo].[dim_vendor] WHERE vendor_code = :code"),
            {"code": VENDOR_NAME},
        ).scalar_one_or_none()

    if result is None:
        raise RuntimeError(
            f"Vendor '{VENDOR_NAME}' not found in dbo.dim_vendor. "
            "Run migration 018_create_dim_vendor.sql first."
        )
    return result


def _discover_files(directory: Path) -> list[Path]:
    """Find all .xlsx files in the drop folder."""
    if not directory.exists():
        return []
    files = sorted(directory.glob("*.xlsx"))
    return [f for f in files if not f.name.startswith("~$")]  # skip temp files


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rates Swaption Skew Loader")
    parser.add_argument(
        "--dir", type=str, default=str(DEFAULT_SKEW_DIR),
        help=f"Directory to scan for .xlsx files. Default: {DEFAULT_SKEW_DIR}",
    )
    parser.add_argument(
        "--files", nargs="+", type=str, default=None,
        help="Explicit file paths (overrides --dir).",
    )
    parser.add_argument(
        "--start", type=str, default=None,
        help="Start date filter (YYYY-MM-DD). Default: all dates.",
    )
    parser.add_argument(
        "--end", type=str, default=None,
        help="End date filter (YYYY-MM-DD). Default: all dates.",
    )
    parser.add_argument(
        "--chunk-size", type=int, default=5000,
        help="Chunk size for bulk merge. Default: 5000.",
    )
    parser.add_argument(
        "--no-archive", action="store_true",
        help="Skip moving processed files to data/skew/old/ after a successful run.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = get_settings()
    configure_logging(settings)

    report = RunReport(pipeline_name="rates.skew_barclays_load")

    # Resolve file paths
    if args.files:
        file_paths = [Path(f) for f in args.files]
    else:
        file_paths = _discover_files(Path(args.dir))

    if not file_paths:
        log.error("no_files_found", dir=args.dir)
        print(f"ERROR: No .xlsx files found in {args.dir}")
        return 1

    # Validate files exist
    for fp in file_paths:
        if not fp.exists():
            log.error("file_not_found", path=str(fp))
            print(f"ERROR: File not found: {fp}")
            return 1

    log.info(
        "skew_load_start",
        n_files=len(file_paths),
        files=[f.name for f in file_paths],
    )

    # Parse date filters
    start = datetime.strptime(args.start, "%Y-%m-%d").date() if args.start else None
    end = datetime.strptime(args.end, "%Y-%m-%d").date() if args.end else None

    connector = MSSQLConnector(settings)
    try:
        vendor_id = _resolve_vendor_id(connector)

        t0 = time.perf_counter()
        pipeline = RatesSkewPipeline(
            connector=connector,
            settings=settings,
            file_paths=file_paths,
            vendor_id=vendor_id,
            start=start,
            end=end,
            chunk_size=args.chunk_size,
        )
        result = pipeline.run()
        elapsed = time.perf_counter() - t0

        # Per-expiry breakdown
        expiry_data: list[dict] = []
        if pipeline._raw_df is not None and not pipeline._raw_df.empty:
            for expiry in sorted(pipeline._raw_df["option_expiry"].unique()):
                mask = pipeline._raw_df["option_expiry"] == expiry
                n_obs = int(mask.sum())
                n_dates = pipeline._raw_df.loc[mask, "ts"].nunique()
                expiry_data.append({
                    "option_expiry": expiry,
                    "n_obs": n_obs,
                    "n_dates": n_dates,
                })

        report.info("pipeline", f"Loaded {result} rows", details={
            "n_files": len(file_paths),
            "rows_loaded": result,
            "elapsed_secs": round(elapsed, 1),
            "per_expiry": expiry_data,
            "date_range": [args.start or "earliest", args.end or "latest"],
        })

        # Send email notification
        if settings.email_enabled and settings.email_to:
            _send_report_email(
                settings=settings,
                report=report,
                result=result,
                file_paths=file_paths,
                expiry_data=expiry_data,
                elapsed_secs=elapsed,
                start=start,
                end=end,
                rows_extracted=len(pipeline._raw_df) if pipeline._raw_df is not None else 0,
            )

        report.finish()

        # Flush RunReport to JSONL
        if settings.run_log_dir:
            ts = datetime.now(timezone.utc)
            log_path = (
                Path(settings.run_log_dir)
                / "rates"
                / "swaption_skew"
                / f"rates_skew_load_{ts:%Y%m%d_%H%M%S}.jsonl"
            )
            report.flush_jsonl(log_path)

        log.info(
            "skew_load_complete",
            rows=result,
            elapsed=f"{elapsed:.1f}s",
        )

        # Archive processed files on success (opt-out via --no-archive).
        if not args.no_archive:
            archive_dir = Path(args.dir) / ARCHIVE_SUBDIR
            moved = _archive_files(file_paths, archive_dir)
            for src, dst in moved:
                log.info("archived_file", src=str(src), dst=str(dst))

        return 0

    except Exception:
        log.exception("skew_load_failed")
        report.error("pipeline", "Skew load failed")
        report.finish()
        return 1
    finally:
        connector.dispose()


def _send_report_email(
    settings: object,
    report: RunReport,
    result: int,
    file_paths: list[Path],
    expiry_data: list[dict],
    elapsed_secs: float,
    start: object,
    end: object,
    rows_extracted: int,
) -> None:
    """Build and send the rates skew load report email."""
    formatter = RatesSkewIngestFormatter()
    has_errors = report.has_errors

    subject = formatter.format_subject(
        rows_loaded=result,
        n_expiries=len(expiry_data),
        has_errors=has_errors,
        start=start,
        end=end,
    )
    body = formatter.format_body(
        rows_extracted=rows_extracted,
        rows_loaded=result,
        n_files=len(file_paths),
        file_names=[f.name for f in file_paths],
        expiry_data=expiry_data,
        has_errors=has_errors,
        elapsed_secs=elapsed_secs,
        start=start,
        end=end,
    )
    send_outlook_email(
        to=settings.email_to,  # type: ignore[attr-defined]
        subject=subject,
        html_body=body,
        importance=2 if has_errors else 1,
    )


if __name__ == "__main__":
    sys.exit(main())
