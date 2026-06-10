"""ABS SDMX REST client for prod AU econ fetchers.

The ABS SDMX REST API at https://data.api.abs.gov.au is public, unauthenticated,
and supports both XML and CSV responses. We use CSV (`format=csv`,
`Accept: text/csv`) — easier to parse than the v2.1 structure-specific XML.

Each prod fetcher under ``scripts/econ/au/abs/`` declares a list of
``SDMXSeries`` specs and calls ``fetch_series`` per spec; the runner
(``scripts.econ._runner``) handles CLI / parquet / DB load.
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
_BASE = "https://data.api.abs.gov.au"
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"


@dataclass(frozen=True)
class SDMXSeries:
    """One ABS SDMX series to fetch."""

    dataflow: str
    key: str
    imdr_code: str
    display_name: str
    unit: str
    frequency: str
    category: str
    is_sa: bool = False
    source_code_suffix: str = ""

    @property
    def source_code(self) -> str:
        suffix = f".{self.source_code_suffix}" if self.source_code_suffix else ""
        return f"ABS.{self.dataflow}.{self.key}{suffix}"


class ABSClient:
    """Minimal SDMX REST client for ABS."""

    def __init__(self, timeout: float = 60.0, delay: float = 0.3) -> None:
        self._client = httpx.Client(
            base_url=_BASE,
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": _UA, "Accept": "*/*"},
        )
        self._delay = delay

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "ABSClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def fetch_series_csv(
        self,
        dataflow: str,
        key: str,
        since: str | None = None,
        until: str | None = None,
    ) -> list[list[str]]:
        params: dict[str, str] = {"format": "csv"}
        if since:
            params["startPeriod"] = since[:7]
        if until:
            params["endPeriod"] = until[:7]
        r = self._client.get(
            f"/rest/data/{dataflow}/{key}",
            params=params,
            headers={"Accept": "text/csv"},
        )
        time.sleep(self._delay)
        r.raise_for_status()
        return list(csv.reader(io.StringIO(r.text)))


def parse_sdmx_period(period: str) -> datetime.date | None:
    """Parse SDMX TIME_PERIOD string to obs_date (period START)."""
    if not period:
        return None
    p = period.strip()
    try:
        if "-Q" in p:
            year_s, q_s = p.split("-Q", 1)
            q = int(q_s)
            if 1 <= q <= 4:
                return datetime.date(int(year_s), (q - 1) * 3 + 1, 1)
            return None
        parts = p.split("-")
        if len(parts) == 3:
            return datetime.date(int(parts[0]), int(parts[1]), int(parts[2]))
        if len(parts) == 2:
            return datetime.date(int(parts[0]), int(parts[1]), 1)
        if len(parts) == 1 and parts[0].isdigit() and len(parts[0]) == 4:
            return datetime.date(int(parts[0]), 1, 1)
    except (TypeError, ValueError):
        return None
    return None


def csv_rows_to_observations(
    rows: list[list[str]],
    imdr_code: str,
    *,
    vintage: int = 0,
) -> list[ObservationRow]:
    if len(rows) < 2:
        return []
    header = rows[0]
    try:
        i_tp = header.index("TIME_PERIOD")
        i_val = header.index("OBS_VALUE")
    except ValueError:
        raise ValueError(f"ABS CSV missing TIME_PERIOD or OBS_VALUE: {header!r}")
    now = datetime.datetime.now(UTC)
    out: list[ObservationRow] = []
    for row in rows[1:]:
        if len(row) <= max(i_tp, i_val):
            continue
        d = parse_sdmx_period(row[i_tp])
        if d is None:
            continue
        try:
            v: float | None = float(row[i_val]) if row[i_val] != "" else None
        except ValueError:
            v = None
        out.append(ObservationRow(
            imdr_code=imdr_code,
            obs_date=d,
            vintage=vintage,
            release_date=now,
            value=v,
            ingested_at=now,
        ))
    return out


def fetch_series(
    client: ABSClient,
    spec: SDMXSeries,
    since: str | None = None,
    until: str | None = None,
) -> tuple[IndicatorRow, list[ObservationRow]]:
    """Fetch one ABS series; return (IndicatorRow, [ObservationRow])."""
    rows = client.fetch_series_csv(spec.dataflow, spec.key, since, until)
    obs = csv_rows_to_observations(rows, spec.imdr_code)
    ind = IndicatorRow(
        imdr_code=spec.imdr_code,
        vendor_name="ABS",
        source_code=spec.source_code,
        display_name=spec.display_name,
        unit=spec.unit,
        frequency=spec.frequency,
        country_iso="AU",
        category=spec.category,
        is_seasonally_adjusted=spec.is_sa,
    )
    return ind, obs
