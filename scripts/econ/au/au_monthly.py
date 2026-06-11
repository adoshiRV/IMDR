"""Australia econ — MONTHLY+QUARTERLY+ANNUAL orchestrator.

Runs every AU prod fetcher that publishes at monthly cadence or slower.
Quarterly + annual series live here too: their fetchers are idempotent
(MERGE on PK), so running them monthly is wasted work on the API side
but catches every release window without per-cadence scheduling overhead
(per econ_to_prod.md §G.3 "one orchestrator, many cadences").

Excludes daily fetchers (see ``scripts.econ.au.au_daily``).

Custom shape (rather than ``_country_runner.run()``) because AU has the
AOFM staleness banner — XLSXs are manually downloaded via Edge by the
operator, and the email surfaces a ``[AOFM STALE]`` warning when the
newest XLSX is older than ``_AOFM_STALENESS_DAYS``.

Wired into ``scripts/imdr_monthly.py:PIPELINES`` (separately gated).

Usage:
    python -m scripts.econ.au.au_monthly
    python -m scripts.econ.au.au_monthly --no-email
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

# Force UTF-8 stdout — em-dashes and the like come through subprocess output.
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import structlog
from sqlalchemy import create_engine, text

from imdr.config.settings import get_settings
from imdr.domains.econ.aofm_xlsx import xlsx_age_days
from imdr.notifications.email import send_outlook_email
from imdr.utils.logging import configure_logging

log = structlog.get_logger(__name__)
UTC = datetime.timezone.utc

_AOFM_STALENESS_DAYS = 35  # AOFM publishes monthly; >35 days = a release missed
_TRACK_A_FREQUENCIES = ("MONTHLY", "QUARTERLY", "ANNUAL")


# ============================================================================
# REGISTERED PIPELINES — extend as new AU monthly fetchers land
# ============================================================================

PIPELINES: list[list[str]] = [
    # ABS — monthly real-economy
    [sys.executable, "-m", "scripts.econ.au.abs.abs_cpi"],
    [sys.executable, "-m", "scripts.econ.au.abs.abs_labour"],
    [sys.executable, "-m", "scripts.econ.au.abs.abs_lf_under"],
    [sys.executable, "-m", "scripts.econ.au.abs.abs_retail"],
    [sys.executable, "-m", "scripts.econ.au.abs.abs_lending"],
    [sys.executable, "-m", "scripts.econ.au.abs.abs_building_approvals"],
    # ABS — quarterly (folded into monthly)
    [sys.executable, "-m", "scripts.econ.au.abs.abs_gdp"],
    [sys.executable, "-m", "scripts.econ.au.abs.abs_gdp_expenditure"],
    [sys.executable, "-m", "scripts.econ.au.abs.abs_wpi"],
    [sys.executable, "-m", "scripts.econ.au.abs.abs_ppi_fd"],
    [sys.executable, "-m", "scripts.econ.au.abs.abs_capex"],
    [sys.executable, "-m", "scripts.econ.au.abs.abs_rppi"],
    [sys.executable, "-m", "scripts.econ.au.abs.abs_bop"],
    [sys.executable, "-m", "scripts.econ.au.abs.abs_bop_goods"],
    [sys.executable, "-m", "scripts.econ.au.abs.abs_trade_prices"],
    [sys.executable, "-m", "scripts.econ.au.abs.abs_job_vacancies"],
    [sys.executable, "-m", "scripts.econ.au.abs.abs_iip"],
    # Derived ToT (reads from econ.fact_indicator — runs after trade_prices)
    [sys.executable, "-m", "scripts.econ.au.abs.abs_tot"],
    # RBA — refresh monthly/quarterly CSVs then load
    [sys.executable, "-m", "scripts.econ.au.rba.rba_snapshot_refresh"],
    [sys.executable, "-m", "scripts.econ.au.rba.rba_monetary"],
    [sys.executable, "-m", "scripts.econ.au.rba.rba_icp"],
    [sys.executable, "-m", "scripts.econ.au.rba.rba_credit_balsheet"],
    [sys.executable, "-m", "scripts.econ.au.rba.rba_reer"],
    # AOFM — XLSX parsers (operator pre-refreshes via Edge; staleness banner
    # surfaces in email if the XLSXs are older than _AOFM_STALENESS_DAYS)
    [sys.executable, "-m", "scripts.econ.au.aofm.aofm_foreign_holdings"],
    [sys.executable, "-m", "scripts.econ.au.aofm.aofm_portfolio_aggregate"],
    [sys.executable, "-m", "scripts.econ.au.aofm.aofm_term_premium"],
    [sys.executable, "-m", "scripts.econ.au.aofm.aofm_turnover"],
    [sys.executable, "-m", "scripts.econ.au.aofm.aofm_issuance_buybacks"],
]


def _engine():
    s = get_settings()
    url = (
        f"mssql+pyodbc://@{s.mssql_host}:{s.mssql_port}/{s.mssql_database}"
        "?driver=ODBC+Driver+18+for+SQL+Server"
        "&Trusted_Connection=yes&Encrypt=yes&TrustServerCertificate=yes"
        "&LoginTimeout=60"
    )
    return create_engine(url, pool_pre_ping=True, fast_executemany=True)


def _track_a_snapshot(run_started_at: datetime.datetime) -> dict:
    """Pull stats on AU monthly+quarterly+annual indicators ingested this run."""
    eng = _engine()
    try:
        with eng.connect() as conn:
            by_vendor = conn.execute(
                text(
                    """
                    SELECT v.display_name                  AS vendor_name,
                           fq.frequency_code,
                           COUNT(DISTINCT i.id)            AS n_indicators,
                           COUNT(f.indicator_id)           AS n_obs,
                           MAX(f.obs_date)                 AS latest_obs
                    FROM   econ.fact_indicator f
                    JOIN   econ.dim_indicator i ON i.id = f.indicator_id
                    JOIN   dbo.dim_vendor v ON v.id = i.vendor_id
                    JOIN   dbo.dim_frequency fq ON fq.id = i.frequency_id
                    JOIN   dbo.dim_country c ON c.id = i.country_id
                    WHERE  c.country_code = 'AU'
                      AND  fq.frequency_code IN ('MONTHLY','QUARTERLY','ANNUAL')
                      AND  f.ingested_at >= :t0
                    GROUP BY v.display_name, fq.frequency_code
                    ORDER BY v.display_name, fq.frequency_code
                    """
                ),
                {"t0": run_started_at},
            ).all()
    finally:
        eng.dispose()
    total_obs = sum(r.n_obs for r in by_vendor)
    return {
        "rows": [
            {
                "vendor_name": vn,
                "frequency_code": fc,
                "n_indicators": int(ni),
                "n_obs": int(no),
                "latest_obs": str(lo),
            }
            for vn, fc, ni, no, lo in by_vendor
        ],
        "total_obs": int(total_obs),
    }


def _aofm_staleness_check() -> dict:
    """Surface AOFM XLSX age. ``stale=True`` when newest XLSX > threshold days.

    User refreshes XLSXs manually via Edge (corp firewall blocks Chrome).
    The email banner reminds them when a refresh is overdue.
    """
    age = xlsx_age_days()
    stale = age is not None and age > _AOFM_STALENESS_DAYS
    return {
        "age_days": age,
        "threshold_days": _AOFM_STALENESS_DAYS,
        "stale": stale,
        "missing": age is None,
    }


def _render_email(
    *,
    run_started_at: datetime.datetime,
    run_completed_at: datetime.datetime,
    duration_s: float,
    pipelines: list[dict],
    failed: list[str],
    track_a: dict,
    aofm: dict,
) -> tuple[str, str]:
    n_obs = track_a["total_obs"]
    fail_n = len(failed)
    aofm_stale = aofm.get("stale") or aofm.get("missing")

    if fail_n > 1:
        status, banner_color = "FAIL", "#e74c3c"
    elif fail_n == 1 or aofm_stale:
        status, banner_color = "PARTIAL", "#f39c12"
    else:
        status, banner_color = "OK", "#27ae60"

    prefix_bits: list[str] = []
    if aofm_stale:
        prefix_bits.append("[AOFM STALE]")
    if fail_n:
        prefix_bits.append(f"{fail_n} fail")
    subject_status = " ".join(prefix_bits) or "OK"
    subject = (
        f"[IMDR Monthly AU] {subject_status} - {n_obs} obs / "
        f"{len(track_a['rows'])} vendor-freq cells ({duration_s/60:.1f} min)"
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

    if track_a["rows"]:
        rows_track_a = "".join(
            f"<tr style='background:{_stripe(i)};'>"
            f"<td style='border:1px solid #ddd;padding:5px;'>{_e(v['vendor_name'])}</td>"
            f"<td style='border:1px solid #ddd;padding:5px;font-family:Consolas,monospace;'>{_e(v['frequency_code'])}</td>"
            f"<td style='border:1px solid #ddd;padding:5px;text-align:right;font-family:Consolas,monospace;'>{v['n_indicators']}</td>"
            f"<td style='border:1px solid #ddd;padding:5px;text-align:right;font-family:Consolas,monospace;'><b>{v['n_obs']}</b></td>"
            f"<td style='border:1px solid #ddd;padding:5px;font-family:Consolas,monospace;'>{_e(v['latest_obs'])}</td>"
            f"</tr>"
            for i, v in enumerate(track_a["rows"])
        )
    else:
        rows_track_a = "<tr><td colspan='5' style='border:1px solid #ddd;padding:8px;color:#888;'>No obs ingested this run (everything already at latest vintage).</td></tr>"

    aofm_banner = ""
    if aofm["missing"]:
        aofm_banner = (
            "<table width='96%' cellpadding='0' cellspacing='0' style='margin:14px auto 0 auto;'>"
            "<tr><td style='background:#f8d7da;border-left:4px solid #e74c3c;padding:10px 14px;'>"
            "<b style='color:#7a1f1f;'>[AOFM STALE]</b> "
            "No XLSXs found under <code>data/econ/au/aofm/xlsx/</code>. "
            "Refresh via Microsoft Edge from "
            "<a href='https://www.aofm.gov.au/data-hub'>aofm.gov.au/data-hub</a>."
            "</td></tr></table>"
        )
    elif aofm["stale"]:
        aofm_banner = (
            "<table width='96%' cellpadding='0' cellspacing='0' style='margin:14px auto 0 auto;'>"
            "<tr><td style='background:#fff3cd;border-left:4px solid #f39c12;padding:10px 14px;'>"
            "<b style='color:#7c5b00;'>[AOFM STALE]</b> "
            f"Newest XLSX is <b>{aofm['age_days']:.1f}</b> days old "
            f"(threshold: {aofm['threshold_days']} days). "
            "Refresh via Microsoft Edge from "
            "<a href='https://www.aofm.gov.au/data-hub'>aofm.gov.au/data-hub</a>. "
            "Corp firewall blocks Chrome/Playwright on these XLSXs."
            "</td></tr></table>"
        )

    aofm_age_str = (
        f"{aofm['age_days']:.1f} days"
        if aofm.get("age_days") is not None
        else "no XLSXs on disk"
    )

    pipelines_summary = (
        f"<span style='color:#27ae60;font-weight:bold;'>{len(pipelines)} OK</span>"
        if fail_n == 0
        else f"<span style='color:#e74c3c;font-weight:bold;'>{fail_n} FAILED</span> / {len(pipelines)} total"
    )
    obs_summary = (
        f"<span style='color:#27ae60;font-weight:bold;'>{n_obs} new obs across {len(track_a['rows'])} vendor-freq cells</span>"
        if n_obs > 0
        else "<span style='color:#888;'>no new obs (all already at latest vintage)</span>"
    )
    aofm_summary = (
        f"<span style='color:#e74c3c;font-weight:bold;'>{aofm_age_str} (STALE)</span>"
        if aofm_stale
        else f"<span style='color:#27ae60;'>{aofm_age_str} (fresh, &le; {aofm['threshold_days']}d)</span>"
    )

    body = f"""<!DOCTYPE html><html><head><meta charset='utf-8'></head>
<body style='margin:0;padding:0;font-family:Calibri,Arial,sans-serif;font-size:14px;color:#222;'>

<!-- HEADER -->
<table width='100%' cellpadding='0' cellspacing='0' style='background-color:#0d2137;'>
  <tr>
    <td style='padding:18px 24px;'>
      <span style='color:#ffffff;font-size:20px;font-weight:bold;'>IMDR &mdash; Australia Econ Ingest (Monthly)</span>
      <span style='background:{banner_color};color:#fff;padding:4px 12px;border-radius:4px;font-size:13px;font-weight:bold;margin-left:16px;'>{status}</span>
    </td>
  </tr>
  <tr>
    <td style='padding:0 24px 14px 24px;'>
      <span style='color:#7ba4c7;font-size:14px;'>{run_started_at:%Y-%m-%d %H:%M UTC} | scope: MONTHLY + QUARTERLY + ANNUAL</span>
    </td>
  </tr>
</table>

{aofm_banner}

<!-- EXECUTION -->
<table width='100%' cellpadding='0' cellspacing='0' style='margin-top:16px;'>
  <tr><td style='padding:0 24px;'><span style='font-size:16px;font-weight:bold;color:#0d2137;'>EXECUTION</span></td></tr>
</table>
<table width='96%' cellpadding='6' cellspacing='0' style='margin:8px auto 0 auto;border-collapse:collapse;border:1px solid #ddd;'>
  <tr style='background:#f5f5f5;'><td style='border:1px solid #ddd;font-weight:bold;width:200px;'>Orchestrator</td><td style='border:1px solid #ddd;font-family:Consolas,monospace;'>scripts.econ.au.au_monthly</td></tr>
  <tr><td style='border:1px solid #ddd;font-weight:bold;'>Started</td><td style='border:1px solid #ddd;'>{run_started_at:%Y-%m-%d %H:%M:%S} UTC</td></tr>
  <tr style='background:#f5f5f5;'><td style='border:1px solid #ddd;font-weight:bold;'>Completed</td><td style='border:1px solid #ddd;'>{run_completed_at:%Y-%m-%d %H:%M:%S} UTC</td></tr>
  <tr><td style='border:1px solid #ddd;font-weight:bold;'>Duration</td><td style='border:1px solid #ddd;'>{duration_s/60:.1f} min</td></tr>
  <tr style='background:#f5f5f5;'><td style='border:1px solid #ddd;font-weight:bold;'>Pipelines</td>
    <td style='border:1px solid #ddd;'>{pipelines_summary}</td>
  </tr>
  <tr><td style='border:1px solid #ddd;font-weight:bold;'>New observations</td>
    <td style='border:1px solid #ddd;'>{obs_summary}</td>
  </tr>
  <tr style='background:#f5f5f5;'><td style='border:1px solid #ddd;font-weight:bold;'>AOFM XLSX age</td>
    <td style='border:1px solid #ddd;'>{aofm_summary}</td>
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

<!-- TRACK A by vendor × frequency -->
<table width='100%' cellpadding='0' cellspacing='0' style='margin-top:20px;'>
  <tr><td style='padding:0 24px;'><span style='font-size:16px;font-weight:bold;color:#0d2137;'>INDICATORS BY VENDOR &times; FREQUENCY</span>
  <span style='font-size:12px;color:#666;margin-left:8px;'>obs ingested this run, scope = MONTHLY / QUARTERLY / ANNUAL</span></td></tr>
</table>
<table width='96%' cellpadding='5' cellspacing='0' style='margin:8px auto 0 auto;border-collapse:collapse;border:1px solid #ddd;font-size:13px;'>
  <tr style='background:#0d2137;color:#fff;'>
    <th style='border:1px solid #555;padding:6px;text-align:left;'>Vendor</th>
    <th style='border:1px solid #555;padding:6px;text-align:left;'>Frequency</th>
    <th style='border:1px solid #555;padding:6px;text-align:right;'>Indicators</th>
    <th style='border:1px solid #555;padding:6px;text-align:right;'>New obs</th>
    <th style='border:1px solid #555;padding:6px;text-align:left;'>Latest obs_date</th>
  </tr>
  {rows_track_a}
</table>

<!-- FOOTER -->
<table width='100%' cellpadding='0' cellspacing='0' style='margin-top:24px;background-color:#f0f0f0;border-top:2px solid #ddd;'>
  <tr><td style='padding:12px 24px;color:#888;font-size:12px;'>
    Generated by IMDR | scripts.econ.au.au_monthly | {run_completed_at:%Y-%m-%d %H:%M:%S} UTC |
    AOFM source: manual Edge download to <code>data/econ/au/aofm/xlsx/</code> (threshold {_AOFM_STALENESS_DAYS}d)
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
        name = cmd[-1] if cmd[-1].startswith("scripts.") else cmd[-2]
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

    track_a: dict = {"rows": [], "total_obs": 0}
    try:
        track_a = _track_a_snapshot(run_started_at)
        log.info(
            "au_monthly_track_a_snapshot",
            new_obs=track_a["total_obs"],
            cells=len(track_a["rows"]),
        )
    except Exception:
        log.exception("au_monthly_track_a_snapshot_failed")
        print(f"\n!! Track A snapshot failed:\n{traceback.format_exc()}")

    aofm: dict = {"age_days": None, "threshold_days": _AOFM_STALENESS_DAYS,
                  "stale": False, "missing": False}
    try:
        aofm = _aofm_staleness_check()
        if aofm["stale"] or aofm["missing"]:
            print(
                f"\n[AOFM STALE] newest XLSX age = "
                f"{aofm['age_days']!r} days (threshold {aofm['threshold_days']}d)"
            )
        log.info("au_monthly_aofm_check", **aofm)
    except Exception:
        log.exception("au_monthly_aofm_check_failed")
        print(f"\n!! AOFM check failed:\n{traceback.format_exc()}")

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
                track_a=track_a,
                aofm=aofm,
            )
            send_outlook_email(
                to=settings.email_to,
                subject=subject,
                html_body=body,
                importance=2 if failed else 1,
            )
        except Exception:
            log.exception("au_monthly_email_failed")
            print(f"\n!! email render/send failed:\n{traceback.format_exc()}")
    elif args.no_email:
        print("\n(email skipped by --no-email)")
    else:
        log.info("email_disabled_skipping_au_monthly_summary")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
