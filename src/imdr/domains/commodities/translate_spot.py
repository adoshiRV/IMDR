"""SPOT tag parser + Citi response → DataFrame converter.

Tags: COMMODITIES.SPOT.SPOT_GOLD, COMMODITIES.SPOT.SPOT_SILVER, COMMODITIES.SPOT.OIL_PRICE_NYMEX
"""
from __future__ import annotations

import pandas as pd

from imdr.connectors.citi_helpers import citi_response_to_rows, parse_x_to_ts_utc

COLUMNS = ["ts", "spot_tag", "value"]


def citi_spot_tag_to_internal(tag: str) -> dict | None:
    """Parse COMMODITIES.SPOT.SPOT_GOLD → dict of column values."""
    parts = tag.split(".")
    if len(parts) != 3 or parts[0] != "COMMODITIES" or parts[1] != "SPOT":
        return None
    return {"spot_tag": tag}


def citi_spot_response_to_df(resp: dict) -> pd.DataFrame:
    """Convert Citi Historical response → DataFrame. Delegates to shared parser."""
    rows = citi_response_to_rows(resp, tag_parser=citi_spot_tag_to_internal)
    df = pd.DataFrame(rows, columns=COLUMNS) if rows else pd.DataFrame(columns=COLUMNS)
    if not df.empty:
        df = df.sort_values(["spot_tag", "ts"]).reset_index(drop=True)
    return df
