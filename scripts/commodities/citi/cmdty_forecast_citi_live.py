"""Citi Velocity commodity PRICE FORECAST loader (gas products).

Pulls the Citi house price-forecast branch for Henry Hub, TTF and JKM --
12 tags (3 products x 4 horizons) -- and upserts into
commodities.fact_price_forecast.

This is the ONLY route to a TTF or JKM number in IMDR: JKM is Platts-
proprietary and TTF settlement is ICE's, so neither has a free licensed feed,
and Citi carries no gas SPOT or futures tag at all. What this gives is Citi's
*house view*, not a market price -- label it as such downstream.

Shape (see imdr.domains.commodities.translate_forecast for the full note):
  POINT_PRICES.0_3M / .6_12M -> RELATIVE, x = the vendor's publication date.
      A step function; only the revisions are stored (`compress_steps`).
  QTR / ANNUAL               -> ABSOLUTE, x = the forecast TARGET period end.
      Current vintage only, so as_of_date is OUR snapshot date.

The full vendor history is re-fetched every run (12 tags is ~0.01% of the
100k/24h quota) and the compressed series recomputed, so the MERGE rewrites
the same natural keys rather than appending -- re-runs are no-ops.

IMPORTANT: `--end` must reach INTO THE FUTURE or the entire forward curve is
silently dropped, because for QTR/ANNUAL the x-axis is the target date, not a
publication date. Default is today + 4 years.

Usage:
    python -m scripts.commodities.citi.cmdty_forecast_citi_live
    python -m scripts.commodities.citi.cmdty_forecast_citi_live --no-load
    python -m scripts.commodities.citi.cmdty_forecast_citi_live --years 5
"""

from __future__ import annotations

import argparse
import datetime
import sys

import structlog

from imdr.config.settings import get_settings
from imdr.connectors.citi_quota import TagQuotaTracker
from imdr.connectors.citi_velocity import CitiVelocityClient
from imdr.connectors.mssql import MSSQLConnector
from imdr.domains.commodities.repository import (
    CmdtyCommodityRepository,
    CmdtyPriceForecastRepository,
)
from imdr.domains.commodities.translate_forecast import (
    citi_forecast_response_to_df,
    compress_steps,
    to_forecast_rows,
)
from imdr.universe.commodities import get_commodities_universe

_log = structlog.get_logger("CmdtyForecastCitiLive")

UTC = datetime.timezone.utc
PIPELINE_NAME = "commodities.price_forecast"

_DEFAULT_HISTORY_YEARS = 3
_DEFAULT_FORWARD_YEARS = 4


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--years", type=int, default=_DEFAULT_HISTORY_YEARS,
                   help="Years of vendor history to re-fetch (default 3).")
    p.add_argument("--forward-years", type=int, default=_DEFAULT_FORWARD_YEARS,
                   help="How far the window reaches forward; MUST exceed the "
                        "longest forecast target or the curve is truncated.")
    p.add_argument("--no-load", action="store_true",
                   help="Fetch and transform, print a summary, skip the DB write.")
    args = p.parse_args()

    settings = get_settings()
    universe = get_commodities_universe()
    specs = universe.forecast_specs()
    spec_by_tag = universe.forecast_spec_by_tag()
    tags = [s["tag"] for s in specs]

    now = datetime.datetime.now(UTC)
    start = now - datetime.timedelta(days=365 * args.years)
    end = now + datetime.timedelta(days=365 * args.forward_years)
    snapshot_date = now.date()

    print(f"{len(tags)} forecast tags  window {start:%Y-%m-%d} -> {end:%Y-%m-%d} "
          f"(forward: the ABSOLUTE curve lives past today)")

    tracker = TagQuotaTracker(
        quota_limit=settings.citi_tag_quota_limit,
        tracker_path=settings.citi_tag_quota_file or None,
    )
    tracker.check_budget(len(tags), PIPELINE_NAME)

    with CitiVelocityClient(settings) as client:
        resp = client.fetch_historical(tags, start, end, "DAILY")
    tracker.record_usage(PIPELINE_NAME, len(tags))

    df = citi_forecast_response_to_df(resp, spec_by_tag)
    if df.empty:
        print("ERROR: no rows returned for any of the 12 tags.")
        return 1

    returned = set(df["tag"].unique())
    missing = sorted(set(tags) - returned)
    if missing:
        # Same reasoning as the EIA storage fetcher: a partial response means
        # the vendor renamed or retired a tag. Loading the survivors would let
        # the rest go quietly stale.
        print(f"ERROR: {len(missing)}/{len(tags)} tags returned nothing: {missing}")
        return 1

    raw_rows = len(df)
    df = compress_steps(df)
    rows = to_forecast_rows(df, snapshot_date)

    print(f"\n{raw_rows:,} vendor points -> {len(rows):,} rows after step-compression")
    for spec in specs:
        sub = [r for r in rows
               if r["symbol"] == spec["symbol"]
               and r["horizon_code"] == spec["horizon_code"]]
        if not sub:
            continue
        latest = max(sub, key=lambda r: (r["target_date"] or r["as_of_date"]))
        label = f"{spec['symbol']}.{spec['horizon_code']}"
        when = latest["target_date"] or latest["as_of_date"]
        print(f"  {label:<18} {spec['horizon_type']:<8} {len(sub):>4} rows  "
              f"latest {when} = {latest['forecast_value']}")

    if args.no_load:
        print("\n--no-load set; skipping DB write.")
        return 0

    connector = MSSQLConnector(settings)
    with connector.session() as session:
        commodities = {c.symbol: c.id for c in CmdtyCommodityRepository(session).all()}
        vendor_id = _resolve_vendor_id(session, universe.forecast_vendor_code())

        unknown = sorted({r["symbol"] for r in rows} - set(commodities))
        if unknown:
            print(f"ERROR: symbols absent from dim_commodity: {unknown} "
                  f"(migration 132 seeds them)")
            return 1

        db_rows = [
            {
                "commodity_id": commodities[r["symbol"]],
                "vendor_id": vendor_id,
                "horizon_type": r["horizon_type"],
                "horizon_code": r["horizon_code"],
                "target_date": r["target_date"],
                "as_of_date": r["as_of_date"],
                "forecast_value": r["forecast_value"],
                "quote_unit": r["quote_unit"],
            }
            for r in rows
        ]
        written = CmdtyPriceForecastRepository(session).bulk_upsert(db_rows)
        session.commit()

    print(f"\nMERGE complete -- {written:,} rows staged into "
          f"commodities.fact_price_forecast")
    return 0


def _resolve_vendor_id(session, vendor_code: str) -> int:
    from sqlalchemy import text
    row = session.execute(
        text("SELECT id FROM dbo.dim_vendor WHERE vendor_code = :c"),
        {"c": vendor_code},
    ).first()
    if row is None:
        raise RuntimeError(f"vendor_code {vendor_code!r} not in dbo.dim_vendor")
    return int(row[0])


if __name__ == "__main__":
    sys.exit(main())
