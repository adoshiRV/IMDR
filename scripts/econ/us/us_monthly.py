"""United States econ — MONTHLY orchestrator.

Runs the US Tier-1 source-agency fetchers that publish at monthly / quarterly
cadence (BLS · BEA · Census · Treasury MTS). Daily-cadence series (EIA energy
spot, Treasury Debt-to-the-Penny) live in ``us_daily.py`` for 24h latency;
they are NOT duplicated here.

Fetchers are idempotent (loader MERGE on PK), so a monthly run that re-pulls a
quarterly release (BEA GDP/ITA/IIP) is harmless — it just catches each release
in the first monthly run after it lands.

NOTE: the US-specific FRED series ARE promoted here (fred_us_monthly, seed_us.yml
— the curated active US set). Only the cross-country OECD *mirror* (non-US series)
stays in playground/econ/fred/. The source agencies remain the authoritative
publishers for the headline concepts (see ``us_coverage_plan.md`` source-of-truth
policy + migration 106 — the 26 FRED dupes stay deactivated).

PROD-LIVE: wired into ``scripts/imdr_monthly.py:PIPELINES`` 2026-06-23.
"""

from __future__ import annotations

import sys

from scripts.econ._country_runner import run


PIPELINES: list[list[str]] = [
    # BLS — CPI / PPI / employment / ECI+JOLTS / import-export prices
    [sys.executable, "-m", "scripts.econ.us.bls.bls_cpi"],
    [sys.executable, "-m", "scripts.econ.us.bls.bls_ppi"],
    [sys.executable, "-m", "scripts.econ.us.bls.bls_employment_situation"],
    [sys.executable, "-m", "scripts.econ.us.bls.bls_eci_jolts"],
    [sys.executable, "-m", "scripts.econ.us.bls.bls_import_export_prices"],
    # BEA — GDP/NIPA · personal income/PCE · ITA (BoP) · IIP
    [sys.executable, "-m", "scripts.econ.us.bea.bea_gdp"],
    [sys.executable, "-m", "scripts.econ.us.bea.bea_personal_income"],
    [sys.executable, "-m", "scripts.econ.us.bea.bea_ita"],
    [sys.executable, "-m", "scripts.econ.us.bea.bea_iip"],
    # Census — MARTS retail · FT-900 trade · residential construction
    [sys.executable, "-m", "scripts.econ.us.census.census_retail"],
    [sys.executable, "-m", "scripts.econ.us.census.census_trade"],
    [sys.executable, "-m", "scripts.econ.us.census.census_housing"],
    # Treasury — Monthly Treasury Statement (fiscal)
    [sys.executable, "-m", "scripts.econ.us.treasury.treasury_mts"],
    # FRED — US-specific monthly/quarterly/annual series (GDPNow, INDPRO, sticky
    # CPI, Case-Shiller, Z.1, regional-Fed surveys, CFNAI, …; seed_us.yml)
    [sys.executable, "-m", "scripts.econ.us.fred.fred_us_monthly"],
    # BIS — US NEER/REER broad basket (cell 3.4 FX/REER)
    [sys.executable, "-m", "scripts.econ.us.bis.bis_us"],
]


def main() -> int:
    return run(
        run_name="Monthly",
        country_code="US",
        country_label="US",
        country_name="United States",
        orchestrator_path="scripts.econ.us.us_monthly",
        pipelines=PIPELINES,
        frequency_scope=["MONTHLY", "QUARTERLY", "ANNUAL"],
    )


if __name__ == "__main__":
    sys.exit(main())
