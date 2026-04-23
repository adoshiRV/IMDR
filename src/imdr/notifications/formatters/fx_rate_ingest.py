"""FX rate ingest email formatter — Jinja2 + inline CSS."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

_SGT = timezone(timedelta(hours=8))
_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"


def _to_sgt(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(_SGT)


def _prepare_pair_groups(
    pair_data: list[dict[str, Any]],
) -> list[tuple[str, list[dict[str, Any]]]]:
    class_order = ["g10", "em_ndf", "em_deliverable"]
    class_labels = {"g10": "G10", "em_ndf": "EM NDF", "em_deliverable": "EM Deliverable"}
    groups: dict[str, list[dict[str, Any]]] = {}

    for pd_ in pair_data:
        cls = pd_.get("ccy_class", "g10")
        groups.setdefault(cls, []).append(pd_)

    for cls in groups:
        groups[cls].sort(key=lambda r: r.get("pair", ""))

    result: list[tuple[str, list[dict[str, Any]]]] = []
    for cls in class_order:
        if cls in groups:
            result.append((class_labels.get(cls, cls.upper()), groups[cls]))
    for cls in sorted(groups):
        if cls not in class_order:
            result.append((cls.upper(), groups[cls]))
    return result


class FXRateIngestFormatter:
    """HTML email formatter for FX rate ingestion runs."""

    def __init__(self) -> None:
        self._env = Environment(
            loader=FileSystemLoader(str(_TEMPLATE_DIR)),
            autoescape=True,
        )
        self._template = self._env.get_template("fx_rate_ingest.html")

    def format_subject(
        self,
        pipeline_name: str = "",
        run_date: datetime | None = None,
        rows_loaded: int = 0,
        n_pairs: int = 0,
        has_errors: bool = False,
        is_historical: bool = False,
        **kwargs: Any,
    ) -> str:
        mode = "Historical" if is_historical else "Live"
        status = "ERROR" if has_errors else "OK"
        date_str = run_date.strftime("%Y-%m-%d") if run_date else "N/A"
        return (
            f"[IMDR] FX Rate {mode} Ingest {status} | {date_str} "
            f"| {n_pairs} pairs / {rows_loaded} obs"
        )

    def format_body(
        self,
        pipeline_name: str = "",
        run_date: datetime | None = None,
        rows_extracted: int = 0,
        rows_loaded: int = 0,
        n_pairs: int = 0,
        pair_data: list[dict[str, Any]] | None = None,
        missing_pairs: list[str] | None = None,
        holiday_hits: list[dict[str, str]] | None = None,
        quality_flags: list[dict[str, Any]] | None = None,
        health_passed: bool | None = None,
        health_details: list[dict[str, Any]] | None = None,
        elapsed_secs: float = 0.0,
        is_historical: bool = False,
        has_errors: bool = False,
        **kwargs: Any,
    ) -> str:
        pair_data = pair_data or []
        missing_pairs = missing_pairs or []
        holiday_hits = holiday_hits or []
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

        pair_groups = _prepare_pair_groups(pair_data)

        ctx = {
            "mode": "Historical" if is_historical else "Live",
            "has_errors": has_errors,
            "pipeline_name": pipeline_name,
            "date_str": date_str,
            "day_name": day_name,
            "run_time_utc": run_time_utc,
            "run_time_sgt": run_time_sgt,
            "elapsed": elapsed,
            "n_pairs": n_pairs,
            "rows_extracted": rows_extracted,
            "rows_loaded": rows_loaded,
            "n_missing": len(missing_pairs),
            "n_holidays": len(holiday_hits),
            "n_quality_flags": len([q for q in quality_flags if q.get("status") != "passed"]),
            "health_passed": health_passed,
            "health_details": health_details,
            "pair_groups": pair_groups,
            "quality_flags": quality_flags,
            "missing_pairs": missing_pairs,
            "holiday_hits": holiday_hits,
        }
        return self._template.render(**ctx)
