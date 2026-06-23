"""Treasury MTS (Monthly Treasury Statement) fetcher — cell 1.2 Fiscal Demand.

Pulls monthly federal receipts, outlays, and surplus/deficit from the
Monthly Treasury Statement (mts_table_1) via the Treasury Fiscal Data API.
Each record_date publication covers all months in the current fiscal year;
we keep the latest published figure per calendar month.

US fiscal year runs Oct 1 – Sep 30. Obs dates are derived from the
classification_desc month name + record_fiscal_year, with Oct/Nov/Dec
mapped to the FY-opening calendar year and Jan-Sep to the following year.

Values stored as usd_mn (raw USD ÷ 1e6). Deficit sign-flipped so that
positive = surplus, negative = deficit.

Usage:
    python -m scripts.econ.us.treasury.treasury_mts
    python -m scripts.econ.us.treasury.treasury_mts --since 2020-01-01 --no-load
"""

from __future__ import annotations

import datetime

from imdr.domains.econ.treasury_fiscaldata import TreasuryClient
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc

_ENDPOINT = "v1/accounting/mts/mts_table_1"
_FIELDS = (
    "record_date,classification_desc,"
    "current_month_gross_rcpt_amt,current_month_gross_outly_amt,current_month_dfct_sur_amt,"
    "record_type_cd,record_fiscal_year,record_calendar_year,record_calendar_month,"
    "parent_id,src_line_nbr"
)

_MONTH_NAME_TO_NUM: dict[str, int] = {
    "January": 1, "February": 2, "March": 3, "April": 4,
    "May": 5, "June": 6, "July": 7, "August": 8, "September": 9,
    "October": 10, "November": 11, "December": 12,
}

# US fiscal year Oct-Sep: Oct/Nov/Dec are the first three months of the FY.
_FY_FIRST_MONTHS = {10, 11, 12}

# Bucketed under "other" until a dedicated "fiscal" code is added to
# econ.dim_indicator_category + VALID_CATEGORIES in
# src/imdr/domains/econ/schema.py.
_FISCAL_CATEGORY_PLACEHOLDER = "other"


def _obs_date_from_row(row: dict) -> datetime.date | None:
    """Derive the calendar-month obs_date from an MTS MTH row.

    The current-FY block rows have src_line_nbr >= 15. We skip prior-FY
    block rows (src < 15) because the current-FY block republishes those
    months and deduplication on obs_date handles the rest.
    """
    try:
        src = int(row["src_line_nbr"])
        pub_date = datetime.date.fromisoformat(row["record_date"])
        mn = row["classification_desc"]
    except (TypeError, ValueError, KeyError):
        return None

    month_num = _MONTH_NAME_TO_NUM.get(mn)
    if month_num is None:
        return None

    if src < 15:
        return None

    fy_start_year = pub_date.year if pub_date.month >= 10 else pub_date.year - 1

    if month_num in _FY_FIRST_MONTHS:
        cal_year = fy_start_year
    else:
        cal_year = fy_start_year + 1

    try:
        return datetime.date(cal_year, month_num, 1)
    except ValueError:
        return None


def _indicators() -> list[IndicatorRow]:
    return [
        IndicatorRow(
            imdr_code="TREASURY.FISCAL.RECEIPTS.US",
            vendor_name="TREASURY_US",
            source_code="mts_table_1:receipts",
            display_name="US Federal Government Monthly Receipts (MTS)",
            unit="usd_mn",
            frequency="MONTHLY",
            country_iso="US",
            category=_FISCAL_CATEGORY_PLACEHOLDER,
            is_seasonally_adjusted=False,
        ),
        IndicatorRow(
            imdr_code="TREASURY.FISCAL.OUTLAYS.US",
            vendor_name="TREASURY_US",
            source_code="mts_table_1:outlays",
            display_name="US Federal Government Monthly Outlays (MTS)",
            unit="usd_mn",
            frequency="MONTHLY",
            country_iso="US",
            category=_FISCAL_CATEGORY_PLACEHOLDER,
            is_seasonally_adjusted=False,
        ),
        IndicatorRow(
            imdr_code="TREASURY.FISCAL.DEFICIT.US",
            vendor_name="TREASURY_US",
            source_code="mts_table_1:deficit_surplus",
            display_name="US Federal Government Monthly Surplus/Deficit (MTS, + = surplus)",
            unit="usd_mn",
            frequency="MONTHLY",
            country_iso="US",
            category=_FISCAL_CATEGORY_PLACEHOLDER,
            is_seasonally_adjusted=False,
        ),
    ]


def run_fetch(
    since: str | None,
    until: str | None,
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    since_dt = datetime.date.fromisoformat(since) if since else datetime.date(2015, 1, 1)
    until_dt = datetime.date.fromisoformat(until) if until else datetime.date.today()
    now = datetime.datetime.now(UTC)

    indicators = _indicators()

    with TreasuryClient() as client:
        raw = client.get_all(
            _ENDPOINT,
            fields=_FIELDS,
            filter_=f"record_type_cd:eq:MTH,record_date:gte:{since_dt.isoformat()}",
            sort="-record_date",
        )

    print(f"  raw MTS rows (MTH type): {len(raw)}")

    dated: list[tuple[datetime.date, dict]] = []
    for row in raw:
        obs_date = _obs_date_from_row(row)
        if obs_date is not None:
            dated.append((obs_date, row))
    print(f"  after current-FY block filter: {len(dated)}")

    # Keep the most-recently-published figure per calendar month.
    # dated is already sorted newest-first (API returns -record_date).
    best: dict[datetime.date, dict] = {}
    for obs_date, row in dated:
        if obs_date not in best:
            best[obs_date] = row

    observations: list[ObservationRow] = []
    for obs_date, row in sorted(best.items()):
        if obs_date < since_dt or obs_date > until_dt:
            continue

        def _amt(field: str) -> float | None:
            v = row.get(field)
            try:
                return float(v) / 1e6 if v is not None else None
            except (TypeError, ValueError):
                return None

        rcpt = _amt("current_month_gross_rcpt_amt")
        outly = _amt("current_month_gross_outly_amt")
        # Raw dfct_sur_amt: positive = deficit, negative = surplus.
        # Stored sign-flipped: positive = surplus, negative = deficit.
        raw_dfct = _amt("current_month_dfct_sur_amt")
        surplus = -raw_dfct if raw_dfct is not None else None

        for imdr_code, value in [
            ("TREASURY.FISCAL.RECEIPTS.US", rcpt),
            ("TREASURY.FISCAL.OUTLAYS.US", outly),
            ("TREASURY.FISCAL.DEFICIT.US", surplus),
        ]:
            observations.append(ObservationRow(
                imdr_code=imdr_code,
                obs_date=obs_date,
                vintage=0,
                release_date=now,
                value=value,
                ingested_at=now,
            ))

    return indicators, observations


def main() -> int:
    return run_main(
        vendor="treasury_us",
        topic="mts",
        fetch_fn=run_fetch,
        description=__doc__.splitlines()[0] if __doc__ else "",
        country_code="US",
    )


if __name__ == "__main__":
    import sys
    sys.exit(main())
