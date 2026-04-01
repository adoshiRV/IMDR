"""Citi Velocity FX vol extractor — fetch vol surfaces, batch + rate limit.

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
from imdr.domains.fx.vol_translate import COLUMNS, citi_vol_response_to_df
from imdr.universe.fx import FXUniverse

_log = structlog.get_logger("FXVolExtractor")


class CitiVelocityFXVolExtractor:
    """Extract FX vol surfaces from Citi Velocity Historical API."""

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
        """Fetch vol surfaces for all (or specified) pairs.

        Parameters
        ----------
        start, end : datetime (UTC)
        pairs : optional list of (ccy1, ccy2) tuples
        frequency : API frequency

        Returns
        -------
        pd.DataFrame with columns [ts, base_ccy, quote_ccy, strike, tenor, vol_type, value]
        """
        vol_pairs = pairs or self._universe.vol_pairs()
        _log.info("extract_start", n_pairs=len(vol_pairs))

        # Pre-flight budget check
        if self._quota_tracker is not None:
            estimated_tags = sum(
                len(self._universe.build_vol_tags(c1, c2)) for c1, c2 in vol_pairs
            )
            self._quota_tracker.check_budget(estimated_tags, "fx_vol.citi_live")

        frames: list[pd.DataFrame] = []
        for ccy1, ccy2 in vol_pairs:
            tags = self._universe.build_vol_tags(ccy1, ccy2)
            _log.info("fetching_pair", pair=f"{ccy1}/{ccy2}", n_tags=len(tags))

            try:
                df = fetch_and_parse_batched(
                    self._client, tags, start, end, frequency,
                    self._batch_size, self._rate_limit,
                    response_parser=citi_vol_response_to_df,
                    quota_tracker=self._quota_tracker,
                    pipeline_name="fx_vol.citi_live",
                )
                if not df.empty:
                    frames.append(df)
            except TagQuotaExceeded:
                _log.error("tag_quota_exceeded", pair=f"{ccy1}/{ccy2}")
                raise
            except Exception as e:
                self._errors.append({"pair": f"{ccy1}/{ccy2}", "error": str(e)})
                _log.exception("pair_fetch_failed", pair=f"{ccy1}/{ccy2}")

        if not frames:
            return pd.DataFrame(columns=COLUMNS)

        return pd.concat(frames, ignore_index=True)
