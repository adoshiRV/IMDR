"""BI Indonesia Monetary Base (M0) fetcher (SEKI Table I.2).

Neraca Analitis Otoritas Moneter — BI's analytic balance sheet showing M0
and its counterparts. Monthly, 2020-present in current sheet. Unit: Miliar Rupiah.
Cell mapping: 4.4 Policy Reaction + cb_balance_sheet.
"""

from __future__ import annotations

import datetime

from imdr.domains.econ.bi_seki import download_seki, parse_seki_wide_sheet
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc

_TARGETS: list[tuple[int, str, str]] = [
    (1,  "BI.M0.LEVEL.ID",
     "Indonesia Monetary Base M0 — Uang Primer (BI SEKI I.2, Miliar Rp)"),
    (3,  "BI.M0.CURRENCY_ISSUED.LEVEL.ID",
     "Indonesia Currency Issued by BI (BI SEKI I.2, Miliar Rp)"),
    (6,  "BI.M0.BANK_RESERVES.LEVEL.ID",
     "Indonesia Commercial Bank Reserves at BI (BI SEKI I.2, Miliar Rp)"),
    (13, "BI.M0.NFA.LEVEL.ID",
     "Indonesia BI Net Foreign Assets (BI SEKI I.2, Miliar Rp)"),
    (19, "BI.M0.NET_CLAIMS_GOVT.LEVEL.ID",
     "Indonesia BI Net Claims on Central Govt (BI SEKI I.2, Miliar Rp)"),
]


def run_fetch(since, until):
    since_dt = datetime.date.fromisoformat(since) if since else None
    until_dt = datetime.date.fromisoformat(until) if until else None
    now = datetime.datetime.now(UTC)

    print("  downloading TABEL1_2.xls ...", end=" ", flush=True)
    path = download_seki("TABEL1_2")
    print(path.name)
    parsed = parse_seki_wide_sheet(path, sheet="I.2")
    print(f"  parsed {len(parsed)} line items")

    indicators: list[IndicatorRow] = []
    observations: list[ObservationRow] = []
    for line_no, imdr_code, display in _TARGETS:
        series = parsed.get(line_no)
        if not series:
            print(f"    {imdr_code}: line {line_no} missing — skipping")
            continue
        indicator = IndicatorRow(
            imdr_code=imdr_code, vendor_name="BI",
            source_code=f"BI/SEKI/TABEL1_2/sheet=I.2/line={line_no}",
            display_name=display, unit="idr_bn", frequency="MONTHLY",
            country_iso="ID", category="cb_balance_sheet",
            is_seasonally_adjusted=False, bbg_ticker=None,
        )
        obs_emitted = 0
        for obs_date, value, _label in series:
            if since_dt and obs_date < since_dt:
                continue
            if until_dt and obs_date > until_dt:
                continue
            observations.append(ObservationRow(
                imdr_code=imdr_code, obs_date=obs_date, vintage=0,
                release_date=now, value=value, ingested_at=now,
            ))
            obs_emitted += 1
        indicators.append(indicator)
        print(f"    {imdr_code}: {obs_emitted} obs")
    return indicators, observations


def main() -> int:
    return run_main(vendor="bi", topic="monetary_base",
                    fetch_fn=run_fetch,
                    description=__doc__.splitlines()[0] if __doc__ else "",
                    country_code="ID")

if __name__ == "__main__":
    import sys; sys.exit(main())
