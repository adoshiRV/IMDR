"""Email dispatch for research-auth events.

Single entry point :func:`send_auth_email` that:

1. Resolves the recipient — prefers ``Settings.email_anomaly_to``
   (currently dormant elsewhere; we activate it here for research-auth
   alerts) and falls back to ``Settings.email_to``.
2. Gates on ``Settings.email_enabled`` — silently no-ops when False.
3. Dispatches to the matching formatter by ``kind``.
4. Calls :func:`imdr.notifications.email.send_outlook_email`.
5. Returns True iff the email was actually sent; never raises.

Three event ``kind`` values are wired today:

* ``"validate_summary"`` — end-of-run summary after
  ``python -m imdr.research.auth validate --vendor all``.
* ``"login_failed"`` — emitted by ``context.get_authed_context`` when
  a programmatic login raises (env-gated by
  ``IMDR_RESEARCH_AUTH_EMAIL_ON_AUTH_FAILURE``).
* ``"needs_human"`` — emitted by ``scripts/imdr_session_heartbeat.py``
  when any vendor returned ``EXPIRED`` and cannot self-recover.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

import structlog

log = structlog.get_logger(__name__)


# Formatter dispatch — each entry is (subject_fn, body_fn) keyed by event
# kind. Late-imported so we don't pay the Jinja2 environment cost for
# callers that never trigger an email.
_FormatterPair = tuple[Callable[..., str], Callable[..., str]]


def _formatters() -> dict[str, _FormatterPair]:
    from imdr.notifications.formatters.research_auth_login_failed import (
        ResearchAuthLoginFailedFormatter,
    )
    from imdr.notifications.formatters.research_auth_needs_human import (
        ResearchAuthNeedsHumanFormatter,
    )
    from imdr.notifications.formatters.research_auth_validate import (
        ResearchAuthValidateFormatter,
    )

    validate = ResearchAuthValidateFormatter()
    login_failed = ResearchAuthLoginFailedFormatter()
    needs_human = ResearchAuthNeedsHumanFormatter()
    return {
        "validate_summary": (validate.format_subject, validate.format_body),
        "login_failed": (login_failed.format_subject, login_failed.format_body),
        "needs_human": (needs_human.format_subject, needs_human.format_body),
    }


def _resolve_recipient(settings: Any) -> str:
    """Prefer ``email_anomaly_to``; fall back to ``email_to``."""
    anomaly = (settings.email_anomaly_to or "").strip()
    if anomaly:
        return anomaly
    return (settings.email_to or "").strip()


def send_auth_email(
    *,
    kind: str,
    dry_run: bool = False,
    **context: Any,
) -> bool:
    """Render + (optionally) send a research-auth alert email.

    Parameters
    ----------
    kind
        One of ``"validate_summary"``, ``"login_failed"``, ``"needs_human"``.
    dry_run
        When True, render the subject + body but do NOT call
        :func:`send_outlook_email`. Returns True. Useful for operator
        preview of the HTML payload.
    **context
        Formatter-specific kwargs. Each formatter documents its keys.

    Returns
    -------
    bool
        True iff the email was rendered AND (in non-dry-run mode)
        actually sent. False when:

        * ``Settings.email_enabled`` is False.
        * No recipient is configured.
        * The formatter ``kind`` is unknown.
        * Rendering or sending raised — caught internally; the
          original auth flow takes priority.

    Never raises.
    """
    try:
        from imdr.config.settings import get_settings

        settings = get_settings()
    except Exception as exc:
        log.warning("auth_email_settings_unavailable", error=str(exc)[:200])
        return False

    if not settings.email_enabled and not dry_run:
        log.debug("auth_email_skipped_disabled", kind=kind)
        return False

    recipient = _resolve_recipient(settings)
    if not recipient and not dry_run:
        log.debug("auth_email_skipped_no_recipient", kind=kind)
        return False

    try:
        formatters = _formatters()
    except Exception as exc:
        log.warning("auth_email_formatter_import_failed", error=str(exc)[:200])
        return False

    pair = formatters.get(kind)
    if pair is None:
        log.warning("auth_email_unknown_kind", kind=kind)
        return False
    subject_fn, body_fn = pair

    try:
        subject = subject_fn(**context)
        body = body_fn(**context)
    except Exception as exc:
        log.warning(
            "auth_email_render_failed",
            kind=kind,
            error_type=type(exc).__name__,
            error=str(exc)[:200],
        )
        return False

    if dry_run:
        log.info("auth_email_dry_run", kind=kind, subject=subject)
        # Print to stdout so the operator can copy/inspect the HTML.
        print(f"--- email (dry-run, kind={kind}) ---")
        print(f"To: {recipient or '(no recipient configured)'}")
        print(f"Subject: {subject}")
        print(body)
        print("--- end ---")
        return True

    try:
        from imdr.notifications.email import send_outlook_email

        ok = send_outlook_email(
            to=recipient,
            subject=subject,
            html_body=body,
            importance=2 if kind in {"login_failed", "needs_human"} else 1,
        )
        return bool(ok)
    except Exception as exc:
        log.warning(
            "auth_email_send_raised",
            kind=kind,
            error_type=type(exc).__name__,
            error=str(exc)[:200],
        )
        return False


__all__ = ["send_auth_email"]
