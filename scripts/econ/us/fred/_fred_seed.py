"""Shared seed loader + fetch loop for the US FRED prod fetchers.

Reads scripts/econ/us/fred/seed_us.yml (the curated ACTIVE US FRED set — the 26
source-agency-dup series deactivated by migration 106 are intentionally absent,
so a reload never re-activates them; categories reflect the post-106 state) and
pulls each series from the FRED API.

Frequency-split: fred_us_daily.py owns DAILY+WEEKLY, fred_us_monthly.py owns
MONTHLY+QUARTERLY+ANNUAL — so high-frequency financial-conditions series refresh
on the daily cron while the slow movers ride the monthly run. Both reuse this.
"""

from __future__ import annotations

import datetime
import time
from pathlib import Path

import yaml

from imdr.domains.econ.fred_http import FredClient
from imdr.domains.econ.schema import IndicatorRow, ObservationRow

UTC = datetime.timezone.utc
_SEED_PATH = Path(__file__).parent / "seed_us.yml"
_THROTTLE_SEC = 0.5  # 120 req/min/key; dual-key rotation in the connector


def load_seed(freqs: set[str]) -> list[IndicatorRow]:
    """Load seed entries whose frequency is in ``freqs`` as IndicatorRows."""
    raw = yaml.safe_load(_SEED_PATH.read_text(encoding="utf-8"))
    rows: list[IndicatorRow] = []
    for it in raw["indicators"]:
        if it["frequency"] not in freqs:
            continue
        rows.append(IndicatorRow(
            imdr_code=it["imdr_code"],
            vendor_name="FRED",
            source_code=it["source_code"],
            display_name=it["description"],
            unit=it["unit"],
            frequency=it["frequency"],
            country_iso=it.get("country_iso", "US"),
            category=it["category"],
            is_seasonally_adjusted=it.get("is_seasonally_adjusted", False),
            bbg_ticker=it.get("bbg_ticker"),
        ))
    return rows


def fetch_seed(
    freqs: set[str],
    since: str | None,
    until: str | None,
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    """Fetch every seed series in ``freqs`` from FRED; return (dims, facts)."""
    seed = load_seed(freqs)
    now = datetime.datetime.now(UTC)
    start = since or "2010-01-01"

    indicators: list[IndicatorRow] = []
    observations: list[ObservationRow] = []

    with FredClient() as client:
        for ind in seed:
            try:
                raw = client.fetch_series(ind.source_code, start=start, end=until)
            except Exception as exc:  # noqa: BLE001 — one bad series shouldn't kill the run
                print(f"  ERROR {ind.source_code}: {type(exc).__name__}: {str(exc)[:80]}")
                time.sleep(_THROTTLE_SEC)
                continue
            n = 0
            for obs in raw:
                try:
                    obs_date = datetime.date.fromisoformat(obs.get("date", ""))
                except (ValueError, TypeError):
                    continue
                val = obs.get("value")
                try:
                    value = float(val) if val not in (None, "", ".") else None
                except (ValueError, TypeError):
                    value = None
                observations.append(ObservationRow(
                    imdr_code=ind.imdr_code, obs_date=obs_date, vintage=0,
                    release_date=now, value=value, ingested_at=now,
                ))
                n += 1
            indicators.append(ind)
            print(f"  {ind.source_code:20} {ind.imdr_code:42} {n} obs")
            time.sleep(_THROTTLE_SEC)

    return indicators, observations
