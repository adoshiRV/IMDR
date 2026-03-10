"""Rates ingest email formatter — Jinja2 + inline CSS for professional Outlook emails."""

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


def _fmt_rate(val: Any) -> str:
    """Format a rate value to 6 decimal places."""
    try:
        return f"{float(val):.6f}"
    except (ValueError, TypeError):
        return str(val)


def _prepare_curve_groups(
    curves: list[dict[str, Any]],
) -> list[tuple[str, list[dict[str, Any]]]]:
    """Group curve rows by classification (G10/Asia/Other), sort by ccy+curve."""
    groups: dict[str, list[dict[str, Any]]] = {}

    for c in curves:
        group = c.get("classification", "OTHER")
        row = {
            "ccy": c.get("ccy", ""),
            "curve": c.get("curve", ""),
            "status": c.get("status", "active"),
            "tenors": c.get("tenors", 0),
            "quotes": c.get("quotes", []),
            "rows": c.get("rows", 0),
        }
        groups.setdefault(group, []).append(row)

    for group in groups:
        groups[group].sort(key=lambda r: (r["ccy"], r["curve"]))

    order = ["G10", "ASIA", "OTHER"]
    result = []
    for g in order:
        if g in groups:
            result.append((g, groups[g]))
    for g in sorted(groups):
        if g not in order:
            result.append((g, groups[g]))
    return result


class RatesIngestFormatter:
    """Formats HTML emails for Rates observation ingestion results."""

    def __init__(self) -> None:
        self._env = Environment(
            loader=FileSystemLoader(str(_TEMPLATE_DIR)),
            autoescape=True,
        )
        self._template = self._env.get_template("rates_ingest.html")

    def format_subject(
        self,
        pipeline_name: str = "",
        run_date: datetime | None = None,
        rows_loaded: int = 0,
        has_errors: bool = False,
        is_historical: bool = False,
        **kwargs: Any,
    ) -> str:
        mode = "Historical" if is_historical else "Daily"
        status = "ERROR" if has_errors else "OK"
        date_str = run_date.strftime("%Y-%m-%d") if run_date else "N/A"
        return f"[IMDR] Rates {mode} Ingest {status} | {date_str} | {rows_loaded} obs"

    def format_body(
        self,
        pipeline_name: str = "",
        run_date: datetime | None = None,
        quotes: list[str] | None = None,
        frequency: str = "DAILY",
        rows_extracted: int = 0,
        rows_loaded: int = 0,
        n_curves: int = 0,
        curves: list[dict[str, Any]] | None = None,
        missing_curves: list[dict[str, str]] | None = None,
        holiday_hits: list[dict[str, str]] | None = None,
        freshness: dict[str, Any] | None = None,
        health_passed: bool | None = None,
        health_details: list[dict[str, Any]] | None = None,
        quality_flags: list[dict[str, Any]] | None = None,
        elapsed_secs: float = 0.0,
        is_historical: bool = False,
        has_errors: bool = False,
        **kwargs: Any,
    ) -> str:
        quotes = quotes or []
        curves = curves or []
        missing_curves = missing_curves or []
        holiday_hits = holiday_hits or []
        quality_flags = quality_flags or []
        health_details = health_details or []

        now_utc = datetime.now(timezone.utc)

        # Date strings
        date_str = run_date.strftime("%Y-%m-%d") if run_date else "N/A"
        day_name = run_date.strftime("%A") if run_date else ""

        # Run time strings
        run_time_utc = now_utc.strftime("%Y-%m-%d %H:%M:%S UTC")
        run_time_sgt = _to_sgt(now_utc).strftime("%H:%M:%S SGT")

        # Elapsed
        elapsed = f"{elapsed_secs:.1f}s" if elapsed_secs else "N/A"

        # Freshness entries for template
        freshness_entries: list[dict[str, Any]] = []
        if freshness and "error" not in freshness:
            for tag, info in freshness.items():
                freshness_entries.append({
                    "tag": tag,
                    "last_modified": info.get("last_modified", "N/A"),
                    "recent_updates": info.get("recent_updates", 0),
                })

        # Curve groups
        curve_groups = _prepare_curve_groups(curves)

        ctx = {
            "mode": "Historical" if is_historical else "Daily",
            "has_errors": has_errors,
            "pipeline_name": pipeline_name,
            "date_str": date_str,
            "day_name": day_name,
            "quotes": quotes,
            "frequency": frequency,
            "run_time_utc": run_time_utc,
            "run_time_sgt": run_time_sgt,
            "elapsed": elapsed,
            "rows_extracted": rows_extracted,
            "rows_loaded": rows_loaded,
            "n_curves": n_curves,
            "n_missing": len(missing_curves),
            "n_holidays": len(holiday_hits),
            "n_quality_flags": len(quality_flags),
            "health_passed": health_passed,
            "health_details": health_details,
            "freshness_entries": freshness_entries,
            "freshness_error": bool(freshness and "error" in freshness),
            "curve_groups": curve_groups,
            "missing_curves": missing_curves,
            "holiday_hits": holiday_hits,
            "quality_flags": quality_flags,
        }
        return self._template.render(**ctx)
