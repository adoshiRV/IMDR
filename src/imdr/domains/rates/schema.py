"""
Internal market data schema — constants, quote type mappings, tenor encoding/decoding.

Schema: [ts, ccy, curve, quote, tenor, value]
  - ts:    datetime64[ns, UTC]
  - ccy:   ISO uppercase (USD, EUR, JPY)
  - curve: market convention uppercase (SOFR, SONIA, EURIBOR)
  - quote: internal short code (par, fwd, bfly, spread, ssw, rc)
  - tenor: market convention encoding (5Y, 2ys10ys, 5ys5ys, 2ys5ys10ys)
  - value: float64

Direct port from RATES_data/src/schema.py — pure logic, no I/O.
"""
from __future__ import annotations

import re
from typing import Optional

# ── Schema columns ───────────────────────────────────────────────

COLUMNS = ["ts", "ccy", "curve", "quote", "tenor", "value"]


# ── Quote type mapping: internal ↔ Citi ──────────────────────────

QUOTE_TO_CITI = {
    "par":    "PAR",
    "ssw":    "SWAP_SPREAD",
    "rc":     "ROLL_CARRY",
    "spread": "CURVES",
    "fwd":    "FWD",
    "bfly":   "BFLY",
    # basis = single-scalar spread in bps. Same column for BBG cross-currency
    # basis ([extractors_bbg.py](../extractors_bbg.py)) and Citi tenor-basis
    # (RATES.BASIS_SWAPS.*); curve_id discriminates which kind.
    "basis":  "BASIS_SPREAD",
}

CITI_TO_QUOTE = {v: k for k, v in QUOTE_TO_CITI.items()}

# Quote types that use single tenors (e.g. 5Y)
SINGLE_TENOR_QUOTES = {"par", "ssw", "rc", "basis"}

# Quote types that use multi-tenor encoding
MULTI_TENOR_QUOTES = {"spread", "fwd", "bfly"}

# Expected leg counts per multi-tenor quote type
MULTI_TENOR_LEGS = {
    "spread": 2,
    "fwd":    2,
    "bfly":   3,
}


# ── Tenor encoding / decoding ────────────────────────────────────

_TENOR_RE = re.compile(r"^(\d+)([YMWD])$", re.IGNORECASE)


def encode_tenor(legs: list[str], quote: str) -> str:
    """
    Encode tenor legs into storage format.

    Examples
    --------
    >>> encode_tenor(["5Y"], "par")
    '5Y'
    >>> encode_tenor(["2Y", "10Y"], "spread")
    '2ys10ys'
    >>> encode_tenor(["5Y", "5Y"], "fwd")
    '5ys5ys'
    >>> encode_tenor(["2Y", "5Y", "10Y"], "bfly")
    '2ys5ys10ys'
    """
    if quote in SINGLE_TENOR_QUOTES:
        if len(legs) != 1:
            raise ValueError(f"Single-tenor quote '{quote}' expects 1 leg, got {len(legs)}: {legs}")
        return legs[0].upper()

    if quote not in MULTI_TENOR_LEGS:
        raise ValueError(f"Unknown quote type: {quote}")

    expected = MULTI_TENOR_LEGS[quote]
    if len(legs) != expected:
        raise ValueError(f"Quote '{quote}' expects {expected} legs, got {len(legs)}: {legs}")

    for leg in legs:
        if not _TENOR_RE.match(leg):
            raise ValueError(f"Invalid tenor leg: {leg!r} (expected e.g. '5Y', '3M')")

    return "s".join(leg.lower() for leg in legs) + "s"


def decode_tenor(tenor: str, quote: str) -> list[str]:
    """
    Decode storage tenor string back to individual legs.

    Examples
    --------
    >>> decode_tenor("5Y", "par")
    ['5Y']
    >>> decode_tenor("2ys10ys", "spread")
    ['2Y', '10Y']
    """
    if quote in SINGLE_TENOR_QUOTES:
        return [tenor.upper()]

    parts = [p for p in tenor.split("s") if p]
    return [p.upper() for p in parts]


def display_tenor(tenor: str, quote: Optional[str] = None) -> str:
    """
    Convert storage encoding to trader-friendly display format.

    Storage: "2ys10ys" → Display: "2s10s"
    Storage: "5ys5ys"  → Display: "5y5y"
    Storage: "5Y"      → Display: "5Y" (unchanged)
    """
    if _TENOR_RE.match(tenor):
        return tenor.upper()

    if quote is None:
        parts = [p for p in tenor.split("s") if p]
        if len(parts) == 3:
            quote = "bfly"
        elif len(parts) == 2:
            quote = "fwd"
        else:
            return tenor

    legs = decode_tenor(tenor, quote)

    if quote == "fwd":
        return "".join(leg.lower() for leg in legs)
    else:
        display_parts = []
        for leg in legs:
            m = _TENOR_RE.match(leg)
            if m:
                num, unit = m.groups()
                if unit.upper() == "Y":
                    display_parts.append(num)
                else:
                    display_parts.append(num + unit.lower())
            else:
                display_parts.append(leg.lower())
        return "s".join(display_parts) + "s"


def validate_quote(quote: str) -> str:
    """Validate and return normalized quote code."""
    q = quote.lower()
    if q not in QUOTE_TO_CITI:
        raise ValueError(f"Unknown quote type: {quote!r}. Valid: {list(QUOTE_TO_CITI.keys())}")
    return q


def quote_to_citi(quote: str) -> str:
    """Convert internal quote code to Citi tag code."""
    return QUOTE_TO_CITI[validate_quote(quote)]


def citi_to_quote(citi_code: str) -> str:
    """Convert Citi tag code to internal quote code."""
    code = citi_code.upper()
    if code not in CITI_TO_QUOTE:
        raise ValueError(f"Unknown Citi quote code: {citi_code!r}. Valid: {list(CITI_TO_QUOTE.keys())}")
    return CITI_TO_QUOTE[code]
