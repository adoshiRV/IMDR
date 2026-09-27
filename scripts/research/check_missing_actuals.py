"""Missing-actuals check for Spider digests (daily + weekly).

Answers one question mechanically, so no edition has to spot it by eye: **for
every calendar release that carried a forecast, did the actual ever land — and
if one lane missed it, did the other lane cover?**

This exists because of two real gaps found by hand on 09 Sep 2026, a day apart
in kind:

  * **Taiwan August CPI.** Released 08 Sep. Both lanes held the scheduled row
    with a number expected — BQL ``CPI YoY`` survey 2.35, TE ``inflation rate
    yoy`` forecast 2.6% — and **neither ever received an actual**. 24h+ later
    the release was still blank in IMDR, and Taiwan has no third source: its
    16 ``econ.dim_indicator`` series stop at 2026-07-31. A genuine hole.
  * **Philippine unemployment.** Released 08 Sep, printed 6.0% against a 5.0%
    TE forecast — a 100bp miss. The TE row never got its actual; the BQL row
    did. So the number *was* in IMDR the whole time, on one lane only.

Those two look identical in any per-row query — "actual IS NULL" — but they
are not the same problem. One is a data gap; the other is normal vendor
asymmetry that a cross-lane read resolves. Conflating them either hides real
holes or floods the operator with false ones, so this check separates them:

  * **UNCOVERED** — no lane has the actual. The genuine gap. Exit code 1.
  * **ONE-LANE**  — this lane is blank but another lane has the number.
    Advisory only, exit 0: TE and BQL have permanently different coverage, and
    gating on that difference would leave this check red forever, which is how
    a gate stops being read (the same reasoning as ``check_event_dates.py``).

Scope — what counts as "an actual was expected":

  * ``event_datetime`` must be present. Rows without one are the seeded soft
    placeholders described in ``docs/admin/calendar/cb_events_refresh.md``;
    they carry a guessed date and were never feed-backed, so a blank actual
    says nothing.
  * a ``survey`` or ``forecast`` must be present. That is what makes a row a
    forecastable data release rather than a speech, an auction announcement or
    a bill-issuance notice — none of which ever get an actual.
  * ``actual`` AND ``revised`` must both be blank.
  * the release instant must be at least ``--grace-hours`` in the past
    (default 24), so a release that simply has not happened yet is never
    flagged.

Cross-lane pairing is by ``(country, event_datetime)``, NOT by event name:
the lanes name the same release differently — Taiwan's is ``CPI YoY`` on BQL
and ``inflation rate yoy`` on TE — so a name join would miss the pairing
entirely and report a covered release as uncovered.

Usage::

    python scripts/research/check_missing_actuals.py
    python scripts/research/check_missing_actuals.py --as-of 2026-09-09
    python scripts/research/check_missing_actuals.py --lookback-days 14
    python scripts/research/check_missing_actuals.py --country TW --country PH
    python scripts/research/check_missing_actuals.py --all   # show ONE-LANE too
    python scripts/research/check_missing_actuals.py --all-countries  # off-roster too

Scans Spider's 17-market roster by default; ``cb_events`` carries ~50 countries
and the rest are markets no edition quotes (see ``SPIDER_UNIVERSE``).

Exit code 0 = every stale release is covered by at least one lane; 1 = at
least one release has no actual on any lane (or a bad argument).

Run it before locking a digest MD and quote its output rather than a
remembered number — see spider.md.
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import sys

from sqlalchemy import bindparam, text

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


# ---------------------------------------------------------------------------
# Lanes
# ---------------------------------------------------------------------------

TE = "TE"
BQL = "BQL"

# Spider's standing roster (daily + weekly). ``cb_events`` carries ~50
# countries, so an unscoped run buries the markets the digest actually quotes:
# on 2026-09-09 it reported 66 uncovered releases, of which all but a handful
# were KZ/RO/HU/CZ/DK/CL/CO rows no edition will ever print. A check whose
# output has to be skimmed for relevance stops being run, so the roster is the
# default and ``--all-countries`` opts out of it.
SPIDER_UNIVERSE: tuple[str, ...] = (
    "CN", "JP", "KR", "IN", "TW", "HK", "SG", "TH", "ID", "MY", "PH",
    "AU", "NZ", "US", "EU", "UK", "CA",
)


def lane_of(source: str | None) -> str:
    """Collapse a ``cb_events.source`` string to its feed lane."""
    if not source:
        return "(none)"
    if source.startswith("tradingeconomics"):
        return TE
    if source == "bloomberg_bql":
        return BQL
    return source


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------

_SQL = """
SELECT e.event_date,
       e.event_datetime,
       e.event_name,
       e.source,
       e.survey,
       e.forecast,
       e.actual,
       e.revised,
       e.prior_value,
       c.country_code
  FROM calendar.cb_events e
  JOIN dbo.dim_country c ON c.id = e.country_id
 WHERE e.event_datetime IS NOT NULL
   AND e.event_datetime >= :start
   AND e.event_datetime <  :end
   AND e.is_estimated = 0
"""

_COUNTRY_CLAUSE = "   AND c.country_code IN :countries\n"

# The pinned ``SQL Server`` ODBC driver hands DATETIMEOFFSET back as a string
# with SQL Server's 7 fractional digits and a space before the offset --
# "2026-09-08 08:00:00.0000000 +00:00" -- which datetime.fromisoformat rejects
# (it takes at most 6). String input is therefore the normal path here, not an
# edge case, exactly as ``check_feed_freshness._as_date`` documents for DATE.
_DT_RE = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2}):(\d{2})"
    r"(?:\.(\d+))?\s*(Z|[+-]\d{2}:?\d{2})?$"
)


def _as_datetime(value) -> dt.datetime:
    """Narrow a driver value to a timezone-aware UTC-comparable datetime.

    A naive value is treated as UTC: every ``cb_events.event_datetime`` is
    stored as an offset-bearing instant, so naive here means the driver
    dropped the offset, not that the instant is local.
    """
    if isinstance(value, dt.datetime):
        return (value if value.tzinfo
                else value.replace(tzinfo=dt.timezone.utc))
    m = _DT_RE.match(str(value).strip())
    if not m:
        raise ValueError(f"unparseable event_datetime: {value!r}")
    y, mo, d, hh, mm, ss, frac, off = m.groups()
    micro = int((frac or "0").ljust(6, "0")[:6])
    if off in (None, "Z"):
        tz = dt.timezone.utc
    else:
        sign = 1 if off[0] == "+" else -1
        body = off[1:].replace(":", "")
        tz = dt.timezone(sign * dt.timedelta(hours=int(body[:2]),
                                             minutes=int(body[2:4])))
    return dt.datetime(int(y), int(mo), int(d), int(hh), int(mm), int(ss),
                       micro, tzinfo=tz)


def fetch_rows(conn, start: dt.datetime, end: dt.datetime,
               countries: list[str] | None) -> list[dict]:
    """Return candidate cb_events rows in the window as plain dicts."""
    sql = _SQL
    params: dict = {"start": start, "end": end}
    if countries:
        sql += _COUNTRY_CLAUSE
        params["countries"] = countries
    stmt = text(sql)
    if countries:
        stmt = stmt.bindparams(bindparam("countries", expanding=True))
    out: list[dict] = []
    for r in conn.execute(stmt, params):
        m = r._mapping
        out.append({
            "event_date": m["event_date"],
            "event_datetime": _as_datetime(m["event_datetime"]),
            "event_name": m["event_name"],
            "source": m["source"],
            "lane": lane_of(m["source"]),
            "survey": m["survey"],
            "forecast": m["forecast"],
            "actual": m["actual"],
            "revised": m["revised"],
            "prior_value": m["prior_value"],
            "country_code": m["country_code"],
        })
    return out


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

def _blank(v) -> bool:
    """True when a cb_events value column carries no number."""
    return v is None or str(v).strip() in ("", "-", "—")


def expected_an_actual(row: dict) -> bool:
    """True when this row is a forecastable release still missing its print."""
    if not (not _blank(row["survey"]) or not _blank(row["forecast"])):
        return False
    return _blank(row["actual"]) and _blank(row["revised"])


def coverage_index(rows: list[dict]) -> dict[tuple, set[str]]:
    """Map ``(country, instant)`` -> set of lanes that DO have an actual."""
    idx: dict[tuple, set[str]] = {}
    for r in rows:
        if _blank(r["actual"]) and _blank(r["revised"]):
            continue
        idx.setdefault((r["country_code"], r["event_datetime"]),
                       set()).add(r["lane"])
    return idx


def classify(rows: list[dict], as_of: dt.datetime, grace_hours: int) -> list[dict]:
    """Return findings, each tagged UNCOVERED or ONE-LANE, newest release last."""
    cov = coverage_index(rows)
    findings: list[dict] = []
    for r in rows:
        if not expected_an_actual(r):
            continue
        inst = r["event_datetime"]
        age_h = (as_of - inst).total_seconds() / 3600.0
        if age_h < grace_hours:
            continue  # not late yet -- never flag a release that just happened
        others = cov.get((r["country_code"], inst), set()) - {r["lane"]}
        findings.append({
            **r,
            "age_hours": age_h,
            "covered_by": sorted(others),
            "status": "ONE-LANE" if others else "UNCOVERED",
        })
    findings.sort(key=lambda f: (f["event_datetime"], f["country_code"],
                                 f["event_name"]))
    return findings


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _fmt(v) -> str:
    return "—" if _blank(v) else str(v)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--as-of", default=None,
                    help="Edition cut date, YYYY-MM-DD (default: today).")
    ap.add_argument("--lookback-days", type=int, default=7,
                    help="How far back to look for stale releases (default 7).")
    ap.add_argument("--grace-hours", type=int, default=24,
                    help="Hours after the release instant before a blank "
                         "actual counts as missing (default 24).")
    ap.add_argument("--country", action="append", default=None,
                    help="Restrict to a country_code; repeatable. Overrides "
                         "the default Spider roster.")
    ap.add_argument("--all-countries", action="store_true",
                    help="Scan every country in cb_events, not just the "
                         "Spider roster. Noisy — most rows are markets no "
                         "edition quotes.")
    ap.add_argument("--all", action="store_true",
                    help="Also list ONE-LANE findings (covered elsewhere).")
    args = ap.parse_args(argv)

    if args.country:
        countries = args.country
        scope = "countries " + ",".join(sorted(args.country))
    elif args.all_countries:
        countries = None
        scope = "all countries"
    else:
        countries = list(SPIDER_UNIVERSE)
        scope = f"Spider roster ({len(SPIDER_UNIVERSE)} markets)"

    if args.as_of:
        try:
            as_of_date = dt.date.fromisoformat(args.as_of)
        except ValueError:
            print(f"!! --as-of must be YYYY-MM-DD, got {args.as_of!r}",
                  file=sys.stderr)
            return 1
    else:
        as_of_date = dt.date.today()

    if args.lookback_days < 1:
        print("!! --lookback-days must be >= 1", file=sys.stderr)
        return 1

    as_of = dt.datetime.combine(as_of_date, dt.time(23, 59),
                                tzinfo=dt.timezone.utc)
    start = dt.datetime.combine(as_of_date - dt.timedelta(days=args.lookback_days),
                                dt.time(0, 0), tzinfo=dt.timezone.utc)

    # Imported here so --help works without DB settings present.
    from imdr.config.settings import get_settings
    from imdr.connectors.mssql import MSSQLConnector

    connector = MSSQLConnector(get_settings())
    try:
        with connector.read_engine.connect() as conn:
            rows = fetch_rows(conn, start, as_of, countries)
    finally:
        connector.dispose()

    findings = classify(rows, as_of, args.grace_hours)
    uncovered = [f for f in findings if f["status"] == "UNCOVERED"]
    one_lane = [f for f in findings if f["status"] == "ONE-LANE"]

    print(f"Missing actuals as of {as_of_date.isoformat()} "
          f"({as_of_date.strftime('%a')}) — releases {start.date()}..{as_of_date} "
          f"with a forecast but no print after {args.grace_hours}h")
    print(f"scope: {scope}\n")
    print(f"  rows scanned        : {len(rows)}")
    print(f"  UNCOVERED (no lane) : {len(uncovered)}")
    print(f"  ONE-LANE (covered)  : {len(one_lane)}")

    def _dump(items: list[dict], title: str) -> None:
        if not items:
            return
        print(f"\n{title}")
        header = (f"{'release (UTC)':<17} {'cc':>3} {'lane':>5} "
                  f"{'event':<34} {'fcst':>9} {'prior':>9} {'age':>6}")
        print(header)
        print("-" * len(header))
        for f in items:
            fcst = f["forecast"] if not _blank(f["forecast"]) else f["survey"]
            name = f["event_name"]
            if len(name) > 34:
                name = name[:31] + "..."
            print(f"{f['event_datetime'].strftime('%Y-%m-%d %H:%M'):<17} "
                  f"{f['country_code']:>3} {f['lane']:>5} {name:<34} "
                  f"{_fmt(fcst):>9} {_fmt(f['prior_value']):>9} "
                  f"{f['age_hours']:>5.0f}h")

    _dump(uncovered, "UNCOVERED — no lane carries the actual:")
    if args.all:
        _dump(one_lane, "ONE-LANE — blank here, but another lane has it:")
    elif one_lane:
        lanes = sorted({c for f in one_lane for c in f["covered_by"]})
        print(f"\n{len(one_lane)} ONE-LANE finding(s) suppressed "
              f"(covered by {', '.join(lanes)}). Pass --all to list them.")

    if uncovered:
        print("\n!! These releases have a forecast on the calendar and no "
              "actual on ANY lane. Do NOT score a surprise against them, and "
              "do not print the forecast as though it were the outcome.")
        return 1

    print("\nEvery stale release is covered on at least one lane — read the "
          "actual across lanes, not from a single feed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
