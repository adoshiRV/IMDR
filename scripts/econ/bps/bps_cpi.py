"""BPS Indonesia headline CPI fetcher.

Source: Badan Pusat Statistik (BPS) Web API, subject 3 "Consumer Prices Indices".
Pulls four headline national-aggregate CPI variables spanning 1979 to present:
var=1 M-to-M inflation (continuous), var=2 pre-2020 level, var=1709 90-City level
(2018=100, 2020-2023), var=2245 150-kab/kota level (2022=100, 2024+). Cell: 2.4 CPI.
"""

from __future__ import annotations

import datetime

from imdr.domains.econ.bps_http import all_th_ids, bps_fetch_data_chunked, make_session
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc
_MONTHS_TURTAHUN = set(range(1, 13))
_NATIONAL_VERVAR_LABEL = "INDONESIA"

_TARGETS: list[tuple[int, str, str, str]] = [
    (
        1,
        "BPS.CPI.HEADLINE.MOM.ID",
        "Indonesia headline CPI Month-to-Month inflation (BPS)",
        "pct",
    ),
    (
        2,
        "BPS.CPI.HEADLINE_PRE2020.LEVEL.ID",
        "Indonesia headline CPI level — pre-2020 series (BPS)",
        "index",
    ),
    (
        1709,
        "BPS.CPI.HEADLINE_90CITY.LEVEL.ID",
        "Indonesia headline CPI level — 90-City series (2018=100) (BPS)",
        "index",
    ),
    (
        2245,
        "BPS.CPI.HEADLINE_150KAB.LEVEL.ID",
        "Indonesia headline CPI level — 150-kab/kota series (2022=100) (BPS)",
        "index",
    ),
]


def _obs_date(tahun_label: str, turtahun_id: int) -> datetime.date | None:
    try:
        year = int(tahun_label.strip())
    except (TypeError, ValueError):
        return None
    if turtahun_id not in _MONTHS_TURTAHUN:
        return None
    return datetime.date(year, turtahun_id, 1)


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

    for var_id, imdr_code, display, unit in _TARGETS:
        print(f"  var={var_id} {imdr_code} ...", end=" ", flush=True)
        th_ids = all_th_ids(session, var_id)
        rows = bps_fetch_data_chunked(
            session, var=var_id, th_ids=th_ids, domain="0000", lang="ind",
        )
        national = [r for r in rows
                    if r["vervar_label"].strip().upper() == _NATIONAL_VERVAR_LABEL
                    and r["turtahun_id"] in _MONTHS_TURTAHUN]

        indicator = IndicatorRow(
            imdr_code=imdr_code,
            vendor_name="BPS",
            source_code=f"BPS/subject=3/var={var_id}/vervar=9999",
            display_name=display,
            unit=unit,
            frequency="MONTHLY",
            country_iso="ID",
            category="cpi",
            is_seasonally_adjusted=False,
            bbg_ticker=None,
        )

        obs_emitted = 0
        for r in national:
            obs_date = _obs_date(r["tahun_label"], r["turtahun_id"])
            if obs_date is None:
                continue
            if since_dt and obs_date < since_dt:
                continue
            if until_dt and obs_date > until_dt:
                continue
            try:
                value = float(r["value"]) if r["value"] is not None else None
            except (TypeError, ValueError):
                value = None
            observations.append(ObservationRow(
                imdr_code=imdr_code,
                obs_date=obs_date,
                vintage=0,
                release_date=now,
                value=value,
                ingested_at=now,
            ))
            obs_emitted += 1

        if obs_emitted == 0:
            print("no national rows — skipping indicator")
            continue
        indicators.append(indicator)
        print(f"{obs_emitted} obs")

    return indicators, observations


def main() -> int:
    return run_main(vendor="bps", topic="cpi",
                    fetch_fn=run_fetch,
                    description=__doc__.splitlines()[0] if __doc__ else "",
                    country_code="ID")


if __name__ == "__main__":
    import sys; sys.exit(main())
