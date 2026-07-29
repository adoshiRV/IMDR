"""BBG EconDashboards Brent -> commodities.fact_spot.

Fills the empty CR_IPE_BRENT (ICE Brent) spot series from the EconDashboards
SQLite ticker `CO1 Comdty` (Generic 1st Brent future, used as the Brent
benchmark, USD/bbl). Month-end sampled (~monthly), 2021->2026.

Source is the EconDashboards SQLite (read-only staging). Idempotent MERGE on
(commodity_id, obs_date) via CmdtySpotRepository.

Usage:
    python -m scripts.commodities.bbg_econdashboard_oil --no-load   # report only
    python -m scripts.commodities.bbg_econdashboard_oil             # upsert
"""

from __future__ import annotations

import argparse
import sys

from imdr.config.settings import get_settings
from imdr.connectors.mssql import MSSQLConnector
from imdr.domains.commodities.repository import CmdtyCommodityRepository, CmdtySpotRepository
from imdr.domains.econ.bbg_econdashboard import read_ticker_observations
from imdr.schemas.commodities import SpotCreate

BRENT_TICKER = "CO1 Comdty"
BRENT_SYMBOL = "CR_IPE_BRENT"   # commodities.dim_commodity


def run(since: str | None, until: str | None, no_load: bool) -> int:
    obs = read_ticker_observations([BRENT_TICKER], since=since, until=until).get(BRENT_TICKER, [])
    if not obs:
        print("No Brent observations found.", file=sys.stderr)
        return 1

    connector = MSSQLConnector(get_settings())
    with connector.session() as session:
        commodity = CmdtyCommodityRepository(session).get_by_key(BRENT_SYMBOL)
        if commodity is None:
            print(f"ERROR: commodity {BRENT_SYMBOL} not in commodities.dim_commodity.", file=sys.stderr)
            return 2
        commodity_id = commodity.id

    items = [SpotCreate(commodity_id=commodity_id, obs_date=d, price=v) for d, v in obs]
    lo, hi = obs[0], obs[-1]
    prices = [v for _, v in obs]
    print(f"{BRENT_SYMBOL} (id {commodity_id}) <- {BRENT_TICKER}")
    print(f"  {len(items)} obs  {lo[0]} -> {hi[0]}  min={min(prices):.2f} max={max(prices):.2f} latest={hi[1]:.2f}")
    if no_load:
        print("[--no-load] nothing written.")
        return 0
    with connector.session() as session:
        n = CmdtySpotRepository(session).bulk_upsert(items)
    print(f"upserted {n} rows into commodities.fact_spot")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="BBG EconDashboards Brent -> commodities.fact_spot")
    p.add_argument("--since", help="Earliest obs_date, YYYY-MM-DD.")
    p.add_argument("--until", help="Latest obs_date, YYYY-MM-DD.")
    p.add_argument("--no-load", action="store_true", help="Report only; no DB write.")
    args = p.parse_args()
    return run(args.since, args.until, args.no_load)


if __name__ == "__main__":
    sys.exit(main())
