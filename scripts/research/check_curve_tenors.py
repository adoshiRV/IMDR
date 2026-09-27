"""Synthetic-tenor check for the rates curves Spider quotes from.

Answers one question mechanically, so no edition has to spot it by eye: **on each
active par curve, which tenors are real market quotes and which are just the anchor
tenor plus a fixed spread?**

A vendor curve is usually fitted to a handful of liquid points and interpolated or
extrapolated everywhere else. Where that happens the derived point does not trade: its
spread to the anchor is a construction constant, so a "move" in it is the anchor's move,
and a change in the constant is a config change wearing a market's clothes. Quoting such
a point as a market observation states something that never happened.

This exists because of a real error shipped in the **22 Sep 2026 daily digest**. It
reported, as its Greater China headline:

    "the 30-year is +17.3bp month-to-date against a 10-year -2.7bp, a 20bp
     steepening nobody in the window writes about"

Nobody wrote about it because it did not happen. Citi's CNY NDIRS 10s30s spread sat at
**0.00bp every day** from June through 04 Sep 2026 -- the 30Y equalled the 10Y to five
decimal places, with the 20Y about 2bp *above* both, an inverted hump no desk would
quote. On **07 Sep 2026** the spread stepped to exactly **20.00bp** overnight and has not
moved since (range 0.04bp over the following 12 sessions). CNY SHIBOR stepped
`-0.01 -> 40.00bp` the same day; MYR KLIBOR stepped `19.5 -> 23.4bp` on 02 Sep. So:

    30Y month-to-date  =  10Y month-to-date  +  the step
        +17.3bp        =      -2.7bp         +    +20.0bp

which is the printed number, exactly. The real China long end went the other way --
CGB 10s30s *flattened* about 3bp on the month -- and IMDR holds no CGB curve to have
caught it. The defect is Citi's curve construction, ingested faithfully; nothing in the
ingest path is wrong, which is why the guard has to live here, at authoring time.

What it flags, per (curve, tenor), against an anchor tenor (default 10Y):

  * **SYNTHETIC** -- the spread to the anchor is frozen on at least ``--frozen-pct`` of
    sessions. The tenor carries no information beyond the anchor. Do not quote it.
  * **STEP** -- a single session moved the spread by more than ``--step-bp`` while the
    series is otherwise frozen. This is the shape that fakes a month-to-date move; the
    report names the date and size so an author can see what a window spanning it buys.

Usage::

    # the survey -- every active par curve, last 90 sessions
    python scripts/research/check_curve_tenors.py

    # gate an edition: also fail if the MD quotes a flagged tenor
    python scripts/research/check_curve_tenors.py data/research_summary/daily/2026/09/22/spider-daily-digest.md

    python scripts/research/check_curve_tenors.py --lookback-days 180 --anchor 10Y
    python scripts/research/check_curve_tenors.py --ccy CNY --ccy INR

Exit code 0 = no digest given (survey only -- always advisory), or the digest quotes no
flagged tenor; 1 = the digest quotes a flagged tenor (or a bad argument). The survey
alone never blocks: a vendor's curve construction is an upstream fact that no edit to an
MD can fix, and gating on it would leave this check permanently red, which is how a gate
stops being read (the same reasoning as ``check_event_dates.py``). ``--strict`` makes the
survey block anyway.

Run it before locking a digest MD and quote its output rather than a remembered spread
-- see spider.md.
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

# A session-on-session spread change at or below this is "no change". Citi publishes par
# rates to 5dp (~0.001bp of resolution), so a genuinely traded spread never sits this
# still: on the real curves the mean absolute daily change is 0.4-1.4bp, and even the
# quietest (NZD BKBM, 0.42bp) clears this by an order of magnitude.
FROZEN_BP = 0.05

# Share of sessions that must be frozen before a tenor is called synthetic on that
# count alone. A tenor between the thresholds shows in the report marked THIN.
FROZEN_PCT = 90.0
THIN_PCT = 60.0

# The second route to a SYNTHETIC verdict, and the one that matters. Frozen-share alone
# under-calls a curve whose construction constant is *re-cut* every few weeks: each step
# is a non-frozen session, so MYR KLIBOR 30Y and PHP PHIREF 30Y score only ~70% frozen
# despite moving a mean 0.09bp and 0.04bp a session against 0.4-1.4bp on every real
# curve. Total variation separates them where frozen-share does not, so a tenor that is
# mostly frozen AND barely moves when it does is synthetic too. 0.15bp sits an order of
# magnitude below the quietest real curve (NZD BKBM, 0.42bp) and above every synthetic
# one, and it deliberately leaves VND VND_REF 30Y (1.02bp, genuinely illiquid rather
# than constructed) out of the SYNTHETIC class.
MAX_MEAN_BP = 0.15

# A one-session spread jump above this, on an otherwise frozen series, is a config
# change rather than a market. 3bp is wider than any single-session 10s30s move observed
# on the frozen curves and narrower than the 20bp/40bp steps this is meant to surface.
STEP_BP = 3.0

# Sessions needed before the statistics mean anything.
MIN_SESSIONS = 20

# Tenors worth testing by default: the ones the digest's curve tables actually print.
# Adjacent interpolated points (9Y, 11Y) are excluded on purpose -- a frozen 9s10s is
# ordinary curve construction and flagging it would bury the signal.
DEFAULT_TENORS = ("2Y", "5Y", "30Y")
DEFAULT_ANCHOR = "10Y"

_SQL = """
WITH ranked AS (
    SELECT c.id AS curve_id, c.ccy, c.curve,
           CAST(o.ts AS date) AS obs_date, o.tenor, o.value,
           ROW_NUMBER() OVER (
               PARTITION BY c.id, CAST(o.ts AS date), o.tenor
               ORDER BY o.ts DESC
           ) AS rn
    FROM rates.fact_observation o
    JOIN rates.dim_curve c ON c.id = o.curve_id
    WHERE o.quote = 'par'
      AND o.ts >= :start
      -- 'reformed' curves are live and quotable (they carry no cessation_date), and
      -- one of them, INR MIFOR, is the India row in the digest's own curve table.
      -- Filtering on 'active' alone silently excluded it from this check.
      AND c.curve_status IN ('active', 'reformed')
      AND o.tenor IN :tenors
)
SELECT curve_id, ccy, curve, obs_date, tenor, value
FROM ranked
WHERE rn = 1
ORDER BY ccy, curve, tenor, obs_date
"""


def as_date(value) -> dt.date | None:
    """Coerce a DB ``date`` to a ``datetime.date``.

    The legacy ODBC "SQL Server" driver this project pins hands back dates as *strings*
    ('2026-09-07'), not dates, so a naive isinstance check silently drops every row.
    """
    if value is None:
        return None
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    text = str(value).strip()[:10]
    try:
        return dt.date.fromisoformat(text)
    except ValueError:
        return None


class Finding:
    """One (curve, tenor) verdict against the anchor."""

    __slots__ = ("ccy", "curve", "tenor", "sessions", "frozen_pct",
                 "mean_abs_bp", "verdict", "steps", "last_spread_bp")

    def __init__(self, ccy: str, curve: str, tenor: str) -> None:
        self.ccy = ccy
        self.curve = curve
        self.tenor = tenor
        self.sessions = 0
        self.frozen_pct = 0.0
        self.mean_abs_bp = 0.0
        self.verdict = "OK"
        self.steps: list[tuple[dt.date, float]] = []
        self.last_spread_bp = 0.0

    @property
    def label(self) -> str:
        return f"{self.ccy} {self.curve}"


def evaluate(rows, anchor: str, tenors: tuple[str, ...],
             frozen_pct: float = FROZEN_PCT,
             step_bp: float = STEP_BP) -> tuple[list[Finding], list[str]]:
    """Turn raw observations into per-(curve, tenor) verdicts. Pure -- no I/O.

    Returns ``(findings, skipped)``. A (curve, tenor) pair with too little overlapping
    history to judge is *reported*, not dropped: "I could not tell" and "it is fine" are
    different answers, and a silent drop is how a curve the digest quotes stays invisible
    to its own gate.
    """
    # (curve_id, tenor) -> {date: value}
    series: dict[tuple[int, str], dict[dt.date, float]] = {}
    names: dict[int, tuple[str, str]] = {}

    for row in rows:
        obs_date = as_date(row.obs_date)
        if obs_date is None or row.value is None:
            continue
        names[row.curve_id] = (row.ccy, row.curve)
        series.setdefault((row.curve_id, row.tenor), {})[obs_date] = float(row.value)

    findings: list[Finding] = []
    skipped: list[str] = []
    for curve_id, (ccy, curve) in sorted(names.items(), key=lambda kv: kv[1]):
        anchor_series = series.get((curve_id, anchor))
        if not anchor_series:
            skipped.append(f"{ccy} {curve}: no {anchor} anchor in the window")
            continue
        for tenor in tenors:
            if tenor == anchor:
                continue
            leg = series.get((curve_id, tenor))
            if not leg:
                continue

            dates = sorted(set(leg) & set(anchor_series))
            if len(dates) <= MIN_SESSIONS:
                skipped.append(f"{ccy} {curve} {tenor}: only {len(dates)} session(s) "
                               f"overlap the {anchor} — too few to judge")
                continue

            # Spread in bp, then session-on-session change in that spread.
            spreads = [(d, 100.0 * (leg[d] - anchor_series[d])) for d in dates]
            changes = [
                (spreads[i][0], spreads[i][1] - spreads[i - 1][1])
                for i in range(1, len(spreads))
            ]
            if not changes:
                continue

            f = Finding(ccy, curve, tenor)
            f.sessions = len(changes)
            f.last_spread_bp = spreads[-1][1]
            f.mean_abs_bp = sum(abs(c) for _, c in changes) / len(changes)
            frozen = sum(1 for _, c in changes if abs(c) < FROZEN_BP)
            f.frozen_pct = 100.0 * frozen / len(changes)
            f.steps = [(d, c) for d, c in changes if abs(c) > step_bp]

            mostly_frozen = f.frozen_pct >= THIN_PCT
            if f.frozen_pct >= frozen_pct:
                f.verdict = "SYNTHETIC"
            elif mostly_frozen and f.mean_abs_bp < MAX_MEAN_BP:
                f.verdict = "SYNTHETIC"
            elif mostly_frozen:
                f.verdict = "THIN"
            findings.append(f)

    return findings, skipped


_TENOR_HDR = re.compile(r"^\**\s*(\d+)\s*(?:Y|-?\s*year)\s*\**$", re.I)


def _cells(line: str) -> list[str]:
    """Split a markdown table row into its cells."""
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _table_hits(lines: list[str], flagged: list[Finding]) -> list[tuple[Finding, int]]:
    """Flag table rows whose tenor COLUMN is synthetic.

    The digest's curve tables put the tenor in the header (``| Curve | Mark | 2Y | 5Y |
    10Y | 30Y | ... |``) and the curve in the row (``| China (NDIRS) | 11:00 | -0.4 |
    ...``), so no single line carries both tokens and a line-wise scan sees nothing. This
    is the shape that shipped the 22 Sep error, so it is the shape that matters most:
    walk each table, learn which column is which tenor, then test each row's curve
    against that column's contents.
    """
    hits: list[tuple[Finding, int]] = []
    tenor_cols: dict[int, str] = {}
    in_table = False

    for n, line in enumerate(lines, start=1):
        if not line.lstrip().startswith("|"):
            in_table = False
            tenor_cols = {}
            continue

        cells = _cells(line)
        if set("".join(cells)) <= set("-: "):        # the |---|---| separator
            in_table = bool(tenor_cols)
            continue

        if not in_table:                              # candidate header row
            found = {}
            for i, cell in enumerate(cells):
                m = _TENOR_HDR.match(cell)
                if m:
                    found[i] = f"{m.group(1)}Y"
            tenor_cols = found
            continue

        for f in flagged:                             # body row
            if not re.search(rf"\b{re.escape(f.curve)}\b", line, re.I):
                continue
            for i, tenor in tenor_cols.items():
                if tenor != f.tenor or i >= len(cells):
                    continue
                # Only a numeric cell is a quote; "n/a" or a blank is the fix.
                if re.search(r"\d", cells[i]):
                    hits.append((f, n))
    return hits


def quoted_in_digest(md_path: Path, flagged: list[Finding]) -> list[tuple[Finding, int]]:
    """Return (finding, line_number) for every flagged tenor the MD appears to quote.

    Two citation shapes are recognised, which between them cover how the digest names a
    curve: the table row form ``| China (NDIRS) | 11:00 | ... |`` and the prose form
    ``CNY NDIRS 2-year -1.4bp``. Both are matched on the curve token, then the line is
    tested for the tenor in either ``30Y`` or ``30-year`` spelling. This is a reading
    aid, not a parser -- it is deliberately eager, because a false flag costs one glance
    and a miss costs a printed number that never happened.
    """
    try:
        text = md_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"!! could not read {md_path}: {exc}", file=sys.stderr)
        return []

    hits: list[tuple[Finding, int]] = []
    lines = text.splitlines()

    # (a) prose: curve token and tenor token on the same line.
    for f in flagged:
        years = f.tenor[:-1] if f.tenor.endswith("Y") else f.tenor
        tenor_re = re.compile(rf"\b{re.escape(f.tenor)}\b|\b{years}[-\s]year\b", re.I)
        curve_re = re.compile(rf"\b{re.escape(f.curve)}\b", re.I)
        for n, line in enumerate(lines, start=1):
            if line.lstrip().startswith("|"):
                continue                      # tables are handled by _table_hits
            if curve_re.search(line) and tenor_re.search(line):
                hits.append((f, n))

    # (b) tables: tenor in the header, curve in the row.
    hits.extend(_table_hits(lines, flagged))
    return sorted(set(hits), key=lambda h: (h[1], h[0].label, h[0].tenor))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("digest", nargs="?", default=None,
                    help="Optional digest MD. When given, the check fails if the MD "
                         "quotes a flagged tenor.")
    ap.add_argument("--lookback-days", type=int, default=90,
                    help="Calendar days of history to test (default: 90).")
    ap.add_argument("--anchor", default=DEFAULT_ANCHOR,
                    help=f"Tenor every other tenor is measured against "
                         f"(default: {DEFAULT_ANCHOR}).")
    ap.add_argument("--tenor", action="append", default=None, dest="tenors",
                    help="Tenor to test; repeatable. Default: "
                         + ", ".join(DEFAULT_TENORS) + ".")
    ap.add_argument("--ccy", action="append", default=None,
                    help="Restrict to a currency; repeatable.")
    ap.add_argument("--frozen-pct", type=float, default=FROZEN_PCT,
                    help=f"Frozen-session share that calls a tenor synthetic "
                         f"(default: {FROZEN_PCT}).")
    ap.add_argument("--step-bp", type=float, default=STEP_BP,
                    help=f"One-session spread jump reported as a step "
                         f"(default: {STEP_BP}).")
    ap.add_argument("--all", action="store_true",
                    help="Also list curves whose tenors all look real.")
    ap.add_argument("--strict", action="store_true",
                    help="Exit 1 on any SYNTHETIC tenor even without a digest.")
    args = ap.parse_args(argv)

    if args.lookback_days < 1:
        print("!! --lookback-days must be >= 1", file=sys.stderr)
        return 1
    if not 0 < args.frozen_pct <= 100:
        print("!! --frozen-pct must be in (0, 100]", file=sys.stderr)
        return 1

    md_path: Path | None = None
    if args.digest:
        md_path = Path(args.digest)
        if not md_path.is_file():
            print(f"!! no such digest: {md_path}", file=sys.stderr)
            return 1

    anchor = args.anchor.upper()
    tenors = tuple(t.upper() for t in (args.tenors or DEFAULT_TENORS))
    start = dt.date.today() - dt.timedelta(days=args.lookback_days)

    # Imported here so --help works without DB settings present.
    from imdr.config.settings import get_settings
    from imdr.connectors.mssql import MSSQLConnector
    from sqlalchemy import bindparam, text

    stmt = text(_SQL).bindparams(bindparam("tenors", expanding=True))
    connector = MSSQLConnector(get_settings())
    try:
        with connector.read_engine.connect() as conn:
            # `start` goes over as an ISO string, not a date: the pinned legacy
            # "SQL Server" ODBC driver raises HYC00 (SQLBindParameter) on a bound
            # date object.
            rows = conn.execute(
                stmt,
                {"start": start.isoformat(), "tenors": list({*tenors, anchor})},
            ).fetchall()
    finally:
        connector.dispose()

    if not rows:
        print(f"!! no par observations since {start} -- nothing to test", file=sys.stderr)
        return 1

    findings, skipped = evaluate(rows, anchor, tenors,
                                 frozen_pct=args.frozen_pct, step_bp=args.step_bp)
    if args.ccy:
        wanted = {c.upper() for c in args.ccy}
        findings = [f for f in findings if f.ccy in wanted]
        skipped = [s for s in skipped if s.split()[0] in wanted]

    flagged = [f for f in findings if f.verdict == "SYNTHETIC"]
    thin = [f for f in findings if f.verdict == "THIN"]

    print(f"Curve-tenor check · anchor {anchor} · tenors {', '.join(tenors)} · "
          f"since {start} · {len({(f.ccy, f.curve) for f in findings})} curves")
    print()

    header = (f"{'curve':<18} {'tenor':>5} {'sess':>5} {'frozen%':>8} "
              f"{'mean|d|bp':>10} {'spread bp':>10}  verdict")
    print(header)
    print("-" * len(header))

    shown = flagged + thin + ([f for f in findings if f.verdict == "OK"] if args.all else [])
    for f in shown:
        print(f"{f.label:<18} {f.tenor:>5} {f.sessions:>5} {f.frozen_pct:>7.1f}% "
              f"{f.mean_abs_bp:>10.3f} {f.last_spread_bp:>10.2f}  {f.verdict}")
    if not shown:
        print("(every tested tenor moves independently of the anchor)")

    if flagged:
        print(f"\n!! {len(flagged)} tenor(s) are the {anchor} plus a construction "
              f"constant. They carry no information of their own -- do not quote a "
              f"level, a change or a curve trade from them.")
        for f in flagged:
            print(f"   {f.label} {f.tenor}: spread to {anchor} fixed near "
                  f"{f.last_spread_bp:.2f}bp on {f.frozen_pct:.1f}% of sessions")
            for when, size in f.steps:
                print(f"      !! STEP {when} {size:+.2f}bp — any window spanning this "
                      f"date shows it as a {f.tenor} move that did not happen")

    if thin:
        print(f"\n-- {len(thin)} tenor(s) are thin rather than synthetic: they move, but "
              f"sit still most sessions. Quotable with a caveat; do not build a headline "
              f"on a single session's move.")

    if skipped:
        print(f"\n-- {len(skipped)} (curve, tenor) pair(s) could not be judged — this is "
              f"'unknown', not 'clean':")
        for line in skipped[:40]:
            print(f"   {line}")
        if len(skipped) > 40:
            print(f"   ... and {len(skipped) - 40} more")

    exit_code = 0

    if md_path is not None:
        hits = quoted_in_digest(md_path, flagged)
        print(f"\nDigest: {md_path}")
        if hits:
            print(f"!! {len(hits)} line(s) quote a synthetic tenor:")
            for f, line_no in hits:
                print(f"   {md_path}:{line_no}  {f.label} {f.tenor}")
            print("\nReplace the cell or clause with an explicit 'n/a', and say why in "
                  "one line, rather than printing a number that is the anchor in "
                  "disguise.")
            exit_code = 1
        else:
            print("No line quotes a synthetic tenor — this edition is clear on this "
                  "check.")
    elif args.strict and flagged:
        exit_code = 1

    if exit_code == 0 and not flagged:
        print("\nEvery tested tenor is an independent quote — read the curve as printed.")
    elif exit_code == 0:
        print("\nSurvey only, so this is advisory: the construction is the vendor's and "
              "no edit here changes it. Pass a digest MD to gate an edition on it.")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
