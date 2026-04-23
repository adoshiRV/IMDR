"""Central Bank Policy Rates — Citi Velocity Daily EOD Runner.

Target table: [rates].[fact_bench_rates]
Schedule: Daily (via imdr_daily.py)
Source: Citi Velocity RATES.BENCH_RATES.* (10 tags, ~8 return data)

Usage:
    python -m scripts.rates.citi.rates_bench_citi_live
    python -m scripts.rates.citi.rates_bench_citi_live --date 2026-04-15
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
from imdr.domains.rates.pipeline_bench import BenchRatesPipeline
from imdr.market_calendar.calendar import last_business_day, last_trading_day
from imdr.market_calendar.holidays import holiday_hits_for_timestamp
from imdr.notifications.email import send_outlook_email
from imdr.notifications.formatters.rates_bench_ingest import RatesBenchIngestFormatter
from imdr.reporting.run_report import RunReport
from imdr.universe.rates import get_rates_universe
from imdr.utils.logging import configure_logging

log = structlog.get_logger(__name__)


LOOKBACK_DAYS = 5


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Central Bank Policy Rates Daily EOD Ingest")
    parser.add_argument("--date", type=str, default=None, help="Override date (YYYY-MM-DD)")
    parser.add_argument("--lookback", type=int, default=LOOKBACK_DAYS,
                        help="Trading days to look back (default: 5) — absorbs vendor publish lag")
    return parser.parse_args()


def _start_of_window(target: datetime, n_trading_days: int, market: str = "US") -> datetime:
    """Walk back `n_trading_days` trading days from target (exclusive of target)."""
    d = target.date()
    for _ in range(n_trading_days):
        d = last_trading_day(market, before=d)
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)


def main() -> int:
    args = parse_args()
    settings = get_settings()
    configure_logging(settings)
    universe = get_rates_universe()
    report = RunReport(pipeline_name="rates.bench_rates_citi_live")

    if args.date:
        target = datetime.strptime(args.date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    else:
        target = last_business_day("US")

    start = _start_of_window(target, args.lookback)
    end = target.replace(hour=23, minute=59)

    log.info("bench_rates_live_start", date=str(target.date()),
             window_start=str(start.date()), lookback=args.lookback)

    connector = MSSQLConnector(settings)
    try:
        t0 = time.perf_counter()
        pipeline = BenchRatesPipeline(
            connector=connector,
            settings=settings,
            universe=universe,
            start=start,
            end=end,
        )
        result = pipeline.run()
        elapsed = time.perf_counter() - t0

        # Build per-CB breakdown
        bench_entries = universe.bench_rates_entries()
        cb_data: list[dict] = []
        missing_cbs: list[str] = []
        if pipeline._raw_df is not None and not pipeline._raw_df.empty:
            for entry in bench_entries:
                rows = pipeline._raw_df[pipeline._raw_df["cb_code"] == entry.cb_code]
                if len(rows) > 0:
                    last_row = rows.iloc[-1]
                    cb_data.append({
                        "cb_code": entry.cb_code,
                        "display_name": entry.display_name,
                        "currency": entry.currency,
                        "market_code": entry.market_code,
                        "rate": f"{last_row['value']:.4f}",
                        "obs_date": str(last_row["ts"].date()) if hasattr(last_row["ts"], "date") else str(last_row["ts"]),
                    })
                else:
                    missing_cbs.append(entry.cb_code)
        else:
            missing_cbs = [e.cb_code for e in bench_entries]

        rows_extracted = len(pipeline._raw_df) if pipeline._raw_df is not None else 0

        report.info("pipeline", f"Loaded {result} rows", details={
            "date": str(target.date()),
            "rows_loaded": result,
            "rows_extracted": rows_extracted,
            "elapsed_secs": round(elapsed, 1),
            "per_cb": cb_data,
            "quota_usage": pipeline._quota_usage,
        })

        if pipeline._extraction_errors:
            report.warning(
                "extraction_errors",
                f"{len(pipeline._extraction_errors)} error(s)",
                details={"errors": pipeline._extraction_errors},
            )

        if missing_cbs:
            report.error(
                "coverage",
                f"{len(missing_cbs)} CB(s) returned zero rows across {args.lookback}-day window",
                details={
                    "missing_cbs": missing_cbs,
                    "window_start": str(start.date()),
                    "window_end": str(target.date()),
                },
            )

        # Holiday detection
        cb_currencies = list({e.currency for e in bench_entries})
        holiday_hits = holiday_hits_for_timestamp(cb_currencies, target)
        if holiday_hits:
            report.info("holidays", f"Holiday hits: {len(holiday_hits)}", details={
                "hits": [{"currency": h.currency, "market_code": h.market_code,
                          "name": h.name} for h in holiday_hits],
            })

        # Send email notification
        if settings.email_enabled and settings.email_to:
            _send_report_email(
                pipeline=pipeline,
                settings=settings,
                report=report,
                target=target,
                result=result,
                cb_data=cb_data,
                missing_cbs=missing_cbs,
                holiday_hits=holiday_hits,
                elapsed_secs=elapsed,
                n_cbs=len(bench_entries),
                rows_extracted=rows_extracted,
            )

        report.finish()
        if settings.run_log_dir:
            log_path = (
                Path(settings.run_log_dir)
                / "rates"
                / "fact_bench_rates"
                / f"rates_bench_citi_live_{target:%Y%m%d}.jsonl"
            )
            report.flush_jsonl(log_path)

        log.info(
            "bench_rates_live_complete",
            date=str(target.date()),
            rows=result,
            elapsed=f"{elapsed:.1f}s",
        )
        return 0

    except TagQuotaExceeded as e:
        log.error(
            "tag_quota_exceeded",
            current_usage=getattr(e, "current_usage", None),
            available=getattr(e, "available", None),
        )
        report.error(
            "tag_quota",
            f"Tag quota exceeded: {e}",
            details={
                "current_usage": getattr(e, "current_usage", None),
                "available": getattr(e, "available", None),
            },
        )
        report.finish()
        if settings.run_log_dir:
            log_path = (
                Path(settings.run_log_dir)
                / "rates"
                / "fact_bench_rates"
                / f"rates_bench_citi_live_{target:%Y%m%d}.jsonl"
            )
            report.flush_jsonl(log_path)
        return 1
    except Exception:
        log.exception("bench_rates_live_failed")
        report.error("pipeline", "Daily bench rates ingest failed")
        report.finish()
        return 1
    finally:
        connector.dispose()


def _send_report_email(
    pipeline: BenchRatesPipeline,
    settings: object,
    report: RunReport,
    target: datetime,
    result: int,
    cb_data: list[dict],
    missing_cbs: list[str],
    holiday_hits: list,
    elapsed_secs: float,
    n_cbs: int,
    rows_extracted: int,
) -> None:
    """Build and send the bench rates ingest email."""
    formatter = RatesBenchIngestFormatter()
    has_errors = report.has_errors

    subject = formatter.format_subject(
        pipeline_name="rates.bench_rates_citi_live",
        run_date=target,
        rows_loaded=result,
        n_cbs=n_cbs,
        has_errors=has_errors,
    )
    body = formatter.format_body(
        pipeline_name="rates.bench_rates_citi_live",
        run_date=target,
        rows_extracted=rows_extracted,
        rows_loaded=result,
        n_cbs=n_cbs,
        cb_data=cb_data,
        missing_cbs=missing_cbs,
        holiday_hits=[
            {"cb_code": h.currency, "market_code": h.market_code, "name": h.name}
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
