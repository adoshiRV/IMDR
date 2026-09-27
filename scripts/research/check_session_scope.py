"""Session-scope checker for Spider daily editions.

WHY THIS EXISTS
---------------
`rates.fact_observation` stamps each curve at whatever time the feed last snapped
it, and those times differ by up to twelve hours across markets. Grouping by
``CAST(ts AS date)`` therefore does NOT give you a common session: on 25 Aug 2026
the INR curve was last marked at 11:10 UTC while USD was marked at 23:00 UTC.

An edition that attributes a same-calendar-day move in an Asian curve to a US
release published at 14:00 UTC is making a sequencing error — the Asian mark
predates the data. That happened on the 26 Aug 2026 edition (India's -7.2bp, the
largest move in the universe, was credited to US consumer confidence it could not
have seen) and this script exists so it is caught mechanically instead.

WHAT IT DOES
------------
For a pair of dates, prints each curve's last-mark time on both days and flags:

  * ``EVENT?``   -- whether the later mark postdates a given event time, so the
                   curve could actually have traded it;
  * ``MISMATCH`` -- whether the two days' marks are taken at materially different
                   times, which breaks the day-over-day comparison itself.

Exit code is 0 always: this is an advisory check whose output the author must
read, not a gate. The failure mode it guards against is a *narrative* error, and
no script can decide whether the prose attributes a move correctly.

USAGE
-----
    python scripts/research/check_session_scope.py --prev 2026-08-24 --curr 2026-08-25
    python scripts/research/check_session_scope.py --prev 2026-08-24 --curr 2026-08-25 --event 14:00

``--event`` is the UTC time of the release you are about to attribute moves to
(US 08:30 ET = 12:30 UTC, 10:00 ET = 14:00 UTC). Defaults to 14:00.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO / "src") not in sys.path:
    sys.path.insert(0, str(REPO / "src"))

# The primary curve per market, matching what the daily reports.
CURVES = {
    "USD": "SOFR", "EUR": "ESTR", "GBP": "SONIA", "JPY": "TONAR", "CAD": "CORRA",
    "AUD": "AONIA", "NZD": "NZIONA", "KRW": "CD", "SGD": "SORA", "THB": "THOR",
    "INR": "MIBOR", "CNY": "REPO_7D", "TWD": "TAIBOR", "HKD": "HIBOR",
    "MYR": "KLIBOR", "PHP": "PHIREF", "IDR": "JIBOR",
}

# Marks more than this far apart across the two days make the DoD non-comparable.
MISMATCH_TOLERANCE_MIN = 90


def _minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")[:2]
    return int(h) * 60 + int(m)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--prev", required=True, help="prior session date, YYYY-MM-DD")
    ap.add_argument("--curr", required=True, help="reported session date, YYYY-MM-DD")
    ap.add_argument("--event", default="14:00",
                    help="UTC time of the release being attributed (default 14:00)")
    ap.add_argument("--tenor", default="10Y")
    args = ap.parse_args(argv)

    import pandas as pd
    from imdr.config import Settings
    from imdr.connectors.mssql import MSSQLConnector

    eng = MSSQLConnector(Settings()).read_engine
    pairs = " OR ".join(f"(c.ccy='{k}' AND c.curve='{v}')" for k, v in CURVES.items())
    df = pd.read_sql(f"""
        SELECT c.ccy, CAST(o.ts AS date) d, o.ts, o.value
        FROM rates.fact_observation o
        JOIN rates.dim_curve c ON c.id = o.curve_id
        WHERE ({pairs}) AND o.quote = 'par' AND o.tenor = '{args.tenor}'
          AND CAST(o.ts AS date) IN ('{args.prev}', '{args.curr}')
    """, eng)

    if df.empty:
        print(f"NO DATA for {args.tenor} on {args.prev}/{args.curr}")
        return 0

    last = df.sort_values("ts").groupby(["ccy", "d"]).tail(1)
    ts = last.pivot(index="ccy", columns="d", values="ts")
    val = last.pivot(index="ccy", columns="d", values="value")
    cols = sorted(ts.columns)

    ev = _minutes(args.event)
    rows = []
    for ccy in ts.index:
        t_prev = str(ts.loc[ccy, cols[0]])[11:16] if len(cols) > 1 and pd.notna(ts.loc[ccy, cols[0]]) else "--:--"
        t_curr = str(ts.loc[ccy, cols[-1]])[11:16] if pd.notna(ts.loc[ccy, cols[-1]]) else "--:--"
        if len(cols) > 1 and pd.notna(val.loc[ccy, cols[0]]) and pd.notna(val.loc[ccy, cols[-1]]):
            bp = round((val.loc[ccy, cols[-1]] - val.loc[ccy, cols[0]]) * 100, 1)
        else:
            bp = None
        sees = "--"
        if t_curr != "--:--":
            sees = "YES" if _minutes(t_curr) >= ev else "no"
        mism = ""
        if t_prev != "--:--" and t_curr != "--:--":
            if abs(_minutes(t_curr) - _minutes(t_prev)) > MISMATCH_TOLERANCE_MIN:
                mism = "MISMATCH"
        rows.append((ccy, t_prev, t_curr, bp, sees, mism))

    rows.sort(key=lambda r: (r[4] != "YES", r[3] if r[3] is not None else 0))

    print(f"SESSION SCOPE  {args.tenor}  {args.prev} -> {args.curr}   event = {args.event} UTC")
    print("=" * 76)
    print(f"{'ccy':<5}{'mark(prev)':>12}{'mark(curr)':>12}{'bp':>8}{'sees event':>13}  flag")
    print("-" * 76)
    for ccy, tp, tc, bp, sees, mism in rows:
        bps = f"{bp:+.1f}" if bp is not None else "  n/a"
        print(f"{ccy:<5}{tp:>12}{tc:>12}{bps:>8}{sees:>13}  {mism}")
    print("-" * 76)

    yes = [r[0] for r in rows if r[4] == "YES"]
    no = [r[0] for r in rows if r[4] == "no"]
    mismatched = [r[0] for r in rows if r[5]]
    missing = [r[0] for r in rows if r[3] is None]

    print(f"CAN have traded the {args.event} event : {', '.join(yes) if yes else 'none'}")
    print(f"CANNOT (marked earlier)              : {', '.join(no) if no else 'none'}")
    if mismatched:
        print(f"!! MARK-TIME MISMATCH across days     : {', '.join(mismatched)}"
              f"  (DoD not comparable for these)")
    if missing:
        print(f"!! NO PAIRED MARK                     : {', '.join(missing)}")
    print()
    print("Do not attribute a move in the CANNOT list to that release. Check the "
          "edition's prose against this table before locking.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
