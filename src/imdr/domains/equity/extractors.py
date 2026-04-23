"""Citi Velocity equity extractor — index levels and VIX family.

Single class with two extract methods. Uses shared fetch_and_parse_batched()
from citi_helpers — zero duplicated batch loop.
"""
from __future__ import annotations

from datetime import datetime

import pandas as pd
import structlog

from imdr.config.settings import Settings
from imdr.connectors.citi_helpers import TagQuotaExceeded, fetch_and_parse_batched
from imdr.connectors.citi_quota import TagQuotaTracker
from imdr.connectors.citi_velocity import CitiVelocityClient
from imdr.domains.equity.translate_index import COLUMNS, citi_index_response_to_df
from imdr.schemas.equity import VIX_TICKERS
from imdr.universe.equity import EquityUniverse

_log = structlog.get_logger("EquityExtractor")


class CitiVelocityEquityExtractor:
    """Extract equity index data from Citi Velocity Historical API."""

    def __init__(
        self,
        client: CitiVelocityClient,
        settings: Settings,
        universe: EquityUniverse,
        quota_tracker: TagQuotaTracker | None = None,
    ) -> None:
        self._client = client
        self._batch_size = settings.citi_batch_size
        self._rate_limit = settings.citi_rate_limit_sec
        self._universe = universe
        self._quota_tracker = quota_tracker
        self._errors: list[dict] = []

    # ── Index levels (24 tags) ───────────────────────────────────

    def extract_index(
        self,
        start: datetime,
        end: datetime,
        frequency: str = "DAILY",
    ) -> pd.DataFrame:
        """Fetch equity index levels (ex-VIX family)."""
        all_tags = self._universe.api_symbols()
        # Exclude VIX family tickers — they go through extract_vix
        tag_to_ticker = self._universe.tag_to_ticker()
        tags = [t for t in all_tags if tag_to_ticker.get(t, "") not in VIX_TICKERS]

        _log.info("extract_index_start", n_tags=len(tags))

        if self._quota_tracker is not None:
            self._quota_tracker.check_budget(len(tags), "equity.index")

        try:
            df = fetch_and_parse_batched(
                self._client, tags, start, end, frequency,
                self._batch_size, self._rate_limit,
                response_parser=citi_index_response_to_df,
                quota_tracker=self._quota_tracker,
                pipeline_name="equity.index",
            )
        except TagQuotaExceeded:
            raise
        except Exception as e:
            self._errors.append({"product": "INDEX", "error": str(e)})
            _log.exception("index_fetch_failed")
            return pd.DataFrame(columns=COLUMNS)

        _log.info("extract_index_complete", rows=len(df))
        return df

    # ── VIX family (5 tags) ──────────────────────────────────────

    def extract_vix(
        self,
        start: datetime,
        end: datetime,
        frequency: str = "DAILY",
    ) -> pd.DataFrame:
        """Fetch VIX family (VIX, VIX3M, VIX9D, VVIX, VXN)."""
        tags = [self._universe.tag_for_ticker(t) for t in sorted(VIX_TICKERS)]

        _log.info("extract_vix_start", n_tags=len(tags))

        if self._quota_tracker is not None:
            self._quota_tracker.check_budget(len(tags), "equity.vix")

        try:
            df = fetch_and_parse_batched(
                self._client, tags, start, end, frequency,
                self._batch_size, self._rate_limit,
                response_parser=citi_index_response_to_df,
                quota_tracker=self._quota_tracker,
                pipeline_name="equity.vix",
            )
        except TagQuotaExceeded:
            raise
        except Exception as e:
            self._errors.append({"product": "VIX", "error": str(e)})
            _log.exception("vix_fetch_failed")
            return pd.DataFrame(columns=COLUMNS)

        _log.info("extract_vix_complete", rows=len(df))
        return df
