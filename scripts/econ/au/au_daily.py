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
                    SELECT v.vendor_name,
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
                    GROUP BY v.vendor_name
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

    prefix_bits: list[str] = []
    if cotality_gap:
        prefix_bits.append("[Cotality gap]")
    if fail_n:
        prefix_bits.append(f"⚠ {fail_n} failed")
    elif not prefix_bits:
        prefix_bits.append("✓ all ok")
    status = " ".join(prefix_bits)

    subject = (
        f"[IMDR Daily AU] {status} — {n_obs} obs / {n_new} filings ({n_chunks} chunks) "
        f"({duration_s/60:.1f} min)"
    )

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

    rows_track_a = "\n".join(
        f"<tr><td>{_e(v['vendor_name'])}</td>"
        f"<td style='text-align:right'>{v['n_indicators']}</td>"
        f"<td style='text-align:right'>{v['n_obs']}</td>"
        f"<td>{_e(v['latest_obs'])}</td></tr>"
        for v in track_a["by_vendor"]
    ) or "<tr><td colspan='4' style='color:#888'>no daily obs ingested this run</td></tr>"

    cotality_banner = ""
    if cotality_gap:
        cotality_banner = (
            f"<div style='background:#fff3cd;border:1px solid #ffe082;padding:8px 12px;"
            f"margin:8px 0;border-radius:4px;'><b>[Cotality gap]</b> "
            f"Only {cotality['n_series_with_today']}/{cotality['expected']} HVI series "
            f"have an observation for {_e(cotality['date'])}. "
            f"Re-run <code>scripts.econ.au.cotality.cotality_hvi</code> to catch up "
            f"(the source page still serves today's value; idempotent MERGE recovers).</div>"
        )

    css = (
        "body{font-family:Segoe UI,Arial,sans-serif;font-size:13px;}"
        "table{border-collapse:collapse;margin:8px 0;}"
        "th,td{border:1px solid #ddd;padding:4px 8px;}"
        "th{background:#f4f4f4;text-align:left;}"
        ".meta{color:#666;margin-top:12px;font-size:11px;}"
    )

    body = f"""<!doctype html><html><head><style>{css}</style></head><body>
<h3>IMDR AU Daily — Track A (data series) + Track B (filings)</h3>
<p>Started {run_started_at:%Y-%m-%d %H:%M UTC} · finished {run_completed_at:%H:%M UTC} ·
duration {duration_s/60:.1f} min · {n_obs} daily obs · {n_new} new filings / {n_chunks} chunks ·
{fail_n} pipeline(s) failed</p>

{cotality_banner}

<h4>Pipelines</h4>
<table><thead><tr><th>name</th><th>rc</th><th>elapsed</th></tr></thead>
<tbody>{rows_pipelines}</tbody></table>

<h4>Track A — daily indicators ingested this run</h4>
<table><thead><tr><th>vendor</th>
<th style='text-align:right'>indicators</th>
<th style='text-align:right'>obs</th>
<th>latest obs_date</th></tr></thead>
<tbody>{rows_track_a}</tbody></table>

<h4>Track B — filings ingested by vendor</h4>
<table><thead><tr><th>code</th><th>vendor</th><th>category</th>
<th style='text-align:right'>reports</th><th style='text-align:right'>chunks</th></tr></thead>
<tbody>{rows_vendors}</tbody></table>

<h4>Most recent filings (top 5)</h4>
<table><thead><tr><th>code</th><th>date</th><th>title</th></tr></thead>
<tbody>{rows_recent}</tbody></table>

<p class="meta">Orchestrator: <code>scripts.econ.au.au_daily</code>.
Pipeline detail: <code>data/econ/au/govt/_last_run.log</code> on the host.</p>
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
