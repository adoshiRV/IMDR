"""BI Indonesia bank + money-market rates fetcher (SEKI I.25/I.26/I.28).

Policy rates, interbank rates (PUAB/INDONIA), Bank Umum lending rates by
loan type, and Bank Umum time-deposit rates by tenor. 13 indicators total.
Unit: Percent. Monthly. Cell mapping: 4.3 Financial Conditions.
"""

from __future__ import annotations

import datetime

from imdr.domains.econ.bi_seki import download_seki, parse_seki_wide_sheet
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc

_TABLE_OFFSETS: dict[str, tuple[int, int, int]] = {
    "TABEL1_25_1": (4, 5, 6),
    "TABEL1_25_2": (4, 5, 6),
    "TABEL1_26":   (3, 4, 5),
    "TABEL1_28":   (3, 4, 5),
}

_TARGETS: list[tuple[str, str, int, str, str]] = [
    ("TABEL1_25_1", "1.25A_2", 55,
     "BI.RATES.DEPOSIT_FACILITY.LEVEL.ID",
     "Indonesia Deposit Facility rate, 1-day afternoon (BI SEKI I.25.A, %)"),
    ("TABEL1_25_1", "1.25A_2", 57,
     "BI.RATES.LENDING_FACILITY.LEVEL.ID",
     "Indonesia Lending Facility rate (BI SEKI I.25.A, %)"),
    ("TABEL1_25_2", "1.25B", 2,
     "BI.RATES.PUAB_OVERNIGHT.LEVEL.ID",
     "Indonesia PUAB interbank overnight rate, IDR morning (BI SEKI I.25.B, %)"),
    ("TABEL1_25_2", "1.25B", 3,
     "BI.RATES.PUAB_ALL_TENORS.LEVEL.ID",
     "Indonesia PUAB interbank rate, all-tenors aggregate (BI SEKI I.25.B, %)"),
    ("TABEL1_25_2", "1.25B", 14,
     "BI.RATES.INDONIA.LEVEL.ID",
     "Indonesia INDONIA — Indonesia Overnight Index Average (BI SEKI I.25.B, %)"),
    ("TABEL1_25_2", "1.25B", 16,
     "BI.RATES.INDONIA_30D.LEVEL.ID",
     "Indonesia Compounded INDONIA 30-day (BI SEKI I.25.B, %)"),
    ("TABEL1_25_2", "1.25B", 17,
     "BI.RATES.INDONIA_90D.LEVEL.ID",
     "Indonesia Compounded INDONIA 90-day (BI SEKI I.25.B, %)"),
    ("TABEL1_26", "1.26", 18,
     "BI.RATES.LEND_BANK_UMUM_WC.LEVEL.ID",
     "Indonesia Bank Umum lending rate — Working Capital (BI SEKI I.26, %)"),
    ("TABEL1_26", "1.26", 19,
     "BI.RATES.LEND_BANK_UMUM_INV.LEVEL.ID",
     "Indonesia Bank Umum lending rate — Investment (BI SEKI I.26, %)"),
    ("TABEL1_26", "1.26", 20,
     "BI.RATES.LEND_BANK_UMUM_CONS.LEVEL.ID",
     "Indonesia Bank Umum lending rate — Consumer (BI SEKI I.26, %)"),
    ("TABEL1_28", "1.28", 27,
     "BI.RATES.DEPOSIT_BANK_UMUM_3M.LEVEL.ID",
     "Indonesia Bank Umum time-deposit rate — 3 months (BI SEKI I.28, %)"),
    ("TABEL1_28", "1.28", 28,
     "BI.RATES.DEPOSIT_BANK_UMUM_6M.LEVEL.ID",
     "Indonesia Bank Umum time-deposit rate — 6 months (BI SEKI I.28, %)"),
    ("TABEL1_28", "1.28", 29,
     "BI.RATES.DEPOSIT_BANK_UMUM_12M.LEVEL.ID",
     "Indonesia Bank Umum time-deposit rate — 12 months (BI SEKI I.28, %)"),
]


def run_fetch(since, until):
    since_dt = datetime.date.fromisoformat(since) if since else None
    until_dt = datetime.date.fromisoformat(until) if until else None
    now = datetime.datetime.now(UTC)
    cache: dict[tuple[str, str], dict] = {}
    indicators: list[IndicatorRow] = []
    observations: list[ObservationRow] = []

    for table_id, sheet, line, imdr_code, display in _TARGETS:
        key = (table_id, sheet)
        if key not in cache:
            print(f"  downloading {table_id} ...", end=" ", flush=True)
            path = download_seki(table_id)
            yr_row, mo_row, data_start = _TABLE_OFFSETS[table_id]
            cache[key] = parse_seki_wide_sheet(
                path, sheet=sheet,
                year_row=yr_row, month_row=mo_row, data_start_row=data_start,
            )
            print(f"{len(cache[key])} line items")
        parsed = cache[key]
        series = parsed.get(line) or []
        if not series:
            print(f"    {imdr_code}: line {line} missing — skipping")
            continue

        indicator = IndicatorRow(
            imdr_code=imdr_code, vendor_name="BI",
            source_code=f"BI/SEKI/{table_id}/sheet={sheet}/line={line}",
            display_name=display, unit="pct", frequency="MONTHLY",
            country_iso="ID", category="rates",
            is_seasonally_adjusted=False, bbg_ticker=None,
        )
        obs_emitted = 0
        for obs_date, value, _label in series:
            if value is None:
                continue
            if since_dt and obs_date < since_dt:
                continue
            if until_dt and obs_date > until_dt:
                continue
            observations.append(ObservationRow(
                imdr_code=imdr_code, obs_date=obs_date, vintage=0,
                release_date=now, value=value, ingested_at=now,
            ))
            obs_emitted += 1
        if obs_emitted == 0:
            continue
        indicators.append(indicator)
        print(f"    {imdr_code}: {obs_emitted} obs")
    return indicators, observations


def main() -> int:
    return run_main(vendor="bi", topic="bank_rates",
                    fetch_fn=run_fetch,
                    description=__doc__.splitlines()[0] if __doc__ else "")

if __name__ == "__main__":
    import sys; sys.exit(main())
