"""BI Indonesia fiscal aggregates fetcher (SEKI Section IV).

Revenue (TABEL4_1), Expenditure (TABEL4_2), Financing (TABEL4_3) —
realisasi (actuals) at headline-aggregate level. Annual, IDR billion.
Cell mapping: 1.2 Fiscal Demand.
"""

from __future__ import annotations

import datetime

from imdr.domains.econ.bi_seki import download_seki, parse_seki_annual_sheet
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc

# Bucketed under "other" until a dedicated "fiscal" code is added to
# econ.dim_indicator_category + VALID_CATEGORIES in
# src/imdr/domains/econ/schema.py. Tracked in
# docs/admin/econ/indonesia/id_coverage_plan.md (Phase E follow-on).
_FISCAL_CATEGORY_PLACEHOLDER = "other"

_TARGETS: list[tuple[str, str, int, str, str]] = [
    ("TABEL4_1", "4.1", 29,
     "BI.FISCAL.REVENUE.TOTAL.IDR.ID",
     "Indonesia total government revenue, realisasi (BI SEKI IV.1, Miliar Rp)"),
    ("TABEL4_1", "4.1", 31,
     "BI.FISCAL.TAX_REVENUE.IDR.ID",
     "Indonesia tax revenue, realisasi (BI SEKI IV.1, Miliar Rp)"),
    ("TABEL4_2", "4.2", 26,
     "BI.FISCAL.EXPEND.TOTAL.IDR.ID",
     "Indonesia total government expenditure, realisasi (BI SEKI IV.2, Miliar Rp)"),
    ("TABEL4_2", "4.2", 27,
     "BI.FISCAL.EXPEND.CENTRAL.IDR.ID",
     "Indonesia central government expenditure, realisasi (BI SEKI IV.2, Miliar Rp)"),
    ("TABEL4_3", "4.3", 22,
     "BI.FISCAL.BALANCE.IDR.ID",
     "Indonesia fiscal balance (surplus/deficit), realisasi (BI SEKI IV.3, Miliar Rp)"),
    ("TABEL4_3", "4.3", 23,
     "BI.FISCAL.NET_FINANCING.IDR.ID",
     "Indonesia net fiscal financing, realisasi (BI SEKI IV.3, Miliar Rp)"),
]


def run_fetch(since, until):
    since_dt = datetime.date.fromisoformat(since) if since else None
    until_dt = datetime.date.fromisoformat(until) if until else None
    now = datetime.datetime.now(UTC)
    table_cache: dict[tuple[str, str], dict] = {}
    indicators: list[IndicatorRow] = []
    observations: list[ObservationRow] = []

    for table_id, sheet, line, imdr_code, display in _TARGETS:
        cache_key = (table_id, sheet)
        if cache_key not in table_cache:
            print(f"  downloading {table_id}.xls (sheet={sheet}) ...", end=" ", flush=True)
            path = download_seki(table_id)
            table_cache[cache_key] = parse_seki_annual_sheet(path, sheet=sheet)
            print(f"{len(table_cache[cache_key])} line items")
        parsed = table_cache[cache_key]
        series = parsed.get(line)
        if not series:
            print(f"    {imdr_code}: line {line} missing — skipping")
            continue
        indicator = IndicatorRow(
            imdr_code=imdr_code, vendor_name="BI",
            source_code=f"BI/SEKI/{table_id}/sheet={sheet}/line={line}",
            display_name=display, unit="idr_bn", frequency="ANNUAL",
            country_iso="ID", category=_FISCAL_CATEGORY_PLACEHOLDER,
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
    return run_main(vendor="bi", topic="fiscal",
                    fetch_fn=run_fetch,
                    description=__doc__.splitlines()[0] if __doc__ else "",
                    country_code="ID")

if __name__ == "__main__":
    import sys; sys.exit(main())
