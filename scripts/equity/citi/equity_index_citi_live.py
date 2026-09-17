"""Equity Index Citi Velocity Daily EOD Runner.

Target table: [equities].[fact_index_level]
Schedule: Daily (via imdr_daily.py)
Source: Citi Velocity Historical Data API

Usage:
    python -m scripts.equity.citi.equity_index_citi_live
    python -m scripts.equity.citi.equity_index_citi_live --date 2026-03-25
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import structlog

from imdr.config.settings import get_settings
from imdr.connectors.citi_helpers import TagQuotaExceeded
from imdr.connectors.mssql import MSSQLConnector
from imdr.domains.equity.pipeline_index import EquityIndexPipeline
from imdr.market_calendar.calendar import last_business_day_any
from imdr.market_calendar.holidays import holiday_hits_for_timestamp
from imdr.notifications.email import send_outlook_email
from imdr.notifications.formatters.equity_ingest import EquityIngestFormatter
from imdr.reporting.run_report import RunReport
from imdr.universe.equity import get_equity_universe
from imdr.utils.logging import configure_logging

log = structlog.get_logger(__name__)

# Calendar days of trailing re-fetch on each run (see fetch_start below).
_FETCH_LOOKBACK_DAYS = 5

# Second Citi OAuth client + its own tag-quota bucket, as rates/fx already use.
# Exposed as a FLAG, not a module constant like rates_citi_historical's
# USE_HOURLY_CREDS: a constant left flipped silently reroutes every later
# scheduled run, and this one is only ever wanted for a manual repair.
_HOURLY_QUOTA_FILE = "data/cache/citi_tag_quota_hourly.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Equity Index Daily EOD Ingest")
    parser.add_argument("--date", type=str, default=None, help="Override date (YYYY-MM-DD)")
    parser.add_argument(
        "--fetch-from", type=str, default=None, metavar="YYYY-MM-DD",
        help=(
            "Start the vendor fetch here instead of the default window. Use for "
            "REPAIRS: Citi caps calls PER TAG (10 per rolling 24h), and that cap "
            "counts calls, not days -- one range call covers a whole gap for the "
            "same cost as one single-day call. Repairing 12 days as a loop of "
            "--date runs burns 12 of the 10 available and dies partway; the same "
            "repair as one --fetch-from run costs 1."
        ),
    )
    parser.add_argument(
        "--use-hourly-creds", action="store_true",
        help=(
            "Route through the SECOND Citi OAuth client and its own tag-quota "
            "bucket. Citi meters both a rolling-24h tag quota and a per-tag "
            "call cap (10/24h) per app registration, so a repair on the primary "
            "key competes with the scheduled pipelines for both. Use for "
            "backfills, especially alongside --fetch-from."
        ),
    )
    return parser.parse_args()


def resolve_fetch_start(
    target: datetime,
    fetch_from: str | None,
    date_given: bool,
) -> datetime:
    """Where the vendor fetch starts, given the anchor and the CLI flags.

    Three cases, in precedence order:

      * ``--fetch-from`` -- an explicit repair window. Opt-in, so it does not
        violate the ``--date`` rule below: the operator asked for a range.
        Raises ValueError if it starts after the anchor, which would be an
        empty or backwards window.
      * ``--date`` alone -- exactly that day. A targeted repair or replay;
        widening it would silently rewrite neighbouring days too.
      * neither (the scheduled run) -- reach back _FETCH_LOOKBACK_DAYS so
        late-publishing tags land. The anchor advances as soon as the first
        exchange completes a session, so any one date is the anchor only
        briefly -- too briefly for FTSE, which Citi serves 12-20h after the
        LSE close. Upserts make re-fetching a settled day a no-op.
    """
    if fetch_from:
        started = datetime.strptime(fetch_from, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        if started > target:
            raise ValueError(
                f"--fetch-from {started.date()} is after the anchor {target.date()}"
            )
        return started
    if date_given:
        return target
    return (target - timedelta(days=_FETCH_LOOKBACK_DAYS)).replace(
        hour=0, minute=0, second=0, microsecond=0,
    )


def main() -> int:
    args = parse_args()
    settings = get_settings()
    configure_logging(settings)
    universe = get_equity_universe()
    report = RunReport(pipeline_name="equity.index_citi_live")

    if args.date:
        target = datetime.strptime(args.date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    else:
        # Anchor on the union of every exchange in the universe, not on one
        # market. Anchoring on US/GT silently dropped 2026-09-07 (US Labor Day)
        # even though 11 of 13 exchange calendars traded that day: four runs
        # logged "success" while all four re-wrote 09-04. Switching to NY would
        # not have helped -- NYSE was shut too.
        target = last_business_day_any(universe.market_calendars())

    start = target
    end = target.replace(hour=23, minute=59)
    try:
        fetch_start = resolve_fetch_start(target, args.fetch_from, bool(args.date))
    except ValueError as e:
        log.error("fetch_window_invalid", error=str(e))
        return 2

    if args.use_hourly_creds and not (
        settings.citi_hourly_client_id and settings.citi_hourly_client_secret
    ):
        log.error("hourly_creds_missing",
                  hint="set IMDR_CITI_HOURLY_CLIENT_ID / _SECRET, or drop the flag")
        return 2

    log.info("equity_index_live_start", date=str(target.date()),
             fetch_from=str(fetch_start.date()),
             creds="hourly" if args.use_hourly_creds else "primary",
             markets=len(universe.market_calendars()))

    connector = MSSQLConnector(settings)
    try:
        t0 = time.perf_counter()
        pipeline = EquityIndexPipeline(
            connector=connector, settings=settings,
            universe=universe, start=start, end=end,
            fetch_start=fetch_start,
            client_id=settings.citi_hourly_client_id if args.use_hourly_creds else None,
            client_secret=(
                settings.citi_hourly_client_secret if args.use_hourly_creds else None
            ),
            quota_tracker_path=_HOURLY_QUOTA_FILE if args.use_hourly_creds else None,
        )
        result = pipeline.run()
        elapsed = time.perf_counter() - t0

        # `result` spans the whole re-fetch window, so it must never be the
        # only number reported against the anchor date -- 5 settled days
        # re-upserting reads as success while the anchor contributed nothing.
        anchor_rows = pipeline.anchor_row_count
        report.info("pipeline", f"Loaded {result} rows ({anchor_rows} for {target.date()})",
                    details={
                        "date": str(target.date()),
                        "rows_loaded": result,
                        "rows_anchor_day": anchor_rows,
                        "fetch_from": str(fetch_start.date()),
                        "elapsed_secs": round(elapsed, 1),
                        "quota_usage": pipeline._quota_usage,
                    })

        if anchor_rows == 0:
            report.warning("anchor_day_empty",
                f"No rows for {target.date()} — the vendor served nothing for "
                f"the anchor session. The {result} rows loaded are backfill of "
                f"earlier days and do NOT mean this run succeeded.",
                details={"date": str(target.date()), "rows_loaded": result})

        # A vendor fetch that ERRORED is a failed run, not a warning. The
        # extractor swallows the exception and returns an empty frame, so
        # without this the process logged "index_fetch_failed" at ERROR, loaded
        # nothing, printed health_checks_passed and exited 0 — indistinguishable
        # from a quiet day. That is how four days of a 2026-09-15 FTSE repair
        # silently did nothing after Citi's per-tag call cap cut in.
        # Health checks cannot catch it: they count rows in the TABLE for the
        # run date, so pre-existing rows from other tickers satisfy them.
        # Only genuine fetch failures land here — per-tag EMPTY payloads for a
        # closed market go to a separate sink (_collect_tag_errors).
        if pipeline._extraction_errors:
            report.error("extraction_errors",
                f"Vendor fetch failed ({len(pipeline._extraction_errors)} error(s)) — "
                f"loaded {result} row(s), nothing can be concluded from this run",
                details={"errors": pipeline._extraction_errors})
            report.finish()
            if settings.run_log_dir:
                report.flush_jsonl(
                    Path(settings.run_log_dir) / "equities" / "fact_index_level"
                    / f"equity_index_citi_live_{target:%Y%m%d}.jsonl"
                )
            log.error("equity_index_live_failed_extraction",
                      date=str(target.date()), rows=result,
                      errors=pipeline._extraction_errors)
            return 1

        # Holiday detection
        holiday_hits = holiday_hits_for_timestamp(universe.target_currencies(), target)
        if holiday_hits:
            report.info("holidays", f"Holiday hits: {len(holiday_hits)}", details={
                "hits": [{"currency": h.currency, "country_code": h.country_code,
                          "name": h.name} for h in holiday_hits],
            })

        # Send email notification
        if settings.email_enabled and settings.email_to:
            _send_report_email(
                settings=settings,
                report=report,
                target=target,
                result=result,
                holiday_hits=holiday_hits,
                elapsed_secs=elapsed,
                quota_usage=pipeline._quota_usage,
            )

        report.finish()
        if settings.run_log_dir:
            log_path = (
                Path(settings.run_log_dir)
                / "equities" / "fact_index_level"
                / f"equity_index_citi_live_{target:%Y%m%d}.jsonl"
            )
            report.flush_jsonl(log_path)

        log.info("equity_index_live_complete", date=str(target.date()),
                 rows=result, elapsed=f"{elapsed:.1f}s")
        return 0

    except TagQuotaExceeded as e:
        log.error("tag_quota_exceeded",
                  current_usage=getattr(e, "current_usage", None),
                  available=getattr(e, "available", None))
        report.error("tag_quota", f"Tag quota exceeded: {e}",
                     details={"current_usage": getattr(e, "current_usage", None),
                              "available": getattr(e, "available", None)})
        report.finish()
        if settings.run_log_dir:
            log_path = (
                Path(settings.run_log_dir)
                / "equities" / "fact_index_level"
                / f"equity_index_citi_live_{target:%Y%m%d}.jsonl"
            )
            report.flush_jsonl(log_path)
        return 1
    except Exception:
        log.exception("equity_index_live_failed")
        report.error("pipeline", "Daily equity index ingest failed")
        report.finish()
        return 1
    finally:
        connector.dispose()


def _send_report_email(
    settings: object,
    report: RunReport,
    target: datetime,
    result: int,
    holiday_hits: list,
    elapsed_secs: float,
    quota_usage: int | None = None,
) -> None:
    """Build and send the equity index ingest report email."""
    formatter = EquityIngestFormatter()
    has_errors = report.has_errors

    subject = formatter.format_subject(
        pipeline_name="equity.index_citi_live",
        run_date=target,
        rows_loaded=result,
        has_errors=has_errors,
    )
    body = formatter.format_body(
        pipeline_name="equity.index_citi_live",
        run_date=target,
        rows_loaded=result,
        holiday_hits=[
            {"currency": h.currency, "country_code": h.country_code, "name": h.name}
            for h in holiday_hits
        ],
        has_errors=has_errors,
        elapsed_secs=elapsed_secs,
        quota_usage=quota_usage,
    )
    send_outlook_email(
        to=settings.email_to,  # type: ignore[attr-defined]
        subject=subject,
        html_body=body,
        importance=2 if has_errors else 1,
    )


if __name__ == "__main__":
    sys.exit(main())
