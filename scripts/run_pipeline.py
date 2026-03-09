"""Generic pipeline runner.

Usage:
    python -m scripts.run_pipeline fx.spot_rates --source csv --path data/fx.csv
    python -m scripts.run_pipeline fx.spot_rates --source bidfx
    python -m scripts.run_pipeline fx.ohlc --hour 2026-03-09T13:00:00
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from imdr.config.settings import get_settings
from imdr.connectors.mssql import MSSQLConnector
from imdr.pipelines.base import BasePipeline
from imdr.utils.logging import configure_logging

# Type alias for pipeline factory functions
PipelineFactory = Callable[[MSSQLConnector, argparse.Namespace], BasePipeline[Any, Any, Any]]


def _build_fx_pipeline(
    connector: MSSQLConnector, args: argparse.Namespace
) -> BasePipeline[Any, Any, Any]:
    """Build an FX pipeline based on CLI args."""
    from imdr.domains.fx.pipeline import FXSpotRatePipeline

    settings = get_settings()

    if args.source == "csv":
        if not args.path:
            print("ERROR: --path is required when source=csv")
            sys.exit(1)
        return FXSpotRatePipeline(connector, source_path=Path(args.path))

    if args.source in ("bidfx", "citivelocity"):
        from imdr.connectors.http import HTTPClient
        from imdr.domains.fx.extractors import BidFXExtractor, CitiVelocityExtractor

        api_key = settings.bidfx_api_key if args.source == "bidfx" else settings.citivelocity_api_key
        http = HTTPClient(
            timeout=settings.http_timeout,
            headers={"Authorization": f"Bearer {api_key}"} if api_key else {},
        )
        extractor = BidFXExtractor(http) if args.source == "bidfx" else CitiVelocityExtractor(http)
        return FXSpotRatePipeline(connector, extractor=extractor)

    print(f"ERROR: Unknown source '{args.source}'")
    sys.exit(1)


def _build_fx_ohlc_pipeline(
    connector: MSSQLConnector, args: argparse.Namespace
) -> BasePipeline[Any, Any, Any]:
    """Build an FX OHLC pipeline based on CLI args."""
    from datetime import datetime, timezone

    from imdr.domains.fx.pipeline_ohlc import FXOHLCPipeline
    from imdr.domains.fx.time_utils import HourWindow, last_full_utc_hour
    from imdr.universe.fx import get_fx_universe

    settings = get_settings()
    universe = get_fx_universe()

    if hasattr(args, "hour") and args.hour:
        start = datetime.fromisoformat(args.hour).replace(tzinfo=timezone.utc)
        from datetime import timedelta

        window = HourWindow(start=start, end=start + timedelta(hours=1))
    else:
        window = last_full_utc_hour()

    return FXOHLCPipeline(
        connector=connector,
        settings=settings,
        universe=universe,
        window=window,
    )


# Registry maps pipeline names to their factory functions.
# Add new pipelines here — no if-chain needed in main().
PIPELINE_REGISTRY: dict[str, PipelineFactory] = {
    "fx.spot_rates": _build_fx_pipeline,
    "fx.ohlc": _build_fx_ohlc_pipeline,
}


def main() -> int:
    parser = argparse.ArgumentParser(description="IMDR Pipeline Runner")
    parser.add_argument("pipeline", choices=PIPELINE_REGISTRY.keys(), help="Pipeline to run")
    parser.add_argument("--source", default="csv", help="Data source (csv, bidfx, citivelocity)")
    parser.add_argument("--path", type=str, help="File path (when source=csv)")
    parser.add_argument("--hour", type=str, help="Hour override for fx.ohlc (ISO format)")
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings)
    connector = MSSQLConnector(settings)

    try:
        factory = PIPELINE_REGISTRY[args.pipeline]
        pipeline = factory(connector, args)
        result = pipeline.run()
        print(f"Pipeline '{args.pipeline}' completed. Rows loaded: {result}")
        return 0
    except Exception as exc:
        print(f"Pipeline '{args.pipeline}' FAILED: {exc}")
        return 1
    finally:
        connector.dispose()


if __name__ == "__main__":
    sys.exit(main())
