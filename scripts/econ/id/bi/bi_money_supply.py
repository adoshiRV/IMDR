"""BI Indonesia Money Supply fetcher (SEKI Table I.1).

M2 (Broad Money), M1, Currency in Circulation, Demand Deposits, Quasi Money.
Monthly, 2010-present in current sheet. Unit: Milyar Rp.
Cell mapping: 4.4 Policy Reaction (M1 + M2 monetary aggregates).
"""

from __future__ import annotations

import datetime

from imdr.domains.econ.bi_seki import download_seki, parse_seki_wide_sheet
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc

_TARGETS: list[tuple[int, str, str]] = [
    (1, "BI.M2.LEVEL.ID",
     "Indonesia Broad Money (M2), Milyar Rp (BI SEKI I.1)"),
    (2, "BI.M1.LEVEL.ID",
     "Indonesia Narrow Money (M1), Milyar Rp (BI SEKI I.1)"),
    (3, "BI.CURRENCY.LEVEL.ID",
     "Indonesia Currency in Circulation outside banks, Milyar Rp (BI SEKI I.1)"),
    (4, "BI.DEMAND_DEPOSITS.LEVEL.ID",
     "Indonesia Rupiah Demand Deposits, Milyar Rp (BI SEKI I.1)"),
    (6, "BI.QUASI_MONEY.LEVEL.ID",
     "Indonesia Quasi Money (savings + time deposits), Milyar Rp (BI SEKI I.1)"),
]


def run_fetch(since, until):
    since_dt = datetime.date.fromisoformat(since) if since else None
    until_dt = datetime.date.fromisoformat(until) if until else None
    now = datetime.datetime.now(UTC)

    print("  downloading TABEL1_1.xls ...", end=" ", flush=True)
    path = download_seki("TABEL1_1")
    print(f"{path.name}")
    print("  parsing sheet 'I.1' ...")
    parsed = parse_seki_wide_sheet(path, sheet="I.1")
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
            source_code=f"BI/SEKI/TABEL1_1/sheet=I.1/line={line_no}",
            display_name=display, unit="idr_bn", frequency="MONTHLY",
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
    return run_main(vendor="bi", topic="money_supply",
                    fetch_fn=run_fetch,
                    description=__doc__.splitlines()[0] if __doc__ else "",
                    country_code="ID")

if __name__ == "__main__":
    import sys; sys.exit(main())
