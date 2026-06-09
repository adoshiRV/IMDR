"""Shared parser for the BBG 3-header CSV layout.

Both FX (``FX/{ccy}/FX_{ccy}.csv``) and rates
(``{IRS|OIS|BASIS|CCS}/{folder}/PAR/{kind}_PAR_{folder}.csv``) trees
in ``Z:\\BBG_mirror\\`` share the same 4-row preamble:

    Row 0: Ticker, <ticker_1>, <ticker_2>, ...
    Row 1: <label_or_tenor_header>, <tenor_alias_1>, <tenor_alias_2>, ...
    Row 2: Maturity, <yrs_1>, <yrs_2>, ...
    Row 3+: dd/mm/yyyy, <value_1>, <value_2>, ...

Only row 1 (tenor aliases) and rows 3+ (data) carry information IMDR
consumes. Row 0 + row 2 are ignored.

This module is read-only with respect to the source tree: it ``glob``s
+ ``pd.read_csv``s, never moves/renames/deletes/writes. See lock-in
test ``tests/unit/test_vendors/test_bbg_no_move.py``.

Lives at ``imdr.bbg`` (top-level subpackage) rather than under
``imdr.vendors`` to avoid a circular import via the vendor-registry
side-effect import in ``imdr.vendors.__init__``.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd


def parse_3hdr_csv(
    path: Path,
    *,
    validate_headers: bool = False,
    expected_row0_col0: str = "Ticker",
    expected_row1_col0: str | None = None,
) -> pd.DataFrame:
    """Parse one BBG 3-row-header CSV into a long-form DataFrame.

    Returns columns ``[obs_date, tenor_alias, value]`` with ``obs_date``
    as ``datetime.date`` and ``value`` coerced to float. Tenor
    canonicalization is the caller's job — this function preserves the
    raw row-1 alias so domain-specific mapping can decide what to do.

    Parameters
    ----------
    path
        Absolute path to the CSV (under ``Z:\\BBG_mirror\\``).
    validate_headers
        If True, assert ``raw.iloc[0, 0] == expected_row0_col0`` and
        ``raw.iloc[1, 0] == expected_row1_col0`` (when provided).
        FX files satisfy both ("Ticker" + "Tenor"); rates files vary
        wildly on row 1 col 0 so the rates caller passes False.
    expected_row0_col0
        Expected value at ``raw.iloc[0, 0]``. Default ``"Ticker"`` —
        every BBG output we've seen has this.
    expected_row1_col0
        Expected value at ``raw.iloc[1, 0]``. Only checked when
        ``validate_headers=True`` and this is non-None.

    Raises
    ------
    ValueError
        If the file has fewer than 4 rows, or if header validation is
        requested and the row 0 / row 1 first-cell labels don't match.
    """
    raw = pd.read_csv(path, header=None, dtype=str, encoding="latin-1")
    if raw.shape[0] < 4:
        raise ValueError(
            f"{path}: fewer than 4 rows; can't parse 3-header layout"
        )

    if validate_headers:
        if raw.iloc[0, 0] != expected_row0_col0:
            raise ValueError(
                f"{path}: row 0 col 0 is {raw.iloc[0, 0]!r}, "
                f"expected {expected_row0_col0!r}"
            )
        if expected_row1_col0 is not None and raw.iloc[1, 0] != expected_row1_col0:
            raise ValueError(
                f"{path}: row 1 col 0 is {raw.iloc[1, 0]!r}, "
                f"expected {expected_row1_col0!r}"
            )

    # Row 1 holds tenor aliases. Strip whitespace — some BBG ticker
    # headers have multiple spaces (e.g. EUR-ESTR-ON's ``"EESWE1Z  BGN
    # Curncy"``). Safe for FX too (FX_EUR_1W has no whitespace).
    tenor_aliases = [str(c).strip() for c in raw.iloc[1, 1:].tolist()]
    data = raw.iloc[3:, :].copy()
    data.columns = ["date_str"] + tenor_aliases

    # Parse dates as UK format (dd/mm/yyyy) — universal across FX + rates.
    data["obs_date"] = pd.to_datetime(
        data["date_str"], format="%d/%m/%Y", errors="coerce"
    ).dt.date
    data = data.drop(columns=["date_str"]).dropna(subset=["obs_date"])

    long_df = data.melt(
        id_vars=["obs_date"],
        var_name="tenor_alias",
        value_name="value_str",
    )
    long_df["value"] = pd.to_numeric(long_df["value_str"], errors="coerce")
    long_df = long_df.dropna(subset=["value"]).drop(columns=["value_str"])

    return long_df
