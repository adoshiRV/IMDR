"""KOFIA freeSIS — fund industry AUM by asset class (설정원본, daily).

Source: Korea Financial Investment Association freeSIS, 펀드 > 설정원본 시계열
(service STATFND0100100130). Daily fund principal (설정원본) split by fund type,
back to 2004-01-02. This is the canonical "asset-management fund AUM by type"
table — Equity / Bond / MMF / hybrids / real-estate / etc. summing to the
industry total. Values published in 억원 (100 mn KRW); stored as krw_bn.

Note: the freeSIS period dropdown shows only 월간/년간, but the backend accepts
a daily code (tmpV35=0) — so this is DAILY, not monthly.

The 13 types sum (within rounding) to 합계/TOTAL — a built-in identity check.
MMF principal here (KOFIA.FUND_AUM.MMF.KR) supersedes the month-end
KOFIA.MMF.SETUP_PRINCIPAL.KR (deactivated, migration 116); MMF *net assets* +
retail/institutional split stay in kofia_mmf_level.py, MMF flows in
kofia_mmf_flows.py.

Cell mapping: 4.2 Balance Sheets (asset-management sector composition).

Usage:
    python -m scripts.econ.kr.kofia.kofia_fund_aum                    # live (90d)
    python -m scripts.econ.kr.kofia.kofia_fund_aum --since 2004-01-01  # backfill
"""

from __future__ import annotations

import datetime

from imdr.domains.econ.kofia_http import EOK_TO_KRW_BN, fetch_freesis_rows, make_session
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc
_SERVICE = "STATFND0100100130"
_HISTORY_START = datetime.date(2004, 1, 1)
_LIVE_LOOKBACK_DAYS = 90

# TMPV column -> (imdr suffix, English display, Korean type)
_TYPES: list[tuple[str, str, str, str]] = [
    ("TMPV2",  "EQUITY",        "Equity funds",              "주식형"),
    ("TMPV3",  "HYBRID_EQUITY", "Hybrid-equity funds",       "혼합주식형"),
    ("TMPV4",  "HYBRID_BOND",   "Hybrid-bond funds",         "혼합채권형"),
    ("TMPV5",  "BOND",          "Bond funds",                "채권형"),
    ("TMPV6",  "MMF",           "Money-market funds",        "단기금융"),
    ("TMPV7",  "DERIVATIVES",   "Derivative funds",          "파생형"),
    ("TMPV8",  "REAL_ESTATE",   "Real-estate funds",         "부동산"),
    ("TMPV9",  "COMMODITY",     "Commodity / physical funds","실물"),
    ("TMPV10", "FOF",           "Fund-of-funds",             "재간접"),
    ("TMPV11", "SPECIAL_ASSET", "Special-asset funds",       "특별자산"),
    ("TMPV13", "CONTRACT",      "Investment-contract funds", "투자계약"),
    ("TMPV14", "MIXED_ASSET",   "Mixed-asset funds",         "혼합자산"),
    ("TMPV15", "GROWTH",        "Business-development funds","기업성장"),
    ("TMPV12", "TOTAL",         "Total fund AUM",            "합계"),
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
    print(f"  Fetching 설정원본 시계열 ({_SERVICE}, daily) {since_dt}..{until_dt} ...",
          end=" ", flush=True)
    rows = fetch_freesis_rows(session, _SERVICE, {
        "tmpV40": "100000000", "tmpV41": "1",
        "tmpV32": since_dt.strftime("%Y%m%d"),
        "tmpV33": until_dt.strftime("%Y%m%d"),
        "tmpV35": "0",  # 0 = daily (8 = monthly)
    })
    print(f"{len(rows)} rows")

    indicators: list[IndicatorRow] = []
    for col, suffix, display, kor in _TYPES:
        indicators.append(IndicatorRow(
            imdr_code=f"KOFIA.FUND_AUM.{suffix}.KR",
            vendor_name="KOFIA",
            source_code=f"freesis/{_SERVICE}/{col}",
            display_name=f"Korea {display} AUM (KRW bn) [{kor}] (KOFIA freeSIS)",
            unit="krw_bn",
            frequency="DAILY",
            country_iso="KR",
            category="balance_sheet",
            is_seasonally_adjusted=False,
            bbg_ticker=None,
        ))

    observations: list[ObservationRow] = []
    for r in rows:
        s = str(r.get("TMPV1"))  # "YYYYMMDD"
        try:
            obs_date = datetime.date(int(s[:4]), int(s[4:6]), int(s[6:8]))
        except (TypeError, ValueError, IndexError):
            continue
        if obs_date < since_dt or obs_date > until_dt:
            continue
        for col, suffix, _display, _kor in _TYPES:
            val = _to_krw_bn(r.get(col))
            if val is None:  # empty types (e.g. 실물/COMMODITY) — don't store NULLs
                continue
            observations.append(ObservationRow(
                imdr_code=f"KOFIA.FUND_AUM.{suffix}.KR",
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
        topic="fund_aum",
        fetch_fn=run_fetch,
        description=__doc__.splitlines()[0] if __doc__ else "",
        country_code="KR",
    )


if __name__ == "__main__":
    import sys
    sys.exit(main())
