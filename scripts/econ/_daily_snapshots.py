"""Shared plumbing for the per-country DAILY dual-track orchestrators.

``kr_daily`` / ``au_daily`` / ``us_daily`` each run Track A indicator fetchers
and/or Track B filings ingest as isolated subprocesses, then email a run
summary built from post-run DB snapshots. The engine, the two snapshot
queries, and the subprocess run-loop were previously copied near-verbatim into
each orchestrator; they live here once.

Only the DATA layer + run-loop are shared. Email rendering stays per-country
(the KR layout is minimalist; AU/US are branded and AU carries a Cotality-gap
banner), so each orchestrator keeps its own ``_render_email``.
"""

from __future__ import annotations

import datetime
import subprocess
import time

from sqlalchemy import bindparam, create_engine, text

from imdr.config.settings import get_settings

UTC = datetime.timezone.utc


def filings_engine():
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


def run_pipelines(pipelines: list[list[str]]) -> dict:
    """Run each argv as an isolated subprocess (one failure never blocks the
    rest). Returns results + failed-name list + timing. The display name is the
    module token after ``-m`` (falls back to the last arg)."""
    started_at = datetime.datetime.now(UTC)
    t0 = time.perf_counter()
    results: list[dict] = []
    failed: list[str] = []
    for cmd in pipelines:
        name = cmd[cmd.index("-m") + 1] if "-m" in cmd else cmd[-1]
        p_start = time.perf_counter()
        rc = subprocess.call(cmd)
        elapsed = time.perf_counter() - p_start
        results.append({"name": name, "rc": rc, "elapsed_s": elapsed})
        if rc != 0:
            print(f"FAIL  {name}  rc={rc}  ({elapsed:.1f}s)")
            failed.append(name)
        else:
            print(f"OK    {name}  ({elapsed:.1f}s)")
    return {
        "results": results,
        "failed": failed,
        "duration_s": time.perf_counter() - t0,
        "started_at": started_at,
        "completed_at": datetime.datetime.now(UTC),
    }


def filings_snapshot(
    run_started_at: datetime.datetime,
    country_code: str,
    *,
    official_only: bool = True,
) -> dict:
    """Track B: filings ingested at/after ``run_started_at`` for a country.

    ``official_only`` restricts to ``vendor_category LIKE 'official_%'`` (KR/US);
    AU passes ``False`` to also include sell-side AU filings ingested via the
    same Phase-J path. Returns ``by_vendor`` + totals + 5 most-recent titles.
    """
    cat_clause = "AND v.vendor_category LIKE 'official_%'" if official_only else ""
    eng = filings_engine()
    try:
        with eng.connect() as conn:
            by_vendor = conn.execute(
                text(
                    f"""
                    SELECT v.vendor_code, v.vendor_category, v.display_name,
                           COUNT(DISTINCT r.id) AS n_reports,
                           COUNT(c.id)           AS n_chunks
                    FROM research.dim_report r
                    JOIN dbo.dim_vendor v   ON v.id = r.vendor_id
                    LEFT JOIN research.fact_chunk c ON c.report_id = r.id
                    WHERE r.country_id = (SELECT id FROM dbo.dim_country WHERE country_code = :cc)
                      {cat_clause}
                      AND r.created_at >= :t0
                    GROUP BY v.vendor_code, v.vendor_category, v.display_name
                    ORDER BY n_reports DESC, v.vendor_code
                    """
                ),
                {"t0": run_started_at, "cc": country_code},
            ).all()
            recent = conn.execute(
                text(
                    f"""
                    SELECT TOP 5 v.vendor_code, r.publish_date, r.title
                    FROM research.dim_report r
                    JOIN dbo.dim_vendor v   ON v.id = r.vendor_id
                    WHERE r.country_id = (SELECT id FROM dbo.dim_country WHERE country_code = :cc)
                      {cat_clause}
                      AND r.created_at >= :t0
                    ORDER BY r.created_at DESC
                    """
                ),
                {"t0": run_started_at, "cc": country_code},
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


def track_a_snapshot(
    run_started_at: datetime.datetime,
    country_code: str,
    frequencies: list[str],
) -> dict:
    """Track A: indicators ingested at/after ``run_started_at`` for a country,
    scoped to the given ``frequencies`` (AU daily = ``["DAILY"]``; US daily =
    ``["DAILY", "WEEKLY"]``) so a monthly orchestrator's snapshot doesn't
    double-count. Returns ``by_vendor`` (indicators / obs / latest_obs) + total.
    """
    stmt = text(
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
        WHERE  c.country_code = :cc
          AND  fq.frequency_code IN :freqs
          AND  f.ingested_at >= :t0
        GROUP BY v.display_name
        ORDER BY n_obs DESC
        """
    ).bindparams(bindparam("freqs", expanding=True))
    eng = filings_engine()
    try:
        with eng.connect() as conn:
            by_vendor = conn.execute(
                stmt,
                {"t0": run_started_at, "cc": country_code, "freqs": list(frequencies)},
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
