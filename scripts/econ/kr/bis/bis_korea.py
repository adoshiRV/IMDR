"""BIS Korea fetcher — Bank of Korea Base Rate (Central Bank policy rate).

Source: Bank for International Settlements SDMX-JSON API at
    https://stats.bis.org/api/v2/data/dataflow/BIS/{flow}/{ver}/{key}

Public, no auth. BIS `WS_CBPOL` publishes harmonised central-bank policy
rates cross-country; for Korea the series IS the BOK Base Rate (기준금리),
daily, end-of-period-on-change, back to 1999.

WHY THIS EXISTS — fills a real coverage gap. IMDR's only prior KR policy-rate
proxy was `FRED.RATES.KR_DISCOUNT.KR` (id 388, FRED INTDSRKRM193N), the BOK
*discount* rate, which sits at a flat 1.0% and is NOT the policy rate. The
BOK Base Rate is also NOT on KOSIS (see scripts/econ/kr/kosis/kosis_bank_rates.py
docstring). BIS CBPOL is the cleanest authoritative source and mirrors the
existing `BIS.POLICY_RATE.ID` (id 600) and `BIS.POLICY_RATE.IN` (id 900) feeds.

Cell mapping: 4.4 Policy Reaction.

Usage:
    C:/Users/adoshi/.conda/envs/imdr/python.exe scripts/econ/kr/bis/bis_korea.py --no-load
    python -m scripts.econ.kr.bis.bis_korea
"""

from __future__ import annotations

import datetime

from imdr.domains.econ.bis_sdmx import bis_fetch_series, parse_bis_period
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc

# (flow_id, version, key, freq, imdr_code, display, unit, category)
_TARGETS: list[tuple[str, str, str, str, str, str, str, str]] = [
    ("WS_CBPOL", "1.0", "D.KR", "DAILY",
     "BIS.POLICY_RATE.KR",
     "Korea central bank policy rate — BOK Base Rate (BIS CBPOL, %)",
     "pct", "rates"),
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
            country_iso="KR", category=cat,
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
    return run_main(vendor="bis", topic="korea",
                    fetch_fn=run_fetch,
                    description=__doc__.splitlines()[0] if __doc__ else "",
                    country_code="KR")


if __name__ == "__main__":
    import sys
    sys.exit(main())
