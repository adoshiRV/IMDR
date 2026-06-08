"""BPS Indonesia Industrial Production fetcher.

Source: BPS Web API subject 9 (Large & Medium Manufacturing — IBS). Monthly and
quarterly manufacturing IIP (level 2010=100 and growth rate) for the headline
Large/Medium Mfg panel. Cells: 1.4 Macro Core (Industrial Production) + 2.3 Domestic Costs.
"""

from __future__ import annotations

import datetime

from imdr.domains.econ.bps_http import all_th_ids, bps_fetch_data_chunked, make_session, turtahun_to_period
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc

# (var_id, vervar_id, turvar_id, freq, imdr_code, display, unit)
_TARGETS: list[tuple[int, int, int, str, str, str, str]] = [
    (88, 1, 0, "MONTHLY",
     "BPS.IP.MFG_MONTHLY.LEVEL.ID",
     "Indonesia Industrial Production — Large/Medium Mfg, monthly (2010=100) (BPS)",
     "index"),
    (88, 2, 0, "MONTHLY",
     "BPS.IP.MFG_MONTHLY.GROWTH.ID",
     "Indonesia Industrial Production growth — Large/Medium Mfg, monthly (BPS, %)",
     "pct"),
    (89, 1, 0, "QUARTERLY",
     "BPS.IP.MFG_QUARTERLY.LEVEL.ID",
     "Indonesia Industrial Production — Large/Medium Mfg, quarterly (2010=100) (BPS)",
     "index"),
    (89, 2, 0, "QUARTERLY",
     "BPS.IP.MFG_QUARTERLY.GROWTH.ID",
     "Indonesia Industrial Production growth — Large/Medium Mfg, quarterly (BPS, %)",
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

    for var_id, vervar_id, turvar_id, freq, imdr_code, display, unit in _TARGETS:
        print(f"  var={var_id} vervar={vervar_id} {imdr_code} ...", end=" ", flush=True)
        if var_id not in data_cache:
            th_ids = all_th_ids(session, var_id)
            data_cache[var_id] = bps_fetch_data_chunked(
                session, var=var_id, th_ids=th_ids, domain="0000", lang="ind",
            )
        rows = data_cache[var_id]
        filtered = [r for r in rows
                    if r["vervar_id"] == vervar_id and r["turvar_id"] == turvar_id]
        if not filtered:
            print("no rows")
            continue

        indicator = IndicatorRow(
            imdr_code=imdr_code, vendor_name="BPS",
            source_code=f"BPS/var={var_id}/vervar={vervar_id}/turvar={turvar_id}",
            display_name=display, unit=unit, frequency=freq,
            country_iso="ID", category="gdp",
            is_seasonally_adjusted=False, bbg_ticker=None,
        )
        obs_emitted = 0
        for r in filtered:
            period = turtahun_to_period(r["turtahun_id"])
            if period is None or period[1] != freq:
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
    return run_main(vendor="bps", topic="ip",
                    fetch_fn=run_fetch,
                    description=__doc__.splitlines()[0] if __doc__ else "")


if __name__ == "__main__":
    import sys; sys.exit(main())
