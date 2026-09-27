"""Korea econ — DAILY orchestrator (dual-track).

Runs every fetcher / sub-orchestrator that produces KR data at daily
cadence:

  Track A (indicators → ``econ.fact_indicator``):
  - scripts.econ.kr.kofia.kofia_cd_trading  — CD secondary-market volume
  - scripts.econ.kr.kofia.kofia_mmf_flows   — MMF daily subscriptions/redemptions/net
  - scripts.econ.kr.kofia.kofia_mmf_level   — MMF net assets / setup principal (latest snapshot)
  - scripts.econ.kr.ksd.ksd_cd_issuance     — CD primary issuance (volume/count/rate) + outstanding

  Track B (documents → ``research.dim_report`` + Qdrant + SharePoint):
  - scripts.econ.kr.govt.ingest_filings     — govt policy filings (BoK, MOEF,
    MOTIR, FSC, FSS, KCS, KDI, MoDS) via ``imdr.research.filings.ingest_filing``.

The KOFIA Track-A fetchers run in *live* mode (no ``--since``): CD + flows
re-pull a rolling ~90-day window (idempotent MERGE skips existing rows) and
MMF-level appends the latest business-day snapshot, so the daily level series
accumulates going forward. Historical backfill is a separate one-off
(``--since``), not part of the daily loop.

Future daily components extend ``PIPELINES`` below. Shape identical to
``kr_weekly.py`` / ``kr_monthly.py`` — one subprocess per fetcher, isolated so
a single failure doesn't block the rest. The email reports BOTH a Track-A
indicator snapshot (``track_a_snapshot``, scoped to DAILY) and a Track-B
filings snapshot (``filings_snapshot``).

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
import sys
import traceback

# Force UTF-8 stdout — Korean titles + bullets come through subprocess output.
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import structlog

from imdr.config.settings import get_settings
from imdr.notifications.email import send_outlook_email
from imdr.utils.logging import configure_logging
from scripts.econ._daily_snapshots import (
    filings_snapshot,
    run_pipelines,
    track_a_snapshot,
)

log = structlog.get_logger(__name__)


# ============================================================================
# REGISTERED PIPELINES — extend this list as new KR daily fetchers are added
# ============================================================================

PIPELINES: list[list[str]] = [
    # Track A — KOFIA money-market + fund indicators (live mode: no --since)
    [sys.executable, "-m", "scripts.econ.kr.kofia.kofia_cd_trading"],
    [sys.executable, "-m", "scripts.econ.kr.kofia.kofia_cd_yield"],
    [sys.executable, "-m", "scripts.econ.kr.kofia.kofia_mmf_flows"],
    [sys.executable, "-m", "scripts.econ.kr.kofia.kofia_mmf_level"],
    [sys.executable, "-m", "scripts.econ.kr.kofia.kofia_fund_aum"],
    [sys.executable, "-m", "scripts.econ.kr.ksd.ksd_cd_issuance"],
    # Track B — government policy filings
    [sys.executable, "-m", "scripts.econ.kr.govt.ingest_filings", "--ingest"],
]

# Track-A frequency scope for the post-run indicator snapshot (KOFIA = DAILY).
_TRACK_A_FREQ = ["DAILY"]

# ============================================================================


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
    """Render (subject, html_body) for the daily KR email."""
    n_new = snap["total_reports"]
    n_chunks = snap["total_chunks"]
    n_obs = track_a["total_obs"]
    fail_n = len(failed)
    status = "✓ all ok" if fail_n == 0 else f"⚠ {fail_n} failed"
    subject = (
        f"[IMDR Daily KR] {status} — {n_obs} econ obs, {n_new} new filings, "
        f"{n_chunks} chunks ({duration_s/60:.1f} min)"
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
    rows_track_a = "\n".join(
        f"<tr><td>{_e(v['vendor_name'])}</td>"
        f"<td style='text-align:right'>{v['n_indicators']}</td>"
        f"<td style='text-align:right'>{v['n_obs']}</td>"
        f"<td>{_e(v['latest_obs'])}</td></tr>"
        for v in track_a["by_vendor"]
    ) or "<tr><td colspan='4' style='color:#888'>no new indicator obs</td></tr>"

    css = (
        "body{font-family:Segoe UI,Arial,sans-serif;font-size:13px;}"
        "table{border-collapse:collapse;margin:8px 0;}"
        "th,td{border:1px solid #ddd;padding:4px 8px;}"
        "th{background:#f4f4f4;text-align:left;}"
        ".meta{color:#666;margin-top:12px;font-size:11px;}"
    )

    body = f"""<!doctype html><html><head><style>{css}</style></head><body>
<h3>IMDR KR Daily — econ indicators + government filings</h3>
<p>Started {run_started_at:%Y-%m-%d %H:%M UTC} · finished {run_completed_at:%H:%M UTC} ·
duration {duration_s/60:.1f} min · {n_obs} new econ obs · {n_new} new filings /
{n_chunks} chunks · {fail_n} pipeline(s) failed</p>

<h4>Pipelines</h4>
<table><thead><tr><th>name</th><th>rc</th><th>elapsed</th></tr></thead>
<tbody>{rows_pipelines}</tbody></table>

<h4>Track A — indicator obs ingested (DAILY scope)</h4>
<table><thead><tr><th>vendor</th><th style='text-align:right'>indicators</th>
<th style='text-align:right'>new obs</th><th>latest obs</th></tr></thead>
<tbody>{rows_track_a}</tbody></table>

<h4>Filings ingested by vendor</h4>
<table><thead><tr><th>code</th><th>vendor</th><th>category</th>
<th style='text-align:right'>reports</th><th style='text-align:right'>chunks</th></tr></thead>
<tbody>{rows_vendors}</tbody></table>

<h4>Most recent (top 5)</h4>
<table><thead><tr><th>code</th><th>date</th><th>title</th></tr></thead>
<tbody>{rows_recent}</tbody></table>

<p class="meta">Orchestrator: <code>scripts.econ.kr.kr_daily</code>.
Pipeline detail: <code>data/econ/kr/govt/_last_run.log</code> on the host.</p>
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

    run = run_pipelines(PIPELINES)
    pipeline_results = run["results"]
    failed = run["failed"]
    duration_s = run["duration_s"]
    run_started_at = run["started_at"]
    run_completed_at = run["completed_at"]

    # --- Track A + Track B snapshots + email ------------------------------
    track_a: dict = {"by_vendor": [], "total_obs": 0}
    try:
        track_a = track_a_snapshot(run_started_at, "KR", _TRACK_A_FREQ)
        log.info(
            "kr_daily_track_a_snapshot",
            new_obs=track_a["total_obs"],
            vendors_with_activity=len(track_a["by_vendor"]),
        )
    except Exception:
        log.exception("kr_daily_track_a_snapshot_failed")
        print(f"\n!! track-a snapshot failed:\n{traceback.format_exc()}")

    snap: dict = {"by_vendor": [], "total_reports": 0, "total_chunks": 0, "recent": []}
    try:
        snap = filings_snapshot(run_started_at, "KR")
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
                track_a=track_a,
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
