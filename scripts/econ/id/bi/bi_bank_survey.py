"""BI Survei Perbankan fetcher (Tabel 1 — new-loan demand).

Quarterly weighted-net-balance index of **new loan disbursement demand**
reported by Indonesian banks, 2012 Q1 →. TOTAL + 32 breakdowns
(usage · consumer sub-type · 18 economic sectors · debtor group ·
export/import orientation) = **33 indicators**.

Cell mapping: **4.1 Demand Transmission** — the lending-standards /
loan-demand cell that [`../../../../docs/admin/econ/onboarding_new_country.md`]
flags as ❌ for most EM ("Only ~20 countries publish a SLOOS-equivalent").
Indonesia does, quarterly, for free, back to 2012, and it was not onboarded.
Found 2026-09-21 while inventorying BI's report categories for Track B.

Distinct from `bi_business_survey` (SKDU), which is the *business activity*
survey answered by firms. This one is answered by **banks**, about credit.

Same two traps as `bi_pmi` — see that module for the detail:

1. The archive URL must be discovered, not constructed. BI's filenames vary
   per edition and even truncate the survey name
   (`Data-Series-Survei-Perbank-Tw-IV-2025.zip`).
2. The trailing column is BI's **forecast** for the coming quarter, flagged
   `III*`. `forecast_periods()` supplies the dates to drop.

Units: this is a weighted net balance ("SBT"), i.e. a diffusion index in
percentage-balance terms, so `unit="pct"` — NOT `index`, which is what
`bi_pmi` uses. Values above 0 mean net-positive expected demand; the series
runs roughly 0-100 in BI's presentation.

Source: `?Kategori=survei perbankan` → `Data Series Survei Perbankan *.xlsx`,
sheet `Tabel1`.
"""

from __future__ import annotations

import datetime

from imdr.domains.econ.bi_survey import (
    download_data_series_zip,
    forecast_periods,
    parse_survey_rows,
)
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.UTC

KATEGORI = "survei perbankan"
CACHE_NAME = "SURVEI_PERBANKAN"
SHEET = "Tabel1"

# Layout differs from PMI: the period header sits at rows 2/3 (not 4/5) and
# data starts at col 5, because cols 1-4 carry the two-level Indonesian and
# English labels.
_LAYOUT = dict(year_row=2, month_row=3, first_data_col=5)

# (row_index, imdr_code, display_name). Row indices are stable within an
# edition's Tabel1; the group headers (rows 4, 7, 12, 30, 33) carry both the
# group label and the first member's data, which is why the group name is
# folded into the code rather than read from the sheet.
_TARGETS: list[tuple[int, str, str]] = [
    (36, "BI.LOAN_DEMAND.TOTAL.ID", "TOTAL new loan demand"),
    # By usage
    (4, "BI.LOAN_DEMAND.USAGE.WORKING_CAPITAL.ID", "by usage — Working Capital Loans"),
    (5, "BI.LOAN_DEMAND.USAGE.INVESTMENT.ID", "by usage — Investment Loans"),
    (6, "BI.LOAN_DEMAND.USAGE.CONSUMER.ID", "by usage — Consumer Loans"),
    # Consumer sub-types
    (7, "BI.LOAN_DEMAND.CONSUMER.HOUSING.ID", "consumer — Housing/Property (KPR/KPA)"),
    (8, "BI.LOAN_DEMAND.CONSUMER.MOTOR_VEHICLE.ID", "consumer — Motor Vehicles"),
    (9, "BI.LOAN_DEMAND.CONSUMER.CREDIT_CARD.ID", "consumer — Credit Card"),
    (10, "BI.LOAN_DEMAND.CONSUMER.MULTIPURPOSE.ID", "consumer — Multi Purpose Loans"),
    (11, "BI.LOAN_DEMAND.CONSUMER.UNSECURED.ID", "consumer — Non-collateral Loans"),
    # By economic sector
    (12, "BI.LOAN_DEMAND.SECTOR.AGRICULTURE.ID", "sector — Agriculture, Hunting & Forestry"),
    (13, "BI.LOAN_DEMAND.SECTOR.FISHERY.ID", "sector — Fishery"),
    (14, "BI.LOAN_DEMAND.SECTOR.MINING.ID", "sector — Mining & Quarrying"),
    (15, "BI.LOAN_DEMAND.SECTOR.MANUFACTURING.ID", "sector — Manufacturing"),
    (16, "BI.LOAN_DEMAND.SECTOR.UTILITIES.ID", "sector — Electricity, Gas & Water"),
    (17, "BI.LOAN_DEMAND.SECTOR.CONSTRUCTION.ID", "sector — Construction"),
    (18, "BI.LOAN_DEMAND.SECTOR.TRADE.ID", "sector — Wholesale & Retail Trade"),
    (19, "BI.LOAN_DEMAND.SECTOR.ACCOM_FOOD.ID", "sector — Accommodation, Food & Beverage"),
    (20, "BI.LOAN_DEMAND.SECTOR.TRANSPORT_COMM.ID", "sector — Transport, Storage & Communication"),
    (21, "BI.LOAN_DEMAND.SECTOR.FIN_INTERMED.ID", "sector — Financial Intermediaries"),
    (22, "BI.LOAN_DEMAND.SECTOR.REAL_ESTATE.ID", "sector — Real Estate, Leasing & Company Services"),
    (23, "BI.LOAN_DEMAND.SECTOR.PUBADMIN.ID", "sector — Government Administration & Defence"),
    (24, "BI.LOAN_DEMAND.SECTOR.EDUCATION.ID", "sector — Educational Services"),
    (25, "BI.LOAN_DEMAND.SECTOR.HEALTH.ID", "sector — Health & Social Work"),
    (26, "BI.LOAN_DEMAND.SECTOR.SOCIAL_CULTURAL.ID", "sector — Public, Social & Cultural Services"),
    (27, "BI.LOAN_DEMAND.SECTOR.HOUSEHOLD_SVC.ID", "sector — Personal Services Serving Households"),
    (28, "BI.LOAN_DEMAND.SECTOR.INTL_AGENCIES.ID", "sector — International & Extra Agencies"),
    (29, "BI.LOAN_DEMAND.SECTOR.UNDEFINED.ID", "sector — Undefined Activities"),
    # By debtor group
    (30, "BI.LOAN_DEMAND.DEBTOR.MSME_KUR.ID", "debtor — MSME (KUR subsidised)"),
    (31, "BI.LOAN_DEMAND.DEBTOR.MSME_NON_KUR.ID", "debtor — MSME (non-KUR)"),
    (32, "BI.LOAN_DEMAND.DEBTOR.NON_MSME.ID", "debtor — Non-MSME"),
    # By usage orientation
    (33, "BI.LOAN_DEMAND.ORIENTATION.EXPORT.ID", "orientation — Export Loans"),
    (34, "BI.LOAN_DEMAND.ORIENTATION.IMPORT.ID", "orientation — Import Loans"),
    (35, "BI.LOAN_DEMAND.ORIENTATION.OTHER.ID", "orientation — Other Loans"),
]


def run_fetch(since, until):
    since_dt = datetime.date.fromisoformat(since) if since else None
    until_dt = datetime.date.fromisoformat(until) if until else None
    now = datetime.datetime.now(UTC)

    print(f"  discovering + downloading Survei Perbankan data-series ZIP "
          f"(Kategori={KATEGORI!r}) ...", end=" ", flush=True)
    path = download_data_series_zip(KATEGORI, CACHE_NAME)
    print(path.name)

    rows_data = parse_survey_rows(
        path, SHEET, rows=[r for r, _, _ in _TARGETS], **_LAYOUT
    )
    skip = forecast_periods(path, SHEET, **_LAYOUT)
    if skip:
        print(f"    excluding BI forecast period(s) "
              f"{sorted(d.isoformat() for d in skip)}")

    indicators: list[IndicatorRow] = []
    observations: list[ObservationRow] = []
    for row_idx, imdr_code, label in _TARGETS:
        series = rows_data.get(row_idx) or []
        if not series:
            print(f"    {imdr_code}: row {row_idx} empty — skipping")
            continue
        indicators.append(IndicatorRow(
            imdr_code=imdr_code, vendor_name="BI",
            source_code=f"BI/SurveiPerbankan/{SHEET}/row={row_idx}",
            display_name=(
                f"Indonesia new-loan demand — {label} "
                f"(BI Survei Perbankan, weighted net balance %)"
            ),
            unit="pct", frequency="QUARTERLY", country_iso="ID",
            category="credit", is_seasonally_adjusted=False, bbg_ticker=None,
        ))
        n = 0
        for obs_date, value in series:
            if value is None or obs_date in skip:
                continue
            if since_dt and obs_date < since_dt:
                continue
            if until_dt and obs_date > until_dt:
                continue
            observations.append(ObservationRow(
                imdr_code=imdr_code, obs_date=obs_date, vintage=0,
                release_date=now, value=value, ingested_at=now,
            ))
            n += 1
        print(f"    {imdr_code}: {n} obs")
    return indicators, observations


def main() -> int:
    return run_main(vendor="bi", topic="bank_survey",
                    fetch_fn=run_fetch,
                    description=__doc__.splitlines()[0] if __doc__ else "",
                    country_code="ID")


if __name__ == "__main__":
    import sys
    sys.exit(main())
