"""ASX RBA Rate Tracker — 30-day interbank cash-rate futures implied curve.

Source (plain HTTPS GET, no auth, no Imperva challenge from rvsg-fs01 —
verified 2026-06-14). Despite the ``.csv`` extension both endpoints are JSON:

  https://www.asx.com.au/content/dam/asx/data/yield_curve.csv
    {"Crnt_Stlmnt_Dt": "2026-06-11", "RBA_Trgt_Cash_Rate": 4.35,
     "months": [{"Expiry_Month": "Jun-26", "Implied_Yield": 4.35}, ...]}   (~18 months)

  https://www.asx.com.au/content/dam/asx/data/market_exp.csv
    {"Ftre_Cash_Rate": 4.1, "Ftre_Cash_Rate_Change": -0.25,
     "days": [{"Stlmnt_Dt": "2026-06-11", "Prob_No_Change": 100, "Prob_Change": 0}, ...]}
                                                                       (~15 trading days)

Why this exists: the RBA discontinued the F1 OIS series (FIRMMOIS1D/3D/6D)
at 2022-12-01 — those columns are now ``NA`` in F1 while cash-rate + BBSW
keep updating. The 30-day interbank cash-rate futures implied curve IS the
market rate-expectations path and supersedes the dead OIS series.

Derived indicators (obs_date = settlement date):
  ASX.CASHRATE.IMPLIED_1M.AU    implied avg cash rate ~1 month ahead   (pct)
  ASX.CASHRATE.IMPLIED_3M.AU                           ~3 months ahead
  ASX.CASHRATE.IMPLIED_6M.AU                           ~6 months ahead
  ASX.CASHRATE.IMPLIED_12M.AU                          ~12 months ahead
  ASX.RATETRACKER.PROB_CHANGE_NEXT_MEETING.AU   P(move at next RBA meeting), %
                                                (backfills ~15 trading days/pull)

The implied rate at horizon N is linearly interpolated off the monthly
curve (each ``Expiry_Month`` anchored to its 15th), where the futures
implied yield for a month is the market's expected average overnight cash
rate during that month.
"""
from __future__ import annotations

import datetime as dt
import json

import httpx

from imdr.domains.econ.schema import IndicatorRow, ObservationRow

_BASE = "https://www.asx.com.au/content/dam/asx/data"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36"
    ),
    "Referer": (
        "https://www.asx.com.au/markets/trade-our-derivatives-market/"
        "futures-market/rba-rate-tracker"
    ),
}

# Fixed horizons (months ahead) interpolated off the monthly curve.
HORIZONS: tuple[int, ...] = (1, 3, 6, 12)

VENDOR_NAME = "ASX"


def _get_json(name: str, *, client: httpx.Client | None = None) -> dict:
    owns = client is None
    client = client or httpx.Client(timeout=30, follow_redirects=True)
    try:
        r = client.get(f"{_BASE}/{name}", headers=_HEADERS)
        r.raise_for_status()
        return json.loads(r.text)
    finally:
        if owns:
            client.close()


def _expiry_anchor(expiry_month: str) -> dt.date:
    """``Jun-26`` -> 2026-06-15 (month midpoint anchor for interpolation)."""
    d = dt.datetime.strptime(expiry_month, "%b-%y")
    return dt.date(d.year, d.month, 15)


def _add_months(d: dt.date, n: int) -> dt.date:
    m = d.month - 1 + n
    return dt.date(d.year + m // 12, m % 12 + 1, min(d.day, 28))


def _interp(curve: list[tuple[dt.date, float]], target: dt.date) -> float | None:
    """Linear interpolation of implied yield at ``target`` across the ordered
    (anchor_date, yield) curve. Returns None if ``target`` is beyond the
    published horizon (we do not extrapolate)."""
    if not curve:
        return None
    if target <= curve[0][0]:
        return curve[0][1]
    if target >= curve[-1][0]:
        return None
    for (d0, y0), (d1, y1) in zip(curve, curve[1:]):
        if d0 <= target <= d1:
            span = (d1 - d0).days or 1
            frac = (target - d0).days / span
            return round(y0 + (y1 - y0) * frac, 4)
    return None


def parse_yield_curve(payload: dict) -> tuple[dt.date, list[tuple[dt.date, float]]]:
    """Return (settlement_date, [(anchor_date, implied_yield), ...] ordered)."""
    if "Crnt_Stlmnt_Dt" not in payload or "months" not in payload:
        raise ValueError(
            "ASX yield_curve payload missing 'Crnt_Stlmnt_Dt'/'months' "
            f"keys; got {sorted(payload)!r}"
        )
    settle = dt.date.fromisoformat(payload["Crnt_Stlmnt_Dt"])
    curve = sorted(
        (_expiry_anchor(m["Expiry_Month"]), float(m["Implied_Yield"]))
        for m in payload["months"]
    )
    if not curve:
        raise ValueError("ASX yield_curve payload has an empty 'months' array")
    return settle, curve


def build_rows(
    *, client: httpx.Client | None = None
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    """Fetch + parse the ASX rate tracker; build (indicators, observations)."""
    yc = _get_json("yield_curve.csv", client=client)
    me = _get_json("market_exp.csv", client=client)

    settle, curve = parse_yield_curve(yc)
    now = dt.datetime.now(dt.timezone.utc)

    indicators: list[IndicatorRow] = []
    observations: list[ObservationRow] = []

    # --- Derived fixed-horizon implied cash rate (the OIS replacement) ---
    for n in HORIZONS:
        code = f"ASX.CASHRATE.IMPLIED_{n}M.AU"
        indicators.append(IndicatorRow(
            imdr_code=code,
            vendor_name=VENDOR_NAME,
            source_code=f"asx_trt_yield_curve:{n}M",
            display_name=(
                f"ASX 30-day interbank cash-rate futures — implied cash rate "
                f"~{n} month{'s' if n > 1 else ''} ahead (market path, %)"
            ),
            unit="pct",
            frequency="DAILY",
            country_iso="AU",
            category="rates",
        ))
        val = _interp(curve, _add_months(settle, n))
        if val is not None:
            observations.append(ObservationRow(
                imdr_code=code, obs_date=settle, vintage=0,
                release_date=now, value=val, ingested_at=now,
            ))

    # --- Next-meeting probability of a change (backfills ~15 trading days) ---
    if "days" not in me:
        raise ValueError(
            f"ASX market_exp payload missing 'days' key; got {sorted(me)!r}"
        )
    pc_code = "ASX.RATETRACKER.PROB_CHANGE_NEXT_MEETING.AU"
    scenario = (
        f"P(move to {me.get('Ftre_Cash_Rate')}% / "
        f"{me.get('Ftre_Cash_Rate_Change'):+}pp) at next RBA meeting, %"
    )
    indicators.append(IndicatorRow(
        imdr_code=pc_code,
        vendor_name=VENDOR_NAME,
        source_code="asx_trt_market_exp:prob_change",
        display_name=f"ASX RBA Rate Tracker — {scenario}",
        unit="pct",
        frequency="DAILY",
        country_iso="AU",
        category="rates",
    ))
    for day in me["days"]:
        observations.append(ObservationRow(
            imdr_code=pc_code,
            obs_date=dt.date.fromisoformat(day["Stlmnt_Dt"]),
            vintage=0, release_date=now,
            value=float(day["Prob_Change"]), ingested_at=now,
        ))

    return indicators, observations
