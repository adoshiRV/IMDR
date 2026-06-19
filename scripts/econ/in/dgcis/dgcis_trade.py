"""DGCIS MEIDB — multi-month commodity-wise trade fetcher.

Source: `tradestat.commerce.gov.in/meidb/commoditywise_{export,import}` —
Laravel form, CSRF-gated. POST with calendar (year, month) returns a
108KB HTML page containing the HS-2 chapter table for that month
(current + prior-year-same-month + FY-YTD current + FY-YTD prior).

Verified 2026-06-11:
  - ddYear accepts calendar years 2014→2026 (dropdown shows 2018+ but
    older years still return distinct, correct data).
  - ddMonth = calendar month 1..12.
  - ddReportYear=1 → FY-YTD column is "Apr→{month}" of the FY
    containing ddYear.
  - Each response carries 6 value columns:
      [prior-year same month] [current month] [YoY%]
      [prior FY-YTD]            [current FY-YTD] [YoY%]
  - 99 HS-2 chapters + 1 "Total" row in the response.

History reachable: **calendar Apr 2014 → today** (Indian FY 2014-15
onwards) by walking (year, month) pairs. Each POST is ~1s server-side;
add 1s throttle → ~2s/request. 145 months × 2 directions ≈ 290 POSTs ≈
10 min for full backfill.

Cadence: monthly, ~15-day publication lag (e.g. March data lands
mid-April). Re-run monthly; idempotent if persisted by (HS, obs_date).

Emits indicators:
  INDIA.TRADE.{EXPORT|IMPORT}.HS{nn}.USD_MN.IN  — per HS-2 chapter
  INDIA.TRADE.{EXPORT|IMPORT}.TOTAL.USD_MN.IN   — headline
  → 99 × 2 + 2 = 200 indicators, ~145 months each ≈ 29,000 obs.

Run:
    python -m scripts.econ.in.dgcis.dgcis_trade --since 2024-01-01
    python -m scripts.econ.in.dgcis.dgcis_trade --no-load            # full backfill, parquet only
    python -m scripts.econ.in.dgcis.dgcis_trade --direction export   # single direction
"""
from __future__ import annotations

import datetime
import re
import time

import httpx

from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc

_BASE = "https://tradestat.commerce.gov.in"
_UA = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 Chrome/120 Safari/537.36"),
    "Referer": _BASE + "/",
}

_HS2_RE = re.compile(r"^\d{1,2}$")
_CSRF_RE = re.compile(r'name=["\']_token["\']\s+value=["\']([^"\']+)["\']')
_TABLE_RE = re.compile(r"<table[^>]*>(.*?)</table>", re.DOTALL)
_ROW_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.DOTALL)
_CELL_RE = re.compile(r"<t[hd][^>]*>(.*?)</t[hd]>", re.DOTALL)
_STRIP_TAGS = re.compile(r"<[^>]+>")

_THROTTLE_SEC = 1.0


def _num(s: str) -> float | None:
    s = (s or "").replace(",", "").strip()
    if not s or s in ("-", "*", "NA", "NR"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _fresh_csrf(client: httpx.Client, direction: str) -> str:
    """Each POST in this app cycles the CSRF — refresh per request."""
    url = f"{_BASE}/meidb/commoditywise_{direction}"
    r = client.get(url, headers=_UA)
    r.raise_for_status()
    m = _CSRF_RE.search(r.text)
    if not m:
        raise RuntimeError(f"CSRF not found on {url}")
    return m.group(1)


def _post_month(
    client: httpx.Client, direction: str, year: int, month: int,
) -> list[list[str]]:
    """POST one (direction, year, month) and return the parsed table rows."""
    url = f"{_BASE}/meidb/commoditywise_{direction}"
    csrf = _fresh_csrf(client, direction)
    prefix = "imdd" if direction == "import" else "dd"
    payload = {
        "_token": csrf,
        f"{prefix}Month": str(month),
        f"{prefix}Year": str(year),
        "comlev": "all",
        f"{prefix}CommodityLevel": "2",
        f"{prefix}ReportVal": "1",     # USD Mn
        f"{prefix}ReportYear": "1",    # FY mode
    }
    r = client.post(url, headers=_UA, data=payload)
    r.raise_for_status()

    tables = _TABLE_RE.findall(r.text)
    if not tables:
        return []
    out: list[list[str]] = []
    for row in _ROW_RE.findall(tables[0])[1:]:  # skip header
        cells = _CELL_RE.findall(row)
        clean = [_STRIP_TAGS.sub("", c).strip() for c in cells]
        if len(clean) >= 6:
            out.append(clean)
    return out


def _month_iter(
    start: datetime.date, end: datetime.date,
) -> list[tuple[int, int]]:
    """Yield (year, month) tuples first-of-month walking start → end."""
    pairs: list[tuple[int, int]] = []
    y, m = start.year, start.month
    while datetime.date(y, m, 1) <= end:
        pairs.append((y, m))
        if m == 12:
            y, m = y + 1, 1
        else:
            m += 1
    return pairs


_HS2_DISPLAY: dict[str, str] = {
    # Populated lazily from the first response — chapter codes are stable.
}


def _imdr_code(direction: str, hs_code: str) -> str:
    if hs_code == "TOTAL":
        stem = "TOTAL"
    else:
        stem = f"HS{int(hs_code):02d}"
    return f"INDIA.TRADE.{direction.upper()}.{stem}.USD_MN.IN"


def _record_row(
    direction: str, hs_code: str, commodity: str, value: float | None,
    obs_date: datetime.date, now: datetime.datetime,
    indicators: dict[str, IndicatorRow], observations: list[ObservationRow],
    seen_obs: set[tuple[str, datetime.date]],
) -> None:
    if value is None:
        return
    imdr_code = _imdr_code(direction, hs_code)
    if imdr_code not in indicators:
        if hs_code == "TOTAL":
            display = f"India merchandise {direction}s — All commodities (DGCIS, USD Mn)"
        else:
            display = f"India merchandise {direction}s — HS{int(hs_code):02d} {commodity.title()} (DGCIS, USD Mn)"
        indicators[imdr_code] = IndicatorRow(
            imdr_code=imdr_code, vendor_name="DGCIS",
            source_code=f"DGCIS/MEIDB/{direction}/HS2/{hs_code}",
            display_name=display[:255],
            unit="usd_mn", frequency="MONTHLY",
            country_iso="IN", category="bop",
            is_seasonally_adjusted=False, bbg_ticker=None,
        )
    key = (imdr_code, obs_date)
    if key in seen_obs:
        return
    seen_obs.add(key)
    observations.append(ObservationRow(
        imdr_code=imdr_code, obs_date=obs_date, vintage=0,
        release_date=now, value=value, ingested_at=now,
    ))


def _parse_month_rows(
    rows: list[list[str]], direction: str, year: int, month: int,
    now: datetime.datetime,
    indicators: dict[str, IndicatorRow], observations: list[ObservationRow],
    seen_obs: set[tuple[str, datetime.date]],
) -> int:
    """Walk one month's table; emit per-HS observations for the current
    month + the prior-year same-month columns (both are real data points)."""
    obs_date = datetime.date(year, month, 1)
    prev_obs_date = datetime.date(year - 1, month, 1)
    n_emitted = 0
    for clean in rows:
        # Layout: [S.No, HS, Commodity, prior-year-month, curr-month, %YoY,
        #          prior-FY-YTD, curr-FY-YTD, %YoY]
        if len(clean) < 5:
            continue
        hs_raw = clean[1]
        commodity = clean[2] if len(clean) > 2 else ""
        # Trailing "India's Total {Export|Import}" row has blank HS code.
        if "india's total" in commodity.lower() or "indias total" in commodity.lower():
            hs_code = "TOTAL"
        elif hs_raw.lower() == "total":
            hs_code = "TOTAL"
        elif _HS2_RE.match(hs_raw):
            hs_code = hs_raw
        else:
            continue
        prev_val = _num(clean[3]) if len(clean) > 3 else None
        curr_val = _num(clean[4]) if len(clean) > 4 else None
        _record_row(direction, hs_code, commodity, curr_val, obs_date,
                    now, indicators, observations, seen_obs)
        _record_row(direction, hs_code, commodity, prev_val, prev_obs_date,
                    now, indicators, observations, seen_obs)
        n_emitted += 1
    return n_emitted


def run_fetch(
    since: str | None,
    until: str | None,
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    today = datetime.date.today()
    # Default backfill = Apr 2014; cap at today's month (no future data).
    start = (datetime.date.fromisoformat(since) if since else datetime.date(2014, 4, 1))
    end_default = today.replace(day=1) - datetime.timedelta(days=1)  # last month
    end_default = end_default.replace(day=1)
    end = (datetime.date.fromisoformat(until) if until else end_default)
    end = end.replace(day=1)
    months = _month_iter(start, end)
    print(f"  iterating {len(months)} months  {months[0]} → {months[-1]}")

    now = datetime.datetime.now(UTC)
    indicators: dict[str, IndicatorRow] = {}
    observations: list[ObservationRow] = []
    seen_obs: set[tuple[str, datetime.date]] = set()

    with httpx.Client(timeout=60, follow_redirects=True) as c:
        for direction in ("export", "import"):
            print(f"\n  === {direction.upper()} ===")
            for y, m in months:
                try:
                    rows = _post_month(c, direction, y, m)
                except Exception as e:
                    print(f"    {y}-{m:02d}: FAIL {type(e).__name__}: {str(e)[:60]}")
                    time.sleep(_THROTTLE_SEC)
                    continue
                n = _parse_month_rows(rows, direction, y, m, now,
                                       indicators, observations, seen_obs)
                if y % 2 == 0 and m == 4:  # progress beacon every 2y
                    print(f"    {y}-{m:02d}: +{n} rows  (running total: {len(observations):,} obs)")
                time.sleep(_THROTTLE_SEC)

    # Drop unreleased months. DGCIS returns "0.00" sentinel for every HS
    # chapter when a month isn't yet published — pattern detectable as
    # ">50% of obs for that (direction, month) are exactly 0.0". Real
    # months always have non-zero values across the bulk of chapters
    # (even the smallest like HS97 carry non-zero values).
    pre = len(observations)
    by_dir_month: dict[tuple[str, datetime.date], list[int]] = {}
    for i, o in enumerate(observations):
        direction = "EXPORT" if ".EXPORT." in o.imdr_code else "IMPORT"
        key = (direction, o.obs_date)
        by_dir_month.setdefault(key, []).append(i)
    drop_idx: set[int] = set()
    for key, idxs in by_dir_month.items():
        zeros = sum(1 for i in idxs if observations[i].value == 0.0)
        if len(idxs) >= 50 and zeros / len(idxs) > 0.5:
            print(f"  dropping unreleased month {key[0]} {key[1]} ({zeros}/{len(idxs)} zero)")
            drop_idx.update(idxs)
    if drop_idx:
        observations = [o for i, o in enumerate(observations) if i not in drop_idx]
        print(f"  dropped {pre - len(observations)} obs from unreleased months")

    return list(indicators.values()), observations


def main() -> int:
    return run_main(vendor="dgcis", topic="trade",
                    fetch_fn=run_fetch,
                    description=__doc__.splitlines()[0] if __doc__ else "",
                    country_code="IN")


if __name__ == "__main__":
    import sys
    sys.exit(main())
