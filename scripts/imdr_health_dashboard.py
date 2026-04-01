"""Weekly health dashboard — runs all domain checks and sends a consolidated email.

Collects health checks, coverage analysis, quality checks, and cleaning
dry-run results for all three domains (FX OHLC, FX Vol, Rates) into
a single HTML email.

All check/rule definitions are imported from the domain scripts (single
source of truth). This script is a thin orchestrator — it does NOT
define any checks or rules itself.

Usage:
    python -m scripts.imdr_health_dashboard
    python -m scripts.imdr_health_dashboard --no-email
    python -m scripts.imdr_health_dashboard --year 2026
"""

from __future__ import annotations

import argparse
import time
from datetime import datetime, timezone

import structlog

from imdr.config.settings import get_settings
from imdr.connectors.mssql import MSSQLConnector
from imdr.connectors.reader import AnalyticalReader
from imdr.domains.commodities.coverage import get_cmdty_vol_coverage
from imdr.domains.fx.coverage import get_ohlc_coverage, get_vol_coverage
from imdr.domains.rates.coverage import get_rates_coverage
from imdr.healthchecks.clean_cli import compute_overlap_stats
from imdr.healthchecks.cleaning import CleaningRunner
from imdr.healthchecks.dashboard import DomainReport, WeeklyDashboard
from imdr.healthchecks.reporter import HealthReporter
from imdr.notifications.email import send_outlook_email
from imdr.notifications.formatters.weekly_dashboard import WeeklyDashboardFormatter

# Domain builders — single source of truth (all from cleaning CLIs)
from scripts.fx.clean.clean_fx_fact_ohlc import (
    build_health_checks as ohlc_health_checks,
    build_quality_checks as ohlc_quality_checks,
    build_cleaning_rules as ohlc_cleaning_rules,
)
from scripts.fx.clean.clean_fx_fact_vol import (
    build_health_checks as vol_health_checks,
    build_quality_checks as vol_quality_checks,
    build_cleaning_rules as vol_cleaning_rules,
)
from scripts.rates.clean.clean_rates_fact_observation import (
    build_health_checks as rates_health_checks,
    build_quality_checks as rates_quality_checks,
    build_cleaning_rules as rates_cleaning_rules,
)
from scripts.commodities.clean.clean_cmdty_fact_implied_vol import (
    build_health_checks as cmdty_vol_health_checks,
    build_quality_checks as cmdty_vol_quality_checks,
    build_cleaning_rules as cmdty_vol_cleaning_rules,
)

log = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# FX OHLC
# ---------------------------------------------------------------------------

def _collect_fx_ohlc(
    connector: MSSQLConnector,
    reader: AnalyticalReader,
    years: list[int] | None = None,
) -> DomainReport:
    log.info("dashboard_collect", domain="FX OHLC")
    reporter = HealthReporter(connector, "fx.ohlc")
    years = years or reporter.discover_years()

    health_report = reporter.run_health_window(
        ohlc_health_checks(), lookback_days=30, quiet=True,
    )
    coverage = get_ohlc_coverage(reader, "[fx].[fact_ohlc]", years)
    quality = reporter.run_quality_section(
        ohlc_quality_checks(), years, quiet=True,
    )

    runner = CleaningRunner(
        connector=connector, reader=reader,
        rules=ohlc_cleaning_rules(), table="[fx].[fact_ohlc]",
        dry_run=True,
    )
    cleaning = runner.run()

    return DomainReport(
        domain_name="FX OHLC",
        table_name="[fx].[fact_ohlc]",
        years=years,
        health_reports=[health_report],
        coverage=coverage,
        quality_results=quality,
        cleaning_results=cleaning,
    )


# ---------------------------------------------------------------------------
# FX Vol
# ---------------------------------------------------------------------------

def _collect_fx_vol(
    connector: MSSQLConnector,
    reader: AnalyticalReader,
    years: list[int] | None = None,
) -> DomainReport:
    log.info("dashboard_collect", domain="FX Vol")
    reporter = HealthReporter(connector, "fx.vol")
    years = years or reporter.discover_years()

    health_report = reporter.run_health_window(
        vol_health_checks(), lookback_days=30, quiet=True,  # freshness from pipelines.yml
    )
    coverage = get_vol_coverage(reader, "[fx].[fact_vol]", years)
    quality = reporter.run_quality_section(
        vol_quality_checks(), years, quiet=True,
    )

    runner = CleaningRunner(
        connector=connector, reader=reader,
        rules=vol_cleaning_rules(), table="[fx].[fact_vol]",
        dry_run=True,
    )
    cleaning = runner.run()

    return DomainReport(
        domain_name="FX Vol",
        table_name="[fx].[fact_vol]",
        years=years,
        health_reports=[health_report],
        coverage=coverage,
        quality_results=quality,
        cleaning_results=cleaning,
    )


# ---------------------------------------------------------------------------
# Rates
# ---------------------------------------------------------------------------

def _collect_rates(
    connector: MSSQLConnector,
    reader: AnalyticalReader,
    years: list[int] | None = None,
) -> DomainReport:
    log.info("dashboard_collect", domain="Rates")
    reporter = HealthReporter(connector, "rates.historical")
    years = years or reporter.discover_years()

    health_report = reporter.run_health_window(
        rates_health_checks(), lookback_days=30, quiet=True,  # freshness from pipelines.yml
    )
    coverage = get_rates_coverage(reader, "[rates].[fact_observation]", years)
    quality = reporter.run_quality_section(
        rates_quality_checks(), years, quiet=True,
    )

    runner = CleaningRunner(
        connector=connector, reader=reader,
        rules=rates_cleaning_rules(), table="[rates].[fact_observation]",
        dry_run=True,
    )
    cleaning = runner.run()

    return DomainReport(
        domain_name="Rates",
        table_name="[rates].[fact_observation]",
        years=years,
        health_reports=[health_report],
        coverage=coverage,
        quality_results=quality,
        cleaning_results=cleaning,
    )


# ---------------------------------------------------------------------------
# Commodities Implied Vol
# ---------------------------------------------------------------------------

def _collect_cmdty_vol(
    connector: MSSQLConnector,
    reader: AnalyticalReader,
    years: list[int] | None = None,
) -> DomainReport:
    log.info("dashboard_collect", domain="Commodities Vol")
    reporter = HealthReporter(connector, "commodities.vol")
    years = years or reporter.discover_years()

    health_report = reporter.run_health_window(
        cmdty_vol_health_checks(), lookback_days=30, quiet=True,
    )
    coverage = get_cmdty_vol_coverage(reader, "[commodities].[fact_implied_vol]", years)
    quality = reporter.run_quality_section(
        cmdty_vol_quality_checks(), years, quiet=True,
    )

    runner = CleaningRunner(
        connector=connector, reader=reader,
        rules=cmdty_vol_cleaning_rules(), table="[commodities].[fact_implied_vol]",
        dry_run=True,
    )
    cleaning = runner.run()

    return DomainReport(
        domain_name="Commodities Vol",
        table_name="[commodities].[fact_implied_vol]",
        years=years,
        health_reports=[health_report],
        coverage=coverage,
        quality_results=quality,
        cleaning_results=cleaning,
    )


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def _print_domain_detail(domain: DomainReport) -> None:
    """Print per-domain detail: failed health checks, quality flags, cleaning breakdown.

    Only expands sections that have issues. Clean domains get a one-liner.
    Cleaning overlap stats reuse ``compute_overlap_stats`` from clean_cli.
    """
    label = f"{domain.domain_name} -- {domain.table_name}"
    print(f"\n  -- {label} {'-' * max(1, 62 - len(label))}")

    # Collect failed/warning health checks across all year reports.
    failed_checks = [
        cr
        for report in domain.health_reports
        for cr in report.results
        if cr.status.value != "passed"
    ]

    # Collect non-passed quality results.
    quality_flags = [
        r for r in domain.quality_results if r.status.value != "passed"
    ]

    # Any cleaning flags?
    cleaning_total = sum(r.count for r in domain.cleaning_results)

    # If everything is clean, one-liner and return.
    if not failed_checks and not quality_flags and cleaning_total == 0:
        print("  All passed. No cleaning flags.")
        return

    # --- Health detail ---
    if failed_checks:
        print(f"\n  Health (FAIL):")
        for cr in failed_checks:
            icon = "X" if cr.status.value == "failed" else "!"
            print(f"    {icon} {cr.check_name:<20} {cr.message}")

    # --- Quality detail ---
    if quality_flags:
        print(f"\n  Quality ({len(quality_flags)} warnings):")
        for r in quality_flags:
            print(f"    ! {r.check_name:<20} {r.message}")

    # --- Cleaning detail ---
    if cleaning_total > 0:
        id_sets, unique_counts, total_unique = compute_overlap_stats(
            domain.cleaning_results,
        )
        print(f"\n  Cleaning [DRY RUN]:")
        print(f"    {'Rule':<20} {'Rows':>8} {'Unique':>8}  Action")
        print(f"    {'-' * 52}")
        for r in domain.cleaning_results:
            action = r.actions[0].action if r.actions else "-"
            uniq = unique_counts.get(r.rule_name)
            uniq_str = str(uniq) if uniq is not None else "-"
            print(f"    {r.rule_name:<20} {r.count:>8} {uniq_str:>8}  {action}")
        print(f"    {'-' * 52}")
        print(f"    {'TOTAL':<20} {cleaning_total:>8}")
        if id_sets:
            null_total = sum(
                r.count for r in domain.cleaning_results if r.rule_name in id_sets
            )
            overlap = null_total - total_unique
            print(
                f"    {'UNIQUE':<20} {total_unique:>8}  ({overlap} overlapping)"
            )


def _print_summary(dashboard: WeeklyDashboard, elapsed: float) -> None:
    """Print overview table followed by per-domain detail sections."""
    print(f"\n{'=' * 70}")
    print("  WEEKLY HEALTH DASHBOARD SUMMARY")
    print(f"{'=' * 70}")

    header = f"  {'Domain':<14}{'Table':<30}{'Health':<9}{'Quality':>9}{'Cleaning':>10}"
    print(f"\n{header}")
    print(f"  {'-' * 13} {'-' * 29} {'-' * 7} {'-' * 9} {'-' * 10}")

    for d in dashboard.domains:
        health_str = "PASS" if d.health_passed else "FAIL"
        quality_flags = sum(
            1 for r in d.quality_results if r.status.value != "passed"
        )
        cleaning_flags = d.total_cleaning_flags
        print(
            f"  {d.domain_name:<14}{d.table_name:<30}{health_str:<9}"
            f"{quality_flags:>9}{cleaning_flags:>10}"
        )

    healthy = sum(1 for d in dashboard.domains if d.health_passed)
    total = len(dashboard.domains)
    print(f"\n  Overall: {healthy}/{total} domains healthy  ({elapsed:.1f}s)")

    # Per-domain detail (expands only if issues found).
    for d in dashboard.domains:
        _print_domain_detail(d)

    print(f"\n{'=' * 70}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Weekly health dashboard — consolidated email for all domains",
    )
    parser.add_argument("--year", type=int, help="Restrict to a single year")
    parser.add_argument(
        "--no-email",
        action="store_true",
        help="Skip sending email (print HTML to stdout instead)",
    )
    args = parser.parse_args()

    years = [args.year] if args.year else None

    settings = get_settings()
    connector = MSSQLConnector(settings)
    reader = AnalyticalReader(connector)

    t0 = time.perf_counter()

    print(f"\n{'=' * 70}")
    print("  WEEKLY HEALTH DASHBOARD — collecting data")
    print(f"{'=' * 70}")

    print(f"\n  [1/4] FX OHLC ...")
    ohlc = _collect_fx_ohlc(connector, reader, years)
    print(f"         done.")

    print(f"  [2/4] FX Vol ...")
    vol = _collect_fx_vol(connector, reader, years)
    print(f"         done.")

    print(f"  [3/4] Rates ...")
    rates = _collect_rates(connector, reader, years)
    print(f"         done.")

    print(f"  [4/4] Commodities Vol ...")
    cmdty_vol = _collect_cmdty_vol(connector, reader, years)
    print(f"         done.")

    dashboard = WeeklyDashboard(
        generated_at=datetime.now(timezone.utc),
        domains=[ohlc, vol, rates, cmdty_vol],
    )

    elapsed = time.perf_counter() - t0
    log.info("dashboard_collected", elapsed=f"{elapsed:.1f}s", domains=len(dashboard.domains))
    _print_summary(dashboard, elapsed)

    formatter = WeeklyDashboardFormatter()
    subject = formatter.format_subject(dashboard)
    body = formatter.format_body(dashboard)

    if args.no_email:
        print(f"\nSubject: {subject}\n")
        print(body)
    elif settings.email_enabled and settings.email_to:
        sent = send_outlook_email(
            to=settings.email_to,
            subject=subject,
            html_body=body,
            importance=1,
        )
        if sent:
            log.info("dashboard_email_sent", to=settings.email_to, subject=subject)
        else:
            log.warning("dashboard_email_failed")
    else:
        log.warning("dashboard_email_disabled", email_enabled=settings.email_enabled)
        print(f"\nSubject: {subject}")
        print("Email not sent (disabled or no recipients configured).")

    connector.dispose()
    print(f"\nWeekly dashboard complete ({elapsed:.1f}s).")


if __name__ == "__main__":
    main()
