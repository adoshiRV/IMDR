"""Coverage analysis for equity domain tables."""
from __future__ import annotations

from imdr.connectors.reader import AnalyticalReader
from imdr.healthchecks.dashboard import CoverageData


def get_index_coverage(
    reader: AnalyticalReader, table: str, years: list[int]
) -> CoverageData:
    """Per-index date coverage analysis for fact_index_level."""
    year_filter = ", ".join(str(y) for y in years)

    df_cov = reader.query(
        f"SELECT di.ticker, di.display_name, di.region, di.market_code, "
        f"MIN(f.obs_date) AS first_date, MAX(f.obs_date) AS last_date, COUNT(*) AS n "
        f"FROM {table} f "
        f"JOIN [equities].[dim_index] di ON di.id = f.index_id "
        f"WHERE YEAR(f.obs_date) IN ({year_filter}) "
        f"GROUP BY di.ticker, di.display_name, di.region, di.market_code "
        f"ORDER BY di.region, di.ticker"
    )

    df_counts = reader.query(
        f"SELECT YEAR(obs_date) AS yr, COUNT(*) AS n "
        f"FROM {table} "
        f"WHERE YEAR(obs_date) IN ({year_filter}) "
        f"GROUP BY YEAR(obs_date)"
    )

    return CoverageData(
        tables={"per_index": df_cov, "row_counts": df_counts},
        summary={
            "grand_total_rows": int(df_counts["n"].sum()) if not df_counts.empty else 0,
            "indices": len(df_cov),
        },
    )


def get_vix_coverage(
    reader: AnalyticalReader, table: str, years: list[int]
) -> CoverageData:
    """Per-ticker date coverage analysis for fact_vix."""
    year_filter = ", ".join(str(y) for y in years)

    df_cov = reader.query(
        f"SELECT ticker, "
        f"MIN(obs_date) AS first_date, MAX(obs_date) AS last_date, COUNT(*) AS n "
        f"FROM {table} "
        f"WHERE YEAR(obs_date) IN ({year_filter}) "
        f"GROUP BY ticker "
        f"ORDER BY ticker"
    )

    df_counts = reader.query(
        f"SELECT YEAR(obs_date) AS yr, COUNT(*) AS n "
        f"FROM {table} "
        f"WHERE YEAR(obs_date) IN ({year_filter}) "
        f"GROUP BY YEAR(obs_date)"
    )

    return CoverageData(
        tables={"per_ticker": df_cov, "row_counts": df_counts},
        summary={
            "grand_total_rows": int(df_counts["n"].sum()) if not df_counts.empty else 0,
            "tickers": len(df_cov),
        },
    )
