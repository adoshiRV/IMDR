"""BI Indonesia Balance of Payments fetcher (SEKI Table V.1).

Quarterly BoP summary in BPM6 framework. Unit: Juta USD. Wide format.
Cell mapping: 3.2 Current Account + 3.3 Capital/Financial Account.
"""

from __future__ import annotations

import datetime

from imdr.domains.econ.bi_seki import download_seki, parse_seki_wide_sheet
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc

_TARGETS: list[tuple[int, str, str]] = [
    (1,  "BI.BOP.CA.TOTAL.USD.ID",
     "Indonesia Current Account total (BI SEKI V.1, USD million, BPM6)"),
    (2,  "BI.BOP.CA.GOODS.USD.ID",
     "Indonesia Current Account — Goods balance (BI SEKI V.1, USD million)"),
    (17, "BI.BOP.CA.SERVICES.USD.ID",
     "Indonesia Current Account — Services balance (BI SEKI V.1, USD million)"),
    (20, "BI.BOP.CA.PRIM_INCOME.USD.ID",
     "Indonesia Current Account — Primary Income (BI SEKI V.1, USD million)"),
    (23, "BI.BOP.CA.SEC_INCOME.USD.ID",
     "Indonesia Current Account — Secondary Income (BI SEKI V.1, USD million)"),
    (26, "BI.BOP.CAPITAL.USD.ID",
     "Indonesia Capital Account (BI SEKI V.1, USD million, BPM6)"),
    (29, "BI.BOP.FA.TOTAL.USD.ID",
     "Indonesia Financial Account total (BI SEKI V.1, USD million, BPM6)"),
    (32, "BI.BOP.FA.DI.USD.ID",
     "Indonesia Financial Account — Direct Investment net (BI SEKI V.1, USD million)"),
    (35, "BI.BOP.FA.PI.USD.ID",
     "Indonesia Financial Account — Portfolio Investment net (BI SEKI V.1, USD million)"),
    (40, "BI.BOP.FA.DERIV.USD.ID",
     "Indonesia Financial Account — Financial Derivatives net (BI SEKI V.1, USD million)"),
    (41, "BI.BOP.FA.OI.USD.ID",
     "Indonesia Financial Account — Other Investment net (BI SEKI V.1, USD million)"),
    (47, "BI.BOP.ERR_OMISSIONS.USD.ID",
     "Indonesia Balance of Payments — Net Errors & Omissions (BI SEKI V.1, USD million)"),
    (48, "BI.BOP.OVERALL.USD.ID",
     "Indonesia Balance of Payments — Overall Balance (BI SEKI V.1, USD million)"),
]


def run_fetch(since, until):
    since_dt = datetime.date.fromisoformat(since) if since else None
    until_dt = datetime.date.fromisoformat(until) if until else None
    now = datetime.datetime.now(UTC)

    print("  downloading TABEL5_1.xls ...", end=" ", flush=True)
    path = download_seki("TABEL5_1")
    print(path.name)
    parsed = parse_seki_wide_sheet(
        path, sheet="5.1",
        year_row=4, month_row=5, data_start_row=6,
    )
    print(f"  parsed {len(parsed)} line items")

    indicators: list[IndicatorRow] = []
    observations: list[ObservationRow] = []
    for line_no, imdr_code, display in _TARGETS:
        series = parsed.get(line_no)
        if not series:
            print(f"    {imdr_code}: line {line_no} missing — skipping")
            continue
        indicator = IndicatorRow(
            imdr_code=imdr_code, vendor_name="BI",
            source_code=f"BI/SEKI/TABEL5_1/sheet=5.1/line={line_no}",
            display_name=display, unit="usd_mn", frequency="QUARTERLY",
            country_iso="ID", category="bop",
            is_seasonally_adjusted=False, bbg_ticker=None,
        )
        obs_emitted = 0
        for obs_date, value, _label in series:
            if since_dt and obs_date < since_dt:
                continue
            if until_dt and obs_date > until_dt:
                continue
            observations.append(ObservationRow(
                imdr_code=imdr_code, obs_date=obs_date, vintage=0,
                release_date=now, value=value, ingested_at=now,
            ))
            obs_emitted += 1
        indicators.append(indicator)
        print(f"    {imdr_code}: {obs_emitted} obs")
    return indicators, observations


def main() -> int:
    return run_main(vendor="bi", topic="bop",
                    fetch_fn=run_fetch,
                    description=__doc__.splitlines()[0] if __doc__ else "")

if __name__ == "__main__":
    import sys; sys.exit(main())
