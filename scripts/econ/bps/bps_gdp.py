"""BPS Indonesia GDP fetcher.

Source: BPS Web API subject 11 (Industrial Origin) + subject 169 (Expenditure).
Headline quarterly GDP at total aggregate level — supply-side (level real/nominal,
YoY, QoQ, deflator) and demand-side (YoY growth + deflator), 2010-base series.
Cell: 1.4 Macro Core (headline GDP supply + demand sides).
"""

from __future__ import annotations

import datetime

from imdr.domains.econ.bps_http import all_th_ids, bps_fetch_data_chunked, make_session, turtahun_to_period
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc

# (var_id, vervar_id, turvar_id, imdr_code, display, unit)
_TARGETS: list[tuple[int, int, int, str, str, str]] = [
    (65,  99003, 237,
     "BPS.GDP.GDP.LEVEL_REAL.ID",
     "Indonesia real GDP level — constant 2010 prices, supply-side (BPS, Milyar Rp)",
     "idr_bn"),
    (65,  99003, 238,
     "BPS.GDP.GDP.LEVEL_NOM.ID",
     "Indonesia nominal GDP level — current prices, supply-side (BPS, Milyar Rp)",
     "idr_bn"),
    (104, 99003, 5,
     "BPS.GDP.GDP.YOY.ID",
     "Indonesia real GDP YoY growth — supply-side (BPS, %)",
     "pct"),
    (104, 99003, 4,
     "BPS.GDP.GDP.QOQ.ID",
     "Indonesia real GDP QoQ chained growth — supply-side (BPS, %)",
     "pct"),
    (105, 99003, 236,
     "BPS.GDP.DEFLATOR.YOY.ID",
     "Indonesia GDP deflator YoY — supply-side (BPS, %)",
     "pct"),
    (108, 800,   5,
     "BPS.GDP.EXP_GDP.YOY.ID",
     "Indonesia real GDP YoY growth — expenditure side (BPS, %)",
     "pct"),
    (109, 800,   236,
     "BPS.GDP.EXP_DEFLATOR.YOY.ID",
     "Indonesia GDP deflator YoY — expenditure side (BPS, %)",
     "pct"),
]


def run_fetch(
    since: str | None,
    until: str | None,
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    session = make_session()
    since_dt = datetime.date.fromisoformat(since) if since else None
    until_dt = datetime.date.fromisoformat(until) if until else None
    now = datetime.datetime.now(UTC)

    data_cache: dict[int, list[dict]] = {}
    indicators: list[IndicatorRow] = []
    observations: list[ObservationRow] = []

    for var_id, vervar_id, turvar_id, imdr_code, display, unit in _TARGETS:
        print(f"  var={var_id} vervar={vervar_id} turvar={turvar_id} {imdr_code} ...",
              end=" ", flush=True)
        if var_id not in data_cache:
            th_ids = all_th_ids(session, var_id)
            data_cache[var_id] = bps_fetch_data_chunked(
                session, var=var_id, th_ids=th_ids, domain="0000", lang="ind",
            )
        rows = data_cache[var_id]

        filtered = [r for r in rows
                    if r["vervar_id"] == vervar_id and r["turvar_id"] == turvar_id]
        if not filtered:
            print("no rows after vervar+turvar filter")
            continue

        indicator = IndicatorRow(
            imdr_code=imdr_code, vendor_name="BPS",
            source_code=f"BPS/var={var_id}/vervar={vervar_id}/turvar={turvar_id}",
            display_name=display, unit=unit, frequency="QUARTERLY",
            country_iso="ID", category="gdp",
            is_seasonally_adjusted=False, bbg_ticker=None,
        )

        obs_emitted = 0
        for r in filtered:
            period = turtahun_to_period(r["turtahun_id"])
            if period is None or period[1] != "QUARTERLY":
                continue
            month, _f = period
            try:
                year = int(r["tahun_label"].strip())
            except (TypeError, ValueError):
                continue
            obs_date = datetime.date(year, month, 1)
            if since_dt and obs_date < since_dt:
                continue
            if until_dt and obs_date > until_dt:
                continue
            try:
                value = float(r["value"]) if r["value"] is not None else None
            except (TypeError, ValueError):
                value = None
            observations.append(ObservationRow(
                imdr_code=imdr_code, obs_date=obs_date, vintage=0,
                release_date=now, value=value, ingested_at=now,
            ))
            obs_emitted += 1
        if obs_emitted == 0:
            print("no obs")
            continue
        indicators.append(indicator)
        print(f"{obs_emitted} obs")

    return indicators, observations


def main() -> int:
    return run_main(vendor="bps", topic="gdp",
                    fetch_fn=run_fetch,
                    description=__doc__.splitlines()[0] if __doc__ else "")


if __name__ == "__main__":
    import sys; sys.exit(main())
