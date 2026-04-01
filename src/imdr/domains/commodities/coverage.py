"""Commodities coverage analysis — returns structured data for all 3 sub-products.

Used by the cleaning CLI (--section coverage) and weekly dashboard.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from imdr.connectors.reader import AnalyticalReader
from imdr.healthchecks.dashboard import CoverageData


def _year_filter(years: list[int], date_col: str) -> tuple[str, dict[str, Any]]:
    if not years or len(years) >= 6:
        return "", {}
    placeholders = ", ".join(f":y{i}" for i in range(len(years)))
    where = f"AND YEAR([{date_col}]) IN ({placeholders})"
    params = {f"y{i}": y for i, y in enumerate(years)}
    return where, params


def get_cmdty_vol_coverage(
    reader: AnalyticalReader,
    table: str,
    years: list[int],
) -> CoverageData:
    """Per-product date coverage, strike x tenor grid, and row counts for implied vol."""
    year_filter, params = _year_filter(years, "obs_date")

    # Per-product date coverage
    sql_cov = f"""
        SELECT c.symbol AS product,
               c.commodity_class,
               COUNT(DISTINCT v.obs_date) AS actual_dates,
               MIN(v.obs_date) AS first_date,
               MAX(v.obs_date) AS last_date
        FROM {table} v
        JOIN [commodities].[dim_commodity] c ON c.id = v.commodity_id
        WHERE 1=1 {year_filter}
        GROUP BY c.symbol, c.commodity_class
        ORDER BY actual_dates DESC
    """
    df_cov = reader.read_sql(sql_cov, params)

    # Strike x tenor grid completeness (latest date per product)
    sql_grid = f"""
        WITH latest AS (
            SELECT commodity_id, MAX(obs_date) AS max_date
            FROM {table}
            WHERE 1=1 {year_filter}
            GROUP BY commodity_id
        )
        SELECT c.symbol AS product,
               COUNT(DISTINCT v.strike) AS strikes,
               COUNT(DISTINCT v.tenor) AS tenors,
               COUNT(*) AS rows_on_latest
        FROM {table} v
        JOIN latest l ON l.commodity_id = v.commodity_id AND v.obs_date = l.max_date
        JOIN [commodities].[dim_commodity] c ON c.id = v.commodity_id
        GROUP BY c.symbol
        ORDER BY product
    """
    df_grid = reader.read_sql(sql_grid, params)

    # Row counts by product
    sql_counts = f"""
        SELECT c.symbol AS product,
               COUNT(*) AS total_rows,
               COUNT(DISTINCT v.obs_date) AS dates,
               MIN(v.obs_date) AS first_date,
               MAX(v.obs_date) AS last_date
        FROM {table} v
        JOIN [commodities].[dim_commodity] c ON c.id = v.commodity_id
        WHERE 1=1 {year_filter}
        GROUP BY c.symbol
        ORDER BY total_rows DESC
    """
    df_counts = reader.read_sql(sql_counts, params)

    summary: dict[str, Any] = {}
    if not df_counts.empty:
        summary["grand_total_rows"] = int(df_counts["total_rows"].sum())
        summary["num_products"] = len(df_counts)

    return CoverageData(
        tables={"per_product": df_cov, "grid": df_grid, "row_counts": df_counts},
        summary=summary,
    )


def get_cmdty_spot_coverage(
    reader: AnalyticalReader,
    table: str,
    years: list[int],
) -> CoverageData:
    """Per-product date coverage for spot prices."""
    year_filter, params = _year_filter(years, "obs_date")

    sql = f"""
        SELECT c.symbol AS product,
               COUNT(DISTINCT s.obs_date) AS actual_dates,
               MIN(s.obs_date) AS first_date,
               MAX(s.obs_date) AS last_date,
               COUNT(*) AS total_rows
        FROM {table} s
        JOIN [commodities].[dim_commodity] c ON c.id = s.commodity_id
        WHERE 1=1 {year_filter}
        GROUP BY c.symbol
        ORDER BY product
    """
    df = reader.read_sql(sql, params)

    summary: dict[str, Any] = {}
    if not df.empty:
        summary["grand_total_rows"] = int(df["total_rows"].sum())
        summary["num_products"] = len(df)

    return CoverageData(tables={"per_product": df}, summary=summary)


def get_cmdty_eia_coverage(
    reader: AnalyticalReader,
    table: str,
    years: list[int],
) -> CoverageData:
    """Per-series coverage for EIA data."""
    year_filter, params = _year_filter(years, "obs_date")

    sql = f"""
        SELECT d.series_name, d.region,
               COUNT(DISTINCT e.obs_date) AS actual_dates,
               MIN(e.obs_date) AS first_date,
               MAX(e.obs_date) AS last_date,
               COUNT(*) AS total_rows
        FROM {table} e
        JOIN [commodities].[dim_eia_series] d ON d.id = e.eia_series_id
        WHERE 1=1 {year_filter}
        GROUP BY d.series_name, d.region
        ORDER BY d.series_name, d.region
    """
    df = reader.read_sql(sql, params)

    summary: dict[str, Any] = {}
    if not df.empty:
        summary["grand_total_rows"] = int(df["total_rows"].sum())
        summary["num_series"] = len(df)

    return CoverageData(tables={"per_series": df}, summary=summary)
