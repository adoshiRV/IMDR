"""Unit tests for commodities tag parsing (translate modules)."""
from __future__ import annotations

import pandas as pd
import pytest

from imdr.domains.commodities.translate_spot import citi_spot_tag_to_internal
from imdr.domains.commodities.translate_eia import citi_eia_tag_to_internal
from imdr.domains.commodities.translate_vol import citi_cmdty_vol_tag_to_internal


# ── SPOT tag parsing ─────────────────────────────────────────────────


class TestSpotTagParsing:
    def test_gold_tag(self):
        result = citi_spot_tag_to_internal("COMMODITIES.SPOT.SPOT_GOLD")
        assert result == {"spot_tag": "COMMODITIES.SPOT.SPOT_GOLD"}

    def test_silver_tag(self):
        result = citi_spot_tag_to_internal("COMMODITIES.SPOT.SPOT_SILVER")
        assert result == {"spot_tag": "COMMODITIES.SPOT.SPOT_SILVER"}

    def test_oil_tag(self):
        result = citi_spot_tag_to_internal("COMMODITIES.SPOT.OIL_PRICE_NYMEX")
        assert result == {"spot_tag": "COMMODITIES.SPOT.OIL_PRICE_NYMEX"}

    def test_invalid_prefix(self):
        assert citi_spot_tag_to_internal("FX.SPOT.EURUSD") is None

    def test_too_many_parts(self):
        assert citi_spot_tag_to_internal("COMMODITIES.SPOT.GOLD.EXTRA") is None


# ── EIA tag parsing ──────────────────────────────────────────────────


class TestEIATagParsing:
    def test_crude_stocks_total(self):
        result = citi_eia_tag_to_internal("COMMODITIES.EIA.CRUDE_STOCKS.TOTAL_US")
        assert result == {"series_name": "CRUDE_STOCKS", "region": "TOTAL_US"}

    def test_gasoline_padd_iii(self):
        result = citi_eia_tag_to_internal("COMMODITIES.EIA.GASOLINE_STOCKS.PADD_III")
        assert result == {"series_name": "GASOLINE_STOCKS", "region": "PADD_III"}

    def test_cushing(self):
        result = citi_eia_tag_to_internal("COMMODITIES.EIA.CRUDE_STOCKS.CUSHING_OK")
        assert result == {"series_name": "CRUDE_STOCKS", "region": "CUSHING_OK"}

    def test_invalid_category(self):
        assert citi_eia_tag_to_internal("COMMODITIES.SPOT.CRUDE_STOCKS.TOTAL_US") is None

    def test_too_few_parts(self):
        assert citi_eia_tag_to_internal("COMMODITIES.EIA.CRUDE_STOCKS") is None


# ── IMPLIED_VOL tag parsing ──────────────────────────────────────────


class TestVolTagParsing:
    # Precious metals (6-part format)
    def test_xau_atm_1m(self):
        result = citi_cmdty_vol_tag_to_internal("COMMODITIES.IMPLIED_VOL.XAU.USD.ATM.1M")
        assert result == {"product": "XAU", "strike": "ATM", "tenor": "1M"}

    def test_xag_25rr_1y(self):
        result = citi_cmdty_vol_tag_to_internal("COMMODITIES.IMPLIED_VOL.XAG.USD.25RR.1Y")
        assert result == {"product": "XAG", "strike": "25RR", "tenor": "1Y"}

    def test_xpt_bid_on(self):
        result = citi_cmdty_vol_tag_to_internal("COMMODITIES.IMPLIED_VOL.XPT.USD.BID.ON")
        assert result == {"product": "XPT", "strike": "BID", "tenor": "ON"}

    def test_xau_svvstar_1w(self):
        result = citi_cmdty_vol_tag_to_internal("COMMODITIES.IMPLIED_VOL.XAU.USD.SVVSTAR.1W")
        assert result == {"product": "XAU", "strike": "SVVSTAR", "tenor": "1W"}

    # Oil (5-part format)
    def test_wti_nearby01(self):
        result = citi_cmdty_vol_tag_to_internal("COMMODITIES.IMPLIED_VOL.CR_NYM_CL.ATM.NEARBY01_M")
        assert result == {"product": "CR_NYM_CL", "strike": "ATM", "tenor": "NEARBY01_M"}

    def test_brent_nearby12(self):
        result = citi_cmdty_vol_tag_to_internal("COMMODITIES.IMPLIED_VOL.CR_IPE_BRENT.ATM.NEARBY12_M")
        assert result == {"product": "CR_IPE_BRENT", "strike": "ATM", "tenor": "NEARBY12_M"}

    # Edge cases
    def test_invalid_prefix(self):
        assert citi_cmdty_vol_tag_to_internal("FX.VOL.EUR.USD.ATM.1M") is None

    def test_unknown_product_5parts(self):
        # 5 parts but not a known oil product
        assert citi_cmdty_vol_tag_to_internal("COMMODITIES.IMPLIED_VOL.UNKNOWN.ATM.1M") is None

    def test_too_few_parts(self):
        assert citi_cmdty_vol_tag_to_internal("COMMODITIES.IMPLIED_VOL.XAU.USD") is None
