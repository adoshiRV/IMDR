"""Feed: Barclays SKEW (swaption skew Excel, daily via Outlook → Live portal).

Reference implementation of an email-linked download feed.  See
``docs/admin/vendors/feeds/barclays_skew.md`` for operational notes.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from imdr.config.settings import Settings
from imdr.connectors.mssql import MSSQLConnector
from imdr.domains.rates.pipeline_skew import RatesSkewPipeline
from imdr.notifications.formatters.rates_skew_ingest import RatesSkewIngestFormatter
from imdr.vendors.acquirers.email_linked import (
    EmailLinkedDownloadAcquirer,
    EmailLinkedDownloadSpec,
)
from imdr.vendors.base import VendorFeed
from imdr.vendors.helpers import resolve_vendor_id
from imdr.vendors.registry import register_feed

FEED_NAME = "barclays_skew"
VENDOR_CODE = "barclays"
OUTPUT_DIR = Path("data/skew")
LOAD_CHUNK_SIZE = 5000

SPEC = EmailLinkedDownloadSpec(
    name=FEED_NAME,
    vendor_code=VENDOR_CODE,
    sender="csa@barcap.com",
    subject_contains="SKEW BARCLAYS",
    link_label="View Excel",
    listing_anchor_selector='a[href*="/rare/retrieve"]',
    output_dir=OUTPUT_DIR,
    profile_name="barclays",
)


def _build_pipeline(
    files: list[Path],
    connector: MSSQLConnector,
    settings: Settings,
) -> RatesSkewPipeline:
    return RatesSkewPipeline(
        connector=connector,
        settings=settings,
        file_paths=files,
        vendor_id=resolve_vendor_id(connector, VENDOR_CODE),
        chunk_size=LOAD_CHUNK_SIZE,
    )


def _success_context(pipeline: RatesSkewPipeline, rows_loaded: int) -> dict[str, Any]:
    """Build per-expiry breakdown for the success email — parity with the
    standalone ``rates_skew_load.py`` report.

    Safe to call before or after ``pipeline.run()``; if ``_raw_df`` wasn't
    populated (e.g. extract returned empty), returns an empty list.
    """
    expiry_data: list[dict[str, Any]] = []
    df = getattr(pipeline, "_raw_df", None)
    if df is not None and not df.empty:
        for expiry in sorted(df["option_expiry"].unique()):
            mask = df["option_expiry"] == expiry
            expiry_data.append({
                "option_expiry": expiry,
                "n_obs": int(mask.sum()),
                "n_dates": int(df.loc[mask, "ts"].nunique()),
            })
    return {"expiry_data": expiry_data}


FEED = VendorFeed(
    name=FEED_NAME,
    vendor_code=VENDOR_CODE,
    acquirer=EmailLinkedDownloadAcquirer(SPEC),
    pipeline_builder=_build_pipeline,
    success_formatter=RatesSkewIngestFormatter(),
    staleness_pipeline_name="rates.skew_barclays_daily",
    success_context_builder=_success_context,
)

register_feed(FEED)
