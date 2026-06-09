"""Rates Citi Velocity Daily EOD Runner.

Target table: [rates].[fact_observation]
Schedule: Daily (via Windows Task Scheduler or cron) — fired multiple times
          per day so each region's curves land shortly after they settle.
          A single ``--region auto`` invocation maps the current UTC hour
          to ASIA / EUROPE / AMERICAS via ``run_cohorts.UTC_FIRE_WINDOWS``.
Source: Citi Velocity Historical Data API (OAuth2)

Usage:
    python -m scripts.rates.citi.rates_citi_live                    # auto-route by UTC
    python -m scripts.rates.citi.rates_citi_live --region asia
    python -m scripts.rates.citi.rates_citi_live --region all       # legacy: pull every active curve
    python -m scripts.rates.citi.rates_citi_live --date 2026-03-07
    python -m scripts.rates.citi.rates_citi_live --quotes par,spread,fwd
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import structlog

from imdr.config.pipeline_config import get_pipeline_config
from imdr.config.settings import get_settings
from imdr.connectors.citi_helpers import TagQuotaExceeded
from imdr.connectors.mssql import MSSQLConnector
from imdr.domains.rates.pipeline import RatesHistoricalPipeline
from imdr.domains.rates.run_cohorts import (
    VALID_REGIONS,
    default_run_label,
    is_static_quote_fire,
    resolve_region_auto,
    select_curves,
    target_for_region,
)
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

# Path used by the hourly OAuth bucket — matches rates_citi_live_hourly.py
# and fx_rate_citi_live_hourly.py so a single rolling-24h quota view stays
# truthful when --use-hourly-creds is passed.
HOURLY_QUOTA_FILE = "data/cache/citi_tag_quota_hourly.json"


def _start_of_window(target: datetime, n_trading_days: int, market: str = "US") -> datetime:
    """Walk back `n_trading_days` trading days from target (exclusive of target)."""
    d = target.date()
    cal = default_calendar(market)
    for _ in range(n_trading_days):
        d = last_trading_day(market, cal, before=d)
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rates Citi Velocity Daily EOD Ingest")
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Override date to process (YYYY-MM-DD). Default: region's last business day.",
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
        help="Disable empty combo cache (retry all API calls). Region runs "
             "(asia/europe/americas/auto) imply --no-cache by design — "
             "we always retry curves that didn't show up. Only use this "
             "flag explicitly with --region all.",
    )
    parser.add_argument(
        "--lookback", type=int, default=LOOKBACK_DAYS,
        help="Trading days to look back (default: 5) — absorbs vendor publish lag",
    )
    parser.add_argument(
        "--region",
        type=str,
        default="auto",
        choices=sorted(VALID_REGIONS) + ["auto"],
        help="Curve cohort. 'auto' (default) resolves the current UTC hour "
             "to asia/europe/americas via run_cohorts.UTC_FIRE_WINDOWS; "
             "outside any window the run is a no-op. 'all' pulls every "
             "active curve (legacy single-run behavior, useful for backfills).",
    )
    parser.add_argument(
        "--run-label",
        type=str,
        default=None,
        help="Override the run label (default derived from region). Used in "
             "RunReport name, email subject prefix, and JSONL log filename.",
    )
    parser.add_argument(
        "--use-hourly-creds",
        action="store_true",
        help="Route this run through IMDR_CITI_HOURLY_CLIENT_* (separate "
             "OAuth client, separate Citi-side 95K/24h bucket and tag-quota "
             "file). Useful for ad-hoc backfills when the primary daily "
             "bucket is exhausted by rates_vol/fx_vol bursts.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = get_settings()
    configure_logging(settings)

    # Resolve region. 'auto' → UTC-based; out-of-window → no-op exit.
    if args.region == "auto":
        region = resolve_region_auto()
        if region is None:
            log.info(
                "rates_citi_live_auto_skip",
                reason="current UTC hour outside any region fire window",
                utc_hour=datetime.now(timezone.utc).hour,
            )
            return 0
    else:
        region = args.region

    run_label = args.run_label or (
        default_run_label(region) if region != "all" else "FULL"
    )
    pipeline_label = f"rates.citi_live[{run_label}]"

    universe = get_rates_universe()
    report = RunReport(pipeline_name=pipeline_label)

    # Determine target date — region-anchored last_business_day
    if args.date:
        target = datetime.strptime(args.date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    elif region == "all":
        target = last_business_day("US", "GT")
    else:
        target = target_for_region(region)

    start = _start_of_window(target, args.lookback)
    end = target.replace(hour=23, minute=59)

    # Resolve quotes: CLI override > pipelines.yml config > fallback "par".
    # Under --region auto, the default config is split into a "live" set
    # (par/spread/fwd — moves intraday) pulled on every fire, and a
    # "static" set (bfly/ssw/rc — derived/EOD-stable) pulled only on the
    # last fire of each region's window. Cuts ~5 redundant tag-calls/day
    # on the static quote types without losing any data — they don't
    # change between fires within the same region's window.
    LIVE_QUOTES = {"par", "spread", "fwd"}
    if args.quotes is not None:
        quotes = [q.strip() for q in args.quotes.split(",")]
    else:
        pipeline_config = get_pipeline_config("rates.historical")
        all_quotes = pipeline_config.default_quotes or ["par"]
        if args.region == "auto" and region != "all":
            if is_static_quote_fire(region):
                quotes = list(all_quotes)
            else:
                quotes = [q for q in all_quotes if q in LIVE_QUOTES]
        else:
            quotes = list(all_quotes)

    # Filter curves into the region cohort (active-only; ceased excluded).
    cohort = select_curves(universe.all_curves(), region)
    cohort_keys: list[tuple[str, str]] = [(c.ccy, c.curve) for c in cohort]

    if not cohort_keys:
        log.warning("rates_citi_live_empty_cohort", region=region, run_label=run_label)
        return 0

    # Region runs always retry missing curves — only 'all' may use the
    # empty-combo cache (and even then only when the user opts in).
    use_cache = (region == "all") and (not args.no_cache)

    log.info(
        "rates_citi_live_start",
        date=str(target.date()),
        quotes=quotes,
        frequency=args.frequency,
        region=region,
        run_label=run_label,
        n_curves=len(cohort_keys),
        use_cache=use_cache,
    )

    pipeline_kwargs: dict = {}
    if args.use_hourly_creds:
        if not settings.citi_hourly_client_id or not settings.citi_hourly_client_secret:
            log.error("hourly_creds_missing",
                      msg="IMDR_CITI_HOURLY_CLIENT_ID/SECRET not set in .env")
            return 2
        pipeline_kwargs["client_id"] = settings.citi_hourly_client_id
        pipeline_kwargs["client_secret"] = settings.citi_hourly_client_secret
        pipeline_kwargs["quota_tracker_path"] = HOURLY_QUOTA_FILE
        log.info("rates_citi_live_hourly_creds", quota_file=HOURLY_QUOTA_FILE)

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
            curves=cohort_keys if region != "all" else None,
            use_cache=use_cache,
            chunk_size=settings.bulk_batch_size,
            **pipeline_kwargs,
        )
        result = pipeline.run()
        elapsed = time.perf_counter() - t0

        report.info("pipeline", f"Loaded {result} rows", details={
            "date": str(target.date()),
            "quotes": quotes,
            "rows_loaded": result,
            "elapsed_secs": round(elapsed, 1),
            "quota_usage": pipeline._quota_usage,
        })

        # Surface extraction errors (non-quota API failures)
        if pipeline._extraction_errors:
            report.warning(
                "extraction_errors",
                f"{len(pipeline._extraction_errors)} curve(s) failed during extraction",
                details={"errors": pipeline._extraction_errors},
            )

        # Coverage check: which curves in the cohort got zero rows across the whole window?
        cohort_set = set(cohort_keys)
        missing_curves: list[str] = []
        if pipeline._raw_df is not None and not pipeline._raw_df.empty:
            loaded_keys = set(zip(pipeline._raw_df["ccy"], pipeline._raw_df["curve"]))
            for c in cohort:
                if (c.ccy, c.curve) not in loaded_keys:
                    missing_curves.append(f"{c.ccy}.{c.curve}")
        else:
            missing_curves = [f"{c.ccy}.{c.curve}" for c in cohort]

        if missing_curves:
            report.error(
                "coverage",
                f"{len(missing_curves)} active curve(s) returned zero rows across {args.lookback}-day window",
                details={
                    "missing_curves": missing_curves,
                    "window_start": str(start.date()),
                    "window_end": str(target.date()),
                },
            )

        # Holiday check for all rates currencies
        rates_ccys = universe.target_currencies()
        holiday_hits = holiday_hits_for_timestamp(rates_ccys, target)
        if holiday_hits:
            report.info("holidays", f"Holiday hits: {len(holiday_hits)}", details={
                "hits": [{"currency": h.currency, "country_code": h.country_code, "name": h.name}
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
                cohort=cohort,
                run_label=run_label,
            )

        report.finish()

        # Flush RunReport to JSONL — filename includes run_label so staggered
        # runs on the same day each get their own log artifact.
        if settings.run_log_dir:
            log_path = (
                Path(settings.run_log_dir)
                / "rates"
                / "fact_observation"
                / f"rates_citi_live_{run_label}_{target:%Y%m%d}.jsonl"
            )
            report.flush_jsonl(log_path)

        log.info("rates_citi_live_complete",
                 date=str(target.date()),
                 region=region,
                 run_label=run_label,
                 rows=result,
                 elapsed=f"{elapsed:.1f}s")
        return 0

    except TagQuotaExceeded as e:
        log.error("rates_citi_live_tag_quota_exceeded",
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
                / "fact_observation"
                / f"rates_citi_live_{run_label}_{target:%Y%m%d}.jsonl"
            )
            report.flush_jsonl(log_path)

        return 1
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
    cohort: list,
    run_label: str,
) -> None:
    """Build and send the rates ingest report email scoped to ``cohort``."""
    # Scope email to the curves this run actually requested. Surfacing
    # out-of-cohort curves as "missing" would be noise.
    curve_data = []
    for c in cohort:
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
        pipeline_name=f"rates.citi_live[{run_label}]",
        run_date=target,
        rows_loaded=rows_loaded,
        has_errors=has_errors,
    )
    body = formatter.format_body(
        pipeline_name=f"rates.citi_live[{run_label}]",
        run_date=target,
        quotes=quotes,
        frequency=frequency,
        rows_extracted=rows_extracted,
        rows_loaded=rows_loaded,
        n_curves=len(cohort),
        curves=curve_data,
        missing_curves=missing,
        holiday_hits=[
            {"currency": h.currency, "country_code": h.country_code, "name": h.name}
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
