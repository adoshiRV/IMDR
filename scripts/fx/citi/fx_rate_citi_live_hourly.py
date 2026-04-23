"""FX Rate Citi Velocity Hourly Intraday Runner.

Target table: [fx].[fact_fx_rate]  (frequency_id = HOURLY)
Schedule:     Hourly (via scripts.imdr_hourly)
Source:       Citi Velocity Historical Data API, HOURLY frequency

Uses the dedicated hourly Citi OAuth credentials (IMDR_CITI_HOURLY_CLIENT_*)
and a separate tag-quota file so intraday pulls don't eat into the daily
pipelines' shared 95K budget on the primary key. Each OAuth client has its
own Citi-side 100K/24h rolling bucket; the hourly key is shared with the
rates-hourly runner via data/cache/citi_tag_quota_hourly.json so the single
rolling bucket gives a truthful view of remaining budget.

Budget: 19 pairs × (1 spot + 2 × 10 fwd tenors) = 399 tags/call × 24 runs
= ~9,576 tags/day (~10% of the hourly OAuth client's 95K budget).

Window strategy: each run pulls the full current-day window (00:00 → 23:59 UTC)
at HOURLY frequency. Citi's API returns empty bodies for narrow sub-hour
windows, and the uq_fx_fact_fx_rate constraint (includes obs_ts post
migration 027) makes the MERGE upsert idempotent — re-fetching earlier
hours is a no-op on already-loaded rows and catches any late-arriving
datapoints.

Covers the full FXUniverse.fx_rate_pairs() — 19 pairs across G10, EM
deliverable, and EM Asia NDF (tags use USD.{NDF} direction per the
citi_velocity_fx catalog).

Sanitation / quality gates (in order):
  1. Pre-flight: IMDR_CITI_HOURLY_CLIENT_* must be non-empty.
  2. FX-open gate: FXUniverse.is_fx_open(window.start) skips Sat all-day
     and Fri 22:00 UTC → Sun 22:00 UTC weekend gap.
  3. Pre-extract tag-quota budget check (extractor-level).
  4. Pre-insert Pydantic validation via FXRateCreate.
  5. Post-load quality checks (PositiveValueCheck, PercentageChangeCheck,
     RobustStatisticalOutlierCheck) run automatically and surface in the
     email body via FXRateIngestFormatter's quality_flags section.
  6. Standard health checks (RowCount, Null, Duplicate, Freshness) run via
     BasePipeline.run() and appear in the email body.

Usage:
    python -m scripts.fx.citi.fx_rate_citi_live_hourly
    python -m scripts.fx.citi.fx_rate_citi_live_hourly --date 2026-04-23
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
from imdr.market_calendar.holidays import holiday_hits_for_timestamp
from imdr.notifications.email import send_outlook_email
from imdr.notifications.formatters.fx_rate_ingest import FXRateIngestFormatter
from imdr.reporting.run_report import RunReport
from imdr.universe.fx import get_fx_universe
from imdr.utils.logging import configure_logging

log = structlog.get_logger(__name__)

PIPELINE_NAME = "fx.citi_rate_live_hourly"

# Separate quota file from the daily pipeline — different OAuth client =
# different Citi-side rolling 24h bucket. Shared with rates-hourly since
# both use the same hourly OAuth client.
HOURLY_QUOTA_FILE = "data/cache/citi_tag_quota_hourly.json"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="FX Rate Citi Velocity Hourly Intraday Ingest")
    p.add_argument(
        "--date",
        default=None,
        help="Override date (YYYY-MM-DD, UTC). Default: today UTC.",
    )
    p.add_argument(
        "--pairs",
        default=None,
        help="Comma-separated pairs (e.g. EUR/USD,USD/HKD). Default: all from universe.",
    )
    return p.parse_args()


def _target_window(date_arg: str | None) -> tuple[datetime, datetime]:
    """Full-day UTC window for the target date (defaults to today UTC).

    Citi returns empty responses for narrow sub-hour windows, so we always
    pull the whole day at HOURLY frequency and rely on MERGE idempotency.
    """
    if date_arg:
        day = datetime.strptime(date_arg, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    else:
        day = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    start = day
    end = day.replace(hour=23, minute=59)
    return start, end


def main() -> int:
    args = parse_args()
    settings = get_settings()
    configure_logging(settings)

    if not settings.citi_hourly_client_id or not settings.citi_hourly_client_secret:
        log.error("hourly_creds_missing",
                  msg="IMDR_CITI_HOURLY_CLIENT_ID/SECRET not set in .env")
        return 2

    start, end = _target_window(args.date)
    universe = get_fx_universe()

    # FX-aware weekend gate — FX market closes Fri 22:00 UTC through Sun 22:00 UTC.
    # Catches Sun 22:00+ UTC Asia opens correctly.
    if not universe.is_fx_open(start):
        log.info("fx_market_closed",
                 date=start.date().isoformat(),
                 weekday=start.strftime("%A"))
        return 0

    # Pairs override
    pairs: list[tuple[str, str]] | None = None
    if args.pairs:
        pairs = [tuple(p.strip().split("/")) for p in args.pairs.split(",")]  # type: ignore[misc]
    all_pairs = pairs or universe.fx_rate_pairs()

    log.info(
        "fx_rate_citi_hourly_start",
        start=start.isoformat(),
        end=end.isoformat(),
        n_pairs=len(all_pairs),
    )

    report = RunReport(pipeline_name=PIPELINE_NAME)
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
            frequency="HOURLY",
            client_id=settings.citi_hourly_client_id,
            client_secret=settings.citi_hourly_client_secret,
            quota_tracker_path=HOURLY_QUOTA_FILE,
        )
        rows = pipeline.run()
        elapsed = time.perf_counter() - t0

        # Per-pair breakdown
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

        report.info("pipeline", f"Loaded {rows} rows", details={
            "date": str(start.date()),
            "n_pairs": len(all_pairs),
            "rows_loaded": rows,
            "elapsed_secs": round(elapsed, 1),
            "quota_usage": pipeline._quota_usage,
        })

        if pipeline._extraction_errors:
            report.warning(
                "extraction_errors",
                f"{len(pipeline._extraction_errors)} pair(s) failed during extraction",
                details={"errors": pipeline._extraction_errors},
            )

        # Unlike the daily runner, hourly treats zero-row pairs as informational
        # — early-morning UTC runs routinely have partial coverage.
        if missing_pairs_list:
            report.info(
                "coverage",
                f"{len(missing_pairs_list)} pair(s) with no data this hour",
                details={"missing_pairs": missing_pairs_list},
            )

        rate_ccys = list({ccy for pair in all_pairs for ccy in pair})
        holiday_hits = holiday_hits_for_timestamp(rate_ccys, start)
        if holiday_hits:
            report.info("holidays", f"Holiday hits: {len(holiday_hits)}", details={
                "hits": [
                    {"currency": h.currency, "market_code": h.market_code, "name": h.name}
                    for h in holiday_hits
                ],
            })

        if settings.email_enabled and settings.email_to:
            _send_report_email(
                pipeline=pipeline,
                settings=settings,
                report=report,
                target=start,
                result=rows,
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
                Path(settings.run_log_dir)
                / "fx"
                / "fact_fx_rate"
                / f"fx_rate_citi_live_hourly_{start:%Y%m%d_%H%M}.jsonl"
            )
            report.flush_jsonl(log_path)

        log.info(
            "fx_rate_citi_hourly_complete",
            rows=rows,
            extraction_errors=len(pipeline._extraction_errors),
            quota_used=pipeline._quota_usage,
            elapsed=f"{elapsed:.1f}s",
        )
        return 0

    except TagQuotaExceeded as e:
        log.error(
            "fx_rate_citi_hourly_tag_quota_exceeded",
            current_usage=getattr(e, "current_usage", None),
            available=getattr(e, "available", None),
        )
        report.error("tag_quota", f"Tag quota exceeded: {e}",
                     details={"current_usage": getattr(e, "current_usage", None),
                              "available": getattr(e, "available", None)})
        report.finish()
        if settings.run_log_dir:
            log_path = (
                Path(settings.run_log_dir)
                / "fx"
                / "fact_fx_rate"
                / f"fx_rate_citi_live_hourly_{start:%Y%m%d_%H%M}.jsonl"
            )
            report.flush_jsonl(log_path)
        return 1
    except Exception:
        log.exception("fx_rate_citi_hourly_failed")
        report.error("pipeline", "Hourly FX rate ingest failed")
        report.finish()
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
    """Build and send the hourly FX rate ingest report email."""
    formatter = FXRateIngestFormatter()
    has_errors = report.has_errors
    subject = formatter.format_subject(
        pipeline_name=PIPELINE_NAME,
        run_date=target,
        rows_loaded=result,
        n_pairs=n_pairs,
        has_errors=has_errors,
        mode="Hourly",
    )
    body = formatter.format_body(
        pipeline_name=PIPELINE_NAME,
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
        mode="Hourly",
    )
    send_outlook_email(
        to=settings.email_to,  # type: ignore[attr-defined]
        subject=subject,
        html_body=body,
        importance=2 if has_errors else 1,
    )


if __name__ == "__main__":
    sys.exit(main())
