"""Unit tests for commodities universe config and tag building."""
from __future__ import annotations

import pytest

from imdr.universe.commodities import get_commodities_universe


@pytest.fixture
def universe():
    return get_commodities_universe()


class TestCommodityDimension:
    def test_five_commodities(self, universe):
        entries = universe.commodity_create_entries()
        assert len(entries) == 5

    def test_commodity_symbols(self, universe):
        symbols = {e.symbol for e in universe.commodity_create_entries()}
        assert symbols == {"XAU", "XAG", "XPT", "CR_NYM_CL", "CR_IPE_BRENT"}

    def test_commodity_classes(self, universe):
        classes = {e.commodity_class for e in universe.commodity_create_entries()}
        assert classes == {"precious_metal", "energy"}

    def test_spot_tags_populated(self, universe):
        entries = universe.commodity_create_entries()
        with_spot = [e for e in entries if e.spot_tag is not None]
        assert len(with_spot) == 3  # XAU, XAG, CR_NYM_CL


class TestSpotTags:
    def test_three_spot_tags(self, universe):
        tags = universe.spot_tags()
        assert len(tags) == 3

    def test_gold_mapping(self, universe):
        tags = universe.spot_tags()
        assert tags["COMMODITIES.SPOT.SPOT_GOLD"] == "XAU"

    def test_spot_symbols(self, universe):
        symbols = universe.spot_commodity_symbols()
        assert set(symbols) == {"XAU", "XAG", "CR_NYM_CL"}


class TestEIATags:
    def test_eia_tag_count(self, universe):
        tags = universe.build_eia_tags()
        assert len(tags) == 67

    def test_eia_tag_format(self, universe):
        tags = universe.build_eia_tags()
        assert "COMMODITIES.EIA.CRUDE_STOCKS.TOTAL_US" in tags
        assert "COMMODITIES.EIA.CRUDE_STOCKS.CUSHING_OK" in tags

    def test_eia_series_create_entries(self, universe):
        entries = universe.eia_series_create_entries()
        assert len(entries) == 67
        assert entries[0].series_name == "CRUDE_STOCKS"

    def test_eia_series_count(self, universe):
        series = universe.eia_series()
        assert len(series) == 16


class TestVolTags:
    def test_vol_products(self, universe):
        products = universe.vol_products()
        assert set(products) == {"XAU", "XAG", "XPT", "CR_IPE_BRENT", "CR_NYM_CL"}

    def test_xau_strikes(self, universe):
        strikes = universe.vol_strikes_for_product("XAU")
        assert "ATM" in strikes
        assert "25RR" in strikes
        assert "SVVSTAR" in strikes
        # XPT-only strikes should not appear
        assert "BID" not in strikes

    def test_xpt_has_extra_strikes(self, universe):
        strikes = universe.vol_strikes_for_product("XPT")
        assert "BID" in strikes
        assert "ASK" in strikes
        assert "ATMF" in strikes

    def test_oil_strikes(self, universe):
        strikes = universe.vol_strikes_for_product("CR_NYM_CL")
        assert strikes == ["ATM"]

    def test_xau_tenors(self, universe):
        tenors = universe.vol_tenors_for_product("XAU")
        assert len(tenors) == 14
        assert "ON" in tenors
        assert "10Y" in tenors

    def test_xpt_tenors(self, universe):
        tenors = universe.vol_tenors_for_product("XPT")
        assert len(tenors) == 27
        assert "30Y" in tenors

    def test_oil_tenors(self, universe):
        tenors = universe.vol_tenors_for_product("CR_NYM_CL")
        assert len(tenors) == 12
        assert tenors[0] == "NEARBY01_M"
        assert tenors[-1] == "NEARBY12_M"

    def test_xau_tag_building(self, universe):
        tags = universe.build_vol_tags("XAU")
        # 13 standard + 3 exotic = 16 strikes, 14 tenors
        assert len(tags) == 16 * 14
        assert "COMMODITIES.IMPLIED_VOL.XAU.USD.ATM.1M" in tags

    def test_oil_tag_building(self, universe):
        tags = universe.build_vol_tags("CR_NYM_CL")
        assert len(tags) == 12
        assert "COMMODITIES.IMPLIED_VOL.CR_NYM_CL.ATM.NEARBY01_M" in tags

    def test_all_vol_tags(self, universe):
        tags = universe.build_all_vol_tags()
        # XAU: 224, XAG: 224, XPT: 19*27=513, CR_IPE_BRENT: 12, CR_NYM_CL: 12
        assert len(tags) > 900

    def test_quality_ranges(self, universe):
        ranges = universe.vol_quality_ranges()
        assert "ATM" in ranges
        lo, hi = ranges["ATM"]
        assert lo == 0.5
        assert hi == 200.0
