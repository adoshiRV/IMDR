"""BI Indonesia Government Securities Outstanding fetcher (SEKI Table IV.4).

Monthly stock of SUN (conventional bonds + T-bills) and SBSN (sukuk).
Unit: Miliar Rupiah. Cell mapping: 1.2 Fiscal Demand + 4.3 Financial Conditions.
"""

from __future__ import annotations

import datetime

from imdr.domains.econ.bi_seki import download_seki, parse_seki_wide_sheet
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc

_TARGETS: list[tuple[int, str, str]] = [
    (1,  "BI.SBN.SUN.TOTAL.IDR.ID",
     "Indonesia SUN total outstanding (BI SEKI IV.4, Miliar Rp)"),
    (2,  "BI.SBN.OBLIGASI.IDR.ID",
     "Indonesia Obligasi Negara — long-term conventional bonds (BI SEKI IV.4, Miliar Rp)"),
    (15, "BI.SBN.BI_HOLDINGS.IDR.ID",
     "Indonesia SUN held by Bank Indonesia (BI SEKI IV.4, Miliar Rp)"),
    (18, "BI.SBN.SPN.IDR.ID",
     "Indonesia SPN — Surat Perbendaharaan Negara T-bill (BI SEKI IV.4, Miliar Rp)"),
    (27, "BI.SBN.SBSN.TOTAL.IDR.ID",
     "Indonesia SBSN total outstanding (sukuk, BI SEKI IV.4, Miliar Rp)"),
]


def run_fetch(since, until):
    since_dt = datetime.date.fromisoformat(since) if since else None
    until_dt = datetime.date.fromisoformat(until) if until else None
    now = datetime.datetime.now(UTC)

    print("  downloading TABEL4_4.xls ...", end=" ", flush=True)
    path = download_seki("TABEL4_4")
    print(path.name)
    parsed = parse_seki_wide_sheet(
        path, sheet="4.4",
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
            source_code=f"BI/SEKI/TABEL4_4/sheet=4.4/line={line_no}",
            display_name=display, unit="idr_bn", frequency="MONTHLY",
            country_iso="ID", category="instr_outstand",
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
    return run_main(vendor="bi", topic="sbn",
                    fetch_fn=run_fetch,
                    description=__doc__.splitlines()[0] if __doc__ else "",
                    country_code="ID")

if __name__ == "__main__":
    import sys; sys.exit(main())
