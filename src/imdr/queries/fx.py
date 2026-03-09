"""Canned SQL queries for FX analytics on fx.fact_ohlc.

These are parameterized SQL strings designed to be executed via
AnalyticalReader.read_sql(). They leverage the NCCI and analytical
views for maximum read performance.

Parameters use SQLAlchemy :named_param syntax.
"""

# ------------------------------------------------------------------
# Daily OHLC bars for a symbol over a date range
# Uses the vw_ohlc_daily view (aggregates ticks to daily bars)
# ------------------------------------------------------------------
OHLC_BY_SYMBOL = """
SELECT
    symbol, series, trade_date,
    open_px, high_px, low_px, close_px,
    avg_mid_px, total_ticks
FROM [fx].[vw_ohlc_daily]
WHERE [symbol] = :symbol
  AND [trade_date] BETWEEN :start_date AND :end_date
ORDER BY [trade_date]
"""

# ------------------------------------------------------------------
# Day-over-day % change for a symbol
# Uses vw_daily_change (LAG-based, accelerated by NCCI)
# ------------------------------------------------------------------
DAILY_CHANGE = """
SELECT
    symbol, series, trade_date,
    close_px, prev_close_px, pct_change_close
FROM [fx].[vw_daily_change]
WHERE [symbol] = :symbol
  AND [trade_date] BETWEEN :start_date AND :end_date
ORDER BY [trade_date]
"""

# ------------------------------------------------------------------
# Moving averages + z-score for a symbol
# Uses vw_ohlc_moving_avg (window functions, NCCI-accelerated)
# ------------------------------------------------------------------
MOVING_AVERAGES = """
SELECT
    symbol, series, trade_date,
    close_px, ma_5d, ma_20d, ma_50d, z_score_20d
FROM [fx].[vw_ohlc_moving_avg]
WHERE [symbol] = :symbol
  AND [trade_date] BETWEEN :start_date AND :end_date
ORDER BY [trade_date]
"""

# ------------------------------------------------------------------
# Cross-symbol comparison — two symbols side by side
# Joins the daily view on trade_date for aligned comparison
# ------------------------------------------------------------------
CROSS_SYMBOL_COMPARE = """
SELECT
    a.trade_date,
    a.symbol AS symbol_a,
    a.close_px AS close_a,
    b.symbol AS symbol_b,
    b.close_px AS close_b,
    CASE WHEN b.close_px <> 0
         THEN a.close_px / b.close_px
         ELSE NULL
    END AS ratio_a_over_b
FROM [fx].[vw_ohlc_daily] a
JOIN [fx].[vw_ohlc_daily] b
    ON a.trade_date = b.trade_date
WHERE a.symbol = :symbol_a
  AND b.symbol = :symbol_b
  AND a.series = b.series
  AND a.trade_date BETWEEN :start_date AND :end_date
ORDER BY a.trade_date
"""

# ------------------------------------------------------------------
# Aggregated stats for a symbol over a date range
# Runs directly on fact_ohlc — NCCI handles the scan
# ------------------------------------------------------------------
OHLC_RANGE_STATS = """
SELECT
    symbol,
    series,
    COUNT(*)                AS total_rows,
    MIN(CAST(ts AS DATE))   AS first_date,
    MAX(CAST(ts AS DATE))   AS last_date,
    AVG(close_px)           AS avg_close,
    MIN(low_px)             AS period_low,
    MAX(high_px)            AS period_high,
    STDEV(close_px)         AS close_stdev,
    SUM(n_ticks)            AS total_ticks
FROM [fx].[fact_ohlc]
WHERE [symbol] = :symbol
  AND [ts] BETWEEN :start_date AND :end_date
GROUP BY symbol, series
"""

# ------------------------------------------------------------------
# Symbol inventory — what data exists and date ranges
# Uses the indexed (materialized) vw_ohlc_summary for instant lookups
# ------------------------------------------------------------------
SYMBOL_INVENTORY = """
SELECT
    symbol,
    series,
    total_rows,
    total_ticks,
    first_ts,
    last_ts
FROM [fx].[vw_ohlc_summary]
ORDER BY symbol, series
"""

# ------------------------------------------------------------------
# Latest data per symbol (most recent trade_date)
# Useful for dashboards showing "current" state
# ------------------------------------------------------------------
LATEST_BY_SYMBOL = """
WITH ranked AS (
    SELECT
        symbol, series,
        CAST(ts AS DATE) AS trade_date,
        close_px, mid_px, bid, ask, n_ticks,
        ROW_NUMBER() OVER (
            PARTITION BY symbol, series
            ORDER BY ts DESC
        ) AS rn
    FROM [fx].[fact_ohlc]
)
SELECT symbol, series, trade_date, close_px, mid_px, bid, ask, n_ticks
FROM ranked
WHERE rn = 1
ORDER BY symbol, series
"""
