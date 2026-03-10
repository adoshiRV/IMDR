"""Rates domain utilities — Citi x-axis timestamp parsing, date formatters.

Ported from RATES_data/src/utils.py (selective — 4 functions).
"""
from __future__ import annotations

from datetime import datetime, timezone


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


def parse_x_to_ts_utc(x: int) -> datetime:
    """
    Infer Citi x-axis format by digit count:
      6  → YYYYMM   (monthly) or YYYYww (weekly)
      8  → YYYYMMDD (daily)
      10 → YYYYMMDDHH (hourly)
      11 → YYYYMMDDHHm (ten-minutely, m = tens digit of minutes)
      12 → YYYYMMDDHHMM (minutely)
    """
    s = str(int(x))
    n = len(s)
    if n == 6:
        mm = int(s[4:6])
        if 1 <= mm <= 12:
            return datetime.strptime(s, "%Y%m").replace(tzinfo=timezone.utc)
        else:
            return datetime.strptime(s + "1", "%G%V%u").replace(tzinfo=timezone.utc)
    if n == 8:
        return datetime.strptime(s, "%Y%m%d").replace(tzinfo=timezone.utc)
    if n == 10:
        return datetime.strptime(s, "%Y%m%d%H").replace(tzinfo=timezone.utc)
    if n == 11:
        base = datetime.strptime(s[:10], "%Y%m%d%H").replace(tzinfo=timezone.utc)
        tens = int(s[10])
        return base.replace(minute=tens * 10)
    if n == 12:
        return datetime.strptime(s, "%Y%m%d%H%M").replace(tzinfo=timezone.utc)
    raise ValueError(f"Unrecognized x timestamp format: {x} (len={n})")
