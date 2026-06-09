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
  2. FX-open gate: FXUniverse.is_fx_open(now) skips runs while the FX
     market is closed (Fri 22:00 UTC → Sun 22:00 UTC weekend gap).
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
from datetime import datetime, timedelta, timezone
from pathlib import Path

import structlog

from imdr.config.settings import get_settings
from imdr.connectors.citi_helpers import TagQuotaExceeded, summarize_tag_errors
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
    """Pull window for the run.

    Default (no --date): yesterday 00:00 UTC → now (current UTC moment).
    Spanning the UTC day boundary catches the prior day's late hours
    (22:00 + 23:00) that wouldn't otherwise be fetched — each scheduled
    fire only sees Citi data up to "now", so the last fire of day N
    (~21:00 UTC) misses 22:00/23:00, and day N+1's narrower windows
    would skip them permanently. End is `now`, not today 23:59 UTC, so
    we ask Citi for everything up to the current moment instead of a
    future timestamp — needed to surface the freshest hourly bar each
    fire on a truly live cadence.

    With --date: that single calendar day's 00:00 → 23:59 UTC window —
    used for explicit backfills.

    Citi returns empty responses for narrow sub-hour windows, so we
    always pull a full multi-hour span and rely on MERGE idempotency.
    """
    if date_arg:
        day = datetime.strptime(date_arg, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        return day, day.replace(hour=23, minute=59)

    now = datetime.now(timezone.utc)
    yesterday = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
    return yesterday, now


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
    # Gate on "now", not window.start: the 48h pull window's left edge is
    # always yesterday 00:00 UTC (often inside the closed weekend zone),
    # but the window itself spans into live hours. Checking now correctly
    # lets Mon SGT runs (Sun ~22:00 UTC onward) through.
    now_utc = datetime.now(timezone.utc)
    if not universe.is_fx_open(now_utc):
        log.info("fx_market_closed",
                 now=now_utc.isoformat(),
                 weekday=now_utc.strftime("%A"))
        return 0

    # Pairs override
    pairs: list[tuple[str, str]] | None = None
    if args.pairs:
        pairs = [tuple(p.strip().split("/")) for p in args.pairs.split(",")]  # type: ignore[misc]
    bbg_only = universe.fx_rate_bbg_only_pairs()
    all_pairs = pairs or [p for p in universe.fx_rate_pairs() if p not in bbg_only]

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

        # Surface anything Citi told us at the per-tag level: ERROR responses
        # (e.g. per-tag 10/24h cap, unsupported frequency) and EMPTY payloads
        # that the extractor would otherwise drop silently.
        api_messages = summarize_tag_errors(pipeline._tag_errors)
        n_errors = sum(m["count"] for m in api_messages if m["type"] in ("ERROR", "RESPONSE", "MALFORMED"))
        if n_errors > 0:
            report.error(
                "citi_api",
                f"Citi returned {n_errors} per-tag error(s); see CITI API MESSAGES in body",
                details={"summary": api_messages[:10]},
            )
        elif rows == 0 and api_messages:
            # All-EMPTY response across the request — likely the per-tag
            # 10/24h rolling bucket is exhausted. Promote to ERROR so the
            # subject prefix flips and the run is visible.
            report.error(
                "citi_api",
                f"Citi returned 0 rows with {len(api_messages)} EMPTY tag(s) — "
                "likely per-tag rate limit exhausted",
                details={"summary": api_messages[:10]},
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
                    {"currency": h.currency, "country_code": h.country_code, "name": h.name}
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
                api_messages=api_messages,
                quota_status=None,
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

        # Email the quota failure — previously this branch was silent.
        # `pipeline` is bound (the exception fires inside pipeline.run()),
        # and its _tag_errors list aliases the extractor's, so any per-tag
        # signals collected before the quota tripped are still available.
        if settings.email_enabled and settings.email_to:
            try:
                quota_status = {
                    "current_usage": getattr(e, "current_usage", None),
                    "available": getattr(e, "available", None),
                    "message": str(e),
                }
                api_messages = summarize_tag_errors(getattr(pipeline, "_tag_errors", []))
                _send_report_email(
                    pipeline=pipeline,
                    settings=settings,
                    report=report,
                    target=start,
                    result=0,
                    pair_data=[],
                    missing_pairs=[f"{c1}/{c2}" for c1, c2 in all_pairs],
                    holiday_hits=[],
                    elapsed_secs=0.0,
                    n_pairs=len(all_pairs),
                    rows_extracted=0,
                    api_messages=api_messages,
                    quota_status=quota_status,
                )
            except Exception:
                log.exception("fx_rate_citi_hourly_quota_email_failed")

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
    api_messages: list[dict] | None = None,
    quota_status: dict | None = None,
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
    if quota_status is not None:
        # Make the subject unmistakable when the aggregate quota tripped.
        subject = f"[QUOTA] {subject}"
    body = formatter.format_body(
        pipeline_name=PIPELINE_NAME,
        run_date=target,
        rows_extracted=rows_extracted,
        rows_loaded=result,
        n_pairs=n_pairs,
        pair_data=pair_data,
        missing_pairs=missing_pairs,
        holiday_hits=[
            {"currency": h.currency, "country_code": h.country_code, "name": h.name}
            for h in holiday_hits
        ],
        quality_flags=pipeline._quality_results,
        api_messages=api_messages or [],
        quota_status=quota_status,
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
