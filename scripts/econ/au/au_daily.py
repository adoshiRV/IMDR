"""Australia econ — DAILY orchestrator.

Mirror of `scripts/econ/kr/kr_daily.py`. Runs every fetcher /
sub-orchestrator that produces AU data at daily cadence:

  Track A — daily data series:
    - scripts.econ.au.rba.rba_snapshot_refresh --daily-only   (refresh F1/F2/F11.1 CSVs)
    - scripts.econ.au.rba.rba_rates       (cash + BBSW + OIS + AGB yields)
    - scripts.econ.au.rba.rba_fx          (AUD crosses + TWI)
    - scripts.econ.au.rba.rba_zerocoupon  (F17 yields + forwards)
    - scripts.econ.au.cotality.cotality_hvi   (5 capitals + aggregate)

  Track B — govt filings:
    - scripts.econ.au.govt.ingest_filings  — RBA/Treasury/APRA/ABS into
      ``research.dim_report`` + ``research.fact_chunk`` + Qdrant +
      SharePoint via ``imdr.research.filings.ingest_filing``.

Email composes BOTH sides (Track A indicator counts via ``econ.fact_indicator``
+ Track B filings via ``research.dim_report``) plus a ``[Cotality gap]`` banner
when fewer than 6 HVI series have an obs for today.

Scheduler-side registration in ``scripts/imdr_daily.py:PIPELINES`` is a
separate gate.

Usage:
    python -m scripts.econ.au.au_daily
    python -m scripts.econ.au.au_daily --no-email
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

# Force UTF-8 stdout — em-dashes / Western titles come through subprocess output.
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
# REGISTERED PIPELINES — extend as new AU daily fetchers land
# ============================================================================

PIPELINES: list[list[str]] = [
    # Track A — refresh RBA daily CSVs first, then load
    [sys.executable, "-m", "scripts.econ.au.rba.rba_snapshot_refresh", "--daily-only"],
    [sys.executable, "-m", "scripts.econ.au.rba.rba_rates"],
    [sys.executable, "-m", "scripts.econ.au.rba.rba_fx"],
    [sys.executable, "-m", "scripts.econ.au.rba.rba_zerocoupon"],
    [sys.executable, "-m", "scripts.econ.au.cotality.cotality_hvi"],
    # Track B — govt filings ingest (Phase J)
    [sys.executable, "-m", "scripts.econ.au.govt.ingest_filings", "--ingest"],
]


_COTALITY_EXPECTED_SERIES = 6  # 5 capitals + 5-capital aggregate


def _engine():
    """Engine for the post-run filings snapshot. ODBC Driver 18 because
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


def _track_a_snapshot(run_started_at: datetime.datetime) -> dict:
    """Pull stats on AU DAILY indicators ingested at/after run_started_at.

    Scopes to ``frequency='DAILY'`` so the monthly orchestrator's own
    snapshot doesn't double-count. Returns by-vendor counts + the most
    recent obs per indicator.
    """
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
                    WHERE  c.country_code = 'AU'
                      AND  fq.frequency_code = 'DAILY'
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
            {
                "vendor_name": vn,
                "n_indicators": int(ni),
                "n_obs": int(no),
                "latest_obs": str(lo),
            }
            for vn, ni, no, lo in by_vendor
        ],
        "total_obs": int(total_obs),
    }


def _cotality_today_check() -> dict:
    """Sanity: did Cotality HVI capture today's value for all 6 series?

    Cotality publishes only today's value on the page — missed runs leave
    a permanent gap in the time series. Banner surfaces when n<6.
    """
    today = datetime.date.today()
    eng = _engine()
    try:
        with eng.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT COUNT(*) AS n
                    FROM   econ.fact_indicator f
                    JOIN   econ.dim_indicator i ON i.id = f.indicator_id
                    WHERE  i.imdr_code LIKE 'COTALITY.HVI.%'
                      AND  f.obs_date = :d
                    """
                ),
                {"d": today},
            ).first()
    finally:
        eng.dispose()
    n = int(row.n) if row else 0
    return {
        "date": today.isoformat(),
        "n_series_with_today": n,
        "expected": _COTALITY_EXPECTED_SERIES,
        "ok": n >= _COTALITY_EXPECTED_SERIES,
    }


def _filings_snapshot(run_started_at: datetime.datetime) -> dict:
    """Pull stats on AU filings ingested at/after run_started_at.

    Includes both `official_*` vendor categories (rba, treasury_au, apra,
    abs) AND `sell_side` AU vendors (westpac, nab) since those are still
    AU-country filings ingested through the same Phase J path.
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
                    WHERE r.country_id = (SELECT id FROM dbo.dim_country WHERE country_code = 'AU')
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
                    WHERE r.country_id = (SELECT id FROM dbo.dim_country WHERE country_code = 'AU')
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
    track_a: dict,
    cotality: dict,
) -> tuple[str, str]:
    n_new = snap["total_reports"]
    n_chunks = snap["total_chunks"]
    n_obs = track_a["total_obs"]
    fail_n = len(failed)
    cotality_gap = not cotality.get("ok", True)

    # Status badge (matches Korea palette: green/orange/red).
    if fail_n > 1:
        status, banner_color = "FAIL", "#e74c3c"
    elif fail_n == 1 or cotality_gap:
        status, banner_color = "PARTIAL", "#f39c12"
    else:
        status, banner_color = "OK", "#27ae60"

    prefix_bits: list[str] = []
    if cotality_gap:
        prefix_bits.append("[Cotality gap]")
    if fail_n:
        prefix_bits.append(f"{fail_n} fail")
    subject_status = " ".join(prefix_bits) or "OK"
    subject = (
        f"[IMDR Daily AU] {subject_status} - {n_obs} obs / "
        f"{n_new} filings ({n_chunks} chunks) ({duration_s/60:.1f} min)"
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
        rows_track_a = "<tr><td colspan='4' style='border:1px solid #ddd;padding:8px;color:#888;'>No daily obs ingested this run (everything already at latest vintage).</td></tr>"

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

    # Pre-compute conditional spans so we don't nest quotes inside f-strings
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

    cotality_banner = ""
    if cotality_gap:
        cotality_banner = (
            "<table width='96%' cellpadding='0' cellspacing='0' style='margin:14px auto 0 auto;'>"
            "<tr><td style='background:#fff3cd;border-left:4px solid #f39c12;padding:10px 14px;'>"
            "<b style='color:#7c5b00;'>[Cotality gap]</b> "
            f"Only <b>{cotality['n_series_with_today']}/{cotality['expected']}</b> HVI series "
            f"have an obs for <code>{_e(cotality['date'])}</code>. "
            "Re-run <code>scripts.econ.au.cotality.cotality_hvi</code> to catch up "
            "(source page serves today's value; idempotent MERGE recovers)."
            "</td></tr></table>"
        )

    body = f"""<!DOCTYPE html><html><head><meta charset='utf-8'></head>
<body style='margin:0;padding:0;font-family:Calibri,Arial,sans-serif;font-size:14px;color:#222;'>

<!-- HEADER -->
<table width='100%' cellpadding='0' cellspacing='0' style='background-color:#0d2137;'>
  <tr>
    <td style='padding:18px 24px;'>
      <span style='color:#ffffff;font-size:20px;font-weight:bold;'>IMDR &mdash; Australia Econ Ingest (Daily)</span>
      <span style='background:{banner_color};color:#fff;padding:4px 12px;border-radius:4px;font-size:13px;font-weight:bold;margin-left:16px;'>{status}</span>
    </td>
  </tr>
  <tr>
    <td style='padding:0 24px 14px 24px;'>
      <span style='color:#7ba4c7;font-size:14px;'>{run_started_at:%Y-%m-%d %H:%M UTC} | scope: Track A (DAILY) + Track B (filings)</span>
    </td>
  </tr>
</table>

{cotality_banner}

<!-- EXECUTION -->
<table width='100%' cellpadding='0' cellspacing='0' style='margin-top:16px;'>
  <tr><td style='padding:0 24px;'><span style='font-size:16px;font-weight:bold;color:#0d2137;'>EXECUTION</span></td></tr>
</table>
<table width='96%' cellpadding='6' cellspacing='0' style='margin:8px auto 0 auto;border-collapse:collapse;border:1px solid #ddd;'>
  <tr style='background:#f5f5f5;'><td style='border:1px solid #ddd;font-weight:bold;width:200px;'>Orchestrator</td><td style='border:1px solid #ddd;font-family:Consolas,monospace;'>scripts.econ.au.au_daily</td></tr>
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
    Generated by IMDR | scripts.econ.au.au_daily | {run_completed_at:%Y-%m-%d %H:%M:%S} UTC |
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

    # --- Snapshots: Track A (DAILY indicators) + Track B (filings) + Cotality check ---
    snap: dict = {"by_vendor": [], "total_reports": 0, "total_chunks": 0, "recent": []}
    track_a: dict = {"by_vendor": [], "total_obs": 0}
    cotality: dict = {
        "date": datetime.date.today().isoformat(),
        "n_series_with_today": 0,
        "expected": _COTALITY_EXPECTED_SERIES,
        "ok": True,  # default ok so a snapshot failure doesn't shout
    }
    try:
        snap = _filings_snapshot(run_started_at)
        log.info(
            "au_daily_filings_snapshot",
            new_reports=snap["total_reports"],
            new_chunks=snap["total_chunks"],
            vendors_with_activity=len(snap["by_vendor"]),
        )
    except Exception:
        log.exception("au_daily_filings_snapshot_failed")
        print(f"\n!! filings snapshot failed:\n{traceback.format_exc()}")

    try:
        track_a = _track_a_snapshot(run_started_at)
        log.info(
            "au_daily_track_a_snapshot",
            new_obs=track_a["total_obs"],
            vendors_with_activity=len(track_a["by_vendor"]),
        )
    except Exception:
        log.exception("au_daily_track_a_snapshot_failed")
        print(f"\n!! Track A snapshot failed:\n{traceback.format_exc()}")

    try:
        cotality = _cotality_today_check()
        if not cotality["ok"]:
            print(
                f"\n[Cotality gap] only {cotality['n_series_with_today']}/"
                f"{cotality['expected']} HVI series have {cotality['date']} obs"
            )
        log.info("au_daily_cotality_check", **cotality)
    except Exception:
        log.exception("au_daily_cotality_check_failed")
        print(f"\n!! Cotality check failed:\n{traceback.format_exc()}")

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
                track_a=track_a,
                cotality=cotality,
            )
            send_outlook_email(
                to=settings.email_to,
                subject=subject,
                html_body=body,
                importance=2 if failed else 1,
            )
        except Exception:
            log.exception("au_daily_email_failed")
            print(f"\n!! email render/send failed:\n{traceback.format_exc()}")
    elif args.no_email:
        print("\n(email skipped by --no-email)")
    else:
        log.info("email_disabled_skipping_au_daily_summary")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
