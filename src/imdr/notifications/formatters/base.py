"""Email formatter protocol."""

from __future__ import annotations

from typing import Any, Protocol


class EmailFormatter(Protocol):
    """Protocol for email body formatters."""

    def format_subject(self, **kwargs: Any) -> str:
        """Generate the email subject line."""
        ...

    def format_body(self, **kwargs: Any) -> str:
        """Generate the HTML email body."""
        ...
