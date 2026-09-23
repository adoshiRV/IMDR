"""Tests for imdr.domains.commodities.translate_forecast + the forecast universe.

The whole risk in this module is that ONE tag family carries TWO shapes and the
`x` axis means a different thing in each. These tests pin that down:

- RELATIVE rows take the VENDOR's publication date as as_of_date and must never
  be stamped with the run date (that would collapse 2.2y of revisions onto today).
- ABSOLUTE rows take the run date as as_of_date and the vendor's x as target_date.
- Step compression keeps first + changes for RELATIVE, leaves ABSOLUTE alone.
- The MERGE join must be NULL-safe on target_date, or every RELATIVE row
  re-inserts on each run and collides with the unique index.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from imdr.domains.commodities.translate_forecast import (
    citi_forecast_response_to_df,
    compress_steps,
    make_forecast_tag_parser,
    to_forecast_rows,
)
from imdr.universe.commodities import get_commodities_universe

HH_REL = "COMMODITIES.FORECAST.ENERGY.HH_NGAS.POINT_PRICES.0_3M.PRICE_FCST.CITI"
HH_QTR = "COMMODITIES.FORECAST.ENERGY.HH_NGAS.QTR.PRICE_FCST.CITI"
TTF_REL = "COMMODITIES.FORECAST.ENERGY.TTF_NGAS.POINT_PRICES.0_3M.PRICE_FCST.CITI"

SNAPSHOT = date(2026, 9, 23)


@pytest.fixture
def spec_by_tag() -> dict[str, dict]:
    return get_commodities_universe().forecast_spec_by_tag()


def _resp(series: dict[str, tuple[list[int], list]]) -> dict:
    return {
        "status": "OK",
        "frequency": "DAILY",
        "body": {
            tag: {"x": xs, "c": cs, "type": "SERIES"} for tag, (xs, cs) in series.items()
        },
    }


# ---------------------------------------------------------------------------
# Universe wiring
# ---------------------------------------------------------------------------

class TestForecastUniverse:
    def test_twelve_gas_tags(self) -> None:
        u = get_commodities_universe()
        assert len(u.forecast_tags()) == 12
        assert len(set(u.forecast_tags())) == 12

    def test_every_spec_resolves_to_a_seeded_commodity(self) -> None:
        u = get_commodities_universe()
        symbols = {c["symbol"] for c in u.commodity_entries()}
        for spec in u.forecast_specs():
            assert spec["symbol"] in symbols, spec

    def test_horizon_types_are_split_correctly(self) -> None:
        by_code = {s["horizon_code"]: s["horizon_type"]
                   for s in get_commodities_universe().forecast_specs()}
        assert by_code == {
            "0_3M": "RELATIVE", "6_12M": "RELATIVE",
            "QTR": "ABSOLUTE", "ANNUAL": "ABSOLUTE",
        }

    def test_ttf_is_quoted_usd_mmbtu_not_eur_mwh(self) -> None:
        """TTF sits 1-2 BELOW JKM across every revision; in EUR/MWh it would be ~3x
        smaller. Pinned because the Citi metadata endpoint returns no units."""
        units = {s["symbol"]: s["quote_unit"]
                 for s in get_commodities_universe().forecast_specs()}
        assert units["NG_TTF"] == "usd_mmbtu"
        assert units["NG_JKM"] == "usd_mmbtu"
        assert units["NG_HH"] == "usd_mmbtu"

    def test_api_symbols_includes_forecast_tags(self) -> None:
        u = get_commodities_universe()
        assert set(u.forecast_tags()).issubset(set(u.api_symbols()))


# ---------------------------------------------------------------------------
# Tag parsing
# ---------------------------------------------------------------------------

class TestTagParser:
    def test_known_tag_resolves_from_universe(self, spec_by_tag) -> None:
        parsed = make_forecast_tag_parser(spec_by_tag)(HH_REL)
        assert parsed["symbol"] == "NG_HH"
        assert parsed["horizon_code"] == "0_3M"
        assert parsed["horizon_type"] == "RELATIVE"
        assert parsed["quote_unit"] == "usd_mmbtu"

    def test_unknown_tag_returns_none_rather_than_inventing(self, spec_by_tag) -> None:
        parse = make_forecast_tag_parser(spec_by_tag)
        assert parse("COMMODITIES.FORECAST.ENERGY.NOT_A_PRODUCT.QTR.PRICE_FCST.CITI") is None
        assert parse("COMMODITIES.SPOT.SPOT_GOLD") is None


# ---------------------------------------------------------------------------
# Response -> frame
# ---------------------------------------------------------------------------

class TestResponseToFrame:
    def test_parses_x_and_c(self, spec_by_tag) -> None:
        df = citi_forecast_response_to_df(
            _resp({HH_REL: ([20260101, 20260102], [2.5, 2.8])}), spec_by_tag
        )
        assert len(df) == 2
        assert list(df["value"]) == [2.5, 2.8]
        assert set(df["symbol"]) == {"NG_HH"}

    def test_unknown_tags_are_dropped(self, spec_by_tag) -> None:
        df = citi_forecast_response_to_df(
            _resp({HH_REL: ([20260101], [2.5]),
                   "COMMODITIES.FORECAST.ENERGY.MYSTERY.QTR.PRICE_FCST.CITI":
                       ([20260101], [9.9])}),
            spec_by_tag,
        )
        assert len(df) == 1

    def test_error_series_is_skipped_not_fatal(self, spec_by_tag) -> None:
        resp = _resp({HH_REL: ([20260101], [2.5])})
        resp["body"][TTF_REL] = {"type": "ERROR", "message": "no data"}
        df = citi_forecast_response_to_df(resp, spec_by_tag)
        assert set(df["tag"]) == {HH_REL}

    def test_null_values_are_dropped(self, spec_by_tag) -> None:
        df = citi_forecast_response_to_df(
            _resp({HH_REL: ([20260101, 20260102], [None, 2.8])}), spec_by_tag
        )
        assert list(df["value"]) == [2.8]

    def test_non_ok_status_raises(self, spec_by_tag) -> None:
        with pytest.raises(RuntimeError):
            citi_forecast_response_to_df({"status": "ERROR", "body": {}}, spec_by_tag)

    def test_empty_body_yields_empty_frame(self, spec_by_tag) -> None:
        assert citi_forecast_response_to_df(_resp({}), spec_by_tag).empty


# ---------------------------------------------------------------------------
# Step compression
# ---------------------------------------------------------------------------

class TestCompressSteps:
    def test_relative_keeps_first_and_changes_only(self, spec_by_tag) -> None:
        xs = [20260101, 20260102, 20260103, 20260104, 20260105]
        cs = [2.5, 2.5, 2.5, 2.8, 2.8]
        df = compress_steps(citi_forecast_response_to_df(_resp({HH_REL: (xs, cs)}), spec_by_tag))
        assert list(df["value"]) == [2.5, 2.8]
        assert [t.date() for t in df["ts"]] == [date(2026, 1, 1), date(2026, 1, 4)]

    def test_a_value_that_returns_is_kept_as_a_new_step(self, spec_by_tag) -> None:
        """2.5 -> 2.8 -> 2.5 is three revisions, not two distinct values."""
        df = compress_steps(citi_forecast_response_to_df(
            _resp({HH_REL: ([20260101, 20260102, 20260103], [2.5, 2.8, 2.5])}), spec_by_tag))
        assert list(df["value"]) == [2.5, 2.8, 2.5]

    def test_absolute_rows_pass_through_untouched(self, spec_by_tag) -> None:
        """Repeated values across a curve are different target periods, not repeats."""
        df = compress_steps(citi_forecast_response_to_df(
            _resp({HH_QTR: ([20260331, 20260630, 20260930], [3.0, 3.0, 3.0])}), spec_by_tag))
        assert len(df) == 3

    def test_tags_are_compressed_independently(self, spec_by_tag) -> None:
        df = compress_steps(citi_forecast_response_to_df(
            _resp({HH_REL: ([20260101, 20260102], [2.5, 2.5]),
                   TTF_REL: ([20260101, 20260102], [18.0, 19.0])}), spec_by_tag))
        counts = df.groupby("tag").size().to_dict()
        assert counts[HH_REL] == 1
        assert counts[TTF_REL] == 2

    def test_empty_frame_is_safe(self) -> None:
        assert compress_steps(pd.DataFrame()).empty


# ---------------------------------------------------------------------------
# Frame -> fact rows  (the crux)
# ---------------------------------------------------------------------------

class TestToForecastRows:
    def test_relative_uses_vendor_date_as_as_of_and_no_target(self, spec_by_tag) -> None:
        rows = to_forecast_rows(
            citi_forecast_response_to_df(_resp({HH_REL: ([20260115], [2.5])}), spec_by_tag),
            SNAPSHOT,
        )
        assert rows[0]["as_of_date"] == date(2026, 1, 15)   # NOT the snapshot date
        assert rows[0]["target_date"] is None
        assert rows[0]["horizon_type"] == "RELATIVE"

    def test_relative_is_not_stamped_with_the_run_date(self, spec_by_tag) -> None:
        """Regression guard: stamping the run date collapses the revision history."""
        rows = to_forecast_rows(
            citi_forecast_response_to_df(
                _resp({HH_REL: ([20240701, 20250320, 20260616], [2.5, 4.0, 2.8])}),
                spec_by_tag),
            SNAPSHOT,
        )
        assert sorted(r["as_of_date"] for r in rows) == [
            date(2024, 7, 1), date(2025, 3, 20), date(2026, 6, 16),
        ]
        assert all(r["as_of_date"] != SNAPSHOT for r in rows)

    def test_absolute_uses_snapshot_as_as_of_and_vendor_x_as_target(self, spec_by_tag) -> None:
        rows = to_forecast_rows(
            citi_forecast_response_to_df(
                _resp({HH_QTR: ([20261231, 20270331], [3.3, 3.2])}), spec_by_tag),
            SNAPSHOT,
        )
        assert {r["as_of_date"] for r in rows} == {SNAPSHOT}
        assert sorted(r["target_date"] for r in rows) == [
            date(2026, 12, 31), date(2027, 3, 31),
        ]

    def test_absolute_keeps_past_targets(self, spec_by_tag) -> None:
        """target_date <= as_of_date is the REALISED number, still stored."""
        rows = to_forecast_rows(
            citi_forecast_response_to_df(
                _resp({HH_QTR: ([20240331, 20271231], [2.1, 2.8])}), spec_by_tag),
            SNAPSHOT,
        )
        past = [r for r in rows if r["target_date"] < SNAPSHOT]
        assert len(past) == 1 and past[0]["forecast_value"] == 2.1

    def test_mixed_shapes_in_one_call(self, spec_by_tag) -> None:
        rows = to_forecast_rows(
            citi_forecast_response_to_df(
                _resp({HH_REL: ([20260115], [2.5]), HH_QTR: ([20261231], [3.3])}),
                spec_by_tag),
            SNAPSHOT,
        )
        rel = [r for r in rows if r["horizon_type"] == "RELATIVE"][0]
        abso = [r for r in rows if r["horizon_type"] == "ABSOLUTE"][0]
        assert rel["target_date"] is None and rel["as_of_date"] == date(2026, 1, 15)
        assert abso["target_date"] == date(2026, 12, 31) and abso["as_of_date"] == SNAPSHOT

    def test_empty_frame_yields_no_rows(self) -> None:
        assert to_forecast_rows(pd.DataFrame(), SNAPSHOT) == []


# ---------------------------------------------------------------------------
# MERGE must be NULL-safe on target_date
# ---------------------------------------------------------------------------

class TestForecastMergeSpec:
    def test_join_is_null_safe_on_target_date(self) -> None:
        """Without this, `NULL = NULL` never matches: every RELATIVE row
        re-inserts each run and collides with the unique index."""
        from imdr.domains.commodities.repository import _FORECAST_SPEC

        sql = _FORECAST_SPEC._build_merge_sql()
        assert "tgt.target_date IS NULL AND src.target_date IS NULL" in sql
        # the other key columns stay plain equality
        assert "tgt.as_of_date = src.as_of_date" in sql
        assert "tgt.commodity_id = src.commodity_id" in sql

    def test_natural_key_matches_the_unique_index(self) -> None:
        from imdr.domains.commodities.repository import _FORECAST_SPEC

        assert _FORECAST_SPEC.natural_key == [
            "commodity_id", "vendor_id", "horizon_code", "target_date", "as_of_date",
        ]
