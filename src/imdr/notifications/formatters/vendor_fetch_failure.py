"""Generic failure-email formatter for the vendors framework.

Used for any ``VendorError`` raised during acquire or load.  Unlike the
per-feed success formatters, this one is vendor-neutral: every feed in
``imdr.vendors`` uses the same subject + body shape for failures so
ops can scan them uniformly.
"""
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


class VendorFetchFailureFormatter:
    """Formats the vendor-failure HTML email."""

    def __init__(self) -> None:
        self._env = Environment(
            loader=FileSystemLoader(str(_TEMPLATE_DIR)),
            autoescape=True,
        )
        self._template = self._env.get_template("vendor_fetch_failure.html")

    def format_subject(
        self,
        feed_name: str = "",
        error_type: str = "",
        **kwargs: Any,
    ) -> str:
        return f"[IMDR] Vendor Feed FAILED — {feed_name} ({error_type})"

    def format_body(
        self,
        feed_name: str = "",
        vendor_code: str = "",
        phase: str = "",
        error_type: str = "",
        error_message: str = "",
        details: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> str:
        now_utc = datetime.now(timezone.utc)
        ctx = {
            "feed_name": feed_name,
            "vendor_code": vendor_code,
            "phase": phase,
            "error_type": error_type,
            "error_message": error_message,
            "details": details or {},
            "run_time_utc": now_utc.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "run_time_sgt": _to_sgt(now_utc).strftime("%H:%M:%S SGT"),
        }
        return self._template.render(**ctx)
