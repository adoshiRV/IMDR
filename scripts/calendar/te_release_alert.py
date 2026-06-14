"""15-minute TE macro-release digest emailer.

Run cadence: every 15 minutes via Windows Task Scheduler (manual setup
by user — NOT auto-wired into any orchestrator).

Per tick:
  1. Refresh the TE calendar (single polite GET on the rolling 4-week
     window, idempotent MERGE).
  2. Collect rows whose `actual` transitioned to a real value in this
     tick (NULL -> value, or revised value -> value).
  3. Filter to importance >= settings.te_alert_importance_threshold
     (default 66 = TE imp 2 + 3).
  4. If nothing changed, exit quietly. Otherwise render one digest email
     and send via Outlook.

Idempotency: the scraper's MERGE only sees a "change" on the FIRST tick
that observes a new actual. Subsequent ticks see old_actual == new_actual
and emit zero alerts. So a successful send is naturally non-repeated.

Subject prefix is `[Macro]` (not `[IMDR]`) so that user-side filters
keyed on `[IMDR]` do not catch these alerts.

Usage
-----
    # Live tick — fetch + parse + upsert + (maybe) email
    python -m scripts.calendar.te_release_alert

    # Dry run — fetch + parse + classify, print subject + body to stdout, no email
    python -m scripts.calendar.te_release_alert --dry-run

    # Replay a saved snapshot (formatter iteration; no network, no email)
    python -m scripts.calendar.te_release_alert --dry-run \
        --html-file playground/econ/calendars/_out/te_ok_<stamp>.html

    # One-off threshold override (e.g. only TE imp=3 = relevance>=90)
    python -m scripts.calendar.te_release_alert --threshold 90

Set in .env to enable:
    IMDR_EMAIL_ENABLED=true
    IMDR_TE_ALERT_ENABLED=true
    IMDR_EMAIL_MACRO_TO=adoshi@rvcapital.com;...    # falls back to IMDR_EMAIL_TO
    IMDR_TE_ALERT_IMPORTANCE_THRESHOLD=66
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import date
from pathlib import Path

import structlog
from sqlalchemy.orm import Session

from imdr.config.settings import get_settings
from imdr.connectors.mssql import MSSQLConnector
from imdr.market_calendar.te_scraper import (
    ActualChange,
    default_window,
    refresh,
)
from imdr.notifications.email import send_outlook_email
from imdr.notifications.formatters.te_release_alert import TEReleaseAlertFormatter
from imdr.utils.logging import configure_logging

log = structlog.get_logger(__name__)


def _resolve_recipients(settings) -> str:
    """email_macro_to -> falls back to email_to. Semicolon-separated."""
    return (settings.email_macro_to or settings.email_to or "").strip()


def _filter_changes(
    changes: list[ActualChange],
    threshold: float,
) -> list[ActualChange]:
    """Keep only changes whose relevance meets the threshold.

    Rows with NULL relevance (e.g. some no-time speech events) are dropped
    — they wouldn't be data releases worth alerting on anyway.
    """
    return [c for c in changes if c.relevance is not None and c.relevance >= threshold]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run the refresh + classification but do not send email.",
    )
    parser.add_argument(
        "--html-file",
        type=Path,
        default=None,
        help="Replay a saved /calendar HTML snapshot (no network). "
             "Implies --dry-run and DB upsert is still attempted.",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="Override IMDR_TE_ALERT_IMPORTANCE_THRESHOLD for this run.",
    )
    parser.add_argument(
        "--d1", type=date.fromisoformat, default=None,
        help="Window start (YYYY-MM-DD). Defaults to today - 7d.",
    )
    parser.add_argument(
        "--d2", type=date.fromisoformat, default=None,
        help="Window end (YYYY-MM-DD). Defaults to today + 21d.",
    )
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings)

    if not settings.te_alert_enabled and not args.dry_run:
        log.info("te_alert.disabled", msg="set IMDR_TE_ALERT_ENABLED=true to send")
        return 0

    if args.html_file is None and args.d1 is None and args.d2 is None:
        args.d1, args.d2 = default_window()

    html_override: str | None = None
    if args.html_file:
        if not args.html_file.exists():
            log.error("html_file_not_found", path=str(args.html_file))
            return 1
        html_override = args.html_file.read_text(encoding="utf-8")

    threshold = args.threshold if args.threshold is not None else settings.te_alert_importance_threshold

    t0 = time.perf_counter()
    connector = MSSQLConnector(settings)
    try:
        with Session(connector.engine) as session:
            result = refresh(
                session,
                d1=args.d1,
                d2=args.d2,
                dry_run=False,             # we always commit so re-runs are idempotent
                html_override=html_override,
            )
    finally:
        connector.engine.dispose()
    elapsed = time.perf_counter() - t0

    all_changes = result.actual_changes
    qualified = _filter_changes(all_changes, threshold)

    log.info(
        "te_alert.tick",
        parsed=result.parsed,
        inserted=result.inserted,
        updated_actual=result.updated_actual,
        n_changes_total=len(all_changes),
        n_changes_qualified=len(qualified),
        threshold=threshold,
        elapsed=round(elapsed, 2),
    )

    if not qualified:
        print(f"[te_alert] no qualifying changes (parsed={result.parsed}, threshold={threshold})")
        return 0

    formatter = TEReleaseAlertFormatter()
    subject = formatter.format_subject(qualified)
    body = formatter.format_body(qualified)

    if args.dry_run or args.html_file:
        print()
        print("=== DRY RUN — would send the following email ===")
        print(f"SUBJECT: {subject}")
        print(f"BODY length: {len(body):,} chars")
        # Save body to a tmp file so the user can open it in a browser
        out_path = Path("data/_tmp/te_alert_preview.html")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(body, encoding="utf-8")
        print(f"BODY preview written to: {out_path}")
        return 0

    to = _resolve_recipients(settings)
    if not to:
        log.error("te_alert.no_recipients",
                  msg="set IMDR_EMAIL_MACRO_TO or IMDR_EMAIL_TO")
        return 1

    sent = send_outlook_email(
        to=to,
        subject=subject,
        html_body=body,
        importance=1,
    )
    if not sent:
        log.error("te_alert.send_failed", subject=subject)
        return 1

    log.info("te_alert.sent", to=to, subject=subject, n=len(qualified))
    print(f"[te_alert] sent {len(qualified)} releases to {to}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
