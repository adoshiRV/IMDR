"""Shared per-country econ orchestrator runtime.

Used by ``scripts/econ/{country}/{country}_{cadence}.py`` runners. All
follow the same shape:

  1. Capture ``run_started_at`` (UTC).
  2. Run each fetcher as a subprocess in sequence (isolation -- one
     failure doesn't block the others). Record rc + elapsed.
  3. After every fetcher runs, snapshot the DB for indicators in the
     given ``country_code`` + ``frequency_scope`` (rows ingested at/after
     ``run_started_at`` count as new this run; staleness comes from the
     frequency cadence).
  4. Render + send one consolidated email via
     ``imdr.notifications.formatters.country_econ_ingest.CountryEconIngestFormatter``.

Returns 0 on full success, 1 if any subprocess failed.
"""

from __future__ import annotations

import datetime
import subprocess
import time
import traceback

import structlog

from imdr.config.settings import get_settings
from imdr.notifications.econ_snapshot import snapshot
from imdr.utils.logging import configure_logging
from imdr.notifications.email import send_outlook_email
from imdr.notifications.formatters.country_econ_ingest import (
    CountryEconIngestFormatter,
)

log = structlog.get_logger(__name__)
UTC = datetime.timezone.utc


def run(
    *,
    run_name: str,
    country_code: str,
    country_label: str,
    country_name: str,
    orchestrator_path: str,
    pipelines: list[list[str]],
    frequency_scope: list[str],
) -> int:
    """Run a set of econ fetcher subprocesses and email a consolidated report.

    ``run_name``: short label for the subject line, e.g. ``"Weekly"``.
    ``country_code``: dim_country.country_code for the DB snapshot scope (e.g. ``"KR"``).
    ``country_label``: 2-letter display label for the email subject (usually == country_code).
    ``country_name``: long display name for the email body (e.g. ``"Korea"``).
    ``orchestrator_path``: dotted module path shown in the email footer.
    ``pipelines``: list of subprocess argv lists (``[sys.executable, "-m", ...]``).
    ``frequency_scope``: dim_frequency.frequency_code values this orchestrator
       owns -- used to scope the DB snapshot + staleness check.
    """
    settings = get_settings()
    configure_logging(settings)

    run_started_at = datetime.datetime.now(UTC)
    t0 = time.perf_counter()

    pipeline_results: list[dict] = []
    failed: list[str] = []

    for cmd in pipelines:
        name = cmd[-1]
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

    # --- DB snapshot + email ------------------------------------------------
    snapshots = []
    try:
        snapshots = snapshot(
            settings,
            country_code=country_code,
            run_started_at=run_started_at,
            frequency_codes=frequency_scope,
        )
        log.info(
            "country_econ_snapshot",
            country=country_code,
            run_name=run_name,
            indicators=len(snapshots),
            new_rows=sum(s.new_obs_this_run for s in snapshots),
            stale=sum(1 for s in snapshots if s.is_stale),
        )
    except Exception:
        log.exception("country_econ_snapshot_failed",
                      country=country_code, run_name=run_name)
        print(f"\n!! DB snapshot failed:\n{traceback.format_exc()}")

    if getattr(settings, "email_enabled", False) and getattr(settings, "email_to", ""):
        try:
            formatter = CountryEconIngestFormatter(
                country_label=country_label,
                country_name=country_name,
                orchestrator_path=orchestrator_path,
            )
            subject_kwargs = dict(
                run_name=run_name,
                new_rows=sum(s.new_obs_this_run for s in snapshots),
                indicators_updated=sum(1 for s in snapshots if s.new_obs_this_run > 0),
                stale_count=sum(1 for s in snapshots if s.is_stale),
                failed_pipelines=failed,
            )
            subject = formatter.format_subject(**subject_kwargs)
            body = formatter.format_body(
                run_name=run_name,
                run_started_at=run_started_at,
                run_completed_at=run_completed_at,
                duration_s=duration_s,
                pipelines=pipeline_results,
                failed_pipelines=failed,
                snapshots=snapshots,
                frequency_scope=frequency_scope,
            )
            importance = 2 if failed else 1
            send_outlook_email(
                to=settings.email_to,
                subject=subject,
                html_body=body,
                importance=importance,
            )
        except Exception:
            log.exception("country_econ_email_failed",
                          country=country_code, run_name=run_name)
            print(f"\n!! email render/send failed:\n{traceback.format_exc()}")
    else:
        log.info("email_disabled_skipping_country_econ_summary",
                 country=country_code, run_name=run_name)

    if failed:
        print(f"\n{len(failed)} pipeline(s) failed: {', '.join(failed)}")
        return 1
    return 0
