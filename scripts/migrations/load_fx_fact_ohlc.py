"""One-time migration: load converted parquet files into [FX].[fact_ohlc].

Processes year-by-year, runs health checks after each year, and prints
a per-year report plus a grand summary.

Reads from IMDR's parquet archive:
    data/parquet/fx/fact_ohlc/{YYYY}/{MM}/{DD}/fx_ohlc_{YYYYMMDD}_{HH}00.parquet

Usage:
    python -m scripts.migrations.load_fx_fact_ohlc
    python -m scripts.migrations.load_fx_fact_ohlc --dry-run
    python -m scripts.migrations.load_fx_fact_ohlc --year 2025
    python -m scripts.migrations.load_fx_fact_ohlc --year 2024 --month 6
    python -m scripts.migrations.load_fx_fact_ohlc --batch-size 5000
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from imdr.config.settings import get_settings
from imdr.connectors.mssql import MSSQLConnector
from imdr.schemas.fx_ohlc import FXFactOHLCCreate
from imdr.universe.fx import get_fx_universe

# ── Paths ────────────────────────────────────────────────────────────────────
PARQUET_ROOT = Path("Z:/Business/Personnel/Arjun/GitHub/IMDR/data/parquet/fx/fact_ohlc")

# ── Health-check thresholds ──────────────────────────────────────────────────
PRICE_COLUMNS = [
    "open_px", "high_px", "low_px", "close_px",
    "mid_px", "mid_mean_px", "mid_median_px", "bid", "ask",
]
UNIQUE_COLUMNS = ["ts", "symbol", "series", "tenor"]


# ── Data classes ─────────────────────────────────────────────────────────────
@dataclass
class CheckResult:
    name: str
    passed: bool
    message: str
    details: dict | None = None


@dataclass
class YearReport:
    year: int
    files: int = 0
    rows_validated: int = 0
    rows_written: int = 0
    validation_errors: int = 0
    elapsed_s: float = 0.0
    # Health checks (populated after DB write)
    db_row_count: int = 0
    null_columns: list[str] = field(default_factory=list)
    duplicate_groups: int = 0
    ts_min: str = ""
    ts_max: str = ""
    symbols: int = 0
    symbol_list: list[str] = field(default_factory=list)
    close_px_min: float = 0.0
    close_px_max: float = 0.0
    mid_px_min: float = 0.0
    mid_px_max: float = 0.0
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        return all(c.passed for c in self.checks)


# ── File helpers ─────────────────────────────────────────────────────────────
def gather_files(year: int | None = None, month: int | None = None) -> list[Path]:
    """Collect converted parquet files, optionally filtered by year/month."""
    if year and month:
        pattern = str(PARQUET_ROOT / str(year) / f"{month:02d}" / "**" / "*.parquet")
    elif year:
        pattern = str(PARQUET_ROOT / str(year) / "**" / "*.parquet")
    else:
        pattern = str(PARQUET_ROOT / "**" / "*.parquet")
    return sorted(Path(f) for f in glob.glob(pattern, recursive=True))


def discover_years() -> list[int]:
    """Return sorted list of year directories present in the parquet archive."""
    years = []
    for p in PARQUET_ROOT.iterdir():
        if p.is_dir() and p.name.isdigit():
            years.append(int(p.name))
    return sorted(years)


def load_and_validate(path: Path) -> tuple[list[FXFactOHLCCreate], list[str]]:
    """Read a parquet file, validate UTC, validate each row via Pydantic."""
    try:
        df = pd.read_parquet(path)
    except Exception as exc:
        return [], [f"{path.name}: failed to read parquet: {exc}"]
    errors: list[str] = []

    if df["ts"].dt.tz is None:
        return [], [f"{path.name}: ts is timezone-naive"]
    if str(df["ts"].dt.tz) != "UTC":
        return [], [f"{path.name}: ts timezone is {df['ts'].dt.tz}, expected UTC"]

    bars: list[FXFactOHLCCreate] = []
    records = df.to_dict(orient="records")
    for i, row in enumerate(records):
        try:
            bars.append(FXFactOHLCCreate.model_validate(row))
        except Exception as exc:
            errors.append(f"{path.name} row {i}: {exc}")

    return bars, errors


# ── Health checks (direct SQL for speed) ─────────────────────────────────────
def run_year_health_checks(connector: MSSQLConnector, year: int) -> YearReport:
    """Run health checks against [fx].[fact_ohlc] for a single year."""
    report = YearReport(year=year)
    start = f"{year}-01-01"
    end = f"{year + 1}-01-01"

    with connector.read_engine.connect() as conn:
        # 1. Row count
        row = conn.execute(
            text("SELECT COUNT(*) FROM [fx].[fact_ohlc] WHERE [ts] >= :s AND [ts] < :e"),
            {"s": start, "e": end},
        ).one()
        report.db_row_count = row[0]
        report.checks.append(CheckResult(
            name="row_count",
            passed=report.db_row_count > 0,
            message=f"{report.db_row_count:,} rows in DB for {year}",
        ))

        if report.db_row_count == 0:
            report.checks.append(CheckResult(
                name="skipped", passed=True,
                message="No rows — skipping remaining checks",
            ))
            return report

        # 2. Null check on price columns
        null_cases = ", ".join(
            f"SUM(CASE WHEN [{c}] IS NULL THEN 1 ELSE 0 END) AS [{c}]"
            for c in PRICE_COLUMNS
        )
        null_row = conn.execute(
            text(f"SELECT {null_cases} FROM [fx].[fact_ohlc] WHERE [ts] >= :s AND [ts] < :e"),
            {"s": start, "e": end},
        ).one()
        null_cols = [c for c, v in zip(PRICE_COLUMNS, null_row) if v and v > 0]
        report.null_columns = null_cols
        report.checks.append(CheckResult(
            name="null_check",
            passed=len(null_cols) == 0,
            message=f"NULLs in: {', '.join(null_cols)}" if null_cols else f"No NULLs in {len(PRICE_COLUMNS)} price columns",
            details={"null_columns": null_cols} if null_cols else None,
        ))

        # 3. Duplicate check on unique key
        dup_row = conn.execute(
            text(
                "SELECT COUNT(*) FROM ("
                "  SELECT [ts], [symbol], [series], [tenor], COUNT(*) AS cnt"
                "  FROM [fx].[fact_ohlc]"
                "  WHERE [ts] >= :s AND [ts] < :e"
                "  GROUP BY [ts], [symbol], [series], [tenor]"
                "  HAVING COUNT(*) > 1"
                ") d"
            ),
            {"s": start, "e": end},
        ).one()
        report.duplicate_groups = dup_row[0]
        report.checks.append(CheckResult(
            name="duplicate_check",
            passed=report.duplicate_groups == 0,
            message=f"{report.duplicate_groups} duplicate groups" if report.duplicate_groups else "No duplicates",
        ))

        # 4. Timestamp range
        ts_row = conn.execute(
            text(
                "SELECT MIN([ts]), MAX([ts])"
                " FROM [fx].[fact_ohlc]"
                " WHERE [ts] >= :s AND [ts] < :e"
            ),
            {"s": start, "e": end},
        ).one()
        report.ts_min = str(ts_row[0]) if ts_row[0] else ""
        report.ts_max = str(ts_row[1]) if ts_row[1] else ""
        report.checks.append(CheckResult(
            name="timestamp_range",
            passed=True,
            message=f"ts range: {report.ts_min} -> {report.ts_max}",
        ))

        # 5. Symbol coverage
        sym_rows = conn.execute(
            text(
                "SELECT DISTINCT [symbol]"
                " FROM [fx].[fact_ohlc]"
                " WHERE [ts] >= :s AND [ts] < :e"
                " ORDER BY [symbol]"
            ),
            {"s": start, "e": end},
        ).all()
        report.symbol_list = [r[0] for r in sym_rows]
        report.symbols = len(report.symbol_list)
        report.checks.append(CheckResult(
            name="symbol_coverage",
            passed=report.symbols > 0,
            message=f"{report.symbols} symbols: {', '.join(report.symbol_list[:10])}{'...' if report.symbols > 10 else ''}",
        ))

        # 6. Per-symbol value range — close_px and mid_px
        # Uses per-symbol hard bounds from fx.yml; flags but does not block.
        universe = get_fx_universe()
        sym_range_rows = conn.execute(
            text(
                "SELECT [symbol],"
                " MIN([close_px]) AS min_close, MAX([close_px]) AS max_close,"
                " MIN([mid_px]) AS min_mid, MAX([mid_px]) AS max_mid"
                " FROM [fx].[fact_ohlc]"
                " WHERE [ts] >= :s AND [ts] < :e"
                " GROUP BY [symbol]"
            ),
            {"s": start, "e": end},
        ).all()

        range_warnings: list[str] = []
        negative_count = 0
        for row in sym_range_rows:
            sym = row[0]
            min_close, max_close = float(row[1]), float(row[2])
            min_mid, max_mid = float(row[3]), float(row[4])

            # Universal: all prices must be positive
            if min_close <= 0 or min_mid <= 0:
                negative_count += 1
                range_warnings.append(f"{sym}: negative values (close={min_close}, mid={min_mid})")

            # Per-symbol bounds from config
            er = universe.expected_range_for(sym)
            if er:
                if min_close < er.min or max_close > er.max:
                    range_warnings.append(
                        f"{sym}: close_px [{min_close:.4f}, {max_close:.4f}] "
                        f"outside [{er.min}, {er.max}]"
                    )
                if min_mid < er.min or max_mid > er.max:
                    range_warnings.append(
                        f"{sym}: mid_px [{min_mid:.4f}, {max_mid:.4f}] "
                        f"outside [{er.min}, {er.max}]"
                    )

        if range_warnings:
            report.checks.append(CheckResult(
                name="value_range_per_symbol",
                passed=True,  # WARNING — flag but don't fail
                message=f"{len(range_warnings)} range warnings: {'; '.join(range_warnings[:3])}"
                        + (f" (+{len(range_warnings) - 3} more)" if len(range_warnings) > 3 else ""),
                details={"warnings": range_warnings},
            ))
        else:
            report.checks.append(CheckResult(
                name="value_range_per_symbol",
                passed=True,
                message=f"All {len(sym_range_rows)} symbols within expected ranges",
            ))

        # 7. n_ticks > 0 check
        bad_ticks = conn.execute(
            text(
                "SELECT COUNT(*) FROM [fx].[fact_ohlc]"
                " WHERE [ts] >= :s AND [ts] < :e AND [n_ticks] <= 0"
            ),
            {"s": start, "e": end},
        ).one()
        report.checks.append(CheckResult(
            name="n_ticks_positive",
            passed=bad_ticks[0] == 0,
            message=f"{bad_ticks[0]} rows with n_ticks <= 0" if bad_ticks[0] else "All n_ticks > 0",
        ))

    return report


# ── Display helpers ──────────────────────────────────────────────────────────
def print_year_report(rpt: YearReport) -> None:
    status = "PASS" if rpt.all_passed else "FAIL"
    print(f"\n{'=' * 70}")
    print(f"  YEAR {rpt.year}  [{status}]")
    print(f"{'=' * 70}")
    print(f"  Files processed:    {rpt.files:,}")
    print(f"  Rows validated:     {rpt.rows_validated:,}")
    print(f"  Rows written to DB: {rpt.rows_written:,}")
    print(f"  Validation errors:  {rpt.validation_errors}")
    print(f"  Elapsed:            {rpt.elapsed_s:.1f}s")
    if rpt.checks:
        print(f"  {'-' * 50}")
        print(f"  Health Checks:")
        for c in rpt.checks:
            icon = "OK" if c.passed else "!!"
            print(f"    [{icon}] {c.name}: {c.message}")
    print()


def print_grand_summary(reports: list[YearReport], total_elapsed: float) -> None:
    print(f"\n{'#' * 70}")
    print(f"  GRAND SUMMARY")
    print(f"{'#' * 70}")

    total_files = sum(r.files for r in reports)
    total_validated = sum(r.rows_validated for r in reports)
    total_written = sum(r.rows_written for r in reports)
    total_db = sum(r.db_row_count for r in reports)
    total_errors = sum(r.validation_errors for r in reports)
    all_passed = all(r.all_passed for r in reports)

    print(f"  Years loaded:       {len(reports)}")
    print(f"  Total files:        {total_files:,}")
    print(f"  Total validated:    {total_validated:,}")
    print(f"  Total written:      {total_written:,}")
    print(f"  Total in DB:        {total_db:,}")
    print(f"  Validation errors:  {total_errors}")
    print(f"  Total elapsed:      {total_elapsed:.1f}s")
    print()

    # Year-by-year summary table
    print(f"  {'Year':<6} {'Files':>8} {'Validated':>12} {'Written':>12} {'DB Rows':>12} {'Symbols':>8} {'Status':>8}")
    print(f"  {'-' * 68}")
    for r in reports:
        status = "PASS" if r.all_passed else "FAIL"
        print(
            f"  {r.year:<6} {r.files:>8,} {r.rows_validated:>12,} "
            f"{r.rows_written:>12,} {r.db_row_count:>12,} {r.symbols:>8} {status:>8}"
        )
    print(f"  {'-' * 68}")
    print(
        f"  {'TOTAL':<6} {total_files:>8,} {total_validated:>12,} "
        f"{total_written:>12,} {total_db:>12,} {'':>8} {'PASS' if all_passed else 'FAIL':>8}"
    )

    # Aggregated check failures
    failed_checks = []
    for r in reports:
        for c in r.checks:
            if not c.passed:
                failed_checks.append((r.year, c.name, c.message))
    if failed_checks:
        print(f"\n  FAILED CHECKS:")
        for year, name, msg in failed_checks:
            print(f"    [{year}] {name}: {msg}")
    else:
        print(f"\n  All health checks PASSED across all years.")
    print()


# ── Column order for staging table and MERGE ─────────────────────────────────
_DB_COLUMNS = [
    "ts", "symbol", "series", "tenor", "deal_type", "pair_used",
    "open_px", "high_px", "low_px", "close_px", "mid_px",
    "mid_mean_px", "mid_median_px", "bid", "ask", "n_ticks",
]

_MERGE_SQL = """
MERGE [fx].[fact_ohlc] AS tgt
USING ##stg_fx_ohlc AS src
ON tgt.[ts] = src.[ts]
   AND tgt.[symbol] = src.[symbol]
   AND tgt.[series] = src.[series]
   AND tgt.[tenor] = src.[tenor]
WHEN MATCHED THEN UPDATE SET
    tgt.[deal_type] = src.[deal_type],
    tgt.[pair_used] = src.[pair_used],
    tgt.[open_px] = src.[open_px],
    tgt.[high_px] = src.[high_px],
    tgt.[low_px] = src.[low_px],
    tgt.[close_px] = src.[close_px],
    tgt.[mid_px] = src.[mid_px],
    tgt.[mid_mean_px] = src.[mid_mean_px],
    tgt.[mid_median_px] = src.[mid_median_px],
    tgt.[bid] = src.[bid],
    tgt.[ask] = src.[ask],
    tgt.[n_ticks] = src.[n_ticks]
WHEN NOT MATCHED THEN INSERT (
    [ts], [symbol], [series], [tenor], [deal_type], [pair_used],
    [open_px], [high_px], [low_px], [close_px], [mid_px],
    [mid_mean_px], [mid_median_px], [bid], [ask], [n_ticks]
) VALUES (
    src.[ts], src.[symbol], src.[series], src.[tenor], src.[deal_type], src.[pair_used],
    src.[open_px], src.[high_px], src.[low_px], src.[close_px], src.[mid_px],
    src.[mid_mean_px], src.[mid_median_px], src.[bid], src.[ask], src.[n_ticks]
);
"""


def _bars_to_dataframe(bars: list[FXFactOHLCCreate]) -> pd.DataFrame:
    """Convert validated Pydantic bars to a DataFrame matching DB columns."""
    rows = [b.model_dump() for b in bars]
    df = pd.DataFrame(rows, columns=_DB_COLUMNS)
    # Ensure ts is tz-naive for MSSQL DATETIME2 insert
    df["ts"] = pd.to_datetime(df["ts"], utc=True).dt.tz_localize(None)
    # Convert Decimal -> float for pyodbc compatibility
    decimal_cols = [
        "open_px", "high_px", "low_px", "close_px", "mid_px",
        "mid_mean_px", "mid_median_px", "bid", "ask",
    ]
    for col in decimal_cols:
        df[col] = df[col].astype(float)
    return df


_STG_INSERT_SQL = (
    "INSERT INTO ##stg_fx_ohlc "
    "([ts],[symbol],[series],[tenor],[deal_type],[pair_used],"
    "[open_px],[high_px],[low_px],[close_px],[mid_px],"
    "[mid_mean_px],[mid_median_px],[bid],[ask],[n_ticks]) "
    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
)

_STG_CREATE_SQL = """
CREATE TABLE ##stg_fx_ohlc (
    [ts]            DATETIME2     NOT NULL,
    [symbol]        NVARCHAR(10)  NOT NULL,
    [series]        NVARCHAR(30)  NOT NULL,
    [tenor]         NVARCHAR(10)  NOT NULL,
    [deal_type]     NVARCHAR(20)  NOT NULL,
    [pair_used]     NVARCHAR(20)  NOT NULL,
    [open_px]       FLOAT         NOT NULL,
    [high_px]       FLOAT         NOT NULL,
    [low_px]        FLOAT         NOT NULL,
    [close_px]      FLOAT         NOT NULL,
    [mid_px]        FLOAT         NOT NULL,
    [mid_mean_px]   FLOAT         NOT NULL,
    [mid_median_px] FLOAT         NOT NULL,
    [bid]           FLOAT         NOT NULL,
    [ask]           FLOAT         NOT NULL,
    [n_ticks]       INT           NOT NULL
)
"""


def _bulk_merge(connector: MSSQLConnector, df: pd.DataFrame) -> int:
    """Bulk insert via raw pyodbc cursor + fast_executemany, then MERGE."""
    import pyodbc

    # Get the raw DBAPI connection from the engine pool
    raw_conn = connector.engine.raw_connection()
    try:
        cursor = raw_conn.cursor()
        cursor.fast_executemany = True

        # Create staging table
        cursor.execute(
            "IF OBJECT_ID('tempdb..##stg_fx_ohlc') IS NOT NULL DROP TABLE ##stg_fx_ohlc"
        )
        cursor.execute(_STG_CREATE_SQL)
        raw_conn.commit()

        # Bulk insert rows as tuples
        rows = list(df.itertuples(index=False, name=None))
        cursor.executemany(_STG_INSERT_SQL, rows)
        raw_conn.commit()

        # MERGE into target
        cursor.execute(_MERGE_SQL)
        raw_conn.commit()

        # Clean up
        cursor.execute("DROP TABLE IF EXISTS ##stg_fx_ohlc")
        raw_conn.commit()
        cursor.close()
    except Exception:
        raw_conn.rollback()
        raise
    finally:
        raw_conn.close()

    return len(df)


# ── Load a single year ───────────────────────────────────────────────────────
def load_year(
    year: int,
    connector: MSSQLConnector | None,
    batch_size: int,
    dry_run: bool,
    month: int | None = None,
) -> YearReport:
    """Load and validate all parquet files for a year, write to DB, return report."""
    files = gather_files(year=year, month=month)
    report = YearReport(year=year, files=len(files))

    if not files:
        print(f"  [{year}] No parquet files found -- skipping")
        return report

    print(f"  [{year}] Found {len(files):,} files -- reading & validating...")
    t0 = time.perf_counter()

    all_errors: list[str] = []
    all_bars: list[FXFactOHLCCreate] = []

    for i, path in enumerate(files, 1):
        bars, errors = load_and_validate(path)
        all_errors.extend(errors)
        all_bars.extend(bars)

        if i % 500 == 0:
            elapsed = time.perf_counter() - t0
            rate = i / elapsed if elapsed > 0 else 0
            print(f"    [{year}] {i:,}/{len(files):,} files ({rate:.0f}/s) -- {len(all_bars):,} bars validated")

    rows_validated = len(all_bars)
    report.rows_validated = rows_validated
    report.validation_errors = len(all_errors)

    if all_errors:
        print(f"    [{year}] {len(all_errors)} validation errors (first 5):")
        for e in all_errors[:5]:
            print(f"      {e}")

    # Write to DB in batches using fast MERGE
    rows_written = 0
    if not dry_run and connector and all_bars:
        df = _bars_to_dataframe(all_bars)
        print(f"    [{year}] Writing {len(df):,} rows to DB via staging MERGE...")

        # Process in chunks to avoid memory issues
        chunk_size = batch_size
        for chunk_start in range(0, len(df), chunk_size):
            chunk = df.iloc[chunk_start : chunk_start + chunk_size]
            written = _bulk_merge(connector, chunk)
            rows_written += written
            if chunk_start > 0 and chunk_start % (chunk_size * 5) == 0:
                print(f"    [{year}] {rows_written:,}/{len(df):,} rows merged...")

    elapsed = time.perf_counter() - t0
    report.rows_written = rows_written
    report.elapsed_s = elapsed

    print(f"    [{year}] Done: {rows_validated:,} validated, {rows_written:,} written in {elapsed:.1f}s")
    return report


# ── Main ─────────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Load converted parquet into [FX].[fact_ohlc] — year by year with health checks"
    )
    parser.add_argument("--dry-run", action="store_true", help="Validate only, don't write to DB")
    parser.add_argument("--year", type=int, help="Process a single year only")
    parser.add_argument("--month", type=int, help="Filter to a specific month (requires --year)")
    parser.add_argument("--batch-size", type=int, default=5000, help="Rows per DB commit (default: 5000)")
    parser.add_argument("--skip-health", action="store_true", help="Skip post-load health checks")
    args = parser.parse_args()

    if args.month and not args.year:
        parser.error("--month requires --year")

    # Determine years to process
    if args.year:
        years = [args.year]
    else:
        years = discover_years()

    if not years:
        print("No year directories found in parquet archive.")
        return

    print(f"Years to process: {years}")
    if args.dry_run:
        print("DRY RUN — validating only, no DB writes\n")

    settings = get_settings()
    connector = MSSQLConnector(settings) if not args.dry_run else None

    reports: list[YearReport] = []
    t_total = time.perf_counter()

    for year in years:
        report = load_year(
            year=year,
            connector=connector,
            batch_size=args.batch_size,
            dry_run=args.dry_run,
            month=args.month,
        )

        # Run health checks after each year (unless dry-run or skipped)
        if not args.dry_run and connector and not args.skip_health:
            print(f"    [{year}] Running health checks...")
            report = _merge_health(report, run_year_health_checks(connector, year))

        print_year_report(report)
        reports.append(report)

    total_elapsed = time.perf_counter() - t_total
    print_grand_summary(reports, total_elapsed)

    if connector:
        connector.dispose()


def _merge_health(load_rpt: YearReport, health_rpt: YearReport) -> YearReport:
    """Merge health-check fields from health_rpt into load_rpt."""
    load_rpt.db_row_count = health_rpt.db_row_count
    load_rpt.null_columns = health_rpt.null_columns
    load_rpt.duplicate_groups = health_rpt.duplicate_groups
    load_rpt.ts_min = health_rpt.ts_min
    load_rpt.ts_max = health_rpt.ts_max
    load_rpt.symbols = health_rpt.symbols
    load_rpt.symbol_list = health_rpt.symbol_list
    load_rpt.close_px_min = health_rpt.close_px_min
    load_rpt.close_px_max = health_rpt.close_px_max
    load_rpt.mid_px_min = health_rpt.mid_px_min
    load_rpt.mid_px_max = health_rpt.mid_px_max
    load_rpt.checks = health_rpt.checks
    return load_rpt


if __name__ == "__main__":
    main()
