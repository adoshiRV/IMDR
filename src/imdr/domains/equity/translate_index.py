"""Index level tag parser + Citi response → DataFrame converter.

Tags: EQUITY.EQUITY_INDEX..{TICKER}.LEVEL.REUTERS
(double-dot is intentional — empty issuer segment)
"""
from __future__ import annotations

import pandas as pd

from imdr.connectors.citi_helpers import citi_response_to_rows

COLUMNS = ["ts", "ticker", "value"]


def citi_index_tag_to_internal(tag: str) -> dict | None:
    """Parse EQUITY.EQUITY_INDEX..SPX.LEVEL.REUTERS → {'ticker': 'SPX'}.

    Returns None if tag doesn't match the expected format.
    """
    parts = tag.split(".")
    # Expected: ['EQUITY', 'EQUITY_INDEX', '', '{TICKER}', 'LEVEL', 'REUTERS']
    if len(parts) != 6:
        return None
    if parts[0] != "EQUITY" or parts[1] != "EQUITY_INDEX":
        return None
    if parts[4] != "LEVEL" or parts[5] != "REUTERS":
        return None
    ticker = parts[3]
    if not ticker:
        return None
    return {"ticker": ticker}


def citi_index_response_to_df(resp: dict) -> pd.DataFrame:
    """Convert Citi Historical response → DataFrame with COLUMNS."""
    rows = citi_response_to_rows(resp, tag_parser=citi_index_tag_to_internal)
    df = pd.DataFrame(rows, columns=COLUMNS) if rows else pd.DataFrame(columns=COLUMNS)
    if not df.empty:
        df = df.sort_values(["ticker", "ts"]).reset_index(drop=True)
    return df
