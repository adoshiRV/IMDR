"""FX vol tag parser + Citi response → DataFrame converter.

Only domain-specific code is citi_vol_tag_to_internal() — everything else
delegates to shared helpers in connectors.citi_helpers.
"""
from __future__ import annotations

import pandas as pd

from imdr.connectors.citi_helpers import citi_response_to_rows

COLUMNS = ["ts", "base_ccy", "quote_ccy", "strike", "tenor", "vol_type", "value"]


def citi_vol_tag_to_internal(tag: str) -> dict | None:
    """Parse FX.VOL.EUR.USD.ATM.1M.IMPLIED.CITI → dict of column values.

    This is the ONLY domain-specific function needed.
    """
    parts = tag.split(".")
    if len(parts) != 8 or parts[0] != "FX" or parts[1] != "VOL":
        return None
    return {
        "base_ccy": parts[2],
        "quote_ccy": parts[3],
        "strike": parts[4],
        "tenor": parts[5],
        "vol_type": parts[6],
    }


def citi_vol_response_to_df(resp: dict) -> pd.DataFrame:
    """Convert Citi Historical response → DataFrame. Delegates to shared parser."""
    rows = citi_response_to_rows(resp, tag_parser=citi_vol_tag_to_internal)
    df = pd.DataFrame(rows, columns=COLUMNS) if rows else pd.DataFrame(columns=COLUMNS)
    if not df.empty:
        df = df.sort_values(
            ["base_ccy", "quote_ccy", "strike", "tenor", "ts"]
        ).reset_index(drop=True)
    return df
