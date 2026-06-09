"""FX Rate Citi Velocity Daily EOD Runner.

Target table: [fx].[fact_fx_rate]
Schedule: Daily
Source: Citi Velocity Historical Data API (OAuth2)

Usage:
    python -m scripts.fx.citi.fx_rate_citi_live
    python -m scripts.fx.citi.fx_rate_citi_live --date 2026-04-21
    python -m scripts.fx.citi.fx_rate_citi_live --pairs EUR/USD,USD/HKD
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
from imdr.domains.fx.pipeline_rate import FXRatePipeline
from imdr.market_calendar.calendar import last_business_day, last_trading_day
from imdr.market_calendar.countries import default_calendar
from imdr.market_calendar.holidays import holiday_hits_for_timestamp
from imdr.notifications.email import send_outlook_email
from imdr.notifications.formatters.fx_rate_ingest import FXRateIngestFormatter
from imdr.reporting.run_report import RunReport
from imdr.universe.fx import get_fx_universe
from imdr.utils.logging import configure_logging

log = structlog.get_logger(__name__)

PIPELINE_NAME = "fx.citi_rate_live"
LOOKBACK_DAYS = 5


def _start_of_window(target: datetime, n_trading_days: int, market: str = "US") -> datetime:
    """Walk back `n_trading_days` trading days from target (exclusive of target)."""
    d = target.date()
    cal = default_calendar(market)
    for _ in range(n_trading_days):
        d = last_trading_day(market, cal, before=d)
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="FX Rate Citi Velocity Daily EOD Ingest")
    parser.add_argument(
        "--date", type=str, default=None,
        help="Override date to process (YYYY-MM-DD). Default: last business day (US).",
    )
    parser.add_argument(
        "--pairs", type=str, default=None,
        help="Comma-separated pairs (e.g. EUR/USD,USD/HKD). Default: all from universe.",
    )
    parser.add_argument(
        "--lookback", type=int, default=LOOKBACK_DAYS,
        help="Trading days to look back (default: 5) — absorbs vendor publish lag",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = get_settings()
    configure_logging(settings)

    universe = get_fx_universe()
    report = RunReport(pipeline_name=PIPELINE_NAME)

    # Target date
    if args.date:
        target = datetime.strptime(args.date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    else:
        target = last_business_day("US", "GT")

    start = _start_of_window(target, args.lookback)
    end = target.replace(hour=23, minute=59)

    # Pairs override
    pairs: list[tuple[str, str]] | None = None
    if args.pairs:
        pairs = [tuple(p.strip().split("/")) for p in args.pairs.split(",")]  # type: ignore[misc]

    bbg_only = universe.fx_rate_bbg_only_pairs()
    all_pairs = pairs or [p for p in universe.fx_rate_pairs() if p not in bbg_only]
    log.info("fx_rate_citi_live_start", date=str(target.date()), n_pairs=len(all_pairs))

    connector = MSSQLConnector(settings)
    try:
        t0 = time.perf_counter()
        pipeline = FXRatePipeline(
            connector=connector,
            settings=settings,
            universe=universe,
            start=start,
            end=end,
            pairs=pairs,
            chunk_size=settings.bulk_batch_size,
            frequency="DAILY",
        )
        result = pipeline.run()
        elapsed = time.perf_counter() - t0

        # Per-pair breakdown from raw df
        pair_data: list[dict] = []
        missing_pairs_list: list[str] = []
        if pipeline._raw_df is not None and not pipeline._raw_df.empty:
            loaded_pairs = set(zip(pipeline._raw_df["base_ccy"], pipeline._raw_df["quote_ccy"]))
            for ccy1, ccy2 in all_pairs:
                pair_name = f"{ccy1}/{ccy2}"
                non_usd = ccy1 if ccy1 != "USD" else ccy2
                ccy_class = universe.classification_for(non_usd)
                if (ccy1, ccy2) in loaded_pairs:
                    sub = pipeline._raw_df[
                        (pipeline._raw_df["base_ccy"] == ccy1)
                        & (pipeline._raw_df["quote_ccy"] == ccy2)
                    ]
                    pair_data.append({"pair": pair_name, "n_obs": len(sub), "ccy_class": ccy_class})
                else:
                    pair_data.append({"pair": pair_name, "n_obs": 0, "ccy_class": ccy_class})
                    missing_pairs_list.append(pair_name)
        else:
            for ccy1, ccy2 in all_pairs:
                missing_pairs_list.append(f"{ccy1}/{ccy2}")

        report.info(
            "pipeline", f"Loaded {result} rows",
            details={
                "date": str(target.date()),
                "n_pairs": len(all_pairs),
                "rows_loaded": result,
                "elapsed_secs": round(elapsed, 1),
                "quota_usage": pipeline._quota_usage,
            },
        )

        if pipeline._extraction_errors:
            report.warning(
                "extraction_errors",
                f"{len(pipeline._extraction_errors)} pair(s) failed during extraction",
                details={"errors": pipeline._extraction_errors},
            )

        if missing_pairs_list:
            report.error(
                "coverage",
                f"{len(missing_pairs_list)} pair(s) returned zero rows across {args.lookback}-day window",
                details={
                    "missing_pairs": missing_pairs_list,
                    "window_start": str(start.date()),
                    "window_end": str(target.date()),
                },
            )

        rate_ccys = list({ccy for pair in all_pairs for ccy in pair})
        holiday_hits = holiday_hits_for_timestamp(rate_ccys, target)
        if holiday_hits:
            report.info(
                "holidays", f"Holiday hits: {len(holiday_hits)}",
                details={
                    "hits": [
                        {"currency": h.currency, "country_code": h.country_code, "name": h.name}
                        for h in holiday_hits
                    ]
                },
            )

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
                n_pairs=len(all_pairs),
                rows_extracted=len(pipeline._raw_df) if pipeline._raw_df is not None else 0,
            )

        report.finish()
        if settings.run_log_dir:
            log_path = (
                Path(settings.run_log_dir) / "fx" / "fact_fx_rate"
                / f"fx_rate_citi_live_{target:%Y%m%d}.jsonl"
            )
            report.flush_jsonl(log_path)

        log.info("fx_rate_citi_live_complete", date=str(target.date()), rows=result, elapsed=f"{elapsed:.1f}s")
        return 0

    except TagQuotaExceeded as e:
        log.error(
            "fx_rate_citi_live_tag_quota_exceeded",
            current_usage=getattr(e, "current_usage", None),
            available=getattr(e, "available", None),
        )
        report.error(
            "tag_quota", f"Tag quota exceeded: {e}",
            details={
                "current_usage": getattr(e, "current_usage", None),
                "available": getattr(e, "available", None),
            },
        )
        report.finish()
        if settings.run_log_dir:
            log_path = (
                Path(settings.run_log_dir) / "fx" / "fact_fx_rate"
                / f"fx_rate_citi_live_{target:%Y%m%d}.jsonl"
            )
            report.flush_jsonl(log_path)
        return 1
    except Exception:
        log.exception("fx_rate_citi_live_failed")
        report.error("pipeline", "Daily FX rate ingest failed")
        report.finish()
        if settings.run_log_dir:
            log_path = (
                Path(settings.run_log_dir) / "fx" / "fact_fx_rate"
                / f"fx_rate_citi_live_{target:%Y%m%d}.jsonl"
            )
            report.flush_jsonl(log_path)
        return 1
    finally:
        connector.dispose()


def _send_report_email(
    pipeline: FXRatePipeline,
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
    formatter = FXRateIngestFormatter()
    has_errors = report.has_errors
    subject = formatter.format_subject(
        pipeline_name=PIPELINE_NAME, run_date=target,
        rows_loaded=result, n_pairs=n_pairs, has_errors=has_errors,
    )
    body = formatter.format_body(
        pipeline_name=PIPELINE_NAME, run_date=target,
        rows_extracted=rows_extracted, rows_loaded=result,
        n_pairs=n_pairs, pair_data=pair_data, missing_pairs=missing_pairs,
        holiday_hits=[
            {"currency": h.currency, "country_code": h.country_code, "name": h.name}
            for h in holiday_hits
        ],
        quality_flags=pipeline._quality_results,
        has_errors=has_errors, elapsed_secs=elapsed_secs,
    )
    send_outlook_email(
        to=settings.email_to,  # type: ignore[attr-defined]
        subject=subject, html_body=body,
        importance=2 if has_errors else 1,
    )


if __name__ == "__main__":
    sys.exit(main())
