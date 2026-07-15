"""Treasury Debt to the Penny fetcher — cells 1.2 / 4.2 Balance Sheets.

Pulls daily total public debt outstanding (tot_pub_debt_out_amt) from the
Treasury Fiscal Data API. Raw values are in USD; stored as usd_mn (÷ 1e6).
obs_date = record_date directly. Treasury publishes on business days only;
~2,800 rows from 2015-01-01 to present.

IMDR code:
    TREASURY.DEBT.TOTAL_PUBLIC.US  (DAILY, usd_mn)

Usage:
    python -m scripts.econ.us.treasury.treasury_debt
    python -m scripts.econ.us.treasury.treasury_debt --since 2024-01-01 --no-load
"""

from __future__ import annotations

import datetime

from imdr.domains.econ.treasury_fiscaldata import TreasuryClient
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc

_ENDPOINT = "v2/accounting/od/debt_to_penny"
_FIELDS = "record_date,tot_pub_debt_out_amt"


def _indicators() -> list[IndicatorRow]:
    return [
        IndicatorRow(
            imdr_code="TREASURY.DEBT.TOTAL_PUBLIC.US",
            vendor_name="TREASURY_US",
            source_code="debt_to_penny:tot_pub_debt_out_amt",
            display_name="US Total Public Debt Outstanding (Debt to the Penny)",
            unit="usd_mn",
            frequency="DAILY",
            country_iso="US",
            category="balance_sheet",
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
            filter_=f"record_date:gte:{since_dt.isoformat()},record_date:lte:{until_dt.isoformat()}",
            sort="-record_date",
        )

    print(f"  raw debt rows: {len(raw)}")

    observations: list[ObservationRow] = []
    for row in raw:
        try:
            obs_date = datetime.date.fromisoformat(row["record_date"])
        except (TypeError, ValueError):
            continue

        raw_val = row.get("tot_pub_debt_out_amt")
        try:
            # tot_pub_debt_out_amt is in raw dollars; store as usd_mn.
            value = float(raw_val) / 1e6 if raw_val is not None else None
        except (TypeError, ValueError):
            value = None

        observations.append(ObservationRow(
            imdr_code="TREASURY.DEBT.TOTAL_PUBLIC.US",
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
        topic="debt",
        fetch_fn=run_fetch,
        description=__doc__.splitlines()[0] if __doc__ else "",
        country_code="US",
    )


if __name__ == "__main__":
    import sys
    sys.exit(main())
