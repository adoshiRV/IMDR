"""SFtpAcquirer — SCAFFOLD.

Intended for vendors that drop files on an SFTP endpoint.  Will use
``paramiko`` (not currently a project dependency) with credentials
resolved via ``imdr.vendors.credentials``.

Not implemented yet.  See ``docs/admin/vendors/sftp.md``.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SFtpSpec:
    """Placeholder spec."""

    name: str
    vendor_code: str
    host: str
    port: int
    remote_dir: str
    filename_glob: str
    output_dir: Path
    credentials_prefix: str


class SFtpAcquirer:
    """Placeholder class — see module docstring."""

    def __init__(self, spec: SFtpSpec) -> None:
        self.spec = spec
        self.name = spec.name

    def fetch(self, *, headless: bool = True, report=None):  # type: ignore[no-untyped-def]
        raise NotImplementedError(
            "SFtpAcquirer is scaffolded but not implemented. "
            "See docs/admin/vendors/sftp.md."
        )
