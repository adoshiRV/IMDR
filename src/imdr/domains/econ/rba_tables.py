"""RBA statistical-table CSV parser + series builder for prod AU econ fetchers.

RBA tables (F1, F2, F11.1, D2, D3, E1, E2, A2, F15, F16, F17-*, G1, I1, I2)
follow a fixed multi-row header:
  Row 1: workbook title (e.g. "F11.1 EXCHANGE RATES")
  Rows 2-9: Title / Description / Frequency / Type / Units / blank / Source /
            Publication date
  Row 10: 'Series ID,FXRUSD,FXRTWI,...'  (canonical column codes)
  Row 11: blank
  Row 12+: data rows. Col 0 is date (DD-MMM-YYYY), cols 1.. are values.

CSVs live under ``data/econ/au/rba/samples/``. Refresh by running
``scripts/econ/au/rba/rba_snapshot_refresh.py`` (Playwright; Akamai blocks
plain HTTP).
"""
from __future__ import annotations

import csv
import datetime
from dataclasses import dataclass
from pathlib import Path

from imdr.domains.econ.schema import IndicatorRow, ObservationRow

UTC = datetime.timezone.utc

_REPO_ROOT = Path(__file__).resolve().parents[4]
SAMPLES_DIR = _REPO_ROOT / "data" / "econ" / "au" / "rba" / "samples"


@dataclass(frozen=True)
class RBASeries:
    """One RBA series to extract from a downloaded CSV."""

    table: str
    series_id: str
    imdr_code: str
    display_name: str
    unit: str
    frequency: str
    category: str
    is_sa: bool = False

    @property
    def source_code(self) -> str:
        return f"RBA.{self.table.upper()}.{self.series_id}"

    @property
    def csv_path(self) -> Path:
        return SAMPLES_DIR / f"{self.table}-data.csv"


def parse_rba_csv(path: Path) -> tuple[str, dict[str, list[tuple[datetime.date, float | None]]]]:
    """Parse an RBA statistical-table CSV.

    Returns ``(table_title, {series_id: [(date, value), ...]})``.
    """
    with open(path, encoding="utf-8-sig") as fp:
        reader = csv.reader(fp)
        rows = list(reader)
    if not rows:
        raise ValueError(f"empty file: {path}")
    title = rows[0][0]

    _MAX_HEADER_ROWS = 20
    sid_row_idx = None
    for i, row in enumerate(rows[:_MAX_HEADER_ROWS]):
        if row and row[0].strip().lower().startswith("series id"):
            sid_row_idx = i
            break
    if sid_row_idx is None:
        raise ValueError(f"no 'Series ID' header in {path}")

    series_ids = rows[sid_row_idx][1:]
    data_start = sid_row_idx + 1
    while data_start < len(rows) and (not rows[data_start] or not rows[data_start][0].strip()):
        data_start += 1

    series_data: dict[str, list[tuple[datetime.date, float | None]]] = {
        sid: [] for sid in series_ids if sid
    }
    for row in rows[data_start:]:
        if not row or not row[0].strip():
            continue
        d = _parse_date(row[0])
        if d is None:
            continue
        for i, sid in enumerate(series_ids):
            if not sid:
                continue
            col = i + 1
            if col >= len(row):
                continue
            cell = row[col].strip()
            v: float | None = None
            if cell:
                try:
                    v = float(cell.replace(",", ""))
                except ValueError:
                    v = None
            series_data[sid].append((d, v))
    return title, series_data


def _parse_date(s: str) -> datetime.date | None:
    s = s.strip()
    if not s:
        return None
    for fmt in ("%d-%b-%Y", "%d %b %Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def build_observations(
    series_data: dict[str, list[tuple[datetime.date, float | None]]],
    spec: RBASeries,
    since: datetime.date | None,
    until: datetime.date | None,
) -> tuple[IndicatorRow, list[ObservationRow]]:
    """Build (Indicator, [Observations]) for one RBASeries from parsed CSV data."""
    now = datetime.datetime.now(UTC)
    rows = series_data.get(spec.series_id, [])
    obs: list[ObservationRow] = []
    for d, v in rows:
        if since is not None and d < since:
            continue
        if until is not None and d > until:
            continue
        obs.append(ObservationRow(
            imdr_code=spec.imdr_code, obs_date=d, vintage=0,
            release_date=now, value=v, ingested_at=now,
        ))
    ind = IndicatorRow(
        imdr_code=spec.imdr_code, vendor_name="RBA", source_code=spec.source_code,
        display_name=spec.display_name, unit=spec.unit, frequency=spec.frequency,
        country_iso="AU", category=spec.category, is_seasonally_adjusted=spec.is_sa,
    )
    return ind, obs


def fetch_specs(
    specs: list[RBASeries],
    since: str | None,
    until: str | None,
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    """Convenience: parse the CSVs needed by ``specs``, return (indicators, observations).

    Each spec's CSV is parsed at most once, even if multiple specs share a table.
    """
    since_d = datetime.date.fromisoformat(since) if since else None
    until_d = datetime.date.fromisoformat(until) if until else None

    parsed_cache: dict[str, dict[str, list[tuple[datetime.date, float | None]]]] = {}
    indicators: list[IndicatorRow] = []
    observations: list[ObservationRow] = []
    for spec in specs:
        if spec.table not in parsed_cache:
            _, series_data = parse_rba_csv(spec.csv_path)
            parsed_cache[spec.table] = series_data
        ind, obs = build_observations(parsed_cache[spec.table], spec, since_d, until_d)
        if not obs:
            print(f"  WARN {spec.imdr_code:<48s} 0 obs (series_id={spec.series_id!r} not in CSV?)")
            continue
        indicators.append(ind)
        observations.extend(obs)
        print(f"  {spec.imdr_code:<48s} {len(obs):>5} obs")
    return indicators, observations
