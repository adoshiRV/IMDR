"""KOFIA freeSIS — MMF (money-market fund) daily fund flows.

Source: Korea Financial Investment Association freeSIS, 펀드 > 기간자금유출입
(service STATFND0100100030) filtered to fund type 단기금융 (MMF, T1111=05 via
param tmpV3). Daily settlement-date flows back to 2006-05, three cuts (total /
domestic-cut only stored as total here):
  설정 (subscriptions / inflow) / 해지 (redemptions / outflow) / 순증 (net).

Net = inflow - outflow (verified against the source arithmetic). Values are
published in 억원 (100 mn KRW); stored as krw_bn. Re-investment is excluded;
flows are confirmed (settlement-date) basis per KOFIA.

This is the literal "MMF flow" series. MMF stock levels (net assets / setup
principal, by retail/institutional) are the sibling fetcher kofia_mmf_level.py.

Cell mapping: 4.4 Policy Reaction / liquidity (money-market fund demand).

Usage:
    python -m scripts.econ.kr.kofia.kofia_mmf_flows                    # live (90d)
    python -m scripts.econ.kr.kofia.kofia_mmf_flows --since 2006-01-01  # backfill
"""

from __future__ import annotations

import datetime

from imdr.domains.econ.kofia_http import EOK_TO_KRW_BN, fetch_freesis_rows, make_session
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc
_SERVICE = "STATFND0100100030"
_HISTORY_START = datetime.date(2006, 1, 1)
_LIVE_LOOKBACK_DAYS = 90

# TMPV column (전체/total) -> (imdr suffix, display, korean)
_CUTS: list[tuple[str, str, str, str]] = [
    ("TMPV4", "NET_FLOW", "MMF net flow (KRW bn)", "순증"),
    ("TMPV2", "INFLOW",   "MMF subscriptions / inflow (KRW bn)", "설정"),
    ("TMPV3", "OUTFLOW",  "MMF redemptions / outflow (KRW bn)", "해지"),
]


def _to_krw_bn(raw: object) -> float | None:
    if raw in (None, ""):
        return None
    try:
        return float(raw) * EOK_TO_KRW_BN
    except (TypeError, ValueError):
        return None


def run_fetch(
    since: str | None,
    until: str | None,
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    today = datetime.date.today()
    since_dt = datetime.date.fromisoformat(since) if since else (
        today - datetime.timedelta(days=_LIVE_LOOKBACK_DAYS))
    # Exclude the current day in live mode (see kofia_cd_trading): freeSIS
    # accrues intraday and the insert-only loader would lock the partial value.
    until_dt = datetime.date.fromisoformat(until) if until else (
        today - datetime.timedelta(days=1))
    if since_dt < _HISTORY_START:
        since_dt = _HISTORY_START
    now = datetime.datetime.now(UTC)

    session = make_session()
    print(f"  Fetching MMF flows 기간자금유출입 ({_SERVICE}, type=단기금융) "
          f"{since_dt}..{until_dt} ...", end=" ", flush=True)
    rows = fetch_freesis_rows(session, _SERVICE, {
        "tmpV40": "100000000", "tmpV41": "1",
        "tmpV30": since_dt.strftime("%Y%m%d"),
        "tmpV31": until_dt.strftime("%Y%m%d"),
        "tmpV37": "0", "tmpV5": "", "tmpV7": "1",
        "tmpV3": "05",  # T1111 fund type = 단기금융 (MMF)
        "tmpV11": "", "tmpV19": "Y",
    })
    print(f"{len(rows)} rows")

    indicators: list[IndicatorRow] = []
    for col, suffix, display, kor in _CUTS:
        indicators.append(IndicatorRow(
            imdr_code=f"KOFIA.MMF.{suffix}.KR",
            vendor_name="KOFIA",
            source_code=f"freesis/{_SERVICE}/T1111=05/{col}",
            display_name=f"Korea {display} [{kor}] (KOFIA freeSIS)",
            unit="krw_bn",
            frequency="DAILY",
            country_iso="KR",
            category="liquidity",
            is_seasonally_adjusted=False,
            bbg_ticker=None,
        ))

    observations: list[ObservationRow] = []
    for r in rows:
        raw_date = r.get("TMPV1")  # "YYYYMMDD"
        try:
            s = str(raw_date)
            obs_date = datetime.date(int(s[:4]), int(s[4:6]), int(s[6:8]))
        except (TypeError, ValueError, IndexError):
            continue
        if obs_date < since_dt or obs_date > until_dt:
            continue
        for col, suffix, _display, _kor in _CUTS:
            observations.append(ObservationRow(
                imdr_code=f"KOFIA.MMF.{suffix}.KR",
                obs_date=obs_date,
                vintage=0,
                release_date=now,
                value=_to_krw_bn(r.get(col)),
                ingested_at=now,
            ))

    return indicators, observations


def main() -> int:
    return run_main(
        vendor="kofia",
        topic="mmf_flows",
        fetch_fn=run_fetch,
        description=__doc__.splitlines()[0] if __doc__ else "",
        country_code="KR",
    )


if __name__ == "__main__":
    import sys
    sys.exit(main())
