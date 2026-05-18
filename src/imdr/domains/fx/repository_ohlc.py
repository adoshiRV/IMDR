from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import delete, select
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

    def bulk_upsert(self, items: list[FXFactOHLCCreate]) -> int:
        """Upsert a batch of bars via temp-table MERGE."""
        return bulk_merge(self._session, _FX_OHLC_SPEC, items)

    def delete_range(self, start: datetime, end: datetime) -> int:
        """Delete bars in a time range — used for rewrite mode."""
        result = self._session.execute(
            delete(FXFactOHLC).where(
                FXFactOHLC.ts >= start,
                FXFactOHLC.ts < end,
            )
        )
        self._session.flush()
        return result.rowcount or 0

    def get_last_closes_batch(
        self,
        keys: list[tuple[str, str]],
        before_ts: datetime,
        lookback_days: int = 7,
    ) -> dict[tuple[str, str], FXFactOHLC]:
        """Batched version of get_last_close — one query for many (symbol, series).

        Returns a dict keyed on (symbol, series); missing pairs are absent.
        Bounds the lookback to `lookback_days` before `before_ts` so the
        candidate set stays small even on tables with multi-year history.

        Replaces an N+1 loop of get_last_close() — see pipeline_ohlc.py
        _anomaly_prescreen for the live caller.
        """
        if not keys:
            return {}
        lower_bound = before_ts - timedelta(days=lookback_days)
        symbols = {s for s, _ in keys}
        series_set = {ser for _, ser in keys}

        # Cartesian filter (symbol IN × series IN) over-fetches mildly but the
        # time window keeps the row count bounded. Python loop trims to the
        # exact keys requested.
        stmt = (
            select(FXFactOHLC)
            .where(
                FXFactOHLC.symbol.in_(symbols),
                FXFactOHLC.series.in_(series_set),
                FXFactOHLC.ts < before_ts,
                FXFactOHLC.ts >= lower_bound,
            )
            .order_by(FXFactOHLC.symbol, FXFactOHLC.series, FXFactOHLC.ts.desc())
        )
        rows = self._session.execute(stmt).scalars().all()

        keys_set = set(keys)
        out: dict[tuple[str, str], FXFactOHLC] = {}
        for row in rows:
            key = (row.symbol, row.series)
            if key in keys_set and key not in out:
                out[key] = row
        return out
