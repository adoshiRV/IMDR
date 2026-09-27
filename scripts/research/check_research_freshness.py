"""Freshness check for the research ingest lanes (portal + email).

Answers one question mechanically: **is each research lane still landing rows,
or has it gone quiet without anyone noticing?**

This exists because of a real failure. The email lane died on 2026-06-29 and
was not noticed until 2026-09-22 — 85 days. Everything needed to catch it was
already being written down: ``logs/research_ingest_*.summary.json`` recorded
``"failed": ["email-stage"]`` on twelve consecutive runs, and the high-water
marks in ``.hwm.json`` stopped advancing. Nothing read either. The scheduled
task kept succeeding on the portal lane, so the run looked healthy.

Two things went wrong, and this script blocks both:

1. **A dead lane looked identical to a quiet one.** ``dim_report`` simply
   stopped gaining email rows. No query asked "when did this lane last load?",
   so the absence never became a signal.
2. **The producer's failure was recorded but not escalated.** An rc captured
   in a JSON file that nothing reads is not monitoring.

Staleness is measured in **business days** between a lane's most recent
``publish_date`` and the as-of date. The thresholds are deliberately loose —
this catches lanes that are *dead*, not lanes having a slow day. A house that
publishes nothing over a long weekend is normal; a lane silent for a week is
not.

Exit codes:
    0  every lane fresh
    1  at least one lane stale (the alerting signal)
    2  could not evaluate (DB unreachable, etc.)

Usage:
    python -m scripts.research.check_research_freshness
    python -m scripts.research.check_research_freshness --as-of 2026-09-22
    python -m scripts.research.check_research_freshness --json
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

import numpy as np
from sqlalchemy import text

from imdr.config.settings import Settings
from imdr.connectors.mssql import MSSQLConnector

REPO_ROOT = Path(__file__).resolve().parents[2]
HWM_PATH = REPO_ROOT / "playground" / "research" / "outlook" / ".hwm.json"

# Business days a lane may go without a new report before it is called stale.
# Generous on purpose: the point is to catch death, not quiet.
LANE_TOLERANCE_BD: dict[str, int] = {
    "portal": 3,
    "email": 3,
}

# The mailbox producer's per-folder high-water marks. A folder legitimately
# goes quiet (Barclays sends little), so this is judged on the NEWEST mark
# across all folders — if *every* folder has stopped advancing, the producer
# itself is down.
HWM_TOLERANCE_BD = 3


@dataclass
class LaneReport:
    lane: str
    last_publish: date | None
    last_ingest: date | None
    reports: int
    stale_bd: int | None = None
    stale: bool = False
    note: str = ""


@dataclass
class FreshnessReport:
    as_of: date
    lanes: list[LaneReport] = field(default_factory=list)
    hwm_newest: date | None = None
    hwm_stale_bd: int | None = None
    hwm_stale: bool = False
    hwm_note: str = ""

    @property
    def any_stale(self) -> bool:
        return any(lane.stale for lane in self.lanes) or self.hwm_stale


def _as_date(value: object) -> date | None:
    """Coerce a driver value to a date.

    pyodbc hands back DATE columns as ``datetime.date`` on some driver builds
    and as an ISO string on others, so neither type can be assumed.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _business_days_between(start: date, end: date) -> int:
    """Business days from start to end (0 if end <= start)."""
    if end <= start:
        return 0
    return int(np.busday_count(start, end))


def _collect_lanes(as_of: date) -> list[LaneReport]:
    engine = MSSQLConnector(Settings()).read_engine
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT source,
                       COUNT(*)                   AS reports,
                       MAX(publish_date)          AS last_publish,
                       MAX(CAST(created_at AS date)) AS last_ingest
                FROM research.dim_report
                GROUP BY source
                """
            )
        ).fetchall()

    found = {r[0]: r for r in rows}
    out: list[LaneReport] = []
    for lane, tolerance in LANE_TOLERANCE_BD.items():
        row = found.get(lane)
        if row is None:
            out.append(
                LaneReport(
                    lane=lane, last_publish=None, last_ingest=None, reports=0,
                    stale=True, note="no rows for this source at all",
                )
            )
            continue

        _, reports, last_publish_raw, last_ingest_raw = row
        last_publish = _as_date(last_publish_raw)
        last_ingest = _as_date(last_ingest_raw)
        if last_publish is None:
            out.append(
                LaneReport(
                    lane=lane, last_publish=None, last_ingest=last_ingest,
                    reports=int(reports), stale=True,
                    note="rows exist but no usable publish_date",
                )
            )
            continue
        stale_bd = _business_days_between(last_publish, as_of)
        rep = LaneReport(
            lane=lane,
            last_publish=last_publish,
            last_ingest=last_ingest,
            reports=int(reports),
            stale_bd=stale_bd,
            stale=stale_bd > tolerance,
        )
        if rep.stale:
            rep.note = f"{stale_bd} business days since last report (tolerance {tolerance})"
        out.append(rep)
    return out


def _collect_hwm(as_of: date) -> tuple[date | None, int | None, bool, str]:
    """Newest high-water mark across the mailbox folders."""
    if not HWM_PATH.exists():
        return None, None, True, f"no high-water-mark file at {HWM_PATH}"

    try:
        hwm = json.loads(HWM_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return None, None, True, f"unreadable high-water-mark file: {exc}"

    marks: list[date] = []
    for value in hwm.values():
        try:
            marks.append(date.fromisoformat(str(value)[:10]))
        except ValueError:
            continue
    if not marks:
        return None, None, True, "high-water-mark file has no usable dates"

    newest = max(marks)
    stale_bd = _business_days_between(newest, as_of)
    stale = stale_bd > HWM_TOLERANCE_BD
    note = ""
    if stale:
        note = (
            f"producer has not advanced any folder in {stale_bd} business days "
            f"(tolerance {HWM_TOLERANCE_BD}) — check that classic Outlook is "
            f"running and logged on to its MAPI profile"
        )
    return newest, stale_bd, stale, note


def build_report(as_of: date) -> FreshnessReport:
    report = FreshnessReport(as_of=as_of, lanes=_collect_lanes(as_of))
    newest, stale_bd, stale, note = _collect_hwm(as_of)
    report.hwm_newest = newest
    report.hwm_stale_bd = stale_bd
    report.hwm_stale = stale
    report.hwm_note = note
    return report


def _print(report: FreshnessReport) -> None:
    print(f"Research lane freshness — as of {report.as_of.isoformat()}\n")
    print(f"  {'lane':8s} {'reports':>8s}  {'last publish':>12s}  {'last ingest':>12s}  status")
    for lane in report.lanes:
        status = "STALE" if lane.stale else "ok"
        lp = lane.last_publish.isoformat() if lane.last_publish else "-"
        li = lane.last_ingest.isoformat() if lane.last_ingest else "-"
        print(f"  {lane.lane:8s} {lane.reports:8d}  {lp:>12s}  {li:>12s}  {status}")
        if lane.note:
            print(f"           -> {lane.note}")

    newest = report.hwm_newest.isoformat() if report.hwm_newest else "-"
    print(f"\n  mailbox producer high-water mark: {newest} "
          f"({'STALE' if report.hwm_stale else 'ok'})")
    if report.hwm_note:
        print(f"           -> {report.hwm_note}")

    print()
    if report.any_stale:
        print("RESULT: STALE — at least one research lane has stopped landing rows.")
    else:
        print("RESULT: ok — every research lane is current.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--as-of", help="YYYY-MM-DD (default: today)")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of a table")
    args = ap.parse_args()

    as_of = (
        datetime.strptime(args.as_of, "%Y-%m-%d").date()
        if args.as_of
        else date.today()
    )

    try:
        report = build_report(as_of)
    except Exception as exc:  # noqa: BLE001 - a failed check must not look fresh
        print(f"could not evaluate research freshness: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(
            json.dumps(
                {
                    "as_of": report.as_of.isoformat(),
                    "any_stale": report.any_stale,
                    "lanes": [
                        {
                            "lane": lane.lane,
                            "reports": lane.reports,
                            "last_publish": lane.last_publish.isoformat() if lane.last_publish else None,
                            "last_ingest": lane.last_ingest.isoformat() if lane.last_ingest else None,
                            "stale_bd": lane.stale_bd,
                            "stale": lane.stale,
                            "note": lane.note,
                        }
                        for lane in report.lanes
                    ],
                    "hwm": {
                        "newest": report.hwm_newest.isoformat() if report.hwm_newest else None,
                        "stale_bd": report.hwm_stale_bd,
                        "stale": report.hwm_stale,
                        "note": report.hwm_note,
                    },
                },
                indent=2,
            )
        )
    else:
        _print(report)

    return 1 if report.any_stale else 0


if __name__ == "__main__":
    sys.exit(main())
