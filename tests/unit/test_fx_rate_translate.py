"""Tests for domains/fx/rate_translate.py — tag parsing + long→wide pivot."""

import pandas as pd
import pytest

from imdr.domains.fx.rate_translate import (
    LONG_COLUMNS,
    WIDE_COLUMNS,
    citi_fx_rate_response_to_long_df,
    citi_fx_rate_tag_to_internal,
    pivot_long_to_wide,
)


class TestCitiTagToInternal:
    def test_spot(self) -> None:
        result = citi_fx_rate_tag_to_internal("FX.SPOT.EUR.USD.CITI")
        assert result == {
            "base_ccy": "EUR", "quote_ccy": "USD",
            "tenor": "SPOT", "quote_kind": "mid_rate",
        }

    def test_fwd_outright(self) -> None:
        result = citi_fx_rate_tag_to_internal("FX.FORWARD.FWD_OUTRIGHT.USD.HKD.1M.CITI")
        assert result == {
            "base_ccy": "USD", "quote_ccy": "HKD",
            "tenor": "1M", "quote_kind": "mid_rate",
        }

    def test_fwd_point(self) -> None:
        result = citi_fx_rate_tag_to_internal("FX.FORWARD.FWD_POINT.EUR.USD.3M.CITI")
        assert result == {
            "base_ccy": "EUR", "quote_ccy": "USD",
            "tenor": "3M", "quote_kind": "fwd_points",
        }

    def test_fwd_point_pip_not_recognized(self) -> None:
        # FWD_POINT_PIP is out of scope — should return None
        assert (
            citi_fx_rate_tag_to_internal("FX.FORWARD.FWD_POINT_PIP.EUR.USD.1M.CITI")
            is None
        )

    def test_unknown_prefix(self) -> None:
        assert citi_fx_rate_tag_to_internal("RATES.OIS.USD_SOFR.PAR.5Y") is None

    def test_missing_citi_suffix(self) -> None:
        assert citi_fx_rate_tag_to_internal("FX.SPOT.EUR.USD") is None

    def test_non_fx_root(self) -> None:
        assert citi_fx_rate_tag_to_internal("EQUITY.SPX.CITI") is None

    def test_imm_not_recognized(self) -> None:
        # Phase 1 scope excludes IMM
        assert citi_fx_rate_tag_to_internal("FX.FORWARD.FWD_IMM.EUR.USD.CITI") is None


class TestCitiResponseToLongDf:
    def test_empty_body(self) -> None:
        resp = {"status": "OK", "body": {}}
        df = citi_fx_rate_response_to_long_df(resp)
        assert df.empty
        assert list(df.columns) == LONG_COLUMNS

    def test_spot_response(self) -> None:
        resp = {
            "status": "OK",
            "body": {
                "FX.SPOT.EUR.USD.CITI": {
                    "type": "SERIES",
                    "x": [20260421],
                    "c": [1.17887],
                }
            },
        }
        df = citi_fx_rate_response_to_long_df(resp)
        assert len(df) == 1
        row = df.iloc[0]
        assert row["base_ccy"] == "EUR"
        assert row["tenor"] == "SPOT"
        assert row["quote_kind"] == "mid_rate"
        assert row["numeric"] == 1.17887

    def test_mixed_spot_and_forward(self) -> None:
        resp = {
            "status": "OK",
            "body": {
                "FX.SPOT.USD.HKD.CITI": {
                    "type": "SERIES", "x": [20260421], "c": [7.82],
                },
                "FX.FORWARD.FWD_OUTRIGHT.USD.HKD.1M.CITI": {
                    "type": "SERIES", "x": [20260421], "c": [7.821],
                },
                "FX.FORWARD.FWD_POINT.USD.HKD.1M.CITI": {
                    "type": "SERIES", "x": [20260421], "c": [0.001],
                },
            },
        }
        df = citi_fx_rate_response_to_long_df(resp)
        assert len(df) == 3
        kinds = set(df["quote_kind"])
        assert kinds == {"mid_rate", "fwd_points"}

    def test_error_tag_skipped(self) -> None:
        resp = {
            "status": "OK",
            "body": {
                "FX.SPOT.EUR.USD.CITI": {"type": "SERIES", "x": [20260421], "c": [1.17]},
                "FX.SPOT.USD.VND.CITI": {"type": "ERROR", "c": []},
            },
        }
        df = citi_fx_rate_response_to_long_df(resp)
        assert len(df) == 1
        assert df.iloc[0]["quote_ccy"] == "USD"


class TestPivotLongToWide:
    def test_empty(self) -> None:
        long_df = pd.DataFrame(columns=LONG_COLUMNS)
        wide = pivot_long_to_wide(long_df)
        assert wide.empty
        assert list(wide.columns) == WIDE_COLUMNS

    def test_spot_row_has_null_fwd_points(self) -> None:
        long_df = pd.DataFrame([
            {"ts": pd.Timestamp("2026-04-21", tz="UTC"), "base_ccy": "EUR", "quote_ccy": "USD",
             "tenor": "SPOT", "quote_kind": "mid_rate", "numeric": 1.17887},
        ])
        wide = pivot_long_to_wide(long_df)
        assert len(wide) == 1
        row = wide.iloc[0]
        assert row["mid_rate"] == 1.17887
        assert pd.isna(row["fwd_points"])

    def test_forward_row_has_both(self) -> None:
        long_df = pd.DataFrame([
            {"ts": pd.Timestamp("2026-04-21", tz="UTC"), "base_ccy": "USD", "quote_ccy": "HKD",
             "tenor": "1M", "quote_kind": "mid_rate", "numeric": 7.821},
            {"ts": pd.Timestamp("2026-04-21", tz="UTC"), "base_ccy": "USD", "quote_ccy": "HKD",
             "tenor": "1M", "quote_kind": "fwd_points", "numeric": 0.001},
        ])
        wide = pivot_long_to_wide(long_df)
        assert len(wide) == 1
        row = wide.iloc[0]
        assert row["mid_rate"] == 7.821
        assert row["fwd_points"] == 0.001

    def test_multiple_tenors_same_pair(self) -> None:
        ts = pd.Timestamp("2026-04-21", tz="UTC")
        long_df = pd.DataFrame([
            {"ts": ts, "base_ccy": "USD", "quote_ccy": "HKD", "tenor": "1M",
             "quote_kind": "mid_rate", "numeric": 7.821},
            {"ts": ts, "base_ccy": "USD", "quote_ccy": "HKD", "tenor": "1Y",
             "quote_kind": "mid_rate", "numeric": 7.746},
        ])
        wide = pivot_long_to_wide(long_df)
        assert len(wide) == 2
        assert set(wide["tenor"]) == {"1M", "1Y"}
