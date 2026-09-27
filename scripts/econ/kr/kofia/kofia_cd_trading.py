"""KOFIA freeSIS — CD (certificate of deposit) secondary-market trading volume.

Source: Korea Financial Investment Association freeSIS, 단기자금 > CD거래현황
(service STATBND0100000050). Daily dealer-reported CD turnover in the KRW
money market, back to 2003-01-01. Three cuts:
  매도 (sell) / 매수 (buy) / 합계 (total) — the total is the headline.

Values are published in 억원 (100 mn KRW); stored as krw_bn.

NOTE (methodology break): per KOFIA, data before 2009-02-04 is based on the
CD-yield reports of 10 securities firms trading AAA commercial-bank CDs; from
2009-02-04 the current reporting basis applies. History is continuous but the
pre-2009 level is a narrower panel.

This is the money-market TRADING-VOLUME series. The CD 91-day *rate* is a
separate KOSIS series (BOK.BANK_RATE.CD_91D.KR). "Who traded" (by investor)
is not in freeSIS — see scripts/econ/kr/ksd/ (KSD data.go.kr, key-gated).

Cell mapping: 4.3 Financial Conditions (money-market liquidity/activity).

Usage:
    python -m scripts.econ.kr.kofia.kofia_cd_trading                 # live (90d)
    python -m scripts.econ.kr.kofia.kofia_cd_trading --since 2003-01-01  # backfill
"""

from __future__ import annotations

import datetime

from imdr.domains.econ.kofia_http import EOK_TO_KRW_BN, fetch_freesis_rows, make_session
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc
_SERVICE = "STATBND0100000050"
_HISTORY_START = datetime.date(2003, 1, 1)
_LIVE_LOOKBACK_DAYS = 90

# TMPV column -> (imdr suffix, display, korean)
_CUTS: list[tuple[str, str, str, str]] = [
    ("TMPV4", "TRADE_TOTAL", "CD trading, total (KRW bn)", "합계"),
    ("TMPV2", "TRADE_SELL",  "CD trading, sell side (KRW bn)", "매도"),
    ("TMPV3", "TRADE_BUY",   "CD trading, buy side (KRW bn)", "매수"),
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
    # Exclude the current day in live mode: freeSIS accrues intraday and the
    # insert-only loader would lock that partial value permanently. Yesterday's
    # finalized figure is ingested today; today's is ingested tomorrow.
    until_dt = datetime.date.fromisoformat(until) if until else (
        today - datetime.timedelta(days=1))
    if since_dt < _HISTORY_START:
        since_dt = _HISTORY_START
    now = datetime.datetime.now(UTC)

    session = make_session()
    print(f"  Fetching CD거래현황 ({_SERVICE}) {since_dt}..{until_dt} ...",
          end=" ", flush=True)
    rows = fetch_freesis_rows(session, _SERVICE, {
        "tmpV40": "100000000", "tmpV41": "1", "tmpV1": "D",
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
        raw_date = r.get("TMPV1")  # "YYYY-MM-DD"
        try:
            obs_date = datetime.date.fromisoformat(str(raw_date))
        except (TypeError, ValueError):
            continue
        if obs_date < since_dt or obs_date > until_dt:
            continue
        for col, suffix, _display, _kor in _CUTS:
            observations.append(ObservationRow(
                imdr_code=f"KOFIA.CD.{suffix}.KR",
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
        topic="cd_trading",
        fetch_fn=run_fetch,
        description=__doc__.splitlines()[0] if __doc__ else "",
        country_code="KR",
    )


if __name__ == "__main__":
    import sys
    sys.exit(main())
