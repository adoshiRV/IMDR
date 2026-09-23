"""PRICE FORECAST tag parser + Citi response -> fact rows.

Tags: COMMODITIES.FORECAST.{SECTOR}.{PRODUCT}.{HORIZON}.PRICE_FCST.CITI

The whole point of this module is that ONE tag family carries TWO shapes, and
the `x` axis means a different thing in each (probed 2026-09-23):

    RELATIVE  (POINT_PRICES.0_3M / .6_12M)
        x = the vendor's PUBLICATION date. The value is "what Citi thinks the
        price will be 0-3M / 6-12M from that date". Published every business
        day, but it is a STEP FUNCTION -- ~579 points over 2.2y carrying only
        6-9 distinct values. So we keep only the CHANGES (see `compress_steps`)
        and read it as "this value holds until the next as_of row".

    ABSOLUTE  (QTR / ANNUAL)
        x = the forecast TARGET period end (quarter/year end). The value is
        Citi's number FOR that period. The vendor serves only the CURRENT
        vintage -- re-querying with a historical `end` returns today's curve
        truncated, not the vintage as of then -- so `as_of_date` has to be OUR
        snapshot date and the as-of history only accrues going forward.

A consequence worth knowing when reading the table back: for ABSOLUTE rows,
`target_date <= as_of_date` means the period is already in the past, and Citi
carries the REALISED number there rather than a forecast. Same column, two
meanings; derive the distinction at read time rather than storing a flag.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import date

import pandas as pd

from imdr.connectors.citi_helpers import citi_response_to_rows

COLUMNS = ["ts", "tag", "symbol", "quote_unit", "horizon_code", "horizon_type", "value"]

_RELATIVE = "RELATIVE"
_ABSOLUTE = "ABSOLUTE"


def make_forecast_tag_parser(
    spec_by_tag: dict[str, dict],
) -> Callable[[str], dict | None]:
    """Build the tag_parser `citi_response_to_rows` needs.

    Resolution is a dict lookup against the universe rather than string
    surgery on the tag: the universe already knows the product -> commodity
    symbol, quote unit and horizon mapping, and an unknown tag must resolve to
    None so the shared parser drops it instead of inventing a commodity.
    """

    def parse(tag: str) -> dict | None:
        spec = spec_by_tag.get(tag)
        if spec is None:
            return None
        return {
            "tag": tag,
            "symbol": spec["symbol"],
            "quote_unit": spec["quote_unit"],
            "horizon_code": spec["horizon_code"],
            "horizon_type": spec["horizon_type"],
        }

    return parse


def citi_forecast_response_to_df(
    resp: dict, spec_by_tag: dict[str, dict]
) -> pd.DataFrame:
    """Convert a Citi Historical response -> tidy DataFrame.

    Delegates the envelope handling (status check, quota errors, per-tag
    `type: "ERROR"` series, x/c zipping) to the shared helper.
    """
    rows = citi_response_to_rows(resp, tag_parser=make_forecast_tag_parser(spec_by_tag))
    df = pd.DataFrame(rows, columns=COLUMNS) if rows else pd.DataFrame(columns=COLUMNS)
    if not df.empty:
        df = df.sort_values(["tag", "ts"]).reset_index(drop=True)
    return df


def compress_steps(df: pd.DataFrame) -> pd.DataFrame:
    """Drop consecutive repeats within each RELATIVE tag.

    The vendor republishes an unchanged forecast every business day; only the
    revisions carry information. Keeping the first point and every subsequent
    change turns ~579 rows per tag into ~10-20 without losing anything: the
    stored value holds until the next as_of row.

    ABSOLUTE rows pass through untouched -- each snapshot is a whole curve and
    is keyed by target_date, so there is no "previous value" to compare against
    inside a single response.
    """
    if df.empty:
        return df

    out: list[pd.DataFrame] = []
    for tag, group in df.groupby("tag", sort=False):
        group = group.sort_values("ts")
        if group["horizon_type"].iloc[0] != _RELATIVE:
            out.append(group)
            continue
        keep = group["value"].ne(group["value"].shift())
        out.append(group[keep])
    return pd.concat(out, ignore_index=True) if out else df


def to_forecast_rows(df: pd.DataFrame, snapshot_date: date) -> list[dict]:
    """Map the tidy frame onto commodities.fact_price_forecast rows.

    `snapshot_date` is only used for ABSOLUTE rows, where the vendor gives no
    as-of of its own. RELATIVE rows carry the vendor's own publication date and
    must NOT be stamped with the run date -- doing so would collapse 2.2 years
    of revision history onto today.
    """
    if df.empty:
        return []

    rows: list[dict] = []
    for r in df.itertuples(index=False):
        x_date = r.ts.date() if hasattr(r.ts, "date") else r.ts
        if r.horizon_type == _RELATIVE:
            as_of, target = x_date, None
        else:
            as_of, target = snapshot_date, x_date
        rows.append({
            "symbol": r.symbol,
            "horizon_type": r.horizon_type,
            "horizon_code": r.horizon_code,
            "target_date": target,
            "as_of_date": as_of,
            "forecast_value": float(r.value),
            "quote_unit": r.quote_unit,
        })
    return rows
