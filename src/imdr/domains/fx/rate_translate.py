"""FX rate tag parsers + Citi response → DataFrame converter.

Handles three tag families under a single parser so the shared
citi_response_to_rows() helper can process all responses uniformly.

Tag patterns:
  FX.SPOT.{C1}.{C2}.CITI                               → quote_kind=mid_rate, tenor=SPOT
  FX.FORWARD.FWD_OUTRIGHT.{C1}.{C2}.{TENOR}.CITI       → quote_kind=mid_rate, tenor=<T>
  FX.FORWARD.FWD_POINT.{C1}.{C2}.{TENOR}.CITI          → quote_kind=fwd_points, tenor=<T>

After parsing to long rows the pipeline pivots to wide form so each
(pair, date, tenor) has both mid_rate and fwd_points columns.
"""
from __future__ import annotations

import pandas as pd

from imdr.connectors.citi_helpers import citi_response_to_rows

LONG_COLUMNS = ["ts", "base_ccy", "quote_ccy", "tenor", "quote_kind", "numeric"]
WIDE_COLUMNS = ["ts", "base_ccy", "quote_ccy", "tenor", "mid_rate", "fwd_points"]


def citi_fx_rate_tag_to_internal(tag: str) -> dict | None:
    """Parse any of the three FX rate tag families into a long-form row dict.

    Returns dict with base_ccy, quote_ccy, tenor, quote_kind — or None if
    the tag doesn't match any of the three patterns.
    """
    parts = tag.split(".")
    if not parts or parts[0] != "FX" or parts[-1] != "CITI":
        return None

    if parts[1] == "SPOT" and len(parts) == 5:
        # FX.SPOT.{C1}.{C2}.CITI
        return {
            "base_ccy": parts[2],
            "quote_ccy": parts[3],
            "tenor": "SPOT",
            "quote_kind": "mid_rate",
        }

    if parts[1] == "FORWARD" and len(parts) == 7:
        sub = parts[2]
        if sub == "FWD_OUTRIGHT":
            quote_kind = "mid_rate"
        elif sub == "FWD_POINT":
            quote_kind = "fwd_points"
        else:
            return None
        return {
            "base_ccy": parts[3],
            "quote_ccy": parts[4],
            "tenor": parts[5],
            "quote_kind": quote_kind,
        }

    return None


def citi_fx_rate_response_to_long_df(resp: dict) -> pd.DataFrame:
    """Convert a Citi Historical response into a long-form DataFrame.

    Columns: ts, base_ccy, quote_ccy, tenor, quote_kind, numeric.
    """
    rows = citi_response_to_rows(resp, tag_parser=citi_fx_rate_tag_to_internal)
    if not rows:
        return pd.DataFrame(columns=LONG_COLUMNS)
    # citi_response_to_rows emits 'value' — rename to 'numeric' to avoid SQL
    # reserved word 'value' downstream (schema_conventions.md §1).
    df = pd.DataFrame(rows)
    df = df.rename(columns={"value": "numeric"})
    return df[LONG_COLUMNS]


def pivot_long_to_wide(long_df: pd.DataFrame) -> pd.DataFrame:
    """Pivot long-form (quote_kind ∈ {mid_rate, fwd_points}) → wide.

    One row per (base_ccy, quote_ccy, tenor, ts). Missing mid_rate/fwd_points
    are NaN (will land as SQL NULL on insert).
    """
    if long_df.empty:
        return pd.DataFrame(columns=WIDE_COLUMNS)
    wide = long_df.pivot_table(
        index=["ts", "base_ccy", "quote_ccy", "tenor"],
        columns="quote_kind",
        values="numeric",
        aggfunc="first",
    ).reset_index()
    wide.columns.name = None
    # Ensure both columns exist even if one is entirely missing (e.g. VND spot-only batch)
    for col in ("mid_rate", "fwd_points"):
        if col not in wide.columns:
            wide[col] = pd.NA
    wide = wide[WIDE_COLUMNS]
    wide = wide.sort_values(["base_ccy", "quote_ccy", "tenor", "ts"]).reset_index(drop=True)
    return wide
