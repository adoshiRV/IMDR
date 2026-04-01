"""Commodity implied vol tag parser + Citi response → DataFrame converter.

Two tag formats:
  Precious metals: COMMODITIES.IMPLIED_VOL.XAU.USD.ATM.1M
  Oil:             COMMODITIES.IMPLIED_VOL.CR_NYM_CL.ATM.NEARBY01_M
"""
from __future__ import annotations

import pandas as pd

from imdr.connectors.citi_helpers import citi_response_to_rows, parse_x_to_ts_utc

COLUMNS = ["ts", "product", "strike", "tenor", "value"]

# Oil products use a different tag structure (no .USD. segment)
_OIL_PRODUCTS = frozenset({"CR_IPE_BRENT", "CR_NYM_CL"})


def citi_cmdty_vol_tag_to_internal(tag: str) -> dict | None:
    """Parse commodity vol tag → dict of column values.

    Precious metals (6 parts):
        COMMODITIES.IMPLIED_VOL.XAU.USD.ATM.1M
        → {"product": "XAU", "strike": "ATM", "tenor": "1M"}

    Oil (5 parts):
        COMMODITIES.IMPLIED_VOL.CR_NYM_CL.ATM.NEARBY01_M
        → {"product": "CR_NYM_CL", "strike": "ATM", "tenor": "NEARBY01_M"}
    """
    parts = tag.split(".")
    if len(parts) < 5 or parts[0] != "COMMODITIES" or parts[1] != "IMPLIED_VOL":
        return None

    # Detect oil products by checking if segment after IMPLIED_VOL
    # matches a known oil product (which contain underscores).
    # Oil products: CR_NYM_CL (joins parts[2:4] → "CR_NYM_CL"), CR_IPE_BRENT (parts[2:4] → "CR_IPE_BRENT")
    # We need to handle the fact that underscores in product names get split by ".":
    # COMMODITIES.IMPLIED_VOL.CR_NYM_CL.ATM.NEARBY01_M is actually 5 parts
    # because CR_NYM_CL doesn't contain dots.
    #
    # Precious: COMMODITIES.IMPLIED_VOL.XAU.USD.ATM.1M = 6 parts
    # Oil:      COMMODITIES.IMPLIED_VOL.CR_NYM_CL.ATM.NEARBY01_M = 5 parts

    if len(parts) == 6 and parts[3] == "USD":
        # Precious metals format: COMMODITIES.IMPLIED_VOL.{product}.USD.{strike}.{tenor}
        return {"product": parts[2], "strike": parts[4], "tenor": parts[5]}

    if len(parts) == 5 and parts[2] in _OIL_PRODUCTS:
        # Oil format: COMMODITIES.IMPLIED_VOL.{product}.{strike}.{tenor}
        return {"product": parts[2], "strike": parts[3], "tenor": parts[4]}

    return None


def citi_cmdty_vol_response_to_df(resp: dict) -> pd.DataFrame:
    """Convert Citi Historical response → DataFrame. Delegates to shared parser."""
    rows = citi_response_to_rows(resp, tag_parser=citi_cmdty_vol_tag_to_internal)
    df = pd.DataFrame(rows, columns=COLUMNS) if rows else pd.DataFrame(columns=COLUMNS)
    if not df.empty:
        df = df.sort_values(["product", "strike", "tenor", "ts"]).reset_index(drop=True)
    return df
