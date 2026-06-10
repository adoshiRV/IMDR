"""BIS Indonesia macro-cross-country fetcher (Effective Exchange Rates,
Debt Service Ratios, Credit-to-GDP gap, Central Bank policy rate).

Source: Bank for International Settlements SDMX-JSON API at
    https://stats.bis.org/api/v2/data/dataflow/BIS/{flow}/{ver}/{key}

Public, no auth. BIS provides cross-country macro-financial gauges with
harmonised definitions — used as Tier-4 fallback per the vendor cascade.

Cell mapping for Indonesia:
  3.4 FX / REER — NEER + REER (broad basket)
  4.2 Balance Sheets — DSR for HH / NFC / Private + Credit-to-GDP ratio + gap
  4.4 Policy Reaction — BI 7-Day Reverse Repo Rate (CBPOL)
"""

from __future__ import annotations

import datetime

from imdr.domains.econ.bis_sdmx import bis_fetch_series, parse_bis_period
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc

# (flow_id, version, key, freq, imdr_code, display, unit, category)
_TARGETS: list[tuple[str, str, str, str, str, str, str, str]] = [
    ("WS_EER", "1.0", "M.N.B.ID", "MONTHLY",
     "BIS.NEER.BROAD.ID",
     "Indonesia Nominal Effective Exchange Rate — broad basket (BIS, index, 2020=100)",
     "index", "fx"),
    ("WS_EER", "1.0", "M.R.B.ID", "MONTHLY",
     "BIS.REER.BROAD.ID",
     "Indonesia Real Effective Exchange Rate — broad basket (BIS, index, 2020=100)",
     "index", "fx"),
    ("WS_DSR", "1.0", "Q.ID.H", "QUARTERLY",
     "BIS.DSR.HOUSEHOLDS.ID",
     "Indonesia Debt Service Ratio — Households & NPISHs (BIS, %)",
     "pct", "balance_sheet"),
    ("WS_DSR", "1.0", "Q.ID.N", "QUARTERLY",
     "BIS.DSR.NFC.ID",
     "Indonesia Debt Service Ratio — Non-financial corporates (BIS, %)",
     "pct", "balance_sheet"),
    ("WS_DSR", "1.0", "Q.ID.P", "QUARTERLY",
     "BIS.DSR.PNFS.ID",
     "Indonesia Debt Service Ratio — Private non-financial sector (BIS, %)",
     "pct", "balance_sheet"),
    ("WS_CREDIT_GAP", "1.0", "Q.ID.P.A.A", "QUARTERLY",
     "BIS.CREDIT_TO_GDP.RATIO.ID",
     "Indonesia Credit-to-GDP ratio — Private non-fin sector, all lenders (BIS, %)",
     "pct", "balance_sheet"),
    ("WS_CREDIT_GAP", "1.0", "Q.ID.P.A.C", "QUARTERLY",
     "BIS.CREDIT_TO_GDP.GAP.ID",
     "Indonesia Credit-to-GDP gap — actual minus HP-filter trend (BIS, %)",
     "pct", "balance_sheet"),
    ("WS_CBPOL", "1.0", "D.ID", "DAILY",
     "BIS.POLICY_RATE.ID",
     "Indonesia central bank policy rate — BI 7-Day Reverse Repo Rate (BIS CBPOL, %)",
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
            country_iso="ID", category=cat,
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
    return run_main(vendor="bis", topic="indonesia",
                    fetch_fn=run_fetch,
                    description=__doc__.splitlines()[0] if __doc__ else "",
                    country_code="ID")


if __name__ == "__main__":
    import sys
    sys.exit(main())
