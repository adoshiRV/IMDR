"""BI Indonesia external debt SULNI fetcher (SEKI Table VI.1).

SULNI — Indonesia external-debt position by sector. Quarterly, 2010-present.
Unit: Juta USD. Cell mapping: 3.3 Capital Account + 4.2 Balance Sheets.
"""

from __future__ import annotations

import datetime

from imdr.domains.econ.bi_seki import download_seki, parse_seki_wide_sheet
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc

_TARGETS: list[tuple[int, str, str]] = [
    (15, "BI.EXT_DEBT.TOTAL.USD.ID",
     "Indonesia total external debt (BI SULNI, USD million)"),
    (1,  "BI.EXT_DEBT.PUBLIC.USD.ID",
     "Indonesia public external debt (Govt + BI, BI SULNI, USD million)"),
    (3,  "BI.EXT_DEBT.GOVT_CENTRAL.USD.ID",
     "Indonesia central government external debt (BI SULNI, USD million)"),
    (4,  "BI.EXT_DEBT.MONETARY_AUTH.USD.ID",
     "Indonesia Bank Indonesia external debt (BI SULNI, USD million)"),
    (6,  "BI.EXT_DEBT.COMMERCIAL.USD.ID",
     "Indonesia commercial external debt (BI SULNI, USD million)"),
    (10, "BI.EXT_DEBT.PRIVATE.USD.ID",
     "Indonesia total private external debt (BI SULNI, USD million)"),
    (12, "BI.EXT_DEBT.PRIVATE_BANK.USD.ID",
     "Indonesia private external debt — banks (BI SULNI, USD million)"),
    (14, "BI.EXT_DEBT.PRIVATE_CORP.USD.ID",
     "Indonesia private external debt — non-financial corporates (BI SULNI, USD million)"),
]


def run_fetch(since, until):
    since_dt = datetime.date.fromisoformat(since) if since else None
    until_dt = datetime.date.fromisoformat(until) if until else None
    now = datetime.datetime.now(UTC)

    print("  downloading TABEL6_1.xls ...", end=" ", flush=True)
    path = download_seki("TABEL6_1")
    print(path.name)
    parsed = parse_seki_wide_sheet(
        path, sheet="6.1",
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
            source_code=f"BI/SEKI/TABEL6_1/sheet=6.1/line={line_no}",
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
    return run_main(vendor="bi", topic="sulni",
                    fetch_fn=run_fetch,
                    description=__doc__.splitlines()[0] if __doc__ else "",
                    country_code="ID")

if __name__ == "__main__":
    import sys; sys.exit(main())
