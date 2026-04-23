"""Generic vendor-feed runner.

Usage:
    python -m scripts.run_vendor_feed <feed-name> [--headed]

Example:
    python -m scripts.run_vendor_feed barclays_skew

Lists every registered feed on ``--list`` so operators can discover
what's available without reading the registry module.
"""
from __future__ import annotations

import argparse
import sys

from imdr.vendors import list_feeds, run_vendor_feed_daily


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "feed",
        nargs="?",
        help="Registered feed name (see --list).",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List registered feeds and exit.",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Run browser headed (default: headless). Use for SSO bootstrap.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.list:
        feeds = list_feeds()
        if not feeds:
            print("(no vendor feeds registered)")
        else:
            print("Registered vendor feeds:")
            for name in feeds:
                print(f"  {name}")
        return 0

    if not args.feed:
        print("ERROR: feed name required (or pass --list).")
        return 2

    return run_vendor_feed_daily(args.feed, headless=not args.headed)


if __name__ == "__main__":
    sys.exit(main())
