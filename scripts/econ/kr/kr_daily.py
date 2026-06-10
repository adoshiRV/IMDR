"""Korea econ — DAILY orchestrator.

Runs every fetcher / sub-orchestrator that produces KR data at daily
cadence. Currently a single component:

  - scripts.econ.kr.govt.ingest_filings  — discovers + ingests govt
    policy filings (BoK, MOEF, MOTIR, FSC, FSS, KCS, KDI, MoDS) into
    ``research.dim_report`` + Qdrant + SharePoint via
    ``imdr.research.filings.ingest_filing``.

Future daily components (high-frequency rates / KRW spot / etc.) can be
added to ``PIPELINES`` below. The shape is identical to
``kr_weekly.py`` / ``kr_monthly.py`` — one subprocess per fetcher, with
isolation so a single failure doesn't block the rest.

Distinct from the ``_country_runner`` pattern used by weekly/monthly:
those orchestrators report indicator-row counts pulled from
``econ.fact_indicator``. KR has no daily-frequency indicators today,
but DOES produce daily filings (text documents) — so the email below
queries ``research.dim_report`` instead.

Wired into ``scripts/imdr_daily.py:PIPELINES``.

Usage:
    python -m scripts.econ.kr.kr_daily
    python -m scripts.econ.kr.kr_daily --no-email   # skip email
"""
from __future__ import annotations

import argparse
import datetime
import html as _html
import io
import subprocess
import sys
import time
import traceback
from pathlib import Path

# Force UTF-8 stdout — Korean titles + bullets come through subprocess output.
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import structlog
from sqlalchemy import create_engine, text

from imdr.config.settings import get_settings
from imdr.notifications.email import send_outlook_email
from imdr.utils.logging import configure_logging

log = structlog.get_logger(__name__)
UTC = datetime.timezone.utc


# ============================================================================
# REGISTERED PIPELINES — extend this list as new KR daily fetchers are added
# ============================================================================

PIPELINES: list[list[str]] = [
    [sys.executable, "-m", "scripts.econ.kr.govt.ingest_filings", "--ingest"],
]

# ============================================================================


def _engine():
    """Engine for the post-run filings snapshot. Uses ODBC Driver 18 because
    research.dim_report writes use BINARY + NVARCHAR(MAX) (per filings.py).
    """
    s = get_settings()
    url = (
        f"mssql+pyodbc://@{s.mssql_host}:{s.mssql_port}/{s.mssql_database}"
        "?driver=ODBC+Driver+18+for+SQL+Server"
        "&Trusted_Connection=yes&Encrypt=yes&TrustServerCertificate=yes"
        "&LoginTimeout=60"
    )
    return create_engine(url, pool_pre_ping=True, fast_executemany=True)


def _filings_snapshot(run_started_at: datetime.datetime) -> dict:
    """Pull stats on KR govt filings ingested at/after run_started_at.

    Returns a dict with:
      * by_vendor: list of (vendor_code, vendor_category, n_reports, n_chunks)
      * total_reports, total_chunks
      * recent_titles: 5 latest titles for the email teaser
    """
    eng = _engine()
    try:
        with eng.connect() as conn:
            by_vendor = conn.execute(
                text(
                    """
                    SELECT v.vendor_code, v.vendor_category, v.display_name,
                           COUNT(DISTINCT r.id) AS n_reports,
                           COUNT(c.id)           AS n_chunks
                    FROM research.dim_report r
                    JOIN dbo.dim_vendor v   ON v.id = r.vendor_id
                    LEFT JOIN research.fact_chunk c ON c.report_id = r.id
                    WHERE v.vendor_category LIKE 'official_%'
                      AND r.country_id = (SELECT id FROM dbo.dim_country WHERE country_code = 'KR')
                      AND r.created_at >= :t0
                    GROUP BY v.vendor_code, v.vendor_category, v.display_name
                    ORDER BY n_reports DESC, v.vendor_code
                    """
                ),
                {"t0": run_started_at},
            ).all()
            recent = conn.execute(
                text(
                    """
                    SELECT TOP 5 v.vendor_code, r.publish_date, r.title
                    FROM research.dim_report r
                    JOIN dbo.dim_vendor v   ON v.id = r.vendor_id
                    WHERE v.vendor_category LIKE 'official_%'
                      AND r.country_id = (SELECT id FROM dbo.dim_country WHERE country_code = 'KR')
                      AND r.created_at >= :t0
                    ORDER BY r.created_at DESC
                    """
                ),
                {"t0": run_started_at},
            ).all()
    finally:
        eng.dispose()
    total_reports = sum(r.n_reports for r in by_vendor)
    total_chunks = sum(r.n_chunks for r in by_vendor)
    return {
        "by_vendor": [
            {
                "vendor_code": v,
                "vendor_category": vc,
                "display_name": dn,
                "n_reports": int(nr),
                "n_chunks": int(nc),
            }
            for v, vc, dn, nr, nc in by_vendor
        ],
        "total_reports": int(total_reports),
        "total_chunks": int(total_chunks),
        "recent": [
            {"vendor_code": v, "publish_date": str(d), "title": t}
            for v, d, t in recent
        ],
    }


def _render_email(
    *,
    run_started_at: datetime.datetime,
    run_completed_at: datetime.datetime,
    duration_s: float,
    pipelines: list[dict],
    failed: list[str],
    snap: dict,
) -> tuple[str, str]:
    """Render (subject, html_body) for the daily KR email."""
    n_new = snap["total_reports"]
    n_chunks = snap["total_chunks"]
    fail_n = len(failed)
    status = "✓ all ok" if fail_n == 0 else f"⚠ {fail_n} failed"
    subject = (
        f"[IMDR Daily KR] {status} — {n_new} new filings, {n_chunks} chunks "
        f"({duration_s/60:.1f} min)"
    )

    # Every external string (titles, display_names, pipeline argv tail)
    # goes through html.escape() — titles come from foreign govt sources
    # scraped via BeautifulSoup and are user-supplied wrt this email.
    def _e(s: object) -> str:
        return _html.escape(str(s or ""))

    rows_pipelines = "\n".join(
        f"<tr><td>{_e(p['name'])}</td><td>{p['rc']}</td>"
        f"<td style='text-align:right'>{p['elapsed_s']:.1f}s</td></tr>"
        for p in pipelines
    )
    rows_vendors = "\n".join(
        f"<tr><td>{_e(v['vendor_code'])}</td><td>{_e(v['display_name'])}</td>"
        f"<td>{_e(v['vendor_category'])}</td>"
        f"<td style='text-align:right'>{v['n_reports']}</td>"
        f"<td style='text-align:right'>{v['n_chunks']}</td></tr>"
        for v in snap["by_vendor"]
    ) or "<tr><td colspan='5' style='color:#888'>no new filings</td></tr>"
    rows_recent = "\n".join(
        f"<tr><td>{_e(r['vendor_code'])}</td><td>{_e(r['publish_date'])}</td>"
        f"<td>{_e(r['title'][:120])}</td></tr>"
        for r in snap["recent"]
    ) or "<tr><td colspan='3' style='color:#888'>—</td></tr>"

    css = (
        "body{font-family:Segoe UI,Arial,sans-serif;font-size:13px;}"
        "table{border-collapse:collapse;margin:8px 0;}"
        "th,td{border:1px solid #ddd;padding:4px 8px;}"
        "th{background:#f4f4f4;text-align:left;}"
        ".meta{color:#666;margin-top:12px;font-size:11px;}"
    )

    body = f"""<!doctype html><html><head><style>{css}</style></head><body>
<h3>IMDR KR Daily — government filings ingest</h3>
<p>Started {run_started_at:%Y-%m-%d %H:%M UTC} · finished {run_completed_at:%H:%M UTC} ·
duration {duration_s/60:.1f} min · {n_new} new filings / {n_chunks} chunks ·
{fail_n} pipeline(s) failed</p>

<h4>Pipelines</h4>
<table><thead><tr><th>name</th><th>rc</th><th>elapsed</th></tr></thead>
<tbody>{rows_pipelines}</tbody></table>

<h4>Filings ingested by vendor</h4>
<table><thead><tr><th>code</th><th>vendor</th><th>category</th>
<th style='text-align:right'>reports</th><th style='text-align:right'>chunks</th></tr></thead>
<tbody>{rows_vendors}</tbody></table>

<h4>Most recent (top 5)</h4>
<table><thead><tr><th>code</th><th>date</th><th>title</th></tr></thead>
<tbody>{rows_recent}</tbody></table>

<p class="meta">Orchestrator: <code>scripts.econ.kr.kr_daily</code>.
Pipeline detail: <code>scripts/econ/kr/govt/data/_last_run.log</code> on the host.</p>
</body></html>"""
    return subject, body


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--no-email", action="store_true",
        help="skip the email send (subprocess + DB snapshot still run)",
    )
    args = ap.parse_args(argv)

    settings = get_settings()
    configure_logging(settings)

    run_started_at = datetime.datetime.now(UTC)
    t0 = time.perf_counter()

    pipeline_results: list[dict] = []
    failed: list[str] = []
    for cmd in PIPELINES:
        name = cmd[-1] if cmd[-1] != "--ingest" else cmd[-2]
        p_start = time.perf_counter()
        rc = subprocess.call(cmd)
        elapsed = time.perf_counter() - p_start
        pipeline_results.append({"name": name, "rc": rc, "elapsed_s": elapsed})
        if rc != 0:
            print(f"FAIL  {name}  rc={rc}  ({elapsed:.1f}s)")
            failed.append(name)
        else:
            print(f"OK    {name}  ({elapsed:.1f}s)")

    duration_s = time.perf_counter() - t0
    run_completed_at = datetime.datetime.now(UTC)

    # --- Filings snapshot + email -----------------------------------------
    snap: dict = {"by_vendor": [], "total_reports": 0, "total_chunks": 0, "recent": []}
    try:
        snap = _filings_snapshot(run_started_at)
        log.info(
            "kr_daily_filings_snapshot",
            new_reports=snap["total_reports"],
            new_chunks=snap["total_chunks"],
            vendors_with_activity=len(snap["by_vendor"]),
        )
    except Exception:
        log.exception("kr_daily_filings_snapshot_failed")
        print(f"\n!! filings snapshot failed:\n{traceback.format_exc()}")

    if (
        not args.no_email
        and getattr(settings, "email_enabled", False)
        and getattr(settings, "email_to", "")
    ):
        try:
            subject, body = _render_email(
                run_started_at=run_started_at,
                run_completed_at=run_completed_at,
                duration_s=duration_s,
                pipelines=pipeline_results,
                failed=failed,
                snap=snap,
            )
            send_outlook_email(
                to=settings.email_to,
                subject=subject,
                html_body=body,
                importance=2 if failed else 1,
            )
        except Exception:
            log.exception("kr_daily_email_failed")
            print(f"\n!! email render/send failed:\n{traceback.format_exc()}")
    elif args.no_email:
        print("\n(email skipped by --no-email)")
    else:
        log.info("email_disabled_skipping_kr_daily_summary")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
