"""BI Indonesia Consumer Survey fetcher (Survei Konsumen — SK.zip, Tabel 1).

Monthly Consumer Confidence Index (IKK) and sub-components from 2012-01 onward,
18 cities. 9 indicators. Cell mapping: 1.1 Private Demand.
"""

from __future__ import annotations

import datetime

from imdr.domains.econ.bi_survey import download_survey_zip, parse_survey_rows
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc

_TARGETS: list[tuple[int, str, str]] = [
    (8,  "BI.SENTIMENT.CCI.LEVEL.ID",
     "Indonesia Consumer Confidence Index — IKK (BI Survei Konsumen, 18 cities, index)"),
    (9,  "BI.SENTIMENT.CECI.LEVEL.ID",
     "Indonesia Current Economic Condition Index — IKE (BI Survei Konsumen, index)"),
    (10, "BI.SENTIMENT.CEI.LEVEL.ID",
     "Indonesia Consumer Expectation Index — IEK (BI Survei Konsumen, index)"),
    (12, "BI.SENTIMENT.CURRENT_INCOMES.LEVEL.ID",
     "Indonesia Current Incomes Index (BI Survei Konsumen, index)"),
    (13, "BI.SENTIMENT.JOB_AVAILABILITY.LEVEL.ID",
     "Indonesia Job Availability Index (BI Survei Konsumen, index)"),
    (14, "BI.SENTIMENT.DURABLE_GOODS.LEVEL.ID",
     "Indonesia Purchase of Durable Goods Index (BI Survei Konsumen, index)"),
    (16, "BI.SENTIMENT.INCOMES_EXP.LEVEL.ID",
     "Indonesia Incomes Expectation Index — 6m ahead (BI Survei Konsumen, index)"),
    (17, "BI.SENTIMENT.JOBS_EXP.LEVEL.ID",
     "Indonesia Job Availability Expectation Index — 6m ahead (BI Survei Konsumen, index)"),
    (18, "BI.SENTIMENT.BIZ_ACT_EXP.LEVEL.ID",
     "Indonesia Business Activities Expectation Index — 6m ahead (BI Survei Konsumen, index)"),
]


def run_fetch(since, until):
    since_dt = datetime.date.fromisoformat(since) if since else None
    until_dt = datetime.date.fromisoformat(until) if until else None
    now = datetime.datetime.now(UTC)

    print("  downloading SK.zip ...", end=" ", flush=True)
    path = download_survey_zip("SK")
    print(path.name)
    rows_data = parse_survey_rows(
        path, "Tabel 1",
        rows=[r for r, _, _ in _TARGETS],
        year_row=5, month_row=6, first_data_col=4,
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
            source_code=f"BI/SK/Tabel 1/row={row_idx}",
            display_name=display, unit="index", frequency="MONTHLY",
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
    return run_main(vendor="bi", topic="consumer_survey",
                    fetch_fn=run_fetch,
                    description=__doc__.splitlines()[0] if __doc__ else "")

if __name__ == "__main__":
    import sys; sys.exit(main())
