"""BI Indonesia Business Survey fetcher (SKDU T1 — Kegiatan Usaha).

Quarterly Weighted Net Balance (SBT) diffusion index by 17-sector industrial
classification. TOTAL + 17 sectors = 18 indicators. Archive: SKDU.zip.
Cell mapping: 1.4 Macro Core + 1.1 Private Demand.
"""

from __future__ import annotations

import datetime

from imdr.domains.econ.bi_survey import download_survey_zip, parse_survey_rows
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc

_TARGETS: list[tuple[int, str, str]] = [
    (52, "BI.BIZ_ACTIVITY.TOTAL.SBT.ID",
     "Indonesia business activity TOTAL — Weighted Net Balance (BI SKDU, %)"),
    (6,  "BI.BIZ_ACTIVITY.AGRI.SBT.ID",
     "Indonesia business activity — A. Agriculture, Forestry & Fishery (BI SKDU SBT, %)"),
    (14, "BI.BIZ_ACTIVITY.MINING.SBT.ID",
     "Indonesia business activity — B. Mining & Quarrying (BI SKDU SBT, %)"),
    (15, "BI.BIZ_ACTIVITY.MFG.SBT.ID",
     "Indonesia business activity — C. Manufacturing (BI SKDU SBT, %)"),
    (30, "BI.BIZ_ACTIVITY.ELEC_GAS.SBT.ID",
     "Indonesia business activity — D. Electricity & Gas (BI SKDU SBT, %)"),
    (31, "BI.BIZ_ACTIVITY.WATER.SBT.ID",
     "Indonesia business activity — E. Water Supply / Sewerage (BI SKDU SBT, %)"),
    (32, "BI.BIZ_ACTIVITY.CONSTR.SBT.ID",
     "Indonesia business activity — F. Construction (BI SKDU SBT, %)"),
    (33, "BI.BIZ_ACTIVITY.TRADE.SBT.ID",
     "Indonesia business activity — G. Wholesale & Retail Trade (BI SKDU SBT, %)"),
    (36, "BI.BIZ_ACTIVITY.TRANSPORT.SBT.ID",
     "Indonesia business activity — H. Transport & Storage (BI SKDU SBT, %)"),
    (37, "BI.BIZ_ACTIVITY.ACCOM.SBT.ID",
     "Indonesia business activity — I. Accommodation & Food Service (BI SKDU SBT, %)"),
    (40, "BI.BIZ_ACTIVITY.INFO_COMM.SBT.ID",
     "Indonesia business activity — J. Information & Communication (BI SKDU SBT, %)"),
    (41, "BI.BIZ_ACTIVITY.FINANCE.SBT.ID",
     "Indonesia business activity — K. Financial & Insurance Services (BI SKDU SBT, %)"),
    (46, "BI.BIZ_ACTIVITY.REALESTATE.SBT.ID",
     "Indonesia business activity — L. Real Estate Activities (BI SKDU SBT, %)"),
    (47, "BI.BIZ_ACTIVITY.BIZ_SVC.SBT.ID",
     "Indonesia business activity — M,N. Business Services (BI SKDU SBT, %)"),
    (48, "BI.BIZ_ACTIVITY.PUBADMIN.SBT.ID",
     "Indonesia business activity — O. Public Administration & Defense (BI SKDU SBT, %)"),
    (49, "BI.BIZ_ACTIVITY.EDUCATION.SBT.ID",
     "Indonesia business activity — P. Education Services (BI SKDU SBT, %)"),
    (50, "BI.BIZ_ACTIVITY.HEALTH.SBT.ID",
     "Indonesia business activity — Q. Health & Social Work (BI SKDU SBT, %)"),
    (51, "BI.BIZ_ACTIVITY.OTHER_SVC.SBT.ID",
     "Indonesia business activity — R,S,T,U. Other Services (BI SKDU SBT, %)"),
]


def run_fetch(since, until):
    since_dt = datetime.date.fromisoformat(since) if since else None
    until_dt = datetime.date.fromisoformat(until) if until else None
    now = datetime.datetime.now(UTC)

    print("  downloading SKDU.zip ...", end=" ", flush=True)
    path = download_survey_zip("SKDU")
    print(path.name)
    rows_data = parse_survey_rows(
        path, "T1 Kegiatan Usaha",
        rows=[r for r, _, _ in _TARGETS],
        year_row=4, month_row=5, first_data_col=4,
    )

    indicators: list[IndicatorRow] = []
    observations: list[ObservationRow] = []
    for row_idx, imdr_code, display in _TARGETS:
        series = rows_data.get(row_idx) or []
        if not series:
            print(f"    {imdr_code}: row {row_idx} empty — skipping")
            continue
        indicator = IndicatorRow(
            imdr_code=imdr_code, vendor_name="BI",
            source_code=f"BI/SKDU/T1 Kegiatan Usaha/row={row_idx}",
            display_name=display, unit="pct", frequency="QUARTERLY",
            country_iso="ID", category="sentiment",
            is_seasonally_adjusted=False, bbg_ticker=None,
        )
        obs_emitted = 0
        for obs_date, value in series:
            if value is None:
                continue
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
    return run_main(vendor="bi", topic="business_survey",
                    fetch_fn=run_fetch,
                    description=__doc__.splitlines()[0] if __doc__ else "",
                    country_code="ID")

if __name__ == "__main__":
    import sys; sys.exit(main())
