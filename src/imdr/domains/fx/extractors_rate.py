"""Citi Velocity FX rate extractor — spot + forward outrights + forward points.

Fetches three tag families for each pair in the fx_rate universe, pivots the
long-form response into wide (mid_rate + fwd_points columns), and returns a
single DataFrame ready for the pipeline's transform step.

Uses shared fetch_and_parse_batched() — zero duplicated batch loop.
"""
from __future__ import annotations

from datetime import datetime

import pandas as pd
import structlog

from imdr.config.settings import Settings
from imdr.connectors.citi_helpers import TagQuotaExceeded, fetch_and_parse_batched
from imdr.connectors.citi_quota import TagQuotaTracker
from imdr.connectors.citi_velocity import CitiVelocityClient
from imdr.domains.fx.rate_translate import (
    WIDE_COLUMNS,
    citi_fx_rate_response_to_long_df,
    pivot_long_to_wide,
)
from imdr.universe.fx import FXUniverse

_log = structlog.get_logger("FXRateExtractor")


class CitiVelocityFXRateExtractor:
    """Extract FX rates (spot + forward outrights + forward points) from Citi."""

    def __init__(
        self,
        client: CitiVelocityClient,
        settings: Settings,
        universe: FXUniverse,
        quota_tracker: TagQuotaTracker | None = None,
    ) -> None:
        self._client = client
        self._batch_size = settings.citi_batch_size
        self._rate_limit = settings.citi_rate_limit_sec
        self._universe = universe
        self._quota_tracker = quota_tracker
        self._errors: list[dict] = []

    def extract(
        self,
        start: datetime,
        end: datetime,
        pairs: list[tuple[str, str]] | None = None,
        frequency: str = "DAILY",
    ) -> pd.DataFrame:
        """Fetch rates for all (or specified) fx_rate pairs.

        Returns
        -------
        pd.DataFrame with columns [ts, base_ccy, quote_ccy, tenor, mid_rate, fwd_points].
        """
        rate_pairs = pairs or self._universe.fx_rate_pairs()
        spot_only = self._universe.fx_rate_spot_only_pairs()
        _log.info("extract_start", n_pairs=len(rate_pairs))

        # Pre-flight budget check
        if self._quota_tracker is not None:
            estimated_tags = 0
            for ccy1, ccy2 in rate_pairs:
                estimated_tags += 1  # spot
                if (ccy1, ccy2) not in spot_only:
                    estimated_tags += 2 * len(self._universe.fx_rate_forward_tenors())
            self._quota_tracker.check_budget(estimated_tags, "fx.citi_rate")

        long_frames: list[pd.DataFrame] = []
        for ccy1, ccy2 in rate_pairs:
            tags: list[str] = [self._universe.build_fx_rate_spot_tag(ccy1, ccy2)]
            if (ccy1, ccy2) not in spot_only:
                tags.extend(self._universe.build_fx_rate_outright_tags(ccy1, ccy2))
                tags.extend(self._universe.build_fx_rate_point_tags(ccy1, ccy2))

            _log.info("fetching_pair", pair=f"{ccy1}/{ccy2}", n_tags=len(tags))
            try:
                df = fetch_and_parse_batched(
                    self._client, tags, start, end, frequency,
                    self._batch_size, self._rate_limit,
                    response_parser=citi_fx_rate_response_to_long_df,
                    quota_tracker=self._quota_tracker,
                    pipeline_name="fx.citi_rate",
                )
                if not df.empty:
                    long_frames.append(df)
            except TagQuotaExceeded:
                _log.error("tag_quota_exceeded", pair=f"{ccy1}/{ccy2}")
                raise
            except Exception as e:
                self._errors.append({"pair": f"{ccy1}/{ccy2}", "error": str(e)})
                _log.exception("pair_fetch_failed", pair=f"{ccy1}/{ccy2}")

        if not long_frames:
            return pd.DataFrame(columns=WIDE_COLUMNS)

        long_df = pd.concat(long_frames, ignore_index=True)
        wide_df = pivot_long_to_wide(long_df)
        _log.info("extract_done", long_rows=len(long_df), wide_rows=len(wide_df))
        return wide_df
