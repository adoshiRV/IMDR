"""Indonesia econ — DAILY orchestrator.

Mirror of `scripts/econ/au/au_daily.py` / `scripts/econ/kr/kr_daily.py`.
Runs every fetcher that produces ID data at daily cadence:

  Track A — daily data series (both were already daily-registered):
    - scripts.econ.id.bis.bis_indonesia   (BIS policy rate + NEER/REER/DSR)
    - scripts.econ.id.bi.bi_srbi          (SRBI 6M/9M/12M auction yields)

  Track B — govt filings (Phase J, new 2026-09-21):
    - scripts.econ.id.govt.ingest_filings --ingest
      BI / BPS / DJPPR / OJK into `research.dim_report` +
      `research.fact_chunk` + Qdrant + SharePoint via
      `imdr.research.filings.ingest_filing`.

Email composes both sides: Track A indicator counts from
`econ.fact_indicator`, Track B filings from `research.dim_report`.

> ## ⚠️ Registering this REPLACES two existing entries
>
> `scripts/imdr_daily.py:PIPELINES` today registers
> `scripts.econ.id.bis.bis_indonesia` and `scripts.econ.id.bi.bi_srbi`
> **individually**. Both are in this orchestrator's PIPELINES, so adding
> `scripts.econ.id.id_daily` without removing those two would run them
> twice per day. The loads are idempotent MERGEs so the data would survive,
> but it doubles the Citi-free-but-not-free fetch traffic and makes the
> daily email double-count ID. Registration is a separate gate — see
> `docs/admin/econ/econ_to_prod.md` § J.4 step 4.

Usage:
    python -m scripts.econ.id.id_daily
    python -m scripts.econ.id.id_daily --no-email
    python -m scripts.econ.id.id_daily --track-b-only
"""
from __future__ import annotations

import argparse
import datetime
import html as _html
import io
import sys
import traceback

# Force UTF-8 stdout — Indonesian titles and em-dashes come through
# subprocess output.
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import structlog  # noqa: E402

from imdr.config.settings import get_settings  # noqa: E402
from imdr.notifications.email import send_outlook_email  # noqa: E402
from imdr.utils.logging import configure_logging  # noqa: E402
from scripts.econ._daily_snapshots import (  # noqa: E402
    filings_snapshot,
    run_pipelines,
    track_a_snapshot,
)

log = structlog.get_logger(__name__)


# ============================================================================
# REGISTERED PIPELINES — extend as new ID daily fetchers land
# ============================================================================

TRACK_A_PIPELINES: list[list[str]] = [
    [sys.executable, "-m", "scripts.econ.id.bis.bis_indonesia"],
    [sys.executable, "-m", "scripts.econ.id.bi.bi_srbi"],
]

TRACK_B_PIPELINES: list[list[str]] = [
    [sys.executable, "-m", "scripts.econ.id.govt.ingest_filings", "--ingest"],
]

PIPELINES: list[list[str]] = TRACK_A_PIPELINES + TRACK_B_PIPELINES

# ID has no daily Track A series outside these two feeds; everything else is
# monthly (`id_monthly.py`). Scoping the Track A snapshot to DAILY keeps the
# monthly orchestrator's loads out of this email.
_TRACK_A_FREQUENCIES = ["DAILY"]

COUNTRY_CODE = "ID"


def _render_email(
    *,
    run_started_at: datetime.datetime,
    pipeline_results: dict,
    track_a: dict,
    track_b: dict,
) -> tuple[str, str]:
    """Return `(subject, html_body)`."""
    n_failed = len(pipeline_results.get("failed", []))
    subject = (
        f"[IMDR] Indonesia daily — {track_a.get('total_obs', 0)} obs, "
        f"{track_b.get('total_reports', 0)} filings"
        + (f" — {n_failed} FAILED" if n_failed else "")
    )

    def esc(x) -> str:
        return _html.escape(str(x))

    rows = []
    for r in pipeline_results.get("results", []):
        ok = r.get("returncode") == 0
        rows.append(
            f"<tr><td>{esc(r.get('name', ''))}</td>"
            f"<td style='color:{'#137333' if ok else '#c5221f'}'>"
            f"{'ok' if ok else 'FAILED'}</td>"
            f"<td align='right'>{esc(r.get('duration_s', ''))}s</td></tr>"
        )
    pipelines_html = "".join(rows) or "<tr><td colspan='3'>none</td></tr>"

    a_rows = "".join(
        f"<tr><td>{esc(v['vendor_name'])}</td>"
        f"<td align='right'>{esc(v['n_indicators'])}</td>"
        f"<td align='right'>{esc(v['n_obs'])}</td>"
        f"<td>{esc(v['latest_obs'])}</td></tr>"
        for v in track_a.get("by_vendor", [])
    ) or "<tr><td colspan='4'>no new daily observations</td></tr>"

    b_rows = "".join(
        f"<tr><td>{esc(v['vendor_code'])}</td>"
        f"<td>{esc(v['display_name'])}</td>"
        f"<td>{esc(v['vendor_category'])}</td>"
        f"<td align='right'>{esc(v['n_reports'])}</td>"
        f"<td align='right'>{esc(v['n_chunks'])}</td></tr>"
        for v in track_b.get("by_vendor", [])
    ) or "<tr><td colspan='5'>no new filings</td></tr>"

    recent = "".join(
        f"<li><b>{esc(r['vendor_code'])}</b> {esc(r['publish_date'])} — "
        f"{esc(r['title'][:120])}</li>"
        for r in track_b.get("recent", [])
    )
    recent_html = f"<ul>{recent}</ul>" if recent else ""

    th = "style='text-align:left;background:#f1f3f4;padding:4px 8px'"
    td = "style='padding:3px 8px;border-top:1px solid #e0e0e0'"
    body = f"""
    <div style="font-family:Segoe UI,Arial,sans-serif;font-size:13px">
      <h2 style="margin-bottom:2px">Indonesia econ — daily</h2>
      <div style="color:#5f6368">run started {esc(run_started_at)}</div>

      <h3>Pipelines</h3>
      <table cellspacing="0" {td}>
        <tr><th {th}>pipeline</th><th {th}>status</th><th {th}>time</th></tr>
        {pipelines_html}
      </table>

      <h3>Track A — new daily observations</h3>
      <table cellspacing="0" {td}>
        <tr><th {th}>vendor</th><th {th}>indicators</th><th {th}>obs</th>
            <th {th}>latest obs</th></tr>
        {a_rows}
      </table>

      <h3>Track B — filings ingested</h3>
      <table cellspacing="0" {td}>
        <tr><th {th}>vendor</th><th {th}>name</th><th {th}>category</th>
            <th {th}>reports</th><th {th}>chunks</th></tr>
        {b_rows}
      </table>
      {recent_html}

      <p style="color:#5f6368;font-size:12px">
        MoF (Kemenkeu) is a known blocker and is expected to report
        <code>ok=NO</code> every run — Angular SPA, no discoverable API, and
        the browser route is blocked by the corp firewall. See
        docs/admin/econ/indonesia/id_govt_doc_sources.md &sect;2.
      </p>
    </div>
    """
    return subject, body


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-email", action="store_true",
                        help="run pipelines + print snapshots, send no email")
    parser.add_argument("--track-b-only", action="store_true",
                        help="skip the Track A series feeds (filings only)")
    parser.add_argument("--track-a-only", action="store_true",
                        help="skip the govt-filings ingest (series only)")
    args = parser.parse_args(argv)

    if args.track_a_only and args.track_b_only:
        parser.error("--track-a-only and --track-b-only are mutually exclusive")

    settings = get_settings()
    configure_logging(settings)
    run_started_at = datetime.datetime.now(datetime.UTC)

    pipelines = PIPELINES
    if args.track_a_only:
        pipelines = TRACK_A_PIPELINES
    elif args.track_b_only:
        pipelines = TRACK_B_PIPELINES

    log.info("id_daily.start", n_pipelines=len(pipelines))
    pipeline_results = run_pipelines(pipelines)

    # Snapshots are best-effort: a DB hiccup must not mask a successful run,
    # and must not suppress the email that reports the pipeline failures.
    track_a: dict = {}
    track_b: dict = {}
    try:
        track_a = track_a_snapshot(
            run_started_at, COUNTRY_CODE, _TRACK_A_FREQUENCIES
        )
    except Exception:
        log.warning("id_daily.track_a_snapshot_failed", exc_info=True)
        traceback.print_exc()
    try:
        # official_only=True: every ID Track B vendor is official_*, unlike
        # AU which also ingests sell-side through the same Phase-J path.
        track_b = filings_snapshot(run_started_at, COUNTRY_CODE, official_only=True)
    except Exception:
        log.warning("id_daily.filings_snapshot_failed", exc_info=True)
        traceback.print_exc()

    print(f"\nTrack A — {track_a.get('total_obs', 0)} new daily obs")
    for v in track_a.get("by_vendor", []):
        print(f"  {v['vendor_name']:<46} {v['n_indicators']:>4} ind "
              f"{v['n_obs']:>7} obs  latest={v['latest_obs']}")
    print(f"\nTrack B — {track_b.get('total_reports', 0)} filings, "
          f"{track_b.get('total_chunks', 0)} chunks")
    for v in track_b.get("by_vendor", []):
        print(f"  {v['vendor_code']:<10} {v['vendor_category']:<22} "
              f"{v['n_reports']:>4} reports {v['n_chunks']:>6} chunks")

    failed = pipeline_results.get("failed", [])

    if (
        not args.no_email
        and getattr(settings, "email_enabled", False)
        and getattr(settings, "email_to", "")
    ):
        try:
            subject, body = _render_email(
                run_started_at=run_started_at,
                pipeline_results=pipeline_results,
                track_a=track_a,
                track_b=track_b,
            )
            send_outlook_email(
                to=settings.email_to,
                subject=subject,
                html_body=body,
                importance=2 if failed else 1,
            )
            log.info("id_daily_email_sent", subject=subject)
        except Exception:
            log.exception("id_daily_email_failed")
            print(f"\n!! email render/send failed:\n{traceback.format_exc()}")
    elif args.no_email:
        print("\n(email skipped by --no-email)")
    else:
        log.info("email_disabled_skipping_id_daily_summary")

    if failed:
        log.error("id_daily.done_with_failures", failed=failed)
        return 1
    log.info("id_daily.done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
