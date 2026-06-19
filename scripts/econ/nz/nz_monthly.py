"""New Zealand econ — MONTHLY+QUARTERLY orchestrator.

Runs all 13 Stats NZ prod fetchers. NZ has both monthly-cadence series
(ECT card transactions, OMT merchandise trade) and quarterly-cadence series
(CPI, GDP, BoP/IIP, PPI, CGPI, OTI, HLPI, LCI, QES, RTS, HLFS) folded
under one trigger. Fetchers are idempotent (MERGE on PK): running them
monthly costs extra Infoshare sessions but catches every release window
without per-cadence scheduling.

Release-CSV fetchers (CPI, GDP, BoP) run first — they are fast plain-HTTP
downloads. Infoshare fetchers (all others) follow; each launches a headless
Playwright browser session.

To wire into scripts/imdr_monthly.py:PIPELINES (pending explicit user sign-off).
"""

from __future__ import annotations

import sys

from scripts.econ._country_runner import run


PIPELINES: list[list[str]] = [
    # Release-CSV fetchers (fast, plain HTTP, no browser)
    [sys.executable, "-m", "scripts.econ.nz.statsnz.statsnz_cpi"],
    [sys.executable, "-m", "scripts.econ.nz.statsnz.statsnz_gdp"],
    [sys.executable, "-m", "scripts.econ.nz.statsnz.statsnz_bop"],
    # Infoshare fetchers (headless Playwright, sequential)
    [sys.executable, "-m", "scripts.econ.nz.statsnz.statsnz_ppi"],
    [sys.executable, "-m", "scripts.econ.nz.statsnz.statsnz_cgpi"],
    [sys.executable, "-m", "scripts.econ.nz.statsnz.statsnz_oti"],
    [sys.executable, "-m", "scripts.econ.nz.statsnz.statsnz_hlpi"],
    [sys.executable, "-m", "scripts.econ.nz.statsnz.statsnz_lci"],
    [sys.executable, "-m", "scripts.econ.nz.statsnz.statsnz_qes"],
    [sys.executable, "-m", "scripts.econ.nz.statsnz.statsnz_ect"],
    [sys.executable, "-m", "scripts.econ.nz.statsnz.statsnz_omt"],
    [sys.executable, "-m", "scripts.econ.nz.statsnz.statsnz_rts"],
    [sys.executable, "-m", "scripts.econ.nz.statsnz.statsnz_hlf"],
]


def main() -> int:
    return run(
        run_name="Monthly",
        country_code="NZ",
        country_label="NZ",
        country_name="New Zealand",
        orchestrator_path="scripts.econ.nz.nz_monthly",
        pipelines=PIPELINES,
        frequency_scope=["MONTHLY", "QUARTERLY"],
    )


if __name__ == "__main__":
    sys.exit(main())
