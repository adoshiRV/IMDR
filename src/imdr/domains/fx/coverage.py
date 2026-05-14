"""FX coverage analysis — returns structured data for OHLC and Vol domains.

Used by report scripts (CLI print) and weekly dashboard (email rendering).
"""

from __future__ import annotations

from typing import Any

from imdr.connectors.reader import AnalyticalReader
from imdr.healthchecks.dashboard import CoverageData
from imdr.healthchecks.quality import CoverageAnalyzer
from imdr.universe.fx import get_fx_universe


def _year_filter(
    years: list[int],
    date_col: str,
) -> tuple[str, dict[str, Any]]:
    """Build year filter clause + params."""
    if not years or len(years) >= 6:
        return "", {}
    placeholders = ", ".join(f":y{i}" for i in range(len(years)))
    where = f"AND YEAR([{date_col}]) IN ({placeholders})"
    params = {f"y{i}": y for i, y in enumerate(years)}
    return where, params


# ---------------------------------------------------------------------------
# FX OHLC coverage (market-hours aware)
# ---------------------------------------------------------------------------

def get_ohlc_coverage(
    reader: AnalyticalReader,
    table: str,
    years: list[int],
) -> CoverageData:
    """Per-symbol coverage and gaps for FX OHLC data."""
    universe = get_fx_universe()
    year_filter, params = _year_filter(years, "ts")

    analyzer = CoverageAnalyzer(
        ts_column="ts",
        symbol_column="symbol",
        is_market_open=universe.is_fx_open,
    )

    df_cov = analyzer.coverage(reader, table, where=year_filter, params=params)
    if not df_cov.empty:
        def _classify(sym: str) -> str:
            non_usd = sym.replace("USD", "")
            try:
                return universe.classification_for(non_usd)
            except KeyError:
                return "unknown"
        df_cov.insert(1, "class", df_cov["symbol"].apply(_classify))

    df_gaps = analyzer.gaps(reader, table, where=year_filter, params=params)

    summary: dict[str, Any] = {}
    if not df_cov.empty:
        summary["total_missing_hours"] = int(df_cov["missing_hours"].sum())
        summary["avg_coverage_pct"] = round(df_cov["coverage_pct"].mean(), 1)
        summary["worst_symbol"] = df_cov.iloc[0]["symbol"]
        summary["worst_pct"] = round(df_cov.iloc[0]["coverage_pct"], 1)
        summary["best_symbol"] = df_cov.iloc[-1]["symbol"]
        summary["best_pct"] = round(df_cov.iloc[-1]["coverage_pct"], 1)

    return CoverageData(
        tables={"per_symbol": df_cov, "gaps": df_gaps},
        summary=summary,
    )


# ---------------------------------------------------------------------------
# FX Vol coverage
# ---------------------------------------------------------------------------

def get_vol_coverage(
    reader: AnalyticalReader,
    table: str,
    years: list[int],
) -> CoverageData:
    """Per-pair date coverage, strike×tenor grid, and row counts for FX Vol."""
    year_filter, params = _year_filter(years, "obs_date")

    # Per-pair date coverage
    sql_cov = f"""
        SELECT p.base_ccy + p.quote_ccy AS pair,
               p.ccy_class,
               COUNT(DISTINCT v.obs_date) AS actual_dates,
               MIN(v.obs_date) AS first_date,
               MAX(v.obs_date) AS last_date
        FROM {table} v
        JOIN [fx].[dim_currency_pair] p ON p.id = v.pair_id
        WHERE 1=1 {year_filter}
        GROUP BY p.base_ccy, p.quote_ccy, p.ccy_class
        ORDER BY actual_dates DESC
    """
    df_cov = reader.read_sql(sql_cov, params)

    # Strike×tenor grid completeness (latest date)
    sql_grid = f"""
        WITH latest AS (
            SELECT pair_id, MAX(obs_date) AS max_date
            FROM {table}
            WHERE 1=1 {year_filter}
            GROUP BY pair_id
        )
        SELECT p.base_ccy + p.quote_ccy AS pair,
               COUNT(DISTINCT v.strike) AS strikes,
               COUNT(DISTINCT v.tenor) AS tenors,
               COUNT(*) AS rows_on_latest
        FROM {table} v
        JOIN latest l ON l.pair_id = v.pair_id AND v.obs_date = l.max_date
        JOIN [fx].[dim_currency_pair] p ON p.id = v.pair_id
        GROUP BY p.base_ccy, p.quote_ccy
        ORDER BY pair
    """
    df_grid = reader.read_sql(sql_grid, params)

    # Row count by pair
    sql_counts = f"""
        SELECT p.base_ccy + p.quote_ccy AS pair,
               COUNT(*) AS total_rows,
               COUNT(DISTINCT v.obs_date) AS dates,
               MIN(v.obs_date) AS first,
               MAX(v.obs_date) AS last
        FROM {table} v
        JOIN [fx].[dim_currency_pair] p ON p.id = v.pair_id
        WHERE 1=1 {year_filter}
        GROUP BY p.base_ccy, p.quote_ccy
        ORDER BY total_rows DESC
    """
    df_counts = reader.read_sql(sql_counts, params)

    summary: dict[str, Any] = {}
    if not df_counts.empty:
        summary["grand_total_rows"] = int(df_counts["total_rows"].sum())
        summary["num_pairs"] = len(df_counts)

    return CoverageData(
        tables={"per_pair": df_cov, "grid": df_grid, "row_counts": df_counts},
        summary=summary,
    )


# ---------------------------------------------------------------------------
# FX Rate coverage (Citi spot + forward curve)
# ---------------------------------------------------------------------------

def get_fx_rate_coverage(
    reader: AnalyticalReader,
    table: str,
    years: list[int],
) -> CoverageData:
    """Per-pair date coverage, tenor grid, and row counts for fx.fact_fx_rate."""
    year_filter, params = _year_filter(years, "obs_date")

    # Per-pair date coverage (joined with vendor + frequency for visibility)
    sql_cov = f"""
        SELECT p.base_ccy + p.quote_ccy AS pair,
               p.ccy_class,
               v.vendor_code,
               f.frequency_code,
               COUNT(DISTINCT r.obs_date) AS actual_dates,
               MIN(r.obs_date) AS first_date,
               MAX(r.obs_date) AS last_date
        FROM {table} r
        JOIN [fx].[dim_currency_pair] p ON p.id = r.pair_id
        JOIN [dbo].[dim_vendor]       v ON v.id = r.vendor_id
        JOIN [dbo].[dim_frequency]    f ON f.id = r.frequency_id
        WHERE 1=1 {year_filter}
        GROUP BY p.base_ccy, p.quote_ccy, p.ccy_class, v.vendor_code, f.frequency_code
        ORDER BY actual_dates DESC
    """
    df_cov = reader.read_sql(sql_cov, params)

    # Tenor grid on the latest date per pair (shows fwd_points coverage too)
    sql_grid = f"""
        WITH latest AS (
            SELECT pair_id, MAX(obs_date) AS max_date
            FROM {table}
            WHERE 1=1 {year_filter}
            GROUP BY pair_id
        )
        SELECT p.base_ccy + p.quote_ccy AS pair,
               COUNT(DISTINCT r.tenor) AS tenors,
               SUM(CASE WHEN r.fwd_points IS NOT NULL THEN 1 ELSE 0 END) AS with_points,
               COUNT(*) AS rows_on_latest,
               MAX(r.obs_date) AS latest_date
        FROM {table} r
        JOIN latest l ON l.pair_id = r.pair_id AND r.obs_date = l.max_date
        JOIN [fx].[dim_currency_pair] p ON p.id = r.pair_id
        GROUP BY p.base_ccy, p.quote_ccy
        ORDER BY pair
    """
    df_grid = reader.read_sql(sql_grid, params)

    # Row count by pair
    sql_counts = f"""
        SELECT p.base_ccy + p.quote_ccy AS pair,
               COUNT(*) AS total_rows,
               COUNT(DISTINCT r.obs_date) AS dates,
               MIN(r.obs_date) AS first_date,
               MAX(r.obs_date) AS last_date
        FROM {table} r
        JOIN [fx].[dim_currency_pair] p ON p.id = r.pair_id
        WHERE 1=1 {year_filter}
        GROUP BY p.base_ccy, p.quote_ccy
        ORDER BY total_rows DESC
    """
    df_counts = reader.read_sql(sql_counts, params)

    summary: dict[str, Any] = {}
    if not df_counts.empty:
        summary["grand_total_rows"] = int(df_counts["total_rows"].sum())
        summary["num_pairs"] = len(df_counts)

    return CoverageData(
        tables={"per_pair": df_cov, "grid": df_grid, "row_counts": df_counts},
        summary=summary,
    )
