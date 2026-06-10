"""BI Indonesia SRBI auction-yield fetcher (prod).

One observation per auction-date × tenor. Default window is the trailing
14 days — BI auctions twice-weekly, so a 14-day look-back catches the
last 4 auctions on every run (idempotent: loader MERGEs on PK).

Pass ``--since`` (and optionally ``--until``) for a wider window
(e.g. ``--since 2023-09-15`` for a full backfill).

Cell mapping: 4.3 Financial Conditions — sterilisation paper yields.
"""

from __future__ import annotations

import datetime

from imdr.domains.econ.bi_srbi import (
    LAUNCH_DATE,
    fetch_srbi_window,
    make_session,
)
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc

_DEFAULT_LOOKBACK_DAYS = 14


def _imdr_code(tenor_months: int) -> str:
    return f"BI.RATES.SRBI_{tenor_months}M.LEVEL.ID"


def _indicator_for(tenor: int) -> IndicatorRow:
    return IndicatorRow(
        imdr_code=_imdr_code(tenor),
        vendor_name="BI",
        source_code=f"BI/OPERASI_MONETER/SRBI/tenor={tenor}M",
        display_name=(
            f"Indonesia SRBI weighted-average winning yield — "
            f"{tenor} months (BI Operasi Moneter, %)"
        ),
        unit="pct",
        frequency="EVENT",
        country_iso="ID",
        category="rates",
        is_seasonally_adjusted=False,
        bbg_ticker=None,
    )


def run_fetch(since, until):
    today = datetime.date.today()
    since_dt = (
        datetime.date.fromisoformat(since) if since
        else max(LAUNCH_DATE, today - datetime.timedelta(days=_DEFAULT_LOOKBACK_DAYS))
    )
    until_dt = datetime.date.fromisoformat(until) if until else today
    now = datetime.datetime.now(UTC)

    print(f"  window: {since_dt} → {until_dt}")
    session = make_session()
    auctions = fetch_srbi_window(since_dt, until_dt, session=session)

    if not auctions:
        return [], []

    by_tenor: dict[int, list] = {}
    for a in auctions:
        by_tenor.setdefault(a.tenor_months, []).append(a)

    indicators: list[IndicatorRow] = []
    observations: list[ObservationRow] = []
    for tenor, rows in sorted(by_tenor.items()):
        rows.sort(key=lambda r: r.auction_date)
        indicator = _indicator_for(tenor)
        for r in rows:
            observations.append(ObservationRow(
                imdr_code=indicator.imdr_code,
                obs_date=r.auction_date,
                vintage=0,
                release_date=now,
                value=r.wa_winning_yield_pct,
                ingested_at=now,
            ))
        indicators.append(indicator)
        print(f"    {indicator.imdr_code}: {len(rows)} obs")
    return indicators, observations


def main() -> int:
    return run_main(
        vendor="bi",
        topic="srbi",
        fetch_fn=run_fetch,
        description=__doc__.splitlines()[0] if __doc__ else "",
        country_code="ID",
    )


if __name__ == "__main__":
    import sys
    sys.exit(main())
