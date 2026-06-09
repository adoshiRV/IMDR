"""Shared Citi Velocity helpers — domain-agnostic.

Used by: rates extractor, rates translate, fx vol extractor, fx vol translate,
and any future Citi-sourced pipeline.
"""
from __future__ import annotations

import re
import time
from collections.abc import Callable
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import pandas as pd
import structlog

from imdr.connectors.citi_velocity import CitiAPIError, CitiVelocityClient

if TYPE_CHECKING:
    from imdr.connectors.citi_quota import TagQuotaTracker

_log = structlog.get_logger("citi_helpers")

# Per-batch retry policy for transient 5xx (gateway/load-balancer hiccups).
# A single 503 used to wipe the whole currency for the run; retry with backoff.
# Geometric ~3× growth; total worst-case wait = 5 + 15 + 45 = 65s per batch.
_RETRY_5XX_DELAYS = (5.0, 15.0, 45.0)


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
    usage_match = re.search(r"Current usage:\s*(\d+)", msg)
    avail_match = re.search(r"Available usage:\s*(\d+)", msg)
    return TagQuotaExceeded(
        msg,
        current_usage=int(usage_match.group(1)) if usage_match else None,
        available=int(avail_match.group(1)) if avail_match else None,
    )


# ── Per-tag error / empty-payload capture ────────────────────────


def _make_error_entry(tag: str, kind: str, message: str | None, raw: dict) -> dict:
    """Build the canonical shape for a tag-error sink entry."""
    return {"tag": tag, "type": kind, "message": message, "raw": raw}


def _collect_tag_errors(resp: dict, sink: list[dict]) -> None:
    """Append per-tag failure or empty-payload entries from a Citi response.

    Citi's Historical response can carry information at two levels:
      * top-level ``status: ERROR`` / ``message`` — already raised upstream
        as ``TagQuotaExceeded`` or ``RuntimeError`` by ``citi_response_to_rows``;
        we record the message defensively in case the caller bypassed that.
      * per-tag ``body[tag]`` series with ``type == ERROR`` (e.g. unsupported
        frequency, per-tag rate-limit hit) — these are otherwise silently
        skipped by ``citi_response_to_rows``.
      * per-tag series with empty ``x`` / ``c`` — Citi returned the slot but
        no datapoints (closed market, future date, exhausted per-tag quota
        for the rolling 24h bucket).

    Each appended entry is::

        {
            "tag": str,
            "type": "ERROR" | "EMPTY" | "MALFORMED" | "RESPONSE",
            "message": str | None,
            "raw": dict,  # remaining series fields (no x/c/type)
        }
    """
    if resp.get("status") != "OK":
        sink.append(_make_error_entry(
            tag="<response>",
            kind="RESPONSE",
            message=resp.get("message") or "non-OK status with no message",
            raw={k: v for k, v in resp.items() if k != "body"},
        ))
        return

    for tag, series in resp.get("body", {}).items():
        if not isinstance(series, dict):
            sink.append(_make_error_entry(tag, "MALFORMED", str(series)[:200], {}))
            continue

        residual = {k: v for k, v in series.items() if k not in ("x", "c", "type")}

        if series.get("type") == "ERROR":
            sink.append(_make_error_entry(
                tag, "ERROR",
                series.get("message") or residual.get("error"),
                residual,
            ))
            continue

        if not (series.get("x") or series.get("c")):
            sink.append(_make_error_entry(tag, "EMPTY", series.get("message"), residual))


def summarize_tag_errors(
    tag_errors: list[dict],
    sample_size: int = 3,
) -> list[dict]:
    """Group raw tag_error entries into a digest suitable for emails / logs.

    Returns a list of summary rows::

        {"type": str, "message": str, "count": int, "sample_tags": [str]}

    Sorted by descending count so the most prevalent failure shows first.
    Tags are grouped by ``(type, message)`` — entries with no message fall
    back to ``"(no message)"`` so they still aggregate cleanly.
    """
    if not tag_errors:
        return []

    buckets: dict[tuple[str, str], list[str]] = {}
    for e in tag_errors:
        key = (e.get("type", "ERROR"), (e.get("message") or "(no message)").strip())
        buckets.setdefault(key, []).append(e.get("tag", ""))

    summary: list[dict] = []
    for (t, m), tags in buckets.items():
        summary.append({
            "type": t,
            "message": m,
            "count": len(tags),
            "sample_tags": tags[:sample_size],
        })
    summary.sort(key=lambda r: r["count"], reverse=True)
    return summary


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


def _fetch_with_retry(
    client: CitiVelocityClient,
    batch: list[str],
    start: datetime,
    end: datetime,
    frequency: str,
    batch_num: int,
    total_batches: int,
) -> dict:
    """Call client.fetch_historical with backoff on transient 5xx.

    Retries up to ``len(_RETRY_5XX_DELAYS)`` times on CitiAPIError with a
    5xx status (gateway 502/503/504, server 500). Other errors — TagQuotaExceeded,
    4xx, malformed JSON — propagate immediately.
    """
    attempt = 0
    while True:
        try:
            return client.fetch_historical(
                tags=batch,
                start=start,
                end=end,
                frequency=frequency,
            )
        except CitiAPIError as e:
            if not (500 <= e.status_code < 600) or attempt >= len(_RETRY_5XX_DELAYS):
                raise
            delay = _RETRY_5XX_DELAYS[attempt]
            _log.warning(
                "citi_5xx_retry",
                batch=f"{batch_num}/{total_batches}",
                status=e.status_code,
                attempt=attempt + 1,
                max_attempts=len(_RETRY_5XX_DELAYS),
                delay_secs=delay,
            )
            time.sleep(delay)
            attempt += 1


def _process_batch(
    client: CitiVelocityClient,
    batch: list[str],
    start: datetime,
    end: datetime,
    frequency: str,
    response_parser: Callable[[dict], pd.DataFrame],
    batch_num: int,
    total_batches: int,
    cumulative_tags: int,
    total_tags: int,
    quota_tracker: TagQuotaTracker | None,
    pipeline_name: str,
    tag_errors: list[dict] | None,
) -> pd.DataFrame:
    """Fetch one batch, record quota, collect errors, log, return parsed frame.

    Pulled out of `fetch_and_parse_batched` so the outer loop is just batch
    iteration + rate-limit sleep, and the per-batch steps share one signature.
    """
    resp = _fetch_with_retry(
        client, batch, start, end, frequency, batch_num, total_batches,
    )

    if quota_tracker is not None:
        quota_tracker.record_usage(pipeline_name, len(batch))

    # Capture per-tag failures / empty payloads before parsing — we still want
    # the signal even if the response_parser swallows partial responses.
    if tag_errors is not None:
        _collect_tag_errors(resp, tag_errors)

    _log.info(
        "batch_complete",
        batch=f"{batch_num}/{total_batches}",
        tags_this_batch=len(batch),
        cumulative_tags=cumulative_tags,
        total_tags=total_tags,
        ratelimit_remaining=client.rate_limit_remaining,
        quota_remaining=quota_tracker.remaining() if quota_tracker else None,
    )

    return response_parser(resp)


def fetch_and_parse_batched(
    client: CitiVelocityClient,
    tags: list[str],
    start: datetime,
    end: datetime,
    frequency: str,
    batch_size: int,
    rate_limit: float,
    response_parser: Callable[[dict], pd.DataFrame],
    quota_tracker: TagQuotaTracker | None = None,
    pipeline_name: str = "",
    tag_errors: list[dict] | None = None,
) -> pd.DataFrame:
    """Fetch tags in batches, respecting rate limits, concat results.

    response_parser converts a single API response dict → DataFrame.
    Each domain provides its own parser.

    If ``quota_tracker`` is provided, each batch records its tag count
    to the shared quota file for cross-process visibility.

    If ``tag_errors`` is provided, per-tag ERROR / EMPTY / MALFORMED entries
    are appended to it (see ``_collect_tag_errors``). Caller can later run
    them through ``summarize_tag_errors`` for reporting.
    """
    frames: list[pd.DataFrame] = []
    total_batches = (len(tags) + batch_size - 1) // batch_size
    cumulative_tags = 0

    for i in range(0, len(tags), batch_size):
        batch = tags[i : i + batch_size]
        batch_num = i // batch_size + 1
        cumulative_tags += len(batch)

        df = _process_batch(
            client, batch, start, end, frequency, response_parser,
            batch_num, total_batches, cumulative_tags, len(tags),
            quota_tracker, pipeline_name, tag_errors,
        )

        if not df.empty:
            frames.append(df)

        if i + batch_size < len(tags):
            time.sleep(rate_limit)

    if not frames:
        return pd.DataFrame()

    return pd.concat(frames, ignore_index=True)
