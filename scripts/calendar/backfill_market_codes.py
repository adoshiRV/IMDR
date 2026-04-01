"""Backfill market_code on domain dimension tables + add FK constraints.

Populates market_code from ccy using calendar.dim_market_currency bridge table,
then adds FK constraints.

Usage:
    python -m scripts.calendar.backfill_market_codes
    python -m scripts.calendar.backfill_market_codes --dry-run
"""

from __future__ import annotations

import argparse
import sys

import structlog
from sqlalchemy import text
from sqlalchemy.orm import Session

from imdr.config.settings import get_settings
from imdr.connectors.mssql import MSSQLConnector
from imdr.utils.logging import configure_logging

log = structlog.get_logger(__name__)


def backfill_fx_pairs(session: Session, dry_run: bool) -> int:
    """Backfill fx.dim_currency_pair.market_code from non-USD leg."""
    rows = session.execute(
        text("""
            SELECT p.id, p.base_ccy, p.quote_ccy
            FROM [fx].[dim_currency_pair] p
            WHERE p.market_code IS NULL
        """),
    ).fetchall()

    updated = 0
    for row in rows:
        pair_id, base_ccy, quote_ccy = row[0], row[1], row[2]
        # Non-USD leg determines the market
        ccy = base_ccy if base_ccy != "USD" else quote_ccy

        market = session.execute(
            text("""
                SELECT market_code FROM [calendar].[dim_market_currency]
                WHERE ccy = :ccy AND is_primary = 1
            """),
            {"ccy": ccy},
        ).fetchone()

        if market:
            if not dry_run:
                session.execute(
                    text("UPDATE [fx].[dim_currency_pair] SET market_code = :mc WHERE id = :id"),
                    {"mc": market[0], "id": pair_id},
                )
            log.info("fx_pair_backfill", pair=f"{base_ccy}/{quote_ccy}", market=market[0])
            updated += 1
        else:
            log.warning("fx_pair_no_market", pair=f"{base_ccy}/{quote_ccy}", ccy=ccy)

    return updated


def backfill_rates_curves(session: Session, dry_run: bool) -> int:
    """Backfill rates.dim_curve.market_code from ccy."""
    rows = session.execute(
        text("""
            SELECT c.id, c.ccy
            FROM [rates].[dim_curve] c
            WHERE c.market_code IS NULL
        """),
    ).fetchall()

    updated = 0
    for row in rows:
        curve_id, ccy = row[0], row[1]

        market = session.execute(
            text("""
                SELECT market_code FROM [calendar].[dim_market_currency]
                WHERE ccy = :ccy AND is_primary = 1
            """),
            {"ccy": ccy},
        ).fetchone()

        if market:
            if not dry_run:
                session.execute(
                    text("UPDATE [rates].[dim_curve] SET market_code = :mc WHERE id = :id"),
                    {"mc": market[0], "id": curve_id},
                )
            updated += 1
        else:
            log.warning("rates_curve_no_market", ccy=ccy, id=curve_id)

    return updated


def backfill_rates_vol_surfaces(session: Session, dry_run: bool) -> int:
    """Backfill rates.dim_vol_surface.market_code from ccy."""
    rows = session.execute(
        text("""
            SELECT s.id, s.ccy
            FROM [rates].[dim_vol_surface] s
            WHERE s.market_code IS NULL
        """),
    ).fetchall()

    updated = 0
    for row in rows:
        surface_id, ccy = row[0], row[1]

        market = session.execute(
            text("""
                SELECT market_code FROM [calendar].[dim_market_currency]
                WHERE ccy = :ccy AND is_primary = 1
            """),
            {"ccy": ccy},
        ).fetchone()

        if market:
            if not dry_run:
                session.execute(
                    text("UPDATE [rates].[dim_vol_surface] SET market_code = :mc WHERE id = :id"),
                    {"mc": market[0], "id": surface_id},
                )
            updated += 1
        else:
            log.warning("rates_vol_no_market", ccy=ccy, id=surface_id)

    return updated


def add_fk_constraints(session: Session) -> None:
    """Add FK constraints after backfill."""
    constraints = [
        ("FK_fx_pair_market", "[fx].[dim_currency_pair]"),
        ("FK_rates_curve_market", "[rates].[dim_curve]"),
        ("FK_rates_vol_surface_market", "[rates].[dim_vol_surface]"),
        ("FK_cb_events_market", "[calendar].[cb_events]"),
    ]

    for fk_name, table in constraints:
        col = "country_code" if "cb_events" in table else "market_code"
        try:
            session.execute(text(f"""
                ALTER TABLE {table}
                ADD CONSTRAINT {fk_name}
                FOREIGN KEY ({col}) REFERENCES [calendar].[dim_market](market_code)
            """))
            log.info("fk_added", constraint=fk_name, table=table)
        except Exception as e:
            if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                log.info("fk_exists", constraint=fk_name)
            else:
                log.warning("fk_failed", constraint=fk_name, error=str(e))


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill market_code on domain dims")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-fks", action="store_true", help="Skip adding FK constraints")
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings)
    connector = MSSQLConnector(settings)

    try:
        with Session(connector.engine) as session:
            fx = backfill_fx_pairs(session, args.dry_run)
            curves = backfill_rates_curves(session, args.dry_run)
            surfaces = backfill_rates_vol_surfaces(session, args.dry_run)

            if not args.dry_run:
                session.commit()
                log.info("backfill_committed", fx_pairs=fx, curves=curves, surfaces=surfaces)

                if not args.skip_fks:
                    add_fk_constraints(session)
                    session.commit()
            else:
                print(f"Dry run: {fx} FX pairs, {curves} curves, {surfaces} surfaces would be updated")

        return 0
    except Exception:
        log.exception("backfill_failed")
        return 1
    finally:
        connector.dispose()


if __name__ == "__main__":
    sys.exit(main())
