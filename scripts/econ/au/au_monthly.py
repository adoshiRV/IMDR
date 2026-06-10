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

    prefix_bits: list[str] = []
    if aofm_stale:
        prefix_bits.append("[AOFM STALE]")
    if fail_n:
        prefix_bits.append(f"⚠ {fail_n} failed")
    elif not prefix_bits:
        prefix_bits.append("✓ all ok")
    status = " ".join(prefix_bits)

    subject = (
        f"[IMDR Monthly AU] {status} — {n_obs} obs / "
        f"{len(track_a['rows'])} vendor×freq cells ({duration_s/60:.1f} min)"
    )

    def _e(s: object) -> str:
        return _html.escape(str(s or ""))

    rows_pipelines = "\n".join(
        f"<tr><td>{_e(p['name'])}</td><td>{p['rc']}</td>"
        f"<td style='text-align:right'>{p['elapsed_s']:.1f}s</td></tr>"
        for p in pipelines
    )
    rows_track_a = "\n".join(
        f"<tr><td>{_e(v['vendor_name'])}</td><td>{_e(v['frequency_code'])}</td>"
        f"<td style='text-align:right'>{v['n_indicators']}</td>"
        f"<td style='text-align:right'>{v['n_obs']}</td>"
        f"<td>{_e(v['latest_obs'])}</td></tr>"
        for v in track_a["rows"]
    ) or "<tr><td colspan='5' style='color:#888'>no obs ingested this run</td></tr>"

    aofm_banner = ""
    if aofm["missing"]:
        aofm_banner = (
            "<div style='background:#f8d7da;border:1px solid #f1aeb5;padding:8px 12px;"
            "margin:8px 0;border-radius:4px;'><b>[AOFM STALE]</b> "
            "No XLSXs found under <code>data/econ/au/aofm/xlsx/</code>. "
            "Refresh via Microsoft Edge from "
            "<a href='https://www.aofm.gov.au/data-hub'>aofm.gov.au/data-hub</a>.</div>"
        )
    elif aofm["stale"]:
        aofm_banner = (
            f"<div style='background:#fff3cd;border:1px solid #ffe082;padding:8px 12px;"
            f"margin:8px 0;border-radius:4px;'><b>[AOFM STALE]</b> "
            f"Newest XLSX is {aofm['age_days']:.1f} days old "
            f"(threshold: {aofm['threshold_days']} days). "
            f"Refresh via Microsoft Edge from "
            f"<a href='https://www.aofm.gov.au/data-hub'>aofm.gov.au/data-hub</a>. "
            f"Corp firewall blocks Chrome/Playwright on these XLSXs.</div>"
        )

    css = (
        "body{font-family:Segoe UI,Arial,sans-serif;font-size:13px;}"
        "table{border-collapse:collapse;margin:8px 0;}"
        "th,td{border:1px solid #ddd;padding:4px 8px;}"
        "th{background:#f4f4f4;text-align:left;}"
        ".meta{color:#666;margin-top:12px;font-size:11px;}"
    )

    body = f"""<!doctype html><html><head><style>{css}</style></head><body>
<h3>IMDR AU Monthly — Track A data series</h3>
<p>Started {run_started_at:%Y-%m-%d %H:%M UTC} · finished {run_completed_at:%H:%M UTC} ·
duration {duration_s/60:.1f} min · {n_obs} obs ingested ·
{fail_n} pipeline(s) failed</p>

{aofm_banner}

<h4>Pipelines</h4>
<table><thead><tr><th>name</th><th>rc</th><th>elapsed</th></tr></thead>
<tbody>{rows_pipelines}</tbody></table>

<h4>Indicators ingested by vendor × frequency</h4>
<table><thead><tr><th>vendor</th><th>freq</th>
<th style='text-align:right'>indicators</th>
<th style='text-align:right'>obs</th>
<th>latest obs_date</th></tr></thead>
<tbody>{rows_track_a}</tbody></table>

<p class="meta">Orchestrator: <code>scripts.econ.au.au_monthly</code>.
AOFM XLSXs source: manual Edge download to <code>data/econ/au/aofm/xlsx/</code>;
staleness threshold {_AOFM_STALENESS_DAYS}d.</p>
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
