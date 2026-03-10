"""Data access layer for rates domain tables.

Session is injected — the repository does NOT own its lifecycle.
"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

import structlog
from sqlalchemy import and_, func, select, text
from sqlalchemy.orm import Session

from imdr.models.rates import RatesCurve, RatesObservation
from imdr.schemas.rates import RatesCurveCreate, RatesObservationCreate

_log = structlog.get_logger("RatesObservationRepository")

# Batch size for MERGE temp table inserts
_MERGE_BATCH_SIZE = 1000


class RatesCurveRepository:
    """Data access layer for [rates].[dim_curve]."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, curve_id: int) -> RatesCurve | None:
        return self._session.get(RatesCurve, curve_id)

    def get_by_key(self, ccy: str, curve: str) -> RatesCurve | None:
        return self._session.execute(
            select(RatesCurve).where(
                RatesCurve.ccy == ccy.upper(),
                RatesCurve.curve == curve.upper(),
            )
        ).scalar_one_or_none()

    def get_or_create(self, data: RatesCurveCreate) -> RatesCurve:
        """Get existing curve or create new one."""
        existing = self.get_by_key(data.ccy, data.curve)
        if existing:
            return existing
        row = RatesCurve(**data.model_dump())
        self._session.add(row)
        self._session.flush()
        return row

    def all(self) -> Sequence[RatesCurve]:
        return self._session.scalars(select(RatesCurve)).all()

    def bulk_seed_from_universe(self, curves: list[RatesCurveCreate]) -> int:
        """Seed dimension table from universe config. Skips existing rows."""
        count = 0
        for data in curves:
            existing = self.get_by_key(data.ccy, data.curve)
            if not existing:
                self._session.add(RatesCurve(**data.model_dump()))
                count += 1
        self._session.flush()
        return count


class RatesObservationRepository:
    """Data access layer for [rates].[fact_observation]."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert(self, data: RatesObservationCreate) -> None:
        """Insert or update based on (curve_id, ts, quote, tenor)."""
        existing = self._session.execute(
            select(RatesObservation).where(
                RatesObservation.curve_id == data.curve_id,
                RatesObservation.ts == data.ts,
                RatesObservation.quote == data.quote,
                RatesObservation.tenor == data.tenor,
            )
        ).scalar_one_or_none()

        if existing:
            existing.value = data.value
        else:
            self._session.add(RatesObservation(**data.model_dump()))
        self._session.flush()

    def bulk_upsert(self, items: list[RatesObservationCreate]) -> int:
        """Upsert observations via SQL MERGE — single round-trip per batch.

        Uses a temp table + MERGE INTO for idempotent insert/update on
        the natural key (curve_id, ts, quote, tenor). Much faster than
        row-by-row for large batches (backfills).
        """
        if not items:
            return 0

        conn = self._session.connection()

        # 1. Create temp table (session-scoped, auto-dropped)
        conn.execute(text("""
            IF OBJECT_ID('tempdb..#rates_staging') IS NOT NULL
                DROP TABLE #rates_staging;
            CREATE TABLE #rates_staging (
                curve_id    INT             NOT NULL,
                ts          DATETIMEOFFSET  NOT NULL,
                quote       VARCHAR(10)     NOT NULL,
                tenor       VARCHAR(30)     NOT NULL,
                value       FLOAT           NOT NULL
            );
        """))

        # 2. Batch insert into temp table
        for i in range(0, len(items), _MERGE_BATCH_SIZE):
            batch = items[i : i + _MERGE_BATCH_SIZE]
            rows = [
                {
                    "curve_id": item.curve_id,
                    "ts": item.ts,
                    "quote": item.quote,
                    "tenor": item.tenor,
                    "value": item.value,
                }
                for item in batch
            ]
            conn.execute(
                text("""
                    INSERT INTO #rates_staging (curve_id, ts, quote, tenor, value)
                    VALUES (:curve_id, :ts, :quote, :tenor, :value)
                """),
                rows,
            )

        # 3. MERGE into fact table
        result = conn.execute(text("""
            MERGE [rates].[fact_observation] AS tgt
            USING #rates_staging AS src
                ON  tgt.curve_id = src.curve_id
                AND tgt.ts       = src.ts
                AND tgt.quote    = src.quote
                AND tgt.tenor    = src.tenor
            WHEN MATCHED THEN
                UPDATE SET
                    tgt.value      = src.value,
                    tgt.updated_at = SYSDATETIMEOFFSET()
            WHEN NOT MATCHED THEN
                INSERT (curve_id, ts, quote, tenor, value, created_at, updated_at)
                VALUES (src.curve_id, src.ts, src.quote, src.tenor, src.value,
                        SYSDATETIMEOFFSET(), SYSDATETIMEOFFSET());
        """))

        merged = result.rowcount
        _log.info("bulk_upsert_merge", total_items=len(items), rows_affected=merged)

        # 4. Cleanup
        conn.execute(text("DROP TABLE IF EXISTS #rates_staging;"))

        return len(items)

    def count_by_date(self, ts: datetime) -> int:
        """Count observations for a given timestamp."""
        result = self._session.execute(
            select(func.count(RatesObservation.id)).where(
                RatesObservation.ts == ts
            )
        ).scalar_one()
        return result or 0

    def count_by_curve(self, curve_id: int) -> int:
        result = self._session.execute(
            select(func.count(RatesObservation.id)).where(
                RatesObservation.curve_id == curve_id
            )
        ).scalar_one()
        return result or 0
