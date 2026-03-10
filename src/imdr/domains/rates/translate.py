"""
Citi Velocity tag ↔ internal schema translation.

Translates between Citi tag format (RATES.OIS.USD_SOFR.PAR.5Y) and
internal schema columns (ccy=USD, curve=SOFR, quote=par, tenor=5Y).

Provider-specific: all Citi logic lives here. Adding a second provider
means adding a parallel set of functions, not modifying these.

Ported from RATES_data/src/translate.py — catalog lookups now use RatesUniverse.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from imdr.domains.rates.schema import CITI_TO_QUOTE, COLUMNS, QUOTE_TO_CITI
from imdr.universe.rates import RatesUniverse, get_rates_universe


# ── Tag → Internal ───────────────────────────────────────────────

def citi_tag_to_internal(
    tag: str,
    universe: RatesUniverse | None = None,
) -> dict[str, str] | None:
    """
    Parse a Citi tag into internal schema fields.

    Returns dict with {ccy, curve, quote, tenor} or None if tag
    doesn't match any catalog entry.

    Tag formats:
      OIS:        RATES.OIS.{CCY}_{INDEX}.{QUOTE_TYPE}.{MATURITY}     (5+ parts)
      SWAP_LIBOR: RATES.SWAP_LIBOR.{CCY}.{QUOTE_TYPE}.{MATURITY}      (5+ parts)
      Multi-tenor: ... .{QT}.{MAT1}.{MAT2} (6 parts) or .{MAT1}.{MAT2}.{MAT3} (7 parts)
    """
    if universe is None:
        universe = get_rates_universe()

    parts = tag.split(".")

    if len(parts) < 5 or parts[0] != "RATES":
        return None

    instrument = parts[1]  # OIS or SWAP_LIBOR

    if instrument == "OIS":
        pair = parts[2]  # e.g. "USD_SOFR"
        citi_qt = parts[3]
        tenor_parts = parts[4:]
    elif instrument == "SWAP_LIBOR":
        pair = parts[2]  # e.g. "USD" or "CNY_NDIRS"
        citi_qt = parts[3]
        tenor_parts = parts[4:]
    else:
        return None

    # Resolve ccy/curve via universe prefix matching
    prefix = f"RATES.{instrument}.{pair}"
    resolved = universe.resolve_prefix(prefix)
    if resolved is None:
        return None
    ccy, curve = resolved

    # Quote type
    quote = CITI_TO_QUOTE.get(citi_qt)
    if quote is None:
        return None

    # Tenor: single part for par/ssw/rc, multi for spread/fwd/bfly
    tenor = ".".join(tenor_parts) if len(tenor_parts) > 1 else tenor_parts[0]

    return {"ccy": ccy, "curve": curve, "quote": quote, "tenor": tenor}


# ── Internal → Tag ───────────────────────────────────────────────

def internal_to_citi_tags(
    ccy: str,
    curve: str,
    quote: str = "par",
    tenors: list[str] | None = None,
    universe: RatesUniverse | None = None,
) -> list[str]:
    """
    Build Citi tags from internal schema fields.

    Parameters
    ----------
    ccy : str      Currency code
    curve : str    Curve name
    quote : str    Internal quote code (par, spread, fwd, etc.)
    tenors : list  Optional tenor list. If None, uses all maturities for the curve.

    Returns
    -------
    List of Citi tag strings
    """
    if universe is None:
        universe = get_rates_universe()

    citi_qt = QUOTE_TO_CITI[quote.lower()]
    return universe.build_tags(ccy, curve, citi_qt, tenors)


# ── Response → DataFrame ────────────────────────────────────────

def citi_response_to_df(
    resp: dict[str, Any],
    parse_x: callable,
    universe: RatesUniverse | None = None,
) -> pd.DataFrame:
    """
    Convert Citi Historical API response to internal schema DataFrame.

    Parameters
    ----------
    resp : dict
        Raw API response with body[tag]{x, c, type}
    parse_x : callable
        Function to parse x-axis values to datetime (e.g. parse_x_to_ts_utc)

    Returns
    -------
    pd.DataFrame with columns [ts, ccy, curve, quote, tenor, value]
    """
    if universe is None:
        universe = get_rates_universe()

    if resp.get("status") != "OK":
        raise RuntimeError(f"API status not OK: {resp}")

    body = resp.get("body", {})
    rows: list[tuple] = []

    for tag, series in body.items():
        if not isinstance(series, dict):
            continue
        if series.get("type") == "ERROR":
            continue

        parsed = citi_tag_to_internal(tag, universe)
        if parsed is None:
            continue

        xs = series.get("x") or []
        cs = series.get("c") or []

        for x, c in zip(xs, cs):
            if c is None:
                continue
            ts = parse_x(x)
            rows.append((
                ts,
                parsed["ccy"],
                parsed["curve"],
                parsed["quote"],
                parsed["tenor"],
                float(c),
            ))

    df = pd.DataFrame(rows, columns=COLUMNS)
    if not df.empty:
        df = df.sort_values(["ccy", "curve", "quote", "tenor", "ts"]).reset_index(drop=True)
    return df
