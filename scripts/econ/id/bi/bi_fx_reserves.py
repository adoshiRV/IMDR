"""BI Indonesia FX Reserves fetcher (SEKI Table V.9).

Position of FX reserves by asset class. Monthly, 2010-present. Unit: Juta USD.
Cell mapping: 3.4 FX/REER (reserves stock + composition) + 4.4 Policy Reaction.
"""

from __future__ import annotations

import datetime

from imdr.domains.econ.bi_seki import download_seki, parse_seki_wide_sheet
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc

_TARGETS: list[tuple[int, str, str]] = [
    (8, "BI.RESERVES.TOTAL.USD.ID",
     "Indonesia FX Reserves — total (BI SEKI V.9, USD million)"),
    (1, "BI.RESERVES.GOLD.USD.ID",
     "Indonesia FX Reserves — Monetary Gold (BI SEKI V.9, USD million)"),
    (2, "BI.RESERVES.SDR.USD.ID",
     "Indonesia FX Reserves — Special Drawing Rights (BI SEKI V.9, USD million)"),
    (3, "BI.RESERVES.IMF_RPF.USD.ID",
     "Indonesia FX Reserves — Reserve Position in IMF (BI SEKI V.9, USD million)"),
    (5, "BI.RESERVES.CURRENCY_DEPOSITS.USD.ID",
     "Indonesia FX Reserves — Foreign Currency & Deposits (BI SEKI V.9, USD million)"),
    (6, "BI.RESERVES.SECURITIES.USD.ID",
     "Indonesia FX Reserves — Foreign Securities (BI SEKI V.9, USD million)"),
]


def run_fetch(since, until):
    since_dt = datetime.date.fromisoformat(since) if since else None
    until_dt = datetime.date.fromisoformat(until) if until else None
    now = datetime.datetime.now(UTC)

    print("  downloading TABEL5_9.xls ...", end=" ", flush=True)
    path = download_seki("TABEL5_9")
    print(path.name)
    parsed = parse_seki_wide_sheet(
        path, sheet="5.9",
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
            source_code=f"BI/SEKI/TABEL5_9/sheet=5.9/line={line_no}",
            display_name=display, unit="usd_mn", frequency="MONTHLY",
            country_iso="ID", category="cb_balance_sheet",
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
    return run_main(vendor="bi", topic="fx_reserves",
                    fetch_fn=run_fetch,
                    description=__doc__.splitlines()[0] if __doc__ else "",
                    country_code="ID")

if __name__ == "__main__":
    import sys; sys.exit(main())
