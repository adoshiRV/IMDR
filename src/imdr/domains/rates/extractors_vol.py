"""Citi Velocity rates swaption vol extractor — fetch vol surfaces, batch + rate limit.

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
from imdr.domains.rates.vol_translate import COLUMNS, citi_rates_vol_response_to_df
from imdr.universe.rates import RatesUniverse

_log = structlog.get_logger("RatesVolExtractor")


class CitiVelocityRatesVolExtractor:
    """Extract swaption vol surfaces from Citi Velocity Historical API."""

    def __init__(
        self,
        client: CitiVelocityClient,
        settings: Settings,
        universe: RatesUniverse,
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
        currencies: list[str] | None = None,
        frequency: str = "DAILY",
    ) -> pd.DataFrame:
        """Fetch vol surfaces for all (or specified) currencies.

        Parameters
        ----------
        start, end : datetime (UTC)
        currencies : optional list of currency codes (e.g. ["USD", "EUR"])
        frequency : API frequency

        Returns
        -------
        pd.DataFrame with columns defined in vol_translate.COLUMNS
        """
        ccys = currencies or self._universe.vol_currencies()
        _log.info("extract_start", n_currencies=len(ccys))

        # Pre-flight budget check
        if self._quota_tracker is not None:
            estimated_tags = sum(
                len(self._universe.build_vol_tags(c)) for c in ccys
            )
            self._quota_tracker.check_budget(estimated_tags, "rates_vol.citi_live")

        frames: list[pd.DataFrame] = []
        for ccy in ccys:
            tags = self._universe.build_vol_tags(ccy)
            _log.info("fetching_ccy", ccy=ccy, n_tags=len(tags))

            try:
                df = fetch_and_parse_batched(
                    self._client, tags, start, end, frequency,
                    self._batch_size, self._rate_limit,
                    response_parser=citi_rates_vol_response_to_df,
                    quota_tracker=self._quota_tracker,
                    pipeline_name="rates_vol.citi_live",
                )
                if not df.empty:
                    frames.append(df)
            except TagQuotaExceeded:
                _log.error("tag_quota_exceeded", ccy=ccy)
                raise
            except Exception as e:
                self._errors.append({"ccy": ccy, "error": str(e)})
                _log.exception("ccy_fetch_failed", ccy=ccy)

        if not frames:
            return pd.DataFrame(columns=COLUMNS)

        return pd.concat(frames, ignore_index=True)
