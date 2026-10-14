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

# ── Roll-carry: one REQUEST family, three STORAGE quotes ─────────
#
# The Citi tag is ROLL_CARRY.{HORIZON}.{FWD_START}.{TENOR}.{MEASURE} — four
# segments, with a trailing measure that has nowhere to live in the
# [ts, ccy, curve, quote, tenor, value] schema.
#
# 'rc' stays the single REQUEST key (so one build_tags call emits all three
# measures and we don't pay 3x the tag quota for the same combos), and the
# parser fans the response out into three STORAGE quotes — so a measure
# filters like any other quote (WHERE quote='rc_carry') with no DDL.
#
# Until 2026-10-14 'rc' was classed single-tenor, so build_tags emitted
# {prefix}.ROLL_CARRY.{tenor} — a 2-segment tail that can never resolve
# against a 4-segment tag. 'rc' therefore produced ZERO rows on all 59
# curves since inception despite sitting in pipelines.yml default_quotes.
RC_MEASURE_TO_QUOTE = {
    "CARRY":       "rc_carry",
    "ROLL":        "rc_roll",
    "TOTAL_CARRY": "rc_total",
}
RC_QUOTES = frozenset(RC_MEASURE_TO_QUOTE.values())

# Quote types that use single tenors (e.g. 5Y)
SINGLE_TENOR_QUOTES = {"par", "ssw", "basis"}

# Quote types that use multi-tenor encoding
MULTI_TENOR_QUOTES = {"spread", "fwd", "bfly", "rc"} | RC_QUOTES

# Expected leg counts per multi-tenor quote type
MULTI_TENOR_LEGS = {
    "spread": 2,
    "fwd":    2,
    "bfly":   3,
    # rc legs are (HORIZON, FWD_START, TENOR); the measure is in the quote.
    "rc":       3,
    "rc_carry": 3,
    "rc_roll":  3,
    "rc_total": 3,
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
    """Validate and return normalized quote code.

    Accepts the three rc_* storage codes as well as the request families —
    they are valid to read and filter on, they just aren't requestable
    (``quote_to_citi`` rejects them; request the ``rc`` family instead).
    """
    q = quote.lower()
    if q not in QUOTE_TO_CITI and q not in RC_QUOTES:
        valid = list(QUOTE_TO_CITI.keys()) + sorted(RC_QUOTES)
        raise ValueError(f"Unknown quote type: {quote!r}. Valid: {valid}")
    return q


def quote_to_citi(quote: str) -> str:
    """Convert internal quote code to Citi tag code.

    The rc_* storage codes have no request form of their own — all three
    come back from one ``rc`` request — so asking for a tag by storage code
    is a bug, not something to silently map onto ROLL_CARRY.
    """
    q = validate_quote(quote)
    if q in RC_QUOTES:
        raise ValueError(
            f"{quote!r} is a storage-only quote; request the 'rc' family instead "
            "(one request returns all three measures)."
        )
    return QUOTE_TO_CITI[q]


def citi_to_quote(citi_code: str) -> str:
    """Convert Citi tag code to internal quote code."""
    code = citi_code.upper()
    if code not in CITI_TO_QUOTE:
        raise ValueError(f"Unknown Citi quote code: {citi_code!r}. Valid: {list(CITI_TO_QUOTE.keys())}")
    return CITI_TO_QUOTE[code]
