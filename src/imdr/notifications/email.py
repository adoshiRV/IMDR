"""Outlook email sender via win32com — domain-agnostic."""

from __future__ import annotations

import structlog

log = structlog.get_logger(__name__)


def send_outlook_email(
    to: str,
    subject: str,
    html_body: str,
    cc: str = "",
    importance: int = 1,
) -> bool:
    """Send an email via Outlook COM automation.

    Args:
        to: Semicolon-separated recipient addresses.
        subject: Email subject line.
        html_body: HTML body content.
        cc: Semicolon-separated CC addresses (optional).
        importance: 0=low, 1=normal, 2=high.

    Returns:
        True if sent successfully, False otherwise.
    """
    try:
        import win32com.client  # type: ignore[import-untyped]

        outlook = win32com.client.Dispatch("Outlook.Application")
        mail = outlook.CreateItem(0)
        mail.To = to
        if cc:
            mail.CC = cc
        mail.Subject = subject
        mail.HTMLBody = html_body
        mail.Importance = importance
        mail.Send()
        log.info("email_sent", to=to, subject=subject)
        return True
    except ImportError:
        log.warning("win32com_not_available", msg="pywin32 not installed — email not sent")
        return False
    except Exception:
        log.exception("email_send_failed", to=to, subject=subject)
        return False
