"""Data access layer for fx.fact_fx_rate.

Reuses FXCurrencyPairRepository for dim seeding (imported from repository_vol).
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from imdr.connectors.bulk import MergeSpec, bulk_merge
from imdr.models.fx_rate import FXFactFXRate
from imdr.schemas.fx_rate import FXRateCreate

FX_RATE_SPEC = MergeSpec(
    target_table="[fx].[fact_fx_rate]",
    staging_name="#fx_fact_fx_rate_staging",
    columns={
        "pair_id": "INT",
        "vendor_id": "INT",
        "frequency_id": "TINYINT",
        "obs_ts": "DATETIMEOFFSET",
        "obs_date": "DATE",
        "tenor": "VARCHAR(5)",
        "mid_rate": "DECIMAL(18, 8)",
        "fwd_points": "DECIMAL(18, 10)",
    },
    natural_key=["pair_id", "vendor_id", "frequency_id", "obs_ts", "tenor"],
    value_columns=["mid_rate", "fwd_points"],
    nullable_columns=["fwd_points"],
)


class FXRateRepository:
    """Data access layer for [fx].[fact_fx_rate]."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def bulk_upsert(self, items: list[FXRateCreate]) -> int:
        """Upsert rate observations via shared temp→MERGE utility."""
        return bulk_merge(self._session, FX_RATE_SPEC, items)

    def count_by_date(self, obs_date: date) -> int:
        result = self._session.execute(
            select(func.count(FXFactFXRate.id)).where(
                FXFactFXRate.obs_date == obs_date
            )
        ).scalar_one()
        return result or 0
