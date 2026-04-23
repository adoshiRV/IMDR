"""HttpPollAcquirer — SCAFFOLD.

Intended for authenticated REST feeds that don't fit the single-service
clients in ``imdr/connectors/`` (e.g. S&P Global, ICE).  Will reuse
``imdr.connectors.http.HTTPClient`` underneath.

Not implemented yet.  See ``docs/admin/vendors/http_poll.md``.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class HttpPollSpec:
    """Placeholder spec."""

    name: str
    vendor_code: str
    base_url: str
    paths: tuple[str, ...]
    output_dir: Path
    credentials_prefix: str


class HttpPollAcquirer:
    """Placeholder class — see module docstring."""

    def __init__(self, spec: HttpPollSpec) -> None:
        self.spec = spec
        self.name = spec.name

    def fetch(self, *, headless: bool = True, report=None):  # type: ignore[no-untyped-def]
        raise NotImplementedError(
            "HttpPollAcquirer is scaffolded but not implemented. "
            "See docs/admin/vendors/http_poll.md."
        )
