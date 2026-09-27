"""Arrival-pass drift check for rates curves.

Answers one question mechanically, so no ops note has to hand-read load
stamps to get it right: **which scheduled loader pass actually built each
curve's row, and has that drifted later than it used to be?**

This exists because of a real failure. A 2026-09-17 note reported that
Citi's EUR basis curves had, "for the third day running", arrived entirely
on the 14:00 SGT pass "with nothing in the 08:00 batch". The 14:00 arrival
was true for one value date only. Read off ``created_at`` the three days
were:

    value date 2026-09-14   19 of 20 tenors at 08:21,  1 at 14:22
    value date 2026-09-15    5 of 20 tenors at 08:03, 15 at 14:23
    value date 2026-09-16    0            at 08:0x,   20 at 14:03

— a three-day *deterioration* (95% -> 25% -> 0% of the grid delivered by the
morning pass), not three days of total absence. The same note also put USD
``SOFR_FEDFUND_BASIS`` (curve 66) in the "EUR basis family" and asserted that
"nothing runs after 09:15", when ``IMDR_daily`` repeats every 6 hours from
08:01 and it was that task's 14:01 firing that wrote the rows being
complained about. Three wrong claims in one note, all of them checkable.

So this script measures arrival, not freshness. The existing staleness
monitor asks *"is the latest observation old?"*; on 2026-09-16 the answer was
no — the row was there, complete, same day. What had changed was *when in the
day* it landed, and that is invisible to a staleness check.

Two design points worth knowing before you read the output:

1. **Passes are labelled relative to the value date, in business days.**
   A Friday row loaded on Monday at 02:27 and a Monday row loaded on Tuesday
   at 08:21 are both ``B+1`` arrivals; a plain calendar offset would call the
   first one three days late every weekend and drown the signal. So a pass is
   ``B+<business days after value date> <scheduled SGT hour>``.

2. **The baseline is learned, not declared, and keyed on completion.** A
   series' expected pass is the modal pass at which it reaches
   ``--min-on-time``% of the day's rows, over the window *excluding the newest
   value date* — so a run of bad days cannot quietly redefine "normal" as
   itself. Completion rather than first arrival, because Citi's par and forward
   curves build a value date across every pass by design and would otherwise
   read as permanently late. Override with ``--expect-pass``.

``created_at`` is the first-arrival stamp: the loader upserts, so a re-run
that only rewrites a value leaves it alone (``updated_at`` moves instead).
That is exactly the semantics this check wants — when did this tenor first
land — but it does mean a delete-and-reload would reset the history.

Usage::

    python scripts/rates/health/check_curve_arrival.py
    python scripts/rates/health/check_curve_arrival.py --curve EUR.3S6S_BASIS --detail
    python scripts/rates/health/check_curve_arrival.py --instrument swap_libor --quote par
    python scripts/rates/health/check_curve_arrival.py --days 20 --tenors

Exit code 0 = every series completed on its baseline pass; 1 = at least one
is LATE, INTERMITTENT, or BEHIND the cohort's newest value date (or a bad
argument / empty cohort).

Scope guard: the default cohort is the active ``basis_swaps`` curves and the
default window is 10 days, because this reads a 23M-row table on the
production server. Widen deliberately — ``--all`` over a long ``--days`` is
not a cheap query.
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import NamedTuple

from sqlalchemy import bindparam, text

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


# ---------------------------------------------------------------------------
# Scheduled passes
#
# Taken from the Windows tasks that actually write this table:
#   IMDR_daily          repeats PT6H from 08:01 SGT -> 08, 14, 20, 02
#   IMDR_snapshots_citi repeats PT3H from 23:00 SGT -> 23, 02, 05, 08, 11,
#                                                      14, 17, 20
# The 3-hourly set is a superset of the 6-hourly one, so bucketing to the
# latest scheduled hour at or before the load stamp assigns every write to the
# pass that produced it. A retry or a manual refresh lands in the bucket of
# the pass it belongs to (a 16:21 write rolls into the 14:00 pass), which is
# the reading an operator wants: "the afternoon pass got it, eventually".
# ---------------------------------------------------------------------------

SCHEDULED_HOURS: tuple[int, ...] = (2, 5, 8, 11, 14, 17, 20, 23)

DEFAULT_DAYS = 10
MAX_DAYS = 90
DEFAULT_MIN_ON_TIME = 90.0
DEFAULT_MAX_LATE_DAYS = 2
DEFAULT_INSTRUMENT = "basis_swaps"

# A pass fires at :01 and the rows land a minute or two later, so a check run
# at 14:02 must not call a 14:00-baseline curve missing. Grace is generous
# because a slow Citi fetch inside the run is normal, not a fault.
DUE_GRACE_MINUTES = 30


class Pass(NamedTuple):
    """A scheduled loader pass, positioned relative to the value date.

    Ordered by the tuple itself, so ``B+1 08:00 < B+1 14:00 < B+2 02:00``
    falls out for free and "arrived no later than baseline" is just ``<=``.
    """

    offset: int  # business days after the value date
    hour: int  # scheduled pass hour, SGT

    @property
    def label(self) -> str:
        sign = "+" if self.offset >= 0 else "-"
        return f"B{sign}{abs(self.offset)} {self.hour:02d}:00"


# ---------------------------------------------------------------------------
# Time arithmetic
# ---------------------------------------------------------------------------


def business_days_between(start: dt.date, end: dt.date) -> int:
    """Count Mon-Fri days strictly after ``start``, up to and including ``end``.

    Negative when ``end`` precedes ``start``. Market holidays are deliberately
    *not* modelled: the loader tasks fire every day of the year regardless of
    whether any market is open, and this function measures loader latency, not
    trading time. Treating Christmas as a non-day would make a row that landed
    on its normal pass look early.
    """
    if end == start:
        return 0
    if end < start:
        return -business_days_between(end, start)
    n = 0
    cur = start
    while cur < end:
        cur += dt.timedelta(days=1)
        if cur.weekday() < 5:
            n += 1
    return n


def pass_slot(loaded: dt.datetime) -> tuple[dt.date, int]:
    """Map a load stamp to the (date, hour) of the pass that wrote it.

    A write before the first scheduled hour of the day belongs to the previous
    day's last pass — e.g. 01:40 is the tail of the 23:00 run, not a mystery
    fifth pass.
    """
    earlier = [h for h in SCHEDULED_HOURS if h <= loaded.hour]
    if earlier:
        return loaded.date(), earlier[-1]
    return loaded.date() - dt.timedelta(days=1), SCHEDULED_HOURS[-1]


def arrival_pass(value_date: dt.date, loaded: dt.datetime) -> Pass:
    """The pass that delivered a row, expressed relative to its value date."""
    slot_date, hour = pass_slot(loaded)
    return Pass(business_days_between(value_date, slot_date), hour)


def pass_due_at(value_date: dt.date, p: Pass) -> dt.datetime:
    """Wall-clock SGT time at which ``p`` fires for ``value_date``.

    Needed to tell "this curve is late" from "this curve isn't due yet". A
    curve whose baseline is the 14:00 pass has nothing wrong with it at 09:00;
    without this, every afternoon-arriving series would read as missing every
    single morning and the check would be noise by its second run.
    """
    day, remaining = value_date, p.offset
    while remaining > 0:
        day += dt.timedelta(days=1)
        if day.weekday() < 5:
            remaining -= 1
    return (dt.datetime.combine(day, dt.time(p.hour))
            + dt.timedelta(minutes=DUE_GRACE_MINUTES))


def parse_pass(spec: str) -> Pass:
    """Parse a ``--expect-pass`` string such as ``B+1 08:00`` or ``1@8``."""
    s = spec.strip().upper().replace("B", "")
    for sep in ("@", " "):
        if sep in s:
            off_s, hour_s = s.split(sep, 1)
            break
    else:
        raise ValueError(f"cannot parse pass {spec!r} — expected 'B+1 08:00'")
    hour = int(hour_s.strip().split(":")[0])
    if hour not in SCHEDULED_HOURS:
        raise ValueError(
            f"{hour:02d}:00 is not a scheduled pass; known: "
            + ", ".join(f"{h:02d}:00" for h in SCHEDULED_HOURS)
        )
    return Pass(int(off_s.strip().replace("+", "") or 0), hour)


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------


@dataclass
class Series:
    """Arrival history for one (curve, quote) pair over the window."""

    curve_id: int
    ccy: str
    curve: str
    quote: str
    # value date -> pass -> rows first written by that pass
    by_date: dict[dt.date, dict[Pass, int]]

    @property
    def key(self) -> str:
        return f"{self.ccy}.{self.curve}"

    @property
    def dates(self) -> list[dt.date]:
        return sorted(self.by_date)

    def passes(self) -> list[Pass]:
        seen: set[Pass] = set()
        for slots in self.by_date.values():
            seen.update(slots)
        return sorted(seen)

    def total(self, day: dt.date) -> int:
        return sum(self.by_date.get(day, {}).values())

    def first_pass(self, day: dt.date) -> Pass | None:
        slots = self.by_date.get(day)
        return min(slots) if slots else None

    def last_pass(self, day: dt.date) -> Pass | None:
        slots = self.by_date.get(day)
        return max(slots) if slots else None

    def cumulative(self, day: dt.date) -> list[tuple[Pass, int]]:
        """(pass, rows landed by the end of that pass) for one value date."""
        running = 0
        out: list[tuple[Pass, int]] = []
        for p, n in sorted(self.by_date.get(day, {}).items()):
            running += n
            out.append((p, running))
        return out

    def complete_pass(self, day: dt.date, threshold: float) -> Pass | None:
        """Earliest pass by which ``threshold``% of the day's rows had landed.

        This, and not the first pass to deliver anything, is what a drift
        check has to key on. Citi's par and forward curves build a value date
        *progressively* across every 3-hourly snapshot pass by design: EUR
        EURIBOR par lands ~8% of its 432 rows on the 14:00 pass and finishes
        at 02:00 the next morning, every single day. Keyed on the first pass
        those curves read 8% on-time forever and the check is pure noise;
        keyed on completion they hold a stable ``B+1 02:00`` baseline and move
        only when something is genuinely late. Single-build series like the
        basis swaps, where one pass delivers the whole grid, are the easy case
        either way.
        """
        total = self.total(day)
        if not total:
            return None
        want = total * threshold / 100.0
        for p, running in self.cumulative(day):
            if running >= want:
                return p
        return self.last_pass(day)

    def on_time_pct(self, day: dt.date, baseline: Pass) -> float | None:
        """Share of the day's rows delivered no later than ``baseline``."""
        total = self.total(day)
        if not total:
            return None
        on_time = sum(n for p, n in self.by_date[day].items() if p <= baseline)
        return 100.0 * on_time / total


# Ordered worst-first so a mixed report sorts usefully.
STATUS_RANK = {
    "BEHIND": 0,
    "LATE": 1,
    "INTERMITTENT": 2,
    "PENDING": 3,
    "SPARSE": 4,
    "OK": 5,
}

FLAGGED_STATUSES = frozenset({"BEHIND", "LATE", "INTERMITTENT"})


@dataclass
class Verdict:
    series: Series
    baseline: Pass | None
    status: str
    latest_date: dt.date | None
    latest_pct: float | None
    latest_complete: Pass | None
    trend: list[tuple[dt.date, float | None]]
    late_dates: list[dt.date]
    note: str = ""

    @property
    def flagged(self) -> bool:
        return self.status in FLAGGED_STATUSES


def evaluate(
    series: Series,
    cohort_latest: dt.date,
    now: dt.datetime,
    min_on_time: float = DEFAULT_MIN_ON_TIME,
    max_late_days: int = DEFAULT_MAX_LATE_DAYS,
    expect_pass: Pass | None = None,
) -> Verdict:
    """Fold one series' arrival history into a verdict.

    ``cohort_latest`` is the newest value date any selected series reached, so
    a curve that simply has not published today is separated from one that
    published late. Without it a dead feed would score a clean 100% on-time
    forever, on the strength of rows it stopped producing.

    ``now`` (SGT) decides whether a missing newest value date is late or
    merely not due yet, and is also why this is not judged on the latest day
    alone: the drift that prompted this script was *intermittent*. On
    2026-09-18 EUR ``3S6S_BASIS`` was back to completing on the 08:00 pass
    while still having missed it on 3 of the prior 8 value dates. A check that
    only looked at today would have printed "all clear" over exactly the
    pattern it was built to catch — hence ``INTERMITTENT``.
    """
    dates = series.dates
    if not dates:
        return Verdict(series, None, "BEHIND", None, None, None, [], [],
                       "no rows at all in the window")

    completion = {d: series.complete_pass(d, min_on_time) for d in dates}
    latest = dates[-1]

    baseline = expect_pass
    if baseline is None:
        # Learn the baseline from the settled part of the window only — the
        # newest value date is the one under suspicion and must not get a vote.
        prior = [d for d in dates[:-1] if completion[d] is not None]
        if len(prior) < 2:
            return Verdict(
                series, None, "SPARSE", latest, None, completion[latest],
                [], [],
                f"only {len(dates)} value date(s) in the window — need at "
                f"least 3 to learn a baseline, or pass --expect-pass",
            )
        counts = Counter(completion[d] for d in prior)
        # Ties break to the earlier pass: the stricter reading of "normal".
        baseline = min(counts, key=lambda p: (-counts[p], p))

    trend = [(d, series.on_time_pct(d, baseline)) for d in dates]
    late_dates = [d for d in dates
                  if completion[d] is not None and completion[d] > baseline]

    if latest < cohort_latest:
        due = pass_due_at(cohort_latest, baseline)
        if now < due:
            return Verdict(
                series, baseline, "PENDING", latest, None, completion[latest],
                trend, late_dates,
                f"{cohort_latest} is not due until {due:%Y-%m-%d %H:%M} SGT "
                f"on this series' {baseline.label} baseline",
            )
        behind = business_days_between(latest, cohort_latest)
        return Verdict(
            series, baseline, "BEHIND", latest, None, completion[latest],
            trend, late_dates,
            f"newest value date {latest} is {behind} business day(s) behind "
            f"the cohort's {cohort_latest}, whose {baseline.label} pass was "
            f"due {due:%Y-%m-%d %H:%M} SGT",
        )

    pct = series.on_time_pct(latest, baseline)
    done = completion[latest]
    if done is None:
        status = "BEHIND"
        note = f"no rows on {latest}"
    elif done > baseline:
        status = "LATE"
        note = (
            f"{latest} did not reach {min_on_time:.0f}% of its "
            f"{series.total(latest)} rows until {done.label}, against a "
            f"{baseline.label} baseline — {_pct(pct)} was in on time"
        )
    elif len(late_dates) > max_late_days:
        status = "INTERMITTENT"
        note = (
            f"{latest} completed on time, but {len(late_dates)} of "
            f"{len(dates)} value dates finished later than the "
            f"{baseline.label} baseline (max {max_late_days}): "
            + ", ".join(d.isoformat() for d in late_dates)
        )
    else:
        status = "OK"
        note = ""
    return Verdict(series, baseline, status, latest, pct, done, trend,
                   late_dates, note)


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------

_CURVE_SQL = """
SELECT id, ccy, curve, instrument, curve_status
  FROM rates.dim_curve
 WHERE 1 = 1
"""

# Grouping by the distinct load stamp keeps the result set tiny — one row per
# (curve, quote, value date, pass) rather than per observation — so the
# aggregation stays on the server and this never ships 23M rows over the wire.
_ARRIVAL_SQL = """
SELECT o.curve_id,
       o.quote,
       CAST(o.ts AS date) AS obs_date,
       CONVERT(varchar(19), SWITCHOFFSET(o.created_at, '+08:00'), 126) AS loaded_sgt,
       COUNT(*) AS n
  FROM rates.fact_observation o
 WHERE o.curve_id IN :curve_ids
   AND o.ts >= :start
   AND o.ts < :end
 GROUP BY o.curve_id, o.quote, CAST(o.ts AS date),
          CONVERT(varchar(19), SWITCHOFFSET(o.created_at, '+08:00'), 126)
"""

_TENOR_SQL = """
SELECT o.quote,
       o.tenor,
       CONVERT(varchar(19), SWITCHOFFSET(o.created_at, '+08:00'), 126) AS loaded_sgt
  FROM rates.fact_observation o
 WHERE o.curve_id = :curve_id
   AND o.ts >= :day
   AND o.ts < :next_day
"""


def _as_date(value) -> dt.date:
    """Narrow whatever the driver hands back to a plain ``date``.

    The pinned ``SQL Server`` ODBC driver returns DATE columns as ISO strings
    rather than ``datetime.date``, so string input is the normal path here.
    """
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    return dt.date.fromisoformat(str(value)[:10])


def select_curves(conn, curves, instruments, want_all) -> list[dict]:
    """Resolve the CLI's cohort flags to dim_curve rows.

    A curve named explicitly with ``--curve`` is returned whatever its
    ``curve_status``: asking for ``EUR.EURIBOR`` (status ``reformed``) and
    getting "no curves matched" back would be a lie about the database, and
    ceased curves are exactly where an arrival post-mortem tends to start.
    The active-only default applies to the *bulk* selectors, where it keeps
    dead curves from flooding the report.
    """
    params: dict = {}
    clauses: list[str] = []
    if curves:
        pairs = []
        for i, spec in enumerate(curves):
            if "." not in spec:
                raise ValueError(
                    f"--curve wants CCY.CURVE, got {spec!r} "
                    f"(e.g. EUR.3S6S_BASIS)")
            ccy, name = spec.split(".", 1)
            pairs.append(f"(ccy = :ccy{i} AND curve = :cv{i})")
            params[f"ccy{i}"] = ccy.upper()
            params[f"cv{i}"] = name.upper()
        clauses.append("(" + " OR ".join(pairs) + ")")
    else:
        if not want_all:
            clauses.append("curve_status = 'active'")
        if instruments:
            clauses.append("instrument IN :instruments")
            params["instruments"] = [i.lower() for i in instruments]
        elif not want_all:
            clauses.append("instrument = :instrument")
            params["instrument"] = DEFAULT_INSTRUMENT

    stmt = text(_CURVE_SQL
                + "".join(f"   AND {c}\n" for c in clauses)
                + " ORDER BY id")
    if "instruments" in params:
        stmt = stmt.bindparams(bindparam("instruments", expanding=True))
    return [
        {"id": r[0], "ccy": r[1], "curve": r[2],
         "instrument": r[3], "status": r[4]}
        for r in conn.execute(stmt, params)
    ]


def load_arrivals(conn, curve_rows, start: dt.date, end: dt.date,
                  quotes: list[str] | None) -> dict[tuple[int, str], Series]:
    meta = {c["id"]: c for c in curve_rows}
    stmt = text(_ARRIVAL_SQL).bindparams(bindparam("curve_ids", expanding=True))
    rows = conn.execute(stmt, {
        "curve_ids": sorted(meta),
        "start": start.isoformat(),
        "end": end.isoformat(),
    })

    wanted = {q.lower() for q in quotes} if quotes else None
    acc: dict[tuple[int, str], dict[dt.date, dict[Pass, int]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(int))
    )
    for curve_id, quote, obs_date, loaded_sgt, n in rows:
        if wanted and quote.lower() not in wanted:
            continue
        day = _as_date(obs_date)
        loaded = dt.datetime.fromisoformat(str(loaded_sgt)[:19])
        acc[(curve_id, quote)][day][arrival_pass(day, loaded)] += int(n)

    out: dict[tuple[int, str], Series] = {}
    for (curve_id, quote), by_date in acc.items():
        c = meta[curve_id]
        out[(curve_id, quote)] = Series(
            curve_id=curve_id, ccy=c["ccy"], curve=c["curve"], quote=quote,
            by_date={d: dict(slots) for d, slots in by_date.items()},
        )
    return out


def load_tenors(conn, curve_id: int, quote: str,
                day: dt.date) -> dict[Pass, list[str]]:
    rows = conn.execute(text(_TENOR_SQL), {
        "curve_id": curve_id,
        "day": day.isoformat(),
        "next_day": (day + dt.timedelta(days=1)).isoformat(),
    })
    out: dict[Pass, list[str]] = defaultdict(list)
    for q, tenor, loaded_sgt in rows:
        if q != quote:
            continue
        loaded = dt.datetime.fromisoformat(str(loaded_sgt)[:19])
        out[arrival_pass(day, loaded)].append(tenor)
    return {p: sorted(t) for p, t in sorted(out.items())}


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _pct(value: float | None) -> str:
    return "—" if value is None else f"{value:.0f}%"


TREND_DAYS = 8


def render_summary(verdicts: list[Verdict]) -> list[str]:
    ordered = sorted(verdicts,
                     key=lambda x: (STATUS_RANK[x.status], x.series.key))
    rows = [
        (f"{v.series.key} {v.series.quote}",
         v.baseline.label if v.baseline else "—",
         v.latest_date.isoformat() if v.latest_date else "—",
         _pct(v.latest_pct),
         f"{len(v.late_dates)}/{len(v.trend)}" if v.trend else "—",
         " ".join(_pct(p) for _, p in v.trend[-TREND_DAYS:]),
         v.status)
        for v in ordered
    ]
    trend_head = f"last {TREND_DAYS} on-time %"
    w_key = max([len(r[0]) for r in rows] + [12])
    w_trend = max([len(r[5]) for r in rows] + [len(trend_head)])
    header = (f"{'series':<{w_key}} {'baseline':>10} {'latest':>11} "
              f"{'on-time':>8} {'late':>6}  {trend_head:<{w_trend}} status")
    lines = [header, "-" * len(header)]
    for name, base, latest, pct, late, trend, status in rows:
        lines.append(f"{name:<{w_key}} {base:>10} {latest:>11} "
                     f"{pct:>8} {late:>6}  {trend:<{w_trend}} {status}")
    return lines


def render_detail(v: Verdict, tenors: dict[Pass, list[str]] | None,
                  threshold: float = DEFAULT_MIN_ON_TIME) -> list[str]:
    """Per-pass breakdown for one series.

    ``complete`` is the pass at which the day crossed ``threshold``% of its
    rows — the column the verdict is actually keyed on. ``first`` and
    ``last`` bracket it so a progressive build (par curves) is visibly
    different from a single-batch one (basis swaps).
    """
    s = v.series
    passes = s.passes()
    lines = ["", f"{s.key} · quote={s.quote} · curve {s.curve_id} · "
                 f"baseline {v.baseline.label if v.baseline else '—'}"]
    head = f"  {'value date':<16}" + "".join(f"{p.label:>11}" for p in passes)
    head += f"{'total':>8}{'on-time':>9}  {'first':<11}{'complete':<11}last"
    lines.append(head)
    for day, pct in v.trend:
        slots = s.by_date.get(day, {})
        row = f"  {day.isoformat()} {day.strftime('%a')[:3]:<3}"
        row += "".join(f"{slots.get(p, 0) or '-':>11}" for p in passes)
        first = s.first_pass(day)
        done = s.complete_pass(day, threshold)
        last = s.last_pass(day)
        row += f"{s.total(day):>8}{_pct(pct):>9}  "
        row += (f"{first.label if first else '—':<11}"
                f"{done.label if done else '—':<11}"
                f"{last.label if last else '—'}")
        lines.append(row)
    if v.note:
        lines.append(f"  !! {v.status} — {v.note}.")
    if tenors and v.latest_date:
        lines.append(f"  tenors on {v.latest_date.isoformat()}:")
        for p, names in tenors.items():
            shown = ", ".join(names[:14]) + (" …" if len(names) > 14 else "")
            lines.append(f"    {p.label:>11}  ({len(names):>3})  {shown}")
    return lines


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--as-of", default=None,
                    help="Window end, YYYY-MM-DD (default: today, local).")
    ap.add_argument("--days", type=int, default=DEFAULT_DAYS,
                    help=f"Value-date window (default: {DEFAULT_DAYS}, "
                         f"max {MAX_DAYS}).")
    ap.add_argument("--curve", action="append", default=None,
                    help="Restrict to CCY.CURVE, e.g. EUR.3S6S_BASIS; "
                         "repeatable. Overrides --instrument.")
    ap.add_argument("--instrument", action="append", default=None,
                    help=f"Restrict to a dim_curve.instrument; repeatable "
                         f"(default: {DEFAULT_INSTRUMENT}).")
    ap.add_argument("--quote", action="append", default=None,
                    help="Restrict to a quote, e.g. par; repeatable.")
    ap.add_argument("--all", action="store_true",
                    help="Every curve in dim_curve, ceased ones included. "
                         "Slow — pair with a short --days.")
    ap.add_argument("--expect-pass", default=None,
                    help="Declare the baseline instead of learning it, "
                         "e.g. 'B+1 08:00'.")
    ap.add_argument("--min-on-time", type=float, default=DEFAULT_MIN_ON_TIME,
                    help=f"Percent of a day's rows that must arrive by the "
                         f"baseline pass (default: {DEFAULT_MIN_ON_TIME:.0f}).")
    ap.add_argument("--max-late-days", type=int, default=DEFAULT_MAX_LATE_DAYS,
                    help=f"Value dates in the window allowed to miss the "
                         f"baseline before a series reads INTERMITTENT even "
                         f"when today is clean (default: "
                         f"{DEFAULT_MAX_LATE_DAYS}).")
    ap.add_argument("--detail", action="store_true",
                    help="Per-pass breakdown for every series, not just "
                         "flagged ones.")
    ap.add_argument("--tenors", action="store_true",
                    help="For flagged series, list which tenors landed in "
                         "which pass on the newest value date.")
    args = ap.parse_args(argv)

    if args.as_of:
        try:
            as_of = dt.date.fromisoformat(args.as_of)
        except ValueError:
            print(f"!! --as-of must be YYYY-MM-DD, got {args.as_of!r}",
                  file=sys.stderr)
            return 1
    else:
        as_of = dt.date.today()

    if not 1 <= args.days <= MAX_DAYS:
        print(f"!! --days must be 1..{MAX_DAYS}, got {args.days}",
              file=sys.stderr)
        return 1

    expect = None
    if args.expect_pass:
        try:
            expect = parse_pass(args.expect_pass)
        except ValueError as e:
            print(f"!! {e}", file=sys.stderr)
            return 1

    start = as_of - dt.timedelta(days=args.days)
    end = as_of + dt.timedelta(days=1)

    # Passes are stamped in SGT and this box runs on SGT, so local now is the
    # right clock. A historical --as-of is treated as fully elapsed: every pass
    # for that day has long since fired, so nothing there can be "not due yet".
    now = (dt.datetime.now() if as_of >= dt.date.today()
           else dt.datetime.combine(end, dt.time(0)))

    # Imported here so --help works without DB settings present.
    from imdr.config.settings import get_settings
    from imdr.connectors.mssql import MSSQLConnector

    connector = MSSQLConnector(get_settings())
    try:
        with connector.read_engine.connect() as conn:
            try:
                curve_rows = select_curves(
                    conn, args.curve, args.instrument, args.all)
            except ValueError as e:
                print(f"!! {e}", file=sys.stderr)
                return 1
            if not curve_rows:
                print("!! no curves matched — check --curve / --instrument "
                      "against rates.dim_curve.", file=sys.stderr)
                return 1

            series = load_arrivals(conn, curve_rows, start, end, args.quote)
            if not series:
                print(f"!! no observations for {len(curve_rows)} curve(s) "
                      f"between {start} and {as_of}.", file=sys.stderr)
                return 1

            cohort_latest = max(s.dates[-1] for s in series.values() if s.dates)
            verdicts = [
                evaluate(s, cohort_latest, now, args.min_on_time,
                         args.max_late_days, expect)
                for s in series.values()
            ]

            tenor_detail: dict[tuple[int, str], dict[Pass, list[str]]] = {}
            if args.tenors:
                for v in verdicts:
                    if v.flagged and v.latest_date:
                        tenor_detail[(v.series.curve_id, v.series.quote)] = \
                            load_tenors(conn, v.series.curve_id,
                                        v.series.quote, v.latest_date)
    finally:
        connector.dispose()

    print(f"Curve arrival — value dates {start} .. {as_of}, "
          f"{len(series)} series, as at {now:%Y-%m-%d %H:%M} SGT")
    print("Passes are business-day offsets from the value date; 'on-time' = "
          "share of a day's rows in by the baseline pass.\n")
    for line in render_summary(verdicts):
        print(line)

    for v in sorted(verdicts, key=lambda x: (STATUS_RANK[x.status],
                                             x.series.key)):
        if args.detail or v.flagged:
            key = (v.series.curve_id, v.series.quote)
            for line in render_detail(v, tenor_detail.get(key),
                                      args.min_on_time):
                print(line)

    flagged = [v for v in verdicts if v.flagged]
    print()
    if not flagged:
        print("Every series completed on its baseline pass — quote this "
              "run, not a remembered arrival time from a prior note.")
        return 0
    print(f"{len(flagged)} series flagged: " +
          ", ".join(f"{v.series.key} {v.series.quote} ({v.status})"
                    for v in flagged))
    return 1


if __name__ == "__main__":
    sys.exit(main())
