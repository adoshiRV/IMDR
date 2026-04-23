"""Staleness alert email formatter.

Produces a cross-domain HTML email summarising which data series
in IMDR are stale (latest observation older than the configured
threshold).  Designed to run once after the daily pipeline batch
completes, giving ops a single consolidated view.

Uses the same Jinja2 + inline-CSS pattern as the ingest formatters.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from imdr.healthchecks.staleness import StalenessReport

_SGT = timezone(timedelta(hours=8))
_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"


def _to_sgt(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(_SGT)


class StalenessAlertFormatter:
    """Formats the cross-domain staleness alert email."""

    def __init__(self) -> None:
        self._env = Environment(
            loader=FileSystemLoader(str(_TEMPLATE_DIR)),
            autoescape=True,
        )
        self._template = self._env.get_template("staleness_alert.html")

    def format_subject(
        self,
        report: StalenessReport | None = None,
        **kwargs: Any,
    ) -> str:
        if report and report.has_stale:
            n_keys = report.total_stale_keys
            n_domains = len(report.stale_domains)
            return (
                f"[IMDR] STALENESS ALERT | "
                f"{n_keys} stale key(s) across {n_domains} domain(s) | "
                f"{report.reference_date}"
            )
        ref = report.reference_date if report else "N/A"
        return f"[IMDR] Staleness Check OK | All domains fresh | {ref}"

    def format_body(
        self,
        report: StalenessReport | None = None,
        **kwargs: Any,
    ) -> str:
        if report is None:
            return "<p>No staleness report available.</p>"

        now_utc = datetime.now(timezone.utc)
        run_time_utc = now_utc.strftime("%Y-%m-%d %H:%M:%S UTC")
        run_time_sgt = _to_sgt(now_utc).strftime("%H:%M:%S SGT")

        ctx = {
            "has_stale": report.has_stale,
            "reference_date": str(report.reference_date),
            "checked_at": report.checked_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "run_time_utc": run_time_utc,
            "run_time_sgt": run_time_sgt,
            "total_stale_keys": report.total_stale_keys,
            "n_stale_domains": len(report.stale_domains),
            "n_healthy_domains": len(report.healthy_domains),
            "n_total_domains": len(report.summaries),
            "stale_domains": [
                {
                    "domain": s.domain,
                    "pipeline_name": s.pipeline_name,
                    "total_keys": s.total_keys,
                    "stale_keys": s.stale_keys,
                    "fresh_keys": s.fresh_keys,
                    "latest_date": str(s.latest_date) if s.latest_date else "N/A",
                    "stale_items": [
                        {
                            "label": sk.label,
                            "latest_date": str(sk.latest_date),
                            "days_behind": sk.days_behind,
                            "max_stale_days": sk.max_stale_days,
                        }
                        for sk in s.stale_items
                    ],
                }
                for s in report.stale_domains
            ],
            "healthy_domains": [
                {
                    "domain": s.domain,
                    "pipeline_name": s.pipeline_name,
                    "total_keys": s.total_keys,
                    "latest_date": str(s.latest_date) if s.latest_date else "N/A",
                }
                for s in report.healthy_domains
            ],
        }
        return self._template.render(**ctx)
