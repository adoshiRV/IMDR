"""Tests for domains/rates/discovery.py — tag parsing (no API calls)."""

from imdr.domains.rates.discovery import RatesTagDiscovery


# Use a mock client since we only test local parsing
class _MockClient:
    pass


def _make_discovery():
    from imdr.universe.rates import get_rates_universe
    return RatesTagDiscovery(client=_MockClient(), universe=get_rates_universe())


class TestDiscoverOis:
    def test_parses_ois_tags(self):
        discovery = _make_discovery()
        tags = [
            "RATES.OIS.USD_SOFR.PAR.5Y",
            "RATES.OIS.USD_SOFR.PAR.10Y",
            "RATES.OIS.EUR_EUROSTR.PAR.5Y",
        ]
        result = discovery.discover_ois(tags)
        assert len(result["pairs"]) == 2
        assert "PAR" in result["quote_types"]
        assert "5Y" in result["quote_types"]["PAR"]

    def test_empty_tags(self):
        discovery = _make_discovery()
        # Empty list is falsy in Python, so `tags or ...` falls through to API.
        # Pass a non-matching tag to test the parsing-returns-nothing path.
        result = discovery.discover_ois(tags=["NOT_A_REAL_TAG"])
        assert result["pairs"] == []

    def test_ignores_swap_tags(self):
        discovery = _make_discovery()
        tags = ["RATES.SWAP_LIBOR.USD.PAR.5Y"]
        result = discovery.discover_ois(tags)
        assert result["pairs"] == []


class TestDiscoverSwapLibor:
    def test_parses_swap_tags(self):
        discovery = _make_discovery()
        tags = [
            "RATES.SWAP_LIBOR.USD.PAR.5Y",
            "RATES.SWAP_LIBOR.USD.PAR.10Y",
            "RATES.SWAP_LIBOR.EUR.PAR.5Y",
        ]
        result = discovery.discover_swap_libor(tags)
        assert "USD" in result["currencies"]
        assert "EUR" in result["currencies"]
        assert "PAR" in result["quote_types"]

    def test_empty_tags(self):
        discovery = _make_discovery()
        result = discovery.discover_swap_libor(tags=["NOT_A_REAL_TAG"])
        assert result["currencies"] == []


class TestDiscoverAll:
    def test_combines(self):
        discovery = _make_discovery()
        # Monkey-patch fetch_all_par_tags to avoid API call
        tags = [
            "RATES.OIS.USD_SOFR.PAR.5Y",
            "RATES.SWAP_LIBOR.EUR.PAR.10Y",
        ]
        discovery.fetch_all_par_tags = lambda force=False: tags

        result = discovery.discover_all()
        assert result["total_tags"] == 2
        assert len(result["ois"]["pairs"]) == 1
        assert len(result["swap_libor"]["currencies"]) == 1


class TestValidateCatalog:
    def test_validation_structure(self):
        discovery = _make_discovery()
        tags = [
            "RATES.OIS.USD_SOFR.PAR.5Y",
            "RATES.OIS.EUR_EUROSTR.PAR.5Y",
            "RATES.OIS.XXX_YYY.PAR.5Y",  # uncataloged
        ]
        discovery.fetch_all_par_tags = lambda force=False: tags

        result = discovery.validate_catalog()
        assert "matched" in result
        assert "unmatched" in result
        assert "uncataloged" in result
        assert result["matched"] >= 2
        assert "RATES.OIS.XXX_YYY" in result["uncataloged_prefixes"]
