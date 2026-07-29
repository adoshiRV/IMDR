"""BBG EconDashboards ingest -- ALL APAC+US markets from one SQLite.

The EconDashboards Bloomberg cache is a SINGLE SQLite that the dashboard app
refreshes ATOMICALLY for all 14 markets at once, so the ingest matches that
grain: one run mirrors every country. There is no per-country cadence to model,
so this deliberately does NOT fan out into one fetcher per country -- the
country-agnostic logic lives in ``imdr.domains.econ.bbg_econdashboard`` and
splitting into thin per-country wrappers later is mechanical if a per-country
orchestrator ever needs it.

Country-first is still honoured on disk: each market's (dim, fact) parquet pair
is written under ``data/econ/{cc}/bbg/econdashboard/{Y}/{M}/{D}/`` via
``_runner.write_parquet`` and loaded through the canonical revision-aware loader
(``scripts.migrations.load_econ_indicator_from_playground``) with explicit
paths.

Usage:
    python -m scripts.econ.bbg.econdashboard                 # all countries, load
    python -m scripts.econ.bbg.econdashboard --no-load       # write parquet only
    python -m scripts.econ.bbg.econdashboard --no-parquet    # counts only
    python -m scripts.econ.bbg.econdashboard --country KR    # one market
    python -m scripts.econ.bbg.econdashboard --since 2024-01-01
"""

from __future__ import annotations

import argparse
import contextlib
import io
import sys

from imdr.domains.econ.bbg_econdashboard import VENDOR_NAME, fetch_econdashboard
from scripts.econ._runner import invoke_loader, write_parquet

TOPIC = "econdashboard"

# The 14 markets the EconDashboards catalog covers.
COUNTRIES = [
    "AU", "CN", "HK", "ID", "IN", "JP", "KR",
    "MY", "NZ", "PH", "SG", "TH", "TW", "US",
]


def _ingest_country(cc: str, since: str | None, until: str | None,
                    no_parquet: bool, no_load: bool) -> int:
    indicators, observations = fetch_econdashboard(cc, since, until)
    print(f"\n[{cc}] {len(indicators)} indicators, {len(observations)} observations")
    if not observations:
        print(f"[{cc}] no observations -- skipped.")
        return 0
    if no_parquet:
        return 0
    dim_path, fact_path = write_parquet(cc, VENDOR_NAME, TOPIC, indicators, observations)
    print(f"[{cc}] wrote {dim_path.name} / {fact_path.name}")
    if no_load:
        return 0
    return invoke_loader(VENDOR_NAME, dim_path, fact_path)


def main() -> int:
    # UTF-8 stdout for non-ASCII display names (mirrors _runner.run_main).
    if not isinstance(sys.stdout, io.TextIOWrapper) or sys.stdout.encoding.lower() != "utf-8":
        with contextlib.suppress(AttributeError, ValueError):
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    p = argparse.ArgumentParser(description="BBG EconDashboards ingest (all markets)")
    p.add_argument("--since", help="Earliest obs_date, YYYY-MM-DD.")
    p.add_argument("--until", help="Latest obs_date, YYYY-MM-DD.")
    p.add_argument("--country", help="Limit to one 2-letter market (default: all 14).")
    p.add_argument("--no-parquet", action="store_true", help="Counts only; no write/load.")
    p.add_argument("--no-load", action="store_true", help="Write parquet but skip DB load.")
    args = p.parse_args()

    countries = [args.country.upper()] if args.country else COUNTRIES
    worst_rc = 0
    for cc in countries:
        rc = _ingest_country(cc, args.since, args.until, args.no_parquet, args.no_load)
        if rc != 0:
            print(f"!! [{cc}] loader exited rc={rc}")
            worst_rc = rc
    print(f"\nDone -- {len(countries)} market(s), worst rc={worst_rc}")
    return worst_rc


if __name__ == "__main__":
    sys.exit(main())
