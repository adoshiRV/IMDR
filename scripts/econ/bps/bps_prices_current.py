"""BPS Indonesia current-base price indices fetcher.

Source: BPS Web API subjects 36 (PPI) + 20 (WPI / Trade Price Indices). Current-base
vars replacing the legacy 2010/2000=100 series: PPI 2016=100 (Q), WPI 2023=100 (M),
Import Price Index 2023=100 (Q), Export Price Index 2023=100 (Q).
Cells: 2.2 Producer Prices, 2.1 Input Costs, 3.1 Terms of Trade.
"""

from __future__ import annotations

import datetime

from imdr.domains.econ.bps_http import all_th_ids, bps_fetch_data_chunked, make_session, turtahun_to_period
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc

# (var_id, vervar_id, turvar_id, freq, imdr_code, display, unit, category)
_TARGETS: list[tuple[int, int, int, str, str, str, str, str]] = [
    (2274, 1, 0, "QUARTERLY",
     "BPS.PPI.TOTAL_2016.LEVEL.ID",
     "Indonesia PPI level — INDEKS UMUM, 2016=100 (BPS)",
     "index", "cpi"),
    (2275, 1, 0, "QUARTERLY",
     "BPS.PPI.TOTAL_2016.QOQ.ID",
     "Indonesia PPI QoQ growth — 2016=100 (BPS, %)",
     "pct", "cpi"),
    (2276, 1, 0, "QUARTERLY",
     "BPS.PPI.TOTAL_2016.YOY.ID",
     "Indonesia PPI YoY growth — 2016=100 (BPS, %)",
     "pct", "cpi"),
    (2498, 6, 0, "MONTHLY",
     "BPS.WPI.TOTAL_2023.LEVEL.ID",
     "Indonesia WPI level — INDEKS UMUM NASIONAL, 2023=100 (BPS)",
     "index", "cpi"),
    (2490, 3, 0, "QUARTERLY",
     "BPS.IMPORT_PRICE.LEVEL.ID",
     "Indonesia Import Price Index — total, 2023=100 (BPS)",
     "index", "cpi"),
    (2492, 3, 0, "QUARTERLY",
     "BPS.IMPORT_PRICE.YOY.ID",
     "Indonesia Import Price Inflation YoY — 2023=100 (BPS, %)",
     "pct", "cpi"),
    (2487, 3, 0, "QUARTERLY",
     "BPS.EXPORT_PRICE.LEVEL.ID",
     "Indonesia Export Price Index — total, 2023=100 (BPS)",
     "index", "cpi"),
    (2489, 3, 0, "QUARTERLY",
     "BPS.EXPORT_PRICE.YOY.ID",
     "Indonesia Export Price Inflation YoY — 2023=100 (BPS, %)",
     "pct", "cpi"),
]


def run_fetch(
    since: str | None,
    until: str | None,
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    session = make_session()
    since_dt = datetime.date.fromisoformat(since) if since else None
    until_dt = datetime.date.fromisoformat(until) if until else None
    now = datetime.datetime.now(UTC)
    indicators: list[IndicatorRow] = []
    observations: list[ObservationRow] = []

    for var_id, vervar_id, turvar_id, freq, imdr_code, display, unit, cat in _TARGETS:
        print(f"  var={var_id} vervar={vervar_id} {imdr_code} ...", end=" ", flush=True)
        th_ids = all_th_ids(session, var_id)
        rows = bps_fetch_data_chunked(
            session, var=var_id, th_ids=th_ids, domain="0000", lang="ind",
        )
        filtered = [r for r in rows
                    if r["vervar_id"] == vervar_id and r["turvar_id"] == turvar_id]
        if not filtered:
            print("no rows after filter")
            continue

        indicator = IndicatorRow(
            imdr_code=imdr_code, vendor_name="BPS",
            source_code=f"BPS/var={var_id}/vervar={vervar_id}/turvar={turvar_id}",
            display_name=display, unit=unit, frequency=freq,
            country_iso="ID", category=cat,
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
    return run_main(vendor="bps", topic="prices_current",
                    fetch_fn=run_fetch,
                    description=__doc__.splitlines()[0] if __doc__ else "")


if __name__ == "__main__":
    import sys; sys.exit(main())
