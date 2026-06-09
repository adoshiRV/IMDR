"""Seed dbo.dim_country from countries.yml.

Idempotent INSERT of missing countries — does NOT overwrite existing rows.

Rationale: ``dbo.dim_country`` is the source of truth post country-anchor
restructure (migrations 037–038 populated the initial 52 rows). This script
exists for **future** country additions: append a new entry to
``src/imdr/market_calendar/countries.yml`` and run this script to materialize
the dim_country row.

Why INSERT-only (no UPDATE on conflict):

* ``dim_country.weekend_days``, ``timezone``, and ``trading_hours`` are the
  runtime source of truth (see calendar_module.md Step 1 status). If an
  operator updates the DB directly to correct a typo, re-running this script
  should NOT clobber that change with the YAML's stale value.
* If the YAML and DB diverge in a way that matters, the right move is to
  reconcile manually rather than have a script silently pick a winner.

For pseudo-country detection: ``EU``, ``WW``, ``XX`` are flagged
``is_pseudo=1`` with ``iso_alpha3 = NULL``; everything else has
``is_pseudo=0`` and falls back to the country_code itself for ``iso_alpha3``
when not in the explicit override map.

Usage:
    python -m scripts.calendar.seed_dim_country
    python -m scripts.calendar.seed_dim_country --dry-run
"""

from __future__ import annotations

import argparse
import sys

import structlog
from sqlalchemy import text
from sqlalchemy.orm import Session

from imdr.config.settings import get_settings
from imdr.connectors.mssql import MSSQLConnector
from imdr.market_calendar.countries import load_countries
from imdr.utils.logging import configure_logging

log = structlog.get_logger(__name__)

# Display names — pulled forward from the legacy seed_dim_market script.
_DISPLAY_NAMES: dict[str, str] = {
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
    "BM": "Bermuda", "WW": "Worldwide", "XX": "Non-sovereign / metals",
}

# ISO alpha-3 overrides where alpha-2 ≠ alpha-3 prefix or our canonical
# country_code differs from ISO alpha-2 (e.g. UK → GBR).
_ISO_ALPHA3: dict[str, str] = {
    "UK": "GBR",  # our code is UK; ISO is GB → GBR
    "AE": "ARE", "AR": "ARG", "AT": "AUT", "AU": "AUS",
    "BD": "BGD", "BM": "BMU", "BR": "BRA",
    "CA": "CAN", "CH": "CHE", "CL": "CHL", "CN": "CHN", "CO": "COL",
    "CZ": "CZE", "DE": "DEU", "DK": "DNK", "EG": "EGY", "ES": "ESP",
    "FI": "FIN", "FR": "FRA", "HK": "HKG", "HU": "HUN",
    "ID": "IDN", "IL": "ISR", "IN": "IND", "IT": "ITA",
    "JP": "JPN", "KR": "KOR", "KZ": "KAZ", "LK": "LKA",
    "MX": "MEX", "MY": "MYS", "NG": "NGA", "NL": "NLD", "NO": "NOR",
    "NZ": "NZL", "PE": "PER", "PH": "PHL", "PL": "POL",
    "RO": "ROU", "RU": "RUS", "SA": "SAU", "SE": "SWE", "SG": "SGP",
    "TH": "THA", "TR": "TUR", "TW": "TWN", "US": "USA", "VN": "VNM",
    "ZA": "ZAF",
}

_PSEUDO_CODES: frozenset[str] = frozenset({"EU", "WW", "XX"})


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed dbo.dim_country from countries.yml")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings)

    config = load_countries()
    connector = MSSQLConnector(settings)

    try:
        with Session(connector.engine) as session:
            existing_codes = {
                row[0] for row in session.execute(
                    text("SELECT country_code FROM dbo.dim_country"),
                ).fetchall()
            }

            to_insert: list[dict[str, object]] = []
            for code, country in config.countries.items():
                if code in existing_codes:
                    continue
                is_pseudo = code in _PSEUDO_CODES
                iso_alpha3 = None if is_pseudo else _ISO_ALPHA3.get(code)
                if not is_pseudo and iso_alpha3 is None:
                    log.warning(
                        "no_iso_alpha3_mapping",
                        country_code=code,
                        hint="Add to _ISO_ALPHA3 in seed_dim_country.py",
                    )

                th = country.trading_hours
                to_insert.append({
                    "code": code,
                    "iso": iso_alpha3,
                    "name": _DISPLAY_NAMES.get(code, code),
                    "pseudo": 1 if is_pseudo else 0,
                    "tz": None if is_pseudo else country.timezone,
                    "wd": None if is_pseudo else ",".join(
                        str(d) for d in country.weekend_days
                    ),
                    "to_": th.open if th and not is_pseudo else None,
                    "tc": th.close if th and not is_pseudo else None,
                    "ls": th.lunch_start if th and not is_pseudo else None,
                    "le": th.lunch_end if th and not is_pseudo else None,
                })

            if not to_insert:
                print(f"No new countries to insert; {len(existing_codes)} already present.")
                return 0

            print(f"{len(to_insert)} new country/countries to insert:")
            for row in to_insert:
                print(f"  {row['code']:>3}  {row['name']}  (pseudo={bool(row['pseudo'])})")

            if args.dry_run:
                print("\n[DRY RUN] No writes performed.")
                return 0

            for row in to_insert:
                session.execute(
                    text("""
                        INSERT INTO dbo.dim_country
                            (country_code, iso_alpha3, display_name, is_pseudo,
                             timezone, weekend_days,
                             trading_open, trading_close, lunch_start, lunch_end,
                             is_active)
                        VALUES
                            (:code, :iso, :name, :pseudo,
                             :tz, :wd, :to_, :tc, :ls, :le, 1)
                    """),
                    row,
                )
                log.info("country_inserted", country_code=row["code"])

            session.commit()
            print(f"Seed complete: {len(to_insert)} country/countries inserted.")
            return 0

    except Exception:
        log.exception("seed_failed")
        return 1
    finally:
        connector.dispose()


if __name__ == "__main__":
    sys.exit(main())
