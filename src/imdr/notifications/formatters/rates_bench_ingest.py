"""Rates bench rates (central bank policy rates) ingest email formatter.

Jinja2 + inline CSS for Outlook emails.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

_SGT = timezone(timedelta(hours=8))
_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"


def _to_sgt(dt: datetime) -> datetime:
    """Convert a UTC datetime to SGT (UTC+8)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(_SGT)


class RatesBenchIngestFormatter:
    """Formats HTML emails for central bank policy rates ingestion results."""

    def __init__(self) -> None:
        self._env = Environment(
            loader=FileSystemLoader(str(_TEMPLATE_DIR)),
            autoescape=True,
        )
        self._template = self._env.get_template("rates_bench_ingest.html")

    def format_subject(
        self,
        pipeline_name: str = "",
        run_date: datetime | None = None,
        rows_loaded: int = 0,
        n_cbs: int = 0,
        has_errors: bool = False,
        is_historical: bool = False,
        **kwargs: Any,
    ) -> str:
        mode = "Historical" if is_historical else "Live"
        status = "ERROR" if has_errors else "OK"
        date_str = run_date.strftime("%Y-%m-%d") if run_date else "N/A"
        return (
            f"[IMDR] Rates Bench {mode} Ingest {status} | {date_str} "
            f"| {n_cbs} CBs / {rows_loaded} obs"
        )

    def format_body(
        self,
        pipeline_name: str = "",
        run_date: datetime | None = None,
        rows_extracted: int = 0,
        rows_loaded: int = 0,
        n_cbs: int = 0,
        cb_data: list[dict[str, Any]] | None = None,
        missing_cbs: list[str] | None = None,
        quality_flags: list[dict[str, Any]] | None = None,
        health_passed: bool | None = None,
        health_details: list[dict[str, Any]] | None = None,
        holiday_hits: list[dict[str, str]] | None = None,
        elapsed_secs: float = 0.0,
        is_historical: bool = False,
        has_errors: bool = False,
        **kwargs: Any,
    ) -> str:
        cb_data = cb_data or []
        missing_cbs = missing_cbs or []
        quality_flags = quality_flags or []
        health_details = health_details or []
        holiday_hits = holiday_hits or []

        now_utc = datetime.now(timezone.utc)

        if run_date:
            date_str = run_date.strftime("%Y-%m-%d")
            day_name = run_date.strftime("%A")
        else:
            date_str = "N/A"
            day_name = ""

        run_time_utc = now_utc.strftime("%Y-%m-%d %H:%M:%S UTC")
        run_time_sgt = _to_sgt(now_utc).strftime("%H:%M:%S SGT")
        elapsed = f"{elapsed_secs:.1f}s" if elapsed_secs else "N/A"

        # Sort CB data alphabetically by cb_code
        cb_data_sorted = sorted(cb_data, key=lambda r: r.get("cb_code", ""))

        n_quality_flags = len([q for q in quality_flags if q.get("status") != "passed"])

        ctx = {
            "mode": "Historical" if is_historical else "Live",
            "has_errors": has_errors,
            "pipeline_name": pipeline_name,
            "date_str": date_str,
            "day_name": day_name,
            "run_time_utc": run_time_utc,
            "run_time_sgt": run_time_sgt,
            "elapsed": elapsed,
            "n_cbs": n_cbs,
            "rows_extracted": rows_extracted,
            "rows_loaded": rows_loaded,
            "n_missing": len(missing_cbs),
            "n_quality_flags": n_quality_flags,
            "health_passed": health_passed,
            "health_details": health_details,
            "cb_data": cb_data_sorted,
            "quality_flags": quality_flags,
            "missing_cbs": missing_cbs,
            "n_holidays": len(holiday_hits),
            "holiday_hits": holiday_hits,
        }
        return self._template.render(**ctx)
