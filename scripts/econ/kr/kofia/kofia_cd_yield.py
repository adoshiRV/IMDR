"""KOFIA freeSIS — CD (certificate of deposit) representative yield, daily.

Source: Korea Financial Investment Association freeSIS, 단기자금 > CD수익률
(service STATBND0100000320). The daily 91-day CD benchmark yield reported by
the bond-rating panel, split 시중은행 (commercial banks) / 특수은행 (special
banks). We take the 대표수익률 (representative, 80–100 rating) cut:
  TMPV2 = 시중은행 (headline KRW money-market benchmark) · TMPV3 = 특수은행.

Distinct from BOK.BANK_RATE.CD_91D.KR (monthly, deposit-rate table): this is
the DAILY market benchmark — the rate that prices KRW IRS and FRNs.

Cell mapping: 4.3 Financial Conditions (money-market benchmark rate).

Usage:
    python -m scripts.econ.kr.kofia.kofia_cd_yield                    # live (90d)
    python -m scripts.econ.kr.kofia.kofia_cd_yield --since 2009-01-01  # backfill
"""

from __future__ import annotations

import datetime

from imdr.domains.econ.kofia_http import fetch_freesis_rows, make_session
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc
_SERVICE = "STATBND0100000320"
_HISTORY_START = datetime.date(2009, 1, 1)
_LIVE_LOOKBACK_DAYS = 90

# TMPV column -> (imdr suffix, display, korean)
_CUTS: list[tuple[str, str, str, str]] = [
    ("TMPV2", "YIELD",              "CD 91-day representative yield, commercial banks", "대표수익률·시중은행"),
    ("TMPV3", "YIELD.SPECIAL_BANK", "CD 91-day representative yield, special banks",    "대표수익률·특수은행"),
]


def _to_pct(raw: object) -> float | None:
    if raw in (None, "", "-"):
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def run_fetch(
    since: str | None,
    until: str | None,
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    today = datetime.date.today()
    since_dt = datetime.date.fromisoformat(since) if since else (
        today - datetime.timedelta(days=_LIVE_LOOKBACK_DAYS))
    # Exclude the current day in live mode (see kofia_cd_trading): the CD panel
    # yield finalizes intraday and the insert-only loader would lock a partial.
    until_dt = datetime.date.fromisoformat(until) if until else (
        today - datetime.timedelta(days=1))
    if since_dt < _HISTORY_START:
        since_dt = _HISTORY_START
    now = datetime.datetime.now(UTC)

    session = make_session()
    print(f"  Fetching CD수익률 ({_SERVICE}) {since_dt}..{until_dt} ...",
          end=" ", flush=True)
    rows = fetch_freesis_rows(session, _SERVICE, {
        "tmpV40": "1", "tmpV41": "1", "tmpV1": "D",
        "tmpV45": since_dt.strftime("%Y%m%d"),
        "tmpV46": until_dt.strftime("%Y%m%d"),
    })
    print(f"{len(rows)} rows")

    indicators: list[IndicatorRow] = []
    for col, suffix, display, kor in _CUTS:
        indicators.append(IndicatorRow(
            imdr_code=f"KOFIA.CD.{suffix}.KR",
            vendor_name="KOFIA",
            source_code=f"freesis/{_SERVICE}/{col}",
            display_name=f"Korea {display}, % p.a. [{kor}] (KOFIA freeSIS)",
            unit="pct",
            frequency="DAILY",
            country_iso="KR",
            category="rates",
            is_seasonally_adjusted=False,
            bbg_ticker=None,
        ))

    observations: list[ObservationRow] = []
    for r in rows:
        raw_date = r.get("TMPV1")  # "YYYY-MM-DD"
        try:
            obs_date = datetime.date.fromisoformat(str(raw_date))
        except (TypeError, ValueError):
            continue
        if obs_date < since_dt or obs_date > until_dt:
            continue
        for col, suffix, _display, _kor in _CUTS:
            val = _to_pct(r.get(col))
            if val is None:  # '-' (no panel quote that day, esp. special banks)
                continue
            observations.append(ObservationRow(
                imdr_code=f"KOFIA.CD.{suffix}.KR",
                obs_date=obs_date,
                vintage=0,
                release_date=now,
                value=val,
                ingested_at=now,
            ))

    return indicators, observations


def main() -> int:
    return run_main(
        vendor="kofia",
        topic="cd_yield",
        fetch_fn=run_fetch,
        description=__doc__.splitlines()[0] if __doc__ else "",
        country_code="KR",
    )


if __name__ == "__main__":
    import sys
    sys.exit(main())
