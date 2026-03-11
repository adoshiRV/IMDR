"""Rates Citi Velocity Daily EOD Runner.

Target table: [rates].[fact_observation]
Schedule: Daily (via Windows Task Scheduler or cron)
Source: Citi Velocity Historical Data API (OAuth2)

Usage:
    python -m scripts.rates.citi.rates_citi_live
    python -m scripts.rates.citi.rates_citi_live --date 2026-03-07
    python -m scripts.rates.citi.rates_citi_live --quotes par,spread,fwd
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import structlog

from imdr.config.pipeline_config import get_pipeline_config
from imdr.config.settings import get_settings
from imdr.connectors.mssql import MSSQLConnector
from imdr.domains.rates.pipeline import RatesHistoricalPipeline
from imdr.market_calendar.holidays import holiday_hits_for_timestamp
from imdr.notifications.email import send_outlook_email
from imdr.notifications.formatters.rates_ingest import RatesIngestFormatter
from imdr.reporting.run_report import RunReport
from imdr.universe.rates import get_rates_universe
from imdr.utils.logging import configure_logging

log = structlog.get_logger(__name__)


def _last_business_day() -> datetime:
    """Return the most recent completed business day (Mon-Fri) in UTC."""
    today = datetime.now(timezone.utc).date()
    yesterday = today - timedelta(days=1)
    # Walk back over weekends: Sun→Fri, Sat→Fri
    while yesterday.weekday() >= 5:  # 5=Sat, 6=Sun
        yesterday -= timedelta(days=1)
    return datetime(yesterday.year, yesterday.month, yesterday.day, tzinfo=timezone.utc)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rates Citi Velocity Daily EOD Ingest")
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Override date to process (YYYY-MM-DD). Default: last business day.",
    )
    parser.add_argument(
        "--quotes",
        type=str,
        default=None,
        help="Comma-separated quote types. Default: loaded from pipelines.yml. Options: par,spread,fwd,bfly,ssw,rc",
    )
    parser.add_argument(
        "--frequency",
        type=str,
        default="DAILY",
        help="Data frequency (default: DAILY).",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable empty combo cache (retry all API calls).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = get_settings()
    configure_logging(settings)

    universe = get_rates_universe()
    report = RunReport(pipeline_name="rates.citi_live")

    # Determine target date
    if args.date:
        target = datetime.strptime(args.date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    else:
        target = _last_business_day()

    # Weekend check
    if target.weekday() >= 5:
        log.info("rates_weekend_skip", date=str(target.date()), day=target.strftime("%A"))
        report.info("market", f"Weekend date {target.date()} — skipping")
        report.finish()
        return 0

    start = target
    end = target.replace(hour=23, minute=59)

    # Resolve quotes: CLI override > pipelines.yml config > fallback "par"
    if args.quotes is not None:
        quotes = [q.strip() for q in args.quotes.split(",")]
    else:
        pipeline_config = get_pipeline_config("rates.historical")
        quotes = pipeline_config.default_quotes or ["par"]

    log.info("rates_citi_live_start", date=str(target.date()), quotes=quotes, frequency=args.frequency)

    connector = MSSQLConnector(settings)
    try:
        t0 = time.perf_counter()
        pipeline = RatesHistoricalPipeline(
            connector=connector,
            settings=settings,
            universe=universe,
            start=start,
            end=end,
            quotes=quotes,
            frequency=args.frequency,
            use_cache=not args.no_cache,
        )
        result = pipeline.run()
        elapsed = time.perf_counter() - t0

        report.info("pipeline", f"Loaded {result} rows", details={
            "date": str(target.date()),
            "quotes": quotes,
            "rows_loaded": result,
            "elapsed_secs": round(elapsed, 1),
        })

        # Holiday check for all rates currencies
        rates_ccys = universe.target_currencies()
        holiday_hits = holiday_hits_for_timestamp(rates_ccys, target)
        if holiday_hits:
            report.info("holidays", f"Holiday hits: {len(holiday_hits)}", details={
                "hits": [{"currency": h.currency, "market_code": h.market_code, "name": h.name}
                         for h in holiday_hits],
            })

        # Send email notification
        if settings.email_enabled and settings.email_to:
            _send_report_email(
                pipeline=pipeline,
                settings=settings,
                universe=universe,
                report=report,
                target=target,
                quotes=quotes,
                frequency=args.frequency,
                rows_loaded=result,
                rows_extracted=len(pipeline._raw_df) if pipeline._raw_df is not None else 0,
                holiday_hits=holiday_hits,
                elapsed_secs=elapsed,
            )

        report.finish()

        # Flush RunReport to JSONL
        if settings.run_log_dir:
            log_path = (
                Path(settings.run_log_dir)
                / "rates"
                / "fact_observation"
                / f"rates_citi_live_{target:%Y%m%d}.jsonl"
            )
            report.flush_jsonl(log_path)

        log.info("rates_citi_live_complete", date=str(target.date()), rows=result, elapsed=f"{elapsed:.1f}s")
        return 0

    except Exception:
        log.exception("rates_citi_live_failed")
        report.error("pipeline", "Daily rates ingest failed")
        report.finish()
        return 1
    finally:
        connector.dispose()


def _send_report_email(
    pipeline: RatesHistoricalPipeline,
    settings: object,
    universe: object,
    report: RunReport,
    target: datetime,
    quotes: list[str],
    frequency: str,
    rows_loaded: int,
    rows_extracted: int,
    holiday_hits: list,
    elapsed_secs: float,
) -> None:
    """Build and send the rates ingest report email."""
    # Gather curve info for email
    all_curves = universe.all_curves()  # type: ignore[attr-defined]
    curve_data = []
    for c in all_curves:
        classification = universe.classification_for(c.ccy)  # type: ignore[attr-defined]
        curve_data.append({
            "ccy": c.ccy,
            "curve": c.curve,
            "classification": classification,
            "status": c.status,
            "tenors": len(universe.maturities_for_curve(c.ccy, c.curve)),  # type: ignore[attr-defined]
            "rows": 0,  # populated below if we have raw data
        })

    # Missing curves = curves with 0 rows in output
    missing = []
    if pipeline._raw_df is not None and not pipeline._raw_df.empty:
        loaded_keys = set(zip(pipeline._raw_df["ccy"], pipeline._raw_df["curve"]))
        for cd in curve_data:
            if (cd["ccy"], cd["curve"]) in loaded_keys:
                cd["rows"] = len(pipeline._raw_df[
                    (pipeline._raw_df["ccy"] == cd["ccy"]) &
                    (pipeline._raw_df["curve"] == cd["curve"])
                ])
            else:
                missing.append({"ccy": cd["ccy"], "curve": cd["curve"], "reason": "No data returned"})
    else:
        missing = [{"ccy": c["ccy"], "curve": c["curve"], "reason": "No data returned"} for c in curve_data]

    formatter = RatesIngestFormatter()
    has_errors = report.has_errors

    subject = formatter.format_subject(
        pipeline_name="rates.citi_live",
        run_date=target,
        rows_loaded=rows_loaded,
        has_errors=has_errors,
    )
    body = formatter.format_body(
        pipeline_name="rates.citi_live",
        run_date=target,
        quotes=quotes,
        frequency=frequency,
        rows_extracted=rows_extracted,
        rows_loaded=rows_loaded,
        n_curves=len(all_curves),
        curves=curve_data,
        missing_curves=missing,
        holiday_hits=[
            {"currency": h.currency, "market_code": h.market_code, "name": h.name}
            for h in holiday_hits
        ],
        freshness=pipeline._metadata_freshness,
        has_errors=has_errors,
        elapsed_secs=elapsed_secs,
    )
    send_outlook_email(
        to=settings.email_to,  # type: ignore[attr-defined]
        subject=subject,
        html_body=body,
        importance=2 if has_errors else 1,
    )


if __name__ == "__main__":
    sys.exit(main())
