"""Feed: BBG rates DAILY close-of-day (mirror of bbg_rates_snapshot, DAILY cadence).

Reads the same ``Z:\\...\\BBG_mirror\\{IRS,OIS,BASIS,CCS}\\...`` files as
the snapshot feed but stamps each captured row with
``frequency_id = DAILY`` and ``ts = midnight UTC of obs_date``
(close-of-day semantics). Fires once per day from ``imdr_daily.py``
after the BBG 19:00 SGT batch + mirror sync settle (~22:00 SGT).

Idempotent on ``(curve_id, vendor_id, ts, quote, tenor, frequency_id)``
— re-runs on the same business day are MERGE no-ops.

⚠️  READ-ONLY ACCESS TO Z:\\BBG_mirror\\  ⚠️
Same hard rule as ``bbg_rates_snapshot``. Enforced by the factory's
``archive_after_load=False`` + lock-in test
``tests/unit/test_vendors/test_bbg_no_move.py``.
"""
from __future__ import annotations

from functools import partial
from pathlib import Path

from imdr.config.settings import Settings
from imdr.connectors.mssql import MSSQLConnector
from imdr.domains.rates.pipeline_bbg_daily import BloombergRatesDailyPipeline
from imdr.notifications.formatters.rates_ingest import RatesIngestFormatter
from imdr.vendors.registry import register_feed
from imdr.vendors.specs._bbg_factory import (
    BBG_MIRROR_ROOT,
    RATES_PATTERNS,
    build_bbg_feed,
    rates_success_context,
)

FEED_NAME = "bbg_rates_daily"


def _build_pipeline(
    files: list[Path],
    connector: MSSQLConnector,
    settings: Settings,
) -> BloombergRatesDailyPipeline:
    return BloombergRatesDailyPipeline(
        files=files,
        connector=connector,
        settings=settings,
        bbg_root=BBG_MIRROR_ROOT,
        historical=False,  # daily live: latest row only, ts=midnight UTC, freq=DAILY
    )


SPEC, FEED = build_bbg_feed(
    name=FEED_NAME,
    root=BBG_MIRROR_ROOT,
    patterns=RATES_PATTERNS,
    pipeline_builder=_build_pipeline,
    success_formatter=RatesIngestFormatter(),
    staleness_pipeline_name="rates.bloomberg_daily",
    success_context_builder=partial(
        rates_success_context, mode_label="Daily", frequency="DAILY"
    ),
    min_matches=15,
)

register_feed(FEED)
