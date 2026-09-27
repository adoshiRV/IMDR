"""KOFIA freeSIS — MMF (money-market fund) stock levels.

Source: Korea Financial Investment Association freeSIS, 펀드 > 기간별 MMF현황
(service STATFND0400000050). Per-date industry snapshot of MMF size, summed to
the 합계 (total) row, split 전체 / 개인 (retail) / 법인 (institutional). We take
the 순자산총액 (net assets, tmpV39=2) metric. Available back to ~2010.

Indicators (all krw_bn, category liquidity):
  KOFIA.MMF.NAV.KR / .INDIV.KR / .CORP.KR   net assets — total / retail / instit.

MMF *setup principal* is NOT here — it lives in kofia_fund_aum.py as
KOFIA.FUND_AUM.MMF.KR (daily, back to 2004). This series' unique value is
net-assets (vs principal) and the retail/institutional split.

Because the source is a per-date snapshot (no range query), history is built by
iterating dates:
  * backfill  (--since given): month-END snapshots (walking back to the last
    business day when the calendar month-end is a holiday).
  * live      (no --since): the single most-recent business-day snapshot, so
    daily runs accumulate a daily level series going forward.

The retail-vs-institutional split is the signal: MMF is where corporates and
funds park cash, so 법인 dominates and its swings lead money-market stress.

Cell mapping: 4.4 Policy Reaction / liquidity (money-market fund stock).

Usage:
    python -m scripts.econ.kr.kofia.kofia_mmf_level                     # live (latest)
    python -m scripts.econ.kr.kofia.kofia_mmf_level --since 2010-01-01   # backfill month-ends
"""

from __future__ import annotations

import calendar
import datetime

from imdr.domains.econ.kofia_http import EOK_TO_KRW_BN, fetch_freesis_rows, make_session
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc
_SERVICE = "STATFND0400000050"
_HISTORY_START = datetime.date(2010, 1, 1)
_WALKBACK_DAYS = 7  # step back from a candidate date when the snapshot is empty

# MMF NET ASSETS (순자산총액, tmpV39=2), total / retail / institutional.
# Setup-principal is NOT emitted here — it lives in kofia_fund_aum.py as
# KOFIA.FUND_AUM.MMF.KR (daily, longer history). This series adds what fund_aum
# lacks: net assets (vs principal) and the retail/institutional split.
# (TMPV column, imdr suffix, display, korean)
_METRICS: list[tuple[str, str, str, str]] = [
    ("TMPV2", "NAV",       "MMF net assets, total (KRW bn)",         "순자산총액·전체"),
    ("TMPV3", "NAV.INDIV", "MMF net assets, retail (KRW bn)",        "순자산총액·개인"),
    ("TMPV4", "NAV.CORP",  "MMF net assets, institutional (KRW bn)", "순자산총액·법인"),
]


def _to_krw_bn(raw: object) -> float | None:
    if raw in (None, ""):
        return None
    try:
        return float(raw) * EOK_TO_KRW_BN
    except (TypeError, ValueError):
        return None


def _month_ends(start: datetime.date, end: datetime.date) -> list[datetime.date]:
    out: list[datetime.date] = []
    y, m = start.year, start.month
    while True:
        last = calendar.monthrange(y, m)[1]
        d = datetime.date(y, m, last)
        if d > end:
            break
        if d >= start:
            out.append(d)
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return out


def _snapshot_total(session, as_of: datetime.date, tmpv39: str) -> dict | None:
    """Return the 합계 row for a date+metric, or None if no data that day."""
    rows = fetch_freesis_rows(session, _SERVICE, {
        "tmpV40": "100000000", "tmpV41": "1",
        "tmpV34": as_of.strftime("%Y%m%d"), "tmpV39": tmpv39, "tmpV1": "D",
    })
    return next((r for r in rows if r.get("TMPV1") == "합계"), None)


def _resolve_snapshot(
    session, target: datetime.date
) -> tuple[datetime.date, dict] | None:
    """Walk back up to _WALKBACK_DAYS from target to the last day WITH data.
    Return (date, 합계-row) so the caller need not re-fetch."""
    for i in range(_WALKBACK_DAYS + 1):
        d = target - datetime.timedelta(days=i)
        row = _snapshot_total(session, d, "2")  # tmpV39=2 = 순자산총액 (NAV)
        if row is not None:
            return d, row
    return None


def run_fetch(
    since: str | None,
    until: str | None,
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    today = datetime.date.today()
    until_dt = datetime.date.fromisoformat(until) if until else today
    now = datetime.datetime.now(UTC)
    session = make_session()

    if since:
        since_dt = max(datetime.date.fromisoformat(since), _HISTORY_START)
        targets = _month_ends(since_dt, until_dt)
        mode = f"backfill month-ends {since_dt}..{until_dt} ({len(targets)} pts)"
    else:
        targets = [until_dt]  # _resolve_snapshot walks back to the latest with data
        mode = f"live latest snapshot (<= {until_dt})"
    print(f"  MMF level ({_SERVICE}): {mode}")

    indicators: list[IndicatorRow] = []
    for _col, suffix, display, kor in _METRICS:
        indicators.append(IndicatorRow(
            imdr_code=f"KOFIA.MMF.{suffix}.KR",
            vendor_name="KOFIA",
            source_code=f"freesis/{_SERVICE}/tmpV39=2/{_col}",
            display_name=f"Korea {display} [{kor}] (KOFIA freeSIS)",
            unit="krw_bn",
            frequency="DAILY",
            country_iso="KR",
            category="liquidity",
            is_seasonally_adjusted=False,
            bbg_ticker=None,
        ))

    observations: list[ObservationRow] = []
    n_ok = 0
    for tgt in targets:
        resolved = _resolve_snapshot(session, tgt)
        if resolved is None:
            continue
        as_of, row = resolved
        n_ok += 1
        for col, suffix, _display, _kor in _METRICS:
            val = _to_krw_bn(row.get(col))
            if val is None:
                continue
            observations.append(ObservationRow(
                imdr_code=f"KOFIA.MMF.{suffix}.KR",
                obs_date=as_of,
                vintage=0,
                release_date=now,
                value=val,
                ingested_at=now,
            ))
    print(f"  resolved {n_ok}/{len(targets)} snapshot dates")

    return indicators, observations


def main() -> int:
    return run_main(
        vendor="kofia",
        topic="mmf_level",
        fetch_fn=run_fetch,
        description=__doc__.splitlines()[0] if __doc__ else "",
        country_code="KR",
    )


if __name__ == "__main__":
    import sys
    sys.exit(main())
