"""Probe Citi Velocity API quota — test with increasing batch sizes.

Run:
    python -m scripts.explore.probe_citi_quota
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone

import structlog

from imdr.config.settings import get_settings
from imdr.connectors.citi_helpers import TagQuotaExceeded
from imdr.connectors.citi_velocity import CitiVelocityClient
from imdr.universe.rates import get_rates_universe
from imdr.utils.logging import configure_logging

log = structlog.get_logger(__name__)


def main() -> int:
    settings = get_settings()
    configure_logging(settings)
    universe = get_rates_universe()

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=1)

    # Get a small set of real tags
    usd_tags = universe.build_vol_tags("USD")
    test_sizes = [1, 10, 100]

    with CitiVelocityClient(settings) as client:
        for n in test_sizes:
            batch = usd_tags[:n]
            log.info("testing_batch", n_tags=n)
            try:
                resp = client.fetch_historical(batch, start, end)
                status = resp.get("status")
                n_returned = len(resp.get("body", {})) if status == "OK" else 0
                print(f"  {n:>4} tags -> {status}, returned {n_returned} series")
                print(f"       rate_limit_remaining={client.rate_limit_remaining}")

                # Check for quota info in body (non-OK responses)
                if status != "OK":
                    print(f"       message: {resp.get('message', 'n/a')}")
                    break

            except TagQuotaExceeded as e:
                print(f"  {n:>4} tags -> QUOTA EXCEEDED")
                print(f"       current_usage={e.current_usage}, available={e.available}")
                break
            except Exception as e:
                print(f"  {n:>4} tags -> ERROR: {e}")
                break

        # Summary
        print("\n=== Rate Limit Headers ===")
        for k, v in client.rate_limit_info.items():
            print(f"  {k}: {v}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
