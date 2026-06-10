"""BI Indonesia Commercial Bank Balance Sheet fetcher (SEKI Table I.3).

Neraca Analitis Bank Umum dan BPR — analytic balance sheet of the commercial
banking system + rural credit banks. Unit: Miliar Rupiah. Monthly, 2010-present.
Cell mapping: 4.2 Balance Sheets + 4.4 Policy Reaction.
"""

from __future__ import annotations

import datetime

from imdr.domains.econ.bi_seki import download_seki, parse_seki_wide_sheet
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc

_TARGETS: list[tuple[int, str, str]] = [
    (1,  "BI.BANK_BS.DEPOSITS_M2.IDR.ID",
     "Indonesia bank deposits + securities feeding M2 (BI SEKI I.3, Miliar Rp)"),
    (2,  "BI.BANK_BS.GIRO.IDR.ID",
     "Indonesia commercial bank demand deposits — Giro (BI SEKI I.3, Miliar Rp)"),
    (6,  "BI.BANK_BS.TIME_DEPOSITS.IDR.ID",
     "Indonesia commercial bank time deposits — Simpanan Berjangka (BI SEKI I.3, Miliar Rp)"),
    (9,  "BI.BANK_BS.SAVINGS.IDR.ID",
     "Indonesia commercial bank savings deposits — Tabungan (BI SEKI I.3, Miliar Rp)"),
    (14, "BI.BANK_BS.NFA.IDR.ID",
     "Indonesia commercial bank Net Foreign Assets (BI SEKI I.3, Miliar Rp)"),
    (17, "BI.BANK_BS.CLAIMS_BI.IDR.ID",
     "Indonesia commercial bank claims on Bank Indonesia (BI SEKI I.3, Miliar Rp)"),
    (25, "BI.BANK_BS.NET_CLAIMS_GOVT.IDR.ID",
     "Indonesia commercial bank net claims on Central Govt (BI SEKI I.3, Miliar Rp)"),
    (28, "BI.BANK_BS.CLAIMS_PRIVATE.IDR.ID",
     "Indonesia commercial bank claims on Other Sectors / Private (BI SEKI I.3, Miliar Rp)"),
]


def run_fetch(since, until):
    since_dt = datetime.date.fromisoformat(since) if since else None
    until_dt = datetime.date.fromisoformat(until) if until else None
    now = datetime.datetime.now(UTC)

    print("  downloading TABEL1_3.xls ...", end=" ", flush=True)
    path = download_seki("TABEL1_3")
    print(path.name)
    parsed = parse_seki_wide_sheet(path, sheet="I.3")
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
            source_code=f"BI/SEKI/TABEL1_3/sheet=I.3/line={line_no}",
            display_name=display, unit="idr_bn", frequency="MONTHLY",
            country_iso="ID", category="balance_sheet",
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
    return run_main(vendor="bi", topic="bank_bs",
                    fetch_fn=run_fetch,
                    description=__doc__.splitlines()[0] if __doc__ else "",
                    country_code="ID")

if __name__ == "__main__":
    import sys; sys.exit(main())
