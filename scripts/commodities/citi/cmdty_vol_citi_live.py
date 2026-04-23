"""Commodities Implied Vol Citi Velocity Daily EOD Runner.

Target table: [commodities].[fact_implied_vol]
Schedule: Daily (via imdr_daily.py)
Source: Citi Velocity Historical Data API

Usage:
    python -m scripts.commodities.citi.cmdty_vol_citi_live
    python -m scripts.commodities.citi.cmdty_vol_citi_live --date 2026-03-25
    python -m scripts.commodities.citi.cmdty_vol_citi_live --products XAU,XAG
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import structlog

from imdr.config.settings import get_settings
from imdr.connectors.citi_helpers import TagQuotaExceeded
from imdr.connectors.mssql import MSSQLConnector
from imdr.domains.commodities.pipeline_vol import CmdtyImpliedVolPipeline
from imdr.market_calendar.calendar import last_business_day
from imdr.market_calendar.holidays import holiday_hits_for_timestamp
from imdr.notifications.email import send_outlook_email
from imdr.notifications.formatters.cmdty_ingest import CmdtyIngestFormatter
from imdr.reporting.run_report import RunReport
from imdr.universe.commodities import get_commodities_universe
from imdr.utils.logging import configure_logging

log = structlog.get_logger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Commodities Implied Vol Daily EOD Ingest")
    parser.add_argument("--date", type=str, default=None, help="Override date (YYYY-MM-DD)")
    parser.add_argument("--products", type=str, default=None,
                        help="Comma-separated products (e.g. XAU,XAG). Default: all.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = get_settings()
    configure_logging(settings)
    universe = get_commodities_universe()
    report = RunReport(pipeline_name="commodities.vol_citi_live")

    if args.date:
        target = datetime.strptime(args.date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    else:
        target = last_business_day("US")

    start = target
    end = target.replace(hour=23, minute=59)

    products: list[str] | None = None
    if args.products:
        products = [p.strip().upper() for p in args.products.split(",")]

    all_products = products or universe.vol_products()
    log.info("cmdty_vol_live_start", date=str(target.date()), n_products=len(all_products))

    connector = MSSQLConnector(settings)
    try:
        t0 = time.perf_counter()
        pipeline = CmdtyImpliedVolPipeline(
            connector=connector, settings=settings,
            universe=universe, start=start, end=end,
            products=products, chunk_size=settings.bulk_batch_size,
        )
        result = pipeline.run()
        elapsed = time.perf_counter() - t0

        # Build per-product breakdown
        product_data: list[dict] = []
        if pipeline._raw_df is not None and not pipeline._raw_df.empty:
            for p in all_products:
                n_obs = len(pipeline._raw_df[pipeline._raw_df["product"] == p])
                product_data.append({"product": p, "n_obs": n_obs})
        else:
            for p in all_products:
                product_data.append({"product": p, "n_obs": 0})

        report.info("pipeline", f"Loaded {result} rows", details={
            "date": str(target.date()),
            "n_products": len(all_products),
            "rows_loaded": result,
            "elapsed_secs": round(elapsed, 1),
            "quota_usage": pipeline._quota_usage,
            "product_breakdown": product_data,
        })

        if pipeline._extraction_errors:
            report.warning("extraction_errors",
                f"{len(pipeline._extraction_errors)} product(s) failed",
                details={"errors": pipeline._extraction_errors})

        # Holiday detection
        holiday_hits = holiday_hits_for_timestamp(["USD"], target)
        if holiday_hits:
            report.info("holidays", f"Holiday hits: {len(holiday_hits)}", details={
                "hits": [{"currency": h.currency, "market_code": h.market_code,
                          "name": h.name} for h in holiday_hits],
            })

        # Send email notification
        if settings.email_enabled and settings.email_to:
            _send_report_email(
                settings=settings,
                report=report,
                target=target,
                result=result,
                product_data=product_data,
                holiday_hits=holiday_hits,
                elapsed_secs=elapsed,
                pipeline_name="commodities.vol_citi_live",
                n_products=len(all_products),
                rows_extracted=len(pipeline._raw_df) if pipeline._raw_df is not None else 0,
            )

        report.finish()
        if settings.run_log_dir:
            log_path = (
                Path(settings.run_log_dir)
                / "commodities" / "fact_implied_vol"
                / f"cmdty_vol_citi_live_{target:%Y%m%d}.jsonl"
            )
            report.flush_jsonl(log_path)

        log.info("cmdty_vol_live_complete", date=str(target.date()),
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
                / "commodities" / "fact_implied_vol"
                / f"cmdty_vol_citi_live_{target:%Y%m%d}.jsonl"
            )
            report.flush_jsonl(log_path)
        return 1
    except Exception:
        log.exception("cmdty_vol_live_failed")
        report.error("pipeline", "Daily commodity vol ingest failed")
        report.finish()
        return 1
    finally:
        connector.dispose()


def _send_report_email(
    settings: object,
    report: RunReport,
    target: datetime,
    result: int,
    product_data: list[dict],
    holiday_hits: list,
    elapsed_secs: float,
    pipeline_name: str,
    n_products: int,
    rows_extracted: int,
) -> None:
    """Build and send the commodity vol ingest report email."""
    formatter = CmdtyIngestFormatter()
    has_errors = report.has_errors

    subject = formatter.format_subject(
        pipeline_name=pipeline_name,
        run_date=target,
        rows_loaded=result,
        n_products=n_products,
        has_errors=has_errors,
    )
    body = formatter.format_body(
        pipeline_name=pipeline_name,
        run_date=target,
        rows_extracted=rows_extracted,
        rows_loaded=result,
        n_products=n_products,
        product_data=product_data,
        holiday_hits=[
            {"currency": h.currency, "market_code": h.market_code, "name": h.name}
            for h in holiday_hits
        ],
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
