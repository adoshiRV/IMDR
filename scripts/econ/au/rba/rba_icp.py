"""RBA I2 — Index of Commodity Prices.

CSV snapshot at ``data/econ/au/rba/samples/i2-data.csv``,
captured via Playwright by ``rba_snapshot_refresh.py`` (Akamai-gated, plain
GET 403s). The CSV has 21 series = 7 sub-indices × 3 currencies (A$,
SDR, US$). Monthly since 1982.

Why we care: AU is the textbook commodity FX. ToT shocks drive AUD;
the bulk/rural/base-metals split lets analytics attribute ToT changes
to specific sub-components.

Filing the entire 21-series set — each is small (~520 monthly obs)
and the sub-components are how macro questions get answered.

Series IDs (from CSV "Series ID" header row):

  Total ICP:                         GRCPAIAD  GRCPAISDR  GRCPAIUSD
  Rural component:                   GRCPRCAD  GRCPRCSDR  GRCPRCUSD
  Non-rural component:               GRCPNRAD  GRCPNRSDR  GRCPNRUSD
  Non-rural — Base metals:           GRCPBMAD  GRCPBMSDR  GRCPBMUSD
  Non-rural — Bulk (export prices):  GRCPBCAD  GRCPBCSDR  GRCPBCUSD
  Total (with bulk spot prices):     GRCPAISAD GRCPAISSDR GRCPAISUSD
  Non-rural — Bulk (spot prices):    GRCPBCSAD GRCPBCSSDR GRCPBCSUSD
"""
from __future__ import annotations

import sys

from imdr.domains.econ.rba_tables import RBASeries, fetch_specs
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main


def _make(series_id: str, suffix: str, label: str) -> RBASeries:
    """Build one RBASeries row. All ICP series share table/freq/unit/category."""
    return RBASeries(
        "i2", series_id,
        f"RBA.ICP.{suffix}",
        f"RBA Index of Commodity Prices — {label} (monthly, Index 2024/25=100)",
        "index", "MONTHLY", "energy",
    )


_SERIES = [
    # ----- Total Commodity Price Index -----
    _make("GRCPAIAD",   "TOTAL_AUD.AU",        "All items, A$"),
    _make("GRCPAISDR",  "TOTAL_SDR.AU",        "All items, SDR"),
    _make("GRCPAIUSD",  "TOTAL_USD.AU",        "All items, US$"),

    # ----- Rural -----
    _make("GRCPRCAD",   "RURAL_AUD.AU",        "Rural, A$"),
    _make("GRCPRCSDR",  "RURAL_SDR.AU",        "Rural, SDR"),
    _make("GRCPRCUSD",  "RURAL_USD.AU",        "Rural, US$"),

    # ----- Non-rural -----
    _make("GRCPNRAD",   "NONRURAL_AUD.AU",     "Non-rural, A$"),
    _make("GRCPNRSDR",  "NONRURAL_SDR.AU",     "Non-rural, SDR"),
    _make("GRCPNRUSD",  "NONRURAL_USD.AU",     "Non-rural, US$"),

    # ----- Non-rural — Base metals -----
    _make("GRCPBMAD",   "BASE_METALS_AUD.AU",  "Base metals, A$"),
    _make("GRCPBMSDR",  "BASE_METALS_SDR.AU",  "Base metals, SDR"),
    _make("GRCPBMUSD",  "BASE_METALS_USD.AU",  "Base metals, US$"),

    # ----- Non-rural — Bulk commodities (export price movements) -----
    _make("GRCPBCAD",   "BULK_EXPORT_AUD.AU",  "Bulk commodities (export prices), A$"),
    _make("GRCPBCSDR",  "BULK_EXPORT_SDR.AU",  "Bulk commodities (export prices), SDR"),
    _make("GRCPBCUSD",  "BULK_EXPORT_USD.AU",  "Bulk commodities (export prices), US$"),

    # ----- All items (with bulk commodities spot prices) -----
    _make("GRCPAISAD",  "TOTAL_SPOT_AUD.AU",   "All items (with bulk spot prices), A$"),
    _make("GRCPAISSDR", "TOTAL_SPOT_SDR.AU",   "All items (with bulk spot prices), SDR"),
    _make("GRCPAISUSD", "TOTAL_SPOT_USD.AU",   "All items (with bulk spot prices), US$"),

    # ----- Non-rural — Bulk commodities (spot price movements) -----
    _make("GRCPBCSAD",  "BULK_SPOT_AUD.AU",    "Bulk commodities (spot prices), A$"),
    _make("GRCPBCSSDR", "BULK_SPOT_SDR.AU",    "Bulk commodities (spot prices), SDR"),
    _make("GRCPBCSUSD", "BULK_SPOT_USD.AU",    "Bulk commodities (spot prices), US$"),
]


def run_fetch(since: str | None, until: str | None) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    return fetch_specs(_SERIES, since, until)


def main() -> int:
    return run_main(vendor="rba", topic="icp", fetch_fn=run_fetch,
                    description=__doc__.splitlines()[0] if __doc__ else "",
                    country_code="AU")


if __name__ == "__main__":
    sys.exit(main())
