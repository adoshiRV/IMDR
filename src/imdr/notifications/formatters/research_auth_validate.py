"""End-of-run summary formatter for the ``validate --vendor all`` flow.

Subject: ``[IMDR] Research auth validate — {n_pass}/{n_total} passed``

Body context keys (passed through :func:`send_auth_email`):

* ``n_pass``: int — vendors that returned SUCCESS
* ``n_total``: int — vendors run
* ``outcomes``: list of dicts, each with keys:
    - ``vendor``: str
    - ``mode``: str (registry value, e.g. ``"programmatic"``)
    - ``status``: str (SessionStatus value)
    - ``smoke``: str — ``"PASS"`` or ``"BLOCKED"``
    - ``elapsed_s``: float
    - ``reason``: str (empty on PASS; populated on BLOCKED)
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

_SGT = timezone(timedelta(hours=8))
_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"


def _to_sgt(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(_SGT)


class ResearchAuthValidateFormatter:
    """Renders the validate-summary email."""

    def __init__(self) -> None:
        self._env = Environment(
            loader=FileSystemLoader(str(_TEMPLATE_DIR)),
            autoescape=True,
        )
        self._template = self._env.get_template("research_auth_validate.html")

    def format_subject(
        self,
        *,
        n_pass: int = 0,
        n_total: int = 0,
        **_kwargs: Any,
    ) -> str:
        return f"[IMDR] Research auth validate — {n_pass}/{n_total} passed"

    def format_body(
        self,
        *,
        n_pass: int = 0,
        n_total: int = 0,
        outcomes: list[dict[str, Any]] | None = None,
        **_kwargs: Any,
    ) -> str:
        now_utc = datetime.now(UTC)
        return self._template.render(
            n_pass=n_pass,
            n_total=n_total,
            n_blocked=max(0, n_total - n_pass),
            outcomes=outcomes or [],
            run_time_utc=now_utc.strftime("%Y-%m-%d %H:%M:%S UTC"),
            run_time_sgt=_to_sgt(now_utc).strftime("%H:%M:%S SGT"),
        )


__all__ = ["ResearchAuthValidateFormatter"]
