"""Import the most recent canonical holiday-calendar snapshot into
``calendar.market_holidays``.

This is the canonical weekly refresh path for IMDR's holiday calendar. The
Friday 11:00 ``refresh_calendar.py`` scheduled task writes a fresh BBG
snapshot to
``Z:\\...\\IMDR_MANUAL_UPLOADS\\Calendar\\YYYY\\MM\\calendar_YYYYMMDD.xlsx``.
This script walks that tree, picks the file with the greatest date in its
filename, parses it via ``load_calendar_pasted_xlsx``, and idempotently
inserts any holiday dates not already in the DB. Re-running is safe — rows
already present are skipped. On completion it sends a confirmation email
(when ``IMDR_EMAIL_ENABLED=true`` and ``IMDR_EMAIL_TO`` is set).

Wired into ``scripts/imdr_weekly.py``.

Usage:
    python -m scripts.calendar.import_latest_holiday_calendar_snapshot
    python -m scripts.calendar.import_latest_holiday_calendar_snapshot --root <path> --dry-run
"""

from __future__ import annotations

import argparse
import re
import sys
import time
import traceback
from datetime import date, datetime, timezone
from pathlib import Path

import structlog

from imdr.config.settings import get_settings
from imdr.connectors.mssql import MSSQLConnector
from imdr.notifications.email import send_outlook_email
from imdr.notifications.formatters.holiday_calendar_ingest import (
    HolidayCalendarIngestFormatter,
)
from imdr.utils.logging import configure_logging
from scripts.calendar.load_calendar_pasted_xlsx import (
    lookup_ids,
    parse_xlsx,
    upsert_holidays,
)

log = structlog.get_logger(__name__)

DEFAULT_ROOT = Path(
    r"Z:\Business\Personnel\Arjun\IMDR_MANUAL_UPLOADS\Calendar"
)
_NAME_RE = re.compile(r"^calendar_(\d{8})\.xlsx$", re.IGNORECASE)


def find_latest_snapshot(root: Path) -> tuple[Path, str]:
    """Return ``(path, YYYYMMDD)`` for the snapshot with the greatest date.

    Searches ``root/YYYY/MM/calendar_YYYYMMDD.xlsx``. Raises FileNotFoundError
    if no matching file exists.
    """
    candidates: list[tuple[str, Path]] = []
    for p in root.glob("*/*/calendar_*.xlsx"):
        m = _NAME_RE.match(p.name)
        if m:
            candidates.append((m.group(1), p))
    if not candidates:
        msg = f"no calendar_YYYYMMDD.xlsx found under {root}"
        raise FileNotFoundError(msg)
    candidates.sort(key=lambda t: t[0])
    return candidates[-1][1], candidates[-1][0]


def _send_email(
    settings,
    *,
    snapshot_path: str,
    snapshot_date: str,
    duration_s: float,
    calendars: int,
    total_parsed: int,
    inserted: int,
    skipped: int,
    load_batch: str,
    per_calendar: list[dict],
    missing: list[str],
    error: str,
) -> None:
    if not (getattr(settings, "email_enabled", False) and getattr(settings, "email_to", "")):
        log.info("email_disabled_skipping_holiday_calendar_confirmation")
        return
    formatter = HolidayCalendarIngestFormatter()
    subject = formatter.format_subject(
        snapshot_date=snapshot_date, inserted=inserted,
        calendars=calendars, missing=missing, error=error,
    )
    body = formatter.format_body(
        snapshot_path=snapshot_path,
        snapshot_date=snapshot_date,
        run_time_utc=datetime.now(timezone.utc),
        duration_s=duration_s,
        calendars=calendars,
        total_parsed=total_parsed,
        inserted=inserted,
        skipped=skipped,
        load_batch=load_batch,
        rows=per_calendar,
        missing=missing,
        error=error,
    )
    importance = 2 if (error or missing) else 1
    send_outlook_email(
        to=settings.email_to,
        subject=subject, html_body=body,
        importance=importance,
    )


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--root", type=Path, default=DEFAULT_ROOT,
        help=f"Snapshot root. Default: {DEFAULT_ROOT}",
    )
    p.add_argument(
        "--load-batch", default=None,
        help="Tag stamped on inserted rows. Defaults to bbg_weekly_<YYYYMMDD>.",
    )
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    settings = get_settings()
    configure_logging(settings)

    t0 = time.perf_counter()
    snapshot_path = ""
    snapshot_date = ""
    inserted = skipped = total_parsed = calendars = 0
    per_calendar: list[dict] = []
    missing: list[str] = []
    error_msg = ""
    load_batch = args.load_batch or f"bbg_weekly_{date.today():%Y%m%d}"

    try:
        if not args.root.exists():
            msg = f"snapshot root missing: {args.root}"
            log.error("snapshot_root_missing", root=str(args.root))
            error_msg = msg
            raise FileNotFoundError(msg)

        xlsx, snapshot_date = find_latest_snapshot(args.root)
        snapshot_path = str(xlsx)
        log.info("latest_snapshot", path=snapshot_path, snapshot_date=snapshot_date)

        parsed = parse_xlsx(xlsx)
        calendars = len(parsed)
        total_parsed = sum(len(v) for v in parsed.values())
        log.info(
            "parsed_xlsx",
            path=snapshot_path, calendars=calendars, total_dates=total_parsed,
        )

        connector = MSSQLConnector(settings)
        try:
            with connector.session() as session:
                cal_map, vendor_id = lookup_ids(session)
                inserted, skipped, missing, per_calendar = upsert_holidays(
                    session, cal_map, vendor_id, parsed, load_batch, args.dry_run,
                )
                if args.dry_run:
                    session.rollback()
        finally:
            connector.dispose()
    except Exception as e:
        log.exception("holiday_calendar_weekly_import_failed")
        if not error_msg:
            error_msg = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"

    duration_s = time.perf_counter() - t0

    log.info(
        "import_complete",
        dry_run=args.dry_run,
        inserted=inserted,
        skipped_existing=skipped,
        missing_calendar_codes=missing,
        load_batch=load_batch,
        source=snapshot_path,
        error=bool(error_msg),
    )

    _send_email(
        settings,
        snapshot_path=snapshot_path,
        snapshot_date=snapshot_date,
        duration_s=duration_s,
        calendars=calendars,
        total_parsed=total_parsed,
        inserted=inserted,
        skipped=skipped,
        load_batch=load_batch,
        per_calendar=per_calendar,
        missing=missing,
        error=error_msg,
    )

    if error_msg:
        return 2
    return 0 if not missing else 1


if __name__ == "__main__":
    sys.exit(main())
