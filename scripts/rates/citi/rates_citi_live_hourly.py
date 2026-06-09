"""Rates Citi Velocity Hourly Intraday Runner.

Target table: [rates].[fact_observation]  (frequency_id = HOURLY)
Schedule:     Hourly (via scripts.imdr_hourly)
Source:       Citi Velocity Historical Data API, HOURLY frequency

Uses the dedicated hourly Citi OAuth credentials (IMDR_CITI_HOURLY_CLIENT_*)
and a separate tag-quota file so intraday pulls don't eat into the daily
pipelines' shared 95K budget on the primary key. Each OAuth client has its
own Citi-side 100K/24h rolling bucket; G4 RFR par = 176 tags/call × 24
runs/day = ~4,224 tags/day — well under the hourly key's limit.

Window strategy: each run pulls the full current-day window (00:00 → 23:59 UTC)
at HOURLY frequency. Citi's API returns empty bodies for narrow sub-hour
windows, and the uq_rates_fact_obs constraint (includes frequency_id) makes
the MERGE upsert idempotent — re-fetching earlier hours is a no-op on
already-loaded rows and catches any late-arriving datapoints.

Covers 12 active RFR curves + USD FEDFUND + 5 G10 IBORs + JPY TONAR_LCH
+ 11 APAC IBOR/NDIRS curves (30 total):
  RFR G10:    USD SOFR, EUR EUROSTR, GBP SONIA, JPY TONAR, CHF SARON,
              AUD AONIA, CAD CORRA, NZD NZIONA, NOK NOWA, SEK STINA
  RFR APAC:   SGD SORA, THB THOR
  US OIS:     USD FEDFUND (effective fed funds)
  IBOR G10:   AUD BBSW, EUR EURIBOR (reformed), NOK NIBOR, NZD BKBM,
              SEK STIBOR
  CCP OIS:    JPY TONAR_LCH (JSCC excluded — Citi stopped serving HOURLY
              ~2026-05-04; see docs/admin/development/rates_hourly_cohort_drift.md)
  IBOR APAC:  HKD HIBOR (deliverable), CNH CNH_HIBOR (offshore deliverable),
              CNY SHIBOR + CNY NDIRS (NDIRS), IDR JIBOR (NDIRS),
              INR MIFOR (NDIRS, reformed), KRW CD (NDIRS),
              MYR KLIBOR (NDIRS), PHP PHIREF (NDIRS),
              TWD TAIBOR (NDIRS), VND VND_REF (NDIRS)

Two quote types per curve:
  par: full tenor grid (~36-44 tenors per curve)
  fwd: forward-starting rates (28 combos per curve)

Budget: ~30 × (40+28) ≈ 2,040 tags/call × 24 runs ≈ ~49K tags/day
(~52% of the hourly OAuth client's 95K budget).

Note on IBOR/NDIRS hourly publish: APAC IBOR fixings are once-daily marks
(e.g., HIBOR 11:15 HKT, KLIBOR 11:00 MYT). Citi may return EMPTY for sub-fix
hours; the live extractor's per-tag error tracking surfaces this in the
ingest email. Adding them here gives same-day visibility once Citi publishes
the daily mark, rather than waiting for the regional daily fire.

Note on publish cadence: each RFR starts showing hourly datapoints when its
home market opens — Asia first (JPY/SGD/THB/AUD/NZD from ~00:00 UTC),
Europe mid-morning (EUR ~06:00 UTC, GBP ~07:00 UTC BST / ~08:00 GMT),
Americas (USD SOFR / CAD CORRA from ~00:00 UTC via overnight trading).
Early-morning UTC runs return partial coverage; the MERGE upsert (natural
key includes frequency_id) fills in hours as the day progresses. PAR quotes
on active curves are protected from empty-combo caching (see
src/imdr/domains/rates/cache.py:_PROTECTED_QUOTES). ROLL_CARRY (`rc`) is
not served at HOURLY frequency — Citi returns type=ERROR for it.

Known issue (missing-data classifier): ``_classify_missing`` labels gaps with
equity-exchange semantics (`pre_open` / `open` / `post_close`) by querying the
ccy's home country's `trading_hours` in `countries.yml`. Rates products are
OTC and don't follow exchange hours, so most of those labels are misleading.
Only `non_trading` (weekend/holiday) and the ``_OTC_RFR_CCYS`` carve-out are
correct. No data-correctness impact; report prose only. Tracked in
`docs/admin/development/rates_hourly_classify_missing_equity_proxy.md`.

Usage:
    python -m scripts.rates.citi.rates_citi_live_hourly
    python -m scripts.rates.citi.rates_citi_live_hourly --date 2026-04-23
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import structlog

from zoneinfo import ZoneInfo

from imdr.config.settings import get_settings
from imdr.connectors.citi_helpers import TagQuotaExceeded, summarize_tag_errors
from imdr.connectors.mssql import MSSQLConnector
from imdr.domains.rates.pipeline import RatesHistoricalPipeline
from imdr.domains.rates.run_cohorts import (
    VALID_REGIONS,
    default_run_label,
    resolve_region_auto,
    select_curves,
)
from imdr.market_calendar.calendar import is_market_open, is_trading_day
from imdr.market_calendar.holidays import holiday_hits_for_timestamp
from imdr.market_calendar.countries import countries_for_currency, default_calendar, get_country
from imdr.notifications.email import send_outlook_email
from imdr.notifications.formatters.rates_ingest import RatesIngestFormatter
from imdr.reporting.run_report import RunReport
from imdr.universe.rates import get_rates_universe
from imdr.utils.logging import configure_logging

log = structlog.get_logger(__name__)

# 12 active RFR curves + 6 APAC IBOR/NDIRS curves. Full tenor grid + forwards.
DEFAULT_CURVES: list[tuple[str, str]] = [
    # RFR G10
    ("USD", "SOFR"),
    ("EUR", "EUROSTR"),
    ("GBP", "SONIA"),
    ("JPY", "TONAR"),
    ("CHF", "SARON"),
    ("AUD", "AONIA"),
    ("CAD", "CORRA"),
    ("NZD", "NZIONA"),
    ("NOK", "NOWA"),
    ("SEK", "STINA"),
    # RFR APAC
    ("SGD", "SORA"),
    ("THB", "THOR"),
    # US effective fed funds OIS — daily mark but tagged here so the
    # intraday hits Citi the same UTC day publication occurs.
    ("USD", "FEDFUND"),
    # G10 IBORs — still actively quoted alongside RFRs (IBOR-RFR basis).
    # EURIBOR is reformed (not ceased) and continues to publish.
    ("AUD", "BBSW"),
    ("EUR", "EURIBOR"),
    ("NOK", "NIBOR"),
    ("NZD", "BKBM"),
    ("SEK", "STIBOR"),
    # CCP-specific JPY OIS (LCH variant). JSCC variant deliberately
    # omitted — Citi stopped serving it at HOURLY around 2026-05-04;
    # see docs/admin/development/rates_hourly_cohort_drift.md.
    ("JPY", "TONAR_LCH"),
    # APAC IBOR / NDIRS — once-daily fixings, hourly fires catch the mark
    # the same UTC day Citi publishes (vs T+1 via regional daily fires).
    ("HKD", "HIBOR"),
    ("CNH", "CNH_HIBOR"),
    ("CNY", "SHIBOR"),
    ("CNY", "NDIRS"),
    ("IDR", "JIBOR"),
    ("INR", "MIFOR"),
    ("KRW", "CD"),
    ("MYR", "KLIBOR"),
    ("PHP", "PHIREF"),
    ("TWD", "TAIBOR"),
    ("VND", "VND_REF"),
]

DEFAULT_QUOTES = ["par", "fwd"]

# Separate quota file from the daily pipeline — different OAuth client =
# different Citi-side rolling 24h bucket.
HOURLY_QUOTA_FILE = "data/cache/citi_tag_quota_hourly.json"

# Anchor country codes (from src/imdr/market_calendar/countries.yml) checked for
# "all closed" skip — weekends + universal holidays (New Year's, Christmas).
# If all four are non-trading, no meaningful rates data will publish that day.
# Good Friday only closes US/UK/EU (JP still trades), so the run still fires.
_ANCHOR_MARKETS = ["US", "EU", "UK", "JP"]


def _market_status(market_code: str, utc_dt: datetime) -> str:
    """Classify a market's state at `utc_dt` against its configured trading hours.

    Returns one of:
      - "non_trading" — weekend or holiday in that market
      - "pre_open"    — trading day, but local time is before market open
      - "open"        — currently in trading hours
      - "post_close"  — trading day, local time is at/after market close
      - "otc"         — market has no trading_hours (24h / OTC)
    """
    country = get_country(market_code)
    cal = default_calendar(market_code)
    tz = ZoneInfo(country.timezone)
    local_dt = utc_dt.astimezone(tz)

    if not is_trading_day(market_code, cal, local_dt.date()):
        return "non_trading"

    th = country.trading_hours
    if th is None:
        return "otc"

    if is_market_open(market_code, cal, utc_dt):
        return "open"

    from datetime import time as _time
    open_t = _time.fromisoformat(th.open)
    if local_dt.time() < open_t:
        return "pre_open"
    return "post_close"


# Currencies whose RFR publishes from ~00:00 UTC via overnight trading rather
# than on the local equity-market clock (see module docstring). Treated as
# OTC for classification so early-UTC hours don't falsely show "pre_open".
_OTC_RFR_CCYS = {"USD", "CAD"}


def _classify_missing(ccy: str, utc_dt: datetime) -> tuple[str, str]:
    """Return (country_code, status) for the ccy's primary country at utc_dt.

    "Primary" = first country alphabetically from ``countries_for_currency``.
    Every ccy maps to exactly one country in ``countries.yml`` today, so this
    is unambiguous; if a multi-country ccy is introduced later, the alphabetic
    pick is deterministic but not necessarily semantic.

    If the currency isn't mapped to any country, returns ("", "unknown").
    Currencies in `_OTC_RFR_CCYS` are classified using OTC semantics: their
    status is `non_trading` on weekends/holidays and `otc` otherwise.

    ⚠ KNOWN MODELING ERROR: the non-carve-out path (`_market_status`) maps to
    equity-exchange hours, which are the wrong clock for rates. Today only
    `non_trading` and the explicit OTC carve-out are correct. See module
    docstring + `docs/admin/development/rates_hourly_classify_missing_equity_proxy.md`.
    """
    countries = countries_for_currency(ccy)
    if not countries:
        return "", "unknown"
    mkt = countries[0]
    if ccy.upper() in _OTC_RFR_CCYS:
        tz = ZoneInfo(get_country(mkt).timezone)
        local_d = utc_dt.astimezone(tz).date()
        if not is_trading_day(mkt, default_calendar(mkt), local_d):
            return mkt, "non_trading"
        return mkt, "otc"
    return mkt, _market_status(mkt, utc_dt)


# Human-readable reason per market status, used in the email body.
_STATUS_REASON = {
    "non_trading": "Market holiday/weekend",
    "pre_open":    "Market not yet open",
    "open":        "Market open — data pending or gap",
    "post_close":  "Market closed — data missing",
    "otc":         "24h OTC market — data missing",
    "unknown":     "No market mapped",
}

# Statuses treated as "unexpected" gaps (promote to a RunReport warning).
# `non_trading` and `pre_open` are expected empties; `otc` covers USD/CAD
# RFRs that publish 24h and therefore should have data on any trading day.
_UNEXPECTED_STATUSES = {"open", "post_close", "otc"}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Rates Citi Velocity Hourly Intraday Ingest")
    p.add_argument(
        "--date",
        default=None,
        help="Override date (YYYY-MM-DD, UTC). Default: today UTC.",
    )
    p.add_argument(
        "--quotes",
        default=None,
        help="Comma-separated quote types. Default: par.",
    )
    p.add_argument(
        "--use-cache",
        action="store_true",
        help="Enable empty-combo cache (disabled by default for hourly — "
             "2-day stale window is too long for 24-runs-per-day cadence, "
             "and the hourly runner would pollute the shared cache used "
             "by the daily pipeline).",
    )
    p.add_argument(
        "--region",
        default="all",
        choices=sorted(VALID_REGIONS) + ["auto"],
        help="RFR cohort. Default 'all' preserves the script's heritage of "
             "pulling every active hourly RFR each fire — required for full "
             "intraday coverage at imdr_snapshots_citi's 3h cadence. 'auto' "
             "resolves the current UTC hour to asia/europe/americas via "
             "run_cohorts.UTC_FIRE_WINDOWS; outside any window the run is "
             "a no-op. Use auto only if you want regional intraday subsets.",
    )
    p.add_argument(
        "--run-label",
        default=None,
        help="Override the run label (default derived from region). Used in "
             "RunReport name, email subject prefix, and JSONL log filename.",
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

    # Resolve region. 'auto' → UTC-based; out-of-window → no-op exit.
    if args.region == "auto":
        region = resolve_region_auto()
        if region is None:
            log.info(
                "rates_citi_hourly_auto_skip",
                reason="current UTC hour outside any region fire window",
                utc_hour=datetime.now(timezone.utc).hour,
            )
            return 0
    else:
        region = args.region

    run_label = args.run_label or (
        default_run_label(region) if region != "all" else "FULL"
    )

    start, end = _target_window(args.date)

    # Skip if every anchor rates market is non-trading (weekend or holiday).
    # Uses the project's canonical calendar — weekends from dbo.dim_country +
    # holidays from calendar.market_holidays (with Python `holidays` lib fallback).
    # Gate on today's UTC date, not start.date(): the 48h pull window's
    # left edge is yesterday UTC, which on Sun/Mon falls in the weekend
    # and would falsely skip the live trading day at the right edge.
    now_utc = datetime.now(timezone.utc)
    day = now_utc.date()
    closed = [m for m in _ANCHOR_MARKETS if not is_trading_day(m, default_calendar(m), day)]
    if len(closed) == len(_ANCHOR_MARKETS):
        log.info("all_anchor_markets_closed_skip",
                 date=day.isoformat(),
                 weekday=now_utc.strftime("%A"),
                 closed_markets=closed)
        return 0

    if args.quotes is not None:
        quotes = [q.strip() for q in args.quotes.split(",")]
    else:
        quotes = DEFAULT_QUOTES

    universe = get_rates_universe()

    # Resolve curve cohort: take the curated DEFAULT_CURVES (already
    # restricted to RFRs that tick intraday — excludes FEDFUND/JSCC/LCH
    # which are once-daily marks), look them up in the universe, then
    # apply the region filter.
    candidate_entries = [universe.get_curve(ccy, curve) for ccy, curve in DEFAULT_CURVES]
    cohort = select_curves(candidate_entries, region)
    cohort_keys: list[tuple[str, str]] = [(c.ccy, c.curve) for c in cohort]

    if not cohort_keys:
        log.info(
            "rates_citi_hourly_empty_cohort",
            region=region,
            run_label=run_label,
            reason="no curves match region from DEFAULT_CURVES",
        )
        return 0

    log.info(
        "rates_citi_hourly_start",
        start=start.isoformat(),
        end=end.isoformat(),
        curves=len(cohort_keys),
        quotes=quotes,
        region=region,
        run_label=run_label,
    )

    report = RunReport(pipeline_name=f"rates.citi_live_hourly[{run_label}]")
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
            frequency="HOURLY",
            curves=cohort_keys,
            use_cache=args.use_cache,
            chunk_size=settings.bulk_batch_size,
            client_id=settings.citi_hourly_client_id,
            client_secret=settings.citi_hourly_client_secret,
            quota_tracker_path=HOURLY_QUOTA_FILE,
        )
        rows = pipeline.run()
        elapsed = time.perf_counter() - t0

        report.info("pipeline", f"Loaded {rows} rows", details={
            "date": str(start.date()),
            "quotes": quotes,
            "rows_loaded": rows,
            "elapsed_secs": round(elapsed, 1),
            "quota_usage": pipeline._quota_usage,
        })

        if pipeline._extraction_errors:
            report.warning(
                "extraction_errors",
                f"{len(pipeline._extraction_errors)} curve(s) failed during extraction",
                details={"errors": pipeline._extraction_errors},
            )

        # Surface anything Citi told us at the per-tag level: ERROR responses
        # (e.g. per-tag 10/24h cap, unsupported frequency for ROLL_CARRY) and
        # EMPTY payloads that the extractor would otherwise drop silently.
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
            # 10/24h rolling bucket is exhausted on the hourly OAuth client.
            report.error(
                "citi_api",
                f"Citi returned 0 rows with {len(api_messages)} EMPTY tag(s) — "
                "likely per-tag rate limit exhausted",
                details={"summary": api_messages[:10]},
            )

        hourly_ccys = sorted({ccy for ccy, _ in cohort_keys})
        holiday_hits = holiday_hits_for_timestamp(hourly_ccys, start)
        if holiday_hits:
            report.info("holidays", f"Holiday hits: {len(holiday_hits)}", details={
                "hits": [{"currency": h.currency, "country_code": h.country_code, "name": h.name}
                         for h in holiday_hits],
            })

        if settings.email_enabled and settings.email_to:
            _send_report_email(
                pipeline=pipeline,
                settings=settings,
                universe=universe,
                report=report,
                target=start,
                quotes=quotes,
                rows_loaded=rows,
                rows_extracted=len(pipeline._raw_df) if pipeline._raw_df is not None else 0,
                holiday_hits=holiday_hits,
                elapsed_secs=elapsed,
                api_messages=api_messages,
                quota_status=None,
                cohort_keys=cohort_keys,
                run_label=run_label,
            )

        report.finish()

        if settings.run_log_dir:
            log_path = (
                Path(settings.run_log_dir)
                / "rates"
                / "fact_observation"
                / f"rates_citi_live_hourly_{run_label}_{start:%Y%m%d_%H%M}.jsonl"
            )
            report.flush_jsonl(log_path)

        log.info(
            "rates_citi_hourly_complete",
            rows=rows,
            region=region,
            run_label=run_label,
            extraction_errors=len(pipeline._extraction_errors),
            quota_used=pipeline._quota_usage,
            elapsed=f"{elapsed:.1f}s",
        )
        return 0

    except TagQuotaExceeded as e:
        log.error(
            "rates_citi_hourly_tag_quota_exceeded",
            current_usage=getattr(e, "current_usage", None),
            available=getattr(e, "available", None),
        )
        report.error("tag_quota", f"Tag quota exceeded: {e}",
                     details={"current_usage": getattr(e, "current_usage", None),
                              "available": getattr(e, "available", None)})

        # Email the quota failure — previously this branch was silent.
        # `pipeline` is bound (the exception fires inside pipeline.run()),
        # and its _tag_errors aliases the extractor's, so any per-tag signals
        # captured before the quota tripped are still available.
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
                    universe=universe,
                    report=report,
                    target=start,
                    quotes=quotes,
                    rows_loaded=0,
                    rows_extracted=0,
                    holiday_hits=[],
                    elapsed_secs=0.0,
                    api_messages=api_messages,
                    quota_status=quota_status,
                    cohort_keys=cohort_keys,
                    run_label=run_label,
                )
            except Exception:
                log.exception("rates_citi_hourly_quota_email_failed")

        report.finish()
        if settings.run_log_dir:
            log_path = (
                Path(settings.run_log_dir)
                / "rates"
                / "fact_observation"
                / f"rates_citi_live_hourly_{run_label}_{start:%Y%m%d_%H%M}.jsonl"
            )
            report.flush_jsonl(log_path)
        return 1
    except Exception:
        log.exception("rates_citi_hourly_failed")
        report.error("pipeline", "Hourly rates ingest failed")
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
    rows_loaded: int,
    rows_extracted: int,
    holiday_hits: list,
    elapsed_secs: float,
    api_messages: list[dict] | None = None,
    quota_status: dict | None = None,
    cohort_keys: list[tuple[str, str]] | None = None,
    run_label: str = "FULL",
) -> None:
    """Build and send the hourly rates ingest report email scoped to the cohort."""
    # Scope the report to only the curves this run actually requested.
    # Surfacing out-of-cohort curves as "missing" would be noise.
    requested = set(cohort_keys) if cohort_keys is not None else set(DEFAULT_CURVES)
    all_curves = [c for c in universe.all_curves() if (c.ccy, c.curve) in requested]  # type: ignore[attr-defined]
    curve_data = []
    for c in all_curves:
        classification = universe.classification_for(c.ccy)  # type: ignore[attr-defined]
        curve_data.append({
            "ccy": c.ccy,
            "curve": c.curve,
            "classification": classification,
            "status": c.status,
            "tenors": len(universe.maturities_for_curve(c.ccy, c.curve)),  # type: ignore[attr-defined]
            "rows": 0,
        })

    # Classify missing curves by market status at run-time so "no data" is
    # explained rather than alarming: pre_open / non_trading are expected
    # gaps, while open / post_close flag genuine coverage concerns.
    now_utc = datetime.now(timezone.utc)
    missing = []
    unexpected_missing = []  # market is open or post-close → concerning
    if pipeline._raw_df is not None and not pipeline._raw_df.empty:
        loaded_keys = set(zip(pipeline._raw_df["ccy"], pipeline._raw_df["curve"]))
        for cd in curve_data:
            if (cd["ccy"], cd["curve"]) in loaded_keys:
                cd["rows"] = len(pipeline._raw_df[
                    (pipeline._raw_df["ccy"] == cd["ccy"]) &
                    (pipeline._raw_df["curve"] == cd["curve"])
                ])
            else:
                mkt, status = _classify_missing(cd["ccy"], now_utc)
                missing.append({
                    "ccy": cd["ccy"],
                    "curve": cd["curve"],
                    "market": mkt,
                    "status": status,
                    "reason": f"{_STATUS_REASON[status]}" + (f" ({mkt})" if mkt else ""),
                })
                if status in _UNEXPECTED_STATUSES:
                    unexpected_missing.append(f"{cd['ccy']}.{cd['curve']}")
    else:
        for c in curve_data:
            mkt, status = _classify_missing(c["ccy"], now_utc)
            missing.append({
                "ccy": c["ccy"],
                "curve": c["curve"],
                "market": mkt,
                "status": status,
                "reason": f"{_STATUS_REASON[status]}" + (f" ({mkt})" if mkt else ""),
            })
            if status in _UNEXPECTED_STATUSES:
                unexpected_missing.append(f"{c['ccy']}.{c['curve']}")

    if unexpected_missing:
        report.warning(
            "coverage_gap",
            f"{len(unexpected_missing)} curve(s) missing despite market open/closed",
            details={"curves": unexpected_missing},
        )

    formatter = RatesIngestFormatter()
    has_errors = report.has_errors

    subject = formatter.format_subject(
        pipeline_name=f"rates.citi_live_hourly[{run_label}]",
        run_date=target,
        rows_loaded=rows_loaded,
        has_errors=has_errors,
        mode="Hourly",
    )
    if quota_status is not None:
        subject = f"[QUOTA] {subject}"
    body = formatter.format_body(
        pipeline_name=f"rates.citi_live_hourly[{run_label}]",
        run_date=target,
        quotes=quotes,
        frequency="HOURLY",
        rows_extracted=rows_extracted,
        rows_loaded=rows_loaded,
        n_curves=len(all_curves),
        curves=curve_data,
        missing_curves=missing,
        holiday_hits=[
            {"currency": h.currency, "country_code": h.country_code, "name": h.name}
            for h in holiday_hits
        ],
        freshness=pipeline._metadata_freshness,
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
