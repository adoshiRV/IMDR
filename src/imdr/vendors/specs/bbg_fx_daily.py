"""Feed: BBG FX rate DAILY close-of-day (mirror of bbg_fx_snapshot, DAILY cadence).

Reads the same ``Z:\\...\\BBG_mirror\\FX\\{CCY}\\FX_{CCY}.csv`` files
as the snapshot feed but stamps each captured row with
``frequency_id = DAILY`` and ``obs_ts = midnight UTC of obs_date``
(close-of-day semantics). Fires once per day from ``imdr_daily.py``
after the BBG 19:00 SGT batch + mirror sync settle (~22:00 SGT).

Idempotent on ``(pair_id, vendor_id, frequency_id, obs_ts, tenor)`` —
re-runs on the same business day are MERGE no-ops.

⚠️  READ-ONLY ACCESS TO Z:\\BBG_mirror\\FX  ⚠️
Same hard rule as ``bbg_fx_snapshot``. Enforced by the factory's
``archive_after_load=False`` + lock-in test
``tests/unit/test_vendors/test_bbg_no_move.py``.
"""
from __future__ import annotations

from functools import partial
from pathlib import Path

from imdr.config.settings import Settings
from imdr.connectors.mssql import MSSQLConnector
from imdr.domains.fx.pipeline_rate_bbg_daily import BloombergFXRateDailyPipeline
from imdr.notifications.formatters.fx_rate_ingest import FXRateIngestFormatter
from imdr.universe.fx import get_fx_universe
from imdr.vendors.registry import register_feed
from imdr.vendors.specs._bbg_factory import (
    BBG_FX_ROOT,
    build_bbg_feed,
    fx_patterns_from_universe,
    fx_success_context,
)

FEED_NAME = "bbg_fx_daily"

_PATTERNS = fx_patterns_from_universe()


def _build_pipeline(
    files: list[Path],
    connector: MSSQLConnector,
    settings: Settings,
) -> BloombergFXRateDailyPipeline:
    return BloombergFXRateDailyPipeline(
        files=files,
        connector=connector,
        settings=settings,
        universe=get_fx_universe(),
        bbg_fx_root=BBG_FX_ROOT,
    )


SPEC, FEED = build_bbg_feed(
    name=FEED_NAME,
    root=BBG_FX_ROOT,
    patterns=_PATTERNS,
    pipeline_builder=_build_pipeline,
    success_formatter=FXRateIngestFormatter(),
    staleness_pipeline_name="fx.bloomberg_daily",
    success_context_builder=partial(
        fx_success_context, mode_label="Daily", frequency="DAILY"
    ),
    min_matches=len(_PATTERNS) // 2,
)

register_feed(FEED)
