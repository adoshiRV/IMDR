"""Rates Swaption Vol Citi Velocity Daily EOD Runner.

Target table: [rates].[fact_swaption_vol]
Schedule: Daily (via Windows Task Scheduler or cron)
Source: Citi Velocity Historical Data API (OAuth2)

Usage:
    python -m scripts.rates.citi.rates_vol_citi_live
    python -m scripts.rates.citi.rates_vol_citi_live --date 2026-03-10
    python -m scripts.rates.citi.rates_vol_citi_live --currencies USD,EUR,JPY
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
from imdr.market_calendar.calendar import last_business_day
from imdr.domains.rates.pipeline_vol import RatesVolPipeline
from imdr.notifications.email import send_outlook_email
from imdr.notifications.formatters.rates_vol_ingest import RatesVolIngestFormatter
from imdr.reporting.run_report import RunReport
from imdr.universe.rates import get_rates_universe
from imdr.utils.logging import configure_logging

log = structlog.get_logger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rates Swaption Vol Daily EOD Ingest")
    parser.add_argument(
        "--date", type=str, default=None,
        help="Override date to process (YYYY-MM-DD). Default: last business day.",
    )
    parser.add_argument(
        "--currencies", type=str, default=None,
        help="Comma-separated currencies (e.g. USD,EUR,JPY). Default: all from universe.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = get_settings()
    configure_logging(settings)

    universe = get_rates_universe()
    report = RunReport(pipeline_name="rates.vol_citi_live")

    # Determine target date
    if args.date:
        target = datetime.strptime(args.date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    else:
        target = last_business_day("US")

    start = target
    end = target.replace(hour=23, minute=59)

    # Parse currencies override
    currencies: list[str] | None = None
    if args.currencies:
        currencies = [c.strip().upper() for c in args.currencies.split(",")]

    vol_ccys = currencies or universe.vol_currencies()
    log.info("rates_vol_citi_live_start", date=str(target.date()), n_currencies=len(vol_ccys))

    connector = MSSQLConnector(settings)
    try:
        t0 = time.perf_counter()
        pipeline = RatesVolPipeline(
            connector=connector,
            settings=settings,
            universe=universe,
            start=start,
            end=end,
            currencies=currencies,
            chunk_size=settings.bulk_batch_size,
        )
        result = pipeline.run()
        elapsed = time.perf_counter() - t0

        # Build per-currency breakdown
        rfr_set = set(universe.vol.rfr_currencies)
        ccy_data = []
        missing_ccys: list[str] = []
        if pipeline._raw_df is not None and not pipeline._raw_df.empty:
            for ccy in vol_ccys:
                n_obs = len(pipeline._raw_df[pipeline._raw_df["ccy"] == ccy])
                ccy_data.append({
                    "ccy": ccy,
                    "n_obs": n_obs,
                    "has_rfr": ccy in rfr_set,
                    "classification": universe.classification_for(ccy),
                })
                if n_obs == 0:
                    missing_ccys.append(ccy)
        else:
            for ccy in vol_ccys:
                ccy_data.append({
                    "ccy": ccy,
                    "n_obs": 0,
                    "has_rfr": ccy in rfr_set,
                    "classification": universe.classification_for(ccy),
                })
                missing_ccys.append(ccy)

        report.info("pipeline", f"Loaded {result} rows", details={
            "date": str(target.date()),
            "n_currencies": len(vol_ccys),
            "rows_loaded": result,
            "elapsed_secs": round(elapsed, 1),
            "per_currency": ccy_data,
            "quota_usage": pipeline._quota_usage,
        })

        # Surface extraction errors (non-quota API failures)
        if pipeline._extraction_errors:
            report.warning(
                "extraction_errors",
                f"{len(pipeline._extraction_errors)} currency(s) failed during extraction",
                details={"errors": pipeline._extraction_errors},
            )

        # Send email notification
        if settings.email_enabled and settings.email_to:
            _send_report_email(
                pipeline=pipeline,
                settings=settings,
                report=report,
                target=target,
                result=result,
                ccy_data=ccy_data,
                missing_ccys=missing_ccys,
                elapsed_secs=elapsed,
                n_currencies=len(vol_ccys),
                rows_extracted=len(pipeline._raw_df) if pipeline._raw_df is not None else 0,
            )

        report.finish()

        # Flush RunReport to JSONL
        if settings.run_log_dir:
            log_path = (
                Path(settings.run_log_dir)
                / "rates"
                / "swaption_vol"
                / f"rates_vol_citi_live_{target:%Y%m%d}.jsonl"
            )
            report.flush_jsonl(log_path)

        log.info(
            "rates_vol_citi_live_complete",
            date=str(target.date()),
            rows=result,
            elapsed=f"{elapsed:.1f}s",
        )
        return 0

    except TagQuotaExceeded as e:
        log.error("rates_vol_citi_live_tag_quota_exceeded",
                  current_usage=getattr(e, "current_usage", None),
                  available=getattr(e, "available", None))
        report.error("tag_quota", f"Tag quota exceeded: {e}",
                     details={"current_usage": getattr(e, "current_usage", None),
                              "available": getattr(e, "available", None)})
        report.finish()

        if settings.run_log_dir:
            log_path = (
                Path(settings.run_log_dir)
                / "rates"
                / "swaption_vol"
                / f"rates_vol_citi_live_{target:%Y%m%d}.jsonl"
            )
            report.flush_jsonl(log_path)

        return 1
    except Exception:
        log.exception("rates_vol_citi_live_failed")
        report.error("pipeline", "Daily rates swaption vol ingest failed")
        report.finish()
        return 1
    finally:
        connector.dispose()


def _send_report_email(
    pipeline: RatesVolPipeline,
    settings: object,
    report: RunReport,
    target: datetime,
    result: int,
    ccy_data: list[dict],
    missing_ccys: list[str],
    elapsed_secs: float,
    n_currencies: int,
    rows_extracted: int,
) -> None:
    """Build and send the rates swaption vol ingest report email."""
    formatter = RatesVolIngestFormatter()
    has_errors = report.has_errors

    subject = formatter.format_subject(
        pipeline_name="rates.vol_citi_live",
        run_date=target,
        rows_loaded=result,
        n_currencies=n_currencies,
        has_errors=has_errors,
    )
    body = formatter.format_body(
        pipeline_name="rates.vol_citi_live",
        run_date=target,
        rows_extracted=rows_extracted,
        rows_loaded=result,
        n_currencies=n_currencies,
        ccy_data=ccy_data,
        missing_ccys=missing_ccys,
        quality_flags=pipeline._quality_results,
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
