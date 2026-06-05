"""Holiday calendar weekly-load email formatter.

Confirms the weekly merge of the canonical BBG holiday-calendar snapshot
(``calendar_YYYYMMDD.xlsx``) into ``calendar.market_holidays``. Produced by
``scripts.calendar.import_latest_holiday_calendar_snapshot``."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

_SGT = timezone(timedelta(hours=8))
_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"

_BANNER_COLOR = {
    "OK": "#2e7d32",
    "PARTIAL": "#f57c00",
    "FAIL": "#d32f2f",
}


def _to_sgt(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(_SGT)


def _status(inserted: int, missing: list[str], error: str) -> str:
    if error:
        return "FAIL"
    if missing:
        return "PARTIAL"
    return "OK"


class HolidayCalendarIngestFormatter:
    """HTML email formatter for the weekly canonical holiday-calendar load
    into ``calendar.market_holidays``."""

    def __init__(self) -> None:
        self._env = Environment(
            loader=FileSystemLoader(str(_TEMPLATE_DIR)),
            autoescape=True,
        )
        self._template = self._env.get_template("holiday_calendar_ingest.html")

    def format_subject(
        self,
        snapshot_date: str = "",
        inserted: int = 0,
        calendars: int = 0,
        missing: list[str] | None = None,
        error: str = "",
        **kwargs: Any,
    ) -> str:
        status = _status(inserted, missing or [], error)
        return (
            f"[IMDR] Holiday Calendar Weekly Load {status} "
            f"| {inserted} new / {calendars} calendars "
            f"| snapshot {snapshot_date}"
        )

    def format_body(
        self,
        snapshot_path: str = "",
        snapshot_date: str = "",
        run_time_utc: datetime | None = None,
        duration_s: float = 0.0,
        calendars: int = 0,
        total_parsed: int = 0,
        inserted: int = 0,
        skipped: int = 0,
        load_batch: str = "",
        rows: list[dict[str, Any]] | None = None,
        missing: list[str] | None = None,
        error: str = "",
        **kwargs: Any,
    ) -> str:
        if run_time_utc is None:
            run_time_utc = datetime.now(timezone.utc)
        status = _status(inserted, missing or [], error)
        return self._template.render(
            snapshot_path=snapshot_path,
            snapshot_date=snapshot_date,
            run_time_utc=run_time_utc.strftime("%Y-%m-%d %H:%M:%S UTC"),
            run_time_sgt=_to_sgt(run_time_utc).strftime("%Y-%m-%d %H:%M:%S SGT"),
            duration_s=f"{duration_s:.2f}",
            calendars=calendars,
            total_parsed=total_parsed,
            inserted=inserted,
            skipped=skipped,
            load_batch=load_batch,
            rows=rows or [],
            missing=missing or [],
            error=error,
            status=status,
            banner_color=_BANNER_COLOR.get(status, "#1a237e"),
        )
