"""Citi Velocity commodities extractor — SPOT, EIA, and IMPLIED_VOL.

Single class with three extract methods. All use shared fetch_and_parse_batched()
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
from imdr.domains.commodities.translate_eia import COLUMNS as EIA_COLUMNS
from imdr.domains.commodities.translate_eia import citi_eia_response_to_df
from imdr.domains.commodities.translate_spot import COLUMNS as SPOT_COLUMNS
from imdr.domains.commodities.translate_spot import citi_spot_response_to_df
from imdr.domains.commodities.translate_vol import COLUMNS as VOL_COLUMNS
from imdr.domains.commodities.translate_vol import citi_cmdty_vol_response_to_df
from imdr.universe.commodities import CommoditiesUniverse

_log = structlog.get_logger("CmdtyExtractor")


class CitiVelocityCmdtyExtractor:
    """Extract commodity data from Citi Velocity Historical API."""

    def __init__(
        self,
        client: CitiVelocityClient,
        settings: Settings,
        universe: CommoditiesUniverse,
        quota_tracker: TagQuotaTracker | None = None,
    ) -> None:
        self._client = client
        self._batch_size = settings.citi_batch_size
        self._rate_limit = settings.citi_rate_limit_sec
        self._universe = universe
        self._quota_tracker = quota_tracker
        self._errors: list[dict] = []

    # ── SPOT (3 tags) ────────────────────────────────────────────

    def extract_spot(
        self,
        start: datetime,
        end: datetime,
        frequency: str = "DAILY",
    ) -> pd.DataFrame:
        """Fetch commodity spot prices (Gold, Silver, WTI)."""
        tags = list(self._universe.spot_tags().keys())
        _log.info("extract_spot_start", n_tags=len(tags))

        if self._quota_tracker is not None:
            self._quota_tracker.check_budget(len(tags), "commodities.spot")

        try:
            df = fetch_and_parse_batched(
                self._client, tags, start, end, frequency,
                self._batch_size, self._rate_limit,
                response_parser=citi_spot_response_to_df,
                quota_tracker=self._quota_tracker,
                pipeline_name="commodities.spot",
            )
        except TagQuotaExceeded:
            raise
        except Exception as e:
            self._errors.append({"product": "SPOT", "error": str(e)})
            _log.exception("spot_fetch_failed")
            return pd.DataFrame(columns=SPOT_COLUMNS)

        _log.info("extract_spot_complete", rows=len(df))
        return df

    # ── EIA (67 tags) ────────────────────────────────────────────

    def extract_eia(
        self,
        start: datetime,
        end: datetime,
        frequency: str = "DAILY",
    ) -> pd.DataFrame:
        """Fetch EIA petroleum status report data."""
        tags = self._universe.build_eia_tags()
        _log.info("extract_eia_start", n_tags=len(tags))

        if self._quota_tracker is not None:
            self._quota_tracker.check_budget(len(tags), "commodities.eia")

        try:
            df = fetch_and_parse_batched(
                self._client, tags, start, end, frequency,
                self._batch_size, self._rate_limit,
                response_parser=citi_eia_response_to_df,
                quota_tracker=self._quota_tracker,
                pipeline_name="commodities.eia",
            )
        except TagQuotaExceeded:
            raise
        except Exception as e:
            self._errors.append({"product": "EIA", "error": str(e)})
            _log.exception("eia_fetch_failed")
            return pd.DataFrame(columns=EIA_COLUMNS)

        _log.info("extract_eia_complete", rows=len(df))
        return df

    # ── IMPLIED_VOL (1,011 tags) ─────────────────────────────────

    def extract_vol(
        self,
        start: datetime,
        end: datetime,
        products: list[str] | None = None,
        frequency: str = "DAILY",
    ) -> pd.DataFrame:
        """Fetch commodity implied vol surfaces for all (or specified) products."""
        target_products = products or self._universe.vol_products()
        _log.info("extract_vol_start", n_products=len(target_products))

        # Pre-flight budget check across all products
        if self._quota_tracker is not None:
            estimated_tags = sum(
                len(self._universe.build_vol_tags(p)) for p in target_products
            )
            self._quota_tracker.check_budget(estimated_tags, "commodities.vol")

        frames: list[pd.DataFrame] = []
        for product in target_products:
            tags = self._universe.build_vol_tags(product)
            _log.info("fetching_product", product=product, n_tags=len(tags))

            try:
                df = fetch_and_parse_batched(
                    self._client, tags, start, end, frequency,
                    self._batch_size, self._rate_limit,
                    response_parser=citi_cmdty_vol_response_to_df,
                    quota_tracker=self._quota_tracker,
                    pipeline_name="commodities.vol",
                )
                if not df.empty:
                    frames.append(df)
            except TagQuotaExceeded:
                _log.error("tag_quota_exceeded", product=product)
                raise
            except Exception as e:
                self._errors.append({"product": product, "error": str(e)})
                _log.exception("product_fetch_failed", product=product)

        if not frames:
            return pd.DataFrame(columns=VOL_COLUMNS)

        return pd.concat(frames, ignore_index=True)
