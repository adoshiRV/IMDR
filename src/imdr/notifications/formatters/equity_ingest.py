"""Equity ingest email formatter — shared for index levels and VIX family.

Jinja2 + inline CSS for professional Outlook emails.
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


class EquityIngestFormatter:
    """Formats HTML emails for equity index/VIX ingestion results."""

    def __init__(self) -> None:
        self._env = Environment(
            loader=FileSystemLoader(str(_TEMPLATE_DIR)),
            autoescape=True,
        )
        self._template = self._env.get_template("equity_ingest.html")

    def format_subject(
        self,
        pipeline_name: str = "",
        run_date: datetime | None = None,
        rows_loaded: int = 0,
        has_errors: bool = False,
        **kwargs: Any,
    ) -> str:
        status = "ERROR" if has_errors else "OK"
        date_str = run_date.strftime("%Y-%m-%d") if run_date else "N/A"
        return f"[IMDR] {pipeline_name} {status} | {date_str} | {rows_loaded} rows"

    def format_body(
        self,
        pipeline_name: str = "",
        run_date: datetime | None = None,
        rows_loaded: int = 0,
        index_data: list[dict[str, Any]] | None = None,
        health_passed: bool | None = None,
        health_details: list[dict[str, Any]] | None = None,
        holiday_hits: list[dict[str, Any]] | None = None,
        elapsed_secs: float = 0.0,
        has_errors: bool = False,
        quota_usage: int | None = None,
        **kwargs: Any,
    ) -> str:
        index_data = index_data or []
        health_details = health_details or []
        holiday_hits = holiday_hits or []

        now_utc = datetime.now(timezone.utc)
        date_str = run_date.strftime("%Y-%m-%d") if run_date else "N/A"
        day_name = run_date.strftime("%A") if run_date else ""
        run_time_utc = now_utc.strftime("%Y-%m-%d %H:%M:%S UTC")
        run_time_sgt = _to_sgt(now_utc).strftime("%H:%M:%S SGT")
        elapsed = f"{elapsed_secs:.1f}s" if elapsed_secs else "N/A"

        # Group by region
        regions: dict[str, list[dict]] = {}
        for item in index_data:
            r = item.get("region", "other")
            regions.setdefault(r, []).append(item)

        ctx = {
            "pipeline_name": pipeline_name,
            "has_errors": has_errors,
            "date_str": date_str,
            "day_name": day_name,
            "run_time_utc": run_time_utc,
            "run_time_sgt": run_time_sgt,
            "elapsed": elapsed,
            "rows_loaded": rows_loaded,
            "n_indices": len(index_data),
            "regions": regions,
            "health_passed": health_passed,
            "health_details": health_details,
            "holiday_hits": holiday_hits,
            "quota_usage": quota_usage,
        }
        return self._template.render(**ctx)
