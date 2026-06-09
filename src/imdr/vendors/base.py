"""Core types for the vendors framework.

``Acquirer`` is a Protocol — any class with a ``name`` attribute and a
``fetch(headless, report) -> FetchResult`` method satisfies it.  This
matches the ``EmailFormatter`` Protocol convention already used in
``imdr.notifications.formatters.base`` and avoids a subclassing ladder
as new acquirer types are added.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Protocol, runtime_checkable

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from imdr.config.settings import Settings
    from imdr.connectors.mssql import MSSQLConnector
    from imdr.notifications.formatters.base import EmailFormatter
    from imdr.pipelines.base import BasePipeline
    from imdr.reporting.run_report import RunReport


class FetchResult(BaseModel):
    """Outcome of an ``Acquirer.fetch()`` call."""

    vendor: str
    feed: str
    saved_files: list[Path] = Field(default_factory=list)
    bytes_downloaded: int = 0
    started_at: datetime
    finished_at: datetime
    warnings: list[str] = Field(default_factory=list)

    model_config = {"arbitrary_types_allowed": True}

    @property
    def elapsed_s(self) -> float:
        return (self.finished_at - self.started_at).total_seconds()

    @property
    def ok(self) -> bool:
        return bool(self.saved_files)


@runtime_checkable
class Acquirer(Protocol):
    """Fetches raw artefacts from an external source into a staging area."""

    name: str

    def fetch(
        self,
        *,
        headless: bool = True,
        report: "RunReport | None" = None,
    ) -> FetchResult: ...


# A builder that constructs a concrete BasePipeline given the acquired files.
# Declared as Callable (not a Protocol) because the signature is simple and
# the runner never introspects it beyond calling it.
PipelineBuilder = Callable[
    [list[Path], "MSSQLConnector", "Settings"],
    "BasePipeline[Any, Any, Any]",
]

# Optional hook used by the runner to enrich the success email.  Given the
# finished pipeline and its row count, returns extra kwargs merged into the
# success formatter's ``format_body(**ctx)`` call — lets per-feed summaries
# (e.g. per-expiry breakdown for skew) flow into the email without bloating
# the runner with feed-specific logic.
SuccessContextBuilder = Callable[
    ["BasePipeline[Any, Any, Any]", int],
    dict[str, Any],
]


@dataclass(frozen=True)
class VendorFeed:
    """A registered daily vendor feed.

    Binds together:
      - ``acquirer``: how to get the raw files
      - ``pipeline_builder``: how to construct the loader pipeline from those files
      - ``success_formatter``: how to render the success email
      - ``staleness_pipeline_name``: log correlation key (also used by the
        staleness monitor to correlate fact tables with the pipeline that
        feeds them).
      - ``success_context_builder`` (optional): hook to enrich the success
        email with feed-specific metrics extracted from the finished pipeline.
    """

    name: str
    vendor_code: str
    acquirer: Acquirer
    pipeline_builder: PipelineBuilder
    success_formatter: "EmailFormatter"
    staleness_pipeline_name: str
    success_context_builder: SuccessContextBuilder | None = None
    archive_after_load: bool = True
    # Set False when the acquirer's source files are owned by an external
    # process that overwrites them in place (e.g. the BBG R pipeline). Moving
    # the file would break the next poll. Default True suits feeds like
    # ``barclays_skew`` that download fresh artefacts each day.
    email_on_zero_rows: bool = True
    # Set False for high-cadence pollers where most fires are MERGE no-ops
    # (e.g. BBG snapshot polled every 30 min). Default True preserves the
    # existing one-email-per-run contract for daily feeds.


def utcnow() -> datetime:
    """Tz-aware UTC now — shared helper so acquirers don't each reinvent it."""
    return datetime.now(timezone.utc)
