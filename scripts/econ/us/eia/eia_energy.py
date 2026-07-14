"""EIA energy spot prices fetcher — cell 2.1 Input Costs (US).

Pulls daily spot prices for WTI crude, Brent crude, and Henry Hub natural gas
from the EIA v2 API. Default history start: 2015-01-01.

Routes and series IDs:
  petroleum/pri/spt   — WTI Cushing:  RWTC   (USD/barrel)
  petroleum/pri/spt   — Brent FOB:    RBRTE  (USD/barrel)
  natural-gas/pri/fut — Henry Hub:    RNGWHHD (USD/MMBtu)

Usage:
    python -m scripts.econ.us.eia.eia_energy
    python -m scripts.econ.us.eia.eia_energy --since 2024-01-01 --no-load
    python -m scripts.econ.us.eia.eia_energy --no-load
"""

from __future__ import annotations

import datetime

from imdr.domains.econ.eia_http import EiaClient
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc

_DEFAULT_START = "2015-01-01"

# (route, series_id, imdr_code, display_name)
_TARGETS: list[tuple[str, str, str, str]] = [
    (
        "petroleum/pri/spt",
        "RWTC",
        "EIA.ENERGY.WTI_SPOT.US",
        "WTI Cushing Crude Oil Spot Price (USD per barrel)",
    ),
    (
        "petroleum/pri/spt",
        "RBRTE",
        "EIA.ENERGY.BRENT_SPOT.US",
        "Europe Brent Crude Oil Spot Price FOB (USD per barrel)",
    ),
    (
        "natural-gas/pri/fut",
        "RNGWHHD",
        "EIA.ENERGY.HH_GAS_SPOT.US",
        "Henry Hub Natural Gas Spot Price (USD per MMBtu)",
    ),
]


def run_fetch(
    since: str | None,
    until: str | None,
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    start_period = since or _DEFAULT_START
    end_period = until or datetime.date.today().isoformat()
    now = datetime.datetime.now(UTC)

    indicators: list[IndicatorRow] = []
    observations: list[ObservationRow] = []

    with EiaClient() as client:
        for route, series_id, imdr_code, display_name in _TARGETS:
            rows = client.fetch_series(
                route,
                frequency="daily",
                facets={"series": series_id},
                start_period=start_period,
            )
            rows = [r for r in rows if r.get("period", "") <= end_period]

            if not rows:
                print(f"  WARN {series_id}: 0 rows in [{start_period}, {end_period}]")
                continue

            indicators.append(IndicatorRow(
                imdr_code=imdr_code,
                vendor_name="EIA",
                source_code=series_id,
                display_name=display_name,
                unit="usd",
                frequency="DAILY",
                country_iso="US",
                category="energy",
                is_seasonally_adjusted=False,
                bbg_ticker=None,
            ))

            n = 0
            for obs in rows:
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

            latest_period = max(r["period"] for r in rows if r.get("period"))
            latest_val = next(
                (r.get("value") for r in sorted(rows, key=lambda x: x.get("period", ""), reverse=True)),
                None,
            )
            print(f"  {series_id:<12} {imdr_code:<36} {n:,} obs  latest={latest_period} value={latest_val}")

    return indicators, observations


def main() -> int:
    return run_main(
        vendor="eia",
        topic="energy",
        fetch_fn=run_fetch,
        description=__doc__.splitlines()[0] if __doc__ else "",
        country_code="US",
    )


if __name__ == "__main__":
    import sys
    sys.exit(main())
