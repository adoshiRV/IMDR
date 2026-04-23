"""Probe — does Citi Velocity return real intraday points at HOURLY frequency?

Pulls ONE curve (USD SOFR par by default) for today's UTC window at HOURLY
frequency. No DB write, no email. Prints the per-tenor timeseries so we can
eyeball whether Citi is actually serving hourly ticks or collapsing to daily.

Usage:
    python -m scripts.explore.probe_rates_citi_hourly
    python -m scripts.explore.probe_rates_citi_hourly --ccy EUR --curve EUROSTR
    python -m scripts.explore.probe_rates_citi_hourly --frequency 10Min
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

from imdr.config.settings import get_settings
from imdr.connectors.citi_quota import TagQuotaTracker
from imdr.connectors.citi_velocity import CitiVelocityClient
from imdr.domains.rates.extractors import CitiVelocityRatesExtractor
from imdr.universe.rates import get_rates_universe
from imdr.utils.logging import configure_logging


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Citi hourly-frequency probe (rates)")
    p.add_argument("--ccy", default="USD")
    p.add_argument("--curve", default="SOFR")
    p.add_argument("--quote", default="par")
    p.add_argument("--frequency", default="HOURLY",
                   help="Citi frequency string (HOURLY, 10Min, 1Min, DAILY, ...)")
    p.add_argument("--date", default=None, help="YYYY-MM-DD, default today UTC")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    settings = get_settings()
    configure_logging(settings)

    if args.date:
        day = datetime.strptime(args.date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    else:
        day = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    start = day
    end = day.replace(hour=23, minute=59)

    print(f"=== Citi hourly probe ===")
    print(f"  slice:     {args.ccy} {args.curve} [{args.quote}]")
    print(f"  window:    {start.isoformat()} -> {end.isoformat()}")
    print(f"  frequency: {args.frequency}")
    print()

    tracker = TagQuotaTracker(
        quota_limit=settings.citi_tag_quota_limit,
        tracker_path=settings.citi_tag_quota_file or None,
    )

    with CitiVelocityClient(settings) as client:
        extractor = CitiVelocityRatesExtractor(
            client=client,
            settings=settings,
            universe=get_rates_universe(),
            cache=None,
            quota_tracker=tracker,
        )
        df = extractor.extract(
            start=start,
            end=end,
            quotes=[args.quote],
            frequency=args.frequency,
            curves=[(args.ccy, args.curve)],
        )

    print(f"rows returned: {len(df)}")
    if df.empty:
        print("EMPTY RESPONSE — Citi returned no points for this window/frequency.")
        return 2

    unique_ts = sorted(df["ts"].unique())
    print(f"unique timestamps: {len(unique_ts)}")
    for ts in unique_ts[:24]:
        print(f"  {ts}")
    if len(unique_ts) > 24:
        print(f"  ... +{len(unique_ts) - 24} more")

    print()
    print("per-tenor point counts:")
    per_tenor = df.groupby("tenor").size().sort_values(ascending=False)
    for tenor, n in per_tenor.items():
        print(f"  {tenor:>6} : {n}")

    print()
    print("sample rows:")
    with_cols = ["ts", "ccy", "curve", "quote", "tenor", "value"]
    print(df[with_cols].head(10).to_string(index=False))

    if len(unique_ts) <= 1:
        print()
        print("WARNING: only 1 distinct timestamp — Citi is likely serving DAILY")
        print("data under the hood, not honouring the requested frequency.")
        return 3

    return 0


if __name__ == "__main__":
    sys.exit(main())
