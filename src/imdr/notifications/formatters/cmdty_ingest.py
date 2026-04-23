"""Commodities ingest email formatter — shared across SPOT, EIA, and IMPLIED_VOL.

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


class CmdtyIngestFormatter:
    """Formats HTML emails for commodities ingestion results (all 3 sub-products)."""

    def __init__(self) -> None:
        self._env = Environment(
            loader=FileSystemLoader(str(_TEMPLATE_DIR)),
            autoescape=True,
        )
        self._template = self._env.get_template("cmdty_ingest.html")

    def format_subject(
        self,
        pipeline_name: str = "",
        run_date: datetime | None = None,
        rows_loaded: int = 0,
        n_products: int = 0,
        has_errors: bool = False,
        is_historical: bool = False,
        **kwargs: Any,
    ) -> str:
        mode = "Historical" if is_historical else "Live"
        status = "ERROR" if has_errors else "OK"
        date_str = run_date.strftime("%Y-%m-%d") if run_date else "N/A"
        return (
            f"[IMDR] Commodities {mode} Ingest {status} | {date_str} "
            f"| {n_products} products / {rows_loaded} obs"
        )

    def format_body(
        self,
        pipeline_name: str = "",
        run_date: datetime | None = None,
        rows_extracted: int = 0,
        rows_loaded: int = 0,
        n_products: int = 0,
        product_data: list[dict[str, Any]] | None = None,
        missing_products: list[str] | None = None,
        quality_flags: list[dict[str, Any]] | None = None,
        health_passed: bool | None = None,
        health_details: list[dict[str, Any]] | None = None,
        holiday_hits: list[dict[str, str]] | None = None,
        elapsed_secs: float = 0.0,
        is_historical: bool = False,
        has_errors: bool = False,
        **kwargs: Any,
    ) -> str:
        product_data = product_data or []
        missing_products = missing_products or []
        quality_flags = quality_flags or []
        health_details = health_details or []
        holiday_hits = holiday_hits or []

        now_utc = datetime.now(timezone.utc)

        date_str = run_date.strftime("%Y-%m-%d") if run_date else "N/A"
        day_name = run_date.strftime("%A") if run_date else ""
        run_time_utc = now_utc.strftime("%Y-%m-%d %H:%M:%S UTC")
        run_time_sgt = _to_sgt(now_utc).strftime("%H:%M:%S SGT")
        elapsed = f"{elapsed_secs:.1f}s" if elapsed_secs else "N/A"

        # Group products by commodity class
        precious = [p for p in product_data if p.get("commodity_class") == "precious_metal"]
        energy = [p for p in product_data if p.get("commodity_class") == "energy"]
        other = [p for p in product_data if p.get("commodity_class") not in ("precious_metal", "energy")]
        product_groups = []
        if precious:
            product_groups.append(("Precious Metals", precious))
        if energy:
            product_groups.append(("Energy", energy))
        if other:
            product_groups.append(("Other", other))
        # Fallback: if no class assigned, show flat list
        if not product_groups and product_data:
            product_groups.append(("Products", product_data))

        ctx = {
            "mode": "Historical" if is_historical else "Live",
            "has_errors": has_errors,
            "pipeline_name": pipeline_name,
            "date_str": date_str,
            "day_name": day_name,
            "run_time_utc": run_time_utc,
            "run_time_sgt": run_time_sgt,
            "elapsed": elapsed,
            "n_products": n_products,
            "rows_extracted": rows_extracted,
            "rows_loaded": rows_loaded,
            "n_missing": len(missing_products),
            "n_quality_flags": len([q for q in quality_flags if q.get("status") != "passed"]),
            "health_passed": health_passed,
            "health_details": health_details,
            "product_groups": product_groups,
            "quality_flags": quality_flags,
            "missing_products": missing_products,
            "n_holidays": len(holiday_hits),
            "holiday_hits": holiday_hits,
        }
        return self._template.render(**ctx)
