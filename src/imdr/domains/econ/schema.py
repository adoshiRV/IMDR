"""Dataclasses mirroring econ.dim_indicator + econ.fact_indicator.

Lightweight containers used by every prod fetcher to write consistent
parquet against the canonical schema. Column names and types match
§3.2 / §3.3 of docs/admin/development/economics_data_ingest.md so the
load step (scripts.migrations.load_econ_indicator_from_playground)
sees the same shape it does for playground output.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field


VALID_CATEGORIES = frozenset({
    "cpi", "gdp", "labour", "bop", "balance_sheet",
    "rates", "fx", "housing", "credit", "sentiment",
    "energy", "tourism", "other",
    "liquidity", "cb_facility", "cb_balance_sheet", "instr_outstand",
})

VALID_FREQUENCIES = frozenset({
    "TICK", "SNAPSHOT", "MINUTE", "HOURLY",
    "DAILY", "WEEKLY", "MONTHLY", "QUARTERLY", "ANNUAL", "EVENT",
})


@dataclass
class IndicatorRow:
    """One entry in econ.dim_indicator."""

    imdr_code: str
    vendor_name: str
    source_code: str
    display_name: str
    unit: str
    frequency: str
    country_iso: str | None
    category: str
    is_seasonally_adjusted: bool = False
    is_active: bool = True
    bbg_ticker: str | None = None

    def __post_init__(self) -> None:
        if self.category not in VALID_CATEGORIES:
            raise ValueError(
                f"IndicatorRow.category must be one of {sorted(VALID_CATEGORIES)!r}, "
                f"got {self.category!r}"
            )
        if self.frequency not in VALID_FREQUENCIES:
            raise ValueError(
                f"IndicatorRow.frequency must be one of {sorted(VALID_FREQUENCIES)!r}, "
                f"got {self.frequency!r}"
            )
        if not self.imdr_code:
            raise ValueError("IndicatorRow.imdr_code must not be empty")
        if not self.source_code:
            raise ValueError("IndicatorRow.source_code must not be empty")


@dataclass
class ObservationRow:
    """One entry in econ.fact_indicator."""

    imdr_code: str
    obs_date: datetime.date
    vintage: int
    release_date: datetime.datetime
    value: float | None
    is_preliminary: bool = False
    ingested_at: datetime.datetime = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )

    def __post_init__(self) -> None:
        if self.vintage < 0:
            raise ValueError(
                f"ObservationRow.vintage must be >= 0, got {self.vintage}"
            )
        if not self.imdr_code:
            raise ValueError("ObservationRow.imdr_code must not be empty")


def indicators_to_records(rows: list[IndicatorRow]) -> list[dict]:
    return [
        {
            "imdr_code": r.imdr_code,
            "vendor_name": r.vendor_name,
            "source_code": r.source_code,
            "display_name": r.display_name,
            "unit": r.unit,
            "frequency": r.frequency,
            "country_iso": r.country_iso,
            "category": r.category,
            "is_seasonally_adjusted": r.is_seasonally_adjusted,
            "is_active": r.is_active,
            "bbg_ticker": r.bbg_ticker,
        }
        for r in rows
    ]


def observations_to_records(rows: list[ObservationRow]) -> list[dict]:
    return [
        {
            "imdr_code": r.imdr_code,
            "obs_date": r.obs_date,
            "vintage": r.vintage,
            "release_date": r.release_date,
            "value": r.value,
            "is_preliminary": r.is_preliminary,
            "ingested_at": r.ingested_at,
        }
        for r in rows
    ]
