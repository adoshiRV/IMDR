"""Canned SQL queries for FX analytics on fx.fact_ohlc.

These are parameterized SQL strings designed to be executed via
AnalyticalReader.read_sql().

Parameters use SQLAlchemy :named_param syntax.
"""

# ------------------------------------------------------------------
# Aggregated stats for a symbol over a date range
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
