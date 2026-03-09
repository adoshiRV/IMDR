"""FX time utilities — hour windows, alignment, market open checks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass(frozen=True)
class HourWindow:
    """A one-hour UTC window [start, end)."""

    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        if self.end <= self.start:
            msg = f"end ({self.end}) must be after start ({self.start})"
            raise ValueError(msg)

    def __str__(self) -> str:
        return f"{self.start:%Y-%m-%d %H:00}-{self.end:%H:00} UTC"


def align_to_hour(dt: datetime) -> datetime:
    """Truncate a datetime to the start of its hour."""
    return dt.replace(minute=0, second=0, microsecond=0)


def last_full_utc_hour(now: datetime | None = None) -> HourWindow:
    """Return the most recently completed full UTC hour window.

    E.g. if now is 14:23 UTC, returns HourWindow(13:00, 14:00).
    """
    if now is None:
        now = datetime.now(timezone.utc)
    end = align_to_hour(now)
    start = end - timedelta(hours=1)
    return HourWindow(start=start, end=end)


def iter_hour_windows(start: datetime, end: datetime) -> list[HourWindow]:
    """Generate a list of HourWindows from start to end (exclusive).

    Both start and end are aligned to hour boundaries.
    """
    start = align_to_hour(start)
    end = align_to_hour(end)
    windows = []
    current = start
    while current < end:
        next_hour = current + timedelta(hours=1)
        windows.append(HourWindow(start=current, end=next_hour))
        current = next_hour
    return windows
