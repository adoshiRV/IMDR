"""FX Vol Citi Velocity Daily EOD Runner.

Target table: [fx].[fact_vol]
Schedule: Daily (via Windows Task Scheduler or cron)
Source: Citi Velocity Historical Data API (OAuth2)

Usage:
    python -m scripts.fx.citi.fx_vol_citi_live
    python -m scripts.fx.citi.fx_vol_citi_live --date 2026-03-10
    python -m scripts.fx.citi.fx_vol_citi_live --pairs EUR/USD,GBP/USD
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
from imdr.domains.fx.pipeline_vol import FXVolPipeline
from imdr.market_calendar.calendar import last_business_day
from imdr.market_calendar.holidays import holiday_hits_for_timestamp
from imdr.notifications.email import send_outlook_email
from imdr.notifications.formatters.fx_vol_ingest import FXVolIngestFormatter
from imdr.reporting.run_report import RunReport
from imdr.universe.fx import get_fx_universe
from imdr.utils.logging import configure_logging

log = structlog.get_logger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="FX Vol Citi Velocity Daily EOD Ingest")
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Override date to process (YYYY-MM-DD). Default: last business day.",
    )
    parser.add_argument(
        "--pairs",
        type=str,
        default=None,
        help="Comma-separated pairs (e.g. EUR/USD,GBP/USD). Default: all from universe.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = get_settings()
    configure_logging(settings)

    universe = get_fx_universe()
    report = RunReport(pipeline_name="fx.vol_citi_live")

    # Determine target date
    if args.date:
        target = datetime.strptime(args.date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    else:
        target = last_business_day("US")

    start = target
    end = target.replace(hour=23, minute=59)

    # Parse pairs override
    pairs: list[tuple[str, str]] | None = None
    if args.pairs:
        pairs = [tuple(p.strip().split("/")) for p in args.pairs.split(",")]

    log.info("fx_vol_citi_live_start", date=str(target.date()), n_pairs=len(pairs or universe.vol_pairs()))

    connector = MSSQLConnector(settings)
    try:
        t0 = time.perf_counter()
        pipeline = FXVolPipeline(
            connector=connector,
            settings=settings,
            universe=universe,
            start=start,
            end=end,
            pairs=pairs,
            chunk_size=settings.bulk_batch_size,
        )
        result = pipeline.run()
        elapsed = time.perf_counter() - t0

        # Build per-pair breakdown from raw data
        pair_data = []
        missing_pairs_list: list[str] = []
        all_vol_pairs = pairs or universe.vol_pairs()

        if pipeline._raw_df is not None and not pipeline._raw_df.empty:
            loaded_pairs = set(
                zip(pipeline._raw_df["base_ccy"], pipeline._raw_df["quote_ccy"])
            )
            for ccy1, ccy2 in all_vol_pairs:
                pair_name = f"{ccy1}/{ccy2}"
                non_usd = ccy1 if ccy1 != "USD" else ccy2
                ccy_class = universe.classification_for(non_usd)
                if (ccy1, ccy2) in loaded_pairs:
                    n_obs = len(pipeline._raw_df[
                        (pipeline._raw_df["base_ccy"] == ccy1)
                        & (pipeline._raw_df["quote_ccy"] == ccy2)
                    ])
                    pair_data.append({"pair": pair_name, "n_obs": n_obs, "ccy_class": ccy_class})
                else:
                    pair_data.append({"pair": pair_name, "n_obs": 0, "ccy_class": ccy_class})
                    missing_pairs_list.append(pair_name)
        else:
            for ccy1, ccy2 in all_vol_pairs:
                pair_name = f"{ccy1}/{ccy2}"
                missing_pairs_list.append(pair_name)

        report.info("pipeline", f"Loaded {result} rows", details={
            "date": str(target.date()),
            "n_pairs": len(all_vol_pairs),
            "rows_loaded": result,
            "elapsed_secs": round(elapsed, 1),
            "quota_usage": pipeline._quota_usage,
        })

        # Surface extraction errors (non-quota API failures)
        if pipeline._extraction_errors:
            report.warning(
                "extraction_errors",
                f"{len(pipeline._extraction_errors)} pair(s) failed during extraction",
                details={"errors": pipeline._extraction_errors},
            )

        # Holiday check for all vol currencies
        vol_ccys = list({ccy for pair in all_vol_pairs for ccy in pair})
        holiday_hits = holiday_hits_for_timestamp(vol_ccys, target)
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
                report=report,
                target=target,
                result=result,
                pair_data=pair_data,
                missing_pairs=missing_pairs_list,
                holiday_hits=holiday_hits,
                elapsed_secs=elapsed,
                n_pairs=len(all_vol_pairs),
                rows_extracted=len(pipeline._raw_df) if pipeline._raw_df is not None else 0,
            )

        report.finish()

        # Flush RunReport to JSONL
        if settings.run_log_dir:
            log_path = (
                Path(settings.run_log_dir)
                / "fx"
                / "fact_vol"
                / f"fx_vol_citi_live_{target:%Y%m%d}.jsonl"
            )
            report.flush_jsonl(log_path)

        log.info("fx_vol_citi_live_complete", date=str(target.date()), rows=result, elapsed=f"{elapsed:.1f}s")
        return 0

    except TagQuotaExceeded as e:
        log.error("fx_vol_citi_live_tag_quota_exceeded",
                  current_usage=getattr(e, "current_usage", None),
                  available=getattr(e, "available", None))
        report.error("tag_quota", f"Tag quota exceeded: {e}",
                     details={"current_usage": getattr(e, "current_usage", None),
                              "available": getattr(e, "available", None)})
        report.finish()

        if settings.run_log_dir:
            log_path = (
                Path(settings.run_log_dir)
                / "fx"
                / "fact_vol"
                / f"fx_vol_citi_live_{target:%Y%m%d}.jsonl"
            )
            report.flush_jsonl(log_path)

        return 1
    except Exception:
        log.exception("fx_vol_citi_live_failed")
        report.error("pipeline", "Daily FX vol ingest failed")
        report.finish()
        return 1
    finally:
        connector.dispose()


def _send_report_email(
    pipeline: FXVolPipeline,
    settings: object,
    report: RunReport,
    target: datetime,
    result: int,
    pair_data: list[dict],
    missing_pairs: list[str],
    holiday_hits: list,
    elapsed_secs: float,
    n_pairs: int,
    rows_extracted: int,
) -> None:
    """Build and send the FX vol ingest report email."""
    formatter = FXVolIngestFormatter()
    has_errors = report.has_errors

    subject = formatter.format_subject(
        pipeline_name="fx.vol_citi_live",
        run_date=target,
        rows_loaded=result,
        n_pairs=n_pairs,
        has_errors=has_errors,
    )
    body = formatter.format_body(
        pipeline_name="fx.vol_citi_live",
        run_date=target,
        rows_extracted=rows_extracted,
        rows_loaded=result,
        n_pairs=n_pairs,
        pair_data=pair_data,
        missing_pairs=missing_pairs,
        holiday_hits=[
            {"currency": h.currency, "market_code": h.market_code, "name": h.name}
            for h in holiday_hits
        ],
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
