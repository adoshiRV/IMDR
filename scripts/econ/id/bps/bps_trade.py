"""BPS Indonesia foreign trade fetcher.

Source: BPS Web API subject 8 (Foreign Trade). Monthly headline exports/imports
(Juta US$, customs basis) and annual Migas/Non-Migas decomposition. Frequency is
auto-detected from turtahun_to_period. Cells: 1.3 External Demand + 3.2 Current Account.
"""

from __future__ import annotations

import datetime

from imdr.domains.econ.bps_http import all_th_ids, bps_fetch_data_chunked, make_session, turtahun_to_period
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc

# vervar filter: int matches vervar_id, str matches vervar_label (upper)
_TARGETS: list[tuple[int, int | str, int | None, str, str, str]] = [
    (196, 9999, None,
     "BPS.TRADE.EXPORT.TOTAL.USD.ID",
     "Indonesia total goods exports (Juta US$, customs basis) (BPS)",
     "usd_mn"),
    (497, 9999, None,
     "BPS.TRADE.IMPORT.TOTAL.USD.ID",
     "Indonesia total goods imports (Juta US$, customs basis) (BPS)",
     "usd_mn"),
    (203, 1, 439,
     "BPS.TRADE.EXPORT.OILGAS.USD.ID",
     "Indonesia goods exports — Oil & Gas (Juta US$, annual) (BPS)",
     "usd_mn"),
    (203, 2, 439,
     "BPS.TRADE.EXPORT.NONOILGAS.USD.ID",
     "Indonesia goods exports — Non Oil & Gas (Juta US$, annual) (BPS)",
     "usd_mn"),
    (203, 1, 440,
     "BPS.TRADE.IMPORT.OILGAS.USD.ID",
     "Indonesia goods imports — Oil & Gas (Juta US$, annual) (BPS)",
     "usd_mn"),
    (203, 2, 440,
     "BPS.TRADE.IMPORT.NONOILGAS.USD.ID",
     "Indonesia goods imports — Non Oil & Gas (Juta US$, annual) (BPS)",
     "usd_mn"),
]


def _matches_vervar(row: dict, vervar_filter: int | str) -> bool:
    if isinstance(vervar_filter, int):
        return row["vervar_id"] == vervar_filter
    return row["vervar_label"].strip().upper() == str(vervar_filter).upper()


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

    for var_id, vervar_filter, turvar_filter, imdr_code, display, unit in _TARGETS:
        print(f"  var={var_id} vervar={vervar_filter} turvar={turvar_filter} {imdr_code} ...",
              end=" ", flush=True)
        if var_id not in data_cache:
            th_ids = all_th_ids(session, var_id)
            data_cache[var_id] = bps_fetch_data_chunked(
                session, var=var_id, th_ids=th_ids, domain="0000", lang="ind",
            )
        rows = data_cache[var_id]

        filtered = []
        for r in rows:
            if not _matches_vervar(r, vervar_filter):
                continue
            if turvar_filter is not None and r["turvar_id"] != turvar_filter:
                continue
            period = turtahun_to_period(r["turtahun_id"])
            if period is None:
                continue
            filtered.append((r, period))

        if not filtered:
            print("no rows — skipping")
            continue

        freq = filtered[0][1][1]

        indicator = IndicatorRow(
            imdr_code=imdr_code,
            vendor_name="BPS",
            source_code=f"BPS/subject=8/var={var_id}/vervar={vervar_filter}"
                        + (f"/turvar={turvar_filter}" if turvar_filter else ""),
            display_name=display,
            unit=unit,
            frequency=freq,
            country_iso="ID",
            category="bop",
            is_seasonally_adjusted=False,
            bbg_ticker=None,
        )

        obs_emitted = 0
        for r, (month, _f) in filtered:
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
            print("no obs after date filter — skipping")
            continue
        indicators.append(indicator)
        print(f"{obs_emitted} obs ({freq})")

    return indicators, observations


def main() -> int:
    return run_main(vendor="bps", topic="trade",
                    fetch_fn=run_fetch,
                    description=__doc__.splitlines()[0] if __doc__ else "",
                    country_code="ID")


if __name__ == "__main__":
    import sys; sys.exit(main())
