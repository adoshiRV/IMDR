"""Single-vendor login-failure formatter.

Emitted by :func:`imdr.research.auth.context.get_authed_context` when
a programmatic login raises (env-gated by
``IMDR_RESEARCH_AUTH_EMAIL_ON_AUTH_FAILURE``).

Subject: ``[IMDR] Research auth FAILED — {vendor} ({error_type})``

Body context keys:

* ``vendor``: str — vendor code
* ``mode``: str — registry mode value
* ``healthcheck_url``: str
* ``error_type``: str — exception class name (e.g. ``LoginFailedError``)
* ``error_message``: str — ``str(exc)``
* ``recoverable``: bool — from ``exc.recoverable``
* ``mfa_kind``: str — empty unless the exception is :class:`MFARequired`
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


class ResearchAuthLoginFailedFormatter:
    """Renders the per-vendor login-failure email."""

    def __init__(self) -> None:
        self._env = Environment(
            loader=FileSystemLoader(str(_TEMPLATE_DIR)),
            autoescape=True,
        )
        self._template = self._env.get_template("research_auth_login_failed.html")

    def format_subject(
        self,
        *,
        vendor: str = "",
        error_type: str = "",
        **_kwargs: Any,
    ) -> str:
        return f"[IMDR] Research auth FAILED — {vendor} ({error_type})"

    def format_body(
        self,
        *,
        vendor: str = "",
        mode: str = "",
        healthcheck_url: str = "",
        error_type: str = "",
        error_message: str = "",
        recoverable: bool = False,
        mfa_kind: str = "",
        **_kwargs: Any,
    ) -> str:
        now_utc = datetime.now(UTC)
        return self._template.render(
            vendor=vendor,
            mode=mode,
            healthcheck_url=healthcheck_url,
            error_type=error_type,
            error_message=error_message,
            recoverable=bool(recoverable),
            mfa_kind=mfa_kind,
            run_time_utc=now_utc.strftime("%Y-%m-%d %H:%M:%S UTC"),
            run_time_sgt=_to_sgt(now_utc).strftime("%H:%M:%S SGT"),
        )


__all__ = ["ResearchAuthLoginFailedFormatter"]
