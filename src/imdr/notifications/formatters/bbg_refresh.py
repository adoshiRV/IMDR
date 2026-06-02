"""BBG Terminal refresh email formatter — one mail per refresh run."""

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


def _status(n_ok: int, n_total: int) -> str:
    if n_total == 0:
        return "FAIL"
    if n_ok == n_total:
        return "OK"
    if n_ok == 0:
        return "FAIL"
    return "PARTIAL"


class BBGRefreshFormatter:
    """HTML email formatter for a single BBG terminal refresh run."""

    def __init__(self) -> None:
        self._env = Environment(
            loader=FileSystemLoader(str(_TEMPLATE_DIR)),
            autoescape=True,
        )
        self._template = self._env.get_template("bbg_refresh.html")

    def format_subject(
        self,
        user: str = "",
        schedule: str = "",
        run_time_utc: datetime | None = None,
        n_ok: int = 0,
        n_total: int = 0,
        **kwargs: Any,
    ) -> str:
        status = _status(n_ok, n_total)
        mode = schedule.capitalize() if schedule else "Refresh"
        date_str = run_time_utc.strftime("%Y-%m-%d %H:%M") if run_time_utc else "N/A"
        return (
            f"[IMDR] Bloomberg Terminal — {mode} Refresh {status} "
            f"| {user} | {n_ok}/{n_total} tickers | {date_str} UTC"
        )

    def format_body(
        self,
        user: str = "",
        host: str = "",
        schedule: str = "",
        run_time_utc: datetime | None = None,
        duration_s: float = 0.0,
        n_ok: int = 0,
        n_total: int = 0,
        rows: list[dict[str, Any]] | None = None,
        errors: list[tuple[str, str]] | None = None,
        output_path: str = "",
        **kwargs: Any,
    ) -> str:
        if run_time_utc is None:
            run_time_utc = datetime.now(timezone.utc)
        status = _status(n_ok, n_total)
        n_failed = n_total - n_ok

        mode = schedule.capitalize() if schedule else "Refresh"
        return self._template.render(
            user=user,
            host=host,
            schedule=schedule,
            mode=mode,
            run_time_utc=run_time_utc.strftime("%Y-%m-%d %H:%M:%S UTC"),
            run_time_sgt=_to_sgt(run_time_utc).strftime("%Y-%m-%d %H:%M:%S SGT"),
            duration_s=f"{duration_s:.2f}",
            n_ok=n_ok,
            n_total=n_total,
            n_failed=n_failed,
            rows=rows or [],
            errors=errors or [],
            output_path=output_path,
            status=status,
            banner_color=_BANNER_COLOR.get(status, "#1a237e"),
        )
