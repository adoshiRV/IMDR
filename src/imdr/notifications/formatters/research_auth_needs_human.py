"""Heartbeat NEEDS_HUMAN formatter.

Emitted by :mod:`scripts.imdr_session_heartbeat` after
:func:`imdr.research.auth.refresh_all` finishes, when one or more
vendors returned EXPIRED and cannot self-recover (PROFILE_ONLY or
HEADER_INJECTION vendors that need a human to re-SSO).

Subject: ``[IMDR] Research session(s) need human re-auth — {n} vendor(s)``

Body context keys:

* ``outcomes``: list of dicts, each with keys:
    - ``vendor``: str
    - ``mode``: str
    - ``healthcheck_url``: str
    - ``detail``: str (best-effort error or status hint)
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


class ResearchAuthNeedsHumanFormatter:
    """Renders the heartbeat NEEDS_HUMAN email."""

    def __init__(self) -> None:
        self._env = Environment(
            loader=FileSystemLoader(str(_TEMPLATE_DIR)),
            autoescape=True,
        )
        self._template = self._env.get_template("research_auth_needs_human.html")

    def format_subject(
        self,
        *,
        outcomes: list[dict[str, Any]] | None = None,
        **_kwargs: Any,
    ) -> str:
        n = len(outcomes or [])
        return f"[IMDR] Research session(s) need human re-auth — {n} vendor(s)"

    def format_body(
        self,
        *,
        outcomes: list[dict[str, Any]] | None = None,
        **_kwargs: Any,
    ) -> str:
        now_utc = datetime.now(UTC)
        return self._template.render(
            outcomes=outcomes or [],
            n=len(outcomes or []),
            run_time_utc=now_utc.strftime("%Y-%m-%d %H:%M:%S UTC"),
            run_time_sgt=_to_sgt(now_utc).strftime("%H:%M:%S SGT"),
        )


__all__ = ["ResearchAuthNeedsHumanFormatter"]
