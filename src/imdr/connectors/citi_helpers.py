"""Shared Citi Velocity helpers — domain-agnostic.

Used by: rates extractor, rates translate, fx vol extractor, fx vol translate,
and any future Citi-sourced pipeline.
"""
from __future__ import annotations

import time
from collections.abc import Callable
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import pandas as pd
import structlog

if TYPE_CHECKING:
    from imdr.connectors.citi_quota import TagQuotaTracker

_log = structlog.get_logger("citi_helpers")


class TagQuotaExceeded(RuntimeError):
    """Raised when the Citi API cumulative tag quota is exhausted."""

    def __init__(self, message: str, current_usage: int | None = None, available: int | None = None) -> None:
        super().__init__(message)
        self.current_usage = current_usage
        self.available = available


class TagQuotaBudgetExceeded(TagQuotaExceeded):
    """Raised BEFORE API call when pre-flight budget check fails.

    Subclass of TagQuotaExceeded so existing handlers catch both.
    """

    def __init__(
        self,
        message: str,
        needed: int,
        remaining: int,
        current_usage: int | None = None,
    ) -> None:
        super().__init__(message, current_usage=current_usage, available=remaining)
        self.needed = needed
        self.remaining_budget = remaining


def _parse_quota_error(resp: dict) -> TagQuotaExceeded | None:
    """If resp is a tag-quota error, return a TagQuotaExceeded; else None."""
    msg = resp.get("message", "")
    if "Exceeded max tag count" not in msg and "max tag count" not in msg.lower():
        return None
    import re
    usage_match = re.search(r"Current usage:\s*(\d+)", msg)
    avail_match = re.search(r"Available usage:\s*(\d+)", msg)
    return TagQuotaExceeded(
        msg,
        current_usage=int(usage_match.group(1)) if usage_match else None,
        available=int(avail_match.group(1)) if avail_match else None,
    )


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
        quota_err = _parse_quota_error(resp)
        if quota_err:
            raise quota_err
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
    quota_tracker: TagQuotaTracker | None = None,
    pipeline_name: str = "",
) -> pd.DataFrame:
    """Fetch tags in batches, respecting rate limits, concat results.

    response_parser converts a single API response dict → DataFrame.
    Each domain provides its own parser.

    If ``quota_tracker`` is provided, each batch records its tag count
    to the shared quota file for cross-process visibility.
    """
    frames: list[pd.DataFrame] = []
    total_batches = (len(tags) + batch_size - 1) // batch_size
    cumulative_tags = 0

    for i in range(0, len(tags), batch_size):
        batch = tags[i : i + batch_size]
        batch_num = i // batch_size + 1
        cumulative_tags += len(batch)

        resp = client.fetch_historical(  # type: ignore[attr-defined]
            tags=batch,
            start=start,
            end=end,
            frequency=frequency,
        )

        # Record tag usage to shared quota tracker
        if quota_tracker is not None:
            quota_tracker.record_usage(pipeline_name, len(batch))

        # Log rate limit info from client if available
        rl_remaining = getattr(client, "rate_limit_remaining", None)
        _log.info(
            "batch_complete",
            batch=f"{batch_num}/{total_batches}",
            tags_this_batch=len(batch),
            cumulative_tags=cumulative_tags,
            total_tags=len(tags),
            ratelimit_remaining=rl_remaining,
            quota_remaining=quota_tracker.remaining() if quota_tracker else None,
        )

        df = response_parser(resp)

        if not df.empty:
            frames.append(df)

        if i + batch_size < len(tags):
            time.sleep(rate_limit)

    if not frames:
        return pd.DataFrame()

    return pd.concat(frames, ignore_index=True)
