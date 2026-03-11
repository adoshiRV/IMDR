"""Shared Citi Velocity helpers — domain-agnostic.

Used by: rates extractor, rates translate, fx vol extractor, fx vol translate,
and any future Citi-sourced pipeline.
"""
from __future__ import annotations

import time
from collections.abc import Callable
from datetime import datetime, timezone

import pandas as pd
import structlog

_log = structlog.get_logger("citi_helpers")


# ── 1. Timestamp parser (moved from domains/rates/utils.py) ──────


def parse_x_to_ts_utc(x: int) -> datetime:
    """Infer Citi x-axis format by digit count → UTC datetime.

    Formats:
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


# ── 2. Generic response → rows parser ────────────────────────────


def citi_response_to_rows(
    resp: dict,
    tag_parser: Callable[[str], dict | None],
    parse_x: Callable[[int], datetime] = parse_x_to_ts_utc,
) -> list[dict]:
    """Parse Citi Historical API response into flat row dicts.

    tag_parser is the ONLY domain-specific piece:
      rates:  tag → {ccy, curve, quote, tenor}
      fx vol: tag → {base_ccy, quote_ccy, strike, tenor, vol_type}

    Returns list of dicts, each: {ts, **tag_fields, value}
    """
    if resp.get("status") != "OK":
        raise RuntimeError(f"API status not OK: {resp}")

    rows: list[dict] = []
    for tag, series in resp.get("body", {}).items():
        if not isinstance(series, dict) or series.get("type") == "ERROR":
            continue
        parsed = tag_parser(tag)
        if parsed is None:
            continue
        for x, c in zip(series.get("x", []), series.get("c", [])):
            if c is None:
                continue
            rows.append({"ts": parse_x(x), **parsed, "value": float(c)})
    return rows


# ── 3. Batched fetch with rate limiting ──────────────────────────


def fetch_and_parse_batched(
    client: object,
    tags: list[str],
    start: datetime,
    end: datetime,
    frequency: str,
    batch_size: int,
    rate_limit: float,
    response_parser: Callable[[dict], pd.DataFrame],
) -> pd.DataFrame:
    """Fetch tags in batches, respecting rate limits, concat results.

    response_parser converts a single API response dict → DataFrame.
    Each domain provides its own parser.
    """
    frames: list[pd.DataFrame] = []

    for i in range(0, len(tags), batch_size):
        batch = tags[i : i + batch_size]

        resp = client.fetch_historical(  # type: ignore[attr-defined]
            tags=batch,
            start=start,
            end=end,
            frequency=frequency,
        )
        df = response_parser(resp)

        if not df.empty:
            frames.append(df)

        if i + batch_size < len(tags):
            time.sleep(rate_limit)

    if not frames:
        return pd.DataFrame()

    return pd.concat(frames, ignore_index=True)
