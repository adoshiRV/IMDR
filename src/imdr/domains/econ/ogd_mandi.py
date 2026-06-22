"""data.gov.in OGD — Agmarknet daily mandi price client.

Source resource: 35985678-0d79-46b4-9ed6-6f13308a1d24
"Variety-wise Daily Market Prices Data of Commodity"

API pattern:
  GET https://api.data.gov.in/resource/{RESOURCE_ID}
      ?api-key={KEY}
      &format=json
      &limit=1000
      &offset={n}
      &filters[Arrival_Date]=DD/MM/YYYY   (optional date filter)

Page size cap: 1000 rows. Prices in INR per quintal.
Data lags ~1-2 days; ~22k records per recent day.

Record fields (as-served, TitleCase):
  Arrival_Date  — string "DD/MM/YYYY"
  Commodity     — commodity name
  Commodity_Code
  District
  Grade         — may be blank/"NR"/"-" → normalised to '' (empty string)
  Market
  Max_Price     — string; may be blank/"NR"/"-"/0 → coerced to Decimal or None
  Min_Price
  Modal_Price
  State
  Variety

This module exposes pure functions for key loading, page fetching, record
normalisation, and full-day paginated fetch. No DB writes here.
"""

from __future__ import annotations

import datetime
import os
import sys
import time
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterator

import requests

from imdr.connectors.http import _redact_params

_RESOURCE_ID = "35985678-0d79-46b4-9ed6-6f13308a1d24"
_BASE_URL = f"https://api.data.gov.in/resource/{_RESOURCE_ID}"
_PAGE_SIZE = 1000
_REPO_ROOT = Path(__file__).resolve().parents[4]

_RETRIES = 4
_RETRY_SLEEP_S = 2.0
_THROTTLE_S = 0.25
_MAX_PAGES_PER_DAY = 100
_RETRYABLE_HTTP_STATUSES = frozenset({429, 502, 503, 504})

_PRICE_NULL_TOKENS = frozenset({"", "NR", "nr", "-", "N/A", "n/a", "0", "0.0", "0.00"})


# ---------------------------------------------------------------------------
# Key loading
# ---------------------------------------------------------------------------

def load_key() -> str:
    """Return the data.gov.in API key.

    Reads IMDR_DATA_GOV_IN_API_KEY from os.environ first (covers the
    pydantic-settings load path), then falls back to a raw .env scan.
    Raises RuntimeError if missing — callers must not proceed without it.
    Never logs or returns a truncated form of the key.
    """
    key = os.environ.get("IMDR_DATA_GOV_IN_API_KEY", "").strip()
    if key:
        return key
    env_path = _REPO_ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("IMDR_DATA_GOV_IN_API_KEY="):
                v = line.split("=", 1)[1].strip()
                if v:
                    return v
    raise RuntimeError("IMDR_DATA_GOV_IN_API_KEY not set in env or .env")


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def make_session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = "Mozilla/5.0 IMDR-ogd-mandi"
    return s


def _get_page(
    session: requests.Session,
    key: str,
    *,
    offset: int,
    arrival_date: str | None = None,
    timeout: int = 30,
) -> dict:
    """Fetch one page from the OGD API.

    ``arrival_date`` is the date filter in DD/MM/YYYY format if provided.
    Never logs the key.
    """
    params: dict[str, object] = {
        "api-key": key,
        "format": "json",
        "limit": _PAGE_SIZE,
        "offset": offset,
    }
    if arrival_date is not None:
        params["filters[Arrival_Date]"] = arrival_date

    safe_params = _redact_params(params)

    last_err: Exception | None = None
    for attempt in range(1, _RETRIES + 1):
        try:
            if attempt > 1:
                # Sleep is LINEAR (_RETRY_SLEEP_S * attempt), not exponential.
                time.sleep(_RETRY_SLEEP_S * attempt)
            resp = session.get(_BASE_URL, params=params, timeout=timeout)
            if resp.status_code not in _RETRYABLE_HTTP_STATUSES:
                resp.raise_for_status()
                return resp.json()
            last_err = requests.exceptions.HTTPError(
                f"HTTP {resp.status_code}", response=resp
            )
            if attempt == _RETRIES:
                break
        except requests.exceptions.HTTPError as e:
            # Non-retryable HTTP status (e.g. 400/401/403/404). requests embeds
            # the full request URL — including ?api-key=... — in str(HTTPError),
            # so we must NOT propagate the raw exception. Re-raise a redacted
            # RuntimeError and suppress the chained original (from None) so the
            # key cannot leak via __cause__ / traceback either.
            status = e.response.status_code if e.response is not None else "?"
            raise RuntimeError(
                f"OGD API non-retryable HTTP {status} "
                f"(offset={offset}, params={safe_params})"
            ) from None
        except (requests.exceptions.ConnectionError,
                requests.exceptions.ChunkedEncodingError,
                requests.exceptions.Timeout) as e:
            last_err = e
            if attempt == _RETRIES:
                break
    raise RuntimeError(
        f"OGD API connection failed after {_RETRIES} attempts "
        f"(offset={offset}, params={safe_params}): {last_err}"
    )


# ---------------------------------------------------------------------------
# Record normalisation
# ---------------------------------------------------------------------------

def _parse_price(raw: object) -> Decimal | None:
    """Coerce a raw price field to Decimal, returning None for blank/NR/zero tokens."""
    s = str(raw).strip() if raw is not None else ""
    if s in _PRICE_NULL_TOKENS:
        return None
    try:
        d = Decimal(s)
        if d <= 0:
            return None
        return d
    except InvalidOperation:
        return None


def _parse_arrival_date(raw: str) -> datetime.date:
    """Parse DD/MM/YYYY string to a datetime.date.

    Raises ValueError with a clear message if the format is wrong — let the
    caller decide whether to skip or abort.
    """
    raw = raw.strip()
    try:
        return datetime.datetime.strptime(raw, "%d/%m/%Y").date()
    except ValueError as e:
        raise ValueError(
            f"OGD Arrival_Date has unexpected format: {raw!r} "
            f"(expected DD/MM/YYYY)"
        ) from e


def _clean_str(raw: object) -> str:
    """Strip whitespace; return empty string for None."""
    return str(raw).strip() if raw is not None else ""


_GRADE_NULL_TOKENS = frozenset({"", "NR", "nr", "-", "FAQ", "faq", "N/A", "n/a"})


def normalise_record(raw: dict) -> dict:
    """Normalise one raw API record dict into a clean typed row.

    Returns a dict with keys:
      arrival_date   datetime.date
      state          str
      district       str
      market         str
      commodity      str
      commodity_code str
      variety        str
      grade          str            ('' when blank or FAQ/NR markers; never None)
      min_price      Decimal | None
      max_price      Decimal | None
      modal_price    Decimal | None

    Raises ValueError if Arrival_Date is malformed.
    """
    grade_raw = _clean_str(raw.get("Grade"))
    grade = "" if grade_raw in _GRADE_NULL_TOKENS else grade_raw

    return {
        "arrival_date": _parse_arrival_date(_clean_str(raw.get("Arrival_Date", ""))),
        "state": _clean_str(raw.get("State")),
        "district": _clean_str(raw.get("District")),
        "market": _clean_str(raw.get("Market")),
        "commodity": _clean_str(raw.get("Commodity")),
        "commodity_code": _clean_str(raw.get("Commodity_Code")),
        "variety": _clean_str(raw.get("Variety")),
        "grade": grade,
        "min_price": _parse_price(raw.get("Min_Price")),
        "max_price": _parse_price(raw.get("Max_Price")),
        "modal_price": _parse_price(raw.get("Modal_Price")),
    }


# ---------------------------------------------------------------------------
# Paginated fetch
# ---------------------------------------------------------------------------

def iter_pages_for_date(
    session: requests.Session,
    key: str,
    date: datetime.date,
    *,
    timeout: int = 30,
) -> Iterator[tuple[list[dict], int]]:
    """Paginate all records for one Arrival_Date.

    Yields (raw_records, total_count) tuples — one yield per page.
    ``total_count`` is the OGD-reported total; use it to display progress
    but don't trust it to detect the last page (use empty records instead).
    """
    date_str = date.strftime("%d/%m/%Y")
    offset = 0
    page_count = 0
    while True:
        if page_count >= _MAX_PAGES_PER_DAY:
            print(
                f"[WARN] iter_pages_for_date: hit {_MAX_PAGES_PER_DAY}-page sentinel "
                f"for {date_str} — stopping early (API anomaly?)",
                file=sys.stderr,
            )
            break
        time.sleep(_THROTTLE_S)
        payload = _get_page(
            session, key,
            offset=offset,
            arrival_date=date_str,
            timeout=timeout,
        )
        total = int(payload.get("total", 0) or 0)
        records = payload.get("records") or []
        if not records:
            break
        page_count += 1
        yield records, total
        if len(records) < _PAGE_SIZE:
            break
        offset += _PAGE_SIZE


def fetch_date(
    session: requests.Session,
    key: str,
    date: datetime.date,
    *,
    timeout: int = 30,
) -> tuple[list[dict], int]:
    """Fetch and normalise all records for one date.

    Returns (normalised_rows, page_count). Skips rows with malformed dates
    (logs a warning to stderr) rather than aborting the whole batch.
    """
    rows: list[dict] = []
    pages = 0
    for raw_records, _total in iter_pages_for_date(session, key, date, timeout=timeout):
        pages += 1
        for raw in raw_records:
            try:
                rows.append(normalise_record(raw))
            except ValueError as e:
                print(f"  [WARN] Skipping malformed record: {e}", file=sys.stderr)
    return rows, pages
