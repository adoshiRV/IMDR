"""Rates swaption skew ingest email formatter — Jinja2 + inline CSS for Outlook emails."""
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


class RatesSkewIngestFormatter:
    """Formats HTML emails for rates swaption skew load results."""

    def __init__(self) -> None:
        self._env = Environment(
            loader=FileSystemLoader(str(_TEMPLATE_DIR)),
            autoescape=True,
        )
        self._template = self._env.get_template("rates_skew_ingest.html")

    def format_subject(
        self,
        rows_loaded: int = 0,
        n_expiries: int = 0,
        has_errors: bool = False,
        start: Any = None,
        end: Any = None,
        **kwargs: Any,
    ) -> str:
        status = "ERROR" if has_errors else "OK"
        date_range = f"{start or 'all'} to {end or 'all'}"
        return (
            f"[IMDR] Rates Skew Load {status} | {date_range} "
            f"| {n_expiries} expiries / {rows_loaded:,} obs"
        )

    def format_body(
        self,
        rows_extracted: int = 0,
        rows_loaded: int = 0,
        n_files: int = 0,
        file_names: list[str] | None = None,
        expiry_data: list[dict[str, Any]] | None = None,
        has_errors: bool = False,
        elapsed_secs: float = 0.0,
        start: Any = None,
        end: Any = None,
        **kwargs: Any,
    ) -> str:
        file_names = file_names or []
        expiry_data = expiry_data or []

        now_utc = datetime.now(timezone.utc)
        run_time_utc = now_utc.strftime("%Y-%m-%d %H:%M:%S UTC")
        run_time_sgt = _to_sgt(now_utc).strftime("%H:%M:%S SGT")
        elapsed = f"{elapsed_secs:.1f}s" if elapsed_secs else "N/A"

        ctx = {
            "has_errors": has_errors,
            "run_time_utc": run_time_utc,
            "run_time_sgt": run_time_sgt,
            "elapsed": elapsed,
            "n_files": n_files,
            "file_names": file_names,
            "rows_extracted": rows_extracted,
            "rows_loaded": rows_loaded,
            "n_expiries": len(expiry_data),
            "expiry_data": expiry_data,
            "date_range": f"{start or 'all'} to {end or 'all'}",
        }
        return self._template.render(**ctx)
