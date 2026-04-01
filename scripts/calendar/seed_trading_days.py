"""Seed calendar.dim_trading_day — full calendar grid for all markets.

Generates one row per market per date from START_YEAR to END_YEAR,
computing is_weekend, is_holiday, is_trading_day, and holiday_name
from markets.yml + the Python holidays library.

Idempotent — skips existing rows, only inserts new ones.
Run yearly to extend the grid, or after adding new markets.

Usage:
    python -m scripts.calendar.seed_trading_days
    python -m scripts.calendar.seed_trading_days --start-year 2025 --end-year 2030
    python -m scripts.calendar.seed_trading_days --markets US,EU,JP
    python -m scripts.calendar.seed_trading_days --dry-run
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import date, timedelta

import structlog
from sqlalchemy import text
from sqlalchemy.orm import Session

from imdr.config.settings import get_settings
from imdr.connectors.mssql import MSSQLConnector
from imdr.market_calendar.calendar import is_holiday, is_weekend
from imdr.market_calendar.holidays import _get_country_holidays, _target2_holidays
from imdr.market_calendar.markets import load_markets
from imdr.utils.logging import configure_logging

log = structlog.get_logger(__name__)

START_YEAR = 2008
END_YEAR = 2030
BATCH_SIZE = 1000  # rows per INSERT batch


def _get_holiday_name(market_code: str, market, d: date) -> str | None:
    """Get holiday name for a date, or None if not a holiday."""
    if market.calendar_type == "target2":
        t2 = _target2_holidays(d.year)
        return t2.get(d)
    hols = _get_country_holidays(market.country_code, d.year)
    return hols.get(d)


def generate_rows(
    market_code: str,
    market,
    start: date,
    end: date,
) -> list[tuple]:
    """Generate (market_code, date, is_weekend, is_holiday, is_trading_day, holiday_name) tuples."""
    rows = []
    d = start
    while d <= end:
        wknd = d.weekday() in market.weekend_days
        hol_name = _get_holiday_name(market_code, market, d)
        hol = hol_name is not None
        trading = not wknd and not hol
        rows.append((market_code, d, wknd, hol, trading, hol_name))
        d += timedelta(days=1)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed calendar.dim_trading_day grid")
    parser.add_argument("--start-year", type=int, default=START_YEAR)
    parser.add_argument("--end-year", type=int, default=END_YEAR)
    parser.add_argument("--markets", type=str, default=None, help="Comma-separated market codes")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings)

    config = load_markets()
    market_codes = (
        [m.strip().upper() for m in args.markets.split(",")]
        if args.markets
        else list(config.markets.keys())
    )

    start = date(args.start_year, 1, 1)
    end = date(args.end_year, 12, 31)
    total_days = (end - start).days + 1

    log.info(
        "seed_start",
        markets=len(market_codes),
        start=str(start),
        end=str(end),
        total_days=total_days,
    )

    if args.dry_run:
        total = len(market_codes) * total_days
        print(f"Dry run: would generate {total:,} rows ({len(market_codes)} markets x {total_days} days)")
        return 0

    connector = MSSQLConnector(settings)
    t0 = time.perf_counter()
    total_inserted = 0

    try:
        with Session(connector.engine) as session:
            for code in market_codes:
                if code not in config.markets:
                    log.warning("market_not_found", market=code)
                    continue

                market = config.markets[code]

                # Check how many rows already exist for this market
                existing = session.execute(
                    text("""
                        SELECT COUNT(*) FROM [calendar].[dim_trading_day]
                        WHERE market_code = :mc
                          AND calendar_date >= :start
                          AND calendar_date <= :end
                    """),
                    {"mc": code, "start": str(start), "end": str(end)},
                ).scalar()

                if existing == total_days:
                    log.info("market_complete", market=code, existing=existing)
                    continue

                # Generate all rows
                rows = generate_rows(code, market, start, end)

                # Bulk insert via temp table + MERGE (one round-trip per batch)
                session.execute(text("""
                    CREATE TABLE #staging (
                        market_code   VARCHAR(5)    NOT NULL,
                        calendar_date DATE          NOT NULL,
                        is_weekend    BIT           NOT NULL,
                        is_holiday    BIT           NOT NULL,
                        is_trading_day BIT          NOT NULL,
                        holiday_name  NVARCHAR(200) NULL
                    )
                """))

                inserted = 0
                for i in range(0, len(rows), BATCH_SIZE):
                    batch = rows[i : i + BATCH_SIZE]
                    session.execute(text("TRUNCATE TABLE #staging"))
                    session.execute(
                        text("""
                            INSERT INTO #staging
                                (market_code, calendar_date, is_weekend, is_holiday,
                                 is_trading_day, holiday_name)
                            VALUES
                                (:mc, :d, :wknd, :hol, :trading, :hol_name)
                        """),
                        [
                            {
                                "mc": mc, "d": str(cal_date),
                                "wknd": 1 if wknd else 0,
                                "hol": 1 if hol else 0,
                                "trading": 1 if trading else 0,
                                "hol_name": hol_name,
                            }
                            for mc, cal_date, wknd, hol, trading, hol_name in batch
                        ],
                    )
                    result = session.execute(text("""
                        MERGE [calendar].[dim_trading_day] AS tgt
                        USING #staging AS src
                            ON tgt.market_code = src.market_code
                           AND tgt.calendar_date = src.calendar_date
                        WHEN NOT MATCHED THEN
                            INSERT (market_code, calendar_date, is_weekend, is_holiday,
                                    is_trading_day, holiday_name, is_custom)
                            VALUES (src.market_code, src.calendar_date, src.is_weekend,
                                    src.is_holiday, src.is_trading_day, src.holiday_name, 0);
                    """))
                    inserted += result.rowcount
                    session.commit()

                session.execute(text("DROP TABLE #staging"))
                session.commit()

                total_inserted += inserted
                log.info("market_seeded", market=code, inserted=inserted, existing=existing)

        elapsed = time.perf_counter() - t0
        log.info("seed_complete", total_inserted=total_inserted, elapsed=f"{elapsed:.1f}s")
        print(f"Seed complete: {total_inserted:,} rows inserted in {elapsed:.1f}s")
        return 0

    except Exception:
        log.exception("seed_failed")
        return 1
    finally:
        connector.dispose()


if __name__ == "__main__":
    sys.exit(main())
