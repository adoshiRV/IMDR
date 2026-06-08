"""Cross-asset snapshot from IMDR — FX, UST, VIX, commodities.

Returns a structured dataclass that the chart layer + KPI layer both
consume. Each query computes the last value and the lagged value for a
5-day comparison.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import text
from sqlalchemy.engine import Connection


@dataclass
class FxRow:
    pair: str
    spot: float
    pct_chg_5d: float | None
    as_of: str | None


@dataclass
class RateRow:
    code: str
    yield_pct: float
    bp_chg_5d: float | None
    as_of: date | None


@dataclass
class VixRow:
    ticker: str
    level: float
    chg_5d: float | None
    as_of: date | None


@dataclass
class CommodityRow:
    symbol: str
    price: float
    pct_chg_5d: float | None
    as_of: date | None


@dataclass
class CrossAssetSnapshot:
    fx: list[FxRow] = field(default_factory=list)
    rates: list[RateRow] = field(default_factory=list)
    vix: list[VixRow] = field(default_factory=list)
    commodities: list[CommodityRow] = field(default_factory=list)


_FX_PAIRS = [
    ("EUR", "USD"), ("GBP", "USD"), ("AUD", "USD"),
    ("USD", "JPY"), ("USD", "CAD"), ("USD", "CHF"),
    ("USD", "KRW"), ("USD", "INR"),
]

_UST_CODES = ("DGS2", "DGS5", "DGS10", "DGS30")
_VIX_TICKERS = ("VIX", "VIX9D", "VIX3M", "VVIX", "VXN")
_COMMOD = ("CR_NYM_CL", "XAU", "XAG")


def load_cross_asset(cx: Connection, lookback_days: int = 6) -> CrossAssetSnapshot:
    """Pull last value + ``lookback_days``-ago value for FX, UST, VIX, commodities.

    The lookback comparison anchors at the most recent tick. For FX
    (intraday) we anchor at ``GETUTCDATE()``; for UST/VIX/commodities
    (daily) the lag is positional within each series.
    """
    snap = CrossAssetSnapshot()

    # ---- FX ----
    for base, quote in _FX_PAIRS:
        row = cx.execute(text("""
            WITH latest AS (
              SELECT r.mid_rate, r.obs_ts,
                     ROW_NUMBER() OVER (ORDER BY r.obs_ts DESC) AS rn
              FROM fx.fact_fx_rate r
              JOIN fx.dim_currency_pair p ON p.id = r.pair_id
              WHERE r.tenor='SPOT' AND p.base_ccy=:b AND p.quote_ccy=:q
            ),
            past AS (
              SELECT r.mid_rate, r.obs_ts,
                     ROW_NUMBER() OVER (ORDER BY r.obs_ts DESC) AS rn
              FROM fx.fact_fx_rate r
              JOIN fx.dim_currency_pair p ON p.id = r.pair_id
              WHERE r.tenor='SPOT' AND p.base_ccy=:b AND p.quote_ccy=:q
                AND r.obs_ts < DATEADD(day, -:lb, GETUTCDATE())
            )
            SELECT
              CAST(l.mid_rate AS float) AS spot_now,
              l.obs_ts AS now_ts,
              CAST(p.mid_rate AS float) AS spot_past,
              CASE WHEN p.mid_rate IS NULL OR p.mid_rate = 0 THEN NULL
                   ELSE CAST((l.mid_rate - p.mid_rate) / p.mid_rate * 100 AS float)
              END AS pct_chg
            FROM latest l LEFT JOIN past p ON p.rn = 1
            WHERE l.rn = 1
        """), {"b": base, "q": quote, "lb": lookback_days}).fetchone()
        if row is not None:
            snap.fx.append(FxRow(
                pair=f"{base}/{quote}",
                spot=float(row.spot_now),
                pct_chg_5d=row.pct_chg,
                as_of=row.now_ts.isoformat() if row.now_ts else None,
            ))

    # ---- UST (FRED daily, positional 5-back) ----
    for code in _UST_CODES:
        row = cx.execute(text("""
            WITH s AS (
              SELECT f.obs_date, f.value,
                     ROW_NUMBER() OVER (ORDER BY f.obs_date DESC) AS rn
              FROM econ.fact_indicator f
              JOIN econ.dim_indicator i ON i.id = f.indicator_id
              WHERE i.source_code = :c
            )
            SELECT
              MAX(CASE WHEN rn=1 THEN obs_date END) AS now_date,
              MAX(CASE WHEN rn=1 THEN value END)    AS now_val,
              MAX(CASE WHEN rn=:n THEN value END)   AS past_val
            FROM s
        """), {"c": code, "n": lookback_days}).fetchone()
        if row and row.now_val is not None:
            snap.rates.append(RateRow(
                code=code,
                yield_pct=float(row.now_val),
                bp_chg_5d=(float(row.now_val) - float(row.past_val)) * 100 if row.past_val else None,
                as_of=row.now_date,
            ))

    # ---- VIX (positional 5-back) ----
    for t in _VIX_TICKERS:
        row = cx.execute(text("""
            WITH s AS (
              SELECT obs_date, close_level,
                     ROW_NUMBER() OVER (ORDER BY obs_date DESC) AS rn
              FROM equities.fact_vix WHERE ticker = :t
            )
            SELECT
              MAX(CASE WHEN rn=1 THEN obs_date END) AS now_date,
              MAX(CASE WHEN rn=1 THEN close_level END) AS now_val,
              MAX(CASE WHEN rn=:n THEN close_level END) AS past_val
            FROM s
        """), {"t": t, "n": lookback_days}).fetchone()
        if row and row.now_val is not None:
            snap.vix.append(VixRow(
                ticker=t,
                level=float(row.now_val),
                chg_5d=(float(row.now_val) - float(row.past_val)) if row.past_val else None,
                as_of=row.now_date,
            ))

    # ---- Commodities ----
    for sym in _COMMOD:
        row = cx.execute(text("""
            WITH s AS (
              SELECT s.obs_date, s.price,
                     ROW_NUMBER() OVER (ORDER BY s.obs_date DESC) AS rn
              FROM commodities.fact_spot s
              JOIN commodities.dim_commodity c ON c.id = s.commodity_id
              WHERE c.symbol = :sym
            )
            SELECT
              MAX(CASE WHEN rn=1 THEN obs_date END) AS now_date,
              MAX(CASE WHEN rn=1 THEN price END)    AS now_val,
              MAX(CASE WHEN rn=:n THEN price END)   AS past_val
            FROM s
        """), {"sym": sym, "n": lookback_days}).fetchone()
        if row and row.now_val is not None:
            snap.commodities.append(CommodityRow(
                symbol=sym,
                price=float(row.now_val),
                pct_chg_5d=(float(row.now_val) / float(row.past_val) - 1) * 100 if row.past_val else None,
                as_of=row.now_date,
            ))

    return snap
