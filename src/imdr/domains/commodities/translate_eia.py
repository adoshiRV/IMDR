"""EIA tag parser + Citi response → DataFrame converter.

Tag format: COMMODITIES.EIA.{SERIES}.{REGION}
Example: COMMODITIES.EIA.CRUDE_STOCKS.TOTAL_US
"""
from __future__ import annotations

import pandas as pd

from imdr.connectors.citi_helpers import citi_response_to_rows, parse_x_to_ts_utc

COLUMNS = ["ts", "series_name", "region", "value"]


def citi_eia_tag_to_internal(tag: str) -> dict | None:
    """Parse COMMODITIES.EIA.EIA_CRUDE_STOCKS.EIA_TOTAL_US → dict of column values."""
    parts = tag.split(".")
    if len(parts) != 4 or parts[0] != "COMMODITIES" or parts[1] != "EIA":
        return None
    series = parts[2].removeprefix("EIA_")
    region = parts[3].removeprefix("EIA_")
    return {"series_name": series, "region": region}


def citi_eia_response_to_df(resp: dict) -> pd.DataFrame:
    """Convert Citi Historical response → DataFrame. Delegates to shared parser."""
    rows = citi_response_to_rows(resp, tag_parser=citi_eia_tag_to_internal)
    df = pd.DataFrame(rows, columns=COLUMNS) if rows else pd.DataFrame(columns=COLUMNS)
    if not df.empty:
        df = df.sort_values(["series_name", "region", "ts"]).reset_index(drop=True)
    return df
