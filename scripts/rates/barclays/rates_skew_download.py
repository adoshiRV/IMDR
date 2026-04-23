"""Download SKEW BARCLAYS Excel reports from Barclays Live.

Thin CLI wrapper around the ``barclays_skew`` feed registered in
``imdr.vendors``.  Does NOT run the loader — just fetches files into
``data/skew/``.  For the daily pipeline (fetch + load + email) use::

    python -m scripts.run_vendor_feed barclays_skew

Usage:
    python -m scripts.rates.barclays.rates_skew_download
    python -m scripts.rates.barclays.rates_skew_download --headed
"""
from __future__ import annotations

import argparse
import sys

import structlog

from imdr.config.settings import get_settings
from imdr.notifications.email import send_outlook_email
from imdr.notifications.formatters.vendor_fetch_failure import VendorFetchFailureFormatter
from imdr.utils.logging import configure_logging
from imdr.vendors import get_feed
from imdr.vendors.exceptions import VendorError

log = structlog.get_logger(__name__)

FEED_NAME = "barclays_skew"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Run browser headed (default: headless). Use for SSO bootstrap.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = get_settings()
    configure_logging(settings)

    feed = get_feed(FEED_NAME)
    try:
        result = feed.acquirer.fetch(headless=not args.headed)
    except VendorError as exc:
        error_type = type(exc).__name__
        log.exception("skew_download_failed", error_type=error_type)
        if settings.email_enabled and settings.email_to:
            fmt = VendorFetchFailureFormatter()
            send_outlook_email(
                to=settings.email_to,
                subject=fmt.format_subject(feed_name=feed.name, error_type=error_type),
                html_body=fmt.format_body(
                    feed_name=feed.name,
                    vendor_code=feed.vendor_code,
                    phase="acquire",
                    error_type=error_type,
                    error_message=str(exc),
                ),
                importance=2,
            )
        return 1

    print(f"Saved {len(result.saved_files)} file(s) "
          f"({result.bytes_downloaded:,} bytes, {result.elapsed_s:.1f}s):")
    for p in result.saved_files:
        print(f"  {p}")
    print("\nNext: python -m scripts.rates.barclays.rates_skew_load")
    return 0


if __name__ == "__main__":
    sys.exit(main())
