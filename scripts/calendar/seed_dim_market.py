"""Seed calendar.dim_market and calendar.dim_market_currency from markets.yml.

Reads the YAML config and upserts all markets + currency mappings to the DB.
Idempotent — safe to re-run.

Usage:
    python -m scripts.calendar.seed_dim_market
"""

from __future__ import annotations

import sys

import structlog
from sqlalchemy import text
from sqlalchemy.orm import Session

from imdr.config.settings import get_settings
from imdr.connectors.mssql import MSSQLConnector
from imdr.market_calendar.markets import load_markets
from imdr.utils.logging import configure_logging

log = structlog.get_logger(__name__)

# Market display names
_MARKET_NAMES: dict[str, str] = {
    "US": "United States", "UK": "United Kingdom", "EU": "Eurozone (TARGET2)",
    "JP": "Japan", "CH": "Switzerland", "AU": "Australia", "NZ": "New Zealand",
    "CA": "Canada", "NO": "Norway", "SE": "Sweden", "DK": "Denmark",
    "CN": "China", "HK": "Hong Kong", "KR": "South Korea", "IN": "India",
    "SG": "Singapore", "TW": "Taiwan", "TH": "Thailand", "ID": "Indonesia",
    "MY": "Malaysia", "PH": "Philippines", "VN": "Vietnam",
    "BR": "Brazil", "MX": "Mexico", "AR": "Argentina", "CL": "Chile",
    "CO": "Colombia", "PE": "Peru",
    "ZA": "South Africa", "TR": "Turkey", "IL": "Israel",
    "SA": "Saudi Arabia", "AE": "UAE", "EG": "Egypt", "NG": "Nigeria",
    "PL": "Poland", "CZ": "Czech Republic", "HU": "Hungary", "RO": "Romania",
    "KZ": "Kazakhstan", "BD": "Bangladesh", "LK": "Sri Lanka",
    # EU member states
    "DE": "Germany", "FR": "France", "IT": "Italy", "ES": "Spain",
    "NL": "Netherlands", "FI": "Finland",
    # Other
    "BM": "Bermuda", "WW": "Worldwide",
}


def main() -> int:
    settings = get_settings()
    configure_logging(settings)

    config = load_markets()
    connector = MSSQLConnector(settings)

    try:
        with Session(connector.engine) as session:
            markets_upserted = 0
            currencies_upserted = 0

            for code, market in config.markets.items():
                name = _MARKET_NAMES.get(code, code)
                weekend_str = ",".join(str(d) for d in market.weekend_days)

                th = market.trading_hours
                trading_open = th.open if th else None
                trading_close = th.close if th else None
                lunch_start = th.lunch_start if th else None
                lunch_end = th.lunch_end if th else None

                # Upsert dim_market
                existing = session.execute(
                    text("SELECT market_code FROM [calendar].[dim_market] WHERE market_code = :code"),
                    {"code": code},
                ).fetchone()

                if existing:
                    session.execute(
                        text("""
                            UPDATE [calendar].[dim_market]
                            SET market_name = :name, timezone = :tz,
                                country_code_iso = :iso, weekend_days = :wd,
                                trading_open = :to_, trading_close = :tc,
                                lunch_start = :ls, lunch_end = :le,
                                updated_at = SYSDATETIMEOFFSET()
                            WHERE market_code = :code
                        """),
                        {
                            "code": code, "name": name, "tz": market.timezone,
                            "iso": market.country_code, "wd": weekend_str,
                            "to_": trading_open, "tc": trading_close,
                            "ls": lunch_start, "le": lunch_end,
                        },
                    )
                else:
                    session.execute(
                        text("""
                            INSERT INTO [calendar].[dim_market]
                                (market_code, market_name, timezone, country_code_iso,
                                 weekend_days, trading_open, trading_close, lunch_start, lunch_end)
                            VALUES
                                (:code, :name, :tz, :iso, :wd, :to_, :tc, :ls, :le)
                        """),
                        {
                            "code": code, "name": name, "tz": market.timezone,
                            "iso": market.country_code, "wd": weekend_str,
                            "to_": trading_open, "tc": trading_close,
                            "ls": lunch_start, "le": lunch_end,
                        },
                    )
                markets_upserted += 1

                # Upsert dim_market_currency for each currency
                for ccy in market.currencies:
                    existing_ccy = session.execute(
                        text("""
                            SELECT market_code FROM [calendar].[dim_market_currency]
                            WHERE market_code = :code AND ccy = :ccy
                        """),
                        {"code": code, "ccy": ccy},
                    ).fetchone()

                    if not existing_ccy:
                        session.execute(
                            text("""
                                INSERT INTO [calendar].[dim_market_currency]
                                    (market_code, ccy, is_primary)
                                VALUES (:code, :ccy, 1)
                            """),
                            {"code": code, "ccy": ccy},
                        )
                        currencies_upserted += 1

            session.commit()

        log.info(
            "seed_complete",
            markets=markets_upserted,
            currencies=currencies_upserted,
        )
        print(f"Seed complete: {markets_upserted} markets, {currencies_upserted} currencies")
        return 0

    except Exception:
        log.exception("seed_failed")
        return 1
    finally:
        connector.dispose()


if __name__ == "__main__":
    sys.exit(main())
