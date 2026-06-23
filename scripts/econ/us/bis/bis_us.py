"""BIS United States Effective Exchange Rates fetcher — cell 3.4 FX/REER.

Source: Bank for International Settlements SDMX-JSON API at
    https://stats.bis.org/api/v2/data/dataflow/BIS/{flow}/{ver}/{key}

Public, no auth. BIS provides harmonised NEER/REER indices (2020=100) for
the broad basket (61 economies) at monthly frequency.

Cell mapping for United States:
  3.4 FX / REER  — NEER + REER (broad basket)

Narrow basket (`N`) is not included: BIS does publish narrow-basket EER for
the US but the broad basket is the canonical cross-country comparable series.
"""

from __future__ import annotations

import datetime

from imdr.domains.econ.bis_sdmx import bis_fetch_series, parse_bis_period
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc

# (flow_id, version, key, freq, imdr_code, display, unit, category)
_TARGETS: list[tuple[str, str, str, str, str, str, str, str]] = [
    ("WS_EER", "1.0", "M.N.B.US", "MONTHLY",
     "BIS.NEER.BROAD.US",
     "United States Nominal Effective Exchange Rate — broad basket (BIS, index, 2020=100)",
     "index", "fx"),
    ("WS_EER", "1.0", "M.R.B.US", "MONTHLY",
     "BIS.REER.BROAD.US",
     "United States Real Effective Exchange Rate — broad basket (BIS, index, 2020=100)",
     "index", "fx"),
]


def run_fetch(
    since: str | None,
    until: str | None,
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    since_dt = datetime.date.fromisoformat(since) if since else None
    until_dt = datetime.date.fromisoformat(until) if until else None
    now = datetime.datetime.now(UTC)

    indicators: list[IndicatorRow] = []
    observations: list[ObservationRow] = []

    for flow, ver, key, freq, imdr_code, display, unit, cat in _TARGETS:
        print(f"  fetching {flow} {key} ({freq}) → {imdr_code} ...", end=" ", flush=True)
        try:
            series = bis_fetch_series(flow, ver, key)
        except Exception as e:
            print(f"FAIL: {str(e)[:80]}")
            continue
        if not series:
            print("no data")
            continue
        indicator = IndicatorRow(
            imdr_code=imdr_code, vendor_name="BIS",
            source_code=f"BIS/{flow}/{ver}/{key}",
            display_name=display, unit=unit, frequency=freq,
            country_iso="US", category=cat,
            is_seasonally_adjusted=False, bbg_ticker=None,
        )
        obs_emitted = 0
        for period_str, value in series:
            obs_date = parse_bis_period(period_str)
            if obs_date is None:
                continue
            if since_dt is not None and obs_date < since_dt:
                continue
            if until_dt is not None and obs_date > until_dt:
                continue
            observations.append(ObservationRow(
                imdr_code=imdr_code, obs_date=obs_date, vintage=0,
                release_date=now, value=value, ingested_at=now,
            ))
            obs_emitted += 1
        indicators.append(indicator)
        print(f"{obs_emitted} obs")
    return indicators, observations


def main() -> int:
    return run_main(vendor="bis", topic="us",
                    fetch_fn=run_fetch,
                    description=__doc__.splitlines()[0] if __doc__ else "",
                    country_code="US")


if __name__ == "__main__":
    import sys
    sys.exit(main())
