"""IMDR Cross-Domain Staleness Check.

Queries every fact table at the per-key level and flags any series
whose latest observation is older than its configured threshold.
Sends a consolidated HTML email via Outlook if any staleness is found.

Designed to run after the nightly pipeline batch (imdr_daily.py) to
catch silent upstream feed drops that don't cause pipeline failures.

Usage:
    python -m scripts.imdr_staleness_check
    python -m scripts.imdr_staleness_check --date 2026-04-13
    python -m scripts.imdr_staleness_check --always-email
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timezone

import structlog

from imdr.config.settings import get_settings
from imdr.connectors.mssql import MSSQLConnector
from imdr.healthchecks.staleness import StalenessMonitor
from imdr.notifications.email import send_outlook_email
from imdr.notifications.formatters.staleness_alert import StalenessAlertFormatter

log = structlog.get_logger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="IMDR cross-domain staleness check")
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Reference date (YYYY-MM-DD). Defaults to today.",
    )
    parser.add_argument(
        "--always-email",
        action="store_true",
        default=False,
        help="Send email even when all domains are fresh.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = get_settings()

    ref_date: date
    if args.date:
        ref_date = date.fromisoformat(args.date)
    else:
        ref_date = date.today()

    print(f"Staleness check | reference_date={ref_date}")

    connector = MSSQLConnector(settings)
    try:
        monitor = StalenessMonitor.from_config(connector, reference_date=ref_date)
        report = monitor.run()

        # ── Console output ─────────────────────────────────────────
        print(f"\nChecked {len(report.summaries)} domains at {report.checked_at:%H:%M:%S} UTC")
        print(f"Reference date: {report.reference_date}\n")

        for s in report.summaries:
            status = "STALE" if s.is_stale else "OK"
            print(
                f"  {'!' if s.is_stale else ' '} {s.domain:<28s} "
                f"{status:<6s}  {s.stale_keys}/{s.total_keys} stale  "
                f"latest={s.latest_date}"
            )
            for sk in s.stale_items:
                print(f"        -> {sk.label:<30s}  last={sk.latest_date}  ({sk.days_behind}d behind)")

        if report.has_stale:
            print(f"\nTOTAL: {report.total_stale_keys} stale key(s) across "
                  f"{len(report.stale_domains)} domain(s)")
        else:
            print("\nAll domains fresh.")

        # ── Email ──────────────────────────────────────────────────
        should_email = report.has_stale or args.always_email
        if should_email and settings.email_enabled and settings.email_to:
            formatter = StalenessAlertFormatter()
            subject = formatter.format_subject(report=report)
            body = formatter.format_body(report=report)
            importance = 2 if report.has_stale else 1
            send_outlook_email(
                to=settings.email_to,
                subject=subject,
                html_body=body,
                importance=importance,
            )
            print(f"\nEmail sent to {settings.email_to}")
        elif should_email:
            print("\nEmail not sent (email_enabled=False or email_to empty)")

        return 1 if report.has_stale else 0
    finally:
        connector.dispose()


if __name__ == "__main__":
    sys.exit(main())
