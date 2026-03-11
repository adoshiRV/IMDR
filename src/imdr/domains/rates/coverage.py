"""Rates coverage analysis — returns structured data for rates domain.

Used by report scripts (CLI print) and weekly dashboard (email rendering).
"""

from __future__ import annotations

from typing import Any

from imdr.connectors.reader import AnalyticalReader
from imdr.healthchecks.dashboard import CoverageData


def _year_filter(years: list[int]) -> tuple[str, dict[str, Any]]:
    """Build year filter clause + params for rates (ts column)."""
    if not years or len(years) >= 6:
        return "", {}
    placeholders = ", ".join(f":y{i}" for i in range(len(years)))
    where = f"AND YEAR([ts]) IN ({placeholders})"
    params = {f"y{i}": y for i, y in enumerate(years)}
    return where, params


def get_rates_coverage(
    reader: AnalyticalReader,
    table: str,
    years: list[int],
) -> CoverageData:
    """Per-curve date coverage, tenor completeness, quote distribution, row counts."""
    year_filter, params = _year_filter(years)

    # Per-curve date coverage
    sql_cov = f"""
        SELECT c.ccy, c.curve, c.curve_type,
               COUNT(DISTINCT CAST(o.ts AS DATE)) AS actual_dates,
               MIN(CAST(o.ts AS DATE)) AS first_date,
               MAX(CAST(o.ts AS DATE)) AS last_date
        FROM {table} o
        JOIN [rates].[dim_curve] c ON c.id = o.curve_id
        WHERE 1=1 {year_filter}
        GROUP BY c.ccy, c.curve, c.curve_type
        ORDER BY c.ccy, c.curve
    """
    df_cov = reader.read_sql(sql_cov, params)

    # Tenor completeness per curve×quote (latest date)
    sql_tenor = f"""
        WITH latest AS (
            SELECT curve_id, MAX(CAST(ts AS DATE)) AS max_date
            FROM {table}
            WHERE 1=1 {year_filter}
            GROUP BY curve_id
        )
        SELECT c.ccy, c.curve, o.quote,
               COUNT(DISTINCT o.tenor) AS tenors,
               COUNT(*) AS rows_on_latest
        FROM {table} o
        JOIN latest l ON l.curve_id = o.curve_id AND CAST(o.ts AS DATE) = l.max_date
        JOIN [rates].[dim_curve] c ON c.id = o.curve_id
        GROUP BY c.ccy, c.curve, o.quote
        ORDER BY c.ccy, c.curve, o.quote
    """
    df_tenor = reader.read_sql(sql_tenor, params)

    # Quote type distribution
    sql_quote = f"""
        SELECT o.quote,
               COUNT(*) AS total_rows,
               COUNT(DISTINCT o.curve_id) AS curves,
               COUNT(DISTINCT CAST(o.ts AS DATE)) AS dates
        FROM {table} o
        WHERE 1=1 {year_filter}
        GROUP BY o.quote
        ORDER BY total_rows DESC
    """
    df_quote = reader.read_sql(sql_quote, params)

    # Per-curve row count
    sql_counts = f"""
        SELECT c.ccy, c.curve, c.curve_type,
               COUNT(*) AS total_rows,
               COUNT(DISTINCT CAST(o.ts AS DATE)) AS dates,
               COUNT(DISTINCT o.quote) AS quotes,
               COUNT(DISTINCT o.tenor) AS tenors
        FROM {table} o
        JOIN [rates].[dim_curve] c ON c.id = o.curve_id
        WHERE 1=1 {year_filter}
        GROUP BY c.ccy, c.curve, c.curve_type
        ORDER BY total_rows DESC
    """
    df_counts = reader.read_sql(sql_counts, params)

    summary: dict[str, Any] = {}
    if not df_quote.empty:
        summary["grand_total_rows"] = int(df_quote["total_rows"].sum())
        summary["num_quote_types"] = len(df_quote)
    if not df_cov.empty:
        summary["num_curves"] = len(df_cov)

    return CoverageData(
        tables={
            "per_curve": df_cov,
            "tenor": df_tenor,
            "quote_dist": df_quote,
            "row_counts": df_counts,
        },
        summary=summary,
    )
