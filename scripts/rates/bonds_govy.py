"""Runner: Track B Govy Monitor -> rates.fact_bond_instrument_obs + rates.fact_bond_auction.

Reads a read-only copy of the Govy Monitor SQLite store (never the live
file), seeds ``dbo.dim_bond_instrument`` from the distinct ISINs, and
upserts per-bond yield/ASW observations + the auction calendar.

Registered in ``scripts/imdr_daily.py`` (2026-10-12). The Govy desktop app
refreshes its store on its own cadence, so a day where it was closed simply
re-upserts the same rows — the MERGE makes re-runs free.

Usage:
    python -m scripts.rates.bonds_govy --no-load
    python -m scripts.rates.bonds_govy --countries IGB,KTB --no-load
    python -m scripts.rates.bonds_govy --db path\\to\\existing_copy.db --no-load
    python -m scripts.rates.bonds_govy                 # real load
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from imdr.config.settings import Settings
from imdr.connectors.mssql import MSSQLConnector
from imdr.domains.rates.govy_bonds import (
    DEFAULT_AUCTION_COUNTRIES,
    DEFAULT_COUNTRIES,
    GovyBondsPipeline,
)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--countries", default=",".join(DEFAULT_COUNTRIES),
        help="comma-separated Govy bond-issuer codes, e.g. IGB,KTB",
    )
    ap.add_argument(
        "--auction-countries", default=",".join(DEFAULT_AUCTION_COUNTRIES),
        help=(
            "comma-separated auction_calendar country codes. Separate namespace "
            "from --countries (issuer codes AND ISO sovereign codes)."
        ),
    )
    ap.add_argument(
        "--no-load", action="store_true",
        help="extract + validate only; never seeds or upserts (no writes to IMDR)",
    )
    ap.add_argument(
        "--db", type=Path, default=None,
        help="use an existing SQLite copy instead of copying the live Govy DB",
    )
    args = ap.parse_args()

    countries = [c.strip() for c in args.countries.split(",") if c.strip()]
    auction_countries = [c.strip() for c in args.auction_countries.split(",") if c.strip()]

    settings = Settings()
    connector = MSSQLConnector(settings)
    pipeline = GovyBondsPipeline(
        connector=connector,
        countries=countries,
        db_path=args.db,
        auction_countries=auction_countries,
    )

    report = pipeline.run(no_load=args.no_load)
    print(json.dumps(report, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
