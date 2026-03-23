"""Rates swaption vol ingest email formatter — Jinja2 + inline CSS for Outlook emails."""

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


def _prepare_ccy_groups(
    ccy_data: list[dict[str, Any]],
) -> list[tuple[str, list[dict[str, Any]]]]:
    """Group currencies by classification (G10/Other), sort each group."""
    groups: dict[str, list[dict[str, Any]]] = {}

    for c in ccy_data:
        group = c.get("classification", "OTHER")
        groups.setdefault(group, []).append(c)

    for group in groups:
        groups[group].sort(key=lambda r: r.get("ccy", ""))

    order = ["G10", "OTHER"]
    result = []
    for g in order:
        if g in groups:
            result.append((g, groups[g]))
    for g in sorted(groups):
        if g not in order:
            result.append((g, groups[g]))
    return result


class RatesVolIngestFormatter:
    """Formats HTML emails for rates swaption vol ingestion results."""

    def __init__(self) -> None:
        self._env = Environment(
            loader=FileSystemLoader(str(_TEMPLATE_DIR)),
            autoescape=True,
        )
        self._template = self._env.get_template("rates_vol_ingest.html")

    def format_subject(
        self,
        pipeline_name: str = "",
        run_date: datetime | None = None,
        rows_loaded: int = 0,
        n_currencies: int = 0,
        has_errors: bool = False,
        is_historical: bool = False,
        **kwargs: Any,
    ) -> str:
        mode = "Historical" if is_historical else "Live"
        status = "ERROR" if has_errors else "OK"
        date_str = run_date.strftime("%Y-%m-%d") if run_date else "N/A"
        return (
            f"[IMDR] Rates Vol {mode} Ingest {status} | {date_str} "
            f"| {n_currencies} ccys / {rows_loaded} obs"
        )

    def format_body(
        self,
        pipeline_name: str = "",
        run_date: datetime | None = None,
        rows_extracted: int = 0,
        rows_loaded: int = 0,
        n_currencies: int = 0,
        ccy_data: list[dict[str, Any]] | None = None,
        missing_ccys: list[str] | None = None,
        quality_flags: list[dict[str, Any]] | None = None,
        health_passed: bool | None = None,
        health_details: list[dict[str, Any]] | None = None,
        elapsed_secs: float = 0.0,
        is_historical: bool = False,
        has_errors: bool = False,
        **kwargs: Any,
    ) -> str:
        ccy_data = ccy_data or []
        missing_ccys = missing_ccys or []
        quality_flags = quality_flags or []
        health_details = health_details or []

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

        ccy_groups = _prepare_ccy_groups(ccy_data)

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
            "n_currencies": n_currencies,
            "rows_extracted": rows_extracted,
            "rows_loaded": rows_loaded,
            "n_missing": len(missing_ccys),
            "n_quality_flags": n_quality_flags,
            "health_passed": health_passed,
            "health_details": health_details,
            "ccy_groups": ccy_groups,
            "quality_flags": quality_flags,
            "missing_ccys": missing_ccys,
        }
        return self._template.render(**ctx)
