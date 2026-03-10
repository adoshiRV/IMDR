"""Citi Velocity rates extractor — fetch historical data, batch + rate limit.

Rewrite of RATES_data/src/fetch.py as an IMDR extractor.
Orchestrates: for each curve x quote → build tags → batch (100 tags) → POST → parse.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import structlog

from imdr.connectors.citi_velocity import CitiVelocityClient
from imdr.config.settings import Settings
from imdr.domains.rates.schema import COLUMNS, QUOTE_TO_CITI
from imdr.domains.rates.translate import citi_response_to_df, internal_to_citi_tags
from imdr.domains.rates.utils import parse_x_to_ts_utc
from imdr.universe.rates import RatesUniverse, get_rates_universe

_log = structlog.get_logger("RatesExtractor")


class CitiVelocityRatesExtractor:
    """Extract rates data from Citi Velocity Historical API.

    Handles batching (100 tags per request), rate limiting, and response parsing.
    """

    def __init__(
        self,
        client: CitiVelocityClient,
        settings: Settings,
        universe: RatesUniverse | None = None,
    ) -> None:
        self._client = client
        self._batch_size = settings.citi_batch_size
        self._rate_limit = settings.citi_rate_limit_sec
        self._universe = universe or get_rates_universe()

    def extract(
        self,
        start: datetime,
        end: datetime,
        quotes: list[str] | None = None,
        frequency: str = "DAILY",
        curves: list[tuple[str, str]] | None = None,
    ) -> pd.DataFrame:
        """Fetch all curves for a date range.

        Parameters
        ----------
        start, end : datetime (UTC)
        quotes : list of internal quote codes. Default: ["par"]
        frequency : API frequency (DAILY, HOURLY, etc.)
        curves : list of (ccy, curve) tuples. Default: all catalog curves.

        Returns
        -------
        pd.DataFrame with columns [ts, ccy, curve, quote, tenor, value]
        """
        if quotes is None:
            quotes = ["par"]

        if curves is None:
            curves = [(c.ccy, c.curve) for c in self._universe.all_curves()]

        total = len(curves) * len(quotes)
        _log.info("extract_start", n_curves=len(curves), n_quotes=len(quotes), total_jobs=total)

        frames: list[pd.DataFrame] = []
        done = 0

        for ccy, curve in curves:
            for quote in quotes:
                done += 1
                try:
                    df = self._fetch_curve(ccy, curve, quote, start, end, frequency)
                    if not df.empty:
                        frames.append(df)
                    _log.info(
                        "curve_fetched",
                        progress=f"{done}/{total}",
                        ccy=ccy, curve=curve, quote=quote,
                        rows=len(df),
                    )
                except Exception:
                    _log.exception("curve_fetch_failed", ccy=ccy, curve=curve, quote=quote)

        if not frames:
            return pd.DataFrame(columns=COLUMNS)

        return pd.concat(frames, ignore_index=True).sort_values(
            ["ccy", "curve", "quote", "tenor", "ts"]
        ).reset_index(drop=True)

    def _fetch_curve(
        self,
        ccy: str,
        curve: str,
        quote: str,
        start: datetime,
        end: datetime,
        frequency: str,
    ) -> pd.DataFrame:
        """Fetch a single curve/quote combo, batching tags."""
        citi_qt = QUOTE_TO_CITI[quote.lower()]
        tags = self._universe.build_tags(ccy, curve, citi_qt)

        if not tags:
            return pd.DataFrame(columns=COLUMNS)

        return self._fetch_batched(tags, start, end, frequency)

    def _fetch_batched(
        self,
        tags: list[str],
        start: datetime,
        end: datetime,
        frequency: str,
    ) -> pd.DataFrame:
        """Fetch in batches of batch_size, respecting rate limit."""
        frames: list[pd.DataFrame] = []

        for i in range(0, len(tags), self._batch_size):
            batch = tags[i : i + self._batch_size]

            resp = self._client.fetch_historical(
                tags=batch,
                start=start,
                end=end,
                frequency=frequency,
            )
            df = citi_response_to_df(resp, parse_x_to_ts_utc, self._universe)

            if not df.empty:
                frames.append(df)

            # Rate limit between batches
            if i + self._batch_size < len(tags):
                time.sleep(self._rate_limit)

        if not frames:
            return pd.DataFrame(columns=COLUMNS)

        return pd.concat(frames, ignore_index=True)
