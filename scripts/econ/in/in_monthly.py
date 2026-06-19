"""India econ — MONTHLY orchestrator.

Runs ALL India fetchers in sequence — monthly, weekly, daily AND the
quarterly/annual ones (MOSPI NAS GDP, UPAG MSP & AIAPY), which were folded
in here on 2026-06-19 rather than kept on a separate quarterly trigger.
Fetchers are idempotent (MERGE on PK), so pulling quarterly/annual data
every month is harmless — it just catches each release in the first
monthly run after it lands.

Pipeline order: fast plain-HTTP fetchers first, then heavier scrapers, with
rbi_bulletin LAST — it requires a headed Chrome session (TSPD anti-bot) and
is the slowest fetcher. This orchestrator must run on a host with a display
(or a virtual framebuffer) for rbi_bulletin to succeed.

Wired into scripts/imdr_monthly.py.
"""

from __future__ import annotations

import sys

from scripts.econ._country_runner import run


PIPELINES: list[list[str]] = [
    # BIS SDMX (smallest, fastest, no auth)
    [sys.executable, "-m", "scripts.econ.in.bis.bis_india"],
    # FAO Food Price Index (plain HTTP CSV download)
    [sys.executable, "-m", "scripts.econ.in.fao.fao_fpi"],
    # RBI DBIE (weekly FX reserves + key-rate snapshot)
    [sys.executable, "-m", "scripts.econ.in.rbi.rbi_fx_reserves"],
    [sys.executable, "-m", "scripts.econ.in.rbi.rbi_key_rates"],
    # MOSPI press-release scrapes (incl. quarterly/annual NAS GDP — folded in
    # here so the monthly run catches every release; idempotent MERGE)
    [sys.executable, "-m", "scripts.econ.in.mospi.mospi_cpi"],
    [sys.executable, "-m", "scripts.econ.in.mospi.mospi_iip"],
    [sys.executable, "-m", "scripts.econ.in.mospi.mospi_nas_gdp"],
    # DPIIT/OEA monthly indices
    [sys.executable, "-m", "scripts.econ.in.dpiit.dpiit_wpi"],
    [sys.executable, "-m", "scripts.econ.in.dpiit.dpiit_core_industries"],
    # CGA Centre fiscal accounts (DAMA dashboard XLSM)
    [sys.executable, "-m", "scripts.econ.in.cga.cga_monthly"],
    # DGCIS trade data
    [sys.executable, "-m", "scripts.econ.in.dgcis.dgcis_trade"],
    # UPAG agriculture — monthly mandi prices + quarterly/annual MSP & AIAPY
    # (folded in here; idempotent so over-pulling quarterly data is harmless)
    [sys.executable, "-m", "scripts.econ.in.upag.upag_imc"],
    [sys.executable, "-m", "scripts.econ.in.upag.upag_msp"],
    [sys.executable, "-m", "scripts.econ.in.upag.upag_aiapy"],
    # RBI Bulletin (headed Chrome, TSPD anti-bot — LAST, slowest)
    [sys.executable, "-m", "scripts.econ.in.rbi.rbi_bulletin"],
]


def main() -> int:
    return run(
        run_name="Monthly",
        country_code="IN",
        country_label="IN",
        country_name="India",
        orchestrator_path="scripts.econ.in.in_monthly",
        pipelines=PIPELINES,
        frequency_scope=["MONTHLY", "WEEKLY", "DAILY", "QUARTERLY", "ANNUAL"],
    )


if __name__ == "__main__":
    sys.exit(main())
