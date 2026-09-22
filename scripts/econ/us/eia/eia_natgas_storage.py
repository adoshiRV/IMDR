"""EIA Weekly Natural Gas Storage Report fetcher (US).

Working gas in underground storage -- the Lower-48 total plus the five EIA
storage regions, and the South Central salt/nonsalt split. Published every
Thursday at 10:30 ET for the week ending the prior Friday. History: 2010-01-01.

Route and series IDs (natural-gas/stor/wkly, frequency=weekly):
  NW2_EPG0_SWO_R48_BCF  Lower 48 States
  NW2_EPG0_SWO_R31_BCF  East
  NW2_EPG0_SWO_R32_BCF  Midwest
  NW2_EPG0_SWO_R33_BCF  South Central
  NW2_EPG0_SSO_R33_BCF  South Central -- salt
  NW2_EPG0_SNO_R33_BCF  South Central -- nonsalt
  NW2_EPG0_SWO_R34_BCF  Mountain
  NW2_EPG0_SWO_R35_BCF  Pacific

All eight are LEVELS in Bcf. The headline "+82 Bcf build" and the 5-year band
are DERIVED from these levels -- compute them downstream rather than storing a
derived series alongside its own inputs.

Requires dim_unit 'bcf' (migration 131). Without it the loader aborts the whole
parquet pair with "!! FK resolution failures" and rc=2 -- nothing is written,
including the rows whose FKs were fine.

Usage:
    python -m scripts.econ.us.eia.eia_natgas_storage
    python -m scripts.econ.us.eia.eia_natgas_storage --since 2024-01-01 --no-load
"""

from __future__ import annotations

import datetime

from imdr.domains.econ.eia_http import EiaClient
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc

_ROUTE = "natural-gas/stor/wkly"
_DEFAULT_START = "2010-01-01"

# EIA series id -> (imdr_code, display_name)
_SERIES: dict[str, tuple[str, str]] = {
    "NW2_EPG0_SWO_R48_BCF": (
        "EIA.NATGAS.STORAGE_L48.US",
        "US Natural Gas Working Underground Storage — Lower 48 States (Bcf)",
    ),
    "NW2_EPG0_SWO_R31_BCF": (
        "EIA.NATGAS.STORAGE_EAST.US",
        "US Natural Gas Working Underground Storage — East region (Bcf)",
    ),
    "NW2_EPG0_SWO_R32_BCF": (
        "EIA.NATGAS.STORAGE_MIDWEST.US",
        "US Natural Gas Working Underground Storage — Midwest region (Bcf)",
    ),
    "NW2_EPG0_SWO_R33_BCF": (
        "EIA.NATGAS.STORAGE_SOUTH_CENTRAL.US",
        "US Natural Gas Working Underground Storage — South Central region (Bcf)",
    ),
    "NW2_EPG0_SSO_R33_BCF": (
        "EIA.NATGAS.STORAGE_SOUTH_CENTRAL_SALT.US",
        "US Natural Gas Working Underground Storage — South Central, salt (Bcf)",
    ),
    "NW2_EPG0_SNO_R33_BCF": (
        "EIA.NATGAS.STORAGE_SOUTH_CENTRAL_NONSALT.US",
        "US Natural Gas Working Underground Storage — South Central, nonsalt (Bcf)",
    ),
    "NW2_EPG0_SWO_R34_BCF": (
        "EIA.NATGAS.STORAGE_MOUNTAIN.US",
        "US Natural Gas Working Underground Storage — Mountain region (Bcf)",
    ),
    "NW2_EPG0_SWO_R35_BCF": (
        "EIA.NATGAS.STORAGE_PACIFIC.US",
        "US Natural Gas Working Underground Storage — Pacific region (Bcf)",
    ),
}


def run_fetch(
    since: str | None,
    until: str | None,
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    start_period = since or _DEFAULT_START
    end_period = until or datetime.date.today().isoformat()
    now = datetime.datetime.now(UTC)

    # One paginated call for all eight series -- EiaClient emits a repeated
    # facets[series][]= param per list entry, so this is 2 requests rather
    # than 8 full paginations.
    with EiaClient() as client:
        rows = client.fetch_series(
            _ROUTE,
            frequency="weekly",
            facets={"series": list(_SERIES)},
            start_period=start_period,
        )

    by_series: dict[str, list[dict]] = {sid: [] for sid in _SERIES}
    for r in rows:
        sid = r.get("series")
        if sid in by_series and r.get("period", "") <= end_period:
            by_series[sid].append(r)

    # All eight series share one publication and one history (2010-01-01 ->),
    # so a PARTIAL response means EIA renamed or retired a series id, not a
    # quiet week. Fail the whole run rather than let 1-7 indicators go stale
    # behind a rc=0 -- run_main's only emptiness gate is "no observations at
    # all", which a surviving L48 would satisfy on its own.
    missing = sorted(sid for sid, rows_ in by_series.items() if not rows_)
    if missing and len(missing) < len(_SERIES):
        raise RuntimeError(
            f"EIA returned no rows for {len(missing)}/{len(_SERIES)} storage series "
            f"in [{start_period}, {end_period}]: {missing}. The other "
            f"{len(_SERIES) - len(missing)} did return data, so this is a source "
            f"change (renamed/retired series id), not an empty window. Re-check "
            f"the facet list: {_ROUTE}/facet/series."
        )

    indicators: list[IndicatorRow] = []
    observations: list[ObservationRow] = []

    for series_id, (imdr_code, display_name) in _SERIES.items():
        series_rows = by_series[series_id]
        if not series_rows:
            # Only reachable when EVERY series is empty (e.g. a --since window
            # in the future); run_main then fails the run on zero observations.
            print(f"  WARN {series_id}: 0 rows in [{start_period}, {end_period}]")
            continue

        indicators.append(IndicatorRow(
            imdr_code=imdr_code,
            vendor_name="EIA",
            source_code=series_id,
            display_name=display_name,
            unit="bcf",
            frequency="WEEKLY",
            country_iso="US",
            category="energy",
            is_seasonally_adjusted=False,
            bbg_ticker=None,
        ))

        n = 0
        for obs in series_rows:
            period = obs.get("period", "")
            if not period or len(period) != 10:
                continue
            try:
                obs_date = datetime.date.fromisoformat(period)
            except ValueError:
                continue
            val_raw = obs.get("value")
            try:
                value = float(val_raw) if val_raw not in (None, "", "--") else None
            except (ValueError, TypeError):
                value = None
            observations.append(ObservationRow(
                imdr_code=imdr_code,
                obs_date=obs_date,
                vintage=0,
                release_date=now,
                value=value,
                ingested_at=now,
            ))
            n += 1

        latest = max(series_rows, key=lambda x: x.get("period", ""))
        print(
            f"  {series_id:<22} {imdr_code:<46} {n:,} obs  "
            f"latest={latest.get('period')} value={latest.get('value')}"
        )

    return indicators, observations


def main() -> int:
    return run_main(
        vendor="eia",
        topic="natgas_storage",
        fetch_fn=run_fetch,
        description=__doc__.splitlines()[0] if __doc__ else "",
        country_code="US",
    )


if __name__ == "__main__":
    import sys
    sys.exit(main())
