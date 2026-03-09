"""FX OHLC pipeline — thin wrapper around shared ingest logic.

Provides BasePipeline's audit trail for scheduled runs.

Target table: [FX].[fact_ohlc]
"""

from __future__ import annotations

from typing import Any

from imdr.config.pipeline_config import get_pipeline_config
from imdr.config.settings import Settings
from imdr.connectors.mssql import MSSQLConnector
from imdr.domains.fx.extractors import PairCache
from imdr.domains.fx.ingest import HourResult, process_hour
from imdr.domains.fx.time_utils import HourWindow
from imdr.pipelines.base import BasePipeline
from imdr.reporting.run_report import RunReport
from imdr.universe.fx import FXUniverse


class FXOHLCPipeline(BasePipeline[None, None, HourResult]):
    """FX OHLC bar ingestion pipeline.

    Delegates to process_hour() from ingest.py for the actual work.
    Provides BasePipeline audit trail + health check integration.
    """

    pipeline_name = "fx.ohlc"
    domain = "fx"

    def __init__(
        self,
        connector: MSSQLConnector,
        settings: Settings,
        universe: FXUniverse,
        window: HourWindow,
        report: RunReport | None = None,
        pair_cache: PairCache | None = None,
    ) -> None:
        super().__init__(connector)
        self._settings = settings
        self._universe = universe
        self._window = window
        self._report = report or RunReport(pipeline_name=self.pipeline_name)
        self._pair_cache = pair_cache
        self._result: HourResult | None = None

    def extract(self) -> None:
        # All work delegated to process_hour() in run()
        return None

    def transform(self, raw: None) -> None:
        return None

    def load(self, data: None) -> HourResult:
        # process_hour handles extract + transform + validate + load + parquet
        result = process_hour(
            window=self._window,
            universe=self._universe,
            settings=self._settings,
            connector=self._connector,
            report=self._report,
            pair_cache=self._pair_cache,
        )
        self._result = result
        return result

    def get_run_context(self) -> dict[str, Any]:
        return {
            "run_date": self._window.start.date(),
            "window": str(self._window),
        }
