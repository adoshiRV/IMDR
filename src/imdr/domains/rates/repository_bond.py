"""Data access layer for the ISIN / per-bond grain (Track B — Govy Monitor).

Mirrors ``repository.py``'s shape (one repository class per table, upserts
routed through ``bulk_merge``). Migrations 112/113/114 (Track B) and
067/125/126 (Track C).

Session is injected — the repository does NOT own its lifecycle.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from imdr.connectors.bulk import MergeSpec, bulk_merge

# Importing these registers them with SQLAlchemy so dim_bond_instrument's
# country_id and the fact tables' vendor_id/frequency_id/currency_id FKs
# resolve at mapper-configuration time (same reason as the imports at the top
# of rates/repository.py). DimBondCurve — dim_bond_instrument.bond_curve_id's
# target — is not listed: it lives in models.rates_bond alongside
# DimBondInstrument, so it is always registered with it.
from imdr.models.country import DimCountry  # noqa: F401
from imdr.models.currency import DimCurrency  # noqa: F401
from imdr.models.frequency import DimFrequency  # noqa: F401
from imdr.models.rates_bond import DimBondInstrument, DimBondSource
from imdr.models.vendor import DimVendor  # noqa: F401
from imdr.schemas.rates_bond import (
    BondAuctionCreate,
    BondInstrumentCreate,
    BondInstrumentObsCreate,
    BondYieldCreate,
)

_DIM_BOND_INSTRUMENT_SPEC = MergeSpec(
    target_table="[dbo].[dim_bond_instrument]",
    staging_name="#dim_bond_instrument_staging",
    columns={
        "isin": "VARCHAR(20)",
        "bbg_ticker": "VARCHAR(30)",
        "country_id": "TINYINT",
        "ccy": "VARCHAR(3)",
        "issuer_code": "VARCHAR(30)",
        "bond_curve_id": "INT",
        "description": "VARCHAR(200)",
        "coupon": "FLOAT",
        "maturity_date": "DATE",
    },
    natural_key=["isin"],
    # bond_curve_id is deliberately NOT a value_column: the Govy ingest always
    # supplies it NULL (Track A/B curve-linking is a later step). Keeping it out
    # of the UPDATE set makes it insert-only — a re-run preserves any curve link
    # set externally instead of clobbering it back to NULL every scheduled load.
    value_columns=[
        "bbg_ticker", "country_id", "ccy", "issuer_code",
        "description", "coupon", "maturity_date",
    ],
    nullable_columns=["bbg_ticker", "bond_curve_id", "description", "coupon", "maturity_date"],
)

_FACT_BOND_INSTRUMENT_OBS_SPEC = MergeSpec(
    target_table="[rates].[fact_bond_instrument_obs]",
    staging_name="#fact_bond_instrument_obs_staging",
    columns={
        "instrument_id": "INT",
        "vendor_id": "INT",
        "frequency_id": "TINYINT",
        "obs_date": "DATE",
        "obs_ts": "DATETIMEOFFSET",
        "quote_type": "VARCHAR(20)",
        "tenor_years": "FLOAT",
        "value": "FLOAT",
        "chg_1d": "FLOAT",
        "chg_1w": "FLOAT",
        "chg_1m": "FLOAT",
        "chg_3m": "FLOAT",
        "pricing_source": "VARCHAR(12)",
        "units": "VARCHAR(10)",
        "source_app": "VARCHAR(20)",
    },
    natural_key=["instrument_id", "vendor_id", "obs_date", "quote_type", "pricing_source"],
    value_columns=[
        "frequency_id", "obs_ts", "tenor_years", "value",
        "chg_1d", "chg_1w", "chg_1m", "chg_3m", "units", "source_app",
    ],
    nullable_columns=["chg_1d", "chg_1w", "chg_1m", "chg_3m"],
)

_FACT_BOND_AUCTION_SPEC = MergeSpec(
    target_table="[rates].[fact_bond_auction]",
    staging_name="#fact_bond_auction_staging",
    columns={
        "country_id": "TINYINT",
        "auction_date": "DATE",
        "security_type": "VARCHAR(30)",
        "term": "VARCHAR(10)",
        "isin": "VARCHAR(20)",
        "cusip": "VARCHAR(20)",
        "coupon": "FLOAT",
        "maturity_date": "DATE",
        "reopening": "BIT",
        "offered_amount": "FLOAT",
        "currency_id": "TINYINT",
        "source": "VARCHAR(30)",
        "fetched_at": "DATETIMEOFFSET",
    },
    natural_key=["country_id", "auction_date", "security_type", "term", "isin"],
    value_columns=[
        "cusip", "coupon", "maturity_date", "reopening",
        "offered_amount", "currency_id", "source", "fetched_at",
    ],
    nullable_columns=[
        "cusip", "coupon", "maturity_date", "reopening",
        "offered_amount", "currency_id", "source",
    ],
)


class BondInstrumentRepository:
    """Data access layer for [dbo].[dim_bond_instrument]."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def seed_and_resolve(self, items: list[BondInstrumentCreate]) -> dict[str, int]:
        """Upsert instrument rows, then read back ``isin -> id`` for the batch.

        The read-back happens in the same session/transaction as the MERGE,
        so it sees the just-inserted rows without needing an intermediate
        commit.
        """
        if not items:
            return {}
        bulk_merge(self._session, _DIM_BOND_INSTRUMENT_SPEC, items)
        isins = [item.isin for item in items]
        rows = self._session.execute(
            select(DimBondInstrument.isin, DimBondInstrument.id).where(
                DimBondInstrument.isin.in_(isins)
            )
        ).all()
        return {isin: instrument_id for isin, instrument_id in rows}


class BondInstrumentObsRepository:
    """Data access layer for [rates].[fact_bond_instrument_obs]."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def bulk_upsert(self, items: list[BondInstrumentObsCreate]) -> int:
        return bulk_merge(self._session, _FACT_BOND_INSTRUMENT_OBS_SPEC, items)


class BondAuctionRepository:
    """Data access layer for [rates].[fact_bond_auction]."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def bulk_upsert(self, items: list[BondAuctionCreate]) -> int:
        return bulk_merge(self._session, _FACT_BOND_AUCTION_SPEC, items)


# Track C -- the CMT grain. Natural key is the deployed uq_fact_bond_yield: the full
# 5-axis decomposition plus (curve, vendor, date). source_ticker is NOT in the key --
# it is provenance, and a curve point is defined by its axes, not by which vendor string
# delivered it. It stays a value_column so a re-point (e.g. GITN10 Index -> GTITL10Y Govt
# on the same curve point) updates in place instead of orphaning the old rows.
_FACT_BOND_YIELD_SPEC = MergeSpec(
    target_table="[rates].[fact_bond_yield]",
    staging_name="#fact_bond_yield_staging",
    columns={
        "bond_curve_id": "INT",
        "vendor_id": "INT",
        "frequency_id": "TINYINT",
        "obs_date": "DATE",
        "obs_ts": "DATETIMEOFFSET",
        "tenor_code": "VARCHAR(10)",
        "tenor_days": "INT",
        "quote_type": "VARCHAR(20)",
        "spread_anchor": "VARCHAR(20)",
        "fwd_start": "VARCHAR(10)",
        "horizon": "VARCHAR(10)",
        "value": "FLOAT",
        "units": "VARCHAR(10)",
        "source_ticker": "VARCHAR(80)",
    },
    natural_key=[
        "bond_curve_id", "vendor_id", "obs_date", "tenor_code",
        "quote_type", "spread_anchor", "fwd_start", "horizon",
    ],
    value_columns=["frequency_id", "obs_ts", "tenor_days", "value", "units", "source_ticker"],
    nullable_columns=[],
)


class BondYieldRepository:
    """Data access layer for [rates].[fact_bond_yield] (CMT grain)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def resolve_sources(self, vendor_id: int) -> dict[str, dict]:
        """Return ``UPPER(source_ticker) -> {curve_id, tenor_code, tenor_days, axes...}``.

        The ingest resolves a vendor ticker to a curve point through THIS table, not
        through a (ccy, yield_type, country) tuple: migration 125 deliberately authors
        curves that share an identity tuple and differ only by ticker family (JPY GJGB10
        vs GTJPY*, AUD GTAUDII* vs CTAUDII*, JPY GTJPYII10Y vs GTJPYII10YR), so the tuple
        is ambiguous by construction while ``uq_dim_bond_source_ticker`` guarantees the
        ticker is not. Keyed upper-case because the seeded strings are byte-exact vendor
        forms with inconsistent case ('Govt' vs 'INDEX').
        """
        rows = self._session.execute(
            select(
                DimBondSource.source_ticker,
                DimBondSource.bond_curve_id,
                DimBondSource.tenor_code,
                DimBondSource.tenor_days,
                DimBondSource.quote_type,
                DimBondSource.spread_anchor,
                DimBondSource.fwd_start,
                DimBondSource.horizon,
                DimBondSource.units,
            ).where(
                DimBondSource.vendor_id == vendor_id,
                # `== True` not `.is_(True)`: SQL Server has no boolean type and
                # rejects `IS 1` on a BIT column.
                DimBondSource.is_active == True,  # noqa: E712
            )
        ).all()
        return {
            r.source_ticker.strip().upper(): {
                "bond_curve_id": r.bond_curve_id,
                "tenor_code": r.tenor_code,
                "tenor_days": r.tenor_days,
                "quote_type": r.quote_type,
                "spread_anchor": r.spread_anchor,
                "fwd_start": r.fwd_start,
                "horizon": r.horizon,
                "units": r.units,
            }
            for r in rows
        }

    def bulk_upsert(self, items: list[BondYieldCreate]) -> int:
        return bulk_merge(self._session, _FACT_BOND_YIELD_SPEC, items)
