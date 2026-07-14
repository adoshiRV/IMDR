"""United States econ — DAILY orchestrator (dual-track).

Runs every fetcher / sub-orchestrator that produces US data at daily cadence:

  Track A — daily data series:
    - scripts.econ.us.eia.eia_energy        (WTI / Brent / Henry Hub spot; MERGE on
                                             PK so non-publishing days are harmless)
    - scripts.econ.us.treasury.treasury_debt (Debt to the Penny, daily)

  Track B — Fed / Treasury / NY Fed filings:
    - scripts.econ.us.govt.ingest_filings --since-days 7
        (re-discovers the 11 streams, ingests docs published in the last 7 days →
         research.dim_report + research.fact_chunk + Qdrant + SharePoint;
         content-hash dedup makes the rolling window idempotent. The one-time
         multi-year backfill is `ingest_filings --recent-years 2`, run manually.)

Email composes BOTH sides:
  - Track A indicator counts via ``econ.fact_indicator`` (rows ingested this run, DAILY freq)
  - Track B filings via ``research.dim_report`` (official_* vendor rows created this run)

3-pipeline design lets one failure leave the others unblocked — each subprocess is
isolated; the orchestrator continues regardless of rc and reports all outcomes.

PROD-LIVE: wired into ``scripts/imdr_daily.py:PIPELINES`` 2026-06-23. Must run
under the conda ``imdr`` env (Py3.11) for the Track B ingest deps.

Usage:
    python -m scripts.econ.us.us_daily
    python -m scripts.econ.us.us_daily --no-email
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

# Force UTF-8 stdout — em-dashes / bullet chars come through subprocess output.
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
# REGISTERED PIPELINES — extend as new US daily fetchers land
# ============================================================================

PIPELINES: list[list[str]] = [
    # Track A — daily indicator snapshot
    [sys.executable, "-m", "scripts.econ.us.eia.eia_energy"],
    [sys.executable, "-m", "scripts.econ.us.treasury.treasury_debt"],
    # FRED — US daily+weekly financial-conditions/high-frequency set (seed_us.yml)
    [sys.executable, "-m", "scripts.econ.us.fred.fred_us_daily"],
    # Track B — ingest docs published in the rolling 7-day window
    [sys.executable, "-m", "scripts.econ.us.govt.ingest_filings", "--since-days", "7"],
]

# ============================================================================


def _engine():
    """Engine for post-run snapshots. ODBC Driver 18 because research.dim_report
    writes use BINARY + NVARCHAR(MAX) (per filings.py)."""
    s = get_settings()
    url = (
        f"mssql+pyodbc://@{s.mssql_host}:{s.mssql_port}/{s.mssql_database}"
        "?driver=ODBC+Driver+18+for+SQL+Server"
        "&Trusted_Connection=yes&Encrypt=yes&TrustServerCertificate=yes"
        "&LoginTimeout=60"
    )
    return create_engine(url, pool_pre_ping=True, fast_executemany=True)


def _track_a_snapshot(run_started_at: datetime.datetime) -> dict:
    """Stats on US DAILY indicators ingested DURING THIS RUN (ingested_at >= t0)."""
    eng = _engine()
    try:
        with eng.connect() as conn:
            by_vendor = conn.execute(
                text(
                    """
                    SELECT v.display_name                  AS vendor_name,
                           COUNT(DISTINCT i.id)            AS n_indicators,
                           COUNT(f.indicator_id)           AS n_obs,
                           MAX(f.obs_date)                 AS latest_obs
                    FROM   econ.fact_indicator f
                    JOIN   econ.dim_indicator i ON i.id = f.indicator_id
                    JOIN   dbo.dim_vendor v ON v.id = i.vendor_id
                    JOIN   dbo.dim_frequency fq ON fq.id = i.frequency_id
                    JOIN   dbo.dim_country c ON c.id = i.country_id
                    WHERE  c.country_code = 'US'
                      AND  fq.frequency_code IN ('DAILY', 'WEEKLY')
                      AND  f.ingested_at >= :t0
                    GROUP BY v.display_name
                    ORDER BY n_obs DESC
                    """
                ),
                {"t0": run_started_at},
            ).all()
    finally:
        eng.dispose()
    total_obs = sum(r.n_obs for r in by_vendor)
    return {
        "by_vendor": [
            {"vendor_name": vn, "n_indicators": int(ni), "n_obs": int(no), "latest_obs": str(lo)}
            for vn, ni, no, lo in by_vendor
        ],
        "total_obs": int(total_obs),
    }


def _filings_snapshot(run_started_at: datetime.datetime) -> dict:
    """Stats on US official filings ingested at/after run_started_at."""
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
                      AND r.country_id = (SELECT id FROM dbo.dim_country WHERE country_code = 'US')
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
                      AND r.country_id = (SELECT id FROM dbo.dim_country WHERE country_code = 'US')
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
            {"vendor_code": v, "vendor_category": vc, "display_name": dn,
             "n_reports": int(nr), "n_chunks": int(nc)}
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
    track_a: dict,
) -> tuple[str, str]:
    n_new = snap["total_reports"]
    n_chunks = snap["total_chunks"]
    n_obs = track_a["total_obs"]
    fail_n = len(failed)

    if fail_n > 1:
        status, banner_color = "FAIL", "#e74c3c"
    elif fail_n == 1:
        status, banner_color = "PARTIAL", "#f39c12"
    else:
        status, banner_color = "OK", "#27ae60"

    subject = (
        f"[IMDR Daily US] "
        + (f"{fail_n} fail - " if fail_n else "OK - ")
        + f"{n_obs} obs / {n_new} filings ({n_chunks} chunks) ({duration_s/60:.1f} min)"
    )

    def _e(s: object) -> str:
        return _html.escape(str(s or ""))

    _OK = "<span style='color:#27ae60;font-weight:bold;'>OK</span>"
    _FAIL = "<span style='color:#e74c3c;font-weight:bold;'>FAIL</span>"

    def _row_bg(rc: int, i: int) -> str:
        if rc != 0:
            return "#fdecea"
        return "#f0f7ff" if (i % 2) else "#ffffff"

    def _stripe(i: int) -> str:
        return "#f0f7ff" if (i % 2) else "#ffffff"

    rows_pipelines = "".join(
        f"<tr style='background:{_row_bg(p['rc'], i)};'>"
        f"<td style='border:1px solid #ddd;padding:5px;font-family:Consolas,monospace;'>{_e(p['name'])}</td>"
        f"<td style='border:1px solid #ddd;padding:5px;'>{_OK if p['rc'] == 0 else _FAIL}</td>"
        f"<td style='border:1px solid #ddd;padding:5px;text-align:right;font-family:Consolas,monospace;'>{p['elapsed_s']:.1f} s</td>"
        f"<td style='border:1px solid #ddd;padding:5px;text-align:right;font-family:Consolas,monospace;'>{p['rc']}</td>"
        f"</tr>"
        for i, p in enumerate(pipelines)
    )

    if track_a["by_vendor"]:
        rows_track_a = "".join(
            f"<tr style='background:{_stripe(i)};'>"
            f"<td style='border:1px solid #ddd;padding:5px;'>{_e(v['vendor_name'])}</td>"
            f"<td style='border:1px solid #ddd;padding:5px;text-align:right;font-family:Consolas,monospace;'>{v['n_indicators']}</td>"
            f"<td style='border:1px solid #ddd;padding:5px;text-align:right;font-family:Consolas,monospace;'><b>{v['n_obs']}</b></td>"
            f"<td style='border:1px solid #ddd;padding:5px;font-family:Consolas,monospace;'>{_e(v['latest_obs'])}</td>"
            f"</tr>"
            for i, v in enumerate(track_a["by_vendor"])
        )
    else:
        rows_track_a = "<tr><td colspan='4' style='border:1px solid #ddd;padding:8px;color:#888;'>No daily obs ingested this run.</td></tr>"

    if snap["by_vendor"]:
        rows_vendors = "".join(
            f"<tr style='background:{_stripe(i)};'>"
            f"<td style='border:1px solid #ddd;padding:5px;font-family:Consolas,monospace;'>{_e(v['vendor_code'])}</td>"
            f"<td style='border:1px solid #ddd;padding:5px;'>{_e(v['display_name'])}</td>"
            f"<td style='border:1px solid #ddd;padding:5px;color:#555;'>{_e(v['vendor_category'])}</td>"
            f"<td style='border:1px solid #ddd;padding:5px;text-align:right;font-family:Consolas,monospace;'><b>{v['n_reports']}</b></td>"
            f"<td style='border:1px solid #ddd;padding:5px;text-align:right;font-family:Consolas,monospace;'>{v['n_chunks']}</td>"
            f"</tr>"
            for i, v in enumerate(snap["by_vendor"])
        )
    else:
        rows_vendors = "<tr><td colspan='5' style='border:1px solid #ddd;padding:8px;color:#888;'>No new filings this run.</td></tr>"

    if snap["recent"]:
        rows_recent = "".join(
            f"<tr style='background:{_stripe(i)};'>"
            f"<td style='border:1px solid #ddd;padding:5px;font-family:Consolas,monospace;'>{_e(r['vendor_code'])}</td>"
            f"<td style='border:1px solid #ddd;padding:5px;font-family:Consolas,monospace;'>{_e(r['publish_date'])}</td>"
            f"<td style='border:1px solid #ddd;padding:5px;'>{_e(r['title'][:140])}</td>"
            f"</tr>"
            for i, r in enumerate(snap["recent"])
        )
    else:
        rows_recent = "<tr><td colspan='3' style='border:1px solid #ddd;padding:8px;color:#888;'>&mdash;</td></tr>"

    pipelines_summary = (
        f"<span style='color:#27ae60;font-weight:bold;'>{len(pipelines)} OK</span>"
        if fail_n == 0
        else f"<span style='color:#e74c3c;font-weight:bold;'>{fail_n} FAILED</span> / {len(pipelines)} total"
    )
    track_a_summary = (
        f"<span style='color:#27ae60;font-weight:bold;'>{n_obs} new obs</span>"
        if n_obs > 0
        else "<span style='color:#888;'>no new obs</span>"
    )
    track_b_summary = (
        f"<span style='color:#27ae60;font-weight:bold;'>{n_new} new filings / {n_chunks} chunks</span>"
        if n_new > 0
        else "<span style='color:#888;'>no new filings</span>"
    )

    body = f"""<!DOCTYPE html><html><head><meta charset='utf-8'></head>
<body style='margin:0;padding:0;font-family:Calibri,Arial,sans-serif;font-size:14px;color:#222;'>

<!-- HEADER -->
<table width='100%' cellpadding='0' cellspacing='0' style='background-color:#0d2137;'>
  <tr>
    <td style='padding:18px 24px;'>
      <span style='color:#ffffff;font-size:20px;font-weight:bold;'>IMDR &mdash; United States Econ Ingest (Daily)</span>
      <span style='background:{banner_color};color:#fff;padding:4px 12px;border-radius:4px;font-size:13px;font-weight:bold;margin-left:16px;'>{status}</span>
    </td>
  </tr>
  <tr>
    <td style='padding:0 24px 14px 24px;'>
      <span style='color:#7ba4c7;font-size:14px;'>{run_started_at:%Y-%m-%d %H:%M UTC} | scope: Track A (DAILY) + Track B (filings)</span>
    </td>
  </tr>
</table>

<!-- EXECUTION -->
<table width='100%' cellpadding='0' cellspacing='0' style='margin-top:16px;'>
  <tr><td style='padding:0 24px;'><span style='font-size:16px;font-weight:bold;color:#0d2137;'>EXECUTION</span></td></tr>
</table>
<table width='96%' cellpadding='6' cellspacing='0' style='margin:8px auto 0 auto;border-collapse:collapse;border:1px solid #ddd;'>
  <tr style='background:#f5f5f5;'><td style='border:1px solid #ddd;font-weight:bold;width:200px;'>Orchestrator</td><td style='border:1px solid #ddd;font-family:Consolas,monospace;'>scripts.econ.us.us_daily</td></tr>
  <tr><td style='border:1px solid #ddd;font-weight:bold;'>Started</td><td style='border:1px solid #ddd;'>{run_started_at:%Y-%m-%d %H:%M:%S} UTC</td></tr>
  <tr style='background:#f5f5f5;'><td style='border:1px solid #ddd;font-weight:bold;'>Completed</td><td style='border:1px solid #ddd;'>{run_completed_at:%Y-%m-%d %H:%M:%S} UTC</td></tr>
  <tr><td style='border:1px solid #ddd;font-weight:bold;'>Duration</td><td style='border:1px solid #ddd;'>{duration_s/60:.1f} min</td></tr>
  <tr style='background:#f5f5f5;'><td style='border:1px solid #ddd;font-weight:bold;'>Pipelines</td>
    <td style='border:1px solid #ddd;'>{pipelines_summary}</td>
  </tr>
  <tr><td style='border:1px solid #ddd;font-weight:bold;'>Track A (data series)</td>
    <td style='border:1px solid #ddd;'>{track_a_summary}</td>
  </tr>
  <tr style='background:#f5f5f5;'><td style='border:1px solid #ddd;font-weight:bold;'>Track B (filings)</td>
    <td style='border:1px solid #ddd;'>{track_b_summary}</td>
  </tr>
</table>

<!-- PIPELINES -->
<table width='100%' cellpadding='0' cellspacing='0' style='margin-top:20px;'>
  <tr><td style='padding:0 24px;'><span style='font-size:16px;font-weight:bold;color:#0d2137;'>FETCHER PIPELINES ({len(pipelines)})</span></td></tr>
</table>
<table width='96%' cellpadding='5' cellspacing='0' style='margin:8px auto 0 auto;border-collapse:collapse;border:1px solid #ddd;font-size:13px;'>
  <tr style='background:#0d2137;color:#fff;'>
    <th style='border:1px solid #555;padding:6px;text-align:left;'>Pipeline</th>
    <th style='border:1px solid #555;padding:6px;text-align:left;'>Status</th>
    <th style='border:1px solid #555;padding:6px;text-align:right;'>Elapsed</th>
    <th style='border:1px solid #555;padding:6px;text-align:right;'>RC</th>
  </tr>
  {rows_pipelines}
</table>

<!-- TRACK A -->
<table width='100%' cellpadding='0' cellspacing='0' style='margin-top:20px;'>
  <tr><td style='padding:0 24px;'><span style='font-size:16px;font-weight:bold;color:#0d2137;'>TRACK A &mdash; DAILY INDICATORS</span>
  <span style='font-size:12px;color:#666;margin-left:8px;'>obs ingested this run, grouped by vendor</span></td></tr>
</table>
<table width='96%' cellpadding='5' cellspacing='0' style='margin:8px auto 0 auto;border-collapse:collapse;border:1px solid #ddd;font-size:13px;'>
  <tr style='background:#0d2137;color:#fff;'>
    <th style='border:1px solid #555;padding:6px;text-align:left;'>Vendor</th>
    <th style='border:1px solid #555;padding:6px;text-align:right;'>Indicators</th>
    <th style='border:1px solid #555;padding:6px;text-align:right;'>New obs</th>
    <th style='border:1px solid #555;padding:6px;text-align:left;'>Latest obs_date</th>
  </tr>
  {rows_track_a}
</table>

<!-- TRACK B -->
<table width='100%' cellpadding='0' cellspacing='0' style='margin-top:20px;'>
  <tr><td style='padding:0 24px;'><span style='font-size:16px;font-weight:bold;color:#0d2137;'>TRACK B &mdash; FILINGS BY VENDOR</span>
  <span style='font-size:12px;color:#666;margin-left:8px;'>research.dim_report + research.fact_chunk + Qdrant + SharePoint</span></td></tr>
</table>
<table width='96%' cellpadding='5' cellspacing='0' style='margin:8px auto 0 auto;border-collapse:collapse;border:1px solid #ddd;font-size:13px;'>
  <tr style='background:#0d2137;color:#fff;'>
    <th style='border:1px solid #555;padding:6px;text-align:left;'>Code</th>
    <th style='border:1px solid #555;padding:6px;text-align:left;'>Vendor</th>
    <th style='border:1px solid #555;padding:6px;text-align:left;'>Category</th>
    <th style='border:1px solid #555;padding:6px;text-align:right;'>Reports</th>
    <th style='border:1px solid #555;padding:6px;text-align:right;'>Chunks</th>
  </tr>
  {rows_vendors}
</table>

<!-- RECENT FILINGS -->
<table width='100%' cellpadding='0' cellspacing='0' style='margin-top:20px;'>
  <tr><td style='padding:0 24px;'><span style='font-size:16px;font-weight:bold;color:#0d2137;'>MOST RECENT FILINGS (top 5)</span></td></tr>
</table>
<table width='96%' cellpadding='5' cellspacing='0' style='margin:8px auto 0 auto;border-collapse:collapse;border:1px solid #ddd;font-size:13px;'>
  <tr style='background:#0d2137;color:#fff;'>
    <th style='border:1px solid #555;padding:6px;text-align:left;'>Code</th>
    <th style='border:1px solid #555;padding:6px;text-align:left;'>Publish date</th>
    <th style='border:1px solid #555;padding:6px;text-align:left;'>Title</th>
  </tr>
  {rows_recent}
</table>

<!-- FOOTER -->
<table width='100%' cellpadding='0' cellspacing='0' style='margin-top:24px;background-color:#f0f0f0;border-top:2px solid #ddd;'>
  <tr><td style='padding:12px 24px;color:#888;font-size:12px;'>
    Generated by IMDR | scripts.econ.us.us_daily | {run_completed_at:%Y-%m-%d %H:%M:%S} UTC |
    data: econ.fact_indicator + research.dim_report + research.fact_chunk
  </td></tr>
</table>

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
        # Display name = the `-m` module token (not the last arg, which for the
        # Track B pipeline is the bare "7" of `--since-days 7`).
        name = cmd[cmd.index("-m") + 1] if "-m" in cmd else cmd[-1]
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

    snap: dict = {"by_vendor": [], "total_reports": 0, "total_chunks": 0, "recent": []}
    track_a: dict = {"by_vendor": [], "total_obs": 0}

    try:
        snap = _filings_snapshot(run_started_at)
        log.info("us_daily_filings_snapshot",
                 new_reports=snap["total_reports"], new_chunks=snap["total_chunks"],
                 vendors_with_activity=len(snap["by_vendor"]))
    except Exception:
        log.exception("us_daily_filings_snapshot_failed")
        print(f"\n!! filings snapshot failed:\n{traceback.format_exc()}")

    try:
        track_a = _track_a_snapshot(run_started_at)
        log.info("us_daily_track_a_snapshot",
                 new_obs=track_a["total_obs"], vendors_with_activity=len(track_a["by_vendor"]))
    except Exception:
        log.exception("us_daily_track_a_snapshot_failed")
        print(f"\n!! Track A snapshot failed:\n{traceback.format_exc()}")

    if (not args.no_email
            and getattr(settings, "email_enabled", False)
            and getattr(settings, "email_to", "")):
        try:
            subject, body = _render_email(
                run_started_at=run_started_at,
                run_completed_at=run_completed_at,
                duration_s=duration_s,
                pipelines=pipeline_results,
                failed=failed,
                snap=snap,
                track_a=track_a,
            )
            send_outlook_email(
                to=settings.email_to,
                subject=subject,
                html_body=body,
                importance=2 if failed else 1,
            )
        except Exception:
            log.exception("us_daily_email_failed")
            print(f"\n!! email render/send failed:\n{traceback.format_exc()}")
    elif args.no_email:
        print("\n(email skipped by --no-email)")
    else:
        log.info("email_disabled_skipping_us_daily_summary")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
