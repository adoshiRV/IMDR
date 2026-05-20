"""Teams Adaptive Card poster via Workflows incoming webhook.

Targets the Power Automate flow created in a channel via
"Workflows" → "Post to a channel when a webhook request is received".
That flow accepts the same `{type: "message", attachments: [...]}` envelope
that the old Office 365 connector used, so the only thing the caller needs
to provide is the Adaptive Card body.

Use:
    from imdr.notifications.teams import post_adaptive_card
    post_adaptive_card(webhook_url, card_body)

where `card_body` is the Adaptive Card content dict (everything that sits
under `attachments[0].content`). This module wraps it in the message
envelope and POSTs as JSON.
"""

from __future__ import annotations

from typing import Any

import requests
import structlog

log = structlog.get_logger(__name__)


def post_adaptive_card(
    webhook_url: str,
    card_body: dict[str, Any],
    *,
    timeout: int = 30,
) -> bool:
    """POST an Adaptive Card to a Teams Workflows webhook.

    Returns True on 2xx, False otherwise. Errors are logged, not raised, so
    a notification failure never blocks the caller (the snapshot HTML is
    still written and email/SharePoint paths are independent).
    """
    if not webhook_url:
        log.warning("teams_webhook_missing", msg="webhook URL is empty — skipping post")
        return False

    payload = {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "contentUrl": None,
                "content": card_body,
            }
        ],
    }
    try:
        resp = requests.post(webhook_url, json=payload, timeout=timeout)
    except requests.RequestException:
        log.exception("teams_post_failed")
        return False

    if 200 <= resp.status_code < 300:
        log.info("teams_post_sent", status=resp.status_code)
        return True
    log.warning(
        "teams_post_rejected",
        status=resp.status_code,
        body=resp.text[:500],
    )
    return False
