"""ABS Terms of Trade — derived from ITPI export/import headline ratio.

Closes wiring-map cell 3.1 (Terms of Trade). The ITPI dataflows publish
export and import price indices separately (`ABS.ITPI.EXPORT_HEADLINE_INDEX.AU`
+ `ABS.ITPI.IMPORT_HEADLINE_INDEX.AU`); the Terms of Trade is their ratio
× 100. ABS publishes a primary ToT series elsewhere but its discovery
requires another dataflow probe — this derived series uses what's already
in DB and matches the official ABS ToT definition (Net Barter ToT).

Identity: `TOT = (ITPI export price index / ITPI import price index) × 100`.

Quarterly since 1974 Q3 (the bounded window where both inputs exist).
Read both series from `econ.fact_indicator`, compute the ratio for every
date where BOTH have a value, emit one quarterly indicator.
"""
from __future__ import annotations

import sys
from datetime import datetime

from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

_EXPORT_CODE = "ABS.ITPI.EXPORT_HEADLINE_INDEX.AU"
_IMPORT_CODE = "ABS.ITPI.IMPORT_HEADLINE_INDEX.AU"
_DERIVED_CODE = "ABS.TOT.NET_BARTER.AU"


def _pull_series(engine, imdr_code: str) -> dict:
    """Return {obs_date: value}. Float casts; NULLs dropped."""
    from sqlalchemy import text
    rows = {}
    with engine.connect() as conn:
        for r in conn.execute(text(
            "SELECT f.obs_date, f.value FROM econ.fact_indicator f "
            "JOIN econ.dim_indicator i ON i.id = f.indicator_id "
            "WHERE i.imdr_code = :c AND f.value IS NOT NULL "
            "ORDER BY f.obs_date"
        ), {"c": imdr_code}):
            rows[r.obs_date] = float(r.value)
    return rows


def run_fetch(since: str | None, until: str | None) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    from sqlalchemy import create_engine
    from imdr.config.settings import get_settings

    s = get_settings()
    url = (
        f"mssql+pyodbc://@{s.mssql_host}:{s.mssql_port}/{s.mssql_database}"
        f"?driver={s.mssql_driver}&Trusted_Connection=yes"
    )
    engine = create_engine(url, pool_pre_ping=True)

    print(f"  pulling {_EXPORT_CODE} ...")
    exp = _pull_series(engine, _EXPORT_CODE)
    print(f"  pulling {_IMPORT_CODE} ...")
    imp = _pull_series(engine, _IMPORT_CODE)
    common = sorted(set(exp) & set(imp))
    print(f"  matched dates: {len(common)}  ({common[0]} -> {common[-1]})")

    now = datetime.now()
    indicator = IndicatorRow(
        imdr_code=_DERIVED_CODE,
        vendor_name="ABS",
        source_code=f"ABS.TOT.NET_BARTER (derived: {_EXPORT_CODE} / {_IMPORT_CODE} × 100)",
        display_name="ABS Terms of Trade — Net Barter (derived from ITPI export/import ratio × 100)",
        unit="index",
        frequency="QUARTERLY",
        country_iso="AU",
        category="bop",
        is_seasonally_adjusted=False,
    )
    observations = [
        ObservationRow(
            imdr_code=_DERIVED_CODE,
            obs_date=d,
            vintage=0,
            release_date=now,
            value=(exp[d] / imp[d]) * 100.0,
            ingested_at=now,
        )
        for d in common
    ]
    if observations:
        print(f"  {_DERIVED_CODE:<35s} {len(observations):>5} obs  "
              f"latest={observations[-1].obs_date}={observations[-1].value:.2f}")
    return [indicator], observations


def main() -> int:
    return run_main(vendor="abs", topic="tot", fetch_fn=run_fetch,
                    description=__doc__.splitlines()[0] if __doc__ else "",
                    country_code="AU")


if __name__ == "__main__":
    sys.exit(main())
