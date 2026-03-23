"""IMDR Data Access Layer.

Read-only access to FX and Rates market data. Import and use directly:

    from imdr.data_access import IMDRData

    data = IMDRData()
    pairs = data.list_fx_pairs()
    df = data.get_fx_spot("EURUSD", "2026-01-01", "2026-03-20")
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from imdr.config.settings import get_settings
from imdr.connectors.mssql import MSSQLConnector


def _parse_date(d: str | date) -> date:
    if isinstance(d, date):
        return d
    return datetime.strptime(d, "%Y-%m-%d").date()


class IMDRData:
    """Read-only data access to IMDR market data."""

    def __init__(self) -> None:
        settings = get_settings()
        self._connector = MSSQLConnector(settings)
        self._engine: Engine = self._connector.read_engine

    def _query(self, sql: str, params: dict[str, Any] | None = None) -> pd.DataFrame:
        with self._engine.connect() as conn:
            return pd.read_sql(text(sql), conn, params=params or {})

    def close(self) -> None:
        self._connector.dispose()

    # ── Discovery ────────────────────────────────────────────────────────

    def list_fx_pairs(self) -> pd.DataFrame:
        """All FX currency pairs with class (G10, EM, etc)."""
        return self._query(
            "SELECT id, base_ccy, quote_ccy, ccy_class "
            "FROM [fx].[dim_currency_pair] ORDER BY ccy_class, base_ccy"
        )

    def list_rates_curves(self) -> pd.DataFrame:
        """All rates curves with currency, type, and status."""
        return self._query(
            "SELECT id, ccy, curve, curve_type, curve_status, instrument "
            "FROM [rates].[dim_curve] ORDER BY ccy, curve"
        )

    def list_vol_surfaces(self) -> pd.DataFrame:
        """All swaption vol surfaces with currency and data type."""
        return self._query(
            "SELECT id, ccy, data_type, quote_type, vol_window, freq, is_rfr "
            "FROM [rates].[dim_vol_surface] ORDER BY ccy, data_type"
        )

    # ── FX Spot / OHLC ──────────────────────────────────────────────────

    def get_fx_spot(
        self,
        pair: str,
        start: str | date,
        end: str | date,
        series: str | None = None,
    ) -> pd.DataFrame:
        """FX spot OHLC data for a currency pair.

        Args:
            pair: e.g. "EURUSD"
            start: start date inclusive
            end: end date inclusive
            series: filter by series (e.g. "LDN_CLOSE"), or None for all
        """
        sql = (
            "SELECT ts, symbol, series, tenor, deal_type, "
            "open_px, high_px, low_px, close_px, mid_px, bid, ask, n_ticks "
            "FROM [fx].[fact_ohlc] "
            "WHERE symbol = :pair "
            "AND CAST(ts AS DATE) BETWEEN :start AND :end"
        )
        params: dict[str, Any] = {
            "pair": pair.upper(),
            "start": _parse_date(start),
            "end": _parse_date(end),
        }
        if series:
            sql += " AND series = :series"
            params["series"] = series
        sql += " ORDER BY ts"
        return self._query(sql, params)

    # ── FX Vol ───────────────────────────────────────────────────────────

    def get_fx_vol(
        self,
        pair: str,
        start: str | date,
        end: str | date,
        strike: str | None = None,
        tenor: str | None = None,
    ) -> pd.DataFrame:
        """FX implied/realized vol data.

        Args:
            pair: e.g. "EURUSD"
            start: start date inclusive
            end: end date inclusive
            strike: filter by strike (e.g. "ATM", "25RR"), or None for all
            tenor: filter by tenor (e.g. "1M", "1Y"), or None for all
        """
        sql = (
            "SELECT v.obs_date, p.base_ccy + p.quote_ccy AS pair, "
            "v.strike, v.tenor, v.vol_type, v.value "
            "FROM [fx].[fact_vol] v "
            "JOIN [fx].[dim_currency_pair] p ON v.pair_id = p.id "
            "WHERE p.base_ccy + p.quote_ccy = :pair "
            "AND v.obs_date BETWEEN :start AND :end"
        )
        params: dict[str, Any] = {
            "pair": pair.upper(),
            "start": _parse_date(start),
            "end": _parse_date(end),
        }
        if strike:
            sql += " AND v.strike = :strike"
            params["strike"] = strike
        if tenor:
            sql += " AND v.tenor = :tenor"
            params["tenor"] = tenor
        sql += " ORDER BY v.obs_date, v.tenor, v.strike"
        return self._query(sql, params)

    # ── Rates Curves ─────────────────────────────────────────────────────

    def get_rates_curve(
        self,
        ccy: str,
        start: str | date,
        end: str | date,
        curve: str | None = None,
        tenor: str | None = None,
    ) -> pd.DataFrame:
        """Rates curve observations (swap rates, OIS, etc).

        Args:
            ccy: currency code, e.g. "USD"
            start: start date inclusive
            end: end date inclusive
            curve: specific curve name, or None for all curves in that ccy
            tenor: filter by tenor (e.g. "5Y"), or None for all
        """
        sql = (
            "SELECT o.ts, c.ccy, c.curve, c.curve_type, "
            "o.quote, o.tenor, o.value "
            "FROM [rates].[fact_observation] o "
            "JOIN [rates].[dim_curve] c ON o.curve_id = c.id "
            "WHERE c.ccy = :ccy "
            "AND CAST(o.ts AS DATE) BETWEEN :start AND :end"
        )
        params: dict[str, Any] = {
            "ccy": ccy.upper(),
            "start": _parse_date(start),
            "end": _parse_date(end),
        }
        if curve:
            sql += " AND c.curve = :curve"
            params["curve"] = curve
        if tenor:
            sql += " AND o.tenor = :tenor"
            params["tenor"] = tenor
        sql += " ORDER BY o.ts, c.curve, o.tenor"
        return self._query(sql, params)

    # ── Swaption Vol ─────────────────────────────────────────────────────

    def get_swaption_vol(
        self,
        ccy: str,
        start: str | date,
        end: str | date,
        data_type: str | None = None,
    ) -> pd.DataFrame:
        """Swaption vol cube data (option_expiry x swap_tenor).

        Args:
            ccy: currency code, e.g. "USD"
            start: start date inclusive
            end: end date inclusive
            data_type: e.g. "ATM", "REALIZED", or None for all
        """
        sql = (
            "SELECT f.obs_date, s.ccy, s.data_type, s.quote_type, "
            "f.option_expiry, f.swap_tenor, f.value "
            "FROM [rates].[fact_swaption_vol] f "
            "JOIN [rates].[dim_vol_surface] s ON f.surface_id = s.id "
            "WHERE s.ccy = :ccy "
            "AND f.obs_date BETWEEN :start AND :end"
        )
        params: dict[str, Any] = {
            "ccy": ccy.upper(),
            "start": _parse_date(start),
            "end": _parse_date(end),
        }
        if data_type:
            sql += " AND s.data_type = :data_type"
            params["data_type"] = data_type
        sql += " ORDER BY f.obs_date, f.option_expiry, f.swap_tenor"
        return self._query(sql, params)

    # ── Generic ──────────────────────────────────────────────────────────

    def query(self, sql: str, params: dict[str, Any] | None = None) -> pd.DataFrame:
        """Run a custom SELECT query. Only SELECT statements are allowed."""
        first_word = sql.strip().split()[0].upper() if sql.strip() else ""
        if first_word != "SELECT":
            raise ValueError("Only SELECT queries are permitted.")
        return self._query(sql, params)
