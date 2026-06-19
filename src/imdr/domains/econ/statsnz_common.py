"""Stats NZ — shared library for prod econ fetchers (release-page CSV path).

Promoted from `playground/econ/statsnz/_statsnz_common.py` (2026-06-17). The
release-page CSV path (Tier-1) serves the macro headlines that publish a
long-format CSV: CPI, GDP, Balance of Payments / IIP. Every Stats NZ
"Information release" publishes one or more CSVs under
`https://www.stats.govt.nz/assets/Uploads/{topic}/.../Download-data/{slug}.csv`
carrying FULL history, served over plain `httpx` with a Chrome UA (no
Playwright, no Cloudflare challenge).

Datasets WITHOUT a release CSV (PPI / CGPI / OTI / HLPI / LCI / QES / ECT /
OMT / RTS / HLFS history) come via `statsnz_infoshare.py` instead.

CSV schema (common to CPI / GDP / BoP release pages):
    Series_reference, Period, Data_value, STATUS, UNITS, [MAGNITUDE,] Subject,
    Group, Series_title_1, ... Series_title_N
  - Period is `YYYY.MM` where MM = quarter-end month (`2026.03` = Q1 2026).
  - Data_value may be empty, 'NA', or `..` (suppressed).

This module owns the CSV client + parser + indicator factory; each
`scripts/econ/nz/statsnz/statsnz_{topic}.py` owns its source_code whitelist.
"""

from __future__ import annotations

import csv
import datetime
import io
import time
from dataclasses import dataclass

import httpx

from imdr.domains.econ.schema import IndicatorRow, ObservationRow

UTC = datetime.timezone.utc
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


@dataclass(frozen=True)
class StatsNZSeries:
    """One Stats NZ series to materialise as an IndicatorRow.

    `source_code` is the vendor's Series_reference (e.g. ``CPIQ.SE9A``);
    `imdr_code` is our canonical name.
    """

    source_code: str
    imdr_code: str
    display_name: str
    unit: str
    frequency: str
    category: str
    is_sa: bool = False


def period_to_obs_date(period: str) -> datetime.date | None:
    """Parse Stats NZ 'YYYY.MM' Period to obs_date (month-end of that month)."""
    if not period:
        return None
    p = period.strip()
    try:
        y_s, m_s = p.split(".", 1)
        y, m = int(y_s), int(m_s)
        if not (1 <= m <= 12):
            return None
        next_first = datetime.date(y + 1, 1, 1) if m == 12 else datetime.date(y, m + 1, 1)
        return next_first - datetime.timedelta(days=1)
    except (TypeError, ValueError):
        return None


def _parse_value(raw: str) -> float | None:
    if raw is None:
        return None
    s = raw.strip()
    if not s or s.upper() in {"NA", "..", "...", "-", "N/A"}:
        return None
    try:
        return float(s)
    except ValueError:
        return None


class StatsNZClient:
    """Plain `httpx` client for Stats NZ release-page assets.

    Cloudflare lets `/assets/Uploads/...` paths through with a Chrome UA; no
    JS rendering needed. A polite delay between calls keeps us under limits.
    """

    def __init__(self, timeout: float = 60.0, delay: float = 0.3) -> None:
        self._client = httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": _UA, "Accept": "*/*"},
        )
        self._delay = delay

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "StatsNZClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def fetch_csv(self, url: str) -> str:
        r = self._client.get(url)
        time.sleep(self._delay)
        r.raise_for_status()
        try:
            return r.content.decode("utf-8")
        except UnicodeDecodeError:
            return r.content.decode("utf-8", errors="replace")


def parse_release_csv(text: str) -> tuple[list[str], list[dict]]:
    """Parse a Stats NZ release-asset CSV into (header, rows-as-dicts)."""
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        raise ValueError("Stats NZ CSV is empty")
    header = rows[0]
    if "Series_reference" not in header or "Period" not in header or "Data_value" not in header:
        raise ValueError(
            f"Stats NZ CSV missing one of Series_reference/Period/Data_value: header={header!r}"
        )
    body = [dict(zip(header, r)) for r in rows[1:] if len(r) >= 3]
    return header, body


def rows_to_indicator_observations(
    rows: list[dict],
    specs: dict[str, StatsNZSeries],
    *,
    country_iso: str = "NZ",
    vendor_name: str = "statsnz",
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    """Filter rows to `specs` and convert to (IndicatorRow, ObservationRow) lists.

    `specs` maps Stats NZ Series_reference -> StatsNZSeries config; rows whose
    Series_reference is not in `specs` are silently dropped.
    """
    indicators: dict[str, IndicatorRow] = {}
    obs: list[ObservationRow] = []
    now = datetime.datetime.now(UTC)
    for row in rows:
        src = (row.get("Series_reference") or "").strip()
        spec = specs.get(src)
        if spec is None:
            continue
        obs_date = period_to_obs_date(row.get("Period") or "")
        if obs_date is None:
            continue
        v = _parse_value(row.get("Data_value") or "")
        status = (row.get("STATUS") or "").strip().upper()

        if spec.imdr_code not in indicators:
            indicators[spec.imdr_code] = IndicatorRow(
                imdr_code=spec.imdr_code,
                vendor_name=vendor_name,
                source_code=spec.source_code,
                display_name=spec.display_name[:500],
                unit=spec.unit,
                frequency=spec.frequency,
                country_iso=country_iso,
                category=spec.category,
                is_seasonally_adjusted=spec.is_sa,
            )
        obs.append(ObservationRow(
            imdr_code=spec.imdr_code,
            obs_date=obs_date,
            vintage=0,
            release_date=now,
            value=v,
            is_preliminary=(status not in ("FINAL", "")),
            ingested_at=now,
        ))
    return list(indicators.values()), obs


__all__ = [
    "StatsNZSeries",
    "StatsNZClient",
    "period_to_obs_date",
    "parse_release_csv",
    "rows_to_indicator_observations",
]
