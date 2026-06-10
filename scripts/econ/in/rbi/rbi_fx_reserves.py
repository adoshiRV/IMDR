"""RBI DBIE — India FX reserves (5 components, weekly).

Source: ``dbie_foreignExchangeReserves`` endpoint on the CIMS_Gateway_DBIE
JSON gateway. See ``src/imdr/domains/econ/rbi_dbie.py`` for the bootstrap
flow + auth handling.

Cell mapping (see docs/admin/econ/india/in_coverage_plan.md):
  3.3 Capital + Financial Account — FX reserves total + composition

Indicators (5, all USD-denominated, Weekly):
  INDIA.FX_RESERVES.TOTAL.USD.IN    reserveCode=TR     Total Reserves
  INDIA.FX_RESERVES.FCA.USD.IN      reserveCode=FCA    Foreign Currency Assets
  INDIA.FX_RESERVES.GOLD.USD.IN     reserveCode=GOLD   Gold
  INDIA.FX_RESERVES.SDR.USD.IN      reserveCode=SDR    SDR Holdings
  INDIA.FX_RESERVES.IMF_POS.USD.IN  reserveCode=IMF    Reserve Position in IMF

DBIE returns values in absolute USD (e.g. 682_321_180_000.0 = $682.32 bn).
"""

from __future__ import annotations

import datetime

from imdr.domains.econ.rbi_dbie import DBIEClient
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc

# (reserve_code, imdr_code, display_name)
_RESERVES: list[tuple[str, str, str]] = [
    ("TR",   "INDIA.FX_RESERVES.TOTAL.USD.IN",
     "India FX Reserves — Total (RBI DBIE, USD)"),
    ("FCA",  "INDIA.FX_RESERVES.FCA.USD.IN",
     "India FX Reserves — Foreign Currency Assets (RBI DBIE, USD)"),
    ("GOLD", "INDIA.FX_RESERVES.GOLD.USD.IN",
     "India FX Reserves — Gold (RBI DBIE, USD)"),
    ("SDR",  "INDIA.FX_RESERVES.SDR.USD.IN",
     "India FX Reserves — SDR Holdings (RBI DBIE, USD)"),
    ("IMF",  "INDIA.FX_RESERVES.IMF_POS.USD.IN",
     "India FX Reserves — Reserve Position in IMF (RBI DBIE, USD)"),
]


def run_fetch(
    since: str | None,
    until: str | None,
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    # DBIE expects YYYY-MM-DD HH:MM:SS; default window = last 10 years
    today = datetime.date.today()
    since_date = (
        datetime.date.fromisoformat(since) if since
        else today.replace(year=today.year - 10)
    )
    until_date = datetime.date.fromisoformat(until) if until else today
    from_s = since_date.strftime("%Y-%m-%d 00:00:00")
    to_s = until_date.strftime("%Y-%m-%d 00:00:00")
    now = datetime.datetime.now(UTC)

    indicators: list[IndicatorRow] = []
    observations: list[ObservationRow] = []

    with DBIEClient() as client:
        for reserve_code, imdr_code, display in _RESERVES:
            print(f"  fetching {reserve_code:5s} → {imdr_code} ...",
                  end=" ", flush=True)
            rows = client.fx_reserves(reserve_code, from_s, to_s)
            print(f"{len(rows)} obs")
            indicators.append(IndicatorRow(
                imdr_code=imdr_code, vendor_name="RBI",
                source_code=f"dbie_foreignExchangeReserves/USD/{reserve_code}/Weekly",
                display_name=display, unit="usd", frequency="WEEKLY",
                country_iso="IN", category="cb_balance_sheet",
                is_seasonally_adjusted=False, bbg_ticker=None,
            ))
            for row in rows:
                ts_ms = row.get("timeDate")
                amount = row.get("amount")
                if ts_ms is None or amount is None:
                    continue
                obs_date = datetime.datetime.fromtimestamp(
                    ts_ms / 1000, tz=UTC
                ).date()
                observations.append(ObservationRow(
                    imdr_code=imdr_code, obs_date=obs_date, vintage=0,
                    release_date=now, value=float(amount),
                    ingested_at=now,
                ))
    return indicators, observations


def main() -> int:
    return run_main(
        vendor="rbi", topic="fx_reserves",
        fetch_fn=run_fetch,
        description=__doc__.splitlines()[0] if __doc__ else "",
        country_code="IN",
    )


if __name__ == "__main__":
    import sys
    sys.exit(main())
