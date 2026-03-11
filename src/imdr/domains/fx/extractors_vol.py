"""Citi Velocity FX vol extractor — fetch vol surfaces, batch + rate limit.

Uses shared fetch_and_parse_batched() — zero duplicated batch loop.
"""
from __future__ import annotations

from datetime import datetime

import pandas as pd
import structlog

from imdr.config.settings import Settings
from imdr.connectors.citi_helpers import fetch_and_parse_batched
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
    ) -> None:
        self._client = client
        self._batch_size = settings.citi_batch_size
        self._rate_limit = settings.citi_rate_limit_sec
        self._universe = universe

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

        frames: list[pd.DataFrame] = []
        for ccy1, ccy2 in vol_pairs:
            tags = self._universe.build_vol_tags(ccy1, ccy2)
            _log.info("fetching_pair", pair=f"{ccy1}/{ccy2}", n_tags=len(tags))

            df = fetch_and_parse_batched(
                self._client, tags, start, end, frequency,
                self._batch_size, self._rate_limit,
                response_parser=citi_vol_response_to_df,
            )
            if not df.empty:
                frames.append(df)

        if not frames:
            return pd.DataFrame(columns=COLUMNS)

        return pd.concat(frames, ignore_index=True)
