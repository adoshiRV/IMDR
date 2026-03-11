"""Rates domain utilities — date formatters, converters, and re-exports.

Ported from RATES_data/src/utils.py (selective).
parse_x_to_ts_utc moved to connectors.citi_helpers — re-exported for backward compat.
"""
from __future__ import annotations

from datetime import datetime, timezone

from imdr.connectors.citi_helpers import parse_x_to_ts_utc  # noqa: F401
from imdr.schemas.rates import RatesCurveCreate
from imdr.universe.rates import CurveEntry


def curve_entry_to_create(entry: CurveEntry) -> RatesCurveCreate:
    """Convert a universe CurveEntry to a RatesCurveCreate schema object."""
    citi = entry.providers.get("citi", {})
    return RatesCurveCreate(
        ccy=entry.ccy,
        curve=entry.curve,
        curve_type=entry.type,
        curve_status=entry.status,
        instrument=citi.get("instrument", ""),
        citi_prefix=citi.get("prefix", ""),
        cessation_date=entry.cessation,
        primary_from=entry.primary_from,
        supersedes=entry.supersedes,
        superseded_by=entry.superseded_by,
        notes=entry.notes,
    )


def parse_iso_utc(s: str) -> datetime:
    """Parse ISO8601 with 'Z' or offset. Returns tz-aware UTC."""
    s = s.strip().replace(" ", "T")
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def yyyymmdd(dt: datetime) -> int:
    return int(dt.astimezone(timezone.utc).strftime("%Y%m%d"))


def hhmm(dt: datetime) -> int:
    return int(dt.astimezone(timezone.utc).strftime("%H%M"))
