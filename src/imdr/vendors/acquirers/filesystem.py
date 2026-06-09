"""LocalFilesystemAcquirer — read pre-staged files from a local/network path.

Pattern: a third-party process (e.g. the R-based BBG fetcher on a separate
PC) drops files onto a shared fileshare; IMDR's only job is to discover
and read them on a schedule. There is no auth, no download, no portal —
just glob + mtime checks.

Reference feed: ``bbg_fx_snapshot`` reads ``Z:\\...\\BBG\\FX\\{CCY}\\FX_{CCY}.csv``
6x daily.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

from imdr.vendors.base import FetchResult, utcnow
from imdr.vendors.exceptions import ListingNotFound

if TYPE_CHECKING:
    from imdr.reporting.run_report import RunReport

log = structlog.get_logger(__name__)


@dataclass(frozen=True)
class LocalFilesystemSpec:
    """Declarative description of a filesystem-poll feed."""

    name: str                               # registry key, e.g. "bbg_fx_snapshot"
    vendor_code: str                        # FK to dbo.dim_vendor.vendor_code
    root: Path                              # base directory containing files
    patterns: list[str] = field(default_factory=list)
    # Glob patterns relative to ``root``. Any single match is sufficient if
    # ``min_matches`` is 1; raise ListingNotFound if total < ``min_matches``.

    min_mtime_age: timedelta | None = None
    # Reject files whose mtime is older than ``utcnow() - min_mtime_age``.
    # None = no freshness check (any file matches).

    min_matches: int = 1
    # Minimum total file count across all patterns. Below this raises ListingNotFound.

    follow_symlinks: bool = False


class LocalFilesystemAcquirer:
    """Discover files on disk matching a glob; do not copy or modify them."""

    def __init__(self, spec: LocalFilesystemSpec) -> None:
        self.spec = spec
        self.name = spec.name

    def fetch(
        self,
        *,
        headless: bool = True,  # ignored; kept for Acquirer Protocol compat
        report: "RunReport | None" = None,
    ) -> FetchResult:
        started_at = utcnow()
        spec = self.spec

        if report is not None:
            report.info(
                category="acquire",
                message="filesystem_scan_start",
                details={"root": str(spec.root), "patterns": spec.patterns},
            )

        if not spec.root.exists():
            raise ListingNotFound(
                f"{spec.name}: root path does not exist: {spec.root}"
            )

        matched: list[Path] = []
        for pattern in spec.patterns:
            for path in spec.root.glob(pattern):
                if path.is_file():
                    matched.append(path)

        # Dedup and sort for stable ordering across runs
        matched = sorted(set(matched))

        # Freshness filter
        warnings: list[str] = []
        if spec.min_mtime_age is not None:
            cutoff = utcnow() - spec.min_mtime_age
            fresh: list[Path] = []
            for p in matched:
                mtime = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
                if mtime >= cutoff:
                    fresh.append(p)
                else:
                    warnings.append(
                        f"stale file (mtime={mtime.isoformat()} < {cutoff.isoformat()}): {p}"
                    )
            matched = fresh

        if len(matched) < spec.min_matches:
            raise ListingNotFound(
                f"{spec.name}: matched {len(matched)} files, "
                f"need >= {spec.min_matches}. root={spec.root} patterns={spec.patterns}"
            )

        bytes_total = sum(p.stat().st_size for p in matched)

        if report is not None:
            report.info(
                category="acquire",
                message="filesystem_scan_complete",
                details={
                    "matched": len(matched),
                    "bytes": bytes_total,
                    "warnings": len(warnings),
                },
            )

        return FetchResult(
            vendor=spec.vendor_code,
            feed=spec.name,
            saved_files=matched,
            bytes_downloaded=bytes_total,
            started_at=started_at,
            finished_at=utcnow(),
            warnings=warnings,
        )
