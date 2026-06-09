"""End-of-day BBG rates SNAPSHOT health check.

Run once daily (e.g. 20:00 SGT, after the 19:45 BBG ingest fire). Counts
distinct ``ts`` per (curve, vendor=bloomberg, frequency=SNAPSHOT) for
today's date and flags curves that didn't capture all 6 expected
intraday batches. Mirrors the FX health-check shape via
``imdr.notifications.bbg_health_core``.

Usage
-----
    python -m scripts.bbg_rates_health_check                    # today, prints + email
    python -m scripts.bbg_rates_health_check --date 2026-04-28  # specific date
    python -m scripts.bbg_rates_health_check --no-email         # console only
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, datetime

from sqlalchemy import text

from imdr.config.settings import get_settings
from imdr.connectors.mssql import MSSQLConnector
from imdr.notifications.bbg_health_core import (
    SGT,
    HealthReport,
    ItemStatus,
    build_html,
    build_subject,
    print_console,
    scan_bbg_check_log,
    summarize,
)
from imdr.notifications.email import send_outlook_email

# Side-effect: load all ORM models for cross-schema FK resolution
import imdr.models.calendar  # noqa: F401
import imdr.models.fx_vol    # noqa: F401
import imdr.models.fx_rate   # noqa: F401
import imdr.models.fx_ohlc   # noqa: F401
import imdr.models.rates     # noqa: F401

# Curves we know are broken upstream. Empty for now — populate as ops
# experience surfaces broken curves (e.g. {"PLN/WIBOR_6M"}).
KNOWN_BROKEN_CURVES: set[str] = set()


def query_curve_status(
    connector: MSSQLConnector, target_date: date,
) -> list[ItemStatus]:
    """Per-curve snapshot count + which UTC hours showed up."""
    sql = text("""
        SELECT
            c.ccy + '/' + c.curve AS curve_label,
            DATEPART(HOUR, o.ts) AS obs_hour_utc,
            COUNT(*) AS row_count
        FROM rates.fact_observation o
        JOIN rates.dim_curve c ON c.id = o.curve_id
        WHERE o.vendor_id = (SELECT id FROM dbo.dim_vendor WHERE vendor_code = 'BBG')
          AND o.frequency_id = (SELECT id FROM dbo.dim_frequency WHERE frequency_code = 'SNAPSHOT')
          AND CAST(o.ts AS DATE) = :d
        GROUP BY c.ccy, c.curve, DATEPART(HOUR, o.ts)
        ORDER BY curve_label, obs_hour_utc
    """)
    # Legacy 'SQL Server' ODBC driver can't bind date — pass ISO string
    with connector.read_engine.connect() as conn:
        rows = conn.execute(sql, {"d": target_date.isoformat()}).all()

    by_curve: dict[str, ItemStatus] = {}
    for label, hour, n in rows:
        st = by_curve.setdefault(
            label, ItemStatus(label=label,
                              is_known_broken=label in KNOWN_BROKEN_CURVES),
        )
        st.captured_hours_utc.append(int(hour))
        st.rows += int(n)
    return sorted(by_curve.values(), key=lambda x: x.label)


def query_universe_size(connector: MSSQLConnector) -> int:
    """Count of curves we expect to see live ingest from.

    Defined as: rows in dim_curve with citi_prefix starting with 'BBG:'
    (BBG-only curves auto-seeded by the pipeline). Falls back to all
    rows if no BBG-prefixed curves exist yet.
    """
    with connector.read_engine.connect() as conn:
        n = conn.execute(text(
            "SELECT COUNT(*) FROM rates.dim_curve WHERE citi_prefix LIKE 'BBG:%'"
        )).scalar_one()
        if n == 0:
            n = conn.execute(text(
                "SELECT COUNT(*) FROM rates.dim_curve"
            )).scalar_one()
    return int(n or 0)


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    parser.add_argument("--date", default=None,
                        help="Target obs_date YYYY-MM-DD (default: today SGT).")
    parser.add_argument("--no-email", action="store_true",
                        help="Print to console only; do not send email.")
    args = parser.parse_args()

    target_date = (date.fromisoformat(args.date) if args.date
                   else datetime.now(SGT).date())

    settings = get_settings()
    if settings.mssql_database != "IMDR":
        raise RuntimeError(
            f"Refusing to run: IMDR_MSSQL_DATABASE={settings.mssql_database!r}"
        )

    connector = MSSQLConnector(settings)

    universe_size = query_universe_size(connector)
    items = query_curve_status(connector, target_date)
    bbg_check = scan_bbg_check_log(target_date)

    report: HealthReport = summarize(
        items, universe_size, KNOWN_BROKEN_CURVES, bbg_check,
    )

    print_console(
        noun="curve", domain_label="rates",
        target_date=target_date, items=items, bbg_check=bbg_check,
        report=report, label_width=22,
    )

    if not args.no_email and settings.email_enabled and settings.email_to:
        html = build_html(
            noun="curve", domain_label="rates",
            target_date=target_date, items=items, bbg_check=bbg_check,
            report=report,
            source_path_hint=r"Z:\...\BBG_mirror\{IRS,OIS,BASIS,CCS}\{CURVE}\PAR\*.csv",
            pipeline_hint="rates.bloomberg_snapshot (SNAPSHOT, half-hourly 09:45-20:45 SGT)",
        )
        subject = build_subject(
            domain_label="rates", target_date=target_date,
            report=report, bbg_check=bbg_check,
        )
        send_outlook_email(
            to=settings.email_to,
            subject=subject,
            html_body=html,
            importance=2 if report.has_problem else 1,
        )

    return 1 if report.has_problem else 0


if __name__ == "__main__":
    sys.exit(main())
