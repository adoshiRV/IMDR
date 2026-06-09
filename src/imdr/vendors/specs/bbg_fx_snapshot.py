"""Feed: BBG FX rate snapshots (multi-PC R-pipeline outputs on Z:\\).

Reads ``Z:\\...\\BBG_mirror\\FX\\{CCY}\\FX_{CCY}.csv`` 6x daily, stamping
each ingested row with ``obs_ts`` = file mtime (UTC). Idempotent on the
``(pair_id, vendor_id, frequency_id, obs_ts, tenor)`` unique key —
re-runs within the same BBG batch window are no-ops.

⚠️  READ-ONLY ACCESS TO Z:\\BBG_mirror\\FX  ⚠️
The R pipeline owns these CSVs and overwrites them in place. IMDR MUST
NOT move/rename/delete/modify them. Enforced by the factory's
``archive_after_load=False`` + lock-in test
``tests/unit/test_vendors/test_bbg_no_move.py``.

See ``docs/admin/vendors/bbg/imdr_integration_plan.md`` for the design.
"""
from __future__ import annotations

from functools import partial
from pathlib import Path

from imdr.config.settings import Settings
from imdr.connectors.mssql import MSSQLConnector
from imdr.domains.fx.pipeline_rate_bbg import BloombergFXRatePipeline
from imdr.notifications.formatters.fx_rate_ingest import FXRateIngestFormatter
from imdr.universe.fx import get_fx_universe
from imdr.vendors.registry import register_feed
from imdr.vendors.specs._bbg_factory import (
    BBG_FX_ROOT,
    build_bbg_feed,
    fx_patterns_from_universe,
    fx_success_context,
)

FEED_NAME = "bbg_fx_snapshot"

_PATTERNS = fx_patterns_from_universe()


def _build_pipeline(
    files: list[Path],
    connector: MSSQLConnector,
    settings: Settings,
) -> BloombergFXRatePipeline:
    return BloombergFXRatePipeline(
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
    staleness_pipeline_name="fx.bloomberg_snapshot",
    success_context_builder=partial(
        fx_success_context, mode_label="Snapshot", frequency="SNAPSHOT"
    ),
    min_matches=len(_PATTERNS) // 2,
)

register_feed(FEED)
