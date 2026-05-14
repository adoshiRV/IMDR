from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from imdr.connectors.bulk import MergeSpec, bulk_merge
from imdr.models.fx_ohlc import FXFactOHLC
from imdr.schemas.fx_ohlc import FXFactOHLCCreate

_FX_OHLC_SPEC = MergeSpec(
    target_table="[fx].[fact_ohlc]",
    staging_name="#fx_ohlc_staging",
    columns={
        "ts": "DATETIMEOFFSET",
        "symbol": "NVARCHAR(10)",
        "series": "NVARCHAR(30)",
        "tenor": "NVARCHAR(10)",
        "deal_type": "NVARCHAR(20)",
        "pair_used": "NVARCHAR(20)",
        "open_px": "FLOAT",
        "high_px": "FLOAT",
        "low_px": "FLOAT",
        "close_px": "FLOAT",
        "mid_px": "FLOAT",
        "mid_mean_px": "FLOAT",
        "mid_median_px": "FLOAT",
        "bid": "FLOAT",
        "ask": "FLOAT",
        "n_ticks": "INT",
    },
    natural_key=["ts", "symbol", "series", "tenor"],
    value_columns=[
        "deal_type", "pair_used",
        "open_px", "high_px", "low_px", "close_px", "mid_px",
        "mid_mean_px", "mid_median_px", "bid", "ask", "n_ticks",
    ],
    audit_columns={"created_at": "SYSDATETIMEOFFSET()"},
)


class FXOHLCRepository:
    """Data access layer for FX OHLC bars ([FX].[fact_ohlc]).

    The session is injected — the repository does NOT own its lifecycle.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def bulk_create(self, items: list[FXFactOHLCCreate]) -> list[FXFactOHLC]:
        bars = [FXFactOHLC(**d.model_dump()) for d in items]
        self._session.add_all(bars)
        self._session.flush()
        return bars

    def bulk_upsert(self, items: list[FXFactOHLCCreate]) -> int:
        """Upsert a batch of bars via temp-table MERGE."""
        return bulk_merge(self._session, _FX_OHLC_SPEC, items)

    def count_by_hour(self, ts: datetime) -> int:
        """Count bars for a given hour — used for completeness checks."""
        result = self._session.execute(
            select(func.count(FXFactOHLC.id)).where(FXFactOHLC.ts == ts)
        ).scalar_one()
        return result or 0

    def delete_range(self, start: datetime, end: datetime) -> int:
        """Delete bars in a time range — used for rewrite mode."""
        stmt = select(FXFactOHLC).where(
            and_(FXFactOHLC.ts >= start, FXFactOHLC.ts < end)
        )
        bars = self._session.scalars(stmt).all()
        count = len(bars)
        for bar in bars:
            self._session.delete(bar)
        self._session.flush()
        return count

    def get_last_close(self, symbol: str, series: str, before_ts: datetime) -> FXFactOHLC | None:
        """Get the most recent bar before a timestamp — used for anomaly pre-screen."""
        stmt = (
            select(FXFactOHLC)
            .where(
                FXFactOHLC.symbol == symbol,
                FXFactOHLC.series == series,
                FXFactOHLC.ts < before_ts,
            )
            .order_by(FXFactOHLC.ts.desc())
            .limit(1)
        )
        return self._session.execute(stmt).scalar_one_or_none()
