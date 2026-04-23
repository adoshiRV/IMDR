"""EmailLinkedDownloadAcquirer — the reference acquirer.

Pattern: vendor sends a daily email containing a link to an
authenticated portal page; portal page lists one or more files to
download.  This acquirer scans Outlook for the email, opens the portal
in a persistent Chrome profile (SSO cookie already present or prompted
on first run), and saves every linked file to ``spec.output_dir``.

Barclays SKEW is the current reference implementation.  Future vendors
using the same shape add a spec; no new acquirer code.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import structlog

from imdr.config.settings import Settings, get_settings
from imdr.vendors.base import FetchResult, utcnow
from imdr.vendors.exceptions import NoEmailFound
from imdr.vendors.sessions import BrowserSession, OutlookClient, Win32OutlookClient

if TYPE_CHECKING:
    from imdr.reporting.run_report import RunReport

log = structlog.get_logger(__name__)


@dataclass(frozen=True)
class EmailLinkedDownloadSpec:
    """Declarative description of a single email-linked download feed."""

    name: str                              # registry key, e.g. "barclays_skew"
    vendor_code: str                       # FK to dbo.dim_vendor.vendor_code
    sender: str                            # "csa@barcap.com"
    subject_contains: str                  # "SKEW BARCLAYS"
    link_label: str                        # bold row label preceding the link, e.g. "View Excel"
    listing_anchor_selector: str           # CSS selector inside the portal frame
    output_dir: Path                       # where downloaded files land
    profile_name: str                      # sub-dir under settings.browser_profile_root
    filename_from: Literal["anchor", "server"] = "anchor"
    days_back: int = 2
    newest_only: bool = True
    sso_timeout_s: float = 300.0


class EmailLinkedDownloadAcquirer:
    """Acquirer implementation for the email-linked-download pattern."""

    def __init__(
        self,
        spec: EmailLinkedDownloadSpec,
        *,
        outlook: OutlookClient | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.spec = spec
        self.name = spec.name
        self._outlook = outlook or Win32OutlookClient()
        self._settings = settings or get_settings()

    def fetch(
        self,
        *,
        headless: bool = True,
        report: "RunReport | None" = None,
    ) -> FetchResult:
        started_at = utcnow()
        spec = self.spec

        emails = self._outlook.find_matching(
            sender=spec.sender,
            subject_contains=spec.subject_contains,
            days_back=spec.days_back,
            link_label=spec.link_label,
        )
        if report is not None:
            report.info(
                "vendor_fetch.scan",
                f"{len(emails)} candidate email(s)",
                details={"feed": spec.name, "sender": spec.sender, "days_back": spec.days_back},
            )
        if not emails:
            raise NoEmailFound(
                f"No {spec.subject_contains!r} from {spec.sender!r} in last {spec.days_back}d"
            )

        targets = emails[:1] if spec.newest_only else emails
        profile_dir = self._settings.browser_profile_root / spec.profile_name
        spec.output_dir.mkdir(parents=True, exist_ok=True)

        saved: list[Path] = []
        warnings: list[str] = []
        total_bytes = 0

        with BrowserSession(profile_dir, headless=headless) as session:
            for email in targets:
                files, nbytes = session.download_anchors(
                    listing_url=email.link_url,
                    selector=spec.listing_anchor_selector,
                    output_dir=spec.output_dir,
                    filename_rule=spec.filename_from,
                    sso_timeout_s=spec.sso_timeout_s,
                )
                saved.extend(files)
                total_bytes += nbytes
                if report is not None:
                    report.info(
                        "vendor_fetch.download",
                        f"{len(files)} file(s) from {email.subject!r}",
                        details={
                            "bytes": nbytes,
                            "received": email.received.isoformat(),
                            "feed": spec.name,
                        },
                    )
                log.info(
                    "email_linked_download_batch",
                    feed=spec.name,
                    saved=len(files),
                    bytes=nbytes,
                )

        return FetchResult(
            vendor=spec.vendor_code,
            feed=spec.name,
            saved_files=saved,
            bytes_downloaded=total_bytes,
            started_at=started_at,
            finished_at=utcnow(),
            warnings=warnings,
        )
