"""Tests for ``vol_translate.py`` — Citi FX vol tag parser.

Pure helpers — no DB, no network, no fixtures needed.
"""
from __future__ import annotations

import pandas as pd

from imdr.domains.fx.vol_translate import (
    COLUMNS,
    citi_vol_response_to_df,
    citi_vol_tag_to_internal,
)


class TestTagToInternal:
    def test_parses_canonical_tag(self) -> None:
        out = citi_vol_tag_to_internal("FX.VOL.EUR.USD.ATM.1M.IMPLIED.CITI")
        assert out == {
            "base_ccy": "EUR",
            "quote_ccy": "USD",
            "strike": "ATM",
            "tenor": "1M",
            "vol_type": "IMPLIED",
        }

    def test_parses_butterfly_tenor(self) -> None:
        out = citi_vol_tag_to_internal("FX.VOL.GBP.JPY.25STR.3M.IMPLIED.CITI")
        assert out is not None
        assert out["strike"] == "25STR"
        assert out["tenor"] == "3M"

    def test_returns_none_on_wrong_prefix(self) -> None:
        assert citi_vol_tag_to_internal("FX.SPOT.EUR.USD.CITI") is None
        assert citi_vol_tag_to_internal("RATES.IRS.USD.ON.SOFR.CITI") is None

    def test_returns_none_on_wrong_segment_count(self) -> None:
        # 7 segments (missing vol_type) — must be rejected
        assert citi_vol_tag_to_internal("FX.VOL.EUR.USD.ATM.1M.CITI") is None
        # 9 segments — must be rejected
        assert citi_vol_tag_to_internal("FX.VOL.EUR.USD.ATM.1M.IMPLIED.EXTRA.CITI") is None

    def test_returns_none_on_empty(self) -> None:
        assert citi_vol_tag_to_internal("") is None


class TestResponseToDF:
    # `x` is Citi's YYYYMMDD integer for daily-frequency series.
    _X_2026_03_10 = 20260310

    def test_empty_response_returns_empty_df_with_columns(self) -> None:
        df = citi_vol_response_to_df({"status": "OK", "body": {}})
        assert df.empty
        assert list(df.columns) == COLUMNS

    def test_response_to_df_sorted(self) -> None:
        resp = {
            "status": "OK",
            "body": {
                "FX.VOL.EUR.USD.ATM.3M.IMPLIED.CITI": {
                    "x": [self._X_2026_03_10], "c": [7.1],
                },
                "FX.VOL.EUR.USD.ATM.1M.IMPLIED.CITI": {
                    "x": [self._X_2026_03_10], "c": [6.8],
                },
            },
        }
        df = citi_vol_response_to_df(resp)
        assert len(df) == 2
        assert list(df.columns) == COLUMNS
        # Sort order is base, quote, strike, tenor, ts → "1M" sorts before "3M"
        # lexicographically (matches the implementation's chosen behavior).
        assert df.iloc[0]["tenor"] == "1M"
        assert df.iloc[1]["tenor"] == "3M"

    def test_unparseable_tags_dropped(self) -> None:
        """Citi may include unrelated tags — those are silently dropped."""
        resp = {
            "status": "OK",
            "body": {
                "FX.VOL.EUR.USD.ATM.1M.IMPLIED.CITI": {
                    "x": [self._X_2026_03_10], "c": [6.8],
                },
                "NOT_A_VOL_TAG": {
                    "x": [self._X_2026_03_10], "c": [99.9],
                },
            },
        }
        df = citi_vol_response_to_df(resp)
        assert len(df) == 1
        assert df.iloc[0]["vol_type"] == "IMPLIED"

    def test_error_type_series_skipped(self) -> None:
        """Per-tag ERROR responses must be dropped, not propagated."""
        resp = {
            "status": "OK",
            "body": {
                "FX.VOL.EUR.USD.ATM.1M.IMPLIED.CITI": {
                    "type": "ERROR", "x": [], "c": [],
                },
                "FX.VOL.EUR.USD.ATM.1M.REALISED.CITI": {
                    "x": [self._X_2026_03_10], "c": [7.0],
                },
            },
        }
        df = citi_vol_response_to_df(resp)
        assert len(df) == 1
        assert df.iloc[0]["vol_type"] == "REALISED"
