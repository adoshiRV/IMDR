"""Feed: BBG rates snapshots (IRS / OIS / BASIS / CCS PAR curves on Z:\\).

Reads ``Z:\\...\\BBG_mirror\\{IRS,OIS,BASIS,CCS}\\{CURVE}\\PAR\\<KIND>_PAR_<CURVE>.csv``
6x daily, stamping each ingested row with ``ts`` = file mtime (UTC).
Idempotent on the ``(curve_id, vendor_id, ts, quote, tenor, frequency_id)``
unique key — re-runs within the same BBG batch window are no-ops.

⚠️  READ-ONLY ACCESS TO Z:\\BBG_mirror\\  ⚠️
The R pipeline owns these CSVs and overwrites them in place. IMDR MUST
NOT move/rename/delete/modify them. Enforced by the factory's
``archive_after_load=False`` + lock-in test
``tests/unit/test_vendors/test_bbg_no_move.py``.

The mirror tree itself acts as the curve filter: only what's mirrored
gets ingested. See ``docs/rates/rates_bbg.md`` for operational details.
"""
from __future__ import annotations

from functools import partial
from pathlib import Path

from imdr.config.settings import Settings
from imdr.connectors.mssql import MSSQLConnector
from imdr.domains.rates.pipeline_bbg import BloombergRatesPipeline
from imdr.notifications.formatters.rates_ingest import RatesIngestFormatter
from imdr.vendors.registry import register_feed
from imdr.vendors.specs._bbg_factory import (
    BBG_MIRROR_ROOT,
    RATES_PATTERNS,
    build_bbg_feed,
    rates_success_context,
)

FEED_NAME = "bbg_rates_snapshot"


def _build_pipeline(
    files: list[Path],
    connector: MSSQLConnector,
    settings: Settings,
) -> BloombergRatesPipeline:
    return BloombergRatesPipeline(
        files=files,
        connector=connector,
        settings=settings,
        bbg_root=BBG_MIRROR_ROOT,
    )


SPEC, FEED = build_bbg_feed(
    name=FEED_NAME,
    root=BBG_MIRROR_ROOT,
    patterns=RATES_PATTERNS,
    pipeline_builder=_build_pipeline,
    success_formatter=RatesIngestFormatter(),
    staleness_pipeline_name="rates.bloomberg_snapshot",
    success_context_builder=partial(
        rates_success_context, mode_label="Snapshot", frequency="SNAPSHOT"
    ),
    # Mirror typically holds ~30 curves across 4 domains. Below 15 → upstream issue.
    min_matches=15,
)

register_feed(FEED)
