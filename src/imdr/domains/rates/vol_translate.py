"""Rates swaption vol tag parser + Citi response -> DataFrame converter.

Only domain-specific code is citi_rates_vol_tag_to_internal() — everything
else delegates to shared helpers in connectors.citi_helpers.

Tag formats (all start with RATES.VOL.{CCY}):
  ATM/ATM_RFR  (depth 7): ...{DATA_TYPE}.{QUOTE_TYPE}.{EXPIRY}.{SWAP_TENOR}
      where QUOTE_TYPE is BLACK, FWDPREMIUM, or PREMIUM
  ATM/ATM_RFR  (depth 8): ...{DATA_TYPE}.NORMAL.{FREQ}.{EXPIRY}.{SWAP_TENOR}
      where FREQ is ANNUAL or DAILY (normal vol has an extra freq segment)
  REALIZED/REALIZED_RFR (depth 8): ...{DATA_TYPE}.{WINDOW}.{FREQ}.{EXPIRY}.{SWAP_TENOR}
  VOL_RATIO/VOL_RATIO_RFR (depth 7): ...{DATA_TYPE}.{WINDOW}.{EXPIRY}.{SWAP_TENOR}
"""
from __future__ import annotations

import pandas as pd

from imdr.connectors.citi_helpers import citi_response_to_rows

COLUMNS = [
    "ts", "ccy", "data_type", "quote_type", "vol_window", "freq",
    "option_expiry", "swap_tenor", "value",
]

# Data types where parts[4] is a quote_type (BLACK, FWDPREMIUM, PREMIUM at depth 7;
# NORMAL at depth 8 with an extra FREQ segment)
_ATM_TYPES = frozenset({"ATM", "ATM_RFR"})
# Quote types that use the depth-7 format (no freq)
_ATM_DEPTH7_QTYPES = frozenset({"BLACK", "FWDPREMIUM", "PREMIUM"})
# Quote types that use the depth-8 format ({QUOTE_TYPE}.{FREQ}.{EXPIRY}.{SWAP_TENOR})
_ATM_DEPTH8_QTYPES = frozenset({"NORMAL"})
# Data types where parts[4] is a vol_window and parts[5] is a freq
_REALIZED_TYPES = frozenset({"REALIZED", "REALIZED_RFR"})
# Data types where parts[4] is a vol_window (no freq)
_VOL_RATIO_TYPES = frozenset({"VOL_RATIO", "VOL_RATIO_RFR"})


def citi_rates_vol_tag_to_internal(tag: str) -> dict | None:
    """Parse a RATES.VOL tag into column values.

    Returns None for unparseable tags (logged upstream by citi_response_to_rows).
    """
    parts = tag.split(".")
    if len(parts) < 7 or parts[0] != "RATES" or parts[1] != "VOL":
        return None

    ccy = parts[2]
    data_type = parts[3]

    if data_type in _ATM_TYPES and len(parts) == 7 and parts[4] in _ATM_DEPTH7_QTYPES:
        return {
            "ccy": ccy,
            "data_type": data_type,
            "quote_type": parts[4],
            "vol_window": "",
            "freq": "",
            "option_expiry": parts[5],
            "swap_tenor": parts[6],
        }

    if data_type in _ATM_TYPES and len(parts) == 8 and parts[4] in _ATM_DEPTH8_QTYPES:
        # NORMAL: RATES.VOL.{CCY}.{ATM|ATM_RFR}.NORMAL.{FREQ}.{EXPIRY}.{SWAP_TENOR}
        return {
            "ccy": ccy,
            "data_type": data_type,
            "quote_type": parts[4],       # NORMAL
            "vol_window": "",
            "freq": parts[5],             # ANNUAL or DAILY
            "option_expiry": parts[6],
            "swap_tenor": parts[7],
        }

    if data_type in _REALIZED_TYPES and len(parts) == 8:
        return {
            "ccy": ccy,
            "data_type": data_type,
            "quote_type": "",
            "vol_window": parts[4],
            "freq": parts[5],
            "option_expiry": parts[6],
            "swap_tenor": parts[7],
        }

    if data_type in _VOL_RATIO_TYPES and len(parts) == 7:
        return {
            "ccy": ccy,
            "data_type": data_type,
            "quote_type": "",
            "vol_window": parts[4],
            "freq": "",
            "option_expiry": parts[5],
            "swap_tenor": parts[6],
        }

    return None


def citi_rates_vol_response_to_df(resp: dict) -> pd.DataFrame:
    """Convert Citi Historical response -> DataFrame. Delegates to shared parser."""
    rows = citi_response_to_rows(resp, tag_parser=citi_rates_vol_tag_to_internal)
    df = pd.DataFrame(rows, columns=COLUMNS) if rows else pd.DataFrame(columns=COLUMNS)
    if not df.empty:
        df = df.sort_values(
            ["ccy", "data_type", "option_expiry", "swap_tenor", "ts"]
        ).reset_index(drop=True)
    return df
