"""End-of-day BBG FX SNAPSHOT health check.

Run once daily (e.g. 20:00 SGT, after the 19:20 BBG ingest fire). Counts
distinct ``obs_ts`` per pair for today's ``obs_date`` and flags pairs
that didn't capture all 6 expected intraday batches. Cross-references
``Z:\\BBG_mirror\\log\\bbgCheck\\*.csv`` to distinguish upstream BBG
terminal failures (V=NA in heartbeat filename) from our ingest failures.

Usage
-----
    python -m scripts.bbg_fx_health_check                    # today, prints + email
    python -m scripts.bbg_fx_health_check --date 2026-04-23  # specific date
    python -m scripts.bbg_fx_health_check --no-email         # console only
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import text

from imdr.config.settings import get_settings
from imdr.connectors.mssql import MSSQLConnector
from imdr.notifications.bbg_health_core import (
    SGT,
    BBGCheckSummary,
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

# Pairs we know are broken upstream (R-side label issues). They will never
# capture batches; excluded from the OK/PARTIAL counts so the email stays
# green when only these are failing.
KNOWN_BROKEN_PAIRS: set[str] = {"USD/CNO"}

# DAILY (close-of-day) coverage window — last 5 business days.
DAILY_LOOKBACK_DAYS = 5
EXPECTED_DAILY_PAIRS = 22  # 26 universe - 4 onshore variants typically empty


@dataclass
class DailyCoverageRow:
    """One row per (obs_date) for the DAILY-frequency coverage report."""
    obs_date: date
    pairs: int
    rows: int

    @property
    def is_ok(self) -> bool:
        return self.pairs >= EXPECTED_DAILY_PAIRS


def query_pair_status(connector: MSSQLConnector, target_date: date) -> list[ItemStatus]:
    """Per-pair snapshot count + which UTC hours showed up."""
    sql = text("""
        SELECT
            p.base_ccy + '/' + p.quote_ccy AS pair,
            DATEPART(HOUR, f.obs_ts) AS obs_hour_utc,
            COUNT(*) AS row_count
        FROM fx.fact_fx_rate f
        JOIN fx.dim_currency_pair p ON p.id = f.pair_id
        WHERE f.vendor_id = (SELECT id FROM dbo.dim_vendor WHERE vendor_code = 'BBG')
          AND f.frequency_id = (SELECT id FROM dbo.dim_frequency WHERE frequency_code = 'SNAPSHOT')
          AND f.obs_date = :d
        GROUP BY p.base_ccy, p.quote_ccy, DATEPART(HOUR, f.obs_ts)
        ORDER BY pair, obs_hour_utc
    """)
    # Legacy 'SQL Server' ODBC driver can't bind date — pass ISO string
    with connector.read_engine.connect() as conn:
        rows = conn.execute(sql, {"d": target_date.isoformat()}).all()

    by_pair: dict[str, ItemStatus] = {}
    for pair, hour, n in rows:
        st = by_pair.setdefault(
            pair, ItemStatus(label=pair, is_known_broken=pair in KNOWN_BROKEN_PAIRS),
        )
        st.captured_hours_utc.append(int(hour))
        st.rows += int(n)
    return sorted(by_pair.values(), key=lambda x: x.label)


def query_daily_coverage(
    connector: MSSQLConnector, target_date: date,
    lookback_days: int = DAILY_LOOKBACK_DAYS,
) -> list[DailyCoverageRow]:
    """Per-date count of DAILY-frequency rows + pairs over the last N days."""
    sql = text("""
        SELECT
            f.obs_date,
            COUNT(DISTINCT f.pair_id) AS pairs,
            COUNT(*) AS rows
        FROM fx.fact_fx_rate f
        WHERE f.vendor_id = (SELECT id FROM dbo.dim_vendor WHERE vendor_code = 'BBG')
          AND f.frequency_id = (SELECT id FROM dbo.dim_frequency WHERE frequency_code = 'DAILY')
          AND f.obs_date >= :start AND f.obs_date <= :end
        GROUP BY f.obs_date
        ORDER BY f.obs_date DESC
    """)
    start = (target_date - timedelta(days=lookback_days)).isoformat()
    end = target_date.isoformat()
    with connector.read_engine.connect() as conn:
        rows = conn.execute(sql, {"start": start, "end": end}).all()
    out: list[DailyCoverageRow] = []
    for r in rows:
        d = r[0]
        if isinstance(d, str):
            d = date.fromisoformat(d)
        # Skip Sat/Sun — BBG R pipeline doesn't run; only the 4 onshore
        # variants (CNO/MYO/IDO/CNY) have weekend rows from upstream R.
        if d.weekday() >= 5:
            continue
        out.append(DailyCoverageRow(obs_date=d, pairs=int(r[1]), rows=int(r[2])))
    return out


def _daily_coverage_html(rows: list[DailyCoverageRow]) -> str:
    if not rows:
        return ""
    body = "<h3>DAILY close-of-day coverage (last 5 days)</h3>"
    body += "<table border='1' cellpadding='6' cellspacing='0'>"
    body += "<tr><th>obs_date</th><th>Pairs</th><th>Rows</th><th>Status</th></tr>"
    for d in rows:
        color = "#5cb85c" if d.is_ok else "#f0ad4e"
        status = "OK" if d.is_ok else f"PARTIAL ({d.pairs}/{EXPECTED_DAILY_PAIRS})"
        body += (
            f"<tr><td>{d.obs_date.isoformat()}</td>"
            f"<td>{d.pairs}</td>"
            f"<td>{d.rows}</td>"
            f"<td style='color: {color};'>{status}</td></tr>"
        )
    body += "</table>"
    return body


def _daily_coverage_console(rows: list[DailyCoverageRow]) -> list[str]:
    if not rows:
        return []
    lines = [
        f"\nDAILY close-of-day coverage (last {DAILY_LOOKBACK_DAYS} days, "
        f"expecting >= {EXPECTED_DAILY_PAIRS} pairs/day):"
    ]
    for d in rows:
        status = "OK" if d.is_ok else f"PARTIAL ({d.pairs}/{EXPECTED_DAILY_PAIRS})"
        lines.append(
            f"  {d.obs_date.isoformat()}  pairs={d.pairs:>3}  "
            f"rows={d.rows:>4}  {status}"
        )
    return lines


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

    from imdr.universe.fx import get_fx_universe
    universe_size = len(get_fx_universe().fx_rate_pairs())

    items = query_pair_status(connector, target_date)
    bbg_check = scan_bbg_check_log(target_date)
    daily_coverage = query_daily_coverage(connector, target_date)

    n_daily_partial = sum(1 for d in daily_coverage if not d.is_ok)
    report: HealthReport = summarize(
        items, universe_size, KNOWN_BROKEN_PAIRS, bbg_check,
        extra_problem=(n_daily_partial > 0),
    )

    print_console(
        noun="pair", domain_label="FX",
        target_date=target_date, items=items, bbg_check=bbg_check,
        report=report, label_width=10,
        extra_lines=_daily_coverage_console(daily_coverage),
    )

    if not args.no_email and settings.email_enabled and settings.email_to:
        html = build_html(
            noun="pair", domain_label="FX",
            target_date=target_date, items=items, bbg_check=bbg_check,
            report=report,
            source_path_hint=r"Z:\...\BBG_mirror\FX\{CCY}\FX_{CCY}.csv",
            pipeline_hint=("fx.bloomberg_snapshot (SNAPSHOT, every 30 min) + "
                           "fx.bloomberg_daily (DAILY, ~22:00 SGT)"),
            extra_html=_daily_coverage_html(daily_coverage),
        )
        extra: list[str] = []
        if n_daily_partial:
            extra.append(f"DAILY {n_daily_partial} day(s) short")
        subject = build_subject(
            domain_label="FX", target_date=target_date,
            report=report, bbg_check=bbg_check, extra_segments=extra,
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
