"""Tenor Basis Swaps — Citi Velocity Daily EOD Runner.

Target table: [rates].[fact_observation]  (quote='basis')
Schedule: Daily (via imdr_daily.py)
Source: Citi Velocity RATES.BASIS_SWAPS.3S6S_BASIS.{EUR,AUD}.SPOT.*

Only active basis-swap curves (EUR + AUD) are pulled here. USD/GBP are
``status: ceased`` (catalog ends 2025-02 post-LIBOR) and are excluded by
the ``select_curves`` filter applied here.

Usage:
    python -m scripts.rates.citi.rates_basis_swaps_citi_live
    python -m scripts.rates.citi.rates_basis_swaps_citi_live --date 2026-06-02
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
from imdr.domains.rates.pipeline import RatesHistoricalPipeline
from imdr.market_calendar.calendar import last_business_day, last_trading_day
from imdr.market_calendar.countries import default_calendar
from imdr.market_calendar.holidays import holiday_hits_for_timestamp
from imdr.notifications.email import send_outlook_email
from imdr.notifications.formatters.rates_ingest import RatesIngestFormatter
from imdr.reporting.run_report import RunReport
from imdr.universe.rates import get_rates_universe
from imdr.utils.logging import configure_logging

log = structlog.get_logger(__name__)

LOOKBACK_DAYS = 5


def _basis_swap_curves(universe) -> list:
    """Active curves wired under the basis_swaps instrument."""
    return [
        c for c in universe.all_curves()
        if c.providers.get("citi", {}).get("instrument") == "basis_swaps"
        and c.status != "ceased"
    ]


def _start_of_window(target: datetime, n_trading_days: int, market: str = "US") -> datetime:
    d = target.date()
    cal = default_calendar(market)
    for _ in range(n_trading_days):
        d = last_trading_day(market, cal, before=d)
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Tenor Basis Swaps Daily EOD Ingest")
    p.add_argument("--date", type=str, default=None, help="Override date (YYYY-MM-DD)")
    p.add_argument("--lookback", type=int, default=LOOKBACK_DAYS,
                   help="Trading days to look back (default: 5)")
    return p.parse_args()


def _send_email(settings, universe, pipeline, target: datetime, cohort,
                rows_loaded: int, rows_extracted: int, has_errors: bool,
                elapsed: float, missing: list[str], holiday_hits: list) -> None:
    pipeline_name = "rates.basis_swaps_citi_live"

    loaded_keys: set[tuple[str, str]] = set()
    if pipeline._raw_df is not None and not pipeline._raw_df.empty:
        loaded_keys = set(zip(pipeline._raw_df["ccy"], pipeline._raw_df["curve"]))

    curve_data: list[dict] = []
    for c in cohort:
        rows = 0
        if loaded_keys and (c.ccy, c.curve) in loaded_keys:
            rows = len(pipeline._raw_df[
                (pipeline._raw_df["ccy"] == c.ccy)
                & (pipeline._raw_df["curve"] == c.curve)
            ])
        curve_data.append({
            "ccy": c.ccy,
            "curve": c.curve,
            "classification": universe.classification_for(c.ccy),
            "status": c.status,
            "tenors": len(universe.maturities_for_curve(c.ccy, c.curve)),
            "rows": rows,
        })

    missing_curves = [
        {"ccy": m.split(".", 1)[0], "curve": m.split(".", 1)[1], "reason": "No data returned"}
        for m in missing
    ]

    formatter = RatesIngestFormatter()
    subject = formatter.format_subject(
        pipeline_name=pipeline_name,
        run_date=target,
        rows_loaded=rows_loaded,
        has_errors=has_errors,
        mode="Basis Daily",
    )
    body = formatter.format_body(
        pipeline_name=pipeline_name,
        run_date=target,
        quotes=["basis"],
        frequency="DAILY",
        rows_extracted=rows_extracted,
        rows_loaded=rows_loaded,
        n_curves=len(cohort),
        curves=curve_data,
        missing_curves=missing_curves,
        holiday_hits=[
            {"currency": h.currency, "country_code": h.country_code, "name": h.name}
            for h in holiday_hits
        ],
        freshness=pipeline._metadata_freshness,
        has_errors=has_errors,
        elapsed_secs=elapsed,
        mode="Basis Daily",
    )
    send_outlook_email(
        to=settings.email_to,
        subject=subject,
        html_body=body,
        importance=2 if has_errors else 1,
    )


def main() -> int:
    args = parse_args()
    settings = get_settings()
    configure_logging(settings)
    universe = get_rates_universe()
    report = RunReport(pipeline_name="rates.basis_swaps_citi_live")

    cohort = _basis_swap_curves(universe)
    if not cohort:
        log.warning("basis_swaps_live_no_active_curves")
        return 0
    curve_keys: list[tuple[str, str]] = [(c.ccy, c.curve) for c in cohort]

    if args.date:
        target = datetime.strptime(args.date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    else:
        target = last_business_day("US", "GT")

    start = _start_of_window(target, args.lookback)
    end = target.replace(hour=23, minute=59)

    log.info("basis_swaps_live_start", date=str(target.date()),
             window_start=str(start.date()), lookback=args.lookback,
             n_curves=len(cohort))

    connector = MSSQLConnector(settings)
    try:
        t0 = time.perf_counter()
        pipeline = RatesHistoricalPipeline(
            connector=connector,
            settings=settings,
            universe=universe,
            start=start,
            end=end,
            quotes=["basis"],
            frequency="DAILY",
            curves=curve_keys,
            use_cache=False,
            chunk_size=settings.bulk_batch_size,
        )
        rows_loaded = pipeline.run()
        elapsed = time.perf_counter() - t0

        rows_extracted = (
            len(pipeline._raw_df) if pipeline._raw_df is not None else 0
        )

        # Coverage check
        missing: list[str] = []
        if pipeline._raw_df is not None and not pipeline._raw_df.empty:
            loaded = set(zip(pipeline._raw_df["ccy"], pipeline._raw_df["curve"]))
            for c in cohort:
                if (c.ccy, c.curve) not in loaded:
                    missing.append(f"{c.ccy}.{c.curve}")
        else:
            missing = [f"{c.ccy}.{c.curve}" for c in cohort]

        report.info("pipeline", f"Loaded {rows_loaded} rows", details={
            "date": str(target.date()),
            "rows_loaded": rows_loaded,
            "rows_extracted": rows_extracted,
            "elapsed_secs": round(elapsed, 1),
            "quota_usage": pipeline._quota_usage,
        })
        if pipeline._extraction_errors:
            report.warning(
                "extraction_errors",
                f"{len(pipeline._extraction_errors)} curve(s) failed",
                details={"errors": pipeline._extraction_errors},
            )
        if missing:
            report.error(
                "coverage",
                f"{len(missing)} curve(s) returned zero rows across {args.lookback}-day window",
                details={"missing": missing,
                         "window_start": str(start.date()),
                         "window_end": str(target.date())},
            )

        cohort_ccys = sorted({c.ccy for c in cohort})
        holiday_hits = holiday_hits_for_timestamp(cohort_ccys, target)
        if holiday_hits:
            report.info("holidays", f"Holiday hits: {len(holiday_hits)}", details={
                "hits": [{"currency": h.currency, "country_code": h.country_code, "name": h.name}
                         for h in holiday_hits],
            })

        if settings.email_enabled and settings.email_to:
            _send_email(
                settings, universe, pipeline, target, cohort, rows_loaded,
                rows_extracted, report.has_errors, elapsed, missing, holiday_hits,
            )

        report.finish()
        if settings.run_log_dir:
            log_path = (
                Path(settings.run_log_dir) / "rates" / "fact_observation"
                / f"rates_basis_swaps_citi_live_{target:%Y%m%d}.jsonl"
            )
            report.flush_jsonl(log_path)

        log.info("basis_swaps_live_complete", date=str(target.date()),
                 rows=rows_loaded, elapsed=f"{elapsed:.1f}s")
        return 0

    except TagQuotaExceeded as e:
        log.error("tag_quota_exceeded",
                  current_usage=getattr(e, "current_usage", None),
                  available=getattr(e, "available", None))
        report.error("tag_quota", f"Tag quota exceeded: {e}")
        report.finish()
        return 1
    except Exception:
        log.exception("basis_swaps_live_failed")
        report.error("pipeline", "Daily basis-swaps ingest failed")
        report.finish()
        return 1
    finally:
        connector.dispose()


if __name__ == "__main__":
    sys.exit(main())
