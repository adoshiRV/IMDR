"""BPS Indonesia full Sakernas labour fetcher.

Source: BPS Web API subject 6 (Employment) Sakernas semi-annual survey (Feb + Aug).
Labour-force decomposition: total LF, employed, unemployed, employed-to-LF ratio,
7 employment-status categories, and Youth NEET % (annual). Cells: 1.4 Macro Core + 2.3.
"""

from __future__ import annotations

import datetime

from imdr.domains.econ.bps_http import all_th_ids, bps_fetch_data_chunked, make_session, turtahun_to_period
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc

_EMP_STATUS: dict[int, tuple[str, str]] = {
    2086: ("SELF_NO_HELP",     "Self-employed (no assistance)"),
    2087: ("SELF_CASUAL_HELP", "Self-employed with temporary/unpaid help"),
    2088: ("SELF_PAID_HELP",   "Self-employed with permanent paid help"),
    2089: ("EMPLOYEE",         "Employees / Wage workers"),
    2090: ("CASUAL_AGRI",      "Casual workers in agriculture"),
    2091: ("CASUAL_NONAGRI",   "Casual workers in non-agriculture"),
    2092: ("FAMILY_UNPAID",    "Family / Unpaid workers"),
}

_BASE_TARGETS: list[tuple[int, int, int, str, str, str, str, str]] = [
    (698, 11, 827, "SEMIANNUAL",
     "BPS.LABOUR.EMPLOYED.LEVEL.ID",
     "Indonesia employed persons, ages 15+ (BPS Sakernas, count)",
     "th_persons", "labour"),
    (698, 11, 828, "SEMIANNUAL",
     "BPS.LABOUR.UNEMPLOYED.LEVEL.ID",
     "Indonesia unemployed persons, ages 15+ (BPS Sakernas, count)",
     "th_persons", "labour"),
    (698, 11, 829, "SEMIANNUAL",
     "BPS.LABOUR.LF.LEVEL.ID",
     "Indonesia labour force total, ages 15+ (BPS Sakernas, count)",
     "th_persons", "labour"),
    (698, 11, 830, "SEMIANNUAL",
     "BPS.LABOUR.EMP_TO_LF.RATIO.ID",
     "Indonesia employed-to-labour-force ratio (BPS Sakernas, %)",
     "pct", "labour"),
    (1186, 9999, 0, "ANNUAL",
     "BPS.LABOUR.YOUTH_NEET.LEVEL.ID",
     "Indonesia youth (15-24) not in education, employment or training (BPS, %)",
     "pct", "labour"),
]


def _build_targets() -> list[tuple[int, int, int, str, str, str, str, str]]:
    targets = list(_BASE_TARGETS)
    for turvar_id, (suffix, label) in _EMP_STATUS.items():
        targets.append((
            2335, 9999, turvar_id, "SEMIANNUAL",
            f"BPS.LABOUR.EMP_{suffix}.LEVEL.ID",
            f"Indonesia employed persons — {label} (BPS Sakernas, count)",
            "th_persons", "labour",
        ))
    return targets


_TARGETS = _build_targets()


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

    for var_id, vervar_id, turvar_id, freq, imdr_code, display, unit, cat in _TARGETS:
        if var_id not in data_cache:
            th_ids = all_th_ids(session, var_id)
            print(f"  fetching var={var_id} ({len(th_ids)} years) ...", end=" ", flush=True)
            data_cache[var_id] = bps_fetch_data_chunked(
                session, var=var_id, th_ids=th_ids, domain="0000", lang="ind",
            )
            print(f"{len(data_cache[var_id])} rows")
        rows = data_cache[var_id]
        filtered = [r for r in rows
                    if r["vervar_id"] == vervar_id and r["turvar_id"] == turvar_id]
        if not filtered:
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
            period = turtahun_to_period(r["turtahun_id"], r.get("turtahun_label", ""))
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
            continue
        indicators.append(indicator)
    return indicators, observations


def main() -> int:
    return run_main(vendor="bps", topic="sakernas",
                    fetch_fn=run_fetch,
                    description=__doc__.splitlines()[0] if __doc__ else "")


if __name__ == "__main__":
    import sys; sys.exit(main())
