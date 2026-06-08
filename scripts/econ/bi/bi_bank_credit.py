"""BI Indonesia Bank Credit Outstanding fetcher (SEKI Table I.4).

Posisi Pinjaman/Kredit by bank-group × economic sector. Legacy sheet
"Th 2016-2024" carries 9 years of monthly history. 5 bank groups × 3
series = 15 indicators. Unit: Miliar Rupiah. Cell mapping: 4.1 Demand Transmission.
"""

from __future__ import annotations

import datetime

from imdr.domains.econ.bi_seki import download_seki, parse_seki_wide_sheet
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc

_BANK_GROUPS: list[tuple[int, str, str]] = [
    (1,   "PERSERO",       "State Banks (Bank Persero)"),
    (26,  "REGIONAL",      "Regional Government Banks (Bank Pemerintah Daerah)"),
    (51,  "PRIVATE_NATL",  "Private National Banks (Bank Swasta Nasional)"),
    (76,  "FOREIGN",       "Foreign & Joint-Venture Banks"),
    (101, "RURAL_BPR",     "Rural Credit Banks (Bank Perkreditan Rakyat / BPR)"),
]


def _build_targets() -> list[tuple[int, str, str]]:
    out: list[tuple[int, str, str]] = []
    for anchor, suffix, label in _BANK_GROUPS:
        out.append((
            anchor,
            f"BI.BANK_CREDIT.{suffix}.TOTAL.IDR.ID",
            f"Indonesia bank credit — {label}, total (BI SEKI I.4, Miliar Rp)",
        ))
        out.append((
            anchor + 1,
            f"BI.BANK_CREDIT.{suffix}.BUSINESS.IDR.ID",
            f"Indonesia bank credit — {label}, by economic sector (BI SEKI I.4, Miliar Rp)",
        ))
        out.append((
            anchor + 19,
            f"BI.BANK_CREDIT.{suffix}.CONSUMER.IDR.ID",
            f"Indonesia bank credit — {label}, household consumer (BI SEKI I.4, Miliar Rp)",
        ))
    return out


_TARGETS = _build_targets()


def run_fetch(since, until):
    since_dt = datetime.date.fromisoformat(since) if since else None
    until_dt = datetime.date.fromisoformat(until) if until else None
    now = datetime.datetime.now(UTC)

    print("  downloading TABEL1_4.xls ...", end=" ", flush=True)
    path = download_seki("TABEL1_4")
    print(path.name)
    parsed = parse_seki_wide_sheet(path, sheet="Th 2016-2024")
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
            source_code=f"BI/SEKI/TABEL1_4/sheet=Th 2016-2024/line={line_no}",
            display_name=display, unit="idr_bn", frequency="MONTHLY",
            country_iso="ID", category="credit",
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
    return run_main(vendor="bi", topic="bank_credit",
                    fetch_fn=run_fetch,
                    description=__doc__.splitlines()[0] if __doc__ else "")

if __name__ == "__main__":
    import sys; sys.exit(main())
