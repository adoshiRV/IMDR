"""Seed [rates].[dim_curve] from universe/rates.yml.

Usage:
    python -m scripts.migrations.seed_rates_dim_curve

Reads all 39 curve entries from rates.yml and inserts any missing rows
into the dim_curve table. Safe to run repeatedly — skips existing rows.
"""
from __future__ import annotations

from imdr.config.settings import get_settings
from imdr.connectors.mssql import MSSQLConnector
from imdr.domains.rates.repository import RatesCurveRepository
from imdr.schemas.rates import RatesCurveCreate
from imdr.universe.rates import get_rates_universe


def main() -> None:
    settings = get_settings()
    connector = MSSQLConnector(settings)
    universe = get_rates_universe()

    curves_to_seed: list[RatesCurveCreate] = []
    for entry in universe.all_curves():
        citi = entry.providers.get("citi", {})
        curves_to_seed.append(
            RatesCurveCreate(
                ccy=entry.ccy,
                curve=entry.curve,
                curve_type=entry.type,
                curve_status=entry.status,
                instrument=citi.get("instrument", ""),
                citi_prefix=citi.get("prefix", ""),
                cessation_date=entry.cessation,
                primary_from=entry.primary_from,
                supersedes=entry.supersedes,
                superseded_by=entry.superseded_by,
                notes=entry.notes,
            )
        )

    try:
        with connector.session() as session:
            repo = RatesCurveRepository(session)
            inserted = repo.bulk_seed_from_universe(curves_to_seed)
            print(f"Seeded {inserted} new curves ({len(curves_to_seed)} total in universe)")
    finally:
        connector.dispose()


if __name__ == "__main__":
    main()
