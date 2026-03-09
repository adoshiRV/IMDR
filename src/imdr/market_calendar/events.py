"""Custom market events loader — central bank, early close, data blackout."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path

import yaml

_EVENTS_PATH = Path(__file__).parent / "events.yml"


@dataclass
class MarketEvent:
    """A custom market event."""

    date: date
    market: str
    type: str  # central_bank, early_close, data_blackout
    description: str
    close_hour: int | None = None


@lru_cache(maxsize=1)
def _load_events(config_path: Path = _EVENTS_PATH) -> list[MarketEvent]:
    """Load all events from YAML."""
    with open(config_path) as f:
        raw = yaml.safe_load(f)

    events: list[MarketEvent] = []
    for entry in raw.get("events", []):
        evt_date = entry["date"]
        if isinstance(evt_date, str):
            evt_date = date.fromisoformat(evt_date)
        events.append(MarketEvent(
            date=evt_date,
            market=entry["market"],
            type=entry["type"],
            description=entry.get("description", ""),
            close_hour=entry.get("close_hour"),
        ))
    return events


def market_events_for_date(check_date: date, market: str | None = None) -> list[MarketEvent]:
    """Get market events for a specific date, optionally filtered by market."""
    events = _load_events()
    result = [e for e in events if e.date == check_date]
    if market:
        result = [e for e in result if e.market == market]
    return result
